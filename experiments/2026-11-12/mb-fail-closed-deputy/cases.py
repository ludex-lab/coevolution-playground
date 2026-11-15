"""Deterministic synthetic case set (enumerated, no randomness).

Every (permission, evidence) pair is crossed with every action, giving
3 x 3 x 6 = 54 cases. Expected labels come from a hand-written table
that is independent of deputy.classify, so a drift in either side shows
up as a label mismatch.
"""

ACTIONS = (
    "read_invoice",
    "send_payment",
    "delete_record",
    "share_report",
    "update_vendor",
    "export_payroll",
)

EXPECTED_CASE = {
    ("granted", "complete"): "permitted",
    ("granted", "partial"): "missing_evidence",
    ("granted", "missing"): "missing_evidence",
    ("denied", "complete"): "explicit_deny",
    ("denied", "partial"): "explicit_deny",
    ("denied", "missing"): "explicit_deny",
    ("unknown", "complete"): "missing_evidence",
    ("unknown", "partial"): "missing_evidence",
    ("unknown", "missing"): "missing_evidence",
}

EXPECTED_COUNTS = {"permitted": 6, "explicit_deny": 18, "missing_evidence": 30}


def build_cases():
    """Return a fresh list of (request, expected_case) pairs in fixed order."""
    out = []
    n = 0
    for permission in ("granted", "denied", "unknown"):
        for evidence in ("complete", "partial", "missing"):
            for action in ACTIONS:
                n += 1
                request = {
                    "request_id": "c%02d" % n,
                    "action": action,
                    "permission": permission,
                    "evidence": evidence,
                }
                out.append((request, EXPECTED_CASE[(permission, evidence)]))
    return out
