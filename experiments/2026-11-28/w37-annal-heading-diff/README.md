# w37-annal-heading-diff

A renamed heading is not a deletion. Two frozen snapshots of an annals or Daily-like markdown folder are compared as headed entries. A retitled entry whose body bytes did not change is reported as `renamed`, not as `removed` plus `added`.

## What and why

A Saturday retro should be able to say what changed in a frozen annals or Daily-like folder: entries added, removed, edited, renamed, or moved. A diff that keys rows by bytes cannot tell a retitled entry from a delete plus a new item. This tool parses a small declared heading grammar and matches entries in three exact passes, so a rename is named as a rename and an unclear case is left unpaired and flagged.

Source: observed need only (Lab Dig 2 Wave37, track 관찰·회고). Clean-room stdlib code. No paper, no upstream repository, no third-party code.

## How to run

From this folder, with system Python and the standard library only:

```
python3 -B annal_diff.py --before fixtures/valid/before --after fixtures/valid/after --pins fixtures/valid/pins.txt
python3 -B annal_diff.py --before fixtures/valid/before --after fixtures/valid/after --pins fixtures/valid/pins.txt --json
python3 -B demo.py
python3 -B -m unittest test_annal_diff
python3 -B mutants.py
sha256sum -c SHA256SUMS
```

`demo.py` prints `changes.md` for the authored fixtures. The committed `changes.md` is that output, and a test checks they are byte-identical.

## Grammar (v1)

- A file may start with one `# title` line. It is the document title, not an entry.
- An entry is an ATX `## heading` line (exactly two hash marks, one space, non-empty text, no leading or trailing space) plus the body up to the next `##` line or end of file.
- An optional first body line `id: <stable-id>` declares a stable identity. The id is lowercase ASCII words (letters and digits) joined by single hyphens.
- The body is compared as exact text after the id line, with leading and trailing blank lines removed.
- Any other line that starts with `#` is DENY `bad_level`, including `#` after line 1, `###`, and `#tag` body text. A malformed `##` line is DENY `bad_heading`. Non-blank text before the first entry is DENY `stray_text`.
- Files are UTF-8 with no BOM, no carriage return and no tab. Every file in a tree must be a regular `.md` file whose path parts use only `[A-Za-z0-9._-]`. Symlinks are DENY.
- A duplicate heading in one file is DENY `duplicate_heading` unless every copy has its own id. A duplicate id anywhere in one snapshot is DENY `duplicate_id`.
- Caps (all DENY): file 65536 bytes, 80 entries per file, 200 files per tree, 4000 characters per heading or body, 8 nested directories per tree. At each cap the input is accepted; one over is DENY. The tree walk is iterative, so a very deep tree is DENY `too_deep`, never a RecursionError.

## Pins

`--pins FILE` is required. Each line is `<sha256>  <size>  <side>/<relpath>` with two spaces between fields, and side is `before` or `after`. Every file in both trees must be pinned (`unpinned`), every pin must name a present file (`pin_missing`), and size and sha256 must match (`pin_mismatch`). A malformed or repeated line is `bad_pins`. Running without `--pins` is DENY `unpinned`.

## Matching: three deterministic passes

1. **Same id, snapshot-wide.** An old entry and a new entry with the same id are one entry wherever they sit.
2. **Same relative path and exact heading**, among entries left after pass 1. The key must be unique on both sides.
3. **Leftover body pairing, per unique body (Reading B).** If a non-empty leftover body occurs exactly once on each side, that pair is one entry. If it occurs more than once on either side, those entries are not paired: they are `removed` and `added`, with INFO `ambiguous_rename` naming them. Nothing is guessed on similarity.

Two entries that carry two different ids are never paired in pass 2 or 3. An empty body is never paired by body.

Classes (unchanged pairs are counted but not listed):

| class | when |
|---|---|
| `renamed` | same id, same body, different heading; or a unique leftover body pair with a different heading |
| `moved` | same heading and body, different path (by id, or by a unique leftover body) |
| `edited` | same id, or same path and heading, with a different body; `also_renamed=true` when the same id also changed its heading |
| `added` / `removed` | anything left unpaired |

A pair whose path also changed carries `also_moved=true`. A path, heading and body change with no id is `removed` plus `added`, never a guess. Each row lists old and new path, heading, id, how it was matched, and the sha256 of the file it came from (12 hex digits in `changes.md`, full in `--json`). The report ends with the count of each class.

## Refusals

Missing tree, unreadable file, unpinned file, pin mismatch, malformed heading, grammar break, or cap overrun: `on_expiry=DENY`, exit 2, empty stdout, and one stderr line `DENY <code>: <detail> (on_expiry=DENY)`. on_expiry is one of DENY, SAFE_FALLBACK, ESCALATE, HOLD and is never a pass value. The tool itself has no timeout. The mutant runner bounds each child run with `TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}`.

## Results (measured on the box with python3 -B)

- `fixtures/valid`: renamed 3, moved 1, edited 2, added 3, removed 3, unchanged 1, and one INFO `ambiguous_rename`.
  - Renamed: one by id, plus two unique body pairs without ids in the same file (the Reading B pin).
  - Moved: one stable id whose file changed path.
  - Edited: one plain body change, and one id whose heading and body both changed (`also_renamed=true`).
  - Added and removed include two bells whose body is shared on both sides, so they are not paired.
- Demo stdout sha256, identical on two runs: `cbe433bd3433eb971017ab37e1769ee150e06e4e4fa9681ff51389844d8038c2`.
- Unit tests: 69, all passing. They include the review's cases (a) to (l). Kills come from in-process tests. Child-process tests check the on-disk CLI shape only.
- Bad fixtures: 20 cases under `fixtures/bad/`, each exit 2 with empty stdout and one `DENY <code>: ` stderr line carrying the expected code.
- Mutants: 16, all KILLED-behaviour (0 crash, 0 timeout, 0 survived). Each runs in memory in a child `python3 -B`. A kill is a test assertion failure only. A timeout or a crash is never counted as a kill.
  - `pair_ambiguous_leftovers`: shared-body leftovers are paired anyway.
  - `ignore_level`: any run of hash marks is accepted as an entry.
  - `timeout_counts_as_kill`: the runner tallies a timed-out child as killed.
  - `leftover_singleton_only`: Reading A, pairing only a global one-and-one leftover.
  - `no_rename_class`: pass 3 is off, so retitles become removed plus added.
  - `ignore_id`: pass 1 is off.
  - `body_and_heading_is_rename`: a same-id heading and body change is called renamed.
  - `moved_as_removed_added`: id matching only within the same path.
  - `duplicate_heading_check_off`: duplicate headings with no ids are accepted.
  - `pair_distinct_ids`: two different ids can be paired in passes 2 and 3.
  - `empty_body_paired`: empty bodies are paired by body.
  - `pin_check_off`: only the size of a pin is compared.
  - `size_cap_off`, `entry_cap_off`, `depth_cap_off`: one cap raised.
  - `crash_counts_as_kill`: the runner tallies a load failure as killed.

## Assumptions

- Reading B is pinned for leftovers, as the review requires. Leftover pairing is snapshot-wide, not per file, so a unique body that changes file and heading is `renamed` with `also_moved=true`. One with the same heading is `moved`.
- `moved` is a declared class. It is not in the original sketch.
- The body excludes the id line, so adding or dropping only an id line on the same path and heading is unchanged.
- Pins are required, not optional, so that unpinned input is always DENY.
- Two different ids are two identities. A shared body between them is not paired and raises no INFO.

## Limits

- Exact bytes only. A retitle with a one-character body edit and no id is `removed` plus `added`. An `id:` line holds identity through edits.
- Shared bodies (for example a repeated "The bell rang.") are never paired. They are reported and flagged instead.
- Order of entries within a file is not reported, and neither are title-line changes.
- The fixtures are small, authored examples, not a copy of any village page.

## on_unmeasured (UNVERIFIED)

- Any real Naru annals or Daily page: not opened, not copied into the fixtures, UNVERIFIED.
- Any count taken from a live `experiments/` tree or a live git log: not measured, UNVERIFIED.
- Any claim that this reproduces a published structured-diff method: none was opened, UNVERIFIED.

## How this differs

- `w30-wave-chronicle` (#154) keys day-README slug rows by `experiments/<date>/<slug>`. It reports added, removed or changed row bytes, with no rename class. This tool reads a different grammar (`##` entries with optional ids) and asks whether a retitled body is a rename.
- `w25-daily-issue-index` checks Daily issue numbers and dates in a TSV. It does not diff two snapshots of headed entries.
- `mb-forecast-or-already-known` (#168) is about post-cutoff leakage in a score, not heading identity.
