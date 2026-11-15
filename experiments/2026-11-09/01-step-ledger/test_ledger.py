"""Offline unittest suite for the two-sided step-record sketch."""

import ast
import hashlib
import html
import json
import math
import os
import re
import unittest

import fixtures
import ledger
from ledger import Fault

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_HTML = "/tmp/mb1109-2611.08144.html"
PIN = "0b4a1417854289ecfb25607bc6c51eb0dc586bdd"


def _read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def normalize(raw):
    """Same normalization as documented in paper_evidence.json."""
    t = re.sub(r"<script\b.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r"<style\b.*?</style>", "", t, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r"<math\b.*?</math>", "", t, flags=re.DOTALL | re.IGNORECASE)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t)


def _fx(fid):
    for fx in fixtures.FIXTURES:
        if fx["id"] == fid:
            return fx
    raise KeyError(fid)


class CleanRun(unittest.TestCase):

    def test_clean_records_agree(self):
        res = ledger.run(fixtures.N_ENVS, fixtures.N_EPISODES)
        self.assertEqual(ledger.detect(res), ("agree", None))
        self.assertEqual(len(res.env_records), len(res.trainer_records))

    def test_run_is_deterministic(self):
        a = ledger.run(2, 10)
        b = ledger.run(2, 10)
        self.assertEqual(a.env_records, b.env_records)
        self.assertEqual(a.curve, b.curve)

    def test_clean_run_ends_both_ways(self):
        res = ledger.run(2, 10)
        ends = [r for r in res.env_records if r.terminated or r.truncated]
        self.assertTrue(any(r.terminated for r in ends))
        self.assertTrue(any(r.truncated for r in ends))

    def test_clean_curve_rises_and_passes_baseline(self):
        res = ledger.run(2, 10)
        status, g = ledger.gain_check(res.curve)
        self.assertEqual(status, "pass")
        self.assertGreater(g, ledger.GAIN_THRESHOLD)

    def test_float16_round_changes_value(self):
        self.assertNotEqual(ledger.float16_round(0.1), 0.1)
        self.assertEqual(ledger.float16_round(0.5), 0.5)

    def test_unknown_fault_kind_rejected(self):
        with self.assertRaises(ValueError):
            ledger.Wire([], [Fault("nope", 0, 0, 0)])


class RequiredFaults(unittest.TestCase):

    def _check(self, fid):
        fx = _fx(fid)
        r = fixtures.run_fixture(fx)
        self.assertEqual(r["ledger"], "detect", fid)
        self.assertEqual(r["where"], fx["expect_where"], fid)
        f = fx["fault"]
        if f.env_id is not None:
            self.assertEqual(r["diff"].env_id, f.env_id)
            self.assertEqual(r["diff"].episode_id, f.episode_id)
        self.assertEqual(r["baseline"], fx["expect_baseline"], fid)
        return r

    def test_float16_observation(self):
        r = self._check("F1-float16-observation")
        d = r["diff"]
        self.assertEqual(d.trainer_value[0], ledger.float16_round(d.env_value[0]))
        self.assertNotEqual(d.trainer_value[0], d.env_value[0])

    def test_float16_reward(self):
        r = self._check("F2-float16-reward")
        self.assertEqual(r["diff"].trainer_value,
                         ledger.float16_round(r["diff"].env_value))

    def test_stale_reward(self):
        r = self._check("F3-stale-reward")
        clean = ledger.run(2, 10)
        prev = [x for x in clean.env_records
                if (x.env_id, x.episode_id, x.step_id) == (1, 8, 4)][0]
        self.assertEqual(r["diff"].trainer_value, prev.reward)

    def test_terminated_truncated_swap(self):
        r = self._check("F4-terminated-truncated-swap")
        clean = ledger.run(2, 10)
        end = [x for x in clean.env_records if x.env_id == 1 and
               x.episode_id == 8 and (x.terminated or x.truncated)]
        self.assertEqual(len(end), 1)
        self.assertEqual(r["diff"].step_id, end[0].step_id)
        self.assertEqual((r["diff"].env_value, r["diff"].trainer_value), (True, False))

    def test_skipped_step_filled_in(self):
        r = self._check("F5-skipped-step-filled-in")
        self.assertEqual(r["diff"].env_value, ledger.MISSING)
        res = ledger.run(2, 10, [_fx("F5-skipped-step-filled-in")["fault"]])
        ids = [x.step_id for x in res.trainer_records
               if x.env_id == 1 and x.episode_id == 8]
        self.assertEqual(ids, list(range(len(ids))))  # trainer stream contiguous

    def test_zeroed_action_extra(self):
        self._check("F6-zeroed-action")

    def test_every_reward_zeroed_extra(self):
        self._check("F7-every-reward-zeroed")


class BaselineVsLedger(unittest.TestCase):

    def test_designed_outcome(self):
        results = fixtures.run_all()
        faulted = [r for r in results if r["id"] != "F0-clean"]
        self.assertEqual(len(faulted), 7)
        self.assertEqual(sum(r["ledger"] == "detect" for r in faulted), 7)
        self.assertEqual([r["id"] for r in faulted if r["baseline"] == "detect"],
                         ["F7-every-reward-zeroed"])

    def test_baseline_misses_every_required_fault(self):
        for fid in fixtures.REQUIRED_FAULT_IDS:
            r = fixtures.run_fixture(_fx(fid))
            self.assertEqual(r["baseline"], "pass", fid)
            self.assertEqual(r["ledger"], "detect", fid)

    def test_overhead_finite_positive(self):
        base, led, ratio = ledger.measure_overhead(repeats=3)
        self.assertGreater(base, 0)
        self.assertGreater(led, 0)
        self.assertTrue(math.isfinite(ratio))
        self.assertGreater(ratio, 0)


class FixturesRunner(unittest.TestCase):

    def test_all_fixtures_match(self):
        for r, fx in zip(fixtures.run_all(), fixtures.FIXTURES):
            self.assertEqual(r["ledger"], fx["expect_ledger"], fx["id"])
            self.assertEqual(r["where"], fx["expect_where"], fx["id"])
            self.assertEqual(r["baseline"], fx["expect_baseline"], fx["id"])

    def test_summary(self):
        s = fixtures.summary(repeats=2)
        self.assertEqual((s["faults"], s["ledger_detected"],
                          s["baseline_detected"], s["localised"]), (7, 7, 1, 7))

    def test_main_returns_zero(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fixtures.main(), 0)


class PaperEvidence(unittest.TestCase):

    def setUp(self):
        self.ev = json.loads(_read("paper_evidence.json"))

    def test_pins_recorded(self):
        pin = self.ev["implementation_pin"]
        self.assertEqual(pin["commit"], PIN)
        self.assertEqual(pin["licence"], "Apache-2.0")
        self.assertEqual(pin["url"], "https://github.com/PlugRL/step-ledger")
        self.assertIn("cite-only", pin["pin_scope"])
        p = self.ev["paper"]
        self.assertEqual(p["licence"], "CC BY 4.0")
        self.assertEqual(p["licence_url"], "https://creativecommons.org/licenses/by/4.0/")
        self.assertIn("5 Nov 2026", p["submitted_display"])

    def test_excerpts_found(self):
        if not os.path.exists(PAPER_HTML):
            self.skipTest("paper HTML cache not present")
        with open(PAPER_HTML, "rb") as fh:
            raw = fh.read()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), self.ev["fetched"]["html_sha256"])
        n = normalize(raw.decode("utf-8"))
        self.assertEqual(len(n), self.ev["normalization"]["normalized_chars"])
        self.assertGreaterEqual(len(self.ev["excerpts"]), 8)
        for e in self.ev["excerpts"]:
            s, o = e["excerpt"], e["normalized_offset"]
            self.assertEqual(n[o:o + e["chars"]], s, e["id"])
            self.assertEqual(o + e["chars"], e["end_offset_exclusive"])
            self.assertEqual(n.count(s), e["occurrences"], e["id"])
            w = n[max(0, o - 64):min(len(n), o + len(s) + 64)]
            self.assertEqual(hashlib.sha256(w.encode("utf-8")).hexdigest(),
                             e["source_window_sha256"], e["id"])


BANNED_EVERYWHERE = ["KEEP", "CloudAgent", "Smith", "Two-" + "Ledger", "2611." + "06989"]
PAPER_FIGURES = ["one run in ten", "1 of 21", "at most 21%", "3%", "189", "207",
                 "1,060", "1060", "728", "723", "63 runs", "23 faults", "500 above"]
IMPL_FILES = ["ledger.py", "fixtures.py"]
PUBLIC_FILES = ["README.md", "NOTICE"]


class Hygiene(unittest.TestCase):

    def test_banned_strings_absent(self):
        for name in PUBLIC_FILES + IMPL_FILES + ["paper_evidence.json"]:
            text = _read(name)
            for needle in BANNED_EVERYWHERE:
                self.assertNotIn(needle, text, (name, needle))

    def test_paper_figures_absent(self):
        for name in PUBLIC_FILES + IMPL_FILES:
            text = _read(name)
            for needle in PAPER_FIGURES:
                self.assertNotIn(needle, text, (name, needle))

    def test_readme_standing_notes(self):
        r = _read("README.md")
        for needle in ["method sketch", "not a reproduction of the paper's",
                       "not Team OS law", "not village law",
                       "https://arxiv.org/abs/2611.08144",
                       "https://arxiv.org/html/2611.08144",
                       "experiments/2026-11-09/01-step-ledger/", PIN,
                       "CC BY 4.0", "Apache-2.0",
                       "python3 -m unittest test_ledger.py -v", "python3 fixtures.py",
                       "## Not implemented", "## UNVERIFIED", "## Builder reflection",
                       "Ludex", "Cody", "Naru"]:
            self.assertIn(needle, r, needle)
        self.assertEqual(r.rstrip("\n").splitlines()[-1],
                         "Implementation may be complete; it is not declared verified.")
        for needle in ["Ork", "Checker", "pull request", "merge"]:
            self.assertNotIn(needle, r, needle)

    def test_notice(self):
        t = _read("NOTICE")
        for needle in ["2611.08144", "Gou", "Lu", "CC BY 4.0", PIN,
                       "Apache License, Version 2.0", "not cloned",
                       "clean-room", "synthetic"]:
            self.assertIn(needle, t, needle)

    def test_no_test_reads_parent_index(self):
        src = _read("test_ledger.py")
        self.assertNotIn("day-" + "README", src)

    def test_imports_stdlib_only(self):
        allowed = {"struct", "time", "collections", "math", "ledger"}
        for name in IMPL_FILES:
            tree = ast.parse(_read(name))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [(node.module or "").split(".")[0]]
                else:
                    continue
                for m in mods:
                    self.assertIn(m, allowed, (name, m))

    def test_vocabulary(self):
        for name in IMPL_FILES:
            tree = ast.parse(_read(name))
            idents = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    idents.add(node.name)
                elif isinstance(node, ast.Name):
                    idents.add(node.id)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    idents.add(node.value)
            for ident in idents:
                low = ident.lower()
                for bad in ("allow", "approve", "permit"):
                    self.assertNotIn(bad, low, (name, ident))
        self.assertTrue(callable(ledger.detect))
        self.assertTrue(callable(ledger.compare_records))


if __name__ == "__main__":
    unittest.main()
