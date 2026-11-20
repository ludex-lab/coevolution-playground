import copy
import io
import json
import operator
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import answerability as an

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
PY = sys.executable
Fraction = an.Fraction
NO_STATE = ("command_only", "command_rules")


def raw(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def main_fx():
    return an.load_fixture(os.path.join(FIX, "main.json"))


def cli(*args):
    p = subprocess.run([PY, "-B", os.path.join(HERE, "answerability.py")] + list(args), cwd=HERE,
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


def code_of(test, mutate):
    root = raw("main.json")
    mutate(root)
    with test.assertRaises(an.AnswerError) as cm:
        an.validate(root)
    return cm.exception.code


def tiny(pairs, extras=()):
    """One system s with fields f and g; one rule: go is PERMIT when f >= 10."""
    return an.validate({
        "fixture_version": 1,
        "systems": {"s": ["f", "g"]},
        "rules": [{"id": "R1", "system": "s", "command": "go", "field": "f", "op": "ge", "limit": 10}],
        "pairs": [{"id": pid, "command": "go", "state_a": {"f": fa, "g": 0}, "state_b": {"f": fb, "g": 0},
                   "expected_a": ea, "expected_b": eb} for pid, fa, fb, ea, eb in pairs],
        "extras": [{"id": xid, "command": "go", "state": {"f": f, "g": 0}, "expected": e} for xid, f, e in extras],
    })


class Fixture(unittest.TestCase):
    def test_main_shape(self):
        fx = main_fx()
        self.assertEqual((len(fx["systems"]), len(fx["rules"]), len(fx["pairs"]), len(fx["extras"])), (3, 6, 12, 11))
        self.assertEqual(len(an.items(fx)), 35)

    def test_every_pair_requires_opposite_answers(self):
        for p in main_fx()["pairs"]:
            self.assertEqual({p["expected_a"], p["expected_b"]}, {an.PERMIT, an.REFUSE}, p["id"])

    def test_pairs_differ_only_in_the_decisive_field(self):
        fx = main_fx()
        by_command = {r["command"]: r for r in fx["rules"]}
        for p in fx["pairs"]:
            differing = [k for k in p["state_a"] if p["state_a"][k] != p["state_b"][k]]
            self.assertEqual(differing, [by_command[p["command"]]["field"]], p["id"])

    def test_both_orders_occur(self):
        pairs = main_fx()["pairs"]
        self.assertEqual(sum(1 for p in pairs if p["expected_a"] == an.PERMIT), 6)

    def test_extras_are_unbalanced_toward_permit(self):
        extras = main_fx()["extras"]
        self.assertEqual(sum(1 for x in extras if x["expected"] == an.PERMIT), 8)
        self.assertEqual(sum(1 for x in extras if x["expected"] == an.REFUSE), 3)

    def test_item_classes(self):
        its = an.items(main_fx())
        self.assertEqual(sum(1 for i in its if i["expected"] == an.PERMIT), 20)
        self.assertEqual(sum(1 for i in its if i["expected"] == an.REFUSE), 15)

    def test_all_four_operators_and_each_command_twice(self):
        fx = main_fx()
        self.assertEqual({r["op"] for r in fx["rules"]}, {"lt", "le", "gt", "ge"})
        for r in fx["rules"]:
            self.assertEqual(sum(1 for p in fx["pairs"] if p["command"] == r["command"]), 2, r["command"])

    def test_boundary_pairs_sit_on_the_limit(self):
        fx = main_fx()
        for r in fx["rules"]:
            edge = [p for p in fx["pairs"] if p["command"] == r["command"]
                    and {p["state_a"][r["field"]], p["state_b"][r["field"]]} & {r["limit"], r["limit"] - 1, r["limit"] + 1}]
            self.assertTrue(edge, r["command"])

    def test_item_order_and_ids(self):
        its = an.items(main_fx())
        self.assertEqual([i["id"] for i in its[:4]], ["p01.a", "p01.b", "p02.a", "p02.b"])
        self.assertEqual(its[24]["id"], "x01")
        self.assertIsNone(its[24]["pair"])
        self.assertEqual(its[0]["pair"], "p01")

    def test_state_fields_belong_to_the_system(self):
        fx = main_fx()
        by_command = {r["command"]: r for r in fx["rules"]}
        for p in fx["pairs"]:
            self.assertEqual(sorted(p["state_a"]), sorted(fx["systems"][by_command[p["command"]]["system"]]))


class Operators(unittest.TestCase):
    CASES = {"lt": operator.lt, "le": operator.le, "gt": operator.gt, "ge": operator.ge}

    def test_each_operator_at_and_around_the_limit(self):
        for name, fn in self.CASES.items():
            rule = {"op": name, "limit": 10}
            for value in (9, 10, 11):
                self.assertEqual(an.decide(rule, value), an.PERMIT if fn(value, 10) else an.REFUSE, (name, value))

    def test_boundaries_are_exact(self):
        self.assertEqual(an.decide({"op": "lt", "limit": 10}, 10), an.REFUSE)
        self.assertEqual(an.decide({"op": "le", "limit": 10}, 10), an.PERMIT)
        self.assertEqual(an.decide({"op": "gt", "limit": 10}, 10), an.REFUSE)
        self.assertEqual(an.decide({"op": "ge", "limit": 10}, 10), an.PERMIT)

    def test_operator_table_is_exactly_four(self):
        self.assertEqual(sorted(an.OPS), ["ge", "gt", "le", "lt"])

    def test_decide_returns_only_permit_or_refuse(self):
        for name in an.OPS:
            for value in range(0, 21):
                self.assertIn(an.decide({"op": name, "limit": 10}, value), (an.PERMIT, an.REFUSE))


class Arms(unittest.TestCase):
    RULES = [{"id": "R1", "system": "s", "command": "start_x", "field": "f", "op": "ge", "limit": 10},
             {"id": "R2", "system": "s", "command": "halt_x", "field": "g", "op": "lt", "limit": 5}]

    def inp(self, command="start_x", rules=True, state=None):
        return {"command": command, "rules": self.RULES if rules else None, "state": state}

    def test_always_arms_ignore_everything(self):
        for state in (None, {"f": 0, "g": 0}, {"f": 99, "g": 99}):
            self.assertEqual(an.answer("always_permit", self.inp(state=state)), an.PERMIT)
            self.assertEqual(an.answer("always_refuse", self.inp(state=state)), an.REFUSE)

    def test_heuristic_reads_the_command_only(self):
        for command, expected in (("start_pump", an.PERMIT), ("open_valve", an.PERMIT), ("raise_rate", an.REFUSE),
                                  ("vent_steam", an.REFUSE), ("reverse_belt", an.REFUSE), ("restart_pump", an.REFUSE),
                                  ("pre_start_pump", an.REFUSE)):
            for state in (None, {"f": 0, "g": 0}, {"f": 50, "g": 50}):
                self.assertEqual(an.answer("command_heuristic", self.inp(command, state=state)), expected, command)
                self.assertEqual(an.answer("command_heuristic", self.inp(command, rules=False, state=state)), expected)

    def test_aware_abstains_without_state(self):
        self.assertEqual(an.answer("answerability_aware", self.inp()), an.ABSTAIN)

    def test_aware_abstains_without_rules(self):
        self.assertEqual(an.answer("answerability_aware", self.inp(rules=False, state={"f": 50, "g": 0})), an.ABSTAIN)

    def test_aware_abstains_when_the_needed_field_is_missing(self):
        self.assertEqual(an.answer("answerability_aware", self.inp(state={"g": 0})), an.ABSTAIN)
        self.assertEqual(an.answer("answerability_aware", self.inp(state={})), an.ABSTAIN)

    def test_aware_abstains_on_an_unknown_command(self):
        self.assertEqual(an.answer("answerability_aware", self.inp("mystery", state={"f": 50, "g": 0})), an.ABSTAIN)

    def test_aware_answers_when_the_needed_field_is_present(self):
        self.assertEqual(an.answer("answerability_aware", self.inp(state={"f": 10, "g": 0})), an.PERMIT)
        self.assertEqual(an.answer("answerability_aware", self.inp(state={"f": 9, "g": 0})), an.REFUSE)

    def test_aware_reads_the_field_the_rule_names(self):
        self.assertEqual(an.answer("answerability_aware", self.inp("halt_x", state={"f": 99, "g": 4})), an.PERMIT)
        self.assertEqual(an.answer("answerability_aware", self.inp("halt_x", state={"f": 0, "g": 5})), an.REFUSE)

    def test_aware_answers_with_only_the_needed_field_present(self):
        self.assertEqual(an.answer("answerability_aware", self.inp(state={"f": 10})), an.PERMIT)

    def test_evaluator_abstains_without_rules_or_state(self):
        self.assertEqual(an.answer("rule_evaluator", self.inp()), an.ABSTAIN)
        self.assertEqual(an.answer("rule_evaluator", self.inp(rules=False, state={"f": 50, "g": 0})), an.ABSTAIN)
        self.assertEqual(an.answer("rule_evaluator", self.inp(rules=False)), an.ABSTAIN)

    def test_evaluator_abstains_on_unknown_command_or_missing_field(self):
        self.assertEqual(an.answer("rule_evaluator", self.inp("mystery", state={"f": 50, "g": 0})), an.ABSTAIN)
        self.assertEqual(an.answer("rule_evaluator", self.inp(state={"g": 1})), an.ABSTAIN)

    def test_evaluator_applies_the_rule(self):
        self.assertEqual(an.answer("rule_evaluator", self.inp(state={"f": 10, "g": 0})), an.PERMIT)
        self.assertEqual(an.answer("rule_evaluator", self.inp(state={"f": 9, "g": 0})), an.REFUSE)
        self.assertEqual(an.answer("rule_evaluator", self.inp("halt_x", state={"f": 0, "g": 5})), an.REFUSE)
        self.assertEqual(an.answer("rule_evaluator", self.inp("halt_x", state={"f": 0, "g": 4})), an.PERMIT)

    def test_unknown_arm_is_refused(self):
        with self.assertRaises(ValueError):
            an.answer("oracle", self.inp())

    def test_arm_table_matches_arm_list(self):
        self.assertEqual(sorted(an.ARM_FUNCTIONS), sorted(an.ARMS))
        self.assertEqual(len(an.ARMS), 5)

    def test_each_arm_name_runs_its_own_function(self):
        for arm in an.ARMS:
            self.assertEqual(an.ARM_FUNCTIONS[arm].__name__, "arm_" + arm)

    def test_answerable_needs_rules_state_and_the_field(self):
        self.assertFalse(an.answerable(self.inp()))
        self.assertFalse(an.answerable(self.inp(rules=False, state={"f": 1})))
        self.assertFalse(an.answerable(self.inp(state={"g": 1})))
        self.assertFalse(an.answerable(self.inp("mystery", state={"f": 1})))
        self.assertTrue(an.answerable(self.inp(state={"f": 1})))
        self.assertEqual(an.needed_field(self.inp("halt_x")), "g")
        self.assertIsNone(an.needed_field(self.inp(rules=False)))


class Inputs(unittest.TestCase):
    def test_conditions_expose_exactly_their_fields(self):
        fx = main_fx()
        item = an.items(fx)[0]
        a = an.build_input(fx, item, "command_only")
        b = an.build_input(fx, item, "command_rules")
        c = an.build_input(fx, item, "command_rules_state")
        self.assertEqual((a["rules"], a["state"]), (None, None))
        self.assertEqual((b["rules"] is fx["rules"], b["state"]), (True, None))
        self.assertEqual((c["rules"] is fx["rules"], c["state"] == item["state"]), (True, True))
        for inp in (a, b, c):
            self.assertEqual(inp["command"], item["command"])
            self.assertEqual(sorted(inp), ["command", "rules", "state"])

    def test_input_never_carries_the_expected_answer(self):
        fx = main_fx()
        for it in an.items(fx):
            for c in an.CONDITIONS:
                self.assertNotIn("expected", an.build_input(fx, it, c))

    def test_condition_inputs_table(self):
        self.assertEqual(an.CONDITION_INPUTS["command_only"], ("command",))
        self.assertEqual(an.CONDITION_INPUTS["command_rules"], ("command", "rules"))
        self.assertEqual(an.CONDITION_INPUTS["command_rules_state"], ("command", "rules", "state"))
        self.assertEqual(list(an.CONDITIONS), ["command_only", "command_rules", "command_rules_state"])

    def test_unknown_condition_is_refused(self):
        fx = main_fx()
        with self.assertRaises(ValueError):
            an.build_input(fx, an.items(fx)[0], "everything")

    def test_both_sides_of_a_pair_see_the_same_input_without_state(self):
        fx = main_fx()
        for c in NO_STATE:
            for p in fx["pairs"]:
                a = an.build_input(fx, {"command": p["command"], "state": p["state_a"]}, c)
                b = an.build_input(fx, {"command": p["command"], "state": p["state_b"]}, c)
                self.assertEqual(a, b, (c, p["id"]))

    def test_the_two_sides_differ_once_state_is_added(self):
        fx = main_fx()
        for p in fx["pairs"]:
            a = an.build_input(fx, {"command": p["command"], "state": p["state_a"]}, "command_rules_state")
            b = an.build_input(fx, {"command": p["command"], "state": p["state_b"]}, "command_rules_state")
            self.assertNotEqual(a, b, p["id"])


class Scoring(unittest.TestCase):
    def test_abstain_is_never_correct(self):
        fx = tiny([("q1", 20, 0, "PERMIT", "REFUSE")])
        s = an.score(fx, "answerability_aware", "command_only")
        self.assertEqual((s["raw"], s["balanced"], s["pairs_correct"], s["abstentions"]), (0, 0, 0, 2))

    def test_raw_is_correct_over_all_items(self):
        fx = tiny([("q1", 20, 0, "PERMIT", "REFUSE")], [("x1", 30, "PERMIT"), ("x2", 40, "PERMIT")])
        s = an.score(fx, "always_permit", "command_only")
        self.assertEqual(s["raw"], Fraction(3, 4))

    def test_balanced_is_the_mean_of_the_two_recalls(self):
        fx = tiny([("q1", 20, 0, "PERMIT", "REFUSE")], [("x1", 30, "PERMIT"), ("x2", 40, "PERMIT"), ("x3", 2, "REFUSE")])
        s = an.score(fx, "always_permit", "command_only")
        self.assertEqual(s["balanced"], Fraction(1, 2))
        s = an.score(fx, "rule_evaluator", "command_rules_state")
        self.assertEqual(s["balanced"], 1)

    def test_balanced_uses_each_class_recall_not_counts(self):
        fx = tiny([("q1", 20, 0, "PERMIT", "REFUSE")], [("x1", 30, "PERMIT"), ("x2", 40, "PERMIT"), ("x3", 2, "REFUSE")])
        s = an.score(fx, "always_refuse", "command_only")
        # PERMIT items: 3, none right; REFUSE items: 2, both right
        self.assertEqual(s["raw"], Fraction(2, 5))
        self.assertEqual(s["balanced"], Fraction(1, 2))

    def test_pair_counts_only_when_both_sides_are_right(self):
        fx = tiny([("q1", 20, 0, "PERMIT", "REFUSE"), ("q2", 0, 20, "REFUSE", "PERMIT")])
        s = an.score(fx, "always_permit", "command_only")
        self.assertEqual(s["pairs_correct"], 0)
        self.assertEqual(s["raw"], Fraction(1, 2))

    def test_one_side_right_is_not_a_pair(self):
        fx = tiny([("q1", 20, 0, "PERMIT", "REFUSE")])
        s = an.score(fx, "always_refuse", "command_only")
        self.assertEqual((s["raw"], s["pairs_correct"]), (Fraction(1, 2), 0))

    def test_extras_never_count_as_pairs(self):
        fx = tiny([("q1", 20, 0, "PERMIT", "REFUSE")], [("x1", 30, "PERMIT")])
        s = an.score(fx, "rule_evaluator", "command_rules_state")
        self.assertEqual((s["pairs_correct"], s["pairs_total"], s["raw"]), (1, 1, 1))

    def test_answerable_items_counts_inputs_not_answers(self):
        fx = tiny([("q1", 20, 0, "PERMIT", "REFUSE")], [("x1", 30, "PERMIT")])
        self.assertEqual(an.score(fx, "always_permit", "command_only")["answerable_items"], "0/3")
        self.assertEqual(an.score(fx, "always_permit", "command_rules")["answerable_items"], "0/3")
        self.assertEqual(an.score(fx, "always_permit", "command_rules_state")["answerable_items"], "3/3")

    def test_fraction_text(self):
        self.assertEqual(an._frac(Fraction(4, 7)), "4/7")
        self.assertEqual(an._frac(Fraction(2, 4)), "1/2")
        self.assertEqual(an._frac(Fraction(0)), "0/1")
        self.assertEqual(an._frac(Fraction(1)), "1/1")

    def test_decimal_text_rounds_half_up_to_four_places(self):
        self.assertEqual(an._dec(Fraction(4, 7)), "0.5714")
        self.assertEqual(an._dec(Fraction(3, 7)), "0.4286")
        self.assertEqual(an._dec(Fraction(1, 2)), "0.5000")
        self.assertEqual(an._dec(Fraction(0)), "0.0000")
        self.assertEqual(an._dec(Fraction(1)), "1.0000")
        self.assertEqual(an._dec(Fraction(1, 3)), "0.3333")
        self.assertEqual(an._dec(Fraction(2, 3)), "0.6667")
        self.assertEqual(an._dec(Fraction(1, 20000)), "0.0001")
        self.assertEqual(an._dec(Fraction(1, 40000)), "0.0000")

    def test_run_has_every_arm_under_every_condition(self):
        result = an.run(main_fx())
        self.assertEqual([(r["condition"], r["arm"]) for r in result["results"]],
                         [(c, a) for c in an.CONDITIONS for a in an.ARMS])

    def test_known_main_scores(self):
        rows = {(r["condition"], r["arm"]): r for r in an.run(main_fx())["results"]}
        self.assertEqual(rows[("command_only", "always_permit")]["raw"], "4/7")
        self.assertEqual(rows[("command_only", "always_refuse")]["raw"], "3/7")
        self.assertEqual(rows[("command_only", "command_heuristic")]["raw"], "19/35")
        self.assertEqual(rows[("command_only", "command_heuristic")]["balanced"], "13/24")
        self.assertEqual(rows[("command_only", "answerability_aware")]["abstentions"], 35)
        self.assertEqual(rows[("command_rules_state", "answerability_aware")]["pairs_correct"], 12)
        self.assertEqual(rows[("command_rules_state", "command_heuristic")]["pairs_correct"], 0)

    def test_abstaining_scores_below_guessing_on_raw_accuracy(self):
        rows = {(r["condition"], r["arm"]): r for r in an.run(main_fx())["results"]}
        self.assertEqual(rows[("command_only", "answerability_aware")]["raw"], "0/1")
        self.assertLess(Fraction(0), Fraction(4, 7))
        self.assertEqual(rows[("command_only", "answerability_aware")]["abstentions"], 35)

    def test_state_blind_arms_do_not_change_when_state_arrives(self):
        rows = {(r["condition"], r["arm"]): r for r in an.run(main_fx())["results"]}
        for arm in ("always_permit", "always_refuse", "command_heuristic"):
            base = rows[("command_only", arm)]
            for c in ("command_rules", "command_rules_state"):
                other = rows[(c, arm)]
                for k in ("raw", "balanced", "pairs_correct", "abstentions"):
                    self.assertEqual(base[k], other[k], (arm, c, k))


class DoneWhen(unittest.TestCase):
    def test_a_without_state_no_arm_gets_both_sides_of_any_pair(self):
        fx = main_fx()
        for c in NO_STATE:
            for arm in an.ARMS:
                s = an.score(fx, arm, c)
                self.assertEqual(s["pairs_correct"], 0, (c, arm))
                for p in fx["pairs"]:
                    self.assertEqual(s["answers"][p["id"] + ".a"], s["answers"][p["id"] + ".b"], (c, arm, p["id"]))

    def test_a_an_answering_arm_is_wrong_on_at_least_one_side_of_every_pair(self):
        fx = main_fx()
        for c in NO_STATE:
            for arm in an.ARMS:
                s = an.score(fx, arm, c)
                for p in fx["pairs"]:
                    right = [s["answers"][p["id"] + ".a"] == p["expected_a"], s["answers"][p["id"] + ".b"] == p["expected_b"]]
                    self.assertLessEqual(sum(right), 1, (c, arm, p["id"]))

    def test_a_every_state_blind_function_of_the_command_fails_every_pair(self):
        fx = main_fx()
        commands = sorted({p["command"] for p in fx["pairs"]})
        for mask in range(2 ** len(commands)):
            table = {c: (an.PERMIT if mask >> i & 1 else an.REFUSE) for i, c in enumerate(commands)}
            for p in fx["pairs"]:
                self.assertFalse(table[p["command"]] == p["expected_a"] and table[p["command"]] == p["expected_b"])

    def test_a_check_in_the_report(self):
        a = an.run(main_fx())["checks"]["a_no_state_no_arm_gets_a_pair"]
        self.assertEqual((a["holds"], a["both_sides_have_identical_input"], a["max_pairs_correct_without_state"]),
                         (True, True, 0))

    def test_b_raw_gap_with_equal_balanced_accuracy_and_no_pairs(self):
        fx = main_fx()
        for c in an.CONDITIONS:
            p = an.score(fx, "always_permit", c)
            r = an.score(fx, "always_refuse", c)
            self.assertEqual(p["raw"], Fraction(4, 7))
            self.assertEqual(r["raw"], Fraction(3, 7))
            self.assertEqual(p["raw"] - r["raw"], Fraction(1, 7))
            self.assertEqual((p["balanced"], r["balanced"]), (Fraction(1, 2), Fraction(1, 2)))
            self.assertEqual((p["pairs_correct"], r["pairs_correct"]), (0, 0))

    def test_b_the_gap_comes_from_the_unbalanced_items(self):
        fx = main_fx()
        fx["extras"] = []
        p = an.score(fx, "always_permit", "command_only")
        r = an.score(fx, "always_refuse", "command_only")
        self.assertEqual((p["raw"], r["raw"]), (Fraction(1, 2), Fraction(1, 2)))
        self.assertEqual((p["balanced"], r["balanced"]), (Fraction(1, 2), Fraction(1, 2)))

    def test_b_a_more_unbalanced_set_widens_the_gap_and_leaves_balanced_alone(self):
        pairs = [("q1", 20, 0, "PERMIT", "REFUSE")]
        extras = [("x%d" % i, 30 + i, "PERMIT") for i in range(8)]
        fx = tiny(pairs, extras)
        p = an.score(fx, "always_permit", "command_only")
        r = an.score(fx, "always_refuse", "command_only")
        self.assertEqual((p["raw"], r["raw"]), (Fraction(9, 10), Fraction(1, 10)))
        self.assertEqual((p["balanced"], r["balanced"]), (Fraction(1, 2), Fraction(1, 2)))
        self.assertEqual((p["pairs_correct"], r["pairs_correct"]), (0, 0))

    def test_b_check_in_the_report(self):
        b = an.run(main_fx())["checks"]["b_always_arms_raw_gap_with_balanced_half_and_no_pairs"]
        self.assertTrue(b["holds"])
        self.assertEqual((b["raw_always_permit"], b["raw_always_refuse"], b["raw_gap"]), ("4/7", "3/7", "1/7"))
        self.assertEqual((b["balanced_always_permit"], b["balanced_always_refuse"]), ("1/2", "1/2"))
        self.assertEqual((b["pairs_correct_always_permit"], b["pairs_correct_always_refuse"]), (0, 0))

    def test_c_rule_evaluator_with_rules_and_state_gets_every_pair(self):
        fx = main_fx()
        s = an.score(fx, "rule_evaluator", "command_rules_state")
        self.assertEqual((s["pairs_correct"], s["pairs_total"], s["raw"], s["balanced"]), (12, 12, 1, 1))
        for it in an.items(fx):
            self.assertEqual(s["answers"][it["id"]], it["expected"], it["id"])

    def test_c_expected_answers_match_an_independent_reading_of_the_rules(self):
        fx = main_fx()
        table = {"lt": operator.lt, "le": operator.le, "gt": operator.gt, "ge": operator.ge}
        for it in an.items(fx):
            rule = next(r for r in fx["rules"] if r["command"] == it["command"])
            want = "PERMIT" if table[rule["op"]](it["state"][rule["field"]], rule["limit"]) else "REFUSE"
            self.assertEqual(want, it["expected"], it["id"])

    def test_c_the_aware_arm_matches_the_evaluator_on_this_fixture(self):
        fx = main_fx()
        a = an.score(fx, "answerability_aware", "command_rules_state")
        e = an.score(fx, "rule_evaluator", "command_rules_state")
        self.assertEqual(a["answers"], e["answers"])

    def test_c_no_state_blind_arm_gets_every_pair_even_with_state_in_the_input(self):
        fx = main_fx()
        for arm in ("always_permit", "always_refuse", "command_heuristic"):
            self.assertEqual(an.score(fx, arm, "command_rules_state")["pairs_correct"], 0, arm)

    def test_c_check_reads_the_rule_evaluator_arm(self):
        real = an.ARM_FUNCTIONS["rule_evaluator"]
        an.ARM_FUNCTIONS["rule_evaluator"] = an.arm_always_refuse
        try:
            c = an.run(main_fx())["checks"]["c_rule_evaluator_with_rules_and_state_gets_every_pair"]
        finally:
            an.ARM_FUNCTIONS["rule_evaluator"] = real
        self.assertFalse(c["holds"])
        self.assertEqual(c["pairs_correct"], 0)

    def test_c_check_in_the_report_carries_the_scope_note(self):
        c = an.run(main_fx())["checks"]["c_rule_evaluator_with_rules_and_state_gets_every_pair"]
        self.assertTrue(c["holds"])
        self.assertEqual((c["pairs_correct"], c["pairs_total"]), (12, 12))
        self.assertIn("fixture completeness check only", c["scope"])
        self.assertIn("independent safety", c["scope"])
        self.assertEqual(an.run(main_fx())["scope_note"], c["scope"])

    def test_c_a_broken_expected_answer_breaks_the_check(self):
        fx = main_fx()
        fx["pairs"][0]["expected_a"], fx["pairs"][0]["expected_b"] = fx["pairs"][0]["expected_b"], fx["pairs"][0]["expected_a"]
        result = an.run(fx)
        self.assertFalse(result["checks"]["c_rule_evaluator_with_rules_and_state_gets_every_pair"]["holds"])

    def test_a_check_fails_if_state_leaks_into_the_stateless_conditions(self):
        real = an.build_input

        def leaky(fx, item, condition):
            return real(fx, item, "command_rules_state")

        an.build_input = leaky
        try:
            a = an.run(main_fx())["checks"]["a_no_state_no_arm_gets_a_pair"]
        finally:
            an.build_input = real
        self.assertFalse(a["holds"])
        self.assertFalse(a["both_sides_have_identical_input"])
        self.assertEqual(a["max_pairs_correct_without_state"], 12)

    def test_b_check_fails_without_the_unbalanced_extras(self):
        fx = main_fx()
        fx["extras"] = []
        b = an.run(fx)["checks"]["b_always_arms_raw_gap_with_balanced_half_and_no_pairs"]
        self.assertFalse(b["holds"])
        self.assertEqual(b["raw_gap"], "0/1")

    def test_b_gap_is_reported_as_a_positive_distance_either_way(self):
        fx = tiny([("q1", 20, 0, "PERMIT", "REFUSE")], [("x%d" % i, 1, "REFUSE") for i in range(6)])
        b = an.run(fx)["checks"]["b_always_arms_raw_gap_with_balanced_half_and_no_pairs"]
        self.assertEqual((b["raw_always_permit"], b["raw_always_refuse"], b["raw_gap"]), ("1/8", "7/8", "3/4"))
        self.assertTrue(b["holds"])

    def test_c_check_needs_every_item_not_only_every_pair(self):
        fx = main_fx()
        fx["extras"][0]["expected"] = an.REFUSE
        c = an.run(fx)["checks"]["c_rule_evaluator_with_rules_and_state_gets_every_pair"]
        self.assertEqual((c["pairs_correct"], c["pairs_total"]), (12, 12))
        self.assertFalse(c["holds"])

    def test_d_no_network_and_no_paid_api(self):
        for name in sorted(os.listdir(HERE)):
            if name.endswith(".py"):
                with open(os.path.join(HERE, name), encoding="utf-8") as fh:
                    src = fh.read()
                for word in ("socket", "urllib", "http", "ssl", "requests", "ftplib", "smtplib", "asyncio", "openai",
                             "anthropic", "api_key", "API_KEY"):
                    if name == "test_answerability.py":
                        continue
                    self.assertNotIn(word, src, (name, word))

    def test_d_checks_all_hold_on_the_main_fixture(self):
        checks = an.run(main_fx())["checks"]
        self.assertEqual({k: v["holds"] for k, v in checks.items()},
                         {"a_no_state_no_arm_gets_a_pair": True,
                          "b_always_arms_raw_gap_with_balanced_half_and_no_pairs": True,
                          "c_rule_evaluator_with_rules_and_state_gets_every_pair": True})


class Validation(unittest.TestCase):
    def test_table(self):
        def pair(i, k, v):
            return lambda d: d["pairs"][i].__setitem__(k, v)

        def rule(i, k, v):
            return lambda d: d["rules"][i].__setitem__(k, v)

        cases = [
            ("not_json", None),
            ("bad_version", lambda d: d.__setitem__("fixture_version", 2)),
            ("bad_version", lambda d: d.__setitem__("fixture_version", True)),
            ("bad_version", lambda d: d.__setitem__("fixture_version", "1")),
            ("missing_key", lambda d: d.pop("extras")),
            ("missing_key", lambda d: d["pairs"][0].pop("state_b")),
            ("missing_key", lambda d: d["rules"][0].pop("op")),
            ("missing_key", lambda d: d["extras"][0].pop("expected")),
            ("unknown_key", lambda d: d.__setitem__("on_expiry", "DENY")),
            ("unknown_key", rule(0, "note", "x")),
            ("unknown_key", pair(0, "note", "x")),
            ("unknown_key", lambda d: d["extras"][0].__setitem__("note", "x")),
            ("wrong_type", lambda d: d.__setitem__("pairs", {})),
            ("wrong_type", lambda d: d.__setitem__("pairs", [])),
            ("wrong_type", lambda d: d.__setitem__("rules", [])),
            ("wrong_type", lambda d: d.__setitem__("extras", None)),
            ("wrong_type", lambda d: d.__setitem__("systems", {})),
            ("wrong_type", lambda d: d.__setitem__("systems", [])),
            ("wrong_type", lambda d: d["systems"].__setitem__("boiler", [])),
            ("wrong_type", lambda d: d["systems"].__setitem__("boiler", "water_level")),
            ("wrong_type", lambda d: d["pairs"].append(7)),
            ("wrong_type", rule(0, "limit", 1.5)),
            ("wrong_type", rule(0, "limit", True)),
            ("wrong_type", pair(0, "state_a", [1, 2, 3])),
            ("wrong_type", lambda d: d["pairs"][0]["state_a"].__setitem__("tank_level", 3.5)),
            ("wrong_type", lambda d: d["pairs"][0]["state_a"].__setitem__("tank_level", True)),
            ("wrong_type", lambda d: d["pairs"][0]["state_a"].__setitem__("tank_level", "5")),
            ("wrong_type", lambda d: d["pairs"][0]["state_a"].__setitem__("tank_level", None)),
            ("bad_value", lambda d: d["pairs"][0]["state_a"].__setitem__("tank_level", -1)),
            ("bad_value", lambda d: d["pairs"][0]["state_a"].__setitem__("tank_level", 100001)),
            ("bad_value", rule(0, "limit", -5)),
            ("bad_value", rule(0, "limit", 10 ** 9)),
            ("bad_id", pair(0, "id", "p 01")),
            ("bad_id", pair(0, "id", "p01\n")),
            ("bad_id", pair(0, "id", "")),
            ("bad_id", pair(0, "id", "p" * 41)),
            ("bad_id", pair(0, "id", "\ud800")),
            ("bad_id", pair(0, "id", "p01\u00e9")),
            ("bad_id", pair(0, "id", 1)),
            ("bad_id", pair(0, "command", "start pump")),
            ("bad_id", rule(0, "id", "R 1")),
            ("bad_id", rule(0, "system", "pump station")),
            ("bad_id", rule(0, "field", "tank level")),
            ("bad_id", rule(0, "command", "")),
            ("bad_id", lambda d: d["systems"].__setitem__("\ud800", ["a"])),
            ("bad_id", lambda d: d["systems"]["boiler"].append("flue temp")),
            ("bad_id", lambda d: d["extras"][0].__setitem__("id", "x 1")),
            ("duplicate_name", pair(1, "id", "p01")),
            ("duplicate_name", lambda d: d["extras"][0].__setitem__("id", "p01")),
            ("duplicate_name", lambda d: d["extras"][1].__setitem__("id", "x01")),
            ("duplicate_name", rule(1, "command", "start_pump")),
            ("duplicate_name", rule(1, "id", "R01")),
            ("duplicate_name", lambda d: d["systems"]["boiler"].append("water_level")),
            ("unknown_system", rule(0, "system", "furnace")),
            ("unknown_field", rule(0, "field", "water_level")),
            ("unknown_op", rule(0, "op", "eq")),
            ("unknown_op", rule(0, "op", "GE")),
            ("unknown_op", rule(0, "op", 5)),
            ("unknown_command", pair(0, "command", "stop_everything")),
            ("unknown_command", lambda d: d["extras"][0].__setitem__("command", "stop_everything")),
            ("bad_answer", pair(0, "expected_a", "ABSTAIN")),
            ("bad_answer", pair(0, "expected_b", "permit")),
            ("bad_answer", pair(0, "expected_a", None)),
            ("bad_answer", pair(0, "expected_a", True)),
            ("bad_answer", lambda d: d["extras"][0].__setitem__("expected", "GRANT")),
            ("pair_not_opposite", pair(0, "expected_b", "PERMIT")),
            ("pair_not_opposite", pair(0, "expected_a", "REFUSE")),
            ("same_state", lambda d: d["pairs"][0].__setitem__("state_b", dict(d["pairs"][0]["state_a"]))),
            ("bad_state", lambda d: d["pairs"][0]["state_a"].pop("pump_temp")),
            ("bad_state", lambda d: d["pairs"][0]["state_a"].__setitem__("water_level", 3)),
            ("bad_state", lambda d: d["pairs"][0].__setitem__("state_a", {})),
            ("bad_state", lambda d: d["pairs"][0].__setitem__("state_a", dict(d["pairs"][8]["state_a"]))),
            ("bad_state", lambda d: d["extras"][0]["state"].pop("line_pressure")),
            ("bad_state", lambda d: d["pairs"][0].__setitem__("state_a", {"\ud800": 1, "line_pressure": 2, "pump_temp": 3})),
        ]
        for code, mutate in cases:
            if mutate is None:
                with self.assertRaises(an.AnswerError) as cm:
                    an.parse("{nope")
                self.assertEqual(cm.exception.code, code)
            else:
                self.assertEqual(code_of(self, mutate), code, code)

    def test_size_constants_are_pinned(self):
        self.assertEqual((an.MAX_ITEMS, an.MAX_NAMES, an.MAX_BYTES, an.MAX_VALUE), (200, 20, 1000000, 100000))

    def test_list_limits_are_inclusive(self):
        root = raw("main.json")
        root["extras"] = [dict(root["extras"][0], id="y%d" % i) for i in range(an.MAX_ITEMS)]
        self.assertEqual(len(an.validate(root)["extras"]), an.MAX_ITEMS)
        root["extras"].append(dict(root["extras"][0], id="y_last"))
        with self.assertRaises(an.AnswerError) as cm:
            an.validate(root)
        self.assertEqual(cm.exception.code, "wrong_type")

    def test_system_and_field_limits_are_inclusive(self):
        root = raw("main.json")
        root["systems"]["boiler"] = ["f%d" % i for i in range(an.MAX_NAMES)]
        root["rules"][2]["field"] = "f0"
        root["rules"][3]["field"] = "f1"
        root["pairs"] = [p for p in root["pairs"] if p["command"] not in ("raise_firing_rate", "vent_steam")]
        root["extras"] = [x for x in root["extras"] if x["command"] not in ("raise_firing_rate", "vent_steam")]
        self.assertEqual(len(an.validate(root)["systems"]["boiler"]), an.MAX_NAMES)
        root["systems"]["boiler"].append("one_more")
        with self.assertRaises(an.AnswerError) as cm:
            an.validate(root)
        self.assertEqual(cm.exception.code, "wrong_type")

    def test_unhashable_op_and_answer_are_clean_errors(self):
        self.assertEqual(code_of(self, lambda d: d["rules"][0].__setitem__("op", ["ge"])), "unknown_op")
        self.assertEqual(code_of(self, lambda d: d["pairs"][0].__setitem__("expected_a", ["PERMIT"])), "bad_answer")
        self.assertEqual(code_of(self, lambda d: d["extras"][0].__setitem__("expected", {"a": 1})), "bad_answer")

    def test_validate_returns_a_copy_of_the_state(self):
        root = raw("main.json")
        fx = an.validate(root)
        root["pairs"][0]["state_a"]["tank_level"] = 1
        self.assertNotEqual(fx["pairs"][0]["state_a"]["tank_level"], 1)

    def test_extras_may_be_empty(self):
        root = raw("main.json")
        root["extras"] = []
        self.assertEqual(an.validate(root)["extras"], [])

    def test_state_value_bounds_are_inclusive(self):
        root = raw("main.json")
        root["pairs"][0]["state_a"]["tank_level"] = 0
        root["pairs"][0]["state_b"]["tank_level"] = an.MAX_VALUE
        an.validate(root)

    def test_state_keys_may_come_in_any_order(self):
        root = raw("main.json")
        root["pairs"][0]["state_a"] = dict(reversed(list(root["pairs"][0]["state_a"].items())))
        self.assertEqual(an.validate(root)["pairs"][0]["state_a"], raw("main.json")["pairs"][0]["state_a"])

    def test_duplicate_key_parse(self):
        with self.assertRaises(an.AnswerError) as cm:
            an.parse('{"a": 1, "a": 2}')
        self.assertEqual(cm.exception.code, "duplicate_key")

    def test_non_finite_constants_parse(self):
        for text in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(an.AnswerError) as cm:
                an.parse("[%s]" % text)
            self.assertEqual(cm.exception.code, "bad_number")

    def test_deep_nesting_and_bigint_parse(self):
        for text in ("[" * 100000, "9" * 5000):
            with self.assertRaises(an.AnswerError) as cm:
                an.parse(text)
            self.assertEqual(cm.exception.code, "not_json")

    def test_escape_helper_is_ascii_one_line(self):
        self.assertEqual(an._esc("a\nb\ud800"), '"a\\nb\\ud800"')

    def test_error_text(self):
        e = an.AnswerError("x", "y")
        self.assertEqual((e.code, e.detail, str(e)), ("x", "y", "x: y"))

    def test_load_fixture_errors(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            with open(p, "wb") as fh:
                fh.write(b"\xff\xfe{}")
            with self.assertRaises(an.AnswerError) as cm:
                an.load_fixture(p)
            self.assertEqual(cm.exception.code, "bad_encoding")
            with self.assertRaises(an.AnswerError) as cm:
                an.load_fixture(os.path.join(d, "missing.json"))
            self.assertEqual(cm.exception.code, "unreadable")
            with self.assertRaises(an.AnswerError) as cm:
                an.load_fixture(d)
            self.assertEqual(cm.exception.code, "unreadable")
            with open(p, "wb") as fh:
                fh.write(b" " * (an.MAX_BYTES + 1))
            with self.assertRaises(an.AnswerError) as cm:
                an.load_fixture(p)
            self.assertEqual(cm.exception.code, "too_large")

    def test_size_limit_is_inclusive(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            with open(p, "wb") as fh:
                fh.write(b" " * an.MAX_BYTES)
            with self.assertRaises(an.AnswerError) as cm:
                an.load_fixture(p)
            self.assertEqual(cm.exception.code, "not_json")


BAD_CODES = {
    "bad_answer_abstain.json": "bad_answer", "bad_answer_lowercase.json": "bad_answer",
    "bad_answer_synonym.json": "bad_answer", "bad_bigint.json": "not_json", "bad_bool_value.json": "wrong_type",
    "bad_deep_nesting.json": "not_json", "bad_duplicate_extra_id.json": "duplicate_name",
    "bad_duplicate_field.json": "duplicate_name", "bad_duplicate_key.json": "duplicate_key",
    "bad_duplicate_pair_id.json": "duplicate_name", "bad_duplicate_rule_command.json": "duplicate_name",
    "bad_duplicate_rule_id.json": "duplicate_name", "bad_empty_file.json": "not_json",
    "bad_empty_pairs.json": "wrong_type", "bad_empty_rules.json": "wrong_type",
    "bad_empty_system_fields.json": "wrong_type", "bad_empty_systems.json": "wrong_type",
    "bad_exponent_overflow.json": "wrong_type", "bad_extra_unknown_command.json": "unknown_command",
    "bad_extras_null.json": "wrong_type", "bad_float_limit.json": "wrong_type", "bad_float_value.json": "wrong_type",
    "bad_huge_value.json": "bad_value", "bad_id_long.json": "bad_id", "bad_id_newline.json": "bad_id",
    "bad_id_non_ascii.json": "bad_id", "bad_id_space.json": "bad_id", "bad_id_surrogate.json": "bad_id",
    "bad_infinity.json": "bad_number", "bad_invalid_utf8.json": "bad_encoding", "bad_missing_key.json": "missing_key",
    "bad_nan.json": "bad_number", "bad_negative_value.json": "bad_value", "bad_not_json.json": "not_json",
    "bad_not_object.json": "wrong_type", "bad_pair_not_opposite.json": "pair_not_opposite",
    "bad_pairs_not_list.json": "wrong_type", "bad_same_state.json": "same_state",
    "bad_state_extra_field.json": "bad_state", "bad_state_missing_field.json": "bad_state",
    "bad_state_not_object.json": "wrong_type", "bad_state_surrogate_key.json": "bad_state",
    "bad_state_wrong_system.json": "bad_state", "bad_string_value.json": "wrong_type",
    "bad_system_surrogate_name.json": "bad_id", "bad_top_unknown_key.json": "unknown_key",
    "bad_unknown_command.json": "unknown_command", "bad_unknown_field.json": "unknown_field",
    "bad_unknown_key.json": "unknown_key", "bad_unknown_op.json": "unknown_op",
    "bad_unknown_system.json": "unknown_system", "bad_version.json": "bad_version",
    "bad_version_bool.json": "bad_version",
}


class Cli(unittest.TestCase):
    def test_main_exits_zero_with_the_report_only(self):
        rc, out, err = cli(os.path.join("fixtures", "main.json"))
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(out, an.report(main_fx()))
        self.assertTrue(out.endswith("}\n"))
        out.encode("ascii")
        self.assertTrue(json.loads(out)["checks"]["c_rule_evaluator_with_rules_and_state_gets_every_pair"]["holds"])

    def test_report_is_deterministic(self):
        self.assertEqual(cli(os.path.join("fixtures", "main.json")), cli(os.path.join("fixtures", "main.json")))

    def test_report_keys_are_sorted(self):
        text = an.report(main_fx())
        self.assertEqual(text, json.dumps(json.loads(text), indent=1, sort_keys=True, ensure_ascii=True) + "\n")

    def test_every_bad_fixture_exits_two_with_one_error_line(self):
        names = sorted(n for n in os.listdir(FIX) if n.startswith("bad_"))
        self.assertEqual(len(names), 53)
        self.assertEqual(names, sorted(BAD_CODES))
        for n in names:
            rc, out, err = cli(os.path.join("fixtures", n))
            self.assertEqual((rc, out), (2, ""), n)
            self.assertTrue(err.startswith("ERROR %s: " % BAD_CODES[n]), (n, err))
            self.assertEqual(err.count("\n"), 1, n)
            self.assertNotIn("Traceback", err)
            err.encode("ascii")

    def test_every_bad_fixture_raises_the_same_code_through_the_loader(self):
        for n, code in BAD_CODES.items():
            with self.assertRaises(an.AnswerError) as cm:
                an.load_fixture(os.path.join(FIX, n))
            self.assertEqual(cm.exception.code, code, n)

    def test_bad_fixtures_each_break_one_rule_of_a_good_fixture(self):
        good = raw("main.json")
        for n in sorted(BAD_CODES):
            if n in ("bad_not_json.json", "bad_empty_file.json", "bad_not_object.json", "bad_invalid_utf8.json",
                     "bad_deep_nesting.json", "bad_bigint.json", "bad_duplicate_key.json", "bad_nan.json",
                     "bad_infinity.json", "bad_exponent_overflow.json"):
                continue
            self.assertNotEqual(json.dumps(raw(n)), json.dumps(good), n)

    def test_the_surrogate_fixture_holds_the_escape_not_the_character(self):
        with open(os.path.join(FIX, "bad_id_surrogate.json"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("\\ud800", text)

    def test_usage_errors(self):
        for args in ((), ("a", "b")):
            rc, out, err = cli(*args)
            self.assertEqual((rc, out), (2, ""))
            self.assertEqual(err, "ERROR usage: answerability.py FIXTURE.json\n")

    def test_missing_file(self):
        rc, out, err = cli("no_such_fixture.json")
        self.assertEqual((rc, out), (2, ""))
        self.assertEqual(err, "ERROR unreadable: file could not be read\n")

    def test_main_function_in_process(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = an.main(["answerability.py", os.path.join(FIX, "main.json")])
        self.assertEqual((rc, err.getvalue()), (0, ""))
        self.assertTrue(out.getvalue().startswith("{"))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = an.main(["answerability.py", os.path.join(FIX, "bad_version.json")])
        self.assertEqual((rc, out.getvalue()), (2, ""))
        self.assertEqual(err.getvalue().count("\n"), 1)

    def test_no_report_is_printed_when_the_input_is_bad(self):
        for n in ("bad_state_wrong_system.json", "bad_pair_not_opposite.json"):
            rc, out, err = cli(os.path.join("fixtures", n))
            self.assertEqual(out, "")

    def test_a_valid_fixture_with_no_perfect_evaluator_still_exits_zero(self):
        root = raw("main.json")
        root["pairs"][0]["expected_a"], root["pairs"][0]["expected_b"] = root["pairs"][0]["expected_b"], root["pairs"][0]["expected_a"]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "swapped.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(root, fh)
            rc, out, err = cli(p)
        self.assertEqual((rc, err), (0, ""))
        self.assertFalse(json.loads(out)["checks"]["c_rule_evaluator_with_rules_and_state_gets_every_pair"]["holds"])


class Demo(unittest.TestCase):
    def run_demo(self):
        p = subprocess.run([PY, "-B", os.path.join(HERE, "demo.py")], cwd=HERE, capture_output=True, text=True,
                           encoding="utf-8")
        self.assertEqual((p.returncode, p.stderr), (0, ""))
        return p.stdout

    def test_demo_is_deterministic(self):
        self.assertEqual(self.run_demo(), self.run_demo())

    def test_demo_shows_the_three_conditions_and_five_arms(self):
        out = self.run_demo()
        for c in an.CONDITIONS:
            self.assertIn("condition %s " % c, out)
        for a in an.ARMS:
            self.assertIn(a, out)

    def test_demo_shows_the_gap_the_pairs_and_the_scope_note(self):
        out = self.run_demo()
        self.assertIn("always_permit raw 4/7, always_refuse raw 3/7 (gap 1/7)", out)
        self.assertIn("balanced 1/2 and 1/2; correct pairs 0 and 0", out)
        self.assertIn("(c) rule_evaluator with rules and state: 12/12 pairs", out)
        self.assertIn("fixture completeness check only", out)
        self.assertIn("needed state field present in 0/35 items", out)
        self.assertIn("needed state field present in 35/35 items", out)

    def test_demo_is_ascii(self):
        self.run_demo().encode("ascii")


class Hygiene(unittest.TestCase):
    def source(self, name):
        with open(os.path.join(HERE, name), encoding="utf-8") as fh:
            return fh.read()

    def test_stdlib_imports_only(self):
        mods = set()
        for line in self.source("answerability.py").splitlines():
            if line.startswith(("import ", "from ")):
                mods.add(line.split()[1])
        self.assertEqual(mods, {"fractions", "json", "re", "sys"})

    def test_no_clock_no_randomness_no_hash(self):
        src = self.source("answerability.py")
        for word in ("hashlib", "hmac", "secrets", "time", "datetime", "random", "os", "subprocess", "threading"):
            self.assertNotIn("import " + word, src)

    def test_no_float_arithmetic_in_the_module(self):
        src = self.source("answerability.py")
        self.assertNotIn("float(", src)
        self.assertNotIn("round(", src)

    def test_no_expiry_or_timeout_concept(self):
        self.assertNotIn("expir", self.source("answerability.py").lower())
        self.assertNotIn("timeout", self.source("answerability.py").lower())

    def test_banned_words_and_paths_are_absent_from_every_file(self):
        banned = ["al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er"]
        paths = ["/work" + "space", "/t" + "mp", "/ho" + "me"]
        seen = 0
        for base, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                with open(os.path.join(base, name), "rb") as fh:
                    text = fh.read().decode("utf-8", "replace")
                seen += 1
                for word in banned:
                    self.assertNotIn(word.lower(), text.lower(), (name, word))
                for path in paths:
                    self.assertNotIn(path, text, (name, path))
        self.assertGreaterEqual(seen, 60)

    def test_decision_values(self):
        self.assertEqual((an.PERMIT, an.REFUSE, an.ABSTAIN), ("PERMIT", "REFUSE", "ABSTAIN"))
        self.assertEqual(an.EXPECTED, ("PERMIT", "REFUSE"))
        self.assertEqual(an.ARMS, ("always_permit", "always_refuse", "command_heuristic", "answerability_aware",
                                   "rule_evaluator"))

    def test_evidence_json(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            ev = json.load(fh)
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.24682")
        self.assertIn("arXiv nonexclusive-distrib 1.0", ev["paper"]["licence"])
        self.assertTrue(ev["paper"]["method_only"])
        self.assertEqual(ev["status"], "UNVERIFIED")
        claims = ev["on_unmeasured"]["claims"]
        self.assertGreaterEqual(len(claims), 6)
        self.assertEqual({c["status"] for c in claims}, {"UNVERIFIED"})
        self.assertEqual(len({c["id"] for c in claims}), len(claims))
        self.assertTrue(ev["measured"]["rule_evaluator_result_is_a_fixture_completeness_check"])
        self.assertFalse(ev["measured"]["independent_safety_test"])
        self.assertFalse(ev["network_used"])
        self.assertFalse(ev["paid_api_used"])

    def test_evidence_measured_numbers_match_the_run(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            ev = json.load(fh)
        result = an.run(main_fx())
        m = ev["measured"]
        self.assertEqual(m["fixture"], result["fixture"])
        self.assertEqual(m["raw_always_permit"], "4/7")
        self.assertEqual(m["raw_always_refuse"], "3/7")
        self.assertEqual(m["raw_gap"], "1/7")
        self.assertEqual(m["balanced_always_permit"], "1/2")
        self.assertEqual(m["balanced_always_refuse"], "1/2")
        self.assertEqual(m["pairs_correct_without_state"], 0)
        self.assertEqual(m["rule_evaluator_pairs_with_rules_and_state"], "12/12")
        rows = {(r["condition"], r["arm"]): r for r in result["results"]}
        self.assertEqual(m["raw_always_permit"], rows[("command_only", "always_permit")]["raw"])
        self.assertEqual(m["raw_always_refuse"], rows[("command_only", "always_refuse")]["raw"])

    def test_paper_numbers_appear_only_under_on_unmeasured(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            ev = json.load(fh)
        ev["on_unmeasured"] = None
        text = json.dumps(ev)
        for phrase in ("15 pairs", "32 percentage", "0 to 13", "four language models", "13 correct", "50% balanced"):
            self.assertNotIn(phrase, text)
        with open(os.path.join(HERE, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        for phrase in ("15 pairs", "32 percentage", "0 to 13", "four language models", "13 correct"):
            self.assertNotIn(phrase, readme)

    def test_every_listed_file_exists(self):
        for name in ("README.md", "answerability.py", "test_answerability.py", "demo.py", "mutants.py",
                     "evidence.json", os.path.join("fixtures", "main.json")):
            self.assertTrue(os.path.exists(os.path.join(HERE, name)), name)


class Docs(unittest.TestCase):
    def readme(self):
        with open(os.path.join(HERE, "README.md"), encoding="utf-8") as fh:
            return fh.read()

    def test_readme_says_the_evaluator_result_is_a_completeness_check(self):
        r = " ".join(self.readme().split())
        self.assertIn("fixture completeness check", r)
        self.assertIn("not an independent safety test", r)

    def test_readme_names_paper_licence_and_method_only(self):
        r = self.readme()
        self.assertIn("2611.24682", r)
        self.assertIn("arXiv nonexclusive-distrib 1.0", r)
        self.assertIn("method", r)
        self.assertIn("UNVERIFIED", r)
        self.assertIn("on_unmeasured", r)

    def test_readme_names_every_arm_condition_and_metric(self):
        r = self.readme()
        for word in an.ARMS + an.CONDITIONS:
            self.assertIn(word, r)
        for word in ("raw accuracy", "balanced accuracy", "paired score", "ABSTAIN", "PERMIT", "REFUSE"):
            self.assertIn(word, r)

    def test_readme_names_the_done_when_checks(self):
        r = self.readme()
        for tag in ("(a)", "(b)", "(c)", "(d)"):
            self.assertIn(tag, r)

    def test_readme_names_every_error_code(self):
        r = self.readme()
        for code in sorted(set(BAD_CODES.values())) + ["unreadable", "too_large"]:
            self.assertIn(code, r)

    def test_readme_states_the_exit_contract(self):
        r = " ".join(self.readme().split())
        self.assertIn("exits 2 with an empty stdout and one `ERROR <code>: <detail>` line on stderr", r)
        self.assertIn("exits 0", r)

    def test_readme_says_there_is_no_expiry_concept(self):
        r = " ".join(self.readme().split())
        self.assertIn("no expiry or timeout", r)


if __name__ == "__main__":
    unittest.main()
