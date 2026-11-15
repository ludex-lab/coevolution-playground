# Attention Manifest Protocol (AMP) — Soft design note (Frame `ignored` + Receipt VoI method only)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint wave13 Soft **#2**  
**Upstream (method pin):** [eloyhere/attention-manifest-protocol](https://github.com/eloyhere/attention-manifest-protocol) @ **`6ee241afe76ee6b7d9b59525b9a6207d371cb3cc`** (short: `6ee241a`) — **Apache-2.0** ([LICENSE](https://github.com/eloyhere/attention-manifest-protocol/blob/6ee241afe76ee6b7d9b59525b9a6207d371cb3cc/LICENSE) @ pin). Pin message: MCP protocol registration (**v0.6.1**); playground spot-checked `docs/schemas/frame.schema.json`, `docs/schemas/receipt.schema.json`, and `docs/examples/receipt.json` @ pin on 2026-11-04 — **did not** run upstream `npm test` or install Node 24.

**Prior pin (dropped):** [BankrBot/skills](https://github.com/BankrBot/skills) `nookplot/references/runtime-latent-space.md` @ `d28a856` described a **different** Intention/Attention Manifest (geometric matching) — **not** AMP Frame/Receipt; do **not** use as primary.

**Tier**: **Soft KEEP** — **Frame `ignored[]`** with seven **`reason`** enums + **`revisit_if`**, and **Receipt** **`predicted_voi` / `realized_voi`** from pinned schemas **cite-only**. Upstream SQLite catalog/entity store, Elasticsearch discover, MCP runtime, and executable **`tools/` checks** **Soft UNVERIFIED** — playground ran **0** upstream tests on 2026-11-04.  
**Soft→Top**: **forbidden** (this note does not promote any Soft sketch to Top).

**Code (playground)**: **NONE** — markdown design note only; **no** AMP runtime, **no** ledger writer, **no** SQLite adapter, **no** receipt emitter in playground.

**Playground tip at authoring**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (default branch at branch cut; history not rewritten).

---

## Why borrow the method (cite-only; no runs today)

From pinned AMP architecture text @ `6ee241a` ([README](https://github.com/eloyhere/attention-manifest-protocol/blob/6ee241afe76ee6b7d9b59525b9a6207d371cb3cc/README.md)):

- **Problem:** Agents spend finite attention without an auditable record of **what was excluded**, **why**, and **when to reopen** — and without comparing **predicted** vs **realized** value-of-information (VoI) after acts.
- **Frame role:** Freeze one allocation cycle with explicit **`ignored`** exclusions (target + reason + revisit condition) alongside active **slots**.
- **Receipt role:** After **`attend` / `act` / `ask` / …**, record usage, outcome, and **`predicted_voi` vs `realized_voi`** for calibration — not narrative self-report alone.
- **Playground stance:** Use **`ignored` + Receipt VoI** as **Team OS observation columns** on handoffs and tool calls — **not** as shipped AMP ledgers, **not** as reproduced discover/search stacks.

Loop rhyme (upstream cite-only): `Attention → Frame → Context → Receipt → Ledger` — playground documents **Frame exclusions + Receipt VoI** slices only.

---

## Frame `ignored` pack (method — ALLOW scope)

From [frame.schema.json](https://github.com/eloyhere/attention-manifest-protocol/blob/6ee241afe76ee6b7d9b59525b9a6207d371cb3cc/docs/schemas/frame.schema.json) @ pin — each **`ignored`** entry:

| Field (Soft cite) | Role |
|-------------------|------|
| **`target`** | Ref to candidate not allocated this cycle (`kind` + `id`) |
| **`reason`** | One of **seven** exclusion enums (below) |
| **`revisit_if`** | Human-readable **re-open condition** (string; not silent drop) |

**Seven `reason` values (normative @ pin):**

| `reason` | Soft meaning (Team OS hook) |
|----------|-----------------------------|
| **`low_voi`** | Expected information gain too small for current goal |
| **`out_of_scope`** | Outside lane charter / sprint scope |
| **`untrusted`** | Source or claim tier not yet admissible ([Warrant Ledger](https://github.com/eloyhere/attention-manifest-protocol/blob/6ee241afe76ee6b7d9b59525b9a6207d371cb3cc/README.md) cite-only) |
| **`budget`** | Tokens/time/calls exhausted for this cycle |
| **`blocked`** | Dependency, permission, or external gate |
| **`habituated`** | Already satisficed; repetition unlikely to change decision |
| **`deferred`** | Legitimate later — must pair with **`revisit_if`** |

Example shape from [frame-chain.json](https://github.com/eloyhere/attention-manifest-protocol/blob/6ee241afe76ee6b7d9b59525b9a6207d371cb3cc/docs/examples/frame-chain.json) (cite-only):

```json
"ignored": [
  {
    "target": { "kind": "concept", "id": "c.dns_failover" },
    "reason": "low_voi",
    "revisit_if": "错误码中出现 DNS 相关项"
  }
]
```

**Tagging rules (method — ALLOW):**

1. Every “not now” decision logs **`ignored`** with **`revisit_if`** — not silent omission ([ImpasseBench park](../04-impassebench-escalate-to-human-ticket-schema.md) rhyme).
2. **`deferred` / `low_voi`** without **`revisit_if`** is **invalid** at Soft tier (schema requires `revisit_if` on all ignored rows @ pin).
3. Re-open when **`revisit_if`** fires — new **Frame** row; do not overwrite prior exclusion narrative (append observation).

**Explicit ALLOW boundary:** Markdown definitions + log columns. **Do not** port frame digests, slot salience math, or compaction/prune engines from upstream.

---

## Receipt VoI pack (method — ALLOW scope)

From [receipt.schema.json](https://github.com/eloyhere/attention-manifest-protocol/blob/6ee241afe76ee6b7d9b59525b9a6207d371cb3cc/docs/schemas/receipt.schema.json) and [receipt.json](https://github.com/eloyhere/attention-manifest-protocol/blob/6ee241afe76ee6b7d9b59525b9a6207d371cb3cc/docs/examples/receipt.json) @ pin:

| Field (Soft cite) | Role |
|-------------------|------|
| **`op`** | What happened: `attend`, `act`, `ask`, `note`, `plan`, `reflect`, `read` |
| **`target`** | Ref (e.g. tool, claim) the receipt attaches to |
| **`usage`** | `{ tokens, calls, ms, … }` spent |
| **`outcome`** | `success` \| `partial` \| `failure` \| `blocked` |
| **`predicted_voi`** | VoI **before** act (0–1 confidence scale @ schema) |
| **`realized_voi`** | VoI **after** observing outcome |

Example (cite-only):

```json
"predicted_voi": 0.55,
"realized_voi": 0.61,
"outcome": "success"
```

**Receipt rules (method — ALLOW):**

1. Log **both** VoI fields when a lane takes a costly **`act`** (tool run, human ask, merge) — pairs with CARE verified progress ([06](../06-care-escalate-verified-progress-checklist.md)).
2. **`realized_voi` ≪ `predicted_voi`** on repeated ops → candidate for **`habituated`** or **`budget`** **`ignored`** on the next cycle.
3. VoI numbers are **declared calibration**, not reproduced AMP scoring — playground **does not** run upstream calibration registries.

---

## SQLite entity store (upstream — method cite only; Soft UNVERIFIED)

Upstream README @ pin describes a **`catalog.sqlite`** path: **`entity → cache → service → repository → SQL → SQLite`** for catalog records and discovery projections — **playground does not vendor, open, or test this store**.

| Check | Playground stance |
|-------|-------------------|
| Upstream persistence adapters | **Cite-only** architecture row in this note |
| Upstream `npm run build` / `node --test tools/…` | **0 tests executed** in playground on 2026-11-04 → **Soft UNVERIFIED** |
| Team OS observation | Log **pointer + revision** when citing external catalog state — no local SQLite file in playground |

**Warning:** Treat all SQLite/catalog/discover behavior as **UNVERIFIED** here until a **separate** Top or Lab doc runs upstream checks — **do not** Soft→Top this note into a database dependency.

---

## Soft Team OS analogy (markdown only)

| AMP concept (Soft) | Team OS hook |
|--------------------|--------------|
| **Frame `ignored`** | Ork handoff **exclusion list**: path/topic skipped + reason enum + **`revisit_if`** |
| **Receipt VoI** | Post-tool row: predicted vs realized usefulness ([01](../01-agentbaton-failure-escalate-handoff.md) failure-id escalate when VoI repeatedly negative) |
| **Attention Ledger** (cite-only) | Board “where attention went” — not full AMP ledger port |
| **PCP human queue** [07](../07-pcp-shared-human-ask-queue-checklist.md) | Human **`ask`** receipts orthogonal to peer **`act`** receipts |
| **Rally tags** [63-rally](../63-rally/) | **`declared`** ignored/receipt lines vs **`observed`** re-read |

---

## ALLOW / FORBID (this experiment)

### ALLOW

- Cite [eloyhere/attention-manifest-protocol @ `6ee241a…`](https://github.com/eloyhere/attention-manifest-protocol/tree/6ee241afe76ee6b7d9b59525b9a6207d371cb3cc) (**Apache-2.0** @ pin) for **Frame `ignored` (7 reasons + `revisit_if`)** and **Receipt VoI** method.
- Document **Team OS observation** hooks and sibling markdown cross-links under `experiments/2026-11-04/` only.

### FORBID (hard)

- **Full port** of AMP runtime, MCP tools, Elasticsearch discover, SQLite adapters, ledger compaction, or **Soft→Top** elevation of this note
- **DSH**, Feishu, playground **SQLite** files, **daemon** services, or **hub** vendoring
- Claims that playground **ran** upstream tests or reproduces VoI calibration
- **Do not touch** open **PR #10** — paths under **`experiments/2026-11-03/`**.
- **Do not touch** merged **PR #11** — [`01-agentbaton-failure-escalate-handoff.md`](../01-agentbaton-failure-escalate-handoff.md) body on `main`.

---

## Sibling links (folder names — not PR numbers)

| Experiment | Link |
|------------|------|
| AgentBaton failure escalate | [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) |
| ImpasseBench escalate ticket | [04-impassebench-escalate-to-human-ticket-schema.md](../04-impassebench-escalate-to-human-ticket-schema.md) |
| CARE verified progress | [06-care-escalate-verified-progress-checklist.md](../06-care-escalate-verified-progress-checklist.md) |
| PCP shared-human ask queue | [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) |
| Agent Rally Point tags (Soft) | [63-rally](../63-rally/) *(wave13 parallel branch — not on `main` until landed)* |
| **This folder** | [64-attention-manifest](./) |

---

## Checker-ready

| Check | Expected |
|-------|----------|
| Tier | **Soft KEEP** (ignored + Receipt VoI) + **Soft UNVERIFIED** (sqlite/tests/runtime); **Soft→Top forbidden** |
| Pin | **`6ee241a…`** AMP repo; **BankrBot nookplot dropped** |
| Method | **7** `ignored.reason` + **`revisit_if`**; **`predicted_voi` / `realized_voi`** — **not** implemented |
| Tests | **0** upstream tests run — stated explicitly |
| Code | **NONE** in playground |
| README | Index row **#64**; sibling links use **folder / file names** |

---

## Status

- [x] Soft design note (this file) — folded from PR #75 re-pin  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** For live AMP ledgers or SQLite catalog adapters, open a **separate** verified doc — do not merge this Soft note upward.
