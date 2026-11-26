"""unittest suite for strict_threshold.py.  Run: python3 -B -m unittest

Every test checks behaviour through the imported module: return values, the in-process CLI, the report text, the JSON
output and the demo output. No test reads any Python source file. There is no catch-all wrapper: an unexpected
exception stays a unittest error, so mutants.py can tell a behaviour kill (an assertion fails) from a crash.
Expected values are written out here or computed from the fixture numbers, not taken from module constants.
"""

import decimal
import io
import json
import os
import tempfile
import unittest

import demo
import mutants
import strict_threshold as st

D = decimal.Decimal
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
VALID = ("main.json", "more.json")
PAIRS = {"real_response": ("PASS", "FAIL"), "zero_reference": ("PASS", "PASS"), "genuine_fail": ("FAIL", "FAIL"),
         "fail_zero_passes": ("FAIL", "PASS")}
HEADER = ("| contrast | equivalence | zero reference, inclusive (passes when T <= m) "
          "| zero reference, paper-strict (passes only when T < m) | critical value T | verdict |")
LEGEND = ("T = max(|human_lo|, |human_hi|) is the critical value: the inclusive reading passes zero at m = T, "
          "the paper-strict reading does not, and under the strict rule no least passing margin exists "
          "(T is the infimum)")
BAD_CODES = {
    "bad_candidate_bool.json": "bad_type",
    "bad_candidate_null.json": "bad_type",
    "bad_candidate_text.json": "bad_type",
    "bad_contrast_not_object.json": "bad_shape",
    "bad_contrasts_object.json": "bad_shape",
    "bad_deep_nesting.json": "not_json",
    "bad_duplicate_id.json": "duplicate_id",
    "bad_duplicate_key.json": "duplicate_key",
    "bad_empty_file.json": "not_json",
    "bad_empty_list.json": "empty_list",
    "bad_exponent_overflow.json": "out_of_range",
    "bad_huge_exponent.json": "out_of_range",
    "bad_human_lo_object.json": "bad_type",
    "bad_id_hyphen.json": "bad_id",
    "bad_id_number.json": "bad_id",
    "bad_id_too_long.json": "bad_id",
    "bad_id_upper.json": "bad_id",
    "bad_infinity_margin.json": "not_finite",
    "bad_interval_reversed.json": "interval_reversed",
    "bad_label_control.json": "bad_text",
    "bad_label_empty.json": "bad_text",
    "bad_label_number.json": "bad_type",
    "bad_label_spaces.json": "bad_text",
    "bad_label_zero_width.json": "bad_text",
    "bad_long_number.json": "bad_number",
    "bad_long_number_few_places.json": "bad_number",
    "bad_margin_list.json": "bad_type",
    "bad_margin_negative.json": "bad_margin",
    "bad_margin_negative_zero.json": "bad_margin",
    "bad_margin_overflow.json": "out_of_range",
    "bad_margin_zero.json": "bad_margin",
    "bad_missing_candidate.json": "missing_field",
    "bad_missing_contrasts.json": "missing_field",
    "bad_missing_human_hi.json": "missing_field",
    "bad_missing_human_lo.json": "missing_field",
    "bad_missing_id.json": "missing_field",
    "bad_missing_label.json": "missing_field",
    "bad_missing_margin.json": "missing_field",
    "bad_missing_planted.json": "missing_field",
    "bad_missing_units.json": "missing_field",
    "bad_nan_candidate.json": "not_finite",
    "bad_neg_infinity_lo.json": "not_finite",
    "bad_not_json.json": "not_json",
    "bad_not_utf8.json": "bad_encoding",
    "bad_planted_number.json": "bad_planted",
    "bad_planted_unknown.json": "bad_planted",
    "bad_positive_exponent.json": "bad_number",
    "bad_tiny_exponent_margin.json": "bad_number",
    "bad_too_large.json": "too_large",
    "bad_too_many.json": "too_many",
    "bad_too_many_places.json": "bad_number",
    "bad_top_level_list.json": "bad_shape",
    "bad_trailing_comma.json": "not_json",
    "bad_truncated.json": "not_json",
    "bad_units_too_long.json": "bad_text",
    "bad_unknown_contrast_field.json": "unknown_field",
    "bad_unknown_root_field.json": "unknown_field",
    "bad_value_just_over.json": "out_of_range",
    "bad_value_too_big.json": "out_of_range",
    "bad_value_too_small.json": "out_of_range",
    "bad_version_2.json": "bad_version",
    "bad_version_float.json": "bad_version",
    "bad_version_text.json": "bad_version",
    "bad_zero_huge_exponent.json": "bad_number",
}


def cli(*args):
    out, err = io.StringIO(), io.StringIO()
    code = st.main(["strict_threshold.py"] + list(args), out, err)
    return code, out.getvalue(), err.getvalue()


def deny_code(root):
    """The DENY code validate() raises, or 'no deny'. Other exceptions are not caught."""
    try:
        st.validate(root)
    except st.FoldError as e:
        return e.code
    return "no deny"


def contrast(lo, hi, cand, margin, planted="real_response", cid="c"):
    return {"id": cid, "label": "l", "units": "SD", "human_lo": D(lo), "human_hi": D(hi), "candidate": D(cand),
            "margin": D(margin), "planted": planted}


def root_with(**fields):
    c = contrast("0.25", "0.45", "0.31", "0.2", cid="reminder_letter")
    c.update(fields)
    return {"fixture_version": D(1), "label": "x", "contrasts": [c]}


def raw_contrasts(name):
    """The fixture numbers read independently of the module, as exact decimals."""
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.loads(fh.read(), parse_float=D, parse_int=D)["contrasts"]


def expected_row(c):
    """What every strict-arm row must show, computed here from the fixture numbers."""
    t = max(c["human_lo"].copy_abs(), c["human_hi"].copy_abs())
    eq, zero = PAIRS[c["planted"]]
    verdict = "response" if eq == "PASS" and zero == "FAIL" else "zero_reference_pass" if eq == "PASS" else "fail"
    return {"id": c["id"], "equivalence": eq, "zero_reference": zero,
            "zero_reference_paper_strict": "PASS" if t < c["margin"] else "FAIL", "zero_threshold": format(t, "f"),
            "verdict": verdict}


def report_of(name):
    return st.report(st.run(st.load_fixture(os.path.join(FIX, name))))


class PaperStrictTests(unittest.TestCase):
    """Done-when 1: the paper-strict reading beside the inclusive one, and the relabelled header."""

    def test_zero_on_edge_inclusive_pass_strict_fail(self):
        d = st.decide(contrast("-0.20", "0.20", "0", "0.20"))
        self.assertEqual((d["zero_reference"], d["zero_reference_paper_strict"], d["zero_threshold"]),
                         ("PASS", "FAIL", D("0.20")))
        self.assertTrue(st.zero_passes_paper_strict(D("-0.2"), D("0.2"), D("0.2000000000000000000000000000001")))
        self.assertFalse(st.zero_passes_paper_strict(D("-0.2"), D("0.2"), D("0.2")))
        self.assertEqual(st.critical_value(D("-0.60"), D("-0.35")), D("0.60"))

    def test_zero_on_edge_row_in_more_fixture(self):
        code, out, err = cli("--json", os.path.join(FIX, "more.json"))
        rows = [r for r in json.loads(out).get("rows", []) if r.get("id") == "zero_on_edge"]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].get("margin"), rows[0].get("zero_threshold"), rows[0].get("zero_reference"),
                          rows[0].get("zero_reference_paper_strict")), ("0.20", "0.20", "PASS", "FAIL"))
        self.assertIn("| zero_on_edge | PASS | PASS | FAIL | 0.20 | zero_reference_pass |", report_of("more.json"))

    def test_readings_around_the_critical_value(self):
        for m, inclusive, strict in (("0.1199", "FAIL", "FAIL"), ("0.12", "PASS", "FAIL"), ("0.1201", "PASS", "PASS")):
            d = st.decide(contrast("-0.05", "0.12", "0", m))
            self.assertEqual((d["zero_reference"], d["zero_reference_paper_strict"]), (inclusive, strict), m)

    def test_strict_arm_header_and_legend_are_pinned(self):
        for name in VALID:
            lines = report_of(name).splitlines()
            i = lines.index("## Arm with_zero_reference (strict)")
            self.assertEqual(lines[i + 2:i + 4], [HEADER, "|---|---|---|---|---|---|"])
            self.assertEqual(lines.count(LEGEND), 1)
            self.assertFalse([x for x in lines if "margin >=" in x or "margin >" in x])

    def test_every_report_row_exact(self):
        for name in VALID:
            lines = report_of(name).splitlines()
            for c in raw_contrasts(name):
                e = expected_row(c)
                line = "| %s | %s | %s | %s | %s | %s |" % (e["id"], e["equivalence"], e["zero_reference"],
                                                           e["zero_reference_paper_strict"], e["zero_threshold"],
                                                           e["verdict"])
                self.assertEqual(lines.count(line), 1, (name, line))

    def test_every_json_row_exact(self):
        for name in VALID:
            code, out, err = cli("--json", os.path.join(FIX, name))
            self.assertEqual((code, err), (0, ""))
            rows = json.loads(out).get("rows", [])
            raw = raw_contrasts(name)
            self.assertEqual(len(rows), len(raw))
            for row, c in zip(rows, raw):
                e = expected_row(c)
                got = {k: row.get(k) for k in e}
                self.assertEqual(got, e, (name, c["id"]))

    def test_readings_differ_summary(self):
        self.assertIn("zero-reference readings differ (inclusive PASS, paper-strict FAIL): 0\n", report_of("main.json"))
        self.assertIn("zero-reference readings differ (inclusive PASS, paper-strict FAIL): 1\n", report_of("more.json"))


class ReportTests(unittest.TestCase):
    def test_unreachable_note_is_in_the_report_text(self):
        lines = report_of("more.json").splitlines()
        note = "no candidate can match (the human interval is wider than twice the margin)"
        self.assertIn("- too_wide (human interval wider than twice the margin, SD): match window [0.40, 0.30]; FAIL; "
                      + note + "; planted genuine_fail: closed", lines)
        self.assertEqual(sum(1 for x in lines if note in x), 1)

    def test_main_fixture_arms(self):
        text = report_of("main.json")
        self.assertIn("weak arm: 2 of 3 contrasts match; it cannot say which matches show a response\n", text)
        self.assertIn("passes that show a response: 1; zero-reference passes: 1; fails: 1\n", text)
        self.assertIn("closed: 3 / 3 planted contrasts\ngate: PASS\non_expiry: DENY\n", text)
        weak = text.split("## Arm with_zero_reference")[0].split("## Arm equivalence_only (weak)")[1]
        self.assertNotIn("zero", weak.lower())
        self.assertIn("PASS, but the zero reference passes too: this does not establish a response", text)

    def test_more_fixture_notes(self):
        text = report_of("more.json")
        self.assertIn("- far_candidate (candidate far off while zero would pass, SD): match window [-0.10, 0.12]; FAIL; "
                      "the zero reference would have passed; planted fail_zero_passes: closed", text)
        self.assertIn("closed: 9 / 9 planted contrasts", text)
        self.assertIn("passes that show a response: 4; zero-reference passes: 1; fails: 4", text)


class RuleTests(unittest.TestCase):
    def test_inclusive_edges(self):
        self.assertTrue(st.equivalent(D("0.45"), D("0.25"), D("0.45"), D("0.20")))
        self.assertTrue(st.equivalent(D("0.25"), D("0.25"), D("0.45"), D("0.20")))
        self.assertFalse(st.equivalent(D("0.4500001"), D("0.25"), D("0.45"), D("0.20")))
        self.assertFalse(st.equivalent(D("0.2499999"), D("0.25"), D("0.45"), D("0.20")))

    def test_window_and_reachable(self):
        d = st.decide(contrast("0.1", "0.3", "0.2", "0.25"))
        self.assertEqual((d["match_window"], d["reachable"]), ((D("0.05"), D("0.35")), True))
        self.assertEqual(st.decide(contrast("0.1", "0.6", "0.35", "0.2"))["reachable"], False)
        self.assertEqual(st.decide(contrast("0.1", "0.5", "0.3", "0.2"))["reachable"], True)

    def test_zero_reference_inclusive(self):
        for lo, hi, m, expect in (("-0.2", "0.2", "0.2", "PASS"), ("-0.2", "0.21", "0.2", "FAIL"),
                                  ("-0.21", "0.1", "0.2", "FAIL"), ("0.05", "0.1", "0.2", "PASS"),
                                  ("-0.3", "-0.1", "0.2", "FAIL")):
            self.assertEqual(st.decide(contrast(lo, hi, "0", m))["zero_reference"], expect, (lo, hi, m))

    def test_four_verdicts(self):
        self.assertEqual(st.decide(contrast("0.25", "0.45", "0.3", "0.2"))["verdict"], "response")
        self.assertEqual(st.decide(contrast("-0.05", "0.1", "0.02", "0.2"))["verdict"], "zero_reference_pass")
        d = st.decide(contrast("-0.05", "0.1", "0.5", "0.2"))
        self.assertEqual((d["verdict"], d["note"]), ("fail", "FAIL; the zero reference would have passed"))
        d = st.decide(contrast("0.3", "0.5", "0.0", "0.2"))
        self.assertEqual((d["verdict"], d["note"]), ("fail", "FAIL"))

    def test_exact_beyond_28_digits(self):
        d = st.decide(contrast("1", "1", "0.99999999999999999999999999993", "6E-29"))
        self.assertEqual((d["equivalence"], d["match_window"][0]), ("FAIL", D("0.99999999999999999999999999994")))
        self.assertEqual(st.decide(contrast("0.5", "0.5", "0.499999999999999999999999999999", "1E-30"))["equivalence"],
                         "PASS")

    def test_gate_opens_on_wrong_planting(self):
        for planted in ("zero_reference", "genuine_fail", "fail_zero_passes"):
            res = st.run({"label": "x", "contrasts": [contrast("0.25", "0.45", "0.31", "0.2", planted)]})
            self.assertEqual((res["closed"], st.gate(res)), (0, "FAIL"), planted)
            self.assertIn("planted %s: OPEN" % planted, st.report(res))


class ContractTests(unittest.TestCase):
    """Done-when 3 and 4: exact fail-closed output, the bool case, the caps and the exponent extremes."""

    def assertDenied(self, name, line):
        self.assertEqual(cli(os.path.join(FIX, "bad", name)), (2, "", line))

    def test_bool_candidate_fails_closed_exactly(self):
        self.assertDenied("bad_candidate_bool.json", "ERROR bad_type: contrast 1 candidate must be a number (on_expiry=DENY)\n")
        self.assertEqual(deny_code(root_with(margin=True)), "bad_type")
        self.assertEqual(deny_code(root_with(human_lo=False)), "bad_type")

    def test_exponent_extremes(self):
        self.assertDenied("bad_exponent_overflow.json",
                          "ERROR out_of_range: contrast 1 candidate must be within +-100 (on_expiry=DENY)\n")
        self.assertDenied("bad_margin_overflow.json",
                          "ERROR out_of_range: contrast 1 margin must be within +-100 (on_expiry=DENY)\n")
        self.assertDenied("bad_zero_huge_exponent.json",
                          "ERROR bad_number: contrast 1 candidate must not use a positive exponent (on_expiry=DENY)\n")
        self.assertDenied("bad_positive_exponent.json",
                          "ERROR bad_number: contrast 1 candidate must not use a positive exponent (on_expiry=DENY)\n")
        self.assertDenied("bad_tiny_exponent_margin.json",
                          "ERROR bad_number: contrast 1 margin has more than 30 decimal places (on_expiry=DENY)\n")

    def test_value_just_over_the_cap(self):
        self.assertEqual(deny_code(root_with(candidate=D("100.0000000000000000000000000001"))), "out_of_range")
        self.assertEqual(deny_code(root_with(human_lo=D("-100"))), "no deny")
        self.assertEqual(deny_code(root_with(human_hi=D("100.000000000000000000000000000"))), "no deny")

    def test_validate_level_extremes(self):
        for field in ("human_lo", "human_hi", "candidate", "margin"):
            self.assertEqual(deny_code(root_with(**{field: D("1E+999999999")})), "out_of_range", field)
            self.assertEqual(deny_code(root_with(**{field: D("0E+999999999")})), "bad_number", field)
            self.assertEqual(deny_code(root_with(**{field: D("1E-999999999")})), "bad_number", field)
            self.assertEqual(deny_code(root_with(**{field: D("Infinity")})), "not_finite", field)
            self.assertEqual(deny_code(root_with(**{field: "0.3"})), "bad_type", field)
        self.assertEqual(deny_code(root_with(planted="other")), "bad_planted")
        self.assertEqual(deny_code(root_with(margin=D("0"))), "bad_margin")

    def test_bad_fixture_set_matches_folder(self):
        self.assertEqual(sorted(os.listdir(os.path.join(FIX, "bad"))), sorted(BAD_CODES))

    def test_every_bad_fixture_fails_closed(self):
        for name, code in sorted(BAD_CODES.items()):
            with self.subTest(name=name):
                path = os.path.join(FIX, "bad", name)
                try:
                    st.load_fixture(path)
                    got = "no deny"
                except st.FoldError as e:
                    got = e.code
                self.assertEqual(got, code)
                if got != code:
                    continue  # do not render a fixture the loader did not deny
                rc, out, err = cli(path)
                self.assertEqual((rc, out), (2, ""))
                self.assertEqual(err.count("\n"), 1)
                self.assertTrue(err.startswith("ERROR %s: " % code) and err.endswith(" (on_expiry=DENY)\n"), err)

    def test_missing_file_and_usage(self):
        self.assertEqual(cli(os.path.join(FIX, "nope.json")),
                         (2, "", "ERROR unreadable: fixture is missing or cannot be read (on_expiry=DENY)\n"))
        self.assertEqual(cli(), (2, "", "ERROR usage: strict_threshold.py [--json] FIXTURE.json (on_expiry=DENY)\n"))

    def test_valid_and_open_gate_exit_codes(self):
        for name in VALID:
            code, out, err = cli(os.path.join(FIX, name))
            self.assertEqual((code, err, out.endswith("gate: PASS\non_expiry: DENY\n")), (0, "", True))
        with open(os.path.join(FIX, "main.json"), encoding="utf-8") as fh:
            text = fh.read().replace('"planted": "genuine_fail"', '"planted": "real_response"')
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "open.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            code, out, err = cli(path)
        self.assertEqual((code, err, "gate: FAIL\n" in out, "planted real_response: OPEN" in out), (1, "", True, True))


class DemoTests(unittest.TestCase):
    def test_demo_is_both_reports_and_deterministic(self):
        a, b = io.StringIO(), io.StringIO()
        demo.main(a)
        demo.main(b)
        self.assertEqual(a.getvalue(), b.getvalue())
        self.assertEqual(a.getvalue(), report_of("main.json") + "\n" + report_of("more.json"))


class EvidenceTests(unittest.TestCase):
    def test_evidence(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            ev = json.load(fh)
        self.assertEqual(ev["source"]["citation_title"], "What Does Matching a Human Intervention Effect Establish? "
                         "Benchmark Checks for LLM Simulations")
        self.assertEqual((ev["source"]["arxiv"], ev["source"]["licence"]), ("2611.27186", "CC BY 4.0"))
        self.assertEqual((ev["code_copied"], ev["on_expiry"]), (False, "DENY"))
        self.assertEqual(ev["timeouts"]["mutants"], {"seconds": 300, "on_expiry": "DENY"})
        self.assertTrue(ev["on_unmeasured"])
        self.assertTrue(all(x["status"] == "UNVERIFIED" and x["reproduced"] is False for x in ev["on_unmeasured"]))
        for name in VALID:
            res = st.run(st.load_fixture(os.path.join(FIX, name)))
            got = {k: res[k] for k in ("closed", "total", "weak_passes", "responses", "zero_reference_passes",
                                       "readings_differ")}
            self.assertEqual(ev["measured"][name[:-5]], got)


class MutantsHarnessTests(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(mutants.classify(None, {}), "TIMEOUT")
        self.assertEqual(mutants.classify(mutants.LOAD_FAILED, {}), "CRASH")
        self.assertEqual(mutants.classify(0, {"failures": 0, "errors": 0}), "SURVIVED")
        self.assertEqual(mutants.classify(1, {"failures": 2, "errors": 3}), "KILLED-behaviour")
        self.assertEqual(mutants.classify(1, {"failures": 0, "errors": 3}), "CRASH")
        self.assertEqual(mutants.classify(1, {}), "CRASH")
        self.assertEqual(mutants.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})

    def test_required_mutants_present(self):
        names = [m[0] for m in mutants.MUTANTS]
        self.assertEqual(len(names), len(set(names)))
        for n in ("json_threshold_dropped_after_row0", "json_threshold_wrong_after_row0",
                  "threshold_rounded_to_2dp_in_report", "header_inclusive_relabelled", "header_strict_relabelled",
                  "json_paper_strict_dropped_after_row0", "json_paper_strict_wrong_after_row0",
                  "bool_counts_as_number", "reachable_flag_ignored_in_report"):
            self.assertIn(n, names)
