# swrm — claim vs host-verified ledger (report schema sketch)

**날짜**: 2026-11-04  
**Experiment**: **#50** (Usage Sprint wave11 Top #3 — Ork→Smith, Asia/Seoul)  
**Upstream**: [surlymochan/swrm](https://github.com/surlymochan/swrm) (Apache-2.0; renamed from the former **openswarm** repo name — **not** `openswarm-ai/openswarm`, which is a different project and does not host this pin)

## Tier

**Top KEEP-with-caveats**

| Pin | Value |
|-----|--------|
| **License** | Apache-2.0 |
| **Explicit pin SHA** | `7a565c05e656611e4cc3ac2a3a108363160dd9b0` |
| **Tip drift warning** | [surlymochan/swrm](https://github.com/surlymochan/swrm) `main` after the pin may drift **docs-only** (e.g. tip `158e0fbd90cb83e3884528ca306cfb97c1185441` — bench rename cleanup). Playground **does not** float the pin silently; re-read pinned `bin/openswarm` + `SKILL.md` before any production port. |
| **Playground tip (this note)** | `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` |

**Caveats (KEEP):** Minimal Python sketch only—no fleet daemon, `sqlite3` quota reader, backend monolith, or GitHub-label bus port. Names **`adjust_status_for_verify`** and ledger fields are **borrowed for orientation**; behavior here is **Team OS lane logic**, not a copy of pinned swrm shell entrypoints.

---

## Goal

Separate **executor self-report**, **host verification**, and **acceptance** without collapsing them into one boolean. **`rework_of`** links a report to an earlier run (cross-agent memory pointer; not transcript replay).

Pinned swrm already splits **executor `status`** (claim) from **evidence-derived `exec_pass`** and host **`verify_rc`**; this sketch adds an explicit **Team OS three-lane table** and a small `surface_status` helper for playground checkers.

---

## Team OS lanes vs upstream (pin `7a565c05…`) — **on purpose**

| Upstream field / API (swrm pin) | Meaning at pin | Team OS sketch (#50) | Delta |
|---------------------------------|----------------|----------------------|--------|
| `status` (`done` / `partial` / `failed`) | Executor-reported terminal claim | Not modeled as enum; **`exec_pass` bool** = **executor self-claim** pass/fail (Team OS **self-claim lane**) | Sketch collapses status to bool for checklist/tests; **not** a byte-for-byte ledger row |
| `exec_pass` / `exec_pass_reason` | **Evidence-derived** pass from change/read-only output + host `verify` / `verify_rc` (`exec_pass_assessment` in `bin/openswarm`; SKILL: *not* the executor's own report) | Same **field names** in JSON fixtures for familiarity, but sketch stores **`exec_pass` as self-claim only** | **Do not** read sketch `exec_pass` as upstream evidence pass; map upstream evidence pass → `host_verified_pass` + `verify_rc` |
| `verify_rc` / `verify` | Host command result | `verify_rc` int \| null + derived `host_verified_pass` | Aligned |
| `accepted` / `accepted_reason` | Human/policy accept | Same | Aligned (sketch keeps lane separate from verify) |
| `rework_of` | Prior run id | Same | Aligned |
| `adjust_status_for_verify(status, verify)` | Adjust executor **`status`** when verify disagrees (e.g. `partial`→`done` if verify ok) | `adjust_status_for_verify(report)` → **`surface_status`** string from **self-claim vs verify** | **Different signature and output**; inspired by upstream authority-of-verify idea, not a port |

**Sketch invariant (Team OS):** Do not **write** sketch `exec_pass` from `verify_rc` or `accepted` inside this module—that preserves three lanes for Ork checkers. Upstream **computes** its own `exec_pass` from evidence + verify; when ingesting real swrm rows, translate rather than aliasing fields blindly.

---

## Report schema (field table)

| Field | Type | Lane | Meaning |
|-------|------|------|---------|
| `report_id` | string | identity | Stable id for this ledger row |
| `exec_pass` | bool | **self-claim (Team OS)** | Executor **self-claim** pass/fail — **not** upstream evidence-derived `exec_pass` |
| `exec_pass_reason` | string | **self-claim (Team OS)** | Executor narrative for the self-claim |
| `verify_rc` | int \| null | **host-verified** | Host verify exit code; **`null`** = not run (distinct from `0`); JSON booleans rejected |
| `host_verified_pass` | bool \| null | **host-verified** | Derived: `true` iff verify ran and `verify_rc == 0`; else `false`; `null` if verify not run |
| `accepted` | bool | **accepted** | Human or policy acceptance (may waive verify failure) |
| `accepted_reason` | string | **accepted** | Why acceptance applied |
| `rework_of` | string \| null | memory | Prior `report_id` |
| `surface_status` | string | derived | From **`adjust_status_for_verify`** (does not overwrite lane fields) |

---

## `adjust_status_for_verify` behavior

Implemented in [`50-claim-vs-verified-ledger/report.py`](./50-claim-vs-verified-ledger/report.py). Rules:

1. **Compute `host_verified_pass`** from `verify_rc` only (`null` → `null`; int `0` → `true`; other int → `false`; bool `verify_rc` → treat as missing).
2. **If `verify_rc is null`** → `unverified_claim_pass` or `unverified_claim_fail` from self-claim `exec_pass` only.
3. **If verify ran and self-claim matches host** → `aligned_pass` or `aligned_fail`.
4. **If verify ran and they disagree** → **`verify_pass_self_fail`** when host passed (`verify_rc == 0`) but self-claim failed; **`contradicted`** when self-claim passed but host failed (`verify_rc != 0`). (Asymmetric on purpose: only agent-overclaim is labeled `contradicted`.)
5. **If `accepted` is true** → `{base}_accepted` (e.g. `contradicted_accepted`).

Acceptance does not mutate lane fields.

### Truth table (verify ran; before acceptance overlay)

| `exec_pass` (self-claim) | `verify_rc` | `host_verified_pass` | `surface_status` (base) |
|--------------------------|-------------|----------------------|-------------------------|
| true | 0 | true | `aligned_pass` |
| false | 0 | true | `verify_pass_self_fail` |
| true | ≠0 | false | `contradicted` |
| false | ≠0 | false | `aligned_fail` |

---

## Conceptual cross-link (Wrap-up — **not** a demotion)

**Wrap-up experiment #37** / **Origin PR #48** also discuss verified progress and handoff memory. Overlap is **conceptual only**. This note stays **Top**; no Soft demotion because of Wrap-up.

---

## How to run tests (VM evidence)

```bash
cd experiments/2026-11-04/50-claim-vs-verified-ledger
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Re-run after each fold; PR report cites head SHA.

Fixtures: aligned, contradicted, unverified, verify-pass/self-fail, acceptance overlay, rework pointer.

---

## Out of scope

- Monolith / fleet port of [surlymochan/swrm](https://github.com/surlymochan/swrm) (`bin/openswarm`, daemon, backends)  
- `sqlite3` quota reader, fleet schedulers, remote backends  
- GitHub-label bus, DSH / Feishu / SQLite / daemon / headcount integrations  
- Editing `experiments/2026-11-03/**` or open **PR #10** / **PR #11** bodies  
- Soft→Top promotion elsewhere; **no** Soft demotion of this Top note  

---

## Status

- [x] Planning (schema + adjust sketch)
- [x] In Progress (Python fixtures + unittest; Checker fold upstream honesty + lane delta)
- [ ] Complete (no upstream pin re-validation in CI)

**Relied on:** pin `7a565c05e656611e4cc3ac2a3a108363160dd9b0` on **surlymochan/swrm**; playground parent tip `a3d544105a19e325dbbb2b5d7e2c5edfcb156098`.

**Next step:** Diff pinned swrm ledger ingest against this lane table if swrm exports JSON schema.

---

## Checker-ready blurb

> Experiment **#50** (**Top KEEP-with-caveats**): design note + Python sketch under `experiments/2026-11-04/50-claim-vs-verified-ledger/`. Upstream **[surlymochan/swrm](https://github.com/surlymochan/swrm)** Apache-2.0 pin **`7a565c05e656611e4cc3ac2a3a108363160dd9b0`** (explicit; tip may docs-drift e.g. `158e0fb…`). **Team OS lane delta** documents that sketch `exec_pass` is **self-claim**, not upstream evidence-derived `exec_pass`; `verify_rc` / `accepted` / `rework_of` align; **`adjust_status_for_verify`** rule 4 matches code (`verify_pass_self_fail` vs `contradicted`). No fleet/sqlite/label-bus port. README **#50** only. Wrap-up **#37** / Origin **PR #48** conceptual; tier stays Top. Tests: `python3 -m unittest discover -s experiments/2026-11-04/50-claim-vs-verified-ledger/tests -v`.
