"""Offline tests; provenance checks establish presence, not paper findings."""
import ast
from dataclasses import FrozenInstanceError, replace
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest

import disclosure
from disclosure import Evidence, Setting, disclose, simulate
from fixtures import POLICIES, STRATEGIES, cautious, paired_runs, pressure, steady

ROOT = Path(__file__).resolve().parent


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.parts.append(data)


def normalized(raw):
    parser = Text()
    parser.feed(raw)
    return " ".join(" ".join(parser.parts).split())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.setting = Setting()

    def test_paired_setting_identity(self):
        for coarse, fine in paired_runs():
            self.assertIs(coarse.setting, fine.setting)
            self.assertEqual(coarse.strategy, fine.strategy)
            self.assertEqual(coarse.setting.rules, fine.setting.rules)
            self.assertEqual(coarse.setting.seller_cost, fine.setting.seller_cost)
            self.assertEqual(coarse.setting.buyer_value, fine.setting.buyer_value)

    def test_only_optional_detail_changes(self):
        coarse, fine = (disclose(self.setting, p) for p in POLICIES)
        self.assertEqual(replace(fine, policy=coarse.policy, exact_cost=None), coarse)
        self.assertEqual(fine.exact_cost, self.setting.seller_cost)
        self.assertIs(coarse.evidence, fine.evidence)

    def test_same_strategy_function_receives_both_views(self):
        seen = []
        def recorder(view):
            seen.append(view)
            return 9
        for policy in POLICIES:
            simulate(self.setting, recorder, policy)
        self.assertEqual([v.policy for v in seen], list(POLICIES))
        self.assertEqual([v.exact_cost for v in seen], [None, 4])

    def test_unaffected_strategy(self):
        coarse, fine = paired_runs()[0]
        self.assertEqual((coarse.action, fine.action), (9, 9))
        self.assertEqual((coarse.realized_welfare, fine.realized_welfare), (8, 8))

    def test_benefiting_strategy(self):
        coarse, fine = paired_runs()[1]
        self.assertIsNone(coarse.action)
        self.assertEqual(fine.action, 5)
        self.assertGreater(fine.realized_welfare, coarse.realized_welfare)

    def test_sign_reversal_existence(self):
        coarse, fine = paired_runs()[2]
        self.assertEqual((coarse.action, fine.action), (9, 3))
        self.assertLess(fine.realized_welfare, coarse.realized_welfare)
        self.assertGreaterEqual(fine.feasible_quality, coarse.feasible_quality)
        self.assertLessEqual(set(coarse.feasible_prices), set(fine.feasible_prices))
        self.assertEqual(fine.status, "hold")

    def test_candidate_quality_not_realized_welfare(self):
        fine = simulate(self.setting, pressure, "disclose")
        self.assertEqual(fine.feasible_quality, 8)
        self.assertEqual(fine.realized_welfare, 0)
        self.assertEqual(fine.feasible_prices, (5, 9))

    def test_physical_opportunities_constant(self):
        for coarse, fine in paired_runs():
            self.assertEqual((coarse.physical_quality, fine.physical_quality), (8, 8))
            self.assertEqual(coarse.feasible_prices, (9,))
            self.assertEqual(fine.feasible_prices, (5, 9))

    def test_realized_utility_accounting(self):
        for pair in paired_runs():
            for result in pair:
                self.assertEqual(result.realized_welfare,
                                 result.buyer_gain + result.seller_gain)
                self.assertGreaterEqual(result.buyer_gain, 0)
                self.assertGreaterEqual(result.seller_gain, 0)
                if result.status == "welfare":
                    self.assertEqual(result.buyer_gain, 12 - result.action)
                    self.assertEqual(result.seller_gain, result.action - 4)

    def test_required_evidence_never_hidden(self):
        for evidence in (Evidence(True, True), Evidence(False, True),
                         Evidence(True, False), Evidence(False, False)):
            setting = replace(self.setting, evidence=evidence)
            for policy in POLICIES:
                view = disclose(setting, policy)
                self.assertIs(view.evidence, evidence)
                self.assertEqual(view.evidence.safety, evidence.safety)
                self.assertEqual(view.evidence.authorization, evidence.authorization)
        self.assertIsNone(disclose(self.setting, POLICIES[0]).exact_cost)
        self.assertIsNotNone(disclose(self.setting, POLICIES[1]).exact_cost)

    def test_missing_safeguard_holds_before_strategy(self):
        def must_not_run(view):
            self.fail("strategy called despite missing required evidence")
        for evidence in (Evidence(False, True), Evidence(True, False)):
            setting = replace(self.setting, evidence=evidence)
            for policy in POLICIES:
                result = simulate(setting, must_not_run, policy)
                self.assertEqual((result.status, result.action, result.realized_welfare),
                                 ("hold", None, 0))

    def test_inputs_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            self.setting.seller_cost = 1
        with self.assertRaises(FrozenInstanceError):
            self.setting.evidence.safety = False
        with self.assertRaises(FrozenInstanceError):
            disclose(self.setting, POLICIES[0]).exact_cost = 4

    def test_unknown_policy_fails_closed(self):
        with self.assertRaises(ValueError):
            disclose(self.setting, "hide-safety")

    def test_invalid_coarse_set_rejected(self):
        with self.assertRaises(ValueError):
            Setting(cost_possibilities=(8,))
        with self.assertRaises(ValueError):
            Setting(candidate_prices=())

    def test_interaction_rules_not_configurable(self):
        with self.assertRaises(ValueError):
            Setting(rules="counteroffers")

    def test_above_value_offer_holds(self):
        def excessive(view):
            return view.buyer_value + 1
        self.assertEqual(simulate(self.setting, excessive, "disclose").status, "hold")

    def test_empty_feasible_menu(self):
        setting = replace(self.setting, candidate_prices=(1, 2))
        for policy in POLICIES:
            result = simulate(setting, steady, policy)
            self.assertEqual((result.feasible_quality, result.physical_quality), (0, 0))

    def test_noninteger_script_output_rejected(self):
        def malformed(view):
            return True
        with self.assertRaises(ValueError):
            simulate(self.setting, malformed, "disclose")


class ScopeTests(unittest.TestCase):
    def test_import_allowlist(self):
        stdlib_and_local = {"ast", "dataclasses", "hashlib", "html", "json", "pathlib",
                            "re", "unittest", "typing", "disclosure", "fixtures"}
        forbidden = {"sqlite3", "subprocess", "socket", "urllib", "http", "hmac",
                     "requests", "docker"}
        for name in ("disclosure.py", "fixtures.py", "test_disclosure.py"):
            tree = ast.parse((ROOT / name).read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                             else [node.module or ""])
                    for module in names:
                        root = module.split(".")[0]
                        self.assertIn(root, stdlib_and_local)
                        self.assertNotIn(root, forbidden)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"eval", "exec", "__import__"})

    def test_no_authorizing_api_names(self):
        for name in disclosure.__all__:
            self.assertTrue(hasattr(disclosure, name))
            for banned in ("allow", "approve", "permit"):
                self.assertNotIn(banned, name.lower())
        for filename in ("disclosure.py", "fixtures.py"):
            for node in ast.walk(ast.parse((ROOT / filename).read_text())):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    for banned in ("allow", "approve", "permit"):
                        self.assertNotIn(banned, node.name.lower())

    def test_number_hygiene(self):
        # ABSENT needles: the paper's auction percentages, never sketch results.
        pattern = r"(?<![\w.])(?:97|78|94|64|62)(?![\w.])"
        for name in ("disclosure.py", "fixtures.py", "README.md", "NOTICE"):
            self.assertIsNone(re.search(pattern, (ROOT / name).read_text()), name)

    def test_readme_scope(self):
        text = (ROOT / "README.md").read_text()
        for needle in ("method sketch", "not Team OS law", "not village law",
                       "https://arxiv.org/abs/2611.07667",
                       "experiments/2026-11-08/w17-disclosure-policy/",
                       "scripted counterexample", "not a replication", "Not implemented",
                       "UNVERIFIED", "Builder reflection", "Ludex", "Cody/Naru",
                       "all paper empirical / model results", "transfer to real LLMs",
                       "coarser disclosure is generally better", "production use as a market",
                       "not evidence about LLMs", "not a village disclosure optimum"):
            # The latter scope can be expressed with a coordinating conjunction.
            if needle == "not a village disclosure optimum":
                self.assertIn("or a village disclosure optimum", text)
            else:
                self.assertIn(needle, text)
        self.assertIn("Required safety/authorization evidence is never withheld from a checker.",
                      text)
        self.assertTrue(text.endswith("Implementation may be complete; it is not declared verified.\n"))

    def test_no_workflow_labels(self):
        # Intentionally do not inspect the future day index in any test.
        for name in ("README.md", "NOTICE"):
            text = (ROOT / name).read_text()
            for needle in ("KEEP", "CloudAgent", "Smith", "(draft)"):
                self.assertNotIn(needle, text)

    def test_notice_terms(self):
        text = (ROOT / "NOTICE").read_text()
        for needle in ("Original", "SYNTHETIC", "arXiv perpetual non-exclusive",
                       "not CC BY", "not a software grant", "Method-cite only",
                       "404", "no accessible implementation pin"):
            self.assertIn(needle, text)

    def test_license_and_no_code_pin(self):
        evidence = json.loads((ROOT / "paper_evidence.json").read_text())
        self.assertTrue(evidence["license"]["not_cc_by"])
        self.assertFalse(evidence["license"]["software_grant"])
        self.assertIn("licenses/nonexclusive-distrib/1.0/", evidence["license"]["url"])
        self.assertEqual(evidence["implementation"]["http_status"], 404)
        self.assertEqual(evidence["implementation"]["observed_status_line"], "HTTP/2 404")
        self.assertIsNone(evidence["implementation"]["accessible_pin"])
        self.assertTrue(evidence["implementation"]["observed_at"].endswith("+09:00"))
        self.assertIn("curl -sI", evidence["implementation"]["command"])


class PaperPresenceTests(unittest.TestCase):
    def check_source(self, source_id):
        evidence = json.loads((ROOT / "paper_evidence.json").read_text())
        source = evidence["sources"][source_id]
        path = Path(source["path"])
        if not path.exists():
            self.skipTest("local paper snapshot absent: " + source_id)
        raw = path.read_bytes()
        self.assertEqual(len(raw), source["bytes"])
        self.assertEqual(digest(raw), source["sha256"])
        text = normalized(raw.decode("utf-8"))
        self.assertEqual(digest(text.encode()), source["normalized_sha256"])
        self.assertEqual(len(text), source["normalized_chars"])
        if source_id == "abs":
            self.assertIn(evidence["license"]["url"], raw.decode())
        for excerpt in evidence["excerpts"]:
            if excerpt["source"] != source_id:
                continue
            with self.subTest(excerpt=excerpt["id"]):
                self.assertLessEqual(len(excerpt["excerpt"]), 160)
                self.assertEqual(excerpt["status"], "FOUND")
                self.assertEqual(text[excerpt["start"]:excerpt["end"]], excerpt["excerpt"])
                window = text[excerpt["window_start"]:excerpt["window_end"]]
                self.assertEqual(digest(window.encode()), excerpt["source_window_sha256"])

    def test_html_excerpts_found(self):
        self.check_source("html")

    def test_abs_excerpts_found(self):
        self.check_source("abs")


if __name__ == "__main__":
    unittest.main()
