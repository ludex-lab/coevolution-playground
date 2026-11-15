from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from silence_expiry.actions import EscalationError, validated_fallback
from silence_expiry.policy import ConfigError, OnExpiry, Policy, Rule, TerminalState

_TERMINAL_BLOCK = frozenset(
    {
        TerminalState.DENIED_ON_TIMEOUT,
        TerminalState.HELD,
        TerminalState.EXHAUSTED,
        TerminalState.FELL_BACK,
        TerminalState.APPROVED,
    }
)


class JournalKind(str, Enum):
    ESCALATION_RAISED = "escalation.raised"
    EXPIRED_NO_ANSWER = "expired_no_answer"
    TIER_ADVANCED = "tier.advanced"
    FALLBACK_ON_TIMEOUT = "fallback_on_timeout"
    DENIED_ON_TIMEOUT = "denied_on_timeout"
    HELD_ON_TIMEOUT = "held_on_timeout"
    EXHAUSTED = "escalation.exhausted"
    APPROVED = "approved"


@dataclass
class Journal:
    entries: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, kind: JournalKind, **detail: Any) -> None:
        self.entries.append({"kind": kind.value, **detail})


@dataclass
class Escalation:
    action_id: str
    tool: str
    risk: str
    rule: Rule
    tier_index: int = 0
    tier_started_at: float = 0.0
    terminal: TerminalState | None = None
    safe_fallback: str | None = None


@dataclass
class EscalationEngine:
    policy: Policy
    actions: Mapping[str, Mapping[str, Any]]
    journal: Journal = field(default_factory=Journal)
    _open: dict[str, Escalation] = field(default_factory=dict)

    def propose(self, action_id: str, tool: str, risk: str, now: float) -> Escalation:
        rule = self.policy.rule_for(risk)
        if not rule.requires_approval:
            raise ConfigError(
                f"ungated propose for risk {risk!r}: set requires_approval false only for autopath, not propose()"
            )
        prior = self._open.get(action_id)
        if prior and prior.terminal in _TERMINAL_BLOCK:
            raise EscalationError(f"action_id {action_id!r} already terminal ({prior.terminal.value})")
        fb = validated_fallback(tool, self.actions)
        esc = Escalation(action_id, tool, risk, rule, tier_started_at=now, safe_fallback=fb)
        self._open[action_id] = esc
        self.journal.emit(
            JournalKind.ESCALATION_RAISED,
            action_id=action_id,
            tool=tool,
            tier=self._tier(esc),
            on_expiry=rule.on_expiry.value,
        )
        return esc

    def approve(self, action_id: str) -> Escalation:
        esc = self._open.get(action_id)
        if esc is None or esc.terminal is not None:
            raise EscalationError(f"no open escalation for {action_id!r}")
        if esc.rule.quorum > 1:
            raise EscalationError("quorum>1 approve path not implemented in this Top sketch")
        esc.terminal = TerminalState.APPROVED
        self.journal.emit(JournalKind.APPROVED, action_id=action_id)
        return esc

    def tick(self, now: float) -> list[Escalation]:
        changed: list[Escalation] = []
        for esc in list(self._open.values()):
            if esc.terminal is not None or now < esc.tier_started_at + esc.rule.deadline_s:
                continue
            self.journal.emit(
                JournalKind.EXPIRED_NO_ANSWER,
                action_id=esc.action_id,
                tier=self._tier(esc),
                waited_s=int(now - esc.tier_started_at),
                on_expiry=esc.rule.on_expiry.value,
            )
            self._apply_expiry(esc, now)
            changed.append(esc)
        return changed

    def _tier(self, esc: Escalation) -> str | None:
        if esc.tier_index >= len(esc.rule.ladder):
            return None
        return esc.rule.ladder[esc.tier_index]

    def _apply_expiry(self, esc: Escalation, now: float) -> None:
        expiry = esc.rule.on_expiry
        if expiry is OnExpiry.ESCALATE:
            esc.tier_index += 1
            if self._tier(esc) is None:
                esc.terminal = TerminalState.EXHAUSTED
                self.journal.emit(JournalKind.EXHAUSTED, action_id=esc.action_id)
                return
            esc.tier_started_at = now
            self.journal.emit(JournalKind.TIER_ADVANCED, action_id=esc.action_id, tier=self._tier(esc))
            return
        if expiry is OnExpiry.HOLD:
            esc.terminal = TerminalState.HELD
            self.journal.emit(JournalKind.HELD_ON_TIMEOUT, action_id=esc.action_id)
            return
        if expiry is OnExpiry.SAFE_FALLBACK:
            try:
                fb = validated_fallback(esc.tool, self.actions)
            except ConfigError:
                fb = None
            if not fb:
                esc.terminal = TerminalState.DENIED_ON_TIMEOUT
                self.journal.emit(JournalKind.DENIED_ON_TIMEOUT, action_id=esc.action_id, why="no_fallback")
                return
            esc.safe_fallback = fb
            esc.terminal = TerminalState.FELL_BACK
            self.journal.emit(
                JournalKind.FALLBACK_ON_TIMEOUT,
                action_id=esc.action_id,
                substituted=esc.safe_fallback,
            )
            return
        esc.terminal = TerminalState.DENIED_ON_TIMEOUT
        self.journal.emit(JournalKind.DENIED_ON_TIMEOUT, action_id=esc.action_id)
