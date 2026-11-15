"""Pure handback directive evaluator (agent-bridge-mcp evaluateOrchestratorDirective sketch)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

ACTIONS = frozenset(
    {
        "COMPLETE",
        "ESCALATE_TO_HUMAN",
        "CONTINUE_AUTONOMOUSLY",
        "POLL_ATTACH",
        "AUTHORIZE_REMOTE_PUBLISH",
        "blocked",
    }
)


@dataclass(frozen=True, slots=True)
class DirectiveResult:
    action: str
    reason: str


def _pick(observed: Mapping[str, Any], reported: Mapping[str, Any], key: str) -> Any:
    if key not in observed:
        return reported.get(key)
    if key not in reported:
        return observed[key]
    obs_val = observed[key]
    rep_val = reported[key]
    if obs_val != rep_val:
        return obs_val
    return obs_val


def _status_complete(status: Any) -> bool:
    return str(status or "").lower() in {"complete", "done", "success"}


def _complete_reason(observed: Mapping[str, Any], reported: Mapping[str, Any]) -> str:
    obs_complete = _status_complete(observed.get("status"))
    rep_complete = _status_complete(reported.get("status"))
    if obs_complete and rep_complete:
        return "aligned_complete"
    if obs_complete:
        return "observed_complete"
    return "reported_complete"


def _effective(observed: Mapping[str, Any], reported: Mapping[str, Any]) -> dict[str, Any]:
    keys = set(reported) | set(observed)
    return {k: _pick(observed, reported, k) for k in keys}


def _fingerprint(state: Mapping[str, Any]) -> str | None:
    fp = state.get("blocker_fingerprint") or state.get("blocker_id")
    if fp is None:
        return None
    return str(fp)


def _locked_path_violation(state: Mapping[str, Any]) -> str | None:
    locked = state.get("locked_paths") or ()
    changed = state.get("changed_paths") or ()
    locked_norm = [str(p).rstrip("/") + "/" if str(p) and not str(p).endswith("/") else str(p) for p in locked]
    for path in changed:
        p = str(path)
        for root in locked_norm:
            root_s = root if root.endswith("/") else root + "/"
            if p == root.rstrip("/") or p.startswith(root_s):
                return p
    if state.get("locked_path_violation"):
        return str(state["locked_path_violation"])
    return None


def directive(
    observed: Mapping[str, Any],
    reported: Mapping[str, Any],
    evidence_refs: Sequence[str],
    prior_fingerprint: str | None,
    streak: int,
    budget: Mapping[str, Any] | None,
) -> DirectiveResult:
    eff = _effective(observed, reported)
    violation = _locked_path_violation(eff)
    if violation:
        return DirectiveResult(
            "blocked",
            f"locked_path_changed:{violation}",
        )

    pending = eff.get("pending_attachments") or ()
    if pending and not eff.get("attachments_ready"):
        return DirectiveResult("POLL_ATTACH", "awaiting_attachments")

    if eff.get("remote_publish_pending") and not eff.get("remote_publish_authorized"):
        return DirectiveResult("AUTHORIZE_REMOTE_PUBLISH", "remote_publish_requires_approval")

    if budget is not None:
        remaining = budget.get("remaining")
        if remaining is not None and int(remaining) <= 0:
            return DirectiveResult("ESCALATE_TO_HUMAN", "budget_exhausted")

    if _status_complete(eff.get("status")) and eff.get("verification_ok", True):
        return DirectiveResult("COMPLETE", _complete_reason(observed, reported))

    fp = _fingerprint(eff)
    if fp and streak >= 2 and prior_fingerprint == fp:
        return DirectiveResult("ESCALATE_TO_HUMAN", f"same_blocker_streak:{fp}")

    prior_refs = set(str(r) for r in (eff.get("prior_evidence_refs") or ()))
    new_refs = [str(r) for r in evidence_refs if str(r) not in prior_refs]
    if new_refs:
        return DirectiveResult(
            "CONTINUE_AUTONOMOUSLY",
            f"new_evidence:{new_refs[0]}",
        )

    if eff.get("blocker_id") or fp:
        return DirectiveResult("CONTINUE_AUTONOMOUSLY", "blocked_progress")

    return DirectiveResult("CONTINUE_AUTONOMOUSLY", "default_continue")
