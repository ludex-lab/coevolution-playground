"""w34-mixed-index-crowds-unseen-tools: shared experience in the same index as tool descriptions can crowd unused
tools out of a router's candidate list.

Method sketch of arXiv 2611.30034, "STUN-Bench: Truly Unseen Tools for Evaluating Shared Tool Experience" (CC BY 4.0).
Not a reproduction: synthetic catalog, scripted clients, a deterministic token-overlap router; no model, no
embeddings, no network, no upstream code or data.

Scorer (pinned): score = number of distinct shared tokens between the request and an index item, where tokens are
the lowercase [a-z0-9]+ runs. Total order over both item kinds: (-score, kind, item id) with kind order
description (0) before experience (1).
- Arm mixed (A): one ranked list of descriptions and experience items; walk it, mapping an experience item to its
  gold_tool_id and skipping ids already taken, until k distinct tools.
- Arm separate (B): the top k descriptions only; experience never takes a slot.
Both arms must return exactly k distinct tool ids, else the run is FAIL unequal_budget.
A pool declared split "heldout" may not label a held-out tool (gold_tool_id) or name it (its id or a token of its
declared name appearing as a token of the experience text): that is DENY heldout_leak.
Bad input is on_expiry DENY: exit 2, empty stdout, one stderr line 'DENY <code>: <detail>'.
"""

import json
import re
import sys

FIXTURE_VERSION = 1
ON_EXPIRY = "DENY"
MAX_BYTES = 65536
KIND_ORDER = {"description": 0, "experience": 1}
SPLITS = ("heldout", "leaky")
ROLES = ("crowding", "n1_empty", "n2_nonoverlap", "n3_labeled", "leaky")
ROOT_KEYS = ("fixture_version", "on_expiry", "k", "catalog", "heldout_ids", "pools", "queries", "sweep")
TOOL_KEYS = ("id", "name", "description")
POOL_KEYS = ("id", "split", "experience")
ITEM_KEYS = ("id", "text", "gold_tool_id", "client_id")
QUERY_KEYS = ("id", "role", "text", "gold_tool_id", "pool")
SWEEP_KEYS = ("query", "clients", "flip_at")
ID_RE = re.compile(r"[a-z][a-z0-9_]{0,39}\Z")
TOKEN_RE = re.compile(r"[a-z0-9]+")


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


def _text(value, where):
    if type(value) is not str or not value.strip() or len(value) > 300:
        raise Deny("bad_type", "%s must be a non-empty string of at most 300 characters" % where)
    return value


def _ident(value, where):
    if type(value) is not str or not ID_RE.match(value):
        raise Deny("bad_type", "%s must match [a-z][a-z0-9_]{0,39}" % where)
    return value


def _unique(ids, where):
    seen = set()
    for i in ids:
        if i in seen:
            raise Deny("duplicate_id", "%s repeats the id %r" % (where, i))
        seen.add(i)


def tokens(text):
    return set(TOKEN_RE.findall(text.lower()))


def validate(root):
    root = _obj(root, ROOT_KEYS, "fixture")
    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:
        raise Deny("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    if root["on_expiry"] != ON_EXPIRY:
        raise Deny("bad_on_expiry", "on_expiry must be the literal DENY")
    catalog = [_obj(t, TOOL_KEYS, "catalog tool %d" % (n + 1)) for n, t in enumerate(_list(root["catalog"], "catalog"))]
    tools = {}
    for n, t in enumerate(catalog):
        where = "catalog tool %d" % (n + 1)
        tools[_ident(t["id"], where + " id")] = t
        _text(t["name"], where + " name")
        _text(t["description"], where + " description")
    _unique([t["id"] for t in catalog], "catalog")
    k = root["k"]
    if type(k) is not int or k <= 0 or k > len(catalog):
        raise Deny("bad_k", "k must be an integer from 1 to the catalog size %d" % len(catalog))
    heldout = _list(root["heldout_ids"], "heldout_ids")
    for h in heldout:
        if _ident(h, "held-out id") not in tools:
            raise Deny("unknown_tool", "held-out id %r is not in the catalog" % h)
    _unique(heldout, "heldout_ids")
    names = {t["id"]: tokens(t["name"]) | {t["id"]} for t in catalog}
    pools = {}
    for n, p in enumerate(_list(root["pools"], "pools")):
        where = "pool %d" % (n + 1)
        if type(p) is dict and "split" not in p:
            raise Deny("bad_split", "%s declares no split" % where)
        p = _obj(p, POOL_KEYS, where)
        pid = _ident(p["id"], where + " id")
        if p["split"] not in SPLITS:
            raise Deny("bad_split", "%s split must be heldout or leaky" % where)
        items = []
        for m, it in enumerate(_list(p["experience"], where + " experience")):
            w = "%s item %d" % (where, m + 1)
            it = _obj(it, ITEM_KEYS, w)
            _ident(it["id"], w + " id")
            _text(it["text"], w + " text")
            _ident(it["client_id"], w + " client_id")
            if _ident(it["gold_tool_id"], w + " gold_tool_id") not in tools:
                raise Deny("unknown_tool", "%s gold_tool_id %r is not in the catalog" % (w, it["gold_tool_id"]))
            if p["split"] == "heldout":
                if it["gold_tool_id"] in heldout:
                    raise Deny("heldout_leak", "%s labels held-out tool %r" % (w, it["gold_tool_id"]))
                named = [h for h in heldout if names[h] & tokens(it["text"])]
                if named:
                    raise Deny("heldout_leak", "%s names held-out tool %r" % (w, named[0]))
            items.append(it)
        _unique([it["id"] for it in items], where + " experience")
        if pid in pools:
            raise Deny("duplicate_id", "pools repeat the id %r" % pid)
        pools[pid] = {"id": pid, "split": p["split"], "experience": items}
    queries = []
    for n, q in enumerate(_list(root["queries"], "queries")):
        where = "query %d" % (n + 1)
        q = _obj(q, QUERY_KEYS, where)
        _ident(q["id"], where + " id")
        _text(q["text"], where + " text")
        if q["role"] not in ROLES:
            raise Deny("bad_role", "%s role must be one of %s" % (where, ", ".join(ROLES)))
        if _ident(q["gold_tool_id"], where + " gold_tool_id") not in tools:
            raise Deny("unknown_tool", "%s gold_tool_id %r is not in the catalog" % (where, q["gold_tool_id"]))
        if _ident(q["pool"], where + " pool") not in pools:
            raise Deny("unknown_pool", "%s pool %r is not declared" % (where, q["pool"]))
        _check_role(q, pools[q["pool"]], heldout, where)
        queries.append(q)
    _unique([q["id"] for q in queries], "queries")
    missing = [r for r in ROLES if r not in {q["role"] for q in queries}]
    if missing:
        raise Deny("missing_role", "queries lack the mandatory role %s" % missing[0])
    sweep = _obj(root["sweep"], SWEEP_KEYS, "sweep")
    sq = [q for q in queries if q["id"] == sweep["query"] and q["role"] == "crowding"]
    clients = _list(sweep["clients"], "sweep clients")
    for c in clients:
        _ident(c, "sweep client")
    _unique(clients, "sweep clients")
    if not sq or not clients or type(sweep["flip_at"]) is not int or not 1 <= sweep["flip_at"] <= len(clients):
        raise Deny("bad_sweep", "sweep needs a crowding query, a client list and flip_at from 1 to its length")
    return {"k": k, "catalog": catalog, "heldout": heldout, "pools": pools, "queries": queries,
            "sweep": {"query": sq[0], "clients": clients, "flip_at": sweep["flip_at"]}}


def _check_role(q, pool, heldout, where):
    role, items = q["role"], pool["experience"]
    if role in ("crowding", "n1_empty", "n2_nonoverlap") and (pool["split"] != "heldout" or q["gold_tool_id"] not in heldout):
        raise Deny("bad_role", "%s %s needs a held-out gold tool and a heldout pool" % (where, role))
    if role == "leaky" and pool["split"] != "leaky":
        raise Deny("bad_role", "%s leaky needs a leaky pool" % where)
    if role == "n1_empty" and items:
        raise Deny("bad_control", "%s n1_empty needs an empty pool" % where)
    if role == "n2_nonoverlap" and (not items or any(tokens(it["text"]) & tokens(q["text"]) for it in items)):
        raise Deny("bad_control", "%s n2_nonoverlap needs a pool with zero token overlap with the request" % where)
    if role == "n3_labeled" and q["gold_tool_id"] not in {it["gold_tool_id"] for it in items}:
        raise Deny("bad_control", "%s n3_labeled needs the gold tool already used in the pool" % where)


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


# ---------------------------------------------------------------- the router

def ranked(query_text, catalog, experience, with_experience):
    q = tokens(query_text)
    items = [(len(q & tokens(t["description"])), "description", t["id"], t["id"]) for t in catalog]
    if with_experience:
        items += [(len(q & tokens(e["text"])), "experience", e["id"], e["gold_tool_id"]) for e in experience]
    items.sort(key=lambda x: (-x[0], KIND_ORDER[x[1]], x[2]))
    return items


def arm_mixed(query_text, catalog, experience, k):
    out = []
    for score, kind, item_id, tool in ranked(query_text, catalog, experience, True):
        if tool not in out:
            out.append(tool)
        if len(out) == k:
            break
    return out


def arm_separate(query_text, catalog, experience, k):
    return [tool for score, kind, item_id, tool in ranked(query_text, catalog, [], False)[:k]]


def budget_ok(a, b, k):
    return len(a) == len(set(a)) == k and len(b) == len(set(b)) == k


def holds(role, gold, a, b):
    if role == "crowding":
        return gold not in a and gold in b
    if role == "n1_empty":
        return a == b
    return gold in a  # n2_nonoverlap, n3_labeled, leaky


def run(fx):
    k, rows = fx["k"], []
    for q in fx["queries"]:
        pool = fx["pools"][q["pool"]]
        a = arm_mixed(q["text"], fx["catalog"], pool["experience"], k)
        b = arm_separate(q["text"], fx["catalog"], pool["experience"], k)
        budget = budget_ok(a, b, k)
        rows.append({"id": q["id"], "role": q["role"], "split": pool["split"], "gold": q["gold_tool_id"], "a": a,
                     "b": b, "budget": "ok" if budget else "unequal_budget",
                     "holds": budget and holds(q["role"], q["gold_tool_id"], a, b)})
    controls = all(r["holds"] for r in rows if r["role"] in ("n1_empty", "n2_nonoverlap", "n3_labeled"))
    crowd = [r for r in rows if r["role"] == "crowding"]
    leaky = [r for r in rows if r["role"] == "leaky"]
    sweep = run_sweep(fx)
    res = {"k": k, "rows": rows, "controls": controls,
           "criterion_a": controls and all(r["holds"] for r in crowd),
           "criterion_b": all(r["holds"] for r in leaky),
           "budget": all(r["budget"] == "ok" for r in rows), "sweep": sweep, "on_expiry": ON_EXPIRY}
    res["gate"] = "PASS" if res["budget"] and res["criterion_a"] and res["criterion_b"] and sweep["holds"] else "FAIL"
    return res


def run_sweep(fx):
    sw, k = fx["sweep"], fx["k"]
    q = sw["query"]
    pool = fx["pools"][q["pool"]]["experience"]
    gold = q["gold_tool_id"]
    steps, observed, predicted = [], None, None
    for n in range(1, len(sw["clients"]) + 1):
        exp = [e for e in pool if e["client_id"] in sw["clients"][:n]]
        a = arm_mixed(q["text"], fx["catalog"], exp, k)
        order = ranked(q["text"], fx["catalog"], exp, True)
        gold_pos = [i for i, x in enumerate(order) if x[1] == "description" and x[2] == gold][0]
        outrank = sorted({x[3] for x in order[:gold_pos] if x[1] == "experience" and x[3] != gold})
        steps.append({"clients": n, "items": len(exp), "used_tools_outranking": len(outrank), "gold_in_a": gold in a})
        if observed is None and gold not in a:
            observed = n
        if predicted is None and len(outrank) >= k:
            predicted = n
    return {"query": q["id"], "steps": steps, "flip_at": sw["flip_at"], "observed": observed, "rule": predicted,
            "holds": observed == sw["flip_at"] == predicted}


# ---------------------------------------------------------------- output

def _row(r):
    return "| %s | %s | %s | %s (%d) | %s (%d) | %s | %s | %s | %s |" % (
        r["id"], r["role"], r["gold"], ", ".join(r["a"]), len(r["a"]), ", ".join(r["b"]), len(r["b"]),
        "yes" if r["gold"] in r["a"] else "no", "yes" if r["gold"] in r["b"] else "no", r["budget"],
        "holds" if r["holds"] else "FAILS")


def report(res):
    head = ["| query | role | gold | arm A mixed (n) | arm B separate (n) | gold in A | gold in B | budget | result |",
            "|---|---|---|---|---|---|---|---|---|"]
    out = ["# Mixed index vs separate index (synthetic, planted; a mechanism demo, not the paper's rate)", "",
           "k = %d distinct tools per arm; score = shared distinct tokens; order (-score, kind, id), description "
           "before experience" % res["k"], "", "## Held-out split (pools declared heldout)", ""] + head
    out += [_row(r) for r in res["rows"] if r["split"] == "heldout"]
    out += ["", "## Leaky split (pools declared leaky; reported apart, never combined)", ""] + head
    out += [_row(r) for r in res["rows"] if r["split"] == "leaky"]
    sw = res["sweep"]
    out += ["", "## Client sweep on %s" % sw["query"], "",
            "| clients | experience items | used tools outranking gold description | gold in arm A |", "|---|---|---|---|"]
    out += ["| %d | %d | %d | %s |" % (s["clients"], s["items"], s["used_tools_outranking"],
                                       "yes" if s["gold_in_a"] else "no") for s in sw["steps"]]
    out += ["", "pre-registered flip: %d clients; observed: %s; rule (gold drops once >= k distinct used tools "
            "outrank its description): %s; sweep %s" % (sw["flip_at"], sw["observed"], sw["rule"],
                                                       "holds" if sw["holds"] else "FAILS"),
            "", "## Criteria",
            "controls n1 n2 n3: %s" % ("PASS" if res["controls"] else "FAIL"),
            "(a) held-out crowding with controls: %s" % ("PASS" if res["criterion_a"] else "FAIL"),
            "(b) leaky split, gold in arm A: %s" % ("PASS" if res["criterion_b"] else "FAIL"),
            "equal budget: %s" % ("ok" if res["budget"] else "FAIL unequal_budget"),
            "gate: %s" % res["gate"], "on_expiry: %s" % res["on_expiry"]]
    return "\n".join(out) + "\n"


def main(argv, out=None, err=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    args = argv[1:]
    as_json = args[:1] == ["--json"]
    if as_json:
        args = args[1:]
    if len(args) != 1:
        err.write("DENY usage: crowding.py [--json] FIXTURE.json\n")
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
