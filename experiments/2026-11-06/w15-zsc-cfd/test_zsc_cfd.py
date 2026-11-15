"""Stdlib tests for the Wave15 Soft3 ZSC CFD method checklist."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from checklist import (
    CHECKLIST_ITEMS,
    PAPER_QUOTES,
    CfdOrigin,
    apply_checklist,
)
from fixtures import (
    FORBIDDEN_DOCKER,
    FORBIDDEN_REPRODUCTION_CLAIM,
    HANDCRAFTED_COMPLETE,
    INCOMPLETE_BLANK,
    INCOMPLETE_HANDCRAFTED,
    METALEARNED_COMPLETE,
)


SKETCH_DIR = Path(__file__).resolve().parent
IMPLEMENTATION_MODULES = ("checklist.py", "fixtures.py")


class TestPaperQuotes(unittest.TestCase):
    def test_quoted_sentences_match_checked_paper_text(self):
        expected = {
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
        self.assertEqual(PAPER_QUOTES, expected)

    def test_quotes_do_not_invent_strangers_or_figures(self):
        blob = " ".join(PAPER_QUOTES.values()).lower()
        self.assertNotIn("stranger", blob)
        self.assertNotIn("%", blob)
        self.assertNotIn("openrouter", blob)
        self.assertNotIn("docker", blob)


class TestChecklistShape(unittest.TestCase):
    def test_origins_are_the_paper_labels(self):
        self.assertEqual(CfdOrigin.HAND_CRAFTED.value, "hand-crafted")
        self.assertEqual(CfdOrigin.META_LEARNED.value, "meta-learned")
        self.assertEqual(
            {origin.value for origin in CfdOrigin},
            {"hand-crafted", "meta-learned"},
        )

    def test_checklist_items_cite_known_quotes(self):
        ids = [item.item_id for item in CHECKLIST_ITEMS]
        self.assertEqual(
            ids,
            [
                "state_zsc_setting",
                "give_shared_cfd",
                "mark_origin",
                "handcrafted_reject_arbitrary_conventions",
                "metalearned_multiple_interpretations",
                "not_a_reproduction",
            ],
        )
        for item in CHECKLIST_ITEMS:
            for key in item.cites:
                self.assertIn(key, PAPER_QUOTES)


class TestSyntheticRecords(unittest.TestCase):
    def test_complete_handcrafted_record_holds(self):
        result = apply_checklist(HANDCRAFTED_COMPLETE)
        self.assertTrue(result.holds)
        self.assertEqual(result.missing, ())

    def test_complete_metalearned_record_holds(self):
        result = apply_checklist(METALEARNED_COMPLETE)
        self.assertTrue(result.holds)
        self.assertEqual(result.missing, ())

    def test_incomplete_records_fail(self):
        blank = apply_checklist(INCOMPLETE_BLANK)
        self.assertFalse(blank.holds)
        self.assertIn("state_zsc_setting", blank.missing)
        self.assertIn("give_shared_cfd", blank.missing)
        missing_flag = apply_checklist(INCOMPLETE_HANDCRAFTED)
        self.assertFalse(missing_flag.holds)
        self.assertEqual(
            missing_flag.missing,
            ("handcrafted_reject_arbitrary_conventions",),
        )

    def test_reproduction_or_runtime_claims_fail(self):
        repro = apply_checklist(FORBIDDEN_REPRODUCTION_CLAIM)
        self.assertFalse(repro.holds)
        self.assertEqual(repro.missing, ("not_a_reproduction",))
        runtime = apply_checklist(FORBIDDEN_DOCKER)
        self.assertFalse(runtime.holds)
        self.assertEqual(runtime.missing, ("not_a_reproduction",))


class TestNoForbiddenRuntime(unittest.TestCase):
    def test_implementation_modules_do_not_import_forbidden_hosts(self):
        forbidden_roots = {
            "sqlite3",
            "docker",
            "openai",
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
            self.assertNotIn("OPENROUTER_API_KEY", src)
            self.assertNotIn("SQLiteStore", src)
