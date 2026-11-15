# Orchestra (theme) — multi-agent orchestration vs role-contract authority (Soft design note)

**날짜**: 2026-11-04  
**Source (Soft KEEP — theme overlap only)**: Usage Sprint **Orchestra** slot — **multi-agent orchestration** themes overlap the **PASS-is-claim / role-contract** family (Agent Role Contracts on open Origin PR #43). **Soft pointer (ideas only — not run, not Top):** [3338902669-ops/agent-orchestra](https://github.com/3338902669-ops/agent-orchestra) — **Apache-2.0**, **★93**, last push **2026-10-23** (public GitHub metadata this session; playground **does not** clone, install, or benchmark).

**Code**: **NONE** — markdown design note only; no agent-orchestra harness or coordinator runtime in playground.

## Soft KEEP rationale (honest Top / Soft)

| Layer | This session |
|-------|----------------|
| **Top (Team OS / ARC only — not Orchestra Top)** | Team OS **Ork (Orchestrator)** naming; open PR #43 **Agent Role Contracts** upstream **“A PASS does not grant execution permission.”** — **Top KEEP #3 for ARC**, not for Orchestra. |
| **Soft KEEP (Orchestra)** | Borrow **ideas only** from [agent-orchestra](https://github.com/3338902669-ops/agent-orchestra): role-labeled agents, coordinator **delegation**, task decomposition — map to **Ork → Smith → Checker**. **Soft pointer pinned; still not Top runnable** (no local run, no tier promotion). |
| **Not Top (Orchestra)** | **Do not** treat coordinator success, task completion strings, or nested delegation traces as **Checker KEEP** or Origin merge authority — same family as ARC **PASS ≠ execution permission** (PR #43). |

Playground **does not** clone or run agent-orchestra this turn.

---

## Theme overlap → Team OS (Ork → Smith → Checker)

Orchestration patterns (role + goal + coordinator delegation) align with **declaration vs execution** separation — same family as ARC preflight, different surface:

| Orchestration theme (generic) | Ork | Smith | Checker |
|------------------------------|-----|-------|---------|
| **Coordinator / conductor** | Owns brief, task split, **who** may write vs read-only review | — | Does not inherit “coordination succeeded” as proof |
| **Specialized executor agent** | Declares **write scope** + handoff pointers before launch | Implements inside scope; fills **evidence** refs ([01](./01-agentbaton-failure-escalate-handoff.md)) | Replays SHAs/CI — not Smith narrative |
| **Nested delegation** | Ork may spawn parallel Smith lanes or Cloud Agent runs | Each lane keeps **distinct** `run_id` / obligation id | **Per-lane** verdict; no rollup PASS from parent chat |
| **Task pipeline “done”** | **`completion_claim`** sketch only when done-when table satisfied | Submits **`handoff_artifact`** | **`certified_complete`** vs **`unknown`** — orchestration trace ≠ certificate |
| **Role contract preflight (sibling #32, PR #43)** | Publishes bundle/task scope before Smith edits | Stays inside declared write scope | ARC-style **PASS** = consistent **declarations** only — **not** tool allow-list |

### PASS ≠ authority (orchestration edition)

1. **Coordinator output is a claim**, not forge head — same stance as ARC PASS ≠ execution permission (PR #43) and Mandate **Missing evidence** ([01](../2026-11-01/01-mandate-agent-run-checklist.md)).
2. **Delegation depth ≠ review independence** — Smith (implementer) and Checker (reviewer) stay **declared separately** even when Ork nested three “agent” labels in one sprint thread.
3. **Coordinator policy is Ork sketch** — Checker still needs **`relied_on`** pointers ([02](../2026-11-02/02-sbus-version-check-board-rule.md)), not orchestration prose alone.

**Cross-links (markdown only):**

- **Handover / Waybill** enforcement sketches — open wave7 PR #37 / #36; offline doc verify complements declaration preflight (#32 on PR #43), not merged here.
- **Evidence-guided recovery (#29)** — open PR #40: ambiguous tool outcomes vs orchestration “task returned OK string”.
- **PCP ask queue ([07](./07-pcp-shared-human-ask-queue-checklist.md))** — JJ bandwidth orthogonal to coordinator delegation.
- **Origin PR #10** — **do not edit** PR #10 body or Cody trajectory columns.

---

## Sample observation row (orchestration episode — checklist sketch)

Log **one row per coordinator delegation burst** (nested agent call, parallel Smith lanes, or sprint wave handoff). **Log only** — no Orchestra runtime.

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `run_id` | string | Cloud Agent / Team OS run id |
| `coordinator_slot` | string | Ork or lead agent id |
| `delegated_to` | string | Smith lane or sub-agent slot |
| `task_sketch` | string | One-line objective — no transcript dump |
| `orchestration_outcome` | enum | `delegated` \| `completed_claim` \| `failed` \| `handoff` |
| `declaration_preflight` | enum | `not_run` \| `pass` \| `fail` \| `n/a` — ARC / #32 when wired (PR #43) |
| `checker_stance` | enum | `unproven` \| `certified_complete` \| `unknown` \| `park` |
| `pass_treated_as_authority` | bool | **Must be false** in healthy rows — log violations explicitly |
| `relied_on` | string | Pointer ids + SHAs used for Checker replay |
| `notes` | string | Link to `log_path`; sibling PR refs |

### Example row (**example** — fictional)

| label | run_id | coordinator_slot | delegated_to | task_sketch | orchestration_outcome | declaration_preflight | checker_stance | pass_treated_as_authority | relied_on | notes |
|-------|--------|------------------|--------------|-------------|----------------------|----------------------|----------------|----------------------------|-----------|-------|
| **example** | `ca-run-orch-33f1` | `ork-wave8` | `smith-docs-33f1` | Add Soft design note #33 under `experiments/2026-11-04/` | `completed_claim` | `not_run` | `unproven` | false | `origin/main@a3d5441` | Coordinator reported “done”; Checker waits for open PR URL + head SHA — [agent-orchestra](https://github.com/3338902669-ops/agent-orchestra) cited **Soft ideas only**, not run |

---

## Soft park (do not implement in wave8)

| Topic | Pointer | Intent |
|-------|---------|--------|
| **C-BASE** | [arXiv:2610.33349](https://arxiv.org/abs/2610.33349) | Next Soft/Top pass placeholder — no harness in this PR. |
| **SpecGate** | [thanhtung2693/specgate](https://github.com/thanhtung2693/specgate) | **Pin-only** if a future turn needs spec-gate overlap with declarations — **skip** when ambiguous vs ARC (#32, PR #43). |
| **Orchestra Top runnable** | [agent-orchestra](https://github.com/3338902669-ops/agent-orchestra) | **Soft pointer only** — Top tier (clone/demo log) **parked**; no Soft→Top flip in this PR. |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Installing or benchmarking [agent-orchestra](https://github.com/3338902669-ops/agent-orchestra)  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or open sibling sketches **#8–#32** (reserved on Origin PR #19–#43 branches)  
- **Origin PR #10** (AgentBaton / Copilot trajectory)—**leave PR #10 alone**  

---

## Status

- [x] Planning (Orchestra **theme** vs role-contract **authority** Soft sketch)  
- [ ] In Progress (no orchestration runtime)  
- [ ] Complete  

**Relied on:** `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (`main` tip at branch); PR #43 ARC README **PASS ≠ execution permission** — **Top (ARC only)**; [agent-orchestra](https://github.com/3338902669-ops/agent-orchestra) — **Soft KEEP (theme overlap + Soft GH pointer)**, **not Top**.

**Next step:** Log orchestration episodes with **`pass_treated_as_authority=false`**; pair with #32 ARC preflight when PR #43 lands — no Orchestra Top promotion until a future turn runs and tiers a demo log.
