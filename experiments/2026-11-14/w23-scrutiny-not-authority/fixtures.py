"""Frozen synthetic fixtures for w23-scrutiny-not-authority.

Every conclusion, self-assessment, check and label here is hand-written
test data. GOLD (sound / unsound) is a FIXTURE LABEL: the fixture author's
statement of whether the conclusion is correct, never shown to an arm.
LABELS holds, per case, the planted kind and the hand-written expected
decisions of the four arms. Independent checks in this world are truthful
except in the two conflict cases, where one independent check is wrong by
construction. Nothing here comes from the paper.

Run: python3 -B fixtures.py   (prints one row per case and the counts)
"""

import copy

import scrutiny_not_authority as M
import oracle as O


def K(cid, source, basis, verdict):
    return {"check_id": cid, "source": source, "basis": basis, "verdict": verdict}


def C(cid, conclusion, assessment, checks):
    return {"case_id": cid, "conclusion": conclusion, "self_assessment": assessment,
            "checks": checks}


OWN = "own_evidence"
FROM_SELF = "self_assessment"

CASES = {
    # Self-assessment ok.
    "ok-sound-plain": C(
        "ok-sound-plain", "The config file sets retries to three.", "ok", []),
    "ok-sound-tested": C(
        "ok-sound-tested", "The parser rejects an empty header.", "ok",
        [K("t1", "fixture_test", OWN, "supports")]),
    "ok-unsound-refuted": C(
        "ok-unsound-refuted", "The invoice was paid on Monday.", "ok",
        [K("w1", "world_record", OWN, "refutes")]),
    "ok-unsound-missed": C(
        "ok-unsound-missed", "The cache is cleared on restart.", "ok", []),
    "ok-unsound-conflict": C(
        "ok-unsound-conflict", "The backup finished before midnight.", "ok",
        [K("w1", "world_record", OWN, "refutes"), K("t1", "fixture_test", OWN, "supports")]),
    # Self-assessment defective, and wrong (the noisy rating).
    "def-sound-unchecked": C(
        "def-sound-unchecked", "The meeting moved to Thursday.", "defective", []),
    "def-sound-cleared": C(
        "def-sound-cleared", "The function returns a sorted list.", "defective",
        [K("t1", "fixture_test", OWN, "supports")]),
    "def-sound-self-recheck": C(
        "def-sound-self-recheck", "The order shipped to the second address.", "defective",
        [K("s1", "self", OWN, "refutes")]),
    "def-sound-laundered": C(
        "def-sound-laundered", "The patch fixes the off-by-one error.", "defective",
        [K("x1", "external_derivation", FROM_SELF, "refutes")]),
    "def-sound-conflict": C(
        "def-sound-conflict", "The two totals are equal.", "defective",
        [K("t1", "fixture_test", OWN, "supports"),
         K("x1", "external_derivation", OWN, "refutes")]),
    "def-sound-world": C(
        "def-sound-world", "The ticket was closed by the owner.", "defective",
        [K("w1", "world_record", OWN, "supports"), K("s1", "self", OWN, "refutes")]),
    # Self-assessment defective, and right.
    "def-unsound-refuted": C(
        "def-unsound-refuted", "The user asked for a refund.", "defective",
        [K("w1", "world_record", OWN, "refutes")]),
    "def-unsound-derived": C(
        "def-unsound-derived", "The sum of the column is forty.", "defective",
        [K("s1", "self", OWN, "refutes"), K("x1", "external_derivation", OWN, "refutes")]),
    "def-unsound-unchecked": C(
        "def-unsound-unchecked", "The flight lands at gate nine.", "defective", []),
    "def-unsound-not-run": C(
        "def-unsound-not-run", "The migration is reversible.", "defective",
        [K("t1", "fixture_test", OWN, "not_run")]),
}

# name: (gold, planted kind, baseline, rule, agree_flip, agree_silence)
LABELS = {
    "ok-sound-plain": ("sound", "control", "RETAIN", "RETAIN", "RETAIN", "RETAIN"),
    "ok-sound-tested": ("sound", "control", "RETAIN", "RETAIN", "RETAIN", "RETAIN"),
    "ok-unsound-refuted": ("unsound", "independent_refutation", "ELIMINATE", "ELIMINATE",
                           "ELIMINATE", "ELIMINATE"),
    "ok-unsound-missed": ("unsound", "missed_by_both", "RETAIN", "RETAIN", "RETAIN", "RETAIN"),
    "ok-unsound-conflict": ("unsound", "conflict", "HOLD", "HOLD", "HOLD", "HOLD"),
    "def-sound-unchecked": ("sound", "noisy_rating", "ELIMINATE", "HOLD", "NEGATE", "RETAIN"),
    "def-sound-cleared": ("sound", "noisy_rating", "ELIMINATE", "RETAIN", "NEGATE", "RETAIN"),
    "def-sound-self-recheck": ("sound", "self_check_only", "ELIMINATE", "HOLD", "NEGATE",
                               "RETAIN"),
    "def-sound-laundered": ("sound", "laundered_check", "ELIMINATE", "HOLD", "NEGATE",
                            "RETAIN"),
    "def-sound-conflict": ("sound", "conflict", "ELIMINATE", "HOLD", "NEGATE", "HOLD"),
    "def-sound-world": ("sound", "noisy_rating", "ELIMINATE", "RETAIN", "NEGATE", "RETAIN"),
    "def-unsound-refuted": ("unsound", "independent_refutation", "ELIMINATE", "ELIMINATE",
                            "NEGATE", "ELIMINATE"),
    "def-unsound-derived": ("unsound", "independent_refutation", "ELIMINATE", "ELIMINATE",
                            "NEGATE", "ELIMINATE"),
    "def-unsound-unchecked": ("unsound", "missing_check", "ELIMINATE", "HOLD", "NEGATE",
                              "RETAIN"),
    "def-unsound-not-run": ("unsound", "missing_check", "ELIMINATE", "HOLD", "NEGATE",
                            "RETAIN"),
}

# Elimination requests: name -> (case, cite, expected decision).
REQUESTS = {
    "Q1-self-assessment-only": ("def-unsound-unchecked", ["self_assessment"], "REFUSE"),
    "Q2-self-recheck": ("def-sound-self-recheck", ["self_assessment", "s1"], "REFUSE"),
    "Q3-laundered": ("def-sound-laundered", ["x1"], "REFUSE"),
    "Q4-not-run": ("def-unsound-not-run", ["self_assessment", "t1"], "REFUSE"),
    "Q5-cherry-pick": ("def-sound-conflict", ["x1"], "REFUSE"),
    "Q6-supporting-check": ("def-sound-cleared", ["t1"], "REFUSE"),
    "Q7-independent-refutation": ("def-unsound-refuted", ["w1"], "PERMIT"),
    "Q8-independent-beside-self": ("def-unsound-derived", ["s1", "x1"], "PERMIT"),
    "Q9-ok-rated-refuted": ("ok-unsound-refuted", ["w1"], "PERMIT"),
}

NOISY_RATING = ("def-sound-unchecked", "def-sound-cleared",
                "def-sound-self-recheck", "def-sound-laundered",
                "def-sound-conflict", "def-sound-world")


def cases():
    """A fresh deep copy of the fixture cases."""
    return copy.deepcopy(CASES)


def gold():
    return dict((n, lab[0]) for n, lab in LABELS.items())


def requests():
    return copy.deepcopy(REQUESTS)


def run_all():
    """Decide every case with the module and the oracle."""
    rows = {}
    for name, case in cases().items():
        rows[name] = (M.evaluate(case), O.reference(copy.deepcopy(case)))
    return rows


def frac(k, n):
    return "%d/%d" % (k, n)


def summary():
    rows = run_all()
    recs = [m for m, _ in rows.values()]
    sc = M.score(recs, gold())
    oracle_ok = sum(1 for m, o in rows.values()
                    if (m["outcome"], m["baseline"]["decision"], m["rule"]["decision"],
                        m["rule"]["flagged"], m["rule"]["basis"],
                        m["agree_flip"]["decision"], m["agree_silence"]["decision"])
                    == (o["outcome"], o["baseline"], o["rule"], o["flagged"], o["basis"],
                        o["agree_flip"], o["agree_silence"]))
    reqs = requests()
    gate_ok = sum(1 for name, (cn, cite, want) in reqs.items()
                  if M.request_elimination(cases()[cn], cite)["decision"] == want
                  and O.gate(cases()[cn], cite) == want)
    lines = ["%-24s %-8s %-10s %-10s %-10s %-10s %-9s" % (
        "case", "gold", "outcome", "baseline", "rule", "flip", "silence")]
    for name, (m, _) in rows.items():
        lines.append("%-24s %-8s %-10s %-10s %-10s %-10s %-9s" % (
            name, LABELS[name][0], m["outcome"], m["baseline"]["decision"],
            m["rule"]["decision"] + ("*" if m["rule"]["flagged"] else ""),
            m["agree_flip"]["decision"], m["agree_silence"]["decision"]))
    b, r, f, s = (sc[a] for a in M.ARMS)
    n = b["n"]
    lines += [
        "cases: %d (sound %d, unsound %d; defective rating on %d)"
        % (n, b["sound"], b["unsound"],
           sum(1 for m in recs if m["self_assessment"] == M.DEFECTIVE)),
        "* = flagged for scrutiny by a defective self-assessment",
    ]
    for name, x in (("baseline", b), ("rule", r), ("agree_flip", f), ("agree_silence", s)):
        lines.append(
            "%s: sound lost %s, unsound eliminated %s, unsound held %d, false held"
            " unflagged %d, eliminations without independent refutation %d, coherent %s"
            % (name, frac(x["sound_lost"], x["sound"]),
               frac(x["unsound_eliminated"], x["unsound"]), x["unsound_held"],
               x["false_held_unflagged"], x["eliminated_unbacked"], frac(x["coherent"], n)))
    lines += [
        "elimination requests: %d/%d decided as labelled" % (gate_ok, len(reqs)),
        "module vs oracle: %d/%d cases agree" % (oracle_ok, len(rows)),
    ]
    return "\n".join(line.rstrip() for line in lines)


if __name__ == "__main__":
    print(summary())
