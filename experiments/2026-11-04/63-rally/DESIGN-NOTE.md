# Rally (Castor-o7) — Soft design note (observed / declared / verified method only)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint wave13 Soft **#1** (Soft pack **#1**)  
**Upstream (primary method pin):** [Castor-o7/rally](https://github.com/Castor-o7/rally) @ **`842f617d43bd7ecc0afaf4df2d7e4d39c65b934b`** (short: `842f617`) — [`docs/design.md`](https://github.com/Castor-o7/rally/blob/842f617d43bd7ecc0afaf4df2d7e4d39c65b934b/docs/design.md) + [`README.md`](https://github.com/Castor-o7/rally/blob/842f617d43bd7ecc0afaf4df2d7e4d39c65b934b/README.md) @ pin on 2026-11-04.

**License:** **AGPL-3.0-or-later** @ pin ([`LICENSE`](https://github.com/Castor-o7/rally/blob/842f617d43bd7ecc0afaf4df2d7e4d39c65b934b/LICENSE), workspace `license = "AGPL-3.0-or-later"` in [`Cargo.toml`](https://github.com/Castor-o7/rally/blob/842f617d43bd7ecc0afaf4df2d7e4d39c65b934b/Cargo.toml); GitHub license card **agpl-3.0**). Playground borrows **method vocabulary only** under that licence — **no** Rally source vendored.

**Tier**: **Soft KEEP** — **observed / declared / verified** record taxonomy + “say how each thing is known” principles **cite-only**. Service, Postgres, myko, Muster roster integration, and viewer stories **Soft UNVERIFIED** beyond public docs @ pin on 2026-11-04.  
**Soft→Top**: **forbidden** (this note does not promote any Soft sketch to Top).

**Code (playground)**: **NONE** — markdown design note only; **no** `rally` service port, **no** Postgres/**myko** stack, **no** Muster daemon wiring, **no** hash-chain replay or `rally check` in playground.

**Playground tip at authoring**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (default branch at branch cut; history not rewritten).

**Not the method source (name collision only):** [tyroneross/agent-rally-point](https://github.com/tyroneross/agent-rally-point) is a separate **Apache-2.0** repo-local coordination CLI. Its nine-step charter uses **“the host verifies”** for tests/builds — that **verified** is **not** Castor Rally’s **Verified** kind (watchman / non-author check against “done when”). Do not merge the two vocabularies.

---

## Why borrow the method (cite-only; no runs today)

From pinned [README](https://github.com/Castor-o7/rally/blob/842f617d43bd7ecc0afaf4df2d7e4d39c65b934b/README.md) + [design.md](https://github.com/Castor-o7/rally/blob/842f617d43bd7ecc0afaf4df2d7e4d39c65b934b/docs/design.md):

- **Problem:** Multi-team agent work was tracked on a hand-kept board; progress and evidence need a **deterministic ledger** that records **how each fact is known**.
- **Rally role (Castor):** Ledger of progress for a **muster** of agents — claims, story states, evidence, check-ins — **informs** the watchman; it **does not command** teams.
- **Muster vs Rally:** Muster answers reachability / wake; Rally answers **what** is being worked and **how far** — Rally depends on Muster; Muster must work with Rally down (design + README tables @ pin).
- **Playground stance:** Apply **observed / declared / verified** labels in Team OS observation logs — **not** as deployed Rally on Murph, **not** as reproduced hash-chain or Postgres tests.

RAL-* story completion claims in upstream docs are **cite-only**; playground **does not** assert which RAL items are verified in production.

---

## Observed / declared / verified (method — ALLOW scope)

From [design.md § “What Rally can and can't determine”](https://github.com/Castor-o7/rally/blob/842f617d43bd7ecc0afaf4df2d7e4d39c65b934b/docs/design.md) @ pin:

| Kind | Upstream meaning (Soft cite) | Examples @ pin |
|------|------------------------------|----------------|
| **Observed** | Came from a **system**, not from an agent's account of itself | Commit exists, CI passed, session can be woken |
| **Declared** | An **agent or person said so** | “Working on MUS-4”, “blocked on a review” |
| **Verified** | **Someone other than the author** checked it | Watchman confirmed “done when” |

Each record should also carry **who or what** it came from and **when**, so a reader can judge freshness (design.md @ pin). README RAL-11: versioned format **refuses** a record missing kind, source, or time — playground **does not** implement RAL-11.

**Deterministic vs not (Soft cite):** Whether a state change is valid, or a commit exists and names its story and passed CI, can be decided by a program. Whether work meets **“done when”** is **not** deterministic — Rally records **who judged** and **on what evidence** (design.md @ pin).

**Story states (vocabulary — cite-only):** Ready → Claimed → In review → **Verified** / Sent back; **Merged** is a separate field; **Blocked** is what a team **declares** about itself (design.md @ pin).

**≠ tyroneross “verified”:** Agent Rally Point’s step 8 is **host-run tests/builds** recorded as optional evidence on a coordination fact. Castor **Verified** is a **ledger kind** for **non-author** judgment against acceptance criteria — different word, different system.

**Explicit ALLOW boundary:** Document the **three-kind taxonomy**, freshness fields, and principles below in markdown only. **Do not** port ledger replay, Levi claim sync, stall tables as runtime automation, or service routes.

### Principles (README @ pin — method)

- **Say how each thing is known** — every record is observed, declared, or verified.
- **Inform; don't command** — Rally flags possible stalls; watchman decides.
- **Authors don't verify their own work.**
- **No points, scores or weights** — plain facts only.

---

## Soft Team OS analogy (ledger labels; markdown only)

| Castor Rally method (Soft) | Team OS observation hook (no runtime) |
|----------------------------|----------------------------------------|
| **Observed** | Log rows backed by **system artifacts**: CI URL, commit SHA on branch, tool exit code — not model narrative ([06](../06-care-escalate-verified-progress-checklist.md)) |
| **Declared** | Lane **intent**: “working on …”, “blocked on …” — structured sketch, not transcript ([05](../05-parallact-shared-repo-handoff-checklist.md)) |
| **Verified** | Checker / peer **other than author** signed off against stated “done when” — distinct from **`declared`** “done” ([01-mandate-agent-run-checklist.md](../../2026-11-01/01-mandate-agent-run-checklist.md)) |
| **Merged vs Verified** | Landed commit (**observed** merge) ≠ acceptance (**verified**) — keep columns separate (design.md @ pin) |
| **Muster roster labels** | When citing wake/liveness, mirror Muster’s own **observed vs declared** field split in memos — don’t treat `last_activity_at` as proof of life (design.md @ pin) — **no Muster daemon port** |

**Explicit non-promotion:** Do **not** Soft→Top this note into Postgres, **myko**, **Muster daemon**, Levi checkout automation, or a live watchman — conceptual rhyme only.

---

## ALLOW / FORBID (this experiment)

### ALLOW

- Cite [Castor-o7/rally](https://github.com/Castor-o7/rally) @ pin **`842f617d43bd7ecc0afaf4df2d7e4d39c65b934b`** (**AGPL-3.0-or-later**) for **observed / declared / verified** taxonomy and related principles in `docs/design.md` + README.
- Light **Team OS observation** hooks and sibling markdown cross-links under `experiments/2026-11-04/` only.
- **Separate mention** of tyroneross/agent-rally-point **only** to disambiguate the homonym **verified** (Apache-2.0) — **not** as Soft method source.

### FORBID (hard)

- **Full port** of Rally service, ledger writer, hash-chain tooling, Levi integration, viewer, or **Soft→Top** elevation
- **Postgres**, **myko**, **Muster daemon** (and Muster-shim transport assumptions), **SQLite** ledger/cache patterns from any Rally lineage
- **headcount**
- **DSH**, Feishu
- Benchmark replay, `rally check` production claims, or “deployed on Murph” claims in playground
- **Do not touch** open **PR #10** — paths under **`experiments/2026-11-03/`**.
- **Do not touch** merged **PR #11** — [`01-agentbaton-failure-escalate-handoff.md`](../01-agentbaton-failure-escalate-handoff.md) body on `main`.

---

## Sibling links (folder names — not PR numbers)

| Experiment | Link |
|------------|------|
| AgentBaton failure escalate | [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) |
| ParallACT shared-repo handoff | [05-parallact-shared-repo-handoff-checklist.md](../05-parallact-shared-repo-handoff-checklist.md) |
| CARE verified progress | [06-care-escalate-verified-progress-checklist.md](../06-care-escalate-verified-progress-checklist.md) |
| PCP shared-human ask queue | [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) |
| Ask on Demand peer ask (Soft) | [57-ask-on-demand](../57-ask-on-demand/) *(wave12 parallel branch — not on `main` until landed)* |
| Coop ack floor (Top) | [61-coop-ack-floor](../61-coop-ack-floor/) *(wave13 parallel branch — not on `main` until landed)* |
| Brigade claim fence (Top) | [62-brigade-claim-fence](../62-brigade-claim-fence/) *(wave13 parallel branch — not on `main` until landed)* |
| **This folder** | [63-rally](./) |

---

## Checker-ready

| Check | Expected |
|-------|----------|
| Tier | Header states **Soft KEEP** and **Soft→Top forbidden** |
| Primary pin | **Castor-o7/rally @ `842f617d43bd7ecc0afaf4df2d7e4d39c65b934b`** |
| License | **AGPL-3.0-or-later** @ pin |
| Method | Three kinds from **`docs/design.md`** + README — **not** implemented |
| Disambiguation | tyroneross **verified** (host tests) ≠ Castor **Verified** kind |
| Code | **NONE**; no Postgres/myko/Muster/SQLite claims |
| Forbidden scope | Postgres, myko, Muster daemon, SQLite, headcount; no PR #10/#11 edits |
| README | Index row **#63**; goal table matches Castor method |

---

## Status

- [x] Soft KEEP design note (this file; folded from wrong pin)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** If a future **Top** tier needs live ledger replay or service routes, open a **separate** Top doc with verified scope — do not merge this Soft note upward.

**Model (completion summary)**: composer-2.5
