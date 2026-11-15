"""Independent reference for trust_feedback (a separate code path).

It imports nothing, shares no function name with the module and does not
validate input (it assumes a well-formed case). It is written from the
declared contract, not from the module's code:

- fate: one pass over the events sorted by arrival round (stable), a table
  of named checks; the replay check is a set of exact-event keys (source,
  advisor_id, graded round, outcome), so only a repeat of the same event is
  a duplicate;
- trust: per arrival round, set algebra over the accepted events of that
  round: the graded rounds of its "correct" events, minus every round that
  has already counted or been refuted, add to the score; then any
  "incorrect" in that round resets the score and trust, and its rounds are
  refuted for good;
- pending: the timely accepted events for the decision's round ranked by
  (outcome is "correct", arrival), so any "incorrect" outranks every
  "correct" and the earliest arrival breaks ties;
- baseline: a running level clipped by min/max.
"""


def _fate(case):
    """Map event index -> refusal reason or None, in arrival order."""
    n = case["rounds"]
    me = case["advisor_id"]
    order = sorted(range(len(case["feedback"])), key=lambda j: case["feedback"][j]["at"])
    taken = set()
    fate = {}
    for j in order:
        ev = case["feedback"][j]
        src = ev["source"]
        age = ev["at"] - ev["round"]
        sig = (src, ev["advisor_id"], ev["round"], ev["outcome"])
        checks = [
            ("self_sourced", src in (me, ev["advisor_id"])),
            ("not_external", src not in case["external_sources"]),
            ("advisor_mismatch", ev["advisor_id"] != me),
            ("no_such_round", not (1 <= ev["round"] <= n)),
            ("future_round", age < 0),
            ("stale", age > case["max_age"]),
            ("duplicate", sig in taken),
        ]
        why = None
        for name, bad in checks:
            if bad:
                why = name
                break
        if why is None:
            taken.add(sig)
        fate[j] = why
    return order, fate


def reference(case):
    """Return the module's record for a well-formed case, computed apart."""
    n = case["rounds"]
    order, fate = _fate(case)
    good = [j for j in order if fate[j] is None]
    trusted = False
    pts = 0
    ups = 0
    rel = []
    spent = set()
    for k in range(1, n + 1):
        rel.append("RELY" if trusted else "VERIFY")
        now = [case["feedback"][j] for j in good if case["feedback"][j]["at"] == k]
        plus = set(e["round"] for e in now if e["outcome"] == "correct") - spent
        minus = set(e["round"] for e in now if e["outcome"] == "incorrect")
        if not trusted and pts + len(plus) >= case["trust_bar"]:
            trusted = True
            ups = ups + 1
        pts = pts + len(plus)
        if minus:
            pts = 0
            trusted = False
        spent = spent | plus | minus
    acc = tuple((j, case["feedback"][j]["round"], case["feedback"][j]["outcome"]) for j in good)
    ref = tuple(sorted((j, fate[j]) for j in fate if fate[j] is not None))
    pend = []
    for p in case["pending"]:
        timely = [case["feedback"][j] for j in good
                  if case["feedback"][j]["round"] == p["round"]
                  and case["feedback"][j]["at"] <= p["deadline"]]
        if not timely:
            pend.append((p["pending_id"], p["on_expiry"], p["deadline"]))
            continue
        top = min(timely, key=lambda e: (e["outcome"] == "correct", e["at"]))
        pend.append((p["pending_id"],
                     "DO_NOT_RELY" if top["outcome"] == "incorrect" else "RELY", top["at"]))
    lvl = 2
    base = []
    for k in range(1, n + 1):
        base.append("RELY" if lvl > 1 else "VERIFY")
        if not case["advice"][k - 1]["confidence"] < 0.5:
            lvl = max(min(lvl + 1, 3), 0)
        if any(ev["at"] == k and ev["outcome"] == "incorrect" for ev in case["feedback"]):
            lvl = 0
    truth = case["truth"]

    def tally(r):
        w = 0
        c = 0
        for idx in range(n):
            if r[idx] == "RELY" and truth[idx] is False:
                w += 1
            if r[idx] == "VERIFY" and truth[idx] is True:
                c += 1
        return w, c

    w, c = tally(rel)
    bw, bc = tally(base)
    return {"status": "ok", "detail": None, "case_id": case["case_id"],
            "reliance": tuple(rel), "final": "trusted" if trusted else "untrusted",
            "upgrades": ups, "upgraded": ups > 0, "accepted": acc, "refused": ref,
            "pending": tuple(pend), "relied_wrong": w, "verified_right": c,
            "baseline": {"reliance": tuple(base), "final_relied": base[-1] == "RELY",
                         "relied_wrong": bw, "verified_right": bc}}
