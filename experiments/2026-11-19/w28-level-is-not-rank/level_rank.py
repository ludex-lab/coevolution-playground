"""w28-level-is-not-rank: handing a conformal level to a quantile function is not the required rank.

Method sketch of arXiv 2611.23329 (clean room, abstract page only; no code from the paper's archive was
read or copied). Stdlib only, no network. All rank and position arithmetic is exact (fractions.Fraction):
the level arrives as a decimal string and is never a float.

Conventions, pinned here and repeated in the README and in the tests:
  * alpha is the miscoverage the interval end must carry; the level is 1 - alpha.
  * required rank (1-based, of n scores): r = ceil((n + 1) * (1 - alpha)); the guarantee is r / (n + 1).
  * a rank is reachable only if r <= n, which is the same as n >= 1/alpha - 1 (the feasibility floor).
  * a helper is handed a quantile level q. Convention "one_sided": q = 1 - alpha.
    Convention "two_sided_upper": q = 1 - alpha / 2 (the upper end of a two-sided interval).
  * positions are 0-based, as in numpy's default linear method: position = (n - 1) * q. The required
    0-based index is r - 1. A helper reaches the rank only when its position equals r - 1 exactly.
"""

import fractions
import json
import math
import re
import sys

FIXTURE_VERSION = 1
HELPERS = ("linear", "weibull", "higher", "conformal_rank")
CONVENTIONS = ("one_sided", "two_sided_upper")
Q_RULES = {"one_sided": "q = 1 - alpha", "two_sided_upper": "q = 1 - alpha/2"}
RANK_RULE = "r = ceil((n + 1) * (1 - alpha)), guarantee r / (n + 1)"
FLOOR_RULE = "r <= n, the same as n >= 1/alpha - 1"
DECISIONS = ("REACHES_RANK", "WRONG_RANK", "REFUSED_BELOW_FLOOR", "DENY")
ID_RE = re.compile(r"[A-Za-z0-9_]{1,40}")
ALPHA_RE = re.compile(r"0\.[0-9]{1,6}")
MAX_SCORES = 5000
MAX_SCORE = 10 ** 9
MAX_CASES = 1000
Fraction = fractions.Fraction


class RankError(Exception):
    """Malformed input: the CLI prints one ERROR line on stderr and exits 2."""

    def __init__(self, code, detail):
        Exception.__init__(self, "%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def _esc(value):
    return json.dumps(str(value), ensure_ascii=True)


# ---------------------------------------------------------------- exact arithmetic

def parse_alpha(text, where="alpha"):
    """alpha as a decimal string strictly between 0 and 1, read exactly. A float is refused."""
    if type(text) is not str or ALPHA_RE.fullmatch(text) is None:
        raise RankError("bad_alpha", "%s must be a decimal string such as \"0.10\"" % where)
    alpha = Fraction(text)
    if alpha == 0:  # the pattern already excludes 1 and above
        raise RankError("bad_alpha", "%s must be greater than 0" % where)
    return alpha


def required_rank(n, alpha):
    """r = ceil((n + 1) * (1 - alpha)), exact. alpha is a decimal string or a Fraction, never a float."""
    if type(n) is not int or n < 1:
        raise RankError("bad_n", "n must be an integer of at least 1")
    a = alpha if isinstance(alpha, Fraction) else parse_alpha(alpha)
    return math.ceil((n + 1) * (1 - a))


def feasible(n, alpha):
    a = alpha if isinstance(alpha, Fraction) else parse_alpha(alpha)
    return required_rank(n, a) <= n


def q_level(convention, alpha):
    if convention == "one_sided":
        return 1 - alpha
    if convention == "two_sided_upper":
        return 1 - alpha / 2
    raise RankError("unknown_convention", "convention must be one of %s" % ", ".join(CONVENTIONS))


def helper_position(helper, n, q):
    """0-based position a level-to-index helper lands on, clamped to [0, n - 1]."""
    if helper == "linear":
        pos = (n - 1) * q
    elif helper == "weibull":
        pos = (n + 1) * q - 1
    elif helper == "higher":
        pos = Fraction(math.ceil((n - 1) * q))
    else:
        raise RankError("unknown_helper", "helper must be one of %s" % ", ".join(HELPERS))
    return min(max(pos, Fraction(0)), Fraction(n - 1))


def value_at(sorted_scores, pos):
    """Score at a 0-based fractional position by linear interpolation, exact."""
    lo = math.floor(pos)
    hi = min(lo + 1, len(sorted_scores) - 1)
    return sorted_scores[lo] + (pos - lo) * (sorted_scores[hi] - sorted_scores[lo])


def num(f):
    """An exact decimal string when the expansion ends, otherwise a fraction."""
    f = Fraction(f)
    d = f.denominator
    for p in (2, 5):
        while d % p == 0:
            d //= p
    if d != 1:
        return "%d/%d" % (f.numerator, f.denominator)
    if f.denominator == 1:
        return str(f.numerator)
    scale = 1
    while (f * scale).denominator != 1:
        scale *= 10
    digits = len(str(scale)) - 1
    whole = f * scale
    sign = "-" if whole < 0 else ""
    text = str(abs(whole.numerator)).rjust(digits + 1, "0")
    return "%s%s.%s" % (sign, text[:-digits], text[-digits:])


# ---------------------------------------------------------------- strict loading

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise RankError("duplicate_key", "key %s is repeated" % _esc(key))
        out[key] = value
    return out


def _constant(name):
    raise RankError("bad_number", "%s is not a finite number" % _esc(name))


def parse(text):
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except RankError:
        raise
    except (ValueError, RecursionError):
        raise RankError("not_json", "input is not valid JSON")


def _obj(value, keys, where):
    if type(value) is not dict:
        raise RankError("wrong_type", "%s must be an object" % where)
    missing = [k for k in keys if k not in value]
    if missing:
        raise RankError("missing_key", "%s lacks %s" % (where, _esc(missing[0])))
    unknown = sorted(set(value) - set(keys))
    if unknown:
        raise RankError("unknown_key", "%s has unknown key %s" % (where, _esc(unknown[0])))
    return value


def _id(value, where):
    if type(value) is not str or ID_RE.fullmatch(value) is None:
        raise RankError("bad_id", "%s must match [A-Za-z0-9_]{1,40}" % where)
    return value


def _choice(value, options, code, where):
    if type(value) is not str or value not in options:
        raise RankError(code, "%s must be one of %s" % (where, ", ".join(options)))
    return value


def _scores(value, where):
    if type(value) is not list or not 1 <= len(value) <= MAX_SCORES:
        raise RankError("bad_scores", "%s must be a list of 1 to %d integers" % (where, MAX_SCORES))
    for v in value:
        if type(v) is not int or not -MAX_SCORE <= v <= MAX_SCORE:
            raise RankError("bad_scores", "%s must hold integers between -%d and %d" % (where, MAX_SCORE, MAX_SCORE))
    return list(value)


def validate(root):
    root = _obj(root, ("fixture_version", "on_expiry", "cases"), "fixture")
    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:
        raise RankError("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    if type(root["on_expiry"]) is not str or root["on_expiry"] != "DENY":
        raise RankError("bad_on_expiry", "on_expiry must be DENY; silence is never approval")
    if type(root["cases"]) is not list or not 1 <= len(root["cases"]) <= MAX_CASES:
        raise RankError("wrong_type", "cases must be a list of 1 to %d items" % MAX_CASES)
    cases = []
    for i, c in enumerate(root["cases"]):
        where = "cases[%d]" % i
        c = _obj(c, ("id", "helper", "convention", "declared_n", "declared_alpha", "alpha", "scores"), where)
        if type(c["declared_n"]) is not int or not 1 <= c["declared_n"] <= MAX_SCORES:
            raise RankError("bad_n", "%s.declared_n must be an integer from 1 to %d" % (where, MAX_SCORES))
        cases.append({
            "id": _id(c["id"], where + ".id"),
            "helper": _choice(c["helper"], HELPERS, "unknown_helper", where + ".helper"),
            "convention": _choice(c["convention"], CONVENTIONS, "unknown_convention", where + ".convention"),
            "declared_n": c["declared_n"],
            "declared_alpha": parse_alpha(c["declared_alpha"], where + ".declared_alpha"),
            "alpha": None if c["alpha"] is None else parse_alpha(c["alpha"], where + ".alpha"),
            "scores": None if c["scores"] is None else _scores(c["scores"], where + ".scores"),
        })
    ids = [c["id"] for c in cases]
    if len(set(ids)) != len(ids):
        raise RankError("duplicate_name", "cases repeats an id")
    return {"cases": cases}


def load_fixture(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except UnicodeDecodeError:
        raise RankError("bad_encoding", "file is not valid UTF-8")
    except OSError:
        raise RankError("unreadable", "file could not be read")
    return validate(parse(text))


# ---------------------------------------------------------------- classification

def _deny(case, code, detail):
    return {"case": case["id"], "decision": "DENY", "code": code, "detail": detail}


def classify(case):
    if case["scores"] is None:
        return _deny(case, "missing_scores", "no score bag was given")
    if case["alpha"] is None:
        return _deny(case, "missing_level", "no level was given")
    n = len(case["scores"])
    if n != case["declared_n"]:
        return _deny(case, "n_changed", "the score bag holds %d scores, not the declared %d" % (n, case["declared_n"]))
    if case["alpha"] != case["declared_alpha"]:
        return _deny(case, "level_changed", "alpha differs from the declared alpha")
    alpha = case["alpha"]
    r = required_rank(n, alpha)
    ok = r <= n
    row = {
        "case": case["id"], "helper": case["helper"], "convention": case["convention"],
        "n": n, "alpha": num(alpha), "q": num(q_level(case["convention"], alpha)),
        "required_rank": r, "required_index": r - 1, "feasible": ok,
        "guarantee_at_required_rank": "%d/%d" % (r, n + 1) if ok else None,
        "feasibility_floor_n": max(1, math.ceil(1 / alpha - 1)),
        "code": None,
    }
    ordered = sorted(case["scores"])
    if case["helper"] == "conformal_rank":
        if not ok:
            row.update(decision="REFUSED_BELOW_FLOOR", position=None, position_one_based=None, value_at_position=None,
                       value_at_required_rank=None, direction=None)
            return row
        row.update(decision="REACHES_RANK", position=num(Fraction(r - 1)), position_one_based=num(Fraction(r)),
                   value_at_position=num(ordered[r - 1]), value_at_required_rank=num(ordered[r - 1]), direction=None)
        return row
    pos = helper_position(case["helper"], n, q_level(case["convention"], alpha))
    if not ok:
        return _deny(case, "finite_end_below_floor",
                     "helper %s returned a finite end at position %s although no rank reaches the level (r=%d > n=%d)"
                     % (case["helper"], num(pos), r, n))
    row.update(position=num(pos), position_one_based=num(pos + 1), value_at_position=num(value_at(ordered, pos)),
               value_at_required_rank=num(ordered[r - 1]))
    if pos == r - 1:
        row.update(decision="REACHES_RANK", direction=None)
    else:
        row.update(decision="WRONG_RANK", direction="below" if pos < r - 1 else "above")
    return row


def run(fx):
    rows = [classify(c) for c in fx["cases"]]
    totals = {d: sum(1 for r in rows if r["decision"] == d) for d in DECISIONS}
    return {"rows": rows, "totals": totals}


def report(fx):
    return json.dumps(run(fx), indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("ERROR usage: level_rank.py FIXTURE.json\n")
        return 2
    try:
        result = run(load_fixture(argv[1]))
    except RankError as e:
        sys.stderr.write("ERROR %s: %s\n" % (e.code, e.detail))
        return 2
    sys.stdout.write(json.dumps(result, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
    return 2 if any(r["decision"] == "DENY" for r in result["rows"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
