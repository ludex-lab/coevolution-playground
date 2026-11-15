# w21-memory-admission

Local success is not admission. A lesson drawn from an episode that went
well is a candidate, not memory. This folder is a small, deterministic
method sketch of the write-admission idea in
[arXiv 2611.14326](https://arxiv.org/abs/2611.14326), "When Should Agents
Remember? Falsification-Gated Self-Evolution for LLM Agents" (Runxuan Tang,
Haoyu Gao, Yuyan Ding, Junyi Yao, Zihao Zheng, Zecheng Sheng and Liwei Hou;
v1). Paper licence: arXiv non-exclusive distribution licence,
http://arxiv.org/licenses/nonexclusive-distrib/1.0/ (not a software grant).
Method borrowed only: no code is linked from the abs page (code
UNVERIFIED) and none is ported.

This is a method sketch, not a reproduction, and not law, policy or a team
rule. It uses only the Python standard library, synthetic fixtures, no
network, no model in the loop, and writes no files. No paper numbers are
reproduced or claimed here; the authors' figures sit only in
`paper_evidence.json`, quoted verbatim and marked UNVERIFIED.

## The gate

A candidate lesson is a hypothesis
`{id, precondition, behavior_change, expected_effect, verifier}`:
`precondition` is `key=value` over task features, `behavior_change` is the
action the lesson prescribes, `verifier` names a registered check
(`action_matches_expected`), and `expected_effect` is the author's claim,
recorded but never trusted: the probes measure it.

`admit(store, request)` applies the hypothesis only in a temporary state (a
copy of the store's lessons plus the candidate) and runs three fixture
probes on that copy:

| probe | passes when |
|---|---|
| `target_transfer` | every target task succeeds on the temporary state, and at least one fails on the current store (a measured gain) |
| `falsification` | every task succeeds; the tasks are chosen so an over-general lesson acts wrongly; the candidate itself must decide at least one task (its precondition matches and the task is not already decided by a stored lesson), else the probe tested nothing |
| `archived_regression` | no archived task that succeeds on the current store fails on the temporary state; the current store must solve at least one archived task, else there is nothing to regress |

Each probe reports `n`, `base_ok`, `temp_ok`, `broken`, `matched` (tasks the
precondition matches) and `decided` (matched tasks no stored lesson decides
first, so the candidate's behavior change is what runs).

Outcomes, in the order they are checked:

| outcome | when | store |
|---|---|---|
| `config_error` | malformed input, or any internal error | unchanged |
| `expired` | a declared deadline ran out; the record carries the declared `on_expiry` | unchanged |
| `reject` (`source_episode_failed`) | the source episode itself did not succeed | unchanged |
| `on_unmeasured` | a required probe is missing or empty (`probe_not_run`); the candidate decides no falsification task, or the current store solves no archived task (`probe_vacuous`) | unchanged (fail closed) |
| `reject` (`falsification_failed`) | the falsification probe failed; never refined | unchanged |
| `commit` | all three probes passed | one lesson appended |
| `refine` | falsification passed, gain and risk are inside the fixture-declared thresholds | unchanged |
| `reject` (`archived_regression` / `transfer_failed`) | otherwise | unchanged |

Each probe is independently necessary. The fixtures hold one candidate per
failure: `H-false` passes transfer and regression but fails falsification;
`H-breaks` passes transfer and falsification but breaks an archived task;
`H-noop` passes falsification and regression but fails transfer. None of
them is committed. `H-good` passes all three, is committed, and a later task
outside every probe then sees it. Dropping any one probe from any candidate
gives `on_unmeasured` and no write.

Refine choice: tested, with fixture-declared thresholds (not left out of
scope). `refine_min_gain_pct` (int 1..100) and `refine_max_risk_pct` (int
0..100) must both be declared in every request; a missing one is a
`config_error`. Gain is the share of transfer tasks the candidate newly
solves; risk is the share of archived tasks it newly breaks. `refine`
writes nothing; it says the lesson is sound where tested but too narrow (or
too risky) to commit as written. Narrowing or widening the precondition is
left to whoever authors the next candidate; this sketch does not rewrite
hypotheses.

## Store and temporary state

The store is a `MemoryStore`: an in-memory Python list of plain-str tuples,
nothing else (no database, no file, no serialisation, no ledger). Lessons
committed earlier take precedence when several match. Probes read a fresh
list copy; only `commit` appends, once, from plain-str copies of the
hypothesis, so later edits to the caller's dict do not reach the store.
The id is claimed at commit time with a single dict.setdefault call, so a
duplicate id that slipped past the early check (for example two admits
racing on one store) is refused there with `config_error` and no write.
This is a narrow guard, not a general thread-safety claim. Seed lessons
passed to `MemoryStore(...)` are validated like a candidate hypothesis; a
malformed or duplicate seed lesson raises `ValueError`.
Tests check that the store is unchanged after `reject`, `refine`,
`on_unmeasured`, `expired` and `config_error`.

## Deadline

A request may carry `deadline: {timeout_s, on_expiry, expired}`. A timeout
without a declared `on_expiry` is a `config_error`; `on_expiry` must be
`hold`, `escalate` or `deny`. An expired deadline never commits or runs the
probes: the record holds outcome `expired` and the module's own `on_expiry`
constant, never the caller's object. There is no clock: expiry is the
caller's declared `expired` flag, and `timeout_s` is validated but not
used. A deadline without `expired` runs the probes.

## Input checks

Inputs are checked by exact type (`type(x) is str`, `dict`, `list`, `int`,
`bool`; bool is not an int threshold). A str subclass that claims to equal
everything, a dict or list subclass, a `MemoryStore` subclass, unknown
fields, a malformed precondition, an unknown verifier and a duplicate
lesson id are each a `config_error`. `admit()` does not raise: objects whose
`__eq__`, `__hash__` or `__str__` raise are rejected by type first, and any
internal error is caught and returned as `config_error`. A `config_error`
record never echoes a hypothesis id; the id is read only after validation
passes.

## Neighbours (dupe check)

- `w18-skill-assurance`: medium overlap. Both gate entry into a library on
  offline checks. Delta here: a separate falsification probe and an
  archived-regression probe, each independently necessary, run on a
  temporary apply of the candidate, plus refine and on_unmeasured outcomes.
- `w20-evidence-linked-memory`: checks an already stored lesson against its
  trajectory at read time; this gates the write.
- `w19-engram-release`: releases a record from retrieval after a probe
  without it; this admits a record after probes with it.
- `w17-memory-scope`: scope tags on write and read; this sketch has no scope
  model.

## Run

From `experiments/2026-11-12/w21-memory-admission/`, with system `python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The source check reads the abstract copy named in `paper_evidence.json`
from the directory in `$W21MA_SOURCES`. There is no default: when the
variable is unset (the normal case) that one test is skipped, so a plain
run reports `Ran 76 tests` and `OK (skipped=1)`.

## Files

- `memory_admission.py`: `MemoryStore`, validation, probes and `admit()`.
- `fixtures.py`: the toy world, seed store, shared archive and candidates;
  prints one record per candidate.
- `test_memory_admission.py`: unittest suite.
- `mutants.py`: 55 code mutants and 13 world (fixture) mutants; each must
  make the suite fail. Code mutants replace one exact snippet of
  `memory_admission.py` in memory (a probe ignored, local success
  committing, the temporary state aliasing the store, refine or expiry
  writing, isinstance in place of exact type, an undeclared `on_expiry` or
  threshold defaulted, no try/except, the validator branches, and the
  fix-round guards: shadowed falsification tasks counted as tested, an
  unsolved archive accepted, the commit-time id claim skipped, the id read
  before validation, seed lessons not validated). World mutants weaken a
  falsification set, shadow it with a stored lesson, drop or vary the
  archive, mislabel a task, empty the seed store, duplicate an id or loosen
  thresholds.
- `paper_evidence.json`: title, authors, licence, verbatim abstract quotes
  and the authors' figures, all UNVERIFIED.

## Limits

- The world, tasks and labels are synthetic and hand-built; the probe sets
  are fixtures, not generated. A weak falsification set is exactly why the
  archived-regression probe exists (`H-breaks`).
- Precondition matching is one `key=value` equality; real lessons are not.
- The verifier is a label comparison; judging real task success is out of
  scope.
- Gain and risk are counts on small fixture sets, not estimates.
