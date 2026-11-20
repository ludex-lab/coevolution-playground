# w28-audit-contract

A small stdlib-only experiment: **a pass under one numerical execution contract is not evidence that an
audit verdict belongs to the model.** The same model, records, threshold and audit code can be evaluated
with the arithmetic done in a different order. The sketch reports a verdict for each declared contract and
a range over all of them, and it refuses to call anything a pass on the strength of one contract.

## Credit and licence

Method idea from arXiv [2611.23657](https://arxiv.org/abs/2611.23657) (Zhang and Chu; v1, 18 Nov 2026), titled
"Same Model, Different People: Numerical Execution Contracts and the Reproducibility of Fairness Audits".
Licence CC BY 4.0 on the abstract page, a paper licence and not a code licence. Only the method is borrowed: the abstract
page lists no code, none was located, and none was copied. This is a clean-room sketch on tiny synthetic
records, **not a reproduction**. Only the abstract page was read for this draft; the full paper was not.
Quotes from the abstract, attributed here as CC BY 4.0 requires:

- "the arithmetic that evaluates it is part of that function"
- "The declared audit depends on the configuration; FP8 is not shown to be fairer."
- the protocol has the auditor declare "contracts, groups, weights and tests before scoring" and record "each verdict's range over them apart from its sampling uncertainty"

The paper's models, tasks, hardware and numbers (54% against 45% selected, the demographic-parity and
equalized-odds gaps, the 4B and 24B models, the four-fifths result) are not measured here. The numbers named
in this prose are tagged UNVERIFIED, and they are recorded as UNVERIFIED entries under `on_unmeasured` in
`evidence.json`.

## The verdict flip is fixture-authored

Read this before the results. In the paper's own words, its Tier 1 change (summation and product order only,
weights byte-identical) "changed decisions near the threshold" but produced
"no verdict under the prespecified, unweighted tests". So the abstract does not report a Tier 1 verdict flip, and this sketch does
not claim one.

The `CONTRACT_DEPENDENT` verdict in `fixtures/main.json` (audit `a1_near_threshold`) is **fixture-authored,
by construction**: two records (`r04`, `r05`) are written with cancelling terms such as `1e16, 1.0, -1e16`,
which float addition resolves differently depending on the order of the sum. The fixture was designed so
that the demographic-parity result lands on both sides of its bound. It shows that the report format and the
pre-declaration rules work when contracts disagree. It says nothing about how often real audits flip.

## What it does

- The model is a list of weights stored as **text** (`weights_text`, for example `1.0,1.0,1.0`). A record is a
  group label and a feature vector. The score is the dot product; a record is selected when its score is
  strictly above the declared `threshold`.
- Four **execution contracts** compute the same float products and differ only in how they are summed:
  - `ltr`: left to right, starting from 0.0;
  - `rtl`: right to left;
  - `lanes2`: even-indexed products in one running sum, odd-indexed in another, then the two added;
  - `fsum`: `math.fsum`, the correctly rounded sum.

  None of the four is named the right one. For `[1e16, 1.0, -1e16]` with weights of 1.0 the four scores are
  0.0, 0.0, 1.0, 1.0.
- Two groups, named in the declaration. Selection rates are exact fractions. Two tests:
  - `dp_gap` passes when the absolute difference of the two selection rates is at most its bound;
  - `rate_ratio` passes when the smaller rate over the larger rate is at least its bound (two rates of zero
    give 1).
- Per test and contract the report gives the statistic and pass or fail, and per test the **range** (smallest
  and largest statistic over the declared contracts) and an outcome: `pass_all_contracts`,
  `fail_all_contracts` or `contract_dependent`.
- One decision per audit, from the outcomes:
  - `CONTRACT_DEPENDENT`: some test passes under one contract and fails under another;
  - otherwise `STABLE_FAIL`: some test fails under every contract;
  - otherwise `STABLE_PASS`: every test passes under every contract;
  - `DENY`: the pre-declaration is broken (below). A DENY row has no verdict.
- The report also lists `single_contract_views` (what an auditor who scored only one contract would have
  printed, PASS or FAIL per contract), the records that change side between contracts, and the line
  `sampling_uncertainty: not_computed`. The range over contracts is kept apart from sampling uncertainty, and
  this sketch computes no sampling uncertainty at all.
- A declaration must name at least two contracts, so a one-contract audit cannot be declared. An audit that
  declares several and scores only some is `DENY contract_missing`, not a pass.

## Pre-declaration is a byte comparison and a sequence number

Each audit holds a `declaration` and a `scoring` block, each with an integer `seq`. The declaration must have
the smaller `seq`; the sketch trusts the fixture's order and reads no clock. The scoring block must then repeat
what was declared. Every check is plain equality, and the first one that fails names the DENY code, in this
order:

| code | broken rule |
|---|---|
| `no_declaration` | `declaration` is null |
| `declared_after_scoring` | declaration `seq` is not smaller than scoring `seq` |
| `contract_missing` | a declared contract has no run |
| `contract_not_declared` | a run uses a contract that was not declared |
| `weights_changed` | a run's `weights_text` differs from the declared `weights_text` |
| `threshold_changed` | the scoring threshold differs from the declared threshold |
| `groups_changed` | the scored groups differ from the declared groups (same order) |
| `post_hoc_test` | a scored test was not declared |
| `test_missing` | a declared test was not scored |
| `test_changed` | a scored test has a different bound than the declared one |

`weights_text` is compared byte-for-byte `==` on its UTF-8 bytes. So `1.00,1.0,1.0` is a different declaration
from `1.0,1.0,1.0` even though both parse to the same numbers, and a trailing space or an invisible character
is a change.
There is no hash, no signing and no timestamp: `hashlib` is not imported, and a test checks the import list. This is an ordering convention in a frozen fixture, not a tamper-proof record: nothing stops
someone from editing the whole fixture file, and nothing here proves that a declaration came first in time.

## Exit codes

The report is printed as JSON. `fixtures/main.json` has no DENY row and exits 0. A fixture with any DENY row
exits 2 with the report on stdout and an empty stderr. Malformed input (bad JSON, duplicate keys, unknown or
missing keys, wrong types, a non-finite number, an `on_expiry` other than `DENY`, an unknown contract, test,
group or id, a feature vector of the wrong length, a text holding a character that cannot be encoded as
UTF-8 such as a lone surrogate, a score that is not finite under a contract including a compensated sum
that overflows) exits 2 with an empty stdout and one `ERROR <code>: <detail>`
line on stderr. The second case does not start with the word DENY, so the two are easy to tell apart. As in
the other experiments, this exit convention is a stream convention described here, not something the tests
claim to make machine-checkable beyond the exit codes they pin.

`on_expiry` must be `DENY`: a missing declaration, contract, threshold or test is never read as consent.

## Run

```
cd experiments/2026-11-19/w28-audit-contract
python3 -B -m unittest -v test_audit_contract
python3 -B demo.py
python3 -B audit_contract.py fixtures/main.json
python3 -B audit_contract.py fixtures/denied.json
python3 -B audit_contract.py fixtures/bad_nan.json
python3 -B mutants.py
```

- `audit_contract.py`: module and CLI.
- `fixtures/main.json`: three audits (`a1_near_threshold`, `a2_calm_pass`, `a3_stable_fail`).
- `fixtures/denied.json`: one clean audit followed by eleven broken pre-declarations, one per DENY code plus a
  same-value-different-bytes case.
- `fixtures/bad_*.json`: 34 malformed fixtures.
- `mutants.py`: inline mutation check; every mutant must be killed by the suite.
- `demo.py`: deterministic text log of both fixtures.

## Distinct from

- **w26-verification-transport**: a verdict kept or changed across a change of verifier view. Here the
  view is fixed and only the arithmetic order changes.
- **w24-threshold-compliance** and **w24-trust-needs-feedback**: a declared threshold against a measured
  rate, not a declared set of execution contracts with a range.
- **mb-certified-region-delta**: a region against a point, not arithmetic-order stability.
- **w19-engram-release**: its overlap is checked before scoring, but it has no execution contracts.

## Limits

- Synthetic records and hand-set bounds. Nothing here says how often real audits change under reduced
  precision, a different GPU or another software stack.
- Only summation order is varied. Reduced-precision weights and kernels (the paper's second tier) are not
  modelled, and no model is run.
- The abstract speaks of "unweighted tests" and of declaring "weights"; this sketch reads the declared weights
  as the model weights and implements no record or group weighting.
- The range over contracts is a min and max, not a majority or an average: there is no vote and no ensemble.
  No sampling uncertainty is computed.
- Exactly two groups and two tests. A group needs at least one record.
- The sums are explicit loops. The builtin `sum()` is a compensated sum from Python 3.12, so it would not be a
  plain left-to-right contract; the contracts are defined by the loops, not by the interpreter.
- Threshold and weights are plain floats; the selection rates, bounds and tests use exact fractions, so only
  the dot product depends on the float summation order. The threshold and the bounds are compared as numbers;
  only the weights text is compared byte for byte.
- No network, no model call, no hashing or signing, no pip or venv.
