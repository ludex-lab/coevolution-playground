"""Commit-boundary check vs a text-only judge, scored against gold state.

Clean-room Python 3 standard-library method sketch of the evaluator
comparison in arXiv 2611.14581 ("When Evaluators of AI Agents Disagree: An
Empirical Study of Native Scoring, LLM Judges, and Commit-Boundary Checks
on tau2-bench"). Not a reproduction and not the author's code. The rules
below are this sketch's own declared rules.

An episode is one synthetic tool-using customer-service episode:

- episode_id: non-blank str; domain: "airline" or "retail";
- expected_writes: list of {"tool", "target"}; the writes the task
  expects (a FIXTURE LABEL; an empty list means no write is expected);
- initial_state: {target: {field: value}} before the episode;
- writes: the recorded database writes, in order, each
  {"tool", "target", "set": {field: value}};
- final_text: the agent's final assistant text (exact str);
- gold_state: {target: {field: value}}, the gold final state (a FIXTURE
  LABEL), with the same targets and fields as initial_state.

Three scores per episode, each PASS or FAIL:

- gold: native scoring. Apply the writes to initial_state in order and
  compare the result with gold_state field by field.
- Arm A, the boundary evaluator (no model): compare "a write was expected"
  with "a write occurred". Every write outside the expected set is flagged:
  "forbidden" when no write was expected at all, "unexpected" otherwise.
  Classes: no_write_ok, commit_ok (PASS); premature_commitment,
  unexpected_write, missed_commitment (FAIL). Arm A reads only
  expected_writes and the (tool, target) of each write: never final_text,
  never the written values, never gold_state.
- Arm B, a seeded noisy text-only judge stub (no model): it reads only
  final_text. A cue rule fails a text holding a failure cue and passes any
  other; then a private random.Random, seeded from the caller's exact int
  seed and the text, flips that verdict with probability 1/4. One draw, one
  verdict: no voting, no ensemble, no global random state.

Optional gate (a toy of this sketch, not the paper's gate): gate(request,
drop) decides PERMIT or REJECT for one write request from an evidence
digest. With customer_auth and order_status in the digest it permits only
an authenticated request on a permitted order status; when the digest
drops either field, only the request wording is left, and it permits
exactly the requests whose text names the tool's verb.

Malformed input is config_error. Every dict key, at every level, must be an
exact str, and that is checked before any lookup in the dict; every value
is checked by exact type, so subclasses of str, int, list and dict are
rejected. validate() reads each caller value once and returns a private
snapshot (exact str values in tuples and fresh dicts); the three scores run
only on that snapshot and never read the caller's objects again. evaluate()
and gate() never raise. No timeout or expiry exists in this design. No
clock, no network, no files.
"""

import random

PASS = "PASS"
FAIL = "FAIL"
PERMIT = "PERMIT"
REJECT = "REJECT"
OK = "ok"
CONFIG_ERROR = "config_error"
ON_UNMEASURED = "on_unmeasured"

NO_WRITE_OK = "no_write_ok"
COMMIT_OK = "commit_ok"
PREMATURE = "premature_commitment"
UNEXPECTED = "unexpected_write"
MISSED = "missed_commitment"
PASSING = (NO_WRITE_OK, COMMIT_OK)

FORBIDDEN = "forbidden"
UNEXPECTED_FLAG = "unexpected"

DOMAINS = {
    "airline": ("cancel_reservation", "update_reservation_flights", "update_passengers"),
    "retail": ("cancel_pending_order", "modify_pending_order_address",
               "return_delivered_order_items"),
}
EPISODE_FIELDS = ("episode_id", "domain", "expected_writes", "initial_state", "writes",
                  "final_text", "gold_state")
EXPECTED_FIELDS = ("tool", "target")
WRITE_FIELDS = ("tool", "target", "set")

FAIL_CUES = ("unable", "cannot", "can't", "could not", "not able", "not eligible",
             "error", "failed")
NOISE_ONE_IN = 4

GATE_FIELDS = ("tool", "request_text", "customer_auth", "order_status")
DROPPABLE = ("customer_auth", "order_status")
PERMITTED_STATUS = {
    "cancel_reservation": ("booked",),
    "update_reservation_flights": ("booked",),
    "update_passengers": ("booked",),
    "cancel_pending_order": ("pending",),
    "modify_pending_order_address": ("pending",),
    "return_delivered_order_items": ("delivered",),
}
REQUEST_VERB = {
    "cancel_reservation": "cancel",
    "update_reservation_flights": "flight",
    "update_passengers": "passenger",
    "cancel_pending_order": "cancel",
    "modify_pending_order_address": "address",
    "return_delivered_order_items": "return",
}


class _Bad(Exception):
    """Internal: a config_error with its detail."""


def paper_results():
    """The paper's figures are not measured here."""
    return ON_UNMEASURED


def _id(v):
    return type(v) is str and v.strip() != ""


def _keys(d, detail):
    """Raise _Bad(detail) unless every key of the exact dict d is an exact str.

    Runs before any lookup in d: iterating an exact dict runs no caller
    code, so no caller-defined __eq__ or __hash__ is reached afterwards.
    """
    for k in d:
        if type(k) is not str:
            raise _Bad(detail)


def _fields(d, names, detail):
    """d is an exact dict whose keys are exact str; its keys must be names."""
    if sorted(d) != sorted(names):
        raise _Bad(detail)


def _state(s, name):
    """Validate one {target: {field: value}} map and return a fresh copy."""
    if type(s) is not dict or not s:
        raise _Bad(name + "_invalid")
    _keys(s, name + "_key_invalid")
    out = {}
    for target, row in list(s.items()):
        if not _id(target):
            raise _Bad(name + "_target_invalid")
        if type(row) is not dict or not row:
            raise _Bad(name + "_row_invalid")
        _keys(row, name + "_key_invalid")
        fresh = {}
        for field, value in list(row.items()):
            if not _id(field) or type(value) is not str:
                raise _Bad(name + "_value_invalid")
            fresh[field] = value
        out[target] = fresh
    return out


def validate(episode):
    """Return a private snapshot of episode, or raise _Bad(detail).

    The snapshot is {"episode_id", "domain", "expected", "initial",
    "writes", "final_text", "gold"}: exact str values in tuples and fresh
    dicts, sharing no container with the caller's objects.
    """
    if type(episode) is not dict:
        raise _Bad("episode_not_dict")
    _keys(episode, "episode_key_invalid")
    for name in EPISODE_FIELDS:
        if name not in episode:
            raise _Bad(name + "_missing")
    _fields(episode, EPISODE_FIELDS, "episode_unknown_field")
    episode_id = episode["episode_id"]
    if not _id(episode_id):
        raise _Bad("episode_id_invalid")
    domain = episode["domain"]
    if type(domain) is not str or domain not in DOMAINS:
        raise _Bad("domain_invalid")
    tools = DOMAINS[domain]
    initial = _state(episode["initial_state"], "initial_state")
    gold = _state(episode["gold_state"], "gold_state")
    if sorted(gold) != sorted(initial):
        raise _Bad("gold_state_shape")
    for target in initial:
        if sorted(gold[target]) != sorted(initial[target]):
            raise _Bad("gold_state_shape")
    exp = episode["expected_writes"]
    if type(exp) is not list:
        raise _Bad("expected_writes_invalid")
    expected = []
    for entry in tuple(exp):
        if type(entry) is not dict:
            raise _Bad("expected_entry_invalid")
        _keys(entry, "expected_key_invalid")
        _fields(entry, EXPECTED_FIELDS, "expected_entry_invalid")
        tool = entry["tool"]
        target = entry["target"]
        if type(tool) is not str or tool not in tools:
            raise _Bad("expected_tool_unknown")
        if type(target) is not str or target not in initial:
            raise _Bad("expected_target_unknown")
        if (tool, target) in expected:
            raise _Bad("expected_duplicate")
        expected.append((tool, target))
    recorded = episode["writes"]
    if type(recorded) is not list:
        raise _Bad("writes_invalid")
    writes = []
    for w in tuple(recorded):
        if type(w) is not dict:
            raise _Bad("write_not_dict")
        _keys(w, "write_key_invalid")
        _fields(w, WRITE_FIELDS, "write_fields_invalid")
        tool = w["tool"]
        target = w["target"]
        sets = w["set"]
        if type(tool) is not str or tool not in tools:
            raise _Bad("write_tool_unknown")
        if type(target) is not str or target not in initial:
            raise _Bad("write_target_unknown")
        if type(sets) is not dict or not sets:
            raise _Bad("write_set_invalid")
        _keys(sets, "write_set_key_invalid")
        fresh = {}
        for field, value in list(sets.items()):
            if field not in initial[target] or type(value) is not str:
                raise _Bad("write_set_invalid")
            fresh[field] = value
        writes.append({"tool": tool, "target": target, "set": fresh})
    final_text = episode["final_text"]
    if type(final_text) is not str:
        raise _Bad("final_text_invalid")
    return {"episode_id": episode_id, "domain": domain, "expected": tuple(expected),
            "initial": initial, "writes": tuple(writes), "final_text": final_text,
            "gold": gold}


def gold_score(snap):
    """Native scoring: final state after the writes vs the gold state."""
    state = {}
    for target, row in snap["initial"].items():
        state[target] = dict(row)
    for w in snap["writes"]:
        state[w["target"]].update(w["set"])
    diff = []
    for target in sorted(state):
        for field in sorted(state[target]):
            if state[target][field] != snap["gold"][target][field]:
                diff.append((target, field))
    return {"verdict": PASS if not diff else FAIL, "diff": tuple(diff)}


def boundary(snap):
    """Arm A: expected write vs write occurred, per write. No model."""
    expected = snap["expected"]
    flags = []
    seen = []
    for i, w in enumerate(snap["writes"]):
        pair = (w["tool"], w["target"])
        if pair in expected:
            if pair not in seen:
                seen.append(pair)
        elif expected:
            flags.append((i, UNEXPECTED_FLAG))
        else:
            flags.append((i, FORBIDDEN))
    missing = tuple(p for p in expected if p not in seen)
    occurred = len(snap["writes"]) > 0
    if not expected:
        cls = PREMATURE if occurred else NO_WRITE_OK
    elif not occurred:
        cls = MISSED
    elif flags:
        cls = UNEXPECTED
    elif missing:
        cls = MISSED
    else:
        cls = COMMIT_OK
    return {"verdict": PASS if cls in PASSING else FAIL, "class": cls,
            "flags": tuple(flags), "missing": missing}


def judge_base(final_text):
    """The stub's cue rule: FAIL on any failure cue in the text, else PASS."""
    low = final_text.lower()
    for cue in FAIL_CUES:
        if cue in low:
            return FAIL
    return PASS


def judge(final_text, seed):
    """Arm B: the seeded noisy text-only judge stub. Sees only final_text."""
    rng = random.Random("%d|%s" % (seed, final_text))
    verdict = judge_base(final_text)
    if rng.randrange(NOISE_ONE_IN) == 0:
        verdict = FAIL if verdict == PASS else PASS
    return verdict


def _config(detail):
    return {"status": CONFIG_ERROR, "detail": detail, "episode_id": None, "domain": None,
            "gold": None, "arm_a": None, "arm_b": None}


def _run(snap, seed):
    """Score the validated snapshot only."""
    return {"status": OK, "detail": OK, "episode_id": snap["episode_id"],
            "domain": snap["domain"], "gold": gold_score(snap), "arm_a": boundary(snap),
            "arm_b": {"verdict": judge(snap["final_text"], seed), "seed": seed}}


def evaluate(episode, seed):
    """Score one episode three ways. Never raises."""
    try:
        if type(seed) is not int:
            raise _Bad("seed_invalid")
        snap = validate(episode)
    except _Bad as exc:
        return _config(str(exc))
    except Exception:
        return _config("internal_error")
    try:
        return _run(snap, seed)
    except Exception:
        return _config("internal_error")


def agreement(records):
    """Counts over ok records: each arm's verdict against the gold verdict."""
    rows = [r for r in records if r["status"] == OK]
    out = {"n": len(rows), "config_error": len(records) - len(rows)}
    for arm in ("arm_a", "arm_b"):
        c = {"agree": 0, "pass_gold_fail": 0, "fail_gold_pass": 0}
        for r in rows:
            mine, gold = r[arm]["verdict"], r["gold"]["verdict"]
            if mine == gold:
                c["agree"] += 1
            elif mine == PASS:
                c["pass_gold_fail"] += 1
            else:
                c["fail_gold_pass"] += 1
        out[arm] = c
    out["arm_a_vs_arm_b"] = sum(1 for r in rows
                                if r["arm_a"]["verdict"] == r["arm_b"]["verdict"])
    return out


def validate_gate(request, drop):
    """Return the private evidence digest the gate sees, or raise _Bad."""
    if type(request) is not dict:
        raise _Bad("request_not_dict")
    _keys(request, "request_key_invalid")
    _fields(request, GATE_FIELDS, "request_fields_invalid")
    tool = request["tool"]
    text = request["request_text"]
    auth = request["customer_auth"]
    status = request["order_status"]
    if type(tool) is not str or tool not in PERMITTED_STATUS:
        raise _Bad("request_tool_unknown")
    if type(text) is not str:
        raise _Bad("request_text_invalid")
    if type(auth) is not bool:
        raise _Bad("customer_auth_invalid")
    if not _id(status):
        raise _Bad("order_status_invalid")
    if type(drop) is not list:
        raise _Bad("drop_invalid")
    dropped = []
    for name in tuple(drop):
        if type(name) is not str or name not in DROPPABLE or name in dropped:
            raise _Bad("drop_invalid")
        dropped.append(name)
    full = {"tool": tool, "request_text": text, "customer_auth": auth,
            "order_status": status}
    return dict((k, v) for k, v in full.items() if k not in dropped)


def _gate_decide(digest):
    tool = digest["tool"]
    if "customer_auth" in digest and "order_status" in digest:
        ok = digest["customer_auth"] is True and digest["order_status"] in PERMITTED_STATUS[tool]
    else:
        # Evidence was dropped: only the request wording is left.
        ok = REQUEST_VERB[tool] in digest["request_text"].lower()
    return PERMIT if ok else REJECT


def gate(request, drop):
    """Toy pre-write gate over an evidence digest. Never raises."""
    try:
        digest = validate_gate(request, drop)
    except _Bad as exc:
        return {"status": CONFIG_ERROR, "detail": str(exc), "decision": None, "seen": ()}
    except Exception:
        return {"status": CONFIG_ERROR, "detail": "internal_error", "decision": None, "seen": ()}
    try:
        return {"status": OK, "detail": OK, "decision": _gate_decide(digest),
                "seen": tuple(sorted(digest))}
    except Exception:
        return {"status": CONFIG_ERROR, "detail": "internal_error", "decision": None, "seen": ()}
