# w35-stopwatch-is-not-the-mechanism

A later run can look cheaper on a stopwatch (here, a scripted work-cost) while the claimed mechanism never moved, or while the output changed. A stopwatch-only check (arm A) passes such a version. Arm B accepts the cost drop only when the claimed-mechanism counter moved in the claimed direction, the output digest is unchanged, and the saving sits inside an attribution bound.

Synthetic lookup, declarative op lists, planted versions. This shows the mechanism only. It is not evidence of any rate and reproduces no paper number.

## Declared rules

- Versions are declarative lists of ops from a closed set: square, pad, cache, wrong, replay. The harness interprets each list and measures cost and counters itself. It never reads a `cost` or `counters` field from a version.
- A version that declares `cost` or `counters` is DENY `self_reported_measure`, exit 2, empty stdout, one stderr line.
- Work-cost of the interpreted ops: square 10, pad 5, a cache hit 1, wrong 2 (wrong emits `k*k + 1` instead of `k*k`). These costs are harness constants, not version fields.
- `claim` names a mechanism and direction from a closed list (`cache_hits` or `single_read`; `up` or `down`) and a positive integer `saving_per_unit`. An unknown name or direction is DENY.
- The fixture declares at least three input sets. The output digest is sha256 of canonical JSON (`sort_keys=True`, `separators=(",", ":")`) of the harness-computed outputs over every declared set. At least one set is one where a stored constant answer differs.
- Arm A (stopwatch only): PASS iff `after_cost < before_cost`. A cost tie is not faster.
- Arm B (mechanism + digest + attribution), all of:
  - `after_cost < before_cost`
  - the claimed counter moved in the claimed direction (`counter_delta > 0`); a missing, tied, or reversed counter is FAIL
  - the output digest is unchanged versus `before`
  - `cost_saved <= counter_delta * saving_per_unit`
- The fixture declares the expected table for every non-before version before the run. The gate is PASS (exit 0) iff the observed arm A and arm B statuses equal it exactly. Otherwise the run fails (exit 1).
- Expected table for `fixtures/main.json` (`claim`: `cache_hits` up, `saving_per_unit` 9; `before` cost 135, hits 0):

| version | arm A | arm B | why arm B fails (if it does) |
|---|---|---|---|
| cheaper_wrong (cost 63) | PASS | FAIL | output digest changes |
| faster_other_reason (cost 90, hits 0) | PASS | FAIL | claimed counter does not move |
| replayed_output (cost 108, hits 3; first set matches, later sets emit a stored constant) | PASS | FAIL | output digest changes |
| genuine_cache (cost 108, hits 3; cost_saved 27 equals the bound) | PASS | PASS | |
| no_faster (cost 135) | FAIL | FAIL | no cost drop (a tie is not faster) |
| cache_plus_skip (cost 63, hits 3; cost_saved 72 > bound 27) | PASS | FAIL | attribution bound |
| fabricated_counter (standalone bad fixture) | DENY exit 2 | DENY exit 2 | self-reported `counters` field |

- Bad input is DENY: exit 2, empty stdout, one stderr line `DENY <code>: <detail>`. Ids and fields are type-checked before any dict or set lookup, so a list, object, null, bool or float is `bad_type`. A bool is refused before the integer check. Codes include: not_json, duplicate_key, unknown_field, missing_field, bad_type, bad_version, bad_on_expiry, unknown_mechanism, bad_direction, bad_op, bad_expected, bad_input_sets, too_many, too_large (fixture over 32768 bytes), self_reported_measure, out_of_range, duplicate_id, unreadable, usage.
- `on_expiry` must be literally one of `DENY`, `SAFE_FALLBACK`, `ESCALATE`, `HOLD`. Any other value is DENY. The mutant runner's timeout is `{"seconds": 300, "on_expiry": "DENY"}`. A timeout is not a kill, and crashes are counted separately.

## Files and how to run

- `stopwatch.py`: module and CLI (`python3 -B stopwatch.py [--json] fixtures/main.json`).
- `test_stopwatch.py`: unit tests (`python3 -B -m unittest test_stopwatch`). No test reads a source file.
- `demo.py`: prints the report for the fixture, then the standalone `fabricated_counter` DENY (`python3 -B demo.py`).
- `mutants.py`: six in-memory mutants, each run in a child `python3 -B` (`python3 -B mutants.py`).
- `evidence.json`: the declared table, measured results and `on_unmeasured`.
- `fixtures/main.json` and `fixtures/bad/*.json` (23 bad fixtures; unreadable and usage are covered by tests).
- `SHA256SUMS`: sha256 of every other file here; run `sha256sum -c SHA256SUMS` inside this folder.
- Stdlib only, no network, no randomness, no model calls, no wall-clock gate metric.

## Limits

- Cost and every mechanism counter are measured by the harness from the declarative op list it interprets. A version that carries a `cost` or `counters` field is DENY `self_reported_measure`. The harness does not read those numbers from the version.
- Residual: the harness meters only the ops it interprets. Real code needs independent instrumentation, as in the paper: "A build agent that never sees the claim rebuilds the code before and after each PR. Below then measures both versions with plain timing runs, hardware counters and LTTng kernel traces."
- The digest is sha256 of canonical JSON of harness-computed outputs over the declared input sets. A stored constant can match one set and still differ on another.
- Arm B requires a strict cost drop, a counter move in the claimed direction, an unchanged digest, and `cost_saved <= counter_delta * saving_per_unit`. A cost tie is not faster. A missing, tied, or reversed counter is FAIL.
- Work-cost is a scripted stand-in for a stopwatch. Wall-clock time is not a gate metric (`time.perf_counter` is not used as one).
- One synthetic fixture with planted versions. This shows the mechanism, not how often it happens.
- Paper figures are under `on_unmeasured` and UNVERIFIED.

## Source and licence

- Yuvraj Sehgal, Sneh Patel, Mahsa Panahandeh and Naser Ezzati-Jivan, "Below the Stopwatch: Checking the Performance Claims of Coding Agents in the Kernel", [arXiv 2611.31460](https://arxiv.org/abs/2611.31460), arXiv v1 Tue 24 Nov 2026 04:31:41 KST (from Mon 23 Nov 2026 19:31:41 UTC). Licence [nonexclusive-distrib 1.0](http://arxiv.org/licenses/nonexclusive-distrib/1.0/), method-only. The citation_title was read from the abs page meta tags. No repository URL appears on the abs page, so no code was used. This is a method sketch only. No code is copied, and the only text from the paper is the attributed quotes in this README.
- Short quote from the abstract, attributed: "Most such claims also give a reason, such as "cache the result" or "read the file once". A stopwatch can show that code got faster, but not that it got faster for the stated reason."

## on_unmeasured (UNVERIFIED)

- Paper-reported figures from 1,343 runtime-performance PRs in the AIDev dataset: 57.3% of the PRs offer only reasoning or no evidence, and only 31.4% state an effect size; of 82 analyzed PRs, 32 ran faster, 28 showed no clear change and 22 ran slower; the expected signal of the claimed mechanism appeared in 34 PRs (20 in kernel-trace signals alone), and 42 PRs also changed their output; author-reported speed-ups 1.7× and 1.15×: UNVERIFIED, not measured here.
- Real wall-clock, hardware counters, and LTTng kernel traces on kernel PRs: UNVERIFIED (not used).

## Distinct from

- #153 (evidence binding, loose vs strict): about whether a claim is bound to evidence. There is no performance claim and no mechanism counter.
- #155 (verify-the-verifier spec cross-check): a scoreboard that misses a spec assertion. Here a cost drop is checked against a measured mechanism signal and an output digest.
- #159 (`w32-record-manifest-presence`): a measurement-record cover vs a folder listing. That is file presence, not a speed claim.
- #160 (`mb-zero-reference-pass`): a zero-reference threshold beside an equivalence decision. Here the question is whether a cheaper run is the claimed mechanism with unchanged output.
- #162 (`mb-error-propagation-trace`): outcome-only vs per-hop error classes along a chain. Different object.
- Open PR #163, not on main (`w34-mixed-index-crowds-unseen-tools`): retrieval crowding in a tool router's candidate list. Unrelated to performance-claim checks.
- Open PR #164, not on main (`mb-intervention-voucher`): a history-replay pass is not a what-if voucher (wrong record or wrong operator). Different objects (named records, not cost + mechanism counter + digest).
