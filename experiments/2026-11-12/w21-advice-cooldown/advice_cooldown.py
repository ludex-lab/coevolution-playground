"""Advice cooldown with micro-contracts: a pure, stdlib-only method sketch.

Not a runtime and not a control plane. There is no loop, no clock, no
thread, no socket and no model or classifier here: select_advice() is one
pure function from (state, history, budget, now) to a decision record.
The caller supplies the time as an integer.

state = {
    "tool": str,                       the tool the agent is about to call
    "args": {str: str},                the arguments it plans to pass
    "contracts": {tool: contract},     micro-contracts, one per tool
    "advice": [advice, ...],           the advice library, in priority order
    "pending": {...}                   optional pending decision (see below)
}
contract = {"required": [arg, ...], "options": {arg: [value, ...]}}
advice   = {"id": str, "tool": str, "when_missing": str or None,
            "args": {str: str}, "tokens": int > 0, "cooldown": int > 0}
history  = [{"advice_id": str, "at": int, "tokens": int}, ...]   past sends
budget   = {"limit": int >= 0}                                   tokens
now      = int >= 0

Rule shortlist: an advice item is a candidate when its tool is the state's
tool and, if it names when_missing, that argument is absent from the
planned args. A candidate is only relevant when a micro-contract exists
for the tool; without one it is not sent.

Each candidate suggests arguments. The suggestion is merged into the
planned args and checked against the contract. A required argument still
missing, or an option value outside the declared list, refuses that
candidate (fail closed): advice never turns a contract violation into a
send. A candidate whose exact advice id was sent less than its cooldown
ago is suppressed; cooldown is keyed by that exact id string, not by the
suggested content. A
candidate whose tokens exceed the remaining budget is not sent; an empty
budget is never an implicit dispatch. The first candidate that passes
every check is sent.

A pending decision {"id", "deadline", "on_expiry"} must declare on_expiry
in (HOLD, ESCALATE, DENY); a missing or other value is a config_error.
When now is at or past the deadline (now >= deadline) the decision is the
declared on_expiry and nothing is sent; a pending item never sends at its
deadline.

Inputs are checked by exact type; subclasses are a config_error. Record
values are None, module constants, exact-str ids from the input, ints
computed here, or tuples of those. select_advice() catches any internal
error and returns config_error; it never raises.
"""

SEND = "send"
NO_SEND = "no_send"
CONFIG_ERROR = "config_error"
HOLD = "HOLD"
ESCALATE = "ESCALATE"
DENY = "DENY"
ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY)
DECISIONS = (SEND, NO_SEND, CONFIG_ERROR) + ON_EXPIRY_VALUES

# per-candidate outcomes, also used as the reason when nothing is sent
SENT = "sent"
NO_CANDIDATE = "no_candidate"
NO_CONTRACT = "no_contract"
REQUIRED_ARG_MISSING = "required_arg_missing"
INVALID_OPTION = "invalid_option"
IN_COOLDOWN = "in_cooldown"
BUDGET_EXHAUSTED = "budget_exhausted"
EXPIRED = "expired"
OUTCOMES = (SENT, NO_CONTRACT, REQUIRED_ARG_MISSING, INVALID_OPTION, IN_COOLDOWN,
            BUDGET_EXHAUSTED)
REASONS = OUTCOMES + (NO_CANDIDATE, EXPIRED, CONFIG_ERROR)

STATE_REQUIRED = ("tool", "args", "contracts", "advice")
STATE_OPTIONAL = ("pending",)
CONTRACT_FIELDS = ("required", "options")
ADVICE_FIELDS = ("id", "tool", "when_missing", "args", "tokens", "cooldown")
HISTORY_FIELDS = ("advice_id", "at", "tokens")
BUDGET_FIELDS = ("limit",)
PENDING_FIELDS = ("id", "deadline", "on_expiry")

RECORD_FIELDS = ("decision", "reason", "sent", "tokens", "remaining", "candidates",
                 "pending_id", "on_expiry")


def _is_str(v):
    return type(v) is str


def _is_int(v):
    return type(v) is int


def _canonical(value, choices):
    if not _is_str(value):
        return None
    for choice in choices:
        if value == choice:
            return choice
    return None


def _exact_keys(mapping, fields, required=None):
    """None if mapping is an exact dict with exact-str keys from fields."""
    if type(mapping) is not dict:
        return "not a mapping"
    for key in mapping:
        # _canonical rejects any key that is not an exact str, without
        # calling the key's own __eq__ or __hash__.
        if _canonical(key, fields) is None:
            return "unknown field"
    for key in (fields if required is None else required):
        if key not in mapping:
            return "missing field"
    return None


def _str_list(value):
    return type(value) is list and all(_is_str(x) and x for x in value)


def _str_map(value):
    if type(value) is not dict:
        return False
    for k in value:
        if not _is_str(k) or not k or not _is_str(value[k]):
            return False
    return True


def _validate_contract(contract):
    err = _exact_keys(contract, CONTRACT_FIELDS)
    if err:
        return "contract: " + err
    if not _str_list(contract["required"]):
        return "contract.required must be a list of strings"
    options = contract["options"]
    if type(options) is not dict:
        return "contract.options must be a mapping"
    for k in options:
        if not _is_str(k) or not k or not _str_list(options[k]) or not options[k]:
            return "contract.options must map an argument to a non-empty list of strings"
    return None


def _validate_advice(item):
    err = _exact_keys(item, ADVICE_FIELDS)
    if err:
        return "advice: " + err
    if not _is_str(item["id"]) or not item["id"] or not _is_str(item["tool"]) or not item["tool"]:
        return "advice id and tool must be non-empty strings"
    wm = item["when_missing"]
    if wm is not None and (not _is_str(wm) or not wm):
        return "advice.when_missing must be None or a non-empty string"
    if not _str_map(item["args"]):
        return "advice.args must map strings to strings"
    if not _is_int(item["tokens"]) or item["tokens"] <= 0:
        return "advice.tokens must be a positive integer"
    if not _is_int(item["cooldown"]) or item["cooldown"] <= 0:
        return "advice.cooldown must be a positive integer"
    return None


def validate(state, history, budget, now):
    """None when the inputs are well formed, else a short error string."""
    err = _exact_keys(state, STATE_REQUIRED + STATE_OPTIONAL, STATE_REQUIRED)
    if err:
        return "state: " + err
    if not _is_str(state["tool"]) or not state["tool"]:
        return "state.tool must be a non-empty string"
    if not _str_map(state["args"]):
        return "state.args must map strings to strings"
    contracts = state["contracts"]
    if type(contracts) is not dict:
        return "state.contracts must be a mapping"
    for tool in contracts:
        if not _is_str(tool) or not tool:
            return "contract tool names must be strings"
        err = _validate_contract(contracts[tool])
        if err:
            return err
    advice = state["advice"]
    if type(advice) is not list:
        return "state.advice must be a list"
    ids = set()
    for item in advice:
        err = _validate_advice(item)
        if err:
            return err
        if item["id"] in ids:
            return "duplicate advice id"
        ids.add(item["id"])
    if not _is_int(now) or now < 0:
        return "now must be a non-negative integer"
    if "pending" in state:
        pending = state["pending"]
        err = _exact_keys(pending, PENDING_FIELDS, ("id", "deadline"))
        if err:
            return "pending: " + err
        if not _is_str(pending["id"]) or not pending["id"]:
            return "pending.id must be a non-empty string"
        if not _is_int(pending["deadline"]) or pending["deadline"] < 0:
            return "pending.deadline must be a non-negative integer"
        if "on_expiry" not in pending:
            return "pending decision declares a deadline without on_expiry"
        if _canonical(pending["on_expiry"], ON_EXPIRY_VALUES) is None:
            return "pending.on_expiry must be one of HOLD, ESCALATE, DENY"
    if type(history) is not list:
        return "history must be a list"
    for entry in history:
        err = _exact_keys(entry, HISTORY_FIELDS)
        if err:
            return "history: " + err
        if not _is_str(entry["advice_id"]) or not entry["advice_id"]:
            return "history.advice_id must be a non-empty string"
        if not _is_int(entry["at"]) or entry["at"] < 0 or entry["at"] > now:
            return "history.at must be an integer between 0 and now"
        if not _is_int(entry["tokens"]) or entry["tokens"] <= 0:
            return "history.tokens must be a positive integer"
    err = _exact_keys(budget, BUDGET_FIELDS)
    if err:
        return "budget: " + err
    if not _is_int(budget["limit"]) or budget["limit"] < 0:
        return "budget.limit must be a non-negative integer"
    return None


def check_contract(contract, args):
    """REQUIRED_ARG_MISSING, INVALID_OPTION or None for a merged call (pure)."""
    for name in contract["required"]:
        if name not in args:
            return REQUIRED_ARG_MISSING
    for name in contract["options"]:
        if name in args and args[name] not in contract["options"][name]:
            return INVALID_OPTION
    return None


def _shortlisted(item, state):
    if item["tool"] != state["tool"]:
        return False
    return item["when_missing"] is None or item["when_missing"] not in state["args"]


def _record(decision, reason, sent=None, tokens=0, remaining=None, candidates=(),
            pending_id=None, on_expiry=None):
    return {"decision": decision, "reason": reason, "sent": sent, "tokens": tokens,
            "remaining": remaining, "candidates": candidates, "pending_id": pending_id,
            "on_expiry": on_expiry}


def _select(state, history, budget, now):
    if validate(state, history, budget, now) is not None:
        return _record(CONFIG_ERROR, CONFIG_ERROR)
    spent = sum(entry["tokens"] for entry in history)
    remaining = budget["limit"] - spent
    pending = state.get("pending")
    pending_id, action = None, None
    if pending is not None:
        pending_id = pending["id"]
        action = _canonical(pending["on_expiry"], ON_EXPIRY_VALUES)
        if now >= pending["deadline"]:
            return _record(action, EXPIRED, None, 0, remaining, (), pending_id, action)
    last_sent = {}
    for entry in history:
        if entry["at"] >= last_sent.get(entry["advice_id"], -1):
            last_sent[entry["advice_id"]] = entry["at"]
    contract = state["contracts"].get(state["tool"])
    candidates = []
    for item in state["advice"]:
        if not _shortlisted(item, state):
            continue
        if contract is None:
            outcome = NO_CONTRACT
        else:
            merged = dict(state["args"])
            merged.update(item["args"])
            outcome = check_contract(contract, merged)
            if outcome is None:
                last = last_sent.get(item["id"])
                if last is not None and now - last < item["cooldown"]:
                    outcome = IN_COOLDOWN
                elif item["tokens"] > remaining:
                    outcome = BUDGET_EXHAUSTED
                else:
                    outcome = SENT
        candidates.append((item["id"], outcome))
        if outcome == SENT:
            return _record(SEND, SENT, item["id"], item["tokens"], remaining - item["tokens"],
                           tuple(candidates), pending_id, action)
    reason = candidates[0][1] if candidates else NO_CANDIDATE
    return _record(NO_SEND, reason, None, 0, remaining, tuple(candidates), pending_id, action)


def select_advice(state, history, budget, now):
    """Decide whether to send one advice item now. Pure; never raises."""
    try:
        return _select(state, history, budget, now)
    except Exception:
        return _record(CONFIG_ERROR, CONFIG_ERROR)
