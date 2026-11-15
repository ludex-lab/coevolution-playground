import json
import unittest
from pathlib import Path

from silence_expiry.actions import EscalationError, check_fallbacks
from silence_expiry.engine import Escalation, EscalationEngine, JournalKind
from silence_expiry.policy import ConfigError, OnExpiry, TerminalState, load_policy

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

ACTIONS = {
    "deploy": {"risk": "high", "safe_fallback": "rollback"},
    "rollback": {"risk": "low"},
    "nuke": {"risk": "medium"},
}


class TestOnExpiryDoctrine(unittest.TestCase):
    def test_no_allow_in_enum(self):
        values = [m.value for m in OnExpiry]
        self.assertNotIn("allow", values)

    def test_loader_rejects_on_expiry_allow(self):
        policy = {
            "rules": {
                "high": {
                    "requires_approval": True,
                    "ladder": ["primary"],
                    "deadline_s": 10,
                    "on_expiry": "allow",
                }
            }
        }
        with self.assertRaises(ConfigError) as ctx:
            load_policy(policy)
        self.assertIn("allow", str(ctx.exception).lower())

    def test_loader_rejects_allow_when_requires_approval_omitted(self):
        policy = {
            "rules": {
                "high": {
                    "ladder": ["primary"],
                    "deadline_s": 10,
                    "on_expiry": "allow",
                }
            }
        }
        with self.assertRaises(ConfigError):
            load_policy(policy)

    def test_loader_rejects_missing_on_expiry(self):
        policy = {
            "rules": {
                "high": {
                    "requires_approval": True,
                    "ladder": ["primary"],
                    "deadline_s": 10,
                }
            }
        }
        with self.assertRaises(ConfigError) as ctx:
            load_policy(policy)
        self.assertIn("on_expiry", str(ctx.exception))

    def test_loader_rejects_unknown_rule_keys(self):
        policy = {
            "rules": {
                "high": {
                    "requires_aproval": True,
                    "ladder": ["primary"],
                    "deadline_s": 10,
                    "on_expiry": "deny",
                }
            }
        }
        with self.assertRaises(ConfigError) as ctx:
            load_policy(policy)
        self.assertIn("unknown keys", str(ctx.exception))

    def test_quorum_below_one_rejected(self):
        policy = {
            "rules": {
                "high": {
                    "requires_approval": True,
                    "ladder": ["primary"],
                    "deadline_s": 10,
                    "on_expiry": "deny",
                    "quorum": 0,
                }
            }
        }
        with self.assertRaises(ConfigError) as ctx:
            load_policy(policy)
        self.assertIn("quorum", str(ctx.exception).lower())


class TestFallbackChecks(unittest.TestCase):
    def test_self_fallback_is_problem(self):
        bad = {"deploy": {"risk": "high", "safe_fallback": "deploy"}}
        self.assertTrue(any("itself" in p for p in check_fallbacks(bad)))

    def test_propose_rejects_self_fallback(self):
        policy = load_policy(
            {
                "rules": {
                    "high": {
                        "requires_approval": True,
                        "ladder": ["primary"],
                        "deadline_s": 5,
                        "on_expiry": "safe_fallback",
                    }
                }
            }
        )
        eng = EscalationEngine(policy, {"deploy": {"risk": "high", "safe_fallback": "deploy"}})
        with self.assertRaises(ConfigError):
            eng.propose("x", "deploy", "high", now=0.0)

    def test_self_fallback_never_fell_back_on_tick(self):
        policy = load_policy(
            {
                "rules": {
                    "high": {
                        "requires_approval": True,
                        "ladder": ["primary"],
                        "deadline_s": 5,
                        "on_expiry": "safe_fallback",
                    }
                }
            }
        )
        actions = {"deploy": {"risk": "high", "safe_fallback": "deploy"}}
        eng = EscalationEngine(policy, actions)
        esc = Escalation.__new__(Escalation)
        esc.action_id, esc.tool, esc.risk = "y", "deploy", "high"
        esc.rule = policy.rule_for("high")
        esc.tier_index, esc.tier_started_at, esc.terminal = 0, 0.0, None
        esc.safe_fallback = "deploy"
        eng._open["y"] = esc
        eng.tick(now=10.0)
        self.assertEqual(eng._open["y"].terminal, TerminalState.DENIED_ON_TIMEOUT)


class TestTickExpiry(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_policy(FIXTURES / "sample_policy.json")
        self.actions = ACTIONS

    def test_propose_rejects_ungated_low_risk(self):
        eng = EscalationEngine(self.policy, self.actions)
        with self.assertRaises(ConfigError) as ctx:
            eng.propose("z", "rollback", "low", now=0.0)
        self.assertIn("ungated", str(ctx.exception).lower())

    def test_deny_on_timeout_journals_distinct_terminal(self):
        eng = EscalationEngine(self.policy, self.actions)
        eng.propose("a1", "nuke", "medium", now=0.0)
        eng.tick(now=301.0)
        esc = eng._open["a1"]
        self.assertEqual(esc.terminal, TerminalState.DENIED_ON_TIMEOUT)
        kinds = [e["kind"] for e in eng.journal.entries]
        self.assertIn(JournalKind.EXPIRED_NO_ANSWER.value, kinds)
        self.assertIn(JournalKind.DENIED_ON_TIMEOUT.value, kinds)
        self.assertNotIn("action.allowed", kinds)
        self.assertNotIn("allowed", kinds)

    def test_safe_fallback_never_logs_allowed(self):
        policy = load_policy(
            {
                "rules": {
                    "high": {
                        "requires_approval": True,
                        "ladder": ["primary"],
                        "deadline_s": 5,
                        "on_expiry": "safe_fallback",
                    }
                }
            }
        )
        eng = EscalationEngine(policy, self.actions)
        eng.propose("a2", "deploy", "high", now=0.0)
        eng.tick(now=10.0)
        esc = eng._open["a2"]
        self.assertEqual(esc.terminal, TerminalState.FELL_BACK)
        text = json.dumps(eng.journal.entries)
        self.assertIn(JournalKind.FALLBACK_ON_TIMEOUT.value, text)
        self.assertNotIn("action.allowed", text.lower())
        self.assertNotIn('"allowed"', text.lower())

    def test_safe_fallback_without_declared_fallback_becomes_deny(self):
        policy = load_policy(
            {
                "rules": {
                    "high": {
                        "requires_approval": True,
                        "ladder": ["primary"],
                        "deadline_s": 5,
                        "on_expiry": "safe_fallback",
                    }
                }
            }
        )
        eng = EscalationEngine(policy, self.actions)
        eng.propose("a3", "nuke", "high", now=0.0)
        eng.tick(now=10.0)
        self.assertEqual(eng._open["a3"].terminal, TerminalState.DENIED_ON_TIMEOUT)

    def test_escalate_climbs_ladder_then_exhausts(self):
        eng = EscalationEngine(self.policy, self.actions)
        eng.propose("a4", "deploy", "high", now=0.0)
        eng.tick(now=61.0)
        self.assertIsNone(eng._open["a4"].terminal)
        self.assertEqual(eng._open["a4"].tier_index, 1)
        eng.tick(now=122.0)
        self.assertEqual(eng._open["a4"].terminal, TerminalState.EXHAUSTED)

    def test_hold_terminal(self):
        eng = EscalationEngine(self.policy, self.actions)
        eng.propose("a5", "deploy", "critical", now=0.0)
        eng.tick(now=200.0)
        self.assertEqual(eng._open["a5"].terminal, TerminalState.HELD)

    def test_repropose_after_denied_refused(self):
        eng = EscalationEngine(self.policy, self.actions)
        eng.propose("a6", "nuke", "medium", now=0.0)
        eng.tick(now=301.0)
        with self.assertRaises(EscalationError):
            eng.propose("a6", "nuke", "medium", now=302.0)

    def test_approve_quorum_one(self):
        eng = EscalationEngine(self.policy, self.actions)
        eng.propose("a7", "deploy", "high", now=0.0)
        eng.approve("a7")
        self.assertEqual(eng._open["a7"].terminal, TerminalState.APPROVED)


if __name__ == "__main__":
    unittest.main()
