# C-BASE — contract quotient delegation (Soft design note)

**날짜**: 2026-11-04  
**Paper (Top — existence + abstract)**: [Contract-Based Agentic Systems Engineering: Delegation as Quotient for Assured System Design](https://arxiv.org/abs/2610.33349) (Damera, Matheu, Baras; arXiv:2610.33349)

**Code**: **NONE** in playground — markdown design note only. **Authors’ Data Availability ([2610.33349](https://arxiv.org/abs/2610.33349)):** the SysML v2 model, the **contract kernel**, and the **campaign records** **will be made available on publication** — i.e. **not released yet** (no public C-BASE artifact URL to clone today). The paper still describes a JAX contract kernel and SysML v2 + STL pipeline; that implementation stays **Soft UNVERIFIED** here until a post-publication drop is verified. Do **not** treat unrelated “contract agent” GitHub repos as C-BASE; do **not** pin [SEIL-ISR/ros2-sysmlv2](https://github.com/SEIL-ISR/ros2-sysmlv2) (paper-related ROS mapping) as **Top** C-BASE code — citation context only.

## Top / Soft (honest tiers)

| Layer | This session |
|-------|----------------|
| **Top** | Paper exists at [2610.33349](https://arxiv.org/abs/2610.33349). Public abstract: a prompt-local component can satisfy its task and **still break the system** because neighbour **assumptions** are omitted; the handover artifact should be **computed** (contract **quotient**), not prose-only “mission” text; SysML v2 requirements as assume/guarantee contracts; STL closed under quotient; warehouse-robot case study compares quotient-derived vs mission-only vs natural-language delegation (live episode scoring). |
| **Soft (Team OS map)** | Map orchestrator → quotient **work order**, design agent → Smith implementation, verification → Checker — **design memo only**, not verified against authors’ kernel. |
| **Soft UNVERIFIED (runtime)** | **JAX contract kernel + campaign data: on publication / not released yet** (Data Availability). Quotient computation, Syside tooling, sim harness — **not cloned or run** in playground. [ros2-sysmlv2](https://github.com/SEIL-ISR/ros2-sysmlv2) and CHASE / generic “contract coding” repos — **not** C-BASE Top pins; at most Soft related-work citations. |

Playground **does not** reproduce warehouse-robot episodes, STL robustness scoring, or quotient algebra this turn.

---

## C-BASE pipeline → Team OS (Ork → Smith → Checker)

Paper Figure 1 (orchestrator → design agent → verification → integration) mapped to Team OS roles ([CONTRIBUTING.md](../../CONTRIBUTING.md)):

| C-BASE stage (paper) | Ork | Smith | Checker |
|----------------------|-----|-------|---------|
| **Architecture / system contract** | Holds **system requirement** sketch, fixed-neighbour contracts (Checker, CI, forge head, sibling PR slots), **delegation boundary** | — | Reads **`relied_on`** SHAs — not Ork narrative |
| **Quotient / work order** | Computes (offline) **weakest sound** requirement: **preservation obligations** = fixed components’ **assumptions** on the delegate | Receives **`work_order`** = quotient-derived spec + pointers — **not** mission-only prompt when integration-aware | Checks Smith deliverable against **quotient sketch**, not “tests green in isolation” |
| **Design agent (LLM)** | Does not implement; may revise **work order** when neighbour contracts change (paper §6.6 intuition) | Writes code/docs inside **`allowed_write_scopes`** | Independent replay |
| **Unit harness + stand-ins** | Policy: mock neighbours **hide** assumption breaks — Ork logs **`harness_kind`** | May pass local tests | **`mock_neighbors=true`** → **downgrade** integration confidence |
| **Live verification / STL margin** | Schedules evidence collection | Supplies **`log_path`**, episode ids ([01](./01-agentbaton-failure-escalate-handoff.md)) | **`certified_complete`** only when live/system contract satisfied — prefix attribution rules (paper §3.4) are **Soft** here |
| **Integration accept** | Opens PR / handoff when done-when table met | Submits **`handoff_artifact`** | Forge head + conflict stance; **mission-only PASS ≠ system sound** |

### Mission-only vs quotient (Team OS stance)

1. **Mission-only brief** (“add Soft note #34, open PR”) is analogous to paper **mission-only requirement** — can succeed locally while violating a **neighbour assumption** (e.g. renumber reserved `#8–#32`, edit PR #10, merge without Checker).
2. **Preservation obligations (Soft)** — examples for playground: **do not touch Origin PR #10**; keep README rows **#1–#7**; filename **`34-*`** not `08-*`; conflict-free vs **`main` tip**; Soft/Top honesty in **`relied_on`** footer.
3. **Checker** treats **orchestration “done”** and **coordinator PASS** as claims — align with Orchestra theme sibling ([#33](./33-orchestra-theme-role-contract-overlap-design-note.md) on open Origin PR #44) and Agent Role Contracts (#32 on PR #43): **PASS ≠ execution permission**.

**Cross-links (markdown only):**

- [33-orchestra-theme-role-contract-overlap-design-note.md](./33-orchestra-theme-role-contract-overlap-design-note.md) — **Soft KEEP** coordinator vs authority; C-BASE is the **integration-aware work order** complement (sibling on PR #44 until merged).
- [01](./01-agentbaton-failure-escalate-handoff.md) — **`handoff_artifact`** pointers, not transcript dumps.
- [04](./04-impassebench-escalate-to-human-ticket-schema.md) — **`escalate_to_human`** when environment impasse, not missing quotient field.
- [06](./06-care-escalate-verified-progress-checklist.md) — verified-progress memory vs local test PASS.
- **Origin PR #10** — **do not edit** (AgentBaton / trajectory columns).

---

## Sample JSON row (delegation episode — checklist sketch)

Append **one object per delegation** (Ork issues work order → Smith completes → Checker verdict). **Log only** — no C-BASE kernel.

```json
{
  "label": "example",
  "run_id": "ca-run-cbase-34a1",
  "system_contract_sketch": "Add experiments/2026-11-04 #34 Soft note; Origin PR open; no merge",
  "work_order_kind": "quotient_sketch",
  "preservation_obligations": [
    "do_not_edit_origin_pr_10",
    "readme_keep_rows_1_7",
    "filename_prefix_34_not_08",
    "conflict_free_vs_main_tip"
  ],
  "mission_only_fallback": false,
  "harness_kind": "markdown_only",
  "mock_neighbors": true,
  "smith_slot": "smith-docs-34a1",
  "handoff_artifact": {
    "workspace_pointer": "coevolution-lab/playground@cursor/c-base-soft-design-note-16e6",
    "log_path": "origin/pr/checks/log (pointer only)"
  },
  "checker_stance": "unproven",
  "integration_sound": null,
  "relied_on": {
    "main_tip_sha": "a3d544105a19e325dbbb2b5d7e2c5edfcb156098",
    "paper": "https://arxiv.org/abs/2610.33349",
    "tier_paper_abstract": "Top",
    "tier_team_os_map": "Soft",
    "tier_cbase_runtime": "Soft UNVERIFIED",
    "cbase_code_release": "on_publication_not_yet_released"
  },
  "notes": "Fictional demo row; live Checker waits for PR URL + head SHA"
}
```

### Column glossary (if flattened to table)

| Column | Type | Definition |
|--------|------|------------|
| `work_order_kind` | enum | `quotient_sketch` \| `mission_only` \| `natural_language` \| `unknown` |
| `preservation_obligations` | string[] | Neighbour assumptions Smith must not break (playground policy ids) |
| `mock_neighbors` | bool | True when CI/docs checks omit fixed-component coupling |
| `integration_sound` | bool \| null | Checker: composes with system contract — `null` until replay |
| `relied_on` | object | SHAs + tier tags for audit |

---

## Soft park (do not implement in wave8)

| Topic | Pointer | Intent |
|-------|---------|--------|
| **SpecGate** | [thanhtung2693/specgate](https://github.com/thanhtung2693/specgate) | **Pin-only** if a future turn needs spec-gate overlap with declaration preflight (#32) — **skip** when ambiguous vs ARC PASS semantics. |
| **C-BASE runtime** | [2610.33349](https://arxiv.org/abs/2610.33349) | **Parked** — Data Availability: artifacts **on publication** (not released yet). Future turn may verify license + runnable demo; **no Soft→Top** in this PR. |
| **Orchestra runnable** | Sibling [#33](./33-orchestra-theme-role-contract-overlap-design-note.md) | Remains theme-only on PR #44 — orthogonal to quotient work orders. |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- JAX contract kernel, SysML v2 editor automation, warehouse sim replay  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or open sibling sketches **#8–#32** (reserved on Origin PR #19–#43 branches)  
- **Origin PR #10** — **leave PR #10 alone**  

---

## Status

- [x] Planning (C-BASE **Soft** quotient-delegation sketch)  
- [ ] In Progress (no C-BASE runtime)  
- [ ] Complete  

**Relied on:** `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (`main` tip at branch); [2610.33349](https://arxiv.org/abs/2610.33349) abstract — **Top**; Data Availability (“on publication”) — **Top** (authors’ statement, not a live URL); Team OS mapping + JSON checklist — **Soft**; JAX kernel / campaign records / C-BASE runtime — **Soft UNVERIFIED** (**on publication / not released yet**). **Origin PR #10** untouched.

**Next step:** After publication release, verify artifacts before any clone/demo row (still subject to Checker tier policy — **no automatic Soft→Top**); until then, pair **`work_order_kind=quotient_sketch`** with Checker **`mock_neighbors` downgrade** and Orchestra #33 **`pass_treated_as_authority=false`** when wired.
