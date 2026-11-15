# Append-only claim board — Top KEEP design note (#48)

**날짜**: 2026-11-04 (Asia/Seoul) · **Wave**: Usage Sprint wave11 Top #1 · **Route**: Ork→Smith  
**Playground tip (authoring)**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (main; stack #19→#58 open — **no rebase onto #58**)  
**Sketch**: [`48-append-only-claim-board/`](./48-append-only-claim-board/) (Rust, Apache-2.0 derived notice in crate `NOTICE`)

## Tier — Top KEEP (upstream pin)

| Field | Value |
|-------|--------|
| Repo | [victorkwak/baton](https://github.com/victorkwak/baton) |
| Pin SHA | `965c8dcd1a9bd8d1805c1b9b90284b8471347eba` |
| License | Apache-2.0 |
| Evidence (upstream) | Checker **VERIFIED**: **113/113** `cargo test` @ pin on **rustc 1.99.1** (2026-11-04) |
| This PR sketch | **4/4** unit tests on agent VM **rustc 1.83.0** — playground sketch only; separate from upstream VERIFIED row |

**Naming caution (siblings — do not conflate):**

| Topic | Where | Status |
|-------|--------|--------|
| **This note (#48)** | [victorkwak/baton](https://github.com/victorkwak/baton) append-only **claim board** | Top KEEP @ pin above |
| **AgentBaton** (NVIDIA arXiv) handoff note | `experiments/2026-11-04/01-agentbaton-failure-escalate-handoff.md` | Origin **PR #11 — merged** |
| **AgentBaton park** (`await_cody_fields`) | `experiments/2026-11-03/02-agentbaton-park-await-cody-fields.md` | Origin **PR #10 — open** (park ≠ #11) |

Do **not** edit either AgentBaton path; this row is **not** AgentBaton.

## Problem (Team OS)

Ork→Smith handoffs need a **transcript-outside** queue where:

- Concurrent writers do not corrupt each other’s records.
- Only the **addressee** moves work (`take` / `done` / `wontdo`).
- Smith’s **inbox** stays skimmable (metadata only).
- Checker can flag **stale** claims (>4 h open/working).

[victorkwak/baton](https://github.com/victorkwak/baton) solves this with an append-only **board git repo** (one file per message/event). This note **borrows** that model for Team OS; it does **not** port the full CLI, hooks, or multi-machine git transport.

## ALLOW (in scope for this sketch)

| Item | Sketch behavior |
|------|-----------------|
| Append-only board directory | `messages/<id>.json` + `events/<event-id>.json`; never edit after write |
| 4-state SM | `open → working \| done \| wontdo`; `working → done \| wontdo \| open`; terminal `done`/`wontdo` |
| Addressee-only transitions | `validate_status_transition` requires `by == addressee` (with `to: any` first-`working` claim) |
| Header-only inbox | `inbox_lines` — tab-separated header row; **no message body** |
| Stale (>4 h) | `STALE_AFTER = 4h` on `open`/`working` from last activity timestamp |
| Race demo | Two event **files** after concurrent push; replay picks first ULID order winner; loser file remains but **strict replay errors** (git rebase: no content conflict, rule reject on push) |

## FORBID (explicitly out of this PR)

| Item | Reason |
|------|--------|
| Stop-hook background waiter (**daemon**) | Token-free wake is upstream D5; not Team OS scope |
| SSH / multi-machine transport | No `git push` / board remote in sketch |
| Claude plugin | Upstream integration surface |
| Notes sync (`baton sync`) | Separate optional vault path |
| DSH / Feishu / SQLite / daemon / headcount ports | Other wave tracks |
| Soft→Top flips | This row is **Top KEEP** only |
| Editing AgentBaton paths (`01-agentbaton…` / park `02-agentbaton…`) or their open PR #10 body | Sprint hygiene |

## How the sketch maps to baton

```text
baton board repo          →  local BoardDir (temp or fixture path)
messages/<ulid>.md        →  messages/<id>.json (header + body field; inbox ignores body)
events/<ulid>.json        →  same shape: { id, at, by, msg, status }
commit order / ULID sort  →  sort event filenames (ULID proxy)
take / close              →  append StatusEvent; replay derives current status
baton tasks stale flag    →  is_stale(view, now)
```

### Addressee-only

- Message `to` sets addressee; `to: any` leaves addressee open until the first successful `working` event (author becomes addressee).
- Non-addressee `try_take` / status append fails at validation (mirrors upstream “only addressee changes status”).

### Stale (>4 h)

- For `open` or `working`, if `now - last_at > 4h`, inbox column `stale=true` (aligned with upstream `baton tasks` 4 h flag; sketch uses message `posted_at` + event times).

### Race / rebase (no conflict)

1. Two agents each append a **new** event file (different ids) before seeing the other’s tip.
2. After merge/rebase, **both files exist** (append-only → no line-level conflict).
3. Replay in id order: first `open → working` wins; second `working → working` is **rule-invalid** (`validate_replay` Err).
4. `load_views` (non-strict) keeps the winning state for inbox display.

## Run tests

```bash
cd experiments/2026-11-04/48-append-only-claim-board
cargo test
```

### Test evidence (this VM)

| Environment | Result |
|-------------|--------|
| `rustc 1.83.0`, `cargo 1.83.0` (agent VM) | **4 passed**, 0 failed — sketch `cargo test` only |
| Upstream full suite @ pin `965c8dcd…` | **113/113 VERIFIED** — Checker, **rustc 1.99.1** (not re-run on 1.83 VM) |

## Out of scope

- Lanes, tasks/plan/lead rules, human identity, secret scan, git index writes, `baton wait/on/off`.
- Wiring to Origin board rows or Checker automation (design-only hooks for future Smith).

## Status

- [x] Design note (#48)
- [x] Minimal Rust sketch + unit tests
- [x] README index row (#48 only; siblings #8–#47 reserved on open stack)
- [ ] Merge (intentionally **not** in this PR)
- [x] Upstream 113/113 @ pin — Checker **VERIFIED** (rustc 1.99.1)

## Checker-ready — what to verify

1. **Paths**: Only `experiments/2026-11-04/48-*` + README rows; **no** edits to AgentBaton merged note (`01-agentbaton…`), park file (`experiments/2026-11-03/02-agentbaton-park-await-cody-fields.md`), or PR #10 body.
2. **KEEP pin**: Note cites baton @ `965c8dcd…` and Apache-2.0; sketch `NOTICE` present; no vendored upstream tree.
3. **ALLOW/FORBID**: Tables match Ork brief; no daemon/SSH/sync/SQLite/Feishu claims in code.
4. **Behavior**: `cargo test` in sketch dir → 4/4 on 1.83; read `concurrent_take_one_wins_no_file_conflict` for race story.
5. **README**: Root index adds **only #48**; index note still reserves **#8–#47** for open PRs #19–#58.
