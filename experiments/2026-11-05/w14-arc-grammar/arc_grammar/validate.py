"""Wire-format and phase-sequence validation (stdlib only).

Port of upstream ``packages/reference/src/validate.ts`` (pin 7a3206b): same
regex strings and error messages, with Python/JS parity fixes — ``fullmatch``,
ASCII ``\\d``, UTF-16 string length caps, and calendar years with ``int(year) >= 100``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal, cast

from .types import ARC_STATUS_PHASES, ArcStatusEvent

RFC3339_PATTERN = (
    r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])"
    r"T([01]\d|2[0-3]):[0-5]\d:[0-5]\d(\.\d{1,9})?"
    r"(Z|[+-](0\d|1[0-4]):[0-5]\d)$"
)

_RFC3339_RE = re.compile(RFC3339_PATTERN, re.ASCII)
_PROTOCOL_VERSION_RE = re.compile(r"^\d+\.\d+(\.\d+)?$", re.ASCII)


def _utf16_len(text: str) -> int:
    """JavaScript ``String.length`` (UTF-16 code units), including lone surrogates."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _utf16_len_safe(text: str) -> tuple[int | None, ValidationIssue | None]:
    try:
        return _utf16_len(text), None
    except UnicodeEncodeError:
        return None, ValidationIssue("", "string is not valid for UTF-16 measurement")

_KNOWN_KEYS = frozenset(
    {
        "arc_id",
        "phase",
        "title",
        "body",
        "step",
        "total",
        "eta_minutes",
        "sent_at",
        "arc_kind",
        "protocol_version",
    }
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationOk:
    event: ArcStatusEvent
    ok: Literal[True] = True


@dataclass(frozen=True, slots=True)
class ValidationErr:
    issues: list[ValidationIssue]
    ok: Literal[False] = False


ValidationResult = ValidationOk | ValidationErr


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_valid_calendar_date(ts: str) -> bool:
    year_s = ts[0:4]
    try:
        year = int(year_s)
    except ValueError:
        return False
    if year < 100:
        return False
    try:
        date(year, int(ts[5:7]), int(ts[8:10]))
        return True
    except ValueError:
        return False


def validate(candidate: object) -> ValidationResult:
    if not isinstance(candidate, dict):
        return ValidationErr([ValidationIssue("", "event must be a JSON object")])

    e = candidate
    issues: list[ValidationIssue] = []

    for key in e:
        if key not in _KNOWN_KEYS and not (isinstance(key, str) and key.startswith("x_")):
            issues.append(
                ValidationIssue(
                    str(key), "unknown field; only x_-prefixed extensions are permitted"
                )
            )

    arc_id = e.get("arc_id")
    if not isinstance(arc_id, str):
        issues.append(ValidationIssue("arc_id", "must be a string"))
    else:
        arc_id_len, arc_id_err = _utf16_len_safe(arc_id)
        if arc_id_err is not None:
            issues.append(ValidationIssue("arc_id", "must be a valid Unicode string"))
        elif arc_id_len is not None and (arc_id_len < 1 or arc_id_len > 128):
            issues.append(ValidationIssue("arc_id", "must be between 1 and 128 characters"))

    if e.get("phase") not in ARC_STATUS_PHASES:
        issues.append(ValidationIssue("phase", "must be one of: " + ", ".join(ARC_STATUS_PHASES)))

    title = e.get("title")
    if not isinstance(title, str):
        issues.append(ValidationIssue("title", "must be a string"))
    else:
        title_len, title_err = _utf16_len_safe(title)
        if title_err is not None:
            issues.append(ValidationIssue("title", "must be a valid Unicode string"))
        elif title_len is not None and (title_len < 1 or title_len > 200):
            issues.append(ValidationIssue("title", "must be between 1 and 200 characters"))
        elif "\n" in title:
            issues.append(
                ValidationIssue(
                    "title", "should not contain newlines (use body for multi-line content)"
                )
            )

    sent_at = e.get("sent_at")
    if not isinstance(sent_at, str):
        issues.append(ValidationIssue("sent_at", "must be a string"))
    elif _RFC3339_RE.fullmatch(sent_at) is None:
        issues.append(
            ValidationIssue(
                "sent_at",
                "must be an RFC 3339 timestamp (canonical: YYYY-MM-DDTHH:MM:SS[.fff]Z)",
            )
        )
    elif not _is_valid_calendar_date(sent_at):
        issues.append(ValidationIssue("sent_at", "is not a valid calendar date"))

    if "body" in e:
        body = e["body"]
        if not isinstance(body, str):
            issues.append(ValidationIssue("body", "must be a string when present"))
        else:
            body_len, body_err = _utf16_len_safe(body)
            if body_err is not None:
                issues.append(ValidationIssue("body", "must be a valid Unicode string"))
            elif body_len is not None and body_len > 32000:
                issues.append(ValidationIssue("body", "must be ≤ 32000 characters"))

    if "step" in e:
        step = e["step"]
        if not _is_int(step) or cast(int, step) < 1:
            issues.append(ValidationIssue("step", "must be an integer ≥ 1"))

    if "total" in e:
        total = e["total"]
        if not _is_int(total) or cast(int, total) < 1:
            issues.append(ValidationIssue("total", "must be an integer ≥ 1"))

    step_v = e.get("step")
    total_v = e.get("total")
    if _is_int(step_v) and _is_int(total_v) and cast(int, step_v) > cast(int, total_v):
        issues.append(ValidationIssue("step", "must be ≤ total when both are present"))

    if "eta_minutes" in e:
        eta = e["eta_minutes"]
        if not _is_number(eta) or cast(float, eta) < 0:
            issues.append(ValidationIssue("eta_minutes", "must be a number ≥ 0"))

    if "arc_kind" in e:
        arc_kind = e["arc_kind"]
        if not isinstance(arc_kind, str):
            issues.append(ValidationIssue("arc_kind", "must be a string when present"))
        else:
            kind_len, kind_err = _utf16_len_safe(arc_kind)
            if kind_err is not None:
                issues.append(ValidationIssue("arc_kind", "must be a valid Unicode string"))
            elif kind_len is not None and kind_len > 64:
                issues.append(ValidationIssue("arc_kind", "must be ≤ 64 characters"))

    if "protocol_version" in e:
        pv = e["protocol_version"]
        if not isinstance(pv, str):
            issues.append(ValidationIssue("protocol_version", "must be a string when present"))
        elif _PROTOCOL_VERSION_RE.fullmatch(pv) is None:
            issues.append(
                ValidationIssue("protocol_version", "must match <major>.<minor>(.<patch>)?")
            )

    if issues:
        return ValidationErr(issues)
    return ValidationOk(cast("ArcStatusEvent", e))


@dataclass(frozen=True, slots=True)
class SequenceIssue:
    index: int
    message: str


@dataclass(frozen=True, slots=True)
class SequenceResult:
    ok: bool
    issues: list[SequenceIssue]


def _parse_ts(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def validate_sequence(
    events: list[ArcStatusEvent],
    *,
    partial: bool = False,
    check_monotonic_sent_at: bool = False,
) -> SequenceResult:
    issues: list[SequenceIssue] = []

    if len(events) == 0:
        return SequenceResult(True, issues)

    arc_id = events[0].get("arc_id")
    for i in range(1, len(events)):
        if events[i].get("arc_id") != arc_id:
            issues.append(
                SequenceIssue(
                    i, f"arc_id mismatch: expected {arc_id}, got {events[i].get('arc_id')}"
                )
            )

    if events[0].get("phase") != "started":
        issues.append(SequenceIssue(0, "first event in an arc must be phase=started"))

    started_count = sum(1 for e in events if e.get("phase") == "started")
    done_count = sum(1 for e in events if e.get("phase") == "done")
    saw_done_at = next((i for i, e in enumerate(events) if e.get("phase") == "done"), None)

    if started_count != 1:
        issues.append(
            SequenceIssue(0, f"arc must contain exactly one started event, found {started_count}")
        )

    if done_count > 1:
        issues.append(
            SequenceIssue(0, f"arc must contain at most one done event, found {done_count}")
        )

    if saw_done_at is not None and saw_done_at != len(events) - 1:
        issues.append(SequenceIssue(saw_done_at, "no events may follow a done event"))

    for i in range(len(events) - 1):
        if events[i].get("phase") == "blocked":
            nxt = events[i + 1].get("phase")
            if nxt == "started":
                issues.append(SequenceIssue(i + 1, "started cannot follow blocked"))
            if nxt == "heartbeat":
                issues.append(
                    SequenceIssue(
                        i + 1,
                        "blocked must be followed by milestone (resume), done (resolve), or "
                        "end-of-arc; heartbeat is not a legal resume signal",
                    )
                )
            if nxt == "blocked":
                issues.append(
                    SequenceIssue(
                        i + 1,
                        "consecutive blocked events are not allowed; emit a milestone (resume) "
                        "before re-blocking (§4.5)",
                    )
                )

    if not partial:
        last_phase = events[-1].get("phase")
        if last_phase != "done" and last_phase != "blocked":
            issues.append(
                SequenceIssue(
                    len(events) - 1,
                    "a complete arc must end in a terminal event (done or terminal blocked); pass "
                    "partial=True to validate an in-flight prefix",
                )
            )

    if check_monotonic_sent_at:
        for i in range(1, len(events)):
            prev = _parse_ts(events[i - 1].get("sent_at"))
            cur = _parse_ts(events[i].get("sent_at"))
            if prev is not None and cur is not None and cur < prev:
                issues.append(
                    SequenceIssue(
                        i,
                        "sent_at decreased from the previous event; not allowed when "
                        "check_monotonic_sent_at is set",
                    )
                )

    return SequenceResult(len(issues) == 0, issues)
