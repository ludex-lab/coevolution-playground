# stallwatch — post-run stall / progress gate (design note)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint **wave10** (Top design note — **stallwatch**)  
**Upstream**: [shouvikkkk/stallwatch](https://github.com/shouvikkkk/stallwatch)

## Verdict labels (Ork / Checker fold)

**Overall (this note / stallwatch borrow): Top KEEP-with-caveats** — pin **MIT** + Checker **66 passed**; adopt upstream **post-run** trace forensics (`stallwatch check`) without vendoring, without DSH/Feishu/SQLite ports, and without claiming in-loop supervision. **Do not** demote stallwatch intake to Soft-only; caveats below are **Top-layer** borrow limits, not a Soft→Top flip of the note itself.

| Layer | Label | Basis |
|-------|-------|--------|
| **Top** | **KEEP-with-caveats** (overall) | Borrow [shouvikkkk/stallwatch](https://github.com/shouvikkkk/stallwatch) concept + CLI contract for **after-run** stagnation forensics; no vendoring; no live watchdog masquerading as upstream. |
| **Top** | MIT license | Upstream `LICENSE` (MIT, Copyright 2026 Shouvik Maji) — SPDX-compatible pin for Team OS borrow review. |
| **Top** | **66 tests passed** | Checker run on upstream tip (wave10 intake); **this VM re-ran** `python3 -m pytest` → **66 passed** (stdlib harness only; not a playground CI job). |
| **Top** | Post-run scope (caveat) | Reads a **finished** JSONL trace; **not** an in-loop watchdog. Live loop-breaking belongs under **Team OS** Watchdog **#47** sketches, not upstream stallwatch. |

**Top (upstream fact — not a caller-supplied score):** Upstream computes **`progress_score`** in **`stallwatch/report.py`**. Any **“progress-score-from-caller”** caveat applies only to **Team OS R-local glue → Watchdog #47 loopbreaker** wiring — **not** to stallwatch itself.

**Soft (R-local only — not upstream):** Any **`glue_progress.py`** (or similar) that wraps stallwatch output into a Team OS **progress gate** is **Team OS Soft / local glue** in playground — **not** part of [shouvikkkk/stallwatch](https://github.com/shouvikkkk/stallwatch). Do **not** pin glue as a stallwatch feature; do **not** Soft→Top-flip glue or demote the stallwatch note to Soft-only.

---

## Upstream pointer (what stallwatch is)

From the public README on [shouvikkkk/stallwatch](https://github.com/shouvikkkk/stallwatch) (paraphrase + contract only; no vendoring):

- **Problem:** Step caps miss **stagnation** — many tool calls with no meaningful state change still burn tokens.
- **Shape:** Stdlib-only Python CLI; **trace forensics after the run**, not live supervision during it.
- **CLI:** `stallwatch check <trace-file> [--format text|json] [--min-repeat N] [--window N]`
- **Verdicts / exit codes:** `HEALTHY` (0), `DEGRADED` (1), `STALLED` (2), `UNKNOWN` (3 fail-closed).

Playground **does not** install stallwatch as a dependency today; this file is markdown-only scope.

---

## Intent (Team OS)

Use stallwatch as a **post-run progress / stall signal** on Cloud Agent (or other) traces:

1. After a run ends (or on a exported JSONL artifact), run **`stallwatch check`** (out-of-band) and attach **`verdict` + exit code + first stall step** to Checker / Evening Close evidence — analogous to “was there meaningful progress?” without counting steps alone.
2. Pair with **verified progress** handoff fields in [06-care-escalate-verified-progress-checklist.md](./06-care-escalate-verified-progress-checklist.md) and **`failure-id` / escalate** in [01-agentbaton-failure-escalate-handoff.md](./01-agentbaton-failure-escalate-handoff.md): stallwatch answers **trace-level stagnation**; CARE/AgentBaton sketches answer **control transfer** — complementary, not merged runtimes.

### Soft relation — wave9 Watchdog **#47** (loopbreaker / loop-gate)

**Soft only — no Soft→Top flip without a separate Checker pass.**

| Concept | stallwatch (upstream) | Team OS Watchdog **#47** sketch (wave9; open PR **#47** — loopbreaker / loop-gate) |
|---------|----------------------|-------------------------------------------------------------------------------------|
| When | **After** run completes | **During** loop — break or gate before burn completes |
| Input | Finished JSONL trace | Live step / tool stream or periodic cadence |
| Output | Verdict + forensic findings | Loop break, park, or escalate trigger |

If playground ever sketches **`glue_progress.py`** (stallwatch JSON → board row / loop-gate hook), label it explicitly:

- **Team OS Soft / local glue** — wires upstream CLI output into Watchdog **#47**-style gates.
- **Not** an upstream stallwatch feature, **not** a Top pin of glue, **not** a substitute for re-running upstream tests on glue.

---

## Observation sketch (markdown only)

Log **one row per post-run stallwatch invocation** (manual or CI step outside this repo today):

| Column | Type | Definition |
|--------|------|------------|
| `run_id` | id | Cloud Agent / composer run id |
| `trace_path` | path | JSONL trace file path (artifact store — not transcript dump in ticket) |
| `stallwatch_verdict` | enum | `HEALTHY` \| `DEGRADED` \| `STALLED` \| `UNKNOWN` |
| `stallwatch_exit` | int | CLI exit code (0–3) |
| `first_stall_step` | optional int | From JSON/text report when present |
| `progress_score` | float | Computed upstream in **`stallwatch/report.py`** (JSON report); not a caller-supplied field for stallwatch CLI |
| `handoff_artifact` | struct | `workspace_pointer` + `log_path` only ([01](./01-agentbaton-failure-escalate-handoff.md)) |
| `glue_source` | tag | `upstream_cli` \| **`team_os_glue_progress_py`** (R-local only) |

---

## Hard out of scope (2026-11-04 wave10)

- DSH / Feishu / SQLite / daemon ports; **no vendoring** of stallwatch into playground
- Live in-process hooks pretending to be upstream stallwatch
- Editing **`experiments/2026-11-03/`** bodies or **PR #10** Cody / park-await columns
- Merging this PR by agent instruction — **do not merge** (human merge gate)

---

## Status

- [x] Planning (Top design note — stallwatch intake)
- [ ] In Progress (no runtime wiring; no `glue_progress.py` in this PR)
- [ ] Complete

**Playground tip (branch time):** `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (main at wave10 stallwatch note authoring).

**Next step:** If Watchdog **#47** lands loop-gate fields, add a **Soft** cross-link only; keep upstream stallwatch Top pins (MIT + test count) separate from R-local glue.
