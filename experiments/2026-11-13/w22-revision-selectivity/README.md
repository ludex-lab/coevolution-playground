# w22-revision-selectivity

Prestige is not selectivity: a disagreement-driven revision is judged by
which initial answers it reverses, and an expert label on the same argument
must not change the decision. **Top method sketch, not a reproduction**, of
[arXiv 2611.16694](https://arxiv.org/abs/2611.16694), "When Expert
Disagreement Hurts: Prestige and Selectivity in LLM Decision Revision"
(Yupeng Tang, Mingfeng Lin; v1, submitted 12 Nov 2026; primary category
cs.AI, cross-listed cs.CL).

Paper licence: CC BY 4.0. Upstream code: MIT,
https://github.com/yupengtang/when-expert-disagreement-hurts at pin
`c511a2a033336248c916dd9b7dc9ba2d72a64bbb`, not cloned, not run, UNVERIFIED.
Its experiment path needs a paid model API key; this sketch does not take it
and needs no model at all. Clean-room, method-borrow only (see `NOTICE`).

This is a method sketch, not law, policy or a team rule. Status: Top. The
fixtures are synthetic: every correct answer, initial answer, evidence label
and recorded final answer is a hand-written fixture label. The paper's model,
decision and accuracy figures are `on_unmeasured` here
(`paper_results()` says so); they live only in `paper_evidence.json`, quoted
verbatim and marked UNVERIFIED. Standard library only: no network, no model,
no paid API, no files written.

## Design

A fixture item holds a question, a fixture-labeled `correct` answer, a
frozen `initial` answer (A or B), one `argument` text and an `evidence`
record (evidence id to the answer that evidence supports, a fixture label).
The second pass varies only the context, with the same argument text:

| context | frame shown before the same argument |
|---|---|
| `neutral` | reflect on your answer |
| `anonymous_disagree` | another agent disagrees |
| `expert_label` | a domain expert disagrees |

`render(item, context)` builds that text; only the frame line differs.

**Prestige-blind policy.** `decide(item, trial)` validates the item and the
trial and copies the fields it uses into a private snapshot. The decision
step `_decide(item, argument)` then sees only the snapshot item (with its
evidence record) and the argument text: never the context, the trial, or
any source words on the trial. It revises only when the argument cites at least one evidence id in
brackets, every cited id is on the item's record, and every cited id
supports the answer other than the initial one; otherwise it retains
(`no_citation`, `unknown_citation`, `cites_support_for_initial`). Identical
arguments therefore get identical decisions in all three contexts. The
policy is not a truth oracle: fixture `p04` cites on-record evidence for the
other answer and abandons a correct initial answer.

**Selectivity audit.** `score(items, trials, help_rule)` scores a batch of
second-pass outcomes, from the policy (`second_pass`) or from a recorded
log. For every scope it reports `n`, `reversals`, `wrong_reversals`
(reversed a wrong initial), `correct_reversals` (reversed a correct
initial), `net` and the claim. Scopes: each context alone, `neutral` on its
own, and `disagreement` = `anonymous_disagree` + `expert_label` pooled; the
neutral rows never enter the disagreement score. A paired prestige audit
lists items whose anonymous and expert outcomes differ on the same
argument.

**Help claim.** `helped` is true only when
`wrong_reversals > k * correct_reversals`, where `k` is declared in the
help rule (`{"min_wrong_per_correct": k}`, exact `int` >= 1; the fixtures
declare `k = 3`). A missing rule, an unknown key (for example an imported
bar) or a bad value is `config_error`; nothing defaults. Reversal counts
alone, or net accuracy alone, never decide the claim. The paper's own
binary selectivity bar is quoted in `paper_evidence.json` and is not
imported: `k` is a fixture choice.

**Input handling.** Every dict the caller passes (item, evidence record,
trial, help rule) must have only exact-`str` keys; this is checked by
iterating the keys before any field lookup, so no caller `__eq__` or
`__hash__` runs during validation (`*_non_str_key` otherwise). Every field
value the module uses is checked by exact type (`type(x) is str`, `int`,
`dict` or `list`); subclasses, and `bool` as the threshold, are rejected.
The validated values are copied once into private snapshots, and all later
work reads only those snapshots, never the caller's objects again. Extra
fields on a trial or an item are ignored and not copied. Every trial must
carry its item's own argument text in every context (`unpaired_argument`
otherwise) and each (item, context) pair appears at most once. `decide`,
`second_pass` and `score` do not raise: malformed input, or an internal
error, is `REJECT` / `config_error`. `render` reads only a validated
snapshot and raises `ValueError` on malformed input. There is no timeout,
so no `on_expiry` surface.

## Done-when

- (a) Expert vs anonymous, same argument: the prestige-blind policy makes
  the same decision (`DoneWhenA_PrestigeBlind`, e.g.
  `test_a_expert_vs_anonymous_same_argument_same_decision`).
- (b) A batch that mostly reverses correct initials is not reported as
  helped; a batch that mostly reverses wrong initials is; the threshold is
  declared and strict (`DoneWhenB_DeclaredThreshold`).
- (c) Neutral reflection is scored separately from disagreement
  (`DoneWhenC_NeutralSeparate`).
- (d) No LLM, no OpenRouter, no network: AST import scan for stdlib only,
  the module imports nothing, no model or network tokens in code; paper
  figures `on_unmeasured` (`DoneWhenD_NoModelNoNetwork`).
- Input handling (r2): `R2_SnapshotIsolation` runs the verifier's three
  hostile-key repros (A1: a `hurt` batch rewritten to look `helped`; A2: a
  validated initial answer rewritten so the item revises; A3: an
  expert-only evidence swap). Each is `config_error` (`trial_non_str_key`)
  and the hostile `__eq__` never runs. With the key check switched off in
  the test, the snapshot alone still gives the honest result (A1 equals
  the plain `hurt` report, A2 retains, and A3 retains in all three
  contexts).
  `R2_TypesAndPairing` covers a one-field prestige leak (ten source-like
  field names x seven values x three contexts), the same-argument check in
  every context, int / str / dict / list subclasses, non-str evidence keys,
  and an internal error that must come back as `config_error`.

`oracle.py` is an independent reference (its own code path; imports only
`re`; does not import the module). `OracleAgreement` checks module vs
oracle on every fixture item in every context and on every batch for
`k` from 1 to 8 and with each context dropped.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The quote test reads the source copies named in `paper_evidence.json` from
the directories listed in `$W22SELECT_SOURCES` (separated by the OS path
separator); it skips when that is unset.

## Results

`python3 -B fixtures.py` (W = wrong-initial reversals, C = correct-initial
reversals; these rows describe our fixtures only, not any model):

```
help rule (declared fixture threshold): helped iff wrong_reversals > 3 x correct_reversals
policy: 8 items x 3 contexts, same decision in every context for 8/8 items
batch   scope                n  rev    W    C  net  claim
policy  neutral              8    3    2    1   +1  not_helped
policy  anonymous_disagree   8    3    2    1   +1  not_helped
policy  expert_label         8    3    2    1   +1  not_helped
policy  disagreement        16    6    4    2   +2  not_helped
policy  prestige flips     none
hurt    neutral              0    0    0    0   +0  not_helped
hurt    anonymous_disagree  10    3    1    2   -1  not_helped
hurt    expert_label        10    6    1    5   -4  not_helped
hurt    disagreement        20    9    2    7   -5  not_helped
hurt    prestige flips     r03,r04,r05,r09,r10
helped  neutral              0    0    0    0   +0  not_helped
helped  anonymous_disagree  10    3    3    0   +3  helped
helped  expert_label        10    4    3    1   +2  not_helped
helped  disagreement        20    7    6    1   +5  helped
helped  prestige flips     r01,r05,r06,r07,r08,r09,r10
border  neutral              0    0    0    0   +0  not_helped
border  anonymous_disagree   8    2    2    0   +2  helped
border  expert_label         8    2    1    1   +0  not_helped
border  disagreement        16    4    3    1   +2  not_helped
border  prestige flips     r01,r05,r06,r07
mixed   neutral             12    6    6    0   +6  helped
mixed   anonymous_disagree  12    1    1    0   +1  helped
mixed   expert_label        12    1    0    1   -1  not_helped
mixed   disagreement        24    2    1    1   +0  not_helped
mixed   prestige flips     r01,r07
```

Read-outs: `hurt` has more reversals than `helped` yet only `helped` clears
the threshold; `border` gains net accuracy but sits exactly at `k * C`, so it
is not reported as helped; in `mixed` the neutral pass is helped while
disagreement is not. The prestige-blind policy shows no flips; the recorded
`hurt` log, a hypothetical label-sensitive reviser, is flagged.

`python3 -B -m unittest`: 69 tests, OK, 1 skipped (the quote source check,
which runs when `$W22SELECT_SOURCES` is set). `python3 -B mutants.py`:
killed 51/51 (code 41/41, world 8/8, harness 2/2). The done-when mutants are the first three code mutants:
flip on the expert label, report "helped" from reversal counts alone, mix
neutral into the disagreement score.

## Files

- `revision_selectivity.py`: `decide`, `second_pass`, `render`, `score`,
  `citations`, `paper_results`.
- `oracle.py`: independent reference policy and scorer.
- `fixtures.py`: declared help rule, eight policy items, four recorded
  batches, the hand-written expected table and `summary()`.
- `test_revision_selectivity.py`: unittest suite.
- `mutants.py`: code mutants (snippets of the module swapped in memory),
  world mutants (fixture changes) and harness mutants (a test helper
  swapped, e.g. the day-README row scoping). Each must make the suite fail.
- `paper_evidence.json`: the authors' claims, verbatim quotes, UNVERIFIED,
  `on_unmeasured`.
- `NOTICE`: credit, licences, pin and the clean-room statement.

## Limits

- Binary answers only; with more than two options a reversal of a wrong
  answer need not land on the correct one, and `net` would no longer equal
  W minus C.
- "Grounded" means bracketed ids that are on a fixture evidence record and
  labeled for the other answer. Mapping free text to evidence (what a model
  would have to do) is out of scope; a label can be wrong, as `p04` shows.
- The recorded batches are hand-written logs of a hypothetical reviser, not
  model outputs; the counts are small (a single wrong reversal with none
  correct clears `k = 3`, as in `mixed` / `anonymous_disagree`). No
  confidence interval, no per-model or per-protocol split.
- `k` is a fixture choice. It is not derived from initial accuracy and is
  not the paper's bar; a real deployment would have to justify its own.
- The prestige audit pairs anonymous and expert outcomes per item; it
  counts disagreements of outcome, it does not test significance.
- Stated source reliability, which the abstract also mentions, is not
  modelled.
- The exact-str key check and the snapshot guard against caller code
  running inside validation (hash-colliding keys, subclasses). They do not
  guard against another thread mutating an input while a call runs; the
  functions are meant for single-threaded use. `oracle.py` does not
  validate input; it is compared with the module on fixture inputs only.
- The hygiene scans of the shared day README read only this sketch's own
  row; the header, footer and conflict-marker checks read the whole file.
