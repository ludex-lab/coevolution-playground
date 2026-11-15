"""Clean-room Agent Handoff Gate decision table (Wave15 Soft1 day-sketch).

Ported as ideas from zsoXi/agent-handoff-gate @ dd4d590c3059baeef5532d25d75fb4c048bbe7fd
(MIT, Copyright (c) 2026 Matt and Agent Handoff Gate contributors). This rewrite does
not vendor upstream TypeSafe/Jev tools, schemas, or example trees.

A recommended continuation is not an executed continuation.
A review-ready packet is not an accepted task.
The routing recommendation does not issue a grant.
A passing test, an evaluator's answer, an authorization to act, and the lead's
acceptance remain separate records.
"""

from __future__ import annotations

from dataclasses import dataclass

REVIEW_READY = "REVIEW_READY"
CONTINUATION_ELIGIBLE = "CONTINUATION_ELIGIBLE"
STOP = "STOP"
LEAD_REVIEW = "LEAD_REVIEW"

EVIDENCE_READY_AT_LOCAL_STAGE = "EVIDENCE_READY_AT_LOCAL_STAGE"
LOCAL_EVIDENCE_GAP_WITHIN_PROPOSED_BUDGET = "LOCAL_EVIDENCE_GAP_WITHIN_PROPOSED_BUDGET"
SUPPORTED_LOCAL_REPAIR_PROPOSAL = "SUPPORTED_LOCAL_REPAIR_PROPOSAL"
PROHIBITED_OPERATION = "PROHIBITED_OPERATION"
EVALUATOR_TIMEOUT = "EVALUATOR_TIMEOUT"
STALE_CANDIDATE = "STALE_CANDIDATE"

PASS = "PASS"
BLOCKED = "BLOCKED"
EVALUATED = "EVALUATED"
CONFIRMED = "CONFIRMED"
INSUFFICIENT = "INSUFFICIENT"

FORBIDDEN_ROUTE_TOKENS = (
    "AUTO_ACCEPT",
    "AUTO_MERGE",
    "AUTO_DEPLOY",
    "AUTO_AUTHORIZE_FOR_PRODUCTION",
    "auto-accept",
    "auto-merge",
    "auto-deploy",
    "auto-authorize-for-production",
)

SEPARATE_RECORDS = (
    "passing_test",
    "evaluator_answer",
    "authorization_to_act",
    "lead_acceptance",
)


@dataclass(frozen=True)
class Packet:
    """Minimal synthetic packet plus assessment fields the table inspects.

    `folder` is the upstream example title used as a label, not a routing enum.
    """

    folder: str
    worker_report: str
    assessment_status: str
    prohibited_operation: bool
    candidate_match: bool
    evaluator_timeout: bool
    criterion_labels: tuple[str, ...]
    repair_proposal_supported: bool
    budget_remaining: bool = True


@dataclass(frozen=True)
class GateResult:
    folder: str
    routing_recommendation: str
    routing_reason: str
    execution_authorized: bool
    grant_issued: bool
    review_ready_only: bool
    accepted: bool
    merged: bool
    deployed: bool
    authorized_for_production: bool


def _assert_no_forbidden_route(recommendation: str, reason: str) -> None:
    blob = f"{recommendation} {reason}"
    for token in FORBIDDEN_ROUTE_TOKENS:
        if token.lower() in blob.lower():
            raise ValueError(f"forbidden route token {token!r} in {blob!r}")


def apply_gate(packet: Packet) -> GateResult:
    """Return a routing recommendation. Never issues a grant or merge authority.

    Priority follows the upstream protocol notes:
    a hard stop / prohibited action stays a stop even if the evaluator is down;
    evaluator timeout falls back to lead review with no extra grant;
    a stale candidate is not reused as current evidence.
    """
    if packet.prohibited_operation:
        recommendation, reason = STOP, PROHIBITED_OPERATION
    elif packet.assessment_status != EVALUATED and packet.evaluator_timeout:
        recommendation, reason = LEAD_REVIEW, EVALUATOR_TIMEOUT
    elif not packet.candidate_match:
        recommendation, reason = LEAD_REVIEW, STALE_CANDIDATE
    elif (
        packet.worker_report == PASS
        and packet.assessment_status == EVALUATED
        and packet.criterion_labels
        and all(label == CONFIRMED for label in packet.criterion_labels)
    ):
        recommendation, reason = REVIEW_READY, EVIDENCE_READY_AT_LOCAL_STAGE
    elif (
        packet.worker_report == PASS
        and packet.assessment_status == EVALUATED
        and any(label == INSUFFICIENT for label in packet.criterion_labels)
        and packet.budget_remaining
    ):
        recommendation, reason = CONTINUATION_ELIGIBLE, LOCAL_EVIDENCE_GAP_WITHIN_PROPOSED_BUDGET
    elif (
        packet.worker_report == BLOCKED
        and packet.assessment_status == EVALUATED
        and packet.repair_proposal_supported
        and packet.budget_remaining
    ):
        recommendation, reason = CONTINUATION_ELIGIBLE, SUPPORTED_LOCAL_REPAIR_PROPOSAL
    else:
        raise ValueError(f"uncovered packet combination for folder {packet.folder!r}")

    _assert_no_forbidden_route(recommendation, reason)
    return GateResult(
        folder=packet.folder,
        routing_recommendation=recommendation,
        routing_reason=reason,
        execution_authorized=False,
        grant_issued=False,
        review_ready_only=recommendation == REVIEW_READY,
        accepted=False,
        merged=False,
        deployed=False,
        authorized_for_production=False,
    )
