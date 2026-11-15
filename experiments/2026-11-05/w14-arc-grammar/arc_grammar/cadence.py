"""Retroactive-started cadence floor + configurable heartbeat interval (emitter side).

Port of upstream ``packages/reference/src/cadence.ts`` with a Team OS fix: no
``heartbeat`` while the last emitted phase is ``blocked`` (§4.5; upstream TS
still emits — do not inherit that bug).
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Callable
from dataclasses import dataclass, field

from .types import ArcStatusEvent, ArcStatusPhase


def _default_now_ms() -> int:
    return int(_dt.datetime.now(_dt.timezone.utc).timestamp() * 1000)


def _iso_z(ms: int) -> str:
    secs, millis = divmod(ms, 1000)
    stamp = _dt.datetime.fromtimestamp(secs, _dt.timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S") + f".{millis:03d}Z"


@dataclass(frozen=True, slots=True)
class CadenceConfig:
    """All intervals are caller-supplied; this sketch does not embed Team OS timing law."""

    cadence_floor_ms: int = 0
    heartbeat_interval_ms: int | None = None
    now: Callable[[], int] = field(default=_default_now_ms)


@dataclass(frozen=True, slots=True)
class ArcSeed:
    arc_id: str
    title: str
    arc_kind: str | None = None
    protocol_version: str | None = None


class CadenceController:
    """Per-arc emitter discipline: floor-gated started, optional heartbeat on silence."""

    def __init__(self, config: CadenceConfig | None = None) -> None:
        cfg = config or CadenceConfig()
        self._floor_ms = cfg.cadence_floor_ms
        self._interval_ms = cfg.heartbeat_interval_ms
        self._now = cfg.now
        self._seed: ArcSeed | None = None
        self._began_at = 0
        self._started_emitted = False
        self._terminal = False
        self._last_emit_at = 0
        self._last_phase: ArcStatusPhase | None = None

    def begin(self, seed: ArcSeed) -> ArcStatusEvent | None:
        self._seed = seed
        self._began_at = self._now()
        self._started_emitted = False
        self._terminal = False
        self._last_emit_at = 0
        self._last_phase = None
        return self._maybe_emit_started()

    def on_emit(self, event: ArcStatusEvent) -> None:
        self._last_emit_at = self._now()
        self._last_phase = event["phase"]
        if event["phase"] == "started":
            self._started_emitted = True
        if event["phase"] == "done":
            self._terminal = True

    def tick(self, current_activity: str = "still working") -> ArcStatusEvent | None:
        if self._terminal or self._seed is None:
            return None
        if not self._started_emitted:
            return self._maybe_emit_started()
        if self._interval_ms is None:
            return None
        if self._last_phase == "blocked":
            return None
        if self._now() - self._last_emit_at >= self._interval_ms:
            return self._emit("heartbeat", current_activity)
        return None

    def is_terminal(self) -> bool:
        return self._terminal

    def _maybe_emit_started(self) -> ArcStatusEvent | None:
        seed = self._seed
        if self._started_emitted or self._terminal or seed is None:
            return None
        if self._now() - self._began_at < self._floor_ms:
            return None
        self._started_emitted = True
        return self._emit("started", seed.title)

    def _emit(self, phase: ArcStatusPhase, title: str) -> ArcStatusEvent:
        seed = self._seed
        assert seed is not None
        t = self._now()
        self._last_emit_at = t
        self._last_phase = phase
        event: ArcStatusEvent = {
            "arc_id": seed.arc_id,
            "phase": phase,
            "title": title,
            "sent_at": _iso_z(t),
        }
        if seed.arc_kind:
            event["arc_kind"] = seed.arc_kind
        if seed.protocol_version:
            event["protocol_version"] = seed.protocol_version
        return event
