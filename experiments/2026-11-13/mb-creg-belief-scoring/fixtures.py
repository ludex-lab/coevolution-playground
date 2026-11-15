"""Frozen synthetic suite for the creg_belief sketch.

Every scenario is hand-written and synthetic: one pressure gauge
("gauge-7") is anomalous or normal; a robot, IoT sensors and an edge
module report on it, or on a sensor that a measures relation ties to it.
No paper data is used. SUITE_SHA256 freezes the suite and REFERENCE
freezes the normative posterior (4 decimals), contradiction flag and action
at every prefix.

Run: python3 -B fixtures.py   (prints a deterministic summary)
"""

import hashlib
import json

import creg_belief as C
import oracle as O

TARGET = "gauge-7"
SOURCES = {"robot-1": 1.0, "iot-3": 0.8, "edge-2": 0.6, "iot-9": 0.25}
RELATIONS = [
    ["sensor-p3", "measures", "gauge-7"],
    ["sensor-p9", "measures", "gauge-9"],
    ["camera-1", "located_near", "gauge-7"],
]
REGIMES = ("revision", "preservation", "relation", "contradiction_onset",
           "contradiction_resolution", "stale", "reliability", "deadline")


def r(rid, source, entity, polarity, confidence, t, at=None, supersedes=None):
    out = {"id": rid, "source": source, "entity": entity, "polarity": polarity,
           "confidence": confidence, "t": t, "at": t if at is None else at}
    if supersedes is not None:
        out["supersedes"] = supersedes
    return out


def s(sid, regime, relation_dependent, reports, deadline=50, on_expiry="HOLD",
      max_age=3, prior=0.5):
    return {"id": sid, "regime": regime, "relation_dependent": relation_dependent,
            "target": TARGET, "prior": prior, "max_age": max_age,
            "deadline": deadline, "on_expiry": on_expiry,
            "relations": [list(x) for x in RELATIONS], "sources": dict(SOURCES),
            "reports": reports}


G = TARGET
SUITE = [
    # Justified revision: moderate evidence accumulates against a first lean.
    s("revision-a", "revision", False, [
        r("a1", "robot-1", G, 1, 0.85, 1),
        r("a2", "robot-1", G, -1, 0.7, 2),
        r("a3", "iot-3", G, -1, 0.7, 3),
        r("a4", "robot-1", G, -1, 0.7, 4),
        r("a5", "robot-1", G, -1, 0.7, 5),
        r("a6", "robot-1", G, -1, 0.7, 6),
    ], max_age=10),
    # Justified revision: a correction supersedes the first report.
    s("revision-b", "revision", False, [
        r("b1", "robot-1", G, 1, 0.95, 1),
        r("b2", "edge-2", G, -1, 0.8, 2, supersedes="b1"),
        r("b3", "iot-3", G, -1, 0.85, 3),
    ]),
    # Belief preservation: weak and unlinked reports do not move the action.
    s("preservation-a", "preservation", False, [
        r("c1", "robot-1", G, 1, 0.95, 1),
        r("c2", "edge-2", G, -1, 0.6, 2),
        r("c3", "robot-1", "camera-1", -1, 0.95, 3),
    ]),
    s("preservation-b", "preservation", False, [
        r("d1", "robot-1", G, -1, 0.95, 1),
        r("d2", "iot-3", "sensor-p9", 1, 0.95, 2),
        r("d3", "iot-9", G, 1, 0.8, 3),
    ]),
    # Relation association: the evidence is about sensor-p3 only.
    s("relation-a", "relation", True, [
        r("e1", "iot-3", "sensor-p3", 1, 0.95, 1),
        r("e2", "edge-2", "sensor-p3", 1, 0.7, 2),
    ]),
    s("relation-b", "relation", True, [
        r("f1", "robot-1", G, 1, 0.7, 1),
        r("f2", "iot-3", "sensor-p3", -1, 0.95, 2),
        r("f3", "edge-2", "sensor-p3", -1, 0.85, 3),
    ]),
    # Contradiction onset: strong reports disagree and stay disagreeing.
    s("contradiction-onset-a", "contradiction_onset", False, [
        r("g1", "robot-1", G, 1, 0.95, 1),
        r("g2", "iot-3", G, -1, 0.95, 2),
        r("g3", "edge-2", G, -1, 0.8, 3),
    ]),
    # The contradiction exists only through the measures relation.
    s("contradiction-onset-b", "contradiction_onset", True, [
        r("h1", "robot-1", G, 1, 0.95, 1),
        r("h2", "iot-3", "sensor-p3", -1, 0.95, 2),
    ]),
    # Contradiction opens at step 3 and resolves at step 4 when a delayed
    # correction (observed at t=1, arriving at 4) supersedes the robot.
    s("contradiction-resolution-a", "contradiction_resolution", False, [
        r("i1", "iot-3", G, 1, 0.7, 1),
        r("i2", "robot-1", G, 1, 0.85, 2),
        r("i3", "iot-3", G, -1, 0.95, 3),
        r("i4", "edge-2", G, -1, 0.8, 1, at=4, supersedes="i2"),
    ]),
    # Contradiction resolves when the supporting report goes stale.
    s("contradiction-resolution-b", "contradiction_resolution", False, [
        r("j1", "robot-1", G, 1, 0.95, 1),
        r("j2", "iot-3", G, -1, 0.85, 3),
        r("j3", "edge-2", G, -1, 0.85, 5),
        r("j4", "robot-1", G, -1, 0.8, 6),
    ]),
    # Stale evidence: a report that arrives already stale has no weight.
    s("stale-a", "stale", False, [
        r("k1", "robot-1", G, 1, 0.95, 1, at=6),
        r("k2", "iot-3", G, -1, 0.95, 6),
    ]),
    # Stale evidence: a decisive report ages out.
    s("stale-b", "stale", False, [
        r("l1", "robot-1", G, 1, 0.95, 1),
        r("l2", "edge-2", G, 1, 0.7, 2),
        r("l3", "iot-3", G, -1, 0.6, 5),
    ]),
    # Stale evidence through the relation: delayed but still fresh enough.
    s("stale-c", "stale", True, [
        r("m1", "iot-3", "sensor-p3", 1, 0.95, 2, at=4),
        r("m2", "robot-1", G, 1, 0.6, 5),
        r("m3", "edge-2", G, -1, 0.6, 7),
    ]),
    # Source reliability: a low-reliability source is not strong evidence.
    s("reliability-a", "reliability", False, [
        r("n1", "iot-9", G, 1, 0.95, 1),
        r("n2", "iot-9", G, 1, 0.95, 2),
        r("n3", "robot-1", G, -1, 0.8, 3),
    ]),
    s("reliability-b", "reliability", False, [
        r("o1", "edge-2", G, 1, 0.95, 1),
        r("o2", "iot-9", G, -1, 0.95, 2),
        r("o3", "robot-1", G, 1, 0.85, 3),
    ], prior=0.4),
    # Deadline: belief says dispatch, but the deadline has passed.
    s("deadline-a", "deadline", False, [
        r("p1", "robot-1", G, 1, 0.95, 1),
        r("p2", "iot-3", G, 1, 0.8, 4),
    ], deadline=4, on_expiry="HOLD"),
    # Deadline with an open contradiction: the declared on_expiry wins.
    s("deadline-b", "deadline", True, [
        r("q1", "robot-1", G, 1, 0.95, 1),
        r("q2", "iot-3", "sensor-p3", -1, 0.95, 2),
        r("q3", "edge-2", G, -1, 0.6, 3),
    ], deadline=3, on_expiry="ESCALATE"),
]

# Normative reference, frozen: (posterior to 4 decimals, contradiction, action)
# per prefix, as oracle.reference() produced it when the suite was frozen.
REFERENCE = {
    "revision-a": [
        (0.85, False, "GATHER_EVIDENCE"),
        (0.7083, False, "GATHER_EVIDENCE"),
        (0.5522, False, "GATHER_EVIDENCE"),
        (0.3457, False, "GATHER_EVIDENCE"),
        (0.1847, False, "GATHER_EVIDENCE"),
        (0.0885, False, "CONTINUE_MONITORING"),
    ],
    "revision-b": [
        (0.95, False, "DISPATCH_INSPECTION"),
        (0.3033, False, "GATHER_EVIDENCE"),
        (0.098, False, "CONTINUE_MONITORING"),
    ],
    "preservation-a": [
        (0.95, False, "DISPATCH_INSPECTION"),
        (0.9371, False, "DISPATCH_INSPECTION"),
        (0.9371, False, "DISPATCH_INSPECTION"),
    ],
    "preservation-b": [
        (0.05, False, "CONTINUE_MONITORING"),
        (0.05, False, "CONTINUE_MONITORING"),
        (0.0693, False, "CONTINUE_MONITORING"),
    ],
    "relation-a": [
        (0.9134, False, "DISPATCH_INSPECTION"),
        (0.946, False, "DISPATCH_INSPECTION"),
    ],
    "relation-b": [
        (0.7, False, "GATHER_EVIDENCE"),
        (0.1812, False, "GATHER_EVIDENCE"),
        (0.0725, False, "CONTINUE_MONITORING"),
    ],
    "contradiction-onset-a": [
        (0.95, False, "DISPATCH_INSPECTION"),
        (0.6431, True, "RECONCILE"),
        (0.4396, True, "RECONCILE"),
    ],
    "contradiction-onset-b": [
        (0.95, False, "DISPATCH_INSPECTION"),
        (0.6431, True, "RECONCILE"),
    ],
    "contradiction-resolution-a": [
        (0.6633, False, "GATHER_EVIDENCE"),
        (0.9178, False, "DISPATCH_INSPECTION"),
        (0.5142, True, "RECONCILE"),
        (0.0752, False, "CONTINUE_MONITORING"),
    ],
    "contradiction-resolution-b": [
        (0.95, False, "DISPATCH_INSPECTION"),
        (0.8259, True, "RECONCILE"),
        (0.081, False, "CONTINUE_MONITORING"),
        (0.0216, False, "CONTINUE_MONITORING"),
    ],
    "stale-a": [
        (0.5, False, "GATHER_EVIDENCE"),
        (0.0866, False, "CONTINUE_MONITORING"),
    ],
    "stale-b": [
        (0.95, False, "DISPATCH_INSPECTION"),
        (0.9693, False, "DISPATCH_INSPECTION"),
        (0.5459, False, "GATHER_EVIDENCE"),
    ],
    "stale-c": [
        (0.9134, False, "DISPATCH_INSPECTION"),
        (0.9405, False, "DISPATCH_INSPECTION"),
        (0.5405, False, "GATHER_EVIDENCE"),
    ],
    "reliability-a": [
        (0.6761, False, "GATHER_EVIDENCE"),
        (0.8134, False, "GATHER_EVIDENCE"),
        (0.5215, False, "GATHER_EVIDENCE"),
    ],
    "reliability-b": [
        (0.796, False, "GATHER_EVIDENCE"),
        (0.6514, False, "GATHER_EVIDENCE"),
        (0.9137, False, "DISPATCH_INSPECTION"),
    ],
    "deadline-a": [
        (0.95, False, "DISPATCH_INSPECTION"),
        (0.9829, False, "HOLD"),
    ],
    "deadline-b": [
        (0.95, False, "DISPATCH_INSPECTION"),
        (0.6431, True, "RECONCILE"),
        (0.5856, True, "ESCALATE"),
    ],
}
# Witness scenarios for the supersession rule (README Limits): a report
# supersedes even when it is itself unlinked or stale. They sit outside
# SUITE, so the frozen digest, reference and Done-when numbers do not move.
WITNESSES = [
    s("supersede-unlinked", "witness", False, [
        r("y1", "robot-1", G, 1, 0.95, 1),
        r("y2", "robot-1", "camera-1", -1, 0.7, 2, supersedes="y1"),
    ]),
    s("supersede-stale", "witness", False, [
        r("z1", "robot-1", G, 1, 0.95, 5),
        r("z2", "edge-2", G, -1, 0.8, 1, at=6, supersedes="z1"),
    ]),
]
SUITE_SHA256 = "efcffbf1acdc9f625ca7fa856e971c3f5c78def6060eab351559674ac46e5f54"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def suite_digest(suite=None):
    return hashlib.sha256(canonical(SUITE if suite is None else suite).encode("utf-8")).hexdigest()


def compact(prefixes):
    return [(round(p["posterior"], 4), p["contradiction"], p["action"]) for p in prefixes]


def relation_subsets(suite=None):
    suite = SUITE if suite is None else suite
    dep = [x for x in suite if x["relation_dependent"]]
    nodep = [x for x in suite if not x["relation_dependent"]]
    return dep, nodep


def score(suite, options=None, ablate=False):
    """Strict marks per scenario of the updater against the oracle."""
    out = []
    for sc in suite:
        ref = O.reference(sc)
        pred = C.run(C.drop_relations(sc) if ablate else sc, options)["prefixes"]
        out.append(C.prefix_marks(pred, ref))
    return out


def endpoint_right_mid_wrong(marks_by_scenario, suite=None):
    suite = SUITE if suite is None else suite
    return [sc["id"] for sc, m in zip(suite, marks_by_scenario)
            if m and m[-1] and not all(m[:-1])]


def summary(suite=None):
    suite = SUITE if suite is None else suite
    lines = []
    n_prefix = sum(len(x["reports"]) for x in suite)
    lines.append("suite: %d scenarios, %d prefixes, %d regimes, sha256 %s" % (
        len(suite), n_prefix, len({x["regime"] for x in suite}), suite_digest(suite)[:16]))
    agree = 0
    for sc in suite:
        ref = O.reference(sc)
        pred = C.run(sc)["prefixes"]
        agree += sum(1 for p, q in zip(pred, ref) if C.strict_match(p, q, tol=1e-9))
    lines.append("updater vs oracle: %d/%d prefixes agree" % (agree, n_prefix))
    lines.append("%-18s %7s %7s %8s  endpoint-right/mid-wrong" % (
        "condition", "prefix", "mid", "endpoint"))
    for name in sorted(C.BASELINES):
        marks = score(suite, C.BASELINES[name])
        pa, ma, ea = C.accuracy(marks)
        ids = endpoint_right_mid_wrong(marks, suite)
        lines.append("%-18s %7.3f %7.3f %8.3f  %s" % (name, pa, ma, ea, ", ".join(ids) or "-"))
    res = [x for x in suite if x["regime"] == "contradiction_resolution"]
    for name in ("full", "no_contradiction"):
        pa, ma, ea = C.accuracy(score(res, C.BASELINES[name]))
        lines.append("contradiction_resolution, %s: mid %.3f vs endpoint %.3f" % (name, ma, ea))
    dep, nodep = relation_subsets(suite)
    for label, sub in (("relation-dependent", dep), ("no-relation", nodep)):
        full = C.accuracy(score(sub))[0]
        abl = C.accuracy(score(sub, ablate=True))[0]
        lines.append("%s (%d scenarios): strict %.3f -> %.3f without relations (drop %.3f)" % (
            label, len(sub), full, abl, full - abl))
    for sc in suite:
        acts = " ".join(p["action"][:4] + ("*" if p["contradiction"] else "")
                        for p in C.run(sc)["prefixes"])
        lines.append("  %-27s %-24s %s" % (sc["id"], sc["regime"], acts))
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
