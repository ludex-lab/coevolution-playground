# RemedyFabric — quorum receipt day-sketch (Team OS borrow)

**날짜**: 2026-11-04  
**Source (Top — public runnable with caveats)**: [Oxygen56/remedyfabric](https://github.com/Oxygen56/remedyfabric) (Apache-2.0; GOAI 2026 Agent Infra hackathon entry)

**Code**: **Top public repo (weak KEEP)** — judge path is documented (`PYTHONPATH=src python3 scripts/run_resilient_matrix.py`, `check_quorum_model.py`, `run_faultbench.py` per [README](https://github.com/Oxygen56/remedyfabric/blob/main/README.md) and [docs/JUDGE_GUIDE.md](https://github.com/Oxygen56/remedyfabric/blob/main/docs/JUDGE_GUIDE.md)). Playground **does not** vendor RemedyFabric or wire a release gate.

## Checker KEEP (Top, weak) — explicit caveats

| Signal | KEEP note |
|--------|-----------|
| License | **Apache-2.0** — real, declared on upstream repo |
| Stars / activity | **★0** at cite time; repo **idle ~2.5 months** since last push **2026-08-14** (competition-shaped maintenance) |
| Provenance | **GOAI 2026** Agent Infra **hackathon** entry — mechanism-first, not production SLO claims |
| Quorum stack | **Finite-state model JSON** (`artifacts/quorum-model.json` + `check_quorum_model.py`) **plus** Python **`QuorumGate` checker** — safety claims are **bounded to that pair**, not live multi-tenant ops |
| AgentTeams hosted path | Official live evidence is **conditional**; upstream may record **hosted runtime blocked** in [`artifacts/agentteams-runtime-blocked.json`](https://github.com/Oxygen56/remedyfabric/blob/main/artifacts/agentteams-runtime-blocked.json) — do **not** treat AgentTeams cloud as verified in playground |
| Frozen release | Four HEAD-bound receipts still **pending** per upstream README — local/stale files are not authority |
| Small model | Finite-state safety **inside published model** only — not general BFT or cryptographic actor identity ([upstream scope table](https://github.com/Oxygen56/remedyfabric/blob/main/README.md)) |
| Matrix re-run | **Do not claim this Cloud Agent re-ran** `run_resilient_matrix.py` **unless** a turn actually executes it here and pins output SHA — **not done in this session** |

**Wave6 Checker verdict:** **KEEP-with-caveats** — borrow **role-separated quorum + machine-checkable receipt** sketch for Team OS; do not upgrade to “production proof” or “AgentTeams live verified” without local artifacts and strict validation.

## Mechanism pointer (citation + checklist; matrix not re-run here)

Upstream reports **22** isolated resilient-matrix trials (**8** single-fault Worker modes, **13** overflow/control fail-closed), **0 unsafe releases** in that layer, plus **20,748** exhaustively checked quorum-model decisions ([artifacts/resilient-matrix.json](https://github.com/Oxygen56/remedyfabric/blob/main/artifacts/resilient-matrix.json), [artifacts/quorum-model.json](https://github.com/Oxygen56/remedyfabric/blob/main/artifacts/quorum-model.json) — **cite only**).

**Resilient matrix re-run (honest):** A prior run elsewhere reported `PYTHONPATH=src python3 scripts/run_resilient_matrix.py` passing in ~12s — **unpinned anecdote only**. **This Cloud Agent session did not re-execute** that command in the playground VM. Verification here is **schema + role map + Checker checklist** only; local re-run remains the upstream five-minute judge route.

Expected terminal summary fields (from [JUDGE_GUIDE.md](https://github.com/Oxygen56/remedyfabric/blob/main/docs/JUDGE_GUIDE.md)) — **not asserted from this workspace**:

| Field | Upstream expectation (when you run locally) |
|-------|---------------------------------------------|
| `passed` | `true` |
| `trial_count` | `22` |
| `single_worker_unsafe_releases` | `0` |
| `tested_out_of_boundary_fail_closed_rate` | `1.0` |
| `preauthorization_workspace_write_attempts` | `0` |

---

## Map RemedyFabric → Team OS (Top mechanism borrow)

| RemedyFabric role / gate | Team OS analog |
|--------------------------|----------------|
| **Worker** (typed `CandidateProposal`, isolated clone) | **Smith** — proposes bounded patch/edits; never self-authorizes merge |
| **Verifier** + **Challenger** (`Attestation`, evidence-bound) | **Checker** — independent test/challenge attestations; **REJECT** blocks release |
| **Governor** (`EvidenceKind.POLICY`) | **Policy** — scope, path, and org rules (branch protection, allowed paths, secret policy) |
| **Release Manager** + `QuorumGate` | **Ork** — requests release only after quorums; materializes workspace **after** authorization |

Cross-links (orthogonal, not replaced):

- Repeat **`failure-id`** escalate → [01](./01-agentbaton-failure-escalate-handoff.md) (`handoff_artifact` = pointer + `log_path` only).
- Human impasse / park → [04](./04-impassebench-escalate-to-human-ticket-schema.md); **PR #10** park pattern — **do not edit PR #10 body**.
- SBUS **`relied_on`** pointer discipline → [02 SBUS board rule](../2026-11-02/02-sbus-version-check-board-rule.md) (decision-used subset only).

Upstream invariant (paraphrase): a single faulty Worker **cannot authorize its own patch**; staged bytes stay off the governed tree until `QuorumGate` authorizes; denied paths retain or restore snapshot bytes ([JUDGE_GUIDE](https://github.com/Oxygen56/remedyfabric/blob/main/docs/JUDGE_GUIDE.md)).

---

## Adversarial refuses (Checker must not treat as quorum)

Playground **Checker sketch** — mirror upstream `reason_codes` / membership rules when logging Team OS merge attempts:

1. **Forged PASS (evidence integrity)** — Upstream `FaultMode.FORGE_EVIDENCE` tampers `claimed_binding_digest`; gate adds **`INVALID_ATTESTATION_INTEGRITY`** (and related blocking codes). Team OS: **never** accept “tests passed” without verifiable log/test artifact bound to the same `run_id` / head SHA as the candidate.
2. **Duplicate identity** — `QuorumGate` constructor **refuses duplicate `actor_id`** in membership (`ValueError: membership contains duplicate actor_id values`). At evaluation time, **duplicate votes do not increase quorum**; duplicate attestations per actor → **`CONTROL_EQUIVOCATION`**. Team OS: one registered principal per gate slot; replayed bot identity must not double-count toward approve.
3. **Forged / stale release request** — **`REQUESTER_NOT_RELEASE_MANAGER`**, **`PROPOSAL_CONTEXT_MISMATCH`**, **`ATTESTATION_CONTEXT_MISMATCH`**, **`WORKER_EQUIVOCATION`**, **`CONTROL_REJECTION`**, role-specific `*_QUORUM_MISSING` — all force **`rollback`** / deny merge (see upstream `quorum.py`).

**Soft/Top caveat:** Attestation digests provide **integrity and binding**, not cryptographic actor authentication — production must authenticate actors at runtime ([upstream `Attestation` docstring](https://github.com/Oxygen56/remedyfabric/blob/main/src/remedyfabric/faults.py)).

---

## Quorum receipt JSON schema sketch (one object)

Minimal **`quorum_receipt`** Team OS could attach to an Origin PR handback (analogous to upstream `QuorumDecision.to_dict()` + trial binders). **Sketch only** — not validated against RemedyFabric CLI in playground.

```json
{
  "schema": "team_os/quorum_receipt/0.1-sketch",
  "run_id": "sha256:…",
  "snapshot_digest": "sha256:…",
  "candidate_digest": "sha256:…",
  "requested_by": {
    "actor_id": "release-manager-1",
    "role": "release_manager"
  },
  "authorized": false,
  "action": "rollback",
  "approval_counts": {
    "worker_proposals": 2,
    "verifier": 1,
    "challenger": 1,
    "governor": 1
  },
  "reason_codes": [
    "INVALID_ATTESTATION_INTEGRITY",
    "VERIFIER_QUORUM_MISSING"
  ],
  "diagnostics": [
    "UNREGISTERED_ATTESTATION_IGNORED"
  ],
  "receipt_digest": "sha256:…",
  "relied_on": [
    {
      "id": "forge/main/tip",
      "version": "a3d5441…"
    },
    {
      "id": "origin_pr/<n>/forge_head",
      "version": "<head_sha>"
    }
  ],
  "evidence_pointers": {
    "workspace_pointer": "repo=playground branch=cursor/… sha=…",
    "log_path": "/tmp/ci-run.log",
    "upstream_matrix_artifact": "optional: path or URL to resilient-matrix.json if re-run locally"
  }
}
```

**Checker rules (sketch):**

- `authorized === true` only if `reason_codes` is empty **and** `approval_counts` meet policy thresholds **and** `relied_on` versions match current board/forge pointers.
- Any non-empty `reason_codes` → treat as **rollback**; do not merge on narrative PASS alone.
- `receipt_digest` must re-hash the declared fields; mismatch → **`FORGED_RECEIPT`** (Team OS local code — not an upstream enum).

---

## Observation checklist (quorum receipt row)

Log **one row per merge/release attempt** when borrowing RemedyFabric semantics. **Log only.**

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `run_id` | string | Cloud Agent / session id |
| `candidate_digest_sketch` | string | Hash or short id of proposed change set (PR head SHA acceptable sketch) |
| `gate_outcome` | enum | `authorized` \| `rollback` \| `parked_human` |
| `reason_codes` | string[] | Blocking codes (upstream names or Team OS extensions) |
| `duplicate_identity_seen` | bool | Same `actor_id` counted twice toward quorum |
| `forged_pass_suspected` | bool | PASS claim without bound log/test artifact |
| `relied_on` | json | Decision-used pointer subset only |
| `receipt_digest_sketch` | string | Optional content hash of receipt object |
| `notes` | string | Link `log_path`; matrix re-run Y/N |

### Example row (**example** — fictional)

| label | run_id | candidate_digest_sketch | gate_outcome | reason_codes | duplicate_identity_seen | forged_pass_suspected | notes |
|-------|--------|-------------------------|--------------|--------------|-------------------------|----------------------|-------|
| **example** | `ca-run-rf-sketch-k2` | `pr-head-deadbeef` | `rollback` | `["INVALID_ATTESTATION_INTEGRITY"]` | false | true | Smith claimed green CI; Checker bound log missing; no merge |

---

## Out of scope (2026-11-04)

- **Agent Passport** — **DROP** (public GitHub target **404** at cite time); **no** passport / identity-doc sketch in this file or README row  
- Installing RemedyFabric, Docker AgentTeams live path, or re-running **`run_resilient_matrix.py`** in this agent VM (unless a future turn explicitly runs and pins output SHA)  
- Claiming **AgentTeams hosted** success when only [`agentteams-runtime-blocked.json`](https://github.com/Oxygen56/remedyfabric/blob/main/artifacts/agentteams-runtime-blocked.json) or missing strict `agentteams-live-evidence.json` validation applies  
- Claiming **frozen-release** receipts (`clean-replay.json`, `public-ci.json`, …) — upstream **pending**  
- DSH / Feishu / SQLite / daemon / new bots / Slack wiring  
- Editing [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) bodies or **Origin PR #10** description / park body  
- Open sibling day-sketch files **#8–#20** (reserved on parallel PR branches **#19–#31** — see [README](./README.md))  

---

## Status

- [x] Planning (quorum receipt + role map sketch)  
- [ ] In Progress (no RemedyFabric runtime in playground)  
- [ ] Complete  

**Next step:** Optionally run upstream judge commands in an isolated checkout and attach one real `quorum_decision` excerpt to `notes`; until then, Checker uses this schema + reason-code refuse list only.

---

## relied_on

- `a3d5441` — `origin/main` tip at branch time ([playground](https://origin.cursor.com/git/coevolution-lab/playground))  
- [github.com/Oxygen56/remedyfabric](https://github.com/Oxygen56/remedyfabric) @ `main` — **Apache-2.0** (repo `LICENSE`; GH API may show Other), **★0**, last push **2026-08-14**, GOAI hackathon-shaped; **Top** local judge path documented; `src/remedyfabric/quorum.py`, [JUDGE_GUIDE.md](https://github.com/Oxygen56/remedyfabric/blob/main/docs/JUDGE_GUIDE.md), `artifacts/quorum-model.json`, `artifacts/agentteams-runtime-blocked.json` (**cite only**, not re-validated here)  
- **Agent Passport** — **not relied on** (GH **404**, DROP)  
- **Resilient matrix:** **not re-run** in this Cloud Agent session — do not infer pass from this PR  
- Origin **PR #32** (`cursor/remedyfabric-quorum-receipt-day-sketch-bfa7`) — handback `relied_on` should pin **`forge_head` at review time** (not self-cited inside the same commit)  
- Sibling sketches [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) on `main`  
- SBUS `relied_on` subset rule: [02](../2026-11-02/02-sbus-version-check-board-rule.md) (**Soft** board pointer IDs)
