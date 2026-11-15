# Wave14 Soft #2 — Sundial (method-borrow + doctrine-ban)

**Lab Dig Wave14** · **Soft** (method-only) · **Do NOT merge as Top** · **Soft→Top forbidden**

Escalation **method ideas** from pinned upstream Sundial — **not** a port of presence sensors, watcher daemon, promise ledger, or stand-in wakes.

| Doc | Purpose |
|-----|---------|
| [DESIGN-NOTE.md](./DESIGN-NOTE.md) | Borrow/FORBID, **doctrine-ban** vs Sundial terminal autonomy, Team OS `on_expiry` pointer |
| [NOTICE](./NOTICE) | Upstream MIT attribution |
| [`unseen_time_sketch.py`](./unseen_time_sketch.py) | Optional **~70 LOC** pure helpers: unseen-time rates + wall ceiling (no OS sensors) |
| [`test_unseen_time_sketch.py`](./test_unseen_time_sketch.py) | stdlib `unittest` (4 cases) |

---

## Pin (verified at pack start)

| Field | Value |
|-------|--------|
| Upstream | https://github.com/bigjoe-oti/sundial |
| **Commit** | **`74ede107762c61a34edcb49f3c8a48e1949685b6`** |
| License | **MIT** © 2026 J. Servo LLC |
| **`git ls-remote` (2026-11-05, this VM)** | `74ede107762c61a34edcb49f3c8a48e1949685b6	HEAD` · `74ede107762c61a34edcb49f3c8a48e1949685b6	refs/heads/main` |

Verification:

```bash
git ls-remote https://github.com/bigjoe-oti/sundial 74ede107762c61a34edcb49f3c8a48e1949685b6
git ls-remote https://github.com/bigjoe-oti/sundial HEAD
```

---

## Borrowed vs forbidden (summary)

**Borrowed (method-only):**

1. **Unseen-time escalation clock** — full rate while away, half while busy elsewhere, **paused** while present (HERE); **method idea only** — no `ioreg` / `xprintidle` / `loginctl` deps.
2. **Wall ceiling** — sensors may **soften** cadence but **never disable** the terminal contract (README + essay @ pin).
3. **≤3 pings** per question per driver (honesty rail @ pin).
4. **“The watcher must not think”** — deterministic wake path; **no LLM** in escalation timing.

**Doctrine-ban (Team OS — not borrowed):**

Sundial’s **informed non-objection / proceed-on-silence / stand-in auto-proceed** terminal paths are **explicitly rejected** in [DESIGN-NOTE.md § Doctrine-ban](./DESIGN-NOTE.md#doctrine-ban-team-os--silence-expiry-top-1). Terminal human silence maps only to Top #1 `on_expiry` ∈ {`DENY`, `SAFE_FALLBACK`, `ESCALATE`, `HOLD`} — see [`experiments/2026-11-05/w14-silence-expiry/`](../w14-silence-expiry/) on Origin [PR #78](https://cursor.com/codebase/coevolution-lab/playground/pull/78). **Never** journal timeout as allowed.

**Forbidden:**

Soft→Top; desktop presence sensors as **required** deps; Sundial daemon/ledger **product**; ALLOW-on-timeout; proceed-on-silence **code**; SQLite/DSH/Feishu; headcount bots; touch **PR #78–#81**; start Wave14 Soft **#3**.

---

## Run tests (optional)

```bash
cd experiments/2026-11-05/w14-sundial
python3 -m unittest test_unseen_time_sketch.py -v
```

---

## Author claim

| Signal | Value |
|--------|--------|
| License | MIT @ pin |
| Playground tests | 4 unittest cases on pure helpers |
| Intended tier | **Soft** — method borrow + doctrine-ban note; **Checker fills verdict** |

**Checker verdict:** *(intentionally empty — Checker assigns KEEP/DROP.)*
