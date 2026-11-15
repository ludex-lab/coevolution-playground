"""SYNTHETIC role-contract table and scenarios; no real agent traces."""
from admission import AdmissionController, ContractTable, Message, RoleContract

# SYNTHETIC opaque speech-act tokens; not the paper's taxonomy.
TABLE = ContractTable((
    RoleContract("researcher", frozenset({"INFORM", "QUERY"})),
    RoleContract("coordinator", frozenset({"REQUEST", "QUERY", "INFORM"})),
    RoleContract("reviewer", frozenset({"CRITIQUE", "QUERY", "APPROVE"})),
))
RECHECK_WINDOW = 2  # SYNTHETIC integer ticks

IN_ROLE = Message("m-in-role", "researcher", ("INFORM", "QUERY"))
OUT_OF_ROLE = Message("m-out-of-role", "researcher", ("INFORM", "APPROVE"))
UNKNOWN_ROLE = Message("m-unknown", "executor", ("INFORM",))
REVISED_IN_ROLE = Message("m-out-of-role", "researcher", ("INFORM",), revision=1)
DRIFT = Message("m-drift", "reviewer", ("CRITIQUE", "REQUEST"))
REVISED_STILL_OUT = Message("m-drift", "reviewer", ("REQUEST",), revision=1)
SLOW = Message("m-slow", "coordinator", ("REQUEST", "CRITIQUE"))
REVISED_SLOW = Message("m-slow", "coordinator", ("REQUEST",), revision=1)
SILENT = Message("m-silent", "coordinator", ("APPROVE",))
REVISED_SILENT = Message("m-silent", "coordinator", ("INFORM",), revision=1)


def controller():
    return AdmissionController(TABLE, RECHECK_WINDOW)


def run_demo():
    gate = controller()
    lines = []

    def show(label, decision):
        lines.append("SYNTHETIC %s: %s %s rev=%d reason=%s out_of_role=%s" % (
            label, decision.message_id, decision.verdict.value, decision.revision,
            decision.reason, ",".join(decision.out_of_role) or "-"))

    show("in-role", gate.propose(IN_ROLE, 0))
    show("out-of-role", gate.propose(OUT_OF_ROLE, 0))
    show("unknown-role", gate.propose(UNKNOWN_ROLE, 0))
    gate.revise(REVISED_IN_ROLE)
    lines.append("SYNTHETIC revision recorded, before re-check: m-out-of-role "
                 + gate.status("m-out-of-role", 1).value)
    show("successful re-check", gate.recheck("m-out-of-role", 1))
    show("drift", gate.propose(DRIFT, 0))
    gate.revise(REVISED_STILL_OUT)
    show("failed re-check", gate.recheck("m-drift", 1))
    show("slow", gate.propose(SLOW, 0))
    gate.revise(REVISED_SLOW)
    show("re-check after window", gate.recheck("m-slow", 3))
    show("silent", gate.propose(SILENT, 0))
    gate.revise(REVISED_SILENT)
    for decision in gate.expire(3):
        show("missing re-check expired", decision)
    lines.append("SYNTHETIC shared context: " + ", ".join(
        "%s@rev%d" % pair for pair in gate.context.ids()))
    lines.append("REJECTED and HELD are never admission; only ADMITTED enters shared context.")
    return gate, tuple(lines)


def main():
    _, lines = run_demo()
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
