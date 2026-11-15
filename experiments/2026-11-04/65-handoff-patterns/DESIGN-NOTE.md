# Handoff patterns — Soft checklist (product decision method only)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint wave13 Soft **#3** (lowest priority in wave13 Soft trio)  
**Upstream (method pin):** [leonardoduarteneto/ai-agent-handoff-patterns](https://github.com/leonardoduarteneto/ai-agent-handoff-patterns) @ **`5286b19912369c558dc06654fec5290d0c8d7b3f`** (short: `5286b19`) on **`main`** as of 2026-11-04. **MIT** ([LICENSE](https://github.com/leonardoduarteneto/ai-agent-handoff-patterns/blob/5286b19912369c558dc06654fec5290d0c8d7b3f/LICENSE) @ pin). README-only upstream — **five core decisions**, **seven handoff principles**, **Patterns 01–05**; playground did **not** verify any product deployment or threshold calibration @ pin.

**Prior mispin (fold honesty):** An earlier draft cited Microsoft **agent-framework** `_handoff.py` — **multi-agent orchestration routing**, not this repository’s **when-to-respond / ask / tool / escalate / human** patterns. That pin was **dropped** on fold; do not treat HandoffBuilder as primary for **#65**.

**Tier**: **Soft UNVERIFIED** — decision vocabulary + Team OS **observation checklist** cite-only from pinned README. Confidence/risk thresholds and platform routing **Soft UNVERIFIED** beyond public markdown on 2026-11-04.  
**Soft→Top**: **forbidden** (this note does not promote any Soft sketch to Top).

**Code (playground)**: **NONE** — markdown design note only; **no** omnichannel queue, **no** policy engine, **no** confidence scorer, **no** workflow runtime.

**Playground tip at authoring**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (default branch at branch cut; history not rewritten).

**Not this note (honest split):**

| Related experiment | What it owns |
|--------------------|--------------|
| [60-handoff-debt-notes](../60-handoff-debt-notes/) *(wave13 Top #1 — parallel branch)* | **Coding-agent successor takeover** — seven-field **`structured_notes`**, dirty-git contradiction, pure-fn sketch — **interrupted-task rediscovery cost** on a repo, **not** customer-support-style respond/ask/human routing. |
| [57-ask-on-demand](../57-ask-on-demand/) *(wave12 Soft — parallel branch)* | **Parallel peer** **(need, known, decision)** + APPROVE/DENY gate — overlaps upstream **Ask** / **Pattern 02** *missing context* only; **not** human handoff or authorization patterns. |
| [04-impassebench-escalate-to-human-ticket-schema.md](../04-impassebench-escalate-to-human-ticket-schema.md) | **Park / human impasse** ticket schema — rhymes with **Hand off to a human** + **Pattern 01** but ImpasseBench fields, not README pattern prose. |
| [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) | **Model escalate** on repeat **`failure-id`** + **`handoff_artifact`** pointers — rhymes with **Escalate** decision, not README’s human/product matrix. |

For structured successor notes and git-dirty consistency, **read #60** — do **not** Soft→Top this checklist into that Top sketch.

---

## Why borrow the method (cite-only; no runs today)

From [README.md @ `5286b19`](https://github.com/leonardoduarteneto/ai-agent-handoff-patterns/blob/5286b19912369c558dc06654fec5290d0c8d7b3f/README.md):

- Agents should **not** handle every situation autonomously; they need reusable rules for **when to act**, **when to clarify**, **when to use tools**, **when to escalate**, and **when humans take over**.
- **Principles** (confidence, risk, intent, authorization, context completeness, emotional sensitivity, recoverability) gate those decisions — playground documents the **names**, not calibrated thresholds.
- **Patterns 01–05** are scenario-specific rules with expected behavior and anti-patterns — cite-only templates for Team OS **run reviews**, not shipped playbooks.

Playground stance: **observation checklist** for human-centered handoff *decisions* in ops narratives — **not** reproduced routing queues or domain policy engines.

---

## Five core decisions (Soft checklist row set A)

| # | Decision @ pin | Soft Team OS observation question |
|---|----------------|-----------------------------------|
| D1 | **Respond** — clear request, within capability | Did the lane answer **without** missing evidence or skipping mandate checks ([01-mandate-agent-run-checklist.md](../../2026-11-01/01-mandate-agent-run-checklist.md))? |
| D2 | **Ask** — important context missing | Was clarification **minimal and necessary** (Pattern 02), not broad data fishing? *(AOD peer tuple is separate — see overlap below.)* |
| D3 | **Use a tool** — external data or action required | Was live state fetched via **approved tool/path**, not model guess (Pattern 03)? |
| D4 | **Escalate** — specialized flow / higher-confidence process | Did repeat failure or low confidence trigger **model/process escalate** ([01](../01-agentbaton-failure-escalate-handoff.md), [06](../06-care-escalate-verified-progress-checklist.md)) **without** conflating with human queue? |
| D5 | **Hand off to a human** — judgment, authorization, empathy | Was JJ/human bandwidth used when required ([07](../07-pcp-shared-human-ask-queue-checklist.md), [04](../04-impassebench-escalate-to-human-ticket-schema.md)) with **context preserved** (pointer handoff, not transcript dump)? |

**Pass rule (Soft):** For each user-visible turn review, mark which **single primary** decision applied; note if the agent **skipped** Ask before Respond or **forced automation** after explicit human request (Pattern 01 anti-pattern).

---

## Seven handoff principles (Soft checklist row set B)

Evaluate qualitatively in markdown reviews — **no numeric scores** in playground.

| # | Principle @ pin | Observation hook |
|---|-----------------|------------------|
| P1 | **Confidence** | Would a reasonable reviewer agree the lane **understood** the task before acting? |
| P2 | **Risk** | If wrong, impact on repo/user — does outcome justify **escalate/human** (Patterns 04–05)? |
| P3 | **User intent** | Explicit ask for a person → **Hand off** (Pattern 01), not persuasion loops |
| P4 | **Authorization** | Action allowed under Team OS / forge rules — else **stop** (Pattern 05) |
| P5 | **Context completeness** | Missing critical facts → **Ask** before Respond (Pattern 02) |
| P6 | **Emotional sensitivity** | Frustration/conflict → bias **human** even if technically answerable |
| P7 | **Recoverability** | Irreversible/high-cost → lower bar for **Escalate** or human confirmation (matrix row @ pin) |

---

## Patterns 01–05 (Soft checklist row set C)

| Pattern | Scenario (cite) | Team OS rhyme (observation only) |
|---------|-----------------|----------------------------------|
| **01** Explicit human request | User asks for a person | Honor request; min routing info; preserve context via **pointers** ([01](../01-agentbaton-failure-escalate-handoff.md)) — anti-pattern: “let me try once more” |
| **02** Missing critical context | Understandable ask, unsafe without facts | **Ask** minimum fields; distinguish missing vs unavailable vs restricted (@ pin) — **AOD overlap: this Ask only** ([57-ask-on-demand](../57-ask-on-demand/) = **peer** `(need, known, decision)`, not customer clarification) |
| **03** Tool required | Answer needs system of record | No speculation; tool failure → escalate or human (@ pin) |
| **04** Low confidence or high risk | Policy/eligibility/money/access ambiguity | Do not feign certainty; clarify, confirm, escalate, or human (@ pin) |
| **05** Authorization required | Sensitive change without permission | Verify before act; NL “I’m the owner” insufficient (@ pin) |

**Decision matrix @ pin** (starting point only — **UNVERIFIED** thresholds in playground): clear + low risk → Respond; missing context → Ask; external state → Tool; low confidence / high risk → Escalate; explicit human / missing auth / emotional / irreversible → Human or confirm (@ pin table).

---

## AOD overlap (narrow)

| Upstream | [57-ask-on-demand](../57-ask-on-demand/) |
|----------|------------------------------------------|
| **Ask** / **Pattern 02** (missing context) | **Peer** parallel consult with gate — same *clarify-before-guess* spirit, **different** channel and schema |
| Escalate / human / tool patterns | **Out of scope** for AOD — do not merge Soft notes |

**Soft→Top forbidden** for both **#65** and **#57**.

---

## ALLOW / FORBID (this experiment)

### ALLOW

- Cite [leonardoduarteneto/ai-agent-handoff-patterns @ 5286b19](https://github.com/leonardoduarteneto/ai-agent-handoff-patterns/tree/5286b19912369c558dc06654fec5290d0c8d7b3f) (**MIT**) for **5 decisions**, **7 principles**, **Patterns 01–05**, and decision matrix **method labels**.
- **Point** to [60-handoff-debt-notes](../60-handoff-debt-notes/) for coding-agent structured handoff debt — **≠** this product-pattern checklist.
- Team OS **observation** hooks under `experiments/2026-11-04/` only.

### FORBID (hard)

- **Code port**, queue/routing implementation, or threshold **calibration claims**
- **Soft→Top** elevation; reinstating Microsoft **agent-framework** as primary pin for this folder
- **DSH**, Feishu, **SQLite**, **daemon**, **hub**
- **Do not touch** open **PR #10** — `experiments/2026-11-03/`.
- **Do not touch** merged **PR #11** — [`01-agentbaton-failure-escalate-handoff.md`](../01-agentbaton-failure-escalate-handoff.md) body on `main`.

---

## Sibling links (folder names — not PR numbers)

| Experiment | Link |
|------------|------|
| AgentBaton failure escalate | [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) |
| Impasse human ticket | [04-impassebench-escalate-to-human-ticket-schema.md](../04-impassebench-escalate-to-human-ticket-schema.md) |
| PCP shared-human ask queue | [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) |
| Ask on Demand (Soft) | [57-ask-on-demand](../57-ask-on-demand/) *(Ask / Pattern 02 overlap only)* |
| Handoff Debt structured notes (Top) | [60-handoff-debt-notes](../60-handoff-debt-notes/) *(≠ this Soft note)* |
| Agent Rally Point (Soft) | [63-rally](../63-rally/) |
| Attention Manifest (Soft) | [64-attention-manifest](../64-attention-manifest/) |
| **This folder** | [65-handoff-patterns](./) |

---

## Checker-ready

| Check | Expected |
|-------|----------|
| Tier | **Soft UNVERIFIED**; **Soft→Top forbidden** |
| Pin | **`5286b19912369c558dc06654fec5290d0c8d7b3f`** + **MIT**; Microsoft mispin **dropped** |
| Method | **5 decisions** + **7 principles** + **Patterns 01–05** checklist — not implemented |
| vs #60 | Points to Top Handoff Debt; **no** seven-field / dirty-git here |
| vs #57 | **Ask / Pattern 02** overlap stated; peer AOD not duplicated |
| Code | **NONE** |
| README | Row **#65** + source link to **ai-agent-handoff-patterns** |

---

## Status

- [x] Soft UNVERIFIED design note (this file; folded from mispin)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** Use row sets A–C in offline run reviews; for successor structured notes on dirty git, use [60-handoff-debt-notes](../60-handoff-debt-notes/) only.

**Model (completion summary)**: composer-2.5
