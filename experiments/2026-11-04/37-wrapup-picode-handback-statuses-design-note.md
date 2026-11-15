# Wrap-up (PiCode) — honest handback statuses (design note)

**날짜**: 2026-11-04 (Usage Sprint wave9 **Top**)  
**Upstream**: [cognixws/picode-wrapup](https://github.com/cognixws/picode-wrapup) — **Apache-2.0**  
**Playground tip (branch base)**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (`main` at sketch start; rebase 시 실제 tip SHA를 PR head에 기록)

**Code in playground**: **NONE** — markdown design note only; no Wrap-up extension vendoring, no CLI rewrite.

## Checker vs this VM

| Evidence slice | Verdict |
|----------------|---------|
| Upstream `node --test` (validator, renderer, ids, redaction, protocol, manifest) | **Checker KEEP-with-caveats:** **41/41** pass reported on upstream; license **Apache-2.0** ([README](https://github.com/cognixws/picode-wrapup/blob/main/README.md)). |
| Re-run on this Cloud Agent VM | **Soft UNVERIFIED** — package not cloned or executed here; beyond Checker pack, treat upstream test count as **citation only**. |

**Labeling honesty (Top):** upstream item statuses are **exactly** `done` | `caveat` | `needs_you` ([docs/format.md](https://github.com/cognixws/picode-wrapup/blob/main/docs/format.md)). **Do not** invent or alias **`ready` / `blocked` / `failed` / `dropped`** as upstream labels—they are **not** part of the Wrap-up contract.

---

## Intent — Ork → Smith → Checker closes

When Smith finishes a **block of work** and Checker (or Ork) needs a **transcript-external** close packet, borrow Wrap-up’s **handback contract** instead of vibe or forge-green alone:

1. **Group by area**, not by time (areas = scoped slices Checker can scan).
2. **Every line carries an upstream status** — no orphan “PASS” prose without `done`/`caveat`/`needs_you`.
3. **Validation rules (upstream, Top):**
   - **`done`** — finished **and** verified; note must say **how** (command, test, URL, file). Vague notes (`ok`, `tested`, `works`) are **refused** when `refuse_vague_notes` is on.
   - **`caveat`** — finished but not fully verified, **or work the agent did not finish**; note must say what was **not** verified or what is missing. **Unfinished agent work is always `caveat`, never `needs_you`.**
   - **`needs_you`** — only a **decision or action only the human** can take (options or deadline). These items sort **last** (areas that are needs-you-only move to end of report).

Agents write in conversation language; Wrap-up adds markers, counts, and report id only—**no extra narrative voice**.

---

## Report id & correction (Top if present upstream)

| Field | Pattern | Role in handback |
|-------|---------|------------------|
| Report id (output footer) | `R-` + **10 base32** characters (example: `R-7K3QX2M9AB`) | Stable id from agent + content (retries → same id). Log as **`handback_report_id`** or align with existing **`handback_id`** in observe logs ([2026-11-02/04-sbus-observe-checklist.md](../2026-11-02/04-sbus-observe-checklist.md)). |
| `replaces` (optional input) | `R-` + 10 base32 | Points at **your earlier report** this one corrects—use for Smith revision cycles without pretending a new close is first intent. |

Do **not** rename these to Team OS ticket ids; **pointer + id** only.

---

## Soft analogy — Team OS four-state (not upstream equality)

Some Team OS boards use a **four-state** completion vocabulary (e.g. ready-to-merge vs parked vs human-blocked vs abandoned). That vocabulary is **Soft analogy only**:

| Team OS sketch (Soft) | Wrap-up upstream (honest borrow) | Caveat |
|----------------------|-----------------------------------|--------|
| “Ready” / mergeable green | Often **`done`** lines with **concrete verification notes** — not the word “ready” | Forge CI green **≠** `done` unless Smith maps evidence into a verified note. |
| “Blocked” on env/tooling | Usually **`caveat`** (unfinished or unverified work)—**not** `needs_you` unless only human can unblock | Impasse tickets stay on [04](./04-impassebench-escalate-to-human-ticket-schema.md) path; don’t relabel as upstream `needs_you` without human-only decision. |
| “Failed” / dropped scope | **`caveat`** (what’s missing) or omit from report—**no** upstream `failed` / `dropped` | Do not import mandate “failed” Report tags as Wrap-up statuses. |
| Human decision pending | **`needs_you`** only | Must be human-only; agent unfinished work **must not** land here. |

**Checker gate (Top):** reject handbacks that use **non-upstream** status tokens or that park **agent-unfinished** work under `needs_you`.

---

## Soft — PASS-is-claim / Orchestra theme overlap

Any evidence slice that treats **“tests passed”** or **“PR opened”** as sufficient close **without** per-item verification notes overlaps the **Orchestra Soft** theme (playground **PR #44** — theme-overlap cited as **related Soft**, not Top). **Soft-demote** those slices here:

- Top for this note = **status vocabulary + handback validation** from Wrap-up.
- Soft = board/forge **PASS** columns, vague “LGTM”, or Team OS **ready** shorthand—map to **`done`/`caveat`/`needs_you`** explicitly or log as **Soft UNVERIFIED** close.

---

## Sketch — Smith handback appendix (markdown-only)

Optional appendix fields for Checker (no daemon):

| Column | Type | Notes |
|--------|------|-------|
| `wrapup_title` | string | 1–100 chars — block title |
| `wrapup_report_id` | string | `R-…` footer id |
| `wrapup_replaces` | string \| null | prior `R-…` if revision |
| `area` | string | Same spelling per area (case-insensitive match upstream) |
| `status` | enum | **`done` \| `caveat` \| `needs_you` only** |
| `text` | string | One line (≤200 chars sketch) |
| `note` | string | Required for `caveat`; for `done` when verification required |
| `counts` | string | Optional rendered summary (`✅ n · ⚠️ n · ⬜ n`) — markers configurable upstream |

Cross-links: version **`relied_on`** / stale observe ([2026-11-02/02-sbus-version-check-board-rule.md](../2026-11-02/02-sbus-version-check-board-rule.md), [04-sbus-observe-checklist.md](../2026-11-02/04-sbus-observe-checklist.md)); open PR column ([03-board-open-pr-column.md](../2026-11-02/03-board-open-pr-column.md)) lists **open** work—Wrap-up **`done`** lines still need **their own** verification notes.

---

## Non-goals (2026-11-04 wave9)

- Vendoring **picode-wrapup** or implementing `report.submit` / `report.guide` in playground  
- Rewriting Wrap-up CLI, PiCode extension manifest, or agent executor  
- Touching **AgentBaton PR #10** or any file under **`experiments/2026-11-03/`**  
- Recording reports in Wrap-up DB, Inbox, or cross-agent boards (upstream **Next** — out of scope)

---

## Example fragment (**example** — fictional Team OS row)

```text
**Sprint wave9 handback sketch**
✅ 1 · ⚠️ 1 · ⬜ 1

**experiments/2026-11-04**
- ✅ README #37 row reserved — diff on branch `cursor/wrapup-picode-handback-statuses-285a`; `git show` path verified locally (Soft UNVERIFIED on forge until Checker)
- ⚠️ Origin PR URL — opened this run; merge explicitly out of scope per sprint brief

**Pendente com você**
- ⬜ Merge wave9 Wrap-up note after human review? — agent stops at open PR

R-EXAMPLE000
```

(`R-EXAMPLE000` is **example** only—not a valid base32 id.)
