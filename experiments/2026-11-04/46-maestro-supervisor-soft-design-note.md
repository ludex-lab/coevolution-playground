# maestro-supervisor — Maestro fleet watchdog (Soft design note)

**날짜**: 2026-11-04  
**Intent (one paragraph):** Skim **[maestro-supervisor](https://github.com/tdat-dev/maestro-supervisor)** as a **read-only watcher + human-facing signals** over many [Maestro](https://github.com/tdat-dev/maestro) coding-agent panes: **stuck detection** (traffic-light radar), **progress / fake-done verdicts** from diff + tests + board evidence, **handover briefs** for model swaps, and **one-click rescue** lines into Maestro’s outbox — without trusting agent “done” claims. This document is Team OS markdown only; **Soft KEEP** on the external repo; **no Soft→Top** promotion of sibling sketches.

**Playground `main` tip (branch base):** `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (report if moved at merge).

**Code**: **NONE in playground** — no vendored copy; no Maestro dashboard or fleet API wired here.

**Tier (fold):** **Soft KEEP** overall. **Soft UNVERIFIED** = vitest and any test/CI claim not re-run in this VM (Checker pack: vitest **UNVERIFIED** — kept honest below). Team OS role map and observation rows are **Soft** design memo only — not runtime.

---

## Pin — Soft KEEP (not Top)

| Source | License (README) | Skim tip (2026-11-04 VM) | Checker / VM |
|--------|-------------------|--------------------------|--------------|
| [tdat-dev/maestro-supervisor](https://github.com/tdat-dev/maestro-supervisor) | **MIT** | `7bcf8906565d3376f64f7c475825565c45cbd339` | **`npm test` / vitest** — **Soft UNVERIFIED** (not executed in playground VM; README cites vitest unit tests only) |

**Do not pin** `ddtcorex/*`, `dsh-maestro-*`, or other DSH stacks as this Soft source — unrelated to this note.

**Soft (do not promote to Top):**

- Upstream demo videos, hackathon scope, and roadmap bullets — README skim only.
- `summarize.ts` Meta-model wiring marked “next” in upstream layout — **Soft UNVERIFIED** for Team OS.
- Sibling markdown **[36-watchdog-loopbreaker-gate-design-note.md](./36-watchdog-loopbreaker-gate-design-note.md)** (Origin **PR #47**, loopbreaker + loop-gate) and **[43-stallwatch-progress-gate-design-note.md](./43-stallwatch-progress-gate-design-note.md)** (Origin **PR #54**) — **light analogy only** (fleet stuck radar vs in-loop stall vs offline trajectory gate); **no Soft→Top** of those pins from here.

---

## Upstream signal model (README skim — citation, not port)

Five product questions drive UI: **stuck?** / **done-really?** / **asking?** / **spent?** / **risky?**

| Upstream module (names only) | Team OS reading |
|------------------------------|-----------------|
| `stuck.ts` + `traffic.ts` | Minutes stuck + loop count → **yellow/red** before human wakes to spin |
| `verdict.ts` + `evidence.ts` | **Fake-done** when diff empty, stubs/TODOs, failing tests, or board card still open |
| `handover.ts` | **Handover suggestion** so a new model continues without transcript rehydration (approval path in upstream) |
| `outbox.ts` | Short **rescue / nudge** lines — one burst, human-approved |
| `gate.ts` | Risky shell patterns wait for **one human click**; checkpoint **Restore** after bad edits |
| `cost.ts` | Budget line in plain dollars (upstream product surface) |

Integration surface (factual from README, not a playground port sketch): poll **`GET /api/fleet`** on Maestro’s local dashboard, read **`.maestro/board.json`**, append **`.maestro/outbox.jsonl`** — supervisor stays a **separate process** that does not patch Maestro core. Team OS does **not** adopt Feishu/SQLite/headcount/DSH daemon patterns here.

---

## Light analogy — Ork → Smith → Checker (+ sibling watchdog notes)

| Role | maestro-supervisor lens |
|------|-------------------------|
| **Ork** | Sets budget / rescue approval policy; chooses when **traffic-light red** triggers [01](./01-agentbaton-failure-escalate-handoff.md) tier bump or [04](./04-impassebench-escalate-to-human-ticket-schema.md) **`escalate_to_human`** — not silent overnight spin. |
| **Smith** | Maestro panes (agents) produce screens, diffs, tests; may claim “done” — supervisor treats claims as **untrusted** until evidence. |
| **Checker** | **Verdict card** aligns with mechanical evidence (git diff, test outcome, board Done column) — same spirit as [06](./06-care-escalate-verified-progress-checklist.md) **verified progress**, not narrative PASS. |

**Sibling sketches (markdown cross-links only):**

- **[36-watchdog-loopbreaker-gate-design-note.md](./36-watchdog-loopbreaker-gate-design-note.md)** (Origin **PR #47**) — in-loop **loopbreaker** + offline **loop-gate** STASIS/EXACT_REPEAT; maestro-supervisor is **fleet-level** watch over Maestro HTTP + workspace files, not a drop-in replacement.
- **[43-stallwatch-progress-gate-design-note.md](./43-stallwatch-progress-gate-design-note.md)** (Origin **PR #54**) — caller-supplied progress streaks; upstream stuck radar uses **minutes + loop count** on pane telemetry — analogous **“refuse silent spin”** intent, different host.

---

## Sample observation row (**example** — fictional)

```json
{
  "label": "example",
  "run_id": "ca-run-maestro-fleet-46a1",
  "fleet_snapshot": {
    "needs_human_panes": 2,
    "worst_traffic": "red",
    "stuck_sketch": "Stuck 12m, looping 5x",
    "verdict": "fake_done",
    "verdict_reason_sketch": "tests fail on login step; board card open"
  },
  "handover": {
    "suggested": true,
    "approval_required": true,
    "artifact_sketch": "pointer + last green checkpoint SHA — no transcript dump"
  },
  "watchdog_refuse": true,
  "refuse_reason_sketch": "red traffic + fake_done — no accept until Recheck green",
  "handoff_artifact": {
    "workspace_pointer": "coevolution-lab/playground@cursor/maestro-supervisor-soft-design-c0a9",
    "log_path": "/tmp/cloud-agent-run-46a1.log"
  },
  "relied_on": {
    "playground_main_tip": "a3d544105a19e325dbbb2b5d7e2c5edfcb156098",
    "maestro_supervisor_pin": "https://github.com/tdat-dev/maestro-supervisor",
    "tier_fold": "Soft KEEP",
    "tier_vitest_vm": "Soft UNVERIFIED",
    "tier_team_os_map": "Soft"
  }
}
```

---

## Explicit non-goals

- **No vendoring** maestro-supervisor or Maestro into playground.
- **No DSH / Feishu / SQLite / daemon / headcount** borrow or port sketches from other stacks.
- **No edits** to Origin **PR #10** or paths under **`experiments/2026-11-03/`**.
- **No claim** that playground ran vitest, `npm start --watch`, or Maestro fleet API unless executed and reported (not this turn).
- **No merge** of this sketch into production wiring — markdown design note only.

---

## Wave10 note

Usage Sprint **wave10 Soft** sketch: **maestro-supervisor** fleet watchdog (stuck radar, verdict, handover, rescue outbox), **Soft KEEP**, vitest **Soft UNVERIFIED**, tip SHA at pin table, path **`46-maestro-supervisor-soft-design-note.md`**, **#10 untouched** — **do not merge** this PR by agent instruction.
