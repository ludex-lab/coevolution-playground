"""Decision-field source authority: a clean-room stdlib method sketch.

Method sketch of arXiv 2611.07640 (paper method only; no repo code or data
copied). Each consequential decision field declares exactly one authorized
source. A claim may set a field only when it comes from that field's
authorized source. Everything else is reported:

* REJECT_SET -- a known source tried to set a field it is not the authorized
  source for. The field is left unchanged. The claim's wording, politeness,
  truthfulness, or lack of override-style instructions are never inspected.
* HOLD -- unknown source, missing declaration, ambiguous declaration, or
  conflict. Nothing is auto-resolved; the field is left unchanged.
* APPLIED -- the authorized source's value was copied into the field as
  data. APPLIED is not permission to act and not a truth verdict: every
  APPLIED record carries truth_status "unverified" (authority is not a truth
  oracle). Correctness is a separate check (check_correctness).

There is no path in this module that authorizes a send, payment, or merge.
hold_consequential_action() always returns HOLD and never emits a token.
"""

from collections import namedtuple

APPLIED = "APPLIED"
HOLD = "HOLD"
REJECT_SET = "REJECT_SET"

TRUTH_UNVERIFIED = "unverified"

REASON_AUTHORIZED_SOURCE = "authorized-source"
REASON_NOT_AUTHORIZED_SOURCE = "not-authorized-source-for-field"
REASON_UNKNOWN_SOURCE = "unknown-source"
REASON_MISSING_MAP = "missing-authority-map"
REASON_MISSING_DECLARATION = "missing-declaration-for-field"
REASON_AMBIGUOUS_DECLARATION = "ambiguous-declaration"
REASON_CONFLICTING_DECLARATION = "conflicting-declaration"
REASON_CONFLICT = "conflict-authorized-values-disagree"
REASON_HELD_WITH_FIELD = "field-held"
REASON_NO_ACTION_PATH = "no-send-payment-merge-path-in-sketch"

CONSEQUENTIAL_ACTIONS = ("send", "payment", "merge")

Claim = namedtuple("Claim", ["source", "field", "value", "text"])
FieldRecord = namedtuple(
    "FieldRecord", ["field", "status", "source", "value", "reason", "truth_status"]
)
CorrectnessResult = namedtuple(
    "CorrectnessResult", ["field", "recorded_value", "reference_value", "matches"]
)
ActionStatus = namedtuple("ActionStatus", ["action", "status", "reason", "token"])


def make_claim(source, field, value, text=""):
    """Build a claim. `text` is kept for the report only; it is never read."""
    return Claim(source, field, value, text)


def build_authority_map(declarations):
    """Turn (field, source) declarations into a map plus declaration issues.

    Returns (authority_map, issues) where issues maps field -> reason for
    fields whose declaration is ambiguous or conflicting. Such fields are not
    in authority_map, so every claim on them is held.
    """
    if declarations is None:
        return None, {}
    seen = {}
    issues = {}
    for field, source in declarations:
        if isinstance(source, (list, tuple, set, frozenset)):
            if len(source) != 1:
                issues[field] = REASON_AMBIGUOUS_DECLARATION
                continue
            source = next(iter(source))
        if not isinstance(source, str) or not source:
            issues[field] = REASON_AMBIGUOUS_DECLARATION
            continue
        if field in seen and seen[field] != source:
            issues[field] = REASON_CONFLICTING_DECLARATION
            continue
        seen[field] = source
    authority_map = {f: s for f, s in seen.items() if f not in issues}
    return authority_map, issues


class Resolution(object):
    """Outcome of resolve_fields. Holds data only; grants nothing."""

    def __init__(self, fields, records):
        self.fields = dict(fields)
        self.records = list(records)
        # Kept for inspection by tests: this sketch never emits action tokens.
        self.action_tokens = ()

    def records_for(self, field):
        return [r for r in self.records if r.field == field]

    def statuses_for(self, field):
        return [r.status for r in self.records_for(field)]

    def held_fields(self):
        return sorted({r.field for r in self.records if r.status == HOLD})

    def reject_set_fields(self):
        return sorted({r.field for r in self.records if r.status == REJECT_SET})

    def applied_fields(self):
        return sorted({r.field for r in self.records if r.status == APPLIED})

    def report(self):
        return [r._asdict() for r in self.records]


def resolve_fields(declarations, known_sources, claims, current=None):
    """Resolve claims against per-field source authority.

    declarations: iterable of (field, source) pairs, or None (missing map).
    known_sources: iterable of source ids recognised by the harness.
    claims: iterable of Claim.
    current: optional dict of existing field values (left unchanged unless
             an authorized-source value is applied).
    """
    fields = dict(current or {})
    known = set(known_sources or ())
    authority_map, issues = build_authority_map(declarations)
    records = []

    # Pass 1: classify each claim.
    candidates = {}  # field -> list of claims from the authorized source
    held = set()
    for claim in claims:
        field = claim.field
        if claim.source not in known:
            records.append(FieldRecord(field, HOLD, claim.source, claim.value,
                                       REASON_UNKNOWN_SOURCE, TRUTH_UNVERIFIED))
            held.add(field)
            continue
        if authority_map is None:
            records.append(FieldRecord(field, HOLD, claim.source, claim.value,
                                       REASON_MISSING_MAP, TRUTH_UNVERIFIED))
            held.add(field)
            continue
        if field in issues:
            records.append(FieldRecord(field, HOLD, claim.source, claim.value,
                                       issues[field], TRUTH_UNVERIFIED))
            held.add(field)
            continue
        if field not in authority_map:
            records.append(FieldRecord(field, HOLD, claim.source, claim.value,
                                       REASON_MISSING_DECLARATION, TRUTH_UNVERIFIED))
            held.add(field)
            continue
        if claim.source != authority_map[field]:
            records.append(FieldRecord(field, REJECT_SET, claim.source, claim.value,
                                       REASON_NOT_AUTHORIZED_SOURCE, TRUTH_UNVERIFIED))
            continue
        candidates.setdefault(field, []).append(claim)

    # Pass 2: authorized-source candidates; disagreement or any hold -> HOLD.
    for field in sorted(candidates):
        group = candidates[field]
        values = []
        for c in group:
            if c.value not in values:
                values.append(c.value)
        if len(values) > 1:
            for c in group:
                records.append(FieldRecord(field, HOLD, c.source, c.value,
                                           REASON_CONFLICT, TRUTH_UNVERIFIED))
            continue
        if field in held:
            for c in group:
                records.append(FieldRecord(field, HOLD, c.source, c.value,
                                           REASON_HELD_WITH_FIELD, TRUTH_UNVERIFIED))
            continue
        fields[field] = values[0]
        records.append(FieldRecord(field, APPLIED, group[0].source, values[0],
                                   REASON_AUTHORIZED_SOURCE, TRUTH_UNVERIFIED))
    return Resolution(fields, records)


def check_correctness(resolution, field, reference_value):
    """Separate correctness check against an out-of-band reference value.

    Authority decides who may set a field; it says nothing about whether the
    value is right. This check can fail on an APPLIED field.
    """
    recorded = resolution.fields.get(field)
    return CorrectnessResult(field, recorded, reference_value, recorded == reference_value)


def hold_consequential_action(resolution, action):
    """Report the status of a consequential action. Always HOLD, no token.

    The sketch has no send, payment, or merge path. Applied fields are data
    for a later, separate process; they are never turned into an action.
    """
    return ActionStatus(action, HOLD, REASON_NO_ACTION_PATH, None)
