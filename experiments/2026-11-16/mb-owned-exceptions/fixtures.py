"""Frozen synthetic world: hidden truths, party records, hand cases.

Every truth, record and label here is synthetic and a fixture label; none
comes from the paper. Records are drawn once from a seeded generator and
pinned by digest in the tests.
"""

import random

import owned_exceptions as oe

SEED = 20261117
N_RECORDS = 30
NOISE = 0.05

# Hidden truth per owner: ("tighten", declaration), ("rule",) or
# ("relax", cls, q1) meaning the truth also accepts q1 == that value in cls.
TRUTHS = {
    "p0": ("tighten", ("s0", "all", "q1_margin", 2)),
    "p1": ("tighten", ("s1", "c", "q2_margin", 2)),
    "p2": ("rule",),
    "p3": ("relax", "a", 6),
}

# Where each party's records come from: its own block, base-accepted
# items only ("accepted"), one class of them, or the whole block ("block").
DRAWS = {
    "p0": ("accepted", None),
    "p1": ("accepted", "c"),
    "p2": ("accepted", None),
    "p3": ("block", None),
}


def truth_label(owner, item):
    kind = TRUTHS[owner]
    base = oe.base_accepts(item)
    if kind[0] == "tighten":
        return 0 if (base and oe.fires(kind[1], item)) else base
    if kind[0] == "relax":
        if (item[1] == kind[1] and item[2] == kind[2]
                and item[3] <= oe._q2_max()):
            return 1
        return base
    return base


def truth_bytes():
    """Truth over the whole domain: each block follows its owner's truth."""
    return bytes(truth_label(oe.subject_owner(x[0]), x) for x in oe.ITEMS)


def _pool(owner):
    subject = oe.owned_subject(owner)
    mode, cls = DRAWS[owner]
    out = []
    for x in oe.ITEMS:
        if x[0] != subject:
            continue
        if mode == "accepted" and not oe.base_accepts(x):
            continue
        if cls is not None and x[1] != cls:
            continue
        out.append(x)
    return out


def _make_records():
    rng = random.Random(SEED)
    out = {}
    for owner in oe.OWNER_NAMES:
        pool = _pool(owner)
        recs = []
        for _ in range(N_RECORDS):
            x = pool[rng.randrange(len(pool))]
            y = truth_label(owner, x)
            if rng.random() < NOISE:
                y = 1 - y
            recs.append({"item": dict(zip(oe.ITEM_KEYS, x)), "label": y})
        out[owner] = recs
    return out


RECORDS = _make_records()


def evidence_for(decl, reps=2):
    """Clean records that support decl: each region item, label 0, reps x."""
    recs = []
    for i in sorted(oe.region(decl)):
        x = oe.ITEMS[i]
        for _ in range(reps):
            recs.append({"item": dict(zip(oe.ITEM_KEYS, x)), "label": 0})
    return recs


# ------------------------------------------------------------ hand cases

class SubStr(str):
    pass


class SubInt(int):
    pass


class SubDict(dict):
    pass


def _decl(subject, scope, form, size):
    return {"subject": subject, "scope": scope, "form": form, "size": size}


def _sub(owner, decl, claimed=None, evidence=None):
    out = {"owner": owner, "declaration": decl}
    if claimed is not None:
        out["claimed"] = claimed
    if evidence is not None:
        out["evidence"] = evidence
    return out


D0 = ("s0", "all", "q1_margin", 2)
D1 = ("s1", "c", "q2_margin", 2)
D2 = ("s2", "c", "q2_margin", 2)


def _valid(owner, d, a, b, recs, **change):
    decl = _decl(*d)
    decl.update(change)
    return _sub(owner, decl, {"a": a, "b": b}, recs)


def _bad_record(field, value):
    recs = [dict(r, item=dict(r["item"])) for r in RECORDS["p0"]]
    if field == "label":
        recs[0]["label"] = value
    else:
        recs[0]["item"][field] = value
    return _sub("p0", _decl(*D0), {"a": 11, "b": 0}, recs)


def _key_swap(obj, key):
    out = {}
    for k, v in obj.items():
        out[SubStr(k) if k == key else k] = v
    return out


# (name, start, op, expected status, expected reason). start names cases
# admitted first; op is ("submit", submission) or ("withdraw", actor, owner).
CASES = [
    ("V1 p0 gated own exception", (), ("submit", _valid("p0", D0, 11, 0, RECORDS["p0"])), "ADMIT", "admitted"),
    ("V2 p1 gated own exception", (), ("submit", _valid("p1", D1, 7, 0, RECORDS["p1"])), "ADMIT", "admitted"),
    ("V3 p1 after p0", ("V1 p0 gated own exception",), ("submit", _valid("p1", D1, 7, 0, RECORDS["p1"])), "ADMIT", "admitted"),
    ("R1 unowned subject", (), ("submit", _valid("p1", D0, 11, 0, RECORDS["p0"])), "REFUSE", "not_owner"),
    ("R2 unknown owner", (), ("submit", _valid("p9", D0, 11, 0, RECORDS["p0"])), "REFUSE", "unknown_owner"),
    ("R3 ungated no gate fields", (), ("submit", _sub("p0", _decl(*D0))), "REFUSE", "ungated"),
    ("R4 ungated no claim", (), ("submit", _sub("p0", _decl(*D0), None, RECORDS["p0"])), "REFUSE", "ungated"),
    ("R5 ungated no evidence", (), ("submit", _sub("p0", _decl(*D0), {"a": 11, "b": 0})), "REFUSE", "ungated"),
    ("R6 forged claim", (), ("submit", _valid("p0", D0, 12, 0, RECORDS["p0"])), "REFUSE", "gate_unreproduced"),
    ("R7 gate fails on noise", (), ("submit", _valid("p2", D2, 2, 0, RECORDS["p2"])), "REFUSE", "gate_failed"),
    ("R8 empty evidence", (), ("submit", _valid("p0", D0, 0, 0, [])), "REFUSE", "gate_failed"),
    ("R9 slot taken", ("V1 p0 gated own exception",), ("submit", _valid("p0", D0, 11, 0, RECORDS["p0"])), "REFUSE", "slot_taken"),
    ("R10 wrong declaration for the records", (), ("submit", _valid("p0", ("s0", "b", "sum_cap", 9), 0, 0, RECORDS["p0"])), "REFUSE", "gate_failed"),
    ("C1 bool size", (), ("submit", _valid("p0", D0, 11, 0, RECORDS["p0"], size=True)), "config_error", "size_not_int"),
    ("C2 NaN size", (), ("submit", _valid("p0", D0, 11, 0, RECORDS["p0"], size=float("nan"))), "config_error", "size_not_int"),
    ("C3 inf size", (), ("submit", _valid("p0", D0, 11, 0, RECORDS["p0"], size=float("inf"))), "config_error", "size_not_int"),
    ("C4 float size", (), ("submit", _valid("p0", D0, 11, 0, RECORDS["p0"], size=2.0)), "config_error", "size_not_int"),
    ("C5 int subclass size", (), ("submit", _valid("p0", D0, 11, 0, RECORDS["p0"], size=SubInt(2))), "config_error", "size_not_int"),
    ("C6 relaxation form", (), ("submit", _valid("p0", D0, 11, 0, RECORDS["p0"], form="q1_relax")), "config_error", "form_unknown"),
    ("C7 size out of range", (), ("submit", _valid("p0", D0, 11, 0, RECORDS["p0"], size=4)), "config_error", "size_range"),
    ("C8 unknown scope", (), ("submit", _valid("p0", D0, 11, 0, RECORDS["p0"], scope="d")), "config_error", "scope_unknown"),
    ("C9 str subclass subject", (), ("submit", _valid("p0", D0, 11, 0, RECORDS["p0"], subject=SubStr("s0"))), "config_error", "subject_not_str"),
    ("C10 str subclass owner", (), ("submit", _valid(SubStr("p0"), D0, 11, 0, RECORDS["p0"])), "config_error", "owner_not_str"),
    ("C11 str subclass declaration key", (), ("submit", dict(_valid("p0", D0, 11, 0, RECORDS["p0"]), declaration=_key_swap(_decl(*D0), "size"))), "config_error", "declaration_key_not_str"),
    ("C12 str subclass submission key", (), ("submit", _key_swap(_valid("p0", D0, 11, 0, RECORDS["p0"]), "owner")), "config_error", "submission_key_not_str"),
    ("C13 weights sent with declaration", (), ("submit", dict(_valid("p0", D0, 11, 0, RECORDS["p0"]), weights=[0] * 10)), "config_error", "submission_keys"),
    ("C14 missing scope", (), ("submit", dict(_valid("p0", D0, 11, 0, RECORDS["p0"]), declaration={"subject": "s0", "form": "q1_margin", "size": 2})), "config_error", "declaration_keys"),
    ("C15 dict subclass submission", (), ("submit", SubDict(_valid("p0", D0, 11, 0, RECORDS["p0"]))), "config_error", "submission_not_dict"),
    ("C16 tuple evidence", (), ("submit", _valid("p0", D0, 11, 0, tuple(RECORDS["p0"]))), "config_error", "evidence_not_list"),
    ("C17 bool label", (), ("submit", _bad_record("label", True)), "config_error", "label_not_int"),
    ("C18 q1 outside domain", (), ("submit", _bad_record("q1", 8)), "config_error", "q1_range"),
    ("C19 NaN q2", (), ("submit", _bad_record("q2", float("nan"))), "config_error", "q2_not_int"),
    ("C20 negative claim", (), ("submit", _valid("p0", D0, -1, 0, RECORDS["p0"])), "config_error", "claimed_a_range"),
    ("C21 bool claim", (), ("submit", _valid("p0", D0, True, 0, RECORDS["p0"])), "config_error", "claimed_a_not_int"),
    ("C22 missing owner", (), ("submit", {"declaration": _decl(*D0)}), "config_error", "submission_keys"),
    ("W1 owner withdraws", ("V1 p0 gated own exception",), ("withdraw", "p0", "p0"), "WITHDRAWN", "withdrawn"),
    ("W2 other party withdraws", ("V1 p0 gated own exception",), ("withdraw", "p1", "p0"), "REFUSE", "not_owner"),
    ("W3 nothing live", (), ("withdraw", "p0", "p0"), "REFUSE", "no_live_exception"),
    ("W4 unknown actor", ("V1 p0 gated own exception",), ("withdraw", "p9", "p0"), "REFUSE", "unknown_owner"),
    ("W5 str subclass actor", ("V1 p0 gated own exception",), ("withdraw", SubStr("p0"), "p0"), "config_error", "owner_not_str"),
    ("W6 withdraw twice", ("V1 p0 gated own exception", "W1 owner withdraws"), ("withdraw", "p0", "p0"), "REFUSE", "no_live_exception"),
]
