# Boba — When-to-Speak Gate (Top design note)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint **wave10** (Top pin)  
**Upstream**: [phanngoc/boba-when-to-speak-gate](https://github.com/phanngoc/boba-when-to-speak-gate) — **MIT**

**Code in playground**: **NONE** — markdown design note only; **no vendoring**, no gate runtime, no transport.

## Pin tier (Soft KEEP-with-caveats → Top)

| Tier | Verdict | Rationale |
|------|---------|-----------|
| **Soft** | **KEEP-with-caveats** | Borrow scope is **narrow** (θ band, debounce race-with-humans, per-thread **feedback** nudges). Full 3-stage cascade, open-loop, VN NLP, and production store stack stay **out of scope** for playground. |
| **Top** | **KEEP** | **MIT** license + upstream **Checker: 51 passed** (pytest suite on upstream default branch at pin time). Top documents **what Team OS may conceptually reuse**, not a port. |
| **This VM** | **Soft UNVERIFIED** | pytest **not re-run** on this cloud agent VM (no local re-execution in this turn). Treat **51 passed** as **Top/Checker citation** until someone re-runs upstream CI or `pytest` and logs SHA. |

**Tip (playground base at branch time):** `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` — report if `main` moved before merge.

---

## Borrow scope (HARD — wave10)

**In scope (concept + observation fields only):**

1. **Two-threshold band (θ)** — Stage-1 style decision: `P < θ_low → silent`, `P > θ_high → speak (often deferred)`, uncertain band → escalate only when stakes warrant. Per-thread `theta_low` / `theta_high` with configured floors/ceilings (`boba_gate/config.py`, `thresholds.py`).
2. **Debounce (τ)** — Even after SPEAK, hold **τ** seconds; if humans **resolve** the thread first (proposal, “chốt …”), **cancel** pending speak (`debounce.py`, shared resolution predicate with stage-1 signals).
3. **Feedback adaptation** — Cheap positive/negative signals **nudge** both thresholds online (`apply_feedback`, dismiss → stronger negative); asymmetric product goal: **false speak ≫ false silence** (precision over recall).

**Explicitly NOT borrowed (non-goals):**

- **No** `SqlThreadStore`, **no** Postgres / Redis / SQLite store port from upstream (`store_backends.py`, `schema_postgres.sql`, durable debounce queues).
- **No** DSH / Feishu harness port.
- **No** vendoring `boba_gate/` into playground.
- **Do not** edit **PR #10** or any file under `experiments/2026-11-03/` in this wave.
- **Do not merge** this PR by agent instruction — human merge gate only.

Open-loop tracking, stage-0 rules, LLM judge, iMessage transport, classifier training, and Vietnam market docs are **upstream context** only — not wave10 borrow.

---

## Relation to Soft Hush (#50)

- **Soft Hush** (open **PR #50**; sketch path **`experiments/2026-11-04/39-hush-…`** on that PR branch) is the **quiet-channel Soft sibling**: channel-level “when not to interrupt.”
- **Boba Top** (this note, **#44**) sits **beside** Hush — same product family (group chat, asymmetric cost of speaking), **different** borrow slice (θ/debounce/feedback vs Hush’s Soft framing).
- **Do NOT** Soft→Top **flip** Hush because Boba is pinned Top here. Boba Top **does not promote** Hush; Hush stays on its own PR until Ork explicitly re-pins.

---

## Ork → Smith → Checker (when-to-speak map, light)

| Role | When-to-speak analog (Team OS / composer) |
|------|-------------------------------------------|
| **Ork** | Sets **channel policy**: default **silence** in low-signal threads; defines when agent **may** speak (mandate, @mention, impasse) vs **must not** (parallel human thread, park #10). Chooses **θ-like** team thresholds as **policy numbers**, not upstream defaults. |
| **Smith** | **Executor** obeys gate: no proactive Slack/comment unless brief allows; on **defer**, waits **debounce window** (human merge/reply first). Records **pending speak** as draft/handoff, not sent message. |
| **Checker** | Audits **barge-in** vs **missed help**: false speak = wrong PR noise, duplicate agent, speaking during human park; false silence = blocked handback without ticket. Re-runs upstream **pytest** when validating Top pin; logs pass count + upstream SHA. |

This is **observation vocabulary** only — no deployed Boba gate in playground.

---

## Team OS observation hooks (markdown)

Log one row when a composer or Slack episode resembles **speak / hold / yield**:

| Column | Definition |
|--------|------------|
| `channel_id` | Thread, channel, or ticket key |
| `gate_outcome` | `silent` \| `speak_immediate` \| `speak_deferred` \| `yielded_to_human` |
| `theta_sketch` | Optional Ork note: relative strictness (high θ_high analog) |
| `debounce_s` | If deferred: planned wait before send |
| `human_resolved_first` | Y/N — human action cancelled pending agent speak |
| `feedback_sketch` | `positive` \| `negative` \| `dismiss` — would nudge θ up/down in Boba model |
| `evidence` | Transcript timestamp, draft id, or “no send” proof |

Align **park / await** with [04](./04-impassebench-escalate-to-human-ticket-schema.md) and PR #10 path reference in [06](./06-care-escalate-verified-progress-checklist.md) — **do not** fill Cody columns here.

---

## Upstream pointers (read-only)

- Objective: asymmetric FP/FN; default **silence** — [`DESIGN.md`](https://github.com/phanngoc/boba-when-to-speak-gate/blob/main/DESIGN.md)
- Pipeline: stage 0 → 1 → 2 → debounce — [`boba_gate/gate/pipeline.py`](https://github.com/phanngoc/boba-when-to-speak-gate/blob/main/boba_gate/gate/pipeline.py)
- Production gap list (stores, durable debounce) — [`PRODUCTION.md`](https://github.com/phanngoc/boba-when-to-speak-gate/blob/main/PRODUCTION.md) — **cite only; do not port P0 store items**

---

## Status

- [x] Top design note (wave10 Boba)
- [ ] Upstream pytest re-run on playground agent VM
- [ ] Optional cross-link after Hush #50 lands (same README day folder)

**Relied on:** playground `main` tip `a3d544105a19e325dbbb2b5d7e2c5edfcb156098`; upstream Checker **51 passed** (Top citation); Hush **#50** / `39-hush` path on open PR branch (not on this branch).
