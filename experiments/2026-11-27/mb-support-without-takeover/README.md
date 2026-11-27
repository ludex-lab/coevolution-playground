# mb-support-without-takeover

A writing session can accept many inline suggestions and still look "helped" while most of the surviving text was inserted by the assistant. A help-count-only check (arm A) passes that session. An ownership-preserving gate (arm B) compares the exact integer ratio of surviving human characters to all surviving characters, and fails the session when that ratio is below the declared bound.

Synthetic drafts, declarative edit events, planted sessions. This shows the mechanism only. It is not evidence of any rate and reproduces no paper number.

## Declared rules

- A session is a mode label (`cowrite` or `scaffold`) plus a list of declarative edit events from a closed set: `human_insert`, `offer`, `accept`, `reject`, `scaffold`, `human_expand`, `delete`, `replace`.
- The harness walks those events and measures, itself: surviving spans tagged `human` or `ai`, the accepted-help count (number of accepted inline suggestions), and the exact ownership ratio `human_chars / total_chars`. It never reads an ownership, help, agency, or character-count field from the fixture.
- A fixture or session that declares `ownership`, `ownership_ratio`, `help_count`, `accepted_help`, `accepted_help_count`, `human_chars`, `ai_chars`, `agency`, or `perceived_agency` is DENY `self_reported_measure`, exit 2, empty stdout, one stderr line.
- Ownership is an exact rational. The gate uses `human_chars * min_den >= min_num * total_chars`. There is no float rounding. Empty surviving text is DENY `empty_surviving`.
- Arm A (help-count only): PASS iff `accepted_help_count >= min_help`. Scaffold prompts are shown to the human and are not inserted into the draft; they do not count as accepted help.
- Arm B (ownership-preserving gate): PASS iff surviving text is non-empty and ownership is at least `min_ownership`. Mode is a label only; it does not change either arm.
- The fixture declares the expected table for every session before the run. The gate is PASS (exit 0) iff the observed arm A and arm B statuses equal it exactly. Otherwise the run fails (exit 1).
- Expected table for `fixtures/main.json` (`min_help` 1, `min_ownership` 3/4):

| session | arm A | arm B | measured (help, ownership) | why this row is in the table |
|---|---|---|---|---|
| heavy_cowrite | PASS | FAIL | help 3, 7/66 | many accepted inline suggestions; ownership drops below 3/4 |
| scaffold_with_human_expansion | FAIL | PASS | help 0, 1/1 | reflective prompts plus human-authored expansion; text grows; no AI span |
| cowrite_all_rejected | FAIL | PASS | help 0, 1/1 | mode is cowrite, every suggestion is rejected; the mode label alone does not fail arm B |
| partial_cowrite_within_cap | PASS | PASS | help 1, 18/24 = 3/4 | a tiny accepted span sits on the bound; the bound is measured, not "any AI span = FAIL" |
| human_rewrite_restores_ownership | PASS | PASS | help 1, 39/39 = 1/1 | a large accepted span is later replaced by the human; surviving spans matter, not the cumulative accept count |
| self_reported_ownership (standalone bad fixture) | DENY exit 2 | DENY exit 2 | — | self-reported `ownership` field |

- Bad input is DENY: exit 2, empty stdout, one stderr line `DENY <code>: <detail>`. Ids and fields are type-checked before any dict or set lookup, so a list, object, null, bool or float is `bad_type`. A bool is refused before the integer check. Codes include: not_json, duplicate_key, unknown_field, missing_field, bad_type, bad_version, bad_on_expiry, unknown_mode, unknown_op, unknown_span, out_of_range, bad_expected, too_many, too_long, too_large (fixture over 32768 bytes), self_reported_measure, too_deep (nesting over 16 levels), empty_surviving, bad_text, bad_utf, unreadable, usage.
- `on_expiry` must be literally one of `DENY`, `SAFE_FALLBACK`, `ESCALATE`, `HOLD`. Any other value is DENY. The mutant runner's timeout is `{"seconds": 300, "on_expiry": "DENY"}`. A timeout is not a kill, and crashes are counted separately.

## Files and how to run

- `ownership.py`: module and CLI (`python3 -B ownership.py [--json] fixtures/main.json`).
- `test_ownership.py`: unit tests (`python3 -B -m unittest test_ownership`). No test reads a source file.
- `demo.py`: prints the report for the fixture, then the standalone `self_reported_ownership` DENY (`python3 -B demo.py`).
- `mutants.py`: six in-memory mutants, each run in a child `python3 -B` (`python3 -B mutants.py`).
- `evidence.json`: the declared table, measured results and `on_unmeasured`.
- `fixtures/main.json` and `fixtures/bad/*.json` (26 bad fixtures; unreadable, usage, and invalid UTF-8 bytes are covered by tests).
- `SHA256SUMS`: sha256 of every other file here; run `sha256sum -c SHA256SUMS` inside this folder.
- Stdlib only, no network, no randomness, no model calls, no wall-clock gate metric.

## Limits

- Span-level text ownership is a structural proxy, not psychological perceived agency. The harness only tracks scripted edit events in this synthetic model. It does not measure how a writer felt about the draft.
- Accepted help is the count of accepted inline suggestions. Reflective scaffold prompts are not inserted and are not counted as help.
- Ownership is computed on surviving spans after delete and replace. A cumulative accept count is not the ownership figure.
- Character counts are Unicode code points of the scripted strings (the fixture text is ASCII).
- One synthetic fixture with planted sessions. This shows the mechanism, not how often it happens.
- Paper figures are under `on_unmeasured` and UNVERIFIED.
- The fixture supplies `min_help`, `min_ownership` and the expected table. `min_ownership` 0/1 makes arm B pass every session; the gate checks that the declared table matches, not that the bound is strict.
- Span sources come from the declared op names. A `replace` or `human_expand` whose text equals an earlier AI offer still counts as human; the harness does not compare texts.

## Source and licence

- Thu Bui, Shashi Salavath, Hillary Merzdorf, Louis Tay and Sooyeon Jeong, "Supporting Without Taking Over: AI Support in Gratitude Writing", [arXiv 2611.34673](https://arxiv.org/abs/2611.34673), arXiv v1 Thu 26 Nov 2026 01:38:14 KST (from Wed 25 Nov 2026 16:38:14 UTC). Licence [nonexclusive-distrib 1.0](http://arxiv.org/licenses/nonexclusive-distrib/1.0/), method-only. The citation_title was read from the abs page meta tags. No repository URL appears on the abs page, so no code was used. This is a method sketch only. No code is copied, and the only text from the paper is the attributed quotes in `on_unmeasured` below.

## on_unmeasured (UNVERIFIED)

- Paper-reported 2x2 between-subjects study (N=401): UNVERIFIED, not measured here. Attributed abstract quote: "In a 2x2 between-subjects study (N=401), participants completed a gratitude reflection or a gratitude letter using two AI-assistance modes: scaffolding, which provided reflective questions after inactivity, or co-writing, which offered inline text suggestions."
- Author-reported claim that participants' well-being improved after using the AI-assisted gratitude-writing system: UNVERIFIED, not measured here.
- Author-reported usability, perceived agency, and perceived ownership findings: UNVERIFIED, not measured here. Attributed abstract quote: "co-writing received higher usability ratings, yet its immediacy could disrupt writing, and greater suggestion acceptance was associated with weaker perceived agency. Scaffolding supported stronger perceived human ownership but was sometimes overlooked."
- Psychological perceived agency and perceived ownership: UNVERIFIED (the harness uses a structural span-level proxy only).

## Distinct from

- #152 (`play-then-craft`): a play stage then a crafted artefact. This experiment scores accepted inline help against surviving text ownership in a draft, not a play-then-craft sequence.
- #153 (evidence binding, loose vs strict): about whether a claim is bound to evidence. There is no quote-to-period binding here.
- #163 (`w34-mixed-index-crowds-unseen-tools`): retrieval crowding in a tool router's candidate list. Unrelated to draft ownership.
- #164 (`mb-intervention-voucher`): a history-replay pass is not a what-if voucher on named records. Different objects (named counts, not surviving text spans).
- #165 (`w35-stopwatch-is-not-the-mechanism`): a cheaper scripted work-cost is not proof of a claimed mechanism or an unchanged output. Different objects (cost and counters, not help vs ownership).
