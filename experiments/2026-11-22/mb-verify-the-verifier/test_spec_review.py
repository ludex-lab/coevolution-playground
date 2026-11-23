"""Tests for spec_review. Run: python3 -B -m unittest"""

import copy
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout

import spec_review as sr

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
TITLE = ("Verify the Verifier: Specification-Grounded LLM Cross-Checking for Bugs That Escape UVM Scoreboards")
FOOTER = "Do not merge experiment PRs without Ork review."

# Expected error code for every bad fixture.
BAD_CODES = {
    'bad_bad_case_id.json': 'bad_id',
    'bad_bad_clause_id.json': 'bad_id',
    'bad_bad_op.json': 'bad_op',
    'bad_bad_plant.json': 'bad_plant',
    'bad_bad_version.json': 'bad_version',
    'bad_bidi_override.json': 'bad_text',
    'bad_bool_depth.json': 'wrong_type',
    'bad_bool_value.json': 'wrong_type',
    'bad_capacity_without_depth.json': 'bad_spec',
    'bad_case_unknown_key.json': 'unknown_key',
    'bad_control_char.json': 'bad_text',
    'bad_deep_nesting.json': 'not_json',
    'bad_depth_on_wrong_clause.json': 'bad_spec',
    'bad_depth_zero.json': 'bad_value',
    'bad_duplicate_case.json': 'duplicate_case',
    'bad_duplicate_case_nfc.json': 'duplicate_case',
    'bad_duplicate_clause_id.json': 'bad_spec',
    'bad_duplicate_compare_field.json': 'bad_compare',
    'bad_duplicate_key.json': 'duplicate_key',
    'bad_duplicate_rule.json': 'bad_spec',
    'bad_edge_space.json': 'bad_text',
    'bad_empty_compare.json': 'bad_compare',
    'bad_empty_file.json': 'not_json',
    'bad_empty_stimulus.json': 'too_many',
    'bad_empty_text.json': 'wrong_type',
    'bad_exponent_value.json': 'wrong_type',
    'bad_float_value.json': 'wrong_type',
    'bad_four_clauses.json': 'bad_spec',
    'bad_giant_int_digits.json': 'not_json',
    'bad_huge_int.json': 'bad_value',
    'bad_infinity.json': 'bad_number',
    'bad_invalid_utf8.json': 'bad_encoding',
    'bad_lone_surrogate.json': 'bad_text',
    'bad_missing_key.json': 'missing_key',
    'bad_nan.json': 'bad_number',
    'bad_negative_infinity.json': 'bad_number',
    'bad_negative_value.json': 'bad_value',
    'bad_no_break_space.json': 'bad_text',
    'bad_no_cases.json': 'too_many',
    'bad_not_json.json': 'not_json',
    'bad_pop_with_value.json': 'unknown_key',
    'bad_push_without_value.json': 'missing_key',
    'bad_step_not_object.json': 'wrong_type',
    'bad_string_value.json': 'wrong_type',
    'bad_tab_in_text.json': 'bad_text',
    'bad_text_too_long.json': 'wrong_type',
    'bad_too_large.json': 'too_large',
    'bad_too_many_cases.json': 'too_many',
    'bad_too_many_steps.json': 'too_many',
    'bad_top_level_list.json': 'wrong_type',
    'bad_trailing_comma.json': 'not_json',
    'bad_unknown_compare_field.json': 'bad_compare',
    'bad_unknown_golden.json': 'unknown_variant',
    'bad_unknown_key.json': 'unknown_key',
    'bad_unknown_rule.json': 'unknown_rule',
    'bad_unknown_variant.json': 'unknown_variant',
    'bad_utf16.json': 'bad_encoding',
    'bad_value_out_of_range.json': 'bad_value',
    'bad_zero_width_space.json': 'bad_text',
}


def load(name="main"):
    return sr.load_fixture(os.path.join(FIX, name + ".json"))


def raw(name="main"):
    with open(os.path.join(FIX, name + ".json"), "r", encoding="utf-8") as fh:
        return json.load(fh)


def rows(fx=None):
    return {r["id"]: r for r in sr.run(fx or load())["rows"]}


def trace(variant, stimulus, depth=4):
    return sr.trace_view(sr.simulate(variant, depth, stimulus))


def push(*values):
    return [{"op": "push", "value": v} for v in values]


POP = {"op": "pop"}


def reason_set(result):
    return {(x["clause"], x["code"]) for x in result["reasons"]}


class DesignTests(unittest.TestCase):

    def test_correct_fifo_behaviour(self):
        t = sr.simulate("correct", 2, push(1, 2, 3) + [POP, POP, POP])
        self.assertEqual([s["out"].get("ok") for s in t[:3]], [True, True, False])
        self.assertEqual([s["out"].get("value") for s in t[3:]], [1, 2, None])
        self.assertEqual([s["out"]["served"] for s in t[3:]], [True, True, False])
        self.assertEqual([s["out"]["count"] for s in t], [1, 2, 2, 1, 0, 0])
        self.assertEqual([s["out"]["full"] for s in t], [False, True, True, False, False, False])
        self.assertEqual([s["out"]["empty"] for s in t], [False, False, False, False, True, True])

    def test_overwrite_variant_drops_the_oldest(self):
        t = sr.simulate("overwrite_when_full", 2, push(1, 2, 3) + [POP, POP])
        self.assertTrue(t[2]["out"]["ok"])
        self.assertEqual([s["out"]["value"] for s in t[3:]], [2, 3])

    def test_lifo_variant_pops_the_newest(self):
        t = sr.simulate("lifo", 4, push(1, 2) + [POP, POP])
        self.assertEqual([s["out"]["value"] for s in t[2:]], [2, 1])

    def test_early_flag_variant(self):
        t = sr.simulate("full_flag_early", 4, push(1, 2, 3, 4))
        self.assertEqual([s["out"]["full"] for s in t], [False, False, True, True])

    def test_underflow_variant_returns_stale_data(self):
        t = sr.simulate("underflow_returns_data", 4, push(7) + [POP, POP])
        self.assertEqual((t[2]["out"]["served"], t[2]["out"]["value"], t[2]["out"]["count"]), (True, 7, 0))

    def test_underflow_variant_on_a_never_used_fifo(self):
        t = sr.simulate("underflow_returns_data", 4, [POP])
        self.assertEqual((t[0]["out"]["served"], t[0]["out"]["value"]), (True, 0))


class ScoreboardTests(unittest.TestCase):

    def case(self, dut, golden, compare=sr.FIELDS, stimulus=None):
        return {"dut": dut, "golden": golden, "compare": list(compare),
                "stimulus": stimulus or push(10, 20, 30, 40, 50) + [POP] * 5}

    def test_shared_bug_passes(self):
        for v in sr.VARIANTS:
            self.assertEqual(sr.scoreboard(self.case(v, v), 4)["verdict"], "PASS", v)

    def test_different_models_fail_on_the_first_compared_field(self):
        self.assertEqual(sr.scoreboard(self.case("lifo", "correct"), 4),
                         {"verdict": "FAIL", "step": 6, "field": "value"})
        self.assertEqual(sr.scoreboard(self.case("overwrite_when_full", "correct"), 4),
                         {"verdict": "FAIL", "step": 5, "field": "ok"})

    def test_unwatched_field_is_never_compared(self):
        self.assertEqual(sr.scoreboard(self.case("full_flag_early", "correct", ["ok", "value"]), 4)["verdict"], "PASS")
        self.assertEqual(sr.scoreboard(self.case("full_flag_early", "correct", ["full"]), 4),
                         {"verdict": "FAIL", "step": 3, "field": "full"})

    def test_scoreboard_never_reads_the_spec(self):
        self.assertNotIn("spec", sr.scoreboard.__code__.co_varnames)


class ClauseAuditTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.spec = load()["spec"]

    def audit(self, variant, stimulus):
        return sr.clause_audit(self.spec, trace(variant, stimulus))

    def test_correct_design_passes_every_clause(self):
        for stim in (push(1, 2, 3, 4, 5) + [POP] * 6, [POP, POP], push(9) + [POP] + push(8, 7) + [POP, POP, POP]):
            self.assertEqual(self.audit("correct", stim), {"verdict": "PASS", "reasons": []})

    def test_each_bug_maps_to_its_clause(self):
        fd = push(10, 20, 30, 40, 50) + [POP] * 5
        self.assertEqual(reason_set(self.audit("overwrite_when_full", fd)),
                         {("S1", "push_accepted_when_full"), ("S2", "pop_out_of_order")})
        self.assertEqual(reason_set(self.audit("lifo", fd)), {("S2", "pop_out_of_order")})
        self.assertEqual(reason_set(self.audit("full_flag_early", fd)), {("S5", "full_flag_wrong")})
        self.assertEqual(reason_set(self.audit("underflow_returns_data", fd)), {("S3", "pop_when_empty_returned_data")})

    def test_hand_written_traces_reach_every_reason_code(self):
        def step(op, given=None, **out):
            return {"op": op, "value": given, "out": out}
        cases = {
            ("S1", "push_refused_when_not_full"): [step("push", 1, ok=False, count=0, full=False, empty=True)],
            ("S2", "pop_not_served_when_not_empty"): [step("push", 1, ok=True, count=1, full=False, empty=False),
                                                     step("pop", served=False, value=None, count=0, full=False,
                                                          empty=True)],
            ("S4", "count_mismatch"): [step("push", 1, ok=True, count=2, full=False, empty=False)],
            ("S5", "empty_flag_wrong"): [step("push", 1, ok=True, count=1, full=False, empty=True)],
            ("S3", "pop_when_empty_returned_data"): [step("pop", served=False, value=5, count=0, full=False,
                                                          empty=True)],
        }
        for (clause, code), t in cases.items():
            self.assertIn((clause, code), reason_set(sr.clause_audit(self.spec, t)), code)
        every = {c for codes in sr.REASONS.values() for c in codes}
        self.assertEqual(len(every), 8)

    def test_reasons_carry_first_step_and_count(self):
        r = self.audit("lifo", push(10, 20, 30, 40, 50) + [POP] * 5)["reasons"]
        self.assertEqual(r, [{"clause": "S2", "rule": "order", "code": "pop_out_of_order", "first_step": 6,
                              "count": 4}])

    def test_reasons_are_ordered_by_first_step(self):
        r = self.audit("overwrite_when_full", push(10, 20, 30, 40, 50) + [POP] * 5)["reasons"]
        self.assertEqual([(x["clause"], x["first_step"]) for x in r], [("S1", 5), ("S2", 6)])

    def test_clause_ids_come_from_the_spec(self):
        spec = copy.deepcopy(self.spec)
        spec["order"]["id"] = "S7"
        r = sr.clause_audit(spec, trace("lifo", push(1, 2) + [POP, POP]))
        self.assertEqual(reason_set(r), {("S7", "pop_out_of_order")})

    def test_audit_uses_the_spec_depth_not_the_design_depth(self):
        spec = copy.deepcopy(self.spec)
        spec["capacity"]["depth"] = 3
        r = sr.clause_audit(spec, trace("correct", push(1, 2, 3, 4)))
        self.assertIn(("S1", "push_accepted_when_full"), reason_set(r))

    def test_audit_never_sees_the_golden_model_or_labels(self):
        view = trace("lifo", push(1) + [POP])
        self.assertEqual(sorted(view[0]), ["op", "out", "value"])
        self.assertEqual(sr.clause_audit.__code__.co_argcount, 2)
        r = sr.run(load())
        relabelled = load()
        for case in relabelled["cases"]:
            case["golden"] = "correct" if case["golden"] != "correct" else "lifo"
            case["planted"] = "clean"
        r2 = sr.run(relabelled)
        self.assertEqual([x["clause_audit"] for x in r["rows"]], [x["clause_audit"] for x in r2["rows"]])

    def test_view_is_a_copy(self):
        t = sr.simulate("correct", 4, push(1))
        v = sr.trace_view(t)
        v[0]["out"]["ok"] = False
        self.assertTrue(t[0]["out"]["ok"])


class DoneWhenTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = sr.run(load())
        cls.rows = {r["id"]: r for r in cls.result["rows"]}

    def test_a_escapes_pass_the_scoreboard_and_fail_a_clause(self):
        escapes = [r for r in self.result["rows"] if r["planted"] == "escape"]
        self.assertEqual(len(escapes), 3)
        for r in escapes:
            self.assertEqual((r["scoreboard"]["verdict"], r["clause_audit"]["verdict"]), ("PASS", "FAIL"), r["id"])
            for x in r["clause_audit"]["reasons"]:
                self.assertRegex(x["clause"], r"^S[1-5]$")

    def test_escape_reason_codes(self):
        self.assertEqual(reason_set(self.rows["escape_shared_overwrite"]["clause_audit"]),
                         {("S1", "push_accepted_when_full"), ("S2", "pop_out_of_order")})
        self.assertEqual(reason_set(self.rows["escape_shared_lifo"]["clause_audit"]), {("S2", "pop_out_of_order")})
        self.assertEqual(reason_set(self.rows["escape_unwatched_flag"]["clause_audit"]), {("S5", "full_flag_wrong")})

    def test_b_clean_cases_pass_both(self):
        clean = [r for r in self.result["rows"] if r["planted"] == "clean"]
        self.assertEqual(len(clean), 2)
        for r in clean:
            self.assertEqual((r["scoreboard"]["verdict"], r["clause_audit"]), ("PASS", {"verdict": "PASS", "reasons": []}))

    def test_c_real_fails_fail_both(self):
        self.assertEqual(self.rows["real_fail_underflow"]["scoreboard"], {"verdict": "FAIL", "step": 10, "field": "served"})
        self.assertEqual(reason_set(self.rows["real_fail_underflow"]["clause_audit"]),
                         {("S3", "pop_when_empty_returned_data")})
        self.assertEqual(self.rows["real_fail_lifo"]["scoreboard"], {"verdict": "FAIL", "step": 6, "field": "value"})
        self.assertEqual(reason_set(self.rows["real_fail_lifo"]["clause_audit"]), {("S2", "pop_out_of_order")})

    def test_summary_and_checks(self):
        self.assertEqual(self.result["summary"], {
            "cases": 7, "escapes_passed_by_scoreboard": "3/3", "escapes_failed_by_clause_audit": "3/3",
            "clean_failed_by_clause_audit": "0/2", "real_fails_failed_by_scoreboard": "2/2",
            "real_fails_failed_by_clause_audit": "2/2", "all_cases_match_their_plant": True})
        self.assertEqual(self.result["checks"], {
            "a_escapes_pass_scoreboard_and_fail_a_clause": True, "b_clean_cases_pass_both": True,
            "c_real_fails_fail_both": True, "d_offline": True})
        self.assertIs(self.result["network"], False)
        self.assertEqual(self.result["model_calls"], 0)

    def test_outcomes_follow_the_two_verdicts(self):
        self.assertEqual(sr.OUTCOMES, {("PASS", "FAIL"): "escape", ("PASS", "PASS"): "clean",
                                       ("FAIL", "FAIL"): "real_fail", ("FAIL", "PASS"): "scoreboard_only"})
        for r in self.result["rows"]:
            self.assertEqual(r["outcome"], r["planted"])
            self.assertTrue(r["matches_plant"])

    def test_a_mislabelled_plant_is_reported(self):
        fx = load()
        fx["cases"][0]["planted"] = "escape"
        r = sr.run(fx)
        self.assertFalse(r["rows"][0]["matches_plant"])
        self.assertFalse(r["summary"]["all_cases_match_their_plant"])
        self.assertFalse(r["checks"]["a_escapes_pass_scoreboard_and_fail_a_clause"])

    def test_a_check_with_no_cases_of_its_kind_is_false(self):
        fx = load()
        fx["cases"] = [c for c in fx["cases"] if c["planted"] != "real_fail"]
        self.assertFalse(sr.run(fx)["checks"]["c_real_fails_fail_both"])

    def test_a_fixed_golden_model_turns_escapes_into_real_fails(self):
        fx = load()
        for c in fx["cases"]:
            c["golden"] = "correct"
            c["compare"] = list(sr.FIELDS)
        by_id = {r["id"]: r for r in sr.run(fx)["rows"]}
        for cid in ("escape_shared_overwrite", "escape_shared_lifo", "escape_unwatched_flag"):
            self.assertEqual(by_id[cid]["outcome"], "real_fail", cid)

    def test_korean_fixtures_give_the_same_verdicts(self):
        def verdicts(fx):
            return [(r["planted"], r["scoreboard"], r["clause_audit"]) for r in sr.run(fx)["rows"]]
        self.assertEqual(verdicts(load("korean")), verdicts(load()))
        self.assertEqual(verdicts(load("korean_nfd")), verdicts(load()))
        self.assertEqual(load("korean_nfd")["spec"], load("korean")["spec"])


class LoaderTests(unittest.TestCase):

    def test_every_bad_fixture_has_its_code(self):
        names = sorted(n for n in os.listdir(FIX) if n.startswith("bad_"))
        self.assertEqual(names, sorted(BAD_CODES))
        for name in names:
            with self.assertRaises(sr.ReviewError, msg=name) as cm:
                sr.load_fixture(os.path.join(FIX, name))
            self.assertEqual(cm.exception.code, BAD_CODES[name], name)

    def test_valid_fixtures(self):
        self.assertEqual(sorted(n for n in os.listdir(FIX) if not n.startswith("bad_")),
                         ["korean.json", "korean_nfd.json", "main.json"])

    def test_bool_is_not_an_int(self):
        with self.assertRaises(sr.ReviewError) as cm:
            sr._int(True, "x", 0, 9)
        self.assertEqual(cm.exception.code, "wrong_type")

    def test_size_cap_boundary(self):
        self.assertEqual(sr.CAPS["file_bytes"]["limit"], sr.MAX_BYTES)
        for name, cap in sr.CAPS.items():
            self.assertEqual(cap["on_expiry"], "DENY", name)
        self.assertEqual(sr.ON_EXPIRY, "DENY")

    def test_step_cap_boundary(self):
        root = raw()
        root["cases"][0]["stimulus"] = [POP] * sr.CAPS["steps"]["limit"]
        self.assertEqual(len(sr.validate(root)["cases"][0]["stimulus"]), sr.CAPS["steps"]["limit"])

    def test_missing_file(self):
        with self.assertRaises(sr.ReviewError) as cm:
            sr.load_fixture(os.path.join(FIX, "no_such_file.json"))
        self.assertEqual(cm.exception.code, "unreadable")

    def test_text_is_nfc(self):
        self.assertEqual(load("korean_nfd")["spec"]["order"]["text"], load("korean")["spec"]["order"]["text"])


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = sr.main(["spec_review.py"] + args)
    return code, out.getvalue(), err.getvalue()


class CommandLineTests(unittest.TestCase):

    def test_bad_fixtures_exit_two_with_one_error_line(self):
        for name in sorted(BAD_CODES):
            code, out, err = run_cli([os.path.join(FIX, name)])
            self.assertEqual((code, out), (2, ""), name)
            self.assertEqual(len(err.splitlines()), 1, name)
            self.assertTrue(err.startswith("ERROR %s: " % BAD_CODES[name]), (name, err))
            self.assertIn("on_expiry DENY", err)

    def test_valid_fixtures_exit_zero(self):
        for name in ("main", "korean", "korean_nfd"):
            code, out, err = run_cli([os.path.join(FIX, name + ".json")])
            self.assertEqual((code, err), (0, ""), name)
            self.assertTrue(json.loads(out)["checks"]["b_clean_cases_pass_both"])

    def test_usage_errors(self):
        for args in ([], ["a", "b"]):
            code, out, err = run_cli(args)
            self.assertEqual((code, out, len(err.splitlines())), (2, "", 1))
            self.assertTrue(err.startswith("ERROR"))

    def test_subprocess_contract(self):
        p = subprocess.run([sys.executable, "-B", "spec_review.py", os.path.join("fixtures", "bad_nan.json")],
                           cwd=HERE, capture_output=True)
        self.assertEqual((p.returncode, p.stdout), (2, b""))
        self.assertEqual(len(p.stderr.splitlines()), 1)
        self.assertTrue(p.stderr.startswith(b"ERROR bad_number: "))
        p = subprocess.run([sys.executable, "-B", "spec_review.py", os.path.join("fixtures", "missing.json")],
                           cwd=HERE, capture_output=True)
        self.assertEqual((p.returncode, p.stdout, len(p.stderr.splitlines())), (2, b"", 1))


class DemoTests(unittest.TestCase):

    def demo(self):
        p = subprocess.run([sys.executable, "-B", "demo.py"], cwd=HERE, capture_output=True)
        self.assertEqual((p.returncode, p.stderr), (0, b""))
        return p.stdout

    def test_deterministic_and_matches_the_readme(self):
        a, b = self.demo(), self.demo()
        self.assertEqual(a, b)
        with open(os.path.join(HERE, "README.md"), "r", encoding="utf-8") as fh:
            self.assertIn(hashlib.sha256(a).hexdigest(), fh.read())

    def test_demo_says_no_model_call(self):
        text = self.demo().decode("utf-8")
        self.assertIn("no model call", text)
        self.assertIn("not model or real-world rates", text)


BANNED = ["al" + "low", "ke" + "ep", "cloud" + "agent", "smi" + "th", "chec" + "ker"]
PATHS = ["/" + "workspace", "/" + "tmp", "/" + "home"]
MECHANISM = [r"fei" + "shu", r"sql" + "ite", r"hm" + "ac", r"dae" + "mon", r"grok" + "ki", r"sla" + "ck",
             r"hash-" + "chain", r"vot" + "ing", r"ensem" + "ble", r"\bds" + r"h\b", r"\bn" + r"c\b",
             r"\bgp" + r"l\b", r"\bsign" + r"ing\b", r"\bhoo" + r"ks?\b", r"cursor_" + "agent", "<d" + "iv", "<!" + "--",
             r"ledg" + "er"]


def all_files():
    out = []
    for base, dirs, files in os.walk(HERE):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        out += [os.path.relpath(os.path.join(base, f), HERE) for f in sorted(files)]
    return out


def read_text(rel):
    with open(os.path.join(HERE, rel), "rb") as fh:
        return fh.read().decode("utf-8", errors="replace")


class HygieneTests(unittest.TestCase):

    def test_file_list(self):
        self.assertEqual(sorted(n for n in os.listdir(HERE) if n != "__pycache__"),
                         ["README.md", "demo.py", "evidence.json", "fixtures", "mutants.py", "spec_review.py",
                          "test_spec_review.py"])

    def test_no_banned_word_or_path(self):
        for rel in all_files():
            low = read_text(rel).lower()
            for word in BANNED + PATHS:
                self.assertNotIn(word, low, rel)
                self.assertNotIn(word, rel.lower())

    def test_no_mechanism_word(self):
        for rel in all_files():
            low = read_text(rel).lower()
            for pattern in MECHANISM:
                self.assertIsNone(re.search(pattern, low), (rel, pattern))

    def test_stdlib_only_and_offline(self):
        src = read_text("spec_review.py")
        imports = set(re.findall(r"^import (\w+)", src, re.M)) | set(re.findall(r"^from (\w+)", src, re.M))
        self.assertEqual(imports, {"json", "re", "sys", "unicodedata"})
        for word in ("socket", "urllib", "http", "subprocess", "random", "time"):
            self.assertIsNone(re.search(r"\b%s\b" % word, src.split('"""', 2)[2]), word)


class EvidenceTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "evidence.json"), "r", encoding="utf-8") as fh:
            cls.ev = json.load(fh)

    def test_flags_and_title(self):
        self.assertIs(self.ev["network_used"], False)
        self.assertIs(self.ev["paid_api_used"], False)
        self.assertEqual(self.ev["model_calls"], 0)
        self.assertEqual(self.ev["paper"]["title"], TITLE)
        self.assertEqual(self.ev["paper"]["arxiv"], "2611.26588")
        self.assertIsNone(self.ev["paper"]["code"])

    def test_measured_equals_a_fresh_run(self):
        result = sr.run(load())
        self.assertEqual(self.ev["measured"]["summary"], result["summary"])
        self.assertEqual(self.ev["measured"]["checks"], result["checks"])

    def test_paper_figures_only_unverified(self):
        claims = self.ev["on_unmeasured"]["claims"]
        self.assertTrue(claims)
        for c in claims:
            self.assertEqual(c["status"], "UNVERIFIED")
        text = json.dumps({k: v for k, v in self.ev.items() if k != "on_unmeasured"})
        for figure in ("564", "68", "41"):
            self.assertIsNone(re.search(r"\b%s\b" % figure, text), figure)

    def test_timeouts(self):
        self.assertEqual(self.ev["timeouts"]["tool"], "none")
        self.assertEqual(self.ev["timeouts"]["mutants"], {"seconds": 300, "on_expiry": "DENY",
                                                          "rule": "a timed-out mutant is reported TIMEOUT and is not counted as killed"})


class DocumentTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.readme = read_text("README.md")
        cls.flat = " ".join(cls.readme.split())

    def test_title_exact(self):
        self.assertTrue(self.readme.startswith("# mb-verify-the-verifier\n"))
        self.assertIn("*" + TITLE + "*", self.readme)

    def test_statements(self):
        for needle in ("clean-room", "method only", "arXiv nonexclusive-distrib 1.0", "rule-based clause evaluator",
                       "no model call", "not model or real-world rates", "UNVERIFIED", "on_expiry", "fixture-authored"):
            self.assertIn(needle, self.flat, needle)

    def test_not_a_remake_line(self):
        lines = [l for l in self.readme.splitlines() if l.startswith("Not a remake")]
        self.assertEqual(len(lines), 1)
        for name in ("#153", "passing-check-vs-verdict", "w20-fidelity-audit", "#154"):
            self.assertIn(name, lines[0])


class MutantsHarnessTests(unittest.TestCase):

    def test_timeout_declared_and_never_a_kill(self):
        import mutants
        self.assertEqual(mutants.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})
        self.assertEqual(mutants.outcome(None), "TIMEOUT")
        self.assertEqual(mutants.outcome(0), "SURVIVED")
        self.assertEqual(mutants.outcome(1), "KILLED")
        self.assertFalse(mutants.is_killed("TIMEOUT"))
        self.assertFalse(mutants.is_killed("SURVIVED"))
        self.assertTrue(mutants.is_killed("KILLED"))

    def test_a_timed_out_run_is_reported_and_not_counted(self):
        import mutants
        original = mutants.run_suite
        try:
            mutants.run_suite = lambda workdir: None
            self.assertEqual(mutants.score(["m1", "m2"], lambda name: mutants.outcome(mutants.run_suite(name))),
                             (0, [("TIMEOUT", "m1"), ("TIMEOUT", "m2")]))
        finally:
            mutants.run_suite = original


if __name__ == "__main__":
    unittest.main()
