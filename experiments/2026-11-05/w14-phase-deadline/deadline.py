"""Phase budgets + bounded extension (clean-room; pi-toolkit deadline.ts semantics)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Mapping, Optional, Union

Millis = int
RunPhase = Literal[
    "ingress_queue", "config_resolve", "session_open", "worker_attach",
    "first_token_wait", "model_slice", "tool_slice", "retry_cooldown",
    "transcript_compact", "shutdown_grace", "reap", "settled",
]
RunStatus = Literal["queued", "starting", "running", "stopping", "completed", "failed", "timed_out", "aborted"]
ExtendRefusal = Literal[
    "already_terminal", "stopping", "not_started", "uncapped", "limit_reached", "no_headroom", "step_disabled",
]
GrantCapResult = Union[tuple[Literal[True], Millis], tuple[Literal[False], Literal["step_disabled"]]]
GrantResult = Union[tuple[Literal[True], Millis], tuple[Literal[False], ExtendRefusal]]

MAX_DEADLINE_SPAN_MS = 365 * 86_400_000
OVERTIME_PHASES: tuple[RunPhase, ...] = (
    "first_token_wait", "model_slice", "tool_slice", "retry_cooldown", "transcript_compact",
)
_TERMINAL = frozenset({"completed", "failed", "timed_out", "aborted"})


@dataclass(frozen=True, slots=True)
class PhaseBudget:
    slot_wait_ms: Millis
    boot_ms: Millis
    attach_ms: Millis
    first_token_ms: Millis
    idle_ms: Millis
    model_slice_cap_ms: Millis
    tool_ms: Millis
    compact_ms: Millis
    shutdown_grace_ms: Millis
    reap_ms: Millis
    retry_slack_ms: Millis
    total_ms: Millis
    total_grace_ms: Millis
    max_extensions: int
    max_total_factor: float
    extend_step_ms: Millis


@dataclass(frozen=True, slots=True)
class PhaseDiag:
    phase_entered_at: Millis
    last_event_at: Optional[Millis] = None
    retry_delay_ms: Millis = 0


@dataclass(frozen=True, slots=True)
class RunDeadlines:
    deadline_at: Optional[Millis]
    hard_deadline_at: Optional[Millis]


@dataclass(frozen=True, slots=True)
class RunSlice:
    status: RunStatus
    phase: RunPhase
    deadlines: RunDeadlines
    extensions_used: int = 0


def _clamp_span_ms(ms: float) -> Optional[Millis]:
    if ms == math.inf:
        return MAX_DEADLINE_SPAN_MS
    if not math.isfinite(ms) or ms <= 0:
        return None
    return int(min(ms, MAX_DEADLINE_SPAN_MS))


def _budget_span_keys(b: PhaseBudget) -> Mapping[str, Union[int, float]]:
    return {
        "total_ms": b.total_ms,
        "max_total_factor": b.max_total_factor,
        "max_extensions": b.max_extensions,
        "extend_step_ms": b.extend_step_ms,
    }


def idle_due_at(diag: PhaseDiag, budget: PhaseBudget) -> Millis:
    base = diag.last_event_at if diag.last_event_at is not None else diag.phase_entered_at
    return base + budget.idle_ms + diag.retry_delay_ms + budget.retry_slack_ms


def due_at_for(phase: RunPhase, diag: PhaseDiag, budget: PhaseBudget) -> Optional[Millis]:
    start = diag.phase_entered_at
    if phase == "model_slice":
        event_base = diag.last_event_at if diag.last_event_at is not None else start
        silence = None if budget.idle_ms == 0 else event_base + budget.idle_ms
        cap = None if budget.model_slice_cap_ms == 0 else start + budget.model_slice_cap_ms
        if silence is None:
            return cap
        if cap is None:
            return silence
        return min(silence, cap)
    if phase == "retry_cooldown":
        return idle_due_at(diag, budget)
    ms = {
        "ingress_queue": budget.slot_wait_ms,
        "worker_attach": budget.attach_ms,
        "first_token_wait": budget.first_token_ms,
        "tool_slice": budget.tool_ms,
        "transcript_compact": budget.compact_ms,
        "shutdown_grace": budget.shutdown_grace_ms,
        "reap": budget.reap_ms,
    }.get(phase)
    if phase in ("config_resolve", "session_open"):
        ms = budget.boot_ms
    if ms is None or ms == 0:
        return None
    return start + ms


def extendable_span_ms(budget: Mapping[str, Union[int, float]]) -> Optional[Millis]:
    total = _clamp_span_ms(float(budget["total_ms"]))
    if total is None:
        return None
    factor_raw = float(budget.get("max_total_factor", 1))
    factor = max(1.0, factor_raw) if math.isfinite(factor_raw) else 1.0
    scaled = total * factor
    factor_span = MAX_DEADLINE_SPAN_MS if not math.isfinite(scaled) else (_clamp_span_ms(math.ceil(scaled)) or total)
    step_f = float(budget.get("extend_step_ms", 0))
    step_ms = 0 if not math.isfinite(step_f) or step_f <= 0 else int(min(step_f, MAX_DEADLINE_SPAN_MS))
    ext_f = float(budget.get("max_extensions", 0))
    max_extensions = 0 if not math.isfinite(ext_f) else max(0, int(ext_f))
    step_span: Optional[Millis] = None
    if factor > 1 and max_extensions > 0 and step_ms > 0:
        raw_step = total + max_extensions * step_ms
        step_span = MAX_DEADLINE_SPAN_MS if raw_step > MAX_DEADLINE_SPAN_MS else (_clamp_span_ms(raw_step) or factor_span)
    return max(total, factor_span, step_span or 0)


def hard_deadline_at_for(enqueued_at: Millis, budget: PhaseBudget, cap_at: Optional[Millis]) -> Optional[Millis]:
    span = extendable_span_ms(_budget_span_keys(budget))
    if span is None:
        return None
    raw = enqueued_at + span
    return raw if cap_at is None else min(raw, cap_at)


def extendability(
    state: RunSlice, budget: PhaseBudget, now: Millis,
) -> Union[tuple[Literal[True], Millis], tuple[Literal[False], ExtendRefusal]]:
    if state.status in _TERMINAL:
        return False, "already_terminal"
    if state.phase in ("shutdown_grace", "reap"):
        return False, "stopping"
    if state.phase not in OVERTIME_PHASES:
        return False, "not_started"
    d_at, hard = state.deadlines.deadline_at, state.deadlines.hard_deadline_at
    if d_at is None or hard is None:
        return False, "uncapped"
    if state.extensions_used >= budget.max_extensions:
        return False, "limit_reached"
    headroom = hard - max(now, d_at)
    return (False, "no_headroom") if headroom <= 0 else (True, headroom)


def extension_grant_cap_ms(budget: PhaseBudget, extend_ms: float) -> GrantCapResult:
    step = budget.extend_step_ms
    if not math.isfinite(step) or step <= 0:
        return False, "step_disabled"
    requested = max(0, int(extend_ms)) if math.isfinite(extend_ms) else 0
    return True, min(requested, max(0, int(step)))


def grant_extension_ms(state: RunSlice, budget: PhaseBudget, now: Millis, extend_ms: float) -> GrantResult:
    """Callee-enforced grant: min(per-grant cap, headroom), matching upstream min(base+ms, H)."""
    verdict = extendability(state, budget, now)
    if not verdict[0]:
        return False, verdict[1]
    headroom = verdict[1]
    cap_verdict = extension_grant_cap_ms(budget, extend_ms)
    if not cap_verdict[0]:
        return False, cap_verdict[1]
    return True, min(cap_verdict[1], headroom)


def grace_window(state: RunSlice, budget: PhaseBudget, at: Millis) -> Optional[Millis]:
    if budget.total_grace_ms <= 0 or not extendability(state, budget, at)[0]:
        return None
    hard = state.deadlines.hard_deadline_at
    assert hard is not None
    until = min(at + budget.total_grace_ms, hard)
    return until if until > at else None
