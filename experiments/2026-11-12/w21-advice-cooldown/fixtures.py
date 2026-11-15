"""Declared synthetic fixtures for w21-advice-cooldown.

All tools, contracts, advice items, histories and times are invented. The
expected outcome of each case is written by hand in the tables below, not
derived from the module under test.

Run: python3 fixtures.py   (prints the timeline table and one JSON line;
exits 1 if any case disagrees with its expected label)
"""

import json
import sys

import advice_cooldown as A

CONTRACTS = {
    "search": {"required": ["query"], "options": {"sort": ["price", "rating"]}},
    "checkout": {"required": ["item_id", "address"], "options": {"speed": ["standard", "express"]}},
}


def advice(i, tool, when_missing, args, tokens, cooldown):
    return {"id": i, "tool": tool, "when_missing": when_missing, "args": args,
            "tokens": tokens, "cooldown": cooldown}


def sort_hint():
    return advice("sort_hint", "search", "sort", {"sort": "price"}, 40, 3)


def bad_sort_hint():
    return advice("bad_sort_hint", "search", "sort", {"sort": "newest"}, 10, 3)


def speed_hint():
    return advice("speed_hint", "checkout", None, {"speed": "express"}, 20, 2)


def ship_hint():
    return advice("ship_hint", "ship", None, {"carrier": "post"}, 10, 2)


def state(tool, args, items, pending=None, contracts=None):
    s = {"tool": tool, "args": dict(args),
         "contracts": CONTRACTS if contracts is None else contracts, "advice": items}
    if pending is not None:
        s["pending"] = pending
    return s


def sent(i, at, tokens):
    return {"advice_id": i, "at": at, "tokens": tokens}


def budget(limit):
    return {"limit": limit}


SEARCH = {"query": "lamp"}

# name: (state, history, budget, now, expected (decision, reason, sent))
DESIGN = {
    "first_send": (state("search", SEARCH, [sort_hint()]), [], budget(100), 0,
                   (A.SEND, A.SENT, "sort_hint")),
    "repeat_in_cooldown": (state("search", SEARCH, [sort_hint()]), [sent("sort_hint", 0, 40)],
                           budget(100), 2, (A.NO_SEND, A.IN_COOLDOWN, None)),
    "after_cooldown": (state("search", SEARCH, [sort_hint()]), [sent("sort_hint", 0, 40)],
                       budget(100), 3, (A.SEND, A.SENT, "sort_hint")),
    "required_arg_missing": (state("checkout", {"address": "home"}, [speed_hint()]), [], budget(100),
                             0, (A.NO_SEND, A.REQUIRED_ARG_MISSING, None)),
    "invalid_option": (state("search", SEARCH, [bad_sort_hint()]), [], budget(100), 0,
                       (A.NO_SEND, A.INVALID_OPTION, None)),
    "budget_short": (state("search", SEARCH, [sort_hint()]), [], budget(30), 0,
                     (A.NO_SEND, A.BUDGET_EXHAUSTED, None)),
    "budget_spent": (state("search", SEARCH, [sort_hint()]), [sent("other", 0, 70)], budget(100), 9,
                     (A.NO_SEND, A.BUDGET_EXHAUSTED, None)),
    "budget_zero": (state("search", SEARCH, [sort_hint()]), [], budget(0), 0,
                    (A.NO_SEND, A.BUDGET_EXHAUSTED, None)),
    "no_contract": (state("ship", {"to": "x"}, [ship_hint()]), [], budget(100), 0,
                    (A.NO_SEND, A.NO_CONTRACT, None)),
    "no_candidate": (state("search", {"query": "lamp", "sort": "rating"}, [sort_hint()]), [],
                     budget(100), 0, (A.NO_SEND, A.NO_CANDIDATE, None)),
    "fallback_second": (state("search", SEARCH, [bad_sort_hint(), sort_hint()]), [], budget(100), 0,
                        (A.SEND, A.SENT, "sort_hint")),
    "checkout_ok": (state("checkout", {"item_id": "i1", "address": "home"}, [speed_hint()]), [],
                    budget(100), 0, (A.SEND, A.SENT, "speed_hint")),
    "pending_expired": (state("search", SEARCH, [sort_hint()],
                              {"id": "p1", "deadline": 5, "on_expiry": "HOLD"}), [], budget(100), 6,
                        (A.HOLD, A.EXPIRED, None)),
    "pending_open": (state("search", SEARCH, [sort_hint()],
                           {"id": "p1", "deadline": 5, "on_expiry": "DENY"}), [], budget(100), 4,
                     (A.SEND, A.SENT, "sort_hint")),
    "pending_at_deadline": (state("search", SEARCH, [sort_hint()],
                                  {"id": "p1", "deadline": 5, "on_expiry": "ESCALATE"}), [],
                            budget(100), 5, (A.ESCALATE, A.EXPIRED, None)),
}

# A declared timeline: the same search state at ticks 0..9, budget 120,
# sort_hint costs 40 with cooldown 3. Hand-written expected outcome per tick.
TIMELINE_BUDGET = 120
TIMELINE_EXPECT = (A.SENT, A.IN_COOLDOWN, A.IN_COOLDOWN, A.SENT, A.IN_COOLDOWN, A.IN_COOLDOWN,
                   A.SENT, A.IN_COOLDOWN, A.IN_COOLDOWN, A.BUDGET_EXHAUSTED)


def run_timeline():
    """Run the finite declared timeline; returns (reasons, history). No clock is read."""
    history = []
    reasons = []
    for now in range(len(TIMELINE_EXPECT)):
        rec = A.select_advice(state("search", SEARCH, [sort_hint()]), list(history),
                              budget(TIMELINE_BUDGET), now)
        reasons.append(rec["reason"])
        if rec["decision"] == A.SEND:
            history.append(sent(rec["sent"], now, rec["tokens"]))
    return tuple(reasons), history


def check(out=print):
    bad = 0
    for name in sorted(DESIGN):
        s, h, b, now, want = DESIGN[name]
        rec = A.select_advice(s, h, b, now)
        got = (rec["decision"], rec["reason"], rec["sent"])
        if got != want:
            bad += 1
            out("design mismatch %s: %r != %r" % (name, got, want))
    reasons, _ = run_timeline()
    if reasons != TIMELINE_EXPECT:
        bad += 1
        out("timeline mismatch: %r" % (reasons,))
    return bad


def main():
    bad = check()
    reasons, history = run_timeline()
    print("%-5s %s" % ("tick", "outcome"))
    for now, r in enumerate(reasons):
        print("%-5d %s" % (now, r))
    summary = {"sent": reasons.count(A.SENT), "in_cooldown": reasons.count(A.IN_COOLDOWN),
               "budget_exhausted": reasons.count(A.BUDGET_EXHAUSTED),
               "tokens": sum(e["tokens"] for e in history), "budget": TIMELINE_BUDGET,
               "mismatches": bad}
    print(json.dumps(summary, sort_keys=True))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
