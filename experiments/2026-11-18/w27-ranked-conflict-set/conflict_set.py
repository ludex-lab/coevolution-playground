"""w27-ranked-conflict-set: collapse vs surface over one shared memory store (stdlib only).

Clean-room method sketch of the idea in arXiv 2611.22461 (pass the ranked conflict set to the
reader instead of collapsing it to one winner). Scripted writers fill a store; two retrieval
policies read the SAME snapshot at the SAME budget k:
  collapse  passes one entry per query (the top-ranked one);
  surface   passes every distinct value among the top-k entries (the ranked conflict set).
The scripted reader is fixed: one distinct value -> ADOPT it; several -> ESCALATE (never a
winner); none -> HOLD. Rank key (fixture-declared, deterministic): score descending, then id
ascending. This is NOT the paper's provenance weighting.
on_expiry = DENY: a passed deadline, or an expired entry among the retrieved ones, is DENY.
CLI: python3 -B conflict_set.py <fixture.json>; exit 2 with one line "DENY <code>: <detail>"
on stderr for a bad fixture or usage.
"""

import json
import math
import re
import sys

FIXTURE_VERSION = 1
ON_EXPIRY = "DENY"
ID_RE = re.compile(r"[a-z][a-z0-9_]{0,31}")
MAX_VALUE = 200
MAX_TIME = 9999
MAX_K = 50
MAX_SCORE = 1000000
ENTRY_KEYS = ("id", "writer", "field", "value", "score", "poisoned", "expires")
QUERY_KEYS = ("id", "field", "read_at", "deadline", "gold")
ROOT_KEYS = ("fixture_version", "on_expiry", "k", "policies", "entries", "queries")


class Deny(Exception):
    """A malformed fixture, a broken budget or bad usage; the CLI prints DENY and exits 2."""

    def __init__(self, code, detail):
        Exception.__init__(self, code + ": " + detail)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- strict JSON

def _no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise Deny("duplicate_key", "key %r appears twice in one object" % key)
        out[key] = value
    return out


def _reject_constant(name):
    raise Deny("non_finite_number", "%s is not permitted" % name)


def _parse_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise Deny("non_finite_number", "%s is not finite" % text)
    return value


def parse_text(text):
    if text.startswith("\ufeff"):
        raise Deny("bom_not_permitted", "the fixture starts with a byte order mark")
    try:
        return json.loads(text, object_pairs_hook=_no_duplicate_keys,
                          parse_constant=_reject_constant, parse_float=_parse_float)
    except (ValueError, RecursionError) as exc:
        raise Deny("bad_json", str(exc).replace("\n", " ")[:80])


# ---------------------------------------------------------------- validation

def _object(value, keys, where):
    if type(value) is not dict:
        raise Deny("wrong_type", "%s must be an object" % where)
    missing = [k for k in keys if k not in value]
    if missing:
        raise Deny("missing_key", "%s lacks %s" % (where, ", ".join(missing)))
    unknown = sorted(set(value) - set(keys))
    if unknown:
        raise Deny("unknown_key", "%s has %s" % (where, ", ".join(unknown)))
    return value


def _ident(value, where):
    if type(value) is not str or ID_RE.fullmatch(value) is None:
        raise Deny("bad_id", "%s must match [a-z][a-z0-9_]{0,31}, got %r" % (where, value))


def _text(value, where):
    if type(value) is not str or not value.strip() or value != value.strip() or len(value) > MAX_VALUE:
        raise Deny("bad_text", "%s must be a trimmed non-empty string, got %r" % (where, value))
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise Deny("bad_text", "%s holds a control character" % where)


def _time(value, where, nullable):
    if value is None and nullable:
        return
    if type(value) is not int or not 0 <= value <= MAX_TIME:
        raise Deny("bad_time", "%s must be an int in 0..%d%s, got %r"
                   % (where, MAX_TIME, " or null" if nullable else "", value))


def _score(value, where):
    if type(value) not in (int, float) or abs(value) > MAX_SCORE:
        raise Deny("bad_score", "%s must be an int or float within +-%d, got %r" % (where, MAX_SCORE, value))


def validate_entry(entry, where):
    _object(entry, ENTRY_KEYS, where)
    for key in ("id", "writer", "field"):
        _ident(entry[key], where + "." + key)
    _text(entry["value"], where + ".value")
    _score(entry["score"], where + ".score")
    if type(entry["poisoned"]) is not bool:
        raise Deny("wrong_type", "%s.poisoned must be a boolean" % where)
    _time(entry["expires"], where + ".expires", True)


def validate_query(query, where):
    _object(query, QUERY_KEYS, where)
    _ident(query["id"], where + ".id")
    _ident(query["field"], where + ".field")
    _time(query["read_at"], where + ".read_at", False)
    _time(query["deadline"], where + ".deadline", True)
    _text(query["gold"], where + ".gold")


def validate_fixture(root):
    """Return a Store plus the checked query list, or raise Deny."""
    _object(root, ROOT_KEYS, "fixture")
    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:
        raise Deny("bad_version", "fixture_version must be the int %d" % FIXTURE_VERSION)
    if root["on_expiry"] != ON_EXPIRY:
        raise Deny("bad_on_expiry", "on_expiry must be %s" % ON_EXPIRY)
    check_k(root["k"])
    check_policies(root["policies"])
    for name in ("entries", "queries"):
        if type(root[name]) is not list or not root[name]:
            raise Deny("empty_" + name, "%s must be a non-empty list" % name)
    store = Store()
    for idx, entry in enumerate(root["entries"]):
        validate_entry(entry, "entries[%d]" % idx)
        store.write(entry)
    seen = set()
    for idx, query in enumerate(root["queries"]):
        validate_query(query, "queries[%d]" % idx)
        if query["id"] in seen:
            raise Deny("duplicate_id", "query id %r repeats" % query["id"])
        seen.add(query["id"])
    return store, root["queries"]


def check_k(k):
    if type(k) is not int or not 1 <= k <= MAX_K:
        raise Deny("bad_k", "k must be an int in 1..%d, got %r" % (MAX_K, k))


def check_policies(names):
    if type(names) is not list or not names or len(set(map(str, names))) != len(names):
        raise Deny("bad_policies", "policies must be a non-empty list without repeats")
    for name in names:
        if type(name) is not str or name not in POLICIES:
            raise Deny("unknown_policy", "policy %r is not one of %s" % (name, ", ".join(sorted(POLICIES))))


# ---------------------------------------------------------------- store, policies, reader

def rank_key(entry):
    return (-entry["score"], entry["id"])


class Store:
    """One contract: write / read / snapshot. Writers are fixture rows, not models."""

    def __init__(self):
        self._entries = {}

    def write(self, entry):
        if entry["id"] in self._entries:
            raise Deny("duplicate_id", "entry id %r repeats" % entry["id"])
        self._entries[entry["id"]] = dict(entry)

    def snapshot(self):
        return [dict(e) for e in sorted(self._entries.values(), key=rank_key)]

    def read(self, field, k):
        return [e for e in self.snapshot() if e["field"] == field][:k]


def collapse(retrieved):
    return retrieved[:1]


def surface(retrieved):
    seen, out = set(), []
    for entry in retrieved:
        if entry["value"] not in seen:
            seen.add(entry["value"])
            out.append(entry)
    return out


POLICIES = {"collapse": collapse, "surface": surface}


def check_budget(view, retrieved, k):
    ids = [e["id"] for e in retrieved]
    if len(retrieved) > k or len(view) > k:
        raise Deny("budget_exceeded", "a view of %d from %d retrieved exceeds k=%d" % (len(view), len(retrieved), k))
    if any(e["id"] not in ids for e in view):
        raise Deny("budget_exceeded", "the view holds an entry outside the retrieved top-k")


def public(entry):
    """What an agent may see: no poison label, no expiry."""
    return {"id": entry["id"], "writer": entry["writer"], "value": entry["value"], "score": entry["score"]}


def reader(view):
    """Fixed scripted rule: never picks a winner among several distinct values."""
    values = []
    for entry in view:
        if entry["value"] not in values:
            values.append(entry["value"])
    if not values:
        return {"decision": "HOLD", "reason": "empty_view"}
    if len(values) > 1:
        return {"decision": "ESCALATE", "values": values}
    return {"decision": "ADOPT", "value": values[0]}


def distinct(entries):
    return len({e["value"] for e in entries})


def outcome(decision, gold, retrieved):
    if decision["decision"] == "ADOPT":
        if decision["value"] == gold:
            return "correct"
        if any(e["poisoned"] and e["value"] == decision["value"] for e in retrieved):
            return "poisoned"
        return "wrong"
    return {"ESCALATE": "escalated", "HOLD": "held", "DENY": "denied"}[decision["decision"]]


def read_query(store, query, policy, k):
    row = {"query": query["id"], "policy": policy, "k": k, "view": [], "conflict_visible": False}
    retrieved = store.read(query["field"], k)
    row["field_conflict"] = distinct([e for e in store.snapshot() if e["field"] == query["field"]]) > 1
    row["conflict_retrieved"] = distinct(retrieved) > 1
    if query["deadline"] is not None and query["read_at"] > query["deadline"]:
        decision = {"decision": "DENY", "reason": "deadline_passed"}
    elif any(e["expires"] is not None and e["expires"] < query["read_at"] for e in retrieved):
        decision = {"decision": "DENY", "reason": "entry_expired"}
    else:
        view = POLICIES[policy](retrieved)
        check_budget(view, retrieved, k)
        row["view"] = [public(e) for e in view]
        row["conflict_visible"] = distinct(view) > 1
        decision = reader(row["view"])
    row["decision"] = decision
    row["outcome"] = outcome(decision, query["gold"], retrieved)
    return row


OUTCOMES = ("correct", "poisoned", "wrong", "escalated", "held", "denied")


def run(root):
    store, queries = validate_fixture(root)
    k, policies = root["k"], root["policies"]
    rows = [read_query(store, q, p, k) for p in policies for q in queries]
    totals = {}
    for p in policies:
        mine = [r for r in rows if r["policy"] == p]
        counts = {o: sum(1 for r in mine if r["outcome"] == o) for o in OUTCOMES}
        counts["conflict_visible"] = sum(1 for r in mine if r["conflict_visible"])
        counts["queries"] = len(mine)
        totals[p] = counts
    return {"k": k, "on_expiry": ON_EXPIRY, "entries": len(store.snapshot()), "rows": rows, "totals": totals}


def load(path):
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        text = data.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise Deny("fixture_unreadable", exc.__class__.__name__)
    return parse_text(text)


def main(argv, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        if len(argv) != 1 or argv[0].startswith("-"):
            raise Deny("usage", "expected exactly one fixture path")
        report = run(load(argv[0]))
    except Deny as exc:
        err.write("DENY %s: %s\n" % (exc.code, exc.detail))
        return 2
    out.write(json.dumps(report, sort_keys=True, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
