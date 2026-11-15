# Soei — evidence, intent, and hash-chained ledger (Soft design note)

**날짜**: 2026-11-04  
**Paper**: [Soei: Structured Observability of Evidence and Intent for Multi-Agent AI Software Engineering](https://arxiv.org/abs/2610.39468) (Khan & Kumar, arXiv:2610.39468)

**Code**: **NONE** — markdown design note only; **no public Soei implementation** cited for checkout in playground. Paper’s Agenttrail audit at commit `e4ba2da` and corpus replay numbers are **abstract / prose cite only — Soft UNVERIFIED** (no Agenttrail install, no ledger daemon, no PROV graph export wired to Team OS).

## Paper pointer (citation only; no runs today)

From the public abstract and v1.1 preprint prose on [2610.39468](https://arxiv.org/abs/2610.39468) — playground **does not** re-audit Agenttrail, re-run the 45-session corpus, or reproduce ledger throughput:

- **Motivation:** Long multi-step agent work returns the developer to the question **what was actually done, by whom, and whether it is finished**—not what the model said in chat.
- **Agenttrail audit (paper §1 narrative):** Against source at **`e4ba2da`**, nine documented constants/mechanisms hold at file-and-line level; **two event pipelines are never unified**; Map service exposes an **unauthenticated local mutation surface** (paper finding—**not** re-verified here).
- **Corpus (paper §2):** **45** real coding-agent sessions — **102,233** records, **20,577** tool executions, **2,336** human-to-agent episodes. Blind-audited classifier precision **83.3%** and **96.7%**.
- **Gap estimates (paper):** **23.4%** (95% CI **17.1–35.7**) of code-editing episodes end with **no independent check** after the last edit; **57.8%** of agent-marked to-dos **complete after editing** had **no proof in between**.
- **Session / hygiene signals (paper):** **10-minute** timing heuristic for hand-offs recovery **6 of 24** session pairs content lineage links; **42%** of sessions **>24 h**; **48.1%** of transcript bytes past a **2 MiB** replay bound; **1,326** records in **16** sessions contain **credential-like strings**.
- **Soei proposal (paper §3):** Acknowledgement-aware event schema; **hash-chained local ledger**; **W3C PROV-aligned** graph; calibrated inference for attribution/lineage; **verification layer** separating **completion claims** from **proof**.
- **Ledger properties (paper, same corpus):** Ledger **~20%** of raw size; holds **no content or credentials**; verifies **~126k events/s**; **tamper + replay** detected deterministically (paper numbers only).

Playground **does not** implement Soei, ship a hash chain, or export PROV.

---

## 1) Hash-chained ledger sketch (Team OS — markdown only)

Append-only **event records** for Cloud Agent / Team OS runs. Content and secrets stay **out of chain entries**; entries bind **hashes of pointers** and prior chain head.

### Event record (sketch)

| Field | Type | Definition |
|-------|------|------------|
| `seq` | int | Monotonic sequence (local ledger) |
| `prev_hash` | string | SHA-256 of canonical bytes of record `seq-1``(genesis: fixed sentinel) |
| `event_kind` | enum | `tool_outcome` \|+`edit_claim` \| `human_ack` \| `completion_claim` \| `proof_anchor` \| `handoff` |
| `run_id` | string | Stable run / session key |
| `actor_sketch` | enum | `agent` \| `human` \|+`infra` \| `checker_offline` |
| `payload_hash` | string | Hash of **redacted** payload (command exit summary, file path list digest—not file bodies) |
| `pointer_refs` | string[] | `log_path` segments, artifact SHAs, PR URLs—**pointers only** ([01](./01-agentbaton-failure-escalate-handoff.md)) |
| `ack_state` | enum | `pending` \| `acked` \| `n/a` — acknowledgement-aware schema (paper); human/infra ack for sensitive transitions |
| `recorded_at` | string | ISO time from **infra clock**, not model free text |

### Chain rules (design memo)

1. **Append-only:** No in-place edit; correction ⇒ new record referencing superseded `seq` in `notes` (hash chain continues).
2. **No credentials in ledger:** Credential-like strings belong in **quarantine / redaction** workflow (paper corpus finding)—ledger stores **`redaction_applied: true`** + hash of safe summary only.
3. **Verify offline:** Recompute `prev_hash` chain at **~126k events/s** is a **paper target**, not a playground SLA; Checker pass walks chain before KEEP ([12-pcm-proof-carrying-handoff-day-sketch.md](./12-pcm-proof-carrying-handoff-day-sketch.md) when landed; PR #23).
4. **Tamper / replay:** Duplicate `(run_id, seq)` or broken `prev_hash` ⇒ **`failed`** verdict; do not merge on broken chain (analogous to PCM stale evidence — PR #23).

### Example chain fragment (**example** — fictional)

| seq | prev_hash (sketch) | event_kind | pointer_refs | ack_state |
|-----|-------------------|------------|--------------|-----------|
| 1 | `GENESIS@ | `tool_outcome` | `log_path:/tmp/ca-run-soei-m1.log#L120-140` | `n/a` |
| 2 | `sha256:…a1` | `edit_claim` | `workspace:experiments/2026-11-04/20-*.md@draft` | `pending` |
| 3 | `sha256:…b2` | `proof_anchor` | same log segment + `exit_code:0` digest | `acked` |
| 4 | `sha256:…c3` | `completion_claim` | `task: "README row #20"` | `pending` |

---

## 2) Completion claim ≠ proof (verification layer)

Soei’s verification layer keeps **“marked complete”** and **“ independently checked”** as distinct ledger events. Team OS maps this to existing handback discipline.

| Soei / paper idea | Team OS analog |
|-------------------|----------------|
| To-do marked complete after edit | Smith |*`completion_claim`** row — **does not** satisfy done gate alone (paper **57.8%** no-proof-between cite) |
| Independent check after last edit | **`proof_anchor`** or Checker **`proven`** on log-backed claim ([12](./12-pcm-proof-carrying-handoff-day-sketch.md) PR #23; [06](./06-care-escalate-verified-progress-checklist.md) **`verified_progress`**) |
| Acknowledgement-aware events | Human **`human_ack`** or infra attestation before promoting claim to **`relied_on`** / board KEEP |
| PROV-aligned lineage | **`handoff_artifact`** + parent `run_id` / session pair keys—not chat rehydration ([01](./01-agentbaton-failure-escalate-handoff.md)) |
| Delegation expected evidence | CoworkOS **`expected_evidence`** vs return **`evidence_refs`** ([09](./09-coworkos-delegation-evidence-contract-day-sketch.md) PR #20) |

### Three-valued handback stance (aligns with PCM sketch)

| Stance | Meaning |
|--------|---------|
| **`completion_claim`** | Agent or run summary asserts done (to-do tick, PR opened, “tests passed” narrative) |
| **`proof_anchor`** | Independent check recorded **between** last material edit and claim (test segment, diff review gate, human ack) |
| **Done gate** | Ork/Checker treats **`completion_claim`** as **`unproven`** until **`proof_anchor`** (or attested T2 evidence) exists—**claim ≠ proof** |

### Observation columns (log one row per completion vs proof gap)

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `run_id` | string | Run key |
| `episode_kind` | enum | `code_edit` \|+`todo_complete` \| `pr_opened` \| `handoff` |
| `completion_claim_at` | string | When agent marked complete / opened PR |
| `last_edit_at` | string | Last material edit timestamp (from log) |
| `proof_anchor_present` | bool | Independent check event between edit and claim |
| `independent_check_sketch` | enum | `test_log` \|+`human_review` \|+`ci_job` \|+`none` |
| `ledger_seq_claim` | int | `seq` of `completion_claim` event (if ledger adopted) |
| `ledger_seq_proof` | int \| null | `seq` of `proof_anchor` (null ⇒ paper-style gap) |
| `checker_verdict` | enum | `proven` \|+`unproven` \| `failed``(PCM analog) |
| `relied_on` | a[{ id, version }]` | **Decision-used** board pointers only ([02](../2026-11-02/02-sbus-version-check-board-rule.md)) |
| `notes` | string | `log_path` pointer—no transcript dump |

### Example row (**example** — fictional)

| label | run_id | episode_kind | completion_claim_at | proof_anchor_present | independent_check_sketch | checker_verdict | relied_on | notes |
|-------|----------------------|---------------------|---------------------|---------------------|--------------------------|-----------------|-----------|-------|
| **example** | `ca-run-soei-sketch-m9` | `todo_complete` | `2026-11-04T08:20Z` | false | `none` | `unproven` | `[{"id":"origin_pr/soei/forge_head","version":"c0ffee00"}]` | Agent ticked README row before push; no test/log segment—matches paper **no proof in between** pattern; blocked at Checker |

---

## Map to Team OS (cross-links only)

- **Escalate / park:** Repeat **`failure-id`** or impasse still uses [01](./01-agentbaton-failure-escalate-handoff.md) + [04](./04-impassebench-escalate-to-human-ticket-schema.md)—ledger does not replace human park (**PR #10** pattern referenced, not edited).
- **Shared-human asks:** Clarification queue ([07](./07-pcp-shared-human-ask-queue-checklist.md)) orthogonal to proof anchors unless ask resolves a spec gap that **becomes** proof.
- **Long sessions:** Paper **>24 h** / **2 MiB replay bound** motivates **`handoff_artifact`** + ledger handoff events instead of full transcript replay.

---

## Soft no runtime caveat

- **This file is a design note only** — no hash-chained ledger service, no Agenttrail fork, no PROV export, no Soei prototype, no corpus re-analysis in playground.
- Paper stats (**23.4%**, **57.8%**, **126k events/s**, ledger **20%** size, etc.) are **Soft UNVERIFIED** citations from [2610.39468](https://arxiv.org/abs/2610.39468); not reproduced or audited here.
- **No** new bots, Slack wiring, SQLite/DSH ports, or runtime verification daemons.
- **`relied_on`:** When logging gaps or KEEP decisions, declare **board pointer ID + version** for evidence actually used—not full read sets ([02](../2026-11-02/02-sbus-version-check-board-rule.md)).

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Installing Agenttrail, re-auditing `e4ba2da`, or replaying **45** sessions  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or open sibling sketches **#8–#19** (reserved on PR #19–#30 branches)  
- **Origin PR #10** (AgentBaton / Copilot trajectory)—**leave PR #10 alone**; no Cody trajectory columns  

---

## Status

- [x] Planning (hash-chain + claimb��proof Soft sketch)  
- [ ] In Progress (no ledger runtime)  
- [ ] Complete  

**Relied on (SHAs):** `a3d5441``(main tip at branch: PCP #7 / merged PR #18); paper [2610.39468](https://arxiv.org/abs/2610.39468) abstract + v1.1 prose cite only — **Soft UNVERIFIED** (no public Soei code; no Agenttrail checkout in playground).

**Next step:** When adopting a local ledger, append `proof_anchor` before accepting Smith **`completion_claim`** on KEEP; tabletop one fictional chain fragment—no merge of this doc required for ops.
