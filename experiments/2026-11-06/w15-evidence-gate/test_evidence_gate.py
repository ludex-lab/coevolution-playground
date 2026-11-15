"""Tests for Layer B evidence-gated authority (synthetic fixtures, no network)."""

from __future__ import annotations

import unittest

from gate import (
    AGGREGATE_PRESSURE_VIOLATION,
    COMPLIANT_SUBOPTIMAL,
    ESCALATE,
    ORACLE_CORRECT,
    REPLACE,
    RETAIN,
    AuditCertificate,
    TaskFixture,
    apply_evidence_gate,
    certificate_fields_valid,
    parse_audit_certificate,
    valid_repair_certificate,
)


def _task(
    proposal: str,
    *,
    max_loss: float,
    losses: dict[str, float],
) -> TaskFixture:
    return TaskFixture(
        proposal_policy_id=proposal,
        max_weighted_loss=max_loss,
        protected_losses=losses,
    )


def _cert(
    task: TaskFixture,
    *,
    disposition: str,
    recommendation: str,
) -> AuditCertificate:
    return AuditCertificate(
        disposition=disposition,
        proposal_policy_id=task.proposal_policy_id,
        proposal_protected_loss=task.proposal_protected_loss(),
        max_weighted_loss=task.max_weighted_loss,
        proposal_violates_duty_1=task.proposal_violates_duty_1(),
        recommended_policy_id=recommendation,
        recommended_protected_loss=float(task.protected_losses[recommendation]),
    )


class EvidenceGateTests(unittest.TestCase):
    def test_oracle_correct_never_flipped_on_replace(self):
        task = _task("p_good", max_loss=2.0, losses={"p_good": 1.0, "p_alt": 0.5})
        self.assertEqual(task.proposal_violates_duty_1(), False)
        record = _cert(task, disposition=REPLACE, recommendation="p_alt")
        self.assertFalse(valid_repair_certificate(record, task))
        self.assertEqual(apply_evidence_gate("p_good", record, task), "p_good")

    def test_retain_leaves_a0(self):
        task = _task("p_bad", max_loss=1.0, losses={"p_bad": 2.0, "p_fix": 0.5})
        record = _cert(task, disposition=RETAIN, recommendation="p_fix")
        self.assertEqual(apply_evidence_gate("p_bad", record, task), "p_bad")

    def test_escalate_leaves_a0(self):
        task = _task("p_bad", max_loss=1.0, losses={"p_bad": 2.0, "p_fix": 0.5})
        record = _cert(task, disposition=ESCALATE, recommendation="p_fix")
        self.assertEqual(apply_evidence_gate("p_bad", record, task), "p_bad")

    def test_replace_binds_with_valid_certificate_on_violation(self):
        task = _task("p_bad", max_loss=1.0, losses={"p_bad": 2.0, "p_fix": 0.5})
        record = _cert(task, disposition=REPLACE, recommendation="p_fix")
        self.assertTrue(valid_repair_certificate(record, task))
        self.assertEqual(apply_evidence_gate("p_bad", record, task), "p_fix")

    def test_invalid_certificate_never_binds(self):
        task = _task("p_bad", max_loss=1.0, losses={"p_bad": 2.0, "p_fix": 0.5})
        record = AuditCertificate(
            disposition=REPLACE,
            proposal_policy_id="p_bad",
            proposal_protected_loss=99.0,
            max_weighted_loss=1.0,
            proposal_violates_duty_1=True,
            recommended_policy_id="p_fix",
            recommended_protected_loss=0.5,
        )
        self.assertFalse(certificate_fields_valid(record, task))
        self.assertEqual(apply_evidence_gate("p_bad", record, task), "p_bad")

    def test_replace_with_noncompliant_repair_does_not_bind(self):
        task = _task("p_bad", max_loss=1.0, losses={"p_bad": 2.0, "p_worse": 1.5})
        record = _cert(task, disposition=REPLACE, recommendation="p_worse")
        self.assertFalse(valid_repair_certificate(record, task))
        self.assertEqual(apply_evidence_gate("p_bad", record, task), "p_bad")

    def test_compliant_suboptimal_welfare_only_not_flipped(self):
        task = _task("p_ok", max_loss=2.0, losses={"p_ok": 1.0, "p_better": 0.2})
        self.assertEqual(task.proposal_violates_duty_1(), False)
        record = _cert(task, disposition=REPLACE, recommendation="p_better")
        self.assertEqual(apply_evidence_gate("p_ok", record, task), "p_ok")

    def test_proposal_state_labels_documented(self):
        self.assertEqual(ORACLE_CORRECT, "oracle_correct")
        self.assertEqual(AGGREGATE_PRESSURE_VIOLATION, "aggregate_pressure_violation")
        self.assertEqual(COMPLIANT_SUBOPTIMAL, "compliant_suboptimal")

    def test_parse_audit_certificate_json(self):
        raw = (
            '{"disposition":"replace","proposal_policy_id":"a","proposal_protected_loss":2,'
            '"max_weighted_loss":1,"proposal_violates_duty_1":true,'
            '"recommended_policy_id":"b","recommended_protected_loss":0.5}'
        )
        rec = parse_audit_certificate(raw, {"a", "b"})
        self.assertEqual(rec.disposition, REPLACE)
        self.assertEqual(rec.recommended_policy_id, "b")

    def test_none_review_leaves_a0(self):
        task = _task("x", max_loss=1.0, losses={"x": 0.0, "y": 0.0})
        self.assertEqual(apply_evidence_gate("x", None, task), "x")


if __name__ == "__main__":
    unittest.main()
