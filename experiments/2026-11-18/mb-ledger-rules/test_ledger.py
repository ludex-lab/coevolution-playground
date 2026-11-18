"""Tests for ledger (stdlib unittest). Run: python3 -B -m unittest -v test_ledger"""

import ast
import copy
import glob
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ledger as L  # noqa: E402

MAIN = os.path.join(HERE, "fixtures", "main.json")
with open(MAIN, encoding="utf-8") as _h:
    RAW = json.load(_h)


def variant(edit):
    obj = copy.deepcopy(RAW)
    edit(obj)
    return obj


def code_of(obj):
    try:
        L.validate(obj)
    except L.Deny as exc:
        return exc.code
    return None


def probe(fx, pid):
    return next(p for p in fx["probes"] if p["id"] == pid)


class CurrentValueRules(unittest.TestCase):
    def setUp(self):
        self.fx = L.load(MAIN)
        self.rows = {r["probe"]["id"]: r for r in L.run(self.fx)}

    def test_in_period_fact_beats_stale_fact(self):
        b = self.rows["p1"]["ledger"]
        self.assertEqual((b["status"], [f["value"] for f in b["facts"]]), ("current", ["3.11"]))

    def test_higher_trust_beats_lower_trust_in_period(self):
        # f2 (high) and f3 (low) both hold on day 7; the high-trust value is chosen
        self.assertEqual(self.rows["p1"]["ledger"]["facts"][0]["trust"], "high")
        self.assertNotIn("3.9", L.serialize(self.rows["p1"]["ledger"]))

    def test_in_period_low_trust_beats_stale_high_trust(self):
        b = self.rows["p2"]["ledger"]
        self.assertEqual([f["value"] for f in b["facts"]], ["us-east"])
        self.assertNotIn("eu-west", L.serialize(b))

    def test_stale_fact_still_current_before_supersession(self):
        led = L.Ledger()
        led.ingest(self.fx["turns"][0], [self.fx["facts"][0]])
        self.assertEqual(led.current("nightly_job", "python_version", 3)[1][0]["value"], "3.8")
        self.assertEqual(led.current("nightly_job", "python_version", 5), ("none", []))

    def test_future_fact_is_not_current(self):
        led = L.Ledger()
        led.ingest(self.fx["turns"][4], [self.fx["facts"][1]])
        self.assertEqual(led.current("nightly_job", "python_version", 4)[0], "none")

    def test_period_bounds_are_inclusive(self):
        f = {"start": 2, "end": 4}
        self.assertEqual([L.in_period(f, d) for d in (1, 2, 4, 5)], [False, True, True, False])
        self.assertTrue(L.in_period({"start": 2, "end": None}, 9999))
        self.assertEqual(L.stale_values(self.fx, probe(self.fx, "p1")), ["3.8"])
        self.assertEqual(L.stale_values(self.fx, dict(probe(self.fx, "p1"), day=4)), [])

    def current_after(self, edit, day=7, subject="nightly_job", attribute="python_version"):
        fx = L.validate(variant(edit))
        led = L.Ledger()
        for t in fx["turns"]:
            led.ingest(t, [f for f in fx["facts"] if f["turn"] == t["id"]])
        return led.current(subject, attribute, day)

    def test_rank_order_is_trust_then_start_then_learned(self):
        # high trust beats a later-starting low-trust fact
        status, facts = self.current_after(lambda o: o["facts"][2].update(start=6))
        self.assertEqual([f["id"] for f in facts], ["f2"])
        # medium beats low
        status, facts = self.current_after(lambda o: (o["facts"][1].update(trust="medium"), o["facts"][2].update(trust="low")))
        self.assertEqual([f["id"] for f in facts], ["f2"])
        # same trust and start: the later-learned turn wins (t6 is day 6, t5 is day 5)
        status, facts = self.current_after(lambda o: o["facts"][2].update(source="ci_log", trust="high"))
        self.assertEqual([f["id"] for f in facts], ["f3"])

    def test_same_value_tie_is_one_current_fact(self):
        def edit(o):
            o["turns"][5]["text"] += " It says 3.11."
            o["facts"][2].update(source="ci_log", trust="high", value="3.11", turn="t6")
            o["turns"][5]["day"] = 5
        status, facts = self.current_after(edit)
        self.assertEqual((status, len(facts)), ("current", 1))

    def test_subject_and_attribute_must_both_match(self):
        self.assertEqual(self.current_after(lambda o: None, subject="staging_db", attribute="python_version")[0], "none")
        self.assertEqual(self.current_after(lambda o: None, subject="nightly_job", attribute="region")[0], "none")

    def test_fact_and_turn_are_visible_on_their_own_day(self):
        self.assertEqual(self.current_after(lambda o: None, day=5)[1][0]["value"], "3.11")
        fx = L.validate(variant(lambda o: o["probes"][0].update(day=5)))
        row = next(r for r in L.run(fx) if r["probe"]["id"] == "p1")
        self.assertEqual(row["ledger"]["facts"][0]["value"], "3.11")

    def test_equal_trust_prefers_later_start(self):
        fx = L.validate(variant(lambda o: o["facts"][2].update(source="ci_log", trust="high", start=6)))
        led = L.Ledger()
        for t in fx["turns"]:
            led.ingest(t, [f for f in fx["facts"] if f["turn"] == t["id"]])
        self.assertEqual(led.current("nightly_job", "python_version", 7)[1][0]["value"], "3.9")

    def test_tie_with_different_values_is_a_conflict(self):
        def edit(o):
            o["facts"][2].update(source="ci_log", trust="high", start=5)
            o["turns"][5].update(day=5)
        fx = L.validate(variant(edit))
        led = L.Ledger()
        for t in fx["turns"]:
            led.ingest(t, [f for f in fx["facts"] if f["turn"] == t["id"]])
        status, facts = led.current("nightly_job", "python_version", 7)
        self.assertEqual((status, [f["id"] for f in facts]), ("conflict", ["f2", "f3"]))

    def test_fallback_only_when_no_fact_and_only_up_to_the_probe_day(self):
        led = L.Ledger()
        for t in self.fx["turns"]:
            led.ingest(t, [f for f in self.fx["facts"] if f["turn"] == t["id"]])
        covered = led.bundle(dict(probe(self.fx, "p1"), fallback=True))
        self.assertEqual((covered["status"], covered["turns"]), ("current", []))
        early = led.bundle(dict(probe(self.fx, "p5"), day=3, terms=["staging"]))
        self.assertEqual([t["id"] for t in early["turns"]], ["t2"])
        self.assertEqual([t["id"] for t in L.replay_bundle(self.fx, dict(probe(self.fx, "p5"), day=3, terms=["staging"]))["turns"]], ["t2"])

    def test_term_match_and_leak_check_ignore_case(self):
        self.assertTrue(L.matches_terms("Python 3", ["PYTHON"]))
        self.assertFalse(L.matches_terms("Python 3", ["rust", "go"]))
        self.assertEqual(L.leaks({"x": "PLUM"}, ["plum", "fig"]), ["plum"])

    def test_probe_on_the_deletion_day_sees_the_deletion(self):
        fx = L.validate(variant(lambda o: o["probes"][3].update(day=8)))
        row = next(r for r in L.run(fx) if r["probe"]["id"] == "p4")
        self.assertEqual(row["deleted"], ["plum-7731-anchor"])

    def test_no_fact_and_no_fallback_gives_empty_bundle(self):
        b = self.rows["p8"]["ledger"]
        self.assertEqual((b["status"], b["facts"], b["turns"]), ("fallback", [], []))
        p = dict(probe(self.fx, "p8"), fallback=False)
        led = L.Ledger()
        self.assertEqual(led.bundle(p)["status"], "none")


class Deletion(unittest.TestCase):
    def setUp(self):
        self.fx = L.load(MAIN)
        self.rows = L.run(self.fx)
        self.secret = "plum-7731-anchor"

    def test_value_is_present_before_the_deletion(self):
        row = next(r for r in self.rows if r["probe"]["id"] == "p3")
        self.assertEqual(row["deleted"], [])
        self.assertEqual(L.leaks(row["ledger"], [self.secret]), [self.secret])

    def test_deleted_value_in_no_later_ledger_bundle(self):
        later = [r for r in self.rows if r["deleted"]]
        self.assertEqual(len(later), 5)
        for row in later:
            self.assertEqual(row["deleted"], [self.secret])
            self.assertEqual(L.leaks(row["ledger"], row["deleted"]), [])

    def test_raw_turn_fallback_is_scrubbed(self):
        row = next(r for r in self.rows if r["probe"]["id"] == "p4")
        self.assertEqual([t["id"] for t in row["ledger"]["turns"]], ["t2", "t4"])
        self.assertIn(L.REMOVED, L.serialize(row["ledger"]))
        self.assertNotIn(self.secret, L.serialize(row["ledger"]))

    def test_scrub_is_case_insensitive(self):
        fx = L.validate(variant(lambda o: o["turns"][3].update(text=o["turns"][3]["text"].replace(
            "plum-7731-anchor", "PLUM-7731-Anchor"))))
        for row in L.run(fx):
            self.assertEqual(L.leaks(row["ledger"], row["deleted"]), [])

    def test_tombstone_holds_description_only(self):
        led = L.Ledger()
        for t in self.fx["turns"][:4]:
            led.ingest(t, [f for f in self.fx["facts"] if f["turn"] == t["id"]])
        led.delete(self.fx["deletions"][0])
        self.assertEqual(sorted(led.tombstones[0]), ["attribute", "id", "source", "subject"])
        self.assertNotIn(self.secret, json.dumps([led.tombstones, led.facts, led.turns]))

    def test_deletion_text_never_restates_the_value(self):
        for d in self.fx["deletions"]:
            self.assertNotIn(self.secret, d["text"].lower())
        bad = variant(lambda o: o["deletions"][0].update(text="Forget plum-7731-anchor please."))
        with self.assertRaises(L.Deny) as ctx:
            L.run(L.validate(bad))
        self.assertEqual(ctx.exception.code, "restates_value")

    def test_deletion_matches_by_period_overlap_only(self):
        def edit(o):
            o["deletions"][0].update(subject="nightly_job", attribute="python_version", source="ci_log",
                                     start=7, end=7, text="Forget the nightly python version from the CI log.")
        rows = {r["probe"]["id"]: r for r in L.run(L.validate(variant(edit)))}
        self.assertEqual(rows["p6"]["deleted"], ["3.11"])
        self.assertEqual(rows["p6"]["ledger"]["facts"][0]["id"], "f3")   # f1 (ended day 4) was not touched
        self.assertNotIn("3.11", L.serialize(rows["p6"]["ledger"]))

    def test_restated_value_check_ignores_case(self):
        bad = variant(lambda o: o["deletions"][0].update(text="Forget PLUM-7731-ANCHOR please."))
        with self.assertRaises(L.Deny) as ctx:
            L.run(L.validate(bad))
        self.assertEqual(ctx.exception.code, "restates_value")

    def test_zero_match_deletion_is_deny(self):
        bad = variant(lambda o: o["deletions"][0].update(source="chat_hearsay"))
        with self.assertRaises(L.Deny) as ctx:
            L.run(L.validate(bad))
        self.assertEqual(ctx.exception.code, "no_match")

    def test_period_outside_the_fact_is_zero_match(self):
        bad = variant(lambda o: o["deletions"][0].update(start=0, end=1))
        with self.assertRaises(L.Deny) as ctx:
            L.run(L.validate(bad))
        self.assertEqual(ctx.exception.code, "no_match")

    def test_ambiguous_deletion_is_deny_and_deletes_nothing(self):
        with open(os.path.join(HERE, "fixtures", "bad_deletion_ambiguous.json"), encoding="utf-8") as h:
            fx = L.validate(json.load(h))
        led = L.Ledger()
        for t in fx["turns"][:4]:
            led.ingest(t, [f for f in fx["facts"] if f["turn"] == t["id"]])
        before = json.dumps([led.facts, led.turns], sort_keys=True)
        with self.assertRaises(L.Deny) as ctx:
            led.delete(fx["deletions"][0])
        self.assertEqual(ctx.exception.code, "ambiguous")
        self.assertEqual(json.dumps([led.facts, led.turns], sort_keys=True), before)
        self.assertEqual(led.tombstones, [])

    def test_value_held_by_another_fact_is_deny(self):
        def edit(o):
            o["turns"][6]["text"] += " Also plum-7731-anchor."
            o["facts"].append(dict(o["facts"][4], id="f9", subject="other", value="plum-7731-anchor"))
        with self.assertRaises(L.Deny) as ctx:
            L.run(L.validate(variant(edit)))
        self.assertEqual(ctx.exception.code, "value_shared")

    def test_deletion_before_the_fact_is_learned_is_zero_match(self):
        bad = variant(lambda o: o["deletions"][0].update(day=1))
        with self.assertRaises(L.Deny) as ctx:
            L.run(L.validate(bad))
        self.assertEqual(ctx.exception.code, "no_match")


class Baseline(unittest.TestCase):
    def setUp(self):
        self.fx = L.load(MAIN)
        self.rows = L.run(self.fx)

    def test_replay_returns_every_matching_raw_turn(self):
        row = next(r for r in self.rows if r["probe"]["id"] == "p1")
        self.assertEqual([t["id"] for t in row["replay"]["turns"]], ["t1", "t5", "t6"])

    def test_replay_includes_the_deleted_value_in_some_probe(self):
        hits = [r["probe"]["id"] for r in self.rows if L.leaks(r["replay"], r["deleted"])]
        self.assertEqual(hits, ["p4", "p5"])

    def test_replay_includes_the_stale_value_in_some_probe(self):
        hits = [r["probe"]["id"] for r in self.rows if L.leaks(r["replay"], L.stale_values(self.fx, r["probe"]))]
        self.assertEqual(hits, ["p1", "p2", "p6"])

    def test_ledger_never_includes_stale_values(self):
        for r in self.rows:
            self.assertEqual(L.leaks(r["ledger"], L.stale_values(self.fx, r["probe"])), [])

    def test_replay_ignores_turns_after_the_probe_day(self):
        row = next(r for r in self.rows if r["probe"]["id"] == "p1")
        self.assertNotIn("t8", [t["id"] for t in row["replay"]["turns"]])

    def test_summary_counts(self):
        s = L.summary(self.fx, self.rows)
        self.assertEqual((s["probes"], s["after_deletion"]), (8, 5))
        self.assertEqual((s["ledger_deleted_leaks"], s["replay_deleted_leaks"]), (0, 2))
        self.assertEqual((s["ledger_stale_leaks"], s["replay_stale_leaks"]), (0, 3))
        self.assertEqual((s["ledger_turns"], s["replay_turns"]), (5, 16))


class Validation(unittest.TestCase):
    def test_main_fixture_validates(self):
        self.assertEqual(code_of(RAW), None)

    def test_missing_field(self):
        self.assertEqual(code_of(variant(lambda o: o["facts"][0].pop("source"))), "missing_key")
        self.assertEqual(code_of(variant(lambda o: o.pop("probes"))), "missing_key")

    def test_unknown_field(self):
        self.assertEqual(code_of(variant(lambda o: o["facts"][0].update(extra=1))), "unknown_key")

    def test_non_boolean_fallback(self):
        for bad in ("true", 1, 0, None):
            self.assertEqual(code_of(variant(lambda o: o["probes"][0].update(fallback=bad))), "wrong_type")

    def test_wrong_container_types(self):
        self.assertEqual(code_of(variant(lambda o: o["facts"].__setitem__(0, [1]))), "wrong_type")
        self.assertEqual(code_of(variant(lambda o: o.update(facts={}))), "wrong_type")
        self.assertEqual(code_of([]), "wrong_type")

    def test_invalid_numbers(self):
        self.assertEqual(code_of(variant(lambda o: o["turns"][0].update(day=True))), "wrong_type")
        self.assertEqual(code_of(variant(lambda o: o["turns"][0].update(day="1"))), "wrong_type")
        self.assertEqual(code_of(variant(lambda o: o["turns"][0].update(day=-1))), "out_of_range")
        self.assertEqual(code_of(variant(lambda o: o["turns"][0].update(day=10000))), "out_of_range")
        self.assertEqual(code_of(variant(lambda o: o.update(fixture_version=True))), "bad_version")

    def test_empty_or_whitespace_ids(self):
        for bad in ("", " ", "f 1", " f1", "F1", "f1\n"):
            self.assertEqual(code_of(variant(lambda o: o["facts"][0].update(id=bad))), "bad_id", repr(bad))

    def test_duplicate_ids_in_each_list(self):
        self.assertEqual(code_of(variant(lambda o: o["facts"][1].update(id="f1"))), "duplicate_id")
        self.assertEqual(code_of(variant(lambda o: o["turns"][1].update(id="t1"))), "duplicate_id")
        self.assertEqual(code_of(variant(lambda o: o["probes"][1].update(id="p1"))), "duplicate_id")
        self.assertEqual(code_of(variant(lambda o: o["deletions"].append(dict(o["deletions"][0])))), "duplicate_id")

    def test_period_end_before_start(self):
        self.assertEqual(code_of(variant(lambda o: o["facts"][0].update(start=5, end=4))), "bad_period")
        self.assertEqual(code_of(variant(lambda o: o["deletions"][0].update(start=5, end=4))), "bad_period")
        self.assertIsNone(code_of(variant(lambda o: o["facts"][0].update(start=4, end=4))))

    def test_unknown_trust_tag(self):
        for bad in ("certain", "HIGH", "", 3):
            self.assertIn(code_of(variant(lambda o: o["facts"][0].update(trust=bad))), ("unknown_trust",))

    def test_fact_must_refer_to_a_real_turn_that_holds_its_value(self):
        self.assertEqual(code_of(variant(lambda o: o["facts"][0].update(turn="t99"))), "unknown_turn")
        self.assertEqual(code_of(variant(lambda o: o["facts"][0].update(value="3.7"))), "value_not_in_turn")

    def test_bad_text(self):
        self.assertEqual(code_of(variant(lambda o: o["turns"][0].update(text=" padded"))), "bad_text")
        self.assertEqual(code_of(variant(lambda o: o["turns"][0].update(text="a\u200bb"))), "bad_text")
        self.assertEqual(code_of(variant(lambda o: o["probes"][0].update(terms=[]))), "empty_list")

    def test_strict_json_text(self):
        with self.assertRaises(L.Deny) as ctx:
            L.parse_text('{"a": 1, "a": 2}')
        self.assertEqual(ctx.exception.code, "duplicate_key")
        for text, code in (("{", "malformed_json"), ("\ufeff{}", "bom_not_permitted"),
                           ('{"fixture_version": NaN}', "non_finite_number"),
                           ('{"fixture_version": 1.5}', "float_not_permitted")):
            with self.assertRaises(L.Deny) as ctx:
                L.parse_text(text)
            self.assertEqual(ctx.exception.code, code)

    def test_deeply_nested_json_and_bad_bytes_are_deny(self):
        with self.assertRaises(L.Deny) as ctx:
            L.parse_text("[" * 200000)
        self.assertEqual(ctx.exception.code, "malformed_json")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "bytes.json")
            with open(path, "wb") as h:
                h.write(b'{"fixture_version": 1, "x": "\xff"}')
            with self.assertRaises(L.Deny) as ctx:
                L.load(path)
        self.assertEqual(ctx.exception.code, "fixture_not_utf8")

    def test_load_errors(self):
        with self.assertRaises(L.Deny) as ctx:
            L.load(os.path.join(HERE, "fixtures", "does_not_exist.json"))
        self.assertEqual(ctx.exception.code, "fixture_unreadable")


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        res = subprocess.run([sys.executable, "-B", os.path.join(HERE, "ledger.py")] + list(args),
                             capture_output=True, text=True, cwd=HERE)
        return res.returncode, res.stdout, res.stderr

    def test_report_exit_zero(self):
        rc, out, err = self.run_cli(MAIN)
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("deleted value in evidence: ledger 0, replay 2", out)

    def test_every_bad_fixture_is_deny_exit_two(self):
        bad = sorted(glob.glob(os.path.join(HERE, "fixtures", "bad_*.json")))
        self.assertGreaterEqual(len(bad), 9)
        for path in bad:
            rc, out, err = self.run_cli(path)
            self.assertEqual((rc, out), (2, ""), path)
            self.assertTrue(err.startswith("DENY "), path)

    def test_usage_errors_are_deny_exit_two(self):
        for args in ((), ("a", "b"), ("--flag",)):
            rc, out, err = self.run_cli(*args)
            self.assertEqual((rc, out), (2, ""))
            self.assertTrue(err.startswith("DENY usage"))

    def test_main_writes_deny_to_the_error_stream(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(L.main([os.path.join(HERE, "fixtures", "bad_empty_id.json")], out, err), 2)
        self.assertEqual(out.getvalue(), "")
        self.assertTrue(err.getvalue().startswith("DENY bad_id"))


class Hygiene(unittest.TestCase):
    def test_ledger_imports_only_stdlib(self):
        with open(os.path.join(HERE, "ledger.py"), encoding="utf-8") as h:
            tree = ast.parse(h.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                names.add(node.module.split(".")[0])
        self.assertTrue(names)
        self.assertLessEqual(names, set(sys.stdlib_module_names))

    def test_demo_output_is_stable(self):
        outs = []
        for _ in range(2):
            res = subprocess.run([sys.executable, "-B", os.path.join(HERE, "demo.py")],
                                 capture_output=True, text=True, cwd=HERE)
            self.assertEqual((res.returncode, res.stderr), (0, ""))
            outs.append(res.stdout)
        self.assertEqual(outs[0], outs[1])
        self.assertIn("done-when (c) PASS", outs[0])
        self.assertEqual(hashlib.sha256(outs[0].encode()).hexdigest(), hashlib.sha256(outs[1].encode()).hexdigest())

    def test_evidence_holds_paper_figures_only_under_on_unmeasured(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as h:
            ev = json.load(h)
        self.assertEqual(sorted(ev), ["measured_here", "note", "on_unmeasured", "paper", "status"])
        claims = ev["on_unmeasured"]["claims"]
        self.assertEqual(len(claims), 3)
        self.assertTrue(all(c["status"] == "UNVERIFIED" for c in claims))
        figures = [c["value"] for c in claims]
        rest = json.dumps({k: v for k, v in ev.items() if k != "on_unmeasured"})
        for name in ("README.md", "ledger.py", "demo.py", "test_ledger.py", "mutants.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as h:
                rest += h.read()
        for fig in figures:
            self.assertNotIn(fig, rest)


if __name__ == "__main__":
    unittest.main()
