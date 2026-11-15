"""Synthetic fixtures for w20-checkable-rulebook. Run: python3 fixtures.py

DESIGN cases were written by hand while building the gate. UNIVERSES are
small finite program sets. Their ground truth is labelled here, first and
without the gate: each program is a stem plus a repeating cycle, so the
position of its first forbidden event and its first answer (or that there
is none, ever) is read off that structure directly.

REGRESSION universes come from fixed seeds. Their labels use the same
first-event predicate the gate applies to a prefix, so (d) on them holds by
construction: they are a regression and property set for prefix() and the
list builder, not evidence for the paper's result. DUPLICATE universes are
the same seeds with a second program reusing an existing id; the list
builder must refuse them in either order. NEAR_MISS, LONG_PROGRAMS and
LATE_VIOLATORS are hand-written worlds for exact-token matching and for long
clean prefixes.
"""

import random
import sys

import rulebook as R

P = R.Program
FORBIDDEN = ("delete", "leak")
ANSWER = "answer"
BENIGN = ("work", "wait", "read")
EVENTS = BENIGN + FORBIDDEN + (ANSWER,)
TOOL = "run_program"
ACTIONS = {TOOL: {"risk": "high", "safe_fallback": "dry_run"}, "dry_run": {"risk": "read_only"}}


def rule(on_expiry=R.HOLD, ladder=("oncall", "lead"), deadline_s=60, **extra):
    body = {"ladder": list(ladder), "deadline_s": deadline_s, **extra}
    if on_expiry is not None:
        body["on_expiry"] = on_expiry
    return body


def gate(on_expiry=R.HOLD, actions=None, **kw):
    return R.Gate(FORBIDDEN, ANSWER, rule(on_expiry, **kw), TOOL, ACTIONS if actions is None else actions)


def prog(pid, stem, cycle=("work",)):
    return P(pid, tuple(stem), tuple(cycle))


# --------------------------------------------------------- ground truth

def first_at(program, events):
    """First position of any of events in the infinite trace, or None (never)."""
    for i, e in enumerate(program.stem):
        if e in events:
            return i
    for j, e in enumerate(program.cycle):
        if e in events:
            return len(program.stem) + j
    return None


MUST_ADMIT, MUST_REFUSE, UNDETERMINED = "must_admit", "must_refuse", "undetermined"


def label(program, horizon):
    """Ground truth relative to what a horizon-step record can settle.

    must_refuse: a forbidden event happens before the horizon.
    must_admit: no forbidden event ever, and an answer before the horizon.
    undetermined: everything else (a violation only at or after the horizon,
    or an answer only at or after it, or never).
    """
    bad, ans = first_at(program, FORBIDDEN), first_at(program, (ANSWER,))
    if bad is not None and bad < horizon:
        return MUST_REFUSE
    if bad is None and ans is not None and ans < horizon:
        return MUST_ADMIT
    return UNDETERMINED


def truly_compliant(program):
    return first_at(program, FORBIDDEN) is None and first_at(program, (ANSWER,)) is not None


# --------------------------------------------------------------- design

CLEAN4 = ("work", "answer", "work", "read")
# name, program, budget, expected (status, violation_at, clean_through, answered_at, expiry)
DESIGN = [
    ("violation_in_prefix", prog("p1", ("work", "delete", "answer")), 3, (R.REFUSE, 1, None, None, None)),
    ("violation_first_step", prog("p2", ("leak",)), 1, (R.REFUSE, 0, None, None, None)),
    ("violation_in_cycle", prog("p3", ("work", "answer"), ("read", "leak")), 6, (R.REFUSE, 3, None, None, None)),
    ("clean_answered", prog("p4", CLEAN4), 4, (R.SCOPED, None, 4, 1, None)),
    ("clean_then_violation_next", prog("p5", CLEAN4 + ("delete",)), 4, (R.SCOPED, None, 4, 1, None)),
    ("same_program_one_more_step", prog("p5", CLEAN4 + ("delete",)), 5, (R.REFUSE, 4, None, None, None)),
    ("no_answer_hold", prog("p6", ("work", "wait")), 6, (R.UNSETTLED, None, None, None, R.HELD)),
    ("answer_just_after_budget", prog("p7", ("work", "wait", "answer")), 2, (R.UNSETTLED, None, None, None, R.HELD)),
    ("zero_budget", prog("p8", ("answer",)), 0, (R.UNSETTLED, None, None, None, R.HELD)),
    ("violation_beats_answer", prog("p9", ("answer", "leak")), 2, (R.REFUSE, 1, None, None, None)),
]

# ------------------------------------------------------------ universes


def design_universe():
    """A small hand-made universe at horizon 4 with one program per kind."""
    progs = (
        prog("u-admit", ("work", "answer")),
        prog("u-admit-cycle", ("work",), ("read", "answer")),
        prog("u-admit-edge", ("work", "wait", "read", "answer")),
        prog("u-refuse", ("delete", "answer")),
        prog("u-refuse-edge", ("work", "answer", "wait", "leak")),
        prog("u-refuse-cycle", ("answer",), ("work", "leak")),
        prog("u-late-violation", ("answer", "work", "wait", "read", "delete")),
        prog("u-late-violation-cycle", ("answer", "work", "read"), ("wait", "leak")),
        prog("u-late-answer", ("work", "wait", "read", "work", "answer")),
        prog("u-never-answers", ("work",), ("wait",)),
        prog("u-never-anything", (), ("read",)),
    )
    return "design_universe", progs, 4


REGRESSION_SEEDS = tuple(range(4001, 4013))


def generate(seed, duplicates=False):
    """A universe: (name, programs, horizon). Random lasso programs plus
    forced boundary programs (violation or answer exactly at horizon-1 and at
    horizon, violations only in the cycle). With duplicates=True, two extra
    programs reuse ids already in the universe: a violating program takes the
    id of the edge must-admit program, and a clean answered one takes the id
    of the edge must-refuse program."""
    rng = random.Random(seed)
    h = rng.randint(3, 9)
    progs = []

    def benign(k):
        return [rng.choice(BENIGN) for _ in range(k)]

    def put(name, stem, cycle):
        progs.append(prog("s%d-%s" % (seed, name), stem, cycle))

    for k in range(rng.randint(14, 22)):
        stem = [rng.choice(EVENTS) if rng.random() < 0.25 else rng.choice(BENIGN)
                for _ in range(rng.randint(0, h + 3))]
        cycle = [rng.choice(EVENTS) if rng.random() < 0.15 else rng.choice(BENIGN)
                 for _ in range(rng.randint(1, 4))]
        put("r%02d" % k, stem, cycle)
    a = rng.randrange(h)
    put("admit-edge", benign(h - 1) + [ANSWER], benign(2))
    put("admit-any", benign(a) + [ANSWER] + benign(rng.randint(0, 3)), benign(rng.randint(1, 3)))
    put("refuse-edge", benign(a) + [ANSWER] + benign(h - 2 - a) + [rng.choice(FORBIDDEN)]
        if a <= h - 2 else benign(h - 1) + [rng.choice(FORBIDDEN)], benign(1))
    put("late-violation", benign(a) + [ANSWER] + benign(h - 1 - a) + [rng.choice(FORBIDDEN)], benign(1))
    put("late-answer", benign(h) + [ANSWER], benign(1))
    put("never-answers", benign(rng.randint(0, h)), benign(rng.randint(1, 3)))
    put("cycle-violation", [ANSWER], benign(rng.randint(0, 2)) + [rng.choice(FORBIDDEN)])
    if duplicates:
        put("admit-edge", benign(rng.randrange(h)) + [rng.choice(FORBIDDEN), ANSWER], benign(1))
        put("refuse-edge", [ANSWER], benign(2))
    rng.shuffle(progs)
    return ("duplicate_%d" if duplicates else "regression_%d") % seed, tuple(progs), h


REGRESSION = [generate(s) for s in REGRESSION_SEEDS]
DUPLICATE = [generate(s, duplicates=True) for s in REGRESSION_SEEDS]


def check_universe(name, programs, horizon, g=None, builder=None):
    """(misses, intrusions, counts): must-admit programs missing from the list
    and must-refuse programs on it. Labels are kept per program object, not
    per id, so when two programs share an id and that id is listed, both
    programs count as listed and the result does not depend on their order.
    counts["rejected"] is 1 when the builder returned no list."""
    g = gate() if g is None else g
    lst = (R.build_list if builder is None else builder)(programs, g, horizon)
    listed = set() if lst is None else {c.program_id for c in lst}
    labels = [(p, label(p, horizon)) for p in programs]
    misses = sorted(p.program_id for p, lab in labels if lab == MUST_ADMIT and p.program_id not in listed)
    intrusions = sorted(p.program_id for p, lab in labels if lab == MUST_REFUSE and p.program_id in listed)
    undet = [p for p, lab in labels if lab == UNDETERMINED]
    ids = [p.program_id for p in programs]
    counts = {
        MUST_ADMIT: sum(lab == MUST_ADMIT for _, lab in labels),
        MUST_REFUSE: sum(lab == MUST_REFUSE for _, lab in labels),
        UNDETERMINED: len(undet),
        "undetermined_listed": sum(p.program_id in listed for p in undet),
        "listed_not_compliant": sum(p.program_id in listed and not truly_compliant(p) for p in programs),
        "duplicate_ids": len(ids) - len(set(ids)),
        "rejected": int(lst is None),
    }
    return misses, intrusions, counts


# ------------------------------------------------- hand-written worlds

# Events are exact tokens. A near-miss spelling is a different event: the
# gate neither folds case nor strips spaces. Expected statuses here are
# written by hand, not computed by label(), so the oracle does not share the
# gate's tokenisation. (name, stem, cycle, budget, expected status)
NEAR_MISS = [
    ("capital_delete", ("Delete", "answer"), ("work",), 2, R.SCOPED),
    ("upper_leak", ("LEAK", "answer"), ("work",), 2, R.SCOPED),
    ("trailing_space_leak", ("leak ", "answer"), ("work",), 2, R.SCOPED),
    ("leading_space_delete", (" delete", "answer"), ("work",), 2, R.SCOPED),
    ("longer_word", ("deleted", "answer"), ("work",), 2, R.SCOPED),
    ("capital_answer", ("work", "Answer"), ("work",), 2, R.UNSETTLED),
    ("trailing_space_answer", ("work", "answer "), ("work",), 2, R.UNSETTLED),
    ("exact_leak_in_cycle", ("answer",), ("Leak", "leak"), 3, R.REFUSE),
]

# Clean programs for the long-prefix check of (b). LONG_PREFIX is at least
# four times the longest stem plus cycle among them.
LONG_PREFIX = 400
LONG_PROGRAMS = [
    prog("long-answer-then-work", ("answer",), ("work",)),
    prog("long-never-answers", (), ("read",)),
    prog("long-answer-in-cycle", ("work",), ("answer", "read")),
    prog("long-clean4", ("work", "answer", "work", "read")),
    prog("long-always-answers", ("answer",), ("answer",)),
    prog("long-stem", ("work",) * 40 + ("answer",), ("wait", "read") * 29 + ("answer",)),
]


def clean_programs(seed, k=12):
    """Random lasso programs with no forbidden event (stem up to 50, cycle up
    to 49 events), for the long-prefix check."""
    rng = random.Random(seed)
    out = []
    for i in range(k):
        stem = tuple(rng.choice(BENIGN + (ANSWER,)) for _ in range(rng.randint(0, 50)))
        cycle = tuple(rng.choice(BENIGN + (ANSWER,)) for _ in range(rng.randint(1, 49)))
        out.append(prog("clean-%d-%02d" % (seed, i), stem, cycle))
    return out


LONG_PROGRAMS += clean_programs(4117)

# Programs that are clean for a long time and then violate.
# (program, first forbidden position)
LATE_VIOLATORS = [
    (prog("late-30", ("answer",) + ("work",) * 29 + ("delete",)), 30),
    (prog("late-cycle-120", ("answer",) + ("read",) * 117, ("work", "work", "leak")), 120),
    (prog("late-390", ("work", "answer") + ("wait",) * 388 + ("leak",)), 390),
]


def check_design(out=print):
    fails = 0
    g = gate()
    for name, p, n, exp in DESIGN:
        v = R.evaluate(p, g, n)
        c = v.certificate
        got = (v.status, v.violation_at, c.clean_through if c else None, c.answered_at if c else None, v.expiry)
        ok = got == exp
        fails += not ok
        out("%s %s" % ("PASS" if ok else "FAIL", name) + ("" if ok else " got %r" % (got,)))
    return fails, len(DESIGN)


def check_universes(out=print):
    """Plain universes must give a list with no miss and no intrusion.
    DUPLICATE universes, in the generated order and reversed, must be
    refused as a whole (no list) and must not count a must-refuse program as
    listed."""
    fails, totals, n = 0, {False: {}, True: {}}, 0
    worlds = [(u, False) for u in [design_universe()] + REGRESSION]
    worlds += [(u, True) for u in DUPLICATE] + [((u[0] + "_reversed", u[1][::-1], u[2]), True) for u in DUPLICATE]
    for (name, progs, h), must_reject in worlds:
        misses, intr, counts = check_universe(name, progs, h)
        if must_reject:
            bad = not counts["rejected"] or not counts["duplicate_ids"] or intr
        else:
            bad = counts["rejected"] or misses or intr
        fails += bool(bad)
        n += 1
        for k, v in counts.items():
            totals[must_reject][k] = totals[must_reject].get(k, 0) + v
        out("%s %s (h=%d, %d programs, %s)" % ("FAIL" if bad else "PASS", name, h, len(progs),
                                              ", ".join("%s %d" % kv for kv in counts.items()))
            + ("" if not bad else " misses %r intrusions %r" % (misses, intr)))
    for dup, kind in ((False, "plain"), (True, "duplicate")):
        out("universes total (%s): " % kind + ", ".join("%s %d" % kv for kv in totals[dup].items()))
    return fails, n


def check_near_miss(out=print):
    fails = 0
    g = gate()
    for name, stem, cycle, n, exp in NEAR_MISS:
        got = R.evaluate(prog("nm-" + name, stem, cycle), g, n).status
        ok = got == exp
        fails += not ok
        out("%s near_miss %s" % ("PASS" if ok else "FAIL", name) + ("" if ok else " got %r" % got))
    return fails, len(NEAR_MISS)


if __name__ == "__main__":
    fd, nd = check_design()
    fu, nu = check_universes()
    fn, nn = check_near_miss()
    print("report: design %d/%d, universes %d/%d, near-miss %d/%d as expected"
          % (nd - fd, nd, nu - fu, nu, nn - fn, nn))
    sys.exit(1 if fd or fu or fn else 0)
