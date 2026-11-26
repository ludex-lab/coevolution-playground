"""Tests for voucher.py. Expected values are written out here from the fixture numbers, not read from module
constants. No test reads a source file."""

import io
import json
import os
import re
import subprocess
import sys
import unittest

import voucher

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "fixtures", "main.json")
BAD = os.path.join(HERE, "fixtures", "bad")
DENY_LINE = re.compile(r"DENY [a-z_]+: \S[^\n]*\n\Z")
BAD_CODES = {
    "not_json": "not_json", "duplicate_key": "duplicate_key", "unknown_field": "unknown_field",
    "missing_history": "missing_field", "question_record_list": "bad_type", "amount_float": "bad_type",
    "bad_version": "bad_version", "on_expiry_other": "bad_on_expiry", "unknown_record": "unknown_record",
    "unknown_question": "unknown_question", "duplicate_question_id": "duplicate_id", "bad_op": "bad_op",
    "out_of_range": "out_of_range", "recorded_final_wrong": "bad_history", "bad_fault": "bad_fault",
    "expected_missing_question": "bad_expected", "too_large": "too_large",
}


def raw():
    with open(MAIN) as fh:
        return json.load(fh)


def deny_code(root):
    try:
        voucher.validate(root)
    except voucher.Deny as e:
        return e.code
    return None


def cli(*args):
    out, err = io.StringIO(), io.StringIO()
    rc = voucher.main(["voucher.py"] + list(args), out, err)
    return rc, out.getvalue(), err.getvalue()


def result(root=None):
    return voucher.run(voucher.validate(raw() if root is None else root))


def sim_row(res, sid):
    found = [r for r in res["rows"] if r.get("simulator") == sid]
    return found[0] if found else {}


def statuses(row):
    return {q.get("question"): q.get("status") for q in row.get("questions", [])}


class BoundaryFirstTests(unittest.TestCase):
    def test_reference_counterfactuals_from_fixture_numbers(self):
        fx = voucher.validate(raw())
        want = {"q_rice": 10 + 5 + 3 - 1, "q_barley": 10 + 1 + 3 - 1, "q_oil": 7 + 2, "q_salt": 4 - 2 - 1,
                "q_null": 4 + 0 - 1}
        self.assertEqual({q["id"]: voucher.reference(fx, q) for q in fx["questions"]}, want)

    def test_identity_question_with_wrong_target_is_fail_not_no_intervention(self):
        fx = voucher.validate(raw())
        q = [x for x in fx["questions"] if x["id"] == "q_null"][0]
        status, why = voucher.voucher(fx, q, {"applied_to": "rice", "op": "add", "answer": 3})
        self.assertEqual(status, "FAIL")
        status, why = voucher.voucher(fx, q, {"applied_to": "salt", "op": "add", "answer": 2})
        self.assertEqual(status, "FAIL")

    def test_identity_question_matching_report_is_not_trusted(self):
        fx = voucher.validate(raw())
        q = [x for x in fx["questions"] if x["id"] == "q_null"][0]
        status, why = voucher.voucher(fx, q, {"applied_to": "salt", "op": "add", "answer": 3})
        self.assertEqual(status, "NO_INTERVENTION")

    def test_set_to_same_value_is_also_no_intervention(self):
        fx = voucher.validate(raw())
        q = {"id": "q_same", "record": "rice", "op": "set", "amount": 10}
        self.assertEqual(voucher.voucher(fx, q, {"applied_to": "rice", "op": "set", "answer": 12})[0],
                         "NO_INTERVENTION")


class ArmTests(unittest.TestCase):
    def test_case1_wrong_record_replay_pass_voucher_fail_on_that_question(self):
        r = sim_row(result(), "sim_wrong_record")
        self.assertEqual((r.get("arm_a"), r.get("arm_b")), ("PASS", "FAIL"))
        self.assertEqual(statuses(r), {"q_rice": "FAIL", "q_barley": "VOUCHED", "q_oil": "VOUCHED",
                                       "q_salt": "VOUCHED", "q_null": "NO_INTERVENTION"})

    def test_wrong_record_answer_value_matches_reference_so_only_target_check_catches_it(self):
        fx = voucher.validate(raw())
        sim = [s for s in fx["sims"] if s["id"] == "sim_wrong_record"][0]
        replayed, reports = voucher.simulate(fx, sim)
        self.assertEqual(reports["q_rice"], {"applied_to": "barley", "op": "add", "answer": 17})

    def test_wrong_operator_same_answer_caught_by_operator_check(self):
        r = sim_row(result(), "sim_wrong_operator")
        self.assertEqual((r.get("arm_a"), r.get("arm_b")), ("PASS", "FAIL"))
        self.assertEqual(statuses(r).get("q_oil"), "FAIL")
        fx = voucher.validate(raw())
        sim = [s for s in fx["sims"] if s["id"] == "sim_wrong_operator"][0]
        self.assertEqual(voucher.simulate(fx, sim)[1]["q_oil"], {"applied_to": "lamp_oil", "op": "add", "answer": 9})

    def test_misreported_target_with_matching_answer_is_vouched_boundary(self):
        # declared boundary: arm B checks the report, not the program; a silent wrong-record change is not caught
        fx = voucher.validate(raw())
        q = [x for x in fx["questions"] if x["id"] == "q_rice"][0]
        self.assertEqual(voucher.voucher(fx, q, {"applied_to": "rice", "op": "add", "answer": 17})[0], "VOUCHED")

    def test_case2_correct_simulator_both_pass(self):
        r = sim_row(result(), "sim_correct")
        self.assertEqual((r.get("arm_a"), r.get("arm_b"), r.get("trusted")), ("PASS", "PASS", 4))

    def test_case3_null_control_does_not_fail_spuriously(self):
        for sid in ("sim_correct", "sim_wrong_record", "sim_wrong_operator", "sim_drop_last_event"):
            self.assertEqual(statuses(sim_row(result(), sid)).get("q_null"), "NO_INTERVENTION", sid)

    def test_replay_failure_arm_a_fail_and_touched_question_fails(self):
        r = sim_row(result(), "sim_drop_last_event")
        self.assertEqual((r.get("arm_a"), r.get("arm_b")), ("FAIL", "FAIL"))
        self.assertEqual(statuses(r).get("q_barley"), "FAIL")
        self.assertEqual(statuses(r).get("q_rice"), "VOUCHED")


class PassRuleTests(unittest.TestCase):
    def test_close_rule_exact(self):
        self.assertEqual(voucher.arm_voucher(["VOUCHED", "NO_INTERVENTION"]), "PASS")
        self.assertEqual(voucher.arm_voucher(["VOUCHED", "FAIL"]), "FAIL")
        self.assertEqual(voucher.arm_voucher(["VOUCHED", "VOUCHED", "VOUCHED", "FAIL"]), "FAIL")
        self.assertEqual(voucher.arm_voucher(["NO_INTERVENTION", "NO_INTERVENTION"]), "FAIL")

    def test_gate_pass_on_main(self):
        rc, out, err = cli(MAIN)
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("gate: PASS", out)
        self.assertIn("on_expiry: DENY", out)

    def test_wrong_declared_table_fails_gate_exit_1(self):
        root = raw()
        root["simulators"][1]["expected"]["arm_b"] = "PASS"
        res = result(root)
        self.assertFalse(sim_row(res, "sim_wrong_record").get("matches_expected"))
        self.assertEqual(res["gate"], "FAIL")

    def test_wrong_declared_question_status_fails_gate(self):
        root = raw()
        root["simulators"][0]["expected"]["questions"]["q_null"] = "VOUCHED"
        self.assertEqual(result(root)["gate"], "FAIL")


class DenyTests(unittest.TestCase):
    def test_unhashable_ids_are_bad_type(self):
        cases = [("questions", 0, "record", ["rice"]), ("questions", 0, "id", {}),
                 ("history", 0, "record", []), ("simulators", 1, "fault_question", ["q_rice"]),
                 ("simulators", 1, "fault_value", {"a": 1})]
        for key, i, field, value in cases:
            root = raw()
            root[key][i][field] = value
            self.assertEqual(deny_code(root), "bad_type", (key, field))
        root = raw()
        root["simulators"][0]["expected"]["questions"] = [["q_rice"]]
        self.assertEqual(deny_code(root), "bad_type")

    def test_bool_amount_is_bad_type(self):
        root = raw()
        root["questions"][0]["amount"] = True
        self.assertEqual(deny_code(root), "bad_type")

    def test_bad_fixtures_deny_exit_2_one_line(self):
        names = sorted(f[:-5] for f in os.listdir(BAD) if f.endswith(".json"))
        self.assertEqual(names, sorted(BAD_CODES))
        for name in names:
            path = os.path.join(BAD, name + ".json")
            try:
                voucher.load(path)
                code = None
            except voucher.Deny as e:
                code = e.code
            self.assertEqual(code, BAD_CODES[name], name)
            if code is None:
                continue
            rc, out, err = cli(path)
            self.assertEqual((rc, out), (2, ""), name)
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
        cmd = [sys.executable, "-B", os.path.join(HERE, "voucher.py"), "--json", MAIN]
        a = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        b = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        self.assertEqual((a.returncode, a.stderr), (0, ""))
        self.assertEqual(a.stdout, b.stdout)
        self.assertEqual(json.loads(a.stdout)["gate"], "PASS")


if __name__ == "__main__":
    unittest.main()
