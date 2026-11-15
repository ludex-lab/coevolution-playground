"""Fixtures for w20-fidelity-audit. Run: python3 fixtures.py

DESIGN: hand-written cases used while writing the check layer, including
one with the shape of the paper's example (an ambiguous claim cut into two
readings; the tools prove the first and refute the second), built on toy
integer identities. The paper's own example is not reproduced.

SCENARIOS: a seeded scenario test over seeds 4101-4112. Each seed draws a
list of scenario labels; the expected (status, reason) of every target
comes from the label table below, decided before any record is built.
Records are then written to realise the label, with random toy
identities, ranges, ids, times and on_expiry values. The seeds vary the
records; they add no evidence beyond the labels themselves, so every
adversarial world the audit must hold against is a label of its own.
"""

import random
import sys

import fidelity_audit as F

C, Ar, V, T, S, St, Case = (F.Claim, F.Artefact, F.FidelityVerdict, F.HumanToken,
                            F.SplitRecord, F.Step, F.Case)

TRUE_PAIRS = (("sum_to_n", "tri"), ("sum_odd_first_n", "square"), ("sum_cubes", "tri_squared"),
              ("sum_even_first_n", "n_times_n_plus_1"), ("twice_n", "n_plus_n"))
FALSE_PAIRS = (("sum_odd_le_n", "square"), ("sum_to_n", "square"), ("twice_n", "square"),
               ("sum_cubes", "square"), ("sum_even_first_n", "square"))
TRAP_PAIR = ("square", "square_wobble")


def cfg(on_expiry=F.HOLD, deadline=10, required=(F.ENUMERATE,)):
    return F.AuditConfig(on_expiry, deadline, required)


class _B:
    """Small builder: every record it adds gets a dialog step."""

    def __init__(self, tag):
        self.tag, self.n = tag, 0
        self.claims, self.arts, self.res, self.ver, self.tok, self.spl, self.steps = ([] for _ in range(7))
        self.by_id = {}

    def _id(self, kind):
        self.n += 1
        return "%s-%s%d" % (self.tag, kind, self.n)

    def step(self, actor, action, ref=""):
        self.steps.append(St(self._id("s"), actor, action, ref))

    def claim(self, statement, ambiguous=False):
        c = C(self._id("c"), statement, ambiguous)
        self.claims.append(c)
        self.step(F.HUMAN, "states claim", c.claim_id)
        return c.claim_id

    def art(self, cid, rid, content, actor=F.AI):
        a = Ar(self._id("a"), cid, rid, content)
        self.arts.append(a)
        self.by_id[a.artefact_id] = a
        self.step(actor, "drafts artefact", a.artefact_id)
        return a

    def tool(self, tool, a, content_seen=None, actor=F.TOOL):
        seen = a if content_seen is None else Ar(a.artefact_id, a.claim_id, a.reading_id, content_seen)
        r = F.run_tool(tool, seen, self._id("r"))
        self.res.append(r)
        self.step(actor, "runs " + tool, r.result_id)
        return r

    def forged(self, tool, a, outcome=F.PASS, actor=F.TOOL):
        """A hand-written result: right id and digest, outcome not from a run."""
        r = F.ToolResult(self._id("r"), tool, a.artefact_id, F.digest(a.content), outcome)
        self.res.append(r)
        self.step(actor, "runs " + tool, r.result_id)
        return r

    def _judged(self, aid, judged):
        if judged is not None:
            return F.digest(judged)
        a = self.by_id.get(aid)
        return F.digest(a.content) if a is not None else F.digest(("none", aid))

    def verdict(self, cid, rid, aid, value, at=3, actor=F.HUMAN, judged=None):
        v = V(self._id("v"), cid, rid, aid, self._judged(aid, judged), value, at)
        self.ver.append(v)
        self.step(actor, "fidelity verdict", v.verdict_id)
        return v

    def token(self, cid, rid, aid, decision, at=5, actor=F.HUMAN, judged=None):
        t = T(self._id("t"), cid, rid, aid, self._judged(aid, judged), decision, at)
        self.tok.append(t)
        self.step(actor, "decides at fixed point", t.token_id)
        return t

    def split(self, cid, readings, at=2, actor=F.HUMAN):
        s = S(self._id("p"), cid, tuple(readings), at)
        self.spl.append(s)
        self.step(actor, "splits claim", s.split_id)
        return s

    def case(self):
        return Case(tuple(self.claims), tuple(self.arts), tuple(self.res), tuple(self.ver),
                    tuple(self.tok), tuple(self.spl), tuple(self.steps))


def content(pair, lo=1, hi=40):
    return ("forall", lo, hi, pair[0], pair[1])


# ------------------------------------------------------------ design


def design_cases():
    """(name, case, config, ((claim_id, reading_id, status, reason), ...))"""
    out = []

    # Faithful artefact, both tools PASS, human accepts on time.
    b = _B("d1")
    c = b.claim("The sum of the first n positive integers is n(n+1)/2.")
    a = b.art(c, "", content(("sum_to_n", "tri")))
    b.tool(F.ENUMERATE, a)
    b.tool(F.ENDPOINTS, a)
    b.verdict(c, "", a.artefact_id, F.FAITHFUL)
    b.token(c, "", a.artefact_id, F.D_ACCEPT)
    out.append(("accepted", b.case(), cfg(), ((c, "", F.ACCEPTED, "tool_pass_faithful_human_accept"),)))

    # (a) Tool PASS on an artefact that states a different reading.
    b = _B("d2")
    c = b.claim("The sum of the odd numbers not above n is n squared.")
    a = b.art(c, "", content(("sum_odd_first_n", "square")))
    b.tool(F.ENUMERATE, a)
    b.verdict(c, "", a.artefact_id, F.UNFAITHFUL)
    b.token(c, "", a.artefact_id, F.D_ACCEPT)
    out.append(("pass_on_different_reading", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "unfaithful_artefact"),)))

    # (b) Verdict names a different artefact than the tool result.
    b = _B("d3")
    c = b.claim("The sum of the first n cubes is the square of the n-th triangular number.")
    a = b.art(c, "", content(("sum_cubes", "tri_squared")))
    other = b.art(c, "", content(("sum_cubes", "tri_squared"), 1, 20))
    b.tool(F.ENUMERATE, a)
    b.verdict(c, "", other.artefact_id, F.FAITHFUL)
    b.token(c, "", a.artefact_id, F.D_ACCEPT)
    out.append(("verdict_names_other_artefact", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "verdict_artefact_mismatch"),)))

    # (a) Artefact edited after the tool ran: the PASS is for other content.
    b = _B("d4")
    c = b.claim("The sum of the first n positive integers is n squared.")
    a = b.art(c, "", content(("sum_to_n", "square")))
    b.tool(F.ENUMERATE, a, content_seen=content(("sum_to_n", "tri")))
    b.verdict(c, "", a.artefact_id, F.FAITHFUL)
    b.token(c, "", a.artefact_id, F.D_ACCEPT)
    out.append(("pass_on_older_content", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "no_bound_tool_result"),)))

    # (c) Token missing / late, for each on_expiry.
    for oe, st in F.STATUS_ON_EXPIRY.items():
        for late in (False, True):
            b = _B("d5%s%d" % (oe[:2].lower(), late))
            c = b.claim("Twice n equals n plus n.")
            a = b.art(c, "", content(("twice_n", "n_plus_n")))
            b.tool(F.ENUMERATE, a)
            b.verdict(c, "", a.artefact_id, F.FAITHFUL)
            if late:
                b.token(c, "", a.artefact_id, F.D_ACCEPT, at=11)
            out.append(("token_%s_%s" % ("late" if late else "missing", oe.lower()), b.case(), cfg(oe),
                        ((c, "", st, "token_late" if late else "token_missing"),)))

    # (d) Ambiguous claim, no split: parent and reading both not accepted.
    b = _B("d6")
    c = b.claim("The sum of the odd numbers up to n is n squared.", ambiguous=True)
    a = b.art(c, "", content(("sum_odd_first_n", "square")))
    b.tool(F.ENUMERATE, a)
    b.verdict(c, "", a.artefact_id, F.FAITHFUL)
    b.token(c, "", a.artefact_id, F.D_ACCEPT)
    out.append(("ambiguous_without_split", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "ambiguous_needs_split"),
                 (c, "first_n_odd", F.NOT_ACCEPTED, "no_split_record"))))

    # (d) The example's shape: two readings; the first proved, the second refuted.
    b = _B("d7")
    c = b.claim("The sum of the odd numbers up to n is n squared.", ambiguous=True)
    b.split(c, ("first_n_odd", "odd_not_above_n"))
    a1 = b.art(c, "first_n_odd", content(("sum_odd_first_n", "square"), 1, 60))
    a2 = b.art(c, "odd_not_above_n", content(("sum_odd_le_n", "square"), 3, 60))
    for a in (a1, a2):
        b.tool(F.ENUMERATE, a)
        b.tool(F.ENDPOINTS, a)
    b.verdict(c, "first_n_odd", a1.artefact_id, F.FAITHFUL)
    b.verdict(c, "odd_not_above_n", a2.artefact_id, F.FAITHFUL)
    b.token(c, "first_n_odd", a1.artefact_id, F.D_ACCEPT)
    b.token(c, "odd_not_above_n", a2.artefact_id, F.D_REJECT)
    out.append(("split_one_proved_one_refuted", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "split_no_merge"),
                 (c, "first_n_odd", F.ACCEPTED, "tool_pass_faithful_human_accept"),
                 (c, "odd_not_above_n", F.REFUTED, "tool_fail_faithful_human_reject"),
                 (c, "third_reading", F.NOT_ACCEPTED, "reading_not_in_split"))))

    # (d) Each reading needs its own audit: reading 2 reuses reading 1's artefact.
    b = _B("d8")
    c = b.claim("The sum of the odd numbers up to n is n squared.", ambiguous=True)
    b.split(c, ("first_n_odd", "odd_not_above_n"))
    a1 = b.art(c, "first_n_odd", content(("sum_odd_first_n", "square")))
    b.tool(F.ENUMERATE, a1)
    b.verdict(c, "first_n_odd", a1.artefact_id, F.FAITHFUL)
    b.verdict(c, "odd_not_above_n", a1.artefact_id, F.FAITHFUL)
    b.token(c, "first_n_odd", a1.artefact_id, F.D_ACCEPT)
    b.token(c, "odd_not_above_n", a1.artefact_id, F.D_ACCEPT)
    out.append(("reading_reuses_other_audit", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "split_no_merge"),
                 (c, "first_n_odd", F.ACCEPTED, "tool_pass_faithful_human_accept"),
                 (c, "odd_not_above_n", F.NOT_ACCEPTED, "no_bound_tool_result"))))

    # (e) A fidelity verdict attributed to the ai: report invalid.
    b = _B("d9")
    c = b.claim("The sum of the first n positive integers is n(n+1)/2.")
    a = b.art(c, "", content(("sum_to_n", "tri")))
    b.tool(F.ENUMERATE, a)
    b.verdict(c, "", a.artefact_id, F.FAITHFUL, actor=F.AI)
    b.token(c, "", a.artefact_id, F.D_ACCEPT)
    out.append(("verdict_attributed_to_ai", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "report_invalid"),)))

    # Endpoints agree, the middle does not.
    b = _B("d10")
    c = b.claim("n squared equals the wobbled square.")
    a = b.art(c, "", content(TRAP_PAIR, 1, 12))
    b.tool(F.ENUMERATE, a)
    b.tool(F.ENDPOINTS, a)
    b.verdict(c, "", a.artefact_id, F.FAITHFUL)
    b.token(c, "", a.artefact_id, F.D_ACCEPT)
    out.append(("tools_disagree", b.case(), cfg(), ((c, "", F.NOT_ACCEPTED, "tools_disagree"),)))

    # (b) The human judged other content; the artefact was replaced since,
    # and the tools were run again on the new content.
    b = _B("d11")
    c = b.claim("The sum of the first n positive integers is n(n+1)/2.")
    judged = content(("sum_to_n", "tri"))
    a = b.art(c, "", content(("twice_n", "n_plus_n")))
    b.tool(F.ENUMERATE, a)
    b.verdict(c, "", a.artefact_id, F.FAITHFUL, judged=judged)
    b.token(c, "", a.artefact_id, F.D_ACCEPT, judged=judged)
    out.append(("stale_verdict_after_content_change", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "verdict_not_bound_to_content"),)))

    # (b) Verdict on the current content, token still names the old content.
    b = _B("d12")
    c = b.claim("The sum of the first n positive integers is n(n+1)/2.")
    a = b.art(c, "", content(("sum_to_n", "tri")))
    b.tool(F.ENUMERATE, a)
    b.verdict(c, "", a.artefact_id, F.FAITHFUL)
    b.token(c, "", a.artefact_id, F.D_ACCEPT, judged=content(("sum_to_n", "tri"), 1, 20))
    out.append(("stale_token_after_content_change", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "token_not_bound_to_content"),)))

    # (a) A hand-written PASS with the right digest on content the tool FAILs.
    b = _B("d13")
    c = b.claim("The sum of the first n positive integers is n squared.")
    a = b.art(c, "", content(("sum_to_n", "square")))
    b.forged(F.ENUMERATE, a)
    b.verdict(c, "", a.artefact_id, F.FAITHFUL)
    b.token(c, "", a.artefact_id, F.D_ACCEPT)
    out.append(("forged_pass_on_failing_content", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "result_not_reproduced"),)))

    # (a) A hand-written PASS on content no tool can check.
    b = _B("d14")
    c = b.claim("Trust me.")
    a = b.art(c, "", ("trust", "me"))
    b.forged(F.ENUMERATE, a)
    b.verdict(c, "", a.artefact_id, F.FAITHFUL)
    b.token(c, "", a.artefact_id, F.D_ACCEPT)
    out.append(("forged_pass_on_uncheckable_content", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "result_not_reproduced"),)))

    # (c) Verdict recorded after the deadline (and after the token).
    b = _B("d15")
    c = b.claim("Twice n equals n plus n.")
    a = b.art(c, "", content(("twice_n", "n_plus_n")))
    b.tool(F.ENUMERATE, a)
    b.verdict(c, "", a.artefact_id, F.FAITHFUL, at=99)
    b.token(c, "", a.artefact_id, F.D_ACCEPT, at=0)
    out.append(("verdict_after_deadline_and_token", b.case(), cfg(F.DENY),
                ((c, "", F.DENIED, "verdict_late"),)))

    # (c) Token recorded before the fidelity verdict it should follow.
    b = _B("d16")
    c = b.claim("Twice n equals n plus n.")
    a = b.art(c, "", content(("twice_n", "n_plus_n")))
    b.tool(F.ENUMERATE, a)
    b.verdict(c, "", a.artefact_id, F.FAITHFUL, at=6)
    b.token(c, "", a.artefact_id, F.D_ACCEPT, at=4)
    out.append(("order_token_before_verdict", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "token_before_verdict"),)))

    # (b) Two artefacts, both judged faithful: no pick.
    b = _B("d17")
    c = b.claim("The sum of the first n cubes is the square of the n-th triangular number.")
    a1 = b.art(c, "", content(("sum_cubes", "tri_squared")))
    a2 = b.art(c, "", content(("sum_cubes", "tri_squared"), 2, 30))
    for a in (a1, a2):
        b.tool(F.ENUMERATE, a)
        b.verdict(c, "", a.artefact_id, F.FAITHFUL)
    b.token(c, "", a1.artefact_id, F.D_ACCEPT)
    out.append(("two_artefacts_both_faithful", b.case(), cfg(),
                ((c, "", F.NOT_ACCEPTED, "several_faithful_artefacts"),)))
    return tuple(out)


DESIGN = design_cases()


# ------------------------------------------------------------ seeded scenarios

SCENARIO_SEEDS = tuple(range(4101, 4113))
OE_STATUS = F.STATUS_ON_EXPIRY

# label -> expected targets, as (reading_key, status or "ON_EXPIRY", reason).
# reading_key "" is the claim itself; "r1"/"r2" are the split readings.
LABELS = {
    "accepted": (("", F.ACCEPTED, "tool_pass_faithful_human_accept"),),
    "refuted": (("", F.REFUTED, "tool_fail_faithful_human_reject"),),
    "unfaithful_pass": (("", F.NOT_ACCEPTED, "unfaithful_artefact"),),
    "no_verdict": (("", F.NOT_ACCEPTED, "no_fidelity_verdict"),),
    "verdict_mismatch": (("", F.NOT_ACCEPTED, "verdict_artefact_mismatch"),),
    "conflicting_verdicts": (("", F.NOT_ACCEPTED, "conflicting_verdicts"),),
    "token_missing": (("", "ON_EXPIRY", "token_missing"),),
    "token_late": (("", "ON_EXPIRY", "token_late"),),
    "token_mismatch": (("", F.NOT_ACCEPTED, "token_artefact_mismatch"),),
    "stale_digest": (("", F.NOT_ACCEPTED, "no_bound_tool_result"),),
    "tools_disagree": (("", F.NOT_ACCEPTED, "tools_disagree"),),
    "required_missing": (("", F.NOT_ACCEPTED, "required_tool_missing"),),
    "tool_error": (("", F.NOT_ACCEPTED, "tool_error"),),
    "human_reject": (("", F.NOT_ACCEPTED, "rejected_by_human"),),
    "accept_on_fail": (("", F.NOT_ACCEPTED, "human_accept_on_tool_fail"),),
    "ambiguous_no_split": (("", F.NOT_ACCEPTED, "ambiguous_needs_split"),
                           ("r1", F.NOT_ACCEPTED, "no_split_record")),
    "split": (("", F.NOT_ACCEPTED, "split_no_merge"),
              ("r1", F.ACCEPTED, "tool_pass_faithful_human_accept"),
              ("r2", F.REFUTED, "tool_fail_faithful_human_reject")),
    "split_reuse": (("", F.NOT_ACCEPTED, "split_no_merge"),
                    ("r1", F.ACCEPTED, "tool_pass_faithful_human_accept"),
                    ("r2", F.NOT_ACCEPTED, "no_bound_tool_result")),
    "split_by_ai": (("", F.NOT_ACCEPTED, "report_invalid"), ("r1", F.NOT_ACCEPTED, "report_invalid")),
    "verdict_by_ai": (("", F.NOT_ACCEPTED, "report_invalid"),),
    "token_by_tool": (("", F.NOT_ACCEPTED, "report_invalid"),),
    "unattributed_step": (("", F.NOT_ACCEPTED, "report_invalid"),),
    "record_without_step": (("", F.NOT_ACCEPTED, "report_invalid"),),
    "mixed_actor_verdict": (("", F.NOT_ACCEPTED, "report_invalid"),),
    "stale_verdict": (("", F.NOT_ACCEPTED, "verdict_not_bound_to_content"),),
    "stale_token": (("", F.NOT_ACCEPTED, "token_not_bound_to_content"),),
    "forged_pass": (("", F.NOT_ACCEPTED, "result_not_reproduced"),),
    "forged_junk": (("", F.NOT_ACCEPTED, "result_not_reproduced"),),
    "verdict_late": (("", "ON_EXPIRY", "verdict_late"),),
    "token_before_verdict": (("", F.NOT_ACCEPTED, "token_before_verdict"),),
    "several_faithful": (("", F.NOT_ACCEPTED, "several_faithful_artefacts"),),
}

# Labels whose world is adversarial; each has a witness in the tests that
# the generated records really carry the attack.
ADVERSARIAL = ("stale_verdict", "stale_token", "forged_pass", "forged_junk", "verdict_late",
               "token_before_verdict", "several_faithful", "mixed_actor_verdict", "stale_digest",
               "verdict_mismatch", "token_mismatch", "unfaithful_pass")


def _range_for(rng, pair, want):
    """lo, hi such that the pair has the wanted tool behaviour on [lo, hi]."""
    f, g = F.FUNCS[pair[0]], F.FUNCS[pair[1]]
    for _ in range(10000):
        lo = rng.randint(1, 30)
        hi = rng.randint(lo + 5, min(lo + 80, F.MAX_N))
        ends = f(lo) == g(lo) and f(hi) == g(hi)
        whole = all(f(n) == g(n) for n in range(lo, hi + 1))
        if want == "true" and whole:
            return lo, hi
        if want == "false" and not (f(lo) == g(lo) or f(hi) == g(hi)):
            return lo, hi
        if want == "trap" and ends and not whole:
            return lo, hi
    raise RuntimeError("no range")


def _content(rng, want):
    pair = TRAP_PAIR if want == "trap" else rng.choice(TRUE_PAIRS if want == "true" else FALSE_PAIRS)
    lo, hi = _range_for(rng, pair, want)
    return ("forall", lo, hi, pair[0], pair[1])


def build(label, tag, rng, deadline):
    """Records realising one label. Returns (case, claim_id, {key: reading_id})."""
    b = _B(tag)
    amb = label.startswith("split") or label == "ambiguous_no_split"
    c = b.claim("scenario claim %s" % tag, ambiguous=amb)
    v_at = rng.randint(0, deadline - 1)
    t_ok = rng.randint(v_at + 1, deadline)
    t_late = deadline + rng.randint(1, 5)
    tools = [F.ENUMERATE] + ([F.ENDPOINTS] if rng.random() < 0.5 else [])
    rr = {"": ""}

    def simple(rid, want, decision, verdict=F.FAITHFUL, token=True, vactor=F.HUMAN, tactor=F.HUMAN):
        a = b.art(c, rid, _content(rng, want))
        for tl in tools:
            b.tool(tl, a)
        b.verdict(c, rid, a.artefact_id, verdict, at=v_at, actor=vactor)
        if token:
            b.token(c, rid, a.artefact_id, decision, at=t_ok, actor=tactor)
        return a

    if label == "accepted":
        simple("", "true", F.D_ACCEPT)
    elif label == "refuted":
        simple("", "false", F.D_REJECT)
    elif label == "unfaithful_pass":
        simple("", "true", F.D_ACCEPT, verdict=F.UNFAITHFUL)
    elif label == "no_verdict":
        a = b.art(c, "", _content(rng, "true"))
        b.tool(F.ENUMERATE, a)
        b.token(c, "", a.artefact_id, F.D_ACCEPT, at=t_ok)
    elif label == "verdict_mismatch":
        a = b.art(c, "", _content(rng, "true"))
        o = b.art(c, "", _content(rng, "true"))
        b.tool(F.ENUMERATE, a)
        b.verdict(c, "", o.artefact_id, F.FAITHFUL)
        b.token(c, "", a.artefact_id, F.D_ACCEPT, at=t_ok)
    elif label == "conflicting_verdicts":
        a = simple("", "true", F.D_ACCEPT)
        b.verdict(c, "", a.artefact_id, F.UNFAITHFUL, at=v_at)
    elif label == "token_missing":
        simple("", rng.choice(["true", "false"]), F.D_ACCEPT, token=False)
    elif label == "token_late":
        a = simple("", "true", F.D_ACCEPT, token=False)
        b.token(c, "", a.artefact_id, F.D_ACCEPT, at=t_late)
    elif label == "token_mismatch":
        a = simple("", "true", F.D_ACCEPT, token=False)
        o = b.art(c, "", _content(rng, "true"))
        b.token(c, "", o.artefact_id, F.D_ACCEPT, at=t_ok)
    elif label == "stale_digest":
        a = b.art(c, "", _content(rng, rng.choice(["true", "false"])))
        b.tool(F.ENUMERATE, a, content_seen=_content(rng, "true"))
        b.verdict(c, "", a.artefact_id, F.FAITHFUL)
        b.token(c, "", a.artefact_id, F.D_ACCEPT, at=t_ok)
    elif label == "tools_disagree":
        a = b.art(c, "", _content(rng, "trap"))
        b.tool(F.ENUMERATE, a)
        b.tool(F.ENDPOINTS, a)
        b.verdict(c, "", a.artefact_id, F.FAITHFUL)
        b.token(c, "", a.artefact_id, rng.choice(F.DECISIONS), at=t_ok)
    elif label == "required_missing":
        a = b.art(c, "", _content(rng, "true"))
        b.tool(F.ENDPOINTS, a)
        b.verdict(c, "", a.artefact_id, F.FAITHFUL)
        b.token(c, "", a.artefact_id, F.D_ACCEPT, at=t_ok)
    elif label == "tool_error":
        lo = rng.randint(1, 10)
        a = b.art(c, "", ("forall", lo, F.MAX_N + rng.randint(1, 50), "sum_to_n", "tri"))
        b.tool(F.ENUMERATE, a)
        b.verdict(c, "", a.artefact_id, F.FAITHFUL)
        b.token(c, "", a.artefact_id, F.D_ACCEPT, at=t_ok)
    elif label == "human_reject":
        simple("", "true", F.D_REJECT)
    elif label == "accept_on_fail":
        simple("", "false", F.D_ACCEPT)
    elif label == "ambiguous_no_split":
        simple("", "true", F.D_ACCEPT)
        rr["r1"] = "reading-a"
    elif label in ("split", "split_reuse", "split_by_ai"):
        r1, r2 = "reading-%d" % rng.randint(0, 99), "reading-x%d" % rng.randint(0, 99)
        rr["r1"], rr["r2"] = r1, r2
        b.split(c, (r1, r2), at=rng.randint(0, deadline), actor=F.AI if label == "split_by_ai" else F.HUMAN)
        a1 = simple(r1, "true", F.D_ACCEPT)
        if label == "split_reuse":
            b.verdict(c, r2, a1.artefact_id, F.FAITHFUL)
            b.token(c, r2, a1.artefact_id, F.D_ACCEPT, at=t_ok)
        else:
            simple(r2, "false", F.D_REJECT)
    elif label == "verdict_by_ai":
        simple("", "true", F.D_ACCEPT, vactor=F.AI)
    elif label == "token_by_tool":
        simple("", "true", F.D_ACCEPT, tactor=F.TOOL)
    elif label == "unattributed_step":
        simple("", "true", F.D_ACCEPT)
        b.steps.insert(rng.randint(0, len(b.steps)), St(tag + "-sx", rng.choice([None, "", "model", "Human"]),
                                                       "unattributed note", ""))
    elif label == "record_without_step":
        simple("", "true", F.D_ACCEPT)
        victims = [k for k, s in enumerate(b.steps) if s.ref and s.ref != c]
        del b.steps[rng.choice(victims)]
    elif label == "mixed_actor_verdict":
        a = simple("", "true", F.D_ACCEPT)
        vid = b.ver[-1].verdict_id
        b.step(rng.choice([F.AI, F.TOOL]), "also records verdict", vid)
    elif label in ("stale_verdict", "stale_token"):
        old = _content(rng, "true")
        a = b.art(c, "", _content(rng, "true"))
        while a.content == old:
            old = _content(rng, "true")
        for tl in tools:
            b.tool(tl, a)
        b.verdict(c, "", a.artefact_id, F.FAITHFUL, at=v_at,
                  judged=old if label == "stale_verdict" else None)
        b.token(c, "", a.artefact_id, F.D_ACCEPT, at=t_ok,
                judged=old if label == "stale_token" or rng.random() < 0.5 else None)
    elif label in ("forged_pass", "forged_junk"):
        if label == "forged_pass":
            a = b.art(c, "", _content(rng, rng.choice(["false", "trap"])))
        else:
            a = b.art(c, "", rng.choice([("trust", "me"), ("forall", 1, 5, "tri", "oracle"),
                                         ("forall", 9, 2, "tri", "tri"), "proved"]))
        b.forged(F.ENUMERATE, a)
        b.verdict(c, "", a.artefact_id, F.FAITHFUL, at=v_at)
        b.token(c, "", a.artefact_id, F.D_ACCEPT, at=t_ok)
    elif label == "verdict_late":
        a = b.art(c, "", _content(rng, "true"))
        for tl in tools:
            b.tool(tl, a)
        b.verdict(c, "", a.artefact_id, F.FAITHFUL, at=t_late)
        b.token(c, "", a.artefact_id, F.D_ACCEPT, at=rng.randint(0, deadline))
    elif label == "token_before_verdict":
        a = b.art(c, "", _content(rng, "true"))
        for tl in tools:
            b.tool(tl, a)
        b.verdict(c, "", a.artefact_id, F.FAITHFUL, at=t_ok)
        b.token(c, "", a.artefact_id, F.D_ACCEPT, at=rng.randint(0, t_ok))
    elif label == "several_faithful":
        a1 = simple("", "true", F.D_ACCEPT)
        a2 = b.art(c, "", _content(rng, "true"))
        b.tool(F.ENUMERATE, a2)
        b.verdict(c, "", a2.artefact_id, F.FAITHFUL, at=v_at)
    else:
        raise ValueError(label)
    steps = b.steps[:]
    head = steps[:1]
    tail = steps[1:]
    rng.shuffle(tail)
    b.steps = head + tail
    return b.case(), c, rr


def make_scenarios(seed):
    """One seeded batch: tuple of (name, case, config, expected targets)."""
    rng = random.Random(seed)
    labels = sorted(LABELS)
    picks = rng.sample(labels, rng.randint(12, 18))
    picks += [rng.choice(["accepted", "refuted", "split"])]
    out = []
    for k, label in enumerate(picks):
        deadline = rng.randint(4, 20)
        oe = F.ON_EXPIRY[(seed + k) % len(F.ON_EXPIRY)]
        tag = "h%d-%d" % (seed, k)
        case, cid, rr = build(label, tag, rng, deadline)
        want = tuple((cid, rr[key], OE_STATUS[oe] if st == "ON_EXPIRY" else st, reason)
                     for key, st, reason in LABELS[label])
        required = (F.ENUMERATE,) if rng.random() < 0.7 or label == "required_missing" else (F.ENUMERATE, F.ENDPOINTS)
        if label in ("required_missing", "tool_error", "no_verdict", "verdict_mismatch", "stale_digest",
                     "forged_pass", "forged_junk", "several_faithful"):
            required = (F.ENUMERATE,)
        if F.ENDPOINTS in required and not any(r.tool == F.ENDPOINTS for r in case.results):
            required = (F.ENUMERATE,)
        out.append(("%s:%s" % (tag, label), case, cfg(oe, deadline, required), want))
    return tuple(out)


SCENARIOS = tuple(c for s in SCENARIO_SEEDS for c in make_scenarios(s))


def check(cases, out=print):
    fails = 0
    for name, case, conf, want in cases:
        bad = []
        for cid, rid, status, reason in want:
            o = F.audit(case, conf, cid, rid)
            if (o.status, o.reason, o.accepted) != (status, reason, status == F.ACCEPTED):
                bad.append("%s/%s: got %s %s" % (cid, rid, o.status, o.reason))
        fails += 1 if bad else 0
        out("%-44s %s" % (name, "PASS" if not bad else "FAIL " + "; ".join(bad)))
    return fails, len(cases)


def scenario_totals():
    t = {"cases": len(SCENARIOS), "targets": 0}
    for name, case, conf, want in SCENARIOS:
        label = name.split(":")[1]
        t["label_" + label] = t.get("label_" + label, 0) + 1
        for _, _, status, _ in want:
            t["targets"] += 1
            t[status] = t.get(status, 0) + 1
    return t


def main():
    fd, nd = check(DESIGN)
    fh, nh = check(SCENARIOS)
    t = scenario_totals()
    print("scenario totals: %s" % {k: v for k, v in sorted(t.items()) if not k.startswith("label_")})
    print("scenario labels covered: %d of %d" % (sum(k.startswith("label_") for k in t), len(LABELS)))
    print("design %d/%d PASS, scenario %d/%d PASS" % (nd - fd, nd, nh - fh, nh))
    return 1 if fd or fh else 0


if __name__ == "__main__":
    sys.exit(main())
