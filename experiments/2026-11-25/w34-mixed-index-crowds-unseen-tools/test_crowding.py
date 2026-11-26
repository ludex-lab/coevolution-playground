"""Tests for crowding.py. Expected values are written out here from the fixture, not read from module constants.
The one declared exception to "no test reads source files" is ForbiddenWordTests, which VERDICT C8 requires: it
reads this folder's .py files as plain text data and imports nothing from them."""

import io
import json
import os
import re
import subprocess
import sys
import unittest

import crowding

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "fixtures", "main.json")
BAD = os.path.join(HERE, "fixtures", "bad")
DENY_LINE = re.compile(r"DENY [a-z_]+: \S[^\n]*\n\Z")
QUERY = "when is high water at the harbour on the coast this weekend for sailing"
BAD_CODES = {
    "not_json": "not_json", "duplicate_key": "duplicate_key", "unknown_field": "unknown_field",
    "missing_catalog": "missing_field", "missing_k": "missing_field", "k_zero": "bad_k", "k_bool": "bad_k",
    "k_float": "bad_type", "k_over_catalog": "bad_k", "unknown_tool": "unknown_tool",
    "duplicate_tool_id": "duplicate_id", "split_absent": "bad_split", "split_unknown": "bad_split",
    "heldout_pool_labels": "heldout_leak", "heldout_pool_names": "heldout_leak", "on_expiry_other": "bad_on_expiry",
    "n2_overlaps": "bad_control", "missing_control": "missing_role", "sweep_flip_out_of_range": "bad_sweep",
    "nan_constant": "bad_type", "gold_tool_id_list": "bad_type",
}


def raw():
    with open(MAIN) as fh:
        return json.load(fh)


def deny_code(root):
    try:
        crowding.validate(root)
    except crowding.Deny as e:
        return e.code
    return None


def cli(*args):
    out, err = io.StringIO(), io.StringIO()
    rc = crowding.main(["crowding.py"] + list(args), out, err)
    return rc, out.getvalue(), err.getvalue()


def result(root=None):
    return crowding.run(crowding.validate(raw() if root is None else root))


def row(res, qid):
    found = [r for r in res["rows"] if r.get("id") == qid]
    return found[0] if found else {}


class BoundaryFirstTests(unittest.TestCase):
    def test_exact_tie_at_k_boundary_uses_kind_then_id(self):
        catalog = [{"id": "zeta", "description": "red"}, {"id": "beta", "description": "red"},
                   {"id": "alpha", "description": "blue"}]
        exp = [{"id": "aa", "text": "red", "gold_tool_id": "alpha"}]
        # three items score 1: descriptions beta, zeta (kind 0, by id), then experience aa (kind 1)
        self.assertEqual(crowding.arm_mixed("red", catalog, exp, 2), ["beta", "zeta"])
        self.assertEqual(crowding.arm_mixed("red", catalog, exp, 3), ["beta", "zeta", "alpha"])

    def test_score_is_shared_distinct_token_count_not_jaccard(self):
        catalog = [{"id": "long", "description": "red blue " + "pad " * 40}, {"id": "short", "description": "red"}]
        self.assertEqual(crowding.arm_separate("red blue", catalog, [], 1), ["long"])

    def test_tokens_lowercase_alnum_runs(self):
        self.assertEqual(crowding.tokens("Tide-times, at 9AM!"), {"tide", "times", "at", "9am"})


class BudgetTests(unittest.TestCase):
    def test_both_arms_return_exactly_k_distinct(self):
        for r in result()["rows"]:
            self.assertEqual((len(r.get("a", [])), len(set(r.get("a", [])))), (3, 3), r.get("id"))
            self.assertEqual((len(r.get("b", [])), len(set(r.get("b", [])))), (3, 3), r.get("id"))

    def test_mixed_arm_skips_repeated_tools(self):
        catalog = [{"id": "w", "description": "x"}, {"id": "t", "description": "q"}, {"id": "m", "description": "y"}]
        exp = [{"id": "e1", "text": "q a b", "gold_tool_id": "w"}, {"id": "e2", "text": "q a c", "gold_tool_id": "w"}]
        self.assertEqual(crowding.arm_mixed("q a b c", catalog, exp, 3), ["w", "t", "m"])

    def test_unequal_counts_are_unequal_budget(self):
        self.assertFalse(crowding.budget_ok(["w"], ["t", "w", "m"], 3))
        self.assertFalse(crowding.budget_ok(["w", "w", "m"], ["t", "w", "m"], 3))
        self.assertTrue(crowding.budget_ok(["w", "t", "m"], ["t", "w", "m"], 3))


class ControlTests(unittest.TestCase):
    def test_n1_empty_pool_arms_identical(self):
        r = row(result(), "q_n1")
        self.assertEqual(r.get("a"), ["tide", "weather", "flights"])
        self.assertEqual(r.get("a"), r.get("b"))

    def test_n2_nonoverlap_pool_heldout_gold_still_in_mixed(self):
        r = row(result(), "q_n2")
        self.assertEqual(r.get("a"), ["tide", "weather", "flights"])
        self.assertTrue(r.get("holds"))

    def test_n3_labeled_gold_in_mixed(self):
        r = row(result(), "q_n3")
        self.assertEqual(r.get("a"), ["weather", "flights", "hotels"])
        self.assertTrue(r.get("holds"))

    def test_criterion_a_fails_when_a_control_fails(self):
        root = raw()
        # make n3 fail: its request now matches nothing in the weather experience or description
        root["queries"][3]["text"] = "zzz"
        res = result(root)
        self.assertTrue(row(res, "q_crowd").get("holds"))
        self.assertFalse(res["controls"])
        self.assertFalse(res["criterion_a"])
        self.assertEqual(res["gate"], "FAIL")


class CrowdingTests(unittest.TestCase):
    def test_heldout_crowding_mixed_omits_separate_includes(self):
        r = row(result(), "q_crowd")
        self.assertEqual(r.get("a"), ["weather", "flights", "hotels"])
        self.assertEqual(r.get("b"), ["tide", "weather", "flights"])
        self.assertEqual(r.get("split"), "heldout")

    def test_leaky_row_includes_gold_and_is_its_own_row(self):
        res = result()
        r = row(res, "q_leaky")
        self.assertEqual((r.get("split"), r.get("a", [None])[0]), ("leaky", "tide"))
        self.assertTrue(res["criterion_b"])

    def test_report_prints_split_rows_apart(self):
        rc, out, err = cli(MAIN)
        held, leaky = out.split("## Leaky split")
        self.assertIn("| q_crowd |", held)
        self.assertNotIn("| q_leaky |", held)
        self.assertIn("| q_leaky |", leaky.split("## Client sweep")[0])
        self.assertNotIn("%", out)

    def test_main_fixture_gate_pass(self):
        rc, out, err = cli(MAIN)
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("gate: PASS", out)
        self.assertIn("on_expiry: DENY", out)


class SweepTests(unittest.TestCase):
    def test_flip_at_four_clients_matches_rule(self):
        sw = result()["sweep"]
        self.assertEqual([s.get("gold_in_a") for s in sw["steps"]], [True, True, True, False, False])
        self.assertEqual([s.get("used_tools_outranking") for s in sw["steps"]], [1, 1, 2, 3, 4])
        self.assertEqual((sw["observed"], sw["rule"], sw["flip_at"]), (4, 4, 4))

    def test_wrong_preregistered_flip_fails_gate(self):
        root = raw()
        root["sweep"]["flip_at"] = 3
        res = result(root)
        self.assertFalse(res["sweep"]["holds"])
        self.assertEqual(res["gate"], "FAIL")


class DenyTests(unittest.TestCase):
    def test_leaky_pool_declared_heldout_is_deny(self):
        root = raw()
        root["pools"][3]["split"] = "heldout"
        self.assertEqual(deny_code(root), "heldout_leak")

    def test_heldout_pool_naming_by_declared_name_token_is_deny(self):
        root = raw()
        root["catalog"][5]["name"] = "Harbour clock"
        root["pools"][0]["experience"].append(
            {"id": "e9", "text": "is the clock right", "gold_tool_id": "maps", "client_id": "c5"})
        self.assertEqual(deny_code(root), "heldout_leak")

    def test_leaky_split_may_label_heldout(self):
        self.assertIsNone(deny_code(raw()))

    def test_bad_fixtures_deny_exit_2_one_line(self):
        names = sorted(f[:-5] for f in os.listdir(BAD) if f.endswith(".json"))
        self.assertEqual(names, sorted(BAD_CODES))
        for name in names:
            path = os.path.join(BAD, name + ".json")
            try:
                crowding.load(path)
                code = None
            except crowding.Deny as e:
                code = e.code
            self.assertEqual(code, BAD_CODES[name], name)
            if code is None:
                continue
            rc, out, err = cli(path)
            self.assertEqual(rc, 2, name)
            self.assertEqual(out, "", name)
            self.assertEqual(err.count("\n"), 1, name)
            self.assertTrue(err.startswith("DENY %s: " % BAD_CODES[name]), name)
            self.assertRegex(err, DENY_LINE)

    def test_missing_file_and_usage_deny(self):
        rc, out, err = cli(os.path.join(BAD, "no_such_file.json"))
        self.assertEqual((rc, out), (2, ""))
        self.assertTrue(err.startswith("DENY unreadable: "))
        self.assertRegex(err, DENY_LINE)
        rc, out, err = cli()
        self.assertEqual((rc, out), (2, ""))
        self.assertRegex(err, DENY_LINE)


class SubprocessTests(unittest.TestCase):
    def test_cli_json_twice_identical(self):
        cmd = [sys.executable, "-B", os.path.join(HERE, "crowding.py"), "--json", MAIN]
        a = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        b = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        self.assertEqual((a.returncode, a.stderr), (0, ""))
        self.assertEqual(a.stdout, b.stdout)
        self.assertEqual(json.loads(a.stdout)["gate"], "PASS")


class ForbiddenWordTests(unittest.TestCase):
    """VERDICT C8: the folder's own .py files, read as text data, contain none of three words in any case."""

    def test_py_files_free_of_forbidden_words(self):
        words = ["al" + "low", "ap" + "prove", "per" + "mit"]
        pattern = re.compile("|".join(words), re.IGNORECASE)
        files = sorted(f for f in os.listdir(HERE) if f.endswith(".py"))
        self.assertGreaterEqual(len(files), 4)
        for name in files:
            with open(os.path.join(HERE, name), encoding="utf-8") as fh:
                self.assertIsNone(pattern.search(fh.read()), name)


if __name__ == "__main__":
    unittest.main()
