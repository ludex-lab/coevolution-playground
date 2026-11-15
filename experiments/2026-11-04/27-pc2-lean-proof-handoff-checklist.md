# PC2 — Lean proof receipt × Team OS handoff (observation checklist)

**날짜**: 2026-11-04  
**Sprint sibling**: **#27** (wave7; conflict-free add — does **not** renumber `01`–`07`)  
**Paper**: [Proof-Carrying Contracts: Commitments AI Agents Cannot Break](https://arxiv.org/abs/2610.28484) (Ciliberto, Rudi, Tassi; arXiv:2610.28484)

**Upstream (read-only pointer)**: [consequential-ai/proof-carrying-contracts](https://github.com/consequential-ai/proof-carrying-contracts) — Lean 4 mechanization under `lean/` ([`lean/README.md`](https://github.com/consequential-ai/proof-carrying-contracts/blob/main/lean/README.md)); companion site JSON under `website/` is **not** vendored here.

**Code in playground**: **NONE** — markdown observation checklist only; **no** Lean/Lake subtree copy, **no** Airlock binary, **no** proof checker harness.

### Checker caveats (hard)

| Topic | Status |
|-------|--------|
| **GPL-2.0** (upstream `LICENSE`) | **Ideas and citation only** — do **not** vendor or subtree-copy `proof-carrying-contracts` into playground; linking arXiv/GitHub is fine. |
| **Lean `lake build`** | **Soft (this session)** — `elan` / `lake` not present on the Cloud Agent VM; upstream README claims ~4s build with Lean 4.35.0 after `cd lean && lake build`. **Top** only after an independent checker run on a machine with elan. |
| **Airlock runtime** | **Soft** — paper + repo describe mechanization and future release (“Further code … will be released”); playground **must not** claim Airlock is runnable or attested here. |

---

## Paper pointer (citation only; no Airlock runs today)

From the public abstract and §2 on [2610.28484](https://arxiv.org/abs/2610.28484):

- **PC2:** Parties write a **formal contract** (clauses + goal). Before each **tool call**, the agent supplies a **machine-checkable proof** that agreed constraints hold through that call; the **Airlock** derives the **obligation**, checks the proof, and runs the call only if accepted.
- **Burden shift:** Safety is argued **per action** (proof for this call) rather than proving a monolithic permission policy safe for all futures.
- **Guarantees:** **Commitment** (clauses hold throughout execution, including adversarial agents) and **completion** (settlement / deadline behavior) under explicit assumptions — mechanized in Lean (`Paper.lean` maps numbered paper items).
- **Capability modules (§6):** Reusable tool+model packages composed into contracts (e.g. travel / payment sketches in `PC2/Examples/Travel.lean` upstream).

Playground **does not** deploy an Airlock, reproduce travel episodes, or require agents to submit Lean proofs for git writes.

---

## Map to Team OS (Ork → Smith → Checker)

| PC2 role | Paper behavior | Team OS analog (markdown / process) |
|----------|----------------|-------------------------------------|
| **Contract** | Signed clauses + goal | Ork brief: **non-goals**, success criteria, “must hold” invariants (budget, paths, no merge, no PR #10 touch) |
| **Agent loop** | Reason → (call + proof) → observe | Smith execution on branch; each **externally visible op** (push, CI trigger, deploy) paired with a **proof receipt** row below |
| **Obligation** | Airlock-derived statement for this call | Checker-scoped **obligation sketch** — what must be true *before* this handback counts (e.g. “markdown only”, “index row #27 present”, “GPL no vendoring”) |
| **Proof** | Formal argument checked by small checker | **Evidence packet**: diff paths, PR URL, head SHA, optional upstream pointer IDs — **not** model narrative |
| **Airlock gate** | No call without accepted proof | **Checker gate**: handback `ready` only if receipt `proof_status=accepted`; reject → Smith revises (PC2 “error message” analog) |
| **Settlement** | Goal proved → escrow / contract ends | Sprint **done-when**: Origin PR open, conflict-free vs `main` tip — **not** merge unless explicitly requested |
| **`handoff_artifact`** | (Team OS parallel) | [`workspace_pointer` + `log_path` only](./01-agentbaton-failure-escalate-handoff.md) — continuity without transcript dump |

### Ork → Smith → Checker procedure (sketch)

1. **Ork** — Freeze contract sketch: allowed files, forbidden targets (e.g. **PR #10** AgentBaton), `relied_on` pointer IDs Checker must chase ([2026-11-02 SBUS rule](../2026-11-02/02-sbus-version-check-board-rule.md) subset semantics).
2. **Smith** — Implement/docs on branch; before handback, attach **proof receipt** (table or JSON) listing obligation + evidence paths; assemble `handoff_artifact`.
3. **Checker** — Verify receipt **mechanically** (git diff, README row, license boundary); record **Top vs Soft** on each `relied_on` entry; **do not** treat Soft Airlock/lake as executed proof.

**Cross-links:** Repeat-failure escalate still uses [01](./01-agentbaton-failure-escalate-handoff.md); human impasse uses [04](./04-impassebench-escalate-to-human-ticket-schema.md); clarification queue orthogonal ([07](./07-pcp-shared-human-ask-queue-checklist.md)).

---

## Observation checklist (proof receipt per handback)

Log **one row per Checker-gated handback** (Smith `ready` or Checker reject). **Log only** — no Lean checker in repo.

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `run_id` | string | Cloud Agent / Team OS run id |
| `contract_sketch` | string | One-line Ork invariants for this slice |
| `operation_sketch` | string | What would have been the “tool call” (e.g. `git push`, `docs edit`) |
| `obligation_sketch` | string | Checker-derived must-hold (PC2 `Obl` analog — informal) |
| `proof_status` | enum | `accepted` \| `rejected` \| `pending` |
| `proof_evidence` | string | Paths, SHAs, PR URL — **pointers only** |
| `airlock_runtime` | enum | **`not_deployed`** (only honest value in playground today) |
| `lean_build` | enum | `not_run` \| `passed` \| `failed` — session truthfulness |
| `handoff_artifact` | struct | `workspace_pointer` + `log_path` |
| `relied_on` | json | `[{ id, version, tier: Top\|Soft }]` — decision-used subset |
| `checker_one_liner` | string | Verdict |

### Example row (**example** — fictional, plausible)

| label | run_id | contract_sketch | operation_sketch | obligation_sketch | proof_status | proof_evidence | airlock_runtime | lean_build | checker_one_liner |
|-------|--------|-----------------|------------------|-------------------|--------------|----------------|-----------------|------------|-------------------|
| **example** | `ca-run-pc2-sketch-9129` | wave7 #27 markdown only; no GPL vendoring; leave PR #10 | add `27-pc2-…md` + README row | diff ⊆ `experiments/2026-11-04/`; no `lean/` copy | `accepted` | Origin PR URL; head SHA; `git diff --stat` | `not_deployed` | `not_run` | Top: arXiv + upstream README map; Soft: lake + Airlock |

---

## Sample evidence sketch (JSON — **example**, not executed Lean proof)

Illustrates how a Smith handback might bundle **Team OS proof receipt** without importing PC2 sources:

```json
{
  "handoff_artifact": {
    "workspace_pointer": {
      "repo": "coevolution-lab/playground",
      "branch": "cursor/pc2-lean-day-sketch-9129",
      "sha": "<head-after-push>"
    },
    "log_path": "/tmp/cloud-agent-pc2-sketch-9129.log"
  },
  "pc2_analog": {
    "contract_sketch": "docs-only sprint #27; do not merge; do not edit PR #10",
    "operation": "commit markdown + README index row",
    "obligation_sketch": "no vendored GPL Lean tree; honest Soft/Top on relied_on",
    "proof_receipt": {
      "status": "accepted",
      "evidence": [
        "experiments/2026-11-04/27-pc2-lean-proof-handoff-checklist.md",
        "experiments/2026-11-04/README.md"
      ]
    }
  },
  "relied_on": [
    {
      "id": "arxiv/2610.28484/abstract",
      "version": "v1",
      "tier": "Top"
    },
    {
      "id": "github/consequential-ai/proof-carrying-contracts/lean/README",
      "version": "main (read-only shallow clone for map)",
      "tier": "Top"
    },
    {
      "id": "upstream/lean/Paper.lean",
      "version": "not_imported",
      "tier": "Top",
      "note": "citation map only — no copy in playground"
    },
    {
      "id": "upstream/lean/lake_build",
      "version": "not_executed_this_session",
      "tier": "Soft"
    },
    {
      "id": "upstream/airlock_runtime",
      "version": "not_released",
      "tier": "Soft"
    }
  ]
}
```

### Lean shape (upstream — citation only)

Upstream mechanization defines tools, contracts, and certificates in Lean 4, e.g. **`Tool`**, **`Contract`**, admissibility **`Adm`**, obligation **`Obl`**, certificate **`Cert`** (`PC2/Basic.lean`; see upstream `lean/README.md` map). Playground **does not** typecheck these declarations; they inform **column names** (`obligation_sketch`, `proof_status`) only.

---

## Soft park (do not implement in wave7)

| Topic | Pointer | Note |
|-------|---------|------|
| Revocation | [arXiv:2610.15991](https://arxiv.org/abs/2610.15991) | Future wave — not in this file |
| Evidence-Guided | [arXiv:2610.41453](https://arxiv.org/abs/2610.41453) | Future wave |
| wave8 | DRS, DelegateOS | Park only |

---

## Out of scope (2026-11-04 #27)

- Vendoring or subtree of `proof-carrying-contracts` (GPL-2.0)  
- Running **Airlock**, remote attestation, or escrow tooling  
- `lake build` claims without elan/lake on checker machine  
- Cody trajectory / intervention columns (**PR #10** only — **do not** edit)  
- Bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md)  
- DSH / Feishu / SQLite / daemon / headcount ports  

---

## Status

- [x] Planning (observation checklist sketch)  
- [ ] In Progress (no Lean/Airlock wiring)  
- [ ] Complete  

**Next step:** On future waves, if elan is available, a Checker may run upstream `lake build` and set `lean_build=passed` on the receipt row — until then, keep **Soft** honest.
