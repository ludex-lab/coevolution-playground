"""Independent reference for mb-conversation-loss-oracle (imports nothing).

A second, separately written code path for the toy static target check and
the preservation rules. It shares no function with the module and does not
validate the source or the profile: it is only called on cases the module
accepts. It reads the raw payloads directly: each message becomes a small
dict ({"k": kind, ...}) instead of a tuple, a reorder is found by counting
equal messages instead of sorting, and a merge or a drop is found by
building each candidate target sequence and comparing it whole.
"""

_SETTING_NAME = {"max_output": "max_tokens", "temperature_milli": "temperature_milli",
                 "reasoning_budget": "thinking_budget"}
_ORDER = ["max_tokens", "temperature_milli", "thinking_budget"]
_WHO = {"human": "user", "model": "assistant"}


def _src_messages(source):
    out = []
    seen = []
    for m in source["messages"]:
        if "content" in m:
            out.append({"k": "text", "who": m["role"], "body": m["content"]})
        elif "tool_call" in m:
            c = m["tool_call"]
            seen.append(c["id"])
            out.append({"k": "call", "fn": c["name"], "args": dict(c["args"])})
        else:
            r = m["result"]
            body = r if isinstance(r, str) else "\n".join(r)
            out.append({"k": "result", "link": seen.index(m["call_id"]), "body": body,
                        "err": m["is_error"]})
    return out


def _dst_messages(target):
    out = []
    seen = []
    for t in target["turns"]:
        if "text" in t:
            out.append({"k": "text", "who": _WHO[t["speaker"]], "body": t["text"]})
        elif "invoke" in t:
            seen.append(t["invoke"]["ref"])
            out.append({"k": "call", "fn": t["invoke"]["fn"], "args": dict(t["invoke"]["params"])})
        else:
            out.append({"k": "result", "link": seen.index(t["ref"]), "body": t["output"],
                        "err": t.get("failed", False)})
    return out


def _is_text(v):
    return isinstance(v, str) and not isinstance(v, bool)


def _is_count(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def reference_schema(target, profile):
    """True when the toy static target check accepts the payload."""
    if not isinstance(target, dict):
        return False
    if not set(target) <= {"preamble", "turns", "functions", "settings"}:
        return False
    if "turns" not in target or "functions" not in target:
        return False
    if "preamble" in target and (not profile["has_system"] or not _is_text(target["preamble"])
                                 or not target["preamble"]):
        return False
    if not isinstance(target["functions"], list):
        return False
    declared = []
    for f in target["functions"]:
        if not isinstance(f, dict) or list(f) != ["name"]:
            return False
        if not _is_text(f["name"]) or not f["name"].strip() or f["name"] in declared:
            return False
        declared.append(f["name"])
    settings = target.get("settings", {})
    if not isinstance(settings, dict):
        return False
    for k, v in settings.items():
        if k not in _SETTING_NAME or not _is_count(v):
            return False
        if _SETTING_NAME[k] not in profile["controls"]:
            return False
        if k == "max_output" and v > profile["max_tokens_cap"]:
            return False
    if not isinstance(target["turns"], list):
        return False
    refs = []
    last = ""
    for t in target["turns"]:
        if not isinstance(t, dict):
            return False
        shape = sorted(t)
        speaker = t.get("speaker")
        if shape == ["speaker", "text"] and speaker in ("human", "model"):
            if not _is_text(t["text"]):
                return False
            if profile["alternating"] and last == speaker:
                return False
            last = speaker
        elif shape == ["invoke", "speaker"] and speaker == "model":
            inv = t["invoke"]
            if not isinstance(inv, dict) or sorted(inv) != ["fn", "params", "ref"]:
                return False
            if not _is_text(inv["ref"]) or not inv["ref"].strip() or inv["ref"] in refs:
                return False
            if not _is_text(inv["fn"]) or inv["fn"] not in declared:
                return False
            if not isinstance(inv["params"], dict):
                return False
            if not all(_is_text(v) for v in inv["params"].values()):
                return False
            refs.append(inv["ref"])
            last = ""
        elif speaker == "tool" and shape in (["output", "ref", "speaker"],
                                             ["failed", "output", "ref", "speaker"]):
            if not _is_text(t["ref"]) or t["ref"] not in refs or not _is_text(t["output"]):
                return False
            if "failed" in t and not isinstance(t["failed"], bool):
                return False
            last = ""
        else:
            return False
    return True


_FIELD_RULES = {
    "text": (("who", "CL04", ".role"), ("body", "CL05", ".text")),
    "call": (("fn", "CL11", ".name"), ("args", "CL12", ".args")),
    "result": (("link", "CL13", ".call"), ("body", "CL14", ".content")),
}


def _messages(S, D, alternating):
    if S == D:
        return []
    if len(S) == len(D):
        if all(S.count(x) == D.count(x) for x in S):
            return [("CL06", "messages", "avoidable")]
        out = []
        for i in range(len(S)):
            a, b = S[i], D[i]
            if a == b:
                continue
            if a["k"] != b["k"]:
                out.append(("CL10", "messages[%d]" % i, "avoidable"))
                continue
            for field, rule, suffix in _FIELD_RULES[a["k"]]:
                if a[field] != b[field]:
                    out.append((rule, "messages[%d]%s" % (i, suffix), "avoidable"))
            if a["k"] == "result" and a["err"] != b["err"]:
                out.append(("CL15" if a["err"] else "CL16", "messages[%d].is_error" % i,
                            "avoidable"))
        return out
    if len(D) == len(S) - 1:
        for i in range(len(S) - 1):
            a, b = S[i], S[i + 1]
            if not (a["k"] == "text" and b["k"] == "text"):
                continue
            for who in (a["who"], b["who"]):
                joined = {"k": "text", "who": who, "body": a["body"] + "\n" + b["body"]}
                if S[:i] + [joined] + S[i + 2:] == D:
                    if a["who"] == b["who"]:
                        return [("CL08", "messages[%d]" % i,
                                 "forced" if alternating else "avoidable")]
                    return [("CL09", "messages[%d]" % i, "avoidable")]
        for i in range(len(S)):
            if S[:i] + S[i + 1:] == D:
                return [("CL07", "messages[%d]" % i, "avoidable")]
    return [("CL10", "messages", "avoidable")]


def reference(source, target, profile):
    """(schema_ok, sorted findings, rule-arm verdict) for one case."""
    if not reference_schema(target, profile):
        return (False, (), "FAIL")
    found = []
    S = _src_messages(source)
    D = _dst_messages(target)
    ss = source["system"]
    ds = target.get("preamble", "")
    if ss != ds:
        if ss != "" and ds == "":
            if D[:1] == [{"k": "text", "who": "user", "body": ss}]:
                found.append(("CL03", "system", "avoidable" if profile["has_system"] else "forced"))
                D = D[1:]
            else:
                found.append(("CL01", "system", "avoidable"))
        else:
            found.append(("CL02", "system", "avoidable"))
    found += _messages(S, D, profile["alternating"])
    src_tools = set(source["tools"])
    dst_tools = set(f["name"] for f in target["functions"])
    found += [("CL17", "tools." + n, "avoidable") for n in src_tools - dst_tools]
    found += [("CL18", "tools." + n, "avoidable") for n in dst_tools - src_tools]
    sc = source["controls"]
    dc = dict((_SETTING_NAME[k], v) for k, v in target.get("settings", {}).items())
    for name in _ORDER:
        where = "controls." + name
        if name in sc and name in dc:
            if sc[name] == dc[name]:
                continue
            cap = profile["max_tokens_cap"]
            ok = name == "max_tokens" and dc[name] == cap and sc[name] > cap
            found.append(("CL21", where, "forced" if ok else "avoidable"))
        elif name in sc:
            found.append(("CL19", where,
                          "avoidable" if name in profile["controls"] else "forced"))
        elif name in dc:
            found.append(("CL20", where, "avoidable"))
    found.sort()
    verdict = "FAIL" if [f for f in found if f[2] == "avoidable"] else "PASS"
    return (True, tuple(found), verdict)
