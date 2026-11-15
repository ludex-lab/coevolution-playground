# Who Takes the Lead? — Team OS handoff checklist

**날짜**: 2026-11-02  
**Paper**: [Who Takes the Lead? Model Ability and Task-Conditioned Collaboration with Humans](https://arxiv.org/abs/2610.27148) (Li et al., arXiv:2610.27148)

## Paper / claim summary

- **Problem:** Raw “human involvement rate” is ambiguous—high involvement can mean smart delegation *or* weak solo ability; low involvement can mean competent self-reliance *or* ignoring a better-positioned partner ([2610.27148](https://arxiv.org/abs/2610.27148)).
- **Setting:** Shared-control maze: agent (blue) and human (orange) share one target; one avatar moves per **team turn**. Agent sees full graph; human acts from a **local view**.
- **Control allocation (3 types):** `MOVE_SELF(d)`, `GUIDE_HUMAN(d)` (human moves, may override direction), `DEFER_TO_HUMAN` (human moves with no recommendation). Initial placement sets human’s shortest-path advantage Δ without telling the model oracle distances.
- **Baseline first:** Solo maze runs (single avatar, full map) separate **capability** from **collaboration pattern**. Strong solo models (GPT 5.6 Sol, Command A+, Qwen 3.8 27B) vs weak solo (Command R ~22% completion).
- **Main finding:** Stronger solo models show **selective, route-conditioned** involvement—~self-action when agent route is tied or shorter; **~77–83% human involvement on the first decision** when the human route is shorter. Weaker Command R shows **no comparable selectivity** (~35–40% self-action across Δ conditions).
- **Secondary:** When models involved humans on initial decisions, they almost always used **guidance**, not bare deference (no initial `DEFER_TO_HUMAN` in reported co-play).

**Evidence note:** This checklist is grounded in the public abstract, introduction, and method sections on arXiv. Full appendix prompts (Appendix A) and cluster-bootstrap tables (Appendix C) were not transcribed here—treat replication numbers as **paper-reported**, not re-verified in playground.

---

## Handoff decision checklist (Team OS)

Use at **each team turn** when Ork routes work between agent steps and human (Smith / Checker / external partner). Map paper actions to Ludex Village roles:

| Paper action | Team OS reading | When to prefer it |
|--------------|-----------------|-------------------|
| `MOVE_SELF` | Ork (or agent) executes the next concrete step without waiting | Human has **no shorter path** to the outcome: task is fully in agent context, low risk, reversible, or human’s marginal value is unclear |
| `GUIDE_HUMAN` | Ork **recommends** a move; human executes (may override) | Human has **comparative advantage** (local knowledge, approval authority, hands-on env) but agent still owns direction quality |
| `DEFER_TO_HUMAN` | Hand control **without** a recommended direction | Rare in paper; in Team OS, only when human must own direction entirely and agent lacks safe recommendation (document why) |

### Pre-flight (once per episode / task)

- [ ] **Solo baseline recorded:** What can the agent chain do alone on this task class (completion rate, quality), analogous to solo maze S@10 / MDO?
- [ ] **Δ proxy defined:** Who has the shorter path to “target” *right now* (time, access, risk, domain)—not headcount or politeness?
- [ ] **Observation asymmetry explicit:** What does the agent see globally vs what only the human sees locally (prod creds, stakeholder intent, Feishu context)?

### Per-turn decision (Ork → Smith → Checker loop)

1. [ ] **Estimate comparative advantage** (qualitative Δ): Is the human’s next move strictly more valuable than agent self-action for *this* state?
2. [ ] If **no** → default **`move_self`**: agent takes the turn; log what human would have added if consulted (anti-silent-failure).
3. [ ] If **yes** → choose **`hand_to_human`**:
   - [ ] Prefer **`guide_human`**: state recommended action + rationale in the handoff packet (Smith can override with reason).
   - [ ] Use **`defer_to_human`** only with explicit “no safe recommendation” flag (Checker should see empty recommendation as a risk signal).
4. [ ] **Do not optimize involvement rate:** A good turn is correct allocation, not “more human” or “more agent.”
5. [ ] **Checker pass:** Did we avoid (a) consulting when human adds nothing, (b) acting alone when human had the better path, (c) **guidance without handoff** when human must execute?

### Failure modes to tag (from paper + Team OS)

| Tag | Meaning |
|-----|---------|
| `unnecessary_handoff` | Human involved when agent path was tied or better (wasted turn / noise) |
| `silent_no_handoff` | Agent acted when human path was better (missed complementarity) |
| `weak_agent_over_handoff` | Chronic handoff because agent cannot solo—not selective collaboration (Command R pattern) |
| `defer_without_need` | Ceded direction when guidance would preserve team efficiency |

---

## Tiny replication sketch (one-day, no full maze UI)

**Goal:** Smoke-test whether your **orchestrator prompt** allocates control like strong models—**conditioned on Δ**, not on fixed “always ask human” rules.

### Protocol

1. **Materials:** 3 fixed maze seeds (text adjacency lists suffice); horizons **T_max = 10**; initial route pairs mirroring paper: agent-favored `(5,7)`, tied `(5,5)`, human-favored `(7,5)` on path length 5 mazes (see §4.2, [2610.27148](https://arxiv.org/abs/2610.27148)).
2. **Solo phase (optional but paper-critical):** Same seeds, single avatar, full map → record completion by turn 10 and directional optimality (even **n = 3–5** seeds for playground).
3. **Co-play phase:** One human operator; agent chooses each team turn. **Decision labels** (log every turn):
   - `move_self` — maps to `MOVE_SELF`
   - `hand_to_human` — maps to `GUIDE_HUMAN` or `DEFER_TO_HUMAN` (sub-tag `guided` vs `bare_defer`)
4. **Primary playground metric (match paper focus):** First-turn allocation vs Δ₀ ∈ {−2, 0, +2}. Descriptive only at small **n**.
5. **Secondary metrics:**
   - Team **path length** / turns to target (success within horizon)
   - Count **`unnecessary_handoff`** (handoff when Δ ≤ 0)
   - Count **`silent_no_handoff`** (move_self when Δ > 0 on first decision, or when human route stays shorter mid-episode if you extend logging)
   - **`bare_defer` rate** on initial decisions (paper reports ~0 for capable models)

### Minimal log row (copy per episode)

```text
seed | delta_0 | turn | label | sub_tag | human_overrode? | notes
```

### Done-when (playground)

- ≥9 co-play episodes (3 seeds × 3 Δ conditions) **or** explicit timebox stop with written gaps
- One paragraph: “selective like near-ceiling models?” vs “flat involvement like weak solo”

**Out of scope today:** Procedural maze generator, human local-view UI, cluster bootstrap CIs, multi-model API sweep.

---

## Borrow / do-not-borrow (Ludex Village Team OS)

### Borrow

- **Measure solo first, interpret co-play second** — apply to Ork agents before judging “collaboration quality” from Slack/Feishu activity counts.
- **Δ as a first-class input** — encode “who has the shorter path to done” in task state (access, latency, authority), not in vibes.
- **Three-way allocation** — distinguish execute-as-agent vs recommend-and-hand vs bare handoff; paper shows guidance dominates when involvement is warranted.
- **First-decision instrumentation** — cheap signal for selectivity before building heavy dashboards.
- **Appendix-driven replication** — paper points to Appendix A prompts; a text-only replay is the intended one-day path.

### Do not borrow

- **No new bots or headcount** — re-label Ork / Smith / Checker behavior; do not spawn parallel agent personas to mimic maze avatars.
- **No DSH / Feishu / SQLite port** — this sketch stays markdown; do not extend yesterday’s DSH essay-delta or wire new persistence.
- **No “involvement OKR”** — do not reward higher human touch rate; reward **correct** allocation vs Δ and solo capability.
- **No full Collaborative Gym / maze product** — geometry is a controlled testbed, not a Village feature backlog item.
- **No scaling claim from n=4 models** — paper is descriptive across four LMs; Team OS should not treat SSR/IGR numbers as production SLAs.

---

## First real log row (2026-11-02)

| task | first_turn | delta_proxy | why |
|------|------------|-------------|-----|
| `mb-2026-11-02-who-takes-lead` — Morning Brief playground experiment (pick *Who Takes the Lead?* + Cloud Agent docs under `experiments/2026-11-02/`) | `move_self` | **authority** — Ork already scoped candidates + done-when; Builder owns reversible Origin docs write; human (JJ) shorter path only at merge gate, not at first turn | Full task context in agent chain; markdown-only; low risk / reversible; asking human first would be `unnecessary_handoff` |

---

## Status

- [x] Planning (Morning Brief sketch)
- [x] In Progress (first real log row recorded; optional maze replication not started)
- [ ] Complete
- [ ] On Hold

**Next step:** Checker reviews this row at merge gate; optional text-only maze replication remains out of scope unless Ork re-scopes.
