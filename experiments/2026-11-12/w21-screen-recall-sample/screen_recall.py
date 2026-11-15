"""What screening evidence can establish: a deterministic, stdlib-only sketch.

Screeners pass or reject items; only items forwarded to the assessor get
judged. report(request) says what the judged evidence supports:

    precision           measured from assessor judgments of every forwarded
                        item
    recall_lower_bound  found / (found + not_passed_count): what acceptance
                        alone supports, reported as a lower bound, never as
                        recall
    recall              an estimate, and only when a seeded random sample of
                        NOT-forwarded items was judged:
                            missed_estimate = relevant_in_sample / sample_size
                                              * not_passed_count
                            recall_estimate = found / (found + missed_estimate)
                        otherwise on_unmeasured

Screener reports are validated and counted, and nothing else. How many
screeners passed the same list never changes precision, the lower bound or
the recall estimate, and never unlocks recall. This module does not combine
screener outputs into any decision or score.

No interval or accuracy claim is attached to the estimate; it is a point
estimate over the judged sample.

A judgment may be "pending". Any pending judgment needs a declared deadline
{timeout_s, on_expiry, expired}; on_expiry is hold, escalate or deny; a
missing declaration is a config_error. An expired deadline reports the
declared on_expiry and no figure at all.

Inputs are checked by exact type. report() catches any Exception raised
while validating or computing and returns a config_error record with no
figures. It can still raise: called with the interpreter stack nearly
exhausted, report() raises RecursionError, because the config_error
fallback needs stack too. That fails closed: no record and no figure.
"""

import random
from fractions import Fraction

REPORTED = "reported"
PENDING = "pending"
EXPIRED = "expired"
CONFIG_ERROR = "config_error"
STATUSES = (REPORTED, PENDING, EXPIRED, CONFIG_ERROR)

MEASURED = "measured"
ESTIMATE = "estimate"
LOWER_BOUND = "lower_bound"
ON_UNMEASURED = "on_unmeasured"

# Reasons a figure is on_unmeasured.
NOTHING_PASSED = "nothing_passed"
PASSES_NOT_FULLY_ASSESSED = "passes_not_fully_assessed"
ASSESSMENT_PENDING = "assessment_pending"
NO_NOT_PASSED_SAMPLE = "no_not_passed_sample"
SAMPLE_EMPTY = "sample_empty"
SAMPLE_NOT_SEEDED_DRAW = "sample_not_seeded_draw"
NO_RELEVANT_OBSERVED = "no_relevant_observed"
NOTHING_NOT_PASSED = "nothing_not_passed"

RELEVANT = "relevant"
NOT_RELEVANT = "not_relevant"
JUDGMENT_PENDING = "pending"
LABELS = (RELEVANT, NOT_RELEVANT, JUDGMENT_PENDING)

HOLD = "hold"
ESCALATE = "escalate"
DENY = "deny"
ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY)

REQUEST_FIELDS = ("items", "forwarded", "screener_reports", "assessed_passes")
OPTIONAL_FIELDS = ("not_passed_sample", "deadline")
REPORT_FIELDS = ("screener", "passed")
SAMPLE_FIELDS = ("seed", "size", "items", "judgments")
DEADLINE_FIELDS = ("timeout_s", "on_expiry", "expired")

RECORD_FIELDS = ("status", "on_expiry", "screener_count", "precision",
                 "recall_lower_bound", "recall")


def _is_str(v):
    return type(v) is str and len(v) > 0


def _is_dict(v):
    return type(v) is dict


def _is_list(v):
    return type(v) is list


def _is_int(v):
    return type(v) is int


def _canonical(value, choices):
    if type(value) is not str:
        return None
    for choice in choices:
        if value == choice:
            return choice
    return None


def _id_list(value, universe=None):
    """Exact list of unique exact-str ids (optionally inside universe)."""
    if not _is_list(value):
        return None
    seen = set()
    for v in value:
        if not _is_str(v) or v in seen:
            return None
        if universe is not None and v not in universe:
            return None
        seen.add(v)
    return value


def _judgments(value, keys):
    """Exact dict whose keys are exactly `keys` and values are labels."""
    if not _is_dict(value):
        return None
    for k in value:
        if not _is_str(k) or k not in keys:
            return None
        if _canonical(value[k], LABELS) is None:
            return None
    if len(value) != len(keys):
        return None
    return value


def draw_sample(not_passed, size, seed):
    """The seeded draw a declared sample must equal: sorted ids, then
    random.Random(seed).sample(...)."""
    return random.Random(seed).sample(sorted(not_passed), size)


def validate(request):
    """None when well formed, else a short error string."""
    if not _is_dict(request):
        return "request is not a mapping"
    for key in request:
        if _canonical(key, REQUEST_FIELDS + OPTIONAL_FIELDS) is None:
            return "unknown field"
    for key in REQUEST_FIELDS:
        if key not in request:
            return "missing field: %s" % (key,)
    items = _id_list(request["items"])
    if items is None:
        return "items must be a list of unique ids"
    universe = set(items)
    forwarded = _id_list(request["forwarded"], universe)
    if forwarded is None:
        return "forwarded must be unique ids drawn from items"
    reports = request["screener_reports"]
    if not _is_list(reports):
        return "screener_reports must be a list"
    names = set()
    for rep in reports:
        if not _is_dict(rep):
            return "screener report is not a mapping"
        for key in rep:
            if _canonical(key, REPORT_FIELDS) is None:
                return "unknown screener report field"
        if len(rep) != len(REPORT_FIELDS):
            return "screener report needs screener and passed"
        if not _is_str(rep["screener"]) or rep["screener"] in names:
            return "screener ids must be unique strings"
        names.add(rep["screener"])
        if _id_list(rep["passed"], universe) is None:
            return "screener passed list must be unique ids from items"
    assessed = request["assessed_passes"]
    if not _is_dict(assessed):
        return "assessed_passes must be a mapping"
    fwd = set(forwarded)
    for k in assessed:
        if not _is_str(k) or k not in fwd:
            return "assessed_passes may judge forwarded items only"
        if _canonical(assessed[k], LABELS) is None:
            return "unknown label"
    if "not_passed_sample" in request:
        sample = request["not_passed_sample"]
        if not _is_dict(sample):
            return "not_passed_sample must be a mapping"
        for key in sample:
            if _canonical(key, SAMPLE_FIELDS) is None:
                return "unknown sample field"
        for key in SAMPLE_FIELDS:
            if key not in sample:
                return "missing sample field: %s" % (key,)
        if not _is_int(sample["seed"]):
            return "sample seed must be an int"
        size = sample["size"]
        not_passed = universe - fwd
        if not _is_int(size) or size < 0 or size > len(not_passed):
            return "sample size must be an int in 0..not_passed_count"
        s_items = _id_list(sample["items"], not_passed)
        if s_items is None or len(s_items) != size:
            return "sample items must be size unique not-passed ids"
        if _judgments(sample["judgments"], set(s_items)) is None:
            return "every sampled item needs exactly one label"
    pending = any(_canonical(v, LABELS) == JUDGMENT_PENDING
                  for v in assessed.values())
    if "not_passed_sample" in request:
        pending = pending or any(
            _canonical(v, LABELS) == JUDGMENT_PENDING
            for v in request["not_passed_sample"]["judgments"].values())
    if "deadline" in request:
        dl = request["deadline"]
        if not _is_dict(dl):
            return "deadline must be a mapping"
        for key in dl:
            if _canonical(key, DEADLINE_FIELDS) is None:
                return "unknown deadline field"
        timeout = dl.get("timeout_s")
        if not _is_int(timeout) or timeout <= 0:
            return "deadline.timeout_s must be a positive int"
        if "on_expiry" not in dl:
            return "deadline declares a timeout without on_expiry"
        if _canonical(dl["on_expiry"], ON_EXPIRY_VALUES) is None:
            return "deadline.on_expiry must be hold, escalate or deny"
        if "expired" in dl and type(dl["expired"]) is not bool:
            return "deadline.expired must be a bool"
    elif pending:
        return "a pending judgment needs a declared deadline"
    return None


def _fig(status, value=None, reason=None, **extra):
    out = {"status": status, "value": None, "exact": None, "reason": reason}
    if value is not None:
        out["value"] = float(value)
        out["exact"] = "%d/%d" % (value.numerator, value.denominator)
    out.update(extra)
    return out


def _unmeasured(reason, **extra):
    return _fig(ON_UNMEASURED, None, reason, **extra)


def _record(status, on_expiry=None, screener_count=None, precision=None,
            lower=None, recall=None):
    return {"status": status, "on_expiry": on_expiry,
            "screener_count": screener_count,
            "precision": precision if precision is not None else _unmeasured(status),
            "recall_lower_bound": lower if lower is not None else _unmeasured(status),
            "recall": recall if recall is not None else _unmeasured(status)}


def _report(request):
    error = validate(request)
    if error is not None:
        return _record(CONFIG_ERROR)
    n_screeners = len(request["screener_reports"])
    on_expiry = None
    if "deadline" in request:
        dl = request["deadline"]
        on_expiry = _canonical(dl["on_expiry"], ON_EXPIRY_VALUES)
        if dl.get("expired", False) is True:
            return _record(EXPIRED, on_expiry, n_screeners)
    items = request["items"]
    forwarded = request["forwarded"]
    assessed = request["assessed_passes"]
    not_passed_count = len(items) - len(forwarded)
    labels = [_canonical(assessed.get(i), LABELS) for i in forwarded]
    status = REPORTED

    # Precision and the acceptance-only lower bound need every forwarded
    # item judged.
    if len(forwarded) == 0:
        precision = _unmeasured(NOTHING_PASSED)
    elif None in labels:
        precision = _unmeasured(PASSES_NOT_FULLY_ASSESSED)
    elif JUDGMENT_PENDING in labels:
        precision = _unmeasured(ASSESSMENT_PENDING)
        status = PENDING
    else:
        found = labels.count(RELEVANT)
        precision = _fig(MEASURED, Fraction(found, len(forwarded)),
                         judged=len(forwarded), relevant=found)
    passes_ok = None not in labels and JUDGMENT_PENDING not in labels
    found = labels.count(RELEVANT) if passes_ok else None

    if not passes_ok:
        reason = ASSESSMENT_PENDING if JUDGMENT_PENDING in labels else PASSES_NOT_FULLY_ASSESSED
        lower = _unmeasured(reason)
    elif found + not_passed_count == 0:
        lower = _unmeasured(NO_RELEVANT_OBSERVED)
    else:
        lower = _fig(LOWER_BOUND, Fraction(found, found + not_passed_count),
                     found=found, not_passed=not_passed_count)

    sample = request.get("not_passed_sample")
    if not passes_ok:
        recall = _unmeasured(lower["reason"])
    elif not_passed_count == 0:
        # Nothing was left out; the passes are every item.
        recall = _unmeasured(NOTHING_NOT_PASSED)
    elif sample is None:
        recall = _unmeasured(NO_NOT_PASSED_SAMPLE)
    elif sample["size"] == 0:
        recall = _unmeasured(SAMPLE_EMPTY)
    else:
        not_passed = [i for i in items if i not in set(forwarded)]
        drawn = draw_sample(not_passed, sample["size"], sample["seed"])
        s_labels = [_canonical(sample["judgments"][i], LABELS)
                    for i in sample["items"]]
        if list(sample["items"]) != drawn:
            recall = _unmeasured(SAMPLE_NOT_SEEDED_DRAW)
        elif JUDGMENT_PENDING in s_labels:
            recall = _unmeasured(ASSESSMENT_PENDING)
            status = PENDING
        else:
            hits = s_labels.count(RELEVANT)
            missed = Fraction(hits * not_passed_count, sample["size"])
            if found + missed == 0:
                recall = _unmeasured(NO_RELEVANT_OBSERVED)
            else:
                recall = _fig(ESTIMATE, Fraction(found) / (found + missed),
                              sample_size=sample["size"],
                              relevant_in_sample=hits,
                              not_passed=not_passed_count,
                              missed_estimate=float(missed),
                              interval=None)
    return _record(status, on_expiry, n_screeners, precision, lower, recall)


def report(request):
    """Return a report record; bad input or an Exception inside ->
    config_error. Can raise RecursionError when the stack is nearly
    exhausted on entry (no record, no figure)."""
    try:
        return _report(request)
    except Exception:
        return _record(CONFIG_ERROR)
