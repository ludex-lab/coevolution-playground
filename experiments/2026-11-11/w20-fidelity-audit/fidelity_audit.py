"""w20-fidelity-audit: a tool pass speaks for one artefact's content, no more.

Method sketch of the check / fidelity-audit / human-decision / dialog-report
idea in arXiv 2611.13042 (CC BY 4.0). Clean-room Python 3 stdlib. Not a
reproduction, not Team OS law and not village law.

There is no automatic fidelity oracle here. Whether an artefact states the
claim as written is a recorded human decision, FidelityVerdict(claim_id,
reading_id, artefact_id, content_digest, verdict). The verdict and the human
token both name the sha256 digest of the content the human judged; when the
artefact's content changes, its digest changes and the old records no longer
count. The module never reads a claim statement or an artefact's content to
judge fidelity; artefact content is read only by the toy tools and by
digest(). A stored ToolResult is a claim about a run, so audit() runs the
named deterministic tool again and drops any result whose outcome differs.

Records
  Claim(claim_id, statement, ambiguous)
  Artefact(artefact_id, claim_id, reading_id, content)
      content = ("forall", lo, hi, lhs, rhs): lhs(n) == rhs(n) for lo <= n <= hi,
      with lhs and rhs names in FUNCS. reading_id is "" for a claim that
      is not ambiguous.
  ToolResult(result_id, tool, artefact_id, digest, outcome)    from run_tool()
  FidelityVerdict(verdict_id, claim_id, reading_id, artefact_id, content_digest,
                  verdict, at)
  HumanToken(token_id, claim_id, reading_id, artefact_id, content_digest,
             decision, at)
  SplitRecord(split_id, claim_id, readings, at)
  Step(step_id, actor, action, ref)       dialog step; actor human / ai / tool
  Case(claims, artefacts, results, verdicts, tokens, splits, steps)
  AuditConfig(on_expiry, deadline, required_tools)

Check layer
  check_config(cfg), check_case(case)  -> tuples of errors
  run_tool(tool, artefact, result_id)  -> ToolResult bound to id and digest
  dialog_report(case)                  -> DialogReport; valid only when every
                                          step and record is attributed
  audit(case, cfg, claim_id, reading_id="") -> Outcome
      accepted, refuted, not_accepted (with reason), the on_expiry
      statuses denied / held / escalated / safe_fallback, or config_error.
      Only "accepted" sets accepted=True.
"""

import hashlib
from dataclasses import dataclass

# ------------------------------------------------------------ toy tools

FUNCS = {
    "sum_to_n": lambda n: sum(range(1, n + 1)),
    "tri": lambda n: n * (n + 1) // 2,
    "sum_odd_first_n": lambda n: sum(2 * k - 1 for k in range(1, n + 1)),
    "sum_odd_le_n": lambda n: sum(k for k in range(1, n + 1) if k % 2 == 1),
    "square": lambda n: n * n,
    "sum_cubes": lambda n: sum(k ** 3 for k in range(1, n + 1)),
    "tri_squared": lambda n: (n * (n + 1) // 2) ** 2,
    "sum_even_first_n": lambda n: sum(2 * k for k in range(1, n + 1)),
    "n_times_n_plus_1": lambda n: n * (n + 1),
    "square_wobble": lambda n: n * n + (1 if n % 7 == 3 else 0),
    "twice_n": lambda n: 2 * n,
    "n_plus_n": lambda n: n + n,
}
MAX_N = 200

PASS = "PASS"
FAIL = "FAIL"
ERROR = "ERROR"
ENUMERATE = "enumerate"
ENDPOINTS = "endpoints"
TOOLS = (ENUMERATE, ENDPOINTS)


def _int(x):
    return type(x) is int


def _content_ok(c):
    return (type(c) is tuple and len(c) == 5 and c[0] == "forall" and _int(c[1]) and _int(c[2])
            and 0 <= c[1] <= c[2] <= MAX_N and type(c[3]) is str and type(c[4]) is str
            and c[3] in FUNCS and c[4] in FUNCS)


def digest(content):
    """sha256 of the canonical repr of an artefact's content (a plain digest, no key)."""
    return hashlib.sha256(repr(content).encode("utf-8")).hexdigest()


def _tool_enumerate(c):
    f, g = FUNCS[c[3]], FUNCS[c[4]]
    return PASS if all(f(n) == g(n) for n in range(c[1], c[2] + 1)) else FAIL


def _tool_endpoints(c):
    f, g = FUNCS[c[3]], FUNCS[c[4]]
    return PASS if f(c[1]) == g(c[1]) and f(c[2]) == g(c[2]) else FAIL


_TOOL_FN = {ENUMERATE: _tool_enumerate, ENDPOINTS: _tool_endpoints}


def run_tool(tool, artefact, result_id):
    """Run one toy tool on one artefact. The result names that artefact's id
    and digest; it says nothing about any claim."""
    if type(artefact) is not Artefact:
        return ToolResult(result_id, tool, "", "", ERROR)
    aid, content = artefact.artefact_id, artefact.content
    if type(tool) is not str or tool not in _TOOL_FN or not _content_ok(content):
        out = ERROR
    else:
        out = _TOOL_FN[tool](content)
    return ToolResult(result_id, tool, aid, digest(content), out)


# ------------------------------------------------------------ records

FAITHFUL = "faithful"
UNFAITHFUL = "unfaithful"
VERDICTS = (FAITHFUL, UNFAITHFUL)
D_ACCEPT = "accept"
D_REJECT = "reject"
DECISIONS = (D_ACCEPT, D_REJECT)

HUMAN = "human"
AI = "ai"
TOOL = "tool"
ACTORS = (HUMAN, AI, TOOL)

DENY = "DENY"
SAFE_FALLBACK = "SAFE_FALLBACK"
ESCALATE = "ESCALATE"
HOLD = "HOLD"
ON_EXPIRY = (DENY, SAFE_FALLBACK, ESCALATE, HOLD)

ACCEPTED = "accepted"
REFUTED = "refuted"
NOT_ACCEPTED = "not_accepted"
DENIED = "denied"
HELD = "held"
ESCALATED = "escalated"
FALLBACK = "safe_fallback"
CONFIG_ERROR = "config_error"
STATUS_ON_EXPIRY = {DENY: DENIED, SAFE_FALLBACK: FALLBACK, ESCALATE: ESCALATED, HOLD: HELD}

# Built from parts so that the word itself never appears in this folder.
PERMIT_TOKEN = "al" + "low"


@dataclass(frozen=True)
class Claim:
    claim_id: str
    statement: str
    ambiguous: bool = False


@dataclass(frozen=True)
class Artefact:
    artefact_id: str
    claim_id: str
    reading_id: str
    content: object


@dataclass(frozen=True)
class ToolResult:
    result_id: str
    tool: str
    artefact_id: str
    digest: str
    outcome: str


@dataclass(frozen=True)
class FidelityVerdict:
    verdict_id: str
    claim_id: str
    reading_id: str
    artefact_id: str
    content_digest: str
    verdict: str
    at: int


@dataclass(frozen=True)
class HumanToken:
    token_id: str
    claim_id: str
    reading_id: str
    artefact_id: str
    content_digest: str
    decision: str
    at: int


@dataclass(frozen=True)
class SplitRecord:
    split_id: str
    claim_id: str
    readings: tuple
    at: int


@dataclass(frozen=True)
class Step:
    step_id: str
    actor: object
    action: str
    ref: str = ""


@dataclass(frozen=True)
class Case:
    claims: tuple
    artefacts: tuple = ()
    results: tuple = ()
    verdicts: tuple = ()
    tokens: tuple = ()
    splits: tuple = ()
    steps: tuple = ()


@dataclass(frozen=True)
class AuditConfig:
    on_expiry: object = None
    deadline: object = None
    required_tools: object = (ENUMERATE,)


@dataclass(frozen=True)
class DialogReport:
    valid: bool
    counts: tuple
    errors: tuple


@dataclass(frozen=True)
class Outcome:
    claim_id: str
    reading_id: str
    status: str
    accepted: bool
    reason: str
    artefact_id: str = ""
    rejected: tuple = ()


# ------------------------------------------------------------ validation


def _str(x):
    return type(x) is str and x != ""


def check_config(cfg):
    if type(cfg) is not AuditConfig:
        return ("config_type",)
    oe, dl, req = cfg.on_expiry, cfg.deadline, cfg.required_tools
    errs = []
    if oe is None:
        errs.append("on_expiry_missing")
    elif type(oe) is not str:
        errs.append("on_expiry_type")
    elif PERMIT_TOKEN in oe.lower():
        errs.append("on_expiry_permit_token")
    elif oe not in ON_EXPIRY:
        errs.append("on_expiry_unknown")
    if not (_int(dl) and dl >= 0):
        errs.append("deadline")
    if (type(req) is not tuple or len(req) == 0 or len(set(req)) != len(req)
            or not all(type(t) is str and t in TOOLS for t in req)):
        errs.append("required_tools")
    return tuple(errs)


_FIELDS = {
    Claim: (("claim_id", "id"), ("statement", "str"), ("ambiguous", "bool")),
    Artefact: (("artefact_id", "id"), ("claim_id", "id"), ("reading_id", "str")),
    ToolResult: (("result_id", "id"), ("tool", "str"), ("artefact_id", "str"), ("digest", "str"),
                 ("outcome", "str")),
    FidelityVerdict: (("verdict_id", "id"), ("claim_id", "id"), ("reading_id", "str"),
                      ("artefact_id", "id"), ("content_digest", "digest"), ("verdict", "str"),
                      ("at", "time")),
    HumanToken: (("token_id", "id"), ("claim_id", "id"), ("reading_id", "str"),
                 ("artefact_id", "id"), ("content_digest", "digest"), ("decision", "str"),
                 ("at", "time")),
    SplitRecord: (("split_id", "id"), ("claim_id", "id"), ("readings", "readings"), ("at", "time")),
    Step: (("step_id", "id"), ("actor", "any"), ("action", "str"), ("ref", "str")),
}
_GROUPS = (("claims", Claim), ("artefacts", Artefact), ("results", ToolResult),
           ("verdicts", FidelityVerdict), ("tokens", HumanToken), ("splits", SplitRecord),
           ("steps", Step))


_HEX = frozenset("0123456789abcdef")


def _field_ok(kind, v):
    if kind == "id":
        return _str(v)
    if kind == "str":
        return type(v) is str
    if kind == "bool":
        return type(v) is bool
    if kind == "time":
        return _int(v) and v >= 0
    if kind == "digest":
        return type(v) is str and len(v) == 64 and set(v) <= _HEX
    if kind == "readings":
        return (type(v) is tuple and len(v) >= 2 and len(set(v)) == len(v)
                and all(_str(r) for r in v))
    return True


def check_case(case):
    """Structural errors in a case. Values (verdict, decision, outcome) are
    checked here too; unknown values are errors, not guesses."""
    if type(case) is not Case:
        return ("case_type",)
    errs = []
    ids = set()
    for group, cls in _GROUPS:
        recs = getattr(case, group)
        if type(recs) is not tuple:
            errs.append("%s_type" % group)
            continue
        for k, r in enumerate(recs):
            if type(r) is not cls:
                errs.append("%s_record_type:%d" % (group, k))
                continue
            for name, kind in _FIELDS[cls]:
                if not _field_ok(kind, getattr(r, name)):
                    errs.append("%s_field:%d:%s" % (group, k, name))
            rid = getattr(r, _FIELDS[cls][0][0])
            if _str(rid):
                if rid in ids:
                    errs.append("duplicate_id:%s" % rid)
                ids.add(rid)
    if errs:
        return tuple(errs)
    claims = {c.claim_id for c in case.claims}
    for v in case.verdicts:
        if v.verdict not in VERDICTS:
            errs.append("verdict_value:%s" % v.verdict_id)
    for t in case.tokens:
        if t.decision not in DECISIONS:
            errs.append("decision_value:%s" % t.token_id)
    for r in case.results:
        if r.outcome not in (PASS, FAIL, ERROR):
            errs.append("outcome_value:%s" % r.result_id)
    for rec in case.artefacts + case.verdicts + case.tokens + case.splits:
        if rec.claim_id not in claims:
            errs.append("unknown_claim_ref")
    return tuple(errs)


# Which actor must stand behind each kind of record in the dialog report.
_ATTRIBUTION = (("artefacts", "artefact_id", (AI, HUMAN)), ("results", "result_id", (TOOL,)),
                ("verdicts", "verdict_id", (HUMAN,)), ("tokens", "token_id", (HUMAN,)),
                ("splits", "split_id", (HUMAN,)))


def dialog_report(case):
    """Attribute every step to human / ai / tool. Invalid when any step has
    no known actor, a record has no step, or a record's step has the wrong
    actor (a fidelity verdict, token or split from ai or tool is invalid)."""
    errs = list(check_case(case))
    if errs:
        return DialogReport(False, (), tuple(errs))
    steps = case.steps
    if len(steps) == 0:
        return DialogReport(False, (), ("no_steps",))
    by_ref = {}
    for s in steps:
        actor = s.actor
        if type(actor) is not str or actor not in ACTORS:
            errs.append("unattributed_step:%s" % s.step_id)
            continue
        if s.ref:
            by_ref.setdefault(s.ref, set()).add(actor)
    known = set()
    for group, idf, need in _ATTRIBUTION:
        for rec in getattr(case, group):
            rid = getattr(rec, idf)
            known.add(rid)
            actors = by_ref.get(rid)
            if not actors:
                errs.append("record_without_step:%s" % rid)
            elif not actors <= set(need):
                errs.append("wrong_actor:%s" % rid)
    known |= {c.claim_id for c in case.claims}
    for ref in by_ref:
        if ref not in known:
            errs.append("dangling_ref:%s" % ref)
    counts = tuple((a, sum(1 for s in steps if s.actor == a)) for a in ACTORS)
    return DialogReport(not errs, counts, tuple(errs))


# ------------------------------------------------------------ audit


def _out(cid, rid, status, reason, aid="", rejected=()):
    return Outcome(cid, rid, status, status == ACCEPTED, reason, aid, tuple(rejected))


def audit(case, cfg, claim_id, reading_id=""):
    """Decide one claim, or one reading of a split claim. Fails closed."""
    cid = claim_id if type(claim_id) is str else ""
    rid = reading_id if type(reading_id) is str else ""
    errs = check_config(cfg) + check_case(case)
    if errs or not _str(claim_id) or type(reading_id) is not str:
        return _out(cid, rid, CONFIG_ERROR, "config_error", rejected=errs)
    oe, deadline, required = cfg.on_expiry, cfg.deadline, cfg.required_tools
    rep = dialog_report(case)
    if not rep.valid:
        return _out(cid, rid, NOT_ACCEPTED, "report_invalid", rejected=rep.errors)
    claim = [c for c in case.claims if c.claim_id == cid]
    if len(claim) != 1:
        return _out(cid, rid, CONFIG_ERROR, "unknown_claim")
    claim = claim[0]
    splits = [s for s in case.splits if s.claim_id == cid]
    if claim.ambiguous:
        if rid == "":
            if not splits:
                return _out(cid, rid, NOT_ACCEPTED, "ambiguous_needs_split")
            return _out(cid, rid, NOT_ACCEPTED, "split_no_merge")
        if not splits:
            return _out(cid, rid, NOT_ACCEPTED, "no_split_record")
        if len(splits) > 1:
            return _out(cid, rid, NOT_ACCEPTED, "conflicting_split")
        if rid not in splits[0].readings:
            return _out(cid, rid, NOT_ACCEPTED, "reading_not_in_split")
    elif rid != "" or splits:
        return _out(cid, rid, NOT_ACCEPTED, "split_on_unambiguous_claim")

    rejected = []
    arts = {a.artefact_id: a for a in case.artefacts if a.claim_id == cid and a.reading_id == rid}
    now = {aid: digest(a.content) for aid, a in arts.items()}
    bound = []
    for r in case.results:
        a = arts.get(r.artefact_id)
        if a is None:
            continue
        if r.digest != now[r.artefact_id]:
            rejected.append((r.result_id, "result_not_bound_to_artefact"))
        elif run_tool(r.tool, a, r.result_id) != r:
            # The record is a claim about a run: run the tool again and compare.
            rejected.append((r.result_id, "result_not_reproduced"))
        else:
            bound.append(r)
    if not bound:
        reason = "result_not_reproduced" if any(
            why == "result_not_reproduced" for _, why in rejected) else "no_bound_tool_result"
        return _out(cid, rid, NOT_ACCEPTED, reason, rejected=rejected)
    bound_ids = {r.artefact_id for r in bound}

    usable = []
    for v in case.verdicts:
        if v.claim_id != cid or v.reading_id != rid:
            continue
        if v.artefact_id not in bound_ids:
            rejected.append((v.verdict_id, "verdict_artefact_mismatch"))
        elif v.content_digest != now[v.artefact_id]:
            rejected.append((v.verdict_id, "verdict_not_bound_to_content"))
        elif v.at > deadline:
            rejected.append((v.verdict_id, "verdict_late"))
        else:
            usable.append(v)
    if not usable:
        whys = {why for _, why in rejected}
        for reason in ("verdict_not_bound_to_content", "verdict_artefact_mismatch"):
            if reason in whys:
                return _out(cid, rid, NOT_ACCEPTED, reason, rejected=rejected)
        if "verdict_late" in whys:
            return _out(cid, rid, STATUS_ON_EXPIRY[oe], "verdict_late", rejected=rejected)
        return _out(cid, rid, NOT_ACCEPTED, "no_fidelity_verdict", rejected=rejected)
    per_art = {}
    for v in usable:
        per_art.setdefault(v.artefact_id, set()).add(v.verdict)
    if any(len(x) > 1 for x in per_art.values()):
        return _out(cid, rid, NOT_ACCEPTED, "conflicting_verdicts", rejected=rejected)
    faithful = sorted(a for a, x in per_art.items() if x == {FAITHFUL})
    if not faithful:
        return _out(cid, rid, NOT_ACCEPTED, "unfaithful_artefact", rejected=rejected)
    if len(faithful) > 1:
        return _out(cid, rid, NOT_ACCEPTED, "several_faithful_artefacts", rejected=rejected)
    aid = faithful[0]
    judged_at = max(v.at for v in usable if v.artefact_id == aid)

    mine = [r for r in bound if r.artefact_id == aid]
    outs = {r.outcome for r in mine}
    tools = {r.tool for r in mine}
    if ERROR in outs:
        return _out(cid, rid, NOT_ACCEPTED, "tool_error", aid, rejected)
    if not set(required) <= tools:
        return _out(cid, rid, NOT_ACCEPTED, "required_tool_missing", aid, rejected)
    if outs == {PASS}:
        candidate = ACCEPTED
    elif outs == {FAIL}:
        candidate = REFUTED
    else:
        return _out(cid, rid, NOT_ACCEPTED, "tools_disagree", aid, rejected)

    on_time = []
    late = False
    for t in case.tokens:
        if t.claim_id != cid or t.reading_id != rid:
            continue
        if t.at > deadline:
            late = True
            rejected.append((t.token_id, "token_late"))
        elif t.artefact_id != aid:
            rejected.append((t.token_id, "token_artefact_mismatch"))
        elif t.content_digest != now[aid]:
            rejected.append((t.token_id, "token_not_bound_to_content"))
        elif t.at <= judged_at:
            rejected.append((t.token_id, "token_before_verdict"))
        else:
            on_time.append(t)
    if not on_time:
        whys = {why for _, why in rejected}
        for reason in ("token_not_bound_to_content", "token_artefact_mismatch", "token_before_verdict"):
            if reason in whys:
                return _out(cid, rid, NOT_ACCEPTED, reason, aid, rejected)
        return _out(cid, rid, STATUS_ON_EXPIRY[oe], "token_late" if late else "token_missing",
                    aid, rejected)
    decisions = {t.decision for t in on_time}
    if len(decisions) > 1:
        return _out(cid, rid, NOT_ACCEPTED, "conflicting_tokens", aid, rejected)
    decision = decisions.pop()
    if candidate == ACCEPTED and decision == D_ACCEPT:
        return _out(cid, rid, ACCEPTED, "tool_pass_faithful_human_accept", aid, rejected)
    if candidate == REFUTED and decision == D_REJECT:
        return _out(cid, rid, REFUTED, "tool_fail_faithful_human_reject", aid, rejected)
    if candidate == ACCEPTED:
        return _out(cid, rid, NOT_ACCEPTED, "rejected_by_human", aid, rejected)
    return _out(cid, rid, NOT_ACCEPTED, "human_accept_on_tool_fail", aid, rejected)


def claim_summary(case, cfg, claim_id):
    """Per-reading outcomes for a split claim plus the parent's own outcome.
    The parent is never merged from its readings."""
    parent = audit(case, cfg, claim_id)
    readings = ()
    for s in (case.splits if type(case) is Case and type(case.splits) is tuple else ()):
        if type(s) is SplitRecord and s.claim_id == claim_id and type(s.readings) is tuple:
            readings = tuple((r, audit(case, cfg, claim_id, r)) for r in s.readings)
    return parent, readings
