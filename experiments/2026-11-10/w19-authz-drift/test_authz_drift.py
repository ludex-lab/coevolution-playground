"""Tests for the w19-authz-drift method sketch (stdlib unittest; pytest runs them too).

Run: python3 -m unittest test_authz_drift.py -v   (or python3 -m pytest -q test_authz_drift.py)
The excerpt check reads the paper HTML and abs page from /tmp and is skipped
when they are absent:
  curl -sL -A 'Mozilla/5.0' https://arxiv.org/html/2611.09113 -o /tmp/w19az-2611.09113.html
  curl -sL -A 'Mozilla/5.0' https://arxiv.org/abs/2611.09113 -o /tmp/w19az-abs.html
"""

import ast
import contextlib
import copy
import dataclasses
import hashlib
import html
import inspect
import io
import json
import os
import re
import sys
import unittest

import authz_drift as A
import fixtures as F

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_HTML = "/tmp/w19az-2611.09113.html"
PAPER_ABS = "/tmp/w19az-abs.html"
IMPL = ("authz_drift.py", "fixtures.py")
PROSE = ("README.md", "NOTICE")
LAYER = {"detect", "check_trajectory", "flag", "hold", "report", "compare",
         "_unknown", "_exceeded"}


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def evidence():
    return json.loads(read("paper_evidence.json"))


def normalize(raw):
    t = raw
    for tag in ("script", "style", "math"):
        t = re.sub(r"<%s\b.*?</%s>" % (tag, tag), "", t, flags=re.DOTALL | re.IGNORECASE)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t)


def deliverables():
    return sorted(n for n in os.listdir(HERE)
                  if os.path.isfile(os.path.join(HERE, n)) and not n.endswith(".pyc"))


def derived(t, which="shortcut"):
    res = A.check_trajectory(t["grant"], t[which])
    return res["status"], res["drift_types"], res["first_drift_step"]


def in_window(g, a):
    return g.window_open <= a.at < g.window_close


def in_scope(g, a):
    return any(a.target.startswith(p) for p in g.scope)


class OverCollection(unittest.TestCase):
    """(a) tool, scope and time inside the grant, data read beyond the need."""

    def test_a_fields_over_collection_is_data_drift(self):
        t = F.task("followup_note")
        g = t["grant"]
        for a in t["shortcut"]:
            self.assertIn(a.tool, g.tools)
            self.assertTrue(in_scope(g, a))
            self.assertTrue(in_window(g, a))
        status, types, first = derived(t)
        self.assertEqual(status, A.DRIFT)
        self.assertEqual(types, (A.DATA,))
        self.assertEqual(first, 1)
        f = A.detect(g, t["shortcut"][0])
        self.assertEqual(f.verdict, A.RESTRICT)
        self.assertEqual(f.exceeded, (A.DATA,))

    def test_a_rows_over_collection_is_data_drift(self):
        t = F.task("stock_summary")
        g = t["grant"]
        a = t["shortcut"][0]
        self.assertIn(a.tool, g.tools)
        self.assertTrue(in_scope(g, a) and in_window(g, a))
        self.assertLessEqual(set(a.reads["ledger"]), set(g.need["ledger"].fields))
        self.assertEqual(derived(t)[:2], (A.DRIFT, (A.DATA,)))

    def test_a_only_the_read_differs_from_compliant(self):
        for name in ("followup_note", "stock_summary"):
            t = F.task(name)
            for c, s in zip(t["compliant"], t["shortcut"]):
                self.assertEqual((c.tool, c.target, c.at), (s.tool, s.target, s.at))
            self.assertEqual(A.compare(t["grant"], t["compliant"], t["shortcut"])["added_types"],
                             (A.DATA,))

    def test_a_unneeded_source_is_data_drift(self):
        g = F.task("followup_note")["grant"]
        a = F.act(1, "lookup_contact", "contacts/mina/card", 1,
                  {"contacts": {"name"}, "calendar": {"busy"}}, {"contacts": 1, "calendar": 3})
        self.assertEqual(A.detect(g, a).exceeded, (A.DATA,))

    def test_a_reading_less_than_need_is_within_bounds(self):
        g = F.task("followup_note")["grant"]
        a = F.act(1, "lookup_contact", "contacts/mina/card", 1, {"contacts": {"email"}}, {"contacts": 1})
        self.assertEqual(A.detect(g, a).verdict, A.WITHIN_BOUNDS)


class DerivedType(unittest.TestCase):
    """(b) drift type comes from the exceeded limit, never from fixture labels."""

    def test_b_shortcut_types_match_expected(self):
        for t in F.TASKS:
            with self.subTest(t["name"]):
                self.assertEqual(derived(t)[1], t["expected"])

    def test_b_relabel_or_remove_labels_changes_nothing(self):
        base = [derived(t) + derived(t, "compliant") for t in F.TASKS]
        tasks = copy.deepcopy(F.TASKS)
        labels = [t["expected"] for t in tasks]
        for t, lab in zip(tasks, labels[1:] + labels[:1]):
            t["expected"] = lab
        self.assertEqual([derived(t) + derived(t, "compliant") for t in tasks], base)
        for t in tasks:
            t["expected"] = ("bogus",)
            t["name"] = "renamed"
        self.assertEqual([derived(t) + derived(t, "compliant") for t in tasks], base)
        for t in tasks:
            del t["expected"]
        self.assertEqual([derived(t) + derived(t, "compliant") for t in tasks], base)

    def test_b_types_follow_the_grant(self):
        t = F.task("poll_close")
        wider = dataclasses.replace(t["grant"], tools=t["grant"].tools | {"send_invites"})
        self.assertEqual(A.check_trajectory(wider, t["shortcut"])["status"], A.WITHIN_BOUNDS)
        t = F.task("workshop_notice")
        wider = dataclasses.replace(t["grant"], scope=t["grant"].scope + ("boards/village-square/",))
        self.assertEqual(A.check_trajectory(wider, t["shortcut"])["status"], A.WITHIN_BOUNDS)
        t = F.task("followup_note")
        need = {"contacts": A.Need(frozenset({"name", "email", "visit_history", "private_notes"}), 1)}
        wider = dataclasses.replace(t["grant"], need=need)
        self.assertEqual(A.check_trajectory(wider, t["shortcut"])["status"], A.WITHIN_BOUNDS)
        t = F.task("poll_close")
        narrower = dataclasses.replace(t["grant"], tools=t["grant"].tools - {"close_poll"})
        self.assertEqual(A.check_trajectory(narrower, t["compliant"])["drift_types"], (A.TOOL,))

    def test_b_each_limit_alone(self):
        g = F.task("followup_note")["grant"]
        ok = dict(tool="lookup_contact", target="contacts/mina/card", at=1,
                  reads={"contacts": {"name"}}, rows={"contacts": 1})
        cases = {A.TOOL: dict(tool="scrape_contacts"), A.SCOPE: dict(target="contacts/tomas/card"),
                 A.DATA: dict(rows={"contacts": 2}), A.TIME: dict(at=10)}
        for limit, change in cases.items():
            kw = dict(ok, **change)
            f = A.detect(g, F.act(1, kw["tool"], kw["target"], kw["at"], kw["reads"], kw["rows"]))
            self.assertEqual(f.exceeded, (limit,), limit)

    def test_b_check_signature_takes_no_labels(self):
        self.assertEqual(list(inspect.signature(A.check_trajectory).parameters), ["grant", "actions"])
        self.assertEqual(list(inspect.signature(A.detect).parameters), ["grant", "action"])
        names = {f.name for f in dataclasses.fields(A.Action)}
        self.assertEqual(names, {"step", "tool", "target", "at", "reads", "rows", "effect_until"})

    def test_b_layer_source_never_names_labels(self):
        src = read("authz_drift.py")
        for bad in ("expected", "label", "TASKS", "fixtures", "shortcut", "compliant_path"):
            self.assertNotIn(bad, src, bad)
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in LAYER:
                strs = {n.value for n in ast.walk(node) if isinstance(n, ast.Constant)
                        and isinstance(n.value, str)}
                self.assertFalse(strs & {"name"}, node.name)


class SilenceDoctrine(unittest.TestCase):
    """(c) once the window has passed: hold, never within bounds."""

    def test_c_every_compliant_step_shifted_past_close_is_held(self):
        for t in F.TASKS:
            g = t["grant"]
            for delta in (0, 1, 100):
                late = [dataclasses.replace(a, at=g.window_close + delta) for a in t["compliant"]]
                res = A.check_trajectory(g, late)
                with self.subTest(t["name"], delta=delta):
                    self.assertEqual(res["status"], A.HOLD)
                    for f in res["findings"]:
                        self.assertEqual(f.verdict, A.HOLD)
                        self.assertIn(A.TIME, f.exceeded)

    def test_c_close_is_exclusive_and_before_open_held(self):
        t = F.task("late_recheck")
        g = t["grant"]
        a = t["compliant"][0]
        self.assertEqual(A.detect(g, dataclasses.replace(a, at=g.window_close - 1)).verdict, A.WITHIN_BOUNDS)
        self.assertEqual(A.detect(g, dataclasses.replace(a, at=g.window_close)).verdict, A.HOLD)
        self.assertEqual(A.detect(g, dataclasses.replace(a, at=g.window_open - 1)).verdict, A.HOLD)

    def test_c_effect_past_close_held(self):
        t = F.task("reminder_tail")
        res = A.check_trajectory(t["grant"], t["shortcut"])
        self.assertEqual(res["status"], A.HOLD)
        self.assertEqual(res["drift_types"], (A.TIME,))
        self.assertEqual(A.hold(t["grant"], t["shortcut"])[0].step, 2)

    def test_c_late_recheck_held_without_renewal(self):
        t = F.task("late_recheck")
        res = A.check_trajectory(t["grant"], t["shortcut"])
        self.assertEqual(res["status"], A.HOLD)
        self.assertEqual([f.verdict for f in res["findings"]], [A.WITHIN_BOUNDS, A.WITHIN_BOUNDS, A.HOLD])

    def test_c_hold_dominates_restrict(self):
        t = F.task("followup_note")
        g = t["grant"]
        late = dataclasses.replace(t["shortcut"][0], at=g.window_close + 3)
        f = A.detect(g, late)
        self.assertEqual(f.verdict, A.HOLD)
        self.assertEqual(f.exceeded, (A.DATA, A.TIME))

    def test_c_no_way_to_widen_window_in_layer(self):
        names = {f.name for f in dataclasses.fields(A.Grant)}
        self.assertEqual(names, {"tools", "scope", "window_open", "window_close", "need"})
        for fn in (A.check_trajectory, A.detect, A.flag, A.hold, A.report, A.compare):
            for p in inspect.signature(fn).parameters:
                for bad in ("renew", "extend", "consent", "now", "clock"):
                    self.assertNotIn(bad, p)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            F.TASKS[0]["grant"].window_close = 99

    def test_c_unknown_fails_closed(self):
        g = F.task("followup_note")["grant"]
        good = F.GOOD
        self.assertEqual(A.detect(g, good).verdict, A.WITHIN_BOUNDS)
        for change in (dict(tool=None), dict(target=None), dict(at=None),
                       dict(reads=None), dict(rows=None), dict(rows={})):
            with self.subTest(change):
                self.assertEqual(A.detect(g, dataclasses.replace(good, **change)).verdict, A.HOLD)
        for w in ((0, None), (None, 10), (None, None), (5, 5), (9, 3)):
            g2 = dataclasses.replace(g, window_open=w[0], window_close=w[1])
            with self.subTest(window=w):
                self.assertEqual(A.check_trajectory(g2, [good])["status"], A.HOLD)
        self.assertEqual(A.check_trajectory(None, [good])["status"], A.HOLD)
        self.assertEqual(A.check_trajectory(g, [])["status"], A.HOLD)
        dup = [good, dataclasses.replace(good)]
        self.assertEqual(A.check_trajectory(g, dup)["status"], A.HOLD)

    def test_c_vocabulary_has_no_admit_path(self):
        self.assertEqual(set(A.VERDICTS), {"within_bounds", "restrict", "hold"})
        self.assertEqual(set(A.STATUSES), {"within_bounds", "drift", "hold"})
        for v in A.VERDICTS + A.STATUSES:
            for bad in ("al" + "low", "appro" + "v", "per" + "mit", "pass", "ok", "go"):
                self.assertNotIn(bad, v)


class Feasibility(unittest.TestCase):
    """(d) every fixture's compliant path actually checks within bounds."""

    def test_d_every_compliant_path_within_bounds(self):
        self.assertEqual(len(F.TASKS), 7)
        for t in F.TASKS:
            with self.subTest(t["name"]):
                res = A.check_trajectory(t["grant"], t["compliant"])
                self.assertEqual(res["status"], A.WITHIN_BOUNDS)
                self.assertEqual(res["drift_types"], ())
                self.assertIsNone(res["first_drift_step"])
                self.assertTrue(all(f.verdict == A.WITHIN_BOUNDS for f in res["findings"]))
                self.assertTrue(F.covers(t["required_tools"], t["compliant"]))
                self.assertTrue(F.feasible(t))

    def test_d_every_shortcut_is_flagged(self):
        for t in F.TASKS:
            with self.subTest(t["name"]):
                self.assertNotEqual(derived(t)[0], A.WITHIN_BOUNDS)
                self.assertTrue(A.flag(t["grant"], t["shortcut"]))

    def test_d_shortcut_still_reaches_the_task(self):
        for t in F.TASKS:
            self.assertTrue(F.covers(t["required_tools"], t["shortcut"]), t["name"])

    def test_d_refuse_everything_gate_fails_feasibility(self):
        def refuse_all(grant, actions):
            return {"status": A.DRIFT, "findings": [], "drift_types": (A.DATA,), "first_drift_step": 1}
        for t in F.TASKS:
            self.assertFalse(F.feasible(t, check=refuse_all), t["name"])

    def test_d_dropping_a_required_step_fails_feasibility(self):
        t = copy.deepcopy(F.task("poll_close"))
        t["compliant"] = t["compliant"][:-1]
        self.assertFalse(F.feasible(t))


NAN = float("nan")
INF = float("inf")
NOT_COUNTS = (900.0, 25.0, "900", "25", None, True, False, -1, NAN, INF)
NOT_TICKS = (NAN, INF, -INF, "5", 5.0, True, False, b"5")


def ledger(step, at, rows, source="ledger"):
    return F.act(step, "read_ledger", "ledger/autumn/grain", at, {source: {"item", "count"}}, {source: rows})


def contact(target="contacts/mina/card", at=1, effect_until=None):
    return F.act(1, "lookup_contact", target, at, {"contacts": {"name"}}, {"contacts": 1}, effect_until)


class FailClosedCounts(unittest.TestCase):
    """(a) regressions: counts must be real ints; rows add up per source."""

    def test_a_non_int_row_count_held(self):
        g = F.task("stock_summary")["grant"]
        for n in NOT_COUNTS:
            with self.subTest(rows=n):
                f = A.detect(g, ledger(1, 3, n))
                self.assertEqual(f.verdict, A.HOLD)
                self.assertIn("rows:ledger", f.unknown)
                self.assertEqual(A.check_trajectory(g, [ledger(1, 3, n)])["status"], A.HOLD)

    def test_a_non_int_row_count_on_any_source_held(self):
        g = F.task("followup_note")["grant"]
        a = F.act(1, "lookup_contact", "contacts/mina/card", 1, {"contacts": {"name"}},
                  {"contacts": 1, "extra": "3"})
        self.assertEqual(A.detect(g, a).verdict, A.HOLD)

    def test_a_non_int_row_cap_held(self):
        t = F.task("stock_summary")
        for cap in NOT_COUNTS:
            g = dataclasses.replace(t["grant"], need={"ledger": A.Need(frozenset({"item", "count"}), cap)})
            with self.subTest(cap=cap):
                self.assertEqual(A.check_trajectory(g, t["compliant"])["status"], A.HOLD)

    def test_a_malformed_read_sets_held(self):
        g = F.task("followup_note")["grant"]
        for reads in ({"contacts": "name"}, {"contacts": ["name"]}, {"contacts": None}, ["contacts"]):
            a = A.Action(1, "lookup_contact", "contacts/mina/card", 1, reads, {"contacts": 1})
            with self.subTest(reads=reads):
                self.assertEqual(A.detect(g, a).verdict, A.HOLD)

    def test_a_split_reads_sum_per_source(self):
        g = F.task("stock_summary")["grant"]
        traj = [ledger(i, i, 25) for i in range(1, 5)]
        for a in traj:
            self.assertEqual(A.detect(g, a).verdict, A.WITHIN_BOUNDS)
        res = A.check_trajectory(g, traj)
        self.assertEqual(res["status"], A.DRIFT)
        self.assertEqual(res["drift_types"], (A.DATA,))
        self.assertEqual(res["first_drift_step"], 2)
        self.assertEqual([f.verdict for f in res["findings"]],
                         [A.WITHIN_BOUNDS, A.RESTRICT, A.RESTRICT, A.RESTRICT])
        self.assertEqual([f.step for f in A.flag(g, traj)], [2, 3, 4])

    def test_a_split_reads_up_to_need_within_bounds(self):
        g = F.task("stock_summary")["grant"]
        for parts in ((25,), (10, 15), (5, 5, 5, 5, 5), (0, 25, 0)):
            traj = [ledger(i + 1, i + 1, n) for i, n in enumerate(parts)]
            with self.subTest(parts=parts):
                self.assertEqual(A.check_trajectory(g, traj)["status"], A.WITHIN_BOUNDS)
        traj = [ledger(1, 1, 10), ledger(2, 2, 16)]
        self.assertEqual(A.check_trajectory(g, traj)["first_drift_step"], 2)

    def test_a_totals_are_per_source_and_per_task(self):
        g = dataclasses.replace(F.task("stock_summary")["grant"], need={
            "ledger": A.Need(frozenset({"item", "count"}), 25),
            "prices": A.Need(frozenset({"item", "count"}), 25)})
        traj = [ledger(1, 1, 25), ledger(2, 2, 25, "prices")]
        self.assertEqual(A.check_trajectory(g, traj)["status"], A.WITHIN_BOUNDS)
        # A second call (another task run under the same grant) starts from zero.
        self.assertEqual(A.check_trajectory(g, traj)["status"], A.WITHIN_BOUNDS)
        self.assertEqual(A.check_trajectory(g, traj + [ledger(3, 3, 1)])["drift_types"], (A.DATA,))

    def test_a_bad_count_makes_later_totals_unknown(self):
        g = F.task("stock_summary")["grant"]
        res = A.check_trajectory(g, [ledger(1, 1, "10"), ledger(2, 2, 1), ledger(3, 3, 1)])
        self.assertEqual(res["status"], A.HOLD)
        self.assertEqual([f.verdict for f in res["findings"]], [A.HOLD, A.HOLD, A.HOLD])

    def test_a_float_rows_over_cap_never_within_bounds(self):
        t = F.task("stock_summary")
        bad = [dataclasses.replace(t["shortcut"][0], rows={"ledger": 900.0}), t["shortcut"][1]]
        self.assertNotEqual(A.check_trajectory(t["grant"], bad)["status"], A.WITHIN_BOUNDS)


class FailClosedTimes(unittest.TestCase):
    """(c) regressions: NaN, inf, strings and other non-int times hold."""

    def test_c_effect_one_tick_past_close_held(self):
        g = F.task("followup_note")["grant"]
        at_close = A.detect(g, contact(effect_until=g.window_close))
        self.assertEqual((at_close.verdict, at_close.exceeded), (A.WITHIN_BOUNDS, ()))
        past = A.detect(g, contact(effect_until=g.window_close + 1))
        self.assertEqual((past.verdict, past.exceeded), (A.HOLD, (A.TIME,)))
        t = F.task("reminder_tail")
        late = [t["compliant"][0], dataclasses.replace(t["compliant"][1], effect_until=t["grant"].window_close + 1)]
        self.assertEqual(A.check_trajectory(t["grant"], late)["status"], A.HOLD)

    def test_c_bad_action_time_held_not_crash(self):
        g = F.task("followup_note")["grant"]
        for at in NOT_TICKS:
            with self.subTest(at=at):
                self.assertEqual(A.detect(g, contact(at=at)).verdict, A.HOLD)
                self.assertEqual(A.check_trajectory(g, [contact(at=at)])["status"], A.HOLD)

    def test_c_bad_effect_end_held_not_crash(self):
        g = F.task("followup_note")["grant"]
        for e in NOT_TICKS:
            with self.subTest(effect_until=e):
                f = A.detect(g, contact(effect_until=e))
                self.assertEqual(f.verdict, A.HOLD)
                self.assertIn("effect_until", f.unknown)

    def test_c_effect_before_start_held(self):
        g = F.task("followup_note")["grant"]
        self.assertEqual(A.detect(g, contact(at=5, effect_until=4)).verdict, A.HOLD)
        self.assertEqual(A.detect(g, contact(at=5, effect_until=5)).verdict, A.WITHIN_BOUNDS)

    def test_c_bad_window_held_not_crash(self):
        g = F.task("followup_note")["grant"]
        for w in ((0.0, 10), (0, 10.0), (0, "10"), ("0", 10), (False, 10), (0, True),
                  (0, INF), (NAN, 10), (-INF, INF)):
            g2 = dataclasses.replace(g, window_open=w[0], window_close=w[1])
            with self.subTest(window=w):
                self.assertEqual(A.check_trajectory(g2, [F.GOOD])["status"], A.HOLD)

    def test_c_bad_step_held_not_crash(self):
        g = F.task("followup_note")["grant"]
        for steps in (("1", 2), (1.0, 2), (None, 1), (True, 2)):
            traj = [dataclasses.replace(F.GOOD, step=steps[0]), dataclasses.replace(F.GOOD, step=steps[1], at=2)]
            with self.subTest(steps=steps):
                self.assertEqual(A.check_trajectory(g, traj)["status"], A.HOLD)


class ScopeBoundary(unittest.TestCase):
    """(b) regressions: scope prefixes match whole path segments only."""

    def test_b_dotdot_segment_held_and_scope(self):
        g = F.task("followup_note")["grant"]
        for target in ("contacts/mina/../tomas/card", "../contacts/mina/card",
                       "contacts/mina/..", "contacts/mina/card/../../tomas"):
            with self.subTest(target=target):
                f = A.detect(g, contact(target=target))
                self.assertEqual(f.verdict, A.HOLD)
                self.assertIn(A.SCOPE, f.exceeded)
                self.assertIn("target", f.unknown)

    def test_b_prefix_matches_on_segment_boundary_only(self):
        g = F.task("followup_note")["grant"]
        for scope in (("contacts/mina",), ("contacts/mina/",), ("contacts//mina/./",)):
            g2 = dataclasses.replace(g, scope=scope)
            with self.subTest(scope=scope):
                for target in ("contacts/mina/card", "contacts/mina", "contacts//mina/./card"):
                    self.assertEqual(A.detect(g2, contact(target=target)).verdict, A.WITHIN_BOUNDS, target)
                for target in ("contacts/minako/card", "contacts/mina-old/card", "contacts/min", "contacts"):
                    f = A.detect(g2, contact(target=target))
                    self.assertEqual((f.verdict, f.exceeded), (A.RESTRICT, (A.SCOPE,)), target)

    def test_b_empty_scope_held(self):
        g = F.task("followup_note")["grant"]
        for scope in ((), ("",), ("/",), (".",), ("./",), ("contacts/mina/", ""), None, "contacts/mina/"):
            g2 = dataclasses.replace(g, scope=scope)
            with self.subTest(scope=scope):
                f = A.detect(g2, contact(target="anything/at/all"))
                self.assertEqual(f.verdict, A.HOLD)
                self.assertIn("scope", f.unknown)
                self.assertEqual(A.detect(g2, contact()).verdict, A.HOLD)

    def test_b_dotdot_in_scope_prefix_held(self):
        g = dataclasses.replace(F.task("followup_note")["grant"], scope=("contacts/mina/../",))
        f = A.detect(g, contact(target="contacts/tomas/card"))
        self.assertEqual(f.verdict, A.HOLD)
        self.assertIn(A.SCOPE, f.exceeded)

    def test_b_empty_or_non_string_target_or_tool_held(self):
        g = F.task("followup_note")["grant"]
        for target in ("", "/", ".", 5, b"contacts/mina/card"):
            with self.subTest(target=target):
                self.assertEqual(A.detect(g, contact(target=target)).verdict, A.HOLD)
        self.assertEqual(A.detect(g, dataclasses.replace(F.GOOD, tool=7)).verdict, A.HOLD)

    def test_b_substring_of_top_segment_is_not_scope(self):
        g = F.task("followup_note")["grant"]
        f = A.detect(g, contact(target="contacts/tomas/mina/card"))
        self.assertEqual(f.exceeded, (A.SCOPE,))


class Layer(unittest.TestCase):

    def test_report_flag_compare(self):
        t = F.task("archive_dig")
        out = A.report(t["grant"], t["shortcut"])
        self.assertTrue(out.startswith("authz check: drift types=data,tool,scope first_drift_step=2"))
        self.assertEqual([f.step for f in A.flag(t["grant"], t["shortcut"])], [2])
        cmp_ = A.compare(t["grant"], t["compliant"], t["shortcut"])
        self.assertEqual(cmp_, {"first_status": A.WITHIN_BOUNDS, "second_status": A.DRIFT,
                                "added_types": (A.DATA, A.TOOL, A.SCOPE)})

    def test_check_does_not_mutate_inputs(self):
        t = copy.deepcopy(F.task("archive_dig"))
        snap = copy.deepcopy(t)
        A.check_trajectory(t["grant"], t["shortcut"])
        self.assertEqual(t, snap)

    def test_public_verbs(self):
        funcs = [n for n, v in vars(A).items()
                 if inspect.isfunction(v) and not n.startswith("_") and v.__module__ == "authz_drift"]
        self.assertEqual(sorted(funcs), ["check_trajectory", "compare", "detect", "flag", "hold", "report"])
        for n in dir(A):
            low = n.lower()
            for bad in ("al" + "low", "appro" + "v", "per" + "mit", "clear", "admit", "grant_more"):
                self.assertNotIn(bad, low, n)


class Fixtures(unittest.TestCase):

    def test_all_fixtures_pass(self):
        for name, fn in F.FIXTURES:
            with self.subTest(name):
                self.assertTrue(fn()[0], name)

    def test_main_returns_zero_and_is_deterministic(self):
        outs = []
        for _ in range(2):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(F.main(), 0)
            outs.append(buf.getvalue())
        self.assertEqual(outs[0], outs[1])
        self.assertIn("tasks: 7, fixtures: 25/25 passed", outs[0])


class PaperEvidence(unittest.TestCase):

    def test_metadata(self):
        ev = evidence()
        p = ev["paper"]
        self.assertEqual(p["arxiv_id"], "2611.09113")
        self.assertEqual(p["licence_url"], "http://creativecommons.org/licenses/by/4.0/")
        self.assertEqual(p["authors"][0], "Chuxue Cao")
        self.assertEqual(len(p["authors"]), 10)
        self.assertTrue(p["citation_title"].startswith("Authorization Drift in LLM Agents"))
        pin = ev["implementation_pin"]
        self.assertEqual(pin["commit"], "4d69a706e4e47148b51d35077e812260e64f6214")
        self.assertEqual(pin["licence"], "MIT")
        self.assertIn("not cloned", pin["status"])
        self.assertEqual(ev["empirical_claims"]["status"], "UNVERIFIED")
        for c in ev["empirical_claims"]["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")

    def test_required_quotes_present(self):
        quotes = [e["excerpt"] for e in evidence()["excerpts"]]
        self.assertTrue(3 <= len(quotes) <= 6)
        for needle in ("without an adversary", "sufficient compliant path",
                       "early data over-collection", "intended execution window",
                       "beyond what the task requires"):
            self.assertTrue(any(needle in q for q in quotes), needle)

    def test_offsets_consistent(self):
        keys = {"id", "section", "excerpt", "chars", "normalized_offset",
                "end_offset_exclusive", "occurrences", "source_window_sha256", "status"}
        for e in evidence()["excerpts"]:
            self.assertEqual(set(e), keys)
            self.assertEqual(e["status"], "FOUND")
            self.assertEqual(e["end_offset_exclusive"] - e["normalized_offset"], len(e["excerpt"]))
            self.assertEqual(e["chars"], len(e["excerpt"]))

    @unittest.skipUnless(os.path.exists(PAPER_HTML) and os.path.exists(PAPER_ABS),
                         "paper HTML/abs not cached in /tmp")
    def test_excerpts_found(self):
        with open(PAPER_HTML, encoding="utf-8") as fh:
            t = normalize(fh.read())
        with open(PAPER_ABS, encoding="utf-8") as fh:
            ta = normalize(fh.read())
        ev = evidence()
        self.assertEqual(len(t), ev["normalization"]["normalized_chars"])
        for e in ev["excerpts"]:
            with self.subTest(e["id"]):
                s, end = e["normalized_offset"], e["end_offset_exclusive"]
                self.assertEqual(t[s:end], e["excerpt"])
                self.assertEqual(t.count(e["excerpt"]), e["occurrences"])
                w = t[max(0, s - 64):min(len(t), end + 64)]
                self.assertEqual(hashlib.sha256(w.encode("utf-8")).hexdigest(),
                                 e["source_window_sha256"])
        for c in ev["empirical_claims"]["claims"]:
            src = t if c["source"] == "html" else ta
            self.assertEqual(src.count(c["text"]), c["occurrences"], c["id"])
        self.assertIn('href="http://creativecommons.org/licenses/by/4.0/"',
                      open(PAPER_ABS, encoding="utf-8").read())


class Hygiene(unittest.TestCase):

    def test_deliverables_only(self):
        expected = ["NOTICE", "README.md", "authz_drift.py", "fixtures.py",
                    "paper_evidence.json", "test_authz_drift.py"]
        extra = set(deliverables()) - set(expected) - {"day" + "-README.md"}
        self.assertEqual(extra, set())

    def test_no_admit_vocabulary(self):
        for name in IMPL + PROSE:
            src = read(name).lower()
            for needle in ("al" + "low", "appro" + "v", "per" + "mit"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))

    def test_absence_needles(self):
        needles = ("Two" + "-Ledger", "2611." + "06989", "HM" + "AC", "2611." + "07483",
                   "inspect" + "_ai", "open" + "ai", "anth" + "ropic", "NA" + "TS", "dock" + "er",
                   "Fei" + "shu", "SQL" + "ite", "dae" + "mon", "vot" + "ing", "ensem" + "ble")
        for name in deliverables():
            src = read(name)
            for n in needles:
                self.assertNotIn(n, src, "%s: %s" % (name, n))

    def test_no_paper_figures_outside_evidence(self):
        needles = ("6" + "48", "25,2" + "07", "0." + "43", "0." + "61", "86." + "18", "93." + "5",
                   "seven do" + "mains", "13 L" + "LMs", "four juris" + "dictions", "thir" + "teen")
        for name in IMPL + PROSE:
            src = read(name).lower()
            for n in needles:
                self.assertNotIn(n.lower(), src, "%s: %s" % (name, n))

    def test_no_conflict_markers(self):
        markers = ("<" * 7, ">" * 7)
        sep = "=" * 7
        for name in deliverables():
            src = read(name)
            for m in markers:
                self.assertNotIn(m, src, "%s: %s" % (name, m))
            for line in src.splitlines():
                self.assertNotEqual(line.strip(), sep, name)

    def test_banned_words_everywhere(self):
        words = ("KE" + "EP", "Cloud" + "Agent", "Smi" + "th", "Chec" + "ker")
        for name in deliverables():
            src = read(name)
            for w in words:
                self.assertNotIn(w, src, "%s: %s" % (name, w))

    def test_prose_words(self):
        for name in PROSE:
            src = read(name)
            low = src.lower()
            self.assertNotIn("kee" + "p", low, name)
            self.assertIsNone(re.search(r"\bO" + r"rk\b", src), name)
            self.assertNotIn("pull " + "request", low, name)
            self.assertIsNone(re.search(r"\bmer" + r"ge\b", src, re.IGNORECASE), name)

    def test_readme_standing_notes(self):
        src = read("README.md")
        for needle in ("method sketch", "not a reproduction", "not village law",
                       "not Team OS law", "UNVERIFIED",
                       "python3 -m pytest -q test_authz_drift.py", "python3 fixtures.py",
                       "Builder reflection", "Ludex:", "2611.09113", "creativecommons.org/licenses/by/4.0",
                       "https://cursor.com/codebase/coevolution-lab/playground/pull/19",
                       "4d69a706e4e47148b51d35077e812260e64f6214",
                       "Implementation may be complete; it is not declared verified."):
            self.assertIn(needle, src, needle)

    def test_notice(self):
        src = read("NOTICE")
        for needle in ("2611.09113", "Chuxue Cao", "Sirui Han", "CC BY 4.0",
                       "creativecommons.org/licenses/by/4.0", "4d69a706e4e47148b51d35077e812260e64f6214",
                       "MIT", "not cloned", "stdlib", "Synthetic"):
            self.assertIn(needle, src, needle)

    def test_no_test_reads_parent_index(self):
        self.assertNotIn("day" + "-README", read("test_authz_drift.py"))

    def test_imports_stdlib_only(self):
        ok = {"dataclasses", "typing", "authz_drift"}
        for name in IMPL:
            for node in ast.walk(ast.parse(read(name))):
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [node.module]
                else:
                    continue
                for m in mods:
                    root = m.split(".")[0]
                    self.assertIn(root, ok, "%s imports %s" % (name, m))
                    if root != "authz_drift" and hasattr(sys, "stdlib_module_names"):
                        self.assertIn(root, sys.stdlib_module_names)

    def test_no_network_or_process_modules(self):
        for name in IMPL:
            src = read(name)
            for n in ("soc" + "ket", "url" + "lib", "http" + ".client", "subpro" + "cess",
                      "sql" + "ite3", "thread" + "ing", "requ" + "ests"):
                self.assertNotIn(n, src, "%s: %s" % (name, n))


if __name__ == "__main__":
    unittest.main()
