"""Tests for the w19-workspace-grant method sketch (stdlib unittest).

Run: python3 -m unittest test_workspace_grant.py -v
The excerpt checks read the source copies named in paper_evidence.json from
the directory in $W19WG_SOURCES (default: the lab review folder) and are
skipped when it is absent.
"""

import ast
import html
import json
import os
import random
import re
import unittest

import workspace_grant as W
import fixtures as F

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W19WG_SOURCES", "/workspace/lab-dig-2-2026-11-10")
IMPL = ("workspace_grant.py", "fixtures.py")
DOCS = ("README.md", "NOTICE")
A, G = W.Action, F.G
EXPIRY_TICK = G.issued_at + G.ttl


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def d(grant, action, claims=False):
    return W.decide(grant, action, claims)


class Fixtures(unittest.TestCase):
    def test_every_fixture_as_expected(self):
        lines = []
        failures, total = F.check_all(out=lines.append)
        self.assertEqual(failures, 0, "\n".join(lines))
        self.assertEqual(total, len(F.CASES))

    def test_each_fixture(self):
        for name, g, a, claims, outcome, reasons in F.CASES:
            with self.subTest(name):
                r = d(g, a, claims)
                self.assertEqual((r.outcome, r.reasons), (outcome, reasons))

    def test_names_unique(self):
        names = [c[0] for c in F.CASES]
        self.assertEqual(len(names), len(set(names)))


class DoneWhen(unittest.TestCase):
    def test_in_grant_write_passes(self):
        r = d(G, A(20, "/ws/app/src/main.py"))
        self.assertEqual((r.outcome, r.reasons, r.grant_id), (W.PASS_WITHIN_GRANT, (), "g1"))

    def test_path_outside_grant_denied(self):
        for p in ("/ws/secrets", "/ws/apple/x", "/etc/passwd", "/w", "/", "/ws"):
            with self.subTest(p=p):
                self.assertEqual(d(G, A(20, p)).outcome, W.DENY)

    def test_egress_outside_grant_denied(self):
        for h in ("evil.net", "x.pypi.org", "pypi.org.evil.net", "pypi.or", "api.example.co"):
            with self.subTest(h=h):
                r = d(G, A(20, egress=h))
                self.assertEqual((r.outcome, r.reasons), (W.DENY, (W.EGRESS_OUTSIDE_GRANT,)))

    def test_expired_resolves_to_declared_on_expiry_and_never_passes(self):
        for oe in W.ON_EXPIRY:
            g = F.grant(on_expiry=oe)
            for t in (EXPIRY_TICK, EXPIRY_TICK + 1, EXPIRY_TICK + 10 ** 9):
                for a in (A(t, "/ws/app/x"), A(t, egress="pypi.org"), A(t, "/ws/other", "evil.net")):
                    with self.subTest(on_expiry=oe, t=t, a=a):
                        r = d(g, a)
                        self.assertEqual((r.outcome, r.reasons), (oe, (W.EXPIRED,)))
                        self.assertNotEqual(r.outcome, W.PASS_WITHIN_GRANT)

    def test_expiry_boundary_is_exclusive(self):
        self.assertEqual(d(G, A(EXPIRY_TICK - 1, "/ws/app/x")).outcome, W.PASS_WITHIN_GRANT)
        self.assertEqual(d(G, A(EXPIRY_TICK, "/ws/app/x")).outcome, W.DENY)

    def test_missing_on_expiry_is_config_error(self):
        bare = W.Grant("g1", "/ws", ("/ws/app",), frozenset(), 3, 100)
        self.assertIsNone(bare.on_expiry)
        for t in (20, 500):
            r = d(bare, A(t, "/ws/app/x"))
            self.assertEqual((r.outcome, r.reasons, r.detail), (W.HOLD, (W.CONFIG_ERROR,), ("on_expiry",)))
        for oe in (None, "", "Deny", "DENY ", "pass", W.PASS_WITHIN_GRANT, 0, True, ("deny",)):
            g = F.grant(on_expiry=oe)
            for t in (20, EXPIRY_TICK, EXPIRY_TICK + 5):
                with self.subTest(on_expiry=oe, t=t):
                    r = d(g, A(t, "/ws/app/x"))
                    self.assertEqual((r.outcome, r.reasons), (W.HOLD, (W.CONFIG_ERROR,)))
                    self.assertIn("on_expiry", r.detail)

    def test_grant_issued_at_or_after_action_denied(self):
        for t in (G.issued_at, G.issued_at - 1, 0):
            with self.subTest(t=t):
                r = d(G, A(t, "/ws/app/x"))
                self.assertEqual((r.outcome, r.reasons), (W.DENY, (W.NOT_BEFORE_ACTION,)))
        self.assertEqual(d(G, A(G.issued_at + 1, "/ws/app/x")).outcome, W.PASS_WITHIN_GRANT)

    def test_no_grant_denied(self):
        self.assertEqual(d(None, A(20, "/ws/app/x")).reasons, (W.NO_GRANT,))
        self.assertEqual(W.decide_by_id({"g1": G}, "g2", A(20, "/ws/app/x")).reasons, (W.NO_GRANT,))
        self.assertEqual(W.decide_by_id({"g1": G}, "g1", A(20, "/ws/app/x")).outcome,
                         W.PASS_WITHIN_GRANT)
        for bad in (None, [G], "g1"):
            self.assertEqual(W.decide_by_id(bad, "g1", A(20, "/ws/app/x")).outcome, W.DENY)

    def test_claimed_path_conflict_denied(self):
        r = d(G, A(20, "/ws/app/x"), True)
        self.assertEqual((r.outcome, r.reasons), (W.DENY, (W.CLAIMED_BY_OTHER,)))
        r = d(G, A(20, "/ws/app/lib/a.py"), frozenset({"/ws/app/lib/"}))
        self.assertEqual(r.reasons, (W.CLAIMED_BY_OTHER,))
        self.assertEqual(d(G, A(20, "/ws/app/libs/a.py"), frozenset({"/ws/app/lib"})).outcome,
                         W.PASS_WITHIN_GRANT)
        self.assertEqual(d(G, A(20, "/ws/app/x"), frozenset()).outcome, W.PASS_WITHIN_GRANT)

    def test_prefix_tricks(self):
        cases = {
            "/ws/app/x": W.PASS_WITHIN_GRANT,
            "/ws/app": W.PASS_WITHIN_GRANT,
            "/ws/app/": W.PASS_WITHIN_GRANT,
            "//ws//app//x": W.PASS_WITHIN_GRANT,
            "/ws/./app/x": W.PASS_WITHIN_GRANT,
            "/ws/apple": W.DENY,
            "/ws/apple/x": W.DENY,
            "/ws/ap": W.DENY,
            "/ws/app/../apple/x": W.DENY,
            "/ws/app/../../etc": W.DENY,
            "app/../../etc": W.DENY,
            "/ws/app/%2e%2e/x": W.HOLD,
            "/ws/app\\..\\x": W.HOLD,
            "/ws/app/.../x": W.HOLD,
        }
        for p, outcome in cases.items():
            with self.subTest(p=p):
                self.assertEqual(d(G, A(20, p)).outcome, outcome)
        # A trailing slash or doubled slash in the grant's own prefix changes nothing.
        for pref in ("/ws/app/", "/ws//app", "app", "./app/"):
            g = F.grant(prefixes=(pref,))
            with self.subTest(prefix=pref):
                self.assertEqual(d(g, A(20, "/ws/app/x")).outcome, W.PASS_WITHIN_GRANT)
                self.assertEqual(d(g, A(20, "/ws/apple/x")).outcome, W.DENY)


class SilenceDoctrine(unittest.TestCase):
    def test_no_expiry_value_resolves_to_pass(self):
        self.assertNotIn(W.PASS_WITHIN_GRANT, W.ON_EXPIRY)
        g = F.grant(on_expiry=W.PASS_WITHIN_GRANT)
        self.assertEqual(d(g, A(EXPIRY_TICK, "/ws/app/x")).reasons, (W.CONFIG_ERROR,))

    def test_nothing_past_expiry_ever_passes(self):
        rng = random.Random(7)
        paths = ["/ws/app/x", "docs/a", "/ws/other", None]
        hosts = ["pypi.org", "evil.net", None]
        for _ in range(3000):
            g = F.grant(on_expiry=rng.choice(W.ON_EXPIRY + (None, "x")),
                        issued_at=rng.randrange(0, 50), ttl=rng.randrange(1, 50))
            t = g.issued_at + g.ttl + rng.randrange(0, 1000)
            a = A(t, rng.choice(paths), rng.choice(hosts))
            self.assertNotEqual(d(g, a, rng.choice([False, True])).outcome, W.PASS_WITHIN_GRANT)

    def test_grant_is_immutable_and_layer_cannot_extend(self):
        import dataclasses
        with self.assertRaises(dataclasses.FrozenInstanceError):
            G.ttl = 10 ** 9
        names = {n for n in dir(W) if not n.startswith("_")}
        for word in ("renew", "extend", "refresh", "touch"):
            self.assertFalse(any(word in n.lower() for n in names), word)

    def test_pass_requires_every_condition(self):
        # Flip one condition at a time from a passing case; none may pass.
        base = A(20, "/ws/app/x", "pypi.org")
        self.assertEqual(d(G, base).outcome, W.PASS_WITHIN_GRANT)
        flips = [
            (None, base, False), (G, A(G.issued_at, "/ws/app/x", "pypi.org"), False),
            (G, A(EXPIRY_TICK, "/ws/app/x", "pypi.org"), False),
            (G, A(20, "/ws/z", "pypi.org"), False), (G, A(20, "/ws/app/x", "evil.net"), False),
            (G, base, True), (F.grant(on_expiry=None), base, False),
        ]
        for g, a, c in flips:
            with self.subTest(g=g, a=a, c=c):
                self.assertNotEqual(d(g, a, c).outcome, W.PASS_WITHIN_GRANT)

    def test_vocabulary(self):
        self.assertEqual(set(W.OUTCOMES),
                         {W.PASS_WITHIN_GRANT, W.DENY, W.HOLD, W.SAFE_FALLBACK, W.ESCALATE})


class FailClosed(unittest.TestCase):
    def test_bad_times(self):
        for t in (20.0, float("nan"), float("inf"), -float("inf"), True, False, None, "20", [20]):
            with self.subTest(t=t):
                self.assertEqual(d(G, A(t, "/ws/app/x")).reasons, (W.BAD_TIME,))
        for field, v in (("issued_at", 10.5), ("issued_at", -1), ("issued_at", None),
                         ("ttl", 0), ("ttl", -5), ("ttl", 2.0), ("ttl", True), ("ttl", float("nan"))):
            with self.subTest(field=field, v=v):
                r = d(F.grant(**{field: v}), A(20, "/ws/app/x"))
                self.assertEqual((r.outcome, r.reasons), (W.HOLD, (W.CONFIG_ERROR,)))

    def test_bad_paths(self):
        for p in (b"/ws/app", 5, "", "\x00", "/ws/app/\x07", "~", "$PWD/app", "/ws/app/%2F", " /ws/app",
                  "/ws/app /x", "/ws/./../ws/app"):
            with self.subTest(p=p):
                self.assertNotEqual(d(G, A(20, p)).outcome, W.PASS_WITHIN_GRANT)

    def test_bad_grants(self):
        for kw in (dict(root="ws"), dict(root=""), dict(root="/"), dict(root=None),
                   dict(prefixes=()), dict(prefixes=["/ws/app"]), dict(prefixes=("/ws/../etc",)),
                   dict(prefixes=("/etc",)), dict(prefixes=("",)), dict(egress={"a.b"}),
                   dict(egress=frozenset({"a.b:80"})), dict(egress=frozenset({""})),
                   dict(grant_id=None), dict(grant_id=7)):
            with self.subTest(kw=kw):
                r = d(F.grant(**kw), A(20, "/ws/app/x"))
                self.assertEqual((r.outcome, r.reasons), (W.HOLD, (W.CONFIG_ERROR,)))
        for g in ({}, "g1", 0, object()):
            self.assertEqual(d(g, A(20, "/ws/app/x")).reasons, (W.CONFIG_ERROR,))

    def test_bad_claims_input(self):
        for c in ("yes", 1, None, ["/ws/app"], {"/ws/app"}, frozenset({5}), frozenset({"rel/path"})):
            with self.subTest(c=c):
                self.assertEqual(d(G, A(20, "/ws/app/x"), c).outcome, W.HOLD)

    def test_egress_normalisation(self):
        self.assertEqual(d(G, A(20, egress="PyPI.ORG.")).outcome, W.PASS_WITHIN_GRANT)
        for h in ("pypi.org:443", "https://pypi.org", "user@pypi.org", "pypi..org", ".pypi.org",
                  "*.pypi.org", "pypi.org/", "pyp\u0456.org", " pypi.org", "", 5, b"pypi.org"):
            with self.subTest(h=h):
                r = d(G, A(20, egress=h))
                self.assertEqual((r.outcome, r.reasons), (W.HOLD, (W.EGRESS_MALFORMED,)))
        # The same refusals apply to the grant's own host list.
        for h in ("pypi..org", "pyp\u0456.org", ".pypi.org", "pypi.org:443"):
            with self.subTest(grant_host=h):
                r = d(F.grant(egress=frozenset({h})), A(20, "/ws/app/x"))
                self.assertEqual((r.outcome, r.detail), (W.HOLD, ("egress_host",)))

    def test_internal_error_holds(self):
        class Weird(W.Grant):
            pass

        class Boom(str):
            def startswith(self, *a):
                raise RuntimeError("boom")

        g = Weird(**{f: getattr(G, f) for f in ("grant_id", "root", "prefixes", "egress",
                                               "issued_at", "ttl", "on_expiry")})
        # A subclass is not a Grant for this layer: it fails closed.
        r = d(g, A(20, "/ws/app/x"))
        self.assertEqual((r.outcome, r.reasons, r.detail), (W.HOLD, (W.CONFIG_ERROR,), ("not_a_grant",)))
        r = d(G, A(20, Boom("/ws/app/x")))
        self.assertEqual(r.outcome, W.HOLD)
        real = W._decide

        def explode(*a):
            raise RuntimeError("boom")

        W._decide = explode
        try:
            self.assertEqual(d(G, A(20, "/ws/app/x")), W.Decision(W.HOLD, (W.BAD_ACTION,)))
        finally:
            W._decide = real


def _flip_grant():
    """A Grant subclass whose on_expiry reads 'deny' twice, then the pass
    outcome: the attack that passed before exact-type checks."""
    class Flip(W.Grant):
        @property
        def on_expiry(self):
            n = self.__dict__.get("_n", 0)
            self.__dict__["_n"] = n + 1
            return W.DENY if n < 2 else W.PASS_WITHIN_GRANT

    fl = object.__new__(Flip)
    for f in ("grant_id", "root", "prefixes", "egress", "issued_at", "ttl"):
        object.__setattr__(fl, f, getattr(G, f))
    return fl


class EqAnyStr(str):
    def __eq__(self, other):
        return True

    __hash__ = str.__hash__


class HostsView(frozenset):
    def __iter__(self):
        return iter(["pypi.org", "evil.net"])


class ExactTypes(unittest.TestCase):
    """FAIL-1: only an exact Grant with exact field types is used, each
    field is read once, and on_expiry comes back as the module constant."""

    def test_mutating_on_expiry_subclass_holds(self):
        for t in (20, EXPIRY_TICK, 10 ** 6):
            with self.subTest(t=t):
                r = d(_flip_grant(), A(t, "/ws/app/x"))
                self.assertEqual((r.outcome, r.reasons), (W.HOLD, (W.CONFIG_ERROR,)))
                self.assertEqual(r.detail, ("not_a_grant",))

    def test_on_expiry_read_once(self):
        # Even on an exact Grant, a mutable stand-in cannot be smuggled in:
        # the value must be an exact str and the result is the constant.
        g = F.grant(on_expiry="".join(["de", "ny"]))
        r = d(g, A(EXPIRY_TICK, "/ws/app/x"))
        self.assertIs(r.outcome, W.DENY)
        for oe in W.ON_EXPIRY:
            fresh = "".join(list(oe))
            r = d(F.grant(on_expiry=fresh), A(EXPIRY_TICK + 1, "/ws/app/x"))
            self.assertIs(r.outcome, oe)

    def test_str_subclass_on_expiry_is_config_error(self):
        for v in (EqAnyStr(W.PASS_WITHIN_GRANT), EqAnyStr("deny"), type("S", (str,), {})("deny")):
            for t in (20, EXPIRY_TICK, 10 ** 6):
                with self.subTest(v=type(v).__name__, t=t):
                    r = d(F.grant(on_expiry=v), A(t, "/ws/app/x"))
                    self.assertEqual((r.outcome, r.reasons, r.detail),
                                     (W.HOLD, (W.CONFIG_ERROR,), ("on_expiry",)))

    def test_frozenset_subclass_egress_fails_closed(self):
        r = d(F.grant(egress=HostsView({"pypi.org"})), A(20, egress="evil.net"))
        self.assertEqual((r.outcome, r.reasons, r.detail), (W.HOLD, (W.CONFIG_ERROR,), ("egress",)))

    def test_other_field_subclasses_fail_closed(self):
        S = type("S", (str,), {})
        T = type("T", (tuple,), {})
        I = type("I", (int,), {})
        for kw, err in ((dict(grant_id=S("g1")), "grant_id"), (dict(root=S("/ws")), "root"),
                        (dict(prefixes=T(("/ws/app",))), "prefixes_empty"),
                        (dict(prefixes=(S("/ws/app"),)), "prefix_malformed"),
                        (dict(egress=frozenset({S("pypi.org")})), "egress_host"),
                        (dict(issued_at=I(3)), "issued_at"), (dict(ttl=I(100)), "ttl")):
            with self.subTest(kw=kw):
                r = d(F.grant(**kw), A(20, "/ws/app/x"))
                self.assertEqual((r.outcome, r.detail), (W.HOLD, (err,)))

    def test_action_and_claims_subclasses_fail_closed(self):
        class Shifty(W.Action):
            pass

        self.assertEqual(d(G, Shifty(20, "/ws/app/x")).reasons, (W.BAD_ACTION,))

        class Hidden(frozenset):
            def __iter__(self):
                return iter([])

        r = d(G, A(20, "/ws/app/lib/a"), Hidden({"/ws/app/lib"}))
        self.assertEqual((r.outcome, r.reasons), (W.HOLD, (W.BAD_CLAIMS,)))
        r = d(G, A(20, "/ws/app/x"), type("B", (int,), {})(1))
        self.assertEqual(r.outcome, W.HOLD)

    def test_no_expired_decision_ever_carries_pass(self):
        seen = []
        variants = list(W.ON_EXPIRY) + [None, "", W.PASS_WITHIN_GRANT, EqAnyStr("x"), "DENY"]
        grants = [F.grant(on_expiry=v) for v in variants] + [_flip_grant()]
        grants += [F.grant(on_expiry=v, egress=HostsView({"pypi.org"})) for v in W.ON_EXPIRY]
        for g in grants:
            for t in (EXPIRY_TICK, EXPIRY_TICK + 1, 10 ** 6, 10 ** 18):
                for a in (A(t, "/ws/app/x"), A(t, egress="pypi.org"), A(t, "/ws/z", "evil.net")):
                    for c in (False, True, frozenset({"/ws/app"})):
                        seen.append(d(g, a, c))
        seen += [d(g, a, c) for _, g, a, c, _, _ in F.CASES]
        expired = [r for r in seen if W.EXPIRED in r.reasons]
        self.assertTrue(expired)
        for r in expired:
            self.assertNotEqual(r.outcome, W.PASS_WITHIN_GRANT)
            self.assertTrue(any(r.outcome is oe for oe in W.ON_EXPIRY), r)
        for r in seen:
            if r.outcome == W.PASS_WITHIN_GRANT:
                self.assertEqual(r.reasons, ())


class Survivors(unittest.TestCase):
    """Gaps found in review: each pinned by a test."""

    def test_safe_fallback_never_counted_as_pass(self):
        rs = [d(F.grant(on_expiry=W.SAFE_FALLBACK), A(EXPIRY_TICK + i, "/ws/app/x")) for i in range(3)]
        counts = W.report(rs)
        self.assertEqual(counts[W.PASS_WITHIN_GRANT], 0)
        self.assertEqual(counts[W.SAFE_FALLBACK], 3)
        mixed = rs + [d(G, A(20, "/ws/app/x"))]
        self.assertEqual(W.report(mixed)[W.PASS_WITHIN_GRANT], 1)

    def test_hosts_not_casefolded(self):
        g = F.grant(egress=frozenset({"passau.de"}))
        r = d(g, A(20, egress="pa\u00dfau.de"))
        self.assertEqual((r.outcome, r.reasons), (W.HOLD, (W.EGRESS_MALFORMED,)))
        self.assertEqual(d(g, A(20, egress="PASSAU.de")).outcome, W.PASS_WITHIN_GRANT)
        r = d(F.grant(egress=frozenset({"pa\u00dfau.de"})), A(20, egress="passau.de"))
        self.assertEqual((r.outcome, r.detail), (W.HOLD, ("egress_host",)))

    def test_kelvin_sign_not_mapped(self):
        g = F.grant(egress=frozenset({"kernel.org"}))
        for h in ("\u212aernel.org", "\u212aERNEL.ORG", "kerne\u0131.org", "\uff4bernel.org"):
            with self.subTest(h=h):
                r = d(g, A(20, egress=h))
                self.assertEqual((r.outcome, r.reasons), (W.HOLD, (W.EGRESS_MALFORMED,)))
        r = d(F.grant(egress=frozenset({"\u212aernel.org"})), A(20, egress="kernel.org"))
        self.assertEqual((r.outcome, r.detail), (W.HOLD, ("egress_host",)))

    def test_grant_hosts_are_normalised_once(self):
        g = F.grant(egress=frozenset({"PyPI.Org."}))
        for h in ("pypi.org", "PYPI.ORG", "pypi.org."):
            with self.subTest(h=h):
                self.assertEqual(d(g, A(20, egress=h)).outcome, W.PASS_WITHIN_GRANT)

    def test_idn_only_as_ascii_xn_form(self):
        g = F.grant(egress=frozenset({"xn--bcher-kva.example"}))
        self.assertEqual(d(g, A(20, egress="XN--BCHER-KVA.example")).outcome, W.PASS_WITHIN_GRANT)
        self.assertEqual(d(g, A(20, egress="b\u00fccher.example")).reasons, (W.EGRESS_MALFORMED,))

    def test_claim_flag_applies_to_egress_only(self):
        r = d(G, A(20, egress="pypi.org"), True)
        self.assertEqual((r.outcome, r.reasons), (W.DENY, (W.CLAIMED_BY_OTHER,)))
        r = d(G, A(20, "/ws/app/x", "pypi.org"), True)
        self.assertEqual((r.outcome, r.reasons), (W.DENY, (W.CLAIMED_BY_OTHER,)))
        # A claim set names paths, so it does not touch an egress-only action,
        # but a malformed set still holds.
        self.assertEqual(d(G, A(20, egress="pypi.org"), frozenset({"/ws/app"})).outcome,
                         W.PASS_WITHIN_GRANT)
        self.assertEqual(d(G, A(20, egress="pypi.org"), frozenset({"app"})).reasons, (W.BAD_CLAIMS,))

    def test_parent_of_claimed_path_denied(self):
        claims = frozenset({"/ws/app/lib"})
        for p in ("/ws/app", "/ws/app/", "app", "//ws/app/."):
            with self.subTest(p=p):
                r = d(G, A(20, p), claims)
                self.assertEqual((r.outcome, r.reasons), (W.DENY, (W.CONTAINS_CLAIMED,)))
        self.assertEqual(d(G, A(20, "/ws/app/lib/x"), claims).reasons, (W.CLAIMED_BY_OTHER,))
        self.assertEqual(d(G, A(20, "/ws/app/lib"), claims).reasons, (W.CLAIMED_BY_OTHER,))
        self.assertEqual(d(G, A(20, "/ws/app/libx"), claims).outcome, W.PASS_WITHIN_GRANT)
        self.assertEqual(d(G, A(20, "/ws/app/x"), claims).outcome, W.PASS_WITHIN_GRANT)
        r = d(G, A(20, "/ws/other"), frozenset({"/ws/other/a"}))
        self.assertEqual(r.reasons, (W.PATH_OUTSIDE_GRANT, W.CONTAINS_CLAIMED))


class TrustBoundary(unittest.TestCase):
    """Out of scope by design and stated in the README: the layer trusts the
    Grant value it is handed. These pin that the documented passes are
    exactly what the README says, not a hidden extra."""

    def test_documented_forge_rows_still_pass(self):
        import dataclasses
        self_written = W.Grant("mine", "/ws", ("/ws",), frozenset({"evil.net"}), 0, 10 ** 18, W.DENY)
        self.assertEqual(d(self_written, A(10 ** 9, "/ws/secrets/key", "evil.net")).outcome,
                         W.PASS_WITHIN_GRANT)
        widened = dataclasses.replace(G, prefixes=("/ws",), ttl=10 ** 12)
        self.assertEqual(widened.grant_id, G.grant_id)
        self.assertEqual(d(widened, A(10 ** 6, "/ws/secrets/key")).outcome, W.PASS_WITHIN_GRANT)
        g = F.grant()
        object.__setattr__(g, "ttl", 10 ** 12)
        object.__setattr__(g, "prefixes", ("/ws",))
        self.assertEqual(d(g, A(10 ** 6, "/ws/secrets/key")).outcome, W.PASS_WITHIN_GRANT)
        reg = {"g1": F.grant()}
        reg["g1"] = widened
        self.assertEqual(W.decide_by_id(reg, "g1", A(10 ** 6, "/ws/secrets/key")).outcome,
                         W.PASS_WITHIN_GRANT)

    def test_readme_states_the_boundary(self):
        text = " ".join(read("README.md").lower().split())
        for s in ("trusts whatever grant", "issuance", "authenticity", "integrity",
                  "subject binding", "replay", "dataclasses.replace", "object.__setattr__",
                  "decide_by_id", "frozenset subclass", "self-written", "#78"):
            self.assertIn(s, text)


class ApprovalUnit(unittest.TestCase):
    def test_one_grant_covers_a_run_of_actions(self):
        run = [A(11 + i, "/ws/app/f%d.py" % i) for i in range(40)]
        self.assertTrue(all(d(G, a).outcome == W.PASS_WITHIN_GRANT for a in run))
        self.assertEqual(W.prompts_needed(run, "per_action"), 40)
        self.assertEqual(W.prompts_needed(run, "per_workspace"), 1)
        self.assertEqual(W.prompts_needed([], "per_workspace"), 0)
        with self.assertRaises(ValueError):
            W.prompts_needed(run, "never")

    def test_boundary_crossing_needs_a_new_grant_issued_first(self):
        a = A(30, "/ws/infra/deploy.sh")
        self.assertEqual(d(G, a).outcome, W.DENY)
        wider = F.grant(grant_id="g2", prefixes=("/ws/infra",), issued_at=25)
        self.assertEqual(d(wider, a).outcome, W.PASS_WITHIN_GRANT)
        late = F.grant(grant_id="g3", prefixes=("/ws/infra",), issued_at=30)
        self.assertEqual(d(late, a).outcome, W.DENY)

    def test_report_counts(self):
        rs = [d(g, a, c) for _, g, a, c, _, _ in F.CASES]
        counts = W.report(rs)
        self.assertEqual(sum(counts.values()), len(F.CASES))
        self.assertGreater(counts[W.PASS_WITHIN_GRANT], 0)


class NotAFence(unittest.TestCase):
    def test_no_claim_state_in_the_layer(self):
        tree = ast.parse(read("workspace_grant.py"))
        globals_assigned = {t.id for n in tree.body if isinstance(n, ast.Assign)
                            for t in n.targets if isinstance(t, ast.Name)}
        for name in globals_assigned:
            self.assertFalse("claim" in name.lower() and name not in ("CLAIMED_BY_OTHER", "BAD_CLAIMS", "CONTAINS_CLAIMED"), name)
        self.assertFalse(any(isinstance(n, ast.ClassDef) and "claim" in n.name.lower()
                             for n in tree.body))

    def test_decide_is_pure(self):
        claims = frozenset({"/ws/app/lib"})
        before = (G, claims)
        for _ in range(3):
            d(G, A(20, "/ws/app/lib/a"), claims)
        self.assertEqual((G, claims), before)


class Hygiene(unittest.TestCase):
    BANNED = ("K" + "EEP", "Cloud" + "Agent", "Sm" + "ith", "Chec" + "ker", "sl" + "ack", "grok" + "ki")
    PERMIT = "al" + "low"

    def test_banned_words_absent(self):
        for name in DOCS + IMPL:
            text = read(name).lower()
            for w in self.BANNED:
                self.assertFalse(w.lower() in text, (name, w))

    def test_no_permit_word_anywhere(self):
        for name in DOCS + IMPL + ("test_workspace_grant.py", "paper_evidence.json"):
            self.assertFalse(self.PERMIT in read(name).lower(), name)

    def test_no_conflict_markers(self):
        for name in DOCS + IMPL + ("paper_evidence.json",):
            for m in ("<" * 7, ">" * 7, "=" * 7 + "\n"):
                self.assertFalse(m in read(name), name)

    def test_stdlib_only_offline_no_runtime_pieces(self):
        permitted = {"math", "dataclasses", "typing", "workspace_grant", "sys"}
        for name in IMPL:
            for node in ast.walk(ast.parse(read(name))):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [node.module.split(".")[0]]
                else:
                    continue
                for m in mods:
                    self.assertIn(m, permitted, (name, m))

    def test_paper_numbers_only_in_evidence(self):
        ev = json.loads(read("paper_evidence.json"))
        nums = set()
        for c in ev["empirical_claims"]["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")
            nums.update(re.findall(r"\d[\d,]*(?:\.\d+)?%?", c["text"]))
        nums = {n for n in nums if len(n.strip("%")) >= 2}
        for name in DOCS + IMPL:
            text = read(name)
            for n in nums:
                with self.subTest(file=name, number=n):
                    self.assertIsNone(re.search(r"(?<![\d.,])" + re.escape(n) + r"(?![\d])", text))


class Evidence(unittest.TestCase):
    def test_shape(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.08516")
        self.assertIn("CC BY 4.0", ev["paper"]["licence"])
        self.assertEqual(ev["upstream_reference"]["pin"], "14653158e820b0ca46f170e0125c8528b72205c0")
        self.assertFalse(ev["upstream_reference"]["used"])
        self.assertEqual(len(ev["excerpts"]), 3)

    def test_notice_and_readme(self):
        notice, readme = read("NOTICE"), read("README.md")
        for t in (notice, readme):
            for s in ("2611.08516", "CC BY 4.0", "14653158e820b0ca46f170e0125c8528b72205c0",
                      "Apache"):
                self.assertIn(s, t)
        self.assertIn("Hui Zhao", notice)
        self.assertIn("no NOTICE file", notice)
        for n in (73, 59, 77, 78, 19):
            self.assertIn("https://cursor.com/codebase/coevolution-lab/playground/pull/%d" % n, readme)

    @unittest.skipUnless(os.path.isdir(SOURCES), "source copies not present")
    def test_excerpts_verbatim(self):
        ev = json.loads(read("paper_evidence.json"))
        src = ev["sources"]

        def load(key):
            with open(os.path.join(SOURCES, src[key]["path"]), encoding="utf-8") as f:
                return f.read()

        abs_html = load("abs_html")
        abs_norm = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", abs_html)))
        readme = load("readme")
        q = {e["id"]: e["excerpt"] for e in ev["excerpts"]}
        self.assertEqual(abs_norm.count(q["Q1-abstract-boundary-shift"]), 1)
        self.assertEqual(load("abs_txt").count(q["Q1-abstract-boundary-shift"]), 1)
        lines = readme.splitlines()
        self.assertIn(q["Q2-readme-what-it-is"], lines[23])
        self.assertIn(q["Q3-readme-security-model"], lines[35])
        self.assertIn("http://creativecommons.org/licenses/by/4.0/", abs_html)


if __name__ == "__main__":
    unittest.main()
