"""Tests for play_craft. Run: python3 -B -m unittest discover -s . -p 'test_*.py'"""

import copy
import hashlib
import inspect
import io
import json
import os
import re
import subprocess
import sys
import unicodedata
import unittest
from fractions import Fraction

import play_craft as pc

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
PY = sys.executable

# every malformed fixture and the one error code it must give
BAD_CODES = {
    "bad_bigint_309_digits": "bad_value",
    "bad_bigint_5000_digits": "not_json",
    "bad_bom_prefix": "not_json",
    "bad_bool_cost": "wrong_type",
    "bad_deep_nesting": "not_json",
    "bad_deep_nesting_200k": "too_large",
    "bad_deep_object_nesting": "not_json",
    "bad_deny_episode_held": "DENY episode_held",
    "bad_deny_knob_out_of_range": "DENY knob_out_of_range",
    "bad_deny_no_report_held": "DENY episode_held",
    "bad_deny_target_edited": "DENY target_not_declared",
    "bad_deny_undeclared_knob": "DENY knob_undeclared",
    "bad_duplicate_id_nfc_nfd_knobs": "duplicate_name",
    "bad_duplicate_id_nfc_nfd_levels": "duplicate_name",
    "bad_duplicate_key": "duplicate_key",
    "bad_duplicate_key_nested": "duplicate_key",
    "bad_empty_file": "not_json",
    "bad_episodes_over_cap": "bad_value",
    "bad_episodes_two": "bad_value",
    "bad_episodes_zero": "bad_value",
    "bad_exponent_overflow": "wrong_type",
    "bad_float_cost": "wrong_type",
    "bad_four_levels": "bad_levels",
    "bad_huge_cost": "bad_value",
    "bad_id_bidi": "bad_id",
    "bad_id_braille_blank": "bad_id",
    "bad_id_c1": "bad_id",
    "bad_id_choseong_filler": "bad_id",
    "bad_id_compat_jamo": "bad_id",
    "bad_id_dash": "bad_id",
    "bad_id_dot": "bad_id",
    "bad_id_empty": "bad_id",
    "bad_id_esc": "bad_id",
    "bad_id_halfwidth_filler": "bad_id",
    "bad_id_hangul_filler": "bad_id",
    "bad_id_ideographic_space": "bad_id",
    "bad_id_latin1": "bad_id",
    "bad_id_line_separator": "bad_id",
    "bad_id_long": "bad_id",
    "bad_id_nbsp": "bad_id",
    "bad_id_newline": "bad_id",
    "bad_id_private_use": "bad_id",
    "bad_id_space": "bad_id",
    "bad_id_surrogate": "bad_id",
    "bad_id_zero_width": "bad_id",
    "bad_infinity": "bad_number",
    "bad_invalid_utf8": "bad_encoding",
    "bad_knob_bool_min": "wrong_type",
    "bad_knob_float_max": "wrong_type",
    "bad_knob_id_space": "bad_id",
    "bad_knob_id_surrogate": "bad_id",
    "bad_knob_id_zero_width": "bad_id",
    "bad_knob_initial_above_max": "bad_knob",
    "bad_knob_initial_below_min": "bad_knob",
    "bad_knob_label_surrogate": "bad_text",
    "bad_knob_max_off_grid": "bad_knob",
    "bad_knob_min_above_max": "bad_knob",
    "bad_knob_negative_min": "bad_value",
    "bad_knob_off_grid_initial": "bad_knob",
    "bad_knob_role_unknown": "bad_roles",
    "bad_knob_roles_same": "bad_roles",
    "bad_knob_step_negative": "bad_value",
    "bad_knob_step_zero": "bad_value",
    "bad_label_bidi": "bad_text",
    "bad_label_bom": "bad_text",
    "bad_label_braille_blank": "bad_text",
    "bad_label_c1": "bad_text",
    "bad_label_choseong_filler": "bad_text",
    "bad_label_empty": "wrong_type",
    "bad_label_esc": "bad_text",
    "bad_label_hangul_filler": "bad_text",
    "bad_label_ideographic_space": "bad_text",
    "bad_label_leading_space": "bad_text",
    "bad_label_line_separator": "bad_text",
    "bad_label_long": "wrong_type",
    "bad_label_nbsp": "bad_text",
    "bad_label_newline": "bad_text",
    "bad_label_number": "wrong_type",
    "bad_label_private_use": "bad_text",
    "bad_label_surrogate": "bad_text",
    "bad_label_tab": "bad_text",
    "bad_label_trailing_space": "bad_text",
    "bad_label_unassigned": "bad_text",
    "bad_label_zero_width": "bad_text",
    "bad_level_label_zero_width": "bad_text",
    "bad_level_patience_bool": "wrong_type",
    "bad_level_patience_negative": "bad_value",
    "bad_level_weight_huge": "bad_value",
    "bad_missing_game_key": "missing_key",
    "bad_missing_on_expiry": "missing_key",
    "bad_nan": "bad_number",
    "bad_neg_infinity": "bad_number",
    "bad_negative_cost": "bad_value",
    "bad_no_report_bool": "wrong_type",
    "bad_no_report_duplicate": "duplicate_name",
    "bad_no_report_not_list": "wrong_type",
    "bad_no_report_out_of_range": "bad_value",
    "bad_no_report_zero": "bad_value",
    "bad_not_json": "not_json",
    "bad_not_object": "wrong_type",
    "bad_on_expiry_grant": "bad_on_expiry",
    "bad_on_expiry_lowercase": "bad_on_expiry",
    "bad_on_expiry_null": "bad_on_expiry",
    "bad_on_expiry_permit": "bad_on_expiry",
    "bad_on_expiry_safe_fallback": "bad_on_expiry",
    "bad_one_knob": "bad_knob",
    "bad_oversize": "too_large",
    "bad_rounds_over_cap": "bad_value",
    "bad_rounds_zero": "bad_value",
    "bad_single_quotes": "not_json",
    "bad_step_cap_negative": "bad_value",
    "bad_step_cap_zero": "bad_value",
    "bad_string_cost": "wrong_type",
    "bad_target_band_bool": "wrong_type",
    "bad_target_band_inverted": "bad_band",
    "bad_target_band_over_episodes": "bad_value",
    "bad_target_band_zero": "bad_value",
    "bad_target_missing": "missing_key",
    "bad_target_null": "wrong_type",
    "bad_target_unknown_key": "unknown_key",
    "bad_target_unknown_level": "unknown_level",
    "bad_three_knobs": "bad_knob",
    "bad_trailing_comma": "not_json",
    "bad_trailing_garbage": "not_json",
    "bad_two_levels": "bad_levels",
    "bad_unknown_crafter": "unknown_crafter",
    "bad_unknown_key_game": "unknown_key",
    "bad_unknown_key_top": "unknown_key",
    "bad_utf16_bom": "bad_encoding",
    "bad_version": "bad_version",
    "bad_version_bool": "bad_version",
    "bad_zero_cost": "bad_value",
}

VALID_FIXTURES = ("main", "hold_capped", "hold_no_report", "escalate_capped", "korean", "korean_nfd",
                  "edge_knob_bounds", "edge_locked_knob", "edge_band_full_range", "edge_single_point_band",
                  "edge_step_two")

# banned words are built from pieces so that this file does not hold them itself
BANNED = ["al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er"]
OTHER_BANNED = ["ds" + "h", "fei" + "shu", "sql" + "ite", "dae" + "mon", "hoo" + "ks", "hm" + "ac",
                "hash" + "-chain", "vot" + "ing", "ensem" + "ble", "sla" + "ck", "grok" + "ki"]
BANNED_PATHS = ["/work" + "space", "/t" + "mp", "/ho" + "me"]
TITLE = "PlayCraft: Designing Engaging Games from Agent Play Experience"
LICENCE = "arXiv nonexclusive-distrib 1.0; method only; no code listed; none copied"


def fx_load(name="main"):
    return pc.load_fixture(os.path.join(FIXTURES, name + ".json"))


def raw_main():
    with open(os.path.join(FIXTURES, "main.json"), "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def read(name):
    with open(os.path.join(HERE, name), "rb") as fh:
        return fh.read().decode("utf-8")


def cli(*args):
    p = subprocess.run([PY, "-B", os.path.join(HERE, "play_craft.py")] + list(args), capture_output=True)
    return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


def rep(level, episode, path, outcome):
    return {"level": level, "episode": episode, "decisions": [path], "outcome": outcome,
            "switched": False, "steps": 1, "progress_num": 1, "progress_den": 1, "capped": False}


def view_for(fx, reports, params=None, target=None):
    return pc.make_view(reports, fx["knobs"], params or pc.initial_params(fx), target or fx["target"])


class WithCrafter:
    """Context manager that registers a crafter under a name and removes it again."""

    def __init__(self, name, fn):
        self.name, self.fn = name, fn

    def __enter__(self):
        pc.CRAFTERS[self.name] = self.fn

    def __exit__(self, *exc):
        del pc.CRAFTERS[self.name]


# ------------------------------------------------------------------ the game and its players

class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.fx = fx_load()
        self.levels = {lv["id"]: lv for lv in self.fx["levels"]}

    def test_three_declared_levels_differ_only_in_integer_thresholds(self):
        self.assertEqual([lv["id"] for lv in self.fx["levels"]], ["novice", "skilled", "expert"])
        for lv in self.fx["levels"]:
            self.assertEqual(sorted(lv), ["id", "label", "patience", "sign_weight"])
            self.assertIs(type(lv["patience"]), int)
            self.assertIs(type(lv["sign_weight"]), int)
        patience = [lv["patience"] for lv in self.fx["levels"]]
        self.assertEqual(patience, sorted(patience, reverse=True))
        self.assertEqual(len(set(patience)), 3)

    def test_effective_patience(self):
        novice = self.levels["novice"]
        self.assertEqual([pc.effective_patience(novice, c) for c in range(5)], [4, 3, 2, 1, 0])
        self.assertEqual(pc.effective_patience({"patience": 1, "sign_weight": 2}, 3), 0)

    def test_choose_path_switches_when_failures_reach_patience(self):
        novice = self.levels["novice"]
        self.assertEqual(pc.choose_path(novice, 0, {"long_fails": 3}), "long")
        self.assertEqual(pc.choose_path(novice, 0, {"long_fails": 4}), "short")
        self.assertEqual(pc.choose_path(novice, 1, {"long_fails": 3}), "short")
        self.assertEqual(pc.choose_path(novice, 4, {"long_fails": 0}), "short")
        self.assertEqual(pc.choose_path(novice, 3, {"long_fails": 0}), "long")

    def test_episode_arithmetic(self):
        fx, novice = self.fx, self.levels["novice"]
        mem = pc.fresh_memory()
        rec = pc.play_episode(fx, novice, {"signpost": 0, "budget": 3}, mem, 1)
        self.assertEqual(rec["held"], None)
        r = rec["report"]
        self.assertEqual((r["outcome"], r["steps"], r["progress_num"], r["progress_den"], r["capped"]),
                         ("fail", 3, 3, 9, False))
        self.assertEqual(r["decisions"], ["long"])
        self.assertEqual(mem, {"long_fails": 1})
        rec = pc.play_episode(fx, novice, {"signpost": 0, "budget": 9}, pc.fresh_memory(), 1)
        self.assertEqual((rec["report"]["outcome"], rec["report"]["steps"]), ("clear", 9))
        rec = pc.play_episode(fx, novice, {"signpost": 3, "budget": 4}, {"long_fails": 1}, 2)
        self.assertEqual((rec["report"]["decisions"], rec["report"]["outcome"], rec["report"]["steps"]),
                         (["short"], "clear", 4))
        self.assertTrue(rec["report"]["switched"])
        rec = pc.play_episode(fx, novice, {"signpost": 4, "budget": 4}, pc.fresh_memory(), 1)
        self.assertEqual((rec["report"]["decisions"], rec["report"]["outcome"]), (["short"], "clear"))
        self.assertFalse(rec["report"]["switched"])

    def test_switched_flag_needs_an_earlier_long_failure(self):
        mem = {"long_fails": 4}
        rec = pc.play_episode(self.fx, self.levels["novice"], {"signpost": 0, "budget": 3}, mem, 5)
        self.assertTrue(rec["report"]["switched"])
        self.assertEqual(mem, {"long_fails": 4})

    def test_only_a_long_failure_adds_to_memory(self):
        mem = {"long_fails": 4}
        rec = pc.play_episode(self.fx, self.levels["novice"], {"signpost": 0, "budget": 3}, mem, 5)
        self.assertEqual((rec["report"]["decisions"], rec["report"]["outcome"]), (["short"], "fail"))
        self.assertEqual(mem["long_fails"], 4)

    def test_players_are_pure_functions(self):
        for level in self.fx["levels"]:
            a = pc.play_session(self.fx, level, {"signpost": 1, "budget": 4}, pc.fresh_memory(), 6)
            b = pc.play_session(self.fx, level, {"signpost": 1, "budget": 4}, pc.fresh_memory(), 6)
            self.assertEqual(a, b)

    def test_levels_order_by_first_clear(self):
        ev = pc.evaluate(self.fx, {"signpost": 1, "budget": 4})
        firsts = [ev["levels"][k]["first_clear"] for k in ("novice", "skilled", "expert")]
        self.assertEqual(firsts, [4, 2, 1])

    def test_step_cap_makes_a_capped_held_record(self):
        fx = fx_load("hold_capped")
        rec = pc.play_episode(fx, fx["levels"][0], {"signpost": 0, "budget": 3}, pc.fresh_memory(), 1)
        self.assertEqual(rec["held"], "step_cap")
        self.assertEqual(rec["report"]["outcome"], "capped")
        self.assertTrue(rec["report"]["capped"])

    def test_no_report_episode_has_no_report(self):
        fx = fx_load("hold_no_report")
        recs = pc.play_session(fx, fx["levels"][0], {"signpost": 0, "budget": 3}, pc.fresh_memory(), 3)
        self.assertEqual([r["held"] for r in recs], [None, "no_report", None])
        self.assertIsNone(recs[1]["report"])

    def test_cost_and_budget_are_integers_throughout(self):
        for level in self.fx["levels"]:
            for r in pc.play_session(self.fx, level, {"signpost": 1, "budget": 4}, pc.fresh_memory(), 6):
                for k in ("episode", "steps", "progress_num", "progress_den"):
                    self.assertIs(type(r["report"][k]), int)


# ------------------------------------------------------------------ metrics

class MetricTests(unittest.TestCase):
    def test_thirds_gain_and_slope_are_exact(self):
        s = pc._stats([0, 0, 0, 1, 1, 1], 6)
        self.assertEqual(s["first_third"], Fraction(0))
        self.assertEqual(s["last_third"], Fraction(1))
        self.assertEqual(s["gain"], Fraction(1))
        self.assertEqual(s["slope"], Fraction(9, 35))
        self.assertEqual(s["curve"], [Fraction(0), Fraction(0), Fraction(0), Fraction(1, 4), Fraction(2, 5), Fraction(1, 2)])

    def test_flat_curves_have_zero_slope_and_gain(self):
        for clears in ([1] * 6, [0] * 6):
            s = pc._stats(clears, 6)
            self.assertEqual((s["gain"], s["slope"]), (Fraction(0), Fraction(0)))

    def test_falling_curve_is_negative(self):
        s = pc._stats([1, 1, 0, 0, 0, 0], 6)
        self.assertEqual(s["gain"], Fraction(-1))
        self.assertLess(s["slope"], 0)

    def test_slope_matches_an_independent_least_squares(self):
        for clears in ([0, 1, 0, 1, 1, 1], [1, 0, 0, 1, 0, 1, 1], [0, 0, 1, 0, 0, 0, 1, 1, 1]):
            n = len(clears)
            mx = Fraction(sum(range(1, n + 1)), n)
            my = Fraction(sum(clears), n)
            num = sum((x - mx) * (y - my) for x, y in zip(range(1, n + 1), clears))
            den = sum((x - mx) ** 2 for x in range(1, n + 1))
            self.assertEqual(pc._stats(clears, n)["slope"], num / den)

    def test_third_uses_floor_division_and_at_least_one(self):
        s = pc._stats([0, 0, 1, 1, 1, 1, 1], 7)
        self.assertEqual((s["first_third"], s["last_third"]), (Fraction(0), Fraction(1)))
        s = pc._stats([0, 1, 1, 1, 1, 1, 0], 7)
        self.assertEqual((s["first_third"], s["last_third"]), (Fraction(1, 2), Fraction(1, 2)))
        s = pc._stats([1, 0, 0], 3)
        self.assertEqual((s["first_third"], s["last_third"]), (Fraction(1), Fraction(0)))

    def test_all_metrics_are_fractions(self):
        s = pc._stats([0, 1, 1, 0, 1, 1], 6)
        for key in ("gain", "slope", "first_third", "last_third"):
            self.assertIs(type(s[key]), Fraction)
        for c in s["curve"]:
            self.assertIs(type(c), Fraction)

    def test_band_verdict_edges(self):
        band = {"lo": 3, "hi": 4}
        self.assertEqual([pc.band_verdict(f, band) for f in (None, 1, 2, 3, 4, 5, 6)],
                         ["too_hard", "too_easy", "too_easy", "in_band", "in_band", "too_hard", "too_hard"])
        self.assertEqual(pc.band_verdict(4, {"lo": 4, "hi": 4}), "in_band")

    def test_first_clear(self):
        self.assertIsNone(pc.first_clear([]))
        self.assertEqual(pc.first_clear([rep("a", 1, "long", "fail"), rep("a", 2, "short", "clear"),
                                         rep("a", 3, "short", "clear")]), 2)

    def test_reported_numbers_for_main(self):
        ev = pc.evaluate(fx_load(), {"signpost": 1, "budget": 4})
        self.assertEqual(ev["levels"]["novice"]["curve"][3], Fraction(1, 4))
        self.assertEqual((ev["levels"]["novice"]["gain"], ev["levels"]["novice"]["slope"]), (Fraction(1), Fraction(9, 35)))
        self.assertEqual((ev["levels"]["skilled"]["gain"], ev["levels"]["skilled"]["slope"]), (Fraction(1, 2), Fraction(1, 7)))
        self.assertEqual((ev["levels"]["expert"]["gain"], ev["levels"]["expert"]["slope"]), (Fraction(0), Fraction(0)))


# ------------------------------------------------------------------ the crafter reads reports only (e)

class CrafterLadderTests(unittest.TestCase):
    """Hand-built report objects: the crafter's choice must follow from the reports, not from a fixed answer."""

    def setUp(self):
        self.fx = fx_load()

    def propose(self, reports, params=None, fx=None):
        fx = fx or self.fx
        return pc.crafter_ladder(view_for(fx, reports, params, fx["target"]))

    def test_no_reports_for_the_target_level_means_no_change(self):
        p = self.propose([rep("skilled", 1, "long", "fail")])
        self.assertEqual((p["changes"], p["why"]), ({}, "no_reports"))

    def test_hard_without_reaching_short_path_raises_cue(self):
        reports = [rep("novice", k, "long", "fail") for k in range(1, 7)]
        p = self.propose(reports)
        self.assertEqual((p["changes"], p["why"]), ({"signpost": 1}, "missed_cue"))

    def test_hard_after_reaching_short_path_raises_reserve(self):
        reports = [rep("novice", 1, "long", "fail"), rep("novice", 2, "short", "fail")]
        p = self.propose(reports)
        self.assertEqual((p["changes"], p["why"]), ({"budget": 4}, "no_reserve"))

    def test_late_first_clear_is_also_hard(self):
        reports = [rep("novice", k, "long", "fail") for k in range(1, 5)] + [rep("novice", 5, "short", "clear")]
        p = self.propose(reports)
        self.assertEqual(p["why"], "missed_cue")

    def test_in_band_means_no_change(self):
        for first in (3, 4):
            reports = [rep("novice", k, "long", "fail") for k in range(1, first)] + [rep("novice", first, "short", "clear")]
            p = self.propose(reports)
            self.assertEqual((p["changes"], p["why"]), ({}, "in_band"))

    def test_too_easy_lowers_cue_then_reserve(self):
        reports = [rep("novice", 1, "short", "clear")]
        p = self.propose(reports, {"signpost": 2, "budget": 6})
        self.assertEqual((p["changes"], p["why"]), ({"signpost": 1}, "too_easy"))
        p = self.propose(reports, {"signpost": 0, "budget": 6})
        self.assertEqual((p["changes"], p["why"]), ({"budget": 5}, "too_easy"))

    def test_moves_fall_through_when_a_knob_is_at_its_end(self):
        reports = [rep("novice", 1, "long", "fail"), rep("novice", 2, "short", "fail")]
        p = self.propose(reports, {"signpost": 0, "budget": 12})
        self.assertEqual((p["changes"], p["why"]), ({"signpost": 1}, "no_reserve"))
        reports = [rep("novice", k, "long", "fail") for k in range(1, 7)]
        p = self.propose(reports, {"signpost": 3, "budget": 5})
        self.assertEqual((p["changes"], p["why"]), ({"budget": 6}, "missed_cue"))

    def test_ladder_exhausted(self):
        reports = [rep("novice", 1, "long", "fail")]
        p = self.propose(reports, {"signpost": 3, "budget": 12})
        self.assertEqual((p["changes"], p["why"]), ({}, "ladder_exhausted"))
        p = self.propose([rep("novice", 1, "short", "clear")], {"signpost": 0, "budget": 3})
        self.assertEqual((p["changes"], p["why"]), ({}, "ladder_exhausted"))

    def test_steps_are_respected(self):
        fx = fx_load("edge_step_two")
        reports = [rep("novice", 1, "long", "fail"), rep("novice", 2, "short", "fail")]
        p = self.propose(reports, {"signpost": 0, "budget": 3}, fx)
        self.assertEqual(p["changes"], {"budget": 6})

    def test_other_levels_do_not_change_the_answer(self):
        base = [rep("novice", k, "long", "fail") for k in range(1, 7)]
        noise = [rep("skilled", 1, "short", "fail"), rep("expert", 1, "short", "clear")]
        self.assertEqual(self.propose(base), self.propose(base + noise))
        self.assertEqual(self.propose(base)["changes"], {"signpost": 1})

    def test_ladder_has_no_fixed_answer(self):
        seen = set()
        scenarios = [
            [rep("novice", 1, "long", "fail")],
            [rep("novice", 1, "long", "fail"), rep("novice", 2, "short", "fail")],
            [rep("novice", 1, "short", "clear")],
            [rep("novice", 1, "long", "fail"), rep("novice", 2, "long", "fail"), rep("novice", 3, "short", "clear")],
        ]
        for reports in scenarios:
            seen.add(json.dumps(self.propose(reports, {"signpost": 1, "budget": 5}), sort_keys=True))
        self.assertEqual(len(seen), 4)

    def test_knob_roles_not_names_pick_the_knob(self):
        raw = raw_main()
        raw["knobs"] = {"zzz_first": raw["knobs"]["budget"], "aaa_second": raw["knobs"]["signpost"]}
        fx = pc.validate(raw)
        reports = [rep("novice", k, "long", "fail") for k in range(1, 7)]
        self.assertEqual(self.propose(reports, {"zzz_first": 3, "aaa_second": 0}, fx)["changes"], {"aaa_second": 1})
        reports = [rep("novice", 1, "long", "fail"), rep("novice", 2, "short", "fail")]
        self.assertEqual(self.propose(reports, {"zzz_first": 3, "aaa_second": 0}, fx)["changes"], {"zzz_first": 4})

    def test_ladder_source_cannot_name_game_internals(self):
        src = inspect.getsource(pc.crafter_ladder) + inspect.getsource(pc._move)
        for word in ("fx", "game", "long_cost", "short_cost", "step_cap", "patience", "sign_weight", "memory", "levels"):
            self.assertIsNone(re.search(r"\b%s\b" % word, src), word)


class CrafterInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.fx = fx_load()

    def run_with_spy(self, fx=None):
        seen = []

        def spy(view):
            seen.append(copy.deepcopy(view))
            return pc.crafter_ladder(view)

        with WithCrafter("spy", spy):
            result = pc.run_crafter(fx or self.fx, "spy")
        return seen, result

    def test_view_holds_exactly_reports_knob_table_params_and_target(self):
        seen, _ = self.run_with_spy()
        self.assertEqual(len(seen), 3)
        for view in seen:
            self.assertEqual(sorted(view), ["knobs", "params", "reports", "target"])
            for knob in view["knobs"]:
                self.assertEqual(sorted(knob), ["id", "max", "min", "role", "step"])
            for r in view["reports"]:
                self.assertEqual(sorted(r), sorted(rep("a", 1, "long", "fail")))

    def test_view_carries_no_game_internals(self):
        seen, _ = self.run_with_spy()
        text = json.dumps(seen, sort_keys=True)
        for word in ("long_cost", "short_cost", "step_cap", "patience", "sign_weight", "no_report", "episodes",
                     "on_expiry", "max_rounds", "crafter", "memory", "long_fails"):
            self.assertNotIn(word, text)

    def test_view_params_and_target_are_the_current_ones(self):
        seen, _ = self.run_with_spy()
        self.assertEqual([v["params"] for v in seen],
                         [{"signpost": 0, "budget": 3}, {"signpost": 0, "budget": 4}, {"signpost": 1, "budget": 4}])
        for v in seen:
            self.assertEqual(v["target"], self.fx["target"])

    def test_reports_in_the_view_are_all_levels_and_all_episodes(self):
        seen, _ = self.run_with_spy()
        for v in seen:
            self.assertEqual(len(v["reports"]), 18)
            self.assertEqual({r["level"] for r in v["reports"]}, {"novice", "skilled", "expert"})

    def test_a_crafter_that_edits_its_view_in_place_cannot_move_the_target(self):
        def tamper(view):
            view["target"]["band"]["hi"] += 1
            return {"target": view["target"], "changes": {}, "why": "tamper"}

        with WithCrafter("tamper", tamper):
            with self.assertRaises(pc.DenyError) as cm:
                pc.run_crafter(self.fx, "tamper")
        self.assertEqual(cm.exception.code, "DENY target_not_declared")
        self.assertEqual(self.fx["target"], {"level": "novice", "band": {"lo": 3, "hi": 4}})

    def test_a_crafter_that_edits_its_reports_cannot_change_the_record(self):
        def scribble(view):
            for r in view["reports"]:
                r["outcome"] = "clear"
                r["episode"] = 1
            return {"target": view["target"], "changes": {}, "why": "scribble"}

        with WithCrafter("scribble", scribble):
            result = pc.run_crafter(self.fx, "scribble")
        first = result["rounds"][0]
        self.assertEqual(first["target_first_clear"], None)
        self.assertTrue(all(r["outcome"] == "fail" for r in first["target_reports"]))

    def test_changes_come_from_reports_so_other_fixtures_give_other_answers(self):
        a = pc.run_crafter(fx_load("main"), "ladder")
        b = pc.run_crafter(fx_load("edge_step_two"), "ladder")
        self.assertEqual(a["final_params"], {"signpost": 1, "budget": 4})
        self.assertEqual(b["final_params"], {"signpost": 1, "budget": 6})


# ------------------------------------------------------------------ rules: DENY

class DenyTests(unittest.TestCase):
    def setUp(self):
        self.fx = fx_load()
        self.target = self.fx["target"]
        self.params = pc.initial_params(self.fx)

    def check(self, proposal):
        return pc.check_proposal(self.target, self.fx["knobs"], self.params, proposal)

    def prop(self, **kw):
        base = {"target": copy.deepcopy(self.target), "changes": {}, "why": "x"}
        base.update(kw)
        return base

    def deny(self, proposal, code):
        with self.assertRaises(pc.DenyError) as cm:
            self.check(proposal)
        self.assertEqual(cm.exception.code, "DENY " + code)

    def test_a_good_proposal_gives_the_new_parameters(self):
        self.assertEqual(self.check(self.prop(changes={"budget": 4})), {"signpost": 0, "budget": 4})
        self.assertEqual(self.check(self.prop()), self.params)

    def test_edited_target_is_denied(self):
        for edit in ({"level": "novice", "band": {"lo": 3, "hi": 5}}, {"level": "novice", "band": {"lo": 2, "hi": 4}},
                     {"level": "skilled", "band": {"lo": 3, "hi": 4}}):
            self.deny(self.prop(target=edit), "target_not_declared")

    def test_missing_or_none_target_is_denied(self):
        self.deny(self.prop(target=None), "target_not_declared")
        self.deny(self.prop(target={}), "target_not_declared")
        self.deny(self.prop(target={"level": "novice"}), "target_not_declared")
        self.deny(self.prop(target={"level": "novice", "band": {"lo": 3, "hi": 4}, "extra": 1}), "target_not_declared")

    def test_boolean_is_not_one_in_the_target(self):
        target = {"level": "novice", "band": {"lo": 1, "hi": 1}}
        tampered = {"level": "novice", "band": {"lo": True, "hi": True}}
        with self.assertRaises(pc.DenyError):
            pc.check_proposal(target, self.fx["knobs"], self.params, {"target": tampered, "changes": {}, "why": "x"})
        self.assertTrue(pc._same(target, copy.deepcopy(target)))
        self.assertFalse(pc._same(1, True))
        self.assertFalse(pc._same({"a": [1]}, {"a": [True]}))
        self.assertFalse(pc._same(1, 1.0))
        self.assertTrue(pc._same({"a": [1, 2]}, {"a": [1, 2]}))
        self.assertFalse(pc._same([1, 2], [1, 2, 3]))

    def test_undeclared_knob_is_denied(self):
        self.deny(self.prop(changes={"volume": 1}), "knob_undeclared")
        self.deny(self.prop(changes={"budget": 4, "volume": 1}), "knob_undeclared")
        self.deny(self.prop(changes={"Budget": 4}), "knob_undeclared")

    def test_out_of_range_is_denied_and_the_ends_are_not(self):
        self.deny(self.prop(changes={"budget": 13}), "knob_out_of_range")
        self.deny(self.prop(changes={"budget": 2}), "knob_out_of_range")
        self.deny(self.prop(changes={"signpost": -1}), "knob_out_of_range")
        self.deny(self.prop(changes={"signpost": 4}), "knob_out_of_range")
        self.assertEqual(self.check(self.prop(changes={"budget": 12, "signpost": 3})), {"signpost": 3, "budget": 12})
        self.assertEqual(self.check(self.prop(changes={"budget": 3, "signpost": 0})), self.params)

    def test_off_step_is_denied(self):
        fx = fx_load("edge_step_two")
        with self.assertRaises(pc.DenyError) as cm:
            pc.check_proposal(fx["target"], fx["knobs"], pc.initial_params(fx),
                              {"target": copy.deepcopy(fx["target"]), "changes": {"budget": 4}, "why": "x"})
        self.assertEqual(cm.exception.code, "DENY knob_off_step")
        ok = pc.check_proposal(fx["target"], fx["knobs"], pc.initial_params(fx),
                               {"target": copy.deepcopy(fx["target"]), "changes": {"budget": 6}, "why": "x"})
        self.assertEqual(ok["budget"], 6)

    def test_bad_value_types_are_denied(self):
        for bad in (True, False, 1.0, 4.0, "4", None, [4], {"v": 4}):
            self.deny(self.prop(changes={"budget": bad}), "knob_bad_value")

    def test_bad_proposal_shapes_are_denied(self):
        self.deny(None, "bad_proposal")
        self.deny([], "bad_proposal")
        self.deny({"target": self.target, "changes": {}}, "bad_proposal")
        self.deny({"target": self.target, "changes": {}, "why": "x", "more": 1}, "bad_proposal")
        self.deny(self.prop(changes=[("budget", 4)]), "bad_proposal")
        self.deny(self.prop(changes=None), "bad_proposal")

    def test_crafters_that_break_the_rules_are_denied_through_the_loop(self):
        for name, code in (("edits_target", "DENY target_not_declared"), ("wild_knob", "DENY knob_undeclared"),
                           ("out_of_range", "DENY knob_out_of_range")):
            with self.assertRaises(pc.DenyError) as cm:
                pc.run_crafter(self.fx, name)
            self.assertEqual(cm.exception.code, code, name)

    def test_target_edited_after_reports_through_the_loop(self):
        calls = []

        def late_edit(view):
            calls.append(1)
            if len(calls) == 1:
                return pc.crafter_ladder(view)
            target = copy.deepcopy(view["target"])
            target["band"]["lo"] = 1
            return {"target": target, "changes": {}, "why": "late_edit"}

        with WithCrafter("late_edit", late_edit):
            with self.assertRaises(pc.DenyError) as cm:
                pc.run_crafter(self.fx, "late_edit")
        self.assertEqual(cm.exception.code, "DENY target_not_declared")
        self.assertEqual(len(calls), 2)

    def test_target_none_after_the_evaluation_is_denied(self):
        outcome = pc.run_crafter(self.fx, "ladder")
        self.assertEqual(outcome["target_verdict"], "in_band")
        with self.assertRaises(pc.DenyError):
            pc.check_proposal(self.fx["target"], self.fx["knobs"], outcome["final_params"],
                              {"target": None, "changes": {}, "why": "after_eval"})

    def test_deny_fixtures_exit_2_with_deny_lines(self):
        for name in sorted(BAD_CODES):
            if BAD_CODES[name].startswith("DENY "):
                rc, out, err = cli(os.path.join(FIXTURES, name + ".json"))
                self.assertEqual((rc, out), (2, ""), name)
                self.assertTrue(err.startswith("ERROR " + BAD_CODES[name] + ": "), (name, err))

    def test_deny_error_is_a_play_error_with_code(self):
        e = pc.DenyError("x", "why")
        self.assertIsInstance(e, pc.PlayError)
        self.assertEqual((e.code, e.detail), ("DENY x", "why"))


# ------------------------------------------------------------------ done-when (a): the revised file

class ParameterFileTests(unittest.TestCase):
    def test_revised_file_differs_only_in_declared_knobs_inside_range(self):
        fx = fx_load()
        result = pc.run_crafter(fx, "ladder")
        before = pc.parameter_file(fx, result["initial_params"])
        after = pc.parameter_file(fx, result["final_params"])
        self.assertEqual(pc.file_diff(before, after), ["knobs.budget", "knobs.signpost"])
        self.assertEqual(result["file_diff"], ["knobs.budget", "knobs.signpost"])
        self.assertEqual(before["game"], after["game"])
        self.assertEqual(before["levels"], after["levels"])
        for knob in fx["knobs"]:
            self.assertTrue(knob["min"] <= after["knobs"][knob["id"]] <= knob["max"])

    def test_every_valid_fixture_changes_only_declared_knobs(self):
        for name in VALID_FIXTURES:
            fx = fx_load(name)
            for crafter in ("ladder", "noop", "overtune"):
                result = pc.run_crafter(fx, crafter)
                declared = ["knobs." + k["id"] for k in fx["knobs"]]
                self.assertTrue(all(p in declared for p in result["file_diff"]), (name, crafter))
                for knob in fx["knobs"]:
                    value = result["final_params"][knob["id"]]
                    self.assertTrue(knob["min"] <= value <= knob["max"])
                    self.assertEqual((value - knob["min"]) % knob["step"], 0)

    def test_the_diff_sees_a_change_outside_the_knobs(self):
        fx = fx_load()
        a = pc.parameter_file(fx, pc.initial_params(fx))
        for path in (("game", "long_cost"), ("game", "step_cap"), ("levels", "novice", "patience")):
            b = copy.deepcopy(a)
            node = b
            for part in path[:-1]:
                node = node[part]
            node[path[-1]] += 1
            self.assertEqual(pc.file_diff(a, b), [".".join(path)])
        b = copy.deepcopy(a)
        b["game"]["no_report"] = [2]
        self.assertEqual(pc.file_diff(a, b), ["game.no_report"])

    def test_the_diff_tells_a_boolean_from_one_and_sees_added_keys(self):
        self.assertEqual(pc.file_diff({"knobs": {"a": 1}}, {"knobs": {"a": True}}), ["knobs.a"])
        self.assertEqual(pc.file_diff({"knobs": {"a": 1}}, {"knobs": {"a": 1, "b": 2}}), ["knobs.b"])
        self.assertEqual(pc.file_diff({"knobs": {"a": 1}}, {"knobs": {"a": 1}}), [])

    def test_parameter_file_is_a_copy(self):
        fx = fx_load()
        a = pc.parameter_file(fx, pc.initial_params(fx))
        a["game"]["no_report"].append(1)
        a["game"]["long_cost"] = 0
        self.assertEqual(fx["game"]["no_report"], [])
        self.assertEqual(fx["game"]["long_cost"], 9)


# ------------------------------------------------------------------ done-when (b): band and controls

class BandAndControlTests(unittest.TestCase):
    def setUp(self):
        self.fx = fx_load()

    def test_before_the_crafting_the_novice_is_outside_the_band(self):
        ev = pc.evaluate(self.fx, pc.initial_params(self.fx))
        self.assertIsNone(ev["levels"]["novice"]["first_clear"])
        self.assertEqual(pc.band_verdict(None, self.fx["target"]["band"]), "too_hard")

    def test_the_real_crafter_lands_in_the_band_on_the_fresh_run(self):
        r = pc.run_crafter(self.fx, "ladder")
        self.assertEqual(r["status"], "OK")
        self.assertTrue(r["converged"])
        self.assertEqual(r["final_params"], {"signpost": 1, "budget": 4})
        self.assertEqual(r["evaluation"]["levels"]["novice"]["first_clear"], 4)
        self.assertEqual(r["target_verdict"], "in_band")
        self.assertEqual([x["changes"] for x in r["rounds"]], [{"budget": 4}, {"signpost": 1}, {}])
        self.assertEqual([x["why"] for x in r["rounds"]], ["no_reserve", "missed_cue", "in_band"])

    def test_noop_misses_the_band_on_the_hard_side(self):
        r = pc.run_crafter(self.fx, "noop")
        self.assertEqual(r["final_params"], pc.initial_params(self.fx))
        self.assertEqual(r["target_verdict"], "too_hard")
        self.assertIsNone(r["evaluation"]["levels"]["novice"]["first_clear"])
        self.assertEqual(len(r["rounds"]), 1)

    def test_overtune_misses_the_band_on_the_easy_side(self):
        r = pc.run_crafter(self.fx, "overtune")
        self.assertEqual(r["final_params"], {"signpost": 3, "budget": 12})
        self.assertEqual(r["target_verdict"], "too_easy")
        self.assertEqual(r["evaluation"]["levels"]["novice"]["first_clear"], 1)

    def test_the_run_checks_hold_on_main(self):
        out = pc.run(self.fx)
        for key, check in out["checks"].items():
            self.assertTrue(check["holds"], key)
        b = out["checks"]["b_band_met_by_the_crafter_and_missed_by_both_controls"]
        self.assertEqual((b["crafter"], b["noop"], b["overtune"]), ("in_band", "too_hard", "too_easy"))
        self.assertEqual(out["status"], "OK")

    def test_controls_are_scored_against_the_same_declared_band(self):
        out = pc.run(self.fx)
        self.assertEqual(out["target"], self.fx["target"])
        for name in ("noop", "overtune"):
            self.assertEqual(out["controls"][name]["name"], name)

    def test_controls_pass_only_where_the_band_permits(self):
        # a band that covers every episode lets the overtune control pass: the band, not the crafter, decides
        out = pc.run(fx_load("edge_band_full_range"))
        self.assertEqual(out["controls"]["overtune"]["target_verdict"], "in_band")
        self.assertFalse(out["checks"]["b_band_met_by_the_crafter_and_missed_by_both_controls"]["holds"])

    def test_single_point_band_and_step_two(self):
        for name in ("edge_single_point_band", "edge_step_two"):
            out = pc.run(fx_load(name))
            self.assertEqual(out["crafter"]["target_verdict"], "in_band", name)
            self.assertTrue(out["checks"]["b_band_met_by_the_crafter_and_missed_by_both_controls"]["holds"], name)

    def test_exhausted_rounds_are_reported_not_hidden(self):
        r = pc.run_crafter(fx_load("edge_knob_bounds"), "ladder")
        self.assertFalse(r["converged"])
        self.assertEqual(len(r["rounds"]), 4)
        self.assertEqual(r["status"], "HOLD")
        self.assertEqual(r["target_verdict"], "too_easy")
        r = pc.run_crafter(fx_load("edge_locked_knob"), "ladder")
        self.assertEqual(r["final_params"]["signpost"], 0)
        self.assertEqual(r["target_verdict"], "too_hard")

    def test_before_block_is_reported(self):
        out = pc.run(self.fx)
        self.assertIsNone(out["before"]["levels"]["novice"]["first_clear"])
        self.assertEqual(out["before"]["levels"]["novice"]["curve"], ["0/1"] * 6)


# ------------------------------------------------------------------ done-when (c): fresh evaluation

class FreshEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.fx = fx_load()

    def test_evaluation_equals_an_independent_fresh_run(self):
        r = pc.run_crafter(self.fx, "ladder")
        independent = pc.evaluate(self.fx, r["final_params"])
        self.assertEqual(r["evaluation"], independent)

    def test_crafting_leaves_memory_and_the_evaluation_starts_empty(self):
        r = pc.run_crafter(self.fx, "ladder")
        self.assertEqual(r["crafting_memory_end"]["novice"], {"long_fails": 3})
        for name, memory in r["eval_memory_start"].items():
            self.assertEqual(memory, pc.fresh_memory(), name)
        self.assertNotEqual(r["crafting_memory_end"]["novice"], r["eval_memory_start"]["novice"])

    def test_carried_memory_would_change_the_result_and_is_not_what_the_loop_shows(self):
        r = pc.run_crafter(self.fx, "ladder")
        self.assertEqual(r["leaky_contrast"]["target_first_clear"], 1)
        self.assertEqual(r["evaluation"]["levels"]["novice"]["first_clear"], 4)

    def test_the_contrast_run_does_not_touch_the_stored_memory(self):
        memories = {"novice": {"long_fails": 0}, "skilled": {"long_fails": 0}, "expert": {"long_fails": 0}}
        before = copy.deepcopy(memories)
        pc.leaky_contrast(self.fx, {"signpost": 0, "budget": 3}, memories)
        self.assertEqual(memories, before)
        carried = {lv["id"]: pc.fresh_memory() for lv in self.fx["levels"]}
        pc.evaluate(self.fx, {"signpost": 0, "budget": 3}, carried)
        self.assertNotEqual(carried, before)

    def test_evaluate_defaults_to_empty_memory_and_is_repeatable(self):
        params = {"signpost": 1, "budget": 4}
        self.assertEqual(pc.evaluate(self.fx, params), pc.evaluate(self.fx, params))
        explicit = {lv["id"]: pc.fresh_memory() for lv in self.fx["levels"]}
        self.assertEqual(pc.evaluate(self.fx, params), pc.evaluate(self.fx, params, explicit))

    def test_a_carried_memory_changes_the_numbers(self):
        params = {"signpost": 1, "budget": 4}
        carried = {lv["id"]: {"long_fails": 9} for lv in self.fx["levels"]}
        self.assertNotEqual(pc.evaluate(self.fx, params, carried)["levels"]["novice"]["curve"],
                            pc.evaluate(self.fx, params)["levels"]["novice"]["curve"])

    def test_each_crafting_round_also_starts_every_player_empty(self):
        r = pc.run_crafter(self.fx, "ladder")
        for rnd in r["rounds"]:
            self.assertEqual(rnd["target_reports"][0]["decisions"], ["long"])
            self.assertEqual(rnd["target_reports"][0]["episode"], 1)

    def test_every_valid_fixture_reports_an_empty_start(self):
        for name in VALID_FIXTURES:
            out = pc.run(fx_load(name))
            if out["status"] == "OK":
                self.assertTrue(out["checks"]["c_fresh_evaluation_reuses_no_crafting_memory"]["holds"], name)
                for memory in out["crafter"]["eval_memory_start"].values():
                    self.assertEqual(memory, {"long_fails": 0})


# ------------------------------------------------------------------ done-when (f): HOLD, ESCALATE, DENY

class ExpiryTests(unittest.TestCase):
    def counting_run(self, name):
        calls = []

        def counting(view):
            calls.append(1)
            return pc.crafter_ladder(view)

        fx = fx_load(name)
        with WithCrafter("counting", counting):
            r = pc.run_crafter(fx, "counting")
        return fx, calls, r

    def test_a_capped_episode_holds_and_licenses_no_craft(self):
        fx, calls, r = self.counting_run("hold_capped")
        self.assertEqual(calls, [])
        self.assertEqual(r["status"], "HOLD")
        self.assertEqual(len(r["rounds"]), 1)
        first = r["rounds"][0]
        self.assertFalse(first["licensed"])
        self.assertEqual(first["changes"], {})
        self.assertEqual(first["held"][0]["reason"], "step_cap")
        self.assertEqual(r["final_params"], pc.initial_params(fx))
        self.assertEqual(r["file_diff"], [])
        self.assertIsNone(r["evaluation"])
        self.assertEqual(r["target_verdict"], "held")

    def test_a_report_less_episode_holds_and_licenses_no_craft(self):
        fx, calls, r = self.counting_run("hold_no_report")
        self.assertEqual(calls, [])
        self.assertEqual(r["status"], "HOLD")
        self.assertEqual(r["rounds"][0]["held"][0], {"level": "novice", "episode": 2, "reason": "no_report"})
        self.assertEqual(r["final_params"], pc.initial_params(fx))
        self.assertIsNone(r["evaluation"])

    def test_hold_reaches_the_report_and_the_exit_code_is_zero(self):
        for name in ("hold_capped", "hold_no_report"):
            rc, out, err = cli(os.path.join(FIXTURES, name + ".json"))
            self.assertEqual((rc, err), (0, ""), name)
            data = json.loads(out)
            self.assertEqual(data["status"], "HOLD")
            self.assertEqual(data["crafter"]["target_verdict"], "held")
            for key in ("noop", "overtune"):
                self.assertEqual(data["controls"][key]["status"], "HOLD")

    def test_escalate_is_a_different_outcome_from_hold(self):
        fx = fx_load("escalate_capped")
        r = pc.run_crafter(fx, "ladder")
        self.assertEqual(r["status"], "ESCALATE")
        self.assertFalse(r["rounds"][0]["licensed"])
        self.assertEqual(r["final_params"], pc.initial_params(fx))

    def test_deny_on_expiry_refuses_with_a_deny_line(self):
        raw = raw_main()
        raw["on_expiry"] = "DENY"
        raw["game"]["no_report"] = [3]
        fx = pc.validate(raw)
        with self.assertRaises(pc.DenyError) as cm:
            pc.run(fx)
        self.assertEqual(cm.exception.code, "DENY episode_held")

    def test_a_held_episode_is_never_a_clear(self):
        raw = raw_main()
        raw["game"]["no_report"] = [4]
        fx = pc.validate(raw)
        ev = pc.evaluate(fx, {"signpost": 1, "budget": 4})
        novice = ev["levels"]["novice"]
        self.assertEqual(novice["first_clear"], 5)
        self.assertEqual(novice["episodes"][3]["outcome"], "no_report")
        self.assertEqual(ev["held"][0], {"level": "novice", "episode": 4, "reason": "no_report"})
        self.assertEqual(novice["curve"][3], Fraction(0))

    def test_a_capped_episode_is_never_a_clear(self):
        fx = fx_load("hold_capped")
        ev = pc.evaluate(fx, {"signpost": 0, "budget": 3})
        for level in ev["levels"].values():
            self.assertIsNone(level["first_clear"])
            self.assertTrue(all(e["outcome"] in ("capped", "fail") for e in level["episodes"]))
        self.assertTrue(ev["held"])

    def test_a_cap_hit_only_in_the_evaluation_still_holds(self):
        raw = raw_main()
        raw["game"]["step_cap"] = 4
        raw["game"]["max_rounds"] = 1
        fx = pc.validate(raw)
        r = pc.run_crafter(fx, "overtune")
        self.assertEqual(r["status"], "HOLD")
        self.assertIsNotNone(r["evaluation"])
        self.assertTrue(r["evaluation"]["held"])
        self.assertEqual(r["evaluation"]["held"][0]["reason"], "step_cap")

    def test_the_round_cap_follows_on_expiry_too(self):
        for action in ("HOLD", "ESCALATE"):
            raw = json.loads(open(os.path.join(FIXTURES, "edge_knob_bounds.json"), "rb").read().decode("utf-8"))
            raw["on_expiry"] = action
            r = pc.run_crafter(pc.validate(raw), "ladder")
            self.assertEqual(r["status"], action)
            self.assertFalse(r["converged"])
        raw["on_expiry"] = "DENY"
        with self.assertRaises(pc.DenyError) as cm:
            pc.run_crafter(pc.validate(raw), "ladder")
        self.assertEqual(cm.exception.code, "DENY rounds_exhausted")

    def test_a_settled_run_is_not_expired(self):
        self.assertEqual(pc.run_crafter(fx_load(), "ladder")["status"], "OK")

    def test_on_expiry_values_are_exactly_hold_escalate_deny(self):
        self.assertEqual(pc.ON_EXPIRY, ("HOLD", "ESCALATE", "DENY"))
        for value in ("HOLD", "ESCALATE", "DENY"):
            raw = raw_main()
            raw["on_expiry"] = value
            self.assertEqual(pc.validate(raw)["on_expiry"], value)

    def test_every_cap_in_the_fixture_has_an_expiry(self):
        fx = fx_load()
        self.assertIn("step_cap", fx["game"])
        self.assertIn("max_rounds", fx["game"])
        self.assertIn(fx["on_expiry"], pc.ON_EXPIRY)


# ------------------------------------------------------------------ loader and validation

class LoaderTests(unittest.TestCase):
    def test_main_loads(self):
        fx = fx_load()
        self.assertEqual(fx["label"], "Fork in the road")
        self.assertEqual(len(fx["levels"]), 3)
        self.assertEqual(len(fx["knobs"]), 2)

    def test_valid_fixture_list_is_complete(self):
        names = sorted(f[:-5] for f in os.listdir(FIXTURES) if f.endswith(".json") and not f.startswith("bad_"))
        self.assertEqual(names, sorted(VALID_FIXTURES))

    def test_every_bad_fixture_is_in_the_code_map_and_back(self):
        names = sorted(f[:-5] for f in os.listdir(FIXTURES) if f.startswith("bad_"))
        self.assertEqual(names, sorted(BAD_CODES))
        self.assertGreaterEqual(len(names), 120)

    def test_each_bad_fixture_raises_its_code_in_process(self):
        for name, code in sorted(BAD_CODES.items()):
            path = os.path.join(FIXTURES, name + ".json")
            with self.assertRaises(pc.PlayError, msg=name) as cm:
                pc.run(pc.load_fixture(path))
            self.assertEqual(cm.exception.code, code, name)

    def test_unreadable_path(self):
        with self.assertRaises(pc.PlayError) as cm:
            pc.load_fixture(os.path.join(FIXTURES, "does_not_exist.json"))
        self.assertEqual(cm.exception.code, "unreadable")

    def test_ids_ascii_and_hangul_are_accepted_nfd_included(self):
        for good in ("a", "A_1", "novice", "초보", "표지판", "걸음수", "x" * 40,
                     unicodedata.normalize("NFD", "초보"), unicodedata.normalize("NFD", "한글_7")):
            self.assertEqual(pc._id(good, "id"), good)

    def test_ids_with_other_characters_are_refused(self):
        for bad in ("", "x" * 41, "a b", "a-b", "a.b", "a\n", "é", "a\u200b", "\ud800", "\u3164", "\u115f", "\u2800",
                    "\u00a0", "\u3000", "\u2028", "\ue000", "\u0085", "\x1b", "\u3131", "１", "a\u0301"):
            with self.assertRaises(pc.PlayError, msg=repr(bad)) as cm:
                pc._id(bad, "id")
            self.assertEqual(cm.exception.code, "bad_id")
        for bad in (1, None, True, ["a"], {"a": 1}):
            with self.assertRaises(pc.PlayError):
                pc._id(bad, "id")

    def test_labels_accept_korean_and_plain_text(self):
        for good in ("Fork in the road", "갈림길", "지름길 표지판", "a", "x" * 80, "Mr. Kim's 3rd try (final)",
                     unicodedata.normalize("NFD", "갈림길")):
            self.assertEqual(pc._label(good, "label"), good)

    def test_labels_refuse_control_invisible_and_unassigned(self):
        for bad in ("a\nb", "a\tb", "a\x1bb", "a\u0085b", "a\u200bb", "a\u200eb", "a\ufeffb", "a\u00a0b", "a\u3000b",
                    "a\u2028b", "a\u2029b", "a\u3164b", "a\u2800b", "a\u115fb", "a\u1160b", "a\u034fb", "a\ue000b",
                    "a\ud800b", "a\u0378b", " a", "a ", "a\u202eb"):
            with self.assertRaises(pc.PlayError, msg=repr(bad)) as cm:
                pc._label(bad, "label")
            self.assertEqual(cm.exception.code, "bad_text")
        for bad in ("", "x" * 81, 5, None, ["a"]):
            with self.assertRaises(pc.PlayError):
                pc._label(bad, "label")

    def test_korean_fixtures_are_accepted_and_run(self):
        for name in ("korean", "korean_nfd"):
            fx = fx_load(name)
            form = "NFC" if name == "korean" else "NFD"
            self.assertEqual(fx["target"]["level"], unicodedata.normalize(form, "초보"))
            out = pc.run(fx)
            self.assertEqual(out["status"], "OK")
            self.assertEqual(out["crafter"]["target_verdict"], "in_band")
            rc, stdout, err = cli(os.path.join(FIXTURES, name + ".json"))
            self.assertEqual((rc, err), (0, ""))
            checks = json.loads(stdout)["checks"]
            self.assertTrue(checks["b_band_met_by_the_crafter_and_missed_by_both_controls"]["holds"])

    def test_korean_nfc_and_nfd_give_the_same_numbers(self):
        a = pc.run(fx_load("korean"))
        b = pc.run(fx_load("korean_nfd"))
        self.assertEqual(len(a["crafter"]["final_params"]), 2)
        self.assertEqual(sorted(a["crafter"]["final_params"].values()), sorted(b["crafter"]["final_params"].values()))
        self.assertEqual(a["crafter"]["target_verdict"], b["crafter"]["target_verdict"])

    def test_nfc_and_nfd_spellings_of_one_id_are_duplicates(self):
        raw = raw_main()
        nfc = unicodedata.normalize("NFC", "초보")
        nfd = unicodedata.normalize("NFD", "초보")
        raw["levels"] = {nfc: raw["levels"]["novice"], nfd: raw["levels"]["skilled"], "expert": raw["levels"]["expert"]}
        raw["target"]["level"] = nfc
        with self.assertRaises(pc.PlayError) as cm:
            pc.validate(raw)
        self.assertEqual(cm.exception.code, "duplicate_name")

    def test_target_level_must_be_one_of_the_levels_exactly(self):
        raw = raw_main()
        raw["target"]["level"] = "master"
        with self.assertRaises(pc.PlayError) as cm:
            pc.validate(raw)
        self.assertEqual(cm.exception.code, "unknown_level")

    def test_integers_must_be_integers(self):
        for bad in (True, False, 1.0, "1", None, [1]):
            with self.assertRaises(pc.PlayError) as cm:
                pc._int(bad, "x", 0, 5)
            self.assertEqual(cm.exception.code, "wrong_type")
        for bad in (-1, 6, 10 ** 400):
            with self.assertRaises(pc.PlayError) as cm:
                pc._int(bad, "x", 0, 5)
            self.assertEqual(cm.exception.code, "bad_value")
        self.assertEqual((pc._int(0, "x", 0, 5), pc._int(5, "x", 0, 5)), (0, 5))

    def test_parse_refuses_nan_infinity_duplicates_and_junk(self):
        cases = {'{"a": NaN}': "bad_number", '{"a": Infinity}': "bad_number", '{"a": -Infinity}': "bad_number",
                 '{"a": 1, "a": 2}': "duplicate_key", '{"a": {"b": 1, "b": 1}}': "duplicate_key",
                 "{'a': 1}": "not_json", '{"a": 1,}': "not_json", "": "not_json", "[1] x": "not_json",
                 "[" * 90000 + "]" * 90000: "not_json", "1" * 5000: "not_json"}
        for text, code in cases.items():
            with self.assertRaises(pc.PlayError, msg=text[:20]) as cm:
                pc.parse(text)
            self.assertEqual(cm.exception.code, code)

    def test_parse_gives_floats_and_bools_their_own_types(self):
        data = pc.parse('{"a": 1.0, "b": true, "c": 1e2, "d": 7}')
        self.assertEqual([type(data[k]) for k in "abcd"], [float, bool, float, int])

    def test_size_cap(self):
        self.assertEqual(pc.MAX_BYTES, 200000)
        for name in ("bad_oversize", "bad_deep_nesting_200k"):
            with self.assertRaises(pc.PlayError) as cm:
                pc.load_fixture(os.path.join(FIXTURES, name + ".json"))
            self.assertEqual(cm.exception.code, "too_large")

    def test_table_of_single_edits_to_main(self):
        def edit(path, value):
            raw = raw_main()
            node = raw
            for part in path[:-1]:
                node = node[part]
            node[path[-1]] = value
            return raw

        cases = [
            (("game", "long_cost"), 0, "bad_value"), (("game", "long_cost"), True, "wrong_type"),
            (("game", "short_cost"), 1.5, "wrong_type"), (("game", "step_cap"), 0, "bad_value"),
            (("game", "episodes"), 2, "bad_value"), (("game", "episodes"), 51, "bad_value"),
            (("game", "episodes"), 3, "bad_value"), (("game", "episodes"), 50, None),
            (("game", "max_rounds"), 0, "bad_value"), (("game", "max_rounds"), 11, "bad_value"),
            (("game", "no_report"), [7], "bad_value"), (("game", "no_report"), [1, 1], "duplicate_name"),
            (("game", "no_report"), "none", "wrong_type"),
            (("knobs", "budget", "min"), 13, "bad_knob"), (("knobs", "budget", "step"), 0, "bad_value"),
            (("knobs", "budget", "step"), -1, "bad_value"), (("knobs", "budget", "initial"), 2, "bad_knob"),
            (("knobs", "budget", "initial"), 12, None), (("knobs", "budget", "role"), "cue", "bad_roles"),
            (("knobs", "budget", "role"), "other", "bad_roles"), (("knobs", "budget", "max"), 11.0, "wrong_type"),
            (("levels", "novice", "patience"), -1, "bad_value"), (("levels", "novice", "patience"), 0, None),
            (("levels", "novice", "sign_weight"), 101, "bad_value"),
            (("target", "band", "lo"), 5, "bad_band"), (("target", "band", "lo"), 0, "bad_value"),
            (("target", "band", "hi"), 7, "bad_value"), (("target", "band", "hi"), True, "wrong_type"),
            (("target", "band", "lo"), 4, None),
            (("on_expiry",), "ALL" + "OW", "bad_on_expiry"), (("on_expiry",), "SAFE_FALLBACK", "bad_on_expiry"),
            (("on_expiry",), "hold", "bad_on_expiry"), (("on_expiry",), None, "bad_on_expiry"),
            (("crafter",), "oracle", "unknown_crafter"), (("fixture_version",), 2, "bad_version"),
            (("fixture_version",), True, "bad_version"), (("label",), "", "wrong_type"),
        ]
        for path, value, code in cases:
            raw = edit(path, value)
            if code is None:
                pc.validate(raw)
                continue
            with self.assertRaises(pc.PlayError, msg=str((path, value))) as cm:
                pc.validate(raw)
            self.assertEqual(cm.exception.code, code, (path, value))

    def test_knob_exactly_at_min_and_max_and_empty_range(self):
        raw = raw_main()
        raw["knobs"]["signpost"].update({"min": 2, "max": 2, "initial": 2})
        fx = pc.validate(raw)
        self.assertEqual(pc.initial_params(fx)["signpost"], 2)
        raw["knobs"]["signpost"].update({"min": 3, "max": 2, "initial": 2})
        with self.assertRaises(pc.PlayError) as cm:
            pc.validate(raw)
        self.assertEqual(cm.exception.code, "bad_knob")

    def test_missing_and_unknown_keys_are_named(self):
        raw = raw_main()
        del raw["game"]["step_cap"]
        with self.assertRaises(pc.PlayError) as cm:
            pc.validate(raw)
        self.assertEqual(cm.exception.code, "missing_key")
        raw = raw_main()
        raw["extra"] = 1
        with self.assertRaises(pc.PlayError) as cm:
            pc.validate(raw)
        self.assertEqual(cm.exception.code, "unknown_key")

    def test_validation_does_not_change_its_input(self):
        raw = raw_main()
        before = copy.deepcopy(raw)
        pc.validate(raw)
        self.assertEqual(raw, before)

    def test_crafter_registry(self):
        self.assertEqual(sorted(pc.CRAFTERS), ["edits_target", "ladder", "noop", "out_of_range", "overtune", "wild_knob"])


# ------------------------------------------------------------------ command line

class CommandLineTests(unittest.TestCase):
    def test_every_malformed_fixture_exits_2_with_empty_stdout_and_one_stderr_line(self):
        for name, code in sorted(BAD_CODES.items()):
            rc, out, err = cli(os.path.join(FIXTURES, name + ".json"))
            self.assertEqual(rc, 2, name)
            self.assertEqual(out, "", name)
            self.assertEqual(err.count("\n"), 1, name)
            self.assertTrue(err.endswith("\n"), name)
            self.assertTrue(err.startswith("ERROR " + code + ": "), (name, err))
            self.assertNotIn("Traceback", err)
            self.assertTrue(err.isascii(), name)

    def test_usage_and_missing_file(self):
        for args in ([], ["a", "b"]):
            rc, out, err = cli(*args)
            self.assertEqual((rc, out), (2, ""))
            self.assertEqual(err.count("\n"), 1)
            self.assertTrue(err.startswith("ERROR usage: "))
        rc, out, err = cli(os.path.join(FIXTURES, "nothing_here.json"))
        self.assertEqual((rc, out), (2, ""))
        self.assertTrue(err.startswith("ERROR unreadable: "))
        self.assertEqual(err.count("\n"), 1)

    def test_valid_fixtures_exit_0_with_json_and_no_stderr(self):
        for name in VALID_FIXTURES:
            rc, out, err = cli(os.path.join(FIXTURES, name + ".json"))
            self.assertEqual((rc, err), (0, ""), name)
            data = json.loads(out)
            self.assertIn(data["status"], ("OK", "HOLD", "ESCALATE"))
            self.assertTrue(out.isascii())
            self.assertTrue(out.endswith("\n"))

    def test_report_is_deterministic_and_states_its_scope(self):
        a, b = pc.report(fx_load()), pc.report(fx_load())
        self.assertEqual(a, b)
        data = json.loads(a)
        self.assertIn("fixture-authored by construction", data["scope_note"])
        self.assertIn("nothing here says the revised game is engaging", data["scope_note"])

    def test_main_returns_codes_without_exiting(self):
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
        try:
            rc = pc.main(["x", os.path.join(FIXTURES, "main.json")])
            out = sys.stdout.getvalue()
            sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
            rc_bad = pc.main(["x", os.path.join(FIXTURES, "bad_nan.json")])
            out_bad, err_bad = sys.stdout.getvalue(), sys.stderr.getvalue()
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("{"))
        self.assertEqual((rc_bad, out_bad), (2, ""))
        self.assertEqual(err_bad.count("\n"), 1)


# ------------------------------------------------------------------ demo (g)

class DemoTests(unittest.TestCase):
    def run_demo(self):
        p = subprocess.run([PY, "-B", os.path.join(HERE, "demo.py")], capture_output=True)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stderr, b"")
        return p.stdout

    def test_demo_is_byte_identical_across_two_runs(self):
        a, b = self.run_demo(), self.run_demo()
        self.assertEqual(a, b)
        self.assertEqual(hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest())

    def test_demo_is_labelled_as_produced_by_the_code(self):
        text = self.run_demo().decode("ascii")
        self.assertIn("transcript produced by this code from the fixture, not written by hand", text)
        self.assertIn("fixture-authored by construction", text)
        self.assertIn("no model is called", text)

    def test_demo_shows_the_whole_session(self):
        text = self.run_demo().decode("ascii")
        for needle in ("TARGET (declared before any episode)", "crafting round 1", "crafting round 3",
                       "CRAFT (no_reserve): budget 3 -> 4", "CRAFT (missed_cue): signpost 0 -> 1",
                       "REVISED: signpost=1 budget=4", "FILE DIFF", "EVAL fresh players with empty memory",
                       "RESULT: novice first clear lands in_band",
                       "noop     signpost=0 budget=3 -> first clear none -> too_hard",
                       "overtune signpost=3 budget=12 -> first clear ep1 -> too_easy",
                       "carrying that memory over would have shown first clear ep1",
                       "DENY target_not_declared", "DENY knob_undeclared", "DENY knob_out_of_range",
                       "DENY knob_bad_value", "status HOLD; round 1 licensed false"):
            self.assertIn(needle, text)

    def test_demo_numbers_come_from_the_module(self):
        text = self.run_demo().decode("ascii")
        novice = pc.run(fx_load())["crafter"]["evaluation"]["levels"]["novice"]
        self.assertIn("gain %s slope %s first clear ep%d" % (novice["gain"], novice["slope"], novice["first_clear"]), text)

    def test_demo_is_ascii_and_has_no_trailing_spaces(self):
        data = self.run_demo()
        for line in data.decode("ascii").split("\n"):
            self.assertEqual(line, line.rstrip())
        self.assertTrue(data.endswith(b"\n"))


# ------------------------------------------------------------------ source scan (h), evidence and docs

def project_files():
    out = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            out.append(os.path.join(root, f))
    return sorted(out)


class HygieneTests(unittest.TestCase):
    def test_imports_are_the_standard_library_only(self):
        mod_imports = set(re.findall(r"^(?:import|from) ([A-Za-z_]+)", read("play_craft.py"), re.M))
        self.assertEqual(mod_imports, {"fractions", "json", "re", "sys", "unicodedata"})
        stdlib = set(sys.stdlib_module_names)
        for name in ("play_craft.py", "demo.py", "mutants.py", "test_play_craft.py"):
            for mod in re.findall(r"^(?:import|from) ([A-Za-z_]+)", read(name), re.M):
                self.assertTrue(mod in stdlib or mod == "play_craft", (name, mod))

    def test_no_network_or_paid_api_words(self):
        words = ["sock" + "et", "url" + "lib", "http" + ".client", "req" + "uests", "ssl", "ftp" + "lib", "smtp" + "lib",
                 "asyn" + "cio", "open" + "ai", "anthr" + "opic", "api_" + "key", "api" + "-key", "bear" + "er ",
                 "tok" + "en", "import ran" + "dom", "time" + ".", "date" + "time", "os" + ".system", "eva" + "l(", "ex" + "ec(",
                 "pic" + "kle"]
        text = read("play_craft.py").lower()
        for w in words:
            self.assertNotIn(w, text, w)

    def test_module_never_writes_or_spawns(self):
        text = read("play_craft.py")
        self.assertEqual(re.findall(r"open\(([^)]*)\)", text), ['path, "rb"'])
        for word in ("subprocess", "os.", "write_text", "mkdir", "remove(", "rename("):
            self.assertNotIn(word, text)

    def test_no_banned_word_or_path_in_any_file(self):
        for path in project_files():
            with open(path, "rb") as fh:
                text = fh.read().decode("utf-8", errors="replace").lower()
            for word in BANNED + OTHER_BANNED + BANNED_PATHS:
                self.assertNotIn(word.lower(), text, (os.path.basename(path), word))
            for word in ("n" + "c", "gp" + "l", "sign" + "ing"):
                self.assertIsNone(re.search(r"\b%s\b" % word, text), (os.path.basename(path), word))

    def test_files_are_utf8_without_bom_or_carriage_returns(self):
        for path in project_files():
            with open(path, "rb") as fh:
                raw = fh.read()
            if "bad_" not in os.path.basename(path):
                raw.decode("utf-8")
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), path)
                self.assertNotIn(b"\r", raw, path)

    def test_no_cache_or_stray_files(self):
        names = sorted(os.path.relpath(p, HERE) for p in project_files() if os.sep + "fixtures" + os.sep not in p)
        self.assertEqual(names, ["README.md", "demo.py", "evidence.json", "mutants.py", "play_craft.py",
                                 "test_play_craft.py"])

    def test_no_forbidden_mechanisms_in_the_source(self):
        text = read("play_craft.py").lower()
        for word in ("hash" + "lib", "hm" + "ac", "sig" + "nature", "timestamp", "led" + "ger", "sql" + "ite", "thread", "dae" + "mon"):
            self.assertNotIn(word, text, word)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.ev = json.loads(read("evidence.json"))

    def test_network_and_paid_api_are_false(self):
        self.assertIs(self.ev["network_used"], False)
        self.assertIs(self.ev["paid_api_used"], False)

    def test_title_and_licence_are_exact(self):
        self.assertEqual(self.ev["paper"]["title"], TITLE)
        self.assertEqual(self.ev["paper"]["licence"], LICENCE)
        self.assertEqual(self.ev["paper"]["arxiv_id"], "2611.26624")
        self.assertIs(self.ev["paper"]["method_only"], True)

    def test_paper_claims_exist_only_under_on_unmeasured_and_are_unverified(self):
        claims = self.ev["on_unmeasured"]["claims"]
        self.assertGreaterEqual(len(claims), 8)
        for c in claims:
            self.assertEqual(c["status"], "UNVERIFIED")
        whats = " ".join(c["what"] for c in claims).lower()
        for needle in ("engaging", "vision", "learning gain", "baselines", "three intelligence settings", "most games"):
            self.assertIn(needle, whats)
        measured = json.dumps(self.ev["measured"]).lower()
        for needle in ("most games", "baseline", "intelligence setting"):
            self.assertNotIn(needle, measured)
        self.assertIs(self.ev["measured"]["improvement_is_fixture_authored"], True)
        self.assertIs(self.ev["measured"]["improvement_claims_engagement"], False)

    def test_measured_numbers_match_the_run(self):
        m = self.ev["measured"]
        out = pc.run(fx_load())
        c = out["crafter"]
        self.assertEqual(m["initial_knobs"], c["initial_params"])
        self.assertEqual(m["revised_knobs"], c["final_params"])
        self.assertEqual(m["crafting_rounds_used"], len(c["rounds"]))
        self.assertEqual(m["round_changes"], [r["changes"] for r in c["rounds"]])
        self.assertEqual(m["novice_first_clear_before"], out["before"]["levels"]["novice"]["first_clear"])
        self.assertEqual(m["novice_first_clear_after"], c["evaluation"]["levels"]["novice"]["first_clear"])
        self.assertEqual(m["novice_gain_after"], c["evaluation"]["levels"]["novice"]["gain"])
        self.assertEqual(m["novice_slope_after"], c["evaluation"]["levels"]["novice"]["slope"])
        self.assertEqual(m["noop_verdict"], out["controls"]["noop"]["target_verdict"])
        self.assertEqual(m["overtune_verdict"], out["controls"]["overtune"]["target_verdict"])
        self.assertEqual(m["leaky_contrast_first_clear"], c["leaky_contrast"]["target_first_clear"])
        self.assertEqual(m["revised_file_changed_paths"], c["file_diff"])
        self.assertEqual(sorted(self.ev["crafters"]), sorted(pc.CRAFTERS))

    def test_measured_has_no_paper_numbers(self):
        text = json.dumps(self.ev["measured"])
        for number in ("311", "520", "29/32", "25/30"):
            self.assertNotIn(number, text)


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.readme = read("README.md")

    def test_title_and_licence_line(self):
        self.assertIn(TITLE, self.readme)
        self.assertIn(LICENCE, self.readme)
        self.assertIn("2611.26624", self.readme)

    def test_scope_statements(self):
        low = self.readme.lower()
        self.assertIn("fixture-authored by construction", low)
        for needle in ("unverified", "engaging", "vision", "paper number", "never claims"):
            self.assertIn(needle, low)

    def test_neighbours_and_first_loop(self):
        self.assertIn("w28-audit-contract", self.readme)
        self.assertIn("mb-answerability-pairs", self.readme)
        self.assertIn("first game or play-design loop on main", self.readme)

    def test_village_section(self):
        self.assertIn("## How a Ludex village would use it", self.readme)
        for name in ("Naru", "Yeoul", "Batang"):
            self.assertIn(name, self.readme)

    def test_formulas_and_contract_are_stated(self):
        for needle in ("learning gain", "learning slope", "least-squares", "this sketch's own definition", "on_expiry",
                       "HOLD", "ESCALATE", "DENY", "exit 2", "noop", "overtune", "python3 -B"):
            self.assertIn(needle, self.readme, needle)

    def test_probe_classes_are_listed(self):
        for needle in ("boolean", "huge int", "nesting", "surrogate", "duplicate", "NaN", "NFC", "NFD", "Hangul",
                       "size cap"):
            self.assertIn(needle, self.readme, needle)

    def test_quotes_are_short(self):
        for quoted in re.findall(r'"([^"\n]{1,200})"', self.readme):
            self.assertLessEqual(len(quoted.split()), 6, quoted)

    def test_no_abstract_sentence_is_copied(self):
        for chunk in ("Recent AI agents can generate playable games", "Mastery is a key source of engagement",
                      "alternates between playing and crafting", "uses a vision-based agent to play games"):
            for name in ("README.md", "evidence.json", "demo.py", "play_craft.py"):
                self.assertNotIn(chunk.lower(), read(name).lower(), (name, chunk))

    def test_demo_hash_in_readme_matches_the_demo(self):
        p = subprocess.run([PY, "-B", os.path.join(HERE, "demo.py")], capture_output=True)
        self.assertIn(hashlib.sha256(p.stdout).hexdigest(), self.readme)


if __name__ == "__main__":
    unittest.main()
