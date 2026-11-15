"""Frozen synthetic fixtures for mb-conversation-loss-oracle.

Every request, payload, profile and label here is hand-written test data.
CASES holds the translation cases: a dialect-A source request, a dialect-B
target payload and the target profile. LABELS holds, per case, the
hand-written gold: (category, baseline verdict, rule-arm verdict, rule-arm
findings). Categories:

- "control": a permitted change (an encoding change only); it should not
  alarm. One control (a stripped trailing newline) is a known false alarm
  of the exact-text rule and is labelled with the alarm it raises.
- "fault": one planted avoidable loss or injection; findings list it.
- "forced": a change the declared target limits make necessary; it is
  reported as forced, not as a fault.
- "schema": a payload the toy static target check rejects.

Nothing here comes from the paper or the upstream repository.

Run: python3 -B fixtures.py   (prints one row per case and the counts)
"""

import copy

import conv_loss as M
import oracle as O

ALL_CONTROLS = ["max_tokens", "temperature_milli", "thinking_budget"]
PROFILES = {
    "full": {"has_system": True, "alternating": False, "controls": list(ALL_CONTROLS),
             "max_tokens_cap": 4096},
    "no_system": {"has_system": False, "alternating": False, "controls": list(ALL_CONTROLS),
                  "max_tokens_cap": 4096},
    "alternating": {"has_system": True, "alternating": True, "controls": list(ALL_CONTROLS),
                    "max_tokens_cap": 4096},
    "no_thinking": {"has_system": True, "alternating": False,
                    "controls": ["max_tokens", "temperature_milli"], "max_tokens_cap": 4096},
}

SYS0 = "You are a careful travel desk. Never book without the traveller's OK."
SYS1 = "Answer in plain English."
T3 = "Two trains: KTX 101 at 07:00 and KTX 105 at 09:30. Shall I hold one?"
T4 = "Hold KTX 105."

SOURCE0 = {
    "system": SYS0,
    "messages": [
        {"role": "user", "content": "Find me a train from Seoul to Busan on Friday."},
        {"role": "assistant", "tool_call": {"id": "c1", "name": "search_trains",
                                            "args": {"from": "Seoul", "to": "Busan",
                                                     "day": "Fri"}}},
        {"role": "tool", "call_id": "c1", "result": ["KTX 101 07:00", "KTX 105 09:30"],
         "is_error": False},
        {"role": "assistant", "content": T3},
        {"role": "user", "content": T4},
        {"role": "assistant", "tool_call": {"id": "c2", "name": "hold_seat",
                                            "args": {"train": "KTX 105"}}},
        {"role": "tool", "call_id": "c2", "result": "seat map unavailable", "is_error": True},
        {"role": "assistant", "content": "The hold failed; nothing is booked."},
    ],
    "tools": ["search_trains", "hold_seat", "cancel_hold"],
    "controls": {"max_tokens": 1024, "temperature_milli": 200},
}

# The faithful dialect-B translation of SOURCE0 under the "full" profile,
# written by hand (the suite checks it against encode_b).
TARGET0 = {
    "preamble": SYS0,
    "turns": [
        {"speaker": "human", "text": "Find me a train from Seoul to Busan on Friday."},
        {"speaker": "model", "invoke": {"ref": "c1", "fn": "search_trains",
                                        "params": {"from": "Seoul", "to": "Busan",
                                                   "day": "Fri"}}},
        {"speaker": "tool", "ref": "c1", "output": "KTX 101 07:00\nKTX 105 09:30",
         "failed": False},
        {"speaker": "model", "text": T3},
        {"speaker": "human", "text": T4},
        {"speaker": "model", "invoke": {"ref": "c2", "fn": "hold_seat",
                                        "params": {"train": "KTX 105"}}},
        {"speaker": "tool", "ref": "c2", "output": "seat map unavailable", "failed": True},
        {"speaker": "model", "text": "The hold failed; nothing is booked."},
    ],
    "functions": [{"name": "search_trains"}, {"name": "hold_seat"}, {"name": "cancel_hold"}],
    "settings": {"max_output": 1024, "temperature_milli": 200},
}

SOURCE1 = {
    "system": SYS1,
    "messages": [
        {"role": "user", "content": "Summarise the meeting notes."},
        {"role": "user", "content": "Use at most five lines."},
        {"role": "assistant", "content": "Here is a five-line summary."},
    ],
    "tools": ["read_notes"],
    "controls": {"max_tokens": 2000, "thinking_budget": 2048},
}

TARGET1 = {
    "preamble": SYS1,
    "turns": [
        {"speaker": "human", "text": "Summarise the meeting notes."},
        {"speaker": "human", "text": "Use at most five lines."},
        {"speaker": "model", "text": "Here is a five-line summary."},
    ],
    "functions": [{"name": "read_notes"}],
    "settings": {"max_output": 2000, "reasoning_budget": 2048},
}

MERGED1 = [{"speaker": "human", "text": "Summarise the meeting notes.\nUse at most five lines."},
           {"speaker": "model", "text": "Here is a five-line summary."}]


def _reverse_keys(v):
    if isinstance(v, dict):
        return dict((k, _reverse_keys(v[k])) for k in reversed(list(v)))
    if isinstance(v, list):
        return [_reverse_keys(x) for x in v]
    return v


def C(cid, source, target, profile):
    return {"case_id": cid, "source": source, "target": target,
            "profile": copy.deepcopy(PROFILES[profile])}


def S0(**over):
    s = copy.deepcopy(SOURCE0)
    s.update(over)
    return s


def S1(**over):
    s = copy.deepcopy(SOURCE1)
    s.update(over)
    return s


def T0(edit=None):
    t = copy.deepcopy(TARGET0)
    if edit:
        edit(t)
    return t


def T1(edit=None):
    t = copy.deepcopy(TARGET1)
    if edit:
        edit(t)
    return t


def _pop(key):
    return lambda t: t.pop(key)


def _turn(i, **fields):
    return lambda t: t["turns"][i].update(fields)


def _drop_turn_key(i, key):
    return lambda t: t["turns"][i].pop(key)


def _invoke(i, **fields):
    return lambda t: t["turns"][i]["invoke"].update(fields)


def _set(path, value):
    def edit(t):
        t[path] = value
    return edit


def _settings(**fields):
    def edit(t):
        t["settings"] = dict(fields)
    return edit


def _reminted(t):
    names = {"c1": "x-9", "c2": "x-4"}
    for turn in t["turns"]:
        if "invoke" in turn:
            turn["invoke"]["ref"] = names[turn["invoke"]["ref"]]
        if "ref" in turn:
            turn["ref"] = names[turn["ref"]]


def _cross_merge(t):
    t["turns"][3:5] = [{"speaker": "human", "text": T3 + "\n" + T4}]


def _swap_3_4(t):
    t["turns"][3], t["turns"][4] = t["turns"][4], t["turns"][3]


def _no_system_demoted(t):
    t.pop("preamble")
    t["turns"].insert(0, {"speaker": "human", "text": SYS0})


def _merged(t):
    t["turns"] = copy.deepcopy(MERGED1)


BIG1 = {"max_tokens": 8000, "thinking_budget": 2048}

CASES = {
    # Permitted changes (encoding only).
    "ctl-role-field-renamed": C("ctl-role-field-renamed", S0(), T0(), "full"),
    "ctl-key-order": C("ctl-key-order", S0(), _reverse_keys(T0()), "full"),
    "ctl-tools-reordered": C("ctl-tools-reordered", S0(),
                             T0(lambda t: t["functions"].reverse()), "full"),
    "ctl-ids-reminted": C("ctl-ids-reminted", S0(), T0(_reminted), "full"),
    "ctl-source-text-result": C(
        "ctl-source-text-result",
        S0(messages=[m if m.get("call_id") != "c1" else
                     dict(m, result="KTX 101 07:00\nKTX 105 09:30")
                     for m in copy.deepcopy(SOURCE0["messages"])]),
        T0(), "full"),
    "ctl-error-false-omitted": C("ctl-error-false-omitted", S0(),
                                 T0(_drop_turn_key(2, "failed")), "full"),
    "ctl-trailing-newline-stripped": C("ctl-trailing-newline-stripped",
                                       S0(system=SYS0 + "\n"), T0(), "full"),
    # Planted avoidable faults.
    "f-system-dropped": C("f-system-dropped", S0(), T0(_pop("preamble")), "full"),
    "f-system-altered": C("f-system-altered", S0(),
                          T0(_set("preamble", "You are a careful travel desk.")), "full"),
    "f-system-demoted-needlessly": C("f-system-demoted-needlessly", S0(),
                                     T0(_no_system_demoted), "full"),
    "f-system-dropped-no-system-target": C("f-system-dropped-no-system-target", S0(),
                                           T0(_pop("preamble")), "no_system"),
    "f-role-swap": C("f-role-swap", S0(), T0(_turn(3, speaker="human")), "full"),
    "f-text-altered": C("f-text-altered", S0(), T0(_turn(4, text="Hold KTX 101.")), "full"),
    "f-cross-role-merge": C("f-cross-role-merge", S0(), T0(_cross_merge), "full"),
    "f-same-role-merge-needless": C("f-same-role-merge-needless", S1(), T1(_merged), "full"),
    "f-reordered": C("f-reordered", S0(), T0(_swap_3_4), "full"),
    "f-message-dropped": C("f-message-dropped", S0(),
                           T0(lambda t: t["turns"].pop(7)), "full"),
    "f-message-injected": C("f-message-injected", S0(),
                            T0(lambda t: t["turns"].append(
                                {"speaker": "human", "text": "Also book a hotel."})), "full"),
    "f-error-flag-dropped": C("f-error-flag-dropped", S0(),
                              T0(_drop_turn_key(6, "failed")), "full"),
    "f-error-flag-injected": C("f-error-flag-injected", S0(),
                               T0(_turn(2, failed=True)), "full"),
    "f-tool-call-renamed": C("f-tool-call-renamed", S0(),
                             T0(_invoke(5, fn="cancel_hold")), "full"),
    "f-tool-args-altered": C("f-tool-args-altered", S0(),
                             T0(_invoke(1, params={"from": "Seoul", "to": "Busan",
                                                   "day": "Sat"})), "full"),
    "f-result-relinked": C("f-result-relinked", S0(), T0(_turn(6, ref="c1")), "full"),
    "f-result-altered": C("f-result-altered", S0(),
                          T0(_turn(2, output="KTX 101 07:00, KTX 105 09:30")), "full"),
    "f-tool-def-dropped": C("f-tool-def-dropped", S0(),
                            T0(lambda t: t["functions"].pop(2)), "full"),
    "f-tool-def-injected": C("f-tool-def-injected", S0(),
                             T0(lambda t: t["functions"].append({"name": "delete_booking"})),
                             "full"),
    "f-thinking-injected": C("f-thinking-injected", S0(),
                             T0(_settings(max_output=1024, temperature_milli=200,
                                          reasoning_budget=1024)), "full"),
    "f-control-dropped": C("f-control-dropped", S0(), T0(_settings(max_output=1024)), "full"),
    "f-control-altered": C("f-control-altered", S0(),
                           T0(_settings(max_output=512, temperature_milli=200)), "full"),
    "f-clamp-plus-injection": C("f-clamp-plus-injection", S1(controls=dict(BIG1)),
                                T1(_settings(max_output=4096, reasoning_budget=2048,
                                             temperature_milli=700)), "full"),
    # Forced by the declared target limits.
    "fo-max-tokens-clamped": C("fo-max-tokens-clamped", S1(controls=dict(BIG1)),
                               T1(_settings(max_output=4096, reasoning_budget=2048)), "full"),
    "fo-thinking-unsupported": C("fo-thinking-unsupported", S1(),
                                 T1(_settings(max_output=2000)), "no_thinking"),
    "fo-system-demoted": C("fo-system-demoted", S0(), T0(_no_system_demoted), "no_system"),
    "fo-same-role-merge": C("fo-same-role-merge", S1(), T1(_merged), "alternating"),
    # Rejected by the toy static target check.
    "s-over-cap": C("s-over-cap", S1(controls=dict(BIG1)),
                    T1(_settings(max_output=8000, reasoning_budget=2048)), "full"),
}

A = "avoidable"
F = "forced"
LABELS = {
    "ctl-role-field-renamed": ("control", "PASS", "PASS", ()),
    "ctl-key-order": ("control", "PASS", "PASS", ()),
    "ctl-tools-reordered": ("control", "PASS", "PASS", ()),
    "ctl-ids-reminted": ("control", "PASS", "PASS", ()),
    "ctl-source-text-result": ("control", "PASS", "PASS", ()),
    "ctl-error-false-omitted": ("control", "PASS", "PASS", ()),
    "ctl-trailing-newline-stripped": ("control", "PASS", "FAIL", (("CL02", "system", A),)),
    "f-system-dropped": ("fault", "PASS", "FAIL", (("CL01", "system", A),)),
    "f-system-altered": ("fault", "PASS", "FAIL", (("CL02", "system", A),)),
    "f-system-demoted-needlessly": ("fault", "PASS", "FAIL", (("CL03", "system", A),)),
    "f-system-dropped-no-system-target": ("fault", "PASS", "FAIL", (("CL01", "system", A),)),
    "f-role-swap": ("fault", "PASS", "FAIL", (("CL04", "messages[3].role", A),)),
    "f-text-altered": ("fault", "PASS", "FAIL", (("CL05", "messages[4].text", A),)),
    "f-cross-role-merge": ("fault", "PASS", "FAIL", (("CL09", "messages[3]", A),)),
    "f-same-role-merge-needless": ("fault", "PASS", "FAIL", (("CL08", "messages[0]", A),)),
    "f-reordered": ("fault", "PASS", "FAIL", (("CL06", "messages", A),)),
    "f-message-dropped": ("fault", "PASS", "FAIL", (("CL07", "messages[7]", A),)),
    "f-message-injected": ("fault", "PASS", "FAIL", (("CL10", "messages", A),)),
    "f-error-flag-dropped": ("fault", "PASS", "FAIL", (("CL15", "messages[6].is_error", A),)),
    "f-error-flag-injected": ("fault", "PASS", "FAIL", (("CL16", "messages[2].is_error", A),)),
    "f-tool-call-renamed": ("fault", "PASS", "FAIL", (("CL11", "messages[5].name", A),)),
    "f-tool-args-altered": ("fault", "PASS", "FAIL", (("CL12", "messages[1].args", A),)),
    "f-result-relinked": ("fault", "PASS", "FAIL", (("CL13", "messages[6].call", A),)),
    "f-result-altered": ("fault", "PASS", "FAIL", (("CL14", "messages[2].content", A),)),
    "f-tool-def-dropped": ("fault", "PASS", "FAIL", (("CL17", "tools.cancel_hold", A),)),
    "f-tool-def-injected": ("fault", "PASS", "FAIL", (("CL18", "tools.delete_booking", A),)),
    "f-thinking-injected": ("fault", "PASS", "FAIL", (("CL20", "controls.thinking_budget", A),)),
    "f-control-dropped": ("fault", "PASS", "FAIL", (("CL19", "controls.temperature_milli", A),)),
    "f-control-altered": ("fault", "PASS", "FAIL", (("CL21", "controls.max_tokens", A),)),
    "f-clamp-plus-injection": ("fault", "PASS", "FAIL",
                               (("CL20", "controls.temperature_milli", A),
                                ("CL21", "controls.max_tokens", F))),
    "fo-max-tokens-clamped": ("forced", "PASS", "PASS", (("CL21", "controls.max_tokens", F),)),
    "fo-thinking-unsupported": ("forced", "PASS", "PASS",
                                (("CL19", "controls.thinking_budget", F),)),
    "fo-system-demoted": ("forced", "PASS", "PASS", (("CL03", "system", F),)),
    "fo-same-role-merge": ("forced", "PASS", "PASS", (("CL08", "messages[0]", F),)),
    "s-over-cap": ("schema", "FAIL", "FAIL", ()),
}


def cases():
    """A fresh deep copy of the fixture cases."""
    return copy.deepcopy(CASES)


def labels():
    return copy.deepcopy(LABELS)


def run_all():
    """Score every case with the module and the oracle."""
    rows = {}
    for name, case in cases().items():
        ref = O.reference(copy.deepcopy(case["source"]), copy.deepcopy(case["target"]),
                          copy.deepcopy(case["profile"]))
        rows[name] = (M.evaluate(case), ref)
    return rows


def summary():
    rows = run_all()
    planted = [n for n, lab in LABELS.items() if lab[0] == "fault"]
    controls = [n for n, lab in LABELS.items() if lab[0] == "control"]
    forced = [n for n, lab in LABELS.items() if lab[0] == "forced"]

    def count(names, arm, verdict):
        return sum(1 for n in names if rows[n][0][arm]["verdict"] == verdict)

    named = sum(1 for n in planted
                if [f for f in LABELS[n][3] if f[2] == "avoidable"]
                and all(f in rows[n][0]["rule_arm"]["findings"] for f in LABELS[n][3]))
    forced_findings = [f for m, _ in rows.values() if m["status"] == "ok"
                       for f in m["rule_arm"]["findings"] if f[2] == "forced"]
    oracle_ok = sum(1 for m, o in rows.values()
                    if (m["baseline"]["verdict"] == "PASS", m["rule_arm"]["findings"],
                        m["rule_arm"]["verdict"]) == o)
    lines = ["%-36s %-8s %-8s %-5s %s" % ("case", "category", "baseline", "rule", "findings")]
    for name, (m, _) in rows.items():
        fs = " ".join("%s:%s:%s" % f for f in m["rule_arm"]["findings"]) or "-"
        if m["baseline"]["schema_error"] is not None:
            fs = "schema %s at %s" % m["baseline"]["schema_error"]
        lines.append("%-36s %-8s %-8s %-5s %s" % (name, LABELS[name][0],
                                                  m["baseline"]["verdict"],
                                                  m["rule_arm"]["verdict"], fs))
    lines += [
        "cases: %d (controls %d, planted faults %d, forced %d, schema %d)"
        % (len(rows), len(controls), len(planted), len(forced),
           sum(1 for lab in LABELS.values() if lab[0] == "schema")),
        "planted faults flagged: baseline %d/%d, rule arm %d/%d"
        % (count(planted, "baseline", "FAIL"), len(planted),
           count(planted, "rule_arm", "FAIL"), len(planted)),
        "planted faults named with rule id and path: %d/%d" % (named, len(planted)),
        "planted faults passing the static target check: %d/%d"
        % (count(planted, "baseline", "PASS"), len(planted)),
        "permitted-change controls alarmed: baseline %d/%d, rule arm %d/%d"
        % (count(controls, "baseline", "FAIL"), len(controls),
           count(controls, "rule_arm", "FAIL"), len(controls)),
        "forced cases passed: baseline %d/%d, rule arm %d/%d"
        % (count(forced, "baseline", "PASS"), len(forced),
           count(forced, "rule_arm", "PASS"), len(forced)),
        "forced findings reported as forced: %d" % len(forced_findings),
        "module vs oracle: %d/%d cases agree" % (oracle_ok, len(rows)),
    ]
    return "\n".join(line.rstrip() for line in lines)


if __name__ == "__main__":
    print(summary())
