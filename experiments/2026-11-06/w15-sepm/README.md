# Wave15 — SEPM EvidenceTier + DAG (Soft day-sketch)

**KEEP Soft.** This folder is a same-day playground sketch of a store-free slice of [SEPM](https://github.com/cookieApril/SEPM) (arXiv [2610.14515](https://arxiv.org/abs/2610.14515)): evidence-authority tiers and an acyclic task-plan graph. It is **not** Top, **not** Team OS law, and it does **not** ship a store.

Paper prose (cite this sentence; the enum member names below are code, not paper vocabulary):

> The authority order is environment or official state, tool observation, verified artifact, and agent inference.

| Artifact | Role |
|----------|------|
| [`models.py`](./models.py) | `EvidenceTier`, `PlanNode`, `PlanEdge`, `TaskPlan` (stdlib; no store) |
| [`fixtures.py`](./fixtures.py) | Synthetic acyclic plans plus cyclic graphs used by tests |
| [`test_sepm.py`](./test_sepm.py) | Stdlib `unittest` (tier order, cycle reject, fixtures) |
| [`NOTICE`](./NOTICE) | Full MIT text — Copyright (c) 2026 SEPM contributors |

Upstream: [cookieApril/SEPM](https://github.com/cookieApril/SEPM). Ideas are ported from `src/sepm/models.py` only.

---

## Upstream pin

| Field | Value |
|-------|-------|
| Repository | https://github.com/cookieApril/SEPM |
| **Pin** | **`083232a954b1de6c4c81884043d20ba41113c949`** |
| License | **MIT** © 2026 SEPM contributors (full text in [`NOTICE`](./NOTICE)) |

---

## Evidence authority

Numeric order in code (ascending authority):

`AGENT_INFERENCE = 1` < `VERIFIED_ARTIFACT = 2` < `TOOL_OBSERVATION = 3` < `AUTHORITATIVE_STATE = 4`

That matches the paper sentence when read highest-to-lowest: environment or official state, then tool observation, then verified artifact, then agent inference. Mark `AUTHORITATIVE_STATE` and the other members as code identifiers, not as the paper's words (`official state` is the paper phrase; `AUTHORITATIVE_STATE` is the code name).

---

## DAG cycle rejection

`TaskPlan` accepts synthetic directed graphs that are acyclic (a linear chain, a diamond, disconnected nodes, and an empty plan). A cyclic dependency raises exactly:

```text
ValueError("dependency graph must be acyclic")
```

---

## Run tests

```bash
cd experiments/2026-11-06/w15-sepm
python3 -m unittest test_sepm.py -v
```

---

## FORBID (honored)

`SQLiteStore` / `src/sepm/storage.py` / `sqlite3` · AutoGen / DyLAN · LLM eval host · DSH · Feishu · daemons · new bot identities · TypeSafe/Jev · MCP/HTTP controller · network at test/runtime · promoting this sketch from Soft to Top.
