# CoworkOS — delegation evidence contract & return boundary (day sketch)

**날짜**: 2026-11-04  
**Paper**: [CoworkOS: Scaling Agent Coworkers for Real-world Automation](https://arxiv.org/abs/2611.03178) (Jin et al., arXiv:2611.03178)

**Code**: [RUC-NLPIR/CoworkOS](https://github.com/RUC-NLPIR/CoworkOS) — **Soft UNVERIFIED** in playground: no `npx coworkos-app`, no `npm install -g coworkos-app`, no local CLI/desktop harness; schema + mock outline only. Repo ideas cited from public README / paper prose (three-layer Main → Coordinator → Subagents, shared application resources, Jobs)—not from a verified checkout of `packages/` layout here.

## Paper pointer (citation only; no runs today)

From the public abstract and §3 harness prose on [2611.03178](https://arxiv.org/abs/2611.03178):

- **Division of labor:** The **model** chooses task strategy, **delegation**, and **acceptance**; the **runtime** (Coordinator) maintains state, queues, and feedback across context boundaries.
- **Delegation as evidence contract:** Main specifies objective, constraints, capability grants, and **expected evidence** at the assignment boundary; Subagents return **report**, **evidence references**, and compact **status** while detailed trajectories stay separately accessible.
- **`ask_main` (async worker):** A Subagent may request a concrete decision from Main with a **bounded wait** and a **declared fallback assumption** so work can progress without holding the runtime indefinitely (paper §3 delegation return path).
- **Shared artifacts:** Platform-managed resources carry **revision**; a stale-base edit yields **conflict**, not silent overwrite (paper Eq. 7 narrative)—humans and agents co-edit the same evolving object.
- **Jobs / long horizon:** Long-running operations retain **status and logs** so work resumes after waiting or interruption.

Playground **does not** install CoworkOS, run Coordinator queues, or reproduce benchmark tables from the paper.

---

## Map to Team OS (markdown only)

| CoworkOS idea | Team OS analog (this sketch) |
|---------------|------------------------------|
| Main → Subagent delegation packet | Ork/Smith **scoped assignment** with explicit caps—not “whole repo write” by default ([08](./08-delegated-scope-affordance-violation-checklist.md) when landed on `main`; PR #19) |
| Coordinator return boundary | **Return row** + pointers (`log_path`, artifact refs)—not transcript merge into parent context ([01](./01-agentbaton-failure-escalate-handoff.md) `handoff_artifact` discipline) |
| `ask_main` + fallback | **Bounded wait** on human/Main; on timeout use `fallback_assumption`; repeat **`failure-id`** → model **escalate** at `consecutive_fail_count >= 2` ([01](./01-agentbaton-failure-escalate-handoff.md)) |
| Revision-aware shared artifact | Git/shared doc edit with **base SHA or revision id**; stale parent ⇒ **conflict** row, not force overwrite ([05](./05-parallact-shared-repo-handoff-checklist.md) joint-fail lens) |
| Impasse vs clarification | Environment **park** ticket ([04](./04-impassebench-escalate-to-human-ticket-schema.md)) vs PCP **ask queue** ([07](./07-pcp-shared-human-ask-queue-checklist.md))—tag which path a wait belongs to |

---

## 1) Delegation evidence-contract template (Main → Subagent)

Ork/Main publishes one **delegation contract** per assignment revision. Checker offline-lints required fields before treating a Subagent run as in-scope.

| Field | Type | Required | Definition |
|-------|------|----------|------------|
| `contract_id` | string | yes | Stable id (`cowork-del-9a1`) |
| `contract_version` | int | yes | Bump when objective, caps, or evidence shape changes |
| `task_id` | string | yes | Parent Task / sprint run key |
| `objective` | string | yes | Outcome Main will accept—testable or inspectable deliverable |
| `constraints` | string[] | yes | Hard limits: paths, time, budget, forbidden actions (“no force-push”, “markdown only”) |
| `background_refs` | string[] | no | Pointers to workspace files, prior Run logs—**not** full parent transcript |
| `granted_caps` | object | yes | Explicit capability grants (see sub-table) |
| `expected_evidence` | object | yes | What must appear at return boundary for Main to judge acceptance |
| `delegation_mode` | enum | yes | `sync` \| `async` — whether result blocks Main’s calling path immediately |
| `parent_workspace_pointer` | string | yes | Repo, branch, head SHA at handoff ([01](./01-agentbaton-failure-escalate-handoff.md) style) |

### `granted_caps` (sketch)

| Key | Type | Definition |
|-----|------|------------|
| `allowed_paths` | string[] | Repo globs Subagent may mutate (delegation \(D\) paths) |
| `allowed_tools` | string[] | Tool names / MCP surfaces enabled for this assignment only |
| `read_shared_refs` | string[] | Task artifact refs readable but not writable unless listed in `allowed_paths` |
| `peer_message` | bool | Whether minimal async peer Inbox is allowed (paper peer channel) |
| `max_wall_ms` | int | Optional wall budget for the assignment |

### `expected_evidence` (sketch)

| Key | Type | Definition |
|-----|------|------------|
| `deliverable_refs` | string[] | Paths or artifact ids that must exist or change |
| `verification_sketch` | string | How Main checks acceptance (test cmd, diff stat, human review gate) |
| `required_log_segments` | string[] | `log_path` offsets or Job ids that must be cited in return |
| `acceptance_criterion` | string | One-line restatement of \(\mathcal{V}\) from paper task formulation |

### Example contract fragment (**example** — fictional)

```yaml
contract_id: cowork-del-9a1
contract_version: 1
objective: "Add experiments/2026-11-04/09-* sketch only; README one row"
constraints:
  - "No npm install coworkos-app"
  - "Do not edit PR #10 body or AgentBaton park files"
granted_caps:
  allowed_paths: ["experiments/2026-11-04/**"]
  allowed_tools: ["Read", "Write", "Shell", "ManagePullRequest"]
expected_evidence:
  deliverable_refs: ["experiments/2026-11-04/09-coworkos-delegation-evidence-contract-day-sketch.md"]
  verification_sketch: "README index row #9; Origin PR open; conflict-free vs main"
```

---

## 2) Return schema (Subagent → Coordinator → Main)

One **return row** per terminal delegation (success, partial, failed, cancelled). Trajectory detail stays out of parent context; only this packet crosses the boundary.

| Field | Type | Required | Definition |
|-------|------|----------|------------|
| `return_id` | string | yes | Matches or references `contract_id` + attempt |
| `contract_id` | string | yes | Join key to delegation contract |
| `report` | string | yes | Compact narrative: what was done, blockers, next step—bounded length |
| `evidence_refs` | string[] | yes | Pointers only: SHAs, `log_path`, Job id, artifact `@revision` |
| `status` | enum | yes | `completed` \| `partial` \| `failed` \| `cancelled` |
| `uncertain` | string[] | no | Claims Main must not treat as verified (assumptions, flaky tests, unread peer message) |
| `candidate_refs` | string[] | no | Private candidates not yet promoted to shared artifact (paper candidate path) |
| `failure-id` | string | no | Repeatable signature if `status=failed` ([01](./01-agentbaton-failure-escalate-handoff.md)) |
| `handoff_artifact` | object | no | On fail/escalate: `workspace_pointer` + `log_path` only |

### Example return row (**example** — fictional)

| label | contract_id | status | report (sketch) | evidence_refs | uncertain |
|-------|-------------|--------|-----------------|---------------|-----------|
| **example** | `cowork-del-9a1` | `partial` | Draft sketch committed; README row pending rebase vs open #8 PR | `experiments/.../09-*.md@sha9a1`, `/tmp/ca-run-9a1.log` | Whether README should include #8 row before #9 lands |

---

## 3) `ask_main` record (bounded wait + fallback)

Log when an async Subagent **blocks on Main/human** for a decision that changes approach. Tie **deadline** behavior to the same **two-strike** escalate pattern as AgentBaton on repeated delegation failure.

| Field | Type | Definition |
|-------|------|------------|
| `ask_id` | string | Stable id for this Main decision request |
| `contract_id` | string | Originating delegation |
| `question_sketch` | string | One-line ambiguity (merge policy, acceptance test, cap widen) |
| `wait_ms` | int | **Bounded wait** before fallback applies (paper: bounded wait on Main) |
| `fallback_assumption` | string | Declared assumption used if Main silent at deadline—must be explicit enough to audit |
| `observation_source` | string \| null | What will wake the worker early: Job poll, Inbox id, file watch, human queue row ([07](./07-pcp-shared-human-ask-queue-checklist.md)) |
| `review_time` | string \| null | ISO time or “next JJ slice” when Main commits to answer—scheduled review |
| `ask_outcome` | enum | `answered` \| `fallback_used` \| `withdrawn` \| `escalated` |
| `failure-id` | string \| null | If fallback_used twice with same bad outcome signature, link to [01](./01-agentbaton-failure-escalate-handoff.md) **`escalate_when`** |

### Escalate coupling (**design memo**)

1. Subagent uses `fallback_assumption` after `wait_ms` without Main answer—**log `ask_outcome=fallback_used`**.
2. If the resulting work hits the **same `failure-id` twice in a row** on that contract, set **`escalate_when`** true: stop Subagent tier, assemble `handoff_artifact`, open **stronger Main/model** session ([01](./01-agentbaton-failure-escalate-handoff.md)—failure-driven escalate, not CoworkOS capable→efficient direction).
3. Distinct from **Impasse park**: if `fallback_assumption` violates `constraints` or needs infra, prefer [04](./04-impassebench-escalate-to-human-ticket-schema.md) ticket instead of silent fallback.

### Example `ask_main` row (**example**)

| label | ask_id | wait_ms | fallback_assumption | observation_source | review_time | ask_outcome | notes |
|-------|--------|---------|---------------------|----------------------|-------------|-------------|-------|
| **example** | `ask-9a1-merge` | 900000 | “Reserve README #9 only; #8 lands via PR #19” | `origin pr list` poll + README on `main` | `2026-11-04T12:00Z` | `answered` | Main answered before deadline; no fallback |

---

## 4) Lint rule note (wait without wake condition)

**Offline Checker rule (sketch):** Reject any record that enters **`waiting`** (delegation blocked on Main/human/Job) when **both** are absent:

- `observation_source` — no durable poll/subscription/Inbox/queue id that can produce a wake event, **and**
- `review_time` — no committed human/Main review deadline.

**Rationale:** CoworkOS async paths allow progress via **fallback_assumption**, but the runtime still needs either a **wake channel** or a **scheduled review** so Tasks do not stall with unbounded “wait for Main” states (aligns with paper Jobs/inbox integration and Team OS **park** gates in [04](./04-impassebench-escalate-to-human-ticket-schema.md)).

**Pass examples:** `wait_ms` + `fallback_assumption` + (`observation_source=job:train-42` **or** `review_time=2026-11-05T09:00Z`).  
**Fail example:** “Waiting for JJ” with null `observation_source` and null `review_time`.

---

## 5) Revision check on shared artifacts

When humans and agents edit the **same shared artifact** (document, CAD ref, branch tip), admit edits only with a **base revision**.

| Field | Type | Definition |
|-------|------|------------|
| `artifact_ref` | string | Path or platform resource id |
| `base_revision` | string | Git SHA, `revision_id`, or saved generation Main/Subagent believed |
| `actor` | string | `main` \| `subagent` \| `human` \| role slot |
| `proposed_revision` | string | New SHA or candidate id after edit |
| `admission` | enum | `accepted` \| `conflict` \| `candidate_only` |
| `conflict_notes` | string | What changed since `base_revision`; pointer to current tip |

**Norm (paper Eq. 7 narrative):** **`conflict`** preserves intervening edits; **do not overwrite**. Main re-merges or re-delegates from current tip—analogous to stale PR base on shared repo ([05](./05-parallact-shared-repo-handoff-checklist.md)).

Subagent **candidates** stay `candidate_only` until Main promotes; promotion re-runs revision check against live artifact.

---

## 6) Mock run outline (no CoworkOS install)

Fictional **tabletop** sequence for Team OS sprint lab—no Coordinator binary, no `coworkos` CLI.

| Step | Actor | Action | Log artifact |
|------|-------|--------|--------------|
| 1 | Ork (Main) | Publish `contract_id=cowork-del-mock-1` with objective + `granted_caps.allowed_paths` | delegation contract row |
| 2 | Cloud Agent (Subagent) | Accept async delegation; write draft under allowed path | Run events → `log_path` |
| 3 | Subagent | Hit ambiguity on README numbering; emit `ask_main` with `wait_ms=600000`, `fallback_assumption="append #9 row only on main tip"` | `ask_main` row |
| 4 | Runtime sketch | Set `observation_source=git fetch origin main` + `review_time` + pass **lint rule §4** | lint note |
| 5 | JJ (Main) | Answer before deadline: “Use 09- filename; rebase if #8 merges” | `ask_outcome=answered` |
| 6 | Subagent | Commit; return `status=completed` with `evidence_refs` (SHA, PR URL sketch) | return schema row |
| 7 | Checker | Verify return cites `expected_evidence.deliverable_refs`; no transcript in parent packet | offline checklist |
| 8 | (Alt branch) | Second writer edits same README without fresh `base_revision` | `admission=conflict` row—not silent merge |

**Stop before:** installing `coworkos-app`, opening Blender/CAD adapters, or claiming reproduced CoworkOS benchmark scores.

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- `coworkos init`, desktop install, or MCP wiring from [CoworkOS docs](https://github.com/RUC-NLPIR/CoworkOS/tree/main/docs) — **Soft UNVERIFIED** paths not exercised here  
- New bots, Slack wiring, Coordinator **runtime** implementation  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[08](./08-delegated-scope-affordance-violation-checklist.md) or **PR #10** description / park body  
- Cody trajectory columns (PR #10 only)  
- Merging this PR or any sibling sprint PR  

---

## Status

- [x] Planning (contract + return + ask_main + lint + revision + mock outline)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** On real multi-step Cloud Agent delegations, append contract/return/`ask_main`/revision rows offline; cross-check waits against lint rule §4 before treating a Task as “blocked on Main”.
