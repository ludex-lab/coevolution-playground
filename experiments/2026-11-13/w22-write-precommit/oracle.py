"""Independent reference for the w22-write-precommit sketch.

Written separately: it does not import write_precommit and shares no code
with it. It reads the schema directly and works by index arithmetic over
the event list instead of a running state machine:

- cut = index of the first tool_result (len(events) when there is none);
- the precommit table is the commit events strictly before cut;
- a write at index i is admitted iff
    its call_id is in the precommit table at an index below i, and
    its tool equals the committed tool, and
    for every targeting arg t of that tool (from the schema):
        t is in both arg maps, the two values are equal, the value has a
        non-space character, and the value occurs in the request, and
    no earlier write at index < i with the same call_id was admitted.

Tool-result text is never consulted. The oracle never validates input;
the suite feeds it only episodes that write_precommit accepts.
"""


def decide(episode):
    """Return [(call_id, admitted_bool), ...] in write-event order."""
    request = episode["request"]
    schema = episode["schema"]
    events = episode["events"]
    kinds = [e["type"] for e in events]
    cut = kinds.index("tool_result") if "tool_result" in kinds else len(events)
    table = {}
    for j in range(cut):
        if events[j]["type"] == "commit":
            table[events[j]["call_id"]] = (j, events[j])
    out = []
    spent = []
    for i, e in enumerate(events):
        if e["type"] != "write":
            continue
        j, c = table.get(e["call_id"], (len(events), None))
        ok = j < i and c["tool"] == e["tool"]
        if ok:
            for t in schema[e["tool"]]["targeting"]:
                w = e["args"].get(t)
                if w is None or c["args"].get(t) != w:
                    ok = False
                elif w.strip() == "" or request.find(w) < 0:
                    ok = False
        if ok and e["call_id"] in spent:
            ok = False
        if ok:
            spent.append(e["call_id"])
        out.append((e["call_id"], ok))
    return out
