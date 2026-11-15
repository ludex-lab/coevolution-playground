"""Brigade claim-fence refuse sketch (fleet_hub_claims @ pin; no hub/SQLite)."""

from __future__ import annotations

from dataclasses import dataclass

RETIRED_HOLDER_HORIZON_SECONDS = 7 * 86400


@dataclass(frozen=True, slots=True)
class Claim:
    target: str
    holder: str
    generation: int


@dataclass(frozen=True, slots=True)
class RetiredHolder:
    target: str
    node: str
    holder: str
    generation: int
    retired_at: float


@dataclass(frozen=True, slots=True)
class FenceRefusal:
    ok: bool
    reason: str = ""


def refuse_stale_fence(
    *,
    action: str,
    expected_generation: int | None,
    fence_generation: int,
    target: str,
    node: str,
    holder: str | None,
    retired: frozenset[RetiredHolder],
    now: float,
    live: Claim | None = None,
    live_node: str | None = None,
    release_holder_scope: bool = False,
) -> FenceRefusal:
    """Refuse stale-generation / stale-holder (mirrors fleet_hub_claims._stale @ pin)."""
    cutoff, retired_gen = now - RETIRED_HOLDER_HORIZON_SECONDS, 0
    if holder and (action != "release" or release_holder_scope):
        for row in retired:
            if (row.target, row.node, row.holder) != (target, node, holder):
                continue
            if row.generation > fence_generation:
                raise ValueError("retired generation exceeds fence")
            if row.retired_at >= cutoff:
                retired_gen = row.generation
                break
    retry = (
        action == "acquire"
        and live is not None
        and live_node == node
        and live.holder == holder
        and expected_generation == fence_generation - 1
        and expected_generation is not None
        and expected_generation >= retired_gen
    )
    if expected_generation is not None and expected_generation != fence_generation and not retry:
        return FenceRefusal(False, "stale-generation")
    if expected_generation is None and retired_gen:
        return FenceRefusal(False, "stale-holder")
    return FenceRefusal(True)
