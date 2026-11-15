# Agentic Path Maps — Ork brief UX (post-run alternatives footer)

**날짜**: 2026-11-04  
**Paper**: [Agentic Path Maps: Exposing an Agent’s Traversal Through the Garden of Forking Paths](https://arxiv.org/abs/2611.04183) (Grunde-McLaughlin et al., arXiv:2611.04183)

**Code**: [madeleinegrunde/agentic_path_maps](https://github.com/madeleinegrunde/agentic_path_maps) — **Soft UNVERIFIED** in playground: README / supplement pointers only; no verified checkout, no Path Maps renderer, and **no runtime Path Maps installer** or Team OS integration in this repo.

## Paper pointer (citation only; no runs today)

From the public abstract and §1 / study summary on [2611.04183](https://arxiv.org/abs/2611.04183):

- **Problem:** Underspecified tasks let agents embed **assumptions** that yield **task-valid** outputs that may still contradict **user-valid** context (garden of forking paths).
- **Proposal:** **Agentic Path Maps** — post-execution displays of **alternative pathways** the agent did not take, so reviewers can sensemake without re-deriving the full decision tree from a linear trace alone.
- **Design space:** Eight generative dimensions (objectives, structure, initiative, timing, **quantity of content**, explanatory content, visualization, interaction)—playground **does not** implement or A/B any widget.
- **Empirical study (Soft):** **n=48** participants in a **data analysis** setting; preregistered one-vs-multiple-path conditions; additional **three-path sample vs nine-path** comparison. **Soft UNVERIFIED** here: no prereg replay, no Ai2 analysis harness in playground.
- **Findings (paper-reported, citation only):** Participants **rarely** propose specific alternative analysis choices unprompted; showing alternatives **reduces overreliance** (Weight of Advice) vs a single extreme path; **~3 sampled paths** can beat showing **all nine** on several measures—**Germane Cognitive Load** favored the sample; nine-path UI **diminishing returns** on most other outcomes.
- **Timing:** Paper argues for **post-hoc** path communication where **pre-run clarification of every fork** is untenable—complements (does not replace) ask-when policies ([07](./07-pcp-shared-human-ask-queue-checklist.md)).

Playground **does not** run the paper’s user study, BLADE multiverse harness, or Path Maps UI code.

---

## When to use (Team OS / Ork brief policy sketch)

| Phase | Path Maps footer? | Rationale (paper-aligned sketch) |
|-------|-------------------|----------------------------------|
| **Pre-run Ork brief** | **No** (default) | Avoid duplicating PCP-style **pre-run ask storms**; state success criteria + pointers only ([07](./07-pcp-shared-human-ask-queue-checklist.md)). |
| **Mid-run** | **No** | Automatic execution; use **withdrawable ask** or **park** tickets for true blockers ([04](./04-impassebench-escalate-to-human-ticket-schema.md), [07](./07-pcp-shared-human-ask-queue-checklist.md)). |
| **Post-run / after decision pack** | **Yes — footer block** | Once Smith returns artifacts + `relied_on`, append **2–3 untaken forks** so JJ/Checker can audit **user-valid** fit without reading full transcript. |
| **Repeat `failure-id` escalate** | Optional 1-line fork | After [01](./01-agentbaton-failure-escalate-handoff.md) escalation, note **which assumption branch** the weaker model took—pointer only. |

**Quantity norm (from paper, Soft):** Prefer **sample ≈3** labeled alternatives in the footer—not an exhaustive **9** (or full multiverse) unless Checker explicitly requests depth.

---

## Ork brief — `## Alternatives not taken` footer template

Append **after** the decision pack (PR URL, head SHA, conflict status, evidence pointers)—**not** in place of success criteria.

```markdown
## Alternatives not taken

_Chosen path (1 line):_ <what Smith actually did — assumption + outcome pointer>

| Fork | One-line consequence if taken instead |
|------|----------------------------------------|
| A | <task-valid branch not taken → different artifact or merge policy> |
| B | <assumption flip (e.g. scope, base branch, evidence gate) → user-valid risk> |
| C | <optional third fork — omit row if only two matter> |

_path_map_count: 3_ · _display: sample_not_full_multiverse_ · _timing: post_run_
```

**Field rules (markdown only):**

1. **2–3 forks** only in the table; each **consequence** is one line (no transcript dump).
2. Forks must be **task-valid** alternatives the agent **could** have taken—not fictional failures.
3. Link consequences to **board pointers** or `log_path` segments when possible ([01](./01-agentbaton-failure-escalate-handoff.md) handoff discipline).
4. If the run had **no meaningful fork** (fully specified brief), write `_path_map_count: 0_` and one sentence **why** (still post-run honesty).

### Example footer (**example** — fictional, plausible)

```markdown
## Alternatives not taken

_Chosen path (1 line):_ Land PCP ask-queue sketch as `#7` on `main`; reserve `#8–#10` to open PRs; add `#11` Path Maps footer on new branch.

| Fork | One-line consequence if taken instead |
|------|----------------------------------------|
| A | Collapse `#8–#10` reservations into one mega-PR → index conflict with open PR #19–#21. |
| B | Pre-run brief lists nine hypothetical merge policies → JJ attention cost without post-run artifacts ([07](./07-pcp-shared-human-ask-queue-checklist.md)). |
| C | Omit footer; JJ anchors on single PR diff only → higher **overreliance** risk on underspecified “Soft UNVERIFIED” claims (paper n=48 Soft note). |

_path_map_count: 3_ · _display: sample_not_full_multiverse_ · _timing: post_run_
```

---

## Map to sibling sketches (cross-links)

| Path Maps idea | Team OS analog |
|----------------|----------------|
| Post-hoc alternatives vs pre-run interrupts | **Footer after decision pack**; keep **PCP queue** for true clarifications ([07](./07-pcp-shared-human-ask-queue-checklist.md)) |
| Sample of 3 vs 9 paths | Ork brief footer **cap at 3** forks; Checker may open a follow-up row for depth |
| Task-valid vs user-valid | Checker compares footer forks to **JJ stated preferences** in brief non-goals |
| Trace transparency alone insufficient | Complements trace/`log_path` pointers—not a replacement ([01](./01-agentbaton-failure-escalate-handoff.md)) |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Path Maps **UI**, graph layout engine, or GitHub Pages demo install from [agentic_path_maps](https://github.com/madeleinegrunde/agentic_path_maps)  
- HCI study **replication** (n=48) or prereg data pulls  
- Editing [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) bodies  
- **`08-*` / `09-*` / `10-*` files** (reserved to open PR #19 / #20 / #21)  
- PR #10 Copilot trajectory checklist **body** or `experiments/2026-11-03/` paths  

---

## Status

- [x] Planning (brief-UX day-sketch)  
- [ ] In Progress (Ork adopts footer on next post-run brief)  
- [ ] Complete  

**Next step:** After the next Cloud Agent **decision pack**, paste the footer template with 2–3 real forks; JJ spot-checks whether **three** rows suffice before asking for a full multiverse list.

**relied_on:** [arXiv:2611.04183](https://arxiv.org/abs/2611.04183) abstract & public study summary (**Soft UNVERIFIED** for effect sizes and UI screenshots); [github.com/madeleinegrunde/agentic_path_maps](https://github.com/madeleinegrunde/agentic_path_maps) README/supplement (**Soft UNVERIFIED** — not executed in playground); HCI **n=48** noted as **Soft** (no local replay).
