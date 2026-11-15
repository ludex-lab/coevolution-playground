# Revocation — executable C0–C5 outcome contract (Soft design note)

**날짜**: 2026-11-04  
**Paper**: [Revocation Is Not Complete at Receipt: An Executable Outcome Contract for Distributed Agent-Tool Gateways](https://arxiv.org/abs/2610.15991) (Liu, Yu, & Zhang, arXiv:2610.15991; DAI ’26)

**Code**: **NONE** — markdown design note only. The preprint cites a review **artifact bundle** (executable C0–C5 monitor, replay scripts, evidence hashes) on an anonymous host — playground **does not** clone, replay E-B24/E-B28, or run Keycloak/OPA/MCPMark harnesses. Treat artifact claims as **Soft UNVERIFIED** here.

## Paper pointer (Top: existence; stats Soft UNVERIFIED)

From the public abstract and §2 on [2610.15991](https://arxiv.org/abs/2610.15991) — playground **does not** reproduce multi-host executions or the 14-case fault matrix:

| Idea (paper) | Sketch |
|--------------|--------|
| **Completion gap** | Revocation may be reported at **issuer commit**, **transport ack**, or **receiver persistence** without every **tool gateway** enforcing deny or **guarded effects** stopping |
| **C0–C5 contract** | **C0** issuer committed → **C1** queued → **C2** transport ack → **C3** persisted at receiver → **C4** gateway enforced (deny installed + receipt) → **C5** effect prevented in bounded window \(W\) |
| **Verdict** | \(\mathrm{Complete}(e,W) = C0 \land \bigwedge_{g\in G(e)} C4(g,e) \land C5(g,e,W)\) — **C1–C3 are progress only**, not completion |
| **False completion** | Rules that treat **C3** or **C4 alone** as done yield **7** or **5** false positives in a derived eight-case audit; bounded **C0–C5** yields **none** (paper §4 narrative) |
| **Primary fault (E-B24)** | Receiver-selective non-delivery: transport + persistence succeed while stale gateways admit **112/225** calls (**49.78%**) and commit effects in every treatment block (two 16-host Keycloak runs) |
| **MCPMark (E-B28)** | Normal **C4**: **31** post-barrier calls denied, no effects; selective **C3**: **344** calls, **145** effects committed (closed-loop agent) |
| **Monitor** | Persistent reference monitor over **frozen** gateway set, call vectors, observation window; verdicts **complete \| partial \| indeterminate \| violated**; sticky violations, immutable conflicting evidence |

**Top (paper exists):** [2610.15991](https://arxiv.org/abs/2610.15991) abstract + stage definitions.  
**Soft UNVERIFIED:** All experiment counts, fault-matrix outcomes, monitor throughput (**1,024** gateways / **10,000** vectors scaling), and artifact replay — **cite only**, no local run.

Playground **does not** implement C0–C5 monitors, CAEP/SSF transports, or gateway receipt joins.

---

## 1) Map C0–C5 → Team OS (Ork → Smith → Checker)

Team OS has no distributed Keycloak gateway mesh; the **same logical mistake** appears when Ork **declares** a capability gone while Smith still holds **cached delegation** (branch lease, MCP session, `handoff_artifact`, or board `relied_on` pointer).

| Stage | Distributed paper reading | Ork | Smith | Checker |
|-------|---------------------------|-----|-------|---------|
| **C0** | Issuer committed revocation | Ork records **`revoke_request`** (edge id, seq, effective time) on the run ticket / board — authoritative **intent to revoke** | Must not treat Ork chat text alone as enforced deny | Logs **`c0_evidence_id`** pointer; does not merge on C0 alone |
| **C1–C2** | Queued / transport ack | Forge hook queued, Slack ack, “revocation sent” — **progress** | May still execute until C4 analog | **`progress_only`**: transport success ≠ revoke complete |
| **C3** | Receiver persisted event | Durable row in ticket DB / PR comment / SSF receiver log — **persisted ≠ enforced** | Paper gap: **112/225** effects after persistence — Smith must assume **stale capability** until C5 check | Reject **`revoke_complete`** claims keyed only on persistence |
| **C4** | Gateway enforced | Each **execution surface** (Cloud Agent worker, MCP gateway, git push lease) emits **`deny_installed`** receipt bound to delegation + event | Stops issuing guarded tool calls; refreshes session if deny receipt missing | Joins receipts for **declared population** only (bounded set) |
| **C5** | Effect prevented in \(W\) | Independent **effect oracle**: no merge/push/deploy in window attributable to revoked edge | No new commits/files under revoked scope after effective time | **`complete`** only with effect-side observation, not gateway HTTP 200 |

### Three Team OS revoke surfaces (design memo)

| Surface | Revoke action | Completion mistake to avoid | C5 analog |
|---------|---------------|-----------------------------|-----------|
| **Capability revoke** | Ork narrows MCP/tool scope, rotates token, closes CA run | “Token revoked at issuer” while another worker still holds old session | No guarded tool effects after `effective_at` in frozen window |
| **Evidence withdraw** | Ork/Smith **withdraw** a `proof_anchor` or board row before Checker KEEP ([07](./07-pcp-shared-human-ask-queue-checklist.md) withdrawable ask pattern) | Treating withdrawn cite as still **`relied_on`** because PR comment persists | Checker verdict **`superseded`**; no merge weight from withdrawn root |
| **Handoff invalidate** | Ork invalidates **`handoff_artifact`** when delegation edge ends ([01](./01-agentbaton-failure-escalate-handoff.md)) | Stronger Smith continues from **`workspace_pointer`** issued under revoked parent `run_id` | New Smith session requires **fresh** artifact + C4 deny on old lease |

**Ork → Smith:** On revoke, send **invalidation packet** (pointers only): `revoke_request_id`, superseded `handoff_artifact` hash, `log_path` segment — **not** transcript replay.  
**Smith → Checker:** Handback includes **`revoke_observation_window`** + **`effect_oracle_refs`**; claim “revoked” is **`completion_claim`** until Checker sees C4+C5 analog ([20-soei-evidence-intent-ledger-design-note.md](./20-soei-evidence-intent-ledger-design-note.md) when landed — claim ≠ proof).

---

## 2) Sample JSON observation row (checklist sketch)

Log **one row per revoke attempt** (declare, progress, or close window). **Log only** — no monitor daemon.

```json
{
  "label": "example",
  "revoke_request_id": "rev-2026-11-04-8f2",
  "delegation_edge_sketch": "smith:mcp:filesystem+postgres@run-ca-8f2",
  "observation_window": {
    "effective_at": "2026-11-04T09:00:00Z",
    "closes_at": "2026-11-04T09:30:00Z",
    "frozen_gateway_set": ["ca-worker-1", "mcp-gateway-a"]
  },
  "stage_evidence": {
    "c0": { "board_row": "experiments/2026-11-04/README.md@a3d5441", "present": true },
    "c1_c2": { "transport_ack": "forge_webhook_queued", "present": true },
    "c3": { "receiver_persisted": true, "notes": "HTTP 202 — not completion" },
    "c4": { "all_gateways_receipt": false, "missing": ["mcp-gateway-a"] },
    "c5": { "guarded_effects_in_window": 2, "oracle_refs": ["log_path:/tmp/ca-8f2-effects.log#L400-420"] }
  },
  "monitor_verdict_sketch": "violated",
  "team_os_surface": "capability_revoke",
  "handoff_invalidated": true,
  "evidence_withdrawn_ids": ["proof-anchor-8f2-a"],
  "checker_stance": "unproven",
  "relied_on": [{ "id": "arxiv/2610.15991/abstract", "version": "v1" }],
  "notes": "C3 true but C4 partial — do not mark revoke complete; Smith handoff superseded"
}
```

Field gloss: **`monitor_verdict_sketch`** ∈ `complete` \| `partial` \| `indeterminate` \| `violated` (paper monitor); **`team_os_surface`** ∈ `capability_revoke` \| `evidence_withdraw` \| `handoff_invalidate`.

---

## 3) Cross-links (markdown only)

- **Escalate / park:** Human **`escalate_to_human`** + park ([04](./04-impassebench-escalate-to-human-ticket-schema.md)) when revoke blocked by infra impasse — orthogonal to C0–C5 unless revoke itself is the guarded effect.
- **PCM / attestation:** Proof-carrying handoff (open PR #23 **`12-pcm-*`**) — stale evidence after revoke should **`failed`** like broken hash chain (Soei sketch PR #31).
- **Delegated scope:** Affordance violation checklist (open PR #19 **`08-delegated-*`**) — revoke completes only for **registered** gateways in the frozen set; unknown worker ⇒ **indeterminate**, not safe.

---

## Soft no runtime caveat

- **This file is a design note only** — no C0–C5 monitor, no Keycloak/OPA/Toxiproxy stack, no MCPMark replay, no artifact checkout in playground.
- Paper stats (**49.78%**, **112/225**, **145/344**, false-positive audit counts, etc.) are **Soft UNVERIFIED** citations from [2610.15991](https://arxiv.org/abs/2610.15991); not reproduced here.
- Mechanism sketch (Ork/Smith/Checker mapping, JSON row) is **Soft** — not validated against paper artifact or Team OS production gates.
- **`relied_on`:** Declare **board pointer ID + version** for evidence actually used in this sketch ([02](../2026-11-02/02-sbus-version-check-board-rule.md)); paper abstract only for stage definitions.

---

## Parked (not in this PR)

| Item | Note |
|------|------|
| **Evidence-Guided** [2610.41453](https://arxiv.org/abs/2610.41453) | **Next Soft** sibling sketch — **do not implement** in this PR |
| **wave8 DRS** | Parked — no file |
| **DelegateOS** | Parked — no file |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Cloning anonymous review artifacts or re-running E-B17–E-B28  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or open sibling sketches **#8–#27** (reserved on Origin PR #19–#38 branches)  
- **Origin PR #10** (AgentBaton / Copilot trajectory)—**leave PR #10 alone**; no Cody trajectory columns  

---

## Status

- [x] Planning (C0–C5 → Team OS revoke surfaces Soft sketch)  
- [ ] In Progress (no monitor runtime)  
- [ ] Complete  

**Relied on (SHAs):** `a3d5441` (main tip at branch: PCP #7 / merged PR #18); paper [2610.15991](https://arxiv.org/abs/2610.15991) abstract + §2 stage definitions — **Top**; experiment counts + artifact replay — **Soft UNVERIFIED**.

**Next step:** On real capability revoke, log C3 vs C4 vs C5 separately before Checker accepts **`revoke_complete`**; tabletop one fictional JSON row — no merge of this doc required for ops.
