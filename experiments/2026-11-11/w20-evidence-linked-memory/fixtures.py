"""Synthetic fixtures for w20-evidence-linked-memory. Run: python3 fixtures.py

DESIGN cases were written by hand while building the read rule. REGRESSION
worlds come from a generator with fixed seeds. The generator's categories
and their expected outcomes were written by the same author as the rule, so
the regression worlds are a regression and property set, not an independent
benchmark: they pin behaviour, they do not measure generalisation. Several
categories are adversarial on purpose (a run label that contradicts the
insight, a failed run whose ok step is not the answer, a failed lesson that
sorts first, a dangling link beside a good same-key chain, a trajectory key
that differs only in case, a verb conflict without detail).
"""

import random
import sys

import evidence_memory as E

ABSENT = object()  # field left out of the record altogether
KEY = "gate"
RIGHT, WRONG, OTHER = ("lift", "north"), ("lift", "south"), ("turn", "east")
NONE, ALL, DONE = E.EMPTY_MEMORY, E.AGENTS, E.DONE


def step(action, result):
    return [action[0], action[1], result]


def lesson(iid, action, outcome=E.SUCCESS, steps=(), key=KEY, arg=ABSENT, link="auto",
           traj="auto", traj_key=None, run="auto"):
    """Records for one insight with its summary and trajectory.

    outcome: the insight's own copy of the run label; ABSENT leaves it out.
    run: the summary's run label; "auto" writes "success" when outcome is
    "success" and "failure" otherwise, ABSENT leaves it out, any string is
    written as given. arg: ABSENT uses the action's own argument, None leaves
    the field out, any string is written as given. link (insight -> summary)
    and traj (summary -> trajectory): "auto" writes the hop; None leaves the
    link field out while the target record is still written; "missing"
    points at an id that has no record. traj may also be "unreadable": the
    trajectory is written with steps that cannot be read.
    """
    ins = {"id": iid, "key": key, "verb": action[0]}
    a = action[1] if arg is ABSENT else arg
    if a is not None:
        ins["arg"] = a
    if outcome is not ABSENT:
        ins["outcome"] = outcome
    sid, tid = "s-" + iid, "t-" + iid
    summ = {"id": sid, "why": "synthetic"}
    if run == "auto":
        summ["outcome"] = E.SUCCESS if outcome == E.SUCCESS else "failure"
    elif run is not ABSENT:
        summ["outcome"] = run
    raw = "binary blob" if traj == "unreadable" else [step(a_, r) for a_, r in steps]
    trj = {"id": tid, "key": traj_key or key, "steps": raw}
    out = {"insights": [ins], "summaries": [summ], "trajectories": [trj]}
    if link == "missing":
        ins["summary"] = "s-gone-" + iid
        out["summaries"] = []
    elif link is not None:
        ins["summary"] = sid
    if traj == "missing":
        summ["trajectory"] = "t-gone-" + iid
        out["trajectories"] = []
    elif traj is not None:
        summ["trajectory"] = tid
    return out


def merge(*parts):
    out = {"insights": [], "summaries": [], "trajectories": []}
    for p in parts:
        for k in out:
            out[k].extend(p[k])
    return out


def task(answer, default, tid="t1", key=KEY):
    return E.Task(tid, key, answer, default)


OK, ERR = E.OK, E.ERROR
SO = E.SUCCESS

# Each design case: name, records, task, on_unresolved, expected
# {empty passed, bare passed, linked (status, passed, descends, verdicts)}.
DESIGN = [
    # (a) memory-induced degradation: no memory solves it, the bare lesson breaks it.
    ("degradation_failed_lesson", lesson("i1", WRONG, "failure", [(WRONG, ERR)]),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, True, 1, {"i1": E.REJECTED}))),
    ("degradation_missing_outcome", lesson("i1", WRONG, ABSENT, [(WRONG, ERR), (RIGHT, OK)], run=SO),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, True, 1, {"i1": E.CORRECTED}))),
    # (b) each trigger alone.
    ("trigger_missing_detail", lesson("i1", RIGHT, SO, [(WRONG, ERR), (RIGHT, OK)], arg=None),
     task(RIGHT, ("lift", "west")), E.HOLD,
     (False, False, (DONE, True, 1, {"i1": E.FILLED}))),
    ("trigger_conflict", merge(lesson("i1", WRONG, SO, [(WRONG, ERR), (RIGHT, OK)]),
                               lesson("i2", RIGHT, SO, [(RIGHT, OK)])),
     task(RIGHT, OTHER), E.HOLD,
     (False, False, (DONE, True, 1, {"i1": E.CORRECTED, "i2": E.CONFIRMED}))),
    ("conflict_second_rejected", merge(lesson("i1", RIGHT, SO, [(RIGHT, OK)]),
                                       lesson("i2", WRONG, SO, [(WRONG, OK)], key="bridge"),
                                       {"insights": [{"id": "i3", "key": KEY, "verb": "lift", "arg": "south",
                                                      "outcome": SO, "summary": "s-i1"}],
                                        "summaries": [], "trajectories": []}),
     task(RIGHT, OTHER), E.HOLD,
     (False, True, (DONE, True, 1, {"i1": E.CONFIRMED, "i3": E.REJECTED}))),
    ("trigger_failed_origin", lesson("i1", WRONG, "failure", [(WRONG, ERR), (RIGHT, OK)]),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, True, 1, {"i1": E.REJECTED}))),
    # (c) the trajectory wins.
    ("success_run_corrects", lesson("i1", WRONG, "failure", [(WRONG, ERR), (RIGHT, OK)], run=SO),
     task(RIGHT, OTHER), E.HOLD,
     (False, False, (DONE, True, 1, {"i1": E.CORRECTED}))),
    ("trajectory_rejects", lesson("i1", WRONG, "failure", [(WRONG, ERR), (OTHER, ERR)]),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, True, 1, {"i1": E.REJECTED}))),
    ("trajectory_overrides_clean", merge(lesson("i1", WRONG),
                                         lesson("i2", ("lift", "x"), SO, [(WRONG, ERR), (RIGHT, OK)],
                                                arg=None)),
     task(RIGHT, OTHER), E.HOLD,
     (False, False, (DONE, True, 1, {"i1": E.REJECTED, "i2": E.FILLED}))),
    ("success_run_without_ok_step", lesson("i1", OTHER, SO, [(OTHER, ERR)], arg=None),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, True, 1, {"i1": E.REJECTED}))),
    ("two_rejected_then_default", merge(lesson("i1", WRONG, "failure", [(WRONG, ERR)]),
                                        lesson("i2", OTHER, ABSENT, [(OTHER, ERR)])),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, True, 2, {"i1": E.REJECTED, "i2": E.REJECTED}))),
    # (c) adversarial: a failed run's ok step is not the answer (F2a).
    ("failed_run_ok_step_is_wrong", lesson("i1", WRONG, "failure", [(WRONG, OK)]),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, True, 1, {"i1": E.REJECTED}))),
    ("failed_run_ok_step_misleads", lesson("i1", OTHER, "failure", [(OTHER, ERR), (WRONG, OK)]),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, True, 1, {"i1": E.REJECTED}))),
    # (c) adversarial: a failed lesson sorts before a correct success lesson (F2b).
    ("failed_lesson_sorts_first", merge(lesson("i0", WRONG, "failure", [(RIGHT, ERR), (WRONG, OK)]),
                                        lesson("i1", RIGHT, SO, [(RIGHT, OK)])),
     task(RIGHT, OTHER), E.HOLD,
     (False, False, (DONE, True, 2, {"i0": E.REJECTED, "i1": E.CONFIRMED}))),
    # (d) a clean insight is used as is.
    ("clean_insight", lesson("i1", RIGHT, SO, [(RIGHT, OK)]),
     task(RIGHT, OTHER), E.HOLD,
     (False, True, (DONE, True, 0, {"i1": E.FOLLOWED}))),
    ("clean_but_wrong_is_a_limit", lesson("i1", WRONG, SO, [(WRONG, ERR), (RIGHT, OK)]),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, False, 0, {"i1": E.FOLLOWED}))),
    ("outcome_wrong_case_descends", lesson("i1", RIGHT, "Success", [(RIGHT, OK)], run=SO),
     task(RIGHT, OTHER), E.HOLD,
     (False, True, (DONE, True, 1, {"i1": E.CONFIRMED}))),
    # (d) near-miss labels on the insight copy (F5): never read as "success".
    ("outcome_successful_descends", lesson("i1", WRONG, "successful", [(WRONG, ERR), (RIGHT, OK)], run=SO),
     task(RIGHT, OTHER), E.HOLD,
     (False, False, (DONE, True, 1, {"i1": E.CORRECTED}))),
    ("outcome_trailing_space_descends", lesson("i1", WRONG, "success ", [(WRONG, ERR), (RIGHT, OK)], run=SO),
     task(RIGHT, OTHER), E.HOLD,
     (False, False, (DONE, True, 1, {"i1": E.CORRECTED}))),
    # (d) the run label comes from the summary, not the insight (F1).
    ("run_label_failure_beats_claim", lesson("i1", WRONG, SO, [(WRONG, OK)], run="failure"),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, True, 1, {"i1": E.REJECTED}))),
    ("run_label_absent_beats_claim", lesson("i1", WRONG, SO, [(WRONG, OK)], run=ABSENT),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, True, 1, {"i1": E.REJECTED}))),
    ("run_label_successful_beats_claim", lesson("i1", WRONG, SO, [(WRONG, OK)], run="successful"),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, True, 1, {"i1": E.REJECTED}))),
    ("run_label_trailing_space_beats_claim", lesson("i1", WRONG, SO, [(WRONG, OK)], run="success "),
     task(RIGHT, RIGHT), E.HOLD,
     (True, False, (DONE, True, 1, {"i1": E.REJECTED}))),
    # (b)/(c) different verbs conflict even when one has no detail (F5).
    ("verb_conflict_without_detail", merge(lesson("i1", OTHER, SO, [(OTHER, ERR), (RIGHT, OK)]),
                                           lesson("i2", RIGHT, SO, [], arg=None)),
     task(RIGHT, ("lift", "west")), E.HOLD,
     (False, False, (DONE, True, 1, {"i1": E.CORRECTED, "i2": E.CONFIRMED}))),
    ("empty_arg_is_missing_detail", lesson("i1", RIGHT, SO, [(RIGHT, OK)], arg=""),
     task(RIGHT, ("lift", "west")), E.HOLD,
     (False, False, (DONE, True, 1, {"i1": E.FILLED}))),
    ("other_key_is_ignored", lesson("i1", WRONG, key="bridge"),
     task(RIGHT, RIGHT), E.HOLD,
     (True, True, (DONE, True, 0, {}))),
    ("other_case_key_is_ignored", lesson("i1", WRONG, key="GATE"),
     task(RIGHT, RIGHT), E.HOLD,
     (True, True, (DONE, True, 0, {}))),
    # (e) unresolved links resolve only through on_unresolved.
    ("no_summary_field", lesson("i1", RIGHT, link=None), task(RIGHT, OTHER), E.HOLD,
     (False, True, ("held", False, 0, {"i1": E.UNRESOLVED}))),
    ("summary_missing", lesson("i1", RIGHT, link="missing"), task(RIGHT, OTHER), E.DENY,
     (False, True, ("denied", False, 0, {"i1": E.UNRESOLVED}))),
    ("no_trajectory_field", lesson("i1", RIGHT, traj=None), task(RIGHT, OTHER), E.ESCALATE,
     (False, True, ("escalated", False, 0, {"i1": E.UNRESOLVED}))),
    ("trajectory_missing", lesson("i1", WRONG, traj="missing"), task(RIGHT, RIGHT), E.SAFE_FALLBACK,
     (True, False, ("fallback", True, 0, {"i1": E.UNRESOLVED}))),
    ("trajectory_unreadable", lesson("i1", WRONG, "failure", traj="unreadable"), task(RIGHT, OTHER),
     E.SAFE_FALLBACK, (False, False, ("fallback", False, 0, {"i1": E.UNRESOLVED}))),
    ("trajectory_for_other_key", lesson("i1", WRONG, "failure", [(RIGHT, OK)], traj_key="bridge"),
     task(RIGHT, OTHER), E.HOLD, (False, False, ("held", False, 0, {"i1": E.UNRESOLVED}))),
    # (e) adversarial (F3): the trajectory key differs only in case.
    ("trajectory_key_case_differs", lesson("i1", WRONG, SO, [(WRONG, OK)], traj_key="GATE"),
     task(RIGHT, OTHER), E.HOLD, (False, False, ("held", False, 0, {"i1": E.UNRESOLVED}))),
    ("one_dangling_among_two", merge(lesson("i1", RIGHT, SO, [(RIGHT, OK)]),
                                     lesson("i2", RIGHT, traj="missing")),
     task(RIGHT, OTHER), E.DENY, (False, True, ("denied", False, 0, {"i2": E.UNRESOLVED}))),
    # (e) adversarial (F3): a dangling summary link beside a good same-key chain.
    ("summary_missing_beside_good_chain", merge(lesson("i1", RIGHT, SO, [(RIGHT, OK)]),
                                                lesson("i2", WRONG, SO, [(WRONG, OK)], link="missing")),
     task(RIGHT, OTHER), E.DENY, (False, True, ("denied", False, 0, {"i2": E.UNRESOLVED}))),
]

# ------------------------------------------------------- regression worlds

REGRESSION_SEEDS = tuple(range(3001, 3013))
VERBS = ("lift", "turn", "press", "slide")
ARGS = ("north", "south", "east", "west", "up", "down")
NEAR_MISS = ("Success", "SUCCESS", " success", "", "successful", "success ")
CATEGORIES = ("none", "clean_right", "clean_wrong", "missing_detail", "missing_outcome",
              "failed_origin_rejected", "failed_run_ok_truth", "conflict", "outcome_case",
              "contradicted_clean", "dangling", "two_failed", "run_label_mismatch",
              "failed_run_misleads", "failed_sorts_first", "verb_conflict_no_detail",
              "dangling_beside_good")
LINK_FAULTS = ("no_summary_field", "summary_missing", "no_trajectory_field", "trajectory_missing",
               "unreadable", "other_key", "key_case")


def _other(rng, action, same_verb=False):
    while True:
        b = (action[0] if same_verb else rng.choice(VERBS), rng.choice(ARGS))
        if b != action:
            return b


def _other_verb(rng, action):
    while True:
        b = (rng.choice(VERBS), rng.choice(ARGS))
        if b[0] != action[0]:
            return b


def _noise(rng, truth, n):
    return [(_other(rng, truth), ERR) for _ in range(n)]


def generate(seed):
    """One world: (records, tasks, on_unresolved, expected).

    expected[task_id] = (category, empty passed, bare passed,
                         linked status, linked passed, linked descends).
    Runs labelled "success" are honest about their own run: their last ok
    step is the key's true action. Failed runs need not be: in the
    failed_run_misleads and failed_sorts_first categories a failed run
    records an ok step for a wrong action. Categories are shuffled and some
    appear twice; insight ids are random, so the descend order is not the
    build order, except where a category fixes which lesson sorts first.
    """
    rng = random.Random(seed)
    oe = rng.choice(E.ON_UNRESOLVED)
    cats = list(CATEGORIES) + [rng.choice(CATEGORIES) for _ in range(4)]
    rng.shuffle(cats)
    parts, tasks, expected = [], [], {}
    faults_used = 0
    ids = rng.sample(range(100, 1000), 3 * len(cats) + 4)
    for n, cat in enumerate(cats):
        key, tid = "k%02d" % n, "task%02d" % n
        truth = (rng.choice(VERBS), rng.choice(ARGS))
        default = truth if rng.random() < 0.5 else _other(rng, truth)
        dflt_pass = default == truth
        iid = lambda: "i%d" % ids.pop()
        wrong = _other(rng, truth)
        honest = lambda tried: _noise(rng, truth, rng.randint(0, 2)) + tried
        if cat == "none":
            rec, bare, st, lp, d = lesson(iid(), wrong, key="x" + key), dflt_pass, DONE, dflt_pass, 0
        elif cat == "clean_right":
            rec, bare, st, lp, d = lesson(iid(), truth, SO, honest([(truth, OK)]), key=key), True, DONE, True, 0
        elif cat == "clean_wrong":
            rec = lesson(iid(), wrong, SO, honest([(wrong, ERR), (truth, OK)]), key=key)
            bare, st, lp, d = False, DONE, False, 0
        elif cat == "missing_detail":
            rec = lesson(iid(), truth, SO, honest([(truth, OK)]), key=key, arg=rng.choice([None, ""]))
            bare, st, lp, d = (truth[0], default[1]) == truth, DONE, True, 1
        elif cat == "missing_outcome":
            rec = lesson(iid(), wrong, ABSENT, honest([(wrong, ERR), (truth, OK)]), key=key, run=SO)
            bare, st, lp, d = False, DONE, True, 1
        elif cat == "outcome_case":
            rec = lesson(iid(), wrong, rng.choice(NEAR_MISS), honest([(wrong, ERR), (truth, OK)]), key=key,
                         run=SO)
            bare, st, lp, d = False, DONE, True, 1
        elif cat == "failed_origin_rejected":
            rec = lesson(iid(), wrong, "failure", honest([(wrong, ERR)]), key=key)
            bare, st, lp, d = False, DONE, dflt_pass, 1
        elif cat == "failed_run_ok_truth":
            # A failed run gives no evidence, even when its ok step is right.
            rec = lesson(iid(), wrong, "failure", honest([(wrong, ERR), (truth, OK)]), key=key)
            bare, st, lp, d = False, DONE, dflt_pass, 1
        elif cat == "run_label_mismatch":
            rec = lesson(iid(), wrong, SO, [(wrong, OK)], key=key,
                         run=rng.choice(["failure", ABSENT] + list(NEAR_MISS)))
            bare, st, lp, d = False, DONE, dflt_pass, 1
        elif cat == "failed_run_misleads":
            w2 = _other(rng, truth)
            rec = lesson(iid(), rng.choice([wrong, w2]), "failure", [(truth, ERR), (w2, OK)], key=key)
            bare, st, lp, d = False, DONE, dflt_pass, 1
        elif cat == "failed_sorts_first":
            lo, hi = sorted((iid(), iid()))
            rec = merge(lesson(lo, wrong, "failure", [(truth, ERR), (wrong, OK)], key=key),
                        lesson(hi, truth, SO, honest([(truth, OK)]), key=key))
            bare, st, lp, d = False, DONE, True, 2
        elif cat == "verb_conflict_no_detail":
            w3 = _other_verb(rng, truth)
            lo, hi = sorted((iid(), iid()))
            rec = merge(lesson(lo, w3, SO, honest([(w3, ERR), (truth, OK)]), key=key),
                        lesson(hi, truth, SO, [], key=key, arg=None))
            bare, st, lp, d = False, DONE, True, 1
        elif cat == "conflict":
            a, b = iid(), iid()
            rec = merge(lesson(a, wrong, SO, honest([(wrong, ERR), (truth, OK)]), key=key),
                        lesson(b, truth, SO, honest([(truth, OK)]), key=key))
            bare, st, lp, d = min(a, b) == b, DONE, True, 1
        elif cat == "contradicted_clean":
            w2 = _other(rng, truth, same_verb=True)
            a, b = iid(), iid()
            rec = merge(lesson(a, (truth[0], w2[1]), SO, honest([(truth, OK)]), key=key),
                        lesson(b, truth, SO, honest([((truth[0], w2[1]), ERR), (truth, OK)]),
                               key=key, arg=None))
            bare = (truth[0], default[1]) == truth if min(a, b) == b else False
            st, lp, d = DONE, True, 1
        elif cat == "two_failed":
            rec = merge(lesson(iid(), wrong, "failure", honest([(wrong, ERR)]), key=key),
                        lesson(iid(), wrong, ABSENT, honest([(wrong, ERR)]), key=key))
            bare, st, lp, d = False, DONE, dflt_pass, 2
        elif cat == "dangling_beside_good":
            good, bad = iid(), iid()
            action = rng.choice([truth, wrong])
            rec = merge(lesson(good, truth, SO, honest([(truth, OK)]), key=key),
                        lesson(bad, action, SO, honest([(truth, OK)]), key=key, link="missing"))
            bare = True if min(good, bad) == good else action == truth
            st = E.STATUS_ON_UNRESOLVED[oe]
            lp, d = (oe == E.SAFE_FALLBACK and dflt_pass), 0
        else:  # dangling
            # The first link fault of each world cycles with the seed, so
            # twelve consecutive seeds cover all seven faults.
            fault = LINK_FAULTS[(seed + faults_used) % len(LINK_FAULTS)]
            faults_used += 1
            action = rng.choice([truth, wrong])
            kw = {"no_summary_field": {"link": None}, "summary_missing": {"link": "missing"},
                  "no_trajectory_field": {"traj": None}, "trajectory_missing": {"traj": "missing"},
                  "unreadable": {"traj": "unreadable"}, "other_key": {"traj_key": "x" + key},
                  "key_case": {"traj_key": key.upper()}}[fault]
            rec = lesson(iid(), action, rng.choice([SO, "failure", ABSENT]),
                         honest([(truth, OK)]), key=key, **kw)
            bare = action == truth
            st = E.STATUS_ON_UNRESOLVED[oe]
            lp, d = (oe == E.SAFE_FALLBACK and dflt_pass), 0
            cat = "dangling/" + fault
        parts.append(rec)
        tasks.append(E.Task(tid, key, truth, default))
        expected[tid] = (cat, dflt_pass, bare, st, lp, d)
    return merge(*parts), tuple(tasks), oe, expected


REGRESSION = [("regression_%d" % s, s) for s in REGRESSION_SEEDS]


def check_design(out=print):
    fails = 0
    for name, records, t, oe, (e_pass, b_pass, lin) in DESIGN:
        m = E.load_memory(records)
        got = (E.run(E.EMPTY, m, t).passed, E.run(E.BARE, m, t).passed)
        r = E.run(E.LINKED, m, t, E.Config(oe))
        g = got + ((r.status, r.passed, r.descends, dict(r.verdicts)),)
        ok = g == (e_pass, b_pass, lin)
        fails += not ok
        out("%s %s" % ("PASS" if ok else "FAIL", name) + ("" if ok else " got %r" % (g,)))
    return fails, len(DESIGN)


def check_regression(out=print):
    fails, totals = 0, {a: 0 for a in ALL}
    n_tasks = 0
    for name, seed in REGRESSION:
        records, tasks, oe, exp = generate(seed)
        res = E.compare(E.load_memory(records), tasks, E.Config(oe))
        bad = []
        for i, t in enumerate(tasks):
            cat, ep, bp, st, lp, d = exp[t.task_id]
            e, b, l = res[E.EMPTY][i], res[E.BARE][i], res[E.LINKED][i]
            if (e.passed, b.passed, l.status, l.passed, l.descends) != (ep, bp, st, lp, d):
                bad.append((t.task_id, cat))
        for a in ALL:
            totals[a] += sum(r.passed for r in res[a])
        n_tasks += len(tasks)
        fails += bool(bad)
        out("%s %s (%s, %d tasks)" % ("PASS" if not bad else "FAIL", name, oe, len(tasks))
            + ("" if not bad else " %r" % bad))
    out("regression passes over %d tasks: %s" % (n_tasks, ", ".join("%s %d" % (a, totals[a]) for a in ALL)))
    return fails, len(REGRESSION)


if __name__ == "__main__":
    fd, nd = check_design()
    fr, nr = check_regression()
    print("report: design %d/%d, regression %d/%d as expected" % (nd - fd, nd, nr - fr, nr))
    sys.exit(1 if fd or fr else 0)
