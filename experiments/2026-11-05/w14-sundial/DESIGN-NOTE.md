# Sundial — unseen-time escalation method + doctrine-ban (Soft design note)

**Date**: 2026-11-05  
**Wave**: Lab Dig **Wave14** Soft **#2** (method-borrow + **doctrine-ban**; **Soft→Top forbidden**)  
**Upstream**: [bigjoe-oti/sundial](https://github.com/bigjoe-oti/sundial) — **MIT** ([LICENSE](https://github.com/bigjoe-oti/sundial/blob/74ede107762c61a34edcb49f3c8a48e1949685b6/LICENSE) © 2026 J. Servo LLC)

**Playground tier**: **Soft** — README/design note + optional **~70 LOC** stdlib helper for unseen-time vs wall ceiling only. **Not** a runtime port of Sundial hooks, `PresenceBackend`, launchd watcher, SQLite ledger, or Hermes stand-in wakes.

**Model / scope guard**: Composer-2.5 authoring turn; **do not merge** this PR as Top product runtime; **do not** start Wave14 Soft **#3**; **do not** edit Origin **PR #78–#81**.

---

## Pin table (authority for citations)

| Item | Value |
|------|--------|
| Repository | https://github.com/bigjoe-oti/sundial |
| **Pinned commit** | **`74ede107762c61a34edcb49f3c8a48e1949685b6`** (matches `HEAD` / `refs/heads/main` at pin time) |
| **`git ls-remote` (2026-11-05, this VM)** | `74ede107762c61a34edcb49f3c8a48e1949685b6	HEAD` · same SHA on `refs/heads/main` |
| License | **MIT** |
| Soft tier | **Soft** method-borrow + **Soft UNVERIFIED** (no local Sundial install, no golden-file watcher tests on this VM) |
| Playground base at authoring | `8cf0d98931d6367375313e5a2c5f7adf3f09cfd6` (`origin/main` at branch creation) |

---

## Problem (upstream narrative — cite-only)

Coding agents block on human answers; wall-clock silence is **ambiguous** (visible “not now” vs unseen void). Sundial @ pin measures **absence, not time**: an unseen-time ladder, desktop nudges, deterministic watcher, and a **terminal autonomy contract** when escalation fails. Playground borrows **coordination method** for Team OS observation rows — **not** Sundial product wiring.

---

## Method borrowed (ALLOW — vocabulary + optional pure sketch)

| # | Sundial @ pin | Playground borrow |
|---|---------------|-------------------|
| 1 | **Unseen-time clock** — full speed away, half elsewhere, **paused** while HERE ([README](https://github.com/bigjoe-oti/sundial/blob/74ede107762c61a34edcb49f3c8a48e1949685b6/README.md) escalation diagram) | Method row + [`unseen_time_sketch.unseen_rate`](./unseen_time_sketch.py) — **no** macOS/Linux sensor backends |
| 2 | **Wall ceiling** — “sensors may soften, never block” / backstop forces final rung | `tick_unseen(..., wall_ceiling_s=…)` → `WALL_FORCED_TERMINAL`; policy text: ceiling **never** removed because presence reads wrong |
| 3 | **≤3 pings** per question | `record_ping` cap + README honesty rail cite |
| 4 | **“The watcher must not think”** — pure arithmetic watcher, **no LLM** in wake path ([`docs/escalation-then-autonomy.md`](https://github.com/bigjoe-oti/sundial/blob/74ede107762c61a34edcb49f3c8a48e1949685b6/docs/escalation-then-autonomy.md) @ pin) | Team OS norm: escalation **tick** is deterministic; model may judge **only** after explicit human approval paths — not to ripen nudges |

### Not borrowed (upstream substance — FORBID in playground)

`PresenceBackend` implementations, `NotifyBackend`, launchd/minute watcher, JSON **`data/` ledger**, `sundial ask` commitments, Claude/Hermes hook adapters, webhook delivery, stand-in session briefs, memory-decay enactment, Ruff golden parity suite — all **upstream product**, out of scope.

---

## Doctrine-ban (Team OS — silence-expiry Top #1)

**Team OS law (Wave14):** **Informed non-objection / silent human = approval is FORBIDDEN.**

Sundial’s terminal doctrine @ pin **does** treat prolonged present silence as consent under some conditions. That path is **not** Team OS law and is **not** borrowed here.

### Upstream quote (rejected — cite for audit)

From Sundial [`docs/escalation-then-autonomy.md`](https://github.com/bigjoe-oti/sundial/blob/74ede107762c61a34edcb49f3c8a48e1949685b6/docs/escalation-then-autonomy.md) @ pin **`74ede107762c61a34edcb49f3c8a48e1949685b6`**, section **“The terminal contract”** (approx. lines 64–81):

> Demonstrably present, ask ripe, cycle after cycle of chosen silence →  
> that *is* an answer: **informed non-objection**. A reversible action the  
> agent is reasonably confident in (0.80–0.95) **proceeds** on it; …  
> … the one unforgivable failure is **auto-proceeding** on something the human never actually saw.

Related upstream prose (also **rejected** for Team OS timeout policy):

- README @ pin: agent may **“proceed on its own stated judgment”** after escalation ([README](https://github.com/bigjoe-oti/sundial/blob/74ede107762c61a34edcb49f3c8a48e1949685b6/README.md) intro).
- Essay @ pin: **stand-in** a waiting session may brief at ladder end (deterministic side still enables agent judgment) — **no stand-in auto-proceed** in Team OS.

**Playground rejection (this note):**

1. **No ALLOW-on-timeout.** Silence — including “seen but quiet” — is **never** approval.
2. **No proceed-on-silence** implementation or journal kind implying consent.
3. **No informed non-objection** tier in Team OS policy rows.
4. Terminal silence resolves **only** via Top #1 **`on_expiry`** ∈ {**`DENY`**, **`SAFE_FALLBACK`**, **`ESCALATE`**, **`HOLD`**} — clean-room sketch: [`experiments/2026-11-05/w14-silence-expiry/`](../w14-silence-expiry/) · Origin [PR #78](https://cursor.com/codebase/coevolution-lab/playground/pull/78) (**do not edit that PR from this branch**).
5. Observation / journal rows must **never** record timeout as **`allowed`** / **`approved`** / generic consent.

**Soft vs Top boundary:** This folder stays **markdown + optional pure helper**. It **does not** import or merge Top #1 Python from `w14-silence-expiry/` (**Soft→Top forbidden**). It **points** Checker/Ork at Top #1 for expiry semantics only.

---

## Team OS observation sketch (markdown row — not Sundial ledger)

Example **Soft** log fields when Smith waits on Main/human (analog, not wired):

| Field | Type | Definition |
|-------|------|------------|
| `ask_id` | string | Stable question id |
| `presence_sketch` | enum | `here` \| `elsewhere` \| `away` \| `unknown` — **optional** human tag; not a required sensor |
| `unseen_seconds` | float | Accrued unseen time per method rates (if tracked) |
| `wall_seconds` | float | Monotonic wall since ask — **ceiling always applies** |
| `pings_sent` | int | **≤ 3** |
| `watcher_kind` | enum | **`deterministic_tick`** — **forbid** `llm_wake` |
| `on_expiry` | enum | **`deny`** \| **`safe_fallback`** \| **`escalate`** \| **`hold`** — **forbid** `allow` |
| `journal_kind` | string | Must **not** be `allowed_on_timeout` / Sundial-style proceed |

**Cross-links (siblings):**

| Artifact | Role |
|----------|------|
| [`w14-silence-expiry/`](../w14-silence-expiry/) — Origin **PR #78** | Top #1 **`on_expiry`** clean-room sketch — **authority for terminal silence** |
| [`01-coworkos-revision-checked-leases/`](../01-coworkos-revision-checked-leases/) | **`ask_main`** + `fallback_assumption` vocabulary — complementary bounded-wait row (**not** silence=consent) |
| [`w14-whose-turn/`](../w14-whose-turn/) — Origin **PR #81** | Session turn habits — orthogonal to escalation clock |

---

## FORBID (Wave14 Soft #2)

| | |
|---|---|
| **FORBID** | **Soft→Top**; vendoring Sundial; **required** desktop presence sensor deps; daemon/ledger **product**; ALLOW-on-timeout; **proceed-on-silence** code paths; **informed non-objection** policy rows; SQLite/DSH/Feishu; headcount bots; LLM in **wake/ripen** path; editing **PR #78–#81**; Wave14 Soft **#3** |
| **FORBID** | Journal / receipt fields that mark timeout as **allowed** or human silence as **approval** |

---

## Honesty

| Source | Opened on this VM | Assumed / HTTP-only |
|--------|-------------------|---------------------|
| Pin SHA | `git ls-remote` + raw README/LICENSE/essay HTTP | — |
| Sundial Python tree | **Not checked out** | Hook protocol, backends named in README |
| Local unittest | **`test_unseen_time_sketch.py`** (4 cases) | Upstream Ruff/golden tests **not** run here |

---

## Author claim

| Signal | Value |
|--------|--------|
| License | MIT @ pin |
| Playground tests | 4 unittest cases on pure helpers |
| Intended tier | **Soft** — method borrow + **doctrine-ban**; **no** Checker KEEP pre-filled |

**Checker verdict:** *(empty — Checker assigns KEEP/DROP after review.)*
