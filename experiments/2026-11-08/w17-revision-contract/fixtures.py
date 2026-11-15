"""Frozen SYNTHETIC fixtures for the call-level revision contract sketch.

Toy workflow sources only; the "provider" is a deterministic in-process stub.
Committed ledgers are a JSON fixture (committed_ledgers.json), not a database.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from contract import (GateDecision, Ledger, OrphanPolicy, RepeatPolicy, RunOutcome,
                      build_ledger, load_ledger_text, revise)

HERE = Path(__file__).resolve().parent
LEDGER_FILE = HERE / "committed_ledgers.json"

INPUTS = {"brief": "lighthouse at dawn"}

# --- base workflow: plan, loop of image calls, compose (compose fails) ------
BASE_OLD = '''
def main(ctx, inp):
    board = ctx.run("storyboard.plan", {"brief": inp["brief"], "shots": 3})
    width = 512
    clips = []
    for i in range(3):
        clips.append(ctx.run("image.generate", {"prompt": inp["brief"], "shot": i, "w": width}))
    return ctx.run("video.compose", {"clips": clips, "fail": True})
'''

# happy path: only the uncommitted failing call is repaired; a comment and a
# non-capability statement are added (identity-stable edits)
HAPPY_NEW = '''
def main(ctx, inp):
    # repaired after compose failure
    board = ctx.run("storyboard.plan", {"brief": inp["brief"], "shots": 3})
    note = "retry"
    width = 512
    clips = []
    for i in range(3):
        clips.append(ctx.run("image.generate", {"prompt": inp["brief"], "shot": i, "w": width}))
    return ctx.run("video.compose", {"clips": clips, "fps": 24})
'''

# literal argument AST edit inside a committed call expression
LITERAL_EDIT_NEW = HAPPY_NEW.replace('"w": width}', '"w": 768}')

# 1. unchanged expression, changed variable feeding it
CHANGED_VARIABLE_NEW = HAPPY_NEW.replace("width = 512", "width = 768")

# 2. relocation: identical expression moved into a helper
RELOCATION_NEW = '''
def plan(ctx, inp):
    return ctx.run("storyboard.plan", {"brief": inp["brief"], "shots": 3})

def main(ctx, inp):
    board = plan(ctx, inp)
    width = 512
    clips = []
    for i in range(3):
        clips.append(ctx.run("image.generate", {"prompt": inp["brief"], "shot": i, "w": width}))
    return ctx.run("video.compose", {"clips": clips, "fps": 24})
'''

# 3. unreachable call / orphan: loop shrinks, every frozen callsite still present
ORPHAN_NEW = HAPPY_NEW.replace("for i in range(3):", "for i in range(1):")

# --- fanout workflow ---------------------------------------------------------
FANOUT_OLD = '''
def shot(ctx, prompt):
    return ctx.run("image.generate", {"prompt": prompt, "w": 512})

def main(ctx, inp):
    prompts = ["harbor", "market", "summit"]
    clips = ctx.fanout(shot, prompts)
    return ctx.run("video.compose", {"clips": clips, "fail": True})
'''

# 4a. path shift: a branch inserted ahead of committed branches
FANOUT_SHIFT_NEW = FANOUT_OLD.replace('["harbor", "market", "summit"]',
                                      '["intro", "harbor", "market", "summit"]').replace(
    '"fail": True', '"fps": 24')

# 4b. fanout append: new branch after committed ones is new work
FANOUT_APPEND_NEW = FANOUT_OLD.replace('["harbor", "market", "summit"]',
                                       '["harbor", "market", "summit", "finale"]').replace(
    '"fail": True', '"fps": 24')

# --- occurrence extension (extra): constant payload, wider loop ---------------
RETRY_OLD = '''
def main(ctx, inp):
    takes = []
    for i in range(2):
        takes.append(ctx.run("image.generate", {"prompt": "fixed take"}))
    return ctx.run("video.compose", {"clips": takes, "fail": True})
'''
RETRY_NEW = RETRY_OLD.replace("range(2)", "range(4)").replace('"fail": True', '"fps": 24')

OLD_SOURCES = {"base": BASE_OLD, "fanout": FANOUT_OLD, "retry": RETRY_OLD}


def rebuild_ledgers() -> Dict[str, Ledger]:
    return {name: build_ledger(src, INPUTS)[0] for name, src in OLD_SOURCES.items()}


def load_frozen_ledgers() -> Dict[str, str]:
    """Return ledger JSON text per base name from the frozen JSON fixture."""
    raw = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
    return {name: json.dumps(body) for name, body in raw.items()}


def write_frozen_ledgers() -> None:
    body = {name: json.loads(l.to_json()) for name, l in rebuild_ledgers().items()}
    LEDGER_FILE.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")


_MISSING = object()


@dataclass(frozen=True)
class Case:
    name: str
    required: str          # which required fixture this is (or "extra")
    base: str
    new_src: str
    expect_gate: GateDecision
    expect_outcome: RunOutcome
    ledger_override: Any = _MISSING   # used by unavailable-ledger cases
    orphan_policy: OrphanPolicy = OrphanPolicy.WARN
    repeat_policy: RepeatPolicy = RepeatPolicy.AUTO


def _conflicting_ledger(text: str) -> str:
    raw = json.loads(text)
    dup = dict(raw["records"][0], result="sim:tampered")
    raw["records"].append(dup)
    return json.dumps(raw)


def _mismatched_ledger(text: str) -> str:
    raw = json.loads(text)
    site = sorted(raw["frozen_sites"])[0]
    raw["frozen_sites"][site]["fingerprint"] = "0" * 64
    return json.dumps(raw)


def cases() -> List[Case]:
    frozen = load_frozen_ledgers()
    return [
        Case("happy_retained_replay", "extra:happy-path", "base", HAPPY_NEW,
             GateDecision.ACCEPT, RunOutcome.COMPLETED),
        Case("literal_argument_edit", "extra:literal-edit", "base", LITERAL_EDIT_NEW,
             GateDecision.REJECT, RunOutcome.NOT_RUN_GATE_REJECTED),
        Case("unchanged_expression_changed_variable", "1:unchanged-expression/changed-variable", "base",
             CHANGED_VARIABLE_NEW, GateDecision.ACCEPT, RunOutcome.STOPPED_DIVERGENCE),
        Case("relocation", "2:relocation", "base", RELOCATION_NEW,
             GateDecision.REJECT, RunOutcome.NOT_RUN_GATE_REJECTED),
        Case("orphan_warn", "3:unreachable-call/orphan", "base", ORPHAN_NEW,
             GateDecision.ACCEPT, RunOutcome.COMPLETED_WITH_ORPHANS, orphan_policy=OrphanPolicy.WARN),
        Case("orphan_stop", "3:unreachable-call/orphan", "base", ORPHAN_NEW,
             GateDecision.ACCEPT, RunOutcome.STOPPED_ORPHAN, orphan_policy=OrphanPolicy.STOP),
        Case("fanout_path_shift", "4:fanout/path-shift", "fanout", FANOUT_SHIFT_NEW,
             GateDecision.ACCEPT, RunOutcome.STOPPED_DIVERGENCE),
        Case("fanout_append", "4:fanout/path-shift", "fanout", FANOUT_APPEND_NEW,
             GateDecision.ACCEPT, RunOutcome.COMPLETED),
        Case("unavailable_ledger_missing", "5:unavailable-ledger", "base", HAPPY_NEW,
             GateDecision.HOLD, RunOutcome.HELD_LEDGER_UNAVAILABLE, ledger_override=None),
        Case("unavailable_ledger_corrupt", "5:unavailable-ledger", "base", HAPPY_NEW,
             GateDecision.HOLD, RunOutcome.HELD_LEDGER_UNAVAILABLE, ledger_override='{"version": 1, "records": ['),
        Case("unavailable_ledger_conflict", "5:unavailable-ledger", "base", HAPPY_NEW,
             GateDecision.HOLD, RunOutcome.HELD_LEDGER_UNAVAILABLE,
             ledger_override=_conflicting_ledger(frozen["base"])),
        Case("unavailable_ledger_mismatch", "5:unavailable-ledger", "base", HAPPY_NEW,
             GateDecision.HOLD, RunOutcome.HELD_LEDGER_UNAVAILABLE,
             ledger_override=_mismatched_ledger(frozen["base"])),
        Case("occurrence_extension_auto_stop", "extra:occurrence-extension", "retry", RETRY_NEW,
             GateDecision.ACCEPT, RunOutcome.STOPPED_REPEAT),
        Case("occurrence_extension_warn", "extra:occurrence-extension", "retry", RETRY_NEW,
             GateDecision.ACCEPT, RunOutcome.COMPLETED, repeat_policy=RepeatPolicy.WARN),
    ]


def run_case(case: Case):
    frozen = load_frozen_ledgers()
    committed = frozen[case.base] if case.ledger_override is _MISSING else case.ledger_override
    return revise(OLD_SOURCES[case.base], case.new_src, committed, INPUTS,
                  orphan_policy=case.orphan_policy, repeat_policy=case.repeat_policy)


def summary() -> Dict[str, Any]:
    frozen = {k: load_ledger_text(v) for k, v in load_frozen_ledgers().items()}
    rows = []
    totals = {"cases": 0, "naive_dispatches": 0, "contract_dispatches": 0,
              "completed_repairs": 0, "naive_dispatches_completed": 0, "dispatches_saved_completed": 0,
              "spend_avoided_by_stops": 0,
              "replayed": 0, "orphans": 0, "divergence_stops": 0, "gate_rejects": 0,
              "ledger_holds": 0, "repeat_stops": 0, "repeated_dispatch_at_retained_identity": 0}
    for case in cases():
        rep = run_case(case)
        retained_repeats = len(rep.run.repeated_dispatch_at_retained(frozen[case.base]))
        rows.append({"case": case.name, "required": case.required,
                     "gate": rep.gate.decision.value, "outcome": rep.run.outcome.value,
                     "naive": rep.naive_dispatches, "dispatched": rep.run.dispatch_count,
                     "saved": rep.dispatches_saved, "avoided": rep.spend_avoided_by_stop,
                     "replayed": len(rep.run.replayed), "orphans": len(rep.run.orphans)})
        totals["cases"] += 1
        totals["naive_dispatches"] += rep.naive_dispatches
        totals["contract_dispatches"] += rep.run.dispatch_count
        if rep.completed:
            totals["completed_repairs"] += 1
            totals["naive_dispatches_completed"] += rep.naive_dispatches
        totals["dispatches_saved_completed"] += rep.dispatches_saved
        totals["spend_avoided_by_stops"] += rep.spend_avoided_by_stop
        totals["replayed"] += len(rep.run.replayed)
        totals["orphans"] += len(rep.run.orphans)
        totals["divergence_stops"] += rep.run.outcome is RunOutcome.STOPPED_DIVERGENCE
        totals["gate_rejects"] += rep.gate.decision is GateDecision.REJECT
        totals["ledger_holds"] += rep.gate.decision is GateDecision.HOLD
        totals["repeat_stops"] += rep.run.outcome is RunOutcome.STOPPED_REPEAT
        totals["repeated_dispatch_at_retained_identity"] += retained_repeats
    return {"rows": rows, "totals": totals}


def main() -> None:
    s = summary()
    print("SYNTHETIC call-level revision contract fixtures (toy workflows, stub provider)")
    hdr = f"{'case':40s} {'gate':7s} {'outcome':24s} naive disp saved avoid replay orphan"
    print(hdr)
    for r in s["rows"]:
        print(f"{r['case']:40s} {r['gate']:7s} {r['outcome']:24s} {r['naive']:5d} {r['dispatched']:4d} "
              f"{r['saved']:5d} {r['avoided']:5d} {r['replayed']:6d} {r['orphans']:6d}")
    t = s["totals"]
    print("SYNTHETIC totals:")
    for k, v in t.items():
        print(f"  {k}: {int(v)}")
    print("SYNTHETIC note: no repeated dispatch at a retained identity in these fixtures; "
          "this is not a universal exactly-once claim.")


if __name__ == "__main__":
    main()
