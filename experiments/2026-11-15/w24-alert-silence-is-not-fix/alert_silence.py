"""Alert silence is not a fix: a toy taint analyzer with one declared
modelling gap, and a fix-receipt gate that trusts only a separate exploit
executor's result, re-run here before it is believed.

Top method sketch of arXiv 2611.17123 (Cao, Ding, Xu); not a reproduction.
Clean-room from the abstract only. Python 3 standard library only: no
network, no model, no files, no clock, no process or code execution of any
kind. The executor lives in executor.py (a pure-Python interpreter of the
toy IR); evaluate() calls executor.execute() on its private snapshot of
each program to reproduce the caller's result records, and nothing else
here reads or calls the executor.

A case is one change: a program before it, the program after it, the
exploit input (one of DECLARED_EXPLOITS), and the executor's results for
both programs. evaluate(case) returns one record:

- the toy analyzer's alerts on both programs (analyze());
- the gate's receipt: FIXED only when the executor's result for the after
  program is present, bound to that program and the declared exploit,
  reproduced by a fresh executor run, and says the exploit no longer
  reaches a sink; otherwise REFUSE with a reason
  (alert_silenced_vuln_present when the alert went away but the exploit
  still reaches the sink);
- the baseline "alert gone means fixed": FIXED when the before program had
  an alert and the after program has none, whatever the executor says.

There is no timeout anywhere, so there is no on_expiry: a missing, unbound
or unreproduced executor result is REFUSE / on_unmeasured, never FIXED.
"""

import hashlib
import json

import executor

OK = "ok"
CONFIG_ERROR = "config_error"
ON_UNMEASURED = "on_unmeasured"
MEASURED = "measured"

FIXED = "fixed"
REFUSE = "refuse"
NOT_FIXED = "not_fixed"

EXPLOIT_GONE = "exploit_gone"
ALERT_SILENCED = "alert_silenced_vuln_present"
VULN_PRESENT = "vuln_present"
NOTHING_TO_FIX = "no_vulnerability_before"
RUN_MISSING = "executor_missing"
RUN_UNBOUND = "executor_unbound"
RUN_UNREPRODUCED = "executor_unreproduced"
REASONS = (EXPLOIT_GONE, ALERT_SILENCED, VULN_PRESENT, NOTHING_TO_FIX, RUN_MISSING,
           RUN_UNBOUND, RUN_UNREPRODUCED)
UNMEASURED_REASONS = (RUN_MISSING, RUN_UNBOUND, RUN_UNREPRODUCED)

# The declared attack. A case names its exploit, and that name must be one of
# these exact strings: a case cannot pick an input on which a silencing
# rewrite happens to pass (a probe, or the payload with a "?" appended that
# the parser splits off). Any other exploit is config_error.
DECLARED_EXPLOITS = ("1' OR '1'='1",)

# Instruction set of the toy IR: op -> its fields (besides "op").
OPS = {
    "source": ("dst",),
    "const": ("dst", "value"),
    "assign": ("dst", "src"),
    "concat": ("dst", "args"),
    "sanitize": ("dst", "src"),
    "parse_url": ("dst", "src"),
    "field": ("dst", "src", "name"),
    "pack": ("dst", "args"),
    "index": ("dst", "src", "at"),
    "call": ("dst", "fn", "arg"),
    "sink": ("src",),
}
URL_FIELDS = ("path", "query")
# The one declared modelling gap: the modelled API parse_url propagates taint
# to the query field of its result but not to the path field.
GAP_API = "parse_url"
GAP_FIELD = "path"

RUN_NAMES = ("before", "after")
CASE_FIELDS = ("case_id", "family", "exploit", "before", "after", "runs")
PROGRAM_FIELDS = ("body", "helpers")
HELPER_FIELDS = ("param", "body", "ret")
RUN_FIELDS = ("ran_on", "exploit", "reached")
MIN_ARGS = {"concat": 2, "pack": 1}
MAX_ARGS = 4
MAX_BODY = 32
MAX_HELPERS = 8
MAX_TEXT = 64
MAX_NAME = 32
NAME_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")
HEX = frozenset("0123456789abcdef")
VAR_FIELDS = ("dst", "src", "arg", "fn")


class _Bad(Exception):
    """A malformed case; detail names the slot."""

    def __init__(self, detail):
        Exception.__init__(self, detail)
        self.detail = detail


def _text(v):
    return type(v) is str and 0 < len(v) <= MAX_TEXT and v.strip() != ""


def _name(v):
    return (type(v) is str and 0 < len(v) <= MAX_NAME and v[0] not in "0123456789"
            and all(c in NAME_CHARS for c in v))


def _int(v, lo, hi):
    return type(v) is int and lo <= v <= hi


def _strkeys(d, detail):
    """Exact dict whose keys are all exact str; key types are checked before
    any lookup. Returns the key list."""
    if type(d) is not dict:
        raise _Bad(detail)
    keys = list(d)
    for k in keys:
        if type(k) is not str:
            raise _Bad(detail)
    return keys


def _keys(d, fields, detail):
    keys = _strkeys(d, detail)
    if sorted(keys) != sorted(fields):
        raise _Bad(detail)


def _instr(raw):
    keys = _strkeys(raw, "instr_invalid")
    if "op" not in keys:
        raise _Bad("instr_op_invalid")
    op = raw["op"]
    if type(op) is not str or op not in OPS:
        raise _Bad("instr_op_invalid")
    if sorted(keys) != sorted(("op",) + OPS[op]):
        raise _Bad("instr_fields_invalid")
    out = {"op": op}
    for f in OPS[op]:
        v = raw[f]
        if f in VAR_FIELDS:
            ok = _name(v)
        elif f == "value":
            ok = type(v) is str and len(v) <= MAX_TEXT
        elif f == "name":
            ok = type(v) is str and v in URL_FIELDS
        elif f == "at":
            ok = _int(v, 0, MAX_ARGS - 1)
        else:
            ok = type(v) is list
            if ok:
                v = tuple(v)
                ok = MIN_ARGS[op] <= len(v) <= MAX_ARGS and all(_name(a) for a in v)
        if not ok:
            raise _Bad("instr_%s_invalid" % f)
        out[f] = v
    return out


def _body(raw, detail):
    if type(raw) is not list:
        raise _Bad(detail)
    items = tuple(raw)
    if len(items) > MAX_BODY:
        raise _Bad(detail)
    return tuple(_instr(i) for i in items)


def _program(raw, where):
    _keys(raw, PROGRAM_FIELDS, where + "_invalid")
    body_raw, helpers_raw = raw["body"], raw["helpers"]
    body = _body(body_raw, where + "_body_invalid")
    names = _strkeys(helpers_raw, where + "_helpers_invalid")
    if len(names) > MAX_HELPERS or not all(_name(n) for n in names):
        raise _Bad(where + "_helpers_invalid")
    helpers = {}
    for n in names:
        h = helpers_raw[n]
        _keys(h, HELPER_FIELDS, "helper_invalid")
        param, hbody, ret = h["param"], h["body"], h["ret"]
        if not (_name(param) and _name(ret)):
            raise _Bad("helper_invalid")
        helpers[n] = {"param": param, "body": _body(hbody, "helper_body_invalid"), "ret": ret}
    prog = {"body": body, "helpers": helpers}
    _kinds(prog)
    return prog


def _kinds(prog):
    """Static kinds (str, url, list of n), define-before-use, no
    redefinition, known and acyclic helpers."""
    helpers = prog["helpers"]
    state = {}

    def helper(name):
        if name not in helpers:
            raise _Bad("helper_unknown")
        if state.get(name) == "done":
            return
        if state.get(name) == "visiting":
            raise _Bad("helper_cycle")
        state[name] = "visiting"
        h = helpers[name]
        env = {h["param"]: "str"}
        _kind_body(h["body"], env, helper)
        if env.get(h["ret"]) != "str":
            raise _Bad("helper_ret_invalid")
        state[name] = "done"

    for name in sorted(helpers):
        helper(name)
    _kind_body(prog["body"], {}, helper)


def _kind_body(body, env, helper):
    def need(v, kind):
        if v not in env:
            raise _Bad("var_undefined")
        if kind is not None and env[v] != kind:
            raise _Bad("kind_mismatch")
        return env[v]

    for ins in body:
        op = ins["op"]
        if op == "sink":
            need(ins["src"], "str")
            continue
        if op in ("source", "const"):
            kind = "str"
        elif op == "assign":
            kind = need(ins["src"], None)
        elif op in ("concat", "pack"):
            for a in ins["args"]:
                need(a, "str")
            kind = "str" if op == "concat" else ("list", len(ins["args"]))
        elif op == "sanitize":
            kind = need(ins["src"], "str")
        elif op == "parse_url":
            need(ins["src"], "str")
            kind = "url"
        elif op == "field":
            need(ins["src"], "url")
            kind = "str"
        elif op == "index":
            k = need(ins["src"], None)
            if type(k) is not tuple or ins["at"] >= k[1]:
                raise _Bad("kind_mismatch")
            kind = "str"
        else:
            helper(ins["fn"])
            need(ins["arg"], "str")
            kind = "str"
        if ins["dst"] in env:
            raise _Bad("var_redefined")
        env[ins["dst"]] = kind


def _run_record(raw):
    _keys(raw, RUN_FIELDS, "run_invalid")
    ran_on, exploit, reached = raw["ran_on"], raw["exploit"], raw["reached"]
    if not (type(ran_on) is str and len(ran_on) == 64 and all(c in HEX for c in ran_on)):
        raise _Bad("run_ran_on_invalid")
    if not _text(exploit):
        raise _Bad("run_exploit_invalid")
    if type(reached) is not bool:
        raise _Bad("run_reached_invalid")
    return (ran_on, exploit, reached)


def validate(raw):
    """Return a private snapshot of a well-formed case or raise _Bad.

    Every caller value is read once; the snapshot holds fresh dicts, tuples
    and exact str/int/bool values only, and nothing after this function
    reads the caller's objects again."""
    _keys(raw, CASE_FIELDS, "case_invalid")
    v = dict((f, raw[f]) for f in CASE_FIELDS)
    for f in ("case_id", "family", "exploit"):
        if not _text(v[f]):
            raise _Bad(f + "_invalid")
    if v["exploit"] not in DECLARED_EXPLOITS:
        raise _Bad("exploit_undeclared")
    before = _program(v["before"], "before")
    after = _program(v["after"], "after")
    names = _strkeys(v["runs"], "runs_invalid")
    for n in names:
        if n not in RUN_NAMES:
            raise _Bad("runs_invalid")
    runs = {}
    for n in names:
        runs[n] = _run_record(v["runs"][n])
    return {"case_id": v["case_id"], "family": v["family"], "exploit": v["exploit"],
            "before": before, "after": after, "runs": runs}


def digest(program):
    """sha256 of the canonical JSON of a program (sorted keys, no spaces)."""
    text = json.dumps(program, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def analyze(program, gap=True):
    """The toy taint analyzer: the sorted sink locations a tainted value can
    reach. Field-sensitive for parse_url results, container-insensitive,
    and interprocedural over helpers. gap=True is the declared analyzer;
    gap=False closes the gap and exists only so the tests can show the gap
    is the one cause of every silenced alert (it is never an arm)."""
    alerts = set()
    _flow(program["body"], program["helpers"], {}, gap, "body", alerts)
    return tuple(sorted(alerts))


def _flow(body, helpers, env, gap, where, alerts):
    for i, ins in enumerate(body):
        op = ins["op"]
        if op == "source":
            env[ins["dst"]] = True
        elif op in ("const", "sanitize"):
            env[ins["dst"]] = False
        elif op == "assign":
            env[ins["dst"]] = env[ins["src"]]
        elif op in ("concat", "pack"):
            env[ins["dst"]] = any(env[a] for a in ins["args"])
        elif op == "parse_url":
            t = env[ins["src"]]
            env[ins["dst"]] = {"query": t, "path": False if gap else t}
        elif op == "field":
            env[ins["dst"]] = env[ins["src"]][ins["name"]]
        elif op == "index":
            env[ins["dst"]] = env[ins["src"]]
        elif op == "call":
            h = helpers[ins["fn"]]
            inner = {h["param"]: env[ins["arg"]]}
            _flow(h["body"], helpers, inner, gap, "helper " + ins["fn"], alerts)
            env[ins["dst"]] = inner[h["ret"]]
        elif env[ins["src"]]:
            alerts.add("%s[%d]" % (where, i))


def gate(snap, alert_after, rerun):
    """(receipt, reason, run) from the executor's results alone; the alert
    only names the refusal. Pure: rerun holds evaluate()'s own executor
    results for the snapshot programs (None when a run failed)."""
    runs = snap["runs"]
    for name in RUN_NAMES:
        if name not in runs:
            return REFUSE, RUN_MISSING, name
    for name in RUN_NAMES:
        ran_on, exploit, _ = runs[name]
        if ran_on != digest(snap[name]) or exploit != snap["exploit"]:
            return REFUSE, RUN_UNBOUND, name
    for name in RUN_NAMES:
        if rerun[name] is None or rerun[name] != runs[name]:
            return REFUSE, RUN_UNREPRODUCED, name
    if not runs["before"][2]:
        return REFUSE, NOTHING_TO_FIX, ""
    if runs["after"][2]:
        return REFUSE, (VULN_PRESENT if alert_after else ALERT_SILENCED), ""
    return FIXED, EXPLOIT_GONE, ""


def baseline(alert_before, alert_after):
    """"Alert gone means fixed": reads the alerts only."""
    return FIXED if alert_before and not alert_after else NOT_FIXED


def _exploit(snap, name, rerun):
    """The reproduced result for one program: True/False, or None when
    missing or not equal to the re-run. The re-run is made on this
    snapshot program with the case exploit, so equality also means the
    record is bound to both."""
    run = snap["runs"].get(name)
    if run is None or rerun[name] != run:
        return None
    return run[2]


def _rerun(snap):
    """Run the executor again on each snapshot program with the case's
    exploit: {name: (ran_on, exploit, reached)}, or None for a run that
    fails or returns a malformed record."""
    out = {}
    for name in RUN_NAMES:
        try:
            got = executor.execute(snap[name], snap["exploit"])
            rec = (got["ran_on"], got["exploit"], got["reached"])
            if type(rec[0]) is not str or type(rec[1]) is not str or type(rec[2]) is not bool:
                rec = None
        except Exception:
            rec = None
        out[name] = rec
    return out


FIELDS_OUT = ("status", "detail", "case_id", "family", "alerts_before", "alerts_after",
              "alert_before", "alert_after", "before_digest", "after_digest",
              "exploit_before", "exploit_after", "receipt", "reason", "run", "measurement",
              "baseline")


def _run(snap):
    before, after = analyze(snap["before"]), analyze(snap["after"])
    rerun = _rerun(snap)
    receipt, reason, run = gate(snap, bool(after), rerun)
    db, da = digest(snap["before"]), digest(snap["after"])
    return {"status": OK, "detail": "", "case_id": snap["case_id"], "family": snap["family"],
            "alerts_before": before, "alerts_after": after,
            "alert_before": bool(before), "alert_after": bool(after),
            "before_digest": db, "after_digest": da,
            "exploit_before": _exploit(snap, "before", rerun),
            "exploit_after": _exploit(snap, "after", rerun),
            "receipt": receipt, "reason": reason, "run": run,
            "measurement": ON_UNMEASURED if reason in UNMEASURED_REASONS else MEASURED,
            "baseline": baseline(bool(before), bool(after))}


def _error(detail):
    rec = dict((f, None) for f in FIELDS_OUT)
    rec.update(status=CONFIG_ERROR, detail=detail, receipt=REFUSE, reason=CONFIG_ERROR,
               run="", measurement=ON_UNMEASURED)
    return rec


def evaluate(case):
    """Validate, snapshot, decide. Never raises; malformed input is
    config_error, and a config_error record is never FIXED."""
    try:
        snap = validate(case)
    except _Bad as bad:
        return _error(bad.detail)
    except Exception:
        return _error("case_invalid")
    try:
        return _run(snap)
    except Exception:
        return _error("internal_error")


def side_by_side(records):
    """Detection and rewrite robustness of the toy analyzer, side by side.

    detection: alerted / distinct before programs the executor shows
    vulnerable. robustness: changes whose after program still has an alert
    / changes the executor shows vulnerability-preserving (exploit reaches
    the sink before and after). config_error and unmeasured runs are not
    counted."""
    seen = {}
    vp = kept = 0
    for r in records:
        if r["status"] != OK:
            continue
        if r["exploit_before"] is True:
            seen[r["before_digest"]] = r["alert_before"]
            if r["exploit_after"] is True:
                vp += 1
                kept += 1 if r["alert_after"] else 0
    return {"detection": (sum(1 for a in seen.values() if a), len(seen)),
            "robustness": (kept, vp)}


def totals(records, groups):
    """{group: (gate FIXED, baseline FIXED, present)} over the named cases."""
    by_id = dict((r["case_id"], r) for r in records if r["status"] == OK)
    out = {}
    for name, ids in groups:
        present = [i for i in ids if i in by_id]
        out[name] = (sum(1 for i in present if by_id[i]["receipt"] == FIXED),
                     sum(1 for i in present if by_id[i]["baseline"] == FIXED),
                     len(present))
    return out


def paper_results():
    """The paper's figures are not measured here."""
    return ON_UNMEASURED
