# Handoff Debt structured notes — seven-field contract + dirty-git check (Top KEEP-with-caveats)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint wave13 Top **#1**  
**Verdict**: **Top KEEP-with-caveats** — upstream **structured_notes** field contract and **no-change vs dirty tree** contradiction logic sketched in pure Python; playground does **not** ship OpenHands, litellm, Docker, SWE-bench harness, trajectory **dataset**, or the upstream experiment harness.

## Upstream pin (honest — clean-room)

| Field | Value |
|-------|--------|
| Upstream | [anjilab/agent-handoff-debt](https://github.com/anjilab/agent-handoff-debt) |
| Pin SHA | `f5fc2c7400ab6e5864e27c1f5a1868c83c53bab2` |
| License | **MIT** ([LICENSE](https://github.com/anjilab/agent-handoff-debt/blob/f5fc2c7400ab6e5864e27c1f5a1868c83c53bab2/LICENSE) @ pin) — **Copyright (c) 2026 Dipesh KC and Anjila Budathoki** |
| Attribution in playground | [`NOTICE.md`](./NOTICE.md) — pin reference; no upstream code vendored |
| Paper | [arXiv:2606.02875](https://arxiv.org/abs/2606.02875) — *Handoff Debt: The Rediscovery Cost When Coding Agents Take Over Interrupted Tasks* |
| Vendoring | **NONE** — upstream harness depends on Docker/OpenHands/SWE-bench; we **do not** vendor that stack |

Authoring tip commit on playground default branch: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` — this experiment branches from that tip without rewriting history.

## Real mechanism (Checker framing)

- Upstream **`structured_notes`** handoff view renders seven string fields inside `=== PREVIOUS AGENT STRUCTURED HANDOFF NOTES ===` (see upstream `structured_notes.py` `_render_record` @ pin): **`problem_understanding`**, **`work_completed`**, **`evidence_observed`**, **`observed_failures_or_error_evidence`**, **`remaining_uncertainty`**, **`rollback_notes`**, **`recommended_next_action`**.
- Playground adds an explicit **`dirty-git contradiction check`**: derive dirtiness from **`git status --short` porcelain** via `git_status_is_dirty` — **untracked-only (`??`) counts as dirty**; empty porcelain is clean. Notes must not claim a **clean / no-change / no-uncommitted-changes** tree when porcelain is non-empty (including **`??` only**).
- Four handoff views in the paper harness: **repository only**, **raw trace**, **summary notes**, **structured notes** — we document the **structured** contract only; no view builder port.

### Paper / corpus numbers (cite honestly)

| Claim | Label in playground |
|-------|---------------------|
| **6,665** recorded runs in the public trajectory corpus (225 predecessor + 6,120 primary + 320 repeated takeovers) | **VERIFIED (count only)** @ upstream README @ pin — not a recomputation of paper tables in this repo |
| Pooled **6665-row medians** / sprint **dig-stats**: **repo_only** solved **39.3%**, median **107** agent events, **1.96M** prompt tokens | **UNVERIFIED** — playground did **not** recompute from Hugging Face tables (forbidden: **dataset**, SWE-bench re-run); no dig-stats job in CI |
| Note views ≈ **−43%** token cost vs repository-only (sprint shorthand) | **UNVERIFIED** in playground — paper reports **42–63%** prompt-token reductions depending on successor/view ([Table 2](https://arxiv.org/abs/2606.02875)); repeated-takeover appendix reports **−43%** on **median agent events** for structured notes (Table 4), not identical to token wording — treat sprint **−43% tokens** as **card shorthand**, not re-derived here |

### ALLOW (this experiment)

- Document pin, paper, ALLOW/FORBID, clean-room honesty (no Docker/SQLite/OpenHands vendoring).
- Pure **seven-field** record validation + **`validate_structured_handoff_record(git_dirty, fields)`** dirty/clean contradiction gate.
- Unittest green under `experiments/2026-11-04/60-handoff-debt-notes/` only.

### FORBID (hard)

- OpenHands, **litellm**, Docker, SWE-bench, trajectory **dataset** loaders, **daemon** harness, DSH, Feishu, **SQLite**
- Generic **done/fixed** word-lint as a merge product (**#61** / verification territory — not this folder)
- Forbidden stack + headcount Soft→Top conflation
- **Do not touch** open **PR #10** — paths under **`experiments/2026-11-03/`** (Copilot trajectories / AgentBaton park).
- **Do not touch** merged **PR #11** — [`01-agentbaton-failure-escalate-handoff.md`](../01-agentbaton-failure-escalate-handoff.md) on `main`.

## Pure-fn sketch (playground)

Module: [`handoff_debt_notes_pure.py`](./handoff_debt_notes_pure.py)

```text
STRUCTURED_FIELDS  # seven upstream field names

git_status_is_dirty(status_short) -> bool   # ?? untracked => dirty
validate_structured_handoff_record(fields, status_short=...) -> HandoffConsistencyResult
validate_structured_handoff_record(fields, git_dirty=...) -> HandoffConsistencyResult
check_dirty_git_contradiction(git_dirty, fields) -> HandoffConsistencyResult
```

| Check | When (sketch) |
|-------|----------------|
| **`missing_field:*`** | Any of the seven keys absent |
| **`dirty_git_contradiction:*`** | Porcelain dirty (incl. **`??` only**) and notes contain a no-change / clean-tree / **no-uncommitted-changes** phrase |
| **`clean_git_contradiction:notes_claim_dirty_tree`** | not dirty but notes assert uncommitted/dirty tree |
| **`overconfident_status`** | Combined fields collapse to a single forbidden status token |

Tests: [`test_handoff_debt_notes_pure.py`](./test_handoff_debt_notes_pure.py):

```bash
cd experiments/2026-11-04/60-handoff-debt-notes
python3 -m unittest test_handoff_debt_notes_pure.py
```

## Sibling links (folder names — not PR numbers)

| Experiment | Link |
|------------|------|
| AgentBaton failure escalate (markdown) | [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) |
| Four Bridges deception checklist | [02-four-bridges-deception-observation-checklist.md](../02-four-bridges-deception-observation-checklist.md) |
| PCP shared-human ask queue | [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) |
| Nunchi `look_again` (wave12 Top sketch) | [54-nunchi-look-again](../54-nunchi-look-again/) *(parallel branch when merged)* |
| PAIRL extractive `#rpt` (wave12 Top sketch) | [55-pairl-extractive-rpt](../55-pairl-extractive-rpt/) *(parallel branch when merged)* |
| a2acompress accounting (wave12 Soft) | [59-a2acompress](../59-a2acompress/) *(parallel branch when merged)* |
| **This folder** | [60-handoff-debt-notes](./) |

## Checker-ready honesty (KEEP-with-caveats)

**KEEP**

- Pin SHA + MIT + paper arXiv:2606.02875 linked; **clean-room** (no upstream harness vendoring).
- Seven-field names match upstream structured handoff record @ pin.
- Dirty-git contradiction check is explicit and unittest-covered.
- Sprint **dig-stats** medians and **−43% token** shorthand labeled **UNVERIFIED** in playground; **6,665 run count** only **VERIFIED** via upstream README @ pin.

**Caveats / UNVERIFIED**

- No LLM summarizer, evidence packet builder, or checkpoint freeze — only post-hoc consistency on provided fields + dirty flag.
- Phrase lists are a **subset** of upstream validation; source-file evidence consistency from upstream is **not** ported (would need checkpoint facts, not git short status alone).
- Pooled **39.3% / 107 / 1.96M** and note token deltas **not** recomputed here.

## Status

- [x] Design note (this file)  
- [x] Pure-fn sketch + unittest  
- [ ] Complete (no upstream submodule; **do not merge** this PR by agent)

**Model (completion summary)**: composer-2.5
