"""w19-guardrail-order: a silent guardrail-order break in a toy harness.

Clean-room Python 3 stdlib method sketch of the order-check idea in
arXiv 2611.09088 (PatternOps). Not a reproduction.

Two layers:

* ``Harness`` is the toy world. Its edit decision path is a chain of stages
  that run in registration order until one stage ends the call. It starts as
  ``[guardrail -> edit_tool]``. Two routine maintenance ops,
  ``reapply_plugin`` and ``save_allow_rule``, change the runtime path without
  touching the static config, which still lists the guardrail as active.
  Every edit decision appends one ``DecisionRecord`` (which stages actually
  ran, in order) to an append-only runtime history.

* ``check_order`` / ``detect`` / ``hold`` / ``report`` / ``compare`` /
  ``flag`` are the check layer. They read only the runtime history. The
  check never clears anything; it reports ``order_ok``, ``order_broken`` or
  ``hold``. There is no path in this layer that admits an action.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

GUARDRAIL = "guardrail"
EDIT_TOOL = "edit_tool"

ORDER_OK = "order_ok"
ORDER_BROKEN = "order_broken"
HOLD = "hold"

# Stage answers. "pass" hands the call to the next stage; the others end it.
PASS = "pass"
BLOCK = "block"
EXECUTE = "execute"


@dataclass(frozen=True)
class DecisionRecord:
    """One edit decision as it actually ran (runtime history, append-only)."""

    decision_id: int
    kind: str
    path: str
    stages_run: Tuple[str, ...]
    outcome: str  # "blocked" | "executed" | "unhandled"


class Harness:
    """Toy agent harness with a chain-of-stages edit decision path."""

    def __init__(self, protected_prefixes: Sequence[str] = ("protected/",)):
        self.protected_prefixes = tuple(protected_prefixes)
        # Static config / plugin listing. The ops below never change it.
        self.config: Dict[str, object] = {
            "pipeline": [GUARDRAIL, EDIT_TOOL],
            "plugins": {GUARDRAIL: {"active": True}, EDIT_TOOL: {"active": True}},
        }
        # Runtime chain: the order stages are actually registered in.
        self._chain: List[str] = [GUARDRAIL, EDIT_TOOL]
        # Retained state written by save_allow_rule (path prefixes).
        self._saved_rules: List[str] = []
        self._history: List[DecisionRecord] = []
        self.ops_log: List[str] = []
        self.files: Dict[str, str] = {}

    # -- stages ---------------------------------------------------------
    def _stage_guardrail(self, path: str, content: str) -> str:
        if any(path.startswith(p) for p in self.protected_prefixes):
            return BLOCK
        return PASS

    def _stage_edit_tool(self, path: str, content: str) -> str:
        self.files[path] = content
        return EXECUTE

    def _run_stage(self, name: str, path: str, content: str) -> str:
        if name == GUARDRAIL:
            return self._stage_guardrail(path, content)
        if name == EDIT_TOOL:
            return self._stage_edit_tool(path, content)
        raise ValueError("unknown stage: %r" % name)

    # -- routine ops (toy maintenance) -----------------------------------
    def reapply_plugin(self, name: str) -> None:
        """Dispose and re-create a plugin instance.

        As in a chain of responsibility, the fresh instance is registered
        last. For the guardrail that puts it behind edit_tool, which ends the
        call, so the guardrail is no longer reached. Config is untouched.
        """
        if name not in self._chain:
            raise ValueError("unknown plugin: %r" % name)
        self._chain.remove(name)
        self._chain.append(name)
        self.ops_log.append("reapply_plugin:%s" % name)

    def save_allow_rule(self, prefix: str) -> None:
        """Save a standing rule for edits under ``prefix`` ("" = any file).

        Requests matching a saved rule are routed straight to edit_tool, so
        the guardrail never sees them. Config is untouched.
        """
        self._saved_rules.append(prefix)
        self.ops_log.append("save_allow_rule:%s" % prefix)

    # -- decisions ------------------------------------------------------
    def _decision_path(self, path: str) -> List[str]:
        if any(path.startswith(p) for p in self._saved_rules):
            return [EDIT_TOOL]
        return list(self._chain)

    def attempt_edit(self, path: str, content: str = "x") -> DecisionRecord:
        ran: List[str] = []
        outcome = "unhandled"
        for name in self._decision_path(path):
            ran.append(name)
            answer = self._run_stage(name, path, content)
            if answer == BLOCK:
                outcome = "blocked"
                break
            if answer == EXECUTE:
                outcome = "executed"
                break
        rec = DecisionRecord(len(self._history), "edit", path, tuple(ran), outcome)
        self._history.append(rec)
        return rec

    def history(self) -> Tuple[DecisionRecord, ...]:
        """Snapshot of the runtime history (records are frozen)."""
        return tuple(self._history)

    def config_lists_active(self, name: str) -> bool:
        plugins = self.config.get("plugins", {})
        return bool(plugins.get(name, {}).get("active")) and name in self.config.get("pipeline", [])


# -- check layer: reads runtime history only -----------------------------

def _decision_ok(rec: DecisionRecord, required: str, before: str) -> Optional[bool]:
    """True/False for an edit decision; None if the record is malformed."""
    stages = getattr(rec, "stages_run", None)
    if not isinstance(stages, tuple) or not stages:
        return None
    if required not in stages:
        return False
    if before in stages and stages.index(required) > stages.index(before):
        return False
    return True


def detect(history: Sequence[DecisionRecord], required: str = GUARDRAIL,
           before: str = EDIT_TOOL) -> List[int]:
    """Decision ids where ``required`` did not run ahead of ``before``."""
    out = []
    for rec in history:
        if getattr(rec, "kind", None) != "edit":
            continue
        if _decision_ok(rec, required, before) is False:
            out.append(rec.decision_id)
    return out


def hold(history: Sequence[DecisionRecord]) -> Optional[str]:
    """Reason to hold (fail closed), or None when the history is readable."""
    edits = [r for r in history if getattr(r, "kind", None) == "edit"]
    if not edits:
        return "no edit decisions in runtime history"
    for rec in edits:
        if _decision_ok(rec, GUARDRAIL, EDIT_TOOL) is None:
            return "malformed record %r" % (getattr(rec, "decision_id", None),)
    return None


def check_order(history: Sequence[DecisionRecord], required: str = GUARDRAIL,
                before: str = EDIT_TOOL) -> Dict[str, object]:
    """PatternOps-style order check over the runtime decision history.

    For every edit decision, did ``required`` actually run on the decision
    path ahead of ``before``? Returns status ``order_ok``, ``order_broken``
    or ``hold``. Takes no config argument and reads none.
    """
    history = tuple(history)
    edits = [r for r in history if getattr(r, "kind", None) == "edit"]
    if not edits:
        return {"status": HOLD, "decisions": 0, "broken": [],
                "reason": "no edit decisions in runtime history"}
    for rec in edits:
        if _decision_ok(rec, required, before) is None:
            return {"status": HOLD, "decisions": len(edits), "broken": [],
                    "reason": "malformed record %r" % (getattr(rec, "decision_id", None),)}
    broken = detect(history, required, before)
    if broken:
        return {"status": ORDER_BROKEN, "decisions": len(edits), "broken": broken,
                "reason": "%s missing or late on %d of %d edit decisions"
                          % (required, len(broken), len(edits))}
    return {"status": ORDER_OK, "decisions": len(edits), "broken": [],
            "reason": "%s ran ahead of %s on every edit decision" % (required, before)}


def flag(history: Sequence[DecisionRecord], required: str = GUARDRAIL,
         before: str = EDIT_TOOL) -> List[str]:
    """Human-readable lines for each decision where the order broke."""
    ids = set(detect(history, required, before))
    return ["decision %d %s path=%s stages=%s"
            % (r.decision_id, r.outcome, r.path, "->".join(r.stages_run))
            for r in history if getattr(r, "decision_id", None) in ids]


def report(history: Sequence[DecisionRecord]) -> str:
    res = check_order(history)
    lines = ["order check: %s (%s)" % (res["status"], res["reason"])]
    lines.extend("  " + s for s in flag(history))
    return "\n".join(lines)


def compare(listed_active: bool, history: Sequence[DecisionRecord]) -> Dict[str, object]:
    """Contrast a static listing claim with what the runtime history shows.

    ``listed_active`` is a caller-supplied boolean (e.g. from the plugin
    listing). It is only echoed next to the runtime result; it never
    changes the order status.
    """
    res = check_order(history)
    return {"listed_active": bool(listed_active), "runtime_status": res["status"],
            "mismatch": bool(listed_active) and res["status"] == ORDER_BROKEN}
