"""mb-occupancy-cap-per-bucket: a burst should not take over a bounded memory.

Method sketch of the deterministic temporal occupancy control described in arXiv 2611.25649, "KeyMem: Temporal
Occupancy Control for Robust Streaming VideoLLM Memory" (CC BY 4.0). Not a reproduction, no code copied, no model.
The paper's optional secret-key sampler is left out entirely: every choice here is deterministic.

A case is a stream of timestamped village items, each with an integer salience score, flowing into a memory of a
fixed number of slots. Three arms ingest the same stream:
- score_only  (weak): when memory is full, evict the lowest-ranked item, with no time structure.
- recency     (weak): when memory is full, evict the oldest arrival (plain FIFO, global capacity only).
- bucket_cap  (strict): the stream is cut into fixed-duration time buckets and each bucket may hold at most
                        bucket_cap slots; a full memory gives up a slot from its most crowded bucket.
Rank order is (score, t, id): lower score goes first, then the older item, then the smaller id.

Queries name the items a later question needs. The gate measures which arm still holds them.
Malformed or missing input is on_expiry DENY: exit 2, empty stdout, one ERROR line on stderr.
"""

import json
import sys
import unicodedata

FIXTURE_VERSION = 1
ON_EXPIRY = "DENY"
CAPS = {
    "file_bytes": {"limit": 65536, "on_expiry": "DENY"},
    "cases": {"limit": 20, "on_expiry": "DENY"},
    "items": {"limit": 200, "on_expiry": "DENY"},
    "queries": {"limit": 50, "on_expiry": "DENY"},
    "capacity": {"limit": 64, "on_expiry": "DENY"},
    "bucket_seconds": {"limit": 86400, "on_expiry": "DENY"},
    "t": {"limit": 10000000, "on_expiry": "DENY"},
    "score": {"limit": 1000, "on_expiry": "DENY"},
    "text_chars": {"limit": 200, "on_expiry": "DENY"},
    "id_chars": {"limit": 40, "on_expiry": "DENY"},
}
PLANTED = ("burst", "none", "need_over_cap")
ARMS = ("score_only", "recency", "bucket_cap")
WEAK_ARMS = ("score_only", "recency")
ID_FIRST = set("abcdefghijklmnopqrstuvwxyz")
ID_CHARS = ID_FIRST | set("0123456789_")
BAD_CATEGORIES = {"Cc", "Cf", "Co", "Cn", "Cs", "Zl", "Zp"}
ROOT_KEYS = ("fixture_version", "label", "cases")
CASE_KEYS = ("id", "label", "planted", "capacity", "bucket_seconds", "bucket_cap", "items", "queries")
ITEM_KEYS = ("id", "t", "score", "note")
QUERY_KEYS = ("id", "ask", "needs")


class CapError(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- loading

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise CapError("duplicate_key", "JSON object repeats the key %r" % key)
        out[key] = value
    return out


def _constant(name):
    raise CapError("not_json", "JSON constant %s is not accepted" % name)


def _no_float(text):
    raise CapError("not_integer", "number %s is not an integer" % text)


def _object(value, keys, where):
    if type(value) is not dict:
        raise CapError("bad_shape", "%s must be an object" % where)
    for key in keys:
        if key not in value:
            raise CapError("missing_key", "%s lacks %r" % (where, key))
    for key in value:
        if key not in keys:
            raise CapError("unknown_key", "%s has unknown key %r" % (where, key))
    return value


def _list(value, cap, where, low=1):
    if type(value) is not list:
        raise CapError("bad_shape", "%s must be a list" % where)
    limit = CAPS[cap]["limit"]
    if not low <= len(value) <= limit:
        raise CapError("bad_count", "%s must hold %d..%d entries (on_expiry DENY)" % (where, low, limit))
    return value


def _int(value, low, high, where):
    if type(value) is not int:
        raise CapError("not_integer", "%s must be an integer" % where)
    if not low <= value <= high:
        raise CapError("out_of_range", "%s must be in %d..%d" % (where, low, high))
    return value


def _text(value, where):
    if type(value) is not str:
        raise CapError("bad_text", "%s must be a string" % where)
    if value == "" or value != value.strip():
        raise CapError("bad_text", "%s must be non-empty with no outer spaces" % where)
    if len(value) > CAPS["text_chars"]["limit"]:
        raise CapError("bad_text", "%s is longer than %d characters" % (where, CAPS["text_chars"]["limit"]))
    if any(unicodedata.category(ch) in BAD_CATEGORIES for ch in value):
        raise CapError("bad_text", "%s holds a control or invisible character" % where)
    return unicodedata.normalize("NFC", value)


def _ident(value, where):
    if type(value) is not str or value == "" or len(value) > CAPS["id_chars"]["limit"]:
        raise CapError("bad_id", "%s must be an id of 1..%d characters" % (where, CAPS["id_chars"]["limit"]))
    if value[0] not in ID_FIRST or any(ch not in ID_CHARS for ch in value):
        raise CapError("bad_id", "%s must match [a-z][a-z0-9_]*" % where)
    return value


def _case(raw, where):
    c = _object(raw, CASE_KEYS, where)
    cid = _ident(c["id"], where + " id")
    label = _text(c["label"], where + " label")
    if c["planted"] not in PLANTED:
        raise CapError("bad_planted", "%s planted must be one of %s" % (where, ", ".join(PLANTED)))
    capacity = _int(c["capacity"], 1, CAPS["capacity"]["limit"], where + " capacity")
    seconds = _int(c["bucket_seconds"], 1, CAPS["bucket_seconds"]["limit"], where + " bucket_seconds")
    cap = _int(c["bucket_cap"], 1, CAPS["capacity"]["limit"], where + " bucket_cap")
    if cap > capacity:
        raise CapError("cap_above_capacity", "%s bucket_cap %d exceeds capacity %d" % (where, cap, capacity))
    items, seen, last_t = [], set(), 0
    for n, raw_item in enumerate(_list(c["items"], "items", where + " items")):
        iw = "%s item %d" % (where, n + 1)
        it = _object(raw_item, ITEM_KEYS, iw)
        iid = _ident(it["id"], iw + " id")
        if iid in seen:
            raise CapError("duplicate_id", "%s repeats item id %r" % (iw, iid))
        seen.add(iid)
        t = _int(it["t"], 0, CAPS["t"]["limit"], iw + " t")
        if t < last_t:
            raise CapError("out_of_order", "%s t=%d arrives before the previous t=%d" % (iw, t, last_t))
        last_t = t
        score = _int(it["score"], 0, CAPS["score"]["limit"], iw + " score")
        items.append({"id": iid, "t": t, "score": score, "note": _text(it["note"], iw + " note"),
                      "bucket": t // seconds})
    queries, qseen = [], set()
    for n, raw_q in enumerate(_list(c["queries"], "queries", where + " queries")):
        qw = "%s query %d" % (where, n + 1)
        q = _object(raw_q, QUERY_KEYS, qw)
        qid = _ident(q["id"], qw + " id")
        if qid in qseen:
            raise CapError("duplicate_id", "%s repeats query id %r" % (qw, qid))
        qseen.add(qid)
        needs = _list(q["needs"], "items", qw + " needs")
        for name in needs:
            _ident(name, qw + " need")
            if name not in seen:
                raise CapError("unknown_need", "%s needs unknown item %r" % (qw, name))
        if len(set(needs)) != len(needs):
            raise CapError("duplicate_id", "%s names an item twice" % qw)
        queries.append({"id": qid, "ask": _text(q["ask"], qw + " ask"), "needs": list(needs)})
    return {"id": cid, "label": label, "planted": c["planted"], "capacity": capacity, "bucket_seconds": seconds,
            "bucket_cap": cap, "items": items, "queries": queries}


def validate(root):
    root = _object(root, ROOT_KEYS, "fixture")
    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:
        raise CapError("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    label = _text(root["label"], "fixture label")
    cases, ids = [], set()
    for n, raw in enumerate(_list(root["cases"], "cases", "fixture cases")):
        case = _case(raw, "case %d" % (n + 1))
        if case["id"] in ids:
            raise CapError("duplicate_id", "case id %r repeats" % case["id"])
        ids.add(case["id"])
        cases.append(case)
    return {"label": label, "cases": cases}


def load_fixture(path):
    limit = CAPS["file_bytes"]["limit"]
    try:
        with open(path, "rb") as fh:
            data = fh.read(limit + 1)
    except OSError:
        raise CapError("unreadable", "fixture is missing or cannot be read")
    if len(data) > limit:
        raise CapError("too_large", "fixture is larger than %d bytes (on_expiry DENY)" % limit)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise CapError("bad_encoding", "fixture is not valid UTF-8")
    try:
        root = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_no_float)
    except CapError:
        raise
    except (ValueError, RecursionError):
        raise CapError("not_json", "fixture is not valid JSON")
    return validate(root)


# ---------------------------------------------------------------- arms

def rank_key(item):
    """Lower goes first: lower score, then the older arrival, then the smaller id."""
    return (item["score"], item["t"], item["id"])


def score_only(case):
    memory = []
    for item in case["items"]:
        memory.append(item)
        if len(memory) > case["capacity"]:
            memory.remove(min(memory, key=rank_key))
    return memory


def recency(case):
    memory = []
    for item in case["items"]:
        memory.append(item)
        if len(memory) > case["capacity"]:
            memory.pop(0)
    return memory


def _occupancy(memory):
    counts = {}
    for m in memory:
        counts[m["bucket"]] = counts.get(m["bucket"], 0) + 1
    return counts


def bucket_cap(case):
    memory = []
    for item in case["items"]:
        memory.append(item)
        same = [m for m in memory if m["bucket"] == item["bucket"]]
        if len(same) > case["bucket_cap"]:
            memory.remove(min(same, key=rank_key))
        if len(memory) > case["capacity"]:
            counts = _occupancy(memory)
            top = max(counts.values())
            lowest = [min((m for m in memory if m["bucket"] == b), key=rank_key)
                      for b in sorted(counts) if counts[b] == top]
            memory.remove(min(lowest, key=rank_key))
    return memory


ARM_FUNCS = {"score_only": score_only, "recency": recency, "bucket_cap": bucket_cap}


# ---------------------------------------------------------------- measuring

def measure(case, memory):
    kept = [m["id"] for m in memory]
    counts = _occupancy(memory)
    top = max(counts.values()) if counts else 0
    crowded = min(b for b in counts if counts[b] == top) if counts else None
    needed = []
    for q in case["queries"]:
        for name in q["needs"]:
            if name not in needed:
                needed.append(name)
    lost = [n for n in needed if n not in kept]
    bucket_of = {it["id"]: it["bucket"] for it in case["items"]}
    earlier_lost = [n for n in lost if crowded is not None and bucket_of[n] < crowded]
    return {"kept": kept, "occupancy": {str(b): counts[b] for b in sorted(counts)}, "most_crowded_bucket": crowded,
            "most_crowded_slots": top, "over_cap": top > case["bucket_cap"], "lost": lost,
            "earlier_lost": earlier_lost, "queries": {q["id"]: all(n in kept for n in q["needs"])
                                                      for q in case["queries"]}}


def judge(case, arms):
    """Closed when the strict arm holds the cap and the planted story is what was measured."""
    strict, weak = arms["bucket_cap"], arms["score_only"]
    if strict["over_cap"] or len(strict["kept"]) > case["capacity"]:
        return False, "bucket_cap broke its own cap"
    if case["planted"] == "burst":
        if strict["lost"]:
            return False, "bucket_cap lost a needed item under a burst"
        if not weak["over_cap"] or not weak["earlier_lost"]:
            return False, "planted burst did not crowd out an earlier needed item under score_only"
        return True, "burst crowds out an earlier needed item under score_only; bucket_cap holds every needed item"
    if case["planted"] == "none":
        if strict["lost"] or weak["lost"]:
            return False, "a needed item was lost with no burst planted"
        return True, "no burst: score_only and bucket_cap both hold every needed item"
    if not strict["lost"]:
        return False, "need_over_cap case lost nothing under bucket_cap"
    return True, "more needed items share one bucket than bucket_cap admits, so bucket_cap drops one (a declared cost)"


def arm_gate(rows, name):
    """FAIL when the arm breaks the cap or loses a needed item where none had to go (planted burst or none)."""
    for r in rows:
        a = r["arms"][name]
        if name == "bucket_cap" and a["over_cap"]:
            return "FAIL"
        if r["planted"] != "need_over_cap" and a["lost"]:
            return "FAIL"
    return "PASS"


def run(fx):
    rows = []
    for case in fx["cases"]:
        arms = {name: measure(case, ARM_FUNCS[name](case)) for name in ARMS}
        closed, reason = judge(case, arms)
        rows.append({"id": case["id"], "label": case["label"], "planted": case["planted"],
                     "capacity": case["capacity"], "bucket_seconds": case["bucket_seconds"],
                     "bucket_cap": case["bucket_cap"], "items": len(case["items"]),
                     "buckets": len({it["bucket"] for it in case["items"]}),
                     "queries": [{"id": q["id"], "ask": q["ask"], "needs": q["needs"]} for q in case["queries"]],
                     "arms": arms, "closed": closed, "reason": reason})
    bursts = [r for r in rows if r["planted"] == "burst"]
    weak_failures = {name: sum(1 for r in bursts if r["arms"][name]["lost"]) for name in WEAK_ARMS}
    strict_holds = sum(1 for r in rows if not r["arms"]["bucket_cap"]["over_cap"])
    arm_gates = {name: arm_gate(rows, name) for name in ARMS}
    return {"label": fx["label"], "rows": rows, "closed": sum(1 for r in rows if r["closed"]), "total": len(rows),
            "bursts": len(bursts), "weak_failures": weak_failures, "strict_within_cap": strict_holds,
            "arm_gates": arm_gates,
            "on_expiry": ON_EXPIRY}


def gate(result):
    return "PASS" if result["closed"] == result["total"] else "FAIL"


def report(result):
    out = ["# Per-bucket occupancy cap vs score-only eviction", "", "fixture: %s" % result["label"],
           "rank order: lower score first, then older, then smaller id; no keyed sampling", ""]
    for r in result["rows"]:
        out.append("## %s (planted: %s)" % (r["id"], r["planted"]))
        out.append(r["label"])
        out.append("memory of %d slots, buckets of %d s, bucket cap %d; %d items in %d buckets" % (
            r["capacity"], r["bucket_seconds"], r["bucket_cap"], r["items"], r["buckets"]))
        out.append("")
        out.append("| arm | kept | occupancy by bucket | needed lost |")
        out.append("|---|---|---|---|")
        for name in ARMS:
            a = r["arms"][name]
            occ = " ".join("b%s:%d" % (b, n) for b, n in a["occupancy"].items())
            tag = "strict" if name == "bucket_cap" else "weak"
            out.append("| %s (%s) | %s | %s | %s |" % (name, tag, " ".join(a["kept"]), occ,
                                                      " ".join(a["lost"]) or "none"))
        out.append("")
        for q in r["queries"]:
            marks = ", ".join("%s %s" % (name, "HIT" if r["arms"][name]["queries"][q["id"]] else "MISS")
                              for name in ARMS)
            out.append("- %s \"%s\" needs %s: %s" % (q["id"], q["ask"], " ".join(q["needs"]), marks))
        out.append("")
        out.append("verdict: %s (%s)" % ("closed" if r["closed"] else "OPEN", r["reason"]))
        out.append("")
    out.append("## Summary")
    out.append("closed: %d / %d on the declared gate" % (result["closed"], result["total"]))
    out.append("bucket_cap within its cap: %d / %d cases" % (result["strict_within_cap"], result["total"]))
    for name in WEAK_ARMS:
        out.append("%s lost a needed item in %d / %d planted bursts" % (
            name, result["weak_failures"][name], result["bursts"]))
    for name in ARMS:
        out.append("arm %s (%s): %s" % (name, "strict" if name == "bucket_cap" else "weak", result["arm_gates"][name]))
    out.append("gate: %s" % gate(result))
    out.append("on_expiry: %s" % result["on_expiry"])
    return "\n".join(out) + "\n"


def main(argv):
    args = argv[1:]
    as_json = args[:1] == ["--json"]
    if as_json:
        args = args[1:]
    if len(args) != 1:
        sys.stderr.write("ERROR usage: occupancy_cap.py [--json] FIXTURE.json (on_expiry=DENY)\n")
        return 2
    try:
        result = run(load_fixture(args[0]))
    except CapError as e:
        sys.stderr.write("ERROR %s: %s (on_expiry=DENY)\n" % (e.code, e.detail))
        return 2
    if as_json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    else:
        sys.stdout.write(report(result))
    return 0 if gate(result) == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
