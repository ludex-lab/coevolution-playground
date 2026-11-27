"""Unit tests for the Nyout rule engine. No test reads nyout.py as source text."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import mutants
import nyout

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "fixtures", "main.json")
BAD_DIR = os.path.join(HERE, "fixtures", "bad")
DENY_LINE = re.compile(r"DENY [a-z_]+: \S[^\n]*\n\Z")
TIMEOUT = {"seconds": 60, "on_expiry": "DENY"}

BAD_CODES = {
    "unknown_field": "unknown_field",
    "seed_forbidden": "seed_forbidden",
    "random_forbidden": "seed_forbidden",
    "bad_horse_count": "bad_horse_count",
    "bad_horse_count_zero": "bad_horse_count",
    "unknown_horse": "unknown_horse",
    "bad_throw_backdo": "bad_throw",
    "bad_throw_upper": "bad_throw",
    "bad_throw_kdi": "bad_throw",
    "bad_throw_int": "bad_throw",
    "bad_throw_bool": "bad_throw",
    "bad_on_expiry_pass": "bad_on_expiry",
    "bad_on_expiry_ignore": "bad_on_expiry",
    "bad_type_bool_count": "bad_type",
    "bad_version": "bad_version",
    "missing_field": "missing_field",
    "not_json": "not_json",
    "duplicate_key": "duplicate_key",
    "too_deep": "too_deep",
    "too_large": "too_large",
    "bad_board_missing": "bad_board",
    "bad_board_extra": "bad_board",
    "bad_board_dup_station": "bad_board",
    "bad_board_bad_edge": "bad_board",
    "wrong_side": "wrong_side",
}


def raw():
    with open(MAIN, encoding="utf-8") as fh:
        return json.loads(fh.read())


def deny_code(root):
    try:
        nyout.validate(root)
        return None
    except nyout.Deny as e:
        return e.code


def row_by_id(res, sid):
    for row in res["rows"]:
        if row["id"] == sid:
            return row
    raise AssertionError("missing session %s" % sid)


def first_apply_index(transcript):
    for i, ev in enumerate(transcript):
        if ev["kind"] == "apply":
            return i
    return None


def throw_index(transcript, name):
    for i, ev in enumerate(transcript):
        if ev["kind"] == "throw" and ev["throw"] == name:
            return i
    return None


class BoardGraphTests(unittest.TestCase):
    def test_twenty_nine_named_stations(self):
        self.assertEqual(len(nyout.STATIONS), 29)
        self.assertEqual(len(set(nyout.STATIONS)), 29)
        self.assertEqual(nyout.STATIONS[4], "r5")
        self.assertEqual(nyout.STATIONS[9], "r10")
        self.assertEqual(nyout.STATIONS[14], "r15")
        self.assertEqual(nyout.STATIONS[19], "r20")
        self.assertEqual(nyout.ALIASES, {"A": "r20", "B": "r5", "C": "r10", "D": "r15"})
        for name in ("b1", "b2", "c1", "c2", "d1", "d2", "a1", "a2", "E"):
            self.assertIn(name, nyout.STATIONS)

    def test_d1_d2_unreachable_under_culin_routes(self):
        found = nyout.reachable_stations()
        self.assertEqual(len(found), 27)
        self.assertNotIn("d1", found)
        self.assertNotIn("d2", found)
        for name in nyout.STATIONS:
            if name not in ("d1", "d2"):
                self.assertIn(name, found, name)

    def test_entry_is_step_one(self):
        land, ev, ill = nyout.apply_steps(nyout.START, 1, True, "A")
        self.assertEqual((land, ill), ("r1", False))
        self.assertIn("enter", ev)
        land, ev, ill = nyout.apply_steps(nyout.START, 5, True, "A")
        self.assertEqual(land, "r5")

    def test_rim_route_twenty_one_steps_to_go_out(self):
        land, ev, _ = nyout.apply_steps(nyout.START, 20, False, "A")
        self.assertEqual(land, "r20")
        self.assertIn("tied", ev)
        land, ev, _ = nyout.apply_steps(nyout.START, 21, False, "A")
        self.assertEqual(land, "out")
        self.assertIn("out", ev)

    def test_via_b_twelve_steps_to_go_out(self):
        mid, _, _ = nyout.apply_steps(nyout.START, 5, False, "A")
        self.assertEqual(mid, "r5")
        land, ev, _ = nyout.apply_steps(mid, 6, False, "A")
        self.assertEqual(land, "r20")
        self.assertIn("tied", ev)
        land, ev, _ = nyout.apply_steps(mid, 7, False, "A")
        self.assertEqual(land, "out")

    def test_via_c_seventeen_steps_to_go_out(self):
        mid, _, _ = nyout.apply_steps(nyout.START, 10, False, "A")
        self.assertEqual(mid, "r10")
        land, ev, _ = nyout.apply_steps(mid, 6, True, "A")
        self.assertEqual(land, "r20")
        self.assertIn("tied", ev)
        land, ev, _ = nyout.apply_steps(mid, 7, True, "A")
        self.assertEqual(land, "out")

    def test_b_and_c_continue_through_centre_to_a(self):
        for start, take_c, path in (
            ("r5", False, ("b1", "b2", "E", "a1", "a2", "r20")),
            ("r10", True, ("c1", "c2", "E", "a1", "a2", "r20")),
        ):
            cur = start
            seen = []
            for _ in range(6):
                cur, ev, _ = nyout.apply_steps(cur, 1, take_c, "A")
                seen.append(cur)
            self.assertEqual(tuple(seen), path)


class EngineRuleTests(unittest.TestCase):
    def test_main_gate_pass(self):
        res = nyout.run(nyout.load(MAIN))
        self.assertEqual(res["gate"], "PASS")
        self.assertIn("gate: PASS\n", res["report"])

    def test_opening_and_overrun_sessions(self):
        res = nyout.run(nyout.load(MAIN))
        mo = row_by_id(res, "opening_mo_to_B")
        self.assertEqual(mo["pos_a"]["p1"], "r5")
        self.assertEqual(mo["arm_a"], "PASS")
        to = row_by_id(res, "opening_to_to_r1")
        self.assertEqual(to["pos_a"]["p1"], "r1")
        oc = row_by_id(res, "overrun_C_no_shortcut")
        self.assertEqual(oc["pos_a"]["p1"], "r11")
        self.assertEqual(oc["arm_a"], "PASS")
        self.assertEqual(oc["arm_b"], "FAIL")
        self.assertEqual(oc["pos_b"]["p1"], "c1")
        ob = row_by_id(res, "overrun_B_no_shortcut")
        self.assertEqual(ob["pos_a"]["p1"], "r6")
        self.assertEqual(ob["arm_b"], "FAIL")
        self.assertEqual(ob["pos_b"]["p1"], "b1")

    def test_passing_b_or_c_does_not_enter_a_radius(self):
        # r3 + 3 steps passes B and lands on r6; r8 + 3 steps passes C and lands on r11.
        land, ev, ill = nyout.apply_steps("r3", 3, True, "A")
        self.assertEqual((land, ill), ("r6", False))
        self.assertNotIn("shortcut", ev)
        land, ev, ill = nyout.apply_steps("r8", 3, True, "A")
        self.assertEqual((land, ill), ("r11", False))
        self.assertNotIn("shortcut", ev)

    def test_mo_then_kel_lands_on_centre_not_r8(self):
        res = nyout.run(nyout.load(MAIN))
        row = row_by_id(res, "mo_then_kel_sequential")
        self.assertEqual(row["pos_a"]["p1"], "E")
        self.assertNotEqual(row["pos_a"]["p1"], "r8")

    def test_split_buffered_throws_across_two_horses(self):
        res = nyout.run(nyout.load(MAIN))
        row = row_by_id(res, "split_buffered_throws")
        self.assertEqual(row["pos_a"]["p1"], "r5")
        self.assertEqual(row["pos_a"]["p2"], "r3")

    def test_nyout_extra_throw_is_collected_before_any_move(self):
        res = nyout.run(nyout.load(MAIN))
        row = row_by_id(res, "nyout_extra_throw_before_move")
        tr = row["transcript_a"]
        i_to = throw_index(tr, "to")
        i_apply = first_apply_index(tr)
        self.assertIsNotNone(i_to)
        self.assertIsNotNone(i_apply)
        self.assertLess(i_to, i_apply)
        self.assertEqual(row["pos_a"]["p1"], "r5")

    def test_chained_nyout_mo_all_throws_before_first_apply(self):
        res = nyout.run(nyout.load(MAIN))
        row = row_by_id(res, "chained_nyout_mo")
        tr = row["transcript_a"]
        names = [ev["throw"] for ev in tr if ev["kind"] == "throw"]
        self.assertEqual(names, ["nyout", "nyout", "to"])
        last_throw = max(i for i, ev in enumerate(tr) if ev["kind"] == "throw")
        self.assertLess(last_throw, first_apply_index(tr))
        self.assertEqual(row["pos_a"]["p1"], "r9")

    def test_capture_sends_opponent_home_and_grants_throw(self):
        res = nyout.run(nyout.load(MAIN))
        row = row_by_id(res, "capture_sends_home")
        self.assertEqual(row["pos_a"]["q1"], "start")
        self.assertEqual(row["pos_a"]["p1"], "r3")
        kinds = [(ev["kind"], ev.get("cause"), ev.get("events")) for ev in row["transcript_a"]]
        self.assertTrue(any(ev["kind"] == "apply" and "capture" in ev["events"]
                            for ev in row["transcript_a"]))
        self.assertTrue(any(ev["kind"] == "extra_throw" and ev.get("cause") == "capture"
                            for ev in row["transcript_a"]))

    def test_capture_with_buffered_throw_and_on_nyout(self):
        res = nyout.run(nyout.load(MAIN))
        buf = row_by_id(res, "capture_with_buffered_throw")
        self.assertEqual(buf["pos_a"]["q1"], "start")
        self.assertEqual(buf["pos_a"]["p1"], "b2")
        ny = row_by_id(res, "capture_on_nyout")
        self.assertEqual(ny["pos_a"]["q1"], "start")
        self.assertTrue(any(ev["kind"] == "apply" and ev["throw"] == "nyout"
                            and "capture" in ev["events"]
                            for ev in ny["transcript_a"]))

    def test_b_mandatory_and_c_selectable(self):
        res = nyout.run(nyout.load(MAIN))
        self.assertEqual(row_by_id(res, "b_radius_is_mandatory")["pos_a"]["p1"], "b1")
        self.assertEqual(row_by_id(res, "c_shortcut_taken")["pos_a"]["p1"], "c1")
        self.assertEqual(row_by_id(res, "c_shortcut_declined")["pos_a"]["p1"], "r11")

    def test_exact_A_stays_tied_on_all_three_routes(self):
        # Rim, via B, and via C: landing exactly on A stays on the board.
        land, ev, _ = nyout.apply_steps("r19", 1, False, "A")
        self.assertEqual(land, "r20")
        self.assertIn("tied", ev)
        land, ev, _ = nyout.apply_steps("a2", 1, False, "A")
        self.assertEqual(land, "r20")
        self.assertIn("tied", ev)
        land, ev, _ = nyout.apply_steps("a2", 1, True, "A")
        self.assertEqual(land, "r20")
        self.assertIn("tied", ev)
        land, ev, _ = nyout.apply_steps("r20", 1, False, "A")
        self.assertEqual(land, "out")
        self.assertIn("out", ev)
        land, ev, _ = nyout.apply_steps("r18", 3, False, "A")
        self.assertEqual(land, "out")

    def test_exit_planted_sessions_and_tied_event(self):
        res = nyout.run(nyout.load(MAIN))
        for sid in ("exit_needs_one_more", "exit_via_b", "exit_via_c"):
            row = row_by_id(res, sid)
            self.assertEqual(row["pos_a"]["p1"], "out", sid)
            events = [e for ev in row["transcript_a"] if ev["kind"] == "apply" for e in ev["events"]]
            self.assertIn("tied", events, sid)
            self.assertIn("out", events, sid)

    def test_stack_join_move_count_and_captured_stack(self):
        res = nyout.run(nyout.load(MAIN))
        join = row_by_id(res, "stack_join_and_move")
        self.assertEqual(join["pos_a"]["p1"], "r2")
        self.assertEqual(join["pos_a"]["p2"], "r2")
        self.assertTrue(any(ev["kind"] == "apply" and "stack" in ev["events"]
                            for ev in join["transcript_a"]))
        win = row_by_id(res, "stack_counts_at_win")
        self.assertEqual(win["winner"], "p")
        self.assertEqual(win["out_p"], 4)
        self.assertEqual(win["pos_a"]["p1"], "out")
        self.assertEqual(win["pos_a"]["p4"], "out")
        cap = row_by_id(res, "captured_stack_returns_whole")
        self.assertEqual(cap["pos_a"]["p1"], "start")
        self.assertEqual(cap["pos_a"]["p2"], "start")
        self.assertEqual(cap["pos_a"]["q1"], "r3")

    def test_one_buffer_is_spent_by_one_side(self):
        horses = nyout._horses_for(4)
        def play(throws, movers):
            session = {"id": "s", "throws": throws, "moves": [{"horse": h} for h in movers],
                       "take_c_shortcut": True, "join_stack": True, "overrun_mark": None}
            try:
                return nyout.play_session(session, "A", horses, 4)["positions"]
            except nyout.Deny as e:
                return e.code
        self.assertEqual(play(["nyout", "to"], ["p1", "q1"]), "wrong_side")
        self.assertEqual(play(["to", "to", "kai"], ["q1", "p1", "q1"]), "wrong_side")
        pos = play(["mo", "kel"], ["p1", "p2"])
        self.assertEqual((pos["p1"], pos["p2"]), ("r5", "r3"))
        pos = play(["to", "to"], ["p1", "q1"])
        self.assertEqual(pos["q1"], "r1")

    def test_gate_compares_arm_b_and_pos_a(self):
        root = raw()
        root["expected"]["overrun_C_no_shortcut"]["arm_b"] = "PASS"
        self.assertEqual(nyout.run(nyout.validate(root))["gate"], "FAIL")
        root = raw()
        root["expected"]["opening_mo_to_B"]["pos_a"]["p1"] = "r6"
        self.assertEqual(nyout.run(nyout.validate(root))["gate"], "FAIL")

    def test_throws_exhausted_ends_session(self):
        res = nyout.run(nyout.load(MAIN))
        row = row_by_id(res, "throws_exhausted_after_mo")
        self.assertEqual(row["end"], "throws_exhausted")
        self.assertTrue(any(ev["kind"] == "throws_exhausted" for ev in row["transcript_a"]))
        self.assertEqual(row["pos_a"]["p1"], "r5")


class DenyTests(unittest.TestCase):
    def test_on_expiry_closed_set(self):
        for value in ("DENY", "SAFE_FALLBACK", "ESCALATE", "HOLD"):
            root = raw()
            root["on_expiry"] = value
            self.assertIsNone(deny_code(root), value)
        for value in ("PASS", "IGNORE", "YES", "deny", ""):
            root = raw()
            root["on_expiry"] = value
            self.assertEqual(deny_code(root), "bad_on_expiry", value)

    def test_timeout_constant(self):
        self.assertEqual(nyout.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})
        self.assertEqual(mutants.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})
        self.assertEqual(set(nyout.ON_EXPIRY_OK), {"DENY", "SAFE_FALLBACK", "ESCALATE", "HOLD"})

    def test_bool_is_not_an_integer(self):
        root = raw()
        root["horse_count"] = True
        self.assertEqual(deny_code(root), "bad_type")
        root = raw()
        root["fixture_version"] = False
        self.assertEqual(deny_code(root), "bad_type")

    def test_horse_count_must_be_one_or_four(self):
        for n in (0, 2, 3, 5, -1):
            root = raw()
            root["horse_count"] = n
            self.assertEqual(deny_code(root), "bad_horse_count", n)

    def test_seed_and_random_forbidden_at_any_depth(self):
        root = raw()
        root["seed"] = 1
        self.assertEqual(deny_code(root), "seed_forbidden")
        root = raw()
        root["sessions"][0]["random"] = 0
        self.assertEqual(deny_code(root), "seed_forbidden")

    def test_unknown_field_and_unknown_horse_and_bad_throw(self):
        root = raw()
        root["extra"] = 1
        self.assertEqual(deny_code(root), "unknown_field")
        root = raw()
        root["sessions"][0]["moves"][0]["horse"] = "z1"
        self.assertEqual(deny_code(root), "unknown_horse")
        for bad in ("backdo", "TO", "kdi", "Mo", "to "):
            root = raw()
            root["sessions"][0]["throws"][0] = bad
            self.assertEqual(deny_code(root), "bad_throw", bad)
        root = raw()
        root["sessions"][0]["throws"][0] = 4
        self.assertEqual(deny_code(root), "bad_throw")
        root = raw()
        root["sessions"][0]["throws"][0] = None
        self.assertEqual(deny_code(root), "bad_throw")

    def test_ids_are_type_checked_before_lookup(self):
        for value in (1, True, None, [], {}):
            root = raw()
            root["sessions"][0]["id"] = value
            self.assertEqual(deny_code(root), "bad_type", repr(value))
            root = raw()
            root["sessions"][0]["moves"][0]["horse"] = value
            self.assertEqual(deny_code(root), "bad_type", repr(value))

    def test_cli_bad_fixtures(self):
        cmd = [sys.executable, "-B", os.path.join(HERE, "nyout.py")]
        names = sorted(os.listdir(BAD_DIR))
        self.assertGreaterEqual(len(names), 20)
        for name in names:
            path = os.path.join(BAD_DIR, name)
            proc = subprocess.run(cmd + [path], capture_output=True, text=True,
                                  timeout=TIMEOUT["seconds"])
            self.assertEqual((proc.returncode, proc.stdout), (2, ""), name)
            self.assertRegex(proc.stderr, DENY_LINE, name)
            key = os.path.splitext(name)[0]
            self.assertTrue(proc.stderr.startswith("DENY %s: " % BAD_CODES[key]), name)

    def test_cli_usage_and_unreadable_and_bad_utf(self):
        cmd = [sys.executable, "-B", os.path.join(HERE, "nyout.py")]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT["seconds"])
        self.assertEqual((proc.returncode, proc.stdout), (2, ""))
        self.assertTrue(proc.stderr.startswith("DENY usage: "))
        self.assertRegex(proc.stderr, DENY_LINE)
        proc = subprocess.run(cmd + [os.path.join(HERE, "fixtures", "no_such.json")],
                              capture_output=True, text=True, timeout=TIMEOUT["seconds"])
        self.assertEqual((proc.returncode, proc.stdout), (2, ""))
        self.assertTrue(proc.stderr.startswith("DENY unreadable: "))
        self.assertRegex(proc.stderr, DENY_LINE)
        handle = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        try:
            handle.write(b"\xff\xfe not utf8")
            handle.close()
            proc = subprocess.run(cmd + [handle.name], capture_output=True, text=True,
                                  timeout=TIMEOUT["seconds"])
            self.assertEqual((proc.returncode, proc.stdout), (2, ""))
            self.assertTrue(proc.stderr.startswith("DENY bad_utf: "))
            self.assertRegex(proc.stderr, DENY_LINE)
        finally:
            os.remove(handle.name)

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
            blob = text.replace('"horse_count": 4', '"horse_count": ' + value, 1)
            try:
                nyout.load_text(blob)
                got = None
            except nyout.Deny as e:
                got = e.code
            except RecursionError:
                got = "RecursionError"
            self.assertEqual(got, want, value[:12])

    def test_duplicate_key_in_process(self):
        text = '{"fixture_version": 1, "fixture_version": 1}'
        try:
            nyout.load_text(text)
            code = None
        except nyout.Deny as e:
            code = e.code
        self.assertEqual(code, "duplicate_key")

    def test_too_large_in_process(self):
        blob = "{" + " " * 32769 + "}"
        try:
            nyout.load_text(blob)
            code = None
        except nyout.Deny as e:
            code = e.code
        self.assertEqual(code, "too_large")


class MutantHarnessTests(unittest.TestCase):
    def test_crash_and_timeout_are_not_kills(self):
        counts = mutants.tally(["KILLED-behaviour", "CRASH", "TIMEOUT", "SURVIVED"])
        self.assertEqual(counts["KILLED-behaviour"], 1)
        self.assertEqual(counts["CRASH"], 1)
        self.assertEqual(counts["TIMEOUT"], 1)
        self.assertEqual(counts["SURVIVED"], 1)
        self.assertFalse(mutants.is_killed("TIMEOUT"))
        self.assertFalse(mutants.is_killed("CRASH"))
        self.assertFalse(mutants.is_killed("SURVIVED"))
        self.assertTrue(mutants.is_killed("KILLED-behaviour"))
        self.assertEqual(mutants.classify(None, "", True), "TIMEOUT")
        self.assertEqual(mutants.classify(mutants.LOAD_FAILED, "", False), "CRASH")
        self.assertEqual(mutants.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})
        self.assertEqual(TIMEOUT["on_expiry"], "DENY")

    def test_demo_is_deterministic(self):
        cmd = [sys.executable, "-B", os.path.join(HERE, "demo.py")]
        a = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT["seconds"])
        b = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT["seconds"])
        self.assertEqual(a.returncode, 0)
        self.assertEqual(b.returncode, 0)
        self.assertEqual(a.stdout, b.stdout)
        self.assertTrue(a.stdout.endswith("gate: PASS\n"))


if __name__ == "__main__":
    unittest.main()
