"""Evidence-linked memory: a read-time descend rule (stdlib method sketch).

Memory holds three linked records: an insight names a summary, and the
summary names the trajectory of the run the insight came from
(insight -> summary -> trajectory). Three agents act on the same toy task:

- empty_memory: ignores memory and takes its own default action;
- bare_insight: follows the first relevant insight as written;
- evidence_linked: checks each relevant insight at read time. An insight
  that lacks its detail, conflicts with another relevant insight, or does not
  come from a run labelled exactly "success" is not acted on until the agent
  descends to its trajectory. The run label is read from the linked summary,
  not only from the insight's own copy: both must say "success", and an
  absent outcome on either counts as a failed origin. The trajectory wins:
  the insight is confirmed, filled, corrected or rejected, never followed
  against the evidence. Only a run labelled "success" supplies evidence; a
  failed run can reject an insight but never supplies an action. A clean
  insight (both labels "success", detail present, no conflict) is used with
  zero descends.

Every relevant insight's link chain is checked before any insight is used.
A missing, dangling or unreadable link, or a trajectory for another key,
resolves only through the declared on_unresolved. A missing or unknown
declaration is config_error and nothing runs.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

# Declared terminal values for an unresolved link (shared vocabulary with the
# silence doctrine of w14-silence-expiry).
DENY, SAFE_FALLBACK, ESCALATE, HOLD = "deny", "safe_fallback", "escalate", "hold"
ON_UNRESOLVED = (DENY, SAFE_FALLBACK, ESCALATE, HOLD)
STATUS_ON_UNRESOLVED = {DENY: "denied", SAFE_FALLBACK: "fallback", ESCALATE: "escalated", HOLD: "held"}
DONE, CONFIG_ERROR = "done", "config_error"

SUCCESS = "success"
OK, ERROR = "ok", "error"

EMPTY, BARE, LINKED = "empty_memory", "bare_insight", "evidence_linked"
AGENTS = (EMPTY, BARE, LINKED)

MISSING_DETAIL, CONFLICT, FAILED_ORIGIN = "missing_detail", "conflict", "failed_origin"

FOLLOWED, CONFIRMED, FILLED = "followed", "confirmed", "filled"
CORRECTED, REJECTED, UNRESOLVED = "corrected", "rejected", "unresolved"


@dataclass(frozen=True)
class Step:
    verb: str
    arg: str
    result: str  # OK or ERROR


@dataclass(frozen=True)
class Trajectory:
    traj_id: str
    key: str
    steps: Optional[Tuple[Step, ...]]  # None: the record could not be read


@dataclass(frozen=True)
class Summary:
    summary_id: str
    traj_id: Optional[str]
    outcome: Optional[str]
    why: str


@dataclass(frozen=True)
class Insight:
    insight_id: str
    key: str
    verb: str
    arg: Optional[str]
    outcome: Optional[str]
    summary_id: Optional[str]


@dataclass(frozen=True)
class Memory:
    insights: Tuple[Insight, ...]
    summaries: Tuple[Summary, ...]
    trajectories: Tuple[Trajectory, ...]


@dataclass(frozen=True)
class Task:
    task_id: str
    key: str
    answer: Tuple[str, str]
    default: Tuple[str, str]


@dataclass(frozen=True)
class Config:
    on_unresolved: Optional[str]


@dataclass(frozen=True)
class Result:
    agent: str
    task_id: str
    status: str
    action: Optional[Tuple[str, str]]
    passed: bool
    descends: int
    verdicts: Tuple[Tuple[str, str], ...]


EMPTY_MEMORY = Memory((), (), ())

# ---------------------------------------------------------------- loading

_INSIGHT_FIELDS = {"id", "key", "verb", "arg", "outcome", "summary"}
_SUMMARY_FIELDS = {"id", "trajectory", "outcome", "why"}
_TRAJ_FIELDS = {"id", "key", "steps"}


def _opt_str(d, name):
    v = d.get(name)
    return v if v is None or type(v) is str else _BAD


_BAD = object()


def _steps(raw):
    """A list of [verb, arg, result] lists, or None when it cannot be read."""
    if type(raw) is not list:
        return None
    out = []
    for s in raw:
        if type(s) is not list or len(s) != 3 or any(type(x) is not str for x in s):
            return None
        if s[2] not in (OK, ERROR):
            return None
        out.append(Step(s[0], s[1], s[2]))
    return tuple(out)


def load_memory(records):
    """Build a Memory from plain dict records; None if they are malformed.

    Absent optional fields become None. None never means clean: an absent
    outcome is a failed origin, an absent arg is a missing detail and an
    absent link is unresolved.
    """
    if type(records) is not dict or set(records) - {"insights", "summaries", "trajectories"}:
        return None
    ins, sums, trs = [], [], []
    for d in records.get("insights", []):
        if type(d) is not dict or set(d) - _INSIGHT_FIELDS:
            return None
        if any(type(d.get(k)) is not str for k in ("id", "key", "verb")):
            return None
        arg, outcome, link = _opt_str(d, "arg"), _opt_str(d, "outcome"), _opt_str(d, "summary")
        if _BAD in (arg, outcome, link):
            return None
        ins.append(Insight(d["id"], d["key"], d["verb"], arg, outcome, link))
    for d in records.get("summaries", []):
        if type(d) is not dict or set(d) - _SUMMARY_FIELDS or type(d.get("id")) is not str:
            return None
        link, outcome = _opt_str(d, "trajectory"), _opt_str(d, "outcome")
        why = d.get("why", "")
        if _BAD in (link, outcome) or type(why) is not str:
            return None
        sums.append(Summary(d["id"], link, outcome, why))
    for d in records.get("trajectories", []):
        if type(d) is not dict or set(d) - _TRAJ_FIELDS:
            return None
        if type(d.get("id")) is not str or type(d.get("key")) is not str:
            return None
        trs.append(Trajectory(d["id"], d["key"], _steps(d.get("steps"))))
    return Memory(tuple(ins), tuple(sums), tuple(trs))


# ------------------------------------------------------------- validation

def _is_str(x):
    return type(x) is str and x != ""


def _is_opt_str(x):
    return x is None or type(x) is str


def _is_action(a):
    return type(a) is tuple and len(a) == 2 and _is_str(a[0]) and _is_str(a[1])


def _valid_memory(m):
    if type(m) is not Memory:
        return False
    ins, sums, trs = m.insights, m.summaries, m.trajectories
    if type(ins) is not tuple or type(sums) is not tuple or type(trs) is not tuple:
        return False
    for i in ins:
        if type(i) is not Insight or not (_is_str(i.insight_id) and _is_str(i.key) and _is_str(i.verb)):
            return False
        if not (_is_opt_str(i.arg) and _is_opt_str(i.outcome) and _is_opt_str(i.summary_id)):
            return False
    for s in sums:
        if type(s) is not Summary or not _is_str(s.summary_id):
            return False
        if not (_is_opt_str(s.traj_id) and _is_opt_str(s.outcome) and type(s.why) is str):
            return False
    for t in trs:
        if type(t) is not Trajectory or not (_is_str(t.traj_id) and _is_str(t.key)):
            return False
        if t.steps is not None:
            if type(t.steps) is not tuple:
                return False
            for st in t.steps:
                if type(st) is not Step or type(st.verb) is not str or type(st.arg) is not str:
                    return False
                if st.result not in (OK, ERROR) or type(st.result) is not str:
                    return False
    for ids in ([i.insight_id for i in ins], [s.summary_id for s in sums], [t.traj_id for t in trs]):
        if len(ids) != len(set(ids)):
            return False
    return True


def _valid_task(t):
    return type(t) is Task and _is_str(t.task_id) and _is_str(t.key) and _is_action(t.answer) \
        and _is_action(t.default)


def _declared(cfg):
    """The declared on_unresolved, or None when the declaration is unusable."""
    if type(cfg) is not Config:
        return None
    oe = cfg.on_unresolved
    if type(oe) is not str or oe not in ON_UNRESOLVED:
        return None
    return ON_UNRESOLVED[ON_UNRESOLVED.index(oe)]


# ------------------------------------------------------------ the read rule

def has_detail(ins):
    return type(ins.arg) is str and ins.arg != ""


def _disagree(a, b):
    if a.verb != b.verb:
        return True
    return has_detail(a) and has_detail(b) and a.arg != b.arg


def _summary(ins, memory):
    """The summary the insight links to, or None (no fallback to any other)."""
    sid = ins.summary_id
    if type(sid) is not str:
        return None
    return next((s for s in memory.summaries if s.summary_id == sid), None)


def run_label(ins, memory):
    """The outcome label of the insight's source run, from its summary."""
    summ = _summary(ins, memory)
    return None if summ is None else summ.outcome


def triggers(ins, relevant, memory):
    """The descend triggers that hold for one insight among the relevant ones."""
    out = []
    if not has_detail(ins):
        out.append(MISSING_DETAIL)
    if any(o.insight_id != ins.insight_id and _disagree(ins, o) for o in relevant):
        out.append(CONFLICT)
    claimed = ins.outcome == SUCCESS
    labelled = run_label(ins, memory) == SUCCESS
    if not (claimed and labelled):
        out.append(FAILED_ORIGIN)
    return tuple(out)


def resolve_link(ins, memory):
    """Follow insight -> summary -> trajectory; None if any hop fails."""
    summ = _summary(ins, memory)
    if summ is None:
        return None
    tid = summ.traj_id
    if type(tid) is not str:
        return None
    tr = next((t for t in memory.trajectories if t.traj_id == tid), None)
    if tr is None or tr.steps is None:
        return None
    if tr.key != ins.key:
        return None
    return tr


def read_trajectory(ins, tr, run_ok):
    """Compare an insight with its trajectory. Returns (verdict, evidence).

    Evidence is the last action the trajectory records as ok, and only a run
    labelled "success" gives evidence: an ok step in a failed run did not
    make the run pass, so it is not taken as the answer. A failed run, or a
    run with no ok step, rejects the insight and gives no evidence.
    """
    if not run_ok:
        return REJECTED, None
    ok = [s for s in tr.steps if s.result == OK]
    if not ok:
        return REJECTED, None
    ev = (ok[-1].verb, ok[-1].arg)
    if not has_detail(ins):
        return (FILLED if ev[0] == ins.verb else CORRECTED), ev
    if (ins.verb, ins.arg) == ev:
        return CONFIRMED, ev
    return CORRECTED, ev


def _agrees(ins, ev):
    return ins.verb == ev[0] and (not has_detail(ins) or ins.arg == ev[1])


def _bare_action(ins, task):
    return (ins.verb, ins.arg if has_detail(ins) else task.default[1])


def relevant_insights(memory, task):
    return sorted((i for i in memory.insights if i.key == task.key), key=lambda i: i.insight_id)


def _linked(memory, task, oe):
    rel = relevant_insights(memory, task)
    if not rel:
        return DONE, task.default, 0, {}
    trajs, dangling = {}, []
    for ins in rel:
        tr = resolve_link(ins, memory)
        if tr is None:
            dangling.append(ins.insight_id)
        trajs[ins.insight_id] = tr
    if dangling:
        verdicts = {iid: UNRESOLVED for iid in dangling}
        action = task.default if oe == SAFE_FALLBACK else None
        return STATUS_ON_UNRESOLVED[oe], action, 0, verdicts
    trig = {ins.insight_id: triggers(ins, rel, memory) for ins in rel}
    verdicts, evidence, descends = {}, None, 0
    for ins in rel:
        if not trig[ins.insight_id]:
            continue
        if evidence is None:
            descends += 1
            run_ok = run_label(ins, memory) == SUCCESS
            verdict, ev = read_trajectory(ins, trajs[ins.insight_id], run_ok)
            verdicts[ins.insight_id] = verdict
            if ev is not None:
                evidence = ev
        else:
            verdicts[ins.insight_id] = CONFIRMED if _agrees(ins, evidence) else REJECTED
    clean = [ins for ins in rel if not trig[ins.insight_id]]
    if evidence is not None:
        action = evidence
        for ins in clean:
            verdicts[ins.insight_id] = FOLLOWED if (ins.verb, ins.arg) == evidence else REJECTED
    elif clean:
        action = (clean[0].verb, clean[0].arg)
        for ins in clean:
            verdicts[ins.insight_id] = FOLLOWED
    else:
        action = task.default
    return DONE, action, descends, verdicts


def run(agent, memory, task, cfg=None):
    """Run one agent on one task. Anything malformed is config_error."""
    def out(status, action=None, descends=0, verdicts=None):
        passed = status in (DONE, STATUS_ON_UNRESOLVED[SAFE_FALLBACK]) and action is not None \
            and action == task.answer
        v = tuple(sorted((verdicts or {}).items()))
        return Result(agent, task.task_id if _valid_task(task) else "", status, action, passed, descends, v)

    if type(agent) is not str or agent not in AGENTS or not _valid_task(task):
        return Result(str(agent), "", CONFIG_ERROR, None, False, 0, ())
    if agent == EMPTY:
        return out(DONE, task.default)
    if not _valid_memory(memory):
        return out(CONFIG_ERROR)
    if agent == BARE:
        rel = relevant_insights(memory, task)
        return out(DONE, _bare_action(rel[0], task) if rel else task.default)
    oe = _declared(cfg)
    if oe is None:
        return out(CONFIG_ERROR)
    status, action, descends, verdicts = _linked(memory, task, oe)
    return out(status, action, descends, verdicts)


def compare(memory, tasks, cfg):
    """All three agents on every task: {agent: tuple of Result}."""
    return {a: tuple(run(a, memory, t, cfg) for t in tasks) for a in AGENTS}


def report(results):
    """Pass counts per agent, and the agent's wrong actions (acted, failed)."""
    rows = {}
    for agent, rs in results.items():
        wrong = sum(1 for r in rs if r.action is not None and not r.passed)
        rows[agent] = {"tasks": len(rs), "passed": sum(r.passed for r in rs), "wrong_actions": wrong,
                       "descends": sum(r.descends for r in rs)}
    return rows
