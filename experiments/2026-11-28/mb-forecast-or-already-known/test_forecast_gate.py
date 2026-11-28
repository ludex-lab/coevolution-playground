"""Tests for forecast_gate.py. Expected values are written out here from the fixture.
No test reads a source file.
"""

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import forecast_gate
import mutants

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "fixtures", "main.json")
BAD = os.path.join(HERE, "fixtures", "bad")
DENY_LINE = re.compile(r"DENY [a-z_]+: \S[^\n]*\n\Z")
TIMEOUT = {"seconds": 60, "on_expiry": "DENY"}
CUTOFF = "2024-12-31"

BAD_CODES = {
    "unknown_field": "unknown_field",
    "missing_field": "missing_field",
    "bad_version": "bad_version",
    "on_expiry_other": "bad_on_expiry",
    "type_bool": "bad_type",
    "type_null": "bad_type",
    "type_id_list": "bad_type",
    "type_id_dict": "bad_type",
    "type_float": "bad_type",
    "bad_date_unpadded": "bad_date",
    "bad_date_invalid": "bad_date",
    "bad_date_compact": "bad_date",
    "bad_date_int": "bad_type",
    "bad_role": "bad_role",
    "bad_weight": "bad_weight",
    "self_label_field": "self_label",
    "self_label_value": "self_label",
    "duplicate_id": "duplicate_id",
    "bad_expected": "bad_expected",
    "bad_outcome": "bad_outcome",
    "too_many": "too_many",
    "too_long": "too_long",
    "not_json": "not_json",
    "duplicate_key": "duplicate_key",
    "too_deep": "too_deep",
    "too_large": "too_large",
}


def raw():
    with open(MAIN, encoding="utf-8") as fh:
        return json.load(fh)


def deny_code(root):
    try:
        forecast_gate.validate(root)
    except forecast_gate.Deny as e:
        return e.code
    return None


def cli(*args):
    out, err = io.StringIO(), io.StringIO()
    rc = forecast_gate.main(["forecast_gate.py"] + list(args), out, err)
    return rc, out.getvalue(), err.getvalue()


def result(root):
    return forecast_gate.run(forecast_gate.validate(root))


class MainFixtureTests(unittest.TestCase):
    def setUp(self):
        self.res = forecast_gate.run(forecast_gate.load(MAIN))
        self.by_id = {r["case"]: r for r in self.res["rows"]}

    def test_own_edge_is_recall_not_forecast(self):
        row = self.by_id["own_edge"]
        self.assertEqual(row["arm_a"], "HIT")
        self.assertEqual(row["arm_b"], "MISS")
        self.assertEqual(row["class"], "recall_not_forecast")

    def test_pre_t_support_is_forecast(self):
        row = self.by_id["pre_t_support"]
        self.assertEqual(row["arm_a"], "HIT")
        self.assertEqual(row["arm_b"], "HIT")
        self.assertEqual(row["class"], "forecast")

    def test_evidence_on_cutoff_is_usable_by_b(self):
        row = self.by_id["evidence_on_cutoff"]
        self.assertEqual(row["arm_a"], "HIT")
        self.assertEqual(row["arm_b"], "HIT")
        self.assertEqual(row["class"], "forecast")

    def test_outcome_on_cutoff_is_not_scorable(self):
        row = self.by_id["outcome_on_cutoff"]
        self.assertEqual(row["arm_a"], "not_scorable")
        self.assertEqual(row["arm_b"], "not_scorable")
        self.assertEqual(row["class"], "not_scorable")

    def test_gate_pass_on_main_exit_0(self):
        self.assertEqual(self.res["gate"], "PASS")
        rc, out, err = cli(MAIN)
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("gate: PASS", out)
        self.assertEqual(out, forecast_gate.report(self.res))

    def test_cutoff_is_year_end_2024(self):
        self.assertEqual(self.res["cutoff"], CUTOFF)


class GateTests(unittest.TestCase):
    def test_wrong_declared_table_fails_gate_exit_1(self):
        root = raw()
        root["expected"]["own_edge"]["arm_b"] = "HIT"
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

    def test_gate_checks_arm_b(self):
        root = raw()
        root["expected"]["pre_t_support"]["arm_b"] = "MISS"
        res = result(root)
        self.assertEqual(res["gate"], "FAIL")
        # arm A still matches the declared row, so a gate that skipped arm B would PASS
        row = {r["case"]: r for r in res["rows"]}["pre_t_support"]
        self.assertEqual(row["arm_a"], "HIT")
        self.assertEqual(row["arm_b"], "HIT")
        self.assertEqual(row["expected"]["arm_a"], "HIT")
        self.assertEqual(row["expected"]["arm_b"], "MISS")

    def test_gate_checks_class(self):
        root = raw()
        root["expected"]["own_edge"]["class"] = "forecast"
        res = result(root)
        row = {r["case"]: r for r in res["rows"]}["own_edge"]
        self.assertEqual((row["arm_a"], row["arm_b"]), ("HIT", "MISS"))
        self.assertEqual((row["expected"]["arm_a"], row["expected"]["arm_b"]), ("HIT", "MISS"))
        self.assertEqual(res["gate"], "FAIL")

    def test_gate_compares_arm_a_too(self):
        root = raw()
        root["expected"]["own_edge"]["arm_a"] = "MISS"
        self.assertEqual(result(root)["gate"], "FAIL")


class DateAndClueTests(unittest.TestCase):
    def test_malformed_dates_are_deny(self):
        for value, code in (
            ("2026-2-30", "bad_date"),
            ("2026-02-30", "bad_date"),
            ("20261128", "bad_date"),
            (20261128, "bad_type"),
            (True, "bad_type"),
            (None, "bad_type"),
        ):
            root = raw()
            root["cutoff"] = value
            self.assertEqual(deny_code(root), code, value)
            root = raw()
            root["cases"][0]["events"][0]["date"] = value
            self.assertEqual(deny_code(root), code, value)

    def test_evidence_after_cutoff_is_hidden_from_b(self):
        root = raw()
        # only strong evidence sits after T; outcome also after T
        root["cases"] = [{
            "id": "own_edge",
            "events": [
                {"id": "ev_late", "name": "late_link", "date": "2025-01-15",
                 "role": "evidence", "weight": "strong"},
                {"id": "ev_out", "name": "first_trial", "date": "2025-04-01",
                 "role": "outcome", "weight": "strong"},
            ],
        }]
        root["expected"] = {
            "own_edge": {"arm_a": "HIT", "arm_b": "MISS", "class": "recall_not_forecast"},
        }
        res = result(root)
        self.assertEqual(res["gate"], "PASS")
        self.assertEqual(res["rows"][0]["arm_b"], "MISS")

    def test_evidence_one_day_after_cutoff_is_hidden_from_b(self):
        root = raw()
        root["cases"] = [{
            "id": "own_edge",
            "events": [
                {"id": "ev_next_day", "name": "next_day_link", "date": "2025-01-01",
                 "role": "evidence", "weight": "strong"},
                {"id": "ev_out", "name": "first_trial", "date": "2025-04-01",
                 "role": "outcome", "weight": "strong"},
            ],
        }]
        root["expected"] = {
            "own_edge": {"arm_a": "HIT", "arm_b": "MISS", "class": "recall_not_forecast"},
        }
        res = result(root)
        self.assertEqual(res["rows"][0]["arm_b"], "MISS")
        self.assertEqual(res["gate"], "PASS")

    def test_outcome_edge_cannot_reappear_as_pre_t_evidence(self):
        root = raw()
        out = root["cases"][0]["events"][1]
        root["cases"][0]["events"][0]["name"] = out["name"]
        root["cases"][0]["events"][0]["weight"] = "strong"
        self.assertEqual(deny_code(root), "duplicate_name")
        root = raw()
        root["cases"][1]["events"][1]["name"] = root["cases"][1]["events"][0]["name"]
        self.assertEqual(deny_code(root), "duplicate_name")
        root = raw()
        root["cases"][1]["events"][0]["name"] = root["cases"][0]["events"][0]["name"]
        self.assertIsNone(deny_code(root))

    def test_outcome_before_cutoff_is_not_scorable(self):
        root = raw()
        root["cases"] = [{
            "id": "own_edge",
            "events": [
                {"id": "ev_str", "name": "prior_link", "date": "2024-06-01",
                 "role": "evidence", "weight": "strong"},
                {"id": "ev_out", "name": "early_trial", "date": "2024-11-01",
                 "role": "outcome", "weight": "strong"},
            ],
        }]
        root["expected"] = {
            "own_edge": {"arm_a": "not_scorable", "arm_b": "not_scorable", "class": "not_scorable"},
        }
        res = result(root)
        self.assertEqual(res["gate"], "PASS")
        self.assertEqual(res["rows"][0]["class"], "not_scorable")


class InputDenyTests(unittest.TestCase):
    def test_ids_type_checked_before_lookup(self):
        for value in ([], {}, None, True, 1, 1.0):
            root = raw()
            root["cases"][0]["id"] = value
            self.assertEqual(deny_code(root), "bad_type", repr(value))

    def test_type_probes_list_dict_none_bool_float(self):
        for value in ({}, None, True, False):
            root = raw()
            root["on_expiry"] = value
            self.assertEqual(deny_code(root), "bad_type", repr(value))
            root = raw()
            root["cases"] = value
            self.assertEqual(deny_code(root), "bad_type", repr(value))
        root = raw()
        root["cases"] = []
        self.assertEqual(deny_code(root), "too_many")
        root = raw()
        root["cases"] = [["not", "an", "object"]]
        self.assertEqual(deny_code(root), "bad_type")

    def test_bool_is_not_accepted_as_int(self):
        root = raw()
        root["fixture_version"] = True
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["fixture_version"] = False
        self.assertEqual(deny_code(root), "bad_type")

    def test_self_reported_classes_are_denied(self):
        root = raw()
        root["cases"][0]["verdict"] = "ok"
        self.assertEqual(deny_code(root), "self_label")
        root = raw()
        root["cases"][0]["events"][0]["name"] = "known"
        self.assertEqual(deny_code(root), "self_label")
        root = raw()
        root["cases"][0]["events"][0]["name"] = "leak"
        self.assertEqual(deny_code(root), "self_label")

    def test_on_expiry_closed_set(self):
        for value in ON_EXPIRY_OK():
            root = raw()
            root["on_expiry"] = value
            self.assertIsNone(deny_code(root), value)
        for value in ("PASS", "ACCEPT", "OK", "YES", ""):
            root = raw()
            root["on_expiry"] = value
            self.assertEqual(deny_code(root), "bad_on_expiry", value)

    def test_on_expiry_pass_like_values_are_deny(self):
        for value in ("PASS", "ACCEPT", "OK", ""):
            root = raw()
            root["on_expiry"] = value
            self.assertEqual(deny_code(root), "bad_on_expiry", value)

    def test_bad_fixtures_deny_exit_2_one_line(self):
        names = sorted(f[:-5] for f in os.listdir(BAD) if f.endswith(".json"))
        self.assertEqual(names, sorted(BAD_CODES))
        for name in names:
            path = os.path.join(BAD, name + ".json")
            try:
                forecast_gate.load(path)
                try:
                    forecast_gate.run(forecast_gate.load(path))
                    code = None
                except forecast_gate.Deny as e:
                    code = e.code
            except forecast_gate.Deny as e:
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

    def test_utf8_decode_failure(self):
        path = None
        try:
            fd, path = tempfile.mkstemp(suffix=".json")
            os.write(fd, b"{\xff\xfe not utf-8")
            os.close(fd)
            with self.assertRaises(forecast_gate.Deny) as ctx:
                forecast_gate.load(path)
            self.assertEqual(ctx.exception.code, "bad_utf")
            rc, out, err = cli(path)
            self.assertEqual((rc, out), (2, ""))
            self.assertTrue(err.startswith("DENY bad_utf: "))
            self.assertRegex(err, DENY_LINE)
            self.assertEqual(err.count("\n"), 1)
        finally:
            if path:
                os.remove(path)

    def test_deep_nesting_is_deny_not_traceback(self):
        with open(MAIN, encoding="utf-8") as fh:
            text = fh.read()
        deep = "[" * 3000 + "]" * 3000
        path = None
        try:
            fd, path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text.replace('"cutoff": "2024-12-31"', '"cutoff": ' + deep, 1))
            self.assertLess(os.path.getsize(path), forecast_gate.MAX_BYTES)
            proc = subprocess.run(
                [sys.executable, "-B", os.path.join(HERE, "forecast_gate.py"), path],
                capture_output=True, text=True, timeout=TIMEOUT["seconds"],
            )
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
            injected = text.replace('"cutoff": "2024-12-31"', '"cutoff": ' + value, 1)
            try:
                forecast_gate.loads(injected)
                got = None
            except forecast_gate.Deny as e:
                got = e.code
            except RecursionError:
                got = "RecursionError"
            self.assertEqual(got, want, value[:12])


def ON_EXPIRY_OK():
    return ("DENY", "SAFE_FALLBACK", "ESCALATE", "HOLD")


class MutantHarnessTests(unittest.TestCase):
    def test_forced_real_timeout_is_not_killed(self):
        rc, stdout, timed_out = mutants.run_source("import time\ntime.sleep(30)\n", timeout=2)
        verdict = mutants.classify(rc, stdout, timed_out)
        self.assertEqual((rc, timed_out, verdict), (None, True, "TIMEOUT"))
        self.assertFalse(mutants.is_killed(verdict))

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
        self.assertEqual(forecast_gate.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})

    def test_classify_other_shapes(self):
        self.assertEqual(mutants.classify(0, '{"failures": 0, "errors": 0}', False), "SURVIVED")
        self.assertEqual(mutants.classify(1, '{"failures": 2, "errors": 0}', False), "KILLED-behaviour")
        self.assertEqual(mutants.classify(1, '{"failures": 0, "errors": 2}', False), "CRASH")
        self.assertEqual(mutants.classify(1, "not-json", False), "CRASH")


class SubprocessTests(unittest.TestCase):
    def test_cli_twice_identical(self):
        cmd = [sys.executable, "-B", os.path.join(HERE, "forecast_gate.py"), MAIN]
        a = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT["seconds"])
        b = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT["seconds"])
        self.assertEqual((a.returncode, a.stderr), (0, ""))
        self.assertEqual(a.stdout, b.stdout)
        self.assertIn("gate: PASS", a.stdout)

    def test_demo_twice_identical(self):
        cmd = [sys.executable, "-B", os.path.join(HERE, "demo.py")]
        a = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT["seconds"])
        b = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT["seconds"])
        self.assertEqual((a.returncode, a.stderr), (0, ""))
        self.assertEqual(a.stdout, b.stdout)


if __name__ == "__main__":
    unittest.main()
