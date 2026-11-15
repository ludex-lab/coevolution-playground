# PCM — proof-carrying handoff (Smith → Checker day sketch)

**날짜**: 2026-11-04  
**Paper**: [PCM: A Proof-Carrying Message Protocol for Verifiable Multi-Agent Communication](https://arxiv.org/abs/2610.39109) (Ghosh, Cygnux Labs, arXiv:2610.39109)

**Code**: [Cygnux-Labs/PCM-protocol](https://github.com/Cygnux-Labs/PCM-protocol) (MIT) — **Soft UNVERIFIED** in playground: no Tracekit attesting signer, no `tracekit pcm demo`, no Merkle log replay wired to Team OS. Public spec + README cited only; optional spot-check: independent Python verifier vector suite (`560` tests) passed outside this repo—does **not** substitute for end-to-end PCM 0.1 demo.

## Paper pointer (citation only; no PCM runtime today)

From the public abstract and §5–§8 on [2610.39109](https://arxiv.org/abs/2610.39109):

- **Gap:** A2A/MCP authenticate **who sent** the message; the doubtful party is often the **sender’s claims** (“tests passed”, “alice approved”).
- **PCM shape:** Each claim carries **evidence**—records from an append-only Merkle log the agent **cannot write**, with inclusion proofs, signed by an **attesting signer** the agent does not control. Receivers check **offline** and assign each claim **`proven` \| `unproven` \| `failed`** (doubt ≠ falsity).
- **Self-report rule:** A claim resting only on the agent’s own tool report is **`unproven`**, never **`proven`** (T1 vs attested T2 tier in spec).
- **Authority:** Grant chains root in a **recorded human approval**; links may only **narrow** under a typed implication table.
- **Benchmark (paper numbers only):** Pre-specified **926** messages, **712** lies in **16** classes; PCM 0.1 accepts **10** lies (**1.4%**, all **stale evidence**—real events later undone); plain A2A accepts all **712**; independent verifiers agree on all **926** verdicts (~**1 ms** check).

Playground **does not** deploy PCM envelopes, pinned schema hashes, or RFC 9162 checkpoints.

---

## Map to Team OS (Smith → Checker handback; markdown only)

| PCM idea | Team OS analog (this sketch) |
|----------|-------------------------------|
| Message + claims + evidence bundle | Smith **handback packet** must not be bare prose “tests passed”; it carries a **`tests_passed_claim`** object with **`evidence_record`** pointers ([§1](#1-tests_passed_claim--log-backed-evidence-record-shape)) |
| Three-valued claim check | Offline **Checker** stamps each claim **`proven` \| `unproven` \| `failed`** before KEEP/DROP ([§2](#2-checker-verdict-columns-offline)) |
| T1 self-report | Smith narrative or stdout paste **without** attested log segment ⇒ **`unproven`** (never KEEP on “proven” alone) |
| Attested execution (T2 analog) | CI / test runner log segment **written by infrastructure Smith cannot edit** (Team OS `log_path` + hash anchor)—closest playground stand-in for signer-backed record |
| Stale evidence | Green test on **old** branch SHA while `main` moved ⇒ paper’s residual lie class; Checker **`failed`** or **`unproven`** + explicit stale flag ([§3](#3-inject-plan-three-fakes-tabletop)) |
| Grant / approval claims | Human merge approval or scope grant as **chain**—forged parent ⇒ **`failed`** ([CoworkOS #9](./09-coworkos-delegation-evidence-contract-day-sketch.md) when landed; PR #20) |

Cross-links: mechanical **`handoff_artifact`** (`workspace_pointer` + `log_path`) from [01](./01-agentbaton-failure-escalate-handoff.md); **`verified_progress`** bullets only when observation-backed ([06](./06-care-escalate-verified-progress-checklist.md)); delegation **`expected_evidence`** ([09](./09-coworkos-delegation-evidence-contract-day-sketch.md) PR #20).

---

## 1) `tests_passed_claim` — log-backed evidence record shape

Smith → Checker handback **must** include this object whenever the run asserts test success (pytest, `npm test`, etc.). Narrative-only success is **`unproven`** by policy.

### Envelope (sketch)

| Field | Type | Required | Definition |
|-------|------|----------|------------|
| `claim_id` | string | yes | Stable id (`pcm-claim-tp-7c2`) |
| `claim_type` | enum | yes | `tests_passed` (PCM claim-family analog) |
| `command_sketch` | string | yes | Exact or normalized test invocation (no shell injection ambiguity in real PCM—here: **literal cmd for audit**) |
| `workspace_pointer` | object | yes | Repo, branch, **head SHA at test time** ([01](./01-agentbaton-failure-escalate-handoff.md)) |
| `evidence_record` | object | yes | Log-backed proof bundle (below)—**not** chat transcript |
| `grant_refs` | string[] | no | If success gated on human scope, ids of approval/grant rows |
| `smith_assertion_tier` | enum | yes | `T1_self_report` \| `T2_attested_log` — Smith **declares** tier; Checker **recomputes** from evidence (mismatch ⇒ **`failed`**) |

### `evidence_record` (log-backed)

| Field | Type | Required | Definition |
|-------|------|----------|------------|
| `log_path` | string | yes | File or CI artifact URL Smith **cannot rewrite after fact** (infra-owned) |
| `log_segment` | object | yes | `{ start_byte, end_byte }` or `{ line_start, line_end }` into `log_path` |
| `log_digest` | string | yes | SHA-256 of **segment bytes** (Checker recomputes) |
| `exit_code` | int | yes | Process exit code recorded in same segment |
| `recorded_at` | string | yes | ISO timestamp from log or CI metadata (not Smith free text) |
| `attestation_sketch` | enum | yes | `ci_job` \| `cloud_agent_run_log` \| `local_tee_unverified` — **`local_tee_unverified` caps at `unproven`** unless upgraded |
| `pcm_evidence_ids` | string[] | no | Future: Merkle record ids + inclusion proof refs (PCM 0.1)—empty in markdown-only phase |

### Example claim fragment (**example** — fictional)

```yaml
claim_id: pcm-claim-tp-mock-1
claim_type: tests_passed
command_sketch: "pytest tests/test_api.py::test_health -q"
workspace_pointer:
  repo: playground
  branch: cursor/pcm-proof-carrying-handoff-262d
  head_sha: "a3d5441"
evidence_record:
  log_path: "/tmp/cloud-agent-run-pcm-mock.log"
  log_segment: { line_start: 880, line_end: 912 }
  log_digest: "sha256:9f3c…"
  exit_code: 0
  recorded_at: "2026-11-04T08:05:12Z"
  attestation_sketch: cloud_agent_run_log
smith_assertion_tier: T2_attested_log
```

**Norm:** Checker **rejects KEEP** when `tests_passed_claim` is missing but Smith summary says “tests passed”.

---

## 2) Checker verdict columns (offline)

Log **one row per claim** at handback. PCM separates **`unproven`** (insufficient evidence) from **`failed`** (malformed or contradicted).

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `handback_id` | string | Smith run / PR handback key |
| `claim_id` | string | Join to `tests_passed_claim.claim_id` |
| `checker_claim_result` | enum | **`proven` \| `unproven` \| `failed`** |
| `checker_message_verdict` | enum | Roll-up sketch: `accept` \| `accept-unproven` \| `reject` \| `bad-input` (PCM message-level analog) |
| `digest_match` | bool | Recomputed `log_digest` vs claim |
| `sha_match` | bool | `workspace_pointer.head_sha` still matches git tip cited in log |
| `tier_match` | bool | Declared `smith_assertion_tier` consistent with `attestation_sketch` |
| `stale_evidence` | bool | True if log proves pass on **superseded** commit/base |
| `keep_eligible` | bool | Ork policy output **after** verdict (see [§4](#4-one-pager-should-ork-require-proven-before-checker-keep)) |
| `notes` | string | Pointer to inject case id or lint rule |

### Verdict rules (sketch)

| Condition | `checker_claim_result` |
|-----------|-------------------------|
| Digest mismatch, missing segment, exit_code ≠ 0 in segment | **`failed`** |
| `T1_self_report` or `local_tee_unverified` only | **`unproven`** (never **`proven`**) |
| Digest match + attested log + exit 0 + SHA still current | **`proven`** (Team OS **best-effort**—not full PCM Merkle proof) |
| Digest match but branch/base moved (open PR rebased away) | **`unproven`** or **`failed`** with `stale_evidence=true` (align with paper stale class) |

### Example Checker row (**example**)

| label | handback_id | claim_id | checker_claim_result | checker_message_verdict | digest_match | sha_match | tier_match | stale_evidence | keep_eligible | notes |
|-------|-------------|----------|------------------------|-------------------------|--------------|-----------|------------|----------------|---------------|-------|
| **example** | `hb-pcm-mock-1` | `pcm-claim-tp-mock-1` | `proven` | `accept` | true | true | true | false | true | Full segment in cloud run log; cmd matches green line |

---

## 3) Inject-plan (three fakes — tabletop)

Use in sprint lab **without** live prompt injection: Ork injects corrupted handback fixtures; Checker must not upgrade to **`proven`** or KEEP wrongly.

| # | Fake class | PCM / paper lens | Inject sketch | Expected Checker |
|---|------------|------------------|---------------|------------------|
| **F1** | **Self-written tests-pass** | T1 non-elevation; agent word alone | Smith sets `smith_assertion_tier=T2_attested_log` but `attestation_sketch=local_tee_unverified` and segment is **pasted** into chat-derived markdown, not infra log | **`unproven`**; `tier_match=false`; **`keep_eligible=false`** if policy requires `proven` |
| **F2** | **Forged approval** | Authority grant not rooted in person record | Attach `grant_refs=["fake-alice-approval"]` with no ticket row in [04](./04-impassebench-escalate-to-human-ticket-schema.md) / no JJ merge record; or widen scope vs parent grant ([09](./09-coworkos-delegation-evidence-contract-day-sketch.md)) | **`failed`** on grant path; message **`reject`** |
| **F3** | **Stale evidence** | Paper’s 10 accepted lies (1.4%) | Log segment shows pytest green on SHA `deadbeef` while `workspace_pointer.head_sha` is newer **and** log was captured **before** force-push / main advance | **`unproven`** or **`failed`** with `stale_evidence=true`; never **`proven`** |

### Inject procedure (Ork sketch)

1. Prepare three handback JSON/markdown fixtures under lab control (not production runs).
2. Run offline Checker lint: digest recompute, SHA freshness, tier consistency.
3. Record rows in inject table; aggregate false **`keep_eligible`** rate—target **0** for F1–F3 under strict policy ([§4](#4-one-pager-should-ork-require-proven-before-checker-keep)).
4. **Do not** merge inject fixtures into `main`; tabletop only.

---

## 4) One-pager: should Ork require `proven` before Checker KEEP?

**Question:** When Smith handback includes success claims (tests, lint, “PR ready”), must Checker **`keep_eligible=true`** only if **`checker_claim_result=proven`** for each **required** claim?

| Stance | Pros | Cons |
|--------|------|------|
| **A — Strict (`proven` required)** | Matches PCM strict reading + Team OS anti–execution misrepresentation ([01-mandate run B class](../2026-11-01/01-mandate-agent-run-checklist.md)); blocks laundered “green” narrative | Slows KEEP when only **`unproven`** but work is useful—needs **`accept-unproven`** path with explicit human ack |
| **B — Mixed (`accept-unproven`)** | Allows KEEP with flagged debt (flake investigation, log upload pending) | Ork must tag **`accept-unproven`** in board state—not silent merge |
| **C — Narrative KEEP (reject for PCM pilot)** | Fastest | Accepts F1 self-written tests-pass; **incompatible** with proof-carrying sprint |

**Draft Team OS answer (2026-11-04 sketch):** Default **A** for **`tests_passed`** and scope-sensitive claims; **`unproven`** may park or **`accept-unproven`** only when Ork publishes **`fallback_assumption`** + review time ([09](./09-coworkos-delegation-evidence-contract-day-sketch.md) `ask_main` pattern). **`failed`** ⇒ DROP / re-run Smith. **`stale_evidence`** ⇒ never **`proven`**; require fresh run on current `head_sha`.

---

## 5) Smith → Checker handback wrapper (procedure)

1. Smith finishes work; **does not** send Checker bare “all tests passed”.
2. Smith assembles **`tests_passed_claim`** with **`evidence_record`** pointing at **`log_path`** segment + digest.
3. Smith attaches **`handoff_artifact`** ([01](./01-agentbaton-failure-escalate-handoff.md)) and optional **`verified_progress`** only for subgoals backed by same log segments ([06](./06-care-escalate-verified-progress-checklist.md)).
4. Checker recomputes digest, SHA freshness, tier; writes verdict row ([§2](#2-checker-verdict-columns-offline)).
5. Ork applies KEEP policy ([§4](#4-one-pager-should-ork-require-proven-before-checker-keep)); escalate on repeat **`failure-id`** unchanged ([01](./01-agentbaton-failure-escalate-handoff.md)).

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Tracekit install, attesting signer deployment, Merkle log, or `pip install tracekit-ai` as **requirement** for this sketch  
- Wiring PCM verifier into Cloud Agent runtime  
- Cody trajectory / intervention columns (**PR #10** only—**do not** edit AgentBaton park body or PR #10 description)  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or open PR #19–#22 files (**#8–#11** reserved on those branches)  

---

## Status

- [x] Planning (PCM → Smith/Checker handback sketch)  
- [ ] In Progress (no attesting signer)  
- [ ] Complete  

**Relied on (SHAs):** `a3d5441` (main tip at branch: PCP #7 / PR #18); paper [2610.39109](https://arxiv.org/abs/2610.39109); [PCM-protocol](https://github.com/Cygnux-Labs/PCM-protocol) README + SPEC cite only—**Soft UNVERIFIED** (no `tracekit pcm demo`; verifier vectors spot-run outside repo).

**Next step:** Tabletop inject F1–F3 fixtures in sprint lab; if Tracekit demo is run later, add one row linking real Merkle `pcm_evidence_ids` without changing KEEP policy text.
