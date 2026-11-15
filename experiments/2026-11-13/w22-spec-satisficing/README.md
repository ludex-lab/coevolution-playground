# w22-spec-satisficing

Acceptable is not compliant: a choice that drops a requirement may not be
committed, whatever reason the agent finds for it. **Top** method sketch
inspired by [arXiv 2611.16289](https://arxiv.org/abs/2611.16289),
"Eliciting and Mitigating Specification Satisficing in Coding Agents"
(Ruixin Wang, Tianyi Zhang; v1, submitted 12 Nov 2026; primary category
cs.SE, cross-listed cs.AI and cs.CL). SatisFix is the name of the paper's
method, not its title.

Paper licence: CC BY 4.0
(http://creativecommons.org/licenses/by/4.0/). Method-borrow only; the abs
page links no code, and none is used here.

This is a method sketch, not law, policy or a team rule, and it is not a
reproduction of the paper. Status: Top. The fixtures are synthetic and
hand-written. The paper's benchmark results are `on_unmeasured` here
(`paper_results()` says so); the authors' figures sit only in
`paper_evidence.json`, quoted verbatim from the abstract and marked
UNVERIFIED. Python 3 standard library only: no network, no model, no
randomness, no files written, no timeout.

## What it does

The paper names *specification satisficing*: an agent considers a choice
that meets a requirement, then commits to another that does not, for a
reason it finds acceptable. The method has two steps: report such choices
with their reasons, then check each choice against the task description.

Here a task is a list of requirement ids plus a catalog of implementation
choices. Each choice carries a fixture label `meets` (the requirement ids
the fixture author declares it satisfies). An agent trace is a list of
events, ending in exactly one commit:

| event | fields | effect |
|---|---|---|
| `report` | `choice`, `reason`, `acceptable` | the choice is reported; a new report voids its earlier check |
| `check` | `choice` | `check(choice, requirements)` runs on the fixture label and is recorded |
| `self_correct` | `choice`, `reason`, `acceptable` | counts as a report of the named choice (retained or new) and voids every earlier check |
| `commit` | `choice` | the gate below decides |

`acceptable` is the agent's own verdict on its reason (an exact `bool`). It
is recorded in the result (`acceptable_claimed`) and never honored.

`spec_satisficing.evaluate(task, trace)` applies the commit gate in order:

| decision | reason | when |
|---|---|---|
| `REFUSE` | `unreported` | no `report` or `self_correct` names the committed choice |
| `REFUSE` | `unchecked` | no `check` of it after its latest report and after the latest self-correction |
| `REFUSE` | `drops_requirement` | that check finds a dropped requirement (listed in `dropped`), "acceptable" or not |
| `COMMIT` | `all_requirements_met` | otherwise |
| `REJECT` | `config_error` | malformed input (a non-str key, unknown field, unknown choice, empty or whitespace-only reason, non-bool `acceptable`, a subclass where an exact type is required, commit not last, a label naming an unknown requirement, ...) |

`evaluate()` never raises. Every dict key, at every level (task, choice
catalog, choice entry, trace event), must be an exact `str`, and that is
checked before any lookup in the dict. Every value is checked by exact
type, so subclasses of `str`, `list` and `dict` are rejected.
`validate()` reads each caller value once and returns a private snapshot
of the validated values (exact `str`, `bool` or `None` in tuples and
fresh dicts); the gate runs only on that snapshot and never reads the caller's
objects again.

Why a self-correction voids every check: the paper reports that existing
self-correction methods are biased toward the choices the agent already
accepted. So a self-correction is treated as a new report, not as
evidence: whatever it selects, retained or new, must be checked again
after it, against every requirement. The self-correction rule (a
self-correction voids every earlier check) and the re-report rule
(re-reporting a choice voids its check) are this sketch's own rules, not
the paper's.

## Independent oracle

`oracle.py` is a second, separate code path. It imports nothing, shares no
function with the module, and decides by scanning backward from the commit:
it stops at the first boundary (any self-correction, or a report of the
committed choice) and asks whether a check of that choice lies between the
boundary and the commit; `dropped` is a set difference. The suite
compares module and oracle on all 20 fixture episodes and on every trace of
up to three events before the commit on both tasks (21,696 traces).

## Done-when (box tests)

| VERDICT T2 | test |
|---|---|
| (a) an all-requirements choice may commit | `test_a_all_requirements_choice_may_commit` |
| (b) a dropping choice is refused even when the reason is "acceptable" | `test_b_dropping_choice_refused_even_if_acceptable` |
| (c) an unreported dropping commit is refused | `test_c_unreported_dropping_commit_refused` |
| (d) a later self-correction that retains the dropping choice still fails | `test_d_self_correction_retaining_dropping_choice_still_fails` |
| paper figures `on_unmeasured`, UNVERIFIED; no model | `test_e_paper_numbers_on_unmeasured_no_model` |

Mutants named in the VERDICT, all in `mutants.py` and all killed:

- honor "acceptable": `honor 'acceptable' at the commit gate` (and
  `honor 'acceptable' at check time`);
- permit unreported commit: `permit unreported commit`;
- skip the re-check after self-correction: `skip re-check after
  self-correction (self-correction counts as a pass)` (and
  `self-correction does not void earlier checks`).

## Results

```
python3 -B -m unittest   ->  Ran 43 tests, OK (skipped=1)
python3 -B mutants.py    ->  killed 55/55 (code 40/40, world 11/11, harness 4/4)
python3 -B fixtures.py   ->  20 episode rows; module vs oracle: 20/20 episodes agree
```

The skip is the quote check against the abstract copy (see Run). These
results describe the synthetic fixtures only; they say nothing about any
agent, model or benchmark.

## How this differs from w20-acf-adherence and w20-fidelity-audit

- `w20-acf-adherence` (experiments/2026-11-11) checks commits against the
  instructions of an agent context file, one instruction at a time. It
  measures instruction-level compliance of what was committed.
- `w20-fidelity-audit` (experiments/2026-11-11) asks that a tool check
  address the claim as stated and binds results to an artefact digest.
- New here: the agent's own reason for swapping a requirement-meeting
  choice for a requirement-dropping one is never honored, a commit needs
  report-then-check, and a self-correction cannot stand in for the check.

## Files

- `spec_satisficing.py`: validation, `check()`, `evaluate()` and
  `paper_results()`.
- `oracle.py`: the independent backward-scan reference.
- `fixtures.py`: two synthetic tasks with fixture labels, 20 episodes
  and the hand-written expected table.
- `test_spec_satisficing.py`: unittest suite.
- `mutants.py`: code mutants (snippets of the module or the oracle swapped
  in memory), world mutants (fixture changes) and harness mutants (the
  row-scoped hygiene scan replaced in memory). Each must make the suite
  fail; the runner exits non-zero if any survives.
- `paper_evidence.json`: the authors' claims with verbatim abstract
  quotes, each UNVERIFIED and `on_unmeasured`.
- `NOTICE`: credit and licence.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The quote test reads the abstract copy named in `paper_evidence.json` from
the directories listed in `$W22SATISFICE_SOURCES` (separated by the OS
path separator); it skips when that is unset.

The hygiene tests (banned words, absolute paths, conflict markers, paper
numbers) read every file of this folder whole, but read only this PR's
own row of the day README (the line starting
`- [w22-spec-satisficing](`), so rows added by other PRs are not judged
here.

## Limits

- "Satisfies / drops a requirement" is a fixture label, not a general
  specification oracle. Each choice's `meets` list is written by hand in
  `fixtures.py`; `check()` only compares that label with the requirement
  list. Nothing here reads code, runs tests or decides whether a real
  implementation meets a real requirement. A wrong label gives a wrong
  verdict.
- Requirements are atomic ids. Partial, conflicting or ranked
  requirements, and requirements that change mid-task, are out of scope.
- Reports are taken at face value as disclosures: the sketch cannot tell
  whether the agent reported every choice it considered, only whether the
  committed one was reported and checked.
- The agent's `acceptable` verdict is recorded (`acceptable_claimed`) and
  its reason text is only checked to be a non-blank exact `str`; neither
  is read by the gate. There is no exception path for a requirement the
  user waived. A waiver would have to change the requirement list itself.
- Key and type checks close the input to caller-defined objects (no
  caller `__eq__`, `__hash__` or `__lt__` runs after the key check). They
  do not defend against code that runs in the same process and patches
  this module.
- One commit per trace; multi-file or staged commits are not modelled.
- The paper's benchmark results are `on_unmeasured`; nothing here
  reproduces or tests them.
