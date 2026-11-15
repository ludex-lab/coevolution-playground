"""Synthetic fixtures for w19-workspace-grant. Run: python3 fixtures.py

Each case is (name, grant, action, claimed_by_other, expected outcome,
expected reasons). The expected values are used only here and in the tests;
the decision sees nothing but the grant, the action and the claim input.
"""

import workspace_grant as W

A = W.Action
fs = frozenset


def grant(**kw):
    base = dict(grant_id="g1", root="/ws", prefixes=("/ws/app", "docs"),
                egress=fs({"pypi.org", "api.example.com"}), issued_at=3, ttl=100,
                on_expiry=W.DENY)
    base.update(kw)
    return W.Grant(**base)


G = grant()
P, D, H = W.PASS_WITHIN_GRANT, W.DENY, W.HOLD


def flip_grant():
    """Grant subclass whose on_expiry reads 'deny' twice, then a pass."""
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


class HostsView(frozenset):
    """Iteration that differs from the contents."""
    def __iter__(self):
        return iter(["pypi.org", "evil.net"])


class EqAnyStr(str):
    def __eq__(self, other):
        return True

    __hash__ = str.__hash__


class ActionSub(W.Action):
    pass


class ClaimsView(frozenset):
    def __iter__(self):
        return iter([])

CASES = [
    # Compliant paths.
    ("in_grant_write", G, A(20, "/ws/app/main.py"), False, P, ()),
    ("in_grant_relative_write", G, A(20, "docs/index.md"), False, P, ()),
    ("in_grant_prefix_itself", G, A(20, "/ws/app"), False, P, ()),
    ("in_grant_egress", G, A(20, egress="pypi.org"), False, P, ()),
    ("in_grant_write_and_egress", G, A(20, "/ws/app/x", "API.Example.com."), False, P, ()),
    ("double_slash_and_dot_collapse", G, A(20, "/ws//app/./src/"), False, P, ()),
    ("last_tick_before_expiry", G, A(102, "/ws/app/x"), False, P, ()),
    # Outside the grant.
    ("path_outside_grant", G, A(20, "/ws/secrets/key"), False, D, (W.PATH_OUTSIDE_GRANT,)),
    ("sibling_prefix_apple", G, A(20, "/ws/apple/x"), False, D, (W.PATH_OUTSIDE_GRANT,)),
    ("sibling_prefix_app_dash", G, A(20, "/ws/app-old/x"), False, D, (W.PATH_OUTSIDE_GRANT,)),
    ("absolute_escape", G, A(20, "/etc/passwd"), False, D, (W.OUTSIDE_WORKSPACE,)),
    ("root_sibling_wsx", G, A(20, "/wsx/app/x"), False, D, (W.OUTSIDE_WORKSPACE,)),
    ("dotdot_escape", G, A(20, "/ws/app/../../etc/passwd"), False, D, (W.PATH_ESCAPE,)),
    ("dotdot_inside", G, A(20, "/ws/app/../app/x"), False, D, (W.PATH_ESCAPE,)),
    ("relative_dotdot", G, A(20, "../etc/passwd"), False, D, (W.PATH_ESCAPE,)),
    ("egress_outside_grant", G, A(20, egress="evil.example.net"), False, D, (W.EGRESS_OUTSIDE_GRANT,)),
    ("egress_subdomain_not_covered", G, A(20, egress="x.pypi.org"), False, D, (W.EGRESS_OUTSIDE_GRANT,)),
    ("egress_suffix_trick", G, A(20, egress="pypi.org.evil.net"), False, D, (W.EGRESS_OUTSIDE_GRANT,)),
    ("write_ok_egress_out", G, A(20, "/ws/app/x", "evil.net"), False, D, (W.EGRESS_OUTSIDE_GRANT,)),
    ("both_out", G, A(20, "/ws/other", "evil.net"), False, D,
     (W.PATH_OUTSIDE_GRANT, W.EGRESS_OUTSIDE_GRANT)),
    # Timing.
    ("no_grant", None, A(20, "/ws/app/x"), False, D, (W.NO_GRANT,)),
    ("issued_at_action_time", G, A(3, "/ws/app/x"), False, D, (W.NOT_BEFORE_ACTION,)),
    ("issued_after_action", G, A(2, "/ws/app/x"), False, D, (W.NOT_BEFORE_ACTION,)),
    ("expired_deny", G, A(103, "/ws/app/x"), False, D, (W.EXPIRED,)),
    ("expired_safe_fallback", grant(on_expiry=W.SAFE_FALLBACK), A(500, "/ws/app/x"), False,
     W.SAFE_FALLBACK, (W.EXPIRED,)),
    ("expired_escalate", grant(on_expiry=W.ESCALATE), A(103, "/ws/app/x"), False,
     W.ESCALATE, (W.EXPIRED,)),
    ("expired_hold", grant(on_expiry=W.HOLD), A(103, "/ws/app/x"), False, H, (W.EXPIRED,)),
    # Configuration errors.
    ("missing_on_expiry", grant(on_expiry=None), A(20, "/ws/app/x"), False, H, (W.CONFIG_ERROR,)),
    ("unknown_on_expiry", grant(on_expiry="pass"), A(20, "/ws/app/x"), False, H, (W.CONFIG_ERROR,)),
    ("on_expiry_pass_within_grant", grant(on_expiry=W.PASS_WITHIN_GRANT), A(103, "/ws/app/x"), False,
     H, (W.CONFIG_ERROR,)),
    ("empty_prefixes", grant(prefixes=()), A(20, "/ws/app/x"), False, H, (W.CONFIG_ERROR,)),
    ("prefix_outside_root", grant(prefixes=("/etc",)), A(20, "/etc/x"), False, H, (W.CONFIG_ERROR,)),
    ("prefix_with_dotdot", grant(prefixes=("/ws/app/..",)), A(20, "/ws/x"), False, H, (W.CONFIG_ERROR,)),
    ("root_is_slash", grant(root="/", prefixes=("/",)), A(20, "/etc/x"), False, H, (W.CONFIG_ERROR,)),
    ("ttl_zero", grant(ttl=0), A(20, "/ws/app/x"), False, H, (W.CONFIG_ERROR,)),
    ("ttl_bool", grant(ttl=True), A(20, "/ws/app/x"), False, H, (W.CONFIG_ERROR,)),
    ("issued_at_float", grant(issued_at=3.0), A(20, "/ws/app/x"), False, H, (W.CONFIG_ERROR,)),
    ("ttl_inf", grant(ttl=float("inf")), A(20, "/ws/app/x"), False, H, (W.CONFIG_ERROR,)),
    ("egress_wildcard", grant(egress=fs({"*.example.com"})), A(20, egress="a.example.com"), False,
     H, (W.CONFIG_ERROR,)),
    ("egress_not_frozenset", grant(egress={"pypi.org"}), A(20, egress="pypi.org"), False,
     H, (W.CONFIG_ERROR,)),
    ("empty_grant_id", grant(grant_id=""), A(20, "/ws/app/x"), False, H, (W.CONFIG_ERROR,)),
    # Malformed actions.
    ("time_float", G, A(20.0, "/ws/app/x"), False, H, (W.BAD_TIME,)),
    ("time_nan", G, A(float("nan"), "/ws/app/x"), False, H, (W.BAD_TIME,)),
    ("time_inf", G, A(float("inf"), "/ws/app/x"), False, H, (W.BAD_TIME,)),
    ("time_bool", G, A(True, "/ws/app/x"), False, H, (W.BAD_TIME,)),
    ("time_str", G, A("20", "/ws/app/x"), False, H, (W.BAD_TIME,)),
    ("path_not_str", G, A(20, b"/ws/app/x"), False, H, (W.PATH_MALFORMED,)),
    ("path_empty", G, A(20, ""), False, H, (W.PATH_MALFORMED,)),
    ("path_backslash", G, A(20, "/ws/app\\..\\..\\etc"), False, H, (W.PATH_MALFORMED,)),
    ("path_percent_encoded_dots", G, A(20, "/ws/app/%2e%2e/%2e%2e/etc"), False, H, (W.PATH_MALFORMED,)),
    ("path_tilde", G, A(20, "~/ws/app/x"), False, H, (W.PATH_MALFORMED,)),
    ("path_env_var", G, A(20, "$HOME/.ssh/id"), False, H, (W.PATH_MALFORMED,)),
    ("path_nul", G, A(20, "/ws/app/x\x00/../../etc"), False, H, (W.PATH_MALFORMED,)),
    ("path_triple_dot", G, A(20, "/ws/app/.../x"), False, H, (W.PATH_MALFORMED,)),
    ("path_trailing_space_segment", G, A(20, "/ws/app /x"), False, H, (W.PATH_MALFORMED,)),
    ("egress_with_port", G, A(20, egress="pypi.org:443"), False, H, (W.EGRESS_MALFORMED,)),
    ("egress_with_userinfo", G, A(20, egress="pypi.org@evil.net"), False, H, (W.EGRESS_MALFORMED,)),
    ("egress_url", G, A(20, egress="https://pypi.org/"), False, H, (W.EGRESS_MALFORMED,)),
    ("empty_action", G, A(20), False, H, (W.BAD_ACTION,)),
    ("not_an_action", G, ("write", "/ws/app/x", 20), False, H, (W.BAD_ACTION,)),
    ("not_a_grant", {"root": "/ws"}, A(20, "/ws/app/x"), False, H, (W.CONFIG_ERROR,)),
    # Claimed paths (external input; the fence itself is #73).
    ("claimed_by_other_flag", G, A(20, "/ws/app/x"), True, D, (W.CLAIMED_BY_OTHER,)),
    ("claimed_by_other_set", G, A(20, "/ws/app/lib/y.py"), fs({"/ws/app/lib"}), D, (W.CLAIMED_BY_OTHER,)),
    ("claim_on_sibling_ignored", G, A(20, "/ws/app/libx/y.py"), fs({"/ws/app/lib"}), P, ()),
    ("claims_malformed", G, A(20, "/ws/app/x"), "yes", H, (W.BAD_CLAIMS,)),
    ("claims_bad_entry", G, A(20, "/ws/app/x"), fs({"../app"}), H, (W.BAD_CLAIMS,)),
    ("claimed_flag_egress_only", G, A(20, egress="pypi.org"), True, D, (W.CLAIMED_BY_OTHER,)),
    ("parent_of_claimed_path", G, A(20, "/ws/app"), fs({"/ws/app/lib"}), D, (W.CONTAINS_CLAIMED,)),
    ("claims_subclass_hiding_entries", G, A(20, "/ws/app/lib/a"), ClaimsView({"/ws/app/lib"}), H,
     (W.BAD_CLAIMS,)),
    # Exact types (review FAIL-1 and friends).
    ("subclass_on_expiry_flip_after_ttl", flip_grant(), A(999999, "/ws/app/x"), False, H, (W.CONFIG_ERROR,)),
    ("frozenset_subclass_egress", grant(egress=HostsView({"pypi.org"})), A(20, egress="evil.net"), False,
     H, (W.CONFIG_ERROR,)),
    ("str_subclass_on_expiry_after_ttl", grant(on_expiry=EqAnyStr(W.PASS_WITHIN_GRANT)), A(500, "/ws/app/x"),
     False, H, (W.CONFIG_ERROR,)),
    ("action_subclass", G, ActionSub(20, "/ws/app/x"), False, H, (W.BAD_ACTION,)),
    # Non-ASCII hosts are refused before any case mapping.
    ("kelvin_sign_host", grant(egress=fs({"kernel.org"})), A(20, egress="\u212aernel.org"), False,
     H, (W.EGRESS_MALFORMED,)),
    ("eszett_host_not_folded", grant(egress=fs({"passau.de"})), A(20, egress="pa\u00dfau.de"), False,
     H, (W.EGRESS_MALFORMED,)),
    ("idn_ascii_form", grant(egress=fs({"xn--bcher-kva.example"})), A(20, egress="xn--bcher-kva.example"),
     False, P, ()),
    # Trust boundary: documented in the README Limitations, expected to pass.
    ("documented_self_written_grant_passes", W.Grant("mine", "/ws", ("/ws",), fs({"evil.net"}), 0,
                                                     2 ** 60, W.DENY),
     A(2 ** 40, "/ws/secrets/key", "evil.net"), False, P, ()),
]


def check_all(out=print):
    failures = 0
    for name, g, a, claims, outcome, reasons in CASES:
        d = W.decide(g, a, claims)
        ok = d.outcome == outcome and d.reasons == reasons
        failures += not ok
        out("%s %s: %s %s" % ("PASS" if ok else "FAIL", name, d.outcome, list(d.reasons)))
    out("report: %d/%d fixtures as expected" % (len(CASES) - failures, len(CASES)))
    return failures, len(CASES)


if __name__ == "__main__":
    import sys
    f, _ = check_all()
    sys.exit(1 if f else 0)
