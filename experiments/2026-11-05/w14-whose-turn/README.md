# Wave14 Soft #1 — whose-turn (method-borrow KEEP)

**Lab Dig Wave14** · **Soft KEEP** · **Do not merge as Top** · **Soft→Top forbidden**

Turn-taking **session habits** from pinned upstream README — **not** a `whoseturn.py` port and **not** a claim/ownership board (see [PR #59](https://cursor.com/codebase/coevolution-lab/playground/pull/59) baton / [PR #73](https://cursor.com/codebase/coevolution-lab/playground/pull/73) Brigade).

| Doc | Purpose |
|-----|---------|
| [DESIGN-NOTE.md](./DESIGN-NOTE.md) | Full borrow/FORBID table, Team OS snapshot sketch, sibling map |
| [NOTICE](./NOTICE) | Upstream attribution |
| [`session_turn_checklist.py`](./session_turn_checklist.py) | Optional **~60 LOC** pure helpers: **P2**, **P4**, snapshot banner |
| [`test_session_turn_checklist.py`](./test_session_turn_checklist.py) | stdlib `unittest` (9 cases) |

---

## Pin (verified at pack start)

| Field | Value |
|-------|--------|
| Upstream | https://github.com/mke3idiot/whose-turn |
| **Commit** | **`291908438b3dcbda09ac1c2d749a0edefba045dc`** |
| License | **MIT** |
| **`git ls-remote` (2026-11-05)** | `291908438b3dcbda09ac1c2d749a0edefba045dc	HEAD` |

---

## Borrowed vs forbidden (summary)

**Borrowed (method-only):**

1. **P2** — never end a session while still **holding the turn**
2. **P4** — never **claim monitoring** without a visible **heartbeat**
3. **Snapshot board label** — any committed/sketched board states **`SNAPSHOT — NOT LIVE TRUTH`** + `generated_at=…`
4. *(Optional text)* P1, P3, P5, P6 as checklist lines in [DESIGN-NOTE.md](./DESIGN-NOTE.md) only

**Forbidden:**

- Soft→Top; vendored **`whoseturn.py`** product; signal JSON + **`gh`** daemons; SQLite/DSH/Feishu; headcount bots; new claim/fence system; touch **PR #78–#80**; start Wave14 Soft **#2/#3**

---

## Run tests (optional)

```bash
cd experiments/2026-11-05/w14-whose-turn
python3 -m unittest test_session_turn_checklist.py -v
```
