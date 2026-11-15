# whose-turn — session turn checklist & snapshot board sketch (Soft design note)

**Date**: 2026-11-05  
**Wave**: Lab Dig **Wave14** Soft **#1** (method-borrow KEEP; **Soft→Top forbidden**)  
**Upstream**: [mke3idiot/whose-turn](https://github.com/mke3idiot/whose-turn) — **MIT** ([LICENSE](https://github.com/mke3idiot/whose-turn/blob/291908438b3dcbda09ac1c2d749a0edefba045dc/LICENSE) © 2026 Masahiro Terawaki)

**Playground tier**: **Soft KEEP** — README + design note + **~60 LOC** stdlib helper/tests for **checklist assertions only**. **Not** a port of `whoseturn.py`, signal JSON, or `gh` board daemons.

**Model / scope guard**: Composer-2.5 authoring turn; **do not** merge this PR as Top runtime; **do not** start Wave14 Soft **#2** or **#3** from this folder.

---

## Pin table (authority for citations)

| Item | Value |
|------|--------|
| Repository | https://github.com/mke3idiot/whose-turn |
| **Pinned commit** | **`291908438b3dcbda09ac1c2d749a0edefba045dc`** (matches `HEAD` at pin time) |
| **`git ls-remote` (2026-11-05, this VM)** | `291908438b3dcbda09ac1c2d749a0edefba045dc	HEAD` |
| License | **MIT** |
| Soft tier | **Soft KEEP** (method-only) + **Soft UNVERIFIED** (no local `whoseturn.py` execution, no `gh` integration on this VM) |
| Playground base at authoring | `main` @ branch creation (clean tree) |

---

## Problem (upstream narrative — cite-only)

Multiple AI sessions on one repo hand off via PR comments. Failures are **silent**: watchers die with sessions, poll loops report success while broken, agents read **committed snapshot boards** as live truth, and PR-scoped polling misses turns on **new** PRs. Upstream README § “The problem” + principles **P1–P6** @ pin.

**Playground stance:** Borrow **session-boundary habits** and **snapshot labeling** for Ork→Smith→Checker **observation rows** — **not** a second claim/ownership product.

---

## Method borrowed (ALLOW — thin checklist + board sketch)

| ID | Upstream rule @ pin | Playground borrow |
|----|---------------------|-------------------|
| **P2** | Before ending a session, check again. **Never finish holding a turn.** | Session-exit row: `holding_turn=true` → **DENY** end (`session_turn_checklist.check_session_exit`) |
| **P4** | Never claim to be monitoring without a **heartbeat**; polling is nice-to-have, fail loudly | Monitoring row: `claims_monitoring && !has_heartbeat` → **DENY** (`check_monitoring_claim`) |
| **Snapshot board** | Generated board must **say on its face** it is a snapshot with a timestamp (failure mode #3) | `format_snapshot_board_header(iso_timestamp)` → banner **`SNAPSHOT — NOT LIVE TRUTH — generated_at=…`** |

### Optional checklist text only (not enforced in code)

| ID | One-line reminder (README @ pin) |
|----|----------------------------------|
| P1 | First action every session: check your turn |
| P3 | After handoff, verify it registered |
| P5 | Something must report stalls (N-hour visibility) |
| P6 | A human starts sessions — say so out loud |

**Not borrowed here:** `signal` JSON file ops, `whoseturn mine/show/done`, `board` via `gh`, stall detector daemons, “watch your own name” PR graph — upstream **substance** layer; see FORBID.

---

## Team OS sketch (markdown board row — not live truth)

Example **snapshot** block an agent may paste into a handoff note (generator output is **not** authoritative state):

```
SNAPSHOT — NOT LIVE TRUTH — generated_at=2026-11-05T06:58:00Z
ork     <- schema-review  said:checker  [handed-off]
smith   <- implement-api   said:ork      [active — verify with live PR thread]
```

**Checker hook:** Reject session-end or monitoring claims in observation JSON when pure helpers return DENY; reject board cites missing the snapshot banner.

---

## Sibling products (do not duplicate)

| Artifact | Role |
|----------|------|
| [48-append-only-claim-board](../../2026-11-04/48-append-only-claim-board/) — Origin **PR #59** | victorkwak **baton** append-only **claim board** (addressee, first-claim-wins) |
| [62-brigade-claim-fence](../../2026-11-04/62-brigade-claim-fence/) — Origin **PR #73** | Brigade **generation + retired-holder** fencing |
| **This folder (Wave14 Soft #1)** | **P2 / P4 / snapshot label** session habits only — **≠** new claim ledger or fleet fence |

Also unrelated: CoworkOS lease/inbox note [`01-coworkos-revision-checked-leases`](../01-coworkos-revision-checked-leases/) (Wave14 morning brief sibling).

---

## FORBID (Wave14 Soft #1)

- **Soft→Top** promotion or runtime merge from this pack
- New **claim / fencing / ownership** product (baton #59 / Brigade #73 cover those lanes)
- Vendoring or shipping **`whoseturn.py`** as playground product code
- **Daemons**, HTTP services, **`gh` poll loops**, SQLite / DSH / Feishu harness
- Extra agent **headcount** bots wired to live signal files
- Editing or depending on Origin **PR #78–#80** (out of scope for this dig)

---

## Honesty

| Source | Opened on this VM | Assumed / README-only |
|--------|-------------------|------------------------|
| Pin SHA | `git ls-remote` + raw README/LICENSE HTTP | — |
| `whoseturn.py` | **Not copied** | CLI behavior described upstream only |
| Local pytest | **`test_session_turn_checklist.py`** (9 cases) | Upstream has no vendored tests in playground |

---

## Author claim

| Signal | Value |
|--------|--------|
| License | MIT @ pin |
| Playground tests | 9 unittest cases on pure helpers (ISO `generated_at=` enforced) |
| Intended tier | **Soft KEEP** — method borrow only; **no** Soft→Top |
