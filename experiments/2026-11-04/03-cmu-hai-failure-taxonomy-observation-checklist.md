# CMU Human–Agent Interaction Failure taxonomy — Team OS / Ludex observation checklist

**날짜**: 2026-11-04  
**Paper**: [When AI Agents Act on Our Behalf: A Taxonomy of Human-Agent Interaction Failure](https://arxiv.org/abs/2611.00291) (Wang et al., arXiv:2611.00291)

**Code**: **NONE** — markdown observation checklist only; no runtime, bots, or API sweeps.

## Paper pointer (verified takeaways; no deployment prevalence claims)

Grounded in the public abstract, §3–§4, and Table 1 on arXiv ([2611.00291](https://arxiv.org/abs/2611.00291)):

- **Corpus:** 695 documented incidents (after screening) drawn from AIAAIC and the AI Incident Database; modes developed bottom-up with interaction stages adapted from Amershi et al. (2019)—**initially** folded into **during interaction**, leaving **three stages**: during interaction, when wrong, over time.
- **Unit:** A **human–agent interaction failure** is a breakdown between a person and a deployed agent that yields negative consequences for people using or encountering it.
- **Autonomy:** Incidents coded **low** vs **high** autonomy (user involved at each agent contribution vs agent leads between involvement points). The paper reports **453 (65.2%)** low and **242 (34.8%)** high in the analysis corpus—**corpus composition**, not an estimate of how often failures happen in the wild.
- **Central claim:** What users can **know, see, stop, and undo** when an agent fails depends on **deployment interaction configuration**, not the model alone. **All 12 modes appear at both autonomy bands**; rising autonomy changes the **form** each failure takes (Table 1 “What changes as autonomy rises”).
- **Counts per mode:** Figure 2 / section headings give **n/695** in the **documented record**; the authors explicitly warn these **do not estimate deployment frequency**. This checklist **does not** treat those ratios as Team OS failure rates.

**Evidence note:** Full paper PDF appendices were not re-coded here. Incident examples below are **paper citations**, not playground incidents.

---

## Twelve failure modes (mapped)

Modes are **not mutually exclusive** in the paper (one incident can carry multiple modes). Numeric **mode_id** matches Team OS log column; **R-primary** marks Ludex Village / Team OS **observation focus** (control, visibility, intervention, handoff, repair, delegated authority)—per sprint lab scope, not a label from the paper.

| mode_id | Stage | Failure mode | R-primary |
|--------:|-------|--------------|:---------:|
| 1 | During interaction | Unclear agent role — users not knowing they interact with AI or what role the agent plays | |
| 2 | During interaction | Unclear provenance — users cannot tell where information came from or whether it was verified | |
| 3 | During interaction | Limited visibility — users cannot tell what the agent is doing, has done, or plans next | **yes** |
| 4 | During interaction | Insufficient control — users cannot easily pause, redirect, or constrain the agent | **yes** |
| 5 | During interaction | Boundary violation — agent exceeds what the user understood they delegated | |
| 6 | When wrong | Failure goes undetected — error not noticed before it affects later actions or people | |
| 7 | When wrong | No timely intervention — failure visible but no meaningful window to stop it before effect | **yes** |
| 8 | When wrong | Intervention or handoff failure — stop, override, escalation, or human transfer does not restore control | **yes** |
| 9 | When wrong | No effective repair — users cannot undo, correct, or obtain meaningful remediation | **yes** |
| 10 | Over time | Accumulated behavioral drift — agent behavior drifts from intended role or current user intent | |
| 11 | Over time | Overextension of delegated authority — permissions granted for one purpose extend into broader activity | **yes** |
| 12 | Over time | Unhealthy emotional and cognitive dependency — reliance on agent for support, judgment, or tasks previously self-managed | |

**R-primary focus set:** modes **3, 4, 7, 8, 9, 11** — where Team OS (Ork → Smith → Checker) most needs **observable state**, **pause/stop**, **handoff**, and **forge-evidence repair**, without re-litigating role/provenance on every turn.

---

## Observation checklist (Team OS / Ludex Village)

Log **one row per observed interaction breakdown** (or per mode tagged on the same run). **Log only** in this sprint sketch—no automated reject gates.

| Column | Type | Definition |
|--------|------|------------|
| `run_id` | string | Cloud Agent / village run id, ticket id, or stable session key |
| `mode_id` | 1–12 | Row in table above |
| `stage` | enum | `during_interaction` \| `when_wrong` \| `over_time` |
| `autonomy_band` | enum | `low` \| `high` \| `unknown` — how much work ran between human involvement points **at failure time** |
| `actor` | enum | Who was in scope: `ork` \| `smith` \| `checker` \| `human_jj` \| `external` \| `agent` |
| `symptom` | string | What was visible (or missing) at failure time—**no transcript dump**; pointer to log path ok |
| `outcome` | enum | `caught_pre_effect` \| `harm_contained` \| `harm_spread` \| `unknown` |
| `notes` | string | Handoff artifact present? stop attempted? forge pointer stale? (free text) |

Optional cross-links (same row): `failure-id` from [01-agentbaton-failure-escalate-handoff.md](./01-agentbaton-failure-escalate-handoff.md) when the breakdown is a **repeatable** tool/CI signature—not required for modes 10–12.

### Example row (**example** — fictional, plausible)

| label | run_id | mode_id | stage | autonomy_band | actor | symptom | outcome | notes |
|-------|--------|---------|-------|---------------|-------|---------|---------|-------|
| **example** | `TEAMOS-run-7f3a` | 8 | when_wrong | high | checker | Smith posted `stop` in thread; Cloud Agent run continued pushing commits for ~4 min; no `handoff_artifact` on disk | harm_contained | Reverted branch; tagged intervention_or_handoff_failure; escalate policy out of scope today |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- New bots, Slack wiring, API sweeps  
- Treating paper **corpus counts** (e.g. n/695, low/high split) as **Team OS incident rates**  
- Editing [01-agentbaton-failure-escalate-handoff.md](./01-agentbaton-failure-escalate-handoff.md) or `02-four-bridges-*` bodies  

---

## Status

- [x] Planning (observation checklist sketch)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** During Ludex / Cloud Agent runs, append rows for R-primary modes when visibility, stop, handoff, repair, or authority creep is in doubt—aggregate offline; no merge of this doc required for ops.
