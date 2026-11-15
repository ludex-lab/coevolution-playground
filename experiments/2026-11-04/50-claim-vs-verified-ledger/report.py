"""Minimal claim vs host-verified report ledger (Team OS sketch; not upstream swrm)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional, Union


VerifyRc = Optional[int]


def coerce_verify_rc(value: Any) -> VerifyRc:
    """Accept int exit codes only; reject bool and non-int (JSON footguns)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def host_verified_pass_from_verify_rc(verify_rc: Union[int, bool, None]) -> Optional[bool]:
    if verify_rc is None or isinstance(verify_rc, bool):
        return None
    return verify_rc == 0


@dataclass
class AgentRunReport:
    report_id: str
    exec_pass: bool
    exec_pass_reason: str = ""
    verify_rc: Optional[int] = None
    accepted: bool = False
    accepted_reason: str = ""
    rework_of: Optional[str] = None
    surface_status: str = field(default="", init=False)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("surface_status", None)
        data["host_verified_pass"] = host_verified_pass_from_verify_rc(self.verify_rc)
        return data


def adjust_status_for_verify(report: AgentRunReport) -> str:
    """Derive outward status without mutating self-claim or verify facts."""
    host_ok = host_verified_pass_from_verify_rc(report.verify_rc)

    if report.verify_rc is None:
        base = "unverified_claim_pass" if report.exec_pass else "unverified_claim_fail"
    elif report.exec_pass is host_ok:
        base = "aligned_pass" if host_ok else "aligned_fail"
    elif host_ok:
        base = "verify_pass_self_fail"
    else:
        base = "contradicted"

    if report.accepted:
        return f"{base}_accepted"
    return base


def report_from_mapping(data: Mapping[str, Any]) -> AgentRunReport:
    return AgentRunReport(
        report_id=str(data["report_id"]),
        exec_pass=bool(data["exec_pass"]),
        exec_pass_reason=str(data.get("exec_pass_reason", "")),
        verify_rc=coerce_verify_rc(data.get("verify_rc")),
        accepted=bool(data.get("accepted", False)),
        accepted_reason=str(data.get("accepted_reason", "")),
        rework_of=data.get("rework_of"),
    )


def finalize_report(report: AgentRunReport) -> AgentRunReport:
    report.surface_status = adjust_status_for_verify(report)
    return report
