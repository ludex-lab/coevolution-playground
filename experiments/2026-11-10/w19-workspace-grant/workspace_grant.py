"""w19-workspace-grant: one grant per workspace, issued before the action.

Clean-room Python 3 stdlib method sketch of the approval-unit shift in
arXiv 2611.08516 (Aegis OS): instead of a prompt for every action, an
operator issues one workspace grant up front and actions inside it pass
without further prompts. Not a port: no sandbox, no proxy, no ledger, no
daemon, no protocol server; nothing from the upstream repository is used.

A ``Grant`` names a workspace root, the path prefixes inside it that may be
written, the egress hosts that may be reached, when it was issued, how long
it lasts (``ttl``) and what happens when it lapses (``on_expiry``).

``decide(grant, action)`` returns ``pass_within_grant`` only when all hold:

* a grant exists, is exactly a ``Grant`` (no subclass) and its
  configuration is valid;
* the grant was issued strictly before the action time;
* the action time is before ``issued_at + ttl``;
* the action's path (if any) normalises to a path at or below one of the
  grant's prefixes, matched on whole segments;
* the action's egress host (if any) is exactly one of the grant's hosts;
* no external claim marks the action as touching something another agent
  holds (the path itself, a path below it, or any action when the claim
  input is ``True``).

Everything else fails closed. A missing grant, a grant issued at or after
the action, a path or host outside the grant and a claimed path are
``deny``. Malformed input is ``hold``. A grant whose configuration is
invalid, including a missing or unknown ``on_expiry``, is ``hold`` with
reason ``config_error``. Once the ttl has passed the outcome is exactly the
grant's declared ``on_expiry``: ``deny``, ``safe_fallback``, ``escalate`` or
``hold``. None of those is a pass, and there is no way to extend a grant
from inside this layer: silence, a quiet period or a missing objection
never renews it. A later grant must be issued, before the action.

Paths are handled as strings only; nothing touches a filesystem.

Trust boundary: the layer trusts whatever ``Grant`` value it is handed.
Who issued it, whether it is authentic or unmodified, whom it is bound to
and whether it is replayed are out of scope here.
"""

from dataclasses import dataclass, field
from typing import FrozenSet, Optional, Tuple

PASS_WITHIN_GRANT = "pass_within_grant"
DENY = "deny"
HOLD = "hold"
SAFE_FALLBACK = "safe_fallback"
ESCALATE = "escalate"
ON_EXPIRY = (DENY, SAFE_FALLBACK, ESCALATE, HOLD)
OUTCOMES = (PASS_WITHIN_GRANT,) + ON_EXPIRY

# Reasons.
NO_GRANT = "no_grant"
CONFIG_ERROR = "config_error"
BAD_ACTION = "bad_action"
BAD_TIME = "bad_time"
BAD_CLAIMS = "bad_claims"
NOT_BEFORE_ACTION = "grant_not_issued_before_action"
EXPIRED = "expired"
PATH_MALFORMED = "path_malformed"
PATH_ESCAPE = "path_escape"
OUTSIDE_WORKSPACE = "path_outside_workspace"
PATH_OUTSIDE_GRANT = "path_outside_grant"
EGRESS_MALFORMED = "egress_malformed"
EGRESS_OUTSIDE_GRANT = "egress_outside_grant"
CLAIMED_BY_OTHER = "claimed_by_other"
CONTAINS_CLAIMED = "path_contains_claimed_path"


@dataclass(frozen=True)
class Grant:
    grant_id: str
    root: str
    prefixes: Tuple[str, ...]
    egress: FrozenSet[str]
    issued_at: int
    ttl: int
    on_expiry: Optional[str] = None


@dataclass(frozen=True)
class Action:
    at: int
    path: Optional[str] = None
    egress: Optional[str] = None


@dataclass(frozen=True)
class Decision:
    outcome: str
    reasons: Tuple[str, ...]
    grant_id: Optional[str] = None
    detail: Tuple[str, ...] = field(default=())


def _is_time(v):
    """A real ``int`` (not bool, float, str, None, NaN or infinity)."""
    return type(v) is int


# --------------------------------------------------------------------------
# Paths, as strings only.

class PathError(ValueError):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


_BAD_CHARS = ("\\", "\x00", "%", "~", "$")


def split_path(p):
    """Absolute path -> tuple of segments. Empty and ``.`` segments
    collapse (so ``//`` and a trailing slash change nothing). A ``..``
    segment is never resolved: it is an escape. Backslashes, NUL, percent
    escapes, ``~``, ``$`` and control characters are refused, so encoded or
    shell-expanded tricks cannot be smuggled through as names."""
    if type(p) is not str or not p:
        raise PathError(PATH_MALFORMED)
    if any(c in p for c in _BAD_CHARS) or any(ord(c) < 32 or ord(c) == 127 for c in p):
        raise PathError(PATH_MALFORMED)
    if not p.startswith("/"):
        raise PathError(PATH_MALFORMED)
    segs = []
    for s in p.split("/"):
        if s in ("", "."):
            continue
        if s == "..":
            raise PathError(PATH_ESCAPE)
        if s.strip() != s or s.strip(".") == "":
            # leading/trailing spaces, or names made only of dots
            raise PathError(PATH_MALFORMED)
        segs.append(s)
    return tuple(segs)


def resolve(root_segs, p):
    """An action path: absolute, or relative to the workspace root."""
    if type(p) is str and p and not p.startswith("/"):
        p = "/" + "/".join(root_segs) + "/" + p
    return split_path(p)


def under(segs, prefix_segs):
    """Segment-boundary containment: equal, or below a whole segment."""
    return segs[:len(prefix_segs)] == prefix_segs


# --------------------------------------------------------------------------
# Hosts.

def normalise_host(h):
    """ASCII host name, lower-cased, one trailing dot dropped. Any character
    outside printable ASCII is refused before any case mapping, so a
    look-alike such as the Kelvin sign cannot be mapped onto an ASCII
    letter; internationalised names must arrive in their ASCII ``xn--``
    form. Ports, schemes, paths, user info, wildcards and empty labels are
    malformed."""
    if type(h) is not str or not h:
        raise ValueError(EGRESS_MALFORMED)
    if any(ord(c) < 33 or ord(c) > 126 for c in h):
        raise ValueError(EGRESS_MALFORMED)
    h = h.lower()
    if h.endswith("."):
        h = h[:-1]
    if not h or any(c in h for c in ":/@*?#[] \\%"):
        raise ValueError(EGRESS_MALFORMED)
    if any(label == "" for label in h.split(".")):
        raise ValueError(EGRESS_MALFORMED)
    return h


# --------------------------------------------------------------------------
# Grant configuration. Each field is read exactly once into a local and
# checked there; the decision only ever uses those checked copies.

@dataclass(frozen=True)
class _Checked:
    grant_id: str
    root: Tuple[str, ...]
    prefixes: Tuple[Tuple[str, ...], ...]
    hosts: FrozenSet[str]
    issued_at: int
    ttl: int
    on_expiry: str


def _check(grant):
    """(errors, checked copy). Only an exact ``Grant`` is accepted, with
    exact ``str``/``tuple``/``frozenset``/``int`` field types, so subclasses
    with properties or custom iteration fail closed."""
    if type(grant) is not Grant:
        return ("not_a_grant",), None
    gid, root_p, prefixes, egress, issued, ttl, oe = (
        grant.grant_id, grant.root, grant.prefixes, grant.egress,
        grant.issued_at, grant.ttl, grant.on_expiry)
    errs = []
    if type(gid) is not str or not gid:
        errs.append("grant_id")
    try:
        root = split_path(root_p)
        if not root:
            errs.append("root_is_filesystem_root")
    except PathError:
        root = None
        errs.append("root")
    pre = []
    if type(prefixes) is not tuple or not prefixes:
        errs.append("prefixes_empty")
    elif root is not None:
        for p in prefixes:
            try:
                segs = resolve(root, p)
            except PathError:
                errs.append("prefix_malformed")
                continue
            if not under(segs, root):
                errs.append("prefix_outside_workspace")
            pre.append(segs)
    hosts = set()
    if type(egress) is not frozenset:
        errs.append("egress")
    else:
        for h in egress:
            try:
                hosts.add(normalise_host(h))
            except ValueError:
                errs.append("egress_host")
    if not (_is_time(issued) and issued >= 0):
        errs.append("issued_at")
    if not (_is_time(ttl) and ttl > 0):
        errs.append("ttl")
    if type(oe) is not str or oe not in ON_EXPIRY:
        errs.append("on_expiry")
    if errs:
        return tuple(errs), None
    # The module's own constant, never the caller's object.
    return (), _Checked(gid, root, tuple(pre), frozenset(hosts), issued, ttl,
                        ON_EXPIRY[ON_EXPIRY.index(oe)])


def config_errors(grant):
    """Every configuration problem with a grant, as strings. Empty means
    the grant is usable."""
    return _check(grant)[0]


# --------------------------------------------------------------------------
# The decision.

def decide(grant, action, claimed_by_other=False):
    """Decision for one action under one grant. ``claimed_by_other`` is an
    external input from a claim fence (this sketch does not fence claims):
    ``True`` marks the action as touching something held by another agent;
    a frozenset of absolute path prefixes lists what others hold."""
    try:
        return _decide(grant, action, claimed_by_other)
    except Exception:
        return Decision(HOLD, (BAD_ACTION,))


def _decide(grant, action, claimed_by_other):
    if grant is None:
        return Decision(DENY, (NO_GRANT,))
    errs, g = _check(grant)
    if errs:
        gid = grant.grant_id if type(grant) is Grant and type(grant.grant_id) is str else None
        return Decision(HOLD, (CONFIG_ERROR,), gid, errs)
    gid = g.grant_id
    if type(action) is not Action:
        return Decision(HOLD, (BAD_ACTION,), gid)
    at, path, egress = action.at, action.path, action.egress
    if not _is_time(at):
        return Decision(HOLD, (BAD_TIME,), gid)
    if path is None and egress is None:
        return Decision(HOLD, (BAD_ACTION,), gid)
    if type(claimed_by_other) is bool:
        claims = ()
    elif type(claimed_by_other) is frozenset:
        claims = []
        for c in claimed_by_other:
            try:
                claims.append(split_path(c))
            except PathError:
                return Decision(HOLD, (BAD_CLAIMS,), gid)
    else:
        return Decision(HOLD, (BAD_CLAIMS,), gid)

    # Issued strictly before the action.
    if not g.issued_at < at:
        return Decision(DENY, (NOT_BEFORE_ACTION,), gid)
    # Lapsed: exactly the declared on_expiry, never a pass.
    if at >= g.issued_at + g.ttl:
        return Decision(g.on_expiry, (EXPIRED,), gid)

    root = g.root
    reasons = []
    segs = None
    if path is not None:
        try:
            segs = resolve(root, path)
        except PathError as e:
            return Decision(HOLD if e.reason == PATH_MALFORMED else DENY, (e.reason,), gid)
        if not under(segs, root):
            reasons.append(OUTSIDE_WORKSPACE)
        elif not any(under(segs, p) for p in g.prefixes):
            reasons.append(PATH_OUTSIDE_GRANT)
    if egress is not None:
        try:
            host = normalise_host(egress)
        except ValueError:
            return Decision(HOLD, (EGRESS_MALFORMED,), gid)
        if host not in g.hosts:
            reasons.append(EGRESS_OUTSIDE_GRANT)
    if claimed_by_other is True:
        # Applies to every action, egress-only ones included.
        reasons.append(CLAIMED_BY_OTHER)
    elif segs is not None:
        if any(under(segs, c) for c in claims):
            reasons.append(CLAIMED_BY_OTHER)
        elif any(under(c, segs) for c in claims):
            # A write to a parent of a claimed path reaches into it.
            reasons.append(CONTAINS_CLAIMED)
    if reasons:
        return Decision(DENY, tuple(reasons), gid)
    return Decision(PASS_WITHIN_GRANT, (), gid)


def decide_by_id(grants, grant_id, action, claimed_by_other=False):
    """Look the grant up by id in a mapping; an unknown id is no grant."""
    if type(grants) is not dict or type(grant_id) is not str:
        return Decision(DENY, (NO_GRANT,))
    return decide(grants.get(grant_id), action, claimed_by_other)


def prompts_needed(actions, unit):
    """Toy count of human approvals for a run of actions under each
    approval unit: ``per_action`` asks once per action; ``per_workspace``
    asks once per grant, before the run. Shows the shift, measures
    nothing."""
    if unit == "per_action":
        return len(actions)
    if unit == "per_workspace":
        return 1 if actions else 0
    raise ValueError(unit)


def report(decisions):
    """Count of decisions by outcome."""
    out = {o: 0 for o in OUTCOMES}
    for d in decisions:
        out[d.outcome] = out.get(d.outcome, 0) + 1
    return out
