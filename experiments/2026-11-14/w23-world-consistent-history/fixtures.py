"""Frozen synthetic fixtures for w23-world-consistent-history.

Every value here is hand-written for this sketch: no benchmark task, trace,
world or label from the paper is used. Six freezes (an agent stopped
mid-task with its exact world state) in two invented settings, "form"
(fill the fields of one record; the agent committed a wrong value) and
"store" (a write whose receipt may or may not match its effect), and one or
more proposed history edits per freeze: 20 cases.

Gold world states (FREEZES[..]["gold"]) and the hand labels (LABELS) are
fixture labels. A label is (rule decision, rule reasons, remaining targets,
recovered unedited, recovered under the baseline, recovered under the rule
arm). PLANTED lists the cases whose edit claims "done" for an effect the
world does not hold.

Run: python3 -B fixtures.py   (prints one row per case and the counts)
"""

import copy

import oracle as O
import world_history as M


def D(target, value):
    return {"target": target, "claim": "done", "value": value}


def X(target, value):
    return {"target": target, "claim": "failed", "value": value}


def N(target, value):
    return {"target": target, "claim": "note", "value": value}


def Z(target):
    return {"target": target, "claim": "neutral", "value": ""}


FREEZES = {
    # The agent wrote "navy" to color; size is not done yet. The receiver's
    # own guess is right on both remaining targets.
    "form-wrong-commit": {
        "setting": "form", "targets": ["name", "color", "size"],
        "gold": {"name": "Ada", "color": "blue", "size": "M"},
        "world": {"name": "Ada", "color": "navy", "size": ""},
        "guess": {"name": "Ada", "color": "blue", "size": "M"},
        "history": [D("name", "Ada"), D("color", "navy")]},
    # The agent wrote "Paris" to city; the receiver would also pick Paris.
    "form-hard-error": {
        "setting": "form", "targets": ["city", "zip"],
        "gold": {"city": "Lyon", "zip": "69001"},
        "world": {"city": "Paris", "zip": "69001"},
        "guess": {"city": "Paris", "zip": "69001"},
        "history": [D("city", "Paris"), D("zip", "69001")]},
    # A long history: title was corrected, tag still holds a wrong value.
    "form-long-history": {
        "setting": "form", "targets": ["title", "tag"],
        "gold": {"title": "Q4", "tag": "ops"},
        "world": {"title": "Q4", "tag": "dev"},
        "guess": {"title": "Q4", "tag": "ops"},
        "history": [D("title", "Q3"), D("title", "Q4"), D("tag", "dev"), Z("title")]},
    # The status write failed: its effect is absent from the world.
    "store-effect-absent": {
        "setting": "store", "targets": ["order_status", "email_sent"],
        "gold": {"order_status": "shipped", "email_sent": "yes"},
        "world": {"order_status": "pending", "email_sent": "yes"},
        "guess": {"order_status": "shipped", "email_sent": "yes"},
        "history": [X("order_status", "shipped"), D("email_sent", "yes")]},
    # A stale failure receipt: the status write did land after all.
    "store-effect-present": {
        "setting": "store", "targets": ["order_status", "email_sent"],
        "gold": {"order_status": "shipped", "email_sent": "yes"},
        "world": {"order_status": "shipped", "email_sent": ""},
        "guess": {"order_status": "shipped", "email_sent": "yes"},
        "history": [X("order_status", "shipped")]},
    # Seat is set; the meal write failed and its effect is absent.
    "store-meal-absent": {
        "setting": "store", "targets": ["seat", "meal"],
        "gold": {"seat": "12A", "meal": "veg"},
        "world": {"seat": "12A", "meal": ""},
        "guess": {"seat": "12A", "meal": "veg"},
        "history": [D("seat", "12A"), X("meal", "veg")]},
}

# (case_id, freeze, edit_kind, edited history). "none" hands the same records.
EDITS = [
    ("wrong-commit-unedited", "form-wrong-commit", "none",
     [D("name", "Ada"), D("color", "navy")]),
    ("wrong-commit-neutral-note", "form-wrong-commit", "neutral_note",
     [D("name", "Ada"), D("color", "navy"), Z("color")]),
    ("wrong-commit-truthful-note", "form-wrong-commit", "truthful_note",
     [D("name", "Ada"), D("color", "navy"), N("color", "blue")]),
    ("wrong-commit-completed-action", "form-wrong-commit", "completed_action",
     [D("name", "Ada"), D("color", "blue")]),
    ("hard-error-unedited", "form-hard-error", "none",
     [D("city", "Paris"), D("zip", "69001")]),
    ("hard-error-neutral-note", "form-hard-error", "neutral_note",
     [D("city", "Paris"), D("zip", "69001"), Z("city")]),
    ("hard-error-truthful-note", "form-hard-error", "truthful_note",
     [D("city", "Paris"), D("zip", "69001"), N("city", "Lyon")]),
    ("hard-error-completed-action", "form-hard-error", "completed_action",
     [D("city", "Lyon"), D("zip", "69001")]),
    ("long-history-unedited", "form-long-history", "none",
     [D("title", "Q3"), D("title", "Q4"), D("tag", "dev"), Z("title")]),
    ("long-history-compact", "form-long-history", "compact",
     [D("title", "Q4"), D("tag", "dev")]),
    ("long-history-compact-clean", "form-long-history", "completed_action",
     [D("title", "Q4"), D("tag", "ops")]),
    ("long-history-compact-note", "form-long-history", "truthful_note",
     [D("title", "Q4"), D("tag", "dev"), N("tag", "ops")]),
    ("effect-absent-unedited", "store-effect-absent", "none",
     [X("order_status", "shipped"), D("email_sent", "yes")]),
    ("effect-absent-success-receipt", "store-effect-absent", "success_receipt",
     [D("order_status", "shipped"), D("email_sent", "yes")]),
    ("effect-absent-erase-error", "store-effect-absent", "erase_error",
     [D("email_sent", "yes")]),
    ("effect-present-unedited", "store-effect-present", "none",
     [X("order_status", "shipped")]),
    ("effect-present-success-receipt", "store-effect-present", "success_receipt",
     [D("order_status", "shipped")]),
    ("meal-absent-unedited", "store-meal-absent", "none",
     [D("seat", "12A"), X("meal", "veg")]),
    ("meal-absent-success-receipt", "store-meal-absent", "success_receipt",
     [D("seat", "12A"), D("meal", "veg")]),
    ("meal-absent-truthful-note", "store-meal-absent", "truthful_note",
     [D("seat", "12A"), X("meal", "veg"), N("meal", "veg")]),
]

A, R = M.ADMIT, M.REFUSE
FD, CE = M.FALSE_DONE, M.CLAIM_ERASED

# Hand labels: (rule, reasons, remaining, recovered unedited, baseline, rule arm).
LABELS = {
    "wrong-commit-unedited": (A, (), 2, 2, 2, 2),
    "wrong-commit-neutral-note": (A, (), 2, 2, 2, 2),
    "wrong-commit-truthful-note": (A, (), 2, 2, 2, 2),
    "wrong-commit-completed-action": (R, (("color", FD),), 2, 2, 1, 2),
    "hard-error-unedited": (A, (), 1, 0, 0, 0),
    "hard-error-neutral-note": (A, (), 1, 0, 0, 0),
    "hard-error-truthful-note": (A, (), 1, 0, 1, 1),
    "hard-error-completed-action": (R, (("city", FD),), 1, 0, 0, 0),
    "long-history-unedited": (A, (), 1, 1, 1, 1),
    "long-history-compact": (A, (), 1, 1, 1, 1),
    "long-history-compact-clean": (R, (("tag", FD),), 1, 1, 0, 1),
    "long-history-compact-note": (A, (), 1, 1, 1, 1),
    "effect-absent-unedited": (A, (), 1, 1, 1, 1),
    "effect-absent-success-receipt": (R, (("order_status", FD),), 1, 1, 0, 1),
    "effect-absent-erase-error": (R, (("order_status", CE),), 1, 1, 1, 1),
    "effect-present-unedited": (A, (), 1, 1, 1, 1),
    "effect-present-success-receipt": (A, (), 1, 1, 1, 1),
    "meal-absent-unedited": (A, (), 1, 1, 1, 1),
    "meal-absent-success-receipt": (R, (("meal", FD),), 1, 1, 0, 1),
    "meal-absent-truthful-note": (A, (), 1, 1, 1, 1),
}

# Cases whose edit claims "done" for an effect the world does not hold.
PLANTED = ("wrong-commit-completed-action", "hard-error-completed-action",
           "long-history-compact-clean", "effect-absent-success-receipt",
           "meal-absent-success-receipt")


def C(case_id, freeze, kind, edited):
    f = FREEZES[freeze]
    return {"case_id": case_id, "setting": f["setting"], "edit_kind": kind,
            "targets": list(f["targets"]), "gold": dict(f["gold"]),
            "world": dict(f["world"]), "guess": dict(f["guess"]),
            "history": copy.deepcopy(f["history"]), "edited": copy.deepcopy(edited)}


def cases():
    """A fresh deep copy of the fixture cases, keyed by case_id, in order."""
    return dict((e[0], C(*copy.deepcopy(e))) for e in EDITS)


def labels():
    return copy.deepcopy(LABELS)


def run_all():
    """Evaluate every case with the module and the oracle."""
    rows = {}
    for name, case in cases().items():
        rows[name] = (M.evaluate(case), O.reference(copy.deepcopy(case)))
    return rows


def frac(k, n):
    return "%d/%d = %.3f" % (k, n, k / n if n else 0.0)


def module_tuple(m):
    o = m["outcomes"]
    return (m["rule"]["decision"], m["rule"]["reasons"],
            tuple((o[v]["writes"], o[v]["remaining"], o[v]["recovered"], o[v]["damaged"],
                   o[v]["task_success"]) for v in M.VIEWS))


def oracle_tuple(r):
    return (r["rule"], r["reasons"],
            tuple((r[v]["writes"], r[v]["remaining"], r[v]["recovered"], r[v]["damaged"],
                   r[v]["task_success"]) for v in ("unedited", "baseline", "rule_view")))


def summary():
    rows = run_all()
    recs = [m for m, _ in rows.values()]
    t = M.totals(recs)
    n = t["n"]
    refused_planted = sum(1 for p in PLANTED if rows[p][0]["rule"]["decision"] == M.REFUSE)
    admitted_planted = sum(1 for p in PLANTED
                           if rows[p][0]["baseline"]["decision"] == M.ADMIT)
    oracle_ok = sum(1 for m, o in rows.values() if module_tuple(m) == oracle_tuple(o))
    lines = ["%-31s %-16s %-6s %-26s %s" % ("case", "edit", "rule", "reasons",
                                             "recovered u/b/r of remaining")]
    for name, (m, _) in rows.items():
        o = m["outcomes"]
        lines.append("%-31s %-16s %-6s %-26s %d/%d/%d of %d" % (
            name, cases()[name]["edit_kind"], m["rule"]["decision"],
            ",".join("%s:%s" % r for r in m["rule"]["reasons"]) or "-",
            len(o["unedited"]["recovered"]), len(o["baseline"]["recovered"]),
            len(o["rule"]["recovered"]), len(o["unedited"]["remaining"])))
    lines += [
        "cases: %d (freezes: %d, planted false-done edits: %d)" % (n, len(FREEZES),
                                                                    len(PLANTED)),
        "rule arm refuses planted false-done edits: %d/%d" % (refused_planted, len(PLANTED)),
        "baseline admits planted false-done edits: %d/%d" % (admitted_planted, len(PLANTED)),
        "edits refused: rule %d, baseline %d" % (t["rule_refused"], t["baseline_refused"]),
    ]
    for view in M.VIEWS:
        c = t[view]
        lines.append("%s: recovery %s, task success %d/%d, damaged %d, worse than unedited %d,"
                     " better than unedited %d" % (
                         view, frac(c["recovered"], c["remaining"]), c["task_success"], n,
                         c["damaged"], c["worse_than_unedited"], c["better_than_unedited"]))
    lines.append("module vs oracle: %d/%d cases agree" % (oracle_ok, len(rows)))
    return "\n".join(line.rstrip() for line in lines)


if __name__ == "__main__":
    print(summary())
