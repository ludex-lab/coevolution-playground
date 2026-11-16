"""Tests for mb-owned-exceptions. Run: python3 -B -m unittest"""

import hashlib
import itertools
import json
import math
import os
import random
import unittest

import demo
import fixtures
import oracle
import owned_exceptions as oe

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = "mb-owned-exceptions"
FOOTER = "Do not merge experiment PRs without Ork review."

BASE_DIGEST = "364bf31ae0cd4eb6a44334a13dd166cb52817ac2bec67b6c03c17ad55656bce0"
EMPTY_PARAMS_DIGEST = "c91003cce2e2e0e5b0921ddfeec43144e7db6e7a45f87f116db53473f63b7a66"
RECORDS_DIGEST = "ca697e83bad58a0c12a21c49eac394ad216d91c495694068660f55733a74c172"
DEMO_DIGEST = "d47b12a05d33f1647fd84e6bc8f0d1a95afbbf67ee2f39add7c549f4cbb7673f"
SWEEP_COUNTS = (
    '{"submit:ADMIT:admitted": 129, "submit:REFUSE:gate_failed": 20, '
    '"submit:REFUSE:not_owner": 29, "submit:REFUSE:slot_taken": 60, '
    '"withdraw:REFUSE:no_live_exception": 69, "withdraw:REFUSE:not_owner": 44, '
    '"withdraw:WITHDRAWN:withdrawn": 49}')
PASSING = [45, 45, 45, 45]

SWEEP_SEED = 1116
SWEEP_RUNS = 40
SWEEP_STEPS = 10
PERM_SEED = 2611
PERM_TRIALS = 30


# ---------------------------------------------------------------- helpers

def _block_mask(subject):
    return [x[0] == subject for x in oe.ITEMS]


def _all_decls():
    return [d for s in oe.SUBJECTS for d in oe.typed_space(s)]


def _pool():
    """For each owner, one clean-evidence submission per typed declaration."""
    pool = {}
    for owner in oe.OWNER_NAMES:
        subs = []
        for d in oe.typed_space(oe.owned_subject(owner)):
            ev = fixtures.evidence_for(d)
            a, b = oe.gate_stats(d, oe.validate_records(ev))
            subs.append({"owner": owner, "declaration": oe.declaration_dict(d),
                         "claimed": {"a": a, "b": b}, "evidence": ev})
        pool[owner] = subs
    return pool


def _oracle_rows(state):
    return [(o, d) for o, d in state.live]


def _oracle_decisions(state):
    return oracle.all_verdicts(_oracle_rows(state))


def _apply(state, op):
    if op[0] == "submit":
        return oe.submit(state, op[1])
    return oe.withdraw(state, op[1], op[2])


def _oracle_verdict(state, op):
    rows = _oracle_rows(state)
    if op[0] == "submit":
        return oracle.judge(rows, op[1])
    return oracle.judge_withdraw(rows, op[1], op[2])


def _sweep():
    """Seeded add/withdraw sequences over all four owners."""
    rng = random.Random(SWEEP_SEED)
    pool = _pool()
    steps = []
    for _run in range(SWEEP_RUNS):
        state = oe.empty_state()
        for _step in range(SWEEP_STEPS):
            owner = rng.choice(oe.OWNER_NAMES)
            r = rng.random()
            if r < 0.55:
                op = ("submit", rng.choice(pool[owner]))
            elif r < 0.85:
                op = ("withdraw", owner, owner)
            elif r < 0.93:
                other = rng.choice([o for o in oe.OWNER_NAMES if o != owner])
                op = ("withdraw", other, owner)
            else:
                other = rng.choice([o for o in oe.OWNER_NAMES if o != owner])
                op = ("submit", dict(rng.choice(pool[other]), owner=owner))
            verdict, after = _apply(state, op)
            steps.append((op, verdict, state, after))
            state = after
    return steps


def _rebuild(live, rng, pool):
    """Admit the given rows into an empty state in a shuffled order."""
    rows = list(live)
    rng.shuffle(rows)
    state = oe.empty_state()
    for owner, decl in rows:
        sub = pool[owner][oe.typed_space(decl[0]).index(decl)]
        v, state = oe.submit(state, sub)
        if v["status"] != oe.ADMIT:
            raise AssertionError("rebuild refused %r" % (v,))
    return state


def _text_files():
    out = []
    for name in sorted(os.listdir(HERE)):
        path = os.path.join(HERE, name)
        if os.path.isfile(path) and not name.endswith(".pyc"):
            out.append(name)
    return out


def _read(name):
    with open(os.path.join(HERE, name), "r", encoding="utf-8") as fh:
        return fh.read()


def _run_case(name):
    byname = {c[0]: c for c in fixtures.CASES}
    state = oe.empty_state()
    for pre in byname[name][1]:
        v, state = _apply(state, byname[pre][2])
    v, after = _apply(state, byname[name][2])
    return state, v, after


# ------------------------------------------------------------- the domain

class DomainTests(unittest.TestCase):

    def test_items_and_typed_space(self):
        self.assertEqual(len(oe.ITEMS), 768)
        self.assertEqual(len(set(oe.ITEMS)), 768)
        self.assertEqual(oe.space_size(), 48)
        for s in oe.SUBJECTS:
            self.assertEqual(len(oe.typed_space(s)), 48)
        self.assertAlmostEqual(math.log2(oe.space_size()), 5.584962500721156)

    def test_every_declaration_is_canonical_and_nonempty(self):
        for s in oe.SUBJECTS:
            regions = [oe.region(d) for d in oe.typed_space(s)]
            self.assertEqual(len(set(regions)), 48)
            for d, r in zip(oe.typed_space(s), regions):
                self.assertTrue(r)
                self.assertEqual(oe.canonical(d), d)
                self.assertTrue(all(oe.ITEMS[i][0] == s for i in r))

    def test_region_counts(self):
        sizes = sorted(len(oe.region(d)) for d in oe.typed_space("s0"))
        self.assertEqual(sum(sizes), 768)
        self.assertEqual((sizes[0], sizes[-1]), (1, 63))
        self.assertEqual(len(oe.region(fixtures.D0)), 36)
        self.assertEqual(len(oe.region(fixtures.D1)), 12)

    def test_base_rule_is_frozen_and_pinned(self):
        state = oe.empty_state()
        self.assertEqual(oe.base_digest(state), BASE_DIGEST)
        self.assertEqual(oe.params_digest(state), EMPTY_PARAMS_DIGEST)
        self.assertEqual(oe.BASE_RULE, (("q1_max", 5), ("q2_max", 5)))
        self.assertIsInstance(oe.BASE_RULE, tuple)
        self.assertIsInstance(oe.BASE_UNITS, tuple)
        self.assertEqual(sum(oe.decisions_compiled(state)), 432)

    def test_compiled_equals_table_and_oracle_per_declaration(self):
        n = 0
        for owner in oe.OWNER_NAMES:
            for d in oe.typed_space(oe.owned_subject(owner)):
                live = ((owner, d),)
                reserved = list(oe.empty_state().reserved)
                k = oe.OWNER_NAMES.index(owner)
                reserved[k] = oe.compile_patch(d)
                st = oe.State(oe.BASE_UNITS, tuple(reserved), live)
                comp = oe.decisions_compiled(st)
                self.assertEqual(comp, oe.decisions_table(live))
                self.assertEqual(comp, oracle.all_verdicts(list(live)))
                n += 1
        self.assertEqual(n, 192)

    def test_patch_support_is_the_owners_unit_only(self):
        for d in _all_decls():
            p = oe.compile_patch(d)
            self.assertEqual(len(p), oe.WIDTH)
            self.assertEqual(p[oe.SUBJECTS.index(d[0])], oe.GATING)
            for j, s in enumerate(oe.SUBJECTS):
                if s != d[0]:
                    self.assertEqual(p[j], 0)
            self.assertTrue(all(type(v) is int for v in p))


# ------------------------------------------------------------------ gate

class GateTests(unittest.TestCase):

    def test_threshold_values(self):
        self.assertIsNone(oe.gate_threshold(0))
        self.assertIsNone(oe.gate_threshold(1))
        self.assertEqual(oe.gate_threshold(10), 4)
        self.assertEqual(oe.gate_threshold(30), 7)
        self.assertEqual(oe.gate_threshold(60), 10)
        for bad in (True, 3.0, float("nan"), float("inf"), -1):
            with self.assertRaises(oe.ConfigError):
                oe.gate_threshold(bad)

    def test_threshold_agrees_with_oracle(self):
        agree = sum(1 for n in range(0, 121)
                    if oe.gate_threshold(n) == oracle.needed(n))
        self.assertEqual(agree, 121)

    def test_gate_stats_agree_with_oracle(self):
        n = 0
        for owner in oe.OWNER_NAMES:
            recs = oe.validate_records(fixtures.RECORDS[owner])
            for d in _all_decls():
                self.assertEqual(oe.gate_stats(d, recs), oracle.tally(d, recs))
                n += 1
        self.assertEqual(n, 768)

    def test_gate_min_binds_for_tiny_regions(self):
        d = ("s0", "a", "sum_cap", 9)  # region is one item
        ev = fixtures.evidence_for(d, reps=4)
        self.assertEqual(oe.gate_stats(d, oe.validate_records(ev)), (4, 0))
        self.assertEqual(oe.gate_threshold(4), 3)
        self.assertEqual(oe.GATE_MIN, 5)
        self.assertFalse(oe.gate_passes(4, 0, 4))  # c(4) is met, GATE_MIN is not
        self.assertTrue(oe.gate_passes(5, 0, 5))
        self.assertTrue(oe.gate_passes(6, 1, 6))
        self.assertFalse(oe.gate_passes(6, 2, 6))
        self.assertTrue(oe.gate_passes(7, 0, 30))
        self.assertFalse(oe.gate_passes(6, 0, 30))
        self.assertFalse(oe.gate_passes(2, 0, 2))
        for reps, want in ((4, "gate_failed"), (5, "admitted")):
            sub = {"owner": "p0", "declaration": oe.declaration_dict(d),
                   "claimed": {"a": reps, "b": 0},
                   "evidence": fixtures.evidence_for(d, reps=reps)}
            v, _ = oe.submit(oe.empty_state(), sub)
            self.assertEqual(v["reason"], want)
            self.assertEqual(oracle.judge([], sub)[1], want)

    def test_behaviour_check_catches_interference(self):
        st = oe.empty_state()
        good = oe.State(st.base, (oe.compile_patch(fixtures.D0),) + st.reserved[1:],
                        (("p0", fixtures.D0),))
        self.assertTrue(oe.behaviour_ok(st, good, fixtures.D0))
        leak = ("s1",) + tuple(fixtures.D0[1:])
        bad = oe.State(st.base, (oe.compile_patch(leak),) + st.reserved[1:],
                       (("p0", fixtures.D0),))
        self.assertFalse(oe.behaviour_ok(st, bad, fixtures.D0))
        self.assertFalse(oe.behaviour_ok(st, st, fixtures.D0))


# --------------------------------------------------------------- learner

class LearnerTests(unittest.TestCase):

    def test_records_world_is_pinned(self):
        blob = json.dumps(fixtures.RECORDS, sort_keys=True).encode("ascii")
        self.assertEqual(hashlib.sha256(blob).hexdigest(), RECORDS_DIGEST)
        for owner in oe.OWNER_NAMES:
            self.assertEqual(len(fixtures.RECORDS[owner]), 30)
            subject = oe.owned_subject(owner)
            for r in fixtures.RECORDS[owner]:
                self.assertEqual(r["item"]["subject"], subject)

    def test_gated_learner_recovers_the_typed_truths(self):
        got = {o: oe.learn(o, fixtures.RECORDS[o]) for o in oe.OWNER_NAMES}
        self.assertEqual(got["p0"]["declaration"], oe.declaration_dict(fixtures.D0))
        self.assertEqual(got["p0"]["claimed"], {"a": 11, "b": 0})
        self.assertEqual(got["p1"]["declaration"], oe.declaration_dict(fixtures.D1))
        self.assertEqual(got["p1"]["claimed"], {"a": 7, "b": 0})
        self.assertIsNone(got["p2"])
        self.assertIsNone(got["p3"])
        self.assertEqual(fixtures.TRUTHS["p0"][1], fixtures.D0)
        self.assertEqual(fixtures.TRUTHS["p1"][1], fixtures.D1)

    def test_search_without_gate_proposes_on_noise_and_is_refused(self):
        free = oe.learn("p2", fixtures.RECORDS["p2"], gated=False)
        self.assertEqual(free["declaration"], oe.declaration_dict(fixtures.D2))
        self.assertEqual(free["claimed"], {"a": 2, "b": 0})
        v, st = oe.submit(oe.empty_state(), free)
        self.assertEqual((v["status"], v["reason"]), ("REFUSE", "gate_failed"))
        self.assertIs(st.live, ())
        self.assertIsNone(oe.learn("p3", fixtures.RECORDS["p3"], gated=False))

    def test_relaxation_is_outside_the_typed_space(self):
        truth = fixtures.truth_bytes()
        rule = oe.decisions_compiled(oe.empty_state())
        self.assertEqual(oe.block_correct(rule, truth, "s3"), 186)
        best = max(oe.block_correct(oe.decisions_table((("p3", d),)), truth, "s3")
                   for d in oe.typed_space("s3"))
        self.assertEqual(best, 185)  # every typed tightening loses an item

    def test_learner_tie_break_prefers_the_narrow_scope(self):
        sub = oe.learn("p1", fixtures.RECORDS["p1"])
        wide = ("s1", "all", "q2_margin", 2)
        recs = oe.validate_records(fixtures.RECORDS["p1"])
        self.assertEqual(oe.gate_stats(wide, recs), oe.gate_stats(fixtures.D1, recs))
        self.assertEqual(sub["declaration"]["scope"], "c")

    def test_learner_validates_inputs(self):
        with self.assertRaises(oe.ConfigError):
            oe.learn(fixtures.SubStr("p0"), fixtures.RECORDS["p0"])
        with self.assertRaises(oe.ConfigError):
            oe.learn("p0", tuple(fixtures.RECORDS["p0"]))
        with self.assertRaises(oe.ConfigError):
            oe.learn("p9", fixtures.RECORDS["p0"])


# ---------------------------------------------------- acceptance and cases

class CaseTests(unittest.TestCase):

    def test_fixture_cases(self):
        self.assertEqual(len(fixtures.CASES), 41)
        for c in fixtures.CASES:
            before, v, after = _run_case(c[0])
            self.assertEqual((v["status"], v["reason"]), (c[3], c[4]), c[0])
            if v["status"] in ("REFUSE", "config_error"):
                self.assertIs(after, before, c[0])
            self.assertEqual(oe.base_digest(after), BASE_DIGEST)

    def test_oracle_agrees_on_cases(self):
        agree = 0
        for c in fixtures.CASES:
            before, v, _ = _run_case(c[0])
            o = _oracle_verdict(before, c[2])
            self.assertEqual(o[0], v["status"], c[0])
            if o[0] != "config_error":
                self.assertEqual(o[1], v["reason"], c[0])
            agree += 1
        self.assertEqual(agree, 41)

    def test_case_kinds(self):
        kinds = {}
        for c in fixtures.CASES:
            kinds[c[3]] = kinds.get(c[3], 0) + 1
        self.assertEqual(kinds, {"ADMIT": 3, "REFUSE": 14, "config_error": 23,
                                 "WITHDRAWN": 1})

    def test_submission_space_agrees_with_oracle(self):
        pool = _pool()
        p0_live = oe.submit(oe.empty_state(), pool["p0"][oe.typed_space("s0").index(fixtures.D0)])[1]
        n = 0
        tally = {}
        for start in (oe.empty_state(), p0_live):
            for owner in oe.OWNER_NAMES + ("p9",):
                for d in _all_decls():
                    ev = fixtures.evidence_for(d)
                    a, b = oe.gate_stats(d, oe.validate_records(ev))
                    decl = oe.declaration_dict(d)
                    variants = (
                        {"owner": owner, "declaration": decl},
                        {"owner": owner, "declaration": decl,
                         "claimed": {"a": a, "b": b}, "evidence": ev},
                        {"owner": owner, "declaration": decl,
                         "claimed": {"a": a + 1, "b": b}, "evidence": ev},
                        {"owner": owner, "declaration": decl,
                         "claimed": {"a": 0, "b": 0}, "evidence": []},
                    )
                    for sub in variants:
                        v, _ = oe.submit(start, sub)
                        o = oracle.judge(_oracle_rows(start), sub)
                        self.assertEqual((v["status"], v["reason"]), o)
                        tally[o] = tally.get(o, 0) + 1
                        n += 1
        self.assertEqual(n, 7680)
        self.assertEqual(tally[("ADMIT", "admitted")], 315)

    def test_validated_snapshot_is_independent_of_later_mutation(self):
        sub = fixtures.CASES[0][2][1]
        sub = json.loads(json.dumps(sub))
        v, st = oe.submit(oe.empty_state(), sub)
        self.assertEqual(v["status"], "ADMIT")
        dec = oe.decisions_compiled(st)
        sub["declaration"]["size"] = 3
        sub["evidence"].clear()
        self.assertEqual(oe.decisions_compiled(st), dec)
        self.assertEqual(st.live, (("p0", fixtures.D0),))

    def test_keys_checked_as_exact_str_before_lookup(self):
        good = oe.declaration_dict(fixtures.D0)
        for key in oe.DECL_KEYS:
            bad = {(fixtures.SubStr(k) if k == key else k): v
                   for k, v in good.items()}
            with self.assertRaises(oe.ConfigError) as cm:
                oe.validate_declaration(bad)
            self.assertEqual(str(cm.exception), "declaration_key_not_str")
        rec = fixtures.RECORDS["p0"][0]
        for key in oe.ITEM_KEYS:
            item = {(fixtures.SubStr(k) if k == key else k): v
                    for k, v in rec["item"].items()}
            with self.assertRaises(oe.ConfigError) as cm:
                oe.validate_item(item)
            self.assertEqual(str(cm.exception), "item_key_not_str")
        for bad in ({1: 0}, {None: 0}):
            with self.assertRaises(oe.ConfigError):
                oe.validate_claimed(bad)

    def test_non_finite_and_bool_values_refused(self):
        for value in (float("nan"), float("inf"), float("-inf"), True, False,
                      fixtures.SubInt(1), 1.0):
            with self.assertRaises(oe.ConfigError):
                oe.validate_item({"subject": "s0", "cls": "a", "q1": value, "q2": 0})
            with self.assertRaises(oe.ConfigError):
                oe.validate_claimed({"a": value, "b": 0})
            with self.assertRaises(oe.ConfigError):
                oe.validate_records([{"item": {"subject": "s0", "cls": "a",
                                               "q1": 0, "q2": 0},
                                      "label": value}])

    def test_dict_subclasses_refused_at_every_level(self):
        good = json.loads(json.dumps(fixtures.CASES[0][2][1]))
        self.assertEqual(oe.submit(oe.empty_state(), good)[0]["status"], "ADMIT")
        variants = []
        s = json.loads(json.dumps(good))
        s["declaration"] = fixtures.SubDict(s["declaration"])
        variants.append((s, "declaration_not_dict"))
        s = json.loads(json.dumps(good))
        s["claimed"] = fixtures.SubDict(s["claimed"])
        variants.append((s, "claimed_not_dict"))
        s = json.loads(json.dumps(good))
        s["evidence"][3] = fixtures.SubDict(s["evidence"][3])
        variants.append((s, "record_not_dict"))
        s = json.loads(json.dumps(good))
        s["evidence"][4]["item"] = fixtures.SubDict(s["evidence"][4]["item"])
        variants.append((s, "item_not_dict"))
        for sub, reason in variants:
            v, _ = oe.submit(oe.empty_state(), sub)
            self.assertEqual((v["status"], v["reason"]), ("config_error", reason))
            self.assertEqual(oracle.judge([], sub)[0], "config_error")

    def test_withdraw_rejects_a_non_state(self):
        v, st = oe.withdraw(("x",), "p0", "p0")
        self.assertEqual(v["status"], "config_error")
        v, st = oe.submit(None, fixtures.CASES[0][2][1])
        self.assertEqual(v["status"], "config_error")


# -------------------------------------------------------------- invariants

class InvariantTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.steps = _sweep()
        cls.pool = _pool()

    def test_sweep_size_and_mix(self):
        counts = {}
        for op, v, _b, _a in self.steps:
            key = op[0] + ":" + v["status"] + ":" + v["reason"]
            counts[key] = counts.get(key, 0) + 1
        self.assertEqual(len(self.steps), SWEEP_RUNS * SWEEP_STEPS)
        self.assertEqual(json.dumps(counts, sort_keys=True), SWEEP_COUNTS)

    def test_i4_base_never_mutated(self):
        for _op, _v, before, after in self.steps:
            self.assertEqual(oe.base_digest(before), BASE_DIGEST)
            self.assertEqual(oe.base_digest(after), BASE_DIGEST)
            self.assertIs(after.base, oe.BASE_UNITS)
        self.assertEqual(oe.BASE_RULE, (("q1_max", 5), ("q2_max", 5)))

    def test_refusals_leave_state_untouched(self):
        n = 0
        for _op, v, before, after in self.steps:
            if v["status"] in ("REFUSE", "config_error"):
                self.assertIs(after, before)
                n += 1
        self.assertGreater(n, 0)

    def test_i1_admission_changes_only_the_owners_block(self):
        n = 0
        for op, v, before, after in self.steps:
            if v["status"] != "ADMIT":
                continue
            owner = op[1]["owner"]
            subject = oe.owned_subject(owner)
            decl = oe.validate_declaration(op[1]["declaration"])
            reg = oe.region(decl)
            d0 = oe.decisions_compiled(before)
            d1 = oe.decisions_compiled(after)
            for i, inside in enumerate(_block_mask(subject)):
                if not inside:
                    self.assertEqual(d1[i], d0[i])
                else:
                    self.assertEqual(d1[i], 0 if i in reg else d0[i])
            n += 1
        self.assertEqual(n, 129)

    def test_i1_with_and_without_each_live_exception(self):
        n = 0
        for _op, _v, _before, after in self.steps:
            dec = oe.decisions_compiled(after)
            for owner, decl in after.live:
                v, without = oe.withdraw(after, owner, owner)
                self.assertEqual(v["status"], "WITHDRAWN")
                dw = oe.decisions_compiled(without)
                subject = oe.owned_subject(owner)
                for i, inside in enumerate(_block_mask(subject)):
                    if not inside:
                        self.assertEqual(dec[i], dw[i])
                n += 1
        self.assertEqual(n, 634)

    def test_i2_withdrawal_restores_exactly(self):
        rng = random.Random(SWEEP_SEED + 1)
        n_undo = 0
        n_rebuild = 0
        prev = None
        for op, v, before, after in self.steps:
            if v["status"] == "WITHDRAWN":
                rebuilt = _rebuild(after.live, rng, self.pool)
                self.assertEqual(rebuilt, after)
                self.assertEqual(oe.params_digest(rebuilt), oe.params_digest(after))
                n_rebuild += 1
                if (prev is not None and prev[1]["status"] == "ADMIT"
                        and prev[0][1]["owner"] == op[2] and prev[3] is before):
                    self.assertEqual(after, prev[2])
                    self.assertEqual(oe.decisions_compiled(after),
                                     oe.decisions_compiled(prev[2]))
                    n_undo += 1
                if not after.live:
                    self.assertEqual(oe.params_digest(after), EMPTY_PARAMS_DIGEST)
            prev = (op, v, before, after)
        self.assertEqual(n_rebuild, 49)
        self.assertEqual(n_undo, 11)

    def test_table_compiled_and_oracle_agree_on_every_state(self):
        n = 0
        for _op, _v, _before, after in self.steps:
            comp = oe.decisions_compiled(after)
            self.assertEqual(comp, oe.decisions_table(after.live))
            self.assertEqual(comp, _oracle_decisions(after))
            n += 1
        self.assertEqual(n, SWEEP_RUNS * SWEEP_STEPS)

    def test_oracle_helper_reads_rows_not_weights(self):
        st = oe.empty_state()
        forged = oe.State(st.base, st.reserved, (("p0", fixtures.D0),))
        self.assertNotEqual(_oracle_decisions(forged), oe.decisions_compiled(forged))
        self.assertEqual(_oracle_decisions(forged), oe.decisions_table(forged.live))

    def test_sweep_verdicts_agree_with_oracle(self):
        for op, v, before, _after in self.steps:
            o = _oracle_verdict(before, op)
            self.assertEqual((v["status"], v["reason"]), o)


class PermutationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pool = _pool()
        cls.passing = {o: [s for s in pool[o] if oe.submit(
            oe.empty_state(), s)[0]["status"] == "ADMIT"]
            for o in oe.OWNER_NAMES}

    def test_admission_order_does_not_matter(self):
        rng = random.Random(PERM_SEED)
        passing = self.passing
        self.assertEqual([len(passing[o]) for o in oe.OWNER_NAMES], PASSING)
        orders = 0
        for _ in range(PERM_TRIALS):
            k = rng.choice((2, 3, 4))
            owners = rng.sample(oe.OWNER_NAMES, k)
            subs = [rng.choice(passing[o]) for o in owners]
            ref = None
            for perm in itertools.permutations(subs):
                st = oe.empty_state()
                for s in perm:
                    v, st = oe.submit(st, s)
                    self.assertEqual(v["status"], "ADMIT")
                if ref is None:
                    ref = st
                    ref_dec = oe.decisions_compiled(st)
                self.assertEqual(st, ref)
                self.assertEqual(oe.params_digest(st), oe.params_digest(ref))
                orders += 1
            self.assertEqual(ref_dec, oracle.all_verdicts(_oracle_rows(ref)))
        self.assertEqual(orders, 302)

    def test_interleaved_add_withdraw_returns_bit_identical(self):
        rng = random.Random(PERM_SEED + 1)
        passing = self.passing
        for _ in range(PERM_TRIALS):
            subs = {o: rng.choice(passing[o]) for o in oe.OWNER_NAMES}
            st = oe.empty_state()
            for o in oe.OWNER_NAMES:
                st = oe.submit(st, subs[o])[1]
            full = st
            gone = rng.sample(oe.OWNER_NAMES, rng.choice((1, 2, 3)))
            for o in gone:
                st = oe.withdraw(st, o, o)[1]
            middle = st
            back = list(gone)
            rng.shuffle(back)
            for o in back:
                st = oe.submit(st, subs[o])[1]
            self.assertEqual(st, full)
            self.assertEqual(oe.decisions_compiled(st), oe.decisions_compiled(full))
            for o in oe.OWNER_NAMES:
                st = oe.withdraw(st, o, o)[1]
            self.assertEqual(st, oe.empty_state())
            self.assertEqual(oe.params_digest(st), EMPTY_PARAMS_DIGEST)
            self.assertEqual(len(middle.live), 4 - len(gone))


# ------------------------------------------------------------- baselines

class BaselineTests(unittest.TestCase):

    def test_global_rule_edit_interferes_where_owned_does_not(self):
        rule = oe.decisions_compiled(oe.empty_state())
        g = oe.decisions_global_edit(fixtures.D0)
        self.assertEqual(oe.changed_outside(rule, g, "s0"), 108)
        owned = oe.decisions_table((("p0", fixtures.D0),))
        self.assertEqual(oe.changed_outside(rule, owned, "s0"), 0)
        self.assertEqual(sum(1 for i in range(768) if owned[i] != rule[i]), 36)

    def test_demo_is_deterministic(self):
        text = demo.render()
        self.assertEqual(text, demo.render())
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(),
                         DEMO_DIGEST)
        facts = demo.run()[1]
        self.assertTrue(facts["table_equals_compiled"])
        self.assertTrue(facts["withdraw_equals_never_added"])
        self.assertTrue(facts["base_unchanged"])
        self.assertEqual(facts["owned_non_owner_changes"], 0)
        self.assertEqual(facts["global_edit_non_owner_changes"], 108)
        self.assertEqual(oe.paper_results()["status"], "on_unmeasured")


# --------------------------------------------------------------- hygiene

def _banned():
    return ["al" + "low", "ke" + "ep", "Cloud" + "Agent", "Sm" + "ith",
            "Che" + "cker"]


def _scan_text(text):
    words = [w.lower() for w in _banned()]
    paths = ["/work" + "space", "/t" + "mp", "/ho" + "me"]
    low = text.lower()
    return [w for w in words + paths if w in low]


def _scan(names):
    return [(name, w) for name in names for w in _scan_text(_read(name))]


class HygieneTests(unittest.TestCase):

    def test_expected_files(self):
        names = _text_files()
        for need in ("NOTICE", "README.md", "demo.py", "fixtures.py",
                     "mutants.py", "oracle.py", "owned_exceptions.py",
                     "paper_evidence.json", "test_owned_exceptions.py"):
            self.assertIn(need, names)

    def test_no_banned_words_or_paths(self):
        names = _text_files()
        self.assertGreaterEqual(len(names), 9)
        self.assertEqual(_scan(names), [])

    def test_scan_catches_planted_words(self):
        self.assertEqual(len(_banned()), 5)
        for w in _banned():
            self.assertEqual(_scan_text("x " + w.upper() + " y"), [w.lower()])
        self.assertEqual(len(_scan_text("/Work" + "space/x /t" + "mp/y /ho" + "me/z")), 3)
        self.assertEqual(_scan_text("plain text"), [])

    def test_no_dynamic_code_or_processes(self):
        bad = ["ex" + "ec(", "ev" + "al(", "sub" + "process", "os." + "system",
               "__im" + "port__", "soc" + "ket", "url" + "lib"]
        for name in ("owned_exceptions.py", "oracle.py", "demo.py",
                     "fixtures.py", "test_owned_exceptions.py"):
            text = _read(name)
            for b in bad:
                self.assertNotIn(b, text, name)

    def test_oracle_is_independent(self):
        text = _read("oracle.py")
        imports = [l for l in text.splitlines()
                   if l.startswith("import ") or l.startswith("from ")]
        self.assertEqual(imports, ["from fractions import Fraction"])
        mod_names = {n for n in dir(oe) if callable(getattr(oe, n))
                     and not n.startswith("__")}
        orc_names = {n for n in dir(oracle) if callable(getattr(oracle, n))
                     and not n.startswith("__")}
        self.assertEqual(mod_names & orc_names, {"Fraction"})

    def test_paper_numbers_only_in_evidence(self):
        nums = ["96" + ".6", "91" + ".7", "84" + ".0", "5" + ".4", "3" + ".1"]
        for name in _text_files():
            if name == "paper_evidence.json":
                continue
            text = _read(name)
            for n in nums:
                self.assertNotIn(n, text, name)

    def test_paper_evidence(self):
        ev = json.loads(_read("paper_evidence.json"))
        abstract = ev["abstract"]["text"]
        self.assertEqual(hashlib.sha256(abstract.encode("utf-8")).hexdigest(),
                         ev["abstract"]["sha256"])
        self.assertEqual(len(abstract), ev["abstract"]["chars"])
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertGreaterEqual(len(ev["claims"]), 6)
        for c in ev["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")
            self.assertEqual(c["measured_here"], "on_unmeasured")
            q = c["quote"]
            self.assertEqual(abstract[c["offset"]:c["offset"] + c["length"]], q)
            self.assertEqual(len(q), c["length"])

    def test_day_readme_row(self):
        parent = os.path.dirname(HERE)
        if os.path.basename(parent) != "2026-11-16":
            self.skipTest("not in the experiments/2026-11-16 layout")
        with open(os.path.join(parent, "README.md"), "r", encoding="utf-8") as fh:
            text = fh.read()
        rows = [l for l in text.splitlines() if l.startswith("- [" + SLUG + "]")]
        self.assertEqual(len(rows), 1)
        self.assertEqual(text.count(FOOTER), 1)
        self.assertTrue(text.endswith(FOOTER + "\n"))
        self.assertTrue(text.startswith("# experiments/2026-11-16\n"))
        self.assertIn("2611.15917", rows[0])


if __name__ == "__main__":
    unittest.main()
