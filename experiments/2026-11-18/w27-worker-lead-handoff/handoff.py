"""w27-worker-lead-handoff: do both conflicting claims reach the lead? (stdlib only).

Clean-room method sketch of the idea in arXiv 2611.22245 (workers retrieve facts, but a lead that
sees only worker handoffs may miss a conflict the workers jointly retrieved). Scripted workers
write a handoff packet from their own context only, using a fixture-declared packet rule (order
the context by id, ascending or descending, and report the first `budget` documents). The lead
sees ONLY the packets, never the raw documents. The scripted detector flags a conflict only when
the lead's evidence holds two different values for the case entity and attribute.
Three frozen layouts over the same documents:
  single_agent    one scripted agent reads the whole union itself (no packet);
  delegated_same  one worker holds both claims, the other worker holds neither;
  delegated_split the two claims sit with different workers.
The evidence-flow profiler reports (i) both claims retrieved anywhere and (ii) lead detected.
Verdict: PASS only when the lead detected the conflict; "both retrieved, lead missed" is FAIL
(handoff_failure), never a pass. on_expiry = DENY: a missing packet, or a packet whose expires_at
is before the fixture's `now` (no wall clock), gives DENY.
CLI: python3 -B handoff.py <fixture.json>; exit 2 when any row verdict is DENY (the report is still printed), and exit 2 with one line "DENY <code>: <detail>" on
stderr for a bad fixture or usage.
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
MAX_BUDGET = 20
LAYOUTS = ("single_agent", "delegated_same", "delegated_split")
RULES = ("id_asc", "id_desc")
ROOT_KEYS = ("fixture_version", "on_expiry", "now", "workers", "docs", "cases")
DOC_KEYS = ("id", "entity", "attribute", "value")
CASE_KEYS = ("id", "layout", "entity", "attribute", "claims", "assign", "packets")
PACKET_KEYS = ("rule", "budget", "issued_at", "expires_at")


class Deny(Exception):
    """A malformed fixture or bad usage; the CLI prints DENY and exits 2."""

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


def _time(value, where):
    if type(value) is not int or not 0 <= value <= MAX_TIME:
        raise Deny("bad_time", "%s must be an int in 0..%d, got %r" % (where, MAX_TIME, value))


def _list(value, where):
    if type(value) is not list:
        raise Deny("wrong_type", "%s must be a list" % where)
    return value


def _doc_ids(value, docs, where):
    ids = _list(value, where)
    for doc_id in ids:
        _ident(doc_id, where)
        if doc_id not in docs:
            raise Deny("unknown_doc", "%s names %r which is not a document" % (where, doc_id))
    if len(set(ids)) != len(ids):
        raise Deny("duplicate_id", "%s repeats a document" % where)
    return ids


def _packet(packet, where, now):
    if packet is None:
        return None
    _object(packet, PACKET_KEYS, where)
    if type(packet["rule"]) is not str or packet["rule"] not in RULES:
        raise Deny("unknown_rule", "%s rule must be one of %s, got %r" % (where, ", ".join(RULES), packet["rule"]))
    if type(packet["budget"]) is not int or not 1 <= packet["budget"] <= MAX_BUDGET:
        raise Deny("bad_budget", "%s budget must be an int in 1..%d, got %r" % (where, MAX_BUDGET, packet["budget"]))
    _time(packet["issued_at"], where + " issued_at")
    _time(packet["expires_at"], where + " expires_at")
    if packet["expires_at"] < packet["issued_at"]:
        raise Deny("bad_packet_window", "%s expires_at is before issued_at" % where)
    if packet["issued_at"] > now:
        raise Deny("bad_packet_window", "%s issued_at is after now" % where)
    return dict(packet)


def _layout_shape(layout, holds):
    sizes = sorted(len(h) for h in holds.values())
    ok = {"single_agent": len(holds) == 1 and sizes == [2],
          "delegated_same": len(holds) == 2 and sizes == [0, 2],
          "delegated_split": len(holds) == 2 and sizes == [1, 1]}[layout]
    if not ok:
        raise Deny("layout_mismatch", "assign does not match layout %s" % layout)


def _case(case, workers, docs, now, seen):
    _object(case, CASE_KEYS, "case")
    _ident(case["id"], "case id")
    if case["id"] in seen:
        raise Deny("duplicate_id", "case %r appears twice" % case["id"])
    seen.add(case["id"])
    where = "case %s" % case["id"]
    if type(case["layout"]) is not str or case["layout"] not in LAYOUTS:
        raise Deny("unknown_layout", "%s layout must be one of %s, got %r" % (where, ", ".join(LAYOUTS), case["layout"]))
    _ident(case["entity"], where + " entity")
    _ident(case["attribute"], where + " attribute")
    claims = _doc_ids(case["claims"], docs, where + " claims")
    if len(claims) != 2:
        raise Deny("bad_claims", "%s needs exactly two claims" % where)
    for claim in claims:
        if docs[claim]["entity"] != case["entity"] or docs[claim]["attribute"] != case["attribute"]:
            raise Deny("claim_mismatch", "%s claim %s is about another entity or attribute" % (where, claim))
    if docs[claims[0]]["value"] == docs[claims[1]]["value"]:
        raise Deny("no_conflict", "%s claims carry the same value" % where)
    if type(case["assign"]) is not dict or not case["assign"]:
        raise Deny("wrong_type", "%s assign must be a non-empty object" % where)
    assign, used = {}, set()
    for worker in sorted(case["assign"]):
        if worker not in workers:
            raise Deny("unknown_worker", "%s assigns documents to unknown worker %r" % (where, worker))
        ids = _doc_ids(case["assign"][worker], docs, where + " assign " + worker)
        for doc_id in ids:
            if doc_id in used:
                raise Deny("duplicate_id", "%s assigns document %s twice" % (where, doc_id))
            used.add(doc_id)
            doc = docs[doc_id]
            if doc_id not in claims and doc["entity"] == case["entity"] and doc["attribute"] == case["attribute"]:
                raise Deny("filler_conflict", "%s filler %s repeats the conflict entity and attribute" % (where, doc_id))
        assign[worker] = ids
    if any(c not in used for c in claims):
        raise Deny("claim_unassigned", "%s leaves a claim with no worker" % where)
    _layout_shape(case["layout"], {w: [c for c in claims if c in ids] for w, ids in assign.items()})
    if type(case["packets"]) is not dict:
        raise Deny("wrong_type", "%s packets must be an object" % where)
    packets = {}
    if case["layout"] == "single_agent":
        if case["packets"]:
            raise Deny("packet_not_expected", "%s is single_agent and takes no packets" % where)
    else:
        for worker in sorted(case["packets"]):
            if worker not in assign:
                raise Deny("unknown_worker", "%s has a packet for %r, which holds no documents here" % (where, worker))
        missing = [w for w in sorted(assign) if w not in case["packets"]]
        if missing:
            raise Deny("missing_key", "%s packets lacks %s" % (where, ", ".join(missing)))
        for worker in sorted(assign):
            packets[worker] = _packet(case["packets"][worker], where + " packet " + worker, now)
    return {"id": case["id"], "layout": case["layout"], "entity": case["entity"],
            "attribute": case["attribute"], "claims": claims, "assign": assign, "packets": packets}


def validate_fixture(root):
    _object(root, ROOT_KEYS, "fixture")
    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:
        raise Deny("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    if root["on_expiry"] != ON_EXPIRY:
        raise Deny("bad_on_expiry", "on_expiry must be %s, got %r" % (ON_EXPIRY, root["on_expiry"]))
    _time(root["now"], "now")
    workers = _list(root["workers"], "workers")
    if not workers:
        raise Deny("wrong_type", "workers must not be empty")
    for worker in workers:
        _ident(worker, "worker")
    if len(set(workers)) != len(workers):
        raise Deny("duplicate_id", "workers repeats an id")
    docs = {}
    for doc in _list(root["docs"], "docs"):
        _object(doc, DOC_KEYS, "doc")
        _ident(doc["id"], "doc id")
        _ident(doc["entity"], "doc entity")
        _ident(doc["attribute"], "doc attribute")
        _text(doc["value"], "doc value")
        if doc["id"] in docs:
            raise Deny("duplicate_id", "doc %r appears twice" % doc["id"])
        docs[doc["id"]] = dict(doc)
    if not docs:
        raise Deny("wrong_type", "docs must not be empty")
    cases, seen = [], set()
    for case in _list(root["cases"], "cases"):
        cases.append(_case(case, workers, docs, root["now"], seen))
    if not cases:
        raise Deny("wrong_type", "cases must not be empty")
    return docs, cases, root["now"]


# ---------------------------------------------------------------- workers, lead, profiler

def item(doc):
    """What a packet carries for one document: provenance id plus the claim fields."""
    return {"doc": doc["id"], "entity": doc["entity"], "attribute": doc["attribute"], "value": doc["value"]}


def write_packet(context, packet):
    """A worker's handoff, from its own context only: order by id, report the first `budget`."""
    ordered = sorted(context, key=lambda d: d["id"], reverse=packet["rule"] == "id_desc")
    return [item(d) for d in ordered[:packet["budget"]]]


def lead_detect(entity, attribute, evidence):
    """The lead sees only packet items. It flags a conflict when two values meet; it never picks one."""
    values = sorted({i["value"] for i in evidence if i["entity"] == entity and i["attribute"] == attribute})
    return {"detected": len(values) > 1, "values": values}


def verdict(both_retrieved, detected):
    if not both_retrieved:
        return "FAIL", "not_retrieved"
    if detected:
        return "PASS", "detected"
    return "FAIL", "handoff_failure"


def packet_state(packet, now):
    if packet is None:
        return "missing_packet"
    if packet["expires_at"] < now:
        return "expired_packet"
    return None


def profile_case(case, docs, now):
    context = {w: [docs[i] for i in ids] for w, ids in case["assign"].items()}
    retrieved = {d["id"] for docs_ in context.values() for d in docs_}
    both_retrieved = all(c in retrieved for c in case["claims"])
    row = {"case": case["id"], "layout": case["layout"], "both_retrieved": both_retrieved,
           "lead_detected": False, "lead_values": [], "reported_claims": [], "dropped_claims": []}
    states = [(w, packet_state(case["packets"][w], now)) for w in sorted(case["packets"])]
    denied = [(w, s) for w, s in states if s is not None]
    if denied:
        row["verdict"], row["reason"], row["denied_workers"] = "DENY", denied[0][1], [w for w, _ in denied]
        return row
    if case["layout"] == "single_agent":
        evidence = [item(d) for w in sorted(context) for d in sorted(context[w], key=lambda d: d["id"])]
    else:
        evidence = [i for w in sorted(context) for i in write_packet(context[w], case["packets"][w])]
    found = lead_detect(case["entity"], case["attribute"], evidence)
    reported = {i["doc"] for i in evidence}
    row["lead_detected"] = found["detected"]
    row["lead_values"] = found["values"]
    row["reported_claims"] = [c for c in case["claims"] if c in reported]
    row["dropped_claims"] = [c for c in case["claims"] if c in retrieved and c not in reported]
    row["verdict"], row["reason"] = verdict(both_retrieved, found["detected"])
    return row


def run(root):
    docs, cases, now = validate_fixture(root)
    rows = [profile_case(c, docs, now) for c in cases]
    totals = {}
    for layout in LAYOUTS:
        mine = [r for r in rows if r["layout"] == layout]
        totals[layout] = {
            "cases": len(mine),
            "both_retrieved": sum(1 for r in mine if r["both_retrieved"]),
            "lead_detected": sum(1 for r in mine if r["lead_detected"]),
            "pass": sum(1 for r in mine if r["verdict"] == "PASS"),
            "fail": sum(1 for r in mine if r["verdict"] == "FAIL"),
            "deny": sum(1 for r in mine if r["verdict"] == "DENY"),
            "handoff_failure": sum(1 for r in mine if r["reason"] == "handoff_failure"),
        }
    return {"now": now, "on_expiry": ON_EXPIRY, "docs": len(docs), "rows": rows, "totals": totals}


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
    return 2 if any(r["verdict"] == "DENY" for r in report["rows"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
