"""Tests for playground-original budget_max + cooldown gate (stdlib unittest)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from gate import DenyReason, GateOutcome, OutboundBudgetCooldownGate


class GateUnitTests(unittest.TestCase):
    def test_cooldown_blocks_before_elapsed(self) -> None:
        gate = OutboundBudgetCooldownGate(budget_max=5, cooldown_s=10.0)
        first = gate.request_send(0.0)
        self.assertEqual(first.outcome, GateOutcome.ALLOW)

        second = gate.request_send(2.0)
        self.assertEqual(second.outcome, GateOutcome.DENY)
        self.assertEqual(second.reason, DenyReason.COOLDOWN)
        self.assertAlmostEqual(second.cooldown_remaining_s, 8.0)

    def test_cooldown_allows_after_elapsed(self) -> None:
        gate = OutboundBudgetCooldownGate(budget_max=5, cooldown_s=10.0)
        gate.request_send(0.0)
        third = gate.request_send(10.0)
        self.assertEqual(third.outcome, GateOutcome.ALLOW)

    def test_budget_max_blocks_after_cap(self) -> None:
        gate = OutboundBudgetCooldownGate(budget_max=2, cooldown_s=0.0)
        self.assertEqual(gate.request_send(0.0).outcome, GateOutcome.ALLOW)
        self.assertEqual(gate.request_send(0.0).outcome, GateOutcome.ALLOW)
        denied = gate.request_send(0.0)
        self.assertEqual(denied.outcome, GateOutcome.DENY)
        self.assertEqual(denied.reason, DenyReason.BUDGET)


class FixtureScenarioTests(unittest.TestCase):
    def test_json_fixtures(self) -> None:
        path = Path(__file__).with_name("fixtures") / "budget_cooldown_scenarios.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for scenario in data["scenarios"]:
            with self.subTest(scenario=scenario["name"]):
                gate = OutboundBudgetCooldownGate(
                    budget_max=scenario["budget_max"],
                    cooldown_s=scenario["cooldown_s"],
                )
                for event in scenario["events"]:
                    decision = gate.request_send(float(event["t"]))
                    if event["expect"] == "allow":
                        self.assertEqual(decision.outcome, GateOutcome.ALLOW)
                    else:
                        self.assertEqual(decision.outcome, GateOutcome.DENY)
                        expected = DenyReason.COOLDOWN if event["reason"] == "cooldown" else DenyReason.BUDGET
                        self.assertEqual(decision.reason, expected)


if __name__ == "__main__":
    unittest.main()
