"""Fail-closed deputy: a deterministic, stdlib-only method sketch.

A deputy receives a request that carries a permission record and an
evidence-completeness grade, and returns a decision record:

    {"request_id", "policy", "case", "decision", "reason", "prior_reason",
     "on_expiry"}

decision is "dispatch" or "refuse". reason is one of REASONS. The two
refusal reasons ``explicit_deny`` and ``missing_evidence`` stay distinct
so a reader of the output can tell "we were told no" from "we could not
verify yes".

Silence is not consent: under the fail_closed policy an unknown or
unverifiable permission never resolves to dispatch, and an expired wait
always refuses.

Inputs are checked by exact type (``type(x) is str``, ``type(x) is dict``,
``type(x) is int``, ``type(x) is bool``), never by isinstance or by
equality alone, so a subclass that pretends to equal a valid value is a
config_error. Every value written into a record is either None or one of
this module's own constants; caller objects are never echoed back, except
an exact-str request_id, which is read only after the whole request has
passed validation (a config_error record carries request_id None). No field
of an unvalidated request is ever looked up. decide() catches any internal
error and refuses with config_error, so it does not raise on bad input.
"""

DISPATCH = "dispatch"
REFUSE = "refuse"

PERMITTED = "permitted"
EXPLICIT_DENY = "explicit_deny"
MISSING_EVIDENCE = "missing_evidence"
EXPIRED = "expired"
CONFIG_ERROR = "config_error"
REASONS = (PERMITTED, EXPLICIT_DENY, MISSING_EVIDENCE, EXPIRED, CONFIG_ERROR)

FAIL_CLOSED = "fail_closed"
OPTIMISTIC_IF_UNKNOWN = "optimistic_if_unknown"
POLICIES = (FAIL_CLOSED, OPTIMISTIC_IF_UNKNOWN)
# Recorded in place of the caller's value when the policy argument is not
# an exact str naming one of POLICIES.
INVALID_POLICY = "invalid_policy"

PERMISSION_VALUES = ("granted", "denied", "unknown")
EVIDENCE_VALUES = ("complete", "partial", "missing")

REQUIRED_FIELDS = ("request_id", "action", "permission", "evidence")
OPTIONAL_FIELDS = ("wait",)
WAIT_FIELDS = ("timeout_s", "on_expiry", "expired")
# The only declared expiry outcome accepted. An expiry that would resolve
# to dispatch is a config_error: unknown never becomes dispatch.
ON_EXPIRY_VALUES = (REFUSE,)

RECORD_FIELDS = ("request_id", "policy", "case", "decision", "reason",
                 "prior_reason", "on_expiry")


def _is_str(value):
    """Exact str only; a str subclass is rejected."""
    return type(value) is str


def _is_dict(value):
    """Exact dict only; a dict subclass is rejected."""
    return type(value) is dict


def _canonical(value, choices):
    """Return the module's own constant equal to value, else None.

    value must be an exact str; the comparison then runs on plain str
    objects only, so no caller-defined __eq__ or __hash__ is ever called.
    """
    if not _is_str(value):
        return None
    for choice in choices:
        if value == choice:
            return choice
    return None


def validate(request):
    """Return None when the request is well formed, else a short error string."""
    if not _is_dict(request):
        return "request is not a mapping"
    for key in request:
        if not _is_str(key):
            return "field names must be strings"
        if _canonical(key, REQUIRED_FIELDS + OPTIONAL_FIELDS) is None:
            return "unknown field"
    for key in REQUIRED_FIELDS:
        if key not in request:
            return "missing field: %s" % (key,)
    if not _is_str(request["request_id"]) or not request["request_id"]:
        return "request_id must be a non-empty string"
    if not _is_str(request["action"]) or not request["action"]:
        return "action must be a non-empty string"
    if _canonical(request["permission"], PERMISSION_VALUES) is None:
        return "permission must be one of %s" % (PERMISSION_VALUES,)
    if _canonical(request["evidence"], EVIDENCE_VALUES) is None:
        return "evidence must be one of %s" % (EVIDENCE_VALUES,)
    if "wait" in request:
        wait = request["wait"]
        if not _is_dict(wait):
            return "wait is not a mapping"
        for key in wait:
            if not _is_str(key):
                return "wait field names must be strings"
            if _canonical(key, WAIT_FIELDS) is None:
                return "unknown wait field"
        timeout = wait.get("timeout_s")
        if type(timeout) is not int or timeout <= 0:
            return "wait.timeout_s must be a positive integer"
        if "on_expiry" not in wait:
            return "wait declares a timeout without on_expiry"
        if _canonical(wait["on_expiry"], ON_EXPIRY_VALUES) is None:
            return "wait.on_expiry must be one of %s" % (ON_EXPIRY_VALUES,)
        if "expired" in wait and type(wait["expired"]) is not bool:
            return "wait.expired must be a boolean"
    return None


def classify(request):
    """Map a validated request to one of the three cases.

    granted + complete evidence          -> permitted
    denied (any evidence grade)          -> explicit_deny
    unknown, or granted but not complete -> missing_evidence
    """
    permission = _canonical(request["permission"], PERMISSION_VALUES)
    evidence = _canonical(request["evidence"], EVIDENCE_VALUES)
    if permission == "denied":
        return EXPLICIT_DENY
    if permission == "granted" and evidence == "complete":
        return PERMITTED
    return MISSING_EVIDENCE


def _record(request_id, policy, case, decision, reason,
            prior_reason=None, on_expiry=None):
    return {
        "request_id": request_id,
        "policy": policy,
        "case": case,
        "decision": decision,
        "reason": reason,
        "prior_reason": prior_reason,
        "on_expiry": on_expiry,
    }


def _decide(request, policy):
    # No field of the request is read before validate() passes. A lookup on
    # an unvalidated mapping can run caller code (a non-str key whose hash
    # collides with a field name has its __eq__ called, and a dict subclass
    # can override get or __getitem__), and that code could rewrite the
    # request before it is checked. rid stays None on every config_error.
    rid = None
    canon = _canonical(policy, POLICIES)
    if canon is None:
        return _record(rid, INVALID_POLICY, None, REFUSE, CONFIG_ERROR)
    error = validate(request)
    if error is not None:
        return _record(rid, canon, None, REFUSE, CONFIG_ERROR)
    rid = request["request_id"]
    case = classify(request)
    wait = request.get("wait")
    on_expiry = REFUSE if wait is not None else None
    if wait is not None and wait.get("expired", False) is True:
        # The wait ran out before an answer came. The only declared outcome
        # is refuse, and the module's own constant is returned, never the
        # caller's object. The case's own reason stays visible.
        return _record(rid, canon, case, REFUSE, EXPIRED, case, on_expiry)
    if case == PERMITTED:
        return _record(rid, canon, case, DISPATCH, PERMITTED, None, on_expiry)
    if case == EXPLICIT_DENY:
        return _record(rid, canon, case, REFUSE, EXPLICIT_DENY, None, on_expiry)
    # case == MISSING_EVIDENCE
    if canon == OPTIMISTIC_IF_UNKNOWN:
        # Baseline under study: treats silence as consent.
        return _record(rid, canon, case, DISPATCH, MISSING_EVIDENCE, None, on_expiry)
    return _record(rid, canon, case, REFUSE, MISSING_EVIDENCE, None, on_expiry)


def decide(request, policy=FAIL_CLOSED):
    """Return a decision record. Does not raise on bad input; refuses instead.

    Any exception inside the decision path fails closed: refuse with
    config_error, no request_id echoed, and the policy recorded only in
    canonical form (or INVALID_POLICY).
    """
    try:
        return _decide(request, policy)
    except Exception:
        return _record(None, _safe_policy(policy), None, REFUSE, CONFIG_ERROR)


def _safe_policy(policy):
    """Canonical policy constant, or INVALID_POLICY; never raises."""
    try:
        canon = _canonical(policy, POLICIES)
    except Exception:
        canon = None
    return INVALID_POLICY if canon is None else canon
