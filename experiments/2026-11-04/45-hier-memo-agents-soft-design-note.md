# hier-memo-agents (`hma`) — Soft pattern note (blackboard + provenance analogy)

**날짜**: 2026-11-04  
**Upstream (Soft KEEP, pattern-only)**: [Lesereingrape/hier-memo-agents](https://github.com/Lesereingrape/hier-memo-agents) — Apache-2.0; public README + `main` tree as of upstream tip `7df04edab756fdbad56fd867391f37d000226c25` (2026-09-26).

**Tier**: **Soft KEEP** — read upstream for hierarchical planner–executor + **shared blackboard** + **citation provenance** *ideas* only. **Soft→Top forbidden** — do not pin, vendor, or treat as production Team OS runtime.

**Code (playground)**: **GH Soft UNVERIFIED** — this VM did **not** `pip install -e .`, run `hma run`, or execute the upstream test suite. README claims (26 tests, sub-second suite, `skipped_by_memory`, `verify()` exit codes, sample stdout blocks) are **README-sourced**, not Checker-verified here.

**Playground tip at authoring**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (wave10 sibling base; unchanged at branch cut).

---

## Upstream blurb (README pointer; no runs today)

From the public [hier-memo-agents README](https://github.com/Lesereingrape/hier-memo-agents/blob/main/README.md):

```
question ──► Planner ──► DAG waves ──► Executors ──► Synthesizer ──► verify()
                            │              │                            │
                       cycle-safe     Blackboard                  evidence chain:
                       topological    dedup · conflicts           claim → quote → doc
                                      topic reuse (skip calls)    any edit breaks it
```

- **Scheduling:** subtasks form a **DAG**; cycles and unknown deps rejected before execution; independent nodes run in reproducible **waves**.
- **Blackboard over pairwise chat:** agents publish **findings** (key, answer, evidence ids, topic tags) — no N² message threads; Jaccard dedup; same-topic-different-answer → **`Conflict`** for review instead of silent overwrite.
- **Topic reuse:** executors query memory **before** model calls; **`skipped_by_memory`** counts call savings when a topic was already researched.
- **Provenance:** quotes checked **verbatim** against corpus before becoming citable evidence; final **`verify()`** fails on unknown evidence ids, broken spans, orphan claims, or post-edit drift — run exits nonzero when broken.
- **Seam:** single `complete_json` contract (`plan`, `research`, `synthesize`); `CorpusLLM` is deterministic offline stand-in for CI-friendly guarantees.

**Evidence note:** Orchestrator, `cite()`, conflict logging, and CLI sample blocks live in upstream source — **not** ported or sketched for Team OS in this note.

---

## Pattern → Team OS (Ork → Smith → Checker)

Use as **Soft analogy** when Ork decomposes work, Smith lanes execute in parallel, and Checker needs **pointer-backed** claims — **not** as a mandate to adopt `hma` or blackboard storage.

| Upstream pattern | Ork → Smith → Checker reading |
|------------------|----------------------------------|
| Planner **DAG waves** | Ork brief lists **ordered waves** (independent Smith tasks first); blocks launch when deps or scope cycle — aligns with structured handoff ([01](./01-agentbaton-failure-escalate-handoff.md)) |
| **Blackboard findings** | Shared **Ludex / ticket `evidence`** surface — findings as rows, not chat ([04](./04-impassebench-escalate-to-human-ticket-schema.md)); pointer + log path, not transcript dump |
| **Topic reuse / `skipped_by_memory`** | Before a second Smith run repeats research, Ork/ledger asks: **already in blackboard?** — token-budget analogy to AgentBaton escalate-only-when-needed ([01](./01-agentbaton-failure-escalate-handoff.md)) |
| **`Conflict` vs dedup** | Same path, **different answer** → log for human/Checker review — not silent last-writer-wins ([05](./05-parallact-shared-repo-handoff-checklist.md) joint-fail subtext) |
| **`verify()` / evidence ids** | Checker **KEEP** only when every claim resolves to **independent refs** (SHA, log span, forge URL) — Smith narrative is not proof ([01](../2026-11-01/01-mandate-agent-run-checklist.md) Missing evidence sketch) |
| **Fabricated quote rejection** | Smith must not cite lines that do not exist in cited artifact — Checker replays refs, not paraphrase |
| **Session persistence** | Multi-question sprint on one board — same repo day’s blackboard carries forward; Ork sets **session id** in observation rows |

**Cross-links:** Bounded loops / ask-human → [07](./07-pcp-shared-human-ask-queue-checklist.md); verified progress without terminal certificate → [06](./06-care-escalate-verified-progress-checklist.md); dual-writer stress → [05](./05-parallact-shared-repo-handoff-checklist.md).

---

## Observation focus (pattern-only checklist)

Log **conceptual** rows when a Team OS episode resembles **DAG + blackboard + provenance gate** — no `hma` install required.

| Column | Type | Definition |
|--------|------|------------|
| `run_id` | string | Cloud Agent / Team OS run id |
| `wave_sketch` | string | e.g. `ork_plan → smith_parallel → checker_verify` |
| `blackboard_shape` | enum | `ticket_evidence` \| `shared_file` \| `forge_only` \| `chat_only` \| `missing` |
| `reuse_sketch` | enum | `skipped_redundant_work` \| `repeated_same_topic` \| `unknown` |
| `conflict_sketch` | enum | `logged_conflict` \| `silent_overwrite` \| `none_observed` |
| `provenance_gate` | enum | `checker_verified_refs` \| `verify_would_fail` \| `narrative_only` \| `not_run` |
| `checker_outcome` | enum | `pass` \| `fail` \| `parked` \| `unknown` |
| `notes` | string | SHAs, evidence ids, log paths — **pointers only** |

### Example row (**example** — fictional)

| label | run_id | wave_sketch | blackboard_shape | reuse_sketch | conflict_sketch | provenance_gate | checker_outcome | notes |
|-------|--------|-------------|------------------|--------------|-----------------|-----------------|-----------------|-------|
| **example** | `TEAMOS-hma-3c81` | `ork→2×smith→checker` | `ticket_evidence` | `skipped_redundant_work` | `none_observed` | `checker_verified_refs` | `pass` | Second Smith lane reused Ork’s cited PR head; Checker matched log span — **analogy** to blackboard + `verify()`, not `hma` proof |

---

## Soft UNVERIFIED (upstream test / CLI claims)

Unless a future VM run pins and tiers otherwise, treat as **README citations only**:

| Claim (upstream docs) | Status here |
|-----------------------|-------------|
| 26 stdlib tests, offline, sub-second | **Soft UNVERIFIED** |
| DAG cycle / dep / duplicate rejection covered by tests | **Soft UNVERIFIED** |
| Orchestrator rejects scripted hallucinated quote | **Soft UNVERIFIED** |
| README sample blocks regenerated by `experiments/make_readme.py` + byte compare test | **Soft UNVERIFIED** |
| Session example: third question **`skipped_by_memory=1`**, `hit_rate=1.0` | **Soft UNVERIFIED** |

---

## Out of scope (2026-11-04 wave10)

- **Top pin**, production rollout, or “Team OS ships hma” claims  
- Vendoring upstream, `pip install`, or running `hma` in playground CI  
- **DSH / Feishu / SQLite** port sketches, MCP daemon wiring, or headcount automation  
- PR **#10** Copilot trajectory files; **`experiments/2026-11-03/`** paths  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md)  
- Asserting **`verify()`**, conflict counts, or memory hit rates were **measured** in this repo (README only unless future Checker run says otherwise)

---

## Status

- [x] Soft pattern note (markdown only)  
- [ ] In Progress (no upstream clone / no test run in playground)  
- [ ] Complete (Top / runtime) — **explicitly not a goal**

**Next step:** During multi-lane research or synthesis sprints, note whether behavior matches **shared findings + reuse + ref-verified KEEP**; aggregate offline. Merge of this doc is not required for ops.
