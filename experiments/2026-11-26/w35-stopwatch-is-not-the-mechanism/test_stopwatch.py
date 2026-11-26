"""Tests for stopwatch.py. Expected numbers are written out here from the fixture, not read from module
constants. No test reads a source file."""

import io
import json
import os
import re
import subprocess
import sys
import unittest

import mutants
import stopwatch

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "fixtures", "main.json")
BAD = os.path.join(HERE, "fixtures", "bad")
DENY_LINE = re.compile(r"DENY [a-z_]+: \S[^\n]*\n\Z")
TIMEOUT = {"seconds": 60, "on_expiry": "DENY"}

# Harness work-costs written out from the declared op costs (square 10, pad 5, hit 1, wrong 2).
BEFORE_COST = 75 + 45 + 15  # 135
GENUINE_COST = 57 + 36 + 15  # 108
GENUINE_HITS = 3
FASTER_OTHER_COST = 50 + 30 + 10  # 90
CHEAPER_WRONG_COST = 35 + 21 + 7  # 63
CACHE_PLUS_SKIP_COST = 32 + 21 + 10  # 63
REPLAY_COST = GENUINE_COST
SAVING_PER_UNIT = 9

BAD_CODES = {
    "not_json": "not_json",
    "duplicate_key": "duplicate_key",
    "unknown_field": "unknown_field",
    "missing_field": "missing_field",
    "bad_version": "bad_version",
    "on_expiry_other": "bad_on_expiry",
    "fabricated_counter": "self_reported_measure",
    "self_reported_cost": "self_reported_measure",
    "unknown_mechanism": "unknown_mechanism",
    "bad_direction": "bad_direction",
    "type_id_list": "bad_type",
    "type_id_dict": "bad_type",
    "type_null": "bad_type",
    "type_bool": "bad_type",
    "type_float": "bad_type",
    "too_large": "too_large",
    "too_few_input_sets": "bad_input_sets",
    "too_many_versions": "too_many",
    "string_too_long": "bad_type",
    "bad_op": "bad_op",
    "missing_before": "missing_field",
    "expected_mismatch": "bad_expected",
    "too_many_ops": "too_many",
}


def raw():
    with open(MAIN) as fh:
        return json.load(fh)


def deny_code(root):
    try:
        stopwatch.validate(root)
    except stopwatch.Deny as e:
        return e.code
    return None


def cli(*args):
    out, err = io.StringIO(), io.StringIO()
    rc = stopwatch.main(["stopwatch.py"] + list(args), out, err)
    return rc, out.getvalue(), err.getvalue()


def result(root=None):
    return stopwatch.run(stopwatch.validate(raw() if root is None else root))


def row(res, vid):
    found = [r for r in res["rows"] if r.get("version") == vid]
    return found[0] if found else {}


class MeasureTests(unittest.TestCase):
    def test_harness_costs_hits_and_outputs_on_main(self):
        fx = stopwatch.validate(raw())
        by_id = {v["id"]: v for v in fx["versions"]}
        before = stopwatch.measure(by_id["before"]["ops"], fx["input_sets"])
        self.assertEqual(before["cost"], BEFORE_COST)
        self.assertEqual(before["counters"]["cache_hits"], 0)
        self.assertEqual(before["outputs"], [[9, 1, 9, 9, 4], [16, 16, 25], [49]])
        genuine = stopwatch.measure(by_id["genuine_cache"]["ops"], fx["input_sets"])
        self.assertEqual(genuine["cost"], GENUINE_COST)
        self.assertEqual(genuine["counters"]["cache_hits"], GENUINE_HITS)
        self.assertEqual(genuine["outputs"], before["outputs"])
        self.assertEqual(BEFORE_COST - GENUINE_COST, GENUINE_HITS * SAVING_PER_UNIT)
        replay = stopwatch.measure(by_id["replayed_output"]["ops"], fx["input_sets"])
        self.assertEqual(replay["cost"], REPLAY_COST)
        self.assertEqual(replay["counters"]["cache_hits"], GENUINE_HITS)
        self.assertEqual(replay["outputs"][0], before["outputs"][0])
        self.assertNotEqual(replay["outputs"][1], before["outputs"][1])
        self.assertNotEqual(replay["outputs"][2], before["outputs"][2])

    def test_digest_is_canonical_json_sha256_over_all_sets(self):
        fx = stopwatch.validate(raw())
        before = stopwatch.measure(["square", "pad"], fx["input_sets"])
        blob = json.dumps(before["outputs"], sort_keys=True, separators=(",", ":"))
        self.assertEqual(before["digest"], stopwatch.hashlib.sha256(blob.encode("utf-8")).hexdigest()
                         if hasattr(stopwatch, "hashlib") else __import__("hashlib").sha256(blob.encode("utf-8")).hexdigest())
        one = stopwatch.digest_of(before["outputs"][:1])
        self.assertNotEqual(one, before["digest"])


class ArmTests(unittest.TestCase):
    def test_cheaper_wrong_a_pass_b_fail(self):
        r = row(result(), "cheaper_wrong")
        self.assertEqual((r.get("arm_a"), r.get("arm_b"), r.get("after_cost")), ("PASS", "FAIL", CHEAPER_WRONG_COST))
        self.assertFalse(r.get("digest_same"))

    def test_faster_other_reason_a_pass_b_fail_counter_still(self):
        r = row(result(), "faster_other_reason")
        self.assertEqual((r.get("arm_a"), r.get("arm_b"), r.get("after_cost")), ("PASS", "FAIL", FASTER_OTHER_COST))
        self.assertTrue(r.get("digest_same"))
        self.assertEqual(r.get("after_hits"), 0)
        self.assertEqual(r.get("counter_delta"), 0)

    def test_replayed_output_a_pass_b_fail_because_digest(self):
        r = row(result(), "replayed_output")
        self.assertEqual((r.get("arm_a"), r.get("arm_b")), ("PASS", "FAIL"))
        self.assertFalse(r.get("digest_same"))
        self.assertEqual(r.get("after_hits"), GENUINE_HITS)
        self.assertEqual(r.get("cost_saved"), r.get("bound"))

    def test_genuine_cache_both_pass_bound_tight(self):
        r = row(result(), "genuine_cache")
        self.assertEqual((r.get("arm_a"), r.get("arm_b")), ("PASS", "PASS"))
        self.assertTrue(r.get("digest_same"))
        self.assertEqual(r.get("after_cost"), GENUINE_COST)
        self.assertEqual(r.get("cost_saved"), r.get("bound"))

    def test_no_faster_both_fail(self):
        r = row(result(), "no_faster")
        self.assertEqual((r.get("arm_a"), r.get("arm_b"), r.get("after_cost")), ("FAIL", "FAIL", BEFORE_COST))

    def test_cache_plus_skip_a_pass_b_fail_attribution(self):
        r = row(result(), "cache_plus_skip")
        self.assertEqual((r.get("arm_a"), r.get("arm_b"), r.get("after_cost")), ("PASS", "FAIL", CACHE_PLUS_SKIP_COST))
        self.assertTrue(r.get("digest_same"))
        self.assertEqual(r.get("after_hits"), GENUINE_HITS)
        self.assertGreater(r.get("cost_saved"), r.get("bound"))


class RuleTests(unittest.TestCase):
    def test_cost_tie_is_not_faster(self):
        self.assertEqual(stopwatch.arm_a(135, 135), "FAIL")
        self.assertEqual(stopwatch.arm_a(135, 134), "PASS")
        self.assertEqual(stopwatch.arm_a(135, 136), "FAIL")

    def test_missing_tied_or_reversed_counter_is_fail(self):
        before = {"cost": 100, "digest": "aaa", "counters": {"cache_hits": 2}}
        base = {"cost": 82, "digest": "aaa", "counters": {"cache_hits": 4}}
        claim = {"mechanism": "cache_hits", "direction": "up", "saving_per_unit": 9}
        self.assertEqual(stopwatch.arm_b(before, base, claim), "PASS")
        missing = {"cost": 80, "digest": "aaa", "counters": {}}
        self.assertEqual(stopwatch.arm_b(before, missing, claim), "FAIL")
        tied = {"cost": 80, "digest": "aaa", "counters": {"cache_hits": 2}}
        self.assertEqual(stopwatch.arm_b(before, tied, claim), "FAIL")
        reversed_c = {"cost": 80, "digest": "aaa", "counters": {"cache_hits": 1}}
        self.assertEqual(stopwatch.arm_b(before, reversed_c, claim), "FAIL")

    def test_gate_pass_on_main_exit_0(self):
        rc, out, err = cli(MAIN)
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("gate: PASS", out)
        self.assertIn("on_expiry: DENY", out)
        for name in ("cheaper_wrong", "faster_other_reason", "replayed_output",
                     "genuine_cache", "no_faster", "cache_plus_skip"):
            self.assertIn(name, out)

    def test_wrong_declared_table_fails_gate_exit_1(self):
        root = raw()
        root["expected"]["cheaper_wrong"]["arm_b"] = "PASS"
        res = result(root)
        self.assertFalse(row(res, "cheaper_wrong").get("matches_expected"))
        self.assertEqual(res["gate"], "FAIL")


class DenyTests(unittest.TestCase):
    def test_ids_type_checked_before_lookup(self):
        cases = [
            ("versions", 1, "id", ["cheaper_wrong"]),
            ("versions", 1, "id", {"x": 1}),
            ("input_sets", 0, "id", ["repeats"]),
            ("claim", None, "mechanism", ["cache_hits"]),
            ("claim", None, "direction", {"d": "up"}),
        ]
        for key, i, field, value in cases:
            root = raw()
            if i is None:
                root[key][field] = value
            else:
                root[key][i][field] = value
            self.assertEqual(deny_code(root), "bad_type", (key, field, value))

    def test_type_probes_list_dict_none_bool_float(self):
        root = raw()
        root["versions"][0]["id"] = ["before"]
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["versions"][0]["ops"] = {"square": 1}
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["claim"]["mechanism"] = None
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["claim"]["saving_per_unit"] = True
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["claim"]["saving_per_unit"] = False
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["input_sets"][0]["keys"][0] = True
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["fixture_version"] = 1.0
        # 1.0 may already be int if it came from Python; set a true float
        root["fixture_version"] = 1.5
        self.assertEqual(deny_code(root), "bad_version")

    def test_bool_is_not_accepted_as_int(self):
        root = raw()
        root["input_sets"][0]["keys"][0] = True
        self.assertEqual(deny_code(root), "bad_type")

    def test_self_reported_fields_are_denied_on_validate(self):
        root = raw()
        root["versions"][4]["counters"] = {"cache_hits": 9}
        self.assertEqual(deny_code(root), "self_reported_measure")
        root = raw()
        root["versions"][4]["cost"] = 0
        self.assertEqual(deny_code(root), "self_reported_measure")

    def test_unknown_mechanism_and_direction_denied(self):
        root = raw()
        root["claim"]["mechanism"] = "speedup"
        self.assertEqual(deny_code(root), "unknown_mechanism")
        root = raw()
        root["claim"]["direction"] = "sideways"
        self.assertEqual(deny_code(root), "bad_direction")

    def test_on_expiry_closed_set(self):
        for value in ("DENY", "SAFE_FALLBACK", "ESCALATE", "HOLD"):
            root = raw()
            root["on_expiry"] = value
            self.assertIsNotNone(stopwatch.validate(root))
        root = raw()
        root["on_expiry"] = "YES"
        self.assertEqual(deny_code(root), "bad_on_expiry")
        root = raw()
        root["on_expiry"] = "deny"
        self.assertEqual(deny_code(root), "bad_on_expiry")

    def test_size_caps(self):
        root = raw()
        root["versions"].extend(
            {"id": "extra_%d" % i, "ops": ["square"]} for i in range(20)
        )
        self.assertEqual(deny_code(root), "too_many")
        root = raw()
        root["versions"][1]["ops"] = ["square"] * 9
        self.assertEqual(deny_code(root), "too_many")
        root = raw()
        root["input_sets"].extend({"id": "more_%d" % i, "keys": [1]} for i in range(10))
        self.assertEqual(deny_code(root), "too_many")

    def test_bad_fixtures_deny_exit_2_one_line(self):
        names = sorted(f[:-5] for f in os.listdir(BAD) if f.endswith(".json"))
        self.assertEqual(names, sorted(BAD_CODES))
        for name in names:
            path = os.path.join(BAD, name + ".json")
            try:
                stopwatch.load(path)
                code = None
            except stopwatch.Deny as e:
                code = e.code
            self.assertEqual(code, BAD_CODES[name], name)
            rc, out, err = cli(path)
            self.assertEqual((rc, out), (2, ""), name)
            self.assertTrue(err.startswith("DENY %s: " % BAD_CODES[name]), name)
            self.assertRegex(err, DENY_LINE)
            self.assertEqual(err.count("\n"), 1, name)

    def test_missing_file_and_usage_deny(self):
        rc, out, err = cli(os.path.join(BAD, "no_such_file.json"))
        self.assertEqual((rc, out), (2, ""))
        self.assertTrue(err.startswith("DENY unreadable: "))
        self.assertRegex(err, DENY_LINE)
        rc, out, err = cli()
        self.assertEqual((rc, out), (2, ""))
        self.assertTrue(err.startswith("DENY usage: "))
        self.assertRegex(err, DENY_LINE)


class MutantHarnessTests(unittest.TestCase):
    def test_forced_crash_is_classified_as_crash_and_is_not_killed(self):
        rc, stdout, timed_out = mutants.run_source(
            "raise RuntimeError('forced crash')", timeout=TIMEOUT["seconds"]
        )
        verdict = mutants.classify(rc, stdout, timed_out)
        self.assertEqual(verdict, "CRASH")
        self.assertFalse(mutants.is_killed(verdict))
        self.assertEqual(rc, mutants.LOAD_FAILED)
        counts = mutants.tally(["KILLED-behaviour", "CRASH", "TIMEOUT", "SURVIVED"])
        self.assertEqual(counts["KILLED-behaviour"], 1)
        self.assertEqual(counts["CRASH"], 1)
        self.assertEqual(counts["TIMEOUT"], 1)
        self.assertEqual(counts["SURVIVED"], 1)
        self.assertFalse(mutants.is_killed("TIMEOUT"))
        self.assertFalse(mutants.is_killed("SURVIVED"))
        self.assertTrue(mutants.is_killed("KILLED-behaviour"))

    def test_classify_timeout_is_not_killed(self):
        self.assertEqual(mutants.classify(None, "", True), "TIMEOUT")
        self.assertFalse(mutants.is_killed("TIMEOUT"))
        self.assertEqual(mutants.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})
        self.assertEqual(TIMEOUT["on_expiry"], "DENY")

    def test_classify_other_shapes(self):
        self.assertEqual(mutants.classify(0, '{"failures": 0, "errors": 0}', False), "SURVIVED")
        self.assertEqual(mutants.classify(1, '{"failures": 2, "errors": 0}', False), "KILLED-behaviour")
        self.assertEqual(mutants.classify(1, '{"failures": 0, "errors": 2}', False), "CRASH")
        self.assertEqual(mutants.classify(1, "not-json", False), "CRASH")


class SubprocessTests(unittest.TestCase):
    def test_cli_json_twice_identical(self):
        cmd = [sys.executable, "-B", os.path.join(HERE, "stopwatch.py"), "--json", MAIN]
        a = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT["seconds"])
        b = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT["seconds"])
        self.assertEqual((a.returncode, a.stderr), (0, ""))
        self.assertEqual(a.stdout, b.stdout)
        self.assertEqual(json.loads(a.stdout)["gate"], "PASS")


if __name__ == "__main__":
    unittest.main()
