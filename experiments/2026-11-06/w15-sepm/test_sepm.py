"""Stdlib tests for the Wave15 Soft2 store-free EvidenceTier + DAG sketch."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from fixtures import (
    DIAMOND,
    DISCONNECTED,
    EMPTY,
    LINEAR_CHAIN,
    three_node_cycle,
    two_node_cycle,
)
from models import (
    PAPER_AUTHORITY_ORDER,
    PAPER_TO_CODE_DESCENDING,
    EvidenceTier,
    PlanEdge,
    PlanNode,
    TaskPlan,
)


SKETCH_DIR = Path(__file__).resolve().parent
IMPLEMENTATION_MODULES = ("models.py", "fixtures.py")


class TestEvidenceTierOrder(unittest.TestCase):
    def test_numeric_order_is_ascending_authority(self):
        self.assertEqual(EvidenceTier.AGENT_INFERENCE, 1)
        self.assertEqual(EvidenceTier.VERIFIED_ARTIFACT, 2)
        self.assertEqual(EvidenceTier.TOOL_OBSERVATION, 3)
        self.assertEqual(EvidenceTier.AUTHORITATIVE_STATE, 4)
        self.assertLess(EvidenceTier.AGENT_INFERENCE, EvidenceTier.VERIFIED_ARTIFACT)
        self.assertLess(EvidenceTier.VERIFIED_ARTIFACT, EvidenceTier.TOOL_OBSERVATION)
        self.assertLess(EvidenceTier.TOOL_OBSERVATION, EvidenceTier.AUTHORITATIVE_STATE)

    def test_paper_prose_maps_onto_code_identifiers(self):
        self.assertEqual(
            PAPER_AUTHORITY_ORDER,
            (
                "The authority order is environment or official state, "
                "tool observation, verified artifact, and agent inference."
            ),
        )
        names = [tier.name for _, tier in PAPER_TO_CODE_DESCENDING]
        values = [int(tier) for _, tier in PAPER_TO_CODE_DESCENDING]
        self.assertEqual(
            names,
            [
                "AUTHORITATIVE_STATE",
                "TOOL_OBSERVATION",
                "VERIFIED_ARTIFACT",
                "AGENT_INFERENCE",
            ],
        )
        self.assertEqual(values, [4, 3, 2, 1])
        phrases = [phrase for phrase, _ in PAPER_TO_CODE_DESCENDING]
        for phrase in phrases:
            self.assertIn(phrase, PAPER_AUTHORITY_ORDER)


class TestDagCycleRejection(unittest.TestCase):
    def test_three_node_cycle_raises_exact_message(self):
        nodes, edges = three_node_cycle()
        with self.assertRaises(ValueError) as ctx:
            TaskPlan(nodes=nodes, edges=edges)
        self.assertEqual(str(ctx.exception), "dependency graph must be acyclic")

    def test_two_node_cycle_raises_exact_message(self):
        nodes, edges = two_node_cycle()
        with self.assertRaises(ValueError) as ctx:
            TaskPlan(nodes=nodes, edges=edges)
        self.assertEqual(str(ctx.exception), "dependency graph must be acyclic")


class TestSyntheticPlanFixtures(unittest.TestCase):
    def test_linear_chain_is_accepted(self):
        self.assertEqual(len(LINEAR_CHAIN.nodes), 3)
        self.assertEqual(len(LINEAR_CHAIN.edges), 2)
        self.assertEqual(
            [node.node_id for node in LINEAR_CHAIN.nodes],
            ["collect", "draft", "review"],
        )

    def test_diamond_is_accepted(self):
        self.assertEqual(len(DIAMOND.nodes), 4)
        self.assertEqual(len(DIAMOND.edges), 4)
        ids = {node.node_id for node in DIAMOND.nodes}
        self.assertEqual(ids, {"start", "left", "right", "join"})

    def test_disconnected_and_empty_plans_are_accepted(self):
        self.assertEqual(len(DISCONNECTED.nodes), 2)
        self.assertEqual(DISCONNECTED.edges, ())
        self.assertEqual(EMPTY.nodes, ())
        self.assertEqual(EMPTY.edges, ())

    def test_unknown_endpoint_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            TaskPlan(
                nodes=(PlanNode("only", "solo step"),),
                edges=(PlanEdge("only", "missing"),),
            )
        self.assertIn("unknown nodes", str(ctx.exception))


class TestNoStoreSurface(unittest.TestCase):
    def test_implementation_modules_do_not_import_forbidden_hosts(self):
        forbidden_roots = {
            "sqlite3",
            "pydantic",
            "autogen",
            "dylan",
            "requests",
            "httpx",
            "urllib",
            "socket",
        }
        for name in IMPLEMENTATION_MODULES:
            src = (SKETCH_DIR / name).read_text(encoding="utf-8")
            imported: set[str] = set()
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            overlap = imported & forbidden_roots
            self.assertFalse(overlap, msg=f"{name} imported {sorted(overlap)}")
            self.assertNotIn("SQLiteStore", src)
