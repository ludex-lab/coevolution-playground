# DRS — Ork→Smith→tool 3-hop receipt & middle-hop forge break (day sketch)

**날짜**: 2026-11-04  
**Source (Top, public runnable)**: [OkeyAmy/DRS](https://github.com/OkeyAmy/DRS) — **Apache-2.0**, **★11** (GitHub star count at sketch time; not a quality score).

**Code in playground**: **NONE** — markdown day sketch only. Upstream ships `drs-core` (Rust), `drs-verify` (Go), `@okeyamy/drs-sdk` (TypeScript), and optional `docker compose` for `ghcr.io/okeyamy/drs-verify`.

## What DRS proves (Top — upstream README)

DRS produces **Ed25519-signed**, **SHA-256 hash-chained** delegation receipts (`prev_dr_hash` links each hop). The verifier runs **six blocks (A–F)** fail-closed before a tool handler may run.

**Top (claims, not runtime behaviour):** Receipts are cryptographic evidence of **authorisation and signed claims** — not proof that the tool actually behaved (cost, PII, side effects remain the tool owner’s problem). See upstream [“What DRS proves — and what it does not”](https://github.com/OkeyAmy/DRS#what-drs-proves--and-what-it-does-not).

**Soft UNVERIFIED here:** OAuth 2.1 / RFC 8693 runtime flows, full `integration-tests` middleware topology, Rust `cargo test`, TS SDK suite, and **`docker compose` / published image E2E** — **not** run in this Cloud Agent session unless explicitly noted below.

### Targeted upstream tests re-run (this session — partial Top)

In a shallow clone of `OkeyAmy/DRS` at `bb407901fb2f524d490beff9f7d2c8c36c1e5417`, this agent ran:

```bash
cd drs-verify && go test ./pkg/verify/ -run 'TestChainBreakIsRejected|TestForgedSignatureIsRejected' -count=1
```

Both **PASS** (~4 ms). That locks **middle-hop `prev_dr_hash` tamper → `CHAIN_BREAK`** and **wrong-key delegation JWT → invalid** on the real `Chain()` path — **not** a claim that all Go/Rust/TS tests or Docker E2E were re-run.

---

## 1) Three-hop sketch — Ork → Smith → tool

Map Team OS lanes onto a **depth-2 delegation chain + invocation** (human-rooted consent → two delegations → tool call), aligned with upstream’s human→root→sub→invocation diagram.

| Hop | DRS role (sketch) | Team OS lane | Receipt / gate |
|-----|-------------------|--------------|----------------|
| 0 | Human consent + **root** delegation (operator key) | **Ork / JJ** approves mandate: scope, `cmd` prefix, policy caps | Root DR JWT; `drs_consent` when human-rooted |
| 1 | **Sub-delegation** (narrowing `cmd` / policy) | **Smith** executes assignment under Ork brief | DR₂ with `prev_dr_hash = hash(DR₁)` |
| 2 | **Invocation** + tool-server verify | **Tool** (MCP handler, CI gate, or Checker-as-verifier sketch) | Invocation JWT + `X-DRS-Bundle`; **`POST /verify`** before handler |

**Ork → Smith:** Handoff carries **pointer-only** mandate (`handoff_artifact`, `log_path` — [01](./01-agentbaton-failure-escalate-handoff.md)) **plus** (future) **DRS bundle header** sketch — not a chat transcript rehydration.

**Smith → tool:** Middleware fail-closed: invalid chain, binding mismatch, or stale invocation → **no handler** (upstream `@drs/mcp-server` pattern).

**Checker (Team OS):** Treat **`valid: false`** / `CHAIN_BREAK` / `INVALID_SIGNATURE` like **forge-evidence reject** — parallel to S-Bus **`would_stale_reject`** when declared `relied_on` ≠ current forge ([02](../2026-11-02/02-sbus-version-check-board-rule.md), [04](../2026-11-02/04-sbus-observe-checklist.md)): cryptographic **splice** at hop 1 is not fixable by narrative; require **re-issuance** from Ork root.

---

## 2) Forge-break evidence note — tamper middle `prev_dr_hash`

**Attack sketch (paper/README threat):** Attacker splices a **forged middle delegation** into the chain; bearer context alone cannot detect reorder/splice.

**DRS response (Top — tested subset above):** Receipt *n* must carry `prev_dr_hash = SHA-256(canonical receipt *n−1*)`. Deliberately wrong hash → verifier **`CHAIN_BREAK`** (`TestChainBreakIsRejected` in `drs-verify/pkg/verify/chain_test.go`). Wrong signing key on a receipt → **invalid** (`TestForgedSignatureIsRejected`).

**Team OS forge-evidence analogy (design memo, Soft):**

| DRS verifier | Team OS / S-Bus |
|--------------|-----------------|
| `CHAIN_BREAK` on bad `prev_dr_hash` | Smith handback cites **`origin_pr/…/content_tip`** but middle hop (branch base, parent SHA) **does not chain** to Ork mandate |
| Forged Ed25519 on DR | **Forged or stale `relied_on`** vs board/forge pointer |
| Fail-closed `/verify` | Checker **refuses KEEP** without independent SHA/PR refs ([01](../2026-11-01/01-mandate-agent-run-checklist.md)) |

**Observation row (example — fictional):**

| label | run_id | hop | tamper_sketch | verifier_code | team_os_stance | notes |
|-------|--------|-----|---------------|---------------|----------------|-------|
| **example** | `ca-run-drs-30a1` | middle (Smith hop) | `prev_dr_hash` replaced after sub-delegation minted | `CHAIN_BREAK` | **reject handback**; Ork re-issues root+chain | Pointer-only rebuttal: log `go test` name + upstream file path — not transcript |

---

## 3) Sample bundle observation JSON (checklist sketch)

Log **one row per verify attempt** at the tool boundary. **Log only** — no DRS middleware in playground.

```json
{
  "label": "example",
  "run_id": "ca-run-drs-30a1",
  "chain_depth": 2,
  "team_os_hops": ["ork_root", "smith_subdel", "tool_invoke"],
  "verify_outcome": "reject",
  "error_code_sketch": "CHAIN_BREAK",
  "tamper": "middle_prev_dr_hash",
  "public_evidence": {
    "relied_on": [
      { "id": "github/OkeyAmy/DRS/main/content_tip", "version": "bb407901fb2f524d490beff9f7d2c8c36c1e5417" },
      { "id": "drs-verify/pkg/verify/chain_test.go/TestChainBreakIsRejected", "version": "pass-local-go-test-2026-11-04" }
    ],
    "log_path": "experiments/2026-11-04/30-drs-3-hop-forge-break-day-sketch.md"
  },
  "forge_evidence_note": "Middle-hop hash mismatch = splice; re-issue chain from Ork — analogous to stale forge head vs claimed content_tip",
  "checker_stance": "unproven_until_valid_bundle"
}
```

---

## 4) `relied_on` — Soft/Top honest (this PR)

| Pointer ID | Tier | Version / note |
|------------|------|----------------|
| `github/OkeyAmy/DRS/main/content_tip` | **Top** | `bb407901fb2f524d490beff9f7d2c8c36c1e5417` — README, six-block algorithm, threat model (splice / `prev_dr_hash`) |
| `forge/main/tip` | **Top** | `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` — playground `main` at sketch authoring |
| `drs-verify/chain_test.go` (subset) | **Top (partial)** | `TestChainBreakIsRejected`, `TestForgedSignatureIsRejected` **re-run PASS** in this agent VM |
| `ghcr.io/okeyamy/drs-verify` compose E2E | **Soft UNVERIFIED** | Not run here — may need upstream `docker compose` for full HTTP topology |
| `drs-core` / SDK full matrices | **Soft UNVERIFIED** | Exist upstream; not re-run in this session |

Use **`content_tip`** vs **`forge_head`** split when pinning sibling Origin PRs ([04](../2026-11-02/04-sbus-observe-checklist.md) §7) — this sketch’s **`relied_on`** uses **content_tip** for the DRS repo pin and **forge/main/tip** for playground merge base.

---

## 5) Wave8 sibling queue (Checker fold — **do not implement in this PR**)

| Priority | Item | Checker stance | Note for later sketch |
|----------|------|----------------|------------------------|
| **#2** | [DelegateOS](https://github.com/newtro/delegateos) | **KEEP-with-caveats** (Top weak) | **NO LICENSE** in repo → **method-borrow OK**, **code reuse NOT** (Waybill-class hard line) when that file lands |
| **#3** | [agent-role-contracts](https://github.com/suirindo/agent-role-contracts) | **KEEP Top** (#3 MIT) | After DelegateOS sketch |
| Soft | Orchestra | **KEEP Soft** | Theme overlap with DRS delegation only — no merge claim |
| Soft | [C-BASE arXiv:2610.33349](https://arxiv.org/abs/2610.33349) | **KEEP Soft** | Citation / design overlap only |
| Soft | [SpecGate](https://github.com/thanhtung2693/specgate) | **pin only** | If repo ambiguous or missing, **skip** SpecGate row — do not invent URL |

**After this PR (parked):** DelegateOS day-sketch → Agent Role Contracts → Orchestra Soft (if still KEEP Soft) + C-BASE / SpecGate pins as separate siblings.

---

## Cross-links (markdown only)

- **S-Bus forge gate:** `relied_on` + `CHAIN_BREAK`-style reject ([02](../2026-11-02/02-sbus-version-check-board-rule.md)).
- **Evidence-bound handoff:** Ambiguous tool outcomes vs cryptographic chain ([29-evidence-guided-recovery-design-note.md](./29-evidence-guided-recovery-design-note.md) on open PR #40 — **file not on `main` until merged**).
- **Escalate / park:** Persistent impasse still [`escalate_to_human`](./04-impassebench-escalate-to-human-ticket-schema.md) — distinct from **one-shot** verify reject.

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Wiring `@drs/mcp-server` into Ludex or Cloud Agent runtime  
- Claiming **full Docker E2E** or complete upstream test matrices without a logged run  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or reserved sibling files **`08`–`29`** on open PR branches  
- **Origin PR #10** (AgentBaton / Copilot trajectory) — **leave PR #10 alone**  
- Implementing DelegateOS, Agent Role Contracts, Orchestra, C-BASE, or SpecGate **in this PR**

---

## Status

- [x] Planning (day sketch + Checker fold)  
- [ ] In Progress (no DRS middleware in playground)  
- [ ] Complete  

**Next step:** When tool boundaries adopt bundle verify, append observation rows at reject/accept; pin `relied_on` with **content_tip** + **forge_head** for any Origin PR cited in the chain narrative.
