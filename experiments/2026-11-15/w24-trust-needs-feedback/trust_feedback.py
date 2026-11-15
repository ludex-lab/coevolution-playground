"""Trust in an advisor needs timely external feedback.

Clean-room Python 3 standard-library method sketch of the reliance contract
suggested by arXiv 2611.14833 ("Do People Trust AI Assistants Even When They
Are Consistently Wrong?"). Not a reproduction and not the authors' code;
no human data. The rules below are this sketch's own declared rules.

A case is one session: one advisor gives advice in rounds 1..N, and the
session may receive accuracy-feedback events about that advice.

- case_id: non-blank str; condition: "feedback" or "no_feedback" (a FIXTURE
  LABEL, read by nothing that decides);
- advisor_id: non-blank str;
- rounds: N, an exact int >= 1;
- truth: N exact bools, whether each round's advice was right (a FIXTURE
  LABEL, read only by the scoring);
- advice: N records {"round", "confidence", "claim", "prestige"}: round is
  i + 1, confidence an exact finite float in [0, 1] (the advisor's own
  stated confidence), claim a str (the advisor's own argument or
  self-claim), prestige a str (how the advisor is presented);
- external_sources: distinct non-blank str, the declared external feedback
  channels;
- max_age: exact int >= 0, in rounds; trust_bar: exact int >= 1;
- feedback: events {"source", "advisor_id", "round", "at", "outcome"}:
  "round" is the round of the advice graded, "at" (1..N) the round in which
  the event arrives, outcome "correct" or "incorrect";
- pending: reliance decisions waiting for feedback, records {"pending_id",
  "round", "deadline", "on_expiry"} with round <= deadline <= N and
  on_expiry one of DENY, SAFE_FALLBACK, ESCALATE, HOLD.

Declared prior: untrusted (reliance VERIFY, verify-before-use).

Rule arm, per round k = 1..N: the reliance on round k's advice is RELY when
the advisor is trusted at the start of round k, else VERIFY. Then the
events arriving at k are checked in list order. An event is accepted only when
its source is not the advisor, is one of the declared external sources, its
advisor_id is the session's advisor, its round is a real round, not later
than its arrival (no feedback for a future round), its age (at - round) is
at most max_age (boundary inclusive; older is stale, and stale feedback is
no feedback), and the exact same event (source, advisor_id, round, outcome)
was not accepted before (no replay; arrival is not part of the key, so a
re-send in a later round is a replay too). Replay is the only dedupe: a
fresh "incorrect" for a round that already has an accepted "correct", from
the same source or another declared source, is accepted.
The accepted events of round k are then applied with every "correct"
before every "incorrect", so a negative always wins its round. An accepted
"correct" adds one to the score only when its graded round has neither
counted before nor been refuted (a round counts at most once, and a round
with an accepted "incorrect" never counts again); the advisor becomes
trusted when the score reaches trust_bar. An accepted "incorrect" always
applies: it marks its round refuted, resets the score to 0 (a reset, not a
decrement) and drops the advisor to untrusted, so the next round is VERIFY.
The outcome depends only on which events arrive in which round, never on
their order in the list. Upgrades never come from the advisor's confidence,
claim, prestige or any other field: the rule never reads them.

Pending decision: final at its deadline, from the accepted events for its
round that arrive no later than the deadline. Any such "incorrect" resolves
it DO_NOT_RELY (at the earliest such arrival), whatever else arrived;
otherwise any such "correct" resolves it RELY (at the earliest such
arrival); with no such event it resolves at the deadline to its declared
on_expiry, never RELY. The deadline is between the decision's round and N
(a deadline past the last round is config_error). A missing or undeclared
on_expiry, including a str subclass, is config_error.

Persuadable baseline (the failure described in the abstract): reliance
level starts high (2 of 0..3) and RELY means level >= 2; after each round's
advice the level rises by one (to at most 3) when the stated confidence is
at least 1/2; any event saying "incorrect" that arrives that round, from
any source, resets it to 0. It never checks sources, freshness or rounds.

Malformed input is config_error. Every dict key, at every level, must be an
exact str, and that is checked before any lookup in the dict; every value
is checked by exact type (subclasses of str, int, float, list and dict are
rejected; bool is not an int; NaN and infinities are rejected).
validate() reads each caller value once and returns a private snapshot;
the rule arm, the baseline and the scoring run only on that snapshot and
never read the caller's objects again. evaluate() never raises. Rounds are
the only clock: no wall clock, no network, no files, no model.
"""

OK = "ok"
CONFIG_ERROR = "config_error"
ON_UNMEASURED = "on_unmeasured"

RELY = "RELY"
VERIFY = "VERIFY"
DO_NOT_RELY = "DO_NOT_RELY"
TRUSTED = "trusted"
UNTRUSTED = "untrusted"
PRIOR = UNTRUSTED

CORRECT = "correct"
INCORRECT = "incorrect"
OUTCOMES = (CORRECT, INCORRECT)

DENY = "DENY"
SAFE_FALLBACK = "SAFE_FALLBACK"
ESCALATE = "ESCALATE"
HOLD = "HOLD"
ON_EXPIRY = (DENY, SAFE_FALLBACK, ESCALATE, HOLD)

# Refusal reasons, in the order they are checked.
SELF_SOURCED = "self_sourced"
NOT_EXTERNAL = "not_external"
ADVISOR_MISMATCH = "advisor_mismatch"
NO_SUCH_ROUND = "no_such_round"
FUTURE_ROUND = "future_round"
STALE = "stale"
DUPLICATE = "duplicate"
REASONS = (SELF_SOURCED, NOT_EXTERNAL, ADVISOR_MISMATCH, NO_SUCH_ROUND, FUTURE_ROUND,
           STALE, DUPLICATE)

BASE_START = 2
BASE_TOP = 3
BASE_RELY = 2
BASE_CONFIDENT = 0.5

CONDITIONS = ("feedback", "no_feedback")
CASE_FIELDS = ("case_id", "condition", "advisor_id", "rounds", "truth", "advice",
               "external_sources", "max_age", "trust_bar", "feedback", "pending")
ADVICE_FIELDS = ("round", "confidence", "claim", "prestige")
EVENT_FIELDS = ("source", "advisor_id", "round", "at", "outcome")
PENDING_FIELDS = ("pending_id", "round", "deadline", "on_expiry")


class _Bad(Exception):
    """Internal: a config_error with its detail."""


def paper_results():
    """The paper's figures are not measured here."""
    return ON_UNMEASURED


def _id(v):
    return type(v) is str and v.strip() != ""


def _int(v, lo, hi=None):
    return type(v) is int and v >= lo and (hi is None or v <= hi)


def _unit(v):
    return type(v) is float and 0.0 <= v <= 1.0


def _keys(d, detail):
    """Raise _Bad(detail) unless every key of the exact dict d is an exact str.

    Runs before any lookup in d: iterating an exact dict runs no caller
    code, so no caller-defined __eq__ or __hash__ is reached afterwards.
    """
    for k in d:
        if type(k) is not str:
            raise _Bad(detail)


def _record(d, names, name):
    """Validate one exact dict with exactly the given exact-str keys; copy."""
    if type(d) is not dict:
        raise _Bad(name + "_invalid")
    _keys(d, name + "_key_invalid")
    pairs = list(d.items())
    if sorted(k for k, _ in pairs) != sorted(names):
        raise _Bad(name + "_shape")
    return dict(pairs)


def _list(v, name):
    if type(v) is not list:
        raise _Bad(name + "_invalid")
    return list(v)


def validate(case):
    """Return a private snapshot of case; raise _Bad(detail) if malformed."""
    if type(case) is not dict:
        raise _Bad("case_not_dict")
    _keys(case, "case_key_invalid")
    pairs = list(case.items())
    names = [k for k, _ in pairs]
    for f in CASE_FIELDS:
        if f not in names:
            raise _Bad(f + "_missing")
    if len(names) != len(CASE_FIELDS):
        raise _Bad("case_unknown_field")
    raw = dict(pairs)
    if not _id(raw["case_id"]):
        raise _Bad("case_id_invalid")
    if type(raw["condition"]) is not str or raw["condition"] not in CONDITIONS:
        raise _Bad("condition_invalid")
    advisor = raw["advisor_id"]
    if not _id(advisor):
        raise _Bad("advisor_id_invalid")
    n = raw["rounds"]
    if not _int(n, 1):
        raise _Bad("rounds_invalid")
    truth = tuple(_list(raw["truth"], "truth"))
    if len(truth) != n or any(type(t) is not bool for t in truth):
        raise _Bad("truth_invalid")
    advice = []
    for i, rec in enumerate(_list(raw["advice"], "advice")):
        r = _record(rec, ADVICE_FIELDS, "advice")
        if not _int(r["round"], 1) or r["round"] != i + 1:
            raise _Bad("advice_round_invalid")
        if not _unit(r["confidence"]):
            raise _Bad("advice_confidence_invalid")
        if type(r["claim"]) is not str:
            raise _Bad("advice_claim_invalid")
        if type(r["prestige"]) is not str:
            raise _Bad("advice_prestige_invalid")
        advice.append((r["round"], r["confidence"], r["claim"], r["prestige"]))
    if len(advice) != n:
        raise _Bad("advice_shape")
    sources = tuple(_list(raw["external_sources"], "external_sources"))
    for s in sources:
        if not _id(s):
            raise _Bad("external_source_invalid")
    if len(set(sources)) != len(sources):
        raise _Bad("external_source_duplicate")
    if not _int(raw["max_age"], 0):
        raise _Bad("max_age_invalid")
    if not _int(raw["trust_bar"], 1):
        raise _Bad("trust_bar_invalid")
    events = []
    for rec in _list(raw["feedback"], "feedback"):
        e = _record(rec, EVENT_FIELDS, "event")
        if not _id(e["source"]):
            raise _Bad("event_source_invalid")
        if not _id(e["advisor_id"]):
            raise _Bad("event_advisor_invalid")
        if type(e["round"]) is not int:
            raise _Bad("event_round_invalid")
        if not _int(e["at"], 1, n):
            raise _Bad("event_at_invalid")
        if type(e["outcome"]) is not str or e["outcome"] not in OUTCOMES:
            raise _Bad("event_outcome_invalid")
        events.append((e["source"], e["advisor_id"], e["round"], e["at"], e["outcome"]))
    pending = []
    seen = []
    for rec in _list(raw["pending"], "pending"):
        if type(rec) is dict:
            _keys(rec, "pending_key_invalid")
            if "on_expiry" not in [k for k in rec]:
                raise _Bad("on_expiry_missing")
        p = _record(rec, PENDING_FIELDS, "pending")
        if not _id(p["pending_id"]) or p["pending_id"] in seen:
            raise _Bad("pending_id_invalid")
        seen.append(p["pending_id"])
        if not _int(p["round"], 1, n):
            raise _Bad("pending_round_invalid")
        if not _int(p["deadline"], p["round"], n):
            raise _Bad("pending_deadline_invalid")
        if type(p["on_expiry"]) is not str or p["on_expiry"] not in ON_EXPIRY:
            raise _Bad("on_expiry_invalid")
        pending.append((p["pending_id"], p["round"], p["deadline"], p["on_expiry"]))
    return {"case_id": raw["case_id"], "condition": raw["condition"], "advisor_id": advisor,
            "rounds": n, "truth": truth, "advice": tuple(advice), "external_sources": sources,
            "max_age": raw["max_age"], "trust_bar": raw["trust_bar"],
            "feedback": tuple(events), "pending": tuple(pending)}


def refusal(snap, event, seen):
    """The first reason an event is refused, or None when it is accepted.

    seen holds the replay keys (source, advisor_id, round, outcome) of the
    events accepted so far.
    """
    source, advisor, rnd, at, outcome = event
    if source == snap["advisor_id"] or source == advisor:
        return SELF_SOURCED
    if source not in snap["external_sources"]:
        return NOT_EXTERNAL
    if advisor != snap["advisor_id"]:
        return ADVISOR_MISMATCH
    if rnd < 1 or rnd > snap["rounds"]:
        return NO_SUCH_ROUND
    if rnd > at:
        return FUTURE_ROUND
    if at - rnd > snap["max_age"]:
        return STALE
    if (source, advisor, rnd, outcome) in seen:
        return DUPLICATE
    return None


def rule(snap):
    """Trust and reliance over the rounds, from accepted feedback only."""
    state = PRIOR
    score = 0
    upgrades = 0
    reliance = []
    accepted = []
    refused = []
    seen = []
    credited = []
    refuted = []
    for k in range(1, snap["rounds"] + 1):
        reliance.append(RELY if state == TRUSTED else VERIFY)
        this_round = []
        for i, ev in enumerate(snap["feedback"]):
            if ev[3] != k:
                continue
            why = refusal(snap, ev, seen)
            if why is not None:
                refused.append((i, why))
                continue
            seen.append((ev[0], ev[1], ev[2], ev[4]))
            accepted.append((i, ev[2], ev[4]))
            this_round.append((ev[2], ev[4]))
        ordered = ([e for e in this_round if e[1] == CORRECT]
                   + [e for e in this_round if e[1] == INCORRECT])
        for rnd, outcome in ordered:
            if outcome == CORRECT:
                if rnd in credited:
                    continue
                if rnd in refuted:
                    continue
                credited.append(rnd)
                score += 1
                if score >= snap["trust_bar"] and state != TRUSTED:
                    state = TRUSTED
                    upgrades += 1
            else:
                refuted.append(rnd)
                score = 0
                state = UNTRUSTED
    refused.sort()
    return {"reliance": tuple(reliance), "final": state, "upgrades": upgrades,
            "upgraded": upgrades > 0, "accepted": tuple(accepted), "refused": tuple(refused)}


def resolve(snap, arm):
    """Resolve each pending decision at its deadline: a timely accepted
    'incorrect' for its round gives DO_NOT_RELY, else a timely accepted
    'correct' gives RELY, else its declared on_expiry."""
    out = []
    for pid, rnd, deadline, on_expiry in snap["pending"]:
        timely = {CORRECT: [], INCORRECT: []}
        for i, graded, outcome in arm["accepted"]:
            at = snap["feedback"][i][3]
            if graded == rnd and at <= deadline:
                timely[outcome].append(at)
        if timely[INCORRECT]:
            out.append((pid, DO_NOT_RELY, min(timely[INCORRECT])))
        elif timely[CORRECT]:
            out.append((pid, RELY, min(timely[CORRECT])))
        else:
            out.append((pid, on_expiry, deadline))
    return tuple(out)


def baseline(snap):
    """Persuadable baseline: starts high, rises with confidence, falls on any 'incorrect'."""
    level = BASE_START
    reliance = []
    for k in range(1, snap["rounds"] + 1):
        reliance.append(RELY if level >= BASE_RELY else VERIFY)
        if snap["advice"][k - 1][1] >= BASE_CONFIDENT:
            level = min(BASE_TOP, level + 1)
        for ev in snap["feedback"]:
            if ev[3] == k and ev[4] == INCORRECT:
                level = 0
    return tuple(reliance)


def score(reliance, truth):
    """(rounds relied on wrong advice, rounds that verified right advice)."""
    wrong = sum(1 for r, t in zip(reliance, truth) if r == RELY and not t)
    cost = sum(1 for r, t in zip(reliance, truth) if r != RELY and t)
    return wrong, cost


def _run(snap):
    arm = rule(snap)
    base = baseline(snap)
    wrong, cost = score(arm["reliance"], snap["truth"])
    b_wrong, b_cost = score(base, snap["truth"])
    return {"status": OK, "detail": None, "case_id": snap["case_id"],
            "reliance": arm["reliance"], "final": arm["final"], "upgrades": arm["upgrades"],
            "upgraded": arm["upgraded"], "accepted": arm["accepted"],
            "refused": arm["refused"], "pending": resolve(snap, arm),
            "relied_wrong": wrong, "verified_right": cost,
            "baseline": {"reliance": base, "final_relied": base[-1] == RELY,
                         "relied_wrong": b_wrong, "verified_right": b_cost}}


FIELDS_OUT = ("case_id", "reliance", "final", "upgrades", "upgraded", "accepted", "refused",
              "pending", "relied_wrong", "verified_right", "baseline")


def _error(detail):
    rec = {"status": CONFIG_ERROR, "detail": detail}
    for f in FIELDS_OUT:
        rec[f] = None
    return rec


def evaluate(case):
    """Validate, snapshot and run one session. Never raises."""
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


def totals(records, groups):
    """Per group of case ids: how many sessions upgraded (config errors skipped)."""
    ok = dict((r["case_id"], r) for r in records if r["status"] == OK)
    out = {}
    for name, ids in groups:
        present = [c for c in ids if c in ok]
        out[name] = (sum(1 for c in present if ok[c]["upgraded"]), len(present))
    return out
