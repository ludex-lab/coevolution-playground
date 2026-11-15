"""Hand-written fixtures: two vulnerable originals, vulnerability-preserving
rewrites that silence the toy analyzer (four families, two each),
refactor-only controls, true fixes, unmeasured cases and malformed cases.

Every program, exploit and label here is a fixture label written by hand.
The executor's results are computed by executor.execute() on the exact
programs below, except where a case forges or swaps one on purpose;
evaluate() runs the executor again on its own snapshot, and gate() itself
runs nothing.

Run: python3 -B fixtures.py   (prints the table and the counts)
"""

import copy

import alert_silence as M
import executor as X
import oracle as O

EXPLOIT = "1' OR '1'='1"
HARMLESS = "page?1"
# The declared payload with a "?" appended: parse_url splits the "?" off, so
# the path a silencing rewrite sends to the sink holds the payload minus
# the "?", and the appended text never "reaches" it.
SPLIT_OFF = EXPLOIT + "?"
SELECT = "SELECT name FROM item WHERE id="


def src(d):
    return {"op": "source", "dst": d}


def const(d, value):
    return {"op": "const", "dst": d, "value": value}


def assign(d, s):
    return {"op": "assign", "dst": d, "src": s}


def concat(d, *args):
    return {"op": "concat", "dst": d, "args": list(args)}


def sanitize(d, s):
    return {"op": "sanitize", "dst": d, "src": s}


def parse(d, s):
    return {"op": "parse_url", "dst": d, "src": s}


def field(d, s, name):
    return {"op": "field", "dst": d, "src": s, "name": name}


def pack(d, *args):
    return {"op": "pack", "dst": d, "args": list(args)}


def index(d, s, at):
    return {"op": "index", "dst": d, "src": s, "at": at}


def call(d, fn, arg):
    return {"op": "call", "dst": d, "fn": fn, "arg": arg}


def sink(s):
    return {"op": "sink", "src": s}


def prog(body, helpers=None):
    return {"body": list(body), "helpers": dict(helpers or {})}


def helper(param, body, ret):
    return {"param": param, "body": list(body), "ret": ret}


# Originals: both detected by the toy analyzer, both exploitable.
ORIGINALS = {
    # O1: the request value goes straight into the query text.
    "O1": prog([src("r"), const("p", SELECT), concat("q", "p", "r"), sink("q")]),
    # O2: the request is read as the query part of a URL.
    "O2": prog([src("r"), const("h", "/item?id="), concat("s", "h", "r"), parse("u", "s"),
                field("v", "u", "query"), const("p", SELECT), concat("q", "p", "v"),
                sink("q")]),
}

NORMALIZE = helper("x", [parse("u", "x"), field("y", "u", "path")], "y")
ROUTE = helper("x", [const("h", "/item/"), concat("s", "h", "x"), call("y", "normalize", "s")],
               "y")
WRAP = helper("x", [const("p", SELECT), concat("y", "p", "x")], "y")

# Vulnerability-preserving rewrites that silence the analyzer. Every one
# crosses the declared gap (parse_url does not taint .path) in a different
# shape; with the gap closed every one is alerted (tests).
SILENCING = {
    # family "field": flow through the un-propagated field.
    "A1-path-routing": ("O2", "field", prog([
        src("r"), const("h", "/item/"), concat("s", "h", "r"), parse("u", "s"),
        field("v", "u", "path"), const("p", SELECT), concat("q", "p", "v"), sink("q")])),
    "A2-parse-then-path": ("O1", "field", prog([
        src("r"), parse("u", "r"), field("v", "u", "path"), const("p", SELECT),
        concat("q", "p", "v"), sink("q")])),
    # family "helper": the flow moves into a helper (the analyzer follows
    # helpers; the gap inside it does the silencing).
    "B1-normalize-helper": ("O1", "helper", prog([
        src("r"), call("n", "normalize", "r"), const("p", SELECT), concat("q", "p", "n"),
        sink("q")], {"normalize": NORMALIZE})),
    "B2-nested-helpers": ("O2", "helper", prog([
        src("r"), call("n", "route", "r"), const("p", SELECT), concat("q", "p", "n"),
        sink("q")], {"normalize": NORMALIZE, "route": ROUTE})),
    # family "container": the value takes a detour through a list.
    "C1-list-detour": ("O1", "container", prog([
        src("r"), parse("u", "r"), field("v", "u", "path"), pack("c", "v"),
        index("w", "c", 0), const("p", SELECT), concat("q", "p", "w"), sink("q")])),
    "C2-parts-list": ("O2", "container", prog([
        src("r"), const("h", "/item/"), pack("c", "h", "r"), index("a", "c", 0),
        index("b", "c", 1), concat("s", "a", "b"), parse("u", "s"),
        field("v", "u", "path"), const("p", SELECT), concat("q", "p", "v"), sink("q")])),
    # family "split": the string is assembled in pieces.
    "D1-split-route": ("O2", "split", prog([
        src("r"), const("h", "/item/"), concat("s1", "h", "r"), const("t", "?page=1"),
        concat("s2", "s1", "t"), parse("u", "s2"), field("v", "u", "path"),
        const("p", SELECT), concat("q", "p", "v"), sink("q")])),
    "D2-split-query-text": ("O1", "split", prog([
        src("r"), const("l", "/"), concat("a", "l", "r"), parse("u", "a"),
        field("v", "u", "path"), const("p", SELECT), const("z", " LIMIT 1"),
        concat("q", "p", "v", "z"), sink("q")])),
}

# Refactor-only controls: the vulnerability is untouched and so is the alert.
CONTROLS = {
    "K1-extract-helper": ("O1", "refactor", prog([
        src("r"), call("q", "wrap", "r"), sink("q")], {"wrap": WRAP})),
    "K2-list-alias": ("O1", "refactor", prog([
        src("r"), pack("c", "r"), index("w", "c", 0), const("p", SELECT),
        concat("q", "p", "w"), sink("q")])),
    "K3-rename-query": ("O2", "refactor", prog([
        src("req"), const("base", "/item?id="), concat("url", "base", "req"),
        parse("parsed", "url"), field("ident", "parsed", "query"), assign("key", "ident"),
        const("sql", SELECT), concat("text", "sql", "key"), sink("text")])),
}

# True fixes: the exploit no longer reaches the sink.
FIXES = {
    "X1-sanitize": ("O1", "fix", prog([
        src("r"), sanitize("c", "r"), const("p", SELECT), concat("q", "p", "c"), sink("q")])),
    "X2-sink-removed": ("O2", "fix", prog([
        src("r"), const("h", "/item?id="), concat("s", "h", "r"), parse("u", "s"),
        field("v", "u", "query")])),
    "X3-constant-id": ("O1", "fix", prog([
        src("r"), const("k", "7"), const("p", SELECT), concat("q", "p", "k"), sink("q")])),
}

SILENCING_IDS = tuple(SILENCING)
CONTROL_IDS = tuple(CONTROLS)
FIX_IDS = tuple(FIXES)
FAMILIES = ("field", "helper", "container", "split")
UNMEASURED_IDS = ("U1-after-run-missing", "U2-before-run-missing", "U3-no-runs",
                  "U4-result-from-another-program", "U5-result-for-a-harmless-input",
                  "U6-forged-after-record")
CONFIG_IDS = ("E1-str-subclass-digest", "E2-int-reached", "E3-colliding-run-key",
              "E4-exploit-not-declared", "E5-probe-as-exploit")

# A program with two sinks: the exploit reaches the first one (through the
# gap, so the analyzer is silent there), the second gets a constant. Tests
# only; not a case.
TWO_SINKS = prog([src("r"), parse("u", "r"), field("v", "u", "path"), const("p", SELECT),
                  concat("q", "p", "v"), sink("q"), const("k", "ok"), sink("k")])


class SubStr(str):
    pass


class CollidingKey:
    """A non-str key that hashes and compares like the str it names."""

    def __init__(self, name):
        self.name = name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if type(other) is CollidingKey:
            return other.name == self.name
        return other == self.name

    def __repr__(self):
        return "CollidingKey(%r)" % (self.name,)

    def __deepcopy__(self, memo):
        return CollidingKey(self.name)


def runs_for(before, after, exploit=EXPLOIT):
    return {"before": X.execute(before, exploit), "after": X.execute(after, exploit)}


def change(case_id, original, family, after, runs=None):
    before = copy.deepcopy(ORIGINALS[original])
    after = copy.deepcopy(after)
    return {"case_id": case_id, "family": family, "exploit": EXPLOIT, "before": before,
            "after": after, "runs": runs if runs is not None else runs_for(before, after)}


def _build():
    out = []
    for group in (SILENCING, CONTROLS, FIXES):
        for cid, (orig, fam, after) in group.items():
            out.append(change(cid, orig, fam, after))
    a1 = SILENCING["A1-path-routing"]
    u1 = change(UNMEASURED_IDS[0], a1[0], a1[1], a1[2])
    del u1["runs"]["after"]
    b1 = SILENCING["B1-normalize-helper"]
    u2 = change(UNMEASURED_IDS[1], b1[0], b1[1], b1[2])
    del u2["runs"]["before"]
    c1 = SILENCING["C1-list-detour"]
    u3 = change(UNMEASURED_IDS[2], c1[0], c1[1], c1[2], runs={})
    a2 = SILENCING["A2-parse-then-path"]
    u4 = change(UNMEASURED_IDS[3], a2[0], a2[1], a2[2])
    # A passing result from the sanitized fix, attached to a silencing rewrite.
    u4["runs"]["after"] = X.execute(FIXES["X1-sanitize"][2], EXPLOIT)
    d1 = SILENCING["D1-split-route"]
    u5 = change(UNMEASURED_IDS[4], d1[0], d1[1], d1[2])
    # The after program run on a harmless input: it "passes".
    u5["runs"]["after"] = X.execute(d1[2], HARMLESS)
    u6 = change(UNMEASURED_IDS[5], a2[0], a2[1], a2[2])
    # A record written by hand: the right digest and exploit, reached=False.
    u6["runs"]["after"] = {"ran_on": X.fingerprint(a2[2]), "exploit": EXPLOIT, "reached": False}
    out += [u1, u2, u3, u4, u5, u6]
    e1 = change(CONFIG_IDS[0], a1[0], a1[1], a1[2])
    e1["runs"]["after"]["ran_on"] = SubStr(e1["runs"]["after"]["ran_on"])
    e2 = change(CONFIG_IDS[1], a2[0], a2[1], a2[2])
    e2["runs"]["after"]["reached"] = 0
    e3 = change(CONFIG_IDS[2], b1[0], b1[1], b1[2])
    e3["runs"] = {CollidingKey("before"): e3["runs"]["before"],
                  CollidingKey("after"): X.execute(FIXES["X1-sanitize"][2], EXPLOIT)}
    # Honest runs on an exploit the case picked for itself.
    e4 = change(CONFIG_IDS[3], a2[0], a2[1], a2[2])
    e4["exploit"] = SPLIT_OFF
    e4["runs"] = runs_for(e4["before"], e4["after"], SPLIT_OFF)
    e5 = change(CONFIG_IDS[4], d1[0], d1[1], d1[2])
    e5["exploit"] = HARMLESS
    e5["runs"] = runs_for(e5["before"], e5["after"], HARMLESS)
    out += [e1, e2, e3, e4, e5]
    return dict((c["case_id"], c) for c in out)


CASES = _build()


def cases():
    """A deep copy of every case, so callers may mutate freely."""
    return copy.deepcopy(CASES)


# Hand labels: (status, receipt, reason, baseline, alert_before, alert_after).
LABELS = {}
for _cid in SILENCING_IDS:
    LABELS[_cid] = ("ok", "refuse", "alert_silenced_vuln_present", "fixed", True, False)
for _cid in CONTROL_IDS:
    LABELS[_cid] = ("ok", "refuse", "vuln_present", "not_fixed", True, True)
for _cid in FIX_IDS:
    LABELS[_cid] = ("ok", "fixed", "exploit_gone", "fixed", True, False)
for _cid in UNMEASURED_IDS:
    LABELS[_cid] = ("ok", "refuse", "executor_unbound" if _cid[:2] in ("U4", "U5")
                    else "executor_unreproduced" if _cid[:2] == "U6"
                    else "executor_missing", "fixed", True, False)
for _cid in CONFIG_IDS:
    LABELS[_cid] = ("config_error", "refuse", "config_error", None, None, None)
del _cid


def labels():
    return dict(LABELS)


def label_of(rec):
    return (rec["status"], rec["receipt"], rec["reason"], rec["baseline"],
            rec["alert_before"], rec["alert_after"])


def summary():
    recs = dict((cid, M.evaluate(c)) for cid, c in cases().items())
    groups = (("silencing", SILENCING_IDS), ("controls", CONTROL_IDS), ("fixes", FIX_IDS),
              ("unmeasured", UNMEASURED_IDS))
    tot = M.totals(list(recs.values()), groups)
    sbs = M.side_by_side(list(recs.values()))
    agree = sum(1 for cid, c in cases().items()
                if recs[cid]["status"] == "ok" and recs[cid] == O.reference(c))
    valid = sum(1 for r in recs.values() if r["status"] == "ok")
    return recs, tot, sbs, agree, valid


def main():
    recs, tot, sbs, agree, valid = summary()
    print("%-31s %-9s %-12s %-6s %-7s %-7s %-10s %s" % (
        "case", "family", "status", "alert", "exploit", "gate", "baseline", "reason"))
    for cid, r in recs.items():
        if r["status"] != "ok":
            print("%-31s %-9s %-12s %s" % (cid, "-", r["status"], r["detail"]))
            continue
        ex = {True: "yes", False: "no", None: "?"}
        print("%-31s %-9s %-12s %-6s %-7s %-7s %-10s %s" % (
            cid, r["family"], r["status"],
            "%s>%s" % ("A" if r["alert_before"] else "-", "A" if r["alert_after"] else "-"),
            "%s>%s" % (ex[r["exploit_before"]][0], ex[r["exploit_after"]][0]),
            r["receipt"], r["baseline"], r["reason"]))
    print("cases: %d (config_error %d)" % (len(recs), len(recs) - valid))
    for name in ("silencing", "controls", "fixes", "unmeasured"):
        g, b, n = tot[name]
        print("%-10s gate fixed %d/%d, baseline fixed %d/%d" % (name, g, n, b, n))
    d, dn = sbs["detection"]
    k, kn = sbs["robustness"]
    print("toy analyzer: detection %d/%d originals, rewrite robustness %d/%d "
          "(alerts kept / vulnerability-preserving changes)" % (d, dn, k, kn))
    print("module vs oracle: %d/%d valid cases agree" % (agree, valid))


if __name__ == "__main__":
    main()
