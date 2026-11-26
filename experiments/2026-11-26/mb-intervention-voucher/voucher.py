"""mb-intervention-voucher: a history-replay pass is not assurance for a what-if answer.

Method sketch of arXiv 2611.31736, "Reproducing History Is Not Enough: Intervention-Level Assurance for
LLM-Generated Simulators" (CC BY 4.0). Not a reproduction: synthetic named records, scripted simulators with
planted faults, no model, no network, no upstream code or text.

- Records are named integer counts. History is a list of events {record, op, amount}; op is add, sub or set.
- A what-if question changes the starting value of one named record ({record, op, amount}) and asks for that
  record's final value after the same history.
- A simulator reports a replayed final state and, per question, {applied_to, op, answer}.
- Arm A (replay only): PASS iff the replayed final state equals the recorded final state.
- Arm B (per-question voucher): a question is VOUCHED iff applied_to is the named record, op is the asked op and
  the answer equals the reference counterfactual. If the asked change leaves the start value unchanged and the
  report matches, the status is NO_INTERVENTION: not a FAIL and not a trusted what-if. Anything else is FAIL.
  Arm B closes iff no question FAILs and at least one question is VOUCHED.
- The fixture declares the expected table per simulator before the run. Gate PASS (exit 0) iff the observed table
  equals it; otherwise FAIL (exit 1).
Bad input is on_expiry DENY: exit 2, empty stdout, one stderr line 'DENY <code>: <detail>'.
"""

import json
import re
import sys

FIXTURE_VERSION = 1
ON_EXPIRY = "DENY"
MAX_BYTES = 32768
MAX_ABS = 10 ** 6
OPS = ("add", "sub", "set")
FAULTS = ("none", "wrong_record", "wrong_operator", "drop_last_event")
STATUSES = ("VOUCHED", "NO_INTERVENTION", "FAIL")
ROOT_KEYS = ("fixture_version", "on_expiry", "records", "history", "recorded_final", "questions", "simulators")
EVENT_KEYS = ("record", "op", "amount")
QUESTION_KEYS = ("id", "record", "op", "amount")
SIM_KEYS = ("id", "fault", "fault_question", "fault_value", "expected")
EXPECTED_KEYS = ("arm_a", "arm_b", "questions")
ID_RE = re.compile(r"[a-z][a-z0-9_]{0,39}\Z")


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
    # type first, so a list or object id is DENY bad_type before any dict or set lookup
    if type(value) is not str or not ID_RE.match(value):
        raise Deny("bad_type", "%s must be a string matching [a-z][a-z0-9_]{0,39}" % where)
    return value


def _int(value, where):
    if type(value) is not int:
        raise Deny("bad_type", "%s must be an integer" % where)
    if abs(value) > MAX_ABS:
        raise Deny("out_of_range", "%s must be within -%d..%d" % (where, MAX_ABS, MAX_ABS))
    return value


def _record(value, records, where):
    if _ident(value, where) not in records:
        raise Deny("unknown_record", "%s %r is not a declared record" % (where, value))
    return value


def _op(value, where):
    if type(value) is not str:
        raise Deny("bad_type", "%s must be a string" % where)
    if value not in OPS:
        raise Deny("bad_op", "%s must be add, sub or set" % where)
    return value


def _state(value, where):
    if type(value) is not dict or not value:
        raise Deny("bad_type", "%s must be a non-empty object of record counts" % where)
    for name in value:
        _ident(name, where + " record name")
        _int(value[name], "%s[%s]" % (where, name))
    return dict(value)


def validate(root):
    root = _obj(root, ROOT_KEYS, "fixture")
    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:
        raise Deny("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    if root["on_expiry"] != ON_EXPIRY:
        raise Deny("bad_on_expiry", "on_expiry must be the literal DENY")
    records = _state(root["records"], "records")
    history = []
    for n, ev in enumerate(_list(root["history"], "history")):
        where = "history event %d" % (n + 1)
        ev = _obj(ev, EVENT_KEYS, where)
        history.append((_record(ev["record"], records, where + " record"), _op(ev["op"], where + " op"),
                        _int(ev["amount"], where + " amount")))
    if not history:
        raise Deny("bad_history", "history must have at least one event")
    recorded = _state(root["recorded_final"], "recorded_final")
    if sorted(recorded) != sorted(records):
        raise Deny("bad_history", "recorded_final must name exactly the declared records")
    if replay(records, history) != recorded:
        raise Deny("bad_history", "recorded_final does not follow from records and history")
    questions = []
    for n, q in enumerate(_list(root["questions"], "questions")):
        where = "question %d" % (n + 1)
        q = _obj(q, QUESTION_KEYS, where)
        qid = _ident(q["id"], where + " id")
        if qid in [x["id"] for x in questions]:
            raise Deny("duplicate_id", "questions repeat the id %r" % qid)
        questions.append({"id": qid, "record": _record(q["record"], records, where + " record"),
                          "op": _op(q["op"], where + " op"), "amount": _int(q["amount"], where + " amount")})
    if not questions:
        raise Deny("missing_field", "questions must not be empty")
    qids = [q["id"] for q in questions]
    sims = []
    for n, s in enumerate(_list(root["simulators"], "simulators")):
        where = "simulator %d" % (n + 1)
        s = _obj(s, SIM_KEYS, where)
        sid = _ident(s["id"], where + " id")
        if sid in [x["id"] for x in sims]:
            raise Deny("duplicate_id", "simulators repeat the id %r" % sid)
        sims.append(_sim(s, sid, records, qids, where))
    if not sims:
        raise Deny("missing_field", "simulators must not be empty")
    return {"records": records, "history": history, "recorded": recorded, "questions": questions, "sims": sims}


def _sim(s, sid, records, qids, where):
    fault, fq, fv = s["fault"], s["fault_question"], s["fault_value"]
    if type(fault) is not str:
        raise Deny("bad_type", "%s fault must be a string" % where)
    if fault not in FAULTS:
        raise Deny("bad_fault", "%s fault must be one of %s" % (where, ", ".join(FAULTS)))
    if fault in ("none", "drop_last_event"):
        if fq is not None or fv is not None:
            raise Deny("bad_fault", "%s fault %s takes null fault_question and fault_value" % (where, fault))
    else:
        if _ident(fq, where + " fault_question") not in qids:
            raise Deny("unknown_question", "%s fault_question %r is not a declared question" % (where, fq))
        if fault == "wrong_record":
            _record(fv, records, where + " fault_value")
        else:
            _op(fv, where + " fault_value")
    exp = _obj(s["expected"], EXPECTED_KEYS, where + " expected")
    for arm in ("arm_a", "arm_b"):
        if exp[arm] not in ("PASS", "FAIL"):
            raise Deny("bad_expected", "%s expected %s must be PASS or FAIL" % (where, arm))
    eq = exp["questions"]
    if type(eq) is not dict:
        raise Deny("bad_type", "%s expected questions must be an object" % where)
    for qid in eq:
        _ident(qid, where + " expected question id")
    if sorted(eq) != sorted(qids):
        raise Deny("bad_expected", "%s expected questions must name every question exactly once" % where)
    for qid in eq:
        if eq[qid] not in STATUSES:
            raise Deny("bad_expected", "%s expected status for %s must be one of %s" % (where, qid, ", ".join(STATUSES)))
    return {"id": sid, "fault": fault, "fault_question": fq, "fault_value": fv,
            "expected": {"arm_a": exp["arm_a"], "arm_b": exp["arm_b"], "questions": dict(eq)}}


def load(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_BYTES + 1)
    except OSError:
        raise Deny("unreadable", "fixture is missing or cannot be read")
    if len(data) > MAX_BYTES:
        raise Deny("too_large", "fixture is larger than %d bytes" % MAX_BYTES)
    try:
        root = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs, parse_float=_no_float,
                          parse_constant=_no_constant)
    except Deny:
        raise
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise Deny("not_json", "fixture is not valid UTF-8 JSON")
    return validate(root)


# ---------------------------------------------------------------- simulation

def apply_op(value, op, amount):
    if op == "add":
        return value + amount
    if op == "sub":
        return value - amount
    return amount


def replay(start, history):
    state = dict(start)
    for record, op, amount in history:
        state[record] = apply_op(state[record], op, amount)
    return state


def reference(fx, q):
    start = dict(fx["records"])
    start[q["record"]] = apply_op(start[q["record"]], q["op"], q["amount"])
    return replay(start, fx["history"])[q["record"]]


def simulate(fx, sim):
    """A scripted simulator with one planted fault (or none). Returns its replay and its per-question reports."""
    history = fx["history"][:-1] if sim["fault"] == "drop_last_event" else fx["history"]
    reports = {}
    for q in fx["questions"]:
        target, op = q["record"], q["op"]
        if sim["fault_question"] == q["id"]:
            if sim["fault"] == "wrong_record":
                target = sim["fault_value"]
            elif sim["fault"] == "wrong_operator":
                op = sim["fault_value"]
        start = dict(fx["records"])
        start[target] = apply_op(start[target], op, q["amount"])
        reports[q["id"]] = {"applied_to": target, "op": op, "answer": replay(start, history)[target]}
    return replay(fx["records"], history), reports


# ---------------------------------------------------------------- the two arms

def arm_replay(fx, replayed):
    return "PASS" if replayed == fx["recorded"] else "FAIL"


def voucher(fx, q, report):
    if report["applied_to"] != q["record"]:
        return "FAIL", "change applied to %s, not the named record %s" % (report["applied_to"], q["record"])
    if report["op"] != q["op"]:
        return "FAIL", "operator %s, not the asked %s" % (report["op"], q["op"])
    want = reference(fx, q)
    if report["answer"] != want:
        return "FAIL", "answer %d, reference counterfactual %d" % (report["answer"], want)
    if apply_op(fx["records"][q["record"]], q["op"], q["amount"]) == fx["records"][q["record"]]:
        return "NO_INTERVENTION", "the asked change leaves the start value unchanged"
    return "VOUCHED", "named record, asked operator, answer %d" % want


def arm_voucher(statuses):
    fails = sum(1 for s in statuses if s == "FAIL")
    vouched = sum(1 for s in statuses if s == "VOUCHED")
    return "PASS" if fails == 0 and vouched > 0 else "FAIL"


def run(fx):
    rows = []
    for sim in fx["sims"]:
        replayed, reports = simulate(fx, sim)
        qrows = []
        for q in fx["questions"]:
            status, why = voucher(fx, q, reports[q["id"]])
            qrows.append({"question": q["id"], "status": status, "why": why,
                          "expected": sim["expected"]["questions"][q["id"]]})
        a = arm_replay(fx, replayed)
        b = arm_voucher([r["status"] for r in qrows])
        observed = {"arm_a": a, "arm_b": b, "questions": {r["question"]: r["status"] for r in qrows}}
        rows.append({"simulator": sim["id"], "fault": sim["fault"], "arm_a": a, "arm_b": b, "questions": qrows,
                     "trusted": sum(1 for r in qrows if r["status"] == "VOUCHED"),
                     "matches_expected": observed == sim["expected"]})
    gate = "PASS" if all(r["matches_expected"] for r in rows) else "FAIL"
    return {"rows": rows, "gate": gate, "on_expiry": ON_EXPIRY}


# ---------------------------------------------------------------- output

def report(res):
    out = ["# Replay-only (arm A) vs per-question intervention voucher (arm B)", "",
           "Synthetic, planted faults; a mechanism demo, not the paper's rates.", "",
           "| simulator | fault | arm A replay | arm B voucher | trusted answers | matches declared table |",
           "|---|---|---|---|---|---|"]
    for r in res["rows"]:
        out.append("| %s | %s | %s | %s | %d | %s |" % (r["simulator"], r["fault"], r["arm_a"], r["arm_b"],
                                                    r["trusted"], "yes" if r["matches_expected"] else "NO"))
    out += ["", "| simulator | question | voucher | expected | why |", "|---|---|---|---|---|"]
    for r in res["rows"]:
        for q in r["questions"]:
            out.append("| %s | %s | %s | %s | %s |" % (r["simulator"], q["question"], q["status"], q["expected"],
                                                     q["why"]))
    out += ["", "gate: %s" % res["gate"], "on_expiry: %s" % res["on_expiry"]]
    return "\n".join(out) + "\n"


def main(argv, out=None, err=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    args = argv[1:]
    as_json = args[:1] == ["--json"]
    if as_json:
        args = args[1:]
    if len(args) != 1:
        err.write("DENY usage: voucher.py [--json] FIXTURE.json\n")
        return 2
    try:
        res = run(load(args[0]))
    except Deny as e:
        err.write("DENY %s: %s\n" % (e.code, e.detail))
        return 2
    out.write(json.dumps(res, indent=1, sort_keys=True) + "\n" if as_json else report(res))
    return 0 if res["gate"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
