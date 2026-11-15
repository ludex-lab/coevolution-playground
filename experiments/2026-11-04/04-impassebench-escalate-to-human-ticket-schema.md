# ImpasseBench — `escalate_to_human` ticket schema (Team OS sketch)

**날짜**: 2026-11-04  
**Paper**: [Impasse Bench: Measuring the Evidence–Action Gap in Coding Agents](https://arxiv.org/abs/2610.31895) (arXiv:2610.31895)

**Code**: **NONE** — markdown ticket-field checklist only; no Impasse Bench harness, blocker cards, or trajectory replay in playground.

## Paper pointer (citation only; no runs today)

From the public abstract and §3 results on [2610.31895](https://arxiv.org/abs/2610.31895):

- **Benchmark:** Controlled environment **blockers** on otherwise solvable SWE-style repair tasks; trajectories scored relative to step \(t^{*}\) when **sufficient evidence** of the fault is in hand (**evidence–action gap**).
- **Persistent barriers:** Agents often collect sufficient evidence early (mean \(t^{*} \approx 7.5\) steps in the paper’s reporting) yet **over-persist**—many tool calls after \(t^{*}\), framework-limit endings, and undesired requests **after** evidence.
- **Escalation tool:** Adding **`escalate_to_human`** (stopping without “task failed = bad”) cuts **framework-limit budget exhaustion** on persistent barriers from **34.0% → 6.7%** (baseline vs tool; paper §3.2.1 / abstract). Playground **does not** re-verify that pair on trajectories.

**Evidence note:** Full tool JSON and Appendix A.1 field text live in the paper PDF; this sketch names fields at the level of §3 “Escalation interface” prose only.

---

## `escalate_to_human` ticket fields (paper → Team OS column)

Impasse Bench’s tool ends the run and files a **structured ticket** with six narrative blocks (paper §3). Map them to Team OS handoff columns without inventing Cody-specific enums.

| Paper ticket block | Team OS field | Definition |
|--------------------|---------------|------------|
| Blocker | `blocker` | Short label for the **environment impasse** (permission, dependency, sandbox loss, verification wall, etc.)—analogous to a stable **`failure-id`** when the signature is repeatable ([01](./01-agentbaton-failure-escalate-handoff.md)). |
| Observed evidence | `evidence` | **Cited tool feedback** already seen in-run (exit codes, denied writes, ownership checks)—pointers to **`log_path`** segments, **not** a chat transcript dump. |
| Recovery attempts | `attempts` | **Reasonable recovery** steps already tried per blocker-card logic (retries, installs, chmod, alternate paths)—bulleted, bounded list. |
| Why outside help is needed | `why_help` | One paragraph: why **in-container / in-repo** work cannot resume without a human or infra change. |
| Requested assistance | `request` | Concrete ask (restore write ACL, rotate secret, unblock registry, approve deploy flag, etc.). |
| When work can resume | `resume_when` | Human-readable **resume gate** (“`/src` writable again”, “dependency mirror reachable”, “CI secret injected”). |

**Optional mechanical handoff (Team OS; not extra paper fields):** attach the same **`handoff_artifact`** pair as [01](./01-agentbaton-failure-escalate-handoff.md)—`workspace_pointer` + `log_path`—so the human or a stronger model can pick up without transcript rehydration.

---

## Progress / verification gap → handoff & **park**

Impasse Bench separates **persistent barriers** (stop → escalate) from **verification-limited** faults (may **`task_complete`** with **`verified=false`** while saving useful edits). Team OS analog:

| Impasse Bench ending | Team OS pattern |
|----------------------|-----------------|
| Sufficient evidence + **outside help** required | **`escalate_to_human`** ticket row populated; run **ends**; Checker treats open ticket as **parked** awaiting human/infra. |
| Verification blocked but code edit still valuable | **Progress handoff:** saved patch + explicit **`verified=false`** report; **not** the same as “give up”—document verification gap in `evidence` / `why_help`. |
| Post-\(t^{*}\) tool churn (over-persistence) | **Failure mode to log**, not a ticket field: agent kept acting after evidence; Ork policy should prefer **early ticket** over budget burn (paper motivation). |

### Park / await alignment (PR #10 note pattern)

**Reference path:** `experiments/2026-11-03/02-agentbaton-park-await-cody-fields.md` — **not present on `main`** at branch time (`6cfa925`); described on open **PR #10** (`cursor/copilot-trajectories-intervention-5eae`) as the **park** sketch for runs that must **await** human action.

Until that file lands, align this Impasse ticket with the **same mechanical handoff** already on main in [01](./01-agentbaton-failure-escalate-handoff.md):

| PR #10 park idea (when merged) | Impasse / Team OS mapping |
|--------------------------------|---------------------------|
| `failure-id` | `blocker` + optional stable signature string in `evidence` header |
| **await** fields (human gate) | `resume_when` + explicit **park** state on the run ticket (“do not auto-resume agent until …”) |
| workspace + log handoff | **`handoff_artifact`**: `workspace_pointer`, `log_path` |

**Do not** populate Cody workflow columns (`Cody intervened?`, `round#`, trajectory **outcome** enums) in this sketch—those belong to Copilot trajectory logging on PR #10, not ImpasseBench tickets.

---

## Procedure (Ork → human ticket)

1. **Detect impasse** — Tool feedback matches a **persistent** blocker pattern; sufficient evidence threshold reached (Team OS: same turn or next, policy TBD).
2. **Stop persisting** — No further privilege guesses, credential reads, or test weakening after evidence (paper safety dimension).
3. **File ticket** — Fill `blocker`, `evidence`, `attempts`, `why_help`, `request`, `resume_when`.
4. **Attach `handoff_artifact`** — Branch/SHA + log path only.
5. **Park** — Mark run **awaiting** `resume_when`; do not spawn a stronger model until human clears the gate (contrasts with [01](./01-agentbaton-failure-escalate-handoff.md) **model** escalate on repeat CI failure).

---

## Example ticket row (**example** — fictional, plausible)

| label | blocker | evidence (sketch) | attempts | why_help | request | resume_when | handoff_artifact |
|-------|---------|-------------------|----------|----------|---------|-------------|------------------|
| **example** | `root-owned-source-readonly` | `edit_file` EACCES on `/testbed/src/parser.py`; `ls -l` shows root:root; `chmod` refused | retried write ×2; checked ownership | Agent cannot change ownership inside sandbox; repair blocked | JJ restore write ACL on `/testbed/src` or re-run job with writable mount | `/testbed/src` owned by test user and writes succeed | `workspace_pointer`: repo `playground`, branch `cursor/fix-parser-9abc`, SHA `d4e5f6a`; `log_path`: `/tmp/cloud-agent-run-impasse-9abc.log` |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- New bots, Slack wiring, Impasse Bench **install** or 19k-trajectory replay  
- Cody **`intervened?` / `round#` / outcome** columns (PR #10 only)  
- Editing bodies of [01-agentbaton-failure-escalate-handoff.md](./01-agentbaton-failure-escalate-handoff.md), [02-four-bridges-deception-observation-checklist.md](./02-four-bridges-deception-observation-checklist.md), or [03-cmu-hai-failure-taxonomy-observation-checklist.md](./03-cmu-hai-failure-taxonomy-observation-checklist.md)  
- Runtime benchmarks or harness monitors from the paper  

---

## Status

- [x] Planning (ticket schema sketch)
- [ ] In Progress (no runtime wiring)
- [ ] Complete

**Next step:** When PR #10 lands, cross-link park **await** columns in `experiments/2026-11-03/02-agentbaton-park-await-cody-fields.md`; Checker gate: ticket present ⇒ `handoff_artifact` has no transcript payload.
