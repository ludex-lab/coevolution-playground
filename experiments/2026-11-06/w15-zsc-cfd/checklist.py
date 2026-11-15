"""Store-free CFD method checklist (Wave15 Soft3 day-sketch).

Clean-room structured records for coordination-friendly definitions
(hand-crafted and meta-learned). This is a method cite, not a runnable
reproduction of ahayler/zsc-llm-agents or of arXiv 2611.06409 numbers.

Paper sentences below were quote-checked against the fetched arXiv HTML
text for 2611.06409. Enum member names and checklist field names are
code, not paper vocabulary, except where a value is itself a quoted
paper phrase (``hand-crafted``, ``meta-learned``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CfdOrigin(str, Enum):
    """How a CFD was produced. Values are the paper's own labels."""

    HAND_CRAFTED = "hand-crafted"
    META_LEARNED = "meta-learned"


# Verbatim sentences from arXiv 2611.06409 (quote-checked).
PAPER_QUOTES: dict[str, str] = {
    "zsc_setting": (
        "We study zero-shot coordination (ZSC), where independently "
        "developed agents must coordinate at test time."
    ),
    "propose_cfds": (
        "Towards this, we propose Coordination-friendly definitions (CFDs) "
        "as a principled approach for enabling robust coordination among "
        "LLM agents."
    ),
    "automatic_discovery": (
        "Finally, we show that coordination-friendly definitions can be "
        "discovered automatically, removing the need for manual engineering."
    ),
    "cfd_comprises": (
        "A CFD comprises a set of textual instructions that encode general "
        "coordination principles used to guide agent behaviour."
    ),
    "independent_developers": (
        "We assume that independent developers can agree on a shared CFD "
        "to facilitate coordination among their agents."
    ),
    "handcrafted_test": (
        "An action/policy is not coordination-friendly if it satisfies any "
        "of the following:"
    ),
    "arbitrary_conventions": (
        "It assumes the existence of arbitrary conventions."
    ),
    "otherwise_friendly": (
        "Otherwise, the action/policy is coordination-friendly."
    ),
    "metalearned_prefer": (
        "Prefer actions that would still be reasonable under several "
        "plausible partner interpretations of the shared observation, and "
        "avoid actions that are good only if a partner infers one specific "
        "unstated rationale."
    ),
    "limitations": (
        "Both the hand-crafted and meta-learned coordination-friendly "
        "definitions remain relatively simple and do not apply to every "
        "coordination challenge."
    ),
}


@dataclass(frozen=True)
class ChecklistItem:
    """One required check in the method checklist."""

    item_id: str
    prompt: str
    cites: tuple[str, ...]


CHECKLIST_ITEMS: tuple[ChecklistItem, ...] = (
    ChecklistItem(
        "state_zsc_setting",
        "State that independently developed agents must coordinate at test time.",
        ("zsc_setting",),
    ),
    ChecklistItem(
        "give_shared_cfd",
        "Give a shared CFD: textual instructions that encode general coordination principles.",
        ("cfd_comprises", "propose_cfds", "independent_developers"),
    ),
    ChecklistItem(
        "mark_origin",
        "Mark whether the CFD is hand-crafted or meta-learned.",
        ("automatic_discovery", "limitations"),
    ),
    ChecklistItem(
        "handcrafted_reject_arbitrary_conventions",
        "If hand-crafted, reject actions or policies that assume arbitrary conventions.",
        ("handcrafted_test", "arbitrary_conventions", "otherwise_friendly"),
    ),
    ChecklistItem(
        "metalearned_multiple_interpretations",
        "If meta-learned, prefer actions reasonable under several plausible partner interpretations.",
        ("metalearned_prefer",),
    ),
    ChecklistItem(
        "not_a_reproduction",
        "Do not treat the record as a runnable reproduction of paper results.",
        ("limitations",),
    ),
)


@dataclass(frozen=True)
class CfdRecord:
    """A synthetic CFD record offered to an independently developed partner."""

    name: str
    origin: CfdOrigin
    instructions: str
    rejects_arbitrary_conventions: bool
    prefers_multiple_partner_interpretations: bool
    claims_runnable_reproduction: bool = False
    uses_docker: bool = False
    uses_openrouter: bool = False


@dataclass(frozen=True)
class ChecklistResult:
    holds: bool
    missing: tuple[str, ...]


def apply_checklist(record: CfdRecord) -> ChecklistResult:
    """Return whether the record satisfies the method-checklist shape."""

    missing: list[str] = []
    if not record.name.strip():
        missing.append("state_zsc_setting")
    if not record.instructions.strip():
        missing.append("give_shared_cfd")
    if record.origin not in (CfdOrigin.HAND_CRAFTED, CfdOrigin.META_LEARNED):
        missing.append("mark_origin")
    if record.origin is CfdOrigin.HAND_CRAFTED:
        if not record.rejects_arbitrary_conventions:
            missing.append("handcrafted_reject_arbitrary_conventions")
    if record.origin is CfdOrigin.META_LEARNED:
        if not record.prefers_multiple_partner_interpretations:
            missing.append("metalearned_multiple_interpretations")
    if (
        record.claims_runnable_reproduction
        or record.uses_docker
        or record.uses_openrouter
    ):
        missing.append("not_a_reproduction")
    return ChecklistResult(holds=not missing, missing=tuple(missing))
