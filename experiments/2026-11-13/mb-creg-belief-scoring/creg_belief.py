"""Per-prefix shared belief updating in log-odds space (stdlib method sketch).

Clean-room Python 3 standard-library sketch of the evidence-to-belief
trajectory idea in arXiv 2611.11842 (CREG). Not a reproduction and not the
authors' code. The update, staleness, supersession, contradiction and
action rules below are this sketch's own declared rules.

One binary hypothesis per scenario: the target entity is "anomalous"
(versus "normal"). Reports arrive one at a time. After every arrival (every
evidence prefix) run() returns the posterior, the support and contradict
sets, the stale, superseded and unlinked sets, the active contradiction
records and an admissible next action.

Declared rules:
- Relevance: a report counts only when its entity is the target, or when a
  ("<entity>", "measures", "<target>") relation is present (and relations
  are in use). Any other report is unlinked and has no weight.
- Staleness: at prefix time now (the arrival time of the newest report),
  a report observed at t is stale when now - t > max_age; it has no weight.
- Supersession: a report that names "supersedes": "<id>" removes that
  earlier report from the evidence from its arrival on.
- Weight: a live report adds polarity * w * log(c / (1 - c)) to the prior
  log-odds, with w the declared reliability of its source.
- Contradiction: active when the live evidence holds a supporting and a
  contradicting report whose weights both reach STRONG_LLR (log 3).
- Action: when now >= deadline the action is the declared on_expiry
  (HOLD, ESCALATE or DENY), never a dispatch. Otherwise RECONCILE while a
  contradiction is active, DISPATCH_INSPECTION at posterior >= HI,
  CONTINUE_MONITORING at posterior <= LO, else GATHER_EVIDENCE.
- Fail closed: a missing or invalid field (on_expiry included), any dict
  key that is not an exact str, or a TypeError or OverflowError on hostile
  or extreme input is a config_error with no prefixes and so no action.
- Snapshot: validate() reads the caller's scenario once and returns fresh
  containers; run() never reads the caller's object again, and on_expiry
  is returned as the module constant.

Pure functions: no clock, no network, no files, no randomness.
"""

import math

ANOMALOUS = "anomalous"
MEASURES = "measures"
HI = 0.9
LO = 0.1
STRONG_LLR = math.log(3.0)

DISPATCH = "DISPATCH_INSPECTION"
CONTINUE = "CONTINUE_MONITORING"
GATHER = "GATHER_EVIDENCE"
RECONCILE = "RECONCILE"
HOLD, ESCALATE, DENY = "HOLD", "ESCALATE", "DENY"
ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY)
BELIEF_ACTIONS = (DISPATCH, CONTINUE, GATHER, RECONCILE)

OK = "ok"
CONFIG_ERROR = "config_error"

# Every rule switched on. Baselines switch one rule off (see BASELINES).
FULL = {"relations": True, "staleness": True, "supersedes": True,
        "contradiction": True, "reliability": True}
BASELINES = {
    "full": dict(FULL),
    "no_contradiction": dict(FULL, contradiction=False),
    "no_staleness": dict(FULL, staleness=False),
    "no_supersedes": dict(FULL, supersedes=False),
    "no_reliability": dict(FULL, reliability=False),
}
SCENARIO_FIELDS = ("id", "target", "prior", "max_age", "deadline", "on_expiry",
                   "relations", "sources", "reports")
REPORT_FIELDS = ("id", "source", "entity", "polarity", "confidence", "t", "at")


class _Bad(Exception):
    """Internal: a config_error with its reason."""


def _is_int(v):
    return type(v) is int


def _is_num(v):
    return type(v) in (int, float) and math.isfinite(v)


def _is_str(v):
    return type(v) is str and v != ""


def _str_keys(d):
    """True when every key of the exact dict d is an exact str.

    Lookups in such a dict compare str with str only, so they run no
    caller code (no __hash__ or __eq__ of a hostile key object)."""
    return all(type(k) is str for k in d)


def validate(scenario):
    """Return a private snapshot of a well-formed scenario or raise _Bad.

    Every dict key at every level must be an exact str. The snapshot holds
    fresh containers built from the validated values (on_expiry is the
    module constant itself); run() reads only the snapshot, never the
    caller's object again.
    """
    if type(scenario) is not dict:
        raise _Bad("scenario_not_dict")
    if not _str_keys(scenario):
        raise _Bad("scenario_key_invalid")
    scenario = dict(scenario)
    if "on_expiry" not in scenario:
        raise _Bad("on_expiry_missing")
    if type(scenario["on_expiry"]) is not str or scenario["on_expiry"] not in ON_EXPIRY_VALUES:
        raise _Bad("on_expiry_invalid")
    on_expiry = ON_EXPIRY_VALUES[ON_EXPIRY_VALUES.index(scenario["on_expiry"])]
    for name in SCENARIO_FIELDS:
        if name not in scenario:
            raise _Bad(name + "_missing")
    if not _is_str(scenario["id"]) or not _is_str(scenario["target"]):
        raise _Bad("id_or_target_invalid")
    prior = scenario["prior"]
    if not _is_num(prior) or not 0.0 < prior < 1.0:
        raise _Bad("prior_invalid")
    if not _is_int(scenario["max_age"]) or scenario["max_age"] < 0:
        raise _Bad("max_age_invalid")
    if not _is_int(scenario["deadline"]) or scenario["deadline"] <= 0:
        raise _Bad("deadline_invalid")
    rels = scenario["relations"]
    if type(rels) is not list:
        raise _Bad("relations_invalid")
    relations = []
    for rel in rels:
        if type(rel) not in (list, tuple):
            raise _Bad("relations_invalid")
        rel = tuple(rel)
        if len(rel) != 3 or not all(_is_str(x) for x in rel):
            raise _Bad("relations_invalid")
        relations.append(rel)
    sources = scenario["sources"]
    if type(sources) is not dict or not sources:
        raise _Bad("sources_invalid")
    weights = {}
    for name, w in sources.items():
        if not _is_str(name) or not _is_num(w) or not 0.0 < w <= 1.0:
            raise _Bad("reliability_invalid")
        weights[name] = w
    reports = scenario["reports"]
    if type(reports) is not list or not reports:
        raise _Bad("reports_invalid")
    seen = set()
    last_at = None
    snapped = []
    for r in reports:
        if type(r) is not dict:
            raise _Bad("report_invalid")
        if not _str_keys(r):
            raise _Bad("report_key_invalid")
        r = dict(r)
        for name in REPORT_FIELDS:
            if name not in r:
                raise _Bad("report_" + name + "_missing")
        if not _is_str(r["id"]) or r["id"] in seen:
            raise _Bad("report_id_invalid")
        if type(r["source"]) is not str:
            raise _Bad("report_source_invalid")
        if r["source"] not in weights:
            raise _Bad("report_source_unknown")
        if not _is_str(r["entity"]):
            raise _Bad("report_entity_invalid")
        if not _is_int(r["polarity"]) or r["polarity"] not in (1, -1):
            raise _Bad("report_polarity_invalid")
        c = r["confidence"]
        if not _is_num(c) or not 0.5 < c < 1.0:
            raise _Bad("report_confidence_invalid")
        if not _is_int(r["t"]) or not _is_int(r["at"]) or r["t"] > r["at"]:
            raise _Bad("report_time_invalid")
        if last_at is not None and r["at"] < last_at:
            raise _Bad("report_order_invalid")
        if "supersedes" in r and type(r["supersedes"]) is not str:
            raise _Bad("report_supersedes_invalid")
        if "supersedes" in r and r["supersedes"] not in seen:
            raise _Bad("report_supersedes_invalid")
        extra = set(r) - set(REPORT_FIELDS) - {"supersedes"}
        if extra:
            raise _Bad("report_field_unknown")
        snap = {name: r[name] for name in REPORT_FIELDS}
        if "supersedes" in r:
            snap["supersedes"] = r["supersedes"]
        snapped.append(snap)
        seen.add(r["id"])
        last_at = r["at"]
    return {"target": scenario["target"], "prior": prior, "max_age": scenario["max_age"],
            "deadline": scenario["deadline"], "on_expiry": on_expiry,
            "relations": tuple(relations), "sources": weights, "reports": tuple(snapped)}


def _options(options):
    if options is None:
        return dict(FULL)
    if type(options) is not dict or set(options) != set(FULL):
        raise ValueError("options must name exactly: %s" % sorted(FULL))
    return dict(options)


def _llr(report, sources, use_reliability):
    c = report["confidence"]
    w = sources[report["source"]] if use_reliability else 1.0
    return report["polarity"] * w * math.log(c / (1.0 - c))


def _action(posterior, contradiction, now, deadline, on_expiry):
    if now >= deadline:
        return on_expiry
    if contradiction:
        return RECONCILE
    if posterior >= HI:
        return DISPATCH
    if posterior <= LO:
        return CONTINUE
    return GATHER


def run(scenario, options=None):
    """Return {"status", "reason", "prefixes"} for one scenario.

    prefixes[k] describes the belief after the first k + 1 reports. The
    scenario is read once, by validate(); everything below uses only the
    private snapshot. A TypeError or OverflowError on hostile or extreme
    input is a config_error too, so no action leaks out of it.
    """
    opts = _options(options)
    try:
        snap = validate(scenario)
        prefixes = _trajectory(snap, opts)
    except _Bad as bad:
        return {"status": CONFIG_ERROR, "reason": str(bad), "prefixes": []}
    except TypeError:
        return {"status": CONFIG_ERROR, "reason": "type_invalid", "prefixes": []}
    except OverflowError:
        return {"status": CONFIG_ERROR, "reason": "numeric_overflow", "prefixes": []}
    return {"status": OK, "reason": None, "prefixes": prefixes}


def _trajectory(snap, opts):
    target = snap["target"]
    sources = snap["sources"]
    max_age = snap["max_age"]
    deadline = snap["deadline"]
    on_expiry = snap["on_expiry"]
    linked = {target}
    if opts["relations"]:
        linked |= {r[0] for r in snap["relations"] if r[1] == MEASURES and r[2] == target}
    prior = snap["prior"]
    prior_lo = math.log(prior / (1.0 - prior))
    arrived = []
    superseded = set()
    prefixes = []
    for step, report in enumerate(snap["reports"], start=1):
        now = report["at"]
        arrived.append(report)
        if opts["supersedes"] and "supersedes" in report:
            superseded.add(report["supersedes"])
        live, stale, unlinked = [], [], []
        for r in arrived:
            if r["id"] in superseded:
                continue
            if r["entity"] not in linked:
                unlinked.append(r["id"])
            elif opts["staleness"] and now - r["t"] > max_age:
                stale.append(r["id"])
            else:
                live.append((r["id"], _llr(r, sources, opts["reliability"])))
        log_odds = prior_lo + math.fsum(v for _, v in live)
        posterior = 1.0 / (1.0 + math.exp(-log_odds))
        strong_for = sorted(i for i, v in live if v >= STRONG_LLR)
        strong_against = sorted(i for i, v in live if v <= -STRONG_LLR)
        conflicts = ()
        if opts["contradiction"]:
            conflicts = tuple((a, b) for a in strong_for for b in strong_against)
        contradiction = bool(conflicts)
        prefixes.append({
            "step": step,
            "now": now,
            "log_odds": log_odds,
            "posterior": posterior,
            "support": tuple(sorted(i for i, v in live if v > 0)),
            "contradict": tuple(sorted(i for i, v in live if v < 0)),
            "stale": tuple(sorted(stale)),
            "superseded": tuple(sorted(i for i in superseded)),
            "unlinked": tuple(sorted(unlinked)),
            "contradiction": contradiction,
            "conflicts": conflicts,
            "action": _action(posterior, contradiction, now, deadline, on_expiry),
        })
    return prefixes


def drop_relations(scenario):
    """Representation ablation: the same scenario with no relation content."""
    out = dict(scenario)
    out["relations"] = []
    return out


# Scoring: a prefix is strictly correct only when every belief-state part
# matches the reference prefix.
STRICT_TOL = 0.05
STRICT_KEYS = ("support", "contradict", "contradiction", "action")


def strict_match(pred, ref, tol=STRICT_TOL):
    if abs(pred["posterior"] - ref["posterior"]) > tol:
        return False
    return all(pred[k] == ref[k] for k in STRICT_KEYS)


def prefix_marks(pred_prefixes, ref_prefixes):
    """One bool per prefix; a length mismatch is all wrong."""
    if len(pred_prefixes) != len(ref_prefixes):
        return [False] * len(ref_prefixes)
    return [strict_match(p, r) for p, r in zip(pred_prefixes, ref_prefixes)]


def accuracy(marks_by_scenario):
    """(all-prefix, mid-trajectory, endpoint-only) strict accuracy.

    Mid-trajectory means every prefix but the last; it is None when no
    scenario has more than one prefix.
    """
    flat = [m for marks in marks_by_scenario for m in marks]
    mid = [m for marks in marks_by_scenario for m in marks[:-1]]
    ends = [marks[-1] for marks in marks_by_scenario if marks]
    if not flat or not ends:
        raise ValueError("empty suite")
    return (sum(flat) / len(flat), sum(mid) / len(mid) if mid else None,
            sum(ends) / len(ends))
