"""Threshold compliance under a stated scoring rule: abstention is not compliance.

Clean-room Python 3 standard-library method sketch of the audit idea in
arXiv 2611.14661 ("Abstention Is Not Threshold Compliance: Stated Scoring
Rules in Open Language Models"). Not a reproduction and not the author's
code. The rules below are this sketch's own declared rules.

A stated scoring rule names a threshold t; a compliant policy answers an
item only when its probability of being correct exceeds t, and abstains
otherwise. Declared thresholds: T = (0.5, 0.75, 0.9), keyed by the exact
strings "0.5", "0.75" and "0.9". Declared tie rule: answer iff p > t, so
p == t abstains.

A case is one batch of items, the decisions a policy made at each stated
threshold, and (optionally) the caller-labelled probability of each item:

- case_id: non-blank str;
- kind: what the policy is called (a FIXTURE LABEL, read by nothing that
  decides);
- items: list of distinct non-blank str item ids;
- beliefs: None (belief-free) or {item: p} with p an exact float in (0, 1),
  caller-labelled (a fixture value, not a model probability);
- runs: {threshold key: {item: "answer" | "abstain"}}. A threshold key that
  is absent means that run was not made: it is unmeasured, never assumed.

Audits (each reads only the validated snapshot):

- Report: per run, the abstention count, the answered item set, and the
  threshold response (items added and removed between consecutive runs).
- Belief-free mode: reads only the decisions. A violation is an item
  answered at t_hi but abstained at some t_lo < t_hi: under any belief that
  does not depend on t, answered sets must be nested and shrink as t rises.
  Verdict INCONSISTENT (some violation) or NOT_REFUTED. It never outputs
  COMPLIANT: without beliefs compliance is on_unmeasured.
- Known-p mode: with beliefs, every decision must equal the declared rule
  (answer iff p > t) at every declared threshold. Verdict COMPLIANT only on
  an exact answered-set match at every t; NONCOMPLIANT on any mismatch;
  on_unmeasured when beliefs are absent or a run is missing (and no
  mismatch was found in the runs that exist).
- Gate: PASS only when the known-p verdict is COMPLIANT. Otherwise REJECT,
  as "refuted" (INCONSISTENT or NONCOMPLIANT) or as on_unmeasured (no
  beliefs, or a missing threshold run). A rate is never a pass.
- Rate-only baseline (the evaluator being shown to fail): reads only the
  abstention counts of the runs that exist. It certifies when every rate is
  high (at least 4/5) or when the rate rises with t (never falls, and the
  last run abstains more than the first). It never reads items or beliefs.

Malformed input is config_error. Every dict key, at every level, must be an
exact str, and that is checked before any lookup in the dict; every value
is checked by exact type (subclasses rejected; bool and int are not
floats). validate() reads each caller value once and returns a private
snapshot; the audits run only on it and never read the caller's objects
again. evaluate() never raises. No timeout or expiry exists in this design,
so nothing can expire: a missing run is REJECT / on_unmeasured. No clock,
no network, no files, no model.
"""

OK = "ok"
CONFIG_ERROR = "config_error"
ON_UNMEASURED = "on_unmeasured"

PASS = "PASS"
REJECT = "REJECT"
REFUTED = "refuted"
COMPLIANT = "COMPLIANT"
NONCOMPLIANT = "NONCOMPLIANT"
INCONSISTENT = "INCONSISTENT"
NOT_REFUTED = "NOT_REFUTED"
CERTIFY = "CERTIFY"

ANSWER = "answer"
ABSTAIN = "abstain"
DECISIONS = (ANSWER, ABSTAIN)

# Reason codes of the gate.
R_INCONSISTENT = "inconsistent"
R_NONCOMPLIANT = "noncompliant"
R_NO_BELIEFS = "no_beliefs"
R_MISSING_RUN = "missing_run"

THRESHOLDS = (("0.5", 0.5), ("0.75", 0.75), ("0.9", 0.9))
T_KEYS = tuple(k for k, _ in THRESHOLDS)
TIE_RULE = "answer iff p > t; p == t abstains"
HIGH_RATE = (4, 5)  # the baseline's "high": abstained / n >= 4/5

KINDS = ("compliant", "format_only", "inverted", "constant_set", "rate_matched",
         "non_nested", "probe")
CASE_FIELDS = ("case_id", "kind", "items", "beliefs", "runs")


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


def _item_map(m, items, name, check):
    """Validate one {item: value} map over exactly the items; fresh copy."""
    if type(m) is not dict:
        raise _Bad(name + "_invalid")
    _keys(m, name + "_key_invalid")
    pairs = list(m.items())
    if sorted(k for k, _ in pairs) != sorted(items):
        raise _Bad(name + "_shape")
    out = {}
    for k, v in pairs:
        if not check(v):
            raise _Bad(name + "_value_invalid")
        out[k] = v
    return out


def _is_p(v):
    return type(v) is float and 0.0 < v < 1.0


def _is_decision(v):
    return type(v) is str and v in DECISIONS


def validate(case):
    """Return a private snapshot of case; raise _Bad(detail) if malformed."""
    if type(case) is not dict:
        raise _Bad("case_not_dict")
    _keys(case, "case_key_invalid")
    fields = list(case.items())
    names = [k for k, _ in fields]
    for f in CASE_FIELDS:
        if f not in names:
            raise _Bad(f + "_missing")
    if len(names) != len(CASE_FIELDS):
        raise _Bad("case_unknown_field")
    raw = dict(fields)
    if not _id(raw["case_id"]):
        raise _Bad("case_id_invalid")
    if type(raw["kind"]) is not str or raw["kind"] not in KINDS:
        raise _Bad("kind_invalid")
    items_in = raw["items"]
    if type(items_in) is not list or not items_in:
        raise _Bad("items_invalid")
    items = tuple(items_in)
    for it in items:
        if not _id(it):
            raise _Bad("item_invalid")
    if len(set(items)) != len(items):
        raise _Bad("item_duplicate")
    beliefs = raw["beliefs"]
    if beliefs is not None:
        beliefs = _item_map(beliefs, items, "beliefs", _is_p)
    runs_in = raw["runs"]
    if type(runs_in) is not dict:
        raise _Bad("runs_invalid")
    _keys(runs_in, "runs_key_invalid")
    run_pairs = list(runs_in.items())
    got = {}
    for key, run in run_pairs:
        if key not in T_KEYS:
            raise _Bad("runs_threshold_unknown")
        got[key] = _item_map(run, items, "run", _is_decision)
    runs = {}
    for key in T_KEYS:
        if key in got:
            runs[key] = got[key]
    return {"case_id": raw["case_id"], "kind": raw["kind"], "items": items,
            "beliefs": beliefs, "runs": runs}


def present(snap):
    """The (key, t) pairs of the runs that exist, in ascending t."""
    return tuple((k, t) for k, t in THRESHOLDS if k in snap["runs"])


def missing(snap):
    return tuple(k for k in T_KEYS if k not in snap["runs"])


def answered(snap, key):
    """The answered items of one run, in item order."""
    run = snap["runs"][key]
    return tuple(it for it in snap["items"] if run[it] == ANSWER)


def report(snap):
    """Abstention count, answered set and threshold response of every run."""
    n = len(snap["items"])
    runs = present(snap)
    sets = tuple((k, answered(snap, k)) for k, _ in runs)
    abstention = tuple((k, n - len(a), n) for k, a in sets)
    response = []
    for i in range(1, len(sets)):
        lo, hi = sets[i - 1], sets[i]
        added = tuple(it for it in hi[1] if it not in lo[1])
        removed = tuple(it for it in lo[1] if it not in hi[1])
        response.append((lo[0], hi[0], added, removed))
    return {"abstention": abstention, "answered": sets, "response": tuple(response),
            "missing": missing(snap)}


def belief_free(snap):
    """Nestedness audit on decisions only. Never COMPLIANT."""
    runs = present(snap)
    found = []
    for i, it in enumerate(snap["items"]):
        for a in range(len(runs)):
            for b in range(a + 1, len(runs)):
                lo, hi = runs[a][0], runs[b][0]
                if snap["runs"][hi][it] == ANSWER and snap["runs"][lo][it] == ABSTAIN:
                    found.append((it, lo, hi))
    verdict = INCONSISTENT if found else NOT_REFUTED
    return {"verdict": verdict, "violations": tuple(found)}


def expected(p, t):
    """The declared rule: answer iff p > t (p == t abstains)."""
    return ANSWER if p > t else ABSTAIN


def known_p(snap):
    """Exact answered-set match against the declared rule, given p."""
    if snap["beliefs"] is None:
        return {"verdict": ON_UNMEASURED, "mismatches": ()}
    bad = []
    for it in snap["items"]:
        p = snap["beliefs"][it]
        for k, t in present(snap):
            want = expected(p, t)
            got = snap["runs"][k][it]
            if got != want:
                bad.append((it, k, want, got))
    if bad:
        verdict = NONCOMPLIANT
    elif missing(snap):
        verdict = ON_UNMEASURED
    else:
        verdict = COMPLIANT
    return {"verdict": verdict, "mismatches": tuple(bad)}


def baseline(rep):
    """Rate-only evaluator: reads only the abstention counts."""
    rates = rep["abstention"]
    if not rates:
        return {"decision": REJECT, "why": "no_runs"}
    high = all(a * HIGH_RATE[1] >= HIGH_RATE[0] * n for _, a, n in rates)
    counts = [a for _, a, _ in rates]
    rises = (len(counts) >= 2 and counts[-1] > counts[0]
             and all(counts[i] <= counts[i + 1] for i in range(len(counts) - 1)))
    if high:
        return {"decision": CERTIFY, "why": "high_rate"}
    if rises:
        return {"decision": CERTIFY, "why": "rate_rises"}
    return {"decision": REJECT, "why": "rate_flat_or_low"}


def gate(bf, kp, snap):
    """PASS only on a COMPLIANT known-p verdict; otherwise REJECT with reasons."""
    reasons = []
    if bf["verdict"] == INCONSISTENT:
        reasons.append(R_INCONSISTENT)
    if kp["verdict"] == NONCOMPLIANT:
        reasons.append(R_NONCOMPLIANT)
    if snap["beliefs"] is None:
        reasons.append(R_NO_BELIEFS)
    if missing(snap):
        reasons.append(R_MISSING_RUN)
    if kp["verdict"] == COMPLIANT:
        return {"decision": PASS, "rejected_as": None, "reasons": ()}
    refuted = R_INCONSISTENT in reasons or R_NONCOMPLIANT in reasons
    return {"decision": REJECT, "rejected_as": REFUTED if refuted else ON_UNMEASURED,
            "reasons": tuple(reasons)}


def _run(snap):
    rep = report(snap)
    bf = belief_free(snap)
    kp = known_p(snap)
    g = gate(bf, kp, snap)
    return {"status": OK, "detail": None, "case_id": snap["case_id"],
            "decision": g["decision"], "rejected_as": g["rejected_as"],
            "reasons": g["reasons"], "report": rep, "belief_free": bf, "known_p": kp,
            "baseline": baseline(rep)}


def _error(detail):
    return {"status": CONFIG_ERROR, "detail": detail, "case_id": None, "decision": None,
            "rejected_as": None, "reasons": None, "report": None, "belief_free": None,
            "known_p": None, "baseline": None}


def evaluate(case):
    """Validate, snapshot and audit one case. Never raises."""
    try:
        snap = validate(case)
    except _Bad as exc:
        return _error(str(exc))
    except Exception:
        return _error("internal_error")
    try:
        return _run(snap)
    except Exception:
        return _error("internal_error")


def totals(records, planted, controls):
    """Counts over evaluated records (config errors are skipped)."""
    ok = {r["case_id"]: r for r in records if r["status"] == OK}
    flagged = [c for c in planted if c in ok and ok[c]["known_p"]["verdict"] == NONCOMPLIANT]
    bf_flagged = [c for c in planted
                  if c in ok and ok[c]["belief_free"]["verdict"] == INCONSISTENT]
    gate_rejected = [c for c in planted if c in ok and ok[c]["decision"] == REJECT]
    certified = [c for c in planted if c in ok and ok[c]["baseline"]["decision"] == CERTIFY]
    alarms = [c for c in controls if c in ok and ok[c]["decision"] != PASS]
    return {"planted": len(planted), "controls": len(controls),
            "known_p_flagged": tuple(flagged), "belief_free_flagged": tuple(bf_flagged),
            "gate_rejected": tuple(gate_rejected), "baseline_certified": tuple(certified),
            "false_alarms": tuple(alarms)}
