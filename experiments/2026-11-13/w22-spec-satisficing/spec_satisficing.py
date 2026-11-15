"""Report-then-check before commit: specification satisficing (stdlib sketch).

Clean-room Python 3 standard-library method sketch of the report-and-check
idea in arXiv 2611.16289 ("Eliciting and Mitigating Specification
Satisficing in Coding Agents"). Not a reproduction and not the authors'
code. The rules below are this sketch's own declared rules.

A task is a list of requirement ids plus a catalog of implementation
choices. Each choice carries a FIXTURE LABEL "meets": the requirement ids
that the fixture author says the choice satisfies. The label is test data,
not a general specification oracle: nothing here can tell whether real code
meets a real requirement.

An agent trace is a list of events:

- report: {"kind": "report", "choice", "reason", "acceptable"}; the agent
  reports a choice and its reason; "acceptable" is the agent's own verdict
  (exact bool) and is recorded but never honored;
- check: {"kind": "check", "choice"}; runs check(choice, requirements) on
  the fixture label and records the result;
- self_correct: {"kind": "self_correct", "choice", "reason", "acceptable"};
  a self-correction step naming the choice it now selects (a retained or a
  new one); it counts as a report of that choice and re-opens every choice;
- commit: {"kind": "commit", "choice"}; exactly one, and the last event.

Declared rules (the commit gate, in order):

1. The committed choice must have been reported (report or self_correct)
   before the commit; else REFUSE / unreported.
2. It must have a check recorded after its latest report and after the
   latest self-correction of any choice; else REFUSE / unchecked. A new
   report of a choice voids its earlier check; a self-correction voids
   every earlier check.
3. That check must find no dropped requirement; else REFUSE /
   drops_requirement, whatever the reason or the "acceptable" verdict says.
4. Otherwise COMMIT / all_requirements_met.

Malformed input is REJECT / config_error. Every dict key, at every level
(task, choice catalog, choice entry, trace event), must be an exact str,
and that is checked before any lookup in the dict; every value is checked
by exact type, so subclasses of str, list and dict are rejected. A reason
must hold a non-whitespace character. validate() reads each caller value
once and returns a private snapshot built from the validated values (exact
str, exact bool or None, tuples and fresh dicts); the gate runs only on that
snapshot and never reads the caller's objects again. evaluate() never
raises. No timeout or expiry exists in this design. Pure functions: no
clock, no network, no files, no randomness, no imports.
"""

COMMIT = "COMMIT"
REFUSE = "REFUSE"
REJECT = "REJECT"

ALL_MET = "all_requirements_met"
UNREPORTED = "unreported"
UNCHECKED = "unchecked"
DROPS = "drops_requirement"
CONFIG_ERROR = "config_error"

ON_UNMEASURED = "on_unmeasured"

REPORT = "report"
CHECK = "check"
SELF_CORRECT = "self_correct"
COMMIT_EVENT = "commit"
KINDS = (REPORT, CHECK, SELF_CORRECT, COMMIT_EVENT)
EVENT_FIELDS = {
    REPORT: ("kind", "choice", "reason", "acceptable"),
    SELF_CORRECT: ("kind", "choice", "reason", "acceptable"),
    CHECK: ("kind", "choice"),
    COMMIT_EVENT: ("kind", "choice"),
}
TASK_FIELDS = ("task_id", "requirements", "choices")


class _Bad(Exception):
    """Internal: a config_error with its reason."""


def _is_str(v):
    return type(v) is str and v != ""


def paper_results():
    """The paper's benchmark figures are not measured here."""
    return ON_UNMEASURED


def check(choice, requirements):
    """Return (ok, dropped) for one choice against the requirement list.

    choice is a catalog entry {"meets": [...]}; "meets" is a fixture label.
    dropped lists, in requirement order, every requirement not in the
    label. ok is True only when nothing is dropped.
    """
    meets = choice["meets"]
    dropped = []
    for req in requirements:
        if req not in meets:
            dropped.append(req)
    return (len(dropped) == 0, tuple(dropped))


def _keys(d, detail):
    """Raise _Bad(detail) unless every key of the exact dict d is an exact str.

    Runs before any lookup in d: iterating an exact dict runs no caller code,
    so no caller-defined __eq__ or __hash__ is ever reached afterwards.
    """
    for k in d:
        if type(k) is not str:
            raise _Bad(detail)


def validate(task, trace):
    """Return a private snapshot of task and trace, or raise _Bad(reason).

    The snapshot is {"task_id", "requirements", "choices", "events"}: exact
    str, bool or None values in tuples and fresh dicts, sharing no container
    with the caller's objects.
    """
    if type(task) is not dict:
        raise _Bad("task_not_dict")
    _keys(task, "task_key_invalid")
    for name in TASK_FIELDS:
        if name not in task:
            raise _Bad(name + "_missing")
    if sorted(task) != sorted(TASK_FIELDS):
        raise _Bad("task_unknown_field")
    task_id = task["task_id"]
    if not _is_str(task_id):
        raise _Bad("task_id_invalid")
    reqs = task["requirements"]
    if type(reqs) is not list or not reqs:
        raise _Bad("requirements_invalid")
    reqs = tuple(reqs)
    for r in reqs:
        if not _is_str(r):
            raise _Bad("requirement_invalid")
    if len(set(reqs)) != len(reqs):
        raise _Bad("requirements_duplicate")
    choices = task["choices"]
    if type(choices) is not dict or not choices:
        raise _Bad("choices_invalid")
    for cid in choices:
        if not _is_str(cid):
            raise _Bad("choice_id_invalid")
    snap_choices = {}
    for cid, entry in choices.items():
        if type(entry) is not dict:
            raise _Bad("choice_entry_invalid")
        _keys(entry, "choice_entry_key_invalid")
        if sorted(entry) != ["meets"]:
            raise _Bad("choice_entry_invalid")
        meets = entry["meets"]
        if type(meets) is not list:
            raise _Bad("meets_invalid")
        meets = tuple(meets)
        for r in meets:
            if not _is_str(r) or r not in reqs:
                raise _Bad("meets_unknown_requirement")
        if len(set(meets)) != len(meets):
            raise _Bad("meets_duplicate")
        snap_choices[cid] = {"meets": meets}
    if type(trace) is not list or not trace:
        raise _Bad("trace_invalid")
    items = tuple(trace)
    events = []
    for i, ev in enumerate(items):
        if type(ev) is not dict:
            raise _Bad("event_not_dict")
        _keys(ev, "event_key_invalid")
        kind = ev.get("kind")
        if type(kind) is not str or kind not in KINDS:
            raise _Bad("event_kind_invalid")
        if sorted(ev) != sorted(EVENT_FIELDS[kind]):
            raise _Bad("event_fields_invalid")
        cid = ev["choice"]
        if type(cid) is not str or cid not in snap_choices:
            raise _Bad("event_choice_unknown")
        acc = None
        if kind in (REPORT, SELF_CORRECT):
            reason = ev["reason"]
            if not _is_str(reason) or reason.strip() == "":
                raise _Bad("reason_missing")
            acc = ev["acceptable"]
            if type(acc) is not bool:
                raise _Bad("acceptable_invalid")
        if kind == COMMIT_EVENT and i != len(items) - 1:
            raise _Bad("commit_not_last")
        events.append({"kind": kind, "choice": cid, "acceptable": acc})
    if events[-1]["kind"] != COMMIT_EVENT:
        raise _Bad("commit_missing")
    return {"task_id": task_id, "requirements": reqs,
            "choices": snap_choices, "events": tuple(events)}


def _record(task_id, decision, reason, choice, dropped, claimed, detail):
    return {"task_id": task_id, "decision": decision, "reason": reason,
            "choice": choice, "dropped": dropped,
            "acceptable_claimed": claimed, "detail": detail}


def _config(detail):
    return _record(None, REJECT, CONFIG_ERROR, None, (), False, detail)


def _run(snap):
    """Decide from the validated snapshot only."""
    requirements = snap["requirements"]
    choices = snap["choices"]
    reported = set()
    claimed = {}
    passed = {}
    for ev in snap["events"]:
        kind = ev["kind"]
        cid = ev["choice"]
        if kind == REPORT:
            reported.add(cid)
            claimed[cid] = ev["acceptable"]
            # A new report must be checked again.
            passed.pop(cid, None)
        elif kind == SELF_CORRECT:
            reported.add(cid)
            claimed[cid] = ev["acceptable"]
            # A self-correction re-opens every choice: nothing stays checked.
            passed.clear()
        elif kind == CHECK:
            passed[cid] = check(choices[cid], requirements)
        else:
            break
    tid = snap["task_id"]
    acc = claimed.get(cid, False)
    label_dropped = check(choices[cid], requirements)[1]
    if cid not in reported:
        return _record(tid, REFUSE, UNREPORTED, cid, label_dropped, acc, "commit_without_report")
    if cid not in passed:
        return _record(tid, REFUSE, UNCHECKED, cid, label_dropped, acc, "no_check_after_latest_report")
    ok, dropped = passed[cid]
    if not ok:
        return _record(tid, REFUSE, DROPS, cid, dropped, acc, "check_failed")
    return _record(tid, COMMIT, ALL_MET, cid, dropped, acc, "check_passed")


def evaluate(task, trace):
    """Gate the single commit at the end of trace. Never raises."""
    try:
        snap = validate(task, trace)
    except _Bad as exc:
        return _config(str(exc))
    except Exception:
        return _config("internal_error")
    try:
        return _run(snap)
    except Exception:
        return _config("internal_error")
