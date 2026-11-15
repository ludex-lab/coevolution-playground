# CoworkOS — revision-checked shared resources & lease vocabulary (Soft design note)

**Date**: 2026-11-05  
**Paper**: [CoworkOS: Scaling Agent Coworkers for Real-world Automation](https://arxiv.org/abs/2611.03178) (Jin et al., arXiv:2611.03178)  
**Upstream repo**: [RUC-NLPIR/CoworkOS](https://github.com/RUC-NLPIR/CoworkOS) — **MIT** ([LICENSE](https://github.com/RUC-NLPIR/CoworkOS/blob/v0.1.3/LICENSE))

**Playground code**: **NONE** — Soft method-borrow design note only. **No Top runtime.** Soft→Top forbidden in this folder.

---

## Pin table (authority for citations)

| Item | Value |
|------|--------|
| Repository | https://github.com/RUC-NLPIR/CoworkOS |
| **Pinned release** | Tag **`v0.1.3`** → commit **`13e2368f99f14f035b126eb2ee9f09b9293358b0`** (“Fix release retries and public CLI feedback links”; verified via `git ls-remote` + GitHub refs API, 2026-11-05) |
| **`main` tip (informational)** | **`baf03c30db56160690f9d03bfa7dee925bad6cfd`** — newer than `v0.1.3`; pack notes cited `baf03c3…` as of 2026-11-03 — **this note pins the tag SHA above**, not floating `main` |
| License | MIT |
| Soft tier | **Soft KEEP** (method-only) + **Soft UNVERIFIED** (no local `coworkos` install, no package tree audit on this VM) |
| Playground base at authoring | `252912fc33992d44cf921ad50bdd7d87c98f0ca0` (`origin/main` at branch creation) |

### Method bullets borrowed (clean-room vocabulary only)

1. **Revision-checked shared resources** — platform-managed artifacts carry a **base revision**; edits from a **stale** base yield **`conflict`**, not silent overwrite (paper §3 / Eq. 7 narrative; README “revision-aware candidate changes”).
2. **Lease-like writer scope** — coordinate concurrent humans/agents on the same evolving object via **exclusive or time-bounded hold** on a contested ref (Team OS maps to claim board / one-writer handoff — not CoworkOS filesystem locks).
3. **Inbox / Jobs as wake vocabulary** — long-running **Jobs** retain status/logs; async paths cite **Inbox** or Job poll as **`observation_source`** for bounded waits (file names such as `main-inbox-delivery.ts` at pin — **not opened line-by-line here**).
4. **`ask_main` pattern** — Subagent/Main decision with **`wait_ms`**, explicit **`fallback_assumption`**, and optional **`review_time`** so work does not stall unbounded on human silence.
5. **Team OS fit** — Ork→Smith→Checker **handoff artifact** + shared repo **base SHA** + ParallACT-style **contested artifact** rows ([05](../2026-11-04/05-parallact-shared-repo-handoff-checklist.md)); complements delegation contract fields in [09](../2026-11-04/09-coworkos-delegation-evidence-contract-day-sketch.md) without duplicating that full schema.

### FORBID (Usage-Sprint)

- **Do not** vendor, clone, or port **CoworkOS**, **DeepSeek Harness (DSH)**, Feishu, SQLite store, daemon, or extra agent **headcount**.
- **Benchmarks vs DSH ≠ DSH port** — DSH and CoworkOS paper tables are **evaluation peers / related work only**; playground does not reproduce harness or CoworkOS RSI loops.
- **No** Postgres / myko / Muster daemon wiring; **no** Soft→Top promotion or runtime config merge from this note.
- **No** `npx coworkos-app`, desktop install, Blender/CAD adapters, or npm global harness in sprint scope.

### Honesty (what was opened vs assumed)

| Source | Opened on this VM | Assumed / README+paper only |
|--------|-------------------|-----------------------------|
| Tag `v0.1.3` SHA | Yes — `git ls-remote`, GitHub tag object | — |
| `main` @ `baf03c3…` | Yes — remote ref only | Not used as pin |
| arXiv [2611.03178](https://arxiv.org/abs/2611.03178) | Abstract + §3 prose via prior sprint notes | Full PDF not re-parsed line-by-line this turn |
| CoworkOS `packages/` / runtime | **No checkout** | Three-layer Main → Coordinator → Subagent; shared application resources |
| `src/runtime/main-inbox-delivery.ts` | **Not opened** | Cited as existence of Inbox delivery path at tag tree listing |
| Local CoworkOS execution | **No** | All admission/conflict examples are **Team OS analog rows** |

---

## Checker verdict

| Signal | Value |
|--------|--------|
| License | MIT (upstream LICENSE at `v0.1.3`) |
| Upstream tests | Not counted in this note — **Soft UNVERIFIED** |
| Promotion | **Soft KEEP** — method borrow only; **no** Soft→Top |

---

## 1) Revision admission row (shared artifact)

When Smith, Checker, or a human touches the **same** handoff surface (README index row, shared markdown spec, branch tip), log an **admission** decision:

| Field | Type | Definition |
|-------|------|------------|
| `artifact_ref` | string | Path, Origin PR head ref, or board pointer id |
| `base_revision` | string | Git SHA, saved `contract_version`, or artifact generation id at start of edit |
| `holder_lease_id` | string \| null | Optional claim/lease id if a writer hold was granted ([40](../2026-11-04/40-agent-handoff-ledger-soft-design-note.md) analog) |
| `actor` | enum | `ork` \| `smith` \| `checker` \| `human` |
| `proposed_revision` | string | New SHA or candidate id after edit attempt |
| `admission` | enum | `accepted` \| **`conflict`** \| `candidate_only` |
| `conflict_notes` | string | What moved since `base_revision`; pointer to live tip |

**Norm (CoworkOS paper narrative):** on **`conflict`**, **do not overwrite** intervening edits. Main/Ork re-reads tip, re-issues delegation or merge plan — same spirit as stale PR base on shared repo ([05](../2026-11-04/05-parallact-shared-repo-handoff-checklist.md)).

**Lease coupling:** a **`holder_lease_id`** is **advisory** in Team OS (cooperative policy). Expired or superseded lease ⇒ treat edit as **`conflict`** if `base_revision` no longer matches live artifact, even if the actor still “feels” assigned.

---

## 2) Lease sketch (claim lane — not CoworkOS runtime)

Borrow **lease** only as **vocabulary** for Team OS contested resources:

| Field | Type | Definition |
|-------|------|------------|
| `lease_id` | string | Stable id (`cowork-lease-mock-1`) |
| `artifact_ref` | string | Scoped resource (path glob, PR branch, doc id) |
| `holder` | string | Smith run id or human slot |
| `issued_at` | string | ISO time |
| `expires_at` | string \| null | Wall expiry — stale ⇒ queue warning ([40](../2026-11-04/40-agent-handoff-ledger-soft-design-note.md)) |
| `base_revision` | string | Revision holder must respect for writes |
| `lease_state` | enum | `active` \| `released` \| `expired` \| `conflict` |

**Cross-link:** append-only **claim** events ([48](../2026-11-04/48-append-only-claim-board-design-note.md) Top sketch) can emit **`held`** / **`released`**; this note stays **Soft** and does not wire Rust board code.

---

## 3) Jobs + Inbox wake fields (vocabulary cite)

For async Smith work blocked on Main/human, pair bounded wait with a **wake channel** (see lint spirit in [09 §4](../2026-11-04/09-coworkos-delegation-evidence-contract-day-sketch.md)):

| Field | Type | Definition |
|-------|------|------------|
| `job_ref` | string \| null | Long-horizon Job id — status/logs survive session break (README Jobs bullet) |
| `inbox_ref` | string \| null | Minimal async message id if peer/Main channel allowed |
| `observation_source` | string | Concrete wake: `job:<id>`, `inbox:<id>`, `git fetch origin main`, human queue row ([07](../2026-11-04/07-pcp-shared-human-ask-queue-checklist.md)) |
| `wait_ms` | int | Bounded wait before **`fallback_assumption`** applies |
| `fallback_assumption` | string | Auditable assumption if Main silent at deadline |
| `review_time` | string \| null | Scheduled human/Main review — satisfies wake when poll absent |

**Inbox paper orthogonality:** CoworkOS **Inbox** delivery is harness vocabulary; [15](../2026-11-04/15-inbox-coordination-primitive-design-note.md) covers **push vs pull** attention policy — complementary, not merged here.

---

## 4) Bounded-wait + fallback (delegation lane)

Minimal **`ask_main`** row when strategy depends on Main:

| Field | Type | Definition |
|-------|------|------------|
| `ask_id` | string | Stable id |
| `contract_id` | string | Join to delegation revision |
| `question_sketch` | string | One-line decision (merge order, acceptance test) |
| `wait_ms` | int | Bounded wait |
| `fallback_assumption` | string | Declared progress if unanswered |
| `ask_outcome` | enum | `answered` \| `fallback_used` \| `withdrawn` \| `escalated` |

**Escalate:** repeat **`failure-id`** after **`fallback_used`** → [01](../2026-11-04/01-agentbaton-failure-escalate-handoff.md) two-strike escalate — **not** a CoworkOS benchmark claim.

---

## 5) Example tabletop (fictional)

| Step | Event | Admission / lease |
|------|-------|-------------------|
| 1 | Ork grants `lease_id=L1` on `experiments/2026-11-05/README.md` at `base_revision=252912fc…` | `lease_state=active` |
| 2 | Smith drafts `#01` folder under lease | `admission=accepted` |
| 3 | Parallel run edits same README without fresh base | `admission=**conflict**` — no silent overwrite |
| 4 | Smith `ask_main` with `wait_ms=900000`, `fallback_assumption="row #01 only"`, `observation_source=origin pr checks` | lint-pass wake |
| 5 | Return with `evidence_refs` pointing at PR head SHA | revision re-checked against live `main` |

---

## Siblings (folder names — not Origin PR #)

| Folder / doc | Relation |
|--------------|----------|
| `2026-11-04/09-coworkos-delegation-evidence-contract-day-sketch.md` | Full delegation contract + return schema |
| `2026-11-04/40-agent-handoff-ledger-soft-design-note.md` | One-writer lease analog |
| `2026-11-04/05-parallact-shared-repo-handoff-checklist.md` | Contested artifact / joint-fail lens |
| `2026-11-01/02-dsh-superagent-borrow-notes.md` | DSH **evaluation peer** — ticket/store borrow **not** ported |

---

## Status

- [x] Planning (pin table + revision/lease/Inbox-Job/`ask_main` vocabulary)
- [ ] In Progress (no runtime)
- [ ] Complete

**Next step:** On multi-agent sprints, append admission + lease rows offline before treating a shared README or handoff file as safe to edit under stale `base_revision`.
