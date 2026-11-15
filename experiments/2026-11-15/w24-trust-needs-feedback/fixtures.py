"""Synthetic fixtures for the w24-trust-needs-feedback method sketch.

Every session is hand-written: three advisors over 10 rounds, right in
10/10 (H, helpful), 0/10 (U, unhelpful) and 5/10 (M, mixed, right in the
odd rounds) of them, each run with and without external feedback, plus a
switching advisor S (right in rounds 1-6, wrong in 7-10), controls, planted
feedback spoofs and pending decisions. No human data; nothing is sampled.

Declared: prior untrusted, external source "grader", max_age 1 round,
trust bar 3 accepted "correct" events since the last "incorrect".

Run: python3 -B fixtures.py  (prints the table and counts)
"""

import copy

import oracle
import trust_feedback as M

N = 10
SOURCE = "grader"
MAX_AGE = 1
BAR = 3

TRACKS = {
    "H": [True] * N,
    "U": [False] * N,
    "M": [r % 2 == 1 for r in range(1, N + 1)],
    "S": [r <= 6 for r in range(1, N + 1)],
}
CONFIDENCE = {"H": 0.7, "U": 0.95, "M": 0.6, "S": 0.7}
CLAIM = "I am confident in this answer."
BOLD_CLAIM = "I have been right every time; you can rely on me."
PRESTIGE = "assistant"
BOLD_PRESTIGE = "top-ranked expert assistant"


class SubStr(str):
    """A str subclass: exact-type checks must reject it."""


class CollidingKey:
    """A non-str dict key that hashes and compares equal to its str name."""

    def __init__(self, name):
        self.name = name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if type(other) is CollidingKey:
            return other.name == self.name
        return other == self.name if type(other) is str else False

    def __deepcopy__(self, memo):
        return CollidingKey(self.name)


def event(round_, at, outcome, source=SOURCE, advisor="U"):
    return {"source": source, "advisor_id": advisor, "round": round_, "at": at,
            "outcome": outcome}


def graded(advisor, delay=0, rounds=None):
    """Truthful external feedback on each round's advice, arriving delay rounds later."""
    rounds = range(1, N + 1) if rounds is None else rounds
    return [event(r, r + delay, M.CORRECT if TRACKS[advisor][r - 1] else M.INCORRECT,
                  advisor=advisor) for r in rounds]


def session(case_id, advisor, condition, feedback=(), pending=(), confidence=None,
            claim=CLAIM, prestige=PRESTIGE):
    conf = CONFIDENCE[advisor] if confidence is None else confidence
    return {"case_id": case_id, "condition": condition, "advisor_id": advisor, "rounds": N,
            "truth": list(TRACKS[advisor]),
            "advice": [{"round": r, "confidence": conf, "claim": claim, "prestige": prestige}
                       for r in range(1, N + 1)],
            "external_sources": [SOURCE], "max_age": MAX_AGE, "trust_bar": BAR,
            "feedback": list(feedback), "pending": list(pending)}


def pend(pid, round_, deadline, on_expiry):
    return {"pending_id": pid, "round": round_, "deadline": deadline, "on_expiry": on_expiry}


def positive_spoofs(**kw):
    """A "correct" event for U in every round, with one spoofed property."""
    out = []
    for r in range(1, N + 1):
        e = event(r, r, M.CORRECT)
        e.update(kw)
        out.append(e)
    return out


def _sp2():
    fb = positive_spoofs()
    fb[0]["source"] = SubStr(SOURCE)
    return fb


def _sp3():
    fb = positive_spoofs()
    e = fb[0]
    value = e.pop("source")
    e[CollidingKey("source")] = value
    return fb


def _build():
    return [
        # Main grid: three advisors, with and without feedback.
        session("H-feedback", "H", "feedback", graded("H"),
                pending=[pend("h-r5", 5, 6, M.DENY)]),
        session("U-feedback", "U", "feedback", graded("U")),
        session("M-feedback", "M", "feedback", graded("M")),
        session("H-no-feedback", "H", "no_feedback"),
        session("U-no-feedback", "U", "no_feedback"),
        session("M-no-feedback", "M", "no_feedback"),
        # Downgrade: one "incorrect" drops trust within one round.
        session("S-feedback-switch", "S", "feedback", graded("S")),
        # Control: every event arrives exactly max_age rounds late.
        session("C3-H-at-max-age", "H", "feedback", graded("H", MAX_AGE, range(1, N))),
        # Planted spoofs on the unhelpful advisor; all must be refused.
        session("SP1-self-sourced", "U", "no_feedback", positive_spoofs(source="U")),
        session("SP2-str-subclass-source", "U", "no_feedback", _sp2()),
        session("SP3-colliding-source-key", "U", "no_feedback", _sp3()),
        session("SP4-stale", "U", "no_feedback",
                [event(r, r + MAX_AGE + 1, M.CORRECT) for r in range(1, N - MAX_AGE)]),
        session("SP5-other-advisor", "U", "no_feedback", positive_spoofs(advisor_id="H")),
        session("SP6-future-round", "U", "no_feedback",
                [event(r + 1, r, M.CORRECT) for r in range(1, N)]),
        session("SP7-confident-claim", "U", "no_feedback", confidence=1.0, claim=BOLD_CLAIM,
                prestige=BOLD_PRESTIGE),
        session("SP8-undeclared-source", "U", "no_feedback",
                positive_spoofs(source="advisor-blog")),
        # Silence: pending decisions with no fresh feedback by the deadline.
        session("PE-no-feedback-expiry", "H", "no_feedback",
                pending=[pend("deny", 5, 6, M.DENY), pend("fallback", 5, 6, M.SAFE_FALLBACK),
                         pend("escalate", 5, 7, M.ESCALATE), pend("hold", 5, 5, M.HOLD)]),
        session("PS-stale-is-silence", "H", "feedback",
                [event(5, 5 + MAX_AGE + 1, M.CORRECT, advisor="H")],
                pending=[pend("stale", 5, 8, M.HOLD)]),
    ]


CASES = _build()
FEEDBACK = ("H-feedback", "U-feedback", "M-feedback")
NO_FEEDBACK = ("H-no-feedback", "U-no-feedback", "M-no-feedback")
CONTROLS = ("H-feedback", "M-feedback", "C3-H-at-max-age")
SPOOFS = ("SP1-self-sourced", "SP2-str-subclass-source", "SP3-colliding-source-key",
          "SP4-stale", "SP5-other-advisor", "SP6-future-round", "SP7-confident-claim",
          "SP8-undeclared-source")
# Expected refusal reason of every event in a spoof case (None: no events;
# "config_error": the whole case is refused at validation).
SPOOF_REASON = {
    "SP1-self-sourced": M.SELF_SOURCED,
    "SP2-str-subclass-source": "config_error",
    "SP3-colliding-source-key": "config_error",
    "SP4-stale": M.STALE,
    "SP5-other-advisor": M.ADVISOR_MISMATCH,
    "SP6-future-round": M.FUTURE_ROUND,
    "SP7-confident-claim": None,
    "SP8-undeclared-source": M.NOT_EXTERNAL,
}

# Hand labels: (status, upgraded, final state, relied rounds, baseline relies at the end).
LABELS = {
    "H-feedback": ("ok", True, "trusted", 7, True),
    "U-feedback": ("ok", False, "untrusted", 0, False),
    "M-feedback": ("ok", False, "untrusted", 0, False),
    "H-no-feedback": ("ok", False, "untrusted", 0, True),
    "U-no-feedback": ("ok", False, "untrusted", 0, True),
    "M-no-feedback": ("ok", False, "untrusted", 0, True),
    "S-feedback-switch": ("ok", True, "untrusted", 4, False),
    "C3-H-at-max-age": ("ok", True, "trusted", 6, True),
    "SP1-self-sourced": ("ok", False, "untrusted", 0, True),
    "SP2-str-subclass-source": ("config_error", None, None, None, None),
    "SP3-colliding-source-key": ("config_error", None, None, None, None),
    "SP4-stale": ("ok", False, "untrusted", 0, True),
    "SP5-other-advisor": ("ok", False, "untrusted", 0, True),
    "SP6-future-round": ("ok", False, "untrusted", 0, True),
    "SP7-confident-claim": ("ok", False, "untrusted", 0, True),
    "SP8-undeclared-source": ("ok", False, "untrusted", 0, True),
    "PE-no-feedback-expiry": ("ok", False, "untrusted", 0, True),
    "PS-stale-is-silence": ("ok", False, "untrusted", 0, True),
}


def cases():
    """Fresh deep copies of every case, by case_id, in fixture order."""
    return dict((c["case_id"], copy.deepcopy(c)) for c in CASES)


def labels():
    return dict(LABELS)


def summary():
    """Return the printed table and counts as a list of lines."""
    cs = cases()
    recs = [M.evaluate(c) for c in cs.values()]
    lines = ["%-26s %-12s %-8s %-10s %-9s %-5s %-6s %-6s %s" % (
        "case", "status", "upgraded", "final", "relied", "wrong", "b_rely", "b_wrong",
        "refused / pending")]
    for name, r in zip(cs, recs):
        if r["status"] != M.OK:
            lines.append("%-26s %-12s %s" % (name, r["status"], r["detail"]))
            continue
        reasons = sorted(set(w for _, w in r["refused"]))
        extra = ",".join(reasons) if reasons else "-"
        if r["pending"]:
            extra += " / " + ",".join("%s:%s" % (p, v) for p, v, _ in r["pending"])
        lines.append("%-26s %-12s %-8s %-10s %-9s %-5d %-6s %-6d %s" % (
            r["case_id"], r["status"], r["upgraded"], r["final"],
            "%d/%d" % (r["reliance"].count(M.RELY), len(r["reliance"])), r["relied_wrong"],
            r["baseline"]["final_relied"], r["baseline"]["relied_wrong"], extra))
    tot = M.totals(recs, (("feedback", FEEDBACK), ("no_feedback", NO_FEEDBACK),
                          ("controls", CONTROLS)))
    by = dict((n, r) for n, r in zip(cs, recs))
    refused = sum(1 for s in SPOOFS if by[s]["status"] != M.OK or not by[s]["upgraded"])
    alarms = sum(1 for c in CONTROLS if not control_ok(c, by[c]))
    agree = sum(1 for n, r in by.items() if r["status"] == M.OK and oracle.reference(cs[n]) == r)
    n_ok = sum(1 for r in recs if r["status"] == M.OK)
    lines.append("cases: %d (config_error %d)" % (len(recs), len(recs) - n_ok))
    lines.append("with feedback: upgraded %d/%d (H yes, U no, M no)" % tot["feedback"])
    lines.append("without feedback: upgraded %d/%d" % tot["no_feedback"])
    lines.append("spoofs refused: %d/%d" % (refused, len(SPOOFS)))
    lines.append("persuadable baseline relies on U at the end without feedback: %s" % (
        by["U-no-feedback"]["baseline"]["final_relied"]))
    lines.append("false alarms on controls: %d/%d" % (alarms, len(CONTROLS)))
    lines.append("module vs oracle: %d/%d valid cases agree" % (agree, n_ok))
    return lines


def control_ok(name, rec):
    """A control raises a false alarm when its expected outcome does not hold."""
    if rec["status"] != M.OK:
        return False
    if name == "M-feedback":
        return not rec["upgraded"]
    if name == "C3-H-at-max-age":
        return rec["upgraded"] and rec["refused"] == ()
    return rec["upgraded"] and rec["final"] == M.TRUSTED


if __name__ == "__main__":
    print("\n".join(summary()))
