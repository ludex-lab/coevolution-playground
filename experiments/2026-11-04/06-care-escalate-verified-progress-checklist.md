# CARE — Know When to Escalate (verified-progress handoff checklist)

**날짜**: 2026-11-04  
**Paper**: [Know When to Escalate: Critic-Guided Adaptive Execution for Cloud–Local Embodied Agents](https://arxiv.org/abs/2610.30587) (Zhang et al., arXiv:2610.30587)

**Code**: **NONE** — markdown observation / handoff checklist only; no CARE critic, speculative cloud launch, or embodied harness in playground.

## Paper pointer (citation only; no runs today)

From the public abstract and §III–§IV on [2610.30587](https://arxiv.org/abs/2610.30587):

- **Problem:** Cloud executors are strong but slow between actions; local executors are fast but error-prone. Fixed planner–executor roles and **stateless per-request routing** do not match trajectories where difficulty shifts mid-task.
- **CARE:** A **critic** scores whether **local** execution should continue; escalation is a **stateful control transfer** (cloud holds control through recovery), not a one-step router flip.
- **Dual thresholds (hysteresis):** Let \(c_t\) be critic confidence for retaining/returning to local control (Eq. 3). Control state \(z_t \in \{L,C\}\) updates with **asymmetric** thresholds \(\theta_{\mathrm{esc}}\) and \(\theta_{\mathrm{ret}}\) satisfying \(\theta_{\mathrm{esc}} < \theta_{\mathrm{ret}}\) (Eq. 4): escalate local→cloud when \(z_{t-1}=L\) and \(c_t \leq \theta_{\mathrm{esc}}\); return cloud→local when \(z_{t-1}=C\) and \(c_t \geq \theta_{\mathrm{ret}}\); otherwise hold \(z_{t-1}\). Cloud control **persists** until return threshold is met—avoiding step-wise ping-pong during multi-step recovery.
- **Shared handoff memory \(M_t\):** Decomposed into recent **observation–action–outcome** window \(M_t^{\mathrm{obs}}\) and episode-level **verified progress** (plus persistent failures) in \(M_t^{\mathrm{epi}}\). Only state supported by **observation or public execution feedback** is promoted to \(M_t^{\mathrm{epi}}\); memory is **not reset** at executor handoff—only control state \(z_t\) changes (§III-C).
- **Reported results (paper numbers only):** Task success **+6.3–18.3** percentage points vs the strongest evaluated **collaboration** baseline; median time-between-action latency **−28.8–82.6%** vs Cloud-only while approaching/exceeding Cloud-only success (abstract). Habitat memory ablation at matched transfer states (Table II, \(N=20\)): full memory **100%** success vs **25%** with memory removed; episodic-only **90%**, observation-only **75%**.

Playground **does not** re-run Habitat / ALFRED / TEACh or fit \(\theta_{\mathrm{esc}}, \theta_{\mathrm{ret}}\).

---

## Map to Team OS (Impasse ticket + park; no CARE runtime)

| CARE concept | Team OS analog (markdown only) |
|--------------|--------------------------------|
| Local executor \(\pi_L\) | Default / efficient agent tier (fast loop) |
| Cloud executor \(\pi_C\) | Stronger model tier after **model** escalate ([01](./01-agentbaton-failure-escalate-handoff.md)) or cloud-capable run |
| Critic \(c_t \leq \theta_{\mathrm{esc}}\) | Policy signal to **stop local retries** and transfer control (repeat `failure-id`, impasse evidence, or manual Ork rule)—**not** a deployed critic in this repo |
| Persistent cloud until \(c_t \geq \theta_{\mathrm{ret}}\) | Stronger tier stays **in control** until recovery criteria met; avoid hand-back after one green check |
| \(M_t^{\mathrm{obs}}\) | Recent tool outcomes in ticket `evidence` + bounded `attempts` list ([04](./04-impassebench-escalate-to-human-ticket-schema.md)) |
| \(M_t^{\mathrm{epi}}\) **verified progress** | Explicit **`verified_progress`** bullets: subgoals **confirmed by logs/artifacts**, not model narrative |
| Human **`escalate_to_human`** | Impasse ticket row + **park** (below)—ends run; distinct from model-only CARE escalate |

### ImpasseBench ticket alignment ([04](./04-impassebench-escalate-to-human-ticket-schema.md))

When filing **`escalate_to_human`**, populate the six paper blocks as in [04](./04-impassebench-escalate-to-human-ticket-schema.md). CARE’s handoff memory motivates **extra Team OS emphasis** on what is already **verified**:

| CARE memory slice | Escalate ticket / handoff field |
|-------------------|----------------------------------|
| \(M_t^{\mathrm{epi}}\) verified progress | **`verified_progress`** (checklist column below): completed steps backed by command output, green tests, or merged edits |
| Persistent failures in \(M_t^{\mathrm{epi}}\) | `blocker` + `evidence` (cited log segments via `log_path`) |
| \(M_t^{\mathrm{obs}}\) recent window | `attempts` (bounded) + tail of `evidence` |
| Verification-limited but useful work | Paper’s **`verified=false`** completion path in [04](./04-impassebench-escalate-to-human-ticket-schema.md)—patch saved, verification gap documented; **not** empty handoff |

Always attach mechanical **`handoff_artifact`** (`workspace_pointer` + `log_path`) per [01](./01-agentbaton-failure-escalate-handoff.md)—continuity without transcript dump.

### Park / await (#10 pattern)

**Reference path:** `experiments/2026-11-03/02-agentbaton-park-await-cody-fields.md` — **not on `main`** at branch time (`e9b18ae`); described on open **PR #10** (`cursor/copilot-trajectories-intervention-5eae`).

Human **park** after Impasse **`escalate_to_human`**: run **awaits** `resume_when` before any executor (local or cloud) resumes—analogous to holding cloud control until \(\theta_{\mathrm{ret}}\), but the gate is **human/infra**, not critic \(c_t\). **Do not** fill Cody trajectory columns (`Cody intervened?`, `round#`, outcome enums)—PR #10 only; see [04](./04-impassebench-escalate-to-human-ticket-schema.md).

---

## Observation checklist (control transfer + verified progress)

Log **one row per control transfer** (model escalate/de-escalate) or per **human park** ticket. **Log only**—no automated critic or threshold tuning.

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** (fictional demo row) |
| `run_id` | id | Team OS / cloud-agent run id |
| `control_before` | enum | `local` \| `cloud` \| `parked_human` |
| `control_after` | enum | `local` \| `cloud` \| `parked_human` |
| `transfer_trigger` | enum | `critic_esc` \| `critic_ret` \| `failure_id_escalate` \| `impasse_ticket` \| `policy_hold` |
| `critic_confidence_sketch` | optional | If logged: relative local-continuation score analogous to \(c_t\) (Ork note only; **no** \(\theta\) values invented here) |
| `verified_progress` | text | Bullets of **observation-backed** completed subgoals (CARE \(M_t^{\mathrm{epi}}\) analog)—tests passed, files written, permissions confirmed |
| `recent_failures_window` | text | Last N tool outcomes (CARE \(M_t^{\mathrm{obs}}\) analog)—exit codes, repeated actions |
| `blocker` | text | Impasse **`blocker`** when `transfer_trigger=impasse_ticket` |
| `resume_when` | text | Human park gate when `control_after=parked_human` |
| `handoff_artifact` | struct | `workspace_pointer` + `log_path` only |

### Example row (**example** — fictional, plausible)

| label | run_id | control_before | control_after | transfer_trigger | critic_confidence_sketch | verified_progress | recent_failures_window | blocker | resume_when | handoff_artifact |
|-------|--------|----------------|---------------|------------------|--------------------------|-------------------|------------------------|---------|-------------|------------------|
| **example** | `ca-run-care-sketch-7f2` | `local` | `cloud` | `failure_id_escalate` | (Ork note: “local continuation low after stall”) | `pytest tests/test_api.py::test_health` **passed**; OpenAPI stub committed on branch | same test **failed** twice with `ConnectionRefusedError`; third identical retry | — | — | `workspace_pointer`: repo `playground`, branch `cursor/api-health-7f2`, SHA `a1b2c3d`; `log_path`: `/tmp/cloud-agent-run-7f2.log` |

---

## Procedure (Ork sketch — dual threshold **idea**, not deployed)

1. **Maintain handoff state** — After each tool/action outcome, update **`verified_progress`** only when public feedback supports it; append failures to the recent window (CARE memory update rule; no extra model call in paper).
2. **Assess continuation** — Before another local retry loop, ask whether local tier should hold control (critic analog: Ork/heuristic, or `failure-id` streak from [01](./01-agentbaton-failure-escalate-handoff.md)).
3. **Escalate with hysteresis** — On escalate, switch to stronger tier and **stay** until recovery is **verified** in \(M^{\mathrm{epi}}\)-style fields—not a single-token success (CARE \(\theta_{\mathrm{ret}}\) idea).
4. **Human impasse** — If blocker is outside repo/sandbox, file [04](./04-impassebench-escalate-to-human-ticket-schema.md) ticket + **park**; attach `handoff_artifact` including **`verified_progress`** so human/cloud resume skips redoing proven work.
5. **Return local** — When strong tier finishes recovery and verification gates pass, hand back to default tier with the **same** memory fields (no transcript rehydration).

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- New bots, Slack wiring, CARE **critic model**, speculative async \(\pi_C\), or embodied benchmarks  
- Cody **`intervened?` / `round#` / outcome** columns (PR #10 only)  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[04](./04-impassebench-escalate-to-human-ticket-schema.md) or a future **#5** ParallACT sketch (open PR #16)—this file is **#6** only  
- Runtime \(\theta_{\mathrm{esc}}, \theta_{\mathrm{ret}}\) calibration or CARE harness monitors  

---

## Status

- [x] Planning (CARE → Team OS checklist sketch)
- [ ] In Progress (no runtime wiring)
- [ ] Complete

**Relied on (SHAs):** `e9b18ae` (main: ImpasseBench #4 / PR #15); ticket field prose cross-check [04](./04-impassebench-escalate-to-human-ticket-schema.md) at same tip; park path note per PR #10 (file absent on main).

**Next step:** If PR #10 merges, cross-link park **await** columns in `experiments/2026-11-03/02-agentbaton-park-await-cody-fields.md`; if PR #16 lands ParallACT **#5**, keep README ordering #5 then #6.
