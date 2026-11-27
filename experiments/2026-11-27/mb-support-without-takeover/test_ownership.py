"""Tests for ownership.py. Expected numbers are written out here from the fixture, not read from module
constants. No test reads a source file."""

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import mutants
import ownership

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "fixtures", "main.json")
BAD = os.path.join(HERE, "fixtures", "bad")
DENY_LINE = re.compile(r"DENY [a-z_]+: \S[^\n]*\n\Z")
TIMEOUT = {"seconds": 60, "on_expiry": "DENY"}

# Character counts written out from the fixture texts (Unicode code points; all ASCII here).
THANKS = 7
LUCKY = 20
AIR = 19
SMILE = 20
EXPAND = 43
THANK_YOU = 18
AMEN = 6
LONG_AI = 68
CHOSE = 21
HEAVY_HUMAN = THANKS
HEAVY_AI = LUCKY + AIR + SMILE  # 59
HEAVY_TOTAL = HEAVY_HUMAN + HEAVY_AI  # 66
SCAFFOLD_TOTAL = THANKS + EXPAND  # 50
PARTIAL_HUMAN = THANK_YOU  # 18
PARTIAL_TOTAL = THANK_YOU + AMEN  # 24
REWRITE_TOTAL = THANK_YOU + CHOSE  # 39
MIN_NUM = 3
MIN_DEN = 4
MIN_HELP = 1

BAD_CODES = {
    "self_reported_ownership": "self_reported_measure",
    "self_reported_help": "self_reported_measure",
    "type_id_list": "bad_type",
    "type_id_dict": "bad_type",
    "type_null": "bad_type",
    "type_bool": "bad_type",
    "type_float": "bad_type",
    "not_json": "not_json",
    "duplicate_key": "duplicate_key",
    "unknown_field": "unknown_field",
    "missing_field": "missing_field",
    "bad_version": "bad_version",
    "on_expiry_other": "bad_on_expiry",
    "too_large": "too_large",
    "unknown_mode": "unknown_mode",
    "unknown_op": "unknown_op",
    "unknown_span": "unknown_span",
    "out_of_range": "out_of_range",
    "too_many_sessions": "too_many",
    "too_many_events": "too_many",
    "text_too_long": "too_long",
    "string_too_long": "bad_type",
    "expected_mismatch": "bad_expected",
    "duplicate_id": "duplicate_id",
    "empty_surviving": "empty_surviving",
    "bad_den": "out_of_range",
}


def raw():
    with open(MAIN) as fh:
        return json.load(fh)


def deny_code(root):
    try:
        ownership.validate(root)
    except ownership.Deny as e:
        return e.code
    return None


def cli(*args):
    out, err = io.StringIO(), io.StringIO()
    rc = ownership.main(["ownership.py"] + list(args), out, err)
    return rc, out.getvalue(), err.getvalue()


def result(root=None):
    return ownership.run(ownership.validate(raw() if root is None else root))


def row(res, sid):
    found = [r for r in res["rows"] if r.get("session") == sid]
    return found[0] if found else {}


class MeasureTests(unittest.TestCase):
    def test_heavy_cowrite_help_and_ownership(self):
        r = row(result(), "heavy_cowrite")
        self.assertEqual(r["accepted_help_count"], 3)
        self.assertEqual(r["human_chars"], HEAVY_HUMAN)
        self.assertEqual(r["ai_chars"], HEAVY_AI)
        self.assertEqual(r["total_chars"], HEAVY_TOTAL)
        self.assertEqual(r["ownership_raw"], "7/66")
        self.assertLess(HEAVY_HUMAN * MIN_DEN, MIN_NUM * HEAVY_TOTAL)

    def test_scaffold_ownership_one_and_text_grows(self):
        r = row(result(), "scaffold_with_human_expansion")
        self.assertEqual(r["accepted_help_count"], 0)
        self.assertEqual(r["scaffold_shown"], 2)
        self.assertEqual(r["human_chars"], SCAFFOLD_TOTAL)
        self.assertEqual(r["ai_chars"], 0)
        self.assertEqual(r["total_chars"], SCAFFOLD_TOTAL)
        self.assertEqual(r["ownership"], "1/1")
        self.assertEqual(r["start_chars"], THANKS)
        self.assertTrue(r["text_grew"])
        self.assertGreater(r["total_chars"], r["start_chars"])

    def test_cowrite_all_rejected_help_zero_ownership_one(self):
        r = row(result(), "cowrite_all_rejected")
        self.assertEqual(r["accepted_help_count"], 0)
        self.assertEqual(r["human_chars"], THANKS)
        self.assertEqual(r["ai_chars"], 0)
        self.assertEqual(r["ownership"], "1/1")
        self.assertFalse(r["text_grew"])

    def test_partial_cowrite_sits_exactly_on_three_quarters(self):
        r = row(result(), "partial_cowrite_within_cap")
        self.assertEqual(r["accepted_help_count"], 1)
        self.assertEqual(r["human_chars"], PARTIAL_HUMAN)
        self.assertEqual(r["total_chars"], PARTIAL_TOTAL)
        self.assertEqual(r["ownership"], "3/4")
        self.assertEqual(PARTIAL_HUMAN * MIN_DEN, MIN_NUM * PARTIAL_TOTAL)

    def test_human_rewrite_surviving_is_all_human(self):
        r = row(result(), "human_rewrite_restores_ownership")
        self.assertEqual(r["accepted_help_count"], 1)
        self.assertEqual(r["human_chars"], REWRITE_TOTAL)
        self.assertEqual(r["ai_chars"], 0)
        self.assertEqual(r["total_chars"], REWRITE_TOTAL)
        self.assertEqual(r["ownership"], "1/1")
        # Cumulative accepted AI text is large; surviving ownership is not.
        self.assertGreater(LONG_AI, 0)
        self.assertLess(THANK_YOU * MIN_DEN, MIN_NUM * (THANK_YOU + LONG_AI))


class ArmTests(unittest.TestCase):
    def test_heavy_cowrite_a_pass_b_fail(self):
        r = row(result(), "heavy_cowrite")
        self.assertEqual((r["arm_a"], r["arm_b"]), ("PASS", "FAIL"))

    def test_scaffold_a_fail_b_pass(self):
        r = row(result(), "scaffold_with_human_expansion")
        self.assertEqual((r["arm_a"], r["arm_b"]), ("FAIL", "PASS"))

    def test_cowrite_all_rejected_a_fail_b_pass(self):
        r = row(result(), "cowrite_all_rejected")
        self.assertEqual((r["arm_a"], r["arm_b"]), ("FAIL", "PASS"))

    def test_partial_cowrite_both_pass(self):
        r = row(result(), "partial_cowrite_within_cap")
        self.assertEqual((r["arm_a"], r["arm_b"]), ("PASS", "PASS"))

    def test_human_rewrite_both_pass(self):
        r = row(result(), "human_rewrite_restores_ownership")
        self.assertEqual((r["arm_a"], r["arm_b"]), ("PASS", "PASS"))


class RuleTests(unittest.TestCase):
    def test_gate_pass_on_main_exit_0(self):
        res = result()
        self.assertEqual(res["gate"], "PASS")
        rc, out, err = cli(MAIN)
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("gate: PASS", out)

    def test_wrong_declared_table_fails_gate_exit_1(self):
        root = raw()
        root["expected"]["heavy_cowrite"]["arm_b"] = "PASS"
        res = result(root)
        self.assertEqual(res["gate"], "FAIL")
        path = None
        try:
            fd, path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(root, fh)
            rc, out, err = cli(path)
            self.assertEqual((rc, err), (1, ""))
            self.assertIn("gate: FAIL", out)
        finally:
            if path:
                os.remove(path)

    def test_ownership_compare_is_exact_rational(self):
        # Inclusive bound at 18/24 = 3/4; one character less is below the bound.
        on_bound = {
            "human_chars": 18, "total_chars": 24, "ai_chars": 6, "mode": "cowrite",
            "inserted_human_chars": 18, "accepted_ai_chars": 6,
        }
        below = {
            "human_chars": 17, "total_chars": 24, "ai_chars": 7, "mode": "cowrite",
            "inserted_human_chars": 17, "accepted_ai_chars": 7,
        }
        self.assertEqual(ownership.arm_b(on_bound, 3, 4), "PASS")
        self.assertEqual(ownership.arm_b(below, 3, 4), "FAIL")
        self.assertEqual(18 * 4, 3 * 24)
        self.assertLess(17 * 4, 3 * 24)
        # Arm A uses an integer help count, not a float.
        self.assertEqual(ownership.arm_a(1, 1), "PASS")
        self.assertEqual(ownership.arm_a(0, 1), "FAIL")

    def test_scaffold_prompts_are_not_help(self):
        r = row(result(), "scaffold_with_human_expansion")
        self.assertEqual(r["scaffold_shown"], 2)
        self.assertEqual(r["accepted_help_count"], 0)
        self.assertEqual(ownership.arm_a(0, MIN_HELP), "FAIL")

    def test_mode_is_a_label_only(self):
        root = raw()
        # Same events as heavy_cowrite, but labelled scaffold: arms must not change.
        for session in root["sessions"]:
            if session["id"] == "heavy_cowrite":
                session["mode"] = "scaffold"
        r = row(result(root), "heavy_cowrite")
        self.assertEqual(r["mode"], "scaffold")
        self.assertEqual((r["arm_a"], r["arm_b"]), ("PASS", "FAIL"))


class DenyTests(unittest.TestCase):
    def test_ids_type_checked_before_lookup(self):
        cases = [
            ("sessions", 0, "id", ["heavy_cowrite"]),
            ("sessions", 0, "id", {"x": 1}),
            ("sessions", 1, "id", ["scaffold_with_human_expansion"]),
        ]
        for key, i, field, value in cases:
            root = raw()
            root[key][i][field] = value
            self.assertEqual(deny_code(root), "bad_type", (key, field, value))
        root = raw()
        root["sessions"][0]["events"][1]["id"] = ["a1"]
        self.assertEqual(deny_code(root), "bad_type")

    def test_type_probes_list_dict_none_bool_float(self):
        root = raw()
        root["sessions"][0]["id"] = ["heavy_cowrite"]
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["sessions"][0]["events"] = {"op": "human_insert"}
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["sessions"][0]["mode"] = None
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["min_help"] = True
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["min_help"] = False
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["min_ownership"]["num"] = True
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["min_help"] = 1.5
        self.assertEqual(deny_code(root), "bad_type")

    def test_bool_is_not_accepted_as_int(self):
        root = raw()
        root["min_help"] = True
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["sessions"][4]["events"][3] = {"op": "delete", "index": False}
        self.assertEqual(deny_code(root), "bad_type")

    def test_self_reported_fields_are_denied_on_validate(self):
        fields = [
            "ownership",
            "ownership_ratio",
            "help_count",
            "accepted_help",
            "human_chars",
            "ai_chars",
            "agency",
            "perceived_agency",
        ]
        for field in fields:
            root = raw()
            root["sessions"][0][field] = 1
            self.assertEqual(deny_code(root), "self_reported_measure", field)

    def test_on_expiry_closed_set(self):
        for value in ("DENY", "SAFE_FALLBACK", "ESCALATE", "HOLD"):
            root = raw()
            root["on_expiry"] = value
            self.assertIsNotNone(ownership.validate(root))
        root = raw()
        root["on_expiry"] = "YES"
        self.assertEqual(deny_code(root), "bad_on_expiry")
        root = raw()
        root["on_expiry"] = "deny"
        self.assertEqual(deny_code(root), "bad_on_expiry")

    def test_size_caps(self):
        root = raw()
        root["sessions"].extend(
            {
                "id": "extra_%d" % i,
                "mode": "cowrite",
                "events": [{"op": "human_insert", "id": "h0", "text": "Thanks."}],
            }
            for i in range(8)
        )
        for session in root["sessions"]:
            sid = session["id"]
            if sid not in root["expected"]:
                root["expected"][sid] = {"arm_a": "FAIL", "arm_b": "PASS"}
        self.assertEqual(deny_code(root), "too_many")
        root = raw()
        root["sessions"][0]["events"].extend(
            {"op": "offer", "id": "z%d" % i, "text": " x"} for i in range(24)
        )
        self.assertEqual(deny_code(root), "too_many")
        root = raw()
        root["sessions"][0]["events"][0]["text"] = "A" * 257
        self.assertEqual(deny_code(root), "too_long")

    def test_unknown_mode_and_op(self):
        root = raw()
        root["sessions"][0]["mode"] = "autopilot"
        self.assertEqual(deny_code(root), "unknown_mode")
        root = raw()
        root["sessions"][0]["events"][0]["op"] = "merge"
        self.assertEqual(deny_code(root), "unknown_op")

    def test_out_of_range_span_and_empty_surviving(self):
        root = raw()
        root["sessions"][2]["events"].append({"op": "delete", "index": 99})
        self.assertEqual(deny_code(root), None)
        with self.assertRaises(ownership.Deny) as ctx:
            ownership.run(ownership.validate(root))
        self.assertEqual(ctx.exception.code, "out_of_range")
        root = raw()
        root["sessions"][2]["events"].append({"op": "delete", "id": "h0"})
        with self.assertRaises(ownership.Deny) as ctx:
            ownership.run(ownership.validate(root))
        self.assertEqual(ctx.exception.code, "empty_surviving")

    def test_utf8_decode_failure(self):
        path = None
        try:
            fd, path = tempfile.mkstemp(suffix=".json")
            os.write(fd, b"{\xff\xfe not utf-8")
            os.close(fd)
            with self.assertRaises(ownership.Deny) as ctx:
                ownership.load(path)
            self.assertEqual(ctx.exception.code, "bad_utf")
            rc, out, err = cli(path)
            self.assertEqual((rc, out), (2, ""))
            self.assertTrue(err.startswith("DENY bad_utf: "))
            self.assertRegex(err, DENY_LINE)
            self.assertEqual(err.count("\n"), 1)
        finally:
            if path:
                os.remove(path)

    def test_bad_fixtures_deny_exit_2_one_line(self):
        names = sorted(f[:-5] for f in os.listdir(BAD) if f.endswith(".json"))
        self.assertEqual(names, sorted(BAD_CODES))
        for name in names:
            path = os.path.join(BAD, name + ".json")
            try:
                ownership.load(path)
                try:
                    ownership.run(ownership.load(path))
                    code = None
                except ownership.Deny as e:
                    code = e.code
            except ownership.Deny as e:
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

    def test_deep_nesting_is_deny_not_traceback(self):
        # 3000 nested lists fit under the 32768-byte cap; the walk must DENY, not raise RecursionError.
        with open(MAIN, encoding="utf-8") as fh:
            text = fh.read()
        deep = "[" * 3000 + "]" * 3000
        path = None
        try:
            fd, path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text.replace('"min_help": 1', '"min_help": ' + deep, 1))
            self.assertLess(os.path.getsize(path), ownership.MAX_BYTES)
            proc = subprocess.run([sys.executable, "-B", os.path.join(HERE, "ownership.py"), path],
                                  capture_output=True, text=True, timeout=TIMEOUT["seconds"])
            self.assertEqual((proc.returncode, proc.stdout), (2, ""))
            self.assertTrue(proc.stderr.startswith("DENY too_deep: "), proc.stderr[:80])
            self.assertRegex(proc.stderr, DENY_LINE)
        finally:
            if path:
                os.remove(path)

    def test_depth_bound_in_process(self):
        # In-process, so an in-memory mutant of the depth walk is the code under test.
        # A RecursionError is recorded as a wrong result (assertion failure), not left as a crash.
        with open(MAIN, encoding="utf-8") as fh:
            text = fh.read()
        cases = [
            ("[" * 15 + "1" + "]" * 15, "bad_type"),
            ("[" * 16 + "1" + "]" * 16, "too_deep"),
            ('{"a":' * 15 + "1" + "}" * 15, "bad_type"),
            ('{"a":' * 16 + "1" + "}" * 16, "too_deep"),
            ("[" * 3000 + "]" * 3000, "too_deep"),
            ('{"a":' * 2000 + "1" + "}" * 2000, "too_deep"),
        ]
        for value, want in cases:
            path = None
            try:
                fd, path = tempfile.mkstemp(suffix=".json")
                os.close(fd)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text.replace('"min_help": 1', '"min_help": ' + value, 1))
                try:
                    ownership.load(path)
                    got = None
                except ownership.Deny as e:
                    got = e.code
                except RecursionError:
                    got = "RecursionError"
                self.assertEqual(got, want, value[:12])
            finally:
                if path:
                    os.remove(path)

    def test_gate_compares_arm_a_too(self):
        root = raw()
        root["expected"]["heavy_cowrite"]["arm_a"] = "FAIL"
        self.assertEqual(result(root)["gate"], "FAIL")

    def test_on_expiry_pass_like_values_are_deny(self):
        for value in ("PASS", "ACCEPT", "OK", ""):
            root = raw()
            root["on_expiry"] = value
            self.assertEqual(deny_code(root), "bad_on_expiry", value)

    def test_delete_index_edges_are_deny(self):
        for index in (-1, 2):
            root = raw()
            root["sessions"][3]["events"].append({"op": "delete", "index": index})
            try:
                ownership.run(ownership.validate(root))
                code = None
            except ownership.Deny as e:
                code = e.code
            except IndexError:  # an unchecked index is a wrong result; other exceptions stay crashes
                code = "IndexError"
            self.assertEqual(code, "out_of_range", index)

    def test_duplicate_span_id_empty_text_and_num_over_den(self):
        root = raw()
        root["sessions"][0]["events"].append({"op": "human_expand", "id": "h0", "text": "again"})
        with self.assertRaises(ownership.Deny) as ctx:
            ownership.run(ownership.validate(root))
        self.assertEqual(ctx.exception.code, "duplicate_id")
        root = raw()
        root["sessions"][0]["events"][0]["text"] = ""
        self.assertEqual(deny_code(root), "bad_text")
        root = raw()
        root["min_ownership"] = {"num": 5, "den": 4}
        self.assertEqual(deny_code(root), "out_of_range")

    def test_forced_real_timeout_is_not_killed(self):
        rc, stdout, timed_out = mutants.run_source("import time\ntime.sleep(30)\n", timeout=2)
        verdict = mutants.classify(rc, stdout, timed_out)
        self.assertEqual((rc, timed_out, verdict), (None, True, "TIMEOUT"))
        self.assertFalse(mutants.is_killed(verdict))


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
        cmd = [sys.executable, "-B", os.path.join(HERE, "ownership.py"), "--json", MAIN]
        a = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT["seconds"])
        b = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT["seconds"])
        self.assertEqual((a.returncode, a.stderr), (0, ""))
        self.assertEqual(a.stdout, b.stdout)
        self.assertEqual(json.loads(a.stdout)["gate"], "PASS")


if __name__ == "__main__":
    unittest.main()
