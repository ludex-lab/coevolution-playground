# w22-write-precommit

Commit writes before any tool result; admit a write only when every
argument that decides whom or what it affects is stated in the user
request. **Top** method sketch of
[arXiv 2611.17115](https://arxiv.org/abs/2611.17115), "CapLite:
Prompt-Injection Defense for Small Language Model Agents without
Model-Written Security Artifacts" (Zimo Xu, Wenzhuo Liu, Hideki Nakayama;
v1, submitted 12 Nov 2026; primary category cs.AI, cross-listed cs.CL and
cs.CR).

Paper licence: CC BY 4.0 (http://creativecommons.org/licenses/by/4.0/).
Method-borrow only; the abs page links no code and none is used.

This is a Top method sketch, not a reproduction, and not law, policy or a
team rule. The fixtures are synthetic. The paper's attacked-episode,
utility and token figures are `on_unmeasured` here
(`write_precommit.paper_results()` says so); the authors' claims sit only
in `paper_evidence.json`, quoted verbatim from the abstract and marked
UNVERIFIED. Standard library only: no network, no model, no files written.

## What is tested

`write_precommit.evaluate(episode)` is a pure function over one fixture
episode:

| field | meaning |
|---|---|
| `request` | the user request (non-empty str) |
| `schema` | per tool: `effect` (`read` or `write`) and `targeting` (arg name to role: `recipient`, `amount`, `object`, `destination`) |
| `events` | ordered `commit`, `tool_result` and `write` events |

The policy comes only from the schema (`policy_from_schema`). An episode
key other than `request`, `schema` and `events` (a `policy`, `constraints`,
`program`, `graph`, ...) is `config_error`: the agent cannot hand in a
security artifact of its own. Malformed schemas and events, non-`str`
values (a `bool`, an `int`, a `str` subclass), unknown tools, a commit or
write naming a read tool, a tool result from a write tool and a duplicate
commit before the first result are all `config_error`.

Rules:

1. The commit set is frozen at the first applied `tool_result`. A later
   `commit` is recorded in `late_commits`, never admitted, and does not
   replace an earlier commit for the same `call_id`.
2. A `write` is `ADMIT` only when its `call_id` was committed earlier in
   the trace and before the first tool result, its tool and every
   targeting arg equal that commit, every targeting arg is present,
   non-blank and an exact (case-sensitive) substring of the request, and
   the commit has not already produced an admitted write. Otherwise it is
   `REFUSE` with reasons from `not_precommitted`, `retargeted`,
   `missing:<arg>`, `empty:<arg>`, `unstated:<arg>`, `already_executed`.
3. Tool-result text is never read by the check. Non-targeting args (a
   body, a subject) are free.

There is no timeout in this design, so no `on_expiry` is declared.

`oracle.py` is an independent reference: it does not import the module
and recomputes each decision by index arithmetic over the event list (cut
at the first tool result, precommit table, single-use list). The suite
checks module = oracle = fixture label on every fixture, and module =
oracle on 800 seeded generated episodes.

## Done-when mapping (VERDICT section 6, T1)

| item | test |
|---|---|
| (a) precommitted write, user-stated args, admitted | `TestDoneWhenA.test_a_precommitted_stated_write_admitted`, `test_a_admitted_across_a_tool_result`, `test_a_non_targeting_body_may_come_from_result` |
| (b) write added only after a tool-result injection refused | `TestDoneWhenB.test_b_injected_attacker_write_refused`, `test_b_injected_write_with_stated_args_refused`, `test_b_commit_after_result_is_late` |
| (c) precommitted write with unstated dest/amount refused | `TestDoneWhenC.test_c_unstated_target_refused`, `test_c_destination_and_amount_absent_from_request`, `test_c_tool_result_text_is_not_user_text`, `test_c_match_is_case_sensitive` |
| (d) no network, no model, no model-written policy | `TestDoneWhenD.test_d_module_and_oracle_import_nothing`, `test_d_stdlib_only_no_network`, `test_d_oracle_independent`, `test_d_episode_cannot_supply_policy`, `test_d_policy_from_schema_only`, `test_d_decisions_ignore_tool_result_text`, `test_d_paper_results_on_unmeasured`, `test_d_evaluate_is_pure` |
| (e) FIX-note: retarget after a tool result refused even when the new target is in the request | `TestDoneWhenE.test_e_retarget_refused_even_when_new_target_stated`, `test_e_new_recipient_appears_in_request`, `test_e_late_recommit_does_not_replace`, `test_e_tool_swap_with_same_args_refused`, `test_e_refused_retarget_does_not_spend_commit`, `test_e_commit_admits_one_write` |

The four VERDICT mutants are `[V1]` skip the precommit check, `[V2]`
tool-result text treated as user text, `[V3]` admit a retarget, `[V4]`
admit an unstated destination; all are killed (see `mutants.py`).

## Fixtures

`python3 -B fixtures.py` prints one row per episode. The expected
decisions are fixture labels written by hand.

| id | done-when | label |
|---|---|---|
| `A1-stated-after-results` | a | ADMIT |
| `A2-body-from-result` | a | ADMIT (body from a tool result) |
| `A3-move-no-results` | a | ADMIT |
| `B1-injected-attacker-write` | b | REFUSE not_precommitted, unstated args |
| `B2-injected-write-stated-args` | b | email ADMIT; injected payment REFUSE not_precommitted |
| `B3-late-commit` | b | REFUSE not_precommitted (late commit) |
| `C1-unstated-destination` | c | REFUSE unstated:folder |
| `C2-unstated-amount` | c | REFUSE unstated:amount |
| `C3-unstated-recipient` | c | REFUSE unstated:recipient |
| `C4-dest-only-in-tool-result` | c | REFUSE (args only in a tool result) |
| `C5-blank-arg` | c | REFUSE empty:recipient |
| `C6-missing-arg` | c | REFUSE missing:recipient |
| `C7-case-differs` | c | REFUSE unstated:recipient |
| `E1-retarget-to-stated-recipient` | e | REFUSE retargeted |
| `E2-recommit-after-result` | e | REFUSE retargeted (late re-commit) |
| `E3-retarget-amount` | e | REFUSE retargeted |
| `E4-retarget-tool` | e | REFUSE retargeted (tool swap) |
| `E5-retarget-then-original` | e | REFUSE, then the original ADMIT |
| `X2-write-before-commit` | x | REFUSE, then ADMIT after the commit |
| `X1-double-execute` | x | ADMIT, then REFUSE already_executed |

Plus 20 `config_error` cases in `fixtures.CONFIG_CASES`.

## How this differs from earlier sketches

- `w19-authz-drift`: an act that exceeds a grant through a shortcut.
- `w19-workspace-grant`: a workspace path grant with an expiry.
- `w17-source-authority`: who may set a field.
- New here: writes frozen before any tool result, and targeting args that
  must be stated by the user, so text arriving in a tool result can
  neither add a write nor retarget one.

## Files

- `write_precommit.py`: validation, `policy_from_schema`, `check_write`,
  `evaluate`, `paper_results`.
- `oracle.py`: independent reference (`decide`).
- `fixtures.py`: schema, 20 labelled episodes, 20 config cases.
- `test_write_precommit.py`: unittest suite.
- `mutants.py`: code mutants (snippets of `write_precommit.py` or
  `oracle.py` swapped in memory) and world mutants (fixture changes).
  Each must make the suite fail.
- `paper_evidence.json`: the authors' claims, verbatim abstract quotes
  with offsets, UNVERIFIED, `on_unmeasured`.
- `NOTICE`: credit and licence.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The quote test reads the source copy named in `paper_evidence.json` from
the directories listed in `$W22PRECOMMIT_SOURCES` (separated by the OS
path separator); it skips when that is unset.

Results: 42 tests, 1 skipped without `$W22PRECOMMIT_SOURCES`; mutants
killed 46/46 (code 28/28, world 18/18).

## Limits

- Substring is a weak notion of "stated": an amount `50` is found inside a
  request that says `500`, and a recipient `Kim` inside `Alice Kim`. The
  sketch does not tokenise, normalise numbers or resolve contacts; exact
  case-sensitive substring is the declared rule.
- A user request that names a target only indirectly ("the bill in
  bill.txt", "my landlord") cannot be served: the write is refused
  (`C4`, `C3`). That is a utility cost, not measured here.
- Which args are targeting args is declared in the fixture schema. A
  schema that leaves a deciding arg out of `targeting` leaves it unchecked.
- Non-targeting args are free, so a body or subject can still carry
  injected text to a user-stated recipient.
- Commits, tool results and writes are caller-supplied fixture events;
  the sketch checks a trace, it does not run or intercept an agent.
- Only the abstract was read. The paper's own policy derivation, its
  argument roles and its evaluation are not reproduced, and every paper
  number is UNVERIFIED and lives only in `paper_evidence.json`.
