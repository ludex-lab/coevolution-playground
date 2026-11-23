# mb-occupancy-cap-per-bucket

A burst should not take over a bounded memory. A memory with a fixed number of slots takes in a stream of
timestamped village items, each with a salience score. If it evicts only by score, one short burst of bright items
(fireworks at the festival) can fill almost every slot and push out quieter items that a later question needs (who
repaired the well). The fix sketched here is a hard per-time-bucket occupancy cap. The stream is cut into
fixed-duration buckets, and no bucket may hold more than `bucket_cap` slots, so a burst holds only its best few items
and the rest of the day stays in memory.

## Credit and licence

Method sketch of arXiv [2611.25649](https://arxiv.org/abs/2611.25649):
"KeyMem: Temporal Occupancy Control for Robust Streaming VideoLLM Memory"
by Wei Song, Yuxin Cao, Xiao Cheng, Christy Jie Liang, Xi Zheng and Leo Yu Zhang. The paper is licensed CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). No repository is listed on the abstract page.

- This is **not a reproduction**. Only the method is borrowed, in paraphrase: fixed-duration temporal buckets, each
  with a hard cap on the slots it may hold. No text or code was copied, and no model or video was used.
- The paper's optional **secret-key sampler** (keyed sampling of survivors) is **left out entirely**. Every choice
  here is deterministic, and there are no keys, seeds or random draws.
- Rank normalisation of a base score is not modelled either, because fixture scores already share one integer scale.
- No paper number is verified. The author-reported figures appear only as `UNVERIFIED` under `on_unmeasured` in
  `evidence.json`.

## The three arms

All three see the same stream and the same memory size (`capacity` slots). Rank order is `(score, t, id)`: the lower
score leaves first, then the older item, then the smaller id.

| arm | role | rule |
|---|---|---|
| `score_only` | weak | When memory is over capacity, evict the lowest-ranked item. No time structure. |
| `recency` | weak | When memory is over capacity, evict the oldest arrival (plain FIFO, global capacity only). |
| `bucket_cap` | strict | Bucket = `t // bucket_seconds`. If the new item's bucket holds more than `bucket_cap`, that bucket loses its lowest-ranked item. If memory is still over capacity, the most crowded bucket loses its lowest-ranked item. A tie among equally crowded buckets goes to the lowest-ranked of their lowest items. |

The per-bucket cap comes from the paper. The overflow rule, the tie-break and the `recency` arm are this sketch's own
declared choices, not claims about the paper.

## The gate

Each case declares what was planted: `burst`, `none` or `need_over_cap`. Queries name the items a later question
needs. A case is closed when:

- `bucket_cap` never holds more than `bucket_cap` slots in a bucket or more than `capacity` in total, and
- `burst`: under `score_only`, the most crowded bucket holds more than the cap and at least one needed item from an
  earlier bucket is gone, while `bucket_cap` still holds every needed item;
- `none`: both `score_only` and `bucket_cap` hold every needed item;
- `need_over_cap`: more needed items share one bucket than the cap admits, so `bucket_cap` does drop one. This is
  the cost of the cap, shown on purpose.

Per arm, `FAIL` means the arm lost a needed item in a `burst` or `none` case (or, for `bucket_cap`, broke its cap).
The report ends with `closed: N / N on the declared gate` and `gate: PASS` only when every case is closed. The exit
code is 0 for PASS and 1 for FAIL.

## Results (synthetic fixtures)

`fixtures/village.json`, a Naru village day:

| case | planted | score_only | recency | bucket_cap |
|---|---|---|---|---|
| festival_burst | burst | 6 of 6 slots in the fireworks minute; loses `well_fixed`, `bridge_crack`, `lost_cat` | loses `well_fixed`, `bridge_crack` | at most 2 per bucket; loses nothing |
| quiet_market | none | loses nothing | loses `bread_sold` | loses nothing |
| busy_council | need_over_cap | loses nothing (all 4 fit) | loses nothing | loses `school_hours` (3 needed in one bucket, cap 2) |

The result is `closed: 3 / 3`, with arm gates `score_only` FAIL, `recency` FAIL and `bucket_cap` PASS.
`fixtures/more.json` (two bursts, equal scores, Korean text) is also `closed: 3 / 3`, and both weak arms lose a needed
item in 2 of 2 planted bursts. These are counts of planted cases, not rates, and say nothing about video models.

## How to run

```
python3 -B occupancy_cap.py fixtures/village.json          # markdown report; exit 0 PASS, 1 FAIL, 2 DENY
python3 -B occupancy_cap.py --json fixtures/village.json   # the same result as JSON
python3 -B demo.py                                          # both fixtures; identical bytes every run
python3 -B -m unittest                                      # the suite
python3 -B mutants.py                                       # mutation run; TIMEOUT 300 s, on_expiry DENY
```

Stdlib only, system `python3 -B`, no network, no subprocess beyond the local test and mutant runs.

## Contract

- Missing, unreadable, oversized, non-UTF-8 or malformed input is `on_expiry=DENY`: exit 2, empty stdout, one stderr
  line starting `ERROR <code>:`. The checks cover duplicate JSON keys, NaN, floats, booleans used as numbers, unknown
  or missing keys, bad ids, control or invisible characters, out-of-order timestamps, `bucket_cap` above `capacity`,
  and queries that name unknown or repeated items. Every cap declares `on_expiry` DENY.
- Equal timestamps are in order. The arrival order is the list order.
- Text is NFC-normalised, so the Korean NFD and NFC forms read the same.
- `mutants.py` declares `TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}`. A mutant whose suite run reaches it is
  reported TIMEOUT and is never counted as killed.

## Not a remake

`53-shut-up-budget-cooldown` caps sends and gaps, `w21-advice-cooldown` rations tokens, `w27-worker-lead-handoff`
cuts a packet to the first n by id, and `mb-verify-the-verifier` audits a FIFO against spec clauses. This sketch bounds
how much of a memory one time bucket may hold.

## How a village would use it

A village memory that stores notes about the day could put a cap on each hour. Then a festival, a storm of chat or a
flood of identical alerts can take only its share of memory, and quieter facts survive for later questions. The cost
is real. When one hour truly holds more needed facts than its cap, one is dropped (`busy_council`), so the bucket
size and cap have to be chosen per village. That choice is not measured here.

## Limits

- Synthetic items and scores only, with no video, tokens, attention scores or model.
- No key sampler, no rank normalisation, no adaptive adversary.
- The overflow rule and tie-break are declared choices. Other choices (oldest bucket first, proportional shares) are
  not tested.
- Bucket size and cap are declared in fixtures. How to choose them is `on_unmeasured`.
- No paper figure is reproduced or verified.

## Files

- `occupancy_cap.py`: loader, the three arms, the gate, the report and the CLI
- `test_occupancy_cap.py`: unittest suite
- `demo.py`: deterministic report on both valid fixtures
- `mutants.py`: mutation run
- `evidence.json`: source, licence, measured counts, `on_expiry`, `on_unmeasured`
- `fixtures/village.json`, `fixtures/more.json`: valid fixtures
- `fixtures/bad_*.json`: malformed fixtures, each DENY with its own error code
