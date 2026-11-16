"""Owned, typed, gated, withdrawable exceptions to a frozen shared rule.

Soft method sketch (not a reproduction) of arXiv 2611.15917. A published
rule decides every item of a small finite domain. Each party owns one
subject (one block of the domain) and may hold one live exception: a typed
declaration (subject, scope, form, size) that tightens the rule on part of
its own block. A party proposes one only when its own records pass a
deterministic, selection-aware evidence gate. The acceptance body checks
types and ownership, re-runs the gate on the submitted records, re-derives
the patch from the declaration (nothing else is taken from the party) and
adds it to a unit reserved for that owner. Withdrawal subtracts the same
patch, so the parameters return bit for bit.

Two equivalent decision forms are kept side by side: the "compiled" form
(integer ReLU units: two frozen base units plus one reserved unit per
owner) and a plain table of owned exception rows run beside the rule.

Python 3 standard library only. No network, no clock, no files written.
"""

import collections
import hashlib
import json
import operator
from fractions import Fraction
from math import comb

# ---------------------------------------------------------------- domain

SUBJECTS = ("s0", "s1", "s2", "s3")
CLASSES = ("a", "b", "c")
Q_VALUES = tuple(range(8))
ITEM_KEYS = ("subject", "cls", "q1", "q2")

# Each owner holds exactly one subject and one reserved unit.
OWNERS = (("p0", "s0"), ("p1", "s1"), ("p2", "s2"), ("p3", "s3"))
OWNER_NAMES = tuple(o for o, _ in OWNERS)

# The frozen published rule: accept (1) iff q1 <= 5 and q2 <= 5.
BASE_RULE = (("q1_max", 5), ("q2_max", 5))

# The typed declaration space. Every form tightens the rule (reject more).
SCOPES = ("all", "a", "b", "c")
FORMS = (
    ("q1_margin", (1, 2, 3)),  # reject in scope when q1 > q1_max - size
    ("q2_margin", (1, 2, 3)),  # reject in scope when q2 > q2_max - size
    ("sum_cap", (4, 5, 6, 7, 8, 9)),  # reject in scope when q1 + q2 > size
)
DECL_KEYS = ("subject", "scope", "form", "size")
SUBMISSION_KEYS = ("owner", "declaration")
GATE_KEYS = ("claimed", "evidence")
RECORD_KEYS = ("item", "label")
CLAIM_KEYS = ("a", "b")

# Evidence gate: improvement T = a - b must reach max(GATE_MIN, c(n)),
# where c(n) is the least c >= 1 with |H| * P[Bin(n, eta) >= c] <= alpha
# (a union bound over the typed space, so the gate accounts for the search).
GATE_MIN = 5
GATE_ETA = Fraction(1, 20)
GATE_ALPHA = Fraction(1, 20)

GATING = 100  # gating weight in reserved units; larger than any score

ADMIT = "ADMIT"
WITHDRAWN = "WITHDRAWN"
REFUSE = "REFUSE"
CONFIG_ERROR = "config_error"


class ConfigError(ValueError):
    """Raised for malformed or mistyped input; reported as config_error."""


def _q1_max():
    return dict(BASE_RULE)["q1_max"]


def _q2_max():
    return dict(BASE_RULE)["q2_max"]


ITEMS = tuple((s, c, q1, q2) for s in SUBJECTS for c in CLASSES
              for q1 in Q_VALUES for q2 in Q_VALUES)


def owned_subject(owner):
    for o, s in OWNERS:
        if o == owner:
            return s
    return None


def subject_owner(subject):
    for o, s in OWNERS:
        if s == subject:
            return o
    return None


# ------------------------------------------------------------ validation

def _exact_keys(obj, keys, what):
    """obj must be a plain dict whose keys are exact str and exactly keys."""
    if type(obj) is not dict:
        raise ConfigError(what + "_not_dict")
    for k in obj:
        if type(k) is not str:
            raise ConfigError(what + "_key_not_str")
    if set(obj) != set(keys):
        raise ConfigError(what + "_keys")


def _exact_str(value, choices, what):
    if type(value) is not str:
        raise ConfigError(what + "_not_str")
    if value not in choices:
        raise ConfigError(what + "_unknown")
    return value


def _exact_int(value, lo, hi, what):
    # bool, float (incl. NaN and inf) and int subclasses are all refused.
    if type(value) is not int:
        raise ConfigError(what + "_not_int")
    if value < lo or value > hi:
        raise ConfigError(what + "_range")
    return value


def validate_item(obj):
    _exact_keys(obj, ITEM_KEYS, "item")
    s = _exact_str(obj["subject"], SUBJECTS, "subject")
    c = _exact_str(obj["cls"], CLASSES, "cls")
    q1 = _exact_int(obj["q1"], Q_VALUES[0], Q_VALUES[-1], "q1")
    q2 = _exact_int(obj["q2"], Q_VALUES[0], Q_VALUES[-1], "q2")
    return (s, c, q1, q2)


def validate_records(obj):
    if type(obj) is not list:
        raise ConfigError("evidence_not_list")
    out = []
    for rec in obj:
        _exact_keys(rec, RECORD_KEYS, "record")
        item = validate_item(rec["item"])
        label = _exact_int(rec["label"], 0, 1, "label")
        out.append((item, label))
    return tuple(out)


def validate_declaration(obj):
    _exact_keys(obj, DECL_KEYS, "declaration")
    s = _exact_str(obj["subject"], SUBJECTS, "subject")
    sc = _exact_str(obj["scope"], SCOPES, "scope")
    f = _exact_str(obj["form"], tuple(n for n, _ in FORMS), "form")
    sizes = dict(FORMS)[f]
    if type(obj["size"]) is not int:
        raise ConfigError("size_not_int")
    if obj["size"] not in sizes:
        raise ConfigError("size_range")
    return (s, sc, f, obj["size"])


def validate_owner(value):
    if type(value) is not str:
        raise ConfigError("owner_not_str")
    return value


def validate_claimed(obj):
    _exact_keys(obj, CLAIM_KEYS, "claimed")
    a = _exact_int(obj["a"], 0, 10 ** 9, "claimed_a")
    b = _exact_int(obj["b"], 0, 10 ** 9, "claimed_b")
    return (a, b)


def validate_submission(obj):
    """Return a validated snapshot (owner, decl, claimed, evidence).

    claimed and evidence are None when the gate keys are absent (ungated).
    """
    if type(obj) is not dict:
        raise ConfigError("submission_not_dict")
    for k in obj:
        if type(k) is not str:
            raise ConfigError("submission_key_not_str")
    keys = set(obj)
    need = set(SUBMISSION_KEYS)
    if not need <= keys or not keys <= need | set(GATE_KEYS):
        raise ConfigError("submission_keys")
    owner = validate_owner(obj["owner"])
    decl = validate_declaration(obj["declaration"])
    claimed = None
    evidence = None
    if "claimed" in obj:
        claimed = validate_claimed(obj["claimed"])
    if "evidence" in obj:
        evidence = validate_records(obj["evidence"])
    return (owner, decl, claimed, evidence)


# ------------------------------------------------------------- semantics

def base_accepts(item):
    return 1 if (item[2] <= _q1_max() and item[3] <= _q2_max()) else 0


def fires(decl, item):
    """True when the declaration's condition holds for item (rule ignored)."""
    subject, scope, form, size = decl
    if item[0] != subject:
        return False
    if scope != "all" and item[1] != scope:
        return False
    if form == "q1_margin":
        return item[2] > _q1_max() - size
    if form == "q2_margin":
        return item[3] > _q2_max() - size
    if form == "sum_cap":
        return item[2] + item[3] > size
    raise ConfigError("form_unknown")


def region(decl):
    """Items whose decision the declaration changes (accept -> reject)."""
    key = tuple(decl)
    if key not in _REGIONS:
        _REGIONS[key] = frozenset(i for i, x in enumerate(ITEMS)
                                  if base_accepts(x) and fires(decl, x))
    return _REGIONS[key]


_REGIONS = {}


def typed_space(subject):
    return tuple((subject, sc, f, size) for sc in SCOPES
                 for f, sizes in FORMS for size in sizes)


def space_size():
    return len(typed_space(SUBJECTS[0]))


def canonical(decl):
    """Least-index declaration of the typed space with the same region."""
    target = region(decl)
    for d in typed_space(decl[0]):
        if region(d) == target:
            return d
    raise ConfigError("declaration_outside_space")


# ---------------------------------------------------- compiled (unit) form

def features(item):
    return (tuple(1 if item[0] == s else 0 for s in SUBJECTS)
            + tuple(1 if item[1] == c else 0 for c in CLASSES)
            + (item[2], item[3], 1))


WIDTH = len(SUBJECTS) + len(CLASSES) + 3
ZERO_UNIT = (0,) * WIDTH
BASE_UNITS = (
    (0,) * (WIDTH - 3) + (1, 0, -_q1_max()),
    (0,) * (WIDTH - 3) + (0, 1, -_q2_max()),
)
FEATURES = tuple(features(x) for x in ITEMS)

State = collections.namedtuple("State", ("base", "reserved", "live"))


def empty_state():
    return State(BASE_UNITS, (ZERO_UNIT,) * len(OWNERS), ())


def compile_patch(decl):
    """Re-derive the reserved-unit weights from the declaration alone."""
    subject, scope, form, size = decl
    w = [0] * WIDTH
    bias = 0
    w[SUBJECTS.index(subject)] = GATING
    bias -= GATING
    if scope != "all":
        w[len(SUBJECTS) + CLASSES.index(scope)] = GATING
        bias -= GATING
    q1i = len(SUBJECTS) + len(CLASSES)
    if form == "q1_margin":
        w[q1i] = 1
        bias += size - _q1_max()
    elif form == "q2_margin":
        w[q1i + 1] = 1
        bias += size - _q2_max()
    elif form == "sum_cap":
        w[q1i] = 1
        w[q1i + 1] = 1
        bias -= size
    else:
        raise ConfigError("form_unknown")
    w[-1] = bias
    return tuple(w)


def _unit(weights, f):
    s = sum(map(operator.mul, weights, f))
    return s if s > 0 else 0


def decide_compiled(state, f):
    return _decide(state.base + tuple(u for u in state.reserved
                                      if u != ZERO_UNIT), f)


def _decide(units, f):
    out = 1
    for u in units:
        out -= _unit(u, f)
    return 1 if out >= 1 else 0


def decisions_compiled(state):
    units = state.base + tuple(u for u in state.reserved if u != ZERO_UNIT)
    return bytes(_decide(units, f) for f in FEATURES)


def decisions_table(live):
    """Baseline: the rule plus a table of owned rows, no weights at all."""
    out = []
    for x in ITEMS:
        d = base_accepts(x)
        if d:
            for _owner, decl in live:
                if decl[0] == x[0] and fires(decl, x):
                    d = 0
                    break
        out.append(d)
    return bytes(out)


def decisions_global_edit(decl):
    """Baseline: the declaration written into the shared rule for everyone."""
    out = []
    for x in ITEMS:
        moved = (x[0],) + tuple(decl[1:])
        out.append(0 if (base_accepts(x) and fires(moved, x))
                   else base_accepts(x))
    return bytes(out)


def _canon_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def params_digest(state):
    return hashlib.sha256(_canon_json(
        [state.base, state.reserved]).encode("ascii")).hexdigest()


def base_digest(state):
    return hashlib.sha256(_canon_json(
        [BASE_RULE, state.base]).encode("ascii")).hexdigest()


def decisions_digest(dec):
    return hashlib.sha256(dec).hexdigest()


# ------------------------------------------------------------------ gate

def gate_stats(decl, records):
    """a: records the declaration fixes; b: records it breaks."""
    a = 0
    b = 0
    for item, label in records:
        before = base_accepts(item)
        after = 0 if (before and fires(decl, item)) else before
        if after == label and before != label:
            a += 1
        elif before == label and after != label:
            b += 1
    return (a, b)


def _tails(n):
    """tails[c] = P[Bin(n, eta) >= c] for c in 0..n+1, exact."""
    p = GATE_ETA
    pmf = [Fraction(comb(n, j)) * p ** j * (1 - p) ** (n - j)
           for j in range(n + 1)]
    tails = [Fraction(0)] * (n + 2)
    for j in range(n, -1, -1):
        tails[j] = tails[j + 1] + pmf[j]
    return tails


def gate_threshold(n):
    """Least c >= 1 with |H| * P[Bin(n, eta) >= c] <= alpha, or None."""
    if type(n) is not int or n < 0:
        raise ConfigError("n_not_int")
    if n not in _THRESHOLDS:
        h = space_size()
        tails = _tails(n)
        found = None
        for c in range(1, n + 1):
            if h * tails[c] <= GATE_ALPHA:
                found = c
                break
        _THRESHOLDS[n] = found
    return _THRESHOLDS[n]


_THRESHOLDS = {}


def gate_passes(a, b, n):
    c = gate_threshold(n)
    return c is not None and a - b >= max(GATE_MIN, c)


# --------------------------------------------------------------- learner

def _record_dicts(records):
    return [{"item": dict(zip(ITEM_KEYS, item)), "label": label}
            for item, label in records]


def declaration_dict(decl):
    return dict(zip(DECL_KEYS, decl))


def learn(owner, records, gated=True):
    """Search the owner's typed space on its own records.

    Candidates are ranked by improvement T = a - b, then by the smallest
    region, then by typed-space index. Returns a submission (with claimed
    stats and the evidence) or None.
    With gated=False the best positive candidate is proposed even when the
    gate would fail (the "search without the gate" arm).
    """
    owner = validate_owner(owner)
    snap = validate_records(records)
    subject = owned_subject(owner)
    if subject is None:
        raise ConfigError("owner_unknown")
    best = None
    best_key = None
    for d in typed_space(subject):
        a, b = gate_stats(d, snap)
        if a - b <= 0:
            continue
        # Largest improvement, then the narrowest region, then least index.
        key = (-(a - b), len(region(d)))
        if best_key is None or key < best_key:
            best, best_key = (d, a, b), key
    if best is None:
        return None
    d, a, b = best
    if gated and not gate_passes(a, b, len(snap)):
        return None
    return {"owner": owner, "declaration": declaration_dict(d),
            "claimed": {"a": a, "b": b}, "evidence": _record_dicts(snap)}


# ------------------------------------------------------ acceptance body

def _verdict(status, reason):
    return {"status": status, "reason": reason}


def _live_owner(state, owner):
    for o, d in state.live:
        if o == owner:
            return d
    return None


def _check_state(state):
    if type(state) is not State:
        raise ConfigError("state_not_state")


def _add(u, v):
    return tuple(x + y for x, y in zip(u, v))


def _sub(u, v):
    return tuple(x - y for x, y in zip(u, v))


def _sorted_live(live):
    return tuple(sorted(live, key=lambda r: OWNER_NAMES.index(r[0])))


def submit(state, submission):
    """Acceptance test. Returns (verdict, state); state is new on ADMIT."""
    try:
        _check_state(state)
        owner, decl, claimed, evidence = validate_submission(submission)
    except ConfigError as e:
        return _verdict(CONFIG_ERROR, str(e)), state
    subject = owned_subject(owner)
    if subject is None:
        return _verdict(REFUSE, "unknown_owner"), state
    if decl[0] != subject:
        return _verdict(REFUSE, "not_owner"), state
    if claimed is None or evidence is None:
        return _verdict(REFUSE, "ungated"), state
    a, b = gate_stats(decl, evidence)
    if (a, b) != claimed:
        return _verdict(REFUSE, "gate_unreproduced"), state
    if not gate_passes(a, b, len(evidence)):
        return _verdict(REFUSE, "gate_failed"), state
    if _live_owner(state, owner) is not None:
        return _verdict(REFUSE, "slot_taken"), state
    decl = canonical(decl)
    patch = compile_patch(decl)
    k = OWNER_NAMES.index(owner)
    reserved = list(state.reserved)
    reserved[k] = _add(reserved[k], patch)
    new = State(state.base, tuple(reserved),
                _sorted_live(state.live + ((owner, decl),)))
    if not behaviour_ok(state, new, decl):
        return _verdict(REFUSE, "interference"), state
    return _verdict(ADMIT, "admitted"), new


def behaviour_ok(old, new, decl):
    """Exhaustive check: new = old with decl's region rejected, nothing else."""
    old_dec = decisions_compiled(old)
    new_dec = decisions_compiled(new)
    reg = region(decl)
    for i in range(len(ITEMS)):
        want = 0 if i in reg else old_dec[i]
        if new_dec[i] != want:
            return False
    return True


def withdraw(state, actor, owner):
    """Only the owner withdraws its own live exception."""
    try:
        _check_state(state)
        actor = validate_owner(actor)
        owner = validate_owner(owner)
    except ConfigError as e:
        return _verdict(CONFIG_ERROR, str(e)), state
    if owned_subject(owner) is None or owned_subject(actor) is None:
        return _verdict(REFUSE, "unknown_owner"), state
    if actor != owner:
        return _verdict(REFUSE, "not_owner"), state
    decl = _live_owner(state, owner)
    if decl is None:
        return _verdict(REFUSE, "no_live_exception"), state
    k = OWNER_NAMES.index(owner)
    reserved = list(state.reserved)
    reserved[k] = _sub(reserved[k], compile_patch(decl))
    live = tuple(r for r in state.live if r[0] != owner)
    return _verdict(WITHDRAWN, "withdrawn"), State(state.base,
                                                   tuple(reserved), live)


# ------------------------------------------------------------- reporting

def block_correct(dec, truth, subject):
    """Count items of subject's block where dec matches truth (bytes)."""
    return sum(1 for i, x in enumerate(ITEMS)
               if x[0] == subject and dec[i] == truth[i])


def changed_outside(dec_a, dec_b, subject):
    return sum(1 for i, x in enumerate(ITEMS)
               if x[0] != subject and dec_a[i] != dec_b[i])


def paper_results():
    return {"status": "on_unmeasured",
            "note": "the paper's figures are not measured, re-run or "
                    "re-claimed here; see paper_evidence.json"}
