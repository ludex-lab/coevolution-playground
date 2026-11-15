# 01-step-ledger — two-sided step records at the env–trainer wire

A tiny, deterministic, offline toy in which an environment and a trainer talk
only through an explicit in-process wire. Silent faults are injected on that
wire. Each side keeps a step record; comparing the two records step by step,
field by field, detects every injected fault and reports where it first
appeared, while an outcome check on the trainer's logged returns misses most
of them. The pattern: check the run, not the outcome.

This is a clean-room Python stdlib **method sketch** of
[arXiv 2611.08144](https://arxiv.org/abs/2611.08144)
([HTML](https://arxiv.org/html/2611.08144)), *Detecting Silent Faults at the
Environment–Trainer Boundary in Reinforcement Learning* (Gou & Lu, submitted
5 Nov 2026). Paper method only; no upstream code copied.

Playground path: `experiments/2026-11-09/01-step-ledger/`

**Standing note:** this is a method sketch, not a reproduction of the paper's
confirmatory results. It is not Team OS law and not village law.

## How to run

```bash
cd experiments/2026-11-09/01-step-ledger/
python3 -m unittest test_ledger.py -v
python3 fixtures.py
```

Offline, stdlib only, finishes in well under a second of compute. Paper
excerpt checks run only when `/tmp/mb1109-2611.08144.html` is present and are
skipped otherwise.

## Pins and licences

- Paper: https://arxiv.org/abs/2611.08144 (v1), licence CC BY 4.0. Method-cite
  only; short quotes with offsets are in `paper_evidence.json`.
- Upstream illustration (cite-only): https://github.com/PlugRL/step-ledger @
  `0b4a1417854289ecfb25607bc6c51eb0dc586bdd` (commit 2026-11-08 10:47 JST),
  Apache-2.0. The LICENSE file at that commit was re-read. The repository was
  not cloned and none of its code was copied or consulted.

## What the toy does

- **Environment** (`CorridorEnv`): a 1D corridor. Observation is
  `(x, time_left_fraction)` with float `x`; reward is a small distance cost
  plus a goal bonus or fall penalty. An episode ends with `terminated` (goal
  or fall) or `truncated` (time limit).
- **Trainer side**: a scripted epsilon policy whose epsilon shrinks per
  episode, so the logged returns rise like a learning curve. It trains
  nothing and is not PPO or any library algorithm.
- **Wire** (`Wire`): the only place env and trainer meet. Messages carry
  `env_id`, `episode_id`, `step_id`, `action`, `observation`, `reward`,
  `terminated`, `truncated`. Faults are injected here and nowhere else.
- **Faults** (all silent; nothing raises):
  1. float16 rounding of an observation component (and, separately, of a
     reward) via stdlib `struct` format `'e'` (IEEE 754 binary16);
  2. stale reward: one step's reward replaced by the previous step's;
  3. `terminated` ↔ `truncated` swap on an episode-ending step;
  4. skipped step: the action never reaches the env and the trainer gets
     filled-in feedback, so its step stream stays contiguous;
  5. extras: one zeroed action, and every reward zeroed.
- **Step records**: the env records what it applied and gave; the trainer
  records what it sent and what it received after the wire.
- **Compare** (`compare_records`): records keyed by
  `(env_id, episode_id, step_id)`, walked in `(episode, step, env)` order,
  fields compared by exact equality of recorded Python values (no float
  tolerance; a float16 round trip changes the recorded float). The first
  difference is reported as env / episode / step / field with both values; a
  step present on one side only is reported with field `step_id`. A clean
  run reports no difference.
- **Baseline** (`gain_check`): mean logged return over the last three
  episodes minus the first three, compared with a fixed threshold. It
  reports `detect` only when that gain falls below the threshold.
- **Measurements** (`fixtures.py`): detection rate of the compare vs the
  baseline on the designed fault set, whether each first difference matches
  the injection site, and the wall-time ratio of runs that keep and compare
  records vs baseline-only runs (`time.perf_counter`, small repeat count).

In this toy the step-record compare detected and localised every injected
fault; the return threshold missed every single-value fault and caught only
the run where every reward was zeroed. These are synthetic measurements of
this sketch, designed that way on purpose, and say nothing about the paper's
own experiments.

## Not implemented

- No gymnasium, Stable-Baselines3, MuJoCo, numpy, or any RL library.
- No PlugRL code (neither step-ledger nor plugrl-server).
- No daemon, no network, no WebSocket, no msgpack.
- No paid LLM API, no Inspect AI.
- No NATS / docker-compose, no DSH / Feishu / SQLite ports.
- No HMAC or other signing of records.
- No training-scale run; no learning algorithm at all.

## UNVERIFIED

- All of the paper's empirical findings.
- Transfer of this check to real RL stacks, real wires, and vectorised envs.
- Production usefulness and the true cost of keeping records at scale.
- Robustness across seeds, real wires, and nondeterministic environments
  (exact equality assumes both sides record the same values deterministically).

## Builder reflection

I made the wire an explicit object so that "where the fault lives" has one
answer, which is what lets the first-difference report name a single env,
episode, step and field. The baseline reads only the returns the trainer
logged, because that is all an outcome check ever sees: a swapped episode end
or a filled-in step leaves those returns almost untouched. Reporting the
first difference instead of a count kept the compare honest, since one
skipped step shifts everything after it.

Ludex: when Cody hands Naru's grain tallies from the mill to the store, he
and the miller each keep a step-by-step tally and compare them line by line;
a matching season total is not enough to say the carrying was right.

Implementation may be complete; it is not declared verified.
