# ATC — Team OS role-contract Soft sketch (Ork / R / Smith / Checker)

**날짜**: 2026-11-04  
**Paper**: [ATC: Agent Trajectory Control for Role-Contract Enforcement in Black-Box Multi-Agent Systems](https://arxiv.org/abs/2611.04321) (Maliha et al., arXiv:2611.04321)

**Code**: **GH Soft UNVERIFIED** — upstream [VishalPramanik/ATC](https://github.com/VishalPramanik/ATC) README stub only; playground **does not** install ATC, run behavior encoder \(f\), role-drift energy \(E_{i,t}\), or constrained regeneration \(g\). **Soft no runtime.**

## Paper pointer (citation only; no runs today)

From the public abstract and §3–§4 on [2611.04321](https://arxiv.org/abs/2611.04321):

- **Role drift:** Turn-level breach of an agent’s **role contract**—locally sensible messages that exercise **another role’s authority** (verifier plans, retriever asserts unsupported conclusions, executor mutates unapproved state).
- **ATC loop (paper):** Encode proposal → score **out-of-role deviation**, **cross-role leakage**, **impermissible speech acts**, **logical contract** breaches → leakage-regularized target → regenerate → **re-check before admission** to shared conversation.
- **Pilot separation (Table 1, descriptive):** Stable vs drifted turns differ sharply on \(D^{\mathrm{out}}\), \(D^{\mathrm{leak}}\), \(D^{\mathrm{ling}}\), \(D^{\mathrm{logic}}\), and energy \(E_{i,t}\) (paper-reported class means—not playground measurements).
- **Main results (Table 2, means over three seeds):** ATC vs strong baselines improves task scores and **Role Consistency (RC)** while lowering **Role Drift Energy (RDE)** on EntCollabBench, MultiAgentBench, and SWE-bench Verified under Hom-10 / Het-10 / Het-12—**citation only** here.

Playground **does not** reproduce benchmarks, role subspaces \(U_i\), or black-box revision harnesses.

---

## Soft sketch: `roles.yaml` (declarative contract only)

Machine-readable Team OS contracts aligned with paper terms \(\mathcal{C}_i=(\mathcal{O}_i,\mathcal{B}_i)\) and linguistic profile \(b_i\) over speech acts \(\ell_{i,t}\)—**documentation / offline rubric**, not an admission gate.

**File:** [19-atc-role-contract-roles.yaml](./19-atc-role-contract-roles.yaml)

| Team OS role | Paper analog (informal) | Contract emphasis in yaml |
|--------------|-------------------------|---------------------------|
| **Ork** | Coordinator / delegator | **Delegate** + summarize scope; **forbidden** implement / verify / merge-as-Smith |
| **R** | Retriever / analyst | **Retrieve** + cite; **forbidden** execute writes / checker verdict |
| **Smith** | Executor / builder | **Execute** + handback pointers; **forbidden** self-verify / scope rewrite |
| **Checker** | Verifier / critic | **Verify** + evidence contrast; **forbidden** primary implement / merge |

**Speech-act keys** (`assert`, `question`, `retrieve`, `verify`, `execute`, `delegate`, `summarize`): `1` = role may use that act in public artifacts; `0` = treat as **role drift** in offline review (paper \(D^{\mathrm{ling}}\) intuition—not computed).

---

## Map to existing Team OS sketches (markdown only)

| ATC / drift signal | Where Team OS already logs or norms |
|--------------------|-------------------------------------|
| Logical contract \(\mathcal{O}_i,\mathcal{B}_i\) | [CONTRIBUTING.md](../../CONTRIBUTING.md) role boundaries; yaml `required_behaviors` / `forbidden_behaviors` |
| Message-boundary admission | **Not implemented** — contrast [01](./01-agentbaton-failure-escalate-handoff.md) handoff **pointers**, [02-sbus](../2026-11-02/02-sbus-version-check-board-rule.md) **`relied_on`** stale-write observe |
| Cross-role leakage (verifier plans, builder verifies) | [03](./03-cmu-hai-failure-taxonomy-observation-checklist.md) mode **10** drift; [06](./06-care-escalate-verified-progress-checklist.md) escalate vs local retry |
| Shared-context pollution after bad turn | [05](./05-parallact-shared-repo-handoff-checklist.md) joint_fail despite local green |

**Cross-links (optional):** Clarification queue vs impasse ticket ([07](./07-pcp-shared-human-ask-queue-checklist.md) vs [04](./04-impassebench-escalate-to-human-ticket-schema.md))—Ork must tag which contract path applies; yaml does not merge those queues.

---

## Observation checklist (role-drift log — Soft)

Log **one row per suspected role-drift turn** in public Team OS artifacts (handback, PR comment, village post). **Log only**—no ATC scorer, no auto-regeneration.

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `run_id` | string | Cloud Agent / session id |
| `speaker_role` | enum | `ork` \| `r` \| `smith` \| `checker` |
| `drift_class` | enum | `out_of_role` \| `cross_role_leak` \| `speech_act_violation` \| `logical_contract` \| `unknown` |
| `leaked_into` | enum \| null | Target role if `cross_role_leak`: `ork` \| `r` \| `smith` \| `checker` |
| `speech_act_seen` | string | Dominant act in message (vocabulary from yaml) |
| `contract_clause` | string | Short id from yaml behavior or CONTRIBUTING (e.g. `verify_own_artifacts_as_final_gate`) |
| `relied_on` | json | **Decision-used** `[{ id, version }]` subset if the turn was a handback or done claim ([02](../2026-11-02/02-sbus-version-check-board-rule.md) semantics)—empty if N/A |
| `outcome` | enum | `corrected_by_human` \| `accepted_drift` \| `blocked_at_merge` \| `not_reviewed` |
| `notes` | string | Pointers only: `log_path`, PR URL, head SHA—no transcript dump |

### Example row (**example** — fictional)

| label | run_id | speaker_role | drift_class | leaked_into | speech_act_seen | contract_clause | relied_on | outcome | notes |
|-------|--------|--------------|-------------|-------------|-----------------|-----------------|-----------|---------|-------|
| **example** | `ca-run-atc-sketch-k2a` | `smith` | `cross_role_leak` | `checker` | `verify` | `verify_own_artifacts_as_final_gate` | `[{"id":"origin_pr/42/forge_head","version":"deadbeef"}]` | `blocked_at_merge` | Smith handback marked `ready` with checker-only verify language; Checker rejected at merge gate; Ork reassigned verify pass |

---

## Soft no runtime caveat

- **No** behavior vector \(z_{i,t}=f(\cdot)\), **no** projections \(P_i,Q_i\), **no** energy thresholding, **no** regeneration operator \(g\).
- **No** clone/install of [VishalPramanik/ATC](https://github.com/VishalPramanik/ATC) in playground; treat upstream code as **GH Soft UNVERIFIED** until team verifies release artifacts.
- **No** new bots, Slack wiring, or message intercept daemons—review yaml + append observation rows offline.
- **`relied_on`:** When logging drift on handbacks, use **board pointer ID + version** for evidence the speaker actually relied on—not full `read_set` dumps ([02](../2026-11-02/02-sbus-version-check-board-rule.md)).

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- ATC benchmark replay, RC/RDE numbers as Team OS KPIs  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or **Origin PR #10** (AgentBaton / Copilot trajectory)—**leave PR #10 alone**  
- `experiments/2026-11-03/` paths or Cody trajectory columns  

---

## Status

- [x] Planning (Soft role-contract yaml + observation rubric)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** On merge disputes or handback taxonomy violations, tag rows with `drift_class` and optional `relied_on`; compare against [19-atc-role-contract-roles.yaml](./19-atc-role-contract-roles.yaml)—no ATC install required.
