"""Tests for the certified-region delta monitor (stdlib unittest). Run: python3 -B -m unittest test_region"""

import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import region

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")

BAD_CODES = {
    "bad_bigint_value": "non_finite",
    "bad_bool_value": "wrong_type",
    "bad_c1_dim_name": "bad_text",
    "bad_critical_type": "wrong_type",
    "bad_duplicate_dim": "duplicate_name",
    "bad_duplicate_key": "duplicate_key",
    "bad_duplicate_obs_id": "duplicate_id",
    "bad_empty_observations": "empty_list",
    "bad_esc_name": "bad_text",
    "bad_hard_inside_region": "bad_hard",
    "bad_missing_key": "missing_key",
    "bad_nan": "non_finite",
    "bad_newline_id": "bad_text",
    "bad_nfd_duplicate_dim": "duplicate_name",
    "bad_not_json": "bad_json",
    "bad_not_object": "wrong_type",
    "bad_obs_missing_dim": "missing_value",
    "bad_obs_unknown_env": "unknown_value",
    "bad_odd_inverted": "bad_odd",
    "bad_overflow": "non_finite",
    "bad_region_inverted": "bad_region",
    "bad_surrogate_name": "bad_text",
    "bad_unknown_key": "unknown_key",
    "bad_zero_width_id": "bad_text",
}

EXPECT_A = [
    ("o01", "IN_REGION", "CONTINUE", "in_region"),
    ("o02", "IN_REGION", "CONTINUE", "in_region"),
    ("o03", "ODD_EXIT", "RECERTIFY", "odd_exit"),
    ("o04", "ODD_EXIT", "RECERTIFY", "odd_exit"),
    ("o05", "OUT_OF_REGION", "CONTINUE", "quarantined_outlier"),
    ("o06", "IN_REGION", "CONTINUE", "in_region"),
    ("o07", "OUT_OF_REGION", "CONTINUE", "quarantined_outlier"),
    ("o08", "OUT_OF_REGION", "WITHDRAW_AUTHORIZATION", "confirmed_outlier"),
    ("o09", "IN_REGION", "WITHDRAW_AUTHORIZATION", "authorization_withdrawn"),
    ("o10", "OUT_OF_REGION", "WITHDRAW_AUTHORIZATION", "critical_single_dim"),
    ("o11", "OUT_OF_REGION", "WITHDRAW_AUTHORIZATION", "correlated_degradation"),
    ("o12", "HARD_SAFETY", "SHUTDOWN", "hard_safety_violation"),
    ("o13", "HARD_SAFETY", "SHUTDOWN", "hard_safety_violation"),
]

EXPECT_B = ["CONTINUE", "CONTINUE", "WITHDRAW_AUTHORIZATION", "SHUTDOWN", "SHUTDOWN", "CONTINUE", "SHUTDOWN",
            "SHUTDOWN", "CONTINUE", "SHUTDOWN", "SHUTDOWN", "SHUTDOWN", "SHUTDOWN"]


def main_text():
    with open(os.path.join(FIX, "main.json"), encoding="utf-8") as handle:
        return handle.read()


def tiny(*observations):
    """Two dims (t, s critical), one ODD variable e. Each observation is (t, s, e)."""
    return region.validate({
        "name": "tiny",
        "dims": [
            {"name": "t", "lo": 10, "hi": 20, "hard_lo": 0, "hard_hi": 30, "critical": False},
            {"name": "s", "lo": 10, "hi": 20, "hard_lo": 0, "hard_hi": 30, "critical": True},
            {"name": "u", "lo": 10, "hi": 20, "hard_lo": 0, "hard_hi": 30, "critical": False},
        ],
        "odd": [{"name": "e", "lo": 0, "hi": 5}],
        "observations": [
            {"id": "x%d" % i, "state": {"t": o[0], "s": o[1], "u": o[3] if len(o) > 3 else 15}, "env": {"e": o[2]}}
            for i, o in enumerate(observations)
        ],
    })


def a_of(*observations):
    return region.run_a(tiny(*observations))


def b_of(*observations):
    return region.run_b(tiny(*observations))


class MainFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = region.load_fixture(os.path.join(FIX, "main.json"))
        cls.a = region.run_a(cls.fx)
        cls.b = region.run_b(cls.fx)

    def test_row_counts(self):
        self.assertEqual(len(self.fx["observations"]), 13)
        self.assertEqual(len(self.a), 13)
        self.assertEqual(len(self.b), 13)

    def test_arm_a_expected_rows(self):
        got = [(r["id"], r["klass"], r["response"], r["reason"]) for r in self.a]
        self.assertEqual(got, EXPECT_A)

    def test_arm_b_expected_responses(self):
        self.assertEqual([r["response"] for r in self.b], EXPECT_B)

    def test_arm_a_counts(self):
        self.assertEqual(region.counts(self.a), {"CONTINUE": 5, "WITHDRAW_AUTHORIZATION": 4, "SHUTDOWN": 2, "RECERTIFY": 2})

    def test_arm_b_counts(self):
        self.assertEqual(region.counts(self.b), {"CONTINUE": 4, "WITHDRAW_AUTHORIZATION": 1, "SHUTDOWN": 8, "RECERTIFY": 0})

    def test_four_responses_distinguishable_in_a(self):
        self.assertTrue(region.distinguishable(self.a))

    def test_arm_b_not_distinguishable(self):
        self.assertFalse(region.distinguishable(self.b))
        self.assertEqual(region.counts(self.b)["RECERTIFY"], 0)

    def test_compare(self):
        diff = region.compare(self.a, self.b)
        self.assertEqual(diff["over_shutdown"], ["o04", "o05", "o07", "o08", "o10", "o11"])
        self.assertEqual(diff["odd_authority_cut"], ["o03"])
        self.assertEqual(diff["missed_shutdown"], [])

    def test_compare_reads_rows_not_classes(self):
        row = lambda r: {"id": "z", "response": r}
        diff = region.compare([row("CONTINUE")], [row("WITHDRAW_AUTHORIZATION")])
        self.assertEqual(diff, {"over_shutdown": [], "missed_shutdown": [], "odd_authority_cut": []})

    def test_every_class_present(self):
        self.assertEqual({r["klass"] for r in self.a}, set(region.CLASSES))

    def test_odd_exit_retains_authority_and_power(self):
        for r in self.a:
            if r["klass"] == "ODD_EXIT":
                self.assertEqual((r["authority"], r["power"], r["recertify"]), ("retained", "on", True))

    def test_shutdown_only_for_hard_safety(self):
        for r in self.a:
            self.assertEqual(r["response"] == "SHUTDOWN", r["klass"] == "HARD_SAFETY")

    def test_odd_exit_with_state_deviation_still_recertifies(self):
        row = {r["id"]: r for r in self.a}["o04"]
        self.assertEqual(row["response"], "RECERTIFY")
        self.assertEqual({r["id"]: r for r in self.b}["o04"]["response"], "SHUTDOWN")

    def test_hard_safety_beats_odd_exit(self):
        self.assertEqual({r["id"]: r for r in self.a}["o13"]["response"], "SHUTDOWN")

    def test_no_continue_after_first_withdrawal(self):
        first = next(i for i, r in enumerate(self.a) if r["response"] == "WITHDRAW_AUTHORIZATION")
        for r in self.a[first:]:
            self.assertNotEqual(r["response"], "CONTINUE")
            self.assertEqual(r["authority"], "withdrawn")

    def test_in_region_row_after_withdrawal_stays_withdrawn(self):
        row = {r["id"]: r for r in self.a}["o09"]
        self.assertEqual((row["klass"], row["response"], row["reason"]), ("IN_REGION", "WITHDRAW_AUTHORIZATION", "authorization_withdrawn"))

    def test_report_is_deterministic(self):
        self.assertEqual(region.report(self.fx), region.report(copy.deepcopy(self.fx)))


class Classify(unittest.TestCase):
    def kl(self, *o):
        fx = tiny(o)
        return region.classify(fx, fx["observations"][0])["klass"]

    def test_in_region(self):
        self.assertEqual(self.kl(15, 15, 2), "IN_REGION")

    def test_region_bounds_inclusive(self):
        self.assertEqual(self.kl(10, 20, 0), "IN_REGION")
        self.assertEqual(self.kl(20, 10, 5), "IN_REGION")

    def test_just_outside_region(self):
        self.assertEqual(self.kl(20.5, 15, 2), "OUT_OF_REGION")
        self.assertEqual(self.kl(9.5, 15, 2), "OUT_OF_REGION")

    def test_hard_bounds_inclusive(self):
        self.assertEqual(self.kl(30, 15, 2), "OUT_OF_REGION")
        self.assertEqual(self.kl(0, 15, 2), "OUT_OF_REGION")

    def test_just_beyond_hard_bound(self):
        self.assertEqual(self.kl(30.5, 15, 2), "HARD_SAFETY")
        self.assertEqual(self.kl(-0.5, 15, 2), "HARD_SAFETY")

    def test_odd_bounds(self):
        self.assertEqual(self.kl(15, 15, 5), "IN_REGION")
        self.assertEqual(self.kl(15, 15, 5.5), "ODD_EXIT")
        self.assertEqual(self.kl(15, 15, -0.5), "ODD_EXIT")

    def test_hard_dims_listed(self):
        fx = tiny((35, 40, 2))
        c = region.classify(fx, fx["observations"][0])
        self.assertEqual(c["hard"], ["t", "s"])
        self.assertEqual(c["out"], ["t", "s"])

    def test_odd_exit_beats_out_of_region(self):
        self.assertEqual(self.kl(25, 15, 9), "ODD_EXIT")


class Responses(unittest.TestCase):
    def test_small_in_region_deviation_continues(self):
        row = a_of((19.9, 10.1, 4.9))[0]
        self.assertEqual((row["response"], row["authority"], row["power"]), ("CONTINUE", "retained", "on"))

    def test_critical_single_dim_withdraws_without_shutdown(self):
        row = a_of((15, 25, 2))[0]
        self.assertEqual(row["response"], "WITHDRAW_AUTHORIZATION")
        self.assertEqual(row["reason"], "critical_single_dim")
        self.assertEqual((row["authority"], row["power"]), ("withdrawn", "on"))

    def test_critical_wins_over_noncritical_pair(self):
        self.assertEqual(a_of((25, 25, 2))[0]["reason"], "critical_single_dim")

    def test_correlated_pair_withdraws(self):
        row = a_of((25, 15, 2, 5))[0]
        self.assertEqual((row["response"], row["reason"]), ("WITHDRAW_AUTHORIZATION", "correlated_degradation"))
        self.assertEqual(row["detail"], ["t", "u"])

    def test_hard_safety_shuts_down(self):
        row = a_of((35, 15, 2))[0]
        self.assertEqual((row["response"], row["authority"], row["power"]), ("SHUTDOWN", "withdrawn", "off"))

    def test_hard_safety_on_critical_dim_shuts_down_not_withdraws(self):
        self.assertEqual(a_of((15, 35, 2))[0]["response"], "SHUTDOWN")

    def test_odd_exit_recertifies_without_authority_cut(self):
        row = a_of((15, 15, 9))[0]
        self.assertEqual(row["response"], "RECERTIFY")
        self.assertEqual((row["authority"], row["power"], row["recertify"]), ("retained", "on", True))
        self.assertEqual(row["detail"], ["e"])

    def test_odd_exit_with_critical_failure_recertifies(self):
        self.assertEqual(a_of((15, 25, 9))[0]["response"], "RECERTIFY")

    def test_hard_safety_with_odd_exit_shuts_down(self):
        self.assertEqual(a_of((35, 15, 9))[0]["response"], "SHUTDOWN")

    def test_effects_table_pairwise_distinct(self):
        effects = {tuple(sorted(e.items())) for e in region.EFFECTS.values()}
        self.assertEqual(len(effects), 4)
        self.assertEqual(set(region.EFFECTS), set(region.RESPONSES))

    def test_only_recertify_requests_recertification(self):
        for name, e in region.EFFECTS.items():
            self.assertEqual(e["recertify"], name == "RECERTIFY")

    def test_only_shutdown_powers_off(self):
        for name, e in region.EFFECTS.items():
            self.assertEqual(e["power"] == "off", name == "SHUTDOWN")


class Quarantine(unittest.TestCase):
    def test_first_isolated_outlier_pending(self):
        row = a_of((25, 15, 2))[0]
        self.assertEqual((row["response"], row["quarantine"]), ("CONTINUE", "pending:t"))

    def test_confirmed_on_same_dim(self):
        rows = a_of((25, 15, 2), (26, 15, 2))
        self.assertEqual((rows[1]["response"], rows[1]["quarantine"]), ("WITHDRAW_AUTHORIZATION", "confirmed:t"))

    def test_released_when_back_in_region(self):
        rows = a_of((25, 15, 2), (15, 15, 2))
        self.assertEqual((rows[1]["response"], rows[1]["quarantine"]), ("CONTINUE", "released:t"))

    def test_second_outlier_on_another_dim_confirms(self):
        rows = a_of((25, 15, 2), (15, 15, 2, 25))
        self.assertEqual((rows[1]["response"], rows[1]["quarantine"]), ("WITHDRAW_AUTHORIZATION", "confirmed:t"))
        self.assertEqual(rows[1]["detail"], ["u"])

    def test_alternating_dims_withdraw_and_stay_withdrawn(self):
        rows = a_of((25, 15, 2), (15, 15, 2, 25), (25, 15, 2), (15, 15, 2, 25), (25, 15, 2))
        self.assertEqual([r["response"] for r in rows], ["CONTINUE"] + ["WITHDRAW_AUTHORIZATION"] * 4)

    def test_repeated_same_dim_outliers_never_flap(self):
        rows = a_of(*[(25, 15, 2)] * 6)
        self.assertEqual([r["response"] for r in rows], ["CONTINUE"] + ["WITHDRAW_AUTHORIZATION"] * 5)
        self.assertEqual(rows[2]["reason"], "authorization_withdrawn")
        self.assertIsNone(rows[2]["quarantine"])

    def test_confirmation_is_one_step_only(self):
        rows = a_of((25, 15, 2), (15, 15, 2), (25, 15, 2))
        self.assertEqual([r["response"] for r in rows], ["CONTINUE", "CONTINUE", "CONTINUE"])
        self.assertEqual(rows[2]["quarantine"], "pending:t")

    def test_withdrawal_is_sticky_through_in_region_rows(self):
        rows = a_of((25, 15, 2), (25, 15, 2), (15, 15, 2), (15, 15, 2))
        self.assertEqual([r["response"] for r in rows], ["CONTINUE"] + ["WITHDRAW_AUTHORIZATION"] * 3)
        self.assertEqual([r["authority"] for r in rows], ["retained"] + ["withdrawn"] * 3)

    def test_withdrawal_by_critical_failure_is_sticky(self):
        rows = a_of((15, 25, 2), (15, 15, 2), (25, 15, 2))
        self.assertEqual([r["response"] for r in rows], ["WITHDRAW_AUTHORIZATION"] * 3)

    def test_withdrawal_by_correlated_degradation_is_sticky(self):
        rows = a_of((25, 15, 2, 25), (15, 15, 2))
        self.assertEqual([r["response"] for r in rows], ["WITHDRAW_AUTHORIZATION"] * 2)

    def test_recertify_after_withdrawal_does_not_restore_authority(self):
        rows = a_of((15, 25, 2), (15, 15, 9))
        self.assertEqual(rows[1]["response"], "RECERTIFY")
        self.assertEqual((rows[1]["authority"], rows[1]["power"], rows[1]["recertify"]), ("withdrawn", "on", True))

    def test_recertify_before_any_withdrawal_retains_authority(self):
        rows = a_of((15, 15, 9), (15, 15, 2))
        self.assertEqual((rows[0]["authority"], rows[1]["response"]), ("retained", "CONTINUE"))

    def test_shutdown_after_withdrawal_still_shuts_down(self):
        rows = a_of((15, 25, 2), (35, 15, 2))
        self.assertEqual([r["response"] for r in rows], ["WITHDRAW_AUTHORIZATION", "SHUTDOWN"])
        self.assertEqual((rows[1]["authority"], rows[1]["power"]), ("withdrawn", "off"))

    def test_shutdown_is_sticky(self):
        rows = a_of((15, 15, 2), (35, 15, 2), (15, 15, 2), (15, 15, 9))
        self.assertEqual([r["response"] for r in rows], ["CONTINUE", "SHUTDOWN", "SHUTDOWN", "SHUTDOWN"])
        self.assertEqual([r["reason"] for r in rows][1:], ["hard_safety_violation", "already_shut_down", "already_shut_down"])
        for row in rows[1:]:
            self.assertEqual((row["authority"], row["power"], row["recertify"]), ("withdrawn", "off", False))
        # Withdrawal-class rows after the hard row: a critical failure, a correlated pair, and a confirmed
        # outlier (pending, then confirmed) are all overridden to SHUTDOWN by the latch alone.
        rows = a_of((15, 15, 2), (35, 15, 2), (15, 25, 2), (25, 15, 2, 5), (25, 15, 2), (25, 15, 2))
        self.assertEqual([r["response"] for r in rows], ["CONTINUE"] + ["SHUTDOWN"] * 5)
        self.assertEqual([r["reason"] for r in rows][1:], ["hard_safety_violation"] + ["already_shut_down"] * 4)
        for row in rows[1:]:
            self.assertEqual((row["authority"], row["power"], row["recertify"]), ("withdrawn", "off", False))
        self.assertEqual([r["klass"] for r in rows][2:], ["OUT_OF_REGION"] * 4)

    def test_four_responses_stay_distinguishable_when_withdrawn(self):
        rows = a_of((15, 25, 2), (15, 15, 9), (35, 15, 2), (15, 15, 2))
        self.assertEqual([r["response"] for r in rows],
                         ["WITHDRAW_AUTHORIZATION", "RECERTIFY", "SHUTDOWN", "SHUTDOWN"])
        self.assertEqual(len({(r["response"], r["authority"], r["power"], r["recertify"]) for r in rows}), 3)

    def test_distinguishable_false_when_two_responses_share_an_effect(self):
        def row(response, effect):
            return {"response": response, "authority": effect[0], "power": effect[1], "recertify": effect[2]}
        rows = [row("CONTINUE", ("retained", "on", False)), row("WITHDRAW_AUTHORIZATION", ("retained", "on", False)),
                row("SHUTDOWN", ("withdrawn", "off", False)), row("RECERTIFY", ("retained", "on", True))]
        self.assertFalse(region.distinguishable(rows))

    def test_odd_exit_clears_pending(self):
        rows = a_of((25, 15, 2), (25, 15, 9), (25, 15, 2))
        self.assertEqual(rows[1]["response"], "RECERTIFY")
        self.assertEqual(rows[2]["quarantine"], "pending:t")

    def test_hard_safety_clears_pending(self):
        rows = a_of((25, 15, 2), (35, 15, 2), (25, 15, 2))
        self.assertIsNone(rows[1]["quarantine"])
        self.assertEqual((rows[2]["response"], rows[2]["quarantine"]), ("SHUTDOWN", None))

    def test_critical_outlier_is_never_quarantined(self):
        row = a_of((15, 25, 2))[0]
        self.assertIsNone(row["quarantine"])


class ArmB(unittest.TestCase):
    def test_any_deviation_shuts_down(self):
        self.assertEqual(b_of((25, 15, 2))[0]["response"], "SHUTDOWN")

    def test_odd_exit_cuts_authority(self):
        row = b_of((15, 15, 9))[0]
        self.assertEqual((row["response"], row["authority"], row["power"]), ("WITHDRAW_AUTHORIZATION", "withdrawn", "on"))

    def test_in_region_continues(self):
        self.assertEqual(b_of((15, 15, 2))[0]["response"], "CONTINUE")

    def test_odd_exit_with_deviation_shuts_down(self):
        self.assertEqual(b_of((25, 15, 9))[0]["response"], "SHUTDOWN")

    def test_hard_safety_shuts_down(self):
        self.assertEqual(b_of((35, 15, 2))[0]["response"], "SHUTDOWN")


class Validation(unittest.TestCase):
    def test_every_bad_fixture_has_expected_code(self):
        names = sorted(n[:-5] for n in os.listdir(FIX) if n.startswith("bad_"))
        self.assertEqual(names, sorted(BAD_CODES))
        for name in names:
            with self.assertRaises(region.FixtureError, msg=name) as ctx:
                region.load_fixture(os.path.join(FIX, name + ".json"))
            self.assertEqual(ctx.exception.code, BAD_CODES[name], name)

    def test_missing_file(self):
        with self.assertRaises(region.FixtureError) as ctx:
            region.load_fixture(os.path.join(FIX, "absent.json"))
        self.assertEqual(ctx.exception.code, "unreadable")

    def test_hard_lower_limit_must_contain_region(self):
        data = json.loads(json.dumps(tiny((15, 15, 2))))
        data["dims"][0]["hard_lo"] = 12
        with self.assertRaises(region.FixtureError) as ctx:
            region.validate(data)
        self.assertEqual(ctx.exception.code, "bad_hard")

    def test_bad_characters_in_names_and_ids(self):
        chars = ["\n", "\r", "\t", "\x1b", "\x7f", "\u0085", "\u200b", "\u200d", "\ufeff", "\u2028",
                 "\u2029", "\u00a0", "\u3000", "\ue000", "\ud800", "\u3164", "\u2800"]
        for ch in chars:
            for place in ("name", "dim", "odd", "id"):
                data = json.loads(json.dumps(tiny((15, 15, 2))))
                bad = "a%sb" % ch
                if place == "name":
                    data["name"] = bad
                elif place == "dim":
                    data["dims"][0]["name"] = bad
                    data["observations"][0]["state"][bad] = data["observations"][0]["state"].pop("t")
                elif place == "odd":
                    data["odd"][0]["name"] = bad
                    data["observations"][0]["env"][bad] = data["observations"][0]["env"].pop("e")
                else:
                    data["observations"][0]["id"] = bad
                with self.assertRaises(region.FixtureError, msg=(place, ch)) as ctx:
                    region.validate(data)
                self.assertEqual(ctx.exception.code, "bad_text", (place, ch))

    def test_korean_text_is_not_over_rejected(self):
        data = json.loads(json.dumps(tiny((15, 15, 2))))
        data["name"] = "\uc628\ub3c4 \uc810\uac80"
        data["observations"][0]["id"] = "\ud589 1"
        region.validate(data)
        data["dims"][0]["name"] = "\u1112\u1161\u11ab"  # decomposed jamo, no filler
        data["observations"][0]["state"]["\u1112\u1161\u11ab"] = data["observations"][0]["state"].pop("t")
        region.validate(data)

    def test_leading_and_trailing_space_rejected(self):
        for bad in (" x0", "x0 "):
            data = json.loads(json.dumps(tiny((15, 15, 2))))
            data["observations"][0]["id"] = bad
            with self.assertRaises(region.FixtureError) as ctx:
                region.validate(data)
            self.assertEqual(ctx.exception.code, "bad_text")

    def test_plain_unicode_and_inner_space_accepted(self):
        data = json.loads(json.dumps(tiny((15, 15, 2))))
        data["name"] = "caf\u00e9 run \u6e29\u5ea6"
        data["observations"][0]["id"] = "row 1"
        region.validate(data)

    def test_nfc_nfd_duplicate_ids_rejected(self):
        data = json.loads(json.dumps(tiny((15, 15, 2), (15, 15, 2))))
        data["observations"][0]["id"] = "caf\u00e9"
        data["observations"][1]["id"] = "cafe\u0301"
        with self.assertRaises(region.FixtureError) as ctx:
            region.validate(data)
        self.assertEqual(ctx.exception.code, "duplicate_id")

    def test_nfc_nfd_duplicate_odd_names_rejected(self):
        data = json.loads(json.dumps(tiny((15, 15, 2))))
        data["odd"] = [{"name": "caf\u00e9", "lo": 0, "hi": 5}, {"name": "cafe\u0301", "lo": 0, "hi": 5}]
        data["observations"][0]["env"] = {"caf\u00e9": 1, "cafe\u0301": 1}
        with self.assertRaises(region.FixtureError) as ctx:
            region.validate(data)
        self.assertEqual(ctx.exception.code, "duplicate_name")

    def test_unknown_key_with_newline_stays_one_line(self):
        data = json.loads(json.dumps(tiny((15, 15, 2))))
        data["x\nFORGED"] = 1
        with self.assertRaises(region.FixtureError) as ctx:
            region.validate(data)
        self.assertNotIn("\n", str(ctx.exception))

    def test_unknown_env_name_with_newline_stays_one_line(self):
        data = json.loads(json.dumps(tiny((15, 15, 2))))
        data["observations"][0]["env"]["x\nFORGED"] = 1
        with self.assertRaises(region.FixtureError) as ctx:
            region.validate(data)
        self.assertEqual(ctx.exception.code, "unknown_value")
        self.assertNotIn("\n", str(ctx.exception))

    def test_duplicate_key_with_newline_stays_one_line(self):
        with self.assertRaises(region.FixtureError) as ctx:
            region.parse_text('{"a\\nb": 1, "a\\nb": 2}')
        self.assertEqual(ctx.exception.code, "duplicate_key")
        self.assertNotIn("\n", str(ctx.exception))

    def test_huge_integer_is_rejected_not_a_crash(self):
        for digits in (309, 400):
            data = json.loads(json.dumps(tiny((15, 15, 2))))
            data["odd"][0]["hi"] = int("2" + "0" * (digits - 1))
            with self.assertRaises(region.FixtureError) as ctx:
                region.validate(data)
            self.assertEqual(ctx.exception.code, "non_finite")

    def test_integer_over_str_digit_limit_is_rejected(self):
        with self.assertRaises(region.FixtureError) as ctx:
            region.parse_text('{"name": 1' + "9" * 5000 + "}")
        self.assertEqual(ctx.exception.code, "bad_json")

    def test_deep_nesting_is_rejected(self):
        for opener in ("[", '{"a":'):
            with self.assertRaises(region.FixtureError, msg=opener) as ctx:
                region.parse_text(opener * 200000)
            self.assertEqual(ctx.exception.code, "too_deep")

    def test_validate_accepts_equal_bounds(self):
        data = json.loads(json.dumps(tiny((15, 15, 2))))
        data["dims"][0].update(lo=15, hi=15, hard_lo=15, hard_hi=15)
        region.validate(data)

    def test_validate_rejects_empty_name(self):
        data = json.loads(json.dumps(tiny((15, 15, 2))))
        data["name"] = ""
        with self.assertRaises(region.FixtureError):
            region.validate(data)

    def test_validate_rejects_empty_dims(self):
        data = json.loads(json.dumps(tiny((15, 15, 2))))
        data["dims"] = []
        with self.assertRaises(region.FixtureError) as ctx:
            region.validate(data)
        self.assertEqual(ctx.exception.code, "empty_list")

    def test_validate_rejects_string_number(self):
        data = json.loads(json.dumps(tiny((15, 15, 2))))
        data["odd"][0]["hi"] = "5"
        with self.assertRaises(region.FixtureError) as ctx:
            region.validate(data)
        self.assertEqual(ctx.exception.code, "wrong_type")


class Cli(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = region.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_main_fixture(self):
        rc, out, err = self.run_main([os.path.join(FIX, "main.json")])
        self.assertEqual((rc, err), (0, ""))
        for response in region.RESPONSES:
            self.assertIn(response, out)
        self.assertIn("four responses distinguishable in arm A: yes", out)
        self.assertIn("four responses distinguishable in arm B: no", out)

    def test_bad_fixture_prints_one_error_line(self):
        rc, out, err = self.run_main([os.path.join(FIX, "bad_region_inverted.json")])
        self.assertEqual((rc, out), (2, ""))
        self.assertEqual(err.count("\n"), 1)
        self.assertTrue(err.startswith("ERROR bad_region: "))

    def test_unwritable_report_exits_2(self):
        class Refuse:
            def write(self, text):
                raise UnicodeEncodeError("ascii", text, 0, 1, "refused")

            def flush(self):
                pass

        err = io.StringIO()
        with redirect_stdout(Refuse()), redirect_stderr(err):
            rc = region.main([os.path.join(FIX, "main.json")])
        self.assertEqual(rc, 2)
        self.assertEqual(err.getvalue().count("\n"), 1)
        self.assertTrue(err.getvalue().startswith("ERROR "))

    def run_text(self, text):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "case.json")
            with open(path, "w", encoding="utf-8", errors="surrogatepass") as handle:
                handle.write(text)
            return subprocess.run([sys.executable, "-B", "region.py", path], cwd=HERE,
                                  capture_output=True, text=True)

    def test_subprocess_huge_integer(self):
        proc = self.run_text(main_text().replace('"latency_ms": 70', '"latency_ms": ' + "2" + "0" * 308, 1))
        self.assertEqual((proc.returncode, proc.stdout), (2, ""))
        self.assertEqual(proc.stderr.count("\n"), 1)
        self.assertNotIn("Traceback", proc.stderr)

    def test_subprocess_deep_nesting(self):
        proc = self.run_text("[" * 200000)
        self.assertEqual((proc.returncode, proc.stdout), (2, ""))
        self.assertTrue(proc.stderr.startswith("ERROR too_deep"))
        self.assertNotIn("Traceback", proc.stderr)

    def test_subprocess_lone_surrogate(self):
        proc = self.run_text(main_text().replace('"name": "main"', '"name": "a\\ud800b"', 1))
        self.assertEqual((proc.returncode, proc.stdout), (2, ""))
        self.assertTrue(proc.stderr.startswith("ERROR bad_text"))
        self.assertNotIn("Traceback", proc.stderr)

    def test_usage(self):
        rc, out, err = self.run_main([])
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("usage", err)

    def test_subprocess_main(self):
        proc = subprocess.run([sys.executable, "-B", "region.py", "fixtures/main.json"], cwd=HERE,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, region.report(region.load_fixture(os.path.join(FIX, "main.json"))))

    def test_subprocess_bad(self):
        proc = subprocess.run([sys.executable, "-B", "region.py", "fixtures/bad_nan.json"], cwd=HERE,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.startswith("ERROR non_finite"))

    def test_demo_output_contains_report(self):
        proc = subprocess.run([sys.executable, "-B", "demo.py"], cwd=HERE, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        report = region.report(region.load_fixture(os.path.join(FIX, "main.json")))
        self.assertIn(report, proc.stdout)
        self.assertIn("RECERTIFY", proc.stdout)


class Docs(unittest.TestCase):
    def test_readme_names_every_state_arm_a_carries(self):
        with open(os.path.join(HERE, "README.md"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("the one-step quarantine, the sticky withdrawal and the sticky shutdown; arm B is stateless", text)


if __name__ == "__main__":
    unittest.main()
