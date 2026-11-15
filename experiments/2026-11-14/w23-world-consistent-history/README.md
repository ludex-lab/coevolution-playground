# w23-world-consistent-history

Do not clean an agent's history into a false "done" while the world still
holds the error. **Top** method sketch, not a reproduction, of
[arXiv 2611.14654](https://arxiv.org/abs/2611.14654), "Cleaning an Agent's
History Hurts When the World Still Holds the Error" (Egor Pakhomov, Anurag
Koul, Hongjun Liu, Bo Pang, Shafiq Joty, Erik Nijkamp; v1, submitted 10 Nov
2026; primary category cs.AI, cross-listed cs.CL and cs.LG).

Paper licence: CC BY 4.0 (http://creativecommons.org/licenses/by/4.0/,
shown on the abs page). The ancillary code and data named in the arXiv
comments were not downloaded and not run; UNVERIFIED. Clean-room,
method-borrow only (see `NOTICE`).

This is a method sketch, not law, policy or a team rule. Status: Top (Lab
Dig 2 Wave23). The fixtures are synthetic and hand-written: every world,
gold world state, history, edit, receiver guess and label is a fixture
label. The paper's figures are `on_unmeasured` here (`paper_results()` says
so); they live only in `paper_evidence.json`, quoted verbatim from the
abstract and marked UNVERIFIED. Python 3 standard library only, and the
module imports nothing: no network, no model, no paid API, no receiver
model, no voting or ensemble, no files written, no timeout. The paper's
"database write" is borrowed only as a generic world-effect value; this is
not a database port.

## What it does

A case is one synthetic agent frozen mid-task with its exact world state,
plus one proposed edit of its history (a compaction, repair or handoff):

| field | meaning |
|---|---|
| `targets` | the task's targets |
| `gold` | the gold value of each target (fixture label; read only by scoring) |
| `world` | what each target holds now; `""` means the effect is absent |
| `guess` | the value the receiver stub would pick on its own (fixture label) |
| `history` | the original history: records `{target, claim, value}` |
| `edited` | the proposed edited history, same record shape |
| `edit_kind` | the edit's name (fixture label; read by nothing that decides) |

A record's claim is `done` (a completed action or a success receipt: the
target now holds `value`), `failed` (a failure receipt: setting `value` did
not land), `note` (a note that `value` is the correct one, beside whatever
the history says) or `neutral` (a note with no claim). A target's claim in
a history is its last `done` or `failed` record.

`world_history.evaluate(case)` decides the edit two ways:

| arm | reads | admits the edit when |
|---|---|---|
| rule arm (world check) | original history, edited history, world | no edited `done V` claim names a value the world does not hold or a blank value (`false_done`), and no claim of the original history is left without any claim (`claim_erased`) |
| honest baseline | edited history only | always: it trusts the history text and believes each `done` claim |

On refusal the rule arm hands the receiver the original, unedited history
(fail closed to "no edit"). The primary gate is the refusal; the receiver
comparison is a fixture arm, not a model.

**Receiver stub (deterministic, no model).** It reads only the history it
is handed and its own guess, never the world or the gold. Per target: with
a note, it writes the noted value (unless the claim is already `done` with
that value); with no claim, it writes its guess; with `done V`, it skips the
target when `V` equals its guess and writes its guess otherwise (it doubts
a commit that disagrees with its own reading); with `failed V`, it retries
`V`. Skipped targets retain their world value. Recovery is the share of
remaining targets (world value differs from gold at the freeze) that hold
the gold value afterwards; "damaged" counts targets that were right and are
now wrong. Three views are scored per case: `unedited` (the original
history), `baseline` (the edit) and `rule` (the edit if admitted, else the
original).

The rule never reads the gold, the receiver's guess or the edit kind: it
knows nothing about which value is right, only what the world holds. It is
narrow by design: a stale failure receipt beside a present effect is not
refused (the contract is about false "done", not about a history that is
less clean than the world).

A `done` claim whose value is blank (`""` or whitespace only) names no
effect, so it never matches the world, not even a blank world value: the
rule refuses it as `false_done`. `""` is the absence marker, so `done ""`
on an absent effect would otherwise rewrite a failed or absent effect as a
completed success (finding M1, see "Fix round 2 (M1)").

Malformed input is `config_error`, and `evaluate()` never raises. Every
dict key, at every level (case, `gold` / `world` / `guess` maps, history
and edited records), must be an exact `str`, and that is checked before any
lookup in the dict. Every value is checked by exact type, so subclasses of
`str`, `list` and `dict` are rejected (tuples and generators are not
histories). `validate()` reads each caller value once and returns a private
snapshot (exact `str` values in tuples and fresh dicts); the rule, the
baseline, the receiver and the scoring run only on that snapshot and never
read the caller's objects again. There is no timeout or expiry in this
design, so no `on_expiry` is declared.

## Independent oracle

`oracle.py` is a second, separate code path. It imports nothing, shares no
function name with the module and does not validate input. It finds each
target's claim by scanning a history backwards, applies the receiver as a
small decision table, and scores the final world position by position. The
suite compares module and oracle on all 20 fixture cases, on every
one-target case with original and edited histories of up to two records
over three world values, two gold values and two guesses (63,948 cases),
on every two-target case with histories of up to one record over every
world and guess (4,624 cases), and on every one-target case over blank and
non-blank values (`""`, `" "`, `u` as record and world values; original
histories of up to one record, edits of up to two; 24,492 cases), where no
blank `done` claim is ever admitted. In total 93,064 exhaustive cases agree.

## Done-when (box tests)

| Wave23 Top (pack done-when) | test |
|---|---|
| (a) the unedited history with the error still in the world is the baseline | `test_a_unedited_history_is_the_baseline` |
| (b) a truthful note beside the preserved error is admitted and the receiver recovers the remaining target | `test_b_truthful_note_admitted_and_receiver_recovers` |
| (c) a "done/success" rewrite while the effect is absent is refused (primary gate), and under the baseline the receiver does worse than (a) | `test_c_done_rewrite_refused_and_receiver_worse`, `test_c_done_blank_on_absent_effect_refused` |
| (d) a success receipt is admitted only once the world effect is present | `test_d_success_receipt_only_once_effect_present` |
| (e) no network, no model, no database port; paper rates `on_unmeasured`, UNVERIFIED | `test_e_no_network_no_model_no_database_paper_on_unmeasured` |

(e) is checked on the code: an AST scan of every import (module and
oracle: nothing; fixtures: `copy`, the module and the oracle), a token scan
of the module, oracle and fixtures for database, socket, URL, HTTP,
subprocess, environment, API-key, vendor, voting, ensemble, thread,
schedule, clock and random names, the same scan on the names of the loaded
functions (so an in-memory mutant is caught), `paper_results()` returning
`on_unmeasured`, and every claim in `paper_evidence.json` marked UNVERIFIED
and `on_unmeasured`, with the ancillary files recorded as not downloaded and
not run.

## Results

```
python3 -B -m unittest   ->  Ran 40 tests, OK (skipped=1)
python3 -B mutants.py    ->  killed 68/68 (code 52/52, world 12/12, harness 4/4)
```

The skip is the quote check against the abstract copy (see Run). With
`$W23WCH_SOURCES` set to the directory holding that copy, all tests pass
with no skip.

`python3 -B fixtures.py`:

```
case                            edit             rule   reasons                    recovered u/b/r of remaining
wrong-commit-unedited           none             ADMIT  -                          2/2/2 of 2
wrong-commit-neutral-note       neutral_note     ADMIT  -                          2/2/2 of 2
wrong-commit-truthful-note      truthful_note    ADMIT  -                          2/2/2 of 2
wrong-commit-completed-action   completed_action REFUSE color:false_done           2/1/2 of 2
hard-error-unedited             none             ADMIT  -                          0/0/0 of 1
hard-error-neutral-note         neutral_note     ADMIT  -                          0/0/0 of 1
hard-error-truthful-note        truthful_note    ADMIT  -                          0/1/1 of 1
hard-error-completed-action     completed_action REFUSE city:false_done            0/0/0 of 1
long-history-unedited           none             ADMIT  -                          1/1/1 of 1
long-history-compact            compact          ADMIT  -                          1/1/1 of 1
long-history-compact-clean      completed_action REFUSE tag:false_done             1/0/1 of 1
long-history-compact-note       truthful_note    ADMIT  -                          1/1/1 of 1
effect-absent-unedited          none             ADMIT  -                          1/1/1 of 1
effect-absent-success-receipt   success_receipt  REFUSE order_status:false_done    1/0/1 of 1
effect-absent-erase-error       erase_error      REFUSE order_status:claim_erased  1/1/1 of 1
effect-present-unedited         none             ADMIT  -                          1/1/1 of 1
effect-present-success-receipt  success_receipt  ADMIT  -                          1/1/1 of 1
meal-absent-unedited            none             ADMIT  -                          1/1/1 of 1
meal-absent-success-receipt     success_receipt  REFUSE meal:false_done            1/0/1 of 1
meal-absent-truthful-note       truthful_note    ADMIT  -                          1/1/1 of 1
cases: 20 (freezes: 6, planted false-done edits: 5)
rule arm refuses planted false-done edits: 5/5
baseline admits planted false-done edits: 5/5
edits refused: rule 6, baseline 0
unedited: recovery 20/24 = 0.833, task success 16/20, damaged 0, worse than unedited 0, better than unedited 0
baseline: recovery 17/24 = 0.708, task success 13/20, damaged 0, worse than unedited 4, better than unedited 1
rule: recovery 21/24 = 0.875, task success 17/20, damaged 0, worse than unedited 0, better than unedited 1
module vs oracle: 20/20 cases agree
```

Reading the numbers (fixture counts, not comparable with any figure in the
paper; u/b/r = unedited / baseline / rule arm):

- The rule arm refuses all five planted false-done edits (three completed
  actions that rewrite a wrong value as the right one, two success
  receipts whose effect is absent) and one erased claim; it refuses nothing
  else. The honest baseline admits all five.
- Under the baseline, four of the five planted edits leave the receiver
  worse off than no edit at all: the history now says the target is done
  with the value the receiver would pick, so it skips the target and the
  wrong value stays in the world. The fifth (`hard-error-completed-action`)
  is no worse only because the unedited history already recovers nothing
  there. The rule arm, which hands over the unedited history, is never
  worse than unedited.
- The value's presence alone does not decide: `hard-error-truthful-note`
  and `hard-error-completed-action` both carry the gold value `Lyon`. The
  note is admitted and the receiver recovers the target (where the
  unedited history and a matched neutral note recover nothing); the
  completed action is refused, and under the baseline it recovers nothing.
- A success receipt is admitted once its effect is present
  (`effect-present-success-receipt`) and refused while it is absent
  (`effect-absent-success-receipt`, `meal-absent-success-receipt`).
- The erased failure receipt (`effect-absent-erase-error`) is refused, but
  in this stub it does not hurt the receiver: with no claim left, the stub
  redoes the target from its own guess, which is right there. The refusal
  rests on the contract (the history may not drop what it says about a
  target), not on a measured harm.
- No view damages a target that was right at the freeze.

## Fix round 2 (M1)

Finding M1: from `meal-absent-unedited` (world `meal` = `""`, the
absence marker), an edit that replaces the failure receipt `failed veg`
with `done ""` was admitted by the rule arm, since the claimed value equals
the world value. That rewrote an absent effect as a completed success and
went around both `false_done` and `claim_erased`.

Fix (the smaller of the two options): in the rule arm, a `done` claim with a
blank value (`""` or whitespace only) never matches the world and is
refused as `false_done`. It is not a `config_error`: input validation is
unchanged, so the baseline still sees and believes the edit, and the
comparison stays visible. The oracle applies the same rule on its own code
path.

- `test_c_done_blank_on_absent_effect_refused`: the M1 edit, with `""` and
  three whitespace values and three receiver guesses, is REFUSED
  (`meal:false_done`), never ADMIT, and the rule view equals unedited; a
  blank `done` on a blank world value `" "` is refused too.
- `test_rule_table` gains blank `done` rows over three world values; a
  blank `failed` record is still admitted (it claims no success).
- The exhaustive agreement adds a 24,492-case blank-value space and counts
  admitted blank `done` claims (0).
- Mutants: the round 1 rule restored in the module, in the oracle, and in
  both together, and a blank test that only matches `""`; all are killed.
  The new test fails on the round 1 code.

Other rewrites checked: a `done` with any non-blank value on an absent
effect is already `false_done` (world `""` differs); whitespace values are
now covered; dropping the failure receipt, or replacing it with a `note` or
`neutral` record, is `claim_erased`; a later `failed` record after a false
`done` leaves the last claim a failure, not a success. `note` records claim
no success and remain unchecked (a disclosed limit). The fixture table and
counts above are unchanged: no fixture edit carries a blank `done` value.

## How this differs from work on main

Closest merged work, named in the verdict overlap section:

- `w21-unused-contradiction`: consume a contradiction already in the
  *trace*. Here the contradiction is between the edited history and the
  *world*, and the edit itself is what is judged.
- `w20-evidence-linked-memory`: check a lesson against its source
  trajectory. Here a history claim is checked against the frozen world
  state, not against another text.
- `w21-memory-admission`: temporary probes before a *write*. Here nothing
  is written; a proposed history edit is admitted or refused.
- `w22-write-precommit` (#127): a pre-commit write gate on targeting
  arguments stated by the user. Here the gate sits on the history, after
  the writes, and asks only whether a "done" claim matches the world.
- `mb-boundary-vs-judge` (#130): an evaluator comparison on recorded
  writes vs a text judge, not a history-edit gate. Here there is one gate
  (refuse a success rewrite whose effect is absent) and a receiver fixture
  arm.

New here: the contract "do not rewrite a still-absent world effect as a
completed success", with a truthful note beside the preserved error as the
admitted repair.

## Builder reflection

- The hardest choice was the receiver. A receiver that trusts every done
  claim makes the completed-action edit and the unedited history equally
  bad, and one that checks the world makes the history irrelevant. The stub
  doubts a done claim only when it disagrees with its own guess, which is
  the smallest rule under which a clean-looking history can do worse than
  no edit. It is a declared toy, and the fixture guesses are chosen by
  hand, so its recovery counts show the mechanism, not a rate.
- The rule was kept world-only on purpose: it reads neither the gold nor
  the guess, so it cannot "know" the right answer. It refuses claims the
  world contradicts; it cannot catch a wrong value that the world also
  holds, and the unedited histories here are admitted for that reason.
- The verdict asked for one primary gate. The refusal is that gate; the
  receiver comparison only shows why the refusal matters. Falling back to
  the unedited history on refusal makes a refused edit never worse than no
  edit by construction; that is a property of the fallback, not evidence.
  Admitted edits can still be worse than no edit (a wrong note, or a wrong
  value the world also holds); on these fixtures none was.
- The erased-claim refusal was added to close the obvious way around the
  false-done check (drop the error instead of rewriting it). The stub shows
  no harm from it; that is reported rather than tuned away.
- Round 1 missed a second way around it: `done ""` equals the absence
  marker, so an exact-equality check admitted it. I had read it as the
  disclosed "value the world also holds" limit; the auditor was right that
  `""` is not a value but the absence of one. The exhaustive spaces used
  only non-blank record values, which is why they never reached it.

## Files

- `world_history.py`: validation and snapshot, `last_claims()`, `rule()`
  (rule arm), `baseline()`, `receiver()`, `outcome()`, `evaluate()`,
  `totals()` and `paper_results()`.
- `oracle.py`: the independent reference.
- `fixtures.py`: 6 freezes in two invented settings, 20 cases (5 planted
  false-done edits), the hand labels; prints the table and counts.
- `test_world_history.py`: unittest suite.
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
the directories listed in `$W23WCH_SOURCES` (separated by the OS path
separator); it skips when that is unset.

The hygiene tests (banned words, absolute paths, conflict markers, paper
numbers) read this folder's files and, in the day-index README, only this
PR's own row (prefix `- [w23-world-consistent-history](`); an in-memory
test shows a dirty sibling row is ignored while the same text in this row
is caught.

## Limits

- Worlds, gold states, histories, edits and receiver guesses are
  hand-written fixture labels; 20 cases from 6 freezes in two invented
  settings. No AgentCE-Bench or AppWorld task, trace or world is used.
- The receiver is a decision table, not a model. Its recovery counts depend
  on the hand-picked guesses and say nothing about how any real receiver
  model behaves.
- The rule checks only claims the world can contradict: a `done` claim
  against the frozen world value (a blank `done` value never matches), and
  claims dropped by the edit. It does not catch a wrong non-blank value the
  world also holds, a stale failure receipt, or an edit that changes notes
  only.
- Only `""` and whitespace count as blank. Another spelling of "nothing"
  (for example `none` or `-`) is an ordinary value compared exactly.
- One world value per target, compared by exact string equality; no
  partial effects, no time, no concurrent writers.
- Falling back to the unedited history on refusal is this sketch's choice;
  a real system might instead ask for a truthful note.
- Key and type checks close the input to caller-defined objects; they do
  not defend against code in the same process that patches the module.
- Mutation kills show the suite catches these specific edits, not every
  possible fault.
- The paper's results are `on_unmeasured`; nothing here reproduces or tests
  them.
