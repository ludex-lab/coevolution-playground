"""w28-audit-contract: an audit verdict is reported over the declared numerical execution contracts.

Method sketch of arXiv 2611.23657 (clean room, abstract page only; no code was copied). Stdlib only,
no network. The model is a fixed list of weights stored as text. Each contract computes the same
products and differs only in how the products are summed. A verdict is reported per contract and as a
range over all declared contracts, never as one pass.
"""

import fractions
import json
import math
import re
import sys

FIXTURE_VERSION = 1
CONTRACTS = ("ltr", "rtl", "lanes2", "fsum")
TESTS = ("dp_gap", "rate_ratio")
DECISIONS = ("STABLE_PASS", "STABLE_FAIL", "CONTRACT_DEPENDENT", "DENY")
ID_RE = re.compile(r"[A-Za-z0-9_]{1,40}")
TOKEN_RE = re.compile(r"-?[0-9]{1,30}(\.[0-9]{1,30})?([eE][+-]?[0-9]{1,3})?")
MAX_WEIGHTS = 16
MAX_TEXT = 400
MAX_ITEMS = 1000
Fraction = fractions.Fraction


class AuditError(Exception):
    """Malformed input: the CLI prints one ERROR line on stderr and exits 2."""

    def __init__(self, code, detail):
        Exception.__init__(self, "%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def _esc(value):
    return json.dumps(str(value), ensure_ascii=True)


# ---------------------------------------------------------------- strict loading

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise AuditError("duplicate_key", "key %s is repeated" % _esc(key))
        out[key] = value
    return out


def _constant(name):
    raise AuditError("bad_number", "%s is not a finite number" % _esc(name))


def parse(text):
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except AuditError:
        raise
    except (ValueError, RecursionError):
        raise AuditError("not_json", "input is not valid JSON")


def _obj(value, keys, where):
    if type(value) is not dict:
        raise AuditError("wrong_type", "%s must be an object" % where)
    missing = [k for k in keys if k not in value]
    if missing:
        raise AuditError("missing_key", "%s lacks %s" % (where, _esc(missing[0])))
    unknown = sorted(set(value) - set(keys))
    if unknown:
        raise AuditError("unknown_key", "%s has unknown key %s" % (where, _esc(unknown[0])))
    return value


def _list(value, where, minimum=1):
    if type(value) is not list or len(value) < minimum or len(value) > MAX_ITEMS:
        raise AuditError("wrong_type", "%s must be a list of %d to %d items" % (where, minimum, MAX_ITEMS))
    return value


def _id(value, where):
    if type(value) is not str or ID_RE.fullmatch(value) is None:
        raise AuditError("bad_id", "%s must match [A-Za-z0-9_]{1,40}" % where)
    return value


def _int(value, where):
    if type(value) is not int or not 0 <= value <= 10 ** 6:
        raise AuditError("wrong_type", "%s must be an integer from 0 to 1000000" % where)
    return value


def _number(value, where):
    if type(value) not in (int, float):
        raise AuditError("wrong_type", "%s must be a number" % where)
    try:
        f = float(value)
    except OverflowError:
        raise AuditError("bad_number", "%s is too large" % where)
    if not math.isfinite(f):
        raise AuditError("bad_number", "%s is not finite" % where)
    return f


def _unique(items, where):
    if len(set(items)) != len(items):
        raise AuditError("duplicate_name", "%s repeats a name" % where)


def _text(value, where):
    if type(value) is not str or len(value) > MAX_TEXT:
        raise AuditError("wrong_type", "%s must be text of at most %d characters" % (where, MAX_TEXT))
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise AuditError("bad_text", "%s holds a character that is not valid text" % where)
    return value


def _contract(value, where):
    if type(value) is not str or value not in CONTRACTS:
        raise AuditError("unknown_contract", "%s must be one of %s" % (where, ", ".join(CONTRACTS)))
    return value


def _test(value, where):
    spec = _obj(value, ("name", "bound"), where)
    if type(spec["name"]) is not str or spec["name"] not in TESTS:
        raise AuditError("unknown_test", "%s name must be one of %s" % (where, ", ".join(TESTS)))
    bound = _bound(spec["bound"], where + ".bound")
    return {"name": spec["name"], "bound": bound}


def _bound(value, where):
    _number(value, where)
    b = Fraction(value) if type(value) is int else Fraction(repr(value))
    if not 0 <= b <= 1:
        raise AuditError("bad_number", "%s must be between 0 and 1" % where)
    return b


def _tests(value, where):
    tests = [_test(t, "%s[%d]" % (where, i)) for i, t in enumerate(_list(value, where))]
    _unique([t["name"] for t in tests], where)
    return tests


def parse_weights(text):
    tokens = text.split(",")
    if not 1 <= len(tokens) <= MAX_WEIGHTS:
        raise AuditError("bad_weights", "weights_text must hold 1 to %d numbers" % MAX_WEIGHTS)
    out = []
    for token in tokens:
        if TOKEN_RE.fullmatch(token) is None:
            raise AuditError("bad_weights", "weights_text holds a token that is not a plain decimal number")
        f = float(token)
        if not math.isfinite(f):
            raise AuditError("bad_weights", "weights_text holds a number that is not finite")
        out.append(f)
    return out


def _declaration(value, where):
    keys = ("seq", "contracts", "groups", "threshold", "weights_text", "tests")
    d = _obj(value, keys, where)
    contracts = [_contract(c, where + ".contracts") for c in _list(d["contracts"], where + ".contracts")]
    _unique(contracts, where + ".contracts")
    if len(contracts) < 2:
        raise AuditError("too_few_contracts", "%s.contracts must declare at least two contracts" % where)
    groups = [_id(g, where + ".groups") for g in _list(d["groups"], where + ".groups", 2)]
    if len(groups) != 2:
        raise AuditError("bad_groups", "%s.groups must name exactly two groups" % where)
    _unique(groups, where + ".groups")
    weights_text = _text(d["weights_text"], where + ".weights_text")
    return {
        "seq": _int(d["seq"], where + ".seq"),
        "contracts": contracts,
        "groups": groups,
        "threshold": _number(d["threshold"], where + ".threshold"),
        "weights_text": weights_text,
        "weights": parse_weights(weights_text),
        "tests": _tests(d["tests"], where + ".tests"),
    }


def _scoring(value, where):
    keys = ("seq", "groups", "threshold", "tests", "runs")
    s = _obj(value, keys, where)
    groups = [_id(g, where + ".groups") for g in _list(s["groups"], where + ".groups", 1)]
    runs = []
    for i, r in enumerate(_list(s["runs"], where + ".runs")):
        run = _obj(r, ("contract", "weights_text"), "%s.runs[%d]" % (where, i))
        runs.append({"contract": _contract(run["contract"], "%s.runs[%d].contract" % (where, i)),
                     "weights_text": _text(run["weights_text"], "%s.runs[%d].weights_text" % (where, i))})
    _unique([r["contract"] for r in runs], where + ".runs")
    return {
        "seq": _int(s["seq"], where + ".seq"),
        "groups": groups,
        "threshold": _number(s["threshold"], where + ".threshold"),
        "tests": _tests(s["tests"], where + ".tests"),
        "runs": runs,
    }


def validate(root):
    root = _obj(root, ("fixture_version", "on_expiry", "audits"), "fixture")
    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:
        raise AuditError("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    if type(root["on_expiry"]) is not str or root["on_expiry"] != "DENY":
        raise AuditError("bad_on_expiry", "on_expiry must be DENY; silence is never approval")
    audits = []
    for i, a in enumerate(_list(root["audits"], "audits")):
        where = "audits[%d]" % i
        a = _obj(a, ("id", "declaration", "scoring", "records"), where)
        decl = None if a["declaration"] is None else _declaration(a["declaration"], where + ".declaration")
        records = []
        for j, r in enumerate(_list(a["records"], where + ".records")):
            rw = "%s.records[%d]" % (where, j)
            rec = _obj(r, ("id", "group", "x"), rw)
            x = [_number(v, rw + ".x") for v in _list(rec["x"], rw + ".x")]
            records.append({"id": _id(rec["id"], rw + ".id"), "group": _id(rec["group"], rw + ".group"), "x": x})
        _unique([r["id"] for r in records], where + ".records")
        if decl is not None:
            for r in records:
                if r["group"] not in decl["groups"]:
                    raise AuditError("unknown_group", "%s record %s is in a group that was not declared" % (where, r["id"]))
                if len(r["x"]) != len(decl["weights"]):
                    raise AuditError("bad_dimension", "%s record %s has %d features for %d weights"
                                     % (where, r["id"], len(r["x"]), len(decl["weights"])))
            for g in decl["groups"]:
                if not any(r["group"] == g for r in records):
                    raise AuditError("empty_group", "%s declared group %s has no record" % (where, g))
        audits.append({"id": _id(a["id"], where + ".id"), "declaration": decl,
                       "scoring": _scoring(a["scoring"], where + ".scoring"), "records": records})
    _unique([a["id"] for a in audits], "audits")
    return {"audits": audits}


def load_fixture(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except UnicodeDecodeError:
        raise AuditError("bad_encoding", "file is not valid UTF-8")
    except OSError:
        raise AuditError("unreadable", "file could not be read")
    return validate(parse(text))


# ---------------------------------------------------------------- numerical execution contracts

def dot(contract, weights, x):
    """Same products for every contract; only the order of the sum differs.

    The sums are explicit loops on purpose: the builtin sum() is a compensated sum on Python 3.12 and later,
    so it would not be a plain left-to-right contract.
    """
    products = [w * v for w, v in zip(weights, x)]
    if contract == "ltr":
        acc = 0.0
        for p in products:
            acc += p
        result = acc
    elif contract == "rtl":
        acc = 0.0
        for p in reversed(products):
            acc += p
        result = acc
    elif contract == "lanes2":
        even = 0.0
        odd = 0.0
        for i, p in enumerate(products):
            if i % 2 == 0:
                even += p
            else:
                odd += p
        result = even + odd
    elif contract == "fsum":
        try:
            result = math.fsum(products)
        except (OverflowError, ValueError):
            raise AuditError("non_finite_score", "a score is not finite under contract %s" % contract)
    else:
        raise AuditError("unknown_contract", "unknown contract %s" % _esc(contract))
    if not math.isfinite(result):
        raise AuditError("non_finite_score", "a score is not finite under contract %s" % contract)
    return result


# ---------------------------------------------------------------- the audit

def _deny(audit_id, code, detail):
    return {"audit": audit_id, "decision": "DENY", "code": code, "detail": detail}


def predeclaration_check(decl, scoring):
    """Return (code, detail) for the first broken pre-declaration, or None.

    Every comparison is plain equality on the declared values; weights_text is compared byte for byte.
    There is no hash, no signature and no timestamp: order is the integer seq in the fixture.
    """
    if decl is None:
        return ("no_declaration", "no audit was declared before scoring")
    if not decl["seq"] < scoring["seq"]:
        return ("declared_after_scoring", "the declaration (seq %d) does not come before scoring (seq %d)"
                % (decl["seq"], scoring["seq"]))
    ran = [r["contract"] for r in scoring["runs"]]
    for c in decl["contracts"]:
        if c not in ran:
            return ("contract_missing", "declared contract %s was not run" % c)
    for c in ran:
        if c not in decl["contracts"]:
            return ("contract_not_declared", "contract %s was run but not declared" % c)
    for r in scoring["runs"]:
        if r["weights_text"].encode("utf-8") != decl["weights_text"].encode("utf-8"):
            return ("weights_changed", "the weights text under contract %s differs byte for byte" % r["contract"])
    if scoring["threshold"] != decl["threshold"]:
        return ("threshold_changed", "the scoring threshold differs from the declared one")
    if scoring["groups"] != decl["groups"]:
        return ("groups_changed", "the scored groups differ from the declared groups")
    declared = dict((t["name"], t["bound"]) for t in decl["tests"])
    used = dict((t["name"], t["bound"]) for t in scoring["tests"])
    for name in used:
        if name not in declared:
            return ("post_hoc_test", "test %s was not declared before scoring" % name)
    for name in declared:
        if name not in used:
            return ("test_missing", "declared test %s was not scored" % name)
    for name in declared:
        if used[name] != declared[name]:
            return ("test_changed", "the bound of test %s differs from the declared bound" % name)
    return None


def _frac(f):
    return "%d/%d" % (f.numerator, f.denominator)


def _statistic(name, rate_a, rate_b):
    if name == "dp_gap":
        return abs(rate_a - rate_b)
    low, high = min(rate_a, rate_b), max(rate_a, rate_b)
    return Fraction(1) if high == 0 else low / high


def _passes(name, stat, bound):
    return stat <= bound if name == "dp_gap" else stat >= bound


def combine(outcomes):
    """One decision from the per-test outcomes: any test that depends on the contract decides first."""
    if "contract_dependent" in outcomes:
        return "CONTRACT_DEPENDENT"
    if "fail_all_contracts" in outcomes:
        return "STABLE_FAIL"
    return "STABLE_PASS"


def run_audit(audit):
    decl, scoring, records = audit["declaration"], audit["scoring"], audit["records"]
    broken = predeclaration_check(decl, scoring)
    if broken is not None:
        return _deny(audit["id"], broken[0], broken[1])
    ga, gb = decl["groups"]
    size = {ga: sum(1 for r in records if r["group"] == ga), gb: sum(1 for r in records if r["group"] == gb)}
    per = {}
    selected = {}
    for c in decl["contracts"]:
        chosen = set(r["id"] for r in records if dot(c, decl["weights"], r["x"]) > decl["threshold"])
        selected[c] = chosen
        rate = {g: Fraction(sum(1 for r in records if r["group"] == g and r["id"] in chosen), size[g]) for g in (ga, gb)}
        per[c] = rate
    tests = []
    for t in decl["tests"]:
        cells = {}
        for c in decl["contracts"]:
            stat = _statistic(t["name"], per[c][ga], per[c][gb])
            cells[c] = {"statistic": _frac(stat), "pass": _passes(t["name"], stat, t["bound"]), "_stat": stat}
        flags = set(cell["pass"] for cell in cells.values())
        outcome = "pass_all_contracts" if flags == {True} else "fail_all_contracts" if flags == {False} else "contract_dependent"
        stats = [cell["_stat"] for cell in cells.values()]
        tests.append({
            "name": t["name"], "bound": _frac(t["bound"]), "outcome": outcome,
            "range": {"min": _frac(min(stats)), "max": _frac(max(stats))},
            "per_contract": {c: {"statistic": cells[c]["statistic"], "pass": cells[c]["pass"]} for c in decl["contracts"]},
        })
    decision = combine([t["outcome"] for t in tests])
    views = {c: "PASS" if all(t["per_contract"][c]["pass"] for t in tests) else "FAIL" for c in decl["contracts"]}
    union = set().union(*selected.values())
    common = set.intersection(*selected.values())
    differing = [r["id"] for r in records if r["id"] in union and r["id"] not in common]
    return {
        "audit": audit["id"], "decision": decision, "code": None,
        "contracts": list(decl["contracts"]), "weights_text": decl["weights_text"], "weights_identical": True,
        "single_contract_views": views, "tests": tests, "differing_records": differing,
        "sampling_uncertainty": "not_computed",
    }


def run(fx):
    rows = [run_audit(a) for a in fx["audits"]]
    totals = {d: sum(1 for r in rows if r["decision"] == d) for d in DECISIONS}
    return {"rows": rows, "totals": totals}


def report(fx):
    return json.dumps(run(fx), indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("ERROR usage: audit_contract.py FIXTURE.json\n")
        return 2
    try:
        fx = load_fixture(argv[1])
        result = run(fx)
    except AuditError as e:
        sys.stderr.write("ERROR %s: %s\n" % (e.code, e.detail))
        return 2
    sys.stdout.write(json.dumps(result, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
    return 2 if any(r["decision"] == "DENY" for r in result["rows"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
