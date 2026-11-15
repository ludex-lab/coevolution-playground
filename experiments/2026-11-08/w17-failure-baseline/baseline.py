"""Offline SYNTHETIC evaluation comparisons; scores are not action authority."""
from dataclasses import dataclass as _dataclass
import math as _math
import random as _random

__all__ = ['RunView', 'History', 'online_difficulty', 'model_only',
           'trajectory_prefix', 'diagnostic_online_ineligible', 'rank_report',
           'compare_budget']


@_dataclass(frozen=True)
class RunView:
    """Decision-time view: identity and observed prefix only; no outcome or cause."""
    issue: str
    model: str
    run: int
    prefix_steps: tuple


@_dataclass(frozen=True)
class History:
    issue: str
    model: str
    run: int
    failed: bool
    split: str


def _rate(rows):
    rows = tuple(rows)
    return sum(r.failed for r in rows) / len(rows) if rows else None


def _training(view, history):
    return tuple(r for r in history if r.split == 'train'
                 and (r.issue, r.model, r.run) != (view.issue, view.model, view.run))


def online_difficulty(view, history):
    """Same-issue, SAME-model earlier training outcomes only; None means hold.

    This personalized historical proxy is not the external diagnostic reference.
    The caller must designate training records before the scored prefix exists.
    """
    return _rate(r for r in _training(view, history)
                 if r.issue == view.issue and r.model == view.model)


def model_only(view, history):
    """Model failure rate on OTHER issues, using training records only."""
    return _rate(r for r in _training(view, history)
                 if r.model == view.model and r.issue != view.issue)


def trajectory_prefix(view):
    """Fixed cheap prefix feature; comparison only, no learned/runtime policy.

    Synthetic steps are nonnegative work counters, not failure-cause labels.
    No completion outcome, retry outcome, or future step is accepted.
    """
    if not view.prefix_steps:
        return None
    if any(not isinstance(x, int) or x < 0 for x in view.prefix_steps):
        raise ValueError('prefix counters must be nonnegative integers')
    return sum(view.prefix_steps) / (sum(view.prefix_steps) + len(view.prefix_steps))


def diagnostic_online_ineligible(issue, external_panel):
    """OFFLINE ONLY: peek at outside-model outcomes unavailable online.

    The panel must be disjoint from evaluated models. This is a diagnostic
    comparator, not an online predictor; all runs of an issue get one score.
    """
    return _rate(r for r in external_panel if r.issue == issue and r.split == 'diagnostic')


def _pair_rank(rows, within):
    credit = 0.0
    pairs = 0
    for a in rows:
        for b in rows:
            if a['failed'] and not b['failed'] and (not within or a['issue'] == b['issue']):
                pairs += 1
                credit += (a['score'] > b['score']) + 0.5 * (a['score'] == b['score'])
    return {'rank': credit / pairs if pairs else None, 'pairs': pairs}


def rank_report(rows):
    """Failure-first pair concordance, tie credit half; outcomes used only here.

    Within-issue result is pair-weighted across issues (including same-model
    repeated runs), not macro-averaged and not the paper's exact pair universe.
    Missing scores produce an explicit hold count, never an imputed ranking.
    """
    rows = tuple(rows)
    usable = [r for r in rows if r['score'] is not None]
    if any(not _math.isfinite(r['score']) for r in usable):
        raise ValueError('scores must be finite')
    return {'pooled': _pair_rank(usable, False),
            'within_issue': _pair_rank(usable, True), 'hold': len(rows) - len(usable)}


def _rank_worst(scores, k):
    # Stable fixture position breaks ties without consulting any outcomes.
    return tuple(sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:k])


def compare_budget(scores, outcomes, k, seed=19):
    """POST-HOC fixture illustration, not a retry controller.

    Score-only selections are frozen before original/retry labels are read.
    Every additional attempt costs one unit, even on an initially successful run.
    A successful first attempt is retained. Full blanket retry is reported with
    its actual larger cost, NOT treated as an equal-budget competitor when k<N.
    """
    scores, outcomes = tuple(scores), tuple(outcomes)
    if len(scores) != len(outcomes) or not 0 <= k <= len(scores):
        raise ValueError('budget or row alignment mismatch')
    if any(s is None or not _math.isfinite(s) for s in scores):
        return {'status': 'hold', 'reason': 'missing or nonfinite score'}
    choices = {'worst_k': _rank_worst(scores, k),
               'random_k': tuple(_random.Random(seed).sample(range(len(scores)), k)),
               'blanket_all_reference': tuple(range(len(scores)))}
    reports = {}
    for name, selected in choices.items():
        selected = set(selected)
        repaired = sum(failed and retry_success and i in selected
                       for i, (failed, retry_success) in enumerate(outcomes))
        reports[name] = {'extra_attempts': len(selected),
                         'total_attempts': len(scores) + len(selected),
                         'repaired': repaired,
                         'final_successes': sum(not f for f, _ in outcomes) + repaired,
                         'equal_budget': len(selected) == k}
    return {'status': 'report', 'budget': k, 'actions': reports}
