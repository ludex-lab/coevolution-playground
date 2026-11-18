# mb-ledger-rules

Memory for an agent is usually judged by its final answer. This sketch judges the **evidence
bundle** a question receives. A small store holds synthetic facts, each with a source, a period in
which it held, and a reliability tag (`high`, `medium`, `low`). Explicit rules, not a model, decide
which value is current, which source wins a conflict, and what a deletion removes. A probe gets
only the bundle those rules produce. A baseline with no ledger replays every raw turn that matches
the probe. The check is by substring: does a deleted or superseded value appear anywhere in the
serialized bundle?

Clean-room method sketch of the idea in **LEDGER** (arXiv 2611.20927, Islam, Shuvo, Waseem and
Abrahamsson, CC BY 4.0, paper only; the abs page listed no code repository); **not a
reproduction**. Python 3 standard library and `unittest` only. No network, clock, randomness,
answering model, paid API, Mem0 or LongMemEval. In the paper a language model proposes facts; here
the fixture lists them. No upstream code was copied or run, and no upstream result is claimed:
external figures live only in `evidence.json` under `on_unmeasured`, marked UNVERIFIED. Every count
below is computed by `ledger.py` from `fixtures/main.json`.

## Run

```
python3 -B -m unittest -v test_ledger     # 57 tests
python3 -B demo.py                        # deterministic summary
python3 -B mutants.py                     # mutation self-check: killed 72/72, exit 0
python3 -B ledger.py fixtures/main.json   # per-probe report
```

Exit 0 with a report. A bad fixture or command line prints `DENY <code>: <detail>` on stderr,
nothing on stdout, and exits 2.

## Rules

1. **Current value.** A fact holds on a day when `start <= day <= end` (`end: null` is open).
   Out-of-period facts are never current, so a superseded fact drops out. Among in-period facts the
   winner has the highest trust, then the later `start`, then the later turn day. A remaining tie
   between different values is reported as `conflict` with both facts, not guessed.
2. **Source trust.** Each fact carries its own tag; there is no per-source table. An in-period
   low-trust fact beats an expired high-trust fact; an in-period high-trust fact beats a low-trust one.
3. **Describe-only deletion.** A request names `subject`, `attribute`, `source` and a period, plus a
   free-text note, and never a value. It matches the live facts with those three fields and an
   overlapping period. The single match is removed and its value is scrubbed (case-insensitive,
   replaced by `[removed]`) from **every raw turn** held at that moment. Only a description is
   retained afterwards (a tombstone).
   - zero matches: `DENY no_match`; two or more: `DENY ambiguous`; nothing is partly deleted.
   - note text that restates the value: `DENY restates_value`.
   - another live fact holds the same value (scrubbing could not be complete): `DENY value_shared`.
4. **Bundle.** `current` (one fact), `conflict` (tied facts), `none`, or `fallback`: when no fact
   holds and the probe sets `fallback: true`, the scrubbed raw turns up to the probe day that match
   any probe term are added. Raw turns never appear next to a current fact.
5. **Baseline.** `replay_bundle` returns every raw turn up to the probe day that matches a term,
   unscrubbed, with no facts and no rules.

Timeline on each day: turns arrive, then deletions run, then probes are answered.

## Fixture (fictional)

8 turns over days 1-7, 7 facts, 1 deletion on day 8, 8 probes:

- `nightly_job.python_version`: `3.8` (high, days 1-4, stale), `3.11` (high, from day 5), `3.9` (low
  hearsay, from day 5).
- `deploy.region`: `eu-west` (high, days 1-3, stale), `us-east` (low hearsay, from day 4).
- `staging_db.admin_password`: a synthetic secret stated on day 2 and repeated in a day-4 reminder;
  the day-8 request describes it as "the staging database password I gave you on day 2".
- `staging_worker.cache_size`, plus probes on attributes with no fact (`connection_limit`,
  `retry_budget`) to exercise the raw-turn fallback.

## Results (computed from the fixture)

| question | ledger | full replay |
|---|---|---|
| probes | 8 | 8 |
| probes after the deletion | 5 | 5 |
| deleted value found in evidence | 0 | 2 (p4, p5) |
| superseded value found in evidence | 0 | 3 (p1, p2, p6) |
| raw turns sent | 5 (all scrubbed fallback turns) | 16 |
| p1 python version (day 7) | `3.11` (in period, high trust) | t1, t5, t6: `3.8`, `3.11` and `3.9` |
| p2 deploy region (day 7) | `us-east` (in period, low trust, beats stale high) | t3, t7: both regions |
| p3 admin password, before deletion | the secret (current fact) | t2, t4 |
| p4 admin password, after deletion | no fact; t2 and t4 with `[removed]` | t2, t4 with the secret |

## Done-when

- (a) the in-period higher-trust fact wins over a stale fact and a lower-trust one (p1, p2).
- (b) after the describe-only deletion the deleted value is in no ledger bundle for probes p4-p8,
  fallback raw turns included.
- (c) full replay carries the deleted value in p4 and p5 and a superseded value in p1, p2, p6.
- (d) no model, no paid API, no Mem0 or LongMemEval, no paper accuracy claimed.
- Malformed input (missing field, duplicate JSON key, non-boolean `fallback`, wrong type, empty or
  padded id, duplicate id, `end < start`, unknown trust tag, unknown turn, value absent from its turn)
  gives `DENY` and exit 2; so do `fixtures/bad_*.json` (9 files).

## Files

- `ledger.py`: strict loader and validator, rules, `Ledger`, baseline, report, CLI.
- `test_ledger.py`: 57 tests, including a test that `ledger.py` imports only the standard library.
- `mutants.py`: in-memory mutation self-check, 72 mutants.
- `demo.py`: deterministic summary with the three done-when lines.
- `fixtures/main.json`, `fixtures/bad_*.json`: the fixture and nine fixtures that must DENY.
- `evidence.json`: paper figures, `on_unmeasured`, UNVERIFIED.

## Limits

- Tiny synthetic fixture written by the author of this sketch; the numbers show the rules work as
  designed, not how any system performs. They are not comparable with the paper's.
- Facts are hand-listed, so extraction errors, which a model-based layer would add, are out of scope.
- Matching is exact on `subject`, `attribute`, `source` and period overlap; no paraphrase handling.
  A deletion that names a source or period loosely is denied rather than guessed.
- Scrubbing replaces the literal value, case-insensitively. A paraphrase of the secret in a raw
  turn would remain; turns that arrive after a deletion are not scrubbed.
- Substring leak checks catch literal values only.
- One fact per (subject, attribute, source, period) is assumed when deleting; overlapping duplicates
  are an `ambiguous` DENY by design.
