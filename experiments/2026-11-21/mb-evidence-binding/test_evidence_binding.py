"""Tests for evidence_binding. Run: python3 -B -m unittest"""

import copy
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import unicodedata
import unittest
from fractions import Fraction

import evidence_binding as eb

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
PY = sys.executable

# every malformed fixture and the one error code it must give
BAD_CODES = {
    "bad_answer_id_duplicate": "duplicate_name",
    "bad_answer_id_surrogate": "bad_id",
    "bad_answers_empty": "too_many",
    "bad_bigint_309_digits": "bad_value",
    "bad_bigint_5000_digits": "not_json",
    "bad_bom_prefix": "not_json",
    "bad_cell_bad_grouping": "bad_display",
    "bad_cell_not_text": "wrong_type",
    "bad_cell_too_long": "bad_display",
    "bad_citation_page_bool": "wrong_type",
    "bad_citation_page_float": "wrong_type",
    "bad_citation_unknown_key": "unknown_key",
    "bad_citations_empty": "too_many",
    "bad_citations_not_list": "too_many",
    "bad_citations_too_many": "too_many",
    "bad_columns_duplicate": "duplicate_name",
    "bad_columns_empty": "too_many",
    "bad_columns_too_many": "too_many",
    "bad_deep_nesting": "not_json",
    "bad_deep_nesting_200k": "too_large",
    "bad_deep_object_nesting": "not_json",
    "bad_duplicate_id_nfc_nfd_lines": "duplicate_name",
    "bad_duplicate_id_nfc_nfd_quotes": "duplicate_name",
    "bad_duplicate_key": "duplicate_key",
    "bad_duplicate_key_nested": "duplicate_key",
    "bad_empty_file": "not_json",
    "bad_exponent_overflow": "wrong_type",
    "bad_id_bidi": "bad_id",
    "bad_id_braille_blank": "bad_id",
    "bad_id_c1": "bad_id",
    "bad_id_choseong_filler": "bad_id",
    "bad_id_compat_jamo": "bad_id",
    "bad_id_dash": "bad_id",
    "bad_id_dot": "bad_id",
    "bad_id_empty": "bad_id",
    "bad_id_esc": "bad_id",
    "bad_id_halfwidth_filler": "bad_id",
    "bad_id_hangul_filler": "bad_id",
    "bad_id_ideographic_space": "bad_id",
    "bad_id_latin1": "bad_id",
    "bad_id_line_separator": "bad_id",
    "bad_id_long": "bad_id",
    "bad_id_nbsp": "bad_id",
    "bad_id_newline": "bad_id",
    "bad_id_private_use": "bad_id",
    "bad_id_space": "bad_id",
    "bad_id_zero_width": "bad_id",
    "bad_inconsistent_filing": "inconsistent_filing",
    "bad_infinity": "bad_number",
    "bad_invalid_utf8": "bad_encoding",
    "bad_lone_surrogate_escape_pair_reversed": "bad_text",
    "bad_missing_question_unit": "missing_key",
    "bad_missing_quotes": "missing_key",
    "bad_nan": "bad_number",
    "bad_neg_infinity": "bad_number",
    "bad_not_json": "not_json",
    "bad_not_object_answers": "wrong_type",
    "bad_oversize": "too_large",
    "bad_page_bool": "wrong_type",
    "bad_page_float": "wrong_type",
    "bad_page_huge": "bad_value",
    "bad_page_string": "wrong_type",
    "bad_page_zero": "bad_value",
    "bad_plant_duplicate": "bad_plant",
    "bad_plant_lowercase_set": "bad_plant",
    "bad_plant_missing_case": "bad_plant",
    "bad_plant_unknown": "bad_plant",
    "bad_quote_id_surrogate": "bad_id",
    "bad_quote_missing_cell": "bad_quote",
    "bad_quote_page": "bad_quote",
    "bad_quote_row_not_in_table": "bad_ref",
    "bad_ref_line": "bad_ref",
    "bad_ref_period_column": "bad_ref",
    "bad_ref_question": "bad_ref",
    "bad_ref_quote": "bad_ref",
    "bad_ref_row_line": "bad_ref",
    "bad_ref_unit": "bad_ref",
    "bad_row_length": "wrong_type",
    "bad_scale_note": "bad_scale_note",
    "bad_single_quotes": "not_json",
    "bad_text_company_long": "wrong_type",
    "bad_text_label_empty": "wrong_type",
    "bad_text_label_number": "wrong_type",
    "bad_text_line_bidi": "bad_text",
    "bad_text_line_bom": "bad_text",
    "bad_text_line_braille_blank": "bad_text",
    "bad_text_line_c1": "bad_text",
    "bad_text_line_choseong_filler": "bad_text",
    "bad_text_line_combining_grapheme_joiner": "bad_text",
    "bad_text_line_esc": "bad_text",
    "bad_text_line_hangul_filler": "bad_text",
    "bad_text_line_ideographic_space": "bad_text",
    "bad_text_line_leading_space": "bad_text",
    "bad_text_line_line_separator": "bad_text",
    "bad_text_line_nbsp": "bad_text",
    "bad_text_line_newline": "bad_text",
    "bad_text_line_private_use": "bad_text",
    "bad_text_line_surrogate": "bad_text",
    "bad_text_line_tab": "bad_text",
    "bad_text_line_trailing_space": "bad_text",
    "bad_text_line_unassigned": "bad_text",
    "bad_text_line_zero_width": "bad_text",
    "bad_text_question_bidi": "bad_text",
    "bad_text_quote_control": "bad_text",
    "bad_text_quote_surrogate": "bad_text",
    "bad_text_quote_too_long": "wrong_type",
    "bad_text_quote_zero_width": "bad_text",
    "bad_text_scale_note_nul": "bad_text",
    "bad_too_many_tables": "too_many",
    "bad_too_many_units": "too_many",
    "bad_top_level_array": "wrong_type",
    "bad_trailing_comma": "not_json",
    "bad_trailing_garbage": "not_json",
    "bad_unanswerable": "unanswerable",
    "bad_unanswerable_kind": "unanswerable",
    "bad_unit_kind": "bad_id",
    "bad_unit_note_control": "bad_text",
    "bad_unit_scale_bool": "wrong_type",
    "bad_unit_scale_float": "wrong_type",
    "bad_unit_scale_huge": "bad_value",
    "bad_unit_scale_zero": "bad_value",
    "bad_unknown_key_table": "unknown_key",
    "bad_unknown_key_top": "unknown_key",
    "bad_utf16_bom": "bad_encoding",
    "bad_value_bool": "wrong_type",
    "bad_value_empty": "bad_display",
    "bad_value_exponent": "bad_display",
    "bad_value_fullwidth_digits": "bad_display",
    "bad_value_number": "wrong_type",
    "bad_value_text": "bad_display",
    "bad_version": "bad_version",
    "bad_version_bool": "bad_version",
}

VALID_FIXTURES = ("main", "korean", "korean_nfd", "multi_citation")

# banned words are built from pieces so that this file does not hold them itself
BANNED = ["al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er"]
OTHER_BANNED = ["fei" + "shu", "sql" + "ite", "dae" + "mon", "hoo" + "ks", "hm" + "ac", "hash" + "-chain",
                "vot" + "ing", "ensem" + "ble", "sla" + "ck", "grok" + "ki"]
WORD_BANNED = ["n" + "c", "gp" + "l", "ds" + "h", "sign" + "ing"]
BANNED_PATHS = ["/work" + "space", "/t" + "mp", "/ho" + "me"]
TITLE = "Show Your Work: Can Small Open Models Read SEC Filings with Evidence a Machine Can Check?"
LICENCE = "paper CC BY 4.0; method only; upstream code Apache-2.0, not cloned or run; no code copied"


def fx_load(name="main"):
    return eb.load_fixture(os.path.join(FIXTURES, name + ".json"))


def raw_main():
    with open(os.path.join(FIXTURES, "main.json"), "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def read(name):
    with open(os.path.join(HERE, name), "rb") as fh:
        return fh.read().decode("utf-8")


def cli(*args):
    p = subprocess.run([PY, "-B", os.path.join(HERE, "evidence_binding.py")] + list(args), capture_output=True)
    return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


def view(question, value, *cites):
    return {"question": question, "value": value, "citations": [{"page": p, "quote": q} for p, q in cites]}


def answers_by(fx):
    return {(a["question"], a["planted"]): a for a in fx["answers"]}


# ------------------------------------------------------------------ exact numbers

class NumberTests(unittest.TestCase):
    def test_parse_display_numbers_exactly(self):
        cases = {"5,432.1": Fraction(54321, 10), "(12.3)": Fraction(-123, 10), "152,300,000": Fraction(152300000),
                 "0": Fraction(0), "-7": Fraction(-7), "655.90": Fraction(6559, 10), "1234": Fraction(1234),
                 "(1,204,500)": Fraction(-1204500), "0.001": Fraction(1, 1000)}
        for text, value in cases.items():
            self.assertEqual(eb.parse_number(text), value, text)
            self.assertIs(type(eb.parse_number(text)), Fraction)

    def test_refuse_what_is_not_a_display_number(self):
        for bad in ("", "5,43,2.1", "5432.1.0", "1e3", "5.4321e3", "+5", "(5", "5)", "--5", "-(5)", "1,234,", ",123",
                    "\uff15", "5 432", "1" * 41, "NaN", "Infinity", " 5", "5 ", "1.", ".5", "١٢٣", 5, 5.0, True, None):
            self.assertIsNone(eb.parse_number(bad), repr(bad))

    def test_appears_as_a_whole_number(self):
        yes = [("5,432,100", "Total revenue $ 5,432,100 $ 4,987,600"), ("4,987,600", "Total revenue $ 5,432,100 $ 4,987,600"),
               ("12.3", "(12.3)"), ("(12.3)", "Net income (12.3)"), ("61.7", "61.7"), ("5", "a 5."), ("5", "5, then")]
        no = [("432", "5,432,100"), ("100", "5,432,100"), ("5,432", "5,432.1"), ("5,432", "5,432,100"),
              ("43", "5,432.1"), ("2.1", "5,432.1"), ("4,987.6", "4,987.65"), ("61.7", "161.7"), ("7", "x 17 y")]
        for needle, text in yes:
            self.assertTrue(eb.appears_as_number(needle, text), (needle, text))
        for needle, text in no:
            self.assertFalse(eb.appears_as_number(needle, text), (needle, text))

    def test_later_occurrence_can_match_after_an_earlier_glued_one(self):
        self.assertTrue(eb.appears_as_number("300", "152,300 and 300"))
        self.assertFalse(eb.appears_as_number("300", "152,300 and 1,300"))

    def test_answer_keys_are_exact_and_scale_across_units(self):
        fx = fx_load()
        keys = {qid: eb.answer_key(fx, q) for qid, q in fx["questions"].items()}
        self.assertEqual(keys["q_revenue"], {Fraction(54321, 10)})
        self.assertEqual(keys["q_net_income"], {Fraction(-123, 10)})
        self.assertEqual(keys["q_operating_cash_flow"], {Fraction(1204500)})
        self.assertEqual(keys["q_diluted_shares"], {Fraction(152300000)})
        q = dict(fx["questions"]["q_revenue"], unit="usd")
        self.assertEqual(eb.answer_key(fx, q), {Fraction(5432100000)})
        q = dict(fx["questions"]["q_diluted_shares"], unit="shares_thousands")
        self.assertEqual(eb.answer_key(fx, q), {Fraction(152300)})


# ------------------------------------------------------------------ the loose test

class LooseTests(unittest.TestCase):
    def setUp(self):
        self.fx = fx_load()

    def loose(self, *args):
        return eb.loose_binding(self.fx, view(*args))

    def test_passes_when_the_string_is_in_the_quote_on_the_cited_page(self):
        r = self.loose("q_revenue", "5,432.1", (28, "q28_revenue"))
        self.assertEqual(r, {"pass": True, "reason": "bound", "citation": 0})

    def test_passes_for_any_number_shown_in_the_quote(self):
        for value in ("5,432.1", "4,987.6"):
            self.assertTrue(self.loose("q_revenue", value, (28, "q28_revenue"))["pass"])
        self.assertTrue(self.loose("q_revenue", "5,432,100", (41, "q41_revenue"))["pass"])

    def test_fails_on_the_wrong_page(self):
        r = self.loose("q_revenue", "5,432.1", (29, "q28_revenue"))
        self.assertEqual((r["pass"], r["reason"]), (False, "not_on_cited_page"))

    def test_fails_when_the_string_is_not_in_the_quote(self):
        r = self.loose("q_revenue", "5,432", (28, "q28_revenue"))
        self.assertEqual((r["pass"], r["reason"]), (False, "number_not_in_quote"))
        r = self.loose("q_revenue", "5432.1", (28, "q28_revenue"))
        self.assertEqual((r["pass"], r["reason"]), (False, "number_not_in_quote"))

    def test_any_citation_is_enough_and_the_furthest_failure_is_reported(self):
        r = self.loose("q_revenue", "5,432.1", (29, "q28_revenue"), (28, "q28_revenue"))
        self.assertEqual((r["pass"], r["citation"]), (True, 1))
        r = self.loose("q_revenue", "5,432.1", (29, "q28_revenue"), (41, "q41_revenue"))
        self.assertEqual((r["pass"], r["reason"]), (False, "number_not_in_quote"))

    def test_loose_ignores_line_period_and_unit(self):
        self.assertTrue(self.loose("q_revenue", "812.4", (28, "q28_operating_income"))["pass"])
        self.assertTrue(self.loose("q_revenue", "152,300", (47, "q47_diluted_shares"))["pass"])


# ------------------------------------------------------------------ the strict test

class StrictTests(unittest.TestCase):
    def setUp(self):
        self.fx = fx_load()

    def strict(self, *args):
        return eb.strict_binding(self.fx, view(*args))

    def test_correct_bound_evidence_passes(self):
        for qid, value, page, quote in (("q_revenue", "5,432.1", 28, "q28_revenue"),
                                        ("q_net_income", "(12.3)", 28, "q28_net_income"),
                                        ("q_operating_cash_flow", "1,204,500", 45, "q45_operating_cash_flow"),
                                        ("q_diluted_shares", "152,300,000", 29, "q29_diluted_shares")):
            self.assertEqual(self.strict(qid, value, (page, quote)), {"pass": True, "reason": "bound", "citation": 0})

    def test_scale_error_is_scale_mismatch(self):
        r = self.strict("q_revenue", "5,432,100", (41, "q41_revenue"))
        self.assertEqual((r["pass"], r["reason"]), (False, "scale_mismatch"))
        r = self.strict("q_operating_cash_flow", "1,204.5", (28, "q28_operating_cash_flow"))
        self.assertEqual((r["pass"], r["reason"]), (False, "scale_mismatch"))

    def test_other_period_cell_is_wrong_period(self):
        r = self.strict("q_revenue", "4,987.6", (28, "q28_revenue"))
        self.assertEqual((r["pass"], r["reason"]), (False, "wrong_period"))

    def test_wrong_period_is_reported_before_scale(self):
        r = self.strict("q_revenue", "4,987,600", (41, "q41_revenue"))
        self.assertEqual(r["reason"], "wrong_period")

    def test_other_line_is_wrong_line(self):
        r = self.strict("q_revenue", "812.4", (28, "q28_operating_income"))
        self.assertEqual((r["pass"], r["reason"]), (False, "wrong_line"))

    def test_number_in_text_that_is_not_a_cell(self):
        fx = copy.deepcopy(self.fx)
        fx["quotes"]["q28_revenue"]["text"] = "Total revenue (note 28) $ 5,432.1 $ 4,987.6"
        r = eb.strict_binding(fx, view("q_revenue", "28", (28, "q28_revenue")))
        self.assertEqual((r["pass"], r["reason"]), (False, "number_not_a_cell"))
        self.assertTrue(eb.loose_binding(fx, view("q_revenue", "28", (28, "q28_revenue")))["pass"])

    def test_unit_kind_mismatch(self):
        fx = copy.deepcopy(self.fx)
        fx["questions"]["q_odd"] = {"text": "x", "line": "diluted_shares", "period": "fy2025", "unit": "usd"}
        r = eb.strict_binding(fx, view("q_odd", "152,300,000", (29, "q29_diluted_shares")))
        self.assertEqual(r["reason"], "unit_kind_mismatch")

    def test_the_scale_comparison_is_exact_arithmetic(self):
        fx = copy.deepcopy(self.fx)
        # a question in thousands answered from the thousands table binds; the same digits asked in millions do not
        fx["questions"]["q_rev_k"] = {"text": "x", "line": "revenue", "period": "fy2025", "unit": "usd_thousands"}
        self.assertTrue(eb.strict_binding(fx, view("q_rev_k", "5,432,100", (41, "q41_revenue")))["pass"])
        self.assertEqual(eb.strict_binding(fx, view("q_rev_k", "5,432.1", (28, "q28_revenue")))["reason"],
                         "scale_mismatch")
        # equal scales under different unit ids still bind
        fx["units"]["usd_k2"] = {"kind": "usd", "scale": 1000, "note": ""}
        fx["questions"]["q_rev_k2"] = {"text": "x", "line": "revenue", "period": "fy2025", "unit": "usd_k2"}
        self.assertTrue(eb.strict_binding(fx, view("q_rev_k2", "5,432,100", (41, "q41_revenue")))["pass"])

    def test_same_value_in_both_periods_binds_to_the_asked_one(self):
        fx = copy.deepcopy(self.fx)
        fx["tables"]["t_selected"]["cells"]["revenue"][1]["value"] = Fraction(54321, 10)
        fx["tables"]["t_selected"]["cells"]["revenue"][1]["display"] = "5,432.1"
        self.assertTrue(eb.strict_binding(fx, view("q_revenue", "5,432.1", (28, "q28_revenue")))["pass"])

    def test_any_citation_that_binds_is_enough(self):
        r = self.strict("q_revenue", "5,432.1", (41, "q41_revenue"), (28, "q28_revenue"))
        self.assertEqual((r["pass"], r["citation"]), (True, 1))

    def test_furthest_reason_wins_when_nothing_binds(self):
        r = self.strict("q_revenue", "4,987.6", (29, "q28_revenue"), (28, "q28_revenue"))
        self.assertEqual(r["reason"], "wrong_period")
        r = self.strict("q_revenue", "5,432,100", (28, "q28_revenue"), (41, "q41_revenue"))
        self.assertEqual(r["reason"], "scale_mismatch")
        self.assertEqual(eb.STAGES, ("not_on_cited_page", "number_not_in_quote", "wrong_line", "number_not_a_cell",
                                     "wrong_period", "unit_kind_mismatch", "scale_mismatch"))

    def test_strict_never_passes_what_loose_fails(self):
        fx = self.fx
        for qid in fx["questions"]:
            for quote_id, quote in fx["quotes"].items():
                for cell in fx["tables"][quote["table"]]["cells"][quote["row"]]:
                    for page in (quote["page"], quote["page"] + 1):
                        v = view(qid, cell["display"], (page, quote_id))
                        if eb.strict_binding(fx, v)["pass"]:
                            self.assertTrue(eb.loose_binding(fx, v)["pass"])

    def test_strict_pass_means_the_value_equals_the_key(self):
        fx = self.fx
        for qid, q in fx["questions"].items():
            key = eb.answer_key(fx, q).pop()
            for quote_id, quote in fx["quotes"].items():
                for cell in fx["tables"][quote["table"]]["cells"][quote["row"]]:
                    v = view(qid, cell["display"], (quote["page"], quote_id))
                    if eb.strict_binding(fx, v)["pass"]:
                        self.assertEqual(eb.parse_number(cell["display"]), key)

    def test_exactly_one_quote_cell_binds_each_question(self):
        fx = self.fx
        for qid in fx["questions"]:
            bound = []
            for quote_id, quote in fx["quotes"].items():
                for cell in fx["tables"][quote["table"]]["cells"][quote["row"]]:
                    if eb.strict_binding(fx, view(qid, cell["display"], (quote["page"], quote_id)))["pass"]:
                        bound.append((quote_id, cell["display"]))
            self.assertEqual(len(bound), 1, (qid, bound))


# ------------------------------------------------------------------ done-when (a) (b) and the planted label

class DoneWhenTests(unittest.TestCase):
    def setUp(self):
        self.fx = fx_load()
        self.result = eb.run(self.fx)

    def test_a_loose_passes_all_three_planted_cases(self):
        for qid, q in self.result["per_question"].items():
            self.assertTrue(q["loose_passes_all_three"], qid)
        self.assertEqual(self.result["summary"]["loose_passes"], 18)
        self.assertTrue(self.result["checks"]["a_loose_passes_all_three_cases"]["holds"])

    def test_b_strict_accepts_only_the_correct_case_with_distinct_reasons(self):
        for qid, q in self.result["per_question"].items():
            self.assertTrue(q["strict_accepts_only_correct"], qid)
            self.assertEqual(q["strict_reasons"], {"scale_error": "scale_mismatch", "wrong_period": "wrong_period"})
            self.assertTrue(q["reasons_distinct"])
        b = self.result["checks"]["b_strict_accepts_only_the_correct_case_with_distinct_reasons"]
        self.assertTrue(b["holds"])
        self.assertEqual((b["scale_error_reasons"], b["wrong_period_reasons"]), (["scale_mismatch"], ["wrong_period"]))

    def test_summary_counts(self):
        s = self.result["summary"]
        self.assertEqual((s["answers"], s["questions"], s["wrong_values"], s["strict_passes"]), (18, 6, 12, 6))
        self.assertEqual((s["loose_false_pass_rate"], s["strict_false_pass_rate"], s["strict_true_pass_rate"]),
                         ("12/12", "0/12", "6/6"))
        self.assertEqual(s["strict_reason_counts"], {"bound": 6, "scale_mismatch": 6, "wrong_period": 6})

    def test_several_questions_lines_units_and_signs(self):
        qs = self.fx["questions"].values()
        self.assertEqual(len({q["line"] for q in qs}), 6)
        self.assertEqual({q["period"] for q in qs}, {"fy2025", "fy2024"})
        self.assertEqual({q["unit"] for q in qs}, {"usd_millions", "usd_thousands", "shares"})
        self.assertTrue(any(eb.answer_key(self.fx, q).pop() < 0 for q in qs))

    def test_each_scale_error_number_really_appears_in_its_quote(self):
        for a in self.fx["answers"]:
            for c in a["citations"]:
                text = self.fx["quotes"][c["quote"]]["text"]
                self.assertIn(a["value"], text, a["id"])

    def test_the_planted_label_is_never_read_by_the_tests(self):
        fx = self.fx
        for a in fx["answers"]:
            v = eb.answer_view(a)
            self.assertEqual(sorted(v), ["citations", "question", "value"])
            changed = copy.deepcopy(a)
            for label in eb.PLANTS:
                changed["planted"] = label
                self.assertEqual(eb.loose_binding(fx, eb.answer_view(changed)), eb.loose_binding(fx, v))
                self.assertEqual(eb.strict_binding(fx, eb.answer_view(changed)), eb.strict_binding(fx, v))

    def test_run_scores_with_relabelled_answers_unchanged(self):
        fx = copy.deepcopy(self.fx)
        for a in fx["answers"]:
            a["planted"] = "correct"
            a["id"] = "x_" + a["id"]
        original = eb.run(self.fx)["answers"]
        rows = []
        for a in fx["answers"]:
            v = eb.answer_view(a)
            rows.append((eb.loose_binding(fx, v), eb.strict_binding(fx, v)))
        self.assertEqual(rows, [(r["loose"], r["strict"]) for r in original])

    def test_view_is_a_copy(self):
        a = self.fx["answers"][0]
        v = eb.answer_view(a)
        v["citations"][0]["page"] = 999
        self.assertNotEqual(a["citations"][0]["page"], 999)

    def test_value_matches_key_only_for_correct_plants(self):
        for row in self.result["answers"]:
            self.assertEqual(row["value_matches_key"], row["planted"] == "correct", row["id"])

    def test_c_offline_check_is_reported(self):
        c = self.result["checks"]["c_offline"]
        self.assertEqual(c, {"holds": True, "network_used": False, "paid_api_used": False})

    def test_other_valid_fixtures_give_the_same_verdicts(self):
        base = [(r["planted"], r["loose"]["pass"], r["strict"]["reason"]) for r in self.result["answers"]]
        for name in ("korean", "korean_nfd", "multi_citation"):
            out = eb.run(fx_load(name))
            got = [(r["planted"], r["loose"]["pass"], r["strict"]["reason"]) for r in out["answers"]]
            self.assertEqual(got, base, name)
            self.assertTrue(all(c["holds"] for c in out["checks"].values()), name)

    def test_multi_citation_binds_through_its_second_citation(self):
        out = eb.run(fx_load("multi_citation"))
        row = [r for r in out["answers"] if r["id"] == "revenue__correct"][0]
        self.assertEqual((row["strict"]["citation"], row["loose"]["citation"]), (1, 1))
        self.assertEqual(len(fx_load("multi_citation")["answers"][0]["citations"]), 2)

    def test_caps_declare_an_expiry_in_the_set(self):
        self.assertEqual(eb.ON_EXPIRY, ("HOLD", "ESCALATE", "DENY"))
        for name, cap in eb.CAPS.items():
            self.assertIn(cap["on_expiry"], eb.ON_EXPIRY, name)
            self.assertIs(type(cap["limit"]), int)
        self.assertEqual(eb.CAPS["file_bytes"]["limit"], eb.MAX_BYTES)

    def test_the_mutation_timeout_declares_an_expiry(self):
        import mutants
        self.assertEqual(mutants.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})
        self.assertIn(mutants.TIMEOUT["on_expiry"], eb.ON_EXPIRY)


# ------------------------------------------------------------------ loader

class LoaderTests(unittest.TestCase):
    def test_main_loads(self):
        fx = fx_load()
        self.assertEqual((len(fx["tables"]), len(fx["quotes"]), len(fx["questions"]), len(fx["answers"])), (6, 12, 6, 18))

    def test_valid_fixture_list_is_complete(self):
        names = sorted(f[:-5] for f in os.listdir(FIXTURES) if f.endswith(".json") and not f.startswith("bad_"))
        self.assertEqual(names, sorted(VALID_FIXTURES))

    def test_every_bad_fixture_is_in_the_code_map_and_back(self):
        names = sorted(f[:-5] for f in os.listdir(FIXTURES) if f.startswith("bad_"))
        self.assertEqual(names, sorted(BAD_CODES))
        self.assertGreaterEqual(len(names), 120)

    def test_each_bad_fixture_raises_its_code_in_process(self):
        for name, code in sorted(BAD_CODES.items()):
            with self.assertRaises(eb.BindingError, msg=name) as cm:
                eb.run(eb.load_fixture(os.path.join(FIXTURES, name + ".json")))
            self.assertEqual(cm.exception.code, code, name)

    def test_unreadable_path(self):
        with self.assertRaises(eb.BindingError) as cm:
            eb.load_fixture(os.path.join(FIXTURES, "does_not_exist.json"))
        self.assertEqual(cm.exception.code, "unreadable")

    def test_korean_free_text_and_hangul_ids_are_accepted(self):
        for name, form in (("korean", "NFC"), ("korean_nfd", "NFD")):
            fx = fx_load(name)
            self.assertEqual(fx["lines"]["revenue"], unicodedata.normalize(form, "매출액"))
            self.assertIn(unicodedata.normalize(form, "매출_질문"), fx["questions"])
            self.assertIn(unicodedata.normalize(form, "단위"), fx["tables"]["t_selected"]["scale_note"])
            rc, out, err = cli(os.path.join(FIXTURES, name + ".json"))
            self.assertEqual((rc, err), (0, ""))
            self.assertTrue(out.isascii())

    def test_text_rules(self):
        for good in ("Total revenue", "매출액", unicodedata.normalize("NFD", "매출액"), "Net income (loss)", "x" * 160,
                     "Note 12: Earnings per share", "$ 5,432.1 – 4,987.6"):
            self.assertEqual(eb._text(good, "t", 160), good)
        for bad in ("a\nb", "a\tb", "a\x1bb", "a\x00b", "a\u0085b", "a\u200bb", "a\u200db", "a\u202eb", "a\u2066b",
                    "a\ufeffb", "a\u00a0b", "a\u3000b", "a\u2028b", "a\u3164b", "a\u2800b", "a\u115fb", "a\u034fb",
                    "a\ue000b", "a\ud800b", "a\u0378b", " a", "a "):
            with self.assertRaises(eb.BindingError, msg=repr(bad)) as cm:
                eb._text(bad, "t", 160)
            self.assertEqual(cm.exception.code, "bad_text")
        for bad in ("", "x" * 161, 5, None, True, ["a"]):
            with self.assertRaises(eb.BindingError) as cm:
                eb._text(bad, "t", 160)
            self.assertEqual(cm.exception.code, "wrong_type")

    def test_id_rules(self):
        for good in ("a", "q_revenue", "매출", unicodedata.normalize("NFD", "매출"), "x" * 40):
            self.assertEqual(eb._id(good, "id"), good)
        for bad in ("", "x" * 41, "a b", "a-b", "é", "a\u200b", "\ud800", "\u3164", "\u3131", "１", 1, None, True):
            with self.assertRaises(eb.BindingError):
                eb._id(bad, "id")

    def test_integers_must_be_integers(self):
        for bad in (True, False, 1.0, "1", None, [1]):
            with self.assertRaises(eb.BindingError) as cm:
                eb._int(bad, "x", 1, 5)
            self.assertEqual(cm.exception.code, "wrong_type")
        for bad in (0, 6, 10 ** 400):
            with self.assertRaises(eb.BindingError) as cm:
                eb._int(bad, "x", 1, 5)
            self.assertEqual(cm.exception.code, "bad_value")

    def test_parse_refuses_nan_infinity_duplicates_and_junk(self):
        cases = {'{"a": NaN}': "bad_number", '{"a": Infinity}': "bad_number", '{"a": -Infinity}': "bad_number",
                 '{"a": 1, "a": 2}': "duplicate_key", '{"a": {"b": 1, "b": 1}}': "duplicate_key",
                 "{'a': 1}": "not_json", "": "not_json", "[1] x": "not_json",
                 "[" * 90000 + "]" * 90000: "not_json", "1" * 5000: "not_json"}
        for text, code in cases.items():
            with self.assertRaises(eb.BindingError, msg=text[:20]) as cm:
                eb.parse(text)
            self.assertEqual(cm.exception.code, code)

    def test_size_cap(self):
        self.assertEqual(eb.MAX_BYTES, 200000)
        for name in ("bad_oversize", "bad_deep_nesting_200k"):
            with self.assertRaises(eb.BindingError) as cm:
                eb.load_fixture(os.path.join(FIXTURES, name + ".json"))
            self.assertEqual(cm.exception.code, "too_large")

    def test_single_edits_to_main(self):
        def edit(fn):
            raw = raw_main()
            fn(raw)
            return raw

        def code_of(raw):
            try:
                eb.validate(raw)
            except eb.BindingError as e:
                return e.code
            return None

        cases = [
            (lambda d: d["tables"]["t_selected"].__setitem__("page", 10001), "bad_value"),
            (lambda d: d["tables"]["t_selected"].__setitem__("page", 10000), "bad_quote"),
            (lambda d: d["units"]["usd"].__setitem__("scale", 10 ** 12), None),
            (lambda d: d["units"]["usd"].__setitem__("scale", 10 ** 12 + 1), "bad_value"),
            (lambda d: d["units"]["usd_millions"].__setitem__("note", ""), None),
            (lambda d: d["tables"]["t_selected"].__setitem__("unit", "usd_thousands"), "bad_scale_note"),
            (lambda d: d["tables"]["t_selected"]["rows"].__setitem__("revenue", ["5,432.1", "4,987.7"]), "bad_quote"),
            (lambda d: d["answers"][0].__setitem__("value", "1"), None),
            (lambda d: d["answers"][0]["citations"][0].__setitem__("page", 1), None),
            (lambda d: d["answers"][0].__setitem__("planted", None), "bad_plant"),
            (lambda d: d["questions"]["q_revenue"].__setitem__("unit", "usd"), None),
            (lambda d: d["answers"][0].__setitem__("citations", [{"page": 28, "quote": "q28_revenue"}] * 5), None),
            (lambda d: d["tables"]["t_selected"].__setitem__("columns", ["fy2024", "fy2025"]), "inconsistent_filing"),
        ]
        for fn, code in cases:
            self.assertEqual(code_of(edit(fn)), code)

    def test_validation_does_not_change_its_input(self):
        raw = raw_main()
        before = copy.deepcopy(raw)
        eb.validate(raw)
        self.assertEqual(raw, before)


# ------------------------------------------------------------------ command line

class CommandLineTests(unittest.TestCase):
    def test_every_malformed_fixture_exits_2_with_empty_stdout_and_one_stderr_line(self):
        for name, code in sorted(BAD_CODES.items()):
            rc, out, err = cli(os.path.join(FIXTURES, name + ".json"))
            self.assertEqual(rc, 2, name)
            self.assertEqual(out, "", name)
            self.assertEqual(err.count("\n"), 1, name)
            self.assertTrue(err.endswith("\n"), name)
            self.assertTrue(err.startswith("ERROR " + code + ": "), (name, err))
            self.assertNotIn("Traceback", err)
            self.assertTrue(err.isascii(), name)

    def test_usage_and_missing_file(self):
        for args in ([], ["a", "b"]):
            rc, out, err = cli(*args)
            self.assertEqual((rc, out, err.count("\n")), (2, "", 1))
            self.assertTrue(err.startswith("ERROR usage: "))
        rc, out, err = cli(os.path.join(FIXTURES, "nothing_here.json"))
        self.assertEqual((rc, out, err.count("\n")), (2, "", 1))
        self.assertTrue(err.startswith("ERROR unreadable: "))

    def test_valid_fixtures_exit_0_with_ascii_json(self):
        for name in VALID_FIXTURES:
            rc, out, err = cli(os.path.join(FIXTURES, name + ".json"))
            self.assertEqual((rc, err), (0, ""), name)
            self.assertTrue(out.isascii() and out.endswith("\n"))
            json.loads(out)

    def test_report_is_deterministic_and_states_its_scope(self):
        a, b = eb.report(fx_load()), eb.report(fx_load())
        self.assertEqual(a, b)
        self.assertIn("fixture-authored", json.loads(a)["scope_note"])

    def test_main_returns_codes(self):
        old = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
        try:
            rc = eb.main(["x", os.path.join(FIXTURES, "main.json")])
            sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
            rc_bad = eb.main(["x", os.path.join(FIXTURES, "bad_nan.json")])
            out_bad, err_bad = sys.stdout.getvalue(), sys.stderr.getvalue()
        finally:
            sys.stdout, sys.stderr = old
        self.assertEqual((rc, rc_bad, out_bad, err_bad.count("\n")), (0, 2, "", 1))


# ------------------------------------------------------------------ demo

class DemoTests(unittest.TestCase):
    def run_demo(self):
        p = subprocess.run([PY, "-B", os.path.join(HERE, "demo.py")], capture_output=True)
        self.assertEqual((p.returncode, p.stderr), (0, b""))
        return p.stdout

    def test_demo_is_byte_identical_across_two_runs(self):
        self.assertEqual(self.run_demo(), self.run_demo())

    def test_demo_is_labelled_and_shows_every_case(self):
        text = self.run_demo().decode("ascii")
        self.assertIn("transcript produced by this code from the fixture, not written by hand", text)
        self.assertEqual(text.count("QUESTION "), 6)
        self.assertEqual(text.count("FAIL scale_mismatch"), 6)
        self.assertEqual(text.count("FAIL wrong_period"), 6)
        self.assertIn("wrong values passing the loose test: 12/12", text)
        self.assertIn("wrong values passing the strict test: 0/12", text)
        for line in text.split("\n"):
            self.assertEqual(line, line.rstrip())

    def test_demo_hash_is_in_the_readme(self):
        self.assertIn(hashlib.sha256(self.run_demo()).hexdigest(), read("README.md"))


# ------------------------------------------------------------------ source scan, evidence and README

def project_files():
    out = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        out.extend(os.path.join(root, f) for f in files)
    return sorted(out)


class HygieneTests(unittest.TestCase):
    def test_imports_are_the_standard_library_only(self):
        mods = set(re.findall(r"^(?:import|from) ([A-Za-z_]+)", read("evidence_binding.py"), re.M))
        self.assertEqual(mods, {"fractions", "json", "re", "sys", "unicodedata"})
        for name in ("evidence_binding.py", "demo.py", "mutants.py", "test_evidence_binding.py"):
            for mod in re.findall(r"^(?:import|from) ([A-Za-z_]+)", read(name), re.M):
                self.assertTrue(mod in sys.stdlib_module_names or mod == "evidence_binding", (name, mod))

    def test_no_network_or_paid_api_words_in_the_module(self):
        text = read("evidence_binding.py").lower()
        for w in ["sock" + "et", "url" + "lib", "http" + ".client", "req" + "uests", "ss" + "l.", "asyn" + "cio",
                  "open" + "ai", "anthr" + "opic", "api_" + "key", "tok" + "en", "import ran" + "dom",
                  "import ti" + "me", "date" + "time", "subpro" + "cess", "os" + ".system", "eva" + "l(", "ex" + "ec("]:
            self.assertNotIn(w, text, w)

    def test_module_never_writes(self):
        text = read("evidence_binding.py")
        self.assertEqual(re.findall(r"open\(([^)]*)\)", text), ['path, "rb"'])

    def test_no_banned_word_or_path_in_any_file(self):
        for path in project_files():
            with open(path, "rb") as fh:
                text = fh.read().decode("utf-8", errors="replace").lower()
            for word in BANNED + OTHER_BANNED + BANNED_PATHS:
                self.assertNotIn(word.lower(), text, (os.path.basename(path), word))
            for word in WORD_BANNED:
                self.assertIsNone(re.search(r"\b%s\b" % word, text), (os.path.basename(path), word))

    def test_no_stray_files(self):
        names = sorted(os.path.relpath(p, HERE) for p in project_files() if os.sep + "fixtures" + os.sep not in p)
        self.assertEqual(names, ["README.md", "demo.py", "evidence.json", "evidence_binding.py", "mutants.py",
                                 "test_evidence_binding.py"])

    def test_text_files_are_clean_utf8(self):
        for path in project_files():
            if os.path.basename(path).startswith("bad_"):
                continue
            with open(path, "rb") as fh:
                raw = fh.read()
            raw.decode("utf-8")
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r", raw)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.ev = json.loads(read("evidence.json"))

    def test_network_and_paid_api_are_false(self):
        self.assertIs(self.ev["network_used"], False)
        self.assertIs(self.ev["paid_api_used"], False)

    def test_title_and_licence(self):
        self.assertEqual(self.ev["paper"]["title"], TITLE)
        self.assertEqual(self.ev["paper"]["licence_line"], LICENCE)
        self.assertIn("Apache-2.0", self.ev["paper"]["upstream_code"])
        self.assertIn("not run", self.ev["paper"]["upstream_code"])

    def test_paper_numbers_only_under_on_unmeasured(self):
        claims = self.ev["on_unmeasured"]["claims"]
        self.assertGreaterEqual(len(claims), 7)
        self.assertTrue(all(c["status"] == "UNVERIFIED" for c in claims))
        measured = json.dumps(self.ev["measured"])
        for number in ("1,000", "17.1", "82.7", "84.5", "167", "57%", "30%", "3.9"):
            self.assertNotIn(number, measured)
            self.assertIn(number, json.dumps(claims))

    def test_measured_matches_the_run(self):
        m = self.ev["measured"]
        s = eb.run(fx_load())["summary"]
        self.assertEqual((m["questions"], m["answers"], m["wrong_values"], m["loose_passes"], m["strict_passes"]),
                         (s["questions"], s["answers"], s["wrong_values"], s["loose_passes"], s["strict_passes"]))
        self.assertEqual((m["loose_false_passes"], m["strict_false_passes"], m["strict_true_passes"]),
                         (s["loose_false_pass_rate"], s["strict_false_pass_rate"], s["strict_true_pass_rate"]))
        self.assertEqual(m["strict_reason_counts"], s["strict_reason_counts"])
        self.assertIs(m["fixture_authored"], True)


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.readme = read("README.md")

    def test_title_and_licence_line(self):
        self.assertIn(TITLE, self.readme)
        self.assertIn(LICENCE, self.readme)
        self.assertIn("2611.24990", self.readme)

    def test_scope_and_remake_statements(self):
        low = " ".join(self.readme.lower().split())
        for needle in ("fixture-authored", "unverified", "not a remake", "passing-check-vs-verdict",
                       "mb-answerability-pairs", "evidence binding, not a completion or scope verdict",
                       "no command, no machine state", "## limits", "## how a ludex village would use it",
                       "loose test", "strict test", "on_expiry", "exit 2", "korean", "nfd"):
            self.assertIn(needle, low, needle)

    def test_quotes_are_short(self):
        for quoted in re.findall(r'"([^"\n]{1,200})"', self.readme):
            self.assertLessEqual(len(quoted.split()), 6, quoted)

    def test_no_abstract_sentence_is_copied(self):
        for chunk in ("a fluent answer from a language model is not a verified one",
                      "an automatic " + "check" + "er rejects many wrong answers", "never reduces them",
                      "reasoning significantly reduces such errors"):
            for name in ("README.md", "evidence.json", "demo.py", "evidence_binding.py"):
                self.assertNotIn(chunk, read(name).lower(), (name, chunk))


if __name__ == "__main__":
    unittest.main()
