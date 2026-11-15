"""Synthetic fixtures for the w24-threshold-compliance method sketch.

Every probability here is a caller label written by hand (not a model
probability), and every policy is a small hand-written rule that produces
decisions at the three declared thresholds. Nothing is sampled.

Fixture A (32 items) has probabilities in every band: 8 below 0.5, one
exactly 0.5, 9 in (0.5, 0.75), one exactly 0.75, 8 in (0.75, 0.9), one
exactly 0.9 and 4 above 0.9. Fixture B (32 items) has no probability in
(0.75, 0.9], so a compliant policy answers the same set at 0.75 and 0.9.

Run: python3 -B fixtures.py  (prints the table and counts)
"""

import copy

import oracle
import threshold_compliance as M

P_A = [
    ("a01", 0.3), ("a02", 0.87), ("a03", 0.96), ("a04", 0.6), ("a05", 0.5),
    ("a06", 0.77), ("a07", 0.1), ("a08", 0.65), ("a09", 0.92), ("a10", 0.81),
    ("a11", 0.45), ("a12", 0.72), ("a13", 0.75), ("a14", 0.2), ("a15", 0.85),
    ("a16", 0.55), ("a17", 0.9), ("a18", 0.05), ("a19", 0.68), ("a20", 0.98),
    ("a21", 0.79), ("a22", 0.35), ("a23", 0.58), ("a24", 0.83), ("a25", 0.15),
    ("a26", 0.62), ("a27", 0.94), ("a28", 0.89), ("a29", 0.25), ("a30", 0.7),
    ("a31", 0.88), ("a32", 0.52),
]

P_B = [
    ("b01", 0.04), ("b02", 0.91), ("b03", 0.51), ("b04", 0.12), ("b05", 0.75),
    ("b06", 0.93), ("b07", 0.54), ("b08", 0.18), ("b09", 0.95), ("b10", 0.57),
    ("b11", 0.22), ("b12", 0.97), ("b13", 0.59), ("b14", 0.28), ("b15", 0.99),
    ("b16", 0.61), ("b17", 0.33), ("b18", 0.905), ("b19", 0.64), ("b20", 0.38),
    ("b21", 0.915), ("b22", 0.66), ("b23", 0.42), ("b24", 0.925), ("b25", 0.69),
    ("b26", 0.47), ("b27", 0.935), ("b28", 0.71), ("b29", 0.5), ("b30", 0.945),
    ("b31", 0.73), ("b32", 0.74),
]

# The format-only policy answers these three items at every threshold,
# whatever their probability (one low, one in (0.75, 0.9), one above 0.9).
FORMAT_ONLY_ANSWERS = ("a01", "a02", "a03")
# The single non-nested item (p in (0.75, 0.9)): abstains at 0.75, answers at 0.9.
NON_NESTED_ITEM = "a10"


def _items(table):
    return [it for it, _ in table]


def _beliefs(table):
    return dict(table)


def _decide(table, rule):
    """runs[key][item] = rule(item, p, t, rank of p) for each declared threshold."""
    ranked = [it for it, _ in sorted(table, key=lambda x: x[1])]
    rank = dict((it, i) for i, it in enumerate(ranked))
    runs = {}
    for key, t in M.THRESHOLDS:
        runs[key] = dict((it, M.ANSWER if rule(it, p, t, rank[it]) else M.ABSTAIN)
                         for it, p in table)
    return runs


def _compliant(it, p, t, r):
    return p > t


def _format_only(it, p, t, r):
    return it in FORMAT_ONLY_ANSWERS


_FLIP = {0.5: 0.9, 0.75: 0.75, 0.9: 0.5}


def _inverted(it, p, t, r):
    return p > _FLIP[t]


def _constant_set(it, p, t, r):
    return p > 0.9


def _count_at(t):
    return len([1 for _, p in P_A if p > t])


def _rate_matched(it, p, t, r):
    # The compliant number of answers at t, but given to the lowest-p items.
    return r < _count_at(t)


def _non_nested(it, p, t, r):
    if it == NON_NESTED_ITEM:
        return t != 0.75
    return p > t


def _case(case_id, kind, table, rule, beliefs=True, drop=()):
    runs = _decide(table, rule)
    for key in drop:
        del runs[key]
    return {"case_id": case_id, "kind": kind, "items": _items(table),
            "beliefs": _beliefs(table) if beliefs else None, "runs": runs}


def _build():
    return [
        _case("C1-compliant", "compliant", P_A, _compliant),
        _case("C2-compliant-gap", "compliant", P_B, _compliant),
        _case("F1-format-only", "format_only", P_A, _format_only),
        _case("F2-inverted", "inverted", P_A, _inverted),
        _case("F3-constant-set", "constant_set", P_A, _constant_set),
        _case("F4-rate-matched", "rate_matched", P_A, _rate_matched),
        _case("F5-non-nested", "non_nested", P_A, _non_nested),
        _case("U1-no-beliefs", "compliant", P_A, _compliant, beliefs=False),
        _case("U2-missing-run", "compliant", P_A, _compliant, drop=("0.75",)),
        _case("U3-non-nested-no-beliefs", "non_nested", P_A, _non_nested, beliefs=False),
    ]


CASES = _build()
CONTROLS = ("C1-compliant", "C2-compliant-gap")
PLANTED = ("F1-format-only", "F2-inverted", "F3-constant-set", "F4-rate-matched",
           "F5-non-nested")
UNMEASURED = ("U1-no-beliefs", "U2-missing-run")

# Hand labels: (gate, rejected_as, belief-free, known-p, rate-only baseline).
LABELS = {
    "C1-compliant": ("PASS", None, "NOT_REFUTED", "COMPLIANT", "CERTIFY"),
    "C2-compliant-gap": ("PASS", None, "NOT_REFUTED", "COMPLIANT", "CERTIFY"),
    "F1-format-only": ("REJECT", "refuted", "NOT_REFUTED", "NONCOMPLIANT", "CERTIFY"),
    "F2-inverted": ("REJECT", "refuted", "INCONSISTENT", "NONCOMPLIANT", "REJECT"),
    "F3-constant-set": ("REJECT", "refuted", "NOT_REFUTED", "NONCOMPLIANT", "CERTIFY"),
    "F4-rate-matched": ("REJECT", "refuted", "NOT_REFUTED", "NONCOMPLIANT", "CERTIFY"),
    "F5-non-nested": ("REJECT", "refuted", "INCONSISTENT", "NONCOMPLIANT", "CERTIFY"),
    "U1-no-beliefs": ("REJECT", "on_unmeasured", "NOT_REFUTED", "on_unmeasured", "CERTIFY"),
    "U2-missing-run": ("REJECT", "on_unmeasured", "NOT_REFUTED", "on_unmeasured", "CERTIFY"),
    "U3-non-nested-no-beliefs": ("REJECT", "refuted", "INCONSISTENT", "on_unmeasured",
                                 "CERTIFY"),
}


def cases():
    """Fresh deep copies of every case, by case_id, in fixture order."""
    return dict((c["case_id"], copy.deepcopy(c)) for c in CASES)


def labels():
    return dict(LABELS)


def summary():
    """Return the printed table and counts as a list of lines."""
    cs = cases()
    recs = [M.evaluate(c) for c in cs.values()]
    lines = ["%-26s %-13s %-7s %-14s %-13s %-13s %-8s %s" % (
        "case", "kind", "gate", "rejected_as", "belief_free", "known_p", "baseline",
        "abstained 0.5/0.75/0.9")]
    for c, r in zip(cs.values(), recs):
        ab = dict((k, a) for k, a, _ in r["report"]["abstention"])
        cells = "/".join(str(ab[k]) if k in ab else "-" for k in M.T_KEYS)
        lines.append("%-26s %-13s %-7s %-14s %-13s %-13s %-8s %s of %d" % (
            r["case_id"], c["kind"], r["decision"], r["rejected_as"] or "-",
            r["belief_free"]["verdict"], r["known_p"]["verdict"],
            r["baseline"]["decision"], cells, len(c["items"])))
    tot = M.totals(recs, PLANTED, CONTROLS)
    agree = sum(1 for c, r in zip(cs.values(), recs) if oracle.reference(c) == r)
    lines.append("cases: %d (controls %d, planted faults %d, unmeasured %d, other %d)" % (
        len(recs), len(CONTROLS), len(PLANTED), len(UNMEASURED),
        len(recs) - len(CONTROLS) - len(PLANTED) - len(UNMEASURED)))
    lines.append("known-p mode flags planted faults: %d/%d" % (
        len(tot["known_p_flagged"]), tot["planted"]))
    lines.append("belief-free mode flags planted faults: %d/%d (%s)" % (
        len(tot["belief_free_flagged"]), tot["planted"], ", ".join(tot["belief_free_flagged"])))
    lines.append("gate rejects planted faults: %d/%d" % (len(tot["gate_rejected"]), tot["planted"]))
    lines.append("rate-only baseline certifies planted faults: %d/%d (%s)" % (
        len(tot["baseline_certified"]), tot["planted"], ", ".join(tot["baseline_certified"])))
    lines.append("false alarms on controls: %d/%d" % (len(tot["false_alarms"]), tot["controls"]))
    lines.append("module vs oracle: %d/%d cases agree" % (agree, len(recs)))
    return lines


if __name__ == "__main__":
    print("\n".join(summary()))
