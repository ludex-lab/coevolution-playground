"""Mutant runner: each mutant patches the code, the fixture world or the test
harness, then the unittest suite runs. A mutant is killed when at least one
test fails.

Code mutants replace one exact snippet of conv_loss.py or oracle.py (each
snippet must occur exactly once) and re-execute the patched source in
memory inside that module. World mutants change the fixtures in memory.
Harness mutants replace one helper of the test module in memory (the
row-scoped hygiene scan, the exhaustive space, the oracle call). Nothing is
written to disk.

Run: python3 -B mutants.py
Exit code 0 only when every mutant is killed and the clean suite passes.
"""

import copy
import io
import os
import sys
import unittest

import conv_loss
import fixtures
import oracle
import test_conv_loss

MODULES = {"conv_loss": conv_loss, "oracle": oracle}
SNAPSHOTS = {k: dict(vars(m)) for k, m in MODULES.items()}
FIX_SNAPSHOT = dict(vars(fixtures))
TEST_SNAPSHOT = dict(vars(test_conv_loss))
WORLD = ("CASES", "LABELS", "PROFILES", "SOURCE0", "TARGET0", "BIG1")
WORLD_ORIG = {k: copy.deepcopy(getattr(fixtures, k)) for k in WORLD}
HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = {}
for _k in MODULES:
    with open(os.path.join(HERE, _k + ".py"), "r", encoding="utf-8") as _fh:
        SOURCES[_k] = _fh.read()


def code(module, *pairs):
    """Return an apply() that swaps each (old, new) snippet once in module."""
    def apply():
        text = SOURCES[module]
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError("snippet not found exactly once: %r" % (old,))
            text = text.replace(old, new)
        path = os.path.join(HERE, module + ".py")
        exec(compile(text, path, "exec"), MODULES[module].__dict__)
    return apply


def mod(*pairs):
    return code("conv_loss", *pairs)


def orc(*pairs):
    return code("oracle", *pairs)


CODE_MUTANTS = [
    # System text.
    ("CL01 system drop never reported", mod(
        ("            out.append((\"CL01\", \"system\", AVOIDABLE))\n", "            pass\n"))),
    ("CL02 system change never reported", mod(
        ("            out.append((\"CL02\", \"system\", AVOIDABLE))\n", "            pass\n"))),
    ("demotion always forced", mod(
        ("AVOIDABLE if profile[\"has_system\"] else FORCED", "FORCED"))),
    ("demotion always avoidable", mod(
        ("AVOIDABLE if profile[\"has_system\"] else FORCED", "AVOIDABLE"))),
    ("demotion never recognised", mod(
        ("        if src[\"system\"] and not dst[\"system\"] and D and D[0] == demoted:\n",
         "        if False:\n"))),
    ("demoted turn left in the message sequence", mod(
        ("            D = D[1:]\n", "            pass\n"))),
    # Messages.
    ("CL04 role change ignored", mod(
        ("        if a[1] != b[1]:\n            out.append((\"CL04\"",
         "        if False:\n            out.append((\"CL04\""))),
    ("CL05 text change ignored", mod(
        ("        if a[2] != b[2]:\n            out.append((\"CL05\"",
         "        if False:\n            out.append((\"CL05\""))),
    ("CL06 reorder not detected", mod(
        ("        if sorted(S) == sorted(D):\n", "        if False:\n"))),
    ("same-role merge always forced", mod(
        ("status = FORCED if profile[\"alternating\"] else AVOIDABLE", "status = FORCED"))),
    ("same-role merge always avoidable", mod(
        ("status = FORCED if profile[\"alternating\"] else AVOIDABLE", "status = AVOIDABLE"))),
    ("merge separator changed", mod(
        ("D[i][2] != a[2] + JOIN + b[2]", "D[i][2] != a[2] + \" \" + b[2]"))),
    ("CL09 cross-role merge ignored", mod(
        ("            if a[1] != b[1] and D[i][1] in (a[1], b[1]):\n",
         "            if False:\n"))),
    ("CL07 drop not detected", mod(
        ("            if S[:i] + S[i + 1:] == D:\n", "            if False:\n"))),
    ("CL10 mismatch returns nothing", mod(
        ("    return [(\"CL10\", \"messages\", AVOIDABLE)]\n", "    return []\n"))),
    ("kind change not a mismatch", mod(
        ("    if a[0] != b[0]:\n        return [(\"CL10\", at, AVOIDABLE)]\n",
         "    if a[0] != b[0]:\n        return []\n"))),
    ("CL11 tool call rename ignored", mod(
        ("        if a[1] != b[1]:\n            out.append((\"CL11\"",
         "        if False:\n            out.append((\"CL11\""))),
    ("CL12 argument change ignored", mod(
        ("        if a[2] != b[2]:\n            out.append((\"CL12\"",
         "        if False:\n            out.append((\"CL12\""))),
    ("CL13 relinked result ignored", mod(
        ("        if a[1] != b[1]:\n            out.append((\"CL13\"",
         "        if False:\n            out.append((\"CL13\""))),
    ("CL14 result change ignored", mod(
        ("        if a[2] != b[2]:\n            out.append((\"CL14\"",
         "        if False:\n            out.append((\"CL14\""))),
    ("CL15 dropped error flag ignored", mod(
        ("        if a[3] and not b[3]:\n", "        if False:\n"))),
    ("CL16 injected error flag ignored", mod(
        ("        if b[3] and not a[3]:\n", "        if False:\n"))),
    # Tools and controls.
    ("CL17 dropped tool definition ignored", mod(
        ("            out.append((\"CL17\", \"tools.\" + name, AVOIDABLE))\n", "            pass\n"))),
    ("CL18 injected tool definition ignored", mod(
        ("            out.append((\"CL18\", \"tools.\" + name, AVOIDABLE))\n", "            pass\n"))),
    ("dropped control always avoidable", mod(
        ("status = AVOIDABLE if name in profile[\"controls\"] else FORCED",
         "status = AVOIDABLE"))),
    ("dropped control always forced", mod(
        ("status = AVOIDABLE if name in profile[\"controls\"] else FORCED", "status = FORCED"))),
    ("CL20 injected control ignored", mod(
        ("            out.append((\"CL20\", at, AVOIDABLE))\n", "            pass\n"))),
    ("altered control always forced", mod(
        ("FORCED if clamped else AVOIDABLE", "FORCED"))),
    ("clamp test skips the cap value", mod(
        (" and dc[name] == cap", ""))),
    ("clamp test skips source above cap", mod(
        (" and sc[name] > cap", ""))),
    ("findings left unsorted", mod(
        ("    return tuple(sorted(out))\n\n\ndef encode_b",
         "    return tuple(out)\n\n\ndef encode_b"))),
    # Arms.
    ("rule arm ignores avoidable findings", mod(
        ("\"verdict\": PASS if err is None and not avoidable else FAIL",
         "\"verdict\": PASS if err is None else FAIL"))),
    ("rule arm ignores the static check", mod(
        ("\"verdict\": PASS if err is None and not avoidable else FAIL",
         "\"verdict\": PASS if not avoidable else FAIL"))),
    ("forced findings counted as faults", mod(
        ("    avoidable = tuple(f for f in findings if f[2] == AVOIDABLE)\n",
         "    avoidable = findings\n"))),
    ("rules run after a failed static check", mod(
        ("    if err is None:\n        findings = rules(",
         "    if True:\n        findings = rules("))),
    # Intermediate record.
    ("omitted failed flag read as true", mod(
        ("failed = turn[\"failed\"] if \"failed\" in turn else False",
         "failed = turn[\"failed\"] if \"failed\" in turn else True"))),
    ("preamble ignored", mod(
        ("\"system\": t[\"preamble\"] if \"preamble\" in t else \"\"", "\"system\": \"\""))),
    ("list result joined with a comma", mod(
        ("text = JOIN.join(parts)", "text = \", \".join(parts)"))),
    ("source error flag dropped", mod(
        ("messages.append((\"result\", ids.index(cid), text, err))",
         "messages.append((\"result\", ids.index(cid), text, False))"))),
    ("raw call ids compared", mod(
        ("messages.append((\"result\", refs.index(turn[\"ref\"]), turn[\"output\"], failed))",
         "messages.append((\"result\", turn[\"ref\"], turn[\"output\"], failed))"))),
    ("tool definitions read in order", mod(
        ("\"tools\": tuple(sorted(f[\"name\"] for f in t[\"functions\"])),",
         "\"tools\": tuple(f[\"name\"] for f in t[\"functions\"]),"))),
    # Static target check.
    ("schema skips alternation", mod(
        ("            if profile[\"alternating\"] and prev_text == sp:\n",
         "            if False:\n"))),
    ("schema skips the cap", mod(
        ("        if k == \"max_output\" and v > profile[\"max_tokens_cap\"]:\n",
         "        if False:\n"))),
    ("schema accepts unsupported settings", mod(
        ("        if SETTING[k] not in profile[\"controls\"]:\n", "        if False:\n"))),
    ("schema accepts a preamble without a system field", mod(
        ("        if not profile[\"has_system\"]:\n            return (\"preamble_unsupported\"",
         "        if False:\n            return (\"preamble_unsupported\""))),
    ("schema accepts undeclared invoke functions", mod(
        ("            if type(inv[\"fn\"]) is not str or inv[\"fn\"] not in names:\n",
         "            if type(inv[\"fn\"]) is not str:\n"))),
    ("schema accepts a non-bool failed flag", mod(
        ("            if \"failed\" in turn and type(turn[\"failed\"]) is not bool:\n",
         "            if False:\n"))),
    # Input hardening.
    ("key check removed (case)", mod(
        ("    _keys(case, \"case_key_invalid\")\n", ""))),
    ("key check removed (message)", mod(
        ("        _keys(m, \"source_message_key_invalid\")\n", ""))),
    ("key check removed (target)", mod(
        ("        _keys(v, \"target_key_invalid\")\n", ""))),
    ("snapshot reuses the caller's target", mod(
        ("    target = _tree(case[\"target\"], 0)\n",
         "    _tree(case[\"target\"], 0)\n    target = case[\"target\"]\n"))),
    ("snapshot reuses the caller's dicts", mod(
        ("        return dict((k, _tree(x, depth + 1)) for k, x in list(v.items()))\n",
         "        [_tree(x, depth + 1) for x in list(v.values())]\n        return v\n"))),
    ("subclasses accepted in the target", mod(
        ("    if t is str or t is int or t is bool:\n",
         "    if isinstance(v, (str, int, bool)):\n"))),
    ("bool accepted as an int control", mod(
        ("        if k not in CONTROLS or type(v) is not int or v < 0:\n",
         "        if k not in CONTROLS or not isinstance(v, int) or v < 0:\n"))),
    ("depth limit removed", mod(
        ("    if depth > MAX_DEPTH:\n", "    if False:\n"))),
    ("profile combination accepted", mod(
        ("    if not has_system and alternating:\n", "    if False:\n"))),
    ("undeclared source tool call accepted", mod(
        ("            if type(name) is not str or name not in tools:\n",
         "            if type(name) is not str:\n"))),
    ("evaluate raises on an internal error", mod(
        ("    try:\n        return _run(snap)\n    except Exception:\n"
         "        return _config(\"internal_error\")\n",
         "    return _run(snap)\n"))),
    # Declared encoding.
    ("encoding never merges", mod(
        ("if profile[\"alternating\"] and last is not None", "if False and last is not None"))),
    ("encoding never clamps", mod(
        ("            v = profile[\"max_tokens_cap\"]\n", "            pass\n"))),
    ("encoding retains unsupported controls", mod(
        ("        if name not in profile[\"controls\"]:\n            continue\n", ""))),
    ("encoding omits the failed flag", mod(
        ("\"output\": item[2],\n                          \"failed\": item[3]})",
         "\"output\": item[2]})"))),
    ("describe drops the path", mod(
        ("    return \"%s %s at %s (%s)\" % (rule, RULES[rule], path, status)\n",
         "    return \"%s %s (%s)\" % (rule, RULES[rule], status)\n"))),
    # Oracle.
    ("oracle: reorder not detected", orc(
        ("        if all(S.count(x) == D.count(x) for x in S):\n", "        if False:\n"))),
    ("oracle: merge reads only the first role", orc(
        ("            for who in (a[\"who\"], b[\"who\"]):\n",
         "            for who in (a[\"who\"],):\n"))),
    ("oracle: error flag direction swapped", orc(
        ("\"CL15\" if a[\"err\"] else \"CL16\"", "\"CL16\" if a[\"err\"] else \"CL15\""))),
    ("oracle: schema skips alternation", orc(
        ("            if profile[\"alternating\"] and last == speaker:\n",
         "            if False:\n"))),
    ("oracle: schema skips the cap", orc(
        ("        if k == \"max_output\" and v > profile[\"max_tokens_cap\"]:\n",
         "        if False:\n"))),
    ("oracle: omitted failed flag read as true", orc(
        ("\"err\": t.get(\"failed\", False)", "\"err\": t.get(\"failed\", True)"))),
    ("oracle: demotion always forced", orc(
        ("\"avoidable\" if profile[\"has_system\"] else \"forced\"", "\"forced\""))),
    ("oracle: injected tool definitions ignored", orc(
        ("    found += [(\"CL18\", \"tools.\" + n, \"avoidable\") for n in dst_tools - src_tools]\n",
         ""))),
    ("oracle: clamp skips source above cap", orc(
        (" and sc[name] > cap", ""))),
]


def _w():
    return {k: copy.deepcopy(v) for k, v in WORLD_ORIG.items()}


def _set(**kw):
    for k, v in kw.items():
        setattr(fixtures, k, v)


def w_planted_fault_made_faithful():
    w = _w()
    w["CASES"]["f-error-flag-dropped"]["target"]["turns"][6]["failed"] = True
    _set(CASES=w["CASES"])


def w_planted_label_removed():
    w = _w()
    w["LABELS"]["f-system-dropped"] = ("fault", "PASS", "FAIL", ())
    _set(LABELS=w["LABELS"])


def w_planted_fault_relabelled_control():
    w = _w()
    lab = w["LABELS"]["f-reordered"]
    w["LABELS"]["f-reordered"] = ("control",) + lab[1:]
    _set(LABELS=w["LABELS"])


def w_false_alarm_hidden():
    w = _w()
    w["LABELS"]["ctl-trailing-newline-stripped"] = ("control", "PASS", "PASS", ())
    w["CASES"]["ctl-trailing-newline-stripped"]["source"]["system"] = fixtures.SYS0
    _set(LABELS=w["LABELS"], CASES=w["CASES"])


def w_forced_demotion_on_full_profile():
    w = _w()
    w["CASES"]["fo-system-demoted"]["profile"] = copy.deepcopy(w["PROFILES"]["full"])
    _set(CASES=w["CASES"])


def w_forced_merge_on_full_profile():
    w = _w()
    w["CASES"]["fo-same-role-merge"]["profile"] = copy.deepcopy(w["PROFILES"]["full"])
    _set(CASES=w["CASES"])


def w_renamed_call_undeclared():
    w = _w()
    w["CASES"]["f-tool-call-renamed"]["target"]["turns"][5]["invoke"]["fn"] = "book_seat"
    _set(CASES=w["CASES"])


def w_over_cap_fixed():
    w = _w()
    w["CASES"]["s-over-cap"]["target"]["settings"]["max_output"] = 4096
    _set(CASES=w["CASES"])


def w_cap_raised():
    w = _w()
    for c in w["CASES"].values():
        c["profile"]["max_tokens_cap"] = 9000
    w["PROFILES"]["full"]["max_tokens_cap"] = 9000
    _set(CASES=w["CASES"], PROFILES=w["PROFILES"])


def w_source_error_flag_cleared():
    w = _w()
    w["SOURCE0"]["messages"][6]["is_error"] = False
    _set(SOURCE0=w["SOURCE0"])


def w_hand_target_reordered():
    w = _w()
    w["TARGET0"]["turns"][3], w["TARGET0"]["turns"][4] = (w["TARGET0"]["turns"][4],
                                                          w["TARGET0"]["turns"][3])
    _set(TARGET0=w["TARGET0"])


def w_control_case_removed():
    w = _w()
    del w["CASES"]["ctl-ids-reminted"]
    del w["LABELS"]["ctl-ids-reminted"]
    _set(CASES=w["CASES"], LABELS=w["LABELS"])


def w_cases_shared():
    fixtures.cases = lambda: fixtures.CASES


def w_labels_shared():
    fixtures.labels = lambda: fixtures.LABELS


WORLD_MUTANTS = [
    ("planted fault made faithful", w_planted_fault_made_faithful),
    ("planted label emptied", w_planted_label_removed),
    ("planted fault relabelled as a control", w_planted_fault_relabelled_control),
    ("false-alarm control replaced by a clean one", w_false_alarm_hidden),
    ("forced demotion run on the full profile", w_forced_demotion_on_full_profile),
    ("forced merge run on the full profile", w_forced_merge_on_full_profile),
    ("renamed call points at an undeclared tool", w_renamed_call_undeclared),
    ("over-cap payload brought under the cap", w_over_cap_fixed),
    ("target cap raised", w_cap_raised),
    ("hand source error flag cleared", w_source_error_flag_cleared),
    ("hand target messages reordered", w_hand_target_reordered),
    ("control case removed", w_control_case_removed),
    ("cases() returns shared state", w_cases_shared),
    ("labels() returns shared state", w_labels_shared),
]


def h_scan_whole_day_readme():
    test_conv_loss.scan_text = lambda name, text: text


def h_own_rows_every_line():
    test_conv_loss.own_rows = lambda text: text.splitlines()


def h_own_rows_nothing():
    test_conv_loss.own_rows = lambda text: []


def h_hygiene_ignores_banned_words():
    real = test_conv_loss.hygiene_hits
    test_conv_loss.hygiene_hits = lambda text: real(text) - {"banned_word"}


def h_exhaustive_space_shortened():
    test_conv_loss.E_MAX_LEN = 1


def h_oracle_replaced_by_module():
    test_conv_loss.oracle_of = lambda c: test_conv_loss.as_oracle(conv_loss.evaluate(c))


HARNESS_MUTANTS = [
    ("hygiene scans read the whole day README", h_scan_whole_day_readme),
    ("own-row filter returns every line", h_own_rows_every_line),
    ("own-row filter returns nothing", h_own_rows_nothing),
    ("hygiene helper ignores banned words", h_hygiene_ignores_banned_words),
    ("exhaustive space shortened", h_exhaustive_space_shortened),
    ("oracle call replaced by the module", h_oracle_replaced_by_module),
]

MUTANTS = ([("code", n, a) for n, a in CODE_MUTANTS]
           + [("world", n, a) for n, a in WORLD_MUTANTS]
           + [("harness", n, a) for n, a in HARNESS_MUTANTS])


def restore():
    for k, m in MODULES.items():
        for name in [n for n in vars(m) if n not in SNAPSHOTS[k]]:
            delattr(m, name)
        m.__dict__.update(SNAPSHOTS[k])
    fixtures.__dict__.update(FIX_SNAPSHOT)
    _set(**_w())
    test_conv_loss.__dict__.update(TEST_SNAPSHOT)


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_conv_loss)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


def main():
    restore()
    ran, bad = run_suite()
    print("clean suite: %d tests, %d failing" % (ran, bad))
    clean_ok = bad == 0
    killed = {"code": 0, "world": 0, "harness": 0}
    for kind, name, apply in MUTANTS:
        try:
            apply()
            ran, bad = run_suite()
        except Exception as exc:
            restore()
            print("%-7s %-56s BROKEN   (%s)" % (kind, name, type(exc).__name__))
            continue
        finally:
            restore()
        status = "KILLED" if bad else "SURVIVED"
        killed[kind] += 1 if bad else 0
        print("%-7s %-56s %-8s (%d/%d tests failing)" % (kind, name, status, bad, ran))
    ran, bad = run_suite()
    print("clean suite after restore: %d tests, %d failing" % (ran, bad))
    clean_ok = clean_ok and bad == 0
    n_code, n_world, n_harness = len(CODE_MUTANTS), len(WORLD_MUTANTS), len(HARNESS_MUTANTS)
    total = killed["code"] + killed["world"] + killed["harness"]
    print("killed %d/%d (code %d/%d, world %d/%d, harness %d/%d)"
          % (total, n_code + n_world + n_harness, killed["code"], n_code,
             killed["world"], n_world, killed["harness"], n_harness))
    ok = clean_ok and total == n_code + n_world + n_harness
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
