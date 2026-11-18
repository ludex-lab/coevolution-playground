"""mb-ledger-rules: a rule-based fact ledger with a full-replay baseline (stdlib only).

Clean-room sketch of the rule-layer idea in arXiv 2611.20927 (LEDGER). No model proposes facts
here: the fixture lists them. Explicit rules decide (i) the current value, (ii) the source to
trust, (iii) what a describe-only deletion removes, raw turns included. A probe receives only the
evidence bundle those rules produce. Baseline: every raw turn that matches the probe.

Exit 0 with a report; exit 2 with "DENY <code>: <detail>" on stderr for a bad fixture or usage.
"""

import json
import re
import sys
import unicodedata

FIXTURE_VERSION = 1
TRUST = {"high": 3, "medium": 2, "low": 1}          # reliability tag -> rank
ID_RE = re.compile(r"[a-z][a-z0-9_]{0,31}")
MAX_TEXT = 400
MAX_DAY = 9999
REMOVED = "[removed]"


class Deny(Exception):
    """A malformed fixture or an unsafe request. The CLI turns it into DENY with exit 2."""

    def __init__(self, code, detail):
        Exception.__init__(self, code + ": " + detail)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- strict JSON reading

def _no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise Deny("duplicate_key", "key %r appears twice in one object" % key)
        out[key] = value
    return out


def _reject_constant(name):
    raise Deny("non_finite_number", "%s is not a permitted value" % name)


def _reject_float(text):
    raise Deny("float_not_permitted", "%s: the fixture has no fractional numbers" % text)


def parse_text(text):
    if type(text) is not str:
        raise Deny("fixture_unreadable", "fixture text must be str")
    if text.startswith("\ufeff"):
        raise Deny("bom_not_permitted", "the fixture starts with a byte order mark")
    try:
        obj = json.loads(text, object_pairs_hook=_no_duplicate_keys,
                         parse_constant=_reject_constant, parse_float=_reject_float)
    except Deny:
        raise
    except (ValueError, RecursionError) as exc:
        raise Deny("malformed_json", str(exc))
    return validate(obj)


def load(path):
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        raise Deny("fixture_unreadable", "%s: %s" % (path, exc.strerror or exc))
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Deny("fixture_not_utf8", str(exc))
    return parse_text(text)


# ---------------------------------------------------------------- validation

def _obj(value, keys, where):
    if type(value) is not dict:
        raise Deny("wrong_type", "%s must be an object" % where)
    unknown = sorted(set(value) - set(keys))
    if unknown:
        raise Deny("unknown_key", "%s: %s" % (where, ", ".join(unknown)))
    missing = [k for k in keys if k not in value]
    if missing:
        raise Deny("missing_key", "%s: %s" % (where, ", ".join(missing)))
    return value


def _list(value, where, empty_ok=False):
    if type(value) is not list:
        raise Deny("wrong_type", "%s must be a list" % where)
    if not value and not empty_ok:
        raise Deny("empty_list", "%s is empty" % where)
    return value


def _ident(value, where):
    if type(value) is not str:
        raise Deny("wrong_type", "%s must be a str" % where)
    if ID_RE.fullmatch(value) is None:
        raise Deny("bad_id", "%s: %r is not [a-z][a-z0-9_]{0,31}" % (where, value))
    return value


def _text(value, where):
    if type(value) is not str:
        raise Deny("wrong_type", "%s must be a str" % where)
    if not value.strip() or value != value.strip() or len(value) > MAX_TEXT:
        raise Deny("bad_text", "%s: empty, padded or longer than %d" % (where, MAX_TEXT))
    if any(unicodedata.category(ch).startswith("C") for ch in value):
        raise Deny("bad_text", "%s: control or invisible character" % where)
    return value


def _int(value, where, lo=0):
    if type(value) is not int:
        raise Deny("wrong_type", "%s must be an int" % where)
    if not lo <= value <= MAX_DAY:
        raise Deny("out_of_range", "%s: %d not in %d..%d" % (where, value, lo, MAX_DAY))
    return value


def _period(row, where):
    start = _int(row["start"], where + ".start")
    end = row["end"]
    if end is not None:
        end = _int(end, where + ".end")
        if end < start:
            raise Deny("bad_period", "%s: end %d is before start %d" % (where, end, start))
    return start, end


def _fresh(seen, value, where):
    if value in seen:
        raise Deny("duplicate_id", "%s: %r" % (where, value))
    seen.add(value)


def validate(obj):
    """Validate a parsed fixture; return a fresh snapshot with no references into obj."""
    root = _obj(obj, ("fixture_version", "turns", "facts", "deletions", "probes"), "fixture")
    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:
        raise Deny("bad_version", "fixture_version must be the int %d" % FIXTURE_VERSION)
    fx = {"turns": [], "facts": [], "deletions": [], "probes": []}
    seen = set()
    for i, row in enumerate(_list(root["turns"], "turns")):
        where = "turns[%d]" % i
        row = _obj(row, ("id", "day", "text"), where)
        _fresh(seen, _ident(row["id"], where + ".id"), where + ".id")
        fx["turns"].append({"id": row["id"], "day": _int(row["day"], where + ".day"),
                            "text": _text(row["text"], where + ".text")})
    turns = {t["id"]: t for t in fx["turns"]}
    seen = set()
    for i, row in enumerate(_list(root["facts"], "facts")):
        where = "facts[%d]" % i
        row = _obj(row, ("id", "subject", "attribute", "value", "source", "trust", "start", "end",
                         "turn"), where)
        _fresh(seen, _ident(row["id"], where + ".id"), where + ".id")
        if type(row["trust"]) is not str or row["trust"] not in TRUST:
            raise Deny("unknown_trust", "%s.trust: %r not in %s" % (where, row["trust"], "/".join(TRUST)))
        start, end = _period(row, where)
        turn = _ident(row["turn"], where + ".turn")
        if turn not in turns:
            raise Deny("unknown_turn", "%s.turn: %r" % (where, turn))
        value = _text(row["value"], where + ".value")
        if value.lower() not in turns[turn]["text"].lower():
            raise Deny("value_not_in_turn", "%s: value does not occur in turn %s" % (where, turn))
        fx["facts"].append({"id": row["id"], "subject": _ident(row["subject"], where + ".subject"),
                            "attribute": _ident(row["attribute"], where + ".attribute"),
                            "value": value, "source": _ident(row["source"], where + ".source"),
                            "trust": row["trust"], "start": start, "end": end, "turn": turn})
    seen = set()
    for i, row in enumerate(_list(root["deletions"], "deletions", empty_ok=True)):
        where = "deletions[%d]" % i
        row = _obj(row, ("id", "day", "subject", "attribute", "source", "start", "end", "text"), where)
        _fresh(seen, _ident(row["id"], where + ".id"), where + ".id")
        start, end = _period(row, where)
        fx["deletions"].append({"id": row["id"], "day": _int(row["day"], where + ".day"),
                                "subject": _ident(row["subject"], where + ".subject"),
                                "attribute": _ident(row["attribute"], where + ".attribute"),
                                "source": _ident(row["source"], where + ".source"),
                                "start": start, "end": end, "text": _text(row["text"], where + ".text")})
    seen = set()
    for i, row in enumerate(_list(root["probes"], "probes")):
        where = "probes[%d]" % i
        row = _obj(row, ("id", "day", "subject", "attribute", "terms", "fallback", "question"), where)
        _fresh(seen, _ident(row["id"], where + ".id"), where + ".id")
        if type(row["fallback"]) is not bool:
            raise Deny("wrong_type", "%s.fallback must be a boolean" % where)
        terms = [_text(t, where + ".terms[]") for t in _list(row["terms"], where + ".terms")]
        fx["probes"].append({"id": row["id"], "day": _int(row["day"], where + ".day"),
                             "subject": _ident(row["subject"], where + ".subject"),
                             "attribute": _ident(row["attribute"], where + ".attribute"),
                             "terms": terms, "fallback": row["fallback"],
                             "question": _text(row["question"], where + ".question")})
    return fx


# ---------------------------------------------------------------- rules

def in_period(fact, day):
    return fact["start"] <= day and (fact["end"] is None or day <= fact["end"])


def overlaps(a, b):
    """Do two [start, end] periods share a day? An end of None is open."""
    a_end = float("inf") if a["end"] is None else a["end"]
    b_end = float("inf") if b["end"] is None else b["end"]
    return a["start"] <= b_end and b["start"] <= a_end


def rank(fact):
    """Rule (i)+(ii): higher trust first, then the later period start, then the later turn."""
    return (TRUST[fact["trust"]], fact["start"], fact["learned"])


def matches_terms(text, terms):
    low = text.lower()
    return any(t.lower() in low for t in terms)


class Ledger:
    """Each fact carries its source, period and trust; turns are retained raw so deletion can scrub them."""

    def __init__(self):
        self.turns = {}
        self.facts = {}
        self.tombstones = []        # descriptions of deletions only, never a value

    def ingest(self, turn, facts):
        self.turns[turn["id"]] = dict(turn)
        for fact in facts:
            self.facts[fact["id"]] = dict(fact, learned=turn["day"])

    def delete(self, req):
        """Rule (iii): a request that only describes a fact. Zero or many matches -> Deny."""
        hits = [f for f in self.facts.values()
                if (f["subject"], f["attribute"], f["source"]) == (req["subject"], req["attribute"], req["source"])
                and overlaps(f, req)]
        if not hits:
            raise Deny("no_match", "deletion %s matches no fact" % req["id"])
        if len(hits) > 1:
            raise Deny("ambiguous", "deletion %s matches %d facts: %s" % (
                req["id"], len(hits), ", ".join(sorted(f["id"] for f in hits))))
        fact = hits[0]
        value = fact["value"].lower()
        if value in req["text"].lower():
            raise Deny("restates_value", "deletion %s restates the value it removes" % req["id"])
        if any(o["value"].lower() == value for o in self.facts.values() if o is not fact):
            raise Deny("value_shared", "deletion %s: another fact holds the same value" % req["id"])
        del self.facts[fact["id"]]
        pattern = re.compile(re.escape(fact["value"]), re.IGNORECASE)
        for turn in self.turns.values():
            turn["text"] = pattern.sub(REMOVED, turn["text"])
        self.tombstones.append({"id": req["id"], "subject": req["subject"],
                                "attribute": req["attribute"], "source": req["source"]})
        return fact["value"]

    def current(self, subject, attribute, day):
        live = [f for f in self.facts.values()
                if f["subject"] == subject and f["attribute"] == attribute and in_period(f, day)]
        if not live:
            return "none", []
        best = max(rank(f) for f in live)
        top = sorted((f for f in live if rank(f) == best), key=lambda f: f["id"])
        if len({f["value"].lower() for f in top}) > 1:
            return "conflict", top
        return "current", top[:1]

    def bundle(self, probe):
        status, facts = self.current(probe["subject"], probe["attribute"], probe["day"])
        turns = []
        if status == "none" and probe["fallback"]:
            status = "fallback"
            turns = [{"id": t["id"], "text": t["text"]} for t in sorted(
                self.turns.values(), key=lambda t: (t["day"], t["id"]))
                if t["day"] <= probe["day"] and matches_terms(t["text"], probe["terms"])]
        return {"probe": probe["id"], "mode": "ledger", "status": status, "turns": turns,
                "facts": [{k: f[k] for k in ("id", "value", "source", "trust", "start", "end")}
                          for f in facts]}


def replay_bundle(fx, probe):
    """Baseline with no ledger: every raw turn up to the probe day that matches its terms."""
    turns = [{"id": t["id"], "text": t["text"]} for t in sorted(fx["turns"], key=lambda t: (t["day"], t["id"]))
             if t["day"] <= probe["day"] and matches_terms(t["text"], probe["terms"])]
    return {"probe": probe["id"], "mode": "replay", "status": "replay", "turns": turns, "facts": []}


def serialize(bundle):
    return json.dumps(bundle, sort_keys=True, ensure_ascii=False)


def run(fx):
    """Replay the timeline (turns, then deletions, then probes on each day). Return one row per probe."""
    events = ([(t["day"], 0, t["id"], "turn", t) for t in fx["turns"]]
              + [(d["day"], 1, d["id"], "delete", d) for d in fx["deletions"]]
              + [(p["day"], 2, p["id"], "probe", p) for p in fx["probes"]])
    ledger, deleted, rows = Ledger(), [], []
    for _day, _order, _id, kind, item in sorted(events, key=lambda e: e[:3]):
        if kind == "turn":
            ledger.ingest(item, [f for f in fx["facts"] if f["turn"] == item["id"]])
        elif kind == "delete":
            deleted.append(ledger.delete(item))
        else:
            rows.append({"probe": item, "deleted": list(deleted), "ledger": ledger.bundle(item),
                         "replay": replay_bundle(fx, item)})
    return rows


def leaks(bundle, values):
    """Deleted or stale values found by substring in the serialized bundle (case-insensitive)."""
    text = serialize(bundle).lower()
    return sorted(v for v in values if v.lower() in text)


def stale_values(fx, probe):
    """Values of facts whose period ended before the probe day (superseded)."""
    return sorted({f["value"] for f in fx["facts"] if f["subject"] == probe["subject"]
                   and f["attribute"] == probe["attribute"] and f["end"] is not None
                   and f["end"] < probe["day"]})


def summary(fx, rows):
    s = {"probes": len(rows), "after_deletion": 0, "ledger_deleted_leaks": 0, "replay_deleted_leaks": 0,
         "ledger_stale_leaks": 0, "replay_stale_leaks": 0, "ledger_turns": 0, "replay_turns": 0}
    for row in rows:
        stale = stale_values(fx, row["probe"])
        s["after_deletion"] += 1 if row["deleted"] else 0
        s["ledger_deleted_leaks"] += len(leaks(row["ledger"], row["deleted"]))
        s["replay_deleted_leaks"] += len(leaks(row["replay"], row["deleted"]))
        s["ledger_stale_leaks"] += len(leaks(row["ledger"], stale))
        s["replay_stale_leaks"] += len(leaks(row["replay"], stale))
        s["ledger_turns"] += len(row["ledger"]["turns"])
        s["replay_turns"] += len(row["replay"]["turns"])
    return s


def report(fx):
    rows = run(fx)
    lines = []
    for row in rows:
        p, b = row["probe"], row["ledger"]
        got = ", ".join("%s=%s (%s/%s)" % (f["id"], f["value"], f["source"], f["trust"]) for f in b["facts"])
        lines.append("%s day %d %s.%s: ledger %s [%s] turns=%s | replay turns=%s | deleted so far: %d" % (
            p["id"], p["day"], p["subject"], p["attribute"], b["status"], got or "no fact",
            ",".join(t["id"] for t in b["turns"]) or "-", ",".join(t["id"] for t in row["replay"]["turns"]) or "-",
            len(row["deleted"])))
    s = summary(fx, rows)
    lines.append("probes %(probes)d, after a deletion %(after_deletion)d" % s)
    lines.append("deleted value in evidence: ledger %(ledger_deleted_leaks)d, replay %(replay_deleted_leaks)d" % s)
    lines.append("stale value in evidence: ledger %(ledger_stale_leaks)d, replay %(replay_stale_leaks)d" % s)
    lines.append("raw turns sent: ledger %(ledger_turns)d, replay %(replay_turns)d" % s)
    return lines


# ---------------------------------------------------------------- CLI

USAGE = "usage: ledger.py FIXTURE"


def main(argv, out=None, err=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    try:
        if len(argv) != 1 or argv[0].startswith("-"):
            raise Deny("usage", USAGE)
        lines = report(load(argv[0]))
    except Deny as exc:
        err.write("DENY %s: %s\n" % (exc.code, exc.detail))
        return 2
    for line in lines:
        out.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
