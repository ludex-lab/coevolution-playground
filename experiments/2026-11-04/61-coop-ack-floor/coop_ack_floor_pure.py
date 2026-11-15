"""Coop ack-floor gate sketch (spalk/coop rules @ pin; no SQLite/HTTP)."""

from __future__ import annotations

from dataclasses import dataclass

AGENT_MOVE_TYPES = frozenset({"say", "ask", "propose", "agree", "reject", "defer", "resolution"})
REPLY_TYPES = frozenset({"agree", "reject", "defer"})
MAX_SUMMARY_CHARS = 120
PAUSE_BUDGET = "budget"


@dataclass(frozen=True, slots=True)
class GateResult:
    ok: bool
    code: str = ""
    unread_seqs: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class SideTurnBudget:
    turn_budget: int
    turns_used: tuple[int, ...]


def validate_one_line_summary(summary: str) -> str | None:
    text = summary.strip()
    if not text:
        return "summary_required"
    if "\n" in text or "\r" in text or len(text) > MAX_SUMMARY_CHARS:
        return "summary_one_line"
    return None


def unread_human_seqs(*, ack: int, human_seqs: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(seq for seq in human_seqs if seq > ack)


def after_public_turn(state: SideTurnBudget, side: int) -> tuple[SideTurnBudget, str]:
    """Increment poster turn count; set budget pause when side exhausts turn_budget (@ pin)."""
    used = list(state.turns_used)
    used[side] += 1
    pause = PAUSE_BUDGET if used[side] >= state.turn_budget else ""
    return SideTurnBudget(state.turn_budget, tuple(used)), pause


def next_floor_side(
    *,
    floor_side: int,
    poster_side: int,
    n_sides: int,
    floor_mode: str = "pass",
    to_side: int | None = None,
) -> int:
    """Public move floor hand-off: keep | pass (default) | explicit to (@ pin Message.Floor / To)."""
    if floor_mode == "keep":
        return floor_side
    if to_side is not None and 0 <= to_side < n_sides:
        return to_side
    return (poster_side + 1) % n_sides


def gate_agent_public_move(
    *,
    floor_side: int,
    poster_side: int,
    pause_kind: str,
    ack: int | None,
    move_type: str,
    summary: str,
    re_seq: int,
    human_seqs: tuple[int, ...],
) -> GateResult:
    if move_type not in AGENT_MOVE_TYPES:
        return GateResult(ok=False, code="bad_move_type")
    if ack is None:
        return GateResult(ok=False, code="ack_required")
    if err := validate_one_line_summary(summary):
        return GateResult(ok=False, code=err)
    if move_type in REPLY_TYPES and re_seq == 0:
        return GateResult(ok=False, code=f"{move_type}_needs_re")
    if move_type == "resolution" and re_seq != 0:
        return GateResult(ok=False, code="resolution_no_re")
    unread = unread_human_seqs(ack=ack, human_seqs=human_seqs)
    if unread:
        return GateResult(ok=False, code="unread_human_message", unread_seqs=unread)
    if pause_kind:
        return GateResult(ok=False, code="paused")
    if floor_side != poster_side:
        return GateResult(ok=False, code="not_your_turn")
    return GateResult(ok=True)
