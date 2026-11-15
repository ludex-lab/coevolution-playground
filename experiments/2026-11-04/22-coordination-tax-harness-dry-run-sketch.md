# Coordination Tax — harness dry-run outline + α / f / r Ork plugs

**날짜**: 2026-11-04  
**Paper**: [The Coordination Tax and the Heterogeneity Dividend](https://arxiv.org/abs/2610.37700) (Zettl & Gosmar, arXiv:2610.37700)

**Harness**: **KEEP** — [azettl/coordination-tax-harness](https://github.com/azettl/coordination-tax-harness) (public; OFP vs single-LLM six-condition study behind the paper)

**Code in playground**: **NONE** — markdown dry-run checklist + Ork parameter plugs only; harness **not** vendored under `playground/`.

## Paid live vs dry-run (explicit)

| Mode | API spend | Numbers | Playground claim |
|------|-----------|---------|------------------|
| **`--dry-run`** | **$0** (fake model; real OFP processes, HTTP, grading path) | Harness prints `*** DRY RUN: numbers below are FAKE ***` | Validates **wiring** only—not paper Table reproduction |
| **Live** (`run_experiment.py --reps 3 --max-spend 95`) | Paper cites **~$80**, **2430** runs, **~10 h** | Real Anthropic billing | **Not executed** in this sprint; **do not** invent spend receipts or pass@1 tables |

**Dry-run status (honest):** This Cloud Agent turn ran an **isolated clone** (not in-repo) with `python3 run_experiment.py --dry-run --reps 1 --limit 2 --conditions A --out /tmp/dry.csv` — completed **4** fake trials, CSV written. That is **smoke validation** of the harness path only; it is **not** the paper’s six-condition matrix and **does not** estimate α, f, or r from real token traces.

---

## Paper pointer (citation only; no paid matrix today)

From [2610.37700](https://arxiv.org/abs/2610.37700) abstract / §3–§6 (playground cites; does not re-derive):

- **Coordination tax:** decomposition inflates token volume (**α**) plus per-handoff protocol cost (**τ**; paper measures **7.2 ms** per OFP handoff ≈ **0.11%** of pipeline wall time on their stack).
- **Heterogeneity dividend:** routable cheap-model output fraction **f** at price ratio **r** = \(p_{\mathrm{out}}^{c}/p_{\mathrm{out}}^{s}\).
- **Cost break-even (output-dominated sketch):** pipeline undercuts one strong call iff \(f > f^{\star}=(\alpha-1)/[\alpha(1-r)]\) (Eq. 3).
- **Feasibility ceiling:** no routing policy wins if \(\alpha \geq 1/r\) (Eq. 4).
- **Empirical headline (135 tasks, their models):** uniform strong planner–coder–reviewer **~3.22×** cost vs single strong call, **~3.24×** latency, **no** pass@1 gain; cheap planner+reviewer (D) cuts cost to **~0.39×** but **−6.7** pass@1 points vs strong single call—still loses on accuracy–cost frontier vs oracle per-task router.

Playground **does not** re-run **2430** live trials or assert **$80** spend from this workspace.

---

## Harness dry-run checklist (KEEP repo — outline for Ork / future lab turn)

Use [coordination-tax-harness README](https://github.com/azettl/coordination-tax-harness/blob/main/README.md). Check off in an **external checkout**; playground stores the procedure only.

### A. Preflight (no spend)

- [ ] Clone [azettl/coordination-tax-harness](https://github.com/azettl/coordination-tax-harness); read `tasks/LICENSES.md` and **non-sandbox** grader warning (model-written code executes in subprocess).
- [ ] `pip install -r requirements.txt`
- [ ] **Skip** `.env` / `ANTHROPIC_API_KEY` for dry-run (fake model path).
- [ ] Optional: `python3 prepare_tasks.py` only if rebuilding `tasks/tasks.jsonl` (SHA-pinned datasets; **no** model calls).

### B. Dry-run smoke (free)

- [ ] Confirm banner: `*** DRY RUN: numbers below are FAKE, for harness validation only ***`
- [ ] `python3 run_experiment.py --dry-run --reps 1 --limit 2 --conditions A --out dry_smoke.csv`
- [ ] Verify CSV rows append per trial; inspect `logs/` for OFP agent tracebacks if conditions B–D exercised later.
- [ ] **Do not** cite dry-run `$` or `solved` cells as economic evidence—only “harness path green.”

### C. Subset live (still paid — out of scope unless explicitly approved)

- [ ] `.env` from `.env.example` + real key; `--max-spend` cap; `--conditions` subset; `--resume` after interrupt.
- [ ] Full paper replication: `--reps 3`, six conditions, **135** tasks → **~$80** — **not** this sketch’s default.

### D. Post-run analytics (when live CSV exists elsewhere)

- [ ] Derive measured **α** = \(\sum_i o_i / O_1\) from logged token columns (harness / paper reporting rule).
- [ ] Derive **f** = cheap-model output share; **r** from provider price list for assigned models.
- [ ] Compare empirical cost ratio to Eq. (3) break-even; note paper’s **−19%** forecast miss when cheap roles inflate volume (abstract).

---

## α / f / r → Team OS Ork plug points (markdown only)

Ork does **not** implement OFP here; these are **read/write sketches** for when Team OS routes Smith tiers across multi-stage handoffs ([01](./01-agentbaton-failure-escalate-handoff.md) escalate, [05](./05-parallact-shared-repo-handoff-checklist.md) multi-writer).

| Symbol | Paper meaning | Ork **read** (observe / ingest) | Ork **write** (policy knob) |
|--------|---------------|----------------------------------|-----------------------------|
| **α** | Decomposition inflation: total pipeline output tokens vs one-shot strong baseline | From run artifacts: sum of stage output token counts (or proxy: handoff count × average completion size) ÷ single-call baseline for same task id | **`ork.routing.decomposition_max_alpha`** — refuse or collapse stages when rolling α exceeds ceiling (paper feasibility uses **α < 1/r**) |
| **f** | Routable fraction of pipeline **output** on cheap model | Tag each stage with `model_tier`; compute cheap output share over window | **`ork.routing.cheap_output_target_f`** — minimum **f** before approving a multi-agent plan (compare to **f\*** from Eq. 3 given logged α, r) |
| **r** | Cheap/strong **output** price ratio \(p_{\mathrm{out}}^{c}/p_{\mathrm{out}}^{s}\) | Read from provider price table / billing export attached to run | **`ork.routing.price_ratio_r`** — refresh when JJ updates model catalog; drives **f\*** threshold without re-running harness |

### Control loop (sketch)

1. **Before** spawning parallel Smith lanes on one task, Ork loads **(α̂, r)** from catalog + historical stage stats; computes **f\***; if planned cheap share **f_plan < f\***, prefer **single strong call** or **router** baseline (paper §2.2)—log decision row.
2. **During** handoffs, increment stage output counters → update rolling **α̂**; if **α̂ ≥ 1/r**, **stop** adding protocol stages (hard feasibility bound)—park or revert to single call.
3. **After** run, append observation row (below); attach **`relied_on`** pointers to billing CSV / harness `out` path—not transcript dumps.

Cross-links: model **escalate** when cheap tier misroutes quality ([01](./01-agentbaton-failure-escalate-handoff.md)); **joint_fail** under parallel writers ([05](./05-parallact-shared-repo-handoff-checklist.md)) can inflate α without improving **f**.

---

## Observation checklist (economic gate — log only)

Log **one row per routing decision** (approve multi-stage vs single-call vs router). No automated OFP in playground.

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `run_id` | string | Cloud Agent / Team OS run id |
| `task_sketch` | string | One-line task class (e.g. `heuristic codegen`, `doc sprint`) |
| `architecture_sketch` | enum | `single_strong` \| `single_cheap` \| `router` \| `multi_plain` \| `multi_ofp_uniform` \| `multi_ofp_mixed` \| `team_os_analog` |
| `alpha_hat` | float \| null | Estimated decomposition inflation (null if not measured) |
| `f_hat` | float \| null | Estimated cheap output share |
| `r_hat` | float \| null | Price ratio used for threshold |
| `f_star_hat` | float \| null | \((\alpha-1)/[\alpha(1-r)]\) when α, r known |
| `decision` | enum | `approve_multi` \| `collapse_to_single` \| `escalate_strong` \| `park` |
| `harness_mode` | enum | `none` \| `dry_run_smoke` \| `live_subset` \| `live_full` |
| `relied_on` | json | Decision-used `[{ id, version }]` — e.g. `forge/main/tip`, harness CSV path + SHA |
| `notes` | string | **`dry-run ≠ paid live`**; pointer to log/CSV only |

### Example row (**example** — fictional)

| label | run_id | task_sketch | architecture_sketch | alpha_hat | f_hat | r_hat | f_star_hat | decision | harness_mode | notes |
|-------|--------|-------------|---------------------|-----------|-------|-------|------------|----------|--------------|-------|
| **example** | `ca-run-ct-sketch-4b1` | docs-only sprint | `team_os_analog` | 2.8 | 0.35 | 0.025 | 0.68 | `collapse_to_single` | `none` | Planned 3-stage Ork→Smith→Checker; **f_plan < f\***; paper Table 1 analog at α≈2.5, r=0.025 — cite [2610.37700](https://arxiv.org/abs/2610.37700) only |

---

## Out of scope (2026-11-04)

- Vendoring coordination-tax-harness into `playground/` or wiring OFP convener into Team OS runtime  
- Claiming **~$80** / **2430-run** paper replication without pinned CSV + billing artifact in this repo  
- Treating **dry-run FAKE** dollar cells as cost evidence  
- DSH / Feishu / SQLite / daemon / new bots / Slack wiring  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or **Origin PR #10** (AgentBaton / Copilot trajectory)—**leave PR #10 alone**  
- Open sibling day-sketch files **#8–#21** (reserved on parallel PR branches **#19–#32** — see [README](./README.md))  

---

## Status

- [x] Planning (dry-run checklist + α/f/r Ork plugs)  
- [ ] In Progress (no harness in playground tree)  
- [ ] Complete  

**Next step:** Optional isolated checkout: full `--dry-run` across conditions **A,Aprime,R,B,C,D** with `--limit 2`; only after JJ approves spend, run capped live subset and log measured α, f, r into observation rows.

---

## relied_on

- `a3d5441` — `origin/main` tip at branch time ([playground](https://origin.cursor.com/git/coevolution-lab/playground))  
- [github.com/azettl/coordination-tax-harness](https://github.com/azettl/coordination-tax-harness) @ `main` — **KEEP** harness README + `run_experiment.py --dry-run` path (**cite**; clone lives outside playground)  
- [arXiv:2610.37700](https://arxiv.org/abs/2610.37700) — α, f, r, break-even Eqs. (3)–(4), empirical cost multiples (**citation only**)  
- **Dry-run:** smoke executed in Cloud Agent VM (`--dry-run --reps 1 --limit 2 --conditions A`) — **FAKE** metrics; **not** paid live  
- **Paid live (~$80):** **not run** — no spend evidence in this PR  
- Origin **PR** (`cursor/coordination-tax-harness-dry-run-e1d8`) — handback `relied_on` should pin **`forge_head` at review time** (not self-cited inside the same commit)  
- Sibling sketches [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) on `main`  
- SBUS `relied_on` subset rule: [02](../2026-11-02/02-sbus-version-check-board-rule.md) (**Soft** board pointer IDs: `forge/main/tip`, `origin_pr/<n>/forge_head`, `origin_pr/<n>/content_tip`)
