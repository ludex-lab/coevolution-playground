# HANDRAISER + CAPA — listener interrupt & floor-taking (Soft design note)

**날짜**: 2026-11-04  
**Tier**: **Soft KEEP** — abstract + public arXiv pages only; **Soft→Top forbidden** (no promoted Top repo pin, no vendored code, no runtime harness in playground).

**Team OS / Checker labels:** **HANDRAISER** and **CAPA** name two *Soft patterns* in Team OS vocabulary. They are **not** guaranteed to appear in the arXiv record titles below; the papers introduce **HandRaiser** (method) and **CAPA** (architecture) in the body/abstract.

**Verification:** **Soft UNVERIFIED** beyond abstract skim and arXiv metadata — full PDF, code drops, and benchmark replays were **not** audited for this note.

## Sources (Soft KEEP — cite by arXiv ID + title)

| Team OS label | arXiv | Title (exact) | Authors (arXiv API) | Posted (UTC) |
|---------------|-------|---------------|---------------------|--------------|
| **HANDRAISER** | [2604.06452](https://arxiv.org/abs/2604.06452) | Learning to Interrupt in Language-based Multi-agent Communication | Danqing Wang, Da Yin, Ruta Desai, Lei Li, Asli Celikyilmaz, Ansong Ni | 2026-04-07 |
| **CAPA** | [2609.03923](https://arxiv.org/abs/2609.03923) | Speak for Me: Giving LLMs the Situational Awareness to Participate in a Meeting | Muneeb Khan, Frederic Kirstein, Terry Ruas, Bela Gipp | 2026-09-03 |

**Code (this note):** **Soft paper-only** — no GitHub URL pinned as Top; playground does not ship HandRaiser training, CAPA modules, or AMI replay.

---

## Paper pointer (abstract skim; numbers are citations only)

### HANDRAISER pattern — [2604.06452](https://arxiv.org/abs/2604.06452)

From the public abstract on **Learning to Interrupt in Language-based Multi-agent Communication**:

- Multi-agent LLM traffic is verbose; prior work mostly **compresses the speaker**; this work lets the **listener interrupt mid-generation** (chunked send, listener decides stop vs continue).
- Naïve interrupt-capable LLMs **interrupt too early** (overconfidence); **HandRaiser** learns when to interrupt from rollouts scored by **future reward vs communication cost**.
- Reported on three multi-agent tasks (2-agent text pictionary, 3-agent meeting scheduling, 3-agent debate): **~32.2%** communication cost reduction vs non-interruptible baseline with comparable or better task performance (abstract figure only — not reproduced here).

### CAPA pattern — [2609.03923](https://arxiv.org/abs/2609.03923)

From the public abstract on **Speak for Me: Giving LLMs the Situational Awareness to Participate in a Meeting**:

- **Online meeting delegation:** an LLM represents an absent participant; prompt-only delegates stay silent on **51.4%** of valid talk opportunities (AMI corpus, abstract).
- **CAPA** (Collaborative Agent Predictive Architecture): **Perceiver** updates structured meeting state; **Predictor** forecasts continuation; **Controller** chooses **Silent / Speak** and proposition; **Generator** phrases output; judges + **Recalibrator** patch state from verdicts.
- Episode-level protocol on **137** AMI meetings: silence **51.4% → 2.5%**, credited recovery roughly doubles (**26.1 → 52.2**), hallucination **0.6%** (abstract — not reproduced here).

---

## Soft analogy — Ork → Smith → Checker (light; design memo only)

| Paper idea | Team OS role sketch |
|------------|---------------------|
| Listener **raises hand** / interrupts when enough context is received (**HANDRAISER**) | **Smith** (or worker agent) signals **stop streaming** / **ready to act** to **Ork**-side speaker — bandwidth guard, not a deployed interrupt model |
| **Silent vs Speak** with explicit **floor** and meeting state (**CAPA**) | **Checker** / human gate: when structured state says the represented slot **should** speak, surface one bounded contribution; otherwise **abstain** — complements portfolio **ask queue** ([07](./07-pcp-shared-human-ask-queue-checklist.md)), not a replacement |
| Cost–quality tradeoff on interruption timing | Align with **withdrawable ask** and **escalate** paths ([01](./01-agentbaton-failure-escalate-handoff.md), [04](./04-impassebench-escalate-to-human-ticket-schema.md)) — interrupt/ speak decisions stay **policy sketches** until instrumented |

No claim that Team OS implements HandRaiser training or CAPA’s perceive–act–recalibrate loop; this is **Soft** vocabulary for observation and future checklists.

---

## Observation hooks (optional future rows; no schema mandated today)

When logging multi-agent Team OS episodes, these **Soft** prompts may help offline review (markdown only):

1. **Early cut-off** — Did a consumer agent stop reading / stop tool output before the producer finished, mimicking over-eager interrupt?
2. **Silent abstention** — Did a delegate miss an obvious human or Checker **floor** window despite relevant context in logs?
3. **State vs raw transcript** — Was a decision made from chat length alone without a structured **stance / coverage / floor** sketch?

---

## Out of scope (2026-11-04 wave10 Soft)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Vendoring paper code or pinning a **Top** implementation repo for either paper  
- Editing [experiments/2026-11-03/](../2026-11-03/) or open **PR #10** bodies / Cody trajectory columns  
- **Soft→Top** promotion of either arXiv entry  

**Branch tip at authoring time:** `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (unchanged on `main` when this file was drafted).

---

## Status

- [x] Soft design note (markdown only)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** If parallel agents share one human attention budget, cross-read [07](./07-pcp-shared-human-ask-queue-checklist.md); if multi-writer repo stress appears, cross-read [05](./05-parallact-shared-repo-handoff-checklist.md) — no merge required for ops.
