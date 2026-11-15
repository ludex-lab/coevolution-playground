# w20-plan-change-notice

Acknowledging a change of objective is not the same as acting on it. A
toy world with an authoritative objective, a local plan, a notice inbox and
an action log; a baseline that acks every notice but goes on executing its
cached plan; a notice-first guard that handles pending notices before any
consequential step; and a detector that compares actions with the
authoritative objective, which completion and ack summaries cannot do.

This is a method sketch of the plan-change idea in
[arXiv 2611.10011](https://arxiv.org/abs/2611.10011). It is not a
reproduction, not Team OS law and not village law. Clean-room Python 3
stdlib, synthetic deterministic worlds, no network, no model in the loop.

## Run

```
cd experiments/2026-11-11/w20-plan-change-notice/
python3 -m unittest test_plan_change.py -v
python3 fixtures.py
python3 mutants.py
```

The source check in the tests reads the abs-page copy named in
`paper_evidence.json` from `$W20PCN_SOURCES` and is skipped when it is absent.

`mutants.py` applies one source-text mutation at a time to `plan_change.py`
in a temporary copy of this directory, runs `fixtures.py` and the suite
there, prints killed or survived per mutant and a summary, and removes the
copy. Its 73 mutants merge the sketch's own list with the list from the
independent review of this pull request (flipped comparisons, dropped
checks, isinstance in place of exact type, unsorted or reordered delivery,
detector and summary blind spots), deduplicated by mutated source. Every
mutant is killed except one documented equivalent: `known_max` (`known =
max(known, v)`) cannot change behaviour, because `known` is assigned only
for a `valid_notice`, and that class already requires `v > known`.

## Records

| Record | Type | Meaning |
|---|---|---|
| authoritative objective | `Change(version, targets, issued_at)` | version `v` takes effect at `issued_at`; versions start at 1 and strictly increase |
| local plan | `Plan(objective_id, version, targets)` | derived from one objective version; step `i` is `targets[i]` |
| notice inbox | `Notice(notice_id, objective_id, version, targets, arrives_at)` | delivered at `arrives_at`; each delivered notice is acked and classified |
| action log | `Action(at, kind, index, plan_version, target)` | `consequential`, `wait` or `fallback_step` |

A `World` holds one objective id, its change history, the notices and the
turns at which the agent moves. At each turn, notices due by then are
delivered and acked (both policies ack the same notices), then the policy
takes at most one step.

Each delivered notice is classified against what the agent already knows
and the authoritative history at that turn: `valid_notice`, `duplicate`
(same id seen), `foreign_objective`, `stale_version` (not newer than the
known version, so an older notice cannot roll a plan back),
`ahead_of_authority` (names a version not yet in force) or
`content_mismatch` (targets differ from the authoritative version).

## Policies

- `baseline`: acks every notice, then executes the next step of the plan it
  derived at the start.
- `notice_first`: handles the inbox first, then compares its plan's version
  with the authoritative version at that turn.
  - equal: execute the next step;
  - different, and a `valid_notice` for the authoritative version has been
    handled: derive a new plan from the authoritative record and execute
    its next step;
  - different, and no such notice yet: take a `wait` turn. After the
    declared `wait_turns`, resolve to the declared `on_expiry`: `deny`,
    `hold` or `escalate` stop with no further step; `safe_fallback`
    records one non-consequential `fallback_step` and stops. No branch
    executes the stale plan.

## Silence doctrine

Taken from merged [#78 w14-silence-expiry](https://cursor.com/codebase/coevolution-lab/playground/pull/78):

- an unread or not-yet-delivered notice is never used; only notices handled
  at a turn count;
- "no notice" is never read as "nothing changed, carry on": a version gap
  with no handled notice is a wait, never a step;
- a handled notice for an older version never licenses a replan to a newer
  version in force (`SilenceDoctrine.test_older_valid_notice_does_not_license_a_newer_version`);
- the guard's wait path must declare `on_expiry` in {`deny`,
  `safe_fallback`, `escalate`, `hold`}; a missing or unknown value is
  `config_error` and nothing runs, even in a world where nothing changes;
- the run status after a timeout is `denied`, `fallback`, `escalated` or
  `held`, never `done`.

## Done-when, as tests

| | Requirement | Tests |
|---|---|---|
| (a) | the baseline acks the notice and still executes obsolete work | `DoneWhenA.test_baseline_acks_then_acts_on_the_cached_plan`, `test_obsolete_after_ack_on_every_design_case_with_a_delivered_valid_notice`, `test_uninformed_vs_after_ack` |
| (b) | the guard acts on the revised objective on held-out worlds | `DoneWhenB.*`: twelve worlds generated from seeds 2001-2012, not used while designing the guard, deterministic; the guard finishes with every consequential step matching the authority and its last step on the final version; the baseline goes obsolete on each |
| (c) | summaries cannot tell the traces apart; the detector can | `DoneWhenC.test_summaries_identical_detector_differs`: `notices_acked`, `steps_completed` and `status` are equal for both policies on five design worlds while `detect_obsolete` finds obsolete steps only in the baseline |

On (c): `summary()` reports only ack count, consequential-step count and
status, so for this summary the "cannot tell apart" half holds by
construction whenever both policies ack the same notices and finish the
same number of steps. The non-trivial part is that the guard reaches those
same counts with every step on the authoritative version, while
`detect_obsolete` still separates the two traces.

Adversarial cases (design fixtures plus tests): a change during a step, a
notice exactly at a turn, out-of-order notices, an older notice after a
newer one, a duplicate notice, a notice for another objective, a misleading
notice, a notice ahead of the authority, an empty inbox with and without a
change, a late notice with each `on_expiry`, a notice that arrives during
the wait, a zero-turn wait, a second notice id for the known version, a
notice id reused by an earlier ahead copy, an inbox listed out of arrival
order, and two changes in quick succession. A randomised test over generated worlds with
dropped, delayed and corrupted notices checks that the guard never has an
obsolete step.

`detect_obsolete(world, trace)` labels each obsolete consequential step
`obsolete_after_ack` when a valid notice for the authoritative version had
already been acked, else `obsolete_uninformed`.

## Fail closed

Every record is a frozen dataclass checked by exact type (`type(x) is
World`, `Notice`, `Change`, `GuardConfig`; exact `str`, `int` and `tuple`
fields), and each field is read once into locals before use, the lesson of
the subclass bypass found in review of
[#112](https://cursor.com/codebase/coevolution-lab/playground/pull/112).
Subclasses, `bool` or `float` times, NaN, non-tuple or empty targets,
non-increasing turns or versions, a first version other than 1, plan
lengths that change between versions, an unknown policy and a bad wait
configuration are all `config_error` with no actions. The expiry value used
is the module's own constant, not the caller's object.

## Overlap with earlier experiments

- [#78 w14-silence-expiry](https://cursor.com/codebase/coevolution-lab/playground/pull/78)
  (merged) is the source of the `on_expiry` vocabulary, the config-error
  rule and the stance that nothing proceeds on timeout. Reused unchanged.
- [#79 w14-phase-deadline](https://cursor.com/codebase/coevolution-lab/playground/pull/79)
  (merged) bounds phases with deadlines and bounded extensions, and leaves
  the silence doctrine out of scope. Here the only timer is the guard's
  `wait_turns`, and what it bounds is waiting for a notice, not a phase.
- [#110 w19-authz-drift](https://cursor.com/codebase/coevolution-lab/playground/pull/110)
  (open; read only) compares each step with the grant it ran under. Here
  each step is compared with the objective in force at that time; the stale
  thing is the plan, not the authorization.
- [#77 CoworkOS revision-checked leases](https://cursor.com/codebase/coevolution-lab/playground/pull/77)
  (`ask_main` with `wait_ms` and `fallback_assumption`) declares a fallback
  when a question goes unanswered; here the wait is for an incoming notice.
- On main, `experiments/2026-11-04/38-agent-mailbox-invariants-design-note.md`
  (read receipts) and `experiments/2026-11-04/20-soei-evidence-intent-ledger-design-note.md`
  (`ack_state`, completion claims vs proof) treat receipt and ack as
  records. This sketch shows why a receipt or ack is not evidence of action.

What this adds: the ack-versus-act split as two runnable policies over the
same world, notice-first ordering before every consequential step with a
declared wait path, and a summary-indistinguishability check paired with a
detector that compares actions with the authoritative objective.

## Not included

No signing, keyed hashes or ledger; no SQLite; no daemon, thread or
network; no language-model API; no simulator or prompts from the paper.

## Limitations

- Synthetic and deterministic: hand-written design worlds and seeded
  held-out worlds. This is not a reproduction of the paper's episodes with
  language-model actors, and its counts say nothing about any model.
- Plans are positional: every objective version has the same number of
  targets and step `i` maps to `targets[i]`. Partial overlap between old
  and new work, dependencies and costs are not modelled.
- The authoritative history is trusted as given; who may change an
  objective, forged authority and multi-agent membership are out of scope.
- The guard replans only after a valid notice for the authoritative version
  has been handled; a lost notice therefore always ends in `on_expiry`, even
  though the authoritative record could be read directly. That is a choice
  to tie ack and act together, not the only reasonable design.
- One agent, one objective id, at most one step per turn.
- Liveness L1, back-to-back changes: the wait counter is reset only when
  the guard replans, not when a newer valid notice arrives, so two changes
  in quick succession can use up `wait_turns` although every notice is
  delivered. The run then ends in `on_expiry`; it fails closed, never
  acting on a stale plan. Behaviour unchanged, locked by
  `Adversarial.test_back_to_back_changes_can_exhaust_the_wait`.
- Liveness L2, notice-id lockout: a mismatched, foreign or ahead copy that
  reuses the genuine notice id marks that id as seen, so the genuine notice
  is later classified `duplicate` and the run ends in `on_expiry`. It fails
  closed. Behaviour unchanged, locked by
  `Adversarial.test_id_reuse_locks_out_the_genuine_notice`.
- Held-out worlds (H1): the seeded generator for (b) is structurally easy;
  it never drops, corrupts or sends early notices, so the held-out set
  exercises replanning and waiting, not the hostile classes (those are
  covered by the design cases and the randomised test). That the held-out
  seeds were fixed before the guard was designed cannot be checked from
  the repository, because the history is a single squashed commit.
- `safe_fallback` (O1): in #78 it needs a registered substitute that is a
  different tool of strictly lower risk, and the doctrine applies when
  `requires_approval` is true. Here there is no substitute registry and no
  approval flag: `safe_fallback` records one non-consequential
  `fallback_step` with no substitute and stops. It reuses the vocabulary,
  not #78's fallback check.

## Paper figures

The paper's figures are recorded only in `paper_evidence.json`, as number
tokens with their offsets in the abstract field, and are marked UNVERIFIED.

## Builder reflection

The baseline here is not lazy: it reads and acks every notice, which is
exactly why its reports look fine. Putting the version check in front of
every consequential step costs one comparison and moves the failure from
silent obsolete work to a visible wait. The detector only works because the
authoritative objective is stored as its own record, apart from what the agent
says it saw. The review's mutants found that an older valid notice could
have licensed a newer version unnoticed, so that rule is now a test, not an
assumption.

Ludex: a receipt says the letter arrived; only the road you took says you
read it.

Implementation may be complete; it is not declared verified.
