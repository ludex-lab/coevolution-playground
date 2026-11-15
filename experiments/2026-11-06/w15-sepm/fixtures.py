"""Synthetic task-plan fixtures for the Wave15 Soft2 SEPM day-sketch."""

from __future__ import annotations

from models import PlanEdge, PlanNode, TaskPlan


LINEAR_CHAIN = TaskPlan(
    nodes=(
        PlanNode("collect", "collect local observations"),
        PlanNode("draft", "draft a summary"),
        PlanNode("review", "review the summary"),
    ),
    edges=(
        PlanEdge("collect", "draft"),
        PlanEdge("draft", "review"),
    ),
)

DIAMOND = TaskPlan(
    nodes=(
        PlanNode("start", "open the task"),
        PlanNode("left", "prepare the left input"),
        PlanNode("right", "prepare the right input"),
        PlanNode("join", "combine both inputs"),
    ),
    edges=(
        PlanEdge("start", "left"),
        PlanEdge("start", "right"),
        PlanEdge("left", "join"),
        PlanEdge("right", "join"),
    ),
)

DISCONNECTED = TaskPlan(
    nodes=(
        PlanNode("alpha", "independent step alpha"),
        PlanNode("beta", "independent step beta"),
    ),
    edges=(),
)

EMPTY = TaskPlan(nodes=(), edges=())


def three_node_cycle() -> tuple[tuple[PlanNode, ...], tuple[PlanEdge, ...]]:
    """A cyclic graph used by tests; constructing TaskPlan must raise."""

    nodes = (
        PlanNode("a", "step a"),
        PlanNode("b", "step b"),
        PlanNode("c", "step c"),
    )
    edges = (
        PlanEdge("a", "b"),
        PlanEdge("b", "c"),
        PlanEdge("c", "a"),
    )
    return nodes, edges


def two_node_cycle() -> tuple[tuple[PlanNode, ...], tuple[PlanEdge, ...]]:
    nodes = (
        PlanNode("src", "step src"),
        PlanNode("dst", "step dst"),
    )
    edges = (
        PlanEdge("src", "dst"),
        PlanEdge("dst", "src"),
    )
    return nodes, edges
