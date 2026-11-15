# OnTrack + Unreliable Progress Bar — Soft design note (cite-only)

**날짜**: 2026-11-04  
**Tier**: **Soft KEEP** — arXiv **ID + exact title** only; abstract/metadata skim **Soft UNVERIFIED** beyond that.  
**Soft→Top**: **forbidden** (this note does not promote any Soft sketch to Top).

**Code**: **NONE** — markdown design note only; no OnTrack monitor, progress-bar eval harness, or benchmark re-run in playground.

---

## Papers (Soft cite-only)

| arXiv | Exact title | Soft use |
|-------|-------------|----------|
| [2610.12375](https://arxiv.org/abs/2610.12375) | OnTrack: Real-Time Monitoring and Intervention in LLM Agent Trajectories via Streaming Structure-Aware Optimal Transport | Citation + light Team OS observation hooks only |
| [2609.08589](https://arxiv.org/abs/2609.08589) | The Unreliable Progress Bar: Can LLM Agents Reliably Report Task Progress Throughout Execution? | Citation + light Team OS observation hooks only |

Titles verified from [arxiv.org/abs/2610.12375](https://arxiv.org/abs/2610.12375) and [arxiv.org/abs/2609.08589](https://arxiv.org/abs/2609.08589) on 2026-11-04 (Asia/Seoul). Paper-reported numbers (e.g. OnTrack AUROC / abort savings; progress-bar reliability gaps) are **not** reproduced or vendored here—**cite-only** if needed elsewhere.

---

## Soft Team OS analogy (conceptual; no Soft→Top)

Two papers sit on opposite sides of the same Team OS tension: **what actually moved forward** vs **what the run claims moved forward**.

| Paper (Soft) | Concept (abstract-level) | Team OS observation hook (markdown only) |
|--------------|--------------------------|------------------------------------------|
| **OnTrack** | Streaming monitor compares live agent steps (and step dependencies) to reference or schema-only signals; flags **loops, stalls, repeated tools without new results** before the run finishes | Ork/Smith runs benefit from **log-backed stall signals** (repeated tool pattern, no new artifact) distinct from model narrative—“intervene early” as a *design* idea, not a deployed monitor |
| **Unreliable Progress Bar** | LLM agents’ **self-reported task progress** can diverge from ground-truth execution progress | Handoffs and wrap-style summaries should treat **self-rated % complete** as **unverified** until tied to commands, tests, or artifacts—**honesty about unknown progress**, not a scored progress UI |

**Pairing (Soft):** OnTrack-style monitoring asks whether the **trajectory structure** still looks like progress; the progress-bar paper asks whether **verbal progress reports** are trustworthy. Team OS already separates **verified** subgoal bullets (see [06](./06-care-escalate-verified-progress-checklist.md) observation columns) from free-form status text—this note only names that pairing at Soft tier.

**Explicit non-promotion:** Do **not** Soft→Top this note into Wrap-up sketch **#37**, stallwatch sketch **#43**, or any Top mandate from those rows—conceptual rhyme only.

---

## Out of scope

- **Soft→Top** of this note or cited papers  
- Vendoring OnTrack / progress-bar **code**, datasets, or claiming **reproduced benchmarks**  
- **DSH**, Feishu, SQLite, daemon, headcount  
- **PR #10**, **PR #11**, and paths under **`experiments/2026-11-03/`**  
- Cody trajectory columns, runtime abort policies, or automated progress scoring in playground  

---

## Status

- [x] Soft KEEP design note (papers cited by ID + title)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** If a future **Top** tier needs streaming abort or progress calibration, open a **separate** Top doc with verified scope—do not merge this Soft note upward.

---

## Checker-ready

| Check | Expected |
|-------|----------|
| Tier | Header states **Soft KEEP** and **Soft→Top forbidden** |
| Papers | Table lists both arXiv IDs, **exact titles**, links, **Soft cite-only** |
| Titles | Match arXiv abstract pages (no invented titles) |
| Code | **NONE**; no benchmark reproduction claims |
| Forbidden scope | No DSH/Feishu/SQLite/daemon/headcount; no PR #10/#11 or `experiments/2026-11-03/` dependency |
| Promotion | No Soft→Top of Wrap-up **#37** or stallwatch **#43** |
| README | Index row **#52** only; **#8–#51** reserved for open PRs **#19–#62** |
