"""Synthetic principle records for the Wave15 Soft4 method checklist."""

from __future__ import annotations

from checklist import PAPER_QUOTES, PrincipleRecord


COMPLETE = PrincipleRecord(
    name="synthetic-durable-memory-principles",
    data_outlives_tooling=True,
    agents_disposable=True,
    ownership_limits_conflict=True,
    writes_carry_provenance=True,
    quarantines_failed_screens=True,
    judgment_written_down=True,
    human_legible=True,
)

INCOMPLETE_BLANK = PrincipleRecord(
    name="",
    data_outlives_tooling=False,
    agents_disposable=True,
    ownership_limits_conflict=True,
    writes_carry_provenance=True,
    quarantines_failed_screens=True,
    judgment_written_down=True,
    human_legible=True,
)

INCOMPLETE_NO_PROVENANCE = PrincipleRecord(
    name="missing-provenance-flag",
    data_outlives_tooling=True,
    agents_disposable=True,
    ownership_limits_conflict=True,
    writes_carry_provenance=False,
    quarantines_failed_screens=True,
    judgment_written_down=True,
    human_legible=True,
)

INCOMPLETE_NO_QUARANTINE = PrincipleRecord(
    name="missing-quarantine-flag",
    data_outlives_tooling=True,
    agents_disposable=True,
    ownership_limits_conflict=True,
    writes_carry_provenance=True,
    quarantines_failed_screens=False,
    judgment_written_down=True,
    human_legible=True,
)

FORBIDDEN_SQLITE_MCP = PrincipleRecord(
    name="would-port-sqlite-mcp",
    data_outlives_tooling=True,
    agents_disposable=True,
    ownership_limits_conflict=True,
    writes_carry_provenance=True,
    quarantines_failed_screens=True,
    judgment_written_down=True,
    human_legible=True,
    claims_storage_or_mcp_port=True,
    uses_sqlite=True,
    uses_mcp=True,
)

# Quote-checked instruction text used only as documentation on fixtures.
ANNOTATION = (
    f"{PAPER_QUOTES['agents_write_before_end']} "
    f"{PAPER_QUOTES['provenance_title']} "
    f"{PAPER_QUOTES['quarantined']}"
)
