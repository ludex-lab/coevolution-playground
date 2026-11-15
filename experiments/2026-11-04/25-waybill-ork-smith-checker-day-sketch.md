# Waybill — Ork→Smith→Checker handoff day-sketch (Team OS borrow)

**날짜**: 2026-11-04  
**Source (weak Top — public runnable, NO LICENSE)**: [ang101/waybill](https://github.com/ang101/waybill) (live [waybill.onrender.com](https://waybill.onrender.com), agent contract [`/skill.md`](https://waybill.onrender.com/skill.md)). **NO LICENSE** on upstream → **method-borrow OK**, **code-reuse NOT**.

**Code**: **KEEP-with-caveats (weak Top)** — public HTTP service + upstream source cited for **pattern** only; playground **does not** vendor, copy, or reuse Waybill code.

> **Checker hard caveat:** **KEEP-with-caveats (weak Top)** — explicit **NO LICENSE** on [ang101/waybill](https://github.com/ang101/waybill) (no `LICENSE` file; GitHub license API **404**) → **method-borrow OK**, **code-reuse NOT**. **★0**, idle **~4mo** since last commit **2026-07-11**. For **license-clear code reuse** when comparing handoff stacks, prefer sibling **[geekidharsh/handover](https://github.com/geekidharsh/handover)** (**Apache-2.0**).

## Checker KEEP-with-caveats — explicit caveats

| Signal | KEEP note |
|--------|-----------|
| License | Explicit **NO LICENSE** on [ang101/waybill](https://github.com/ang101/waybill) — **method-borrow OK**, **code-reuse NOT**; compare **[Handover](https://github.com/geekidharsh/handover)** (**Apache-2.0**) when reuse matters |
| Scope | Hackathon-sized **task-handoff hygiene** service — not a paper reproduction or production identity layer |
| Stars / activity | **★0** at cite time; last push **2026-07-11**, idle **~4mo** at sketch date ([GitHub API](https://api.github.com/repos/ang101/waybill)) |
| Alignment floor | **Keyword overlap** is the deterministic floor — **paraphrase** violations may slip in `check_mode: keyword` only ([SKILL.md limitations](https://waybill.onrender.com/skill.md)) |
| Semantic layer | `/health` may report `semantic_check: configured` — **`semantic:` flags advisory** (non-deterministic); **this Checker turn:** liveness via `/health` curl only |
| Signatures | Ed25519 proves **handoff content** integrity in storage/transit — **not agent identity** (complementary to AgentPass-style “who are you?”) |
| Storage | In-memory on free Render — disclosed hackathon tradeoff; not durable multi-tenant ops |
| pytest | Upstream README claims **69 tests** — **not re-run** in sketch or Checker amend turns (`uv` absent); **R / upstream README only** |
| Demo Act 1–4 | **Not re-run this Checker amend turn.** Prior **wave7 sketch session** manual curl vs live base URL (**R / prior-session only** — root/extend, aligned true·false, `package_drift` 400); do **not** treat as Checker-turn Top evidence |

**Wave7 Checker verdict:** **KEEP-with-caveats (weak Top)** — borrow **signed root + hop lock + pre-execution validate-plan** *as a design pattern* for Team OS Ork/Smith/Checker; **method-borrow OK**, **code-reuse NOT**; do not upgrade to “semantic comprehension guaranteed” or “per-agent auth proven.”

---

## Map Waybill API → Team OS (Ork → Smith → Checker)

| Waybill step | HTTP | Team OS role | Intent |
|--------------|------|--------------|--------|
| **Act 1 — signed root** | `POST /handoffs` | **Ork** (coordinator) | Write **once**: `original_goal`, `constraints`, `out_of_scope`, initial `completed`/`remaining`. Receive `handoff_id`, `signature`, `hop_index: 0`. Pass **`handoff_id`** to downstream — not a paraphrased spawn prompt alone ([SKILL.md](https://waybill.onrender.com/skill.md)). |
| **Act 2 — compliant relay** | `POST /handoffs/{id}/extend` | **Smith** (relay worker) | Update **only** `completed`/`remaining`; locked fields must match root **verbatim** (list order irrelevant). Ork/Smith handoff artifact = **`handoff_id` + log pointer**, not transcript dump ([01](./01-agentbaton-failure-escalate-handoff.md)). |
| **Act 3a — green gate** | `POST /handoffs/{id}/validate-plan` | **Checker** | Smith (or ephemeral subagent) submits **`proposed_plan`** **before** merge/edit execution. Proceed only if `aligned === true` **and** `signature_valid === true` ([SKILL.md decision rule](https://waybill.onrender.com/skill.md)). |
| **Act 3b — red gate (dropped obligation)** | same | **Checker** | Plan omits an obligation (e.g. never mentions **“must log every refund decision”**) → `aligned: false`, deterministic `obligation unmet` flag — **must-log dropped** is the canonical red path in demo + tests. |
| **Act 4 — tamper** | `POST …/extend` with rewritten goal | **Checker / service** | Locked-field rewrite → **HTTP 400** `package_drift`; body returns **root** goal/constraints for self-correction — not silent acceptance. |

Cross-links (orthogonal):

- Repeat **`failure-id`** escalate → [01](./01-agentbaton-failure-escalate-handoff.md).
- Human impasse / park → [04](./04-impassebench-escalate-to-human-ticket-schema.md); **Origin PR #10** — **do not edit PR #10 body or park pattern**.
- SBUS **`relied_on`** pointer discipline → [02 SBUS board rule](../2026-11-02/02-sbus-version-check-board-rule.md) (decision-used subset only).

---

## Evidence JSON sketch (sample shapes — illustrative)

Shapes match [SKILL.md](https://waybill.onrender.com/skill.md) captured examples; field values below are **schema sketches** (IDs/signatures differ per call).

### Root create (Ork) — `201`

```json
{
  "handoff_id": "wb-…",
  "hop_index": 0,
  "signature": "<ed25519-hex>",
  "package": {
    "original_goal": "process the refund request backlog",
    "constraints": [
      "must log every refund decision",
      "never contact the customer directly"
    ],
    "out_of_scope": ["issue partial refunds"],
    "completed": [],
    "remaining": ["triage backlog", "approve refunds"]
  }
}
```

### Validate-plan green (Checker) — `200`

```json
{
  "aligned": true,
  "flags": [],
  "signature_valid": true,
  "check_mode": "keyword+semantic"
}
```

### Validate-plan red — dropped **must-log** — `200`

```json
{
  "aligned": false,
  "flags": [
    "obligation unmet: plan never addresses 'must log every refund decision'"
  ],
  "signature_valid": true,
  "check_mode": "keyword+semantic"
}
```

*(Live deploy may append extra `semantic:` flags; treat deterministic `obligation unmet` / `prohibition violated` as the reliable refuse signal.)*

### Tamper extend (Smith rogue rewrite) — `400`

```json
{
  "error": "package_drift",
  "detail": "original_goal was rewritten: expected 'process the refund request backlog', got 'upsell enterprise customers on premium plans'",
  "root_original_goal": "process the refund request backlog",
  "root_constraints": ["must log every refund decision", "never contact the customer directly"],
  "root_out_of_scope": ["issue partial refunds"]
}
```

---

## Team OS observation row (validate-plan gate)

Log **one row per plan validation** when borrowing Waybill semantics. **Log only.**

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `run_id` | string | Cloud Agent / session id |
| `handoff_id_sketch` | string | Waybill id or Team OS analog (`failure-id` / PR scope bundle) |
| `agent_slot` | string | `ork-root` \| `smith-relay` \| `checker-validate` |
| `proposed_plan_sketch` | string | One-line plan under test — **no transcript dump** |
| `aligned` | bool | Waybill `aligned` or Team OS manual verdict |
| `deterministic_flags` | string[] | Keyword-layer flags only (exclude `semantic:` for gate KPI) |
| `signature_valid` | bool | Content signature check (not identity) |
| `gate_action` | enum | `proceed` \| `block_before_execute` \| `reject_extend_400` |
| `relied_on` | json | Decision-used pointer subset ([02](../2026-11-02/02-sbus-version-check-board-rule.md)) |
| `notes` | string | `log_path`; live vs local Waybill base URL |

### Example row (**example** — fictional Team OS mapping)

| label | run_id | handoff_id_sketch | agent_slot | proposed_plan_sketch | aligned | deterministic_flags | gate_action | notes |
|-------|--------|-------------------|------------|----------------------|---------|---------------------|-------------|-------|
| **example** | `ca-run-wb-sketch-w7` | `wb-e530…` | `checker-validate` | Approve refunds without audit logging | false | `["obligation unmet: … must log …"]` | `block_before_execute` | **example** mirrors upstream demo Act 3b shape (**R** / SKILL.md — not re-run this Checker turn) |

---

## Out of scope (2026-11-04)

- **Vendoring, copying, or forking** [ang101/waybill](https://github.com/ang101/waybill) source into playground (**NO LICENSE** — use live API + method sketch only, or **Apache-2.0 [Handover](https://github.com/geekidharsh/handover)** if licensed reuse is required)
- Installing Waybill in playground, Render deploy, or enforcement proxy (advisory-only today per upstream Q&A)
- Claiming **pytest 69 passed** from **this VM** without `uv run pytest` artifact (**not done here**)
- Replacing Checker with keyword-only alignment for security-critical prohibitions without human review
- DSH / Feishu / SQLite / daemon / new bots / Slack wiring
- Editing [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) bodies or **Origin PR #10** description
- Open sibling day-sketch files **#8–#24** (reserved on parallel PR branches **#19–#35** — see [README](./README.md))

---

## Status

- [x] Planning (Ork→Smith→Checker map + JSON evidence sketch)  
- [ ] In Progress (no Waybill runtime in playground)  
- [ ] Complete  

**Next step:** Optional isolated checkout with `uv sync && uv run pytest` to pin pytest output SHA; until then, Checker uses live **Act 3b** deterministic flag + `package_drift` 400 as refuse templates.

---

## relied_on

| id | version / note |
|----|----------------|
| `forge/main/tip` | `a3d5441` — playground `origin/main` at branch time |
| [github.com/ang101/waybill](https://github.com/ang101/waybill) @ `5881959` | **KEEP-with-caveats (weak Top)** — explicit **NO LICENSE**; **method-borrow OK**, **code-reuse NOT**; ~**4mo** idle since **2026-07-11**; ★0; pytest **69** — **R / README only** |
| [github.com/geekidharsh/handover](https://github.com/geekidharsh/handover) | **Soft** license comparator — **Apache-2.0** sibling handoff stack (**cite only**, not merged on `main`) |
| `waybill.onrender.com/health` | **This Checker amend turn** — `GET /health` curl only (`status` ok; signing/semantic fields as returned) |
| Live demo Act 1–4 | **R / prior wave7 sketch session only** — **not** re-run this Checker amend turn; **not** Checker-turn Top |
| [SKILL.md](https://waybill.onrender.com/skill.md) | Endpoint contract + sample JSON (**Soft** cite for paraphrase/limitation text) |
| Sibling sketches [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) on `main` | **Top** merged playground context |
| SBUS `relied_on` subset rule | [02](../2026-11-02/02-sbus-version-check-board-rule.md) (**Soft** board pointer IDs) |
| Origin **PR #10** | **Not edited** — Copilot trajectory / AgentBaton park sibling; leave alone |
