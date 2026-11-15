# Replication or Corroboration? — evidential dependence (Soft design note)

**날짜**: 2026-11-04  
**Paper**: [Replication or Corroboration? An Axiomatic Framework for Evidential Dependence in Multi-Agent Debate](https://arxiv.org/abs/2610.36151) (Cao et al., arXiv:2610.36151)

**Code**: **NONE** — markdown design note only; **no public implementation** of the lineage quotient, QBAF lift, or AVeriTeC audit harness cited for checkout in playground. Structural audit counts (**28,224** direct-star profiles, **2,052** multi-layer DAGs, **277** AVeriTeC-derived profiles) are **abstract cite only — Soft UNVERIFIED** (no debate judge runtime, no profile replay).

## Paper pointer (citation only; no runs today)

From the public abstract and §3–§7 on [2610.36151](https://arxiv.org/abs/2610.36151) — playground **does not** run matched-intervention audits or reproduce DF-QuAD moduli:

| Idea (paper) | Sketch |
|--------------|--------|
| **Replication** vs **corroboration** | Matching agent reports may repeat one **evidential root** (relay, paraphrase, alias resubmission, excerpt split) or reflect **distinct roots** that happen to agree |
| **Occurrence aggregation fails** | Counting every report occurrence overweight relays, paraphrases, alias resubmissions, and excerpt splits |
| **Content-only merge fails** | Merging identical propositions removes replication error but also **suppresses genuine corroboration** when distinct roots agree |
| **Root–role unit** | Aggregation unit is **$(\lambda, p, s)$** — root label, targeted claim, support/attack sign — not surface text or occurrence count |
| **Replication class $\mathcal{R}$** | Actions O2–O5: relay, paraphrase, alias resubmission, excerpt split — **no fresh root**, cheap vs fresh contribution O1 |
| **RRI (Root Replication Invariance)** | Further rendering of an already represented root (at most prior strength) **does not change** judge score; equivalent to threshold-uniform replication immunity |
| **Lineage quotient $q_L$** | Coarsest representation that ignores replicas and excerpt splits yet **counts distinct roots**; judge score depends on profile only through $q_L$ when RRI + LNI hold |
| **Trust boundary** | Judge receives an **upstream-supplied partition** of occurrences into roots; provenance discovery and fact-checking accuracy stay **out of scope** for aggregation guarantees |

Playground **does not** implement $q_L$, coalition replication-proof judges, or QBAF propagation checks.

---

## 1) Judge must ignore relayed / paraphrased / resubmitted / split evidence (unless keyed on original source + role)

Paper occurrence fields include display identity $h$, surface text $x$, normalized content $\kappa$, **root label** $\lambda$, claim $p$, sign $s$, strength $\tau$. The judge **does not** observe which agent controls an identity. Strategic agents may append O2–O5 without acquiring new evidence.

**Team OS Checker reading (design memo):**

| Paper rendering | Team OS analog (untrusted unless keyed) |
|-----------------|----------------------------------------|
| **Relay (O2)** | Second agent cites the **same log segment / same CI URL / same parent commit** already in `evidence_refs` |
| **Paraphrase (O3)** | Same underlying fact in **different prose** (PR body vs handback vs thread) |
| **Alias resubmission (O4)** | Same artifact under **second run id** or duplicate PR comment without new forge read |
| **Excerpt split (O5)** | Two **non-overlapping quotes** from one document treated as two independent proofs |

**Rule:** Checker merge/policy gate must **not** treat extra occurrences as extra proof unless each maps to a **fresh root label** at the **same root–role unit** key — i.e. explicit **`(evidence_root_id, claim_slot, role)`** on the handback, supplied upstream (Ork board, PCM attestation sketch PR #23, Soei ledger partition sketch PR #31), not inferred from chat agreement alone.

Without that key, **ignore** relayed / paraphrased / resubmitted / split **occurrences** for verdict strength (RRI analog). Wording match or “two agents said it” is **not** corroboration.

---

## 2) Occurrence ≠ new evidence

**Occurrence** = one submitted report row (one bullet, one `evidence_refs[]` entry, one duplicate SHA mention). **Fresh root** = root label $\lambda \notin \Lambda(P)$ at decision time.

| Mistake | Symptom |
|---------|---------|
| **Occurrence counting** | Checker approves because **three** agents or **three** PR comments repeat “tests green” — one underlying log |
| **Plurality on text** | Same $\kappa$ from one document split into two excerpts → **two** apparent supporters (paper Ex. 8 / CRI vs RRI gap) |
| **Fresh confusion** | New **chat turn** restating an old forge pointer without a **new** independent read or attestation |

**Done gate analog:** One **`proof_anchor`** per **root–role unit** toward a claim ([20-soei-evidence-intent-ledger-design-note.md](./20-soei-evidence-intent-ledger-design-note.md) PR #31 when landed); repeating the anchor in prose adds **zero** marginal proof.

---

## 3) Map to Checker **double-count** across **R-picks / X-picks**

Borrow Team OS handback vocabulary (not in paper):

| Pick kind | Definition | Checker use |
|-----------|------------|-------------|
| **R-pick** | **Root-keyed** evidence unit: stable `evidence_root_id` + `claim_slot` + `role` (`support` \| `attack` \| `policy_clause`) — aligns with paper $u_R(a)=(\lambda,p,s)$ | **At most one** scored unit per R-pick; strength = max attested $\tau$ for that unit (paper $\rho_P=\max$) |
| **X-pick** | **Occurrence-level** pick: each free-text mention, duplicate URL, second agent echo, or extra row in `evidence_refs[]` **without** a distinct `evidence_root_id` | **Do not increment** verdict weight; log for audit only |

**Double-count failure mode:** Checker tallies **X-picks** (N mentions ⇒ N votes toward approve) instead of deduping to **R-picks**. Symmetric failure: **content collapse** merges two **distinct** R-picks because $\kappa$ matches — drops **genuine corroboration** (two independent forge reads, two CI jobs, two policy clauses).

**Cross-links:**

- **Evidence-only Checker** ([16-inter-agent-influence-checker-gate-checklist.md](./16-inter-agent-influence-checker-gate-checklist.md) PR #27): free-text approve path is an X-pick trap; structured **`evidence_refs` / `relied_on`** must carry root keys.
- **Duplicate identity** ([21-remedyfabric-quorum-receipt-day-sketch.md](./21-remedyfabric-quorum-receipt-day-sketch.md) PR #32): same `actor_id` must not double-count quorum — orthogonal but same **occurrence ≠ weight** discipline.
- **S-Bus `relied_on`** ([02](../2026-11-02/02-sbus-version-check-board-rule.md)): versioned **pointer** is one R-pick; repeating the pointer id in narrative is X-pick noise.
- **CMU HAI R-primary** ([03](./03-cmu-hai-failure-taxonomy-observation-checklist.md)): modes **3, 4, 7, 8, 9, 11** — stop/handoff/repair when visibility is unclear; **do not** substitute **more occurrences** of the same root for **observable state**.

### Observation columns (one row per Checker episode)

| Column | Type | Definition |
|--------|------|------------|
| `run_id` | string | Cloud Agent / merge gate id |
| `claim_slot` | string | Policy clause, PR requirement, or ticket key |
| `r_pick_count` | int | Distinct `(evidence_root_id, claim_slot, role)` after dedupe |
| `x_pick_count` | int | Raw occurrence mentions in handback + PR body (Checker may ignore for score) |
| `double_count_risk` | bool | `x_pick_count > r_pick_count` and verdict used occurrence tally |
| `replication_class_sketch` | enum | `none` \| `relay` \| `paraphrase` \| `alias` \| `excerpt_split` \| `mixed` |
| `corroboration_present` | bool | **≥2 distinct** `evidence_root_id` for same `claim_slot` + supporting `role` |
| `verdict_basis` | enum | `r_pick_deduped` \| `x_pick_occurrence` \| `content_collapse` \| `mixed` |
| `checker_verdict` | enum | `proven` \| `unproven` \| `failed` |
| `relied_on` | string | JSON or pointer list — **decision-used** board refs only |
| `notes` | string | `log_path` segment — no transcript dump |

### Example row (**example** — fictional)

| run_id | claim_slot | r_pick_count | x_pick_count | double_count_risk | replication_class_sketch | corroboration_present | verdict_basis | checker_verdict | notes |
|--------|------------|--------------|--------------|-------------------|---------------------------|------------------------|---------------|-----------------|-------|
| **example** | `merge/ci-required` | 1 | 4 | true | `paraphrase` | false | `x_pick_occurrence` | `failed` | Ork + two Smith runs + PR body each cited same green check URL; one CI job — should be **one** R-pick; Checker wrongly weighted four X-picks |

---

## 4) Optional ~100-line reimpl sketch (prose only — not implemented)

**Intent:** A tabletop **lineage-aware deduper** sitting between Smith handback and Checker verdict — **design fiction** for one sprint; **no code in playground**, no claim of correctness vs paper Thm. 3–4.

1. **Ingest** structured handback: each `evidence_refs[i]` must carry optional `evidence_root_id` (upstream partition). Missing id ⇒ treat as **unkeyed X-pick** (weight 0 until human assigns root).
2. **Normalize** claim slot + role from ticket schema ([04](./04-impassebench-escalate-to-human-ticket-schema.md)).
3. **Build** multiset of occurrences; project to **R-picks** by key `(evidence_root_id, claim_slot, role)`; set `strength = max(strength_i)` per key (max-aggregate per paper Asm.).
4. **Replication filter:** Any new occurrence whose key already exists with **strength ≤** incumbent ⇒ **drop** for score (RRI step); allow **strength revelation (O6 analog)** only when new attestation raises max with same root id.
5. **Corroboration:** Count **distinct** `evidence_root_id` per `(claim_slot, role)`; two roots ⇒ eligible positive shift; one root with many X-picks ⇒ still one unit.
6. **Threshold verdict:** Compare aggregated support vs attack per claim to $\theta$ (borrow PCM three-valued gate PR #23); **do not** add occurrence multiplicities.
7. **Emit** `r_pick_count`, `x_pick_count`, `double_count_risk` row for offline audit (Sec. 7 matched-intervention **spirit** only — no 28k profile sweep).
8. **Trust boundary:** Partition edits require **Ork/board** action, not agent self-label; agents cannot mint fresh root ids by excerpting ([2610.36151](https://arxiv.org/abs/2610.36151) Asm. 1).
9. **LLM judge warning:** Paper Thm. 5 — if prompt represents replica and fresh root **identically**, no judge can be both RRI and fresh-responsive; Checker prompts must **expose root keys** in structured fields, not prose-only profiles.
10. **Out of scope for sketch:** QBAF DAG propagation, DF-QuAD modulus, provenance discovery, AVeriTeC replay.

---

## Soft no runtime caveat

- **This file is a design note only** — no lineage quotient code, no debate judge, no QBAF engine, no audit harness vendored in playground.
- Paper theorems, audit sizes, and AVeriTeC intervention results are **Soft UNVERIFIED** citations from [2610.36151](https://arxiv.org/abs/2610.36151); not reproduced here.
- **No** new bots, Slack wiring, SQLite/DSH ports, or merge-gate automation.
- **`relied_on`:** Declare **board pointer ID + version** for evidence actually used in KEEP decisions — not full read sets ([02](../2026-11-02/02-sbus-version-check-board-rule.md)).

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Running paper audits, installing QBAF tooling, or replaying AVeriTeC profiles  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or open sibling sketches **#8–#22** (reserved on Origin PR #19–#33 branches)  
- **Origin PR #10** (AgentBaton / Copilot trajectory)—**leave PR #10 alone**; no `experiments/2026-11-03/` edits  

---

## Status

- [x] Planning (RRI / R-pick vs X-pick Soft sketch)  
- [ ] In Progress (no judge runtime)  
- [ ] Complete  

**Relied on (SHAs):** `a3d5441` (main tip at branch: PCP #7 / merged PR #18); paper [2610.36151](https://arxiv.org/abs/2610.36151) abstract + public HTML/PDF prose cite only — **Soft UNVERIFIED** (no implementation checkout).

**Next step:** When wiring Checker handbacks, require `evidence_root_id` on structured refs before counting corroboration; tabletop one fictional double-count row — no merge of this doc required for ops.
