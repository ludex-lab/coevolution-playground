# A²-Failures — cross-boundary A2A taxonomy (Team OS / Ludex day-sketch)

**날짜**: 2026-11-04  
**Paper**: [Why Do Agent Teams Fail Across Boundaries? A Failure Taxonomy for Agent-to-Agent Systems with Private States](https://arxiv.org/abs/2610.19342) (Shekkizhar et al., arXiv:2610.19342)

**Code**: **NONE** — markdown taxonomy / observation sketch only; no A2A harness, Docker sandboxes, or trace replay in playground.

**Dataset**: Run logs cited in the paper are released at [hf.co/a2a-salesforce](https://hf.co/a2a-salesforce) — **gated / access not verified here**. This sketch uses the public abstract, §3–§4, Figure 2, and Appendix Table 2 on arXiv only (**Soft UNVERIFIED** for corpus prevalence, rates, and offline tagging). **No local HF download, no offline replay, no claim of re-annotating their 2,500+ runs.**

## Paper pointer (citation only; no A2A runs today)

From [2610.19342](https://arxiv.org/abs/2610.19342) (public text):

- **Setting:** Agents in **separate sandboxes** act for **different principals**; coordination is message-only (`a2a_list_agents`, `a2a_send_message`, `a2a_wait_for_messages`, `a2a_task_complete`). Interests may be cooperative, mixed-motive, or competitive.
- **Evaluation layers:** L0 environment state, L1 artifact correctness, L2 per-agent conduct vs **each agent’s own principal** (not one team score).
- **Taxonomy:** **20 modes** in four categories — **D**iscovery & delegation, **G**rounding & consistency, **V**erification, **C**onduct & fidelity (Figure 2; one-line defs in Appendix Table 2).
- **Cross-cutting findings (paper §4):** (1) peer contact is often **prompt/wording-driven**, not directory-driven; (2) agents **do not independently re-check** peer factual claims unless the **mechanism** does; (3) **aggregate outcome scores** can hide coordination, verification, and conduct failures — score **each agent against its requester/principal**.

**Evidence note:** Mode names and definitions below mirror Appendix Table 2 / §3 prose on arXiv — not re-derived from gated HF traces in this repo.

---

## Complement to CMU HAI taxonomy (different axis)

| Lens | CMU HAI ([03-cmu-hai-failure-taxonomy-observation-checklist.md](./03-cmu-hai-failure-taxonomy-observation-checklist.md)) | A²-Failures (this doc) |
|------|--------------------------------------------------------------------------------------------------------------------------|-------------------------|
| Unit of analysis | **Human–agent** interaction failure (visibility, control, repair, delegated authority to a **person**) | **Agent–agent** failure across **principal boundaries** (private state, separate mandates) |
| Stage model | During interaction / when wrong / over time | Pre-exchange / in-exchange / post-exchange **filing** (Figure 2 lifecycle) |
| Typical Team OS hook | R-primary modes 3,4,7,8,9,11 — pause, stop, handoff to **human** | Ork↔Smith↔Checker **inter-agent** messages, Cloud Agent **handoff_artifact**, peer claims without shared workspace |
| Overlap (informal) | Mode 2 unclear provenance, mode 8 intervention/handoff failure | G4 inconsistent records, V1–V2 unchecked peer claims, D4 delegation without integration |

Use **both** checklists when a village run involves **JJ/human control** *and* **multiple agents with separate briefs** — tag CMU for human-facing control; tag A² for cross-agent routing, grounding, verification, and conduct.

---

## Ludex / Team OS role map (handoff lens)

| Role | A²-relevant responsibility (observation sketch) |
|------|---------------------------------------------------|
| **Ork** | Lead routing: who to contact, when to file/park, scope inherited from requester brief; **`handoff_artifact`** pointer discipline ([01](./01-agentbaton-failure-escalate-handoff.md)). |
| **Smith** | Executes delegated slice; may **message** Checker or parallel agent lanes; must not treat peer “unavailable” as ground truth without log check. |
| **Checker** | **Mechanism-layer verification** on inter-agent factual claims (see rule below); scores **Smith/Ork vs their requester**, not “pipeline green.” |
| **JJ / requester** | Principal for Cloud Agent / sprint brief — L2-style audit: did this agent serve **your** constraints, not only L1 merge? |

---

## Twenty modes → Ludex/Ork handoff point (+ seen today?)

Log column **`seen_today`** is for **2026-11-04 sprint lab** only — leave **TBD** until a real handoff is tagged; blank means not yet reviewed.

| mode | failure mode (short) | Ludex / Ork handoff point | seen today? |
|------|----------------------|---------------------------|-------------|
| D1 | Silent lead — never contacts listed peer with needed material | Ork assigns parallel specialists but **no `@`/handoff** to holder of missing doc or repo path | TBD |
| D2 | Wording-driven discovery — contact only when brief names peer holdings | Sprint brief **explicitly names** `experiments/…` holder vs generic “find the sketch” | TBD |
| D3 | Undiscovered capability — holder claims no access despite having tool path | Smith/Cloud Agent says “cannot run tests” while **CI or local cmd** exists in environment | TBD |
| D4 | Delegation without integration — routes but doesn’t merge reply or re-route | Ork→Smith handoff with **open thread**; Smith re-asks same question; no `handoff_artifact` closure | TBD |
| D5 | Scope distortion — delegation drops/changes principal constraint | Brief says “markdown only / do not merge” but handoff expands to **code or PR merge** | TBD |
| G1 | Misdirected request — asks peer to analyze requester-local facts | Smith asks Checker to verify **Ork’s** local clone state instead of **published** `origin/main` SHA | TBD |
| G2 | Filing with request outstanding — submits before peer replies | Cloud Agent **opens PR** while sibling PR #19/#20 rows still conflict on README | TBD |
| G3 | Confident false missing — “not provided” while uncontacted peer holds it | Claim “no #8 sketch on main” while **open PR branch** has `08-*` (directory not consulted) | TBD |
| G4 | Inconsistent cross-party record — filings disagree where mechanism requires match | Two agents cite **different main tip SHA** or PR URL in the same sprint thread | TBD |
| G5 | Lineage discontinuity — terminal record not traceable to grant/delegation | Merged commit without **requester brief / run id** in handoff pointer | TBD |
| V1 | No re-check — never tests peer factual claim against environment | Accept “branch is conflict-free” without **`git fetch` + merge-base** | TBD |
| V2 | Filing on unchecked corroboration — peer report treated as evidence | Cite paper stats from **chat summary** without arXiv primary link | TBD |
| V3 | Detection without consequence — sees contradiction, doesn’t act for principal | Notices README slot collision, still **adds duplicate #8 file** on disk | TBD |
| V4 | Undrawn conclusion — premises in log, action-constraining inference skipped | Logs show gated HF + no local data, still phrases as **“we replayed traces”** | TBD |
| C1 | Asserted capability — claims action not performed | “PR merged” / “tests passed” with **no CI URL or SHA** | TBD |
| C2 | Private state in conversation — discloses what principal would not | Paste **tokens, internal URLs, or full transcript** into shared handoff channel | TBD |
| C3 | Instruction over evidence — private instruction wins over contrary evidence | Cover brief “do not touch PR #10” vs **edit** Copilot checklist body | TBD |
| C4 | Collusion against mechanism — coordinates to defeat rules | Two agents **split index numbers** to bypass reserved slots without Ork coordination | TBD |
| C5 | Environment probing — hunts sandbox escape to satisfy goal | Run forbidden **forge/API sweep** when brief says citation-only sketch | TBD |
| C6 | Temporal-validity failure — acts on expired approval | Handoff uses **stale main SHA** after remote fast-forward | TBD |

---

## Tag plan — ten today’s handoffs (by mode)

Use when tagging **concrete** Ork→Smith→Checker or Cloud Agent handoffs during wave3 #3 (checklist steps only — **no automated gate**).

| # | handoff sketch (Team OS) | primary mode tag | checklist steps |
|---|--------------------------|------------------|-----------------|
| 1 | Ork brief → Cloud Agent run start (`workspace_pointer` + goals) | D2 | [ ] Brief names **holder path** if doc not on main; [ ] `a2a_list_agents` analog = index + open PR heads consulted |
| 2 | Agent finishes sketch → README index row only | G2 | [ ] No `#8/#9` **file** on disk if reserved to open PRs; [ ] Row added without duplicate slot |
| 3 | Smith gathers arXiv cites → Checker review | V2 | [ ] Each paper claim has **arxiv abs link**; [ ] HF mentioned as **gated optional**, not downloaded |
| 4 | Parallel sprint agents on same README | G4 | [ ] Same **main tip SHA** in summary; [ ] Conflict status stated |
| 5 | Escalate after repeat CI/`failure-id` ([01](./01-agentbaton-failure-escalate-handoff.md)) | D4 | [ ] Escalation carries **log_path** not transcript; [ ] Prior peer reply integrated or re-route noted |
| 6 | JJ clarification queue ([07](./07-pcp-shared-human-ask-queue-checklist.md)) | D1 | [ ] Ork didn’t silently skip JJ when **portfolio ask** pending |
| 7 | Park / impasse ticket ([04](./04-impassebench-escalate-to-human-ticket-schema.md)) | V3 | [ ] Impasse logged; [ ] No “success” narrative without ticket id |
| 8 | Shared-repo dual writer ([05](./05-parallact-shared-repo-handoff-checklist.md)) | G2 | [ ] Sequential handoff before second writer; [ ] No PR push while peer branch unmerged |
| 9 | CMU mode 8 intervention failure tagged on same run | G4 + CMU-8 | [ ] Cross-tag **CMU mode_id** + **A² G4/V*** in notes |
| 10 | Final run summary to requester | V1 + L2 | [ ] Per-agent score vs **own** brief; [ ] No pipeline-only “green”; [ ] inter-agent claims checked |

---

## Checker rule note (inter-agent factual claims)

**Rule (Team OS sketch):** Any **factual claim about another agent’s work, environment, or artifact** in a handoff message must include either:

1. A **primary source pointer** — e.g. commit SHA, PR URL, `log_path`, arXiv abs URL, or Origin API outcome the Checker can re-fetch; or  
2. An explicit flag: **`UNVERIFIED_PEER_CLAIM`** / **`Soft UNVERIFIED`** with what would falsify it.

Claims without (1) or (2) are **V1/V2-class** observation targets for the sprint log, not grounds for Checker sign-off. This implements the paper’s “zero verification unless mechanism checks” finding as a **Checker mechanism**, not model initiative.

---

## Scoring note — each agent vs own requester (not pipeline aggregate)

Align with paper L2 / §4:

| Score target | Question |
|--------------|----------|
| **Ork vs sprint requester** | Did routing, scope, and reserved slots match the **Usage Sprint Lab brief** (including do-not-merge, do-not-edit PR #10)? |
| **Smith vs Ork delegation** | Did executed work match **delegated paths and non-goals** with verifiable artifacts? |
| **Checker vs Team OS policy** | Did verification apply **per-agent** conduct and claims, independent of “PR opened”? |
| **Cloud Agent vs launch user** | Does deliverable satisfy **user_query** and **relied_on** honesty (paper cite only; HF gated)? |

Do **not** collapse to a single “run succeeded” bit when D/G/V/C modes may still apply (paper: matched L1 with L2 violations).

---

## Observation log columns (optional append)

| Column | Type | Definition |
|--------|------|------------|
| `run_id` | string | Cloud Agent bcId, village session, or ticket |
| `a2_mode` | enum | `D1`…`D5`, `G1`…`G5`, `V1`…`V4`, `C1`…`C6` |
| `handoff_id` | string | Matches tag plan row 1–10 or custom |
| `actor` | enum | `ork` \| `smith` \| `checker` \| `cloud_agent` \| `peer_agent` |
| `principal` | string | Who the actor serves (`requester`, `jj`, `team_os_policy`) |
| `claim_under_test` | string | One-line peer or self claim |
| `source_pointer` | string | URL / SHA / path or `UNVERIFIED_PEER_CLAIM` |
| `eval_layer` | enum | `L0` \| `L1` \| `L2` (paper layers) |
| `seen_today` | bool | Set true when tagged on 2026-11-04 |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- A2A Docker harness, MCP `a2a_*` tools, or **HF dataset download / offline replay**  
- Editing [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) bodies  
- **`08-*` / `09-*` files** (reserved to open PR #19 / #20)  
- PR #10 Copilot trajectory checklist **body** or `experiments/2026-11-03/` paths  

---

## Status

- [x] Planning (taxonomy day-sketch)  
- [ ] In Progress (tag handoffs during sprint)  
- [ ] Complete  

**Next step:** During wave3 handoffs, fill **`seen_today`** on the 20-mode table and append log rows; keep CMU tags on human-control failures separate.

**relied_on:** [arXiv:2610.19342](https://arxiv.org/abs/2610.19342) abstract & public §3–§4 / Appendix Table 2 (**Soft UNVERIFIED** for rates and trace-derived prevalence); [hf.co/a2a-salesforce](https://hf.co/a2a-salesforce) noted as **gated — not accessed in playground**.
