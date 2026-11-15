"""Call-level revision contract: clean-room, stdlib-only method sketch.

Method sketch of arXiv 2611.06967 (method-cite only). Synthetic toy
workflows only. Not Team OS law, not village law.

Vocabulary: accept / reject / hold for the static gate; replay / dispatch /
diverge / orphan / stop for the runtime. There is no permissive verdict.

A call identity is the triple (callsite path, fanout index, occurrence count):
  * callsite path  -- enclosing function + block path + ordinal of the
                      ``ctx.run`` call inside the innermost block (static);
  * fanout index   -- tuple of branch indices pushed by ``ctx.fanout`` (runtime);
  * occurrence     -- zero-based counter per (callsite path, fanout index).

The static gate freezes the *call expression* at every committed callsite. It
does not freeze upstream data dependencies, so a changed variable feeding an
unchanged call expression passes the gate and must be stopped by the runtime
payload digest. Gate acceptance does not mean every committed identity is
replayed: identities the candidate never invokes are reported as orphans.
"""

import ast
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = [
    "GateDecision", "RunOutcome", "OrphanPolicy", "RepeatPolicy",
    "Record", "Ledger", "LedgerUnavailable", "GateFinding", "GateResult",
    "RunReport", "RevisionReport", "assign_sites", "call_fingerprint",
    "payload_digest", "canonical_payload", "load_ledger_text", "gate",
    "run_workflow", "build_ledger", "revise", "naive_rerun_dispatches",
    "identity_key",
]


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

class GateDecision(Enum):
    ACCEPT = "accept"      # structural premise holds for every frozen site
    REJECT = "reject"      # a committed call expression changed, moved, or vanished
    HOLD = "hold"          # ledger unavailable or inconsistent: fail closed


class RunOutcome(Enum):
    COMPLETED = "completed"
    COMPLETED_WITH_ORPHANS = "completed_with_orphans"   # orphan policy = warn
    STOPPED_DIVERGENCE = "stopped_divergence"           # digest mismatch at committed identity
    STOPPED_ORPHAN = "stopped_orphan"                   # orphan policy = stop
    STOPPED_REPEAT = "stopped_repeat"                   # semantic repeat under stop policy
    HELD_LEDGER_UNAVAILABLE = "held_ledger_unavailable"
    NOT_RUN_GATE_REJECTED = "not_run_gate_rejected"
    FAILED_PROVIDER = "failed_provider"                 # simulated provider failure


class OrphanPolicy(Enum):
    WARN = "warn"   # default: report orphans, run still completes
    STOP = "stop"   # report orphans and fail the run


class RepeatPolicy(Enum):
    WARN = "warn"
    STOP = "stop"
    AUTO = "auto"   # stop for side-effecting capabilities, warn otherwise


class LedgerUnavailable(Exception):
    """The committed ledger could not be read or is inconsistent."""


class Divergence(Exception):
    def __init__(self, key: str, reason: str):
        super().__init__(f"divergence at {key}: {reason}")
        self.key = key
        self.reason = reason


class RepeatStop(Exception):
    def __init__(self, key: str):
        super().__init__(f"semantic repeat stopped at {key}")
        self.key = key


class ProviderFailure(Exception):
    pass


class ContractError(Exception):
    """Source violates the toy script subset."""


# --------------------------------------------------------------------------
# Payload digest
# --------------------------------------------------------------------------

def canonical_payload(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_digest(payload: Any) -> str:
    return hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()


def identity_key(site: str, path: Tuple[int, ...], occurrence: int) -> str:
    return f"{site}|{','.join(str(i) for i in path)}|{occurrence}"


# --------------------------------------------------------------------------
# Static side: callsites and call-expression fingerprints
# --------------------------------------------------------------------------

_BLOCK_KINDS = {ast.For: "for", ast.While: "while", ast.If: "if", ast.With: "with"}


def _is_run_call(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "ctx")


def _strip_site(call: ast.Call) -> ast.Call:
    clone = ast.Call(func=call.func, args=call.args,
                     keywords=[k for k in call.keywords if k.arg != "_site"])
    return clone


def call_fingerprint(call: ast.Call) -> str:
    """sha256 over the normalized AST dump of one ctx.run(...) expression."""
    dump = ast.dump(_strip_site(call), annotate_fields=True, include_attributes=False)
    return hashlib.sha256(dump.encode("utf-8")).hexdigest()


def _capability_of(call: ast.Call) -> Optional[str]:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None


def _contains_run(node: ast.AST) -> bool:
    return any(_is_run_call(n) for n in ast.walk(node))


def _runs_in_order(node: ast.AST) -> List[ast.Call]:
    calls = [n for n in ast.walk(node) if _is_run_call(n)]
    return sorted(calls, key=lambda c: (c.lineno, c.col_offset))


def _check_subset(tree: ast.Module) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ContractError("imports are outside the toy script subset")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ContractError("dunder names are outside the toy script subset")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ContractError("dunder attributes are outside the toy script subset")
        if isinstance(node, ast.keyword) and node.arg == "_site":
            raise ContractError("_site is reserved for the host annotator")
        if _is_run_call(node) and _capability_of(node) is None:
            raise ContractError("capability name must be a string literal")
    for top in tree.body:
        if not isinstance(top, ast.FunctionDef):
            if _contains_run(top):
                raise ContractError("capability calls must live inside a top-level def")
            continue
        for inner in ast.walk(top):
            if inner is not top and isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                if _contains_run(inner):
                    raise ContractError("capability calls inside nested functions are unsupported")


def _walk_block(stmts: List[ast.stmt], func: str, prefix: Tuple[str, ...],
                out: Dict[str, ast.Call]) -> None:
    ordinal = 0
    block_counts: Dict[str, int] = {}

    def site_for(j: int) -> str:
        return "/".join((func,) + prefix + (f"run#{j}",))

    for st in stmts:
        kind = None
        for cls, name in _BLOCK_KINDS.items():
            if isinstance(st, cls):
                kind = name
        if kind is not None and _contains_run(st):
            # header expressions belong to the current block
            headers: List[ast.AST] = []
            if isinstance(st, ast.For):
                headers = [st.iter]
            elif isinstance(st, (ast.While, ast.If)):
                headers = [st.test]
            elif isinstance(st, ast.With):
                headers = [it.context_expr for it in st.items]
            for h in headers:
                for call in _runs_in_order(h):
                    out[site_for(ordinal)] = call
                    ordinal += 1
            k = block_counts.get(kind, 0)
            block_counts[kind] = k + 1
            _walk_block(st.body, func, prefix + (f"{kind}#{k}",), out)
            orelse = getattr(st, "orelse", [])
            if orelse:
                _walk_block(orelse, func, prefix + (f"{kind}#{k}.else",), out)
        elif _contains_run(st):
            if isinstance(st, (ast.Try, ast.AsyncFor, ast.AsyncWith)):
                raise ContractError(f"{type(st).__name__} around a capability call is unsupported")
            for call in _runs_in_order(st):
                out[site_for(ordinal)] = call
                ordinal += 1


def _sites_from_tree(tree: ast.Module) -> Dict[str, ast.Call]:
    _check_subset(tree)
    out: Dict[str, ast.Call] = {}
    for top in tree.body:
        if isinstance(top, ast.FunctionDef):
            _walk_block(top.body, top.name, (), out)
    return out


def assign_sites(src: str) -> Dict[str, Dict[str, str]]:
    """Map callsite path -> {capability, fingerprint}. Independent of line numbers."""
    tree = ast.parse(src)
    return {site: {"capability": _capability_of(call), "fingerprint": call_fingerprint(call)}
            for site, call in _sites_from_tree(tree).items()}


# --------------------------------------------------------------------------
# Ledger (JSON, not a database)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Record:
    site: str
    path: Tuple[int, ...]
    occurrence: int
    capability: str
    payload_sha256: str
    result: str

    @property
    def key(self) -> str:
        return identity_key(self.site, self.path, self.occurrence)


@dataclass
class Ledger:
    frozen_sites: Dict[str, Dict[str, str]] = field(default_factory=dict)
    records: Dict[str, Record] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "version": 1,
            "frozen_sites": {k: self.frozen_sites[k] for k in sorted(self.frozen_sites)},
            "records": [
                {"site": r.site, "path": list(r.path), "occurrence": r.occurrence,
                 "capability": r.capability, "payload_sha256": r.payload_sha256,
                 "result": r.result}
                for _, r in sorted(self.records.items())
            ],
        }, indent=2, sort_keys=True)


def load_ledger_text(text: Optional[str]) -> Ledger:
    """Strict loader: anything unreadable or inconsistent raises LedgerUnavailable."""
    if text is None:
        raise LedgerUnavailable("ledger missing")
    try:
        raw = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise LedgerUnavailable(f"ledger unreadable: {exc}") from None
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise LedgerUnavailable("ledger version unsupported")
    try:
        frozen = {str(k): {"capability": str(v["capability"]), "fingerprint": str(v["fingerprint"])}
                  for k, v in raw["frozen_sites"].items()}
        records: Dict[str, Record] = {}
        for item in raw["records"]:
            rec = Record(site=str(item["site"]), path=tuple(int(i) for i in item["path"]),
                         occurrence=int(item["occurrence"]), capability=str(item["capability"]),
                         payload_sha256=str(item["payload_sha256"]), result=str(item["result"]))
            prior = records.get(rec.key)
            if prior is not None and prior != rec:
                raise LedgerUnavailable(f"conflicting duplicate record at {rec.key}")
            records[rec.key] = rec
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise LedgerUnavailable(f"ledger malformed: {exc!r}") from None
    for rec in records.values():
        fs = frozen.get(rec.site)
        if fs is None or fs["capability"] != rec.capability:
            raise LedgerUnavailable(f"record {rec.key} has no matching frozen site")
    return Ledger(frozen_sites=frozen, records=records)


def _coerce_ledger(committed: Any) -> Ledger:
    if isinstance(committed, Ledger):
        return committed
    if committed is None or isinstance(committed, str):
        return load_ledger_text(committed)
    raise LedgerUnavailable(f"unsupported ledger object {type(committed).__name__}")


# --------------------------------------------------------------------------
# Static gate
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class GateFinding:
    kind: str      # removed | capability_changed | call_changed | relocated_not_reused |
                   # ledger_unavailable | ledger_mismatch | parse_error | subset_violation
    site: str
    detail: str = ""


@dataclass
class GateResult:
    decision: GateDecision
    findings: List[GateFinding] = field(default_factory=list)

    @property
    def kinds(self) -> List[str]:
        return [f.kind for f in self.findings]


def gate(old_src: str, new_src: str, committed: Any) -> GateResult:
    """Static pre-spend gate over committed callsites.

    Rejects a candidate that removes, changes, or moves a committed call
    expression. Holds (fails closed) when the ledger is unavailable or does not
    match the old source. Acceptance says nothing about reachability or about
    run-time payload values.
    """
    try:
        ledger = _coerce_ledger(committed)
    except LedgerUnavailable as exc:
        return GateResult(GateDecision.HOLD, [GateFinding("ledger_unavailable", "*", str(exc))])

    try:
        old_sites = assign_sites(old_src)
    except (SyntaxError, ContractError) as exc:
        return GateResult(GateDecision.HOLD, [GateFinding("ledger_mismatch", "*", f"old source: {exc}")])
    for site, frozen in ledger.frozen_sites.items():
        if old_sites.get(site) != frozen:
            return GateResult(GateDecision.HOLD, [GateFinding(
                "ledger_mismatch", site, "ledger fingerprint does not match the old source")])

    try:
        new_sites = assign_sites(new_src)
    except SyntaxError as exc:
        return GateResult(GateDecision.REJECT, [GateFinding("parse_error", "*", str(exc))])
    except ContractError as exc:
        return GateResult(GateDecision.REJECT, [GateFinding("subset_violation", "*", str(exc))])

    findings: List[GateFinding] = []
    new_by_fp: Dict[str, List[str]] = {}
    for s, info in new_sites.items():
        new_by_fp.setdefault(info["fingerprint"], []).append(s)

    for site in sorted(ledger.frozen_sites):
        frozen = ledger.frozen_sites[site]
        cand = new_sites.get(site)
        if cand == frozen:
            continue
        # the frozen expression now lives at a site that is not frozen: a move
        elsewhere = [s for s in new_by_fp.get(frozen["fingerprint"], [])
                     if s != site and s not in ledger.frozen_sites]
        if elsewhere:
            findings.append(GateFinding("relocated_not_reused", site,
                                        f"same expression now at {elsewhere[0]}; relocation is a stop"))
        elif cand is None:
            findings.append(GateFinding("removed", site))
        elif cand["capability"] != frozen["capability"]:
            # under ordinal identity a removal ahead of a site can surface here too
            findings.append(GateFinding("capability_changed", site,
                                        f"{frozen['capability']} -> {cand['capability']}"))
        else:
            findings.append(GateFinding("call_changed", site, "call expression AST changed"))

    return GateResult(GateDecision.REJECT if findings else GateDecision.ACCEPT, findings)


# --------------------------------------------------------------------------
# Runtime: annotated execution with payload digest
# --------------------------------------------------------------------------

class _Annotate(ast.NodeTransformer):
    def __init__(self, site_of: Dict[int, str]):
        self.site_of = site_of

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        site = self.site_of.get(id(node))
        if site is not None:
            node.keywords.append(ast.keyword(arg="_site", value=ast.Constant(site)))
        return node


_SAFE_BUILTINS = {"range": range, "len": len, "str": str, "int": int, "dict": dict,
                  "list": list, "enumerate": enumerate, "sorted": sorted, "min": min, "max": max}


Provider = Callable[[str, Any], str]


def default_provider(capability: str, payload: Any) -> str:
    """Simulated provider. Fails deterministically on payloads with fail=True."""
    if isinstance(payload, dict) and payload.get("fail") is True:
        raise ProviderFailure(f"simulated failure in {capability}")
    return f"sim:{capability}:{payload_digest(payload)[:12]}"


@dataclass
class RunReport:
    outcome: RunOutcome
    replayed: List[str] = field(default_factory=list)
    dispatched: List[str] = field(default_factory=list)
    invoked: List[str] = field(default_factory=list)
    orphans: List[str] = field(default_factory=list)
    unreached: List[str] = field(default_factory=list)
    repeats: List[str] = field(default_factory=list)
    diverged: Optional[str] = None
    detail: str = ""
    ledger_out: Optional[Ledger] = None

    @property
    def dispatch_count(self) -> int:
        return len(self.dispatched)

    def repeated_dispatch_at_retained(self, committed: Ledger) -> List[str]:
        return [k for k in self.dispatched if k in committed.records]


class _Ctx:
    def __init__(self, prior: Ledger, out: Ledger, frozen_new: Dict[str, Dict[str, str]],
                 provider: Provider, repeat_policy: RepeatPolicy, side_effecting: frozenset,
                 report: RunReport):
        self._prior = prior
        self._out = out
        self._frozen_new = frozen_new
        self._provider = provider
        self._repeat_policy = repeat_policy
        self._side_effecting = side_effecting
        self._report = report
        self._path: List[int] = []
        self._occ: Dict[Tuple[str, Tuple[int, ...]], int] = {}

    def fanout(self, fn: Callable, items: List[Any]) -> List[Any]:
        results = []
        for i, item in enumerate(items):
            self._path.append(i)
            try:
                results.append(fn(self, item))
            finally:
                self._path.pop()
        return results

    def run(self, capability: str, payload: Any, _site: str = "") -> str:
        if not _site:
            raise ContractError("unannotated capability call")
        path = tuple(self._path)
        occ = self._occ.get((_site, path), 0)
        self._occ[(_site, path)] = occ + 1
        key = identity_key(_site, path, occ)
        digest = payload_digest(payload)
        self._report.invoked.append(key)

        rec = self._prior.records.get(key)
        if rec is not None:
            if rec.capability != capability:
                raise Divergence(key, "capability changed")
            if rec.payload_sha256 != digest:
                raise Divergence(key, "payload sha256 changed")
            self._report.replayed.append(key)
            self._out.records[key] = rec
            return rec.result

        # identity miss: occurrence ledger looks for a semantic repeat at (site, path)
        same_slot = [r for r in self._prior.records.values()
                     if r.site == _site and r.path == path and r.payload_sha256 == digest]
        if same_slot:
            self._report.repeats.append(key)
            policy = self._repeat_policy
            if policy is RepeatPolicy.AUTO:
                policy = RepeatPolicy.STOP if capability in self._side_effecting else RepeatPolicy.WARN
            if policy is RepeatPolicy.STOP:
                raise RepeatStop(key)

        result = self._provider(capability, payload)   # the branch that "spends"
        self._report.dispatched.append(key)
        self._out.records[key] = Record(_site, path, occ, capability, digest, result)
        self._out.frozen_sites[_site] = self._frozen_new[_site]
        return result


def run_workflow(src: str, committed: Any, inputs: Any = None, *,
                 provider: Provider = default_provider,
                 orphan_policy: OrphanPolicy = OrphanPolicy.WARN,
                 repeat_policy: RepeatPolicy = RepeatPolicy.AUTO,
                 side_effecting: Tuple[str, ...] = ("image.generate", "video.compose")) -> RunReport:
    """Execute a synthetic toy workflow under the runtime rule.

    Replay-or-divergence is claimed only for committed identities this run
    actually invokes; every committed identity it does not invoke is an orphan.
    """
    try:
        prior = _coerce_ledger(committed)
    except LedgerUnavailable as exc:
        return RunReport(RunOutcome.HELD_LEDGER_UNAVAILABLE, detail=str(exc))

    tree = ast.parse(src)
    sites = _sites_from_tree(tree)
    frozen_new = {s: {"capability": _capability_of(c), "fingerprint": call_fingerprint(c)}
                  for s, c in sites.items()}
    tree = _Annotate({id(c): s for s, c in sites.items()}).visit(tree)
    ast.fix_missing_locations(tree)
    namespace: Dict[str, Any] = {"__builtins__": dict(_SAFE_BUILTINS)}
    exec(compile(tree, "<synthetic-workflow>", "exec"), namespace)

    report = RunReport(RunOutcome.COMPLETED)
    out = Ledger(frozen_sites={s: prior.frozen_sites[s] for s in prior.frozen_sites}, records={})
    # previously committed records stay committed (the prefix only grows)
    out.records.update(prior.records)
    report.ledger_out = out
    ctx = _Ctx(prior, out, frozen_new, provider, repeat_policy, frozenset(side_effecting), report)
    try:
        namespace["main"](ctx, inputs)
    except Divergence as exc:
        report.outcome, report.diverged, report.detail = RunOutcome.STOPPED_DIVERGENCE, exc.key, str(exc)
    except RepeatStop as exc:
        report.outcome, report.detail = RunOutcome.STOPPED_REPEAT, str(exc)
    except ProviderFailure as exc:
        report.outcome, report.detail = RunOutcome.FAILED_PROVIDER, str(exc)

    invoked = set(report.invoked)
    not_invoked = sorted(k for k in prior.records if k not in invoked)
    if report.outcome is not RunOutcome.COMPLETED:
        # a stopped run did not reach these; that is not an orphan finding
        report.unreached = not_invoked
    else:
        report.orphans = not_invoked
    if report.outcome is RunOutcome.COMPLETED and report.orphans:
        report.outcome = (RunOutcome.STOPPED_ORPHAN if orphan_policy is OrphanPolicy.STOP
                          else RunOutcome.COMPLETED_WITH_ORPHANS)
    return report


def build_ledger(src: str, inputs: Any = None, provider: Provider = default_provider) -> Tuple[Ledger, RunReport]:
    """Run a toy workflow from an empty prefix; return the committed ledger."""
    report = run_workflow(src, Ledger(), inputs, provider=provider)
    return report.ledger_out, report


def naive_rerun_dispatches(src: str, inputs: Any = None, provider: Provider = default_provider) -> int:
    """Dispatches a full rerun from an empty prefix would make (ignoring failures)."""
    def never_fail(cap: str, payload: Any) -> str:
        if isinstance(payload, dict) and payload.get("fail") is True:
            payload = dict(payload, fail=False)
        return provider(cap, payload)
    return run_workflow(src, Ledger(), inputs, provider=never_fail,
                        repeat_policy=RepeatPolicy.WARN).dispatch_count


@dataclass
class RevisionReport:
    gate: GateResult
    run: RunReport
    naive_dispatches: int

    @property
    def completed(self) -> bool:
        return self.run.outcome in (RunOutcome.COMPLETED, RunOutcome.COMPLETED_WITH_ORPHANS)

    @property
    def dispatches_saved(self) -> int:
        """Saved versus a naive rerun; only meaningful for a completed repair."""
        return self.naive_dispatches - self.run.dispatch_count if self.completed else 0

    @property
    def spend_avoided_by_stop(self) -> int:
        """Naive-rerun dispatches not made because the candidate was stopped or held."""
        return 0 if self.completed else self.naive_dispatches - self.run.dispatch_count


def revise(old_src: str, new_src: str, committed: Any, inputs: Any = None, *,
           orphan_policy: OrphanPolicy = OrphanPolicy.WARN,
           repeat_policy: RepeatPolicy = RepeatPolicy.AUTO,
           provider: Provider = default_provider) -> RevisionReport:
    """Gate first; run only an accepted candidate. Rejected or held candidates spend nothing."""
    g = gate(old_src, new_src, committed)
    naive = naive_rerun_dispatches(new_src, inputs, provider) if _parses(new_src) else 0
    if g.decision is GateDecision.HOLD:
        return RevisionReport(g, RunReport(RunOutcome.HELD_LEDGER_UNAVAILABLE,
                                           detail="; ".join(f.detail for f in g.findings)), naive)
    if g.decision is GateDecision.REJECT:
        return RevisionReport(g, RunReport(RunOutcome.NOT_RUN_GATE_REJECTED,
                                           detail="; ".join(f"{f.kind}:{f.site}" for f in g.findings)), naive)
    return RevisionReport(g, run_workflow(new_src, committed, inputs, provider=provider,
                                          orphan_policy=orphan_policy, repeat_policy=repeat_policy), naive)


def _parses(src: str) -> bool:
    try:
        _sites_from_tree(ast.parse(src))
        return True
    except (SyntaxError, ContractError):
        return False
