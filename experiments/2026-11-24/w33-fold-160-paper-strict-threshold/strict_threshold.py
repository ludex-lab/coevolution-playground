"""w33-fold-160-paper-strict-threshold: the #160 zero-reference check with a paper-strict reading beside it.

A fold of experiments/2026-11-24/mb-zero-reference-pass (#160), rebuilt here as one self-contained stdlib module.
Method sketch of arXiv 2611.27186, "What Does Matching a Human Intervention Effect Establish? Benchmark Checks for LLM
Simulations" (CC BY 4.0). Not a reproduction; no code copied; no model is called.

Each contrast gives a human 90 percent interval [human_lo, human_hi], a candidate effect (a point estimate) and an
equivalence margin m > 0, all in the same units.

- Equivalence (inclusive, as in #160): the candidate c matches when human_hi - m <= c <= human_lo + m.
- Critical value T = max(|human_lo|, |human_hi|). The zero reference (c = 0) is read two ways, side by side:
  - inclusive (#160): passes when T <= m;
  - paper-strict: passes only when T < m. Under a strict rule no least passing margin exists; T is the infimum.
  At m = T the two readings differ: inclusive PASS, paper-strict FAIL.
- The verdict and the planted gate use the inclusive reading, so #160's planted outcomes are unchanged.

Numbers are exact decimals: at most 32 characters, |value| <= 100 compared with copy_abs() before any rounding, at most
30 decimal places, no positive exponent; the rule runs at 80 significant digits.
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
STRICT_ARM_HEADER = ("| contrast | equivalence | zero reference, inclusive (passes when T <= m) "
                     "| zero reference, paper-strict (passes only when T < m) | critical value T | verdict |")
STRICT_ARM_LEGEND = ("T = max(|human_lo|, |human_hi|) is the critical value: the inclusive reading passes zero at m = T, "
                     "the paper-strict reading does not, and under the strict rule no least passing margin exists "
                     "(T is the infimum)")


class FoldError(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- loading

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise FoldError("duplicate_key", "JSON object repeats the key %r" % key)
        out[key] = value
    return out


def _constant(name):
    raise FoldError("not_finite", "JSON constant %s is not a finite number" % name)


def _number_text(text):
    if len(text) > CAPS["number_chars"]["limit"]:
        raise FoldError("bad_number", "number %s... is longer than %d characters"
                        % (text[:12], CAPS["number_chars"]["limit"]))
    return D(text)


def _object(value, keys, where):
    if type(value) is not dict:
        raise FoldError("bad_shape", "%s must be an object" % where)
    for key in keys:
        if key not in value:
            raise FoldError("missing_field", "%s lacks %r" % (where, key))
    for key in value:
        if key not in keys:
            raise FoldError("unknown_field", "%s has unknown field %r" % (where, key))
    return value


def _text(value, where):
    if type(value) is not str:
        raise FoldError("bad_type", "%s must be a string" % where)
    if value == "" or value != value.strip() or len(value) > CAPS["text_chars"]["limit"]:
        raise FoldError("bad_text", "%s must be 1..%d characters with no outer spaces"
                        % (where, CAPS["text_chars"]["limit"]))
    if any(unicodedata.category(ch) in INVISIBLE for ch in value):
        raise FoldError("bad_text", "%s holds a control or invisible character" % where)
    return unicodedata.normalize("NFC", value)


def _number(value, where):
    if type(value) is not D:
        raise FoldError("bad_type", "%s must be a number" % where)
    value = D(value)  # a plain Decimal copy; exact, no context
    if not value.is_finite():
        raise FoldError("not_finite", "%s must be finite" % where)
    if value.copy_abs() > CAPS["abs_value"]["limit"]:  # exact and context-free: never rounds or overflows
        raise FoldError("out_of_range", "%s must be within +-%d" % (where, CAPS["abs_value"]["limit"]))
    exponent = value.as_tuple().exponent
    if exponent > 0:
        raise FoldError("bad_number", "%s must not use a positive exponent" % where)
    if -exponent > CAPS["decimal_places"]["limit"]:
        raise FoldError("bad_number", "%s has more than %d decimal places" % (where, CAPS["decimal_places"]["limit"]))
    return value


def _contrast(raw, where):
    c = _object(raw, CONTRAST_KEYS, where)
    cid = c["id"]
    if type(cid) is not str or cid == "" or len(cid) > 40 or cid[0] not in ID_FIRST or any(
            ch not in ID_CHARS for ch in cid):
        raise FoldError("bad_id", "%s id must match [a-z][a-z0-9_]{0,39}" % where)
    lo = _number(c["human_lo"], where + " human_lo")
    hi = _number(c["human_hi"], where + " human_hi")
    if lo > hi:
        raise FoldError("interval_reversed", "%s human_lo %s is above human_hi %s" % (where, lo, hi))
    margin = _number(c["margin"], where + " margin")
    if margin <= 0:
        raise FoldError("bad_margin", "%s margin must be above zero, got %s" % (where, margin))
    if c["planted"] not in PLANTED:
        raise FoldError("bad_planted", "%s planted must be one of %s" % (where, ", ".join(PLANTED)))
    return {"id": cid, "label": _text(c["label"], where + " label"), "units": _text(c["units"], where + " units"),
            "human_lo": lo, "human_hi": hi, "candidate": _number(c["candidate"], where + " candidate"),
            "margin": margin, "planted": c["planted"]}


def validate(root):
    root = _object(root, ROOT_KEYS, "fixture")
    version = root["fixture_version"]
    if type(version) is not D or version.as_tuple().exponent != 0 or version != FIXTURE_VERSION:
        raise FoldError("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    label = _text(root["label"], "fixture label")
    items = root["contrasts"]
    if type(items) is not list:
        raise FoldError("bad_shape", "contrasts must be a list")
    if not items:
        raise FoldError("empty_list", "contrasts must not be empty")
    if len(items) > CAPS["contrasts"]["limit"]:
        raise FoldError("too_many", "more than %d contrasts (on_expiry DENY)" % CAPS["contrasts"]["limit"])
    out, seen = [], set()
    for n, raw in enumerate(items):
        c = _contrast(raw, "contrast %d" % (n + 1))
        if c["id"] in seen:
            raise FoldError("duplicate_id", "contrast id %r repeats" % c["id"])
        seen.add(c["id"])
        out.append(c)
    return {"label": label, "contrasts": out}


def load_fixture(path):
    limit = CAPS["file_bytes"]["limit"]
    try:
        with open(path, "rb") as fh:
            data = fh.read(limit + 1)
    except OSError:
        raise FoldError("unreadable", "fixture is missing or cannot be read")
    if len(data) > limit:
        raise FoldError("too_large", "fixture is larger than %d bytes (on_expiry DENY)" % limit)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise FoldError("bad_encoding", "fixture is not valid UTF-8")
    try:
        root = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_number_text,
                          parse_int=_number_text)
    except FoldError:
        raise
    except (ValueError, RecursionError, decimal.InvalidOperation):
        raise FoldError("not_json", "fixture is not valid JSON")
    return validate(root)


# ---------------------------------------------------------------- the rule

def equivalent(effect, lo, hi, margin):
    """Inclusive: effect is within margin of every point of [lo, hi]."""
    return hi - margin <= effect <= lo + margin


def critical_value(lo, hi):
    """T = max(|lo|, |hi|): zero passes at m >= T (inclusive) and only at m > T (paper-strict)."""
    return max(lo.copy_abs(), hi.copy_abs())


def zero_passes_paper_strict(lo, hi, margin):
    return critical_value(lo, hi) < margin


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
    strict = zero_passes_paper_strict(c["human_lo"], c["human_hi"], c["margin"])
    reachable = c["human_hi"] - c["human_lo"] <= 2 * c["margin"]
    return {"equivalence": "PASS" if eq else "FAIL", "zero_reference": "PASS" if zero else "FAIL",
            "zero_reference_paper_strict": "PASS" if strict else "FAIL",
            "zero_threshold": critical_value(c["human_lo"], c["human_hi"]), "verdict": verdict, "note": note,
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
    return {"label": fx["label"], "rows": rows, "closed": sum(1 for r in rows if r["closed"]), "total": len(rows),
            "weak_passes": weak_passes, "responses": sum(1 for r in rows if r["verdict"] == "response"),
            "zero_reference_passes": sum(1 for r in rows if r["verdict"] == "zero_reference_pass"),
            "fails": len(rows) - weak_passes,
            "readings_differ": sum(1 for r in rows if r["zero_reference"] != r["zero_reference_paper_strict"]),
            "on_expiry": ON_EXPIRY}


def gate(res):
    return "PASS" if res["closed"] == res["total"] else "FAIL"


def _fmt(x):
    return format(x, "f")


def report(res):
    out = ["# Equivalence pass vs zero reference, inclusive and paper-strict", "", "fixture: %s" % res["label"],
           "rule: candidate c matches when human_hi - m <= c <= human_lo + m (inclusive); the zero reference uses c = 0",
           "", "## Arm equivalence_only (weak)", "",
           "| contrast | candidate | human 90% interval | margin | equivalence |", "|---|---|---|---|---|"]
    for r in res["rows"]:
        out.append("| %s | %s | [%s, %s] | %s | %s |" % (r["id"], _fmt(r["candidate"]), _fmt(r["human_lo"]),
                                                     _fmt(r["human_hi"]), _fmt(r["margin"]), r["equivalence"]))
    out += ["", "weak arm: %d of %d contrasts match; it cannot say which matches show a response"
            % (res["weak_passes"], res["total"]), "", "## Arm with_zero_reference (strict)", "",
            STRICT_ARM_HEADER, "|---|---|---|---|---|---|"]
    for r in res["rows"]:
        out.append("| %s | %s | %s | %s | %s | %s |" % (r["id"], r["equivalence"], r["zero_reference"],
                                                       r["zero_reference_paper_strict"], _fmt(r["zero_threshold"]),
                                                       r["verdict"]))
    out += ["", STRICT_ARM_LEGEND, ""]
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
            "zero-reference readings differ (inclusive PASS, paper-strict FAIL): %d" % res["readings_differ"],
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
        err.write("ERROR usage: strict_threshold.py [--json] FIXTURE.json (on_expiry=DENY)\n")
        return 2
    try:
        res = run(load_fixture(args[0]))
    except FoldError as e:
        err.write("ERROR %s: %s (on_expiry=DENY)\n" % (e.code, e.detail))
        return 2
    if as_json:
        out.write(json.dumps(_jsonable(res), ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    else:
        out.write(report(res))
    return 0 if gate(res) == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
