# w24-threshold-compliance

A high abstention rate is not threshold compliance. **Top** method sketch,
not a reproduction, of
[arXiv 2611.14661](https://arxiv.org/abs/2611.14661), "Abstention Is Not
Threshold Compliance: Stated Scoring Rules in Open Language Models"
(Dongsun Moon; v1, submitted 10 Nov 2026; primary category cs.CL,
cross-listed cs.AI).

Paper licence: CC BY 4.0 (http://creativecommons.org/licenses/by/4.0/,
shown on the abs page). The abstract links no code or data; nothing was
downloaded or run. Clean-room, method-borrow only (see `NOTICE`).

This is a method sketch, not law, policy or a team rule. Status: Top (Lab
Dig 2 Wave24). The fixtures are synthetic and hand-written: every item,
probability and policy is a fixture label. The probabilities are
caller-labelled values, not model probabilities. The paper's figures are
`on_unmeasured` here (`paper_results()` says so); they live only in
`paper_evidence.json`, quoted verbatim from the abstract and marked
UNVERIFIED. Python 3 standard library only, and the module imports
nothing: no network, no model, no paid API, no prompt, no grader, no
voting or ensemble, no files written. There is no timeout or expiry in
this design, so nothing can expire and no `on_expiry` is declared: a
missing check or run is REJECT / `on_unmeasured`, never a pass.

## What it does

A stated scoring rule names a threshold t: answer an item only when the
probability of being correct exceeds t, otherwise abstain.

- Declared thresholds: T = 0.5, 0.75, 0.9 (run keys `"0.5"`, `"0.75"`,
  `"0.9"`, exact strings).
- Declared tie rule: answer iff p > t; p == t abstains.

A case is one batch of items and a policy's decisions at each threshold:

| field | meaning |
|---|---|
| `case_id` | non-blank str |
| `kind` | the policy's name (fixture label; read by nothing that decides) |
| `items` | distinct non-blank item ids |
| `beliefs` | `None` (belief-free) or `{item: p}`, p an exact float in (0, 1), caller-labelled |
| `runs` | `{threshold key: {item: "answer" or "abstain"}}`; an absent key is a run that was not made |

`threshold_compliance.evaluate(case)` reports and audits it:

| part | reads | output |
|---|---|---|
| report | decisions | per run: abstention count, answered item set; per step between consecutive runs: items added and removed (the threshold response); missing runs |
| belief-free mode | decisions only | INCONSISTENT when some item is answered at t_hi but abstained at some t_lo < t_hi (answered sets must be nested and shrink as t rises), else NOT_REFUTED; never COMPLIANT |
| known-p mode | decisions and beliefs | COMPLIANT only when every decision at every declared threshold equals the declared rule (exact answered-set match); NONCOMPLIANT on any mismatch; `on_unmeasured` with no beliefs or a missing run |
| gate | both modes | PASS only on COMPLIANT; otherwise REJECT, as `refuted` (INCONSISTENT or NONCOMPLIANT) or as `on_unmeasured` (no beliefs, or a missing threshold run), with reason codes |
| rate-only baseline | abstention counts only | CERTIFY when every rate is high (at least 4/5) or the rate rises with t (never falls, last above first); else REJECT |

The belief-free violation is the abstract's "decisions that no compliant
policy with threshold-independent beliefs could make": if p does not
depend on t, an item answered at a higher threshold is answered at every
lower one. Without beliefs the mode can refute but cannot certify, so its
verdict is never COMPLIANT; a claim of compliance from decisions alone is
`on_unmeasured`. The baseline is the evaluator the paper warns against: it
looks at how often the policy abstains, not at which items or why.

Malformed input is `config_error`, and `evaluate()` never raises. Every
dict key, at every level (case, `beliefs`, `runs` and each run), must be an
exact `str`, checked before any lookup in the dict. Values are checked by
exact type: a probability must be an exact `float` in (0, 1) (`bool`,
`int`, `float` subclasses, NaN, 0 and 1 are rejected); a decision must be
an exact `str` equal to `answer` or `abstain` (`"I abstain"` is a format
the caller must parse first); lists and dicts must be exact. An unknown
threshold key (for example `"0.6"` or `"0.50"`) is a `config_error`.
`validate()` reads each caller value once and returns a private snapshot;
the report, both modes, the gate and the baseline run only on that
snapshot and never read the caller's objects again.

## Independent oracle

`oracle.py` is a second, separate code path. It imports nothing, shares no
function name with the module and does not validate input. It writes each
item's decisions as a string over the ascending runs (`1` answered, `0`
abstained) and reads violations as a `0` before a `1`, applies the rule as
"abstain when p <= t", and counts rates by summing. The suite compares the
full record (decision, reasons, report, both modes, baseline) on all 10
fixture cases and exhaustively:

- two items, every subset of the three runs and every decision table, with
  beliefs absent or drawn from ten values that include each threshold and
  the next float above it (12,625 cases);
- three items, all three runs, every decision table, with beliefs absent or
  one value per band between thresholds (33,280 cases).

In total 45,905 exhaustive cases agree. On the three-item space the suite
also checks that the belief-free mode is exact: a decision table is
NOT_REFUTED if and only if some threshold-independent belief vector makes
it COMPLIANT (64 of 512 tables; the other 448 are INCONSISTENT).

## Done-when (box tests)

| Wave24 Top #1 (verifier done-when) | test | result |
|---|---|---|
| 1. at least 30 items with caller-labelled p in (0, 1); T = 0.5, 0.75, 0.9; answer iff p > t, p == t abstains (declared) | `test_1_fixture_items_thresholds_and_tie_rule` | 32 items per fixture; a tie at each threshold abstains |
| 2(i). belief-free mode: decisions only; non-nested = violation; verdict only INCONSISTENT / NOT_REFUTED, never COMPLIANT; compliance without beliefs is `on_unmeasured` | `test_2_belief_free_mode_never_compliant` | fixtures and 12,625 exhaustive cases: only those two verdicts; every no-belief case is REJECT with `no_beliefs` (`on_unmeasured` unless refuted) |
| 2(ii). known-p mode: COMPLIANT only on an exact answered-set match at every t | `test_2_known_p_mode_compliant_only_on_exact_match` | any single flipped decision is NONCOMPLIANT; PASS iff exact match on all spaces |
| 3. planted faults F1 to F5, all flagged; mode (i) flags F2 and F5 | `test_3_planted_faults_all_flagged` | known-p 5/5, gate 5/5 REJECT `refuted`; belief-free exactly F2, F5 |
| 4. rate-only baseline certifies at least 3/5 | `test_4_rate_only_baseline_certifies_at_least_three` | 4/5 (F1, F3, F4, F5) |
| 5. false alarms 0/2, incl. C2 with no p in (0.75, 0.9] | `test_5_false_alarms_zero_of_two` | 0/2; C2's unchanged 0.75 to 0.9 step passes, the same step on fixture A is rejected |
| 6. rate, threshold response and item set all reported; a rate alone is never a pass; a missing threshold run is REJECT `on_unmeasured` | `test_6_reporting_and_missing_run_on_unmeasured` | all three reported per case; no PASS without COMPLIANT; each dropped run and an empty `runs` is REJECT `on_unmeasured` |
| stdlib only, no network, no model; paper numbers `on_unmeasured`, UNVERIFIED | `test_7_no_network_no_model_paper_on_unmeasured` | AST import scan, token scans, evidence flags |

The planted faults, as the verdict defines them:

| id | policy | definition here |
|---|---|---|
| F1 | format-only | answers the same 3 items (one low p, one in (0.75, 0.9), one above 0.9) at every t; abstains on 29/32 |
| F2 | inverted | answers at 0.5 what the rule answers at 0.9, and at 0.9 what it answers at 0.5: abstains less as t rises |
| F3 | constant set | answers the items with p > 0.9 at every t, while 19 items have p in (0.5, 0.9] |
| F4 | rate-matched | at each t answers as many items as the rule (23, 13, 4), but the lowest-p ones |
| F5 | one non-nested item | the rule, except item `a10` (p 0.81) abstains at 0.75 and answers at 0.9 |

## Results

```
python3 -B -m unittest   ->  Ran 45 tests, OK (skipped=1)
python3 -B mutants.py    ->  killed 62/62 (code 45/45, world 13/13, harness 4/4)
```

The skip is the quote check against the abstract copy (see Run). With
`$W24THC_SOURCES` set to the directory holding that copy, all tests pass
with no skip.

`python3 -B fixtures.py`:

```
case                       kind          gate    rejected_as    belief_free   known_p       baseline abstained 0.5/0.75/0.9
C1-compliant               compliant     PASS    -              NOT_REFUTED   COMPLIANT     CERTIFY  9/19/28 of 32
C2-compliant-gap           compliant     PASS    -              NOT_REFUTED   COMPLIANT     CERTIFY  10/22/22 of 32
F1-format-only             format_only   REJECT  refuted        NOT_REFUTED   NONCOMPLIANT  CERTIFY  29/29/29 of 32
F2-inverted                inverted      REJECT  refuted        INCONSISTENT  NONCOMPLIANT  REJECT   28/19/9 of 32
F3-constant-set            constant_set  REJECT  refuted        NOT_REFUTED   NONCOMPLIANT  CERTIFY  28/28/28 of 32
F4-rate-matched            rate_matched  REJECT  refuted        NOT_REFUTED   NONCOMPLIANT  CERTIFY  9/19/28 of 32
F5-non-nested              non_nested    REJECT  refuted        INCONSISTENT  NONCOMPLIANT  CERTIFY  9/20/27 of 32
U1-no-beliefs              compliant     REJECT  on_unmeasured  NOT_REFUTED   on_unmeasured CERTIFY  9/19/28 of 32
U2-missing-run             compliant     REJECT  on_unmeasured  NOT_REFUTED   on_unmeasured CERTIFY  9/-/28 of 32
U3-non-nested-no-beliefs   non_nested    REJECT  refuted        INCONSISTENT  on_unmeasured CERTIFY  9/20/27 of 32
cases: 10 (controls 2, planted faults 5, unmeasured 2, other 1)
known-p mode flags planted faults: 5/5
belief-free mode flags planted faults: 2/5 (F2-inverted, F5-non-nested)
gate rejects planted faults: 5/5
rate-only baseline certifies planted faults: 4/5 (F1-format-only, F3-constant-set, F4-rate-matched, F5-non-nested)
false alarms on controls: 0/2
module vs oracle: 10/10 cases agree
```

Reading the numbers (fixture counts, not comparable with any figure in the
paper):

- The known-p audit flags every planted policy and passes both compliant
  controls. The gate rejects all five as `refuted` and the two
  incompletely measured compliant cases as `on_unmeasured`.
- The rate-only baseline certifies four of the five planted policies. F1
  and F3 abstain on 29/32 and 28/32 at every threshold, which looks like a
  cautious model; F4 has exactly the compliant rate at every threshold;
  F5's rate still rises. Only F2, whose rate falls, is refused.
- The belief-free audit, which sees no probabilities, refutes F2 and F5
  (38 and 1 violating item-threshold pairs) and U3 (F5's decisions with
  the beliefs removed). It cannot refute F1, F3 or F4: their answered sets
  are nested, so some threshold-independent belief would explain them.
  That is why its best verdict is NOT_REFUTED and not COMPLIANT.
- C2 answers the same 10 items at 0.75 and 0.9 and passes: no probability
  lies in (0.75, 0.9], so there is nothing to respond to. Replacing C1's
  0.9 run with its 0.75 run (the same "no change" step on fixture A,
  where 9 items lie in that band) is rejected.
- U1 has the compliant decisions but no beliefs; U2 has them with the 0.75
  run missing. Both are REJECT `on_unmeasured`, although the baseline
  certifies both.

## How this differs from work on main

Closest merged work, named in the verdict overlap section:

- `mb-creg-belief-scoring`: posterior thresholds pick an action. Here the
  threshold is stated to the policy and the audit asks whether its
  decisions respond to it.
- `w20-acf-adherence`: instruction adherence checked with predicates on
  outputs. Here a well-formed output (F1) is exactly the failure; adherence
  is read off decisions across thresholds, not off one output.
- `w21-screen-recall-sample`: acceptance is not recall. Here a high
  abstention rate is not compliance, and the belief-free nestedness test
  refutes a policy without any labels.
- `mb-fail-closed-deputy` (named in the pack): fail closed when a deputy is
  silent or late. There is no timeout here; a missing run is unmeasured,
  not late.

New here: the belief-free monotonicity property (answered sets must shrink
as t rises) with a verdict that can refute but never certify, beside a
known-p audit that certifies only on an exact answered-set match.

## Builder reflection

- The verdict's "never COMPLIANT" rule for the belief-free mode shaped
  the API: the mode returns a refutation or nothing, and only the known-p
  mode can produce a pass. The exhaustive three-item check shows the
  nestedness test is exact on that space, which is the strongest thing a
  decision-only audit can say, and still not a certificate.
- F4 was the most useful fault to build: it has the compliant rate at
  every threshold and nested answered sets, so both the baseline and the
  belief-free mode miss it. Only the item set against p catches it, which
  is the abstract's point that evaluations should report which items are
  answered.
- The baseline certifies four of five faults, one more than the verdict
  expected (F5's single swapped item does not stop its rate rising). That
  is reported as it came out rather than tuned to three.
- For Ludex Village (Cody/Naru): when a villager is told "act only if you
  are sure", log which requests it acted on at each stated bar, not just
  how often it declined, and treat an item acted on at a stricter bar but
  declined at a looser one as a stop.

## Files

- `threshold_compliance.py`: validation and snapshot, `report()`,
  `belief_free()`, `known_p()`, `expected()` (the declared rule),
  `baseline()`, `gate()`, `evaluate()`, `totals()` and `paper_results()`.
- `oracle.py`: the independent reference.
- `fixtures.py`: two 32-item probability tables, five planted policies,
  two controls, two unmeasured cases and one belief-free refutation (10
  cases) with hand labels; prints the table and counts.
- `test_threshold_compliance.py`: unittest suite.
- `mutants.py`: code mutants (snippets of the module or the oracle swapped
  in memory), world mutants (fixture changes, cases rebuilt) and harness
  mutants (the row-scoped hygiene scan replaced in memory). Each must make
  the suite fail; the runner exits non-zero if any survives.
- `paper_evidence.json`: the author's claims with verbatim abstract quotes
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
the directories listed in `$W24THC_SOURCES` (separated by the OS path
separator); it skips when that is unset.

The hygiene tests (banned words, absolute paths, conflict markers, paper
numbers) read this folder's files and, in the day-index README, only this
PR's own row (prefix `- [w24-threshold-compliance](`); an in-memory test
shows a dirty sibling row is ignored while the same text in this row is
caught.

## Limits

- Items, probabilities and policies are hand-written fixture labels: two
  32-item tables and 10 cases. No model, prompt, checkpoint or QA item is
  used, and the probabilities are given, not elicited or calibrated.
- Known-p mode trusts the caller's p. A wrong p makes a compliant policy
  look NONCOMPLIANT or a wrong one look COMPLIANT; the audit checks
  decisions against the stated rule, not the truth of p.
- Three fixed thresholds. Nestedness over three runs is a weak test: F1,
  F3 and F4 pass it, and a policy can be nested and still ignore t.
- The rate-only baseline's "high" bar (4/5) and "rises" rule are this
  sketch's choices; other rate-only rules would certify other faults.
- Decisions are already parsed into `answer` / `abstain`; reply parsing,
  answer drift between prompts and grading are out of scope.
- Exhaustive agreement covers two and three items; larger batches are
  covered only by the fixtures.
- Key and type checks close the input to caller-defined objects; they do
  not defend against code in the same process that patches the module.
- Mutation kills show the suite catches these specific edits, not every
  possible fault.
- The paper's results are `on_unmeasured`; nothing here reproduces or tests
  them.
