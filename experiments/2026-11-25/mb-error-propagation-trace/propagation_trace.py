"""mb-error-propagation-trace: a green final answer can hide an error that passed from one agent to the next.

Method sketch of arXiv 2611.31063, "From Local Errors to System Failures: Modeling and Benchmarking Error
Propagation in Multi-Agent LLM Systems" (arXiv nonexclusive-distrib 1.0). Method only: no code, text or figures
copied; no model is called. Not a reproduction of the paper's structural model.

A case is a chain of agents. Each agent is a deterministic local step on a numeric message: it receives the previous
message, applies its operation (add or mul by arg), and may add a planted fault. An agent with recheck true recomputes
its step from the reference input instead of the message it received (a later agent that checks the source).
The reference chain applies the same operations without faults, so every hop has a known correct value.

- Arm outcome_only (A): scores only the final message against the case tolerance.
- Arm per_hop_trace (B): records each hop's error magnitude e_k = |message_k - reference_k| and classifies the hop
  against the error it received, p = e_(k-1) (p = 0 for the first hop, which receives the correct start):
    clean       p <= tol and e_k <= tol
    introduced  p <= tol and e_k >  tol
    corrected   p >  tol and e_k <= tol
    amplified   p >  tol and e_k >= p   (equal magnitude counts as amplified: the error was not reduced)
    attenuated  p >  tol and tol < e_k < p
  An error exactly equal to tol is within tolerance. The trace verdict is reached_end (final error > tol),
  corrected (some hop error > tol, final error <= tol) or clean (no hop error > tol).

Numbers: exact decimals of at most 32 characters, |value| <= 1000000 (copy_abs, before rounding), at most 12 decimal
places, no positive exponent; NaN and Infinity are bad_number; booleans are bad_type; -0 is read as 0. Steps are
exact: 700 significant digits hold any in-cap chain (16 integer digits + 12 places per input and per mul, at most
51 inputs deep = 628 digits), and Inexact is trapped, so a rounded step is DENY computed_out_of_range instead of a
silent boundary flip; a computed value above 1E+15 in magnitude is DENY computed_out_of_range.
An empty chain is bad input (empty_chain). Bad input is on_expiry DENY: exit 2, empty stdout, one stderr line
'ERROR <code>: ...'.
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
    "cases": {"limit": 100, "on_expiry": "DENY"},
    "hops": {"limit": 50, "on_expiry": "DENY"},
    "abs_value": {"limit": 1000000, "on_expiry": "DENY"},
    "computed_abs": {"limit": D("1E+15"), "on_expiry": "DENY"},
    "number_chars": {"limit": 32, "on_expiry": "DENY"},
    "decimal_places": {"limit": 12, "on_expiry": "DENY"},
    "text_chars": {"limit": 200, "on_expiry": "DENY"},
}
STEP_PREC = 700  # exact for every in-cap chain: 16 + 12 * (1 + 50) = 628 digits at most
OPS = ("add", "mul")
CLASSES = ("clean", "introduced", "amplified", "attenuated", "corrected")
TRACES = ("clean", "reached_end", "corrected")
OUTCOMES = ("PASS", "FAIL")
ROOT_KEYS = ("fixture_version", "label", "cases")
CASE_KEYS = ("id", "label", "start", "tolerance", "hops", "expect")
HOP_KEYS = ("agent", "op", "arg")
HOP_OPTIONAL = ("fault", "recheck")
EXPECT_KEYS = ("outcome", "trace", "hops")
ID_FIRST = set("abcdefghijklmnopqrstuvwxyz")
ID_CHARS = ID_FIRST | set("0123456789_")
INVISIBLE = {"Cc", "Cf", "Co", "Cs", "Cn", "Zl", "Zp"}


class TraceError(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- loading

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise TraceError("duplicate_key", "JSON object repeats the key %r" % key)
        out[key] = value
    return out


def _constant(name):
    raise TraceError("bad_number", "JSON constant %s is not a finite number" % name)


def _number_text(text):
    if len(text) > CAPS["number_chars"]["limit"]:
        raise TraceError("bad_number", "number %s... is longer than %d characters"
                         % (text[:12], CAPS["number_chars"]["limit"]))
    return D(text)


def _object(value, required, where, optional=()):
    if type(value) is not dict:
        raise TraceError("bad_shape", "%s must be an object" % where)
    for key in required:
        if key not in value:
            raise TraceError("missing_field", "%s lacks %r" % (where, key))
    for key in value:
        if key not in required and key not in optional:
            raise TraceError("unknown_field", "%s has unknown field %r" % (where, key))
    return value


def _text(value, where):
    if type(value) is not str:
        raise TraceError("bad_type", "%s must be a string" % where)
    if value == "" or value != value.strip() or len(value) > CAPS["text_chars"]["limit"]:
        raise TraceError("bad_text", "%s must be 1..%d characters with no outer spaces"
                         % (where, CAPS["text_chars"]["limit"]))
    if any(unicodedata.category(ch) in INVISIBLE for ch in value):
        raise TraceError("bad_text", "%s holds a control or invisible character" % where)
    return unicodedata.normalize("NFC", value)


def _ident(value, where):
    if type(value) is not str or value == "" or len(value) > 40 or value[0] not in ID_FIRST or any(
            ch not in ID_CHARS for ch in value):
        raise TraceError("bad_id", "%s must match [a-z][a-z0-9_]{0,39}" % where)
    return value


def _number(value, where):
    if type(value) is not D:
        raise TraceError("bad_type", "%s must be a number" % where)
    value = D(value)  # plain Decimal copy; exact
    if not value.is_finite():
        raise TraceError("bad_number", "%s must be finite" % where)
    if value.copy_abs() > CAPS["abs_value"]["limit"]:
        raise TraceError("out_of_range", "%s must be within +-%d" % (where, CAPS["abs_value"]["limit"]))
    exponent = value.as_tuple().exponent
    if exponent > 0:
        raise TraceError("bad_number", "%s must not use a positive exponent" % where)
    if -exponent > CAPS["decimal_places"]["limit"]:
        raise TraceError("bad_number", "%s has more than %d decimal places" % (where, CAPS["decimal_places"]["limit"]))
    if value.is_zero():
        value = value.copy_abs()  # -0 is read as 0
    return value


def _hop(raw, where):
    h = _object(raw, HOP_KEYS, where, HOP_OPTIONAL)
    if h["op"] not in OPS:
        raise TraceError("bad_op", "%s op must be one of %s" % (where, ", ".join(OPS)))
    recheck = h.get("recheck", False)
    if type(recheck) is not bool:
        raise TraceError("bad_type", "%s recheck must be true or false" % where)
    return {"agent": _ident(h["agent"], where + " agent"), "op": h["op"], "arg": _number(h["arg"], where + " arg"),
            "fault": _number(h.get("fault", D(0)), where + " fault"), "recheck": recheck}


def _case(raw, where):
    c = _object(raw, CASE_KEYS, where)
    cid = _ident(c["id"], where + " id")
    tol = _number(c["tolerance"], where + " tolerance")
    if tol <= 0:
        raise TraceError("bad_tolerance", "%s tolerance must be above zero" % where)
    hops = c["hops"]
    if type(hops) is not list:
        raise TraceError("bad_shape", "%s hops must be a list" % where)
    if not hops:
        raise TraceError("empty_chain", "%s has no hops; an empty chain has no message to score" % where)
    if len(hops) > CAPS["hops"]["limit"]:
        raise TraceError("too_many", "%s has more than %d hops" % (where, CAPS["hops"]["limit"]))
    hops = [_hop(h, "%s hop %d" % (where, n + 1)) for n, h in enumerate(hops)]
    e = _object(c["expect"], EXPECT_KEYS, where + " expect")
    if e["outcome"] not in OUTCOMES or e["trace"] not in TRACES or type(e["hops"]) is not list or len(
            e["hops"]) != len(hops) or any(x not in CLASSES for x in e["hops"]):
        raise TraceError("bad_expect", "%s expect needs outcome PASS/FAIL, a trace verdict and one class per hop"
                         % where)
    return {"id": cid, "label": _text(c["label"], where + " label"), "start": _number(c["start"], where + " start"),
            "tolerance": tol, "hops": hops,
            "expect": {"outcome": e["outcome"], "trace": e["trace"], "hops": list(e["hops"])}}


def validate(root):
    root = _object(root, ROOT_KEYS, "fixture")
    version = root["fixture_version"]
    if type(version) is not D or version.as_tuple().exponent != 0 or version != FIXTURE_VERSION:
        raise TraceError("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    label = _text(root["label"], "fixture label")
    items = root["cases"]
    if type(items) is not list:
        raise TraceError("bad_shape", "cases must be a list")
    if not items:
        raise TraceError("empty_list", "cases must not be empty")
    if len(items) > CAPS["cases"]["limit"]:
        raise TraceError("too_many", "more than %d cases" % CAPS["cases"]["limit"])
    out, seen = [], set()
    for n, raw in enumerate(items):
        c = _case(raw, "case %d" % (n + 1))
        if c["id"] in seen:
            raise TraceError("duplicate_id", "case id %r repeats" % c["id"])
        seen.add(c["id"])
        out.append(c)
    return {"label": label, "cases": out}


def load_fixture(path):
    limit = CAPS["file_bytes"]["limit"]
    try:
        with open(path, "rb") as fh:
            data = fh.read(limit + 1)
    except OSError:
        raise TraceError("unreadable", "fixture is missing or cannot be read")
    if len(data) > limit:
        raise TraceError("too_large", "fixture is larger than %d bytes" % limit)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise TraceError("bad_encoding", "fixture is not valid UTF-8")
    try:
        root = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_number_text,
                          parse_int=_number_text)
    except TraceError:
        raise
    except (ValueError, RecursionError, decimal.InvalidOperation):
        raise TraceError("not_json", "fixture is not valid JSON")
    return validate(root)


# ---------------------------------------------------------------- the chain

def _apply(op, value, arg):
    out = value + arg if op == "add" else value * arg
    if not out.is_finite() or out.copy_abs() > CAPS["computed_abs"]["limit"]:
        raise TraceError("computed_out_of_range", "a computed value leaves +-1E+15")
    if out.is_zero():
        out = out.copy_abs()  # a computed -0 is reported as 0
    return out


def classify(prev, err, tol):
    """Classify one hop from the error it received (prev) and the error it passes on (err)."""
    if prev <= tol:
        return "clean" if err <= tol else "introduced"
    if err <= tol:
        return "corrected"
    return "amplified" if err >= prev else "attenuated"


def trace_case(case):
    ctx = decimal.Context(prec=STEP_PREC, rounding=decimal.ROUND_HALF_EVEN, Emax=999999, Emin=-999999,
                          traps=[decimal.Overflow, decimal.InvalidOperation, decimal.DivisionByZero, decimal.Inexact])
    try:
        with decimal.localcontext(ctx):
            return _trace(case)
    except decimal.Inexact:
        raise TraceError("computed_out_of_range", "a computed value cannot be held exactly")
    except (decimal.Overflow, decimal.InvalidOperation):
        raise TraceError("computed_out_of_range", "a computed value is not finite")


def _trace(case):
    tol = case["tolerance"]
    ref = msg = case["start"]
    prev = D(0)
    hops = []
    for n, h in enumerate(case["hops"]):
        ref_out = _apply(h["op"], ref, h["arg"])
        base = ref if h["recheck"] else msg
        msg_out = _apply("add", _apply(h["op"], base, h["arg"]), h["fault"])
        err = (msg_out - ref_out).copy_abs()
        hops.append({"hop": n + 1, "agent": h["agent"], "reference": ref_out, "message": msg_out, "error": err,
                     "class": classify(prev, err, tol), "recheck": h["recheck"]})
        ref, msg, prev = ref_out, msg_out, err
    final = hops[-1]["error"]
    outcome = "PASS" if final <= tol else "FAIL"
    if final > tol:
        trace = "reached_end"
    elif any(x["error"] > tol for x in hops):
        trace = "corrected"
    else:
        trace = "clean"
    exp = case["expect"]
    measured_classes = [x["class"] for x in hops]
    return {"id": case["id"], "label": case["label"], "tolerance": tol, "hops": hops, "final_error": final,
            "outcome": outcome, "trace": trace,
            "closed_a": outcome == exp["outcome"],
            "closed_b": (outcome, trace, measured_classes) == (exp["outcome"], exp["trace"], exp["hops"]),
            "expect": exp}


def run(fx):
    rows = [trace_case(c) for c in fx["cases"]]
    return {"label": fx["label"], "rows": rows, "total": len(rows),
            "closed_a": sum(1 for r in rows if r["closed_a"]), "closed_b": sum(1 for r in rows if r["closed_b"]),
            "a_passes": sum(1 for r in rows if r["outcome"] == "PASS"),
            "errors_hidden_by_a": sum(1 for r in rows if r["outcome"] == "PASS" and r["trace"] == "corrected"),
            "on_expiry": ON_EXPIRY}


def gate(res):
    return "PASS" if res["closed_b"] == res["total"] else "FAIL"


def _fmt(x):
    return format(x, "f")


def _story(r):
    if r["trace"] == "clean":
        return "no hop error above tolerance"
    starts = [x for x in r["hops"] if x["class"] == "introduced"]
    text = "error introduced at hop %s" % ", ".join("%d (%s)" % (x["hop"], x["agent"]) for x in starts)
    fixes = [x for x in r["hops"] if x["class"] == "corrected"]
    if fixes:
        text += "; corrected at hop %s" % ", ".join("%d (%s)" % (x["hop"], x["agent"]) for x in fixes)
    if r["trace"] == "corrected":
        return text + "; final PASS, but an error did occur"
    return text + "; the error reaches the final answer"


def report(res):
    out = ["# Outcome-only score vs per-hop error trace", "", "fixture: %s" % res["label"],
           "hop classes use the error received (p) and passed on (e): clean, introduced, amplified (e >= p), "
           "attenuated (tol < e < p), corrected (e <= tol after p > tol); e = tol is within tolerance",
           "", "## Arm outcome_only (A)", "", "| case | final message | final reference | tolerance | outcome |",
           "|---|---|---|---|---|"]
    for r in res["rows"]:
        last = r["hops"][-1]
        out.append("| %s | %s | %s | %s | %s |" % (r["id"], _fmt(last["message"]), _fmt(last["reference"]),
                                                  _fmt(r["tolerance"]), r["outcome"]))
    out += ["", "arm A: %d of %d cases PASS; it cannot say whether an error occurred on the way"
            % (res["a_passes"], res["total"]), "", "## Arm per_hop_trace (B)", "",
            "| case | hop | agent | reference | message | error | class |", "|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        for x in r["hops"]:
            out.append("| %s | %d | %s%s | %s | %s | %s | %s |" % (
                r["id"], x["hop"], x["agent"], " (recheck)" if x["recheck"] else "", _fmt(x["reference"]),
                _fmt(x["message"]), _fmt(x["error"]), x["class"]))
    out.append("")
    for r in res["rows"]:
        out.append("- %s (%s): outcome %s; trace %s: %s; planted: %s" % (
            r["id"], r["label"], r["outcome"], r["trace"], _story(r), "closed" if r["closed_b"] else "OPEN"))
    out += ["", "## Summary",
            "arm A closed: %d / %d (outcome only)" % (res["closed_a"], res["total"]),
            "arm B closed: %d / %d (outcome, trace and every hop class)" % (res["closed_b"], res["total"]),
            "final PASS with an error on the way (hidden from arm A): %d" % res["errors_hidden_by_a"],
            "gate: %s" % gate(res), "on_expiry: %s" % res["on_expiry"]]
    return "\n".join(out) + "\n"


def _jsonable(v):
    if isinstance(v, D):
        return _fmt(v)
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    return v


def main(argv, out=None, err=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    args = argv[1:]
    as_json = args[:1] == ["--json"]
    if as_json:
        args = args[1:]
    if len(args) != 1:
        err.write("ERROR usage: propagation_trace.py [--json] FIXTURE.json (on_expiry=DENY)\n")
        return 2
    try:
        res = run(load_fixture(args[0]))
    except TraceError as e:
        err.write("ERROR %s: %s (on_expiry=DENY)\n" % (e.code, e.detail))
        return 2
    if as_json:
        out.write(json.dumps(_jsonable(res), ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    else:
        out.write(report(res))
    return 0 if gate(res) == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
