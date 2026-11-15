"""Role-contract admission sketch: check at the shared-context boundary.

Stdlib only. A message enters the shared context only when every speech-act
token it carries is in its role's contract. A rejected message may be revised
by an external party; the revision is held until a fresh re-check passes.
Timeout, a failed re-check, or a missing re-check never admits.
No scoring model or message rewriting is implemented here; see README.
"""
from dataclasses import dataclass
from enum import Enum


class Verdict(Enum):
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    HELD = "HELD"


def _tokens(values, label):
    if isinstance(values, str):
        raise ValueError(label + " must be a collection of tokens, not a string")
    items = tuple(values)
    if not items:
        raise ValueError(label + " must be non-empty")
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(label + " tokens must be non-empty strings")
    return items


@dataclass(frozen=True)
class RoleContract:
    role: str
    speech_acts: frozenset

    def __post_init__(self):
        if not isinstance(self.role, str) or not self.role.strip():
            raise ValueError("role must be a non-empty string")
        object.__setattr__(self, "speech_acts",
                           frozenset(_tokens(self.speech_acts, "speech_acts")))


@dataclass(frozen=True)
class ContractTable:
    contracts: tuple

    def __post_init__(self):
        contracts = tuple(self.contracts)
        if not contracts:
            raise ValueError("contract table must be non-empty")
        roles = [c.role for c in contracts if isinstance(c, RoleContract)]
        if len(roles) != len(contracts):
            raise ValueError("contract table entries must be RoleContract")
        if len(set(roles)) != len(roles):
            raise ValueError("duplicate role in contract table")
        object.__setattr__(self, "contracts", contracts)

    def lookup(self, role):
        for contract in self.contracts:
            if contract.role == role:
                return contract
        return None


@dataclass(frozen=True)
class Message:
    message_id: str
    role: str
    acts: tuple
    revision: int = 0

    def __post_init__(self):
        for name in ("message_id", "role"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(name + " must be a non-empty string")
        object.__setattr__(self, "acts", _tokens(self.acts, "acts"))
        if (not isinstance(self.revision, int) or isinstance(self.revision, bool)
                or self.revision < 0):
            raise ValueError("revision must be a non-negative int")


@dataclass(frozen=True)
class Check:
    """Pure contract check; carries no admission by itself."""
    role_known: bool
    out_of_role: tuple

    @property
    def in_role(self):
        return self.role_known and not self.out_of_role


@dataclass(frozen=True)
class Decision:
    message_id: str
    revision: int
    verdict: Verdict
    reason: str
    out_of_role: tuple = ()
    at: int = 0


def check_acts(table, role, acts):
    if not isinstance(table, ContractTable):
        raise ValueError("table must be a ContractTable")
    acts = _tokens(acts, "acts")
    contract = table.lookup(role)
    if contract is None:
        return Check(False, tuple(sorted(set(acts))))
    return Check(True, tuple(sorted({a for a in acts if a not in contract.speech_acts})))


class SharedContext:
    """In-memory shared conversation log; receives ADMITTED messages only."""

    def __init__(self):
        self._entries = []

    @property
    def entries(self):
        return tuple(self._entries)

    def ids(self):
        return tuple((m.message_id, m.revision) for m in self._entries)


@dataclass(frozen=True)
class _Pending:
    original: Message
    deadline: int
    revisions_left: int
    revised: object = None


class AdmissionController:
    """Admission point in front of SharedContext.

    propose(): first check of an original message.
    revise(): record an externally supplied revision; does NOT admit.
    recheck(): re-check the recorded revision; the only path to admit it.
    status(): HELD while a rejected message awaits a passing re-check.
    """

    def __init__(self, table, recheck_window=2, max_revisions=1):
        if not isinstance(table, ContractTable):
            raise ValueError("table must be a ContractTable")
        for name, value, low in (("recheck_window", recheck_window, 0),
                                 ("max_revisions", max_revisions, 1)):
            if not isinstance(value, int) or isinstance(value, bool) or value < low:
                raise ValueError(name + " must be an int >= " + str(low))
        self.table = table
        self.recheck_window = recheck_window
        self.max_revisions = max_revisions
        self.context = SharedContext()
        self._pending = {}
        self._final = {}
        self._decisions = []

    @property
    def decisions(self):
        return tuple(self._decisions)

    def _record(self, decision, message=None):
        self._decisions.append(decision)
        if decision.verdict is Verdict.ADMITTED:
            if message is None or not check_acts(self.table, message.role, message.acts).in_role:
                raise RuntimeError("admission invariant broken")
            self.context._entries.append(message)
        return decision

    def _finish(self, message_id, decision, message=None):
        self._pending.pop(message_id, None)
        self._final[message_id] = decision
        return self._record(decision, message)

    def propose(self, message, now=0, check_timed_out=False):
        if not isinstance(message, Message):
            raise ValueError("message must be a Message")
        if message.revision != 0:
            raise ValueError("revisions go through revise() and recheck()")
        _time(now)
        key = message.message_id
        if key in self._pending or key in self._final:
            raise ValueError("duplicate message_id")
        if check_timed_out:
            return self._finish(key, Decision(key, 0, Verdict.HELD, "check-timeout", (), now))
        result = check_acts(self.table, message.role, message.acts)
        if not result.role_known:
            return self._finish(key, Decision(key, 0, Verdict.REJECTED, "unknown-role",
                                              result.out_of_role, now))
        if result.in_role:
            return self._finish(key, Decision(key, 0, Verdict.ADMITTED, "in-role", (), now),
                                message)
        self._pending[key] = _Pending(message, now + self.recheck_window, self.max_revisions)
        return self._record(Decision(key, 0, Verdict.REJECTED, "out-of-role",
                                     result.out_of_role, now))

    def revise(self, revised):
        if not isinstance(revised, Message):
            raise ValueError("revised must be a Message")
        pending = self._pending.get(revised.message_id)
        if pending is None:
            raise ValueError("no rejected message awaiting revision")
        if pending.revised is not None:
            raise ValueError("revision already awaiting re-check")
        if revised.role != pending.original.role:
            raise ValueError("revision must keep the original role")
        used = self.max_revisions - pending.revisions_left
        if revised.revision != used + 1:
            raise ValueError("revision number must increase by one")
        self._pending[revised.message_id] = _Pending(pending.original, pending.deadline,
                                                     pending.revisions_left, revised)

    def recheck(self, message_id, now, check_timed_out=False):
        _time(now)
        pending = self._pending.get(message_id)
        if pending is None or pending.revised is None:
            raise ValueError("no recorded revision awaiting re-check")
        revised = pending.revised
        if check_timed_out or now > pending.deadline:
            return self._finish(message_id, Decision(message_id, revised.revision, Verdict.HELD,
                                                     "recheck-timeout", (), now))
        result = check_acts(self.table, revised.role, revised.acts)
        if result.in_role:
            return self._finish(message_id, Decision(message_id, revised.revision,
                                                     Verdict.ADMITTED, "recheck-in-role", (), now),
                                revised)
        left = pending.revisions_left - 1
        decision = Decision(message_id, revised.revision, Verdict.REJECTED, "failed-recheck",
                            result.out_of_role, now)
        if left <= 0:
            return self._finish(message_id, decision)
        self._pending[message_id] = _Pending(pending.original, pending.deadline, left)
        return self._record(decision)

    def status(self, message_id, now):
        _time(now)
        if message_id in self._final:
            return self._final[message_id].verdict
        pending = self._pending.get(message_id)
        if pending is None:
            raise ValueError("unknown message_id")
        return Verdict.HELD

    def expire(self, now):
        _time(now)
        expired = []
        for key in sorted(self._pending):
            pending = self._pending[key]
            if now > pending.deadline:
                revision = pending.revised.revision if pending.revised else 0
                reason = "missing-recheck-timeout" if pending.revised else "no-revision-timeout"
                expired.append(self._finish(key, Decision(key, revision, Verdict.HELD,
                                                          reason, (), now)))
        return tuple(expired)


def _time(now):
    if not isinstance(now, int) or isinstance(now, bool) or now < 0:
        raise ValueError("now must be a non-negative int tick")
