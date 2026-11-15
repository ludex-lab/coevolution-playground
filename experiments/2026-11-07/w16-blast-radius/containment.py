"""Clean-room synchronous full-quarantine sketch; all actuations are simulated.

This is conservative reachability, not timestamp-aware distributed enforcement.
The provenance graph is immutable except for append operations. Runtime state
(taint, quarantine and simulated commits) is separate from historical records.
"""

from dataclasses import dataclass
from types import MappingProxyType


class AppendOnlyError(ValueError):
    """A historical node or edge cannot be removed or rewritten."""


class BlockedAction(RuntimeError):
    """The simulated commit gate denied an action."""


@dataclass(frozen=True)
class Node:
    name: str
    kind: str
    permissions: frozenset


@dataclass(frozen=True)
class Edge:
    producer: str
    consumer: str
    kind: str


class ProvenanceDAG:
    """Single-threaded, in-memory DAG with monotone quarantine and no release API.

    Data/session edges describe already-recorded exposure. Authority edges
    describe parent-to-child delegation with subset checks. For this sketch,
    forward reach includes all edge kinds conservatively; no causal time model
    or semantic influence inference is claimed.
    """

    def __init__(self):
        self._nodes = {}
        self._edges = {}
        self._out = {}
        self._in = {}
        self._origins = set()
        self._tainted = set()
        self._held = set()
        self._committed = set()

    @property
    def nodes(self):
        return MappingProxyType(self._nodes)

    @property
    def edges(self):
        return MappingProxyType(self._edges)

    @property
    def tainted(self):
        return frozenset(self._tainted)

    @property
    def frozen(self):
        return frozenset(self._held)

    @property
    def committed(self):
        return frozenset(self._committed)

    def add_node(self, name, kind="task", permissions=()):
        if not isinstance(name, str) or not name:
            raise ValueError("node name must be a nonempty string")
        if name in self._nodes:
            raise AppendOnlyError("append-only: node already exists")
        if kind not in {"task", "artifact", "effect"}:
            raise ValueError("unknown node kind")
        node = Node(name, kind, frozenset(permissions))
        self._nodes[name] = node
        self._out[name] = set()
        self._in[name] = set()
        return node

    def _walk(self, start, adjacency):
        if start not in self._nodes:
            raise KeyError(start)
        seen, todo = set(), [start]
        while todo:
            current = todo.pop()
            if current not in seen:
                seen.add(current)
                todo.extend(adjacency[current] - seen)
        return seen

    def descendants(self, start):
        """Forward reach, including the supplied vertex."""
        return frozenset(self._walk(start, self._out))

    def roots(self, symptom):
        """Candidate ancestors, including symptom; not a causal diagnosis/ranking.

        Interior ancestors may be faulty too, so returning only zero-in-degree
        vertices would incorrectly discard possible causes.
        """
        return frozenset(self._walk(symptom, self._in))

    def add_edge(self, edge_id, producer, consumer, kind="data"):
        if edge_id in self._edges:
            raise AppendOnlyError("append-only: edge ID already exists; no rewrite")
        if not isinstance(edge_id, str) or not edge_id:
            raise ValueError("edge ID must be a nonempty string")
        if producer not in self._nodes or consumer not in self._nodes:
            raise KeyError("both endpoints must already exist")
        if kind not in {"data", "session", "authority"}:
            raise ValueError("unknown edge kind")
        if producer in self.descendants(consumer):
            raise ValueError("edge would create a cycle")
        if kind == "authority":
            parent, child = self._nodes[producer], self._nodes[consumer]
            if parent.kind != "task" or child.kind != "task":
                raise ValueError("authority endpoints must be tasks")
            if not child.permissions <= parent.permissions:
                raise ValueError("child permissions must be a subset of parent")
            if any(e.kind == "authority" and e.consumer == consumer
                   for e in self._edges.values()):
                raise ValueError("child already has an authority parent")
        edge = Edge(producer, consumer, kind)
        self._edges[edge_id] = edge
        self._out[producer].add(consumer)
        self._in[consumer].add(producer)
        # Late-recorded consumption and newly exposed descendants cannot bypass
        # an earlier alert. Append and refresh finish before any simulated commit.
        if self._origins:
            self.quarantine()
        return edge

    def delete_edge(self, edge_id):
        raise AppendOnlyError("append-only: edge deletion forbidden")

    def rewrite_edge(self, edge_id, *args, **kwargs):
        raise AppendOnlyError("append-only: edge rewrite forbidden")

    def delete_node(self, name):
        raise AppendOnlyError("append-only: node deletion forbidden")

    def taint(self, alert=None):
        """Record a source and close forward; None means silence, never clearance."""
        if alert is not None:
            if alert not in self._nodes:
                raise KeyError(alert)
            self._origins.add(alert)
        for origin in self._origins:
            self._tainted.update(self.descendants(origin))
        return self.tainted

    def quarantine(self, alert=None):
        """Freeze every tainted record and deny its future simulated egress.

        Historical committed effects remain committed: this never undoes harm.
        New artifact versions are new nodes, not repairs of recorded history.
        No unfreeze, endorsement or approval operation is modeled.
        """
        self.taint(alert)
        self._held.update(self._tainted)
        return self.frozen

    def actuate(self, effect):
        """Record a simulated actuation only; never call an external device/tool."""
        node = self._nodes[effect]
        if node.kind != "effect":
            raise ValueError("actuation requires an effect node")
        if effect in self._tainted or effect in self._held:
            raise BlockedAction("tainted/quarantined pending action blocked: " + effect)
        if effect in self._committed:
            raise BlockedAction("effect already committed: " + effect)
        self._committed.add(effect)
        return effect
