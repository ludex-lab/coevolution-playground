"""Independent reference for termination_lag (no imports, no shared code).

It takes an already valid trajectory (plain dicts and lists) and recomputes
every result on a separate code path: each raw-run state is rebuilt from
scratch by replaying the step prefix, and the gate holds a list of
admitted edit indices and replays that list for every candidate. It
returns plain tuples so the comparison with the module is exact.
"""


def _ok(trajectory, state):
    for c in trajectory["checks"]:
        if state.get(c["file"], None) not in c["accept"]:
            return False
    return True


def _replay(trajectory, indices):
    state = {}
    for k, v in trajectory["initial"].items():
        state[k] = v
    for i in indices:
        s = trajectory["steps"][i]
        if s["kind"] == "edit":
            state[s["file"]] = s["content"]
    return state


def reference(trajectory):
    """Return (first_pass, lag, regressions, baseline, rule verdict,
    protected_from, refused, stop verdict, steps run)."""
    n = len(trajectory["steps"])
    passing = [_ok(trajectory, _replay(trajectory, range(k + 1))) for k in range(n)]
    hits = [k for k in range(n) if passing[k]]
    fp = hits[0] if hits else None
    lag = None if fp is None else n - fp - 1
    regs = tuple(k for k in range(1, n) if passing[k - 1] and not passing[k])
    base = "PASS" if passing[-1] else "FAIL"

    admitted = []
    locked = None
    refused = []
    for i in range(n):
        if trajectory["steps"][i]["kind"] != "edit":
            continue
        good = _ok(trajectory, _replay(trajectory, admitted + [i]))
        if locked is not None and not good:
            refused.append(i)
            continue
        admitted.append(i)
        if good and locked is None:
            locked = i
    rule = "PASS" if _ok(trajectory, _replay(trajectory, admitted)) else "FAIL"

    if fp is None:
        stop, ran = base, n
    else:
        stop, ran = "PASS", fp + 1
    return (fp, lag, regs, base, rule, locked, tuple(refused), stop, ran)
