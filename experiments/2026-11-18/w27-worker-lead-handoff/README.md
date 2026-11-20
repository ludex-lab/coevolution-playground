# w27-worker-lead-handoff

A small stdlib-only experiment: when workers retrieve both sides of a factual conflict, does the lead
that sees only their handoff packets notice it? Thesis: **the workers having seen both claims is not
evidence the lead did.**

## Credit and licence

Method idea from arXiv [2611.22245](https://arxiv.org/abs/2611.22245) (v1 of 17 Nov 2026, licence CC BY 4.0
on the abstract page). Only the method is borrowed: no text and no code are copied beyond the short
attributed quotes below, and no code was located. Quotes from the abstract:

- "facts retrieved by workers may be missing from the evidence available to the lead for a joint conclusion"
- "Worker-to-lead handoffs are a central target for improving conflict detection in multi-agent LLMs"

This is a clean-room method sketch on a tiny synthetic fixture, **not a reproduction**. Only the abstract
page was read for this draft. The paper's figures, its three models and its document-review tasks are not
reproduced and appear only as UNVERIFIED entries under `on_unmeasured` in `evidence.json`.

## What it does

- A fixture plants conflicts: two claims about one entity and attribute with different values, plus
  filler documents about other things. Each case runs one of three frozen layouts over the same documents:
  - `single_agent`: one scripted agent reads the whole union itself (no packet);
  - `delegated_same`: one worker holds both claims, the other worker holds neither;
  - `delegated_split`: the two claims sit with different workers.
- Each scripted worker writes a **handoff packet from its own context only**, by a fixture-declared rule:
  order its documents by id (`id_asc` or `id_desc`) and report the first `budget`. Fillers can crowd a claim
  out, so a worker can drop a claim it retrieved.
- The **lead sees only the packets**, never the raw documents. The scripted detector flags a conflict only
  when the lead's evidence holds two different values for the case entity and attribute. It never names a
  winner.
- The **evidence-flow profiler** reports two things separately per case: (i) both claims were retrieved
  anywhere (the union of worker contexts) and (ii) the lead detected the conflict.
- **Verdict**: `PASS` only when the lead detected the conflict. Both retrieved but the lead missed is
  `FAIL` with reason `handoff_failure`, never a pass. Retrieval alone is not a pass.
- **on_expiry: DENY.** A worker with no packet (`null`) gives `DENY missing_packet`; a packet whose
  `expires_at` is before the fixture's `now` gives `DENY expired_packet` (no wall clock; a packet that
  expires exactly at `now` is still valid). DENY rows still report the profiler's retrieval column. The report
  is still printed; the CLI exits 2 when any row is DENY, and `demo.py` exits 0 on purpose because it
  demonstrates DENY rows.
- Malformed input (duplicate JSON keys, missing or unknown keys, wrong types, unknown layout, rule or
  worker, duplicate ids, a packet missing for an assigned worker, a window that ends before it starts, a
  layout that does not match the assignment, claims with equal values, a filler that repeats the conflict,
  on_expiry other than DENY) prints one line `DENY <code>: <detail>` on stderr and exits 2.
- The two exit-2 cases are told apart by stream, not by code: a DENY row exits 2 with the report on stdout and an empty stderr, while malformed
  input exits 2 with an empty stdout and one `DENY <code>:` line on stderr (the same word as a DENY decision, so read the stream, not the
  word). This is a README convention only; no test claims it is machine-checkable.
- Text values share one text rule with `mb-certified-region-delta`: control (including C1), format (zero-width), surrogate,
  private-use, line and paragraph separator characters are rejected, as is any space other than a plain space, and HANGUL FILLER U+3164 and
  BRAILLE PATTERN BLANK U+2800 are rejected by code point (`DENY bad_text`). Korean text is accepted. Other look-alikes stay accepted: U+115F,
  U+1160, U+FFA0, U+034F, U+17B4, variation selectors, U+180B, and Cyrillic or Greek letters that look Latin (for example Cyrillic `о`).
- No network, no model call, no votes or ensembles, no hashing or signing, no pip or venv.

## Distinct from

- **w27-ranked-conflict-set**: shared-memory collapse versus surfacing a retrieved conflict set at equal k.
  Here nothing is collapsed in memory; the question is whether a conflict the workers jointly retrieved
  reaches the lead through worker-to-lead packets.
- **w15-handoff-gate**: a pre-lead gate that routes on evidence completeness. Here there is no gate or
  routing; the measure is whether both *conflicting claims* reach the lead.
- **w21-unused-contradiction**: a single trajectory where a flag is not a repair. Here there are several
  agents and the failure is loss at the handoff, before any flag exists.
- **w17-source-authority**: a per-field authorized source sets the value. Here no source is trusted and no
  value is chosen; the failure is a claim dropped in a packet.
- **mb-ledger-rules**: rules that pick the current fact and scrub a deleted one from a ledger. Here there
  is no ledger and no deletion.

## Run

```
cd experiments/2026-11-18/w27-worker-lead-handoff
python3 -B -m unittest -v test_handoff
python3 -B demo.py
python3 -B mutants.py
python3 -B handoff.py fixtures/main.json
```

## Results (measured on the synthetic fixtures)

`fixtures/main.json`: 12 documents, 3 planted conflicts, 9 cases (each conflict under each layout).

| layout | cases | both retrieved | lead detected | PASS | FAIL (handoff) |
|---|---|---|---|---|---|
| single_agent | 3 | 3 | 3 | 3 | 0 |
| delegated_same | 3 | 3 | 2 | 2 | 1 |
| delegated_split | 3 | 3 | 1 | 1 | 2 |

Both claims are retrieved in 9 of 9 cases, the lead detects the conflict in 6 of 9, and the other 3 are
`FAIL handoff_failure`. In `c2_same` the one worker that held both claims reports a packet crowded by a
filler, so one claim is dropped. In `c2_split` one worker's packet drops its claim. In `c3_split` both
workers drop theirs. `c1_split` and `c3_same` show a packet rule that reports every claim, so the lead
detects. `fixtures/expired.json` (now=30) gives `DENY expired_packet` for one case and
`DENY missing_packet` for another, and `PASS` for the other two.

## Limits

- Retrieval is fixed by the layout, so both claims are always retrieved in valid fixtures; the sketch shows
  loss at the handoff, not retrieval gains from delegation. The `not_retrieved` branch exists and is
  tested below the validator, but fixtures cannot reach it.
- Packet rules are two hand-written orderings plus a budget; real workers summarise differently.
- Synthetic fixture, exact string equality for "same value", one conflict per case. No claim about any real
  model, dataset or the paper's numbers.
- A missing or expired packet from an idle worker (one holding no claim) still gives DENY.
- `totals.<arm>.both_retrieved` counts every case row where both claims were retrieved, DENY rows included, because retrieval is fixed by the
  layout and DENY rows still report it. On `fixtures/expired.json` `delegated_same` shows cases 1, both_retrieved 1, deny 1 and
  `delegated_split` shows cases 2, both_retrieved 2, deny 1. Read `deny` next to it. A test pins these totals.
