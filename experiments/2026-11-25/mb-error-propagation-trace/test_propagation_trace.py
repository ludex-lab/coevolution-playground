"""unittest suite for propagation_trace.py.  Run: python3 -B -m unittest

The numeric-boundary self-tests come first (BoundaryFirstTests, which also sorts first). Every test checks behaviour
through the imported module: return values, the in-process CLI, report text, JSON output and the demo output.
No test reads any Python source file. There is no catch-all wrapper: an unexpected exception stays a unittest error,
so mutants.py can tell a kill by assertion from a crash.
"""

import decimal
import io
import json
import os
import tempfile
import unittest

import demo
import mutants
import propagation_trace as pt

D = decimal.Decimal
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
VALID = ("main.json", "more.json")
BAD_CODES = {
    "bad_agent_empty.json": "bad_id",
    "bad_agent_number.json": "bad_id",
    "bad_arg_bool.json": "bad_type",
    "bad_arg_null.json": "bad_type",
    "bad_case_not_object.json": "bad_shape",
    "bad_cases_object.json": "bad_shape",
    "bad_computed_overflow.json": "computed_out_of_range",
    "bad_deep_nesting.json": "not_json",
    "bad_duplicate_id.json": "duplicate_id",
    "bad_duplicate_key.json": "duplicate_key",
    "bad_empty_cases.json": "empty_list",
    "bad_empty_chain.json": "empty_chain",
    "bad_empty_file.json": "not_json",
    "bad_expect_class.json": "bad_expect",
    "bad_expect_outcome.json": "bad_expect",
    "bad_expect_short.json": "bad_expect",
    "bad_expect_trace.json": "bad_expect",
    "bad_fault_list.json": "bad_type",
    "bad_hop_not_object.json": "bad_shape",
    "bad_hops_object.json": "bad_shape",
    "bad_huge_exponent.json": "out_of_range",
    "bad_id_hyphen.json": "bad_id",
    "bad_id_upper.json": "bad_id",
    "bad_infinity_arg.json": "bad_number",
    "bad_label_control.json": "bad_text",
    "bad_label_empty.json": "bad_text",
    "bad_label_number.json": "bad_type",
    "bad_label_zero_width.json": "bad_text",
    "bad_long_number.json": "bad_number",
    "bad_missing_cases.json": "missing_field",
    "bad_missing_expect.json": "missing_field",
    "bad_missing_expect_trace.json": "missing_field",
    "bad_missing_hop_agent.json": "missing_field",
    "bad_missing_hop_arg.json": "missing_field",
    "bad_missing_hop_op.json": "missing_field",
    "bad_missing_hops.json": "missing_field",
    "bad_missing_id.json": "missing_field",
    "bad_missing_label.json": "missing_field",
    "bad_missing_start.json": "missing_field",
    "bad_missing_tolerance.json": "missing_field",
    "bad_nan_start.json": "bad_number",
    "bad_nan_tolerance.json": "bad_number",
    "bad_neg_infinity_fault.json": "bad_number",
    "bad_not_json.json": "not_json",
    "bad_not_utf8.json": "bad_encoding",
    "bad_op_number.json": "bad_op",
    "bad_op_unknown.json": "bad_op",
    "bad_positive_exponent.json": "bad_number",
    "bad_recheck_number.json": "bad_type",
    "bad_start_bool.json": "bad_type",
    "bad_start_text.json": "bad_type",
    "bad_tiny_exponent.json": "bad_number",
    "bad_tolerance_bool.json": "bad_type",
    "bad_tolerance_negative.json": "bad_tolerance",
    "bad_tolerance_negative_zero.json": "bad_tolerance",
    "bad_tolerance_zero.json": "bad_tolerance",
    "bad_too_large.json": "too_large",
    "bad_too_many_cases.json": "too_many",
    "bad_too_many_hops.json": "too_many",
    "bad_too_many_places.json": "bad_number",
    "bad_top_level_list.json": "bad_shape",
    "bad_trailing_comma.json": "not_json",
    "bad_truncated.json": "not_json",
    "bad_unknown_case_field.json": "unknown_field",
    "bad_unknown_hop_field.json": "unknown_field",
    "bad_unknown_root_field.json": "unknown_field",
    "bad_value_too_big.json": "out_of_range",
    "bad_value_too_small.json": "out_of_range",
    "bad_version_2.json": "bad_version",
    "bad_version_float.json": "bad_version",
    "bad_version_text.json": "bad_version",
    "bad_zero_huge_exponent.json": "bad_number",
}


def cli(*args):
    out, err = io.StringIO(), io.StringIO()
    code = pt.main(["propagation_trace.py"] + list(args), out, err)
    return code, out.getvalue(), err.getvalue()


def bad(name):
    return os.path.join(FIX, "bad", name)


def deny_code(root):
    """The DENY code validate() raises, or 'no deny'. Other exceptions are not caught."""
    try:
        pt.validate(root)
    except pt.TraceError as e:
        return e.code
    return "no deny"


def hop(op="add", arg="1", fault="0", recheck=False, agent="a"):
    return {"agent": agent, "op": op, "arg": D(arg), "fault": D(fault), "recheck": recheck}


def case(hops, start="0", tol="0.5", classes=None, outcome="PASS", trace="clean", cid="c"):
    return {"id": cid, "label": "l", "start": D(start), "tolerance": D(tol), "hops": hops,
            "expect": {"outcome": outcome, "trace": trace, "hops": classes or ["clean"] * len(hops)}}


def root_with(case_fields=None, hop_fields=None):
    h = {"agent": "a", "op": "add", "arg": D("1")}
    h.update(hop_fields or {})
    c = {"id": "c", "label": "l", "start": D("0"), "tolerance": D("0.5"), "hops": [h],
         "expect": {"outcome": "PASS", "trace": "clean", "hops": ["clean"]}}
    c.update(case_fields or {})
    return {"fixture_version": D(1), "label": "x", "cases": [c]}


def result(name):
    return pt.run(pt.load_fixture(os.path.join(FIX, name)))


def rows(name):
    return {r["id"]: r for r in result(name)["rows"]}


class BoundaryFirstTests(unittest.TestCase):
    """Numeric boundaries, run first."""

    def test_empty_chain_is_bad_input(self):
        self.assertEqual(deny_code(root_with({"hops": [], "expect": {"outcome": "PASS", "trace": "clean", "hops": []}})),
                         "empty_chain")
        self.assertEqual(cli(bad("bad_empty_chain.json")), (2, "", "ERROR empty_chain: case 1 has no hops; an empty "
                                                                    "chain has no message to score (on_expiry=DENY)\n"))

    def test_single_hop(self):
        r = pt.trace_case(case([hop("mul", "3")], start="1", tol="0.1"))
        self.assertEqual((r["outcome"], r["trace"], [x["class"] for x in r["hops"]]), ("PASS", "clean", ["clean"]))
        r = pt.trace_case(case([hop("mul", "3", fault="-0.2")], start="1", tol="0.1"))
        self.assertEqual((r["outcome"], r["trace"], [x["class"] for x in r["hops"]], r["final_error"]),
                         ("FAIL", "reached_end", ["introduced"], D("0.2")))

    def test_huge_values(self):
        self.assertEqual(deny_code(root_with({"start": D("1000000")})), "no deny")
        self.assertEqual(deny_code(root_with({"start": D("-1000000")})), "no deny")
        self.assertEqual(deny_code(root_with({"start": D("1000000.000000000001")})), "out_of_range")
        # just over the cap beyond 28 significant digits: compared exactly, before any rounding
        self.assertEqual(deny_code(root_with({"start": D("1000000.0000000000000000000001")})), "out_of_range")
        for field in ("start", "tolerance"):
            self.assertEqual(deny_code(root_with({field: D("1E+999999999")})), "out_of_range", field)
            self.assertEqual(deny_code(root_with({field: D("0E+999999999")})), "bad_number", field)
        self.assertEqual(deny_code(root_with(hop_fields={"arg": D("1E+999999999")})), "out_of_range")
        self.assertEqual(deny_code(root_with(hop_fields={"fault": D("0E+999999999")})), "bad_number")
        self.assertEqual(deny_code(root_with({"start": D("1E+1")})), "bad_number")

    def test_tiny_values(self):
        self.assertEqual(deny_code(root_with({"tolerance": D("1E-12")})), "no deny")
        self.assertEqual(deny_code(root_with({"tolerance": D("1E-13")})), "bad_number")
        self.assertEqual(deny_code(root_with(hop_fields={"fault": D("1E-999999999")})), "bad_number")
        self.assertEqual(cli(bad("bad_tiny_exponent.json")),
                         (2, "", "ERROR bad_number: case 1 hop 1 fault has more than 12 decimal places (on_expiry=DENY)\n"))

    def test_negative_zero(self):
        fx = pt.validate(root_with({"start": D("-0.0")}, {"fault": D("-0")}))
        c = fx["cases"][0]
        self.assertEqual((c["start"].is_signed(), c["hops"][0]["fault"].is_signed()), (False, False))
        r = pt.trace_case(case([hop("add", "-3"), hop("mul", "0")], start="-0.0"))
        self.assertEqual([x["message"].is_signed() for x in r["hops"]], [True, False])
        self.assertEqual(r["hops"][1]["message"], D(0))
        self.assertEqual(deny_code(root_with({"tolerance": D("-0.0")})), "bad_tolerance")
        text = pt.report(result("more.json"))
        self.assertIn("| negative_zero | 2 | second | 0.0 | 0.0 | 0.0 | clean |", text.splitlines())

    def test_nan_and_infinity_are_bad_number(self):
        for name, line in (("bad_nan_start.json", "JSON constant NaN is not a finite number"),
                           ("bad_infinity_arg.json", "JSON constant Infinity is not a finite number"),
                           ("bad_neg_infinity_fault.json", "JSON constant -Infinity is not a finite number")):
            self.assertEqual(cli(bad(name)), (2, "", "ERROR bad_number: %s (on_expiry=DENY)\n" % line))
        for value in (D("Infinity"), D("-Infinity"), D("NaN")):
            self.assertEqual(deny_code(root_with({"start": value})), "bad_number", value)

    def test_bool_is_not_a_number(self):
        self.assertEqual(cli(bad("bad_start_bool.json")),
                         (2, "", "ERROR bad_type: case 1 start must be a number (on_expiry=DENY)\n"))
        self.assertEqual(deny_code(root_with({"tolerance": True})), "bad_type")
        self.assertEqual(deny_code(root_with(hop_fields={"arg": False})), "bad_type")
        self.assertEqual(deny_code(root_with(hop_fields={"recheck": 1})), "bad_type")

    def test_non_finite_after_computation(self):
        try:  # exactly 1E+15 is inside the computed cap
            got = pt.trace_case(case([hop("mul", "1000000"), hop("mul", "1000")], start="1000000"))["hops"][-1]["message"]
        except pt.TraceError as e:
            got = e.code
        self.assertEqual(got, D("1E+15"))
        with self.assertRaises(pt.TraceError) as cm:
            pt.trace_case(case([hop("mul", "1000000"), hop("mul", "1000000")], start="1000000"))
        self.assertEqual(cm.exception.code, "computed_out_of_range")
        self.assertEqual(cli(bad("bad_computed_overflow.json")),
                         (2, "", "ERROR computed_out_of_range: a computed value leaves +-1E+15 (on_expiry=DENY)\n"))

    def test_tolerance_edge_survives_long_multiplication(self):
        # exact e == tol after three 12-place multiplications near the input cap: at 40 digits this rounded to
        # 0.5000000000000000000000000000000001 and flipped PASS/clean to FAIL/introduced
        hops = [{"agent": "m1", "op": "mul", "arg": D("0.999999999989"), "fault": D(0), "recheck": False},
                {"agent": "m2", "op": "mul", "arg": D("0.999999999999"), "fault": D(0), "recheck": False},
                {"agent": "m3", "op": "mul", "arg": D("0.999999999989"), "fault": D(0), "recheck": False},
                {"agent": "f", "op": "add", "arg": D(0), "fault": D("0.5"), "recheck": False}]
        case = {"id": "flip", "label": "edge", "start": D("999999.999999999999"), "tolerance": D("0.5"), "hops": hops,
                "expect": {"outcome": "PASS", "trace": "clean", "hops": ["clean"] * 4}}
        try:
            row = pt.trace_case(case)
        except pt.TraceError as e:
            self.fail("an in-cap chain must stay exact, got %s" % e.code)
        self.assertEqual(row["hops"][-1]["error"], D("0.5"))
        self.assertEqual((row["outcome"], row["trace"], [x["class"] for x in row["hops"]]),
                         ("PASS", "clean", ["clean"] * 4))

    def test_rounded_step_is_deny_not_silent(self):
        # built past the loader caps on purpose (40-place args): a step that would round is DENY, never a quiet result
        hops = [{"agent": "a%d" % n, "op": "mul", "arg": D("0." + "3" * 40), "fault": D(0), "recheck": False}
                for n in range(20)]
        case = {"id": "deep", "label": "deep", "start": D(1), "tolerance": D("0.5"), "hops": hops,
                "expect": {"outcome": "PASS", "trace": "clean", "hops": ["clean"] * 20}}
        with self.assertRaises(pt.TraceError) as cm:
            pt.trace_case(case)
        self.assertEqual(cm.exception.code, "computed_out_of_range")

    def test_classification_edges(self):
        tol = D("0.25")
        self.assertEqual(pt.classify(D(0), D("0.25"), tol), "clean")              # e = tol is within tolerance
        self.assertEqual(pt.classify(D(0), D("0.250000000001"), tol), "introduced")
        self.assertEqual(pt.classify(D("0.25"), D("5"), tol), "introduced")       # p = tol counts as no error received
        self.assertEqual(pt.classify(D("2"), D("2"), tol), "amplified")           # equal magnitude: amplified (pinned)
        self.assertEqual(pt.classify(D("2"), D("3"), tol), "amplified")
        self.assertEqual(pt.classify(D("2"), D("1.999999999999"), tol), "attenuated")
        self.assertEqual(pt.classify(D("2"), D("0.250000000001"), tol), "attenuated")
        self.assertEqual(pt.classify(D("2"), D("0.25"), tol), "corrected")        # back to e = tol: corrected
        self.assertEqual(pt.classify(D("2"), D("0"), tol), "corrected")


class RequiredCaseTests(unittest.TestCase):
    """The three required cases on fixtures/main.json; arm B must tell all three apart."""

    def test_i_error_reaches_end(self):
        r = rows("main.json")["reaches_end"]
        self.assertEqual((r["outcome"], r["trace"], [x["class"] for x in r["hops"]]),
                         ("FAIL", "reached_end", ["introduced", "amplified", "amplified"]))
        self.assertEqual([x["error"] for x in r["hops"]], [D(2), D(4), D(4)])

    def test_ii_corrected_later_is_not_no_error(self):
        r = rows("main.json")["corrected_later"]
        self.assertEqual((r["outcome"], r["trace"], [x["class"] for x in r["hops"]]),
                         ("PASS", "corrected", ["introduced", "attenuated", "corrected"]))
        self.assertGreater(max(x["error"] for x in r["hops"]), r["tolerance"])
        line = [x for x in pt.report(result("main.json")).splitlines() if x.startswith("- corrected_later ")]
        self.assertEqual(line, ["- corrected_later (the same error is halved, then a rechecking agent recomputes from the "
                                "source): outcome PASS; trace corrected: error introduced at hop 1 (drafter); corrected "
                                "at hop 3 (verifier); final PASS, but an error did occur; planted: closed"])

    def test_iii_clean_run(self):
        r = rows("main.json")["clean_run"]
        self.assertEqual((r["outcome"], r["trace"], max(x["error"] for x in r["hops"])), ("PASS", "clean", D(0)))
        self.assertIn("- clean_run (no planted fault): outcome PASS; trace clean: no hop error above tolerance; "
                      "planted: closed", pt.report(result("main.json")).splitlines())

    def test_arm_a_cannot_tell_but_arm_b_can(self):
        r = rows("main.json")
        self.assertEqual([r[k]["outcome"] for k in ("reaches_end", "corrected_later", "clean_run")],
                         ["FAIL", "PASS", "PASS"])
        self.assertEqual([r[k]["trace"] for k in ("reaches_end", "corrected_later", "clean_run")],
                         ["reached_end", "corrected", "clean"])
        res = result("main.json")
        self.assertEqual((res["a_passes"], res["errors_hidden_by_a"], res["closed_a"], res["closed_b"]), (2, 1, 3, 3))


class ReportTests(unittest.TestCase):
    def test_main_hop_rows_exact(self):
        lines = pt.report(result("main.json")).splitlines()
        i = lines.index("| case | hop | agent | reference | message | error | class |")
        self.assertEqual(lines[i + 1:i + 11], [
            "|---|---|---|---|---|---|---|",
            "| reaches_end | 1 | drafter | 15 | 17 | 2 | introduced |",
            "| reaches_end | 2 | scaler | 30 | 34 | 4 | amplified |",
            "| reaches_end | 3 | finisher | 31 | 35 | 4 | amplified |",
            "| corrected_later | 1 | drafter | 15 | 17 | 2 | introduced |",
            "| corrected_later | 2 | summarizer | 7.5 | 8.5 | 1.0 | attenuated |",
            "| corrected_later | 3 | verifier (recheck) | 10.5 | 10.5 | 0.0 | corrected |",
            "| clean_run | 1 | drafter | 15 | 15 | 0 | clean |",
            "| clean_run | 2 | summarizer | 7.5 | 7.5 | 0.0 | clean |",
            "| clean_run | 3 | finisher | 10.5 | 10.5 | 0.0 | clean |"])

    def test_arm_a_table_and_summary(self):
        text = pt.report(result("main.json"))
        for line in ("| reaches_end | 35 | 31 | 0.5 | FAIL |", "| corrected_later | 10.5 | 10.5 | 0.5 | PASS |",
                     "arm A: 2 of 3 cases PASS; it cannot say whether an error occurred on the way",
                     "arm A closed: 3 / 3 (outcome only)", "arm B closed: 3 / 3 (outcome, trace and every hop class)",
                     "final PASS with an error on the way (hidden from arm A): 1", "gate: PASS", "on_expiry: DENY"):
            self.assertIn(line, text.splitlines())
        arm_a = text.split("## Arm per_hop_trace (B)")[0].split("## Arm outcome_only (A)")[1]
        for word in ("introduced", "corrected", "amplified", "attenuated", "clean"):
            self.assertNotIn("| %s |" % word, arm_a)

    def test_more_stories(self):
        lines = pt.report(result("more.json")).splitlines()
        self.assertIn("- corrected_then_again (corrected, then a new fault at the last hop): outcome FAIL; trace "
                      "reached_end: error introduced at hop 1 (first), 3 (third); corrected at hop 2 (second); the "
                      "error reaches the final answer; planted: closed", lines)
        self.assertIn("- attenuated_to_pass (halved until within tolerance, with no recheck): outcome PASS; trace "
                      "corrected: error introduced at hop 1 (first); corrected at hop 3 (third); final PASS, but an "
                      "error did occur; planted: closed", lines)
        self.assertIn("| extremes | 2 | second | 999999000000 | 999999000000.000000000002 | 0.000000000002 | introduced |",
                      lines)
        self.assertIn("arm B closed: 10 / 10 (outcome, trace and every hop class)", lines)

    def test_every_json_row_matches_its_planting(self):
        for name in VALID:
            code, out, err = cli("--json", os.path.join(FIX, name))
            self.assertEqual((code, err), (0, ""))
            with open(os.path.join(FIX, name), encoding="utf-8") as fh:
                raw = json.loads(fh.read(), parse_float=D, parse_int=D)["cases"]
            got = json.loads(out).get("rows", [])
            self.assertEqual(len(got), len(raw))
            for row, c in zip(got, raw):
                e = c["expect"]
                self.assertEqual((row.get("id"), row.get("outcome"), row.get("trace"),
                                  [x.get("class") for x in row.get("hops", [])]),
                                 (c["id"], e["outcome"], e["trace"], e["hops"]), (name, c["id"]))


class GateTests(unittest.TestCase):
    def run_text(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "f.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            return cli(path)

    def main_text(self):
        with open(os.path.join(FIX, "main.json"), encoding="utf-8") as fh:
            return fh.read()

    def test_wrong_trace_planting_opens_arm_b_only(self):
        text = self.main_text().replace('"trace": "corrected"', '"trace": "clean"')
        code, out, err = self.run_text(text)
        self.assertEqual((code, err), (1, ""))
        for line in ("arm A closed: 3 / 3 (outcome only)", "arm B closed: 2 / 3 (outcome, trace and every hop class)",
                     "gate: FAIL"):
            self.assertIn(line, out.splitlines())

    def test_wrong_outcome_planting_opens_arm_a(self):
        text = self.main_text().replace('"outcome": "FAIL", "trace": "reached_end"', '"outcome": "PASS", "trace": "reached_end"')
        code, out, err = self.run_text(text)
        self.assertEqual((code, err), (1, ""))
        for line in ("arm A: 2 of 3 cases PASS; it cannot say whether an error occurred on the way",
                     "arm A closed: 2 / 3 (outcome only)", "arm B closed: 2 / 3 (outcome, trace and every hop class)"):
            self.assertIn(line, out.splitlines())

    def test_size_cap_boundary(self):
        text = self.main_text().rstrip("\n")
        at_cap = text + " " * (65536 - len(text.encode("utf-8")) - 1) + "\n"
        self.assertEqual(len(at_cap.encode("utf-8")), 65536)
        code, out, err = self.run_text(at_cap)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.run_text(at_cap + " "),
                         (2, "", "ERROR too_large: fixture is larger than 65536 bytes (on_expiry=DENY)\n"))

    def test_wrong_hop_class_opens_the_gate(self):
        text = self.main_text().replace('["introduced", "amplified", "amplified"]', '["introduced", "amplified", "attenuated"]')
        code, out, err = self.run_text(text)
        self.assertEqual((code, "arm B closed: 2 / 3 (outcome, trace and every hop class)" in out), (1, True))

    def test_valid_fixtures_exit_zero(self):
        for name in VALID:
            code, out, err = cli(os.path.join(FIX, name))
            self.assertEqual((code, err, out.endswith("gate: PASS\non_expiry: DENY\n")), (0, "", True))


class ContractTests(unittest.TestCase):
    def test_bad_fixture_set_matches_folder(self):
        self.assertEqual(sorted(os.listdir(os.path.join(FIX, "bad"))), sorted(BAD_CODES))

    def test_every_bad_fixture_fails_closed(self):
        for name, code in sorted(BAD_CODES.items()):
            with self.subTest(name=name):
                try:
                    pt.run(pt.load_fixture(bad(name)))
                    got = "no deny"
                except pt.TraceError as e:
                    got = e.code
                self.assertEqual(got, code)
                if got != code:
                    continue  # do not render input the mutant failed to deny
                rc, out, err = cli(bad(name))
                self.assertEqual((rc, out, err.count("\n")), (2, "", 1))
                self.assertTrue(err.startswith("ERROR %s: " % code) and err.endswith(" (on_expiry=DENY)\n"), err)

    def test_missing_file_and_usage(self):
        self.assertEqual(cli(os.path.join(FIX, "nope.json")),
                         (2, "", "ERROR unreadable: fixture is missing or cannot be read (on_expiry=DENY)\n"))
        self.assertEqual(cli(), (2, "", "ERROR usage: propagation_trace.py [--json] FIXTURE.json (on_expiry=DENY)\n"))


class DemoTests(unittest.TestCase):
    def test_demo_is_both_reports_and_deterministic(self):
        a, b = io.StringIO(), io.StringIO()
        demo.main(a)
        demo.main(b)
        self.assertEqual(a.getvalue(), b.getvalue())
        self.assertEqual(a.getvalue(), pt.report(result("main.json")) + "\n" + pt.report(result("more.json")))


class EvidenceTests(unittest.TestCase):
    def test_evidence(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            ev = json.load(fh)
        self.assertEqual(ev["source"]["citation_title"], "From Local Errors to System Failures: Modeling and "
                         "Benchmarking Error Propagation in Multi-Agent LLM Systems")
        self.assertEqual((ev["source"]["arxiv"], ev["source"]["licence"]), ("2611.31063", "arXiv nonexclusive-distrib 1.0"))
        self.assertEqual((ev["code_copied"], ev["on_expiry"]), (False, "DENY"))
        self.assertEqual(ev["timeouts"]["mutants"], {"seconds": 300, "on_expiry": "DENY"})
        figures = " ".join(x["what"] for x in ev["on_unmeasured"])
        for fig in ("0.84", "0.47", "19 percentage points", "16%"):
            self.assertIn(fig, figures)
        self.assertTrue(all(x["status"] == "UNVERIFIED" and x["reproduced"] is False for x in ev["on_unmeasured"]))
        for name in VALID:
            res = result(name)
            got = {k: res[k] for k in ("total", "closed_a", "closed_b", "a_passes", "errors_hidden_by_a")}
            self.assertEqual(ev["measured"][name[:-5]], got)


class MutantsHarnessTests(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(mutants.classify(None, {}), "TIMEOUT")
        self.assertEqual(mutants.classify(mutants.LOAD_FAILED, {}), "CRASH")
        self.assertEqual(mutants.classify(0, {"failures": 0, "errors": 0}), "SURVIVED")
        self.assertEqual(mutants.classify(1, {"failures": 1, "errors": 2}), "KILLED-behaviour")
        self.assertEqual(mutants.classify(1, {"failures": 0, "errors": 2}), "CRASH")
        self.assertEqual(mutants.classify(1, {}), "CRASH")
        self.assertEqual(mutants.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})
