"""mb-support-without-takeover: a high accepted-suggestion count is not proof that the human still owns the surviving draft.

Method sketch of arXiv 2611.34673, "Supporting Without Taking Over: AI Support in Gratitude Writing"
(nonexclusive-distrib 1.0). Not a reproduction: synthetic drafts, declarative edit events, planted sessions,
no model calls, no wall-clock gate metric, no upstream code or text beyond the attributed quotes in README.md.

- The harness walks declarative edit events and measures surviving human/AI spans and the accepted-help count itself.
- A fixture or session that declares ownership, help, agency, or related scores is DENY self_reported_measure, exit 2.
- Arm A (help-count only): PASS iff accepted_help_count >= min_help. Scaffold prompts are not help.
- Arm B (ownership-preserving gate): PASS iff surviving text is non-empty and
  human_chars * min_den >= min_num * total_chars (exact integer comparison; no float rounding).
- Mode is a label only; it does not change either arm.
- The fixture declares the expected table before the run. Gate PASS (exit 0) iff the observed table equals it exactly;
  otherwise FAIL (exit 1).
Bad input is DENY: exit 2, empty stdout, one stderr line 'DENY <code>: <detail>'.
"""

import json
import re
import sys
from fractions import Fraction

FIXTURE_VERSION = 1
ON_EXPIRY_OK = ("DENY", "SAFE_FALLBACK", "ESCALATE", "HOLD")
MODES = ("cowrite", "scaffold")
OPS = ("human_insert", "offer", "accept", "reject", "scaffold", "human_expand", "delete", "replace")
ARMS = ("PASS", "FAIL")
ROOT_KEYS = ("fixture_version", "on_expiry", "min_ownership", "min_help", "sessions", "expected")
FRAC_KEYS = ("num", "den")
SESSION_KEYS = ("id", "mode", "events")
EXPECTED_KEYS = ("arm_a", "arm_b")
ID_RE = re.compile(r"[a-z][a-z0-9_]{0,39}\Z")

MAX_BYTES = 32768
MAX_SESSIONS = 8
MAX_EVENTS = 24
MAX_TEXT = 256
MAX_ABS = 10 ** 6
MAX_DEPTH = 16

SELF_REPORTED = (
    "ownership",
    "ownership_ratio",
    "help_count",
    "accepted_help",
    "accepted_help_count",
    "human_chars",
    "ai_chars",
    "agency",
    "perceived_agency",
)

OP_KEYS = {
    "human_insert": ("op", "id", "text"),
    "offer": ("op", "id", "text"),
    "accept": ("op", "id"),
    "reject": ("op", "id"),
    "scaffold": ("op", "id", "text"),
    "human_expand": ("op", "id", "text"),
    "replace": ("op", "id", "text"),
}


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
    if isinstance(value, bool) or not isinstance(value, int):
        raise Deny("bad_type", "%s must be an integer" % where)
    if abs(value) > MAX_ABS:
        raise Deny("out_of_range", "%s must be within -%d..%d" % (where, MAX_ABS, MAX_ABS))
    return value


def _text(value, where):
    if type(value) is not str:
        raise Deny("bad_type", "%s must be a string" % where)
    if len(value) > MAX_TEXT:
        raise Deny("too_long", "%s may be at most %d characters" % (where, MAX_TEXT))
    if value == "":
        raise Deny("bad_text", "%s must not be empty" % where)
    return value


def _reject_self_reported(value, where, depth=0):
    # bounded walk: a deeply nested fixture is DENY too_deep, never an uncaught RecursionError
    if depth > MAX_DEPTH:
        raise Deny("too_deep", "%s nests deeper than %d levels" % (where, MAX_DEPTH))
    if type(value) is dict:
        for key in value:
            if key in SELF_REPORTED:
                raise Deny("self_reported_measure",
                           "%s declares %s; the harness measures this itself" % (where, key))
            _reject_self_reported(value[key], where, depth + 1)
    elif type(value) is list:
        for item in value:
            _reject_self_reported(item, where, depth + 1)


def validate(root):
    if type(root) is not dict:
        raise Deny("bad_type", "fixture must be an object")
    _reject_self_reported(root, "fixture")
    root = _obj(root, ROOT_KEYS, "fixture")
    version = root["fixture_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise Deny("bad_type", "fixture_version must be an integer")
    if version != FIXTURE_VERSION:
        raise Deny("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    on_expiry = root["on_expiry"]
    if type(on_expiry) is not str:
        raise Deny("bad_type", "on_expiry must be a string")
    if on_expiry not in ON_EXPIRY_OK:
        raise Deny("bad_on_expiry", "on_expiry must be one of %s" % ", ".join(ON_EXPIRY_OK))
    min_own = _frac(root["min_ownership"], "min_ownership")
    min_help = _int(root["min_help"], "min_help")
    if min_help < 1 or min_help > 1000:
        raise Deny("out_of_range", "min_help must be in 1..1000")
    sessions = _sessions(root["sessions"])
    expected = _expected(root["expected"], sessions)
    return {
        "on_expiry": on_expiry,
        "min_ownership": min_own,
        "min_help": min_help,
        "sessions": sessions,
        "expected": expected,
    }


def _frac(raw, where):
    raw = _obj(raw, FRAC_KEYS, where)
    num = _int(raw["num"], where + " num")
    den = _int(raw["den"], where + " den")
    if num < 0 or den < 1 or num > den:
        raise Deny("out_of_range", "%s must have 0 <= num <= den and den >= 1" % where)
    return {"num": num, "den": den}


def _sessions(raw):
    raw = _list(raw, "sessions")
    if len(raw) > MAX_SESSIONS:
        raise Deny("too_many", "sessions may have at most %d entries" % MAX_SESSIONS)
    if not raw:
        raise Deny("missing_field", "sessions must not be empty")
    sessions = []
    seen = []
    for n, item in enumerate(raw):
        where = "session %d" % (n + 1)
        item = _obj(item, SESSION_KEYS, where)
        sid = _ident(item["id"], where + " id")
        if sid in seen:
            raise Deny("duplicate_id", "sessions repeat the id %r" % sid)
        seen.append(sid)
        mode = item["mode"]
        if type(mode) is not str:
            raise Deny("bad_type", "%s mode must be a string" % where)
        if mode not in MODES:
            raise Deny("unknown_mode", "%s mode must be one of %s" % (where, ", ".join(MODES)))
        events = _events(item["events"], where)
        sessions.append({"id": sid, "mode": mode, "events": events})
    return sessions


def _events(raw, where):
    raw = _list(raw, where + " events")
    if len(raw) > MAX_EVENTS:
        raise Deny("too_many", "%s events may have at most %d entries" % (where, MAX_EVENTS))
    if not raw:
        raise Deny("missing_field", "%s events must not be empty" % where)
    events = []
    for n, item in enumerate(raw):
        events.append(_event(item, "%s event %d" % (where, n + 1)))
    return events


def _event(item, where):
    if type(item) is not dict:
        raise Deny("bad_type", "%s must be an object" % where)
    if "op" not in item:
        raise Deny("missing_field", "%s lacks %r" % (where, "op"))
    op = item["op"]
    if type(op) is not str:
        raise Deny("bad_type", "%s op must be a string" % where)
    if op not in OPS:
        raise Deny("unknown_op", "%s op must be one of %s" % (where, ", ".join(OPS)))
    if op == "delete":
        return _delete_event(item, where)
    keys = OP_KEYS[op]
    item = _obj(item, keys, where)
    ev = {"op": op}
    if "id" in keys:
        ev["id"] = _ident(item["id"], where + " id")
    if "text" in keys:
        ev["text"] = _text(item["text"], where + " text")
    return ev


def _delete_event(item, where):
    if "id" in item and "index" in item:
        raise Deny("unknown_field", "%s must use exactly one of id or index" % where)
    if "id" in item:
        item = _obj(item, ("op", "id"), where)
        return {"op": "delete", "id": _ident(item["id"], where + " id")}
    if "index" in item:
        item = _obj(item, ("op", "index"), where)
        return {"op": "delete", "index": _int(item["index"], where + " index")}
    raise Deny("missing_field", "%s lacks id or index" % where)


def _expected(raw, sessions):
    if type(raw) is not dict:
        raise Deny("bad_type", "expected must be an object")
    want_ids = [s["id"] for s in sessions]
    for key in raw:
        if type(key) is not str or key not in want_ids:
            # type-check the key as an ident-shaped session id before treating it as a lookup miss
            if type(key) is not str:
                raise Deny("bad_type", "expected key must be a string")
            raise Deny("bad_expected", "expected has no matching session %r" % key)
    for sid in want_ids:
        if sid not in raw:
            raise Deny("bad_expected", "expected lacks session %r" % sid)
        row = _obj(raw[sid], EXPECTED_KEYS, "expected %s" % sid)
        arm_a = row["arm_a"]
        arm_b = row["arm_b"]
        if type(arm_a) is not str or type(arm_b) is not str:
            raise Deny("bad_type", "expected %s arms must be strings" % sid)
        if arm_a not in ARMS or arm_b not in ARMS:
            raise Deny("bad_expected", "expected %s arms must be PASS or FAIL" % sid)
    return {sid: {"arm_a": raw[sid]["arm_a"], "arm_b": raw[sid]["arm_b"]} for sid in want_ids}


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
    try:
        root = json.loads(text, object_pairs_hook=_pairs, parse_float=_no_float,
                          parse_constant=_no_constant)
    except Deny:
        raise
    except (ValueError, RecursionError):
        raise Deny("not_json", "fixture is not valid JSON")
    return validate(root)


# ---------------------------------------------------------------- harness measurement

def _span_index(spans, span_id, where):
    for i, span in enumerate(spans):
        if span["id"] == span_id:
            return i
    raise Deny("unknown_span", "%s refers to unknown span %r" % (where, span_id))


def apply_events(events):
    """Walk declarative events. The harness measures surviving spans and accepted help itself."""
    spans = []
    pending = {}
    used_ids = []
    accepted_help = 0
    scaffold_shown = 0
    inserted_human_chars = 0
    accepted_ai_chars = 0
    start_chars = 0

    def take_id(span_id, where):
        if span_id in used_ids or span_id in pending:
            raise Deny("duplicate_id", "%s repeats the id %r" % (where, span_id))
        used_ids.append(span_id)

    for n, ev in enumerate(events):
        where = "event %d" % (n + 1)
        op = ev["op"]
        if op == "human_insert":
            take_id(ev["id"], where)
            spans.append({"id": ev["id"], "source": "human", "text": ev["text"]})
            inserted_human_chars += len(ev["text"])
            if start_chars == 0:
                start_chars = len(ev["text"])
        elif op == "human_expand":
            take_id(ev["id"], where)
            spans.append({"id": ev["id"], "source": "human", "text": ev["text"]})
            inserted_human_chars += len(ev["text"])
        elif op == "offer":
            take_id(ev["id"], where)
            pending[ev["id"]] = ev["text"]
        elif op == "accept":
            if ev["id"] not in pending:
                raise Deny("unknown_span", "%s accepts an offer that is not pending" % where)
            text = pending.pop(ev["id"])
            spans.append({"id": ev["id"], "source": "ai", "text": text})
            accepted_help += 1
            accepted_ai_chars += len(text)
        elif op == "reject":
            if ev["id"] not in pending:
                raise Deny("unknown_span", "%s rejects an offer that is not pending" % where)
            pending.pop(ev["id"])
        elif op == "scaffold":
            take_id(ev["id"], where)
            scaffold_shown += 1
        elif op == "delete":
            if "id" in ev:
                i = _span_index(spans, ev["id"], where)
            else:
                i = ev["index"]
                if i < 0 or i >= len(spans):
                    raise Deny("out_of_range", "%s index %d is out of range" % (where, i))
            spans.pop(i)
        elif op == "replace":
            i = _span_index(spans, ev["id"], where)
            spans[i] = {"id": ev["id"], "source": "human", "text": ev["text"]}
            inserted_human_chars += len(ev["text"])
        else:
            raise Deny("unknown_op", "%s has unknown op" % where)

    human = sum(len(s["text"]) for s in spans if s["source"] == "human")
    ai = sum(len(s["text"]) for s in spans if s["source"] == "ai")
    total = human + ai
    if total <= 0:
        raise Deny("empty_surviving", "surviving text is empty")
    return {
        "spans": spans,
        "final_text": "".join(s["text"] for s in spans),
        "human_chars": human,
        "ai_chars": ai,
        "total_chars": total,
        "accepted_help_count": accepted_help,
        "scaffold_shown": scaffold_shown,
        "inserted_human_chars": inserted_human_chars,
        "accepted_ai_chars": accepted_ai_chars,
        "start_chars": start_chars,
        "text_grew": total > start_chars,
    }


def measure(session):
    measured = apply_events(session["events"])
    measured["id"] = session["id"]
    measured["mode"] = session["mode"]
    return measured


def _ownership_parts(measured):
    # Surviving spans only: a later delete or replace can restore the human share.
    return measured["human_chars"], measured["total_chars"]


def arm_a(accepted_help_count, min_help):
    return "PASS" if accepted_help_count >= min_help else "FAIL"


def arm_b(measured, min_num, min_den):
    human, total = _ownership_parts(measured)
    if total <= 0:
        return "FAIL"
    if human * min_den >= min_num * total:
        return "PASS"
    return "FAIL"


def run(fx):
    min_num = fx["min_ownership"]["num"]
    min_den = fx["min_ownership"]["den"]
    min_help = fx["min_help"]
    rows = []
    for session in fx["sessions"]:
        measured = measure(session)
        a = arm_a(measured["accepted_help_count"], min_help)
        b = arm_b(measured, min_num, min_den)
        observed = {"arm_a": a, "arm_b": b}
        want = fx["expected"][session["id"]]
        human, total = measured["human_chars"], measured["total_chars"]
        own = Fraction(human, total)
        rows.append({
            "session": session["id"],
            "mode": session["mode"],
            "arm_a": a,
            "arm_b": b,
            "accepted_help_count": measured["accepted_help_count"],
            "scaffold_shown": measured["scaffold_shown"],
            "human_chars": human,
            "ai_chars": measured["ai_chars"],
            "total_chars": total,
            "ownership": "%d/%d" % (own.numerator, own.denominator),
            "ownership_raw": "%d/%d" % (human, total),
            "start_chars": measured["start_chars"],
            "text_grew": measured["text_grew"],
            "final_text": measured["final_text"],
            "matches_expected": observed == want,
            "expected": dict(want),
        })
    gate = "PASS" if all(r["matches_expected"] for r in rows) else "FAIL"
    return {
        "rows": rows,
        "gate": gate,
        "on_expiry": fx["on_expiry"],
        "min_help": min_help,
        "min_ownership": "%d/%d" % (min_num, min_den),
        "min_num": min_num,
        "min_den": min_den,
    }


# ---------------------------------------------------------------- output

def report(res):
    out = [
        "# Help-count only (arm A) vs ownership-preserving gate (arm B)",
        "",
        "Synthetic, planted sessions; a mechanism demo, not the paper's rates.",
        "",
        "min_help: %d" % res["min_help"],
        "min_ownership: %s" % res["min_ownership"],
        "",
        "| session | mode | arm A | arm B | accepted help | ownership | human/total | text grew | matches table |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in res["rows"]:
        out.append("| %s | %s | %s | %s | %d | %s | %d/%d | %s | %s |" % (
            r["session"], r["mode"], r["arm_a"], r["arm_b"], r["accepted_help_count"],
            r["ownership"], r["human_chars"], r["total_chars"],
            "yes" if r["text_grew"] else "no",
            "yes" if r["matches_expected"] else "NO"))
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
        err.write("DENY usage: ownership.py [--json] FIXTURE.json\n")
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
