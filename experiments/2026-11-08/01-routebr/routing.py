"""Original offline toy: supplied proposal -> committed primary -> closed gate.

A dispatch is a typed return record, never a tool invocation. The explicitly
unsafe fallback function is a comparison foil, not part of the controller.
"""
from dataclasses import dataclass
from enum import Enum


def _identifier(value):
    return (type(value) is str and 0 < len(value) <= 80
            and all(c.isascii() and (c.isalnum() or c in "_.:-+") for c in value))


def _require(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class Choice:
    action: str
    object_id: str | None

    def __post_init__(self):
        _require(_identifier(self.action), "invalid action identifier")
        _require(self.object_id is None or _identifier(self.object_id), "invalid object identifier")


@dataclass(frozen=True)
class Action:
    identifier: str
    object_types: tuple[str, ...]

    def __post_init__(self):
        _require(_identifier(self.identifier), "invalid action")
        _require(type(self.object_types) is tuple and all(_identifier(x) for x in self.object_types),
                 "object contract must be an immutable tuple")
        _require(len(set(self.object_types)) == len(self.object_types), "duplicate object type")


@dataclass(frozen=True)
class RegisteredObject:
    identifier: str
    kind: str

    def __post_init__(self):
        _require(_identifier(self.identifier) and _identifier(self.kind), "invalid registry entry")


@dataclass(frozen=True)
class Rule:
    identifier: str
    action: str
    required_flags: tuple[str, ...]

    def __post_init__(self):
        _require(_identifier(self.identifier) and _identifier(self.action), "invalid rule")
        _require(type(self.required_flags) is tuple and all(_identifier(x) for x in self.required_flags),
                 "flags must be immutable identifiers")
        _require(len(set(self.required_flags)) == len(self.required_flags), "duplicate flag")


@dataclass(frozen=True)
class Snapshot:
    catalog_version: str
    registry_version: str
    rules_version: str
    state_version: str
    frozen_time: str
    actions: tuple[Action, ...]
    objects: tuple[RegisteredObject, ...]
    rules: tuple[Rule, ...]

    def __post_init__(self):
        _require(all(_identifier(x) for x in self.versions + (self.frozen_time,)), "invalid version/time")
        for entries, kind in ((self.actions, Action), (self.objects, RegisteredObject), (self.rules, Rule)):
            _require(type(entries) is tuple and all(type(x) is kind for x in entries), "mutable/invalid asset")
            ids = tuple(x.identifier for x in entries)
            _require(len(set(ids)) == len(ids), "duplicate asset identifier")
        _require(bool(self.actions) and bool(self.rules), "empty catalog/rules")
        action_ids = {x.identifier for x in self.actions}
        _require(all(r.action in action_ids for r in self.rules), "rule references unknown action")
        _require(len({r.action for r in self.rules}) == len(self.rules), "ambiguous action rule")

    @property
    def versions(self):
        return (self.catalog_version, self.registry_version, self.rules_version, self.state_version)


@dataclass(frozen=True)
class State:
    version: str
    frozen_time: str
    flags: tuple[tuple[str, bool], ...]

    def __post_init__(self):
        _require(_identifier(self.version) and _identifier(self.frozen_time), "invalid state version/time")
        _require(type(self.flags) is tuple, "state must be immutable")
        _require(all(type(x) is tuple and len(x) == 2 and _identifier(x[0])
                     and type(x[1]) is bool for x in self.flags), "invalid state flags")
        _require(len({x[0] for x in self.flags}) == len(self.flags), "duplicate state flag")


@dataclass(frozen=True)
class Proposal:
    primary: Choice
    candidates: tuple[Choice, ...]
    versions: tuple[str, ...]

    def __post_init__(self):
        _require(type(self.primary) is Choice, "invalid primary")
        _require(type(self.candidates) is tuple and len(self.candidates) <= 3
                 and all(type(x) is Choice for x in self.candidates), "invalid audit candidates")
        ids = (self.primary.action,) + tuple(x.action for x in self.candidates)
        _require(len(set(ids)) == len(ids), "repeated action in proposal")
        _require(type(self.versions) is tuple and len(self.versions) == 4
                 and all(_identifier(x) for x in self.versions), "invalid asset versions")


class Verdict(str, Enum):
    DISPATCH = "DISPATCH"
    NON_DISPATCH = "NON-DISPATCH"


class Reason(str, Enum):
    CHECKED_PRIMARY = "checked-primary"
    INVALID_INPUT = "invalid-input"
    VERSION_MISMATCH = "version-mismatch"
    UNKNOWN_ACTION = "unknown-action"
    MISSING_RULE = "missing-rule"
    STATE_BLOCK = "state-block"
    OBJECT_REQUIRED = "object-required"
    UNREGISTERED_OBJECT = "unregistered-object"
    OBJECT_TYPE = "incompatible-object-type"
    OBJECT_FORBIDDEN = "object-forbidden"
    UNSAFE_SUBSTITUTION = "unsafe-baseline-substitution"


@dataclass(frozen=True)
class DispatchRecord:
    action: str
    object_id: str | None


@dataclass(frozen=True)
class Outcome:
    verdict: Verdict
    reason: Reason
    committed: Choice | None
    dispatch: DispatchRecord | None
    audit_candidates: tuple[Choice, ...]
    versions: tuple[str, ...]
    rule_id: str | None = None


def route(proposal, snapshot, state):
    """No ranking, repair, retry, side effect, or alternative execution path."""
    if type(proposal) is not Proposal or type(snapshot) is not Snapshot or type(state) is not State:
        return Outcome(Verdict.NON_DISPATCH, Reason.INVALID_INPUT, None, None, (), ())
    primary = proposal.primary  # commitment precedes all admissibility checks

    def terminal(reason, rule_id=None):
        return Outcome(Verdict.NON_DISPATCH, reason, primary, None,
                       proposal.candidates, snapshot.versions, rule_id)

    if (proposal.versions != snapshot.versions or state.version != snapshot.state_version
            or state.frozen_time != snapshot.frozen_time):
        return terminal(Reason.VERSION_MISMATCH)
    action = next((a for a in snapshot.actions if a.identifier == primary.action), None)
    if action is None:
        return terminal(Reason.UNKNOWN_ACTION)
    rule = next((r for r in snapshot.rules if r.action == primary.action), None)
    if rule is None:
        return terminal(Reason.MISSING_RULE)
    flags = dict(state.flags)
    if not all(flags.get(flag) is True for flag in rule.required_flags):
        return terminal(Reason.STATE_BLOCK, rule.identifier)
    if not action.object_types:
        if primary.object_id is not None:
            return terminal(Reason.OBJECT_FORBIDDEN, rule.identifier)
    else:
        if primary.object_id is None:
            return terminal(Reason.OBJECT_REQUIRED, rule.identifier)
        obj = next((o for o in snapshot.objects if o.identifier == primary.object_id), None)
        if obj is None:
            return terminal(Reason.UNREGISTERED_OBJECT, rule.identifier)
        if obj.kind not in action.object_types:
            return terminal(Reason.OBJECT_TYPE, rule.identifier)
    return Outcome(Verdict.DISPATCH, Reason.CHECKED_PRIMARY, primary,
                   DispatchRecord(primary.action, primary.object_id), proposal.candidates,
                   snapshot.versions, rule.identifier)


def unsafe_fallback_baseline(proposal, snapshot, state):
    """Deliberately flawed foil: promote next route while omitting object checks.

    It still requires a known action and matching state rule. Both accepting a
    valid different route and bypassing an invalid object's contract violate
    primary commitment. This is not an upstream baseline reproduction.
    """
    first = route(proposal, snapshot, state)
    if first.verdict is Verdict.DISPATCH or first.reason in (Reason.INVALID_INPUT, Reason.VERSION_MISMATCH):
        return first
    object_failures = {Reason.OBJECT_REQUIRED, Reason.UNREGISTERED_OBJECT,
                       Reason.OBJECT_TYPE, Reason.OBJECT_FORBIDDEN}
    for candidate in proposal.candidates:
        probe = route(Proposal(candidate, (), proposal.versions), snapshot, state)
        if probe.verdict is Verdict.DISPATCH or probe.reason in object_failures:
            return Outcome(Verdict.DISPATCH, Reason.UNSAFE_SUBSTITUTION, proposal.primary,
                           DispatchRecord(candidate.action, candidate.object_id), proposal.candidates,
                           snapshot.versions, probe.rule_id)
    return first
