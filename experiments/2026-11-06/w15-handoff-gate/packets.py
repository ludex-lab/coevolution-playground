"""Six synthetic packets labeled by upstream example folder titles.

Folder titles are labels (complete / premature / blocked / prohibited /
unavailable / stale paraphrases), not a six-value routing enum.
Routing values come from apply_gate, not from looking up the folder name.
"""

from gate import BLOCKED, EVALUATED, INSUFFICIENT, PASS, Packet

SYNTHETIC_PACKETS = (
    Packet(
        folder="01-complete-evidence",
        worker_report=PASS,
        assessment_status=EVALUATED,
        prohibited_operation=False,
        candidate_match=True,
        evaluator_timeout=False,
        criterion_labels=("CONFIRMED", "CONFIRMED"),
        repair_proposal_supported=False,
    ),
    Packet(
        folder="02-premature-pass",
        worker_report=PASS,
        assessment_status=EVALUATED,
        prohibited_operation=False,
        candidate_match=True,
        evaluator_timeout=False,
        criterion_labels=(INSUFFICIENT, INSUFFICIENT),
        repair_proposal_supported=False,
    ),
    Packet(
        folder="03-local-blocker",
        worker_report=BLOCKED,
        assessment_status=EVALUATED,
        prohibited_operation=False,
        candidate_match=True,
        evaluator_timeout=False,
        criterion_labels=("CONTRADICTED",),
        repair_proposal_supported=True,
    ),
    Packet(
        folder="04-out-of-scope",
        worker_report=BLOCKED,
        assessment_status="NOT_EVALUATED",
        prohibited_operation=True,
        candidate_match=True,
        evaluator_timeout=False,
        criterion_labels=(),
        repair_proposal_supported=False,
    ),
    Packet(
        folder="05-evaluator-unavailable",
        worker_report=PASS,
        assessment_status="NOT_EVALUATED",
        prohibited_operation=False,
        candidate_match=True,
        evaluator_timeout=True,
        criterion_labels=(),
        repair_proposal_supported=False,
    ),
    Packet(
        folder="06-stale-evidence",
        worker_report=PASS,
        assessment_status="NOT_EVALUATED",
        prohibited_operation=False,
        candidate_match=False,
        evaluator_timeout=False,
        criterion_labels=(),
        repair_proposal_supported=False,
    ),
)

EXPECTED_ROUTES = {
    "01-complete-evidence": ("REVIEW_READY", "EVIDENCE_READY_AT_LOCAL_STAGE"),
    "02-premature-pass": (
        "CONTINUATION_ELIGIBLE",
        "LOCAL_EVIDENCE_GAP_WITHIN_PROPOSED_BUDGET",
    ),
    "03-local-blocker": (
        "CONTINUATION_ELIGIBLE",
        "SUPPORTED_LOCAL_REPAIR_PROPOSAL",
    ),
    "04-out-of-scope": ("STOP", "PROHIBITED_OPERATION"),
    "05-evaluator-unavailable": ("LEAD_REVIEW", "EVALUATOR_TIMEOUT"),
    "06-stale-evidence": ("LEAD_REVIEW", "STALE_CANDIDATE"),
}
