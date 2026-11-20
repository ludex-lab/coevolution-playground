# mb-answerability-pairs

An answerability audit on a tiny synthetic industrial-controller fixture. The same command is paired with two
machine states that require opposite answers: PERMIT in one state, REFUSE in the other. A decision maker that
never sees the state can look accurate on an unbalanced item set and still get no pair right. This sketch
shows that with five arms, three input conditions and three metrics, on frozen data, with no model call.

## Credit and licence

Method sketch of arXiv 2611.24682, "The Limit Is in the Input, Not the Model: State-Dependent Command Safety in
Natural-Language Interfaces to Industrial Controllers" (Taukoor, Wang, Shankararaman; submitted 18 Nov 2026).
Paper licence: arXiv nonexclusive-distrib 1.0, which is not a code licence. No repository is listed on the abstract page.
Clean room: only the abstract page was read. No code was copied; a few short abstract phrases are quoted with attribution below or paraphrased in evidence.json, and the fixture, rules and other wording are original. This is a method sketch,
not a reproduction.

Short quotes from the abstract, attributed here:

- "the same command can require opposite safety decisions in different states, so an incorrect answer may reflect missing information rather than poor reasoning"
- "the paired score counts a pair only when both answers are correct"
- the rule evaluator "is not an independent safety test"

The paper's models, systems, sample sizes and scores are not measured here. The numbers named in the
abstract are tagged UNVERIFIED and recorded as UNVERIFIED entries under `on_unmeasured` in `evidence.json`;
this README does not repeat them. The fixture counts below are this sketch's own and are not comparable
with anything in the paper.

## The fixture

`fixtures/main.json` is frozen and hand-written:

- 3 systems (`pump_station`, `boiler`, `conveyor`), each with three integer state fields.
- 6 rules, one per command. A rule names one state field, an operator (`lt`, `le`, `gt`, `ge`) and an
  integer limit. The command is PERMIT when the comparison holds and REFUSE when it does not.
- 12 pairs: the same command with `state_a` and `state_b`, where one side requires PERMIT and the other
  REFUSE. The two states differ only in the field the rule reads, and several sit exactly on the limit.
  PERMIT is the `a` side in six pairs and the `b` side in six.
- 11 extras: unpaired items (8 require PERMIT, 3 require REFUSE). They make the item set unbalanced; they
  count in raw accuracy and balanced accuracy, and never in the paired score.

That is 35 items: 20 require PERMIT and 15 require REFUSE.

## Arms

All five arms return PERMIT, REFUSE or ABSTAIN. ABSTAIN is never correct: it fails the item, and it fails the pair.

- `always_permit` and `always_refuse` ignore the input.
- `command_heuristic` reads the command text only: names starting `start_` or `open_` get PERMIT, all others REFUSE.
- `answerability_aware` answers only when the input holds the state field its rule needs; otherwise ABSTAIN.
  It needs the rules to know which field that is, and the state to read it.
- `rule_evaluator` applies the rules to the state it is given. It is the reference that the fixture's expected
  answers were written from, and it also ABSTAINs when it lacks rules or state.

The aware arm and the evaluator give the same answer on every input, not only on this fixture: both abstain
unless the input holds rules and the needed state field, and both then apply the same rule, so no fixture can
tell them apart and the report shows identical rows. They are listed as two arms only to name two roles (the
audit question "did the input contain the needed field?" and the reference for the expected answers); the
separation in this sketch is between those two and the three state-blind arms. The suite tells them apart only
by function name.

## Input conditions

- `command_only`: the command.
- `command_rules`: the command and the rules.
- `command_rules_state`: the command, the rules and the state.

The audit records what the input held. For each condition the report gives `answerable_items`, the number of
items whose input contains the state field the rule needs: 0/35, 0/35 and 35/35. An arm cannot be blamed for
reasoning badly on an item whose input never held the fact.

## Metrics

- raw accuracy: correct items over all items.
- balanced accuracy: the mean of the recall on the PERMIT items and the recall on the REFUSE items.
- paired score: the number of pairs where both sides are correct, out of 12.

All three are exact fractions (`fractions.Fraction`), printed as `n/d` with a four-place decimal.

## The four done-when checks

- (a) Without state, no answering arm gets both sides of any pair. Both sides of a pair build the same input
  in `command_only` and `command_rules`, so any arm gives both sides the same answer, and the two sides
  require opposite answers. A test checks the identical inputs, every arm, and every state-blind table of
  commands.
- (b) `always_permit` and `always_refuse` show a raw accuracy gap on the unbalanced item set (4/7 against 3/7,
  a gap of 1/7) while both have 1/2 balanced accuracy and 0 correct pairs. Remove the extras and the gap is
  gone, because the pairs alone are balanced. Raw accuracy rewards leaning toward the larger class;
  balanced accuracy and the paired score do not.
- (c) The `rule_evaluator` with rules and state gets all 12 pairs and all 35 items. This is a fixture
  completeness check, not an independent safety test: the expected answers were written from the same rules
  the evaluator applies, so a perfect score shows the fixture is complete and says nothing about whether the
  rules are safe or whether any model would obey them. A test also reads the rules a second way, inside the test
  file, and compares.
- (d) No network and no paid API: the module imports `fractions`, `json`, `re` and `sys`; tests scan every
  source file for network and API words; `evidence.json` records `network_used` and `paid_api_used` as false.

The `command_heuristic` and the two constant arms score 0 pairs in all three conditions, so adding state to the input
does not help an arm that never reads it. Abstaining scores 0 raw accuracy in the first two conditions,
below the guessing arms' raw accuracy: an honest ABSTAIN is not rewarded by raw accuracy either.

## Exit codes

`python3 -B answerability.py fixtures/main.json` prints a JSON report and exits 0. The report holds the
fixture counts, one row per condition and arm, the three checks, and the scope note. A valid fixture always
exits 0, even when a check does not hold; the checks are reported, not enforced.

Malformed input exits 2 with an empty stdout and one `ERROR <code>: <detail>` line on stderr. Codes:
`usage`, `unreadable`, `too_large`, `bad_encoding`, `not_json`, `duplicate_key`, `bad_number`, `bad_version`,
`wrong_type`, `missing_key`, `unknown_key`, `bad_id`, `bad_value`, `duplicate_name`, `unknown_system`,
`unknown_field`, `unknown_op`, `unknown_command`, `bad_answer`, `bad_state`, `pair_not_opposite`, `same_state`.
The loader rejects duplicate keys, NaN and Infinity, booleans and floats where integers are required,
ids outside `[A-Za-z0-9_]{1,40}` (which includes lone surrogates and trailing newlines), states that do not
hold exactly the fields of their system, expected answers other than PERMIT or REFUSE, pairs that do not
require opposite answers, and files over 1,000,000 bytes.

This experiment has no expiry or timeout concept, so there is no `on_expiry` field; a fixture that
supplies one is an `unknown_key` error.

## What this is not

It does not rebuild earlier experiments. There is no DENY row or exit-code scheme (a valid fixture always exits 0), no
ledger, no pre-declaration, no certified region and no check-against-verdict comparison. The only comparison
is between what an arm was given and what the item needed.

## Run

```
python3 -B -m unittest discover
python3 -B demo.py
python3 -B answerability.py fixtures/main.json
python3 -B answerability.py fixtures/bad_nan.json
python3 -B mutants.py
```

## Files

- `answerability.py`: module and CLI.
- `test_answerability.py`: unittest suite.
- `demo.py`: deterministic log of the three conditions and the checks.
- `mutants.py`: inline mutation check; every mutant must be killed by the suite.
- `evidence.json`: source, licence, measured counts, and every paper claim under `on_unmeasured`.
- `fixtures/main.json`: the frozen fixture.
- `fixtures/bad_*.json`: 53 malformed fixtures.

## Limits

- Synthetic integer states, six single-field rules and hand-set limits. Nothing here says how any real
  language model behaves, or how often real controller commands depend on state.
- No model is run. The arms are small functions written for the audit; "always permits" and "always refuses"
  are stand-ins for the behaviours the abstract describes.
- One rule per command and one field per rule. Real safety rules combine several fields and have exceptions.
- The paired score needs exactly two states per pair; larger groups of states are not modelled.
- The rule evaluator is circular by design (see (c)).
