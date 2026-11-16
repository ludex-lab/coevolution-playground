# w25-series-title-lint

A small file-in/file-out lint for series labels in video titles. It was built for Yeoul's
`@LudexVillage` channel, where the recurring Weekly, the documentary series and the OSTs do not
use one series string or one number style. Python 3 standard library only. No network, no
subprocess, no clock and no randomness in the module.

Inputs:

- a **titles file**: either one title per line, or TSV with the header `ref<TAB>lang<TAB>title`
  (`ref` is free text such as a video id or a date; `lang` is a declared language code, or empty
  to let the label decide). **Comment lines** exist only in TSV mode: lines starting with `#`
  before the header are skipped. After the header every non-blank line is a row (a `ref` may
  start with `#`; a `# note` line has the wrong field count and gives DENY). A file without the
  header is plain lines, and there every non-blank line is a title, including one that starts
  with `#` (`#LudexVillage | Ludex Weekly06` is linted, not skipped). Blank lines are skipped;
- a **series catalog** (JSON) that declares, per series:
  - the canonical label for every language, with its number format (`pad`, `suffix`). Korean
    titles use `루덱스 빌리지 다큐 4화` on purpose, so the catalog gives the documentary a `ko`
    label `루덱스 빌리지 다큐` with `pad: 0` and suffix `화`;
  - **retired aliases in order**, each with the last number it covered. For the Weekly that is
    `Naru Daily Weekly` (01), then `Ludex Daily Weekly` (02), then `Ludex Weekly` from 03 on;
  - known drift spellings (`variants`), e.g. `Ludex Village Doc`;
  - optionally, a `names` table of characters per language with known misspellings. This
    replaces a separate character-name lint.

Output: a report with one decision, `PASS`, `FAIL` or `DENY`. `on_expiry` is always `DENY`.

| code | severity | when |
|---|---|---|
| `spacing_drift` | FAIL | the label differs from the canonical rendering only by spaces or separators (`Ludex Weekly06`) |
| `case_drift` | FAIL | the label differs only by letter case |
| `number_format_drift` | FAIL | the number is padded or decorated differently (`Ludex Weekly 6`, `Documentary · Ep. 2`, `다큐 04화`) |
| `label_drift` | FAIL | a declared variant spelling (`Ludex Village Doc 07` where the series says `Documentary`) |
| `language_label` | FAIL | the row's `lang` says one language but the label of another is used |
| `retired_alias_out_of_era` | FAIL | a retired alias on a number after (or before) its era (`Naru Daily Weekly 09`) |
| `duplicate_number` | FAIL | two titles claim the same number in one series |
| `name_drift`, `name_case_drift` | FAIL | a declared misspelling of a character name, or a name in the wrong case |
| `number_gap` | WARN | numbers missing between the series' `first` and its highest seen number |
| `unicode_drift` | FAIL | the mention contains invisible format characters (zero-width space, zero-width joiner, soft hyphen), non-ASCII digits (`０８`, `٠٨`, `⑧`) or compatibility forms (`Ｌudex`) |
| `label_without_number` | FAIL | a declared label (canonical, retired or variant, any language) with no parsable number after it (`Ludex Weekly #08`, `No. 8`, `Episode 8`, `: 08`, `(08)`, `다큐 제8화`, `Ludex Weekly Special`) |
| `label_near_miss` | FAIL | the words of a declared label with at most one letter edited (`Weekley`, Cyrillic `е` in `Ludеx`) or joined by a non-separator (`Ludex & Weekly`); labels of 6 or more letters only |
| `retired_alias` | INFO | a retired alias on a past item inside its era. This is history, not drift |
| `unmatched_title` | INFO | the title mentions no declared series label; listed so that nothing is counted silently |

Exit codes: `0` PASS (WARN and INFO do not fail), `1` FAIL, `2` DENY.

**Folding before matching.** Each title is put in NFC form; then format characters (Unicode
category Cf) are removed, decimal digits of any script become ASCII digits, and every other
character is NFKC-normalised. Matching runs on the folded text, and every finding quotes the
original text. A mention whose original text differs from the folded text (other than in
whitespace, which stays `spacing_drift`) is `unicode_drift`. A number longer than 6 digits is
`number_format_drift` and is not counted. A `number_gap` list shows at most 20 numbers and then
the total (`... (N missing)`).

**Fail-closed.** A missing, unreadable (directory, not UTF-8) or malformed titles file or
catalog, an empty titles file, a bad command line or an unwritable `--out` all give
`decision=DENY on_expiry=DENY` and exit 2. A `RecursionError` or `ValueError` while reading
or linting (for example a catalog nested 100,000 levels deep) gives DENY `input_limit`, exit
2, not a traceback. There is no pass on missing input.

**Catalog validation** (`validate_catalog`) checks exact types: keys and strings must be
exact `str`, objects exact `dict`, numbers exact `int` (bool, float, NaN and infinity are
refused; the JSON reader also refuses `NaN`/`Infinity` and duplicate keys). Unknown or missing
keys are refused. A label must be NFKC-normal with ASCII digits and no invisible (Cf)
characters, may not end in a digit, and may not collide, after removing spaces and
separators and ignoring case, with a label of another series. Retired aliases must be in
increasing order. The function returns an immutable snapshot (nested tuples), and the lint
works only from that snapshot, so later edits to the loaded object change nothing.

## How to run

```
python3 -B lint_titles.py fixtures/live_titles.tsv fixtures/catalog.json            # text report
python3 -B lint_titles.py TITLES CATALOG --out report.json --format json            # file out
python3 -B demo.py                                                                  # demo sample
python3 -B -m unittest                                                              # tests
python3 -B mutants.py                                                               # mutation check
```

## Result on the observed titles

`fixtures/live_titles.tsv` holds the first-page titles of the `@LudexVillage` videos tab
(see Sources). With `fixtures/catalog.json`:

```
w25-series-title-lint decision=FAIL on_expiry=DENY
titles=29 matched=17 unmatched=12 FAIL=4 WARN=1 INFO=14
WARN --   number_gap documentary found='missing 1' expected='1..7 contiguous'
INFO L7   unmatched_title  ref=Rcjuf2oD7Lo found='작업대의 첫 박자 | The First Beat at the Workbench · Nella' expected='no declared series label'
FAIL L8   label_drift documentary 7 ref=OI7T4YiBjvQ found='Ludex Village Doc 07' expected='Ludex Village Documentary 07'
FAIL L9   spacing_drift weekly 6 ref=5PmEeWP2i6I found='Ludex Weekly06' expected='Ludex Weekly 06'
INFO L10  unmatched_title  ref=ul-SOEF7CRQ found='Same Character, One Shot Changed | Ludex Village Maker Film' expected='no declared series label'
INFO L11  unmatched_title  ref=--rKxmXZ7Bg found='Across Small Distances | Milo · Weft & Rivet · Ludex Village' expected='no declared series label'
FAIL L13  spacing_drift weekly 5 ref=2PNq9HAiHtQ found='Ludex Weekly05' expected='Ludex Weekly 05'
INFO L14  unmatched_title  ref=4wJmyvFnX-o found='A Door That Actually Opens | Building Ludex Village' expected='no declared series label'
INFO L18  unmatched_title  ref=--pWy5YFitc found='같은 카페를 다시 찾아가려면 | 루덱스 월드를 만드는 기준' expected='no declared series label'
INFO L19  unmatched_title  ref=MaIpArLQjEI found='실의 다른 끝에서 | 엘리스 & 코디 · Ludex Village' expected='no declared series label'
INFO L22  unmatched_title  ref=fSDFurX5fAQ found='영상 속 카페가 공간이 되기까지 | 루덱스 빌리지 3D 공방' expected='no declared series label'
INFO L25  retired_alias weekly 2 ref=HsNupqme-Is found='Ludex Daily Weekly 02' expected='Ludex Weekly 02'
INFO L26  unmatched_title  ref=kfcF8d8satg found='마을은 어떻게 노래를 만들까? | Luma와 이음의 제작 이야기' expected='no declared series label'
INFO L27  unmatched_title  ref=ymAxGuLj-zE found='Leave a Little Light | Luma & Ieum · Ludex Village Music Video' expected='no declared series label'
INFO L28  unmatched_title  ref=Ka-uhyudZes found='The Neighbor Who Never Says Hello | A Fruit-Fly Circuit in Ludex Village' expected='no declared series label'
INFO L29  retired_alias weekly 1 ref=G7ZfTlY4bmY found='Naru Daily Weekly 01' expected='Ludex Weekly 01'
FAIL L31  number_format_drift documentary 2 ref=cFAe8QRvvL8 found='Ludex Village Documentary · Ep. 2' expected='Ludex Village Documentary 02'
INFO L32  unmatched_title  ref=Z2T9DktKzNA found='A Village in a Bag | The Morning the Ledger Missed' expected='no declared series label'
INFO L33  unmatched_title  ref=sw2scAPEBSU found='Myoha: Two Tiny Rules | Behind the Workbench' expected='no declared series label'
series documentary numbers=2,3,4,5,6,7
series ost numbers=1,2,3,4
series weekly numbers=1,2,3,4,5,6,7
```

The Korean `다큐 4화` and `다큐 3화`, `루덱스 빌리지 OST 03`, the Weekly 03 title with a Korean
headline, and every character name pass. The documentary gap (no 01) is a WARN because only
the first page of the channel was read; it is not a claim that a Documentary 01 is missing.
The 12 titles with no series label are listed as INFO `unmatched_title`.
`Documentary · Ep. 2` is reported as format drift with this catalog. If the caretaker decides
the early `· Ep.` style was a deliberate first format, declaring it as a retired alias
(`"label": "Ludex Village Documentary · Ep.", "last": 2, "pad": 0`) turns it into INFO; a
test shows this.

**Which documentary label is canonical is a caretaker decision (UNVERIFIED).** The catalog
makes `Ludex Village Documentary` canonical and `Ludex Village Doc` drift, because 05 and 06
use the long form. The newest upload (07) uses `Doc`, and the Weekly history shows this
channel renaming forward, so `Doc` may be the new name rather than a slip. The tool does not
decide this. To flip it, declare `"en": {"label": "Ludex Village Doc", ...}` and move the long
form to `"retired": [{"label": "Ludex Village Documentary", "last": 6, "pad": 2}]` (and drop
the variant); no code change is needed.

## Demo

`python3 -B demo.py` lints `demo/titles.tsv` (authored drafts plus four past titles) against
`fixtures/catalog.json` and prints:

```
w25-series-title-lint decision=FAIL on_expiry=DENY
titles=10 matched=9 unmatched=1 FAIL=5 WARN=3 INFO=3
WARN --   number_gap documentary found='missing 1,2,3,4,5,6' expected='1..8 contiguous'
WARN --   number_gap ost found='missing 1,2,3,4' expected='1..6 contiguous'
WARN --   number_gap weekly found='missing 3,4,5,6' expected='1..9 contiguous'
INFO L4   retired_alias weekly 1 ref=past-w01 found='Naru Daily Weekly 01' expected='Ludex Weekly 01'
INFO L5   retired_alias weekly 2 ref=past-w02 found='Ludex Daily Weekly 02' expected='Ludex Weekly 02'
FAIL L7   label_drift documentary 7 ref=past-d07 found='Ludex Village Doc 07' expected='Ludex Village Documentary 07'
FAIL L8   spacing_drift weekly 8 ref=draft-w08 found='Ludex Weekly08' expected='Ludex Weekly 08'
FAIL L9   retired_alias_out_of_era weekly 9 ref=draft-w09 found='Naru Daily Weekly 09' expected='Ludex Weekly 09'
FAIL L12  number_format_drift ost 6 ref=draft-o06e found='Ludex Village OST 6' expected='Ludex Village OST 06'
FAIL L13  name_case_drift ieum ref=draft-mv found='ieum' expected='Ieum'
INFO L13  unmatched_title  ref=draft-mv found='Draft: Two Voices | Luma & ieum · Ludex Village Music Video' expected='no declared series label'
series documentary numbers=7,8
series ost numbers=5,6
series weekly numbers=1,2,7,8,9
```

The English OST draft is a different song with its own number (OST 6), so the demo shows a
padding slip, not a cross-language duplicate. Its stdout sha256 is
`b58c1e167e4223b5959347c40969eadeb5c61bcffa2fe2d3f7e3051d01670973`,
pinned in `test_lint_titles.py`.

## How a caretaker would use it on Yeoul titles

1. Maintain one catalog file per channel (start from `fixtures/catalog.json`). When a series is
   renamed, move the old label into `retired` with the last number it covered. Do not delete
   it: past videos still carry it and should be reported as INFO.
2. Before an upload, write the drafted title(s) into a TSV together with the recent published
   titles (`ref<TAB>lang<TAB>title`, `lang` = the language of the series label segment) and run
   `python3 -B lint_titles.py drafts.tsv catalog.json`.
3. Fix every FAIL before the title ships (spacing, padding, `Doc` vs `Documentary`, a retired
   alias reused, a number already taken, a misspelt character). Read WARN gaps as "check
   whether an episode is missing or simply not in this file". INFO lines need no action, but
   skim the `unmatched_title` lines: a series title that shows up there carries a label the
   catalog does not know yet.
4. Exit 2 (DENY) means an input could not be read. Nothing was checked, so treat the title as not
   cleared.

The tool never fetches the channel, never renames anything, and does not judge video content.

## Sources

Source = observed `@LudexVillage` titles. `fixtures/live_titles.tsv` copies the id and title
columns verbatim from `raw/youtube-videos-tab-first-page.tsv` of the Wave25 lab-dig pack
(sha256 `5ce2cee7…88705`; fetched 2026-11-16 about 14:53-14:58 KST). The Wave25 review
VERDICT (sha256 `628be325…a4b`, section 2c) re-parsed the same page independently with an
identical result, and asked for retired aliases and per-language labels (defect L2) and for
a names table in this tool (defect L1). One row of the raw file is omitted from the
fixture: its title contains a word on this repository's banned-substring list, and it carries
no catalog series label. Its id and a hash of its raw line are in `evidence.json`. The `lang`
column is an annotation added here, not observed. Channel counts and quotes are recorded only
in `evidence.json`, marked UNVERIFIED. The tests copy titles into fixtures; they never scrape.

## Files

- `lint_titles.py`: catalog validation and snapshot, titles parsing, lint, text/JSON report, CLI.
- `test_lint_titles.py`: unittest suite (live drift, retired alias, per-language labels, names,
  numbers, fail-closed inputs, exact-type validation, snapshot, demo hash, stdlib-only imports,
  and the 27 decorated, unparseable and invisible-character variants from the r2 review).
- `mutants.py`: mutation harness. It copies the folder to a temporary directory, applies one
  source edit, and runs the suite with the same interpreter.
- `demo.py`, `demo/titles.tsv`: the demo.
- `fixtures/catalog.json`, `fixtures/live_titles.tsv`: catalog and observed titles.
- `evidence.json`: provenance, hashes, quoted titles and counts (UNVERIFIED).

## Mutation check

`python3 -B mutants.py` applies 134 single-fragment mutants: validation 34, parsing 8,
matching 9, severity 13, numbers 3, names 5, deny 10, folding 14, unparsed 21, comments 4,
limits 6, and data 7 (catalog, live fixture, demo inputs). All 134 are killed. The data mutants are caught first by the pinned fixture
and demo hashes.

## Limits

- A drift spelling is caught when the catalog declares it as a variant, when it differs from
  a declared label by spaces, separators, case, number format or folded characters, when a
  declared label has no parsable number, or when it is within one letter edit of a declared
  label of 6 or more letters. A heavier misspelling, or a transposition (`Weekyl`), is listed
  only as INFO `unmatched_title`. Labels shorter than 6 letters get no near-miss check.
- Matching runs per character after folding; characters that NFKC would combine only across
  a sequence (rare outside decomposed Hangul jamo) are first combined by NFC.
- Names are checked against declared labels and misspellings only. The tool cannot discover an
  unknown name.
- Duplicates count across languages: one video, one number. Bilingual twin uploads of one
  episode would be reported as duplicates.
- The observed fixture is the first page of the videos tab only.
