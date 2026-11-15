"""Contract-derived assurance and a tiny skill registry (clean-room, stdlib).

A skill is a manifest (typed input contract, output contract, declared safety
boundary), a deterministic effect, and the author's own checks. Before a skill
can be registered, ``detect`` derives probe inputs from the manifest's input
contract, runs the effect on every probe, and checks each output against the
manifest's output contract and safety boundary. The author's checks must also
pass, but they are not enough: a skill whose effect breaks a declared
boundary on any derived probe is rejected even when the author's checks pass.

Public verbs: hold, register, reject, report (Registry); detect, compare
(module). ``invoke`` runs a registered skill and rejects out-of-contract input
before the effect is called.
"""

import copy
import importlib
import inspect
import io
import itertools
import json
import os
import sys
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(HERE, "manifest.json")

SYNTH_NAMES = frozenset(("exec", "eval", "compile", "__import__"))
NETWORK_NAMES = frozenset(("socket", "urllib", "http", "requests", "ssl"))
TYPES = ("integer", "string", "boolean")


class Rejected(Exception):
    """Raised when an input, output or skill is rejected."""

    def __init__(self, reasons):
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons))


# ---------------------------------------------------------------- manifest

def load_manifest(path=MANIFEST_PATH):
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    problems = check_manifest(manifest)
    if problems:
        raise Rejected(problems)
    return manifest


def check_manifest(manifest):
    """Return a list of structural problems with a manifest (empty if none)."""
    problems = []
    for key in ("skill_id", "version", "effect", "input_contract",
                "output_contract", "safety_boundary"):
        if key not in manifest:
            problems.append("manifest missing %r" % key)
    for side in ("input_contract", "output_contract"):
        contract = manifest.get(side, {})
        if contract.get("extra_fields") != "reject":
            problems.append("%s.extra_fields must be 'reject'" % side)
        fields = contract.get("fields") or []
        if not fields:
            problems.append("%s has no fields" % side)
        for f in fields:
            if f.get("type") not in TYPES:
                problems.append("%s.%s: unknown type %r"
                                % (side, f.get("name"), f.get("type")))
            if f.get("type") == "integer" and not (
                    isinstance(f.get("minimum"), int)
                    and isinstance(f.get("maximum"), int)
                    and f["minimum"] <= f["maximum"]):
                problems.append("%s.%s: integer needs minimum <= maximum"
                                % (side, f.get("name")))
            if f.get("type") == "string" and not f.get("enum"):
                problems.append("%s.%s: string needs a closed enum"
                                % (side, f.get("name")))
    return problems


def load_effect(manifest):
    """Import the effect named by the manifest from this directory."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    module = importlib.import_module(manifest["effect"]["module"])
    return getattr(module, manifest["effect"]["function"])


# ---------------------------------------------------------------- contracts

def _is_type(value, kind):
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    return False


def check_against(contract, record, side):
    """Return violations of ``record`` against a typed field contract."""
    if not isinstance(record, dict):
        return ["%s: not an object (%s)" % (side, type(record).__name__)]
    out = []
    names = [f["name"] for f in contract["fields"]]
    for f in contract["fields"]:
        name = f["name"]
        if name not in record:
            out.append("%s.%s: missing" % (side, name))
            continue
        value = record[name]
        if not _is_type(value, f["type"]):
            out.append("%s.%s=%r: not %s" % (side, name, value, f["type"]))
            continue
        if "minimum" in f and value < f["minimum"]:
            out.append("%s.%s=%r: below declared minimum %r"
                       % (side, name, value, f["minimum"]))
        if "maximum" in f and value > f["maximum"]:
            out.append("%s.%s=%r: above declared maximum %r"
                       % (side, name, value, f["maximum"]))
        if "enum" in f and value not in f["enum"]:
            out.append("%s.%s=%r: not in declared enum %r"
                       % (side, name, value, f["enum"]))
    for name in sorted(set(record) - set(names)):
        out.append("%s.%s: undeclared field" % (side, name))
    return out


def check_boundary(boundary, output):
    """Return violations of the declared safety boundary by one output."""
    out = []
    if not isinstance(output, dict):
        return out
    for name in boundary.get("forbidden_output_fields", []):
        if name in output:
            out.append("boundary: forbidden output field %r" % name)
    for name, values in sorted(boundary.get("forbidden_output_values", {}).items()):
        if output.get(name) in values:
            out.append("boundary: forbidden value %s=%r" % (name, output[name]))
    return out


def scan_source(effect, boundary):
    """Simple original static check on the effect's own source tokens.

    Flags identifiers that synthesize or load code at runtime, and network
    module names, when the boundary declares them out of bounds. Strings and
    comments are not identifiers, so they do not trip the check.
    """
    try:
        src = inspect.getsource(effect)
    except (OSError, TypeError):
        return ["source: effect source unavailable; cannot scan"]
    names = set()
    for tok in tokenize.generate_tokens(io.StringIO(_dedent(src)).readline):
        if tok.type == tokenize.NAME:
            names.add(tok.string)
    out = []
    if boundary.get("no_runtime_code_synthesis"):
        for name in sorted(names & SYNTH_NAMES):
            out.append("source: runtime code synthesis via %r" % name)
    if boundary.get("no_network_modules"):
        for name in sorted(names & NETWORK_NAMES):
            out.append("source: network module %r" % name)
    return out


def _dedent(src):
    lines = src.splitlines(True)
    pad = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    return "".join(l[pad:] for l in lines)


# ------------------------------------------------------------------ probes

def _field_values(f):
    if f["type"] == "boolean":
        return [False, True]
    if f["type"] == "string":
        return list(f["enum"])
    lo, hi = f["minimum"], f["maximum"]
    vals = {lo, hi, (lo + hi) // 2, min(lo + 1, hi), max(hi - 1, lo)}
    return sorted(vals)


def derive_probes(manifest):
    """Deterministic in-contract probe inputs derived only from the manifest:
    integer edges and midpoint, every enum value, both booleans, crossed."""
    fields = manifest["input_contract"]["fields"]
    names = [f["name"] for f in fields]
    probes = [dict(zip(names, combo))
              for combo in itertools.product(*[_field_values(f) for f in fields])]
    for p in probes:
        assert not check_against(manifest["input_contract"], p, "input"), p
    return probes


# ------------------------------------------------------------------- skill

class Skill:
    """A manifest, an effect, and the author's own checks.

    ``author_checks`` is a list of (name, fn) where fn(call) -> bool and
    ``call`` runs the effect. Every effect call is counted in ``calls``.
    """

    def __init__(self, manifest, effect, author_checks=()):
        self.manifest = manifest
        self.effect = effect
        self.author_checks = list(author_checks)
        self.calls = 0

    @property
    def skill_id(self):
        return self.manifest["skill_id"]

    def call(self, payload):
        self.calls += 1
        return self.effect(copy.deepcopy(payload))


def run_author_checks(skill):
    results = []
    for name, fn in skill.author_checks:
        try:
            ok = bool(fn(skill.call))
            detail = "" if ok else "returned false"
        except Exception as exc:  # an author check that raises fails
            ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
        results.append({"check": name, "passed": ok, "detail": detail})
    return results


def detect(skill):
    """Contract-derived assurance. Returns a report dict; never registers."""
    m = skill.manifest
    boundary = m["safety_boundary"]
    violations = list(check_manifest(m))
    violations += scan_source(skill.effect, boundary)
    probes = derive_probes(m) if not violations else []
    calls_before = skill.calls
    failing = []
    for probe in ([] if violations else probes):
        try:
            first = skill.call(probe)
        except Exception as exc:
            failing.append({"probe": probe,
                            "violations": ["effect raised %s" % type(exc).__name__]})
            continue
        found = check_against(m["output_contract"], first, "output")
        found += check_boundary(boundary, first)
        if boundary.get("deterministic"):
            second = skill.call(probe)
            if second != first:
                found.append("boundary: not deterministic (%r then %r)"
                             % (first, second))
        if found:
            failing.append({"probe": probe, "violations": found})
    return {
        "skill_id": m.get("skill_id"),
        "status": "fail" if (violations or failing) else "pass",
        "static_violations": violations,
        "probes": len(probes),
        "failing_probes": failing,
        "effect_calls": skill.calls - calls_before,
    }


def compare(skill):
    """Author checks alone versus contract-derived assurance, side by side."""
    author = run_author_checks(skill)
    assured = detect(skill)
    return {
        "skill_id": skill.skill_id,
        "author_checks": "pass" if author and all(r["passed"] for r in author) else "fail",
        "contract_assurance": assured["status"],
        "first_failure": (assured["static_violations"][:1]
                          or (assured["failing_probes"][0]["violations"][:1]
                              if assured["failing_probes"] else [])),
    }


# ---------------------------------------------------------------- registry

class Registry:
    """Skills are held, then registered only after assurance passes."""

    def __init__(self):
        self._held = {}
        self._registered = {}
        self._rejected = {}
        self.log = []

    def hold(self, skill):
        sid = skill.skill_id
        if sid in self._registered:
            raise Rejected(["%s: already registered" % sid])
        self._held[sid] = skill
        self.log.append(("hold", sid))
        return "held"

    def register(self, skill_id):
        """Run author checks and contract-derived assurance; register only if
        both pass, otherwise reject. Callers cannot hand in their own report."""
        skill = self._held.get(skill_id)
        if skill is None:
            return self.reject(skill_id, ["not held"], None)
        author = run_author_checks(skill)
        assured = detect(skill)
        reasons = []
        if not author:
            reasons.append("no author checks")
        reasons += ["author check %s failed" % r["check"] for r in author if not r["passed"]]
        reasons += assured["static_violations"]
        for f in assured["failing_probes"]:
            reasons += ["probe %s: %s" % (json.dumps(f["probe"], sort_keys=True), v)
                        for v in f["violations"]]
        if reasons:
            return self.reject(skill_id, reasons, assured)
        del self._held[skill_id]
        self._registered[skill_id] = skill
        self.log.append(("register", skill_id))
        return {"skill_id": skill_id, "status": "registered", "assurance": assured}

    def reject(self, skill_id, reasons, assurance):
        skill = self._held.pop(skill_id, None)
        if skill is not None:
            self._rejected[skill_id] = skill
        self.log.append(("reject", skill_id))
        return {"skill_id": skill_id, "status": "rejected", "reasons": list(reasons),
                "assurance": assurance}

    def report(self):
        return {"held": sorted(self._held), "registered": sorted(self._registered),
                "rejected": sorted(self._rejected), "log": list(self.log)}

    def invoke(self, skill_id, payload):
        """Run a registered skill. Out-of-contract input is rejected before
        the effect runs; an out-of-contract output is held back, not returned."""
        skill = self._registered.get(skill_id)
        if skill is None:
            raise Rejected(["%s: not registered" % skill_id])
        m = skill.manifest
        problems = check_against(m["input_contract"], payload, "input")
        if problems:
            raise Rejected(problems)
        output = skill.call(payload)
        problems = (check_against(m["output_contract"], output, "output")
                    + check_boundary(m["safety_boundary"], output))
        if problems:
            raise Rejected(problems)
        return output
