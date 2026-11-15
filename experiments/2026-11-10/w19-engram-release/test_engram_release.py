"""Tests for the w19-engram-release method sketch (stdlib unittest).

Run: python3 -m unittest test_engram_release.py -v
The excerpt check reads the abs page from /tmp and is skipped when absent:
  curl -sL -A 'Mozilla/5.0' https://arxiv.org/abs/2611.09472 -o /tmp/w19er-abs.html
"""

import ast
import html
import inspect
import json
import os
import re
import unittest
from fractions import Fraction

import engram_release as E
import fixtures as F

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_ABS = "/tmp/w19er-abs.html"
IMPL = ("engram_release.py", "fixtures.py")
ALPHA = 0.6
DEFAULT = object()


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def compliant(skill="upper", rule="upper", student=None):
    return F.build(skill, rule, [("abc", "dog"), ("sun",)],
                   ("xyz", "hello", "tree", "moon"), student=student)


def snapshot(store):
    return (store.records(), {s: store.retrieve(s) for s in store.skills()})


class Fixtures(unittest.TestCase):
    def test_every_fixture_as_expected(self):
        lines = []
        failures, total = F.check_all(out=lines.append)
        self.assertEqual(failures, 0, "\n".join(lines))
        self.assertEqual(total, len(F.SCENARIOS) + len(F.VERIFY_CASES) + 1)

    def test_each_scenario(self):
        for name, bkw, rkw, (outcome, reasons, left) in F.SCENARIOS:
            with self.subTest(name):
                store, d = F.run_scenario(name, bkw, rkw)
                self.assertEqual((d.outcome, d.reasons), (outcome, reasons))
                self.assertEqual(len(store.retrieve(bkw["skill"])), left)

    def test_every_hold_scenario_changes_nothing(self):
        for name, bkw, rkw, (outcome, _, _) in F.SCENARIOS:
            if outcome != E.HOLD:
                continue
            with self.subTest(name):
                store, student, base, probes = F.build(**bkw)
                before = snapshot(store)
                d = E.release(store, bkw["skill"], student, base, probes, **rkw)
                self.assertEqual(d.outcome, E.HOLD)
                self.assertEqual(d.released_ids, ())
                self.assertEqual(snapshot(store), before)
                self.assertFalse(any(r.state == E.RELEASED for r in store.records()))


class CompliantPath(unittest.TestCase):
    def test_learned_released_then_not_retrievable(self):
        store, student, base, probes = compliant()
        ids = {r.record_id for r in store.retrieve("upper")}
        self.assertEqual(len(ids), 2)
        self.assertEqual(student.learned["upper"], "upper")
        d = E.release(store, "upper", student, base, probes, alpha=ALPHA)
        self.assertEqual(d.outcome, E.RELEASE)
        self.assertEqual(d.student_score, 1)
        self.assertEqual(d.base_score, 1)
        self.assertEqual(set(d.released_ids), ids)
        self.assertEqual(store.retrieve("upper"), ())
        # Archived, not deleted.
        self.assertEqual({r.state for r in store.records("upper")}, {E.RELEASED})
        self.assertEqual(E.report(store)["upper"]["released"], 2)
        self.assertEqual(E.report(store)["upper"]["retrievable"], 0)

    def test_student_still_answers_after_release(self):
        store, student, base, probes = compliant()
        E.release(store, "upper", student, base, probes, alpha=ALPHA)
        for x, y in probes:
            self.assertEqual(student.answer("upper", x), y)
        # The base with retrieval now sees nothing for the skill.
        self.assertEqual(E.score(lambda x: base.answer("upper", x, store.retrieve("upper")), probes), 0)

    def test_second_release_holds(self):
        store, student, base, probes = compliant()
        E.release(store, "upper", student, base, probes, alpha=ALPHA)
        d = E.release(store, "upper", student, base, probes, alpha=ALPHA)
        self.assertEqual((d.outcome, d.reasons), (E.HOLD, (E.NOTHING_TO_RELEASE,)))

    def test_only_participating_records_released(self):
        store, student, base, probes = F.build("upper", "upper", [("abc",)], ("xyz", "moon"),
                                               late_inputs=[("pen",)])
        d = E.release(store, "upper", student, base, probes, alpha=ALPHA)
        self.assertEqual(d.released_ids, ("upper-0",))
        self.assertEqual([r.record_id for r in store.retrieve("upper")], ["upper-late-0"])

    def test_release_of_one_skill_leaves_others(self):
        store = E.Store()
        store.add(F.rec("u", "upper", "upper", ("abc",)))
        store.add(F.rec("s", "sort", "sort", ("cba",)))
        st = E.Student()
        for sk in ("upper", "sort"):
            store.admit(sk, **F.ADMIT)
            store.train(st, sk)
        d = E.release(store, "upper", st, E.RetrievalBase(), E.make_probes("upper", ("xyz",)), alpha=ALPHA)
        self.assertEqual(d.outcome, E.RELEASE)
        self.assertEqual(len(store.retrieve("sort")), 1)


class ReleaseCriteria(unittest.TestCase):
    def _run(self, name):
        for n, bkw, rkw, exp in F.SCENARIOS:
            if n == name:
                store, d = F.run_scenario(n, bkw, rkw)
                return store, d, bkw["skill"]
        raise KeyError(name)

    def test_unmastered_cannot_release(self):
        store, d, sk = self._run("unmastered_sort_held")
        self.assertEqual(d.outcome, E.HOLD)
        self.assertLess(d.student_score, d.base_score)
        self.assertLessEqual(d.student_score, ALPHA)
        self.assertEqual(len(store.retrieve(sk)), 2)

    def test_fails_relative_only_record_stays(self):
        store, d, sk = self._run("fails_relative_only_held")
        self.assertEqual(d.reasons, (E.BELOW_RELATIVE,))
        self.assertGreater(d.student_score, ALPHA)
        self.assertLess(d.student_score, d.base_score)
        self.assertEqual(len(store.retrieve(sk)), 2)

    def test_fails_absolute_only_record_stays(self):
        store, d, sk = self._run("fails_absolute_only_held")
        self.assertEqual(d.reasons, (E.BELOW_FLOOR,))
        self.assertEqual(d.student_score, d.base_score)
        self.assertEqual(len(store.retrieve(sk)), 1)

    def test_failed_verification_record_states_unchanged(self):
        for name in ("unmastered_sort_held", "fails_relative_only_held",
                     "fails_absolute_only_held", "memorising_student_held"):
            with self.subTest(name):
                store, d, sk = self._run(name)
                self.assertEqual(d.outcome, E.HOLD)
                states = {r.state for r in store.records(sk)}
                self.assertNotIn(E.RELEASED, states)
                self.assertIn(E.ADMITTED, states)

    def test_relative_equality_passes_and_floor_is_strict(self):
        self.assertEqual(E.verify(0.8, 0.8, 0.0, ALPHA), ())
        self.assertEqual(E.verify(ALPHA, 0.0, 0.0, ALPHA), (E.BELOW_FLOOR,))
        self.assertEqual(E.verify(0.61, 0.0, 0.0, ALPHA), ())

    def test_margin(self):
        self.assertEqual(E.verify(0.7, 0.8, -0.2, ALPHA), ())
        self.assertEqual(E.verify(0.7, 0.8, -0.05, ALPHA), (E.BELOW_RELATIVE,))
        self.assertEqual(E.verify(0.9, 0.8, 0.2, ALPHA), (E.BELOW_RELATIVE,))

    def test_both_failures_reported(self):
        self.assertEqual(E.verify(0.2, 0.9, 0.0, ALPHA), (E.BELOW_RELATIVE, E.BELOW_FLOOR))

    def test_release_floor_at_score_holds(self):
        # 2 of 3 probes right gives exactly 2/3; a floor of 2/3 holds.
        store, student, base, _ = F.build("sort", "sort", [("cba",)], ())
        probes = E.make_probes("sort", ("fed", "qpo", "dfe"))
        d = E.release(store, "sort", student, base, probes, alpha=Fraction(2, 3))
        self.assertEqual(d.reasons, (E.BELOW_FLOOR,))

    def test_alpha_is_required(self):
        store, student, base, probes = compliant()
        with self.assertRaises(TypeError):
            E.release(store, "upper", student, base, probes)
        self.assertEqual(len(store.retrieve("upper")), 2)


class AdmissionIsSeparate(unittest.TestCase):
    def test_admission_keeps_records_retrievable(self):
        store = E.Store()
        store.add(F.rec("a", "upper", "upper", ("abc",)))
        before = len(store.retrieve("upper"))
        d = store.admit("upper", **F.ADMIT)
        self.assertEqual(d.outcome, "admitted")
        self.assertEqual(len(store.retrieve("upper")), before)
        self.assertEqual(store.records("upper")[0].state, E.ADMITTED)

    def test_admitted_not_trained_cannot_release(self):
        store, d, sk = ReleaseCriteria._run(self, "admitted_not_trained_held")
        self.assertEqual(d.reasons, (E.NO_PARTICIPATION,))

    def test_not_admitted_cannot_release_even_if_student_masters(self):
        store, student, base, probes = F.build("upper", "upper", [("abc",)], ("xyz", "moon"),
                                               admit=False, train=False, external_fit=True)
        self.assertEqual(E.score(lambda x: student.answer("upper", x), probes), 1)
        d = E.release(store, "upper", student, base, probes, alpha=ALPHA)
        self.assertEqual(d.outcome, E.HOLD)
        self.assertIn(E.NOT_ADMITTED, d.reasons)

    def test_train_refuses_unadmitted(self):
        store = E.Store()
        store.add(F.rec("a", "upper", "upper", ("abc",)))
        d = store.train(E.Student(), "upper")
        self.assertEqual(d.reasons, (E.NOT_ADMITTED,))
        self.assertEqual(store.participation("upper"), frozenset())

    def test_demonstration_branch_admits_at_zero_mastery(self):
        store = E.Store()
        store.add(F.rec("a", "upper", "upper", ("abc",)))
        d = store.admit("upper", mastery=0.0, tau_m=0.8, n_min=5, d_min=1)
        self.assertEqual(d.outcome, "admitted")

    def test_mastery_branch_needs_records_and_eligibility(self):
        store = E.Store()
        store.add(F.rec("a", "upper", "upper", ("abc",), success=False, source="student"))
        held = store.admit("upper", mastery=0.9, tau_m=0.8, n_min=2, d_min=1)
        self.assertEqual(held.reasons, (E.NOT_ELIGIBLE,))
        store.add(F.rec("b", "upper", "upper", ("dog",), success=False, source="student"))
        self.assertEqual(store.admit("upper", mastery=0.9, tau_m=0.8, n_min=2, d_min=1).outcome,
                         "admitted")

    def test_consolidated_skill_not_readmitted_by_mastery(self):
        store2 = E.Store()
        store2.add(F.rec("p", "upper", "upper", ("abc",)))
        store2.add(F.rec("q", "upper", "upper", ("dog",)))
        store2.admit("upper", **F.ADMIT)
        store2.train(E.Student(), "upper")
        store2._admitted.discard("upper")  # simulate a fresh admission round
        d = store2.admit("upper", mastery=1.0, tau_m=0.8, n_min=1, d_min=99)
        self.assertEqual(d.reasons, (E.NOT_ELIGIBLE,))

    def test_admission_malformed_inputs_hold(self):
        store = E.Store()
        store.add(F.rec("a", "upper", "upper", ("abc",)))
        bad = [dict(mastery=float("nan"), tau_m=0.8, n_min=1, d_min=1),
               dict(mastery=True, tau_m=0.8, n_min=1, d_min=1),
               dict(mastery="0.9", tau_m=0.8, n_min=1, d_min=1),
               dict(mastery=0.9, tau_m=float("inf"), n_min=1, d_min=1),
               dict(mastery=0.9, tau_m=0.8, n_min=True, d_min=1),
               dict(mastery=0.9, tau_m=0.8, n_min=1, d_min=0),
               dict(mastery=0.9, tau_m=0.8, n_min=1.0, d_min=1),
               dict(mastery=1.5, tau_m=0.8, n_min=1, d_min=1)]
        for kw in bad:
            with self.subTest(kw=kw):
                self.assertEqual(store.admit("upper", **kw).reasons, (E.BAD_INPUT,))
        self.assertFalse(store.is_admitted("upper"))
        self.assertEqual(store.admit("nope", **F.ADMIT).reasons, (E.UNKNOWN_SKILL,))

    def test_training_failure_leaves_store_unchanged(self):
        store = E.Store()
        store.add(F.rec("a", "upper", "upper", ("abc",)))
        store.admit("upper", **F.ADMIT)
        before = snapshot(store)
        d = store.train(F.RaisingFit(), "upper")
        self.assertEqual(d.reasons, (E.TRAINING_FAILED,))
        self.assertEqual(snapshot(store), before)
        self.assertEqual(store.participation("upper"), frozenset())

    def test_failed_records_give_no_participation(self):
        store = E.Store()
        store.add(F.rec("a", "upper", "upper", ("abc",), success=False))
        store.add(F.rec("b", "upper", "upper", ("dog",), success=False))
        store.admit("upper", mastery=0.9, tau_m=0.8, n_min=2, d_min=1)
        self.assertEqual(store.train(E.Student(), "upper").reasons, (E.NO_PARTICIPATION,))


class ProbeCopyTautology(unittest.TestCase):
    def test_memorising_student_fails_held_out_probes(self):
        m = E.MemorisingStudent()
        store, student, base, probes = compliant(student=m)
        # It reproduces every record exactly ...
        for r in store.records("upper"):
            for x, y in r.examples:
                self.assertEqual(m.answer("upper", x), y)
        # ... yet answers none of the held-out probes.
        self.assertEqual(E.score(lambda x: m.answer("upper", x), probes), 0)
        d = E.release(store, "upper", m, base, probes, alpha=ALPHA)
        self.assertEqual(d.outcome, E.HOLD)
        self.assertEqual(len(store.retrieve("upper")), 2)

    def test_probes_disjoint_from_record_text(self):
        for name, bkw, rkw, (outcome, _, _) in F.SCENARIOS:
            if outcome != E.RELEASE:
                continue
            with self.subTest(name):
                store, _, _, probes = F.build(**bkw)
                text = " ".join(r.text for r in store.records())
                tokens = set(re.findall(r"[A-Za-z]+", text))
                for x, y in probes:
                    self.assertNotIn(x, tokens)
                    self.assertNotIn(y, tokens)

    def test_probe_copied_from_record_holds(self):
        m = E.MemorisingStudent()
        store, _, base, _ = F.build("upper", "upper", [("abc", "dog")], (), student=m)
        leaked = E.make_probes("upper", ("abc", "dog"))
        # Without the overlap check this would be a perfect, tautological score.
        self.assertEqual(E.score(lambda x: m.answer("upper", x), leaked), 1)
        self.assertEqual(E.detect_probe_overlap(store, "upper", leaked), ("abc", "dog"))
        d = E.release(store, "upper", m, base, leaked, alpha=ALPHA)
        self.assertEqual(d.reasons, (E.PROBE_OVERLAP,))

    def test_one_leaked_probe_is_enough_to_hold(self):
        store, student, base, _ = compliant()
        probes = E.make_probes("upper", ("xyz", "hello", "sun"))
        d = E.release(store, "upper", student, base, probes, alpha=ALPHA)
        self.assertEqual(d.reasons, (E.PROBE_OVERLAP,))

    def test_overlap_counts_released_records_too(self):
        store, student, base, probes = compliant()
        E.release(store, "upper", student, base, probes, alpha=ALPHA)
        self.assertEqual(E.detect_probe_overlap(store, "upper", E.make_probes("upper", ("abc",))),
                         ("abc",))


class StudentWithoutRetrieval(unittest.TestCase):
    def test_student_answer_takes_no_context(self):
        for cls in (E.Student, E.MemorisingStudent):
            params = list(inspect.signature(cls.answer).parameters)
            self.assertEqual(params, ["self", "skill", "x"])

    def test_release_calls_student_without_context(self):
        calls = []

        class Spy(E.Student):
            def answer(self, *args, **kwargs):
                calls.append((args, kwargs))
                return super().answer(*args, **kwargs)

        store, student, base, probes = compliant(student=Spy())
        E.release(store, "upper", student, base, probes, alpha=ALPHA)
        self.assertTrue(calls)
        for args, kwargs in calls:
            self.assertEqual(len(args), 2)
            self.assertEqual(kwargs, {})

    def test_base_sees_pre_release_store(self):
        seen = []

        class SpyBase(E.RetrievalBase):
            def answer(self, skill, x, context):
                seen.append(tuple(r.record_id for r in context))
                return super().answer(skill, x, context)

        store, student, _, probes = compliant()
        E.release(store, "upper", student, SpyBase(), probes, alpha=ALPHA)
        self.assertTrue(seen)
        self.assertTrue(all(s == ("upper-0", "upper-1") for s in seen))

    def test_student_answers_do_not_depend_on_store(self):
        store, student, base, probes = compliant()
        before = [student.answer("upper", x) for x, _ in probes]
        store._records.clear()
        store._order.clear()
        self.assertEqual([student.answer("upper", x) for x, _ in probes], before)


class FailClosed(unittest.TestCase):
    def _hold(self, *, skill="upper", probes=DEFAULT, student=None, base=None, **kw):
        store, st, b, pr = compliant()
        kw.setdefault("alpha", ALPHA)
        d = E.release(store, skill, student or st, base or b,
                      pr if probes is DEFAULT else probes, **kw)
        self.assertEqual(d.outcome, E.HOLD)
        self.assertEqual(len(store.retrieve("upper")), 2)
        return d

    def test_bad_floor(self):
        for a in (float("nan"), float("inf"), -0.1, 1.0, 2, True, False, "0.6", None):
            with self.subTest(alpha=a):
                self.assertIn(E.BAD_FLOOR, self._hold(alpha=a).reasons)

    def test_bad_margin(self):
        for m in (float("nan"), float("-inf"), 1.5, -2, True, "0", None):
            with self.subTest(delta=m):
                self.assertIn(E.BAD_MARGIN, self._hold(delta=m).reasons)

    def test_bad_scores(self):
        for s in (float("nan"), float("inf"), -0.1, 1.1, True, "1", None):
            with self.subTest(score=s):
                self.assertIn(E.BAD_SCORE, E.verify(s, 0.4, 0.0, ALPHA))
                self.assertIn(E.BAD_SCORE, E.verify(0.9, s, 0.0, ALPHA))

    def test_empty_and_malformed_probes(self):
        self.assertEqual(self._hold(probes=()).reasons, (E.EMPTY_PROBES,))
        self.assertEqual(self._hold(probes=[]).reasons, (E.EMPTY_PROBES,))
        for p in ([["xyz", "XYZ"]], [("xyz",)], [("xyz", None)], [(1, "1")],
                  "xyz", None, iter([("xyz", "XYZ")]), {("xyz", "XYZ")}):
            with self.subTest(probes=p):
                self.assertEqual(self._hold(probes=p).reasons, (E.MALFORMED_PROBES,))

    def test_unknown_or_non_string_skill(self):
        for s in ("nope", "", None, 1, ("upper",)):
            with self.subTest(skill=s):
                self.assertEqual(self._hold(skill=s).reasons, (E.UNKNOWN_SKILL,))

    def test_model_errors(self):
        self.assertEqual(self._hold(student=F.RaisingAnswer()).reasons, (E.MODEL_ERROR,))

        class BadBase:
            def answer(self, skill, x, context):
                raise ValueError("boom")

        self.assertEqual(self._hold(base=BadBase()).reasons, (E.MODEL_ERROR,))
        self.assertEqual(self._hold(student=object()).reasons, (E.MODEL_ERROR,))

    def test_store_rejects_bad_records(self):
        store = E.Store()
        store.add(F.rec("a", "upper", "upper", ("abc",)))
        with self.assertRaises(ValueError):
            store.add(F.rec("a", "upper", "upper", ("dog",)))
        with self.assertRaises(TypeError):
            store.add({"record_id": "b"})
        with self.assertRaises(ValueError):
            store.add(E.Record("c", "", (("a", "A"),)))


def sort_store(probe_inputs):
    """Trained on one descending input, the student induces reverse, not sort."""
    store, student, base, _ = F.build("sort", "sort", [("cba",)], ())
    return store, student, base, E.make_probes("sort", probe_inputs)


class ExactBoundary(unittest.TestCase):
    # Descending inputs (reverse happens to be right) and others (it is wrong);
    # none shares letters-in-any-order with the record "cba".
    RIGHT = ("fed", "qpo", "ihg", "nml", "wvu", "tsr", "kji", "onm", "rqp", "zwv")
    WRONG = ("dfe", "kml", "hgj", "rts", "pqo", "uwv", "jik", "mon", "qrp", "wzv")

    def _probes(self, right, total):
        return self.RIGHT[:right] + self.WRONG[:total - right]

    def test_score_equal_to_float_floor_holds_end_to_end(self):
        for alpha, right, total in ((0.3, 3, 10), (0.6, 3, 5), (0.7, 7, 10)):
            with self.subTest(alpha=alpha):
                store, student, base, probes = sort_store(self._probes(right, total))
                self.assertEqual(student.learned["sort"], "reverse")
                d = E.release(store, "sort", student, base, probes, alpha=alpha)
                self.assertEqual(d.student_score, Fraction(right, total))
                self.assertEqual(d.student_score, d.base_score)
                self.assertEqual((d.outcome, d.reasons), (E.HOLD, (E.BELOW_FLOOR,)))
                self.assertEqual(len(store.retrieve("sort")), 1)

    def test_same_boundary_as_fraction_or_str_form(self):
        for alpha in (Fraction(3, 5), Fraction("0.6"), 0.6):
            store, student, base, probes = sort_store(self._probes(3, 5))
            d = E.release(store, "sort", student, base, probes, alpha=alpha)
            self.assertEqual(d.reasons, (E.BELOW_FLOOR,), repr(alpha))

    def test_one_step_above_floor_releases(self):
        # The gate is not refuse-everything: 4/5 over a 0.6 floor clears it.
        store, student, base, probes = sort_store(self._probes(4, 5))
        d = E.release(store, "sort", student, base, probes, alpha=0.6)
        self.assertEqual(d.outcome, E.RELEASE)

    def test_float_inputs_convert_exactly(self):
        self.assertEqual(E._exact(0.6), Fraction(3, 5))
        self.assertEqual(E._exact(0.3), Fraction(3, 10))
        self.assertEqual(E._exact(0.1 + 0.2), Fraction("0.30000000000000004"))
        self.assertEqual(E.verify(Fraction(3, 5), 0.6, 0.0, 0.6), (E.BELOW_FLOOR,))
        self.assertEqual(E.verify(0.6 + 1e-12, 0.6, 0.0, 0.6), ())
        self.assertEqual(E.verify(Fraction(7, 10), Fraction(8, 10), -0.1, 0.6), ())
        self.assertEqual(E.verify(Fraction(7, 10), Fraction(9, 10), -0.1, 0.6),
                         (E.BELOW_RELATIVE,))

    def test_non_finite_and_foreign_numbers_hold(self):
        from decimal import Decimal
        for v in (float("nan"), float("inf"), float("-inf"), Decimal("0.6"),
                  10 ** 400, True, None, "0.6", complex(0.6, 0)):
            with self.subTest(v=v):
                if v != 10 ** 400:
                    self.assertIsNone(E._exact(v))
                self.assertIn(E.BAD_FLOOR, E.verify(0.9, 0.4, 0.0, v))
                self.assertIn(E.BAD_SCORE, E.verify(v, 0.4, 0.0, 0.6))
                self.assertIn(E.BAD_MARGIN, E.verify(0.9, 0.4, v, 0.6))


class NearCopyProbes(unittest.TestCase):
    RECORDS = ("abc", "dog", "sun")
    ATTACKS = {
        "exact": ["abc", "dog", "sun"],
        "whitespace": [" abc", "dog ", "s un"],
        "case": ["ABC", "Dog", "sUN"],
        "combining accent": ["abc\u0301", "dog", "sun"],
        "fullwidth": ["\uff41\uff42\uff43", "\uff44\uff4f\uff47", "\uff53\uff55\uff4e"],
        "look-alike and zero-width": ["\u0430bc", "d\u043eg", "sun\u200b"],
        "punctuation": ["abc.", "dog!", "s-un"],
        "reorder": ["cba", "god", "nus"],
    }
    # Not copies; flagged or not, a copier cannot answer them.
    EDITS = {
        "truncation": ["ab", "do", "su"],
        "prefix/suffix": ["xabc", "dogs", "sunx"],
        "one-letter edit": ["abd", "dig", "son"],
    }

    def _run(self, rule, inputs, student):
        store, _, base, _ = F.build(rule, rule, [(x,) for x in self.RECORDS], (),
                                    student=student)
        probes = E.make_probes(rule, tuple(inputs))
        before = snapshot(store)
        d = E.release(store, rule, student, base, probes, alpha=ALPHA)
        self.assertEqual(snapshot(store), before)
        return store, probes, d

    def test_every_near_copy_is_flagged_and_held(self):
        for rule in ("upper", "sort", "reverse", "double"):
            for name, inputs in self.ATTACKS.items():
                with self.subTest(rule=rule, attack=name):
                    store, probes, d = self._run(rule, inputs, F.FuzzyCopier())
                    self.assertTrue(E.detect_probe_overlap(store, rule, probes))
                    self.assertEqual(d.reasons, (E.PROBE_OVERLAP,))

    def test_edits_hold_with_a_copier(self):
        for rule in ("upper", "sort", "reverse", "double"):
            for name, inputs in self.EDITS.items():
                with self.subTest(rule=rule, attack=name):
                    _, _, d = self._run(rule, inputs, F.FuzzyCopier())
                    self.assertEqual(d.outcome, E.HOLD)

    def test_expected_output_equal_to_record_output_holds(self):
        store, _, _, _ = F.build("upper", "upper", [("abc",)], ())
        self.assertTrue(E.detect_probe_overlap(store, "upper", (("ABC", "ABC"),)))
        # A new input whose label equals a stored output is flagged too.
        store, _, _, _ = F.build("sort", "sort", [("cab",)], ())
        self.assertEqual(E.detect_probe_overlap(store, "sort", (("zz", "abc"),)), ("zz",))

    def test_normalise(self):
        for raw in (" A b-C. ", "\uff21\uff22\uff23", "\u0430bc\u200b", "a\u0301bc", "A_B_C"):
            self.assertEqual(E.normalise(raw), "abc", repr(raw))
        # Distinct letters stay distinct: the key recomposes after dropping
        # accents, so a letter whose decomposition ends in a spacing mark
        # (Tamil AU, Myanmar UU) is not folded into a different letter.
        self.assertNotEqual(E.normalise("\u0b94"), E.normalise("\u0b92"))
        self.assertNotEqual(E.normalise("\u1026"), E.normalise("\u1025"))

    def test_held_out_probes_still_pass_the_check(self):
        for name, bkw, rkw, (outcome, _, _) in F.SCENARIOS:
            if outcome == E.RELEASE:
                store, _, _, probes = F.build(**bkw)
                self.assertEqual(E.detect_probe_overlap(store, bkw["skill"], probes), (), name)


class StrOnlyScoring(unittest.TestCase):
    def test_object_equal_to_anything_scores_zero(self):
        self.assertEqual(E.score(lambda x: F.AlwaysEqual(), (("a", "A"), ("b", "B"))), 0)
        store, _, base, probes = compliant()
        d = E.release(store, "upper", F.EqualityCheat(), base, probes, alpha=ALPHA)
        self.assertEqual(d.outcome, E.HOLD)
        self.assertEqual(d.student_score, 0)
        self.assertEqual(len(store.retrieve("upper")), 2)

    def test_str_subclass_and_other_types_score_zero(self):
        class S(str):
            def __eq__(self, other):
                return True
            __hash__ = str.__hash__

        for a in (S("nope"), b"A", ["A"], None, 1):
            self.assertEqual(E.score(lambda x, a=a: a, (("a", "A"),)), 0, repr(a))
        self.assertEqual(E.score(lambda x: "A", (("a", "A"),)), 1)


class Eq2Edges(unittest.TestCase):
    def _store(self, n, success=True, source="student"):
        s = E.Store()
        for i in range(n):
            s.add(E.Record("r%d" % i, "k", (("a", "A"),), success, source))
        return s

    def test_mastery_equal_to_threshold_admits(self):
        d = self._store(2).admit("k", mastery=0.8, tau_m=0.8, n_min=2, d_min=9)
        self.assertEqual(d.outcome, "admitted")
        d = self._store(2).admit("k", mastery=Fraction(4, 5), tau_m=0.8, n_min=2, d_min=9)
        self.assertEqual(d.outcome, "admitted")
        d = self._store(2).admit("k", mastery=0.79, tau_m=0.8, n_min=2, d_min=9)
        self.assertEqual(d.reasons, (E.NOT_ELIGIBLE,))

    def test_mastery_branch_needs_n_min(self):
        d = self._store(2).admit("k", mastery=0.9, tau_m=0.8, n_min=3, d_min=9)
        self.assertEqual(d.reasons, (E.NOT_ELIGIBLE,))

    def test_failed_teacher_records_are_not_demonstrations(self):
        d = self._store(3, success=False, source="teacher").admit(
            "k", mastery=0.0, tau_m=0.8, n_min=9, d_min=1)
        self.assertEqual(d.reasons, (E.NOT_ELIGIBLE,))
        s = self._store(2, success=False, source="teacher")
        s.add(E.Record("ok", "k", (("b", "B"),), True, "teacher"))
        self.assertEqual(s.admit("k", mastery=0.0, tau_m=0.8, n_min=9, d_min=2).reasons,
                         (E.NOT_ELIGIBLE,))
        self.assertEqual(s.admit("k", mastery=0.0, tau_m=0.8, n_min=9, d_min=1).outcome,
                         "admitted")

    def test_student_records_are_not_demonstrations(self):
        d = self._store(3, success=True, source="student").admit(
            "k", mastery=0.0, tau_m=0.8, n_min=9, d_min=1)
        self.assertEqual(d.reasons, (E.NOT_ELIGIBLE,))

    def test_mastery_rise_does_not_requalify_consolidated_skill(self):
        # Stricter than the paper on purpose: no re-qualification on a mastery rise.
        s = self._store(2)
        s.add(E.Record("t", "k", (("b", "B"),), True, "teacher"))
        self.assertEqual(s.admit("k", mastery=0.0, tau_m=0.8, n_min=2, d_min=1).outcome, "admitted")
        self.assertEqual(s.train(E.Student(), "k").outcome, "trained")
        s._admitted.discard("k")  # a fresh admission round
        d = s.admit("k", mastery=1.0, tau_m=0.8, n_min=1, d_min=9)
        self.assertEqual(d.reasons, (E.NOT_ELIGIBLE,))
        # The demonstration branch still admits it.
        self.assertEqual(s.admit("k", mastery=1.0, tau_m=0.8, n_min=1, d_min=1).outcome, "admitted")


class OuterHandlerHolds(unittest.TestCase):
    def test_broken_store_holds_never_releases(self):
        for bad in (None, object(), {}, "store"):
            with self.subTest(store=bad):
                d = E.release(bad, "upper", E.Student(), E.RetrievalBase(),
                              (("x", "X"),), alpha=ALPHA)
                self.assertEqual((d.outcome, d.reasons), (E.HOLD, (E.MODEL_ERROR,)))
                self.assertEqual(d.released_ids, ())

    def test_store_raising_mid_gate_holds(self):
        store, student, base, probes = compliant()

        def boom(skill):
            raise RuntimeError("store failure")

        store.participation = boom
        before = store.records()
        d = E.release(store, "upper", student, base, probes, alpha=ALPHA)
        self.assertEqual((d.outcome, d.reasons), (E.HOLD, (E.MODEL_ERROR,)))
        self.assertEqual(store.records(), before)


WORDS = ("abc", "dog", "sun", "moon", "tree")


def concat_store(student=None, rule="upper", words=WORDS):
    return F.build(rule, rule, [tuple(words)], (), student=student)


class ReferenceAdversaries(unittest.TestCase):
    CONCAT = {
        "two-way": ("abcdog", "sunmoon", "treeabc"),
        "three-way": ("abcdogsun", "moontreeabc"),
        "repeat": ("abcabc", "dogdogdog"),
        "case": ("ABCdog", "SunMoon"),
        "space": ("abc dog", "sun  moon", " tree abc "),
        "case and space": ("ABC Dog", "s u n m o o n"),
        "punctuation and width": ("abc-dog", "\uff53\uff55\uff4emoon"),
    }

    def test_concat_attacks_hold(self):
        for name, inputs in self.CONCAT.items():
            with self.subTest(attack=name):
                cop = F.SegmentCopier()
                store, _, base, _ = concat_store(cop)
                probes = E.make_probes("upper", inputs)
                before = snapshot(store)
                d = E.release(store, "upper", cop, base, probes, alpha=ALPHA)
                self.assertEqual((d.outcome, d.reasons), (E.HOLD, (E.PROBE_ANSWERABLE,)))
                self.assertEqual(snapshot(store), before)
                self.assertEqual(len(store.retrieve("upper")), 1)

    def test_concat_attack_is_real_and_not_caught_by_overlap(self):
        cop = F.SegmentCopier()
        store, _, _, _ = concat_store(cop)
        probes = E.make_probes("upper", ("abcdog", "sunmoon", "treeabc"))
        self.assertEqual(E.detect_probe_overlap(store, "upper", probes), ())
        self.assertEqual(E.score(lambda x: cop.answer("upper", x), probes), 1)
        hits = E.detect_answerable_from_records(store, "upper", probes)
        self.assertIn(("segmentation", "abcdog"), hits)
        self.assertIn(("normalised_segmentation", "sunmoon"), hits)

    def test_one_answerable_probe_is_enough(self):
        store, student, base, _ = concat_store()
        probes = E.make_probes("upper", ("xyz", "hello", "lamp", "dogsun"))
        d = E.release(store, "upper", student, base, probes, alpha=ALPHA)
        self.assertEqual(d.reasons, (E.PROBE_ANSWERABLE,))

    def test_each_adversary_on_its_own(self):
        store, _, _, _ = concat_store()
        found = lambda probes: {n for n, _ in E.detect_answerable_from_records(store, "upper", probes)}
        self.assertIn("exact_lookup", found((("abc", "ABC"),)))
        self.assertIn("normalised_lookup", found((("A b C", "ABC"),)))
        self.assertEqual(found((("A b C", "ABC"),)) & {"exact_lookup", "segmentation"}, set())
        self.assertIn("segmentation", found((("abcdog", "ABCDOG"),)))
        self.assertEqual(found((("Abc Dog", "ABC DOG"),)), {"normalised_segmentation"})

    def test_exhaustive_segmentation_beats_greedy(self):
        # Greedy longest-first takes "abc" and is stuck on "d"; "ab"+"cd" works.
        cop = F.SegmentCopier()
        store, _, base, _ = F.build("upper", "upper", [("ab", "abc", "cd")], (), student=cop)
        probes = E.make_probes("upper", ("abcd",))
        self.assertIsNone(cop.answer("upper", "abcd"))
        self.assertTrue(E.detect_answerable_from_records(store, "upper", probes))

    def test_outputs_compared_normalised(self):
        store, _, _, _ = concat_store()
        self.assertTrue(E.detect_answerable_from_records(store, "upper", (("abcdog", "ABC-DOG"),)))
        self.assertTrue(E.detect_answerable_from_records(store, "upper", (("abcdog", "abc dog"),)))

    def test_unbounded_segmentation_holds(self):
        store = E.Store()
        for i, (x, y) in enumerate((("a", "P"), ("a", "Q"), ("b", "R"), ("b", "S"))):
            store.add(E.Record("r%d" % i, "k", ((x, y),)))
        probes = (("ababababa", "nothing-like-it"),)
        self.assertTrue(E.detect_answerable_from_records(store, "k", probes))

    def test_pre_check_runs_before_any_model(self):
        calls = []

        class Spy(F.SegmentCopier):
            def answer(self, skill, x):
                calls.append(x)
                return super().answer(skill, x)

        class SpyBase(E.RetrievalBase):
            def answer(self, skill, x, context):
                calls.append(x)
                return super().answer(skill, x, context)

        s = Spy()
        store, _, _, _ = concat_store(s)
        d = E.release(store, "upper", s, SpyBase(), E.make_probes("upper", ("abcdog",)), alpha=ALPHA)
        self.assertEqual(d.reasons, (E.PROBE_ANSWERABLE,))
        self.assertEqual(calls, [])

    def test_generalising_student_still_releases(self):
        store, student, base, probes = concat_store()
        probes = E.make_probes("upper", ("xyz", "hello", "lamp", "frog", "kite"))
        self.assertEqual(E.detect_answerable_from_records(store, "upper", probes), ())
        d = E.release(store, "upper", student, base, probes, alpha=ALPHA)
        self.assertEqual(d.outcome, E.RELEASE)
        self.assertEqual(store.retrieve("upper"), ())

    def test_release_fixture_probes_pass_the_pre_check(self):
        for name, bkw, rkw, (outcome, _, _) in F.SCENARIOS:
            if outcome == E.RELEASE:
                store, _, _, probes = F.build(**bkw)
                self.assertEqual(E.detect_answerable_from_records(store, bkw["skill"], probes), (), name)

    def test_probe_label_equal_to_record_output_only(self):
        # Record outputs are part of the copy check, not only inputs.
        store = E.Store()
        store.add(E.Record("r", "k", (("cat", "dog"),)))
        self.assertEqual(E.detect_probe_overlap(store, "k", (("xyz", "dog"),)), ("xyz",))
        st = E.Student()
        store.admit("k", **F.ADMIT)
        store.train(st, "k")
        d = E.release(store, "k", st, E.RetrievalBase(), (("xyz", "dog"),), alpha=ALPHA)
        self.assertEqual((d.outcome, d.reasons), (E.HOLD, (E.PROBE_OVERLAP,)))
        self.assertEqual(len(store.retrieve("k")), 1)


class ReferenceAdversariesMore(unittest.TestCase):
    def test_raw_segmentation_catches_what_normalising_hides(self):
        # A record whose input normalises to nothing still splices raw.
        store = E.Store()
        for i, (x, y) in enumerate((("a", "A"), ("b", "B"), ("!", "X"))):
            store.add(E.Record("r%d" % i, "k", ((x, y),)))
        hits = E.detect_answerable_from_records(store, "k", (("a!b", "AXB"),))
        self.assertEqual({n for n, _ in hits}, {"segmentation"})

    def test_archived_records_still_feed_the_pre_check(self):
        store, student, base, probes = compliant()
        self.assertEqual(E.release(store, "upper", student, base, probes, alpha=ALPHA).outcome, E.RELEASE)
        self.assertEqual(store.retrieve("upper"), ())
        self.assertTrue(E.detect_answerable_from_records(store, "upper", (("abcdog", "ABCDOG"),)))


class Hardening(unittest.TestCase):
    def test_probe_parts_must_be_plain_str(self):
        class L(str):
            def __eq__(self, other):
                return True
            __hash__ = str.__hash__

        class Plain(str):
            pass

        for p in ((("a", L("A")),), ((L("a"), "A"),), (("a", Plain("A")),)):
            self.assertEqual(E.validate_probes(p), E.MALFORMED_PROBES)
        store, student, base, _ = compliant()
        d = E.release(store, "upper", student, base, (("xyz", L("nope")),), alpha=ALPHA)
        self.assertEqual(d.reasons, (E.MALFORMED_PROBES,))

    def odd_numbers(self):
        class NpLike(float):
            def __repr__(self):
                return "np.float64(%s)" % float.__repr__(self)

        class Liar(float):
            def __repr__(self):
                return "0.0"

        class Raiser(float):
            def __repr__(self):
                raise RuntimeError("no repr")

        class IntSub(int):
            pass

        class FracSub(Fraction):
            pass

        class HasFloat:
            def __float__(self):
                return 0.6

        from decimal import Decimal
        return (NpLike(0.6), Liar(0.9), Raiser(0.6), IntSub(0), FracSub(3, 5),
                HasFloat(), Decimal("0.6"), "0.6", b"0.6", [0.6], None, True)

    def test_verify_holds_never_raises(self):
        for v in self.odd_numbers():
            with self.subTest(v=type(v).__name__):
                self.assertIn(E.BAD_FLOOR, E.verify(Fraction(4, 5), 0, 0, v))
                self.assertIn(E.BAD_MARGIN, E.verify(Fraction(4, 5), 0, v, 0.6))
                self.assertIn(E.BAD_SCORE, E.verify(v, 0, 0, 0.6))
                self.assertIn(E.BAD_SCORE, E.verify(Fraction(4, 5), v, 0, 0.6))

    def test_admit_holds_never_raises(self):
        for v in self.odd_numbers():
            with self.subTest(v=type(v).__name__):
                store = E.Store()
                store.add(F.rec("a", "upper", "upper", ("abc",)))
                self.assertEqual(store.admit("upper", mastery=v, tau_m=0.6, n_min=1, d_min=9).reasons,
                                 (E.BAD_INPUT,))
                self.assertEqual(store.admit("upper", mastery=0.9, tau_m=v, n_min=1, d_min=9).reasons,
                                 (E.BAD_INPUT,))
                self.assertFalse(store.is_admitted("upper"))

    def test_release_with_odd_floor_holds_bad_floor(self):
        for v in self.odd_numbers():
            with self.subTest(v=type(v).__name__):
                store, student, base, probes = compliant()
                d = E.release(store, "upper", student, base, probes, alpha=v)
                self.assertEqual((d.outcome, d.reasons), (E.HOLD, (E.BAD_FLOOR,)))
                self.assertEqual(len(store.retrieve("upper")), 2)

    def test_non_decimal_float_floor_read_strictly(self):
        third = 1 / 3
        self.assertEqual(E._exact(third, E.HIGH), Fraction(1, 3))
        self.assertEqual(E._exact(third, E.LOW), Fraction(float.__repr__(third)))
        self.assertEqual(E.verify(Fraction(1, 3), 0, 0, third), (E.BELOW_FLOOR,))
        self.assertEqual(E.verify(Fraction(1, 3), 0, 0, Fraction(1, 3)), (E.BELOW_FLOOR,))
        self.assertEqual(E.verify(third, 0, 0, Fraction(1, 3)), (E.BELOW_FLOOR,))
        # A float student score is read low: between its two readings it fails.
        self.assertEqual(E.verify(third, 0, 0, Fraction(float.__repr__(third))), (E.BELOW_FLOOR,))
        # A float base score is read high: between its two readings it wins.
        self.assertEqual(E.verify(Fraction(float.__repr__(third)), third, 0, 0), (E.BELOW_RELATIVE,))
        self.assertEqual(E.verify(Fraction(2, 3), Fraction(2, 3), 0, 2 / 3), (E.BELOW_FLOOR,))
        self.assertEqual(E.verify(Fraction(2, 3) + Fraction(1, 10 ** 9), 0, 0, 2 / 3), ())
        # A decimal float that is not near a simple fraction keeps its decimal value.
        self.assertEqual(E._exact(0.6 + 1e-12, E.HIGH), Fraction("0.600000000001"))
        self.assertEqual(E._exact(0.1 + 0.2, E.HIGH), Fraction("0.30000000000000004"))

    def test_low_mastery_reading_is_strict(self):
        store = E.Store()
        for i in range(2):
            store.add(F.rec("r%d" % i, "k", "upper", ("ab",), success=False, source="student"))
        # mastery 1/3 as a float is read low, threshold 1/3 as a Fraction: held.
        self.assertEqual(store.admit("k", mastery=1 / 3, tau_m=Fraction(1, 3), n_min=2, d_min=9).reasons,
                         (E.NOT_ELIGIBLE,))
        self.assertEqual(store.admit("k", mastery=Fraction(1, 3), tau_m=1 / 3, n_min=2, d_min=9).outcome,
                         "admitted")


class Hygiene(unittest.TestCase):
    BANNED = ("K" + "EEP", "Cloud" + "Agent", "Sm" + "ith", "Chec" + "ker")

    def test_banned_words_absent(self):
        for name in ("README.md", "NOTICE") + IMPL:
            text = read(name)
            for w in self.BANNED:
                with self.subTest(file=name, word=w):
                    self.assertFalse(w.lower() in text.lower(), (name, w))
            for w in ("slack", "grokki"):
                self.assertFalse(w in text.lower(), (name, w))

    def test_no_permit_vocabulary(self):
        for name in ("README.md", "NOTICE") + IMPL:
            self.assertFalse("allow" in read(name).lower(), name)
        self.assertEqual(set(E.OUTCOMES), {E.RELEASE, E.HOLD})

    def test_no_conflict_markers(self):
        for name in ("README.md", "NOTICE", "paper_evidence.json") + IMPL:
            for m in ("<" * 7, ">" * 7, "=" * 7 + "\n"):
                self.assertNotIn(m, read(name), name)

    def test_stdlib_only_offline(self):
        allowed = {"math", "re", "unicodedata", "dataclasses", "fractions", "typing",
                   "engram_release", "sys"}
        for name in IMPL:
            tree = ast.parse(read(name))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [node.module.split(".")[0]]
                else:
                    continue
                for m in mods:
                    self.assertIn(m, allowed, (name, m))

    def test_paper_numbers_only_in_evidence(self):
        ev = json.loads(read("paper_evidence.json"))
        nums = set()
        for c in ev["empirical_claims"]["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")
            nums.update(n for n in re.findall(r"\d+(?:\.\d+)?%?", c["text"]))
        nums = {n for n in nums if len(n.strip("%")) >= 2 or "." in n}
        for name in ("README.md", "NOTICE") + IMPL:
            text = read(name)
            for n in nums:
                with self.subTest(file=name, number=n):
                    self.assertIsNone(re.search(r"(?<![\d.])" + re.escape(n) + r"(?![\d])", text))


class Evidence(unittest.TestCase):
    def test_evidence_shape(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.09472")
        self.assertIn("CC BY 4.0", ev["paper"]["licence"])
        self.assertEqual(ev["upstream_code"]["status"], "UNVERIFIED")
        self.assertFalse(ev["upstream_code"]["used"])
        self.assertEqual(len(ev["excerpts"]), 3)
        self.assertEqual(ev["empirical_claims"]["status"], "UNVERIFIED")

    def test_notice_and_readme_credit(self):
        notice, readme = read("NOTICE"), read("README.md")
        ev = json.loads(read("paper_evidence.json"))
        for a in ev["paper"]["authors"]:
            self.assertIn(a, notice.replace("\n", " "))
        for t in (notice, readme):
            self.assertIn("2611.09472", t)
            self.assertIn("CC BY 4.0", t)
        self.assertIn("anonymous.4open.science/r/engram-anonymous", readme)
        self.assertIn("UNVERIFIED", readme)

    @unittest.skipUnless(os.path.exists(PAPER_ABS), "abs page not cached in /tmp")
    def test_excerpts_verbatim_in_abs(self):
        with open(PAPER_ABS, encoding="utf-8") as f:
            raw = f.read()
        t = re.sub(r"<math.*?</math>", " ", raw, flags=re.S)
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
        ev = json.loads(read("paper_evidence.json"))
        for e in ev["excerpts"]:
            with self.subTest(e["id"]):
                self.assertEqual(t.count(e["excerpt"]), 1)
        self.assertIn("http://creativecommons.org/licenses/by/4.0/", raw)


if __name__ == "__main__":
    unittest.main()
