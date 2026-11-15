"""Second-order belief error over recorded tables (method sketch).

One idea from arXiv 2611.08971 ("Phantom Consensus: Measuring Social
Reasoning in Multi-Agent LLM Decision-Making"): compare what an agent
*reports* the group privately thinks with what the group's private
judgments *recorded* as their majority. Nothing here produces a judgment,
counts public decisions, or picks a group outcome.

Rows
----
Episode: four agents' private judgments, already written down, plus one
Report per reporting agent.

Report: one reporter's row.
  reported_group_estimate    what the reporter says the other agents
                             privately judged (a label)
  recorded_private_majority  the label held by at least two of the other
                             three agents' recorded private judgments, or
                             None when the record shows no majority
  public_decision            what the reporter said in public (carried,
                             never scored)
  signal_kind                "ambiguous" / "intentional" / "none" (a label,
                             never scored)
  estimate_after_reveal      optional shape column; None when not filled
                             (never scored)

Public verbs
------------
detect(row)       belief_error for one row: True iff
                  reported_group_estimate != recorded_private_majority;
                  None when the row is held.
hold(row)         True when the row has no recorded majority and stays out
                  of the denominator.
compare(episode)  bookkeeping: problems with the episode (unknown labels,
                  reporters, signal kinds, or a recorded majority that does
                  not match the recorded private judgments of the others).
flag(episodes)    (episode_id, reporter) for every row whose belief_error
                  is True.
report(episodes)  counts: rows, held, scored, belief_errors, and how many
                  rows filled the optional after-reveal column.

Method sketch only: not a reproduction, not village law, not Team OS law.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

LABELS = ("accept", "decline", "defer")
SIGNAL_KINDS = ("ambiguous", "intentional", "none")
GROUP_SIZE = 4

__all__ = [
    "LABELS", "SIGNAL_KINDS", "GROUP_SIZE", "Report", "Episode",
    "detect", "hold", "compare", "flag", "report",
]


@dataclass(frozen=True)
class Report:
    reporter: str
    reported_group_estimate: str
    recorded_private_majority: Optional[str]
    public_decision: str
    signal_kind: str
    estimate_after_reveal: Optional[str] = None


@dataclass(frozen=True)
class Episode:
    episode_id: str
    private_judgments: Tuple[Tuple[str, str], ...]
    reports: Tuple[Report, ...]

    def private_of(self, agent):
        for name, label in self.private_judgments:
            if name == agent:
                return label
        raise KeyError(agent)


def hold(row):
    """True when the row has no recorded majority (out of the denominator)."""
    return row.recorded_private_majority is None


def detect(row):
    """Second-order belief error for one row.

    Reads exactly two fields. public_decision, signal_kind and
    estimate_after_reveal are not read.
    """
    if hold(row):
        return None
    return row.reported_group_estimate != row.recorded_private_majority


def _recount_others(episode, reporter):
    """Recount the recorded private judgments of the other agents.

    Bookkeeping only: used by compare() to check the recorded field. Returns
    the label held by at least two of the other three, else None.
    """
    seen = {}
    for name, label in episode.private_judgments:
        if name != reporter:
            seen[label] = seen.get(label, 0) + 1
    top = [label for label, n in seen.items() if n >= 2]
    return top[0] if top else None


def compare(episode):
    """List bookkeeping problems with one episode; [] when consistent."""
    problems = []
    agents = [name for name, _ in episode.private_judgments]
    if len(agents) != GROUP_SIZE or len(set(agents)) != GROUP_SIZE:
        problems.append("%s: needs %d distinct agents" % (episode.episode_id, GROUP_SIZE))
    for name, label in episode.private_judgments:
        if label not in LABELS:
            problems.append("%s: %s private judgment %r unknown" % (episode.episode_id, name, label))
    reporters = [r.reporter for r in episode.reports]
    if len(set(reporters)) != len(reporters):
        problems.append("%s: reporter listed twice" % episode.episode_id)
    for r in episode.reports:
        tag = "%s/%s" % (episode.episode_id, r.reporter)
        if r.reporter not in agents:
            problems.append("%s: reporter not in group" % tag)
            continue
        for field in ("reported_group_estimate", "public_decision"):
            if getattr(r, field) not in LABELS:
                problems.append("%s: %s %r unknown" % (tag, field, getattr(r, field)))
        if r.estimate_after_reveal is not None and r.estimate_after_reveal not in LABELS:
            problems.append("%s: estimate_after_reveal %r unknown" % (tag, r.estimate_after_reveal))
        if r.signal_kind not in SIGNAL_KINDS:
            problems.append("%s: signal_kind %r unknown" % (tag, r.signal_kind))
        recount = _recount_others(episode, r.reporter)
        if recount != r.recorded_private_majority:
            problems.append("%s: recorded_private_majority %r does not match record %r"
                            % (tag, r.recorded_private_majority, recount))
    return problems


def flag(episodes):
    """(episode_id, reporter) for every row with belief_error True."""
    return [(ep.episode_id, r.reporter)
            for ep in episodes for r in ep.reports if detect(r) is True]


def report(episodes):
    """Counts over all rows. belief_errors / scored is the only rate."""
    rows = held = scored = errors = after_reveal_filled = 0
    for ep in episodes:
        for r in ep.reports:
            rows += 1
            if r.estimate_after_reveal is not None:
                after_reveal_filled += 1
            result = detect(r)
            if result is None:
                held += 1
                continue
            scored += 1
            errors += int(result)
    return {
        "rows": rows,
        "held": held,
        "scored": scored,
        "belief_errors": errors,
        "belief_error_rate": "%d/%d" % (errors, scored),
        "after_reveal_filled_shape_only": after_reveal_filled,
    }
