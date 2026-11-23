# w32-record-manifest-presence

Does a record folder hold every file its cover names? Naru's measurement records each have a cover (a Markdown file
with a `## Files` table). The table names the specification, corrections, verdict, instruments and the data as run.
This tool reads such a cover, a listing of the record folder and, optionally, an ignore-rule file. It reports each
named file that the listing lacks as FAIL. When an ignore rule explains a miss, the report names that rule.

Lab Dig 2 Wave32 Top build, track 빌리지 생활 도구.

## Why

The public measurements page says each record holds the data exactly as it came out. The E1 and E2 covers in
`ludex-lab/ludex` (main `199dd04dc7382a4aab5173cd3d7c37f9021bebf1`) name `.jsonl` run files in their "Data as run"
group, but those files are not in the public tree. The repository's `.gitignore` has a `*.jsonl` rule, which explains
the gap. A link test cannot see this, because the page links to the folders, not to the files. A cover-versus-listing
check can. Every later record (E3 and on) can get the same check.

## Clean-room and scope

- Stdlib only, system `python3 -B`, file-in/file-out, with no network and no GitHub API. No upstream code was copied or
  run. The upstream repository is MIT, but only file names and the table shape were used.
- The fixtures are small and hand-made. They mirror the E1 and E2 Files tables (same names, same groups) with new
  prose. No site page is vendored.
- Read-only. The tool never creates, writes, repairs or restores a missing file, hashes nothing and uses no keys.
  The E2 cover suggests a signed commit or an external time anchor as a stronger proof; this tool implements
  neither.
- It does not claim that a missing file never existed, that any result is wrong, or what a missing file contains.
  Later commits, private copies and file contents are `on_unmeasured`.

## What it reports

| Level | Code | When |
|---|---|---|
| FAIL | `missing_named_file` | The cover names a file that the listing lacks. The report gives its cover group, e.g. `Data as run`. |
| FAIL | `missing_receipt` | The missing named file is a receipt: its name contains `receipt` (any case), or it equals `--receipt-name`. |
| INFO | `ignored_by_pattern <pattern>` | Added to a FAIL when an ignore rule matches the missing name. The FAIL stays. |
| INFO | `unparsed_name` | A token that is not one filename, such as `CORRECTION_01…03`, a `(+ AMENDMENT 01–04 in-file)` note after a name, loose words, a glob, or a comma list. Never FAIL and never dropped. A token that still reads as one file (a stem and an extension, even with a space, `@`, `+`, `~` or a leading dot) is checked; with a folder path in front, its last segment is checked. |
| INFO | `listed_not_named` | The listing has a file that the cover does not name (for example the cover itself). |
| INFO | `receipt_not_named` | `--receipt-name` was given, but the cover does not name that file. |

- Brace names expand per file: `` `e1_selftest_{agy,haiku,grok}.json` `` names three files. A brace group needs two
  or more non-empty choices, and nested or unbalanced braces are `unparsed_name`.
- A Corrections group is optional, since E2 has none. The report only says whether one is present.
- Parenthesised notes such as `(48 runs)` describe a name and are not names. A note that starts with `+` claims extra
  content and is reported as `unparsed_name`.
- Names are compared after NFC normalisation and are case-sensitive.
- Ignore rules use this tool's own matcher, not git. Blank lines and `#` comments are skipped, `!` negates, and the
  last matching rule decides. A rule ending in `/` only matches folders, so it never matches a file. A rule without
  `/` tests the filename. A rule with `/` tests `--record-path/<name>` and needs `--record-path`. Each `/` segment is
  matched with `fnmatchcase` (`*`, `?`, `[...]`), and `**` spans any number of folders.

Exit codes: 0 PASS, 1 FAIL, 2 DENY.

## Results on the fixtures

| Fixture | named | listed | missing | unparsed | result |
|---|---|---|---|---|---|
| E1 cover vs E1 listing | 20 | 20 | 4 (`e1_screen_v2.jsonl`, `e1_battery.jsonl`, `e1_anchor.jsonl`, `e1_telemetry.jsonl`) | 2 | FAIL |
| E2 cover vs E2 listing | 13 | 12 | 2 (`e2_battery.jsonl`, `e2_telemetry.jsonl`) | 0 | FAIL |
| E2 cover, receipt removed | 13 | 11 | 3, including `missing_receipt` | 0 | FAIL |
| E1 cover vs complete listing | 20 | 24 | 0 | 2 | PASS |

With `fixtures/ignore_rules.txt`, each of the six misses is absent and matches ignore pattern `*.jsonl`. That explains
the gap; it does not fill it.

The E1 analysis script's usage line names `e1_screen.jsonl`, while the cover names `e1_screen_v2.jsonl`. This check
uses the cover's name.

## How to run

```
python3 -B record_presence.py --cover fixtures/e1/cover.md --listing fixtures/e1/listing.txt \
    --ignore fixtures/ignore_rules.txt --record-path research/physics-e1      # exit 1, four FAIL lines
python3 -B record_presence.py --json --cover fixtures/e2/cover.md --listing fixtures/e2/listing.txt
python3 -B demo.py                # four runs; identical bytes every run
python3 -B -m unittest            # the suite
python3 -B mutants.py             # mutation run
```

A listing is one filename per line, UTF-8, with no blank lines, no `/` and no duplicates. On a real folder, `ls -1`
gives one.

## Contract

- Malformed, missing or unreadable input is `on_expiry=DENY`: exit 2, empty stdout, one stderr line
  `ERROR <code>: ... (on_expiry=DENY)`, and no traceback. This includes a cover without a `## Files` table.
- Error codes:
  - reading: `unreadable`, `too_large`, `bad_encoding`
  - cover: `no_files_table`, `two_files_tables`, `bad_files_header`, `bad_table_row`, `empty_files_table`,
    `too_many_rows`, `empty_group`, `duplicate_group`, `bad_cell`, `bad_name`, `duplicate_name`, `too_many_names`
  - listing: `blank_listing_line`, `bad_listing_name`, `duplicate_listing_name`, `too_many_listing_names`
  - ignore file: `bad_ignore_line`, `too_many_ignore_lines`
  - options: `bad_record_path`, `bad_receipt_name`, `usage`
- Caps, each with `on_expiry` DENY: 65536 bytes per input file, 50 table rows, 500 named files, 2000 listing names,
  1000 ignore lines and 255 characters per name.
- The tool itself has no timeout. `mutants.py` declares `TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}`. A timed-out
  mutant is TIMEOUT. A mutant that does not import, or whose suite only errors, is CRASH. Neither counts as a kill, and
  the summary prints killed / timeout / crash / survived.
- No test reads any Python source file. Every mutant must die by a failing behavioural test.

## Not a remake

w30-wave-chronicle reads day READMEs and flags a missing pinned date folder. w25-daily-issue-index and
w25-series-title-lint check issue lists and series labels. w20-fidelity-audit binds claims to artefact digests. None
of them compares a record cover's named files with a folder listing.

## Limits

- Only `## Files` pipe tables with one `Group` and one `Files` column. Fenced or free-form manifests are not read.
- A name with a folder path is checked by its last segment only; the listing is one flat folder.
- The ignore matcher does not apply git's rule that a file under an excluded folder cannot be re-included, and it
  takes backslash escapes literally.
- The receipt rule is a name heuristic plus `--receipt-name`. It does not read the receipt or verify any event or time
  stamp.
- The fixtures mirror the pinned tree. The live tree, later commits and private copies are not checked.

## Files

- `record_presence.py`: parser, matcher, check, report and CLI
- `test_record_presence.py`: unittest suite
- `demo.py`: deterministic four-run demo
- `mutants.py`: mutation run
- `evidence.json`: scope, measured counts, caps, `on_expiry`, `on_unmeasured`
- `fixtures/e1/`, `fixtures/e2/`: hand-made covers and listings mirroring E1 and E2
- `fixtures/unicode/`: Korean names, with the listing in NFD
- `fixtures/ignore_rules.txt`, `fixtures/ignore_negated.txt`: ignore rules
- `fixtures/bad/`: malformed covers, listings and ignore files, each DENY with its own code
