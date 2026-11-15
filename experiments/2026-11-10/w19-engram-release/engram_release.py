"""w19-engram-release: hold a skill's records in retrieval until verified.

Clean-room Python 3 stdlib method sketch of the separation of training
admission from memory release in arXiv 2611.09472 (ENGRAM). Not a
reproduction: no training, no weights, no language model. Written from the
paper text only; the paper's linked code was unreachable and is not used.

A ``Store`` holds experience ``Record`` objects per skill, each in one of
three states:

* ``stored``   - in the store and retrievable;
* ``admitted`` - the skill passed the admission gate; still retrievable;
* ``released`` - moved to a non-retrievable archive after verification.

Two decisions per skill, kept apart:

* ``admit`` is the training-participation decision. It follows the paper's
  demonstration-aware rule: (mastery >= tau_m and records >= n_min and the
  skill not yet consolidated) or successful teacher records >= d_min.
  Admission never removes anything from retrieval.
* ``release`` removes records from retrieval only when every condition
  holds: the skill was admitted, it actually contributed training examples
  (participation), the reserved probe set is non-empty and does not overlap
  the stored records, the student *without* retrieval meets the relative
  criterion ``A_W - A_M >= delta`` against the base *with* retrieval, and
  the absolute criterion ``A_W > alpha`` (a strict floor). Only records that
  took part in training are archived; other records of the skill stay
  retrievable.

Any failed condition, and any missing, malformed or wrongly typed input
(non-numeric, NaN or infinite scores, a bool given as a number, a margin or
floor out of range, an empty or malformed probe set, an unknown skill, a
model that raises), is ``hold``: fail closed, nothing changes, every record
stays retrievable. There is no path that skips verification.

Numbers are compared exactly. Scores are ``Fraction`` values; every score,
margin, floor, mastery and mastery threshold is converted to a ``Fraction``
before any comparison: a plain ``int`` or ``Fraction`` as is, and a finite
plain ``float`` through the stricter of its shortest decimal form and its
simplest nearby fraction (see ``_exact``), so a floor written ``0.6`` is
exactly 3/5 and a score of 3/5 does not clear it. Anything else (bool, NaN,
infinity, str, None, Decimal, any subclass) holds. Floors that are not
short decimals are best passed as ``Fraction``.

The toy "student" induces a string rule from training examples and answers
probes from that induced rule alone; it is never handed retrieved records.
The toy "base" answers with retrieved records in context. Probes are
held-out inputs labelled by the true rule. Before scoring, the gate holds
any probe whose input or expected output matches any record input or output
of the skill after normalisation (Unicode compatibility form, accents and
case folded, a few look-alike letters mapped, whitespace, punctuation and
invisible characters dropped) or after also ignoring character order. So a
student that copies record text into a lookup table, even under a fuzzy key,
cannot answer them. Then a fixed set of lookup-only reference students,
built from the record text alone (exact lookup, normalised lookup, and
every segmentation of the probe input, raw or normalised, into whole record
inputs with their outputs concatenated), is run on the probes; if any of
them answers any probe, the gate holds. Only ``str`` answers can score.
"""

import math
import re
import unicodedata
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple

STORED = "stored"
ADMITTED = "admitted"
RELEASED = "released"
STATES = (STORED, ADMITTED, RELEASED)

RELEASE = "release"
HOLD = "hold"
OUTCOMES = (RELEASE, HOLD)

# Hold reasons.
UNKNOWN_SKILL = "unknown_skill"
NOT_ADMITTED = "not_admitted"
NO_PARTICIPATION = "no_training_participation"
EMPTY_PROBES = "empty_probes"
MALFORMED_PROBES = "malformed_probes"
PROBE_OVERLAP = "probe_overlaps_record"
PROBE_ANSWERABLE = "probe_answerable_from_records"
MODEL_ERROR = "model_error"
BAD_SCORE = "bad_score"
BAD_MARGIN = "bad_margin"
BAD_FLOOR = "bad_floor"
BAD_INPUT = "bad_input"
BELOW_RELATIVE = "below_relative"
BELOW_FLOOR = "below_floor"
NOTHING_TO_RELEASE = "nothing_to_release"
TRAINING_FAILED = "training_failed"
NOT_ELIGIBLE = "admission_criteria_not_met"


# --------------------------------------------------------------------------
# Toy rule domain.

def _reverse(s):
    return s[::-1]


def _upper(s):
    return s.upper()


def _sort(s):
    return "".join(sorted(s))


def _double(s):
    return s + s


def _capitalize(s):
    return s[:1].upper() + s[1:]


# The hypotheses a model can induce, in a fixed order (first consistent
# hypothesis wins). ``capitalize`` is deliberately missing: a skill with that
# true rule cannot be learned by induction from this library.
HYPOTHESES: Tuple[Tuple[str, Callable[[str], str]], ...] = (
    ("reverse", _reverse),
    ("upper", _upper),
    ("sort", _sort),
    ("double", _double),
)

TRUE_RULES: Dict[str, Callable[[str], str]] = {
    "reverse": _reverse,
    "upper": _upper,
    "sort": _sort,
    "double": _double,
    "capitalize": _capitalize,
}


def induce(examples):
    """Return the name of the first library hypothesis consistent with every
    example, or None when there is no example or no consistent hypothesis."""
    examples = tuple(examples)
    if not examples:
        return None
    for name, fn in HYPOTHESES:
        if all(fn(x) == y for x, y in examples):
            return name
    return None


def make_probes(rule, inputs):
    """Reserved probes: held-out inputs labelled by the true rule."""
    fn = TRUE_RULES[rule]
    return tuple((x, fn(x)) for x in inputs)


# --------------------------------------------------------------------------
# Records and store.

@dataclass(frozen=True)
class Record:
    record_id: str
    skill: str
    examples: Tuple[Tuple[str, str], ...]
    success: bool = True
    source: str = "teacher"
    state: str = STORED

    @property
    def text(self):
        body = "; ".join("%s -> %s" % (x, y) for x, y in self.examples)
        return "%s: %s" % (self.skill, body)


@dataclass(frozen=True)
class Decision:
    outcome: str
    skill: object
    reasons: Tuple[str, ...]
    student_score: Optional[Fraction] = None
    base_score: Optional[Fraction] = None
    released_ids: Tuple[str, ...] = ()


def _hold(skill, *reasons, a_w=None, a_m=None):
    return Decision(HOLD, skill, tuple(reasons), a_w, a_m, ())


def _is_real(v):
    """A finite real number that is not a bool."""
    return _exact(v) is not None


HIGH = "high"
LOW = "low"


def _exact(v, side=HIGH):
    """Exact ``Fraction`` for a plain int, Fraction or finite float; else None.

    Only the exact types ``int``, ``Fraction`` and ``float`` are numbers
    here; bools, subclasses (a numpy-like float, a float with its own
    ``__repr__``), Decimal, str and everything else give None, and the
    caller holds. This never raises.

    A float may stand for more than one exact value. Two readings are
    taken: its shortest decimal form (``float.__repr__``, so ``0.6`` is
    exactly 3/5) and, when one exists, the simplest fraction with a
    denominator up to a million that rounds to the same float (so ``1/3``
    is exactly 1/3). ``side`` picks the stricter reading: ``HIGH`` for a
    floor, margin, mastery threshold or base score, ``LOW`` for a student
    score or a mastery estimate. Pass a ``Fraction`` to avoid any reading.
    """
    try:
        t = type(v)
        if t is Fraction:
            return v
        if t is int:
            return Fraction(v)
        if t is not float or not math.isfinite(v):
            return None
        readings = [Fraction(float.__repr__(v))]
        snapped = Fraction(v).limit_denominator(10 ** 6)
        if float(snapped) == v:
            readings.append(snapped)
        return max(readings) if side == HIGH else min(readings)
    except Exception:
        return None


def _is_count(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


class Store:
    """Experience store. ``retrieve`` returns stored and admitted records;
    released records sit in a non-retrievable archive (not deleted)."""

    def __init__(self):
        self._records: Dict[str, Record] = {}
        self._order: List[str] = []
        self._admitted: set = set()
        self._consolidated: set = set()
        # skill -> frozenset of record ids that supplied training examples
        self._participation: Dict[str, FrozenSet[str]] = {}

    # -- writes that never remove anything from retrieval -----------------

    def add(self, record):
        if not isinstance(record, Record):
            raise TypeError("record must be a Record")
        if record.record_id in self._records:
            raise ValueError("duplicate record id %r" % record.record_id)
        if not isinstance(record.skill, str) or not record.skill:
            raise ValueError("record skill must be a non-empty string")
        state = ADMITTED if record.skill in self._admitted else STORED
        self._records[record.record_id] = replace(record, state=state)
        self._order.append(record.record_id)

    def skills(self):
        return frozenset(r.skill for r in self._records.values())

    def records(self, skill=None):
        """Every record, archived ones included (for reports)."""
        out = [self._records[i] for i in self._order]
        return tuple(r for r in out if skill is None or r.skill == skill)

    def retrieve(self, skill):
        """Records a model with retrieval may read: never released ones."""
        return tuple(r for r in self.records(skill) if r.state != RELEASED)

    def admit(self, skill, mastery, tau_m, n_min, d_min):
        """Admission gate (training participation decision only).

        u = (mastery >= tau_m and n >= n_min and not consolidated)
            or d >= d_min
        where n counts the skill's records and d its successful teacher
        records (failed records never count as demonstrations). Malformed
        inputs hold. The paper also lets a consolidated skill qualify again
        once its mastery has risen by a configured amount; that branch is
        left out on purpose, so a consolidated skill re-enters only through
        the demonstration branch (stricter). Admission moves stored records to
        ``admitted``; they stay retrievable.
        """
        if not isinstance(skill, str) or skill not in self.skills():
            return _hold(skill, UNKNOWN_SKILL)
        mastery, tau_m = _exact(mastery, LOW), _exact(tau_m, HIGH)
        if not (mastery is not None and 0 <= mastery <= 1
                and tau_m is not None and 0 <= tau_m <= 1
                and _is_count(n_min) and _is_count(d_min) and d_min > 0):
            return _hold(skill, BAD_INPUT)
        recs = [r for r in self.records(skill) if r.state != RELEASED]
        n = len(recs)
        d = sum(1 for r in recs if r.success is True and r.source == "teacher")
        eligible = skill not in self._consolidated
        u = (mastery >= tau_m and n >= n_min and eligible) or d >= d_min
        if not u:
            return _hold(skill, NOT_ELIGIBLE)
        self._admitted.add(skill)
        for r in recs:
            if r.state == STORED:
                self._records[r.record_id] = replace(r, state=ADMITTED)
        return Decision("admitted", skill, ())

    def is_admitted(self, skill):
        return skill in self._admitted

    def participation(self, skill):
        return self._participation.get(skill, frozenset())

    def train(self, student, skill):
        """Build the valid training examples D_s for an admitted skill (its
        admitted, successful records) and hand them to the student. b_s is
        recorded only when D_s is non-empty and fitting succeeded; a training
        failure leaves records and participation unchanged."""
        if not isinstance(skill, str) or skill not in self.skills():
            return _hold(skill, UNKNOWN_SKILL)
        if skill not in self._admitted:
            return _hold(skill, NOT_ADMITTED)
        used = [r for r in self.records(skill)
                if r.state == ADMITTED and r.success is True and r.examples]
        examples = tuple(e for r in used for e in r.examples)
        if not examples:
            return _hold(skill, NO_PARTICIPATION)
        try:
            student.fit(skill, examples)
        except Exception:
            return _hold(skill, TRAINING_FAILED)
        self._participation[skill] = (self._participation.get(skill, frozenset())
                                      | frozenset(r.record_id for r in used))
        self._consolidated.add(skill)
        return Decision("trained", skill, ())

    def _archive(self, ids):
        for i in ids:
            self._records[i] = replace(self._records[i], state=RELEASED)


# --------------------------------------------------------------------------
# Toy models.

class Student:
    """Learns a rule from training examples; answers from that rule alone.
    ``answer`` takes no retrieval context."""

    def __init__(self):
        self.learned: Dict[str, Optional[str]] = {}

    def fit(self, skill, examples):
        self.learned[skill] = induce(examples)

    def answer(self, skill, x):
        name = self.learned.get(skill)
        if name is None:
            return None
        return dict(HYPOTHESES)[name](x)


class MemorisingStudent:
    """Copies training record text into a lookup table (input -> output).
    Answers only inputs it has seen verbatim."""

    def __init__(self):
        self.table: Dict[Tuple[str, str], str] = {}

    def fit(self, skill, examples):
        for x, y in examples:
            self.table[(skill, x)] = y

    def answer(self, skill, x):
        return self.table.get((skill, x))


class RetrievalBase:
    """Base model with retrieval: induces from the retrieved records in
    context (successful ones), and copies an exact match if one is there."""

    def answer(self, skill, x, context):
        examples = [e for r in context if r.success is True for e in r.examples]
        for ex, ey in examples:
            if ex == x:
                return ey
        name = induce(examples)
        if name is None:
            return None
        return dict(HYPOTHESES)[name](x)


# --------------------------------------------------------------------------
# Check layer: detect / compare / verify / release / report.

def validate_probes(probes):
    """Probes must be a non-empty sequence of (str, str) pairs whose input
    and label are exactly ``str`` (a subclass could redefine equality)."""
    if not isinstance(probes, (tuple, list)):
        return MALFORMED_PROBES
    if len(probes) == 0:
        return EMPTY_PROBES
    for p in probes:
        if not (isinstance(p, tuple) and len(p) == 2
                and type(p[0]) is str and type(p[1]) is str):
            return MALFORMED_PROBES
    return None


# Look-alike letters folded to Latin before comparison (Cyrillic, Greek).
_LOOKALIKE = str.maketrans({
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0441": "c",
    "\u0440": "p", "\u0445": "x", "\u0443": "y", "\u0456": "i",
    "\u0455": "s", "\u0458": "j", "\u03bf": "o", "\u03b1": "a",
})
_NON_WORD = re.compile(r"[\W_]+")


def normalise(s):
    """Comparison key: compatibility form, accents dropped, case folded,
    look-alike letters mapped, and everything that is not a letter or digit
    (whitespace, punctuation, invisible characters) removed."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = unicodedata.normalize("NFKC", s).casefold().translate(_LOOKALIKE)
    return _NON_WORD.sub("", s)


def _keys(s):
    n = normalise(s)
    return {n, "".join(sorted(n))}


def detect_probe_overlap(store, skill, probes):
    """Probe inputs whose input or expected output matches any record input
    or output of the skill, in any state, after normalisation or with
    character order ignored. Such a probe can be answered by copying record
    text, so it is not evidence of mastery."""
    seen = set()
    for r in store.records(skill):
        for x, y in r.examples:
            seen |= _keys(x) | _keys(y)
    return tuple(x for x, y in probes if (_keys(x) | _keys(y)) & seen)


# --------------------------------------------------------------------------
# Reference adversaries: lookup-only students built from record text alone.

# Upper bound on distinct candidate answers kept per position while
# segmenting; past it the pre-check cannot rule a probe out and holds.
SEGMENT_CAP = 256


def _record_pairs(store, skill):
    return [(x, y) for r in store.records(skill) for x, y in r.examples
            if type(x) is str and type(y) is str]


def _exact_lookup(pairs):
    table = {}
    for x, y in pairs:
        table.setdefault(x, set()).add(y)
    return lambda q: table.get(q, set())


def _normalised_lookup(pairs):
    table = {}
    for x, y in pairs:
        for k in _keys(x):
            table.setdefault(k, set()).add(y)
    return lambda q: set().union(*(table.get(k, set()) for k in _keys(q)))


def _segmentation(pairs, key):
    """Every way to split key(probe input) into whole key(record input)
    pieces, answering with the concatenated record outputs. Returns None
    when the number of candidates passes SEGMENT_CAP (cannot rule out)."""
    table = {}
    for x, y in pairs:
        k = key(x)
        if k:
            table.setdefault(k, set()).add(y)
    lengths = sorted({len(k) for k in table})

    def answer(q):
        q = key(q)
        if not q:
            return set()
        outs = [set() for _ in range(len(q) + 1)]
        outs[0].add("")
        for i in range(len(q)):
            if not outs[i]:
                continue
            for n in lengths:
                piece = q[i:i + n]
                if len(piece) == n and piece in table:
                    for head in outs[i]:
                        for y in table[piece]:
                            outs[i + n].add(head + y)
                    if len(outs[i + n]) > SEGMENT_CAP:
                        return None
        return outs[len(q)]
    return answer


def reference_adversaries(store, skill):
    """The fixed set of lookup-only reference students for a skill. Each
    maps a probe input to the set of answers it could give from record text
    alone (None: too many to rule out)."""
    pairs = _record_pairs(store, skill)
    return (
        ("exact_lookup", _exact_lookup(pairs)),
        ("normalised_lookup", _normalised_lookup(pairs)),
        ("segmentation", _segmentation(pairs, lambda s: s)),
        ("normalised_segmentation", _segmentation(pairs, normalise)),
    )


def detect_answerable_from_records(store, skill, probes):
    """(adversary, probe input) for every probe some reference adversary
    answers correctly, its answer compared both exactly and normalised. A
    probe whose candidates could not be bounded counts as answered."""
    hits = []
    for name, adversary in reference_adversaries(store, skill):
        for x, y in probes:
            answers = adversary(x)
            if answers is None or any(a == y or normalise(a) == normalise(y)
                                      for a in answers):
                hits.append((name, x))
    return tuple(hits)


def score(answer_fn, probes):
    """Fraction of probes answered with exactly the expected ``str``; an
    answer of any other type is wrong, whatever its ``__eq__`` says."""
    correct = 0
    for x, y in probes:
        a = answer_fn(x)
        if type(a) is str and a == y:
            correct += 1
    return Fraction(correct, len(probes))


def compare(a_w, a_m, delta):
    """Relative criterion: A_W - A_M >= delta."""
    return a_w - a_m >= delta


def verify(a_w, a_m, delta, alpha):
    """Score check only. Returns a tuple of hold reasons (empty when both
    criteria are met). Scores must be finite reals in [0, 1], delta a finite
    real in [-1, 1], alpha a finite real in [0, 1); bools are not numbers.
    All four are converted with ``_exact`` first. There is no default floor:
    the caller states it."""
    reasons = []
    a_w, a_m = _exact(a_w, LOW), _exact(a_m, HIGH)
    delta, alpha = _exact(delta, HIGH), _exact(alpha, HIGH)
    if not (a_w is not None and a_m is not None
            and 0 <= a_w <= 1 and 0 <= a_m <= 1):
        reasons.append(BAD_SCORE)
    if not (delta is not None and -1 <= delta <= 1):
        reasons.append(BAD_MARGIN)
    if not (alpha is not None and 0 <= alpha < 1):
        reasons.append(BAD_FLOOR)
    if reasons:
        return tuple(reasons)
    if not compare(a_w, a_m, delta):
        reasons.append(BELOW_RELATIVE)
    if not a_w > alpha:
        reasons.append(BELOW_FLOOR)
    return tuple(reasons)


def release(store, skill, student, base, probes, *, alpha, delta=0.0):
    """Release gate z_s = u_s * b_s * [N_s > 0] * [A_W - A_M >= delta] *
    [A_W > alpha]. Archives only records that took part in training; any
    failure holds and changes nothing."""
    try:
        return _release(store, skill, student, base, probes, delta, alpha)
    except Exception:
        return _hold(skill, MODEL_ERROR)


def _release(store, skill, student, base, probes, delta, alpha):
    if not isinstance(skill, str) or skill not in store.skills():
        return _hold(skill, UNKNOWN_SKILL)
    gate = []
    if not store.is_admitted(skill):
        gate.append(NOT_ADMITTED)
    part = store.participation(skill)
    if not part:
        gate.append(NO_PARTICIPATION)
    bad = validate_probes(probes)
    if bad:
        gate.append(bad)
    if gate:
        return _hold(skill, *gate)
    if detect_probe_overlap(store, skill, probes):
        return _hold(skill, PROBE_OVERLAP)
    # Reference-adversary pre-check: if a lookup-only student built from
    # the record text answers any probe at all, the probe set is no
    # evidence of mastery.
    if detect_answerable_from_records(store, skill, probes):
        return _hold(skill, PROBE_ANSWERABLE)
    eligible = tuple(r.record_id for r in store.retrieve(skill)
                     if r.record_id in part)
    if not eligible:
        return _hold(skill, NOTHING_TO_RELEASE)
    # Student WITHOUT retrieval; base WITH retrieval from the pre-release store.
    context = store.retrieve(skill)
    try:
        a_w = score(lambda x: student.answer(skill, x), probes)
        a_m = score(lambda x: base.answer(skill, x, context), probes)
    except Exception:
        return _hold(skill, MODEL_ERROR)
    reasons = verify(a_w, a_m, delta, alpha)
    if reasons:
        return _hold(skill, *reasons, a_w=a_w, a_m=a_m)
    store._archive(eligible)
    return Decision(RELEASE, skill, (), a_w, a_m, eligible)


def report(store):
    """Per-skill counts by state, plus admission and participation."""
    out = {}
    for skill in sorted(store.skills()):
        recs = store.records(skill)
        out[skill] = {
            "stored": sum(1 for r in recs if r.state == STORED),
            "admitted": sum(1 for r in recs if r.state == ADMITTED),
            "released": sum(1 for r in recs if r.state == RELEASED),
            "retrievable": len(store.retrieve(skill)),
            "is_admitted": store.is_admitted(skill),
            "participating": len(store.participation(skill)),
        }
    return out
