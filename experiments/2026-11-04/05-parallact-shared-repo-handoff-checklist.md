# ParallACT — shared-repo multi-writer handoff (Team OS / Ludex observation checklist)

**날짜**: 2026-11-04  
**Paper**: [ParallACT: A Diagnostic Testbed for Multi-Agent Coordination in Shared Codebases](https://arxiv.org/abs/2611.00314) (arXiv:2611.00314)

**Code**: **GH Soft UNVERIFIED** — no verified public GitHub repository URL in this sketch; playground does not install ParallACT or run multi-agent harnesses.

## Paper pointer (citation only; no runs today)

From the public abstract and §5 results on [2611.00314](https://arxiv.org/abs/2611.00314) (Claude Code + Claude Opus 4.8 on **contradictory** instances unless noted):

| Metric (paper-reported) | Value | Notes |
|-------------------------|------:|-------|
| Single-agent oracle **joint pass** (both requirements visible to one agent) | **62%** | Contradictory split; paper Table 1 / §5 — **success rate**, not a “conflict rate” |
| Parallel-unaware **joint pass** (two agents, no peer awareness) | **16%** | Same split; large drop vs oracle (**62% → 16%**, $p<0.001$ in paper) |
| Sequential **A→B** hand-off **joint success** (one turn each, no edit history) | **54%** | vs **16%** parallel-unaware on contradictory instances ($p<0.001$) |

Complementary-instance oracle (**86%**) and parallel-unaware (**57%**) figures appear in the same tables; this checklist cites the contradictory **joint pass / joint success** trio above only where they motivate **shared-repo coordination** failures.

**Evidence note:** ParallACT instances, reconcilers, Redis/shared-file channels, and full significance tables live in the paper PDF and appendices— not transcribed here.

---

## Shared codebase → Team OS / Ludex (observation lens)

ParallACT is **not** Team OS runtime today. Use the mapping when **two or more principals** (humans and/or agents) edit the **same repository** with **separate requirements** that must **jointly pass** integration tests.

| ParallACT idea | Team OS / Ludex reading |
|----------------|-------------------------|
| Two agents, one workspace, separate specs | Parallel Cloud Agent runs, dual Smith lanes, or JJ + agent on one branch without a single writer lock |
| Parallel-unaware collapse in **joint pass** | Each side “green” locally (own tests / own PR checks) but **combined** state fails Checker / integration |
| Sequential **A→B** hand-off | **Structured handoff**: B starts from A’s pushed commit; one-writer-at-a-time on the contested tree |
| Shared append-only file / Redis inbox | Ludex **handoff channel** (pointer file, thread summary, forge ticket)—not a chat transcript dump |
| Complementary vs contradictory interaction | **Non-interacting** paths vs **shared interface** vs **same region** edits—sets how heavy handoff must be |

Mechanical handoff already on main in [01-agentbaton-failure-escalate-handoff.md](./01-agentbaton-failure-escalate-handoff.md): **`handoff_artifact`** = `workspace_pointer` + `log_path` only.

---

## Observation focus (this sprint)

Log rows when a multi-writer episode resembles ParallACT coordination stress—not to reproduce benchmark numbers.

1. **One-writer + structured handoff** — Was there an explicit **turn order** (A finishes → pointer → B), or simultaneous writers on one branch? Did handoff include **SHA / branch / log path** without transcript rehydration?
2. **Contested artifact ownership** — Which **path, module, or config** did both sides touch? Who held write authority (branch protection, lease, Ork assignment)? Any overwrite or force-push after peer work?
3. **Send-early / read-late failure mode** — Actor **appended** handoff or “done” signal before peers **re-read** shared state; peer continued from stale base (paper’s async channel risk abstractly, not Redis-specific).

---

## Observation checklist (Team OS / Ludex)

**Log only** in this sketch—no automated merge resolver, no ParallACT harness.

| Column | Type | Definition |
|--------|------|------------|
| `run_id` | string | Cloud Agent run id, village session, or ticket key |
| `writers` | string | Who edited: e.g. `agent_a+agent_b`, `jj+smith`, `parallel_runs` — roles or run ids, not personal names required |
| `artifact` | string | Contested **repo object**: branch, path glob, package, or integration test name |
| `handoff_shape` | enum | `parallel_unaware` \| `sequential_ab` \| `sequential_ba` \| `one_writer_lease` \| `shared_channel_file` \| `other` |
| `failure_mode` | enum | `joint_fail_local_pass` \| `overwrite_peer` \| `send_early_read_late` \| `ownership_dispute` \| `reconciler_only_fix` \| `none_observed` |
| `outcome` | enum | `joint_pass` \| `joint_fail` \| `aborted` \| `unknown` — **team/integration** result, not single-side CI |
| `notes` | string | Pointers only: SHAs, `handoff_artifact`, channel id; cite paper motivation if useful (**62/16/54** as **joint pass**, not conflict %) |

Optional cross-link: stable **`failure-id`** from [01](./01-agentbaton-failure-escalate-handoff.md) when the joint failure signature repeats across runs.

### Example row (**example** — fictional, plausible)

| label | run_id | writers | artifact | handoff_shape | failure_mode | outcome | notes |
|-------|--------|---------|----------|---------------|--------------|---------|-------|
| **example** | `TEAMOS-par-2c91` | `cloud-agent-run-a9f2 + cloud-agent-run-b3e0` | `src/api/cache.py` (shared arg slot) | `parallel_unaware` | `joint_fail_local_pass` | `joint_fail` | Each run passed its own pytest module; combined branch failed integration; no `one_writer_lease`; paper cites **16%** parallel-unaware **joint pass** vs **62%** oracle on contradictory tasks—analogy only |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- New bots, Slack wiring, ParallACT / SWE-Bench Pro **runtime harness**  
- Inventing a ParallACT **GitHub URL** or claiming **GH Soft** release status beyond **UNVERIFIED**  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[04](./04-impassebench-escalate-to-human-ticket-schema.md)  
- PR #10 Copilot trajectory files or `experiments/2026-11-03/` paths  

---

## Status

- [x] Planning (observation checklist sketch)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** During dual-writer Ludex or parallel Cloud Agent work on one repo, append rows when handoff shape or contested paths explain **joint_fail** despite local green—aggregate offline; no merge of this doc required for ops.
