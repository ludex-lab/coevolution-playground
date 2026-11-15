"""Store-free EvidenceTier and task-plan DAG (Wave15 Soft2 day-sketch).

Clean-room port of ideas from cookieApril/SEPM ``src/sepm/models.py`` only:
``EvidenceTier``, ``PlanNode``, ``PlanEdge``, and ``TaskPlan``.

This sketch has no store. It does not import sqlite, pydantic, or any
upstream storage, adapter, host, or evaluation module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class EvidenceTier(IntEnum):
    """Higher numeric values mean greater authority.

    The paper states: "The authority order is environment or official
    state, tool observation, verified artifact, and agent inference."
    Those phrases are paper vocabulary. The identifiers below are code
    names for the same descending list, not words the paper uses.
    """

    AGENT_INFERENCE = 1
    VERIFIED_ARTIFACT = 2
    TOOL_OBSERVATION = 3
    AUTHORITATIVE_STATE = 4


# Paper prose (arXiv 2610.14515). Cite this sentence; do not treat the
# EvidenceTier member names as paper vocabulary.
PAPER_AUTHORITY_ORDER = (
    "The authority order is environment or official state, tool observation, "
    "verified artifact, and agent inference."
)

# Highest authority first, matching the paper sentence. Each pair is
# (paper phrase, code identifier).
PAPER_TO_CODE_DESCENDING = (
    ("environment or official state", EvidenceTier.AUTHORITATIVE_STATE),
    ("tool observation", EvidenceTier.TOOL_OBSERVATION),
    ("verified artifact", EvidenceTier.VERIFIED_ARTIFACT),
    ("agent inference", EvidenceTier.AGENT_INFERENCE),
)


@dataclass(frozen=True)
class PlanNode:
    """One action node in a task-plan graph."""

    node_id: str
    action: str


@dataclass(frozen=True)
class PlanEdge:
    """Directed dependency: ``source`` must finish before ``target`` starts."""

    source: str
    target: str


def _reject_cycles(ids: set[str], edges: tuple[PlanEdge, ...]) -> None:
    """Kahn topological walk. A leftover node means the graph has a cycle."""

    pairs = {(edge.source, edge.target) for edge in edges}
    if len(pairs) != len(edges):
        raise ValueError("dependency graph cannot contain duplicate edges")

    outgoing: dict[str, list[str]] = {node: [] for node in ids}
    incoming: dict[str, int] = {node: 0 for node in ids}
    for source, target in pairs:
        outgoing[source].append(target)
        incoming[target] += 1

    ready = [node for node, count in incoming.items() if count == 0]
    visited = 0
    while ready:
        node = ready.pop()
        visited += 1
        for target in outgoing[node]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    if visited != len(ids):
        raise ValueError("dependency graph must be acyclic")


@dataclass(frozen=True)
class TaskPlan:
    """Plan graph of action nodes and dependency edges.

    Construction validates uniqueness, endpoint membership, the absence
    of self-loops, and acyclicity. A cycle raises
    ``ValueError("dependency graph must be acyclic")``.
    """

    nodes: tuple[PlanNode, ...]
    edges: tuple[PlanEdge, ...]

    def __post_init__(self) -> None:
        ids = [node.node_id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("Plan graph node_id values must be unique")
        if any(edge.source == edge.target for edge in self.edges):
            raise ValueError("Plan graph cannot contain self-loops")
        known = set(ids)
        missing = {
            endpoint
            for edge in self.edges
            for endpoint in (edge.source, edge.target)
        } - known
        if missing:
            raise ValueError(
                f"Plan edges reference unknown nodes: {sorted(missing)}"
            )
        _reject_cycles(known, self.edges)
