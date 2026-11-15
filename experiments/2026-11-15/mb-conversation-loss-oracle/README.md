# mb-conversation-loss-oracle

Schema-valid is not conversation-preserving: a translated chat request can
pass the target's static checks and still have lost its system text, a
role, a tool-error flag or a generation control. **Soft** method sketch,
not a reproduction, of
[arXiv 2611.15543](https://arxiv.org/abs/2611.15543), "Testing Conversation
Preservation Across LLM APIs: A Rule-Based Oracle for Detecting Silent
Information Loss" (Xin Liu, Xu Han, Yuxin Wang, Haoran Song, Mingjian Zhao,
Lei Wang; v1, submitted 11 Nov 2026; primary category cs.SE, cross-listed
cs.AI).

Paper licence: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/, as
linked on the abs page). Upstream repository:
https://github.com/convpreserve/conv-preserve (Apache-2.0, HEAD
8c34759bb854767e55b80af3016693400f5cb698); not run, not installed, not
copied, UNVERIFIED. This folder is a reimplementation of the method from the
paper's description only; it uses no upstream code, rule list or rule text.
Clean-room, method-borrow only (see `NOTICE`).

This is a method sketch, not law, policy or a team rule. Status: Soft (a
Morning Brief candidate). The fixtures are synthetic and hand-written:
every request, payload, target profile and gold label is a fixture label.
The paper's figures are `on_unmeasured` here (`paper_results()` says so);
they live only in `paper_evidence.json`, quoted verbatim from the abstract
and marked UNVERIFIED. Python 3 standard library only: no network, no
model, no paid API, no SDK, no gateway, no voting or ensemble, no files
written, no timeout or expiry.

## What it does

A case is one translation: a source request in toy dialect A, the
translated payload in toy dialect B, and the target profile (the declared
limits of the target endpoint).

| dialect A (source) | dialect B (target) |
|---|---|
| `system` (`""` means none) | optional `preamble` |
| message `role`: `user` / `assistant` / `tool` | turn `speaker`: `human` / `model` / `tool` |
| `tool_call` `{id, name, args}` | `invoke` `{ref, fn, params}` |
| tool result `{call_id, result, is_error}`; `result` is text or a list of text parts | tool turn `{ref, output, failed}`; `failed` is optional and defaults to false |
| `tools` (names) | `functions` (`{name}` objects) |
| `controls`: `max_tokens`, `temperature_milli`, `thinking_budget` | `settings`: `max_output`, `temperature_milli`, `reasoning_budget` |

Profile: `has_system`, `alternating` (adjacent same-speaker text turns are
rejected), `controls` (the controls the target supports) and
`max_tokens_cap`. A profile with no system field that also requires
alternation is out of scope for this toy (`config_error`).

Dialect B can express everything dialect A can. Its declared encoding
(`encode_b`): system to preamble, or, when the target has no system field,
to a first `human` turn holding the system text; role to speaker; call ids
may be re-minted consistently; a list result becomes its parts joined with
a newline; when the target requires alternation, two adjacent same-role
text messages are merged with a newline; an unsupported control is dropped
and `max_tokens` is clamped to the cap. Those four are the forced changes.

Both payloads map to one intermediate record (ConvIR-like): system text,
the ordered messages (`text` with role, `call` with name and arguments,
`result` with the position of the call it answers, its text and its error
flag), the set of tool names and the controls. Call ids are replaced by
call positions, so consistently re-minted ids are not a change.

Two arms score every case:

| arm | reads | PASS when |
|---|---|---|
| baseline: static check only | the target payload and the profile | `schema_check` accepts the payload (well-typed dialect B within the declared limits) |
| rule arm: static check + IR rules | both intermediate records and the profile | the static check passes and `rules()` finds no avoidable change |

The rules (this sketch's own ids; each finding is `(rule id, field path,
status)`, status `avoidable` or `forced`; paths are ConvIR paths and message
indices are source positions):

| id | name | path | forced when |
|---|---|---|---|
| CL01 | system_dropped | `system` | never |
| CL02 | system_altered | `system` | never |
| CL03 | system_demoted | `system` | the target has no system field |
| CL04 | role_changed | `messages[i].role` | never |
| CL05 | text_altered | `messages[i].text` | never |
| CL06 | messages_reordered | `messages` | never |
| CL07 | message_dropped | `messages[i]` | never |
| CL08 | same_role_merge | `messages[i]` | the target requires alternation |
| CL09 | cross_role_merge | `messages[i]` | never |
| CL10 | message_mismatch | `messages` or `messages[i]` | never |
| CL11 | tool_call_renamed | `messages[i].name` | never |
| CL12 | tool_call_args_altered | `messages[i].args` | never |
| CL13 | tool_result_relinked | `messages[i].call` | never |
| CL14 | tool_result_altered | `messages[i].content` | never |
| CL15 | tool_error_flag_dropped | `messages[i].is_error` | never |
| CL16 | tool_error_flag_injected | `messages[i].is_error` | never |
| CL17 | tool_definition_dropped | `tools.<name>` | never |
| CL18 | tool_definition_injected | `tools.<name>` | never |
| CL19 | control_dropped | `controls.<name>` | the target does not support the control |
| CL20 | control_injected | `controls.<name>` | never |
| CL21 | control_altered | `controls.<name>` | `max_tokens` above the cap, translated to exactly the cap |

Dropping the system text is avoidable even when the target has no system
field, because the declared encoding can demote it. Text is compared
exactly: whitespace counts.

Malformed input is `config_error`, and `evaluate()` never raises. Every
dict key, at every level (case, source, message, tool call, arguments,
controls, profile and every level of the target payload), must be an exact
`str`, and that is checked before any lookup in the dict. Every value is
checked by exact type, so subclasses of `str`, `int`, `bool`, `list` and
`dict` are rejected, and `bool` is not an `int`. `validate()` reads each
caller value once and returns a private snapshot (the source as its
intermediate record, the target as fresh dicts and lists, depth at most
8); the static check and the rules run only on that snapshot and never
read the caller's objects again. There is no timeout or expiry in this
design, so no `on_expiry` is declared.

## Independent oracle

`oracle.py` is a second, separate code path. It imports nothing, shares no
name with the module and does not validate the source or the profile. It
reads the raw payloads directly, turns each message into a small dict,
finds a reorder by counting equal messages (not by sorting) and finds a
merge or a drop by building each candidate target sequence and comparing
it whole; it has its own static check. The suite compares module and
oracle on every fixture case and exhaustively on three spaces:

```
messages: 74261 cases, 37994 accepted, 18832 past the static check, 0 disagreements
controls: 576 cases, 576 accepted, 324 past the static check, 0 disagreements
tools: 128 cases, 128 accepted, 128 past the static check, 0 disagreements
```

`messages`: every source sequence of up to two messages over six source
messages, against every target sequence of up to two turns over twelve
target turns, under eleven system/preamble/profile combinations (sources
with an unanswered result or a duplicate call id are `config_error` and
are not compared). `controls`: every source control map against every
target settings map under two profiles. `tools`: every source tool set
against every ordered target function list over three names.

## Done-when (box tests)

| Morning Brief #1 | test |
|---|---|
| (a) every planted avoidable fault is flagged by the rule arm | `test_a_rule_arm_flags_every_planted_fault` |
| (b) permitted-change controls do not alarm, or any false alarm is reported honestly | `test_b_permitted_controls_do_not_alarm_or_are_reported` |
| (c) encoding-only payloads and the planted faults still pass the toy static target check (the baseline misses the faults) | `test_c_static_check_passes_encoding_changes_and_planted_faults` |
| (d) every finding names the rule id and the field path | `test_d_every_finding_names_rule_id_and_field_path` |
| (e) no model API, no network, standard library only | `test_e_no_model_no_network_stdlib_only` |
| forced changes are labelled forced, not faults | `test_f_forced_changes_labelled_forced_not_faults` |
| paper figures `on_unmeasured`, UNVERIFIED | `test_g_paper_numbers_on_unmeasured` |

(e) is checked on the code: an AST scan of every import (module and
oracle: nothing; fixtures: `copy` and the two modules), a token scan of
the module, oracle and fixtures for voting, ensemble, API-key,
environment, URL, socket, subprocess, random, thread and timeout names,
and the same name checks on the loaded function code (plus `open`,
`eval`, `exec`), so an in-memory mutant that adds them is caught.

## Results

```
python3 -B -m unittest   ->  Ran 41 tests, OK (skipped=1)
python3 -B mutants.py    ->  killed 92/92 (code 72/72, world 14/14, harness 6/6)
```

The skip is the quote check against the abstract copy (see Run). With
`$MBCONVLOSS_SOURCES` set to the directory holding that copy, all 41 pass
with no skip.

`python3 -B fixtures.py`:

```
case                                 category baseline rule  findings
ctl-role-field-renamed               control  PASS     PASS  -
ctl-key-order                        control  PASS     PASS  -
ctl-tools-reordered                  control  PASS     PASS  -
ctl-ids-reminted                     control  PASS     PASS  -
ctl-source-text-result               control  PASS     PASS  -
ctl-error-false-omitted              control  PASS     PASS  -
ctl-trailing-newline-stripped        control  PASS     FAIL  CL02:system:avoidable
f-system-dropped                     fault    PASS     FAIL  CL01:system:avoidable
f-system-altered                     fault    PASS     FAIL  CL02:system:avoidable
f-system-demoted-needlessly          fault    PASS     FAIL  CL03:system:avoidable
f-system-dropped-no-system-target    fault    PASS     FAIL  CL01:system:avoidable
f-role-swap                          fault    PASS     FAIL  CL04:messages[3].role:avoidable
f-text-altered                       fault    PASS     FAIL  CL05:messages[4].text:avoidable
f-cross-role-merge                   fault    PASS     FAIL  CL09:messages[3]:avoidable
f-same-role-merge-needless           fault    PASS     FAIL  CL08:messages[0]:avoidable
f-reordered                          fault    PASS     FAIL  CL06:messages:avoidable
f-message-dropped                    fault    PASS     FAIL  CL07:messages[7]:avoidable
f-message-injected                   fault    PASS     FAIL  CL10:messages:avoidable
f-error-flag-dropped                 fault    PASS     FAIL  CL15:messages[6].is_error:avoidable
f-error-flag-injected                fault    PASS     FAIL  CL16:messages[2].is_error:avoidable
f-tool-call-renamed                  fault    PASS     FAIL  CL11:messages[5].name:avoidable
f-tool-args-altered                  fault    PASS     FAIL  CL12:messages[1].args:avoidable
f-result-relinked                    fault    PASS     FAIL  CL13:messages[6].call:avoidable
f-result-altered                     fault    PASS     FAIL  CL14:messages[2].content:avoidable
f-tool-def-dropped                   fault    PASS     FAIL  CL17:tools.cancel_hold:avoidable
f-tool-def-injected                  fault    PASS     FAIL  CL18:tools.delete_booking:avoidable
f-thinking-injected                  fault    PASS     FAIL  CL20:controls.thinking_budget:avoidable
f-control-dropped                    fault    PASS     FAIL  CL19:controls.temperature_milli:avoidable
f-control-altered                    fault    PASS     FAIL  CL21:controls.max_tokens:avoidable
f-clamp-plus-injection               fault    PASS     FAIL  CL20:controls.temperature_milli:avoidable CL21:controls.max_tokens:forced
fo-max-tokens-clamped                forced   PASS     PASS  CL21:controls.max_tokens:forced
fo-thinking-unsupported              forced   PASS     PASS  CL19:controls.thinking_budget:forced
fo-system-demoted                    forced   PASS     PASS  CL03:system:forced
fo-same-role-merge                   forced   PASS     PASS  CL08:messages[0]:forced
s-over-cap                           schema   FAIL     FAIL  schema setting_over_cap at settings.max_output
cases: 35 (controls 7, planted faults 23, forced 4, schema 1)
planted faults flagged: baseline 0/23, rule arm 23/23
planted faults named with rule id and path: 23/23
planted faults passing the static target check: 23/23
permitted-change controls alarmed: baseline 0/7, rule arm 1/7
forced cases passed: baseline 4/4, rule arm 4/4
forced findings reported as forced: 5
module vs oracle: 35/35 cases agree
```

Reading the numbers (fixture counts, not comparable with any figure in the
paper):

- The rule arm flags all 23 planted avoidable faults, each with the
  planted rule id and field path; every one of the 21 rule ids is planted
  at least once. The baseline, the same static check without the rules,
  passes all 23: each faulty payload is well-typed dialect B within the
  declared limits.
- Six of the seven permitted-change controls raise nothing: the
  role-field rename (the faithful translation), dict key order, function
  order, consistently re-minted call ids, a source result written as text
  instead of a list, and an omitted `failed` flag where the source flag
  was false.
- One control is a false alarm, reported here rather than hidden:
  `ctl-trailing-newline-stripped` (the translator stripped a trailing
  newline from the system text) is flagged `CL02 system_altered`, because
  the rules compare text exactly. Whether whitespace is information is a
  rule choice; this sketch chose exactness.
- The four forced cases pass the rule arm with their change reported as
  forced: max tokens clamped to the cap, thinking budget dropped on a
  target that does not support it, system text demoted on a target with no
  system field, and two user messages merged on a target that requires
  alternation. The same demotion and the same merge are faults
  (`f-system-demoted-needlessly`, `f-same-role-merge-needless`) on a
  target whose limits did not force them. `f-clamp-plus-injection` holds a
  forced clamp beside an avoidable injected temperature: both are
  reported, and the case fails on the avoidable one.
- The static check is not vacuous: `s-over-cap` (max output above the
  cap) fails both arms.

## How this differs from w23-world-consistent-history

- `w23-world-consistent-history` (experiments/2026-11-14) checks edits to
  an agent's history against the world state: an edit that turns a
  failure into a completed action or a success receipt the world does not
  hold is refused. It needs a world state and judges whether a history
  claim is true.
- New here: no world state and no truth judgement. The question is only
  whether a translation from one API dialect to another preserved the
  conversation it was given (system text, roles, order, tool calls,
  results, error flags, tool definitions and controls), checked by
  comparing the source and translated payloads through one shared record,
  and whether each change was avoidable or forced by the declared target
  limits. A stripped tool-error flag is caught here as a translation loss
  even when nothing in the history is false.

## Files

- `conv_loss.py`: validation and snapshot, `schema_check()` (the toy
  static target check), `target_ir()`, `rules()` and `compare_messages()`,
  `encode_b()` (the declared encoding), `describe()`, `evaluate()` and
  `paper_results()`.
- `oracle.py`: the independent reference.
- `fixtures.py`: 35 synthetic cases (7 permitted-change controls, 23
  planted faults, 4 forced, 1 schema-rejected) with hand-written gold
  labels.
- `test_conv_loss.py`: unittest suite.
- `mutants.py`: code mutants (snippets of the module or the oracle swapped
  in memory), world mutants (fixture changes) and harness mutants (the
  row-scoped hygiene scan, the exhaustive space and the oracle call
  replaced in memory). Each must make the suite fail; the runner exits
  non-zero if any survives.
- `paper_evidence.json`: the authors' claims with verbatim abstract quotes
  and offsets, and the upstream README's rule count, each UNVERIFIED and
  `on_unmeasured`.
- `NOTICE`: credit and licence.

## Run

From this folder, with system `python3`:

```
python3 -B -m unittest
python3 -B fixtures.py
python3 -B mutants.py
```

The quote test reads the abstract copy named in `paper_evidence.json` from
the directories listed in `$MBCONVLOSS_SOURCES` (separated by the OS path
separator); it skips when that is unset.

The hygiene tests (banned words, absolute paths, conflict markers, paper
numbers) read every file of this folder whole, but read only this PR's own
row of the day README (the line starting `- [mb-conversation-loss-oracle](`),
so rows added by other PRs are not judged here.

## Builder reflection

Useful: a model-free diff of source and translated payloads through one
shared record names each silent loss with a rule id and a field path, and
the forced/avoidable split stops a target's real limits from being
reported as translator bugs. Fragile: the verdict is only as good as the
declared target profile (a wrong profile turns a fault into "forced"), and
exact text comparison already produced one false alarm on a stripped
newline. For Ludex Village (Cody/Naru): when an adapter re-encodes a
villager's request for another tool, diff source against translated
through one shared record before the hand-off, and treat a dropped
tool-error flag as a stop, not a log line.

## Limits

- Both dialects, the intermediate record, the 21 rules and the target
  profiles are this sketch's own toys; they are not any real provider's
  API, and the rules are not the paper's or the upstream repository's.
- Requests only: reply streams, streaming chunks and SDK behaviour (part of
  the paper's scope) are not modelled.
- Message alignment is positional with one reorder, one merge or one drop
  recognised per conversation; anything else is a single `CL10`
  mismatch. Calls are numbered by position, so reordering two calls reads
  as renames.
- Text is compared exactly, so whitespace-only changes alarm (the declared
  false alarm). There is no semantic equivalence check.
- The forced/avoidable decision trusts the declared profile; it does not
  probe a real endpoint.
- 35 hand-written cases and small exhaustive spaces; no translator,
  gateway, SDK, model or benchmark is run, and no human labels exist.
- Key and type checks close the input to caller-defined objects (no caller
  `__eq__`, `__hash__` or `__lt__` runs after the key check). They do not
  defend against code that runs in the same process and patches this
  module.
- Mutation kills show the suite catches these specific edits, not every
  possible fault.
- The paper's results are `on_unmeasured`; nothing here reproduces or
  tests them.
