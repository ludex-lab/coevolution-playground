"""Rule oracle for silent conversation-information loss across two toy API dialects.

Clean-room Python 3 standard-library method sketch of the idea in arXiv
2611.15543 ("Testing Conversation Preservation Across LLM APIs: A
Rule-Based Oracle for Detecting Silent Information Loss"). Not a
reproduction and not the authors' code: the dialects, the intermediate
record, the rule ids, the rules and the target limits below are this
sketch's own declared choices. No upstream code or rule text is used.

A case is {"case_id", "source", "target", "profile"}:

- source: a request in dialect A (the source dialect):
    {"system": str ("" means none),
     "messages": [ {"role": "user"|"assistant", "content": str}
                 | {"role": "assistant",
                    "tool_call": {"id": str, "name": str, "args": {str: str}}}
                 | {"role": "tool", "call_id": str,
                    "result": str | [str, ...], "is_error": bool} ],
     "tools": [str, ...]             (declared tool names, unique),
     "controls": {"max_tokens"?: int, "temperature_milli"?: int,
                  "thinking_budget"?: int}}
  A list-valued tool result is a sequence of text parts; dialect A
  defines its text as the parts joined with "\\n".
- target: the translated request in dialect B (the target dialect):
    {"preamble"?: str,
     "turns": [ {"speaker": "human"|"model", "text": str}
              | {"speaker": "model",
                 "invoke": {"ref": str, "fn": str, "params": {str: str}}}
              | {"speaker": "tool", "ref": str, "output": str,
                 "failed"?: bool} ],
     "functions": [{"name": str}, ...],
     "settings"?: {"max_output"?: int, "temperature_milli"?: int,
                   "reasoning_budget"?: int}}
  "failed" is optional and defaults to false, as in many real schemas.
- profile: the declared limits of the target endpoint:
    {"has_system": bool, "alternating": bool,
     "controls": [control names the target supports],
     "max_tokens_cap": int}
  A profile that has no system field and also requires alternation is
  out of scope for this toy (config_error).

Dialect B can express everything dialect A can (a lossless-capable
encoding, see encode_b). Its declared encoding: system -> preamble (or, when
the target has no system field, a first "human" turn holding the system
text); role -> speaker (user -> human, assistant -> model); tool_call ->
invoke (call ids may be re-minted consistently); a list result -> its
"\\n"-joined text; is_error -> failed; tools -> functions; max_tokens ->
max_output, thinking_budget -> reasoning_budget; when the target requires
alternation, two adjacent same-role text messages are merged with "\\n";
an unsupported control is dropped and max_tokens is clamped to the cap.

Both payloads map to one intermediate record (a ConvIR-like record):
{"system": str, "messages": tuple, "tools": sorted tuple of names,
 "controls": sorted tuple of (name, int)}, where a message is
("text", role, text), ("call", name, sorted args pairs) or
("result", link, text, is_error) and link is the position of the answered
call among the calls (so consistently re-minted ids are not a change).

Two arms score each case:

- baseline: the toy static target check, schema_check(target, profile),
  only. PASS when the payload is a well-typed dialect-B request that the
  target's declared limits accept.
- rule arm: the same static check, then rules(source IR, target IR,
  profile). Each finding is (rule id, field path, status) where status is
  "avoidable" (the target could have preserved it) or "forced" (the
  declared target limits made it necessary). The rule arm FAILs a case
  with any avoidable finding or a failed static check; forced findings are
  reported, not faults. Paths are ConvIR paths; message indices are source
  positions.

Malformed input is config_error. Every dict key, at every level, must be an
exact str, and that is checked before any lookup in the dict; values are
checked by exact type (subclasses of str, int, bool, list and dict are
rejected; bool is not int). validate() reads each caller value once and
returns a private snapshot (the source as its IR, the target as fresh
dicts and lists); everything after it runs only on that snapshot.
evaluate() never raises. No timeout or expiry exists in this design. No
clock, no network, no files, no model.
"""

PASS = "PASS"
FAIL = "FAIL"
OK = "ok"
CONFIG_ERROR = "config_error"
ON_UNMEASURED = "on_unmeasured"
AVOIDABLE = "avoidable"
FORCED = "forced"

JOIN = "\n"
MAX_DEPTH = 8
ROLES = ("user", "assistant")
CONTROLS = ("max_tokens", "temperature_milli", "thinking_budget")
SPEAKER = {"user": "human", "assistant": "model"}
ROLE_OF = {"human": "user", "model": "assistant"}
SETTING = {"max_output": "max_tokens", "temperature_milli": "temperature_milli",
           "reasoning_budget": "thinking_budget"}
SETTING_OF = {"max_tokens": "max_output", "temperature_milli": "temperature_milli",
              "thinking_budget": "reasoning_budget"}

CASE_FIELDS = ("case_id", "profile", "source", "target")
SOURCE_FIELDS = ("controls", "messages", "system", "tools")
PROFILE_FIELDS = ("alternating", "controls", "has_system", "max_tokens_cap")
TEXT_FIELDS = ("content", "role")
CALL_FIELDS = ("role", "tool_call")
CALL_INNER = ("args", "id", "name")
RESULT_FIELDS = ("call_id", "is_error", "result", "role")
B_REQUIRED = ("functions", "turns")
B_OPTIONAL = ("preamble", "settings")

RULES = {
    "CL01": "system_dropped",
    "CL02": "system_altered",
    "CL03": "system_demoted",
    "CL04": "role_changed",
    "CL05": "text_altered",
    "CL06": "messages_reordered",
    "CL07": "message_dropped",
    "CL08": "same_role_merge",
    "CL09": "cross_role_merge",
    "CL10": "message_mismatch",
    "CL11": "tool_call_renamed",
    "CL12": "tool_call_args_altered",
    "CL13": "tool_result_relinked",
    "CL14": "tool_result_altered",
    "CL15": "tool_error_flag_dropped",
    "CL16": "tool_error_flag_injected",
    "CL17": "tool_definition_dropped",
    "CL18": "tool_definition_injected",
    "CL19": "control_dropped",
    "CL20": "control_injected",
    "CL21": "control_altered",
}


class _Bad(Exception):
    """Internal: a config_error with its detail."""


def paper_results():
    """The paper's figures are not measured here."""
    return ON_UNMEASURED


def _id(v):
    return type(v) is str and v.strip() != ""


def _keys(d, detail):
    """Raise _Bad(detail) unless every key of the exact dict d is an exact str.

    Runs before any lookup in d: iterating an exact dict runs no caller
    code, so no caller-defined __eq__ or __hash__ is reached afterwards.
    """
    for k in d:
        if type(k) is not str:
            raise _Bad(detail)


def _fields(d, names, detail):
    """d is an exact dict whose keys are exact str; its keys must be names."""
    if sorted(d) != sorted(names):
        raise _Bad(detail)


def _str_map(d, detail):
    """An exact {str: str} dict as a sorted tuple of pairs."""
    if type(d) is not dict:
        raise _Bad(detail)
    _keys(d, detail)
    out = []
    for k, v in list(d.items()):
        if type(v) is not str:
            raise _Bad(detail)
        out.append((k, v))
    return tuple(sorted(out))


def _controls(d, detail):
    if type(d) is not dict:
        raise _Bad(detail)
    _keys(d, detail)
    out = []
    for k, v in list(d.items()):
        if k not in CONTROLS or type(v) is not int or v < 0:
            raise _Bad(detail)
        out.append((k, v))
    return tuple(sorted(out))


def _source(src):
    """Validate a dialect-A request and return its intermediate record."""
    if type(src) is not dict:
        raise _Bad("source_not_dict")
    _keys(src, "source_key_invalid")
    _fields(src, SOURCE_FIELDS, "source_fields_invalid")
    system = src["system"]
    if type(system) is not str:
        raise _Bad("source_system_invalid")
    tools_in = src["tools"]
    if type(tools_in) is not list:
        raise _Bad("source_tools_invalid")
    tools = []
    for name in tuple(tools_in):
        if not _id(name) or name in tools:
            raise _Bad("source_tools_invalid")
        tools.append(name)
    controls = _controls(src["controls"], "source_controls_invalid")
    msgs_in = src["messages"]
    if type(msgs_in) is not list:
        raise _Bad("source_messages_invalid")
    messages = []
    ids = []
    for m in tuple(msgs_in):
        if type(m) is not dict:
            raise _Bad("source_message_invalid")
        _keys(m, "source_message_key_invalid")
        keys = sorted(m)
        role = m.get("role")
        if keys == list(TEXT_FIELDS):
            if type(role) is not str or role not in ROLES:
                raise _Bad("source_role_invalid")
            if type(m["content"]) is not str:
                raise _Bad("source_content_invalid")
            messages.append(("text", role, m["content"]))
        elif keys == list(CALL_FIELDS):
            if type(role) is not str or role != "assistant":
                raise _Bad("source_role_invalid")
            call = m["tool_call"]
            if type(call) is not dict:
                raise _Bad("source_call_invalid")
            _keys(call, "source_call_invalid")
            _fields(call, CALL_INNER, "source_call_invalid")
            cid = call["id"]
            name = call["name"]
            if not _id(cid) or cid in ids:
                raise _Bad("source_call_id_invalid")
            if type(name) is not str or name not in tools:
                raise _Bad("source_call_name_unknown")
            args = _str_map(call["args"], "source_call_args_invalid")
            ids.append(cid)
            messages.append(("call", name, args))
        elif keys == list(RESULT_FIELDS):
            if type(role) is not str or role != "tool":
                raise _Bad("source_role_invalid")
            cid = m["call_id"]
            if type(cid) is not str or cid not in ids:
                raise _Bad("source_result_link_invalid")
            result = m["result"]
            if type(result) is str:
                text = result
            elif type(result) is list:
                parts = tuple(result)
                for p in parts:
                    if type(p) is not str:
                        raise _Bad("source_result_invalid")
                text = JOIN.join(parts)
            else:
                raise _Bad("source_result_invalid")
            err = m["is_error"]
            if type(err) is not bool:
                raise _Bad("source_is_error_invalid")
            messages.append(("result", ids.index(cid), text, err))
        else:
            raise _Bad("source_message_shape")
    return {"system": system, "messages": tuple(messages), "tools": tuple(sorted(tools)),
            "controls": controls}


def _profile(p):
    if type(p) is not dict:
        raise _Bad("profile_not_dict")
    _keys(p, "profile_key_invalid")
    _fields(p, PROFILE_FIELDS, "profile_fields_invalid")
    has_system = p["has_system"]
    alternating = p["alternating"]
    if type(has_system) is not bool or type(alternating) is not bool:
        raise _Bad("profile_flag_invalid")
    if not has_system and alternating:
        raise _Bad("profile_combination_unsupported")
    names = p["controls"]
    if type(names) is not list:
        raise _Bad("profile_controls_invalid")
    controls = []
    for n in tuple(names):
        if type(n) is not str or n not in CONTROLS or n in controls:
            raise _Bad("profile_controls_invalid")
        controls.append(n)
    cap = p["max_tokens_cap"]
    if type(cap) is not int or cap <= 0:
        raise _Bad("profile_cap_invalid")
    return {"has_system": has_system, "alternating": alternating,
            "controls": tuple(sorted(controls)), "max_tokens_cap": cap}


def _tree(v, depth):
    """A fresh copy of a JSON-like value: exact dict, list, str, int, bool."""
    if depth > MAX_DEPTH:
        raise _Bad("target_too_deep")
    t = type(v)
    if t is dict:
        _keys(v, "target_key_invalid")
        return dict((k, _tree(x, depth + 1)) for k, x in list(v.items()))
    if t is list:
        return [_tree(x, depth + 1) for x in tuple(v)]
    if t is str or t is int or t is bool:
        return v
    raise _Bad("target_value_invalid")


def validate(case):
    """Return a private snapshot of case, or raise _Bad(detail)."""
    if type(case) is not dict:
        raise _Bad("case_not_dict")
    _keys(case, "case_key_invalid")
    for name in CASE_FIELDS:
        if name not in case:
            raise _Bad(name + "_missing")
    _fields(case, CASE_FIELDS, "case_unknown_field")
    case_id = case["case_id"]
    if not _id(case_id):
        raise _Bad("case_id_invalid")
    profile = _profile(case["profile"])
    source = _source(case["source"])
    target = _tree(case["target"], 0)
    return {"case_id": case_id, "profile": profile, "source": source, "target": target}


def schema_check(t, profile):
    """The toy static target check. None when accepted, else (code, path)."""
    if type(t) is not dict:
        return ("payload_not_object", "")
    for k in sorted(t):
        if k not in B_REQUIRED + B_OPTIONAL:
            return ("unknown_field", k)
    for k in B_REQUIRED:
        if k not in t:
            return ("missing_field", k)
    if "preamble" in t:
        if not profile["has_system"]:
            return ("preamble_unsupported", "preamble")
        if type(t["preamble"]) is not str or t["preamble"] == "":
            return ("preamble_invalid", "preamble")
    fns = t["functions"]
    if type(fns) is not list:
        return ("functions_invalid", "functions")
    names = []
    for i, f in enumerate(fns):
        path = "functions[%d]" % i
        if type(f) is not dict or sorted(f) != ["name"]:
            return ("function_invalid", path)
        if not _id(f["name"]) or f["name"] in names:
            return ("function_name_invalid", path + ".name")
        names.append(f["name"])
    settings = t["settings"] if "settings" in t else {}
    if type(settings) is not dict:
        return ("settings_invalid", "settings")
    for k in sorted(settings):
        path = "settings." + k
        if k not in SETTING:
            return ("setting_unknown", path)
        v = settings[k]
        if type(v) is not int or v < 0:
            return ("setting_invalid", path)
        if SETTING[k] not in profile["controls"]:
            return ("setting_unsupported", path)
        if k == "max_output" and v > profile["max_tokens_cap"]:
            return ("setting_over_cap", path)
    turns = t["turns"]
    if type(turns) is not list:
        return ("turns_invalid", "turns")
    refs = []
    prev_text = None
    for i, turn in enumerate(turns):
        path = "turns[%d]" % i
        if type(turn) is not dict:
            return ("turn_invalid", path)
        sp = turn["speaker"] if "speaker" in turn else None
        keys = sorted(turn)
        if sp in ("human", "model") and keys == ["speaker", "text"]:
            if type(turn["text"]) is not str:
                return ("turn_text_invalid", path + ".text")
            if profile["alternating"] and prev_text == sp:
                return ("alternation_violated", path)
            prev_text = sp
            continue
        if sp == "model" and keys == ["invoke", "speaker"]:
            inv = turn["invoke"]
            if type(inv) is not dict or sorted(inv) != ["fn", "params", "ref"]:
                return ("invoke_invalid", path + ".invoke")
            if not _id(inv["ref"]) or inv["ref"] in refs:
                return ("invoke_ref_invalid", path + ".invoke.ref")
            if type(inv["fn"]) is not str or inv["fn"] not in names:
                return ("invoke_fn_undeclared", path + ".invoke.fn")
            params = inv["params"]
            if type(params) is not dict or [v for v in params.values() if type(v) is not str]:
                return ("invoke_params_invalid", path + ".invoke.params")
            refs.append(inv["ref"])
        elif sp == "tool" and keys in (["output", "ref", "speaker"],
                                       ["failed", "output", "ref", "speaker"]):
            if type(turn["ref"]) is not str or turn["ref"] not in refs:
                return ("tool_ref_unknown", path + ".ref")
            if type(turn["output"]) is not str:
                return ("tool_output_invalid", path + ".output")
            if "failed" in turn and type(turn["failed"]) is not bool:
                return ("tool_failed_invalid", path + ".failed")
        else:
            return ("turn_shape_invalid", path)
        prev_text = None
    return None


def target_ir(t):
    """The intermediate record of a target payload that passed schema_check."""
    refs = []
    messages = []
    for turn in t["turns"]:
        if "text" in turn:
            messages.append(("text", ROLE_OF[turn["speaker"]], turn["text"]))
        elif "invoke" in turn:
            inv = turn["invoke"]
            refs.append(inv["ref"])
            messages.append(("call", inv["fn"], tuple(sorted(inv["params"].items()))))
        else:
            failed = turn["failed"] if "failed" in turn else False
            messages.append(("result", refs.index(turn["ref"]), turn["output"], failed))
    settings = t["settings"] if "settings" in t else {}
    return {"system": t["preamble"] if "preamble" in t else "",
            "messages": tuple(messages),
            "tools": tuple(sorted(f["name"] for f in t["functions"])),
            "controls": tuple(sorted((SETTING[k], v) for k, v in settings.items()))}


def _item_diff(i, a, b):
    """Findings for one aligned source/target message pair that differ."""
    at = "messages[%d]" % i
    if a[0] != b[0]:
        return [("CL10", at, AVOIDABLE)]
    out = []
    if a[0] == "text":
        if a[1] != b[1]:
            out.append(("CL04", at + ".role", AVOIDABLE))
        if a[2] != b[2]:
            out.append(("CL05", at + ".text", AVOIDABLE))
    elif a[0] == "call":
        if a[1] != b[1]:
            out.append(("CL11", at + ".name", AVOIDABLE))
        if a[2] != b[2]:
            out.append(("CL12", at + ".args", AVOIDABLE))
    else:
        if a[1] != b[1]:
            out.append(("CL13", at + ".call", AVOIDABLE))
        if a[2] != b[2]:
            out.append(("CL14", at + ".content", AVOIDABLE))
        if a[3] and not b[3]:
            out.append(("CL15", at + ".is_error", AVOIDABLE))
        if b[3] and not a[3]:
            out.append(("CL16", at + ".is_error", AVOIDABLE))
    return out


def compare_messages(S, D, profile):
    """Message-sequence rules. S and D are tuples of IR messages."""
    if S == D:
        return []
    n, m = len(S), len(D)
    if n == m:
        if sorted(S) == sorted(D):
            return [("CL06", "messages", AVOIDABLE)]
        out = []
        for i in range(n):
            if S[i] != D[i]:
                out += _item_diff(i, S[i], D[i])
        return out
    if m == n - 1:
        for i in range(n - 1):
            a, b = S[i], S[i + 1]
            if a[0] != "text" or b[0] != "text" or D[i][0] != "text":
                continue
            if D[:i] != S[:i] or D[i + 1:] != S[i + 2:] or D[i][2] != a[2] + JOIN + b[2]:
                continue
            if a[1] == b[1] and D[i][1] == a[1]:
                status = FORCED if profile["alternating"] else AVOIDABLE
                return [("CL08", "messages[%d]" % i, status)]
            if a[1] != b[1] and D[i][1] in (a[1], b[1]):
                return [("CL09", "messages[%d]" % i, AVOIDABLE)]
        for i in range(n):
            if S[:i] + S[i + 1:] == D:
                return [("CL07", "messages[%d]" % i, AVOIDABLE)]
    return [("CL10", "messages", AVOIDABLE)]


def rules(src, dst, profile):
    """Compare two intermediate records. Returns sorted (rule, path, status)."""
    out = []
    S = src["messages"]
    D = dst["messages"]
    if src["system"] != dst["system"]:
        demoted = ("text", "user", src["system"])
        if src["system"] and not dst["system"] and D and D[0] == demoted:
            out.append(("CL03", "system", AVOIDABLE if profile["has_system"] else FORCED))
            D = D[1:]
        elif src["system"] and not dst["system"]:
            out.append(("CL01", "system", AVOIDABLE))
        else:
            out.append(("CL02", "system", AVOIDABLE))
    out += compare_messages(S, D, profile)
    for name in src["tools"]:
        if name not in dst["tools"]:
            out.append(("CL17", "tools." + name, AVOIDABLE))
    for name in dst["tools"]:
        if name not in src["tools"]:
            out.append(("CL18", "tools." + name, AVOIDABLE))
    sc = dict(src["controls"])
    dc = dict(dst["controls"])
    for name in CONTROLS:
        at = "controls." + name
        if name in sc and name not in dc:
            status = AVOIDABLE if name in profile["controls"] else FORCED
            out.append(("CL19", at, status))
        elif name in dc and name not in sc:
            out.append(("CL20", at, AVOIDABLE))
        elif name in sc and sc[name] != dc[name]:
            cap = profile["max_tokens_cap"]
            clamped = name == "max_tokens" and sc[name] > cap and dc[name] == cap
            out.append(("CL21", at, FORCED if clamped else AVOIDABLE))
    return tuple(sorted(out))


def encode_b(src, profile):
    """Dialect B's declared encoding of a source record under profile.

    The changes it makes are exactly the forced ones: system demotion when
    the target has no system field, same-role merge when it requires
    alternation, unsupported controls dropped, max_tokens clamped.
    """
    turns = []
    out = {}
    if src["system"]:
        if profile["has_system"]:
            out["preamble"] = src["system"]
        else:
            turns.append({"speaker": "human", "text": src["system"]})
    refs = []
    for item in src["messages"]:
        if item[0] == "text":
            sp = SPEAKER[item[1]]
            last = turns[-1] if turns else None
            if profile["alternating"] and last is not None and "text" in last \
                    and last["speaker"] == sp:
                last["text"] = last["text"] + JOIN + item[2]
            else:
                turns.append({"speaker": sp, "text": item[2]})
        elif item[0] == "call":
            ref = "call-%d" % len(refs)
            refs.append(ref)
            turns.append({"speaker": "model",
                          "invoke": {"ref": ref, "fn": item[1], "params": dict(item[2])}})
        else:
            turns.append({"speaker": "tool", "ref": refs[item[1]], "output": item[2],
                          "failed": item[3]})
    settings = {}
    for name, v in src["controls"]:
        if name not in profile["controls"]:
            continue
        if name == "max_tokens" and v > profile["max_tokens_cap"]:
            v = profile["max_tokens_cap"]
        settings[SETTING_OF[name]] = v
    out["turns"] = turns
    out["functions"] = [{"name": n} for n in src["tools"]]
    out["settings"] = settings
    return out


def describe(finding):
    rule, path, status = finding
    return "%s %s at %s (%s)" % (rule, RULES[rule], path, status)


def _config(detail):
    return {"status": CONFIG_ERROR, "detail": detail, "case_id": None, "baseline": None,
            "rule_arm": None}


def _run(snap):
    """Score the validated snapshot only."""
    err = schema_check(snap["target"], snap["profile"])
    findings = ()
    if err is None:
        findings = rules(snap["source"], target_ir(snap["target"]), snap["profile"])
    avoidable = tuple(f for f in findings if f[2] == AVOIDABLE)
    forced = tuple(f for f in findings if f[2] == FORCED)
    base = PASS if err is None else FAIL
    return {"status": OK, "detail": OK, "case_id": snap["case_id"],
            "baseline": {"verdict": base, "schema_error": err},
            "rule_arm": {"verdict": PASS if err is None and not avoidable else FAIL,
                         "findings": findings, "avoidable": len(avoidable),
                         "forced": len(forced)}}


def evaluate(case):
    """Score one translation case with both arms. Never raises."""
    try:
        snap = validate(case)
    except _Bad as exc:
        return _config(str(exc))
    except Exception:
        return _config("internal_error")
    try:
        return _run(snap)
    except Exception:
        return _config("internal_error")
