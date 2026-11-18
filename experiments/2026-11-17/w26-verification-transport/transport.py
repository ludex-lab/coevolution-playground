"""Verification transport on frozen fictional executions (stdlib only).

Clean-room method sketch of arXiv 2611.18471 (CC BY 4.0); not a reproduction. The same frozen
execution is shown to the same fixture verifier as a native (full) view and as a matched
abstracted view (composed tool, delegation or compaction hides some evidence). A verdict that is
correct on the native view and wrong on the abstracted view is `transport_incorrect`; one that
abstains there is `transport_abstain`; the two are counted separately and never merged into a
single score. A full restore of the hidden provenance and a lossy restore (ids only, values lost)
are both re-verified. A suite scored on native views only reports `transport: unmeasured`.

A pair is matched only when both views come from the same execution id with equal step content
(tool, evidence, summary, hidden_by) and every frozen field is equal. Any missing, unmatched,
expired or malformed view, a repeated step id, a non-boolean `expired`, a repeated JSON key or a
blank id or text field is DENY with exit 2 (on_expiry=DENY). The same pair listed again under a
new pair id is counted once and reported as an INFO line.

Run: python3 -B transport.py fixtures/executions.json
"""

import copy
import json
import sys

ON_EXPIRY = "DENY"
BOUNDARIES = ("composed_tool", "delegation", "compaction")
VERDICTS = ("pass", "fail", "abstain")
FROZEN = ("task", "trajectory_id", "step_ids", "outcome", "ground_truth", "criterion", "verifier")
BINDING = ("execution", "step_content")
LABELS = ("stable", "transport_incorrect", "transport_abstain", "native_not_correct")


class Deny(Exception):
    """A view or fixture that cannot be scored. Always exit 2, never a verdict."""

    def __init__(self, code, detail):
        Exception.__init__(self, "%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- verifiers (no model)

def _lookup(obs, item):
    """Value of an evidence item in the visible steps: True, False, or None when not visible."""
    for step in obs["steps"]:
        ev = step["evidence"]
        if ev is not None and item in ev and ev[item] is not None:
            return ev[item]
    return None


def _claimed(obs, item):
    for step in obs["steps"]:
        summary = step.get("summary")
        if summary is not None and item in summary["claims"]:
            return summary["claims"][item]
    return None


def direct(obs):
    """Decides on whatever it sees: trusts a summary claim, otherwise treats an unseen item as unmet."""
    for item in obs["criterion"]:
        value = _lookup(obs, item)
        if value is None:
            value = _claimed(obs, item)
        if value is not True:
            return "fail"
    return "pass"


def grounded(obs):
    """Decides only on visible evidence; abstains when any required item is not visible."""
    values = [_lookup(obs, item) for item in obs["criterion"]]
    if any(v is None for v in values):
        return "abstain"
    return "pass" if all(values) else "fail"


VERIFIERS = {"direct": direct, "grounded": grounded}


# ---------------------------------------------------------------- views

def _content(execution):
    """The realized trajectory as plain nested tuples, compared structurally (no digest)."""
    out = []
    for s in execution["steps"]:
        summary = s.get("summary")
        if summary is not None:
            summary = (summary["text"], tuple(sorted(summary["claims"].items())))
        out.append((s["id"], s["tool"], tuple(sorted(s["evidence"].items())), summary,
                    tuple(sorted(s.get("hidden_by", ())))))
    return tuple(out)


def _frozen(execution, verifier):
    return {
        "execution": execution["id"],
        "task": execution["task"],
        "trajectory_id": execution["trajectory_id"],
        "step_ids": tuple(s["id"] for s in execution["steps"]),
        "outcome": execution["outcome"],
        "ground_truth": execution["ground_truth"],
        "criterion": tuple(execution["criterion"]),
        "verifier": verifier,
        "step_content": _content(execution),
    }


def native_view(execution, verifier):
    view = _frozen(execution, verifier)
    view["kind"] = "native"
    view["boundary"] = None
    view["steps"] = [{"id": s["id"], "tool": s["tool"], "evidence": dict(s["evidence"]), "summary": None}
                     for s in execution["steps"]]
    return view


def abstract(execution, verifier, boundary):
    """Abstracted view plus the provenance it hid. Hidden steps show only their summary, if any."""
    if boundary not in BOUNDARIES:
        raise Deny("unknown_boundary", repr(boundary))
    view = _frozen(execution, verifier)
    view["kind"] = "abstracted"
    view["boundary"] = boundary
    view["steps"] = []
    provenance = {}
    for s in execution["steps"]:
        if boundary in s.get("hidden_by", ()):
            provenance[s["id"]] = dict(s["evidence"])
            summary = copy.deepcopy(s.get("summary"))
            view["steps"].append({"id": s["id"], "tool": s["tool"], "evidence": None, "summary": summary})
        else:
            view["steps"].append({"id": s["id"], "tool": s["tool"], "evidence": dict(s["evidence"]), "summary": None})
    if not provenance:
        raise Deny("boundary_hides_nothing", "%s on %s" % (boundary, execution["id"]))
    return view, provenance


def restore(view, provenance, lossy=False):
    """Put hidden provenance back. A lossy restore returns the item ids with their values lost."""
    out = copy.deepcopy(view)
    out["kind"] = "restored"
    out["restore"] = "lossy" if lossy else "full"
    for step in out["steps"]:
        if step["id"] in provenance:
            hidden = provenance[step["id"]]
            step["evidence"] = {k: None for k in hidden} if lossy else dict(hidden)
            step["summary"] = None if not lossy else step["summary"]
    return out


def observable(view):
    """What a verifier may read: the criterion and the visible steps. Never the ground truth."""
    return {"criterion": list(view["criterion"]), "steps": copy.deepcopy(view["steps"])}


def verdict(view):
    v = VERIFIERS[view["verifier"]](observable(view))
    if v not in VERDICTS:
        raise Deny("bad_verdict", repr(v))
    return v


def check_matched(a, b):
    """A matched pair: every frozen field equal, the same execution id and equal step content."""
    for field in FROZEN + BINDING:
        if a[field] != b[field]:
            raise Deny("mismatched_pair", "%s differs (%s vs %s)" % (field, a["execution"], b["execution"]))


# ---------------------------------------------------------------- measurement

def label(truth, native_v, abstracted_v):
    if native_v != truth:
        return "native_not_correct"
    if abstracted_v == truth:
        return "stable"
    if abstracted_v == "abstain":
        return "transport_abstain"
    return "transport_incorrect"


def measure_pair(pair_id, native, abstracted, provenance):
    check_matched(native, abstracted)
    truth = native["ground_truth"]
    nv = verdict(native)
    av = verdict(abstracted)
    lab = label(truth, nv, av)
    row = {"pair": pair_id, "execution": native["execution"], "verifier": native["verifier"],
           "boundary": abstracted["boundary"], "truth": truth, "native": nv, "abstracted": av,
           "label": lab, "restore_full": "n/a", "restore_lossy": "n/a"}
    if lab in ("transport_incorrect", "transport_abstain"):
        for mode, lossy in (("restore_full", False), ("restore_lossy", True)):
            restored = restore(abstracted, provenance, lossy=lossy)
            check_matched(native, restored)
            row[mode] = "recovered" if verdict(restored) == truth else "not_recovered"
    return row


def summarize(rows):
    """Per-verifier counts. Incorrect and abstain stay separate; there is no single score."""
    out = {}
    for row in rows:
        s = out.setdefault(row["verifier"], {
            "pairs": 0, "native_correct": 0, "stable": 0, "transport_incorrect": 0,
            "transport_abstain": 0, "transport_failures": 0, "native_not_correct": 0,
            "recovered_full": 0, "recovered_lossy": 0})
        s["pairs"] += 1
        s[row["label"]] += 1
        if row["label"] != "native_not_correct":
            s["native_correct"] += 1
        if row["label"] in ("transport_incorrect", "transport_abstain"):
            s["transport_failures"] += 1
        if row["restore_full"] == "recovered":
            s["recovered_full"] += 1
        if row["restore_lossy"] == "recovered":
            s["recovered_lossy"] += 1
    return out


def rank(a, b):
    """Order two summaries only when one is no worse on BOTH incorrect and abstain counts.

    Fewer transport failures bought with more incorrect verdicts is `not_ranked`.
    """
    ai, aa = a["transport_incorrect"], a["transport_abstain"]
    bi, ba = b["transport_incorrect"], b["transport_abstain"]
    if (ai, aa) == (bi, ba):
        return "equal"
    if ai <= bi and aa <= ba:
        return "first_more_reliable"
    if bi <= ai and ba <= aa:
        return "second_more_reliable"
    return "not_ranked"


def score_native_only(views):
    """Native-view accuracy is reported, but transport is unmeasured and the status is never PASS."""
    correct = sum(1 for v in views if verdict(v) == v["ground_truth"])
    return {"native_correct": correct, "native_views": len(views),
            "transport": "unmeasured", "status": "unmeasured"}


# ---------------------------------------------------------------- fixture loading (DENY on anything odd)

def _need(cond, code, detail):
    if not cond:
        raise Deny(code, detail)


def _text(v):
    """A non-blank string: whitespace-only ids and text fields are malformed."""
    return isinstance(v, str) and v.strip() != ""


def _no_duplicate_keys(pairs):
    """object_pairs_hook: a repeated key at any nesting level is malformed, never last-wins."""
    out = {}
    for k, v in pairs:
        if k in out:
            raise Deny("malformed_fixture", "duplicate key %r" % k)
        out[k] = v
    return out


def _is_bool_map(m):
    return isinstance(m, dict) and all(isinstance(k, str) and isinstance(v, bool) for k, v in m.items())


def _check_execution(e):
    _need(isinstance(e, dict), "malformed_fixture", "execution is not an object")
    for f in ("id", "task", "trajectory_id", "outcome"):
        _need(_text(e.get(f)), "malformed_fixture", "execution field %s" % f)
    eid = e["id"]
    _need(e.get("ground_truth") in ("pass", "fail"), "malformed_fixture", "%s ground_truth" % eid)
    crit = e.get("criterion")
    _need(isinstance(crit, list) and crit and all(_text(c) for c in crit),
          "malformed_fixture", "%s criterion" % eid)
    steps = e.get("steps")
    _need(isinstance(steps, list) and steps, "malformed_fixture", "%s steps" % eid)
    seen = {}
    step_ids = set()
    for s in steps:
        _need(isinstance(s, dict) and _text(s.get("id")) and _text(s.get("tool")),
              "malformed_fixture", "%s step" % eid)
        _need(s["id"] not in step_ids, "malformed_fixture", "%s step id %s repeated" % (eid, s["id"]))
        step_ids.add(s["id"])
        _need(_is_bool_map(s.get("evidence")), "malformed_fixture", "%s %s evidence" % (eid, s["id"]))
        hb = s.get("hidden_by", [])
        _need(isinstance(hb, list) and all(b in BOUNDARIES for b in hb), "unknown_boundary",
              "%s %s hidden_by" % (eid, s["id"]))
        if "summary" in s:
            sm = s["summary"]
            _need(isinstance(sm, dict) and _text(sm.get("text")) and _is_bool_map(sm.get("claims")),
                  "malformed_fixture", "%s %s summary" % (eid, s["id"]))
        for k, v in s["evidence"].items():
            _need(k not in seen, "malformed_fixture", "%s evidence item %s repeated" % (eid, k))
            seen[k] = v
    _need(all(c in seen for c in crit), "malformed_fixture", "%s criterion item without evidence" % eid)
    full = all(seen[c] for c in crit)
    _need(full == (e["ground_truth"] == "pass"), "ground_truth_inconsistent", eid)


def _view_spec(spec, executions, pair_id, side):
    _need(isinstance(spec, dict), "missing_view", "%s %s" % (pair_id, side))
    if "expired" in spec:
        _need(type(spec["expired"]) is bool, "malformed_fixture",
              "%s %s expired is not a JSON boolean (%r)" % (pair_id, side, spec["expired"]))
    _need(spec.get("expired") is not True, "on_expiry", "%s %s view expired (on_expiry=%s)" % (pair_id, side, ON_EXPIRY))
    _need(spec.get("execution") in executions, "missing_view", "%s %s execution %r" % (pair_id, side, spec.get("execution")))
    _need(spec.get("verifier") in VERIFIERS, "unknown_verifier", "%s %s %r" % (pair_id, side, spec.get("verifier")))
    return executions[spec["execution"]], spec["verifier"]


def load(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise Deny("unreadable_fixture", "%s (%s)" % (path, exc.__class__.__name__))
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except ValueError:
        raise Deny("malformed_fixture", "not JSON")
    _need(isinstance(data, dict), "malformed_fixture", "top level is not an object")
    execs = data.get("executions")
    _need(isinstance(execs, list) and execs, "malformed_fixture", "no executions")
    by_id = {}
    for e in execs:
        _check_execution(e)
        _need(e["id"] not in by_id, "malformed_fixture", "duplicate execution %s" % e["id"])
        by_id[e["id"]] = e
    has_pairs = "pairs" in data
    has_native = "native_only" in data
    _need(has_pairs != has_native, "malformed_fixture", "declare exactly one of pairs / native_only")
    key = "pairs" if has_pairs else "native_only"
    _need(isinstance(data[key], list) and data[key], "malformed_fixture", "empty %s" % key)
    return data, by_id


def run(path):
    data, by_id = load(path)
    if "native_only" in data:
        views = []
        for i, spec in enumerate(data["native_only"]):
            ex, ver = _view_spec(spec, by_id, "n%d" % (i + 1), "native")
            views.append(native_view(ex, ver))
        return {"mode": "native_only", "result": score_native_only(views)}
    rows = []
    ids = set()
    first = {}
    info = []
    for pair in data["pairs"]:
        _need(isinstance(pair, dict) and _text(pair.get("id")), "malformed_fixture", "pair id")
        pid = pair["id"]
        _need(pid not in ids, "malformed_fixture", "duplicate pair %s" % pid)
        ids.add(pid)
        _need("native" in pair and "abstracted" in pair, "missing_view", "%s lacks a native or abstracted view" % pid)
        nex, nver = _view_spec(pair["native"], by_id, pid, "native")
        aex, aver = _view_spec(pair["abstracted"], by_id, pid, "abstracted")
        native = native_view(nex, nver)
        abstracted, prov = abstract(aex, aver, pair["abstracted"].get("boundary"))
        row = measure_pair(pid, native, abstracted, prov)
        key = (row["execution"], row["verifier"], row["boundary"])
        if key in first:
            info.append("counted_twice: %s repeats %s (counted once)" % (pid, first[key]))
            continue
        first[key] = pid
        rows.append(row)
    return {"mode": "pairs", "rows": rows, "summary": summarize(rows),
            "transport": "measured", "status": "measured", "info": info}


def render(report):
    lines = []
    if report["mode"] == "native_only":
        r = report["result"]
        lines.append("native views scored: %d, native correct: %d" % (r["native_views"], r["native_correct"]))
        lines.append("transport: %s" % r["transport"])
        lines.append("status: %s" % r["status"])
        return lines
    lines.append("pair  execution  verifier  boundary       truth  native  abstracted  label                restore_full   restore_lossy")
    for row in report["rows"]:
        lines.append("%-5s %-10s %-9s %-14s %-6s %-7s %-11s %-20s %-14s %s" % (
            row["pair"], row["execution"], row["verifier"], row["boundary"], row["truth"], row["native"],
            row["abstracted"], row["label"], row["restore_full"], row["restore_lossy"]))
    names = sorted(report["summary"])
    for name in names:
        s = report["summary"][name]
        lines.append("%s: pairs=%d native_correct=%d stable=%d transport_incorrect=%d transport_abstain=%d "
                     "transport_failures=%d recovered_full=%d recovered_lossy=%d" % (
                         name, s["pairs"], s["native_correct"], s["stable"], s["transport_incorrect"],
                         s["transport_abstain"], s["transport_failures"], s["recovered_full"], s["recovered_lossy"]))
    if len(names) == 2:
        lines.append("rank(%s, %s): %s" % (names[0], names[1],
                                           rank(report["summary"][names[0]], report["summary"][names[1]])))
    lines.append("transport: %s" % report["transport"])
    lines.append("status: %s" % report["status"])
    for note in report["info"]:
        lines.append("INFO %s" % note)
    return lines


def main(argv):
    if len(argv) != 1:
        sys.stderr.write("DENY usage: python3 -B transport.py <fixture.json>\n")
        return 2
    try:
        report = run(argv[0])
    except Deny as exc:
        sys.stderr.write("DENY %s: %s\n" % (exc.code, exc.detail))
        return 2
    sys.stdout.write("\n".join(render(report)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
