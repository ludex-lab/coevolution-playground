"""w18-decaf-dimensions: a proposal-format validator (method sketch).

A proposed change to an agent configuration should touch one dimension at a
time and carry an evidence trace that points at runs we actually observed.
This module only reads proposals and says what it sees. It never applies a
change, never runs an agent, and never judges whether a change is good.

Public verbs: detect_changes, report, report_all, flag, hold_reasons,
compare, restrict.

Outcomes (most severe first):
  fail_closed  malformed proposal, or a changed dimension with no evidence
  hold         evidence trace empty, placeholder, or citing an unknown run;
               also a proposal whose before and after are identical
  flag         declared dimensions disagree with the computed diff, or a
               changed key is not in the dimension manifest
  no_flag      nothing to flag (this is a report, not a sign-off)

Python 3 stdlib only.
"""

import copy
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

FAIL_CLOSED = "fail_closed"
HOLD = "hold"
FLAG = "flag"
NO_FLAG = "no_flag"
_RANK = {NO_FLAG: 0, FLAG: 1, HOLD: 2, FAIL_CLOSED: 3}

PLACEHOLDERS = frozenset([
    "", "tbd", "todo", "tba", "n/a", "na", "none", "null", "-", "--", "...",
    "placeholder", "see above", "see below", "lgtm", "trust me", "obvious",
    "fixme", "xxx", "?", "same as before",
])


def load_manifest(path=None):
    """Return the ordered tuple of dimension names from dimensions.json."""
    with open(path or os.path.join(HERE, "dimensions.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    return tuple(d["name"] for d in data["dimensions"])


DIMENSIONS = load_manifest()


def _canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _is_placeholder(text):
    if not isinstance(text, str):
        return True
    t = re.sub(r"\s+", " ", text).strip().lower().rstrip(".!")
    return t in PLACEHOLDERS


def detect_changes(before, after):
    """Sorted keys whose value differs between before and after.

    A key present on one side only counts as changed. Values are compared
    by canonical JSON, so nested lists and dicts are compared by content.
    """
    keys = set(before) | set(after)
    missing = object()
    changed = []
    for k in keys:
        a, b = before.get(k, missing), after.get(k, missing)
        if a is missing or b is missing or _canon(a) != _canon(b):
            changed.append(k)
    return sorted(changed)


def _run_ids(run_log):
    ids = set()
    for r in run_log or ():
        if isinstance(r, dict):
            r = r.get("run_id")
        if isinstance(r, str) and r.strip():
            ids.add(r.strip())
    return ids


def _malformed(p):
    if not isinstance(p, dict):
        return "proposal is not an object"
    if not isinstance(p.get("id"), str) or not p["id"].strip():
        return "missing proposal id"
    for side in ("before", "after"):
        if not isinstance(p.get(side), dict):
            return "%s is not an object" % side
    dec = p.get("declared_dimensions")
    if not isinstance(dec, list) or not all(isinstance(d, str) for d in dec):
        return "declared_dimensions is not a list of names"
    ev = p.get("evidence")
    if not isinstance(ev, list) or not all(isinstance(e, dict) for e in ev):
        return "evidence is not a list of objects"
    return None


def _finding(code, severity, detail, dimension=None):
    f = {"code": code, "severity": severity, "detail": detail}
    if dimension is not None:
        f["dimension"] = dimension
    return f


def report(proposal, run_log, dimensions=DIMENSIONS):
    """Report one proposal against a run log. Returns a plain dict."""
    pid = proposal.get("id") if isinstance(proposal, dict) else None
    bad = _malformed(proposal)
    if bad:
        return {"proposal_id": pid, "outcome": FAIL_CLOSED,
                "actual_dimensions": [], "declared_dimensions": [],
                "unknown_dimensions": [], "evidence_by_dimension": {},
                "multi_dimension": False,
                "findings": [_finding("malformed", FAIL_CLOSED, bad)]}

    known_runs = _run_ids(run_log)
    known_dims = set(dimensions)
    actual = detect_changes(proposal["before"], proposal["after"])
    declared = sorted(set(proposal["declared_dimensions"]))
    findings = []

    # 1. Trace checks. A broken trace cannot show coverage either way.
    trace_ok = True
    evidence = proposal["evidence"]
    if not evidence:
        trace_ok = False
        findings.append(_finding("empty_evidence", HOLD, "evidence trace has no entries"))
    covered = {}
    for n, e in enumerate(evidence):
        run, dim, note = e.get("run_id"), e.get("dimension"), e.get("note")
        if _is_placeholder(run) or _is_placeholder(note) or _is_placeholder(dim):
            trace_ok = False
            findings.append(_finding("placeholder_evidence", HOLD,
                                     "entry %d has an empty or placeholder field" % n))
            continue
        if run.strip() not in known_runs:
            trace_ok = False
            findings.append(_finding("unknown_run", HOLD,
                                     "entry %d cites run %r, not in the run log" % (n, run), dim))
            continue
        covered.setdefault(dim, []).append(run.strip())

    if not actual:
        findings.append(_finding("empty_diff", HOLD, "before and after are identical"))

    # 2. Coverage: every changed dimension needs its own evidence entry.
    if trace_ok:
        for dim in actual:
            if dim not in covered:
                findings.append(_finding("uncovered_dimension", FAIL_CLOSED,
                                         "changed without evidence", dim))
        for dim in sorted(covered):
            if dim not in actual:
                findings.append(_finding("evidence_for_unchanged", NO_FLAG,
                                         "evidence names a dimension that did not change", dim))

    # 3. Declared list vs computed diff, and manifest membership.
    if declared != actual:
        findings.append(_finding(
            "declared_mismatch", FLAG,
            "declared %s, diff shows %s" % (declared, actual)))
    unknown = sorted((set(actual) | set(declared)) - known_dims)
    for dim in unknown:
        findings.append(_finding("unknown_dimension", FLAG,
                                 "not in the dimension manifest", dim))

    multi = len(actual) > 1
    if multi:
        findings.append(_finding("multi_dimension", NO_FLAG,
                                 "%d dimensions changed in one proposal" % len(actual)))
        if any(f["code"] == "uncovered_dimension" for f in findings):
            findings.append(_finding("multi_dimension_uncovered", FAIL_CLOSED,
                                     "several dimensions changed, not all evidenced"))

    outcome = NO_FLAG
    for f in findings:
        if _RANK[f["severity"]] > _RANK[outcome]:
            outcome = f["severity"]
    return {"proposal_id": pid, "outcome": outcome,
            "actual_dimensions": actual, "declared_dimensions": declared,
            "unknown_dimensions": unknown,
            "evidence_by_dimension": {k: sorted(v) for k, v in sorted(covered.items())},
            "multi_dimension": multi, "findings": findings}


def report_all(proposals, run_log, dimensions=DIMENSIONS):
    return [report(p, run_log, dimensions) for p in proposals]


def flag(reports):
    """Proposal ids whose outcome is anything other than no_flag."""
    return [r["proposal_id"] for r in reports if r["outcome"] != NO_FLAG]


def hold_reasons(rep):
    """Finding codes that put a report on hold."""
    return [f["code"] for f in rep["findings"] if f["severity"] == HOLD]


def compare(a, b):
    """Compare the computed touched dimensions of two proposals."""
    da = set(detect_changes(a["before"], a["after"]))
    db = set(detect_changes(b["before"], b["after"]))
    return {"a": a["id"], "b": b["id"],
            "only_a": sorted(da - db), "only_b": sorted(db - da),
            "shared": sorted(da & db), "disjoint": not (da & db)}


def restrict(proposal, dimension):
    """A new proposal narrowed to one dimension; the input is not changed.

    Every other key in `after` is set back to its `before` value, the
    declared list becomes [dimension], and only evidence for that dimension
    is kept. The result is still only a proposal: run report() on it.
    """
    p = copy.deepcopy(proposal)
    after = {}
    for k in set(p["before"]) | set(p["after"]):
        if k == dimension:
            if k in p["after"]:
                after[k] = p["after"][k]
        elif k in p["before"]:
            after[k] = p["before"][k]
    p["after"] = after
    p["declared_dimensions"] = [dimension]
    p["evidence"] = [e for e in p["evidence"] if e.get("dimension") == dimension]
    p["restricted_from"] = proposal["id"]
    p["id"] = "%s~%s" % (proposal["id"], dimension)
    return p
