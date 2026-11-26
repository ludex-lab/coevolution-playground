"""unittest suite for zero_reference.py.  Run: python3 -B -m unittest

Every test checks behaviour through the imported module (return values, the in-process CLI, the demo output).
No test reads any Python source file. The tests call main() in-process so that mutants.py, which loads a mutated
module from memory, is exercised by every test.
"""

import decimal
import io
import json
import os
import unittest

import demo
import mutants
import zero_reference as zr

D = decimal.Decimal
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
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
    "bad_too_large.json": "too_large",
    "bad_too_many_places.json": "bad_number",
    "bad_too_many.json": "too_many",
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
}


def cli(*args):
    """In-process CLI. An unexpected exception is returned as exit 99 so that assertions fail on it."""
    out, err = io.StringIO(), io.StringIO()
    try:
        code = zr.main(["zero_reference.py"] + list(args), out, err)
    except Exception as e:  # a crash must show up as a wrong result, not hide as an error
        return 99, out.getvalue(), "CRASH %r" % (e,)
    return code, out.getvalue(), err.getvalue()


def deny_code(root):
    """The DENY code validate() raises for a parsed fixture, or a marker when it does not deny or crashes."""
    try:
        zr.validate(root)
    except zr.ZeroRefError as e:
        return e.code
    except Exception as e:
        return "crash %r" % (e,)
    return "no deny"


def contrast(lo, hi, cand, margin, planted="real_response", cid="c"):
    return {"id": cid, "label": "l", "units": "SD", "human_lo": D(lo), "human_hi": D(hi), "candidate": D(cand),
            "margin": D(margin), "planted": planted}


def rows(name):
    return {r["id"]: r for r in zr.run(zr.load_fixture(os.path.join(FIX, name)))["rows"]}


class DoneWhenTests(unittest.TestCase):
    """(a)-(d) from the pack, on fixtures/main.json."""

    def test_a_real_response_pass(self):
        r = rows("main.json")["reminder_letter"]
        self.assertEqual((r["equivalence"], r["zero_reference"], r["verdict"]), ("PASS", "FAIL", "response"))

    def test_b_zero_reference_pass_is_labelled(self):
        r = rows("main.json")["font_change"]
        self.assertEqual((r["equivalence"], r["zero_reference"], r["verdict"]), ("PASS", "PASS", "zero_reference_pass"))
        self.assertIn("does not establish a response", r["note"])

    def test_c_genuine_fail(self):
        r = rows("main.json")["peer_comparison"]
        self.assertEqual((r["equivalence"], r["zero_reference"], r["verdict"]), ("FAIL", "FAIL", "fail"))

    def test_d_zero_result_beside_every_equivalence_decision(self):
        for name in ("main.json", "more.json"):
            res = zr.run(zr.load_fixture(os.path.join(FIX, name)))
            text = zr.report(res)
            for r in res["rows"]:
                line = [x for x in text.splitlines() if x.startswith("| %s | %s | %s |" % (
                    r["id"], r["equivalence"], r["zero_reference"]))]
                self.assertEqual(len(line), 1, r["id"])
                self.assertIn("| %s |" % format(r["zero_threshold"], "f"), line[0])

    def test_weak_and_strict_arms_differ(self):
        res = zr.run(zr.load_fixture(os.path.join(FIX, "main.json")))
        self.assertEqual((res["weak_passes"], res["responses"], res["zero_reference_passes"], res["fails"]),
                         (2, 1, 1, 1))
        text = zr.report(res)
        weak = text.split("## Arm with_zero_reference")[0]
        self.assertNotIn("zero", weak.split("## Arm equivalence_only (weak)")[1].lower())
        self.assertIn("weak arm: 2 of 3 contrasts match; it cannot say which matches show a response", text)
        self.assertIn("passes that show a response: 1; zero-reference passes: 1; fails: 1", text)
        self.assertIn("closed: 3 / 3 planted contrasts", text)


class RuleTests(unittest.TestCase):
    def test_inclusive_edges(self):
        self.assertTrue(zr.equivalent(D("0.45"), D("0.25"), D("0.45"), D("0.20")))
        self.assertTrue(zr.equivalent(D("0.25"), D("0.25"), D("0.45"), D("0.20")))
        self.assertFalse(zr.equivalent(D("0.4500001"), D("0.25"), D("0.45"), D("0.20")))
        self.assertFalse(zr.equivalent(D("0.2499999"), D("0.25"), D("0.45"), D("0.20")))

    def test_window_is_hi_minus_m_to_lo_plus_m(self):
        d = zr.decide(contrast("0.1", "0.3", "0.2", "0.25"))
        self.assertEqual(d["match_window"], (D("0.05"), D("0.35")))
        self.assertTrue(d["reachable"])

    def test_zero_reference_passes_iff_interval_inside_margin(self):
        for lo, hi, m, expect in (("-0.2", "0.2", "0.2", "PASS"), ("-0.2", "0.21", "0.2", "FAIL"),
                                  ("-0.21", "0.1", "0.2", "FAIL"), ("0", "0", "0.01", "PASS"),
                                  ("0.05", "0.1", "0.2", "PASS"), ("-0.3", "-0.1", "0.2", "FAIL")):
            self.assertEqual(zr.decide(contrast(lo, hi, "0", m))["zero_reference"], expect, (lo, hi, m))

    def test_zero_threshold(self):
        self.assertEqual(zr.zero_threshold(D("-0.05"), D("0.12")), D("0.12"))
        self.assertEqual(zr.zero_threshold(D("-0.60"), D("-0.35")), D("0.60"))
        self.assertEqual(zr.zero_threshold(D("0.25"), D("0.45")), D("0.45"))
        d = zr.decide(contrast("-0.3", "0.1", "0", "0.3"))
        self.assertEqual((d["zero_threshold"], d["zero_reference"]), (D("0.3"), "PASS"))

    def test_four_verdicts(self):
        self.assertEqual(zr.decide(contrast("0.25", "0.45", "0.3", "0.2"))["verdict"], "response")
        self.assertEqual(zr.decide(contrast("-0.05", "0.1", "0.02", "0.2"))["verdict"], "zero_reference_pass")
        d = zr.decide(contrast("-0.05", "0.1", "0.5", "0.2"))
        self.assertEqual((d["verdict"], d["note"]), ("fail", "FAIL; the zero reference would have passed"))
        d = zr.decide(contrast("0.3", "0.5", "0.0", "0.2"))
        self.assertEqual((d["verdict"], d["note"]), ("fail", "FAIL"))

    def test_too_wide_interval_is_unreachable(self):
        d = zr.decide(contrast("0.1", "0.6", "0.35", "0.2"))
        self.assertEqual((d["equivalence"], d["reachable"]), ("FAIL", False))
        d = zr.decide(contrast("0.1", "0.5", "0.3", "0.2"))
        self.assertEqual((d["equivalence"], d["reachable"]), ("PASS", True))

    def test_negative_effects_are_symmetric(self):
        a = zr.decide(contrast("0.35", "0.60", "0.42", "0.2"))
        b = zr.decide(contrast("-0.60", "-0.35", "-0.42", "0.2"))
        self.assertEqual((a["equivalence"], a["zero_reference"]), (b["equivalence"], b["zero_reference"]))

    def test_exact_decimals(self):
        res = zr.run({"label": "x", "contrasts": [contrast("0.1", "0.3", "0.3", "0.2")]})
        self.assertEqual(res["rows"][0]["equivalence"], "PASS")

    def test_exact_beyond_28_digits(self):
        # 1 - 6E-29 = 0.99999999999999999999999999994 is above the candidate; 28-digit rounding would pass it
        d = zr.decide(contrast("1", "1", "0.99999999999999999999999999993", "6E-29"))
        self.assertEqual((d["equivalence"], d["match_window"][0]), ("FAIL", D("0.99999999999999999999999999994")))
        d = zr.decide(contrast("0.5", "0.5", "0.499999999999999999999999999999", "1E-30"))
        self.assertEqual(d["equivalence"], "PASS")


class GateTests(unittest.TestCase):
    def test_mismatched_planting_opens_the_gate(self):
        for planted in ("zero_reference", "genuine_fail", "fail_zero_passes"):
            res = zr.run({"label": "x", "contrasts": [contrast("0.25", "0.45", "0.31", "0.2", planted)]})
            self.assertEqual((res["closed"], zr.gate(res)), (0, "FAIL"), planted)
            self.assertIn("planted %s: OPEN" % planted, zr.report(res))
        res = zr.run({"label": "x", "contrasts": [contrast("0.25", "0.45", "0.31", "0.2")]})
        self.assertEqual(zr.gate(res), "PASS")

    def test_more_fixture(self):
        r = rows("more.json")
        self.assertEqual(r["edge_upper"]["verdict"], "response")
        self.assertEqual(r["edge_lower"]["verdict"], "response")
        self.assertEqual(r["just_outside"]["equivalence"], "FAIL")
        self.assertEqual(r["zero_on_edge"]["verdict"], "zero_reference_pass")
        self.assertEqual(r["negative_effect"]["verdict"], "response")
        self.assertEqual((r["far_candidate"]["equivalence"], r["far_candidate"]["zero_reference"]), ("FAIL", "PASS"))
        self.assertFalse(r["too_wide"]["reachable"])
        self.assertEqual(r["hangul_label"]["label"], "마을 공지 문구 변경")
        self.assertTrue(all(x["closed"] for x in r.values()))


class CliTests(unittest.TestCase):
    def test_valid_fixtures_exit_zero(self):
        for name in ("main.json", "more.json"):
            code, out, err = cli(os.path.join(FIX, name))
            self.assertEqual((code, err), (0, ""))
            self.assertIn("gate: PASS", out)

    def test_json_mode(self):
        code, out, err = cli("--json", os.path.join(FIX, "main.json"))
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["rows"][0]["zero_threshold"], "0.45")
        self.assertEqual(data["rows"][1]["verdict"], "zero_reference_pass")
        self.assertEqual(data["on_expiry"], "DENY")

    def test_bad_fixture_set_matches_folder(self):
        self.assertEqual(sorted(os.listdir(os.path.join(FIX, "bad"))), sorted(BAD_CODES))

    def test_every_bad_fixture_fails_closed(self):
        for name, code in sorted(BAD_CODES.items()):
            with self.subTest(name=name):
                rc, out, err = cli(os.path.join(FIX, "bad", name))
                self.assertEqual((rc, out), (2, ""))
                lines = err.splitlines()
                self.assertEqual(len(lines), 1)
                self.assertTrue(lines[0].startswith("ERROR %s: " % code), lines[0])

    def test_missing_folder_and_usage(self):
        for args, code in (([os.path.join(FIX, "absent.json")], "unreadable"), ([FIX], "unreadable"),
                           ([], "usage"), (["a", "b"], "usage"), (["--json"], "usage")):
            rc, out, err = cli(*args)
            self.assertEqual((rc, out), (2, ""))
            self.assertEqual(len(err.splitlines()), 1)
            self.assertTrue(err.startswith("ERROR %s" % code), err)

    def test_open_gate_exits_one(self):
        import tempfile
        with open(os.path.join(FIX, "main.json"), encoding="utf-8") as fh:
            raw = json.load(fh)
        raw["contrasts"][1]["planted"] = "real_response"
        with tempfile.TemporaryDirectory() as work:
            path = os.path.join(work, "open.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(raw, fh)
            code, out, err = cli(path)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("closed: 2 / 3 planted contrasts", out)
        self.assertIn("gate: FAIL", out)

    def test_non_finite_and_non_numbers_deny_in_validate(self):
        base = {"fixture_version": D(1), "label": "x", "contrasts": [
            {"id": "c", "label": "l", "units": "SD", "human_lo": D("0.1"), "human_hi": D("0.3"),
             "candidate": D("0.2"), "margin": D("0.2"), "planted": "real_response"}]}
        self.assertEqual(deny_code(base), "no deny")
        for field, value, code in (("candidate", D("Infinity"), "not_finite"), ("margin", D("-Infinity"), "not_finite"),
                                   ("human_lo", D("NaN"), "not_finite"), ("candidate", True, "bad_type"),
                                   ("margin", False, "bad_type"), ("candidate", 0.2, "bad_type"),
                                   ("planted", "other", "bad_planted"),
                                   ("candidate", D("100.0000000000000000000000000001"), "out_of_range"),
                                   ("margin", D("1E+999999999"), "out_of_range")):
            root = {"fixture_version": D(1), "label": "x", "contrasts": [dict(base["contrasts"][0], **{field: value})]}
            self.assertEqual(deny_code(root), code, (field, value))

    def test_caps(self):
        self.assertTrue(all(v["on_expiry"] == "DENY" for v in zr.CAPS.values()))
        self.assertEqual(zr.ON_EXPIRY, "DENY")
        ok = {"fixture_version": D(1), "label": "x", "contrasts": [
            {"id": "c%d" % i, "label": "l", "units": "SD", "human_lo": D("-100"), "human_hi": D("100"),
             "candidate": D(0), "margin": D("100"), "planted": "zero_reference"} for i in range(200)]}
        self.assertEqual(len(zr.validate(ok)["contrasts"]), 200)


class DemoTests(unittest.TestCase):
    def test_demo_is_deterministic(self):
        a, b = io.StringIO(), io.StringIO()
        self.assertEqual(demo.main(a), 0)
        demo.main(b)
        self.assertEqual(a.getvalue(), b.getvalue())
        text = a.getvalue()
        self.assertIn("| reminder_letter | PASS | FAIL | 0.45 | response |", text)
        self.assertIn("| font_change | PASS | PASS | 0.12 | zero_reference_pass |", text)
        self.assertIn("| peer_comparison | FAIL | FAIL | 0.50 | fail |", text)
        self.assertIn("closed: 8 / 8 planted contrasts", text)
        self.assertNotIn(HERE, text)


class EvidenceTests(unittest.TestCase):
    def test_evidence(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            ev = json.load(fh)
        self.assertEqual(ev["source"]["citation_title"], "What Does Matching a Human Intervention Effect Establish? "
                                                         "Benchmark Checks for LLM Simulations")
        self.assertEqual(ev["source"]["licence"], "CC BY 4.0")
        self.assertEqual(ev["on_expiry"], "DENY")
        figures = " ".join(u["what"] for u in ev["on_unmeasured"])
        for fig in ("72 percent", "16 contrasts", "1.58", "70-experiment", "0.20 SD"):
            self.assertIn(fig, figures)
        self.assertTrue(all(u["status"] == "UNVERIFIED" for u in ev["on_unmeasured"]))
        res = zr.run(zr.load_fixture(os.path.join(FIX, "main.json")))
        m = ev["measured"]["main"]
        self.assertEqual((m["closed"], m["total"], m["equivalence_passes"], m["responses"],
                          m["zero_reference_passes"]), (res["closed"], res["total"], res["weak_passes"],
                                                        res["responses"], res["zero_reference_passes"]))
        self.assertEqual(ev["timeouts"]["mutants"], {"seconds": mutants.TIMEOUT["seconds"], "on_expiry": "DENY"})


class MutantsHarnessTests(unittest.TestCase):
    def test_timeout_is_deny_never_a_kill(self):
        self.assertEqual(mutants.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})
        self.assertEqual(mutants.classify(None, ""), "TIMEOUT")

    def test_classification(self):
        self.assertEqual(mutants.classify(0, "OK"), "SURVIVED")
        self.assertEqual(mutants.classify(1, "FAILED (failures=2)"), "KILLED")
        self.assertEqual(mutants.classify(1, "FAILED (failures=1, errors=3)"), "KILLED")
        self.assertEqual(mutants.classify(1, "FAILED (errors=2)"), "CRASH")
        self.assertEqual(mutants.classify(mutants.IMPORT_FAILED, "boom"), "CRASH")
        self.assertEqual(mutants.classify(1, "no summary"), "CRASH")

    def test_summary(self):
        self.assertEqual(mutants.summary(["KILLED", "TIMEOUT", "CRASH", "SURVIVED", "KILLED"]),
                         "mutants k/t/c: 2/1/1 (survived 1 of 5; a timeout or crash is never a kill; on_expiry DENY)")


if __name__ == "__main__":
    unittest.main()
