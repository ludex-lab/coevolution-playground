# mb-memory-preview-rules

A memory rule says when an assistant may reuse something it remembers. An editor can confirm a
rule by showing a **preview**: one use the rule permits and one use it blocks. This sketch asks
what such a preview lets a person infer. It enumerates every rule from a small typed vocabulary
that is compatible with a preview, on a tiny fictional fixture, and shows that the usual
"same task permitted / one-off blocked" preview fits three rules, while a preview built from
uses in **other tasks** (a transfer preview) pins down the scope.

Clean-room method sketch of the idea in [arXiv 2611.17874](https://arxiv.org/abs/2611.17874)
(Tonni and Shahid); not a reproduction. Python 3 standard library and `unittest` only. No
network, clock, randomness, model, survey or UI. No upstream code was copied, fetched or run, and
no upstream result is claimed: every count below is computed from `fixtures/memory_rules.json`
by `preview_rules.py`. External figures and links live only in `evidence.json` (UNVERIFIED).

## Run

```
python3 -B -m unittest                       # 33 tests
python3 -B demo.py                           # deterministic report + done-when lines
python3 -B mutants.py                        # mutation self-check: killed 79/79, exit 0
python3 -B preview_rules.py fixtures/memory_rules.json
python3 -B preview_rules.py fixtures/memory_rules.json --permitted u1 --blocked u5
```

Exit 0 with a report. A missing, unreadable or malformed fixture, or a bad command line, prints
`DENY <code>: <detail>` on stderr, nothing on stdout, and exits 2.

## Model

- **Rule** = `(scope, kinds)`. Scope: `same_task` (only the task the event was remembered in),
  `same_topic` (any task with the same topic), `any_task`. Kinds: `preference_only`,
  `one_off_only`, `any_kind`. The vocabulary is the product of the listed values (here 3 x 3 = 9).
- **Use** = an event reused in a task for an audience. Every rule in this vocabulary covers the
  person's own requests only (`audience=self`); a use for `others` is blocked by every rule.
- **Preview** = `(permitted use, blocked use)`. A rule is compatible when it permits the first and
  blocks the second. `compatible()` returns them in vocabulary order.
- **Transfer use** = the event reused in a task other than the one it was remembered in.
- **Verdict** for the rule the person chose: `IDENTIFIED` (exactly that rule fits), `AMBIGUOUS`
  (it fits, and so do others), `CONFLICT` (it does not fit).

## Fixture (fictional)

Two events: `veg` (Mira eats vegetarian; preference; remembered in `meal_planning`, topic food)
and `seat` (one aisle seat on a late train; one-off; remembered in `trip_booking`, topic travel).
Four tasks: `meal_planning` and `grocery_list` (food), `trip_booking` (travel), `gift_ideas`
(shopping). Eight uses `u1`..`u8`. Intended rule: `same_topic/preference_only` ("use my food
preferences for food tasks, nothing else"). Previews: `weak` = (`u1` meal planning, `u5` the seat
again) and `transfer` = (`u2` grocery list, `u3` train meal).

## Results (computed from the fixture)

| question | result |
|---|---|
| rules in the vocabulary | 9 |
| uses the intended rule permits / blocks | 2 (`u1`, `u2`) / 6 |
| possible previews of the intended rule | 12 |
| previews whose blocked use no rule permits (`u7`, `u8`, sharing with others) | 4 of 12 |
| previews that identify the intended rule | **0 of 12** |
| compatible-set sizes over the 12 previews | 2:3, 3:2, 4:4, 5:1, 6:2 |
| `weak` preview (u1 permit, u5 block) | **3 rules, 3 scopes**: `same_task`, `same_topic`, `any_task` (all `preference_only`) -> AMBIGUOUS |
| `transfer` preview (u2 permit, u3 block) | 2 rules, **1 scope** (`same_topic`; kinds open) -> AMBIGUOUS |
| both previews together | 1 rule -> IDENTIFIED |
| probes after `weak` that separate scopes | `u2`, `u3`, `u4` (all transfer uses) |
| probes after `weak` that leave all 3 scopes open | `u6` (a transfer of the one-off), `u7`, `u8` |
| smallest probe sets that identify the intended rule | 3 uses, 2 sets: `u2,u3,u5` and `u2,u4,u5` |
| rule pairs no fixture use can tell apart | 1: `same_task/one_off_only` and `same_topic/one_off_only` |

Done-when mapping:

- (a) `test_every_ordered_pair_matches_brute_force` checks `compatible()` on all 56 ordered pairs
  of distinct uses against a hand-listed table of which uses each of the 9 rules permits, and
  `test_intended_pairs_and_their_sets` lists the 12 intended previews with their set sizes.
- (b) the `weak` preview fits 3 rules and does not identify the intended one.
- (c) the `transfer` preview leaves one scope where `weak` leaves three; after `weak`, the transfer
  probe `u2` rules out `same_task` and `u3` rules out `any_task`, while `u7` and `u8` change nothing.
  Not every transfer use helps: `u6` reuses the one-off event, which every remaining rule blocks.
- (d) every number above is printed by `demo.py` and asserted by the tests.
- (e) tests and the demo command are listed under Run.

## Input checks

The fixture is strict JSON with exactly the documented keys at every level (unknown or missing
key: DENY). Keys and values must be exactly `str`, `int`, `list` or `dict` (no subclasses, no
`bool` for an int). `NaN`, `Infinity`, any fractional number, duplicate keys, a byte order mark,
non-UTF-8 bytes and trailing data are DENY. Ids are ASCII `[a-z][a-z0-9_]{0,31}`; free text must
be NFC, unpadded, at most 200 characters, with no control, format (zero-width), private-use,
unassigned or line/paragraph-separator characters. Ids must be unique, references must resolve,
two uses may not repeat the same event, task and audience, the intended rule must be in the
vocabulary, and every preview must be what the intended rule does (its permitted use permitted,
its blocked use blocked, not the same use twice). Nothing is skipped: either the whole fixture
validates or the run is DENY. The validated fixture is a fresh snapshot; later changes to the
input object do not affect results.

There is no timeout or expiry anywhere, so no `on_expiry` is declared.

## For a village caretaker saving memory rules

- A confirmed preview is not proof of the rule. "I clicked confirm" on one permitted and one
  blocked example says only that the saved rule is one of the compatible ones; here that is 3 of 9.
- Preview more than one pair, and choose the second pair to split what the first left open.
  Run `preview_rules.py ... --permitted A --blocked B` and save as confirmed only on `IDENTIFIED`.
- Add a transfer probe: one use of the same remembered fact in a different task (the grocery
  list, the train ticket). That is the question scope actually turns on.
- Do not spend a preview on a blocked use that no rule permits (sharing with others here); it
  tells the person nothing about the rule.
- When two rules can never be told apart on the uses at hand, say so instead of asking again.

## Limits

- One tiny fictional fixture and a 9-rule vocabulary of this sketch's own design; no claim beyond
  these counts, and none comparable with the paper's figures.
- No people were asked anything; whether better previews help people is not tested here.
- The optional one-off tie case from the paper's description is not modelled.
- `consistent()` and `smallest_probe_sets()` assume the person answers every probe exactly as the
  intended rule would.
