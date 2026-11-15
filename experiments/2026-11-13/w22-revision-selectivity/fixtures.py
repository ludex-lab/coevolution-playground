"""Frozen synthetic fixtures for the revision_selectivity sketch.

Every "correct" answer, initial answer, evidence label and recorded final
answer below is a fixture label written by hand. None of it comes from the
paper, its data or any model output.

- HELP_RULE: the declared fixture threshold for a help claim.
- POLICY_ITEMS: items for the prestige-blind policy (decide / second_pass).
- BATCHES: recorded second-pass logs of a hypothetical label-sensitive
  reviser (final answers given), scored by score().
- EXPECTED_*: the hand-written expected table.

Run: python3 -B fixtures.py   (prints the summary also shown in README.md)
"""

import revision_selectivity as R

# Declared fixture threshold: a batch is "helped" only when its wrong-initial
# reversals exceed this many times its correct-initial reversals. A choice
# for these fixtures, not a value taken from the paper.
HELP_RULE = {"min_wrong_per_correct": 3}


def _item(item_id, correct, initial, argument, evidence):
    return {"id": item_id,
            "question": "Fixture question %s: answer A or B." % item_id,
            "correct": correct, "initial": initial,
            "argument": argument, "evidence": evidence}


POLICY_ITEMS = [
    # wrong initial, argument cites on-record evidence for the other answer
    _item("p01", "A", "B", "Record [E1] points to A.", {"E1": "A", "E2": "B"}),
    # correct initial, argument cites evidence that supports the initial
    _item("p02", "A", "A", "Weigh [E1] again; I read it as B.", {"E1": "A", "E2": "B"}),
    # correct initial, appeal to authority with no citation
    _item("p03", "B", "B", "Most specialists would answer A.", {"E1": "B"}),
    # correct initial, on-record evidence for the other answer: the policy
    # revises and abandons a correct answer (it is not a truth oracle)
    _item("p04", "A", "A", "Record [E2] points to B.", {"E1": "A", "E2": "B"}),
    # wrong initial, cites an id that is not on record
    _item("p05", "B", "A", "See [E7]; it settles B.", {"E1": "B"}),
    # wrong initial, two on-record citations for the other answer
    _item("p06", "B", "A", "[E1] and [E2] both point to B.", {"E1": "B", "E2": "B"}),
    # wrong initial, mixed citations
    _item("p07", "A", "B", "[E1] points to A, though [E2] points to B.", {"E1": "A", "E2": "B"}),
    # correct initial, self-declared expertise, no citation, empty record
    _item("p08", "B", "B", "As an expert I am certain it is A.", {}),
]

EXPECTED_DECISIONS = {
    "p01": ("REVISE", "grounded"),
    "p02": ("RETAIN", "cites_support_for_initial"),
    "p03": ("RETAIN", "no_citation"),
    "p04": ("REVISE", "grounded"),
    "p05": ("RETAIN", "unknown_citation"),
    "p06": ("REVISE", "grounded"),
    "p07": ("RETAIN", "cites_support_for_initial"),
    "p08": ("RETAIN", "no_citation"),
}


def _recorded(n_correct, n_wrong, reversed_by):
    """Items r01.. (first n_correct have a correct initial, the rest a wrong
    one) and one trial per item for each context in reversed_by. A trial's
    final is the other answer when the item id is listed for that context."""
    items = []
    for i in range(1, n_correct + n_wrong + 1):
        item_id = "r%02d" % i
        correct = "A" if i % 2 else "B"
        other = "B" if correct == "A" else "A"
        initial = correct if i <= n_correct else other
        items.append(_item(item_id, correct, initial,
                           "Reconsider %s: the other option fits the record better." % item_id,
                           {}))
    trials = []
    for context in R.CONTEXTS:
        if context not in reversed_by:
            continue
        for item in items:
            flip = "B" if item["initial"] == "A" else "A"
            final = flip if item["id"] in reversed_by[context] else item["initial"]
            trials.append({"item": item["id"], "context": context,
                           "argument": item["argument"], "final": final})
    return {"items": items, "trials": trials}


BATCHES = {
    # (b) mostly reverses correct initials: 7 of 9 disagreement reversals.
    "hurt": _recorded(8, 2, {
        "anonymous_disagree": ("r01", "r02", "r09"),
        "expert_label": ("r01", "r02", "r03", "r04", "r05", "r10"),
    }),
    # (b) mostly reverses wrong initials: 6 of 7 disagreement reversals.
    "helped": _recorded(4, 6, {
        "anonymous_disagree": ("r05", "r06", "r07"),
        "expert_label": ("r08", "r09", "r10", "r01"),
    }),
    # (b) border: wrong reversals equal k * correct reversals; net gain > 0.
    "border": _recorded(4, 4, {
        "anonymous_disagree": ("r05", "r06"),
        "expert_label": ("r07", "r01"),
    }),
    # (c) neutral reflection reverses only wrong initials; disagreement does not
    # clear the threshold.
    "mixed": _recorded(6, 6, {
        "neutral": ("r07", "r08", "r09", "r10", "r11", "r12"),
        "anonymous_disagree": ("r07",),
        "expert_label": ("r01",),
    }),
}

# Hand-written: scope -> (n, wrong_reversals, correct_reversals, helped);
# "flips" are items whose anonymous and expert outcomes differ.
EXPECTED_SCORES = {
    "policy": {
        "neutral": (8, 2, 1, False), "anonymous_disagree": (8, 2, 1, False),
        "expert_label": (8, 2, 1, False), "disagreement": (16, 4, 2, False),
        "flips": (),
    },
    "hurt": {
        "neutral": (0, 0, 0, False), "anonymous_disagree": (10, 1, 2, False),
        "expert_label": (10, 1, 5, False), "disagreement": (20, 2, 7, False),
        "flips": ("r03", "r04", "r05", "r09", "r10"),
    },
    "helped": {
        "neutral": (0, 0, 0, False), "anonymous_disagree": (10, 3, 0, True),
        "expert_label": (10, 3, 1, False), "disagreement": (20, 6, 1, True),
        "flips": ("r01", "r05", "r06", "r07", "r08", "r09", "r10"),
    },
    "border": {
        "neutral": (0, 0, 0, False), "anonymous_disagree": (8, 2, 0, True),
        "expert_label": (8, 1, 1, False), "disagreement": (16, 3, 1, False),
        "flips": ("r01", "r05", "r06", "r07"),
    },
    "mixed": {
        "neutral": (12, 6, 0, True), "anonymous_disagree": (12, 1, 0, True),
        "expert_label": (12, 0, 1, False), "disagreement": (24, 1, 1, False),
        "flips": ("r01", "r07"),
    },
}

SCOPES = ("neutral", "anonymous_disagree", "expert_label", "disagreement")


def policy_batch():
    out = R.second_pass(POLICY_ITEMS)
    assert out["status"] == R.OK, out
    return {"items": POLICY_ITEMS, "trials": out["trials"]}


def all_batches():
    batches = {"policy": policy_batch()}
    batches.update(BATCHES)
    return batches


def summary():
    lines = ["help rule (declared fixture threshold): helped iff wrong_reversals > %d x correct_reversals"
             % HELP_RULE["min_wrong_per_correct"]]
    pol = policy_batch()
    same = 0
    for item in POLICY_ITEMS:
        finals = set(t["final"] for t in pol["trials"] if t["item"] == item["id"])
        same += 1 if len(finals) == 1 else 0
    lines.append("policy: %d items x %d contexts, same decision in every context for %d/%d items"
                 % (len(POLICY_ITEMS), len(R.CONTEXTS), same, len(POLICY_ITEMS)))
    lines.append("%-7s %-18s %3s %4s %4s %4s %4s  %s"
                 % ("batch", "scope", "n", "rev", "W", "C", "net", "claim"))
    for name, batch in all_batches().items():
        rep = R.score(batch["items"], batch["trials"], HELP_RULE)
        assert rep["status"] == R.OK, rep
        for scope in SCOPES:
            blk = rep["disagreement"] if scope == "disagreement" else rep["by_context"][scope]
            lines.append("%-7s %-18s %3d %4d %4d %4d %+4d  %s" % (
                name, scope, blk["n"], blk["reversals"], blk["wrong_reversals"],
                blk["correct_reversals"], blk["net"], blk["claim"]))
        lines.append("%-7s %-18s %s" % (name, "prestige flips",
                                        ",".join(rep["prestige"]["flips"]) or "none"))
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
