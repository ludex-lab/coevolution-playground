# Theory of Scene — symmetry trap & shared scene division (Soft design note)

**날짜**: 2026-11-04  
**Paper (Soft KEEP — abstract / preprint only)**: [Theory of Scene: Breaking the Symmetry Trap in Multi-Agent LLM Coordination](https://arxiv.org/abs/2609.32939) (Yuan et al., arXiv:2609.32939; submitted 26 Sep 2026)

**Code**: **NONE** — markdown design note only; **no-code** paper (training-free reasoning schema at inference). Playground **does not** run DivvyBench, GovSim, Overcooked, or ship a ToS prompt harness. **No GitHub Top pin**, no vendored artifact, no repo claim for this work.

## Tier policy (this note)

| Layer | Stance |
|-------|--------|
| **Soft KEEP** | Paper + public abstract on [2609.32939](https://arxiv.org/abs/2609.32939): homogeneous LLM agents without communication can fall into the **symmetry trap** (collide where targets must split, diverge where they must converge); **Theory of Mind (ToM)** cannot escape when agents are homogeneous; **Theory of Scene (ToS)** is a **training-free** schema where each agent reads **public role** + shared **task context** via **role gating** and **task coupling** to derive the same division of labor. Abstract-reported gains vs ToM on DivvyBench, GovSim, and Overcooked — **cite only**, not reproduced here. |
| **Soft (Team OS map)** | Treat **shared scene** (board row, mandate scope, forge pointers, reserved README slots) + **public role** (Ork / Smith / Checker) as a light analogy for deriving division of labor without chat-level ToM — **design memo only**. |
| **Soft UNVERIFIED** | Full paper proofs, appendix algorithms, exact prompt templates, DivvyBench/GovSim/Overcooked replay, baseline code paths — **not read or run** in playground unless a future pass says otherwise. **Soft→Top forbidden** for this arXiv id (no verified runnable drop pinned). |

Playground **does not** implement ToS reasoning fields, role-gating prompts, or multi-agent simulators this turn.

---

## Paper pointer (Soft KEEP — abstract only)

From the public abstract on [2609.32939](https://arxiv.org/abs/2609.32939) (Yuan, Fang, Wang, Brinton):

| Idea (abstract) | Sketch |
|-----------------|--------|
| **Symmetry trap** | Concurrent homogeneous agents **without communication** collide on targets that must be **divided** and split on targets that require **joint** action. |
| **ToM limit** | Homogeneous agents that predict one another share the same prediction and **respond identically** — trap persists. |
| **ToS** | Each agent reads **public role** (the only inter-agent difference) and **task context** all observe; **role gating** + **task coupling** infer converge vs divide vs staged work. |
| **Evaluation (cite only)** | DivvyBench (introduced in paper), GovSim, Overcooked — abstract reports ToS vs ToM and six baselines; playground **does not** re-run trials. |

**Soft UNVERIFIED beyond abstract:** Mechanism details in §4, DivvyBench construction, decoding config (e.g. backbone named in full paper), and non-abstract tables — not audited in this note.

---

## ToS scene reading → Team OS (Ork → Smith → Checker) — light touch

Team OS already separates agents by **role** and a **shared scene** outside chat (board pointer ID, mandate scope, forge head, reserved experiment index rows). ToS is a **Soft analogy**, not a claim that playground runs ToS prompts.

| ToS signal (paper) | Team OS analog (observation / policy sketch) |
|--------------------|-----------------------------------------------|
| **Public role** | Fixed slot labels — **Ork** (brief + boundaries), **Smith** (implement), **Checker** (independent verdict) — not interchangeable “another LLM thread.” |
| **Task context / scene** | Shared **`relied_on`** + board row + `main` tip policy ([02](../2026-11-02/02-sbus-version-check-board-rule.md)) — same observable scene, not private ToM guesses about teammate intent. |
| **Role gating** | Ork sets **preservation obligations** (e.g. do not edit PR #10, keep README `#1–#7`, filename prefix `#41`) — ownership already divided vs overlapping work inferred from scene. |
| **Task coupling** | Mixed ticket: some subtasks **competitive** (one Smith PR slot) vs **cooperative** (Checker + forge head must agree) within one sprint — division changes **per target**, not one static “planner forever” prompt. |
| **ToM failure mode** | Homogeneous Cloud Agents guessing each other’s next file edit without scene → duplicate README rows or colliding `#08` filenames — **symmetry-trap sketch**, not a formal proof. |
| **ToS-style cure (Soft)** | Read **scene + role** first → same division (who owns `#41`, who must not touch `#10`) before parallel writes — aligns with pointer handoffs ([01](./01-agentbaton-failure-escalate-handoff.md)), not transcript prediction. |

**Ork → Smith:** Brief includes **scene snapshot** (tip SHA, reserved index gaps `#36–#40`, conflict stance) + **role-bound scope** — not “predict what Smith will do.”  
**Smith → Checker:** Handback cites **`relied_on`** + artifact pointers; Checker replays forge/board evidence, not Smith’s model of Ork.  
**Checker:** Treats parallel **PASS** claims as insufficient when scene requires **convergence** (one head SHA, one open PR URL) — light echo of cooperative targets.

**Cross-links (markdown only):**

- [33-orchestra-theme-role-contract-overlap-design-note.md](./33-orchestra-theme-role-contract-overlap-design-note.md) — role vs authority (sibling on open PR #44 — **file not on `main` until merged**).
- [34-c-base-contract-quotient-delegation-design-note.md](./34-c-base-contract-quotient-delegation-design-note.md) — integration-aware **work order** complement (sibling on open PR — **Soft**).
- [07](./07-pcp-shared-human-ask-queue-checklist.md) — shared-attention queue when scene does not fix division.
- **Origin PR #10** — **do not edit**.

---

## Sample JSON observation row (scene division sketch)

Log **one row per parallel delegation episode** where agents might **collide** on the same artifact without reading shared scene. **Log only** — no ToS runtime.

```json
{
  "label": "example",
  "run_id": "ca-run-tos-41a1",
  "scene_snapshot": {
    "main_tip_sha": "a3d544105a19e325dbbb2b5d7e2c5edfcb156098",
    "reserved_readme_rows": ["36", "37", "38", "39", "40"],
    "assigned_row": "41",
    "forbidden_targets": ["origin_pr_10", "experiments/2026-11-03"]
  },
  "public_roles": ["ork", "smith", "checker"],
  "coordination_schema_sketch": "theory_of_scene_analog",
  "tom_collision_sketch": false,
  "symmetry_trap_sketch": "duplicate_readme_row_without_scene",
  "role_gating_sketch": "filename_prefix_41_only",
  "task_coupling_sketch": "cooperative_on_forge_head_sha",
  "handoff_artifact": {
    "workspace_pointer": "coevolution-lab/playground@cursor/theory-of-scene-soft-design-note-d2a5",
    "log_path": "origin/pr/checks (pointer only)"
  },
  "checker_stance": "unproven",
  "relied_on": {
    "paper": "https://arxiv.org/abs/2609.32939",
    "tier_paper_abstract": "Soft KEEP",
    "tier_team_os_map": "Soft",
    "tier_tos_runtime": "Soft UNVERIFIED",
    "soft_to_top": "forbidden"
  },
  "notes": "Fictional demo row; no DivvyBench/GovSim/Overcooked execution"
}
```

---

## Soft park (do not implement in wave9)

| Topic | Pointer | Intent |
|-------|---------|--------|
| **ToS prompt harness** | [2609.32939](https://arxiv.org/abs/2609.32939) | **Parked** — no training-free schema wired in playground; future turn needs explicit Soft tier review; **no Soft→Top**. |
| **DivvyBench / sim replay** | Paper benchmark | **Parked** — no simulator install; abstract numbers **Soft KEEP cite only**. |
| **ToM baselines in Team OS** | — | Do not replace board/`relied_on` with teammate-intent prediction as primary coordination. |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- DivvyBench, GovSim, Overcooked runs, Qwen backbone serving, or ToS/ToM A/B harness  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md), **`experiments/2026-11-03/`**, or open sibling sketches **#8–#40** (reserved on concurrent Origin PR branches)  
- **Origin PR #10** — **leave PR #10 alone**  

---

## Status

- [x] Planning (Theory of Scene **Soft KEEP** sketch)  
- [ ] In Progress (no ToS runtime)  
- [ ] Complete  

**Relied on:** `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (`main` tip at branch); [2609.32939](https://arxiv.org/abs/2609.32939) abstract — **Soft KEEP**; Team OS scene/role analogy + JSON checklist — **Soft**; paper implementation / benchmarks — **Soft UNVERIFIED**. **Origin PR #10** untouched. **Soft→Top forbidden** for this paper id.

**Next step:** When parallel wave9 agents land, compare README collisions offline — append observation rows; no merge of this doc required for ops.
