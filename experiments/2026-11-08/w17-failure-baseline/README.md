# Failure-prediction baseline critique

A clean-room stdlib **method sketch** of “Hard Issue, Weak Model, or Bad Run?”
https://arxiv.org/abs/2611.08285 (HTML: https://arxiv.org/html/2611.08285).
Future playground path: `experiments/2026-11-08/w17-failure-baseline/`.
This is evaluation criticism: not Team OS law, not village law, and no action
is authorized by a score. All fixtures and reported numbers are SYNTHETIC.

## Run offline

```bash
python3 -m unittest test_baseline.py -v
python3 fixtures.py
```

Only the seven named deliverables belong in the eventual upload; local output
logs and the manifest are NOT for upload. `day-README.md` is a separate future
parent index, not a file to place inside this sketch's directory. No test
reads that index. Cached paper HTML is optional for offline excerpt tests.

## Comparators and data boundaries

Six issues, three evaluated models, eight runs per cell: first four runs are
historical training and the next four held out. Original probabilities are
scripted, with a fixed random seed, not fitted to the paper. The fixed prefix
contains three cheap work counters generated without consulting run outcomes.
All generated runs survive to this observation point; censoring is not modeled.

- `diagnostic_online_ineligible` uses a disjoint four-model external panel.
  The paper's strong difficulty-only reference uses other-model outcomes
  unavailable online: it is a diagnostic reference, not a practical online
  predictor. Our panel is illustrative, not a reproduction. Its issue score
  is constant across models and runs. It is never used in the budget table.
- `online_difficulty` uses only same-issue, same-model training outcomes.
  It is an online-eligible historical difficulty proxy, personalized to the
  model, not a pure model-independent issue parameter. It needs prior attempts;
  on a new issue it holds (`None`), rather than borrowing other-model evidence.
- `model_only` uses the model's history on other issues, never current-issue
  holdouts. Training labels must have existed before decision time. Both online
  history scorers discard every holdout and the scored run even if mislabeled
  as training. Split integrity otherwise remains a caller responsibility.
- `trajectory_prefix` scores only observed counters; it neither stops a run
  nor chooses a model. No outcome or privileged cause label exists in its API.
  Decision-time views are separate from post-hoc labels; no latent generator
  probabilities, future counters, or retry outcomes are passed to scorers.

The report computes failure-first failed/successful pair concordance with
half-credit ties. Pooled ranks mix issues; within-issue ranks pool only pairs
sharing an issue (including same-model repeats). Counts accompany both; an
undefined comparison is `None`, not evidence of no gain. This is pair-weighted,
not a per-issue macro average and not the paper's exact pair definition.

The budget table freezes score-only selections before reading evaluation
outcomes. Retrying the worst K and randomly chosen K each cost K extra attempts;
a blanket retry costs N and is explicitly a non-comparable reference when K<N.
Every attempt has unit cost, even a wasted retry after an original success;
successes are retained. Fixed tie order and one random seed are conveniences,
not evidence that one action is better. Generator probabilities can make a
ranking look useful or useless; no cause labels guide selections. Retry outcomes
are pre-generated same-model samples, not actions executed by this module.

The paper's equivalence finding is conditional on a bounded, pre-specified
interval test and multiplicity control; it is not a universal proof of no
trajectory information. No significance or equivalence test is implemented.

Distinct from playground #94 fail-signatures: this compares run-blind baselines
and ranking strata, not prefix mining on web-agent traces. No fail-signature
prefixes are mined.

## Not implemented

No early-stop policy, model switching, any-model oracle selector, voting or
ensemble, learned classifier, production monitor, cause diagnosis, external
trajectory download, model API call, or runtime retry engine. No copied author
code, prompts, data, or implementation pin. No runtime dependencies beyond
stdlib. Evidence hashes document fetched pages, not scientific validation.

## UNVERIFIED

- All paper empirical findings.
- SWE-bench transfer.
- Whether a real online monitor could match a diagnostic difficulty reference.
- Production usefulness of retry-the-worst-K.
- Robustness across seeds, observation points, costs, and real leakage boundaries.

## Builder reflection

I separated decision-time views from evaluation outcomes so that a tempting
post-hoc explanation cannot silently become a scorer input. I kept the external
panel visibly offline because an impressive pooled rank does not establish
run-specific knowledge. The fixed-budget comparison exposes cost mismatches
rather than claiming a retry policy has been earned.

Ludex: Cody/Naru should compare the same attempt budget and inspect within-issue
ranks before treating a failure alarm as useful evidence.

Implementation may be complete; it is not declared verified.
