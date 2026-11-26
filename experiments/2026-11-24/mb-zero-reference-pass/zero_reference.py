"""mb-zero-reference-pass: an equivalence pass is not enough if a zero reference would have passed too.

Method sketch of arXiv 2611.27186, "What Does Matching a Human Intervention Effect Establish? Benchmark Checks for LLM
Simulations" (CC BY 4.0). Not a reproduction; no code copied (abstract figures are quoted with attribution); no model
is called.

Each contrast gives a human 90 percent interval [human_lo, human_hi] for an intervention effect, a candidate effect
(a point estimate, e.g. from a simulation) and an equivalence margin m > 0, all in the same units.

Declared equivalence rule (inclusive): the candidate c matches when it is within m of every point of the human
interval, that is human_hi - m <= c <= human_lo + m.
Zero reference: the same rule with c = 0 (no response at all). It passes exactly when the human interval already lies
inside [-m, m]. The zero-reference threshold is max(|human_lo|, |human_hi|): the smallest margin at which zero passes.

Two arms read the same contrasts:
- equivalence_only (weak): reports the equivalence decision alone.
- with_zero_reference (strict): reports the zero-reference result and threshold beside every equivalence decision,
  and calls a pass a response only when the zero reference fails.
Numbers are parsed as exact decimals with at most 30 decimal places, and the rule is evaluated with 80 significant
digits, enough for every in-cap value, so boundary cases are decided without rounding.
Malformed or missing input is on_expiry DENY: exit 2, empty stdout, one stderr line 'ERROR <code>: ...'.
"""

import decimal
import json
import sys
import unicodedata

D = decimal.Decimal
FIXTURE_VERSION = 1
ON_EXPIRY = "DENY"
CAPS = {
    "file_bytes": {"limit": 65536, "on_expiry": "DENY"},
    "contrasts": {"limit": 200, "on_expiry": "DENY"},
    "abs_value": {"limit": 100, "on_expiry": "DENY"},
    "text_chars": {"limit": 200, "on_expiry": "DENY"},
    "number_chars": {"limit": 32, "on_expiry": "DENY"},
    "decimal_places": {"limit": 30, "on_expiry": "DENY"},
}
RULE_PREC = 80  # |value| <= 100 with <= 30 decimal places needs at most 34 significant digits
PLANTED = ("real_response", "zero_reference", "genuine_fail", "fail_zero_passes")
ROOT_KEYS = ("fixture_version", "label", "contrasts")
CONTRAST_KEYS = ("id", "label", "units", "human_lo", "human_hi", "candidate", "margin", "planted")
ID_FIRST = set("abcdefghijklmnopqrstuvwxyz")
ID_CHARS = ID_FIRST | set("0123456789_")
INVISIBLE = {"Cc", "Cf", "Co", "Cs", "Cn", "Zl", "Zp"}


class ZeroRefError(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- loading

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ZeroRefError("duplicate_key", "JSON object repeats the key %r" % key)
        out[key] = value
    return out


def _constant(name):
    raise ZeroRefError("not_finite", "JSON constant %s is not a finite number" % name)


def _number_text(text):
    if len(text) > CAPS["number_chars"]["limit"]:
        raise ZeroRefError("bad_number", "number %s... is longer than %d characters"
                           % (text[:12], CAPS["number_chars"]["limit"]))
    return D(text)


def _object(value, keys, where):
    if type(value) is not dict:
        raise ZeroRefError("bad_shape", "%s must be an object" % where)
    for key in keys:
        if key not in value:
            raise ZeroRefError("missing_field", "%s lacks %r" % (where, key))
    for key in value:
        if key not in keys:
            raise ZeroRefError("unknown_field", "%s has unknown field %r" % (where, key))
    return value


def _text(value, where):
    if type(value) is not str:
        raise ZeroRefError("bad_type", "%s must be a string" % where)
    if value == "" or value != value.strip() or len(value) > CAPS["text_chars"]["limit"]:
        raise ZeroRefError("bad_text", "%s must be 1..%d characters with no outer spaces"
                           % (where, CAPS["text_chars"]["limit"]))
    if any(unicodedata.category(ch) in INVISIBLE for ch in value):
        raise ZeroRefError("bad_text", "%s holds a control or invisible character" % where)
    return unicodedata.normalize("NFC", value)


def _number(value, where):
    if type(value) is not D:
        raise ZeroRefError("bad_type", "%s must be a number" % where)
    if not value.is_finite():
        raise ZeroRefError("not_finite", "%s must be finite" % where)
    if value.copy_abs() > CAPS["abs_value"]["limit"]:  # exact and context-free: never rounds or overflows
        raise ZeroRefError("out_of_range", "%s must be within +-%d" % (where, CAPS["abs_value"]["limit"]))
    if -value.as_tuple().exponent > CAPS["decimal_places"]["limit"]:
        raise ZeroRefError("bad_number", "%s has more than %d decimal places" % (where, CAPS["decimal_places"]["limit"]))
    return value


def _contrast(raw, where):
    c = _object(raw, CONTRAST_KEYS, where)
    cid = c["id"]
    if type(cid) is not str or cid == "" or len(cid) > 40 or cid[0] not in ID_FIRST or any(
            ch not in ID_CHARS for ch in cid):
        raise ZeroRefError("bad_id", "%s id must match [a-z][a-z0-9_]{0,39}" % where)
    lo = _number(c["human_lo"], where + " human_lo")
    hi = _number(c["human_hi"], where + " human_hi")
    if lo > hi:
        raise ZeroRefError("interval_reversed", "%s human_lo %s is above human_hi %s" % (where, lo, hi))
    margin = _number(c["margin"], where + " margin")
    if margin <= 0:
        raise ZeroRefError("bad_margin", "%s margin must be above zero, got %s" % (where, margin))
    if c["planted"] not in PLANTED:
        raise ZeroRefError("bad_planted", "%s planted must be one of %s" % (where, ", ".join(PLANTED)))
    return {"id": cid, "label": _text(c["label"], where + " label"), "units": _text(c["units"], where + " units"),
            "human_lo": lo, "human_hi": hi, "candidate": _number(c["candidate"], where + " candidate"),
            "margin": margin, "planted": c["planted"]}


def validate(root):
    root = _object(root, ROOT_KEYS, "fixture")
    version = root["fixture_version"]
    if type(version) is not D or version.as_tuple().exponent != 0 or version != FIXTURE_VERSION:
        raise ZeroRefError("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    label = _text(root["label"], "fixture label")
    items = root["contrasts"]
    if type(items) is not list:
        raise ZeroRefError("bad_shape", "contrasts must be a list")
    if not items:
        raise ZeroRefError("empty_list", "contrasts must not be empty")
    if len(items) > CAPS["contrasts"]["limit"]:
        raise ZeroRefError("too_many", "more than %d contrasts (on_expiry DENY)" % CAPS["contrasts"]["limit"])
    out, seen = [], set()
    for n, raw in enumerate(items):
        c = _contrast(raw, "contrast %d" % (n + 1))
        if c["id"] in seen:
            raise ZeroRefError("duplicate_id", "contrast id %r repeats" % c["id"])
        seen.add(c["id"])
        out.append(c)
    return {"label": label, "contrasts": out}


def load_fixture(path):
    limit = CAPS["file_bytes"]["limit"]
    try:
        with open(path, "rb") as fh:
            data = fh.read(limit + 1)
    except OSError:
        raise ZeroRefError("unreadable", "fixture is missing or cannot be read")
    if len(data) > limit:
        raise ZeroRefError("too_large", "fixture is larger than %d bytes (on_expiry DENY)" % limit)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ZeroRefError("bad_encoding", "fixture is not valid UTF-8")
    try:
        root = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_number_text,
                          parse_int=_number_text)
    except ZeroRefError:
        raise
    except (ValueError, RecursionError, decimal.InvalidOperation):
        raise ZeroRefError("not_json", "fixture is not valid JSON")
    return validate(root)


# ---------------------------------------------------------------- the rule

def equivalent(effect, lo, hi, margin):
    """Inclusive: effect is within margin of every point of [lo, hi]."""
    return hi - margin <= effect <= lo + margin


def zero_threshold(lo, hi):
    """Smallest margin at which the zero reference passes."""
    return max(abs(lo), abs(hi))


def decide(c):
    with decimal.localcontext() as ctx:
        ctx.prec = RULE_PREC
        return _decide(c)


def _decide(c):
    eq = equivalent(c["candidate"], c["human_lo"], c["human_hi"], c["margin"])
    zero = equivalent(D(0), c["human_lo"], c["human_hi"], c["margin"])
    if eq and not zero:
        verdict = "response"
        note = "PASS; the zero reference fails, so the pass shows a response"
    elif eq:
        verdict = "zero_reference_pass"
        note = "PASS, but the zero reference passes too: this does not establish a response"
    elif zero:
        verdict = "fail"
        note = "FAIL; the zero reference would have passed"
    else:
        verdict = "fail"
        note = "FAIL"
    reachable = c["human_hi"] - c["human_lo"] <= 2 * c["margin"]
    return {"equivalence": "PASS" if eq else "FAIL", "zero_reference": "PASS" if zero else "FAIL",
            "zero_threshold": zero_threshold(c["human_lo"], c["human_hi"]), "verdict": verdict, "note": note,
            "match_window": (c["human_hi"] - c["margin"], c["human_lo"] + c["margin"]), "reachable": reachable}


EXPECTED = {
    "real_response": ("PASS", "FAIL"),
    "zero_reference": ("PASS", "PASS"),
    "genuine_fail": ("FAIL", "FAIL"),
    "fail_zero_passes": ("FAIL", "PASS"),
}


def run(fx):
    rows = []
    for c in fx["contrasts"]:
        d = decide(c)
        closed = (d["equivalence"], d["zero_reference"]) == EXPECTED[c["planted"]]
        rows.append(dict(c, **d, closed=closed))
    weak_passes = sum(1 for r in rows if r["equivalence"] == "PASS")
    responses = sum(1 for r in rows if r["verdict"] == "response")
    zero_passes = sum(1 for r in rows if r["verdict"] == "zero_reference_pass")
    return {"label": fx["label"], "rows": rows, "closed": sum(1 for r in rows if r["closed"]), "total": len(rows),
            "weak_passes": weak_passes, "responses": responses, "zero_reference_passes": zero_passes,
            "fails": len(rows) - weak_passes, "on_expiry": ON_EXPIRY}


def gate(res):
    return "PASS" if res["closed"] == res["total"] else "FAIL"


def _fmt(x):
    return format(x, "f")


def report(res):
    out = ["# Equivalence pass vs zero reference", "", "fixture: %s" % res["label"],
           "rule: candidate c matches when human_hi - m <= c <= human_lo + m (inclusive); the zero reference uses c = 0",
           "", "## Arm equivalence_only (weak)", "",
           "| contrast | candidate | human 90% interval | margin | equivalence |", "|---|---|---|---|---|"]
    for r in res["rows"]:
        out.append("| %s | %s | [%s, %s] | %s | %s |" % (r["id"], _fmt(r["candidate"]), _fmt(r["human_lo"]),
                                                     _fmt(r["human_hi"]), _fmt(r["margin"]), r["equivalence"]))
    out += ["", "weak arm: %d of %d contrasts match; it cannot say which matches show a response"
            % (res["weak_passes"], res["total"]), "", "## Arm with_zero_reference (strict)", "",
            "| contrast | equivalence | zero reference | zero passes at margin >= | verdict |", "|---|---|---|---|---|"]
    for r in res["rows"]:
        out.append("| %s | %s | %s | %s | %s |" % (r["id"], r["equivalence"], r["zero_reference"],
                                                  _fmt(r["zero_threshold"]), r["verdict"]))
    out.append("")
    for r in res["rows"]:
        lo, hi = r["match_window"]
        out.append("- %s (%s, %s): match window [%s, %s]; %s%s; planted %s: %s" % (
            r["id"], r["label"], r["units"], _fmt(lo), _fmt(hi), r["note"],
            "" if r["reachable"] else "; no candidate can match (the human interval is wider than twice the margin)",
            r["planted"], "closed" if r["closed"] else "OPEN"))
    out += ["", "## Summary",
            "equivalence passes: %d (weak arm reports all of them as matches)" % res["weak_passes"],
            "passes that show a response: %d; zero-reference passes: %d; fails: %d" % (
                res["responses"], res["zero_reference_passes"], res["fails"]),
            "closed: %d / %d planted contrasts" % (res["closed"], res["total"]),
            "gate: %s" % gate(res), "on_expiry: %s" % res["on_expiry"]]
    return "\n".join(out) + "\n"


def _jsonable(res):
    def conv(v):
        if isinstance(v, D):
            return _fmt(v)
        if isinstance(v, tuple):
            return [conv(x) for x in v]
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        if isinstance(v, list):
            return [conv(x) for x in v]
        return v
    return conv(res)


def main(argv, out=None, err=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    args = argv[1:]
    as_json = args[:1] == ["--json"]
    if as_json:
        args = args[1:]
    if len(args) != 1:
        err.write("ERROR usage: zero_reference.py [--json] FIXTURE.json (on_expiry=DENY)\n")
        return 2
    try:
        res = run(load_fixture(args[0]))
    except ZeroRefError as e:
        err.write("ERROR %s: %s (on_expiry=DENY)\n" % (e.code, e.detail))
        return 2
    if as_json:
        out.write(json.dumps(_jsonable(res), ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    else:
        out.write(report(res))
    return 0 if gate(res) == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
