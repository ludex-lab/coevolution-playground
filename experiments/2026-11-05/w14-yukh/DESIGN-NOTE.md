# Yukh coordination — envelope lifecycle checklist (Soft design note)

**Date**: 2026-11-05  
**Lab**: Wave14 Soft **#3** (final Soft in Wave14)  
**Upstream**: [nomed/yukh-coordination](https://github.com/nomed/yukh-coordination) — **Apache-2.0**

**Playground code**: **NONE** — markdown checklist + reading pointers only. **No Top runtime.** Soft→Top forbidden in this folder.

---

## Pin table (authority for citations)

| Item | Value |
|------|--------|
| Repository | https://github.com/nomed/yukh-coordination |
| **Pinned commit** | **`85eb6a005529e2da6fc7151d7409336c18308986`** (`HEAD` / `main` at pin time; message: “Attach preview NATS to edge network (#231)”) |
| License | Apache-2.0 |
| Soft tier (author) | **Soft KEEP** — checklist + reading only |
| Playground base at authoring | `8cf0d98931d6367375313e5a2c5f7adf3f09cfd6` |
| `git ls-remote` | Recorded in [README.md](./README.md) (2026-11-05) |

### Method bullets borrowed (clean-room checklist only)

1. **Thirteen envelope verb/types** — authoritative enum in pin `schema/envelope-0.1.schema.json` (pack copy once said nine; Checker correction: **13**). Mapped to Team OS lifecycle in [CHECKLIST.md](./CHECKLIST.md).
2. **Independent verdict before handoff** — qualification transcript orders `review_request` → **`verdict`** → **`handoff_offer`** → **`handoff_accept`** (`internal/relay/runtime/testdata/four-agent-sanitized.json`). Verdict payload requires `review_event_id`, `evidence_set_digest`, and `reviewer_independent` (`schema/payloads/verdict-0.1.schema.json`). RFC-0001: verdicts are attributed reviewer statements; relay does not infer independence — Team OS checklist still **requires** a standalone verdict row before handoff language.
3. **Immutable evidence refs** — descriptors via `schema/evidence-0.1.schema.json` (URI + digest + declared size); sets hashed per RFC-0001 (`evidence_set_digest`); forbidden inline evidence bodies and credential leakage in the same RFC section narrative.
4. **RFC-0016 reading** — *Resumable fenced-lease handle* — `.context/rfcs/RFC-0016-resumable-fenced-lease-handle.md` (Resume on `FencedLeaseStore`; capability-sealed resume value). **Pointer only** — no lease product in playground from this note.
5. **RFC-0021 reading** — *Lease-acquisition contention response clarification* — `.context/rfcs/RFC-0021-lease-acquisition-contention-response.md` (`409 conflict`; `contended` is not success). **Pointer only** — Team OS may analogize contested claim rows without implementing primitives HTTP.

### FORBID (Wave14 Soft #3)

| Forbidden | Notes |
|-----------|--------|
| Soft→Top | No promotion path from this folder |
| Go / relay / SQLite / NATS / JetStream / daemon | No code port; no vendored adapters |
| Claim/fencing **product** overlapping [playground PR #73](https://cursor.com/codebase/coevolution-lab/playground/pull/73) | Mention as **boundary only** — Brigade owns product sketch |
| DSH / Feishu | Out of scope |
| Vendoring yukh relay adapters | Out of scope |
| Touching playground PR **#78–#82** or their paths | Hard stop for this sprint |

### Honesty (what was opened vs assumed)

| Source | Opened on this VM | Assumed / pin path only |
|--------|-------------------|-------------------------|
| Pin SHA | `git ls-remote` + shallow fetch at `85eb6a0…` | — |
| `schema/envelope-0.1.schema.json` | Enum of 13 types | Full semantic validator not re-run here |
| `documentation/reference/protocol.md` | Signal family table | — |
| RFC-0001 evidence + review prose | Grep + section read | Full RFC not line-audited |
| RFC-0016 / RFC-0021 | Title + decision sections | No Resume/409 implementation |
| Relay runtime / `go test` | **Not executed** | Qualification ordering taken from sanitized JSON fixture |

---

## Author claim (Soft)

| Signal | Value |
|--------|--------|
| Deliverable | [CHECKLIST.md](./CHECKLIST.md) + this note + [NOTICE](./NOTICE) |
| License | Apache-2.0 (upstream at pin) |
| Runnable port | **None** — markdown only |
| Promotion | **Soft KEEP** intent — **no** Soft→Top |

*(Checker verdict section deliberately omitted — Checker fills KEEP / UNVERIFIED.)*

---

## 1) Thirteen-type envelope checklist (Team OS mapping)

Use [CHECKLIST.md](./CHECKLIST.md) as the sprint-facing tick list. Upstream groups (from `documentation/reference/protocol.md`):

| Flow | Types |
|------|--------|
| Presence | `join`, `presence`, `leave` |
| Work | `claim`, `progress`, `release` |
| Questions | `question`, `answer` |
| Review | `review_request`, `verdict` |
| Transfer | `handoff_offer`, `handoff_accept` |
| Evidence | `evidence_verification` (+ descriptor refs on other payloads) |

**Norm for Team OS:** log offline rows with `type`, actor (ork/smith/checker/human), correlation/causation ids, and **`evidence_set_digest`** when the upstream schema requires it — without pretending a relay appended bytes.

---

## 2) Verdict before handoff (ordering gate)

**Borrowed ordering** (pin fixture sequence 9–13):

1. `review_request`
2. **`verdict`** (independent reviewer / `reviewer_independent`)
3. **`handoff_offer`**
4. **`handoff_accept`** (+ successor `claim`, prior `release` as needed)

**Team OS rule:** Smith must not phrase Ork→Checker handoff as complete until Checker’s **verdict row** exists as its own artifact (PR comment, ledger row, or checklist tick) — even if Smith already opened a draft PR.

---

## 3) Immutable evidence refs (checklist rules)

From RFC-0001 Draft 0.1 narrative + pin schemas:

- Cite **URI + digest** (`schema/evidence-0.1.schema.json`); use **`evidence_set_digest`** on review and handoff payloads.
- Treat digest as **content identity**, not automatic truth — verification is a separate **`evidence_verification`** statement.
- Do not paste secrets, inline blobs, or unbounded logs into coordination envelopes.

---

## 4) Reading pointers (no implementation)

| RFC | Pin path | Why read (Team OS) |
|-----|----------|-------------------|
| **RFC-0016** | `.context/rfcs/RFC-0016-resumable-fenced-lease-handle.md` | Vocabulary for **resumable fenced lease** after capability handoff — analog to “don’t re-acquire blindly after restart” on shared claim rows |
| **RFC-0021** | `.context/rfcs/RFC-0021-lease-acquisition-contention-response.md` | **Contention = deterministic non-success** (`409 conflict`) — analog when two agents claim the same artifact ref |

Do **not** implement `FencedLeaseStore.Resume`, primitives HTTP, or JetStream KV from this Soft note.

---

## 5) Boundary: playground PR #73

[PR #73](https://cursor.com/codebase/coevolution-lab/playground/pull/73) (Brigade) explores claim/fencing **product** in playground. **This Soft note** stays checklist-only and does not extend, duplicate, or merge with that product surface.

---

## Siblings (folder names)

| Path | Relation |
|------|----------|
| `2026-11-05/01-coworkos-revision-checked-leases/` | Revision + lease vocabulary (CoworkOS Soft #1) |
| `2026-11-04/40-agent-handoff-ledger-soft-design-note.md` | One-writer handoff ledger analog |
| `2026-11-04/05-parallact-shared-repo-handoff-checklist.md` | Contested artifact checklist |

---

## Status

- [x] Planning (pin + 13-type checklist + RFC reading pointers)
- [x] Soft #3 deliverable (markdown)
- [ ] Checker verdict (external)
- [ ] Complete (post-Checker only)

**Next step:** On multi-agent sprints, walk [CHECKLIST.md](./CHECKLIST.md) before `handoff_offer` language in Smith→Checker transitions.
