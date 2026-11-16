# mb-owned-exceptions

A local exception is not a rule change: when a party holds private evidence
that a shared, published rule is wrong for its own cases, it can carry an
owned, typed, gated and withdrawable exception that changes its own
decisions and no one else's, and that comes off again bit for bit.
**Soft** method sketch, not a reproduction, of
[arXiv 2611.15917](https://arxiv.org/abs/2611.15917), "Owned Edits to a
Shared Decision Rule: Learning Private Exceptions as Typed, Gated,
Withdrawable Weight Edits" (John J. O'Hare; v1, submitted 11 Nov 2026;
primary category cs.LG, cross-listed cs.CY).

Paper licence: CC0 1.0 (https://creativecommons.org/publicdomain/zero/1.0/,
as linked on the abs page). No method repository exists: the abs page links
none, and the paper says the two other public repositories of the author's
group contain neither the compiler, the typed learner nor the acceptance
test. Clean-room, method-borrow only (see `NOTICE`).

This is a method sketch, not law, policy or a team rule. Status: Soft (a
Morning Brief candidate). The world is synthetic and hand-built: every
rule, truth, record and label is a fixture label. The paper's figures are
`on_unmeasured` here (`paper_results()` says so); they live only in
`paper_evidence.json`, quoted verbatim from the abstract and marked
UNVERIFIED. Python 3 standard library only: no network, no model, no paid
API, no neural network training, no voting or ensemble, no files written,
no clock. There is no timeout or expiry anywhere, so no `on_expiry` is
declared.

## What it does

**Domain and frozen rule.** An item is `(subject, cls, q1, q2)` with four
subjects `s0..s3`, three classes `a, b, c` and `q1, q2` in `0..7`: 768
items, so every "for every item" claim is checked exhaustively. The
published rule accepts (1) iff `q1 <= 5 and q2 <= 5` (432 items). It is a
module constant (`BASE_RULE`, compiled once into `BASE_UNITS`) and is never
written to; its digest is pinned in the tests.

**Owners.** Four parties `p0..p3`; party `pK` owns subject `sK` and one
reserved unit.

**Typed declarations.** A declaration names four values and nothing else:
`subject`, `scope` (`all`, `a`, `b` or `c`), `form` and `size`. Every form
tightens the rule inside the scope (the decision becomes
`rule AND NOT declaration`):

| form | size | rejects in scope when |
|---|---|---|
| `q1_margin` | 1, 2, 3 | `q1 > 5 - size` |
| `q2_margin` | 1, 2, 3 | `q2 > 5 - size` |
| `sum_cap` | 4 to 9 | `q1 + q2 > size` |

So each owner's typed space `H` has 4 x 12 = 48 declarations; a declaration
discloses at most log2(48) = 5.585 bits. No two declarations of a subject
change the same set of items, so the canonical form (least-index
declaration with the same behaviour) is the declaration itself (tested). A
relaxation (accepting something the rule rejects) is not in the typed space
and is `config_error`.

**Evidence gate.** For a declaration and a party's records, `a` counts
records the declaration decides correctly where the rule did not, `b` the
reverse, and `T = a - b`. The gate passes iff `T >= max(5, c(n))`, where
`n` is the number of records and `c(n)` is the least `c >= 1` with
`|H| * P[Bin(n, 1/20) >= c] <= 1/20`, computed exactly with fractions. The
`|H|` factor is a union bound over the 48 candidates the learner searched,
so the gate accounts for picking the best of many (selection-aware); it is
this sketch's own deterministic stand-in for the paper's Monte Carlo
p-value. `c(30) = 7`; `c(n)` is undefined (the gate cannot pass) for
`n <= 2`.

**Learner.** `learn(owner, records)` scores every declaration in its own
typed space, ranks by `T`, then by the smallest changed region, then by
index, and proposes the best one only if the gate passes. With
`gated=False` it proposes the best positive candidate anyway (the "search
without the gate" arm).

**Acceptance body.** `submit(state, submission)` takes
`{"owner", "declaration", "claimed": {"a", "b"}, "evidence": [records]}`
and checks, in this order:

| check | outcome when it fails |
|---|---|
| plain `dict`, exact-`str` keys (checked before any lookup), exact key set, exact types (`int` not `bool`, no `float` so no NaN or inf, no subclasses), values in range, form and scope in the typed space | `config_error` with a reason such as `size_not_int`, `declaration_key_not_str`, `form_unknown`, `submission_keys` |
| owner is known | `REFUSE unknown_owner` |
| the declaration's subject is the owner's | `REFUSE not_owner` |
| `claimed` and `evidence` both present | `REFUSE ungated` |
| `(a, b)` re-computed from the evidence equals `claimed` | `REFUSE gate_unreproduced` |
| the gate passes on the evidence | `REFUSE gate_failed` |
| the owner has no live exception (one reserved unit each) | `REFUSE slot_taken` |
| exhaustive check: the new decisions equal the old ones with the declared region rejected, nothing else (`behaviour_ok`) | `REFUSE interference` (never reached by a typed declaration; tested on a forged state) |

All input is copied into a validated tuple snapshot first; nothing is read
from the caller's objects afterwards. Weights sent with a declaration are a
`config_error` (unknown key): the body derives the patch itself from the
declaration (`compile_patch`) and adds it to the owner's reserved unit.
Every refusal returns the very same state object.

**Withdrawal.** `withdraw(state, actor, owner)`: only the owner withdraws
its own live exception (`REFUSE not_owner`, `unknown_owner`,
`no_live_exception` otherwise). It subtracts the re-derived patch from the
reserved unit, so the parameters return exactly.

**Two decision forms.** The *compiled* form holds integer ReLU-style units:
two frozen base units (`relu(q1 - 5)`, `relu(q2 - 5)`) and one reserved
unit per owner, gated on the owner's subject (and scope) by a weight of
100; an item is accepted iff `1 - sum(units) >= 1`. The *table* form is the
rule plus a table of owned rows, each applied only to its owner's subject.
The paper concedes that on a rule-only base a table of owned exceptions
makes the same decisions; here that is the stated baseline, and the tests
check the two forms agree on every item of every reached state.

## Invariants and how they are tested

| # | invariant | evidence |
|---|---|---|
| 1 | an exception affects only its owner's cases | for every admission in the sweep (129) the decisions outside the owner's block are byte-identical before and after, and inside it equal `rule AND NOT region`; for every live exception of every reached state (634 checks) the decisions with and without it are byte-identical outside the owner's block; all 192 single-row states agree across compiled, table and oracle |
| 2 | withdrawal restores exact prior outcomes | every withdrawal in the sweep (49) yields a state equal (parameters, live rows, digest) to one rebuilt from scratch with the remaining rows in a shuffled order; 11 add-then-withdraw pairs return the exact earlier state; 30 interleaved trials (all four owners, withdraw 1 to 3, re-admit in another order) return the full state bit for bit and, after all withdrawals, the pinned empty-parameter digest |
| 3 | ungated, unowned and mistyped exceptions are rejected | 41 hand cases (3 ADMIT, 1 WITHDRAWN, 14 REFUSE, 23 `config_error`); a 7,680-submission space (4 gate variants x 192 declarations x 5 owners incl. an unknown one x 2 start states) agrees with the oracle on every verdict |
| 4 | the base rule is never mutated | base digest pinned and re-checked before and after all 400 sweep steps and all 41 cases; `state.base` is the module's `BASE_UNITS` object throughout |

Permutation and property sweep (deterministic, seeded): 40 runs x 10 steps
of random add, owner withdraw, wrong-party withdraw and unowned submit over
all four owners (seed 1116); and 30 seeded live sets of 2 to 4 owners
admitted in every order (302 orders) giving identical states and
parameter digests (seed 2611).

## Fixture world and demo

Each party holds 30 records from its own block (seed 20261117, label noise
1/20): `p0`, `p2` from the rule-accepted items of their block, `p1` from
the rule-accepted class `c` items, `p3` from its whole block. Hidden truths:
`p0` tightens `s0/all/q1_margin=2`, `p1` tightens `s1/c/q2_margin=2`, `p2`
follows the rule, `p3` would relax the rule (`q1 = 6` accepted in class
`a`), which no typed declaration can express.

`python3 -B demo.py` prints:

```
frozen rule: accept iff q1 <= 5 and q2 <= 5; 4 subjects x 3 classes x q1,q2 in 0..7 = 768 items
typed space per owner |H| = 48 (discloses at most log2(48) = 5.585 bits); gate: T = a - b >= max(5, c(n)), c(30) = 7

owner | hidden truth | gated proposal | a-b | verdict | own block correct of 192 (rule -> now) | other blocks changed | search without the gate
--- | --- | --- | --- | --- | --- | --- | ---
p0 | tighten s0/all/q1_margin=2 | s0/all/q1_margin=2 | 11-0 | ADMIT admitted | 156 -> 192 | 0 | s0/all/q1_margin=2 ADMIT admitted
p1 | tighten s1/c/q2_margin=2 | s1/c/q2_margin=2 | 7-0 | ADMIT admitted | 180 -> 192 | 0 | s1/c/q2_margin=2 ADMIT admitted
p2 | rule | - | - | no proposal | 192 -> 192 | 0 | s2/c/q2_margin=2 REFUSE gate_failed
p3 | relax a q1=6 | - | - | no proposal | 186 -> 186 | 0 | no proposal

table of owned rows == compiled units on all 768 items: True
p0's declaration written into the shared rule instead: 108 decisions change outside s0; as an owned exception: 0
p0 withdraws: WITHDRAWN; state equals the one where p0 never submitted: True
base rule digest unchanged through every step: True
paper figures: on_unmeasured
```

`p1`'s records come only from class `c`, so `scope=all` and `scope=c` score
the same on them; the narrowest-region tie-break picks `c`. Writing `p0`'s
declaration into the shared rule instead of an owned row changes 108
decisions in other parties' blocks.

## Oracle

`oracle.py` is an independent reference written from this README's
specification. It imports only `fractions`, shares no function name with
the module, holds no weights (decisions are the rule plus row predicates),
and builds the binomial mass step by step instead of using `comb`.
Agreement: all 41 cases; all 7,680 submissions in the submission space;
all 400 sweep verdicts and the decisions of all 400 sweep states (768 items
each); the decisions of all 192 single-row states and of every permutation
reference state; `gate_stats` on 768 (owner records x declaration) pairs;
`c(n)` for `n = 0..120`.

## Mutants

`python3 -B mutants.py` patches one snippet at a time (code), the fixture
world in memory (world) or one test helper (harness), and re-runs the
suite: 84 mutants, all killed: 66 code (54 in the module:
validation, rule and typed-space semantics, compiled units, digests, gate,
learner, acceptance and withdrawal; 12 in the oracle), 10 world (records,
truths, cases, evidence helper, subclass helper) and 8 harness (sweep,
banned-word scan, oracle helper, block mask, rebuild, declaration list,
file list, case runner). A mutant counts as killed when at least one test
fails or errors. Two first-run survivors (a `dict` subclass accepted below
the submission level, the oracle ignoring the gate minimum) led to two
added tests.

## Run

```
python3 -B -m unittest
python3 -B mutants.py
python3 -B demo.py
```

## Files

- `owned_exceptions.py`: validation and snapshot, typed space, `region()`, `canonical()`, `compile_patch()`, compiled and table decisions, digests, gate, `learn()`, `submit()`, `behaviour_ok()`, `withdraw()`, baselines, `paper_results()`.
- `oracle.py`: independent spec oracle.
- `fixtures.py`: truths, seeded records, `evidence_for()`, 41 hand cases.
- `demo.py`: the table above.
- `test_owned_exceptions.py`: unittest suite (the day-README test skips outside the `experiments/2026-11-16/` layout).
- `mutants.py`: mutant runner.
- `paper_evidence.json`: the abstract, nine quoted claims with offsets, UNVERIFIED and `on_unmeasured`.
- `NOTICE`: credit, licence and clean-room statement.

## Differentiation

Read on Origin main: `w17-memory-scope` (2026-11-08) holds memory writes and
reads to a declared scope; `2026-11-04` #28 (revocation outcome contract)
and #7 (withdrawable ask) are markdown design notes with no code. New here:
the object is a shared decision rule that stays frozen while each party
carries one typed, evidence-gated exception confined to its own subject,
with exact withdrawal and non-interference checked exhaustively over the
whole domain, and the table form and the compiled form shown to decide
identically.

## Limits

- Toy: one rule, 768 items, four owners, one slot per owner, three
  tightening forms. The paper's compiled ReLU network, its trained-base
  variant, its selection-aware Monte Carlo p-value, its reference-set test
  and its disclosure and hidden-capacity measurements are not built.
- Non-interference and exact withdrawal hold by construction here too
  (disjoint reserved units, integer parameters); the tests confirm the
  construction, they do not prove it for other encodings.
- The acceptance body re-runs the gate on the submitted records, so the
  records are shown to it; the paper's parties hold their records privately and
  submit only the statistic. This sketch does not model that privacy.
- Tightening only: a truth that needs a relaxation (`p3`) is not
  expressible, and every typed tightening of `p3`'s block loses an item.
- The gate's noise rate and level are stated constants, and `GATE_MIN = 5`
  is this sketch's choice; with few records the gate declines.
- Over-broad scope within the owner's own block is possible when the
  records do not separate scopes; the tie-break picks the narrowest region,
  which is a choice, not a guarantee.
- Synthetic records from one seed; no accuracy claim is made beyond the
  fixture counts, and none is comparable with the paper's figures.
