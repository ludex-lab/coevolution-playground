import json
import unittest
from pathlib import Path

from directive import directive

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_case(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class DirectiveFixtures(unittest.TestCase):
    def test_same_blocker_twice_escalates(self) -> None:
        case = load_case("same_blocker_twice")
        out = directive(**case["inputs"])
        self.assertEqual(out.action, case["expect"]["action"])
        self.assertIn("same_blocker", out.reason)

    def test_new_ref_continues(self) -> None:
        case = load_case("new_evidence_ref")
        out = directive(**case["inputs"])
        self.assertEqual(out.action, "CONTINUE_AUTONOMOUSLY")
        self.assertTrue(out.reason.startswith("new_evidence:"))

    def test_locked_path_changed_blocked(self) -> None:
        case = load_case("locked_path_violation")
        out = directive(**case["inputs"])
        self.assertEqual(out.action, "blocked")
        self.assertIn("locked_path_changed", out.reason)

    def test_observed_beats_reported_complete(self) -> None:
        """Reported still in_progress; observed marks complete — trust observed."""
        out = directive(
            observed={"status": "complete", "verification_ok": True},
            reported={"status": "in_progress", "verification_ok": False},
            evidence_refs=[],
            prior_fingerprint=None,
            streak=0,
            budget=None,
        )
        self.assertEqual(out.action, "COMPLETE")
        self.assertEqual(out.reason, "observed_complete")

    def test_reported_only_complete_reason(self) -> None:
        """No observed status — COMPLETE must not claim observed_complete."""
        out = directive(
            observed={},
            reported={"status": "complete", "verification_ok": True},
            evidence_refs=[],
            prior_fingerprint=None,
            streak=0,
            budget=None,
        )
        self.assertEqual(out.action, "COMPLETE")
        self.assertEqual(out.reason, "reported_complete")
        self.assertNotIn("observed_complete", out.reason)


if __name__ == "__main__":
    unittest.main()
