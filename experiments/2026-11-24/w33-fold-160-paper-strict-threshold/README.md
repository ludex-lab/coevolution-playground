# w33-fold-160-paper-strict-threshold

A fold of `experiments/2026-11-24/mb-zero-reference-pass` (#160), not a new experiment. #160 prints, beside every
equivalence decision, whether a zero reference (an effect of 0) would also pass and its threshold. This fold retains
#160's inclusive reading and adds the paper's strict reading beside it. It also closes the open #160 review notes
L3, L4 and L6, and the review's JSON-row test gap.

The module `strict_threshold.py` is self-contained. It adapts this lab's own #160 code and does not import the #160
folder. The merged #160 folder is unchanged.

## Credit and licence

- **Paper:** method sketch of arXiv [2611.27186](https://arxiv.org/abs/2611.27186), "What Does Matching a Human
  Intervention Effect Establish? Benchmark Checks for LLM Simulations", by Tengfei Shao, Asma Rezaei and Ali Reza
  Kamali (dated 2026/11/20).
- **Licence:** CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). No repository is listed.
- **Not a reproduction.** No paper code exists, and none was copied. No model or network is used. All contrasts are
  synthetic.
- **Quotes:** only the two short inequalities below are quoted, with attribution. The author-reported figures
  appear only as `UNVERIFIED` entries under `on_unmeasured` in `evidence.json`.

## The paper's two strict conditions (#160 L6)

#160's README labelled the zero-reference formula "the paper's §2.2 rule". The paper's §2.2 has two separate
conditions:

- **Condition (1), zero-reference pass:** `|bH| + 1.645 SEH < δ`. The paper calls `|bH| + 1.645 SEH` the
  zero-reference threshold. The review's text extraction puts this at PDF line 260.
- **Simulation criterion:** a simulation passes when `|E| + 1.645 SEE < δ` (PDF line 254).

Both use a strict `<`. The PDF line numbers come from the review's extraction; the PDF was not reopened for this
fold.

## The rule

The fixtures give a human 90 percent interval `[human_lo, human_hi]`, a candidate `c` (a point estimate) and a margin
`m > 0`. They do not give `bH` or `SEH`, and none are invented here.

- **Equivalence:** inclusive and unchanged from #160: `human_hi - m <= c <= human_lo + m`.
- **Critical value:** `T = max(|human_lo|, |human_hi|)`. For a symmetric 90 percent interval this equals
  `|bH| + 1.645 SEH`.
- **Zero reference, inclusive (#160):** passes when `T <= m`. This reading drives the verdict and the planted gate,
  so #160's planted outcomes do not change.
- **Zero reference, paper-strict:** passes only when `T < m`. Under a strict rule no least passing margin exists, so
  `T` is the critical value (the infimum), not a "smallest margin".
- **At `m = T`** the two readings differ: inclusive PASS, paper-strict FAIL. `more.json` `zero_on_edge`
  (`[-0.20, 0.20]`, `m = 0.20`) shows this, and a test pins it.

The strict-arm header is relabelled so that no `>=` can be read as the paper's `<`. Its exact text, pinned in a test,
is:

```
| contrast | equivalence | zero reference, inclusive (passes when T <= m) | zero reference, paper-strict (passes only when T < m) | critical value T | verdict |
```

A one-line legend follows the table. The summary also counts the rows where the two readings differ.

## Results (synthetic)

- **`fixtures/main.json`** (#160's three planted contrasts):
  - The weak arm reports 2 of 3 as matches.
  - The strict arm finds 1 response, 1 zero-reference pass and 1 fail. The readings differ on 0 rows.
  - `closed: 3 / 3`, gate PASS.
- **`fixtures/more.json`:** #160's 8 edge cases plus `three_places`, whose critical value 0.234 has three decimal
  places so that a report that rounds to 2 places is caught.
  - The readings differ on 1 row (`zero_on_edge`).
  - `closed: 9 / 9`, gate PASS.
- **Bad input:** 64 bad fixtures, each with its own code, exit 2.

## What the fold closes

- **The review's JSON-row gap:** the critical value (`zero_threshold`) and the new `zero_reference_paper_strict`
  field are now checked exactly on every JSON row of every valid fixture, not only row 0. The strict-arm table row
  is checked the same way. Expected values are computed in the test from the fixture numbers.
- **The review's 4 surviving extra mutants,** adapted to this module, now die by assertion:
  - `json_threshold_dropped_after_row0`
  - `json_threshold_wrong_after_row0`
  - `threshold_rounded_to_2dp_in_report`
  - `header_inclusive_relabelled` (the old `>=` to `>`)

  The matching paper-strict mutants are added and also die by assertion:
  - `json_paper_strict_dropped_after_row0`
  - `json_paper_strict_wrong_after_row0`
  - `header_strict_relabelled`
  - `strict_column_prints_inclusive`
  - `paper_strict_uses_inclusive`
- **#160 L3** (`bool_counts_as_number`, crash-only in #160): `_number` now makes a plain-`Decimal` copy after the
  type check. With the bool gate removed, `true` becomes 1 and the run produces a result instead of an
  `AttributeError`. The exact CLI test (exit 2, empty stdout, the exact `ERROR bad_type` line) and a validate case
  for `true`/`false` margins then fail by assertion.
- **#160 L4** (`reachable_flag_ignored_in_report`): a test pins the full `too_wide` bullet line, including "no
  candidate can match", in the report text, and checks that no other row carries the note.
- **#160 L6:** the two conditions are named separately above.

## Numbers and caps (the #160 lessons)

- Numbers are parsed as exact decimals of at most 32 characters.
- `|value| <= 100` is checked with `value.copy_abs()`, before any rounding. `1E+999999999` in any field gives
  `out_of_range`.
- At most 30 decimal places, so `1E-999999999` gives `bad_number`.
- **No positive exponent:** `0E+999999999` (and `1E+1`) are denied as `bad_number`, not accepted as 0. No valid
  value needs a positive exponent, and refusing it holds the number text exact.
- The rule runs at 80 significant digits.
- Malformed or missing input is `on_expiry=DENY`: exit 2, empty stdout, one stderr line `ERROR <code>: ...`.

## Tests and mutants

- `python3 -B -m unittest`: 28 tests. No test reads Python source. There is no catch-all wrapper, so an exception
  stays a unittest error.
- `python3 -B mutants.py` applies 50 mutants to in-memory copies of the module. Each runs in a child `python3 -B`
  with `TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}`, and every mutant gets an attribution line:
  - `KILLED-behaviour` needs at least one assertion failure.
  - `CRASH` is a load failure or errors only. It is counted apart and is never a kill.
  - `TIMEOUT` is never a kill.
- Result: `mutants k/t/c: 50/0/0 (behaviour kills 50, crash-only 0, survived 0 of 50; on_expiry DENY)`.
- `python3 -B demo.py` prints both reports and gives the same bytes on every run.

## How to run

```
python3 -B strict_threshold.py fixtures/more.json          # report; exit 0 gate PASS, 1 gate FAIL, 2 DENY
python3 -B strict_threshold.py --json fixtures/more.json   # every row carries zero_threshold and zero_reference_paper_strict
python3 -B demo.py
python3 -B -m unittest
python3 -B mutants.py
```

## Limits

- Only the zero reference gets a paper-strict reading. The equivalence decision stays inclusive, so `edge_upper`
  and `edge_lower` remain PASS here although the paper's strict simulation criterion would FAIL them.
- `T = max(|lo|, |hi|)` equals `|bH| + 1.645 SEH` only for a symmetric 90 percent interval. The paper's statistics
  and its planned-precision margin are not computed.
- The candidate is a point estimate, and the margins are given, not chosen.
- Denying every positive exponent also refuses harmless spellings such as `1E+1`.
- No paper figure is reproduced or verified.

## Files

- `strict_threshold.py`: loader, rule, both readings, report, CLI
- `test_strict_threshold.py`: unittest suite
- `demo.py`: deterministic report on both fixtures
- `mutants.py`: in-memory mutation run with per-mutant attribution
- `evidence.json`: source, licence, declared rule, measured counts, `on_unmeasured`
- `fixtures/main.json`, `fixtures/more.json`: valid fixtures
- `fixtures/bad/`: 64 malformed fixtures, each DENY with its own code
