# Nunchi `look_again` — pure-fn HOLD|GO sketch (Top KEEP-with-caveats)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint wave12 Top **#1**  
**Verdict**: **Top KEEP-with-caveats** — mechanism pinned and sketched; playground does **not** ship Nunchi runtime, Discord/MCP, or a `turn.py` port.

## Upstream pin (honest)

| Field | Value |
|-------|--------|
| Upstream | [mentatzoe/nunchi](https://github.com/mentatzoe/nunchi) |
| Pin SHA | `e1392a9a3d36eee3e714c5d26dcd877cc2fefed7` |
| License (repo files) | Dual **MIT / Apache-2.0** in tree (per upstream) |
| GitHub `license` field | **`NOASSERTION`** — do not infer SPDX from the GitHub UI alone |
| Test evidence (upstream, cited) | **1031 pass** at pin (recorded from sprint pin card; **UNVERIFIED** in this playground run) |

Authoring tip commit on playground default branch: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` — this experiment branches from that tip without rewriting history.

## Real mechanism (Checker framing)

- The presend recheck API is **`Turn.look_again()`** in upstream `src/nunchi/turn.py` at pin **`def look_again` → lines 1175–1199** (do not anchor on ~1008–1033 — that band is module docstring / bind prose, not the method def).
- Behavior (conceptual): before the first visible post/reaction, expand `direction="new"`; **`new_messages(page)`** counts **all** events with `type == "message"` (no author filter). If that count is zero (e.g. reactions only), return **`None` → GO**; else return a page → **HOLD** and re-decide. Failed expand never blocks send.
- **Name collision:** **`Pipeline.look_again`** in upstream `pipeline.py` is a separate **timed pause re-judge** (`look_again_seconds`) — not this presend recheck. Checker must not conflate the two.
- There is **no** symbol named `presend_recheck` — do not invent one. **`look_again`** is the correct name.
- Upstream **`turn.py` is marked obsolete** (architecture review; library may not extend it). This folder is a **pure reimplementation** of the HOLD|GO decision slice plus an **`answer_candidates`** field carried from attention context — **not** a port of `Turn`, scheduling, or host I/O.
- Pre-attention **suppress** remains a **method-level note** only: V2 attention can **SUPPRESS** before a participant turn is offered (`attention.py` pipeline). We do not port suppress routing here.

### ALLOW (this experiment)

- Pure **HOLD \| GO** when the **board revision advanced** since compose and interim events qualify (reactions alone do not HOLD — aligns with upstream **`new_messages`** counting `type == "message"` only).
- **Sketch delta:** [`look_again_pure.py`](./look_again_pure.py) additionally ignores messages whose `author` / `participant` equals `self_participant`. Upstream **`new_messages()` does not filter by author** — document this as an intentional playground simplification, not upstream parity.
- Pass-through **`answer_candidates`** on the verdict (typed-attention analog; see upstream `attention_questions.answer_candidates` usage in `attention.py`).
- Document pin, caveats, and unittest-green sketch under `experiments/2026-11-04/` only.

### FORBID (hard)

- `turn.py` / `Turn` **port** or daemon harness
- Discord / MCP integration
- `service_worker` / `turn_server` daemon
- Dashboard, memory store, LLM judge
- Forbidden stack: DSH, Feishu, SQLite, daemon, headcount Soft→Top conflation
- **Do not touch** open **PR #10** — live Origin title *Morning Brief 2026-11-03: Copilot trajectories intervention checklist*; park paths under **`experiments/2026-11-03/`** (e.g. Copilot trajectories checklist; AgentBaton park-await fields on that PR branch only).
- **Do not touch** merged **PR #11** — live Origin title *docs: AgentBaton failure-escalate handoff sketch (2026-11-04)* → [`01-agentbaton-failure-escalate-handoff.md`](../01-agentbaton-failure-escalate-handoff.md) on `main`.

## Pure-fn sketch (playground)

Module: [`look_again_pure.py`](./look_again_pure.py)

```text
look_again_pure(
  board_revision_at_compose,
  board_revision_now,
  action_kind,
  interim_events,
  answer_candidates,
  already_looked_again=False,
  expand_failed=False,
) -> LookAgainVerdict(decision, answer_candidates, ...)
```

| `decision` | When (sketch) |
|------------|----------------|
| **HOLD** | Board advanced **and** ≥1 interim **message** from someone other than `self_participant`, visible `action_kind`, first look, expand ok |
| **GO** | Board unchanged, no qualifying messages, second look, non-visible kind, or `expand_failed` (failed check never blocks send — upstream parity) |

Tests: [`test_look_again_pure.py`](./test_look_again_pure.py) — run from this directory:

```bash
python3 -m unittest test_look_again_pure.py
```

## Sibling links (folder names — not PR numbers)

| Experiment | Link |
|------------|------|
| AgentBaton failure escalate (markdown) | [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) |
| Four Bridges deception checklist | [02-four-bridges-deception-observation-checklist.md](../02-four-bridges-deception-observation-checklist.md) |
| PCP shared-human ask queue | [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) |
| **This folder** | [54-nunchi-look-again](./) |

## Checker-ready honesty (KEEP-with-caveats)

**KEEP**

- Pin SHA and real API name (`Turn.look_again`) documented with line anchor at pin.
- ALLOW/FORBID aligned with sprint forbidden stack and park boundaries.
- Minimal pure function + unittest that passes locally in this folder.

**Caveats / UNVERIFIED**

- Upstream **1031 tests** not executed in playground CI for this PR.
- GitHub **NOASSERTION** license badge vs dual in-tree licenses — human must reconcile before redistribution.
- `board_revision_*` is a playground stand-in for host “room advanced” — not a literal Nunchi event log schema.
- `answer_candidates` tuple is carried for attention parity; values are **not** computed from real projection in this sketch.
- **`self_participant` author filter** in the sketch is **not** upstream `new_messages()` behavior (see sketch delta above).
- Obsolete upstream module: production integrations should follow current `AGENTS.md` / architecture review, not extend `turn.py`.

## Status

- [x] Design note (this file)  
- [x] Pure-fn sketch + unittest  
- [ ] Complete (no Nunchi submodule; no merge of this PR by agent)

**Model (completion summary)**: composer-2.5
