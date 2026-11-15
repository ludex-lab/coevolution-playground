# AXL protocol — handoff verbs, `store:<sha>`, validator (Soft KEEP-with-caveats)

**날짜**: 2026-11-04  
**Pin (Top)**: [CaelumIT/axl-protocol](https://github.com/CaelumIT/axl-protocol) — **MIT** ([LICENSE](https://github.com/CaelumIT/axl-protocol/blob/main/LICENSE))

**Playground tip at authoring**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (`main` at branch cut; report if moved)

**Code (playground)**: **markdown design note only** — **no vendoring**, no `tools/axl_tools` install, no AXL transcript harness in Team OS this turn.

## Tier policy (honest)

| Layer | Stance |
|-------|--------|
| **Top (pin + Checker)** | Public repo at pin; **MIT** license; upstream [`tools/README.md`](https://github.com/CaelumIT/axl-protocol/blob/main/tools/README.md) documents reference tooling (parser, **validator**, decompiler, gateway, audits, **reference store**, state **ledger**) with **`262` unittest tests passing** under `tools/tests` — **Checker re-ran `python -m unittest discover -s tests` in `tools/` and reported 262 passed** (wave10 Top1). |
| **Soft KEEP-with-caveats** | Borrow **protocol shape**, **verbs**, **`store:<sha>` addressing**, and **validator epistemics/grants** as Ork→Smith→Checker *handoff language* — not a claim that playground runs AXL transports or beats plain English on cost. |
| **Soft UNVERIFIED (this VM)** | Shallow clone read + upstream docs only; **unittest suite not re-executed here** (no local Python run logged). Measured API cost/compliance tables in upstream README, live Claude benchmarks, gateway demo runs, cache policy tuning — **cite upstream, not reproduced**. |
| **Soft caveat (upstream honest limits)** | **Ledger compaction** — upstream measured: **did not pay at ≤21 turns** vs cached history ([`tools/README.md` Ledger](https://github.com/CaelumIT/axl-protocol/blob/main/tools/README.md)). **Anti-laundering** — upstream status **“Not yet shown”** as *behaviour change* (models did not inflate confidence in tested runs); validator *can* reject inflation, but that is **not a proven win** over plain English habits — **Soft caveat, not Top proof**. |

**Borrow scope (HARD):** **protocol / verbs / `store:<sha>` / validator** only.  
**Hard rule (Team OS):** **no SQLite / DSH / Feishu port** — upstream `axl-protocol` **has no SQLite** in tree (fresh clone of `main`); playground still treats SQLite/DSH/Feishu/daemon/headcount ports as **out of scope**, same as sibling experiment notes.

---

## What AXL is (Top docs pointer)

AXL (Agent eXchange Language) is a **compact message protocol** (not a framework): agents exchange acts with typed fields, grants, sessions, and machine-checkable epistemics ([upstream README](https://github.com/CaelumIT/axl-protocol/blob/main/README.md)). Reference tools live in `tools/axl_tools/` — stdlib Python 3.10+.

**In borrow scope for Team OS handoff design:**

| Piece | Upstream role | Team OS sketch (Soft) |
|-------|---------------|------------------------|
| **Verbs + header** | `@v1 … from:…` messages with acts (`QUERY`, `DELEGATE`, `PROPOSE`, `COMMIT`, `RESULT`, `ASSERT`, `GRANT`, `REVOKE`, `PLAN`, …) | Ork brief / Smith handback / Checker verdict as **typed acts**, not prose-only Slack — *schema inspiration only* |
| **`store:<digest>`** | Content-addressed docs; `DEF #name := store:<sha>` binds immutably; `prefetch` / section cites ([`store.py` docs](https://github.com/CaelumIT/axl-protocol/blob/main/tools/README.md)) | Mandate fragments, board rows, log paths as **pointer + digest** in `handoff_artifact` — aligns with [01](./01-agentbaton-failure-escalate-handoff.md) (no transcript dump) |
| **Validator** | Spec enforcement: references, request ids, grant attenuation, role narrowing, epistemic rules (no confidence inflation without `ev`), reply budgets ([`validator.py` summary](https://github.com/CaelumIT/axl-protocol/blob/main/tools/README.md)) | **Checker** replays cited acts + forge evidence; **refuse** handback when acts would fail validator-shaped rules (scope, stale grant, missing `ev`) |

**Out of borrow scope (this note):** shipping `gateway.py` as Team OS runtime, vendoring `tools/`, ledger-as-primary compaction, full decompiler pipeline as runtime, cache/TTL policy tables — even if upstream documents them.

---

## Ork → Smith → Checker (light handoff map)

| Phase | AXL-shaped idea (Soft) | Team OS reading |
|-------|------------------------|-----------------|
| **Ork** | `PLAN` / `DELEGATE` with request ids; policy docs via `DEF … := store:<sha>` | Brief + preservation obligations + tip SHA; attach **digest-pinned** scope text, not chat paraphrase |
| **Smith** | `COMMIT` / `RESULT` under cited `GRANT`; `RESULT #q1` answers named request | Implement within grant; handback = **workspace pointer + log path** + criterion `RESULT` rows — [01](./01-agentbaton-failure-escalate-handoff.md) |
| **Checker** | Validator + optional `audit.completion_gaps` / `retraction_gaps` themes | Independent replay: forge head, CI log, **no** accepting inflated claims or orphan grants; align [MANDATE](../2026-11-01/01-mandate-agent-run-checklist.md) missing-evidence refuse |

**Cross-links (markdown only):**

- [01](./01-agentbaton-failure-escalate-handoff.md) — mechanical `handoff_artifact`
- [02 SBUS](../2026-11-02/02-sbus-version-check-board-rule.md) — stale-write reject vs transcript truth
- [40-agent-handoff-ledger-soft-design-note.md](./40-agent-handoff-ledger-soft-design-note.md) — **sibling on open PR** (MCP/SQLite ledger *pattern*; **not** AXL ledger — different upstream; **file not on `main` until merged**)
- [41-theory-of-scene-soft-design-note.md](./41-theory-of-scene-soft-design-note.md) — shared scene + role (**sibling on open PR** — **file not on `main` until merged**)
- **Origin PR #10** — **do not edit**
- **`experiments/2026-11-03/`** — **do not touch**

---

## Caveats (do not paper over)

| Topic | Upstream / Checker honesty |
|-------|----------------------------|
| **Ledger ≤21 turns** | State ledger compacts live conversation to one AXL message; upstream **measured: didn’t beat cached history at 21 turns or fewer**. Team OS should **not** assume ledger compaction replaces pointer+log handoffs on short Ork→Smith hops. |
| **Anti-laundering** | Protocol + validator encode confidence/provenance rules; upstream headline table: benefit **“Not yet shown”** as behaviour change on tested Claude runs. Treat as **Soft caveat** — Checker may still want explicit `p` / `ev` fields in handback JSON sketches, without claiming AXL solved laundering in production. |
| **262 tests** | **Top** via Checker on upstream `tools/`; **Soft UNVERIFIED** re-run on this cloud VM. |

---

## Sample JSON row (AXL-shaped handoff episode — log only)

```json
{
  "label": "example",
  "run_id": "ca-run-axl-42c1",
  "session_sketch": "ork_smith_checker_v1",
  "acts_sketch": ["DELEGATE #job", "RESULT #job", "ASSERT #head"],
  "store_refs_sketch": ["DEF #mandate := store:3f9a1c07b2de"],
  "validator_refuse_sketch": false,
  "ledger_compaction_sketch": "not_used_under_21_turns",
  "anti_laundering_claim": "unproven_behaviour_change",
  "handoff_artifact": {
    "workspace_pointer": "coevolution-lab/playground@cursor/axl-protocol-handoff-design-note-460d",
    "log_path": "origin/pr/checks (pointer only)"
  },
  "relied_on": {
    "pin": "https://github.com/CaelumIT/axl-protocol",
    "license": "MIT",
    "checker_unittest_tools": "262 passed (Checker; not re-run this VM)",
    "main_tip_sha": "a3d544105a19e325dbbb2b5d7e2c5edfcb156098",
    "tier_borrow": "Soft KEEP-with-caveats",
    "tier_runtime": "Soft UNVERIFIED"
  },
  "notes": "Fictional demo row; no AXL wire traffic in playground"
}
```

---

## Out of scope (2026-11-04)

- **Vendoring** or subtree-import of `axl-protocol`
- **SQLite / DSH / Feishu** port — **none exists in upstream axl-protocol**; hard Team OS rule anyway (no port sketches)
- Daemon / headcount ports
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md), open sibling sketches **#8–#41** (reserved on concurrent Origin PR branches), **`experiments/2026-11-03/`**, or **Origin PR #10**
- Claiming upstream **−43% / −49% token cost** or compliance percentages as Team OS outcomes without a future measured pass

---

## Status

- [x] Planning (AXL **Soft KEEP-with-caveats** handoff sketch)
- [ ] In Progress (no runtime wiring)
- [ ] Complete

**Next step:** If Team OS adopts typed handbacks, prototype **validator-shaped Checker rules** on JSON/log rows first — do **not** merge ledger compaction for short hops until a measured win exists.
