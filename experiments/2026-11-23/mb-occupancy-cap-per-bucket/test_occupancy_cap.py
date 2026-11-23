"""unittest suite for occupancy_cap.py.  Run: python3 -B -m unittest"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import unicodedata

import mutants
import occupancy_cap as oc

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
VALID = ("village.json", "more.json")
BAD_CODES = {
    "bad_bucket_cap_above_capacity.json": "cap_above_capacity",
    "bad_bucket_cap_float.json": "not_integer",
    "bad_bucket_cap_zero.json": "out_of_range",
    "bad_bucket_seconds_negative.json": "out_of_range",
    "bad_bucket_seconds_too_big.json": "out_of_range",
    "bad_bucket_seconds_zero.json": "out_of_range",
    "bad_capacity_bool.json": "not_integer",
    "bad_capacity_null.json": "not_integer",
    "bad_capacity_text.json": "not_integer",
    "bad_capacity_too_big.json": "out_of_range",
    "bad_capacity_zero.json": "out_of_range",
    "bad_case_bad_id_digit_first.json": "bad_id",
    "bad_case_bad_id_hyphen.json": "bad_id",
    "bad_case_bad_id_upper.json": "bad_id",
    "bad_case_id_too_long.json": "bad_id",
    "bad_case_label_control.json": "bad_text",
    "bad_case_label_empty.json": "bad_text",
    "bad_case_label_spaces.json": "bad_text",
    "bad_case_label_too_long.json": "bad_text",
    "bad_case_label_zero_width.json": "bad_text",
    "bad_case_missing_capacity.json": "missing_key",
    "bad_case_not_object.json": "bad_shape",
    "bad_case_unknown_key.json": "unknown_key",
    "bad_cases_not_list.json": "bad_shape",
    "bad_deep_nesting.json": "not_json",
    "bad_duplicate_case_id.json": "duplicate_id",
    "bad_duplicate_key.json": "duplicate_key",
    "bad_empty_file.json": "not_json",
    "bad_exponent_t.json": "not_integer",
    "bad_float_score.json": "not_integer",
    "bad_infinity_t.json": "not_json",
    "bad_item_bad_id.json": "bad_id",
    "bad_item_duplicate_id.json": "duplicate_id",
    "bad_item_id_hangul.json": "bad_id",
    "bad_item_id_not_text.json": "bad_id",
    "bad_item_missing_score.json": "missing_key",
    "bad_item_missing_t.json": "missing_key",
    "bad_item_not_object.json": "bad_shape",
    "bad_item_note_bidi.json": "bad_text",
    "bad_item_note_empty.json": "bad_text",
    "bad_item_note_newline.json": "bad_text",
    "bad_item_note_null.json": "bad_text",
    "bad_item_score_bool.json": "not_integer",
    "bad_item_score_negative.json": "out_of_range",
    "bad_item_score_text.json": "not_integer",
    "bad_item_score_too_big.json": "out_of_range",
    "bad_item_t_bool.json": "not_integer",
    "bad_item_t_negative.json": "out_of_range",
    "bad_item_t_text.json": "not_integer",
    "bad_item_t_too_big.json": "out_of_range",
    "bad_item_unknown_key.json": "unknown_key",
    "bad_items_not_list.json": "bad_shape",
    "bad_items_out_of_order.json": "out_of_order",
    "bad_label_not_text.json": "bad_text",
    "bad_missing_cases.json": "missing_key",
    "bad_nan_score.json": "not_json",
    "bad_needs_duplicate.json": "duplicate_id",
    "bad_needs_empty.json": "bad_count",
    "bad_needs_not_list.json": "bad_shape",
    "bad_needs_not_text.json": "bad_id",
    "bad_needs_other_case_item.json": "unknown_need",
    "bad_needs_unknown_item.json": "unknown_need",
    "bad_no_cases.json": "bad_count",
    "bad_no_items.json": "bad_count",
    "bad_no_queries.json": "bad_count",
    "bad_not_json.json": "not_json",
    "bad_not_utf8.json": "bad_encoding",
    "bad_planted_unknown.json": "bad_planted",
    "bad_planted_upper.json": "bad_planted",
    "bad_queries_not_list.json": "bad_shape",
    "bad_query_ask_empty.json": "bad_text",
    "bad_query_bad_id.json": "bad_id",
    "bad_query_duplicate_id.json": "duplicate_id",
    "bad_query_missing_needs.json": "missing_key",
    "bad_query_unknown_key.json": "unknown_key",
    "bad_too_large.json": "too_large",
    "bad_too_many_cases.json": "bad_count",
    "bad_too_many_items.json": "bad_count",
    "bad_too_many_queries.json": "bad_count",
    "bad_top_level_list.json": "bad_shape",
    "bad_truncated.json": "not_json",
    "bad_unknown_root_key.json": "unknown_key",
    "bad_utf16.json": "bad_encoding",
    "bad_version_2.json": "bad_version",
    "bad_version_bool.json": "bad_version",
    "bad_version_text.json": "bad_version",
}


def tool(*args):
    return subprocess.run([sys.executable, "-B", os.path.join(HERE, "occupancy_cap.py")] + list(args),
                          capture_output=True, text=True, timeout=120)


def item(i, t, s):
    return {"id": i, "t": t, "score": s, "note": "n"}


def case(items, capacity, seconds, cap, needs, planted="none"):
    raw = {"id": "c", "label": "c", "planted": planted, "capacity": capacity, "bucket_seconds": seconds,
           "bucket_cap": cap, "items": items, "queries": [{"id": "q", "ask": "q", "needs": needs}]}
    return oc.validate({"fixture_version": 1, "label": "t", "cases": [raw]})["cases"][0]


def ids(memory):
    return [m["id"] for m in memory]


def village():
    return {r["id"]: r for r in oc.run(oc.load_fixture(os.path.join(FIX, "village.json")))["rows"]}


class DoneWhenTests(unittest.TestCase):
    """(a)-(d) from the pack."""

    def test_a_burst_crowds_out_an_earlier_needed_item_under_score_only(self):
        r = village()["festival_burst"]
        weak = r["arms"]["score_only"]
        self.assertTrue(weak["over_cap"])
        self.assertEqual(weak["most_crowded_slots"], 6)
        self.assertEqual(weak["occupancy"], {"2": 6})
        self.assertIn("well_fixed", weak["earlier_lost"])
        self.assertIn("bridge_crack", weak["earlier_lost"])
        self.assertFalse(weak["queries"]["q_well"])

    def test_b_bucket_cap_holds_the_cap_and_the_needed_items(self):
        r = village()["festival_burst"]
        strict = r["arms"]["bucket_cap"]
        self.assertFalse(strict["over_cap"])
        self.assertTrue(all(n <= r["bucket_cap"] for n in strict["occupancy"].values()))
        self.assertEqual(strict["lost"], [])
        self.assertEqual(strict["kept"], ["well_fixed", "seed_swap", "bridge_crack", "fireworks_3", "fireworks_5",
                                          "lost_cat"])
        self.assertTrue(all(strict["queries"].values()))

    def test_c_no_burst_both_arms_hold_what_they_should(self):
        r = village()["quiet_market"]
        self.assertEqual(r["arms"]["score_only"]["lost"], [])
        self.assertEqual(r["arms"]["bucket_cap"]["lost"], [])
        self.assertTrue(r["closed"])

    def test_d_stdlib_only_no_keyed_sampling_no_network(self):
        with open(os.path.join(HERE, "occupancy_cap.py"), encoding="utf-8") as fh:
            src = fh.read()
        imports = sorted({line.split()[1] for line in src.splitlines() if line.startswith(("import ", "from "))})
        self.assertEqual(imports, ["json", "sys", "unicodedata"])
        for word in ("random", "hashlib", "hm" + "ac", "secrets", "socket", "urllib", "subprocess"):
            self.assertNotIn(word, src)

    def test_recency_also_loses_the_well_under_the_burst(self):
        r = village()["festival_burst"]
        self.assertEqual(r["arms"]["recency"]["lost"], ["well_fixed", "bridge_crack"])
        self.assertEqual(r["arms"]["recency"]["occupancy"], {"2": 5, "3": 1})

    def test_need_over_cap_is_a_declared_cost(self):
        r = village()["busy_council"]
        self.assertEqual(r["arms"]["bucket_cap"]["lost"], ["school_hours"])
        self.assertEqual(r["arms"]["score_only"]["lost"], [])
        self.assertTrue(r["closed"])


class ArmTests(unittest.TestCase):
    def test_score_only_evicts_lowest_score_then_oldest_then_id(self):
        c = case([item("a", 0, 5), item("b", 1, 5), item("c", 1, 9), item("d", 2, 5)], 2, 100, 2, ["c"])
        self.assertEqual(ids(oc.score_only(c)), ["c", "d"])
        c = case([item("b", 0, 5), item("a", 0, 5), item("c", 1, 9)], 2, 100, 2, ["c"])
        self.assertEqual(ids(oc.score_only(c)), ["b", "c"])

    def test_score_only_may_drop_the_newcomer(self):
        c = case([item("a", 0, 9), item("b", 1, 8), item("c", 2, 1)], 2, 100, 2, ["a"])
        self.assertEqual(ids(oc.score_only(c)), ["a", "b"])

    def test_recency_is_fifo(self):
        c = case([item("a", 0, 99), item("b", 1, 1), item("c", 2, 1)], 2, 100, 2, ["b"])
        self.assertEqual(ids(oc.recency(c)), ["b", "c"])

    def test_bucket_cap_evicts_lowest_in_the_same_bucket(self):
        c = case([item("a", 0, 1), item("b", 10, 50), item("c", 11, 40), item("d", 12, 60)], 9, 10, 2, ["a"])
        self.assertEqual(ids(oc.bucket_cap(c)), ["a", "b", "d"])

    def test_bucket_cap_evicts_the_newcomer_when_it_ranks_lowest(self):
        c = case([item("a", 10, 50), item("b", 11, 40), item("c", 12, 10)], 9, 10, 2, ["a"])
        self.assertEqual(ids(oc.bucket_cap(c)), ["a", "b"])

    def test_bucket_boundary_is_floor_division(self):
        c = case([item("a", 9, 1), item("b", 10, 5), item("c", 19, 6), item("d", 20, 7)], 9, 10, 1, ["a"])
        self.assertEqual(ids(oc.bucket_cap(c)), ["a", "c", "d"])
        self.assertEqual([it["bucket"] for it in c["items"]], [0, 1, 1, 2])

    def test_overflow_takes_from_the_most_crowded_bucket(self):
        # bucket 0 holds two high scores, bucket 1 one low score: the crowded bucket gives up its lowest.
        c = case([item("a", 0, 80), item("b", 1, 70), item("c", 10, 5), item("d", 20, 6)], 3, 10, 2, ["c"])
        self.assertEqual(ids(oc.bucket_cap(c)), ["a", "c", "d"])
        self.assertEqual(ids(oc.score_only(c)), ["a", "b", "d"])

    def test_overflow_tie_between_crowded_buckets_uses_rank(self):
        c = case([item("a", 0, 30), item("b", 1, 31), item("c", 10, 20), item("d", 11, 40), item("e", 20, 1)],
                 4, 10, 2, ["e"])
        self.assertEqual(ids(oc.bucket_cap(c)), ["a", "b", "d", "e"])
        c = case([item("a", 0, 20), item("b", 1, 31), item("c", 10, 20), item("d", 11, 40), item("e", 20, 1)],
                 4, 10, 2, ["e"])
        self.assertEqual(ids(oc.bucket_cap(c)), ["b", "c", "d", "e"])

    def test_cap_equal_to_capacity_in_one_bucket_matches_score_only(self):
        items = [item("e%d" % n, n, (n * 37) % 11) for n in range(12)]
        c = case(items, 4, 1000, 4, ["e0"])
        self.assertEqual(ids(oc.bucket_cap(c)), ids(oc.score_only(c)))

    def test_nothing_evicted_when_everything_fits(self):
        c = case([item("a", 0, 1), item("b", 10, 1), item("c", 20, 1)], 3, 10, 1, ["a"])
        for name in oc.ARMS:
            self.assertEqual(ids(oc.ARM_FUNCS[name](c)), ["a", "b", "c"])

    def test_invariants_on_generated_streams(self):
        state = 7
        for trial in range(60):
            items, t = [], 0
            for n in range(25):
                state = (state * 1103515245 + 12345) % 2147483648
                t += state % 7
                items.append(item("e%d" % n, t, (state >> 8) % 13))
            capacity, cap = 3 + trial % 5, 1 + trial % 3
            c = case(items, capacity, 1 + trial % 9, min(cap, capacity), ["e0"])
            for name in oc.ARMS:
                mem = oc.ARM_FUNCS[name](c)
                if name != "bucket_cap":
                    self.assertEqual(len(mem), min(capacity, len(items)))
                self.assertLessEqual(len(mem), capacity)
                self.assertEqual(ids(mem), [i["id"] for i in c["items"] if i["id"] in ids(mem)])
            occ = oc.measure(c, oc.bucket_cap(c))["occupancy"]
            self.assertTrue(all(v <= c["bucket_cap"] for v in occ.values()), (trial, occ))
            # a full bucket_cap memory is either at capacity or every seen bucket is at its cap or exhausted
            mem = oc.bucket_cap(c)
            if len(mem) < capacity:
                for b in {i["bucket"] for i in c["items"]}:
                    seen = sum(1 for i in c["items"] if i["bucket"] == b)
                    self.assertEqual(occ.get(str(b), 0), min(seen, c["bucket_cap"]), (trial, b))


class JudgeTests(unittest.TestCase):
    def _row(self, c):
        return oc.run({"label": "t", "cases": [c]})

    def test_burst_that_hurts_nothing_is_open(self):
        c = case([item("a", 0, 50), item("b", 10, 1), item("c", 11, 2)], 3, 10, 1, ["a"], planted="burst")
        res = self._row(c)
        self.assertFalse(res["rows"][0]["closed"])
        self.assertEqual(oc.gate(res), "FAIL")

    def test_burst_that_only_hurts_later_items_is_open(self):
        c = case([item("b1", 0, 90), item("b2", 1, 91), item("late", 20, 1)], 2, 10, 1, ["late"], planted="burst")
        res = self._row(c)
        self.assertEqual(res["rows"][0]["arms"]["score_only"]["lost"], ["late"])
        self.assertEqual(res["rows"][0]["arms"]["score_only"]["earlier_lost"], [])
        self.assertFalse(res["rows"][0]["closed"])

    def test_none_with_a_loss_is_open(self):
        c = case([item("a", 0, 1), item("b", 10, 5), item("c", 20, 6)], 2, 10, 1, ["a"])
        self.assertFalse(self._row(c)["rows"][0]["closed"])

    def test_need_over_cap_without_loss_is_open(self):
        c = case([item("a", 0, 1), item("b", 10, 5)], 2, 10, 1, ["a"], planted="need_over_cap")
        self.assertFalse(self._row(c)["rows"][0]["closed"])

    def test_strict_breaking_its_cap_is_open(self):
        c = case([item("a", 0, 1), item("b", 1, 2), item("c", 10, 5)], 3, 10, 1, ["a"])
        arms = {name: oc.measure(c, oc.ARM_FUNCS[name](c)) for name in oc.ARMS}
        arms["bucket_cap"] = oc.measure(c, c["items"])
        self.assertEqual(oc.judge(c, arms), (False, "bucket_cap broke its own cap"))
        arms["bucket_cap"] = oc.measure(c, c["items"][1:])
        arms["bucket_cap"]["kept"] = ["a", "b", "c", "x"]
        arms["bucket_cap"]["over_cap"] = False
        self.assertFalse(oc.judge(c, arms)[0])

    def test_arm_gates_on_the_village(self):
        res = oc.run(oc.load_fixture(os.path.join(FIX, "village.json")))
        self.assertEqual(res["arm_gates"], {"score_only": "FAIL", "recency": "FAIL", "bucket_cap": "PASS"})
        self.assertEqual((res["closed"], res["total"], res["bursts"]), (3, 3, 1))
        self.assertEqual(res["weak_failures"], {"score_only": 1, "recency": 1})
        self.assertEqual(res["strict_within_cap"], 3)

    def test_arm_gate_ignores_need_over_cap_losses(self):
        rows = [{"planted": "need_over_cap", "arms": {"bucket_cap": {"over_cap": False, "lost": ["x"]}}}]
        self.assertEqual(oc.arm_gate(rows, "bucket_cap"), "PASS")
        rows[0]["planted"] = "none"
        self.assertEqual(oc.arm_gate(rows, "bucket_cap"), "FAIL")
        rows = [{"planted": "burst", "arms": {"bucket_cap": {"over_cap": True, "lost": []}}}]
        self.assertEqual(oc.arm_gate(rows, "bucket_cap"), "FAIL")

    def test_more_fixture(self):
        res = oc.run(oc.load_fixture(os.path.join(FIX, "more.json")))
        rows = {r["id"]: r for r in res["rows"]}
        self.assertEqual((res["closed"], res["total"]), (3, 3))
        self.assertEqual(rows["two_bursts"]["arms"]["bucket_cap"]["kept"], ["well_water", "bell_3", "parade_2",
                                                                            "ox_sick"])
        self.assertEqual(rows["two_bursts"]["arms"]["score_only"]["lost"], ["well_water", "ox_sick"])
        self.assertEqual(rows["equal_scores"]["arms"]["bucket_cap"]["kept"], ["b_note", "c_note", "d_note"])
        self.assertEqual(rows["hangul_burst"]["arms"]["score_only"]["lost"], ["well_fixed"])
        self.assertEqual(res["weak_failures"], {"score_only": 2, "recency": 2})


class FixtureTests(unittest.TestCase):
    def test_bad_fixture_list_matches_the_folder(self):
        on_disk = sorted(f for f in os.listdir(FIX) if f.startswith("bad_"))
        self.assertEqual(on_disk, sorted(BAD_CODES))
        self.assertGreaterEqual(len(on_disk), 80)

    def test_every_bad_fixture_is_deny_with_its_code(self):
        for name, code in sorted(BAD_CODES.items()):
            with self.subTest(name=name):
                p = tool(os.path.join(FIX, name))
                self.assertEqual(p.returncode, 2)
                self.assertEqual(p.stdout, "")
                lines = p.stderr.splitlines()
                self.assertEqual(len(lines), 1)
                self.assertTrue(lines[0].startswith("ERROR %s: " % code), lines[0])
                self.assertTrue(lines[0].endswith("(on_expiry=DENY)"))

    def test_bad_fixtures_raise_in_process(self):
        for name, code in sorted(BAD_CODES.items()):
            with self.subTest(name=name):
                with self.assertRaises(oc.CapError) as ctx:
                    oc.load_fixture(os.path.join(FIX, name))
                self.assertEqual(ctx.exception.code, code)

    def test_valid_fixtures_exit_zero(self):
        for name in VALID:
            p = tool(os.path.join(FIX, name))
            self.assertEqual((p.returncode, p.stderr), (0, ""))
            self.assertIn("closed: 3 / 3 on the declared gate", p.stdout)
            self.assertIn("gate: PASS", p.stdout)

    def test_missing_and_folder_and_usage_are_deny(self):
        for args in ([os.path.join(FIX, "absent.json")], [FIX], [], ["a", "b"], ["--json"]):
            p = tool(*args)
            self.assertEqual(p.returncode, 2, args)
            self.assertEqual(p.stdout, "")
            self.assertEqual(len(p.stderr.splitlines()), 1)
            self.assertTrue(p.stderr.startswith("ERROR"))

    def test_json_mode(self):
        p = tool("--json", os.path.join(FIX, "village.json"))
        self.assertEqual(p.returncode, 0)
        data = json.loads(p.stdout)
        self.assertEqual(data["closed"], 3)
        self.assertEqual(data["on_expiry"], "DENY")

    def test_open_gate_exits_one(self):
        with open(os.path.join(FIX, "village.json"), encoding="utf-8") as fh:
            raw = json.load(fh)
        raw["cases"][1]["planted"] = "burst"
        res = oc.run(oc.validate(raw))
        self.assertEqual(oc.gate(res), "FAIL")
        self.assertIn("gate: FAIL", oc.report(res))
        self.assertIn("verdict: OPEN", oc.report(res))
        with tempfile.TemporaryDirectory() as work:
            path = os.path.join(work, "open.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(raw, fh)
            p = tool(path)
        self.assertEqual((p.returncode, p.stderr), (1, ""))
        self.assertIn("closed: 2 / 3 on the declared gate", p.stdout)

    def test_korean_text_is_nfc(self):
        fx = oc.load_fixture(os.path.join(FIX, "more.json"))
        label = fx["cases"][2]["label"]
        self.assertTrue(unicodedata.is_normalized("NFC", label))
        raw = json.load(open(os.path.join(FIX, "more.json"), encoding="utf-8"))
        raw["cases"][2]["label"] = unicodedata.normalize("NFD", raw["cases"][2]["label"])
        self.assertEqual(oc.validate(raw)["cases"][2]["label"], label)

    def test_equal_t_is_in_order(self):
        c = case([item("a", 5, 1), item("b", 5, 2)], 2, 10, 2, ["a"])
        self.assertEqual([i["t"] for i in c["items"]], [5, 5])

    def test_caps_declare_deny(self):
        self.assertTrue(all(v["on_expiry"] == "DENY" for v in oc.CAPS.values()))
        self.assertEqual(oc.ON_EXPIRY, "DENY")


class DemoTests(unittest.TestCase):
    def test_demo_is_deterministic(self):
        runs = [subprocess.run([sys.executable, "-B", os.path.join(HERE, "demo.py")], capture_output=True,
                               timeout=120) for _ in range(2)]
        self.assertEqual(runs[0].returncode, 0)
        self.assertEqual(runs[0].stdout, runs[1].stdout)
        text = runs[0].stdout.decode("utf-8")
        self.assertEqual(text.count("closed: 3 / 3 on the declared gate"), 2)
        self.assertIn("| score_only (weak) | fireworks_1 fireworks_2 fireworks_3 fireworks_4 fireworks_5 "
                      "fireworks_6 | b2:6 | well_fixed bridge_crack lost_cat |", text)
        self.assertIn("| bucket_cap (strict) | well_fixed seed_swap bridge_crack fireworks_3 fireworks_5 lost_cat "
                      "| b0:2 b1:1 b2:2 b3:1 | none |", text)
        self.assertIn("arm bucket_cap (strict): PASS", text)
        self.assertIn("arm score_only (weak): FAIL", text)
        self.assertIn("- q_well \"Who repaired the well?\" needs well_fixed: score_only MISS, recency MISS, "
                      "bucket_cap HIT", text)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            self.ev = json.load(fh)

    def test_measured_numbers_match_a_fresh_run(self):
        for name, key in (("village.json", "village"), ("more.json", "more")):
            res = oc.run(oc.load_fixture(os.path.join(FIX, name)))
            m = self.ev["measured"][key]
            self.assertEqual((m["closed"], m["total"]), (res["closed"], res["total"]))
            self.assertEqual(m["arm_gates"], res["arm_gates"])
            self.assertEqual(m["weak_failures_in_planted_bursts"], res["weak_failures"])
            self.assertEqual(m["planted_bursts"], res["bursts"])

    def test_unmeasured_and_expiry(self):
        self.assertEqual(self.ev["on_expiry"], "DENY")
        self.assertTrue(self.ev["on_unmeasured"])
        self.assertTrue(all(u["status"] == "UNVERIFIED" for u in self.ev["on_unmeasured"]))
        self.assertEqual(self.ev["timeouts"]["mutants"], dict(mutants.TIMEOUT, rule=self.ev["timeouts"]["mutants"]["rule"]))
        self.assertEqual(self.ev["source"]["citation_title"],
                         "KeyMem: Temporal Occupancy Control for Robust Streaming VideoLLM Memory")
        self.assertEqual(self.ev["source"]["licence"], "CC BY 4.0")
        self.assertFalse(self.ev["key_sampler_implemented"])


class DocumentTests(unittest.TestCase):
    def test_readme_credit_and_limits(self):
        with open(os.path.join(HERE, "README.md"), encoding="utf-8") as fh:
            text = fh.read()
        for phrase in ("KeyMem: Temporal Occupancy Control for Robust Streaming VideoLLM Memory", "CC BY 4.0",
                       "https://arxiv.org/abs/2611.25649", "not a reproduction", "secret-key sampler",
                       "python3 -B -m unittest", "on_expiry"):
            self.assertIn(phrase, text)


class HygieneTests(unittest.TestCase):
    def files(self):
        for root, dirs, names in os.walk(HERE):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for n in names:
                yield os.path.join(root, n)

    def test_no_banned_substrings_or_paths(self):
        banned = ["al" + "low", "ke" + "ep", "cloud" + "agent", "smi" + "th", "chec" + "ker",
                  "/work" + "space", "/t" + "mp", "/ho" + "me"]
        for path in self.files():
            with open(path, "rb") as fh:
                text = fh.read().decode("utf-8", "replace").lower()
            for word in banned:
                self.assertNotIn(word, text, (path, word))


class MutantsHarnessTests(unittest.TestCase):
    def test_timeout_is_deny_and_never_a_kill(self):
        self.assertEqual(mutants.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})
        self.assertEqual(mutants.outcome(None), "TIMEOUT")
        self.assertFalse(mutants.is_killed("TIMEOUT"))
        self.assertEqual(mutants.outcome(1), "KILLED")
        self.assertEqual(mutants.outcome(0), "SURVIVED")

    def test_score_counts_only_kills(self):
        fake = {"a": "KILLED", "b": "TIMEOUT", "c": "SURVIVED"}
        killed, results = mutants.score(["a", "b", "c"], fake.get)
        self.assertEqual(killed, 1)
        self.assertIn("timeouts: 1", mutants.summary_line(killed, 3, results))
        self.assertIn("killed: 1/3", mutants.summary_line(killed, 3, results))

    @unittest.skipIf(os.environ.get("OCCUPANCY_MUTANT_RUN") == "1",
                     "reads the mutated source; mutants.py checks every fragment itself before the run")
    def test_every_fragment_occurs_once(self):
        with open(os.path.join(HERE, "occupancy_cap.py"), encoding="utf-8") as fh:
            src = fh.read()
        names = [m[0] for m in mutants.MUTANTS]
        self.assertEqual(len(names), len(set(names)))
        for name, fragment, replacement in mutants.MUTANTS:
            self.assertEqual(src.count(fragment), 1, name)
            self.assertNotEqual(fragment, replacement)


if __name__ == "__main__":
    unittest.main()


class BehaviourKillTests(unittest.TestCase):
    """Behavioural tests for rules the suite otherwise checked only through the fragment-count test."""

    def test_score_only_tie_break_uses_age_before_id(self):
        c = case([item("z", 0, 5), item("a", 1, 5), item("m", 2, 9)], 2, 100, 2, ["m"])
        self.assertEqual(ids(oc.score_only(c)), ["a", "m"])

    def test_earlier_lost_excludes_the_crowded_bucket_itself(self):
        c = case([item("e", 0, 50), item("n", 10, 1), item("f1", 11, 90), item("f2", 12, 91)], 3, 10, 1, ["n"],
                 planted="burst")
        m = oc.measure(c, [x for x in c["items"] if x["id"] != "n"])
        self.assertEqual(m["most_crowded_bucket"], 1)
        self.assertEqual(m["lost"], ["n"])
        self.assertEqual(m["earlier_lost"], [])

    def test_burst_where_bucket_cap_loses_a_needed_item_is_open(self):
        c = case([item("e", 0, 1), item("f1", 10, 90), item("f2", 11, 91), item("f3", 12, 92), item("f0", 13, 5)],
                 3, 10, 1, ["e", "f0"], planted="burst")
        arms = {name: oc.measure(c, oc.ARM_FUNCS[name](c)) for name in oc.ARMS}
        self.assertTrue(arms["score_only"]["over_cap"])
        self.assertEqual(arms["score_only"]["earlier_lost"], ["e"])
        self.assertEqual(arms["bucket_cap"]["lost"], ["f0"])
        self.assertEqual(oc.judge(c, arms), (False, "bucket_cap lost a needed item under a burst"))

    def test_none_case_where_only_score_only_loses_is_open(self):
        c = case([item("a", 0, 1), item("b", 10, 5), item("c", 11, 6)], 2, 10, 2, ["a"])
        arms = {name: oc.measure(c, oc.ARM_FUNCS[name](c)) for name in oc.ARMS}
        self.assertEqual(arms["bucket_cap"]["lost"], [])
        self.assertEqual(arms["score_only"]["lost"], ["a"])
        self.assertEqual(oc.judge(c, arms), (False, "a needed item was lost with no burst planted"))

    def test_strict_over_capacity_within_cap_is_open(self):
        c = case([item("a", 0, 1), item("b", 10, 2), item("c", 20, 3)], 2, 10, 1, ["a"])
        arms = {name: oc.measure(c, c["items"]) for name in oc.ARMS}
        self.assertFalse(arms["bucket_cap"]["over_cap"])
        self.assertEqual(oc.judge(c, arms), (False, "bucket_cap broke its own cap"))
