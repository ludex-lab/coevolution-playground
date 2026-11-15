# w23-scrutiny-not-authority

Self-assessment is advisory, not a deletion authority: when an agent rates
its own reasoning as defective, that rating flags the conclusion for
scrutiny, and only independent evidence may eliminate it. **Top** method
sketch, not a reproduction, of
[arXiv 2611.14889](https://arxiv.org/abs/2611.14889), "Can an AI Agent Be
Epistemically Akratic? Higher-Order Evidence & the Limits of
Self-Correction" (Eno Agolli; v1, submitted 11 Nov 2026; primary category
cs.AI).

Paper licence: arXiv non-exclusive distribution licence
(http://arxiv.org/licenses/nonexclusive-distrib/1.0/). The abs page links
no code; the paper is an argument with no empirical code or rate. Nothing
was cloned or run. Clean-room, method-borrow only (see `NOTICE`).

This is a method sketch, not law, policy or a team rule. Status: Top (Lab
Dig 2 Wave23). The fixtures are synthetic and hand-written: every
conclusion, self-assessment, check and gold label is a fixture label. The
paper states no figure to reproduce; its claims are `on_unmeasured` here
(`paper_results()` says so) and live only in `paper_evidence.json`, quoted
verbatim from the abstract and marked UNVERIFIED. Python 3 standard library
only: no network, no model, no paid API, no voting or ensemble, no files
written, no timeout.

## The doctrine, as a box test

The abstract argues that obeying a negative self-assessment can make an
agent worse at telling sound reasoning from defective reasoning: the part
that decides which conclusions to retain may rely on information about the
reasoning that the part judging justification cannot use. A negative
assessment can still identify conclusions requiring further scrutiny
"without having authority to eliminate them", and agreement between
conclusions and assessments "can be achieved by degrading either one".
This sketch turns that into a decision rule on recorded cases and scores
it against hand-written gold labels.

## What it does

A case is one conclusion an agent reached:

| field | meaning |
|---|---|
| `case_id` | non-blank id |
| `conclusion` | the conclusion text, read as a yes/no claim (no arm reads it) |
| `self_assessment` | `ok` or `defective`: the agent's own rating of its reasoning |
| `checks` | scrutiny checks, each `check_id`, `source`, `basis`, `verdict` |

A check's `source` is `self` (the agent re-reading its own reasoning),
`fixture_test`, `world_record` or `external_derivation`; its `basis` is
`own_evidence` or `self_assessment` (it only restates the rating); its
`verdict` is `supports`, `refutes` or `not_run`. A check is
**independent** when its source is not `self` and its basis is its own
evidence. An unrun check counts for nothing: silence is neither a
refutation nor a clearance. The independent outcome over the checks is
`refuted`, `supported`, `conflict` (both) or `none`.

`scrutiny_not_authority.evaluate(case)` decides each case under four arms.
Decisions: `RETAIN`, `HOLD` (retained, flagged, unresolved), `ELIMINATE`,
`NEGATE` (the conclusion replaced by its negation). Gold (`sound` /
`unsound`) is kept out of the case; no arm reads it.

| arm | defective rating | ok rating |
|---|---|---|
| baseline (honest: obey the rating) | `ELIMINATE` | ok path |
| rule (scrutiny, not authority) | flag; `refuted` -> `ELIMINATE`, `supported` -> `RETAIN`, `conflict` or `none` -> `HOLD` | ok path |
| agree_flip (degrade the conclusion) | `NEGATE` | ok path |
| agree_silence (degrade the assessment) | rating treated as ok: ok path | ok path |

The ok path, shared by every arm: `refuted` -> `ELIMINATE`, `conflict` ->
`HOLD`, otherwise `RETAIN`. The rule arm therefore differs from the
baseline only on defective ratings, so the comparison isolates what the
rating is permitted to do. A missing scrutiny check after a flag fails
closed: the conclusion is held (`HOLD`), neither dropped nor cleared.

`request_elimination(case, cite)` is the gate the rule arm uses: a request
to eliminate one conclusion, citing `self_assessment` and/or check ids. It
is `PERMIT` only when a cited check is an independent refutation and the
case's independent outcome is not `conflict` (support elsewhere in the
case cannot be ignored by citing around it). Citing the rating, a self
check, a check based on the rating, an unrun check or a supporting check
is `REFUSE`. The rule arm eliminates exactly when this gate, given every
citation, says `PERMIT`, and reports the refuting check ids as its basis.

`score(records, gold)` counts, per arm: sound conclusions lost (eliminated
or negated), unsound conclusions eliminated, unsound conclusions held
flagged, false conclusions held unflagged (an unsound `RETAIN` or a sound
`NEGATE`), eliminations without an independent refutation, and
**coherence** (the end state agrees with the arm's final rating:
eliminated, negated, or rated ok). Coherence is reported beside the gold
counts and is not scored as success.

Malformed input is `config_error`, and `evaluate()`,
`request_elimination()` and `score()` never raise. Every dict key, at
every level (case, check, score record, record arm, gold map), must be an
exact `str`, and that is checked before any lookup in the dict. Every
value is checked by exact type, so subclasses of `str`, `list` and `dict`
are rejected. `validate()` reads each caller value once and returns a
private snapshot (fresh dicts in a tuple); every arm runs only on that
snapshot and never reads the caller's objects again. There is no timeout
or expiry in this design, so no `on_expiry` is declared.

## Independent oracle

`oracle.py` is a second, separate code path. It imports nothing, shares no
function with the module and does not validate input. It flattens the
checks to `(source, basis, verdict)` triples, takes the set of verdicts
carried by independent, run checks, selects the outcome from a table, and
decides each arm by one table lookup keyed by (rating, outcome). It also
holds the elimination gate. The suite compares module and oracle on all 15
fixture cases, on every case with up to three checks over all 24 check
kinds and both ratings (28,850 cases), and on every non-empty citation set
for every case with up to two checks (8,210 requests).

## Done-when (box tests)

| Wave23 Top 3 | test |
|---|---|
| (a) a defective self-assessment flags the item and leaves it retained | `test_a_defective_assessment_flags_and_retains` |
| (b) auto-elimination on a defective assessment is refused | `test_b_auto_elimination_on_a_defective_assessment_refused` |
| (c) after a scrutiny check, an unsound conclusion may be dropped; a sound one is retained even if flagged | `test_c_scrutiny_check_drops_unsound_and_retains_sound` |
| (d) forcing agreement by flipping the conclusion fails where the rating is the noisy one | `test_d_forced_agreement_fails_where_the_rating_is_noisy` |
| (e) no LLM | `test_e_no_llm` |
| paper statements `on_unmeasured`, UNVERIFIED | `test_f_paper_on_unmeasured` |

(e) is checked on the code: an AST scan of every import (module and
oracle: nothing; fixtures: `copy` and the two local modules), a token scan
of the module, oracle and fixtures for model, voting, ensemble, API-key,
environment, URL, socket, subprocess, random and clock names, and the same
name checks on the loaded function code, so an in-memory mutant that adds
any of them is caught.

## Results

```
python3 -B -m unittest   ->  Ran 46 tests, OK (skipped=1)
python3 -B mutants.py    ->  killed 75/75 (code 57/57, world 14/14, harness 4/4)
```

The skip is the quote check against the abstract copy (see Run). With
`$W23SCRUTINY_SOURCES` set to the directory holding that copy, all 46 pass
with no skip.

`python3 -B fixtures.py`:

```
case                     gold     outcome    baseline   rule       flip       silence
ok-sound-plain           sound    none       RETAIN     RETAIN     RETAIN     RETAIN
ok-sound-tested          sound    supported  RETAIN     RETAIN     RETAIN     RETAIN
ok-unsound-refuted       unsound  refuted    ELIMINATE  ELIMINATE  ELIMINATE  ELIMINATE
ok-unsound-missed        unsound  none       RETAIN     RETAIN     RETAIN     RETAIN
ok-unsound-conflict      unsound  conflict   HOLD       HOLD       HOLD       HOLD
def-sound-unchecked      sound    none       ELIMINATE  HOLD*      NEGATE     RETAIN
def-sound-cleared        sound    supported  ELIMINATE  RETAIN*    NEGATE     RETAIN
def-sound-self-recheck   sound    none       ELIMINATE  HOLD*      NEGATE     RETAIN
def-sound-laundered      sound    none       ELIMINATE  HOLD*      NEGATE     RETAIN
def-sound-conflict       sound    conflict   ELIMINATE  HOLD*      NEGATE     HOLD
def-sound-world          sound    supported  ELIMINATE  RETAIN*    NEGATE     RETAIN
def-unsound-refuted      unsound  refuted    ELIMINATE  ELIMINATE* NEGATE     ELIMINATE
def-unsound-derived      unsound  refuted    ELIMINATE  ELIMINATE* NEGATE     ELIMINATE
def-unsound-unchecked    unsound  none       ELIMINATE  HOLD*      NEGATE     RETAIN
def-unsound-not-run      unsound  none       ELIMINATE  HOLD*      NEGATE     RETAIN
cases: 15 (sound 8, unsound 7; defective rating on 10)
* = flagged for scrutiny by a defective self-assessment
baseline: sound lost 6/8, unsound eliminated 5/7, unsound held 1, false held unflagged 1, eliminations without independent refutation 8, coherent 15/15
rule: sound lost 0/8, unsound eliminated 3/7, unsound held 3, false held unflagged 1, eliminations without independent refutation 0, coherent 7/15
agree_flip: sound lost 6/8, unsound eliminated 1/7, unsound held 1, false held unflagged 7, eliminations without independent refutation 0, coherent 15/15
agree_silence: sound lost 0/8, unsound eliminated 3/7, unsound held 1, false held unflagged 3, eliminations without independent refutation 0, coherent 15/15
elimination requests: 9/9 decided as labelled
module vs oracle: 15/15 cases agree
```

Reading the numbers (fixture counts on 15 hand-written cases; the paper
states no figure, so nothing here is comparable with it):

- The honest baseline obeys every defective rating. It eliminates 5 of
  the 7 unsound conclusions, more than any other arm, but it also loses 6
  of the 8 sound ones: every case where the rating was the noisy one. 8 of
  its 11 eliminations rest on the rating alone.
- The rule arm loses no sound conclusion. It eliminates 3 of 7 unsound
  conclusions, each on an independent refutation it names, and holds 3
  (two unchecked defective cases and one conflict) flagged for a check.
  That is the price of the doctrine on this fixture: two unsound
  conclusions that the baseline drops correctly are held, not dropped,
  because nothing independent refutes them yet.
- Both forced-agreement arms reach 15/15 coherence. Flipping the
  conclusion negates all six sound conclusions under a noisy rating and
  ends with 7 false conclusions held unflagged; silencing the rating
  retains the two unchecked unsound conclusions unflagged (3 false held).
  The baseline is also fully coherent. The rule arm is the least coherent
  (7/15) and holds the fewest false conclusions unflagged (1, the
  `ok-unsound-missed` case that every arm misses).
- The self re-check (`def-sound-self-recheck`) and the laundered check
  (`def-sound-laundered`, an external source whose basis is the rating)
  both say "refutes"; neither counts as independent, so the rule holds
  both sound conclusions. The cherry-pick request (`Q5`, citing only the
  refuting half of a conflict) is refused.

## How this differs from merged main work

The verdict's overlap section names three neighbours on main:

- `w22-revision-selectivity` (experiments/2026-11-13) audits revisions
  prompted by *external* disagreement and checks that prestige cues do not
  decide which initial answers are reversed. Here the challenge is
  internal: the agent's own rating of its reasoning, and the question is
  whether that rating may delete anything.
- `w22-spec-satisficing` (experiments/2026-11-13) refuses to drop a stated
  *requirement* for an "acceptable" reason. Here the object is a
  *conclusion* the agent reached, and the dropping authority under test is
  the agent's self-assessment, not a reason about the task.
- `w17-revision-contract` (experiments/2026-11-08) is about call identity
  in a revision contract (which call a revision belongs to). Nothing here
  tracks calls.
- New here: self-assessment is advisory, not a deletion authority. A
  defective rating flags and holds; only a cited independent refutation
  eliminates; a self re-check or a check that restates the rating is not
  independent; a missing check holds; and coherence between conclusions
  and ratings is measured as a separate quantity that two degrading arms
  maximise while scoring worse against gold.

## Files

- `scrutiny_not_authority.py`: validation and snapshot, `independent()`,
  `outcome()`, the four arms, `evaluate()`, `request_elimination()`,
  `score()` and `paper_results()`.
- `oracle.py`: the independent reference.
- `fixtures.py`: 15 synthetic cases (8 sound, 7 unsound; 10 with a
  defective rating, 6 of them noisy), hand-written labels for all four
  arms, 9 elimination requests.
- `test_scrutiny_not_authority.py`: unittest suite.
- `mutants.py`: code mutants (snippets of the module or the oracle swapped
  in memory), world mutants (fixture changes) and harness mutants (the
  row-scoped hygiene scan replaced in memory). Each must make the suite
  fail; the runner exits non-zero if any survives.
- `paper_evidence.json`: six verbatim abstract quotes with offsets, each
  UNVERIFIED and `on_unmeasured`; no paper numbers exist to record.
- `NOTICE`: credit and licence.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The quote test reads the abstract copy named in `paper_evidence.json` from
the directories listed in `$W23SCRUTINY_SOURCES` (separated by the OS path
separator); it skips when that is unset.

The hygiene tests (banned words, absolute paths, conflict markers, paper
numbers) read every file of this folder whole, but read only this PR's own
row of the day README (the line starting `- [w23-scrutiny-not-authority](`),
so rows added by other PRs are not judged here.

## Builder reflection

The tempting build was a judge that reads the conclusion and decides
whether the self-assessment is right; that would have rebuilt the very
authority the paper denies, one level up. The rule here is narrower: a
rating can only change a conclusion's status from "retained" to "held for
scrutiny", and the only thing that moves it further is a check that does
not rest on the rating. Two details mattered more than expected. First,
independence has to be checked on the basis, not only the source: an
external-looking check that just repeats the rating is the easiest way to
launder self-assessment into authority. Second, a conflict has to block
elimination for the whole case, or a request can cite around the support.
The honest cost is visible in the counts: the baseline drops two unsound
conclusions the rule only holds. The doctrine buys zero sound losses and
zero unbacked eliminations at the price of unresolved holds, which is the
trade the paper argues for; whether it is worth it depends on how cheap
the scrutiny checks are.

## Limits

- Gold labels, ratings and checks are hand-written fixture labels. A wrong
  label gives a wrong count for every arm.
- Independent checks are truthful in this world except in the two
  conflict cases. A real independent check can be wrong without any
  conflict showing, and the rule would then eliminate a sound conclusion
  on its word.
- "Independent" is a declared label (source and basis), not something the
  sketch can verify; a mislabelled check defeats the rule.
- Conclusions are treated as yes/no claims so that `NEGATE` has a truth
  value; real conclusions are rarely binary.
- The rule arm never resolves a `HOLD` by itself. Held conclusions stay
  held until a check runs; this sketch has no timeout, so nothing expires
  into a decision.
- `ok-unsound-missed` shows the obvious gap: an unsound conclusion rated
  ok and never checked is retained unflagged by every arm.
- 15 cases; the paper is an argument and states no rate, so nothing here
  tests, reproduces or measures it (`on_unmeasured`).
- Key and type checks close the input to caller-defined objects (no caller
  `__eq__`, `__hash__` or `__lt__` runs after the key check). They do not
  defend against code that runs in the same process and patches this
  module.
- Mutation kills show the suite catches these specific edits, not every
  possible fault.
