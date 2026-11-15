# w21-unused-contradiction

A flag is not a repair. When a trajectory already holds evidence against
something the agent believes or did, the run may not close as success
until a later step removes that deviated state, and the state must stay
removed: a later belief or act that asserts it again is a relapse and
fails. Flagging the deviation is not enough, and neither is a repair that
lands on another state or before the evidence arrived.

This is a method sketch, not law, policy or a team rule. It borrows one
idea from:

Shaohuang Wang, Jinghao Wen, Xulei Zhang and Xun Jiao.
"Dependable Long-Horizon LLM Agents: A Trajectory-Centered Empirical Study
of Where Errors Enter and Which Controls Reach Them". arXiv 2611.13254 v1,
<https://arxiv.org/abs/2611.13254>. Licence: arXiv non-exclusive
distribution, http://arxiv.org/licenses/nonexclusive-distrib/1.0/.
Method-borrow only. Code UNVERIFIED: the abs page says protocol, records
and scripts are included but links no repository.

It is not a reproduction of that paper. Clean-room Python 3 standard
library, synthetic hand-declared fixtures, no network, no model in the
loop, no files written.

## Episode trace

An episode is `{episode_id, contradiction_labels, task_done, steps, wait?}`.
Each step is one of:

| kind | fields | meaning |
|---|---|---|
| `belief` / `act` | `id`, `state` | the agent holds a belief about, or writes, a state |
| `evidence` | `id`, `contradicts` | an observation; `contradicts` names an earlier belief or act, or is `None` |
| `flag` | `id`, `target` | something flags a deviation in an earlier belief or act |
| `repair` | `id`, `state` | a response that removes whatever holds that state now |

`contradicts` is a declared fixture label written by hand. It is never
inferred. The episode must say `contradiction_labels: "declared_fixture"`;
anything else, or a missing value, is a `config_error`.

## Rule (`decide(episode, policy="consume_contradiction")`)

For every labelled contradiction (evidence `e` against holder `h` of state
`S`), the contradiction is consumed only if some repair after `e` removes
`S` while `h` still holds it, and no belief or act asserts `S` again after
that repair. Then, in order:

1. `task_done` is false: `fail` / `task_not_done`.
2. any contradiction with no flag after it and no removing repair:
   `fail` / `unused_contradiction`.
3. any contradiction whose state was removed and then asserted again by a
   later belief or act, for example `[b1 S, e1 -> b1, repair S, b3 S]`:
   `fail` / `reasserted_after_repair`. A flag does not excuse it, under
   `flag_as_repair` too.
4. any contradiction flagged after the evidence but never removed:
   `fail` / `flag_without_repair`.
5. any evidence step without a `contradicts` label:
   `on_unmeasured` / `unlabeled_evidence`.
6. otherwise `success` / `contradictions_consumed`.

The sketch cannot compare values, so it cannot tell a corrected
re-assertion from the same error coming back. It treats every re-assertion
of a repaired state as a relapse (fail closed). A belief or act on another
state after the repair is fine.

The record lists `unresolved` (evidence id, holder id, reason), the
`ineffective_repairs` that removed no contradicted holder, and the
`unlabeled` evidence ids.

## Not measured (`on_unmeasured`)

- General contradiction detection. Telling whether two statements conflict
  would need an NLI-style oracle; `detect_contradiction()` always returns
  `on_unmeasured`.
- Origin and phase localisation of an error (the paper's annotation
  protocol); `localise_origin()` always returns `on_unmeasured`.
- Silent overwrites: a later belief that replaces the contradicted one
  without a repair step is not counted as a response (fail closed).
- Superseded holders: a label against a belief or act that was already
  replaced when the evidence arrived can never be consumed, since no
  repair can find it still holding its state (fail closed; fixture
  `d_superseded_holder`).

## Waits and bad input

A `wait` block is `{timeout_s, on_expiry, expired}`. `on_expiry` must be
declared as one of `HOLD`, `ESCALATE`, `DENY`; a timeout without it is a
`config_error`. An expired wait returns the declared action with reason
`expired` and records the would-be verdict in `prior_verdict`; it never
returns `success`.

Inputs are checked by exact type (`type(x) is str`, `dict`, `list`, `int`,
`bool`). Unknown fields (for example a confidence score, `origin` or
`phase`), unknown or forward ids, duplicate ids and subclasses that pretend
to equal valid values are a `config_error`. `decide()` catches internal
errors and returns `config_error`; it does not raise. A policy that is not
an exact known string is recorded as `invalid_policy`.

## Baselines and what we measured

Two hand-written baselines are measured against the gate on 36 enumerated
synthetic fixtures (9 response shapes x task done or not x a neutral or an
unlabeled extra evidence step):

- `symptom_only` closes on `task_done` alone and ignores the evidence.
- `flag_as_repair` counts a flag after the evidence as a response.

```
policy                    n  success  success_over_gate
consume_contradiction    36        2                  0
symptom_only             36       18                 16
flag_as_repair           36        3                  1
n_cases=36 (synthetic declared fixtures only)
```

`success_over_gate` counts cases a policy closes as success where the
gate does not. The gap is there by construction and says nothing about any
agent or corpus. The authors' own figures from their annotated runs are
quoted, attributed and marked UNVERIFIED in `paper_evidence.json` only; we
have not checked them and do not claim them.

The baselines return the same `success` constant as the gate; only the
record's `policy` field says which policy closed the run, so a consumer
must read `policy` before trusting a `success`.

## Not a duplicate of

- `w20-plan-change-notice` (2026-11-11), the closest prior work: an acked
  objective-change notice is not acted on unless a guard checks the plan's
  version before each consequential step and replans or waits. Same
  "signal is not a response" shape; there the signal is an incoming notice
  and the response is a replan before the next step, here the signal is
  evidence already in the trace and the response is a repair that removes
  the contradicted state, checked when the run closes.
- `w20-fidelity-audit` (2026-11-11): a tool pass vouches only for the
  artefact it ran on; it checks that a check addresses the claim as
  stated. Here the question is whether contradicting evidence already in
  the trace was consumed.
- `w16-fail-signatures` (2026-11-07): closed sequential failure signatures
  and stop-and-report. That matches symptom patterns; this sketch asks
  whether a response removed the contradicted state.
- `w20-evidence-linked-memory` (2026-11-11): descend from a stored lesson
  to its trajectory before acting. That is about memory lessons; this is
  about one episode closing.

## Files

- `unused_contradiction.py`: `validate`, `decide`,
  `detect_contradiction`, `localise_origin`, `summarise`.
- `fixtures.py`: declared fixtures with expected labels from separate
  hand-written tables; `python3 fixtures.py` prints the table above.
- `test_unused_contradiction.py`: unittest suite.
- `paper_evidence.json`: paper metadata and verbatim abstract quotes,
  UNVERIFIED.
- `mutants.py`: 52 code mutants of the module and 23 world mutants of
  the fixtures, the tests, `paper_evidence.json` and the day README; each
  must make the suite or `fixtures.py` fail. Each runs in a temporary
  repo-layout copy (the day README copied to the day folder) that is
  removed afterwards.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest -v
python3 -B fixtures.py
python3 -B mutants.py
```

The quote check in the suite reads the abstract copy named in
`paper_evidence.json` from the directory in `$W21UC_SOURCES`; with the
variable unset (the normal case) that one test is skipped. Without it the
quote spans are still pinned by length and sha256, but their offsets in
the abstract are not checked; run once with the variable set before a
merge.

The day README tests read `../README.md` when this folder sits in its
day folder, and fall back to `_day/README.md` in a flat draft copy.

## Limits

- Fixtures are synthetic and enumerated, not sampled from real traces.
- Contradiction labels are given. Whether real evidence contradicts a real
  belief is out of scope.
- A repair is modelled as removing a named state; whether a real response
  removes the right state is a labelling question, also out of scope.
- `decide()` returns `config_error` on internal errors, but a caller that
  is already at Python's recursion limit can still see `RecursionError`
  raised before `decide()` runs its guard. It never yields `success`.
  Caller stack depth is out of scope.
