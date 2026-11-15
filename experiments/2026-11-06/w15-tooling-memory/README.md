# Wave15 — tooling-memory durable-memory principles (Soft day-sketch)

**KEEP Soft.** This folder is a same-day principles-only method-cite checklist for [Durable Memory for Disposable Agents](https://github.com/apache/tooling-memory/blob/4662cc2d0f76ceeb95bd0614e29dd3ce914fefba/docs/durable-memory-for-disposable-agents.md) — agents disposable; data outlives tooling; ownership and expiring claims; provenance on every write; quarantine of writes that fail screening; judgment written down; human-legible records. It is **not** Top, and it is **not** a port of the upstream SQLite index, ledger, metering, or MCP surface.

Design-paper prose (quote-checked against `docs/durable-memory-for-disposable-agents.md` at pin `4662cc2d0f76ceeb95bd0614e29dd3ce914fefba`; do not invent figures):

> Anything worth keeping is written to shared memory before the agent ends.

> Every write carries provenance, and trust does not pass along on its own.

> Everything stays human-legible.

The paper’s own numbered principles include **Data outlives tooling**, **Agents are disposable**, **Ownership limits conflict**, **Judgment is written down**, **Every write carries provenance, and trust does not pass along on its own**, and **Everything stays human-legible**. Quarantine is in the paper body (writes that fail screening are kept in the historian and hidden from everything else), not as its own numbered axiom. “Disputed writes” is not a paper phrase; the paper says “disputed question” and “disputed request” in other sections.

| Artifact | Role |
|----------|------|
| [`checklist.py`](./checklist.py) | Quote-checked sentences, `PrincipleRecord`, `apply_checklist` |
| [`fixtures.py`](./fixtures.py) | Synthetic complete, incomplete, and forbidden records |
| [`test_tooling_memory.py`](./test_tooling_memory.py) | Stdlib `unittest` (quote text, checklist shape) |
| [`NOTICE`](./NOTICE) | Apache-2.0 — upstream LICENSE at the pin (no NOTICE file upstream) |

Upstream code and paper: [apache/tooling-memory](https://github.com/apache/tooling-memory) @ `4662cc2d0f76ceeb95bd0614e29dd3ce914fefba`. Design paper: [`docs/durable-memory-for-disposable-agents.md`](https://github.com/apache/tooling-memory/blob/4662cc2d0f76ceeb95bd0614e29dd3ce914fefba/docs/durable-memory-for-disposable-agents.md).

---

## Upstream pin

| Field | Value |
|-------|-------|
| Repository | https://github.com/apache/tooling-memory |
| **Pin** | **`4662cc2d0f76ceeb95bd0614e29dd3ce914fefba`** |
| License | **Apache-2.0** (full text in [`NOTICE`](./NOTICE); no copyright-owner line in upstream LICENSE; no NOTICE file at the repository root) |
| Design paper | `docs/durable-memory-for-disposable-agents.md` |

The upstream README at this pin says “The index, the ledger and the metering are each a SQLite file” and refers to “the MCP surface.” This sketch does not re-implement that stack.

---

## Checklist shape

A complete record names itself and affirms the cited principles: lasting value stays in documented text-readable records; agents are disposable and write anything worth keeping before they end; domains, files, and tasks have owners whose claims expire; every write carries provenance; writes that fail screening are quarantined; judgment is written down; records stay human-legible. A record that claims to port the upstream storage or MCP stack, or that would need SQLite or MCP, fails the checklist.

---

## Run tests

```bash
cd experiments/2026-11-06/w15-tooling-memory
python3 -m unittest test_tooling_memory.py -v
```

---

## FORBID (honored)

SQLite index/ledger/metering (and `sqlite3`) · MCP surface · treating this as a port of the upstream storage/MCP stack · DSH · Feishu · daemons · new bot identities · TypeSafe/Jev · MCP/HTTP controller · network at test/runtime · promoting this sketch from Soft to Top.
