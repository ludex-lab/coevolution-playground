"""Synthetic fixtures for w19-engram-release. Run: python3 fixtures.py

Each scenario builds a store, admits and trains (or not), then asks the
release gate about one skill. ``expected`` is used only by this file and the
tests; it is never passed to the gate.
"""

import engram_release as E

ADMIT = dict(mastery=0.0, tau_m=0.8, n_min=2, d_min=1)


def rec(rid, skill, rule, inputs, success=True, source="teacher"):
    fn = E.TRUE_RULES[rule]
    return E.Record(rid, skill, tuple((x, fn(x)) for x in inputs), success, source)


def build(skill, rule, train_inputs, probe_inputs, late_inputs=(),
          admit=True, train=True, success=True, student=None,
          external_fit=False, admit_kwargs=None):
    """Return (store, student, base, probes)."""
    store = E.Store()
    for i, chunk in enumerate(train_inputs):
        store.add(rec("%s-%d" % (skill, i), skill, rule, chunk, success))
    student = E.Student() if student is None else student
    if admit:
        store.admit(skill, **(admit_kwargs or ADMIT))
    if train:
        store.train(student, skill)
    if external_fit:
        # The student learned the rule elsewhere; the store never saw it.
        fn = E.TRUE_RULES[rule]
        student.fit(skill, tuple((x, fn(x)) for c in train_inputs for x in c))
    for j, chunk in enumerate(late_inputs):
        store.add(rec("%s-late-%d" % (skill, j), skill, rule, chunk))
    probes = E.make_probes(rule, probe_inputs)
    return store, student, E.RetrievalBase(), probes


class RaisingFit(E.Student):
    def fit(self, skill, examples):
        raise RuntimeError("training failed")


class RaisingAnswer(E.Student):
    def answer(self, skill, x):
        raise RuntimeError("load failed")


class AlwaysEqual:
    def __eq__(self, other):
        return True

    def __hash__(self):
        return 0


class EqualityCheat(E.Student):
    """Answers with an object that claims to equal anything."""
    def answer(self, skill, x):
        return AlwaysEqual()


class SegmentCopier(E.Student):
    """Lookup table over record inputs; splits a probe into stored inputs
    (case and spacing ignored) and concatenates their outputs. Learns no
    rule."""
    def fit(self, skill, examples):
        self.table = {x: y for x, y in examples}

    def answer(self, skill, x):
        q = "".join(x.split()).lower()
        out, i = "", 0
        while i < len(q):
            for j in range(len(q), i, -1):
                if q[i:j] in self.table:
                    out += self.table[q[i:j]]
                    i = j
                    break
            else:
                return None
        return out


class FuzzyCopier(E.Student):
    """Copies records under a case-folded and a sorted-character key; learns
    no rule."""
    def fit(self, skill, examples):
        self.table = {}
        for x, y in examples:
            self.table.setdefault(x.casefold(), y)
            self.table.setdefault("".join(sorted(x.casefold())), y)

    def answer(self, skill, x):
        k = x.casefold()
        return self.table.get(k, self.table.get("".join(sorted(k))))


# name -> (builder kwargs, release kwargs, expected)
# expected: outcome, reasons, retrievable count after the gate
SCENARIOS = [
    ("compliant_upper_released",
     dict(skill="upper", rule="upper", train_inputs=[("abc", "dog"), ("sun",)],
          probe_inputs=("xyz", "hello", "tree", "moon")),
     dict(alpha=0.6),
     (E.RELEASE, (), 0)),
    ("compliant_double_released",
     dict(skill="double", rule="double", train_inputs=[("ab",), ("q",)],
          probe_inputs=("xy", "cat", "z")),
     dict(alpha=0.6),
     (E.RELEASE, (), 0)),
    ("late_record_not_trained_stays",
     dict(skill="upper", rule="upper", train_inputs=[("abc",)],
          late_inputs=[("pen",)], probe_inputs=("xyz", "moon")),
     dict(alpha=0.6),
     (E.RELEASE, (), 1)),
    ("unmastered_sort_held",
     # Trained only on descending inputs: the student induces reverse.
     # A later record disambiguates for the base with retrieval.
     dict(skill="sort", rule="sort", train_inputs=[("cba", "zyx")],
          late_inputs=[("bac",)],
          probe_inputs=("dfe", "kml", "fed", "hgj", "rts")),
     dict(alpha=0.6),
     (E.HOLD, (E.BELOW_RELATIVE, E.BELOW_FLOOR), 2)),
    ("fails_relative_only_held",
     dict(skill="sort", rule="sort", train_inputs=[("cba", "zyx")],
          late_inputs=[("bac",)],
          probe_inputs=("fed", "qpo", "ihg", "nml", "dfe")),
     dict(alpha=0.6),
     (E.HOLD, (E.BELOW_RELATIVE,), 2)),
    ("fails_absolute_only_held",
     # Student and base both induce reverse: equal scores, below the floor.
     dict(skill="sort", rule="sort", train_inputs=[("cba", "zyx")],
          probe_inputs=("fed", "qpo", "ihg", "dfe", "kml")),
     dict(alpha=0.7),
     (E.HOLD, (E.BELOW_FLOOR,), 1)),
    ("rule_outside_library_held",
     dict(skill="cap", rule="capitalize", train_inputs=[("abc", "dog")],
          probe_inputs=("xyz", "moon")),
     dict(alpha=0.6),
     (E.HOLD, (E.BELOW_FLOOR,), 1)),
    ("not_admitted_held",
     # Student masters the rule from outside the store; still held.
     dict(skill="upper", rule="upper", train_inputs=[("abc",)],
          probe_inputs=("xyz", "moon"), admit=False, train=False,
          external_fit=True),
     dict(alpha=0.6),
     (E.HOLD, (E.NOT_ADMITTED, E.NO_PARTICIPATION), 1)),
    ("admitted_not_trained_held",
     dict(skill="upper", rule="upper", train_inputs=[("abc",)],
          probe_inputs=("xyz", "moon"), train=False, external_fit=True),
     dict(alpha=0.6),
     (E.HOLD, (E.NO_PARTICIPATION,), 1)),
    ("admitted_no_valid_examples_held",
     # Mastery branch admits; every record is a failed trace, so D_s is empty.
     dict(skill="upper", rule="upper", train_inputs=[("abc",), ("dog",)],
          probe_inputs=("xyz", "moon"), success=False, external_fit=True,
          admit_kwargs=dict(mastery=0.9, tau_m=0.8, n_min=2, d_min=1)),
     dict(alpha=0.6),
     (E.HOLD, (E.NO_PARTICIPATION,), 2)),
    ("training_failure_held",
     dict(skill="upper", rule="upper", train_inputs=[("abc",)],
          probe_inputs=("xyz", "moon"), student=RaisingFit()),
     dict(alpha=0.6),
     (E.HOLD, (E.NO_PARTICIPATION,), 1)),
    ("memorising_student_held",
     # Copies record text into a lookup table; probes are held out.
     dict(skill="upper", rule="upper", train_inputs=[("abc", "dog")],
          probe_inputs=("xyz", "moon"), student=E.MemorisingStudent()),
     dict(alpha=0.6),
     (E.HOLD, (E.BELOW_RELATIVE, E.BELOW_FLOOR), 1)),
    ("probe_copies_record_held",
     # Probe inputs taken from the record: copying would score 1.0.
     dict(skill="upper", rule="upper", train_inputs=[("abc", "dog")],
          probe_inputs=("abc", "dog"), student=E.MemorisingStudent()),
     dict(alpha=0.6),
     (E.HOLD, (E.PROBE_OVERLAP,), 1)),
    ("floor_equal_score_held",
     # Reversing, not sorting: 3/5 on the probes, exactly the floor 0.6.
     dict(skill="sort", rule="sort", train_inputs=[("cba",)],
          probe_inputs=("fed", "qpo", "ihg", "dfe", "kml")),
     dict(alpha=0.6),
     (E.HOLD, (E.BELOW_FLOOR,), 1)),
    ("case_variant_probe_held",
     dict(skill="upper", rule="upper", train_inputs=[("abc", "dog", "sun")],
          probe_inputs=("ABC", "Dog", "sUN"), student=FuzzyCopier()),
     dict(alpha=0.6),
     (E.HOLD, (E.PROBE_OVERLAP,), 1)),
    ("reordered_probe_held",
     dict(skill="sort", rule="sort", train_inputs=[("abc", "dog", "sun")],
          probe_inputs=("cba", "god", "nus"), student=FuzzyCopier()),
     dict(alpha=0.6),
     (E.HOLD, (E.PROBE_OVERLAP,), 1)),
    ("concat_probe_held",
     # Probes spliced from whole record inputs; a segment table answers them.
     dict(skill="upper", rule="upper",
          train_inputs=[("abc", "dog", "sun", "moon", "tree")],
          probe_inputs=("abcdog", "sunmoon", "treeabc"), student=SegmentCopier()),
     dict(alpha=0.6),
     (E.HOLD, (E.PROBE_ANSWERABLE,), 1)),
    ("three_way_concat_held",
     dict(skill="upper", rule="upper",
          train_inputs=[("abc", "dog", "sun", "moon", "tree")],
          probe_inputs=("abcdogsun", "moontreeabc"), student=SegmentCopier()),
     dict(alpha=0.6),
     (E.HOLD, (E.PROBE_ANSWERABLE,), 1)),
    ("concat_case_space_held",
     dict(skill="upper", rule="upper",
          train_inputs=[("abc", "dog", "sun", "moon", "tree")],
          probe_inputs=("ABC dog", "Sun Moon", "tree  ABC"), student=SegmentCopier()),
     dict(alpha=0.6),
     (E.HOLD, (E.PROBE_ANSWERABLE,), 1)),
    ("non_str_answer_held",
     dict(skill="upper", rule="upper", train_inputs=[("abc", "dog"), ("sun",)],
          probe_inputs=("xyz", "hello", "tree", "moon"), student=EqualityCheat()),
     dict(alpha=0.6),
     (E.HOLD, (E.BELOW_RELATIVE, E.BELOW_FLOOR), 2)),
    ("empty_probes_held",
     dict(skill="upper", rule="upper", train_inputs=[("abc",)], probe_inputs=()),
     dict(alpha=0.6),
     (E.HOLD, (E.EMPTY_PROBES,), 1)),
    ("model_error_held",
     dict(skill="upper", rule="upper", train_inputs=[("abc",)],
          probe_inputs=("xyz",), student=RaisingAnswer()),
     dict(alpha=0.6),
     (E.HOLD, (E.MODEL_ERROR,), 1)),
    ("nan_floor_held",
     dict(skill="upper", rule="upper", train_inputs=[("abc",)], probe_inputs=("xyz",)),
     dict(alpha=float("nan")),
     (E.HOLD, (E.BAD_FLOOR,), 1)),
    ("inf_margin_held",
     dict(skill="upper", rule="upper", train_inputs=[("abc",)], probe_inputs=("xyz",)),
     dict(delta=float("-inf"), alpha=0.6),
     (E.HOLD, (E.BAD_MARGIN,), 1)),
    ("bool_floor_held",
     dict(skill="upper", rule="upper", train_inputs=[("abc",)], probe_inputs=("xyz",)),
     dict(alpha=False),
     (E.HOLD, (E.BAD_FLOOR,), 1)),
    ("string_floor_held",
     dict(skill="upper", rule="upper", train_inputs=[("abc",)], probe_inputs=("xyz",)),
     dict(alpha="0.6"),
     (E.HOLD, (E.BAD_FLOOR,), 1)),
    ("floor_of_one_held",
     dict(skill="upper", rule="upper", train_inputs=[("abc",)], probe_inputs=("xyz",)),
     dict(alpha=1.0),
     (E.HOLD, (E.BAD_FLOOR,), 1)),
]

# Score-only cases for verify(a_w, a_m, delta, alpha).
VERIFY_CASES = [
    ("equal_scores_above_floor", (0.8, 0.8, 0.0, 0.6), ()),
    ("bounded_decrease_with_negative_margin", (0.85, 0.9, -0.1, 0.6), ()),
    ("score_at_floor_is_below_strict_floor", (0.6, 0.4, 0.0, 0.6), (E.BELOW_FLOOR,)),
    ("relative_short_by_margin", (0.9, 0.8, 0.2, 0.6), (E.BELOW_RELATIVE,)),
    ("nan_student_score", (float("nan"), 0.4, 0.0, 0.6), (E.BAD_SCORE,)),
    ("inf_base_score", (0.9, float("inf"), 0.0, 0.6), (E.BAD_SCORE,)),
    ("string_score", ("0.9", 0.4, 0.0, 0.6), (E.BAD_SCORE,)),
    ("bool_score", (True, 0.4, 0.0, 0.6), (E.BAD_SCORE,)),
    ("none_score", (None, 0.4, 0.0, 0.6), (E.BAD_SCORE,)),
    ("score_above_one", (1.5, 0.6, 0.0, 0.6), (E.BAD_SCORE,)),
    ("negative_floor", (0.9, 0.4, 0.0, -0.1), (E.BAD_FLOOR,)),
    ("bool_margin", (0.9, 0.4, True, 0.6), (E.BAD_MARGIN,)),
]


def run_scenario(name, bkw, rkw):
    store, student, base, probes = build(**bkw)
    d = E.release(store, bkw["skill"], student, base, probes, **rkw)
    return store, d


def check_all(out=print):
    failures = 0
    for name, bkw, rkw, (outcome, reasons, retrievable) in SCENARIOS:
        store, d = run_scenario(name, bkw, rkw)
        left = len(store.retrieve(bkw["skill"]))
        ok = (d.outcome == outcome and d.reasons == reasons and left == retrievable)
        failures += not ok
        out("%s %s: %s %s retrievable=%d" % ("PASS" if ok else "FAIL", name,
                                             d.outcome, list(d.reasons), left))
    for name, args, reasons in VERIFY_CASES:
        got = E.verify(*args)
        ok = got == reasons
        failures += not ok
        out("%s verify/%s: %s" % ("PASS" if ok else "FAIL", name, list(got)))
    # Unknown skill against a populated store.
    store, student, base, probes = build("upper", "upper", [("abc",)], ("xyz",))
    d = E.release(store, "nonexistent", student, base, probes, alpha=0.6)
    ok = d.outcome == E.HOLD and d.reasons == (E.UNKNOWN_SKILL,)
    failures += not ok
    out("%s unknown_skill_held: %s %s" % ("PASS" if ok else "FAIL", d.outcome, list(d.reasons)))
    total = len(SCENARIOS) + len(VERIFY_CASES) + 1
    out("report: %d/%d fixtures as expected" % (total - failures, total))
    return failures, total


if __name__ == "__main__":
    import sys
    f, _ = check_all()
    sys.exit(1 if f else 0)
