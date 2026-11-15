"""Clean-room structured handoff notes checks (Handoff Debt seven-field contract).

Upstream reference: anjilab/agent-handoff-debt structured_notes field names @ pin
(f5fc2c7400ab6e5864e27c1f5a1868c83c53bab2, MIT — Copyright (c) 2026 Dipesh KC and
Anjila Budathoki). See NOTICE.md. Playground does not import OpenHands, litellm,
Docker, or the upstream harness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

STRUCTURED_FIELDS: tuple[str, ...] = (
    "problem_understanding",
    "work_completed",
    "evidence_observed",
    "observed_failures_or_error_evidence",
    "remaining_uncertainty",
    "rollback_notes",
    "recommended_next_action",
)

NO_CHANGE_CLAIMS: tuple[str, ...] = (
    "no code changes have been made",
    "no code changes were made",
    "no changes have been made",
    "no changes were made",
    "no source changes have been made",
    "no source changes were made",
    "working tree clean",
    "clean working tree",
    "nothing to commit",
    "no local changes",
    "no uncommitted changes",
    "no uncommitted change",
    "without uncommitted changes",
)

OVERCONFIDENT_STATUS_VALUES: frozenset[str] = frozenset(
    {"fixed", "done", "complete", "completed", "solved"}
)


@dataclass(frozen=True, slots=True)
class HandoffConsistencyResult:
    ok: bool
    issues: tuple[str, ...]


def combine_structured_fields(fields: Mapping[str, str]) -> str:
    return "\n".join(fields[name] for name in STRUCTURED_FIELDS)


def missing_structured_fields(fields: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(name for name in STRUCTURED_FIELDS if name not in fields)


def git_status_is_dirty(status_short: str) -> bool:
    """True when `git status --short` porcelain shows tracked edits or untracked paths.

    Untracked-only trees are **dirty** (`??` lines). Empty porcelain (no path lines)
    is clean. Do not infer cleanliness from notes that mention only "uncommitted"
    tracked edits while omitting untracked files.
    """
    for line in status_short.splitlines():
        if _porcelain_line_is_dirty(line):
            return True
    return False


def _porcelain_line_is_dirty(line: str) -> bool:
    stripped = line.rstrip("\n")
    if not stripped.strip() or stripped.lstrip().startswith("#"):
        return False
    if len(stripped) < 2:
        return True
    xy = stripped[0:2]
    if xy in ("??", "!!"):
        return True
    return xy[0] != " " or xy[1] != " "


def check_dirty_git_contradiction(
    *,
    git_dirty: bool,
    fields: Mapping[str, str],
) -> HandoffConsistencyResult:
    """Flag notes that claim a clean tree while git reports dirty (or the reverse)."""
    if missing_structured_fields(fields):
        return HandoffConsistencyResult(
            ok=False,
            issues=tuple(
                f"missing_field:{name}" for name in missing_structured_fields(fields)
            ),
        )

    combined = combine_structured_fields(fields)
    lower = combined.lower()
    issues: list[str] = []

    if lower.strip().rstrip(".") in OVERCONFIDENT_STATUS_VALUES:
        issues.append("overconfident_status")

    clean_claims = [phrase for phrase in NO_CHANGE_CLAIMS if phrase in lower]
    if git_dirty and clean_claims:
        for phrase in clean_claims:
            issues.append(f"dirty_git_contradiction:{phrase}")
    if not git_dirty and _claims_dirty_tree(lower):
        issues.append("clean_git_contradiction:notes_claim_dirty_tree")

    return HandoffConsistencyResult(ok=not issues, issues=tuple(issues))


def _strip_clean_claim_phrases(lower: str) -> str:
    """Remove NO_CHANGE_CLAIMS spans so negated clean phrases do not match dirty markers."""
    scrubbed = lower
    for phrase in sorted(NO_CHANGE_CLAIMS, key=len, reverse=True):
        scrubbed = scrubbed.replace(phrase, "")
    return scrubbed


def _claims_dirty_tree(lower: str) -> bool:
    scrubbed = _strip_clean_claim_phrases(lower)
    markers = (
        "uncommitted changes",
        "dirty working tree",
        "modified files not staged",
        "git is dirty",
    )
    return any(marker in scrubbed for marker in markers)


def validate_structured_handoff_record(
    *,
    fields: Mapping[str, str],
    git_dirty: bool | None = None,
    status_short: str | None = None,
) -> HandoffConsistencyResult:
    """Entry point: required seven fields + dirty/clean consistency.

    Prefer ``status_short`` from ``git status --short`` so untracked ``??`` paths
    mark the tree dirty. If only ``git_dirty`` is passed, callers must set it
    consistently with porcelain (including untracked).
    """
    if status_short is not None:
        resolved_dirty = git_status_is_dirty(status_short)
    elif git_dirty is not None:
        resolved_dirty = git_dirty
    else:
        raise ValueError("provide status_short or git_dirty")
    return check_dirty_git_contradiction(git_dirty=resolved_dirty, fields=fields)


def field_names() -> Sequence[str]:
    return STRUCTURED_FIELDS
