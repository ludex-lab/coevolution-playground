"""Tests for w27-ranked-conflict-set (stdlib unittest). Run: python3 -B -m unittest -v test_conflict_set"""

import copy
import glob
import io
import json
import os
import subprocess
import sys
import unittest

import conflict_set as cs

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(HERE, "fixtures")


def E(i, field, value, score, poisoned=False, expires=None, writer="w_a"):
    return {"id": i, "writer": writer, "field": field, "value": value, "score": score,
            "poisoned": poisoned, "expires": expires}


def Q(i, field, gold, read_at=10, deadline=None):
    return {"id": i, "field": field, "read_at": read_at, "deadline": deadline, "gold": gold}


def make(entries, queries, k=2, policies=("collapse", "surface")):
    return {"fixture_version": 1, "on_expiry": "DENY", "k": k, "policies": list(policies),
            "entries": entries, "queries": queries}


def fixture(name):
    with open(os.path.join(FX, name), encoding="utf-8") as handle:
        return json.load(handle)


def row(report, policy, query):
    return [r for r in report["rows"] if r["policy"] == policy and r["query"] == query][0]


def deny_code(testcase, root):
    with testcase.assertRaises(cs.Deny) as ctx:
        cs.run(root)
    return ctx.exception.code


class ConflictSetBehaviour(unittest.TestCase):
    def setUp(self):
        self.report = cs.run(fixture("main.json"))

    def test_a_collapse_single_value_view(self):
        view = row(self.report, "collapse", "q_region")["view"]
        self.assertEqual([e["value"] for e in view], ["ap-south"])
        self.assertFalse(row(self.report, "collapse", "q_region")["conflict_visible"])

    def test_a_surface_holds_both_facts_ranked(self):
        view = row(self.report, "surface", "q_region")["view"]
        self.assertEqual([e["id"] for e in view], ["m_region_p", "m_region_a"])
        self.assertTrue(row(self.report, "surface", "q_region")["conflict_visible"])

    def test_b_collapse_lets_poison_through(self):
        r = row(self.report, "collapse", "q_region")
        self.assertEqual(r["decision"], {"decision": "ADOPT", "value": "ap-south"})
        self.assertEqual(r["outcome"], "poisoned")

    def test_b_collapse_poison_on_tie_break(self):
        r = row(self.report, "collapse", "q_log")
        self.assertEqual(r["decision"]["value"], "debug")
        self.assertEqual(r["outcome"], "poisoned")

    def test_l1_surface_escalates_on_multi_value(self):
        for q in ("q_region", "q_owner", "q_log"):
            self.assertEqual(row(self.report, "surface", q)["decision"]["decision"], "ESCALATE")

    def test_l1_escalate_never_names_a_winner(self):
        for r in self.report["rows"]:
            if r["decision"]["decision"] == "ESCALATE":
                self.assertNotIn("value", r["decision"])
                self.assertEqual(sorted(r["decision"]), ["decision", "values"])
                self.assertGreater(len(r["decision"]["values"]), 1)

    def test_l1_reader_unit_rule(self):
        view = [{"value": "x"}, {"value": "y"}]
        self.assertEqual(cs.reader(view), {"decision": "ESCALATE", "values": ["x", "y"]})
        self.assertEqual(cs.reader(list(reversed(view)))["decision"], "ESCALATE")
        self.assertEqual(cs.reader([{"value": "x"}, {"value": "x"}]), {"decision": "ADOPT", "value": "x"})
        self.assertEqual(cs.reader([])["decision"], "HOLD")

    def test_surface_pays_with_escalations(self):
        self.assertEqual(row(self.report, "collapse", "q_owner")["outcome"], "correct")
        self.assertEqual(row(self.report, "surface", "q_owner")["outcome"], "escalated")

    def test_same_value_twice_is_not_a_conflict(self):
        r = row(self.report, "surface", "q_ttl")
        self.assertEqual(r["decision"], {"decision": "ADOPT", "value": "60"})
        self.assertEqual(len(r["view"]), 1)

    def test_conflict_beyond_k_stays_hidden(self):
        r = row(self.report, "surface", "q_backup")
        self.assertTrue(r["field_conflict"])
        self.assertFalse(r["conflict_retrieved"])
        self.assertEqual(r["outcome"], "correct")
        self.assertEqual({e["id"] for e in r["view"]} & {"m_bk_p"}, set())

    def test_empty_field_holds(self):
        for policy in ("collapse", "surface"):
            self.assertEqual(row(self.report, policy, "q_unknown")["decision"]["decision"], "HOLD")

    def test_agents_never_see_poison_label_or_expiry(self):
        for r in self.report["rows"]:
            for entry in r["view"]:
                self.assertEqual(sorted(entry), ["id", "score", "value", "writer"])

    def test_main_counts(self):
        t = self.report["totals"]
        self.assertEqual((t["collapse"]["correct"], t["collapse"]["poisoned"], t["collapse"]["held"]), (4, 2, 1))
        self.assertEqual((t["surface"]["correct"], t["surface"]["escalated"], t["surface"]["held"]), (3, 3, 1))
        self.assertEqual((t["collapse"]["conflict_visible"], t["surface"]["conflict_visible"]), (0, 3))

    def test_run_is_deterministic(self):
        again = cs.run(fixture("main.json"))
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(self.report, sort_keys=True))


class RankAndBudget(unittest.TestCase):
    def test_l2_score_descending(self):
        store = cs.Store()
        for e in (E("a_low", "f", "x", 1), E("z_high", "f", "y", 9), E("m_mid", "f", "z", 5)):
            store.write(e)
        self.assertEqual([e["id"] for e in store.read("f", 3)], ["z_high", "m_mid", "a_low"])

    def test_l2_tie_breaks_by_id_ascending(self):
        store = cs.Store()
        for e in (E("b_two", "f", "y", 5), E("a_one", "f", "x", 5), E("c_three", "f", "z", 5)):
            store.write(e)
        self.assertEqual([e["id"] for e in store.read("f", 3)], ["a_one", "b_two", "c_three"])

    def test_l2_rank_ignores_writer_poison_flag_and_value(self):
        a = E("a_one", "f", "x", 5, poisoned=True, writer="w_z")
        b = E("b_two", "f", "y", 5, poisoned=False, writer="w_a")
        self.assertLess(cs.rank_key(a), cs.rank_key(b))
        self.assertEqual(cs.rank_key(a), (-5, "a_one"))

    def test_l2_no_toggle_keys_in_fixture(self):
        root = fixture("main.json")
        root["trust_gate"] = True
        self.assertEqual(deny_code(self, root), "unknown_key")
        self.assertFalse(any("gate" in k or "router" in k for k in cs.ROOT_KEYS + cs.ENTRY_KEYS + cs.QUERY_KEYS))

    def test_c_k_one_makes_surface_equal_collapse(self):
        root = fixture("main.json")
        root["k"] = 1
        report = cs.run(root)
        self.assertEqual(report["totals"]["surface"]["poisoned"], report["totals"]["collapse"]["poisoned"])
        self.assertEqual(report["totals"]["surface"]["escalated"], 0)

    def test_c_surface_view_within_k(self):
        entries = [E("e%d" % i, "f", "v%d" % i, 10 - i) for i in range(5)]
        for k in (1, 2, 3, 5):
            r = row(cs.run(make(entries, [Q("q", "f", "v0")], k=k)), "surface", "q")
            self.assertEqual(len(r["view"]), k)

    def test_c_policy_ignoring_cap_is_denied(self):
        retrieved = [E("a_one", "f", "x", 2), E("b_two", "f", "y", 1)]
        extra = E("c_three", "f", "z", 0)
        with self.assertRaises(cs.Deny) as ctx:
            cs.check_budget(retrieved + [extra], retrieved, 2)
        self.assertEqual(ctx.exception.code, "budget_exceeded")
        with self.assertRaises(cs.Deny):
            cs.check_budget([extra], retrieved, 2)
        cs.check_budget(retrieved, retrieved, 2)
        three = retrieved + [extra]
        for view in ([], three[:1], three):
            with self.assertRaises(cs.Deny):
                cs.check_budget(view, three, 2)

    def test_c_run_denies_a_cap_breaking_policy(self):
        cs.POLICIES["greedy"] = lambda retrieved: retrieved + retrieved
        try:
            root = make([E("a_one", "f", "x", 2), E("b_two", "f", "y", 1)], [Q("q", "f", "x")], policies=("greedy",))
            self.assertEqual(deny_code(self, root), "budget_exceeded")
        finally:
            del cs.POLICIES["greedy"]


    def test_store_copies_what_it_holds(self):
        store, entry = cs.Store(), E("a_one", "f", "x", 1)
        store.write(entry)
        entry["value"] = "changed"
        snap = store.snapshot()
        snap[0]["value"] = "changed too"
        self.assertEqual(store.read("f", 1)[0]["value"], "x")

    def test_wrong_but_not_poisoned_outcome(self):
        root = make([E("a_one", "f", "stale", 9), E("b_two", "f", "fresh", 1)], [Q("q", "f", "fresh")])
        self.assertEqual(row(cs.run(root), "collapse", "q")["outcome"], "wrong")

    def test_float_score_and_time_zero_are_valid(self):
        root = make([E("a_one", "f", "x", 1.5), E("b_two", "f", "y", 2)], [Q("q", "f", "y", 0, 0)])
        self.assertEqual(row(cs.run(root), "collapse", "q")["decision"]["value"], "y")


class ExpiryDeny(unittest.TestCase):
    def setUp(self):
        self.report = cs.run(fixture("expired.json"))

    def test_deadline_passed_is_deny(self):
        for p in ("collapse", "surface"):
            r = row(self.report, p, "q_late")
            self.assertEqual(r["decision"], {"decision": "DENY", "reason": "deadline_passed"})
            self.assertEqual(r["view"], [])

    def test_expired_retrieved_entry_is_deny(self):
        for p in ("collapse", "surface"):
            self.assertEqual(row(self.report, p, "q_stale")["decision"]["reason"], "entry_expired")

    def test_fresh_read_still_adopts(self):
        self.assertEqual(row(self.report, "surface", "q_fresh")["decision"], {"decision": "ADOPT", "value": "10"})

    def test_boundaries_are_inclusive(self):
        entries = [E("a_one", "f", "x", 1, expires=5)]
        ok = cs.run(make(entries, [Q("q", "f", "x", 5, 5)]))
        self.assertEqual(row(ok, "collapse", "q")["decision"]["decision"], "ADOPT")
        late = cs.run(make(entries, [Q("q", "f", "x", 6, 9)]))
        self.assertEqual(row(late, "collapse", "q")["decision"]["reason"], "entry_expired")
        past = cs.run(make([E("a_one", "f", "x", 1)], [Q("q", "f", "x", 6, 5)]))
        self.assertEqual(row(past, "collapse", "q")["decision"]["reason"], "deadline_passed")

    def test_expired_entry_below_cap_is_not_read(self):
        entries = [E("a_one", "f", "x", 9), E("b_two", "f", "x", 8), E("c_three", "f", "y", 7, expires=1)]
        r = row(cs.run(make(entries, [Q("q", "f", "x")])), "surface", "q")
        self.assertEqual(r["decision"], {"decision": "ADOPT", "value": "x"})

    def test_on_expiry_declared_deny(self):
        self.assertEqual(self.report["on_expiry"], "DENY")
        root = fixture("main.json")
        root["on_expiry"] = "HOLD"
        self.assertEqual(deny_code(self, root), "bad_on_expiry")


class StrictInput(unittest.TestCase):
    def check(self, mutate, code):
        root = fixture("main.json")
        mutate(root)
        self.assertEqual(deny_code(self, root), code)

    def test_missing_keys(self):
        self.check(lambda r: r.pop("k"), "missing_key")
        self.check(lambda r: r["entries"][0].pop("score"), "missing_key")
        self.check(lambda r: r["queries"][0].pop("gold"), "missing_key")

    def test_wrong_types(self):
        self.check(lambda r: r.__setitem__("entries", {}), "empty_entries")
        self.check(lambda r: r["entries"].__setitem__(0, []), "wrong_type")
        self.check(lambda r: r["entries"][0].__setitem__("poisoned", 0), "wrong_type")
        self.check(lambda r: r["entries"][0].__setitem__("value", 5), "bad_text")
        self.check(lambda r: r.__setitem__("fixture_version", True), "bad_version")
        self.check(lambda r: r.__setitem__("queries", []), "empty_queries")

    def test_score_types(self):
        for bad in (True, False, "9", None, [1], float("inf"), 10 ** 7):
            self.check(lambda r, b=bad: r["entries"][0].__setitem__("score", b), "bad_score")

    def test_time_types(self):
        for bad in (True, 1.5, "3", -1, 10000):
            self.check(lambda r, b=bad: r["queries"][0].__setitem__("read_at", b), "bad_time")
        self.check(lambda r: r["queries"][0].__setitem__("deadline", False), "bad_time")
        self.check(lambda r: r["queries"][0].__setitem__("read_at", None), "bad_time")
        self.check(lambda r: r["entries"][0].__setitem__("expires", 2.0), "bad_time")

    def test_bad_ids(self):
        for bad in ("", " ", "A_b", "a b", " a", "9a", "x" * 33, 7, None):
            self.check(lambda r, b=bad: r["entries"][0].__setitem__("id", b), "bad_id")
            self.check(lambda r, b=bad: r["queries"][0].__setitem__("id", b), "bad_id")
        self.check(lambda r: r["entries"][0].__setitem__("writer", " "), "bad_id")

    def test_bad_text_values(self):
        for bad in ("", "  ", " x", "x ", "a\nb", "q" * 201):
            self.check(lambda r, b=bad: r["entries"][0].__setitem__("value", b), "bad_text")

    def test_duplicate_ids(self):
        self.check(lambda r: r["entries"][1].__setitem__("id", r["entries"][0]["id"]), "duplicate_id")
        self.check(lambda r: r["queries"][1].__setitem__("id", r["queries"][0]["id"]), "duplicate_id")

    def test_k_values(self):
        for bad in (0, -1, True, 2.0, "2", 51, None):
            self.check(lambda r, b=bad: r.__setitem__("k", b), "bad_k")

    def test_policies(self):
        self.check(lambda r: r.__setitem__("policies", ["collapse", "majority"]), "unknown_policy")
        self.check(lambda r: r.__setitem__("policies", [["surface"]]), "unknown_policy")
        self.check(lambda r: r.__setitem__("policies", []), "bad_policies")
        self.check(lambda r: r.__setitem__("policies", ["surface", "surface"]), "bad_policies")
        self.check(lambda r: r.__setitem__("policies", "surface"), "bad_policies")

    def test_json_level_rejections(self):
        for text, code in (('{"a": 1, "a": 2}', "duplicate_key"), ("{\"a\": NaN}", "non_finite_number"),
                           ('{"a": 1e999}', "non_finite_number"), ("\ufeff{}", "bom_not_permitted"),
                           ("{", "bad_json"), ("[" * 100000, "bad_json")):
            with self.assertRaises(cs.Deny) as ctx:
                cs.parse_text(text)
            self.assertEqual(ctx.exception.code, code)


class CommandLine(unittest.TestCase):
    def cli(self, *args):
        res = subprocess.run([sys.executable, "-B", os.path.join(HERE, "conflict_set.py")] + list(args),
                             capture_output=True, text=True, cwd=HERE, timeout=60)
        return res.returncode, res.stdout, res.stderr

    def test_main_fixture_exit_zero(self):
        rc, out, err = self.cli(os.path.join("fixtures", "main.json"))
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(json.loads(out)["totals"]["collapse"]["poisoned"], 2)

    def test_expired_fixture_exit_two_with_deny_decisions(self):
        rc, out, err = self.cli(os.path.join("fixtures", "expired.json"))
        self.assertEqual((rc, err), (2, ""))
        self.assertEqual(json.loads(out)["totals"]["collapse"]["denied"], 2)

    def test_main_fixture_has_no_deny_row(self):
        rc, out, _ = self.cli(os.path.join("fixtures", "main.json"))
        self.assertEqual(rc, 0)
        self.assertNotIn("DENY", [r["decision"]["decision"] for r in json.loads(out)["rows"]])

    def test_demo_exits_zero_on_purpose(self):
        res = subprocess.run([sys.executable, "-B", os.path.join(HERE, "demo.py")],
                             capture_output=True, text=True, cwd=HERE, timeout=60)
        self.assertEqual((res.returncode, res.stderr), (0, ""))
        self.assertIn("DENY", res.stdout)

    def test_every_bad_fixture_denies_exit_two(self):
        paths = sorted(glob.glob(os.path.join(FX, "bad_*.json")))
        self.assertGreaterEqual(len(paths), 11)
        for path in paths:
            rc, out, err = self.cli(path)
            self.assertEqual(rc, 2, path)
            self.assertEqual(out, "")
            self.assertTrue(err.startswith("DENY "), path)
            self.assertEqual(err.count("\n"), 1, path)

    def test_usage_errors(self):
        for args in ([], ["a", "b"], ["--help"]):
            rc, _, err = self.cli(*args)
            self.assertEqual(rc, 2)
            self.assertTrue(err.startswith("DENY usage: "), err)
        rc, _, err = self.cli(os.path.join(FX, "nope.json"))
        self.assertEqual(rc, 2)
        self.assertTrue(err.startswith("DENY fixture_unreadable"))

    def test_non_utf8_file_denied(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.json")
            with open(path, "wb") as handle:
                handle.write(b"\xff\xfe{}")
            rc, _, err = self.cli(path)
        self.assertEqual(rc, 2)
        self.assertTrue(err.startswith("DENY fixture_unreadable"))


class Packaging(unittest.TestCase):
    def test_stdlib_only_imports(self):
        stdlib = set(sys.stdlib_module_names) | {"conflict_set"}
        import ast
        for name in ("conflict_set.py", "demo.py", "mutants.py", "test_conflict_set.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            for node in ast.walk(tree):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module] if isinstance(node, ast.ImportFrom) else []
                for mod in mods:
                    self.assertIn(mod.split(".")[0], stdlib, name + " imports " + mod)

    def test_evidence_declares_policy_and_marks_paper_numbers(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as handle:
            ev = json.load(handle)
        self.assertEqual(ev["on_expiry"], "DENY")
        self.assertEqual(ev["status"], "UNVERIFIED")
        claims = ev["on_unmeasured"]["claims"]
        self.assertEqual(sorted(c["value"] for c in claims),
                         sorted(["+0.340", "22 -> 7 of 122", "50.2 -> 68.7", "16.2 -> 13.2", "35.2"]))
        self.assertTrue(all(c["status"] == "UNVERIFIED" for c in claims))
        report = cs.run(fixture("main.json"))
        self.assertEqual(ev["measured_here"]["main_totals"], report["totals"])
        self.assertEqual(ev["measured_here"]["k"], report["k"])
        self.assertEqual(ev["measured_here"]["expired_totals"], cs.run(fixture("expired.json"))["totals"])

    def test_paper_numbers_only_in_unmeasured(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as handle:
            ev = json.load(handle)
        ev.pop("on_unmeasured")
        text = json.dumps(ev)
        for number in ("0.340", "122", "68.7", "13.2", "35.2"):
            self.assertNotIn(number, text)



if __name__ == "__main__":
    unittest.main()
