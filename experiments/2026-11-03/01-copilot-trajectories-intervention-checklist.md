# Copilot trajectories — CloudAgent intervention checklist

**날짜**: 2026-11-03  
**Paper**: [Large-Scale Study of GitHub Copilot Trajectories](https://arxiv.org/abs/2610.32313) (Sohail et al., arXiv:2610.32313, NYU Abu Dhabi)

## Paper takeaways (Team OS)

Numbers below are **paper-reported** from the public abstract and body ([2610.32313](https://arxiv.org/abs/2610.32313)); not re-computed in playground.

- **Scope:** 7,581 GitHub Copilot **cloud agent** PRs (issue-assigned, ≥100-star repos, on/after 2025-08-05 @-mention rule), with scraped session trajectories encoded as PR lifecycles (initial trajectory + zero or more Human–AI loops after `@copilot` feedback).
- **Mostly hands-off:** **58%** of PRs have **no** human intervention (no Human–AI loop); agent work stays in one initial trajectory for the majority.
- **Intervention is brief when it happens:** Among intervened PRs, **median 2** Human–AI loops (max 25 in data); merge status within intervened PRs does **not** strongly track loop count (both merged and unmerged groups median **2** loops — negligible effect size).
- **Merge association:** **78%** of **intervened** PRs merge vs **62%** of **non-intervened** (χ², small Cramér’s V ≈ 0.17) — intervention **presence** correlates with merge, not necessarily “more loops = better.”
- **First intervention reshapes the nett run:** Trajectory **after the first** human intervention drops **~20.8 iterations** and **~8.4 min** vs pre-intervention trajectory; **later** interventions show minimal iteration drop and no significant duration change — most agent effort sits in the **initial** trajectory; follow-ups tend to be smaller, focused requests.
- **Initial effort vs outcome:** Merged PRs tend to have **fewer initial trajectory iterations** than unmerged (e.g. median initial **34 vs 39** overall); long initial runs correlate with harder tasks and eventual intervention.
- **Qualitative patterns:** Common interventions — implementation alternatives, requirement refinement, bug pointers, spec misunderstandings; some developers **delegate** via feedback, others **commit themselves**; repeated / hand-holding loops exist but are not the model case.
- **Partial public data:** PR metadata and events come from **AIDev v4 (2.7M-PR release)** on Hugging Face; this paper’s **session-level JSON lifecycle encoding** is separate from the bulk HF dump (cite only — do not download the full dataset here).

**Evidence note:** Merge-rate breakdown (78% / 62%) and loop medians are from §RQ1 / Table II in the paper. “~58% no intervention” and “20.8 / 8.4 min after first intervention” match the abstract.

---

## Intervention checklist (CloudAgent / Origin PRs)

Map Copilot’s `@copilot` Human–AI loop to Team OS: **Ork** scopes the run, **Checker** (or Smith) decides when to comment / redirect the agent, **board open-PR column** surfaces stuck PRs ([2026-11-02 #3](../2026-11-02/03-board-open-pr-column.md)). This is **policy + logging**, not a new automation layer.

Complements **handoff allocation** ([Who Takes the Lead](../2026-11-02/01-who-takes-the-lead-handoff-checklist.md)): there, the question is *who moves*; here, the question is *whether the agent gets another trajectory* after human feedback.

### When to stay quiet (let the agent finish the initial trajectory)

- [ ] Task was **fully specified** in the issue / agent brief; reversible markdown or scoped code; CI not failing on fundamentals.
- [ ] Agent is still within **expected initial effort** for the task class (no unbounded iteration spiral visible in run logs / PR timeline).
- [ ] Human has **no shorter path** than a focused agent comment would provide (cf. Δ proxy in handoff checklist) — waiting avoids noise interventions that paper associates with **longer** initial trajectories before merge.
- [ ] PR is **open but progressing** (new commits, plan updates) — use open-PR visibility before pinging.

**Paper anchor:** **58%** non-intervened; **62%** of non-intervened merged PRs are “fully autonomous” (no extra developer commits); many successful merges never needed a loop.

### When to step in (first human / Checker intervention)

Prefer **one clear, scoped** feedback message (Copilot analogue: `@`-tagged comment that starts a **new session** / trajectory).

- [ ] **Wrong direction** early: spec mismatch, wrong files, missing constraint — paper: first intervention often **shortens** the next trajectory; early correction is high leverage.
- [ ] **CI / tests red** with an obvious fix the agent can execute (bug pointer, not a lecture).
- [ ] **Initial trajectory looks “too heavy”** vs task (many iterations, no merge progress) — paper links higher initial iteration counts with unmerged and eventually intervened PRs.
- [ ] **Security / irreversible** risk — intervention or human execution beats silent autonomy regardless of merge stats.

**Do not** intervene just to “show involvement”; intervened PRs merge more on average, but **loop count** after intervention is not a strong merge predictor.

### When to stop after N rounds (design hint: median **2** loops)

Treat **2** Human–AI loops as a **planning hint** from Copilot data, **not** a hard cap.

- [ ] After **round 1:** if the next agent trajectory is **not** shorter / more focused (paper’s typical post–first-intervention drop absent), escalate: narrower instruction or change intervention *type* (delegate vs human commit).
- [ ] After **round 2 (median):** if requirements are still misunderstood or the same failure repeats, **stop delegating** — human implements, split issue, or abandon; log `hand_holding_exhausted`.
- [ ] **>2 loops:** allowed for hard tasks, but Checker should require **written rationale** and outcome tag; paper shows tail up to 25 loops with hand-holding patterns in qual examples.

### Checker pass (each intervention)

1. [ ] Is this the **smallest** feedback that completes one focused sub-task?
2. [ ] Are we repeating the **same** instruction (risk of repeated loops)?
3. [ ] Should a **human commit** replace another agent trajectory (paper: developers sometimes commit instead of re-assigning)?
4. [ ] Update **log row** below and open-PR board if outcome still `open``past timebox.

---

## Intervention log (Origin / CloudAgent PRs)

Copy rows per PR lifecycle. `round#` = Human–AI loop index (0 = initial trajectory only, no intervention yet).

| ticket/PR id | agent id | intervened? (Y/N) | round# | reason | outcome (merged/open/abandoned) | notes |
|--------------|---------|-------------------|--------|--------|----------------------------------|--------|
| *(fill)* | *(fill)* | | | | | |

### Example JSON (schema sketch only — not AIDev / HF export)

```json
{
  "ticket_pr_id": "origin/playground#42",
  "agent_id": "cloud-agent-bcId-or-run-url",
  "intervened": true,
  "round": 1,
  "reason": "ci_fail_tests|spec_clarify|wrong_scope|security|other",
  "outcome": "open",
  "notes": "First @-style redirect; expect shorter follow-up trajectory per 2610.32313"
}
```

---

## First log row (2026-11-03 Morning Brief run)

| ticket/PR id | agent id | intervened? (Y/N) | round# | reason | outcome (merged/open/abandoned) | notes |
|--------------|----------|-------------------|--------|--------|----------------------------------|--------|
| ``mb-2026-11-03-copilot-trajectories` | *(Smith: cloud run id)* | N | 0 | — | open | Builder markdown under `experiments/2026-11-03/`; no Checker step-in during initial agent trajectory |

---

## Out of scope (explicit)

- No DSH / Feishu / SQLite / daemon / headcount changes.
- No live GitHub Copilot API or session scraping in playground.
- No download or local load of **AIDev-2.7M** (HF); cite [AIDev](https://huggingface.co/datasets) / paper data pointer only.
- No new bots — intervention labels apply to existing Ork / Checker / CloudAgent workflow.

----

## References

- Paper: [arXiv:2610.32313](https://arxiv.org/abs/2610.32313)
- Partial code/data context: **AIDev v4 (2.7M-PR release)** — PR metadata and events; paper adds **Copilot session lifecycle JSON** encoding pipeline (Listing 1–2 in paper).

---

## Status

- [x] Planning (Morning Brief sketch)
- [x] In Progress (checklist + blank log + example row for today)
- [ ] Complete (Smith fills agent id + outcome at merge gate)
- [ ] On Hold
