# fael — memory pointers scoped to the opened file (Soft design note)

**날짜**: 2026-11-04  
**Upstream (Soft KEEP, pattern-only)**: [zecalis/fael](https://github.com/zecalis/fael) — MIT; public README + tree at pin **`7e9044220fcca5c371cb743fd9df4fabae99e20d`** (`release v0.106.0`, 2026-11-03).

**Tier**: **Soft KEEP** — borrow the **file-scoped memory pointer** idea for Team OS handoffs and observation logs only. **Soft→Top forbidden** — do not vendor the binary, hooks, MCP server, `.git/fael/` JSONL, or treat fael as production Team OS runtime.

**Code (playground)**: **NONE** — markdown design note only. This session did **not** install `@zecalis/fael`, run hooks, or execute upstream CI. README claims (per-file attach on edit, token budget, `fael stats` hit rates, hook latency) are **README-sourced** — **Soft UNVERIFIED** here unless a future Checker run pins and tiers otherwise.

**Playground tip at authoring**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (wave11 Soft #1 base; unchanged at branch cut).

---

## Upstream blurb (README pointer; no code copy; no runs today)

From the public [fael README](https://github.com/zecalis/fael/blob/7e904422/README.md) at the pin above (paraphrase):

- **Continuity ledger** between agent sessions that do not share chat — decisions, open issues, hand-offs, and assignments live as **rows** keyed to **files** and optional **keys**, stored under the clone (`.git/fael/`), not on code branches.
- **File-scoped recall (the pointer semantics):** When an agent **edits** a file, fael attaches **only rows written about that file** — the opened/touched file is the query. **Reading or searching alone does not inject rows**; memory waits until the relevant file is in play. Sub-agents with a thin brief still get file-local context at edit time.
- **No global notes dump:** Rows push **per file**, **once per context window** (again after compaction or a fresh sub-agent context), trimmed to a **token budget** (default 800). Anything broader is opt-in via MCP/`find`.
- **Same-turn filing:** Agents can record decisions/issues/notes **in the same message as the next tool call** (or trailing `fael decision|issue|note:` lines) so memory does not cost an extra orchestration turn.
- **Hand-offs & assignments:** Session-start lists what was routed to this git `user.name` or agent id; `--files` / `--key` tie rows to paths so the **next opener** of that path sees the pointer payload.
- **Retire & follow code:** Rows close when code absorbs the fact; renames follow `git log -M`; stale rows surface via `fael doctor` — git owns diffs, fael owns what git cannot say.

**Evidence note:** Hook wiring, JSONL schema, SQLite-backed internals (upstream crate graph mentions storage helpers), and `fael crew` plan/chunk flows live in upstream source and docs — **not** ported, vendored, or audited in playground this turn.

---

## ALLOW / FORBID (wave11 Soft #1)

| | |
|---|---|
| **ALLOW** | Soft **method-borrow**: treat **repo-relative path (+ optional stable key)** as the scope for durable memory **pointers** shown to Smith only when that file is the active edit target; cite upstream pin + **Soft KEEP** tier; light **Ork → Smith → Checker** analogy; pointer-only **`handoff_artifact`** cross-links ([01](./01-agentbaton-failure-escalate-handoff.md)). |
| **FORBID** | **Soft→Top** promotion; **rusqlite** or any fael / playground **crate vendoring**; DSH / Feishu / **SQLite daemon** / headcount automation sketches; runtime wiring (hooks, MCP, `.git/fael/` writes); editing **Origin PR #10** / **#11** bodies or **`experiments/2026-11-03/`** paths; claiming fael **hit rates** or hook timings were measured in this repo. |

---

## Pattern → Team OS (Ork → Smith → Checker)

Use as **Soft analogy** when Cloud Agent or Smith lanes revisit the same paths across runs — **not** as a mandate to install fael in Ludex or forge bots.

| fael idea | Ork | Smith | Checker |
|-----------|-----|-------|---------|
| **File-scoped pointer** | Brief lists **paths in scope**; durable notes keyed by **`path` + optional `memory_key`** — not session-global prose | When touching `path`, receives **only pointers** for that path (prior decision, open issue, hand-off) — aligns with **`handoff_artifact`** = workspace + log, not transcript | Verifies claims against **forge head + path**; rejects “I remembered” without **`relied_on`** refs |
| **Attach on edit, not on read** | Ork does not preload all sprint notes into Smith context | Smith **edit/write tools** on `path` trigger injection of scoped rows; read-only grep does not substitute for edit-time memory | Checker treats read-only passes as **lower evidence** (fael `stats` “miss” analogy) |
| **Once per context window** | Re-brief after compaction / new sub-agent run id | Same path pointers may be re-stated after context reset — idempotent keys avoid duplicate rows | Dedupes repeated KEEP claims against same SHA |
| **Assignment vs file memory** | **`--to`-style routing** ≈ ticket assignee at session start ([04](./04-impassebench-escalate-to-human-ticket-schema.md) park distinct from file notes) | Executes assigned work; files local findings on touched paths | Separates **assigned queue** from **path-local ledger** |
| **Claim / held marker** | Parallel Smith lanes: Ork marks **held** scope to reduce duplicate edits ([05](./05-parallact-shared-repo-handoff-checklist.md) contested artifact) | Picks another path when `(held @)` analog present | **`joint_pass`** needs explicit writer lease, not silent double-edit |
| **Retire when code speaks** | Closes Ork rows when merge lands | `fael close`-analog: drop stale decision when diff contradicts | **`certified_complete`** when git + log pointers agree — not narrative |

**Cross-links (markdown only):**

- [01-agentbaton-failure-escalate-handoff.md](./01-agentbaton-failure-escalate-handoff.md) — **`handoff_artifact`** pointers only.
- [05-parallact-shared-repo-handoff-checklist.md](./05-parallact-shared-repo-handoff-checklist.md) — parallel writers + file contention.
- [06-care-escalate-verified-progress-checklist.md](./06-care-escalate-verified-progress-checklist.md) — verified-progress memory vs local green.

---

## Observation columns (optional log row)

Log **one row per file-scoped memory episode** (markdown-only today):

| Column | Type | Definition |
|--------|------|------------|
| `run_id` | string | Cloud Agent / Team OS run id |
| `opened_file` | string | Repo-relative path when memory pointers applied |
| `pointer_kind` | enum | `decision` \| `issue` \| `handoff` \| `assignment` \| `keyed_note` |
| `attach_trigger` | enum | `on_edit` \| `session_kickoff` \| `mcp_find` \| `none_observed` |
| `scope_ok` | bool | True when injected rows matched **`opened_file`** only (no cross-file bleed) |
| `context_generation` | string | e.g. `post_compaction` \| `sub_agent` \| `primary` — fael “once per window” analog |
| `budget_sketch` | string | Token/line cap applied — pointer to policy id, not dump |
| `checker_outcome` | enum | `pass` \| `fail` \| `parked` \| `unknown` |
| `notes` | string | SHAs, row ids, `log_path` — **pointers only** |

### Example row (**example** — fictional)

| label | run_id | opened_file | pointer_kind | attach_trigger | scope_ok | context_generation | checker_outcome | notes |
|-------|--------|-------------|--------------|----------------|----------|--------------------|-----------------|-------|
| **example** | `TEAMOS-fael-51a1` | `experiments/2026-11-04/51-fael-memory-pointers-soft-design-note.md` | `handoff` | `on_edit` | true | `primary` | `unknown` | Prior run left pricing-layout note on same path; Smith saw pointer at edit — **fael analogy**, not measured `fael stats` |

---

## Soft UNVERIFIED (upstream README / release pin only)

| Claim (upstream docs @ pin) | Status here |
|-----------------------------|-------------|
| Rows attach on **file edit**, not passive read | **Soft UNVERIFIED** (README) |
| Per-file push once per context window + ~800 token budget | **Soft UNVERIFIED** |
| Hook ~10 ms / session start ~100 ms @ 1k rows | **Soft UNVERIFIED** |
| `fael stats` hit/M and `across agents` definitions | **Soft UNVERIFIED** — see upstream [docs/stats.md](https://github.com/zecalis/fael/blob/7e904422/docs/stats.md) |
| Storage stack includes SQLite-family deps in crate graph | **Acknowledged upstream** — **FORBID** porting into playground |

---

## Out of scope (2026-11-04 wave11 Soft #1)

- **Top pin**, production rollout, or “Team OS ships fael hooks” claims  
- Vendoring fael, `npm i -g`, `brew install`, rusqlite, or writing `.git/fael/` from playground CI  
- **DSH / Feishu / SQLite daemon / headcount** ports or MCP wiring beyond this note  
- **Origin PR #10** / **#11** and **`experiments/2026-11-03/`** paths  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or open sibling sketches **#8–#50** (reserved on Origin PRs [#19](https://cursor.com/codebase/coevolution-lab/playground/pull/19)–[#61](https://cursor.com/codebase/coevolution-lab/playground/pull/61))  
- Asserting **`fael stats`** or hook latency was **measured** in this repo  

---

## Status

- [x] Soft KEEP design note (markdown only)  
- [ ] In Progress (no upstream install / no hook run in playground)  
- [ ] Complete (Top / runtime) — **explicitly not a goal**

**Next step:** When Smith reopens hot paths across parallel runs, log whether scoped pointers prevented duplicate work — aggregate offline; merge of this doc is not required for ops.

---

## Checker-ready blurb

> Experiment **#51** adds a **Soft KEEP** design note only: [51-fael-memory-pointers-soft-design-note.md](./51-fael-memory-pointers-soft-design-note.md) borrows **fael**’s **file-scoped memory pointers** (attach on edit/touch, not global preload) as an Ork→Smith→Checker observation pattern. Upstream pin **`7e9044220fcca5c371cb743fd9df4fabae99e20d`** ([zecalis/fael](https://github.com/zecalis/fael), MIT, `v0.106.0` tag context) is cited; **Soft→Top forbidden**; **no** fael binary, hooks, MCP, rusqlite, or `.git/fael/` vendoring in playground. README adds row **#51** only; rows **#8–#50** reserved for open Origin PRs **#19–#61**. **Do not merge** this PR for runtime — markdown borrow only.
