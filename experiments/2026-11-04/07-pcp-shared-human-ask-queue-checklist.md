# PCP — shared-human clarification queue (observation checklist)

**날짜**: 2026-11-04  
**Paper**: [When Should AI Agents Ask? Clarification Requests Under Limited Human Attention](https://arxiv.org/abs/2610.41129) (Wang et al., arXiv:2610.41129)

**Code**: **NONE** — markdown observation checklist only; no Pairwise Coordination Policy (PCP) solver, synthetic 864-portfolio replay, or LLM ask-routing harness in playground.

## Paper pointer (citation only; no runs today)

From the public abstract and §6 results on [2610.41129](https://arxiv.org/abs/2610.41129):

- **Setting:** Several delegated agents share **one human** with limited attention. Each agent may **search** records for a missing requirement, **ask** the human, and continue **independent work** that does not depend on the gap. The human is intermittently available and answers **at most one pending question per period**; a submitted question stays **pending** until answered or **withdrawn** after a successful search.
- **Coordination:** Whether to ask depends on more than one agent’s uncertainty—**which question the human should answer first depends on all waiting questions**; no ranking computed **agent-by-agent** is optimal in general.
- **PCP (Pairwise Coordination Policy):** Estimates delay from **sharing the human** using exactly solvable **one- and two-task** subproblems (pairwise price of shared attention). **Exactly optimal** when at most **two** requirements remain unresolved; costs at most **twice** the optimum when every unresolved requirement must be resolved by the human (paper §5 guarantees).
- **Synthetic benchmark (864 portfolios, three or four tasks):** PCP’s mean cost gap to optimal is **0.07%**; versus three standard **when-to-ask rules**, PCP reduces cost by **18% to 31%** on average (abstract / §6).
- **LLM case study:** Agents completed every task correctly in the paper’s Codex procurement setting; PCP achieved the **lowest mean cost** in all tested settings (abstract)—playground **does not** re-run that study or add Codex trajectory columns.

Playground **does not** implement PCP, fit search probabilities \(p_i,\alpha_i\), or reproduce the dynamic program.

---

## Map to Team OS (Ork → JJ bandwidth; markdown only)

| Paper concept | Team OS analog (observation / policy sketch) |
|---------------|-----------------------------------------------|
| Shared human, one answer per attention slice | **Central question queue** for JJ (or designated human): one **active clarification** served at a time across parallel Cloud Agent / village runs—not N simultaneous @-mentions competing without ordering. |
| Pending question + continued search | **Withdrawable ask:** agent keeps working and **pulls back** the ask when logs, repo search, or tests resolve the gap before the human answers ([01](./01-agentbaton-failure-escalate-handoff.md) `log_path` / artifact search—not chat archaeology). |
| Portfolio-optimal queue order | Queue **priority from the whole waiting set** (pairwise shared-attention intuition)—not “first inbox wins” per bot thread. |
| Independent work while waiting | Ork/Smith continue **non-blocked** subtasks (docs, tests unrelated to open spec) while `ask_state=pending`. |
| Impasse / park | Distinct path: **`escalate_to_human`** ticket + park ([04](./04-impassebench-escalate-to-human-ticket-schema.md)) when the gap is an **environment impasse**, not a clarifying preference—do not mix into the same queue row without tagging. |

### Ork → JJ bandwidth norms (design memo)

1. **Do not score bots by ask-rarity.** The paper shows more independent work can **increase** justified ask demand; penalizing “too many questions” per agent misaligns with portfolio-optimal coordination.
2. **Prefer withdraw over stale answers.** If an ask is withdrawn, JJ should not spend attention on superseded text—queue UI should drop or mark **withdrawn** clearly.
3. **Log queue decisions, not transcripts.** Record which pending ask was served, in what order, and whether others were waiting—**pointers only** (`run_id`, `ask_id`, `log_path`).

**Cross-links (optional):** Model **escalate** after repeat `failure-id` ([01](./01-agentbaton-failure-escalate-handoff.md)); **control transfer** rows ([06-care-escalate-verified-progress-checklist.md](./06-care-escalate-verified-progress-checklist.md) when landed)—orthogonal to clarification queue unless the same run both asks and parks.

---

## Observation checklist (shared-human ask queue)

Log **one row per clarification ask** (submit, serve, or withdraw). **Log only**—no automated PCP or ask-rule baselines.

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** (fictional demo row) |
| `run_id` | string | Cloud Agent / Team OS run id or stable session key |
| `agent_slot` | string | Which parallel agent/thread (e.g. `smith-pr-7`, `ork-research-a`) |
| `ask_id` | string | Stable id for this ask (re-submit after withdraw → new id) |
| `question_sketch` | string | One-line missing spec (timezone, merge policy, ACL)—**no transcript dump** |
| `ask_state` | enum | `pending` \| `answered` \| `withdrawn` |
| `submitted_at` | string | ISO time or relative period index |
| `withdrawn_before_serve` | bool | True if search/work resolved gap before human answered |
| `parallel_search_active` | bool | Agent kept searching while `pending` (paper-allowed) |
| `independent_work_continued` | bool | Non-blocked subtasks advanced while waiting |
| `waiting_ask_count` | int | **Portfolio-wide** pending asks when human became available |
| `served_order` | int \| null | 1-based order human served this ask among waiting set (`null` if withdrawn unanswered) |
| `rule_sketch` | enum | Human/Ork policy used: `fifo` \| `newest_first` \| `manual_jj` \| `portfolio_pairwise` \| `unknown` |
| `outcome` | enum | `resolved_by_human` \| `resolved_by_search` \| `still_pending` \| `superseded` |
| `notes` | string | Queue contention, stale serve, link to `log_path` segment |

### Example row (**example** — fictional, plausible)

| label | run_id | agent_slot | ask_id | question_sketch | ask_state | submitted_at | withdrawn_before_serve | parallel_search_active | independent_work_continued | waiting_ask_count | served_order | rule_sketch | outcome | notes |
|-------|--------|------------|--------|-----------------|-----------|--------------|------------------------|------------------------|----------------------------|-------------------|--------------|-------------|---------|-------|
| **example** | `ca-run-pcp-sketch-9c1` | `smith-docs-9c1` | `ask-9c1-a` | Which Origin PR counts as “done” for sprint #7—merge or open URL? | `withdrawn` | `2026-11-04T07:10Z` | true | true | true | 2 | null | `manual_jj` | `resolved_by_search` | Found answer in `experiments/2026-11-04/README.md` on `main`; withdrew before JJ served; other run’s ask served first (`served_order=1` on sibling row—not duplicated here) |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- New bots, Slack wiring, or triage daemons implementing PCP  
- Runtime PCP harness, 864-portfolio replay, or ask-rule A/B baselines  
- Cody trajectory / intervention columns (open **PR #10** only—**do not** add those fields here)  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[04](./04-impassebench-escalate-to-human-ticket-schema.md) or open PR #10 description  

---

## Status

- [x] Planning (observation checklist sketch)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** When JJ oversees multiple parallel agents, append rows for submit / serve / withdraw events; review queue order offline against portfolio cost—no merge of this doc required for ops.
