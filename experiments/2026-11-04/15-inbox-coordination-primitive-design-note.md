# Inbox as coordination primitive — push vs pull for Ork ask-queue (design note)

**날짜**: 2026-11-04  
**Paper**: [The Inbox as a Coordination Primitive for LLM Agent Societies](https://arxiv.org/abs/2610.36264) (Sreedhar et al., arXiv:2610.36264)

**Code**: **NONE** — design note only; no inbox simulator, no 16k-agent society replay, and **no public implementation repository** tied to this paper in playground.

## Paper pointer (citation only; no runs today)

From the public abstract and §1 / §3 on [2610.36264](https://arxiv.org/abs/2610.36264):

- **Scarce resource:** Delivery (push) is cheap; **reading** is costly—each message consumes tokens and displaces prior context.
- **Push:** Messages enter context in **arrival order**; when context fills, the **oldest** content is dropped. Senders decide what the recipient “sees.”
- **Pull:** Messages **wait outside** context in an **inbox**; the recipient’s **private rules** decide what to read and keep before any model judgment.
- **Push failure mode (Soft):** Under push, an agent **leading 20 negotiations** with a full memory **re-proposes options already rejected ~97% of the time**, because it has **dropped the oldest replies** (paper Figure 2 / contribution (1)—**Soft UNVERIFIED** here: no local replay of simulated societies).
- **Inbox necessity (Soft):** Under heavy noisy traffic where first-come-first-read misses every request, an inbox that **reads paid/deposit messages first** still finds **~60%** of needed agents at scales 1k–16k (paper §4.2)—citation only.
- **Four inbox decisions** (paper §4.3–4.4): **what to read**, **what to keep**, **what a sender pays** for attention, **what a reply may say**—best rule depends on traffic and role; no single inbox suits every agent.

Playground **does not** run the paper’s simulated societies, email-network forwarding experiments, or LLM-judgment harness.

---

## Push vs pull — Ork / JJ ask-queue (design memo)

[07](./07-pcp-shared-human-ask-queue-checklist.md) models **portfolio-optimal ordering** of clarification asks (PCP). The inbox paper adds a **separate layer**: even a good queue policy fails if the **human’s working context** is push-fed like an unbounded chat scroll.

| Mode | Ork / JJ ask-queue analog | Risk |
|------|---------------------------|------|
| **Push** | Every @-mention, thread reply, and bot status line **appends straight into** JJ’s active attention slice (Cursor chat, Slack thread, “current run” panel) in arrival order; oldest clarifications **fall off** when context is full. | **Stale re-proposal:** leading Ork/Smith re-offers merge options, scope choices, or PR strategies **already rejected** in earlier replies—paper’s **~97%** push pathology when coordinating many threads at once (**Soft**). |
| **Pull** | Asks land in an **external inbox** (queue row, ticket, board pointer): JJ (or Ork-on-behalf) **pulls** the next row under explicit **reading rules**—not “whatever arrived last wins.” | Requires **memory rules** so served answers and rejections stay addressable after read; otherwise pull degenerates to push-with-extra steps. |

**Norm (sketch):** Treat PCP **portfolio order** as *which pending ask to serve* ([07](./07-pcp-shared-human-ask-queue-checklist.md)); treat inbox **pull** as *what JJ reads into context at all*—orthogonal knobs.

---

## Four decisions → Team OS inbox sketch

Paper inbox \(I_i = (R_i, M_i, d_i, V_i)\). Map to Ork/JJ policy labels only—**no runtime**.

| Decision | Paper meaning | Team OS sketch (Ork ask-queue / JJ attention) |
|----------|---------------|-----------------------------------------------|
| **What to read** \(R_i\) | FIFO, newest-first, deposit-first, category folders, etc. | Queue **serve rule**: `fifo` vs `portfolio_pairwise` vs `deposit_first` on rows in [07](./07-pcp-shared-human-ask-queue-checklist.md) `rule_sketch`—log which rule fired. |
| **What to keep** \(M_i\) | Cache replacement after read—may read now but forget before needed later. | **Decision memory outside chat:** rejections, merge policy picks, and `relied_on` pointers live in **handback / board row**, not only in JJ’s last N chat turns ([01](./01-agentbaton-failure-escalate-handoff.md) `log_path` + artifact pointers). |
| **Sender pays** \(d_i\) | Refundable deposit for read priority under spam. | Optional **attention bond** on low-signal asks (duplicate spec questions, re-opened settled threads)—refund on withdraw-after-search ([07](./07-pcp-shared-human-ask-queue-checklist.md) `withdrawn_before_serve`). |
| **Reply may say** \(V_i\) | Vocabulary limits disclosure (yes/no vs conditions vs private info). | JJ replies tag **`reply_vocab`**: `binary` \| `conditional` \| `pointer_only`—avoid dumping private forge/state into every thread when a **pointer** suffices. |

**Leading-agent note:** When one Cloud Agent run **coordinates many parallel negotiations** (open PRs #19–#25 slots, multi-run sprint), prefer **pull + explicit keep** for rejections; push-only context is where the paper reports **~97%** re-proposal of dead options (**Soft**).

---

## Observation hook (optional log column — design only)

Extend [07](./07-pcp-shared-human-ask-queue-checklist.md) rows when reviewing inbox policy offline:

| Column | Type | Definition |
|--------|------|------------|
| `attention_mode` | enum | `push_chat` \| `pull_inbox` \| `mixed` |
| `reproposal_of_rejected` | bool \| null | Did an agent re-offer an option JJ/run logs already rejected? |
| `inbox_read_rule` | string | Which \(R_i\) sketch applied at serve time |
| `memory_rule_sketch` | string | Where rejection persisted (`board_row`, `handback`, `chat_only`) |

No new automated detector in playground.

---

## Map to sibling sketches

| Inbox idea | Team OS analog |
|------------|----------------|
| Pull inbox vs push context | **Queue outside chat** + PCP ordering ([07](./07-pcp-shared-human-ask-queue-checklist.md)) |
| Drop oldest replies | **Handoff pointers** vs transcript rehydration ([01](./01-agentbaton-failure-escalate-handoff.md)) |
| Escalate / park vs clarify | Impasse tickets ([04](./04-impassebench-escalate-to-human-ticket-schema.md))—not the same row as lightweight asks |
| Shared-repo async send | ParallACT send-early / read-late ([05](./05-parallact-shared-repo-handoff-checklist.md))—inbox layer reduces stale coordination |

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Inbox **implementations**, A2A/MCP protocol changes, or deposit/stake runtime  
- Simulated societies (1k–16k agents) or email-network replay from [2610.36264](https://arxiv.org/abs/2610.36264)  
- Editing [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) bodies  
- **`08-*` … `14-*` files** or README rows **#8–#14** (reserved to open Origin PR #19–#25)  
- PR #10 Copilot trajectory checklist **body** or `experiments/2026-11-03/` paths  

---

## Status

- [x] Planning (design note — Soft, no runtime)  
- [ ] In Progress (Ork/JJ adopt pull inbox + keep rules on next multi-run day)  
- [ ] Complete  

**Next step:** On the next sprint with **≥2 parallel asks**, log `attention_mode` and whether any option was **re-proposed after explicit rejection**; compare push-chat-only days vs pull-inbox rows—no merge required for ops.

**relied_on:** [arXiv:2610.36264](https://arxiv.org/abs/2610.36264) abstract & §1 / §3 / Figure 2 (**Soft UNVERIFIED** for **~97%** re-proposal rate, **~60%** deposit-first recovery, and 16k-scale numbers—no local replay); **no code repository** for this paper in this sketch (**explicit Soft: design note, not runtime**).
