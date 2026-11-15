"""Exploit executor: the independent ground truth for the gate.

It interprets one toy program concretely, with the source returning the
exploit input, and reports whether the exploit text reaches a sink. It is a
pure Python model of the sink: a sink receives a string, and the exploit
reaches it when the exploit text occurs verbatim in a received string.
Nothing runs outside this interpreter: no process, no network, no file, no
evaluation of program text. It imports neither the analyzer module nor the
oracle and shares no function name with them.

Concrete semantics (declared):
- source returns the exploit; const returns its value;
- concat joins its arguments; sanitize replaces every "'" with "&#39;";
- parse_url splits at the first "?": path before it, query after it (no "?":
  the whole string is the path and the query is "");
- field reads path or query; pack builds a list; index reads one element;
- call runs a helper with its own variables and returns its ret variable;
- sink receives its argument.

The result record is {ran_on, exploit, reached}; ran_on is the sha256 of the
program's canonical JSON (sorted keys, no spaces), so a result names the
exact program it ran on.
"""

import hashlib
import json

QUOTE = "'"
QUOTE_ESCAPED = "&#39;"
MAX_DEPTH = 16


class ExecError(Exception):
    """The program cannot be interpreted."""


def fingerprint(program):
    blob = json.dumps(program, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("ascii")).hexdigest()


def received(program, exploit):
    """Every string the sinks received, in execution order."""
    got = []
    _interp(program["body"], program["helpers"], {}, exploit, got, 0)
    return got


def execute(program, exploit):
    got = received(program, exploit)
    return {"ran_on": fingerprint(program), "exploit": exploit,
            "reached": any(exploit in s for s in got)}


def _interp(steps, helpers, mem, exploit, got, depth):
    if depth > MAX_DEPTH:
        raise ExecError("too deep")
    for st in steps:
        kind = st["op"]
        if kind == "sink":
            val = mem[st["src"]]
            if not isinstance(val, str):
                raise ExecError("sink needs a string")
            got.append(val)
            continue
        if kind == "source":
            val = exploit
        elif kind == "const":
            val = st["value"]
        elif kind == "assign":
            val = mem[st["src"]]
        elif kind == "concat":
            val = "".join(mem[a] for a in st["args"])
        elif kind == "sanitize":
            val = mem[st["src"]].replace(QUOTE, QUOTE_ESCAPED)
        elif kind == "parse_url":
            text = mem[st["src"]]
            cut = text.find("?")
            val = {"path": text, "query": ""} if cut < 0 else \
                {"path": text[:cut], "query": text[cut + 1:]}
        elif kind == "field":
            val = mem[st["src"]][st["name"]]
        elif kind == "pack":
            val = [mem[a] for a in st["args"]]
        elif kind == "index":
            val = mem[st["src"]][st["at"]]
        elif kind == "call":
            h = helpers[st["fn"]]
            local = {h["param"]: mem[st["arg"]]}
            _interp(h["body"], helpers, local, exploit, got, depth + 1)
            val = local[h["ret"]]
        else:
            raise ExecError("unknown op")
        mem[st["dst"]] = val
