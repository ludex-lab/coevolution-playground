# w21-plan-changing-ask

Ask for the fact that changes the plan, not just any clarification. This
folder is a small, deterministic method sketch inspired by
[arXiv 2611.13015](https://arxiv.org/abs/2611.13015), "From Questions to
Decisions: Benchmarking How LLM Agents Acquire Decision-Relevant
Information from Human Beings" (Yuhan Tang, Ke Fan, Xinkai Zou, Baichuan
Mo, Kangxin Cui, Ao Qu, Ou Zheng, Jiangbo Yu, Haris N. Koutsopoulos,
Jinhua Zhao, Yuan Zhou; v1, submitted 9 Nov 2026). Ask2Decide is the name
of the paper's benchmark. The abstract notes: "This is ongoing work and
will be updated."

Paper licence: arXiv non-exclusive distribution licence
(http://arxiv.org/licenses/nonexclusive-distrib/1.0/). Method-borrow only;
code UNVERIFIED (none linked on the abs page, none used).

This is a method sketch, not law, policy or a team rule, and not a
reproduction of the paper. The fixtures are synthetic. No figure from the
paper is reproduced or re-claimed here; the authors' figures sit only in
`paper_evidence.json`, quoted verbatim from the abstract and marked
UNVERIFIED. Standard library only: no network, no model, no files
written.

## The task

A task is a partial request plus facts held by an operator. Each fact has
a declared fixture label:

| label | meaning |
|---|---|
| `plan_changing` | the plan is wrong or infeasible without this fact |
| `inert` | worded like a plan-changing fact, but the plan does not depend on it |

The labels are fixture declarations. There is no optimality solver here:
which plan is optimal is `on_unmeasured` (`optimality()` says so for
every task), and so are the paper's solver-optimal plans. A fact with no
label makes the whole task `on_unmeasured`; it never resolves to `ACT`.

The agent's moves are `ask(fact)` and `act`; the operator's move is
`answer(fact)`. `plan_ask.decide(task, trace, now)` returns one record:

| decision | reason | when |
|---|---|---|
| `ACT` | `valid` | `act` before the deadline, every `plan_changing` fact answered before it |
| `REJECT` | `missing_plan_changing` | `act` before the deadline with a `plan_changing` fact unanswered (listed in `missing`) |
| `WAIT` | `awaiting` | no `act` yet and `now` is before the deadline |
| `HOLD` / `ESCALATE` / `DENY` | `expired` | `now` reached the deadline with no valid `act` before it: the task's declared `on_expiry` |
| `REJECT` | `on_unmeasured` | a fact has no label |
| `REJECT` | `config_error` | any malformed input |

Asking is not knowing: an `ask` with no `answer` does not count. Answers
and acts at or after the deadline do not count.

## Silence is not consent

Every task declares a positive integer `deadline` and an `on_expiry` in
{`HOLD`, `ESCALATE`, `DENY`}. A missing `on_expiry` is a `config_error`, and
so is any other value, a `str` subclass included. On expiry the decision
is the module's own constant, never the caller's object, and never
`ACT`: there is no dispatch on timeout.

## Input checks

Inputs are checked by exact type (`type(x) is dict`, `list`, `str`,
`int`), so `bool` deadlines, `int` subclasses, `str` subclasses and
`dict` subclasses are `config_error`. Unknown fields, unknown fact ids in
a trace, an answer with no earlier ask, times that go backwards or run
past `now`, and any event after `act` are `config_error`.

No part of the input is read before the checks that guard it: every
mapping (the task, the facts, each fact, each event) has all of its keys
confirmed as exact `str` before any lookup, so no caller-defined
`__eq__`, `__hash__` or other method runs inside `decide()`. A key that
merely hashes like a field name is rejected unread. The `task_id` is
echoed only after the task has passed validation; on a task-level
`config_error` it is `None`.

`decide()` does not raise on any input: every `Exception` inside it,
`RecursionError` and `MemoryError` included, becomes `REJECT` with
`config_error`, and that fallback record is a literal that needs no
further call. Runtime signals that do not come from the input
(`KeyboardInterrupt`, `SystemExit`) are left to propagate. If the
interpreter has no recursion headroom to enter `decide()` at all, the
`RecursionError` is raised at the call site, before `decide()` runs.

## Done-when (box tests)

- (a) `act` with any `plan_changing` fact missing is `REJECT`.
- (b) Asking only `inert` facts still cannot validly `act`.
- (c) Asking the `plan_changing` facts, with answers, then `act` is `ACT`.
- (d) No LLM: stdlib imports only, no network or process modules.
- (e) Deadline with no answer returns the declared `on_expiry`
  (`HOLD`/`ESCALATE`/`DENY`), never `ACT`; a missing `on_expiry` or an
  invalid one (a `str` subclass included) is `config_error`; the result is
  the module's own constant.
- Unlabeled fact: `on_unmeasured`, never `ACT`.

`python3 fixtures.py` prints the 27 scripted rows (3 synthetic tasks x 9
scripted strategies). These rows describe our fixtures and hand-written
scripts only; they say nothing about how any model behaves.

## Neighbours (dupe check)

- `w20-plan-change-notice` (experiments/2026-11-11): acknowledging an
  objective change is not acting on it. That sketch is about a notice the
  agent already received; this one is about which missing fact the agent
  must go and get. Ack is not act; ask is not know. That sketch already
  has a declared-wait `on_expiry` with `config_error` when it is missing
  (the silence doctrine); this folder reuses that doctrine with
  `HOLD`/`ESCALATE`/`DENY` and adds nothing new there. The new part is
  which missing fact must be fetched: `plan_changing` versus a similarly
  worded `inert` one, which w20 has no notion of.
- PR #119 `mb-fail-closed-deputy` (experiments/2026-11-12, open): missing
  evidence refuses. Low-medium overlap. The delta here is which missing
  fact changes the plan: an `inert` fact can stay missing, a
  `plan_changing` one cannot.
- `w20-fidelity-audit` (experiments/2026-11-11): a check vouches only for
  the artefact it ran on (claim vs artefact). Here the question is whether
  the plan had the facts it depends on.

## Files

- `plan_ask.py`: validation, `optimality()` and `decide(task, trace, now)`.
- `fixtures.py`: three synthetic tasks, scripted strategies and the
  hand-written expected table.
- `test_plan_ask.py`: unittest suite.
- `mutants.py`: code mutants (source snippets of `plan_ask.py` swapped in
  memory) and world mutants (fixture changes). Each must make the suite
  fail.
- `paper_evidence.json`: the authors' figures with verbatim abstract
  quotes, UNVERIFIED.
- `NOTICE`: credit and licence.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The quote test reads the abstract copy named in `paper_evidence.json`
from the directory in `$W21ASK_SOURCES`; it skips when that is unset.

## Limits

- Labels are given, not derived. Judging whether a real fact changes a
  real plan needs a solver or a domain model, which is out of scope.
- No model and no human in the loop; the agents and the operator are
  scripts.
- The deadline is a step count on a toy clock, not wall time.
- With no `plan_changing` facts (no facts at all, or only `inert` ones),
  acting at once is `ACT`: the rule asks for nothing it does not need.
  Whether a task really has no plan-changing fact rests on the labels.
- `answer` events come from the caller's trace and are not
  authenticated, so a caller can write an operator answer that no
  operator gave. Authenticating answers is out of scope here.
- `decide()` reads the trace in place and takes no snapshot; a caller
  that changes the trace from another thread during the call gets a
  result for whatever it iterated.
