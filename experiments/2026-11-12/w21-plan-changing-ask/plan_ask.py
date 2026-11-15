"""Ask for the fact that changes the plan: a deterministic, stdlib-only sketch.

A task is a partial request plus facts held by an operator. Each fact
carries a declared fixture label:

    plan_changing  the plan is wrong or infeasible without it
    inert          similarly worded, but the plan does not depend on it

The labels are fixture declarations. This module has no optimality
solver and does not decide which plan is optimal; ``optimality()``
returns ON_UNMEASURED for every task. A fact with no label is
ON_UNMEASURED and the task never resolves to ACT.

An agent trace is a list of events at integer times:

    {"t": int, "kind": "ask",    "fact": fact_id}
    {"t": int, "kind": "answer", "fact": fact_id}   (operator reply)
    {"t": int, "kind": "act"}

``decide(task, trace, now)`` returns a record:

    {"task_id", "decision", "reason", "detail", "missing", "on_expiry"}

decision is one of ACT, REJECT, WAIT, HOLD, ESCALATE, DENY. ACT is
returned only when the act event comes before the deadline and every
plan_changing fact was answered before it. Asking is not knowing: an
ask with no answer does not count. Inert answers never stand in for a
plan_changing one.

Silence is not consent. Every task declares a positive integer deadline
and an on_expiry in {HOLD, ESCALATE, DENY}. When ``now`` reaches the
deadline with no valid act before it, the declared on_expiry is
returned as this module's own constant, never the caller's object, and
never ACT. A missing or invalid on_expiry is a config_error.

Inputs are checked by exact type (``type(x) is str`` and so on), never
by isinstance or equality alone. No part of the input is read before the
key and type checks that guard it: every mapping has all of its keys
confirmed as exact str before any lookup, so no caller-defined __eq__,
__hash__ or other method ever runs. Every value in a record is None, a
module constant, a tuple of exact-str fact ids from the validated task,
or the task_id, which is echoed only once the task has passed
validation.

decide() does not raise on any input: every Exception inside it,
including RecursionError and MemoryError, becomes REJECT with reason
config_error, and the fallback record is built without a further call.
Only BaseException signals that do not come from the input
(KeyboardInterrupt, SystemExit, GeneratorExit raised by the runtime) are
left to propagate; no caller code runs inside decide() that could raise
them. If the interpreter has no recursion headroom to enter decide() at
all, the RecursionError is raised at the call site, before decide() runs.
"""

ACT = "ACT"
REJECT = "REJECT"
WAIT = "WAIT"
HOLD = "HOLD"
ESCALATE = "ESCALATE"
DENY = "DENY"
ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY)
DECISIONS = (ACT, REJECT, WAIT) + ON_EXPIRY_VALUES

VALID = "valid"
MISSING_PLAN_CHANGING = "missing_plan_changing"
AWAITING = "awaiting"
EXPIRED = "expired"
CONFIG_ERROR = "config_error"
ON_UNMEASURED = "on_unmeasured"
REASONS = (VALID, MISSING_PLAN_CHANGING, AWAITING, EXPIRED, CONFIG_ERROR,
           ON_UNMEASURED)

PLAN_CHANGING = "plan_changing"
INERT = "inert"
LABELS = (PLAN_CHANGING, INERT)

ASK = "ask"
ANSWER = "answer"
ACT_EVENT = "act"
KINDS = (ASK, ANSWER, ACT_EVENT)

TASK_FIELDS = ("task_id", "request", "facts", "deadline", "on_expiry")
REQUIRED_TASK_FIELDS = ("task_id", "request", "facts", "deadline")
FACT_FIELDS = ("text", "label")
EVENT_FIELDS = ("t", "kind", "fact")

# detail codes (module constants only)
D_NONE = None
D_TASK = "bad_task"
D_FACT = "bad_fact"
D_LABEL = "bad_label"
D_UNLABELED = "unlabeled_fact"
D_DEADLINE = "bad_deadline"
D_ON_EXPIRY_MISSING = "on_expiry_missing"
D_ON_EXPIRY_INVALID = "on_expiry_invalid"
D_TRACE = "bad_trace"
D_NOW = "bad_now"
D_INTERNAL = "internal_error"
DETAILS = (D_NONE, D_TASK, D_FACT, D_LABEL, D_UNLABELED, D_DEADLINE,
           D_ON_EXPIRY_MISSING, D_ON_EXPIRY_INVALID, D_TRACE, D_NOW,
           D_INTERNAL)

RECORD_FIELDS = ("task_id", "decision", "reason", "detail", "missing",
                 "on_expiry")


class _Bad(Exception):
    """Internal: carries a detail code to a config_error record."""

    def __init__(self, detail):
        Exception.__init__(self, detail)
        self.detail = detail


def _is_str(value):
    """Exact str only; a str subclass is rejected."""
    return type(value) is str


def _is_int(value):
    """Exact int only; bool and int subclasses are rejected."""
    return type(value) is int


def _canonical(value, choices):
    """Return the module's own constant equal to value, else None.

    value must be an exact str, so no caller-defined __eq__ runs.
    """
    if not _is_str(value):
        return None
    for choice in choices:
        if value == choice:
            return choice
    return None


def _check_keys(mapping, fields, detail):
    if type(mapping) is not dict:
        raise _Bad(detail)
    for key in mapping:
        if not _is_str(key):
            raise _Bad(detail)
        if _canonical(key, fields) is None:
            raise _Bad(detail)


def optimality(task):
    """No solver here: optimality of any plan is not measured."""
    return ON_UNMEASURED


def validate_task(task):
    """Return (task_id, labels, deadline, on_expiry) or raise _Bad.

    labels maps fact_id -> PLAN_CHANGING, INERT or None (unlabeled).
    """
    _check_keys(task, TASK_FIELDS, D_TASK)
    for key in REQUIRED_TASK_FIELDS:
        if key not in task:
            raise _Bad(D_TASK)
    task_id = task["task_id"]
    if not _is_str(task_id) or not task_id:
        raise _Bad(D_TASK)
    if not _is_str(task["request"]) or not task["request"]:
        raise _Bad(D_TASK)
    deadline = task["deadline"]
    if not _is_int(deadline) or deadline <= 0:
        raise _Bad(D_DEADLINE)
    if "on_expiry" not in task:
        raise _Bad(D_ON_EXPIRY_MISSING)
    on_expiry = _canonical(task["on_expiry"], ON_EXPIRY_VALUES)
    if on_expiry is None:
        raise _Bad(D_ON_EXPIRY_INVALID)
    facts = task["facts"]
    if type(facts) is not dict:
        raise _Bad(D_FACT)
    # First pass: every fact id is an exact, non-empty str before any lookup.
    for fact_id in facts:
        if not _is_str(fact_id) or not fact_id:
            raise _Bad(D_FACT)
    labels = {}
    for fact_id in facts:
        fact = facts[fact_id]
        _check_keys(fact, FACT_FIELDS, D_FACT)
        if "text" not in fact or not _is_str(fact["text"]) or not fact["text"]:
            raise _Bad(D_FACT)
        if "label" in fact:
            label = _canonical(fact["label"], LABELS)
            if label is None:
                raise _Bad(D_LABEL)
        else:
            label = None
        labels[fact_id] = label
    return task_id, labels, deadline, on_expiry


def validate_trace(trace, labels, now):
    """Return a list of (t, kind, fact_id) with module-constant kinds."""
    if not _is_int(now) or now < 0:
        raise _Bad(D_NOW)
    if type(trace) is not list:
        raise _Bad(D_TRACE)
    out = []
    asked = set()
    last_t = 0
    for i, event in enumerate(trace):
        _check_keys(event, EVENT_FIELDS, D_TRACE)
        if "t" not in event or "kind" not in event:
            raise _Bad(D_TRACE)
        t = event["t"]
        if not _is_int(t) or t < last_t or t > now:
            raise _Bad(D_TRACE)
        last_t = t
        kind = _canonical(event["kind"], KINDS)
        if kind is None:
            raise _Bad(D_TRACE)
        if kind == ACT_EVENT:
            if "fact" in event or i != len(trace) - 1:
                raise _Bad(D_TRACE)
            out.append((t, kind, None))
            continue
        fact_id = event.get("fact")
        if not _is_str(fact_id) or fact_id not in labels:
            raise _Bad(D_TRACE)
        if kind == ANSWER and fact_id not in asked:
            raise _Bad(D_TRACE)
        if kind == ASK:
            asked.add(fact_id)
        out.append((t, kind, fact_id))
    return out


def _record(task_id, decision, reason, detail=None, missing=(), on_expiry=None):
    return {
        "task_id": task_id,
        "decision": decision,
        "reason": reason,
        "detail": detail,
        "missing": missing,
        "on_expiry": on_expiry,
    }


def _decide(task, trace, now):
    # Nothing is read from the input before validate_task: the task_id is
    # echoed only after the whole task has passed validation.
    try:
        task_id, labels, deadline, on_expiry = validate_task(task)
    except _Bad as bad:
        return _record(None, REJECT, CONFIG_ERROR, bad.detail)
    try:
        events = validate_trace(trace, labels, now)
    except _Bad as bad:
        return _record(task_id, REJECT, CONFIG_ERROR, bad.detail)
    if any(label is None for label in labels.values()):
        return _record(task_id, REJECT, ON_UNMEASURED, D_UNLABELED,
                       (), on_expiry)
    required = sorted(f for f, label in labels.items() if label == PLAN_CHANGING)
    known = set()
    for t, kind, fact_id in events:
        if t >= deadline:
            # The deadline has passed: late answers and late acts do not count.
            break
        if kind == ANSWER:
            known.add(fact_id)
        elif kind == ACT_EVENT:
            missing = tuple(f for f in required if f not in known)
            if missing:
                return _record(task_id, REJECT, MISSING_PLAN_CHANGING, None,
                               missing, on_expiry)
            return _record(task_id, ACT, VALID, None, (), on_expiry)
    missing = tuple(f for f in required if f not in known)
    if now >= deadline:
        # No valid act before the deadline: the declared outcome, as this
        # module's own constant. Never ACT on timeout.
        return _record(task_id, on_expiry, EXPIRED, None, missing, on_expiry)
    return _record(task_id, WAIT, AWAITING, None, missing, on_expiry)


def decide(task, trace, now):
    """Return a decision record; failures are REJECT with config_error.

    Any Exception inside (RecursionError and MemoryError included) is
    caught. The fallback is a dict literal, so it needs no further call
    frame.
    """
    try:
        return _decide(task, trace, now)
    except Exception:
        return {"task_id": None, "decision": REJECT, "reason": CONFIG_ERROR,
                "detail": D_INTERNAL, "missing": (), "on_expiry": None}
