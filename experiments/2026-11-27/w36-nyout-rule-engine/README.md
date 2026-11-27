# w36-nyout-rule-engine

A deterministic Nyout (윷놀이) rule engine taken from an opened public-domain 1895 description. Throws, horse choices and policy flags are listed in a JSON fixture. The engine writes a transcript and a PASS/FAIL table. Arm A follows the legal routes. Arm B, on the overrun sessions, takes a radius without first stopping on B or C; that play is FAIL.

This is a method sketch of Culin 1895, chapter LXX. It is not a modern 윷놀이 variant, not a gambling simulation, and not a reading of any later ruleset.

## Source

Stewart Culin, *Korean Games with Notes on the Corresponding Games of China and Japan*, Philadelphia: University of Pennsylvania, 1895, chapter LXX. Opened Internet Archive item [`koreangameswith00culigoog`](https://archive.org/details/koreangameswith00culigoog). Author dates in the item metadata: 1858–1929.

Public-domain case: published in the United States in 1895; the author died in 1929; the Internet Archive metadata field `possible-copyright-status` is `NOT_IN_COPYRIGHT` (region US). The title verso of the opened book reads "Copyright, 1895, by Stewart Culin ALL RIGHTS RESERVED"; that notice has expired. The digitization preface in the opened scan is Google's preface stating that the book has entered the public domain.

Fig. 75, Fig. 76 and Plate XV were not used as a source of coordinates, rules or images, and are not copied here.

## Quotes from the opened chapter (printed pp. 66–70)

OCR artifacts are left as they appear and flagged.

- “The most popular game in Korea at the present day is known as Nyout-nol'ki or " Nyout playing."”
- “The diagram, called nyout-hpan or " nyout board," consists of twenty-nine round marks, twenty of which are arranged at equal distances in a circle, with an interior cross of nine marks, as shown in Fig. 75.” (the opened text hyphenates "twenty-nine" across a line break)
- Throw table, as printed: “4 white sides up, called nyout, 4.” “4 black sides up, called mo, 5.” “3 white sides up, called kel, 3.” “2 white sides up, called kdi, 2.” “I white side up, called to, i.”
- “A throw of nyout or mo entitles the player to another throw, which he makes before moving his piece.”
- “A throw of one more than enough to carry a man to that point is necessary to take it out, but if there is an excess, it does not matter.”
- “In opening the game a throw of mo, or five, takes the player to the spot marked B, and he returns toward the goal by the radius BE. If, on the contrary, the player throws less than five, and his next throw or throws do not terminate upon the mark B, he must continue around the circle, until, if he falls upon the mark C, he may return by the way of CE, EA. If he overthrows the mark C, he must continue on to D, and thence around to A, the going-out place.” (the opened text hyphenates "continue" across a line break)
- Capture, with the OCR glyph retained: the latter's piece is `" caught/'` (printed as `" caught/'` before the Korean/Chinese gloss `tjap-et-ta`) “and must be started again as at first. When a player captures an opponent's piece, it gives him another throw.”
- “he may divide the throws between two pieces.”
- “he may double up the two pieces, and thereafter take them round as one piece, but they count as two in the game.”
- “The players enter their men on the mark next on the left of that marked with the character cKut”
- Entry names, with OCR retained: “as it eftters upon the first, second, third, fourth, or fifth mark, it is spoken of as to, kdi, kel, nyout, or mo-potU-tchyet'ta.”
- On the station count, pp. 69–70: “the twenty-eight marks represent the horse-soldiers of the famous Chinese general, Hiang Yii/ with the general himself in the centre.” (OCR `Yii/` retained)

## Declared rules (engine)

- Board: 29 unique stations `r1`..`r20` (with `r5=B`, `r10=C`, `r15=D`, `r20=A`), `b1`, `b2`, `c1`, `c2`, `d1`, `d2`, `a1`, `a2`, and centre `E`. A fixture `board` field, if present, must match this station set and edge set or the run is DENY `bad_board`.
- Two sides (`p` and `q`), each with 1 or 4 horses (`horse_count`).
- Named throws only: `to`, `kai`, `kel`, `nyout`, `mo` (1, 2, 3, 4, 5). The fixture name `kai` is a romanization of the OCR “kdi”, not a silent emendation of the quote. Any other token, including `backdo`, `kdi`, upper-case variants, integers, booleans or null, is DENY `bad_throw`.
- Entry counts as step 1: an opening `to` lands on `r1`; an opening `mo` lands on `r5` (`B`).
- Routes to land on A / to go out: rim 20 / 21; via B 11 / 12; via C 16 / 17. Both B and C continue `E -> a1 -> a2 -> r20` (A).
- A shortcut is taken only when a move terminates on B or C. Passing B or C mid-move stays on the current path. Planted `overrun_C_no_shortcut` and `overrun_B_no_shortcut` contrast Arm A (continue on the rim) with Arm B (illegal radius; FAIL). Arm B is scoped by `overrun_mark` `B` or `C` so a path that later tests C is not diverted at B.
- Default optionality follows Culin's verbs: B is mandatory ("he returns") when a horse starts a move on `r5`; C is a policy flag `take_c_shortcut` ("he may").
- `nyout` or `mo` grants one more throw before any horse moves. Buffered throws are applied one at a time, never summed, and may be assigned to different horses of the same side. Planted `mo_then_kel_sequential` lands on `E` (`r5 -> b1 -> b2 -> E`), not `r8`.
- Each `nyout` or `mo` and each capture adds exactly one throw to the pending buffer. Chains are unbounded except by the fixture throw list. Exhausting that list ends the session as `throws_exhausted`.
- Landing exactly on A (`r20`) stays on the board (`tied`). One step or more past A goes out; excess past that point does not matter.
- Joining a stack is a policy flag `join_stack` (Culin "may"). A stack moves as one unit and counts as N horses at exit. A captured stack returns to start as a whole.
- Bad input is DENY: exit 2, empty stdout, one stderr line `DENY <code>: <detail>`. The fixture size cap is 32768 bytes (`too_large`). A bounded nesting walk (`MAX_NESTING_DEPTH = 16`) returns `too_deep` and never a `RecursionError`. Integers are checked with `type(x) is int`, so a boolean is `bad_type`. Duplicate JSON keys, unknown fields, a `seed` or `random` field, a horse count other than 1 or 4, a move that names an absent horse, and a move that spends one side's pending buffer on the other side's horse (`wrong_side`) are DENY.
- `on_expiry` must be one of `DENY`, `SAFE_FALLBACK`, `ESCALATE`, `HOLD`. Any other string, including `PASS` or `IGNORE`, is DENY `bad_on_expiry`. The mutant runner uses `TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}`.
- The fixture declares the expected Arm A (and, where present, Arm B) table before the run. The gate is PASS (exit 0) only if the observed table equals it exactly; otherwise exit 1.

## Limits

Culin 1895 wording and engine conventions are listed separately.

From Culin 1895 (opened text): the 29-station board ("twenty-nine round marks" plus the pp. 69–70 confirmation that twenty-eight marks stand around the general in the centre); the five throws; entry on the mark next on the left of A; "he returns" by BE after a mo to B; "he may return" by CE, EA after landing on C; overrun of C continues to D and around to A; a throw of nyout or mo is made, then another throw, before moving; landing on an opponent sends that piece back "as at first" and grants another throw; exact arrival at A is not yet out; a player "may divide the throws between two pieces"; a player "may double up" two of his own pieces, after which they travel as one and count as two; two players use one or four horses.

Declared engine conventions (not claimed as fully specified in Culin):

- C1: `d1` and `d2` exist as named marks on the cross, but they are unreachable under the routes Culin describes (no D-radius play). This is pinned by a reachability test (27 of 29 stations are playable).
- C3: after E, both the B path and the C path continue `a1 -> a2 -> r20`. This is a declared reading of "toward the goal" and of "CE, EA".
- C5: B is mandatory; C is selected by `take_c_shortcut`. Both values of that flag are tested.
- C6: buffered throws apply one by one; a sum of the buffer is a mutant that tests kill.
- C7: each nyout, mo, or capture adds one throw to the buffer; chains stop when the fixture list is exhausted (`throws_exhausted`).
- C9: a captured stack returns to start as a whole. Culin does not say whether a stacked group is captured together; this convention is UNVERIFIED in Culin and is tested as a declared rule.
- C10: the engine name `kai` romanizes OCR `"kdi"`.
- Turns: one pending buffer (a throw plus its nyout, mo and capture bonuses) belongs to the side whose horse it moves first; spending it on the other side is DENY `wrong_side`. Which side throws next is scripted by the fixture; strict alternation between sides is not enforced.

Fig. 75, Fig. 76 and Plate XV were not used. Later folk or tournament rules (including Back-Do) were not opened and are not implemented.

## Files and how to run

- `nyout.py`: module and CLI (`python3 -B nyout.py fixtures/main.json`).
- `test_nyout.py`: unit tests (`python3 -B -m unittest -v test_nyout.py`). 37 tests. No test reads `nyout.py` as source text.
- `demo.py`: prints the report for `fixtures/main.json` (`python3 -B demo.py`).
- `mutants.py`: ten in-memory behaviour mutants, each run in a child `python3 -B` (`python3 -B mutants.py`). Tally: 10 killed, 0 crash, 0 timeout, 0 survived. A crash or timeout is never counted as a kill. `TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}`.
- `fixtures/main.json`: 21 planted sessions, including Arm A / Arm B contrasts on the two overrun sessions.
- `fixtures/bad/`: 25 bad fixtures covering the DENY codes above.
- `SHA256SUMS`: sha256 of every other file here; run `sha256sum -c SHA256SUMS` inside this folder.
- Stdlib only. No network, no install step, no runtime chance source, no wall-clock metric.

Demo stdout sha256, recorded from two identical runs (exit 0):

`ad97b7a6728f6e75ab706f5c738b9f5f9166ae1f2cb0e58ece87e08aafc48584`
