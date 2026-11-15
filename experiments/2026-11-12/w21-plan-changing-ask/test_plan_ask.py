"""Tests for the w21-plan-changing-ask method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
The quote check reads the abstract copy named in paper_evidence.json from
the directory in $W21ASK_SOURCES. There is no default: when the variable
is unset, or the file is absent there, that check is skipped.
"""

import ast
import copy
import dis
import hashlib
import json
import os
import random
import re
import sys
import traceback
import unittest

import fixtures as F
import plan_ask as P

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W21ASK_SOURCES")
CODE = ("plan_ask.py", "fixtures.py")
DAY_HEADER = "# experiments/2026-11-12\n"
ROW_START = "- [w21-plan-changing-ask](w21-plan-changing-ask/): "
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
ALL = ("README.md", "NOTICE", "plan_ask.py", "fixtures.py", "test_plan_ask.py",
       "mutants.py", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
STDLIB_PERMITTED = {"copy", "sys", "plan_ask"}


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def task(name="drivers"):
    for t in F.tasks():
        if t["task_id"] == name:
            return t
    raise KeyError(name)


def ask(t, fact):
    return {"t": t, "kind": "ask", "fact": fact}


def answer(t, fact):
    return {"t": t, "kind": "answer", "fact": fact}


def act(t):
    return {"t": t, "kind": "act"}


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

    def __str__(self):
        raise RuntimeError("str")


class Mutator(object):
    """A non-str key that hashes like a field name and, once armed, rewrites
    the task from inside __eq__ (the PR #120 r1 F1 shape). calls counts
    every __eq__ call; after the fix there must be none."""

    def __init__(self, target, name, action=None):
        self.target = target
        self.name = name
        self.action = action
        self.armed = False
        self.calls = 0

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        self.calls += 1
        if not self.armed:
            return False
        self.armed = False
        if self.action is not None:
            self.action(self)
        return False


def interrupt(key):
    raise KeyboardInterrupt("from input")


def f1_task():
    """The r1 repro, inline: task_id absent, a self-rewriting colliding key
    present, d_licence labelled plan_changing."""
    t = {"request": "r", "deadline": 10, "on_expiry": "HOLD",
         "facts": {"d_licence": {"text": "Licence lapses.", "label": "plan_changing"}}}

    def rewrite(key):
        key.target["facts"]["d_licence"]["label"] = "inert"
        key.target.pop(key, None)
        key.target["task_id"] = "drivers"

    k = Mutator(t, "task_id", rewrite)
    t[k] = 1
    k.calls = 0
    k.armed = True
    return t, k


VALID_TRACE = [ask(0, "d_licence"), answer(1, "d_licence"), act(2)]


class TestDoneWhen(unittest.TestCase):

    def test_a_act_with_plan_changing_missing_rejected(self):
        for t in F.tasks():
            rec = P.decide(t, [act(0)], 0)
            self.assertEqual(rec["decision"], P.REJECT)
            self.assertEqual(rec["reason"], P.MISSING_PLAN_CHANGING)
            self.assertTrue(rec["missing"])

    def test_a_one_of_two_plan_changing_missing_rejected(self):
        t = task("nurses")
        rec = P.decide(t, [ask(0, "n_cert"), answer(1, "n_cert"), act(2)], 2)
        self.assertEqual(rec["decision"], P.REJECT)
        self.assertEqual(rec["missing"], ("n_leave",))

    def test_b_inert_only_cannot_act(self):
        rec = P.decide(task(), [ask(0, "d_paint"), answer(1, "d_paint"), act(2)], 2)
        self.assertEqual(rec["decision"], P.REJECT)
        self.assertEqual(rec["reason"], P.MISSING_PLAN_CHANGING)
        self.assertEqual(rec["missing"], ("d_licence",))

    def test_c_plan_changing_then_act_succeeds(self):
        rec = P.decide(task(), VALID_TRACE, 2)
        self.assertEqual(rec["decision"], P.ACT)
        self.assertEqual(rec["reason"], P.VALID)
        self.assertEqual(rec["missing"], ())

    def test_c_asking_is_not_knowing(self):
        rec = P.decide(task(), [ask(0, "d_licence"), act(1)], 1)
        self.assertEqual(rec["decision"], P.REJECT)
        self.assertEqual(rec["missing"], ("d_licence",))

    def test_c_answer_after_act_is_not_counted(self):
        rec = P.decide(task(), [ask(0, "d_licence"), act(1), answer(1, "d_licence")], 1)
        self.assertEqual(rec["reason"], P.CONFIG_ERROR)

    def test_e_silent_operator_returns_declared_on_expiry(self):
        for name, want in (("drivers", P.HOLD), ("nurses", P.ESCALATE), ("room", P.DENY)):
            t = task(name)
            pc = sorted(f for f, v in t["facts"].items() if v["label"] == "plan_changing")
            rec = P.decide(t, [ask(0, pc[0])], t["deadline"])
            self.assertEqual(rec["decision"], want, name)
            self.assertEqual(rec["reason"], P.EXPIRED)
            self.assertEqual(rec["on_expiry"], want)
            self.assertNotEqual(rec["decision"], P.ACT)

    def test_e_each_on_expiry_value(self):
        for value in P.ON_EXPIRY_VALUES:
            t = task()
            t["on_expiry"] = value
            rec = P.decide(t, [], t["deadline"])
            self.assertEqual(rec["decision"], value)
            self.assertEqual(rec["reason"], P.EXPIRED)

    def test_e_expiry_well_past_deadline(self):
        t = task()
        rec = P.decide(t, [ask(0, "d_licence")], t["deadline"] + 100)
        self.assertEqual(rec["decision"], P.HOLD)

    def test_e_expiry_result_is_module_constant(self):
        for value in P.ON_EXPIRY_VALUES:
            t = task()
            caller = "".join(list(value))
            self.assertIsNot(caller, value)
            t["on_expiry"] = caller
            rec = P.decide(t, [], t["deadline"])
            self.assertIs(rec["decision"], value)
            self.assertIs(rec["on_expiry"], value)

    def test_e_late_answer_does_not_count(self):
        t = task()
        d = t["deadline"]
        rec = P.decide(t, [ask(1, "d_licence"), answer(d, "d_licence"), act(d + 1)], d + 1)
        self.assertEqual(rec["decision"], P.HOLD)
        self.assertEqual(rec["missing"], ("d_licence",))

    def test_e_late_act_never_acts(self):
        t = task()
        d = t["deadline"]
        trace = [ask(0, "d_licence"), answer(1, "d_licence"), act(d)]
        rec = P.decide(t, trace, d)
        self.assertEqual(rec["decision"], P.HOLD)
        self.assertEqual(rec["missing"], ())

    def test_e_act_just_before_deadline_counts(self):
        t = task()
        d = t["deadline"]
        trace = [ask(0, "d_licence"), answer(d - 2, "d_licence"), act(d - 1)]
        self.assertEqual(P.decide(t, trace, d - 1)["decision"], P.ACT)
        self.assertEqual(P.decide(t, trace, d + 5)["decision"], P.ACT)

    def test_e_answer_at_last_step_counts(self):
        t = task()
        d = t["deadline"]
        trace = [ask(0, "d_licence"), answer(d - 1, "d_licence")]
        rec = P.decide(t, trace, d - 1)
        self.assertEqual(rec["decision"], P.WAIT)
        self.assertEqual(rec["missing"], ())

    def test_e_all_known_but_no_act_still_expires(self):
        t = task()
        rec = P.decide(t, [ask(0, "d_licence"), answer(1, "d_licence")], t["deadline"])
        self.assertEqual(rec["decision"], P.HOLD)
        self.assertEqual(rec["missing"], ())

    def test_e_missing_on_expiry_is_config_error(self):
        t = task()
        del t["on_expiry"]
        for trace, now in ((VALID_TRACE, 2), ([], t["deadline"]), ([act(0)], 0)):
            rec = P.decide(t, trace, now)
            self.assertEqual(rec["decision"], P.REJECT)
            self.assertEqual(rec["reason"], P.CONFIG_ERROR)
            self.assertEqual(rec["detail"], P.D_ON_EXPIRY_MISSING)

    def test_e_invalid_on_expiry_is_config_error(self):
        for value in ("hold", "ACT", "act", "PROCEED", "DISPATCH", "", " HOLD", None,
                      1, True, StrSub("HOLD"), StrSub("x"), ["HOLD"], Boom()):
            t = task()
            t["on_expiry"] = value
            rec = P.decide(t, VALID_TRACE, 2)
            self.assertEqual(rec["reason"], P.CONFIG_ERROR, repr(type(value)))
            self.assertEqual(rec["detail"], P.D_ON_EXPIRY_INVALID)
            self.assertEqual(rec["decision"], P.REJECT)

    def test_e_no_act_on_timeout_anywhere(self):
        for t in F.tasks():
            for trace in ([], [ask(0, sorted(t["facts"])[0])]):
                for now in range(t["deadline"], t["deadline"] + 3):
                    rec = P.decide(t, trace, now)
                    self.assertIn(rec["decision"], P.ON_EXPIRY_VALUES)

    def test_wait_before_deadline(self):
        t = task()
        for now in range(0, t["deadline"]):
            rec = P.decide(t, [], now)
            self.assertEqual(rec["decision"], P.WAIT)
            self.assertEqual(rec["reason"], P.AWAITING)
            self.assertEqual(rec["missing"], ("d_licence",))

    def test_d_no_llm_stdlib_only(self):
        for name in CODE:
            tree = ast.parse(read(name))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [(node.module or "").split(".")[0]]
                else:
                    continue
                for m in mods:
                    self.assertIn(m, STDLIB_PERMITTED, (name, m))
        self.assertEqual([n for n in ast.walk(ast.parse(read("plan_ask.py")))
                          if isinstance(n, (ast.Import, ast.ImportFrom))], [])

    def test_unlabeled_fact_is_on_unmeasured_never_act(self):
        t = task()
        del t["facts"]["d_paint"]["label"]
        for trace, now in ((VALID_TRACE, 2), ([], t["deadline"]), ([act(0)], 0),
                           ([ask(0, "d_paint"), answer(1, "d_paint"), act(2)], 2)):
            rec = P.decide(t, trace, now)
            self.assertEqual(rec["decision"], P.REJECT)
            self.assertEqual(rec["reason"], P.ON_UNMEASURED)
            self.assertEqual(rec["detail"], P.D_UNLABELED)

    def test_unknown_label_is_config_error(self):
        for label in ("relevant", "PLAN_CHANGING", "", None, 0, StrSub("inert"),
                      StrSub("plan_changing"), Boom()):
            t = task()
            t["facts"]["d_paint"]["label"] = label
            rec = P.decide(t, VALID_TRACE, 2)
            self.assertEqual(rec["reason"], P.CONFIG_ERROR, type(label).__name__)
            self.assertEqual(rec["detail"], P.D_LABEL)

    def test_no_solver(self):
        for t in F.tasks():
            self.assertEqual(P.optimality(t), P.ON_UNMEASURED)
        self.assertEqual(P.optimality(None), P.ON_UNMEASURED)
        self.assertEqual([n for n in dir(P) if "solve" in n.lower()], [])
        for name, rec in ((t["task_id"], P.decide(t, [], 0)) for t in F.tasks()):
            self.assertNotIn("optimal", " ".join(str(v) for v in rec.values()), name)


class TestInputs(unittest.TestCase):

    def assertConfig(self, rec, detail=None):
        self.assertEqual(rec["decision"], P.REJECT)
        self.assertEqual(rec["reason"], P.CONFIG_ERROR)
        if detail is not None:
            self.assertEqual(rec["detail"], detail)

    def test_task_container_types(self):
        t = task()
        self.assertConfig(P.decide(DictSub(t), VALID_TRACE, 2), P.D_TASK)
        self.assertConfig(P.decide(None, VALID_TRACE, 2), P.D_TASK)
        self.assertConfig(P.decide([t], VALID_TRACE, 2), P.D_TASK)

    def test_task_fields(self):
        t = task()
        t["extra"] = 1
        self.assertConfig(P.decide(t, VALID_TRACE, 2), P.D_TASK)
        for key in P.REQUIRED_TASK_FIELDS:
            t = task()
            del t[key]
            self.assertConfig(P.decide(t, VALID_TRACE, 2))
        t = task()
        t[StrSub("zzz")] = 1
        self.assertConfig(P.decide(t, VALID_TRACE, 2), P.D_TASK)

    def test_task_id_and_request(self):
        for field in ("task_id", "request"):
            for value in ("", None, 3, StrSub("drivers")):
                t = task()
                t[field] = value
                rec = P.decide(t, VALID_TRACE, 2)
                self.assertConfig(rec, P.D_TASK)
                if field == "task_id":
                    self.assertIsNone(rec["task_id"])

    def test_deadline_exact_positive_int(self):
        for value in (0, -1, True, IntSub(10), 10.0, "10", None):
            t = task()
            t["deadline"] = value
            self.assertConfig(P.decide(t, VALID_TRACE, 2), P.D_DEADLINE)

    def test_facts_shape(self):
        bad = [
            ("facts", DictSub(task()["facts"])),
            ("facts", [("d_licence", {})]),
        ]
        for key, value in bad:
            t = task()
            t[key] = value
            self.assertConfig(P.decide(t, [], 0), P.D_FACT)
        t = task()
        t["facts"][StrSub("d_extra")] = {"text": "x", "label": "inert"}
        self.assertConfig(P.decide(t, [], 0), P.D_FACT)
        t = task()
        t["facts"][""] = {"text": "x", "label": "inert"}
        self.assertConfig(P.decide(t, [], 0), P.D_FACT)
        for fact in ({"label": "inert"}, {"text": "", "label": "inert"},
                     {"text": StrSub("x"), "label": "inert"},
                     {"text": "x", "label": "inert", "solver": "optimal"},
                     DictSub({"text": "x", "label": "inert"}), "x"):
            t = task()
            t["facts"]["d_paint"] = fact
            self.assertConfig(P.decide(t, [], 0), P.D_FACT)

    def test_now_exact_int(self):
        for now in (-1, True, IntSub(2), 2.0, "2", None):
            self.assertConfig(P.decide(task(), VALID_TRACE, now), P.D_NOW)

    def test_trace_shape(self):
        bad_traces = [
            ListSub(VALID_TRACE),
            tuple(VALID_TRACE),
            None,
            [DictSub(ask(0, "d_licence"))],
            [{"t": 0, "kind": "ask", "fact": "d_licence", "x": 1}],
            [{"kind": "act"}],
            [{"t": 0}],
            [{"t": True, "kind": "act"}],
            [{"t": IntSub(0), "kind": "act"}],
            [{"t": -1, "kind": "act"}],
            [{"t": 0, "kind": StrSub("act")}],
            [{"t": 0, "kind": "ACT"}],
            [{"t": 0, "kind": "act", "fact": "d_licence"}],
            [ask(0, "nope")],
            [ask(0, StrSub("d_licence"))],
            [{"t": 0, "kind": "ask"}],
            [answer(0, "d_licence")],
            [ask(1, "d_licence"), ask(0, "d_paint")],
            [act(0), act(1)],
            [act(0), ask(1, "d_licence")],
            [ask(0, "d_licence"), answer(5, "d_licence")],
        ]
        for trace in bad_traces:
            self.assertConfig(P.decide(task(), trace, 2), P.D_TRACE)

    def test_never_raises(self):
        weird = [None, 0, "", [], {}, Boom(), [Boom()], {BadKey(): 1}, {"t": Boom()},
                 [{"t": 0, "kind": Boom()}], DictSub(), StrSub("x"), object()]
        for a in weird:
            for b in weird:
                for c in (0, 2, Boom(), None):
                    rec = P.decide(a, b, c)
                    self.assertEqual(rec["decision"], P.REJECT)
        t = task()
        t["facts"]["d_paint"]["text"] = Boom()
        self.assertEqual(P.decide(t, [], 0)["reason"], P.CONFIG_ERROR)

    def test_internal_error_fails_closed(self):
        orig = P._decide
        try:
            def broken(*args):
                raise KeyError("x")
            P._decide = broken
            rec = P.decide(task(), VALID_TRACE, 2)
        finally:
            P._decide = orig
        self.assertEqual(rec, {"task_id": None, "decision": P.REJECT,
                               "reason": P.CONFIG_ERROR, "detail": P.D_INTERNAL,
                               "missing": (), "on_expiry": None})

    def test_random_mutations_never_act_unless_valid(self):
        rng = random.Random(21013)
        kinds = ["ask", "answer", "act", "ACT", StrSub("act")]
        facts = ["d_licence", "d_paint", "zz", StrSub("d_licence")]
        for _ in range(2000):
            trace = []
            t = 0
            for _ in range(rng.randint(0, 5)):
                t += rng.choice([0, 1, 1, 2, -1])
                ev = {"t": t, "kind": rng.choice(kinds)}
                if rng.random() < 0.8:
                    ev["fact"] = rng.choice(facts)
                trace.append(ev)
            now = rng.randint(-1, 14)
            rec = P.decide(task(), trace, now)
            self.assertIn(rec["decision"], P.DECISIONS)
            self.assertIn(rec["reason"], P.REASONS)
            if rec["decision"] == P.ACT:
                knows = any(type(e["kind"]) is str and e["kind"] == "answer"
                            and type(e.get("fact")) is str and e["fact"] == "d_licence"
                            and e["t"] < 10 for e in trace)
                self.assertTrue(knows)
                self.assertLess(trace[-1]["t"], 10)


class TestNoCallerCode(unittest.TestCase):
    """r2 F1-F3: nothing in the input is read before validation."""

    def test_f1_self_rewriting_key_fails_closed(self):
        t, k = f1_task()
        rec = P.decide(t, [{"t": 0, "kind": "act"}], 0)
        calls, armed = k.calls, k.armed
        k.armed = False  # disarm before inspecting t: lookups would fire it
        self.assertEqual(rec["decision"], P.REJECT)
        self.assertEqual(rec["reason"], P.CONFIG_ERROR)
        self.assertEqual(rec["detail"], P.D_TASK)
        self.assertIsNone(rec["task_id"])
        self.assertEqual(calls, 0)
        self.assertTrue(armed)
        self.assertEqual(t["facts"]["d_licence"]["label"], "plan_changing")
        self.assertEqual([key for key in t if type(key) is str],
                         ["request", "deadline", "on_expiry", "facts"])

    def test_f1_with_task_id_present_fails_closed(self):
        t, k = f1_task()
        k.armed = False
        t["task_id"] = "drivers"
        k.calls = 0
        k.armed = True
        rec = P.decide(t, [{"t": 0, "kind": "act"}], 0)
        calls = k.calls
        k.armed = False
        self.assertEqual(rec["decision"], P.REJECT)
        self.assertEqual(rec["detail"], P.D_TASK)
        self.assertEqual(calls, 0)

    def test_f3_colliding_key_never_echoed(self):
        for name in ("task_id", "on_expiry", "deadline", "facts", "request"):
            t = task()
            del t["task_id"]
            k = Mutator(t, name)
            t[k] = "victim"
            k.calls = 0
            k.armed = True
            rec = P.decide(t, VALID_TRACE, 2)
            self.assertEqual(rec["reason"], P.CONFIG_ERROR, name)
            self.assertIsNone(rec["task_id"], name)
            self.assertEqual(k.calls, 0, name)

    def test_no_eq_called_anywhere(self):
        def in_task(t, name):
            k = Mutator(t, name)
            t[k] = 1
            k.calls = 0
            return k

        def in_facts(t, name):
            k = Mutator(t, name)
            t["facts"][k] = {"text": "x", "label": "inert"}
            k.calls = 0
            return k

        def in_fact(t, name):
            k = Mutator(t, name)
            t["facts"]["d_paint"][k] = 1
            k.calls = 0
            return k

        cases = [(in_task, n) for n in P.TASK_FIELDS]
        cases += [(in_facts, n) for n in ("d_licence", "d_paint")]
        cases += [(in_fact, n) for n in P.FACT_FIELDS]
        for place, name in cases:
            t = task()
            k = place(t, name)
            rec = P.decide(t, VALID_TRACE, 2)
            self.assertEqual(rec["reason"], P.CONFIG_ERROR, (place.__name__, name))
            self.assertEqual(k.calls, 0, (place.__name__, name))
        for name in P.EVENT_FIELDS:
            ev = dict(VALID_TRACE[0])
            k = Mutator(ev, name)
            ev[k] = 1
            k.calls = 0
            rec = P.decide(task(), [ev] + VALID_TRACE[1:], 2)
            self.assertEqual(rec["detail"], P.D_TRACE, name)
            self.assertEqual(k.calls, 0, name)

    def test_f1_fact_lookup_probe_order(self):
        # A colliding fact key whose index slot comes before "d_licence" in
        # the probe chain but whose entry is iterated after it: a lookup of
        # "d_licence" before every fact id is type-checked would call its
        # __eq__. All fact ids are checked first, so it never runs.
        t = task()
        facts = {}
        k = Mutator(t, "d_licence")
        facts[k] = {"text": "x", "label": "inert"}
        facts.update(t["facts"])
        del facts[k]
        facts[k] = {"text": "x", "label": "inert"}
        t["facts"] = facts
        k.calls = 0
        k.armed = True
        rec = P.decide(t, VALID_TRACE, 2)
        calls = k.calls
        k.armed = False
        self.assertIs(list(facts)[-1], k)
        self.assertEqual(rec["detail"], P.D_FACT)
        self.assertEqual(calls, 0)

    def test_f2_fallback_needs_no_call(self):
        tree = ast.parse(read("plan_ask.py"))
        fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "decide"][0]
        handlers = [n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)]
        self.assertEqual(len(handlers), 1)
        self.assertIsInstance(handlers[0].type, ast.Name)
        self.assertEqual(handlers[0].type.id, "Exception")
        self.assertEqual([n for n in ast.walk(handlers[0]) if isinstance(n, ast.Call)], [])
        # The loaded function too: one call in all (to _decide).
        calls = [i for i in dis.get_instructions(P.decide) if i.opname.startswith("CALL")]
        self.assertEqual(len(calls), 1)
        self.assertNotIn("_record", P.decide.__code__.co_names)
        self.assertEqual(P.decide(None, None, None),
                         {"task_id": None, "decision": P.REJECT, "reason": P.CONFIG_ERROR,
                          "detail": P.D_TASK, "missing": (), "on_expiry": None})

    def test_f2_raising_key_is_config_error_not_raised(self):
        for name in ("task_id", "on_expiry", "facts"):
            t = task()
            k = Mutator(t, name, interrupt)
            t[k] = 1
            k.calls = 0
            k.armed = True
            rec = P.decide(t, VALID_TRACE, 2)
            self.assertEqual(rec["reason"], P.CONFIG_ERROR)
            self.assertEqual(k.calls, 0)
        t = task()
        k = Mutator(t, "d_licence", interrupt)
        t["facts"][k] = {"text": "x", "label": "inert"}
        k.calls = 0
        k.armed = True
        self.assertEqual(P.decide(t, VALID_TRACE, 2)["detail"], P.D_FACT)
        self.assertEqual(k.calls, 0)

    def test_f2_low_recursion_headroom(self):
        def depth():
            f, n = sys._getframe(), 0
            while f is not None:
                n, f = n + 1, f.f_back
            return n

        t, trace = task(), copy.deepcopy(VALID_TRACE)
        decide, limit, old = P.decide, sys.setrecursionlimit, sys.getrecursionlimit()
        outcomes = []
        for extra in range(0, 40):
            rec = exc = None
            try:
                limit(depth() + extra)
            except RecursionError:
                continue
            try:
                rec = decide(t, trace, 2)
            except RecursionError as caught:
                exc = caught
            finally:
                limit(old)
            outcomes.append((extra, rec, exc))
        self.assertTrue(any(rec is not None for _, rec, _ in outcomes))
        for extra, rec, exc in outcomes:
            if exc is not None:
                # Only permitted when decide() could not be entered at all.
                files = [os.path.basename(fr.filename)
                         for fr in traceback.extract_tb(exc.__traceback__)]
                self.assertNotIn("plan_ask.py", files, extra)
            else:
                self.assertIn(rec["decision"], (P.ACT, P.REJECT), extra)
                if rec["decision"] == P.REJECT:
                    self.assertEqual(rec["reason"], P.CONFIG_ERROR, extra)


class TestRecords(unittest.TestCase):

    def test_record_values_clean(self):
        for task_id, strategy, rec in F.run_all():
            self.assertEqual(tuple(rec), P.RECORD_FIELDS)
            self.assertIn(rec["decision"], P.DECISIONS)
            self.assertIn(rec["reason"], P.REASONS)
            self.assertIn(rec["detail"], P.DETAILS)
            self.assertIs(type(rec["missing"]), tuple)
            self.assertEqual(list(rec["missing"]), sorted(rec["missing"]))
            self.assertIn(rec["on_expiry"], P.ON_EXPIRY_VALUES)
            self.assertIs(type(rec["task_id"]), str)
            for value in (rec["decision"], rec["reason"], rec["on_expiry"]):
                self.assertTrue(any(value is c for c in P.DECISIONS + P.REASONS))

    def test_trace_error_echoes_validated_task_id_only(self):
        rec = P.decide(task(), [{"t": 0, "kind": "nope"}], 0)
        self.assertEqual(rec["detail"], P.D_TRACE)
        self.assertEqual(rec["task_id"], "drivers")
        self.assertIs(type(rec["task_id"]), str)

    def test_config_error_does_not_echo_spoofed_id(self):
        t = task()
        t["task_id"] = StrSub("drivers")
        self.assertIsNone(P.decide(t, VALID_TRACE, 2)["task_id"])


class TestFixtures(unittest.TestCase):

    def test_expected_table(self):
        rows = F.run_all()
        self.assertEqual(len(rows), len(F.EXPECTED))
        seen = set()
        for task_id, strategy, rec in rows:
            key = (task_id, strategy)
            self.assertNotIn(key, seen)
            seen.add(key)
            self.assertIn(key, F.EXPECTED)
            self.assertEqual((rec["decision"], rec["reason"], rec["missing"]),
                             F.EXPECTED[key], key)

    def test_fixture_invariants(self):
        ids = [t["task_id"] for t in F.tasks()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sorted({t["on_expiry"] for t in F.tasks()}),
                         sorted(P.ON_EXPIRY_VALUES))
        for t in F.tasks():
            labels = [v["label"] for v in t["facts"].values()]
            self.assertIn("plan_changing", labels)
            self.assertIn("inert", labels)
            self.assertIs(type(t["deadline"]), int)
            self.assertIn("on_expiry", t)

    def test_fixture_labels_pinned(self):
        want = {
            "drivers": {"d_licence": "plan_changing", "d_paint": "inert"},
            "nurses": {"n_cert": "plan_changing", "n_leave": "plan_changing",
                       "n_parking": "inert"},
            "room": {"r_capacity": "plan_changing", "r_colour": "inert"},
        }
        got = {t["task_id"]: {f: v["label"] for f, v in t["facts"].items()}
               for t in F.tasks()}
        self.assertEqual(got, want)

    def test_missing_order_is_sorted(self):
        # r2 F4: facts inserted out of order still give a sorted missing.
        t = {"task_id": "order", "request": "r", "deadline": 5, "on_expiry": "HOLD",
             "facts": {"b": {"text": "B.", "label": "plan_changing"},
                       "c": {"text": "C.", "label": "inert"},
                       "a": {"text": "A.", "label": "plan_changing"}}}
        for trace, now in (([act(0)], 0), ([], 1), ([], 5)):
            self.assertEqual(P.decide(t, trace, now)["missing"], ("a", "b"))
        rec = P.decide(t, [ask(0, "b"), answer(1, "b"), act(2)], 2)
        self.assertEqual(rec["missing"], ("a",))

    def test_fixture_world_pinned(self):
        # r2 F5: deadlines, on_expiry and the one-step operator latency.
        got = {t["task_id"]: (t["deadline"], t["on_expiry"]) for t in F.tasks()}
        self.assertEqual(got, {"drivers": (10, "HOLD"), "nurses": (8, "ESCALATE"),
                               "room": (6, "DENY")})
        for t in F.tasks():
            for strategy in ("inert_then_act", "plan_changing_then_act", "ask_all_then_act"):
                trace, _ = F.script(t, strategy)
                asks = {e["fact"]: e["t"] for e in trace if e["kind"] == "ask"}
                for e in trace:
                    if e["kind"] == "answer":
                        self.assertEqual(e["t"], asks[e["fact"]] + 1, (t["task_id"], strategy))
        trace, now = F.script(task("nurses"), "late_answer")
        self.assertEqual(now, 9)
        self.assertEqual([e["t"] for e in trace], [1, 1, 8, 8, 9])

    def test_tasks_returns_copies(self):
        a = F.tasks()
        a[0]["facts"].clear()
        self.assertTrue(F.tasks()[0]["facts"])

    def test_determinism(self):
        self.assertEqual(F.run_all(), F.run_all())

    def test_inputs_not_mutated(self):
        t = task()
        trace = copy.deepcopy(VALID_TRACE)
        before = (copy.deepcopy(t), copy.deepcopy(trace))
        P.decide(t, trace, 2)
        self.assertEqual((t, trace), before)


class TestDocs(unittest.TestCase):

    def test_banned_words_absent(self):
        for name in ALL:
            text = read(name).lower()
            for word in BANNED:
                self.assertNotIn(word.lower(), text, (name, word))

    def test_no_absolute_paths_or_markers(self):
        for name in ALL:
            text = read(name)
            self.assertNotIn("/" + "workspace", text, name)
            self.assertNotIn("/" + "tmp", text, name)
            self.assertNotIn("/" + "home/", text, name)
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

    def test_no_paper_figures_outside_evidence(self):
        pat = re.compile(r"43\s*%|\b7\s*%|58\s*-\s*98|5\s*-\s*28|39\s*-\s*52|32\s*-\s*41|\b79\b|\b19 participants")
        for name in ("README.md", "NOTICE", "plan_ask.py", "fixtures.py"):
            self.assertIsNone(pat.search(read(name)), name)

    def test_readme_credits_and_scope(self):
        text = read("README.md")
        flat = " ".join(text.split())
        ev = json.loads(read("paper_evidence.json"))
        self.assertIn(ev["paper"]["title"], flat)
        for author in ev["paper"]["authors"]:
            self.assertIn(author, flat)
        for s in ("http://arxiv.org/licenses/nonexclusive-distrib/1.0/",
                  "This is ongoing work and will be updated.",
                  "method sketch, not law", "synthetic", "UNVERIFIED",
                  "w20-plan-change-notice", "Ack is not act", "#119",
                  "mb-fail-closed-deputy", "w20-fidelity-audit", "on_unmeasured",
                  "Ask2Decide"):
            self.assertIn(s, flat, s)

    def test_evidence_shape(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.13015")
        self.assertEqual(ev["paper"]["version"], "v1")
        quotes = " ".join(c["quote"] for c in ev["claims"])
        for fig in ("43% versus 7%", "58-98%", "5-28%", "39-52% versus 32-41%"):
            self.assertIn(fig, quotes)
        for c in ev["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")
            self.assertEqual(len(c["quote"]), c["length"])

    def test_quotes_exact_in_source(self):
        ev = json.loads(read("paper_evidence.json"))
        src = ev["source"]
        if not SOURCES:
            self.skipTest("W21ASK_SOURCES not set")
        path = os.path.join(SOURCES, src["file"])
        if not os.path.exists(path):
            self.skipTest("abstract copy not present")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), src["sha256"])
        self.assertEqual(len(text), src["chars"])
        for c in ev["claims"]:
            self.assertEqual(text.count(c["quote"]), 1, c["id"])
            self.assertEqual(text[c["offset"]:c["offset"] + c["length"]], c["quote"], c["id"])


if __name__ == "__main__":
    unittest.main()
