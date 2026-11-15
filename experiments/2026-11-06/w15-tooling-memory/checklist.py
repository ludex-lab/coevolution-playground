"""Store-free tooling-memory principle checklist (Wave15 Soft4 day-sketch).

Clean-room structured records for the design principles in
apache/tooling-memory docs/durable-memory-for-disposable-agents.md
at pin 4662cc2d0f76ceeb95bd0614e29dd3ce914fefba. This is a method cite,
not a port of the upstream SQLite index/ledger/metering or MCP surface.

Paper sentences below were quote-checked against that design paper at
the pin. Enum member names and checklist field names are code, not
paper vocabulary, except where a value is itself a quoted paper phrase.
"""

from __future__ import annotations

from dataclasses import dataclass


PAPER_QUOTES: dict[str, str] = {
    'data_outlives_title': 'Data outlives tooling.',
    'data_outlives_formats': 'The record and historian have documented, text-readable formats.',
    'data_outlives_rebuild': (
        'Together they preserve the state from which indexes, ledgers, '
        'and dashboards can be rebuilt.'
    ),
    'plain_text_provenance': (
        'So everything of lasting value lives in plain-text data with '
        'provenance.'
    ),
    'agents_disposable_title': 'Agents are disposable.',
    'agents_write_before_end': (
        'Anything worth keeping is written to shared memory before the '
        'agent ends.'
    ),
    'ownership_title': 'Ownership limits conflict.',
    'ownership_owners': 'Domains, files, and tasks have owners.',
    'ownership_claims': 'Claims expire, and delayed actions from old claims are rejected.',
    'lease_expires': 'A claim expires unless renewed',
    'judgment_title': 'Judgment is written down.',
    'judgment_files': 'Values, strategy, and quality bars are versioned files agents read.',
    'provenance_title': (
        'Every write carries provenance, and trust does not pass along on '
        'its own.'
    ),
    'human_legible_title': 'Everything stays human-legible.',
    'human_legible_continuity': 'People are the only continuity at decade scale.',
    'write_screened': (
        'Every write is appended to the historian, then screened for '
        'secrets, credentials, and whatever else L0 names.'
    ),
    'quarantined': (
        'It is quarantined: raised to the highest classification, '
        'readable only by the security role named in policy, and excluded '
        'from everything downstream.'
    ),
}


@dataclass(frozen=True)
class ChecklistItem:
    """One required check in the principle checklist."""

    item_id: str
    prompt: str
    cites: tuple[str, ...]


CHECKLIST_ITEMS: tuple[ChecklistItem, ...] = (
    ChecklistItem(
        "data_outlives_tooling",
        "Keep lasting value in documented, text-readable records that outlive tooling.",
        ("data_outlives_title", "data_outlives_formats", "data_outlives_rebuild", "plain_text_provenance"),
    ),
    ChecklistItem(
        "agents_disposable",
        "Treat agents as disposable and write anything worth keeping before the agent ends.",
        ("agents_disposable_title", "agents_write_before_end"),
    ),
    ChecklistItem(
        "ownership_leases",
        "Give domains, files, and tasks owners, and let claims expire.",
        ("ownership_title", "ownership_owners", "ownership_claims", "lease_expires"),
    ),
    ChecklistItem(
        "write_carries_provenance",
        "Record provenance on every write; trust does not pass along on its own.",
        ("provenance_title",),
    ),
    ChecklistItem(
        "quarantine_failed_screens",
        "Screen writes and quarantine those that fail, hidden from everything downstream.",
        ("write_screened", "quarantined"),
    ),
    ChecklistItem(
        "judgment_written_down",
        "Write values, strategy, and quality bars as versioned files agents read.",
        ("judgment_title", "judgment_files"),
    ),
    ChecklistItem(
        "human_legible",
        "Keep records human-legible; people are the continuity at decade scale.",
        ("human_legible_title", "human_legible_continuity"),
    ),
    ChecklistItem(
        "not_a_port",
        "Do not treat the record as a port of the upstream SQLite or MCP stack.",
        ("plain_text_provenance",),
    ),
)


@dataclass(frozen=True)
class PrincipleRecord:
    """A synthetic record of whether a sketch honours the cited principles."""

    name: str
    data_outlives_tooling: bool
    agents_disposable: bool
    ownership_limits_conflict: bool
    writes_carry_provenance: bool
    quarantines_failed_screens: bool
    judgment_written_down: bool
    human_legible: bool
    claims_storage_or_mcp_port: bool = False
    uses_sqlite: bool = False
    uses_mcp: bool = False


@dataclass(frozen=True)
class ChecklistResult:
    holds: bool
    missing: tuple[str, ...]


def apply_checklist(record: PrincipleRecord) -> ChecklistResult:
    """Return whether the record satisfies the principle-checklist shape."""

    missing: list[str] = []
    if not record.name.strip() or not record.data_outlives_tooling:
        missing.append("data_outlives_tooling")
    if not record.agents_disposable:
        missing.append("agents_disposable")
    if not record.ownership_limits_conflict:
        missing.append("ownership_leases")
    if not record.writes_carry_provenance:
        missing.append("write_carries_provenance")
    if not record.quarantines_failed_screens:
        missing.append("quarantine_failed_screens")
    if not record.judgment_written_down:
        missing.append("judgment_written_down")
    if not record.human_legible:
        missing.append("human_legible")
    if (
        record.claims_storage_or_mcp_port
        or record.uses_sqlite
        or record.uses_mcp
    ):
        missing.append("not_a_port")
    return ChecklistResult(holds=not missing, missing=tuple(missing))
