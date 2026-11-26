# mb-zero-reference-pass

An equivalence pass is not enough if a zero reference would have passed too. A simulated (candidate) effect "matches"
a human intervention effect when it lies within a stated margin of the human interval. But if the human interval
already sits inside that margin around zero, a candidate that shows no response at all (effect 0) would pass as well.
Such a pass does not show that the candidate captured a response. This sketch prints the zero-reference result and
threshold beside every equivalence decision.

## Credit and licence

Method sketch of arXiv [2611.27186](https://arxiv.org/abs/2611.27186):
"What Does Matching a Human Intervention Effect Establish? Benchmark Checks for LLM Simulations"
by Tengfei Shao, Asma Rezaei and Ali Reza Kamali. The paper is CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). No repository is listed on the abstract page.

- **Not a reproduction.** Only the idea of reporting a zero reference beside each equivalence decision is borrowed,
  as a method. No code was copied. `evidence.json` quotes abstract figures with attribution (fragments of up to 14
  words, CC BY 4.0).
- No model, simulation, study data, network or paid API is used. The contrasts are small, hand-made and synthetic.
- The paper's planned-precision margin and its test statistics are not reimplemented.
- The author-reported figures (for example 72 percent, 16 contrasts, 1.58 expected, 70 experiments, a ±0.20 SD
  margin) appear only as `UNVERIFIED` under `on_unmeasured` in `evidence.json`. They are not reproduced.

## The rule (declared for this sketch)

Each contrast gives a human 90 percent interval `[human_lo, human_hi]`, a candidate effect `c` (a point estimate) and a
margin `m > 0`, all in the same units (SD in the fixtures).

- **Equivalence (inclusive):** `c` matches when it is within `m` of every point of the human interval, that is
  `human_hi - m <= c <= human_lo + m`. When the interval is wider than `2m`, no candidate can match, and the report
  says so.
- **Zero reference:** the same rule with `c = 0`. It passes exactly when the human interval lies inside `[-m, m]`.
- **Zero-reference threshold:** `max(|human_lo|, |human_hi|)`, the smallest margin at which the zero reference passes.
  It is printed for every contrast.
- Numbers are parsed from the fixture as exact decimals, so values on a boundary (such as `0.45` against `0.25 + 0.20`)
  are decided without float rounding.

| equivalence | zero reference | verdict |
|---|---|---|
| PASS | FAIL | `response`: the pass shows a response |
| PASS | PASS | `zero_reference_pass`: PASS, but it does not establish a response |
| FAIL | FAIL | `fail` |
| FAIL | PASS | `fail`, noting that the zero reference would have passed |

The inclusive edges, the point-estimate candidate and the "within the margin of every point of the interval" reading
are this sketch's own choices. They are not claimed to be the paper's exact test.
The paper's §2.2 rule is strict (`|bH| + 1.645 SEH < δ`); this tool's inclusive `<=` is a declared choice, so the exact-edge cases `edge_upper`, `edge_lower` and `zero_on_edge` in `more.json` would FAIL under the paper's rule.

## The two arms

- `equivalence_only` (weak): prints the equivalence decision alone and counts every PASS as a match. On the main
  fixture it reports 2 of 3 matches and cannot say which one shows a response.
- `with_zero_reference` (strict): prints the zero-reference result and threshold beside every equivalence decision.
  On the main fixture it finds 1 response, 1 zero-reference pass and 1 fail.

## Results (synthetic)

`fixtures/main.json`, the three planted contrasts from the pack:

| contrast | human 90% interval | candidate | margin | equivalence | zero reference | zero threshold | verdict |
|---|---|---|---|---|---|---|---|
| reminder_letter | [0.25, 0.45] | 0.31 | 0.20 | PASS | FAIL | 0.45 | response |
| font_change | [-0.05, 0.12] | 0.03 | 0.20 | PASS | PASS | 0.12 | zero_reference_pass |
| peer_comparison | [0.30, 0.50] | 0.05 | 0.20 | FAIL | FAIL | 0.50 | fail |

The result is `closed: 3 / 3 planted contrasts`, `gate: PASS`.

`fixtures/more.json` covers exact edges on both sides, a candidate one step past the edge, a human interval touching
the margin, a negative effect, two fails where zero would pass (one with a Korean label) and an interval wider than
twice the margin. It is `closed: 8 / 8`.

These are counts of planted cases, not rates, and say nothing about any model.

## How to run

```
python3 -B zero_reference.py fixtures/main.json          # report; exit 0 gate PASS, 1 gate FAIL, 2 DENY
python3 -B zero_reference.py --json fixtures/main.json   # the same result as JSON
python3 -B demo.py                                        # both fixtures; identical bytes every run
python3 -B -m unittest                                    # the suite
python3 -B mutants.py                                     # mutation run; prints k/t/c
```

## Contract

- Malformed or missing input is `on_expiry=DENY`: exit 2, empty stdout, one stderr line `ERROR <code>: ...`.
- Error codes:
  - reading: `unreadable`, `too_large`, `bad_encoding`, `not_json`
  - values: `not_finite` (NaN or infinity), `bad_number`, `out_of_range`
  - structure: `duplicate_key`, `bad_shape`, `missing_field`, `unknown_field`, `empty_list`, `too_many`
  - fields: `bad_version`, `bad_type`, `bad_text`, `bad_id`, `duplicate_id`, `bad_margin` (zero or negative),
    `interval_reversed` (`human_lo > human_hi`), `bad_planted`
  - command line: `usage`
- Caps, each with `on_expiry` DENY: 65536 bytes, 200 contrasts, |value| ≤ 100 (compared exactly, so `1E+999999999` is
  `out_of_range`), 200 text characters, 32 characters
  per number and 30 decimal places per number. The rule runs with 80 significant digits, so in-cap values are exact.
- `mutants.py` applies each mutant to an in-memory copy of the module, loads it in a child `python3 -B` and runs the
  suite against it. Nothing is written. `TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}`:
  - A timeout is TIMEOUT, never a kill.
  - A mutant that fails to load, or whose suite only errors, is a CRASH, counted separately.
  - A kill needs a test failure.
- No test reads Python source. The tests call `main()` in-process so that every test exercises the loaded (possibly
  mutated) module.

## Not a remake

- passing-check-vs-verdict asks whether a work report's checks support its verdict.
- #153 evidence binding tests whether a quoted number is bound to the right line, period and unit.
- #155 verify-the-verifier audits a design against spec clauses where a scoreboard missed bugs.
- #158 bounds memory occupancy per time bucket.
- There is no voting and no ensemble.
- This sketch asks one statistical question: would a do-nothing reference have passed the same equivalence check?

## Limits

- The candidate is a point estimate. Candidate intervals, sampling error and the paper's planned-precision margin are
  not modelled, so this is a reporting rule, not a significance test.
- The equivalence reading (inclusive, within `m` of every point of the human interval) is one choice among several.
  Other readings, such as comparing a difference interval or using the interval midpoint, are not tested.
- The margin is given per contrast. Choosing a margin is out of scope.
- All contrasts are synthetic, with no real study or model output.
- No paper figure is reproduced or verified.
- An earlier NaN-to-`Decimal` mutant (`parse_constant=D`) survives as an equivalent mutant: the later `is_finite` guard
  rejects NaN with the same `not_finite` code, so NaN handling is not fail-open. It was replaced by `nan_becomes_zero`.

## Files

- `zero_reference.py`: loader, rule, arms, report and CLI
- `test_zero_reference.py`: unittest suite
- `demo.py`: deterministic report on both fixtures
- `mutants.py`: in-memory mutation run
- `evidence.json`: source, licence, declared rule, measured counts, `on_unmeasured`
- `fixtures/main.json`, `fixtures/more.json`: valid fixtures
- `fixtures/bad/`: malformed fixtures, each DENY with its own code
