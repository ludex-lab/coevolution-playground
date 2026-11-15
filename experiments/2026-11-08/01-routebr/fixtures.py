"""Frozen SYNTHETIC toy routes. No model, external action, or paper benchmark."""
from dataclasses import dataclass
from routing import (Action, Choice, Proposal, RegisteredObject, Rule, Snapshot,
                     State, Verdict, route, unsafe_fallback_baseline)

SNAPSHOT = Snapshot(
    "toy-catalog.v1", "toy-registry.v1", "toy-rules.v1", "toy-state.v1",
    "2026-11-08T08:00:00+09:00",
    (Action("paint", ("tile",)), Action("describe", ("tile",)),
     Action("ring", ("bell",)), Action("wave", ())),
    (RegisteredObject("tile-blue", "tile"), RegisteredObject("bell-small", "bell")),
    (Rule("paint-ready", "paint", ("paint_ready",)),
     Rule("describe-ready", "describe", ("online",)),
     Rule("ring-ready", "ring", ("online",)), Rule("wave-ready", "wave", ("online",))),
)
READY = State("toy-state.v1", SNAPSHOT.frozen_time, (("online", True), ("paint_ready", True)))
BLOCKED = State("toy-state.v1", SNAPSHOT.frozen_time, (("online", True), ("paint_ready", False)))


def proposal(action, object_id, *candidates):
    return Proposal(Choice(action, object_id), tuple(candidates), SNAPSHOT.versions)


@dataclass(frozen=True)
class Case:
    name: str
    proposal: Proposal
    state: State
    expected_gate: Verdict
    expected_baseline: Verdict
    expected_unsafe_object: bool = False
    expected_substitution: bool = False


CASES = (
    Case("primary-ok", proposal("paint", "tile-blue"), READY, Verdict.DISPATCH, Verdict.DISPATCH),
    Case("state-block", proposal("paint", "tile-blue"), BLOCKED, Verdict.NON_DISPATCH, Verdict.NON_DISPATCH),
    Case("unknown-object", proposal("describe", "tile-ghost"), READY, Verdict.NON_DISPATCH, Verdict.NON_DISPATCH),
    Case("wrong-type", proposal("describe", "bell-small"), READY, Verdict.NON_DISPATCH, Verdict.NON_DISPATCH),
    Case("valid-secondary", proposal("paint", "tile-blue", Choice("describe", "tile-blue")), BLOCKED,
         Verdict.NON_DISPATCH, Verdict.DISPATCH, False, True),
    Case("unknown-secondary-object", proposal("paint", "tile-blue", Choice("describe", "tile-ghost")), BLOCKED,
         Verdict.NON_DISPATCH, Verdict.DISPATCH, True, True),
    Case("wrong-secondary-type", proposal("paint", "tile-blue", Choice("describe", "bell-small")), BLOCKED,
         Verdict.NON_DISPATCH, Verdict.DISPATCH, True, True),
    Case("missing-primary-object", proposal("paint", None, Choice("ring", "tile-blue")), READY,
         Verdict.NON_DISPATCH, Verdict.DISPATCH, True, True),
    Case("unknown-primary-action", proposal("teleport", "tile-blue", Choice("wave", None)), READY,
         Verdict.NON_DISPATCH, Verdict.DISPATCH, False, True),
    Case("object-free", proposal("wave", None), READY, Verdict.DISPATCH, Verdict.DISPATCH),
    Case("object-on-free-action", proposal("wave", "tile-blue"), READY, Verdict.NON_DISPATCH, Verdict.NON_DISPATCH),
    Case("audit-ignored-on-success", proposal("paint", "tile-blue", Choice("describe", "tile-ghost")), READY,
         Verdict.DISPATCH, Verdict.DISPATCH),
)


def unsafe_object(dispatch):
    """Independent fixture oracle: registry membership and action contract only."""
    if dispatch is None:
        return False
    contract = next((a for a in SNAPSHOT.actions if a.identifier == dispatch.action), None)
    if contract is None:
        return True
    if not contract.object_types:
        return dispatch.object_id is not None
    obj = next((x for x in SNAPSHOT.objects if x.identifier == dispatch.object_id), None)
    return obj is None or obj.kind not in contract.object_types


def compare():
    counts = dict(cases=len(CASES), gate_dispatches=0, baseline_dispatches=0,
                  gate_unsafe_objects=0, baseline_unsafe_objects=0,
                  gate_substitutions=0, baseline_substitutions=0)
    for case in CASES:
        for name, controller in (("gate", route), ("baseline", unsafe_fallback_baseline)):
            result = controller(case.proposal, SNAPSHOT, case.state)
            if result.verdict is Verdict.DISPATCH:
                counts[name + "_dispatches"] += 1
                counts[name + "_unsafe_objects"] += int(unsafe_object(result.dispatch))
                counts[name + "_substitutions"] += int(
                    (result.dispatch.action, result.dispatch.object_id)
                    != (case.proposal.primary.action, case.proposal.primary.object_id))
    return counts


if __name__ == "__main__":
    for case in CASES:
        gate = route(case.proposal, SNAPSHOT, case.state)
        baseline = unsafe_fallback_baseline(case.proposal, SNAPSHOT, case.state)
        print(f"SYNTHETIC {case.name}: gate={gate.verdict.value}:{gate.reason.value} "
              f"baseline={baseline.verdict.value}:{baseline.reason.value} "
              f"baseline_record={baseline.dispatch}")
    print("SYNTHETIC totals:", compare())
