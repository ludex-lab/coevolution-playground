"""Unused contradiction: a flag is not a repair. Stdlib-only method sketch.

An episode is a trace of steps. Each step is one of:

    {"kind": "belief", "id", "state"}      the agent holds a belief about a state
    {"kind": "act",    "id", "state"}      the agent acts, writing a state
    {"kind": "evidence", "id", "contradicts"}
                                           an observation; "contradicts" is a
                                           DECLARED FIXTURE LABEL: the id of an
                                           earlier belief or act, or None
    {"kind": "flag",   "id", "target"}     something flags a deviation in an
                                           earlier belief or act
    {"kind": "repair", "id", "state"}      a response that removes whatever
                                           currently holds that state

The run may close as success only when every labelled contradiction was
consumed: after the evidence, a repair removed the contradicted belief or
act while it still held its state, and no later belief or act asserted
that state again (a re-assertion after the repair is a relapse and fails
with reasserted_after_repair). A flag alone never counts. A repair of
another state, a repair before the evidence, or a repair after the
contradicted holder was already replaced does not count either.

Contradiction labels are never inferred. This sketch has no contradiction
detector (that would need an NLI-style oracle) and no origin or phase
localisation; both are reported as on_unmeasured. An evidence step without
a "contradicts" label leaves the episode on_unmeasured, and an episode that
does not declare its labels as fixtures is a config_error.

A wait carries a timeout and a declared on_expiry in (HOLD, ESCALATE,
DENY). A timeout without on_expiry is a config_error. An expired wait
returns the declared on_expiry and never success.

Inputs are checked by exact type (type(x) is str / dict / list / int /
bool), never by isinstance, so subclasses that pretend to equal valid
values are a config_error. Record values are None, module constants,
exact-str ids from the input, or tuples of those. decide() catches any
internal error and returns config_error; it does not raise.
"""

SUCCESS = "success"
FAIL = "fail"
ON_UNMEASURED = "on_unmeasured"
CONFIG_ERROR = "config_error"
HOLD = "HOLD"
ESCALATE = "ESCALATE"
DENY = "DENY"
ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY)
VERDICTS = (SUCCESS, FAIL, ON_UNMEASURED, CONFIG_ERROR) + ON_EXPIRY_VALUES

# reasons
CONSUMED = "contradictions_consumed"
TASK_NOT_DONE = "task_not_done"
UNUSED_CONTRADICTION = "unused_contradiction"
FLAG_WITHOUT_REPAIR = "flag_without_repair"
REASSERTED_AFTER_REPAIR = "reasserted_after_repair"
UNLABELED_EVIDENCE = "unlabeled_evidence"
EXPIRED = "expired"
REASONS = (CONSUMED, TASK_NOT_DONE, UNUSED_CONTRADICTION, REASSERTED_AFTER_REPAIR,
           FLAG_WITHOUT_REPAIR, UNLABELED_EVIDENCE, EXPIRED, CONFIG_ERROR)

# policies: the gate under study and two baselines it is measured against
CONSUME = "consume_contradiction"
SYMPTOM_ONLY = "symptom_only"          # closes on the task flag alone
FLAG_AS_REPAIR = "flag_as_repair"      # counts a later flag as a response
POLICIES = (CONSUME, SYMPTOM_ONLY, FLAG_AS_REPAIR)
INVALID_POLICY = "invalid_policy"

DECLARED_FIXTURE = "declared_fixture"
LABEL_MODES = (DECLARED_FIXTURE,)

# axes this sketch does not measure
CONTRADICTION_DETECTION = "contradiction_detection"
ORIGIN_LOCALISATION = "origin_localisation"
PHASE_LOCALISATION = "phase_localisation"
UNMEASURED_AXES = (CONTRADICTION_DETECTION, ORIGIN_LOCALISATION, PHASE_LOCALISATION)

BELIEF = "belief"
ACT = "act"
EVIDENCE = "evidence"
FLAG = "flag"
REPAIR = "repair"
KINDS = (BELIEF, ACT, EVIDENCE, FLAG, REPAIR)
STEP_REQUIRED = {
    BELIEF: ("kind", "id", "state"),
    ACT: ("kind", "id", "state"),
    EVIDENCE: ("kind", "id"),
    FLAG: ("kind", "id", "target"),
    REPAIR: ("kind", "id", "state"),
}
STEP_OPTIONAL = {BELIEF: (), ACT: (), EVIDENCE: ("contradicts",), FLAG: (), REPAIR: ()}

REQUIRED_FIELDS = ("episode_id", "contradiction_labels", "task_done", "steps")
OPTIONAL_FIELDS = ("wait",)
WAIT_FIELDS = ("timeout_s", "on_expiry", "expired")

RECORD_FIELDS = ("episode_id", "policy", "verdict", "reason", "prior_verdict",
                 "prior_reason", "on_expiry", "unresolved", "ineffective_repairs",
                 "unlabeled", "unmeasured_axes")


def _is_str(value):
    return type(value) is str


def _is_dict(value):
    return type(value) is dict


def _canonical(value, choices):
    """The module's own constant equal to an exact-str value, else None."""
    if not _is_str(value):
        return None
    for choice in choices:
        if value == choice:
            return choice
    return None


def _check_keys(mapping, required, optional, where):
    for key in mapping:
        if not _is_str(key):
            return "%s field names must be strings" % where
        if _canonical(key, required + optional) is None:
            return "unknown %s field" % where
    for key in required:
        if key not in mapping:
            return "missing %s field" % where
    return None


def _validate_wait(wait):
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
        return "wait.on_expiry must be one of HOLD, ESCALATE, DENY"
    if type(wait.get("expired")) is not bool:
        return "wait.expired must be a boolean"
    return None


def validate(episode):
    """None when the episode is well formed, else a short error string.

    Key types are checked before any lookup, so it does not raise.
    """
    if not _is_dict(episode):
        return "episode is not a mapping"
    err = _check_keys(episode, REQUIRED_FIELDS, OPTIONAL_FIELDS, "episode")
    if err:
        return err
    if not _is_str(episode["episode_id"]) or not episode["episode_id"]:
        return "episode_id must be a non-empty string"
    if _canonical(episode["contradiction_labels"], LABEL_MODES) is None:
        return "contradiction_labels must be declared_fixture (labels are never inferred)"
    if type(episode["task_done"]) is not bool:
        return "task_done must be a boolean"
    if "wait" in episode:
        err = _validate_wait(episode["wait"])
        if err:
            return err
    steps = episode["steps"]
    if type(steps) is not list or not steps:
        return "steps must be a non-empty list"
    seen_ids = set()
    holders = set()   # ids of beliefs and acts seen so far
    states = set()    # states asserted so far
    for step in steps:
        if not _is_dict(step):
            return "step is not a mapping"
        for key in step:
            if not _is_str(key):
                return "step field names must be strings"
        kind = _canonical(step.get("kind"), KINDS)
        if kind is None:
            return "step kind must be one of %s" % (KINDS,)
        err = _check_keys(step, STEP_REQUIRED[kind], STEP_OPTIONAL[kind], "step")
        if err:
            return err
        sid = step["id"]
        if not _is_str(sid) or not sid:
            return "step id must be a non-empty string"
        if sid in seen_ids:
            return "duplicate step id"
        seen_ids.add(sid)
        if kind in (BELIEF, ACT):
            if not _is_str(step["state"]) or not step["state"]:
                return "state must be a non-empty string"
            holders.add(sid)
            states.add(step["state"])
        elif kind == EVIDENCE:
            if "contradicts" in step:
                label = step["contradicts"]
                if label is not None:
                    if not _is_str(label):
                        return "contradicts must be None or a step id"
                    if label not in holders:
                        return "contradicts must name an earlier belief or act"
        elif kind == FLAG:
            if not _is_str(step["target"]) or step["target"] not in holders:
                return "flag target must name an earlier belief or act"
        else:
            if not _is_str(step["state"]) or step["state"] not in states:
                return "repair state must name a state asserted earlier"
    return None


def _analyse(episode):
    """Trace facts of a validated episode (pure; callers validate first).

    Returns (pairs, unlabeled, ineffective) where pairs is a tuple of
    (evidence_id, holder_id, status) and status is "repaired",
    "reasserted" (removed, then the same state asserted again by a later
    belief or act), "flagged" (flag after the evidence, no removing
    repair) or "unused".
    """
    holder = {}      # state -> id of the belief/act holding it now
    state_of = {}    # belief/act id -> the state it asserted
    asserts = []     # (index, state) for every belief/act
    contradictions = []  # (index, evidence_id, holder_id)
    flags = []       # (index, target)
    removals = []    # (index, repair_id, removed_holder_id or None)
    unlabeled = []
    for index, step in enumerate(episode["steps"]):
        kind = step["kind"]
        if kind in (BELIEF, ACT):
            holder[step["state"]] = step["id"]
            state_of[step["id"]] = step["state"]
            asserts.append((index, step["state"]))
        elif kind == EVIDENCE:
            if "contradicts" not in step:
                unlabeled.append(step["id"])
            elif step["contradicts"] is not None:
                contradictions.append((index, step["id"], step["contradicts"]))
        elif kind == FLAG:
            flags.append((index, step["target"]))
        else:
            removals.append((index, step["id"], holder.pop(step["state"], None)))
    pairs = []
    effective = set()
    for e_index, e_id, h_id in contradictions:
        hits = [(r_index, r_id) for r_index, r_id, removed in removals
                if r_index > e_index and removed == h_id]
        if hits:
            effective.update(r_id for _, r_id in hits)
            first = min(r_index for r_index, _ in hits)
            if any(a_index > first and a_state == state_of[h_id] for a_index, a_state in asserts):
                status = "reasserted"
            else:
                status = "repaired"
        elif any(f_index > e_index and target == h_id for f_index, target in flags):
            status = "flagged"
        else:
            status = "unused"
        pairs.append((e_id, h_id, status))
    ineffective = tuple(sorted(r_id for _, r_id, _ in removals if r_id not in effective))
    return tuple(pairs), tuple(unlabeled), ineffective


def _judge(episode, policy):
    pairs, unlabeled, ineffective = _analyse(episode)
    unresolved = []
    for e_id, h_id, status in pairs:
        if status == "repaired":
            continue
        if status == "reasserted":
            unresolved.append((e_id, h_id, REASSERTED_AFTER_REPAIR))
        elif status == "flagged":
            if policy == FLAG_AS_REPAIR:
                continue
            unresolved.append((e_id, h_id, FLAG_WITHOUT_REPAIR))
        else:
            unresolved.append((e_id, h_id, UNUSED_CONTRADICTION))
    unresolved = tuple(sorted(unresolved))
    if not episode["task_done"]:
        verdict, reason = FAIL, TASK_NOT_DONE
    elif policy == SYMPTOM_ONLY:
        verdict, reason = SUCCESS, CONSUMED
    elif any(r == UNUSED_CONTRADICTION for _, _, r in unresolved):
        verdict, reason = FAIL, UNUSED_CONTRADICTION
    elif any(r == REASSERTED_AFTER_REPAIR for _, _, r in unresolved):
        verdict, reason = FAIL, REASSERTED_AFTER_REPAIR
    elif unresolved:
        verdict, reason = FAIL, FLAG_WITHOUT_REPAIR
    elif unlabeled:
        verdict, reason = ON_UNMEASURED, UNLABELED_EVIDENCE
    else:
        verdict, reason = SUCCESS, CONSUMED
    return verdict, reason, unresolved, ineffective, unlabeled


def _record(episode_id, policy, verdict, reason, prior_verdict=None, prior_reason=None,
            on_expiry=None, unresolved=(), ineffective=(), unlabeled=()):
    return {
        "episode_id": episode_id,
        "policy": policy,
        "verdict": verdict,
        "reason": reason,
        "prior_verdict": prior_verdict,
        "prior_reason": prior_reason,
        "on_expiry": on_expiry,
        "unresolved": unresolved,
        "ineffective_repairs": ineffective,
        "unlabeled": unlabeled,
        "unmeasured_axes": UNMEASURED_AXES,
    }


def _decide(episode, policy):
    pol = _canonical(policy, POLICIES)
    if pol is None:
        return _record(None, INVALID_POLICY, CONFIG_ERROR, CONFIG_ERROR)
    if validate(episode) is not None:
        return _record(None, pol, CONFIG_ERROR, CONFIG_ERROR)
    eid = episode["episode_id"]
    verdict, reason, unresolved, ineffective, unlabeled = _judge(episode, pol)
    wait = episode.get("wait")
    if wait is not None:
        action = _canonical(wait["on_expiry"], ON_EXPIRY_VALUES)
        if wait["expired"]:
            return _record(eid, pol, action, EXPIRED, verdict, reason, action,
                           unresolved, ineffective, unlabeled)
        return _record(eid, pol, verdict, reason, None, None, action,
                       unresolved, ineffective, unlabeled)
    return _record(eid, pol, verdict, reason, None, None, None,
                   unresolved, ineffective, unlabeled)


def decide(episode, policy=CONSUME):
    """Close an episode under a policy. Never raises; failures are config_error."""
    try:
        return _decide(episode, policy)
    except Exception:
        pol = _canonical(policy, POLICIES)
        return _record(None, INVALID_POLICY if pol is None else pol, CONFIG_ERROR, CONFIG_ERROR)


def detect_contradiction(first, second):
    """General contradiction detection is not measured here (no NLI oracle)."""
    return {"verdict": ON_UNMEASURED, "axis": CONTRADICTION_DETECTION}


def localise_origin(episode):
    """Origin and phase localisation of an error are not measured here."""
    return {"verdict": ON_UNMEASURED, "axis": (ORIGIN_LOCALISATION, PHASE_LOCALISATION)}


def summarise(episodes, policy=CONSUME):
    """Count verdicts over an exact list of episodes; pure, no I/O, never raises.

    Anything other than an exact list counts as one config_error.
    """
    counts = dict((v, 0) for v in VERDICTS)
    if type(episodes) is not list:
        counts[CONFIG_ERROR] += 1
        return counts
    for episode in episodes:
        counts[decide(episode, policy)["verdict"]] += 1
    return counts
