"""Original SYNTHETIC repeated runs; no downloaded traces or model calls."""
import random
from baseline import (RunView, History, online_difficulty, model_only,
                      trajectory_prefix, diagnostic_online_ineligible,
                      rank_report, compare_budget)


def synthetic(seed=71):
    rng = random.Random(seed)
    history, views, labels, panel = [], [], {}, []
    for issue in range(6):
        # Latent probabilities remain in the generator, never in scorer inputs.
        for model in range(3):
            chance = max(0.08, min(0.93, 0.88 - issue * 0.13 + model * 0.08))
            for run in range(8):
                failed = rng.random() >= chance
                retry_success = rng.random() < chance
                split = 'train' if run < 4 else 'holdout'
                history.append(History(str(issue), str(model), run, failed, split))
                if split == 'holdout':
                    # Work counters share issue/model structure but are not
                    # constructed from failures, retries, or cause labels.
                    steps = tuple(1 + issue + (2-model) + rng.randrange(4) for _ in range(3))
                    views.append(RunView(str(issue), str(model), run, steps))
                    labels[(str(issue), str(model), run)] = (failed, retry_success)
        for outside in range(4):
            for run in range(5):
                panel.append(History(str(issue), 'external-' + str(outside), run,
                                     rng.random() >= (0.9 - issue * 0.14), 'diagnostic'))
    return history, views, labels, panel


def comparison():
    history, views, labels, panel = synthetic()
    scorers = {
        'online_same_model_difficulty': lambda v: online_difficulty(v, history),
        'online_model_only': lambda v: model_only(v, history),
        'online_prefix_work': trajectory_prefix,
        'OFFLINE_diagnostic_other_models': lambda v: diagnostic_online_ineligible(v.issue, panel),
    }
    rankings, budgets = {}, {}
    for name, scorer in scorers.items():
        scores = [scorer(v) for v in views]
        rankings[name] = rank_report([
            {'issue': v.issue, 'failed': labels[(v.issue, v.model, v.run)][0], 'score': s}
            for v, s in zip(views, scores)])
        if not name.startswith('OFFLINE'):
            budgets[name] = compare_budget(scores, [labels[(v.issue, v.model, v.run)]
                                                    for v in views], k=18)
    return rankings, budgets


if __name__ == '__main__':
    rankings, budgets = comparison()
    print('SYNTHETIC ONLY — failure-first pair ranks; no paper results')
    print('scorer                              pooled  within_issue  pooled_pairs within_pairs holds')
    for name, result in rankings.items():
        print(f"{name:35s} {result['pooled']['rank']:.4f}  "
              f"{result['within_issue']['rank']:.4f}       "
              f"{result['pooled']['pairs']:5d}        {result['within_issue']['pairs']:4d}     {result['hold']}")
    print('SYNTHETIC equal-budget illustration; each row has 72 initial attempts')
    print('scorer / action: extra attempts, total attempts, repaired, final successes, equal budget')
    for name, report in budgets.items():
        for action, result in report['actions'].items():
            print(name, '/', action, ':', result)
    print('Blanket-all is an unequal-budget reference here; no production policy follows.')
