"""Stdlib tests for the Wave15 Soft1 handoff-gate decision table."""

from __future__ import annotations

import unittest

from gate import (
    CONTINUATION_ELIGIBLE,
    EVALUATED,
    FORBIDDEN_ROUTE_TOKENS,
    PASS,
    SEPARATE_RECORDS,
    STOP,
    Packet,
    apply_gate,
)
from packets import EXPECTED_ROUTES, SYNTHETIC_PACKETS


class TestSixFolderRoutes(unittest.TestCase):
    def test_six_synthetic_packets_match_upstream_example_routes(self):
        self.assertEqual(len(SYNTHETIC_PACKETS), 6)
        seen = []
        for packet in SYNTHETIC_PACKETS:
            result = apply_gate(packet)
            seen.append(packet.folder)
            expected = EXPECTED_ROUTES[packet.folder]
            self.assertEqual(
                (result.routing_recommendation, result.routing_reason),
                expected,
                msg=packet.folder,
            )
            self.assertEqual(result.folder, packet.folder)
        self.assertEqual(
            seen,
            [
                "01-complete-evidence",
                "02-premature-pass",
                "03-local-blocker",
                "04-out-of-scope",
                "05-evaluator-unavailable",
                "06-stale-evidence",
            ],
        )

    def test_folder_label_is_not_consulted_for_routing(self):
        packet = SYNTHETIC_PACKETS[0]
        relabeled = Packet(
            folder="not-a-routing-enum",
            worker_report=packet.worker_report,
            assessment_status=packet.assessment_status,
            prohibited_operation=packet.prohibited_operation,
            candidate_match=packet.candidate_match,
            evaluator_timeout=packet.evaluator_timeout,
            criterion_labels=packet.criterion_labels,
            repair_proposal_supported=packet.repair_proposal_supported,
            budget_remaining=packet.budget_remaining,
        )
        result = apply_gate(relabeled)
        self.assertEqual(result.routing_recommendation, "REVIEW_READY")
        self.assertEqual(result.routing_reason, "EVIDENCE_READY_AT_LOCAL_STAGE")


class TestInvariants(unittest.TestCase):
    def test_no_path_is_auto_accept_or_auto_merge(self):
        for packet in SYNTHETIC_PACKETS:
            result = apply_gate(packet)
            blob = " ".join(
                [
                    result.routing_recommendation,
                    result.routing_reason,
                ]
            )
            for token in FORBIDDEN_ROUTE_TOKENS:
                self.assertNotIn(token.lower(), blob.lower())
            self.assertFalse(result.execution_authorized)
            self.assertFalse(result.grant_issued)
            self.assertFalse(result.accepted)
            self.assertFalse(result.merged)
            self.assertFalse(result.deployed)
            self.assertFalse(result.authorized_for_production)

    def test_review_ready_is_ready_for_review_only(self):
        complete = next(p for p in SYNTHETIC_PACKETS if p.folder == "01-complete-evidence")
        result = apply_gate(complete)
        self.assertEqual(result.routing_recommendation, "REVIEW_READY")
        self.assertTrue(result.review_ready_only)
        self.assertFalse(result.accepted)
        self.assertFalse(result.merged)
        self.assertFalse(result.deployed)
        self.assertFalse(result.authorized_for_production)
        self.assertFalse(result.grant_issued)
        self.assertFalse(result.execution_authorized)

    def test_continuation_eligible_is_not_a_grant(self):
        for folder in ("02-premature-pass", "03-local-blocker"):
            packet = next(p for p in SYNTHETIC_PACKETS if p.folder == folder)
            result = apply_gate(packet)
            self.assertEqual(result.routing_recommendation, CONTINUATION_ELIGIBLE)
            self.assertFalse(result.execution_authorized)
            self.assertFalse(result.grant_issued)

    def test_separate_records_stay_separate(self):
        self.assertEqual(
            SEPARATE_RECORDS,
            (
                "passing_test",
                "evaluator_answer",
                "authorization_to_act",
                "lead_acceptance",
            ),
        )
        self.assertEqual(len(set(SEPARATE_RECORDS)), 4)
        for packet in SYNTHETIC_PACKETS:
            result = apply_gate(packet)
            self.assertNotIn(result.routing_recommendation, SEPARATE_RECORDS)
            # A gate route is not the lead's acceptance and not an authorization.
            self.assertNotEqual(result.routing_recommendation, "lead_acceptance")
            self.assertFalse(result.execution_authorized)

    def test_prohibited_operation_stops_even_if_evaluator_timed_out(self):
        packet = Packet(
            folder="04-out-of-scope",
            worker_report="BLOCKED",
            assessment_status="NOT_EVALUATED",
            prohibited_operation=True,
            candidate_match=True,
            evaluator_timeout=True,
            criterion_labels=(),
            repair_proposal_supported=True,
        )
        result = apply_gate(packet)
        self.assertEqual(result.routing_recommendation, STOP)
        self.assertEqual(result.routing_reason, "PROHIBITED_OPERATION")
        self.assertFalse(result.grant_issued)

    def test_uncovered_combination_raises(self):
        packet = Packet(
            folder="uncovered",
            worker_report=PASS,
            assessment_status=EVALUATED,
            prohibited_operation=False,
            candidate_match=True,
            evaluator_timeout=False,
            criterion_labels=("CONTRADICTED",),
            repair_proposal_supported=False,
            budget_remaining=False,
        )
        with self.assertRaises(ValueError):
            apply_gate(packet)


if __name__ == "__main__":
    unittest.main()
