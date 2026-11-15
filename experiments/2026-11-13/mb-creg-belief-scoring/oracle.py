"""Independent normative reference for the creg_belief sketch.

A separate code path: it shares no code with creg_belief.py and works in
probability / Bayes-factor space (products of odds, no logarithms). For a
well-formed scenario it recomputes each evidence prefix from scratch:

- a report is linked when its entity is the target or a measures relation
  ties that entity to the target;
- a report is live while now <= t + max_age and no arrived report names it
  in "supersedes";
- its Bayes factor is (c / (1 - c)) ** w for a supporting report and
  ((1 - c) / c) ** w for a contradicting one;
- posterior odds = prior odds * product of live Bayes factors;
- a contradiction is active when one live factor is >= 3 and one is <= 1/3;
- the action is on_expiry once now >= deadline, else RECONCILE, then a
  dispatch at odds >= 9, continue at odds <= 1/9, else gather.

The oracle never validates input; the suite feeds it only scenarios that
creg_belief.validate() accepts.
"""

STRONG_FACTOR = 3.0
DISPATCH_ODDS = 9.0          # posterior 0.9
CONTINUE_ODDS = 1.0 / 9.0    # posterior 0.1


def _factor(report, reliability):
    c = report["confidence"]
    ratio = c / (1.0 - c) if report["polarity"] == 1 else (1.0 - c) / c
    return ratio ** reliability[report["source"]]


def _prefix(scenario, k):
    reports = scenario["reports"][:k]
    now = reports[-1]["at"]
    target = scenario["target"]
    measured_by = {}
    for subj, rel, obj in scenario["relations"]:
        if rel == "measures":
            measured_by.setdefault(obj, set()).add(subj)
    entities = {target} | measured_by.get(target, set())
    gone = {r["supersedes"] for r in reports if "supersedes" in r}
    factors = {}
    stale, unlinked = set(), set()
    for r in reports:
        if r["id"] in gone:
            continue
        if r["entity"] not in entities:
            unlinked.add(r["id"])
            continue
        if now > r["t"] + scenario["max_age"]:
            stale.add(r["id"])
            continue
        factors[r["id"]] = _factor(r, scenario["sources"])
    odds = scenario["prior"] / (1.0 - scenario["prior"])
    for rid in sorted(factors):
        odds *= factors[rid]
    up = sorted(rid for rid, f in factors.items() if f >= STRONG_FACTOR)
    down = sorted(rid for rid, f in factors.items() if f <= 1.0 / STRONG_FACTOR)
    pairs = tuple((a, b) for a in up for b in down)
    if now >= scenario["deadline"]:
        action = scenario["on_expiry"]
    elif pairs:
        action = "RECONCILE"
    elif odds >= DISPATCH_ODDS:
        action = "DISPATCH_INSPECTION"
    elif odds <= CONTINUE_ODDS:
        action = "CONTINUE_MONITORING"
    else:
        action = "GATHER_EVIDENCE"
    return {
        "step": k,
        "now": now,
        "odds": odds,
        "posterior": odds / (1.0 + odds),
        "support": tuple(sorted(rid for rid, f in factors.items() if f > 1.0)),
        "contradict": tuple(sorted(rid for rid, f in factors.items() if f < 1.0)),
        "stale": tuple(sorted(stale)),
        "superseded": tuple(sorted(gone)),
        "unlinked": tuple(sorted(unlinked)),
        "contradiction": bool(pairs),
        "conflicts": pairs,
        "action": action,
    }


def reference(scenario):
    """Normative prefix list for one well-formed scenario."""
    return [_prefix(scenario, k) for k in range(1, len(scenario["reports"]) + 1)]
