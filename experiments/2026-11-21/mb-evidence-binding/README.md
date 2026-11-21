# mb-evidence-binding

A quote that contains the number can still be the wrong scale or the wrong period. This experiment builds a frozen
synthetic filing, plants three answers per question, and runs two binding tests over them:

- the **loose test** (`loose_binding`) passes when the reported number string appears, as a whole number, in a cited
  quote on the cited page;
- the **strict test** (`strict_binding`) also requires that the quote is the asked line, that the number is the cell
  for the asked period, and that the quote's table unit, named by its scale note, is the asked unit.

## Credit and licence

Method idea: *Show Your Work: Can Small Open Models Read SEC Filings with Evidence a Machine Can Check?*, arXiv
2611.24990 (submitted 18 Nov 2026, Krishna Nandula as listed on the abstract page). The title is the live
`citation_title` of the abstract page. Only the abstract page was read here.
Licence line: paper CC BY 4.0; method only; upstream code Apache-2.0, not cloned or run; no code copied.
The upstream repository (`pramana-research/filing-evidence`) was not cloned, run or copied, and this experiment does
not run its benchmark. Everything here is a stdlib paraphrase of the evidence contract.

## The fixture (fixture-authored)

`fixtures/main.json` is a hand-written synthetic filing. The company, every number and every planted answer were
written for this experiment:

- 6 tables on 6 pages, 2 periods (`fy2025`, `fy2024`), 6 lines;
- the same lines appear in a table in thousands of US dollars and in a selected-data table in millions; diluted
  shares appear in thousands of shares (an earnings-per-share note) and as a raw share count;
- 12 quotes, one per table row, each showing both periods' cells of that row;
- 6 questions, each asking for one line, one period and one unit (millions, thousands or a number of shares);
- 18 answers, three per question: `correct` (bound evidence), `scale_error` (a number from the other-unit table that
  still appears in its cited quote) and `wrong_period` (the right line, the other period's cell).

The loader refuses a filing whose tables disagree once scaled (`inconsistent_filing`), a quote that does not show its
row's cells (`bad_quote`), a scale note that does not name its unit (`bad_scale_note`), and a question without
exactly one answer of each planted kind (`bad_plant`). The planted label is never read by either test; a test and a
mutant check that.

## The two tests

Numbers are display strings (`5,432.1`, `(12.3)`, `152,300,000`) parsed to exact `fractions.Fraction` values; there
are no floats anywhere. "Appears as a whole number" means the string is found in the quote with no digit, and no
comma or point followed or preceded by a digit, on either side, so `432` does not appear in `5,432,100`.

Loose test, per citation: the cited page is the quote's page (`not_on_cited_page`), and the number string appears in
the quote (`number_not_in_quote`). It passes if any citation passes.

Strict test, per citation, after the two loose steps:

1. the quote is the asked line (`wrong_line`);
2. the number equals a cell of that row (`number_not_a_cell`);
3. that cell is the asked period's cell (`wrong_period`);
4. the table unit and the asked unit are the same kind, money or shares (`unit_kind_mismatch`);
5. reported value times the asked unit's scale equals the cell value times the table unit's scale, exactly
   (`scale_mismatch`).

It passes if any citation passes all steps. If none does, it reports the reason of the citation that got furthest.

## Result on the main fixture

| | loose test | strict test |
|---|---|---|
| answers passing | 18 of 18 | 6 of 18 |
| wrong values passing | 12/12 | 0/12 |
| right values passing | 6/6 | 6/6 |

- (a) The loose test passes all three planted cases for every question.
- (b) The strict test accepts only the correct case. It rejects the scale error with `scale_mismatch` and the
  wrong-period case with `wrong_period` for all six questions.
- (c) No paid API and no network: `evidence.json` records both as false, and a test scans the source.

These counts come from the plants above. They show how the two tests separate the planted cases; they are not an
error rate for any model and are not comparable with the paper's figures.

## Why this is not a remake

- Not the passing-check-vs-verdict topic: nothing here decides whether work is complete or within scope. The question
  is narrower. Does a cited quote bind the reported number to the asked line, period and unit? This is evidence
  binding, not a completion or scope verdict.
- Not `mb-answerability-pairs` (#151): there is no command, no machine state and no permit or refuse decision. Every
  answer here cites evidence that is present in the input; the planted errors are in how the number is bound to it.

## Paper claims (UNVERIFIED)

The benchmark size, the models and setups, the accuracy range and best result, the per-1,000 count of check-passing
wrong answers, the split of those into scale or unit errors and other-period takes, and the effects of reasoning
and retry are paper numbers. They are UNVERIFIED and sit only under `on_unmeasured` in `evidence.json`. None of them
was measured here.

## Contract

- `python3 -B evidence_binding.py fixtures/main.json` prints one JSON report and exits 0.
- Malformed input: exit 2, empty stdout, exactly one stderr line `ERROR <code>: <detail>`, no traceback.
- Every cap declares its `on_expiry` and all of them are `DENY` (the input is refused): file size 200000 bytes,
  and counts of units, periods, lines, tables, columns per table, quotes, questions, answers and citations per answer.
  The only timeout is the mutation harness's limit of 300 seconds per suite run (`mutants.TIMEOUT`, on_expiry
  `DENY`: a run that reaches it is not counted as passing).

## Probe battery

The standing battery is stored under `fixtures/bad_*.json` (132 files); each exits 2 with empty stdout and one stderr
line. Covered: duplicate JSON keys (flat and nested); NaN, Infinity and an exponent overflow; floats, booleans and
strings where integers are required (pages, scales, versions); huge ints (309 and 5000 digits, and page numbers past
the range); deep nesting (arrays and objects, below and above the size cap); lone surrogates in ids and text,
including an escaped reversed pair; control, C1, ESC, NUL, tab, newline, zero-width, bidi, BOM, NBSP, U+3000,
U+2028, U+3164, U+2800, U+115F, U+034F, private-use and unassigned characters in ids and free text; NFC and NFD
duplicate ids; the size cap; invalid UTF-8, a BOM prefix and UTF-16; empty input, trailing comma, trailing garbage,
single quotes and a top-level array; malformed display numbers (bad grouping, exponent, full-width digits, too long);
broken references; and the filing-integrity refusals listed above. Korean free text is accepted: `fixtures/korean.json`
and `fixtures/korean_nfd.json` (NFD Hangul) carry Korean labels, scale notes, quotes and a Hangul question id, and give
the same verdicts as the main fixture.

## Files

| File | What it holds |
|---|---|
| `evidence_binding.py` | loader, the loose and strict tests, scoring, command line |
| `test_evidence_binding.py` | unittest suite (`python3 -B -m unittest`) |
| `demo.py` | prints every question, its three planted answers and both verdicts, computed by the code |
| `mutants.py` | breaks the module one way at a time and requires the suite to fail every time |
| `evidence.json` | measured counts on the fixture; paper claims under `on_unmeasured`, all UNVERIFIED |
| `fixtures/` | `main.json`, `korean.json`, `korean_nfd.json`, `multi_citation.json` and 132 `bad_*.json` |

`demo.py` output is byte-identical across runs; its sha256 is
`22ed05a45db07545c838519cdc5174f6ba0be23f6b26881c91b213af4b19c955`

## Limits

One small synthetic filing, two periods, money and share units only, one quote per table row. Real filings have
footnotes, restated columns, mixed scales inside one table and quotes that span lines; none of that is modelled. The
strict test trusts the fixture's table metadata (which row, which column, which unit), so it shows what binding
requires, not how to recover that metadata from a PDF page.

## How a Ludex village would use it

A village that answers number questions from a shared document (Naru's ferry timetable, a Batang budget sheet) could
run the strict test before posting an answer, so a figure quoted from the wrong year's column or the wrong unit is
held back with its reason code instead of passing because the digits appear on the page. This is a use sketch only;
no village page was opened.
