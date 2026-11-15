from __future__ import annotations

from typing import Literal, TypedDict

ArcStatusPhase = Literal["started", "milestone", "heartbeat", "done", "blocked"]

ARC_STATUS_PHASES: tuple[ArcStatusPhase, ...] = (
    "started",
    "milestone",
    "heartbeat",
    "done",
    "blocked",
)


class _ArcStatusEventRequired(TypedDict):
    arc_id: str
    phase: ArcStatusPhase
    title: str
    sent_at: str


class ArcStatusEvent(_ArcStatusEventRequired, total=False):
    body: str
    step: int
    total: int
    eta_minutes: float
    arc_kind: str
    protocol_version: str
