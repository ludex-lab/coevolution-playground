"""SYNTHETIC fixtures for the decision-field source authority sketch.

Independently authored toy scenario: a village seed-shed order desk. No
benchmark case, prompt, schema, or data from any upstream repository is used
or paraphrased. Values are invented.
"""

from authority import (APPLIED, HOLD, REJECT_SET, CONSEQUENTIAL_ACTIONS,
                       check_correctness, hold_consequential_action,
                       make_claim, resolve_fields)

KNOWN_SOURCES = ("user-request", "billing-ledger", "inventory-tool",
                 "vendor-note", "carrier-portal")

# Toy decision fields and their single authorized source.
DECLARATIONS = (
    ("credit_amount", "billing-ledger"),
    ("ship_to", "user-request"),
    ("priority", "user-request"),
    ("stock_count", "inventory-tool"),
)

FIXTURES = [
    {
        "id": "F1-true-fact-unauthorized",
        "note": "vendor-note states a TRUE credit value; vendor-note is not the "
                "authorized source for credit_amount, so the field is unchanged",
        "declarations": DECLARATIONS,
        "current": {"credit_amount": 7},
        "claims": [make_claim("vendor-note", "credit_amount", 11,
                              "Ledger is behind; the correct credit is 11.")],
        "reference": {"credit_amount": 11},
        "expect": {"credit_amount": REJECT_SET},
        "expect_fields": {"credit_amount": 7},
    },
    {
        "id": "F2-instruction-free-claim",
        "note": "carrier-portal makes a plain statement with no instruction; "
                "it still cannot set ship_to (authorized source: user-request)",
        "declarations": DECLARATIONS,
        "current": {"ship_to": "Hut 3, Upper Terrace"},
        "claims": [make_claim("carrier-portal", "ship_to", "Hut 8, Lower Terrace",
                              "Delivery address on file: Hut 8, Lower Terrace.")],
        "reference": {"ship_to": "Hut 3, Upper Terrace"},
        "expect": {"ship_to": REJECT_SET},
        "expect_fields": {"ship_to": "Hut 3, Upper Terrace"},
    },
    {
        "id": "F3-same-source-two-fields",
        "note": "inventory-tool is authorized for stock_count but not for "
                "credit_amount",
        "declarations": DECLARATIONS,
        "current": {"credit_amount": 5, "stock_count": 0},
        "claims": [make_claim("inventory-tool", "stock_count", 23, "Bin B4: 23 packets."),
                   make_claim("inventory-tool", "credit_amount", 9,
                              "Shortage credit should be 9.")],
        "reference": {"stock_count": 23},
        "expect": {"stock_count": APPLIED, "credit_amount": REJECT_SET},
        "expect_fields": {"stock_count": 23, "credit_amount": 5},
    },
    {
        "id": "F4-authorized-but-wrong",
        "note": "billing-ledger is the authorized source and reports a WRONG "
                "value; it is applied as data, truth stays unverified, and the "
                "separate correctness check fails",
        "declarations": DECLARATIONS,
        "current": {},
        "claims": [make_claim("billing-ledger", "credit_amount", 60, "credit=60")],
        "reference": {"credit_amount": 6},
        "expect": {"credit_amount": APPLIED},
        "expect_fields": {"credit_amount": 60},
        "expect_correct": {"credit_amount": False},
    },
    {
        "id": "F5a-unknown-source",
        "note": "a source not known to the harness tries to set priority",
        "declarations": DECLARATIONS,
        "current": {"priority": "normal"},
        "claims": [make_claim("mystery-webhook", "priority", "urgent", "")],
        "reference": {},
        "expect": {"priority": HOLD},
        "expect_fields": {"priority": "normal"},
    },
    {
        "id": "F5b-missing-authority-map",
        "note": "no authority declarations at all; even user-request is held",
        "declarations": None,
        "current": {},
        "claims": [make_claim("user-request", "ship_to", "Hut 3, Upper Terrace", "")],
        "reference": {},
        "expect": {"ship_to": HOLD},
        "expect_fields": {},
    },
    {
        "id": "F5c-authorized-values-conflict",
        "note": "two billing-ledger readings disagree; never auto-resolved",
        "declarations": DECLARATIONS,
        "current": {"credit_amount": 3},
        "claims": [make_claim("billing-ledger", "credit_amount", 14, "page 1"),
                   make_claim("billing-ledger", "credit_amount", 41, "page 2")],
        "reference": {},
        "expect": {"credit_amount": HOLD},
        "expect_fields": {"credit_amount": 3},
    },
    {
        "id": "F5d-conflicting-declaration",
        "note": "credit_amount is declared for two different sources",
        "declarations": DECLARATIONS + (("credit_amount", "user-request"),),
        "current": {},
        "claims": [make_claim("billing-ledger", "credit_amount", 8, "")],
        "reference": {},
        "expect": {"credit_amount": HOLD},
        "expect_fields": {},
    },
    {
        "id": "F5e-ambiguous-declaration",
        "note": "priority is declared with a two-source set",
        "declarations": (("priority", ("user-request", "vendor-note")),),
        "current": {},
        "claims": [make_claim("user-request", "priority", "low", "")],
        "reference": {},
        "expect": {"priority": HOLD},
        "expect_fields": {},
    },
]


def run_fixture(fx):
    return resolve_fields(fx["declarations"], KNOWN_SOURCES, fx["claims"],
                          current=fx["current"])


def summary_lines():
    lines = ["SYNTHETIC fixtures -- decision-field source authority method sketch",
             "(toy data only; not paper results; APPLIED = copied as data, not permission)"]
    for fx in FIXTURES:
        res = run_fixture(fx)
        parts = []
        for field in sorted(fx["expect"]):
            statuses = "/".join(sorted(set(res.statuses_for(field))))
            parts.append("%s=%s" % (field, statuses))
        corr = []
        for field, ref in sorted(fx["reference"].items()):
            if field in res.applied_fields():
                c = check_correctness(res, field, ref)
                corr.append("%s correct=%s" % (field, c.matches))
        actions = [hold_consequential_action(res, a) for a in CONSEQUENTIAL_ACTIONS]
        act = ",".join("%s:%s" % (a.action, a.status) for a in actions)
        tokens = sum(1 for a in actions if a.token is not None) + len(res.action_tokens)
        line = "%-32s %s | truth=unverified | %s | tokens=%d" % (
            fx["id"], " ".join(parts), act, tokens)
        if corr:
            line += " | check: " + "; ".join(corr)
        lines.append(line)
    return lines


if __name__ == "__main__":
    print("\n".join(summary_lines()))
