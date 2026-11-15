"""Synthetic fixtures for w21-info-friction. Run: python3 -B fixtures.py

TASKS: two hand-written gathering tasks, one per declared novelty rule.
EPISODES: hand-written observation sequences (no model, no clock), each
with the evaluation time ``now``.
EXPECTED: the outcome of every (task, episode) pair, written by hand from
the episode plan, not computed by info_friction.
"""

import copy
import sys

import info_friction as I

TASKS = [
    {
        "task_id": "rescue",
        "requirements": ["location", "count", "route"],
        "friction_bound": 2,
        "deadline": 20,
        "on_expiry": "HOLD",
        "novelty_rule": "evidence_key",
    },
    {
        "task_id": "grid",
        "requirements": ["exit", "key"],
        "friction_bound": 1,
        "deadline": 12,
        "on_expiry": "DENY",
        "novelty_rule": "declared",
    },
]


def tasks():
    """A fresh deep copy of TASKS."""
    return copy.deepcopy(TASKS)


def o(t, evidence, resolves=None, novel=None):
    obs = {"t": t, "evidence": evidence}
    if resolves is not None:
        obs["resolves"] = resolves
    if novel is not None:
        obs["novel"] = novel
    return obs


EPISODES = {
    "rescue": {
        # resolves everything in three steps
        "direct": ([o(1, "radio-1", "location"), o(2, "radio-2", "count"),
                    o(3, "map-1", "route")], 3),
        # new evidence that resolves nothing, then resolution: exploration
        "explore_then_resolve": ([o(1, "radio-1", "location"), o(2, "drone-1"),
                                  o(3, "drone-2"), o(4, "drone-3"), o(5, "drone-4"),
                                  o(6, "radio-2", "count"), o(7, "map-1", "route")], 7),
        # one resolution, then the same radio message over and over
        "repeat_loop": ([o(1, "radio-1", "location"), o(2, "radio-1"),
                         o(3, "radio-1"), o(4, "radio-1"),
                         o(5, "radio-2", "count"), o(6, "map-1", "route")], 6),
        # two repeats (at the bound), then progress: no stop
        "repeat_at_bound": ([o(1, "radio-1", "location"), o(2, "radio-1"),
                             o(3, "radio-1"), o(4, "radio-2", "count"),
                             o(5, "map-1", "route")], 5),
        # alternating new and old evidence: friction resets each time
        "alternating": ([o(1, "radio-1", "location"), o(2, "radio-1"), o(3, "drone-1"),
                         o(4, "radio-1"), o(5, "drone-2"), o(6, "radio-1")], 6),
        # a repeat of evidence that resolves an already resolved requirement
        "re_resolve": ([o(1, "radio-1", "location"), o(2, "radio-1", "location"),
                        o(3, "radio-1", "location"), o(4, "radio-1", "location")], 4),
        # new evidence forever, never enough: the deadline returns on_expiry
        "explore_forever": ([o(i, "drone-%d" % i) for i in range(1, 20)], 20),
        # last requirement arrives at the deadline: too late
        "late_resolution": ([o(1, "radio-1", "location"), o(2, "radio-2", "count"),
                             o(20, "map-1", "route")], 20),
        # still gathering before the deadline
        "in_progress": ([o(1, "radio-1", "location")], 5),
        # post-completion chatter is not counted
        "post_completion": ([o(1, "radio-1", "location"), o(2, "radio-2", "count"),
                             o(3, "map-1", "route"), o(4, "map-1"), o(5, "map-1"),
                             o(6, "map-1"), o(7, "map-1")], 7),
    },
    "grid": {
        "direct": ([o(1, "cell-a", "exit", False), o(2, "cell-b", "key", False)], 2),
        # same evidence key, but the fixture declares it new (revisit with a
        # new purpose): exploration under the declared rule
        "declared_revisit": ([o(1, "cell-a", None, True), o(2, "cell-a", None, True),
                              o(3, "cell-a", None, True), o(4, "cell-b", "exit", False),
                              o(5, "cell-c", "key", False)], 5),
        # new evidence key, but declared not new: recurrent under the rule
        "declared_recurrent": ([o(1, "cell-a", "exit", False), o(2, "cell-x", None, False),
                                o(3, "cell-y", None, False), o(4, "cell-c", "key", False)], 4),
        "silent_until_deadline": ([o(1, "cell-a", "exit", False)], 12),
    },
}

R = ("count", "route")

# (task_id, episode) -> (decision, reason, unresolved, friction); hand-written.
EXPECTED = {
    ("rescue", "direct"): ("SUCCESS", "all_resolved", (), 0),
    ("rescue", "explore_then_resolve"): ("SUCCESS", "all_resolved", (), 0),
    ("rescue", "repeat_loop"): ("STOP", "friction_bound", R, 3),
    ("rescue", "repeat_at_bound"): ("SUCCESS", "all_resolved", (), 0),
    ("rescue", "alternating"): ("CONTINUE", "gathering", R, 1),
    ("rescue", "re_resolve"): ("STOP", "friction_bound", R, 3),
    ("rescue", "explore_forever"): ("HOLD", "expired", ("count", "location", "route"), 0),
    ("rescue", "late_resolution"): ("HOLD", "expired", ("route",), 0),
    ("rescue", "in_progress"): ("CONTINUE", "gathering", R, 0),
    ("rescue", "post_completion"): ("SUCCESS", "all_resolved", (), 0),
    ("grid", "direct"): ("SUCCESS", "all_resolved", (), 0),
    ("grid", "declared_revisit"): ("SUCCESS", "all_resolved", (), 0),
    ("grid", "declared_recurrent"): ("STOP", "friction_bound", ("key",), 2),
    ("grid", "silent_until_deadline"): ("DENY", "expired", ("key",), 0),
}


def run_all():
    """Return [(task_id, episode, record)] over every task and its episodes."""
    out = []
    for task in tasks():
        for name, (observations, now) in sorted(EPISODES[task["task_id"]].items()):
            out.append((task["task_id"], name,
                        I.evaluate(task, copy.deepcopy(observations), now)))
    return out


def main():
    rows = run_all()
    for task_id, name, rec in rows:
        print("%-7s %-22s %-9s %-15s unresolved=%-22s friction=%d" % (
            task_id, name, rec["decision"], rec["reason"],
            ",".join(rec["unresolved"]) or "-", rec["friction"]))
    print("rows=%d (synthetic fixtures only)" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
