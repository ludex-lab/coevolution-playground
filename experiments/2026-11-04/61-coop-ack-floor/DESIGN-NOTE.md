# Coop ack-floor gate — human-first ack + negotiation floor (Top KEEP-with-caveats)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint wave13 Top **#2**  
**Verdict**: **Top KEEP-with-caveats** — upstream **ack-before-post**, **floor**, **turn-budget pause**, **one-line summary**, and **typed agent moves** sketched as a clean-room pure gate; playground does **not** ship coop HTTP API, **SQLite**, web UI, or `cmd/coop` daemon.

## Upstream pin (honest — clean-room)

| Field | Value |
|-------|--------|
| Upstream | [spalk/coop](https://github.com/spalk/coop) |
| Pin SHA | `bfba48ec9e7c69a3f2f7ef660b60a8b2c2ee60c8` (short `bfba48ec9e7c`) |
| License | **MIT** ([LICENSE](https://github.com/spalk/coop/blob/bfba48ec9e7c69a3f2f7ef660b60a8b2c2ee60c8/LICENSE) @ pin) |
| Test evidence (upstream, cited) | **`go test ./...` — 28 passing test cases** @ pin (`internal/room` + `internal/server`; **VERIFIED** in this agent run on pin) |
| Vendoring | **NONE** — upstream room service uses **SQLite** + HTTP; we **do not** import or vendor that stack |

Authoring tip commit on playground default branch: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` — this experiment branches from that tip without rewriting history.

## Real mechanism (Checker framing)

- **Human-first delivery:** before a **public** agent move, `Post` loads human events with `seq > ack` visible to the poster’s side (`unreadHuman` in upstream `internal/room/rules.go` @ pin). Any match → **`409 unread_human_message`** with the unread events attached — agents must read humans first, then repost with an updated **`ack`** (protocol §5–6 in [`docs/protocol.md`](https://github.com/spalk/coop/blob/bfba48ec9e7c69a3f2f7ef660b60a8b2c2ee60c8/docs/protocol.md) @ pin).
- **Floor:** in negotiation, exactly one side holds the floor; public agent posts without the floor get **`not_your_turn`** (`rules.go` `agentsBlocked` / floor check @ pin).
- **Turn budget pause:** when a side’s **`turns_used >= turn_budget`** after a public move, the room records a **budget** pause (`PauseBudget`, server `EventPaused`) — further public agent traffic hits **`paused`** while `pause_kind` is set (@ pin).
- **One-line summary:** agent public moves require a non-empty **`summary`**, trimmed, no newlines, at most **120** runes (`MaxSummary` @ pin `types.go`).
- **Typed moves:** agents post **`say`**, **`ask`**, **`propose`**, **`agree`**, **`reject`**, **`defer`**, **`resolution`**; **`agree` / `reject` / `defer`** require **`re`**; **`resolution`** must not carry **`re`** (`Message.validate` @ pin).

### ≠ conceptual siblings (different mechanisms — do not merge products)

| Sketch | Mechanism | Relation to this folder |
|--------|-----------|-------------------------|
| [54-nunchi-look-again](../54-nunchi-look-again/) (**Origin PR #65**) | Client-side **`look_again`**: any-participant **HOLD\|GO** before first visible send when the board revision moved | **Not** server **human-only ACK refuse**; **does not replace #65** — presend hygiene vs coop delivery gate |
| [56-dala-round-arbiter](../56-dala-round-arbiter/) (**Origin PR #67**) | **Second-price auction** round arbiter + **token budget** — **not** round-robin floor rotation | **Not** coop negotiation floor; turn-**count** pause-for-human (**`turns_used` / `turn_budget`**) ≠ DALA **token** budget |
| This folder | Server-side **human ack**, **floor**, **turn-count budget pause** on public agent posts | coop-specific; no shared gate code with #65 / #67 |

## Pure-fn sketch (playground)

Module: [`coop_ack_floor_pure.py`](./coop_ack_floor_pure.py)

```text
validate_one_line_summary(summary) -> error_code | None
unread_human_seqs(ack, human_seqs) -> tuple[int, ...]
after_public_turn(SideTurnBudget, side) -> (SideTurnBudget, pause_kind)  # sets pause_kind="budget" when exhausted
next_floor_side(floor_side, poster_side, n_sides, floor_mode, to_side) -> int  # pass | keep | to
gate_agent_public_move(...) -> GateResult  # no phase model — negotiation slice only
```

| `code` (sketch) | When |
|-----------------|------|
| **`unread_human_message`** | Any human `seq > ack` in the supplied seq list |
| **`not_your_turn`** | `floor_side != poster_side` |
| **`paused`** | Non-empty `pause_kind` (e.g. **`budget`** from **`after_public_turn`**, not caller-invented) |
| **`summary_*` / `ack_required` / `*_needs_re`** | Summary / ack / reply-shape checks aligned with upstream validate |

Tests: [`test_coop_ack_floor_pure.py`](./test_coop_ack_floor_pure.py):

```bash
cd experiments/2026-11-04/61-coop-ack-floor
python3 -m unittest test_coop_ack_floor_pure.py
```

**Playground test status:** **VERIFIED** — unittest green in this PR branch (run locally as above).

### ALLOW (this experiment)

- Document pin, MIT, protocol mechanism, ALLOW/FORBID, clean-room honesty (no SQLite/HTTP/UI/daemon).
- Pure **ack-floor gate** + one-line summary + typed-move shape checks.
- Unittest green under `experiments/2026-11-04/61-coop-ack-floor/` only.

### FORBID (hard)

- **go-sqlite3** / **SQLite**, **HTTP** server or client harness, **UI**, **daemon**, DSH, Feishu
- Vendoring upstream `internal/room` store or `ncruces/go-sqlite3`
- **Do not touch** open **PR #10** — paths under **`experiments/2026-11-03/`** (Copilot trajectories / AgentBaton park).
- **Do not touch** merged **PR #11** — [`01-agentbaton-failure-escalate-handoff.md`](../01-agentbaton-failure-escalate-handoff.md) on `main`.

## Sibling links (folder names — not PR numbers)

| Experiment | Link |
|------------|------|
| AgentBaton failure escalate (markdown) | [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) |
| PCP shared-human ask queue | [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) |
| Nunchi `look_again` (wave12 Top) | [54-nunchi-look-again](../54-nunchi-look-again/) *(parallel branch when merged)* |
| DALA round arbiter (wave12 Top) | [56-dala-round-arbiter](../56-dala-round-arbiter/) *(parallel branch when merged)* |
| Handoff Debt seven-field (wave13 Top #1) | [60-handoff-debt-notes](../60-handoff-debt-notes/) *(parallel branch when merged)* |
| **This folder** | [61-coop-ack-floor](./) |

## Checker-ready honesty (KEEP-with-caveats)

**KEEP**

- Pin SHA + MIT + real upstream symbols (`unread_human_message`, floor, budget pause, `MaxSummary=120`).
- Clean-room: no forbidden stack; mechanism slice matches `rules.go` ordering (unread → pause → floor).
- **`after_public_turn`** implements turn-count **`turns_used` / `turn_budget`** → **`pause_kind="budget"`** (playground **VERIFIED** unittest).
- Upstream **28/28** `go test` cases cited and re-run on pin in agent environment.
- Playground unittest **VERIFIED** on branch.

**Caveats / UNVERIFIED**

- No **phase** machine (briefing / approval / decided) — gate assumes negotiation-shaped inputs only.
- No private-message path, resolution→approval transition, or charter/amendment pauses — public slice only.
- **`next_floor_side`** sketches **`pass` / `keep` / `to`** hand-off only; not wired into `gate_agent_public_move` yet.
- `human_seqs` is a stand-in tuple, not a full visibility model (`visible_to` per side).
- E2E **`scripts/e2e.sh`** and demo HTTP flows **not** executed in playground.

## Status

- [x] Design note (this file)  
- [x] Pure-fn sketch + unittest  
- [ ] Complete (no coop submodule; **do not merge** this PR by agent)

**Model (completion summary)**: composer-2.5
