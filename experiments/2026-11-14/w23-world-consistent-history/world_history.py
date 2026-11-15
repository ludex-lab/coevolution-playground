"""World-consistent history edits: a "done" claim must match the world.

Clean-room Python 3 standard-library method sketch of the history-edit
contract in arXiv 2611.14654 ("Cleaning an Agent's History Hurts When the
World Still Holds the Error"). Not a reproduction and not the authors'
code. The rules below are this sketch's own declared rules.

A case is one synthetic agent frozen mid-task, plus one proposed edit of
its history (a compaction, repair or handoff summary):

- case_id: non-blank str; setting: "form" or "store" (a fixture label);
- edit_kind: what the edit is called (a FIXTURE LABEL, never read by the
  rule, the baseline or the receiver);
- targets: list of distinct non-blank str, the task's targets;
- gold: {target: value}, the gold value of each target (a FIXTURE LABEL,
  read only by the scoring);
- world: {target: value}, the frozen world state (what each target holds
  now; "" means the effect is absent);
- guess: {target: value}, the value the receiver stub would pick on its own
  for a target (a FIXTURE LABEL);
- history: the original history, a list of records;
- edited: the proposed edited history, a list of records.

A record is {"target", "claim", "value"} with claim one of:
"done" (the history says the target now holds value: a completed action or
a success receipt), "failed" (an attempt to set value did not land: a
failure receipt), "note" (a note that value is the correct one, beside
whatever the history says), "neutral" (a note with no claim; value is
ignored). A target's claim in a history is its last done or failed record.

Two arms decide whether the edit is admitted:

- Rule arm (world check): it reads the original history, the edited
  history and the world. It refuses the edit when, for some target, the
  edited claim is "done V" while the world does not hold V (false_done), or
  the original history had a claim and the edit leaves none (claim_erased).
  A "done" claim whose value is blank ("" or whitespace only) names no
  effect, so it never matches the world, not even a blank world value: it is
  false_done too (a failed or absent effect may not be rewritten as a
  completed success by pointing "done" at the absence marker).
  Otherwise it admits. On refusal the receiver is handed the original,
  unedited history (fail closed to "no edit").
- Honest baseline: it trusts the history text. It reads only the edited
  history, admits every well-formed edit and believes each done claim.

Receiver fixture arm (a deterministic stub, no model): it reads only the
history it is handed and its guess, never the world or the gold. Per
target: with a note, it writes the noted value, unless the claim is already
"done" with that value; with no claim, it writes its guess; with "done V",
it skips the target when V equals its guess and writes its guess otherwise;
with "failed V", it retries V. Skipped targets retain their world value.
Recovery is the share of remaining targets (world value differs from gold
at the freeze) that hold the gold value afterwards.

Malformed input is config_error. Every dict key, at every level, must be an
exact str, and that is checked before any lookup in the dict; every value
is checked by exact type, so subclasses of str, list and dict are rejected.
validate() reads each caller value once and returns a private snapshot
(exact str values in tuples and fresh dicts); the arms and the scoring run
only on that snapshot and never read the caller's objects again.
evaluate() never raises. No timeout or expiry exists in this design. No
clock, no network, no files, no database.
"""

ADMIT = "ADMIT"
REFUSE = "REFUSE"
OK = "ok"
CONFIG_ERROR = "config_error"
ON_UNMEASURED = "on_unmeasured"

FALSE_DONE = "false_done"
CLAIM_ERASED = "claim_erased"

DONE = "done"
FAILED = "failed"
NOTE = "note"
NEUTRAL = "neutral"
CLAIMS = (DONE, FAILED, NOTE, NEUTRAL)
STATUS_CLAIMS = (DONE, FAILED)

SETTINGS = ("form", "store")
EDIT_KINDS = ("none", "neutral_note", "truthful_note", "completed_action",
              "success_receipt", "compact", "erase_error")
CASE_FIELDS = ("case_id", "setting", "edit_kind", "targets", "gold", "world", "guess",
               "history", "edited")
RECORD_FIELDS = ("target", "claim", "value")
VIEWS = ("unedited", "baseline", "rule")


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


def _value_map(m, targets, name):
    """Validate one {target: value} map over exactly the targets; fresh copy."""
    if type(m) is not dict:
        raise _Bad(name + "_invalid")
    _keys(m, name + "_key_invalid")
    if sorted(m) != sorted(targets):
        raise _Bad(name + "_shape")
    out = {}
    for target, value in list(m.items()):
        if type(value) is not str:
            raise _Bad(name + "_value_invalid")
        out[target] = value
    return out


def _records(lst, targets, name):
    """Validate one history; return a tuple of (target, claim, value) tuples."""
    if type(lst) is not list:
        raise _Bad(name + "_invalid")
    out = []
    for rec in tuple(lst):
        if type(rec) is not dict:
            raise _Bad(name + "_record_invalid")
        _keys(rec, name + "_key_invalid")
        _fields(rec, RECORD_FIELDS, name + "_record_invalid")
        target = rec["target"]
        claim = rec["claim"]
        value = rec["value"]
        if type(target) is not str or target not in targets:
            raise _Bad(name + "_target_unknown")
        if type(claim) is not str or claim not in CLAIMS:
            raise _Bad(name + "_claim_unknown")
        if type(value) is not str:
            raise _Bad(name + "_value_invalid")
        out.append((target, claim, value))
    return tuple(out)


def validate(case):
    """Return a private snapshot of case, or raise _Bad(detail).

    The snapshot is {"case_id", "setting", "edit_kind", "targets", "gold",
    "world", "guess", "history", "edited"}: exact str values in tuples and
    fresh dicts, sharing no container with the caller's objects.
    """
    if type(case) is not dict:
        raise _Bad("case_not_dict")
    _keys(case, "case_key_invalid")
    for name in CASE_FIELDS:
        if name not in case:
            raise _Bad(name + "_missing")
    _fields(case, CASE_FIELDS, "case_unknown_field")
    case_id = case["case_id"]
    if not _id(case_id):
        raise _Bad("case_id_invalid")
    setting = case["setting"]
    if type(setting) is not str or setting not in SETTINGS:
        raise _Bad("setting_invalid")
    kind = case["edit_kind"]
    if type(kind) is not str or kind not in EDIT_KINDS:
        raise _Bad("edit_kind_invalid")
    raw = case["targets"]
    if type(raw) is not list or not raw:
        raise _Bad("targets_invalid")
    targets = []
    for t in tuple(raw):
        if not _id(t):
            raise _Bad("target_invalid")
        if t in targets:
            raise _Bad("target_duplicate")
        targets.append(t)
    targets = tuple(targets)
    gold = _value_map(case["gold"], targets, "gold")
    world = _value_map(case["world"], targets, "world")
    guess = _value_map(case["guess"], targets, "guess")
    history = _records(case["history"], targets, "history")
    edited = _records(case["edited"], targets, "edited")
    return {"case_id": case_id, "setting": setting, "edit_kind": kind, "targets": targets,
            "gold": gold, "world": world, "guess": guess, "history": history,
            "edited": edited}


def blank(value):
    """A blank value ("" or whitespace only) names no effect."""
    return value.strip() == ""


def last_claims(records):
    """{target: (claim, value)} from each target's last done or failed record."""
    out = {}
    for target, claim, value in records:
        if claim in STATUS_CLAIMS:
            out[target] = (claim, value)
    return out


def rule(snap):
    """Rule arm: check the edited history's claims against the world."""
    world = snap["world"]
    before = last_claims(snap["history"])
    after = last_claims(snap["edited"])
    reasons = []
    for t in snap["targets"]:
        c = after.get(t)
        if c is None:
            if t in before:
                reasons.append((t, CLAIM_ERASED))
        elif c[0] == DONE and blank(c[1]):
            reasons.append((t, FALSE_DONE))
        elif c[0] == DONE and world[t] != c[1]:
            reasons.append((t, FALSE_DONE))
    return {"decision": REFUSE if reasons else ADMIT, "reasons": tuple(reasons)}


def baseline(snap):
    """Honest baseline: trusts the history text, so it admits the edit."""
    believed = [(t, c[1]) for t, c in sorted(last_claims(snap["edited"]).items())
                if c[0] == DONE]
    return {"decision": ADMIT, "believed_done": tuple(believed)}


def receiver(records, guess, targets):
    """Receiver stub: {target: value to write, or None to skip}.

    Reads only the handed history and its own guess; never the world."""
    claims = last_claims(records)
    notes = {}
    for target, claim, value in records:
        if claim == NOTE:
            notes[target] = value
    writes = {}
    for t in targets:
        c = claims.get(t)
        if t in notes:
            done_same = c is not None and c[0] == DONE and c[1] == notes[t]
            writes[t] = None if done_same else notes[t]
        elif c is None:
            writes[t] = guess[t]
        elif c[0] == DONE:
            writes[t] = None if c[1] == guess[t] else guess[t]
        else:
            writes[t] = c[1]
    return writes


def outcome(snap, records):
    """Run the receiver on records and score the resulting world against gold."""
    targets = snap["targets"]
    world = snap["world"]
    gold = snap["gold"]
    writes = receiver(records, snap["guess"], targets)
    final = {}
    for t in targets:
        final[t] = world[t] if writes[t] is None else writes[t]
    remaining = tuple(t for t in targets if world[t] != gold[t])
    recovered = tuple(t for t in remaining if final[t] == gold[t])
    damaged = tuple(t for t in targets if world[t] == gold[t] and final[t] != gold[t])
    return {"writes": tuple((t, writes[t]) for t in targets),
            "final": tuple((t, final[t]) for t in targets),
            "remaining": remaining, "recovered": recovered, "damaged": damaged,
            "task_success": all(final[t] == gold[t] for t in targets)}


def _config(detail):
    return {"status": CONFIG_ERROR, "detail": detail, "case_id": None, "rule": None,
            "baseline": None, "outcomes": None}


def _run(snap):
    """Decide and score on the validated snapshot only."""
    r = rule(snap)
    b = baseline(snap)
    rule_view = snap["edited"] if r["decision"] == ADMIT else snap["history"]
    base_view = snap["edited"] if b["decision"] == ADMIT else snap["history"]
    return {"status": OK, "detail": OK, "case_id": snap["case_id"], "rule": r,
            "baseline": b,
            "outcomes": {"unedited": outcome(snap, snap["history"]),
                         "baseline": outcome(snap, base_view),
                         "rule": outcome(snap, rule_view)}}


def evaluate(case):
    """Decide one proposed history edit two ways and score the receiver. Never raises."""
    try:
        snap = validate(case)
    except _Bad as exc:
        return _config(str(exc))
    except Exception:
        return _config("internal_error")
    try:
        return _run(snap)
    except Exception:
        return _config("internal_error")


def totals(records):
    """Counts over ok records, per view: remaining, recovered, damaged, task successes,
    refusals, and cases where the view recovers fewer or more targets than unedited."""
    rows = [r for r in records if r["status"] == OK]
    out = {"n": len(rows), "config_error": len(records) - len(rows),
           "rule_refused": sum(1 for r in rows if r["rule"]["decision"] == REFUSE),
           "baseline_refused": sum(1 for r in rows if r["baseline"]["decision"] == REFUSE)}
    for view in VIEWS:
        c = {"remaining": 0, "recovered": 0, "damaged": 0, "task_success": 0,
             "worse_than_unedited": 0, "better_than_unedited": 0}
        for r in rows:
            o = r["outcomes"][view]
            u = len(r["outcomes"]["unedited"]["recovered"])
            c["remaining"] += len(o["remaining"])
            c["recovered"] += len(o["recovered"])
            c["damaged"] += len(o["damaged"])
            c["task_success"] += 1 if o["task_success"] else 0
            if len(o["recovered"]) < u:
                c["worse_than_unedited"] += 1
            elif len(o["recovered"]) > u:
                c["better_than_unedited"] += 1
        out[view] = c
    return out
