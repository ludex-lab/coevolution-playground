"""Falsification-gated memory admission: a deterministic, stdlib-only sketch.

A candidate lesson is a hypothesis

    {"id", "precondition", "behavior_change", "expected_effect", "verifier"}

taken from an episode that went well locally. Local success alone never
writes the lesson into memory. admit(store, request) applies the hypothesis
only in a temporary state (a copy of the store's lessons plus the
candidate), runs three fixture probes on that copy, and returns a record
whose outcome is one of:

    commit        all three probes passed; the lesson is written to the store
    refine        no false prediction, but the measured gain or risk misses
                  commit; fixture-declared thresholds decide refine vs reject;
                  nothing is written
    reject        a probe failed; nothing is written
    on_unmeasured a required probe was not run (or ran on no task the lesson
                  claims to cover); nothing is written (fail closed)
    expired       the declared deadline ran out; the record carries the
                  declared on_expiry (hold, escalate or deny); nothing is
                  written
    config_error  malformed input; nothing is written

The three probes:

    target_transfer      tasks the lesson is meant to help; every task must
                         succeed on the temporary state and at least one must
                         fail on the current store (a measured gain)
    falsification        tasks where the precondition holds and a false or
                         over-general lesson would act wrongly; every task
                         must succeed, and the candidate itself must decide
                         at least one task (matched by its precondition and
                         not already decided by a stored lesson); else the
                         probe tested nothing and the outcome is
                         on_unmeasured
    archived_regression  archived tasks; no task that succeeds on the current
                         store may fail on the temporary state, and the
                         current store must solve at least one archived task
                         (else there is nothing to regress and the outcome
                         is on_unmeasured)

The store is an in-memory list only. Nothing here opens files, databases or
network links. Inputs are checked by exact type (type(x) is str / dict / list /
int / bool). admit() catches any internal error and returns config_error, so
it does not raise on bad input, and every error path leaves the store as it
was. A config_error record never echoes a hypothesis id: the id is read only
after validation passes.

The deadline is not a clock: expiry is the caller's declared `expired`
flag, and timeout_s is validated but not used. Lesson ids are claimed with
one dict.setdefault call at commit time, so a duplicate id is refused there
too, even if it slipped past the earlier check.
"""

COMMIT = "commit"
REFINE = "refine"
REJECT = "reject"
ON_UNMEASURED = "on_unmeasured"
EXPIRED = "expired"
CONFIG_ERROR = "config_error"
OUTCOMES = (COMMIT, REFINE, REJECT, ON_UNMEASURED, EXPIRED, CONFIG_ERROR)

TARGET_TRANSFER = "target_transfer"
FALSIFICATION = "falsification"
ARCHIVED_REGRESSION = "archived_regression"
REQUIRED_PROBES = (TARGET_TRANSFER, FALSIFICATION, ARCHIVED_REGRESSION)

# Reasons.
ALL_PROBES_PASSED = "all_probes_passed"
SOURCE_EPISODE_FAILED = "source_episode_failed"
TRANSFER_FAILED = "transfer_failed"
FALSIFICATION_FAILED = "falsification_failed"
REGRESSION_FAILED = "archived_regression"
WITHIN_REFINE_BOUNDS = "within_refine_bounds"
PROBE_NOT_RUN = "probe_not_run"
PROBE_VACUOUS = "probe_vacuous"
REASONS = (ALL_PROBES_PASSED, SOURCE_EPISODE_FAILED, TRANSFER_FAILED,
           FALSIFICATION_FAILED, REGRESSION_FAILED, WITHIN_REFINE_BOUNDS,
           PROBE_NOT_RUN, PROBE_VACUOUS, EXPIRED, CONFIG_ERROR)

HOLD = "hold"
ESCALATE = "escalate"
DENY = "deny"
ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY)

ACTION_MATCHES_EXPECTED = "action_matches_expected"
VERIFIERS = (ACTION_MATCHES_EXPECTED,)

HYPOTHESIS_FIELDS = ("id", "precondition", "behavior_change",
                     "expected_effect", "verifier")
REQUEST_FIELDS = ("hypothesis", "local_success", "probes", "thresholds")
OPTIONAL_REQUEST_FIELDS = ("deadline",)
THRESHOLD_FIELDS = ("refine_min_gain_pct", "refine_max_risk_pct")
DEADLINE_FIELDS = ("timeout_s", "on_expiry", "expired")
TASK_FIELDS = ("id", "features", "default_action", "expected_action")

RECORD_FIELDS = ("hypothesis_id", "outcome", "reason", "on_expiry",
                 "failed_probes", "measures", "committed")


def _is_str(value):
    return type(value) is str


def _is_nonempty_str(value):
    return type(value) is str and len(value) > 0


def _is_dict(value):
    return type(value) is dict


def _is_list(value):
    return type(value) is list


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


def _str_copy(value):
    """A plain str copy of an exact str (never the caller's object)."""
    return "".join(value)


class MemoryStore(object):
    """Persistent lessons for this sketch: an in-memory list, nothing else.

    Lessons are (id, key, value, action) tuples of plain str. The first
    lesson whose precondition matches a task decides the action, so lessons
    committed earlier take precedence over later ones.
    """

    def __init__(self, lessons=()):
        """Seed lessons are hypothesis dicts and are validated like a
        candidate; a malformed or duplicate seed lesson raises ValueError."""
        self._lessons = []
        self._claimed = {}
        for lesson in lessons:
            error = validate_hypothesis(lesson)
            if error is not None:
                raise ValueError("seed lesson: " + error)
            frozen = _freeze(lesson)
            if not self._commit(frozen):
                raise ValueError("seed lesson: duplicate id")

    def lessons(self):
        return tuple(self._lessons)

    def ids(self):
        return tuple(lesson[0] for lesson in self._lessons)

    def act(self, task):
        return act(self._lessons, task)

    def _commit(self, lesson):
        """Append lesson unless its id is already claimed; True on success.

        The claim is a single dict.setdefault call with a plain-str key, so
        two admits racing on one id cannot both win it.
        """
        token = object()
        if self._claimed.setdefault(lesson[0], token) is not token:
            return False
        self._lessons.append(lesson)
        return True


def parse_precondition(text):
    """'key=value' with non-empty key and value -> (key, value), else None."""
    if not _is_nonempty_str(text) or text.count("=") != 1:
        return None
    key, value = text.split("=")
    if not key or not value:
        return None
    return key, value


def _freeze(hypothesis):
    """Plain-str tuple built from a validated hypothesis dict."""
    key, value = parse_precondition(hypothesis["precondition"])
    return (_str_copy(hypothesis["id"]), _str_copy(key), _str_copy(value),
            _str_copy(hypothesis["behavior_change"]))


def matches(lesson, task):
    return task["features"].get(lesson[1]) == lesson[2]


def act(lessons, task):
    """First matching lesson decides; otherwise the task's default action."""
    for lesson in lessons:
        if matches(lesson, task):
            return lesson[3]
    return task["default_action"]


def verify(verifier, action, task):
    if verifier == ACTION_MATCHES_EXPECTED:
        return action == task["expected_action"]
    return False


# ---- validation ---------------------------------------------------------

def validate_task(task):
    if not _is_dict(task):
        return "task is not a mapping"
    for key in task:
        if _canonical(key, TASK_FIELDS) is None:
            return "unknown task field"
    for key in TASK_FIELDS:
        if key not in task:
            return "missing task field"
    if not _is_nonempty_str(task["id"]):
        return "task id must be a non-empty string"
    features = task["features"]
    if not _is_dict(features):
        return "task features must be a mapping"
    for key in features:
        if not _is_nonempty_str(key) or not _is_nonempty_str(features[key]):
            return "task features must map strings to strings"
    if not _is_nonempty_str(task["default_action"]):
        return "default_action must be a non-empty string"
    if not _is_nonempty_str(task["expected_action"]):
        return "expected_action must be a non-empty string"
    return None


def validate_hypothesis(hyp):
    """None when hyp is a well-formed hypothesis dict, else an error string."""
    if not _is_dict(hyp):
        return "hypothesis is not a mapping"
    for key in hyp:
        if _canonical(key, HYPOTHESIS_FIELDS) is None:
            return "unknown hypothesis field"
    for key in HYPOTHESIS_FIELDS:
        if key not in hyp:
            return "missing hypothesis field: %s" % (key,)
        if not _is_nonempty_str(hyp[key]):
            return "hypothesis %s must be a non-empty string" % (key,)
    if parse_precondition(hyp["precondition"]) is None:
        return "precondition must be key=value"
    if _canonical(hyp["verifier"], VERIFIERS) is None:
        return "unknown verifier"
    return None


def validate(store, request):
    """None when (store, request) is well formed, else a short error string."""
    if type(store) is not MemoryStore:
        return "store is not a MemoryStore"
    if not _is_dict(request):
        return "request is not a mapping"
    for key in request:
        if _canonical(key, REQUEST_FIELDS + OPTIONAL_REQUEST_FIELDS) is None:
            return "unknown request field"
    for key in REQUEST_FIELDS:
        if key not in request:
            return "missing request field: %s" % (key,)
    hyp = request["hypothesis"]
    error = validate_hypothesis(hyp)
    if error is not None:
        return error
    if hyp["id"] in store.ids():
        return "hypothesis id already in the store"
    if type(request["local_success"]) is not bool:
        return "local_success must be a boolean"
    probes = request["probes"]
    if not _is_dict(probes):
        return "probes is not a mapping"
    for key in probes:
        if _canonical(key, REQUIRED_PROBES) is None:
            return "unknown probe"
        tasks = probes[key]
        if not _is_list(tasks):
            return "probe tasks must be a list"
        for task in tasks:
            error = validate_task(task)
            if error is not None:
                return error
    thresholds = request["thresholds"]
    if not _is_dict(thresholds):
        return "thresholds is not a mapping"
    for key in thresholds:
        if _canonical(key, THRESHOLD_FIELDS) is None:
            return "unknown threshold"
    for key in THRESHOLD_FIELDS:
        if key not in thresholds:
            return "threshold not declared: %s" % (key,)
    gain = thresholds["refine_min_gain_pct"]
    risk = thresholds["refine_max_risk_pct"]
    if not _is_int(gain) or gain < 1 or gain > 100:
        return "refine_min_gain_pct must be an int in 1..100"
    if not _is_int(risk) or risk < 0 or risk > 100:
        return "refine_max_risk_pct must be an int in 0..100"
    if "deadline" in request:
        deadline = request["deadline"]
        if not _is_dict(deadline):
            return "deadline is not a mapping"
        for key in deadline:
            if _canonical(key, DEADLINE_FIELDS) is None:
                return "unknown deadline field"
        timeout = deadline.get("timeout_s")
        if not _is_int(timeout) or timeout <= 0:
            return "deadline.timeout_s must be a positive int"
        if "on_expiry" not in deadline:
            return "deadline declares a timeout without on_expiry"
        if _canonical(deadline["on_expiry"], ON_EXPIRY_VALUES) is None:
            return "deadline.on_expiry must be one of %s" % (ON_EXPIRY_VALUES,)
        if "expired" in deadline and type(deadline["expired"]) is not bool:
            return "deadline.expired must be a boolean"
    return None


# ---- probes -------------------------------------------------------------

def _measure(base, temp, lesson, verifier, tasks):
    """Counts for one probe: n, base_ok, temp_ok, broken, matched, decided.

    matched: tasks the candidate's precondition matches.
    decided: matched tasks no stored lesson already decides, i.e. tasks
    where the candidate's behavior_change is what runs on the temporary
    state.
    """
    n = base_ok = temp_ok = broken = matched = decided = 0
    for task in tasks:
        n += 1
        b = verify(verifier, act(base, task), task)
        t = verify(verifier, act(temp, task), task)
        base_ok += 1 if b else 0
        temp_ok += 1 if t else 0
        broken += 1 if (b and not t) else 0
        hit = matches(lesson, task)
        matched += 1 if hit else 0
        shadowed = any(matches(old, task) for old in base)
        decided += 1 if (hit and not shadowed) else 0
    return {"n": n, "base_ok": base_ok, "temp_ok": temp_ok,
            "broken": broken, "matched": matched, "decided": decided}


def _record(hid, outcome, reason, on_expiry=None, failed=(), measures=None,
            committed=False):
    return {
        "hypothesis_id": hid,
        "outcome": outcome,
        "reason": reason,
        "on_expiry": on_expiry,
        "failed_probes": tuple(failed),
        "measures": measures,
        "committed": committed,
    }


def _admit(store, request):
    error = validate(store, request)
    if error is not None:
        return _record(None, CONFIG_ERROR, CONFIG_ERROR)
    # Read only after validation: every key is an exact str by now.
    hid = _str_copy(request["hypothesis"]["id"])
    deadline = request.get("deadline")
    on_expiry = None
    if deadline is not None:
        on_expiry = _canonical(deadline["on_expiry"], ON_EXPIRY_VALUES)
        if deadline.get("expired", False) is True:
            # Never act or commit on a timeout: the declared outcome is
            # recorded and the store is untouched.
            return _record(hid, EXPIRED, EXPIRED, on_expiry)
    if request["local_success"] is not True:
        return _record(hid, REJECT, SOURCE_EPISODE_FAILED, on_expiry)
    hyp = request["hypothesis"]
    verifier = _canonical(hyp["verifier"], VERIFIERS)
    lesson = _freeze(hyp)
    probes = request["probes"]
    for name in REQUIRED_PROBES:
        if name not in probes or len(probes[name]) == 0:
            return _record(hid, ON_UNMEASURED, PROBE_NOT_RUN, on_expiry,
                           (name,))
    # Temporary state: a copy of the current lessons plus the candidate.
    base = list(store._lessons)
    temp = list(store._lessons) + [lesson]
    measures = {}
    for name in REQUIRED_PROBES:
        measures[name] = _measure(base, temp, lesson, verifier, probes[name])
    tr = measures[TARGET_TRANSFER]
    fa = measures[FALSIFICATION]
    rg = measures[ARCHIVED_REGRESSION]
    if fa["decided"] == 0:
        # The candidate never ran on a falsification task.
        return _record(hid, ON_UNMEASURED, PROBE_VACUOUS, on_expiry,
                       (FALSIFICATION,), measures)
    if rg["base_ok"] == 0:
        # The current store solves no archived task: nothing to regress.
        return _record(hid, ON_UNMEASURED, PROBE_VACUOUS, on_expiry,
                       (ARCHIVED_REGRESSION,), measures)
    gain = tr["temp_ok"] - tr["base_ok"]
    transfer_ok = tr["temp_ok"] == tr["n"] and gain > 0
    falsification_ok = fa["temp_ok"] == fa["n"]
    regression_ok = rg["broken"] == 0
    failed = []
    if not transfer_ok:
        failed.append(TARGET_TRANSFER)
    if not falsification_ok:
        failed.append(FALSIFICATION)
    if not regression_ok:
        failed.append(ARCHIVED_REGRESSION)
    if not falsification_ok:
        return _record(hid, REJECT, FALSIFICATION_FAILED, on_expiry, failed,
                       measures)
    if transfer_ok and regression_ok:
        if not store._commit(lesson):
            # The id was claimed after validation (a concurrent admit).
            return _record(hid, CONFIG_ERROR, CONFIG_ERROR, on_expiry)
        return _record(hid, COMMIT, ALL_PROBES_PASSED, on_expiry, failed,
                       measures, True)
    th = request["thresholds"]
    gain_ok = gain > 0 and 100 * gain >= th["refine_min_gain_pct"] * tr["n"]
    risk_ok = 100 * rg["broken"] <= th["refine_max_risk_pct"] * rg["n"]
    if gain_ok and risk_ok:
        return _record(hid, REFINE, WITHIN_REFINE_BOUNDS, on_expiry, failed,
                       measures)
    reason = REGRESSION_FAILED if not regression_ok else TRANSFER_FAILED
    return _record(hid, REJECT, reason, on_expiry, failed, measures)


def admit(store, request):
    """Return an admission record. Does not raise; bad input -> config_error.

    Only outcome commit writes to the store, and it writes exactly one
    lesson built from plain-str copies of the hypothesis.
    """
    try:
        return _admit(store, request)
    except Exception:
        return _record(None, CONFIG_ERROR, CONFIG_ERROR)
