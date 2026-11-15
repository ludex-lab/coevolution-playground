"""Tests for the w20-plan-change-notice method sketch (stdlib unittest).

Run: python3 -m unittest test_plan_change.py -v
The source check reads the abs-page copy named in paper_evidence.json from
$W20PCN_SOURCES (default: the morning-brief raw folder) and is skipped when
it is absent.
"""

import ast
import html
import json
import os
import random
import re
import unittest

import plan_change as P
import fixtures as F

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W20PCN_SOURCES", "/workspace/morning-brief-2026-11-11/raw")
CODE = ("plan_change.py", "fixtures.py")
DOCS = ("README.md", "NOTICE")
DAY_INDEX = os.path.join(HERE, "..", "README.md")
N, C = P.Notice, P.Change


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def both(world, config=None):
    config = config if config is not None else F.cfg()
    return P.run(world, P.BASELINE), P.run(world, P.NOTICE_FIRST, config)


def design(name):
    return next(c for c in F.DESIGN if c[0] == name)


class Fixtures(unittest.TestCase):
    def test_design_and_held_out_reports(self):
        lines = []
        fd, nd = F.check_design(out=lines.append)
        fh, nh = F.check_held_out(out=lines.append)
        self.assertEqual((fd, fh), (0, 0), "\n".join(lines))
        self.assertEqual((nd, nh), (len(F.DESIGN), len(F.HELD_OUT)))

    def test_names_unique(self):
        names = [c[0] for c in F.DESIGN] + [c[0] for c in F.HELD_OUT]
        self.assertEqual(len(names), len(set(names)))


class DoneWhenA(unittest.TestCase):
    """(a) the baseline acks the notice and still executes obsolete work."""

    def test_baseline_acks_then_acts_on_the_cached_plan(self):
        b = P.run(F.BASE, P.BASELINE)
        self.assertEqual([(k.at, k.notice_id, k.classification) for k in b.acks],
                         [(20, "n2", P.VALID)])
        self.assertEqual(P.final_targets(b), F.NORTH)
        self.assertEqual([a.plan_version for a in b.actions], [1, 1, 1])
        found = P.detect_obsolete(F.BASE, b)
        self.assertEqual([(f[1], f[2], f[3], f[4]) for f in found],
                         [(20, P.OBSOLETE_AFTER_ACK, 1, 2), (30, P.OBSOLETE_AFTER_ACK, 1, 2)])
        # Every obsolete step came after the ack.
        ack_t = b.acks[0].at
        self.assertTrue(all(f[1] >= ack_t for f in found))

    def test_obsolete_after_ack_on_every_design_case_with_a_delivered_valid_notice(self):
        for name, w, c, exp in F.DESIGN:
            b = P.run(w, P.BASELINE)
            valid = [k for k in b.acks if k.classification == P.VALID]
            found = P.detect_obsolete(w, b)
            with self.subTest(name):
                if valid and any(a.at >= valid[0].at for a in b.actions if a.kind == P.CONSEQUENTIAL):
                    self.assertTrue(any(f[2] == P.OBSOLETE_AFTER_ACK for f in found))

    def test_uninformed_vs_after_ack(self):
        w = design("notice_arrives_during_wait")[1]
        found = P.detect_obsolete(w, P.run(w, P.BASELINE))
        self.assertEqual([(f[1], f[2]) for f in found],
                         [(20, P.OBSOLETE_UNINFORMED), (30, P.OBSOLETE_AFTER_ACK)])


class DoneWhenB(unittest.TestCase):
    """(b) the guard acts on the revised objective on held-out worlds."""

    def test_held_out_seeds_are_separate_and_deterministic(self):
        self.assertEqual(len(set(F.HELD_OUT_SEEDS)), len(F.HELD_OUT))
        design_worlds = {repr(w) for _, w, _, _ in F.DESIGN}
        for s in F.HELD_OUT_SEEDS:
            w1, c1 = F.generate(s)
            w2, c2 = F.generate(s)
            self.assertEqual((w1, c1), (w2, c2))
            self.assertNotIn(repr(w1), design_worlds)
        self.assertEqual(len({repr(F.generate(s)[0]) for s in F.HELD_OUT_SEEDS}), len(F.HELD_OUT))

    def test_guard_follows_the_authority_on_every_held_out_world(self):
        for name, w, c in F.HELD_OUT:
            g = P.run(w, P.NOTICE_FIRST, c)
            with self.subTest(name):
                self.assertEqual(g.status, P.DONE)
                self.assertEqual(P.detect_obsolete(w, g), ())
                hist = [(x.version, x.targets, x.issued_at) for x in w.changes]
                for a in g.actions:
                    if a.kind == P.CONSEQUENTIAL:
                        v, targets = P.authoritative_at(hist, a.at)
                        self.assertEqual((a.plan_version, a.target), (v, targets[a.index]))
                last = [a for a in g.actions if a.kind == P.CONSEQUENTIAL][-1]
                self.assertEqual(last.plan_version, w.changes[-1].version)

    def test_baseline_goes_obsolete_on_every_held_out_world(self):
        for name, w, c in F.HELD_OUT:
            with self.subTest(name):
                self.assertGreaterEqual(len(P.detect_obsolete(w, P.run(w, P.BASELINE))), 1)

    def test_held_out_worlds_exercise_the_hard_parts(self):
        kinds = set()
        for _, w, c in F.HELD_OUT:
            for k in P.run(w, P.NOTICE_FIRST, c).acks:
                kinds.add(k.classification)
            if any(a.kind == P.WAIT for a in P.run(w, P.NOTICE_FIRST, c).actions):
                kinds.add("waited")
        self.assertTrue({P.VALID, P.DUPLICATE, P.FOREIGN, "waited"} <= kinds, kinds)


class Detector(unittest.TestCase):
    def test_version_bump_with_same_targets_is_still_obsolete(self):
        # A new version can change constraints without changing targets;
        # acting on the superseded version is still flagged.
        w = P.World(F.OID, (F.V1, C(2, F.NORTH, 15)), (N("n2", F.OID, 2, F.NORTH, 15),), F.TURNS)
        found = P.detect_obsolete(w, P.run(w, P.BASELINE))
        self.assertEqual([(f[1], f[3], f[4]) for f in found], [(20, 1, 2), (30, 1, 2)])
        self.assertEqual(P.detect_obsolete(w, P.run(w, P.NOTICE_FIRST, F.cfg())), ())

    def test_same_version_wrong_target_is_obsolete(self):
        bad = P.Trace(P.BASELINE, P.DONE, (P.Action(10, P.CONSEQUENTIAL, 0, 1, "build:north"),), ())
        self.assertEqual(len(P.detect_obsolete(F.BASE, bad)), 1)

    def test_summary_counts_only_consequential_steps(self):
        w = design("notice_late_timeout_safe_fallback")[1]
        g = P.run(w, P.NOTICE_FIRST, F.cfg(P.SAFE_FALLBACK))
        self.assertEqual(P.summary(g), {"notices_acked": 0, "steps_completed": 1, "status": "fallback"})


class DoneWhenC(unittest.TestCase):
    """(c) summaries cannot tell the traces apart; the detector can."""

    SAME = ("change_mid_step", "notice_at_turn_boundary", "out_of_order_notices",
            "older_notice_cannot_roll_back", "duplicate_notice")

    def test_summaries_identical_detector_differs(self):
        for name in self.SAME:
            _, w, c, _ = design(name)
            b, g = both(w, c)
            with self.subTest(name):
                self.assertEqual(P.summary(b), P.summary(g))
                self.assertEqual(P.summary(b)["status"], P.DONE)
                self.assertGreater(P.summary(b)["notices_acked"], 0)
                self.assertGreater(len(P.detect_obsolete(w, b)), 0)
                self.assertEqual(P.detect_obsolete(w, g), ())
                self.assertNotEqual(P.final_targets(b), P.final_targets(g))

    def test_summary_carries_no_objective_information(self):
        self.assertEqual(set(P.summary(P.run(F.BASE, P.BASELINE))),
                         {"notices_acked", "steps_completed", "status"})

    def test_detector_reads_only_world_and_trace(self):
        b = P.run(F.BASE, P.BASELINE)
        relabelled = P.Trace("anything", b.status, b.actions, b.acks)
        self.assertEqual(P.detect_obsolete(F.BASE, relabelled), P.detect_obsolete(F.BASE, b))


class SilenceDoctrine(unittest.TestCase):
    def test_guard_requires_a_declared_on_expiry(self):
        for bad in (None, "", "DENY", "deny ", "proceed", "continue", "pass", 0, True):
            for w in (F.BASE, design("empty_inbox_no_change")[1]):
                with self.subTest(on_expiry=bad):
                    t = P.run(w, P.NOTICE_FIRST, P.GuardConfig(1, bad))
                    self.assertEqual((t.status, t.actions), (P.CONFIG_ERROR, ()))
                    self.assertIn("on_expiry", t.errors)
        for missing in (None, P.GuardConfig(1)):
            self.assertEqual(P.run(F.BASE, P.NOTICE_FIRST, missing).status, P.CONFIG_ERROR)

    def test_timeout_resolves_only_to_the_declared_value(self):
        w = design("notice_late_timeout_hold")[1]
        for oe in P.ON_EXPIRY:
            g = P.run(w, P.NOTICE_FIRST, F.cfg(oe))
            with self.subTest(oe=oe):
                self.assertEqual(g.status, P.STATUS_ON_EXPIRY[oe])
                kinds = [a.kind for a in g.actions]
                self.assertEqual(kinds[:2], [P.CONSEQUENTIAL, P.WAIT])
                self.assertEqual(kinds[2:], [P.FALLBACK_STEP] if oe == P.SAFE_FALLBACK else [])
                self.assertEqual(P.detect_obsolete(w, g), ())
                # Nothing of the new objective was done without its notice.
                self.assertFalse(set(P.final_targets(g)) & set(F.SOUTH))

    def test_no_notice_is_not_consent(self):
        # Authority changed, nothing in the inbox: no stale step, no silent replan.
        w = design("empty_inbox_silent_change")[1]
        for oe in P.ON_EXPIRY:
            g = P.run(w, P.NOTICE_FIRST, F.cfg(oe, 3))
            self.assertEqual(P.final_targets(g), ("survey:north",))
            self.assertNotEqual(g.status, P.DONE)

    def test_pending_notice_is_not_used_before_delivery(self):
        w = design("notice_arrives_during_wait")[1]
        g = P.run(w, P.NOTICE_FIRST, F.cfg(P.HOLD, 2))
        self.assertEqual([(a.at, a.kind) for a in g.actions][:2],
                         [(10, P.CONSEQUENTIAL), (20, P.WAIT)])
        self.assertEqual([k.at for k in g.acks], [30])
        self.assertEqual(g.actions[2].plan_version, 2)

    def test_each_gap_gets_its_own_wait(self):
        w = P.World(F.OID, (F.V1, C(2, F.SOUTH, 15), C(3, F.EAST, 35)),
                    (N("n2", F.OID, 2, F.SOUTH, 25), N("n3", F.OID, 3, F.EAST, 45)),
                    (10, 20, 30, 40, 50))
        g = P.run(w, P.NOTICE_FIRST, F.cfg(P.HOLD, 1))
        self.assertEqual(g.status, P.DONE)
        self.assertEqual([(a.at, a.kind, a.plan_version) for a in g.actions],
                         [(10, P.CONSEQUENTIAL, 1), (20, P.WAIT, 1), (30, P.CONSEQUENTIAL, 2),
                          (40, P.WAIT, 2), (50, P.CONSEQUENTIAL, 3)])
        self.assertEqual(P.detect_obsolete(w, g), ())

    def test_older_valid_notice_does_not_license_a_newer_version(self):
        # v2 notice handled, v3 in force with no v3 notice: wait, then
        # on_expiry; never a replan to v3.
        w = P.World(F.OID, (F.V1, C(2, F.SOUTH, 12), C(3, F.EAST, 18)),
                    (N("n2", F.OID, 2, F.SOUTH, 13),), (10, 20, 30, 40))
        for oe in P.ON_EXPIRY:
            g = P.run(w, P.NOTICE_FIRST, F.cfg(oe, 1))
            with self.subTest(oe=oe):
                self.assertEqual(g.status, P.STATUS_ON_EXPIRY[oe])
                self.assertEqual([(a.at, a.kind, a.plan_version) for a in g.actions][:2],
                                 [(10, P.CONSEQUENTIAL, 1), (20, P.WAIT, 1)])
                self.assertFalse(any(a.plan_version == 3 for a in g.actions))
                self.assertEqual([(k.notice_id, k.classification) for k in g.acks], [("n2", P.VALID)])

    def test_status_vocabulary_has_no_proceed_on_timeout(self):
        self.assertEqual(set(P.STATUS_ON_EXPIRY), set(P.ON_EXPIRY))
        self.assertNotIn(P.DONE, P.STATUS_ON_EXPIRY.values())

    def test_expiry_value_is_the_module_constant(self):
        fresh = "".join(["ho", "ld"])
        errs, snap = P.check_config(P.GuardConfig(1, fresh))
        self.assertEqual(errs, ())
        self.assertIs(snap[1], P.HOLD)

    def test_guard_never_acts_on_a_stale_plan_random_worlds(self):
        rng = random.Random(77)
        for seed in range(400):
            w, c = F.generate(rng.randrange(10 ** 6, 10 ** 7))
            # Drop, delay or corrupt notices at random.
            ns = []
            for n in w.notices:
                r = rng.random()
                if r < 0.2:
                    continue
                if r < 0.3:
                    n = N(n.notice_id, n.objective_id, n.version, n.targets[::-1], n.arrives_at)
                if r < 0.4:
                    n = N(n.notice_id, n.objective_id, n.version, n.targets, n.arrives_at + 50)
                ns.append(n)
            w2 = P.World(w.objective_id, w.changes, tuple(ns), w.turns)
            g = P.run(w2, P.NOTICE_FIRST, P.GuardConfig(rng.randrange(0, 3), rng.choice(P.ON_EXPIRY)))
            self.assertIn(g.status, (P.DONE, P.INCOMPLETE) + tuple(P.STATUS_ON_EXPIRY.values()))
            self.assertEqual(P.detect_obsolete(w2, g), (), seed)


class Adversarial(unittest.TestCase):
    def acks(self, name):
        _, w, c, _ = design(name)
        return [(k.notice_id, k.version, k.classification) for k in P.run(w, P.NOTICE_FIRST, c).acks]

    def test_mid_step_change_does_not_taint_the_step_already_taken(self):
        g = P.run(F.BASE, P.NOTICE_FIRST, F.cfg())
        self.assertEqual(g.actions[0].plan_version, 1)
        self.assertEqual(P.detect_obsolete(F.BASE, g), ())

    def test_out_of_order_and_no_roll_back(self):
        self.assertEqual(self.acks("out_of_order_notices"),
                         [("n3", 3, P.VALID), ("n2", 2, P.STALE)])
        self.assertEqual(self.acks("older_notice_cannot_roll_back"),
                         [("n2", 2, P.VALID), ("n1-late", 1, P.STALE)])
        _, w, c, _ = design("older_notice_cannot_roll_back")
        self.assertEqual(P.final_targets(P.run(w, P.NOTICE_FIRST, c))[1:], F.SOUTH[1:])

    def test_foreign_duplicate_misleading_ahead(self):
        self.assertEqual(self.acks("foreign_objective_notice_only"), [("x2", 2, P.FOREIGN)])
        self.assertEqual(self.acks("duplicate_notice"), [("n2", 2, P.VALID), ("n2", 2, P.DUPLICATE)])
        self.assertEqual(self.acks("misleading_notice_content"), [("n2", 2, P.MISMATCH)])
        self.assertEqual(self.acks("notice_ahead_of_authority"), [("n2", 2, P.AHEAD)])

    def test_ahead_notice_is_not_reused_when_authority_catches_up(self):
        w = P.World(F.OID, (F.V1, C(2, F.SOUTH, 22)), (N("n2", F.OID, 2, F.SOUTH, 15),),
                    (10, 20, 30, 40))
        g = P.run(w, P.NOTICE_FIRST, F.cfg(P.DENY))
        self.assertEqual(g.status, "denied")
        self.assertEqual(P.detect_obsolete(w, g), ())

    def test_second_id_for_the_known_version_is_stale(self):
        w = P.World(F.OID, (F.V1, C(2, F.SOUTH, 15)),
                    (N("n2", F.OID, 2, F.SOUTH, 15), N("n2b", F.OID, 2, F.SOUTH, 18)), F.TURNS)
        g = P.run(w, P.NOTICE_FIRST, F.cfg())
        self.assertEqual([(k.notice_id, k.classification) for k in g.acks],
                         [("n2", P.VALID), ("n2b", P.STALE)])
        self.assertEqual(g.status, P.DONE)

    def test_id_reuse_locks_out_the_genuine_notice(self):
        # Documented liveness limit L2: an early (ahead) copy marks the id as
        # seen, so the genuine notice is a duplicate and the run ends on_expiry.
        w = P.World(F.OID, (F.V1, C(2, F.SOUTH, 25)),
                    (N("n2", F.OID, 2, F.SOUTH, 10), N("n2", F.OID, 2, F.SOUTH, 26)), (10, 20, 30, 40, 50))
        g = P.run(w, P.NOTICE_FIRST, F.cfg(P.HOLD, 1))
        self.assertEqual(g.status, "held")
        self.assertEqual([(k.notice_id, k.classification) for k in g.acks],
                         [("n2", P.AHEAD), ("n2", P.DUPLICATE)])
        self.assertEqual([(a.at, a.kind, a.plan_version) for a in g.actions],
                         [(10, P.CONSEQUENTIAL, 1), (20, P.CONSEQUENTIAL, 1), (30, P.WAIT, 1)])
        self.assertEqual(P.detect_obsolete(w, g), ())

    def test_inbox_is_delivered_in_arrival_order_not_list_order(self):
        w = P.World(F.OID, (F.V1, C(2, F.SOUTH, 15)),
                    (N("x", "orchard", 2, F.SOUTH, 45), N("n2", F.OID, 2, F.SOUTH, 16)), (10, 20, 30, 40, 50))
        g = P.run(w, P.NOTICE_FIRST, F.cfg(P.HOLD, 1))
        self.assertEqual(g.status, P.DONE)
        self.assertEqual([(k.at, k.notice_id) for k in g.acks], [(20, "n2")])
        self.assertEqual([(a.at, a.plan_version) for a in g.actions], [(10, 1), (20, 2), (30, 2)])

    def test_back_to_back_changes_can_exhaust_the_wait(self):
        # Documented liveness limit L1: the wait counter is reset only on a
        # replan, not on a newer valid notice, so two quick changes can use
        # up the wait even though every notice arrives.
        w = P.World(F.OID, (F.V1, C(2, F.SOUTH, 15), C(3, F.EAST, 25)),
                    (N("n2", F.OID, 2, F.SOUTH, 21), N("n3", F.OID, 3, F.EAST, 41)),
                    (10, 20, 30, 40, 50, 60))
        g = P.run(w, P.NOTICE_FIRST, F.cfg(P.DENY, 2))
        self.assertEqual(g.status, "denied")
        self.assertEqual([(a.at, a.kind) for a in g.actions],
                         [(10, P.CONSEQUENTIAL), (20, P.WAIT), (30, P.WAIT)])
        self.assertEqual(P.detect_obsolete(w, g), ())

    def test_empty_inbox(self):
        b, g = both(design("empty_inbox_no_change")[1])
        self.assertEqual((b.acks, g.acks), ((), ()))
        self.assertEqual(P.final_targets(b), P.final_targets(g))


class FailClosed(unittest.TestCase):
    def bad(self, world, config="default", policy=P.NOTICE_FIRST):
        t = P.run(world, policy, F.cfg() if config == "default" else config)
        self.assertEqual((t.status, t.actions, t.acks), (P.CONFIG_ERROR, (), ()))
        return t.errors

    def test_subclasses_fail_closed(self):
        class W2(P.World):
            pass

        class N2(P.Notice):
            pass

        class C2(P.Change):
            pass

        class G2(P.GuardConfig):
            pass

        class S(str):
            def __eq__(self, other):
                return True

            __hash__ = str.__hash__

        w = F.BASE
        self.assertEqual(self.bad(W2(w.objective_id, w.changes, w.notices, w.turns)), ("not_a_world",))
        self.assertIn("notice_type", self.bad(P.World(F.OID, w.changes, (N2("n", F.OID, 2, F.SOUTH, 15),),
                                                        F.TURNS)))
        self.assertIn("change_type", self.bad(P.World(F.OID, (F.V1, C2(2, F.SOUTH, 15)), (), F.TURNS)))
        self.assertIn("not_a_config", self.bad(w, G2(1, P.HOLD)))
        self.assertIn("on_expiry", self.bad(w, P.GuardConfig(1, S("hold"))))
        self.assertIn("objective_id", self.bad(P.World(S(F.OID), w.changes, (), F.TURNS)))

    def test_bad_times_and_fields(self):
        V1 = F.V1
        cases = [
            P.World(F.OID, (C(1, F.NORTH, 0.0),), (), F.TURNS),
            P.World(F.OID, (C(1, F.NORTH, True),), (), F.TURNS),
            P.World(F.OID, (C(1, F.NORTH, float("nan")),), (), F.TURNS),
            P.World(F.OID, (V1,), (), (10, 20.0, 30)),
            P.World(F.OID, (V1,), (), (10, 10, 30)),
            P.World(F.OID, (V1,), (), (30, 20)),
            P.World(F.OID, (V1,), (), ()),
            P.World(F.OID, (V1,), (), [10, 20]),
            P.World(F.OID, [V1], (), F.TURNS),
            P.World(F.OID, (), (), F.TURNS),
            P.World("", (V1,), (), F.TURNS),
            P.World(F.OID, (C(2, F.NORTH, 0),), (), F.TURNS),
            P.World(F.OID, (V1, C(1, F.SOUTH, 5)), (), F.TURNS),
            P.World(F.OID, (V1, C(2, F.SOUTH, 0)), (), F.TURNS),
            P.World(F.OID, (V1, C(2, F.SOUTH[:2], 5)), (), F.TURNS),
            P.World(F.OID, (C(1, (), 0),), (), F.TURNS),
            P.World(F.OID, (C(1, ["a"], 0),), (), F.TURNS),
            P.World(F.OID, (C(1, ("a", 5), 0),), (), F.TURNS),
            P.World(F.OID, (C(1, ("a", ""), 0),), (), F.TURNS),
            P.World(F.OID, (V1,), (N("n", F.OID, 2, F.SOUTH, 1.5),), F.TURNS),
            P.World(F.OID, (V1,), (N("n", F.OID, True, F.SOUTH, 15),), F.TURNS),
            P.World(F.OID, (V1,), (N("n", F.OID, 0, F.SOUTH, 15),), F.TURNS),
            P.World(F.OID, (V1,), (N("", F.OID, 2, F.SOUTH, 15),), F.TURNS),
            P.World(F.OID, (V1,), [N("n", F.OID, 2, F.SOUTH, 15)], F.TURNS),
            P.World(F.OID, (V1,), (("n", F.OID, 2, F.SOUTH, 15),), F.TURNS),
            {"objective_id": F.OID},
            None,
        ]
        for w in cases:
            with self.subTest(w=w):
                self.bad(w)
                self.bad(w, policy=P.BASELINE)

    def test_bad_config_and_policy(self):
        for c in (P.GuardConfig(True, P.HOLD), P.GuardConfig(-1, P.HOLD), P.GuardConfig(1.0, P.HOLD),
                  P.GuardConfig("1", P.HOLD), {"wait_turns": 1}, None):
            with self.subTest(c=c):
                self.bad(F.BASE, c)
        for pol in ("guard", "", None, ["baseline"], "BASELINE"):
            with self.subTest(policy=pol):
                self.bad(F.BASE, policy=pol)

    def test_objective_must_exist_at_the_first_turn(self):
        w = P.World(F.OID, (C(1, F.NORTH, 50),), (), F.TURNS)
        self.assertEqual(self.bad(w), ("no_objective_at_start",))

    def test_detector_fails_closed_on_a_bad_world(self):
        b = P.run(F.BASE, P.BASELINE)
        self.assertEqual(P.detect_obsolete(None, b)[0][0], "config_error")


class Hygiene(unittest.TestCase):
    BANNED = ("K" + "EEP", "Cloud" + "Agent", "Sm" + "ith", "Chec" + "ker", "sl" + "ack", "grok" + "ki")
    PERMIT = "al" + "low"
    ALL = DOCS + CODE + ("test_plan_change.py", "paper_evidence.json", "mutants.py")

    def day_index(self):
        if not os.path.exists(DAY_INDEX):
            self.skipTest("day index not beside this folder")
        with open(DAY_INDEX, encoding="utf-8") as f:
            return f.read()

    def test_banned_words_absent(self):
        texts = [(n, read(n)) for n in DOCS + CODE]
        if os.path.exists(DAY_INDEX):
            texts.append(("day index", self.day_index()))
        for name, text in texts:
            for w in self.BANNED:
                self.assertNotIn(w.lower(), text.lower(), (name, w))

    def test_no_permit_word_anywhere(self):
        for name in self.ALL:
            self.assertNotIn(self.PERMIT, read(name).lower(), name)

    def test_no_conflict_markers(self):
        for name in self.ALL:
            for line in read(name).splitlines():
                self.assertFalse(line.startswith(("<" * 7, ">" * 7)) or line == "=" * 7, name)

    def test_day_index_footer_once(self):
        text = self.day_index()
        self.assertEqual(text.count("Do not merge experiment PRs without Ork review."), 1)
        self.assertIn("[w20-plan-change-notice](w20-plan-change-notice/)", text)

    def test_stdlib_only_no_runtime_pieces(self):
        permitted = {"dataclasses", "typing", "random", "plan_change", "sys"}
        for name in CODE:
            src = read(name)
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [node.module.split(".")[0]]
                else:
                    continue
                for m in mods:
                    self.assertIn(m, permitted, (name, m))
            for word in ("sqlite", "hmac", "hashlib", "socket", "thread", "subprocess", "urllib",
                         "openai", "anthropic"):
                self.assertNotIn(word, src.lower(), (name, word))

    def test_paper_numbers_only_in_evidence(self):
        ev = json.loads(read("paper_evidence.json"))
        tokens = [c["token"] for c in ev["empirical_claims"]["claims"]]
        self.assertTrue(all(c["status"] == "UNVERIFIED" for c in ev["empirical_claims"]["claims"]))
        pats = [re.escape(t) for t in tokens if any(ch.isdigit() for ch in t)] + [r"(?<!\d)" + "1" + "6" + r"(?!\d)"]
        texts = [(n, read(n)) for n in DOCS + CODE]
        if os.path.exists(DAY_INDEX):
            texts.append(("day index", self.day_index()))
        for name, text in texts:
            for p in pats:
                self.assertIsNone(re.search(p, text), (name, p))


class Evidence(unittest.TestCase):
    def test_shape_and_notice(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.10011")
        self.assertIn("non-exclusive", ev["paper"]["licence"])
        self.assertIn("METHOD ONLY", ev["paper"]["use"])
        notice, readme = read("NOTICE"), read("README.md")
        for t in (notice, readme):
            self.assertIn("2611.10011", t)
            self.assertIn("https://arxiv.org/abs/2611.10011", t)
        for n in (78, 79, 110):
            self.assertIn("https://cursor.com/codebase/coevolution-lab/playground/pull/%d" % n, readme)

    @unittest.skipUnless(os.path.isdir(SOURCES), "source copy not present")
    def test_offsets_and_no_copied_text(self):
        ev = json.loads(read("paper_evidence.json"))
        path = os.path.join(SOURCES, "2611.10011.html")
        if not os.path.exists(path):
            self.skipTest("abs page copy not present")
        with open(path, encoding="utf-8", errors="replace") as f:
            page = f.read()
        ab = html.unescape(re.search(r'<meta name="citation_abstract" content="([^"]*)"', page).group(1))
        self.assertEqual(len(ab), ev["source"]["abstract_chars"])
        for c in ev["empirical_claims"]["claims"]:
            o = c["offset_in_abstract"]
            self.assertEqual(ab[o:o + len(c["token"])], c["token"])
        self.assertIn("nonexclusive-distrib/1.0", page)
        # No run of six words from the abstract appears in our prose or code.
        words = re.findall(r"[a-z0-9']+", ab.lower())
        shingles = {" ".join(words[i:i + 6]) for i in range(len(words) - 5)}
        for name in DOCS + CODE + ("test_plan_change.py",):
            ours = re.findall(r"[a-z0-9']+", read(name).lower())
            mine = {" ".join(ours[i:i + 6]) for i in range(len(ours) - 5)}
            self.assertEqual(shingles & mine, set(), name)


if __name__ == "__main__":
    unittest.main()
