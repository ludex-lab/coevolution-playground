"""Synthetic fixtures for w21-plan-changing-ask. Run: python3 fixtures.py

TASKS: three hand-written planning tasks. Each has a partial request and
operator-held facts. Every fact carries a declared label (plan_changing
or inert); each inert fact is worded like a plan_changing one about the
same subject. The labels are fixture declarations, not solver output.

STRATEGIES: scripted agents (no model) that produce a trace for a task.
The operator answers an ask one step later, except where a strategy
says the operator stays silent or answers after the deadline.

EXPECTED: the outcome of every (task, strategy) pair, written by hand
from the task plan, not computed by plan_ask.
"""

import copy
import sys

import plan_ask as P

TASKS = [
    {
        "task_id": "drivers",
        "request": "Schedule two drivers for the Saturday routes.",
        "facts": {
            "d_licence": {"text": "Driver B's licence lapses on Friday.",
                          "label": "plan_changing"},
            "d_paint": {"text": "Driver B's van was repainted on Friday.",
                        "label": "inert"},
        },
        "deadline": 10,
        "on_expiry": "HOLD",
    },
    {
        "task_id": "nurses",
        "request": "Assign nurses to the night shift.",
        "facts": {
            "n_cert": {"text": "Nurse C is not certified for ICU this week.",
                       "label": "plan_changing"},
            "n_leave": {"text": "Nurse D is on leave on Tuesday night.",
                        "label": "plan_changing"},
            "n_parking": {"text": "Nurse C parks in lot 4 this week.",
                          "label": "inert"},
        },
        "deadline": 8,
        "on_expiry": "ESCALATE",
    },
    {
        "task_id": "room",
        "request": "Book a meeting room for the design review.",
        "facts": {
            "r_capacity": {"text": "Room 2 now seats only six people.",
                           "label": "plan_changing"},
            "r_colour": {"text": "Room 2 now has grey walls.",
                         "label": "inert"},
        },
        "deadline": 6,
        "on_expiry": "DENY",
    },
]


def tasks():
    """A fresh deep copy of TASKS, so a test cannot alter shared state."""
    return copy.deepcopy(TASKS)


def _ids(task, label):
    return sorted(f for f, v in task["facts"].items() if v.get("label") == label)


def _ask_answer(fact_ids, t):
    events = []
    for f in fact_ids:
        events.append({"t": t, "kind": "ask", "fact": f})
        events.append({"t": t + 1, "kind": "answer", "fact": f})
        t += 2
    return events, t


def script(task, strategy):
    """Return (trace, now) for a scripted strategy on task."""
    pc = _ids(task, "plan_changing")
    inert = _ids(task, "inert")
    deadline = task["deadline"]
    if strategy == "act_now":
        return [{"t": 0, "kind": "act"}], 0
    if strategy == "inert_then_act":
        events, t = _ask_answer(inert, 0)
        return events + [{"t": t, "kind": "act"}], t
    if strategy == "one_plan_changing_then_act":
        events, t = _ask_answer(pc[:1], 0)
        return events + [{"t": t, "kind": "act"}], t
    if strategy == "plan_changing_then_act":
        events, t = _ask_answer(pc, 0)
        return events + [{"t": t, "kind": "act"}], t
    if strategy == "ask_all_then_act":
        events, t = _ask_answer(pc + inert, 0)
        return events + [{"t": t, "kind": "act"}], t
    if strategy == "ask_unanswered_then_act":
        events = [{"t": i, "kind": "ask", "fact": f} for i, f in enumerate(pc)]
        return events + [{"t": len(pc), "kind": "act"}], len(pc)
    if strategy == "silent_operator":
        events = [{"t": i, "kind": "ask", "fact": f} for i, f in enumerate(pc)]
        return events, deadline
    if strategy == "late_answer":
        events = [{"t": 1, "kind": "ask", "fact": f} for f in pc]
        events += [{"t": deadline, "kind": "answer", "fact": f} for f in pc]
        return events + [{"t": deadline + 1, "kind": "act"}], deadline + 1
    if strategy == "waiting":
        return [{"t": 0, "kind": "ask", "fact": pc[0]}], 1
    raise ValueError("unknown strategy")


STRATEGIES = (
    "act_now", "inert_then_act", "one_plan_changing_then_act",
    "plan_changing_then_act", "ask_all_then_act", "ask_unanswered_then_act",
    "silent_operator", "late_answer", "waiting",
)

DL, NU, RO = ("d_licence",), ("n_cert", "n_leave"), ("r_capacity",)

# (task_id, strategy) -> (decision, reason, missing); hand-written.
EXPECTED = {
    ("drivers", "act_now"): ("REJECT", "missing_plan_changing", DL),
    ("drivers", "inert_then_act"): ("REJECT", "missing_plan_changing", DL),
    ("drivers", "one_plan_changing_then_act"): ("ACT", "valid", ()),
    ("drivers", "plan_changing_then_act"): ("ACT", "valid", ()),
    ("drivers", "ask_all_then_act"): ("ACT", "valid", ()),
    ("drivers", "ask_unanswered_then_act"): ("REJECT", "missing_plan_changing", DL),
    ("drivers", "silent_operator"): ("HOLD", "expired", DL),
    ("drivers", "late_answer"): ("HOLD", "expired", DL),
    ("drivers", "waiting"): ("WAIT", "awaiting", DL),
    ("nurses", "act_now"): ("REJECT", "missing_plan_changing", NU),
    ("nurses", "inert_then_act"): ("REJECT", "missing_plan_changing", NU),
    ("nurses", "one_plan_changing_then_act"): ("REJECT", "missing_plan_changing", ("n_leave",)),
    ("nurses", "plan_changing_then_act"): ("ACT", "valid", ()),
    ("nurses", "ask_all_then_act"): ("ACT", "valid", ()),
    ("nurses", "ask_unanswered_then_act"): ("REJECT", "missing_plan_changing", NU),
    ("nurses", "silent_operator"): ("ESCALATE", "expired", NU),
    ("nurses", "late_answer"): ("ESCALATE", "expired", NU),
    ("nurses", "waiting"): ("WAIT", "awaiting", NU),
    ("room", "act_now"): ("REJECT", "missing_plan_changing", RO),
    ("room", "inert_then_act"): ("REJECT", "missing_plan_changing", RO),
    ("room", "one_plan_changing_then_act"): ("ACT", "valid", ()),
    ("room", "plan_changing_then_act"): ("ACT", "valid", ()),
    ("room", "ask_all_then_act"): ("ACT", "valid", ()),
    ("room", "ask_unanswered_then_act"): ("REJECT", "missing_plan_changing", RO),
    ("room", "silent_operator"): ("DENY", "expired", RO),
    ("room", "late_answer"): ("DENY", "expired", RO),
    ("room", "waiting"): ("WAIT", "awaiting", RO),
}


def run_all():
    """Return [(task_id, strategy, record)] over every task and strategy."""
    out = []
    for task in tasks():
        for strategy in STRATEGIES:
            trace, now = script(task, strategy)
            out.append((task["task_id"], strategy, P.decide(task, trace, now)))
    return out


def main():
    acts = 0
    rows = run_all()
    for task_id, strategy, rec in rows:
        acts += rec["decision"] == P.ACT
        print("%-8s %-28s %-9s %-22s %s" % (task_id, strategy, rec["decision"],
                                             rec["reason"], ",".join(rec["missing"])))
    print("rows=%d act=%d (synthetic fixtures only)" % (len(rows), acts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
