"""Declared synthetic fixtures for w21-unused-contradiction.

Every contradiction here is a DECLARED FIXTURE LABEL written by hand
("contradicts": <belief id>). Nothing is inferred from text. The expected
outcome of each case comes from the hand-written STATUS and EXPECT tables
below, not from the module under test.

Run: python3 fixtures.py   (prints the measurement table, then one JSON
line; exits 1 if any case disagrees with its expected label)
"""

import json
import sys

import unused_contradiction as U


def belief(i, state):
    return {"kind": "belief", "id": i, "state": state}


def act(i, state):
    return {"kind": "act", "id": i, "state": state}


def evidence(i, contradicts):
    return {"kind": "evidence", "id": i, "contradicts": contradicts}


def unlabeled(i):
    return {"kind": "evidence", "id": i}


def flag(i, target):
    return {"kind": "flag", "id": i, "target": target}


def repair(i, state):
    return {"kind": "repair", "id": i, "state": state}


def episode(eid, steps, task_done=True, wait=None):
    ep = {"episode_id": eid, "contradiction_labels": "declared_fixture",
          "task_done": task_done, "steps": steps}
    if wait is not None:
        ep["wait"] = wait
    return ep


# The response shapes of the grid. b1 holds state "total" and is the
# contradicted belief; a2 (an act) holds the other state "route".
RESPONSES = {
    "none": lambda: [belief("b1", "total"), act("a2", "route"), evidence("e1", "b1")],
    "flag": lambda: [belief("b1", "total"), act("a2", "route"), evidence("e1", "b1"),
                     flag("f1", "b1")],
    "repair": lambda: [belief("b1", "total"), act("a2", "route"), evidence("e1", "b1"),
                       repair("r1", "total")],
    "flag_then_repair": lambda: [belief("b1", "total"), act("a2", "route"), evidence("e1", "b1"),
                                 flag("f1", "b1"), repair("r1", "total")],
    "repair_then_reassert": lambda: [belief("b1", "total"), act("a2", "route"),
                                     evidence("e1", "b1"), repair("r1", "total"),
                                     belief("b3", "total")],
    "repair_other_state": lambda: [belief("b1", "total"), act("a2", "route"),
                                   evidence("e1", "b1"), repair("r1", "route")],
    "repair_before_evidence": lambda: [belief("b1", "total"), act("a2", "route"),
                                       repair("r1", "total"), evidence("e1", "b1")],
    "repair_after_overwrite": lambda: [belief("b1", "total"), act("a2", "route"),
                                       evidence("e1", "b1"), belief("b3", "total"),
                                       repair("r1", "total")],
    "flag_before_evidence": lambda: [belief("b1", "total"), act("a2", "route"),
                                     flag("f1", "b1"), evidence("e1", "b1")],
}

# Hand-written: what happened to the contradiction in each shape.
STATUS = {
    "none": "unused",
    "flag": "flagged",
    "repair": "repaired",
    "flag_then_repair": "repaired",
    "repair_then_reassert": "reasserted",
    "repair_other_state": "unused",
    "repair_before_evidence": "unused",
    "repair_after_overwrite": "unused",
    "flag_before_evidence": "unused",
}

EXTRAS = ("neutral", "unlabeled")


def make_case(response, task_done, extra):
    steps = RESPONSES[response]()
    steps.append(evidence("e2", None) if extra == "neutral" else unlabeled("e2"))
    eid = "%s/%s/%s" % (response, "done" if task_done else "not_done", extra)
    return episode(eid, steps, task_done)


GRID = tuple(make_case(r, t, x) for r in sorted(RESPONSES) for t in (True, False) for x in EXTRAS)


def expect(eid, policy):
    """Expected (verdict, reason) for a grid case, from the tables above."""
    response, done, extra = eid.split("/")
    status = STATUS[response]
    if done != "done":
        return U.FAIL, U.TASK_NOT_DONE
    if policy == U.SYMPTOM_ONLY:
        return U.SUCCESS, U.CONSUMED
    if status == "unused":
        return U.FAIL, U.UNUSED_CONTRADICTION
    if status == "reasserted":
        return U.FAIL, U.REASSERTED_AFTER_REPAIR
    if status == "flagged" and policy == U.CONSUME:
        return U.FAIL, U.FLAG_WITHOUT_REPAIR
    if extra == "unlabeled":
        return U.ON_UNMEASURED, U.UNLABELED_EVIDENCE
    return U.SUCCESS, U.CONSUMED


# Named design fixtures for the done-when tests, each with its expected
# (verdict, reason) under CONSUME.
DESIGN = {
    "a_unused": (episode("a_unused", RESPONSES["none"]()), (U.FAIL, U.UNUSED_CONTRADICTION)),
    "b_flag_only": (episode("b_flag_only", RESPONSES["flag"]()), (U.FAIL, U.FLAG_WITHOUT_REPAIR)),
    "c_repair": (episode("c_repair", RESPONSES["repair"]()), (U.SUCCESS, U.CONSUMED)),
    "c_two_repaired": (episode("c_two_repaired", [
        belief("b1", "total"), act("a2", "route"), evidence("e1", "b1"), evidence("e2", "a2"),
        repair("r1", "route"), repair("r2", "total")]), (U.SUCCESS, U.CONSUMED)),
    "d_one_of_two": (episode("d_one_of_two", [
        belief("b1", "total"), act("a2", "route"), evidence("e1", "b1"), evidence("e2", "a2"),
        repair("r1", "total")]), (U.FAIL, U.UNUSED_CONTRADICTION)),
    "d_other_state": (episode("d_other_state", RESPONSES["repair_other_state"]()),
                      (U.FAIL, U.UNUSED_CONTRADICTION)),
    "d_before_evidence": (episode("d_before_evidence", RESPONSES["repair_before_evidence"]()),
                          (U.FAIL, U.UNUSED_CONTRADICTION)),
    "d_after_overwrite": (episode("d_after_overwrite", RESPONSES["repair_after_overwrite"]()),
                          (U.FAIL, U.UNUSED_CONTRADICTION)),
    "d_reasserted_after_repair": (episode("d_reasserted_after_repair", [
        belief("b1", "total"), evidence("e1", "b1"), repair("r1", "total"), belief("b3", "total")]),
        (U.FAIL, U.REASSERTED_AFTER_REPAIR)),
    "d_reacted_after_repair": (episode("d_reacted_after_repair", [
        belief("b1", "total"), evidence("e1", "b1"), repair("r1", "total"), act("a3", "total")]),
        (U.FAIL, U.REASSERTED_AFTER_REPAIR)),
    "c_other_state_after_repair": (episode("c_other_state_after_repair", [
        belief("b1", "total"), evidence("e1", "b1"), repair("r1", "total"), belief("b3", "route")]),
        (U.SUCCESS, U.CONSUMED)),
    "d_superseded_holder": (episode("d_superseded_holder", [
        belief("b1", "total"), belief("b2", "total"), evidence("e1", "b1"), repair("r1", "total")]),
        (U.FAIL, U.UNUSED_CONTRADICTION)),
    "d_flag_and_wrong_repair": (episode("d_flag_and_wrong_repair", [
        belief("b1", "total"), act("a2", "route"), evidence("e1", "b1"), flag("f1", "b1"),
        repair("r1", "route")]), (U.FAIL, U.FLAG_WITHOUT_REPAIR)),
    "e_unlabeled": (episode("e_unlabeled", [belief("b1", "total"), unlabeled("e1")]),
                    (U.ON_UNMEASURED, U.UNLABELED_EVIDENCE)),
    "neutral_only": (episode("neutral_only", [belief("b1", "total"), evidence("e1", None)]),
                     (U.SUCCESS, U.CONSUMED)),
}


def check(out=print):
    """Compare every case with its expected label; return the mismatch count."""
    bad = 0
    for name in sorted(DESIGN):
        ep, want = DESIGN[name]
        rec = U.decide(ep, U.CONSUME)
        if (rec["verdict"], rec["reason"]) != want:
            bad += 1
            out("design mismatch %s: %r != %r" % (name, (rec["verdict"], rec["reason"]), want))
    for ep in GRID:
        for policy in U.POLICIES:
            rec = U.decide(ep, policy)
            want = expect(ep["episode_id"], policy)
            if (rec["verdict"], rec["reason"]) != want:
                bad += 1
                out("grid mismatch %s %s: %r != %r" % (ep["episode_id"], policy,
                                                      (rec["verdict"], rec["reason"]), want))
    return bad


def measure():
    """Success rates per policy over the grid, and false successes against CONSUME."""
    gate = dict((ep["episode_id"], U.decide(ep, U.CONSUME)["verdict"]) for ep in GRID)
    rows = []
    for policy in U.POLICIES:
        verdicts = [(ep["episode_id"], U.decide(ep, policy)["verdict"]) for ep in GRID]
        success = sum(1 for _, v in verdicts if v == U.SUCCESS)
        false_success = sum(1 for eid, v in verdicts if v == U.SUCCESS and gate[eid] != U.SUCCESS)
        rows.append({"policy": policy, "n": len(verdicts), "success": success,
                     "success_over_gate": false_success})
    return rows


def main():
    bad = check()
    rows = measure()
    print("%-22s %4s %8s %18s" % ("policy", "n", "success", "success_over_gate"))
    for r in rows:
        print("%-22s %4d %8d %18d" % (r["policy"], r["n"], r["success"], r["success_over_gate"]))
    print("n_cases=%d (synthetic declared fixtures only)" % len(GRID))
    print(json.dumps({"rows": rows, "mismatches": bad}, sort_keys=True))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
