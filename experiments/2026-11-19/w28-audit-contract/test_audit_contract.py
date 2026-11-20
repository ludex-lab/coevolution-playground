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

import audit_contract as ac

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
PY = sys.executable
Fraction = ac.Fraction


def raw(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def audit_of(name="main.json", index=0):
    return copy.deepcopy(raw(name)["audits"][index])


def run_root(audits):
    return ac.run(ac.validate({"fixture_version": 1, "on_expiry": "DENY", "audits": audits}))


def deny_code(test, mutate, index=0, name="main.json"):
    a = audit_of(name, index)
    mutate(a)
    row = run_root([a])["rows"][0]
    test.assertEqual(row["decision"], "DENY")
    return row["code"]


def error_code(test, mutate, name="main.json"):
    root = raw(name)
    mutate(root)
    with test.assertRaises(ac.AuditError) as cm:
        ac.run(ac.validate(root))
    return cm.exception.code


def cli(*args):
    p = subprocess.run([PY, "-B", os.path.join(HERE, "audit_contract.py")] + list(args), cwd=HERE,
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


class Contracts(unittest.TestCase):
    W = [1.0, 1.0, 1.0]

    def all(self, x):
        return [ac.dot(c, self.W, x) for c in ac.CONTRACTS]

    def test_contract_names_are_pinned(self):
        self.assertEqual(ac.CONTRACTS, ("ltr", "rtl", "lanes2", "fsum"))

    def test_cancellation_record_one(self):
        self.assertEqual(self.all([1e16, 1.0, -1e16]), [0.0, 0.0, 1.0, 1.0])

    def test_cancellation_record_two(self):
        self.assertEqual(self.all([1.0, 1e16, -1e16]), [0.0, 1.0, 0.0, 1.0])

    def test_cancellation_record_three(self):
        self.assertEqual(self.all([1e16, -1e16, 1.0]), [1.0, 0.0, 0.0, 1.0])

    def test_ordinary_record_agrees_everywhere(self):
        self.assertEqual(self.all([0.9, 0.0, 0.0]), [0.9, 0.9, 0.9, 0.9])

    def test_fsum_is_the_exact_rounded_sum(self):
        self.assertEqual(ac.dot("fsum", self.W, [0.1] * 3), math.fsum([0.1, 0.1, 0.1]))
        self.assertEqual(ac.dot("fsum", [1.0, 1.0, 1.0, 1.0], [1e100, 1.0, -1e100, 1.0]), 2.0)

    def test_ltr_and_rtl_are_the_two_scan_orders(self):
        x = [0.1, 0.2, 0.3]
        self.assertEqual(ac.dot("ltr", self.W, x), (0.0 + 0.1 + 0.2) + 0.3)
        self.assertEqual(ac.dot("rtl", self.W, x), (0.0 + 0.3 + 0.2) + 0.1)

    def test_lanes2_is_even_lane_plus_odd_lane(self):
        w = [1.0, 1.0, 1.0, 1.0]
        x = [1e16, 1.0, -1e16, 1.0]
        self.assertEqual(ac.dot("lanes2", w, x), (1e16 + -1e16) + (1.0 + 1.0))

    def test_products_are_the_same_for_every_contract(self):
        w = [0.5, 0.25, 4.0]
        x = [2.0, 4.0, 0.5]
        self.assertEqual(self.all_w(w, x), [4.0] * 4)

    def all_w(self, w, x):
        return [ac.dot(c, w, x) for c in ac.CONTRACTS]

    def test_unknown_contract_name_is_an_error(self):
        for name in ("tree", "LTR", "", "fsum "):
            with self.assertRaises(ac.AuditError) as cm:
                ac.dot(name, self.W, [1.0, 1.0, 1.0])
            self.assertEqual(cm.exception.code, "unknown_contract")

    def test_sums_are_not_the_builtin_compensated_sum(self):
        # Python 3.12 and later make sum() compensated; the ltr contract must stay a plain running sum.
        self.assertEqual(ac.dot("ltr", self.W, [1e16, 1.0, -1e16]), 0.0)
        self.assertEqual(ac.dot("rtl", self.W, [1e16, 1.0, -1e16]), 0.0)

    def test_lanes2_uses_two_lanes_not_three(self):
        w = [1.0] * 6
        self.assertEqual(ac.dot("lanes2", w, [1.0, 1e16, 1.0, -1e16, 1.0, 0.0]),
                         (1.0 + 1.0 + 1.0) + (1e16 + -1e16 + 0.0))

    def test_non_finite_score_is_an_error_for_every_contract(self):
        for c in ac.CONTRACTS:
            with self.assertRaises(ac.AuditError) as cm:
                ac.dot(c, [1e308, 1e308], [10.0, 10.0])
            self.assertEqual(cm.exception.code, "non_finite_score")

    def test_fsum_overflow_is_an_error_not_a_crash(self):
        with self.assertRaises(ac.AuditError) as cm:
            ac.dot("fsum", [1.0, 1.0, 1.0], [1.7e308, 1.7e308, 0.0])
        self.assertEqual(cm.exception.code, "non_finite_score")
        self.assertIn("fsum", cm.exception.detail)

    def test_fsum_of_opposite_infinities_is_an_error_not_a_crash(self):
        with self.assertRaises(ac.AuditError) as cm:
            ac.dot("fsum", [1e308, -1e308, 1.0], [1e308, 1e308, 0.0])
        self.assertEqual(cm.exception.code, "non_finite_score")

    def test_non_finite_code_does_not_depend_on_contract_order(self):
        cases = (("1.0,1.0,1.0", [1.7e308, 1.7e308, 0.0]), ("1e308,-1e308,1.0", [1e308, 1e308, 0.0]))
        for weights, x in cases:
            for order in (["fsum", "ltr"], ["ltr", "fsum"], ["fsum", "rtl", "lanes2", "ltr"], ["ltr", "rtl", "lanes2", "fsum"]):
                a = audit_of()
                a["declaration"]["weights_text"] = weights
                a["declaration"]["contracts"] = list(order)
                a["scoring"]["runs"] = [{"contract": c, "weights_text": weights} for c in order]
                a["records"][0]["x"] = list(x)
                with self.assertRaises(ac.AuditError) as cm:
                    run_root([a])
                self.assertEqual(cm.exception.code, "non_finite_score", (weights, order))

    def test_non_finite_sum_of_finite_products(self):
        with self.assertRaises(ac.AuditError):
            ac.dot("ltr", [1.0, 1.0], [1e308, 1e308])


class Weights(unittest.TestCase):
    def test_valid_texts(self):
        self.assertEqual(ac.parse_weights("1.0,1.0,1.0"), [1.0, 1.0, 1.0])
        self.assertEqual(ac.parse_weights("-0.5,2,1e-3,1E3"), [-0.5, 2.0, 0.001, 1000.0])

    def test_invalid_texts(self):
        for text in ("", "1.0,", ",1.0", "1.0, 1.0", " 1.0", "1.0 ", "one", "1e", ".5", "+1", "0x10", "nan", "inf",
                     "1.0;1.0", "\u0661", "1.0\u200b", "1e999", "1" * 31, ",".join(["1"] * 17)):
            with self.assertRaises(ac.AuditError, msg=repr(text)) as cm:
                ac.parse_weights(text)
            self.assertEqual(cm.exception.code, "bad_weights")

    def test_sixteen_weights_are_accepted(self):
        self.assertEqual(len(ac.parse_weights(",".join(["1"] * 16))), 16)


class MainFixture(unittest.TestCase):
    def setUp(self):
        self.result = ac.run(ac.load_fixture(os.path.join(FIX, "main.json")))
        self.rows = {r["audit"]: r for r in self.result["rows"]}

    def test_decisions(self):
        self.assertEqual({k: r["decision"] for k, r in self.rows.items()},
                         {"a1_near_threshold": "CONTRACT_DEPENDENT", "a2_calm_pass": "STABLE_PASS",
                          "a3_stable_fail": "STABLE_FAIL"})
        self.assertEqual(self.result["totals"],
                         {"STABLE_PASS": 1, "STABLE_FAIL": 1, "CONTRACT_DEPENDENT": 1, "DENY": 0})

    def test_a1_disagreement_is_reported_per_record_and_per_contract(self):
        a1 = self.rows["a1_near_threshold"]
        self.assertEqual(a1["differing_records"], ["r04", "r05"])
        self.assertEqual(a1["single_contract_views"], {"ltr": "FAIL", "rtl": "PASS", "lanes2": "PASS", "fsum": "FAIL"})
        self.assertTrue(a1["weights_identical"])
        self.assertEqual(a1["weights_text"], "1.0,1.0,1.0")

    def test_a1_dp_gap_is_contract_dependent_with_a_range(self):
        t = self.rows["a1_near_threshold"]["tests"][0]
        self.assertEqual((t["name"], t["bound"], t["outcome"]), ("dp_gap", "3/20", "contract_dependent"))
        self.assertEqual(t["range"], {"min": "0/1", "max": "1/5"})
        self.assertEqual({c: v["statistic"] for c, v in t["per_contract"].items()},
                         {"ltr": "1/5", "rtl": "0/1", "lanes2": "0/1", "fsum": "1/5"})
        self.assertEqual({c: v["pass"] for c, v in t["per_contract"].items()},
                         {"ltr": False, "rtl": True, "lanes2": True, "fsum": False})

    def test_a1_rate_ratio_is_stable_and_has_its_own_range(self):
        t = self.rows["a1_near_threshold"]["tests"][1]
        self.assertEqual((t["name"], t["outcome"]), ("rate_ratio", "pass_all_contracts"))
        self.assertEqual(t["range"], {"min": "2/3", "max": "1/1"})

    def test_a_pass_under_one_contract_is_not_a_pass(self):
        a1 = self.rows["a1_near_threshold"]
        self.assertIn("PASS", a1["single_contract_views"].values())
        self.assertNotEqual(a1["decision"], "STABLE_PASS")

    def test_calm_audit_has_no_disagreement(self):
        a2 = self.rows["a2_calm_pass"]
        self.assertEqual(a2["differing_records"], [])
        self.assertEqual(set(a2["single_contract_views"].values()), {"PASS"})

    def test_stable_fail_is_a_fail_under_every_contract(self):
        a3 = self.rows["a3_stable_fail"]
        self.assertEqual(set(a3["single_contract_views"].values()), {"FAIL"})
        self.assertEqual([t["outcome"] for t in a3["tests"]], ["fail_all_contracts", "fail_all_contracts"])

    def test_sampling_uncertainty_is_not_computed(self):
        for r in self.result["rows"]:
            self.assertEqual(r["sampling_uncertainty"], "not_computed")

    def test_fixture_flip_is_authored_with_cancellation_records(self):
        recs = {r["id"]: r["x"] for r in raw("main.json")["audits"][0]["records"]}
        self.assertEqual(recs["r04"], [1e16, 1.0, -1e16])
        self.assertEqual(recs["r05"], [1.0, 1e16, -1e16])
        for other in ("r01", "r03", "r06", "r10"):
            self.assertLess(max(abs(v) for v in recs[other]), 1.0)

    def test_report_is_deterministic(self):
        fx = ac.load_fixture(os.path.join(FIX, "main.json"))
        self.assertEqual(ac.report(fx), ac.report(fx))
        self.assertEqual(ac.report(fx), json.dumps(json.loads(ac.report(fx)), indent=1, sort_keys=True) + "\n")


class Verdict(unittest.TestCase):
    def build(self, rates_a, rates_b, tests, thr=0.5):
        """Audit whose group g_a selects `rates_a` of 10 records and g_b `rates_b` of 10 (ordinary records)."""
        recs = []
        for g, k in (("g_a", rates_a), ("g_b", rates_b)):
            for i in range(10):
                recs.append({"id": "%s_%d" % (g, i), "group": g, "x": [0.9 if i < k else 0.1, 0.0, 0.0]})
        a = audit_of()
        a["records"] = recs
        a["declaration"]["tests"] = copy.deepcopy(tests)
        a["scoring"]["tests"] = copy.deepcopy(tests)
        return a

    def row(self, a_sel, b_sel, tests):
        return run_root([self.build(a_sel, b_sel, tests)])["rows"][0]

    def test_dp_gap_passes_at_exactly_the_bound(self):
        r = self.row(5, 6, [{"name": "dp_gap", "bound": 0.1}])
        self.assertEqual(r["tests"][0]["per_contract"]["ltr"], {"statistic": "1/10", "pass": True})
        self.assertEqual(r["decision"], "STABLE_PASS")

    def test_dp_gap_fails_just_over_the_bound(self):
        r = self.row(4, 6, [{"name": "dp_gap", "bound": 0.1}])
        self.assertEqual(r["decision"], "STABLE_FAIL")

    def test_rate_ratio_passes_at_exactly_the_bound(self):
        r = self.row(4, 8, [{"name": "rate_ratio", "bound": 0.5}])
        self.assertEqual(r["tests"][0]["per_contract"]["fsum"], {"statistic": "1/2", "pass": True})

    def test_rate_ratio_fails_just_under_the_bound(self):
        r = self.row(3, 8, [{"name": "rate_ratio", "bound": 0.5}])
        self.assertEqual(r["decision"], "STABLE_FAIL")

    def test_rate_ratio_uses_the_smaller_over_the_larger_rate(self):
        r1 = self.row(4, 8, [{"name": "rate_ratio", "bound": 0.5}])
        r2 = self.row(8, 4, [{"name": "rate_ratio", "bound": 0.5}])
        self.assertEqual(r1["tests"][0]["range"], r2["tests"][0]["range"])

    def test_rate_ratio_with_two_empty_selections_is_one(self):
        r = self.row(0, 0, [{"name": "rate_ratio", "bound": 1}])
        self.assertEqual(r["tests"][0]["per_contract"]["ltr"], {"statistic": "1/1", "pass": True})

    def test_rate_ratio_with_one_empty_selection_is_zero(self):
        r = self.row(0, 5, [{"name": "rate_ratio", "bound": 0.1}])
        self.assertEqual(r["tests"][0]["per_contract"]["ltr"], {"statistic": "0/1", "pass": False})

    def test_bounds_are_exact_decimals(self):
        r = self.row(5, 6, [{"name": "dp_gap", "bound": 0.1}])
        self.assertEqual(r["tests"][0]["bound"], "1/10")
        r = self.row(1, 2, [{"name": "dp_gap", "bound": 0.3}])
        self.assertEqual(r["tests"][0]["bound"], "3/10")

    def test_selection_is_strictly_above_the_threshold(self):
        a = self.build(5, 5, [{"name": "dp_gap", "bound": 0}])
        a["records"][0]["x"] = [0.5, 0.0, 0.0]
        r = run_root([a])["rows"][0]
        self.assertEqual(r["tests"][0]["per_contract"]["ltr"]["statistic"], "1/10")
        a["records"][0]["x"] = [0.5000001, 0.0, 0.0]
        r = run_root([a])["rows"][0]
        self.assertEqual(r["tests"][0]["per_contract"]["ltr"]["statistic"], "0/1")

    def test_combine(self):
        P, F, D = "pass_all_contracts", "fail_all_contracts", "contract_dependent"
        for outcomes, want in (([P, P], "STABLE_PASS"), ([P], "STABLE_PASS"), ([P, F], "STABLE_FAIL"), ([F, P], "STABLE_FAIL"),
                               ([F, F], "STABLE_FAIL"), ([D, F], "CONTRACT_DEPENDENT"), ([F, D], "CONTRACT_DEPENDENT"),
                               ([D, P], "CONTRACT_DEPENDENT"), ([P, D], "CONTRACT_DEPENDENT"), ([D], "CONTRACT_DEPENDENT")):
            self.assertEqual(ac.combine(outcomes), want, outcomes)

    def test_stable_fail_beats_a_stable_pass(self):
        a = audit_of("main.json", 2)
        a["declaration"]["tests"] = [{"name": "dp_gap", "bound": 0.9}, {"name": "rate_ratio", "bound": 0.5}]
        a["scoring"]["tests"] = copy.deepcopy(a["declaration"]["tests"])
        r = run_root([a])["rows"][0]
        self.assertEqual([t["outcome"] for t in r["tests"]], ["pass_all_contracts", "fail_all_contracts"])
        self.assertEqual(r["decision"], "STABLE_FAIL")

    def test_range_is_over_every_declared_contract(self):
        r = run_root([audit_of()])["rows"][0]
        t = r["tests"][0]
        stats = [Fraction(v["statistic"]) for v in t["per_contract"].values()]
        self.assertEqual((t["range"]["min"], t["range"]["max"]), (ac._frac(min(stats)), ac._frac(max(stats))))

    def test_a_declared_subset_of_contracts_is_reported_over_that_subset(self):
        a = audit_of()
        a["declaration"]["contracts"] = ["rtl", "lanes2"]
        a["scoring"]["runs"] = [r for r in a["scoring"]["runs"] if r["contract"] in ("rtl", "lanes2")]
        r = run_root([a])["rows"][0]
        self.assertEqual(r["contracts"], ["rtl", "lanes2"])
        self.assertEqual(r["decision"], "STABLE_PASS")
        self.assertEqual(list(r["single_contract_views"]), ["rtl", "lanes2"])

    def test_run_order_in_the_scoring_block_does_not_change_the_report(self):
        a = audit_of()
        b = audit_of()
        b["scoring"]["runs"].reverse()
        self.assertEqual(run_root([a]), run_root([b]))

    def test_records_in_a_different_order_give_the_same_decision(self):
        a = audit_of()
        a["records"].reverse()
        r = run_root([a])["rows"][0]
        self.assertEqual(r["decision"], "CONTRACT_DEPENDENT")
        self.assertEqual(sorted(r["differing_records"]), ["r04", "r05"])


class Predeclaration(unittest.TestCase):
    def test_every_denied_row_has_its_code(self):
        rows = ac.run(ac.load_fixture(os.path.join(FIX, "denied.json")))["rows"]
        got = [(r["audit"], r["decision"], r["code"]) for r in rows]
        self.assertEqual(got, [
            ("d00_clean", "STABLE_PASS", None),
            ("d01_no_declaration", "DENY", "no_declaration"),
            ("d02_declared_after_scoring", "DENY", "declared_after_scoring"),
            ("d03_contract_missing", "DENY", "contract_missing"),
            ("d04_contract_not_declared", "DENY", "contract_not_declared"),
            ("d05_weights_changed", "DENY", "weights_changed"),
            ("d06_weights_same_value_other_bytes", "DENY", "weights_changed"),
            ("d07_threshold_changed", "DENY", "threshold_changed"),
            ("d08_groups_changed", "DENY", "groups_changed"),
            ("d09_post_hoc_test", "DENY", "post_hoc_test"),
            ("d10_test_missing", "DENY", "test_missing"),
            ("d11_test_changed", "DENY", "test_changed"),
        ])

    def test_a_denied_row_has_no_verdict_fields(self):
        row = run_root([self.denied(lambda a: a.__setitem__("declaration", None))])["rows"][0]
        self.assertEqual(set(row), {"audit", "decision", "code", "detail"})

    def denied(self, mutate):
        a = audit_of()
        mutate(a)
        return a

    def test_no_declaration(self):
        self.assertEqual(deny_code(self, lambda a: a.__setitem__("declaration", None)), "no_declaration")

    def test_declaration_must_come_strictly_before_scoring(self):
        self.assertEqual(deny_code(self, lambda a: a["declaration"].__setitem__("seq", 2)), "declared_after_scoring")
        self.assertEqual(deny_code(self, lambda a: a["declaration"].__setitem__("seq", 3)), "declared_after_scoring")
        a = audit_of()
        a["declaration"]["seq"] = 0
        a["scoring"]["seq"] = 1
        self.assertEqual(run_root([a])["rows"][0]["decision"], "CONTRACT_DEPENDENT")

    def test_missing_contract(self):
        self.assertEqual(deny_code(self, lambda a: a["scoring"]["runs"].pop()), "contract_missing")

    def test_scoring_only_one_contract_is_denied_not_passed(self):
        def only_fsum(a):
            a["scoring"]["runs"] = [r for r in a["scoring"]["runs"] if r["contract"] == "fsum"]
        self.assertEqual(deny_code(self, only_fsum), "contract_missing")
        self.assertEqual(deny_code(self, only_fsum, 1), "contract_missing")

    def test_undeclared_contract(self):
        def drop_declared(a):
            a["declaration"]["contracts"] = ["ltr", "rtl", "lanes2"]
        self.assertEqual(deny_code(self, drop_declared), "contract_not_declared")

    def test_weights_text_must_match_byte_for_byte(self):
        for text in ("1.0,1.0,1.1", "1.00,1.0,1.0", "1,1,1", "1.0,1.0,1.0 ", " 1.0,1.0,1.0", "1.0,1.0,1.0\u200b",
                     "1.0,1.0,1.0\n", "\uff11.0,1.0,1.0", "1.0,1.0,1.0\x00"):
            def change(a, t=text):
                a["scoring"]["runs"][3]["weights_text"] = t
            self.assertEqual(deny_code(self, change), "weights_changed", repr(text))

    def test_weights_check_applies_to_every_run(self):
        for i in range(4):
            def change(a, k=i):
                a["scoring"]["runs"][k]["weights_text"] = "1.0,1.0,1.5"
            self.assertEqual(deny_code(self, change), "weights_changed")

    def test_same_numeric_weights_in_other_bytes_are_still_denied(self):
        self.assertEqual(ac.parse_weights("1.00,1.0,1.0"), ac.parse_weights("1.0,1.0,1.0"))
        def change(a):
            a["scoring"]["runs"][0]["weights_text"] = "1.00,1.0,1.0"
        self.assertEqual(deny_code(self, change), "weights_changed")

    def test_threshold_changed(self):
        self.assertEqual(deny_code(self, lambda a: a["scoring"].__setitem__("threshold", 0.6)), "threshold_changed")
        self.assertEqual(deny_code(self, lambda a: a["scoring"].__setitem__("threshold", 0.4)), "threshold_changed")
        self.assertEqual(deny_code(self, lambda a: a["scoring"].__setitem__("threshold", 0.5000000001)), "threshold_changed")

    def test_equal_threshold_written_differently_is_the_same_threshold(self):
        a = audit_of()
        a["scoring"]["threshold"] = 0.50
        a["declaration"]["threshold"] = 5e-1
        self.assertEqual(run_root([a])["rows"][0]["decision"], "CONTRACT_DEPENDENT")

    def test_groups_changed(self):
        self.assertEqual(deny_code(self, lambda a: a["scoring"].__setitem__("groups", ["g_b", "g_a"])), "groups_changed")
        self.assertEqual(deny_code(self, lambda a: a["scoring"].__setitem__("groups", ["g_a"])), "groups_changed")
        self.assertEqual(deny_code(self, lambda a: a["scoring"].__setitem__("groups", ["g_a", "g_b", "g_c"])), "groups_changed")

    def test_post_hoc_test_is_denied(self):
        def trim(a):
            a["declaration"]["tests"] = [t for t in a["declaration"]["tests"] if t["name"] == "dp_gap"]
        self.assertEqual(deny_code(self, trim), "post_hoc_test")

    def test_dropping_a_declared_test_is_denied(self):
        def trim(a):
            a["scoring"]["tests"] = [t for t in a["scoring"]["tests"] if t["name"] == "dp_gap"]
        self.assertEqual(deny_code(self, trim), "test_missing")

    def test_changing_a_bound_after_the_fact_is_denied(self):
        def loosen(a):
            a["scoring"]["tests"][0]["bound"] = 0.25
        self.assertEqual(deny_code(self, loosen), "test_changed")
        def tighten(a):
            a["scoring"]["tests"][0]["bound"] = 0.1
        self.assertEqual(deny_code(self, tighten), "test_changed")

    def test_test_order_in_the_scoring_block_is_not_a_change(self):
        a = audit_of()
        a["scoring"]["tests"].reverse()
        self.assertEqual(run_root([a])["rows"][0]["decision"], "CONTRACT_DEPENDENT")

    def test_the_first_broken_rule_names_the_code(self):
        def two(a):
            a["declaration"]["seq"] = 2
            a["scoring"]["threshold"] = 0.9
        self.assertEqual(deny_code(self, two), "declared_after_scoring")
        def two_b(a):
            a["scoring"]["runs"].pop()
            a["scoring"]["runs"][0]["weights_text"] = "9"
        self.assertEqual(deny_code(self, two_b), "contract_missing")
        def two_c(a):
            a["scoring"]["runs"][0]["weights_text"] = "9"
            a["scoring"]["threshold"] = 0.9
        self.assertEqual(deny_code(self, two_c), "weights_changed")
        def two_d(a):
            a["scoring"]["threshold"] = 0.9
            a["scoring"]["groups"] = ["g_b", "g_a"]
        self.assertEqual(deny_code(self, two_d), "threshold_changed")
        def two_e(a):
            a["scoring"]["groups"] = ["g_b", "g_a"]
            a["scoring"]["tests"][0]["bound"] = 0.9
        self.assertEqual(deny_code(self, two_e), "groups_changed")

    def test_a_denied_audit_does_not_change_the_others(self):
        solo = run_root([audit_of("main.json", 1)])["rows"][0]
        bad = audit_of()
        bad["scoring"]["threshold"] = 0.9
        rows = run_root([bad, audit_of("main.json", 1)])["rows"]
        self.assertEqual(rows[0]["decision"], "DENY")
        self.assertEqual(rows[1], solo)
        self.assertEqual(run_root([bad, audit_of("main.json", 1)])["totals"]["DENY"], 1)

    def test_compare_function_returns_none_for_a_clean_audit(self):
        fx = ac.load_fixture(os.path.join(FIX, "main.json"))
        for a in fx["audits"]:
            self.assertIsNone(ac.predeclaration_check(a["declaration"], a["scoring"]))


class Validation(unittest.TestCase):
    def test_codes(self):
        cases = [
            ("missing_key", lambda r: r.pop("audits")),
            ("missing_key", lambda r: r["audits"][0].pop("records")),
            ("missing_key", lambda r: r["audits"][0]["declaration"].pop("tests")),
            ("missing_key", lambda r: r["audits"][0]["scoring"].pop("runs")),
            ("missing_key", lambda r: r["audits"][0]["records"][0].pop("x")),
            ("missing_key", lambda r: r["audits"][0]["scoring"]["runs"][0].pop("contract")),
            ("unknown_key", lambda r: r.__setitem__("extra", 1)),
            ("unknown_key", lambda r: r["audits"][0].__setitem__("extra", 1)),
            ("unknown_key", lambda r: r["audits"][0]["declaration"].__setitem__("extra", 1)),
            ("unknown_key", lambda r: r["audits"][0]["scoring"]["tests"][0].__setitem__("extra", 1)),
            ("wrong_type", lambda r: r.__setitem__("audits", {})),
            ("wrong_type", lambda r: r.__setitem__("audits", [])),
            ("wrong_type", lambda r: r["audits"][0].__setitem__("declaration", [])),
            ("wrong_type", lambda r: r["audits"][0].__setitem__("scoring", None)),
            ("wrong_type", lambda r: r["audits"][0]["records"][0].__setitem__("x", [])),
            ("wrong_type", lambda r: r["audits"][0]["records"][0]["x"].__setitem__(0, True)),
            ("wrong_type", lambda r: r["audits"][0]["records"][0]["x"].__setitem__(0, "1")),
            ("wrong_type", lambda r: r["audits"][0]["records"][0]["x"].__setitem__(0, None)),
            ("wrong_type", lambda r: r["audits"][0]["declaration"].__setitem__("seq", "1")),
            ("wrong_type", lambda r: r["audits"][0]["declaration"].__setitem__("seq", 1.0)),
            ("wrong_type", lambda r: r["audits"][0]["declaration"].__setitem__("seq", -1)),
            ("wrong_type", lambda r: r["audits"][0]["scoring"].__setitem__("seq", True)),
            ("wrong_type", lambda r: r["audits"][0]["declaration"].__setitem__("weights_text", 1)),
            ("wrong_type", lambda r: r["audits"][0]["declaration"].__setitem__("weights_text", "1," * 300)),
            ("wrong_type", lambda r: r["audits"][0]["declaration"].__setitem__("threshold", "0.5")),
            ("wrong_type", lambda r: r["audits"][0]["scoring"]["runs"][0].__setitem__("weights_text", None)),
            ("bad_number", lambda r: r["audits"][0]["declaration"].__setitem__("threshold", 1e999)),
            ("bad_number", lambda r: r["audits"][0]["records"][0]["x"].__setitem__(0, 10 ** 400)),
            ("bad_number", lambda r: r["audits"][0]["declaration"]["tests"][0].__setitem__("bound", 1.5)),
            ("bad_number", lambda r: r["audits"][0]["declaration"]["tests"][0].__setitem__("bound", -0.1)),
            ("bad_version", lambda r: r.__setitem__("fixture_version", 2)),
            ("bad_version", lambda r: r.__setitem__("fixture_version", True)),
            ("bad_on_expiry", lambda r: r.__setitem__("on_expiry", "HOLD")),
            ("bad_on_expiry", lambda r: r.__setitem__("on_expiry", "ESCALATE")),
            ("bad_on_expiry", lambda r: r.__setitem__("on_expiry", "deny")),
            ("bad_on_expiry", lambda r: r.__setitem__("on_expiry", None)),
            ("unknown_contract", lambda r: r["audits"][0]["declaration"]["contracts"].append("tree")),
            ("unknown_contract", lambda r: r["audits"][0]["scoring"]["runs"][0].__setitem__("contract", "LTR")),
            ("unknown_test", lambda r: r["audits"][0]["declaration"]["tests"].append({"name": "x", "bound": 0.1})),
            ("duplicate_name", lambda r: r["audits"][0]["declaration"]["contracts"].append("ltr")),
            ("duplicate_name", lambda r: r["audits"][0]["declaration"]["tests"].append({"name": "dp_gap", "bound": 0.2})),
            ("duplicate_name", lambda r: r["audits"][0]["declaration"]["groups"].__setitem__(1, "g_a")),
            ("duplicate_name", lambda r: r["audits"][0]["scoring"]["runs"].append(dict(r["audits"][0]["scoring"]["runs"][0]))),
            ("duplicate_name", lambda r: r["audits"][0]["records"][1].__setitem__("id", "r01")),
            ("duplicate_name", lambda r: r["audits"][1].__setitem__("id", "a1_near_threshold")),
            ("too_few_contracts", lambda r: r["audits"][0]["declaration"].__setitem__("contracts", ["fsum"])),
            ("wrong_type", lambda r: r["audits"][0]["declaration"].__setitem__("contracts", [])),
            ("bad_groups", lambda r: r["audits"][0]["declaration"]["groups"].append("g_c")),
            ("wrong_type", lambda r: r["audits"][0]["declaration"].__setitem__("groups", ["g_a"])),
            ("bad_id", lambda r: r["audits"][0]["records"][0].__setitem__("id", "r 01")),
            ("bad_id", lambda r: r["audits"][0]["records"][0].__setitem__("id", "")),
            ("bad_id", lambda r: r["audits"][0]["records"][0].__setitem__("id", "r01\n")),
            ("bad_id", lambda r: r["audits"][0]["records"][0].__setitem__("id", "r\u200b01")),
            ("bad_id", lambda r: r["audits"][0].__setitem__("id", "a" * 41)),
            ("bad_id", lambda r: r["audits"][0]["records"][0].__setitem__("group", "g\u0430")),
            ("unknown_group", lambda r: r["audits"][0]["records"][0].__setitem__("group", "g_c")),
            ("empty_group", lambda r: [x.__setitem__("group", "g_a") for x in r["audits"][0]["records"]]),
            ("bad_dimension", lambda r: r["audits"][0]["records"][0].__setitem__("x", [0.9, 0.0])),
            ("bad_dimension", lambda r: r["audits"][0]["declaration"].__setitem__("weights_text", "1.0,1.0")),
            ("bad_text", lambda r: r["audits"][0]["scoring"]["runs"][0].__setitem__("weights_text", "\ud800")),
            ("bad_text", lambda r: r["audits"][0]["scoring"]["runs"][3].__setitem__("weights_text", "1.0,1.0,1.0\udfff")),
            ("bad_text", lambda r: r["audits"][0]["declaration"].__setitem__("weights_text", "\ud800")),
            ("bad_weights", lambda r: r["audits"][0]["declaration"].__setitem__("weights_text", "1.0,one,1.0")),
            ("bad_weights", lambda r: r["audits"][0]["declaration"].__setitem__("weights_text", "1.0,\u0661,1.0")),
        ]
        for code, mutate in cases:
            self.assertEqual(error_code(self, mutate), code, code)

    def test_a_null_declaration_skips_the_dimension_checks_but_not_the_scoring_block(self):
        root = raw("main.json")
        root["audits"][0]["declaration"] = None
        root["audits"][0]["records"][0]["x"] = [1.0]
        self.assertEqual(ac.run(ac.validate(root))["rows"][0]["code"], "no_declaration")
        root["audits"][0]["scoring"]["seq"] = "2"
        with self.assertRaises(ac.AuditError):
            ac.validate(root)

    def test_every_malformed_run_stops_before_any_row_is_printed(self):
        root = raw("main.json")
        root["audits"][2]["records"][0]["x"] = [True, 0, 0]
        with self.assertRaises(ac.AuditError):
            ac.run(ac.validate(root))

    def test_strict_json(self):
        for text, code in (("{ not json", "not_json"), ("", "not_json"), ("[1,2", "not_json"),
                           ('{"a": 1, "a": 2}', "duplicate_key"), ('{"a": NaN}', "bad_number"),
                           ('{"a": Infinity}', "bad_number"), ('{"a": -Infinity}', "bad_number"),
                           ("[" * 10000 + "]" * 10000, "not_json"), ('{"a": ' + "9" * 5000 + "}", "not_json")):
            with self.assertRaises(ac.AuditError, msg=text[:20]) as cm:
                ac.parse(text)
            self.assertEqual(cm.exception.code, code)

    def test_parse_accepts_ordinary_json(self):
        self.assertEqual(ac.parse('{"a": [1, 2.5]}'), {"a": [1, 2.5]})

    def test_error_details_escape_odd_key_text(self):
        root = raw("main.json")
        root["audits"][0]["x\nINJECT"] = 1
        with self.assertRaises(ac.AuditError) as cm:
            ac.validate(root)
        self.assertNotIn("\n", cm.exception.detail)
        self.assertIn("\\n", cm.exception.detail)

    def test_error_details_are_ascii(self):
        root = raw("main.json")
        root["audits"][0]["x\u0430\u200b"] = 1
        with self.assertRaises(ac.AuditError) as cm:
            ac.validate(root)
        self.assertTrue(cm.exception.detail.isascii())
        self.assertIn("\\u0430", cm.exception.detail)

    def test_load_fixture_errors(self):
        for path, code in ((os.path.join(FIX, "does_not_exist.json"), "unreadable"), (FIX, "unreadable")):
            with self.assertRaises(ac.AuditError) as cm:
                ac.load_fixture(path)
            self.assertEqual(cm.exception.code, code)

    def test_load_fixture_rejects_invalid_utf8(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            with open(p, "wb") as fh:
                fh.write(b"\xff\xfe{}")
            with self.assertRaises(ac.AuditError) as cm:
                ac.load_fixture(p)
            self.assertEqual(cm.exception.code, "bad_encoding")


class Cli(unittest.TestCase):
    def test_main_exits_zero_with_report_only(self):
        rc, out, err = cli(os.path.join("fixtures", "main.json"))
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(json.loads(out)["totals"]["CONTRACT_DEPENDENT"], 1)
        self.assertEqual(out, ac.report(ac.load_fixture(os.path.join(FIX, "main.json"))))

    def test_deny_rows_exit_two_with_the_report_on_stdout_and_empty_stderr(self):
        rc, out, err = cli(os.path.join("fixtures", "denied.json"))
        self.assertEqual((rc, err), (2, ""))
        self.assertEqual(json.loads(out)["totals"]["DENY"], 11)

    def test_deny_in_a_later_row_still_exits_two(self):
        rc, out, err = cli(os.path.join("fixtures", "denied.json"))
        decisions = [r["decision"] for r in json.loads(out)["rows"]]
        self.assertNotEqual(decisions[0], "DENY")
        self.assertEqual(rc, 2)

    def test_every_bad_fixture_exits_two_with_one_error_line(self):
        names = sorted(n for n in os.listdir(FIX) if n.startswith("bad_"))
        self.assertEqual(len(names), 34)
        for n in names:
            rc, out, err = cli(os.path.join("fixtures", n))
            self.assertEqual((rc, out), (2, ""), n)
            self.assertTrue(err.startswith("ERROR "), n)
            self.assertEqual(err.count("\n"), 1, n)

    def test_bad_fixture_codes(self):
        expect = {"bad_duplicate_key.json": "duplicate_key", "bad_nan.json": "bad_number", "bad_not_json.json": "not_json",
                  "bad_on_expiry.json": "bad_on_expiry", "bad_single_contract.json": "too_few_contracts",
                  "bad_unknown_group.json": "unknown_group", "bad_weights_unicode_digit.json": "bad_weights",
                  "bad_deep_nesting.json": "not_json", "bad_bigint.json": "not_json", "bad_overflow.json": "bad_number",
                  "bad_lone_surrogate.json": "bad_text", "bad_fsum_overflow.json": "non_finite_score",
                  "bad_fsum_inf_mix.json": "non_finite_score"}
        for n, code in expect.items():
            rc, out, err = cli(os.path.join("fixtures", n))
            self.assertTrue(err.startswith("ERROR %s: " % code), (n, err))

    def test_lone_surrogate_in_a_run_text_is_a_clean_error(self):
        root = raw("main.json")
        root["audits"][0]["scoring"]["runs"][0]["weights_text"] = "\ud800"
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(root, fh)
            with open(p, encoding="utf-8") as fh:
                self.assertIn("\\ud800", fh.read())
            rc, out, err = cli(p)
        self.assertEqual((rc, out), (2, ""))
        self.assertTrue(err.startswith("ERROR bad_text: "), err)
        self.assertEqual(err.count("\n"), 1)
        self.assertNotIn("Traceback", err)

    def test_fsum_crashes_are_clean_errors_whatever_the_declared_order(self):
        for name in ("bad_fsum_overflow.json", "bad_fsum_inf_mix.json"):
            rc, out, err = cli(os.path.join("fixtures", name))
            self.assertEqual((rc, out), (2, ""), name)
            self.assertTrue(err.startswith("ERROR non_finite_score: "), err)
            self.assertEqual(err.count("\n"), 1)
            self.assertNotIn("Traceback", err)

    def test_usage(self):
        for args in ((), ("a", "b")):
            rc, out, err = cli(*args)
            self.assertEqual((rc, out), (2, ""))
            self.assertTrue(err.startswith("ERROR usage:"))

    def test_missing_file(self):
        rc, out, err = cli("fixtures/nothing.json")
        self.assertEqual((rc, out), (2, ""))
        self.assertTrue(err.startswith("ERROR unreadable:"))

    def test_error_lines_never_start_with_the_deny_word(self):
        rc, out, err = cli(os.path.join("fixtures", "bad_nan.json"))
        self.assertFalse(err.startswith("DENY"))

    def test_main_function_streams(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = ac.main(["x", os.path.join(FIX, "main.json")])
        self.assertEqual((rc, err.getvalue()), (0, ""))
        self.assertTrue(out.getvalue().startswith("{"))


class Demo(unittest.TestCase):
    def run_demo(self):
        p = subprocess.run([PY, "-B", os.path.join(HERE, "demo.py")], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual((p.returncode, p.stderr), (0, ""))
        return p.stdout

    def test_demo_is_deterministic(self):
        self.assertEqual(self.run_demo(), self.run_demo())

    def test_demo_shows_the_single_contract_views_and_the_range(self):
        out = self.run_demo()
        self.assertIn("ltr=FAIL  rtl=PASS  lanes2=PASS  fsum=FAIL", out)
        self.assertIn("range 0/1..1/5", out)
        self.assertIn("by construction", out)
        self.assertIn("DENY post_hoc_test", out)


class Hygiene(unittest.TestCase):
    def source(self, name):
        with open(os.path.join(HERE, name), encoding="utf-8") as fh:
            return fh.read()

    def test_stdlib_imports_only(self):
        mods = set()
        for line in self.source("audit_contract.py").splitlines():
            if line.startswith("import "):
                mods.add(line.split()[1])
            elif line.startswith("from "):
                mods.add(line.split()[1])
        self.assertEqual(mods, {"fractions", "json", "math", "re", "sys"})

    def test_no_hash_no_signing_no_clock(self):
        src = self.source("audit_contract.py")
        for word in ("hashlib", "hmac", "secrets", "time", "datetime", "random", "socket", "urllib", "subprocess", "os."):
            self.assertNotIn("import " + word, src)
        self.assertNotIn("hashlib", src.replace("no hash", ""))

    def test_pre_declaration_is_byte_equality(self):
        src = self.source("audit_contract.py")
        self.assertIn('r["weights_text"].encode("utf-8") != decl["weights_text"].encode("utf-8")', src)

    def test_evidence_json(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            ev = json.load(fh)
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.23657")
        self.assertEqual(ev["paper"]["title"],
                         "Same Model, Different People: Numerical Execution Contracts and the Reproducibility of Fairness Audits")
        self.assertIn("CC BY 4.0", ev["paper"]["licence"])
        self.assertTrue(ev["paper"]["method_only"])
        self.assertEqual(ev["status"], "UNVERIFIED")
        claims = ev["on_unmeasured"]["claims"]
        self.assertGreaterEqual(len(claims), 8)
        self.assertEqual({c["status"] for c in claims}, {"UNVERIFIED"})
        self.assertEqual(len({c["id"] for c in claims}), len(claims))
        self.assertTrue(ev["measured"]["verdict_flip_is_fixture_authored"])
        self.assertEqual(ev["measured"]["decisions"],
                         {"a1_near_threshold": "CONTRACT_DEPENDENT", "a2_calm_pass": "STABLE_PASS", "a3_stable_fail": "STABLE_FAIL"})

    def test_paper_numbers_appear_only_under_on_unmeasured(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            ev = json.load(fh)
        ev["on_unmeasured"] = None
        text = json.dumps(ev)
        for number in ("54%", "45%", "0.0567", "0.0515", "0.0417", "0.0394", "24B"):
            self.assertNotIn(number, text)


class Docs(unittest.TestCase):
    def readme(self):
        with open(os.path.join(HERE, "README.md"), encoding="utf-8") as fh:
            return fh.read()

    def test_readme_says_the_flip_is_fixture_authored(self):
        r = self.readme()
        self.assertIn("fixture-authored", r)
        self.assertIn("by construction", r)
        self.assertIn("no verdict under the prespecified, unweighted tests", r)

    def test_readme_says_pre_declaration_is_byte_equality_only(self):
        r = self.readme()
        self.assertIn("byte-for-byte `==`", r)
        self.assertIn("no hash, no signing and no timestamp", r)

    def test_readme_names_paper_licence_and_title(self):
        r = self.readme()
        self.assertIn("CC BY 4.0", r)
        self.assertIn("2611.23657", r)
        self.assertIn("Same Model, Different People: Numerical Execution Contracts and the Reproducibility of Fairness Audits", r)

    def test_readme_names_every_decision_and_deny_code(self):
        r = self.readme()
        for word in ac.DECISIONS:
            self.assertIn(word, r)
        for code in ("no_declaration", "declared_after_scoring", "contract_missing", "contract_not_declared",
                     "weights_changed", "threshold_changed", "groups_changed", "post_hoc_test", "test_missing", "test_changed"):
            self.assertIn(code, r)


if __name__ == "__main__":
    unittest.main()
