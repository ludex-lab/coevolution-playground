# w20-evidence-linked-memory

A lesson is only as good as the run it came from. Memory here holds three
linked records per lesson, an insight, a summary of its run and the run's
trajectory (insight -> summary -> trajectory), and an agent that reads an
insight must descend to the trajectory before acting on it whenever the
insight is incomplete, contested or of doubtful origin. Three agents are
compared on the same toy tasks: one with no memory, one that follows
insights as written, and one that applies the descend rule.

This is a method sketch of the evidence-linked memory idea in
[arXiv 2611.14320](https://arxiv.org/abs/2611.14320) (CC BY 4.0). It is not a
reproduction, not Team OS law and not village law. Clean-room Python 3
stdlib, synthetic deterministic data, no network, no model in the loop.

Status: Soft. This revision answers review items F1-F5 on the first head;
it stays Soft until it is re-verified on the new head.

## Run

```
cd experiments/2026-11-11/w20-evidence-linked-memory/
python3 -m unittest test_evidence_memory.py -v
python3 fixtures.py
python3 mutants.py
```

The source checks in the tests read the lab copies named in
`paper_evidence.json` from the directory in `$W20ELM_SOURCES`. There is no
default path: with the variable unset, the two source checks are skipped
with the reason `W20ELM_SOURCES not set`; with it set, a missing lab copy
fails the test. To run them, point the variable at a directory holding
`2611.14320.abs.txt` and `wikitrace.README.head.txt` (their sha256 values are
in `paper_evidence.json`):

```
W20ELM_SOURCES=/path/to/lab-copies python3 -m unittest test_evidence_memory.py -v
```

`mutants.py` applies one source-text mutation at a time in a temporary copy
of this directory, runs `fixtures.py` and the suite there (with
`W20ELM_SOURCES` removed), prints killed or survived per mutant, and which
run killed it, and removes the copy. It has two kinds of mutant: behaviour
mutants on `evidence_memory.py`, and world mutants on `fixtures.py` that
make an adversarial fixture easy (an honest ok step, a matching label, a
lesson that sorts last, a key that differs by more than case). Most world
mutants leave the fixture's expected outcome unchanged, so only the `WorldShapes`
tests can notice them.

## Records

| Record | Fields | Meaning |
|---|---|---|
| insight | `id, key, verb, arg, outcome, summary` | a lesson for tasks with this `key`: do `(verb, arg)`; `outcome` is the insight's own copy of its run's label; `summary` links to the summary |
| summary | `id, trajectory, outcome, why` | the run's label (`outcome`) and why the run went as it did; `trajectory` links to the raw run |
| trajectory | `id, key, steps` | the run itself: `(verb, arg, result)` steps, `result` in `ok` / `error` |
| task | `task_id, key, answer, default` | the action that passes, and the action an agent takes with no memory |

`load_memory` builds the records from plain dicts. An absent optional field
becomes `None`, and `None` never reads as clean: an absent `outcome` is a
failed origin, an absent or empty `arg` is a missing detail, an absent link is
unresolved. Steps that cannot be parsed make the trajectory unreadable.
Unknown fields or wrong types are `config_error`.

## Agents

- `empty_memory`: takes the task's default action.
- `bare_insight`: follows the first relevant insight (lowest id) as written;
  with no `arg` it uses the default argument.
- `evidence_linked`: the read rule below.

## Read rule

For the insights whose `key` matches the task, in id order:

1. Check every link chain first. If any relevant insight has a missing,
   dangling or unreadable link, or its trajectory belongs to another key
   (keys compare exactly, so `GATE` is not `gate`), the task resolves only
   through the declared `on_unresolved`, even when that insight looked
   clean. A dangling link never falls back to some other summary or
   trajectory, even one for the same key.
2. Flag each insight with the triggers that hold for it:
   - `missing_detail`: no non-empty `arg`;
   - `conflict`: another relevant insight names a different verb (whether or
     not either has an `arg`), or the same verb with a different `arg`;
   - `failed_origin`: the run is not labelled exactly `"success"` on both
     sides, the insight's own `outcome` and its summary's `outcome`. Absent,
     `failure`, `Success`, `successful`, `"success "` (trailing space) and
     `""` all count. The insight's copy alone is not trusted: an insight that
     claims success while its summary says failure, or has no label, is
     flagged.
3. A flagged insight is not acted on until the agent descends to its
   trajectory (one `descend`). Only a run whose summary is labelled
   `"success"` gives evidence: the last `ok` step. A failed run's `ok` step
   did not make it pass, so a failed run never supplies an action; it can
   only reject. The verdict is `confirmed` (same action), `filled` (detail
   taken from the trajectory), `corrected` (the trajectory shows a different
   action) or `rejected` (a failed run, or no `ok` step). A rejected descend
   gives no evidence, so the next flagged insight is descended into as well.
   Once a trajectory has given evidence for the key, the remaining flagged
   insights are compared with it without another descend.
4. The trajectory wins. With evidence, the action is the evidence, and a
   clean insight that disagrees with it is `rejected`. Without evidence, the
   clean insights (which agree, as none is in conflict) are `followed`. With
   neither, the agent takes the default, as with no memory.

A clean insight (both labels exactly `"success"`, detail present, no
conflict, links resolve) is used with zero descends.

## Silence doctrine

Shared with [w14-silence-expiry](https://cursor.com/codebase/coevolution-lab/playground/pull/78):

- `on_unresolved` must be declared, in {`deny`, `safe_fallback`, `escalate`,
  `hold`}; a missing, unknown or non-`str` value (a `str` subclass included)
  is `config_error`, nothing runs, and this is checked before memory is read,
  even with an empty memory;
- an unresolved link never becomes "carry on with the insight": `deny`,
  `escalate` and `hold` stop with no action (statuses `denied`, `escalated`,
  `held`); `safe_fallback` drops memory for the task and takes the default
  action (status `fallback`);
- absent fields never default to clean.

## Done-when, as tests

| | Requirement | Tests | Status |
|---|---|---|---|
| (a) | degradation fixture is real: empty memory passes, bare insight fails | `DoneWhenA.*`: `degradation_failed_lesson`, `degradation_missing_outcome`; every regression world has such a task | implemented, tests pass |
| (b) | each trigger alone forces exactly one descend, then the task passes; dropping any trigger fails a test | `DoneWhenB.test_b_missing_detail_alone`, `test_b_conflict_alone`, `test_b_failed_origin_alone` (each asserts the other two triggers are absent); mutants `drop_*_trigger` | implemented, tests pass, mutants killed |
| (c) | trajectory wins; a contradicted insight is corrected or rejected, never followed | `DoneWhenC.*`: corrected, rejected, a clean insight overridden, `followed` only when the action is the insight's; a failed run never supplies the action; over every design case and regression world the linked agent never acts wrong where no memory passes, except the clean-but-wrong limit; adversarial worlds `failed_run_ok_step_is_wrong`, `failed_run_ok_step_misleads`, `failed_lesson_sorts_first` | implemented, tests pass |
| (d) | a clean insight is used with zero descends | `DoneWhenD.*`; every near-miss label on the insight or on its summary (`Success`, `successful`, `"success "`, `""`, `failure`, absent) descends; a success claim over a failed or unlabelled run descends (`run_label_*_beats_claim`) | implemented, tests pass |
| (e) | missing outcome -> failed origin -> descend; dangling link -> declared `on_unresolved`; missing declaration -> `config_error`; the permit word -> `config_error` | `DoneWhenE.*`: every link-fault case times four declarations, including a dangling summary beside a good same-key chain and a trajectory key that differs only in case; the permit word in any case, unknown values, `None`, non-`Config`, `str` subclass | implemented, tests pass |
| (f) | no network, model, Docker or OpenRouter imports; paper figures UNVERIFIED | `DoneWhenF.*`: imports restricted to an exact stdlib set, banned module words, figures only in `paper_evidence.json`, offsets match the lab copies when `$W20ELM_SOURCES` is set, no six-word run copied, no box path | implemented, tests pass |
| worlds | each adversarial fixture still has its adversarial shape | `WorldShapes.*`; world mutants in `mutants.py` | implemented, tests pass, world mutants killed |

Counts on this revision (system `python3`, stdlib only): 64 tests, of which
2 are skipped with `W20ELM_SOURCES` unset and 0 with it set; `fixtures.py`
reports design 36/36 and regression 12/12 (252 tasks); `mutants.py` runs 77
mutants (57 behaviour, 20 world): 75 killed, 2 listed as equivalent
(`conflict_skips_self_check`, `declaration_returned_as_given`), 0
survivors, 0 bad anchors. 18 of the 20 world mutants are killed only by the
unittest suite, with `fixtures.py` still passing.

Not declared verified.

## Regression worlds (not an independent benchmark)

`fixtures.generate(seed)` for seeds 3001-3012 builds twenty-one tasks per
world from seventeen categories (no relevant insight, clean right, clean
wrong, missing detail, missing outcome, a near-miss outcome label, failed
origin rejected, a failed run whose ok step is the true action, conflict, a
clean insight contradicted by another's trajectory, two failed lessons, a
success claim over a failed or unlabelled run, a failed run whose ok step is
a wrong action, a failed lesson that sorts before a correct success lesson,
a verb conflict where one lesson has no detail, a dangling link beside a
good same-key chain, and a link fault of seven kinds, the first fault in each
world cycling with the seed), shuffled, some twice, with random insight ids,
error noise in trajectories, a default that matches the answer about half
the time, and a declared `on_unresolved` drawn per world. Each task carries
the outcome its category implies for each agent; the module is compared
with those.

These worlds were written by the same author as the rule, alongside it, so
they are a regression and property set: they pin behaviour and the
properties tested over them (a failed run never supplies the action; the
linked agent never acts wrong where no memory passes, except a clean wrong
insight). They say nothing about generalisation. An independent check would
need categories written and hashed by someone else before the code.

## Credits and overlap

- [arXiv 2611.14320](https://arxiv.org/abs/2611.14320), Lee, Choi, Baek and
  Hwang, CC BY 4.0: the insight / summary / trajectory link and the three
  descend triggers. Method only.
- WikiTrace, https://github.com/yukyeongleee/wikitrace at
  `9ee357fbb95db9caae09808f3472a9fce6409c90`, Apache-2.0: cited for method
  only. Not cloned, installed or run (it needs Docker and an OpenRouter key);
  no code from it is here. See `NOTICE`.
- `experiments/2026-11-06/w15-tooling-memory/` (main): its checklist asks
  that every write carry provenance. This sketch adds a read-time rule that
  uses the provenance link before acting.
- `experiments/2026-11-08/w17-memory-scope/` (main): formation scope versus
  application scope of benign notes. Different trigger and fix; scope is not
  modelled here beyond the exact `key` match.
- `experiments/2026-11-04/51-fael-memory-pointers-soft-design-note.md`
  (main): file-scoped memory pointers, markdown only. Here the pointer runs
  from a lesson to its source run and is followed at read time.
- [#111 w19-engram-release](https://cursor.com/codebase/coevolution-lab/playground/pull/111)
  (open, head `c40bafd5`; read only): when experience records may leave
  retrieval. This sketch decides when a retrieved lesson may be acted on.
- [#78 w14-silence-expiry](https://cursor.com/codebase/coevolution-lab/playground/pull/78)
  (merged): the terminal vocabulary and the config-error rule, reused.

What this adds: an executable read-time rule over linked lesson records, the
three triggers as separate tested branches, the run label read from the
summary rather than the insight, trajectory-over-insight precedence with
failed runs held to rejection only, a degradation fixture in which the
bare-insight agent fails a task the no-memory agent passes, and adversarial
test worlds whose shape is itself pinned by tests and world mutants.

## Not included

No signing, keyed hashes or ledger; no SQLite; no daemon, thread or network;
no language-model API; no voting or ensemble; nothing from the WikiTrace
runtime.

## Limits

- Clean is trusted. A clean but wrong insight (both labels `"success"`) is
  followed with no descend and the task fails (`clean_but_wrong_is_a_limit`,
  and the `clean_wrong` regression category). The rule narrows
  memory-induced failure; it does not remove it.
- A failed run only rejects. When a failed run's `ok` step happens to be the
  true action (`failed_run_ok_truth`), that evidence is not used and the
  agent falls back to the default, so memory helps less there. This is the
  price of not letting a failed run's misleading `ok` step beat the
  no-memory agent.
- Runs labelled `"success"` are taken as honest: their last `ok` step is
  treated as the answer. A forged success trajectory, a mislabelled success
  run, or a task where the past run's action no longer applies, is out of
  scope.
- One descend settles a key: later flagged insights are compared with the
  first evidence found. Two trajectories with different `ok` actions for one
  key are not modelled.
- One unresolved link among several relevant insights stops the task, even if
  the others would settle it. That fails closed at the cost of some tasks.
- `safe_fallback` here means "act with no memory for this task". It has no
  substitute registry and no approval flag, unlike #78's fallback check.
- Relevance is an exact `key` match; misapplying a lesson to a similar but
  different task is not modelled.
- Synthetic and deterministic; nothing here says anything about any model.

## Paper figures

The paper's and the upstream README's figures are recorded only in
`paper_evidence.json`, as tokens with their offsets in the lab copies, and are
marked UNVERIFIED.

## Builder reflection

The first version descended to the run and then believed every ok step in
it, so a failed run became an oracle, and its fixtures only ever wrote runs
where that oracle was right. Reading the label from the summary and holding
failed runs to rejection closed both gaps, but the real fix was in the
worlds: each adversarial fixture now has a test for its shape, and mutants
that make a world easy are killed as surely as mutants of the rule.

Ludex: before Cody uses Naru's note on the gate, he reads the day's log to
see whether the day really went well; a bad day's log can tell him what not
to do, but never which way to turn.

Implementation may be complete; it is not declared verified.
