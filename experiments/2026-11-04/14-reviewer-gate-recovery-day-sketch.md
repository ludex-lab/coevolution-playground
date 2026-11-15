# Beyond Division of Labor — Reviewer gate & recovery after first failure (Team OS day sketch)

**날짜**: 2026-11-04  
**Paper**: [Beyond Division of Labor: How Roles Shape Feedback and Recovery in Multi-Agent Systems](https://arxiv.org/abs/2611.03931) (Yang et al., arXiv:2611.03931)

**Code**: [ChihHsuan-Yang/AAMAS2027-AgentProtocols](https://github.com/ChihHsuan-Yang/AAMAS2027-AgentProtocols) (MIT) — **Soft UNVERIFIED** in playground: no PER runner, no Omni-MATH/SciBench replay, no forced-submit toggle wired to Team OS. Public repo + paper protocol cited only.

**Dataset (optional)**: [AgentsSci/AAMAS2027-Roles](https://huggingface.co/datasets/AgentsSci/AAMAS2027-Roles) (ungated) — trajectory tables for offline spot-check; **not required** for this markdown sketch to be valid.

## Paper pointer (citation only; no runs today)

From the public abstract and §5.3 on [2611.03931](https://arxiv.org/abs/2611.03931) (Planner–Executor–Reviewer vs role-free; fixed topology, call budget, ground-truth evaluator):

| Metric (paper-reported; cite only) | Value | Notes |
|-----------------------------------|------:|-------|
| First-pass accuracy (roles vs role-free) | ~unchanged | Specialization without first-pass gain in tested settings |
| Recovery after failed first answer (role-free **with feedback** vs role-structured) | role-free higher | All five model–benchmark cells in main comparison |
| Verdict-matched recovery (pooled RS − RF) | **+0.009** | 95% interval **[-0.014, +0.033]** — post hoc, equal verdict counts |
| Forced submit every cycle (exploratory, gemma-4, **400** Omni-MATH) | recovery **0.198 → 0.613** | Role prompts kept; Reviewer gate removed; paired vs role-free: no detected difference |
| Submissions per failed trajectory (gemma-4, RS vs RF) | **1.27** vs **3.20** | Fewer external verdicts under Reviewer gate |
| Reviewer **withhold** before any submission | **53%** of declines | Of role-structured Reviewer declines |
| Failed trajectories **never submitting** (gemma-4 Omni-MATH) | **84 / 316** | Graded once at budget end; no external feedback |
| Reviewer decline when approval allowed (later cycles) | **75%** (RS) vs **4%** (RF third agent) | Omni-MATH / SciBench nuance in paper for prompt-clause coverage |

Playground **does not** reproduce PER loops, grader hints, or frozen campaign cells. HF card v1.2.0 documents feedback-delivery caveats for frozen arm `B` vs control `Bf` — treat any table replay as **Soft UNVERIFIED** until a local manifest run is logged.

---

## 1) Tabulate plan — Reviewer withhold-after-first-failure (observation targets)

Log **descriptive** rates when Team OS runs resemble PER **Reviewer-as-gate** (internal “ready to merge/submit” withheld) vs **forced external check** each cycle. Numbers below are **paper anchors for planning**, not playground baselines.

| Plan row | Numerator sketch | Denominator sketch | Paper anchor (if applicable) |
|----------|------------------|--------------------|------------------------------|
| `withhold_before_first_external` | Reviewer/Checker cycles ending **without** CI/evaluator submit while Smith claims “done” | All Reviewer cycles **before** first external verdict | **53%** of RS Reviewer declines pre-first-submission (gemma-4 narrative in §5.3) |
| `never_external_before_budget` | Runs that exhaust budget with **zero** outside verdict | First-pass-wrong or all failed trajectories | **84/316** never submit (gemma-4 Omni-MATH) |
| `submissions_per_failed_trajectory` | Count of external verdicts (CI red/green, merge gate, harness PASS/FAIL) | Trajectories whose first external grade was wrong | RS **1.27** vs RF **3.20** (paper) |
| `decline_when_submit_allowed` | Withhold after at least one FAIL and policy allows resubmit | Eligible resubmit cycles | RS **75%** vs RF **4%** (paper later-cycle contrast) |
| `recovery_given_first_fail` | Trajectories eventually correct after first external wrong | First-pass-wrong set per condition | Main + exploratory **0.198 → 0.613** under forced submit |

**Team OS proxy:** “External verdict” = Checker-visible **CI result**, integration gate, or attested `log_path` segment Smith cannot edit ([05](./05-parallact-shared-repo-handoff-checklist.md) joint pass; [12](./12-pcm-proof-carrying-handoff-day-sketch.md) when landed PR #23). “Reviewer withhold” = Ork/Smith **does not open PR / does not push for CI** despite local green.

---

## 2) Small P/E/R loop outline — 20 problems (Reviewer gate vs forced submit)

**Tabletop only** — no harness. Same **20** ticket ids across two policy columns; one actor model and fixed call/budget sketch (paper: six cycles max).

| Phase | Reviewer **gate** (role-structured analog) | **Forced submit** each cycle (exploratory analog) |
|-------|---------------------------------------------|-----------------------------------------------------|
| P | Planner decomposes; no final answer in Planner slot | Same |
| E | Executor produces candidate + boxed answer | Same |
| R | Reviewer **[Continue]** vs **[Agree]** controls **whether** external evaluator runs this cycle | After E, **always** enqueue external check (CI / grader) even if Reviewer would withhold |
| Eval | PASS → stop; FAIL → repair hint to all roles (paper) or `failure-id` + log to Team OS | Same, but **more verdict rows** expected |
| Budget | Stop at N cycles or PASS | Same |

**20-problem panel (fictional ids — planning):**

| ticket_id | domain_sketch | gate_policy | forced_submit |
|-----------|---------------|-------------|---------------|
| `RG-01` … `RG-20` | mix: lint fix, doc sketch, flaky test, merge conflict | A: Reviewer may block external | B: Checker/CI invoked every cycle until PASS or budget |

Compare **only descriptively:** final accuracy, recovery among first-fail subset, mean verdicts per ticket, mean internal-only cycles. Paper expectation: B raises verdict count and can raise recovery when feedback is reliable; gate A saves evaluations but may **never** surface hint ([2611.03931](https://arxiv.org/abs/2611.03931) §5.3).

---

## 3) Checklist metrics — recovery after first failure + verdicts per task

Append **one row per task ticket** (or per Cloud Agent run). **Log only.**

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `ticket_id` | string | Stable task id (`RG-07`, `TEAMOS-8842`, …) |
| `policy_sketch` | enum | `reviewer_gate` \| `forced_external_each_cycle` \| `role_free_feedback` \| `unknown` |
| `first_external_verdict` | enum | `pass` \| `fail` \| `none` (budget ended without external) |
| `first_fail_recovery` | bool | First external was wrong **and** final outcome correct |
| `verdict_count` | int | External PASS/FAIL events (CI runs, harness grades) |
| `internal_only_cycles` | int | Cycles with work but **no** external verdict (Reviewer withhold analog) |
| `reviewer_withheld_before_first_external` | bool | Any withhold before first CI/evaluator |
| `never_external_before_budget` | bool | Budget exhausted with `verdict_count=0` |
| `recovery_rate_cell` | string | Optional aggregate label for offline roll-up (not computed here) |
| `notes` | string | Pointers: `failure-id`, `log_path`, PR URL — **no transcript dump** |

### Example row (**example** — fictional, plausible)

| label | ticket_id | policy_sketch | first_external_verdict | first_fail_recovery | verdict_count | internal_only_cycles | reviewer_withheld_before_first_external | never_external_before_budget | notes |
|-------|-----------|---------------|------------------------|---------------------|---------------|----------------------|----------------------------------------|------------------------------|-------|
| **example** | `RG-14` | `reviewer_gate` | `fail` | false | 1 | 4 | true | false | Smith passed local pytest; Ork withheld PR until “ready”; single CI fail then budget; paper analog **1.27** submits/failed traj — cite only |

---

## 4) Map to Ork — `fail≥2` ([01](./01-agentbaton-failure-escalate-handoff.md)) vs outside verdict

| Paper / Team OS concept | Ork / Checker reading |
|---------------------------|------------------------|
| Reviewer gate limits **evaluator** access | Withholding CI/merge is **not** the same as fixing — fewer `failure-id` observations |
| External FAIL + hint | First **outside** verdict with stable `failure-id` starts [01](./01-agentbaton-failure-escalate-handoff.md) counter |
| `consecutive_fail_count >= 2` | Same **`failure-id`** on two **external** failures (or two CI runs), not two internal Reviewer “not ready” notes |
| Escalate to stronger model | **`handoff_artifact`** only after external evidence exists — question for policy: |

**Design memo (markdown only):** Must Checker **submit** (open CI / push for gate) for an **outside** verdict **before** Ork may escalate on `fail≥2`?

- **Yes (strict):** Internal withhold cycles **do not** increment `consecutive_fail_count`; escalation requires at least one external FAIL with matching `failure-id`, then repeat. Aligns with paper claim that recovery needs **feedback opportunities**, not only internal critique.
- **No (lenient):** Local/tool failures count even if Reviewer blocked CI — risks **never-escalate** when gate prevents external grade (paper **84/316** never submit).
- **Recommended sketch default:** **Strict external** for escalate counter; separate **`internal_review_cycles`** column (§3) for Reviewer gate health. Escalation **`handoff_artifact`**: `workspace_pointer` + `log_path` from last **external** run ([01](./01-agentbaton-failure-escalate-handoff.md)).

Cross-links: park / human ticket ([04](./04-impassebench-escalate-to-human-ticket-schema.md)); proof-carrying “tests passed” ([12](./12-pcm-proof-carrying-handoff-day-sketch.md) PR #23); clarification queue ([07](./07-pcp-shared-human-ask-queue-checklist.md)) — orthogonal unless withhold masquerades as ask.

---

## 5) Soft caveat — exploratory intervention & Checker pack

- **Exploratory:** Forced-submit **0.198 → 0.613** is **400**-problem gemma-4 Omni-MATH intervention in paper — not pre-registered frozen cell. Use for **policy intuition**, not KEEP/DROP thresholds.
- **Verdict-matched +0.009** interval crosses **0** — do not claim large recovery advantage for role-structured teams at equal verdicts.
- **Checker pack / CI:** Treat any Team OS “recovery rate” computed from **internal** Smith self-check alone as **invalid** for this sketch; Checker must see **outside** verdict or **`unproven`** claim ([12](./12-pcm-proof-carrying-handoff-day-sketch.md)). Exploratory tabletop may **cross 0** on small-n paired deltas — label **`exploratory`**, not production gate.
- **HF frozen arm `B`:** Dataset README warns role-free **without delivered feedback** confounds role ablation — do not import frozen A-vs-B recovery into Team OS without reading `Bf` control ([AgentsSci/AAMAS2027-Roles](https://huggingface.co/datasets/AgentsSci/AAMAS2027-Roles)).

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- AAMAS2027-AgentProtocols **install**, Omni-MATH/SciBench **replay**, or HF **download** as merge prerequisite  
- New bots, Slack wiring, or PER prompt deployment  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md)  
- Open **PR #10** AgentBaton park body / Copilot trajectory columns — **do not touch**  
- Claiming code or HF numbers **verified** in playground (**Soft UNVERIFIED** unless logged run)  

---

## Status

- [x] Planning (day sketch + tabulate plan + checklist)  
- [ ] In Progress (no PER / CI policy wiring)  
- [ ] Complete  

**Next step:** On sprint tickets, log §3 rows under `reviewer_gate` vs `forced_external_each_cycle`; offline compare `verdict_count` and `first_fail_recovery` — no merge required for ops.

---

## Relied on

| Source | Role in this sketch |
|--------|---------------------|
| [arXiv:2611.03931](https://arxiv.org/abs/2611.03931) | PER recovery, Reviewer withhold rates, forced-submit exploratory, verdict-matched interval — **citation only** |
| [github.com/ChihHsuan-Yang/AAMAS2027-AgentProtocols](https://github.com/ChihHsuan-Yang/AAMAS2027-AgentProtocols) (MIT) | Protocol reference — **Soft UNVERIFIED** (no playground run) |
| [huggingface.co/datasets/AgentsSci/AAMAS2027-Roles](https://huggingface.co/datasets/AgentsSci/AAMAS2027-Roles) | Optional trajectory spot-check; frozen vs `Bf` feedback caveat — **not required** for sketch validity |
