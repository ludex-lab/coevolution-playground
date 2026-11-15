# w23-termination-lag

Once a first patch passes, later steps must not undo it. **Top** method
sketch, not a reproduction, of
[arXiv 2611.14960](https://arxiv.org/abs/2611.14960), "Termination Lag:
Coding Agents Solve Early but Stop Late" (Musa Cim, Burak Topcu, Mahmut
Taylan Kandemir; v1, submitted 11 Nov 2026; primary category cs.AI,
cross-listed cs.CL).

Paper licence: CC BY 4.0 (http://creativecommons.org/licenses/by/4.0/). The
abs page links no code; none was found or used. Clean-room, method-borrow
only (see `NOTICE`).

This is a method sketch, not law, policy or a team rule. Status: Top (Lab
Dig 2 Wave23). The trajectories are synthetic and hand-written: every
repository state, edit, check and label is a fixture label. The paper's
figures are `on_unmeasured` here (`paper_results()` says so); they live
only in `paper_evidence.json`, quoted verbatim from the abstract and marked
UNVERIFIED. Python 3 standard library only: no network, no model, no paid
API, no voting or ensemble, no daemon, no files written, no timeout.

## What it does

A trajectory is one synthetic coding-agent run:

| field | meaning |
|---|---|
| `initial` | `{file: content}` before the run; it must fail the checks |
| `checks` | the task's fixture test: `[{"file", "accept"}]`; a state passes when every checked file is present with one of its accepted contents (fixture label) |
| `steps` | `{"kind": "edit", "file", "content"}` (overwrite one file), `{"kind": "verify"}` or `{"kind": "explore"}` (no state change) |

`termination_lag.evaluate(trajectory)` replays the run and reports:

- `first_pass`: the first step after which the checks pass (`None` if
  never);
- `lag`: termination lag, the number of steps after `first_pass` up to the
  end of the run;
- `regressions`: the raw-run steps that turn a passing state into a
  failing one (a correct patch undone).

Three arms:

| arm | reads | output |
|---|---|---|
| honest baseline (final-state judge) | the final state of the raw run only | `PASS` / `FAIL` |
| rule (step gate) | every step, in order | gated final verdict, `protected_from`, refused edits, per-step decisions, compare-run regressions |
| stop at first pass | steps up to the first passing patch | verdict and steps run |

The rule: before the first passing patch every step is permitted. From that
patch on, an edit whose result would fail the checks is refused: it is not
applied and the passing state is retained. An edit that still passes (an
alternative correct patch, an unrelated file) is permitted. Protection
never expires: no number of verify or explore steps after the first pass
turns a later breaking edit into a permitted one. The same rule, used as a
score on a compare run that applies everything, reports each regression
step. Stopping at the first pass is a valid, fail-closed end: nothing
requires further steps, and the solution stays correct.

The honest baseline is the usual end-of-run check: it runs the fixture test
on the final state and says `PASS` or `FAIL`. It is not weakened on
purpose; it simply cannot see mid-run correctness, so a run that was
solved and then undone looks the same as a run that was never solved, and
a regression that a later edit re-fixed is invisible.

Malformed input is `config_error`, and `evaluate()` never raises. Every
dict key, at every level (trajectory, initial state, check, step), must be
an exact `str`, and that is checked before any lookup in the dict. Every
value is checked by exact type, so subclasses of `str`, `list` and `dict`
are rejected (and `True` is not a content). `validate()` reads each caller
value once and returns a private snapshot (exact `str` values in tuples
and fresh dicts); every arm runs only on that snapshot and never reads the
caller's objects again. There is no timeout or expiry in this design, so no
`on_expiry` is declared; the gate's protection has no expiry either.

## Independent oracle

`oracle.py` is an independent oracle on a second, separate code path. It imports nothing, shares no
function name with the module and does not validate input. It rebuilds
every raw-run state from scratch by replaying the step prefix, and runs
the gate by holding a list of admitted edit indices and replaying that list
for every candidate edit. The suite compares module and oracle on all 15
fixture trajectories and exhaustively on every step sequence of up to five
steps over two small worlds and up to four steps over a third (23,632
short traces in all; see Results).

## Done-when (box tests)

| Wave23 Top, termination lag | test |
|---|---|
| (a) a first passing patch is recorded; lag is counted from that step | `test_a_first_passing_patch_recorded_and_lag_counted` |
| (b) a later edit that breaks the fixture test is refused (or scored incorrect in the compare run) | `test_b_later_breaking_edit_refused_or_scored_fail` |
| (c) stopping at the first pass leaves the solution correct | `test_c_stop_at_first_pass_leaves_solution_correct` |
| (d) no model; paper figures not reproduced, UNVERIFIED, `on_unmeasured` | `test_d_no_model_and_paper_numbers_on_unmeasured` |
| a wait after the first pass does not become permission | `test_wait_after_first_pass_never_permits_breaking_edit` |
| the honest baseline misses mid-run correctness and regressions | `test_baseline_misses_mid_run_correctness_and_regressions` |

(d) is checked on the code: an AST scan of every import (module and
oracle: nothing; fixtures: `copy` plus this folder's modules) and a token
scan of the module, oracle and fixtures for model, API, network,
environment, random, sleep, timeout, voting, ensemble, ledger and
database names.

## Results

```
python3 -B -m unittest   ->  Ran 43 tests, OK (skipped=1)
python3 -B mutants.py    ->  killed 66/66 (code 52/52, world 10/10, harness 4/4)
```

The skip is the quote check against the abstract copy (see Run). With
`$W23TERMLAG_SOURCES` set to the directory holding that copy, all tests
pass with no skip.

`python3 -B fixtures.py` (fixture counts; not comparable with any figure
in the paper):

```
c-churn-before-solve       first=3    lag=0    regs=()     base=PASS rule=PASS refused=()     stop=PASS/4
c-full-then-undo-one       first=1    lag=2    regs=(3,)   base=FAIL rule=PASS refused=(3,)   stop=PASS/2
c-never-solved             first=None lag=None regs=()     base=FAIL rule=FAIL refused=()     stop=FAIL/2
c-partial-then-full        first=2    lag=1    regs=()     base=PASS rule=PASS refused=()     stop=PASS/3
c-unrelated-edit-after     first=1    lag=1    regs=()     base=PASS rule=PASS refused=()     stop=PASS/2
d-alt-correct              first=0    lag=3    regs=()     base=PASS rule=PASS refused=()     stop=PASS/1
d-first-edit-stop          first=0    lag=0    regs=()     base=PASS rule=PASS refused=()     stop=PASS/1
d-first-edit-then-verify   first=0    lag=3    regs=()     base=PASS rule=PASS refused=()     stop=PASS/1
d-late-solve               first=3    lag=1    regs=()     base=PASS rule=PASS refused=()     stop=PASS/4
d-long-wait-then-undo      first=0    lag=8    regs=(8,)   base=FAIL rule=PASS refused=(8,)   stop=PASS/1
d-never-solved             first=None lag=None regs=()     base=FAIL rule=FAIL refused=()     stop=FAIL/4
d-revert-to-bug            first=1    lag=3    regs=(3,)   base=FAIL rule=PASS refused=(3,)   stop=PASS/2
d-undo-at-end              first=0    lag=3    regs=(3,)   base=FAIL rule=PASS refused=(3,)   stop=PASS/1
d-undo-then-refix          first=0    lag=3    regs=(1,)   base=PASS rule=PASS refused=(1,)   stop=PASS/1
d-undo-then-wrong-again    first=0    lag=3    regs=(1,)   base=FAIL rule=PASS refused=(1, 2) stop=PASS/1
```

- trajectories: 15 (13 reach a first passing patch, 2 never do; 6 carry a planted regression, 6 regression steps in all)
- first passing patch and termination lag: rule arm matches the gold labels on 15/15; the baseline reports neither
- regressions: rule arm flags 6/6 planted regression trajectories at the gold steps and refuses 7 edits (gold refusals matched on 15/15 trajectories, 0 false flags); the baseline flags 0/6
- final verdict against gold 'reached a correct patch': rule arm 15/15, baseline 10/15 (it fails 5 runs that were solved and then undone, and passes 1 run whose regression a later edit re-fixed without seeing the regression)
- stop at the first pass: 13/13 solved runs end correct; 31 of 61 total steps come after the first passing patch; stopping there runs 30 steps
- module vs oracle: 15/15 trajectories agree; module vs hand labels: 15/15

Reading the numbers:

- The rule arm recovers the gold first-correct step and termination lag on
  every trajectory, and its `protected_from` is that same step.
- Six trajectories carry a planted regression. The gate refuses the
  breaking edit in each, so every run that ever passed ends correct. In
  `d-undo-then-wrong-again` it refuses two edits: the raw run has one
  pass-to-fail step, but the second wrong edit would also break the
  retained passing state.
- `d-long-wait-then-undo` undoes the patch after seven verify and explore
  steps; the gate still refuses it. The test also sweeps 0 to 40 waiting
  steps.
- The baseline fails five runs that had a correct patch mid-way and passes
  `d-undo-then-refix`, whose regression a later edit re-fixed, without
  seeing that regression. It also cannot report a first-correct step or a
  lag.
- No false flags: an alternative correct patch (`d-alt-correct`), an
  unrelated file edit after the pass (`c-unrelated-edit-after`) and churn
  before the first pass (`c-churn-before-solve`) are all permitted.

## How this differs from merged work on main

- `w21-info-friction` (experiments/2026-11-12) stops a run when recurrent
  evidence adds no requirement gain. It is about when to stop gathering
  evidence; it has no notion of a solved task being un-solved.
- `w14-phase-deadline` and `w14-silence-expiry` handle stalls and timeout
  expiry: what happens when a step does not arrive in time.
- New here: the task is already solved, and continued work can un-solve
  it. The sketch records the first passing patch, measures the lag after
  it, and refuses (or scores as a regression) any later edit that would
  make the fixture test fail. There is no clock, no deadline and no
  stopping rule based on evidence gain.

## Files

- `termination_lag.py`: validation, `passes()`, `raw_run()`,
  `first_pass()`, `lag()`, `regressions()`, `baseline()`, `gate()`,
  `stop_first()`, `evaluate()` and `paper_results()`.
- `oracle.py`: the independent reference.
- `fixtures.py`: 15 synthetic trajectories over two toy tasks, the
  hand-written gold set, the summary lines this README carries.
- `test_termination_lag.py`: unittest suite.
- `mutants.py`: code mutants (snippets of the module or the oracle swapped
  in memory), world mutants (fixture changes) and harness mutants (the
  row-scoped hygiene scan replaced in memory). Each must make the suite
  fail; the runner exits non-zero if any survives.
- `paper_evidence.json`: the authors' claims with verbatim abstract quotes
  and offsets, each UNVERIFIED and `on_unmeasured`.
- `NOTICE`: credit and licence.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The quote test reads the abstract copy named in `paper_evidence.json` from
the directories listed in `$W23TERMLAG_SOURCES` (separated by the OS path
separator); it skips when that is unset.

The hygiene tests (banned words, absolute paths, conflict markers, paper
numbers) read every file of this folder whole, but read only this PR's own
row of the day README (the line starting `- [w23-termination-lag](`), so
rows added by other PRs are not judged here.

## Builder reflection

A strawman baseline would have been easy to beat; the honest one is what
most harnesses do: run the fixture test once, at the end. Writing
the fixtures showed where it is blind: not only on runs that end broken
(it says FAIL, correctly, but cannot tell "never solved" from "solved and
then undone"), but also on a run that broke and re-fixed its own patch,
which it passes with no trace of the regression. The design choice that
mattered most was what "undo" means. Comparing content with the first
correct patch would refuse an alternative correct fix; judging each
candidate edit by the fixture test against the retained state permits that
fix, refuses a second wrong edit the raw run would not count as a new
regression, and leaves churn before the first pass alone. The no-expiry
rule is deliberate: a long verify-and-explore tail is exactly where the
paper places the risk, so waiting must never earn permission.

## Limits

- "Passes" is a fixture label: a list of accepted contents per checked
  file, written by hand. It is not a general patch-correctness oracle, and
  a wrong label gives a wrong verdict for every arm. Live SWE-bench runs are
  `on_unmeasured`.
- A refused edit is simply not applied. A real agent may then act on a
  state it did not expect; the sketch does not model that, or an agent that
  needs a temporarily failing state to reach a better patch.
- Edits overwrite one whole file; partial diffs, deletions, renames and
  flaky tests are out of scope.
- The gate trusts the fixture test after the first pass. If the test is
  incomplete, a breaking edit that the test does not cover is permitted.
- 15 hand-written trajectories over two invented tasks; no agent, model,
  benchmark or human label is used.
- Key and type checks close the input to caller-defined objects (no caller
  `__eq__`, `__hash__` or `__lt__` runs after the key check). They do not
  defend against code that runs in the same process and patches this
  module.
- Mutation kills show the suite catches these specific edits, not every
  possible fault.
- The paper's results are `on_unmeasured`; nothing here reproduces or
  tests them.
