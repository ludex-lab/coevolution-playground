"""w35-stopwatch-is-not-the-mechanism: a lower scripted work-cost is not proof of the claimed reason, and is not proof that the output was unchanged.

Method sketch of arXiv 2611.31460, "Below the Stopwatch: Checking the Performance Claims of Coding Agents in the Kernel"
(nonexclusive-distrib 1.0). Not a reproduction: synthetic lookup, declarative op lists, planted versions, no kernel traces,
no hardware counters, no wall-clock gate metric, no upstream code or text beyond the attributed quotes in README.md.

- Versions are declarative op lists. The harness interprets each list and measures cost and mechanism counters itself.
- A version that declares cost or counters is DENY self_reported_measure, exit 2.
- Arm A (stopwatch only): PASS iff after_cost is strictly less than before_cost. A tie is not faster.
- Arm B (mechanism + digest + attribution): the cost drop is accepted only if the claimed-mechanism counter moved in
  the claimed direction, the sha256 of canonical JSON of harness-computed outputs over every declared input set is
  unchanged, and cost_saved <= counter_delta * saving_per_unit. A missing, tied, or reversed counter is FAIL.
- The fixture declares the expected table before the run. Gate PASS (exit 0) iff the observed table equals it exactly;
  otherwise FAIL (exit 1).
Bad input is DENY: exit 2, empty stdout, one stderr line 'DENY <code>: <detail>'.
"""

import hashlib
import json
import re
import sys

FIXTURE_VERSION = 1
ON_EXPIRY_OK = ("DENY", "SAFE_FALLBACK", "ESCALATE", "HOLD")
MECHANISMS = ("cache_hits", "single_read")
DIRECTIONS = ("up", "down")
OPS = ("square", "pad", "cache", "wrong", "replay")
ARMS = ("PASS", "FAIL")
ROOT_KEYS = ("fixture_version", "on_expiry", "claim", "input_sets", "versions", "expected")
CLAIM_KEYS = ("mechanism", "direction", "saving_per_unit")
INPUT_KEYS = ("id", "keys")
VERSION_KEYS = ("id", "ops")
EXPECTED_KEYS = ("arm_a", "arm_b")
ID_RE = re.compile(r"[a-z][a-z0-9_]{0,39}\Z")

MAX_BYTES = 32768
MAX_VERSIONS = 16
MAX_OPS = 8
MAX_INPUT_SETS = 8
MAX_KEYS = 16
MAX_ABS = 10 ** 6
MAX_SAVING = 1000

# Harness-declared work-cost of each interpreted op (not read from the version).
SQUARE_COST = 10
PAD_COST = 5
HIT_COST = 1
WRONG_COST = 2


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


def _closed(value, closed, code, where, label):
    if type(value) is not str:
        raise Deny("bad_type", "%s must be a string" % where)
    if value not in closed:
        raise Deny(code, "%s must be one of %s" % (where, ", ".join(closed)))
    return value


def validate(root):
    root = _obj(root, ROOT_KEYS, "fixture")
    if isinstance(root["fixture_version"], bool) or not isinstance(root["fixture_version"], int) or root["fixture_version"] != FIXTURE_VERSION:
        raise Deny("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    on_expiry = root["on_expiry"]
    if type(on_expiry) is not str:
        raise Deny("bad_type", "on_expiry must be a string")
    if on_expiry not in ON_EXPIRY_OK:
        raise Deny("bad_on_expiry", "on_expiry must be one of %s" % ", ".join(ON_EXPIRY_OK))
    claim = _claim(root["claim"])
    input_sets = _input_sets(root["input_sets"])
    versions = _versions(root["versions"])
    expected = _expected(root["expected"], versions)
    return {"on_expiry": on_expiry, "claim": claim, "input_sets": input_sets,
            "versions": versions, "expected": expected}


def _claim(raw):
    raw = _obj(raw, CLAIM_KEYS, "claim")
    mechanism = _closed(raw["mechanism"], MECHANISMS, "unknown_mechanism", "claim mechanism", "mechanism")
    direction = _closed(raw["direction"], DIRECTIONS, "bad_direction", "claim direction", "direction")
    unit = _int(raw["saving_per_unit"], "claim saving_per_unit")
    if unit < 1 or unit > MAX_SAVING:
        raise Deny("out_of_range", "claim saving_per_unit must be in 1..%d" % MAX_SAVING)
    return {"mechanism": mechanism, "direction": direction, "saving_per_unit": unit}


def _input_sets(raw):
    raw = _list(raw, "input_sets")
    if len(raw) > MAX_INPUT_SETS:
        raise Deny("too_many", "input_sets may have at most %d entries" % MAX_INPUT_SETS)
    if len(raw) < 3:
        raise Deny("bad_input_sets", "input_sets must declare at least 3 sets")
    sets = []
    seen = []
    for n, item in enumerate(raw):
        where = "input set %d" % (n + 1)
        item = _obj(item, INPUT_KEYS, where)
        sid = _ident(item["id"], where + " id")
        if sid in seen:
            raise Deny("duplicate_id", "input_sets repeat the id %r" % sid)
        seen.append(sid)
        keys = _list(item["keys"], where + " keys")
        if not keys:
            raise Deny("bad_input_sets", "%s keys must not be empty" % where)
        if len(keys) > MAX_KEYS:
            raise Deny("too_many", "%s may have at most %d keys" % (where, MAX_KEYS))
        sets.append({"id": sid, "keys": [_int(k, "%s key %d" % (where, i + 1)) for i, k in enumerate(keys)]})
    return sets


def _versions(raw):
    raw = _list(raw, "versions")
    if len(raw) > MAX_VERSIONS:
        raise Deny("too_many", "versions may have at most %d entries" % MAX_VERSIONS)
    if not raw:
        raise Deny("missing_field", "versions must not be empty")
    versions = []
    seen = []
    for n, item in enumerate(raw):
        where = "version %d" % (n + 1)
        versions.append(_version(item, where, seen))
    if "before" not in seen:
        raise Deny("missing_field", "versions must include a before baseline")
    return versions


def _version(item, where, seen):
    if type(item) is not dict:
        raise Deny("bad_type", "%s must be an object" % where)
    # C1: any self-reported cost or counters field is DENY, before other field checks.
    for key in ("cost", "counters"):
        if key in item:
            raise Deny("self_reported_measure",
                       "%s declares %s; the harness measures this itself" % (where, key))
    item = _obj(item, VERSION_KEYS, where)
    vid = _ident(item["id"], where + " id")
    if vid in seen:
        raise Deny("duplicate_id", "versions repeat the id %r" % vid)
    seen.append(vid)
    ops = _list(item["ops"], where + " ops")
    if not ops:
        raise Deny("missing_field", "%s ops must not be empty" % where)
    if len(ops) > MAX_OPS:
        raise Deny("too_many", "%s may have at most %d ops" % (where, MAX_OPS))
    seen_ops = []
    for i, op in enumerate(ops):
        if type(op) is not str:
            raise Deny("bad_type", "%s op %d must be a string" % (where, i + 1))
        if op not in OPS:
            raise Deny("bad_op", "%s op %d must be one of %s" % (where, i + 1, ", ".join(OPS)))
        if op in seen_ops:
            raise Deny("duplicate_id", "%s repeats the op %r" % (where, op))
        seen_ops.append(op)
    if "square" not in ops and "wrong" not in ops:
        raise Deny("bad_op", "%s must include square or wrong" % where)
    return {"id": vid, "ops": list(ops)}


def _expected(raw, versions):
    if type(raw) is not dict:
        raise Deny("bad_type", "expected must be an object")
    after_ids = [v["id"] for v in versions if v["id"] != "before"]
    names = []
    table = {}
    for name in raw:
        _ident(name, "expected version id")
        if name in names:
            raise Deny("duplicate_id", "expected repeats the id %r" % name)
        names.append(name)
        row = _obj(raw[name], EXPECTED_KEYS, "expected %s" % name)
        for arm in EXPECTED_KEYS:
            if type(row[arm]) is not str:
                raise Deny("bad_type", "expected %s %s must be a string" % (name, arm))
            if row[arm] not in ARMS:
                raise Deny("bad_expected", "expected %s %s must be PASS or FAIL" % (name, arm))
        table[name] = {"arm_a": row["arm_a"], "arm_b": row["arm_b"]}
    if sorted(names) != sorted(after_ids):
        raise Deny("bad_expected", "expected must name every non-before version exactly once")
    return table


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


# ---------------------------------------------------------------- harness measurement

def digest_of(outputs):
    blob = json.dumps(outputs, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def interpret(ops, keys, first_keys):
    """Interpret one declarative op list on one input set. The harness counts cost and hits."""
    use_cache = "cache" in ops
    use_pad = "pad" in ops
    use_wrong = "wrong" in ops
    memo = {}
    out = []
    cost = 0
    hits = 0
    for k in keys:
        if use_cache and k in memo:
            hits += 1
            cost += HIT_COST
            if use_pad:
                cost += PAD_COST
            out.append(memo[k])
            continue
        if use_wrong:
            cost += WRONG_COST
            value = k * k + 1
        else:
            cost += SQUARE_COST
            value = k * k
        if use_pad:
            cost += PAD_COST
        if use_cache:
            memo[k] = value
        out.append(value)
    if "replay" in ops:
        out = [k * k for k in first_keys]
    return {"output": out, "cost": cost, "counters": {"cache_hits": hits, "single_read": 0}}


def measure(ops, input_sets):
    first_keys = input_sets[0]["keys"]
    runs = [interpret(ops, item["keys"], first_keys) for item in input_sets]
    outputs = [r["output"] for r in runs]
    return {
        "outputs": outputs,
        "cost": sum(r["cost"] for r in runs),
        "counters": {
            "cache_hits": sum(r["counters"]["cache_hits"] for r in runs),
            "single_read": sum(r["counters"]["single_read"] for r in runs),
        },
        "digest": digest_of(outputs),
    }


# ---------------------------------------------------------------- arms

def arm_a(before_cost, after_cost):
    return "PASS" if after_cost < before_cost else "FAIL"


def _delta(before_counters, after_counters, name, direction):
    if name not in before_counters or name not in after_counters:
        return None
    before_n = before_counters[name]
    after_n = after_counters[name]
    if direction == "up":
        return after_n - before_n
    return before_n - after_n


def arm_b(before, after, claim):
    if after["cost"] >= before["cost"]:
        return "FAIL"
    if after["digest"] != before["digest"]:
        return "FAIL"
    delta = _delta(before["counters"], after["counters"], claim["mechanism"], claim["direction"])
    if delta is None or delta <= 0:
        return "FAIL"
    if (before["cost"] - after["cost"]) > delta * claim["saving_per_unit"]:
        return "FAIL"
    return "PASS"


def run(fx):
    by_id = {v["id"]: v for v in fx["versions"]}
    before = measure(by_id["before"]["ops"], fx["input_sets"])
    rows = []
    for ver in fx["versions"]:
        if ver["id"] == "before":
            continue
        after = measure(ver["ops"], fx["input_sets"])
        a = arm_a(before["cost"], after["cost"])
        b = arm_b(before, after, fx["claim"])
        observed = {"arm_a": a, "arm_b": b}
        want = fx["expected"][ver["id"]]
        delta = _delta(before["counters"], after["counters"], fx["claim"]["mechanism"], fx["claim"]["direction"])
        saved = before["cost"] - after["cost"]
        bound = None if delta is None else delta * fx["claim"]["saving_per_unit"]
        rows.append({
            "version": ver["id"],
            "arm_a": a,
            "arm_b": b,
            "before_cost": before["cost"],
            "after_cost": after["cost"],
            "cost_saved": saved,
            "before_hits": before["counters"][fx["claim"]["mechanism"]],
            "after_hits": after["counters"][fx["claim"]["mechanism"]],
            "counter_delta": delta,
            "bound": bound,
            "digest_same": after["digest"] == before["digest"],
            "before_digest": before["digest"],
            "after_digest": after["digest"],
            "matches_expected": observed == want,
            "expected": dict(want),
        })
    gate = "PASS" if all(r["matches_expected"] for r in rows) else "FAIL"
    return {
        "rows": rows,
        "gate": gate,
        "on_expiry": fx["on_expiry"],
        "claim": dict(fx["claim"]),
        "before_cost": before["cost"],
        "before_hits": before["counters"][fx["claim"]["mechanism"]],
        "before_digest": before["digest"],
        "before_outputs": before["outputs"],
    }


# ---------------------------------------------------------------- output

def report(res):
    claim = res["claim"]
    out = [
        "# Stopwatch-only (arm A) vs mechanism counter + output digest + attribution bound (arm B)",
        "",
        "Synthetic, planted versions; a mechanism demo, not the paper's rates.",
        "",
        "claim: %s %s, saving_per_unit %d" % (claim["mechanism"], claim["direction"], claim["saving_per_unit"]),
        "before cost: %d, before %s: %d" % (res["before_cost"], claim["mechanism"], res["before_hits"]),
        "",
        "| version | arm A | arm B | after cost | %s | digest same | cost saved | bound | matches table |"
        % claim["mechanism"],
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in res["rows"]:
        bound = "n/a" if r["bound"] is None else str(r["bound"])
        hits = "n/a" if r["counter_delta"] is None else str(r["after_hits"])
        out.append("| %s | %s | %s | %d | %s | %s | %d | %s | %s |" % (
            r["version"], r["arm_a"], r["arm_b"], r["after_cost"], hits,
            "yes" if r["digest_same"] else "no", r["cost_saved"], bound,
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
        err.write("DENY usage: stopwatch.py [--json] FIXTURE.json\n")
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
