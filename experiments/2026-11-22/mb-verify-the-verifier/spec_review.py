"""mb-verify-the-verifier: a green scoreboard is not a met specification.

Method sketch of the scoreboard-versus-specification split described on the abstract page of arXiv 2611.26588
(clean-room: no upstream code exists or was used; the paper's model-based cross-check is NOT run or imitated with a
model). A toy 4-entry FIFO design is driven by a fixture stimulus. Two independent reviews read the same trace:

- scoreboard(): compares the design's outputs, on a declared set of fields, against a golden reference model.
  It never reads the specification.
- clause_audit(): reads only the numbered specification clauses and the observed trace, and returns clause-level
  reason codes. It never reads the golden model. This rule-based clause evaluator stands in for the paper's
  model-based cross-check; there is no model call anywhere.

Stdlib only: no network, no randomness, no clock, no files written.
"""

import json
import re
import sys
import unicodedata

FIXTURE_VERSION = 1
MAX_BYTES = 100000
ON_EXPIRY = "DENY"
CAPS = {
    "file_bytes": {"limit": MAX_BYTES, "on_expiry": "DENY"},
    "cases": {"limit": 50, "on_expiry": "DENY"},
    "steps": {"limit": 64, "on_expiry": "DENY"},
    "text_chars": {"limit": 300, "on_expiry": "DENY"},
}
RULES = ("capacity", "order", "underflow", "count", "flags")
VARIANTS = ("correct", "overwrite_when_full", "lifo", "full_flag_early", "underflow_returns_data")
FIELDS = ("ok", "served", "value", "count", "full", "empty")
PLANTS = ("clean", "escape", "real_fail")
ID_RE = re.compile(r"[A-Za-z0-9_\uac00-\ud7a3]{1,40}")
CLAUSE_ID_RE = re.compile(r"S[1-9]")
BAD_CATEGORIES = {"Cc", "Cf", "Co", "Cn", "Cs", "Zl", "Zp", "Zs"}
REASONS = {
    "capacity": ("push_accepted_when_full", "push_refused_when_not_full"),
    "order": ("pop_out_of_order", "pop_not_served_when_not_empty"),
    "underflow": ("pop_when_empty_returned_data",),
    "count": ("count_mismatch",),
    "flags": ("full_flag_wrong", "empty_flag_wrong"),
}


class ReviewError(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- strict loading

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ReviewError("duplicate_key", "a key is repeated")
        out[key] = value
    return out


def _constant(name):
    raise ReviewError("bad_number", "%s is not a finite number" % name)


def _no_float(text):
    raise ReviewError("wrong_type", "fractional numbers are not used in this fixture")


def parse(text):
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_no_float)
    except ReviewError:
        raise
    except (ValueError, RecursionError, OverflowError):
        raise ReviewError("not_json", "input is not valid JSON")


def _obj(value, keys, where, optional=()):
    if type(value) is not dict:
        raise ReviewError("wrong_type", "%s must be an object" % where)
    missing = [k for k in keys if k not in value]
    if missing:
        raise ReviewError("missing_key", "%s lacks %s" % (where, missing[0]))
    unknown = sorted(set(value) - set(keys) - set(optional))
    if unknown:
        raise ReviewError("unknown_key", "%s has an unknown key" % where)
    return value


def _int(value, where, low, high):
    if type(value) is not int:
        raise ReviewError("wrong_type", "%s must be an integer" % where)
    if not low <= value <= high:
        raise ReviewError("bad_value", "%s must be from %d to %d" % (where, low, high))
    return value


def _text(value, where):
    limit = CAPS["text_chars"]["limit"]
    if type(value) is not str or not 1 <= len(value) <= limit:
        raise ReviewError("wrong_type", "%s must be text of 1 to %d characters" % (where, limit))
    for ch in value:
        if ch != " " and unicodedata.category(ch) in BAD_CATEGORIES:
            raise ReviewError("bad_text", "%s holds a control, invisible or unassigned character" % where)
    if value != value.strip(" "):
        raise ReviewError("bad_text", "%s has a leading or trailing space" % where)
    return unicodedata.normalize("NFC", value)


def _choice(value, options, where, code):
    if type(value) is not str or value not in options:
        raise ReviewError(code, "%s must be one of %s" % (where, ", ".join(options)))
    return value


def _spec(value):
    _obj(value, ("title", "clauses"), "spec")
    _text(value["title"], "spec title")
    clauses = value["clauses"]
    if type(clauses) is not list or len(clauses) != len(RULES):
        raise ReviewError("bad_spec", "spec must hold exactly %d clauses, one per rule" % len(RULES))
    out, ids, rules = {}, set(), set()
    for n, c in enumerate(clauses):
        where = "clause %d" % (n + 1)
        rule = _choice(_obj(c, ("id", "rule", "text"), where, optional=("depth",))["rule"], RULES, where + " rule",
                       "unknown_rule")
        if type(c["id"]) is not str or CLAUSE_ID_RE.fullmatch(c["id"]) is None:
            raise ReviewError("bad_id", "%s id must be S1 to S9" % where)
        if c["id"] in ids or rule in rules:
            raise ReviewError("bad_spec", "%s repeats a clause id or a rule" % where)
        if ("depth" in c) != (rule == "capacity"):
            raise ReviewError("bad_spec", "only the capacity clause carries a depth")
        ids.add(c["id"])
        rules.add(rule)
        out[rule] = {"id": c["id"], "text": _text(c["text"], where + " text")}
        if rule == "capacity":
            out[rule]["depth"] = _int(c["depth"], where + " depth", 1, 16)
    return out


def _stimulus(value, where):
    if type(value) is not list or not 1 <= len(value) <= CAPS["steps"]["limit"]:
        raise ReviewError("too_many", "%s must hold 1 to %d steps (on_expiry DENY)"
                          % (where, CAPS["steps"]["limit"]))
    steps = []
    for n, s in enumerate(value):
        w = "%s step %d" % (where, n + 1)
        if type(s) is not dict or "op" not in s:
            raise ReviewError("wrong_type", "%s must be an object with an op" % w)
        op = _choice(s["op"], ("push", "pop"), w + " op", "bad_op")
        if op == "push":
            _obj(s, ("op", "value"), w)
            steps.append({"op": "push", "value": _int(s["value"], w + " value", 0, 255)})
        else:
            _obj(s, ("op",), w)
            steps.append({"op": "pop"})
    return steps


def _cases(value):
    if type(value) is not list or not 1 <= len(value) <= CAPS["cases"]["limit"]:
        raise ReviewError("too_many", "cases must hold 1 to %d entries (on_expiry DENY)" % CAPS["cases"]["limit"])
    out, seen = [], set()
    for n, c in enumerate(value):
        where = "case %d" % (n + 1)
        _obj(c, ("id", "planted", "dut", "golden", "compare", "stimulus"), where, optional=("note",))
        cid = unicodedata.normalize("NFC", c["id"]) if type(c["id"]) is str else None
        if cid is None or ID_RE.fullmatch(cid) is None:
            raise ReviewError("bad_id", "%s id must be 1 to 40 letters, digits, underscores or Hangul" % where)
        if cid in seen:
            raise ReviewError("duplicate_case", "%s repeats a case id (compared after NFC)" % where)
        seen.add(cid)
        compare = c["compare"]
        if type(compare) is not list or not compare:
            raise ReviewError("bad_compare", "%s compare must be a non-empty list of fields" % where)
        for f in compare:
            _choice(f, FIELDS, where + " compare field", "bad_compare")
        if len(set(compare)) != len(compare):
            raise ReviewError("bad_compare", "%s compare repeats a field" % where)
        case = {"id": cid,
                "planted": _choice(c["planted"], PLANTS, where + " planted", "bad_plant"),
                "dut": _choice(c["dut"], VARIANTS, where + " dut", "unknown_variant"),
                "golden": _choice(c["golden"], VARIANTS, where + " golden", "unknown_variant"),
                "compare": list(compare),
                "stimulus": _stimulus(c["stimulus"], where)}
        if "note" in c:
            case["note"] = _text(c["note"], where + " note")
        out.append(case)
    return out


def validate(root):
    _obj(root, ("fixture_version", "label", "design", "spec", "cases"), "fixture")
    if _int(root["fixture_version"], "fixture_version", 0, 1000) != FIXTURE_VERSION:
        raise ReviewError("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    _text(root["label"], "label")
    _obj(root["design"], ("name", "depth"), "design")
    _text(root["design"]["name"], "design name")
    return {"depth": _int(root["design"]["depth"], "design depth", 1, 16), "spec": _spec(root["spec"]),
            "cases": _cases(root["cases"])}


def load_fixture(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_BYTES + 1)
    except OSError:
        raise ReviewError("unreadable", "file could not be read")
    if len(data) > MAX_BYTES:
        raise ReviewError("too_large", "file is larger than %d bytes (on_expiry DENY)" % MAX_BYTES)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ReviewError("bad_encoding", "file is not valid UTF-8")
    return validate(parse(text))


# ---------------------------------------------------------------- the toy design and its reference models

def simulate(variant, depth, stimulus):
    """Drive one FIFO model. 'correct' is the specified behaviour; the others are fixture-authored bugs."""
    queue, last, trace = [], 0, []
    for step in stimulus:
        if step["op"] == "push":
            if len(queue) < depth:
                queue.append(step["value"])
                ok = True
            elif variant == "overwrite_when_full":
                queue.pop(0)
                queue.append(step["value"])
                ok = True
            else:
                ok = False
            out = {"ok": ok}
        else:
            if queue:
                value = queue.pop() if variant == "lifo" else queue.pop(0)
                last = value
                out = {"served": True, "value": value}
            elif variant == "underflow_returns_data":
                out = {"served": True, "value": last}
            else:
                out = {"served": False, "value": None}
        full_at = depth - 1 if variant == "full_flag_early" else depth
        out.update({"count": len(queue), "full": len(queue) >= full_at, "empty": len(queue) == 0})
        trace.append(dict(step, out=out))
    return trace


def scoreboard(case, depth):
    """Compare the design against the golden model on the declared fields only. Never reads the spec."""
    dut = simulate(case["dut"], depth, case["stimulus"])
    gold = simulate(case["golden"], depth, case["stimulus"])
    for n, (d, g) in enumerate(zip(dut, gold)):
        for field in case["compare"]:
            if field in d["out"] and d["out"][field] != g["out"][field]:
                return {"verdict": "FAIL", "step": n + 1, "field": field}
    return {"verdict": "PASS", "step": None, "field": None}


def trace_view(trace):
    """What the clause audit may see: each step's input and the design's observed outputs, nothing else."""
    return [{"op": s["op"], "value": s.get("value"), "out": dict(s["out"])} for s in trace]


def clause_audit(spec, view):
    """Evaluate each numbered spec clause on the observed trace and return clause-level reason codes.

    A rule-based clause evaluator: it stands in for the paper's model-based cross-check and makes no model call.
    It never sees the golden model, the variant name or the planted label.
    """
    depth = spec["capacity"]["depth"]
    occupancy, queue, found = 0, [], {}

    def flag(rule, code, step):
        key = (spec[rule]["id"], rule, code)
        first, count = found.get(key, (step, 0))
        found[key] = (first, count + 1)

    for n, s in enumerate(view, 1):
        o = s["out"]
        if s["op"] == "push":
            if occupancy >= depth:
                if o["ok"]:
                    flag("capacity", "push_accepted_when_full", n)
            elif not o["ok"]:
                flag("capacity", "push_refused_when_not_full", n)
            else:
                queue.append(s["value"])
                occupancy += 1
        elif occupancy == 0:
            if o["served"] or o["value"] is not None:
                flag("underflow", "pop_when_empty_returned_data", n)
        elif not o["served"]:
            flag("order", "pop_not_served_when_not_empty", n)
        else:
            if o["value"] != queue.pop(0):
                flag("order", "pop_out_of_order", n)
            occupancy -= 1
        if o["count"] != occupancy:
            flag("count", "count_mismatch", n)
        if o["full"] != (occupancy == depth):
            flag("flags", "full_flag_wrong", n)
        if o["empty"] != (occupancy == 0):
            flag("flags", "empty_flag_wrong", n)
    reasons = [{"clause": k[0], "rule": k[1], "code": k[2], "first_step": v[0], "count": v[1]}
               for k, v in found.items()]
    reasons.sort(key=lambda r: (r["first_step"], r["clause"], r["code"]))
    return {"verdict": "FAIL" if reasons else "PASS", "reasons": reasons}


# ---------------------------------------------------------------- scoring

OUTCOMES = {("PASS", "FAIL"): "escape", ("PASS", "PASS"): "clean", ("FAIL", "FAIL"): "real_fail",
            ("FAIL", "PASS"): "scoreboard_only"}


def _rate(rows, plant, pred):
    group = [r for r in rows if r["planted"] == plant]
    return "%d/%d" % (sum(1 for r in group if pred(r)), len(group))


def run(fx):
    rows = []
    for case in fx["cases"]:
        sb = scoreboard(case, fx["depth"])
        au = clause_audit(fx["spec"], trace_view(simulate(case["dut"], fx["depth"], case["stimulus"])))
        outcome = OUTCOMES[(sb["verdict"], au["verdict"])]
        rows.append({"id": case["id"], "planted": case["planted"], "scoreboard": sb, "clause_audit": au,
                     "outcome": outcome, "matches_plant": outcome == case["planted"]})

    def all_of(plant, pred):
        group = [r for r in rows if r["planted"] == plant]
        return bool(group) and all(pred(r) for r in group)

    sb_pass = lambda r: r["scoreboard"]["verdict"] == "PASS"
    au_pass = lambda r: r["clause_audit"]["verdict"] == "PASS"
    clause_ids = {c["id"] for c in fx["spec"].values()}
    checks = {
        "a_escapes_pass_scoreboard_and_fail_a_clause": all_of(
            "escape", lambda r: sb_pass(r) and not au_pass(r)
            and all(x["clause"] in clause_ids for x in r["clause_audit"]["reasons"])),
        "b_clean_cases_pass_both": all_of("clean", lambda r: sb_pass(r) and au_pass(r)),
        "c_real_fails_fail_both": all_of("real_fail", lambda r: not sb_pass(r) and not au_pass(r)),
        "d_offline": True,
    }
    summary = {
        "cases": len(rows),
        "escapes_passed_by_scoreboard": _rate(rows, "escape", sb_pass),
        "escapes_failed_by_clause_audit": _rate(rows, "escape", lambda r: not au_pass(r)),
        "clean_failed_by_clause_audit": _rate(rows, "clean", lambda r: not au_pass(r)),
        "real_fails_failed_by_scoreboard": _rate(rows, "real_fail", lambda r: not sb_pass(r)),
        "real_fails_failed_by_clause_audit": _rate(rows, "real_fail", lambda r: not au_pass(r)),
        "all_cases_match_their_plant": all(r["matches_plant"] for r in rows),
    }
    return {"rows": rows, "summary": summary, "checks": checks, "network": False, "model_calls": 0,
            "on_expiry": ON_EXPIRY,
            "scope": "fixture-authored plants; counts are not model or real-world rates"}


def report(fx):
    return json.dumps(run(fx), indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("ERROR usage: spec_review.py FIXTURE.json (on_expiry DENY)\n")
        return 2
    try:
        text = report(load_fixture(argv[1]))
    except ReviewError as e:
        sys.stderr.write("ERROR %s: %s (on_expiry DENY)\n" % (e.code, e.detail))
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
