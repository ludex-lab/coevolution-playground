# Wave14 Top #1 — silence / expiry clean-room sketch

**Track:** Top KEEP (clean-room day-sketch). **Not** Soft markdown-only work and **not** Top #2.

## Upstream pin (verified at port start)

| Field | Value |
|-------|--------|
| Repository | [TanayPratapSingh/handoff](https://github.com/TanayPratapSingh/handoff) |
| Pin SHA | `b64cac41f47e834d769e591ddaa850622edcf419` |
| Remote `HEAD` at verify | `b64cac41f47e834d769e591ddaa850622edcf419` (matches pin; no re-pin) |
| License | MIT © 2026 Tanay Pratap Singh |

Verification command:

```bash
git ls-remote https://github.com/TanayPratapSingh/handoff b64cac41f47e834d769e591ddaa850622edcf419
git ls-remote https://github.com/TanayPratapSingh/handoff HEAD
```

## Doctrine (Team OS)

**Silence ≠ consent.** There is no ALLOW-on-timeout. When `requires_approval` is true, every rule must declare `on_expiry` ∈ {`deny`, `safe_fallback`, `escalate`, `hold`}. Missing `on_expiry` or `allow`/`ALLOW` is a `ConfigError`.

Expiry is resolved only by caller-driven `tick(now)` — no background thread, daemon, or HTTP.

## Ported (ALLOW slice, stdlib Python)

Clean-room under `silence_expiry/` (~130–180 LOC core):

- `OnExpiry` enum without ALLOW
- JSON policy loader + per-risk `{requires_approval, ladder[], deadline_s, on_expiry, quorum}`
- Deterministic `EscalationEngine.tick(now)` — tier expiry → ladder climb when `on_expiry=escalate` → terminal outcomes
- Per-action `safe_fallback` with **`check_fallbacks`**: substitute must be registered, ≠ same tool, strictly lower risk; invalid → deny at expiry / error at `propose`
- **`requires_approval` defaults true**; unknown rule keys (e.g. `requires_aproval`) → `ConfigError`. `propose()` raises on ungated risks instead of returning `None`.
- **`quorum` ≥ 1**; re-`propose` on terminal `action_id` refused. **`approve()`** exists for quorum=1 only; `quorum>1` and full human-answer paths are **out of scope** (Soft expansion) — `TerminalState.APPROVED` is unreachable without `approve()`.
- Journal kinds including `expired_no_answer`, terminal states distinct from `approved`, and **`fallback_on_timeout`** on the safe-fallback path (never `action.allowed` / generic `allowed` on timeout)

## Forbidden (not in this folder)

Incident-sim worlds/tools, miniyaml, agents/analyst layers, roster/pager product code, daemons/HTTP, ALLOW-on-timeout variants, SQLite/DSH/Feishu, new bots, vendoring the upstream `handoff` package, Soft↔Top confusion.

## Soft ≠ Top

Sibling Soft work for 2026-11-05 lives under markdown design notes (e.g. CoworkOS leases). **This directory is Top KEEP runtime sketch only** — small Python pack + tests, no merge to product runtime.

## Conflict-free vs `main`

Branch is intended to merge only experiment paths under `experiments/2026-11-05/w14-silence-expiry/`; rebase onto latest `origin/main` before merge if the queue moves.

## Run tests

From repo root:

```bash
cd experiments/2026-11-05/w14-silence-expiry
PYTHONPATH=. python -m unittest discover -s tests -v
```

Or:

```bash
PYTHONPATH=experiments/2026-11-05/w14-silence-expiry python -m unittest discover -s experiments/2026-11-05/w14-silence-expiry/tests -v
```
