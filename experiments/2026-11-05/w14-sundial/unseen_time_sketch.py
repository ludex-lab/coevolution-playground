"""Playground-original sketch: unseen-time accrual vs wall ceiling (method only).

Reimplements *ideas* from pinned Sundial README / escalation essay — not Sundial
presence backends, ledger files, or watcher daemons. Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Presence(str, Enum):
    HERE = "here"
    ELSEWHERE = "elsewhere"
    AWAY = "away"


class LadderPhase(str, Enum):
    ACCRUING = "accruing"
    WALL_FORCED_TERMINAL = "wall_forced_terminal"
    MAX_PINGS_REACHED = "max_pings_reached"


@dataclass(frozen=True)
class TickResult:
    unseen_seconds: float
    wall_seconds: float
    pings_sent: int
    phase: LadderPhase


def unseen_rate(presence: Presence) -> float:
    """Sundial ladder accrual: paused here, half elsewhere, full away."""
    if presence == Presence.HERE:
        return 0.0
    if presence == Presence.ELSEWHERE:
        return 0.5
    return 1.0


def tick_unseen(
    *,
    unseen_seconds: float,
    wall_seconds: float,
    pings_sent: int,
    delta_wall_s: float,
    presence: Presence,
    wall_ceiling_s: float,
    max_pings: int = 3,
) -> TickResult:
    """Advance one deterministic step: unseen accrues by rate * wall delta; wall always advances."""
    if delta_wall_s < 0:
        raise ValueError("delta_wall_s must be non-negative")
    if max_pings < 1:
        raise ValueError("max_pings must be >= 1")

    new_wall = wall_seconds + delta_wall_s
    new_unseen = unseen_seconds + delta_wall_s * unseen_rate(presence)

    if new_wall >= wall_ceiling_s:
        return TickResult(
            unseen_seconds=new_unseen,
            wall_seconds=new_wall,
            pings_sent=pings_sent,
            phase=LadderPhase.WALL_FORCED_TERMINAL,
        )

    new_pings = pings_sent
    phase = LadderPhase.ACCRUING
    if new_pings >= max_pings:
        phase = LadderPhase.MAX_PINGS_REACHED

    return TickResult(
        unseen_seconds=new_unseen,
        wall_seconds=new_wall,
        pings_sent=new_pings,
        phase=phase,
    )


def record_ping(pings_sent: int, *, max_pings: int = 3) -> int:
    """Bounded nudge count — Sundial honesty rail: ≤3 pings per question."""
    if pings_sent >= max_pings:
        raise ValueError("ping budget exhausted")
    return pings_sent + 1
