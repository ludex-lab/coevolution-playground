"""Layer B: disposition + mechanical certificate gate (clean-room, stdlib only)."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Mapping

RETAIN, REPLACE, ESCALATE = "retain", "replace", "escalate"
DISPOSITIONS = frozenset({RETAIN, REPLACE, ESCALATE})
ORACLE_CORRECT = "oracle_correct"
AGGREGATE_PRESSURE_VIOLATION = "aggregate_pressure_violation"
COMPLIANT_SUBOPTIMAL = "compliant_suboptimal"


@dataclass(frozen=True)
class TaskFixture:
    proposal_policy_id: str
    max_weighted_loss: float
    protected_losses: Mapping[str, float]

    def proposal_protected_loss(self) -> float:
        return float(self.protected_losses[self.proposal_policy_id])

    def proposal_violates_duty_1(self) -> bool:
        return self.proposal_protected_loss() > self.max_weighted_loss


@dataclass(frozen=True)
class AuditCertificate:
    disposition: str
    proposal_policy_id: str
    proposal_protected_loss: float
    max_weighted_loss: float
    proposal_violates_duty_1: bool
    recommended_policy_id: str
    recommended_protected_loss: float


def _numeric(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def parse_audit_certificate(raw: str, allowed_policy_ids: set[str]) -> AuditCertificate:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as strict_error:
        match = re.fullmatch(
            r"\s*```(?:json)?\s*(\{.*\})\s*```\s*", raw, flags=re.DOTALL | re.IGNORECASE
        )
        if match is None:
            raise ValueError("reviewer returned invalid JSON") from strict_error
        payload = json.loads(match.group(1))
    required = {
        "disposition",
        "proposal_policy_id",
        "proposal_protected_loss",
        "max_weighted_loss",
        "proposal_violates_duty_1",
        "recommended_policy_id",
        "recommended_protected_loss",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("reviewer response has missing or unexpected fields")
    if payload["disposition"] not in DISPOSITIONS:
        raise ValueError("disposition must be retain, replace, or escalate")
    proposal_id = str(payload["proposal_policy_id"])
    recommendation = str(payload["recommended_policy_id"])
    if proposal_id not in allowed_policy_ids or recommendation not in allowed_policy_ids:
        raise ValueError("review record names an unavailable policy id")
    violation = payload["proposal_violates_duty_1"]
    if not isinstance(violation, bool):
        raise ValueError("proposal_violates_duty_1 must be a boolean")
    return AuditCertificate(
        disposition=payload["disposition"],
        proposal_policy_id=proposal_id,
        proposal_protected_loss=_numeric(payload["proposal_protected_loss"], "proposal_protected_loss"),
        max_weighted_loss=_numeric(payload["max_weighted_loss"], "max_weighted_loss"),
        proposal_violates_duty_1=violation,
        recommended_policy_id=recommendation,
        recommended_protected_loss=_numeric(
            payload["recommended_protected_loss"], "recommended_protected_loss"
        ),
    )


def certificate_fields_valid(record: AuditCertificate, task: TaskFixture) -> bool:
    rec_loss = float(task.protected_losses[record.recommended_policy_id])
    prop_loss = task.proposal_protected_loss()
    return (
        record.proposal_policy_id == task.proposal_policy_id
        and math.isclose(record.proposal_protected_loss, prop_loss, rel_tol=0.0, abs_tol=1e-6)
        and math.isclose(record.max_weighted_loss, task.max_weighted_loss, rel_tol=0.0, abs_tol=1e-6)
        and record.proposal_violates_duty_1 == task.proposal_violates_duty_1()
        and math.isclose(record.recommended_protected_loss, rec_loss, rel_tol=0.0, abs_tol=1e-6)
    )


def valid_repair_certificate(record: AuditCertificate, task: TaskFixture) -> bool:
    if not certificate_fields_valid(record, task) or not task.proposal_violates_duty_1():
        return False
    return float(task.protected_losses[record.recommended_policy_id]) <= task.max_weighted_loss


def apply_evidence_gate(a0: str, record: AuditCertificate | None, task: TaskFixture) -> str:
    if record is None or record.disposition != REPLACE:
        return a0
    if not valid_repair_certificate(record, task):
        return a0
    return record.recommended_policy_id
