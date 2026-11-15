# Handover — Ork→Smith→Checker day-sketch (Team OS borrow)

**날짜**: 2026-11-04  
**Source (Top — public runnable)**: [geekidharsh/handover](https://github.com/geekidharsh/handover) ([`PROTOCOL.md`](https://github.com/geekidharsh/handover/blob/main/PROTOCOL.md), Zenodo [10.5281/zenodo.21797944](https://doi.org/10.5281/zenodo.21797944))

**Code**: **Top public repo** — zero-dependency Node (≥18) **lint + scaffold + bench**; optional Claude Code plugin hooks. Playground **does not** vendor Handover or wire Team OS runs through its behavioral gate.

## Checker KEEP (Top) — explicit caveats

| Signal | KEEP note |
|--------|-----------|
| License | **Apache-2.0** ([`LICENSE`](https://github.com/geekidharsh/handover/blob/main/LICENSE)) — **prefer Handover over Waybill** when playground needs a **license-clear enforcement layer** (see sibling Waybill below). GitHub API `license` field may show `null`; file on disk is authoritative. |
| Stars / activity | **★3** at cite time ([GitHub API](https://api.github.com/repos/geekidharsh/handover)); last push **2026-09-08** — active maintenance vs idle hackathon demos. |
| Scope | **Document + deterministic tooling** (not a hosted multi-hop API). [`paper/`](https://github.com/geekidharsh/handover/tree/main/paper) + bench = research-shaped; day-to-day product is **`HANDOVER_*.md` + lint**. |
| LLM in enforcement | **None** in lint/bench/hook paths (README claim) — Checker is **structure + verify_cmd**, not semantic plan alignment. |
| Identity vs content | Header **`true_at_sha` + per-claim verify** proves **document/repo claims**, not **which agent** wrote them (orthogonal to Waybill Ed25519 **content** signatures). |
| Cold-agent transfer | **`bench/run.js`** reports **trap coverage** deterministically; **empirical cold-agent trials** are **gated** (“give a cold agent only each artifact…”) — **not run in this Cloud Agent turn** → treat transfer KPI as **Soft UNVERIFIED live** until pinned. |
| Plugin gate | `policy.default.json` behavioral rules (reads auto, destructive deny) are **Claude Code–specific** — Team OS borrow focuses on **handoff doc contract**, not porting hooks wholesale. |
| `verify_cmd` exercise | **Re-run this session** on playground checkout: `handover-scaffold.js` → `true_at_sha: a3d544105a19`; `handover-lint.js … --repo` → **drift OK** at true-at SHA; placeholder `FILL IN` **first_action / verify_cmd** → **INVALID header** (expected gate). Upstream `examples/handover.example.md` → **STRUCTURE 100/100**; **`bench/run.js`** → 3 scenarios **good 100/100 vs bad ~4–16/100**, trap coverage **3/3 vs 0/3** (deterministic only). |

**Wave7 Checker verdict:** **KEEP Top** — borrow **YAML header + verify_cmd + negative-knowledge sections + lint strict** for Team OS Ork/Smith/Checker; do **not** claim cold-agent bench scores without a pinned trial.

### Sibling: Waybill (Origin PR [#36](https://cursor.com/codebase/coevolution-lab/playground/pull/36)) — KEEP **with caveats**, not dropped

| Signal | Note |
|--------|------|
| License | **`license: null`** on [ang101/waybill](https://github.com/ang101/waybill) — **method borrow OK** (signed hop chain, validate-plan gate); **code reuse NOT** without a SPDX grant. |
| Activity | **★0**; last push **2026-07-11** (~**4 months** idle vs cite date) — live Render demo may still work; treat as **Top live bits only when re-probed**. |
| Complement | Waybill = **online obligation alignment + content signature** on a hop chain; Handover = **offline lossless doc + repo-grounded verification**. Pick per threat model; **license-sensitive playground paths → Handover first**. |

### Soft later (park — **do not implement** in wave7)

| Topic | Pointer | Intent |
|-------|---------|--------|
| Revocation | [arXiv:2610.15991](https://arxiv.org/abs/2610.15991) | Design note only — supersession / stale handoff **revocation** semantics vs Handover **H6 supersede** |
| Evidence-Guided | [arXiv:2610.41453](https://arxiv.org/abs/2610.41453) | Design note only — evidence-conditioned handoff (follow-on to revocation line) |
| Wave8 park | **DRS**, **DelegateOS** | Named placeholders — no filenames or claims in this sketch |

---

## Map Handover tooling → Team OS (Ork → Smith → Checker)

| Handover step | Tool / artifact | Team OS role | Intent |
|---------------|-----------------|--------------|--------|
| **Contract + anchor** | `handover-scaffold.js` / `/handover:write` | **Ork** | Emit **`HANDOVER_*.md`** with **`true_at_sha`**, **`first_action`**, **`verify_cmd`**, **`shape: handoff`** — machine facts from **live git**, not chat memory ([PROTOCOL.md §3–§4](https://github.com/geekidharsh/handover/blob/main/PROTOCOL.md)). |
| **Relay fill** | Prose sections §0–§8, negative knowledge §2b | **Smith** | Complete **tried-failed / reverted / out-of-scope** and claims table; handoff artifact stays **`path + SHA pointer`**, not transcript dump ([01](./01-agentbaton-failure-escalate-handoff.md)). |
| **Structure gate** | `handover-lint.js` (STRUCTURE 0–100) | **Checker** | Refuse merge/session-done if header invalid or rubric fails — **deterministic**, no LLM. |
| **Truth gate** | `handover-lint.js --repo --verify --claims --strict` | **Checker** | Run **`verify_cmd`** + **per-claim checks**; **`status: done`** blocked until verify passes (**H8**). |
| **Transfer metric** | `bench/run.js` trap coverage | **Checker (quality)** | Measures whether artifact carries **negative knowledge** traps — **deterministic layer run Top**; **cold-agent layer Soft UNVERIFIED** here. |
| **Optional commit gate** | `hooks/pre-commit.sample` | **Checker** | Staged `HANDOVER_*.md` must lint — fails open if Handover absent (upstream doc). |

Cross-links (orthogonal):

- Repeat **`failure-id`** escalate → [01](./01-agentbaton-failure-escalate-handoff.md).
- Human impasse / park → [04](./04-impassebench-escalate-to-human-ticket-schema.md); **Origin PR #10** — **do not edit PR #10 body or Copilot trajectory files**.
- Online signed hop chain (license-caveated) → sibling sketch on branch **PR #36** (`25-waybill-…`) — **not merged on main** at this sketch.

---

## Evidence YAML / header sketch (sample shapes — illustrative)

From [`templates/handover.template.md`](https://github.com/geekidharsh/handover/blob/main/templates/handover.template.md) / [`examples/handover.example.md`](https://github.com/geekidharsh/handover/blob/main/examples/handover.example.md) — **schema only**; SHAs and verify output differ per repo.

### Header (Ork scaffold target)

```yaml
---
protocol_version: 1
handoff: guest-checkout
author: Dana (STORE team)
iso_date: 2026-01-14
true_at_sha: a1b2c3d4e5f6
shape: handoff
supersedes: null
first_action: Run the pending migration on the preview database, then point the /api/guest-order route at the new table (see section 6, step 1).
verify_cmd: npm test -- guest-checkout && npm run typecheck
status: in_progress
---
```

### Claim row pattern (Checker `--claims`)

```markdown
| The `/api/guest-order` route returns a hardcoded stub | `grep -n 'STUB' src/routes/guestOrder.ts` |
| Rate limiting on the route | `[belief, unverified]` — confirm before launch |
```

### Lint stdout sketch (Checker STRUCTURE pass) — **Top, this session**

```text
STRUCTURE:  100/100   header: valid   (shape only — not proof of truth)
  header 45/45  negative-knowledge 20/20  sections 15/15  self-containment 12/12  prose 8/8
```

*(Running `--repo --verify --claims --strict` on the **fictional** guest-checkout example against the Handover repo itself **correctly FAILS** foreign SHA/claims — not a tool bug.)*

### Playground `verify_cmd` / drift exercise — **Top, this session**

Branch `cursor/handover-ork-smith-checker-day-sketch-7dca` at **`a3d544105a19`** (main tip at scaffold time):

```text
✓ true_at_sha: commit a3d544105a19 exists
✓ drift: HEAD is at the true-at SHA; nothing has drifted
✗ verify_cmd: INVALID header while first_action / verify_cmd still `FILL IN`
```

Illustrative **`verify_cmd`** once Ork fills the sketch row (Team OS analog, not committed as `HANDOVER_*.md`):

```bash
test -f experiments/2026-11-04/26-handover-ork-smith-checker-day-sketch.md && git merge-base --is-ancestor a3d544105a19 HEAD
```

---

## Team OS observation row (lint + verify gate)

Log **one row per handoff lint/verify episode** when borrowing Handover semantics. **Log only.**

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `run_id` | string | Cloud Agent / session id |
| `handoff_path_sketch` | string | `Docs/HANDOVER_*.md` or Team OS pointer file |
| `agent_slot` | string | `ork-scaffold` \| `smith-fill` \| `checker-lint` \| `checker-verify` |
| `structure_score` | int | Handover STRUCTURE 0–100 |
| `header_valid` | bool | Gate-blocking header |
| `verify_cmd_ran` | bool | `--verify` executed |
| `verify_cmd_pass` | bool | Whole-artifact verify result |
| `claims_ratio` | string | e.g. `2/6` from `--claims` |
| `drift_at_true_sha` | enum | `none` \| `ahead` \| `unknown` |
| `notes` | string | SHAs, superseded doc id; no transcript dump |

### Example row (**example** — fictional, plausible)

| label | run_id | handoff_path_sketch | agent_slot | structure_score | header_valid | verify_cmd_pass | notes |
|-------|--------|---------------------|------------|-----------------|--------------|-----------------|-------|
| **example** | `TEAMOS-ho-7dca` | `Docs/HANDOVER_wave7-sketch_2026-11-04.md` | `checker-verify` | 100 | true | false | `verify_cmd` failed after Smith edited route without updating claims; **`failure-id`** links to [01](./01-agentbaton-failure-escalate-handoff.md) escalate |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Installing Handover plugin hooks into playground CI or Cloud Agent image  
- Implementing **Revocation / Evidence-Guided / DRS / DelegateOS** bodies (Soft park only)  
- Vendoring Waybill service or copying Waybill code (**NO LICENSE**)  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or **PR #10** files  

---

## Status

- [x] Planning (day-sketch + Checker **KEEP Top**)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** When a Cloud Agent session ends mid-workstream, Ork scaffolds a compliant header; Smith fills negative knowledge; Checker runs `handover-lint --repo --verify --strict` before marking done — aggregate observation rows offline; **no merge of this doc required for ops**.

**relied_on (this sketch):** `origin/main` @ **`a3d544105a19`**; branch head after push (see PR summary); Handover clone @ **`f3baa3ea`** (2026-09-08) for lint/bench commands — **Soft** for cold-agent bench trials **not executed here**.
