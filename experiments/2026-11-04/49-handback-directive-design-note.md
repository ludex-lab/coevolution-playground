# Handback orchestrator directive — Top KEEP-with-caveats design note (#49)

**날짜**: 2026-11-04 (Asia/Seoul) · **Wave**: Usage Sprint wave11 Top #2 · **Route**: Ork→Smith  
**Playground tip (authoring)**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (main; stack #19→#59 open — **no rebase onto #59**)  
**Sketch**: [`49-handback-directive/`](./49-handback-directive/) (pure Python ~120 LOC + JSON fixtures; **no** MCP/SQLite)

## Tier — Top KEEP-with-caveats (upstream pin)

| Field | Value |
|-------|--------|
| Concept | **agent-bridge-mcp** `directive.ts` — **`evaluateOrchestratorDirective` ONLY** (not store, not MCP server) |
| Pin SHA | `7ffe3577cf5afaa0ff33b99e3051a6cf2554357f` |
| License | MIT |
| Public tree @ pin | **Public cloneable HEAD** — `git clone` + `git checkout 7ffe3577cf5afaa0ff33b99e3051a6cf2554357f`; read `directive.ts` / `evaluateOrchestratorDirective` at that commit. This PR ships a **semantic Python port**, not vendored TS. |

### Caveats (honest)

| Caveat | Meaning for Checker |
|--------|---------------------|
| **Age / stars** | Upstream surface **&lt;1 day old**, **0★** at triage — treat as **KEEP-with-caveats**, not production-ready upstream. |
| **Unverified runtime (this VM)** | Playground agents may not re-run upstream `npm test` @ pin every turn; **fixture unittest** is the acceptance gate for **this borrow**, not a claim that upstream CI was replayed here. |
| **Node 20 + SQLite** | Reported upstream failures on Node 20 around **store.ts / SQLite** are **runtime/environment**, not evidence that directive **logic** is wrong. **This PR does not import store.ts.** |
| **No isolated directive unit test upstream** | Upstream has **no** standalone test file targeting `evaluateOrchestratorDirective` alone. **Playground fixtures + `test_directive.py` cover that gap.** |

**Naming:** **agent-bridge-mcp directive** ≠ NVIDIA **AgentBaton** ([01](./01-agentbaton-failure-escalate-handoff.md)) ≠ victorkwak **baton** ([#48](./48-append-only-claim-board-design-note.md) on open PR #59). Do not edit `experiments/2026-11-03/`, PR #10, PR #11.

## Problem (Team OS)

Smith **handback** packets mix **reported** progress (agent narrative) with **observed** forge/CI/log facts. Ork needs a **pure function** that maps `(observed, reported, evidence_refs, prior_fingerprint, streak, budget)` → **`action` + `reason`** without SQLite, MCP, or browser gateways — same role as upstream **`evaluateOrchestratorDirective`**.

**Core rule:** **Observed beats reported on conflict only** — if both maps carry a key and values **differ**, **`observed` wins** (`_pick`); if only one side sets a key, that value is used. COMPLETE **`reason`** distinguishes **`observed_complete`**, **`reported_complete`**, and **`aligned_complete`** (never `observed_complete` when completion is **reported-only**).

### Upstream action delta (Team OS choices)

| Topic | Upstream @ pin (summary) | This sketch |
|-------|--------------------------|-------------|
| **`PUBLISH_LOCALLY`** | Present in upstream action set | **Dropped** — not in local `ACTIONS`; use `AUTHORIZE_REMOTE_PUBLISH` / handoff policy elsewhere if needed. |
| **Locked-path violation** | Tends toward **CONTINUE** or **ESCALATE** depending on branch | **Team OS:** hard **`blocked`** + `locked_path_changed:…` (fail-closed on mandate tree edits). |
| **Order: budget vs complete** | Upstream evaluates **completion-first** in places | Sketch checks **`budget.remaining <= 0` before** COMPLETE (budget-before-completion). |
| **`streak`** | May be derived in store layer | **Caller-owned** — Ork/Checker pass `prior_fingerprint` + `streak`; sketch does not persist. |
| **New `evidence_refs`** | Upstream may **reset blocker fingerprint** on new evidence | Sketch maps new refs → **`CONTINUE_AUTONOMOUSLY`** (`new_evidence:…`) without auto-clearing fingerprint (caller resets if mirroring upstream). |

## ALLOW (in scope)

| Item | Sketch |
|------|--------|
| Pure API | `directive(observed, reported, evidence_refs, prior_fingerprint, streak, budget) → DirectiveResult(action, reason)` |
| Actions | `COMPLETE`, `ESCALATE_TO_HUMAN`, `CONTINUE_AUTONOMOUSLY`, `POLL_ATTACH`, `AUTHORIZE_REMOTE_PUBLISH`, `blocked` (**no** upstream `PUBLISH_LOCALLY`) |
| Same blocker ×2 | `streak >= 2` and `prior_fingerprint == blocker_fingerprint` → **`ESCALATE_TO_HUMAN`** |
| New evidence ref | Any `evidence_refs` entry not in effective `prior_evidence_refs` → **`CONTINUE_AUTONOMOUSLY`** |
| Locked path touched | Observed `changed_paths` ∩ `locked_paths` → **`blocked`** (`locked_path_changed:…`) |
| Attach / publish gates | `pending_attachments` → `POLL_ATTACH`; `remote_publish_pending` → `AUTHORIZE_REMOTE_PUBLISH` |
| Budget | `budget.remaining <= 0` → **`ESCALATE_TO_HUMAN`** |

## FORBID (explicitly out of this PR)

| Item | Reason |
|------|--------|
| `store.ts` / SQLite persistence | Upstream durable state; wave hygiene |
| MCP server / browser / OpenClaw gateway | Integration surfaces |
| PR publisher / remote deploy automation | Out of pure directive |
| DSH / Feishu / daemon / headcount ports | Other tracks |
| Soft→Top promotion | This row is **Top KEEP-with-caveats** only |
| Vendoring full upstream repo | Pin + sketch only |
| Editing PR #10 / #11 or `experiments/2026-11-03/` | Sprint directive |

## Fixture table

| Fixture file | Scenario | Expected `action` | Reason prefix (sketch) |
|--------------|----------|-------------------|-------------------------|
| `fixtures/same_blocker_twice.json` | Same `blocker_fingerprint`, `streak=2`; reported says in_progress, observed blocked | `ESCALATE_TO_HUMAN` | `same_blocker_streak:` |
| `fixtures/new_evidence_ref.json` | New `ci:artifact#sha-new` not in `prior_evidence_refs` | `CONTINUE_AUTONOMOUSLY` | `new_evidence:` |
| `fixtures/locked_path_violation.json` | Observed edits file **under** locked `experiments/2026-11-03/`; reported denies change | `blocked` | `locked_path_changed:` |
| (inline test) | Observed `complete`, reported `in_progress` (conflict) | `COMPLETE` | `observed_complete` |
| (inline test) | Reported `complete` only; observed empty | `COMPLETE` | `reported_complete` |

## Run tests

```bash
cd experiments/2026-11-04/49-handback-directive
python -m pytest -q
# or
python -m unittest test_directive.py -v
```

### Test evidence (this VM)

| Environment | Command | Result |
|-------------|---------|--------|
| Python 3.x, 2026-11-04 UTC | `python3 -m unittest test_directive.py -v` in sketch dir | **5 passed**, 0 failed (`pytest` optional) |
| Upstream TS @ pin | `git checkout 7ffe3577…` + read `directive.ts` | **Logic diff** documented above; full upstream test replay **optional** on maintainer machine |

## Out of scope

- Wiring to Origin MCP host, Manus/Codex delegates, approval envelopes, or workboard lifecycle.
- Persisting streak/fingerprint across turns (callers pass `prior_fingerprint` + `streak`; see delta table).
- Parity replay of upstream MCP/store integration (directive-only borrow).

## Status

- [x] Design note (#49)
- [x] Pure Python sketch + fixtures + tests
- [x] README index row (#49 only; siblings #8–#48 reserved on open stack)
- [ ] Merge (intentionally **not** in this PR)
- [ ] Optional: maintainer replay upstream tests @ pin on Node LTS (store failures ≠ directive logic)

## Checker-ready — what to verify

1. **Paths**: Only `experiments/2026-11-04/49-*` + README rows; **no** edits under `experiments/2026-11-03/`, PR #10, PR #11 bodies.
2. **KEEP-with-caveats pin**: Note cites MIT @ `7ffe3577…` and **evaluateOrchestratorDirective-only** scope; caveats table present.
3. **ALLOW/FORBID**: Matches Ork brief; no SQLite/MCP/daemon imports in `.py` files.
4. **Semantics**: `python3 -m unittest test_directive.py -v` → 5/5; `_pick` conflict-only; COMPLETE reasons not mislabeled on reported-only.
5. **README**: Root index adds **only #49**; index note reserves **#8–#48** for open PRs **#19–#59**.
