"""Synthetic fixtures for the effect-reversibility sketch. Run directly to
print a summary of fixtures 1-5. Deterministic; no network, no files."""

import sys

import reversibility as rv
from reversibility import Path, Step, World

CLOSED = "r1"
OPEN = "r2"

SCOPES = {
    "planner": ("issue_route",),
    "verifier": ("verify_route", "recall_plan", "hold_plan", "relay_plan"),
    "dispatcher": ("dispatch", "delegate_dispatch"),
    "courier": ("dispatch", "direct_dispatch"),
    "repairer": ("restore_relay", "relay_plan"),
}


def _dispatch(agent, region, exec_token="exec:dispatcher", relay=True):
    reads = ("plan:" + region, exec_token) + (("relay",) if relay else ())
    return Step(agent, "dispatch", "dispatch_interface", reads, (), region)


def base_paths():
    original = Path("original_mechanism", (
        Step("planner", "issue_route", "fresh_route", (), ("route:r1",), CLOSED),
        Step("verifier", "verify_route", "verify", ("route:r1",), ("plan:r1",), CLOSED),
        _dispatch("dispatcher", CLOSED),
    ), frozenset({"exec:dispatcher", "relay"}), "original")

    shared_memory = Path("shared_memory", (
        Step("verifier", "recall_plan", "shared_memory",
             ("memory:plan:r1",), ("plan:r1",), CLOSED),
        _dispatch("dispatcher", CLOSED),
    ), frozenset({"exec:dispatcher", "relay", "memory:plan:r1"}))

    delegate = Path("delegate", (
        Step("verifier", "recall_plan", "shared_memory",
             ("memory:plan:r1",), ("plan:r1",), CLOSED),
        Step("dispatcher", "delegate_dispatch", "delegate",
             ("exec:dispatcher",), ("exec:courier",), CLOSED),
        _dispatch("courier", CLOSED, exec_token="exec:courier"),
    ), frozenset({"exec:dispatcher", "relay", "memory:plan:r1"}))

    unauthorized_repair = Path("unauthorized_repair", (
        Step("repairer", "restore_relay", "replacement_relay", (), ("relay",), CLOSED),
        Step("verifier", "recall_plan", "shared_memory",
             ("memory:plan:r1",), ("plan:r1",), CLOSED),
        Step("repairer", "relay_plan", "replacement_relay",
             ("plan:r1", "relay"), ("plan:r1",), CLOSED),
        _dispatch("dispatcher", CLOSED),
    ), frozenset({"exec:dispatcher", "memory:plan:r1"}))

    legitimate_repair = Path("legitimate_repair", (
        Step("repairer", "restore_relay", "replacement_relay", (), ("relay",), OPEN),
        Step("verifier", "recall_plan", "shared_memory",
             ("memory:plan:r2",), ("plan:r2",), OPEN),
        _dispatch("dispatcher", OPEN),
    ), frozenset({"exec:dispatcher", "memory:plan:r2"}), "service")

    open_service = Path("open_region_service", (
        Step("planner", "issue_route", "fresh_route", (), ("route:r2",), OPEN),
        Step("verifier", "verify_route", "verify", ("route:r2",), ("plan:r2",), OPEN),
        _dispatch("dispatcher", OPEN),
    ), frozenset({"exec:dispatcher", "relay"}), "service")

    # Joint effect: the verifier only holds a plan, the repairer only restores
    # a connection, the dispatcher only uses its retained execution right.
    joint = Path("joint_three_agents", (
        Step("verifier", "hold_plan", "retained_plan",
             ("verified:r1",), ("plan:r1",), CLOSED),
        Step("repairer", "restore_relay", "replacement_relay", (), ("relay",), CLOSED),
        _dispatch("dispatcher", CLOSED),
    ), frozenset({"verified:r1", "exec:dispatcher"}), "joint")

    return [original, shared_memory, delegate, unauthorized_repair,
            legitimate_repair, open_service, joint]


ALTERNATES = ("shared_memory", "delegate", "unauthorized_repair")


def build_world():
    return World(frozenset({CLOSED}), dict(SCOPES), base_paths())


def growth_paths():
    """A sink interface learned after the restriction was set: a direct
    vehicle API that needs no relay."""
    to_closed = Path("growth_direct_dispatch", (
        Step("verifier", "recall_plan", "shared_memory",
             ("memory:plan:r1",), ("plan:r1",), CLOSED),
        Step("dispatcher", "delegate_dispatch", "delegate",
             ("exec:dispatcher",), ("exec:courier",), CLOSED),
        Step("courier", "direct_dispatch", "direct_api",
             ("plan:r1", "exec:courier"), (), CLOSED),
    ), frozenset({"exec:dispatcher", "memory:plan:r1"}), "growth")
    to_open = Path("growth_direct_open", (
        Step("verifier", "recall_plan", "shared_memory",
             ("memory:plan:r2",), ("plan:r2",), OPEN),
        Step("dispatcher", "delegate_dispatch", "delegate",
             ("exec:dispatcher",), ("exec:courier",), OPEN),
        Step("courier", "direct_dispatch", "direct_api",
             ("plan:r2", "exec:courier"), (), OPEN),
    ), frozenset({"exec:dispatcher", "memory:plan:r2"}), "growth")
    return [to_closed, to_open]


GROWTH_ACTIONS = {"direct_dispatch": "sink"}


def effect_r():
    return rv.restrict_effect(rv.PROHIBITED, ("dispatch",))


def mechanism_r():
    return rv.restrict_mechanism("fresh_route", (CLOSED,))


# ---------------------------------------------------------------- fixtures

def fixture_1():
    w = build_world()
    rep = rv.detect(w, effect_r())
    alts = [rep.by_name(n) for n in ALTERNATES]
    ok = (all(not r.prohibited and r.held_at >= 0 for r in alts)
          and rep.prohibited_count == 0 and rv.rare_bar(rep))
    return ok, ("effect-keyed: alternates held %d/%d; prohibited %d/%d paths"
                % (sum(r.held_at >= 0 for r in alts), len(alts),
                   rep.prohibited_count, len(rep.paths)))


def fixture_2():
    w = build_world()
    rep = rv.detect(w, mechanism_r())
    original = rep.by_name("original_mechanism")
    leaking_alts = [n for n in ALTERNATES if rep.by_name(n).prohibited]
    compliant = rv.compliance_check_original(w, mechanism_r())
    ok = (original.held_at >= 0 and not original.prohibited
          and len(leaking_alts) >= 1 and compliant and not rv.rare_bar(rep))
    return ok, ("mechanism-only: original held; compliance check passes=%s; "
                "still leaking: %s" % (compliant, ", ".join(rep.leaking())))


def fixture_3():
    w = build_world()
    rep = rv.detect(w, effect_r())
    lr = rep.by_name("legitimate_repair")
    os_ = rep.by_name("open_region_service")
    ok = (lr.held_at < 0 and lr.stalled_at < 0 and not lr.prohibited
          and rv.RESTORE in lr.effects and rv.SERVE_OPEN in lr.effects
          and os_.held_at < 0 and rv.SERVE_OPEN in os_.effects)
    return ok, ("service under effect-keyed: legitimate_repair effects=%s; "
                "open_region_service effects=%s" % (list(lr.effects), list(os_.effects)))


def per_agent_reports(world, path):
    """Run each agent's own steps alone (same start state)."""
    out = {}
    for agent in sorted({s.agent for s in path.steps}):
        sub = Path(path.name + ":" + agent,
                   tuple(s for s in path.steps if s.agent == agent),
                   path.start, path.kind)
        out[agent] = rv.run_path(world, sub)
    return out


def fixture_4():
    w = build_world()
    p = w.path("joint_three_agents")
    unrestricted = rv.run_path(w, p)
    alone = per_agent_reports(w, p)
    restricted = rv.run_path(w, p, effect_r())
    mech = rv.run_path(w, p, mechanism_r())
    ok = (all(unrestricted.local_ok) and unrestricted.prohibited
          and not any(r.prohibited for r in alone.values())
          and restricted.held_at >= 0 and not restricted.prohibited
          and mech.prohibited)
    return ok, ("joint: local checks %d/%d in scope; alone prohibited=%s; "
                "together unrestricted prohibited=%s; effect-keyed held=%s; "
                "mechanism-only prohibited=%s"
                % (sum(unrestricted.local_ok), len(unrestricted.local_ok),
                   any(r.prohibited for r in alone.values()),
                   unrestricted.prohibited, restricted.held_at >= 0, mech.prohibited))


def fixture_5():
    w = build_world()
    before = len(w.paths)
    first = rv.recheck_update(w, effect_r(), growth_paths(), GROWTH_ACTIONS)
    unchanged = len(w.paths) == before and "direct_dispatch" not in w.actions
    wider = rv.extend_restriction(effect_r(), ("direct_dispatch",))
    second = rv.recheck_update(w, wider, growth_paths(), GROWTH_ACTIONS)
    after = rv.detect(w, wider)
    contrast = build_world()
    rv.register_unchecked(contrast, growth_paths(), GROWTH_ACTIONS)
    silent = rv.detect(contrast, effect_r()).by_name("growth_direct_dispatch")
    ok = (first.status == "fail_closed"
          and "flag:prohibited:growth_direct_dispatch" in first.flags
          and unchanged and second.status == "registered"
          and after.prohibited_count == 0
          and rv.SERVE_OPEN in after.by_name("growth_direct_open").effects
          and silent.prohibited)
    return ok, ("growth: recheck under old gate -> %s %s; after extending gate -> %s, "
                "prohibited %d/%d; unchecked registration leaks=%s"
                % (first.status, list(first.flags), second.status,
                   after.prohibited_count, len(after.paths), silent.prohibited))


FIXTURES = [
    {"id": 1, "title": "effect-keyed restriction holds alternate paths", "fn": fixture_1},
    {"id": 2, "title": "mechanism-only restriction leaves a leaking path", "fn": fixture_2},
    {"id": 3, "title": "required service / legitimate repair still succeeds", "fn": fixture_3},
    {"id": 4, "title": "joint effect from locally in-scope steps is caught", "fn": fixture_4},
    {"id": 5, "title": "growth step is rechecked and fails closed", "fn": fixture_5},
]


def run_all():
    return [(fx["id"], fx["title"]) + fx["fn"]() for fx in FIXTURES]


def summary():
    lines = []
    for fid, title, ok, detail in run_all():
        lines.append("fixture %d [%s] %s\n    %s"
                     % (fid, "PASS" if ok else "FAIL", title, detail))
    w = build_world()
    c = rv.compare(w, effect_r(), mechanism_r())
    lines.append("compare: effect_keyed prohibited=%d service=%d | "
                 "mechanism_only prohibited=%d service=%d compliance_check_original=%s"
                 % (c["effect_keyed"]["prohibited"], c["effect_keyed"]["service"],
                    c["mechanism_only"]["prohibited"], c["mechanism_only"]["service"],
                    c["mechanism_only"]["compliance_check_original"]))
    lines.append("note: 0 prohibited on these enumerated toy paths meets the "
                 "'rare while maintaining required service' bar here; it is not "
                 "a claim about future growth (see fixture 5).")
    return "\n".join(lines)


def main():
    print(summary())
    return 0 if all(r[2] for r in run_all()) else 1


if __name__ == "__main__":
    sys.exit(main())
