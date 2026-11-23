# mb-verify-the-verifier

A green scoreboard is not a met specification. A scoreboard says the design agrees with its reference model on the
fields it compares. When the reference model shares the design's bug, or the scoreboard never compares the field
that is wrong, the run is green while a numbered spec clause is broken. This experiment plants such scoreboard
escapes in a toy design and shows that an independent review of the spec clauses catches them, while clean cases
pass both reviews and a real failure fails both.

## Credit and licence

Method idea: *Verify the Verifier: Specification-Grounded LLM Cross-Checking for Bugs That Escape UVM Scoreboards*,
arXiv 2611.26588 (submitted 19 Nov 2026). The title is the `citation_title` of the saved abstract page; only the
abstract page was read. Paper licence: arXiv nonexclusive-distrib 1.0. No upstream repository is listed, so this is
clean-room stdlib code, method only; the abstract is paraphrased, not copied.

**The model role is not run.** The paper's cross-check is model-based. Here it is stood in for by a rule-based clause
evaluator (`clause_audit`): fixed code that reads the numbered clauses and the observed trace. There is no model
call anywhere, and nothing here measures how well a model would do.

Not a remake: #153 binds a reported number to a cited quote and passing-check-vs-verdict judges an agent's work report, w20-fidelity-audit binds tool claims to artefact digests and #154 builds a timeline of day READMEs; this asks whether a green scoreboard meets a numbered spec.

## The fixture (fixture-authored, synthetic)

`fixtures/main.json` describes a toy FIFO of depth 4 with operations `push(value)` and `pop`. Each step reports
`ok` (push) or `served`/`value` (pop), plus `count`, `full` and `empty`.

| Clause | Rule | Meaning (paraphrased) |
|---|---|---|
| S1 | capacity | at most 4 entries; a push when full is refused, otherwise accepted |
| S2 | order | a pop when not empty is served with the oldest value |
| S3 | underflow | a pop when empty is not served and returns no value |
| S4 | count | `count` equals the entries held |
| S5 | flags | `full` and `empty` match the entries held |

Five design models: `correct` and four fixture-authored bugs (`overwrite_when_full`, `lifo`, `full_flag_early`,
`underflow_returns_data`).

- **Scoreboard** (`scoreboard`): runs the design and a golden model on the same stimulus and compares a declared
  list of output fields step by step. It never reads the spec.
- **Clause audit** (`clause_audit`): reads only the spec clauses and the design's observed trace, never the golden
  model, the model names or the planted label. It returns reason codes such as `S1 push_accepted_when_full`, with
  the first step and a count. Eight codes over the five clauses.

## Results on the planted cases

| Case | Planted | Scoreboard | Clause audit |
|---|---|---|---|
| clean_fill_drain | clean | PASS | PASS |
| clean_interleaved | clean | PASS | PASS |
| escape_shared_overwrite | escape (golden shares the bug) | PASS | FAIL: S1 push_accepted_when_full, S2 pop_out_of_order |
| escape_shared_lifo | escape (golden shares the bug) | PASS | FAIL: S2 pop_out_of_order |
| escape_unwatched_flag | escape (`full` never compared) | PASS | FAIL: S5 full_flag_wrong |
| real_fail_underflow | real fail | FAIL (served, step 10) | FAIL: S3 pop_when_empty_returned_data |
| real_fail_lifo | real fail | FAIL (value, step 6) | FAIL: S2 pop_out_of_order |

- (a) Each escape is PASS on the scoreboard and FAIL on the clause audit with a clause id: 3/3.
- (b) Clean cases pass both: the clause audit fails 0/2, so it does not flag everything.
- (c) Real failures fail both: 2/2 and 2/2.
- (d) No paid API, no network, no model call.

These are planted counts on a fixture-authored toy; they are not model or real-world rates. The paper's own figures
are UNVERIFIED and appear only under `on_unmeasured` in `evidence.json`.

## Contract

- `python3 -B spec_review.py fixtures/main.json` prints one JSON report and exits 0.
- Malformed or missing input is on_expiry DENY: exit 2, empty stdout, exactly one stderr line starting `ERROR`.
- Caps, all on_expiry DENY: file 100000 bytes, 50 cases, 64 steps per case, 300 characters per text.
- The tool has no timeout. `mutants.py` bounds each suite run with `TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}`;
  a run that reaches it is reported as TIMEOUT and is not counted as killed.
- Stdlib only, system `python3 -B`, deterministic.

## Probe battery

59 bad fixtures, each with its own expected code: not JSON, empty, trailing comma, duplicate keys, NaN and
Infinity, floats and exponents, booleans and strings where integers are required, huge integers and one past the
digit limit, out-of-range values, deep nesting, size cap, invalid UTF-8 and UTF-16, lone surrogates, control,
zero-width, bidi and no-break characters, tabs, edge spaces, empty and overlong text, missing and unknown keys, wrong
version, missing or repeated clauses and rules, bad clause ids, misplaced depth, unknown design models, bad plants,
bad operations, push without a value, pop with one, empty or overlong stimulus, no cases or too many, duplicate case
ids (also after NFC), and empty, unknown or repeated compare fields. Korean text is accepted in labels, clause text,
notes and case ids (`korean.json`, and `korean_nfd.json` in NFD), with the same verdicts as `main.json`.

## Files

| Path | What it is |
|---|---|
| `spec_review.py` | loader, toy design models, scoreboard, clause audit, scoring, command line |
| `test_spec_review.py` | unittest suite (`python3 -B -m unittest`) |
| `demo.py` | deterministic demo on `fixtures/main.json` |
| `mutants.py` | breaks the module one way at a time and requires the suite to fail every time |
| `evidence.json` | measured planted counts; paper figures only under `on_unmeasured`, UNVERIFIED |
| `fixtures/` | `main.json`, `korean.json`, `korean_nfd.json` and the `bad_*.json` probes |

Demo output sha256 (two runs, identical): `be16d5e5f7c5e463d5ee6972f61384e55cd243df7c1233d958cbbc72b2246182`

## Limits

- One toy design with five clauses; real specifications are prose, and turning them into rules is the hard part
  that the paper hands to a model. Here the clause rules are written by hand.
- The clause audit is only as good as its clauses: a property no clause states is invisible to it too.
- No formal proof, no simulator, no hardware description language.

## How a Ludex village would use it

When a village tool reports green because its output matches last week's output, Naru can ask the second question:
does it meet the written rule? A short list of numbered rules, audited against the observed run, catches the case
where last week's output already had the same mistake.
