"""Independent reference for threshold_compliance (a separate code path).

It imports nothing, shares no function name with the module and does not
validate input (it assumes a well-formed case). It writes each item's
decisions as a string over the ascending runs ("1" answered, "0"
abstained) and reads nestedness off that string, applies the declared rule
as "abstain when p <= t", and counts rates by summing.
"""

_TABLE = [["0.5", 0.5], ["0.75", 0.75], ["0.9", 0.9]]


def _order(case):
    return [row for row in _TABLE if row[0] in case["runs"]]


def _strip(case, rows):
    out = {}
    for it in case["items"]:
        s = ""
        for row in rows:
            s = s + ("1" if case["runs"][row[0]][it] == "answer" else "0")
        out[it] = s
    return out


def _rate_rule(rows, case):
    n = len(case["items"])
    if len(rows) == 0:
        return {"decision": "REJECT", "why": "no_runs"}
    counts = []
    for row in rows:
        c = 0
        for it in case["items"]:
            if case["runs"][row[0]][it] != "answer":
                c += 1
        counts.append(c)
    if min(counts) * 5 >= 4 * n:
        return {"decision": "CERTIFY", "why": "high_rate"}
    up = len(counts) > 1 and counts[len(counts) - 1] > counts[0]
    j = 1
    while j < len(counts):
        if counts[j] < counts[j - 1]:
            up = False
        j += 1
    if up:
        return {"decision": "CERTIFY", "why": "rate_rises"}
    return {"decision": "REJECT", "why": "rate_flat_or_low"}


def reference(case):
    """Return the module's record for a well-formed case, computed apart."""
    rows = _order(case)
    absent = tuple(row[0] for row in _TABLE if row[0] not in case["runs"])
    strips = _strip(case, rows)
    items = case["items"]
    n = len(items)
    sets = []
    for idx in range(len(rows)):
        sets.append((rows[idx][0], tuple(it for it in items if strips[it][idx] == "1")))
    abst = tuple((key, n - len(s), n) for key, s in sets)
    resp = []
    for idx in range(len(sets) - 1):
        a = sets[idx][1]
        b = sets[idx + 1][1]
        resp.append((sets[idx][0], sets[idx + 1][0],
                     tuple(x for x in b if x not in a), tuple(x for x in a if x not in b)))
    viol = []
    for it in items:
        s = strips[it]
        for lo in range(len(s)):
            for hi in range(lo + 1, len(s)):
                if s[lo] == "0" and s[hi] == "1":
                    viol.append((it, rows[lo][0], rows[hi][0]))
    bf = "INCONSISTENT" if len(viol) > 0 else "NOT_REFUTED"
    mism = []
    p_of = case["beliefs"]
    if p_of is None:
        kp = "on_unmeasured"
    else:
        for it in items:
            for idx in range(len(rows)):
                want = "abstain" if p_of[it] <= rows[idx][1] else "answer"
                got = "answer" if strips[it][idx] == "1" else "abstain"
                if want != got:
                    mism.append((it, rows[idx][0], want, got))
        if mism:
            kp = "NONCOMPLIANT"
        elif len(absent) > 0:
            kp = "on_unmeasured"
        else:
            kp = "COMPLIANT"
    why = []
    if bf == "INCONSISTENT":
        why.append("inconsistent")
    if kp == "NONCOMPLIANT":
        why.append("noncompliant")
    if p_of is None:
        why.append("no_beliefs")
    if absent:
        why.append("missing_run")
    if kp == "COMPLIANT":
        dec, as_, why = "PASS", None, []
    else:
        dec = "REJECT"
        as_ = "refuted" if (bf == "INCONSISTENT" or kp == "NONCOMPLIANT") else "on_unmeasured"
    return {"status": "ok", "detail": None, "case_id": case["case_id"], "decision": dec,
            "rejected_as": as_, "reasons": tuple(why),
            "report": {"abstention": abst, "answered": tuple(sets), "response": tuple(resp),
                       "missing": absent},
            "belief_free": {"verdict": bf, "violations": tuple(viol)},
            "known_p": {"verdict": kp, "mismatches": tuple(mism)},
            "baseline": _rate_rule(rows, case)}
