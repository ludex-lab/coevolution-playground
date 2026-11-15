"""Tests for w14-whose-turn session checklist helpers (stdlib unittest)."""

from __future__ import annotations

import unittest

from session_turn_checklist import (
    MonitoringVerdict,
    SNAPSHOT_BANNER_PREFIX,
    SessionExitVerdict,
    check_monitoring_claim,
    check_session_exit,
    format_snapshot_board_header,
    snapshot_board_label_valid,
)


class SessionTurnChecklistTests(unittest.TestCase):
    def test_p2_denies_exit_while_holding_turn(self) -> None:
        decision = check_session_exit(holding_turn=True)
        self.assertEqual(decision.verdict, SessionExitVerdict.DENY_HOLDING_TURN)
        self.assertEqual(decision.rule, "P2")

    def test_p2_allows_exit_when_not_holding(self) -> None:
        decision = check_session_exit(holding_turn=False)
        self.assertEqual(decision.verdict, SessionExitVerdict.OK)

    def test_p4_denies_monitoring_without_heartbeat(self) -> None:
        decision = check_monitoring_claim(claims_monitoring=True, has_heartbeat=False)
        self.assertEqual(decision.verdict, MonitoringVerdict.DENY_HEARTBEAT_MISSING)

    def test_p4_allows_monitoring_with_heartbeat(self) -> None:
        decision = check_monitoring_claim(claims_monitoring=True, has_heartbeat=True)
        self.assertEqual(decision.verdict, MonitoringVerdict.OK)

    def test_p4_allows_not_monitoring_without_heartbeat(self) -> None:
        decision = check_monitoring_claim(claims_monitoring=False, has_heartbeat=False)
        self.assertEqual(decision.verdict, MonitoringVerdict.OK)

    def test_snapshot_header_on_its_face(self) -> None:
        header = format_snapshot_board_header("2026-11-05T06:58:00Z")
        self.assertIn("NOT LIVE TRUTH", header)
        self.assertIn("generated_at=2026-11-05T06:58:00Z", header)
        self.assertTrue(snapshot_board_label_valid(header))

    def test_snapshot_label_rejects_stale_board_without_banner(self) -> None:
        self.assertFalse(snapshot_board_label_valid("agent-b <- task-x [new]"))

    def test_snapshot_label_rejects_empty_generated_at_regression(self) -> None:
        self.assertFalse(
            snapshot_board_label_valid(f"{SNAPSHOT_BANNER_PREFIX} — generated_at=")
        )

    def test_formatter_rejects_non_iso_timestamp(self) -> None:
        with self.assertRaises(ValueError):
            format_snapshot_board_header("not-a-time")


if __name__ == "__main__":
    unittest.main()
