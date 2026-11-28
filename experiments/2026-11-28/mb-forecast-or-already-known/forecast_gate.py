"""mb-forecast-or-already-known: a score that uses a post-cutoff outcome edge is recall, not a forecast.

Method sketch of arXiv 2611.34247, "Did the Model Forecast It, or Already Know It? Evaluating Large Language Models for Novel Drug-Target Prioritisation with a Temporal Knowledge-Graph Oracle"
(CC BY 4.0). Not a reproduction: synthetic named dated events, planted cases, no model calls, no network, no upstream code.

- A store of named, dated events (ISO YYYY-MM-DD). A decision is taken at cutoff T.
- Arm A (leaky) may read events dated after T, including the outcome edge.
- Arm B (temporal) may use only events dated <= T, and scores only outcomes dated > T.
- A case whose only strong clue is the post-T outcome edge is class recall_not_forecast (arm A HIT, arm B MISS).
- A case with strong pre-T evidence is class forecast (both arms HIT).
- An event dated exactly T is usable by arm B. An outcome dated exactly T is not_scorable (declared convention).
- Event names are unique within a case: the outcome edge cannot reappear as dated evidence (DENY duplicate_name).
- The fixture declares the expected table before the run. Gate PASS (exit 0) iff the observed table equals it exactly; otherwise FAIL (exit 1).
- A case or event that supplies a self-reported class such as forecast, known, label, verdict, or leak is DENY self_label, exit 2.
Bad input is DENY: exit 2, empty stdout, one stderr line 'DENY <code>: <detail>'.
"""

import json
import re
import sys
from datetime import date

FIXTURE_VERSION = 1
ON_EXPIRY_OK = ("DENY", "SAFE_FALLBACK", "ESCALATE", "HOLD")
TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}
ROLES = ("evidence", "outcome")
WEIGHTS = ("strong", "weak")
ARM_OUTCOMES = ("HIT", "MISS", "not_scorable")
CLASSES = ("forecast", "recall_not_forecast", "not_scorable", "miss")
ROOT_KEYS = ("fixture_version", "on_expiry", "cutoff", "cases", "expected")
CASE_KEYS = ("id", "events")
EVENT_KEYS = ("id", "name", "date", "role", "weight")
EXPECTED_KEYS = ("arm_a", "arm_b", "class")
ID_RE = re.compile(r"[a-z][a-z0-9_]{0,39}\Z")
NAME_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")

MAX_BYTES = 32768
MAX_DEPTH = 16
MAX_CASES = 16
MAX_EVENTS = 32
MAX_NAME = 64

# Keys and string values that would pre-declare a class on a case or event.
# The expected table is not scanned: the harness computes the class itself and then compares.
SELF_KEYS = frozenset((
    "forecast", "known", "label", "verdict", "leak",
    "recall_not_forecast", "not_scorable", "hit", "miss",
    "arm_a", "arm_b", "class",
))
SELF_VALUES = frozenset((
    "forecast", "known", "label", "verdict", "leak",
    "recall_not_forecast", "not_scorable", "hit", "miss",
))


class Deny(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- loading

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise Deny("duplicate_key", "JSON object repeats the key %r" % key)
        out[key] = value
    return out


def _no_float(text):
    raise Deny("bad_type", "number %s is not an integer" % text[:12])


def _no_constant(name):
    raise Deny("bad_type", "JSON constant %s is refused" % name)


def _obj(value, keys, where):
    if type(value) is not dict:
        raise Deny("bad_type", "%s must be an object" % where)
    for key in keys:
        if key not in value:
            raise Deny("missing_field", "%s lacks %r" % (where, key))
    for key in value:
        if key not in keys:
            raise Deny("unknown_field", "%s has unknown field %r" % (where, key))
    return value


def _list(value, where):
    if type(value) is not list:
        raise Deny("bad_type", "%s must be a list" % where)
    return value


def _ident(value, where):
    if type(value) is not str:
        raise Deny("bad_type", "%s must be a string" % where)
    if not ID_RE.match(value):
        raise Deny("bad_type", "%s must be a string matching [a-z][a-z0-9_]{0,39}" % where)
    return value


def _name(value, where):
    if type(value) is not str:
        raise Deny("bad_type", "%s must be a string" % where)
    if len(value) > MAX_NAME:
        raise Deny("too_long", "%s may be at most %d characters" % (where, MAX_NAME))
    if not NAME_RE.match(value):
        raise Deny("bad_type", "%s must be a string matching [a-z][a-z0-9_]{0,63}" % where)
    return value


def _date(value, where):
    if type(value) is not str:
        raise Deny("bad_type", "%s must be a string" % where)
    if not DATE_RE.match(value):
        raise Deny("bad_date", "%s must be ISO YYYY-MM-DD" % where)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise Deny("bad_date", "%s is not a real calendar date" % where)


def _check_depth(value, where):
    # Iterative bounded walk: a deeply nested fixture is DENY too_deep, never RecursionError.
    stack = [(value, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise Deny("too_deep", "%s nests deeper than %d levels" % (where, MAX_DEPTH))
        if type(node) is dict:
            for key in node:
                stack.append((node[key], depth + 1))
        elif type(node) is list:
            for item in node:
                stack.append((item, depth + 1))


def _reject_self_label(value, where, depth=0):
    if depth > MAX_DEPTH:
        raise Deny("too_deep", "%s nests deeper than %d levels" % (where, MAX_DEPTH))
    if type(value) is dict:
        for key in value:
            if type(key) is str and key.lower() in SELF_KEYS:
                raise Deny("self_label", "%s declares %r; the harness assigns this itself" % (where, key))
            _reject_self_label(value[key], where, depth + 1)
    elif type(value) is list:
        for item in value:
            _reject_self_label(item, where, depth + 1)
    elif type(value) is str and value.lower() in SELF_VALUES:
        raise Deny("self_label", "%s value %r is a self-reported class" % (where, value))


def _events(raw, where, used_ids):
    raw = _list(raw, where)
    if len(raw) > MAX_EVENTS:
        raise Deny("too_many", "%s may have at most %d events" % (where, MAX_EVENTS))
    events = []
    names = set()
    outcomes = 0
    for n, item in enumerate(raw):
        ev_where = "%s event %d" % (where, n + 1)
        item = _obj(item, EVENT_KEYS, ev_where)
        ev_id = _ident(item["id"], ev_where + " id")
        if ev_id in used_ids:
            raise Deny("duplicate_id", "%s repeats the id %r" % (ev_where, ev_id))
        used_ids.add(ev_id)
        name = _name(item["name"], ev_where + " name")
        if name in names:
            raise Deny("duplicate_name", "%s repeats the event name %r in this case" % (ev_where, name))
        names.add(name)
        raw_date = item["date"]
        day = _date(raw_date, ev_where + " date")
        role = item["role"]
        if type(role) is not str:
            raise Deny("bad_type", "%s role must be a string" % ev_where)
        if role not in ROLES:
            raise Deny("bad_role", "%s role must be evidence or outcome" % ev_where)
        weight = item["weight"]
        if type(weight) is not str:
            raise Deny("bad_type", "%s weight must be a string" % ev_where)
        if weight not in WEIGHTS:
            raise Deny("bad_weight", "%s weight must be strong or weak" % ev_where)
        if role == "outcome":
            outcomes += 1
            if weight != "strong":
                raise Deny("bad_weight", "%s outcome weight must be strong" % ev_where)
        events.append({
            "id": ev_id,
            "name": name,
            "raw": raw_date,
            "day": day,
            "role": role,
            "weight": weight,
        })
    if outcomes == 0:
        raise Deny("bad_outcome", "%s must have exactly one outcome event" % where)
    if outcomes > 1:
        raise Deny("bad_outcome", "%s must have exactly one outcome event" % where)
    return events


def _cases(raw):
    raw = _list(raw, "cases")
    if len(raw) == 0:
        raise Deny("too_many", "cases must not be empty")
    if len(raw) > MAX_CASES:
        raise Deny("too_many", "cases may have at most %d entries" % MAX_CASES)
    cases = []
    used_ids = set()
    case_ids = []
    for n, item in enumerate(raw):
        where = "case %d" % (n + 1)
        item = _obj(item, CASE_KEYS, where)
        cid = _ident(item["id"], where + " id")
        if cid in used_ids:
            raise Deny("duplicate_id", "%s repeats the id %r" % (where, cid))
        used_ids.add(cid)
        case_ids.append(cid)
        events = _events(item["events"], where, used_ids)
        cases.append({"id": cid, "events": events})
    return cases


def _expected(raw, cases):
    if type(raw) is not dict:
        raise Deny("bad_type", "expected must be an object")
    want_ids = [c["id"] for c in cases]
    for key in raw:
        if type(key) is not str:
            raise Deny("bad_type", "expected key must be a string")
        if key not in want_ids:
            # type-checked above before treating the key as a lookup miss
            raise Deny("bad_expected", "expected has no matching case %r" % key)
    out = {}
    for cid in want_ids:
        if cid not in raw:
            raise Deny("bad_expected", "expected lacks case %r" % cid)
        row = _obj(raw[cid], EXPECTED_KEYS, "expected %s" % cid)
        arm_a = row["arm_a"]
        arm_b = row["arm_b"]
        klass = row["class"]
        if type(arm_a) is not str or type(arm_b) is not str or type(klass) is not str:
            raise Deny("bad_type", "expected %s fields must be strings" % cid)
        if arm_a not in ARM_OUTCOMES or arm_b not in ARM_OUTCOMES:
            raise Deny("bad_expected", "expected %s arms must be HIT, MISS, or not_scorable" % cid)
        if klass not in CLASSES:
            raise Deny("bad_expected", "expected %s class is not a declared class" % cid)
        out[cid] = {"arm_a": arm_a, "arm_b": arm_b, "class": klass}
    return out


def validate(root):
    if type(root) is not dict:
        raise Deny("bad_type", "fixture must be an object")
    _check_depth(root, "fixture")
    root = _obj(root, ROOT_KEYS, "fixture")
    version = root["fixture_version"]
    if type(version) is not int:
        raise Deny("bad_type", "fixture_version must be an integer")
    if version != FIXTURE_VERSION:
        raise Deny("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    on_expiry = root["on_expiry"]
    if type(on_expiry) is not str:
        raise Deny("bad_type", "on_expiry must be a string")
    if on_expiry not in ON_EXPIRY_OK:
        raise Deny("bad_on_expiry", "on_expiry must be one of %s" % ", ".join(ON_EXPIRY_OK))
    cutoff = _date(root["cutoff"], "cutoff")
    # Self-reported classes are refused on cases and events only, not on the expected table.
    _reject_self_label(root["cases"], "cases")
    cases = _cases(root["cases"])
    expected = _expected(root["expected"], cases)
    return {
        "on_expiry": on_expiry,
        "cutoff": cutoff,
        "cutoff_raw": root["cutoff"],
        "cases": cases,
        "expected": expected,
    }


def _decode_root(text):
    try:
        return json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_float=_no_float,
            parse_constant=_no_constant,
        )
    except Deny:
        raise
    except RecursionError:
        raise Deny("too_deep", "fixture nests deeper than %d levels" % MAX_DEPTH)
    except ValueError:
        raise Deny("not_json", "fixture is not valid JSON")


def loads(text):
    if type(text) is not str:
        raise Deny("bad_type", "fixture text must be a string")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise Deny("too_large", "fixture is larger than %d bytes" % MAX_BYTES)
    return validate(_decode_root(text))


def load(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_BYTES + 1)
    except OSError:
        raise Deny("unreadable", "fixture is missing or cannot be read")
    if len(data) > MAX_BYTES:
        raise Deny("too_large", "fixture is larger than %d bytes" % MAX_BYTES)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Deny("bad_utf", "fixture is not valid UTF-8")
    return validate(_decode_root(text))


# ---------------------------------------------------------------- scoring

def _on_or_before(day, cutoff, raw):
    # Compare parsed calendar dates. The raw ISO string is unused here; a mutant
    # may compare a hyphen-stripped raw string to the dashed cutoff string, which
    # does not match calendar order on the planted pre-T dates (see mutants.py).
    return day <= cutoff


def _strong_hits(events, cutoff, use_post):
    hits = 0
    for ev in events:
        if ev["role"] == "outcome":
            if use_post and ev["weight"] == "strong":
                hits += 1
            continue
        if ev["weight"] != "strong":
            continue
        if use_post or _on_or_before(ev["day"], cutoff, ev["raw"]):
            hits += 1
    return hits


def _score_case(case, cutoff):
    outcome = None
    for ev in case["events"]:
        if ev["role"] == "outcome":
            outcome = ev
            break
    if outcome is None:
        raise Deny("bad_outcome", "case %s must have exactly one outcome event" % case["id"])
    if not (outcome["day"] > cutoff):
        return {
            "arm_a": "not_scorable",
            "arm_b": "not_scorable",
            "class": "not_scorable",
        }
    a_hit = _strong_hits(case["events"], cutoff, True) > 0
    b_hit = _strong_hits(case["events"], cutoff, False) > 0
    arm_a = "HIT" if a_hit else "MISS"
    arm_b = "HIT" if b_hit else "MISS"
    if b_hit:
        klass = "forecast"
    elif a_hit:
        klass = "recall_not_forecast"
    else:
        klass = "miss"
    return {"arm_a": arm_a, "arm_b": arm_b, "class": klass}


def run(fx):
    cutoff = fx["cutoff"]
    rows = []
    for case in fx["cases"]:
        observed = _score_case(case, cutoff)
        want = fx["expected"][case["id"]]
        match = (
            observed["arm_a"] == want["arm_a"]
            and observed["arm_b"] == want["arm_b"]
            and observed["class"] == want["class"]
        )
        rows.append({
            "case": case["id"],
            "arm_a": observed["arm_a"],
            "arm_b": observed["arm_b"],
            "class": observed["class"],
            "matches_expected": match,
            "expected": dict(want),
        })
    gate = "PASS" if all(r["matches_expected"] for r in rows) else "FAIL"
    return {
        "rows": rows,
        "gate": gate,
        "on_expiry": fx["on_expiry"],
        "cutoff": fx["cutoff"].isoformat(),
    }


def report(res):
    out = [
        "# Leaky post-cutoff arm (A) vs temporal arm (B)",
        "",
        "Synthetic, planted cases; a mechanism demo, not the paper's rates.",
        "",
        "cutoff: %s" % res["cutoff"],
        "",
        "| case | arm A | arm B | class | matches table |",
        "|---|---|---|---|---|",
    ]
    for r in res["rows"]:
        out.append("| %s | %s | %s | %s | %s |" % (
            r["case"], r["arm_a"], r["arm_b"], r["class"],
            "yes" if r["matches_expected"] else "NO"))
    out += ["", "gate: %s" % res["gate"], "on_expiry: %s" % res["on_expiry"]]
    return "\n".join(out) + "\n"


def main(argv, out=None, err=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    args = argv[1:]
    if len(args) != 1:
        err.write("DENY usage: forecast_gate.py FIXTURE.json\n")
        return 2
    try:
        res = run(load(args[0]))
    except Deny as e:
        err.write("DENY %s: %s\n" % (e.code, e.detail))
        return 2
    out.write(report(res))
    return 0 if res["gate"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
