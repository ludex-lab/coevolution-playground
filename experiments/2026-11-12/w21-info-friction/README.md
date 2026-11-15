# w21-info-friction

Busy is not progress: when recurrent evidence brings no new resolution,
gathering stops fail-closed. **Soft** method sketch inspired by
[arXiv 2611.14111](https://arxiv.org/abs/2611.14111), "Model-Free Runtime
Measurement of Task-Relevant Information" (Dimitris Panagopoulos, Adolfo
Perrusquía, Yang Xing, Weisi Guo; v1, submitted 10 Nov 2026; primary
category cs.RO, cross-listed cs.AI). Acquisition-State Telemetry (AST) is
the name of the paper's method, not its title.

Paper licence: arXiv non-exclusive distribution licence
(http://arxiv.org/licenses/nonexclusive-distrib/1.0/). Method-borrow only.

Code disclosure: the abs page Comments field says "Code available", but
the abs page gives no link. The code is UNVERIFIED and unlocated, and none
is used here.

This is a method sketch, not law, policy or a team rule, and not a
reproduction of the paper. Status: Soft (a Soft pick, not promoted). The
fixtures are synthetic. The paper's eight-domain and reinforcement
learning results are `on_unmeasured` here (`domain_results()` says so);
the authors' claims sit only in `paper_evidence.json`, quoted verbatim
from the abstract and marked UNVERIFIED. Standard library only: no
network, no model, no files written.

## Pure function, no monitor

The paper describes a monitor that emits real-time signals. This sketch
has no monitor loop, thread, sleep or clock.
`info_friction.evaluate(task, observations, now)` is a pure function over
a fixture observation sequence, evaluated at the caller's `now`.

A task declares:

| field | meaning |
|---|---|
| `requirements` | outstanding requirement ids (non-empty, unique) |
| `friction_bound` | how many recurrent observations in a row are tolerated |
| `deadline` | positive integer step on a toy clock |
| `on_expiry` | `HOLD`, `ESCALATE` or `DENY` |
| `novelty_rule` | `evidence_key` or `declared` (the fixture rule for "new evidence") |

A missing `friction_bound`, `on_expiry` or `novelty_rule` is a
`config_error`; so is any invalid value, a `str` subclass or a `bool`
included.

Each observation names its `evidence` and may name a requirement it
`resolves`. Every counted observation is one of:

- `resolved`: it resolves a requirement that was still unresolved
  (progress: the unresolved count goes down; friction resets to 0);
- `explore`: no new resolution, but the evidence is new under the
  declared rule (purposeful exploration; friction resets to 0);
- `recurrent`: no new resolution and the evidence is not new
  (friction goes up by 1).

The declared novelty rule decides "new": under `evidence_key`, evidence is
new when its key has not been seen earlier in the sequence; under
`declared`, each observation carries a fixture label `novel` (exact
`bool`). Re-resolving a requirement already resolved is no new
resolution.

| decision | reason | when |
|---|---|---|
| `SUCCESS` | `all_resolved` | `now` is before the deadline and every requirement resolved before the bound is passed |
| `STOP` | `friction_bound` | `now` is before the deadline and friction went past `friction_bound`: fail-closed, no success, later observations not counted |
| `CONTINUE` | `gathering` | neither of the above and `now` is before the deadline |
| `HOLD` / `ESCALATE` / `DENY` | `expired` | `now` is at or after the deadline: the declared `on_expiry`, whatever the observations say (expiry guard) |
| `REJECT` | `config_error` | malformed input |

On expiry the decision is the module's own constant, never the caller's
object, and never `SUCCESS`, `CONTINUE` or `STOP`. Observations at or
after the deadline do not count; observations after success are not counted
(post-completion activity is muted). The record's `signals` holds
`(t, kind, unresolved_count, friction)` per counted observation.

Inputs are checked by exact type (`type(x) is dict`, `list`, `str`, `int`,
`bool`). `evaluate()` does not raise: any internal failure is `REJECT`
with `config_error`. `task_id` is read once, after the task is validated,
and a `config_error` record never echoes it (its `task_id` is `None`).
Every task and observation field is read once, by a constant subscript
or `.get`. Two tests pin this: a source (AST) check of `info_friction.py`
that bans other reading paths on the caller's mappings, and a mapping
that counts its reads and flips `novel` after the first one. Neither is a
proof against every dynamic path (see Limits).

## Expiry guard: an expiry is final

Event times `t` are asserted by the caller; this pure function has no
receipt clock. Without a guard, a later call could present evidence
backdated to before the deadline and turn an earlier `HOLD` into
`SUCCESS` or `STOP`. Silence is not consent, so the sketch resolves an
expiry to the declared `on_expiry` and nothing else: any call with `now`
at or after the deadline returns `on_expiry`, whatever the observations
say. The observations are still validated (malformed input is still
`config_error`), and `unresolved`, `friction` and `signals` still
describe the counted observations, as information only; they never
change the decision.

Consequences, by design:

- a `SUCCESS` or `STOP` is read from a call made before the deadline;
  the same history evaluated at or after the deadline returns
  `on_expiry`;
- `STOP` stays final while `now` is before the deadline (appended
  observations are not counted after it);
- no history can move a call at or after the deadline away from
  `on_expiry`, so a timed-out refusal cannot be overturned.

This is simpler than a receipt-time field in the spirit of
`w14-arc-grammar`'s receipt liveness: in a pure function such a field
would be caller-asserted too, so it would not close the gap on its own.

## Done-when (box tests)

- A resolving observation lowers the unresolved count and does not trip
  the bound.
- A repeat-only loop trips friction and cannot declare success, even if a
  resolving observation follows.
- New but non-resolving evidence (exploration) is told apart from
  recurrent evidence by the declared rule, under both rules.
- Success only when every requirement is resolved.
- A call with `now` at or after the deadline returns the declared
  `on_expiry`, for all three values, regardless of prior or later
  observations, including after STOP or SUCCESS; a missing friction
  bound or `on_expiry` is `config_error`; nothing is dispatched on
  timeout.
- An expiry is final across calls: evidence backdated to before the
  deadline cannot turn it into a success or a stop.
- The eight-domain / reinforcement learning results are `on_unmeasured`.
- No model, no clock, no thread: the module imports nothing.

`python3 -B fixtures.py` prints the 14 hand-written episode rows. These
describe our fixtures only; they say nothing about any robot, model or
domain.

## How this differs from w14-arc-grammar and w14-phase-deadline

- `w14-arc-grammar` (experiments/2026-11-05) validates the shape and
  phase order of status reports (`started`, `milestone`, `heartbeat`,
  `done`, `blocked`), gates heartbeats by a cadence, and tracks
  receipt-time liveness. A heartbeat there shows the reporter is alive;
  that README rules out using heartbeat silence as stall forensics.
  Nothing there asks whether the events resolve any requirement.
- `w14-phase-deadline` (experiments/2026-11-05) computes per-phase time
  budgets, idle due times (silence since the last event) and bounded
  extensions. It measures time and silence, not what the events carry.
- New here: recurrent evidence with no requirement gain. A run can emit
  fresh events on time, never go idle and stay well inside its budget,
  and still be stuck, because each observation repeats evidence already
  seen and resolves nothing. Friction counts exactly that, and the
  declared novelty rule stops purposeful exploration (new evidence, no
  resolution yet) from being counted as stagnation. The `on_expiry`
  surface is shared with earlier silence-is-not-consent sketches and is
  not the new part.

## Files

- `info_friction.py`: validation, `domain_results()` and
  `evaluate(task, observations, now)`.
- `fixtures.py`: two synthetic tasks (one per novelty rule), 14 episodes
  and the hand-written expected table.
- `test_info_friction.py`: unittest suite.
- `mutants.py`: code mutants (source snippets of `info_friction.py`
  swapped in memory) and world mutants (fixture changes). Each must make
  the suite fail.
- `paper_evidence.json`: the authors' claims with verbatim abstract
  quotes and the Comments field, UNVERIFIED.
- `NOTICE`: credit, licence and the code disclosure.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The quote test reads the source copies named in `paper_evidence.json`
from the directories listed in `$W21FRICTION_SOURCES` (separated by the
OS path separator); it skips when that is unset.

## Limits

- Requirements, resolutions and novelty are given as fixture data. Mapping
  raw observations to requirements (the paper's domain interface) is out
  of scope.
- Friction here is an integer count of recurrent observations in a row,
  not the paper's continuous signal.
- The deadline is a step count on a toy clock, not wall time.
- Novelty can be spoofed until the deadline. Friction is only as strong
  as the novelty key: under `evidence_key` any byte-different string (a
  nonce, a case, whitespace or Unicode variant) counts as new, and under
  `declared` a self-declared `novel` label resets friction. One fresh key
  every `friction_bound + 1` steps holds friction down indefinitely. The
  mandatory deadline is the backstop: it returns `on_expiry`, never
  success.
- The expiry guard relies on the caller's `now`. Event times and `now`
  are both caller data; the guard only makes the outcome at or after the
  deadline independent of the observations presented.
- The read-once tests are pattern checks. The source check bans the
  reading shapes it names (`dict.get(task, ...)`, `dict(task)`,
  `.items()`, helpers, aliases, `locals()`, `operator` and similar) in
  this module's text; a read through a path it does not name, or code
  outside this module, is not covered. The counting mapping sees
  subscript and `.get` reads only, not reads through C-level `dict`
  methods.
