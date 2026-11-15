"""Stdlib tests for the Wave15 Soft4 tooling-memory principle checklist."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from checklist import CHECKLIST_ITEMS, PAPER_QUOTES, apply_checklist
from fixtures import (
    COMPLETE,
    FORBIDDEN_SQLITE_MCP,
    INCOMPLETE_BLANK,
    INCOMPLETE_NO_PROVENANCE,
    INCOMPLETE_NO_QUARANTINE,
)


SKETCH_DIR = Path(__file__).resolve().parent
IMPLEMENTATION_MODULES = ("checklist.py", "fixtures.py")


class TestPaperQuotes(unittest.TestCase):
    def test_quoted_sentences_match_checked_paper_text(self):
        expected = {
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
        self.assertEqual(PAPER_QUOTES, expected)

    def test_quotes_do_not_invent_disputed_writes_or_figures(self):
        blob = " ".join(PAPER_QUOTES.values()).lower()
        self.assertNotIn("disputed write", blob)
        self.assertNotIn("disputed writes", blob)
        self.assertNotIn("%", blob)
        self.assertNotIn("sqlite", blob)
        self.assertNotIn("mcp", blob)


class TestChecklistShape(unittest.TestCase):
    def test_checklist_items_cite_known_quotes(self):
        ids = [item.item_id for item in CHECKLIST_ITEMS]
        self.assertEqual(
            ids,
            [
                "data_outlives_tooling",
                "agents_disposable",
                "ownership_leases",
                "write_carries_provenance",
                "quarantine_failed_screens",
                "judgment_written_down",
                "human_legible",
                "not_a_port",
            ],
        )
        for item in CHECKLIST_ITEMS:
            for key in item.cites:
                self.assertIn(key, PAPER_QUOTES)

    def test_quarantine_is_screening_not_a_numbered_principle_title(self):
        titles = {
            PAPER_QUOTES["data_outlives_title"],
            PAPER_QUOTES["agents_disposable_title"],
            PAPER_QUOTES["ownership_title"],
            PAPER_QUOTES["judgment_title"],
            PAPER_QUOTES["provenance_title"],
            PAPER_QUOTES["human_legible_title"],
        }
        self.assertNotIn("Quarantine of disputed writes.", titles)
        self.assertIn("write_screened", PAPER_QUOTES)
        self.assertIn("quarantined", PAPER_QUOTES)
        cites = {item.item_id: item.cites for item in CHECKLIST_ITEMS}
        self.assertEqual(
            cites["quarantine_failed_screens"],
            ("write_screened", "quarantined"),
        )


class TestSyntheticRecords(unittest.TestCase):
    def test_complete_record_holds(self):
        result = apply_checklist(COMPLETE)
        self.assertTrue(result.holds)
        self.assertEqual(result.missing, ())

    def test_incomplete_records_fail(self):
        blank = apply_checklist(INCOMPLETE_BLANK)
        self.assertFalse(blank.holds)
        self.assertIn("data_outlives_tooling", blank.missing)
        missing_prov = apply_checklist(INCOMPLETE_NO_PROVENANCE)
        self.assertFalse(missing_prov.holds)
        self.assertEqual(missing_prov.missing, ("write_carries_provenance",))
        missing_q = apply_checklist(INCOMPLETE_NO_QUARANTINE)
        self.assertFalse(missing_q.holds)
        self.assertEqual(missing_q.missing, ("quarantine_failed_screens",))

    def test_sqlite_or_mcp_port_flags_fail(self):
        result = apply_checklist(FORBIDDEN_SQLITE_MCP)
        self.assertFalse(result.holds)
        self.assertEqual(result.missing, ("not_a_port",))


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
            self.assertNotIn("SQLiteStore", src)
            self.assertNotIn("OPENROUTER_API_KEY", src)
