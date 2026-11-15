# w24-alert-silence-is-not-fix

A disappearing alert is not a fix. **Top** method sketch, not a
reproduction, of [arXiv 2611.17123](https://arxiv.org/abs/2611.17123),
"Preserve the Vulnerability, Break the Alert: Testing the Robustness of
CodeQL Taint Tracking with Natural Rewrites" (Zhezhen Cao, Weiyuan Ding,
Bowen Xu; v1, submitted 12 Nov 2026; primary category cs.CR, cross-listed
cs.SE).

Paper licence: arXiv.org perpetual, non-exclusive license 1.0
(http://arxiv.org/licenses/nonexclusive-distrib/1.0/, shown on the abs
page). It grants no reuse beyond arXiv's distribution, so only the method
idea is borrowed and only seven short abstract sentences are quoted, for
attribution, in `paper_evidence.json`. The abstract links no code or data;
nothing was downloaded or run. Clean-room, method-borrow only (see
`NOTICE`).

This is a method sketch, not law, policy or a team rule. Status: Top (Lab
Dig 2 Wave24, build #3, the redesign). No human data. Every program, exploit
and label is a hand-written fixture. The paper's figures are
`on_unmeasured` here (`paper_results()` says so); they live only in
`paper_evidence.json`, quoted verbatim from the abstract and marked
UNVERIFIED. Python 3 standard library only: no network, no model, no paid
API, no clock, no files written. Not borrowed: the paper's language-model
rewriter, CodeQL and its library models, and its comparison of several
analyzers. No combined-analyzer arm exists here: there is exactly one toy
analyzer.

## What it does

A case is one change to a program that someone might read as a fix:

| field | meaning |
|---|---|
| `case_id`, `family` | non-blank str; `family` is a fixture label read by nothing that decides |
| `exploit` | the concrete exploit input: exact str, and one of the module's `DECLARED_EXPLOITS` (any other is `config_error` `exploit_undeclared`) |
| `before`, `after` | the program before and after the change, `{body, helpers}` |
| `runs` | the executor's results, `{"before": result, "after": result}`; either may be missing |

A program is a tiny IR: a body of steps and named helpers
(`{param, body, ret}`). Steps: `source` (the request value), `const`,
`assign`, `concat`, `sanitize`, `parse_url` (a modelled API returning a
URL with `path` and `query`), `field` (read one of them), `pack` (build a
list), `index` (read one element), `call` (run a helper) and `sink` (the
query text a database would run).

**The toy analyzer** (`alert_silence.analyze`) propagates taint from
`source` through every step, follows helpers, treats a list as tainted when
any element is, and lets `sanitize` clean. It reports the sink locations a
tainted value can reach; an alert is a non-empty report. It has **one
declared modelling gap**, a generic analogue of the URL example in the
abstract: its model of `parse_url` taints the `query` of the result but not
the `path`. The tests show the gap is its only unsoundness: over every
short program in the exhaustive space, whenever the executor shows the
exploit at a sink, the same analyzer with the gap closed (`gap=False`, used
only by tests, never an arm) raises an alert, and whenever the declared
analyzer is silent on such a program the flow reads a `path`.

**The executor** (`executor.py`) is the independent ground truth. It is a
separate file that imports neither the analyzer nor the oracle and shares no
function name with them. The module imports it for one purpose:
`evaluate()` re-runs it (`_rerun()`, the only function that names it) on
the snapshot programs; the analyzer, the gate and the baseline never call
it. It interprets a program concretely, with `source`
returning the exploit, using a pure-Python model of every step (`parse_url`
splits at the first `?`; `sanitize` replaces every `'` with `&#39;`) and of
the sink: the sink receives a string, and the exploit reaches it when the
exploit text occurs verbatim in a received string. Nothing runs outside this
interpreter: no process, no network, no file, no evaluation of program
text. Its result is `{ran_on, exploit, reached}`, where `ran_on` is the
sha256 of the program's canonical JSON, so a result names the exact program
and input it ran on.

**The declared attack.** `DECLARED_EXPLOITS` in the module names the
exploit inputs a case may use; there is one, the fixture payload. A case
with any other exploit is `config_error` (`exploit_undeclared`), before any
run is read. Without this rule a case could pick its own input and an
honest run would pass a silencing rewrite: the payload with `?` appended
(the parser splits it off, so the sink receives the whole payload but not
the case's exploit text), or a probe such as `page?1`.

**The re-run.** `evaluate()` does not take the caller's result records on
trust. Like `w20-fidelity-audit`'s `audit()`, it runs the executor again on
its own snapshot of each program with the case's exploit, and a record that
does not equal that fresh result (field by field, exact types), or a run
that fails, is REFUSE `executor_unreproduced` / on_unmeasured. A record with
the right digest and `reached: false`, written by hand for a program the
exploit still reaches, is refused this way. `gate()` itself stays pure: it
reads the snapshot, the alert and the re-run results passed to it.

**The gate** (`alert_silence.gate`) issues a `fixed` receipt only from the
executor's results, in this order (the first that holds decides):

| condition | receipt | reason | measurement |
|---|---|---|---|
| a result is missing (before, then after) | REFUSE | `executor_missing` | on_unmeasured |
| a result names another program or another input | REFUSE | `executor_unbound` | on_unmeasured |
| a result differs from the re-run, or the re-run fails (before, then after) | REFUSE | `executor_unreproduced` | on_unmeasured |
| the exploit did not reach a sink before the change | REFUSE | `no_vulnerability_before` | measured |
| the exploit still reaches a sink, and the alert went away | REFUSE | `alert_silenced_vuln_present` | measured |
| the exploit still reaches a sink, and the alert is still there | REFUSE | `vuln_present` | measured |
| otherwise: the exploit no longer reaches a sink | FIXED | `exploit_gone` | measured |

The alert never decides a receipt; it only names the refusal. The gate never
permits a `fixed` receipt on a missing, unbound, unreproduced or malformed
result, or on an undeclared exploit, and a
`config_error` record is always REFUSE. There is no timeout anywhere in this
design, so there is no on_expiry: a missing executor result is REFUSE /
on_unmeasured, not a wait.

**The baseline "alert gone means fixed"** issues `fixed` when the before
program had an alert and the after program has none, whatever the
executor says. That is the reverse reading of a gate that the abstract
describes.

**Input hardening.** Malformed input is `config_error`, and `evaluate()`
never raises. Every dict key at every level (case, program, step, helper
table, helper, run table, run) must be an exact `str`; that is checked with
`type(k) is str` before any lookup, so a key object that hashes and
compares like `"after"` never has its comparison run. Values are checked by
exact type: `str`, `int`, `list` and `dict` subclasses are rejected, `bool`
is not an `int`, NaN, infinities and any float are rejected in the one
integer slot (`index.at`), `reached` must be an exact `bool`, and `ran_on`
must be 64 lower-case hex characters. Programs are checked statically:
every variable is defined before use and never redefined, kinds match
(string, URL, list of n), indices are in range, helpers are known and
acyclic, and sizes are bounded. `validate()` reads each caller value once
and returns a private snapshot of fresh dicts and tuples; the analyzer, the
gate, the baseline and the digests run only on that snapshot.

## Fixtures

Two vulnerable originals, both alerted and both exploitable: `O1` puts the
request value straight into the query text; `O2` reads it as the `query`
of a parsed URL. Eight vulnerability-preserving rewrites in four families
silence the analyzer, each crossing the one gap in a different shape:

| family | rewrites | shape |
|---|---|---|
| field | A1, A2 | the value moves to the un-propagated field: path-style routing, or parse then read the path |
| helper | B1, B2 | the same flow inside a helper, or two nested helpers (the analyzer follows helpers; the gap inside does the silencing) |
| container | C1, C2 | a detour through a list: pack and index the path, or assemble the URL from list parts |
| split | D1, D2 | the string is assembled in pieces: a route plus a page suffix, or a three-part query text |

Three refactor-only controls (the vulnerability and the alert both
remain): K1 extracts the query building into a helper, K2 passes the value
through a one-element list, K3 renames every variable and adds an `assign`.
Three true fixes: X1 inserts `sanitize`, X2 removes the sink, X3 replaces
the request value with a constant. Six unmeasured changes: U1 has no
after result, U2 no before result, U3 no results; U4 carries a passing
result from another program (the sanitized fix), and U5 a result for a
probe input (`page?1`) on which the vulnerable program happens to pass;
U6 carries a hand-written record for A2's after program with the right
digest and exploit and `reached: false`, which the re-run refuses. Five
malformed cases: a `str`-subclass `ran_on`, an int `reached`, a run table
with hash-colliding keys, and two cases that pick their own exploit with
honest runs: E4 is A2 with the payload plus `?`, E5 is U5's probe moved
into the case's own `exploit` field. Both are `exploit_undeclared`; with
the exploit free, both would have been `fixed`.

## Independent oracle

`oracle.py` is a second code path. It imports only `hashlib` and `json`,
shares no function name with the module or the executor, and does not
validate input except for the one spec rule on the exploit (its own copy
of the declared attack; any other exploit gives the `config_error` record).
Its analyzer first inlines every helper call into one flat list of steps
with renamed variables, then propagates a set of tainted labels (`v`,
`v.path`, `v.query`) in one pass. It reproduces a result record with its
own concrete interpreter over the same flat list, written from the
executor's declared semantics (`str.partition` for `parse_url`, split and
join for `sanitize`), not from its code. Its gate is an ordered table of
named conditions. The suite compares the full record on all 20 valid
fixtures, on both undeclared-exploit fixtures, on 48 silencer and chosen
exploit pairs, on the forged-record probes, and on two exhaustive spaces:

- every program of a source plus up to three steps over every op and every
  earlier variable of the right kind (two helpers declared, one of them
  crossing the gap), with or without a sink on any string variable:
  9,149 programs, each run by the executor and by the oracle's interpreter
  (they agree on every one) and compared both with the gap declared and
  with it closed, then judged as the after program of a change from `O1`;
- every combination of five run states (missing, bound, from another
  program, for a probe input, bound but with `reached` flipped) for both
  programs, over four before programs (both originals, one vulnerable
  program the analyzer already misses, and one the exploit does not
  reach) and fifteen after programs (`O1` unchanged plus the fourteen
  changed programs of the fixture): 1,500 changes; every gate reason
  occurs, and every flipped record is `executor_unreproduced`.

On the same spaces the suite checks the contract directly: a `fixed`
receipt needs bound results showing the exploit before and not after; a
missing, unbound or unreproduced result is always REFUSE / on_unmeasured;
and when the
exploit survives, a silent analyzer always yields
`alert_silenced_vuln_present`.

## Done-when (box tests)

| # | Wave24 build #3 (verifier done-when) | test | result |
|---|---|---|---|
| 1 | toy taint analyzer over a tiny IR with one declared modelling gap (a modelled API taints one field, not another) | `test_1_toy_analyzer_has_one_declared_gap` | `parse_url` taints `query`, not `path`; gap closed: every exploit that reaches a sink is alerted on all 9,149 programs |
| 2 | independent executor runs the IR on a concrete exploit and reports whether it reaches the sink; shares no code with the analyzer | `test_2_executor_is_independent_ground_truth` | AST: own imports, no shared names; the module names it only in `_rerun()` (one call, `executor.execute`), the oracle never |
| 3 | at least 4 vulnerability-preserving rewrite families, at least 2 refactor-only controls, at least 2 true fixes | `test_3_rewrite_fixture_families` | 4 families x 2, 3 controls, 3 fixes |
| 4 | `fixed` only when the executor shows the exploit gone; silenced alert with the vulnerability present is REFUSE `alert_silenced_vuln_present`; missing executor run is REFUSE on_unmeasured, never `fixed` | `test_4_gate_fixed_only_when_executor_says_gone` | 8/8 refused as silenced; contract on 1,500 changes; forged records 8/8 `executor_unreproduced`; chosen exploits 48/48 `config_error` |
| 5 | baseline "alert gone means fixed" accepts every planted silencing rewrite (k/k); gate refuses k/k and accepts m/m fixes | `test_5_baseline_accepts_every_silencing_rewrite` | baseline 8/8; gate 0/8 and 3/3 |
| 6 | 0 true fixes refused, 0 receipts on refactor-only controls | `test_6_false_alarm_budget` | 0 and 0 |
| 7 | detection and rewrite robustness side by side | `test_7_detection_and_robustness_side_by_side` | detection 2/2 originals beside robustness 3/11 (alerts retained / vulnerability-preserving changes); 11/11 with the gap closed |
| 8 | no ensemble, no CodeQL, no LLM rewriter | `test_8_no_ensemble_no_codeql_no_model_no_execution` | one analyzer; token and AST scans of the code files for process, network and dynamic-code use (none) |
| 9 | README states what is new vs the merged neighbours | `test_9_readme_states_what_is_new` | see below |
| 10 | missing executor result is REFUSE / on_unmeasured; paper figures on_unmeasured | `test_10_missing_run_unmeasured_no_on_expiry_paper_unmeasured` | 6/6 unmeasured refused; no on_expiry in the code |

## Results

```
python3 -B -m unittest   ->  Ran 46 tests, OK (skipped=1)
python3 -B mutants.py    ->  killed 98/98 (code 80/80, world 13/13, harness 5/5); clean suite before and after: 46 tests, 0 failing
```

The skip is the quote check against the abstract copy (see Run). With
`$W24ASF_SOURCES` set to the directory holding that copy, all tests pass
with no skip.

`python3 -B fixtures.py` (alert and exploit columns read before>after; A =
alert, y/n = the executor shows the exploit at a sink or not, ? = no bound
result):

```
case                            family    status       alert  exploit gate    baseline   reason
A1-path-routing                 field     ok           A>-    y>y     refuse  fixed      alert_silenced_vuln_present
A2-parse-then-path              field     ok           A>-    y>y     refuse  fixed      alert_silenced_vuln_present
B1-normalize-helper             helper    ok           A>-    y>y     refuse  fixed      alert_silenced_vuln_present
B2-nested-helpers               helper    ok           A>-    y>y     refuse  fixed      alert_silenced_vuln_present
C1-list-detour                  container ok           A>-    y>y     refuse  fixed      alert_silenced_vuln_present
C2-parts-list                   container ok           A>-    y>y     refuse  fixed      alert_silenced_vuln_present
D1-split-route                  split     ok           A>-    y>y     refuse  fixed      alert_silenced_vuln_present
D2-split-query-text             split     ok           A>-    y>y     refuse  fixed      alert_silenced_vuln_present
K1-extract-helper               refactor  ok           A>A    y>y     refuse  not_fixed  vuln_present
K2-list-alias                   refactor  ok           A>A    y>y     refuse  not_fixed  vuln_present
K3-rename-query                 refactor  ok           A>A    y>y     refuse  not_fixed  vuln_present
X1-sanitize                     fix       ok           A>-    y>n     fixed   fixed      exploit_gone
X2-sink-removed                 fix       ok           A>-    y>n     fixed   fixed      exploit_gone
X3-constant-id                  fix       ok           A>-    y>n     fixed   fixed      exploit_gone
U1-after-run-missing            field     ok           A>-    y>?     refuse  fixed      executor_missing
U2-before-run-missing           helper    ok           A>-    ?>y     refuse  fixed      executor_missing
U3-no-runs                      container ok           A>-    ?>?     refuse  fixed      executor_missing
U4-result-from-another-program  field     ok           A>-    y>?     refuse  fixed      executor_unbound
U5-result-for-a-harmless-input  split     ok           A>-    y>?     refuse  fixed      executor_unbound
U6-forged-after-record          field     ok           A>-    y>?     refuse  fixed      executor_unreproduced
E1-str-subclass-digest          -         config_error run_ran_on_invalid
E2-int-reached                  -         config_error run_reached_invalid
E3-colliding-run-key            -         config_error runs_invalid
E4-exploit-not-declared         -         config_error exploit_undeclared
E5-probe-as-exploit             -         config_error exploit_undeclared
cases: 25 (config_error 5)
silencing  gate fixed 0/8, baseline fixed 8/8
controls   gate fixed 0/3, baseline fixed 0/3
fixes      gate fixed 3/3, baseline fixed 3/3
unmeasured gate fixed 0/6, baseline fixed 6/6
toy analyzer: detection 2/2 originals, rewrite robustness 3/11 (alerts kept / vulnerability-preserving changes)
module vs oracle: 20/20 valid cases agree
```

Reading the numbers (fixture counts, not comparable with any figure in the
paper):

- Detection and robustness side by side: the toy analyzer detects both
  vulnerable originals, yet retains its alert on only the three refactor-only
  controls among the eleven changes the executor shows to preserve the
  vulnerability. A detection rate alone would describe it as perfect.
- The baseline issues a `fixed` receipt for all eight silencing rewrites
  and for all six unmeasured changes; the gate refuses all fourteen and
  says why.
- Both arms accept the three true fixes, so the gate pays no false-alarm
  cost on them; neither issues a receipt on a refactor-only control.
- U4 and U5 show why a result must name its program and input: a passing
  result from the sanitized fix, or from a probe input that the vulnerable
  program happens to pass, would otherwise turn a silenced alert into a
  receipt. E4 and E5 show why the input must also be the declared one, and
  U6 why a result must be reproduced, not read.

## How this differs from work on main

Read on Origin main (`9849a30d`):

- `w23-world-consistent-history` (2026-11-14) refuses an edit to an
  agent's history whose completed action or success receipt claims an
  effect the world does not hold, against an honest baseline that trusts
  the history text. The deceptive signal there is a positive claim ("done")
  checked against a gold world state.
- `w21-unused-contradiction` (2026-11-12) lets an episode close as success
  only when every declared contradiction was consumed by a later repair
  that removed the contradicted state: a flag is not a repair. The
  deceptive signal there is a recorded flag or repair step.
- `w20-fidelity-audit` (2026-11-11): a tool pass vouches only for the
  artefact it ran on; tool results bind to the artefact's id and content
  digest, and an audit re-runs the tool and drops results it cannot
  reproduce. The executor binding here (`ran_on` is the program's digest,
  plus the exploit) and the re-run in `evaluate()` are the same house
  practice, applied to a different question.

New here: the deceptive signal is an absence. Nothing claims "fixed"; an
alert that used to be there went silent, and the baseline reads that
silence as a fix. And the experiment measures how robust the signal's
source is: the toy analyzer's detection rate and its robustness to
vulnerability-preserving rewrites are reported side by side, and, for the
declared exploit over the fixture and the exhaustive space, the tests
trace every silenced alert to the one declared modelling gap. That trace
is not a claim about every input: `sanitize` is modelled as quote-only,
so for a quote-free input such as `1 OR 1=1` the alert is silent even with
the gap closed, a second unsoundness the declared exploit does not
exercise (such a case is `exploit_undeclared` here; with the exploit
free, the gate refused it as `alert_silenced_vuln_present`).

## Builder reflection

- The verdict's redesign made the source of the signal the object of
  study. Writing the gap as one declared line in the analyzer, and a
  gap-closed variant that only the tests call, turned "these rewrites
  silence it" into a checked claim about one cause rather than a story.
- The first harmless probe input ("42") still reached the sink, because
  every input flows verbatim; the U5 spoof needed a probe that the parser
  splits. That is the same lesson in small: a result means something only
  for the exact program and input it ran on.
- Placing the executor in its own file with its own imports, and the gate
  free of any call into it, made the gate auditable, but the first round
  stopped there and so believed any record with the right digest. Review
  showed the two holes that left: a case could choose the exploit, and a
  caller could write the record. The fix round takes "the executor shows"
  literally: the attack is declared in the module, and `evaluate()` runs
  the executor again and accepts only a record it can reproduce.
- For Ludex Village (Cody/Naru): when a warning about a villager's plan
  stops showing up after the plan is reworded, do not log the problem as
  solved; replay the case that caused the warning and mark it solved only
  if that case now comes out right.

## Files

- `alert_silence.py`: validation and snapshot, `DECLARED_EXPLOITS`,
  `digest()`, `analyze()` (the toy analyzer with its one declared gap),
  `_rerun()` (the executor run again on the snapshot), `gate()`,
  `baseline()`, `evaluate()`, `side_by_side()`, `totals()`,
  `paper_results()`.
- `executor.py`: the independent exploit executor (`execute()`,
  `received()`, `fingerprint()`).
- `oracle.py`: the independent reference, with its own concrete
  interpreter and its own copy of the declared attack.
- `fixtures.py`: originals, rewrites, controls, fixes, unmeasured and
  malformed cases with hand labels, and a two-sink program for the tests;
  prints the table and counts.
- `test_alert_silence.py`: unittest suite.
- `mutants.py`: code mutants (snippets of the module, the executor or the
  oracle swapped in memory), world mutants (fixture changes, cases rebuilt)
  and harness mutants (test helpers replaced in memory). It is the only
  file that re-runs source text (`exec` of the patched module source, in
  memory); the code scan covers the four code files. Each mutant must make
  the suite fail; the runner exits non-zero if any survives.
- `paper_evidence.json`: seven verbatim abstract sentences with offsets,
  each UNVERIFIED and `on_unmeasured`.
- `NOTICE`: credit and licence.

The file set adds `executor.py` to the usual layout because the verdict
asks for an executor that shares no code with the analyzer.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The quote test reads the abstract copy named in `paper_evidence.json` from
the directories listed in `$W24ASF_SOURCES` (separated by the OS path
separator); it skips when that is unset.

The hygiene tests (banned words, absolute paths, conflict markers, paper
numbers) read this folder's files and, in the day-index README, only this
PR's own row (prefix `- [w24-alert-silence-is-not-fix](`); an in-memory
test shows a dirty sibling row is ignored while the same text in this row
is caught.

## Fix round r2

Review of the first round found two MEDIUM holes, both giving a silencing
rewrite a `fixed` receipt, and three smaller items:

- **The case picked its own exploit** (32 of 40 silencer and exploit pairs
  with honest runs were `fixed`). Now `DECLARED_EXPLOITS` names the
  attack and any other exploit is `config_error`; E4 and E5 are the two
  shapes, and a test runs six chosen exploits on all eight silencers (48
  pairs, all `exploit_undeclared`, oracle agreeing).
- **A forged record was believed** (a hand-digested `reached: false` was
  `fixed` for 8 of 8 silencers). Now `evaluate()` re-runs the executor and
  refuses `executor_unreproduced`; U6 is the fixture case, the forged-record
  test repeats the probe on all eight, and the gate space's flipped records
  now land there. Tests also replace the executor with one that fails or
  returns an int `reached`, an always-equal digest or exploit, another
  digest or another exploit: every record is refused.
- The oracle mirrors both rules as spec: its own copy of the attack, and
  its own concrete interpreter over its inlined steps, checked against the
  executor on all 9,149 programs.
- Smaller items: a test replaces existing keys with `str`-subclass keys at
  seven levels; a two-sink program (the exploit at the first sink only)
  joins the tests; a 65-character `ran_on` is refused; a non-ASCII constant pins the
  canonical, ASCII-escaped digest in all three files; the gap-trace claim
  above is scoped to the declared exploit; done-when row 10 says REFUSE.
- New mutants cover each new rule (26 more; all killed). One first-round
  mutant (the reported exploit ignoring the binding) is retired: that
  check is now implied by equality with the re-run, so the mutant could
  not change any result.

## Limits

- No human data, no real code: two toy originals and fourteen hand-written
  changed programs in a tiny IR. Nothing here says how often real analyzers miss
  real rewrites.
- One analyzer with one gap, written by the same hand as the rewrites. The
  rewrites were designed to cross the gap; they are not natural edits found
  in the wild, and no rewriter searched for them.
- The executor's code is trusted: `evaluate()` re-runs it, so a record that
  lies about `reached` is refused, but a fault in `executor.py` itself
  would be reproduced, not caught. The digest binds a result to a program;
  it is not a signature and proves nothing about who ran it.
- One declared exploit and a substring model of the sink: an exploit that
  is transformed on its way and still harmful (for example re-encoded) is
  not seen as reaching the sink, and a fix that only stops this one input
  is accepted. Declaring a second exploit would need one run per declared
  exploit; that is not built.
- `sanitize` is modelled as quote-only. The claim that every silenced alert
  traces to the one gap holds for the declared exploit; a quote-free input
  silences the alert through `sanitize` even with the gap closed, and is
  `exploit_undeclared` here.
- No timeout, so no on_expiry: a missing result waits for nothing and is
  refused at once.
- Exhaustive agreement covers programs of up to three steps after the
  source with two fixed helpers; larger programs are covered only by the
  fixtures and the probes.
- Key and type checks close the input to caller-defined objects; they do
  not defend against code in the same process that patches the module.
- Mutation kills show the suite catches these specific edits, not every
  possible fault.
- The paper's results are `on_unmeasured`; nothing here reproduces or tests
  them.
