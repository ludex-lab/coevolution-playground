"""Synthetic fixtures for w20-plan-change-notice. Run: python3 fixtures.py

DESIGN cases were written by hand while building the guard. HELD_OUT cases
are generated from fixed seeds that were not used while designing it; the
generator is deterministic, so every run sees the same worlds.
"""

import random

import plan_change as P

C, N, W = P.Change, P.Notice, P.World
OID = "harbour"
NORTH = ("survey:north", "build:north", "supply:north")
SOUTH = ("survey:south", "build:south", "supply:south")
EAST = ("survey:east", "build:east", "supply:east")
TURNS = (10, 20, 30)


def cfg(on_expiry=P.HOLD, wait_turns=1):
    return P.GuardConfig(wait_turns, on_expiry)


def world(changes, notices=(), turns=TURNS, oid=OID):
    return W(oid, tuple(changes), tuple(notices), tuple(turns))


V1 = C(1, NORTH, 0)
BASE = world([V1, C(2, SOUTH, 15)], [N("n2", OID, 2, SOUTH, 15)])

# Each design case: name, world, guard config, expected
# (baseline status, baseline obsolete count, baseline obsolete-after-ack count,
#  guard status, guard obsolete count, guard consequential targets).
DESIGN = [
    ("change_mid_step", BASE, cfg(),
     (P.DONE, 2, 2, P.DONE, 0, ("survey:north", "build:south", "supply:south"))),
    ("notice_at_turn_boundary", world([V1, C(2, SOUTH, 20)], [N("n2", OID, 2, SOUTH, 20)]), cfg(),
     (P.DONE, 2, 2, P.DONE, 0, ("survey:north", "build:south", "supply:south"))),
    ("out_of_order_notices", world([V1, C(2, SOUTH, 12), C(3, EAST, 14)],
                                   [N("n3", OID, 3, EAST, 15), N("n2", OID, 2, SOUTH, 17)]), cfg(),
     (P.DONE, 2, 2, P.DONE, 0, ("survey:north", "build:east", "supply:east"))),
    ("older_notice_cannot_roll_back", world([V1, C(2, SOUTH, 15)],
                                            [N("n2", OID, 2, SOUTH, 15), N("n1-late", OID, 1, NORTH, 25)]),
     cfg(), (P.DONE, 2, 2, P.DONE, 0, ("survey:north", "build:south", "supply:south"))),
    ("duplicate_notice", world([V1, C(2, SOUTH, 15)],
                               [N("n2", OID, 2, SOUTH, 15), N("n2", OID, 2, SOUTH, 18)]), cfg(),
     (P.DONE, 2, 2, P.DONE, 0, ("survey:north", "build:south", "supply:south"))),
    ("foreign_objective_notice_only", world([V1], [N("x2", "orchard", 2, SOUTH, 15)]), cfg(),
     (P.DONE, 0, 0, P.DONE, 0, NORTH)),
    ("foreign_notice_hides_nothing", world([V1, C(2, SOUTH, 15)], [N("x2", "orchard", 2, SOUTH, 15)]),
     cfg(P.HOLD), (P.DONE, 2, 0, "held", 0, ("survey:north",))),
    ("empty_inbox_no_change", world([V1]), cfg(), (P.DONE, 0, 0, P.DONE, 0, NORTH)),
    ("empty_inbox_silent_change", world([V1, C(2, SOUTH, 15)]), cfg(P.ESCALATE),
     (P.DONE, 2, 0, "escalated", 0, ("survey:north",))),
    ("notice_late_timeout_deny", world([V1, C(2, SOUTH, 15)], [N("n2", OID, 2, SOUTH, 99)]), cfg(P.DENY),
     (P.DONE, 2, 0, "denied", 0, ("survey:north",))),
    ("notice_late_timeout_safe_fallback", world([V1, C(2, SOUTH, 15)], [N("n2", OID, 2, SOUTH, 99)]),
     cfg(P.SAFE_FALLBACK), (P.DONE, 2, 0, "fallback", 0, ("survey:north",))),
    ("notice_late_timeout_escalate", world([V1, C(2, SOUTH, 15)], [N("n2", OID, 2, SOUTH, 99)]),
     cfg(P.ESCALATE), (P.DONE, 2, 0, "escalated", 0, ("survey:north",))),
    ("notice_late_timeout_hold", world([V1, C(2, SOUTH, 15)], [N("n2", OID, 2, SOUTH, 99)]), cfg(P.HOLD),
     (P.DONE, 2, 0, "held", 0, ("survey:north",))),
    ("notice_arrives_during_wait", world([V1, C(2, SOUTH, 15)], [N("n2", OID, 2, SOUTH, 25)],
                                         turns=(10, 20, 30, 40)), cfg(P.HOLD, 2),
     (P.DONE, 2, 1, P.DONE, 0, ("survey:north", "build:south", "supply:south"))),
    ("misleading_notice_content", world([V1, C(2, SOUTH, 15)], [N("n2", OID, 2, EAST, 15)]), cfg(P.HOLD),
     (P.DONE, 2, 0, "held", 0, ("survey:north",))),
    ("notice_ahead_of_authority", world([V1], [N("n2", OID, 2, SOUTH, 15)]), cfg(),
     (P.DONE, 0, 0, P.DONE, 0, NORTH)),
    ("zero_wait_resolves_at_once", world([V1, C(2, SOUTH, 15)], [N("n2", OID, 2, SOUTH, 25)]),
     cfg(P.DENY, 0), (P.DONE, 2, 1, "denied", 0, ("survey:north",))),
]


# --------------------------------------------------------------------------
# Held-out generator.

REGIONS = ("north", "south", "east", "west", "ridge", "delta", "upland", "coast")
VERBS = ("survey", "build", "supply", "staff", "inspect")
HELD_OUT_SEEDS = tuple(range(2001, 2013))


def generate(seed):
    """One held-out world: two to five steps, one to three authoritative
    changes issued strictly between the first and last baseline turns,
    notices that may arrive late (inside the guard's wait), out of order,
    duplicated, or mixed with notices for another objective."""
    rng = random.Random(seed)
    n = rng.randrange(2, 6)
    verbs = rng.sample(VERBS, n)
    regions = rng.sample(REGIONS, 4)
    k = rng.randrange(1, min(n, 3) + 1)
    turns = tuple(10 * (i + 1) for i in range(n + 2 * k + 2))
    last_baseline = turns[n - 1]
    times = sorted(rng.sample(range(turns[0] + 1, last_baseline), k))
    changes = [C(1, tuple("%s:%s" % (v, regions[0]) for v in verbs), 0)]
    for j, at in enumerate(times):
        changes.append(C(j + 2, tuple("%s:%s" % (v, regions[j + 1]) for v in verbs), at))
    notices = []
    for c in changes[1:]:
        delay = rng.randrange(0, 10)
        notices.append(N("s%d-v%d" % (seed, c.version), OID, c.version, c.targets, c.issued_at + delay))
        if rng.random() < 0.3:
            notices.append(N("s%d-v%d" % (seed, c.version), OID, c.version, c.targets,
                             c.issued_at + delay + 1))
        if rng.random() < 0.3:
            notices.append(N("s%d-x%d" % (seed, c.version), "orchard", c.version, c.targets,
                             c.issued_at + rng.randrange(0, 10)))
    rng.shuffle(notices)
    return world(changes, notices, turns), P.GuardConfig(2, rng.choice(P.ON_EXPIRY))


HELD_OUT = [("held_out_%d" % s,) + generate(s) for s in HELD_OUT_SEEDS]


def check_design(out=print):
    failures = 0
    for name, w, c, exp in DESIGN:
        b, g = P.run(w, P.BASELINE), P.run(w, P.NOTICE_FIRST, c)
        fb, fg = P.detect_obsolete(w, b), P.detect_obsolete(w, g)
        got = (b.status, len(fb), sum(f[2] == P.OBSOLETE_AFTER_ACK for f in fb),
               g.status, len(fg), P.final_targets(g))
        ok = got == exp
        failures += not ok
        out("%s %s: baseline %s obsolete=%d after_ack=%d | guard %s obsolete=%d" % ((
            ("PASS" if ok else "FAIL"), name) + got[:5]))
    return failures, len(DESIGN)


def check_held_out(out=print):
    failures = 0
    for name, w, c in HELD_OUT:
        b, g = P.run(w, P.BASELINE), P.run(w, P.NOTICE_FIRST, c)
        fb, fg = P.detect_obsolete(w, b), P.detect_obsolete(w, g)
        last = w.changes[-1]
        tail = [a for a in g.actions if a.kind == P.CONSEQUENTIAL][-1]
        ok = (g.status == P.DONE and not fg and len(fb) >= 1 and tail.plan_version == last.version)
        failures += not ok
        out("%s %s: baseline obsolete=%d | guard %s obsolete=%d final_version=%d/%d" % (
            "PASS" if ok else "FAIL", name, len(fb), g.status, len(fg), tail.plan_version, last.version))
    return failures, len(HELD_OUT)


if __name__ == "__main__":
    import sys
    fd, nd = check_design()
    fh, nh = check_held_out()
    print("report: design %d/%d, held-out %d/%d as expected" % (nd - fd, nd, nh - fh, nh))
    sys.exit(1 if fd or fh else 0)
