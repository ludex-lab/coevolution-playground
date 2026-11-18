# w26-verification-transport

A verifier that is correct on the full (native) view of an execution is not evidence that the
same verifier stays correct when that execution reaches it through an abstraction boundary.

Clean-room method sketch of [arXiv 2611.18471](https://arxiv.org/abs/2611.18471) v1
("Do Verifier Judgments Survive Abstraction? Measuring Verification Transport for LLM Agent
Evaluation", CC BY 4.0);
not a reproduction. Python 3 standard library and `unittest` only. No network, clock,
randomness, model, LLM, paid API, pip or background process. No upstream code exists or was
used. Every count below is computed from `fixtures/*.json` by `transport.py`. The paper's figures
and quotes live only in `evidence.json` under `on_unmeasured` (UNVERIFIED).

## Run (from this folder)

```
python3 -B -m unittest                          # 66 tests
python3 -B demo.py                              # deterministic report; stdout sha256 pinned in a test
python3 -B mutants.py                           # mutation self-check: killed 106/106, exit 0
python3 -B transport.py fixtures/executions.json
python3 -B transport.py fixtures/bad_missing_view.json   # DENY missing_view, exit 2
```

Exit 0 with a report. A missing, unmatched, expired, unreadable or malformed view or fixture
(including a repeated step id, a non-boolean `expired`, a repeated JSON key at any level, or a
blank id or text field) prints
`DENY <code>: <detail>` on stderr, nothing on stdout, and exits 2 (`on_expiry=DENY`: a view that
was never produced is never scored and never turns into a pass).

## Model

- **Frozen execution**: task, trajectory id, ordered steps (each with evidence items `name -> bool`),
  outcome text, ground truth (`pass`/`fail`) and criterion (the evidence items that must all be
  true). The fixture's ground truth must agree with the criterion on the full record, else DENY.
- **Native view**: every step with its evidence.
- **Abstracted view** `abstract(execution, verifier, boundary)`: steps tagged with the boundary
  (`composed_tool`, `delegation`, `compaction`) show no evidence, only their summary if they have
  one. The hidden evidence is returned as provenance. A boundary that hides nothing is DENY.
- **Restored view** `restore(view, provenance, lossy)`: a full restore puts the hidden evidence
  back; a lossy restore returns the item names with their values lost.
- **Verifiers** (fixture rules, no model) read only the criterion and the visible steps, never the
  ground truth. `direct` decides on whatever it sees: it trusts a summary claim for hidden
  evidence and treats unseen, unclaimed evidence as unmet. `grounded` decides only on visible
  evidence and abstains when any required item is unseen.
- **Matched pair**: native and abstracted views of the same execution: the same execution id,
  equal step content (each step's id, tool, evidence, summary and `hidden_by`, compared as plain
  values), and task, trajectory id, step ids, outcome, ground truth, criterion and verifier all
  equal. Any difference is DENY `mismatched_pair`, so an identical copy under a new execution id is
  not a pair. A pair without both views is DENY `missing_view`; an expired view (`"expired": true`)
  is DENY `on_expiry`; an `expired` value that is not a JSON boolean (`1`, `"true"`, `1.0`) is DENY
  `malformed_fixture`.
- **Repeated pair**: the same (execution, verifier, boundary) listed again under a new pair id is
  counted once and reported as `INFO counted_twice: <new id> repeats <first id> (counted once)`.
- **Label** per pair: `stable`; `transport_incorrect` (correct on native, the opposite verdict on
  abstracted); `transport_abstain` (correct on native, abstains on abstracted); or
  `native_not_correct` (excluded from transport counts). Each transport failure is re-verified on
  a full and a lossy restore: `recovered` or `not_recovered`.
- **Summary** per verifier: counts only, with `transport_incorrect` and `transport_abstain`
  reported separately. There is no single score.
- **Ranking** `rank(a, b)`: one verifier is more reliable only if it is no worse on both the
  incorrect and the abstain count. Fewer transport failures bought with more incorrect verdicts
  is `not_ranked`.
- **Native-only suite**: native accuracy is reported, but `transport: unmeasured` and
  `status: unmeasured`. The harness never prints PASS for a suite.

## Fixture (fictional)

`fixtures/executions.json`: four invented executions and eight matched pairs (each execution x
both verifiers).

| exec | task | boundary | what the boundary hides | truth |
|---|---|---|---|---|
| e1 | refund an order and tell the customer | delegation | the subagent's refund step (refund not posted; its summary claims done) | fail |
| e2 | rename three files | composed_tool | both rename steps (summary claims all three renamed) | pass |
| e3 | move a meeting to a free slot | compaction | the free/busy check (no summary) | pass |
| e4 | add an item to a shared list | compaction | a read step the criterion does not need | pass |

`native_only.json` scores two of these on native views only. `bad_mismatched_pair.json`
(outcome differs), `bad_missing_view.json` (no abstracted view) and `bad_expired_view.json`
(abstracted view expired) each give DENY exit 2.

## What it shows (on this fixture only)

| verifier | native correct | stable | transport_incorrect | transport_abstain | full restore recovers | lossy restore recovers |
|---|---|---|---|---|---|---|
| direct | 4 of 4 | 2 | 2 (e1, e3) | 0 | 2 of 2 | 0 of 2 |
| grounded | 4 of 4 | 1 | 0 | 3 (e1, e2, e3) | 3 of 3 | 0 of 3 |

- Both verifiers are perfect on native views, and both lose verdicts at the boundary.
- `direct` fails less often (2 against 3) but every failure is a wrong verdict; `grounded` fails
  more often but only by abstaining. `rank(direct, grounded)` is `not_ranked`.
- A full restore recovers all five failures; the lossy restore recovers none.
- Scoring the same verifiers on native views only says nothing about transport: `unmeasured`.

## r2 changes (input strictness only)

The r1 measurement logic is unchanged and the demo output is byte-identical (same sha256). r2
closes input paths that were scored with exit 0 when they should be DENY exit 2:

- Pair binding: a pair needs the same execution id and equal step content, not only equal frozen
  fields. A drifted summary, evidence value or tool in a second execution can no longer pass as a
  `stable` pair.
- A repeated step id in one execution is DENY `malformed_fixture` (the restore is keyed by step id).
- `expired` must be a JSON boolean (checked by type, since `1 == True` in Python).
- A repeated key in any JSON object is DENY `malformed_fixture` (no last-wins).
- Blank (empty or whitespace-only) ids, task, trajectory id, outcome, tool, criterion items and
  summary texts are DENY `malformed_fixture`.
- The paper title is now given in full.

## Limits

- Four fictional executions and two rule-based verifiers. Nothing here estimates how often real
  verifiers fail at a boundary or how much a restore recovers; the paper's figures are not
  reproduced and stay `on_unmeasured` in `evidence.json`.
- The lossy restore is one simple kind of loss (values gone, names left). Other losses (a subset
  of items, stale values) are not modelled.
- `direct` and `grounded` stand in for protocol behaviours, not for any model or prompt.

## Closest neighbours in this repo

`mb-conversation-loss-oracle` (translation loss between API dialects, not a verifier's verdict on
a hidden slice of one execution), `w23-world-consistent-history` (history edit against world
effect), `w20-fidelity-audit`, `w20-evidence-linked-memory`, `w15-evidence-gate`. None holds one
verifier fixed across matched native, abstracted and restored views of the same execution.
