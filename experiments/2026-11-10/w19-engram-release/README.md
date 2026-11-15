# w19-engram-release

A skill's experience records stay in retrieval until a check shows the
student can do without them. Admission to training and release from
retrieval are two separate gates, and release needs both a relative and an
absolute score criterion on reserved probes.

This is a method sketch of the release-after-verification idea in arXiv
2611.09472, ENGRAM (Yang, Li, Li, Yin, Xue and Salim). It is not a
reproduction, not the paper's system, not village law and not Team OS law.
Clean-room Python 3 stdlib, synthetic data, no network at runtime, no
training, no weights, no language model in the loop.

## Run

```
cd experiments/2026-11-10/w19-engram-release/ && python3 -m unittest test_engram_release.py -v && python3 fixtures.py
```

The tests are plain `unittest` classes and need nothing beyond the standard
library. One excerpt check reads the abs page from `/tmp` and is skipped when
it is absent:

```
curl -sL -A 'Mozilla/5.0' https://arxiv.org/abs/2611.09472 -o /tmp/w19er-abs.html
```

## What is in it

- `engram_release.py`: the `Record` and `Store`, the admission gate, the
  training step, the toy models and the check layer (`detect_probe_overlap`,
  `compare`, `verify`, `release`, `report`).
- `fixtures.py`: twenty-seven release scenarios, twelve score-only cases and
  one unknown-skill case, each with its expected outcome; `python3 fixtures.py`
  prints one PASS/FAIL line per fixture and one report line.
- `test_engram_release.py`: unit tests, the compliant path, the criteria,
  exact floor boundaries end to end, the probe-copy and near-copy checks,
  answer typing, admission edge cases, fail-closed cases, hygiene and
  evidence checks.
- `paper_evidence.json`: licence, citation, the upstream link and its
  status, the three abstract excerpts, method excerpts, and the paper's own
  figures marked UNVERIFIED.

## The method as sketched

A `Store` holds `Record` objects per skill. Each record is in one state:

- `stored`: in the store and retrievable;
- `admitted`: the skill passed admission; still retrievable;
- `released`: moved to a non-retrievable archive (kept, not deleted).

`admit` is the training-participation decision only. It follows the paper's
demonstration-aware rule: the skill is admitted when student mastery meets
`tau_m`, the skill has at least `n_min` records and has not been
consolidated before, or when it has at least `d_min` successful teacher
records. Failed records never count as demonstrations, and a mastery equal
to `tau_m` meets it. Admission never takes anything out of retrieval.

The paper also lets a consolidated skill qualify again through the mastery
branch once its mastery has risen by a configured amount. That
re-qualification is left out on purpose: here a consolidated skill can only
re-enter through the demonstration branch, which is stricter. A test pins
this.

`train` builds the skill's valid training examples from its admitted,
successful records and hands them to the student. The skill gets training
participation only when that set is non-empty and fitting succeeds. A
training failure leaves the store and participation as they were.

`release(store, skill, student, base, probes, alpha=..., delta=0.0)` is the
release gate. It archives records only when all of these hold:

1. the skill is known and was admitted;
2. it has training participation;
3. the reserved probe set is a non-empty list of `(input, expected)` pairs
   of plain `str` (not a subclass), no probe input or expected output
   matches any record input or output of the skill under the normalised
   comparison below, and no reference adversary built from the record text
   answers any probe (the pre-check below);
4. relative criterion: the student's probe score without retrieval minus the
   base's probe score with retrieval (from the pre-release store) is at
   least the margin `delta`;
5. absolute criterion: the student's score is strictly above the floor
   `alpha`.

Only records that took part in training are archived; a record added later
stays retrievable. After a release, `retrieve(skill)` no longer returns the
archived records. There is no default floor; the caller states `alpha`.

Numbers are compared exactly. Probe scores are fractions, and every score,
margin, floor, mastery and mastery threshold is converted to an exact
fraction before it is compared. Only plain `int`, `Fraction` and finite
plain `float` count as numbers; a bool, a subclass (a numpy-like float, a
float with its own `repr`), Decimal, str or anything else holds, and the
conversion never raises, so `verify` and `admit` return a hold instead of
an error. A float is read two ways, as its shortest decimal form and as the
simplest fraction with a denominator up to a million that rounds to the
same float, and the stricter reading is used: the higher one for a floor,
margin, mastery threshold or base score, the lower one for a student score
or mastery estimate. So a floor written `0.6` is exactly three fifths, a
floor written `1 / 3` is read as one third, and a student at exactly the
floor is held at `0.3`, `0.6`, `0.7` or any other such floor, as the strict
floor in the paper requires. A float floor that is neither a short decimal
nor close to a simple fraction is only as exact as the float itself:
**pass any floor that is not decimal-exact (for example one third) as a
`Fraction`**, which is used as given. Answers count only when they are `str` and equal to the
expected string; any other type is wrong, including an object whose
equality test always says yes.

Everything else is `hold`, and a hold changes nothing: every record stays
retrievable in its earlier state. That covers each failed criterion and
every malformed input: a score, margin or floor that is not a finite real
(NaN, infinity, a string, `None`), a bool given as a number, a score outside
`[0, 1]`, a margin outside `[-1, 1]`, a floor outside `[0, 1)`, an empty or
malformed probe set, an unknown or non-string skill, a second release with
nothing left to archive, a model that raises, and a store or any other
argument that breaks the gate part-way (the outer handler holds; it never
reports a release). The check layer reports,
compares, detects and holds; it has no path that skips verification.

## The toy models and why the probe is not a copy

Each skill has a true string rule (`upper`, `reverse`, `sort`, `double`, and
`capitalize`). A record holds input/output examples of that rule.

- `Student` induces a rule from its training examples, picking the first
  rule in a fixed library that fits them all, and answers from that rule
  alone. Its `answer(skill, x)` has no retrieval argument.
- `RetrievalBase` answers with the retrieved records in context: it copies
  an exact match if one is there, otherwise it induces from them.
- `MemorisingStudent` copies record examples into a lookup table and answers
  only inputs it has seen.

Probes are held-out inputs labelled by the true rule (`make_probes`). The
gate holds with `probe_overlaps_record` when a probe's input or expected
output matches any record input or output of the skill, in any state, after
`normalise`: Unicode compatibility form, accents dropped, case folded, a few
Cyrillic and Greek look-alike letters mapped to Latin, and whitespace,
punctuation and invisible characters removed. It also compares with
character order ignored, so a reordered copy is caught. The paper
deduplicates normalised questions across partitions and uses
question-answer matching as an extra check, without spelling out the
normalisation; the key here is this sketch's own, stricter choice.

So a student that memorised the record text scores zero on the probes and
cannot be released, and a probe set copied from the records, even with
changed case, spacing, punctuation, width, accents, look-alike letters or
letter order, is held before scoring.

## Reference-adversary pre-check

Matching probes against records one string at a time misses probes built
from several records: under `upper`, `abcdog` is two record inputs spliced
together, and a lookup table that splits it and joins the stored outputs
answers it without learning anything. So before any model is scored, the
gate runs a fixed set of lookup-only reference students built from the
skill's record text alone (all records, in any state):

- `exact_lookup`: the probe input as stored;
- `normalised_lookup`: the probe input under the normalised and
  order-free keys;
- `segmentation`: every way to split the probe input into whole record
  inputs, answering with the stored outputs joined in order (exhaustive,
  not greedy);
- `normalised_segmentation`: the same over normalised inputs, so case,
  spacing, punctuation and width do not hide a splice.

Each answer is compared with the expected output both exactly and
normalised. If any of them answers any probe correctly, the gate holds with
`probe_answerable_from_records` and the records stay retrievable. If a
segmentation has more candidate answers than a fixed cap, it cannot be
ruled out and the gate holds too. A student that generalises still clears
this on probes that are not built from record inputs; the compliant
fixtures and a test show it.

## Limits of the copy checks

The reference adversaries are a fixed, small family. They do not cover:

- arbitrary programs over record text (a copier that reverses, slices,
  interleaves or otherwise edits stored outputs before answering);
- partial overlaps: probes that share part of a record input without being
  made of whole record inputs (truncations, prefixes or suffixes added to a
  record input, one-letter edits). These are not flagged; in the tests the
  lookup-only copiers answer none of them, but that is a property of these
  toy rules and copiers, not a guarantee;
- transformations beyond the normalisation (spelling variants, synonyms,
  scripts or look-alikes outside the small mapped set);
- composition beyond in-order concatenation of whole record inputs
  (reordered pieces, pieces from the outputs, overlapping pieces, or any
  rule that combines records in another way).

A probe set that survives every check is evidence only against these
copiers. Probes still have to be reserved and held out by construction;
the checks hold obvious leaks, they do not certify a probe set.

## How each requirement is shown

| Requirement | Fixture | Tests |
|---|---|---|
| compliant path: learned, released, no longer retrievable | `compliant_upper_released`, `compliant_double_released`, `late_record_not_trained_stays` | `test_learned_released_then_not_retrievable`, `test_student_still_answers_after_release`, `test_only_participating_records_released`, `test_release_of_one_skill_leaves_others` |
| unmastered skill cannot be released | `unmastered_sort_held`, `rule_outside_library_held` | `test_unmastered_cannot_release` |
| relative criterion alone fails: record kept | `fails_relative_only_held` | `test_fails_relative_only_record_stays`, `test_margin` |
| absolute criterion alone fails: record kept | `fails_absolute_only_held`, `verify/score_at_floor_is_below_strict_floor` | `test_fails_absolute_only_record_stays`, `test_relative_equality_passes_and_floor_is_strict`, `test_release_floor_at_score_holds` |
| score exactly at a decimal floor holds end to end | `floor_equal_score_held` | the `ExactBoundary` class |
| admission is separate; not admitted or not trained cannot be released | `not_admitted_held`, `admitted_not_trained_held`, `admitted_no_valid_examples_held`, `training_failure_held` | the `AdmissionIsSeparate` class |
| failed verification leaves the record retrievable | every `*_held` fixture | `test_every_hold_scenario_changes_nothing`, `test_failed_verification_record_states_unchanged` |
| probe is not answerable by copying record text | `memorising_student_held`, `probe_copies_record_held`, `case_variant_probe_held`, `reordered_probe_held` | the `ProbeCopyTautology` and `NearCopyProbes` classes |
| probe spliced from record inputs is held by the pre-check | `concat_probe_held`, `three_way_concat_held`, `concat_case_space_held` | the `ReferenceAdversaries` class |
| odd numbers and probe types hold, never raise | | the `Hardening` class |
| only `str` answers score | `non_str_answer_held` | the `StrOnlyScoring` class |
| admission edges: mastery at `tau_m`, failed records not demonstrations, no re-qualification on a mastery rise | | the `Eq2Edges` class |
| a gate that breaks part-way holds | | the `OuterHandlerHolds` class |
| student scored without retrieval, base with it | all scored fixtures | the `StudentWithoutRetrieval` class |
| malformed inputs fail closed | `empty_probes_held`, `model_error_held`, `nan_floor_held`, `inf_margin_held`, `bool_floor_held`, `string_floor_held`, `floor_of_one_held`, the score-only cases, `unknown_skill_held` | the `FailClosed` class |

The `sort` fixtures carry the two single-criterion failures. The student is
trained only on inputs whose letters run backwards, so reversing fits its
examples as well as sorting does and it induces `reverse`. In the
relative-only case a later record breaks that tie for the base with
retrieval, so the base scores higher while the student still clears the
floor. In the absolute-only case there is no such record: student and base
induce the same rule and score the same, which meets the relative criterion
and still falls short of the floor.

## Overlap with earlier sketches

- [#97](https://cursor.com/codebase/coevolution-lab/playground/pull/97)
  (memory-scope) decides where a note applies.
- [#104](https://cursor.com/codebase/coevolution-lab/playground/pull/104)
  (skill-assurance) decides what enters a skill registry.

This sketch decides neither. It decides when a record may leave retrieval,
on evidence that the skill is held without it, and holds that decision apart
from the decision to train on the record. Nothing from those sketches is
rebuilt here.

## What this is not

- Not the paper's system: no Engram Trace Graph, no adapter, no fine-tuning,
  no replay, no residual-record retention, no serving path and no benchmark.
  The "student" picks one of four library rules in a five-rule toy domain.
- Not a measurement: every fixture outcome is synthetic and says nothing
  about any model.
- Not a policy: it is a method sketch, not Team OS law and not village law.

## UNVERIFIED numbers

The paper's release counts, footprint, probe threshold and F1 figures are
recorded in `paper_evidence.json` under `empirical_claims`, each marked
UNVERIFIED. None of them is used or checked here, and none appears in the
code, fixtures or this README.

## Licence and upstream code

The paper is under CC BY 4.0
(http://creativecommons.org/licenses/by/4.0/), confirmed from the abs page
licence link. This sketch takes the method and shape only; no paper text is
copied into the code, fixtures or prose. Short attributed excerpts sit in
`paper_evidence.json` as evidence.

The abs page links the paper's code at
http://anonymous.4open.science/r/engram-anonymous. As checked on 2026-11-10
(17:20 and 17:30 JST), the page returns HTTP 500, while the site's file API
lists a source tree with no LICENSE file. Its `pyproject.toml`, read as text
only, depends on torch, transformers, peft and openai, with an optional
anthropic extra: model-training stacks and paid model API clients, with no
licence. That rules it out here. The upstream code is UNVERIFIED and was not
used: only the file listing, its README and `pyproject.toml` were read as
text; nothing was cloned, installed, imported or run, and there is no
upstream pin. The sketch is implemented from the paper text only. See
`NOTICE`.

## Builder reflection

The gate is only as honest as its probe. A student that copies its records
passes any probe drawn from those records, so the probe set has to be held
out and the overlap has to be checked before scoring, not trusted. The two
`sort` cases were worth building because each criterion catches a failure
the other misses. The quieter gaps were a float floor that three fifths
beat in binary and copy checks that compared one string at a time, so
floors are now exact fractions and lookup-only reference copiers, splicing
included, must fail every probe before anything is scored.

Ludex: Cody may put away the recipe card for Naru's soup only after he cooks
it without the card, as well as Naru does with it in hand, on a day of
vegetables the card never mentions; until then the card stays on the shelf.

Implementation may be complete; it is not declared verified.
