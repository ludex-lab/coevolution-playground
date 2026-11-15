# MASCAL — prompt-level handoff confidence + recheck (Soft design note)

**날짜**: 2026-11-04  
**Paper**: [Learning Calibrated Confidence for Multi-Agent Collaboration (MASCAL)](https://arxiv.org/abs/2610.39927) (Fan et al., arXiv:2610.39927)

**Code**: **NONE** — markdown design note only; **no MASCAL training code**, no collaboration-architecture harness, and **no reinforcement-learning or calibration-training loop** in playground. Paper claims (calibrated probabilities via RL, confidence-aware weighting, intervention analyses, selective answering / targeted rechecking on three architectures) are **abstract + public HTML/PDF prose cite only — Soft UNVERIFIED** (no runs, no weight checkpoints, no replay of paper benchmarks).

**Scope of this sketch (Soft low KEEP):** Borrow only the **handoff shape**—upstream report carries a **quantitative confidence field**, Checker/Ork uses **prompt-level policy** to choose **trust vs recheck**—**not** the paper’s learned calibration pipeline.

---

## Paper pointer (citation only; no runs today)

From the public abstract on [2610.39927](https://arxiv.org/abs/2610.39927) — playground **does not** train agents, reproduce RL+calibration objectives, or run Web multi-hop / review / fusion architectures:

| Idea (paper) | This sketch (prompt-only) |
|--------------|---------------------------|
| Upstream report $m_i=(t_i,a_i,e_i,c_i)$ with correctness probability $c_i$ | Structured handback adds **`handoff_confidence_sketch`** (0–1 or H/M/L) filled by **prompt + self-report** — **not** claimed calibrated |
| Downstream **trust** upstream vs **launch verification** | Checker/Ork **recheck branch** when $c_i$ below **`θ_recheck`** (policy constant chosen by humans, **not** learned) |
| **Selective answering** / **targeted rechecking** on final confidence | Ork **withholds KEEP** or routes extra Checker pass when final **`answer_confidence_sketch`** low — **procedure only** |
| MASCAL trains $c_i$ with **RL + calibration objective** + **confidence-aware weighting** | **Explicitly out of scope** — no RL, no BCE calibration loss, no masking/up-weighting training |

Playground **does not** implement MASCAL, vend collaboration rollouts, or claim paper accuracy/calibration deltas.

---

## 1) Prompt-level confidence at handoff (Smith → Checker / Ork)

Paper handoff augments text with $c_i\in[0,1]$. Team OS analog without training:

### Handback fields (sketch)

| Field | Type | Definition |
|-------|------|------------|
| `handoff_confidence_sketch` | number \| enum | Agent **prompt-asked** estimate: “How likely is your subtask answer correct?” — **uncalibrated**; Ork treats as **hint**, not proof |
| `confidence_basis` | enum | `self_report` \| `checklist_tick` \| `log_backed` — only `log_backed` pairs with **`proof_anchor`** ([20-soei-evidence-intent-ledger-design-note.md](./20-soei-evidence-intent-ledger-design-note.md) PR #31 when landed) |
| `recheck_requested` | bool | Smith **asks** downstream to verify when self-report low — optional; Checker may override |
| `handoff_artifact` | object | Unchanged: **`workspace_pointer` + `log_path` only** ([01](./01-agentbaton-failure-escalate-handoff.md)) |

### Prompt pattern (Checker/Ork instructions — prose policy, not code)

1. **Require** structured confidence on upstream handbacks to Checker (missing ⇒ treat as **unknown**, default **recheck** on merge-critical claims).
2. **Do not** treat confidence as evidence weight without **`evidence_refs` / R-picks** ([23-replication-corroboration-evidential-dependence-design-note.md](./23-replication-corroboration-evidential-dependence-design-note.md) PR #34 when landed).
3. **Label** in scribe: “MASCAL-shaped **prompt confidence** — **not** paper-calibrated $c_i$.”

**Anti-claim (mandatory):** This sketch **does not** implement MASCAL’s **reinforcement learning**, **joint task+calibration optimization**, or **confidence-aware weighting** during training. Any numeric field is **operational self-report**, not a reproduced calibrated probability.

---

## 2) Checker / Ork — trust vs recheck (no training loop)

Map paper downstream “trust or verify” to existing gates:

| Signal | Checker action (sketch) |
|--------|-------------------------|
| `handoff_confidence_sketch` ≥ **`θ_trust`** (human-set) | Proceed with normal **`proven` / `unproven`** path on **log-backed** claims ([12-pcm-proof-carrying-handoff-day-sketch.md](./12-pcm-proof-carrying-handoff-day-sketch.md) PR #23) |
| `handoff_confidence_sketch` < **`θ_recheck`** | **Recheck branch:** re-read forge pointers, fresh CI/log segment, or **`failure-id`** escalate ([01](./01-agentbaton-failure-escalate-handoff.md)); **do not** approve on prose alone ([16-inter-agent-influence-checker-gate-checklist.md](./16-inter-agent-influence-checker-gate-checklist.md) PR #27) |
| Conflicting high confidence + weak evidence | **`failed`** — confidence **cannot** override missing **`proof_anchor`** (Soei **claim ≠ proof**, PR #31) |
| Repeat low confidence same `failure-id` | AgentBaton-style **escalate** to stronger model / human park ([01](./01-agentbaton-failure-escalate-handoff.md), [04](./04-impassebench-escalate-to-human-ticket-schema.md)) |

**Hysteresis note:** CARE uses separate **`θ_esc` / `θ_ret`** for control transfer ([06](./06-care-escalate-verified-progress-checklist.md)) — orthogonal knobs; do **not** conflate critic $c_t$ with MASCAL $c_i$ without explicit column labels.

### Observation columns (one row per Checker episode)

| Column | Type | Definition |
|--------|------|------------|
| `run_id` | string | Cloud Agent / merge gate id |
| `upstream_confidence_sketch` | number \| null | Raw handback field (uncalibrated) |
| `final_confidence_sketch` | number \| null | Checker/Ork summary after recheck (prompt-filled, not RL) |
| `policy_action` | enum | `trust` \| `recheck` \| `withhold_keep` \| `escalate` |
| `θ_trust` / `θ_recheck` | string | Human policy constants referenced (not learned) |
| `recheck_outcome` | enum | `confirmed` \| `refuted` \| `inconclusive` \| `n/a` |
| `checker_verdict` | enum | `proven` \| `unproven` \| `failed` |
| `relied_on` | `[{ id, version }]` | **Decision-used** board pointers only ([02](../2026-11-02/02-sbus-version-check-board-rule.md)) |
| `notes` | string | `log_path` segment — no transcript dump |

### Example row (**example** — fictional)

| run_id | upstream_confidence_sketch | policy_action | recheck_outcome | checker_verdict | relied_on | notes |
|--------|----------------------------|---------------|-----------------|-----------------|-----------|-------|
| **example** | `0.92` (self_report) | `recheck` | `refuted` | `failed` | see §3 minimal JSON | High self-report but **`forge_head`** moved; recheck found stale CI cite — MASCAL **intervention spirit** only, **no** paper RL |

---

## 3) `relied_on` — **content_tip** + **forge_head** (recheck trigger)

Recheck should compare **claimed content** vs **live forge head**, not chat confidence alone ([04-sbus-observe-checklist.md](../2026-11-02/04-sbus-observe-checklist.md) §7 soft caveat).

**Minimal `relied_on` example** (board pointer IDs — fictional SHAs):

```json
"relied_on": [
  { "id": "origin_pr/24/content_tip", "version": "a3d544105a19e325dbbb2b5d7e2c5edfcb156098" },
  { "id": "origin_pr/24/forge_head", "version": "b7e2c1d0a9f8765432109876543210fedcba9876" },
  { "id": "forge/main/tip", "version": "a3d544105a19e325dbbb2b5d7e2c5edfcb156098" }
]
```

When **`content_tip` = `forge/main/tip`** but **`forge_head` ≠ `content_tip`**, Checker **recheck** path: refresh head read before KEEP; log pointer-chase note — **observe-only** until hard stale reject ([02](../2026-11-02/02-sbus-version-check-board-rule.md)).

---

## 4) Selective KEEP / targeted recheck (Ork policy prose)

Paper: final calibrated confidence supports **withholding** uncertain answers and **directing recheck** where needed. Team OS **prompt-only** analog:

| Ork stance | Condition (sketch) |
|------------|-------------------|
| **KEEP allowed** | Checker **`proven`** + structured evidence + **`forge_head`** matches recheck |
| **Targeted recheck** | Low **`final_confidence_sketch`** OR **`handoff_confidence_sketch` < θ_recheck** — schedule one extra Checker pass (specific log segment / diff), not open-ended retrain |
| **Withhold merge / park** | Recheck **refuted** or **`unproven`** after targeted pass — park ticket ([04](./04-impassebench-escalate-to-human-ticket-schema.md)) |

No claim that withholding reduces error rate by paper-reported margins — cite abstract motivation only.

---

## Soft no runtime caveat

- **This file is a design note only** — no MASCAL repo checkout, no RL trainer, no collaboration rollout harness, no calibration metrics pipeline.
- Paper results (accuracy gains, calibration quality, intervention effects, generalization to deeper chains / smaller models) are **Soft UNVERIFIED** citations from [2610.39927](https://arxiv.org/abs/2610.39927); **not** reproduced here.
- **No RL claim:** playground does **not** run policy gradients, BCE on readout $c$, or confidence-aware token weighting from the paper.
- **No** new bots, Slack wiring, SQLite/DSH ports, or automated merge-gate code.
- **`relied_on`:** Declare **board pointer ID + version** for evidence actually used in KEEP/recheck decisions — prefer **`content_tip` + `forge_head` + `forge/main/tip`** when forge freshness matters ([02](../2026-11-02/02-sbus-version-check-board-rule.md), [04](../2026-11-02/04-sbus-observe-checklist.md) §7).

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Installing MASCAL, training collaboration policies, or replaying paper architectures  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or open sibling sketches **#8–#23** (reserved on Origin PR #19–#34 branches)  
- **Origin PR #10** (AgentBaton / Copilot trajectory)—**leave PR #10 alone**; no `experiments/2026-11-03/` edits  

---

## Status

- [x] Planning (prompt confidence + recheck Soft sketch)  
- [ ] In Progress (no Checker runtime wiring)  
- [ ] Complete  

**Relied on (SHAs):** `a3d5441` (main tip at branch: PCP #7 / merged PR #18); paper [2610.39927](https://arxiv.org/abs/2610.39927) abstract + public HTML cite only — **Soft UNVERIFIED** (no MASCAL implementation; **no RL / no training loop** in playground).

**Next step:** Add Checker prompt bullets for **`handoff_confidence_sketch`** + **`θ_recheck`** tabletop; log one fictional row where high self-report triggers **forge_head** recheck — no merge of this doc required for ops.
