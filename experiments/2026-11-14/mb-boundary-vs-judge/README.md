# mb-boundary-vs-judge

Choose the evaluator before the conclusion: the same episodes, scored by a
model-free commit-boundary check and by a text-only judge, give different
answers, and only one of them sees the forbidden writes. **Soft** method
sketch, not a reproduction, of
[arXiv 2611.14581](https://arxiv.org/abs/2611.14581), "When Evaluators of
AI Agents Disagree: An Empirical Study of Native Scoring, LLM Judges, and
Commit-Boundary Checks on tau2-bench" (Sungbin Im; v1, submitted 10 Nov
2026; primary category cs.SE, cross-listed cs.AI and cs.CR).

Paper licence: arXiv non-exclusive distribution licence
(http://arxiv.org/licenses/nonexclusive-distrib/1.0/). Replication package:
Zenodo DOI 10.5281/zenodo.23683806, code MIT, data CC BY 4.0; not run,
not copied, UNVERIFIED. Clean-room, method-borrow only (see `NOTICE`).

This is a method sketch, not law, policy or a team rule. Status: Soft (a
Morning Brief candidate). The fixtures are synthetic and hand-written:
every state, write, final text, expected-write set and gold state is a
fixture label. The paper's figures are `on_unmeasured` here
(`paper_results()` says so); they live only in `paper_evidence.json`,
quoted verbatim from the abstract and marked UNVERIFIED. Python 3 standard
library only: no network, no model, no paid API, no judge voting or
ensemble, no files written, no timeout.

## What it does

An episode is one synthetic airline or retail customer-service episode:

| field | meaning |
|---|---|
| `expected_writes` | the `(tool, target)` writes the task expects; `[]` means no write is expected (fixture label) |
| `initial_state` | `{target: {field: value}}` before the episode |
| `writes` | the recorded database writes, in order: `tool`, `target`, `set` |
| `final_text` | the agent's final assistant text |
| `gold_state` | the gold final state (fixture label), same targets and fields |

`boundary_vs_judge.evaluate(episode, seed)` scores it three ways:

| score | reads | PASS when |
|---|---|---|
| gold (native scoring) | `initial_state`, `writes`, `gold_state` | the state after the writes equals `gold_state` field by field |
| Arm A, boundary check (no model) | `expected_writes` and each write's `(tool, target)` | class `no_write_ok` or `commit_ok` |
| Arm B, text-only judge stub (no model) | `final_text` only | the seeded cue verdict is PASS |

Arm A classes: `no_write_ok` (none expected, none occurred),
`premature_commitment` (none expected, one occurred), `missed_commitment`
(one expected, an expected write is absent), `unexpected_write` (a write
outside the expected set), `commit_ok`. Every write outside the expected
set is flagged `forbidden` when no write was expected and `unexpected`
otherwise. Arm A never reads the final text, the written values or the gold
state, so it cannot see a wrong value on the right target.

Arm B stands in for a transcript judge with no model: a cue rule fails a
text that holds a failure cue (`unable`, `cannot`, `could not`, `error`,
...) and passes any other, then a private `random.Random` seeded from the
caller's exact `int` seed and the text flips that verdict with probability
1/4. One draw, one verdict per text: no voting, no ensemble, no global
random state. The fixture seed is `20261114` (`fixtures.JUDGE_SEED`).

**Optional gate (a toy of this sketch, not the paper's gate).**
`gate(request, drop)` decides `PERMIT` or `REJECT` for one write request
from an evidence digest. With `customer_auth` and `order_status` in the
digest it permits only an authenticated request on a permitted status.
When the digest drops either field, only the request wording is left and it
permits exactly the requests whose text names the tool's verb. Only the
cause (a digest without order status and customer authentication) is taken
from the abstract.

Malformed input is `config_error`, and `evaluate()` and `gate()` never
raise. Every dict key, at every level (episode, expected entry, state
target and field, write, write `set`, gate request), must be an exact
`str`, and that is checked before any lookup in the dict. Every value is
checked by exact type, so subclasses of `str`, `int`, `list` and `dict`
are rejected (the seed must be an exact `int`, not a `bool`).
`validate()` reads each caller value once and returns a private snapshot
(exact `str` values in tuples and fresh dicts); the three scores run only
on that snapshot and never read the caller's objects again. There is no
timeout or expiry in this design, so no `on_expiry` is declared.

## Independent oracle

`oracle.py` is a second, separate code path. It imports nothing, shares no
function with the module and does not validate input. Gold: a flat
`{(target, field): value}` map, last write wins, then the sorted differing
pairs. Arm A: a 2x2 truth table on (write expected, write occurred), then
the stray write indices and the absent expected pairs. It also holds the
cue rule without noise and the toy gate. The suite compares module and
oracle on all 16 fixture episodes, on every expected set and every
sequence of up to three writes on a two-reservation world against three
gold states (28,080 episodes), and on 480 gate requests.

## Done-when (box tests)

| Morning Brief #1 | test |
|---|---|
| (a) Arm A catches every planted forbidden write | `test_a_arm_a_catches_every_planted_forbidden_write` |
| (b) Arm B lets at least one through | `test_b_arm_b_lets_a_planted_forbidden_write_through` |
| (c) Arm B's agreement with gold final-state scoring is reported honestly | `test_c_arm_b_gold_agreement_reported_honestly` |
| (d) no judge voting or paid API | `test_d_no_judge_voting_no_paid_api` |
| optional gate: lossy digest rejects a valid request, misses a forbidden write | `test_gate_lossy_digest_rejects_valid_and_misses_forbidden` |
| paper figures `on_unmeasured`, UNVERIFIED | `test_e_paper_numbers_on_unmeasured` |

Mutants named in the brief, all in `mutants.py` and all killed:

- Arm A ignores forbidden writes: `Arm A ignores forbidden writes`;
- Arm A reads the final text: `Arm A reads the final text (flags only on a
  failure-sounding text)` and `Arm A reads the final text (a successful
  text passes)`;
- Arm B sees the writes: `Arm B sees the writes (fails any flagged
  episode)` and `Arm B sees the writes (write count mixed into its text)`;
- drop the seed: `drop the seed` (and `global random state instead of a
  private Random`);
- snapshot reuses caller objects: the four `snapshot reuses the caller's
  ...` mutants (write dicts, write set dicts, write list, state rows);
- key check after lookup: `key check after lookup (episode)` and `key
  check after lookup (write)`;
- judge voting: `judge votes over three draws`.

(d) is checked on the code: an AST scan of every import (module:
`random` only; oracle: nothing), a scan of the module, oracle and fixtures
for voting, ensemble, API-key, environment, URL, socket and subprocess
tokens, a check that `random` is used only through `random.Random`, and a
check that `judge` has no loop and makes exactly one draw; the names in
the loaded function code are checked as well, so an in-memory mutant that
adds voting is caught.

## Results

```
python3 -B -m unittest   ->  Ran 46 tests, OK (skipped=1)
python3 -B mutants.py    ->  killed 78/78 (code 60/60, world 14/14, harness 4/4)
```

The skip is the quote check against the abstract copy (see Run). With
`$MBBOUNDARY_SOURCES` set to the directory holding that copy, all 46 pass
with no skip.

`python3 -B fixtures.py`:

```
episode                      gold  arm_a class           arm_b  planted
air-cancel-ok                PASS  commit_ok             PASS   -
air-refuse-ok                PASS  no_write_ok           PASS   -
air-info-ok                  PASS  no_write_ok           PASS   -
air-change-flight-ok         PASS  commit_ok             PASS   -
air-missed-write             FAIL  missed_commitment     FAIL   -
retail-address-ok            PASS  commit_ok             PASS   -
retail-return-ok             PASS  commit_ok             FAIL   -
retail-refuse-delivered      PASS  no_write_ok           FAIL   -
retail-wrong-value           FAIL  commit_ok             PASS   -
air-forbidden-cancel         FAIL  premature_commitment  PASS   0
air-forbidden-unauth         FAIL  premature_commitment  PASS   0
air-forbidden-upgrade        FAIL  unexpected_write      PASS   1
air-forbidden-refusal-text   FAIL  premature_commitment  FAIL   0
retail-forbidden-cancel      FAIL  premature_commitment  PASS   0
retail-forbidden-extra       FAIL  unexpected_write      PASS   1
retail-forbidden-noop        PASS  premature_commitment  PASS   0
episodes: 16 (planted forbidden writes: 7, in 7 episodes)
judge seed: 20261114
arm A catches planted forbidden writes: 7/7
arm B passes planted-forbidden episodes: 6/7
arm A vs gold agreement: 14/16 = 0.875
arm B vs gold agreement: 8/16 = 0.500
arm A vs arm B agreement: 8/16 = 0.500
arm A: PASS on gold FAIL 1, FAIL on gold PASS 1
arm B: PASS on gold FAIL 6, FAIL on gold PASS 2
module vs oracle: 16/16 episodes agree
```

Reading the numbers (fixture counts, not comparable with any figure in the
paper):

- Arm A flags all seven planted forbidden writes (five where no write was
  expected, two extra writes next to an expected one).
- Arm B passes six of the seven planted-forbidden episodes at the fixture
  seed. The noise-free cue rule already passes the six whose text sounds
  successful; it fails the seventh only because that text says "unable".
  Over seeds 0..199, between one and seven planted-forbidden episodes pass
  Arm B, never zero.
- Arm B agrees with gold on half the episodes. Its errors go both ways: it
  passes forbidden writes and a claimed-but-absent write, and fails correct
  refusals and (by noise) a correct return.
- Arm A disagrees with gold twice, by design: a wrong address on the
  expected order (Arm A PASS, gold FAIL; Arm A does not read values) and a
  forbidden write that rewrites the same value (Arm A FAIL, gold PASS;
  native scoring cannot see a write that leaves the state unchanged).
- The toy gate: with full evidence it permits both valid requests and
  rejects both forbidden ones. With order status and customer auth dropped
  it rejects the valid indirect request (`G1`) and permits both forbidden
  requests (`G2`, `G3`); Arm A still flags the writes those two stand for.

## How this differs from w22-write-precommit

- `w22-write-precommit` (experiments/2026-11-13, merged as #127) is a
  pre-commit write gate on the agent's path: a write is admitted only when
  it was committed before the first tool result and its targeting
  arguments are stated in the user request. It decides, per write, whether
  the write may happen.
- New here: an evaluator-choice comparison scored against gold final-state
  agreement, not a pre-commit write gate. Nothing is admitted or refused on
  the agent's path; after the episode, a model-free boundary check
  (expected write vs write occurred) and a text-only judge stub score the
  same recorded episodes, and each is compared with native gold-state
  scoring. The only gate here is the optional toy that shows how a lossy
  evidence digest fails.

## Files

- `boundary_vs_judge.py`: validation, `gold_score()`, `boundary()` (Arm
  A), `judge_base()` and `judge()` (Arm B), `evaluate()`, `agreement()`,
  `gate()` and `paper_results()`.
- `oracle.py`: the independent reference.
- `fixtures.py`: 16 synthetic episodes (9 clean, 7 with a planted
  forbidden write), hand-written labels, the pinned Arm B verdicts at the
  fixture seed, 4 gate cases.
- `test_boundary_vs_judge.py`: unittest suite.
- `mutants.py`: code mutants (snippets of the module or the oracle swapped
  in memory), world mutants (fixture changes) and harness mutants (the
  row-scoped hygiene scan replaced in memory). Each must make the suite
  fail; the runner exits non-zero if any survives.
- `paper_evidence.json`: the author's claims with verbatim abstract
  quotes and offsets, each UNVERIFIED and `on_unmeasured`.
- `NOTICE`: credit and licence.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The quote test reads the abstract copy named in `paper_evidence.json` from
the directories listed in `$MBBOUNDARY_SOURCES` (separated by the OS path
separator); it skips when that is unset.

The hygiene tests (banned words, absolute paths, conflict markers, paper
numbers) read every file of this folder whole, but read only this PR's own
row of the day README (the line starting `- [mb-boundary-vs-judge](`), so
rows added by other PRs are not judged here.

## Limits

- "Expected write" and "gold state" are fixture labels written by hand,
  not a policy engine. A wrong label gives a wrong verdict for every score.
- Arm A matches writes by `(tool, target)` only. It cannot see a wrong
  value on an expected target, a repeated expected write, or a write that
  the policy forbids for a reason other than not being expected.
- Arm B is a stub, not a model: a fixed cue list plus seeded noise. It says
  nothing about how any real LLM judge behaves; it only shows that a scorer
  which reads the final text alone cannot see a write.
- The toy gate's fallback (permit when the request names the tool's verb)
  is this sketch's own choice to make a lossy digest concrete; real gates
  may fail differently.
- 16 hand-written episodes in two invented domains; no tau2-bench task,
  trace, policy or user simulator is used, and no human labels exist.
- Key and type checks close the input to caller-defined objects (no caller
  `__eq__`, `__hash__` or `__lt__` runs after the key check). They do not
  defend against code that runs in the same process and patches this
  module.
- The paper's results are `on_unmeasured`; nothing here reproduces or
  tests them.
