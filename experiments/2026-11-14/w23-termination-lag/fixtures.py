"""Frozen synthetic trajectories with a hand-written gold set.

Every repository state, edit, check and label below is invented test data
for this sketch. Two toy tasks:

- dates: one checked file, two accepted contents (a primary fix and an
  alternative correct fix);
- cache: two checked files; the test passes only when both are fixed.

LABELS[name] = (first_correct, lag, regressions, baseline, refused, rule):
the gold first-correct step, the gold termination lag, the gold raw-run
regression steps (a passing state undone), the gold final-state verdict of
the raw run (what the honest baseline should say), the gold edits the step
gate must refuse, and the gold final verdict under the gate. Labels were
written by hand from the step lists, not printed by the module.

Run: python3 -B fixtures.py   (prints the table and the summary lines)
"""

import copy

import oracle
import termination_lag as M

D_FILE = "src/dates.py"
D_GOOD = "return parse(s, tz=True)"
D_ALT = "return parse_aware(s)"
D_BUG = "return parse(s)"
D_BAD = "return parse(s, tz=False)"
D_BAD2 = "return parse(s.strip())"

C_CACHE = "src/cache.py"
C_CONFIG = "src/config.py"
C_CACHE_BUG = "ttl = None"
C_CACHE_FIX = "ttl = config.ttl"
C_CONFIG_BUG = "ttl: missing"
C_CONFIG_FIX = "ttl: 30s"


def e(name, content):
    return {"kind": "edit", "file": name, "content": content}


V = {"kind": "verify"}
X = {"kind": "explore"}


def dates(tid, steps):
    return {"trajectory_id": tid,
            "initial": {D_FILE: D_BUG, "tests/test_dates.py": "case: utc offset"},
            "checks": [{"file": D_FILE, "accept": [D_GOOD, D_ALT]}],
            "steps": steps}


def cache(tid, steps):
    return {"trajectory_id": tid,
            "initial": {C_CACHE: C_CACHE_BUG, C_CONFIG: C_CONFIG_BUG},
            "checks": [{"file": C_CACHE, "accept": [C_CACHE_FIX]},
                       {"file": C_CONFIG, "accept": [C_CONFIG_FIX]}],
            "steps": steps}


_LIST = [
    dates("d-first-edit-stop", [e(D_FILE, D_GOOD)]),
    dates("d-first-edit-then-verify", [e(D_FILE, D_GOOD), V, X, V]),
    dates("d-late-solve", [X, e(D_FILE, D_BAD), V, e(D_FILE, D_GOOD), V]),
    dates("d-undo-at-end", [e(D_FILE, D_GOOD), V, X, e(D_FILE, D_BAD)]),
    dates("d-revert-to-bug", [X, e(D_FILE, D_GOOD), V, e(D_FILE, D_BUG), V]),
    dates("d-alt-correct", [e(D_FILE, D_GOOD), V, e(D_FILE, D_ALT), V]),
    dates("d-undo-then-refix", [e(D_FILE, D_GOOD), e(D_FILE, D_BAD), V, e(D_FILE, D_ALT)]),
    dates("d-undo-then-wrong-again", [e(D_FILE, D_GOOD), e(D_FILE, D_BAD), e(D_FILE, D_BAD2), V]),
    dates("d-never-solved", [X, e(D_FILE, D_BAD), V, e(D_FILE, D_BAD2)]),
    dates("d-long-wait-then-undo", [e(D_FILE, D_GOOD), V, X, X, X, X, X, X, e(D_FILE, D_BAD)]),
    cache("c-partial-then-full", [e(C_CACHE, C_CACHE_FIX), V, e(C_CONFIG, C_CONFIG_FIX), V]),
    cache("c-full-then-undo-one", [e(C_CACHE, C_CACHE_FIX), e(C_CONFIG, C_CONFIG_FIX), X,
                                   e(C_CACHE, C_CACHE_BUG)]),
    cache("c-unrelated-edit-after", [e(C_CACHE, C_CACHE_FIX), e(C_CONFIG, C_CONFIG_FIX),
                                     e("README.md", "notes: ttl comes from config")]),
    cache("c-churn-before-solve", [e(C_CACHE, C_CACHE_FIX), e(C_CACHE, C_CACHE_BUG),
                                   e(C_CACHE, C_CACHE_FIX), e(C_CONFIG, C_CONFIG_FIX)]),
    cache("c-never-solved", [e(C_CACHE, C_CACHE_FIX), V]),
]
EPISODES = dict((t["trajectory_id"], t) for t in _LIST)

P, F = M.PASS, M.FAIL
LABELS = {
    "d-first-edit-stop": (0, 0, (), P, (), P),
    "d-first-edit-then-verify": (0, 3, (), P, (), P),
    "d-late-solve": (3, 1, (), P, (), P),
    "d-undo-at-end": (0, 3, (3,), F, (3,), P),
    "d-revert-to-bug": (1, 3, (3,), F, (3,), P),
    "d-alt-correct": (0, 3, (), P, (), P),
    "d-undo-then-refix": (0, 3, (1,), P, (1,), P),
    "d-undo-then-wrong-again": (0, 3, (1,), F, (1, 2), P),
    "d-never-solved": (None, None, (), F, (), F),
    "d-long-wait-then-undo": (0, 8, (8,), F, (8,), P),
    "c-partial-then-full": (2, 1, (), P, (), P),
    "c-full-then-undo-one": (1, 2, (3,), F, (3,), P),
    "c-unrelated-edit-after": (1, 1, (), P, (), P),
    "c-churn-before-solve": (3, 0, (), P, (), P),
    "c-never-solved": (None, None, (), F, (), F),
}

# The trajectory whose undo comes only after a long run of verify and
# explore steps: waiting does not turn a breaking edit into a permitted one.
LONG_WAIT = "d-long-wait-then-undo"


def episodes():
    """A fresh deep copy of every trajectory."""
    return copy.deepcopy(EPISODES)


def labels_of(record):
    r = record
    return (r["first_pass"], r["lag"], r["regressions"], r["baseline"]["verdict"],
            r["rule"]["refused"], r["rule"]["verdict"])


def run_all():
    """{name: (module record, oracle tuple)} over the fixture."""
    out = {}
    for name, t in episodes().items():
        out[name] = (M.evaluate(copy.deepcopy(t)), oracle.reference(copy.deepcopy(t)))
    return out


def summary():
    """Counts on the frozen fixture, computed from the module records and
    compared with the hand-written labels."""
    runs = run_all()
    names = sorted(runs)
    recs = dict((n, runs[n][0]) for n in names)
    solved = [n for n in names if LABELS[n][0] is not None]
    planted = [n for n in names if LABELS[n][2]]
    s = {
        "n": len(names),
        "solved": len(solved),
        "never": len(names) - len(solved),
        "planted": len(planted),
        "planted_steps": sum(len(LABELS[n][2]) for n in names),
        "rule_first_lag_match": sum(1 for n in names
                                    if (recs[n]["first_pass"], recs[n]["lag"]) == LABELS[n][:2]
                                    and recs[n]["rule"]["protected_from"] == LABELS[n][0]),
        "rule_flags_planted": sum(1 for n in planted
                                  if recs[n]["rule"]["regressions"] == LABELS[n][2]),
        "rule_refused": sum(len(recs[n]["rule"]["refused"]) for n in names),
        "rule_refused_match": sum(1 for n in names
                                  if recs[n]["rule"]["refused"] == LABELS[n][4]),
        "rule_false_flags": sum(1 for n in names if not LABELS[n][2]
                                and (recs[n]["rule"]["regressions"] or recs[n]["rule"]["refused"])),
        "rule_vs_solved": sum(1 for n in names
                              if (recs[n]["rule"]["verdict"] == M.PASS) == (n in solved)),
        "base_vs_solved": sum(1 for n in names
                              if (recs[n]["baseline"]["verdict"] == M.PASS) == (n in solved)),
        "base_missed_solved": sum(1 for n in solved if recs[n]["baseline"]["verdict"] == M.FAIL),
        "base_silent_regression": sum(1 for n in planted
                                      if recs[n]["baseline"]["verdict"] == M.PASS),
        "base_matches_label": sum(1 for n in names
                                  if recs[n]["baseline"]["verdict"] == LABELS[n][3]),
        "stop_correct": sum(1 for n in solved if recs[n]["stop_first"]["verdict"] == M.PASS),
        "total_steps": sum(recs[n]["steps"] for n in names),
        "lag_steps": sum(recs[n]["lag"] for n in solved),
        "stop_steps": sum(recs[n]["stop_first"]["steps_run"] for n in names),
        "oracle_agree": sum(1 for n in names if labels_of(runs[n][0]) + (
            runs[n][0]["rule"]["protected_from"], runs[n][0]["stop_first"]["verdict"],
            runs[n][0]["stop_first"]["steps_run"]) == _oracle_order(runs[n][1])),
        "label_agree": sum(1 for n in names if labels_of(recs[n]) == LABELS[n]),
    }
    return s


def _oracle_order(o):
    fp, lag, regs, base, rule, locked, refused, stop, ran = o
    return (fp, lag, regs, base, refused, rule, locked, stop, ran)


def summary_lines():
    """The result lines the README carries verbatim."""
    s = summary()
    return [
        "- trajectories: %d (%d reach a first passing patch, %d never do; %d carry a planted "
        "regression, %d regression steps in all)"
        % (s["n"], s["solved"], s["never"], s["planted"], s["planted_steps"]),
        "- first passing patch and termination lag: rule arm matches the gold labels on %d/%d; "
        "the baseline reports neither" % (s["rule_first_lag_match"], s["n"]),
        "- regressions: rule arm flags %d/%d planted regression trajectories at the gold steps "
        "and refuses %d edits (gold refusals matched on %d/%d trajectories, %d false flags); "
        "the baseline flags 0/%d"
        % (s["rule_flags_planted"], s["planted"], s["rule_refused"], s["rule_refused_match"],
           s["n"], s["rule_false_flags"], s["planted"]),
        "- final verdict against gold 'reached a correct patch': rule arm %d/%d, baseline %d/%d "
        "(it fails %d runs that were solved and then undone, and passes %d run whose "
        "regression a later edit re-fixed without seeing the regression)"
        % (s["rule_vs_solved"], s["n"], s["base_vs_solved"], s["n"], s["base_missed_solved"],
           s["base_silent_regression"]),
        "- stop at the first pass: %d/%d solved runs end correct; %d of %d total steps come "
        "after the first passing patch; stopping there runs %d steps"
        % (s["stop_correct"], s["solved"], s["lag_steps"], s["total_steps"], s["stop_steps"]),
        "- module vs oracle: %d/%d trajectories agree; module vs hand labels: %d/%d"
        % (s["oracle_agree"], s["n"], s["label_agree"], s["n"]),
    ]


def main():
    for name, (m, o) in sorted(run_all().items()):
        print("%-26s first=%-4s lag=%-4s regs=%-6s base=%s rule=%s refused=%-6s stop=%s/%s"
              % (name, m["first_pass"], m["lag"], m["regressions"], m["baseline"]["verdict"],
                 m["rule"]["verdict"], m["rule"]["refused"], m["stop_first"]["verdict"],
                 m["stop_first"]["steps_run"]))
    for line in summary_lines():
        print(line)


if __name__ == "__main__":
    main()
