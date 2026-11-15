# Team OS — envelope lifecycle checklist (13 verbs)

**Source vocabulary (pin):** `schema/envelope-0.1.schema.json` @ [nomed/yukh-coordination](https://github.com/nomed/yukh-coordination) `85eb6a005529e2da6fc7151d7409336c18308986`  
**Playground use:** offline Ork→Smith→Checker rows — **not** a relay transcript.

Mark each phase before treating a work item as closed. Order below is **typical**, not every sprint uses every row.

## Presence lane

- [ ] **join** — participant admitted to the channel/session for this work URI.
- [ ] **presence** — bounded liveness (`valid_until > observed_at` in upstream schema semantics).
- [ ] **leave** — participant exits without implying work completion.

## Work lane

- [ ] **claim** — one contender asserts writer scope on the work URI (Team OS: claim board / branch ownership row).
- [ ] **progress** — durable statement of work state (correlates to parent claim).
- [ ] **release** — prior holder relinquishes claim without silent successor inference.

## Conversation lane

- [ ] **question** — blocked or ambiguous scope surfaced with correlation id.
- [ ] **answer** — response bound to the question event (causation chain).

## Review lane (independent before transfer)

- [ ] **review_request** — criteria + **`evidence_set_digest`** frozen; set **`independence_required`** when Checker must not be the author.
- [ ] **verdict** — **`review_event_id`** points at exactly one review request; outcome is **`pass` | `fail` | `inconclusive`** with **`reviewer_independent`** recorded.  
  - **Gate:** do **not** emit Team OS “handoff ready” until a **standalone verdict row** exists (upstream qualification orders **verdict before `handoff_offer`** — see pin `internal/relay/runtime/testdata/four-agent-sanitized.json`).

## Transfer lane (after verdict)

- [ ] **handoff_offer** — boundary + evidence-set digests on the offer; parent is claim, not review.
- [ ] **handoff_accept** — successor accepts one offer; no implicit ownership without accept + successor **claim**.

## Evidence lane

- [ ] **evidence_verification** — verifier reports against **`referenced_event_id`** + descriptor digest rules (**reading** RFC-0001 § evidence — no URI fetch in this Soft folder).

## Immutable evidence refs (checklist rules)

- [ ] Every cited artifact is an **immutable ref**: URI + **`sha-256`** digest (+ optional revision string) — no inline bodies, secrets, or “latest” without digest.
- [ ] **`evidence_set_digest`** on review/handoff rows matches the **ordered descriptor set** at freeze time; changing bytes ⇒ new digest, not silent edit.
- [ ] Verification events **add** statements; they do **not** rewrite prior envelopes (RFC-0001 narrative).

## Explicitly out of scope here

- [ ] No Soft→Top promotion from this checklist.
- [ ] No claim/fencing **product** — boundary: [playground PR #73](https://cursor.com/codebase/coevolution-lab/playground/pull/73) (Brigade); this note borrows **verbs only**.
