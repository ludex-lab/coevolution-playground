# w28-level-is-not-rank

A small stdlib-only experiment: **handing a conformal level to a quantile function is not evidence that the
required rank was reached.** A conformal interval end needs one particular order statistic of the calibration
scores. A helper that turns a level into an index can land somewhere else. The sketch computes the required
rank exactly, classifies each helper by where it lands, and refuses to return a finite end when no rank can
reach the level.

## Credit and licence

Method idea from arXiv [2611.23329](https://arxiv.org/abs/2611.23329) (Lalakiya; v1, 16 Nov 2026), titled
"A level is not a rank: an empirical audit of quantile-to-index conversion in 10 released conformal-prediction libraries".
Paper licence: arXiv nonexclusive-distrib 1.0. That is a licence to arXiv, not a grant to this repository, so
only the method is borrowed: no paper text or figures are reproduced beyond the short abstract quotes below.
Only the abstract page was read for this draft; the full paper was not.

The abstract links a software archive (concept DOI 10.5281/zenodo.21799203). The review pack that prepared
this experiment read its LICENSE file as MIT. This sketch did not run, read or copy that archive: it is
clean-room, and no code, test, fixture or wording came from it. None of the ten libraries was installed or cloned.

Quotes from the abstract:

- "a fresh score falls at or below the rth smallest of n with probability r/(n + 1)"
- "The libraries we study instead hand a level to a quantile function, which can land elsewhere."
- "At n = 20, the upper end of statsforecast's interval sits at position 18.05 where rank 19 is required."

The paper's other numbers (10 libraries, 39 sites, the coverage deltas, 5 of 14 call paths, 6 of 19 merged
filings) are not measured here. They appear only as UNVERIFIED entries under `on_unmeasured` in `evidence.json`.

## Conventions, pinned

These are stated once in `level_rank.py` (`Q_RULES`, `RANK_RULE`, `FLOOR_RULE`), repeated here, copied into
`evidence.json`, and checked by tests, because the abstract's two numbers only fit together under one reading.

- `alpha` is the miscoverage the interval end must carry; the level is 1 - alpha. It is given as a **decimal
  string** (`"0.10"`) and read with `fractions.Fraction`. A JSON number is refused.
- Required rank, rule `r = ceil((n + 1) * (1 - alpha)), guarantee r / (n + 1)`.
- Feasibility floor, rule `r <= n, the same as n >= 1/alpha - 1`. Below it no order statistic of the `n` scores
  reaches the level, and the end is not a finite number.
- A helper is handed a quantile level `q`:
  - `one_sided`: `q = 1 - alpha`
  - `two_sided_upper`: `q = 1 - alpha/2` (the upper end of a two-sided interval)
- Positions are **0-based indexes**, as in numpy's default linear method: the linear helper lands at
  `(n - 1) * q`. The required rank `r` is 1-based, so the required index is `r - 1`. A helper reaches the rank
  only when its position equals `r - 1` exactly. Each report row shows both the 0-based index and the 1-based
  rank scale (index plus one) so neither reading is hidden.

### The abstract's 18.05

At n = 20 and level 0.90 the required rank is 19 (index 18). The linear helper's index is 17.1 at q = 0.90 and
18.05 at q = 0.95. So 18.05 is the linear index for **q = 0.95**, not for q = 0.90. This sketch therefore reads
the abstract's pairing as: the upper end of a two-sided 0.90 interval is handed q = 0.95, while the rank the
abstract's formula gives for level 0.90 is 19. That reading is **UNVERIFIED**: it rests on the abstract alone,
and whether the library's interval construction needs rank 19 or rank 20 at q = 0.95 is not settled here. The
sketch only shows what the helper lands on under each pinned convention and that neither lands on the rank.
The fixture reports 18.05 as `WRONG_RANK` ("above" the required index 18); it does not claim the interval
over-covers, since the guarantee holds only at the required rank itself.

## Exact arithmetic

Every rank, level and position is a `fractions.Fraction`. Float arithmetic gives a different required rank in 4
of the 6000 cases of the grid n = 1..300, alpha = 0.01..0.20: for example `math.ceil((149 + 1) * (1 - 0.18))` is
124 while the exact value for (n=149, alpha=0.18) is 123, because `1 - 0.18` is not exactly 0.82 in binary.
The other three are (249, 0.18), (299, 0.18) and (299, 0.19). A test covers all four, runs the whole grid
against an independent integer computation, and checks that the module has no `float(` call.

## What it does

Each fixture case holds a bag of integer scores, a declared `n` and `alpha`, a `convention`, and the `helper`
being classified:

- `linear`: index `(n - 1) * q`;
- `weibull`: index `(n + 1) * q - 1`;
- `higher`: index `ceil((n - 1) * q)`;
- `conformal_rank`: the required index `r - 1`, and a refusal below the floor.

The first three are clamped to the bag, so below the floor they still return a finite score. Decisions:

- `REACHES_RANK`: the helper's index equals the required index. This is the only decision that carries the
  `r / (n + 1)` guarantee.
- `WRONG_RANK`: the index differs; the row says `below` or `above` and gives the interpolated end value next to
  the value at the required rank.
- `REFUSED_BELOW_FLOOR`: `conformal_rank` at an `n` below the floor. Refusing is the closed behaviour and exits 0.
- `DENY`, with a code:
  - `finite_end_below_floor`: another helper returned a finite end although no rank reaches the level;
  - `missing_scores`, `missing_level`: the score bag or the level is null;
  - `n_changed`: the bag does not hold the declared `n`;
  - `level_changed`: `alpha` differs (as an exact value) from the declared `alpha`.

`on_expiry` must be `DENY`: a missing bag or level is never read as consent.

## Exit codes

`fixtures/main.json` has no DENY row and exits 0. A fixture with any DENY row (`fixtures/below_floor.json`,
`fixtures/denied.json`) exits 2 with the report on stdout and an empty stderr. Malformed input (bad JSON,
duplicate keys, unknown or missing keys, a float or out-of-range `alpha`, a non-integer score, an unknown
helper or convention, an `on_expiry` other than `DENY`) exits 2 with an empty stdout and one
`ERROR <code>: <detail>` line on stderr. The two exit-2 cases are told apart by stream and by that prefix;
this is a convention described here, beyond the exit codes the tests pin.

## Run

```
cd experiments/2026-11-19/w28-level-is-not-rank
python3 -B -m unittest -v test_level_rank
python3 -B demo.py
python3 -B level_rank.py fixtures/main.json
python3 -B level_rank.py fixtures/below_floor.json
python3 -B level_rank.py fixtures/bad_alpha_float.json
python3 -B mutants.py
```

- `level_rank.py`: module and CLI.
- `fixtures/main.json`: 8 cases at n = 20, 9 and 8.
- `fixtures/below_floor.json`: a clean case, four finite ends below the floor, a refusal and a boundary case.
- `fixtures/denied.json`: a clean case, four broken declarations and one level written another way.
- `fixtures/bad_*.json`: 32 malformed fixtures.
- `mutants.py`: inline mutation check; every mutant must be killed by the suite.
- `demo.py`: deterministic text log of the three fixtures.

## Distinct from

- **w24-threshold-compliance**: a declared threshold against a measured rate, not a conformal rank against a
  quantile level.
- **w28-audit-contract**: arithmetic contracts and a range over them, not a rank.
- **mb-certified-region-delta**: a region against a point.
- **w27-ranked-conflict-set**: a score ordering for retrieval; its `rank_key` has nothing to do with
  calibration ranks.

## Limits

- Synthetic integer scores and four hand-written helpers. No library is run, so nothing here says which real
  libraries land on the wrong rank, or how much coverage that costs.
- The 18.05 reading above is unverified. The sketch does not decide which interval construction a library uses
  or whether its rank requirement is 19 or 20 at q = 0.95.
- Only a single upper end is classified; no full interval, no lower end and no coverage simulation.
- Linear interpolation of the end value is exact but is only an illustration: the guarantee attaches to the
  order statistic, not to an interpolated value.
- `alpha` has at most six decimals. The bag is at most 5000 integers.
- No network, no model call, no random numbers, no hashing or signing, no pip or venv.
