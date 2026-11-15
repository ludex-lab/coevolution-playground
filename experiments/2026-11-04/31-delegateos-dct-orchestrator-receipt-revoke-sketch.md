# DelegateOS — DCT delegation, attestation receipt, revoke/validate (day sketch)

**날짜**: 2026-11-04  
**Source (Top #2 weak — public repo)**: [newtro/delegateos](https://github.com/newtro/delegateos) — npm **`delegate-os@0.3.0`**, TypeScript middleware (DCT engine, MCP plugin, revocation list, PR-review demo).

**Code in playground**: **NONE** — markdown day sketch only. **Method borrow OK**; **no vendored DelegateOS**, no MCP plugin wiring, no `npm install delegate-os` in this repo.

## Checker KEEP-with-caveats (Top #2 weak) — explicit

| Signal | KEEP note |
|--------|-----------|
| **License (hard line)** | GitHub API **`license: null`**; **`LICENSE` / `LICENSE.md` → HTTP 404** on `main` at inspect time. **`package.json` declares `"license": "MIT"`** but **no SPDX file on disk** → **Waybill-class**: **method-borrow OK** (DCT/attenuation/revoke/validate *ideas*, observation columns); **code-reuse NOT** until an authoritative **`LICENSE`** is committed and GitHub `license` resolves. |
| Stars / activity | **★4** ([GitHub API](https://api.github.com/repos/newtro/delegateos)); last push **2026-10-30** — small but recent vs idle demos. |
| Runnable Top | README documents **`npm test`** (vitest) and **`npm run demo`** → `npx tsx src/demo/scenario.ts` (orchestrator → 3 specialists). **Soft UNVERIFIED this session:** shallow clone + `npm install` hit **peer dependency resolution errors**; vitest did not run — **do not claim green CI or demo output** from playground/agent turn. |
| Scope vs siblings | **Online middleware** (Ed25519 **DCT** + MCP **`tools/call` gate** + in-memory **revocation**) complements **offline** Handover docs ([#26](https://cursor.com/codebase/coevolution-lab/playground/pull/37) branch) and **hash-chained DR JWTs** in DRS ([#30](https://cursor.com/codebase/coevolution-lab/playground/pull/41) branch). Pick per threat model; **license-sensitive copy-paste → Handover/DRS first**. |
| Trust scoring / Biscuit | README + `docs/architecture.md` mark **trust scoring, Biscuit WASM backend, A2A, payments** as **v0.2 deferred** — borrow **v0.1 SJT path only** in sketches. |
| Demo claims | PR-review demo (security / Blazor / database specialists) is **described in upstream README** — **not executed here**. |

**Wave8 Checker verdict:** **KEEP-with-caveats (Top #2 weak)** — borrow **scoped delegation + monotonic attenuation + contract-bound verify + revocation IDs at verify time + attestation chain** for Ork→Smith→Checker *policy* rows; **no upstream source copy** until repo **`LICENSE`** is fixed.

### Soft later (park — **do not implement** in wave8)

| Topic | Pointer | Intent |
|-------|---------|--------|
| Agent Role Contracts | [suirindo/agent-role-contracts](https://github.com/suirindo/agent-role-contracts) (**MIT** on file at cite time) | Role-shaped mandates vs DCT capability tuples — design overlap only |
| Orchestra | (theme overlap) | Orchestration narrative — no filename claims |
| C-BASE | [arXiv:2610.33349](https://arxiv.org/abs/2610.33349) | Citation-only context |
| SpecGate | **pin only** [thanhtung2693/specgate](https://github.com/thanhtung2693/specgate) | Spec gate pin — no SpecGate harness in playground |

---

## Map DelegateOS → Team OS (Ork → Smith → Checker)

| DelegateOS concept | Upstream anchor | Team OS lane | Intent |
|--------------------|-----------------|--------------|--------|
| Root **DCT** mint | `createDCT`, `docs/protocol-spec.md` §3 | **Ork** | Mandate as **scoped capabilities** (`namespace` / `action` / `resource` glob), **contractId**, budget cap, expiry, **maxChainDepth** — not “do whatever” chat brief. |
| **Monotonic attenuation** | `attenuateDCT`, spec §3.4 | **Ork → Smith** | Smith receives **≤ Ork** scope (narrower resources, lower budget, shorter TTL). Sub-delegation to a tool lane must **not widen** authority. |
| **Contract-first done** | Task contract + JSON Schema / composite verify (spec §5) | **Smith** | “Done” = **contract verification sketch** (paths, tests, schema) — aligns with MANDATE **missing evidence** checks ([01-mandate sketch](../2026-11-01/01-mandate-agent-run-checklist.md)). |
| **Attestation** (receipt) | spec §7 `Attestation` / chain | **Smith → Checker** | Signed **completion receipt** back to root — Checker treats as **evidence packet** input (SHA/PR/diff still required independently). |
| **`verifyDCT` gate** | spec §10 verification steps | **Checker** | Fail-closed before tool/merge: expiry, budget, capability match, signature chain, **revocationIds**. |
| **Revocation** | `InMemoryRevocationList`, spec §4 | **Ork / Checker** | Mid-flight **revoke delegationId** — cascading optional; parallel to Handover **H6 supersede** / DRS re-issuance, not chat retraction. |
| MCP plugin | `delegate-os/mcp/plugin` | **Tool boundary** | Maps MCP tool names → capability tuples; filters `tools/list` — **design reference only** in playground. |

**Handoff pointer discipline (unchanged on main):** Ork→Smith relay stays **`handoff_artifact` + `log_path`** ([01](./01-agentbaton-failure-escalate-handoff.md)) — future DCT fields are **metadata beside pointers**, not transcript dumps.

**Cross-links (orthogonal):**

- Repeat **`failure-id`** escalate → [01](./01-agentbaton-failure-escalate-handoff.md).
- Human impasse / park → [04](./04-impassebench-escalate-to-human-ticket-schema.md).
- **Origin PR #10** (AgentBaton / Copilot trajectory) — **do not edit PR #10 body or trajectory files**.
- Sibling **DRS** hash-chain forge break → open **PR #41** `#30` sketch (JWT bundle) — complementary evidence shape.

---

## Sample JSON evidence sketches (schema-only — **example** labels)

Shapes from public [`docs/protocol-spec.md`](https://github.com/newtro/delegateos/blob/main/docs/protocol-spec.md) and README Quick Start — **Ed25519 payloads fictional**; do not treat as live tokens.

### 1) Signed JSON token authority fragment (Ork root → Smith)

```json
{
  "label": "example",
  "format": "delegateos-sjt-v1",
  "authority": {
    "issuer": "<ork-root-principal-base64url>",
    "delegatee": "<smith-principal-base64url>",
    "capabilities": [
      { "namespace": "forge", "action": "open_pr", "resource": "coevolution-lab/playground" },
      { "namespace": "docs", "action": "write", "resource": "experiments/2026-11-04/**" }
    ],
    "contractId": "ct_sprint_wave8_delegateos_sketch",
    "delegationId": "del_wave8_ork_smith_001",
    "parentDelegationId": "del_000000000000",
    "chainDepth": 0,
    "maxChainDepth": 2,
    "maxBudgetMicrocents": 0,
    "expiresAt": "2026-11-04T23:59:59.000Z",
    "issuedAt": "2026-11-04T08:00:00.000Z"
  },
  "signatures": [{ "signer": "<ork-root>", "signature": "<base64url>", "covers": "authority" }]
}
```

### 2) Attenuation row (Smith → Checker tool lane)

```json
{
  "label": "example",
  "attenuation": {
    "attenuator": "<smith-principal>",
    "delegatee": "<checker-verify-principal>",
    "delegationId": "del_wave8_smith_checker_002",
    "contractId": "ct_sprint_wave8_delegateos_sketch",
    "allowedCapabilities": [
      { "namespace": "docs", "action": "read", "resource": "experiments/2026-11-04/31-*.md" }
    ],
    "maxChainDepth": 0,
    "maxBudgetMicrocents": 0
  },
  "monotonic_note": "allowedCapabilities ⊆ parent; budget/TTL ≤ parent (spec §3.4)"
}
```

### 3) Verify + revocation observation row (Checker gate)

```json
{
  "label": "example",
  "run_id": "ca-run-delegateos-31f1",
  "team_os_hops": ["ork_root_dct", "smith_execute", "checker_verify_dct"],
  "verify_context_sketch": {
    "namespace": "docs",
    "operation": "read",
    "resource": "experiments/2026-11-04/31-delegateos-dct-orchestrator-receipt-revoke-sketch.md",
    "revocationIds": []
  },
  "verify_outcome": "ok",
  "checker_independent": {
    "main_tip_sha": "a3d544105a19",
    "pr_url": "https://cursor.com/codebase/coevolution-lab/playground/pull/<TBD>",
    "conflict_free_vs_main": true
  },
  "notes": "DCT ok does not replace diff review; revocationIds empty at verify time"
}
```

### 4) Revocation entry sketch (Ork mid-flight cancel)

```json
{
  "label": "example",
  "revocation": {
    "delegationId": "del_wave8_smith_checker_002",
    "revokedAt": "2026-11-04T09:15:00.000Z",
    "reason": "superseded_by_orchestrator_mandate_rev2",
    "cascade": false
  },
  "expected_verify": "verifyDCT returns deny when delegationId ∈ revocationIds (spec §4)"
}
```

---

## Observation checklist (delegation / receipt / revoke — log only)

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `run_id` | string | Cloud Agent / Team OS run id |
| `delegation_id` | string | Stable id (maps to upstream `delegationId`) |
| `team_os_role` | enum | `ork` \| `smith` \| `checker` \| `tool` |
| `hop` | enum | `root_mint` \| `attenuate` \| `execute` \| `attest` \| `verify` \| `revoke` |
| `contract_id` | string | Task contract key |
| `capability_sketch` | string | One-line `namespace:action:resource` — no secrets |
| `verify_outcome` | enum | `ok` \| `deny_expired` \| `deny_scope` \| `deny_revoked` \| `deny_signature` \| `unknown` |
| `attestation_ref` | string | Pointer to receipt blob path or hash — **not** full token dump in logs |
| `revocation_ids_active` | string | Comma-separated ids at verify time |
| `checker_sha_independent` | string | Commit SHA Checker verified without trusting Smith narrative |
| `notes` | string | Link `log_path`, sibling DRS/Handover analogy |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Vendoring **`delegate-os`** or copying `src/**` until repo **`LICENSE`** is authoritative  
- **`npm test` / demo re-run claims** without a pinned green log in this sketch (**Soft UNVERIFIED** as of write)  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or **Origin PR #10**  
- Implementing **Agent Role Contracts**, **SpecGate**, or **C-BASE** harnesses (park table above)

---

## Status

- [x] Planning (day sketch + sample JSON shapes)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** When Team OS adopts capability-shaped mandates, append observation rows at attenuate/verify/revoke events; keep Checker **`main_tip_sha` + PR URL** independent of DCT narrative — no merge of this doc required for ops.

**relied_on (this session):** GitHub API repo metadata; raw `README.md`, `package.json`, `docs/protocol-spec.md` (§3–§4, §7, §10 headings); **failed local `npm install`** on shallow clone (peer conflict) — **no test/demo Top**.
