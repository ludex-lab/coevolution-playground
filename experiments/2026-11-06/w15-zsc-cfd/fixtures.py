"""Synthetic CFD records for the Wave15 Soft3 method checklist."""

from __future__ import annotations

from checklist import CfdOrigin, CfdRecord, PAPER_QUOTES


HANDCRAFTED_COMPLETE = CfdRecord(
    name="synthetic-hand-crafted-cfd",
    origin=CfdOrigin.HAND_CRAFTED,
    instructions=(
        f"{PAPER_QUOTES['handcrafted_test']} "
        f"{PAPER_QUOTES['arbitrary_conventions']} "
        f"{PAPER_QUOTES['otherwise_friendly']}"
    ),
    rejects_arbitrary_conventions=True,
    prefers_multiple_partner_interpretations=False,
)

METALEARNED_COMPLETE = CfdRecord(
    name="synthetic-meta-learned-cfd",
    origin=CfdOrigin.META_LEARNED,
    instructions=PAPER_QUOTES["metalearned_prefer"],
    rejects_arbitrary_conventions=False,
    prefers_multiple_partner_interpretations=True,
)

INCOMPLETE_BLANK = CfdRecord(
    name="",
    origin=CfdOrigin.HAND_CRAFTED,
    instructions="",
    rejects_arbitrary_conventions=True,
    prefers_multiple_partner_interpretations=False,
)

INCOMPLETE_HANDCRAFTED = CfdRecord(
    name="missing-arbitrary-convention-flag",
    origin=CfdOrigin.HAND_CRAFTED,
    instructions=PAPER_QUOTES["cfd_comprises"],
    rejects_arbitrary_conventions=False,
    prefers_multiple_partner_interpretations=False,
)

FORBIDDEN_REPRODUCTION_CLAIM = CfdRecord(
    name="claims-paper-numbers",
    origin=CfdOrigin.META_LEARNED,
    instructions=PAPER_QUOTES["metalearned_prefer"],
    rejects_arbitrary_conventions=False,
    prefers_multiple_partner_interpretations=True,
    claims_runnable_reproduction=True,
)

FORBIDDEN_DOCKER = CfdRecord(
    name="would-need-docker",
    origin=CfdOrigin.HAND_CRAFTED,
    instructions=PAPER_QUOTES["cfd_comprises"],
    rejects_arbitrary_conventions=True,
    prefers_multiple_partner_interpretations=False,
    uses_docker=True,
    uses_openrouter=True,
)
