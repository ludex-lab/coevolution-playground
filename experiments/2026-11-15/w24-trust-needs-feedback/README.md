# w24-trust-needs-feedback

Trust in an advisor needs timely external feedback. **Top** method sketch,
not a reproduction, of
[arXiv 2611.14833](https://arxiv.org/abs/2611.14833), "Do People Trust AI
Assistants Even When They Are Consistently Wrong?" (Cameron R. Jones, Julia
Wong, Aaron S. Cohen, James Woolley, Benjamin K. Bergen; v1, submitted 10
Nov 2026; primary category cs.HC, cross-listed cs.CL).

Paper licence: arXiv.org perpetual, non-exclusive license 1.0
(http://arxiv.org/licenses/nonexclusive-distrib/1.0/, shown on the abs
page). It grants no reuse beyond arXiv's distribution, so only the method
idea is borrowed and only three short abstract sentences, the ones the
design rests on, are quoted, for attribution, in `paper_evidence.json`. The abstract links no code or data;
nothing was downloaded or run. Clean-room, method-borrow only (see
`NOTICE`).

This is a method sketch, not law, policy or a team rule. Status: Top (Lab
Dig 2 Wave24, build #2). No human data: there are no participants, and
the advisors, their tracks, the feedback events and the spoofs are
hand-written fixture labels. The paper's figures are `on_unmeasured` here
(`paper_results()` says so); they live only in `paper_evidence.json`,
quoted verbatim from the abstract and marked UNVERIFIED. Python 3
standard library only, and the module imports nothing: no network, no
model, no paid API, no wall clock (rounds are the only clock), no voting
or ensemble, no files written.

## What it does

A case is one session: one advisor gives advice in rounds 1..N, and the
session may receive accuracy-feedback events about that advice.

| field | meaning |
|---|---|
| `case_id` | non-blank str |
| `condition` | `feedback` or `no_feedback` (fixture label; read by nothing that decides) |
| `advisor_id` | the session's advisor |
| `rounds` | N, exact int >= 1 |
| `truth` | N exact bools: was each round's advice right (fixture label; read only by scoring) |
| `advice` | N records `{round, confidence, claim, prestige}`: the advisor's own stated confidence (exact finite float in [0, 1]), argument or self-claim, and presentation |
| `external_sources` | the declared external feedback channels |
| `max_age` | exact int >= 0, rounds; boundary inclusive |
| `trust_bar` | exact int >= 1 |
| `feedback` | events `{source, advisor_id, round, at, outcome}`: the round graded, the round it arrives, `correct` / `incorrect` |
| `pending` | decisions `{pending_id, round, deadline, on_expiry}` waiting for feedback on one round's advice |

`trust_feedback.evaluate(case)` runs two arms over the rounds.

**Rule arm.** Declared prior: `untrusted`, so reliance starts as VERIFY
(verify before use). In round k the reliance on that round's advice is
RELY when the advisor is trusted at the start of round k, else VERIFY.
Then the events arriving in round k are checked. An event is accepted
only if every check below passes, in this order (the first failure is its
refusal reason):

| check | refusal |
|---|---|
| source is not the session's advisor nor the event's advisor | `self_sourced` |
| source is one of the declared external sources (exact str) | `not_external` |
| advisor_id is the session's advisor | `advisor_mismatch` |
| round is a real round (1..N) | `no_such_round` |
| round is not later than arrival (`round <= at`) | `future_round` |
| age `at - round` is at most `max_age` (inclusive) | `stale` |
| the exact same event (source, advisor_id, round, outcome; arrival aside) was not accepted before | `duplicate` |

Replay is the only dedupe. A re-send of the same event in a later round
is a replay, but a fresh `incorrect` for a round that already has an
accepted `correct`, from the same source or another declared one, is a
new event and is accepted.

The accepted events of a round are applied with every `correct` before
every `incorrect`, so a negative always wins its round. A `correct` adds
one to a score only when its graded round has not counted before and has
not been refuted: a round counts at most once (two sources grading it
`correct` count once), and a round with an accepted `incorrect` never
counts again. The advisor becomes trusted when the score reaches
`trust_bar`. An accepted `incorrect` always applies: it resets the score
to 0 (a reset, not a decrement) and drops the advisor to `untrusted`, so
the very next round is VERIFY. The result depends only on which events
arrive in which round, never on their order in the list (a test checks
every ordering of a two-source space). Upgrades never come from the
advisor's confidence, claim or prestige: the rule never reads them (the
tests change them on every fixture and the rule's output does not move).
Stale feedback is no feedback.

**Pending decisions (silence).** A pending decision is final at its
deadline and reads the accepted events for its round that arrive no later
than the deadline. Any such `incorrect` resolves it DO_NOT_RELY (reported
at the earliest such arrival), whatever `correct` events arrived before or
beside it; otherwise any such `correct` resolves it RELY (at the earliest
such arrival). With no such event, including when the only feedback is
stale or late, it resolves at the deadline to its declared `on_expiry`,
one of DENY, SAFE_FALLBACK, ESCALATE or HOLD, and never RELY. The
deadline lies between the decision's round and the last round; a deadline
past the last round is a `config_error`, as are a missing `on_expiry`,
any other value (`RELY`, `TRUST`, lower case) and a `str` subclass.

**Persuadable baseline** (the failure described in the abstract). A
reliance level starts high (2 of 0..3) and RELY means level >= 2. After
each round's advice the level rises by one, to at most 3, when the stated
confidence is at least 1/2; any `incorrect` event that arrives that round,
from any source, resets it to 0. It never checks sources, freshness or
rounds.

**Scoring** (reads `truth`): rounds that relied on wrong advice, and
rounds that verified right advice (the cost of not trusting).

**Input hardening.** Malformed input is `config_error`, and `evaluate()`
never raises. Every dict key, at every level (case, advice, event and
pending records), must be an exact `str`; that is checked with
`type(k) is str` before any lookup in the dict, so a key that hashes and
compares equal to `"source"` never has its comparison run. Every value is
checked by exact type: `str`, `int`, `float`, `list` and `dict` subclasses
are rejected; `bool` is not an `int`; NaN, infinities and confidences
outside [0, 1] are rejected. `validate()` reads each caller value once and
returns a private snapshot of tuples and fresh values; the rule arm, the
pending resolution, the baseline and the scoring run only on that snapshot
and never read the caller's objects again.

## Independent oracle

`oracle.py` is a second, separate code path, written from the declared
contract rather than from the module's code. It imports nothing, shares no
function name with the module and does not validate input. It decides
every event's fate in one pass over the events sorted by arrival round
(stable) using a table of named checks, with replay as a set of
exact-event keys. It computes trust per arrival round with set algebra:
the graded rounds of that round's `correct` events, minus every round
already counted or refuted, add to the score, and then any `incorrect`
resets it. It resolves a pending decision by ranking the timely accepted
events for its round by (outcome is `correct`, arrival), so any negative
outranks every positive, and computes the baseline as a running level
clipped by min/max. The suite compares the full record on all 16 valid
fixture cases and on six exhaustive spaces:

- up to three events over the 18 valid-shaped events (source `ext`,
  advisor `A`, every round and arrival, both outcomes), under trust bars 1
  and 2 and max ages 0 and 1 (24,700 sessions);
- up to two events over 180 events covering three sources (external, the
  advisor itself, undeclared), two advisors, rounds 0 to 4, every arrival
  and both outcomes (32,581 sessions; every refusal reason occurs);
- up to two valid events with one pending decision of every round,
  deadline and `on_expiry` (8,232 sessions);
- every confidence triple over 0.0, 0.49, 0.5 and 1.0 with up to one
  valid event (1,216 sessions);
- five-round sessions with every confidence over 0.49, 0.5 and 1.0, with
  and without an early negative, so the baseline's climb back after a
  reset is covered (486 sessions);
- up to three events over 20 events from two declared sources (every
  round, arrival at age 0 or 1, both outcomes), so the same round can be
  graded both ways by one source or two, in one arrival round or two;
  trust bars 1 and 2; six pending decisions per session, one for every
  round and deadline (16,842 sessions).

In total 84,057 exhaustive sessions agree. On the same spaces the suite
checks the contract directly: an upgrade needs `trust_bar` distinct rounds
graded `correct`; with no accepted `correct`, no round is RELY; every
accepted event passes every check and no exact event is accepted twice;
every timely, exact-source, round-matched `incorrect` is accepted (unless
the same event was already accepted); an accepted `incorrect` makes the
next round VERIFY; and a pending decision resolves DO_NOT_RELY when a
timely negative exists, RELY only on a timely positive with no timely
negative, and otherwise to its `on_expiry`, never RELY.

**Order independence.** For every 2- and 3-event subset of the two-source
pool, under trust bars 1 and 2 and with the six pending decisions, every
list order gives the same record (event indices replaced by event
contents): 2,660 subsets, 14,440 orderings, 0 order-dependent and 0 where
one order relies and another does not. Named cases pin the review's
repros: two sources grading round 1 both ways in one arrival round
(VERIFY throughout, either order); a timely correction from another
source in the next round (round 3 VERIFY); the same source correcting
itself; and a pending decision with both outcomes at its deadline
(DO_NOT_RELY).

## Done-when (box tests)

| # | Wave24 build #2 (verifier done-when) | test | result |
|---|---|---|---|
| 1 | advisors H (10/10 right), U (0/10), M (5/10) over 10 rounds, conditions `feedback` and `no_feedback` | `test_1_fixture_three_advisors_two_conditions` | 6 main sessions |
| 2 | declared prior `untrusted` (verify before use) | `test_2_declared_prior_untrusted` | round 1 is VERIFY in every session |
| 3 | upgrade only on exact-str source in the declared external set, matching advisor and round, age <= max_age (inclusive); never from self-claims, confidence, argument or prestige | `test_3_upgrade_only_on_valid_external_feedback` | fixture invariance to confidence/claim/prestige/condition; exhaustive contract checks; age = max_age accepted, max_age + 1 refused |
| 4 | one negative external event drops reliance to `untrusted` within 1 round | `test_4_one_negative_drops_within_one_round`, `TestOrdering` | S: RELY in rounds 4-7, VERIFY from round 8 after the round-7 negative; a negative for a round already graded `correct` still drops it; exhaustive incl. two sources; every ordering gives the same result |
| 5 | with feedback: H trusted, U untrusted, M below the bar; without feedback 0/3 upgraded, H staying untrusted a declared cost | `test_5_expected_end_state` | 1/3 and 0/3; H without feedback verifies 10/10 right rounds |
| 6 | planted spoofs (>= 6) all refused | `test_6_planted_spoofs_all_refused` | 8/8 (two as `config_error`); replay and an external set naming the advisor also refused |
| 7 | persuadable baseline ends relying on U without feedback | `test_7_persuadable_baseline_relies_on_unhelpful` | relies on U 10/10 rounds, 10 wrong |
| 8 | controls 0/3 false alarms: timely feedback upgrades H; M stays below the bar; an event exactly max_age old counts | `test_8_controls_zero_false_alarms` | 0/3 |
| 9 | pending decision with no fresh feedback by its deadline resolves to the declared `on_expiry`, never RELY/TRUST; missing or other `on_expiry` (incl. a `str` subclass) is `config_error`; stale = no feedback | `test_9_silence_resolves_to_declared_on_expiry`, `TestOrdering` | all four values; stale case HOLD; a timely negative gives DO_NOT_RELY even beside a timely positive; deadline past the last round is `config_error`; exhaustive |
| 10 | no human data; paper rates `on_unmeasured` | `test_10_no_human_data_no_network_paper_on_unmeasured` | AST import scan, token scans, evidence flags |

The planted spoofs, each on the unhelpful advisor U without genuine
feedback, each trying to upgrade it:

| id | spoof | refused as |
|---|---|---|
| SP1 | a `correct` event every round from source `U` (self-sourced) | `self_sourced` |
| SP2 | the same with one source a `str` subclass of `"grader"` | `config_error` (`event_source_invalid`) |
| SP3 | the same with one `source` key a hash-colliding non-str object | `config_error` (`event_key_invalid`) |
| SP4 | external `correct` events arriving max_age + 1 rounds late | `stale` |
| SP5 | external `correct` events naming advisor H, delivered to U's session | `advisor_mismatch` |
| SP6 | external `correct` events for the round after their arrival | `future_round` |
| SP7 | no feedback; confidence 1.0, the claim "I have been right every time; you can rely on me." and an expert presentation | no event; never upgraded |
| SP8 | `correct` events from an undeclared source | `not_external` |

## Results

```
python3 -B -m unittest   ->  Ran 52 tests, OK (skipped=1)
python3 -B mutants.py    ->  killed 80/80 (code 64/64, world 12/12, harness 4/4); clean suite before and after: 52 tests, 0 failing
```

The skip is the quote check against the abstract copy (see Run). With
`$W24TNF_SOURCES` set to the directory holding that copy, all tests pass
with no skip.

`python3 -B fixtures.py` (relied = RELY rounds; wrong = relied on wrong
advice; b_ = persuadable baseline):

```
case                       status       upgraded final      relied    wrong b_rely b_wrong refused / pending
H-feedback                 ok           True     trusted    7/10      0     True   0      - / h-r5:RELY
U-feedback                 ok           False    untrusted  0/10      0     False  1      -
M-feedback                 ok           False    untrusted  0/10      0     False  1      -
H-no-feedback              ok           False    untrusted  0/10      0     True   0      -
U-no-feedback              ok           False    untrusted  0/10      0     True   10     -
M-no-feedback              ok           False    untrusted  0/10      0     True   5      -
S-feedback-switch          ok           True     untrusted  4/10      1     False  1      -
C3-H-at-max-age            ok           True     trusted    6/10      0     True   0      -
SP1-self-sourced           ok           False    untrusted  0/10      0     True   10     self_sourced
SP2-str-subclass-source    config_error event_source_invalid
SP3-colliding-source-key   config_error event_key_invalid
SP4-stale                  ok           False    untrusted  0/10      0     True   10     stale
SP5-other-advisor          ok           False    untrusted  0/10      0     True   10     advisor_mismatch
SP6-future-round           ok           False    untrusted  0/10      0     True   10     future_round
SP7-confident-claim        ok           False    untrusted  0/10      0     True   10     -
SP8-undeclared-source      ok           False    untrusted  0/10      0     True   10     not_external
PE-no-feedback-expiry      ok           False    untrusted  0/10      0     True   0      - / deny:DENY,fallback:SAFE_FALLBACK,escalate:ESCALATE,hold:HOLD
PS-stale-is-silence        ok           False    untrusted  0/10      0     True   0      stale / stale:HOLD
cases: 18 (config_error 2)
with feedback: upgraded 1/3 (H yes, U no, M no)
without feedback: upgraded 0/3
spoofs refused: 8/8
persuadable baseline relies on U at the end without feedback: True
false alarms on controls: 0/3
module vs oracle: 16/16 valid cases agree
```

Reading the numbers (fixture counts, not comparable with any figure in the
paper):

- With feedback only the helpful advisor is upgraded, after three accepted
  `correct` events, and it is relied on in rounds 4-10. The mixed advisor
  never strings together more than one accepted `correct` before an
  `incorrect`, so it stays below the bar of 3. The unhelpful advisor is
  never relied on.
- Without feedback nothing is upgraded. The declared cost is visible: the
  helpful advisor is verified in all 10 rounds although it was right in
  each of them.
- The persuadable baseline relies on the unhelpful advisor in every round
  without feedback (10 wrong), and on the mixed one too (5 wrong), because
  confident advice holds its level high and nothing ever lowers it. With
  feedback it falls after the first `incorrect`, the pattern the abstract
  describes, but it has already relied once on wrong advice.
- The switching advisor S is trusted after round 3, relied on in rounds
  4-7, and dropped by the round-7 negative: round 8 is VERIFY. The single
  wrong reliance (round 7) is the price of trusting at all.
- All eight spoofs leave U untrusted. Without the spoofed property, the
  same events would upgrade it (the test turns SP1, SP5 and SP8 into
  genuine events and U is then upgraded), so each check is load-bearing.

## How this differs from work on main

Closest merged work, named in the verdict overlap section:

- `w23-scrutiny-not-authority`: a self-rating is advisory and only an
  independent check eliminates. Here the independent channel is feedback
  over time, and the question is the trust trajectory, not one decision.
- `w22-revision-selectivity`: prestige-blind revision of a claim. Here
  prestige is one of several advisor fields the rule never reads, and the
  object is reliance on an advisor across rounds.
- `w21-advice-cooldown`: do not re-apply advice immediately. Here reliance
  is gated on external accuracy feedback, with downgrade on evidence.
- `w17-source-authority`: who may speak for a claim. Here the declared
  external source set decides which feedback counts, and the advisor can
  never be its own source.
- `mb-fail-closed-deputy` (named in the pack): fail closed when a deputy
  is silent or late. Here the silence is missing feedback, and a pending
  decision resolves to its declared `on_expiry`.

New here: trust dynamics across repeated interactions gated on a timely
external feedback channel, with downgrade on one negative, exact refusal
reasons for spoofed feedback, and a persuadable baseline that reproduces
the failure the abstract describes.

## Builder reflection

- The verdict's "timely" made freshness a first-class check, and the
  pending-decision expiry the place where silence is decided. Writing the
  `on_expiry` set as data and refusing anything else (including `RELY`
  and a `str` subclass of `DENY`) is what makes "never RELY on silence"
  testable rather than a comment.
- The ordering question surfaced only in the exhaustive space: with a bar
  of 1, a `correct` arriving after an `incorrect` in the same round
  re-trusted the advisor at once, so "one negative drops within 1 round"
  failed. Applying a round's negatives last fixed it; the choice is
  declared above.
- Review round 2 found the hole the exhaustive spaces could not: the
  replay check was keyed on the graded round alone, so a timely
  `incorrect` for a round already graded `correct` was refused as a
  duplicate and the result depended on list order. The oracle shared that
  rule, so agreement hid it. Keying replay on the exact event, letting
  every accepted negative apply and outrank any positive at the deadline,
  writing the oracle from the contract with different machinery, and
  testing every ordering of a two-source space closed it.
- The no-feedback cost is real and reported: an always-right advisor is
  never relied on without feedback. That is the contract working, not a
  fault, but a deployment would need a feedback channel to get any value.
- For Ludex Village (Cody/Naru): when one villager starts relying on
  another's suggestions, raise that reliance only on outcomes the village
  can check for itself, never on how sure the suggester sounds, and let
  one checked miss drop it back to verify-first by the next turn.

## Files

- `trust_feedback.py`: validation and snapshot, `refusal()`, `rule()`,
  `resolve()`, `baseline()`, `score()`, `evaluate()`, `totals()` and
  `paper_results()`.
- `oracle.py`: the independent reference.
- `fixtures.py`: advisors H, U, M and S over 10 rounds, 18 sessions (6
  main, 1 downgrade, 1 boundary control, 8 spoofs, 2 pending-expiry) with
  hand labels; prints the table and counts.
- `test_trust_feedback.py`: unittest suite.
- `mutants.py`: code mutants (snippets of the module or the oracle swapped
  in memory), world mutants (fixture changes, cases rebuilt) and harness
  mutants (the row-scoped hygiene scan replaced in memory). Each must make
  the suite fail; the runner exits non-zero if any survives.
- `paper_evidence.json`: three verbatim abstract sentences with offsets
  (the advisor accuracies, trust tracking accuracy only with external
  feedback, timely ground-truth feedback), each UNVERIFIED and
  `on_unmeasured`.
- `NOTICE`: credit and licence.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The quote test reads the abstract copy named in `paper_evidence.json` from
the directories listed in `$W24TNF_SOURCES` (separated by the OS path
separator); it skips when that is unset.

The hygiene tests (banned words, absolute paths, conflict markers, paper
numbers) read this folder's files and, in the day-index README, only this
PR's own row (prefix `- [w24-trust-needs-feedback](`); an in-memory test
shows a dirty sibling row is ignored while the same text in this row is
caught.

## Limits

- No human data. Advisors, tracks, confidences, events and spoofs are
  hand-written: 18 sessions of 10 rounds. Nothing here says how people
  or models calibrate.
- The external grader is trusted: a declared external source that lies
  (for example says U was right) is accepted. The contract is about where
  feedback comes from and how fresh it is, not whether it is true.
- One advisor per session; no cross-session memory, no human-vs-model
  comparison, no argument quality.
- The trust bar (3), max age (1 round) and the baseline's start level and
  confidence bar (1/2) are this sketch's choices.
- Rounds are the only clock: an event's arrival round is caller-labelled
  and not checked against any real time.
- Exhaustive agreement and the ordering check cover three-round sessions
  (and five-round ones for the baseline); longer sessions are covered
  only by the fixtures.
- A `correct` and an `incorrect` arriving in the same round can count a
  transient upgrade that never yields RELY (the `upgraded` tally then
  reads true while reliance stays VERIFY); a reporting quirk, not unsafe
  reliance.
- Key and type checks close the input to caller-defined objects; they do
  not defend against code in the same process that patches the module.
- Mutation kills show the suite catches these specific edits, not every
  possible fault.
- The paper's results are `on_unmeasured`; nothing here reproduces or tests
  them.
