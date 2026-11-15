"""Offline stdlib checks of boundaries and toy computations, not paper results."""
import ast
from dataclasses import fields, replace
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest

import baseline
from baseline import (RunView, History, online_difficulty, model_only,
                      trajectory_prefix, diagnostic_online_ineligible,
                      rank_report, compare_budget)
from fixtures import synthetic, comparison

HERE = Path(__file__).resolve().parent


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _normalized(raw):
    parser = _Text()
    parser.feed(raw.decode('utf-8'))
    return ' '.join(' '.join(parser.parts).split())


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.history, self.views, self.labels, self.panel = synthetic()
        self.view = self.views[0]

    def test_original_repeated_fixture_shape(self):
        self.assertEqual(len(self.views), 72)
        self.assertEqual(len(self.history), 144)
        self.assertEqual({r.split for r in self.history}, {'train', 'holdout'})
        self.assertEqual(synthetic(), synthetic())
        self.assertTrue(set(r.model for r in self.panel).isdisjoint(v.model for v in self.views))

    def test_online_holdout_isolation(self):
        poisoned = [replace(r, failed=not r.failed) if r.split == 'holdout' else r
                    for r in self.history]
        for view in self.views:
            for scorer in (online_difficulty, model_only):
                self.assertEqual(scorer(view, self.history), scorer(view, poisoned))

    def test_scored_run_excluded_even_if_mislabeled(self):
        for failed in (False, True):
            added = History(self.view.issue, self.view.model, self.view.run, failed, 'train')
            for scorer in (online_difficulty, model_only):
                self.assertEqual(scorer(self.view, self.history), scorer(self.view, self.history+[added]))

    def test_online_difficulty_other_model_isolation(self):
        poisoned = [replace(r, failed=not r.failed) if r.model != self.view.model else r
                    for r in self.history]
        self.assertEqual(online_difficulty(self.view, self.history), online_difficulty(self.view, poisoned))
        self.assertEqual(online_difficulty(self.view, self.history+self.panel),
                         online_difficulty(self.view, self.history))

    def test_online_difficulty_other_issue_isolation(self):
        poisoned = [replace(r, failed=not r.failed) if r.issue != self.view.issue else r
                    for r in self.history]
        self.assertEqual(online_difficulty(self.view, self.history), online_difficulty(self.view, poisoned))

    def test_diagnostic_online_split(self):
        panel = [History('0', 'external', 0, True, 'diagnostic')]
        self.assertEqual(diagnostic_online_ineligible('0', panel), 1)
        self.assertEqual(diagnostic_online_ineligible('0', [replace(panel[0], failed=False)]), 0)
        self.assertIsNone(online_difficulty(self.view, panel))
        self.assertIsNone(diagnostic_online_ineligible('missing', panel))

    def test_model_only_excludes_current_issue_even_training(self):
        poisoned = [replace(r, failed=not r.failed) if r.issue == self.view.issue else r
                    for r in self.history]
        self.assertEqual(model_only(self.view, self.history), model_only(self.view, poisoned))
        self.assertIsNone(model_only(self.view, [r for r in self.history if r.issue == self.view.issue]))

    def test_model_only_expected_training_other_issues(self):
        expected = [r.failed for r in self.history if r.model == self.view.model
                    and r.issue != self.view.issue and r.split == 'train']
        self.assertEqual(model_only(self.view, self.history), sum(expected)/len(expected))

    def test_no_privileged_cause_or_outcome_in_view(self):
        self.assertEqual({f.name for f in fields(RunView)}, {'issue','model','run','prefix_steps'})
        self.assertEqual({f.name for f in fields(History)}, {'issue','model','run','failed','split'})
        with self.assertRaises(TypeError):
            RunView('0', '0', 9, (1,), cause='bad_run')
        with self.assertRaises(TypeError):
            trajectory_prefix(self.view, cause='hard_issue')
        self.assertEqual(list(trajectory_prefix.__code__.co_varnames[:trajectory_prefix.__code__.co_argcount]), ['view'])

    def test_prefix_only_no_policy_or_identity_choice(self):
        expected = trajectory_prefix(self.view)
        self.assertEqual(expected, trajectory_prefix(replace(self.view, issue='x', model='y', run=999)))
        self.assertIsInstance(expected, float)
        self.assertNotEqual(trajectory_prefix(replace(self.view, prefix_steps=(1,))),
                            trajectory_prefix(replace(self.view, prefix_steps=(8,))))
        self.assertIsNone(trajectory_prefix(replace(self.view, prefix_steps=())))
        with self.assertRaises(ValueError):
            trajectory_prefix(replace(self.view, prefix_steps=(-1,)))
        for name in baseline.__all__:
            self.assertFalse(any(x in name.lower() for x in ('stop','oracle','ensemble','switch')))

    def test_missing_history_holds(self):
        self.assertIsNone(online_difficulty(self.view, []))
        self.assertIsNone(model_only(self.view, []))
        self.assertEqual(compare_budget([None], [(True, True)], 1)['status'], 'hold')

    def test_pooled_and_within_issue_ranks(self):
        rows = [{'issue': 'a', 'failed': True, 'score': 1},
                {'issue': 'a', 'failed': False, 'score': 1},
                {'issue': 'b', 'failed': True, 'score': 0},
                {'issue': 'b', 'failed': False, 'score': 0}]
        result = rank_report(rows)
        self.assertEqual(result['pooled'], {'rank': 0.5, 'pairs': 4})
        self.assertEqual(result['within_issue'], {'rank': 0.5, 'pairs': 2})
        rows = [{'issue': 'a', 'failed': True, 'score': 1},
                {'issue': 'b', 'failed': False, 'score': 0}]
        result = rank_report(rows)
        self.assertEqual(result['pooled']['rank'], 1)
        self.assertIsNone(result['within_issue']['rank'])

    def test_rank_missing_and_nonfinite(self):
        self.assertEqual(rank_report([{'score': None}])['hold'], 1)
        with self.assertRaises(ValueError):
            rank_report([{'score': float('nan')}])

    def test_equal_budget_and_blanket_cost(self):
        report = compare_budget([0.1, 0.8, 0.4], [(True, True), (True, True), (False, True)], 1)
        actions = report['actions']
        for name in ('worst_k', 'random_k'):
            self.assertEqual(actions[name]['extra_attempts'], 1)
            self.assertEqual(actions[name]['total_attempts'], 4)
            self.assertTrue(actions[name]['equal_budget'])
        self.assertEqual(actions['worst_k']['repaired'], 1)
        self.assertEqual(actions['blanket_all_reference']['extra_attempts'], 3)
        self.assertFalse(actions['blanket_all_reference']['equal_budget'])
        self.assertEqual(compare_budget([1], [(True, True)], 0)['actions']['worst_k']['repaired'], 0)
        with self.assertRaises(ValueError):
            compare_budget([1], [(True, True)], 2)

    def test_selection_does_not_consume_labels(self):
        # Exercise the selection helper with an inaccessible evaluation object;
        # outcomes are absent from its signature, not merely ignored by fixture luck.
        self.assertEqual(list(baseline._rank_worst.__code__.co_varnames[:baseline._rank_worst.__code__.co_argcount]), ['scores', 'k'])
        self.assertEqual(baseline._rank_worst([1, 1, 0], 1), (0,))
        self.assertEqual(baseline._rank_worst([0, 1, 0], 1), (1,))

    def test_fixture_report_has_all_comparators(self):
        ranks, budgets = comparison()
        self.assertEqual(len(ranks), 4)
        self.assertEqual(len(budgets), 3)
        diagnostic = ranks['OFFLINE_diagnostic_other_models']
        self.assertEqual(diagnostic['within_issue']['rank'], 0.5)
        self.assertNotEqual(diagnostic['pooled']['rank'], diagnostic['within_issue']['rank'])
        for result in ranks.values():
            self.assertEqual(set(result), {'pooled', 'within_issue', 'hold'})

    def test_import_allowlist(self):
        allowed = {'dataclasses','math','random','baseline','fixtures','ast','hashlib',
                   'html','json','pathlib','unittest'}
        forbidden = {'sqlite3','subprocess','socket','urllib','http','hmac','requests','docker','inspect','inspect_ai'}
        for filename in ('baseline.py','fixtures.py','test_baseline.py'):
            tree = ast.parse((HERE/filename).read_text())
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(n.name.split('.')[0] for n in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module.split('.')[0])
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {'__import__','eval','exec','compile'})
            self.assertTrue(set(imports) <= allowed)
            self.assertFalse(set(imports) & forbidden)

    def test_public_api_vocabulary(self):
        for name in dir(baseline):
            if not name.startswith('_'):
                self.assertFalse(any(s in name.lower() for s in ('allow','approve','permit')))
        self.assertEqual(set(n for n in dir(baseline) if not n.startswith('_')), set(baseline.__all__))

    def test_number_hygiene_absent_needles(self):
        absent = ('0.924','0.92','0.62','SWE-bench AUROC','Holm','±0.02')
        for filename in ('baseline.py','fixtures.py','README.md','NOTICE'):
            text = (HERE/filename).read_text()
            for needle in absent:
                self.assertNotIn(needle, text)

    def test_readme_scope(self):
        text = (HERE/'README.md').read_text()
        for needle in ('method sketch','not Team OS law','not village law',
                       'https://arxiv.org/abs/2611.08285',
                       'experiments/2026-11-08/w17-failure-baseline/',
                       'Not implemented','UNVERIFIED','Builder reflection','Ludex', 'Cody/Naru',
                       '#94','SWE-bench transfer','retry-the-worst-K','other-model outcomes'):
            self.assertIn(needle, text)
        for needle in ('KEEP','CloudAgent','Smith','(draft)'):
            self.assertNotIn(needle, text)
        self.assertTrue(text.rstrip().endswith('Implementation may be complete; it is not declared verified.'))

    def test_notice_terms(self):
        text = (HERE/'NOTICE').read_text()
        for needle in ('Original','perpetual non-exclusive','not CC BY','not a software grant',
                       'Method-cite only','No implementation pin'):
            self.assertIn(needle, text)
        for needle in ('KEEP','CloudAgent','Smith','(draft)'):
            self.assertNotIn(needle, text)

    def test_evidence_structure(self):
        evidence = json.loads((HERE/'paper_evidence.json').read_text())
        self.assertIsNone(evidence['implementation_pin'])
        self.assertGreaterEqual(len(evidence['excerpts']), 6)
        for quote in evidence['excerpts']:
            self.assertLessEqual(len(quote['quote']), 160)
            self.assertEqual(quote['status'], 'FOUND')
            self.assertEqual(quote['end']-quote['start'], len(quote['quote']))

    def test_cached_paper_excerpts(self):
        path = Path('/tmp/w17-2611.08285.html')
        if not path.exists():
            self.skipTest('optional cached paper HTML absent; no network')
        evidence = json.loads((HERE/'paper_evidence.json').read_text())
        raw = path.read_bytes()
        source = evidence['sources']['html']
        self.assertEqual(len(raw), source['bytes'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), source['sha256'])
        text = _normalized(raw)
        for quote in evidence['excerpts']:
            with self.subTest(id=quote['id']):
                self.assertEqual(text[quote['start']:quote['end']], quote['quote'])
                window = text[quote['window_start']:quote['window_end']]
                self.assertEqual(hashlib.sha256(window.encode()).hexdigest(), quote['source_window_sha256'])

    def test_cached_abs_licence(self):
        path = Path('/tmp/w17-2611.08285-abs.html')
        if not path.exists():
            self.skipTest('optional cached abs absent; no network')
        evidence = json.loads((HERE/'paper_evidence.json').read_text())
        raw = path.read_bytes()
        self.assertEqual(len(raw), evidence['sources']['abs']['bytes'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), evidence['sources']['abs']['sha256'])
        self.assertIn('licenses/nonexclusive-distrib/1.0/', raw.decode())


if __name__ == '__main__':
    unittest.main()
