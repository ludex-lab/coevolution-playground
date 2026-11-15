"""Informational friction: a deterministic, stdlib-only method sketch.

A pure function over a fixture observation sequence. There is no monitor
loop, no thread, no sleep and no clock: the caller passes the sequence
and the evaluation time ``now``.

A task declares outstanding requirements, a friction bound, a deadline,
an on_expiry outcome and a novelty rule. Each observation names a piece
of evidence and may resolve one requirement:

    {"t": int, "evidence": str, "resolves": requirement_id, "novel": bool}

("resolves" is optional; "novel" is required under the declared rule
NOVELTY_DECLARED and not permitted under NOVELTY_EVIDENCE_KEY.)

Each counted observation (time before the deadline, before success) is
one of:

    RESOLVED   it resolves a requirement that was still unresolved
    EXPLORE    no new resolution, but the evidence is new under the
               declared novelty rule (purposeful exploration)
    RECURRENT  no new resolution and the evidence is not new

Progress is the unresolved count going down. Friction counts RECURRENT
observations in a row; a RESOLVED or EXPLORE observation resets it to 0.
When friction goes past the declared bound before the deadline, gathering
stops fail-closed (decision STOP): the run cannot declare success, and
later observations are not counted. A call with ``now`` at or after the
deadline returns the declared on_expiry, regardless of prior or later
observations, including after STOP or SUCCESS; a missing on_expiry is
config_error; nothing is dispatched on timeout.

``evaluate(task, observations, now)`` returns a record:

    {"task_id", "decision", "reason", "detail", "unresolved", "friction",
     "signals", "on_expiry"}

decision is one of SUCCESS, CONTINUE, STOP, HOLD, ESCALATE, DENY, REJECT.
SUCCESS only when every requirement is resolved before the deadline and
before the bound is passed, and ``now`` is still before the deadline.

Expiry guard: any call with ``now`` at or after the deadline returns the
declared on_expiry, as this module's own constant, regardless of prior
or later observations, including after STOP or SUCCESS: never SUCCESS,
CONTINUE or STOP, and nothing is dispatched on timeout. The event times
``t`` are asserted by the caller, so a later call could present evidence
backdated to before the deadline; with the guard, such evidence cannot
turn an expiry into a success or a stop. A SUCCESS or STOP is read from
a call made before the deadline. At expiry, ``unresolved``, ``friction``
and ``signals`` still describe the counted observations, as plain
information only. A missing friction bound, on_expiry or novelty rule is
a config_error.

``signals`` is a tuple of (t, kind, unresolved_count, friction) per
counted observation: the two signals of the method, as plain data.

Inputs are checked by exact type (``type(x) is str`` and so on).
evaluate() does not raise: any failure is REJECT with config_error. A
config_error record never echoes the caller's task_id.
"""

SUCCESS = "SUCCESS"
CONTINUE = "CONTINUE"
STOP = "STOP"
REJECT = "REJECT"
HOLD = "HOLD"
ESCALATE = "ESCALATE"
DENY = "DENY"
ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY)
DECISIONS = (SUCCESS, CONTINUE, STOP, REJECT) + ON_EXPIRY_VALUES

ALL_RESOLVED = "all_resolved"
GATHERING = "gathering"
FRICTION_BOUND = "friction_bound"
EXPIRED = "expired"
CONFIG_ERROR = "config_error"
ON_UNMEASURED = "on_unmeasured"
REASONS = (ALL_RESOLVED, GATHERING, FRICTION_BOUND, EXPIRED, CONFIG_ERROR,
           ON_UNMEASURED)

RESOLVED = "resolved"
EXPLORE = "explore"
RECURRENT = "recurrent"
KINDS = (RESOLVED, EXPLORE, RECURRENT)

NOVELTY_EVIDENCE_KEY = "evidence_key"
NOVELTY_DECLARED = "declared"
NOVELTY_RULES = (NOVELTY_EVIDENCE_KEY, NOVELTY_DECLARED)

TASK_FIELDS = ("task_id", "requirements", "friction_bound", "deadline",
               "on_expiry", "novelty_rule")
OBS_FIELDS = ("t", "evidence", "resolves", "novel")

D_TASK = "bad_task"
D_REQUIREMENTS = "bad_requirements"
D_BOUND_MISSING = "friction_bound_missing"
D_BOUND_INVALID = "friction_bound_invalid"
D_DEADLINE = "bad_deadline"
D_ON_EXPIRY_MISSING = "on_expiry_missing"
D_ON_EXPIRY_INVALID = "on_expiry_invalid"
D_RULE_MISSING = "novelty_rule_missing"
D_RULE_INVALID = "novelty_rule_invalid"
D_OBS = "bad_observation"
D_NOW = "bad_now"
D_INTERNAL = "internal_error"
DETAILS = (None, D_TASK, D_REQUIREMENTS, D_BOUND_MISSING, D_BOUND_INVALID,
           D_DEADLINE, D_ON_EXPIRY_MISSING, D_ON_EXPIRY_INVALID,
           D_RULE_MISSING, D_RULE_INVALID, D_OBS, D_NOW, D_INTERNAL)

RECORD_FIELDS = ("task_id", "decision", "reason", "detail", "unresolved",
                 "friction", "signals", "on_expiry")


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
    """Return the module's own constant equal to value, else None."""
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
        if not _is_str(key) or _canonical(key, fields) is None:
            raise _Bad(detail)


def domain_results():
    """The paper's eight-domain and RL results are not measured here."""
    return ON_UNMEASURED


def validate_task(task):
    """Return (task_id, requirements, bound, deadline, on_expiry, rule)."""
    _check_keys(task, TASK_FIELDS, D_TASK)
    if "task_id" not in task:
        raise _Bad(D_TASK)
    # Read once; the same local is validated and returned.
    task_id = task["task_id"]
    if not _is_str(task_id) or not task_id:
        raise _Bad(D_TASK)
    reqs = task.get("requirements")
    if type(reqs) is not list or not reqs:
        raise _Bad(D_REQUIREMENTS)
    seen = []
    for req in reqs:
        if not _is_str(req) or not req or req in seen:
            raise _Bad(D_REQUIREMENTS)
        seen.append(req)
    if "friction_bound" not in task:
        raise _Bad(D_BOUND_MISSING)
    bound = task["friction_bound"]
    if not _is_int(bound) or bound < 0:
        raise _Bad(D_BOUND_INVALID)
    deadline = task.get("deadline")
    if not _is_int(deadline) or deadline <= 0:
        raise _Bad(D_DEADLINE)
    if "on_expiry" not in task:
        raise _Bad(D_ON_EXPIRY_MISSING)
    on_expiry = _canonical(task["on_expiry"], ON_EXPIRY_VALUES)
    if on_expiry is None:
        raise _Bad(D_ON_EXPIRY_INVALID)
    if "novelty_rule" not in task:
        raise _Bad(D_RULE_MISSING)
    rule = _canonical(task["novelty_rule"], NOVELTY_RULES)
    if rule is None:
        raise _Bad(D_RULE_INVALID)
    return task_id, tuple(seen), bound, deadline, on_expiry, rule


def validate_observations(observations, requirements, rule, now):
    """Return a list of (t, evidence, resolves_or_None, novel_or_None)."""
    if not _is_int(now) or now < 0:
        raise _Bad(D_NOW)
    if type(observations) is not list:
        raise _Bad(D_OBS)
    out = []
    last_t = 0
    for obs in observations:
        _check_keys(obs, OBS_FIELDS, D_OBS)
        t = obs.get("t")
        if not _is_int(t) or t < last_t or t > now:
            raise _Bad(D_OBS)
        last_t = t
        evidence = obs.get("evidence")
        if not _is_str(evidence) or not evidence:
            raise _Bad(D_OBS)
        resolves = None
        if "resolves" in obs:
            resolves = obs["resolves"]
            if not _is_str(resolves) or resolves not in requirements:
                raise _Bad(D_OBS)
        novel = None
        if rule == NOVELTY_DECLARED:
            if "novel" not in obs:
                raise _Bad(D_OBS)
            novel = obs["novel"]
            if type(novel) is not bool:
                raise _Bad(D_OBS)
        elif "novel" in obs:
            raise _Bad(D_OBS)
        out.append((t, evidence, resolves, novel))
    return out


def _record(task_id, decision, reason, detail=None, unresolved=(), friction=0,
            signals=(), on_expiry=None):
    return {
        "task_id": task_id,
        "decision": decision,
        "reason": reason,
        "detail": detail,
        "unresolved": unresolved,
        "friction": friction,
        "signals": signals,
        "on_expiry": on_expiry,
    }


def _count(reqs, bound, deadline, rule, obs):
    """Return (decision, reason, unresolved, friction, signals) before expiry."""
    unresolved = list(reqs)
    seen_evidence = set()
    friction = 0
    signals = []
    for t, evidence, resolves, novel in obs:
        if t >= deadline:
            # Late observations do not count.
            break
        if resolves is not None and resolves in unresolved:
            unresolved.remove(resolves)
            kind = RESOLVED
            friction = 0
        else:
            if rule == NOVELTY_DECLARED:
                is_new = novel
            else:
                is_new = evidence not in seen_evidence
            if is_new:
                kind = EXPLORE
                friction = 0
            else:
                kind = RECURRENT
                friction += 1
        seen_evidence.add(evidence)
        signals.append((t, kind, len(unresolved), friction))
        if friction > bound:
            # Fail closed: gathering stops and success cannot be declared.
            return (STOP, FRICTION_BOUND, tuple(sorted(unresolved)), friction,
                    tuple(signals))
        if not unresolved:
            # Observations after completion are not counted.
            return SUCCESS, ALL_RESOLVED, (), friction, tuple(signals)
    return (CONTINUE, GATHERING, tuple(sorted(unresolved)), friction,
            tuple(signals))


def _evaluate(task, observations, now):
    try:
        task_id, reqs, bound, deadline, on_expiry, rule = validate_task(task)
        obs = validate_observations(observations, reqs, rule, now)
    except _Bad as bad:
        # Never echo the caller's task_id on a config_error.
        return _record(None, REJECT, CONFIG_ERROR, bad.detail)
    decision, reason, left, friction, signals = _count(reqs, bound, deadline,
                                                       rule, obs)
    if now >= deadline:
        # Expiry guard: at or after the deadline the declared on_expiry is
        # returned whatever the observations say, so evidence backdated by
        # a later call cannot overturn an expiry. Never SUCCESS, CONTINUE or
        # STOP on timeout; the decision is this module's own constant.
        decision, reason = on_expiry, EXPIRED
    return _record(task_id, decision, reason, None, left, friction, signals,
                   on_expiry)


def evaluate(task, observations, now):
    """Return a record. Does not raise; failures are config_error."""
    try:
        return _evaluate(task, observations, now)
    except Exception:
        return _record(None, REJECT, CONFIG_ERROR, D_INTERNAL)
