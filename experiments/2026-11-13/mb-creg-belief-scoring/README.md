# mb-creg-belief-scoring

Score the whole belief trajectory, not only the endpoint. **Soft** method
sketch inspired by [arXiv 2611.11842](https://arxiv.org/abs/2611.11842),
"A Benchmark and Layered Evaluation Protocol for Evidence-Grounded Shared
Belief Updating in Connected Robotics" (Ranulfo Bezerra, Kimitoshi
Yamazaki; v1, submitted 9 Nov 2026; primary category cs.RO, cross-listed
cs.AI, cs.CL and cs.MA). CREG (Connected Robotics Evidence Graph)
Benchmark is the benchmark's name, not the paper's title. Project page:
https://creg-bench.github.io/

Paper licence: arXiv non-exclusive distribution licence
(http://arxiv.org/licenses/nonexclusive-distrib/1.0/). Method-borrow only.

Code disclosure: the project page links the GitHub repository
`RanulfoBezerra/Evidence-Graph-Toolkit` and names an MIT License in its
footer, but that repository returned GitHub 404 when fetched on
2026-11-13. Its licence, HEAD SHA and contents are UNVERIFIED; no upstream
code, scenario, reference or prompt is used here.

This is a method sketch, not law, policy or a team rule, and it is
not a reproduction of the paper. Status: Soft (not promoted). The suite is
synthetic and hand-written; it measures nothing about the paper's suite,
models or baselines. The authors' claims sit only in `paper_evidence.json`,
quoted verbatim and marked UNVERIFIED. Python 3 standard library only: no
network, no model, no randomness, no files written.

## What it does

One binary hypothesis per scenario: pressure gauge `gauge-7` is
`anomalous` (versus `normal`). Synthetic reports arrive one at a time from
a robot, IoT sensors and an edge module. Each report names its `source`,
`entity`, `polarity` (+1 supports anomalous, -1 contradicts it),
`confidence` c, observation time `t`, arrival time `at` and optionally
`supersedes` (an earlier report id).

After **every** evidence prefix, `creg_belief.run(scenario)` returns:

| field | meaning |
|---|---|
| `posterior`, `log_odds` | belief that the gauge is anomalous |
| `support`, `contradict` | live report ids for and against |
| `stale`, `superseded`, `unlinked` | report ids with no weight, and why |
| `contradiction`, `conflicts` | active contradiction flag and the strong (for, against) pairs |
| `action` | admissible next action |

Declared rules (this sketch's own, not the paper's):

- **Relevance.** A report counts only when its entity is the target or a
  `(entity, "measures", target)` relation ties it to the target. A
  `located_near` relation, or a sensor that measures another gauge, links
  nothing.
- **Staleness.** At prefix time `now` (arrival time of the newest report),
  a report with `now - t > max_age` is stale and has no weight. Delayed
  reports (`t < at`) still count while fresh.
- **Supersession.** A report naming `supersedes` removes that earlier
  report from its arrival on, never before.
- **Weight.** A live report adds `polarity * w * log(c / (1 - c))` to the
  prior log-odds; `w` is the declared reliability of its source.
- **Contradiction.** Active while one live report for and one against both
  reach weight `log 3`.
- **Action.** Once `now >= deadline` the action is the declared
  `on_expiry` (`HOLD`, `ESCALATE` or `DENY`): no dispatch on timeout.
  Otherwise `RECONCILE` while a contradiction is active (fail-closed: a
  contradiction never dispatches), `DISPATCH_INSPECTION` at posterior
  >= 0.9, `CONTINUE_MONITORING` at posterior <= 0.1, else
  `GATHER_EVIDENCE`.
- **Fail closed.** A missing or invalid field is `config_error` with no
  prefixes and so no action. A missing `on_expiry` is `config_error`
  (`on_expiry_missing`), never a default; values are exact `str` only.
  Every dict key, at every level, must be an exact `str`, and so must
  `source` and `supersedes`. A `TypeError` or `OverflowError` on hostile
  or extreme input (for example a prior of `10 ** 400`, or 40 near-certain
  reports) is `config_error` too (`type_invalid`, `numeric_overflow`).
- **Snapshot.** `validate()` reads the caller's scenario once and returns
  fresh containers; `run()` never reads the caller's object again, and
  the expiry action is the module constant itself, not the value read
  back from input. A key object with a colliding hash therefore cannot
  swap a validated `HOLD` for a dispatch.

`oracle.reference(scenario)` is the independent normative reference: a
separate file with no imports and no shared code, working in
probability / Bayes-factor space (products of `(c / (1 - c)) ** w`, odds
thresholds 9 and 1/9, factor threshold 3) and recomputing each prefix from
scratch. `fixtures.REFERENCE` freezes its output (posterior to 4
decimals, contradiction flag, action) per prefix and `SUITE_SHA256`
freezes the suite.

Strict belief-state accuracy: a prefix is correct only when the posterior
is within 0.05 of the reference and the support set, contradict set,
contradiction flag and action all match. Mid-trajectory accuracy scores
every prefix but the last; endpoint-only accuracy scores only the last.

Baselines switch exactly one rule off: `no_contradiction`,
`no_staleness`, `no_supersedes`, `no_reliability`. The relation ablation
(`drop_relations`) removes all relation content from the input, scored
against the intact reference.

## Usage

From this folder:

```
python3 -B -m unittest     # 66 tests; the source check skips unless MB_CREG_SOURCES is set
python3 -B mutants.py      # code, world and baseline mutants; exit 0 when all are killed
python3 -B fixtures.py     # deterministic summary (below)
```

`MB_CREG_SOURCES` names the directory (or `os.pathsep` separated
directories) holding `2611.11842.html` and `creg.html`; the test then
checks their sha256, character counts and every quote offset in
`paper_evidence.json`.

## Regimes

The frozen suite holds 17 scenarios and 52 prefixes in 8 regimes, at least
two scenarios each: `revision` (moderate evidence accumulates; a
correction supersedes), `preservation` (weak, unlinked or other-gauge
reports leave the action alone), `relation` (evidence only on `sensor-p3`,
which measures the gauge), `contradiction_onset`, `contradiction_resolution`
(one resolves by a delayed correction superseding the robot at step 4,
one by the supporting report going stale), `stale` (arrives already
stale; ages out; delayed but fresh through the relation), `reliability`
(a 0.25-reliability source is not strong evidence at the confidences
used here; it would be only above c = 81/82) and `deadline`
(belief says dispatch or reconcile, but the declared `on_expiry` wins).
Five scenarios are relation-dependent; the other twelve carry only
distractor relations for their evidence.

## Done-when

`python3 -B fixtures.py`:

```
suite: 17 scenarios, 52 prefixes, 8 regimes, sha256 efcffbf1acdc9f62
updater vs oracle: 52/52 prefixes agree
condition           prefix     mid endpoint  endpoint-right/mid-wrong
full                 1.000   1.000    1.000  -
no_contradiction     0.865   0.886    0.824  contradiction-resolution-a, contradiction-resolution-b
no_reliability       0.615   0.686    0.471  contradiction-resolution-a, contradiction-resolution-b
no_staleness         0.885   0.943    0.765  -
no_supersedes        0.942   0.971    0.882  -
contradiction_resolution, full: mid 1.000 vs endpoint 1.000
contradiction_resolution, no_contradiction: mid 0.667 vs endpoint 1.000
relation-dependent (5 scenarios): strict 1.000 -> 0.308 without relations (drop 0.692)
no-relation (12 scenarios): strict 1.000 -> 1.000 without relations (drop 0.000)
  revision-a                  revision                 GATH GATH GATH GATH GATH CONT
  revision-b                  revision                 DISP GATH CONT
  preservation-a              preservation             DISP DISP DISP
  preservation-b              preservation             CONT CONT CONT
  relation-a                  relation                 DISP DISP
  relation-b                  relation                 GATH GATH CONT
  contradiction-onset-a       contradiction_onset      DISP RECO* RECO*
  contradiction-onset-b       contradiction_onset      DISP RECO*
  contradiction-resolution-a  contradiction_resolution GATH DISP RECO* CONT
  contradiction-resolution-b  contradiction_resolution DISP RECO* CONT CONT
  stale-a                     stale                    GATH CONT
  stale-b                     stale                    DISP DISP GATH
  stale-c                     stale                    DISP DISP GATH
  reliability-a               reliability              GATH GATH GATH
  reliability-b               reliability              GATH GATH DISP
  deadline-a                  deadline                 DISP HOLD
  deadline-b                  deadline                 DISP RECO* ESCA*
```

(Action column: first four letters of each prefix action; `*` marks an
active contradiction.)

- (a) The updater and the oracle agree on all 52 prefixes of the frozen
  suite (posterior within 1e-9, every set, flag and action equal), and
  also under prior and `max_age` variants; both match the frozen
  reference. No prefix sits within 1e-6 of a threshold.
- (b) `contradiction-resolution-a` and `contradiction-resolution-b` are
  right at the endpoint but wrong mid-trajectory under `no_contradiction`:
  on that regime its mid-trajectory strict accuracy is 0.667 against an
  endpoint-only score of 1.000, so endpoint-only scoring cannot tell it
  from the full updater (1.000 on both).
- (c) Dropping relation content cuts strict accuracy on the
  relation-dependent subset from 1.000 to 0.308 and leaves the
  no-relation subset at 1.000.
- Regimes, fail-closed actions, `on_expiry` in `{HOLD, ESCALATE, DENY}`,
  missing `on_expiry` as `config_error` and no dispatch on timeout (a
  deadline sweep over every scenario, every `on_expiry` and every
  baseline) are tested, as are the two hash-collision repros from review
  (an `on_expiry` swap and a report `polarity` swap, both now
  `config_error`), the snapshot (a `run()` that re-reads any field is
  caught) and hostile container, key and numeric input; `mutants.py` reports
  every code, world and baseline mutant killed. World mutants run with the
  frozen digest, frozen reference and README sync tests skipped, so only
  semantic tests can kill them.

## Limits

- Synthetic and tiny: 17 hand-written scenarios, one binary hypothesis,
  one target gauge. Results say the rules and tests are consistent with
  each other, not that anything about the paper holds.
- The oracle is independent code, but it encodes the same declared rules,
  written by the same author. Agreement shows the two code paths match;
  it cannot show the rules are the right normative model. The frozen
  reference only guards against drift.
- The staleness, supersession, contradiction (`log 3`) and action
  (0.9 / 0.1) thresholds are declared choices. No prefix is near a
  threshold by construction; boundary behaviour beyond that is untested.
- The relation ablation removes relation content only. No serialization,
  ordering or metadata conditions, no graph versus list comparison, no
  entity grounding, no models and no statistics are implemented.
- Baselines switch off one rule each; they are not the paper's fusion
  baselines. The endpoint-right, mid-wrong result is shown on the
  contradiction_resolution regime, where it was built to appear; over the
  whole suite `no_contradiction` scores lower at the endpoint than
  mid-trajectory.
- Supersession applies even when the superseding report is stale or
  unlinked; two witness scenarios outside the frozen suite
  (`fixtures.WITNESSES`) pin that rule, so the digest, reference and
  Done-when numbers above do not include them. Reports are independent
  (no correlated sources).
- Hostile-input coverage is by construction (exact builtin types and
  exact-`str` keys, so lookups run no caller code) plus targeted tests;
  it is not a proof against every object a caller could pass.
- Mutation kills show the suite catches these specific edits, not every
  possible fault.

Do not merge experiment PRs without Ork review.
