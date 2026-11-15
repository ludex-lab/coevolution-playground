"""w22-write-precommit: commit writes before any tool result; admit a write
only when every targeting argument is stated in the user request.

Top method sketch of arXiv 2611.17115 (CapLite); not a reproduction.
Clean-room, Python 3 standard library only, pure functions, no I/O.

Policy comes from the tool schemas alone (policy_from_schema). Nothing in
an episode can supply a policy, a program, a graph or a constraint list:
an episode key outside EPISODE_KEYS is a config_error.

An episode is a dict:

    request: the user request (non-empty str)
    schema:  {tool: {"effect": "read" | "write",
                     "targeting": {arg: role}}}   role in ROLES;
             a write tool needs at least one targeting arg, a read tool none
    events:  ordered list, each one of
             {"type": "commit", "call_id", "tool", "args"}
             {"type": "tool_result", "tool", "text"}
             {"type": "write", "call_id", "tool", "args"}

Rules (evaluate):

1. The commit set is frozen at the first applied tool_result. A commit
   event after that point is a late commit: recorded, never admitted, and
   it does not replace an earlier commit for the same call_id.
2. A write event is ADMIT only when all hold:
   - its call_id was committed earlier in the trace and before the
     first tool_result (else not_precommitted);
   - its tool and every targeting arg equal the commit (else retargeted);
   - every targeting arg is present (else missing:<arg>), non-blank
     (else empty:<arg>) and a substring of the request
     (else unstated:<arg>);
   - its commit has not already produced an admitted write
     (else already_executed).
   Anything else is REFUSE. Tool-result text is never read by the check.
3. Non-targeting args (a body, a subject) are free; they decide what a
   write says, not whom or what it affects.

There is no timeout in this design, so no on_expiry is declared.
"""

ADMIT = "ADMIT"
REFUSE = "REFUSE"
OK = "ok"
CONFIG_ERROR = "config_error"
ON_UNMEASURED = "on_unmeasured"

ROLES = ("recipient", "amount", "object", "destination")
EFFECTS = ("read", "write")
EPISODE_KEYS = ("request", "schema", "events")
EVENT_KEYS = {
    "commit": ("type", "call_id", "tool", "args"),
    "tool_result": ("type", "tool", "text"),
    "write": ("type", "call_id", "tool", "args"),
}


class ConfigError(ValueError):
    pass


def _is_str(x):
    return type(x) is str


def policy_from_schema(schema):
    """Return {write_tool: (targeting arg names, sorted)} from tool schemas."""
    if type(schema) is not dict or not schema:
        raise ConfigError("schema must be a non-empty dict")
    policy = {}
    for tool, spec in schema.items():
        if not _is_str(tool) or not tool:
            raise ConfigError("tool name must be a non-empty str")
        if type(spec) is not dict or set(spec) != {"effect", "targeting"}:
            raise ConfigError("tool %r needs exactly effect and targeting" % tool)
        effect, targeting = spec["effect"], spec["targeting"]
        if not _is_str(effect) or effect not in EFFECTS:
            raise ConfigError("tool %r effect must be read or write" % tool)
        if type(targeting) is not dict:
            raise ConfigError("tool %r targeting must be a dict" % tool)
        for arg, role in targeting.items():
            if not _is_str(arg) or not arg or not _is_str(role) or role not in ROLES:
                raise ConfigError("tool %r targeting %r: bad arg or role" % (tool, arg))
        if effect == "write" and not targeting:
            raise ConfigError("write tool %r has no targeting arg" % tool)
        if effect == "read" and targeting:
            raise ConfigError("read tool %r must not declare targeting" % tool)
        if effect == "write":
            policy[tool] = tuple(sorted(targeting))
    return policy


def _validate(episode):
    if type(episode) is not dict:
        raise ConfigError("episode must be a dict")
    extra = set(episode) - set(EPISODE_KEYS)
    if extra:
        raise ConfigError("episode keys not permitted: %s" % ", ".join(sorted(map(str, extra))))
    for key in EPISODE_KEYS:
        if key not in episode:
            raise ConfigError("episode missing %s" % key)
    request = episode["request"]
    if not _is_str(request) or not request.strip():
        raise ConfigError("request must be a non-empty str")
    schema = episode["schema"]
    policy = policy_from_schema(schema)
    events = episode["events"]
    if type(events) is not list:
        raise ConfigError("events must be a list")
    early_ids = set()
    seen_result = False
    for i, ev in enumerate(events):
        if type(ev) is not dict or not _is_str(ev.get("type")) or ev["type"] not in EVENT_KEYS:
            raise ConfigError("event %d: bad type" % i)
        kind = ev["type"]
        if set(ev) != set(EVENT_KEYS[kind]):
            raise ConfigError("event %d: keys must be %s" % (i, ", ".join(EVENT_KEYS[kind])))
        tool = ev["tool"]
        if not _is_str(tool) or tool not in schema:
            raise ConfigError("event %d: unknown tool" % i)
        if kind == "tool_result":
            if schema[tool]["effect"] != "read":
                raise ConfigError("event %d: tool_result from a non-read tool" % i)
            if not _is_str(ev["text"]):
                raise ConfigError("event %d: text must be a str" % i)
            seen_result = True
            continue
        if tool not in policy:
            raise ConfigError("event %d: %s names a read tool" % (i, kind))
        if not _is_str(ev["call_id"]) or not ev["call_id"]:
            raise ConfigError("event %d: call_id must be a non-empty str" % i)
        args = ev["args"]
        if type(args) is not dict:
            raise ConfigError("event %d: args must be a dict" % i)
        for name, value in args.items():
            if not _is_str(name) or not _is_str(value):
                raise ConfigError("event %d: arg names and values must be str" % i)
        if kind == "commit" and not seen_result:
            if ev["call_id"] in early_ids:
                raise ConfigError("event %d: duplicate commit %r" % (i, ev["call_id"]))
            early_ids.add(ev["call_id"])
    return request, policy, events


def check_write(request, policy, commit, write):
    """Reasons a write is refused (empty list means ADMIT). commit is the
    frozen pre-result commit for write's call_id, or None."""
    reasons = []
    if commit is None:
        reasons.append("not_precommitted")
    elif commit["tool"] != write["tool"]:
        reasons.append("retargeted")
    else:
        for arg in policy[write["tool"]]:
            if commit["args"].get(arg) != write["args"].get(arg):
                reasons.append("retargeted")
                break
    for arg in policy[write["tool"]]:
        if arg not in write["args"]:
            reasons.append("missing:" + arg)
            continue
        value = write["args"][arg]
        if not value.strip():
            reasons.append("empty:" + arg)
        elif value not in request:
            reasons.append("unstated:" + arg)
    return reasons


def evaluate(episode):
    """Pure decision over one episode. Returns a dict with status OK and a
    decision per write event, or status CONFIG_ERROR and an error."""
    try:
        request, policy, events = _validate(episode)
    except ConfigError as exc:
        return {"status": CONFIG_ERROR, "error": str(exc)}
    commits = {}
    frozen = False
    late = []
    used = set()
    decisions = []
    for index, ev in enumerate(events):
        kind = ev["type"]
        if kind == "tool_result":
            frozen = True
        elif kind == "commit":
            if frozen:
                late.append(ev["call_id"])
            else:
                commits[ev["call_id"]] = {"tool": ev["tool"], "args": dict(ev["args"])}
        else:
            call_id = ev["call_id"]
            reasons = check_write(request, policy, commits.get(call_id), ev)
            if call_id in used:
                reasons.append("already_executed")
            decision = ADMIT if not reasons else REFUSE
            if decision == ADMIT:
                used.add(call_id)
            decisions.append({"index": index, "call_id": call_id,
                              "decision": decision, "reasons": reasons})
    return {"status": OK, "decisions": decisions, "late_commits": late}


def paper_results():
    """The paper's episode, utility and token figures are not measured here."""
    return {"status": ON_UNMEASURED, "see": "paper_evidence.json"}
