import copy
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import level_rank as lr

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
PY = sys.executable
Fraction = lr.Fraction
S20 = [2, 3, 5, 8, 9, 12, 14, 15, 19, 21, 24, 26, 29, 31, 33, 38, 40, 45, 52, 90]


def raw(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def case(helper="linear", convention="one_sided", scores=None, alpha="0.10", cid="x"):
    scores = list(S20) if scores is None else scores
    return {"id": cid, "helper": helper, "convention": convention, "declared_n": len(scores),
            "declared_alpha": alpha, "alpha": alpha, "scores": scores}


def run_cases(*cases):
    return lr.run(lr.validate({"fixture_version": 1, "on_expiry": "DENY", "cases": list(cases)}))


def row_of(**kw):
    return run_cases(case(**kw))["rows"][0]


def error_code(test, mutate, name="main.json"):
    root = raw(name)
    mutate(root)
    with test.assertRaises(lr.RankError) as cm:
        lr.run(lr.validate(root))
    return cm.exception.code


def cli(*args):
    p = subprocess.run([PY, "-B", os.path.join(HERE, "level_rank.py")] + list(args), cwd=HERE,
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


class RequiredRank(unittest.TestCase):
    def test_known_ranks(self):
        for n, alpha, want in ((20, "0.10", 19), (20, "0.05", 20), (9, "0.10", 9), (8, "0.10", 9), (1, "0.5", 1),
                               (1, "0.4", 2), (100, "0.10", 91), (19, "0.05", 19), (18, "0.05", 19)):
            self.assertEqual(lr.required_rank(n, alpha), want, (n, alpha))

    def test_the_abstract_case_n20_level_090_needs_rank_19(self):
        self.assertEqual(lr.required_rank(20, "0.10"), 19)
        self.assertEqual("%d/%d" % (19, 20 + 1), "19/21")
        self.assertEqual(row_of(helper="conformal_rank")["guarantee_at_required_rank"], "19/21")

    def test_float_ceil_disagrees_with_the_exact_rank_at_n149_alpha_018(self):
        self.assertEqual(lr.required_rank(149, "0.18"), 123)
        self.assertEqual(math.ceil((149 + 1) * (1 - 0.18)), 124)
        self.assertEqual(lr.required_rank(149, "0.18"), math.ceil(Fraction(150) * (1 - Fraction(18, 100))))

    def test_the_other_float_disagreements(self):
        for n, a, want in ((249, "0.18", 205), (299, "0.18", 246), (299, "0.19", 243)):
            self.assertEqual(lr.required_rank(n, a), want)
        self.assertEqual(math.ceil((249 + 1) * (1 - 0.18)), 206)
        self.assertEqual(math.ceil((299 + 1) * (1 - 0.18)), 247)
        self.assertEqual(math.ceil((299 + 1) * (1 - 0.19)), 244)

    def test_a_float_alpha_is_refused(self):
        for bad in (0.18, 0.1, 1e-1, 0.0):
            with self.assertRaises(lr.RankError) as cm:
                lr.required_rank(149, bad)
            self.assertEqual(cm.exception.code, "bad_alpha")

    def test_grid_of_6000_cases_matches_an_integer_oracle_and_float_disagrees_4_times(self):
        float_off = []
        for n in range(1, 301):
            for a in range(1, 21):
                oracle = -((-(n + 1) * (100 - a)) // 100)
                got = lr.required_rank(n, "0.%02d" % a)
                self.assertEqual(got, oracle, (n, a))
                if math.ceil((n + 1) * (1 - a / 100)) != oracle:
                    float_off.append((n, a, oracle, math.ceil((n + 1) * (1 - a / 100))))
        self.assertEqual(float_off, [(149, 18, 123, 124), (249, 18, 205, 206), (299, 18, 246, 247), (299, 19, 243, 244)])

    def test_feasibility_floor_is_n_at_least_one_over_alpha_minus_one(self):
        for n in range(1, 301):
            for a in range(1, 21):
                alpha = Fraction(a, 100)
                self.assertEqual(lr.feasible(n, "0.%02d" % a), Fraction(n) >= 1 / alpha - 1, (n, a))

    def test_the_floor_is_exactly_where_rank_n_stops_being_reachable(self):
        self.assertTrue(lr.feasible(9, "0.10"))
        self.assertFalse(lr.feasible(8, "0.10"))
        self.assertTrue(lr.feasible(19, "0.05"))
        self.assertFalse(lr.feasible(18, "0.05"))
        self.assertEqual(lr.required_rank(8, "0.10"), 9)
        self.assertEqual(lr.required_rank(9, "0.10"), 9)

    def test_rank_never_exceeds_n_plus_one_and_is_at_least_one(self):
        for n in (1, 2, 7, 50):
            for a in ("0.01", "0.5", "0.99", "0.999999"):
                r = lr.required_rank(n, a)
                self.assertTrue(1 <= r <= n + 1)

    def test_n_must_be_a_plain_positive_integer(self):
        for bad in (0, -1, True, 1.0, "20", None):
            with self.assertRaises(lr.RankError) as cm:
                lr.required_rank(bad, "0.10")
            self.assertEqual(cm.exception.code, "bad_n")

    def test_parse_alpha(self):
        self.assertEqual(lr.parse_alpha("0.10"), Fraction(1, 10))
        self.assertEqual(lr.parse_alpha("0.1"), Fraction(1, 10))
        self.assertEqual(lr.parse_alpha("0.000001"), Fraction(1, 10 ** 6))
        for bad in ("1.0", "0.0", "0", "1", "-0.1", ".1", "0.", "0.1234567", "1e-1", "0,1", " 0.1", "0.1 ", "0.\u0661",
                    "0.1\u200b", "10%", "", 0.1, None, 1, "0.10\n"):
            with self.assertRaises(lr.RankError, msg=repr(bad)) as cm:
                lr.parse_alpha(bad)
            self.assertEqual(cm.exception.code, "bad_alpha")

    def test_floor_n_is_the_smallest_feasible_n(self):
        for a in range(1, 100):
            alpha = "0.%02d" % a
            row = row_of(helper="conformal_rank", scores=[1] * 400, alpha=alpha)
            smallest = next(n for n in range(1, 10 ** 4) if lr.feasible(n, alpha))
            self.assertEqual(row["feasibility_floor_n"], smallest, alpha)
            self.assertFalse(lr.feasible(smallest - 1, alpha) if smallest > 1 else False)

    def test_alpha_one_minus_tiny_is_accepted_and_zero_is_not(self):
        self.assertEqual(lr.parse_alpha("0.999999"), Fraction(999999, 10 ** 6))
        with self.assertRaises(lr.RankError):
            lr.parse_alpha("0.000000")


class Convention(unittest.TestCase):
    def test_pinned_texts(self):
        self.assertEqual(lr.CONVENTIONS, ("one_sided", "two_sided_upper"))
        self.assertEqual(lr.Q_RULES, {"one_sided": "q = 1 - alpha", "two_sided_upper": "q = 1 - alpha/2"})
        self.assertEqual(lr.RANK_RULE, "r = ceil((n + 1) * (1 - alpha)), guarantee r / (n + 1)")
        self.assertEqual(lr.FLOOR_RULE, "r <= n, the same as n >= 1/alpha - 1")

    def test_q_levels(self):
        a = Fraction(1, 10)
        self.assertEqual(lr.q_level("one_sided", a), Fraction(9, 10))
        self.assertEqual(lr.q_level("two_sided_upper", a), Fraction(19, 20))
        self.assertEqual(lr.q_level("one_sided", Fraction(1, 20)), Fraction(19, 20))

    def test_unknown_convention(self):
        with self.assertRaises(lr.RankError) as cm:
            lr.q_level("lower", Fraction(1, 10))
        self.assertEqual(cm.exception.code, "unknown_convention")

    def test_q_095_is_where_position_18_05_comes_from(self):
        n = 20
        self.assertEqual(lr.helper_position("linear", n, Fraction(19, 20)), Fraction(361, 20))
        self.assertEqual(lr.num(Fraction(361, 20)), "18.05")
        self.assertEqual(lr.helper_position("linear", n, Fraction(9, 10)), Fraction(171, 10))
        self.assertEqual(lr.num(Fraction(171, 10)), "17.1")

    def test_the_two_conventions_classify_the_same_helper_differently(self):
        one = row_of(helper="linear", convention="one_sided")
        two = row_of(helper="linear", convention="two_sided_upper")
        self.assertEqual((one["q"], one["position"], one["direction"]), ("0.9", "17.1", "below"))
        self.assertEqual((two["q"], two["position"], two["direction"]), ("0.95", "18.05", "above"))
        self.assertEqual(one["required_rank"], two["required_rank"])

    def test_conformal_rank_helper_ignores_the_convention(self):
        a = row_of(helper="conformal_rank", convention="one_sided")
        b = row_of(helper="conformal_rank", convention="two_sided_upper")
        a.pop("convention"), b.pop("convention"), a.pop("q"), b.pop("q")
        self.assertEqual(a, b)


class Positions(unittest.TestCase):
    q = Fraction(9, 10)

    def test_linear_is_the_zero_based_numpy_position(self):
        self.assertEqual(lr.helper_position("linear", 20, self.q), Fraction(171, 10))
        self.assertEqual(lr.helper_position("linear", 5, Fraction(1, 2)), Fraction(2))

    def test_weibull(self):
        self.assertEqual(lr.helper_position("weibull", 20, self.q), Fraction(179, 10))
        self.assertEqual(lr.helper_position("weibull", 100, Fraction(1, 2)), Fraction(101, 2) - 1)

    def test_higher(self):
        self.assertEqual(lr.helper_position("higher", 20, self.q), Fraction(18))
        self.assertEqual(lr.helper_position("higher", 20, Fraction(19, 20)), Fraction(19))

    def test_positions_are_clamped_to_the_bag(self):
        self.assertEqual(lr.helper_position("weibull", 8, self.q), Fraction(7))
        self.assertEqual(lr.helper_position("weibull", 3, Fraction(1, 100)), Fraction(0))
        self.assertEqual(lr.helper_position("linear", 1, self.q), Fraction(0))

    def test_unknown_helper(self):
        with self.assertRaises(lr.RankError) as cm:
            lr.helper_position("nearest", 20, self.q)
        self.assertEqual(cm.exception.code, "unknown_helper")

    def test_value_at_interpolates_exactly(self):
        s = sorted(S20)
        self.assertEqual(lr.value_at(s, Fraction(18)), 52)
        self.assertEqual(lr.value_at(s, Fraction(171, 10)), Fraction(457, 10))
        self.assertEqual(lr.value_at(s, Fraction(361, 20)), Fraction(539, 10))
        self.assertEqual(lr.value_at(s, Fraction(19)), 90)
        self.assertEqual(lr.value_at([5], Fraction(0)), 5)

    def test_num_formatting(self):
        for f, want in ((Fraction(361, 20), "18.05"), (Fraction(3), "3"), (Fraction(1, 3), "1/3"), (Fraction(-7, 4), "-1.75"),
                        (Fraction(1, 8), "0.125"), (Fraction(1, 20), "0.05"), (Fraction(0), "0"), (Fraction(-1, 2), "-0.5"),
                        (Fraction(1001, 1000), "1.001"), (Fraction(22, 7), "22/7")):
            self.assertEqual(lr.num(f), want)


class MainFixture(unittest.TestCase):
    def setUp(self):
        self.result = lr.run(lr.load_fixture(os.path.join(FIX, "main.json")))
        self.rows = {r["case"]: r for r in self.result["rows"]}

    def test_decisions(self):
        self.assertEqual({k: r["decision"] for k, r in self.rows.items()}, {
            "c01_n20_linear_one_sided": "WRONG_RANK", "c02_n20_linear_two_sided_upper": "WRONG_RANK",
            "c03_n20_weibull_one_sided": "WRONG_RANK", "c04_n20_higher_one_sided": "REACHES_RANK",
            "c05_n20_rank_helper": "REACHES_RANK", "c06_n9_boundary_rank_helper": "REACHES_RANK",
            "c07_n8_rank_helper_refuses": "REFUSED_BELOW_FLOOR", "c08_n20_alpha05_linear_one_sided": "WRONG_RANK"})
        self.assertEqual(self.result["totals"], {"REACHES_RANK": 3, "WRONG_RANK": 4, "REFUSED_BELOW_FLOOR": 1, "DENY": 0})

    def test_n20_level_090_required_rank_is_19_and_17_1_is_not_it(self):
        r = self.rows["c01_n20_linear_one_sided"]
        self.assertEqual((r["n"], r["alpha"], r["required_rank"], r["required_index"]), (20, "0.1", 19, 18))
        self.assertEqual((r["position"], r["position_one_based"], r["direction"]), ("17.1", "18.1", "below"))
        self.assertEqual((r["value_at_position"], r["value_at_required_rank"]), ("45.7", "52"))

    def test_position_18_05_is_reported_as_not_that_rank(self):
        r = self.rows["c02_n20_linear_two_sided_upper"]
        self.assertEqual((r["position"], r["position_one_based"]), ("18.05", "19.05"))
        self.assertEqual((r["required_rank"], r["required_index"]), (19, 18))
        self.assertEqual((r["decision"], r["direction"]), ("WRONG_RANK", "above"))
        self.assertEqual((r["value_at_position"], r["value_at_required_rank"]), ("53.9", "52"))

    def test_weibull_lands_at_17_9(self):
        r = self.rows["c03_n20_weibull_one_sided"]
        self.assertEqual((r["position"], r["direction"]), ("17.9", "below"))

    def test_reaching_the_required_rank_is_admitted(self):
        for cid in ("c04_n20_higher_one_sided", "c05_n20_rank_helper"):
            r = self.rows[cid]
            self.assertEqual((r["decision"], r["position"], r["direction"]), ("REACHES_RANK", "18", None))
            self.assertEqual(r["value_at_position"], r["value_at_required_rank"])
            self.assertEqual(r["guarantee_at_required_rank"], "19/21")

    def test_boundary_n9_reaches_rank_9(self):
        r = self.rows["c06_n9_boundary_rank_helper"]
        self.assertEqual((r["required_rank"], r["feasible"], r["decision"]), (9, True, "REACHES_RANK"))
        self.assertEqual(r["feasibility_floor_n"], 9)

    def test_n8_is_below_the_floor_and_is_refused(self):
        r = self.rows["c07_n8_rank_helper_refuses"]
        self.assertEqual((r["required_rank"], r["feasible"], r["decision"]), (9, False, "REFUSED_BELOW_FLOOR"))
        self.assertIsNone(r["position"])
        self.assertIsNone(r["guarantee_at_required_rank"])
        self.assertEqual(r["feasibility_floor_n"], 9)

    def test_alpha_005_case(self):
        r = self.rows["c08_n20_alpha05_linear_one_sided"]
        self.assertEqual((r["required_rank"], r["position"], r["direction"]), (20, "18.05", "below"))

    def test_a_wrong_rank_has_no_stated_guarantee_in_the_report_of_its_helper(self):
        r = self.rows["c01_n20_linear_one_sided"]
        self.assertEqual(r["guarantee_at_required_rank"], "19/21")
        self.assertNotEqual(r["decision"], "REACHES_RANK")

    def test_report_is_deterministic_and_order_free_in_the_bag(self):
        fx = lr.load_fixture(os.path.join(FIX, "main.json"))
        self.assertEqual(lr.report(fx), lr.report(fx))
        a = case(scores=list(S20))
        b = case(scores=list(reversed(S20)))
        self.assertEqual(run_cases(a), run_cases(b))

    def test_ties_in_the_bag(self):
        r = row_of(scores=[5] * 20)
        self.assertEqual(r["value_at_position"], "5")
        self.assertEqual(r["decision"], "WRONG_RANK")


class BelowFloor(unittest.TestCase):
    def setUp(self):
        self.rows = {r["case"]: r for r in lr.run(lr.load_fixture(os.path.join(FIX, "below_floor.json")))["rows"]}

    def test_finite_ends_below_the_floor_are_denied(self):
        for cid in ("f01_n8_linear_finite_end", "f02_n8_weibull_finite_end", "f03_n8_higher_finite_end", "f06_n3_linear_finite_end"):
            r = self.rows[cid]
            self.assertEqual((r["decision"], r["code"]), ("DENY", "finite_end_below_floor"), cid)
            self.assertIn("no rank reaches the level", r["detail"])

    def test_refusing_below_the_floor_is_the_closed_behaviour(self):
        self.assertEqual(self.rows["f04_n8_rank_helper_refuses"]["decision"], "REFUSED_BELOW_FLOOR")

    def test_boundary_just_inside_the_floor_is_not_a_floor_denial(self):
        r = self.rows["f05_n4_boundary_linear"]
        self.assertEqual((r["decision"], r["required_rank"], r["feasible"]), ("WRONG_RANK", 4, True))

    def test_every_helper_that_returns_a_finite_end_is_denied_below_the_floor(self):
        for helper in ("linear", "weibull", "higher"):
            for conv in lr.CONVENTIONS:
                r = row_of(helper=helper, convention=conv, scores=S20[:8])
                self.assertEqual((r["decision"], r["code"]), ("DENY", "finite_end_below_floor"), (helper, conv))

    def test_same_bag_one_more_score_is_no_longer_a_floor_denial(self):
        r = row_of(helper="linear", scores=S20[:9])
        self.assertEqual(r["decision"], "WRONG_RANK")

    def test_detail_names_the_numbers(self):
        r = self.rows["f01_n8_linear_finite_end"]
        self.assertEqual(r["detail"], "helper linear returned a finite end at position 6.3 although no rank reaches the level (r=9 > n=8)")


class Denied(unittest.TestCase):
    def test_every_row(self):
        rows = lr.run(lr.load_fixture(os.path.join(FIX, "denied.json")))["rows"]
        got = [(r["case"], r["decision"], r.get("code")) for r in rows]
        self.assertEqual(got, [
            ("c05_n20_rank_helper", "REACHES_RANK", None),
            ("m01_missing_scores", "DENY", "missing_scores"),
            ("m02_missing_level", "DENY", "missing_level"),
            ("m03_n_changed", "DENY", "n_changed"),
            ("m04_level_changed", "DENY", "level_changed"),
            ("m05_same_level_other_text", "WRONG_RANK", None)])

    def test_check_order(self):
        c = case()
        c["scores"] = None
        c["alpha"] = None
        self.assertEqual(run_cases(c)["rows"][0]["code"], "missing_scores")
        c = case()
        c["alpha"] = None
        c["declared_n"] = 99
        self.assertEqual(run_cases(c)["rows"][0]["code"], "missing_level")
        c = case()
        c["declared_n"] = 19
        c["declared_alpha"] = "0.05"
        self.assertEqual(run_cases(c)["rows"][0]["code"], "n_changed")

    def test_n_changed_in_both_directions(self):
        for dn in (19, 21, 1):
            c = case()
            c["declared_n"] = dn
            self.assertEqual(run_cases(c)["rows"][0]["code"], "n_changed")

    def test_level_changed_in_both_directions(self):
        for da in ("0.05", "0.20", "0.11"):
            c = case()
            c["declared_alpha"] = da
            self.assertEqual(run_cases(c)["rows"][0]["code"], "level_changed")

    def test_the_same_level_written_another_way_is_not_a_change(self):
        c = case()
        c["declared_alpha"] = "0.1000"
        self.assertEqual(run_cases(c)["rows"][0]["decision"], "WRONG_RANK")

    def test_a_denied_case_does_not_change_the_others(self):
        solo = run_cases(case(cid="b"))["rows"][0]
        bad = case(cid="a")
        bad["scores"] = None
        rows = run_cases(bad, case(cid="b"))["rows"]
        self.assertEqual(rows[0]["decision"], "DENY")
        self.assertEqual(rows[1], solo)

    def test_deny_rows_have_no_rank_fields(self):
        c = case()
        c["alpha"] = None
        self.assertEqual(set(run_cases(c)["rows"][0]), {"case", "decision", "code", "detail"})


class Validation(unittest.TestCase):
    def test_codes(self):
        cases = [
            ("missing_key", lambda r: r.pop("cases")),
            ("missing_key", lambda r: r["cases"][0].pop("scores")),
            ("missing_key", lambda r: r["cases"][0].pop("declared_alpha")),
            ("unknown_key", lambda r: r.__setitem__("extra", 1)),
            ("unknown_key", lambda r: r["cases"][0].__setitem__("extra", 1)),
            ("wrong_type", lambda r: r.__setitem__("cases", {})),
            ("wrong_type", lambda r: r.__setitem__("cases", [])),
            ("wrong_type", lambda r: r["cases"].__setitem__(0, [])),
            ("bad_version", lambda r: r.__setitem__("fixture_version", 2)),
            ("bad_version", lambda r: r.__setitem__("fixture_version", True)),
            ("bad_on_expiry", lambda r: r.__setitem__("on_expiry", "HOLD")),
            ("bad_on_expiry", lambda r: r.__setitem__("on_expiry", "ESCALATE")),
            ("bad_on_expiry", lambda r: r.__setitem__("on_expiry", None)),
            ("bad_alpha", lambda r: r["cases"][0].__setitem__("alpha", 0.1)),
            ("bad_alpha", lambda r: r["cases"][0].__setitem__("alpha", "1.0")),
            ("bad_alpha", lambda r: r["cases"][0].__setitem__("alpha", "0.0")),
            ("bad_alpha", lambda r: r["cases"][0].__setitem__("declared_alpha", None)),
            ("bad_alpha", lambda r: r["cases"][0].__setitem__("declared_alpha", 0.1)),
            ("bad_scores", lambda r: r["cases"][0].__setitem__("scores", [])),
            ("bad_scores", lambda r: r["cases"][0].__setitem__("scores", {})),
            ("bad_scores", lambda r: r["cases"][0]["scores"].__setitem__(0, 1.5)),
            ("bad_scores", lambda r: r["cases"][0]["scores"].__setitem__(0, True)),
            ("bad_scores", lambda r: r["cases"][0]["scores"].__setitem__(0, "2")),
            ("bad_scores", lambda r: r["cases"][0]["scores"].__setitem__(0, None)),
            ("bad_scores", lambda r: r["cases"][0]["scores"].__setitem__(0, 10 ** 12)),
            ("bad_scores", lambda r: r["cases"][0]["scores"].__setitem__(0, -10 ** 12)),
            ("bad_scores", lambda r: r["cases"][0].__setitem__("scores", [1] * 5001)),
            ("bad_n", lambda r: r["cases"][0].__setitem__("declared_n", 0)),
            ("bad_n", lambda r: r["cases"][0].__setitem__("declared_n", True)),
            ("bad_n", lambda r: r["cases"][0].__setitem__("declared_n", 20.0)),
            ("bad_n", lambda r: r["cases"][0].__setitem__("declared_n", "20")),
            ("bad_n", lambda r: r["cases"][0].__setitem__("declared_n", 5001)),
            ("unknown_helper", lambda r: r["cases"][0].__setitem__("helper", "nearest")),
            ("unknown_helper", lambda r: r["cases"][0].__setitem__("helper", None)),
            ("unknown_convention", lambda r: r["cases"][0].__setitem__("convention", "lower")),
            ("unknown_convention", lambda r: r["cases"][0].__setitem__("convention", "ONE_SIDED")),
            ("bad_id", lambda r: r["cases"][0].__setitem__("id", "c 01")),
            ("bad_id", lambda r: r["cases"][0].__setitem__("id", "c\u200b01")),
            ("bad_id", lambda r: r["cases"][0].__setitem__("id", "")),
            ("bad_id", lambda r: r["cases"][0].__setitem__("id", "c01\n")),
            ("duplicate_name", lambda r: r["cases"][1].__setitem__("id", r["cases"][0]["id"])),
        ]
        for code, mutate in cases:
            self.assertEqual(error_code(self, mutate), code, code)

    def test_a_bad_convention_is_rejected_even_when_the_helper_ignores_it(self):
        root = raw("main.json")
        root["cases"][4]["convention"] = "lower"
        with self.assertRaises(lr.RankError) as cm:
            lr.validate(root)
        self.assertEqual(cm.exception.code, "unknown_convention")

    def test_bag_limits_are_inclusive(self):
        c = case(scores=[1] * 5000)
        self.assertEqual(run_cases(c)["rows"][0]["n"], 5000)
        c = case(scores=[10 ** 9, -10 ** 9], alpha="0.5")
        self.assertEqual(run_cases(c)["rows"][0]["n"], 2)

    def test_strict_json(self):
        for text, code in (("{ not json", "not_json"), ("", "not_json"), ('{"a": 1, "a": 2}', "duplicate_key"),
                           ('{"a": NaN}', "bad_number"), ('{"a": Infinity}', "bad_number"), ('{"a": -Infinity}', "bad_number"),
                           ("[" * 10000 + "]" * 10000, "not_json"), ('{"a": ' + "9" * 5000 + "}", "not_json")):
            with self.assertRaises(lr.RankError, msg=text[:20]) as cm:
                lr.parse(text)
            self.assertEqual(cm.exception.code, code)

    def test_error_details_escape_odd_key_text(self):
        root = raw("main.json")
        root["cases"][0]["x\nINJECT"] = 1
        with self.assertRaises(lr.RankError) as cm:
            lr.validate(root)
        self.assertNotIn("\n", cm.exception.detail)

    def test_error_details_are_ascii(self):
        root = raw("main.json")
        root["cases"][0]["x\u0430\u200b"] = 1
        with self.assertRaises(lr.RankError) as cm:
            lr.validate(root)
        self.assertTrue(cm.exception.detail.isascii())
        self.assertIn("\\u0430", cm.exception.detail)

    def test_load_fixture_errors(self):
        for path, code in ((os.path.join(FIX, "none.json"), "unreadable"), (FIX, "unreadable")):
            with self.assertRaises(lr.RankError) as cm:
                lr.load_fixture(path)
            self.assertEqual(cm.exception.code, code)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            with open(p, "wb") as fh:
                fh.write(b"\xff\xfe{}")
            with self.assertRaises(lr.RankError) as cm:
                lr.load_fixture(p)
            self.assertEqual(cm.exception.code, "bad_encoding")


class Cli(unittest.TestCase):
    def test_main_exits_zero(self):
        rc, out, err = cli(os.path.join("fixtures", "main.json"))
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(out, lr.report(lr.load_fixture(os.path.join(FIX, "main.json"))))
        self.assertEqual(json.loads(out)["totals"]["DENY"], 0)

    def test_refusing_below_the_floor_still_exits_zero(self):
        c = case(helper="conformal_rank", scores=S20[:8])
        rows = run_cases(c)["rows"]
        self.assertEqual(rows[0]["decision"], "REFUSED_BELOW_FLOOR")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "f.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"fixture_version": 1, "on_expiry": "DENY", "cases": [c]}, fh)
            rc, out, err = cli(p)
        self.assertEqual((rc, err), (0, ""))

    def test_deny_rows_exit_two_with_report_and_empty_stderr(self):
        for name, denies in (("below_floor.json", 4), ("denied.json", 4)):
            rc, out, err = cli(os.path.join("fixtures", name))
            self.assertEqual((rc, err), (2, ""), name)
            self.assertEqual(json.loads(out)["totals"]["DENY"], denies)

    def test_deny_after_a_clean_first_row_still_exits_two(self):
        rc, out, err = cli(os.path.join("fixtures", "below_floor.json"))
        rows = json.loads(out)["rows"]
        self.assertNotEqual(rows[0]["decision"], "DENY")
        self.assertEqual(rc, 2)

    def test_every_bad_fixture_exits_two_with_one_error_line(self):
        names = sorted(n for n in os.listdir(FIX) if n.startswith("bad_"))
        self.assertEqual(len(names), 32)
        for n in names:
            rc, out, err = cli(os.path.join("fixtures", n))
            self.assertEqual((rc, out), (2, ""), n)
            self.assertTrue(err.startswith("ERROR "), n)
            self.assertEqual(err.count("\n"), 1, n)

    def test_bad_fixture_codes(self):
        expect = {"bad_alpha_float.json": "bad_alpha", "bad_alpha_exponent.json": "bad_alpha", "bad_alpha_zero.json": "bad_alpha",
                  "bad_alpha_unicode_digit.json": "bad_alpha", "bad_nan.json": "bad_number", "bad_overflow.json": "bad_scores",
                  "bad_duplicate_key.json": "duplicate_key", "bad_not_json.json": "not_json", "bad_on_expiry.json": "bad_on_expiry",
                  "bad_scores_float.json": "bad_scores", "bad_deep_nesting.json": "not_json", "bad_bigint.json": "not_json"}
        for n, code in expect.items():
            rc, out, err = cli(os.path.join("fixtures", n))
            self.assertTrue(err.startswith("ERROR %s: " % code), (n, err))

    def test_usage_and_missing_file(self):
        for args in ((), ("a", "b")):
            rc, out, err = cli(*args)
            self.assertEqual((rc, out), (2, ""))
            self.assertTrue(err.startswith("ERROR usage:"))
        rc, out, err = cli("fixtures/nothing.json")
        self.assertEqual((rc, out), (2, ""))
        self.assertTrue(err.startswith("ERROR unreadable:"))

    def test_main_function_streams(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = lr.main(["x", os.path.join(FIX, "main.json")])
        self.assertEqual((rc, err.getvalue()), (0, ""))
        self.assertTrue(out.getvalue().startswith("{"))


class Demo(unittest.TestCase):
    def run_demo(self):
        p = subprocess.run([PY, "-B", os.path.join(HERE, "demo.py")], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual((p.returncode, p.stderr), (0, ""))
        return p.stdout

    def test_demo_is_deterministic(self):
        self.assertEqual(self.run_demo(), self.run_demo())

    def test_demo_shows_the_conventions_and_the_positions(self):
        out = self.run_demo()
        self.assertIn(lr.Q_RULES["one_sided"], out)
        self.assertIn(lr.Q_RULES["two_sided_upper"], out)
        self.assertIn("17.1", out)
        self.assertIn("18.05", out)
        self.assertIn("required rank 19", out)
        self.assertIn("WRONG_RANK", out)
        self.assertIn("DENY finite_end_below_floor", out)


class Hygiene(unittest.TestCase):
    def source(self, name):
        with open(os.path.join(HERE, name), encoding="utf-8") as fh:
            return fh.read()

    def test_stdlib_imports_only(self):
        mods = set()
        for line in self.source("level_rank.py").splitlines():
            if line.startswith(("import ", "from ")):
                mods.add(line.split()[1])
        self.assertEqual(mods, {"fractions", "json", "math", "re", "sys"})

    def test_no_float_arithmetic_in_the_module(self):
        src = self.source("level_rank.py")
        self.assertNotIn("float(", src)
        self.assertNotIn("decimal", src.lower().replace("decimal string", "").replace("exact decimal", "").replace("decimal such", ""))
        self.assertNotIn("import numpy", src)

    def test_rank_is_computed_with_fraction(self):
        src = self.source("level_rank.py")
        self.assertIn("return math.ceil((n + 1) * (1 - a))", src)
        self.assertIn("alpha = Fraction(text)", src)

    def test_evidence_json(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            ev = json.load(fh)
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.23329")
        self.assertEqual(ev["paper"]["title"],
                         "A level is not a rank: an empirical audit of quantile-to-index conversion in 10 released conformal-prediction libraries")
        self.assertIn("arXiv nonexclusive-distrib 1.0", ev["paper"]["licence"])
        self.assertTrue(ev["paper"]["method_only"])
        self.assertIn("MIT", ev["artifact"]["licence"])
        self.assertTrue(ev["artifact"]["nothing_copied"])
        self.assertEqual(ev["conventions"]["q"], lr.Q_RULES)
        self.assertEqual(ev["conventions"]["rank"], lr.RANK_RULE)
        self.assertEqual(ev["conventions"]["floor"], lr.FLOOR_RULE)
        claims = ev["on_unmeasured"]["claims"]
        self.assertGreaterEqual(len(claims), 8)
        self.assertEqual({c["status"] for c in claims}, {"UNVERIFIED"})
        self.assertEqual(len({c["id"] for c in claims}), len(claims))
        self.assertEqual(ev["measured"]["n20_alpha010"]["required_rank"], 19)
        self.assertEqual(ev["measured"]["n20_alpha010"]["linear_position_0based"], {"q=0.90": "17.1", "q=0.95": "18.05"})
        self.assertEqual(ev["measured"]["float_ceil_disagreements_on_6000_grid"], 4)

    def test_paper_numbers_appear_only_under_on_unmeasured(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            ev = json.load(fh)
        ev["on_unmeasured"] = None
        text = json.dumps(ev)
        for token in ("0.0280", "0.0560", "39 sites", "6 of 19", "14 public", "statsforecast", "darts"):
            self.assertNotIn(token, text)


class Docs(unittest.TestCase):
    def readme(self):
        with open(os.path.join(HERE, "README.md"), encoding="utf-8") as fh:
            return fh.read()

    def test_readme_pins_the_q_convention(self):
        r = self.readme()
        for text in lr.Q_RULES.values():
            self.assertIn(text, r)
        self.assertIn(lr.RANK_RULE, r)
        self.assertIn(lr.FLOOR_RULE, r)

    def test_readme_states_the_18_05_reading_is_unverified(self):
        r = self.readme()
        self.assertIn("18.05", r)
        self.assertIn("q = 0.95", r)
        self.assertIn("UNVERIFIED", r)

    def test_readme_names_licences_and_no_borrowed_code(self):
        r = self.readme()
        self.assertIn("2611.23329", r)
        self.assertIn("nonexclusive-distrib", r)
        self.assertIn("MIT", r)
        self.assertIn("A level is not a rank: an empirical audit of quantile-to-index conversion in 10 released conformal-prediction libraries", r)

    def test_readme_names_every_decision_and_deny_code(self):
        r = self.readme()
        for word in lr.DECISIONS:
            self.assertIn(word, r)
        for code in ("finite_end_below_floor", "missing_scores", "missing_level", "n_changed", "level_changed"):
            self.assertIn(code, r)

    def test_readme_says_exact_arithmetic(self):
        r = self.readme()
        self.assertIn("fractions.Fraction", r)
        self.assertIn("(n=149, alpha=0.18)", r)


if __name__ == "__main__":
    unittest.main()
