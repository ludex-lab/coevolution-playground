# Evidence-Guided — ambiguous tool outcomes & partial execution (Soft design note)

**날짜**: 2026-11-04  
**Paper**: [Evidence-Guided Recovery for AI Agents with Ambiguous Tool Outcomes and Partial Execution](https://arxiv.org/abs/2610.41453) (Zhu et al., arXiv:2610.41453)

**Code**: **NONE** — markdown design note only. The preprint describes a **known-model** recovery profile (observation-contingent planning + separately implemented effect-history adjudicator) and preregistered model-facing comparisons — playground **does not** run the 37-assignment finite study, 116-episode replay shield, or native persistence executor qualifications. Treat implementation and replay claims as **Soft UNVERIFIED** unless a **public runnable** artifact is pinned and tiered in a future pass.

## Paper pointer (Top: existence; stats Soft UNVERIFIED)

From the public abstract and §1 on [2610.41453](https://arxiv.org/abs/2610.41453) — playground **does not** reproduce paired units, independent replay, or synthetic fee accounting:

| Idea (paper) | Sketch |
|--------------|--------|
| **Ambiguous outcome** | Tool **timeout / lost ack** ⇒ invocation may have **failed**, **committed**, or remain **in flight** while later workflow steps already ran |
| **Evidence-guided recovery** | Choose **evidence acquisition**, **wait**, **retry under dedup contract**, **continue independent obligations**, **compensate**, or **handoff** — under **approved obligations** + **public provider capabilities** + states compatible with **public evidence** |
| **Admissibility shield** | Common check excludes actions that add a **checked violation** or **abstract pending hazard** in any compatible state — probabilities guide selection but **cannot** legalize a prohibited transition |
| **Terminal certificate** | Separates **actual goal satisfaction** from **publicly supported safe completion**; **unknown** and **handoff** outcomes stay explicit |
| **Controlled evaluation (cite only)** | 37 assignments: five policies tie at **28/37** completions in one frame; assignment-held-out model comparison **30/58** vs **9/58** certified completions (planning advice vs evidence prompting), **272** vs **399** proposals, **116** trajectories independently replayed (abstract / Table 1 narrative) |

**Top (paper exists):** [2610.41453](https://arxiv.org/abs/2610.41453) abstract + contract framing (obligations, evidence, completion vs unknown).  
**Soft UNVERIFIED:** All completion counts, sign-flip \(p\)-values, replay pass rates, executor qualification demos, and upstream code paths — **cite only**, no local run.

Playground **does not** implement POMDP search, effect-history adjudicators, or provider capability contracts.

---

## 1) Map evidence-guided recovery → Team OS (Ork → Smith → Checker)

Team OS delegates through forge/git/MCP surfaces where **HTTP 200**, **empty tool output**, or **timeout** are not negative effect certificates ([2610.41453](https://arxiv.org/abs/2610.41453) §2.1). The paper’s **shield + certificate** pattern maps to **evidence-bound plans**, **guided checks**, and **refuse without evidence**.

| Paper layer | Ork | Smith | Checker |
|-------------|-----|-------|---------|
| **Approved obligations** | Brief lists **done-when** as obligations + **forbidden** retries (no duplicate merge, no scope creep) — not vibes | Executes only steps in the **current admissible set** | Verdict keyed to obligation table, not Smith narrative |
| **Public evidence packet** | Requires **`relied_on`** pointers (SHA, PR URL, log segment) before launch ([02](../2026-11-02/02-sbus-version-check-board-rule.md)) | Appends **cited** tool outcomes to ticket `evidence` ([04](./04-impassebench-escalate-to-human-ticket-schema.md)) — no transcript dump | **Refuses KEEP** when claim lacks independent replay anchors ([01](../2026-11-01/01-mandate-agent-run-checklist.md) Missing evidence) |
| **Evidence acquisition action** | Authorizes bounded **read/query** steps (fetch PR, read CI, grep log) before another **write** | Runs queries; labels row `action_kind=evidence_acquire` | Treats inconclusive read as **unknown**, not “failed write” |
| **Wait / visibility delay** | Sets **wait_until** when provider contract says ack may lag | No non-idempotent retry inside window | Logs **pending hazard** if Smith writes anyway |
| **Continue independent work** | Marks obligations **non-blocked** while one tool outcome is unknown ([07](./07-pcp-shared-human-ask-queue-checklist.md) parallel work) | Advances docs/tests not depending on ambiguous step | Separates **partial progress** from **certified complete** |
| **Compensate / rollback sketch** | Permits **reversible** repair only when contract lists compensation — not “delete remote message already sent” | Records compensation attempt + **its** ambiguous outcome | Effect-history: final state OK but **extra irreversible** action ⇒ fail |
| **Handoff to operator** | **`escalate_to_human`** when no trustworthy evidence path ([04](./04-impassebench-escalate-to-human-ticket-schema.md)) | Stops guarded writes; hands **`evidence` + `attempts`** | **Park** — not conflated with success |
| **Terminal certificate** | Declares **`completion_claim`** only with packet checklist satisfied | Submits **`handoff_artifact`** + evidence refs ([01](./01-agentbaton-failure-escalate-handoff.md)) | **`certified_complete`** vs **`unknown`** vs **`handoff`** — no merge on plausible message alone |

### Three Team OS stances (design memo)

| Stance | When | Ork → Smith | Checker |
|--------|------|-------------|---------|
| **Evidence-bound plan** | Before guarded write burst | Plan lists **next action** only if admissible under **current public evidence** — optional planner advice is **hint**, not authority | Replays proposed action against **`relied_on` + log refs** |
| **Guided check** | After ambiguous tool return | Smith runs **verify/wait/query** per brief; no “retry because error string” | Compares trajectory to **shield** rules (pending hazard, key expiry sketch) |
| **Refuse without evidence** | Claimed done, push blocked, or revoke in flight | Smith must not fabricate proof | **`unproven`** / abort-delegation until packet complete; aligns with **C3 ≠ complete** revoke sketch ([28-revocation-executable-outcome-contract-design-note.md](./28-revocation-executable-outcome-contract-design-note.md) on open PR #39 — **Soft**, file not on `main` until that PR lands) |

**Ork → Smith:** Handoff carries **obligation ids**, **capability contract sketch** (which tools are idempotent, which reads are authoritative), and **`evidence_packet_min`** — pointers only.  
**Smith → Checker:** Handback includes **`ambiguous_outcomes[]`**, **`certificate_sketch`**, and **`shield_violations=0`** claim — Checker independently validates refs, not Smith prose.

---

## 2) Sample JSON observation row (checklist sketch)

Log **one row per ambiguous tool episode** (timeout, partial batch, lost ack). **Log only** — no recovery planner runtime.

```json
{
  "label": "example",
  "run_id": "ca-run-eg-29a1",
  "obligation_id": "done-when-origin-pr-open",
  "tool_call_sketch": "git push after network blip",
  "outcome_class": "unknown_in_flight",
  "public_evidence": {
    "relied_on": [{ "id": "origin/pr/42/head", "sha": "abc1234" }],
    "log_path": "terminals/3.txt#L40-55",
    "ci_status": "pending"
  },
  "admissible_next_sketch": ["evidence_acquire: fetch origin", "wait: visibility_120s", "handoff: escalate_to_human"],
  "smith_action_taken": "evidence_acquire",
  "shield": {
    "checked_violations": 0,
    "pending_hazard": true,
    "non_idempotent_retry_blocked": true
  },
  "certificate_sketch": "unknown",
  "checker_stance": "unproven",
  "notes": "No second push until forge head matches evidence; independent doc edit allowed"
}
```

Field gloss: **`outcome_class`** ∈ `failed` \| `committed` \| `unknown_in_flight` \| `partial_batch`; **`certificate_sketch`** ∈ `certified_complete` \| `safe_completion_public` \| `unknown` \| `handoff`.

---

## 3) Cross-links (markdown only)

- **Impasse / park:** Persistent blockers → **`escalate_to_human`** ([04](./04-impassebench-escalate-to-human-ticket-schema.md)); distinct from **ambiguous** outcome where work can continue under shield.
- **Revocation (sibling Soft #28):** Open PR #39 — **evidence withdraw** and **C3 vs C4** completion mistakes when Smith keeps acting after Ork narrows scope; pair with **refuse without evidence** here.
- **CARE / verified progress:** Dual thresholds ([06](./06-care-escalate-verified-progress-checklist.md)) — **`verified=false`** handoff is progress, not terminal certificate.
- **Soei ledger (open PR #31):** Intent vs proof rows — **`completion_claim`** ≠ **`certified_complete`**.

---

## Soft no runtime caveat

- **This file is a design note only** — no observation-contingent planner, no effect-history adjudicator, no 116-episode replay harness in playground.
- Paper stats (**28/37**, **30/58** vs **9/58**, **272** vs **399** proposals, **36.2** pp, \(p=0.0078\), etc.) are **Soft UNVERIFIED** citations from [2610.41453](https://arxiv.org/abs/2610.41453); not reproduced here.
- Ork/Smith/Checker mapping and JSON row are **Soft** — not validated against paper artifact or production gates.
- **`relied_on`:** Declare **board pointer ID + version** for evidence used in this sketch; paper abstract **Top** for problem framing only.

---

## Parked (not in this PR)

| Item | Note |
|------|------|
| **wave8 DRS** | Parked — no file |
| **DelegateOS** | Parked — no file |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Cloning unpublished recovery executors or re-running preregistered study cells  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or open sibling sketches **#8–#28** (reserved on Origin PR #19–#39 branches)  
- **Origin PR #10** (AgentBaton / Copilot trajectory)—**leave PR #10 alone**  

---

## Status

- [x] Planning (evidence-bound plans + guided checks + refuse without evidence Soft sketch)  
- [ ] In Progress (no recovery runtime)  
- [ ] Complete  

**Relied on (SHAs):** `a3d5441` (main tip at branch: PCP #7 / merged PR #18); paper [2610.41453](https://arxiv.org/abs/2610.41453) abstract + §1 contract — **Top**; experiment counts + replay — **Soft UNVERIFIED**.

**Next step:** On ambiguous tool timeout, log one JSON row with **`outcome_class=unknown_in_flight`** before any non-idempotent retry; tabletop against Mandate Missing evidence — no merge of this doc required for ops.
