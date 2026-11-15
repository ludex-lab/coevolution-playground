"""Synthetic exposure DAG and attributed, HTML-checked paper sentences."""

from containment import ProvenanceDAG

PAPER_QUOTES = (
    "Meanwhile, an append-only provenance DAG records cross-agent data consumption horizontally.",
    "Upon an alert, Airlock traces forward on this DAG to isolate tainted executions and pending actions, and backward to narrow root causes.",
    "In HomeSvc, full quarantine halts each tainted assistant invocation as it starts while leaving automation running (Fig. 4).",
)


def synthetic_dag():
    """Bad version already consumed; independent automation has no data path.

    Planner delegates to reader and automation with narrowed permissions.
    Shared authority ancestry alone does not make automation a descendant of
    the bad artifact. Permissions are opaque synthetic effect-target tokens.
    """
    dag = ProvenanceDAG()
    dag.add_node("planner", permissions={"lamp:desk", "lamp:lobby"})
    dag.add_node("reader", permissions={"lamp:desk"})
    dag.add_node("next-turn", permissions={"lamp:desk"})
    dag.add_node("automation", permissions={"lamp:lobby"})
    dag.add_node("bad-v1", "artifact")
    dag.add_node("memo-v1", "artifact")
    dag.add_node("desk-command", "effect")
    dag.add_node("later-command", "effect")
    dag.add_node("lobby-command", "effect")
    edges = (
        ("delegate-reader", "planner", "reader", "authority"),
        ("delegate-auto", "planner", "automation", "authority"),
        ("produced", "planner", "bad-v1", "data"),
        ("already-read", "bad-v1", "reader", "data"),
        ("memory-write", "reader", "memo-v1", "data"),
        ("memory-read", "memo-v1", "next-turn", "data"),
        ("conversation", "reader", "next-turn", "session"),
        ("pending-desk", "reader", "desk-command", "data"),
        ("pending-later", "next-turn", "later-command", "data"),
        ("pending-lobby", "automation", "lobby-command", "data"),
    )
    for args in edges:
        dag.add_edge(*args)
    return dag


def demo():
    dag = synthetic_dag()
    print("frozen:", ", ".join(sorted(dag.quarantine("bad-v1"))))
    print("healthy simulated commit:", dag.actuate("lobby-command"))
    print("candidate roots:", ", ".join(sorted(dag.roots("later-command"))))


if __name__ == "__main__":
    demo()
