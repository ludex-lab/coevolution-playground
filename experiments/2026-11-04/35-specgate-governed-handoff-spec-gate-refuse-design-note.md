# SpecGate — governed handoff and spec gate refuse (Soft design note)

**날짜**: 2026-11-04  
**Pin (Soft — only source inspected)**: [thanhtung2693/specgate](https://github.com/thanhtung2693/specgate)

**Code**: **GH Soft UNVERIFIED** — public repo and user docs read from the pin this session; **`specgate` CLI / Local store / IDE plugin not installed or run** in playground.

## Top / Soft (honest tiers)

| Layer | This session |
|-------|----------------|
| **Top** | Repo resolves unambiguously at the pin. Public README + linked docs: versioned **artifact approval** → **Context Pack** to coding agent → **delivery evidence** per acceptance criterion → **human accept / request-changes**; readiness **before** implement; delivery review **after**; gate verdicts include `pass`, `warn`, `fail`, `needs_human_review`, `not_run`, `not_applicable` ([governance-and-gates](https://github.com/thanhtung2693/specgate/blob/main/docs/using-specgate/concepts/governance-and-gates.md)). |
| **Soft (Team OS map)** | Ork ≈ publish/approve + policy; Smith ≈ implementing agent with Context Pack; Checker ≈ criterion-level evidence + forge head vs receipt — **design memo only**, not wired to SpecGate store. |
| **Soft UNVERIFIED (runtime)** | `curl \| sh` install, `specgate init`, `specgate doctor`, `work resume`, `change submit --run-checks` — **not executed** here. No claim that playground runs SpecGate gates. |

Playground **does not** deploy SpecGate Full appliance, Doc Registry HTTP, or model-judged delivery review this turn.

---

## SpecGate workflow → Team OS (Ork → Smith → Checker)

Public flow ([coding-agent-workflow](https://github.com/thanhtung2693/specgate/blob/main/docs/using-specgate/guides/coding-agent-workflow.md)):

```text
publish artifact → governance → readiness checks → approve version
→ Context Pack → implement → submit evidence → delivery review → human accept
```

| SpecGate stage | Ork | Smith | Checker |
|----------------|-----|-------|---------|
| **Artifact publish / policy** | Registers scope, impact, governance level; shows governance policy before publish — **not** chat-only mission text | — | Reads **`relied_on`** artifact version ids, not stale chat |
| **Readiness gates (pre-handoff)** | Blocks **implement** delegation until readiness satisfied **and** human approved exact version | Must **stop** if approval absent, Context Pack stale, or contract ambiguous | **`spec_gate_refuse` (readiness)** — no Smith turn without approved pack + AC |
| **Context Pack handoff** | Issues stable **work reference** + pointers (`work resume`, indexed `work context`) | Implements only inside approved scope; material spec change → back to Ork for new version | Verifies handoff cited **work-ref**, not branch name alone |
| **Implement + verify** | Does not silently expand scope | Maps edits to AC; runs checks recorded for evidence | Independent replay of claimed checks |
| **Delivery submit** | — | `change submit` with criterion claims + `--run-checks` when authorized | **`spec_gate_refuse` (delivery)** on failed/skipped check supporting a “met” claim |
| **Delivery review / gates** | Schedules human decision | Returns compact receipt; **no** self-accept | Gate `fail` / `needs_human_review` → **refuse accept** until gap closed |
| **Human accept** | `change accept` / `request-changes` (JJ) | Rework loop on focused feedback | Forge **head SHA** must match completion receipt when policy requires MR observation |

### Spec gate refuse (Team OS reading)

**Refuse** = do not treat the next role as authorized until the gate state allows it (analogous to SpecGate agent **stop** + Checker **non-accept**):

1. **Readiness refuse** — Ork must not assign Smith **implement** when readiness is incomplete or artifact version is not human-approved (SpecGate: agent stops; no editing).
2. **Stale Context Pack refuse** — Checker rejects “done” if approved snapshot digest ≠ what Smith claims ([SBUS stale-write](./../2026-11-02/02-sbus-version-check-board-rule.md) theme — transcript ≠ source of truth).
3. **Evidence refuse** — Checker blocks accept when delivery gate is `fail` or evidence is agent-only without reproducible check output (align [MANDATE missing evidence](./../2026-11-01/01-mandate-agent-run-checklist.md)).
4. **Scope refuse** — Smith silent scope expansion returns to Ork as **new artifact version**, not a green local PR alone.
5. **Park vs refuse** — Environment impasse → [04](./04-impassebench-escalate-to-human-ticket-schema.md) **`escalate_to_human`**, not a readiness typo.

**Cross-links (markdown only):**

- [01](./01-agentbaton-failure-escalate-handoff.md) — **`handoff_artifact`** = workspace pointer + `log_path`, not transcript dump.
- [34-c-base-contract-quotient-delegation-design-note.md](./34-c-base-contract-quotient-delegation-design-note.md) — **quotient work order** vs mission-only brief (sibling on open Origin PR #45 until merged).
- [06](./06-care-escalate-verified-progress-checklist.md) — verified-progress memory vs local PASS.
- **Origin PR #10** — **do not edit** (AgentBaton / trajectory columns).

---

## Sample JSON row (governed handoff episode — checklist sketch)

Append **one object per work item** (approve → Smith implement → Checker gate). **Log only** — no SpecGate store.

```json
{
  "label": "example",
  "run_id": "ca-run-specgate-35b2",
  "work_ref_sketch": "LOCAL-35b2",
  "artifact_version_pinned": "approved@digest (pointer)",
  "readiness_verdict": "pass",
  "context_pack_stale": false,
  "smith_slot": "smith-impl-35b2",
  "delivery_gate_verdict": "needs_human_review",
  "spec_gate_refuse": {
    "readiness": false,
    "delivery": true,
    "reason_sketch": "AC2 evidence unclear — await human accept command"
  },
  "handoff_artifact": {
    "workspace_pointer": "coevolution-lab/playground@cursor/specgate-soft-design-note-1c5e",
    "log_path": "origin/pr/checks/log (pointer only)"
  },
  "checker_stance": "refuse_accept_until_review_id",
  "relied_on": {
    "main_tip_sha": "(set at PR open)",
    "pin": "https://github.com/thanhtung2693/specgate",
    "tier_pin_docs": "Top",
    "tier_team_os_map": "Soft",
    "tier_specgate_runtime": "Soft UNVERIFIED"
  },
  "notes": "Fictional demo row; live Checker binds forge head + PR URL"
}
```

### Column glossary (if flattened to table)

| Column | Type | Definition |
|--------|------|------------|
| `readiness_verdict` | enum | `pass` \| `warn` \| `fail` \| `not_run` \| `unknown` |
| `delivery_gate_verdict` | enum | SpecGate-style verdict on delivery review |
| `spec_gate_refuse.readiness` | bool | True when Smith must not start implement |
| `spec_gate_refuse.delivery` | bool | True when Checker/human must not accept |
| `context_pack_stale` | bool | Approved snapshot no longer matches claimed scope |
| `relied_on` | object | Pin URL + tier tags + SHAs for audit |

---

## Soft park (do not implement in wave8)

| Topic | Pointer | Intent |
|-------|---------|--------|
| Full appliance + Doc Registry | [trust-and-security](https://github.com/thanhtung2693/specgate/blob/main/docs/using-specgate/concepts/trust-and-security.md) | Trusted network only — not Team OS egress default |
| Model-judged gates | `app/agents` (repo layout) | Optional Full mode — observe before delegating verdict to model |
| Verification pins | [CLI contracts](https://github.com/thanhtung2693/specgate/blob/main/docs/using-specgate/reference/cli.md#local-resume-and-verification-contracts) | Pin check commands across resumes — later wave |
| IDE plugin install | [install-ide-plugins](https://github.com/thanhtung2693/specgate/blob/main/docs/using-specgate/guides/install-ide-plugins.md) | Cursor plugin path — separate PR if team adopts |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Installing SpecGate CLI or `.specgate/` store in playground repo  
- Replacing Origin PR review or CI with SpecGate delivery review  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or **Origin PR #10**  
- Inventing alternate **SpecGate** GitHub orgs or forks as substitutes for the pin  

---

## Status

- [x] Planning (Soft design note sketch)  
- [ ] In Progress (no SpecGate runtime wiring)  
- [ ] Complete  

**Next step:** When Team OS adopts governed handoffs, log readiness/delivery refuse rows beside existing **`handoff_artifact`** pointers — aggregate offline; no merge of this doc required for ops.
