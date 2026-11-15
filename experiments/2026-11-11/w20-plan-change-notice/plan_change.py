"""w20-plan-change-notice: acknowledging a change is not acting on it.

Clean-room Python 3 stdlib method sketch of the split between notice
receipt and consequential action described in arXiv 2611.10011. Not a
reproduction: no language model, no simulator from the paper, synthetic
deterministic worlds only.

Four records:

* ``Change``: the authoritative objective history. Version ``v`` of
  objective ``objective_id`` takes effect at ``issued_at``; versions are
  strictly increasing and start at 1.
* ``Plan``: the agent's local plan, derived from one objective version.
  Step ``i`` of the plan is the target ``targets[i]`` of that version.
* ``Notice``: a message in the agent's inbox saying that a version exists,
  delivered at ``arrives_at``. Inbox state goes ``pending`` -> ``acked``.
* ``Action``: one consequential step the agent committed, with the plan
  version it used.

Two policies run on the same world:

* ``baseline``: acks every delivered notice, then executes the next step of
  its cached plan.
* ``notice_first``: before any consequential step it processes pending
  notices, then compares its plan's version with the authoritative version.
  Equal: act. Different and a processed notice for the authoritative version
  exists: replan from the authoritative record, then act. Different and no
  such notice yet: wait, and when the declared wait runs out resolve to the
  declared ``on_expiry``. It never acts on a stale plan.

Silence doctrine (from merged #78): a pending (unread) notice is never
used; "no notice" is never read as "nothing changed, carry on"; a wait path
must declare ``on_expiry`` in {deny, safe_fallback, escalate, hold}; a
missing or unknown value is ``config_error``. ``safe_fallback`` records a
non-consequential fallback step and stops.

``detect_obsolete`` compares every consequential action with the
authoritative objective at the action's time. ``summary`` reports only
acks, completed steps and status, and is shown to be the same for both
policies on the cases where the detector tells them apart.

All records are frozen dataclasses checked by exact type, and every field
is read once into locals before use; anything malformed is config_error.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

DENY = "deny"
SAFE_FALLBACK = "safe_fallback"
ESCALATE = "escalate"
HOLD = "hold"
ON_EXPIRY = (DENY, SAFE_FALLBACK, ESCALATE, HOLD)

# Run statuses.
DONE = "done"
INCOMPLETE = "incomplete"
CONFIG_ERROR = "config_error"
STATUS_ON_EXPIRY = {DENY: "denied", SAFE_FALLBACK: "fallback", ESCALATE: "escalated", HOLD: "held"}

# Action kinds.
CONSEQUENTIAL = "consequential"
WAIT = "wait"
FALLBACK_STEP = "fallback_step"

# Notice classifications.
VALID = "valid_notice"
DUPLICATE = "duplicate"
STALE = "stale_version"
FOREIGN = "foreign_objective"
AHEAD = "ahead_of_authority"
MISMATCH = "content_mismatch"

# Detector findings.
OBSOLETE_AFTER_ACK = "obsolete_after_ack"
OBSOLETE_UNINFORMED = "obsolete_uninformed"

BASELINE = "baseline"
NOTICE_FIRST = "notice_first"


@dataclass(frozen=True)
class Change:
    version: int
    targets: Tuple[str, ...]
    issued_at: int


@dataclass(frozen=True)
class Notice:
    notice_id: str
    objective_id: str
    version: int
    targets: Tuple[str, ...]
    arrives_at: int


@dataclass(frozen=True)
class World:
    objective_id: str
    changes: Tuple[Change, ...]
    notices: Tuple[Notice, ...]
    turns: Tuple[int, ...]


@dataclass(frozen=True)
class GuardConfig:
    wait_turns: int
    on_expiry: Optional[str] = None


@dataclass(frozen=True)
class Plan:
    objective_id: str
    version: int
    targets: Tuple[str, ...]


@dataclass(frozen=True)
class Action:
    at: int
    kind: str
    index: int
    plan_version: int
    target: str


@dataclass(frozen=True)
class Ack:
    at: int
    notice_id: str
    version: int
    classification: str


@dataclass(frozen=True)
class Trace:
    policy: str
    status: str
    actions: Tuple[Action, ...]
    acks: Tuple[Ack, ...]
    errors: Tuple[str, ...] = ()


def _int(v):
    return type(v) is int


def _targets(t):
    return type(t) is tuple and len(t) > 0 and all(type(x) is str and x != "" for x in t)


def _id(s):
    return type(s) is str and s != ""


# --------------------------------------------------------------------------
# Validation and snapshots.

def check_world(world):
    """(errors, snapshot). The snapshot is plain tuples built from fields
    read once; errors are strings. Exact types only."""
    if type(world) is not World:
        return ("not_a_world",), None
    oid, changes, notices, turns = world.objective_id, world.changes, world.notices, world.turns
    errs = []
    if not _id(oid):
        errs.append("objective_id")
    hist = []
    if type(changes) is not tuple or not changes:
        errs.append("changes")
    else:
        for c in changes:
            if type(c) is not Change:
                errs.append("change_type")
                continue
            v, t, at = c.version, c.targets, c.issued_at
            if not (_int(v) and _int(at) and _targets(t)):
                errs.append("change_fields")
                continue
            hist.append((v, t, at))
        if not errs:
            for i, (v, t, at) in enumerate(hist):
                if i == 0 and v != 1:
                    errs.append("first_version")
                if i and not (v > hist[i - 1][0] and at > hist[i - 1][2]):
                    errs.append("history_not_monotonic")
            if len({len(t) for _, t, _ in hist}) != 1:
                errs.append("plan_length_changes")
    nots = []
    if type(notices) is not tuple:
        errs.append("notices")
    else:
        for n in notices:
            if type(n) is not Notice:
                errs.append("notice_type")
                continue
            nid, noid, v, t, at = n.notice_id, n.objective_id, n.version, n.targets, n.arrives_at
            if not (_id(nid) and _id(noid) and _int(v) and v >= 1 and _int(at) and _targets(t)):
                errs.append("notice_fields")
                continue
            nots.append((nid, noid, v, t, at))
    if type(turns) is not tuple or not turns or not all(_int(x) for x in turns):
        errs.append("turns")
    elif any(b <= a for a, b in zip(turns, turns[1:])):
        errs.append("turns_not_increasing")
    if errs:
        return tuple(errs), None
    return (), (oid, tuple(hist), tuple(nots), turns)


def check_config(config):
    """(errors, snapshot) for the guard's wait path."""
    if type(config) is not GuardConfig:
        return ("not_a_config",), None
    w, oe = config.wait_turns, config.on_expiry
    errs = []
    if not (_int(w) and w >= 0):
        errs.append("wait_turns")
    if type(oe) is not str or oe not in ON_EXPIRY:
        errs.append("on_expiry")
    if errs:
        return tuple(errs), None
    return (), (w, ON_EXPIRY[ON_EXPIRY.index(oe)])


def authoritative_at(hist, t):
    """(version, targets) in force at time t, or None before version 1."""
    cur = None
    for v, targets, at in hist:
        if at <= t:
            cur = (v, targets)
    return cur


def derive_plan(oid, version, targets):
    return Plan(oid, version, targets)


# --------------------------------------------------------------------------
# The run.

def _classify(note, oid, known, seen, hist, t):
    nid, noid, v, targets, _ = note
    if nid in seen:
        return DUPLICATE
    if noid != oid:
        return FOREIGN
    if v <= known:
        return STALE
    auth = {hv: ht for hv, ht, hat in hist if hat <= t}
    if v not in auth:
        return AHEAD
    if auth[v] != targets:
        return MISMATCH
    return VALID


def run(world, policy, config=None):
    """Deterministic run of one policy over one world."""
    errs, snap = check_world(world)
    if type(policy) is not str or policy not in (BASELINE, NOTICE_FIRST):
        errs = errs + ("policy",)
    cfg = None
    if policy == NOTICE_FIRST:
        cerrs, cfg = check_config(config)
        errs = errs + cerrs
    if errs:
        return Trace(policy if type(policy) is str else "", CONFIG_ERROR, (), (), tuple(errs))
    oid, hist, nots, turns = snap
    first = authoritative_at(hist, turns[0])
    if first is None:
        return Trace(policy, CONFIG_ERROR, (), (), ("no_objective_at_start",))
    plan = derive_plan(oid, first[0], first[1])
    n = len(plan.targets)
    inbox = sorted(nots, key=lambda x: (x[4], x[0]))
    delivered = 0
    known = plan.version
    seen = set()
    acks, actions = [], []
    i = 0
    waited = 0
    for t in turns:
        if i >= n:
            break
        # Deliver, then process the inbox (both policies ack every notice).
        while delivered < len(inbox) and inbox[delivered][4] <= t:
            note = inbox[delivered]
            delivered += 1
            c = _classify(note, oid, known, seen, hist, t)
            seen.add(note[0])
            if c == VALID:
                known = note[2]
            acks.append(Ack(t, note[0], note[2], c))
        if policy == BASELINE:
            actions.append(Action(t, CONSEQUENTIAL, i, plan.version, plan.targets[i]))
            i += 1
            continue
        auth_v, auth_t = authoritative_at(hist, t)
        if plan.version != auth_v:
            if known == auth_v:
                plan = derive_plan(oid, auth_v, auth_t)
                waited = 0
            else:
                wait_turns, on_expiry = cfg
                if waited < wait_turns:
                    waited += 1
                    actions.append(Action(t, WAIT, i, plan.version, ""))
                    continue
                if on_expiry == SAFE_FALLBACK:
                    actions.append(Action(t, FALLBACK_STEP, i, plan.version, ""))
                return Trace(policy, STATUS_ON_EXPIRY[on_expiry], tuple(actions), tuple(acks))
        actions.append(Action(t, CONSEQUENTIAL, i, plan.version, plan.targets[i]))
        i += 1
    return Trace(policy, DONE if i >= n else INCOMPLETE, tuple(actions), tuple(acks))


# --------------------------------------------------------------------------
# Reading traces.

def summary(trace):
    """What a completion/ack report shows: nothing about objectives."""
    return {
        "notices_acked": len(trace.acks),
        "steps_completed": sum(a.kind == CONSEQUENTIAL for a in trace.actions),
        "status": trace.status,
    }


def detect_obsolete(world, trace):
    """Compare each consequential action with the authoritative objective
    at its time. Returns findings (index_in_trace, at, kind, used_version,
    authoritative_version). ``obsolete_after_ack`` means a valid notice for
    the authoritative version (or a later one) had already been acked when
    the action ran; otherwise the finding is ``obsolete_uninformed``."""
    errs, snap = check_world(world)
    if errs:
        return (("config_error",) + errs,)
    _, hist, _, _ = snap
    out = []
    for k, a in enumerate(trace.actions):
        if a.kind != CONSEQUENTIAL:
            continue
        auth = authoritative_at(hist, a.at)
        if auth is None:
            out.append((k, a.at, OBSOLETE_UNINFORMED, a.plan_version, 0))
            continue
        av, at_targets = auth
        if a.plan_version == av and at_targets[a.index] == a.target:
            continue
        informed = any(x.at <= a.at and x.version >= av and x.classification == VALID
                       for x in trace.acks)
        out.append((k, a.at, OBSOLETE_AFTER_ACK if informed else OBSOLETE_UNINFORMED,
                    a.plan_version, av))
    return tuple(out)


def final_targets(trace):
    return tuple(a.target for a in trace.actions if a.kind == CONSEQUENTIAL)
