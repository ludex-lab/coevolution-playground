"""w31-prerelease-is-not-stable: a pre-release is not the associated normal version.

Clean-room method sketch of the precedence rules in Semantic Versioning 2.0.0 (https://semver.org/spec/v2.0.0.html,
CC BY 3.0). No code was copied. Stdlib only, file-in/file-out, deterministic.

SemVer 2.0.0 defines precedence only; it has no range operators. This tool declares two operators, '>=' and '==',
evaluated by spec section 11 precedence, plus one POLICY that is not a SemVer rule: a stable range also rejects every
candidate that has pre-release identifiers, whatever its core. It is not an npm or PEP 440 solver.

Arms reported side by side:
- stable       : the declared gate (precedence plus the stable-range policy).
- precedence   : pure section 11 precedence; shown for contrast and never called stable.
- weak         : strip the pre-release and build suffix, then compare cores; the planted wrong arm.

Malformed or missing input is on_expiry DENY: exit 2, empty stdout, one ERROR line on stderr, no range verdict.
"""

import functools
import json
import sys
import unicodedata

FIXTURE_VERSION = 1
ON_EXPIRY = "DENY"
CAPS = {
    "file_bytes": {"limit": 65536, "on_expiry": "DENY"},
    "pairs": {"limit": 200, "on_expiry": "DENY"},
    "version_chars": {"limit": 128, "on_expiry": "DENY"},
    "text_chars": {"limit": 200, "on_expiry": "DENY"},
}
OPERATORS = (">=", "==")
VERDICTS = ("SATISFIES", "DOES_NOT_SATISFY")
DIGITS = "0123456789"
IDENT_CHARS = set(DIGITS + "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-")
BAD_CATEGORIES = {"Cc", "Cf", "Co", "Cn", "Cs", "Zl", "Zp", "Zs"}


class GateError(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- versions

def _numeric(text, where):
    if text == "" or any(ch not in DIGITS for ch in text):
        raise GateError("bad_core", "%s must be three dot-separated non-negative integers" % where)
    if len(text) > 1 and text[0] == "0":
        raise GateError("leading_zero", "%s has a leading zero" % where)
    return int(text)


def _identifiers(text, where, build):
    out = []
    for ident in text.split("."):
        if ident == "":
            raise GateError("empty_identifier", "%s has an empty identifier" % where)
        if any(ch not in IDENT_CHARS for ch in ident):
            raise GateError("bad_identifier", "%s identifiers use only ASCII letters, digits and hyphens" % where)
        if build:
            out.append(ident)
        elif all(ch in DIGITS for ch in ident):
            if len(ident) > 1 and ident[0] == "0":
                raise GateError("leading_zero", "%s has a numeric identifier with a leading zero" % where)
            out.append(int(ident))
        else:
            out.append(ident)
    return tuple(out)


def parse_version(text, where="version"):
    """MAJOR.MINOR.PATCH, optional -pre.release identifiers, optional +build metadata."""
    if type(text) is not str:
        raise GateError("wrong_type", "%s must be text" % where)
    if len(text) > CAPS["version_chars"]["limit"]:
        raise GateError("too_long", "%s exceeds %d characters" % (where, CAPS["version_chars"]["limit"]))
    build = ()
    if "+" in text:
        text, rest = text.split("+", 1)
        build = _identifiers(rest, where + " build metadata", True)
    pre = ()
    if "-" in text:
        text, rest = text.split("-", 1)
        pre = _identifiers(rest, where + " pre-release", False)
    parts = text.split(".")
    if len(parts) != 3:
        raise GateError("bad_core", "%s must be three dot-separated non-negative integers" % where)
    major, minor, patch = (_numeric(p, where) for p in parts)
    return {"major": major, "minor": minor, "patch": patch, "pre": pre, "build": build}


def render_version(v):
    out = "%d.%d.%d" % (v["major"], v["minor"], v["patch"])
    if v["pre"]:
        out += "-" + ".".join(str(i) for i in v["pre"])
    if v["build"]:
        out += "+" + ".".join(v["build"])
    return out


def compare_pre(a, b):
    """Section 11 order of two non-empty pre-release identifier tuples: -1, 0 or 1."""
    for x, y in zip(a, b):
        if x == y:
            continue
        xn, yn = type(x) is int, type(y) is int
        if xn and yn:
            return -1 if x < y else 1
        if xn != yn:
            return -1 if xn else 1
        return -1 if x < y else 1
    return (len(a) > len(b)) - (len(a) < len(b))


def compare(a, b):
    """Section 11 precedence: -1, 0 or 1. Build metadata is never read."""
    ca = (a["major"], a["minor"], a["patch"])
    cb = (b["major"], b["minor"], b["patch"])
    if ca != cb:
        return -1 if ca < cb else 1
    if not a["pre"] and not b["pre"]:
        return 0
    if not a["pre"]:
        return 1
    if not b["pre"]:
        return -1
    return compare_pre(a["pre"], b["pre"])


def sort_versions(versions):
    return sorted(versions, key=functools.cmp_to_key(compare))


# ---------------------------------------------------------------- requirements and the three arms

def parse_requirement(text, where="requirement"):
    """Exactly '<op> <version>' with op in OPERATORS; the version must be a normal version (no suffix)."""
    if type(text) is not str:
        raise GateError("wrong_type", "%s must be text" % where)
    op, sep, rest = text.partition(" ")
    if sep != " " or op not in OPERATORS:
        raise GateError("bad_requirement", "%s must be '>= X.Y.Z' or '== X.Y.Z'" % where)
    version = parse_version(rest, where + " version")
    if version["pre"] or version["build"]:
        raise GateError("bad_requirement", "%s must name a normal version without a suffix" % where)
    return {"op": op, "version": version}


def _holds(op, order):
    return order >= 0 if op == ">=" else order == 0


def precedence_arm(cand, req):
    ok = _holds(req["op"], compare(cand, req["version"]))
    return {"verdict": VERDICTS[0] if ok else VERDICTS[1], "reason": "by precedence (spec §11)"}


def stable_arm(cand, req):
    """The declared gate: section 11 precedence, then the stable-range policy."""
    target = render_version(req["version"])
    if not _holds(req["op"], compare(cand, req["version"])):
        same_core = (cand["major"], cand["minor"], cand["patch"]) == \
            (req["version"]["major"], req["version"]["minor"], req["version"]["patch"])
        if cand["pre"] and same_core:
            reason = "pre-release < %s (spec §11)" % target
        elif req["op"] == ">=":
            reason = "below %s (spec §11)" % target
        else:
            reason = "precedence differs from %s (spec §11)" % target
        return {"verdict": VERDICTS[1], "reason": reason}
    if cand["pre"]:
        return {"verdict": VERDICTS[1], "reason": "pre-release excluded by stable range (policy)"}
    return {"verdict": VERDICTS[0], "reason": "equal precedence (spec §11)" if req["op"] == "==" else
            "precedence holds (spec §11)"}


def weak_arm(cand, req):
    """The planted wrong arm: drop every suffix, then compare cores."""
    core = dict(cand, pre=(), build=())
    ok = _holds(req["op"], compare(core, req["version"]))
    return {"verdict": VERDICTS[0] if ok else VERDICTS[1], "reason": "suffix stripped"}


# ---------------------------------------------------------------- strict fixture loading

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise GateError("duplicate_key", "a JSON key is repeated")
        out[key] = value
    return out


def _constant(name):
    raise GateError("bad_number", "%s is not a finite number" % name)


def _no_float(text):
    raise GateError("wrong_type", "fractional numbers are not used in this fixture")


def _obj(value, keys, where):
    if type(value) is not dict:
        raise GateError("wrong_type", "%s must be an object" % where)
    missing = [k for k in keys if k not in value]
    if missing:
        raise GateError("missing_key", "%s lacks %s" % (where, missing[0]))
    if set(value) - set(keys):
        raise GateError("unknown_key", "%s has an unknown key" % where)
    return value


def _text(value, where):
    limit = CAPS["text_chars"]["limit"]
    if type(value) is not str or not 1 <= len(value) <= limit:
        raise GateError("wrong_type", "%s must be text of 1 to %d characters" % (where, limit))
    for ch in value:
        if ch != " " and unicodedata.category(ch) in BAD_CATEGORIES:
            raise GateError("bad_text", "%s holds a control, invisible or unassigned character" % where)
    if value != value.strip(" "):
        raise GateError("bad_text", "%s has a leading or trailing space" % where)
    return unicodedata.normalize("NFC", value)


def validate(root):
    _obj(root, ("fixture_version", "label", "pairs"), "fixture")
    if type(root["fixture_version"]) is not int:
        raise GateError("wrong_type", "fixture_version must be an integer")
    if root["fixture_version"] != FIXTURE_VERSION:
        raise GateError("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    label = _text(root["label"], "label")
    pairs = root["pairs"]
    if type(pairs) is not list or not 1 <= len(pairs) <= CAPS["pairs"]["limit"]:
        raise GateError("too_many", "pairs must hold 1 to %d entries (on_expiry DENY)" % CAPS["pairs"]["limit"])
    out, seen = [], set()
    for n, p in enumerate(pairs, 1):
        where = "pair %d" % n
        _obj(p, ("id", "candidate", "requirement", "expected"), where)
        pid = _text(p["id"], where + " id")
        if pid in seen:
            raise GateError("duplicate_id", "%s repeats an id (compared after NFC)" % where)
        seen.add(pid)
        if type(p["expected"]) is not str or p["expected"] not in VERDICTS:
            raise GateError("bad_expected", "%s expected must be SATISFIES or DOES_NOT_SATISFY" % where)
        out.append({"id": pid, "candidate_text": p["candidate"],
                    "candidate": parse_version(p["candidate"], where + " candidate"),
                    "requirement_text": p["requirement"],
                    "requirement": parse_requirement(p["requirement"], where + " requirement"),
                    "expected": p["expected"]})
    return {"label": label, "pairs": out}


def load_fixture(path):
    limit = CAPS["file_bytes"]["limit"]
    try:
        with open(path, "rb") as fh:
            data = fh.read(limit + 1)
    except OSError:
        raise GateError("unreadable", "fixture is missing or cannot be read")
    if len(data) > limit:
        raise GateError("too_large", "fixture is larger than %d bytes (on_expiry DENY)" % limit)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise GateError("bad_encoding", "fixture is not valid UTF-8")
    try:
        root = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_no_float)
    except GateError:
        raise
    except (ValueError, RecursionError):
        raise GateError("not_json", "fixture is not valid JSON")
    return validate(root)


# ---------------------------------------------------------------- run and report

def run(fx):
    rows = []
    for p in fx["pairs"]:
        cand, req = p["candidate"], p["requirement"]
        rows.append({"id": p["id"], "candidate": p["candidate_text"], "requirement": p["requirement_text"],
                     "expected": p["expected"], "stable": stable_arm(cand, req),
                     "precedence": precedence_arm(cand, req), "weak": weak_arm(cand, req)})
    closed = sum(1 for r in rows if r["stable"]["verdict"] == r["expected"])
    weak_wrong = sum(1 for r in rows if r["weak"]["verdict"] != r["expected"])
    return {"label": fx["label"], "rows": rows, "closed": closed, "total": len(rows), "weak_wrong": weak_wrong,
            "weak_gate": "FAIL" if weak_wrong else "PASS", "on_expiry": ON_EXPIRY,
            "range_semantics": "'>=' and '==' by spec section 11 precedence; a stable range also rejects every "
                               "pre-release candidate (policy, not a SemVer rule)"}


def report(result):
    width = max(len(r["candidate"]) for r in result["rows"])
    out = ["# Pre-release is not the associated normal version", "", "fixture: %s" % result["label"]]
    groups = []
    for r in result["rows"]:
        if r["requirement"] not in groups:
            groups.append(r["requirement"])
    for req in groups:
        out += ["", "requirement: %s" % req]
        for r in result["rows"]:
            if r["requirement"] == req:
                s = r["stable"]
                line = "- %s  %s" % (r["candidate"].ljust(width), s["verdict"])
                if s["verdict"] == VERDICTS[1]:
                    line += "  (%s)" % s["reason"]
                if s["verdict"] != r["expected"]:
                    line += "  [expected %s]" % r["expected"]
                out.append(line)
    out += ["", "precedence_arm (pure spec §11 precedence; shown, never called stable):"]
    diff = [r for r in result["rows"] if r["precedence"]["verdict"] != r["stable"]["verdict"]]
    out += ["- %s  %s %s  by precedence" % (r["candidate"].ljust(width), r["requirement"], r["precedence"]["verdict"])
            for r in diff] or ["- (agrees with the stable arm on every pair)"]
    out += ["", "weak_arm (strip suffix, then compare):"]
    wrong = [r for r in result["rows"] if r["weak"]["verdict"] != r["expected"]]
    out += ["- %s  %s wrongly %s  — gate FAIL" % (r["candidate"].ljust(width), r["requirement"], r["weak"]["verdict"])
            for r in wrong] or ["- (no wrong verdict on this fixture)"]
    out += ["", "closed: %d / %d on the declared comparator" % (result["closed"], result["total"])]
    return "\n".join(out) + "\n"


def main(argv):
    args = argv[1:]
    as_json = args[:1] == ["--json"]
    if as_json:
        args = args[1:]
    if len(args) != 1:
        sys.stderr.write("ERROR usage: prerelease_gate.py [--json] FIXTURE.json (on_expiry=DENY)\n")
        return 2
    try:
        result = run(load_fixture(args[0]))
    except GateError as e:
        sys.stderr.write("ERROR %s: %s (on_expiry=DENY)\n" % (e.code, e.detail))
        return 2
    if as_json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    else:
        sys.stdout.write(report(result))
    return 0 if result["closed"] == result["total"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
