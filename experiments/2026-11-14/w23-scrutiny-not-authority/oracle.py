"""Independent reference for w23-scrutiny-not-authority (imports nothing).

A second, separately written code path for the independent outcome, the
four arms' decisions and the elimination gate. It shares no function with
the module and does not validate input: it is only called on inputs the
module accepts.

The checks are flattened to (source, basis, verdict) triples. The set of
verdicts carried by independent, run checks selects the outcome from a
table; each arm is then one table lookup keyed by (self_assessment,
outcome).
"""

_OUTCOME = {
    frozenset(): "none",
    frozenset(["refutes"]): "refuted",
    frozenset(["supports"]): "supported",
    frozenset(["refutes", "supports"]): "conflict",
}

_BASELINE = {
    ("ok", "none"): "RETAIN", ("ok", "supported"): "RETAIN",
    ("ok", "refuted"): "ELIMINATE", ("ok", "conflict"): "HOLD",
    ("defective", "none"): "ELIMINATE", ("defective", "supported"): "ELIMINATE",
    ("defective", "refuted"): "ELIMINATE", ("defective", "conflict"): "ELIMINATE",
}

_RULE = {
    ("ok", "none"): "RETAIN", ("ok", "supported"): "RETAIN",
    ("ok", "refuted"): "ELIMINATE", ("ok", "conflict"): "HOLD",
    ("defective", "none"): "HOLD", ("defective", "supported"): "RETAIN",
    ("defective", "refuted"): "ELIMINATE", ("defective", "conflict"): "HOLD",
}

_FLIP = {
    ("ok", "none"): "RETAIN", ("ok", "supported"): "RETAIN",
    ("ok", "refuted"): "ELIMINATE", ("ok", "conflict"): "HOLD",
    ("defective", "none"): "NEGATE", ("defective", "supported"): "NEGATE",
    ("defective", "refuted"): "NEGATE", ("defective", "conflict"): "NEGATE",
}


def _triples(case):
    return [(c["source"], c["basis"], c["verdict"]) for c in case["checks"]]


def _counts(case, only=None):
    found = set()
    for i, (src, basis, verdict) in enumerate(_triples(case)):
        if only is not None and case["checks"][i]["check_id"] not in only:
            continue
        if src == "self" or basis != "own_evidence" or verdict == "not_run":
            continue
        found.add(verdict)
    return found


def reference(case):
    """{outcome, baseline, rule, flagged, agree_flip, agree_silence, basis}."""
    out = _OUTCOME[frozenset(_counts(case))]
    a = case["self_assessment"]
    basis = []
    if _RULE[(a, out)] == "ELIMINATE":
        for c in case["checks"]:
            if c["source"] != "self" and c["basis"] == "own_evidence" \
                    and c["verdict"] == "refutes":
                basis.append(c["check_id"])
    return {"outcome": out, "baseline": _BASELINE[(a, out)], "rule": _RULE[(a, out)],
            "flagged": a == "defective", "agree_flip": _FLIP[(a, out)],
            "agree_silence": _RULE[("ok", out)], "basis": tuple(basis)}


def gate(case, cite):
    """PERMIT or REFUSE for one elimination request."""
    whole = _OUTCOME[frozenset(_counts(case))]
    if whole == "conflict":
        return "REFUSE"
    cited = _counts(case, only=set(cite))
    return "PERMIT" if "refutes" in cited else "REFUSE"
