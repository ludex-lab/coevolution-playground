"""Tests for the w21-info-friction method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
The quote check reads the source copies named in paper_evidence.json from
the directories listed in $W21FRICTION_SOURCES (os.pathsep separated).
There is no default: when the variable is unset, or a file is absent,
that check is skipped.
"""

import ast
import copy
import hashlib
import json
import os
import random
import re
import unittest

import fixtures as F
import info_friction as I

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W21FRICTION_SOURCES")
CODE = ("info_friction.py", "fixtures.py")
DAY_HEADER = "# experiments/2026-11-12\n"
ROW_START = "- [w21-info-friction](w21-info-friction/): "
FOOTER = "Do not merge experiment PRs without Ork review."


def day_readme():
    """Return (relative path, layout) of the day-index README.

    Repo layout: the day index is ../README.md in the 2026-11-12 folder.
    Flat draft: it is _day/README.md beside this file. The parent README is
    used only when it is present and starts with the day header, so an
    unrelated README above a flat draft folder is never picked up.
    """
    parent = os.path.join("..", "README.md")
    path = os.path.join(HERE, parent)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            if f.read().startswith(DAY_HEADER):
                return parent, "repo"
    return os.path.join("_day", "README.md"), "flat"


DAY, LAYOUT = day_readme()
ALL = ("README.md", "NOTICE", "info_friction.py", "fixtures.py",
       "test_info_friction.py", "mutants.py", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
STDLIB_PERMITTED = {"copy", "sys", "info_friction"}
o = F.o
# mutants.py sets this to the patched module text while a code mutant runs,
# so the source checks below see the code under test, not the file on disk.
SOURCE_OVERRIDE = None


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def module_source():
    """Text of info_friction.py under test (the patched text in mutants.py)."""
    if SOURCE_OVERRIDE is not None:
        return SOURCE_OVERRIDE
    return read("info_friction.py")


# Where the caller's task and observation mappings may appear, per function:
# function -> {name: permitted uses}. Uses: "field" (a subscript or .get
# with one constant field name), "member" (a constant "key" in / not in),
# "type" (type(name)), "iter" (for ... in name), or a callee name (passed as
# a positional argument to that function only).
FIELD_USES = {
    "evaluate": {"task": ("_evaluate",), "observations": ("_evaluate",)},
    "_evaluate": {"task": ("validate_task",),
                  "observations": ("validate_observations",)},
    "validate_task": {"task": ("field", "member", "_check_keys")},
    "validate_observations": {"obs": ("field", "member", "_check_keys"),
                              "observations": ("type", "iter")},
    "_check_keys": {"mapping": ("type", "iter")},
}
# function -> (mapping name, fields that must each be read exactly once)
FIELD_ONCE = {
    "validate_task": ("task", I.TASK_FIELDS),
    "validate_observations": ("obs", I.OBS_FIELDS),
}
# Names and attributes that would reach a mapping by another path.
BANNED_NAMES = ("locals", "vars", "globals", "getattr", "setattr", "eval",
                "exec", "compile", "__import__", "operator", "itemgetter",
                "attrgetter", "Mapping", "MutableMapping", "sys")
BANNED_ATTRS = ("items", "values", "keys", "copy", "setdefault", "pop",
                "popitem", "update", "__getitem__", "__dict__", "__iter__",
                "f_locals", "f_globals")


def _const_str(node):
    return isinstance(node, ast.Constant) and type(node.value) is str


def _use_of(node, parents):
    """Classify one load of a mapping name: (use, field or None)."""
    p = parents.get(node)
    if isinstance(p, ast.Subscript) and p.value is node and isinstance(p.ctx, ast.Load):
        if _const_str(p.slice):
            return "field", p.slice.value
        return "subscript", None
    if isinstance(p, ast.Attribute) and p.value is node:
        g = parents.get(p)
        if (p.attr == "get" and isinstance(g, ast.Call) and g.func is p
                and len(g.args) == 1 and not g.keywords and _const_str(g.args[0])):
            return "field", g.args[0].value
        return "attr:" + p.attr, None
    if (isinstance(p, ast.Compare) and p.comparators == [node] and len(p.ops) == 1
            and isinstance(p.ops[0], (ast.In, ast.NotIn)) and _const_str(p.left)):
        return "member", None
    if isinstance(p, ast.Call) and node in p.args and not p.keywords:
        if isinstance(p.func, ast.Name):
            if p.func.id == "type" and p.args == [node]:
                return "type", None
            return p.func.id, None
        return "call", None
    if isinstance(p, ast.For) and p.iter is node:
        return "iter", None
    return type(p).__name__, None


def field_read_problems(source):
    """Return a list of field-read problems in the module source (empty: clean)."""
    tree = ast.parse(source)
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            problems.append(("statement", type(node).__name__))
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            problems.append(("name", node.id))
        elif isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRS:
            problems.append(("attr", node.attr))
        elif isinstance(node, ast.Name) and node.id == "dict":
            p = parents.get(node)
            if not (isinstance(p, ast.Compare) and node in p.comparators):
                problems.append(("dict", type(p).__name__))
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for fname, uses in sorted(FIELD_USES.items()):
        if fname not in funcs:
            problems.append(("missing", fname))
            continue
        counts = {}
        for node in ast.walk(funcs[fname]):
            if not isinstance(node, ast.Name) or node.id not in uses:
                continue
            if isinstance(node.ctx, ast.Store):
                p = parents.get(node)
                if not (fname == "validate_observations" and node.id == "obs"
                        and isinstance(p, ast.For) and p.target is node):
                    problems.append((fname, node.id, "rebound"))
                continue
            use, field = _use_of(node, parents)
            if use not in uses[node.id]:
                problems.append((fname, node.id, use))
            elif use == "field":
                counts[field] = counts.get(field, 0) + 1
        if fname in FIELD_ONCE:
            name, fields = FIELD_ONCE[fname]
            for field in sorted(set(counts) | set(fields)):
                if field not in fields or counts.get(field, 0) != 1:
                    problems.append((fname, name, field, counts.get(field, 0)))
    return problems


def task(name="rescue"):
    for t in F.tasks():
        if t["task_id"] == name:
            return t
    raise KeyError(name)


class StrSub(str):
    def __eq__(self, other):
        return True

    __hash__ = str.__hash__


class IntSub(int):
    pass


class DictSub(dict):
    pass


class ListSub(list):
    pass


class BadKey(object):
    def __eq__(self, other):
        raise RuntimeError("eq")

    def __hash__(self):
        return hash("task_id")


class Boom(object):
    def __eq__(self, other):
        raise RuntimeError("eq")

    def __hash__(self):
        raise RuntimeError("hash")


DIRECT = [o(1, "radio-1", "location"), o(2, "radio-2", "count"), o(3, "map-1", "route")]


class TestDoneWhen(unittest.TestCase):

    def test_resolving_lowers_unresolved_without_tripping(self):
        rec = I.evaluate(task(), DIRECT, 3)
        self.assertEqual(rec["decision"], I.SUCCESS)
        counts = [s[2] for s in rec["signals"]]
        self.assertEqual(counts, [2, 1, 0])
        self.assertEqual([s[3] for s in rec["signals"]], [0, 0, 0])
        self.assertEqual([s[1] for s in rec["signals"]], [I.RESOLVED] * 3)
        one = I.evaluate(task(), DIRECT[:1], 1)
        self.assertEqual(one["decision"], I.CONTINUE)
        self.assertEqual(one["unresolved"], ("count", "route"))
        self.assertEqual(one["friction"], 0)

    def test_resolving_with_zero_bound(self):
        t = task()
        t["friction_bound"] = 0
        self.assertEqual(I.evaluate(t, DIRECT, 3)["decision"], I.SUCCESS)
        rec = I.evaluate(t, [o(1, "radio-1", "location"), o(2, "radio-1")], 2)
        self.assertEqual(rec["decision"], I.STOP)

    def test_repeat_only_loop_trips_and_cannot_succeed(self):
        obs = [o(i, "radio-1") for i in range(1, 6)]
        rec = I.evaluate(task(), obs, 5)
        self.assertEqual(rec["decision"], I.STOP)
        self.assertEqual(rec["reason"], I.FRICTION_BOUND)
        self.assertEqual(rec["friction"], 3)
        # the first sighting is exploration, the next three are recurrent
        self.assertEqual([s[1] for s in rec["signals"]],
                         [I.EXPLORE, I.RECURRENT, I.RECURRENT, I.RECURRENT])

    def test_stop_is_final_even_if_resolution_follows(self):
        obs = [o(1, "radio-1"), o(2, "radio-1"), o(3, "radio-1"), o(4, "radio-1"),
               o(5, "radio-1", "location"), o(6, "radio-2", "count"), o(7, "map-1", "route")]
        rec = I.evaluate(task(), obs, 7)
        self.assertEqual(rec["decision"], I.STOP)
        self.assertNotEqual(rec["decision"], I.SUCCESS)
        self.assertEqual(len(rec["signals"]), 4)

    def test_stop_read_before_deadline_expiry_after(self):
        obs = [o(1, "radio-1"), o(2, "radio-1"), o(3, "radio-1"), o(4, "radio-1")]
        self.assertEqual(I.evaluate(task(), obs, 4)["decision"], I.STOP)
        self.assertEqual(I.evaluate(task(), obs, 19)["decision"], I.STOP)
        # Expiry guard: at or after the deadline the declared on_expiry wins.
        rec = I.evaluate(task(), obs, 50)
        self.assertIs(rec["decision"], I.HOLD)
        self.assertEqual(rec["reason"], I.EXPIRED)
        self.assertEqual(rec["friction"], 3)

    def test_exploration_distinguished_from_recurrence_evidence_key(self):
        explore = [o(1, "radio-1", "location")] + [o(i, "drone-%d" % i) for i in range(2, 8)]
        rec = I.evaluate(task(), explore, 7)
        self.assertEqual(rec["decision"], I.CONTINUE)
        self.assertEqual(rec["friction"], 0)
        self.assertEqual([s[1] for s in rec["signals"]][1:], [I.EXPLORE] * 6)
        repeat = [o(1, "radio-1", "location")] + [o(i, "radio-1") for i in range(2, 8)]
        self.assertEqual(I.evaluate(task(), repeat, 7)["decision"], I.STOP)

    def test_exploration_resets_friction(self):
        obs = [o(1, "radio-1", "location"), o(2, "radio-1"), o(3, "radio-1"),
               o(4, "drone-1"), o(5, "radio-1"), o(6, "radio-1")]
        rec = I.evaluate(task(), obs, 6)
        self.assertEqual(rec["decision"], I.CONTINUE)
        self.assertEqual([s[3] for s in rec["signals"]], [0, 1, 2, 0, 1, 2])

    def test_resolution_resets_friction(self):
        obs = [o(1, "radio-1", "location"), o(2, "radio-1"), o(3, "radio-1"),
               o(4, "radio-1", "count"), o(5, "radio-1"), o(6, "radio-1")]
        rec = I.evaluate(task(), obs, 6)
        self.assertEqual(rec["decision"], I.CONTINUE)
        self.assertEqual([s[3] for s in rec["signals"]], [0, 1, 2, 0, 1, 2])

    def test_recurrent_evidence_can_still_resolve(self):
        obs = [o(1, "radio-1"), o(2, "radio-1", "location")]
        rec = I.evaluate(task(), obs, 2)
        self.assertEqual([s[1] for s in rec["signals"]], [I.EXPLORE, I.RESOLVED])

    def test_re_resolving_is_no_gain(self):
        obs = [o(1, "radio-1", "location"), o(2, "radio-9", "location")]
        rec = I.evaluate(task(), obs, 2)
        self.assertEqual(rec["signals"][1][1], I.EXPLORE)
        obs = [o(1, "radio-1", "location"), o(2, "radio-1", "location")]
        self.assertEqual(I.evaluate(task(), obs, 2)["signals"][1][1], I.RECURRENT)

    def test_declared_rule_follows_fixture_label(self):
        t = task("grid")
        same_key_new = [o(1, "cell-a", None, True), o(2, "cell-a", None, True),
                        o(3, "cell-a", None, True)]
        rec = I.evaluate(t, same_key_new, 3)
        self.assertEqual(rec["decision"], I.CONTINUE)
        self.assertEqual([s[1] for s in rec["signals"]], [I.EXPLORE] * 3)
        new_key_old = [o(1, "cell-x", None, False), o(2, "cell-y", None, False)]
        rec = I.evaluate(t, new_key_old, 2)
        self.assertEqual(rec["decision"], I.STOP)
        self.assertEqual([s[1] for s in rec["signals"]], [I.RECURRENT] * 2)

    def test_same_sequence_differs_by_declared_rule(self):
        seq_key = [o(1, "a"), o(2, "a"), o(3, "a")]
        t = task()
        t["friction_bound"] = 1
        self.assertEqual(I.evaluate(t, seq_key, 3)["decision"], I.STOP)
        t["novelty_rule"] = "declared"
        seq_decl = [o(1, "a", None, True), o(2, "a", None, True), o(3, "a", None, True)]
        self.assertEqual(I.evaluate(t, seq_decl, 3)["decision"], I.CONTINUE)

    def test_success_only_when_all_resolved(self):
        for k in range(0, 3):
            rec = I.evaluate(task(), DIRECT[:k], 3)
            self.assertNotEqual(rec["decision"], I.SUCCESS, k)
        self.assertEqual(I.evaluate(task(), DIRECT, 3)["decision"], I.SUCCESS)
        rng = random.Random(14111)
        for _ in range(500):
            obs = []
            for t in range(1, rng.randint(1, 10)):
                ob = o(t, "e%d" % rng.randint(0, 3))
                if rng.random() < 0.4:
                    ob["resolves"] = rng.choice(["location", "count", "route"])
                obs.append(ob)
            now = rng.randint(len(obs), 25)
            rec = I.evaluate(task(), obs, now)
            got = {ob["resolves"] for ob in obs if "resolves" in ob}
            if rec["decision"] == I.SUCCESS:
                self.assertEqual(got, {"location", "count", "route"})
                self.assertEqual(rec["unresolved"], ())

    def test_post_completion_muted(self):
        obs = DIRECT + [o(4, "map-1"), o(5, "map-1"), o(6, "map-1"), o(7, "map-1")]
        rec = I.evaluate(task(), obs, 7)
        self.assertEqual(rec["decision"], I.SUCCESS)
        self.assertEqual(rec["friction"], 0)
        self.assertEqual(len(rec["signals"]), 3)

    def test_deadline_returns_each_declared_on_expiry(self):
        for value in I.ON_EXPIRY_VALUES:
            t = task()
            t["on_expiry"] = value
            rec = I.evaluate(t, DIRECT[:1], t["deadline"])
            self.assertEqual(rec["decision"], value)
            self.assertEqual(rec["reason"], I.EXPIRED)
            self.assertNotIn(rec["decision"], (I.SUCCESS, I.CONTINUE))

    def test_expiry_result_is_module_constant(self):
        for value in I.ON_EXPIRY_VALUES:
            t = task()
            caller = "".join(list(value))
            self.assertIsNot(caller, value)
            t["on_expiry"] = caller
            rec = I.evaluate(t, [], t["deadline"])
            self.assertIs(rec["decision"], value)
            self.assertIs(rec["on_expiry"], value)

    def test_late_observations_do_not_count(self):
        t = task()
        d = t["deadline"]
        obs = DIRECT[:2] + [o(d, "map-1", "route")]
        rec = I.evaluate(t, obs, d)
        self.assertEqual(rec["decision"], I.HOLD)
        self.assertEqual(rec["unresolved"], ("route",))
        obs = DIRECT[:2] + [o(d - 1, "map-1", "route")]
        self.assertEqual(I.evaluate(t, obs, d - 1)["decision"], I.SUCCESS)
        # Expiry guard: a success is read before the deadline, not after it.
        rec = I.evaluate(t, obs, d + 9)
        self.assertEqual(rec["decision"], I.HOLD)
        self.assertEqual(rec["unresolved"], ())

    def test_expiry_is_final_across_calls(self):
        # Verdict repro: a later call appends evidence backdated to t=2.
        t = task()
        h = [o(1, "a", "location"), o(2, "b", "count")]
        first = I.evaluate(t, h, 20)
        self.assertEqual((first["decision"], first["reason"]), (I.HOLD, I.EXPIRED))
        later = I.evaluate(t, h + [o(2, "c", "route")], 25)
        self.assertEqual((later["decision"], later["reason"]), (I.HOLD, I.EXPIRED))
        control = I.evaluate(t, h + [o(20, "c", "route")], 25)
        self.assertEqual(control["decision"], I.HOLD)
        # A backdated repeat run cannot turn the expiry into a stop either.
        stop = I.evaluate(t, h + [o(2, "b"), o(2, "b"), o(2, "b")], 25)
        self.assertEqual((stop["decision"], stop["reason"]), (I.HOLD, I.EXPIRED))
        for value in I.ON_EXPIRY_VALUES:
            t = task()
            t["on_expiry"] = value
            rec = I.evaluate(t, DIRECT, t["deadline"])
            self.assertIs(rec["decision"], value)

    def test_after_deadline_decision_ignores_observations(self):
        rng = random.Random(2611)
        for t in F.tasks():
            d = t["deadline"]
            declared = t["novelty_rule"] == "declared"
            for _ in range(300):
                obs, last = [], 0
                for _ in range(rng.randint(0, 12)):
                    last = rng.randint(last, d - 1)
                    req = rng.choice(t["requirements"] + [None, None])
                    novel = rng.random() < 0.5 if declared else None
                    obs.append(o(last, "e%d" % rng.randint(0, 3), req, novel))
                for now in (d, d + rng.randint(1, 50)):
                    rec = I.evaluate(t, obs, now)
                    self.assertIs(rec["decision"],
                                  I._canonical(t["on_expiry"], I.ON_EXPIRY_VALUES))
                    self.assertEqual(rec["reason"], I.EXPIRED)

    def test_late_repeats_do_not_stop(self):
        t = task()
        d = t["deadline"]
        obs = [o(d + i, "radio-1") for i in range(5)]
        rec = I.evaluate(t, obs, d + 5)
        self.assertEqual(rec["decision"], I.HOLD)

    def test_no_success_or_continue_on_timeout(self):
        for t in F.tasks():
            for now in range(t["deadline"], t["deadline"] + 3):
                rec = I.evaluate(t, [], now)
                self.assertIn(rec["decision"], I.ON_EXPIRY_VALUES)
            rec = I.evaluate(t, [], t["deadline"] - 1)
            self.assertEqual(rec["decision"], I.CONTINUE)

    def test_missing_bound_on_expiry_rule_config_error(self):
        for key, detail in (("friction_bound", I.D_BOUND_MISSING),
                            ("on_expiry", I.D_ON_EXPIRY_MISSING),
                            ("novelty_rule", I.D_RULE_MISSING)):
            t = task()
            del t[key]
            for obs, now in ((DIRECT, 3), ([], t["deadline"]), ([o(1, "a")], 1)):
                rec = I.evaluate(t, obs, now)
                self.assertEqual(rec["decision"], I.REJECT)
                self.assertEqual(rec["reason"], I.CONFIG_ERROR)
                self.assertEqual(rec["detail"], detail, key)

    def test_invalid_on_expiry_config_error(self):
        for value in ("hold", "SUCCESS", "CONTINUE", "STOP", "", None, 1, True,
                      StrSub("HOLD"), ["DENY"], Boom()):
            t = task()
            t["on_expiry"] = value
            rec = I.evaluate(t, DIRECT, 3)
            self.assertEqual(rec["detail"], I.D_ON_EXPIRY_INVALID, type(value).__name__)
            self.assertEqual(rec["decision"], I.REJECT)

    def test_invalid_bound_config_error(self):
        for value in (-1, True, False, IntSub(2), 2.0, "2", None):
            t = task()
            t["friction_bound"] = value
            self.assertEqual(I.evaluate(t, DIRECT, 3)["detail"], I.D_BOUND_INVALID)

    def test_invalid_rule_config_error(self):
        for value in ("EVIDENCE_KEY", "none", "", None, StrSub("declared"), 0):
            t = task()
            t["novelty_rule"] = value
            self.assertEqual(I.evaluate(t, DIRECT, 3)["detail"], I.D_RULE_INVALID)

    def test_domain_results_on_unmeasured(self):
        self.assertEqual(I.domain_results(), I.ON_UNMEASURED)

    def test_no_model_no_clock_no_threads(self):
        for name in CODE:
            for node in ast.walk(ast.parse(read(name))):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [(node.module or "").split(".")[0]]
                else:
                    continue
                for m in mods:
                    self.assertIn(m, STDLIB_PERMITTED, (name, m))
        tree = ast.parse(read("info_friction.py"))
        self.assertEqual([n for n in ast.walk(tree)
                          if isinstance(n, (ast.Import, ast.ImportFrom))], [])
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for bad in ("time", "sleep", "Thread", "threading", "monotonic", "while"):
            self.assertNotIn(bad, names)
        self.assertEqual([n for n in ast.walk(tree) if isinstance(n, ast.While)], [])


class TestInputs(unittest.TestCase):

    def assertConfig(self, rec, detail=None):
        self.assertEqual(rec["decision"], I.REJECT)
        self.assertEqual(rec["reason"], I.CONFIG_ERROR)
        if detail is not None:
            self.assertEqual(rec["detail"], detail)

    def test_task_container_and_fields(self):
        self.assertConfig(I.evaluate(DictSub(task()), DIRECT, 3), I.D_TASK)
        self.assertConfig(I.evaluate(None, DIRECT, 3), I.D_TASK)
        t = task()
        t["extra"] = 1
        self.assertConfig(I.evaluate(t, DIRECT, 3), I.D_TASK)
        t = task()
        t[StrSub("zz")] = 1
        self.assertConfig(I.evaluate(t, DIRECT, 3), I.D_TASK)
        for value in ("", None, 5, StrSub("rescue")):
            t = task()
            t["task_id"] = value
            rec = I.evaluate(t, DIRECT, 3)
            self.assertConfig(rec, I.D_TASK)
            self.assertIsNone(rec["task_id"])

    def test_requirements(self):
        for value in ([], ["a", "a"], ["a", ""], ["a", StrSub("b")], ("a",),
                      ListSub(["a"]), "a", None, ["a", 1]):
            t = task()
            t["requirements"] = value
            self.assertConfig(I.evaluate(t, [], 0), I.D_REQUIREMENTS)
        t = task()
        del t["requirements"]
        self.assertConfig(I.evaluate(t, [], 0), I.D_REQUIREMENTS)

    def test_deadline(self):
        for value in (0, -3, True, IntSub(5), 5.0, None):
            t = task()
            t["deadline"] = value
            self.assertConfig(I.evaluate(t, [], 0), I.D_DEADLINE)

    def test_now(self):
        for now in (-1, True, IntSub(3), 3.0, None, "3"):
            self.assertConfig(I.evaluate(task(), DIRECT, now), I.D_NOW)

    def test_observations_shape(self):
        bad = [
            ListSub(DIRECT), tuple(DIRECT), None,
            [DictSub(o(1, "a"))],
            [{"t": 1, "evidence": "a", "x": 1}],
            [{"evidence": "a"}],
            [{"t": 1}],
            [o(1, "")],
            [o(1, StrSub("a"))],
            [{"t": True, "evidence": "a"}],
            [{"t": IntSub(1), "evidence": "a"}],
            [o(2, "a"), o(1, "b")],
            [o(9, "a")],
            [o(1, "a", "nope")],
            [o(1, "a", StrSub("location"))],
            [{"t": 1, "evidence": "a", "resolves": None}],
            [o(1, "a", None, True)],
        ]
        for obs in bad:
            self.assertConfig(I.evaluate(task(), obs, 3), I.D_OBS)
        for obs in ([o(1, "a")], [o(1, "a", None, 1)], [{"t": 1, "evidence": "a", "novel": None}]):
            self.assertConfig(I.evaluate(task("grid"), obs, 3), I.D_OBS)

    def test_equal_timestamps_accepted(self):
        obs = [o(1, "radio-1", "location"), o(1, "radio-2", "count"), o(1, "map-1", "route")]
        self.assertEqual(I.evaluate(task(), obs, 1)["decision"], I.SUCCESS)
        self.assertEqual(I.evaluate(task(), [o(0, "a"), o(0, "a")], 0)["decision"],
                         I.CONTINUE)

    def test_negative_t_rejected(self):
        for obs in ([o(-1, "a")], [o(-5, "a"), o(1, "b")]):
            self.assertConfig(I.evaluate(task(), obs, 3), I.D_OBS)

    def test_evidence_key_is_exact_string(self):
        obs = [o(1, "a"), o(2, "A"), o(3, " a"), o(4, "a ")]
        rec = I.evaluate(task(), obs, 4)
        self.assertEqual([s[1] for s in rec["signals"]], [I.EXPLORE] * 4)
        self.assertEqual(rec["friction"], 0)

    def test_config_error_never_echoes_task_id(self):
        for key in ("friction_bound", "on_expiry", "novelty_rule", "deadline"):
            t = task()
            del t[key]
            rec = I.evaluate(t, DIRECT, 3)
            self.assertConfig(rec)
            self.assertIsNone(rec["task_id"], key)
        rec = I.evaluate(task(), [o(1, "")], 3)
        self.assertConfig(rec, I.D_OBS)
        self.assertIsNone(rec["task_id"])
        self.assertEqual(I.evaluate(task(), DIRECT, 3)["task_id"], "rescue")

    def test_task_id_read_once(self):
        # Mapping whose task_id value flips after the first read, so any
        # later read is visible whatever the function's shape. Production
        # rejects a dict subclass (exact type), so the key-shape check
        # runs without that gate for this object only.
        class Flip(dict):
            def __init__(self, other):
                dict.__init__(self, other)
                self._reads = 0

            def __getitem__(self, key):
                if key == "task_id":
                    self._reads += 1
                    return "rescue" if self._reads == 1 else "swapped"
                return dict.__getitem__(self, key)

            def get(self, key, default=None):
                if key == "task_id" and dict.__contains__(self, key):
                    return self[key]
                return dict.get(self, key, default)

        t = Flip(task())
        orig = I._check_keys

        def check(mapping, fields, detail):
            if mapping is t:
                for key in mapping:
                    if not I._is_str(key) or I._canonical(key, fields) is None:
                        raise I._Bad(detail)
                return
            return orig(mapping, fields, detail)

        I._check_keys = check
        try:
            rec = I.evaluate(t, DIRECT, 3)
        finally:
            I._check_keys = orig
        self.assertEqual(t._reads, 1)
        self.assertEqual(rec["decision"], I.SUCCESS)
        self.assertEqual(rec["task_id"], "rescue")

    def test_novel_read_once(self):
        # Observation whose 'novel' label flips after the first read (False,
        # then True), with every task and observation field read counted
        # (subscript and .get; reads through the C-level dict methods are
        # not visible here and are left to the source check). One read gives
        # recurrent, recurrent -> STOP; a second read would see True and
        # turn the pair into exploration (CONTINUE). Production rejects a
        # dict subclass (exact type), so the key-shape check runs without
        # that gate for these objects only.
        class Flip(dict):
            def __init__(self, other):
                dict.__init__(self, other)
                self.reads = {}

            def __getitem__(self, key):
                self.reads[key] = self.reads.get(key, 0) + 1
                if key == "novel":
                    return self.reads[key] > 1
                return dict.__getitem__(self, key)

            def get(self, key, default=None):
                if dict.__contains__(self, key):
                    return self[key]
                return default

        class Count(Flip):
            def __getitem__(self, key):
                self.reads[key] = self.reads.get(key, 0) + 1
                return dict.__getitem__(self, key)

        t = Count(task("grid"))
        obs = [Flip(o(1, "same", None, False)), Flip(o(2, "same", None, False))]
        ids = {id(x) for x in obs} | {id(t)}
        orig = I._check_keys

        def check(mapping, fields, detail):
            if id(mapping) in ids:
                for key in mapping:
                    if not I._is_str(key) or I._canonical(key, fields) is None:
                        raise I._Bad(detail)
                return
            return orig(mapping, fields, detail)

        I._check_keys = check
        try:
            rec = I.evaluate(t, obs, 5)
        finally:
            I._check_keys = orig
        self.assertEqual(t.reads, {k: 1 for k in I.TASK_FIELDS})
        for x in obs:
            self.assertEqual(x.reads, {"t": 1, "evidence": 1, "novel": 1})
        self.assertEqual(rec["decision"], I.STOP)
        self.assertEqual([s[1] for s in rec["signals"]], [I.RECURRENT, I.RECURRENT])

    def test_field_reads_single_path(self):
        # Source check: each task and observation field is read once, by a
        # constant subscript or .get, and the caller's mappings reach no
        # other path (no dict.get(task, ...), dict(task), .items(), helper,
        # alias, locals(), operator.itemgetter and so on).
        self.assertEqual(field_read_problems(module_source()), [])

    def test_field_read_check_is_not_vacuous(self):
        # The source check flags each reading shape it claims to ban. It
        # edits the return line of validate_task; when the module text no
        # longer has that line, or is not clean, this test stands aside
        # and test_field_reads_single_path reports.
        src = module_source()
        ret = "    return task_id, tuple(seen), bound, deadline, on_expiry, rule"
        if src.count(ret) != 1 or field_read_problems(src):
            self.skipTest("module text differs from the reviewed shape")
        shapes = [
            "dict.get(task, \"task_id\")", "dict(task)[\"task_id\"]",
            "task.get(\"task_id\")", "task[\"task_id\"]", "_tid(task)",
            "next(v for k, v in task.items() if k == \"task_id\")",
            "[task[k] for k in TASK_FIELDS][0]", "locals()[\"task\"][\"task_id\"]",
        ]
        for shape in shapes:
            bad = src.replace(ret, ret.replace("return task_id", "return " + shape))
            self.assertNotEqual(field_read_problems(bad), [], shape)
        alias = src.replace(ret, "    alias = task\n" + ret)
        self.assertNotEqual(field_read_problems(alias), [])
        reread = src.replace("        out.append((t, evidence, resolves, novel))",
                             "        out.append((t, obs[\"evidence\"], resolves, novel))")
        self.assertNotEqual(field_read_problems(reread), [])

    def test_never_raises(self):
        weird = [None, 0, "", [], {}, Boom(), [Boom()], {BadKey(): 1},
                 [{"t": 0, "evidence": Boom()}], DictSub(), StrSub("x"), object()]
        for a in weird:
            for b in weird:
                for c in (0, 3, Boom(), None):
                    self.assertEqual(I.evaluate(a, b, c)["decision"], I.REJECT)
        t = task()
        t["requirements"] = ["a", Boom()]
        self.assertEqual(I.evaluate(t, [], 0)["reason"], I.CONFIG_ERROR)

    def test_internal_error_fails_closed(self):
        orig = I._evaluate
        try:
            def broken(*args):
                raise KeyError("x")
            I._evaluate = broken
            rec = I.evaluate(task(), DIRECT, 3)
        finally:
            I._evaluate = orig
        self.assertEqual(rec, {"task_id": None, "decision": I.REJECT,
                               "reason": I.CONFIG_ERROR, "detail": I.D_INTERNAL,
                               "unresolved": (), "friction": 0, "signals": (),
                               "on_expiry": None})

    def test_inputs_not_mutated(self):
        t = task()
        obs = copy.deepcopy(DIRECT)
        before = (copy.deepcopy(t), copy.deepcopy(obs))
        I.evaluate(t, obs, 3)
        self.assertEqual((t, obs), before)


class TestRecords(unittest.TestCase):

    def test_records_clean(self):
        for task_id, name, rec in F.run_all():
            self.assertEqual(tuple(rec), I.RECORD_FIELDS)
            self.assertIn(rec["decision"], I.DECISIONS)
            self.assertIn(rec["reason"], I.REASONS)
            self.assertIn(rec["detail"], I.DETAILS)
            self.assertIs(type(rec["unresolved"]), tuple)
            self.assertEqual(list(rec["unresolved"]), sorted(rec["unresolved"]))
            self.assertIs(type(rec["signals"]), tuple)
            for t, kind, count, friction in rec["signals"]:
                self.assertIn(kind, I.KINDS)
                self.assertIs(type(count), int)
                self.assertIs(type(friction), int)
            for value in (rec["decision"], rec["reason"], rec["on_expiry"]):
                self.assertTrue(any(value is c for c in I.DECISIONS + I.REASONS))

    def test_signals_progress_monotone(self):
        for task_id, name, rec in F.run_all():
            counts = [s[2] for s in rec["signals"]]
            self.assertEqual(counts, sorted(counts, reverse=True), name)


class TestFixtures(unittest.TestCase):

    def test_expected_table(self):
        rows = F.run_all()
        self.assertEqual(len(rows), len(F.EXPECTED))
        seen = set()
        for task_id, name, rec in rows:
            key = (task_id, name)
            self.assertNotIn(key, seen)
            seen.add(key)
            self.assertIn(key, F.EXPECTED)
            self.assertEqual((rec["decision"], rec["reason"], rec["unresolved"],
                              rec["friction"]), F.EXPECTED[key], key)

    def test_fixture_invariants(self):
        ids = [t["task_id"] for t in F.tasks()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sorted(t["novelty_rule"] for t in F.tasks()),
                         sorted(I.NOVELTY_RULES))
        for t in F.tasks():
            for key in ("friction_bound", "on_expiry", "novelty_rule", "deadline"):
                self.assertIn(key, t)
        decisions = {v[0] for v in F.EXPECTED.values()}
        for d in (I.SUCCESS, I.STOP, I.CONTINUE, I.HOLD, I.DENY):
            self.assertIn(d, decisions)

    def test_fixture_pins(self):
        got = {t["task_id"]: (tuple(t["requirements"]), t["friction_bound"],
                              t["deadline"], t["on_expiry"], t["novelty_rule"])
               for t in F.tasks()}
        self.assertEqual(got, {
            "rescue": (("location", "count", "route"), 2, 20, "HOLD", "evidence_key"),
            "grid": (("exit", "key"), 1, 12, "DENY", "declared"),
        })

    def test_tasks_returns_copies(self):
        a = F.tasks()
        a[0]["requirements"].clear()
        self.assertTrue(F.tasks()[0]["requirements"])

    def test_determinism(self):
        self.assertEqual(F.run_all(), F.run_all())


class TestDocs(unittest.TestCase):

    def test_banned_words_absent(self):
        for name in ALL:
            text = read(name).lower()
            for word in BANNED:
                self.assertNotIn(word.lower(), text, (name, word))

    def test_no_absolute_paths_or_markers(self):
        for name in ALL:
            text = read(name)
            for p in ("/" + "workspace", "/" + "tmp", "/" + "home/"):
                self.assertNotIn(p, text, name)
            for marker in ("<" * 7, "=" * 7, ">" * 7):
                self.assertNotIn(marker, text, name)

    def test_day_readme(self):
        text = read(DAY)
        lines = text.splitlines()
        self.assertTrue(text.startswith(DAY_HEADER + "\n"))
        self.assertEqual(text.count(FOOTER), 1)
        self.assertTrue(text.endswith("\n\n" + FOOTER + "\n"))
        self.assertEqual(sum(1 for line in lines if line.startswith(ROW_START)), 1)
        if LAYOUT == "flat":
            # The draft carries only this folder's row; in the repo the day
            # index may also hold other folders' rows.
            self.assertEqual(sum(1 for line in lines if line.startswith("- ")), 1)

    def test_no_paper_claims_outside_evidence(self):
        pat = re.compile(r"\d+\s*%|eight diverse|high mission success|search and rescue dialogue")
        for name in ("README.md", "NOTICE", "info_friction.py", "fixtures.py"):
            self.assertIsNone(pat.search(read(name)), name)

    def test_readme_credits_and_scope(self):
        flat = " ".join(read("README.md").split())
        ev = json.loads(read("paper_evidence.json"))
        self.assertIn(ev["paper"]["title"], flat)
        for author in ev["paper"]["authors"]:
            self.assertIn(author, flat)
        for s in ("http://arxiv.org/licenses/nonexclusive-distrib/1.0/",
                  '"Code available"', "UNVERIFIED and unlocated",
                  "method sketch, not law", "synthetic", "Soft", "on_unmeasured",
                  "w14-arc-grammar", "w14-phase-deadline",
                  "recurrent evidence with no requirement gain",
                  "Acquisition-State Telemetry (AST)", "cs.RO"):
            self.assertIn(s, flat, s)
        notice = " ".join(read("NOTICE").split())
        self.assertIn('"Code available"', notice)
        self.assertIn("UNVERIFIED and unlocated", notice)
        self.assertIn("this sketch's own rules, not the paper's", notice)
        self.assertNotIn("stopped when friction persists", notice)
        for s in ("Novelty can be spoofed until the deadline",
                  "Expiry guard: an expiry is final"):
            self.assertIn(s, flat, s)

    def test_evidence_shape(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.14111")
        self.assertIn("Code available", ev["paper"]["comments_field"])
        self.assertIn("UNVERIFIED", ev["paper"]["code"])
        for c in ev["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")
            self.assertEqual(len(c["quote"]), c["length"])

    def _find(self, name):
        for d in SOURCES.split(os.pathsep):
            path = os.path.join(d, name)
            if d and os.path.exists(path):
                return path
        return None

    def test_quotes_exact_in_sources(self):
        if not SOURCES:
            self.skipTest("W21FRICTION_SOURCES not set")
        ev = json.loads(read("paper_evidence.json"))
        abs_src, html_src = ev["sources"]
        p1, p2 = self._find(abs_src["file"]), self._find(html_src["file"])
        if p1 is None or p2 is None:
            self.skipTest("source copies not present")
        with open(p1, encoding="utf-8") as f:
            text = f.read()
        with open(p2, encoding="utf-8") as f:
            page = f.read()
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), abs_src["sha256"])
        self.assertEqual(hashlib.sha256(page.encode("utf-8")).hexdigest(), html_src["sha256"])
        for c in ev["claims"]:
            self.assertEqual(text.count(c["quote"]), 1, c["id"])
            self.assertEqual(text[c["offset"]:c["offset"] + c["length"]], c["quote"], c["id"])
        self.assertIn(ev["paper"]["comments_field"], page)
        self.assertIn(html_src["comments_quote"], ev["paper"]["comments_field"])


if __name__ == "__main__":
    unittest.main()
