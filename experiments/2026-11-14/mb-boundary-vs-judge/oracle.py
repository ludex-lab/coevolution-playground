"""Independent reference for mb-boundary-vs-judge (imports nothing).

A second, separately written code path for the gold score, the Arm A
boundary class and flags, the Arm B cue rule (without noise) and the toy
gate. It shares no function with the module and does not validate input:
it is only called on inputs the module accepts.

Gold: a flat {(target, field): value} map, last write wins, then a sorted
list of the pairs that differ from the gold state. Arm A: a 2x2 truth
table on (write expected, write occurred), then the stray write indices
and the absent expected pairs.
"""

_TABLE = {
    (False, False): "no_write_ok",
    (False, True): "premature_commitment",
    (True, False): "missed_commitment",
}

_CUES = ["unable", "cannot", "can't", "could not", "not able", "not eligible", "error",
         "failed"]

_OK_STATUS = {
    "cancel_reservation": "booked", "update_reservation_flights": "booked",
    "update_passengers": "booked", "cancel_pending_order": "pending",
    "modify_pending_order_address": "pending", "return_delivered_order_items": "delivered",
}
_VERB = {
    "cancel_reservation": "cancel", "update_reservation_flights": "flight",
    "update_passengers": "passenger", "cancel_pending_order": "cancel",
    "modify_pending_order_address": "address", "return_delivered_order_items": "return",
}


def reference(ep):
    want = [(e["tool"], e["target"]) for e in ep["expected_writes"]]
    got = [(w["tool"], w["target"]) for w in ep["writes"]]
    key = (len(want) > 0, len(got) > 0)
    stray = [i for i in range(len(got)) if got[i] not in want]
    absent = [p for p in want if p not in got]
    if key in _TABLE:
        cls = _TABLE[key]
    elif stray:
        cls = "unexpected_write"
    elif absent:
        cls = "missed_commitment"
    else:
        cls = "commit_ok"
    tag = "unexpected" if want else "forbidden"
    flat = {}
    for t in ep["initial_state"]:
        for f in ep["initial_state"][t]:
            flat[(t, f)] = ep["initial_state"][t][f]
    for w in ep["writes"]:
        for f in w["set"]:
            flat[(w["target"], f)] = w["set"][f]
    diff = sorted(k for k in flat if flat[k] != ep["gold_state"][k[0]][k[1]])
    return {
        "gold": "FAIL" if diff else "PASS",
        "diff": tuple(diff),
        "class": cls,
        "arm_a": "PASS" if cls in ("no_write_ok", "commit_ok") else "FAIL",
        "flags": tuple((i, tag) for i in stray),
        "missing": tuple(absent),
    }


def reference_cue(text):
    t = text.lower()
    return "FAIL" if [c for c in _CUES if t.find(c) >= 0] else "PASS"


def reference_gate(request, drop):
    tool = request["tool"]
    if drop:
        return "PERMIT" if request["request_text"].lower().find(_VERB[tool]) >= 0 else "REJECT"
    if request["customer_auth"] and request["order_status"] == _OK_STATUS[tool]:
        return "PERMIT"
    return "REJECT"
