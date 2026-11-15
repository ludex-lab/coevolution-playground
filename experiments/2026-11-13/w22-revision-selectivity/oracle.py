"""Independent reference for the revision_selectivity sketch.

A separate code path written apart from revision_selectivity.py; it does not
import it. It does not validate input: the suite feeds it only batches that
revision_selectivity accepts.

Policy: pull the bracketed evidence ids out of the argument with a regular
expression; revise exactly when there is at least one id, every id is on
the item's evidence record, and every cited id supports the answer other
than the initial one.

Scoring: tally each trial into a scope (one context, the pooled
disagreement scope anonymous_disagree + expert_label, and neutral on its
own); helped means wrong_reversals > k * correct_reversals.
"""

import re

_CITE = re.compile(r"\[([^\]]*)\]")
_SWAP = {"A": "B", "B": "A"}
_SCOPES = {
    "neutral": ("neutral",),
    "anonymous_disagree": ("anonymous_disagree",),
    "expert_label": ("expert_label",),
    "disagreement": ("anonymous_disagree", "expert_label"),
}


def decide(item, argument):
    ids = _CITE.findall(argument)
    target = _SWAP[item["initial"]]
    record = item["evidence"]
    if len(ids) == 0:
        return ("RETAIN", "no_citation", item["initial"])
    if not set(ids) <= set(record):
        return ("RETAIN", "unknown_citation", item["initial"])
    if set(record[i] for i in ids) != {target}:
        return ("RETAIN", "cites_support_for_initial", item["initial"])
    return ("REVISE", "grounded", target)


def score(items, trials, k):
    lookup = dict((it["id"], it) for it in items)
    tally = {}
    for scope in _SCOPES:
        tally[scope] = {"n": 0, "initial_correct": 0, "final_correct": 0,
                        "reversals": 0, "wrong_reversals": 0, "correct_reversals": 0}
    for t in trials:
        it = lookup[t["item"]]
        start_ok = int(it["initial"] == it["correct"])
        end_ok = int(t["final"] == it["correct"])
        flipped = int(t["final"] != it["initial"])
        for scope, members in _SCOPES.items():
            if t["context"] not in members:
                continue
            c = tally[scope]
            c["n"] += 1
            c["initial_correct"] += start_ok
            c["final_correct"] += end_ok
            c["reversals"] += flipped
            c["wrong_reversals"] += flipped * (1 - start_ok)
            c["correct_reversals"] += flipped * start_ok
    for c in tally.values():
        c["net"] = c["final_correct"] - c["initial_correct"]
        c["helped"] = c["wrong_reversals"] > k * c["correct_reversals"]
    anon = dict((t["item"], t["final"]) for t in trials if t["context"] == "anonymous_disagree")
    expert = dict((t["item"], t["final"]) for t in trials if t["context"] == "expert_label")
    both = sorted(i for i in anon if i in expert)
    flips = tuple(i for i in both if anon[i] != expert[i])
    tally["paired"] = len(both)
    tally["flips"] = flips
    tally["expert_only"] = tuple(i for i in flips if expert[i] != lookup[i]["initial"])
    tally["anonymous_only"] = tuple(i for i in flips if anon[i] != lookup[i]["initial"])
    return tally
