"""Playground-original sketch: outbound budget_max + cooldown gates.

Reimplemented from the *idea* of rate-limiting agent chatter only.
NOT derived from Shut-Up upstream source (NO LICENSE — do not copy).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DenyReason(str, Enum):
    BUDGET = "budget_max"
    COOLDOWN = "cooldown"


class GateOutcome(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class GateDecision:
    outcome: GateOutcome
    reason: Optional[DenyReason] = None
    remaining_budget: int = 0
    cooldown_remaining_s: float = 0.0


@dataclass
class OutboundBudgetCooldownGate:
    """Cap total sends (budget_max) and enforce minimum gap (cooldown_s)."""

    budget_max: int
    cooldown_s: float
    sends_used: int = 0
    last_send_at: Optional[float] = None

    def __post_init__(self) -> None:
        if self.budget_max < 0:
            raise ValueError("budget_max must be non-negative")
        if self.cooldown_s < 0:
            raise ValueError("cooldown_s must be non-negative")

    def preview(self, now: float) -> GateDecision:
        remaining = self.budget_max - self.sends_used
        if remaining <= 0:
            return GateDecision(GateOutcome.DENY, DenyReason.BUDGET, 0, 0.0)
        if self.last_send_at is not None:
            elapsed = now - self.last_send_at
            if elapsed < self.cooldown_s:
                return GateDecision(
                    GateOutcome.DENY,
                    DenyReason.COOLDOWN,
                    remaining,
                    self.cooldown_s - elapsed,
                )
        return GateDecision(GateOutcome.ALLOW, None, remaining - 1, 0.0)

    def request_send(self, now: float) -> GateDecision:
        decision = self.preview(now)
        if decision.outcome == GateOutcome.ALLOW:
            self.sends_used += 1
            self.last_send_at = now
        return decision
