"""Independent reference for w23-world-consistent-history (imports nothing).

A second, separately written code path for the rule arm's decision and
reasons, the receiver stub's writes and the recovery score. It shares no
function with the module and does not validate input: it is only called on
inputs the module accepts.

Claim lookup scans each history backwards for the first done/failed record
of a target; a done claim with a blank value (no non-space character) never
matches the world; the receiver is a small decision table; scoring compares the
final world with gold position by position.
"""


def _claim(history, target):
    for rec in reversed(history):
        if rec["target"] == target and rec["claim"] in ("done", "failed"):
            return rec["claim"], rec["value"]
    return None


def _note(history, target):
    for rec in reversed(history):
        if rec["target"] == target and rec["claim"] == "note":
            return rec["value"]
    return None


def reference_rule(case):
    reasons = []
    for t in case["targets"]:
        now = _claim(case["edited"], t)
        was = _claim(case["history"], t)
        if now is None and was is not None:
            reasons.append((t, "claim_erased"))
        if now is not None and now[0] == "done" and (not now[1].split()
                                                      or now[1] != case["world"][t]):
            reasons.append((t, "false_done"))
    return ("REFUSE" if reasons else "ADMIT"), tuple(reasons)


def reference_writes(history, guess, targets):
    out = []
    for t in targets:
        c = _claim(history, t)
        n = _note(history, t)
        if n is not None:
            w = None if c == ("done", n) else n
        elif c is None:
            w = guess[t]
        elif c[0] == "failed":
            w = c[1]
        elif c[1] == guess[t]:
            w = None
        else:
            w = guess[t]
        out.append((t, w))
    return tuple(out)


def reference_score(case, history):
    writes = reference_writes(history, case["guess"], case["targets"])
    rem, rec, dmg, ok = [], [], [], True
    for t, w in writes:
        end = case["world"][t] if w is None else w
        start_ok = case["world"][t] == case["gold"][t]
        end_ok = end == case["gold"][t]
        if not start_ok:
            rem.append(t)
            if end_ok:
                rec.append(t)
        elif not end_ok:
            dmg.append(t)
        ok = ok and end_ok
    return {"writes": writes, "remaining": tuple(rem), "recovered": tuple(rec),
            "damaged": tuple(dmg), "task_success": ok}


def reference(case):
    decision, reasons = reference_rule(case)
    return {
        "rule": decision,
        "reasons": reasons,
        "unedited": reference_score(case, case["history"]),
        "baseline": reference_score(case, case["edited"]),
        "rule_view": reference_score(case, case["edited"] if decision == "ADMIT"
                                     else case["history"]),
    }
