"""Tests for the w20-checkable-rulebook method sketch (stdlib unittest).

Run: python3 -m unittest test_rulebook.py -v
Test class names carry the done-when letter (DoneWhenA ... DoneWhenE).
WorldShape pins the shape of the test worlds themselves (long prefixes,
duplicate ids, disguised declarations, near-miss tokens, parity rows), so a
change that thins a world fails here even when no behaviour test notices.
The w14 comparison loads experiments/2026-11-05/w14-silence-expiry from beside
this repo layout (or $W14_SILENCE_EXPIRY) and is skipped when it is absent.
The source checks read the lab copy named in paper_evidence.json from
$W20CRB_SOURCES and are skipped when it is unset or the file is absent.
"""

import ast
import enum
import hashlib
import importlib
import json
import os
import re
import sys
import unittest

import rulebook as R
import fixtures as F

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W20CRB_SOURCES")  # env only, no default path; source checks skip when unset
W14 = os.environ.get("W14_SILENCE_EXPIRY", os.path.join(HERE, "..", "..", "2026-11-05", "w14-silence-expiry"))
CODE = ("rulebook.py", "fixtures.py")
DOCS = ("README.md", "NOTICE")
ALL = DOCS + CODE + ("test_rulebook.py", "mutants.py", "paper_evidence.json")
PERMIT = "al" + "low"


class StrSub(str):
    """A plain str subclass."""


class LyingStr(str):
    """Value is one word, str() reports another."""

    def __str__(self):
        return "hold"


class LyingLower(str):
    """Value is one word, str() and lower() report another."""

    def __str__(self):
        return "hold"

    def lower(self):
        return "hold"


class StrEnum(str, enum.Enum):
    HOLD = "hold"


# on_expiry values that are not an exact str. The mirror refuses every one
# (config_error); w14 on main resolves some of them (see W14_ON_DISGUISED).
DISGUISED = (
    ("lying_str_permit", LyingStr(PERMIT)),
    ("lying_lower_permit", LyingLower(PERMIT)),
    ("lying_str_permit_upper", LyingStr(PERMIT.upper())),
    ("subclass_hold", StrSub("hold")),
    ("subclass_hold_upper", StrSub("HOLD")),
    ("subclass_deny", StrSub("deny")),
    ("str_enum_hold", StrEnum.HOLD),
)
# What w14 on main (ee75ded1) returns for each, read from the live package.
W14_ON_DISGUISED = {
    "lying_str_permit": R.CONFIG_ERROR,
    "lying_lower_permit": R.HELD,
    "lying_str_permit_upper": R.CONFIG_ERROR,
    "subclass_hold": R.HELD,
    "subclass_hold_upper": R.HELD,
    "subclass_deny": R.DENIED_ON_TIMEOUT,
    "str_enum_hold": R.CONFIG_ERROR,
}

_HI = {F.TOOL: {"risk": "high", "safe_fallback": "dry_run"}, "dry_run": {"risk": "read_only"}}
# Rules and action sets outside the w14 grid: (name, rule body, actions,
# mirror result, w14 result). A w14 result "raises X" means the w14 loader or
# engine raises X, not its ConfigError; the mirror reports config_error there.
PARITY = (
    ("requires_approval_string_false", dict(F.rule(R.HOLD), requires_approval="false"), F.ACTIONS, R.HELD, R.HELD),
    ("requires_approval_zero_string", dict(F.rule(R.HOLD), requires_approval="0"), F.ACTIONS, R.HELD, R.HELD),
    ("quorum_string_fraction", dict(F.rule(R.HOLD), quorum="2.5"), F.ACTIONS, R.CONFIG_ERROR, "raises ValueError"),
    ("quorum_float_two", dict(F.rule(R.HOLD), quorum=2.0), F.ACTIONS, R.HELD, R.HELD),
    ("quorum_inf", dict(F.rule(R.HOLD), quorum=float("inf")), F.ACTIONS, R.CONFIG_ERROR, "raises OverflowError"),
    ("deadline_inf", F.rule(R.HOLD, deadline_s=float("inf")), F.ACTIONS, R.CONFIG_ERROR, "raises OverflowError"),
    ("deadline_nan", F.rule(R.HOLD, deadline_s=float("nan")), F.ACTIONS, R.CONFIG_ERROR, "raises ValueError"),
    ("deadline_word", F.rule(R.HOLD, deadline_s="x"), F.ACTIONS, R.CONFIG_ERROR, "raises ValueError"),
    ("ladder_none", dict(F.rule(R.HOLD), ladder=None), F.ACTIONS, R.CONFIG_ERROR, "raises TypeError"),
    ("missing_risk", F.rule(R.SAFE_FALLBACK), {F.TOOL: {"safe_fallback": "dry_run"}, "dry_run": {"risk": "low"}},
     R.CONFIG_ERROR, "raises KeyError"),
    ("unhashable_fallback", F.rule(R.SAFE_FALLBACK),
     {F.TOOL: {"risk": "high", "safe_fallback": ["dry_run"]}, "dry_run": {"risk": "low"}},
     R.CONFIG_ERROR, "raises TypeError"),
    ("unhashable_fallback_elsewhere", F.rule(R.SAFE_FALLBACK),
     dict(_HI, other={"risk": "high", "safe_fallback": ["dry_run"]}), R.CONFIG_ERROR, "raises TypeError"),
    ("number_fallback_elsewhere", F.rule(R.SAFE_FALLBACK),
     dict(_HI, other={"risk": "high", "safe_fallback": 5}), R.FELL_BACK, R.FELL_BACK),
)


def w14_outcome(se, policy, body, actions):
    """Terminal state of w14 on main for one rule, config_error for its
    ConfigError, "raises X" for any other exception."""
    try:
        eng = se.EscalationEngine(se.load_policy({"rules": {"high": body}}), actions)
        esc = eng.propose("a1", F.TOOL, "high", 0)
        now = 0
        while esc.terminal is None:
            now += esc.rule.deadline_s
            eng.tick(now)
        return esc.terminal.value, tuple(e["kind"] for e in eng.journal.entries)
    except policy.ConfigError:
        return R.CONFIG_ERROR, ()
    except Exception as exc:  # recorded, compared with the table
        return "raises " + type(exc).__name__, ()


def load_w14():
    sys.path.insert(0, os.path.abspath(W14))
    try:
        return importlib.import_module("silence_expiry"), importlib.import_module("silence_expiry.policy")
    finally:
        sys.path.pop(0)


HAVE_W14 = os.path.isdir(os.path.join(W14, "silence_expiry"))


def lenient_build(programs, gate, n):
    """A list builder that does not refuse shared ids: one certificate per
    program whose prefix is SCOPED. Used to show the duplicate worlds bite."""
    out = []
    for p in programs:
        v = R.evaluate(p, gate, n)
        if v.status == R.SCOPED:
            out.append(v.certificate)
    return tuple(out)


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def design(name):
    return next(c for c in F.DESIGN if c[0] == name)


class Fixtures(unittest.TestCase):
    def test_design_and_universe_reports(self):
        lines = []
        fd, nd = F.check_design(out=lines.append)
        fu, nu = F.check_universes(out=lines.append)
        fn, nn = F.check_near_miss(out=lines.append)
        self.assertEqual((fd, fu, fn), (0, 0, 0), "\n".join(lines))
        self.assertEqual((nd, nu, nn), (len(F.DESIGN), 1 + len(F.REGRESSION) + 2 * len(F.DUPLICATE), len(F.NEAR_MISS)))


class DoneWhenA(unittest.TestCase):
    """(a) a violation in the trace prefix is refused."""

    def test_a_violation_in_prefix_is_refused(self):
        for name in ("violation_in_prefix", "violation_first_step", "violation_in_cycle", "violation_beats_answer"):
            _, p, n, (_, at, _, _, _) = design(name)
            v = R.evaluate(p, F.gate(), n)
            with self.subTest(name=name):
                self.assertEqual((v.status, v.violation_at, v.certificate), (R.REFUSE, at, None))

    def test_a_every_position_and_every_forbidden_event(self):
        for bad in F.FORBIDDEN:
            for k in range(7):
                p = F.prog("p", ("work",) * k + (bad,) + ("answer",))
                for n in range(k + 1, k + 4):
                    v = R.evaluate(p, F.gate(), n)
                    with self.subTest(bad=bad, k=k, n=n):
                        self.assertEqual((v.status, v.violation_at), (R.REFUSE, k))
                self.assertNotEqual(R.evaluate(p, F.gate(), k).status, R.REFUSE)

    def test_a_refuse_wins_over_every_claim(self):
        _, p, n, _ = design("violation_in_prefix")
        for claim in R.CLAIMS:
            self.assertEqual(R.certify(p, F.gate(), n, claim).status, R.REFUSE)


class DoneWhenB(unittest.TestCase):
    """(b) a clean prefix earns clean_through=n only; never/eventually are UNSETTLED."""

    def test_b_clean_prefix_gets_a_scoped_certificate(self):
        _, p, n, _ = design("clean_answered")
        v = R.certify(p, F.gate(), n, R.CLEAN_THROUGH)
        self.assertEqual((v.status, v.certificate), (R.SCOPED, R.Certificate(p.program_id, n, 1)))
        self.assertTrue(R.check_certificate(p, F.gate(), v.certificate))

    def test_b_never_and_eventually_are_unsettled_on_any_clean_prefix(self):
        # Every n from 0 to LONG_PREFIX, on hand-written and random clean
        # programs; WorldShape pins LONG_PREFIX against the program lengths.
        g = F.gate()
        bad = []
        for p in F.LONG_PROGRAMS:
            for n in range(0, F.LONG_PREFIX + 1):
                for claim in (R.NEVER, R.EVENTUALLY):
                    v = R.certify(p, g, n, claim)
                    if (v.status, v.certificate) != (R.UNSETTLED, None):
                        bad.append((p.program_id, n, claim, v.status))
        self.assertEqual(bad, [])

    def test_b_late_violators_stay_unsettled_then_refuse(self):
        g = F.gate()
        for p, at in F.LATE_VIOLATORS:
            for n in sorted(set(range(0, at + 3)) & set(range(0, F.LONG_PREFIX + 1)) | {at, at + 1}):
                for claim in (R.NEVER, R.EVENTUALLY):
                    v = R.certify(p, g, n, claim)
                    exp = (R.UNSETTLED, None) if n <= at else (R.REFUSE, at)
                    with self.subTest(p=p.program_id, n=n, claim=claim):
                        self.assertEqual((v.status, v.violation_at if n > at else None), exp)
                        self.assertIsNone(v.certificate)
            c = R.certify(p, g, at, R.CLEAN_THROUGH).certificate
            self.assertEqual(c.clean_through, at)
            self.assertTrue(R.check_certificate(p, g, c))
            self.assertFalse(R.check_certificate(p, g, R.Certificate(p.program_id, at + 1, c.answered_at)))

    def test_b_violation_at_n_plus_one_flips_and_old_certificate_stays_true(self):
        _, p, n, _ = design("clean_then_violation_next")
        cert = R.evaluate(p, F.gate(), n).certificate
        self.assertEqual(cert.clean_through, n)
        v = R.evaluate(p, F.gate(), n + 1)
        self.assertEqual((v.status, v.violation_at), (R.REFUSE, n))
        self.assertTrue(R.check_certificate(p, F.gate(), cert))
        self.assertFalse(R.check_certificate(p, F.gate(), R.Certificate(p.program_id, n + 1, cert.answered_at)))

    def test_b_certificates_cannot_be_stretched_or_moved(self):
        _, p, n, _ = design("clean_answered")
        g = F.gate()
        good = R.evaluate(p, g, n).certificate
        for bad in (R.Certificate("other", n, 1), R.Certificate(p.program_id, n, 0),
                    R.Certificate(p.program_id, n, 3), R.Certificate(p.program_id, n, -1),
                    R.Certificate(p.program_id, n, True), R.Certificate(p.program_id, -1, 1), (p.program_id, n, 1)):
            with self.subTest(bad=bad):
                self.assertFalse(R.check_certificate(p, g, bad))
        self.assertTrue(R.check_certificate(p, g, good))
        twice = F.prog("t", ("answer", "work", "answer"))
        self.assertTrue(R.check_certificate(twice, g, R.Certificate("t", 3, 0)))
        self.assertFalse(R.check_certificate(twice, g, R.Certificate("t", 3, 2)))

    def test_b_clean_through_without_an_answer(self):
        p = F.prog("q", ("work", "wait"))
        v = R.certify(p, F.gate(), 2, R.CLEAN_THROUGH)
        self.assertEqual(v.certificate, R.Certificate("q", 2, -1))
        self.assertTrue(R.check_certificate(p, F.gate(), v.certificate))


class DoneWhenC(unittest.TestCase):
    """(c) no answer in the prefix: UNSETTLED, then the declared on_expiry (w14 contract)."""

    def unanswered(self, g):
        return R.evaluate(F.prog("p6", ("work", "wait")), g, 6)

    def test_c_each_declaration(self):
        no_fb = {F.TOOL: {"risk": "high"}}
        cases = [
            (F.gate(R.DENY), R.DENIED_ON_TIMEOUT, (R.J_RAISED, R.J_EXPIRED, R.J_DENIED)),
            (F.gate(R.HOLD), R.HELD, (R.J_RAISED, R.J_EXPIRED, R.J_HELD)),
            (F.gate(R.ESCALATE), R.EXHAUSTED, (R.J_RAISED, R.J_EXPIRED, R.J_TIER, R.J_EXPIRED, R.J_EXHAUSTED)),
            (F.gate(R.SAFE_FALLBACK), R.FELL_BACK, (R.J_RAISED, R.J_EXPIRED, R.J_FALLBACK)),
            (F.gate(R.SAFE_FALLBACK, actions=no_fb), R.DENIED_ON_TIMEOUT, (R.J_RAISED, R.J_EXPIRED, R.J_DENIED)),
        ]
        for g, terminal, journal in cases:
            v = self.unanswered(g)
            with self.subTest(oe=g.expiry_rule["on_expiry"], actions=g.actions):
                self.assertEqual((v.status, v.expiry, v.journal, v.certificate), (R.UNSETTLED, terminal, journal, None))

    def test_c_missing_or_permit_or_unknown_is_config_error_before_anything_runs(self):
        for oe in (None, PERMIT, PERMIT.upper(), PERMIT.title(), "proceed", "approved", "", " hold", 0, "denied"):
            g = F.gate(oe)
            for name in ("violation_in_prefix", "clean_answered", "no_answer_hold"):
                _, p, n, _ = design(name)
                with self.subTest(oe=oe, name=name):
                    self.assertEqual(R.evaluate(p, g, n).status, R.CONFIG_ERROR)
            self.assertIsNone(R.build_list((F.prog("x", ("answer",)),), g, 2))
            self.assertIsNone(R.build_list((), g, 2))

    def test_c_declaration_must_be_an_exact_str(self):
        _, p, n, _ = design("clean_answered")
        for name, oe in DISGUISED:
            g = F.gate(oe)
            with self.subTest(name=name):
                self.assertEqual(R.expire(g.expiry_rule, F.TOOL, F.ACTIONS), (R.CONFIG_ERROR, ()))
                self.assertEqual(R.evaluate(p, g, n).status, R.CONFIG_ERROR)
                self.assertEqual(R.evaluate(F.prog("q", ("work",)), g, 2).status, R.CONFIG_ERROR)
                self.assertIsNone(R.build_list((p,), g, n))

    def test_c_rules_outside_the_grid(self):
        for name, body, actions, mirror, _ in PARITY:
            with self.subTest(name=name):
                self.assertEqual(R.expire(body, F.TOOL, actions)[0], mirror)
                g = R.Gate(F.FORBIDDEN, F.ANSWER, body, F.TOOL, actions)
                status = R.evaluate(F.prog("q", ("work",)), g, 2).status
                self.assertEqual(status, R.CONFIG_ERROR if mirror == R.CONFIG_ERROR else R.UNSETTLED)

    @unittest.skipUnless(HAVE_W14, "w14-silence-expiry not beside this folder")
    def test_c_w14_on_disguised_declarations_and_rules_outside_the_grid(self):
        se, policy = load_w14()
        for name, oe in DISGUISED:
            with self.subTest(name=name):
                self.assertEqual(w14_outcome(se, policy, F.rule(oe), F.ACTIONS)[0], W14_ON_DISGUISED[name])
        for name, body, actions, mirror, w14 in PARITY:
            live = w14_outcome(se, policy, json.loads(json.dumps(body)) if "inf" not in name and "nan" not in name
                               else dict(body), actions)
            with self.subTest(name=name):
                self.assertEqual(live[0], w14)
                if not w14.startswith("raises "):
                    self.assertEqual(R.expire(body, F.TOOL, actions), live)

    def test_c_w14_lowercases_the_declaration(self):
        for oe, terminal in (("HOLD", R.HELD), ("Deny", R.DENIED_ON_TIMEOUT), ("ESCALATE", R.EXHAUSTED)):
            self.assertEqual(self.unanswered(F.gate(oe)).expiry, terminal)

    def test_c_matches_w14_documented_behaviour(self):
        # Statements from the w14-silence-expiry README on main.
        ok = F.rule(R.HOLD)
        doc = [
            ("missing on_expiry is a ConfigError", F.rule(None), F.ACTIONS, R.CONFIG_ERROR),
            ("the permit word is a ConfigError", F.rule(PERMIT.upper()), F.ACTIONS, R.CONFIG_ERROR),
            ("unknown rule keys are a ConfigError", dict(ok, requires_aproval=True), F.ACTIONS, R.CONFIG_ERROR),
            ("requires_approval defaults true", ok, F.ACTIONS, R.HELD),
            ("an ungated rule is refused at propose", dict(ok, requires_approval=False), F.ACTIONS, R.CONFIG_ERROR),
            ("quorum at least 1", dict(ok, quorum=0), F.ACTIONS, R.CONFIG_ERROR),
            ("empty ladder", F.rule(R.HOLD, ladder=()), F.ACTIONS, R.CONFIG_ERROR),
            ("deadline must be positive (w14 policy.py)", F.rule(R.HOLD, deadline_s=0), F.ACTIONS, R.CONFIG_ERROR),
            ("fallback must be registered", F.rule(R.SAFE_FALLBACK),
             {F.TOOL: {"risk": "high", "safe_fallback": "gone"}}, R.CONFIG_ERROR),
            ("fallback must not be the same tool", F.rule(R.SAFE_FALLBACK),
             {F.TOOL: {"risk": "high", "safe_fallback": F.TOOL}}, R.CONFIG_ERROR),
            ("fallback must be strictly lower risk", F.rule(R.SAFE_FALLBACK),
             {F.TOOL: {"risk": "high", "safe_fallback": "dry_run"}, "dry_run": {"risk": "high"}}, R.CONFIG_ERROR),
            ("quorum the ladder cannot meet (w14 policy.py)", dict(F.rule(R.HOLD, ladder=("a",)), quorum=2),
             F.ACTIONS, R.CONFIG_ERROR),
            ("unknown risk level (w14 actions.py)", F.rule(R.SAFE_FALLBACK),
             {F.TOOL: {"risk": "high", "safe_fallback": "dry_run"}, "dry_run": {"risk": "unknown"}}, R.CONFIG_ERROR),
            ("valid fallback falls back on timeout", F.rule(R.SAFE_FALLBACK), F.ACTIONS, R.FELL_BACK),
            ("escalate climbs the ladder to exhaustion", F.rule(R.ESCALATE, ladder=("a", "b", "c")), F.ACTIONS,
             R.EXHAUSTED),
        ]
        for what, body, actions, terminal in doc:
            with self.subTest(what=what):
                self.assertEqual(R.expire(body, F.TOOL, actions)[0], terminal)
        j = R.expire(F.rule(R.ESCALATE, ladder=("a", "b", "c")), F.TOOL, F.ACTIONS)[1]
        self.assertEqual(j.count(R.J_TIER), 2)
        self.assertEqual(j.count(R.J_EXPIRED), 3)
        for _, body, actions, _ in doc:
            self.assertNotIn("approved", R.expire(body, F.TOOL, actions)[1])

    def grid(self):
        values = (None, "deny", "DENY", "Hold", "safe_fallback", "escalate", "Escalate", PERMIT, PERMIT.upper(),
                  "proceed", "", " deny", 0)
        action_sets = (
            F.ACTIONS,
            {F.TOOL: {"risk": "high"}},
            {F.TOOL: {"risk": "high", "safe_fallback": "gone"}},
            {F.TOOL: {"risk": "high", "safe_fallback": F.TOOL}},
            {F.TOOL: {"risk": "low", "safe_fallback": "dry_run"}, "dry_run": {"risk": "medium"}},
            {F.TOOL: {"risk": "high", "safe_fallback": "dry_run"}, "dry_run": {"risk": "unknown"}},
            {F.TOOL: {"risk": "high"}, "other": {"risk": "odd", "safe_fallback": F.TOOL}},
        )
        extras = ({}, {"quorum": 2}, {"quorum": 3}, {"requires_approval": False}, {"colour": "red"},
                  {"deadline_seconds": 30})
        for oe in values:
            for ladder in (("oncall",), ("oncall", "lead", "exec"), ()):
                for deadline in (60, 0):
                    for actions in action_sets:
                        for extra in extras:
                            body = F.rule(oe, ladder=ladder, deadline_s=deadline, **extra)
                            if "deadline_seconds" in extra:
                                del body["deadline_s"]
                            yield body, actions

    @unittest.skipUnless(HAVE_W14, "w14-silence-expiry not beside this folder")
    def test_c_matches_the_w14_package(self):
        se, policy = load_w14()
        n = 0
        for body, actions in self.grid():
            live = w14_outcome(se, policy, json.loads(json.dumps(body)), actions)
            with self.subTest(body=body, actions=actions):
                self.assertEqual(R.expire(body, F.TOOL, actions), live)
            n += 1
        self.assertGreater(n, 1000)


class DoneWhenD(unittest.TestCase):
    """(d) the list holds every must-admit program and no must-refuse program."""

    UNIVERSES = [F.design_universe()] + F.REGRESSION

    def test_d_every_must_admit_and_no_must_refuse(self):
        for name, progs, h in self.UNIVERSES:
            misses, intrusions, _ = F.check_universe(name, progs, h)
            with self.subTest(universe=name):
                self.assertEqual((misses, intrusions), ([], []))

    def test_d_every_label_present(self):
        for name, progs, h in self.UNIVERSES:
            labels = {F.label(p, h) for p in progs}
            with self.subTest(universe=name):
                self.assertEqual(labels, {F.MUST_ADMIT, F.MUST_REFUSE, F.UNDETERMINED})

    def test_d_labels_are_decided_without_the_gate(self):
        tree = ast.parse(read("fixtures.py"))
        for fn in (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("label", "first_at",
                                                                                          "truly_compliant")):
            for node in ast.walk(fn):
                with self.subTest(fn=fn.name):
                    self.assertFalse(isinstance(node, ast.Name) and node.id == "R")

    def test_d_every_entry_is_checkable(self):
        for name, progs, h in self.UNIVERSES:
            lst = R.build_list(progs, F.gate(), h)
            byid = {p.program_id: p for p in progs}
            for c in lst:
                with self.subTest(universe=name, pid=c.program_id):
                    self.assertTrue(R.check_certificate(byid[c.program_id], F.gate(), c))
                    self.assertEqual(c.clean_through, h)

    def test_d_undetermined_fall_both_ways(self):
        listed = unlisted = 0
        for name, progs, h in self.UNIVERSES:
            ids = {c.program_id for c in R.build_list(progs, F.gate(), h)}
            for p in progs:
                if F.label(p, h) == F.UNDETERMINED:
                    if p.program_id in ids:
                        listed += 1
                        # Listed undetermined programs are late violators: the one-sided failure.
                        self.assertIsNotNone(F.first_at(p, F.FORBIDDEN))
                    else:
                        unlisted += 1
        self.assertGreater(listed, 0)
        self.assertGreater(unlisted, 0)

    def test_d_each_universe_lists_a_late_violator(self):
        # The one-sided limit shows up in every universe, not only in total.
        for name, progs, h in self.UNIVERSES:
            ids = {c.program_id for c in R.build_list(progs, F.gate(), h)}
            late = [p for p in progs if p.program_id in ids and F.first_at(p, F.FORBIDDEN) is not None]
            with self.subTest(universe=name):
                self.assertTrue(late)

    def test_d_listed_violators_get_only_the_horizon(self):
        # Against the infinite trace: a listed program that ever violates is
        # given clean_through=h, which is at or before its first violation,
        # and never more; a standing never claim on it stays unsettled.
        seen = 0
        for name, progs, h in self.UNIVERSES:
            byid = {p.program_id: p for p in progs}
            for c in R.build_list(progs, F.gate(), h):
                p = byid[c.program_id]
                bad = F.first_at(p, F.FORBIDDEN)
                if bad is None:
                    continue
                seen += 1
                with self.subTest(universe=name, pid=c.program_id):
                    self.assertEqual(c.clean_through, h)
                    self.assertLessEqual(c.clean_through, bad)
                    self.assertFalse(R.check_certificate(p, F.gate(), R.Certificate(p.program_id, bad + 1,
                                                                                     c.answered_at)))
                    self.assertEqual(R.certify(p, F.gate(), h, R.NEVER).status, R.UNSETTLED)
        self.assertGreater(seen, 0)

    def test_d_duplicate_ids_refused_in_both_orders(self):
        clean, bad = F.prog("x", ("answer",)), F.prog("x", ("leak", "answer"))
        for progs in ((clean, bad), (bad, clean), (clean, clean), (clean, F.prog("y", ("answer",)), bad)):
            with self.subTest(order=[p.stem for p in progs]):
                self.assertIsNone(R.build_list(progs, F.gate(), 3))
                misses, intrusions, counts = F.check_universe("dup", progs, 3)
                self.assertEqual((intrusions, counts["rejected"]), ([], 1))
        self.assertEqual(R.build_list((clean, F.prog("y", ("answer",))), F.gate(), 3),
                         (R.Certificate("x", 3, 0), R.Certificate("y", 3, 0)))

    def test_d_check_universe_does_not_depend_on_order(self):
        # With a builder that does not refuse shared ids, the shared id is an
        # intrusion whichever program comes first.
        clean, bad = F.prog("x", ("answer",)), F.prog("x", ("leak", "answer"))
        for progs in ((clean, bad), (bad, clean)):
            with self.subTest(first=progs[0].stem):
                misses, intrusions, _ = F.check_universe("dup", progs, 3, builder=lenient_build)
                self.assertEqual((misses, intrusions), ([], ["x"]))

    def test_d_duplicate_universes_refused_and_would_bite(self):
        for name, progs, h in F.DUPLICATE:
            for order in (progs, progs[::-1]):
                with self.subTest(universe=name, reversed=order is not progs):
                    self.assertIsNone(R.build_list(order, F.gate(), h))
                    _, intrusions, _ = F.check_universe(name, order, h, builder=lenient_build)
                    self.assertTrue(intrusions)

    def test_d_list_follows_input_order(self):
        name, progs, h = F.design_universe()
        for order in (progs, progs[::-1]):
            lst = R.build_list(order, F.gate(), h)
            ids = [c.program_id for c in lst]
            self.assertEqual(ids, [p.program_id for p in order if p.program_id in set(ids)])
        self.assertNotEqual([c.program_id for c in R.build_list(progs, F.gate(), h)],
                            [c.program_id for c in R.build_list(progs[::-1], F.gate(), h)])

    def test_d_list_does_not_depend_on_on_expiry(self):
        name, progs, h = F.design_universe()
        lists = {oe: R.build_list(progs, F.gate(oe), h) for oe in R.ON_EXPIRY}
        self.assertEqual(len(set(lists.values())), 1)

    def test_d_seeds_fixed_and_deterministic(self):
        self.assertEqual(F.REGRESSION_SEEDS, tuple(range(4001, 4013)))
        self.assertEqual(F.generate(4001), F.generate(4001))


class FailClosed(unittest.TestCase):
    def test_malformed_inputs_are_config_error(self):
        g, p = F.gate(), F.prog("p", ("answer",))
        class SubP(R.Program):
            pass
        bad_programs = (None, ("p", ("answer",), ("work",)), R.Program("p", ("answer",), ()),
                        R.Program("p", ["answer"], ("work",)), R.Program("", ("answer",), ("work",)),
                        R.Program("p", ("answer", ""), ("work",)), SubP("p", ("answer",), ("work",)))
        for bp in bad_programs:
            with self.subTest(program=bp):
                self.assertEqual(R.evaluate(bp, g, 2).status, R.CONFIG_ERROR)
        bad_gates = (None, R.Gate((), "answer", F.rule(), F.TOOL, F.ACTIONS),
                     R.Gate(["delete"], "answer", F.rule(), F.TOOL, F.ACTIONS),
                     R.Gate(("answer",), "answer", F.rule(), F.TOOL, F.ACTIONS),
                     R.Gate(F.FORBIDDEN, "answer", F.rule(), F.TOOL, [("dry_run", {})]),
                     R.Gate(F.FORBIDDEN, "answer", [("ladder", ["a"]), ("deadline_s", 60), ("on_expiry", "hold")],
                            F.TOOL, F.ACTIONS),
                     R.Gate(F.FORBIDDEN, "", F.rule(), F.TOOL, F.ACTIONS))
        for bg in bad_gates:
            with self.subTest(gate=bg):
                self.assertEqual(R.evaluate(p, bg, 2).status, R.CONFIG_ERROR)
        for n in (-1, True, 2.0, "2", None):
            with self.subTest(n=n):
                self.assertEqual(R.evaluate(p, g, n).status, R.CONFIG_ERROR)
                self.assertIsNone(R.build_list((p,), g, n))
        for claim in ("forever", None, "NEVER"):
            self.assertEqual(R.certify(p, g, 2, claim).status, R.CONFIG_ERROR)
        self.assertIsNone(R.build_list([p], g, 2))
        self.assertIsNone(R.build_list((p, None), g, 2))

    def test_near_miss_tokens_are_different_events(self):
        # Exact-token semantics, expected statuses written by hand.
        g = F.gate()
        for name, stem, cycle, n, exp in F.NEAR_MISS:
            with self.subTest(name=name):
                self.assertEqual(R.evaluate(F.prog(name, stem, cycle), g, n).status, exp)

    def test_prefix(self):
        p = F.prog("p", ("a", "b"), ("c", "d", "e"))
        self.assertEqual(R.prefix(p, 7), ("a", "b", "c", "d", "e", "c", "d"))
        self.assertEqual(R.prefix(p, 1), ("a",))
        self.assertEqual(R.prefix(p, 0), ())


class WorldShape(unittest.TestCase):
    """Pins on the test worlds, so thinning a world fails visibly."""

    def test_world_long_prefix_covers_the_programs(self):
        longest = max(len(p.stem) + len(p.cycle) for p in F.LONG_PROGRAMS)
        self.assertGreaterEqual(F.LONG_PREFIX, 4 * longest)
        self.assertGreaterEqual(F.LONG_PREFIX, 400)
        self.assertGreaterEqual(len(F.LONG_PROGRAMS), 15)
        self.assertTrue(any(F.ANSWER in p.cycle for p in F.LONG_PROGRAMS))
        self.assertTrue(any(F.first_at(p, (F.ANSWER,)) is None for p in F.LONG_PROGRAMS))
        self.assertTrue(all(F.first_at(p, F.FORBIDDEN) is None for p in F.LONG_PROGRAMS))
        self.assertGreaterEqual(max(at for _, at in F.LATE_VIOLATORS), 300)
        for p, at in F.LATE_VIOLATORS:
            self.assertEqual(F.first_at(p, F.FORBIDDEN), at)

    def test_world_duplicate_universes(self):
        self.assertEqual(len(F.DUPLICATE), len(F.REGRESSION_SEEDS))
        for name, progs, h in F.DUPLICATE:
            labels = {}
            for p in progs:
                labels.setdefault(p.program_id, set()).add(F.label(p, h))
            shared = [ls for ls in labels.values() if len(ls) > 1]
            with self.subTest(universe=name):
                self.assertGreaterEqual(len(shared), 2)
                self.assertTrue(all({F.MUST_ADMIT, F.MUST_REFUSE} <= ls for ls in shared))

    def test_world_disguised_declarations(self):
        kinds = {type(v) for _, v in DISGUISED}
        self.assertTrue({LyingStr, LyingLower, StrSub, StrEnum} <= kinds)
        self.assertTrue(any(str.lower(v) == PERMIT and str(v) in R.ON_EXPIRY for _, v in DISGUISED))
        self.assertTrue(any(type(v) is StrSub and str.lower(v) in R.ON_EXPIRY for _, v in DISGUISED))
        self.assertEqual({n for n, _ in DISGUISED}, set(W14_ON_DISGUISED))

    def test_world_near_miss_tokens(self):
        events = [(e, exp) for _, stem, cycle, _, exp in F.NEAR_MISS for e in stem + cycle]
        self.assertTrue(any(e != e.lower() and e.lower() in F.FORBIDDEN for e, _ in events))
        self.assertTrue(any(e != e.strip() and e.strip() in F.FORBIDDEN for e, _ in events))
        self.assertTrue(any(e != e.lower() and e.lower() == F.ANSWER for e, _ in events))
        self.assertTrue(any(e != e.strip() and e.strip() == F.ANSWER for e, _ in events))

    def test_world_parity_rows(self):
        names = {row[0] for row in PARITY}
        for need in ("requires_approval_string_false", "quorum_string_fraction", "quorum_inf", "deadline_inf",
                     "unhashable_fallback", "unhashable_fallback_elsewhere", "number_fallback_elsewhere"):
            self.assertIn(need, names)


class DoneWhenE(unittest.TestCase):
    """(e) the simulation figure stays UNVERIFIED and only in paper_evidence.json; hygiene."""

    BANNED_IMPORT_WORDS = ("socket", "urllib", "http", "requests", "subprocess", "docker", "openrouter",
                           "openai", "anthropic", "sqlite", "hmac", "hashlib", "thread", "asyncio",
                           "multiprocessing", "ctypes", "pickle")
    # sha256 of the lower-case banned words, so the words never appear here.
    # Every substring of every [a-z]+ token is compared at these lengths.
    # The first is upper-case-only (the paper title says "gatekeeping"), so
    # it is matched against [A-Z]+ tokens; the rest against every token of
    # the lower-cased text.
    BANNED_UPPER_ONLY = {"6ca7ea2feefc88ecb5ed6356ed963f47dc9137f82526fdd25d618ea626d0803f": 4}
    BANNED_ANY_CASE = {
        "36c1852b63947092f69e46964f3a7400e49d5749741af087f444f458e72b27c9": 10,
        "6627835f988e2c5e50533d491163072d3f4f41f5c8b04630150debb3722ca2dd": 5,
        "d2d2328e3359f3de3515871090d1316cbcdc5383204c204f9390788c3ef8618f": 7,
    }

    @staticmethod
    def _hits(tokens, digests):
        found = []
        for tok in tokens:
            for n in set(digests.values()):
                for i in range(len(tok) - n + 1):
                    d = hashlib.sha256(tok[i:i + n].encode()).hexdigest()
                    if digests.get(d) == n:
                        found.append(tok)
        return found

    def test_e_figures_only_in_evidence_and_unverified(self):
        ev = json.loads(read("paper_evidence.json"))
        claims = ev["empirical_claims"]["claims"]
        self.assertEqual(ev["empirical_claims"]["status"], "UNVERIFIED")
        self.assertTrue(claims and all(c["status"] == "UNVERIFIED" for c in claims))
        pats = [re.escape(c["token"]) for c in claims] + ["2" + r"\.2", "mill" + "ion"]
        for name in ALL:
            if name == "paper_evidence.json":
                continue
            for pat in pats:
                with self.subTest(name=name, pat=pat):
                    self.assertIsNone(re.search(pat, read(name), re.I))

    def test_e_stdlib_imports_only(self):
        permitted = {"dataclasses", "typing", "random", "sys", "rulebook"}
        for name in CODE:
            src = read(name)
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module]
                    for mod in mods:
                        self.assertIn(mod.split(".")[0], permitted, (name, mod))
            for word in self.BANNED_IMPORT_WORDS:
                self.assertNotIn(word, src.lower(), (name, word))
            for call in ("eval(", "exec(", "open(", "__import__"):
                self.assertNotIn(call, src, (name, call))
        for node in ast.walk(ast.parse(read("mutants.py"))):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module]
                for mod in mods:
                    self.assertIn(mod.split(".")[0], {"os", "shutil", "subprocess", "sys", "tempfile"}, mod)

    def test_e_banned_words_permit_word_markers(self):
        for name in ALL:
            text = read(name)
            upper = [t.lower() for t in re.findall(r"[A-Z]+", text)]
            self.assertEqual(self._hits(upper, self.BANNED_UPPER_ONLY), [], name)
            self.assertEqual(self._hits(re.findall(r"[a-z]+", text.lower()), self.BANNED_ANY_CASE), [], name)
            self.assertNotIn(PERMIT, text.lower(), name)
            for line in text.splitlines():
                self.assertFalse(line.startswith(("<" * 7, ">" * 7, "=" * 7 + " ")) or line == "=" * 7, name)

    def test_e_banned_digest_scan_finds_a_planted_word(self):
        # The scan itself must work: plant words decoded from code points.
        planted = "".join(map(chr, (99, 104, 101, 99, 107, 101, 114)))
        self.assertTrue(self._hits(["x" + planted + "s"], self.BANNED_ANY_CASE))
        self.assertTrue(self._hits([("".join(map(chr, (75, 69, 69, 80)))).lower()], self.BANNED_UPPER_ONLY))
        self.assertEqual(self._hits(["gatekeeping"], self.BANNED_ANY_CASE), [])

    def test_e_soft_status_and_credits(self):
        readme, notice = read("README.md"), read("NOTICE")
        self.assertIn("Soft", readme)
        self.assertIn("not Team OS law and not village law", readme)
        for t in (readme, notice):
            for s in ("2611.13367", "https://arxiv.org/abs/2611.13367", "CC BY 4.0"):
                self.assertIn(s, t)
        for s in ("experiments/2026-11-05/w14-silence-expiry",
                  "https://cursor.com/codebase/coevolution-lab/playground/pull/78", "mirror"):
            self.assertIn(s, readme)
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["paper"]["licence"], "CC BY 4.0")
        self.assertIn("METHOD ONLY", ev["paper"]["use"])
        self.assertEqual(ev["quotes"], [])
        self.assertFalse(os.path.exists(os.path.join(HERE, "day-README.md")))

    def _abstract(self):
        if not SOURCES:
            self.skipTest("W20CRB_SOURCES not set")
        ev = json.loads(read("paper_evidence.json"))
        path = os.path.join(SOURCES, ev["source"]["file"])
        if not os.path.exists(path):
            self.skipTest("lab copy not present")
        with open(path, encoding="utf-8") as f:
            text = f.read()[len("Abstract:"):].rstrip("\n")
        self.assertEqual(len(text), ev["source"]["chars"])
        return ev, text

    def test_e_offsets_match_source(self):
        ev, text = self._abstract()
        for c in ev["empirical_claims"]["claims"]:
            self.assertEqual(text[c["offset"]:c["offset"] + len(c["token"])], c["token"], c["id"])

    def test_e_no_six_word_run_copied(self):
        ev, text = self._abstract()

        def runs(t):
            w = re.findall(r"[a-z0-9']+", t.lower())
            return {" ".join(w[i:i + 6]) for i in range(len(w) - 5)}
        theirs = runs(text) - runs(ev["paper"]["title"]) - runs(ev["paper"]["abs_url"])
        for name in DOCS + CODE + ("test_rulebook.py", "mutants.py"):
            with self.subTest(name=name):
                self.assertEqual(theirs & runs(read(name)), set())


if __name__ == "__main__":
    unittest.main()
