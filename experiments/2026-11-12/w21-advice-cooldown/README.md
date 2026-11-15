# w21-advice-cooldown

Soft. Reused advice should be checked and rationed: send a suggestion
only when a micro-contract for the tool applies and the suggested call
passes it, the same advice id is not still in cooldown, and the token
budget covers it. A contract violation fails closed, and an empty budget
never turns into an implicit dispatch.

This is a method sketch, not law, policy or a team rule. It borrows one
idea from:

Zhiyuan Huang, Shengan Zheng, Chenghu Yang, Song Zhang, Lingyun Li, Chen
Yu, Weiquan Huang and Linpeng Huang. "Synapse-Control: Making Agent
Experience Actionable with Lightweight Runtime Control". arXiv 2611.13615
v1, <https://arxiv.org/abs/2611.13615>. Licence: arXiv non-exclusive
distribution, http://arxiv.org/licenses/nonexclusive-distrib/1.0/.
Method-borrow only. Code UNVERIFIED: the abs page links no repository.

This is not a runtime port; no classifier. The upstream describes an
agent runtime with a control plane and a fine-tuned scoring model. Here
there is one pure function, no loop, no clock, no thread, socket, port or
daemon, and no model of any size. Candidates are ordered by the library's
own declared order, not scored. Clean-room Python 3 standard library,
synthetic hand-declared fixtures, no network, no files written.

## `select_advice(state, history, budget, now)`

- `state`: `{tool, args, contracts, advice, pending?}`. `contracts` maps a
  tool to `{required: [arg], options: {arg: [value]}}`. Each advice item is
  `{id, tool, when_missing, args, tokens, cooldown}`.
- `history`: past sends `[{advice_id, at, tokens}]` (the caller's record
  of earlier guidance).
- `budget`: `{limit}` in tokens; spent = sum of history tokens.
- `now`: an integer the caller supplies. Nothing reads a clock.

For each advice item in order:

1. Rule shortlist: same tool, and `when_missing` (if set) absent from the
   planned args. Otherwise skipped.
2. Relevance: no contract for the tool gives `no_contract`; not sent.
3. Contract: the suggestion's args are merged into the planned args. A
   required argument still missing gives `required_arg_missing`; an option
   value outside the declared list gives `invalid_option`. Refused.
4. Cooldown: the same advice id (exact string) sent less than `cooldown`
   ticks ago gives `in_cooldown`; suppressed.
5. Budget: `tokens` above the remaining budget gives `budget_exhausted`;
   not sent.
6. Otherwise `send`, and no later item is tried.

When nothing is sent the decision is `no_send` with the first candidate's
outcome as the reason (`no_candidate` if none was shortlisted). The record
lists every candidate tried and its outcome.

A pending decision `{id, deadline, on_expiry}` must declare `on_expiry`
as `HOLD`, `ESCALATE` or `DENY`; missing or anything else is a
`config_error`. When `now` is at or past the deadline (`now >= deadline`)
the decision is the declared action, reason `expired`, and nothing is
sent: a pending item at its deadline never sends. Nothing acts on a
timeout; it only resolves to the declared `on_expiry`.

Every input is checked by exact type (`type(x) is str`, `dict`, `list`,
`int`). Unknown fields (such as a score), duplicate ids, history times
after `now` and subclasses that pretend to equal valid values are a
`config_error`. `select_advice()` catches internal errors and returns
`config_error`; it never raises and does not mutate its inputs.

## What the fixtures show

`fixtures.py` holds 15 named cases with hand-written expected outcomes
and a declared 10-tick timeline (one search state, a 40-token hint with
cooldown 3, budget 120): sent at ticks 0, 3 and 6, suppressed at the six
ticks between, and `budget_exhausted` at tick 9. These counts describe the
fixture only. The authors' own benchmark figures are quoted, attributed
and marked UNVERIFIED in `paper_evidence.json` only; we have not checked
them and do not claim them.

## Not a duplicate of (low-medium overlap)

- `w18-skill-assurance` (2026-11-09): contract-derived assurance that
  rejects a skill breaking its declared boundary before registry entry.
  Its contracts gate what enters a library once. Here a micro-contract is
  checked on every suggested call at send time, and a pass is still
  rationed by cooldown and budget.
- `w14-phase-deadline` (2026-11-05): an MIT port of pi-toolkit phase
  deadlines. There `retry_cooldown` is a run phase name: one row of its
  port table maps it to pi-toolkit's `retry_backoff`, and `deadline.py`
  (lines 103-104) times that phase by the idle budget. It is a deadline
  timer for a phase. Here the cooldown is per advice id and suppresses a
  repeated send of that id, alongside a token budget and the contract
  check.
- `53-shut-up-budget-cooldown` (2026-11-04): the closest prior sketch, an
  outbound gate (`OutboundBudgetCooldownGate`) that caps the number of
  sends (`budget_max`) and enforces one minimum gap between any two sends
  (`cooldown_s`). Differences: its cooldown is one global gap, here it is
  per advice id; its budget counts sends, here it is a token sum over a
  caller-supplied history; it has no micro-contract check, no rule
  shortlist and no pending decision with a declared `on_expiry`; it is a
  stateful dataclass with float seconds that records each send and a
  two-value outcome enum, here one pure function over exact-int ticks
  that stores nothing.

## Files

- `advice_cooldown.py`: `validate`, `check_contract`, `select_advice`.
  Imports nothing.
- `fixtures.py`: declared cases and the timeline; `python3 fixtures.py`
  prints the timeline.
- `test_advice_cooldown.py`: unittest suite, including AST checks that
  the module imports nothing and that the module and fixtures have no
  `while` loop, async code, sleep, thread, socket, process or HTTP use.
- `paper_evidence.json`: paper metadata and verbatim abstract quotes,
  UNVERIFIED.
- `mutants.py`: 46 code mutants of the module and 22 world mutants of
  the fixtures, tests, `paper_evidence.json` and the day index; each must
  make the suite or `fixtures.py` fail. It is the only file that starts a
  process (the suite, in a temporary
  `experiments/2026-11-12/w21-advice-cooldown/` copy with the day index at
  `../README.md`, removed afterwards). It reads the day index the same way
  the tests do.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest -v
python3 -B fixtures.py
python3 -B mutants.py
```

The quote check reads the abstract copy named in `paper_evidence.json`
from the directory in `$W21AC_SOURCES`; with the variable unset (the
normal case) that one test is skipped.

The day-index tests read `experiments/2026-11-12/README.md`: in the repo
layout that is `../README.md` (picked when the parent folder is
`2026-11-12` and the file opens with the day header); in a flat draft
copy it is `_day/README.md`. If neither exists those tests fail.

## Limits

- Fixtures are synthetic; no agent, benchmark or real tool is involved.
- Advice relevance is a declared rule (tool match, missing argument), not
  learned or scored. Whether advice helps is out of scope.
- The history is supplied by the caller; this sketch holds no state
  between calls and stores nothing. Cooldown and budget hold only
  relative to an honest history.
- Cooldown is keyed by the exact advice id string, not by content. The
  same suggestion under a new id, or an NFC/NFD lookalike id that renders
  the same, is a different id and can be sent inside the first one's
  cooldown. Ids are not normalised; the library is caller config.
- A pending item at its deadline (`now == deadline`) already resolves to
  its declared `on_expiry`; only `now < deadline` can send.
- The static AST and function-name checks in the test file are a guard,
  not a proof: a classifier or threshold inside a permitted function, a
  `getattr` or `globals()` lookup, or a lambda would evade them. The real
  classifier guard is the exact-field validation (an unknown field such as
  a score is a `config_error`). The shipped module is clean by those
  checks and contains none of these.
