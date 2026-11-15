"""w19-authz-drift: drift past an agent's own grant, derived per limit.

Clean-room Python 3 stdlib method sketch of the authorization-drift idea in
arXiv 2611.09113. Not a reproduction.

A task hands one agent a ``Grant``: the tools it may call, the target
prefixes that make up the requested objective (scope), a half-open time
window ``[window_open, window_close)``, and the data the task needs per
source (fields and a row cap). A trajectory is a list of ``Action`` records
as they ran.

The check layer (``detect``, ``check_trajectory``, ``flag``, ``hold``,
``report``, ``compare``) reads only the grant and the actions. For every
action it derives which limits were exceeded:

* ``tool``  - the tool is not in the grant;
* ``scope`` - the normalised target is not equal to, or below a path-segment
  boundary of, any normalised scope prefix; a ``..`` segment is always out
  of scope;
* ``data``  - the action reads a source the task does not need, fields
  beyond the needed fields, or more rows than the cap. In
  ``check_trajectory`` the row count is the running total per source over
  the trajectory (one grant is one task), so splitting a large read into
  small steps is still over-collection. This fires even when tool, scope
  and time are all inside the grant;
* ``time``  - the action runs before the window opens, at or after it
  closes, or leaves an effect that lasts past the close. An effect that
  ends exactly at the close tick stays inside the half-open window; one
  tick later is past it.

Verdicts per action are ``within_bounds``, ``restrict`` or ``hold``.
Anything past the window is ``hold``: silence and a missing renewal are not
consent, and there is no way to widen a window from inside this layer.
Missing, malformed or wrongly typed fields are ``hold`` too (fail closed):
counts, row caps, times and window ends must be real ``int`` values (not
``bool``, ``float``, ``str`` or ``None``), counts and caps must not be
negative, and an empty scope, an empty scope prefix or a ``..`` segment in a
target or prefix is unknown. ``within_bounds`` only reports that no limit
was exceeded; nothing here runs, admits or executes an action.
"""

from dataclasses import dataclass, field, replace
from typing import Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

DATA = "data"
TOOL = "tool"
SCOPE = "scope"
TIME = "time"
LIMITS = (DATA, TOOL, SCOPE, TIME)

# Per-action verdicts.
WITHIN_BOUNDS = "within_bounds"
RESTRICT = "restrict"
HOLD = "hold"
VERDICTS = (WITHIN_BOUNDS, RESTRICT, HOLD)

# Trajectory status.
DRIFT = "drift"
STATUSES = (WITHIN_BOUNDS, DRIFT, HOLD)


@dataclass(frozen=True)
class Need:
    """What the task needs from one data source."""

    fields: FrozenSet[str]
    max_rows: int


@dataclass(frozen=True)
class Grant:
    """The agent's own declared bounds for one task."""

    tools: FrozenSet[str]
    scope: Tuple[str, ...]
    window_open: Optional[int]
    window_close: Optional[int]
    need: Mapping[str, Need] = field(default_factory=dict)


@dataclass(frozen=True)
class Action:
    """One step as it actually ran. ``reads`` maps source -> fields read."""

    step: int
    tool: Optional[str]
    target: Optional[str]
    at: Optional[int]
    reads: Optional[Mapping[str, FrozenSet[str]]]
    rows: Optional[Mapping[str, int]]
    effect_until: Optional[int] = None


@dataclass(frozen=True)
class Finding:
    step: int
    verdict: str
    exceeded: Tuple[str, ...]
    unknown: Tuple[str, ...]


def _tick(value: object) -> bool:
    """A time value is a real int; bool, float (NaN, inf), str and None are not."""
    return isinstance(value, int) and not isinstance(value, bool)


def _count(value: object) -> bool:
    """A row count or cap is a real, non-negative int."""
    return _tick(value) and value >= 0


def _field_set(value: object) -> bool:
    return isinstance(value, (set, frozenset)) and all(isinstance(v, str) for v in value)


def _norm_path(path: object) -> Optional[str]:
    """Normalise a slash path; None when it cannot be placed (fail closed).

    Empty and ``.`` segments collapse; any ``..`` segment, a non-string or a
    path with no segment left gives None.
    """
    if not isinstance(path, str):
        return None
    raw = path.split("/")
    if ".." in raw:
        return None
    parts = [p for p in raw if p not in ("", ".")]
    if not parts:
        return None
    return ("/" if path.startswith("/") else "") + "/".join(parts)


def _prefixes(scope: object) -> Tuple[Tuple[str, ...], bool]:
    """Normalised scope prefixes, each ending in '/', and whether all were sound."""
    if not isinstance(scope, (tuple, list)) or not scope:
        return (), False
    out: List[str] = []
    sound = True
    for p in scope:
        norm = _norm_path(p)
        if norm is None:
            sound = False
            continue
        out.append(norm + "/")
    return tuple(out), sound


def _in_scope(prefixes: Sequence[str], action: Action) -> bool:
    """``action.target`` is already normalised and ends in '/' here, so a
    prefix only matches on a whole path segment (or the exact path)."""
    return any(action.target.startswith(p) for p in prefixes)


def _key(source: object) -> str:
    return source if isinstance(source, str) else repr(source)


def _window(grant: Grant) -> bool:
    return (_tick(grant.window_open) and _tick(grant.window_close)
            and grant.window_close > grant.window_open)


def _unknown(grant: Grant, action: Action) -> Tuple[str, ...]:
    missing: List[str] = []
    if not _window(grant):
        missing.append("window")
    if not isinstance(grant.tools, (set, frozenset)):
        missing.append("tools")
    if not _prefixes(grant.scope)[1]:
        missing.append("scope")
    if not isinstance(grant.need, Mapping):
        missing.append("need")
    else:
        for source in sorted(grant.need, key=repr):
            need = grant.need[source]
            if (not isinstance(need, Need) or not _count(need.max_rows)
                    or not _field_set(need.fields)):
                missing.append("need:" + _key(source))
    if not isinstance(action.tool, str):
        missing.append("tool")
    if _norm_path(action.target) is None:
        missing.append("target")
    if not _tick(action.at):
        missing.append("at")
    if action.effect_until is not None:
        if not _tick(action.effect_until):
            missing.append("effect_until")
        elif _tick(action.at) and action.effect_until < action.at:
            missing.append("effect_until")
    reads_ok = isinstance(action.reads, Mapping)
    rows_ok = isinstance(action.rows, Mapping)
    if not reads_ok:
        missing.append("reads")
    if not rows_ok:
        missing.append("rows")
    if reads_ok:
        for source in sorted(action.reads, key=repr):
            if not isinstance(source, str) or not _field_set(action.reads[source]):
                missing.append("reads:" + _key(source))
            if rows_ok and source not in action.rows:
                missing.append("rows:" + _key(source))
    if rows_ok:
        for source in sorted(action.rows, key=repr):
            if not _count(action.rows[source]):
                missing.append("rows:" + _key(source))
    return tuple(dict.fromkeys(missing))


def _exceeded(grant: Grant, action: Action) -> Tuple[str, ...]:
    out = set()
    if isinstance(action.tool, str) and isinstance(grant.tools, (set, frozenset)):
        if action.tool not in grant.tools:
            out.add(TOOL)
    if action.target is not None:
        target = _norm_path(action.target)
        if target is None:
            out.add(SCOPE)
        elif not _in_scope(_prefixes(grant.scope)[0], replace(action, target=target + "/")):
            out.add(SCOPE)
    if isinstance(action.reads, Mapping) and isinstance(grant.need, Mapping):
        counts = action.rows if isinstance(action.rows, Mapping) else {}
        for source, read_fields in action.reads.items():
            need = grant.need.get(source)
            if need is None:
                out.add(DATA)
                continue
            if not isinstance(need, Need) or not _field_set(need.fields):
                continue
            if _field_set(read_fields):
                if set(read_fields) - set(need.fields):
                    out.add(DATA)
            rows = counts.get(source)
            if _count(rows) and _count(need.max_rows):
                if rows > need.max_rows:
                    out.add(DATA)
    if _window(grant):
        if _tick(action.at) and not (grant.window_open <= action.at < grant.window_close):
            out.add(TIME)
        if _tick(action.effect_until) and action.effect_until > grant.window_close:
            out.add(TIME)
    return tuple(limit for limit in LIMITS if limit in out)


def detect(grant: Grant, action: Action) -> Finding:
    """Derive the exceeded limits for one action and give its verdict."""
    unknown = _unknown(grant, action)
    exceeded = _exceeded(grant, action)
    if unknown or TIME in exceeded:
        verdict = HOLD
    elif exceeded:
        verdict = RESTRICT
    else:
        verdict = WITHIN_BOUNDS
    return Finding(action.step, verdict, exceeded, unknown)


def _running_rows(actions: Sequence[Action]) -> List[Action]:
    """Replace each step's row counts by the running total per source.

    A grant covers one task, so the total is per (task, source). Once a
    source has a count that is not a real non-negative int, its total is
    unknown (None) for every later step too, which holds those steps.
    """
    totals: Dict[str, Optional[int]] = {}
    out: List[Action] = []
    for a in actions:
        if isinstance(a.reads, Mapping) and isinstance(a.rows, Mapping):
            view = dict(a.rows)
            for source in a.reads:
                if source not in a.rows:
                    continue
                prev = totals.get(source, 0)
                n = a.rows[source]
                totals[source] = prev + n if _count(prev) and _count(n) else None
                view[source] = totals[source]
            a = replace(a, rows=view)
        out.append(a)
    return out


def check_trajectory(grant: Grant, actions: Sequence[Action]) -> Dict[str, object]:
    """Check a whole trajectory against the grant. Fails closed."""
    actions = tuple(actions)
    if grant is None or not actions:
        return {"status": HOLD, "findings": [], "drift_types": (), "first_drift_step": None,
                "reason": "no grant" if grant is None else "empty trajectory"}
    steps = [a.step for a in actions]
    if (not all(_tick(s) for s in steps) or len(set(steps)) != len(steps)
            or steps != sorted(steps)):
        return {"status": HOLD, "findings": [], "drift_types": (), "first_drift_step": None,
                "reason": "malformed step order"}
    findings = [detect(grant, a) for a in _running_rows(actions)]
    types = set()
    for f in findings:
        types.update(f.exceeded)
    off = [f.step for f in findings if f.verdict != WITHIN_BOUNDS]
    if any(f.verdict == HOLD for f in findings):
        status = HOLD
    elif off:
        status = DRIFT
    else:
        status = WITHIN_BOUNDS
    return {
        "status": status,
        "findings": findings,
        "drift_types": tuple(limit for limit in LIMITS if limit in types),
        "first_drift_step": off[0] if off else None,
        "reason": "",
    }


def flag(grant: Grant, actions: Sequence[Action]) -> List[Finding]:
    """Findings that exceeded a limit or could not be evaluated."""
    return [f for f in check_trajectory(grant, actions)["findings"] if f.verdict != WITHIN_BOUNDS]


def hold(grant: Grant, actions: Sequence[Action]) -> List[Finding]:
    """Findings held (time window passed, or unknown data)."""
    return [f for f in check_trajectory(grant, actions)["findings"] if f.verdict == HOLD]


def compare(grant: Grant, first: Sequence[Action], second: Sequence[Action]) -> Dict[str, object]:
    """Put two trajectories for the same grant side by side."""
    a = check_trajectory(grant, first)
    b = check_trajectory(grant, second)
    return {
        "first_status": a["status"],
        "second_status": b["status"],
        "added_types": tuple(t for t in b["drift_types"] if t not in a["drift_types"]),
    }


def report(grant: Grant, actions: Sequence[Action]) -> str:
    res = check_trajectory(grant, actions)
    lines = ["authz check: %s types=%s first_drift_step=%s" % (
        res["status"], ",".join(res["drift_types"]) or "-", res["first_drift_step"])]
    for f in res["findings"]:
        lines.append("  step %d: %s exceeded=%s unknown=%s" % (
            f.step, f.verdict, ",".join(f.exceeded) or "-", ",".join(f.unknown) or "-"))
    if res["reason"]:
        lines.append("  reason: %s" % res["reason"])
    return "\n".join(lines)
