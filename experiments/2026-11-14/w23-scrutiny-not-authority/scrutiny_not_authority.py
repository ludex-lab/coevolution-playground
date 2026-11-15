"""Scrutiny, not authority: a negative self-assessment flags, it cannot delete.

Clean-room Python 3 standard-library method sketch of the doctrine in
arXiv 2611.14889 ("Can an AI Agent Be Epistemically Akratic? Higher-Order
Evidence & the Limits of Self-Correction"). The paper is an argument, not
an experiment; there is no code or rate to reproduce. The rules below are
this sketch's own declared rules.

A case is one conclusion an agent reached, plus what was said about it:

- case_id: non-blank str (no surrounding spaces);
- conclusion: the conclusion as a non-blank str, read as a yes/no claim;
- self_assessment: "ok" or "defective", the agent's own rating of the
  reasoning that produced the conclusion;
- checks: a list of scrutiny checks, each
  {"check_id", "source", "basis", "verdict"} with
  source in {"self", "fixture_test", "world_record", "external_derivation"},
  basis in {"own_evidence", "self_assessment"} and
  verdict in {"supports", "refutes", "not_run"}.

A check is INDEPENDENT when its source is not "self" and its basis is its
own evidence (a check that only restates the self-assessment is not
independent, whatever its source says). A "not_run" check counts for
nothing: silence is neither a refutation nor a clearance. The independent
outcome over the checks is "refuted" (an independent refutation and no
independent support), "supported" (the reverse), "conflict" (both) or
"none".

Four arms decide RETAIN, HOLD (retained, flagged, unresolved), ELIMINATE or
NEGATE (the conclusion replaced by its negation) for each case. Gold
(sound / unsound) is a fixture label kept out of the case: no arm reads it.

- baseline (honest, obeys the rating): a defective self-assessment
  eliminates the conclusion. Otherwise the ok path: refuted -> ELIMINATE,
  conflict -> HOLD, else RETAIN.
- rule (scrutiny, not authority): a defective self-assessment FLAGS the
  conclusion and does nothing else. Refuted -> ELIMINATE; supported ->
  RETAIN (even when flagged); conflict -> HOLD; none -> HOLD when flagged
  (a missing scrutiny check fails closed), RETAIN otherwise.
- agree_flip (forced agreement by degrading the conclusion): a defective
  rating replaces the conclusion with its negation; otherwise the ok path.
- agree_silence (forced agreement by degrading the assessment): the rating
  is treated as ok for every case; the ok path.

request_elimination(case, cite) is the gate the rule arm uses: a request to
eliminate one conclusion, citing "self_assessment" and/or check ids. It is
PERMIT only when a cited check is an independent refutation and the case's
independent outcome is not "conflict" (support elsewhere in the case cannot
be ignored by citing around it). Citing the self-assessment, a self check,
a check based on the self-assessment, an unrun check or a supporting check
is REFUSE.

Malformed input is config_error. Every dict key, at every level, must be an
exact str, and that is checked before any lookup in the dict; every value
is checked by exact type, so subclasses of str, list and dict are
rejected. validate() reads each caller value once and returns a private
snapshot; every arm runs only on that snapshot and never reads the
caller's objects again. evaluate(), request_elimination() and score()
never raise. No timeout or expiry exists in this design. No clock, no
network, no files, no model.
"""

OK = "ok"
CONFIG_ERROR = "config_error"
ON_UNMEASURED = "on_unmeasured"

ASSESS_OK = "ok"
DEFECTIVE = "defective"
ASSESSMENTS = (ASSESS_OK, DEFECTIVE)

SELF = "self"
SOURCES = (SELF, "fixture_test", "world_record", "external_derivation")
OWN_EVIDENCE = "own_evidence"
FROM_ASSESSMENT = "self_assessment"
BASES = (OWN_EVIDENCE, FROM_ASSESSMENT)
SUPPORTS = "supports"
REFUTES = "refutes"
NOT_RUN = "not_run"
VERDICTS = (SUPPORTS, REFUTES, NOT_RUN)

REFUTED = "refuted"
SUPPORTED = "supported"
CONFLICT = "conflict"
NONE = "none"

RETAIN = "RETAIN"
HOLD = "HOLD"
ELIMINATE = "ELIMINATE"
NEGATE = "NEGATE"
PERMIT = "PERMIT"
REFUSE = "REFUSE"

SOUND = "sound"
UNSOUND = "unsound"
GOLDS = (SOUND, UNSOUND)

CITE_SELF = "self_assessment"
CASE_FIELDS = ("case_id", "conclusion", "self_assessment", "checks")
CHECK_FIELDS = ("check_id", "source", "basis", "verdict")
ARMS = ("baseline", "rule", "agree_flip", "agree_silence")
METRICS = ("n", "sound", "unsound", "sound_lost", "sound_negated", "unsound_eliminated",
           "unsound_held", "unsound_retained_unflagged", "eliminated",
           "eliminated_unbacked", "false_held_unflagged", "true_held", "coherent")


class _Bad(Exception):
    pass


def _id(v):
    return type(v) is str and v != "" and v == v.strip()


def _fields(d, fields, shape, keyerr):
    """Exact-str keys first, then the exact field set, then one read each."""
    if type(d) is not dict:
        raise _Bad(shape)
    keys = tuple(d)
    for k in keys:
        if type(k) is not str:
            raise _Bad(keyerr)
    if sorted(keys) != sorted(fields):
        raise _Bad(keyerr)
    return dict((k, d[k]) for k in fields)


def _one_of(v, choices, detail):
    if type(v) is not str or v not in choices:
        raise _Bad(detail)
    return v


def validate(case):
    """Return a private snapshot of case, or raise _Bad(detail)."""
    c = _fields(case, CASE_FIELDS, "case_invalid", "case_key_invalid")
    if not _id(c["case_id"]):
        raise _Bad("case_id_invalid")
    conclusion = c["conclusion"]
    if type(conclusion) is not str or conclusion.strip() == "":
        raise _Bad("conclusion_invalid")
    assessment = _one_of(c["self_assessment"], ASSESSMENTS, "self_assessment_invalid")
    raw_checks = c["checks"]
    if type(raw_checks) is not list:
        raise _Bad("checks_invalid")
    checks = []
    seen = []
    for raw in tuple(raw_checks):
        k = _fields(raw, CHECK_FIELDS, "check_invalid", "check_key_invalid")
        cid = k["check_id"]
        if not _id(cid) or cid == CITE_SELF or cid in seen:
            raise _Bad("check_id_invalid")
        seen.append(cid)
        checks.append({"check_id": cid,
                       "source": _one_of(k["source"], SOURCES, "check_source_invalid"),
                       "basis": _one_of(k["basis"], BASES, "check_basis_invalid"),
                       "verdict": _one_of(k["verdict"], VERDICTS, "check_verdict_invalid")})
    return {"case_id": c["case_id"], "conclusion": conclusion,
            "self_assessment": assessment, "checks": tuple(checks)}


def independent(check):
    """A check is independent when it is not the agent's own re-reading and
    it rests on its own evidence, not on the self-assessment."""
    return check["source"] != SELF and check["basis"] == OWN_EVIDENCE


def outcome(checks):
    """The independent outcome over the checks that ran."""
    refuted = False
    supported = False
    for k in checks:
        if not independent(k):
            continue
        if k["verdict"] == REFUTES:
            refuted = True
        elif k["verdict"] == SUPPORTS:
            supported = True
    if refuted and supported:
        return CONFLICT
    if refuted:
        return REFUTED
    if supported:
        return SUPPORTED
    return NONE


def _ok_path(out):
    """What every arm does when the self-assessment is ok (or is ignored)."""
    if out == REFUTED:
        return ELIMINATE
    if out == CONFLICT:
        return HOLD
    return RETAIN


def baseline(snap):
    """Honest baseline: obey the self-assessment."""
    if snap["self_assessment"] == DEFECTIVE:
        return {"decision": ELIMINATE}
    return {"decision": _ok_path(outcome(snap["checks"]))}


def _decide_elimination(snap, cited):
    """PERMIT only on a cited independent refutation outside a conflict."""
    if outcome(snap["checks"]) == CONFLICT:
        return REFUSE, ()
    basis = tuple(k["check_id"] for k in snap["checks"]
                  if k["check_id"] in cited and independent(k) and k["verdict"] == REFUTES)
    if basis:
        return PERMIT, basis
    return REFUSE, ()


def rule(snap):
    """Scrutiny, not authority: a defective rating flags; only independent
    refuting evidence eliminates; a missing check holds."""
    flagged = snap["self_assessment"] == DEFECTIVE
    out = outcome(snap["checks"])
    cite = (CITE_SELF,) + tuple(k["check_id"] for k in snap["checks"])
    gate_decision, basis = _decide_elimination(snap, cite)
    if gate_decision == PERMIT:
        decision = ELIMINATE
    elif out == SUPPORTED:
        decision = RETAIN
    elif out == CONFLICT:
        decision = HOLD
    elif flagged:
        decision = HOLD
    else:
        decision = RETAIN
    return {"decision": decision, "flagged": flagged, "basis": basis}


def agree_flip(snap):
    """Forced agreement by degrading the conclusion."""
    if snap["self_assessment"] == DEFECTIVE:
        return {"decision": NEGATE}
    return {"decision": _ok_path(outcome(snap["checks"]))}


def agree_silence(snap):
    """Forced agreement by degrading the assessment (treated as ok)."""
    return {"decision": _ok_path(outcome(snap["checks"]))}


def _run(snap):
    return {"status": OK, "detail": OK, "case_id": snap["case_id"],
            "self_assessment": snap["self_assessment"],
            "outcome": outcome(snap["checks"]),
            "baseline": baseline(snap), "rule": rule(snap),
            "agree_flip": agree_flip(snap), "agree_silence": agree_silence(snap)}


def _cfg(detail):
    rec = {"status": CONFIG_ERROR, "detail": detail, "case_id": None,
           "self_assessment": None, "outcome": None}
    for arm in ARMS:
        rec[arm] = None
    return rec


def evaluate(case):
    """Decide one case under all four arms. Never raises."""
    try:
        snap = validate(case)
    except _Bad as exc:
        return _cfg(str(exc))
    except Exception:
        return _cfg("internal_error")
    try:
        return _run(snap)
    except Exception:
        return _cfg("internal_error")


def validate_request(case, cite):
    snap = validate(case)
    if type(cite) is not list or not cite:
        raise _Bad("cite_invalid")
    ids = [CITE_SELF] + [k["check_id"] for k in snap["checks"]]
    cited = []
    for c in tuple(cite):
        if type(c) is not str or c not in ids or c in cited:
            raise _Bad("cite_invalid")
        cited.append(c)
    return snap, tuple(cited)


def request_elimination(case, cite):
    """Gate one elimination request. Never raises."""
    try:
        snap, cited = validate_request(case, cite)
    except _Bad as exc:
        return {"status": CONFIG_ERROR, "detail": str(exc), "decision": None, "basis": ()}
    except Exception:
        return {"status": CONFIG_ERROR, "detail": "internal_error", "decision": None,
                "basis": ()}
    try:
        decision, basis = _decide_elimination(snap, cited)
        return {"status": OK, "detail": OK, "decision": decision, "basis": basis}
    except Exception:
        return {"status": CONFIG_ERROR, "detail": "internal_error", "decision": None,
                "basis": ()}


def _final_assessment(arm, rec):
    if arm == "agree_silence":
        return ASSESS_OK
    return rec["self_assessment"]


DECISIONS = (RETAIN, HOLD, ELIMINATE, NEGATE)
OUTCOMES = (REFUTED, SUPPORTED, CONFLICT, NONE)


def _record(raw):
    """Snapshot of one evaluate() record; None for a config_error record."""
    if type(raw) is not dict:
        raise _Bad("record_invalid")
    keys = tuple(raw)
    for k in keys:
        if type(k) is not str:
            raise _Bad("record_key_invalid")
    if "status" not in keys:
        raise _Bad("record_invalid")
    status = raw["status"]
    if type(status) is str and status == CONFIG_ERROR:
        return None
    r = _fields(raw, ("status", "detail", "case_id", "self_assessment", "outcome") + ARMS,
                "record_invalid", "record_key_invalid")
    if type(r["status"]) is not str or r["status"] != OK or not _id(r["case_id"]):
        raise _Bad("record_invalid")
    rec = {"case_id": r["case_id"],
           "self_assessment": _one_of(r["self_assessment"], ASSESSMENTS, "record_invalid"),
           "outcome": _one_of(r["outcome"], OUTCOMES, "record_invalid")}
    for arm in ARMS:
        a = r[arm]
        if type(a) is not dict:
            raise _Bad("record_invalid")
        for k in tuple(a):
            if type(k) is not str:
                raise _Bad("record_key_invalid")
        if "decision" not in tuple(a):
            raise _Bad("record_invalid")
        rec[arm] = {"decision": _one_of(a["decision"], DECISIONS, "record_invalid")}
    return rec


def _score(records, gold):
    if type(gold) is not dict:
        raise _Bad("gold_invalid")
    labels = {}
    for k in tuple(gold):
        if type(k) is not str:
            raise _Bad("gold_key_invalid")
    for k in tuple(gold):
        labels[k] = _one_of(gold[k], GOLDS, "gold_invalid")
    if type(records) is not list:
        raise _Bad("records_invalid")
    out = {"config_error": 0}
    for arm in ARMS:
        out[arm] = dict((m, 0) for m in METRICS)
    for raw in tuple(records):
        rec = _record(raw)
        if rec is None:
            out["config_error"] += 1
            continue
        g = labels.get(rec["case_id"])
        if g is None:
            raise _Bad("gold_missing")
        backed = rec["outcome"] == REFUTED
        for arm in ARMS:
            d = rec[arm]["decision"]
            s = out[arm]
            s["n"] += 1
            s[g] += 1
            held = d in (RETAIN, HOLD)
            if g == SOUND:
                if d in (ELIMINATE, NEGATE):
                    s["sound_lost"] += 1
                if d == NEGATE:
                    s["sound_negated"] += 1
                    s["false_held_unflagged"] += 1
                if held:
                    s["true_held"] += 1
            else:
                if d == ELIMINATE:
                    s["unsound_eliminated"] += 1
                if d == HOLD:
                    s["unsound_held"] += 1
                if d == RETAIN:
                    s["unsound_retained_unflagged"] += 1
                    s["false_held_unflagged"] += 1
                if d == NEGATE:
                    s["true_held"] += 1
            if d == ELIMINATE:
                s["eliminated"] += 1
                if not backed:
                    s["eliminated_unbacked"] += 1
            if d in (ELIMINATE, NEGATE) or _final_assessment(arm, rec) == ASSESS_OK:
                s["coherent"] += 1
    return out


def score(records, gold):
    """Count each arm's decisions against gold labels. Never raises;
    malformed input gives {"config_error": detail}."""
    try:
        return _score(records, gold)
    except _Bad as exc:
        return {"config_error": str(exc)}
    except Exception:
        return {"config_error": "internal_error"}


def paper_results():
    """The paper is an argument with no measured rate; nothing is measured here."""
    return ON_UNMEASURED
