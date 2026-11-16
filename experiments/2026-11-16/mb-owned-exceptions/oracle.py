"""Independent spec oracle for mb-owned-exceptions.

Written from the README's specification, not from owned_exceptions.py: it
imports only fractions and shares no function name or data structure with
the module. It holds no weights: a decision is the published rule with the
owned rows applied as predicates, and the gate threshold is computed from a
binomial probability mass built step by step.
"""

from fractions import Fraction

SUBJ = ["s0", "s1", "s2", "s3"]
KLASS = ["a", "b", "c"]
QMAX = 7
LIMIT1 = 5
LIMIT2 = 5
HOLDERS = {"p0": "s0", "p1": "s1", "p2": "s2", "p3": "s3"}
AREAS = ["all", "a", "b", "c"]
SIZES = {"q1_margin": [1, 2, 3], "q2_margin": [1, 2, 3],
         "sum_cap": [4, 5, 6, 7, 8, 9]}
MIN_GAIN = 5
NOISE = Fraction(1, 20)
LEVEL = Fraction(1, 20)


def universe():
    out = []
    for s in SUBJ:
        for k in KLASS:
            for u in range(QMAX + 1):
                for v in range(QMAX + 1):
                    out.append((s, k, u, v))
    return out


def rule(x):
    return int(x[2] <= LIMIT1 and x[3] <= LIMIT2)


def hits(row, x):
    subj, area, kind, amount = row
    if x[0] != subj:
        return False
    if area != "all" and area != x[1]:
        return False
    if kind == "q1_margin":
        return x[2] >= LIMIT1 - amount + 1
    if kind == "q2_margin":
        return x[3] >= LIMIT2 - amount + 1
    return x[2] + x[3] >= amount + 1


def verdict_for(x, rows):
    """Spec decision: the rule, then any owned row for x's subject rejects."""
    if not rule(x):
        return 0
    for _who, row in rows:
        if row[0] == x[0] and hits(row, x):
            return 0
    return 1


def all_verdicts(rows):
    return bytes(verdict_for(x, rows) for x in universe())


def catalogue(subj):
    out = []
    for area in AREAS:
        for kind in ("q1_margin", "q2_margin", "sum_cap"):
            for amount in SIZES[kind]:
                out.append((subj, area, kind, amount))
    return out


_SEEN = {}


def needed(n):
    """Least c >= 1 with |H| * P[Bin(n, NOISE) >= c] <= LEVEL, else None."""
    if n not in _SEEN:
        _SEEN[n] = _needed(n)
    return _SEEN[n]


def _needed(n):
    pmf = [Fraction(1)]
    for _ in range(n):
        nxt = [Fraction(0)] * (len(pmf) + 1)
        for j, p in enumerate(pmf):
            nxt[j] += p * (1 - NOISE)
            nxt[j + 1] += p * NOISE
        pmf = nxt
    width = len(catalogue("s0"))
    upper = Fraction(0)
    tails = [Fraction(0)] * (n + 2)
    for j in range(n, -1, -1):
        upper += pmf[j]
        tails[j] = upper
    for c in range(1, n + 1):
        if width * tails[c] <= LEVEL:
            return c
    return None


def tally(row, recs):
    fixed = 0
    broken = 0
    for x, y in recs:
        old = rule(x)
        new = 0 if hits(row, x) else old
        if new != old:
            if new == y:
                fixed += 1
            else:
                broken += 1
    return fixed, broken


def _plain(v, typ):
    return type(v) is typ


def _rec_ok(r):
    if not _plain(r, dict) or not all(_plain(k, str) for k in r):
        return None
    if sorted(r) != ["item", "label"]:
        return None
    it = r["item"]
    if not _plain(it, dict) or not all(_plain(k, str) for k in it):
        return None
    if sorted(it) != ["cls", "q1", "q2", "subject"]:
        return None
    s, k, u, v = it["subject"], it["cls"], it["q1"], it["q2"]
    if not (_plain(s, str) and s in SUBJ and _plain(k, str) and k in KLASS):
        return None
    if not (_plain(u, int) and 0 <= u <= QMAX and _plain(v, int)
            and 0 <= v <= QMAX):
        return None
    y = r["label"]
    if not (_plain(y, int) and y in (0, 1)):
        return None
    return ((s, k, u, v), y)


def _row_ok(d):
    if not _plain(d, dict) or not all(_plain(k, str) for k in d):
        return None
    if sorted(d) != ["form", "scope", "size", "subject"]:
        return None
    s, a, f, z = d["subject"], d["scope"], d["form"], d["size"]
    if not (_plain(s, str) and s in SUBJ and _plain(a, str) and a in AREAS):
        return None
    if not (_plain(f, str) and f in SIZES):
        return None
    if not (_plain(z, int) and z in SIZES[f]):
        return None
    return (s, a, f, z)


def judge(rows, sub):
    """Spec acceptance: (status, reason) for a submission against rows."""
    bad = ("config_error", None)
    if not _plain(sub, dict) or not all(_plain(k, str) for k in sub):
        return bad
    ks = set(sub)
    if not {"owner", "declaration"} <= ks:
        return bad
    if not ks <= {"owner", "declaration", "claimed", "evidence"}:
        return bad
    who = sub["owner"]
    if not _plain(who, str):
        return bad
    row = _row_ok(sub["declaration"])
    if row is None:
        return bad
    claim = None
    if "claimed" in sub:
        c = sub["claimed"]
        if not _plain(c, dict) or not all(_plain(k, str) for k in c):
            return bad
        if sorted(c) != ["a", "b"]:
            return bad
        if not all(_plain(c[k], int) and 0 <= c[k] <= 10 ** 9
                   for k in ("a", "b")):
            return bad
        claim = (c["a"], c["b"])
    recs = None
    if "evidence" in sub:
        ev = sub["evidence"]
        if not _plain(ev, list):
            return bad
        recs = []
        for r in ev:
            got = _rec_ok(r)
            if got is None:
                return bad
            recs.append(got)
    if who not in HOLDERS:
        return ("REFUSE", "unknown_owner")
    if HOLDERS[who] != row[0]:
        return ("REFUSE", "not_owner")
    if claim is None or recs is None:
        return ("REFUSE", "ungated")
    t = tally(row, recs)
    if t != claim:
        return ("REFUSE", "gate_unreproduced")
    c = needed(len(recs))
    if c is None or t[0] - t[1] < max(MIN_GAIN, c):
        return ("REFUSE", "gate_failed")
    if any(w == who for w, _ in rows):
        return ("REFUSE", "slot_taken")
    return ("ADMIT", "admitted")


def judge_withdraw(rows, actor, holder):
    if not _plain(actor, str) or not _plain(holder, str):
        return ("config_error", None)
    if actor not in HOLDERS or holder not in HOLDERS:
        return ("REFUSE", "unknown_owner")
    if actor != holder:
        return ("REFUSE", "not_owner")
    if not any(w == holder for w, _ in rows):
        return ("REFUSE", "no_live_exception")
    return ("WITHDRAWN", "withdrawn")
