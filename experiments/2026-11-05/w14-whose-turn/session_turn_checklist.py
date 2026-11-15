"""Playground-original helpers for whose-turn *method* checklist rows (P2, P4, snapshot board).

Reimplements only the *ideas* from pinned upstream README prose — not whoseturn.py.
Stdlib only; no network, no signal JSON, no claim fencing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SessionExitVerdict(str, Enum):
    OK = "ok"
    DENY_HOLDING_TURN = "deny_holding_turn"


class MonitoringVerdict(str, Enum):
    OK = "ok"
    DENY_HEARTBEAT_MISSING = "deny_heartbeat_missing"


SNAPSHOT_BANNER_PREFIX = "SNAPSHOT — NOT LIVE TRUTH"
_GENERATED_AT_MARKER = "generated_at="


def _normalize_iso_for_parse(raw: str) -> str:
    ts = raw.strip()
    if ts.endswith("Z"):
        return ts[:-1] + "+00:00"
    return ts


def _iso_timestamp_valid(raw: str) -> bool:
    ts = raw.strip()
    if not ts:
        return False
    try:
        datetime.fromisoformat(_normalize_iso_for_parse(ts))
    except ValueError:
        return False
    return True


def _require_iso_timestamp(raw: str) -> str:
    ts = raw.strip()
    if not ts:
        raise ValueError("iso_timestamp must be non-empty")
    if not _iso_timestamp_valid(ts):
        raise ValueError(f"iso_timestamp must be ISO-8601-like, got {ts!r}")
    return ts


def _extract_generated_at_value(text: str) -> str | None:
    idx = text.find(_GENERATED_AT_MARKER)
    if idx < 0:
        return None
    tail = text[idx + len(_GENERATED_AT_MARKER) :]
    line, _, _ = tail.partition("\n")
    value = line.strip()
    if not value:
        return ""
    return value.split()[0]


@dataclass(frozen=True)
class SessionExitDecision:
    verdict: SessionExitVerdict
    rule: str = "P2"


@dataclass(frozen=True)
class MonitoringDecision:
    verdict: MonitoringVerdict
    rule: str = "P4"


def format_snapshot_board_header(iso_timestamp: str) -> str:
    """Board sketch label: states on its face that content is a timestamped snapshot."""
    ts = _require_iso_timestamp(iso_timestamp)
    return f"{SNAPSHOT_BANNER_PREFIX} — {_GENERATED_AT_MARKER}{ts}"


def snapshot_board_label_valid(text: str) -> bool:
    """True when a board artifact carries the required snapshot disclaimer + timestamp."""
    if SNAPSHOT_BANNER_PREFIX not in text:
        return False
    extracted = _extract_generated_at_value(text)
    if extracted is None or extracted == "":
        return False
    return _iso_timestamp_valid(extracted)


def check_session_exit(*, holding_turn: bool) -> SessionExitDecision:
    """P2: never end a session while your name still holds the turn."""
    if holding_turn:
        return SessionExitDecision(SessionExitVerdict.DENY_HOLDING_TURN)
    return SessionExitDecision(SessionExitVerdict.OK)


def check_monitoring_claim(*, claims_monitoring: bool, has_heartbeat: bool) -> MonitoringDecision:
    """P4: do not claim monitoring unless a heartbeat can be shown."""
    if claims_monitoring and not has_heartbeat:
        return MonitoringDecision(MonitoringVerdict.DENY_HEARTBEAT_MISSING)
    return MonitoringDecision(MonitoringVerdict.OK)
