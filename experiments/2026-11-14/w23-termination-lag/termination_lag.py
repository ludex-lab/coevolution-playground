"""Termination lag: once a first patch passes, later steps must not undo it.

Clean-room Python 3 standard-library method sketch of the termination-lag
idea in arXiv 2611.14960 ("Termination Lag: Coding Agents Solve Early but
Stop Late"). Not a reproduction and not the authors' code. The rules below
are this sketch's own declared rules.

A trajectory is one synthetic coding-agent run:

- trajectory_id: non-blank str;
- initial: {file: content}, the repository before the run (exact str
  values; it must FAIL the checks, so a first passing patch is a real
  event of the run);
- checks: the task's fixture test, a non-empty list of
  {"file", "accept"}: the patch passes when every checked file is present
  and its content is one of its accepted contents (a FIXTURE LABEL, not a
  general patch-correctness oracle);
- steps: a non-empty list of steps, each {"kind": "edit", "file",
  "content"} (overwrite one file) or {"kind": "verify"} /
  {"kind": "explore"} (no state change).

Derived from the raw run (every step applied in order):

- first_pass: the index of the first step after which the checks pass, or
  None when they never pass;
- lag (termination lag): the number of steps after first_pass up to the end
  of the run, or None;
- regressions: the step indices where the raw run goes from passing to
  failing (a correct patch undone).

Three arms per trajectory:

- baseline (honest, no model): judges the final state of the raw run only.
  It reports PASS or FAIL and nothing else: it cannot see that a run was
  correct mid-way, nor a regression that a later edit re-fixed.
- rule (the step gate): replays the run; before the first pass every step
  is permitted. From the first passing patch on, an edit whose result would
  fail the checks is refused (not applied; the passing state is retained).
  Edits that still pass (an alternative correct patch, an unrelated file)
  are permitted. Protection never expires: no number of verify or explore
  steps after the first pass turns a later breaking edit into a permitted
  one. It also reports the raw-run regressions (the score of a compare run
  that applies everything).
- stop_first: stop at the first passing patch. A stop there is a valid,
  fail-closed end; nothing requires further steps.

Malformed input is config_error. Every dict key, at every level, must be an
exact str, and that is checked before any lookup in the dict; every value
is checked by exact type, so subclasses of str, list and dict are rejected.
validate() reads each caller value once and returns a private snapshot
(exact str values in tuples and fresh dicts); every arm runs only on that
snapshot and never reads the caller's objects again. evaluate() never
raises. No timeout or expiry exists in this design. No clock, no network,
no files, no model.
"""

PASS = "PASS"
FAIL = "FAIL"
PERMIT = "permit"
REFUSE = "refuse"
OK = "ok"
CONFIG_ERROR = "config_error"
ON_UNMEASURED = "on_unmeasured"

EDIT = "edit"
VERIFY = "verify"
EXPLORE = "explore"
KINDS = (EDIT, VERIFY, EXPLORE)

TRAJECTORY_FIELDS = ("trajectory_id", "initial", "checks", "steps")
CHECK_FIELDS = ("file", "accept")
EDIT_FIELDS = ("kind", "file", "content")
BARE_FIELDS = ("kind",)


class _Bad(Exception):
    """Internal: a config_error with its detail."""


def paper_results():
    """The paper's figures are not measured here."""
    return ON_UNMEASURED


def _id(v):
    return type(v) is str and v.strip() != ""


def _keys(d, detail):
    """Raise _Bad(detail) unless every key of the exact dict d is an exact str.

    Runs before any lookup in d: iterating an exact dict runs no caller
    code, so no caller-defined __eq__ or __hash__ is reached afterwards.
    """
    for k in d:
        if type(k) is not str:
            raise _Bad(detail)


def _fields(d, names, detail):
    """d is an exact dict whose keys are exact str; its keys must be names."""
    if sorted(d) != sorted(names):
        raise _Bad(detail)


def passes(checks, state):
    """True when every checked file is present with an accepted content."""
    for name, accept in checks:
        if name not in state or state[name] not in accept:
            return False
    return True


def validate(trajectory):
    """Return a private snapshot of trajectory, or raise _Bad."""
    if type(trajectory) is not dict:
        raise _Bad("trajectory_not_dict")
    _keys(trajectory, "trajectory_key_invalid")
    _fields(trajectory, TRAJECTORY_FIELDS, "trajectory_fields_invalid")
    tid = trajectory["trajectory_id"]
    initial = trajectory["initial"]
    checks = trajectory["checks"]
    steps = trajectory["steps"]
    if not _id(tid):
        raise _Bad("trajectory_id_invalid")
    if type(initial) is not dict:
        raise _Bad("initial_invalid")
    _keys(initial, "initial_key_invalid")
    init = {}
    for name, content in list(initial.items()):
        if not _id(name) or type(content) is not str:
            raise _Bad("initial_value_invalid")
        init[name] = content
    if type(checks) is not list or not checks:
        raise _Bad("checks_invalid")
    chk = []
    seen = []
    for c in list(checks):
        if type(c) is not dict:
            raise _Bad("check_invalid")
        _keys(c, "check_key_invalid")
        _fields(c, CHECK_FIELDS, "check_fields_invalid")
        name = c["file"]
        accept = c["accept"]
        if not _id(name) or name in seen:
            raise _Bad("check_file_invalid")
        if type(accept) is not list or not accept:
            raise _Bad("check_accept_invalid")
        acc = []
        for a in list(accept):
            if type(a) is not str or a in acc:
                raise _Bad("check_accept_invalid")
            acc.append(a)
        seen.append(name)
        chk.append((name, tuple(acc)))
    if type(steps) is not list or not steps:
        raise _Bad("steps_invalid")
    st = []
    for s in list(steps):
        if type(s) is not dict:
            raise _Bad("step_invalid")
        _keys(s, "step_key_invalid")
        if "kind" not in s:
            raise _Bad("step_fields_invalid")
        kind = s["kind"]
        if type(kind) is not str or kind not in KINDS:
            raise _Bad("step_kind_unknown")
        if kind == EDIT:
            _fields(s, EDIT_FIELDS, "step_fields_invalid")
            name = s["file"]
            content = s["content"]
            if not _id(name) or type(content) is not str:
                raise _Bad("step_edit_invalid")
            st.append((EDIT, name, content))
        else:
            _fields(s, BARE_FIELDS, "step_fields_invalid")
            st.append((kind, None, None))
    snap = {"trajectory_id": tid, "initial": init, "checks": tuple(chk), "steps": tuple(st)}
    if passes(snap["checks"], snap["initial"]):
        raise _Bad("initial_passes")
    return snap


def raw_run(snap):
    """Apply every step; return (pass flag after each step, final state)."""
    state = dict(snap["initial"])
    flags = []
    for kind, name, content in snap["steps"]:
        if kind == EDIT:
            state[name] = content
        flags.append(passes(snap["checks"], state))
    return tuple(flags), state


def first_pass(flags):
    for i, ok in enumerate(flags):
        if ok:
            return i
    return None


def lag(flags):
    fp = first_pass(flags)
    if fp is None:
        return None
    return len(flags) - 1 - fp


def regressions(flags):
    """Steps where the raw run goes from passing to failing."""
    out = []
    prev = False
    for i, ok in enumerate(flags):
        if prev and not ok:
            out.append(i)
        prev = ok
    return tuple(out)


def baseline(snap):
    """Honest baseline: judge only the final state of the raw run."""
    flags, final = raw_run(snap)
    return {"verdict": PASS if passes(snap["checks"], final) else FAIL}


def gate(snap):
    """Step gate: from the first passing patch on, refuse any edit that would
    make the checks fail. Protection never expires."""
    checks = snap["checks"]
    state = dict(snap["initial"])
    solved = False
    protected_from = None
    decisions = []
    refused = []
    for i, (kind, name, content) in enumerate(snap["steps"]):
        if kind != EDIT:
            decisions.append(PERMIT)
            continue
        candidate = dict(state)
        candidate[name] = content
        ok = passes(checks, candidate)
        if solved and not ok:
            decisions.append(REFUSE)
            refused.append(i)
            continue
        state = candidate
        decisions.append(PERMIT)
        if ok and not solved:
            solved = True
            protected_from = i
    return {"verdict": PASS if passes(checks, state) else FAIL,
            "protected_from": protected_from, "refused": tuple(refused),
            "decisions": tuple(decisions)}


def stop_first(snap):
    """Stop at the first passing patch (a valid, fail-closed end)."""
    checks = snap["checks"]
    state = dict(snap["initial"])
    run = 0
    for kind, name, content in snap["steps"]:
        run += 1
        if kind == EDIT:
            state[name] = content
        if passes(checks, state):
            break
    return {"verdict": PASS if passes(checks, state) else FAIL, "steps_run": run}


def _config(detail):
    return {"status": CONFIG_ERROR, "detail": detail, "trajectory_id": None,
            "steps": None, "first_pass": None, "lag": None, "regressions": None,
            "baseline": None, "rule": None, "stop_first": None}


def _run(snap):
    flags, _ = raw_run(snap)
    rule = gate(snap)
    rule["regressions"] = regressions(flags)
    return {"status": OK, "detail": OK, "trajectory_id": snap["trajectory_id"],
            "steps": len(snap["steps"]), "first_pass": first_pass(flags),
            "lag": lag(flags), "regressions": regressions(flags),
            "baseline": baseline(snap), "rule": rule, "stop_first": stop_first(snap)}


def evaluate(trajectory):
    """Score one trajectory with all arms. Never raises."""
    try:
        snap = validate(trajectory)
    except _Bad as exc:
        return _config(str(exc))
    except Exception:
        return _config("internal_error")
    try:
        return _run(snap)
    except Exception:
        return _config("internal_error")
