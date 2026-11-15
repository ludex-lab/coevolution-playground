"""Consumer-side liveness using local receipt time (never event sent_at)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


def _default_now_ms() -> int:
    import datetime as _dt

    return int(_dt.datetime.now(_dt.timezone.utc).timestamp() * 1000)


@dataclass(frozen=True, slots=True)
class ReceiptLiveness:
    """Tracks when events were received; interval checks are configurable per deployment."""

    now: Callable[[], int] = field(default=_default_now_ms)
    _last_receipt_ms: dict[str, int] = field(default_factory=dict)

    def record(self, arc_id: str, receipt_ms: int | None = None) -> None:
        """Record local receipt time for an arc (ignore payload sent_at for liveness)."""
        self._last_receipt_ms[arc_id] = self.now() if receipt_ms is None else receipt_ms

    def forget(self, arc_id: str) -> None:
        self._last_receipt_ms.pop(arc_id, None)

    def ms_since_receipt(self, arc_id: str, now_ms: int | None = None) -> int | None:
        last = self._last_receipt_ms.get(arc_id)
        if last is None:
            return None
        now = self.now() if now_ms is None else now_ms
        return now - last

    def heartbeat_due(self, arc_id: str, heartbeat_interval_ms: int, now_ms: int | None = None) -> bool:
        """True when silence since last *receipt* exceeds the configured interval."""
        elapsed = self.ms_since_receipt(arc_id, now_ms=now_ms)
        if elapsed is None:
            return False
        return elapsed >= heartbeat_interval_ms
