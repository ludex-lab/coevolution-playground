"""Offline unit tests for a synthetic sketch, not empirical paper verification."""

import ast
from dataclasses import FrozenInstanceError
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest

from containment import AppendOnlyError, BlockedAction, ProvenanceDAG
from fixtures import PAPER_QUOTES, synthetic_dag

HERE = Path(__file__).resolve().parent


class ContainmentTests(unittest.TestCase):
    def setUp(self):
        self.dag = synthetic_dag()

    def test_every_descendant_and_alerted_vertex_frozen(self):
        expected = {"bad-v1", "reader", "memo-v1", "next-turn",
                    "desk-command", "later-command"}
        self.assertEqual(self.dag.descendants("bad-v1"), expected)
        self.assertEqual(self.dag.quarantine("bad-v1"), expected)
        self.assertEqual(self.dag.tainted, expected)

    def test_non_descendant_healthy_work_not_frozen(self):
        self.dag.quarantine("bad-v1")
        healthy = {"planner", "automation", "lobby-command"}
        self.assertFalse(healthy & self.dag.frozen)
        self.assertEqual(self.dag.actuate("lobby-command"), "lobby-command")

    def test_pending_actuations_on_tainted_branches_blocked(self):
        self.dag.quarantine("bad-v1")
        for effect in ("desk-command", "later-command"):
            with self.subTest(effect=effect), self.assertRaises(BlockedAction):
                self.dag.actuate(effect)
        self.assertFalse(self.dag.committed)

    def test_gate_denies_taint_even_before_explicit_quarantine(self):
        self.dag.taint("bad-v1")
        with self.assertRaises(BlockedAction):
            self.dag.actuate("desk-command")

    def test_backward_roots_are_candidates_not_single_cause(self):
        self.assertEqual(self.dag.roots("later-command"),
                         {"planner", "bad-v1", "reader", "memo-v1",
                          "next-turn", "later-command"})
        self.assertNotIn("automation", self.dag.roots("later-command"))
        self.assertNotIn("desk-command", self.dag.roots("later-command"))

    def test_no_alert_does_not_mean_clearance(self):
        self.assertEqual(self.dag.taint(), frozenset())
        frozen = self.dag.quarantine("bad-v1")
        for _ in range(3):
            self.dag.taint(None)
            self.assertEqual(self.dag.quarantine(None), frozen)
        with self.assertRaises(BlockedAction):
            self.dag.actuate("later-command")

    def test_later_repaired_version_does_not_unfreeze_old_consumers(self):
        frozen = self.dag.quarantine("bad-v1")
        self.dag.add_node("repaired-v2", "artifact")
        self.dag.add_edge("repair-written", "planner", "repaired-v2")
        self.dag.add_edge("repair-consumed", "repaired-v2", "reader")
        self.assertEqual(self.dag.quarantine(), frozen)
        self.assertNotIn("repaired-v2", self.dag.tainted)
        self.assertIn("bad-v1", self.dag.nodes)
        with self.assertRaises(BlockedAction):
            self.dag.actuate("desk-command")
        self.assertFalse(hasattr(self.dag, "release"))

    def test_late_consumption_is_frozen_before_commit(self):
        self.dag.quarantine("bad-v1")
        self.dag.add_node("new-consumer")
        self.dag.add_node("new-effect", "effect")
        self.dag.add_edge("later-pending", "new-consumer", "new-effect")
        self.dag.add_edge("late-ingested-read", "bad-v1", "new-consumer")
        self.assertTrue({"new-consumer", "new-effect"} <= self.dag.frozen)
        with self.assertRaises(BlockedAction):
            self.dag.actuate("new-effect")

    def test_edge_deletion_and_rewrite_rejected_without_mutation(self):
        before = dict(self.dag.edges)
        for operation in (
            lambda: self.dag.delete_edge("already-read"),
            lambda: self.dag.delete_edge("unknown"),
            lambda: self.dag.rewrite_edge("already-read", "bad-v1", "automation"),
            lambda: self.dag.add_edge("already-read", "bad-v1", "automation"),
        ):
            with self.assertRaisesRegex(AppendOnlyError, "append-only"):
                operation()
            self.assertEqual(dict(self.dag.edges), before)

    def test_public_history_and_node_permissions_are_immutable(self):
        with self.assertRaises(TypeError):
            self.dag.edges["extra"] = self.dag.edges["already-read"]
        with self.assertRaises(FrozenInstanceError):
            self.dag.edges["already-read"].consumer = "automation"
        with self.assertRaises(TypeError):
            self.dag.nodes["reader"] = self.dag.nodes["planner"]
        with self.assertRaises(FrozenInstanceError):
            self.dag.nodes["reader"].permissions = frozenset({"extra"})
        with self.assertRaises(AppendOnlyError):
            self.dag.add_node("reader")
        with self.assertRaises(AppendOnlyError):
            self.dag.delete_node("reader")

    def test_cycle_missing_endpoint_and_bad_kind_rejected(self):
        before = dict(self.dag.edges)
        for args in (("cycle", "reader", "bad-v1"),
                     ("self", "reader", "reader"),
                     ("kind", "reader", "automation", "unknown")):
            with self.assertRaises(ValueError):
                self.dag.add_edge(*args)
        with self.assertRaises(KeyError):
            self.dag.add_edge("missing", "reader", "absent")
        self.assertEqual(dict(self.dag.edges), before)

    def test_authority_permissions_narrow_and_reject_broader_child(self):
        dag = ProvenanceDAG()
        dag.add_node("parent", permissions={"lamp:desk"})
        dag.add_node("child", permissions=set())
        dag.add_node("broad", permissions={"lamp:desk", "lamp:lobby"})
        dag.add_node("other", permissions={"lamp:desk"})
        dag.add_edge("ok", "parent", "child", "authority")
        self.assertLessEqual(dag.nodes["child"].permissions,
                             dag.nodes["parent"].permissions)
        with self.assertRaisesRegex(ValueError, "subset"):
            dag.add_edge("bad", "parent", "broad", "authority")
        with self.assertRaisesRegex(ValueError, "already has"):
            dag.add_edge("second-parent", "other", "child", "authority")
        self.assertEqual(set(dag.edges), {"ok"})

    def test_multiple_alerts_union_and_unknown_alert_rejected_without_clearance(self):
        first = self.dag.quarantine("bad-v1")
        with self.assertRaises(KeyError):
            self.dag.quarantine("unseen-source")
        self.assertEqual(self.dag.frozen, first)
        self.dag.quarantine("automation")
        self.assertTrue(first <= self.dag.frozen)
        with self.assertRaises(BlockedAction):
            self.dag.actuate("lobby-command")

    def test_past_commit_not_undone_and_repeated_commit_denied(self):
        self.dag.actuate("desk-command")
        self.dag.quarantine("bad-v1")
        self.assertIn("desk-command", self.dag.committed)
        with self.assertRaises(BlockedAction):
            self.dag.actuate("desk-command")
        self.dag.actuate("lobby-command")
        with self.assertRaises(BlockedAction):
            self.dag.actuate("lobby-command")
        with self.assertRaises(ValueError):
            self.dag.actuate("reader")


class EvidenceAndBoundaryTests(unittest.TestCase):
    def test_copied_sentences_match_checked_html_excerpts(self):
        evidence = json.loads((HERE / "paper_evidence.json").read_text())
        self.assertEqual(evidence["source"], "https://arxiv.org/html/2611.06727")
        self.assertEqual(tuple(q["text"] for q in evidence["quotes"]), PAPER_QUOTES)
        class Text(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts = []

            def handle_data(self, data):
                self.parts.append(data)

        parser = Text()
        parser.feed(" ".join(evidence["html_excerpts"]))
        fetched_text = " ".join("".join(parser.parts).split())
        for quote in PAPER_QUOTES:
            self.assertIn(quote, fetched_text)
            self.assertTrue(quote.isascii())
            self.assertTrue(quote.endswith("."))
        self.assertEqual(evidence["license"], "License: CC BY 4.0")
        # Portable offline check is against the small checked evidence record.
        # The full fetched HTML is intentionally not shipped with this sketch.
        digest = evidence["raw_html_sha256"]
        self.assertEqual(len(bytes.fromhex(digest)), hashlib.sha256().digest_size)
        self.assertIn("permanently holds every artifact version and pending effect",
                      evidence["anchors"])

    def test_ast_import_allowlist_and_network_llm_ban(self):
        banned = {"sqlite3", "nats", "docker", "openai", "anthropic", "requests",
                  "httpx", "urllib", "socket", "http", "aiohttp", "langgraph",
                  "langchain", "feishu"}
        allowed = {"containment.py": {"dataclasses", "types"},
                   "fixtures.py": {"containment"},
                   "test_containment.py": {"ast", "dataclasses", "hashlib", "json",
                                           "pathlib", "unittest", "containment", "fixtures", "html"}}
        for path in sorted(HERE.glob("*.py")):
            self.assertIn(path.name, allowed, "audit new Python files explicitly")
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    self.assertEqual(node.level, 0)
                    modules = [(node.module or "").split(".")[0]]
                for module in modules:
                    self.assertNotIn(module, banned)
                    self.assertIn(module, allowed[path.name])
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id,
                                     {"eval", "exec", "__import__", "compile"})

    def test_implementation_string_bans(self):
        forbidden = ("two-ledger", "curiosityexplorer/two-ledger-model",
                     "openrouter_api_key", "openai_api_key", "hmac-manifest",
                     "composition.py", "theta_v", "voting", "ensemble",
                     "more-agents-reliability", "docker-compose", "feishu", "dsh")
        for filename in ("containment.py", "fixtures.py"):
            source = (HERE / filename).read_text().lower()
            for token in forbidden:
                self.assertNotIn(token, source, (filename, token))


if __name__ == "__main__":
    unittest.main()
