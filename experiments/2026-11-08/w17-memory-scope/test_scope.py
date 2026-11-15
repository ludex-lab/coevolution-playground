"""Offline synthetic boundary tests; optional raw-source checks never fetch the web."""
import ast
from dataclasses import replace, FrozenInstanceError
import hashlib
import json
from pathlib import Path
import unittest

import scope
from scope import Scope, Entry, Task, SourceEvent, Status, applicable, lint_write, read_scope, action_hold, repair_hold
import fixtures

HERE = Path(__file__).resolve().parent


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.entry = fixtures.LUDEX.entry
        self.task = Task(self.entry.scope, self.entry.source_event.identity)

    def test_matching_scope_is_applicable_not_action_authority(self):
        self.assertTrue(applicable(self.entry, self.task))
        self.assertEqual(lint_write(self.entry).status, Status.IN_SCOPE)
        report = action_hold(self.entry, self.task)
        self.assertEqual(report.status, Status.HOLD)
        self.assertIn('independent-action-review-required', report.reasons)

    def test_write_tool_widening_and_narrowing(self):
        wide = replace(self.entry, scope=replace(self.entry.scope, tools=frozenset({'edit', 'send'})))
        self.assertIn('write-tool-widening', lint_write(wide).reasons)
        narrow = replace(self.entry, scope=replace(self.entry.scope, tools=frozenset()))
        self.assertEqual(lint_write(narrow).status, Status.IN_SCOPE)
        self.assertFalse(applicable(narrow, self.task))
        self.assertTrue(applicable(narrow, replace(self.task, scope=narrow.scope)))

    def test_write_task_and_stakes_shifts(self):
        for changed in [replace(self.entry.scope, task_class='other'), replace(self.entry.scope, stakes=0), replace(self.entry.scope, stakes=8)]:
            with self.subTest(scope=changed):
                self.assertEqual(lint_write(replace(self.entry, scope=changed)).status, Status.HOLD)

    def test_read_each_dimension_independently(self):
        tasks = [replace(self.task, source_event='other-source'),
                 replace(self.task, scope=replace(self.task.scope, task_class='other')),
                 replace(self.task, scope=replace(self.task.scope, stakes=8)),
                 replace(self.task, scope=replace(self.task.scope, tools=frozenset({'send'})))]
        for task in tasks:
            with self.subTest(task=task):
                self.assertFalse(applicable(self.entry, task))
                self.assertEqual(read_scope(self.entry, task).status, Status.HOLD)

    def test_missing_and_ambiguous_scope_holds(self):
        bad_scopes = [None, {}, Scope('*', 1, frozenset({'edit'})), Scope('unknown', 1, frozenset()),
                      Scope('chore', None, frozenset()), Scope('chore', True, frozenset()),
                      Scope('chore', -1, frozenset()), Scope('chore', 1, {'edit'}),
                      Scope('chore', 1, frozenset({'?'})), Scope('chore ', 1, frozenset())]
        for value in bad_scopes:
            with self.subTest(value=value):
                entry = replace(self.entry, scope=value)
                self.assertEqual(lint_write(entry).status, Status.HOLD)
                self.assertFalse(applicable(entry, self.task))
                self.assertFalse(applicable(self.entry, replace(self.task, scope=value)))

    def test_missing_source_or_malformed_entry_holds(self):
        for entry in [None, {}, replace(self.entry, text=''), replace(self.entry, source_event=None),
                      replace(self.entry, source_event=SourceEvent('?', self.entry.scope)),
                      replace(self.entry, source_event=SourceEvent('event', None))]:
            with self.subTest(entry=entry):
                self.assertEqual(lint_write(entry).status, Status.HOLD)
                self.assertFalse(applicable(entry, self.task))
        for task in [None, {}, replace(self.task, source_event=None), replace(self.task, source_event='*')]:
            self.assertFalse(applicable(self.entry, task))

    def test_stakes_ordering_is_not_authority(self):
        for task in fixtures.STAKES_MISMATCH_TASKS:
            report = read_scope(self.entry, task)
            self.assertFalse(applicable(self.entry, task))
            self.assertIn('read-source-identity-mismatch', report.reasons)
            self.assertIn('read-task-class-out-of-scope', report.reasons)
        # Even exactly equal stakes do not overcome mismatched identities.
        self.assertFalse(applicable(self.entry, replace(self.task, source_event='different-source')))

    def test_confirmation_skip_both_boundaries(self):
        case = fixtures.TRAPS[0]
        self.assertEqual(case.name, 'confirmation skip')
        self.assertEqual(lint_write(case.widened).status, Status.HOLD)
        self.assertFalse(applicable(case.entry, case.task))

    def test_sycophancy_bias_both_boundaries(self):
        case = fixtures.TRAPS[1]
        self.assertEqual(case.name, 'sycophancy bias')
        self.assertEqual(lint_write(case.widened).status, Status.HOLD)
        self.assertFalse(applicable(case.entry, case.task))

    def test_test_weakening_both_boundaries(self):
        case = fixtures.TRAPS[2]
        self.assertEqual(case.name, 'test weakening')
        self.assertEqual(lint_write(case.widened).status, Status.HOLD)
        self.assertFalse(applicable(case.entry, case.task))
        # A mislabelled in-scope memory still cannot authorize a test change.
        self.assertEqual(action_hold(case.entry, Task(case.entry.scope, case.entry.source_event.identity)).status, Status.HOLD)

    def test_read_rechecks_invalid_formation(self):
        entry = fixtures.LUDEX.widened
        task = Task(entry.scope, entry.source_event.identity)
        self.assertFalse(applicable(entry, task))
        self.assertIn('write-task-class-shift', read_scope(entry, task).reasons)

    def test_blocked_repairs_preserve_actual_failing_assertion(self):
        original = fixtures.CORRECT_TEST
        with self.assertRaisesRegex(AssertionError, 'correct safeguard'):
            fixtures.run_safeguard_test(original)
        # Demonstrate the dangerous proposed expected-value edit masks the defect.
        fixtures.run_safeguard_test(fixtures.WEAKENED_TEST)
        proposals = [fixtures.WEAKENED_TEST, fixtures.DELETED_TEST,
                     replace(original, enabled=False), replace(original, input_label='different-input')]
        for proposal in proposals:
            retained, report = repair_hold(original, proposal)
            self.assertIs(retained, original)
            self.assertIn('blocked-repair-test-change', report.reasons)
            with self.assertRaisesRegex(AssertionError, 'correct safeguard'):
                fixtures.run_safeguard_test(retained)
        retained, report = repair_hold(original, original)
        self.assertIn('blocked-repair-frozen-defect', report.reasons)
        self.assertTrue(fixtures.safeguard_fails(retained))

    def test_ludex_adopt_check_both_holds_safeguard_intact(self):
        self.assertEqual(fixtures.adopt_check(), {'write_hold': True, 'read_hold': True,
                         'repair_hold': True, 'safeguard_still_failing': True})

    def test_fixtures_are_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            fixtures.LUDEX.entry.text = 'changed'
        self.assertIsInstance(fixtures.TRAPS, tuple)
        self.assertIsInstance(self.entry.scope.tools, frozenset)

    def test_public_api_no_action_authority(self):
        for name in scope.__all__:
            for forbidden in ['ALLOW', 'approve', 'permit']:
                self.assertNotIn(forbidden.lower(), name.lower())
        self.assertEqual(set(Status.__members__), {'HOLD', 'IN_SCOPE'})


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads((HERE / 'paper_evidence.json').read_text())

    def test_number_hygiene(self):
        hygiene = self.evidence['number_hygiene']
        self.assertGreater(len(hygiene['absence_needles']), 10)
        for name in hygiene['protected_files']:
            text = (HERE / name).read_text()
            for needle in hygiene['absence_needles']:
                with self.subTest(file=name, needle=needle):
                    self.assertNotIn(needle, text)

    def test_import_allowlist_and_no_dynamic_execution(self):
        permitted = {'dataclasses', 'enum', 'json', 'scope', 'fixtures', 'ast', 'hashlib', 'pathlib', 'unittest'}
        for name in ['scope.py', 'fixtures.py', 'test_scope.py']:
            tree = ast.parse((HERE / name).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name, permitted)
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, permitted)
                    self.assertEqual(node.level, 0)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {'eval', 'exec', '__import__', 'compile', 'breakpoint'})

    def test_readme_scope_strings(self):
        text = (HERE / 'README.md').read_text()
        for required in ['method sketch', 'not Team OS law', 'not village law',
                         'https://arxiv.org/abs/2611.07554', 'experiments/2026-11-08/w17-memory-scope/',
                         'Not implemented', 'UNVERIFIED', 'Builder reflection', 'Ludex', 'Cody/Naru',
                         'not a proven defense', 'formation-scope', 'application-scope', 'tooling-memory', 'FlyHash']:
            self.assertIn(required, text)
        for forbidden in ['KEEP', 'CloudAgent', 'Smith', '(draft)']:
            self.assertNotIn(forbidden, text)
        self.assertTrue(text.rstrip().endswith('Implementation may be complete; it is not declared verified.'))

    def test_license_and_no_code_pin(self):
        evidence = self.evidence
        self.assertFalse(evidence['paper_license']['cc_by'])
        self.assertFalse(evidence['paper_license']['software_grant'])
        self.assertEqual(evidence['github']['http_status'], 404)
        self.assertIsNone(evidence['github']['implementation_pin'])
        self.assertIsNone(evidence['github']['software_license'])
        self.assertIn('not CC BY', (HERE / 'NOTICE').read_text())

    def test_offline_paper_excerpt_found_and_window_hashes(self):
        present = 0
        for excerpt in self.evidence['excerpts']:
            source = self.evidence['sources'][excerpt['source']]
            path = Path(source['saved_path'])
            if not path.exists():
                continue
            present += 1
            raw = path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), source['sha256'])
            self.assertEqual(raw[excerpt['start']:excerpt['end']], excerpt['text'].encode())
            window = raw[excerpt['window_start']:excerpt['window_end']]
            self.assertEqual(hashlib.sha256(window).hexdigest(), excerpt['source_window_sha256'])
            self.assertEqual(excerpt['status'], 'FOUND')
        if not present:
            self.skipTest('saved paper HTML absent; no network attempted')
        self.assertEqual(present, len(self.evidence['excerpts']), 'partial paper evidence unavailable')


if __name__ == '__main__':
    unittest.main()
