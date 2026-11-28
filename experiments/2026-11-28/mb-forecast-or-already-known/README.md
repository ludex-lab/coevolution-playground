# mb-forecast-or-already-known

A score that uses an outcome dated after the decision is recall, not a forecast. Arm A may read events dated after cutoff T, including the outcome edge itself, and so can hit a case whose only strong clue is that later edge. Arm B may use only events dated <= T and scores only outcomes dated > T, so it misses that planted case. A case with strong pre-T evidence is a forecast on both arms.

## Credit and licence

Method sketch of arXiv [2611.34247](https://arxiv.org/abs/2611.34247):
"Did the Model Forecast It, or Already Know It? Evaluating Large Language Models for Novel Drug-Target Prioritisation with a Temporal Knowledge-Graph Oracle"
by Pui Chung Siu, Yuan Liang, Claudia Cabrera, Mani Mudaliar and Arkaitz Zubiaga. The paper is CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). The upstream repository is MIT, but it was not cloned, installed, or run. No upstream code was copied.

- **Not a reproduction.** Only the method idea is borrowed: date both features and labels, give one arm post-cutoff evidence (including the outcome edge), and give the other arm only pre-cutoff evidence, scoring only later outcomes.
- No model, knowledge graph, trial register, network or paid API is used. The cases are small, hand-made and synthetic.
- Paper figures are not reproduced. The author-reported 95-97% own-edge share is an UNVERIFIED author figure; see `on_unmeasured` below.

## Declared rules

Events are named and dated. Dates are ISO `YYYY-MM-DD`, checked with a strict `YYYY-MM-DD` regex and then `datetime.date.fromisoformat`. This is a store of dated events, not a financial or HMAC ledger.

- A run has one cutoff T. Each case has exactly one outcome event and zero or more evidence events. Weight is `strong` or `weak`. A hit requires at least one visible strong clue.
- Arm A (leaky) may read every event, including the outcome edge and any post-T evidence.
- Arm B (temporal) may use only evidence dated <= T. It never uses the outcome as a clue. It scores a case only when the outcome date is > T.
- An event dated exactly T is usable by arm B as evidence. An event dated T+1 is not.
- Event names are unique within a case, so the outcome edge cannot also appear as dated evidence; a repeat is DENY `duplicate_name`.
- An outcome dated exactly T (or earlier) is `not_scorable` on both arms. This is a declared convention, not a claim about the paper's year-end snapshots.
- Case class, for a scorable outcome:
  - arm B hit: `forecast`
  - arm A hit and arm B miss: `recall_not_forecast`
  - neither hits: `miss`
- The fixture declares the expected per-case arm A, arm B and class values before the run. The gate is PASS (exit 0) iff the observed table equals that declaration exactly. Otherwise the run is FAIL (exit 1).
- A case or event that supplies a self-reported class, including fields or values such as `forecast`, `known`, `label`, `verdict`, or `leak`, is DENY `self_label`, exit 2. The expected table is the declared gate table, not a self-score on a case.

Expected table for `fixtures/main.json` (cutoff `2024-12-31`):

| case | arm A | arm B | class |
|---|---|---|---|
| own_edge (weak pre-T mention plus a post-T outcome edge) | HIT | MISS | recall_not_forecast |
| pre_t_support (strong evidence dated 2024-06-01, outcome 2025-04-01) | HIT | HIT | forecast |
| evidence_on_cutoff (strong evidence dated exactly T) | HIT | HIT | forecast |
| outcome_on_cutoff (outcome dated exactly T) | not_scorable | not_scorable | not_scorable |

## Limits

- Synthetic events and a single cutoff. This shows the mechanism only. It is not evidence of any rate.
- Dates must be zero-padded ISO dates. Forms such as `2026-2-30`, `2026-02-30`, `20261128`, an integer, a bool, or null are DENY `bad_date` or `bad_type`.
- Outcome-at-T convention: an outcome whose date is T is not a forecast, even if pre-T evidence exists. The paper's evaluations use year-end snapshots and next-year labels; this tool pins the exact-T edge as a declared rule.
- Weak evidence is not a strong clue. The planted `own_edge` case has a weak pre-T mention so the only strong clue is the post-T outcome.
- Calendar comparison uses parsed `datetime.date` values. Valid ISO `YYYY-MM-DD` strings sort in the same order as dates, so a mutant that compared raw strings directly would not diverge. The `date_compare_as_string` mutant instead compares a hyphen-stripped event string such as `20240601` to the dashed cutoff string `2024-12-31`, which treats planted pre-T evidence as post-T.
- `on_expiry` must be literally one of `DENY`, `SAFE_FALLBACK`, `ESCALATE`, `HOLD`. Any other value is DENY. The mutant runner's timeout is `{"seconds": 300, "on_expiry": "DENY"}`. on_expiry is never a pass value. A timeout is not a kill, and crashes are counted separately.

## on_unmeasured (UNVERIFIED)

- Author-reported share of positives whose retrieved paths include the pair's own trial edge (about 95-97% on the newest graph, against under 1% of negatives): UNVERIFIED, not measured here, and no paper figure is reproduced. The pack notes the opened aggregate file lists 0.951-0.972 across years 2021-2026 for that arm; that artefact was not re-run.
- Model ranking numbers, retrieval gains, and any trial-history baseline from the paper: UNVERIFIED, not measured here.
- The biomedical knowledge graph, Open Targets snapshots, and clinical-trial labels: not used.

## How this differs

Checked against the validators on Origin at `c51e503c1173c640f4b183c88604fe53e17ad9e6`, not only against their names.

- #156 (`w31-prerelease-is-not-stable`): `prerelease_gate.py` evaluates SemVer candidates against a stable range (`>=` / `==`) and a weak arm that strips pre-release suffixes. It has no dated event store and does not split features from labels at a cutoff T.
- #160 (`mb-zero-reference-pass`): `zero_reference.py` checks whether a candidate effect sits inside a margin of a human interval and whether a zero candidate would pass too. It has no temporal cutoff and no post-decision outcome edge.
- #164 (`mb-intervention-voucher`): `voucher.py` compares a history-replay pass with a per-question what-if voucher on named integer counts (add, sub, or set). It does not date evidence against outcomes and does not treat a post-cutoff label as recall.
- #165 (`w35-stopwatch-is-not-the-mechanism`): `stopwatch.py` takes a scripted work-cost drop as arm A and, on arm B, also requires a claimed-counter move, an unchanged output digest, and an attribution bound. It does not separate pre-T evidence from post-T outcomes.
- #166 (`mb-support-without-takeover`): `ownership.py` measures surviving human-character ownership against a help-count arm after scripted edit events. It is not a dated event store and does not score forecast versus recall.

## Files and how to run

- `forecast_gate.py`: module and CLI (`python3 -B forecast_gate.py fixtures/main.json`). Exit 0 on gate PASS, 1 on gate FAIL, 2 on DENY.
- `test_forecast_gate.py`: unit tests (`python3 -B -m unittest -v test_forecast_gate.py`). 32 tests. No test reads `forecast_gate.py` as source text. Nesting depth is capped at 16 by a bounded walk (DENY `too_deep`, never RecursionError) and is tested in-process.
- `demo.py`: prints the report for `fixtures/main.json` (`python3 -B demo.py`).
- `mutants.py`: nine in-memory behaviour mutants, each run in a child `python3 -B` (`python3 -B mutants.py`). Tally: 9 killed, 0 crash, 0 timeout, 0 survived. A crash or timeout is never counted as a kill. `TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}`. The nine are: `b_reads_post_t`, `outcome_at_t_scored`, `clean_flagged_as_leak`, `date_compare_as_string`, `gate_ignores_arm_b`, `b_window_t_plus_1`, `gate_ignores_class`, `duplicate_name_check_off`, `depth_cap_disabled`.
- `fixtures/main.json`: four planted cases in the table above.
- `fixtures/bad/`: 26 bad fixtures covering the DENY codes. Bad input is DENY: exit 2, empty stdout, one stderr line `DENY <code>: <detail>`. Ids and fields are type-checked before any dict or set lookup (`type(x) is int` and the same for other types, so a bool is not an integer). Codes include: usage, unreadable, bad_utf, not_json, duplicate_key, too_deep, too_large, too_many, too_long, unknown_field, missing_field, bad_type, bad_version, bad_on_expiry, bad_date, bad_role, bad_weight, bad_expected, bad_outcome, duplicate_id, duplicate_name, self_label.
- `SHA256SUMS`: sha256 of every other file here; run `sha256sum -c SHA256SUMS` inside this folder.
- Stdlib only. No network, no install step, no runtime chance source, no wall-clock metric.

Demo stdout sha256, recorded from two identical runs (exit 0):

`b6f061a3629b114a7a4b7c094524c6cfb852436f509e23ef3d1a5ee718966430`
