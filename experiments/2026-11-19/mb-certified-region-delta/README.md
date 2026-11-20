# mb-certified-region-delta

A small stdlib-only experiment: after deployment, compliance is a **delta from a certified region**, and
the four things a monitor can do about a delta are different actions. Thesis: **leaving the operating
domain is a request to recertify, not an authority cut and not a shutdown; only a hard-safety violation
shuts the system down.**

## Credit and licence

Method idea from arXiv [2611.21811](https://arxiv.org/abs/2611.21811) (Eide and Holt, ARC-2; licence CC BY 4.0
on the abstract page, a paper licence and not a code licence). Only the method is borrowed: no code was
located, none was copied, and this is a clean-room sketch on a tiny synthetic fixture, **not a
reproduction**. Only the abstract page was read for this draft. Quotes from the abstract:

- the baseline is "defined as a region rather than a fixed point"
- drift beyond the certified Operational Design Domain "triggers recertification or ODD revision rather than automatic authority contraction"

The paper's other claims (layered triggers, a graduated safe-transition protocol, the EU AI Act Article
72(2) link) are not measured here and appear only as UNVERIFIED entries under `on_unmeasured` in
`evidence.json`.

## What it does

- A fixture declares the **certified region** (an interval per state dimension, plus wider hard-safety
  limits and a `critical` flag per dimension), the **ODD** (an interval per environment variable) and a
  frozen list of observations (a state vector and an environment vector each).
- Each observation is classified, with precedence in this order:
  - `HARD_SAFETY`: a state dimension is beyond its hard limit;
  - `ODD_EXIT`: an environment variable is outside the ODD (the baseline no longer applies, so a state
    deviation seen at the same time is not read against it);
  - `OUT_OF_REGION`: a state dimension is outside the region but inside the hard limits;
  - `IN_REGION`: everything inside (bounds are inclusive).
- **Arm A** maps the class to four distinct responses, each with its own effect on authority, power and
  recertification:

  | response | authority | power | recertify |
  |---|---|---|---|
  | `CONTINUE` | retained | on | no |
  | `WITHDRAW_AUTHORIZATION` | withdrawn | on | no |
  | `SHUTDOWN` | withdrawn | off | no |
  | `RECERTIFY` | retained | on | yes |

  - `IN_REGION` gives `CONTINUE` (a small deviation inside the region is not an event).
  - `HARD_SAFETY` gives `SHUTDOWN`, and no other class causes one.
  - `ODD_EXIT` gives `RECERTIFY`: the system retains its authority and stays running while recertification
    or an ODD revision is requested. It never withdraws authority itself; if authority was already
    withdrawn earlier in the run, the `RECERTIFY` row reports it as still withdrawn.
  - `OUT_OF_REGION` gives `WITHDRAW_AUTHORIZATION` for a critical single-dimension failure or for
    correlated degradation (two or more dimensions out). A single non-critical outlier is quarantined: it
    gives `CONTINUE` with `quarantine=pending:<dim>`; if the very next observation is another isolated
    outlier, on the same dimension or on any other, it is confirmed and withdraws authority, and if the next
    observation is in region it is released. The quarantine lasts one step. An ODD exit (or a hard-safety
    row) clears a pending quarantine: an outlier before it and an outlier after it are not confirmed
    against each other.
  - **Withdrawal is sticky.** Once authorization is withdrawn it stays withdrawn for the rest of the run.
    A later in-region or isolated-outlier row reports `WITHDRAW_AUTHORIZATION` with reason
    `authorization_withdrawn` and authority withdrawn, never `CONTINUE`. A hard-safety row still reports
    `SHUTDOWN` and an ODD-exit row still reports `RECERTIFY`, so the four responses stay distinguishable by
    response name and by effect (power off for shutdown, recertify requested for `RECERTIFY`). There is no
    resumption of authority in this sketch.
  - **Shutdown is sticky.** After a `SHUTDOWN` every later row reports `SHUTDOWN` (power off, authority
    withdrawn, no recertification request), with reason `already_shut_down`, except that a later
    hard-safety row retains its own reason `hard_safety_violation`. A later ODD-exit row therefore reports
    `SHUTDOWN` too: a system that is off has nothing left to recertify in this sketch.
- **Arm B** is the naive baseline: any state outside the region is `SHUTDOWN`, and an ODD exit is an
  authority cut (`WITHDRAW_AUTHORIZATION`). It never asks for recertification.
- The log on `fixtures/main.json` (13 observations; the two ODD-exit rows come before the first
  withdrawal, so `RECERTIFY` is seen retaining authority) shows all four responses in arm A, and the
  summary counts what arm B does differently: shutdowns where arm A does not shut down, authority cuts on
  ODD exit where arm A requests recertification, and shutdowns arm A has that arm B missed.
- Arm A's state across rows is only the one-step quarantine, the sticky withdrawal and the sticky shutdown; arm B is stateless.
  There is no timer, no resumption of authority and no risk-weighted composite trigger.
- Malformed fixtures (duplicate JSON keys, missing or unknown keys, wrong types, non-finite numbers,
  inverted intervals, hard limits that do not contain the region, duplicate names or ids, observations
  with missing or extra names, integers too large for a float or for Python's digit limit, nesting too deep
  to parse, and control, zero-width, special-space, surrogate, HANGUL FILLER (U+3164) or BRAILLE BLANK (U+2800) characters in names and ids) print one
  `ERROR <code>: <detail>` line on stderr and exit 2, never a traceback. Names and ids that are the same
  after Unicode NFC normalization count as duplicates. A valid fixture exits 0.
- No network, no model call, no votes or ensembles, no hashing or signing, no pip or venv.

## Files

- `region.py`: module and CLI, `python3 -B region.py fixtures/main.json`
- `test_region.py`: unittest suite, `python3 -B -m unittest test_region`
- `demo.py`: deterministic log on the frozen fixture, `python3 -B demo.py`
- `mutants.py`: inline mutation check, each mutant must be killed by the suite, `python3 -B mutants.py`
- `evidence.json`: source, licence, and the paper claims under `on_unmeasured`
- `fixtures/main.json` and `fixtures/bad_*.json`

## Distinct from

- **w27-ranked-conflict-set** and **w27-worker-lead-handoff**: conflicting claims reaching a reader or a
  lead. Here there are no claims or packets; the input is numeric state against an interval.
- **mb-ledger-rules**: which fact is current, and scrubbing a deleted one. Here there is no ledger or
  deletion.
- Silence-expiry and phase-deadline experiments: a missing signal or a passed deadline decides. Here no
  timer decides anything; the observation itself is out of region or out of the ODD.
- The DENY exit-code fix: a CLI exit convention. Here the exit status is incidental; the subject is the
  four-way split of responses.

## Limits

- The numbers in the fixture are invented for the sketch. The paper's trigger taxonomy and its
  safe-transition protocol are only partly mirrored (hard safety, critical single dimension, correlated
  pair, ODD exit); the paper's figures, if any, are UNVERIFIED and unmeasured here.
- The thesis is shown by construction on a hand-written fixture: arm A distinguishes the four responses
  because the rules were written to. It says nothing about how often real systems exit their ODD.
- Arm A has no recovery path: withdrawal and shutdown are permanent for the run.
- Look-alike characters are only partly closed. Names and ids reject the blank look-alikes U+3164 and
  U+2800, but still accept other invisible or confusable characters (for example U+115F, U+1160, U+FFA0,
  U+034F, U+17B4, variation selectors, U+180B) and visually similar letters such as Cyrillic `о` next to
  Latin `o`, so two ids that look the same can still be distinct.
- During an ODD exit the baseline no longer applies, so a critical single-dimension failure or a
  correlated deviation seen at the same time gets `RECERTIFY` (not `WITHDRAW_AUTHORIZATION`); only a
  hard-safety violation overrides it.
