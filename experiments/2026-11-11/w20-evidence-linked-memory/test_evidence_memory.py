"""Tests for the w20-evidence-linked-memory method sketch (stdlib unittest).

Run: python3 -m unittest test_evidence_memory.py -v
Test class names carry the done-when letter (DoneWhenA ... DoneWhenF).
World* classes pin the shape of the adversarial fixtures, so a fixture that
loses its adversarial shape fails a test even when its expected outcome still
holds. The source checks read the lab copies named in paper_evidence.json
from the directory in $W20ELM_SOURCES. There is no default: with the
variable unset they are skipped ("W20ELM_SOURCES not set"); with it set, a
missing lab copy fails.
"""

import ast
import hashlib
import json
import os
import re
import unittest

import evidence_memory as E
import fixtures as F

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W20ELM_SOURCES")
CODE = ("evidence_memory.py", "fixtures.py")
DOCS = ("README.md", "NOTICE")
ALL = DOCS + CODE + ("test_evidence_memory.py", "mutants.py", "paper_evidence.json")
PERMIT = "al" + "low"


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def design(name):
    return next(c for c in F.DESIGN if c[0] == name)


def run_case(name, agent=E.LINKED, oe=None):
    _, records, t, case_oe, _ = design(name)
    return E.run(agent, E.load_memory(records), t, E.Config(case_oe if oe is None else oe))


def all_triggers(name):
    _, records, t, _, _ = design(name)
    m = E.load_memory(records)
    rel = E.relevant_insights(m, t)
    return {i.insight_id: E.triggers(i, rel, m) for i in rel}


def last_ok(m, ins):
    """The last ok action of the insight's linked trajectory (None if none)."""
    summ = next(s for s in m.summaries if s.summary_id == ins.summary_id)
    tr = next(t for t in m.trajectories if t.traj_id == summ.traj_id)
    ok = [s for s in tr.steps if s.result == E.OK]
    return (ok[-1].verb, ok[-1].arg) if ok else None


def summary_of(m, ins):
    return next((s for s in m.summaries if s.summary_id == ins.summary_id), None)


def loaded(name):
    _, records, t, oe, _ = design(name)
    return E.load_memory(records), t, oe


class Fixtures(unittest.TestCase):
    def test_design_and_regression_reports(self):
        lines = []
        fd, nd = F.check_design(out=lines.append)
        fr, nr = F.check_regression(out=lines.append)
        self.assertEqual((fd, fr), (0, 0), "\n".join(lines))
        self.assertEqual((nd, nr), (len(F.DESIGN), len(F.REGRESSION)))

    def test_names_unique(self):
        names = [c[0] for c in F.DESIGN] + [c[0] for c in F.REGRESSION]
        self.assertEqual(len(names), len(set(names)))


class DoneWhenA(unittest.TestCase):
    """(a) the degradation fixture is real: empty memory passes, bare insight fails."""

    def test_a_empty_memory_passes_bare_insight_fails(self):
        for name in ("degradation_failed_lesson", "degradation_missing_outcome"):
            with self.subTest(name=name):
                self.assertTrue(run_case(name, E.EMPTY).passed)
                bare = run_case(name, E.BARE)
                self.assertEqual(bare.status, E.DONE)
                self.assertFalse(bare.passed)
                self.assertIsNotNone(bare.action)
                self.assertTrue(run_case(name).passed)

    def test_a_degradation_present_in_every_regression_world(self):
        for _, seed in F.REGRESSION:
            records, tasks, oe, _ = F.generate(seed)
            res = E.compare(E.load_memory(records), tasks, E.Config(oe))
            deg = [i for i in range(len(tasks)) if res[E.EMPTY][i].passed and not res[E.BARE][i].passed]
            with self.subTest(seed=seed):
                self.assertTrue(deg)
                self.assertTrue(all(res[E.LINKED][i].passed or res[E.LINKED][i].status != E.DONE
                                    or F.generate(seed)[3][tasks[i].task_id][0] == "clean_wrong"
                                    for i in deg))

    def test_a_memory_also_helps(self):
        # Memory is not useless: some tasks fail with no memory and pass with it.
        r = run_case("trigger_missing_detail")
        self.assertTrue(r.passed)
        self.assertFalse(run_case("trigger_missing_detail", E.EMPTY).passed)


class DoneWhenB(unittest.TestCase):
    """(b) each trigger alone forces exactly one descend, then the task passes."""

    def check_alone(self, name, trigger):
        trig = all_triggers(name)
        for iid, t in trig.items():
            self.assertIn(t, ((), (trigger,)), (iid, t))
        self.assertIn((trigger,), trig.values())
        r = run_case(name)
        self.assertEqual((r.status, r.descends, r.passed), (E.DONE, 1, True))
        self.assertFalse(run_case(name, E.BARE).passed)

    def test_b_missing_detail_alone(self):
        self.check_alone("trigger_missing_detail", E.MISSING_DETAIL)

    def test_b_conflict_alone(self):
        self.check_alone("trigger_conflict", E.CONFLICT)

    def test_b_failed_origin_alone(self):
        self.check_alone("trigger_failed_origin", E.FAILED_ORIGIN)

    def test_b_empty_arg_counts_as_missing_detail(self):
        self.assertEqual(all_triggers("empty_arg_is_missing_detail"), {"i1": (E.MISSING_DETAIL,)})
        self.assertEqual(run_case("empty_arg_is_missing_detail").descends, 1)

    def test_b_each_trigger_needs_a_descend_before_acting(self):
        m = E.load_memory(F.lesson("i1", F.WRONG, E.SUCCESS, [(F.WRONG, F.ERR), (F.RIGHT, F.OK)]))
        t = F.task(F.RIGHT, F.OTHER)
        for patch in ({"arg": None}, {"outcome": "failure"}):
            ins = E.Insight("i1", F.KEY, "lift", patch.get("arg", "south"), patch.get("outcome", E.SUCCESS),
                            "s-i1")
            mm = E.Memory((ins,), m.summaries, m.trajectories)
            r = E.run(E.LINKED, mm, t, E.Config(E.HOLD))
            with self.subTest(patch=patch):
                self.assertEqual(r.descends, 1)
                self.assertEqual(r.action, F.RIGHT)


class DoneWhenC(unittest.TestCase):
    """(c) the trajectory wins; a contradicted insight is corrected or rejected, never followed."""

    def test_c_corrected(self):
        r = run_case("success_run_corrects")
        self.assertEqual(dict(r.verdicts), {"i1": E.CORRECTED})
        self.assertEqual(r.action, F.RIGHT)
        self.assertNotEqual(r.action, F.WRONG)

    def test_c_rejected_falls_back_to_no_memory(self):
        for name in ("trajectory_rejects", "success_run_without_ok_step"):
            r = run_case(name)
            with self.subTest(name=name):
                self.assertEqual(dict(r.verdicts), {"i1": E.REJECTED})
                self.assertEqual(r.action, design(name)[2].default)
        m, _, _ = loaded("success_run_without_ok_step")
        self.assertEqual(m.summaries[0].outcome, E.SUCCESS)
        self.assertIsNone(last_ok(m, m.insights[0]))

    def test_c_trajectory_overrides_a_clean_insight(self):
        r = run_case("trajectory_overrides_clean")
        self.assertEqual(all_triggers("trajectory_overrides_clean")["i1"], ())
        self.assertEqual(dict(r.verdicts)["i1"], E.REJECTED)
        self.assertEqual(r.action, F.RIGHT)

    def test_c_latest_ok_step_is_the_evidence(self):
        ins = E.Insight("i1", F.KEY, "lift", None, E.SUCCESS, "s")
        tr = E.Trajectory("t", F.KEY, (E.Step("lift", "west", E.OK), E.Step("lift", "north", E.OK),
                                       E.Step("lift", "up", E.ERROR)))
        self.assertEqual(E.read_trajectory(ins, tr, True), (E.FILLED, ("lift", "north")))

    def test_c_failed_run_gives_no_evidence(self):
        ins = E.Insight("i1", F.KEY, "lift", "south", "failure", "s")
        tr = E.Trajectory("t", F.KEY, (E.Step("lift", "south", E.OK),))
        self.assertEqual(E.read_trajectory(ins, tr, False), (E.REJECTED, None))

    def test_c_failed_run_never_supplies_the_action(self):
        # Every descend into a chain whose run label is not "success" ends rejected.
        worlds = [(E.load_memory(c[1]), (c[2],), c[3]) for c in F.DESIGN]
        for _, seed in F.REGRESSION:
            records, tasks, oe, _ = F.generate(seed)
            worlds.append((E.load_memory(records), tasks, oe))
        n = 0
        for m, tasks, oe in worlds:
            for t in tasks:
                r = E.run(E.LINKED, m, t, E.Config(oe))
                if r.status != E.DONE:
                    continue
                for i in E.relevant_insights(m, t):
                    if E.run_label(i, m) != E.SUCCESS and E.triggers(i, E.relevant_insights(m, t), m):
                        v = dict(r.verdicts)[i.insight_id]
                        if v != E.CONFIRMED:
                            n += 1
                            self.assertEqual(v, E.REJECTED, (t.task_id, i.insight_id))
        self.assertGreater(n, 20)

    def test_c_linked_never_worse_than_no_memory(self):
        # Property over every design case and regression world: where the
        # no-memory agent passes, the linked agent passes too, or stops without
        # acting (or falls back), except the documented clean-but-wrong limit.
        cases = [(c[0], E.load_memory(c[1]), (c[2],), c[3], lambda _t, n=c[0]: n) for c in F.DESIGN]
        for _, seed in F.REGRESSION:
            records, tasks, oe, exp = F.generate(seed)
            cases.append((seed, E.load_memory(records), tasks, oe, lambda t, exp=exp: exp[t.task_id][0]))
        for _, m, tasks, oe, cat in cases:
            for t in tasks:
                e = E.run(E.EMPTY, m, t)
                r = E.run(E.LINKED, m, t, E.Config(oe))
                if e.passed and r.action is not None and not r.passed:
                    self.assertIn(cat(t), ("clean_wrong", "clean_but_wrong_is_a_limit"), t.task_id)

    def test_c_followed_only_when_action_is_the_insights(self):
        for name, records, t, oe, _ in F.DESIGN:
            m = E.load_memory(records)
            r = E.run(E.LINKED, m, t, E.Config(oe))
            byid = {i.insight_id: i for i in m.insights}
            for iid, v in r.verdicts:
                with self.subTest(name=name, iid=iid):
                    if v == E.FOLLOWED:
                        self.assertEqual(E.triggers(byid[iid], E.relevant_insights(m, t), m), ())
                        self.assertEqual(r.action, (byid[iid].verb, byid[iid].arg))
                    if v in (E.CORRECTED, E.REJECTED, E.UNRESOLVED):
                        self.assertNotEqual(r.action, (byid[iid].verb, byid[iid].arg))

    def test_c_descended_insights_never_lead_to_a_wrong_insight_action_regression(self):
        for _, seed in F.REGRESSION:
            records, tasks, oe, _ = F.generate(seed)
            m = E.load_memory(records)
            res = E.compare(m, tasks, E.Config(oe))
            for t, r in zip(tasks, res[E.LINKED]):
                rel = E.relevant_insights(m, t)
                with self.subTest(seed=seed, task=t.task_id):
                    if r.descends and r.action is not None and not r.passed:
                        self.assertEqual(r.action, t.default)
                    for i in rel:
                        if E.triggers(i, rel, m):
                            self.assertNotEqual(dict(r.verdicts).get(i.insight_id), E.FOLLOWED)


class DoneWhenD(unittest.TestCase):
    """(d) a clean insight (outcome success, detail present, no conflict) is used with zero descends."""

    def test_d_clean_insight_zero_descends(self):
        r = run_case("clean_insight")
        self.assertEqual((r.descends, dict(r.verdicts), r.action, r.passed), (0, {"i1": E.FOLLOWED}, F.RIGHT, True))
        self.assertEqual(all_triggers("clean_insight"), {"i1": ()})

    NEAR_MISS = ("Success", "SUCCESS", " success", "", "successful", "success ", "failure", None)

    @staticmethod
    def _mem(ins, label):
        return E.Memory((ins,), (E.Summary("s-i1", "t-i1", label, ""),),
                        (E.Trajectory("t-i1", F.KEY, (E.Step("lift", "north", E.OK),)),))

    def test_d_clean_means_present_fields_only(self):
        for outcome in self.NEAR_MISS:
            ins = E.Insight("i1", F.KEY, "lift", "north", outcome, "s-i1")
            with self.subTest(outcome=outcome):
                self.assertEqual(E.triggers(ins, [ins], self._mem(ins, E.SUCCESS)), (E.FAILED_ORIGIN,))
        for arg in (None, ""):
            ins = E.Insight("i1", F.KEY, "lift", arg, E.SUCCESS, "s-i1")
            with self.subTest(arg=arg):
                self.assertEqual(E.triggers(ins, [ins], self._mem(ins, E.SUCCESS)), (E.MISSING_DETAIL,))

    def test_d_run_label_strict_on_the_summary(self):
        # F1 and F5: the summary's label must be exactly "success" too.
        ins = E.Insight("i1", F.KEY, "lift", "north", E.SUCCESS, "s-i1")
        self.assertEqual(E.triggers(ins, [ins], self._mem(ins, E.SUCCESS)), ())
        for label in self.NEAR_MISS:
            with self.subTest(label=label):
                self.assertEqual(E.triggers(ins, [ins], self._mem(ins, label)), (E.FAILED_ORIGIN,))
        dangling = E.Insight("i1", F.KEY, "lift", "north", E.SUCCESS, "s-other")
        self.assertEqual(E.triggers(dangling, [dangling], self._mem(ins, E.SUCCESS)), (E.FAILED_ORIGIN,))

    def test_d_success_claim_with_failed_run_descends(self):
        for name in ("run_label_failure_beats_claim", "run_label_absent_beats_claim",
                     "run_label_successful_beats_claim", "run_label_trailing_space_beats_claim"):
            r = run_case(name)
            with self.subTest(name=name):
                self.assertEqual(all_triggers(name), {"i1": (E.FAILED_ORIGIN,)})
                self.assertEqual((r.descends, dict(r.verdicts), r.passed), (1, {"i1": E.REJECTED}, True))
                self.assertNotEqual(r.action, F.WRONG)

    def test_d_near_miss_insight_labels_descend(self):
        for name in ("outcome_successful_descends", "outcome_trailing_space_descends",
                     "outcome_wrong_case_descends"):
            r = run_case(name)
            with self.subTest(name=name):
                self.assertEqual(all_triggers(name), {"i1": (E.FAILED_ORIGIN,)})
                self.assertEqual((r.descends, r.passed), (1, True))

    def test_d_clean_but_wrong_is_followed(self):
        # The documented limit: clean is trusted, so a clean wrong insight fails.
        r = run_case("clean_but_wrong_is_a_limit")
        self.assertEqual((r.descends, r.passed), (0, False))


class DoneWhenE(unittest.TestCase):
    """(e) missing outcome is a failed origin; dangling links use on_unresolved; bad declarations are config_error."""

    def test_e_missing_outcome_is_failed_origin(self):
        records = F.lesson("i1", F.RIGHT, F.ABSENT, [(F.RIGHT, F.OK)], run=E.SUCCESS)
        self.assertNotIn("outcome", records["insights"][0])
        m = E.load_memory(records)
        self.assertIsNone(m.insights[0].outcome)
        self.assertEqual(E.triggers(m.insights[0], list(m.insights), m), (E.FAILED_ORIGIN,))
        r = E.run(E.LINKED, m, F.task(F.RIGHT, F.OTHER), E.Config(E.HOLD))
        self.assertEqual((r.descends, dict(r.verdicts)), (1, {"i1": E.CONFIRMED}))
        self.assertEqual(run_case("degradation_missing_outcome").descends, 1)
        # Both labels absent: a failed origin whose run gives no evidence.
        m = E.load_memory(F.lesson("i1", F.RIGHT, F.ABSENT, [(F.RIGHT, F.OK)], run=F.ABSENT))
        self.assertIsNone(m.summaries[0].outcome)
        r = E.run(E.LINKED, m, F.task(F.RIGHT, F.OTHER), E.Config(E.HOLD))
        self.assertEqual((r.descends, dict(r.verdicts), r.action), (1, {"i1": E.REJECTED}, F.OTHER))

    def test_e_every_link_fault_with_every_declaration(self):
        faults = ("no_summary_field", "summary_missing", "no_trajectory_field", "trajectory_missing",
                  "trajectory_unreadable", "trajectory_for_other_key", "trajectory_key_case_differs",
                  "summary_missing_beside_good_chain")
        for name in faults:
            for oe in E.ON_UNRESOLVED:
                r = run_case(name, oe=oe)
                t = design(name)[2]
                with self.subTest(name=name, oe=oe):
                    self.assertEqual(r.status, E.STATUS_ON_UNRESOLVED[oe])
                    self.assertEqual(r.descends, 0)
                    self.assertIn(E.UNRESOLVED, dict(r.verdicts).values())
                    self.assertEqual(r.action, t.default if oe == E.SAFE_FALLBACK else None)
                    self.assertNotEqual(r.status, E.DONE)

    def test_e_clean_insight_with_dangling_link_is_not_used(self):
        # The insight's own fields look clean (claim "success", detail, no
        # conflict); its chain does not resolve, so it is not acted on.
        for name in ("no_summary_field", "summary_missing", "no_trajectory_field"):
            m, _, _ = loaded(name)
            ins = m.insights[0]
            with self.subTest(name=name):
                self.assertEqual((ins.outcome, E.has_detail(ins)), (E.SUCCESS, True))
                self.assertIsNone(run_case(name, oe=E.HOLD).action)
        # With the summary present and labelled "success", no trigger holds at all.
        self.assertEqual(all_triggers("no_trajectory_field"), {"i1": ()})

    def test_e_one_dangling_link_stops_the_task(self):
        r = run_case("one_dangling_among_two")
        self.assertEqual((r.status, r.action), ("denied", None))

    def test_e_dangling_summary_never_lands_on_another_summary(self):
        # F3: another same-key summary is present; the dangling link still
        # resolves only through on_unresolved, under every declaration.
        m, t, _ = loaded("summary_missing_beside_good_chain")
        bad = next(i for i in m.insights if i.insight_id == "i2")
        self.assertIsNone(E.resolve_link(bad, m))
        self.assertIsNone(E.run_label(bad, m))
        for oe in E.ON_UNRESOLVED:
            r = E.run(E.LINKED, m, t, E.Config(oe))
            with self.subTest(oe=oe):
                self.assertEqual((r.status, r.descends, dict(r.verdicts)),
                                 (E.STATUS_ON_UNRESOLVED[oe], 0, {"i2": E.UNRESOLVED}))
                self.assertEqual(r.action, t.default if oe == E.SAFE_FALLBACK else None)

    def test_e_trajectory_key_differing_in_case_does_not_match(self):
        m, t, _ = loaded("trajectory_key_case_differs")
        self.assertIsNone(E.resolve_link(m.insights[0], m))
        for oe in E.ON_UNRESOLVED:
            r = E.run(E.LINKED, m, t, E.Config(oe))
            with self.subTest(oe=oe):
                self.assertEqual((r.status, r.descends), (E.STATUS_ON_UNRESOLVED[oe], 0))
                self.assertNotEqual(r.action, F.WRONG)

    def test_e_insight_key_differing_in_case_is_not_relevant(self):
        m, t, _ = loaded("other_case_key_is_ignored")
        self.assertEqual(E.relevant_insights(m, t), [])

    def test_e_missing_declaration_is_config_error(self):
        _, records, t, _, _ = design("clean_insight")
        m = E.load_memory(records)
        class C2(E.Config):
            pass
        for cfg in (None, E.Config(None), object(), C2(E.HOLD), (E.HOLD,)):
            with self.subTest(cfg=cfg):
                r = E.run(E.LINKED, m, t, cfg)
                self.assertEqual((r.status, r.action, r.passed), (E.CONFIG_ERROR, None, False))

    def test_e_permit_word_is_config_error(self):
        _, records, t, _, _ = design("clean_insight")
        m = E.load_memory(records)
        for word in (PERMIT, PERMIT.upper(), PERMIT.title(), " " + PERMIT, "proceed", "done", "",
                     "Hold", "DENY", 0, True):
            with self.subTest(word=word):
                r = E.run(E.LINKED, m, t, E.Config(word))
                self.assertEqual((r.status, r.action), (E.CONFIG_ERROR, None))

    def test_e_declaration_checked_even_without_memory(self):
        r = E.run(E.LINKED, E.EMPTY_MEMORY, F.task(F.RIGHT, F.RIGHT), E.Config(PERMIT))
        self.assertEqual(r.status, E.CONFIG_ERROR)
        r = E.run(E.LINKED, E.EMPTY_MEMORY, F.task(F.RIGHT, F.RIGHT), E.Config(E.HOLD))
        self.assertEqual((r.status, r.passed), (E.DONE, True))

    def test_e_str_subclass_declaration_rejected(self):
        class S(str):
            pass
        r = E.run(E.LINKED, E.EMPTY_MEMORY, F.task(F.RIGHT, F.RIGHT), E.Config(S("hold")))
        self.assertEqual(r.status, E.CONFIG_ERROR)

    def test_e_status_is_the_modules_own(self):
        r = run_case("summary_missing", oe="".join(["de", "ny"]))
        self.assertIs(r.status, E.STATUS_ON_UNRESOLVED[E.DENY])


class FailClosed(unittest.TestCase):
    def test_malformed_records_load_to_none(self):
        good = F.lesson("i1", F.RIGHT, E.SUCCESS, [(F.RIGHT, F.OK)])
        bad = [
            None, [], {"insights": [], "extra": []},
            {"insights": [{"id": "i1", "key": F.KEY}]},
            {"insights": [{"id": "i1", "key": F.KEY, "verb": "lift", "colour": "red"}]},
            {"insights": [{"id": "i1", "key": F.KEY, "verb": "lift", "outcome": True}]},
            {"insights": [{"id": "i1", "key": F.KEY, "verb": "lift", "arg": 3}]},
            {"summaries": [{"id": 1}]},
            {"trajectories": [{"id": "t", "key": 2, "steps": []}]},
        ]
        self.assertIsNotNone(E.load_memory(good))
        for b in bad:
            with self.subTest(b=b):
                self.assertIsNone(E.load_memory(b))

    def test_unparsable_steps_are_unreadable_not_clean(self):
        for steps in ("x", [["lift", "north"]], [["lift", "north", "maybe"]], [["lift", 1, "ok"]], None):
            m = E.load_memory({"trajectories": [{"id": "t", "key": F.KEY, "steps": steps}]})
            with self.subTest(steps=steps):
                self.assertIsNone(m.trajectories[0].steps)

    def test_bad_memory_or_task_is_config_error(self):
        m = E.load_memory(F.lesson("i1", F.RIGHT, E.SUCCESS, [(F.RIGHT, F.OK)]))
        t = F.task(F.RIGHT, F.OTHER)
        dup = E.Memory(m.insights * 2, m.summaries, m.trajectories)
        list_steps = E.Memory(m.insights, m.summaries,
                              (E.Trajectory("t-i1", F.KEY, list(m.trajectories[0].steps)),))
        class I(E.Insight):
            pass
        sub = E.Memory((I(*[getattr(m.insights[0], f) for f in
                             ("insight_id", "key", "verb", "arg", "outcome", "summary_id")]),),
                       m.summaries, m.trajectories)
        for mem in (None, dup, list_steps, sub, (m.insights, m.summaries, m.trajectories)):
            for agent in (E.BARE, E.LINKED):
                with self.subTest(mem=type(mem).__name__, agent=agent):
                    self.assertEqual(E.run(agent, mem, t, E.Config(E.HOLD)).status, E.CONFIG_ERROR)
        for bad in (None, E.Task("t", F.KEY, ["lift", "north"], F.OTHER), E.Task("t", F.KEY, F.RIGHT, ("", "x")),
                    E.Task("", F.KEY, F.RIGHT, F.OTHER)):
            with self.subTest(task=bad):
                self.assertEqual(E.run(E.LINKED, m, bad, E.Config(E.HOLD)).status, E.CONFIG_ERROR)
        self.assertEqual(E.run("oracle", m, t, E.Config(E.HOLD)).status, E.CONFIG_ERROR)

    def test_bare_agent_has_no_checks(self):
        r = run_case("trajectory_missing", E.BARE)
        self.assertEqual((r.status, r.action, r.descends), (E.DONE, F.WRONG, 0))


class Regression(unittest.TestCase):
    """Regression and property worlds; not independent (same author as the rule)."""

    def test_seeds_fixed_and_deterministic(self):
        self.assertEqual(F.REGRESSION_SEEDS, tuple(range(3001, 3013)))
        self.assertEqual(F.generate(3001), F.generate(3001))

    def test_every_category_and_link_fault_appears(self):
        cats, faults, decls = set(), set(), set()
        for _, seed in F.REGRESSION:
            _, _, oe, exp = F.generate(seed)
            decls.add(oe)
            for c in exp.values():
                cats.add(c[0].split("/")[0])
                if "/" in c[0]:
                    faults.add(c[0].split("/")[1])
        self.assertEqual(cats, set(F.CATEGORIES))
        self.assertEqual(faults, set(F.LINK_FAULTS))
        self.assertEqual(decls, set(E.ON_UNRESOLVED))

    def test_linked_wrong_actions_only_from_clean_wrong(self):
        for _, seed in F.REGRESSION:
            records, tasks, oe, exp = F.generate(seed)
            res = E.compare(E.load_memory(records), tasks, E.Config(oe))
            for t, r in zip(tasks, res[E.LINKED]):
                cat = exp[t.task_id][0]
                wrong = r.action is not None and not r.passed
                ok_wrong = cat == "clean_wrong" or (not exp[t.task_id][1] and (
                    cat in ("failed_origin_rejected", "failed_run_ok_truth", "two_failed", "none",
                            "run_label_mismatch", "failed_run_misleads") or cat.startswith("dangling")))
                with self.subTest(seed=seed, task=t.task_id, cat=cat):
                    if wrong:
                        self.assertTrue(ok_wrong)
                    if wrong and cat != "clean_wrong":
                        # It acted on its own default, never on an insight.
                        self.assertEqual(r.action, t.default)


class WorldShapes(unittest.TestCase):
    """The adversarial fixtures still have their adversarial shape.

    Each test names what a fixture must contain for it to discriminate: if a
    world is edited into an easy one (an honest ok step, a matching label, a
    single lesson, an unrelated key), its expected outcome can still hold, so
    only these checks notice.
    """

    def test_world_run_label_contradicts_the_claim(self):
        labels = set()
        for name in ("run_label_failure_beats_claim", "run_label_absent_beats_claim",
                     "run_label_successful_beats_claim", "run_label_trailing_space_beats_claim"):
            m, t, _ = loaded(name)
            ins = m.insights[0]
            with self.subTest(name=name):
                self.assertEqual(ins.outcome, E.SUCCESS)
                self.assertNotEqual(summary_of(m, ins).outcome, E.SUCCESS)
                self.assertTrue(E.has_detail(ins))
                # Following the claim would act wrong; the failed run's ok step is that wrong action.
                self.assertNotEqual((ins.verb, ins.arg), t.answer)
                self.assertEqual(last_ok(m, ins), (ins.verb, ins.arg))
                self.assertEqual(t.default, t.answer)
            labels.add(summary_of(m, ins).outcome)
        self.assertEqual(labels, {"failure", None, "successful", "success "})

    def test_world_failed_run_ok_step_is_not_the_answer(self):
        for name in ("failed_run_ok_step_is_wrong", "failed_run_ok_step_misleads"):
            m, t, _ = loaded(name)
            ins = m.insights[0]
            with self.subTest(name=name):
                self.assertNotEqual(summary_of(m, ins).outcome, E.SUCCESS)
                ev = last_ok(m, ins)
                self.assertIsNotNone(ev)
                self.assertNotEqual(ev, t.answer)
                self.assertEqual(t.default, t.answer)
                self.assertTrue(run_case(name, E.EMPTY).passed)
        m, _, _ = loaded("failed_run_ok_step_misleads")
        self.assertNotEqual(last_ok(m, m.insights[0]), (m.insights[0].verb, m.insights[0].arg))

    def test_world_failed_lesson_sorts_first(self):
        m, t, _ = loaded("failed_lesson_sorts_first")
        first, second = E.relevant_insights(m, t)
        self.assertNotEqual(summary_of(m, first).outcome, E.SUCCESS)
        self.assertEqual(summary_of(m, second).outcome, E.SUCCESS)
        self.assertNotEqual(last_ok(m, first), t.answer)
        self.assertIsNotNone(last_ok(m, first))
        self.assertEqual(last_ok(m, second), t.answer)
        self.assertEqual((second.verb, second.arg), t.answer)
        self.assertIn(E.CONFLICT, E.triggers(first, [first, second], m))
        self.assertNotEqual(t.default, t.answer)

    def test_world_dangling_summary_beside_a_good_chain(self):
        m, t, _ = loaded("summary_missing_beside_good_chain")
        rel = E.relevant_insights(m, t)
        dangling = [i for i in rel if type(i.summary_id) is str and summary_of(m, i) is None]
        good = [i for i in rel if E.resolve_link(i, m) is not None]
        self.assertEqual(len(dangling), 1)
        self.assertTrue(good)
        self.assertEqual(len(m.summaries), 1)
        # Any summary it might land on resolves to a same-key trajectory.
        tr = next(x for x in m.trajectories if x.traj_id == m.summaries[0].traj_id)
        self.assertEqual(tr.key, t.key)
        self.assertEqual(E.triggers(dangling[0], rel, m)[:1], (E.CONFLICT,))

    def test_world_trajectory_key_differs_only_in_case(self):
        m, t, _ = loaded("trajectory_key_case_differs")
        ins = m.insights[0]
        tr = m.trajectories[0]
        self.assertNotEqual(tr.key, t.key)
        self.assertEqual(tr.key.lower(), t.key.lower())
        self.assertEqual(ins.key, t.key)
        self.assertEqual(summary_of(m, ins).outcome, E.SUCCESS)
        self.assertNotEqual((ins.verb, ins.arg), t.answer)
        m2, t2, _ = loaded("other_case_key_is_ignored")
        self.assertNotEqual(m2.insights[0].key, t2.key)
        self.assertEqual(m2.insights[0].key.lower(), t2.key.lower())

    def test_world_verb_conflict_without_detail(self):
        m, t, _ = loaded("verb_conflict_without_detail")
        a, b = E.relevant_insights(m, t)
        self.assertNotEqual(a.verb, b.verb)
        self.assertTrue(E.has_detail(a))
        self.assertFalse(E.has_detail(b))
        self.assertNotEqual((a.verb, a.arg), t.answer)
        self.assertEqual(summary_of(m, a).outcome, E.SUCCESS)
        self.assertEqual(last_ok(m, b), None)
        self.assertEqual(last_ok(m, a), t.answer)

    def test_world_near_miss_labels_present(self):
        claims = {loaded(n)[0].insights[0].outcome for n in
                  ("outcome_successful_descends", "outcome_trailing_space_descends", "outcome_wrong_case_descends")}
        self.assertEqual(claims, {"successful", "success ", "Success"})
        self.assertTrue({"successful", "success "} <= set(F.NEAR_MISS))
        self.assertNotIn(E.SUCCESS, F.NEAR_MISS)

    def test_world_regression_categories_hold_their_shape(self):
        seen = set()
        for _, seed in F.REGRESSION:
            records, tasks, _, exp = F.generate(seed)
            m = E.load_memory(records)
            for t in tasks:
                cat = exp[t.task_id][0]
                rel = E.relevant_insights(m, t)
                with self.subTest(seed=seed, task=t.task_id, cat=cat):
                    if cat == "run_label_mismatch":
                        i, = rel
                        self.assertEqual(i.outcome, E.SUCCESS)
                        self.assertNotEqual(summary_of(m, i).outcome, E.SUCCESS)
                        self.assertNotEqual((i.verb, i.arg), t.answer)
                    elif cat == "failed_run_misleads":
                        i, = rel
                        self.assertNotEqual(summary_of(m, i).outcome, E.SUCCESS)
                        self.assertNotIn(last_ok(m, i), (None, t.answer))
                    elif cat == "failed_sorts_first":
                        first, second = rel
                        self.assertNotEqual(summary_of(m, first).outcome, E.SUCCESS)
                        self.assertNotIn(last_ok(m, first), (None, t.answer))
                        self.assertEqual(summary_of(m, second).outcome, E.SUCCESS)
                        self.assertEqual(last_ok(m, second), t.answer)
                    elif cat == "verb_conflict_no_detail":
                        first, second = rel
                        self.assertNotEqual(first.verb, second.verb)
                        self.assertFalse(E.has_detail(second))
                        self.assertNotEqual((first.verb, first.arg), t.answer)
                    elif cat == "dangling_beside_good":
                        self.assertEqual(len(rel), 2)
                        # One summary link points at an id with no record (not an absent field).
                        self.assertEqual(sum(type(i.summary_id) is str and summary_of(m, i) is None
                                             for i in rel), 1)
                        self.assertEqual(sum(E.resolve_link(i, m) is not None for i in rel), 1)
                    elif cat == "dangling/key_case":
                        i, = rel
                        summ = summary_of(m, i)
                        tr = next(x for x in m.trajectories if x.traj_id == summ.traj_id)
                        self.assertNotEqual(tr.key, t.key)
                        self.assertEqual(tr.key.lower(), t.key.lower())
                seen.add(cat)
        for cat in ("run_label_mismatch", "failed_run_misleads", "failed_sorts_first",
                    "verb_conflict_no_detail", "dangling_beside_good", "dangling/key_case"):
            self.assertIn(cat, seen)


class DoneWhenF(unittest.TestCase):
    """(f) hygiene: no network, model, Docker or OpenRouter pieces; paper figures stay UNVERIFIED."""

    BANNED_IMPORT_WORDS = ("socket", "urllib", "http", "requests", "subprocess", "docker", "openrouter",
                           "openai", "anthropic", "sqlite", "hmac", "hashlib", "thread", "asyncio",
                           "multiprocessing", "ctypes", "pickle")
    # sha256 of each banned word, lower case, mapped to its length. The words
    # themselves never appear in this directory. Every substring of every
    # [a-z]+ token of the lower-cased text is compared at these lengths, so a
    # banned word is found in any case and inside longer words.
    BANNED_DIGESTS = {
        "6ca7ea2feefc88ecb5ed6356ed963f47dc9137f82526fdd25d618ea626d0803f": 4,
        "36c1852b63947092f69e46964f3a7400e49d5749741af087f444f458e72b27c9": 10,
        "6627835f988e2c5e50533d491163072d3f4f41f5c8b04630150debb3722ca2dd": 5,
        "d2d2328e3359f3de3515871090d1316cbcdc5383204c204f9390788c3ef8618f": 7,
    }

    @staticmethod
    def _hits(text, digests):
        found = []
        for tok in re.findall(r"[a-z]+", text.lower()):
            for n in set(digests.values()):
                for i in range(len(tok) - n + 1):
                    if digests.get(hashlib.sha256(tok[i:i + n].encode()).hexdigest()) == n:
                        found.append(tok)
        return found

    def test_f_stdlib_imports_only(self):
        permitted = {"dataclasses", "typing", "random", "sys", "evidence_memory"}
        for name in CODE:
            src = read(name)
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [node.module.split(".")[0]]
                else:
                    continue
                for mod in mods:
                    self.assertIn(mod, permitted, (name, mod))
            for word in self.BANNED_IMPORT_WORDS:
                self.assertNotIn(word, src.lower(), (name, word))
            for call in ("eval(", "exec(", "open(", "__import__"):
                self.assertNotIn(call, src, (name, call))

    def test_f_mutants_script_imports(self):
        permitted = {"os", "shutil", "subprocess", "sys", "tempfile"}
        for node in ast.walk(ast.parse(read("mutants.py"))):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module]
                for mod in mods:
                    self.assertIn(mod.split(".")[0], permitted, mod)

    def test_f_paper_figures_only_in_evidence_and_unverified(self):
        ev = json.loads(read("paper_evidence.json"))
        claims = ev["empirical_claims"]["claims"]
        self.assertEqual(ev["empirical_claims"]["status"], "UNVERIFIED")
        self.assertTrue(claims and all(c["status"] == "UNVERIFIED" for c in claims))
        self.assertEqual(ev["upstream_code"]["status"], "UNVERIFIED")
        tokens = [c["token"] for c in claims]
        w5, w8 = "fi" + "ve", "ei" + "ght"
        self.assertIn(w5 + " agentic benchmarks", tokens)
        pats = [re.escape(t) for t in tokens] + [r"\b" + w5 + r"\b", r"\b" + w8 + r"\b",
                                                   "8" + r"\.5", "4" + r"\.5", w5 + r"\s+benchmarks"]
        for name in ALL:
            if name == "paper_evidence.json":
                continue
            text = read(name)
            for p in pats:
                self.assertIsNone(re.search(p, text, re.I), (name, p))

    def test_f_banned_words_and_permit_word(self):
        for name in ALL:
            text = read(name)
            with self.subTest(name=name):
                self.assertEqual(self._hits(text, self.BANNED_DIGESTS), [])
                self.assertNotIn(PERMIT, text.lower())

    def test_f_digest_scan_works(self):
        # The scanner itself, checked with a harmless word's digest: found in
        # any case and inside a longer token, not found when absent.
        probe = {hashlib.sha256(b"gate").hexdigest(): 4}
        self.assertEqual(self._hits("the GATEway", probe), ["gateway"])
        self.assertEqual(self._hits("Gate", probe), ["gate"])
        self.assertEqual(self._hits("a g-ate", probe), [])
        self.assertEqual(len(self.BANNED_DIGESTS), 4)
        self.assertEqual(sorted(self.BANNED_DIGESTS.values()), [4, 5, 7, 10])

    def test_f_no_box_paths(self):
        # The lab copies are found only through $W20ELM_SOURCES; no box path is written here.
        box = "/" + "work" + "space"
        for name in ALL:
            self.assertNotIn(box, read(name), name)

    def test_f_readme_status_soft_and_regression_wording(self):
        readme = read("README.md")
        self.assertIn("Status: Soft", readme)
        self.assertNotIn("Top", readme)
        self.assertIn("not Team OS law and not village law", readme)
        for name in ALL:
            text = read(name).lower()
            self.assertIsNone(re.search(r"held[-_ ]?out", text), name)

    def test_f_no_conflict_markers(self):
        for name in ALL:
            for line in read(name).splitlines():
                self.assertFalse(line.startswith(("<" * 7, ">" * 7, "=" * 7 + " ")) or line == "=" * 7, name)

    def test_f_no_day_index_in_this_folder(self):
        self.assertFalse(os.path.exists(os.path.join(HERE, "day-README.md")))

    def test_f_notice_and_readme_credit(self):
        notice, readme = read("NOTICE"), read("README.md")
        for t in (notice, readme):
            for s in ("2611.14320", "https://arxiv.org/abs/2611.14320", "CC BY 4.0", "Apache",
                      "9ee357fbb95db9caae09808f3472a9fce6409c90"):
                self.assertIn(s, t)
        for s in ("w15-tooling-memory", "w17-memory-scope", "51-fael-memory-pointers", "#111",
                  "https://cursor.com/codebase/coevolution-lab/playground/pull/111"):
            self.assertIn(s, readme)
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["paper"]["licence"], "CC BY 4.0")
        self.assertIn("METHOD ONLY", ev["paper"]["use"])
        self.assertIn("METHOD ONLY", ev["upstream_code"]["use"])

    def _source(self, name):
        if not SOURCES:
            self.skipTest("W20ELM_SOURCES not set")
        ev = json.loads(read("paper_evidence.json"))
        src = next(s for s in ev["sources"] if s["name"] == name)
        path = os.path.join(SOURCES, src["file"])
        self.assertTrue(os.path.isfile(path), "W20ELM_SOURCES is set but has no " + src["file"])
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if name == "abstract":
            text = text[len("Abstract:"):].rstrip("\n")
        self.assertEqual(len(text), src["chars"])
        return text

    def test_f_offsets_match_sources(self):
        ev = json.loads(read("paper_evidence.json"))
        for c in ev["empirical_claims"]["claims"]:
            text = self._source(c["source"])
            self.assertEqual(text[c["offset"]:c["offset"] + len(c["token"])], c["token"], c["id"])

    def test_f_no_six_word_run_copied(self):
        def runs(text):
            w = re.findall(r"[a-z0-9']+", text.lower())
            return {" ".join(w[i:i + 6]) for i in range(len(w) - 5)}
        ev = json.loads(read("paper_evidence.json"))
        theirs = runs(self._source("abstract")) | runs(self._source("upstream_readme_head"))
        # The title and the abs URL are cited on purpose (attribution).
        theirs -= runs(ev["paper"]["title"]) | runs(ev["paper"]["abs_url"])
        for name in DOCS + CODE + ("test_evidence_memory.py", "mutants.py"):
            with self.subTest(name=name):
                self.assertEqual(theirs & runs(read(name)), set())


if __name__ == "__main__":
    unittest.main()
