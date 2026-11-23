# w30-wave-chronicle

A dated wave chronicle from the experiments index, not a remembered list. `wave_chronicle.py` reads the day READMEs
under `experiments/YYYY-MM-DD/README.md`, turns their `- [slug](slug/): …` rows into a timeline tagged with wave,
family and track, counts them, and can list what changed between two snapshots. Every timeline entry carries the path
and the git blob SHA1 of the day README it came from, so a reader can check each line against the repository.

Clean-room team sketch (Lab Dig 2 Wave30 build #1): no paper and no upstream repository were used, read or copied.
The need comes from the team's own experiments index; all code here is original stdlib work.

Not a remake: w25-daily-issue-index checks Naru Daily issue numbers and dates, and w20-fidelity-audit binds tool claims to artefact digests; this builds a lab timeline from day-README rows.

## Scope (v1)

- Measured: day READMEs dated **2026-11-09 or later**. From that day on the index uses one row shape.
- Not measured: earlier day folders use other headings and table rows. They are listed under `on_unmeasured` as
  `legacy_table_format` and are **never opened**, so they can never fail a run.
- `--from DATE` / `--to DATE` (inclusive) limit the run. Days outside the window are listed as `outside_window` and
  are never opened either.
- Inside the scope and the window, input must be exact. Any missing, unreadable or malformed input is DENY.

## Grammar of an in-scope day README

1. Line 1 is exactly `# experiments/<date>`, and the date equals the folder name.
2. Line 2 is blank.
3. One or more rows `- [slug](slug/): text`. The slug is lowercase ASCII words joined by hyphens, and the link is the
   slug folder. The text may be any language (Korean included, NFC or NFD), with no control, format, private-use or
   unassigned characters and no spaces other than U+0020.
4. Optionally a blank line and then the footer line `Do not merge experiment PRs without Ork review.`, which is not an entry.
5. At most one final newline. UTF-8 only: no byte order mark, no carriage returns.

The wave is the number in a `wNN-` prefix; the family is the first hyphen-separated part of the slug (`mb`, `w28`,
`01`). The track comes only from `--tracks` (a JSON object of prefix to name). An unknown prefix is listed with INFO
`unknown_track` and no track; the tool never invents a track name. `fixtures/tracks.json` maps `mb`, `w25` to `w30`.
w24 is left out on purpose: its track is not sourced.

## Pinned snapshot of real data

`fixtures/snapshot-f2fa1e5d/` holds the 13 real day READMEs 2026-11-09 to 2026-11-21 from main
`f2fa1e5d341f2f022d5b4a61d7563a6560db0212`, copied byte-exact, plus `pins.txt` with each file's git blob SHA1 and
size. Each copy was matched against the SHA-verified blob index before use. With `--pins` (or `--case`), every README
a run opens must be pinned, and its blob id (sha1 of `blob <len>\0` plus the bytes) and size must match. A flipped byte
is DENY `pin_mismatch`. These are frozen bytes, not a live checkout and not a live git log. They are left exactly as on
main, including their footer lines.

Measured on the snapshot (regression tests assert these):

| | value |
|---|---|
| days | 13 |
| entries | 49 |
| per day | 11-09 7, 11-10 4, 11-11 5, 11-12 7, 11-13 4, 11-14 4, 11-15 4, 11-16 3, 11-17 2, 11-18 3, 11-19 3, 11-20 2, 11-21 1 |
| by track | morning-brief 10, 검증 3, 빌리지 생활 도구 2, 에이전트 사이 협업 2, 창작·놀이 1, no track 31 |
| week 11-15..11-21 | 7 days, 18 entries; what changed since 11-20: one added entry, `experiments/2026-11-21/mb-evidence-binding` |

## Usage

```
python3 -B wave_chronicle.py --case fixtures/snapshot-f2fa1e5d --tracks fixtures/tracks.json
python3 -B wave_chronicle.py --root DIR [--pins FILE] [--tracks FILE] [--from DATE] [--to DATE] \
    [--base DIR] [--base-pins FILE] [--base-to DATE] [--json]
```

`--base DIR` compares against an older snapshot: entries added, removed, or changed (same `experiments/<date>/<slug>`,
different row bytes), each with the blob it came from. `--base-to DATE` alone compares against the same root up to that
date. `--case DIR` is shorthand for `DIR/experiments` plus `DIR/pins.txt`, `DIR/tracks.json`, `DIR/base/` and the
window flags in `DIR/args`, each only when present. Output is markdown by default, or JSON with `--json`.

## Contract

- Exit 0 with the chronicle on stdout, or exit 2 with empty stdout and exactly one stderr line
  `ERROR <code>: <detail> (on_expiry=DENY)`. No traceback, no partial timeline.
- Every cap has `on_expiry` DENY: README 65536 bytes, 60 entries per day, 400 root entries, 4000 characters per row,
  80 per slug, 65536 bytes per pin or tracks file, 100 tracks, 40 characters per track name, 1024 bytes of case args.
- The tool has no timeout. `mutants.py` bounds each suite run with `TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}`;
  a run that reaches it is reported as TIMEOUT and is not counted as killed.
- Deterministic: sorted listings, no clock, no randomness, no network, stdlib only, system `python3 -B`.

## Probe battery (fixtures/bad, 117 folders)

Each bad folder exits 2 with one ERROR line and its own expected code: other headings (including the legacy titles),
heading date mismatch, table rows, bold-label bullets, link and slug errors (uppercase, Korean, `./slug/`, backticks,
double hyphen, overlong), empty or edge-spaced text, tab, NUL, escape, zero-width and bidi characters, no-break space,
line separator, private-use and unassigned code points, CRLF and lone CR, byte order mark, invalid, overlong and
surrogate UTF-8, UTF-16, stray lines, footer variants, size and count caps, a README that is a folder, missing READMEs,
stray or impossible root entries, empty and inverted windows, bad arguments, pin mismatches (hash, size, unpinned,
missing, uppercase, short, duplicate, unsorted, huge or zero-padded size, legacy day, CRLF), and tracks files with
duplicate keys, NaN or Infinity, floats, ints, huge ints, booleans, null, nesting, deep nesting, a lone surrogate,
control and zero-width characters, bad keys and size caps. `fixtures/valid` (13 folders) covers the planned cases,
legacy and out-of-window days that are unreadable but never opened, two-snapshot diffs and Korean text.

## Files

| Path | What it is |
|---|---|
| `wave_chronicle.py` | loader, grammar, pins, timeline, counts, diff, markdown and JSON output, command line |
| `test_wave_chronicle.py` | unittest suite (`python3 -B -m unittest`), including the real-snapshot regression |
| `demo.py` | deterministic demo on the pinned snapshot (full chronicle, then the week with what changed) |
| `mutants.py` | breaks the module one way at a time and requires the suite to fail every time |
| `evidence.json` | measured counts on the snapshot; facts outside it under `on_unmeasured`, all UNVERIFIED |
| `fixtures/` | `snapshot-f2fa1e5d/` (frozen real bytes), `tracks.json`, `valid/`, `bad/` |

Demo output sha256 (two runs, identical): `1eae6b8f48e1ac6d8f9e11a37339ddd6a3839aba8e0c00b712d331ad155692b3`

## Limits

- v1 reads README rows only: no live git log, merge times or authors.
- Days before 2026-11-09 are not measured; a later version could add a declared table-row grammar for them.
- Track names exist only where a prefix is mapped; waves 18 to 24 have none here.
- Changed means different row bytes; a reworded row and a substantive change look the same.
- The snapshot is frozen at main `f2fa1e5d`; anything added later is UNVERIFIED until a new pinned snapshot is made.

## How a Ludex village would use it

On a Saturday, the Lab Dig team points it at a fresh pinned copy of the index and gets the week's `w*` and `mb-*`
landings as a dated timeline, each line traceable to a blob. Naru or Cody could later point the two-snapshot diff at
a frozen copy of a Daily or annals folder once that folder has a declared row shape; no village page was opened here.
