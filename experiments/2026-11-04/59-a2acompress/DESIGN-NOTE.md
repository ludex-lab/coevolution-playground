# A2ACompress — Soft design note (accounting + round-trip method only)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint wave12 Soft **#3** (last Soft for wave12)  
**Upstream (method pin)**: [reh8n/a2acompress](https://github.com/reh8n/a2acompress) @ **`87164185485c301b3835a69824701b19e4c645b9`** (short: `8716418`) — **MIT** ([LICENSE](https://github.com/reh8n/a2acompress/blob/87164185485c301b3835a69824701b19e4c645b9/LICENSE) © 2026); pinned README + `costs.py` / `verify.py` docstrings on 2026-11-04.

**Tier**: **Soft KEEP** — **full-cost accounting rules** and **lossless round-trip gate** from pinned upstream **cite-only**. Benchmark headline (−36.6% ToolBench), optimize loop, and wire-format mechanics **Soft UNVERIFIED** beyond public README text on 2026-11-04.  
**Soft→Top**: **forbidden** (this note does not promote any Soft sketch to Top).

**Code (playground)**: **NONE** — markdown design note only; **no** `a2acompress` codec port, **no** `encode_session` / `decode_session`, **no** `optimize` CLI, **no** ToolBench fetch/replay in playground.

**Playground tip at authoring**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (default branch at branch cut; history not rewritten).

---

## Why borrow the method (cite-only; no runs today)

From the pinned [a2acompress README](https://github.com/reh8n/a2acompress/blob/87164185485c301b3835a69824701b19e4c645b9/README.md):

- **Problem:** Agent handoffs re-send JSON structure, tool catalogs, and quoted outputs; demos often compare **payload-only** bytes and ignore decode instructions.
- **Honest headline (upstream claim — cite-only):** **Full cost** counts compact payload **plus** reconstruction instructions **plus** any dictionary shipped alongside — not transport gzip as token savings.
- **Playground stance:** Treat **accounting + round-trip** as a **Team OS observation vocabulary** for handoff artifacts (pointer + minimal canonical sketch) — **not** as reproduced −36.6% savings or a shipped wire format.

Numeric bars (140,661 → 89,235 tokens, 196 trajectories, 3,013 handoffs) are **cite-only** if referenced elsewhere; playground **does not** reproduce them.

---

## Full-cost accounting (method — ALLOW scope)

From pinned upstream README and [`costs.py`](https://github.com/reh8n/a2acompress/blob/87164185485c301b3835a69824701b19e4c645b9/a2acompress/costs.py) module docstring:

```
full cost = compact payload
          + the reconstruction instructions a model needs to decode it
          + any learned dictionary shipped alongside
```

| Component (Soft cite) | Role |
|-----------------------|------|
| **`raw_tokens`** | Actual `cl100k_base` count of canonical JSON lines (baseline) |
| **`payload_tokens`** | Compact wire text only — **never** compared alone to raw |
| **`instruction_tokens`** | Per-session decode instructions (adaptive / minimal variants in upstream) |
| **`bootstrap_tokens`** | Dictionary material required to read the payload |
| **`update_tokens`** | Lazy-bootstrap dictionary increments (summaries track separately from one-shot bootstrap) |
| **`full_tokens`** | Sum used for savings claims — must reconcile in summaries |
| **Transport (`raw_gzip_bytes`, …)** | Reported separately; **not** mixed into token figures |

**Explicit ALLOW boundary:** Document this **definition and separation** in markdown observation hooks only. **Do not** port `score_session`, tokenizers, dictionary mining, or benchmark grids from upstream.

---

## Lossless round-trip gate (method — ALLOW scope)

From pinned [`verify.py`](https://github.com/reh8n/a2acompress/blob/87164185485c301b3835a69824701b19e4c645b9/a2acompress/verify.py):

1. **Encode → decode → compare** — every record’s **canonical JSON** must match **byte for byte** or the configuration is rejected.
2. **Strict references** — unresolved `$n` / dictionary placeholders **fail loudly** (no silent guess).
3. **Dictionary honesty** — if a payload used dictionary entries but decodes identically without them, reject as dead weight still charged in full cost.

Upstream README adds holdout rules (trajectory-level train/test split, real `cl100k_base`, no invented token IDs) — **cite-only** here; playground **does not** enforce them at runtime.

---

## Evidence card: 33/33 (honest labels)

| Claim | Label |
|-------|-------|
| Pinned tree contains **33** pytest cases under `tests/` (`pytest --collect-only` at **`8716418`**) | **Soft VERIFIED** (tree inspection on 2026-11-04) |
| Upstream CI runs `python -m pytest tests -q` on push (see `.github/workflows/ci.yml` at pin) | **Soft VERIFIED** (workflow file at pin) |
| All **33/33** tests **pass** at pin | **Checker-reproduced at pin** (`python -m pytest tests -q` on 2026-11-04); not a playground CI job |

Do **not** cite 33/33 as reproduced benchmark evidence here; it is the upstream **unit-test card**, not ToolBench trajectory count.

---

## Soft Team OS analogy (handoff honesty; markdown only)

Full-cost accounting rhymes with **pointer handoffs** and **verified progress** — charge the receiver everything needed to reconstruct state, not just the compressed bullet.

| a2acompress method (Soft) | Team OS observation hook (no runtime) |
|---------------------------|----------------------------------------|
| **Full cost vs payload-only** | Log **handoff_artifact** size as pointers + decode sketch + any shared catalog refs — not “one-line summary” alone ([01](../01-agentbaton-failure-escalate-handoff.md)) |
| **Byte-exact round trip** | Checker re-reads cited commits/logs; paraphrase fails like **canonical_mismatch** ([01-mandate-agent-run-checklist.md](../../2026-11-01/01-mandate-agent-run-checklist.md) Missing evidence sketch) |
| **Break-even handoffs** | Early handoffs may cost more overhead — don’t claim savings before verified progress crosses threshold ([06](../06-care-escalate-verified-progress-checklist.md)) |
| **Transport vs tokens** | gzip / attachment bytes ≠ model token bill — separate fields in observation memos |
| **Peer comms overhead** | Targeted ask still has **instruction cost** ([57-ask-on-demand](../57-ask-on-demand/)) — analogous to decode instructions in full cost |
| **Structural comms need** | ICG > 0 memo: compression does not replace missing evidence units ([58-icg-mas](../58-icg-mas/)) |

**Explicit non-promotion:** Do **not** Soft→Top this note into a wire codec, optimizer, or Team OS transport layer — conceptual rhyme only.

**Sibling rhyme (conceptual only):** [55-pairl-extractive-rpt](../55-pairl-extractive-rpt/) *(parallel branch — not on `main` until landed)* and [42-axl-protocol-handoff-design-note.md](../42-axl-protocol-handoff-design-note.md) *(parallel branch — not on `main` until landed)* — folder-name parallels for handoff / transport **vocabulary**; no shared implementation or Soft→Top merge.

---

## ALLOW / FORBID (this experiment)

### ALLOW

- Cite [reh8n/a2acompress](https://github.com/reh8n/a2acompress) at pin **`87164185485c301b3835a69824701b19e4c645b9`** (**MIT** © 2026) for **full-cost accounting** and **lossless round-trip verification method** (definitions, gate rules, transport separation).
- Light **Team OS observation** hooks and sibling markdown cross-links under `experiments/2026-11-04/` only.

### FORBID (hard)

- **Codec port**, **`ProtocolOptions` / encode-decode implementation**, CLI **`a2acompress`**, optimize loop, ToolBench harness, or **−36.6% reproduction claims**
- **Soft→Top** of this note or upstream codec stack
- **DSH**, Feishu, SQLite, **daemon**, **headcount**
- **Do not touch** open **PR #10** — paths under **`experiments/2026-11-03/`** (Copilot trajectories checklist).
- **Do not touch** merged **PR #11** — [`01-agentbaton-failure-escalate-handoff.md`](../01-agentbaton-failure-escalate-handoff.md) body on `main`.

---

## Sibling links (folder names — not PR numbers)

| Experiment | Wave (honest label) | Link |
|------------|---------------------|------|
| hier-memo agents (Soft flat note) | wave10 | [45-hier-memo-agents-soft-design-note.md](../45-hier-memo-agents-soft-design-note.md) *(parallel branch — not on `main` until landed)* |
| OnTrack + progress bar (Soft flat note) | wave11 | [52-ontrack-unreliable-progress-bar-soft-design-note.md](../52-ontrack-unreliable-progress-bar-soft-design-note.md) *(parallel branch — not on `main` until landed)* |
| DALA round arbiter (Top sibling branch) | wave12 | [56-dala-round-arbiter](../56-dala-round-arbiter/) *(parallel branch — not on `main` until landed)* |
| Ask on Demand (Soft folder note) | wave12 Soft **#1** | [57-ask-on-demand](../57-ask-on-demand/) *(parallel branch — not on `main` until landed)* |
| ICG-MAS metric (Soft folder note) | wave12 Soft **#2** | [58-icg-mas](../58-icg-mas/) *(parallel branch — not on `main` until landed)* |
| AgentBaton failure escalate | day index | [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) |
| PCP shared-human ask queue | day index | [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) |
| **This folder** | wave12 Soft **#3** | [59-a2acompress](./) |

---

## Checker-ready

| Check | Expected |
|-------|----------|
| Tier | Header states **Soft KEEP** and **Soft→Top forbidden** |
| Pin | Upstream **`87164185485c301b3835a69824701b19e4c645b9`**; accounting + round-trip method only |
| Accounting | **Full cost** formula + component table — **not implemented** in playground |
| Round-trip | Encode/decode/canonical gate — **method cite only** |
| Codec | **FORBID** — no wire format port |
| Evidence | **33** tests at pin: collect **Soft VERIFIED**; **33/33 pass Checker-reproduced at pin** (not playground CI) |
| Code | **NONE** |
| Forbidden scope | No DSH/Feishu/SQLite/daemon/headcount; no PR #10/#11 edits |
| README | Index row **#59**; sibling links use **folder / file names**; waves labeled honestly |

---

## Status

- [x] Soft KEEP design note (this file)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** If a future **Top** tier needs a lossless handoff codec or benchmark replay, open a **separate** Top doc with verified harness scope — do not merge this Soft note upward.

**Model (completion summary)**: composer-2.5
