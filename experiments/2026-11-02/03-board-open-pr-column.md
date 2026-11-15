# Team OS board — open-PR column (sketch)

**날짜**: 2026-11-02 · **유형**: board-visible state 제안 (markdown only; UI·Slack·daemon·Evening Close prompt 변경 없음)

## Context (why this column)

2026-11-02: playground PRs #2–#7 stayed **open for days** while CloudAgent merge token was blocked. Evening Close / Watchdog could report “no merges today” without surfacing **stuck open PRs**. As of main tip `8ac2ce3` those PRs are merged (open count 0); the gap was **visibility**, not merge policy alone.

## Column purpose

Surface **open Origin/playground PRs** that need attention on the Team OS board/OPS view—merge hygiene, CI, token blockers, owner—so close routines cannot treat “quiet forge” as “healthy day” when PRs are aging open.

## Fields shown (one row per open PR)

| Field | Meaning |
|-------|---------|
| **PR #** | Origin PR number (board pointer may alias this; see [02](./02-sbus-version-check-board-rule.md) `kind: origin_pr`) |
| **Title** | Short title |
| **Age** | Days open (calendar or business; pick one and stick to it on the board) |
| **CI / mergeable** | Pass/fail/pending + mergeable yes/no/unknown |
| **Blocker** | One short string (e.g. `merge_token`, `ci_red`, `needs_review`, `conflict`) |
| **Owner** | Smith / human / agent assignment on the ticket |

Optional tie-in (not required for v0 sketch): when a row’s PR head changes, bump the scoped **`version`** on that pointer—same spirit as version-check in note #2, without implementing stale-write reject here.

## How Evening Close / Watchdog reads it

1. **Scan column cardinality:** `open_count` = number of rows (0 vs ≥1).
2. **`open_count = 0`:** One-line close line — **“no open PRs”** (still compatible with “no merges today”; both can be true).
3. **`open_count ≥ 1`:** Call out **oldest age** and any row with **non-empty blocker** or **CI/mergeable not green**; name PR # + owner. Do not infer merge from chat—use this column + forge.

## Behavior (open 0 vs open ≥1)

| State | Evening Close | Watchdog |
|-------|---------------|----------|
| **Open = 0** | Report hygiene OK for open queue; no escalate unless OPS elsewhere flags forge drift | Periodic tick: log `open_pr_count: 0` |
| **Open ≥ 1** | List stuck/blocked rows in close summary; if age ≥ team threshold or blocker ∈ `{merge_token, ci_red}`, **flag merge hygiene** for Ork/human | Escalate or re-flag on each tick until row clears or blocker updated on board |

**Non-goals (hard):** No DSH/Feishu/SQLite/daemon/headcount ports; no live board UI in this PR; no Slack bot or routine prompt edits.

## Relation to same-day notes

- [01](./01-who-takes-the-lead-handoff-checklist.md): **who** takes the next turn after a stuck PR is visible.
- [02](./02-sbus-version-check-board-rule.md): **which board/PR version** handbacks may rely on once someone acts—not a substitute for listing *that* PRs are still open.

---

**Status:** sketch only; column is **board-visible state** to maintain by hand or future forge sync—not implemented in playground repo.
