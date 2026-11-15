"""Offline tests; the independent oracle enumerates index combinations."""
import ast
from dataclasses import FrozenInstanceError
import itertools
import json
from pathlib import Path
import random
import unittest

import fixtures
import miner

HERE = Path(__file__).resolve().parent
IMPLEMENTATION = ("miner.py", "fixtures.py")


def oracle(sequences, minimum):
    # Independent support oracle: enumerate sets of subsequences per trace.
    per_trace = []
    for sequence in sequences:
        per_trace.append({tuple(sequence[i] for i in indices)
                          for n in range(1, len(sequence) + 1)
                          for indices in itertools.combinations(range(len(sequence)), n)})
    all_patterns = set().union(*per_trace) if per_trace else set()
    support = {p: sum(p in trace for trace in per_trace) for p in all_patterns}

    def subsequence(small, large):
        return any(tuple(large[i] for i in ix) == small
                   for ix in itertools.combinations(range(len(large)), len(small)))

    return {(p, count) for p, count in support.items() if count >= minimum
            and not any(len(q) > len(p) and support[q] == count and subsequence(p, q)
                        for q in all_patterns)}


class ClosedMinerTests(unittest.TestCase):
    def test_exact_closure_against_independent_brute_force(self):
        cases = [(), ((),), (("a", "b"), ("a", "b")),
                 (("a", "b", "a"), ("b", "a", "b"), ("a", "b")),
                 (("a", "x", "b"), ("a", "b")),
                 (("a", "a"), ("a",), ())]
        rng = random.Random(19)
        cases += [tuple(tuple(rng.choice(("a", "b", "c"))
                             for _ in range(rng.randrange(5)))
                        for _ in range(rng.randrange(5))) for _ in range(100)]
        for sequences in cases:
            for minimum in range(1, len(sequences) + 2):
                with self.subTest(sequences=sequences, minimum=minimum):
                    actual = {(p.tokens, p.support)
                              for p in miner.mine_closed(sequences, minimum)}
                    self.assertEqual(actual, oracle(sequences, minimum))

    def test_support_counts_traces_not_embeddings(self):
        self.assertEqual(miner.mine_closed((("a", "a", "a"),), 2), ())
        self.assertEqual(miner.positions(("a", "b"), ("a", "x", "b")), (0, 2))
        self.assertIsNone(miner.positions(("b", "a"), ("a", "b")))

    def test_training_only_fixed_library_and_prefix(self):
        self.assertEqual(fixtures.K, 3)
        self.assertEqual(fixtures.PRIMARY_CONFIGURATION, "Exclude-errors")
        self.assertEqual(fixtures.CONFIGURATIONS, ("Full", "Exclude-errors", "Variant C"))
        self.assertEqual((fixtures.MIN_SUPPORT, fixtures.MIN_PRECISION), (2, 0.75))
        self.assertTrue({t.name for t in fixtures.TRAIN}.isdisjoint(t.name for t in fixtures.TEST))
        self.assertEqual(fixtures.library(), (miner.Signature(
            miner.Pattern(("click", "click", "nav"), 2), 2, 1.0),))
        extended = tuple(miner.Trace(t.name, t.steps[:3] + ("noise",), t.outcome)
                         for t in fixtures.TRAIN)
        self.assertEqual(miner.emit_signatures(extended, 3, 2, 0.75), fixtures.library())

    def test_records_immutable(self):
        for record, field, value in [(fixtures.TRAIN[0], "outcome", "success"),
                                     (fixtures.library()[0], "precision", 0),
                                     (fixtures.library()[0].pattern, "support", 0)]:
            with self.assertRaises(FrozenInstanceError):
                setattr(record, field, value)
        trace = miner.Trace("immutable", ["click"], "failure")
        self.assertIsInstance(trace.steps, tuple)
        self.assertIsInstance(fixtures.library()[0].pattern.tokens, tuple)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            miner.mine_closed((("a",),), 0)
        with self.assertRaises(ValueError):
            miner.Trace("bad", (), "unknown")
        with self.assertRaises(ValueError):
            miner.emit_signatures((), 0)
        with self.assertRaises(ValueError):
            miner.early_stop((), (), 0)
        with self.assertRaises(ValueError):
            miner.filter_traces((), "fourth")


class MetricsPolicyTests(unittest.TestCase):
    def test_pinned_metrics_separate_fields_and_hand_counts(self):
        expected = {
            "Full": ((7, 3, 2, 1, 2), (3/7, 2/3, 1/2)),
            "Exclude-errors": ((5, 3, 2, 1, 1), (3/5, 2/3, 2/3)),
            "Variant C": ((4, 2, 1, 1, 1), (1/2, 1/2, 1/2)),
        }
        for config, (counts, rates) in expected.items():
            result = miner.evaluate(miner.filter_traces(fixtures.TEST, config),
                                    fixtures.library(), fixtures.K)
            self.assertEqual((result.evaluated, result.matched, result.tp, result.fp, result.fn), counts)
            self.assertEqual(fixtures.HAND_COUNTS[config], counts)
            for actual, wanted in zip((result.coverage, result.precision, result.recall), rates):
                self.assertAlmostEqual(actual, wanted)
        self.assertEqual(miner.coverage(3, 5), 3/5)
        self.assertEqual(miner.precision(2, 1), 2/3)
        self.assertEqual(miner.recall(2, 2), 1/2)

    def test_contamination_exclusion_changes_numbers_and_membership(self):
        full = miner.filter_traces(fixtures.TEST, "Full")
        clean = miner.filter_traces(fixtures.TEST, "Exclude-errors")
        variant = miner.filter_traces(fixtures.TEST, "Variant C")
        self.assertEqual({t.name for t in full} - {t.name for t in clean},
                         {"test-zero-step-crash", "test-trivial-success"})
        self.assertEqual({t.name for t in clean} - {t.name for t in variant}, {"test-timeout-hit"})
        before = miner.evaluate(full, fixtures.library(), 3)
        after = miner.evaluate(clean, fixtures.library(), 3)
        self.assertNotEqual(before.coverage, after.coverage)
        self.assertNotEqual(before.recall, after.recall)
        extra = (miner.Trace("nonzero-error", ("click", "nav"), "error"),
                 miner.Trace("zero-natural-failure", (), "failure"))
        self.assertEqual(miner.filter_traces(extra, "Exclude-errors"), extra[1:])

    def test_false_positive_explicitly_counted(self):
        trace = next(t for t in fixtures.TEST if t.name == "test-false-positive")
        report = miner.early_stop(trace.steps, fixtures.library(), 3)
        self.assertEqual(report.verdict, miner.Verdict.STOP_AND_REPORT)
        self.assertEqual(report.matches[0].positions, (0, 1, 2))
        self.assertEqual(report.observed_steps, 3)
        metrics = miner.evaluate((trace,), fixtures.library(), 3)
        self.assertEqual((metrics.tp, metrics.fp), (0, 1))
        self.assertLess(metrics.precision, 1)

    def test_unmatched_empty_timeout_never_success(self):
        self.assertEqual(miner.decide((), fixtures.library()).verdict, miner.Verdict.UNMATCHED)
        self.assertEqual(miner.decide(("type",), fixtures.library()).verdict, miner.Verdict.UNMATCHED)
        expired = miner.decide(("click", "click", "nav"), fixtures.library(), timed_out=True)
        self.assertEqual(expired.verdict, miner.Verdict.TIMEOUT)
        self.assertEqual(expired.matches, ())
        self.assertEqual(miner.early_stop(("click", "click", "nav"), fixtures.library(), 2).verdict,
                         miner.Verdict.UNMATCHED)
        self.assertEqual(miner.evaluate((), (), 3), miner.Metrics(0, 0, 0, 0, 0, 0, 0, 0))

    def test_no_permission_path_or_public_names(self):
        self.assertEqual({v.value for v in miner.Verdict},
                         {"STOP_AND_REPORT", "UNMATCHED", "TIMEOUT"})
        forbidden = ("allow", "approve", "success_on_unmatched", "release", "certificate", "gate_to_allow")
        tree = ast.parse((HERE / "miner.py").read_text())
        names = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
        names += [n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
        for name in names:
            self.assertFalse(any(word in name.lower() for word in forbidden), name)
        for path in IMPLEMENTATION:
            self.assertNotIn('"ALLOW"', (HERE / path).read_text())


class HygieneEvidenceTests(unittest.TestCase):
    def test_ast_import_allowlist_and_no_dynamic_execution(self):
        permitted = {"dataclasses", "enum", "json", "miner"}
        for filename in IMPLEMENTATION:
            tree = ast.parse((HERE / filename).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(a.name in permitted for a in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, permitted)
                    self.assertEqual(node.level, 0)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"exec", "eval", "compile", "__import__", "open"})

    def test_implementation_string_bans(self):
        needles = ("miniwob", "huggingface", "hugging face", "openai_api_key", "anthropic_api_key",
                   "xai_api_key", "inspect_ai", "two-ledger", "two_ledger", "hmac-manifest",
                   "hmac_manifest", "voting", "ensemble", "more-agents-reliability",
                   "blast-radius", "overseer-flip", "sqlite3", "docker", "feishu", "nats",
                   "requests", "urllib", "http://", "https://", "socket", "subprocess")
        for filename in IMPLEMENTATION:
            source = (HERE / filename).read_text().lower()
            for needle in needles:
                self.assertNotIn(needle, source, (filename, needle))

    def test_paper_numbers_distinct_non_targets_not_implementation_or_readme(self):
        evidence = json.loads((HERE / "paper_evidence.json").read_text())
        hygiene = evidence["number_hygiene"]
        self.assertTrue(hygiene["not_targets"])
        self.assertTrue(hygiene["not_reproduced"])
        quantities = {q["value"]: q for q in hygiene["quantities"]}
        self.assertEqual(set(quantities), {"0.717", "88%", "26.3%", "0.380"})
        self.assertEqual(len({q["kind"] for q in quantities.values()}), 4)
        self.assertIn("balanced", quantities["0.717"]["configuration"])
        self.assertIn("Not best across all K", quantities["0.717"]["caveat"])
        self.assertIn("Not high-precision policy recall", quantities["88%"]["caveat"])
        self.assertIn("tokens saved", quantities["26.3%"]["kind"])
        self.assertEqual(quantities["0.380"]["kind"], "policy recall")
        for filename in (*IMPLEMENTATION, "README.md"):
            source = (HERE / filename).read_text()
            for needle in quantities:
                self.assertNotIn(needle, source)
            for forbidden in ("we reproduce", "reproduced results:", "universally guarantees"):
                self.assertNotIn(forbidden, source.lower())

    def test_short_attributed_offline_evidence(self):
        evidence = json.loads((HERE / "paper_evidence.json").read_text())
        self.assertEqual(evidence["authors"], ["Sergio Talavera", "Magdalini Eirinaki"])
        self.assertEqual(evidence["version"], "2611.04142v1")
        self.assertEqual(evidence["license_line"], "License: CC BY-NC-SA 4.0")
        self.assertTrue(evidence["license_found_in_html"])
        self.assertIsNone(evidence["upstream_code_pin"])
        self.assertRegex(evidence["html_sha256"], r"^[a-f0-9]{64}$")
        excerpts = evidence["html_excerpts"]
        self.assertLess(sum(len(e["text"].split()) for e in excerpts), 100)
        for excerpt in excerpts:
            self.assertTrue(excerpt["found_after_tag_strip_whitespace_collapse"])
            self.assertTrue(excerpt["text"].isascii())
            self.assertTrue(excerpt["section"].startswith(("2 ", "3 ")))
        stored = " ".join(e["text"] for e in excerpts)
        for checked in ("ordered subsequences (not necessarily contiguous)",
                        "exactly the same set of traces", "errors and timeouts both removed",
                        "single-step successes", "avoids the latter by design"):
            self.assertIn(checked, stored)

    def test_readme_scope_attribution_and_day_entry_without_day_file_dependency(self):
        source = (HERE / "README.md").read_text()
        for phrase in ("KEEP Top", "paper-method only", "method-cite", "Not Team OS law",
                       "not a reproduction", "Sergio Talavera", "Magdalini Eirinaki",
                       "CC BY-NC-SA 4.0", "No upstream code pin", "UNVERIFIED",
                       "synthetic", "not universal laws", "w16-3"):
            self.assertIn(phrase.lower(), source.lower())
        self.assertIn("not declared verified", source)
        notice = (HERE / "NOTICE").read_text()
        self.assertIn("not relicensed as MIT", notice)
        self.assertIn("No upstream code pin", notice)


if __name__ == "__main__":
    unittest.main()
