# w27-ranked-conflict-set

A small stdlib-only experiment: what does a reader see when shared memory **collapses** a
disagreement to one value, versus when it **surfaces** the ranked conflict set at the same budget?

## Credit and licence

Method idea from *Surfacing Disagreement Beats Resolving It: A Gated Ablation Study of
Provenance-Weighted Memory for Multi-Agent Debate* (Khan, Ziaullah; Khalid, Abdul Rehman; Lal,
Shrestha Nischal; Vanchhay, Nheng; Mozumder, Md Ariful Islam; Kim, Hee-Cheol),
[arXiv 2611.22461](https://arxiv.org/abs/2611.22461), v1 of 17 Nov 2026. The abstract page carries the
licence arXiv nonexclusive-distrib 1.0, so only the method is borrowed: no text and no code are copied
beyond the short attributed quotes below, and no harness was pinned (the abstract says one is released;
none was located). Quotes from the abstract:

- "retrieval returns one winning fact and the disagreement disappears before any agent sees it"
- "preserving contradictions and passing the ranked conflict set to the debate, rather than collapsing it to a winner"

This is a clean-room method sketch on a tiny synthetic fixture, **not a reproduction**. Only the abstract
page was read for this draft. Paper figures are not reproduced and appear only as UNVERIFIED entries under
`on_unmeasured` in `evidence.json`.

## What it does

- A `Store` with one contract (`write`, `read`, `snapshot`) holds fixture entries: id, writer, field,
  value, score, a `poisoned` label (for scoring only, never shown to a reader) and an optional expiry.
  Writers are fixture rows; one writer (`w_poison`) is adversarial. There is no model call anywhere.
- **Rank key** (declared by the fixture, deterministic): score descending, then id ascending. This is
  **not** the paper's provenance weighting. There is no trust gate and no provenance router.
- Two policies read the **same snapshot at the same k** (the top-k entries of the queried field):
  - `collapse` passes one entry, the top-ranked one;
  - `surface` passes the ranked conflict set: one entry for each distinct value inside the top-k.
- The **scripted reader** is fixed. One distinct value: `ADOPT` it. Several distinct values:
  `ESCALATE` with the list of values; it never names a winner. No value: `HOLD`.
- **on_expiry: DENY.** A query whose `read_at` is after its `deadline`, or a retrieved entry whose
  `expires` is before `read_at`, gives the decision `DENY` (the CLI still exits 0: the report holds the
  decision). A policy that returns more than k entries, or an entry outside the retrieved top-k, raises
  `DENY budget_exceeded`.
- Malformed input (missing or unknown keys, duplicate JSON keys, wrong types, bool or text as a score or
  time, empty or whitespace ids, duplicate ids, k below 1, unknown or repeated policy, on_expiry other
  than DENY) prints one line `DENY <code>: <detail>` on stderr and exits 2.

## Run

```
cd experiments/2026-11-18/w27-ranked-conflict-set
python3 -B -m unittest -v test_conflict_set
python3 -B demo.py
python3 -B mutants.py
python3 -B conflict_set.py fixtures/main.json
```

## Results (measured on the synthetic fixtures, k=2)

| policy | correct | poison adopted | escalated | held | conflicts visible to reader |
|---|---|---|---|---|---|
| collapse | 4 | 2 | 0 | 1 | 0 |
| surface | 3 | 0 | 3 | 1 | 3 |

`fixtures/main.json` has 12 entries and 7 queries. Collapse adopts the poison on `q_region` (the poison
has the top score) and on `q_log` (equal scores, the poison id sorts first). Surface turns both, and
`q_owner`, into `ESCALATE`. `q_backup` shows the retrieval-cap effect: a poisoned third entry is outside
k=2, so neither policy sees it. `fixtures/expired.json` gives `DENY` for a passed deadline and for an
expired retrieved entry. `evidence.json` holds the counts and the paper figures marked UNVERIFIED.

## Limits

- Surface pays for visibility with escalations, including one on a query where collapse was right.
- A conflict outside the top-k is invisible to both policies; k is the budget.
- Synthetic fixture, hand-set scores, exact string equality for "same value". No claim about any
  real model, dataset or the paper's numbers.
- The expiry rule reads the retrieved top-k, so an expired entry inside it denies both policies alike.
