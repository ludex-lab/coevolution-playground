# w25-daily-issue-index

A small file-in/file-out list check of Naru Daily issues. It reads an authored fixture of the
issues as they are listed (number, date, whether an EN and a KO body exist) and, optionally, the
Daily issues each annals close says reached readers, and reports facts about numbers and dates.
Python 3 standard library only. No network, no child processes, no clock, no randomness.

This is **not a signed, hash-chained or append-only ledger; it does not verify editor signatures.**
There is no hashing or signing anywhere in the module. It also does not decide
whether an issue should have been published: the village's own Daily duty (annals Day 100,
"It now notices when an earlier day's issue was prepared at the desk but never went out.")
does that, and this check does not re-implement it. It reports facts only.

## Input

One or more fixture files, each a TSV with the header

```
list	kind	id	no	date	en	ko
```

- `kind=index`: an issue listing such as the public `daily.html`, one row per issue in listing
  order. `id` is the N of the `issue-N` anchor, `no` and `date` are the printed `No. N · date`,
  `en` and `ko` are `yes` or `no`.
- `kind=close`: the Daily issues one day's close names as having reached readers, in the order
  named. `no` is required, `date` only when the close gives one; `id`, `en` and `ko` are empty.
- `list` names the list (for example `daily`, `annals-day-98`). One list has one kind and lives
  in one file.

**Comments and blank lines.** A line starting with `#` is a comment **only before the header**.
After the header every non-blank line is a row with exactly seven fields, including one that
starts with `#` (a list named `#daily` is checked, not skipped; a `# note` line after the header
has the wrong field count and gives DENY). Comment and blank lines are counted in the report
(`comment_lines=`, `blank_lines=`); nothing is dropped silently. A UTF-8 BOM and CRLF line ends
are accepted.

**Folding before parsing.** Every field is put in NFC form; then default-ignorable characters
(category Cf such as the zero-width space, joiner, soft hyphen and BOM, plus the other
Default_Ignorable ranges: combining grapheme joiner, Hangul fillers, variation selectors, tags)
are removed, decimal digits of any script become ASCII digits, and every other character is
NFKC-normalised. Parsing runs on the folded value. A field that folding changes is FAIL
`unicode_field`, quoting the original (`８２`, `٨٢`, `8\u200d2`, `⁸²`). A number must then be
plain digits `1..999999` without sign, padding, spaces or decoration (`#82`, `No. 82`, `82화`,
`(82)`, `082`, `8 2` are FAIL `unparsed_number`); a date must be a real calendar date
`YYYY-MM-DD` (else FAIL `unparsed_date`).

## Findings

| code | severity | when |
|---|---|---|
| `id_mismatch` | FAIL | an index row's anchor id differs from its printed number |
| `missing_number` | FAIL | a number missing between the lowest and highest number of an index list, or between the declared `--first` and `--last` when given (at most 20 shown, then the total) |
| `out_of_range` | FAIL | an index number below the declared `--first` or above the declared `--last` |
| `duplicate_listing` | FAIL | one number listed more than once **in one index list** (a listing row pasted twice) |
| `language_missing` | FAIL | an index row without its EN or KO body |
| `unicode_field` | FAIL | a field that folding changes (invisible, compatibility or non-ASCII digit characters) |
| `unparsed_number`, `unparsed_date` | FAIL | a number or date that cannot be parsed after folding |
| `not_in_index` | FAIL | a close names a number that no index list has |
| `date_mismatch` | FAIL | a close gives a date that differs from the index date of that number |
| `published_late` | INFO | a number dated before the next lower number (No. 82 · 2026-11-13 above No. 81 · 2026-11-14) |
| `date_gap` | INFO | dates inside an index list's range with no issue (2026-11-10) |
| `reissued` | INFO | one number named in more than one close (Daily 80 in the Day 97 and Day 98 closes) |
| `counted_twice` | INFO | one number named more than once **in one close** (Daily 78 in the Day 94 close, Daily 74 in the Day 91 close: same-day reissues) |
| `shared_date` | INFO | two numbers with the same date |
| `listing_order` | INFO | an index list not ordered by number, highest first |
| `index_absent` | INFO | close lists without any index list, so `not_in_index` and `date_mismatch` did not run |
| `list_name_form` | INFO | a list name outside ASCII letters, digits and single hyphens (`#daily`, a Cyrillic `а` in `dаily`), reported once per list |

Decisions: `PASS` (no FAIL; INFO never fails) exit 0, `FAIL` exit 1, `DENY` exit 2.
`on_expiry` is always `DENY`.

**Reissue versus duplicate.** The review verdict (sha256 `628be325…`), section 3 T2 (MEDIUM-1),
separates "a reissue of the same number (Daily 80 style → INFO, not duplicate-fail)" from "a
true duplicate listing of one number in one list". The PR review of the first round (sha256
`11d9b3cb…`, M1 and I4) found that both live repeats inside one close are explained by the annals
as same-day reissues: Day 94 says Daily 78 "was reissued at Folio's evening request" and its close
adds "It was reissued in the evening."; Day 91 says "Daily 74 and Daily 72 went out again from
their signed manuscripts" (full quotes, UNVERIFIED, in `evidence.json`). This check therefore
reports:

- the same number in two different closes: `reissued` (INFO);
- the same number more than once in one close: `counted_twice` (INFO, a fact);
- the same number more than once in one **index** list: `duplicate_listing` (FAIL).

A close number is still checked against the index (`not_in_index`, `date_mismatch`) on every row,
repeated or not. The same section requires the 82-above-81 inversion to be INFO with exit 0, and
section 7 limits FAIL to structural errors such as a missing number, an id/printed mismatch or a
duplicate number in one listing. Section 6 Info I2 notes the listing is strictly by number, so the
inversion is read as number versus date, not as listing order.

**Declared range.** By default `missing_number` spans the lowest to the highest listed number, so
a list that loses No. 1 or its newest issue still passes. `--first N` and `--last N` (or
`run(paths, first, last)`) declare the expected range of every index list: a number of the range
that is absent is FAIL `missing_number`, and an index number outside it is FAIL `out_of_range`.
The values must be plain numbers 1..999999 with `first <= last`; anything else (0, `083`, `８３`,
bool, float) gives DENY `bad_range` (Python) or DENY `usage` (command line). Close numbers are not
range-checked. A declared run prints `declared first=N last=M` under the counts line.

**A closes-only run checks less.** With close lists and no index list the result is PASS exit 0
with INFO `index_absent`, because `not_in_index` and `date_mismatch` have nothing to compare with.
Read `index_absent` as "the cross-checks did not run", not as a clean result; pass the Daily list
too for a full check.

**Fail-closed.** A missing, unreadable (directory, not UTF-8) or malformed fixture (no header,
wrong header, wrong field count, unknown `kind`, `en`/`ko` not `yes`/`no` on an index row, a
non-empty `id`/`en`/`ko` on a close row, a blank or padded list name, a list with two kinds, a
list in two files), an empty fixture, a bad command line or an unwritable `--out` all give
`decision=DENY on_expiry=DENY` and exit 2. A `RecursionError` or `ValueError` while reading or
checking gives DENY `input_limit`, not a traceback. There is no pass on missing input.

**Row validation** (`validate_rows`, also usable from Python) checks exact types: each row an
exact `dict` whose keys are exact `str` and exactly `list kind id no date en ko line`, every field
an exact `str`, `line` an exact `int` >= 1. bool, float (NaN, infinity), other types and
subclasses are refused. It returns an immutable snapshot (nested tuples) and `check` works only
from that snapshot, so later edits to the rows change nothing.

## How to run

```
python3 -B issue_index.py fixtures/daily_list.tsv                              # the observed Daily list
python3 -B issue_index.py fixtures/daily_list.tsv fixtures/annals_closes.tsv   # plus annals closes
python3 -B issue_index.py fixtures/daily_list.tsv --first 1 --last 83          # declared range
python3 -B issue_index.py FIXTURE [FIXTURE ...] --out report.json --format json
python3 -B demo.py                                                             # demo sample
python3 -B -m unittest                                                         # tests
python3 -B mutants.py                                                          # mutation check
```

## Result on the observed site

`fixtures/daily_list.tsv` is the Daily list of the public site; `fixtures/annals_closes.tsv` is
the closes of annals Days 91–100 (see Sources). The Daily list alone passes with INFO only:

```
w25-daily-issue-index decision=PASS on_expiry=DENY
files=1 rows=83 lists=1 (index=1 close=0) comment_lines=4 blank_lines=0 FAIL=0 INFO=5
INFO --    date_gap daily found='2026-08-25' expected='a fact; no issue dated between 2026-08-24 and 2026-08-26'
INFO --    date_gap daily found='2026-08-29' expected='a fact; no issue dated between 2026-08-28 and 2026-08-30'
INFO --    date_gap daily found='2026-08-31' expected='a fact; no issue dated between 2026-08-30 and 2026-09-01'
INFO --    date_gap daily found='2026-11-10' expected='a fact; no issue dated between 2026-11-09 and 2026-11-11'
INFO L7    published_late daily 82 found='No. 82 · 2026-11-13' expected='dated on or after No. 81 · 2026-11-14'
list daily kind=index rows=83 numbers=1..83
```

With the annals closes the result is also PASS with INFO only. The two closes that count one
Daily twice (Day 91: "Daily 74, which is listed twice"; Day 94: "Daily 78, of November 9, counted
twice. It was reissued in the evening.") are INFO `counted_twice`; the three numbers named in two
closes are INFO `reissued`; every close number and date agrees with the Daily list:

```
w25-daily-issue-index decision=PASS on_expiry=DENY
files=2 rows=99 lists=10 (index=1 close=9) comment_lines=9 blank_lines=0 FAIL=0 INFO=10
INFO --    date_gap daily found='2026-08-25' expected='a fact; no issue dated between 2026-08-24 and 2026-08-26'
INFO --    date_gap daily found='2026-08-29' expected='a fact; no issue dated between 2026-08-28 and 2026-08-30'
INFO --    date_gap daily found='2026-08-31' expected='a fact; no issue dated between 2026-08-30 and 2026-09-01'
INFO --    date_gap daily found='2026-11-10' expected='a fact; no issue dated between 2026-11-09 and 2026-11-11'
INFO L7    published_late daily 82 found='No. 82 · 2026-11-13' expected='dated on or after No. 81 · 2026-11-14'
INFO L11   reissued annals-day-97 80 found='Daily 80 named in annals-day-98, annals-day-97' expected='a fact; not a duplicate listing'
INFO L14   reissued annals-day-94 78 found='Daily 78 named in annals-day-96, annals-day-94' expected='a fact; not a duplicate listing'
INFO L15   counted_twice annals-day-94 78 found='Daily 78 named 2 times in annals-day-94 (lines 14,15)' expected='a fact; a close may count a same-day reissue again'
INFO L18   reissued annals-day-92 76 found='Daily 76 named in annals-day-93, annals-day-92' expected='a fact; not a duplicate listing'
INFO L22   counted_twice annals-day-91 74 found='Daily 74 named 2 times in annals-day-91 (lines 21,22)' expected='a fact; a close may count a same-day reissue again'
list daily kind=index rows=83 numbers=1..83
list annals-day-100 kind=close rows=2 numbers=82..83
list annals-day-99 kind=close rows=1 numbers=81
list annals-day-98 kind=close rows=1 numbers=80
list annals-day-97 kind=close rows=1 numbers=80
list annals-day-96 kind=close rows=2 numbers=78..79
list annals-day-94 kind=close rows=2 numbers=78
list annals-day-93 kind=close rows=2 numbers=76..77
list annals-day-92 kind=close rows=2 numbers=75..76
list annals-day-91 kind=close rows=3 numbers=72..74
```

## Demo

`demo/issues.tsv` is a draft listing built from the observed rows No. 74–83 and the closes of
Days 96–98, with planted defects named in its comment lines (the planted rows are not
observations). `python3 -B demo.py` prints:

```
w25-daily-issue-index decision=FAIL on_expiry=DENY
files=1 rows=14 lists=4 (index=1 close=3) comment_lines=5 blank_lines=0 FAIL=6 INFO=4
FAIL --    missing_number draft found='missing 79' expected='74..83 contiguous'
FAIL L12   id_mismatch draft 77 found='id=71 no=77' expected='id equal to the printed number'
FAIL L13   language_missing draft 76 found='ko=no' expected='ko body present'
FAIL L14   unicode_field draft found="no='７５'" expected="no='75'"
FAIL L16   duplicate_listing draft 74 found='No. 74 listed 2 times (lines 15,16)' expected='each number once in one list'
FAIL L19   not_in_index annals-day-96 79 found='No. 79' expected='a number listed in an index list'
INFO --    date_gap draft found='2026-11-10..2026-11-11 (2 days)' expected='a fact; no issue dated between 2026-11-09 and 2026-11-12'
INFO L8    published_late draft 82 found='No. 82 · 2026-11-13' expected='dated on or after No. 81 · 2026-11-14'
INFO L16   listing_order draft 74 found='1 of 9 adjacent pairs not newest-first' expected='a fact; listing by number, highest first'
INFO L18   reissued annals-day-97 80 found='Daily 80 named in annals-day-98, annals-day-97' expected='a fact; not a duplicate listing'
list draft kind=index rows=10 numbers=74..83
list annals-day-98 kind=close rows=1 numbers=80
list annals-day-97 kind=close rows=1 numbers=80
list annals-day-96 kind=close rows=2 numbers=78..79
```

## How a caretaker would use it

1. Before or after the 17:00 ring, save the issue list as rows (`list`, `kind=index`, anchor id,
   printed number, printed date, `en`, `ko`); optionally add the day's close as a `kind=close`
   list.
2. Run `python3 -B issue_index.py daily.tsv closes.tsv`. Exit 0 means no structural error; read
   the INFO lines as facts (a late publication, a date with no issue, a reissue), not as faults.
3. On exit 1 fix the listing or the close (a missing number, an id typo, a doubled index
   entry, a missing language body, an invisible character). Add `--first 1 --last N` when the
   newest number is known, so a lost first or newest issue is not missed. Exit 2 means the fixture itself could not be
   read; nothing was checked.

The check never edits the site, never decides that an unpublished issue must go out, and never
looks at signatures.

## Sources

- Source: the observed live site Daily list, `https://ludex-lab.github.io/daily.html`, and the
  annals page `https://ludex-lab.github.io/annals.html` (Days 91–100), as fetched for the Wave25
  review on 2026-11-16 15:03:03 KST (`Last-Modified` 10:09:40 KST). Source hashes, the close
  sentences used for each row and the site counts are in `evidence.json`, all UNVERIFIED.
- The review verdict (sha256 `628be325aa11e592694a076f9edbe29f26ec8ae75f500294f0829705cae08a4b`):
  section 2a (83 issues, numbers 1–83, one inversion, both languages present), section 3 T2 and
  MEDIUM-1 (severity), Low-3 (name and disclaimer), Info I2 and I3 (number versus date; date
  gaps, the Daily 80 reissue and the Daily 74 double listing).
- The PR review verdict of the first round (sha256
  `11d9b3cbc17690a2a584942f483f6ab88db5ae4de113123c9ab5e51fcd0d9ed1`): M1 (a repeat inside one
  close is a same-day reissue, INFO), I4 (the Day 91 reading), Lows L1 to L4.
- The Wave25 pack, section TOP 2 (the fixture shape `{id, printed_no, date, lang_en, lang_ko}`).

## Limits

- Without `--first`/`--last`, `missing_number` counts from the lowest to the highest listed
  number, so a list that lacks No. 1 or its newest issue is not flagged; the observed list starts
  at No. 1 and ends at No. 83.
- `counted_twice` is INFO for every repeat inside a close, so a close row typed twice by mistake
  is reported as a fact, not failed; the annals text (quoted in `evidence.json`) is the place to
  tell a reissue from a typing slip.
- `list_name_form` flags names outside ASCII letters, digits and hyphens; it does not compare
  two names for likeness, and rows under a look-alike name are still checked as their own list.
- `published_late` compares neighbouring numbers only.
- Close lists cover Days 91–100 only (one annals page); earlier closes were not transcribed.
- `reissued` is read from closes only; a reissue that no close names is not seen, and the
  reissue sentences in the entries themselves (Days 91, 93, 94, 96, 98) are quoted in
  `evidence.json`, not parsed.
- No network at run time, no ports or daemons, no database, no hashing or signing, no paid APIs
  and no third-party code.
