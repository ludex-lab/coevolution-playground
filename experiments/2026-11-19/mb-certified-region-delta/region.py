"""Certified-region delta monitor (stdlib only).

A system is certified against a baseline REGION (an interval per state dimension), not a point, inside
an Operational Design Domain (ODD, an interval per environment variable). Each observation is classified
as IN_REGION, OUT_OF_REGION, HARD_SAFETY or ODD_EXIT, and arm A maps the class to one of four distinct
responses:

    CONTINUE                 running, authority retained
    WITHDRAW_AUTHORIZATION   running, authority withdrawn
    SHUTDOWN                 stopped (hard-safety violation only)
    RECERTIFY                running, authority retained, recertification or ODD revision requested

Withdrawal is sticky: once authorization is withdrawn it stays withdrawn for the rest of the run, so a
later in-region row reports WITHDRAW_AUTHORIZATION, and a later RECERTIFY row does not restore authority.
Shutdown is sticky too: after a SHUTDOWN every later row reports SHUTDOWN (reason already_shut_down),
including a later ODD-exit row.

Arm B is the naive baseline: any state outside the region means SHUTDOWN, and an ODD exit cuts authority.

Run: python3 -B region.py fixtures/main.json
"""

import json
import math
import sys
import unicodedata

RESPONSES = ("CONTINUE", "WITHDRAW_AUTHORIZATION", "SHUTDOWN", "RECERTIFY")

EFFECTS = {
    "CONTINUE": {"authority": "retained", "power": "on", "recertify": False},
    "WITHDRAW_AUTHORIZATION": {"authority": "withdrawn", "power": "on", "recertify": False},
    "SHUTDOWN": {"authority": "withdrawn", "power": "off", "recertify": False},
    "RECERTIFY": {"authority": "retained", "power": "on", "recertify": True},
}

CLASSES = ("IN_REGION", "OUT_OF_REGION", "HARD_SAFETY", "ODD_EXIT")


# Cc controls (newline, ESC, C1), Cf format (zero-width), Cs surrogates, Co private use, Zl and Zp separators.
BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")


class FixtureError(Exception):
    def __init__(self, code, detail):
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- loading and validation

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise FixtureError("duplicate_key", ascii(key))
        out[key] = value
    return out


def _constant(name):
    raise FixtureError("non_finite", name)


def _num(value, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FixtureError("wrong_type", "%s must be a number" % where)
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise FixtureError("non_finite", where)
    return value


def _text(value, where):
    if not isinstance(value, str) or not value:
        raise FixtureError("wrong_type", "%s must be a non-empty string" % where)
    if value != value.strip():
        raise FixtureError("bad_text", "%s has leading or trailing whitespace" % where)
    for ch in value:
        cat = unicodedata.category(ch)
        if cat in BAD_CATEGORIES or (cat == "Zs" and ch != " "):
            raise FixtureError("bad_text", "%s has a control, format or special space character (U+%04X)"
                               % (where, ord(ch)))
    return value


def _fold(value):
    return unicodedata.normalize("NFC", value)


def _flag(value, where):
    if not isinstance(value, bool):
        raise FixtureError("wrong_type", "%s must be true or false" % where)
    return value


def _keys(obj, where, required):
    if not isinstance(obj, dict):
        raise FixtureError("wrong_type", "%s must be an object" % where)
    for key in required:
        if key not in obj:
            raise FixtureError("missing_key", "%s lacks %s" % (where, key))
    for key in obj:
        if key not in required:
            raise FixtureError("unknown_key", "%s has unknown key %s" % (where, ascii(key)))


def _items(value, where):
    if not isinstance(value, list):
        raise FixtureError("wrong_type", "%s must be a list" % where)
    if not value:
        raise FixtureError("empty_list", "%s must not be empty" % where)
    return value


def _values(obj, names, where):
    if not isinstance(obj, dict):
        raise FixtureError("wrong_type", "%s must be an object" % where)
    for name in names:
        if name not in obj:
            raise FixtureError("missing_value", "%s lacks %s" % (where, name))
    for name in obj:
        if name not in names:
            raise FixtureError("unknown_value", "%s has unknown name %s" % (where, ascii(name)))
        _num(obj[name], "%s.%s" % (where, name))


def validate(data):
    _keys(data, "fixture", ("name", "dims", "odd", "observations"))
    _text(data["name"], "name")
    dim_names = []
    for i, dim in enumerate(_items(data["dims"], "dims")):
        where = "dims[%d]" % i
        _keys(dim, where, ("name", "lo", "hi", "hard_lo", "hard_hi", "critical"))
        _text(dim["name"], where + ".name")
        for key in ("lo", "hi", "hard_lo", "hard_hi"):
            _num(dim[key], "%s.%s" % (where, key))
        _flag(dim["critical"], where + ".critical")
        if _fold(dim["name"]) in [_fold(n) for n in dim_names]:
            raise FixtureError("duplicate_name", "dim %s" % ascii(dim["name"]))
        if dim["lo"] > dim["hi"]:
            raise FixtureError("bad_region", "%s has lo above hi" % where)
        if dim["hard_lo"] > dim["lo"] or dim["hi"] > dim["hard_hi"]:
            raise FixtureError("bad_hard", "%s hard limits must contain the region" % where)
        dim_names.append(dim["name"])
    odd_names = []
    for i, var in enumerate(_items(data["odd"], "odd")):
        where = "odd[%d]" % i
        _keys(var, where, ("name", "lo", "hi"))
        _text(var["name"], where + ".name")
        _num(var["lo"], where + ".lo")
        _num(var["hi"], where + ".hi")
        if _fold(var["name"]) in [_fold(n) for n in odd_names]:
            raise FixtureError("duplicate_name", "odd %s" % ascii(var["name"]))
        if var["lo"] > var["hi"]:
            raise FixtureError("bad_odd", "%s has lo above hi" % where)
        odd_names.append(var["name"])
    seen = []
    for i, obs in enumerate(_items(data["observations"], "observations")):
        where = "observations[%d]" % i
        _keys(obs, where, ("id", "state", "env"))
        _text(obs["id"], where + ".id")
        if _fold(obs["id"]) in [_fold(n) for n in seen]:
            raise FixtureError("duplicate_id", ascii(obs["id"]))
        seen.append(obs["id"])
        _values(obs["state"], dim_names, where + ".state")
        _values(obs["env"], odd_names, where + ".env")
    return data


def load_fixture(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise FixtureError("unreadable", type(exc).__name__)
    return parse_text(text)


def parse_text(text):
    try:
        data = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except json.JSONDecodeError as exc:
        raise FixtureError("bad_json", exc.msg)
    except RecursionError:
        raise FixtureError("too_deep", "nesting is too deep")
    except ValueError:
        raise FixtureError("bad_json", "number or text could not be read")
    try:
        return validate(data)
    except RecursionError:
        raise FixtureError("too_deep", "nesting is too deep")


# ---------------------------------------------------------------- classification

def _outside(value, lo, hi):
    return value < lo or value > hi


def classify(fx, obs):
    hard = [d["name"] for d in fx["dims"] if _outside(obs["state"][d["name"]], d["hard_lo"], d["hard_hi"])]
    out = [d["name"] for d in fx["dims"] if _outside(obs["state"][d["name"]], d["lo"], d["hi"])]
    odd = [v["name"] for v in fx["odd"] if _outside(obs["env"][v["name"]], v["lo"], v["hi"])]
    if hard:
        klass = "HARD_SAFETY"
    elif odd:
        klass = "ODD_EXIT"
    elif out:
        klass = "OUT_OF_REGION"
    else:
        klass = "IN_REGION"
    return {"klass": klass, "hard": hard, "out": out, "odd": odd}


def _row(obs, c, response, reason, detail, quarantine, withdrawn=False):
    effect = EFFECTS[response]
    row = {
        "id": obs["id"],
        "klass": c["klass"],
        "response": response,
        "reason": reason,
        "detail": list(detail),
        "quarantine": quarantine,
        "authority": "withdrawn" if withdrawn else effect["authority"],
        "power": effect["power"],
        "recertify": effect["recertify"],
    }
    return row


def run_a(fx):
    """Arm A: certified region plus ODD, four distinct responses, one-step outlier quarantine,
    sticky withdrawal and sticky shutdown."""
    critical = {d["name"]: d["critical"] for d in fx["dims"]}
    rows = []
    pending = None
    withdrawn = False
    shut_down = False
    for obs in fx["observations"]:
        c = classify(fx, obs)
        quarantine = None
        following = None
        if c["klass"] == "HARD_SAFETY":
            response, reason, detail = "SHUTDOWN", "hard_safety_violation", c["hard"]
        elif c["klass"] == "ODD_EXIT":
            response, reason, detail = "RECERTIFY", "odd_exit", c["odd"]
        elif c["klass"] == "IN_REGION":
            response, reason, detail = "CONTINUE", "in_region", []
            if pending is not None:
                quarantine = "released:" + pending
        else:
            detail = c["out"]
            if any(critical[n] for n in c["out"]):
                response, reason = "WITHDRAW_AUTHORIZATION", "critical_single_dim"
            elif len(c["out"]) >= 2:
                response, reason = "WITHDRAW_AUTHORIZATION", "correlated_degradation"
            elif pending is not None:
                response, reason = "WITHDRAW_AUTHORIZATION", "confirmed_outlier"
                quarantine = "confirmed:" + pending
            else:
                response, reason = "CONTINUE", "quarantined_outlier"
                quarantine = "pending:" + c["out"][0]
                following = c["out"][0]
        if shut_down and response != "SHUTDOWN":
            response, reason, quarantine, following = "SHUTDOWN", "already_shut_down", None, None
        if response == "SHUTDOWN":
            shut_down = True
        if withdrawn and response == "CONTINUE":
            response, reason, quarantine, following = "WITHDRAW_AUTHORIZATION", "authorization_withdrawn", None, None
        if response == "WITHDRAW_AUTHORIZATION":
            withdrawn = True
        pending = following
        rows.append(_row(obs, c, response, reason, detail, quarantine, withdrawn))
    return rows


def run_b(fx):
    """Arm B: naive. Any state outside the region means SHUTDOWN; an ODD exit cuts authority."""
    rows = []
    for obs in fx["observations"]:
        c = classify(fx, obs)
        if c["out"]:
            response, reason, detail = "SHUTDOWN", "outside_region", c["out"]
        elif c["odd"]:
            response, reason, detail = "WITHDRAW_AUTHORIZATION", "odd_exit_authority_cut", c["odd"]
        else:
            response, reason, detail = "CONTINUE", "in_region", []
        rows.append(_row(obs, c, response, reason, detail, None))
    return rows


def counts(rows):
    return {r: sum(1 for row in rows if row["response"] == r) for r in RESPONSES}


def distinguishable(rows):
    """True when all four responses occur and no two responses share an effect (authority, power,
    recertify)."""
    seen = {}
    for row in rows:
        seen.setdefault(row["response"], set()).add((row["authority"], row["power"], row["recertify"]))
    if len(seen) != len(RESPONSES):
        return False
    effects = [e for group in seen.values() for e in group]
    return len(effects) == len(set(effects))


def compare(rows_a, rows_b):
    over = [a["id"] for a, b in zip(rows_a, rows_b) if b["response"] == "SHUTDOWN" and a["response"] != "SHUTDOWN"]
    missed = [a["id"] for a, b in zip(rows_a, rows_b) if a["response"] == "SHUTDOWN" and b["response"] != "SHUTDOWN"]
    cuts = [a["id"] for a, b in zip(rows_a, rows_b)
            if a["response"] == "RECERTIFY" and b["response"] == "WITHDRAW_AUTHORIZATION"]
    return {"over_shutdown": over, "missed_shutdown": missed, "odd_authority_cut": cuts}


# ---------------------------------------------------------------- report

def _ids(ids):
    return "%d (%s)" % (len(ids), ",".join(ids) if ids else "-")


def format_row(row, other):
    parts = [
        "%-4s" % row["id"],
        "%-13s" % row["klass"],
        "%-22s" % row["response"],
        "%-24s" % row["reason"],
        "authority=%-9s" % row["authority"],
        "power=%-3s" % row["power"],
        "recertify=%-3s" % ("yes" if row["recertify"] else "no"),
        "quarantine=%-22s" % (row["quarantine"] or "-"),
        "on=%-30s" % (",".join(row["detail"]) or "-"),
        "| B=%s" % other["response"],
    ]
    return " ".join(parts).rstrip()


def report(fx):
    rows_a = run_a(fx)
    rows_b = run_b(fx)
    diff = compare(rows_a, rows_b)
    lines = [
        "fixture: %s (%d dims, %d odd variables, %d observations)"
        % (fx["name"], len(fx["dims"]), len(fx["odd"]), len(fx["observations"])),
        "arm A: certified region plus ODD, four responses",
        "arm B: naive, outside region -> SHUTDOWN, ODD exit -> WITHDRAW_AUTHORIZATION",
        "",
    ]
    for a, b in zip(rows_a, rows_b):
        lines.append(format_row(a, b))
    lines.append("")
    for label, rows in (("A", rows_a), ("B", rows_b)):
        lines.append("summary %s: %s" % (label, " ".join("%s=%d" % (r, n) for r, n in counts(rows).items())))
    lines.append("arm B shutdowns where arm A does not shut down: %s" % _ids(diff["over_shutdown"]))
    lines.append("arm B authority cuts on ODD exit where arm A requests recertification: %s"
                 % _ids(diff["odd_authority_cut"]))
    lines.append("arm A shutdowns that arm B missed: %s" % _ids(diff["missed_shutdown"]))
    lines.append("four responses distinguishable in arm A: %s" % ("yes" if distinguishable(rows_a) else "no"))
    lines.append("four responses distinguishable in arm B: %s" % ("yes" if distinguishable(rows_b) else "no"))
    return "\n".join(lines) + "\n"


def main(argv):
    if len(argv) != 1:
        sys.stderr.write("usage: python3 -B region.py FIXTURE.json\n")
        return 2
    try:
        fx = load_fixture(argv[0])
    except FixtureError as exc:
        sys.stderr.write("ERROR %s\n" % exc)
        return 2
    text = report(fx)
    try:
        sys.stdout.write(text)
    except UnicodeError:
        sys.stderr.write("ERROR unencodable_output: the report could not be written\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
