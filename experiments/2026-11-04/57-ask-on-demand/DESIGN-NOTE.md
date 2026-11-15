# Ask on Demand (AOD) — Soft design note (cite-only)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint wave12 Soft **#1**  
**Paper**: [Ask on Demand: Targeted Peer Communication for Parallel Agentic Systems](https://arxiv.org/abs/2610.41378) (Yang et al., arXiv:**2610.41378**)

**Tier**: **Soft KEEP** — arXiv **ID + exact title**; §3.2 **(need, known, decision)** request schema **cite-only**. Abstract / method skim **Soft UNVERIFIED** beyond public arXiv text on 2026-11-04.  
**Soft→Top**: **forbidden** (this note does not promote any Soft sketch to Top).

**Code (playground)**: **NONE** — markdown design note only; no AOD gate, BM25 peer retrieval, AppWorld/WebShop harness, or paired-continuation training in playground.

**Playground tip at authoring**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (default branch at branch cut; history not rewritten).

---

## Paper pointer (citation only; no runs today)

From the public abstract and §3 on [2610.41378](https://arxiv.org/abs/2610.41378):

- **Problem:** Parallel LLM agents keep useful discoveries in **private execution histories**; advance summarization / shared memory can drop details whose relevance appears only later.
- **AOD idea:** **Demand-driven peer communication** — when a specific information need arises, the requester asks a **targeted peer**; upon an **approved** request, the framework retrieves evidence from peer **completed records**, selects one peer, and returns an **evidence-grounded** reply (not a broadcast of full histories).
- **When to ask:** A lightweight **gate** (paper: ~0.6B) learns **APPROVE / DENY** from **paired team continuations** (same state, approve vs deny the same request), with labels from **final team task score** and **inference cost** when scores tie — playground **does not** train or ship this gate.
- **Benchmarks (cite-only):** AppWorld and WebShop — paper Table 1: AOD **beats Independent** on selected task metrics **in all four** model×benchmark settings; **vs LTS (Adapted)** task metrics are **not** universally ahead (**4B AppWorld: LTS leads** on TGC/SGC per paper text), while the paper reports **lower total tokens than LTS in all four** settings. Playground **does not** reproduce Table 1 or other baselines.

Title verified from [arxiv.org/abs/2610.41378](https://arxiv.org/abs/2610.41378) on 2026-11-04. Numeric table cells in the paper are **cite-only** if referenced elsewhere.

---

## Request schema (§3.2 — cite-only; not a playground API)

When the frozen task model selects peer help, the paper defines a structured request as:

\[
q_{i,t} = (\mathrm{need}, \mathrm{known}, \mathrm{decision}) = \mathcal{M}(h_{i,t})
\]

| Field | Paper meaning (Soft cite) |
|-------|---------------------------|
| **`need`** | Missing fact or lead the requester must resolve |
| **`known`** | Requester’s relevant observations and prior peer replies, **distinguishing them from assumptions** |
| **`decision`** | What the requester **plans to do next** depending on the answer |

The gate **does not** edit \(q_{i,t}\); it only decides **APPROVE** (execute once as written) or **DENY** (continue locally; later asks still allowed). Playground **does not** implement `ask_peer`, BM25 \(\operatorname{rel}(q,c)\), or peer answering calls.

---

## Soft Team OS analogy (parallel agents; markdown only)

AOD is **peer-to-peer** under parallel exploration — distinct from **shared-human** clarification in [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) (JJ bandwidth, withdrawable human ask).

| AOD concept (Soft) | Team OS observation hook (no runtime) |
|--------------------|----------------------------------------|
| **(need, known, decision)** tuple | When Smith lanes ask each other (or Ork routes a peer question), log a **one-line structured sketch** — not chat paste — mirroring the three fields |
| **Gate APPROVE/DENY** | Treat unsolicited peer ping storms like **unapproved** comms; “worth the inference cost?” is a **policy memo**, not a trained 0.6B gate here |
| **Completed records only** | Peer evidence from **finished** sub-runs (commit, test log, artifact path) — align with pointer handoffs ([01](../01-agentbaton-failure-escalate-handoff.md)) |
| **Single selected peer** | One consult target per approved ask — avoid N-way transcript fan-out ([05](../05-parallact-shared-repo-handoff-checklist.md) multi-writer stress is orthogonal) |
| **Evidence-grounded reply** | Answers cite **excerpt + pointer**; requester verifies — Checker reads refs, not paraphrase ([01-mandate-agent-run-checklist.md](../../2026-11-01/01-mandate-agent-run-checklist.md) Missing evidence sketch) |
| **Team outcome vs ask presence** | Gap alone ≠ worth asking; paper ties worth to **downstream team score + cost** — pairs with verified progress / escalate paths ([06](../06-care-escalate-verified-progress-checklist.md)) |

**Explicit non-promotion:** Do **not** Soft→Top this note into any Top peer-bus, gate trainer, or AppWorld replay — conceptual rhyme only.

---

## ALLOW / FORBID (this experiment)

### ALLOW

- Cite [2610.41378](https://arxiv.org/abs/2610.41378) by **exact title** and ID.
- Document **(need, known, decision)** schema and **APPROVE/DENY** gate role at Soft tier.
- Team OS **observation** hooks and sibling markdown cross-links under `experiments/2026-11-04/` only.

### FORBID (hard)

- **Code port**, pseudo-Top **implementation sketch**, AppWorld/WebShop **training harness**, gate fine-tuning, or benchmark **reproduction claims**
- **Soft→Top** of this note or cited paper mechanisms
- **DSH**, Feishu, SQLite, **daemon**, **headcount**
- **Do not touch** open **PR #10** — paths under **`experiments/2026-11-03/`** (Copilot trajectories checklist).
- **Do not touch** merged **PR #11** — [`01-agentbaton-failure-escalate-handoff.md`](../01-agentbaton-failure-escalate-handoff.md) body on `main`.

---

## Sibling links (folder names — not PR numbers)

| Experiment | Link |
|------------|------|
| AgentBaton failure escalate | [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) |
| PCP shared-human ask queue | [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) |
| CARE verified progress | [06-care-escalate-verified-progress-checklist.md](../06-care-escalate-verified-progress-checklist.md) |
| DALA round arbiter (Top sibling branch) | [56-dala-round-arbiter](../56-dala-round-arbiter/) *(wave12 parallel branch — not on `main` until landed)* |
| OnTrack + progress bar (Soft flat note) | [52-ontrack-unreliable-progress-bar-soft-design-note.md](../52-ontrack-unreliable-progress-bar-soft-design-note.md) *(wave11 parallel branch — not on `main` until landed)* |
| hier-memo agents (Soft flat note) | [45-hier-memo-agents-soft-design-note.md](../45-hier-memo-agents-soft-design-note.md) *(wave10 parallel branch — not on `main` until landed)* |
| **This folder** | [57-ask-on-demand](./) |

---

## Checker-ready

| Check | Expected |
|-------|----------|
| Tier | Header states **Soft KEEP** and **Soft→Top forbidden** |
| Paper | arXiv **2610.41378**, **exact title**, link; **cite-only** numbers |
| Schema | **(need, known, decision)** attributed to paper §3.2 — **not** implemented |
| Code | **NONE**; no gate/BM25/harness claims |
| Forbidden scope | No DSH/Feishu/SQLite/daemon/headcount; no PR #10/#11 edits |
| README | Index row **#57**; sibling links use **folder / file names** |

---

## Status

- [x] Soft KEEP design note (this file)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** If a future **Top** tier needs peer ask routing or gate training, open a **separate** Top doc with verified scope — do not merge this Soft note upward.

**Model (completion summary)**: composer-2.5
