"""Tests for preview_rules (stdlib unittest). Run: python3 -B -m unittest"""

import copy
import io
import itertools
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import preview_rules as pr  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "memory_rules.json")
USES = ("u1", "u2", "u3", "u4", "u5", "u6", "u7", "u8")

# Hand-listed: which fixture uses each rule permits (worked out on paper from the fixture).
HAND = {
    ("same_task", "preference_only"): {"u1"},
    ("same_task", "one_off_only"): {"u5"},
    ("same_task", "any_kind"): {"u1", "u5"},
    ("same_topic", "preference_only"): {"u1", "u2"},
    ("same_topic", "one_off_only"): {"u5"},
    ("same_topic", "any_kind"): {"u1", "u2", "u5"},
    ("any_task", "preference_only"): {"u1", "u2", "u3", "u4"},
    ("any_task", "one_off_only"): {"u5", "u6"},
    ("any_task", "any_kind"): {"u1", "u2", "u3", "u4", "u5", "u6"},
}
INTENDED = ("same_topic", "preference_only")
WEAK = [("same_task", "preference_only"), ("same_topic", "preference_only"),
        ("any_task", "preference_only")]
TRANSFER = [("same_topic", "preference_only"), ("same_topic", "any_kind")]


def brute(permitted, blocked):
    return {r for r, s in HAND.items() if permitted in s and blocked not in s}


def raw():
    with open(FIXTURE, encoding="utf-8") as handle:
        return json.load(handle)


def deny_code(obj):
    try:
        pr.validate_fixture(obj)
    except pr.FixtureError as exc:
        return exc.code
    return None


def text_code(text):
    try:
        pr.parse_fixture_text(text)
    except pr.FixtureError as exc:
        return exc.code
    return None


class Str(str):
    pass


class Int(int):
    pass


class Dict(dict):
    pass


class List(list):
    pass


class EnumerationTests(unittest.TestCase):
    def setUp(self):
        self.fx = pr.load_fixture(FIXTURE)

    def test_vocabulary_is_the_full_product_in_order(self):
        self.assertEqual(list(self.fx["rules"]), [(s, k) for s in pr.SCOPES for k in pr.KINDS])
        self.assertEqual(len(self.fx["rules"]), 9)

    def test_permits_matches_the_hand_table_on_every_cell(self):
        for rule, expected in HAND.items():
            got = {u["id"] for u in self.fx["uses"] if pr.permits(self.fx, rule, u)}
            self.assertEqual(got, expected, rule)

    def test_every_ordered_pair_matches_brute_force(self):
        for p, b in itertools.permutations(USES, 2):
            got = pr.compatible(self.fx, p, b)
            self.assertEqual(set(got), brute(p, b), (p, b))
            self.assertEqual(len(got), len(set(got)))
            self.assertEqual(got, [r for r in self.fx["rules"] if r in got])

    def test_same_use_on_both_sides_fits_no_rule(self):
        for u in USES:
            self.assertEqual(pr.compatible(self.fx, u, u), [])

    def test_intended_pairs_and_their_sets(self):
        pairs, yes, no = pr.all_pairs(self.fx)
        self.assertEqual(yes, ["u1", "u2"])
        self.assertEqual(no, ["u3", "u4", "u5", "u6", "u7", "u8"])
        self.assertEqual(len(pairs), 12)
        sizes = {(p, b): len(c) for p, b, c in pairs}
        self.assertEqual(sizes, {
            ("u1", "u3"): 4, ("u1", "u4"): 4, ("u1", "u5"): 3, ("u1", "u6"): 5,
            ("u1", "u7"): 6, ("u1", "u8"): 6, ("u2", "u3"): 2, ("u2", "u4"): 2,
            ("u2", "u5"): 2, ("u2", "u6"): 3, ("u2", "u7"): 4, ("u2", "u8"): 4})
        for p, b, c in pairs:
            self.assertIn(INTENDED, c)
            self.assertEqual(set(c), brute(p, b))
        self.assertEqual(sum(1 for _, _, c in pairs if len(c) == 1), 0)

    def test_vacuous_blocked_uses(self):
        self.assertEqual(pr.vacuous_blocked(self.fx), ["u7", "u8"])

    def test_report_counts(self):
        lines = pr.report(self.fx)
        self.assertIn("pairs under intended: 12 (permitted 2 x blocked 6)", lines)
        self.assertIn("blocked uses no rule permits: u7 u8", lines)
        self.assertIn("pairs whose blocked use no rule permits: 4/12", lines)
        self.assertIn("pairs that identify the intended rule: 0/12", lines)
        self.assertIn("compatible-set sizes: 2:3 3:2 4:4 5:1 6:2", lines)
        self.assertIn("fixture: rules=9 (scopes=3 x kinds=3) tasks=4 events=2 uses=8 previews=2", lines[0])
        self.assertIn("use u2 veg@grocery_list self: intended=permit permitted_by=4/9 transfer=yes", lines)
        self.assertIn("use u7 veg@meal_planning others: intended=block permitted_by=0/9 transfer=no", lines)
        self.assertIn("smallest probe set identifying the intended rule: 3 uses, 2 sets: u2,u3,u5 | u2,u4,u5", lines)
        self.assertIn("rule groups no fixture use can tell apart: 1 [same_task/one_off_only same_topic/one_off_only]", lines)


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.fx = pr.load_fixture(FIXTURE)

    def test_weak_preview_fits_more_than_the_intended_rule(self):
        weak = pr.compatible(self.fx, "u1", "u5")
        self.assertEqual(weak, WEAK)
        self.assertEqual(pr.scopes_of(weak), ["same_task", "same_topic", "any_task"])
        self.assertEqual(pr.verdict(weak, INTENDED), "AMBIGUOUS")

    def test_transfer_preview_fixes_the_scope(self):
        tr = pr.compatible(self.fx, "u2", "u3")
        self.assertEqual(tr, TRANSFER)
        self.assertEqual(pr.scopes_of(tr), ["same_topic"])
        self.assertTrue(pr.is_transfer(self.fx, self.fx["use_by_id"]["u2"]))
        self.assertTrue(pr.is_transfer(self.fx, self.fx["use_by_id"]["u3"]))
        self.assertFalse(pr.is_transfer(self.fx, self.fx["use_by_id"]["u1"]))
        self.assertFalse(pr.is_transfer(self.fx, self.fx["use_by_id"]["u5"]))

    def test_both_previews_together_identify_the_rule(self):
        lines = pr.report(self.fx)
        self.assertIn("all previews together: 1 rules, 1 scopes -> IDENTIFIED: same_topic/preference_only", lines)
        self.assertIn("preview weak (u1 permit, u5 block): 3 rules, 3 scopes -> AMBIGUOUS: "
                      "same_task/preference_only same_topic/preference_only any_task/preference_only", lines)
        self.assertIn("preview transfer (u2 permit, u3 block): 2 rules, 1 scopes -> AMBIGUOUS: "
                      "same_topic/preference_only same_topic/any_kind", lines)

    def test_probes_after_the_weak_preview(self):
        rows = {r["use"]: r for r in pr.probe_table(self.fx, WEAK, ("u1", "u5"))}
        self.assertEqual(sorted(rows), ["u2", "u3", "u4", "u6", "u7", "u8"])
        self.assertEqual({u for u, r in rows.items() if r["separates"]}, {"u2", "u3", "u4"})
        self.assertEqual(rows["u2"]["block"], [("same_task", "preference_only")])
        self.assertEqual(rows["u3"]["permit"], [("any_task", "preference_only")])
        self.assertTrue(rows["u6"]["transfer"])
        self.assertFalse(rows["u6"]["separates"])
        for u in ("u7", "u8"):
            self.assertEqual(rows[u]["permit"], [])
            self.assertEqual(pr.scopes_of(pr.consistent(self.fx, WEAK, (u,))), ["same_task", "same_topic", "any_task"])
        self.assertEqual(pr.consistent(self.fx, WEAK, ("u2",)), WEAK[1:])
        self.assertEqual(pr.consistent(self.fx, WEAK, ("u3",)), WEAK[:2])
        self.assertEqual(pr.consistent(self.fx, WEAK, ("u2", "u3")), [INTENDED])
        lines = pr.report(self.fx)
        self.assertIn("probe after weak: u2 transfer=yes separates=yes scopes_left=2 (same_topic any_task)", lines)
        self.assertIn("probe after weak: u7 transfer=no separates=no scopes_left=3 (same_task same_topic any_task)", lines)

    def test_probe_that_every_rule_permits_does_not_separate(self):
        rows = {r["use"]: r for r in pr.probe_table(self.fx, TRANSFER)}
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows["u1"]["permit"], TRANSFER)
        self.assertFalse(rows["u1"]["separates"])
        self.assertTrue(rows["u5"]["separates"])
        self.assertFalse(rows["u3"]["separates"])

    def test_one_probe_can_be_enough(self):
        obj = raw()
        obj["vocabulary"] = {"scopes": ["same_topic"], "kinds": ["preference_only", "any_kind"]}
        fx = pr.validate_fixture(obj)
        size, sets = pr.smallest_probe_sets(fx)
        self.assertEqual((size, sets), (1, [("u5",)]))

    def test_smallest_probe_sets(self):
        size, sets = pr.smallest_probe_sets(self.fx)
        self.assertEqual(size, 3)
        self.assertEqual(sets, [("u2", "u3", "u5"), ("u2", "u4", "u5")])
        for combo in itertools.combinations(USES, 2):
            self.assertNotEqual(pr.consistent(self.fx, self.fx["rules"], combo), [INTENDED])

    def test_unidentifiable_intended_rule_reports_none(self):
        obj = raw()
        obj["intended"] = {"scope": "same_task", "kinds": "one_off_only"}
        obj["previews"] = [{"id": "p", "permitted": "u5", "blocked": "u1"}]
        fx = pr.validate_fixture(obj)
        self.assertEqual(pr.smallest_probe_sets(fx), (None, []))
        self.assertIn("smallest probe set identifying the intended rule: none", pr.report(fx))

    def test_verdicts(self):
        self.assertEqual(pr.verdict([INTENDED], INTENDED), "IDENTIFIED")
        self.assertEqual(pr.verdict(WEAK, INTENDED), "AMBIGUOUS")
        self.assertEqual(pr.verdict([], INTENDED), "CONFLICT")
        self.assertEqual(pr.verdict([WEAK[0]], INTENDED), "CONFLICT")
        self.assertEqual(pr.compatible(self.fx, "u5", "u1"), [("same_task", "one_off_only"),
                                                             ("same_topic", "one_off_only"),
                                                             ("any_task", "one_off_only")])

    def test_unknown_use_is_refused(self):
        for bad in ("u9", Str("u1"), 1, None):
            with self.assertRaises(pr.FixtureError) as ctx:
                pr.compatible(self.fx, bad, "u5")
            self.assertEqual(ctx.exception.code, "unknown_use")

    def test_smaller_vocabulary(self):
        obj = raw()
        obj["vocabulary"] = {"scopes": ["any_task", "same_topic"], "kinds": ["preference_only"]}
        obj["previews"] = [{"id": "t", "permitted": "u2", "blocked": "u3"}]
        fx = pr.validate_fixture(obj)
        self.assertEqual(fx["rules"], (("any_task", "preference_only"), ("same_topic", "preference_only")))
        self.assertEqual(pr.compatible(fx, "u1", "u5"), list(fx["rules"]))
        self.assertIn("all previews together: 1 rules, 1 scopes -> IDENTIFIED: same_topic/preference_only", pr.report(fx))
        self.assertIn("rule groups no fixture use can tell apart: 0", pr.report(fx))


class ValidationTests(unittest.TestCase):
    def test_fixture_is_valid(self):
        self.assertIsNone(deny_code(raw()))

    def test_snapshot_is_independent_of_the_input(self):
        obj = raw()
        fx = pr.validate_fixture(obj)
        before = pr.report(fx)
        obj["uses"][1]["task"] = "trip_booking"
        obj["events"][0]["kind"] = "one_off"
        obj["tasks"][1]["topic"] = "travel"
        obj["vocabulary"]["scopes"].pop()
        obj["previews"].clear()
        self.assertEqual(pr.report(fx), before)

    def test_types_and_subclasses(self):
        cases = []
        o = raw(); o["fixture_version"] = True; cases.append((o, "bad_version"))
        o = raw(); o["fixture_version"] = 2; cases.append((o, "bad_version"))
        o = raw(); o["fixture_version"] = Int(1); cases.append((o, "bad_version"))
        o = raw(); o["fixture_version"] = "1"; cases.append((o, "bad_version"))
        o = raw(); o["fixture_version"] = 1.0; cases.append((o, "bad_version"))
        o = raw(); o["fixture_version"] = float("nan"); cases.append((o, "bad_version"))
        o = raw(); o["fixture_version"] = float("inf"); cases.append((o, "bad_version"))
        o = raw(); o["tasks"][0]["id"] = Str("meal_planning"); cases.append((o, "wrong_type"))
        o = raw(); o["tasks"][0]["topic"] = True; cases.append((o, "wrong_type"))
        o = raw(); o["events"][0]["text"] = Str("x"); cases.append((o, "wrong_type"))
        o = raw(); o["events"][0]["kind"] = Str("preference"); cases.append((o, "wrong_type"))
        o = raw(); o["uses"][0] = Dict(o["uses"][0]); cases.append((o, "wrong_type"))
        o = raw(); o["uses"] = List(o["uses"]); cases.append((o, "wrong_type"))
        o = raw(); o["uses"] = tuple(o["uses"]); cases.append((o, "wrong_type"))
        o = raw(); o["intended"][Str("extra")] = "x"; cases.append((o, "wrong_type"))
        o = raw(); o["intended"] = {1: "same_topic", "scope": "same_topic", "kinds": "preference_only"}; cases.append((o, "wrong_type"))
        o = raw(); o["intended"] = {Str("scope"): "same_topic", "kinds": "preference_only"}; cases.append((o, "wrong_type"))
        o = raw(); o["previews"][0]["permitted"] = 1; cases.append((o, "wrong_type"))
        o = raw(); o["uses"][0]["audience"] = None; cases.append((o, "wrong_type"))
        o = raw(); o["vocabulary"]["scopes"][0] = False; cases.append((o, "wrong_type"))
        cases.append(([], "wrong_type"))
        for obj, code in cases:
            self.assertEqual(deny_code(obj), code, obj if not isinstance(obj, dict) else code)

    def test_str_subclass_key_with_exact_key_set(self):
        o = raw()
        o["intended"] = {Str("scope"): "same_topic", Str("kinds"): "preference_only"}
        self.assertEqual(deny_code(o), "wrong_type")

    def test_keys(self):
        o = raw(); o["extra"] = 1
        self.assertEqual(deny_code(o), "unknown_key")
        o = raw(); del o["previews"]
        self.assertEqual(deny_code(o), "missing_key")
        o = raw(); o["uses"][3]["note"] = "x"
        self.assertEqual(deny_code(o), "unknown_key")
        o = raw(); del o["events"][1]["text"]
        self.assertEqual(deny_code(o), "missing_key")
        o = raw(); del o["vocabulary"]["kinds"]
        self.assertEqual(deny_code(o), "missing_key")

    def test_values_and_references(self):
        cases = []
        o = raw(); o["vocabulary"]["scopes"].append("same_task"); cases.append((o, "duplicate_id"))
        o = raw(); o["vocabulary"]["kinds"].append("any_kind"); cases.append((o, "duplicate_id"))
        o = raw(); o["vocabulary"]["scopes"].append("everywhere"); cases.append((o, "unknown_value"))
        o = raw(); o["vocabulary"]["kinds"] = []; cases.append((o, "empty_list"))
        o = raw(); o["uses"] = []; cases.append((o, "empty_list"))
        o = raw(); o["previews"] = []; cases.append((o, "empty_list"))
        o = raw(); o["tasks"][1]["id"] = "meal_planning"; cases.append((o, "duplicate_id"))
        o = raw(); o["events"][1]["id"] = "veg"; cases.append((o, "duplicate_id"))
        o = raw(); o["uses"][1]["id"] = "u1"; cases.append((o, "duplicate_id"))
        o = raw(); o["previews"][1]["id"] = "weak"; cases.append((o, "duplicate_id"))
        o = raw(); o["uses"][1]["task"] = "meal_planning"; cases.append((o, "duplicate_use"))
        o = raw(); o["events"][0]["origin_task"] = "cooking"; cases.append((o, "unknown_reference"))
        o = raw(); o["uses"][0]["event"] = "tea"; cases.append((o, "unknown_reference"))
        o = raw(); o["uses"][0]["task"] = "cooking"; cases.append((o, "unknown_reference"))
        o = raw(); o["previews"][0]["blocked"] = "u9"; cases.append((o, "unknown_reference"))
        o = raw(); o["previews"][0]["permitted"] = "u9"; cases.append((o, "unknown_reference"))
        o = raw(); o["events"][0]["kind"] = "habit"; cases.append((o, "unknown_value"))
        o = raw(); o["uses"][0]["audience"] = "public"; cases.append((o, "unknown_value"))
        o = raw(); o["intended"]["scope"] = "everywhere"; cases.append((o, "unknown_value"))
        o = raw(); o["intended"]["kinds"] = "all"; cases.append((o, "unknown_value"))
        o = raw(); o["vocabulary"]["kinds"] = ["any_kind"]; cases.append((o, "intended_not_in_vocabulary"))
        o = raw(); o["vocabulary"]["scopes"] = ["same_task"]; cases.append((o, "intended_not_in_vocabulary"))
        o = raw(); o["previews"][0]["blocked"] = "u1"; cases.append((o, "same_use_twice"))
        o = raw(); o["previews"][0] = {"id": "w", "permitted": "u3", "blocked": "u5"}; cases.append((o, "preview_contradicts_intended"))
        o = raw(); o["previews"][0] = {"id": "w", "permitted": "u1", "blocked": "u2"}; cases.append((o, "preview_contradicts_intended"))
        for obj, code in cases:
            self.assertEqual(deny_code(obj), code, code)

    def test_ids(self):
        for bad in ("Meal", "1meal", "meal planning", "meal\u200bplan", "meal-plan", "", "m" * 33,
                    "me\u0430l", "meal\n", "\uff4deal"):
            o = raw(); o["tasks"][0]["id"] = bad
            self.assertEqual(deny_code(o), "bad_id", repr(bad))
            o = raw(); o["tasks"][0]["topic"] = bad
            self.assertEqual(deny_code(o), "bad_id", repr(bad))
        o = raw(); o["tasks"][3]["topic"] = "m" * 32
        self.assertIsNone(deny_code(o))

    def test_texts(self):
        for bad in ("", " ", " lead", "trail ", "a\u200bb", "a\x07b", "a\u2028b", "x" * 201,
                    "e\u0301", "a\ufeffb", "a\ue000b", "a\u0378b"):
            o = raw(); o["uses"][0]["text"] = bad
            self.assertEqual(deny_code(o), "bad_text", repr(bad))
        o = raw(); o["uses"][0]["text"] = "x" * 200
        self.assertIsNone(deny_code(o))
        o = raw(); o["uses"][0]["text"] = "\u00e9 \ucc44\uc2dd"
        self.assertIsNone(deny_code(o))

    def test_json_text(self):
        with open(FIXTURE, encoding="utf-8") as handle:
            good = handle.read()
        self.assertIsNone(text_code(good))
        self.assertEqual(text_code(good.replace('"fixture_version": 1', '"fixture_version": NaN')), "non_finite_number")
        self.assertEqual(text_code(good.replace('"fixture_version": 1', '"fixture_version": Infinity')), "non_finite_number")
        self.assertEqual(text_code(good.replace('"fixture_version": 1', '"fixture_version": -Infinity')), "non_finite_number")
        self.assertEqual(text_code(good.replace('"fixture_version": 1', '"fixture_version": 1.0')), "float_not_permitted")
        self.assertEqual(text_code(good.replace('"fixture_version": 1', '"fixture_version": 1e0')), "float_not_permitted")
        self.assertEqual(text_code(good.replace('"fixture_version": 1', '"fixture_version": true')), "bad_version")
        self.assertEqual(text_code(good.replace('"fixture_version": 1,', '"fixture_version": 1, "fixture_version": 1,')), "duplicate_key")
        self.assertEqual(text_code(good.replace('"topic": "food"}', '"topic": "food", "topic": "food"}', 1)), "duplicate_key")
        self.assertEqual(text_code("\ufeff" + good), "bom_not_permitted")
        self.assertEqual(text_code(good + "\n{}"), "malformed_json")
        self.assertEqual(text_code(good[:-20]), "malformed_json")
        self.assertEqual(text_code(""), "malformed_json")
        self.assertEqual(text_code(b"{}"), "fixture_unreadable")
        self.assertEqual(text_code(Str(good)), "fixture_unreadable")
        self.assertEqual(text_code("[" * 100000), "malformed_json")

    def test_files(self):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "absent.json")
            with self.assertRaises(pr.FixtureError) as ctx:
                pr.load_fixture(missing)
            self.assertEqual(ctx.exception.code, "fixture_unreadable")
            bad = os.path.join(d, "latin1.json")
            with open(bad, "wb") as handle:
                handle.write('{"x": "caf\u00e9"}'.encode("latin-1"))
            with self.assertRaises(pr.FixtureError) as ctx:
                pr.load_fixture(bad)
            self.assertEqual(ctx.exception.code, "fixture_not_utf8")
            with self.assertRaises(pr.FixtureError) as ctx:
                pr.load_fixture(d)
            self.assertEqual(ctx.exception.code, "fixture_unreadable")


class CliTests(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        code = pr.main(argv, out, err)
        return code, out.getvalue(), err.getvalue()

    def test_report(self):
        code, out, err = self.run_main([FIXTURE])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines(), pr.report(pr.load_fixture(FIXTURE)))

    def test_one_preview(self):
        code, out, err = self.run_main([FIXTURE, "--permitted", "u1", "--blocked", "u5"])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, "preview (u1 permit, u5 block): 3 rules, 3 scopes -> AMBIGUOUS: "
                              "same_task/preference_only same_topic/preference_only any_task/preference_only\n")
        code, out, _ = self.run_main(["--blocked", "u3", "--permitted", "u2", FIXTURE])
        self.assertEqual(code, 0)
        self.assertIn("2 rules, 1 scopes -> AMBIGUOUS", out)
        code, out, _ = self.run_main([FIXTURE, "--permitted", "u5", "--blocked", "u1"])
        self.assertEqual(code, 0)
        self.assertIn("-> CONFLICT", out)
        code, out, _ = self.run_main([FIXTURE, "--permitted", "u7", "--blocked", "u1"])
        self.assertEqual(code, 0)
        self.assertTrue(out.endswith("0 rules, 0 scopes -> CONFLICT: -\n"))

    def test_deny(self):
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "bad.json")
            obj = raw(); obj["uses"][0]["audience"] = "public"
            with open(bad, "w", encoding="utf-8") as handle:
                json.dump(obj, handle)
            cases = [
                [bad], [os.path.join(d, "absent.json")], [], [FIXTURE, FIXTURE],
                [FIXTURE, "--permitted", "u1"], [FIXTURE, "--permitted"],
                [FIXTURE, "--permitted", "u1", "--permitted", "u2", "--blocked", "u5"],
                [FIXTURE, "--permit", "u1", "--blocked", "u5"], ["-h"],
                [FIXTURE, "--permitted", "u9", "--blocked", "u5"],
            ]
            for argv in cases:
                code, out, err = self.run_main(argv)
                self.assertEqual(code, 2, argv)
                self.assertEqual(out, "", argv)
                self.assertTrue(err.startswith("DENY "), argv)
                self.assertEqual(err.count("\n"), 1, argv)
            self.assertIn("DENY unknown_value", self.run_main([bad])[2])
            self.assertIn("DENY usage", self.run_main([])[2])
            self.assertIn("DENY usage", self.run_main(["-h"])[2])
            self.assertIn("DENY usage", self.run_main(["--permit", "u1", FIXTURE])[2])

    def test_subprocess_exit_codes(self):
        ok = subprocess.run([sys.executable, "-B", os.path.join(HERE, "preview_rules.py"), FIXTURE],
                            capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0)
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "bad.json")
            with open(bad, "w", encoding="utf-8") as handle:
                handle.write('{"fixture_version": NaN}')
            res = subprocess.run([sys.executable, "-B", os.path.join(HERE, "preview_rules.py"), bad],
                                 capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertEqual(res.stdout, "")
        self.assertTrue(res.stderr.startswith("DENY non_finite_number"))

    def test_demo_is_deterministic(self):
        runs = [subprocess.run([sys.executable, "-B", os.path.join(HERE, "demo.py")],
                               capture_output=True, text=True, cwd=d)
                for d in (HERE, os.path.dirname(HERE))]
        self.assertEqual([r.returncode for r in runs], [0, 0])
        self.assertEqual(runs[0].stdout, runs[1].stdout)
        self.assertIn("done-when b: weak preview fits 3 rules, verdict AMBIGUOUS\n", runs[0].stdout)
        self.assertIn("done-when c: transfer preview leaves 1 scope(s) where the weak preview leaves 3\n", runs[0].stdout)


if __name__ == "__main__":
    unittest.main()
