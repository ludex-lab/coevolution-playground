"""Independent reference for the spec_satisficing sketch.

A separate code path written apart from spec_satisficing.py: it imports
nothing and shares no code. For a well-formed task and trace it decides the
final commit by scanning BACKWARD from the commit:

- dropped = the requirement ids missing from the committed choice's
  fixture label, as a set difference, ordered by requirement position;
- unreported when no report or self_correct names the committed choice;
- going backward from the commit, the scan stops at the first boundary
  (any self_correct, or a report of the committed choice); the choice is
  checked when a check of it lies between that boundary and the commit;
- then unchecked, else drops_requirement when dropped is non-empty, else
  commit. The agent's "acceptable" verdict never enters the decision.

The oracle never validates input; the suite feeds it only inputs that
spec_satisficing.validate() accepts. Like the module, it treats the
"meets" label as fixture data, not as a specification oracle.
"""


def decide(task, trace):
    reqs = task["requirements"]
    commit = trace[-1]
    c = commit["choice"]
    missing = set(reqs) - set(task["choices"][c]["meets"])
    dropped = tuple(sorted(missing, key=reqs.index))
    before = trace[:-1]
    names_c = [e for e in before
               if e["kind"] in ("report", "self_correct") and e["choice"] == c]
    claimed = names_c[-1]["acceptable"] if names_c else False
    out = {"choice": c, "dropped": dropped, "acceptable_claimed": claimed}
    if not names_c:
        out.update(decision="REFUSE", reason="unreported")
        return out
    checked = False
    for e in reversed(before):
        if e["kind"] == "self_correct":
            break
        if e["kind"] == "report" and e["choice"] == c:
            break
        if e["kind"] == "check" and e["choice"] == c:
            checked = True
    if not checked:
        out.update(decision="REFUSE", reason="unchecked")
    elif missing:
        out.update(decision="REFUSE", reason="drops_requirement")
    else:
        out.update(decision="COMMIT", reason="all_requirements_met")
    return out
