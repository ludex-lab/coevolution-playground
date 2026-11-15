# Hush — conversational restraint (Soft design note)

**Date**: 2026-11-04  
**Upstream**: [tanishacodes19/Hush](https://github.com/tanishacodes19/Hush) — **MIT** ([LICENSE](https://github.com/tanishacodes19/Hush/blob/main/LICENSE))  
**Pinned tip (read-only)**: `edc2e68dc6c8da8f2756f20504221f17cdb2b4c4` (fetched 2026-11-04; report if `main` moved)  
**Playground base for this sprint folder**: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` (main at authoring; unchanged on this branch)

**Code in playground**: **NONE** — markdown Soft design note only; no Hush API/decider vendoring, no Slack/Teams wiring, no production restraint gate.

## Checker verdict (Soft **KEEP**)

| Signal | Value |
|--------|--------|
| License | MIT |
| Upstream tests (README claim) | **227** unit/integration/audit tests under `tests/` (offline mocks per upstream docs) |
| Tests (this VM) | **Soft UNVERIFIED** — Hush not installed or executed here |
| Promotion | **Soft KEEP** — theme/pattern borrow only; **no** Soft→Top flip in this note |

**Soft framing:** Hush is a **decision-first restraint engine** for group chat: evaluate addressing and context **before** invoking a text model. Team OS may borrow the **SILENT / SPEAK / ASK** gate and “restrain by default” norm for multi-agent channels—not a claim that playground runs Hush or that upstream metrics generalize without caveats (upstream documents template overlap on the historical test split).

---

## Core upstream pattern (citation only)

From [Hush README](https://github.com/tanishacodes19/Hush/blob/main/README.md) at tip:

```text
Incoming Message + History → Decision Service → SILENT | SPEAK | ASK
SILENT → bypass generation (0 gen calls)
SPEAK  → generate direct helpful reply when addressed + sufficient context
ASK    → generate one concise clarifying question when addressed but underspecified
```

**Two-tier addressing (invariant sketch):** Tier 1 — authoritative metadata (`mentions`, `reply_to` assistant). Tier 2 — text fallback only when metadata absent (name/handle at turn start, explicit role request). Human-to-human threads and third-person mentions stay **not addressed** even if natural language contains “hush”.

**Production note (upstream):** default decider mode loads a trained restraint classifier artifact; stub/real modes exist for dev and integration—playground **does not** select or ship any of these modes.

---

## Intent (Team OS — Soft analogy only)

Map **quiet-channel / suppressed-noise** coordination lightly to Ork→Smith→Checker **as observation policy**, not as deployed roles:

| Hush action | Soft Team OS analog |
|-------------|---------------------|
| **SILENT** | Ork (or any coordinator slot) **does not post** while Smith↔Checker or human↔human solve without needing orchestration; Cloud Agent run stays off the “speak” path when not addressed. |
| **SPEAK** | Addressed agent (often **Smith** executor) responds with scoped work output when mandate + context suffice—after a **decide** step, not on every channel event. |
| **ASK** | At most **one** focused clarification ([07](./07-pcp-shared-human-ask-queue-checklist.md) withdrawable ask; distinct from [04](./04-impassebench-escalate-to-human-ticket-schema.md) park/impasse tickets). |
| Addressing tiers | Prefer **machine-readable routing** (mention, reply-to, ticket assignment) over parsing free chat for coordinator reflex replies. |

**Cross-links (orthogonal):** repeat `failure-id` escalate ([01](./01-agentbaton-failure-escalate-handoff.md)); deception/asymmetry observation ([02](./02-four-bridges-deception-observation-checklist.md)); shared repo handoff contention ([05](./05-parallact-shared-repo-handoff-checklist.md)).

---

## Observation columns (optional log row)

When borrowing the pattern in Team OS logs (markdown-only today):

| Column | Meaning |
|--------|---------|
| `restraint_action` | `silent` \| `speak` \| `ask` |
| `addressed_to` | slot id or `none` |
| `addressing_tier` | `metadata` \| `text_fallback` \| `none` |
| `generation_used` | bool (mirror upstream: false on silent) |
| `run_id` / `log_path` | pointer only—no transcript dump |

---

## Non-goals (this note)

- No vendoring of Hush backend, classifier artifact, or frontend chat UI.
- No claim that playground production Slack/Origin bots implement Hush deciders.
- No Soft→Top promotion; no merge of this sketch into runtime config.
- **PR #10** and **`experiments/2026-11-03/`** untouched by this wave.

---

## Pointers

| Item | Link |
|------|------|
| Repository (MIT) | https://github.com/tanishacodes19/Hush |
| Decision / action taxonomy | [README §1](https://github.com/tanishacodes19/Hush/blob/main/README.md) |
| Addressing architecture | [README §2](https://github.com/tanishacodes19/Hush/blob/main/README.md) |
| Decider modes / config | [README §3](https://github.com/tanishacodes19/Hush/blob/main/README.md) |
