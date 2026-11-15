import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from report import (
    adjust_status_for_verify,
    coerce_verify_rc,
    finalize_report,
    host_verified_pass_from_verify_rc,
    report_from_mapping,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


class TestHostVerifiedPass(unittest.TestCase):
    def test_null_verify(self) -> None:
        self.assertIsNone(host_verified_pass_from_verify_rc(None))

    def test_zero_is_pass(self) -> None:
        self.assertTrue(host_verified_pass_from_verify_rc(0))

    def test_nonzero_is_fail(self) -> None:
        self.assertFalse(host_verified_pass_from_verify_rc(1))

    def test_bool_verify_rc_rejected(self) -> None:
        self.assertIsNone(coerce_verify_rc(True))
        self.assertIsNone(host_verified_pass_from_verify_rc(True))


class TestAdjustStatusForVerify(unittest.TestCase):
    def _load(self, name: str):
        with (FIXTURES / name).open(encoding="utf-8") as fh:
            return report_from_mapping(json.load(fh))

    def test_aligned_pass_fixture(self) -> None:
        report = finalize_report(self._load("aligned_pass.json"))
        self.assertEqual(adjust_status_for_verify(report), "aligned_pass")
        self.assertEqual(report.surface_status, "aligned_pass")

    def test_contradicted_fixture(self) -> None:
        report = finalize_report(self._load("contradicted.json"))
        self.assertEqual(report.surface_status, "contradicted")

    def test_verify_pass_self_fail_fixture(self) -> None:
        report = finalize_report(self._load("verify_pass_self_fail.json"))
        self.assertEqual(report.surface_status, "verify_pass_self_fail")

    def test_unverified_fixture(self) -> None:
        report = finalize_report(self._load("unverified_claim_pass.json"))
        self.assertEqual(report.surface_status, "unverified_claim_pass")

    def test_accepted_overlay(self) -> None:
        report = finalize_report(self._load("contradicted_accepted.json"))
        self.assertEqual(report.surface_status, "contradicted_accepted")
        self.assertEqual(report.rework_of, "r-contra-002")


if __name__ == "__main__":
    unittest.main()
