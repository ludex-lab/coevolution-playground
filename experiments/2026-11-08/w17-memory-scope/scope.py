"""Original offline scope-boundary method sketch; metadata never authorizes action."""
from dataclasses import dataclass
from enum import Enum

__all__ = ["Scope", "SourceEvent", "Entry", "Task", "Status", "Report",
           "lint_write", "read_scope", "applicable", "action_hold", "repair_hold"]


@dataclass(frozen=True)
class Scope:
    task_class: str
    stakes: int
    tools: frozenset[str]


@dataclass(frozen=True)
class SourceEvent:
    identity: str
    scope: Scope


@dataclass(frozen=True)
class Entry:
    text: str
    scope: Scope
    source_event: SourceEvent


@dataclass(frozen=True)
class Task:
    scope: Scope
    source_event: str


class Status(str, Enum):
    HOLD = "hold"
    IN_SCOPE = "in-scope"


@dataclass(frozen=True)
class Report:
    status: Status
    reasons: tuple[str, ...]


def _label(value):
    return (type(value) is str and bool(value.strip())
            and value == value.strip() and value not in {"*", "?", "unknown", "ambiguous"})


def _scope_valid(value):
    return (type(value) is Scope and _label(value.task_class)
            and type(value.stakes) is int and value.stakes >= 0
            and type(value.tools) is frozenset
            and all(_label(tool) for tool in value.tools))


def lint_write(entry):
    """Formation-scope check. Every malformed or expanded dimension yields a hold."""
    if type(entry) is not Entry or not _label(entry.text):
        return Report(Status.HOLD, ("missing-or-ambiguous-entry",))
    event = entry.source_event
    if type(event) is not SourceEvent or not _label(event.identity):
        return Report(Status.HOLD, ("missing-or-ambiguous-source",))
    if not _scope_valid(entry.scope) or not _scope_valid(event.scope):
        return Report(Status.HOLD, ("missing-or-ambiguous-scope",))
    reasons = []
    if entry.scope.task_class != event.scope.task_class:
        reasons.append("write-task-class-shift")
    # Stakes are labels, NOT an authority ordering: even a lower value is a shift.
    if entry.scope.stakes != event.scope.stakes:
        reasons.append("write-stakes-shift")
    if not entry.scope.tools <= event.scope.tools:
        reasons.append("write-tool-widening")
    return Report(Status.HOLD if reasons else Status.IN_SCOPE, tuple(reasons))


def read_scope(entry, task):
    """Application-scope check, including formation lint; never a dispatch decision."""
    formation = lint_write(entry)
    if formation.status is Status.HOLD:
        return formation
    if type(task) is not Task or not _scope_valid(task.scope):
        return Report(Status.HOLD, ("missing-or-ambiguous-task-scope",))
    if not _label(task.source_event):
        return Report(Status.HOLD, ("missing-or-ambiguous-task-source",))
    reasons = []
    if task.source_event != entry.source_event.identity:
        reasons.append("read-source-identity-mismatch")
    if task.scope.task_class != entry.scope.task_class:
        reasons.append("read-task-class-out-of-scope")
    if task.scope.stakes != entry.scope.stakes:
        reasons.append("read-stakes-out-of-scope")
    if not task.scope.tools <= entry.scope.tools:
        reasons.append("read-tools-out-of-scope")
    return Report(Status.HOLD if reasons else Status.IN_SCOPE, tuple(reasons))


def applicable(entry, task):
    """True means only matching scope, never authority to skip safeguards."""
    return read_scope(entry, task).status is Status.IN_SCOPE


def action_hold(entry, task):
    report = read_scope(entry, task)
    return Report(Status.HOLD, report.reasons + ("independent-action-review-required",))


def repair_hold(original_test, proposed_test):
    """Conservatively freeze the entire correct safeguard test, not just assertions."""
    if original_test != proposed_test:
        return original_test, Report(Status.HOLD, ("blocked-repair-test-change",))
    return original_test, Report(Status.HOLD, ("blocked-repair-frozen-defect",))
