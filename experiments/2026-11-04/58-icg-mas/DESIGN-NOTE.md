# ICG-MAS — Soft design note (metric method only)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint wave12 Soft **#2**  
**Upstream (method pin)**: [zihao-jing/ICG-MAS](https://github.com/zihao-jing/ICG-MAS) @ **`02d432a70b3a0f2cdb319ffce84ec92339a1de09`** (short: `02d432a`) — README documents *Measuring the Irreducible Communication Gap in Multi-Agent LLM Systems* (preprint target ICLR/AAAI 2027; **no public arXiv ID** in pinned README on 2026-11-04).

**Tier**: **Soft KEEP** — **ICG metric definition + interpretation** from pinned upstream README **cite-only**. Abstract / hypotheses / benchmark tables **Soft UNVERIFIED** beyond that public text on 2026-11-04.  
**Soft→Top**: **forbidden** (this note does not promote any Soft sketch to Top).

**Code (playground)**: **NONE** — markdown design note only; **no** ICG computation port, **no** `src/eval/` harness, **no** protocol runners, **no** Sharded MuSiQue / Silo-Bench / GPQA replay in playground.

**Playground tip at authoring**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (default branch at branch cut; history not rewritten).

---

## Why borrow the metric (cite-only; no runs today)

From the pinned [ICG-MAS README](https://github.com/zihao-jing/ICG-MAS/blob/02d432a70b3a0f2cdb319ffce84ec92339a1de09/README.md):

- **Problem:** Multi-agent evals often mix **communication necessity** (task structure) with **protocol effectiveness** (this chat pattern vs that one).
- **ICG role:** A **task-side** score for when communication is **structurally necessary**, stated to be independent of model, protocol, and token budget in the upstream doc.
- **Playground stance:** Use ICG as a **design vocabulary** for Team OS handoffs (who holds which evidence units) — **not** as a reproduced benchmark correlation or F1 delta claim.

Numeric hypothesis tables (H1–H3), benchmark F1 gaps, and protocol ablation results in upstream docs are **cite-only** if referenced elsewhere; playground **does not** reproduce them.

---

## ICG metric (method — ALLOW scope)

From pinned upstream README (notation preserved):

```
ICG(x) = |S*(x)| - max_i |S*(x) ∩ U_i|
```

| Symbol | Upstream meaning (Soft cite) |
|--------|------------------------------|
| **`S*(x)`** | Minimum-cardinality evidence set sufficient to answer question **`x`** correctly |
| **`U_i`** | Evidence units visible to agent **`i`** |
| **`max_i \|S*(x) ∩ U_i\|`** | Best single-agent overlap with the minimal support |

| ICG | Interpretation (Soft cite) |
|-----|----------------------------|
| **0** | Some agent alone holds all minimally required evidence → communication **not structurally necessary** |
| **> 0** | At least one evidence unit in the minimal support lies **outside every single-agent view** → communication **structurally necessary** |

**Soft properties (upstream claims — not verified here):** task-side only; conservative at ICG=0; higher ICG ↔ more distributed minimal evidence.

**Explicit ALLOW boundary:** Document and apply this **definition + interpretation** in markdown observation hooks only. **Do not** port `data_loader.py` ICG computation, shard loaders, or experiment CLI from upstream.

---

## Soft Team OS analogy (distributed evidence; markdown only)

ICG separates **task-side evidence dispersion** from **whether our comms protocol helped** — complementary to peer/human ask patterns elsewhere in this index.

| ICG concept (Soft) | Team OS observation hook (no runtime) |
|--------------------|----------------------------------------|
| **`U_i` shards** | Map Smith lanes / repos / log partitions to “what this agent could see without reading others’ private runs” |
| **`S*(x)` sketch** | For a handoff question, list **minimal pointer set** (commits, test logs, artifact paths) a Checker would need — not transcript dumps ([01](../01-agentbaton-failure-escalate-handoff.md)) |
| **ICG = 0 memo** | If one lane already holds all required pointers, **skip** peer broadcast — rhymes with targeted ask ([57-ask-on-demand](../57-ask-on-demand/)) vs human queue ([07](../07-pcp-shared-human-ask-queue-checklist.md)) |
| **ICG > 0 memo** | Missing units are **distributed** — name which lane must receive which pointer before claiming “team can answer” |
| **Δ vs protocol** | Upstream ties **`Δ = F1_centralized − F1_isolated`** to ICG — playground logs **verified progress** ([06](../06-care-escalate-verified-progress-checklist.md)), not F1 reproduction |

**Explicit non-promotion:** Do **not** Soft→Top this note into DALA auction cores, AOD gates, or any Top eval harness — conceptual rhyme only.

---

## ALLOW / FORBID (this experiment)

### ALLOW

- Cite [zihao-jing/ICG-MAS](https://github.com/zihao-jing/ICG-MAS) at pin **`02d432a70b3a0f2cdb319ffce84ec92339a1de09`** for **ICG metric method** (formula, symbols, interpretation table).
- Light **Team OS observation** hooks and sibling markdown cross-links under `experiments/2026-11-04/` only.

### FORBID (hard)

- **Harness port**, **`run_experiment.py`**, variant A/B eval loops, protocol modules, dataset loaders, or **full eval harness** claims
- **Soft→Top** of this note or upstream experiment stack
- **DSH**, Feishu, SQLite, **daemon**, **headcount**
- **Do not touch** open **PR #10** — paths under **`experiments/2026-11-03/`** (Copilot trajectories checklist).
- **Do not touch** merged **PR #11** — [`01-agentbaton-failure-escalate-handoff.md`](../01-agentbaton-failure-escalate-handoff.md) body on `main`.

---

## Sibling links (folder names — not PR numbers)

| Experiment | Wave (honest label) | Link |
|------------|---------------------|------|
| hier-memo agents (Soft flat note) | wave10 | [45-hier-memo-agents-soft-design-note.md](../45-hier-memo-agents-soft-design-note.md) *(parallel branch — not on `main` until landed)* |
| OnTrack + progress bar (Soft flat note) | wave11 | [52-ontrack-unreliable-progress-bar-soft-design-note.md](../52-ontrack-unreliable-progress-bar-soft-design-note.md) *(parallel branch — not on `main` until landed)* |
| DALA round arbiter (Top sibling branch) | wave12 | [56-dala-round-arbiter](../56-dala-round-arbiter/) *(parallel branch — not on `main` until landed)* |
| Ask on Demand (Soft folder note) | wave12 | [57-ask-on-demand](../57-ask-on-demand/) *(parallel branch — not on `main` until landed)* |
| AgentBaton failure escalate | day index | [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) |
| PCP shared-human ask queue | day index | [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) |
| **This folder** | wave12 Soft **#2** | [58-icg-mas](./) |

---

## Checker-ready

| Check | Expected |
|-------|----------|
| Tier | Header states **Soft KEEP** and **Soft→Top forbidden** |
| Pin | Upstream **`02d432a70b3a0f2cdb319ffce84ec92339a1de09`**; method-only scope |
| Metric | **ICG(x)** formula + symbol table — **not implemented** in playground |
| Harness | **FORBID** — no eval port, no benchmark reproduction |
| Code | **NONE** |
| Forbidden scope | No DSH/Feishu/SQLite/daemon/headcount; no PR #10/#11 edits |
| README | Index row **#58**; sibling links use **folder / file names**; waves labeled honestly |

---

## Status

- [x] Soft KEEP design note (this file)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** If a future **Top** tier needs ICG computation on real shards, open a **separate** Top doc with verified harness scope — do not merge this Soft note upward.

**Model (completion summary)**: composer-2.5
