"""Independent reference for alert_silence.evaluate on well-formed cases.

A second code path: it imports only hashlib and json, shares no function
name with alert_silence.py or executor.py, and does not validate input
beyond the one spec rule on the exploit (a case whose exploit is not the
declared attack is config_error). Its analyzer first inlines every helper
call into one flat list of steps with renamed variables, then propagates a
set of tainted labels ("v" for a string or list, "v.path" / "v.query" for a
parsed URL) in one pass. To reproduce a result record it runs the same flat
list concretely with its own interpreter (written from the executor's
declared semantics, not from its code). Its gate is an ordered table of
named conditions; the first that holds decides.
"""

import hashlib
import json


def _sha(prog):
    canon = json.dumps(prog, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canon.encode("ascii")).hexdigest()


def _inline(steps, helpers, scope, names, flat, tag):
    for pos, st in enumerate(steps):
        if st["op"] == "call":
            h = helpers[st["fn"]]
            inner = {h["param"]: names[st["arg"]]}
            _inline(h["body"], helpers, "%s%s.%d/" % (scope, st["fn"], pos), inner, flat,
                    "helper " + st["fn"])
            names[st["dst"]] = inner[h["ret"]]
            continue
        new = {"op": st["op"], "loc": "%s[%d]" % (tag, pos)}
        for key in ("src", "args", "value", "name", "at"):
            if key in st:
                val = st[key]
                if key == "src":
                    val = names[val]
                elif key == "args":
                    val = [names[a] for a in val]
                new[key] = val
        if "dst" in st:
            names[st["dst"]] = scope + st["dst"]
            new["dst"] = names[st["dst"]]
        flat.append(new)


def _labels(prog, open_gap):
    flat = []
    _inline(prog["body"], prog["helpers"], "", {}, flat, "body")
    hot = set()
    hits = []
    for st in flat:
        kind = st["op"]
        dst = st.get("dst")
        if kind == "source":
            hot.add(dst)
        elif kind in ("concat", "pack"):
            if [a for a in st["args"] if a in hot]:
                hot.add(dst)
        elif kind in ("assign", "index"):
            if st["src"] in hot:
                hot.add(dst)
            for part in ("path", "query"):
                if st["src"] + "." + part in hot:
                    hot.add(dst + "." + part)
        elif kind == "parse_url":
            if st["src"] in hot:
                hot.add(dst + ".query")
                if not open_gap:
                    hot.add(dst + ".path")
        elif kind == "field":
            if st["src"] + "." + st["name"] in hot:
                hot.add(dst)
        elif kind == "sink":
            if st["src"] in hot and st["loc"] not in hits:
                hits.append(st["loc"])
    return tuple(sorted(hits))


# The spec's declared attack, written out here on its own.
ATTACK = "1' OR '1'=" + "'1"

OUT_KEYS = ("status", "detail", "case_id", "family", "alerts_before", "alerts_after",
            "alert_before", "alert_after", "before_digest", "after_digest",
            "exploit_before", "exploit_after", "receipt", "reason", "run", "measurement",
            "baseline")


def _concrete(prog, attack):
    """True when the attack text occurs in some string a sink receives."""
    flat = []
    _inline(prog["body"], prog["helpers"], "", {}, flat, "body")
    val = {}
    sunk = []
    for st in flat:
        kind = st["op"]
        if kind == "source":
            v = attack
        elif kind == "const":
            v = st["value"]
        elif kind in ("assign", "index"):
            v = val[st["src"]] if kind == "assign" else val[st["src"]][st["at"]]
        elif kind == "concat":
            v = "".join(val[a] for a in st["args"])
        elif kind == "sanitize":
            v = "&#39;".join(val[st["src"]].split("'"))
        elif kind == "parse_url":
            head, mark, tail = val[st["src"]].partition("?")
            v = {"path": head, "query": tail}
        elif kind == "field":
            v = val[st["src"]][st["name"]]
        elif kind == "pack":
            v = [val[a] for a in st["args"]]
        else:
            sunk.append(val[st["src"]])
            continue
        val[st["dst"]] = v
    return len([s for s in sunk if attack in s]) > 0


def _bound(case, which):
    rec = case["runs"].get(which)
    if rec is None:
        return "missing", None
    if rec["ran_on"] != _sha(case[which]) or rec["exploit"] != case["exploit"]:
        return "unbound", None
    if rec["reached"] is not _concrete(case[which], case["exploit"]):
        return "unreproduced", None
    return "bound", rec["reached"]


def reference(case):
    if case["exploit"] != ATTACK:
        out = dict((k, None) for k in OUT_KEYS)
        out.update(status="config_error", detail="exploit_undeclared", receipt="refuse",
                   reason="config_error", run="", measurement="on_unmeasured")
        return out
    before = _labels(case["before"], True)
    after = _labels(case["after"], True)
    state = dict((w, _bound(case, w)) for w in ("before", "after"))
    table = [
        (state["before"][0] == "missing", ("refuse", "executor_missing", "before")),
        (state["after"][0] == "missing", ("refuse", "executor_missing", "after")),
        (state["before"][0] == "unbound", ("refuse", "executor_unbound", "before")),
        (state["after"][0] == "unbound", ("refuse", "executor_unbound", "after")),
        (state["before"][0] == "unreproduced", ("refuse", "executor_unreproduced", "before")),
        (state["after"][0] == "unreproduced", ("refuse", "executor_unreproduced", "after")),
        (state["before"][1] is False, ("refuse", "no_vulnerability_before", "")),
        (state["after"][1] is True and len(after) > 0, ("refuse", "vuln_present", "")),
        (state["after"][1] is True, ("refuse", "alert_silenced_vuln_present", "")),
        (True, ("fixed", "exploit_gone", "")),
    ]
    receipt, reason, run = [out for cond, out in table if cond][0]
    return {"status": "ok", "detail": "", "case_id": case["case_id"],
            "family": case["family"], "alerts_before": before, "alerts_after": after,
            "alert_before": len(before) > 0, "alert_after": len(after) > 0,
            "before_digest": _sha(case["before"]), "after_digest": _sha(case["after"]),
            "exploit_before": state["before"][1], "exploit_after": state["after"][1],
            "receipt": receipt, "reason": reason, "run": run,
            "measurement": ("on_unmeasured" if reason.startswith("executor_")
                            else "measured"),
            "baseline": "fixed" if before and not after else "not_fixed"}


def labels_open(prog):
    """The oracle's analyzer with the declared gap closed (tests only)."""
    return _labels(prog, False)
