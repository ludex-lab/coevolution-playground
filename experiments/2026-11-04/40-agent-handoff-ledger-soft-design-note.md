# Agent Handoff Ledger — Soft pattern note (Team OS handoff analogy)

**날짜**: 2026-11-04  
**Upstream (Soft KEEP, pattern-only)**: [EAdamesJ/agent-handoff-ledger](https://github.com/EAdamesJ/agent-handoff-ledger) — public README as of upstream `main` (~2026-11-03; **Checker: no automated tests** in tree).

**Tier**: **Soft KEEP** — read upstream for coordination *ideas* only. **Soft→Top forbidden** — do not pin, vendor, or treat as production Team OS runtime.

**Code (playground)**: **GH Soft UNVERIFIED** — this VM did **not** install `uvx`, register MCP clients, or run the ledger. Any claim about SQLite lease behavior, default caps, or tool JSON is **README-sourced**, not Checker-verified here.

**Playground tip at authoring**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (wave9 sibling base; unchanged at branch cut).

---

## Upstream blurb (README pointer; no runs today)

From the public [agent-handoff-ledger README](https://github.com/EAdamesJ/agent-handoff-ledger/blob/main/README.md):

- **Problem framing:** connecting agents is easy; **shared task state**, **who writes next**, and **bounded back-and-forth** are harder.
- **Shared record (conceptual):** goal/constraints, current owner, handoff summary + next action, files touched so far, append-only event history, **finite handoff budget** (default four; configurable 0–16 at create).
- **One writer:** transaction-backed **workspace lease** — one participating agent holds writer role; default lease **90 minutes**, renewable; stale lease returns task to queue with inspect-workspace warning (cooperative, not a filesystem lock).
- **MCP host clients (upstream docs only):** Claude Code (`.mcp.json`), Codex (`config.toml`), DeepSeek Harness (external MCP client plugin). Server stores state locally; **does not call model APIs** or launch agents.
- **Tool flow (names only):** `create_handoff` → `claim_handoff` → work → `pass_handoff` | `complete_handoff`; `show_handoff` / `list_handoffs`; `renew_handoff` for long tasks.
- **v0.1 scope:** shared ledger + one-writer + resumable handoffs + loop budget — **not** agent sandboxing or provider invocation.

**Evidence note:** State path `.agent-handoff/ledger.sqlite3` and MCP stdio wiring are upstream implementation details — **not** ported or sketched for Team OS in this note.

---

## Pattern → Team OS (Ork → Smith → Checker)

Use as **Soft analogy** when multiple agent lanes or humans share one repo/task — **not** as a mandate to adopt MCP/SQLite.

| Upstream pattern | Ork → Smith → Checker reading |
|------------------|----------------------------------|
| Persistent brief (objective, constraints, next action) | **Handoff artifact** beyond chat: pointer + summary aligned with [01](./01-agentbaton-failure-escalate-handoff.md) (`workspace_pointer`, `log_path`) — ledger *shape* without transcript dump |
| `claim_handoff` / single writer lease | **One writer at a time** on contested tree — same spirit as ParallACT sequential handoff ([05](./05-parallact-shared-repo-handoff-checklist.md)); Ork assigns turn order; Smith holds lease until pass/complete |
| `pass_handoff` (queue next agent) | **Ork → Smith** (or Smith A → Smith B) with explicit `target_agent` / role slot — resumable queue, not parallel unaware edits |
| Append-only event history | Ludex / run logs: **audit trail** of claims, passes, renewals — Checker reads outcomes, not MCP JSON |
| Handoff budget exhausted | **Bounded loop** — escalate or **ask human** ([04](./04-impassebench-escalate-to-human-ticket-schema.md), [07](./07-pcp-shared-human-ask-queue-checklist.md)) instead of unbounded agent ping-pong |
| Cooperative lease | Matches README honesty: unconfigured process or human can still edit — **policy + observation**, not crypto enforcement |
| `complete_handoff` | Smith signals **done**; Checker owns verify gate — upstream does not replace CI |

**Cross-links:** Repeat failure signatures → [01](./01-agentbaton-failure-escalate-handoff.md) `failure-id`; verified-progress / dual thresholds → [06](./06-care-escalate-verified-progress-checklist.md) when relevant; dual-writer stress → [05](./05-parallact-shared-repo-handoff-checklist.md).

---

## Observation focus (pattern-only checklist)

Log **conceptual** rows when a session *resembles* ledger semantics — no MCP install required.

| Column | Type | Definition |
|--------|------|------------|
| `run_id` | string | Cloud Agent / Team OS run id |
| `handoff_slot` | string | e.g. `ork→smith`, `smith→checker`, `smith_a→smith_b` |
| `brief_shape` | enum | `pointer_only` \| `summary+next_action` \| `full_transcript_dump` \| `missing` |
| `writer_mode` | enum | `one_writer_lease` \| `parallel_unaware` \| `human_override` |
| `loop_bound` | enum | `within_budget` \| `budget_exhausted` \| `unbounded_observed` |
| `checker_outcome` | enum | `pass` \| `fail` \| `parked` \| `unknown` |
| `notes` | string | SHAs, paths, ticket ids — **pointers only** |

### Example row (**example** — fictional)

| label | run_id | handoff_slot | brief_shape | writer_mode | loop_bound | checker_outcome | notes |
|-------|--------|--------------|-------------|-------------|------------|-----------------|-------|
| **example** | `TEAMOS-ahl-7f02` | `ork→smith→checker` | `summary+next_action` | `one_writer_lease` | `within_budget` | `pass` | Ork left objective + log path; Smith pushed once; Checker green — **analogy** to ledger brief, not MCP proof |

---

## Out of scope (2026-11-04 wave9)

- **Top pin**, production rollout, or “Team OS ships agent-handoff-ledger” claims  
- Vendoring upstream, `uvx` recipes, or MCP registration in playground  
- **SQLite / DSH / Feishu** port sketches, daemon wiring, or headcount automation  
- PR **#10** Copilot trajectory files; **`experiments/2026-11-03/`** paths  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md)  
- Asserting lease timing, SQLite serialization, or handoff-cap defaults were **measured** in this repo (README only unless future Checker run says otherwise)

---

## Status

- [x] Soft pattern note (markdown only)  
- [ ] In Progress (no MCP / no upstream clone in playground)  
- [ ] Complete (Top / runtime) — **explicitly not a goal**

**Next step:** During multi-agent handoffs on one repo, note whether behavior matches **shared brief + one writer + bounded loops**; aggregate offline. Merge of this doc is not required for ops.
