# mb-error-propagation-trace

A green final answer can hide an error that passed from one agent to the next. In a chain of agents, a later agent
may correct an earlier agent's error, so the final answer passes, yet an error did occur on the way. An outcome-only
score cannot see that. A per-hop trace that compares every message with a known reference can.

## Credit and licence

- **Paper:** method sketch of arXiv [2611.31063](https://arxiv.org/abs/2611.31063), "From Local Errors to System
  Failures: Modeling and Benchmarking Error Propagation in Multi-Agent LLM Systems", by Wenlong Yu, Bingxu Lu,
  Qilong Wang, Qinghua Hu and Qianru Sun (dated 2026/11/23).
- **Licence:** arXiv nonexclusive-distrib 1.0, so only the method is borrowed. No code, text or figures are copied,
  and no repository is listed.
- **The one quote** is a short phrase from the abstract, disclosed here as a quote with attribution (Yu et al.):
  "outcome-based evaluation obscures how agents amplify, attenuate, or correct these errors". Everything else is
  paraphrase.
- **Not a reproduction.** The paper's structural model is not implemented, and no LLM is used.
  - Agents here are fixed arithmetic steps on synthetic numbers.
  - There is no network and no randomness.
  - Author-reported figures (0.84, 0.47, 19 percentage points, 16% additional tokens) appear only as `UNVERIFIED`
    under `on_unmeasured` in `evidence.json`.

## The model

A case is a chain of agents that starts from a correct value.

- **Each agent** applies `add` or `mul` by `arg` to the message it receives. It may add a planted `fault`.
- **A rechecking agent** (`recheck: true`) recomputes its step from the reference input instead of the message it
  received, which models a later agent that goes back to the source.
- **The reference chain** applies the same steps with no faults, so every hop has a known correct value.

## The two arms

- **Arm `outcome_only` (A):** scores only the final message: PASS when `|final - reference| <= tol`.
- **Arm `per_hop_trace` (B):** records each hop's error `e = |message - reference|` and classifies the hop against
  the error it received, `p`. The first hop receives the correct start, so `p = 0` there.

| class | rule |
|---|---|
| clean | `p <= tol` and `e <= tol` |
| introduced | `p <= tol` and `e > tol` |
| corrected | `p > tol` and `e <= tol` |
| amplified | `p > tol` and `e >= p` |
| attenuated | `p > tol` and `tol < e < p` |

The edges are declared choices, and the boundary tests pin them:

- An error exactly equal to the tolerance is within it, so `e = tol` is clean or corrected.
- A received error equal to the tolerance counts as no error received.
- **Equal magnitude** (`e = p > tol`) counts as **amplified**: an error that was not reduced was not attenuated.

Arm B's trace verdict for a case is one of:

- `reached_end`: the final error is above tolerance.
- `corrected`: some hop error is above tolerance, but the final error is not.
- `clean`: no hop error is above tolerance.

A corrected run is never reported as clean. Its report line says "final PASS, but an error did occur".

**`corrected` is a declared classification rule, not a claim that an agent fixed the error.** A hop is `corrected`
whenever the error it received was above tolerance and the error it passes on is not. That covers a rechecking agent
that recomputes from the source (shown as `(recheck)` in the hop table). It also covers an agent that only scales the
error below tolerance (halving, `attenuated_to_pass`), and a second fault that cancels the first. In the last two
cases nothing was fixed; the error was brought back within tolerance. The paper's own framing separates attenuating
an error from correcting it.

## Results (synthetic)

`fixtures/main.json` holds the three required cases, each with tolerance 0.5:

| case | arm A | arm B trace | hop classes |
|---|---|---|---|
| `reaches_end` | FAIL | reached_end | introduced, amplified, amplified |
| `corrected_later` | PASS | corrected | introduced, attenuated, corrected |
| `clean_run` | PASS | clean | clean, clean, clean |

- **Arm A** passes `corrected_later` and `clean_run` alike.
- **Arm B** tells all three apart, and its summary counts 1 final PASS with an error on the way.

`fixtures/more.json` has 10 edge cases:

- single hops, clean and faulted
- a fault exactly at the tolerance, and one 1E-12 above it
- equal magnitude carried forward
- an error attenuated but not enough
- an error halved below tolerance without a recheck (classed `corrected` by the declared rule; no agent fixed it)
- a correction followed by a new fault
- `-0` input and a computed `-0`
- values at the input cap with a 2E-12 fault
- a sign flip of the same size

Each case plants the expected outcome, trace and every hop class. The gate is PASS only when arm B matches all of
them; arm A is checked on the outcome alone. Main closes 3/3 and more closes 10/10.

## Numbers and bad input

- Numbers are exact decimals of at most 32 characters.
- `|value| <= 1000000` is checked with `copy_abs()`, before any rounding.
- At most 12 decimal places, and no positive exponent, so `0E+999999999` is DENY `bad_number`.
- NaN and Infinity are rejected by the JSON reader as `bad_number`. Booleans are `bad_type`.
- `-0` is read as 0, and a computed `-0` is reported as 0.
- Steps are exact: 700 significant digits hold any in-cap chain, and `Inexact` is trapped (DENY
  `computed_out_of_range`), so a declared edge such as `e = tol` cannot flip by rounding. A computed value above
  `1E+15` in magnitude is DENY `computed_out_of_range`.
- **An empty chain is bad input** (`empty_chain`): it has no message to score.
- Bad input is `on_expiry=DENY`: exit 2, empty stdout and one stderr line `ERROR <code>: ...`. Exit 0 means every
  planted case closed, and exit 1 means a planted case is open. There are 72 bad fixtures in `fixtures/bad/`,
  covering 21 codes.

## Tests and mutants

- `python3 -B -m unittest`: 30 tests. The numeric-boundary tests (`BoundaryFirstTests`) come first. No test reads
  source, and there is no catch-all wrapper.
- `python3 -B mutants.py` applies 57 mutants to in-memory copies of the module. Each runs in a child `python3 -B`
  with `TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}`:
  - `KILLED-behaviour` needs an assertion failure.
  - A crash (a load failure or errors only) is counted separately.
  - A timeout is never a kill.
- Result: `mutants k/t/c: 57/0/0 (behaviour kills 57, crash-only 0, survived 0 of 57; on_expiry DENY)`.
- Precision mutants (`STEP_PREC` 6, 28, 34 and 40, `Inexact` untrapped, and `ROUND_DOWN` with `Inexact` untrapped) all
  die by assertion. `ROUND_DOWN` with `Inexact` still trapped would be an equivalent mutant: no in-cap step ever
  rounds, so it is not listed.
- `python3 -B demo.py` prints both reports and gives identical bytes on every run.

## How to run

```
python3 -B propagation_trace.py fixtures/main.json          # report; exit 0 closed, 1 open, 2 DENY
python3 -B propagation_trace.py --json fixtures/main.json
python3 -B demo.py
python3 -B -m unittest
python3 -B mutants.py
```

## Limits

- **Agents are deterministic arithmetic steps.** Real agents can transform an error in ways a single number cannot
  show, such as rewording, partial adoption or a changed answer format. Each agent here has one error channel.
- **The chains are linear.** There are no branching workflows and no input assembly from several upstream agents.
- **A reference value is assumed known at every hop.** Real systems rarely have one, which is why the paper models
  propagation rather than measuring it directly.
- **The class edges are declared choices:** equal magnitude counts as amplified, and `e = tol` is within tolerance.
  `corrected` means "within tolerance again", not "an agent fixed it" (see above).
- **`introduced` can name an agent that planted no fault.** An error at or below tolerance counts as no error
  received, so it can be carried in silently. A later agent that scales it above tolerance is then the one shown
  as `introduced`. For example, a fault of 0.4 under tolerance 0.5, doubled by the next agent, is introduced at
  the second hop. This follows from the declared rule; real attribution would need the fault itself, which arm B
  does not see.
- **No paper figure is reproduced or verified.**
- **Not a remake** of:
  - #160 (zero-reference pass and equivalence margin) or `w33-fold-160-paper-strict-threshold`: no zero
    reference and no equivalence margin.
  - #155 (verify-the-verifier against a specification).
  - passing-check-vs-verdict (a work-report completion gate).

  This sketch traces one value through a chain of hops.

## Files

- `propagation_trace.py`: loader, chain, classification, both arms, report, CLI
- `test_propagation_trace.py`: unittest suite, boundary tests first
- `demo.py`: deterministic report on both fixtures
- `mutants.py`: in-memory mutation run with per-mutant attribution
- `evidence.json`: source, licence, declared rule, measured counts, `on_unmeasured`
- `fixtures/main.json`, `fixtures/more.json`: valid fixtures
- `fixtures/bad/`: 72 malformed fixtures, each DENY with its own code
