"""Pure HOLD|GO sketch for Nunchi presend recheck — not a port of turn.py."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

# Mirrors upstream visibility gate (mentatzoe/nunchi turn.py @ pin); sketch only.
VISIBLE_KINDS = frozenset({"message", "reply", "reaction"})


@dataclass(frozen=True, slots=True)
class LookAgainVerdict:
    """Outcome of a single presend recheck."""

    decision: str  # "HOLD" | "GO"
    answer_candidates: tuple[str, ...]
    board_revision_at_compose: int
    board_revision_now: int
    held_by_other_messages: int = 0


def _other_messages_since(
    events: Sequence[Mapping[str, Any]], *, self_participant: str
) -> int:
    # Sketch-only: upstream new_messages() counts all messages, not authors.
    count = 0
    for event in events:
        if not isinstance(event, Mapping):
            continue
        if event.get("type") != "message":
            continue
        author = event.get("author") or event.get("participant")
        if author == self_participant:
            continue
        count += 1
    return count


def look_again_pure(
    *,
    board_revision_at_compose: int,
    board_revision_now: int,
    action_kind: str,
    interim_events: Sequence[Mapping[str, Any]],
    answer_candidates: Sequence[str],
    already_looked_again: bool = False,
    self_participant: str = "agent",
    expand_failed: bool = False,
) -> LookAgainVerdict:
    """Decide HOLD vs GO before sending a visible room action.

    Sketch of ``Turn.look_again`` HOLD|GO (turn.py @ pin, def ~1175–1199 — not a port):
    one recheck, board must have advanced; uses sketch author filter on messages.
    Failed expansion never blocks send (GO).
    """

    candidates = tuple(answer_candidates)
    base = LookAgainVerdict(
        decision="GO",
        answer_candidates=candidates,
        board_revision_at_compose=board_revision_at_compose,
        board_revision_now=board_revision_now,
        held_by_other_messages=0,
    )

    if already_looked_again:
        return base
    if action_kind not in VISIBLE_KINDS:
        return base
    if expand_failed:
        return base
    if board_revision_now <= board_revision_at_compose:
        return base

    held = _other_messages_since(interim_events, self_participant=self_participant)
    if held == 0:
        return base

    return LookAgainVerdict(
        decision="HOLD",
        answer_candidates=candidates,
        board_revision_at_compose=board_revision_at_compose,
        board_revision_now=board_revision_now,
        held_by_other_messages=held,
    )
