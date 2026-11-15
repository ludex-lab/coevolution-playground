"""Synthetic fixtures for the memory-admission sketch.

A toy file-handling world. Each task has features {kind, size}; the agent's
untrained default is parse_whole. The ground truth, used only to label the
fixtures (never consulted by memory_admission), is:

    kind=log            -> tail
    size in large, huge -> parse_stream
    otherwise           -> parse_whole

The seed store already holds one archived lesson, L0 (kind=log -> tail),
and the shared archive holds tasks the seed store solves. Each candidate
comes from an episode that went well locally (local_success True); the
probes decide whether that local success generalizes.

Run: python3 fixtures.py   (prints one admission record per candidate)
"""

import json

import memory_admission as M

DEFAULT_ACTION = "parse_whole"


def truth(features):
    if features.get("kind") == "log":
        return "tail"
    if features.get("size") in ("large", "huge"):
        return "parse_stream"
    return "parse_whole"


def task(tid, kind, size):
    features = {"kind": kind, "size": size}
    return {"id": tid, "features": features,
            "default_action": DEFAULT_ACTION, "expected_action": truth(features)}


SEED_LESSON = {"id": "L0", "precondition": "kind=log", "behavior_change": "tail",
               "expected_effect": "log files are read from the end",
               "verifier": M.ACTION_MATCHES_EXPECTED}


def seed_store():
    return M.MemoryStore([SEED_LESSON])


def archive():
    """Shared archived tasks; the seed store solves every one of them."""
    return [
        task("arc-json-small", "json", "small"),
        task("arc-log-large", "log", "large"),
        task("arc-log-small", "log", "small"),
    ]


def hypothesis(hid, precondition, behavior_change, expected_effect):
    return {"id": hid, "precondition": precondition,
            "behavior_change": behavior_change,
            "expected_effect": expected_effect,
            "verifier": M.ACTION_MATCHES_EXPECTED}


THRESHOLDS = {"refine_min_gain_pct": 50, "refine_max_risk_pct": 0}

# Each candidate: hypothesis, transfer tasks, falsification tasks.
CANDIDATES = {
    # (b) sound lesson: passes all three probes.
    "good": (
        hypothesis("H-good", "size=large", "parse_stream",
                   "large inputs are parsed as a stream"),
        [task("tr-csv-large", "csv", "large"), task("tr-json-large", "json", "large")],
        [task("fa-xml-large", "xml", "large"), task("fa-log-large", "log", "large")],
    ),
    # (a1) over-general: learned on a large csv, claims every csv.
    "false": (
        hypothesis("H-false", "kind=csv", "parse_stream",
                   "csv inputs are parsed as a stream"),
        [task("tr-csv-large-2", "csv", "large"), task("tr-csv-huge", "csv", "huge")],
        [task("fa-csv-small", "csv", "small"), task("fa-csv-large", "csv", "large")],
    ),
    # (a2) breaks an archived task; its falsification set is too weak to
    # notice, so only the archived-regression probe catches it.
    "breaks_archive": (
        hypothesis("H-breaks", "kind=json", "parse_stream",
                   "json inputs are parsed as a stream"),
        [task("tr-json-large-2", "json", "large"), task("tr-json-huge", "json", "huge")],
        [task("fa-json-large", "json", "large")],
    ),
    # (a3) harmless but useless: never helps a target task.
    "no_transfer": (
        hypothesis("H-noop", "kind=xml", "parse_whole",
                   "xml inputs are parsed whole"),
        [task("tr-csv-large-3", "csv", "large")],
        [task("fa-xml-small", "xml", "small")],
    ),
    # refine: sound but narrow; helps 1 of 2 target tasks.
    "narrow": (
        hypothesis("H-narrow", "size=huge", "parse_stream",
                   "huge inputs are parsed as a stream"),
        [task("tr-csv-huge-2", "csv", "huge"), task("tr-csv-large-4", "csv", "large")],
        [task("fa-json-huge", "json", "huge")],
    ),
}

# A later task, not part of any probe, used to show a committed lesson is
# visible afterwards.
LATER_TASK = task("later-tsv-large", "tsv", "large")


def request(name, drop=(), **overrides):
    """Admission request for a named candidate; drop omits probes."""
    hyp, transfer, falsification = CANDIDATES[name]
    probes = {M.TARGET_TRANSFER: transfer, M.FALSIFICATION: falsification,
              M.ARCHIVED_REGRESSION: archive()}
    for probe in drop:
        del probes[probe]
    req = {"hypothesis": dict(hyp), "local_success": True, "probes": probes,
           "thresholds": dict(THRESHOLDS)}
    req.update(overrides)
    return req


def all_tasks():
    out = list(archive()) + [LATER_TASK]
    for _, transfer, falsification in CANDIDATES.values():
        out.extend(transfer)
        out.extend(falsification)
    return out


def main():
    for name in CANDIDATES:
        store = seed_store()
        rec = M.admit(store, request(name))
        print(json.dumps({"candidate": name, "outcome": rec["outcome"],
                          "reason": rec["reason"],
                          "failed_probes": list(rec["failed_probes"]),
                          "store_ids": list(store.ids())}, sort_keys=True))


if __name__ == "__main__":
    main()
