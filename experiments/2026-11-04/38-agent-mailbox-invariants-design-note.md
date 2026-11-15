# agent-mailbox — mailbox invariants (design note)

**Date**: 2026-11-04  
**Upstream**: [piedragus/agent-mailbox](https://github.com/piedragus/agent-mailbox) — **MIT**  
**Pinned tip (read-only)**: `2410ecf4eb4cd82116272e053c7610fcc2f913a2` (fetched 2026-11-04; report if `main` moved)  
**Playground base for this sprint folder**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (detached at authoring; unchanged on this branch)

**Code in playground**: **NONE** — markdown design note only; no broker/daemon vendoring, no HTTP wiring.

## Checker verdict (Soft **KEEP-with-caveats**)

| Signal | Value |
|--------|--------|
| License | MIT ([LICENSE](https://github.com/piedragus/agent-mailbox/blob/main/LICENSE)) |
| Tests (Checker pack) | **pytest 44/44** — broker + daemon suites per upstream layout |
| Tests (this VM) | **Soft UNVERIFIED** — `pytest` not installed here; no local run beyond Checker pack |
| Promotion | **Soft KEEP-with-caveats** — **no** Soft→Top flip in this note |

**Caveats (why not Top today):** upstream stack is Flask + SQLite on a single broker host; Team OS has **not** adopted transport or storage. This note copies **behavioral invariants** only for Ork→Smith→Checker and human-in-loop handoffs—not a port plan.

---

## Intent (Team OS)

Use [agent-mailbox](https://github.com/piedragus/agent-mailbox) as a **reference model** for async task mail between agents on different machines: atomic work claiming, visibility when the peer is stuck, and **hard stops** that park automation until a human decides. Map:

| Upstream role | Team OS analog |
|---------------|----------------|
| Identity (`de` / `para`) | Ork, Smith, Checker slots (or Cloud Agent run identities)—not transcript routing |
| Daemon claims `pendiente` | Smith/Checker **claim-once** on a handoff ticket or mailbox row |
| `esperando_humano` | Park + human queue ([04](./04-impassebench-escalate-to-human-ticket-schema.md), [07](./07-pcp-shared-human-ask-queue-checklist.md)) |
| Read receipts + sender alerts | Ork knows Smith **saw** the handoff without polling chat archaeology |

Cross-links (orthogonal): repeat `failure-id` escalate ([01](./01-agentbaton-failure-escalate-handoff.md)); dual-writer repo contention ([05](./05-parallact-shared-repo-handoff-checklist.md)).

---

## Invariant 1 — claim-once

**Problem:** two headless agents poll the same queue and both execute the same task.

**Upstream behavior:**

- `GET /api/mensajes/pendientes?maquina=<identidad>` runs under SQLite **`BEGIN IMMEDIATE`**, selects eligible `pendiente` rows, then **`UPDATE`s them to `tomado`** in the **same transaction** ([`broker/app.py`](https://github.com/piedragus/agent-mailbox/blob/main/broker/app.py) — pendientes handler).
- Eligibility excludes self-claim: `de != maquina` (sender never claims own message).
- Stale claims: `tomado` older than `MENSAJERIA_TOMADO_TIMEOUT_MIN` returns to `pendiente` on the next pendientes pass (OpenRig-style recovery); each rescue counts toward the **3-attempt** path to `fallido`.

**Team OS sketch:** any shared handoff queue (Origin comment, ticket row, or future mailbox) should expose **at-most-one active claimer** per work item, with **timeout re-queue** and **attempt budget**—without requiring SQLite specifically.

**Observation column (optional log row):** `claim_id`, `claimed_by`, `claim_at`, `requeued_after_timeout`, `attempt_count`.

---

## Invariant 2 — read receipts

**Problem:** sender agent burns budget re-asking “did you see my handoff?”

**Upstream behavior:**

- Claim sets **`tomado_en`** (read by recipient identity); success sets **`respondido_en`**.
- `GET /api/mensajes/<id>/recibo` — timeline for one message.
- `GET /api/mensajes/enviados?de=<yo>[&solo_sin_leer=1]` — outbound visibility.
- **`GET /api/estado`** — per-identity `sin_leer`, last invocation summary (ops “ps” view).
- **Sender alerts** (not human blast by default): if unread longer than `MENSAJERIA_SIN_LEER_MIN`, or message lands `fallido`, broker posts an in-thread alert **`de: broker`** to the **original sender**; watchdog runs every `MENSAJERIA_WATCHDOG_SEG`; identities in `MENSAJERIA_HUMANOS` are excluded from alert noise.

**Team OS sketch:** Ork (or coordinator) gets **machine-readable receipt** when Smith/Checker claims or completes—**pointers only** (`handoff_id`, `log_path`, timestamps)—aligned with [01](./01-agentbaton-failure-escalate-handoff.md) “no transcript dump.”

**Observation column:** `handoff_id`, `sent_at`, `read_at`, `completed_at`, `alert_type` (`sin_leer` \| `fallido` \| null).

---

## Invariant 3 — thread-cap → waiting-human

**Problem:** A↔B reply loops forever in agent mail.

**Upstream behavior:**

- Env **`MENSAJERIA_MAX_MSGS_POR_HILO`** (default **10**): on `POST /api/mensajes`, if the thread already has ≥ cap messages, the **new** message is forced to estado **`esperando_humano`** ([`broker/app.py`](https://github.com/piedragus/agent-mailbox/blob/main/broker/app.py) + [`docs/PROTOCOLO.md`](https://github.com/piedragus/agent-mailbox/blob/main/docs/PROTOCOLO.md)).
- **`requiere_confirmacion=1`** at create time also lands in **`esperando_humano`** and **never** appears in `/pendientes`.
- **`esperando_humano`** is **terminal for automation**: no daemon claims it; humans/admins use `/api/mensajes/esperando_humano` or thread GET, then act outside or post continuation.

**Team OS sketch:** cap **ping-pong turns** on a single `thread_id` / PR comment chain; when exceeded, flip run to **`waiting-human`** / park—distinct from a normal clarification ask ([07](./07-pcp-shared-human-ask-queue-checklist.md)).

**Observation column:** `thread_id`, `msg_count_in_thread`, `cap_triggered`, `park_state` (`esperando_humano` analog).

---

## Invariant 4 — `REQUIERE_HUMANO` (upstream spelling)

**Spelling note:** upstream uses Spanish **`REQUIERE_HUMANO:`** (with **`E`**) in the daemon system prompt and tests—not English `REQUIRE_HUMANO`. API/schema fields are Spanish too (`requiere_confirmacion`, `esperando_humano`). Team OS docs may translate labels but should **not silently rename** upstream markers when quoting behavior.

**Problem:** irreversible or ambiguous actions must not proceed on autopilot.

**Upstream behavior:**

- Daemon constant `MARCADOR_REQUIERE_HUMANO = "REQUIERE_HUMANO:"` ([`daemon/daemon.py`](https://github.com/piedragus/agent-mailbox/blob/main/daemon/daemon.py)).
- If headless agent output contains the marker, daemon posts a reply with **`requiere_confirmacion: true`**, records invocation **`resultado: esperando_humano`**, and does **not** treat the turn as success ([`daemon/test_daemon.py`](https://github.com/piedragus/agent-mailbox/blob/main/daemon/test_daemon.py)).
- Same end state as manually flagged delicate sends—human must resolve before automation resumes.

**Team OS sketch:** Checker (or Smith before merge/deploy) emits a **single canonical stop token** in run logs; orchestration maps it to park + ticket—not to “green check” on the handoff.

---

## Explicit non-goals (2026-11-04 wave9)

- **No vendoring** of `broker/` or `daemon/` into playground.
- **No** SQLite port, **no** DSH, **no** Feishu, **no** new transport/daemon wiring in this PR.
- **Do not** edit AgentBaton PR **#10** or bodies under `experiments/2026-11-03/`.
- **Do not** treat this note as approval to run a production mailbox on Team OS infra.

If brainstorming mentions SQLite/DSH/Feishu as “next steps,” treat those as **out-of-scope** for wave9; invariants above are the portable slice.

---

## Status

- [x] Planning (invariants-only design note)  
- [ ] In Progress (no runtime wiring)  
- [ ] Complete  

**Next step:** When parallel Cloud Agents hand off via shared tickets, log claim/receipt/park events against these four invariants—compare offline to upstream `PROTOCOLO.md`; no merge of this doc required for ops.
