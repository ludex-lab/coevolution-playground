# Shut-Up — budget_max + cooldown (Soft design note)

**Date**: 2026-11-04  
**Wave**: Usage Sprint **wave11 Soft #3** (Ork→Smith)  
**Upstream (idea pointer only)**: **Shut-Up** @ short SHA **`acbca7b`** — **NO LICENSE** in public checkout at authoring time → **Soft UNVERIFIED** (full tip not resolved on this VM; do **not** fetch or paste upstream source here).

**Playground base for this sprint folder**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (main at branch time; report if `main` moved).

**Code in playground**: **Self-authored slice only** — `53-shut-up-budget-cooldown/` (`gate.py` + fixtures + unittest). **FORBID** copying Shut-Up upstream files.

---

## Checker verdict (Soft **KEEP**)

| Signal | Value |
|--------|--------|
| License | **None / unknown** (NO LICENSE → **reimplement from idea only**) |
| Upstream tests | **Soft UNVERIFIED** — upstream repo not executed or vendored here |
| Playground tests | **Run locally** — see [How to run tests](#how-to-run-tests--vm-evidence) |
| Promotion | **Soft KEEP** — narrow **budget_max + cooldown** borrow only; **Soft→Top forbidden** on this note |

**Soft framing:** Shut-Up (upstream name only) suggests **hard caps on outbound agent noise**: a **`budget_max`** on sends in a scope and a **`cooldown`** minimum gap between sends. Team OS may borrow that **pair of gates** beside quiet-channel siblings—not a claim that playground runs Shut-Up or that upstream behavior matches this sketch byte-for-byte.

---

## ALLOW / FORBID (this PR)

| | Scope |
|---|--------|
| **ALLOW** | Markdown Soft design note; **budget_max + cooldown** gate sketch under `53-shut-up-budget-cooldown/`; fixtures proving both deny paths |
| **FORBID** | Copying Shut-Up upstream source (NO LICENSE) |
| **FORBID** | **Soft→Top** of this note, or promoting Boba/Hush siblings via this PR |
| **FORBID** | DSH / Feishu / SQLite / daemon / headcount ports |
| **FORBID** | Editing **PR #10** / **PR #11** or any file under **`experiments/2026-11-03/`** |

---

## Slice scope (HARD — wave11 Soft #3)

**In scope (playground-original code + observation vocabulary):**

1. **`budget_max`** — after `N` committed outbound sends in the gate’s scope, further sends **deny** with reason `budget_max`.
2. **`cooldown_s`** — after a committed send, sends at `now < last_send_at + cooldown_s` **deny** with reason `cooldown` (preview exposes `cooldown_remaining_s`).

**Explicitly NOT borrowed (non-goals):**

- Any Shut-Up upstream module, config, or test port.
- Boba **θ / debounce / feedback** ([experiment #44](./44-boba-when-to-speak-gate-design-note.md) on open **Origin PR #55** — **Top** sibling; stay separate).
- Hush **SILENT / SPEAK / ASK** + addressing tiers ([experiment #39](./39-hush-soft-design-note.md) on open **Origin PR #50** — **Soft** sibling; stay separate).
- Transport (Slack/Origin bots), durable stores, or production wiring.

---

## Sibling honesty (do not Soft→Top / do not duplicate)

| Sibling | Origin PR | Experiment # | Their slice | This note |
|---------|-----------|--------------|-------------|-----------|
| **Hush** | [#50](https://cursor.com/codebase/coevolution-lab/playground/pull/50) | **#39** | SILENT/SPEAK/ASK restraint | **Does not** replace or promote Hush |
| **Boba** | [#55](https://cursor.com/codebase/coevolution-lab/playground/pull/55) | **#44** | θ/debounce/feedback (Top) | **Does not** replace or promote Boba |

Cross-links are **coordination boundaries**, not sources to merge or flip tier.

---

## Intent (Team OS — Soft analogy only)

Map **rate-limited outbound chatter** lightly to Ork→Smith→Checker **as policy**, not deployed roles:

| Gate | Soft Team OS analog |
|------|---------------------|
| **`budget_max`** | Ork caps how many **channel-visible** Smith posts (PR comments, Slack sends) per run or thread before mandatory handback/park. |
| **`cooldown`** | Even when budget remains, Smith **waits** minimum wall time between visible posts so humans can interleave (complements Boba debounce conceptually—**different mechanism**, no merge). |
| Deny `budget_max` | Checker sees **budget exhausted** → require ticket/handoff ([04](./04-impassebench-escalate-to-human-ticket-schema.md)) instead of more noise. |
| Deny `cooldown` | Treat as **hold**, not failure; retry after window (draft-only work may continue off-channel). |

**Cross-links (orthogonal):** withdrawable ask queue ([07](./07-pcp-shared-human-ask-queue-checklist.md)); repeat `failure-id` escalate ([01](./01-agentbaton-failure-escalate-handoff.md)).

---

## Sketch API (playground-original)

Module: [`53-shut-up-budget-cooldown/gate.py`](./53-shut-up-budget-cooldown/gate.py)

- `OutboundBudgetCooldownGate(budget_max, cooldown_s)`
- `preview(now)` → allow/deny without mutating state
- `request_send(now)` → allow/deny and commit on allow

Deny reasons: `budget_max` | `cooldown`.

---

## How to run tests + honest VM evidence

From repo root:

```bash
cd experiments/2026-11-04/53-shut-up-budget-cooldown
python3 -m unittest -v test_gate.py
```

**VM evidence (this Cloud Agent run, composer-2.5):**

```text
Python 3.x — cd experiments/2026-11-04/53-shut-up-budget-cooldown && python3 -m unittest -v test_gate.py
Ran 4 tests in 0.000s — OK
```

Upstream Shut-Up remains **Soft UNVERIFIED** even when playground tests pass.

---

## Observation columns (optional log row)

| Column | Meaning |
|--------|---------|
| `gate_outcome` | `allow` \| `deny` |
| `deny_reason` | `budget_max` \| `cooldown` \| null |
| `remaining_budget` | int after decision |
| `cooldown_remaining_s` | float when denied for cooldown |
| `run_id` / `log_path` | pointer only — no transcript dump |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount  
- Vendoring Shut-Up or merging Boba/Hush design notes  
- Soft→Top promotion; agent merge of this PR  
- **PR #10** / **PR #11** / **`experiments/2026-11-03/`**

---

## Status

- [x] Planning (Soft design note + original sketch)  
- [x] In Progress (playground unittest slice)  
- [ ] Complete (await human review / optional upstream SHA resolution)

**Checker-ready:** Soft **KEEP**; NO LICENSE **reimplement-only** warning; sibling table; local test command; VM evidence slot filled on authoring agent run.

**Next step:** If Shut-Up publishes a license + public tip, Ork may re-pin **without** copying source until license allows; until then keep this sketch as the only executable reference in playground.
