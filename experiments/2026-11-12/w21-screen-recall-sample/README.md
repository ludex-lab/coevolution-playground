# w21-screen-recall-sample

Agreement is not recall. When screeners pass items to a costly assessor,
only what they pass gets judged. This folder is a small, deterministic
method sketch of one idea from
[arXiv 2611.12705](https://arxiv.org/abs/2611.12705), "Multi-Agent
Screening: What Agreement and Acceptance Cannot Tell You" (Benjamin Chang
and Dell Zhang; v1). Paper licence: arXiv non-exclusive distribution
licence, http://arxiv.org/licenses/nonexclusive-distrib/1.0/ (not a
software grant). Method borrowed only: no code is linked from the abs page
(code UNVERIFIED) and none is ported.

Status: Soft (eval-shaped). This is a method sketch, not law, not policy
and not a reproduction. Python standard library only, synthetic fixtures,
no network, no model in the loop, no files written. The paper's bounds
("even with unlimited data"), its upper-bound result and its sample-size
claim (a sample estimates misses "to any chosen accuracy", and its size
does not grow with the number of agents) are recorded verbatim in
`paper_evidence.json`, marked UNVERIFIED and **not claimed here**.

## What each kind of evidence supports

`screen_recall.report(request)` returns three figures:

| figure | status when reported | needs |
|---|---|---|
| `precision` | `measured` | every forwarded item judged by the assessor |
| `recall_lower_bound` | `lower_bound` | the same; it is `found / (found + not_passed_count)`, true whatever the misses are |
| `recall` | `estimate` | the same, plus a judged random sample of NOT-forwarded items |

Anything else is `on_unmeasured` with a reason. Recall is never reported
from acceptance alone: that gives `recall_lower_bound`, never `recall`.

The estimator is a plain proportion over the sample, scaled to the
not-passed count:

```
missed_estimate = relevant_in_sample / sample_size * not_passed_count
recall_estimate = found / (found + missed_estimate)
```

It is a point estimate. No interval, accuracy or sample-size guarantee is
computed or claimed (`interval` is `None`). On the fixtures the estimate
is 1/2 while the fixture truth is 2/3: the sample happens to hold every
missed relevant item. A sample of the whole not-passed set gives the truth.

The sample must be the seeded draw `random.Random(seed).sample(sorted(not_passed), size)`.
A declared sample that differs from that draw (reordered, cherry-picked,
or under another seed) leaves recall `on_unmeasured`
(`sample_not_seeded_draw`). An omitted sample gives `no_not_passed_sample`;
a size-0 sample gives `sample_empty`.

## Not a voter or ensemble

Screener reports are validated and counted (`screener_count`), and that
is all. No majority, vote, aggregate pass, consensus score or
agreement-weighted figure is computed. The forwarded list is an input, not
something derived from screener reports. Tests show that 0 to 64
screeners agreeing on the same pass list leave recall `on_unmeasured`, and
that the whole record (status, `on_expiry` and every figure with all its
fields) is identical across screener variants: 0 to 64 screeners all
passing the forwarded list, all passing the all-items list, empty, mixed and
disagreeing lists (including 10 or more disagreeing screeners), random
and reordered reports. Only `screener_count`, the number of
reports, changes. This is checked on ten paths: with and without a sample,
cherry-picked and reordered samples, expired (with and without a pending
judgment), a pending sample judgment, a pending pass, and partially
assessed passes (with and without a sample). The module source has no
ensemble terms, and `_report` reads the request only by literal field
names, with `screener_reports` read only inside `len()`. The same source
check rejects `global` and `nonlocal` statements, `locals()` and `vars()`
calls, and `getattr` on the request object. Mutants that add
a majority rule, or that let 4 or more screeners all passing the forwarded
list waive the seeded-draw check, bypass expiry or read a pending sample
judgment as judged, are killed.

## Pending judgments and deadlines

A judgment may be `pending`. Any pending judgment needs a declared
`deadline: {timeout_s, on_expiry, expired}`, with `on_expiry` one of
`hold`, `escalate`, `deny`; a missing declaration is a `config_error`.
While pending, figures that depend on it are `on_unmeasured`
(`assessment_pending`). An expired deadline reports status `expired`, the
module's own `on_expiry` constant, and no figure at all.

## Input checks

Exact types throughout (`type(x) is str`, `dict`, `list`, `int`, `bool`).
Unknown fields, duplicate ids, ids outside the item list, judgments of
items that were not forwarded, sample items that were forwarded, a sample
size that does not match its items, and str/dict/list/int subclasses are
each a `config_error`. `report()` catches any `Exception` raised while
validating or computing and returns a `config_error` record with no
figures. It can still raise: called with the interpreter stack nearly
exhausted, it raises `RecursionError` (the `config_error` fallback needs
stack too). That fails closed, with no record and no figure.

## Neighbours (dupe check)

- `w18-phantom-consensus`: the "not a voter or ensemble" precedent. That
  sketch measures second-order belief error; this one measures what
  screening evidence can establish, and also takes no winning decision from
  several outputs.
- #91 (voting/ensemble, arXiv 2611.07140): out of bounds. Nothing here
  combines screener outputs; this folder is the opposite claim (agreement
  establishes nothing about recall). #91 is not touched.

## Run

From `experiments/2026-11-12/w21-screen-recall-sample/`, with system
`python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The source check reads the abstract copy named in `paper_evidence.json`
from the directory in `$W21SR_SOURCES`; unset (the normal case), that one
test is skipped, so a plain run reports `Ran 63 tests` and `OK (skipped=1)`.
The tests find the day index as `../README.md` in the repo layout, or as
`_day/README.md` in a flat copy.

## Files

- `screen_recall.py`: validation, `draw_sample`, `report()`.
- `fixtures.py`: 40 synthetic items, 12 relevant by a fixture truth table,
  12 forwarded (8 relevant), fully agreeing screeners, seeded sample.
- `test_screen_recall.py`: unittest suite.
- `mutants.py`: 46 code mutants and 9 world (fixture) mutants; each must
  make the suite fail. They include two majority rules over screener
  reports (one using ensemble words, one with neutral names), agreeing
  screeners unlocking recall, three bypasses gated on 4 or more screeners
  all passing the forwarded list (seeded-draw check waived, expiry
  bypassed, pending sample judgment read as judged; K1-K3), a validate()
  global stash and a locals() alias of the request that waive the
  seeded-draw check at 51 or more unanimous screeners, a draw that reseeds
  the process RNG, a config error on 10 or more disagreeing screeners, the
  lower bound reported as recall, the seeded-draw check skipped, a seed of
  None accepted, an extra upper or agreement field on a figure, a pending
  pass without a sample accepted with no deadline, a wrong estimator
  scale, expiry ignored, an undeclared `on_expiry` defaulted, isinstance
  in place of exact type and no try/except. World mutants make the fixture
  screeners disagree, cherry-pick or mislabel the sample, or make the
  assessor stand-in trust the screeners.
- `paper_evidence.json`: title, authors, licence, verbatim abstract quotes,
  all UNVERIFIED. The abstract states no numeric results.

## Limits

- Synthetic items and an assessor stand-in that reads a fixture truth
  table; real relevance judgments are noisy.
- One sample, no interval; small samples give rough estimates.
- The seeded-draw check proves the sample matches its seed, not that the
  seed was chosen before the judgments were seen.
- The anti-ensemble guard is bounded: known residuals include
  `globals()`, `sys.modules`, function attributes, module dicts,
  mutable default arguments, `sys._getframe` stashes, `getattr`
  via an alias of the request, gates at 65 or more screeners,
  and unanimous lists other than the forwarded list and the
  all-items list.
