# w14 phase deadline sketch

Clean-room phase budget + bounded extension helpers for Team OS runs.

Reference (read-only dig pin):

- Upstream: [Newbluecake/pi-toolkit](https://github.com/Newbluecake/pi-toolkit)
- Pin SHA: `3831a2bda573798925c749d985138c1946db265d` (`master`, tag `v0.10.0` → `d0c259c8e8ff0fa748f2e5b6a72c7e2c4af6b009`)
- Re-checked at port time via `git ls-remote`: `master` unchanged; `dev` @ `f86860e44117e08792b797f4e374244a0eecf8e3` still byte-identical for `src/core/deadline.ts` (SHA-256 `640e416f…`).
- License: MIT © 2026 Newbluecake (not vendored; semantics ported by hand).

## Ported (pure functions)

| Team OS | Upstream `RunPhase` (pi-toolkit) |
|---------|----------------------------------|
| `ingress_queue` | `queue_wait` |
| `config_resolve` / `session_open` | `resolve_config` / `session_create` |
| `worker_attach` | `extension_bind` |
| `first_token_wait` | `prompt_dispatch` |
| `model_slice` | `model_turn` |
| `tool_slice` | `tool_exec` |
| `retry_cooldown` | `retry_backoff` |
| `transcript_compact` | `compaction` |
| `shutdown_grace` / `reap` | `abort_grace` / `reap` |

Functions: `due_at_for`, `idle_due_at`, `extendable_span_ms`, `hard_deadline_at_for`, `extendability` (refusal enum), `extension_grant_cap_ms`, `grant_extension_ms`, `grace_window`, `OVERTIME_PHASES`.

### Lab defaults vs upstream `DEFAULT_BUDGET`

Per-phase timers (`total_ms`, `idle_ms`, `tool_ms`, …) in `lab_budget()` / `PhaseBudget` are **Team OS lab picks**, not pi-toolkit defaults (e.g. lab `total_ms=2_400_000` vs upstream `totalMs=1_800_000`).

The **extension triple** (`max_extensions`, `max_total_factor`, `extend_step_ms`) intentionally matches the upstream pin **shape** so span/grant table tests align with `tests/core/deadline-grace.test.ts`; see [`fixtures/extension_triple.json`](fixtures/extension_triple.json) for an explicit diff.

Measured core size: **`deadline.py` is 192 lines** (`wc -l` on the module only; tests/fixtures excluded).

### Team OS delta vs upstream

- `extension_grant_cap_ms`: **`step_disabled` refusal** when `extend_step_ms <= 0` (typed `(False, "step_disabled")`), not legacy uncapped grants.
- `grant_extension_ms`: callee enforces **`min(cap, headroom)`** so `deadline_at + grant ≤ hard_deadline_at` (same intent as upstream reducer `min(base+ms, H)`).

## Forbidden (out of scope)

pi runtime/extension wiring, web-hub, bash child-registry, spawn-service, ask-user, archive/delivery, subagent spawning, npm/PyPI dependency on pi-toolkit, daemon/HTTP, SQLite/DSH/Feishu, silence/ALLOW-on-timeout doctrine, `applyBudgetPolicy`, `describeTimeout`, `withDeadline`, remaining/effective deadline helpers.

## Run tests

```bash
cd experiments/2026-11-05/w14-phase-deadline
python3 -m unittest -v test_deadline.py
```

## Merge note

Intended as a conflict-free day-sketch under `experiments/`; does not modify Top runtime or PR #78.
