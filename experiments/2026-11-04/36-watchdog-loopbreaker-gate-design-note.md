# Watchdog pair — loopbreaker + loop-gate (design note)

**날짜**: 2026-11-04  
**Intent (one paragraph):** Pair **[loopbreaker](https://github.com/prayingperceptions/loopbreaker)** (in-loop stall watcher) with **[loop-gate](https://github.com/chenhz01/loop-gate)** (offline trajectory pathology checker) as a **Watchdog** for agent loops: catch **stasis** and **exact repeats** before token burn, surface **nudge → escalate** while the run is live, and **refuse silent infinite loops** in replay/CI via non-zero exit when pathologies are found. This document is a Team OS sketch only — not a product integration.

**Playground `main` tip (branch base):** `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (unchanged at PR open).

**Code**: **NONE in playground** — no vendored copies of either repo; no edits to upstream `gate.py`.

**Tier (fold):** **Soft KEEP-with-caveats** overall. **Top** = both external pins (repo, license, Checker-pack claims below). **Soft UNVERIFIED** = slices not re-run or not wired in this VM (pytest, Actions/Docker, Team OS map).

---

## Pins — Soft KEEP-with-caveats (Top repos + Soft UNVERIFIED slices)

| Pin | License | Checker-reported signal (Top) | Tip at skim (2026-11-04 VM clone) |
|-----|---------|-------------------------|-----------------------------------|
| [prayingperceptions/loopbreaker](https://github.com/prayingperceptions/loopbreaker) | **MIT** | **pytest 10/10** (Checker pack) | `c28286aff946a906957c0c9bca9b01368ccf5bb2` |
| [chenhz01/loop-gate](https://github.com/chenhz01/loop-gate) | **Apache-2.0** + **CC BY 4.0** (SPEC) | `gate.py check` → **STASIS** + **EXACT_REPEAT** → **exit 1** (Checker pack) | `7c36443ed5cdfe427bdfb2995c1434add3e54c4b` |

**VM re-check this session (honest):**

| Check | Result |
|-------|--------|
| `python3 gate.py check examples/trajectory.jsonl` on loop-gate pin | **Top (this VM)** — STASIS + EXACT_REPEAT; **`LG_EXIT=1`** |
| `pytest` on loopbreaker pin | **Soft UNVERIFIED** — `python3 -m pytest` unavailable (no pytest / venv on VM); Checker **10/10** cited as **Top** pin claim only, not re-proven here |

**Soft (do not promote to Top):**

- loop-gate GitHub Actions / Docker / composite **`action.yml`** — **Soft UNVERIFIED** (not run in playground VM).
- loopbreaker **`examples/spin_demo.py`** — **Soft UNVERIFIED** (not executed here; README-only skim).
- Team OS role mapping below — **Soft** design memo, not wired runtime.

---

## Critical caveat (caller-supplied progress)

**Progress score is supplied by the caller** — neither `StallWatcher.observe(action, progress)` nor loop-gate’s offline signatures **compute** task-level “are we done?” progress inside the gate alone.

- **loopbreaker:** The host/orchestrator must map observations to a **0..4 rubric** (or compatible scalar) on every tick; only **strictly better** scores reset the flat streak ([`watch.py`](https://github.com/prayingperceptions/loopbreaker/blob/main/loopbreaker/watch.py) at pin).
- **loop-gate:** Detects **repeated step signatures** (tool + args + output digest) in a recorded trajectory; it does **not** judge whether retries were justified ([`gate.py`](https://github.com/chenhz01/loop-gate/blob/main/gate.py) header + README).

Team OS must treat **verified progress** (logs, green tests, merged artifacts) as a **separate channel** — align [06-care-escalate-verified-progress-checklist.md](./06-care-escalate-verified-progress-checklist.md), not model narrative alone.

---

## Watchdog pair (runtime vs replay)

```text
  [Smith agent loop]
        │
        ├─ each tick: loopbreaker StallWatcher.observe(action, progress_from_caller)
        │       ok → continue
        │       nudge → Ork/Smith: new tactic (once per stall window)
        │       escalate → stop / human / model tier bump (refuse silent spin)
        │
        └─ append steps → trajectory JSON/JSONL

  [Checker / CI / postmortem]
        loop-gate: python gate.py check trajectory.json --window W --repeat-threshold T
        exit 0 → clean
        exit 1 → STASIS / EXACT_REPEAT / CYCLE findings → refuse merge / refuse accept
```

| Layer | loopbreaker | loop-gate |
|-------|-------------|-----------|
| When | **In-loop** (before next tick) | **Offline** (after steps recorded) |
| STASIS analog | Flat progress streak → nudge/escalate | Consecutive identical normalized signatures |
| EXACT_REPEAT analog | Same action label with flat rubric | Same signature ≥ threshold in sliding window |
| Breaker | `"nudge"` / `"escalate"` strings | `suggest_breaker` → `halt` on STASIS/CYCLE; exit **1** |

---

## Team OS — Ork → Smith → Checker

| Role | Watchdog use |
|------|----------------|
| **Ork** | Defines **progress rubric** and who computes it (tool outcomes, test counters, human checklist); sets **stall_ticks** / loop-gate **window** policy; on **escalate**, triggers [01](./01-agentbaton-failure-escalate-handoff.md) model bump or Impasse [04](./04-impassebench-escalate-to-human-ticket-schema.md) **`escalate_to_human`** — not endless local retry. |
| **Smith** | Calls `observe` every loop tick with **caller progress**; on **nudge**, must change tactic (not identical tool spam); emits trajectory steps for audit. |
| **Checker** | Runs **loop-gate** on exported trajectory before accept; **refuses** “done” when exit **1** unless human waives with documented reason; cross-checks **verified_progress** vs stall signals. |

**Refuse silent infinite loops** = do not authorize the next Smith turn or PR accept while (a) loopbreaker returned **escalate** unhandled, or (b) loop-gate reports **STASIS** / **EXACT_REPEAT** / **CYCLE** on the same run’s artifact.

**Cross-links (markdown only):**

- [01](./01-agentbaton-failure-escalate-handoff.md) — **`handoff_artifact`**: workspace pointer + `log_path`.
- [06](./06-care-escalate-verified-progress-checklist.md) — verified progress memory vs flat local PASS.
- **Origin PR #10** — **do not edit** (AgentBaton / trajectory columns; `experiments/2026-11-03/` paths untouched).

---

## Sample observation row (checklist sketch — **example**)

```json
{
  "label": "example",
  "run_id": "ca-run-watchdog-36c1",
  "loopbreaker": {
    "stall_ticks": 20,
    "last_signal": "escalate",
    "progress_supplier": "caller_rubric_from_pytest_and_git_diff",
    "best_progress_seen": 2,
    "flat_streak_at_escalate": 40
  },
  "loop_gate": {
    "trajectory_pointer": "artifacts/run-36c1-steps.json",
    "exit_code": 1,
    "findings_types": ["STASIS", "EXACT_REPEAT"],
    "breaker_action": "halt"
  },
  "verified_progress": ["README line added; design note path reserved"],
  "watchdog_refuse": true,
  "refuse_reason_sketch": "escalate unhandled + gate exit 1 — no silent continue",
  "handoff_artifact": {
    "workspace_pointer": "coevolution-lab/playground@cursor/watchdog-loopbreaker-gate-design-note-2a55",
    "log_path": "/tmp/cloud-agent-run-36c1.log"
  },
  "relied_on": {
    "playground_main_tip": "a3d544105a19e325dbbb2b5d7e2c5edfcb156098",
    "loopbreaker_pin": "https://github.com/prayingperceptions/loopbreaker",
    "loop_gate_pin": "https://github.com/chenhz01/loop-gate",
    "tier_fold": "Soft KEEP-with-caveats",
    "tier_external_pins": "Top",
    "tier_team_os_map": "Soft",
    "tier_loopbreaker_pytest_vm": "Soft UNVERIFIED",
    "tier_loop_gate_check_vm": "Top (VM re-check)"
  }
}
```

---

## Explicit non-goals

- **No vendoring** loopbreaker or loop-gate into playground.
- **No rewrite** of upstream `gate.py` or loopbreaker package — consume as external pins only.
- **No claim** that playground runs loop-gate Docker, GitHub Action, or upstream CI unless executed and reported (not this turn).
- **No merge** of this sketch into production Team OS wiring — markdown design note only.

---

## Wave9 note

Usage Sprint **wave9 Top1** sketch: **Watchdog pair** (loopbreaker + loop-gate), **Soft KEEP-with-caveats**, progress score **from caller**, pins at table above, **#10 untouched**.
