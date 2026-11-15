"""Effect-keyed versus mechanism-only restriction in a tiny path-graph toy.

Clean-room stdlib method sketch of the agenda in arXiv 2611.09054
("From Emergence to Reversibility"). Not a reproduction: the paper has no
experiments and no code. Everything here is synthetic and deterministic.

World model
-----------
A logistics collective moves tokens along *paths*. A path is an ordered list
of steps; each step is taken by one agent, reads some tokens from the path's
working state, and writes some tokens. A sink step (dispatch-like action)
sends a vehicle into a region. Dispatch into a closed region is the
prohibited effect; dispatch into an open region and relay restoration are
required service.

Two restrictions are compared:

* restrict_mechanism(...) holds steps that use one named mechanism (here:
  issuing a fresh route for the closed region). It asks "is this the
  original mechanism?" -- the paper's failure mode.
* restrict_effect(...) holds a sink step whenever that step would produce
  the prohibited effect, whatever mechanism or source fed it. It asks
  "would this step dispatch into a closed region?".

The effect-keyed hold looks only at (action kind, target region, closed
regions). It never labels tokens by where they came from and never halts
steps just because they follow an earlier step.

Growth: recheck_update(...) evaluates proposed new paths (and new sink
actions) before they join the world. A proposed path that would still
produce the prohibited effect under the current restriction is flagged and
the whole update fails closed (nothing is registered).
"""

from dataclasses import dataclass, field

PROHIBITED = "dispatch_closed_region"
SERVE_OPEN = "serve_open_region"
RESTORE = "restore_service"
REQUIRED_SERVICE = (SERVE_OPEN, RESTORE)

# Action kind -> effect family. Growth may add new sink actions.
BASE_ACTIONS = {
    "issue_route": "produce",
    "verify_route": "produce",
    "recall_plan": "produce",
    "hold_plan": "produce",
    "delegate_dispatch": "produce",
    "restore_relay": "repair",
    "relay_plan": "produce",
    "dispatch": "sink",
}


@dataclass(frozen=True)
class Step:
    agent: str
    action: str
    mechanism: str
    reads: tuple = ()
    writes: tuple = ()
    region: str = ""


@dataclass(frozen=True)
class Path:
    name: str
    steps: tuple
    start: frozenset = frozenset()
    kind: str = "alternate"  # original | alternate | service | joint | growth


@dataclass
class World:
    closed_regions: frozenset
    agent_scopes: dict
    paths: list
    actions: dict = field(default_factory=lambda: dict(BASE_ACTIONS))

    def path(self, name):
        for p in self.paths:
            if p.name == name:
                return p
        raise KeyError(name)


@dataclass(frozen=True)
class Restriction:
    """A held effect or mechanism. ``covered_actions`` is the set of sink
    interfaces the intervention sits on (the paper's dispatch gate)."""
    keyed_on: str  # "effect" | "mechanism"
    effect: str = PROHIBITED
    mechanism: str = ""
    regions: frozenset = frozenset()
    covered_actions: frozenset = frozenset({"dispatch"})

    def hold_reason(self, step, world):
        if self.keyed_on == "mechanism":
            if step.mechanism == self.mechanism and step.region in self.regions:
                return "hold:mechanism:" + self.mechanism
            return ""
        if self.keyed_on == "effect":
            if step.action in self.covered_actions and \
                    effect_of(step, world) == self.effect:
                return "hold:effect:" + self.effect
            return ""
        raise ValueError("unknown restriction key: %r" % (self.keyed_on,))


def restrict_effect(effect=PROHIBITED, covered_actions=("dispatch",)):
    return Restriction(keyed_on="effect", effect=effect,
                       covered_actions=frozenset(covered_actions))


def restrict_mechanism(mechanism, regions):
    return Restriction(keyed_on="mechanism", mechanism=mechanism,
                       regions=frozenset(regions))


def extend_restriction(restriction, extra_actions):
    """Restrict one more sink interface (the gate added once a bypass is
    known)."""
    return Restriction(keyed_on=restriction.keyed_on,
                       effect=restriction.effect,
                       mechanism=restriction.mechanism,
                       regions=restriction.regions,
                       covered_actions=restriction.covered_actions
                       | frozenset(extra_actions))


def effect_of(step, world):
    """Effect a single step would produce. Depends only on the action kind,
    the target region and which regions are closed -- not on where the
    step's inputs came from."""
    family = world.actions.get(step.action)
    if family is None:
        raise ValueError("unknown action: %r" % (step.action,))
    if family == "sink":
        return PROHIBITED if step.region in world.closed_regions else SERVE_OPEN
    if family == "repair":
        return RESTORE
    return ""


def local_check(step, world):
    """Each agent's own scope check: is this action inside the agent's
    role? Says nothing about what steps combine into."""
    return step.action in world.agent_scopes.get(step.agent, ())


@dataclass(frozen=True)
class PathReport:
    name: str
    kind: str
    effects: tuple
    held_at: int  # index of held step, -1 if none
    hold: str
    stalled_at: int  # index of step whose reads were missing, -1 if none
    local_ok: tuple

    @property
    def prohibited(self):
        return PROHIBITED in self.effects

    @property
    def served(self):
        """Required service delivered: the path ran to the end and produced
        a service effect."""
        return (self.held_at < 0 and self.stalled_at < 0
                and any(e in REQUIRED_SERVICE for e in self.effects))


def run_path(world, path, restriction=None):
    state = set(path.start)
    effects = []
    held_at, hold, stalled_at = -1, "", -1
    local = []
    for i, step in enumerate(path.steps):
        local.append(local_check(step, world))
        if restriction is not None:
            reason = restriction.hold_reason(step, world)
            if reason:
                held_at, hold = i, reason
                break  # fail closed: the path stops here
        if not set(step.reads) <= state:
            stalled_at = i
            break
        eff = effect_of(step, world)
        if eff:
            effects.append(eff)
        state.update(step.writes)
    return PathReport(path.name, path.kind, tuple(effects), held_at, hold,
                      stalled_at, tuple(local))


@dataclass(frozen=True)
class Report:
    restriction: str
    paths: tuple

    def by_name(self, name):
        for r in self.paths:
            if r.name == name:
                return r
        raise KeyError(name)

    @property
    def prohibited_count(self):
        return sum(1 for r in self.paths if r.prohibited)

    @property
    def service_count(self):
        return sum(1 for r in self.paths if r.served)

    def leaking(self):
        return tuple(r.name for r in self.paths if r.prohibited)


def detect(world, restriction=None, paths=None):
    """Run every enumerated path under ``restriction`` and report effects."""
    label = "none" if restriction is None else restriction.keyed_on
    todo = world.paths if paths is None else paths
    return Report(label, tuple(run_path(world, p, restriction) for p in todo))


def compliance_check_original(world, restriction):
    """A routine compliance check that only inspects the original path:
    "is the original mechanism held?". Passing it says nothing about
    alternate paths."""
    originals = [p for p in world.paths if p.kind == "original"]
    return all(run_path(world, p, restriction).held_at >= 0 for p in originals)


def rare_bar(report, max_rate=0.0):
    """The paper's bar, toy form: the prohibited effect stays rare (rate at
    most ``max_rate`` over enumerated paths) while required service still
    happens. A pass describes these enumerated paths only, not all future
    growth."""
    total = len(report.paths)
    rate = report.prohibited_count / total if total else 0.0
    return rate <= max_rate and report.service_count > 0


def compare(world, effect_restriction, mechanism_restriction):
    eff = detect(world, effect_restriction)
    mech = detect(world, mechanism_restriction)
    return {
        "effect_keyed": {
            "prohibited": eff.prohibited_count,
            "service": eff.service_count,
            "leaking": eff.leaking(),
            "rare_bar": rare_bar(eff),
        },
        "mechanism_only": {
            "prohibited": mech.prohibited_count,
            "service": mech.service_count,
            "leaking": mech.leaking(),
            "rare_bar": rare_bar(mech),
            "compliance_check_original": compliance_check_original(
                world, mechanism_restriction),
        },
    }


@dataclass(frozen=True)
class UpdateReport:
    status: str  # "registered" | "fail_closed"
    flags: tuple
    service_kept: bool


def recheck_update(world, restriction, new_paths, new_actions=None):
    """Recheck control before an update. Simulate the world as it would be
    after the update; if any path (new or old) would produce the prohibited
    effect under ``restriction``, or any required-service path (kind
    "service") would no longer serve, flag it and fail closed without
    changing ``world``."""
    actions = dict(world.actions)
    actions.update(new_actions or {})
    trial = World(world.closed_regions, world.agent_scopes,
                  list(world.paths) + list(new_paths), actions)
    report = detect(trial, restriction)
    flags = tuple("flag:prohibited:" + n for n in report.leaking())
    lost = tuple(r.name for r in report.paths if r.kind == "service" and not r.served)
    service_kept = not lost
    flags += tuple("flag:service_lost:" + n for n in lost)
    if flags:
        return UpdateReport("fail_closed", flags, service_kept)
    world.actions.update(new_actions or {})
    world.paths.extend(new_paths)
    return UpdateReport("registered", (), service_kept)


def register_unchecked(world, new_paths, new_actions=None):
    """What a mechanism-only regime does with growth: add the path without
    asking what effect it produces. Used only as the contrast case."""
    world.actions.update(new_actions or {})
    world.paths.extend(new_paths)
    return UpdateReport("registered", (), True)
