# BRIDGE — selective handoff frontier repair (Soft day sketch)

**날짜**: 2026-11-04  
**Paper**: [BRIDGE: Selective Boundary Repair with Dependency Graph Evidence in Multi-Agent Systems](https://arxiv.org/abs/2610.17805) (Su et al., arXiv:2610.17805)

**Code**: **NONE** — no public GitHub URL verified for this sprint; **Soft UNVERIFIED** method borrow from paper prose only. Playground does **not** install BRIDGE, HandoffProbe, provenance-graph controllers, or SILO-BENCH / TeamBench / MAST replays.

## Paper pointer (citation only; no runs today)

From the public abstract and §3–§5 on [2610.17805](https://arxiv.org/abs/2610.17805):

- **Problem:** Multi-agent workflows fail at **inter-agent handoffs**—context dropped, misrouted, or ignored—while each agent’s local output still looks plausible.
- **BRIDGE (runtime sketch):** Compile **public** interaction traces into a **provenance graph**; surface **frontiers** (unmet contract dependencies); apply **selective** repairs only when an empirical **utility gate** expects net benefit; **verify** postconditions before committing a repaired message, else **rollback** to native handoff \(m^{\mathrm{nat}}\).
- **HandoffProbe (offline):** Counterfactual handoff perturbations on historical traces to calibrate intervention priors—playground cites the idea only; **no** paired-rollout harness here.
- **Reported gains (paper numbers only):** Up to **+12.3** pp task success on SILO-BENCH and **+11.1** on TeamBench; **69.8%** F1 on **562** handoff-relevant MAST traces (single pass, GPT-5.6-Terra in paper); as little as **~2.0%** marginal token overhead on one backbone; HandoffProbe analysis: **87.5%** of **unselected** repairs waste tokens without improving success—motivation for **not** intervening on every gap.

Playground **does not** reproduce graph update, eligibility Eq. (2), utility Eq. (5–6), or verify-before-commit Eq. (7).

---

## Map to Team OS (markdown only)

| BRIDGE idea | Team OS analog (this sketch) |
|-------------|-------------------------------|
| Execution contract \((O,R,\mathcal{V})\) | Ork delegation + caps + **`handoff_artifact`** discipline ([01](./01-agentbaton-failure-escalate-handoff.md)); optional CoworkOS **`expected_evidence`** ([09](./09-coworkos-delegation-evidence-contract-day-sketch.md) when landed; PR #20) |
| Provenance graph from public trace | Forge + CI + **`log_path`** segments + board pointers—**not** private Smith scratch state |
| Frontier \(\mathcal{F}=\mathcal{F}_{\mathrm{use}}\cup\mathcal{F}_{\mathrm{abs}}\cup\mathcal{F}_{\mathrm{scope}}\) | Unconsumed delivery, missing evidence, routing mismatch at Smith→Checker handback |
| Native message \(m^{\mathrm{nat}}\) | Smith handback as submitted; gate failure ⇒ **unchanged forward**, not forced re-prompt |
| ASK primitive | Human/JJ or upstream **ask** ([07](./07-pcp-shared-human-ask-queue-checklist.md) queue) or **`ask_main`** wait ([09](./09-coworkos-delegation-evidence-contract-day-sketch.md))—distinct from model **escalate** ([01](./01-agentbaton-failure-escalate-handoff.md)) |
| VERIFY primitive | Checker **`proven`/`unproven`/`failed`** on claims ([12](./12-pcm-proof-carrying-handoff-day-sketch.md) when landed; PR #23)—offline, not LLM judge in paper’s oracle sense |
| Park / impasse | Environment blocker ticket ([04](./04-impassebench-escalate-to-human-ticket-schema.md))—**not** every graph gap warrants BRIDGE-style repair |

Mechanical handoff on main: **`handoff_artifact`** = `workspace_pointer` + `log_path` only ([01](./01-agentbaton-failure-escalate-handoff.md)).

---

## 1) `contract.yaml` — facts / roles sketch

File: [18-bridge-handoff-frontier-contract.yaml](./18-bridge-handoff-frontier-contract.yaml) (YAML **sketch** for lint/discussion; **not** loaded by any runtime).

| BRIDGE symbol | Sketch field | Team OS reading |
|---------------|--------------|-----------------|
| \(O\) obligations | `obligations[]` with `id`, `desc`, `owner`, `dest` | Required facts at handoff (scope, pointer, artifact, optional test claim) |
| \(R\) roles | `roles` map | `ork` / `smith` / `checker` / optional `jj` as `human_dest` |
| \(\mathcal{V}\) constraints | `constraints[]` | No transcript handoff; public trace only; verify-before-commit; **selective gate** |
| \(q=(\mathrm{id},\text{desc},\mathrm{owner})\) | each obligation row | Stable **`fact.*`** ids for log columns and frontier typing |

**Offline lint (Checker memo):** For each handback, every obligation with `dest=checker` should appear in delivered facts **or** appear on an explicit frontier row with a planned repair primitive—do not silently drop `fact.handoff_artifact`.

---

## 2) Frontier gap types → repair primitives

Paper Table 1 (domain-agnostic actions). Log **`frontier_class`** and **`repair_primitive`** on observation rows only.

| Frontier class (Eq. 1 sketch) | Meaning | Typical Team OS trigger |
|------------------------------|---------|-------------------------|
| \(\mathcal{F}_{\mathrm{use}}\) | Delivered but **unconsumed** | Checker never saw cited SHA / claim id Smith mentioned |
| \(\mathcal{F}_{\mathrm{abs}}\) | **Missing evidence** in public trace | No `log_path` segment for asserted test success |
| \(\mathcal{F}_{\mathrm{scope}}\) | **Routing mismatch** | Fact produced for wrong role (Ork scope on Smith handback without `dest`) |

| Repair primitive | Prerequisite (paper) | Intended state change | Team OS action sketch |
|------------------|----------------------|------------------------|------------------------|
| **ASK** | Identified owner + valid query | Acquire target evidence from sender | JJ clarification or upstream ask—not blanket re-prompt |
| **INTEGRATE** | Evidence in recipient scope | Weave fact into outgoing handback | Smith amends handback packet with pointer refs |
| **VERIFY** | Declared contract constraint | Verification certificate on graph | Checker stamps claim verdict (PCM analog) |
| **DECOMPOSE** | Complex unmet obligation | Rewrite message using visible local sources | Split handback into scoped sub-rows + new `contract_version` |
| **RETRIEVE** | Accessible local/public state | Fetch missing context into scope | Repo search / `log_path` read—**ineligible** if fact exists only in private upstream state (paper: force **ASK**) |

---

## 3) Selective gate ≠ always intervene

**Design norm (from paper Algorithm 1):**

1. If frontier set \(\mathcal{F}_t=\emptyset\) → forward **`m_nat`** (no repair).
2. Eligible candidates must satisfy structural **`pre(a)`** (Eq. 2)—no speculative repair when prerequisites absent.
3. **Utility gate** \(\pi(a,f^*)=1\) requires positive expected utility, bounded harm rate, and minimum calibration support (Eq. 6)—else forward **`m_nat`**.
4. Even admitted repair **`a*`** commits only if **`Check(post(a*))`** passes (Eq. 7); else restore snapshot and release **`m_nat`**.

**Team OS reading:** Do **not** treat every missing bullet as mandate to re-run Smith, spam JJ, or auto-escalate model tier. Prefer:

- **Gate closed** → document frontier on observation row; ship native handback for human/Checker review.
- **Gate open** → one targeted primitive (often **INTEGRATE** or **VERIFY**, sometimes **ASK**).
- Contrast with always-on self-refinement / clarification baselines paper criticizes (side effects on valid trajectories).

**HandoffProbe prior (citation only):** Interventions help only when aligned with failure mode; **87.5%** of unselected repairs are wasted—supports **default = no intervention**.

---

## 4) Observation checklist (handoff frontier; log only)

Log **one row per diagnosed frontier** at Smith→Checker (or cross-agent) boundary. **No** automated graph compiler in playground.

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `run_id` | string | Cloud Agent / handback key |
| `handoff_id` | string | Stable id for this boundary event |
| `frontier_class` | enum | `use` \| `abs` \| `scope` \| `none_observed` |
| `fact_id` | string | Contract obligation id (e.g. `fact.handoff_artifact`) |
| `repair_primitive` | enum | `ASK` \| `INTEGRATE` \| `VERIFY` \| `DECOMPOSE` \| `RETRIEVE` \| `none` |
| `gate_decision` | enum | `admit_repair` \| `forward_native` \| `rollback_after_fail_check` |
| `utility_gate_sketch` | string | Human/Checker memo: why admit vs forward native (no HandoffProbe tables) |
| `post_check` | enum | `passed` \| `failed` \| `not_attempted` \| `n/a_native` |
| `native_preserved` | bool | True if downstream received **`m_nat`** after failed verify or empty admissible set |
| `contract_id` | string | Join to [contract.yaml](./18-bridge-handoff-frontier-contract.yaml) sketch |
| `notes` | string | Pointers only: SHAs, `log_path`, PR url—no transcript dump |

### Example row (**example** — fictional)

| label | run_id | handoff_id | frontier_class | fact_id | repair_primitive | gate_decision | utility_gate_sketch | post_check | native_preserved | notes |
|-------|--------|------------|----------------|---------|------------------|---------------|---------------------|------------|------------------|-------|
| **example** | `ca-bridge-sketch-18e1` | `hb-18e1-checker` | `abs` | `fact.tests_passed_claim` | `RETRIEVE` | `forward_native` | No attested log segment in public trace; RETRIEVE ineligible for private upstream only—gate closed per selective policy | `n/a_native` | true | Smith summary said “tests green”; Checker **`unproven`**; no auto re-prompt—PCM #12 analog when landed |

---

## relied_on (Soft UNVERIFIED)

| Source | Use in this sketch |
|--------|-------------------|
| Paper [arXiv:2610.17805](https://arxiv.org/abs/2610.17805) | Contract \((O,R,\mathcal{V})\), frontier Eq. (1), primitives Table 1, utility gate Eq. (6), verify-before-commit Eq. (7), reported benchmark numbers |
| Public GitHub | **None** — no verified repo URL for BRIDGE/HandoffProbe in playground; **do not** invent release links |

Cross-links cite sibling sketches on **`main`** or open PR branches by number only; merging those PRs is out of scope for this file.

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- BRIDGE / HandoffProbe **runtime**, provenance graph service, or MAST/SILO/TeamBench harness  
- Always-on clarification loops or unguided self-refinement as default handoff policy  
- Cody trajectory / intervention columns (open **PR #10** only—**do not** edit PR #10 body or park files)  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md)  

---

## Status

- [x] Planning (Soft sketch + contract.yaml facts/roles)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** On Smith→Checker handbacks, append frontier rows when a contract fact is missing, unconsumed, or misrouted; practice **forward native** when gate would stay closed—aggregate offline; no merge of this doc required for ops.
