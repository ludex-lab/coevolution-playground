# Agent Role Contracts — Ork→Smith→Checker preflight checklist

**날짜**: 2026-11-04  
**Source (Checker KEEP Top #3)**: [suirindo/agent-role-contracts](https://github.com/suirindo/agent-role-contracts) (npm `@netsujo/agent-role-contracts@1.0.1`, stable per upstream README this session)

**Code**: **NONE in playground** — markdown mapping + **cited** public JSON shapes only; no `npm install`, `agent-role-contracts explain`, or CI wiring in this repo turn.

## Checker KEEP (Top) — session-verified caveats

| Signal | KEEP note |
|--------|-----------|
| License | **MIT** ([`LICENSE`](https://github.com/suirindo/agent-role-contracts/blob/main/LICENSE) on disk — Copyright (c) 2026 Netsujo株式会社) — **code reuse OK** under MIT terms; playground still ships **markdown only** here. |
| Scope | **Declaration checker** — role, authority, task write scope, **implementer vs reviewer separation**, handoff/stale-binding checks. Upstream: **“A PASS does not grant execution permission.”** |
| Runnable without keys | Public README: clone + `npm run demo` (Node **≥22.5**), or `npx agent-role-contracts explain` on bundled `starter-*.json` — **not executed in this Cloud Agent turn** → live PASS/FAIL exit codes **Soft UNVERIFIED live** until someone pins a command log. |
| vs prompt-only rules | Catches contradictions such as task scope outside `allowed_write_scopes`, **declared self-review**, stale reviewed subject (upstream failure-case docs) — **deterministic offline preflight**, not runtime permission enforcement. |
| vs Team OS runtime | ARC does **not** authenticate Cloud Agent identity, enforce Origin merge gates, or verify artifact bytes — maps to **Checker preflight + Smith evidence pack**, not Ork chat promises alone. |
| Stars / activity | **Not scored in this sketch** — adoption signal deferred; cite only README + public examples verified below. |

**Wave8 Checker verdict:** **KEEP Top #3** — borrow **bundle + task + handoff declarations** and **explain/check before Smith writes**; do **not** treat ARC PASS as merge authority or Cursor tool allow-list.

### Soft park (do not implement in wave8)

| Topic | Pointer | Intent |
|-------|---------|--------|
| Orchestra | (theme overlap only) | Multi-agent **orchestration** naming — no filename or claims here. |
| C-BASE | [arXiv:2610.33349](https://arxiv.org/abs/2610.33349) | Citation placeholder only — no harness. |
| SpecGate | [thanhtung2693/specgate](https://github.com/thanhtung2693/specgate) | **Pin-only** if a future turn needs spec-gate overlap — **skipped** when ambiguous vs ARC scope. |

---

## Upstream concepts (verified from public README + examples this session)

From [agent-role-contracts README](https://github.com/suirindo/agent-role-contracts/blob/main/README.md) (abridged):

- **Bundle** — policy capabilities, **roles** (`implementer`, `reviewer`, …), **routes** (who executes vs reviews per `task_type`).
- **Task** — `type`, `inputs.scope`, acceptance criteria; checker compares task write target to role **`allowed_write_scopes`**.
- **Handoff** — structured transfer (`from_agent`, `suggested_next_agent`, `evidence`, `required_next_action`, …) for stale/inconsistent declaration checks (schema in repo `schemas/handoff.schema.json`).
- **Demo narrative** — in-scope task **PASS**; scope pointing at `secrets/production.txt` with authority `src/**` → **`TASK_WRITE_SCOPE_OUTSIDE_AUTHORITY`** (expected FAIL); repaired scope **PASS** again.
- **PASS ≠ execution authority** — runtime identity, side effects, evidence authenticity remain **outside** ARC.

Playground **does not** re-run demo, G1 binding, or G2 filesystem adapter demos from upstream.

---

## Map ARC → Team OS (Ork → Smith → Checker)

| ARC artifact / check | Team OS role | Obligation (markdown policy) |
|----------------------|--------------|--------------------------------|
| **`bundle.json` policy + routes** | **Ork** | Before launch: declare **task_type**, accountable role, **separate reviewer**, write scope glob (e.g. `experiments/**`), and escalation when authority insufficient — aligns with sprint brief + non-goals. |
| **`task.json` scope + objective** | **Ork → Smith** | Smith receives task whose `inputs.scope` stays inside Ork-declared authority; out-of-scope paths (secrets, unrelated packages) **must fail preflight** before edit tools run. |
| **`implementer` (`write_scoped`)** | **Smith** | Implementation + evidence pointers only within declared scope; **cannot** `approve_own_implementation`; may delegate to reviewer per bundle. |
| **`reviewer` (`read_only` + `review.perform`)** | **Checker** | Independent declared role — diff/SHA/CI review **without** scoped write; blocks “Smith merged own PR” stories at **declaration** layer (runtime still needs branch protection). |
| **`explain` / check CLI (upstream)** | **Checker** | Run (when wired) **before** handoff to human merge: consistent declarations; log diagnostic code on FAIL — **not** run in playground this turn. |
| **`handoff.json` shape** | **Smith → Checker** | Smith fills completed work, **evidence** (paths + result sketches), risks, `required_next_action`; Checker re-validates if task scope or subject changed ([01](./01-agentbaton-failure-escalate-handoff.md) pointer-only handoff). |
| Stale binding / post-review task drift | **Checker** | Re-check when another agent resumes ([upstream AGENT-SWITCH-REVALIDATION](https://github.com/suirindo/agent-role-contracts/blob/main/docs/AGENT-SWITCH-REVALIDATION.md)) — analog: new Cloud Agent turn after human edited scope. |

Cross-links (orthogonal):

- Repeat **`failure-id`** model escalate → [01](./01-agentbaton-failure-escalate-handoff.md).
- Human impasse / park → [04](./04-impassebench-escalate-to-human-ticket-schema.md); **Origin PR #10** — **do not edit PR #10 body or Cody trajectory columns**.
- Shared-human ask queue → [07](./07-pcp-shared-human-ask-queue-checklist.md) — clarification **asks** vs ARC **write-scope** preflight are separate gates.
- Sibling **Handover / Waybill** enforcement docs → open wave7 branches (PR #37 / #36) — **offline doc verify** vs ARC **JSON declarations**; complementary, not merged here.

---

## Evidence sketch — public JSON samples (verbatim shapes, truncated)

Upstream [`examples/starter-task.json`](https://github.com/suirindo/agent-role-contracts/blob/main/examples/starter-task.json) (fields verified this session):

```json
{
  "schema_version": "0.1",
  "id": "starter-change-1",
  "type": "code-change",
  "objective": "Change one file under src and send it to an independent reviewer.",
  "inputs": { "scope": "src/example.mjs" },
  "acceptance_criteria": [
    "The requested file stays inside declared write authority.",
    "The reviewer remains independent from the implementer."
  ]
}
```

Upstream route slice from [`examples/starter-bundle.json`](https://github.com/suirindo/agent-role-contracts/blob/main/examples/starter-bundle.json):

```json
{
  "task_type": "code-change",
  "accountable": "implementer",
  "executors": ["implementer"],
  "reviewers": ["reviewer"],
  "require_human_approval": true
}
```

Implementer authority fragment (same bundle — `allowed_write_scopes` vs task scope is the core check):

```json
{
  "authority_mode": "write_scoped",
  "allowed_write_scopes": ["src/**"],
  "cannot": ["approve_own_implementation"],
  "may_delegate_to": ["reviewer"]
}
```

**Team OS fictional mapping row (`example` — not executed):**

| label | ork_bundle_ref | smith_task_scope | checker_preflight | arc_diagnostic | outcome |
|-------|----------------|------------------|-------------------|----------------|---------|
| **example** | `playground-sprint-32-markdown-only` | `experiments/2026-11-04/32-agent-role-contracts-preflight-checklist.md` | `explain --bundle … --task …` **not run** | (expected **PASS** if scope ⊆ `experiments/**`) | `declaration_ok_sketch` |

Out-of-scope counterpart upstream: [`starter-task-outside-scope.json`](https://github.com/suirindo/agent-role-contracts/blob/main/examples/starter-task-outside-scope.json) → README documents **`TASK_WRITE_SCOPE_OUTSIDE_AUTHORITY`**, exit **1** — Team OS analog: Smith asked to edit `secrets/` or default branch protection paths while Ork brief said `experiments/**` only.

Handoff evidence header ([`examples/handoff.json`](https://github.com/suirindo/agent-role-contracts/blob/main/examples/handoff.json) — fictional upstream example):

```json
{
  "schema_version": "0.1",
  "from_agent": "implementer",
  "suggested_next_agent": "reviewer",
  "current_status": "ready_for_review",
  "evidence": [
    {
      "file": "docs/example.md",
      "result": "Fictional example only. No real source file was checked."
    }
  ],
  "required_next_action": "Review the stated evidence.",
  "risks": ["Actual reviewer identity is not verified."]
}
```

**Checker translation:** evidence entries should become **`log_path` + SHA pointers** ([01](./01-agentbaton-failure-escalate-handoff.md)), not transcript paste; ARC **`risks`** line stays true — declaration PASS does not prove which Cursor model instance reviewed.

---

## Observation checklist (declaration preflight — log only)

Log **one row per task handoff** when Ork/Smith/Checker adopt ARC-shaped declarations. **No automated checker** in playground.

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `run_id` | string | Cloud Agent / sprint run id |
| `task_id` | string | Stable task id (ARC `task.json` `id` analog) |
| `task_type` | string | e.g. `code-change`, `docs-sketch` |
| `declared_write_scope` | string | Glob from Ork bundle (Smith must not exceed) |
| `task_input_scope` | string | Path(s) Smith task requests |
| `implementer_role` | string | Declared executor id |
| `reviewer_role` | string | Declared reviewer id (must differ from implementer) |
| `preflight_tool` | enum | `arc_explain` \| `arc_check` \| `none` \| `unknown` |
| `preflight_result` | enum | `pass` \| `fail` \| `skipped` |
| `diagnostic_code` | string \| null | e.g. `TASK_WRITE_SCOPE_OUTSIDE_AUTHORITY`, `G1_SUBJECT_MISMATCH` (upstream codes only when observed) |
| `human_approval_required` | bool | Route flag analog (`require_human_approval`) |
| `handoff_status` | string | e.g. `ready_for_review` |
| `evidence_pointer` | string | `workspace_pointer` + `log_path` — no transcript dump |
| `notes` | string | PASS treated as non-merge-authority reminder |

### Example row (**example** — fictional)

| label | run_id | task_id | task_type | declared_write_scope | task_input_scope | implementer_role | reviewer_role | preflight_tool | preflight_result | diagnostic_code | human_approval_required | handoff_status | evidence_pointer | notes |
|-------|--------|---------|-----------|------------------------|------------------|------------------|---------------|----------------|------------------|-----------------|-------------------------|----------------|------------------|-------|
| **example** | `ca-run-arc-sketch-32a` | `sprint32-docs` | `docs-sketch` | `experiments/2026-11-04/**` | `experiments/2026-11-04/32-agent-role-contracts-preflight-checklist.md` | `smith` | `checker` | `none` | `skipped` | null | true | `ready_for_review` | branch `cursor/agent-role-contracts-day-sketch-a848`; `log_path`: cloud run log | Markdown-only turn; wire `arc_explain` in a later Top replay |

---

## Procedure (Ork sketch — three beats)

1. **Ork — bundle** — Publish route + scopes for the sprint slice (files, forbidden paths, reviewer id). Explicit **`cannot: approve_own_implementation`** analog in brief.
2. **Smith — task + execute** — Work only after scope matches; attach handoff evidence as pointers; if scope drifts, **repair task JSON** (upstream demo pattern) before review.
3. **Checker — explain/check + review** — Run ARC when integrated; independently verify artifacts; **FAIL closed** on declaration errors; **PASS** still requires Origin rules + human merge if `require_human_approval`.

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- `npm install @netsujo/agent-role-contracts`, GitHub Actions adoption YAML vendoring, or G1/G2 adapter demos  
- Cody **`intervened?` / `round#` / outcome** columns (**PR #10 only**)  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or open **PR #10**  
- Orchestra / C-BASE / SpecGate implementation (park table above)  
- Claiming production adoption of ARC — upstream explicitly separates publication from runtime enforcement  

---

## Status

- [x] Planning (preflight + Ork→Smith→Checker mapping sketch)  
- [ ] In Progress (no `agent-role-contracts` CLI in CI)  
- [ ] Complete  

**Next step:** Pin one `agent-role-contracts explain` log on a playground task scope under `experiments/**`; append an `observation` row with real `diagnostic_code` — no merge of this doc required for ops.

## relied_on (Soft / Top honest)

| Tier | Source | Used for |
|------|--------|----------|
| **Top** | [suirindo/agent-role-contracts](https://github.com/suirindo/agent-role-contracts) README + `LICENSE` + `examples/starter-bundle.json`, `starter-task.json`, `handoff.json` | Role separation, scope check narrative, JSON evidence sketches |
| **Top** | Upstream documented codes `TASK_WRITE_SCOPE_OUTSIDE_AUTHORITY`, PASS vs execution disclaimer | Failure mapping |
| **Soft UNVERIFIED live** | `npm run demo`, `npx agent-role-contracts explain` exit codes on this VM | Not run this session |
| **Soft** | GitHub API star count / npm download stats | Intentionally omitted |
| **Park** | Orchestra, [2610.33349](https://arxiv.org/abs/2610.33349), [specgate](https://github.com/thanhtung2693/specgate) | Named only — no claims |
