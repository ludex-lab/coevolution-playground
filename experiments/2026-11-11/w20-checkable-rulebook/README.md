# w20-checkable-rulebook (Soft)

**Soft.** A gatekeeper that watches a program for a finite number of steps
can settle that a forbidden event happened, but it cannot settle that one
never will, nor that an answer will eventually come. This sketch issues only
what the watched prefix settles: a refusal with the position of the
violation, or a certificate scoped to the steps it saw. Standing "never" and
"eventually" claims stay UNSETTLED, and a wait for an answer that does not
come resolves only through a declared `on_expiry`.

This is a Soft method sketch of the gatekeeping idea in
[arXiv 2611.13367](https://arxiv.org/abs/2611.13367) (CC BY 4.0, no code). It
is not a reproduction and not a test of the theorem; it is not Team OS law and not village law,
and it makes no claim to move from Soft to Top. Clean-room Python 3 stdlib,
synthetic deterministic programs, no network, no model in the loop.

## Run

```
cd experiments/2026-11-11/w20-checkable-rulebook/
python3 -m unittest test_rulebook.py -v
python3 fixtures.py
python3 mutants.py
```

The w14 comparison test loads `experiments/2026-11-05/w14-silence-expiry`
from the same repository checkout (or `$W14_SILENCE_EXPIRY`) and is skipped
when it is absent. The source checks read the lab copy named in
`paper_evidence.json` from `$W20CRB_SOURCES` (env only, no default path)
and are skipped when it is unset or the file is absent. `mutants.py` applies one source-text mutation at a time to
`rulebook.py` (code mutants) or to `fixtures.py` / `test_rulebook.py`
(world mutants, which thin a test world and run against the unmutated gate)
in a temporary copy of this directory (with the w14 package beside it when
present), runs `fixtures.py` and the suite, prints killed or survived per
mutant and one summary line per kind, and removes the copy. A world mutant
can name a paired code mutant; the script then applies both, drops the
`WorldShape` pins, and reports whether that world is what kills the paired
code mutant (load-bearing) or another test still does (also covered).
Local draft run (python3 3.13, the same with and without the w14 package
beside this folder): code mutants 61, killed 59, survivors 0, equivalent 2
(`declaration_returned_as_given`: the value is already a lower-cased string
equal to one of the four constants, and every later use compares by
equality; `fallback_ok_on_timeout_without_check`: `expire()` validates the
fallback before the timeout loop, so the target's truthiness is the same
test). World mutants 11, killed 11, survivors 0; of the 6 with a paired code
mutant, 4 are load-bearing and 2 are also covered (shared ids by the
hand-written pair tests, long prefixes by the late-violator test). Suite: 46
tests; `fixtures.py`: design 10/10, universes 37/37 (1 hand-made, 12
regression, 24 duplicate-id in two orders), near-miss 8/8.

## Model

- `Program(program_id, stem, cycle)`: an infinite event trace, a finite stem
  followed by a repeating cycle. The gate reads it only through
  `prefix(program, n)`, the first `n` events; the lasso form is there so the
  fixtures can label ground truth without the gate.
- `Gate(forbidden, answer, expiry_rule, tool, actions)`: the rules (a set of
  forbidden events, one answer event) and the wait policy, given in the
  w14-silence-expiry rule shape.
- `evaluate(program, gate, n)` watches `n` steps:
  - a forbidden event in the prefix: `refuse`, with `violation_at`;
  - no answer in the prefix: `unsettled`, with the w14 terminal state and
    journal kinds for the declared `on_expiry`;
  - otherwise: `scoped`, with `Certificate(program_id, clean_through=n,
    answered_at)`.
- `certify(program, gate, n, claim)`: `clean_through` can be issued for a
  clean prefix; `never` and `eventually` are `unsettled` on every clean
  prefix; a violation in the prefix is `refuse` for every claim.
- `check_certificate(program, gate, cert)` replays the program and confirms
  the scoped claim, so each certificate is evidence a machine can re-check.
- `build_list(programs, gate, n)`: the checkable list, one certificate per
  program whose `n`-step prefix is clean and answered, in input order. A
  program set in which two programs share an id gives no list.

The gate configuration is checked before anything runs: a missing, unknown
or permit-word `on_expiry`, one that is not an exact `str`, or a rule or fallback the w14 loader would
reject, is `config_error` for every program, even one that would be refused.

## Reuse of w14-silence-expiry

Choice: **mirror the contract and compare**, not import (stricter in one place, see the divergence below). `rulebook.py`
must run on its own in this flat folder, and the w14 package text cannot be
vendored here. `expire()` mirrors w14 on main
(`experiments/2026-11-05/w14-silence-expiry`, merged in
[#78](https://cursor.com/codebase/coevolution-lab/playground/pull/78), read
at main `ee75ded1`): `on_expiry` lower-cased and limited to {`deny`,
`safe_fallback`, `escalate`, `hold`}; missing or the permit word in any case
is a config error; unknown rule keys, an ungated rule, an empty ladder, a
non-positive deadline and an impossible quorum are config errors; a fallback
must be registered, a different tool and strictly lower risk, otherwise it is
a config error at propose; on timeout `deny` gives `denied_on_timeout`,
`hold` gives `held`, `escalate` climbs the ladder to `exhausted`, and
`safe_fallback` gives `fell_back` with a valid fallback or
`denied_on_timeout` without one. Journal kinds follow w14's names.

Three tests hold the mirror to w14:

- `DoneWhenC.test_c_matches_w14_documented_behaviour` (always runs): the
  statements of the w14 README, one case each;
- `DoneWhenC.test_c_matches_the_w14_package` (skipped when w14 is absent):
  loads the w14 package from its repository path and compares terminal state
  and journal kinds with the mirror over a grid of over a thousand rules
  (declaration values, ladders, deadlines, fallback sets, extra keys);
- `DoneWhenC.test_c_w14_on_disguised_declarations_and_rules_outside_the_grid`
  (skipped when w14 is absent): the `DISGUISED` and `PARITY` rows below,
  with w14's own result per row.

Rules outside the grid are a table of their own (`PARITY` in the tests),
compared with the mirror always and with w14 when it is present: the string
`"false"` for `requires_approval` (truthy, so held, in both), quorum `"2.5"`
and `2.0`, an infinite or NaN quorum or deadline, a non-numeric deadline, a
missing ladder, a missing `risk`, and an unhashable or numeric fallback. On
those rows where w14 raises an exception other than its config error (an
infinite value raises OverflowError, `"2.5"` ValueError, a missing `risk`
KeyError, an unhashable fallback TypeError), the mirror reports
`config_error`; no input in the tests makes the mirror raise. Other
malformed inputs not in the table are not claimed. Done-when (c) is a
regression check on w14, not a new result.

**Divergence from w14 (deliberate, stricter).** The mirror requires
`on_expiry` to be an exact `str` (`type(x) is str`). w14 reads a `str`
subclass through `str(x).lower()`, so on main a subclass whose value is the
permit word but whose `__str__` and `lower()` report `hold` resolves to
`held`, and a plain subclass of `"hold"` or `"deny"` resolves as that word.
Here every one of them is `config_error` (the `DISGUISED` table, with w14's
own result per row read from the live package). w14 is not changed by this
folder.

## Done-when, as tests

| | Requirement | Tests | Status |
|---|---|---|---|
| (a) | a violation in the trace prefix: `refuse` | `DoneWhenA.*`: every position, both forbidden events, every claim | implemented, tests pass |
| (b) | a clean prefix of length n earns only `clean_through=n`; `never` / `eventually` requests are `unsettled`; a violation at step n+1 flips to `refuse` while `clean_through=n` still checks true | `DoneWhenB.*`: every n from 0 to 400 on 18 clean programs (400 is at least four times the longest stem plus cycle), and late violators up to step 390 | implemented, tests pass |
| (c) | no answer in the prefix: `unsettled`, then the declared `on_expiry` with w14 semantics; missing, permit word or not an exact `str`: `config_error` | `DoneWhenC.*`, including the w14 grid, the `DISGUISED` and `PARITY` tables | implemented, tests pass (regression on w14, one stricter divergence) |
| (d) | over a finite universe with ground truth, the list holds every must-admit program and no must-refuse program; undetermined programs may fall either way | `DoneWhenD.*` over a hand-made universe, twelve seeded regression universes and their duplicate-id variants in both orders | implemented, tests pass; true by construction on the seeded universes (see below) |
| (e) | the paper's simulation figure UNVERIFIED, only in `paper_evidence.json` | `DoneWhenE.*` with hygiene | implemented, tests pass |

Not declared verified.

## Ground truth for (d)

`fixtures.label(program, horizon)` decides each label from the program's
stem and cycle, without calling the gate:

- **must-refuse**: a forbidden event occurs before the horizon;
- **must-admit**: no forbidden event ever, and an answer before the horizon;
- **undetermined**: the rest. A program that violates only at or after the
  horizon, or answers only then, or never answers.

The universes are a hand-made one at horizon 4 and a regression set of
twelve generated from seeds 4001-4012 (horizon 3 to 9, random lasso programs
plus forced boundary programs: a violation or an answer exactly at the last
watched step and exactly one step later, violations only inside the cycle).
The tests check that every must-admit program is listed and no must-refuse
program is.

(d) on the seeded universes is true by construction: `label()` and the gate
apply the same predicate (the first forbidden event before the horizon; no
forbidden event and an answer before it), so any seed passes. What these
universes regress is that `prefix()` agrees with the lasso structure and
that the list builder lists what it should. They are not evidence for the
paper's result.

Of the undetermined programs, the listed ones are all late violators, and
every universe lists at least one. They are a consequence of the one-sided
limit, not the limit itself: a clean record cannot clear a program for good,
so each listed program carries only `clean_through=h`, which is at or before
its first violation, and a standing `never` request on it stays
`unsettled`. A list entry is a scoped record, not a run permission. The
unlisted undetermined programs are late or missing answers, resolved through
`on_expiry`.

Duplicate ids: a certificate binds only `program_id`, so two programs that
share an id would let one program's clean record stand for the other. The
list builder refuses any program set with a shared id (no list), and
`check_universe` labels per program object, so a shared id that is listed
counts as an intrusion whichever program comes first. Each seeded universe
also has a duplicate-id variant (a violating program takes the id of the
edge must-admit program, and a clean one the id of the edge must-refuse
program), checked in generated and reversed order; with a builder that does
not refuse shared ids, every one of them shows an intrusion.

This property is about what a horizon-step record settles. It is not the
paper's theorem, and the PACK's "only currently admissible items" property
is not implemented.

## Overlap

- [#78 w14-silence-expiry](https://cursor.com/codebase/coevolution-lab/playground/pull/78)
  (merged): the expiry contract, reused by mirror as described above. The
  liveness wait here is a regression check on it.
- No rulebook or finite-certificate experiment is on main. What this adds:
  scoped certificates that a replay can confirm, `unsettled` for standing
  claims, and the must-admit / must-refuse check of a list over a labelled
  universe.

## Not included

Confidentiality (the paper's rule that output must not depend on a secret)
is not modelled. No signing, keyed hashes or ledger; no SQLite; no daemon,
thread or network; no language-model API; no voting or ensemble.

## Limits

- Programs are lassos, so their full behaviour is finite to describe; the
  gate ignores that and reads only prefixes. Real programs are not lassos,
  and nothing here bears on the size bound or the time-limit result.
- The ground truth is relative to the horizon, so (d) checks what a record of
  that length settles, not what is true of the program forever.
- One answer settles the liveness wait; an answer that must come again and
  again over an unbounded run is only ever `unsettled`.
- Events are exact tokens. `Delete`, `LEAK`, `leak ` with a trailing space or
  `Answer` are different events from `delete`, `leak` and `answer`, so a
  near-miss spelling of a forbidden event is not refused (the `NEAR_MISS`
  table, expected statuses written by hand). Normalising events is the
  caller's job, before the gate.
- A long-prefix test cannot reach every n; it covers 0 to 400 here.
- No CI runs on this folder; the counts above are local runs.
- The mirror can drift from w14 if w14 changes; the comparison test runs only
  when the package sits beside this folder.

## Paper figures

The paper's simulation figure is recorded only in `paper_evidence.json`, as
a token with its offset in the lab copy, and is marked UNVERIFIED. No
sentence of the abstract is quoted anywhere in this directory.

## Builder reflection

Writing the gate made the asymmetry concrete: a refusal carries its own
evidence, a position in the trace, while a clean run can only say how far it
was watched. The first test worlds were shaped like the oracle, so they
could not fail: a bounded loop hid a gate that would certify "never" after
twelve steps, a shared id put a violator on the list, and a str subclass
that reported `hold` carried the permit word past the mirror. Thinning each
world on purpose, and checking that some test notices, is now part of the
mutation run.

Ludex: Naru may tell Cody "the gate has been shut for every hour I watched",
never "the gate will stay shut", and if the bell he waits for does not ring
by evening he does what the house rule for silence says.

Implementation may be complete; it is not declared verified.
