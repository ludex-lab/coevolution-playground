# Wave15 — Agent Handoff Gate (Soft day-sketch)

**KEEP Soft** (demoted from Top). This folder is a same-day playground sketch of the upstream *pre-lead evidence gate* and its bounded-continuation routing table. It is **not** Top, **not** Team OS law, and **not** another Wave13 Handoff Debt note-field schema.

A gate-approved packet (`REVIEW_READY`) is ready for review only. It is never automatically accepted, merged, deployed, or authorized for production. A recommended continuation (`CONTINUATION_ELIGIBLE`) is not an executed continuation and does not issue a grant.

A passing test, an evaluator's answer, an authorization to act, and the lead's acceptance remain separate records. Do not treat a gate-approved packet as merge authority.

| Artifact | Role |
|----------|------|
| [`gate.py`](./gate.py) | Decision table (`apply_gate`) over synthetic packet + assessment fields |
| [`packets.py`](./packets.py) | Six synthetic packets labeled by upstream example folder titles |
| [`test_handoff_gate.py`](./test_handoff_gate.py) | Stdlib `unittest` (routes + no-auto-accept + separate-records) |
| [`NOTICE`](./NOTICE) | Full MIT text — Copyright (c) 2026 Matt and Agent Handoff Gate contributors |

Upstream: [zsoXi/agent-handoff-gate](https://github.com/zsoXi/agent-handoff-gate).

---

## Upstream pin

| Field | Value |
|-------|-------|
| Repository | https://github.com/zsoXi/agent-handoff-gate |
| **Pin** | **`dd4d590c3059baeef5532d25d75fb4c048bbe7fd`** |
| License | **MIT** © 2026 Matt and Agent Handoff Gate contributors (full text in [`NOTICE`](./NOTICE)) |

This sketch does not vendor TypeSafe/Jev, an MCP/HTTP controller, a daemon, or the upstream example trees.

---

## Six packets (folder titles, not a routing enum)

Pack paraphrases (complete / premature / blocked / prohibited / unavailable / stale) name the upstream example folders. They are not a six-value packet enum. Routing values are the upstream recommendations and reasons:

| folder | `worker_report` | distinguishing fields | `routing_recommendation` | `routing_reason` |
|--------|-----------------|----------------------|--------------------------|------------------|
| `01-complete-evidence` | `PASS` | evaluated; criteria `CONFIRMED` | `REVIEW_READY` | `EVIDENCE_READY_AT_LOCAL_STAGE` |
| `02-premature-pass` | `PASS` | evaluated; criteria `INSUFFICIENT`; budget remaining | `CONTINUATION_ELIGIBLE` | `LOCAL_EVIDENCE_GAP_WITHIN_PROPOSED_BUDGET` |
| `03-local-blocker` | `BLOCKED` | evaluated; supported local repair; budget remaining | `CONTINUATION_ELIGIBLE` | `SUPPORTED_LOCAL_REPAIR_PROPOSAL` |
| `04-out-of-scope` | `BLOCKED` | prohibited operation | `STOP` | `PROHIBITED_OPERATION` |
| `05-evaluator-unavailable` | `PASS` | evaluator timeout; not evaluated | `LEAD_REVIEW` | `EVALUATOR_TIMEOUT` |
| `06-stale-evidence` | `PASS` | candidate match fails | `LEAD_REVIEW` | `STALE_CANDIDATE` |

A hard stop remains a stop even if the evaluator is unavailable. Evaluator timeout falls back to lead review and never grants extra work.

---

## Upstream banner (cite honestly)

Public facts at the pin: **0★**, exactly one publish commit on **2026-09-17**, no further pushes. The upstream README calls the project a maintained independent learning and research effort. **"Abandoned project (learning/fun)" is the GitHub description only** — do not claim the README says abandoned. `rg -i abandon` over the upstream git tree at this pin is empty.

---

## Run tests

```bash
cd experiments/2026-11-06/w15-handoff-gate
python3 -m unittest test_handoff_gate.py -v
```

---

## FORBID (honored)

TypeSafe/Jev · MCP/HTTP controller · daemon · auto-accept / auto-merge / auto-deploy / auto-authorize-for-production path · treating `REVIEW_READY` as merge authority · new bot identities · DSH · Feishu · SQLite · network at test/runtime · promoting this sketch from Soft to Top.
