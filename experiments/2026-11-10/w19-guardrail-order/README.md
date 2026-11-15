# w19-guardrail-order

A silent guardrail-order break in a toy agent harness, and an order check
that reads what actually ran instead of what the config says.

This is a method sketch of the order-check idea in arXiv 2611.09088
(PatternOps, Xia, Lu, Sejdinovic and Zhu). It is not a reproduction,
not village law and not Team OS law. Clean-room Python 3 stdlib, synthetic data,
no network at runtime.

## Run

```
cd experiments/2026-11-10/w19-guardrail-order/ && python3 -m unittest test_guardrail_order.py -v && python3 fixtures.py
```

## What is in it

- `guardrail_order.py`: the toy `Harness` and the check layer.
- `fixtures.py`: ten synthetic scenarios; `python3 fixtures.py` prints one
  PASS/FAIL line each and the order report.
- `test_guardrail_order.py`: unit tests, evidence checks and hygiene checks.
- `paper_evidence.json`: licence, citation, excerpts with offsets, and the
  paper's own figures marked UNVERIFIED.

The harness's edit decision path is a chain of stages that run in
registration order until one stage ends the call. It starts as
`[guardrail -> edit_tool]`. `guardrail` blocks edits under `protected/`;
`edit_tool` writes the file and ends the call. Every edit decision appends a
frozen `DecisionRecord` (which stages actually ran, in order, and the
outcome) to an append-only runtime history.

Two routine maintenance ops change the runtime path without touching the
static config:

- `reapply_plugin("guardrail")` disposes the guardrail instance and registers
  a fresh one last, behind `edit_tool`. `edit_tool` ends the call first, so
  the guardrail is never reached.
- `save_allow_rule("")` stores a standing rule for edits to any file; matching
  requests go straight to `edit_tool`.

After either op, `config["plugins"]["guardrail"]["active"]` is still `True`
and `config["pipeline"]` still reads `[guardrail, edit_tool]`.

The check layer is `check_order`, `detect`, `hold`, `flag`, `report` and
`compare`. `check_order(history, required="guardrail", before="edit_tool")`
asks, for every edit decision in the history, whether the guardrail actually
ran on the decision path ahead of the edit tool. It reports one of
`order_ok`, `order_broken` or `hold`, and it never clears or admits anything.
An empty history, or a malformed record, is `hold` (fail closed).

## How each requirement is shown

| | Requirement | Fixture | Tests |
|---|---|---|---|
| (a) | prohibited edit blocked before the ops | `a_before_ops_blocked` | `test_a_prohibited_edit_blocked_before_ops` |
| (b) | same edit executes after the ops | `b_after_ops_executes`, `reapply_only_breaks`, `saved_rule_only_breaks` | `test_b_prohibited_edit_executes_after_ops`, `test_reapply_alone_breaks`, `test_saved_rule_alone_breaks` |
| (c) | order check: `order_ok` before, `order_broken` after | `c_check_before_ok`, `c_check_after_broken` | `test_c_check_ok_before_ops`, `test_c_check_broken_after_ops` |
| (d) | check reads runtime history, not config | `d_config_lists_active_runtime_broken`, `d_config_says_inactive_runtime_ok` | `test_d_config_lists_active_while_check_fails`, `test_d_mutating_config_has_no_effect`, `test_d_check_signature_has_no_config`, `test_d_check_layer_source_never_names_config` |

Also covered: a benign edit after the ops executes and the check still
reports `order_broken` (`benign_after_ops_still_broken`), because the order
is broken even though nothing harmful happened; an empty history is `hold`
(`empty_history_held`); a guardrail that runs after the edit tool counts as
broken; a saved rule scoped to another folder leaves the path intact.

For (d), the fixture `d_config_lists_active_runtime_broken` shows the config
still listing the guardrail as active while the check fails on the runtime
history, and `d_config_says_inactive_runtime_ok` shows the mirror case: a
config edited to say the guardrail is off, with the runtime chain intact,
still checks `order_ok`. `check_order` takes no config argument, its source
never names the config, and clearing or editing the config leaves its result
unchanged. `compare` only puts the listing claim next to the runtime result.

## UNVERIFIED numbers

The paper's study sizes (how many relationships, harnesses and plugins it
examined) are recorded in `paper_evidence.json` under `empirical_claims`,
each marked UNVERIFIED. None of them is used or checked here, and none
appears in the code, fixtures or this README.

## Licence

The paper is under the arXiv.org perpetual non-exclusive license 1.0
(http://arxiv.org/licenses/nonexclusive-distrib/1.0/). This sketch takes the
method and shape only; no paper text is copied into the code, fixtures or
prose. Short attributed excerpts sit in `paper_evidence.json` as evidence.
The paper has no code to pin, so `implementation_pin` is `null`. See
`NOTICE`.

## Builder reflection

The part worth having is that the check never looks at the config: a
listing that says "guardrail active" is a claim, and only the record of
which stages ran for each decision can back it. Building both ops showed two
different carriers for the same break, one in stage order and one in saved
state, and the check catches both without knowing which op ran. The benign
edit is the uncomfortable case on purpose: nothing bad happened, and the
order is still broken.

Ludex: after Cody reinstalls the gate-latch plugin on the village workshop
door, Naru reads the night's door log rather than the plugin list, and if
any entry shows the door opening without the latch step before it, she
marks the door as broken order and holds the tool room until the latch is
back in front.

Implementation may be complete; it is not declared verified.
