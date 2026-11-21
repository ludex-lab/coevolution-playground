# w29-play-then-craft

A small, deterministic play-then-revise loop. Scripted players at three declared levels play a tiny two-path game and
each episode leaves a report. A crafter reads only those reports and may change only declared integer knobs, inside
their range, toward a target band that was declared before any episode. A fresh evaluation with new players, who share
no memory with the crafting episodes, scores the revised game against the band. A `noop` control and an `overtune`
control are scored against the same band.

## Credit and licence

Method idea: *PlayCraft: Designing Engaging Games from Agent Play Experience*, arXiv 2611.26624 (v1, 19 Nov 2026,
Weihao Cheng as listed on the abstract page). Only the abstract page was read here; the full paper was not read.
Licence line: arXiv nonexclusive-distrib 1.0; method only; no code listed; none copied.
The README, the evidence file and the code paraphrase the idea; nothing is copied from the abstract.

## What this does not claim (read this first)

- The improvement in `fixtures/main.json` is fixture-authored by construction: the two knobs, their ranges, the player
  thresholds and the band were chosen so that the loop works. The result shows that the loop, its refusals and its
  controls behave as designed. It never claims the revised game is engaging.
- Every paper number and claim is UNVERIFIED and sits only under `on_unmeasured` in `evidence.json`: the learning gain
  and slope results, "most games", the three intelligence settings, the baseline comparison, and "engaging" itself.
- The paper's vision-based player is UNVERIFIED and is not built here: there is no screen and no vision player. The
  players are small pure functions. The paper's player reflections are not built either; reports here are structured
  integers and short labels.
- No model is called. No network, no paid API, no randomness, no clock, no files written.

## Files

| File | What it holds |
|---|---|
| `play_craft.py` | loader, game, players, crafters, rules, loop, metrics, command line |
| `test_play_craft.py` | unittest suite |
| `demo.py` | prints one session transcript, built by the code from `fixtures/main.json` |
| `mutants.py` | breaks the module one way at a time and requires the suite to fail every time |
| `evidence.json` | what was measured here, and the UNVERIFIED paper claims under `on_unmeasured` |
| `fixtures/main.json` | the frozen scenario |
| `fixtures/*.json` (valid) | hold, escalate, Korean (NFC and NFD) and edge scenarios |
| `fixtures/bad_*.json` | malformed inputs for the standing probe battery |

Run with the system interpreter only: `python3 -B play_craft.py fixtures/main.json`, `python3 -B demo.py`,
`python3 -B -m unittest discover -s . -p 'test_*.py'`, `python3 -B mutants.py`. Standard library only (`fractions`,
`json`, `re`, `sys`, `unicodedata`; the tools add `unittest`, `os`, and a few others).

## The game and the players

One two-path game. The long path costs `long_cost` steps, the short path costs `short_cost` steps. An episode succeeds
(a clear) when the chosen path's cost is within the `reserve` knob (a step budget). A declared integer `step_cap`
bounds the steps one episode may use.

Two integer knobs, each declared as `{min, max, step, initial}` with a role:

- a `cue` knob (`signpost` in the main fixture) that makes the short path easier to notice;
- a `reserve` knob (`budget` in the main fixture) that sets the step budget.

Three declared levels (`novice`, `skilled`, `expert` in the main fixture) differ only in two integer thresholds:
`patience` (long-path failures before switching) and `sign_weight` (how much one cue point lowers that patience).
A player is a pure function of the game, the knobs and its own memory of earlier episodes (a count of long-path
failures). A fresh player has empty memory. There is no randomness.

Each episode produces a report object: level, episode number, decisions, outcome (`clear`, `fail` or `capped`), steps,
progress as two integers, and a capped flag.

## The crafter

The crafter's view holds exactly four things: the report objects, the declared knob table (id, role, min, max, step),
the current knob values, and the declared target. It never sees the game, the player thresholds, the fixture's
expectations or the players' memory. The shipped `ladder` crafter reads the target level's reports and applies a fixed
ordered ladder over declared knobs by role, with no hard-coded answer:

- the first clear is inside the band: no change;
- too hard, and the short path was reached but still failed: raise the `reserve` knob one step, else the `cue` knob;
- too hard otherwise: raise the `cue` knob one step, else the `reserve` knob;
- too easy: lower the `cue` knob one step, else the `reserve` knob;
- nothing left to move: `ladder_exhausted`, no change.

The crafter returns a proposal `{target, changes, why}`. The loop applies the rules below before anything changes.
The registry also holds `noop` and `overtune` (all knobs to their maximum) as controls, and three rule-breakers
(`edits_target`, `wild_knob`, `out_of_range`) used to show the refusals.

## Rules

- The target is declared in the fixture before any episode and stored as a private copy. A proposal whose target is
  not equal to it (compared with type-aware equality, so a boolean is not the number one), or has none, is
  `DENY target_not_declared`.
- A change to an undeclared knob is `DENY knob_undeclared`; a value that is not an integer is `DENY knob_bad_value`;
  outside `[min, max]` is `DENY knob_out_of_range`; off the step grid is `DENY knob_off_step`.
- Every cap declares what happens at expiry. `on_expiry` is one of `HOLD`, `ESCALATE`, `DENY`; any other value
  or a missing one is a loader error.
  - A capped episode or an episode with no report is never a clear. It licenses no craft: the round stops, the
    parameters stay as they were, and the run ends with `HOLD` or `ESCALATE`, or with `DENY episode_held` when the
    fixture says `DENY`.
  - If the round cap (`max_rounds`) runs out before the revision settles, the same `on_expiry` decides
    (`DENY rounds_exhausted` for `DENY`).
- Malformed input: exit 2, empty stdout, exactly one stderr line `ERROR <code>: <detail>`, no traceback. A refusal
  uses the same shape with a `DENY ...` code. A valid fixture exits 0 and prints one JSON report.

## Fresh evaluation

After the last round the loop plays the revised game with new player instances (empty memory) and scores the target
level's first clear against the band: `too_hard` (no clear, or a clear after the band), `in_band`, or `too_easy`
(a clear before the band). `noop` and `overtune` get the same fresh evaluation against the same declared band, so
the real crafter passes only by landing inside it: `noop` misses on the hard side, `overtune` on the easy side. The
report also shows, for contrast only, what the target level would have shown if the crafting memory had been carried
into the evaluation (`leaky_contrast`); the loop never does that. The test suite and a mutant that carries memory over
both check it.

## Metrics (this sketch's own definitions, not the paper's)

All metrics are exact `fractions.Fraction` values over the clear/not-clear sequence of one level's episodes:

- clear-rate curve: cumulative clears divided by episodes so far;
- learning gain: the clear rate over the last third of the episodes minus the clear rate over the first third
  (a third is `episodes // 3`, at least one episode);
- learning slope: the exact least-squares slope of the 0/1 clear sequence against the episode number.

In the main fixture the novice goes from no clear in six episodes to a first clear at episode 4 (gain 1, slope 9/35)
after two knob changes. That movement is the fixture's design, see the top of this file.

## Probe battery (all handled)

The standing battery is stored under `fixtures/bad_*.json` and every file exits 2 with empty stdout and one stderr
line. Classes covered: boolean where an integer is required (`True` is not 1); huge int (309 and 5000 digits);
deep nesting (arrays and objects, up to the size cap and beyond it); lone surrogate in ids and labels; duplicate JSON
keys (flat and nested); NaN, Infinity and floats where integers are required; control, C1, ESC, zero-width, bidi, NBSP,
U+3000, U+2028, U+3164, U+2800, Hangul fillers, private-use and unassigned characters; NFC and NFD duplicate ids; a
size cap of 200000 bytes; invalid UTF-8, a BOM and UTF-16; empty input, trailing comma, trailing garbage, single quotes;
knob at exactly `min` and `max` (accepted), `min > max`, negative or zero step, empty or too-few episodes, an episode
count over the cap, step cap 0, a band with `lo > hi`, a target for an undeclared level, wrong counts of knobs and
levels, and `on_expiry` values outside the three. Korean ids and labels, including NFD Hangul, are accepted.

## How a Ludex village would use it

This is a use sketch only; the village pages were not opened for this experiment. A village that runs a small daily
quiz or path puzzle could treat one number, such as the hint shown on a hard step, as the knob. Naru (나루, the
ferry crossing) could tune how visible the short way across is; Yeoul (여울, the shoals) could tune the step
budget of a repeated challenge; Batang (바탕, the ground) could tune how much help a first visit gets. In each case the
village would declare the band first (for example, a newcomer's first clear in episodes 3 to 4), run scripted
players or recorded play reports through the loop, and accept only a revision that passes the rules above. A
`HOLD` means a human looks at the capped or silent episode before anything is tuned. None of this has been tried on a
real village.

## Neighbours on main (C8 disclosure)

- `w28-audit-contract` also pre-declares before scoring: its contract fixes what is claimed before any result is
  read. This experiment pre-declares the target band the same way, and it repeats that experiment's disclosure that
  the gain is fixture-authored.
- `mb-answerability-pairs` also scores an abstain or hold path: a case with no safe answer is scored as an abstain.
  Here the held episode is the analogue and is scored as a hold with no craft licensed.
- This experiment is the first game or play-design loop on main. Neither neighbour plays or revises a game.

## Demo transcript

`demo.py` prints the whole session from the code: target declaration, three crafting rounds, the revised
file diff, the fresh evaluation per level, both controls, the leaky contrast, the refusals and the hold cases. It is
labelled as produced by the code and is byte-identical across runs. sha256 of its output:
1aefef5f59b77fe536fa651ae510db985a339ae238995d660cd8d16a3fe23ad7

## Limits

Two knobs and three levels only; one tiny game; scripted players; the ladder is one fixed policy. The shipped numbers
are not a measurement of anything outside this fixture.
