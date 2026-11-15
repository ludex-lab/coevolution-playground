"""A gatekeeper that only issues what a finite record settles (stdlib method sketch).

The gate watches a program for n steps and reads nothing but that prefix.
Rules: a set of forbidden events ("never do this") and an answer event
("answer eventually").

- A forbidden event in the prefix is settled: REFUSE, with its position.
- A clean prefix earns only a scoped certificate, clean_through=n. A request
  for a standing "never" or "eventually" certificate is UNSETTLED: no finite
  record settles either.
- No answer in the prefix leaves liveness UNSETTLED, and the wait for it
  resolves only through the declared on_expiry, with the contract of
  w14-silence-expiry (mirrored here, see expire()). A missing, unknown or
  permit-word on_expiry, or one that is not an exact str, is config_error,
  checked before anything runs.

build_list() returns the checkable list: one certificate per program with a
clean, answered prefix, in input order; duplicate program ids are refused. check_certificate() replays a program and confirms a
certificate, so each entry carries evidence a machine can re-check.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

REFUSE, SCOPED, UNSETTLED, CONFIG_ERROR = "refuse", "scoped", "unsettled", "config_error"
CLEAN_THROUGH, NEVER, EVENTUALLY = "clean_through", "never", "eventually"
CLAIMS = (CLEAN_THROUGH, NEVER, EVENTUALLY)

# ---------------------------------------------------------------------------
# Mirror of the w14-silence-expiry contract (experiments/2026-11-05/
# w14-silence-expiry on main): on_expiry values, rule keys, ladder and
# deadline checks, fallback validation, terminal states and journal kinds.
# The regression tests compare this mirror with the w14 package when it is
# present beside this folder, and with its documented behaviour always.
DENY, SAFE_FALLBACK, ESCALATE, HOLD = "deny", "safe_fallback", "escalate", "hold"
ON_EXPIRY = (DENY, SAFE_FALLBACK, ESCALATE, HOLD)
RULE_KEYS = frozenset({"requires_approval", "ladder", "deadline_s", "deadline_seconds", "on_expiry", "quorum"})
FELL_BACK, DENIED_ON_TIMEOUT, HELD, EXHAUSTED = "fell_back", "denied_on_timeout", "held", "exhausted"
J_RAISED, J_EXPIRED, J_TIER = "escalation.raised", "expired_no_answer", "tier.advanced"
J_FALLBACK, J_DENIED, J_HELD, J_EXHAUSTED = "fallback_on_timeout", "denied_on_timeout", "held_on_timeout", \
    "escalation.exhausted"
RISK_RANK = {"read_only": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


class _ConfigError(Exception):
    pass


def parse_on_expiry(raw):
    """w14 _parse_on_expiry, stricter on type: None is missing; the value
    must be an exact str (type(raw) is str), so a str subclass whose __str__
    or lower() reports a different word than its value is refused; it is
    lower-cased; only the four members are accepted. Anything else (the
    permit word in any case included) is a config error. w14 itself accepts
    str subclasses; this divergence is deliberate and documented."""
    if raw is None:
        raise _ConfigError("missing on_expiry")
    if type(raw) is not str:
        raise _ConfigError("on_expiry must be an exact str")
    value = raw.lower()
    if value not in ON_EXPIRY:
        raise _ConfigError("unknown on_expiry")
    return ON_EXPIRY[ON_EXPIRY.index(value)]


def _rank(risk):
    if risk not in RISK_RANK:
        raise _ConfigError("unknown risk")
    return RISK_RANK[risk]


def _fallback(tool, actions):
    """w14 validated_fallback: None when the tool names no fallback; a
    config error when the named fallback is unregistered, itself, or not
    strictly lower risk (checked for every action that names one)."""
    spec = actions.get(tool, {})
    target = spec.get("safe_fallback")
    if not target:
        return None
    for name, s in actions.items():
        t = s.get("safe_fallback")
        if not t:
            continue
        try:
            registered = t in actions
        except TypeError:
            raise _ConfigError("unhashable fallback")
        if not registered:
            problem = True
        elif t == name:
            problem = True
        else:
            if "risk" not in actions[t] or "risk" not in s:
                raise _ConfigError("missing risk")
            problem = _rank(str(actions[t]["risk"])) >= _rank(str(s["risk"]))
        if problem and name == tool:
            raise _ConfigError("invalid fallback")
    return str(target)


def _rule(body):
    if type(body) is not dict:
        raise _ConfigError("rule must be an object")
    if set(body) - RULE_KEYS:
        raise _ConfigError("unknown rule keys")
    requires = True if "requires_approval" not in body else bool(body["requires_approval"])
    if not requires:
        raise _ConfigError("an ungated rule cannot hold a wait")
    try:
        ladder = tuple(str(x) for x in body.get("ladder", ()))
        deadline = int(body.get("deadline_s", body.get("deadline_seconds", 0)))
        quorum = int(body.get("quorum", 1))
    except (TypeError, ValueError, OverflowError):
        raise _ConfigError("malformed rule")
    on_expiry = parse_on_expiry(body.get("on_expiry"))
    if quorum < 1 or not ladder or deadline <= 0 or quorum > len(ladder):
        raise _ConfigError("bad ladder, deadline or quorum")
    return on_expiry, ladder, deadline


def expire(rule_body, tool, actions):
    """Resolve an unanswered wait the way w14's engine does when every tier
    deadline passes with no answer. Returns (terminal state, journal kinds),
    or (CONFIG_ERROR, ()) for a rule or fallback the w14 loader or propose()
    would reject. No branch returns an approval."""
    try:
        if type(actions) is not dict or any(type(v) is not dict for v in actions.values()):
            raise _ConfigError("actions must map tools to objects")
        on_expiry, ladder, _ = _rule(rule_body)
        _fallback(tool, actions)
    except _ConfigError:
        return CONFIG_ERROR, ()
    journal = [J_RAISED]
    tier = 0
    while True:
        journal.append(J_EXPIRED)
        if on_expiry == ESCALATE:
            tier += 1
            if tier >= len(ladder):
                journal.append(J_EXHAUSTED)
                return EXHAUSTED, tuple(journal)
            journal.append(J_TIER)
            continue
        if on_expiry == HOLD:
            journal.append(J_HELD)
            return HELD, tuple(journal)
        if on_expiry == SAFE_FALLBACK and _fallback(tool, actions):
            journal.append(J_FALLBACK)
            return FELL_BACK, tuple(journal)
        journal.append(J_DENIED)
        return DENIED_ON_TIMEOUT, tuple(journal)


# ---------------------------------------------------------------------------
# Programs and the gate.

@dataclass(frozen=True)
class Program:
    """An infinite event trace written as a finite stem followed by a
    repeating cycle. The gate reads it only through prefix()."""
    program_id: str
    stem: Tuple[str, ...]
    cycle: Tuple[str, ...]


@dataclass(frozen=True)
class Gate:
    forbidden: Tuple[str, ...]
    answer: str
    expiry_rule: dict
    tool: str
    actions: dict


@dataclass(frozen=True)
class Certificate:
    program_id: str
    clean_through: int
    answered_at: int


@dataclass(frozen=True)
class Verdict:
    program_id: str
    status: str
    observed: int
    violation_at: Optional[int]
    certificate: Optional[Certificate]
    expiry: Optional[str]
    journal: Tuple[str, ...]


def _is_str(x):
    return type(x) is str and x != ""


def _valid_program(p):
    if type(p) is not Program or not _is_str(p.program_id):
        return False
    if type(p.stem) is not tuple or type(p.cycle) is not tuple or not p.cycle:
        return False
    return all(_is_str(e) for e in p.stem + p.cycle)


def _valid_gate(g):
    if type(g) is not Gate:
        return False
    if type(g.forbidden) is not tuple or not g.forbidden or not all(_is_str(e) for e in g.forbidden):
        return False
    return _is_str(g.answer) and g.answer not in g.forbidden and _is_str(g.tool)


def _valid_budget(n):
    return type(n) is int and n >= 0


def prefix(p, n):
    """The first n events of the program's trace."""
    out = list(p.stem[:n])
    i = 0
    while len(out) < n:
        out.append(p.cycle[i % len(p.cycle)])
        i += 1
    return tuple(out)


def _config_error(pid):
    return Verdict(pid, CONFIG_ERROR, 0, None, None, None, ())


def evaluate(program, gate, n):
    """Watch n steps and report what that prefix settles."""
    pid = program.program_id if type(program) is Program and type(program.program_id) is str else ""
    if not (_valid_program(program) and _valid_gate(gate) and _valid_budget(n)):
        return _config_error(pid)
    terminal, journal = expire(gate.expiry_rule, gate.tool, gate.actions)
    if terminal == CONFIG_ERROR:
        return _config_error(pid)
    seen = prefix(program, n)
    for i, e in enumerate(seen):
        if e in gate.forbidden:
            return Verdict(pid, REFUSE, n, i, None, None, ())
    if gate.answer not in seen:
        return Verdict(pid, UNSETTLED, n, None, None, terminal, journal)
    cert = Certificate(pid, n, seen.index(gate.answer))
    return Verdict(pid, SCOPED, n, None, cert, None, ())


def certify(program, gate, n, claim):
    """A certificate request. Only clean_through can be issued; a standing
    never or eventually claim is UNSETTLED on any clean prefix."""
    if type(claim) is not str or claim not in CLAIMS:
        return _config_error(program.program_id if type(program) is Program else "")
    v = evaluate(program, gate, n)
    if v.status in (CONFIG_ERROR, REFUSE):
        return v
    if claim == CLEAN_THROUGH:
        seen = prefix(program, n)
        at = seen.index(gate.answer) if gate.answer in seen else -1
        return Verdict(v.program_id, SCOPED, n, None, Certificate(v.program_id, n, at), None, ())
    return Verdict(v.program_id, UNSETTLED, n, None, None, None, ())


def check_certificate(program, gate, cert):
    """Replay the program and confirm the certificate's scoped claim."""
    if type(cert) is not Certificate or not _valid_program(program) or not _valid_gate(gate):
        return False
    if cert.program_id != program.program_id or not _valid_budget(cert.clean_through):
        return False
    seen = prefix(program, cert.clean_through)
    if any(e in gate.forbidden for e in seen):
        return False
    if type(cert.answered_at) is not int:
        return False
    if cert.answered_at == -1:
        return gate.answer not in seen
    return 0 <= cert.answered_at < len(seen) and seen[cert.answered_at] == gate.answer \
        and gate.answer not in seen[:cert.answered_at]


def build_list(programs, gate, n):
    """The checkable list: certificates for every program whose n-step prefix
    is clean and answered, in input order. Returns None when the gate, budget
    or program set is unusable, including two programs that share an id (a
    certificate binds only the id, so a shared id would let one program's
    clean record stand for another's)."""
    if not _valid_gate(gate) or not _valid_budget(n) or type(programs) is not tuple:
        return None
    if expire(gate.expiry_rule, gate.tool, gate.actions)[0] == CONFIG_ERROR:
        return None
    ids = [p.program_id for p in programs if _valid_program(p)]
    if len(set(ids)) != len(ids):
        return None
    out = []
    for p in programs:
        v = evaluate(p, gate, n)
        if v.status == CONFIG_ERROR:
            return None
        if v.status == SCOPED:
            out.append(v.certificate)
    return tuple(out)
