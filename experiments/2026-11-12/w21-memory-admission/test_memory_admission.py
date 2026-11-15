"""Tests for the falsification-gated memory-admission sketch.

Run from this folder: python3 -B -m unittest

The source check reads the abstract copy named in paper_evidence.json from
the directory in $W21MA_SOURCES. There is no default: when the variable is
unset, or the file is absent there, that one test is skipped.
"""

import copy
import hashlib
import json
import os
import sys
import threading
import unittest

import fixtures as F
import memory_admission as M

HERE = os.path.dirname(os.path.abspath(__file__))
DAY = "2026-11-12"
DAY_HEADER = "# experiments/" + DAY + "\n"
SOURCES = os.environ.get("W21MA_SOURCES")
CODE = ("memory_admission.py", "fixtures.py")
DOCS = ("README.md", "NOTICE")
OWN = DOCS + CODE + ("test_memory_admission.py", "mutants.py",
                     "paper_evidence.json")
TT, FA, AR = M.TARGET_TRANSFER, M.FALSIFICATION, M.ARCHIVED_REGRESSION


def day_readme():
    """Day-index README: ../README.md in the repo layout, else _day/README.md.

    The parent README is used only when this folder sits in the 2026-11-12
    day folder and that README starts with the day header, so an unrelated
    README above a flat draft folder is never picked up.
    """
    parent = os.path.dirname(HERE)
    repo = os.path.join(parent, "README.md")
    if os.path.basename(parent) == DAY and os.path.isfile(repo):
        with open(repo, encoding="utf-8") as fh:
            if fh.read().startswith(DAY_HEADER):
                return repo
    return os.path.join(HERE, "_day", "README.md")


L1_LESSON = {"id": "L1", "precondition": "size=small",
             "behavior_change": "parse_whole",
             "expected_effect": "small inputs are parsed whole",
             "verifier": M.ACTION_MATCHES_EXPECTED}


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def flat(name):
    """File text with runs of whitespace folded to one space."""
    return " ".join(read(name).split())


def admit(name, store=None, **kw):
    store = F.seed_store() if store is None else store
    return store, M.admit(store, F.request(name, **kw))


def passed(rec, probe):
    return probe not in rec["failed_probes"]


class SpoofStr(str):
    """A str subclass that claims to equal everything."""

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = str.__hash__


class RaisingStr(str):
    def __eq__(self, other):
        raise RuntimeError("eq")

    def __ne__(self, other):
        raise RuntimeError("ne")

    def __hash__(self):
        raise RuntimeError("hash")

    def __str__(self):
        raise RuntimeError("str")

    def __len__(self):
        raise RuntimeError("len")


class RaisingObj(object):
    def __eq__(self, other):
        raise RuntimeError("eq")

    def __hash__(self):
        raise RuntimeError("hash")

    def __bool__(self):
        raise RuntimeError("bool")


class SubDict(dict):
    pass


class SubList(list):
    pass


class SubInt(int):
    pass


def sub_store(lessons):
    """Instance of a MemoryStore subclass, built against the live class."""
    return type("SubStore", (M.MemoryStore,), {})(lessons)


class DoneWhen(unittest.TestCase):
    """The done-when cases; each probe is independently necessary."""

    def test_a1_fails_falsification_only_not_committed(self):
        store, rec = admit("false")
        self.assertEqual(rec["outcome"], M.REJECT)
        self.assertEqual(rec["reason"], M.FALSIFICATION_FAILED)
        self.assertEqual(rec["failed_probes"], (FA,))
        self.assertTrue(passed(rec, TT) and passed(rec, AR))
        self.assertFalse(rec["committed"])
        self.assertEqual(store.ids(), ("L0",))

    def test_a2_breaks_archive_only_not_committed(self):
        store, rec = admit("breaks_archive")
        self.assertEqual(rec["outcome"], M.REJECT)
        self.assertEqual(rec["reason"], M.REGRESSION_FAILED)
        self.assertEqual(rec["failed_probes"], (AR,))
        self.assertEqual(rec["measures"][AR]["broken"], 1)
        self.assertFalse(rec["committed"])
        self.assertEqual(store.ids(), ("L0",))

    def test_a3_fails_transfer_only_not_committed(self):
        store, rec = admit("no_transfer")
        self.assertEqual(rec["outcome"], M.REJECT)
        self.assertEqual(rec["reason"], M.TRANSFER_FAILED)
        self.assertEqual(rec["failed_probes"], (TT,))
        self.assertFalse(rec["committed"])
        self.assertEqual(store.ids(), ("L0",))

    def test_b_passes_all_committed_and_visible_later(self):
        store = F.seed_store()
        self.assertEqual(store.act(F.LATER_TASK), "parse_whole")
        store, rec = admit("good", store=store)
        self.assertEqual(rec["outcome"], M.COMMIT)
        self.assertEqual(rec["reason"], M.ALL_PROBES_PASSED)
        self.assertEqual(rec["failed_probes"], ())
        self.assertTrue(rec["committed"])
        self.assertEqual(store.ids(), ("L0", "H-good"))
        self.assertEqual(store.act(F.LATER_TASK), "parse_stream")
        self.assertEqual(store.act(F.LATER_TASK), F.LATER_TASK["expected_action"])

    def test_b_committed_lesson_is_base_for_next_admission(self):
        store, _ = admit("good")
        _, rec = admit("narrow", store=store)
        # huge csv is not matched by H-good, large csv is now solved on base.
        self.assertEqual(rec["measures"][TT]["base_ok"], 1)

    def test_c_each_missing_probe_is_unmeasured_no_write(self):
        for name in F.CANDIDATES:
            for probe in M.REQUIRED_PROBES:
                store, rec = admit(name, drop=(probe,))
                self.assertEqual(rec["outcome"], M.ON_UNMEASURED, (name, probe))
                self.assertEqual(rec["reason"], M.PROBE_NOT_RUN)
                self.assertEqual(rec["failed_probes"], (probe,))
                self.assertFalse(rec["committed"])
                self.assertEqual(store.ids(), ("L0",))

    def test_c_empty_probe_is_unmeasured(self):
        for probe in M.REQUIRED_PROBES:
            req = F.request("good")
            req["probes"][probe] = []
            store = F.seed_store()
            rec = M.admit(store, req)
            self.assertEqual(rec["outcome"], M.ON_UNMEASURED, probe)
            self.assertEqual(store.ids(), ("L0",))

    def test_c_all_probes_missing_is_unmeasured(self):
        req = F.request("good", drop=M.REQUIRED_PROBES)
        store = F.seed_store()
        rec = M.admit(store, req)
        self.assertEqual(rec["outcome"], M.ON_UNMEASURED)
        self.assertEqual(rec["failed_probes"], (TT,))
        self.assertEqual(store.ids(), ("L0",))

    def test_vacuous_falsification_is_unmeasured(self):
        req = F.request("good")
        req["probes"][FA] = [F.task("fa-csv-small-v", "csv", "small")]
        store = F.seed_store()
        rec = M.admit(store, req)
        self.assertEqual(rec["outcome"], M.ON_UNMEASURED)
        self.assertEqual(rec["reason"], M.PROBE_VACUOUS)
        self.assertEqual(rec["failed_probes"], (FA,))
        self.assertEqual(store.ids(), ("L0",))

    def test_local_success_alone_never_commits(self):
        for name in F.CANDIDATES:
            store, rec = admit(name, drop=M.REQUIRED_PROBES)
            self.assertNotEqual(rec["outcome"], M.COMMIT)
            self.assertEqual(store.ids(), ("L0",))

    def test_local_failure_rejects_even_when_probes_pass(self):
        store, rec = admit("good", local_success=False)
        self.assertEqual(rec["outcome"], M.REJECT)
        self.assertEqual(rec["reason"], M.SOURCE_EPISODE_FAILED)
        self.assertEqual(store.ids(), ("L0",))


class NoLeak(unittest.TestCase):
    """Temporary state never reaches the store unless the outcome is commit."""

    def _snapshot(self, store):
        return (store.lessons(), tuple(store.act(t) for t in F.all_tasks()))

    def test_non_commit_outcomes_leave_store_unchanged(self):
        cases = [("false", {}), ("breaks_archive", {}), ("no_transfer", {}),
                 ("narrow", {}), ("good", {"drop": (FA,)}),
                 ("good", {"local_success": False}),
                 ("good", {"deadline": {"timeout_s": 5, "on_expiry": M.HOLD,
                                        "expired": True}}),
                 ("good", {"thresholds": {"refine_min_gain_pct": 50}})]
        for name, kw in cases:
            store = F.seed_store()
            before = self._snapshot(store)
            lessons_obj = store._lessons
            rec = M.admit(store, F.request(name, **kw))
            self.assertNotEqual(rec["outcome"], M.COMMIT, (name, kw))
            self.assertFalse(rec["committed"])
            self.assertEqual(self._snapshot(store), before, (name, kw))
            self.assertIs(store._lessons, lessons_obj)

    def test_commit_writes_exactly_one_lesson(self):
        store = F.seed_store()
        n = len(store.lessons())
        M.admit(store, F.request("good"))
        self.assertEqual(len(store.lessons()), n + 1)

    def test_committed_lesson_is_a_plain_copy(self):
        store = F.seed_store()
        req = F.request("good")
        M.admit(store, req)
        req["hypothesis"]["behavior_change"] = "skip"
        req["hypothesis"]["precondition"] = "kind=csv"
        lesson = store.lessons()[-1]
        self.assertEqual(lesson, ("H-good", "size", "large", "parse_stream"))
        for part in lesson:
            self.assertIs(type(part), str)

    def test_request_not_mutated(self):
        req = F.request("good")
        before = copy.deepcopy(req)
        M.admit(F.seed_store(), req)
        self.assertEqual(req, before)

    def test_store_lessons_view_is_a_copy(self):
        store = F.seed_store()
        view = store.lessons()
        self.assertIsInstance(view, tuple)
        self.assertEqual(store.ids(), ("L0",))


class Refine(unittest.TestCase):
    """Refine choice: tested, with fixture-declared gain and risk thresholds."""

    def test_narrow_lesson_refines_not_committed(self):
        store, rec = admit("narrow")
        self.assertEqual(rec["outcome"], M.REFINE)
        self.assertEqual(rec["reason"], M.WITHIN_REFINE_BOUNDS)
        self.assertEqual(rec["failed_probes"], (TT,))
        self.assertFalse(rec["committed"])
        self.assertEqual(store.ids(), ("L0",))

    def test_gain_threshold_boundary(self):
        # narrow gains 1 of 2 transfer tasks = 50%.
        _, rec = admit("narrow", thresholds={"refine_min_gain_pct": 50,
                                             "refine_max_risk_pct": 0})
        self.assertEqual(rec["outcome"], M.REFINE)
        _, rec = admit("narrow", thresholds={"refine_min_gain_pct": 51,
                                             "refine_max_risk_pct": 0})
        self.assertEqual(rec["outcome"], M.REJECT)
        self.assertEqual(rec["reason"], M.TRANSFER_FAILED)

    def test_risk_threshold_boundary(self):
        # breaks_archive breaks 1 of 3 archived tasks = 33.3%.
        _, rec = admit("breaks_archive", thresholds={"refine_min_gain_pct": 50,
                                                     "refine_max_risk_pct": 33})
        self.assertEqual(rec["outcome"], M.REJECT)
        self.assertEqual(rec["reason"], M.REGRESSION_FAILED)
        store, rec = admit("breaks_archive", thresholds={"refine_min_gain_pct": 50,
                                                         "refine_max_risk_pct": 34})
        self.assertEqual(rec["outcome"], M.REFINE)
        self.assertEqual(store.ids(), ("L0",))

    def test_zero_gain_never_refines(self):
        _, rec = admit("no_transfer", thresholds={"refine_min_gain_pct": 1,
                                                  "refine_max_risk_pct": 100})
        self.assertEqual(rec["outcome"], M.REJECT)
        self.assertEqual(rec["reason"], M.TRANSFER_FAILED)

    def test_falsification_failure_never_refines(self):
        _, rec = admit("false", thresholds={"refine_min_gain_pct": 1,
                                            "refine_max_risk_pct": 100})
        self.assertEqual(rec["outcome"], M.REJECT)
        self.assertEqual(rec["reason"], M.FALSIFICATION_FAILED)

    def test_thresholds_must_be_declared(self):
        for missing in M.THRESHOLD_FIELDS:
            th = dict(F.THRESHOLDS)
            del th[missing]
            store, rec = admit("narrow", thresholds=th)
            self.assertEqual(rec["outcome"], M.CONFIG_ERROR, missing)
            self.assertEqual(store.ids(), ("L0",))

    def test_threshold_types_and_ranges(self):
        bad = [{"refine_min_gain_pct": True, "refine_max_risk_pct": 0},
               {"refine_min_gain_pct": 50, "refine_max_risk_pct": False},
               {"refine_min_gain_pct": SubInt(50), "refine_max_risk_pct": 0},
               {"refine_min_gain_pct": 50.0, "refine_max_risk_pct": 0},
               {"refine_min_gain_pct": 0, "refine_max_risk_pct": 0},
               {"refine_min_gain_pct": 101, "refine_max_risk_pct": 0},
               {"refine_min_gain_pct": 50, "refine_max_risk_pct": -1},
               {"refine_min_gain_pct": 50, "refine_max_risk_pct": 101},
               {"refine_min_gain_pct": 50, "refine_max_risk_pct": 0, "x": 1},
               SubDict(F.THRESHOLDS)]
        for th in bad:
            _, rec = admit("narrow", thresholds=th)
            self.assertEqual(rec["outcome"], M.CONFIG_ERROR, th)


class ProbeSemantics(unittest.TestCase):

    def test_regression_counts_only_newly_broken_tasks(self):
        req = F.request("good")
        already_failing = F.task("arc-csv-huge", "csv", "huge")
        req["probes"][AR] = F.archive() + [already_failing]
        store = F.seed_store()
        self.assertNotEqual(store.act(already_failing), already_failing["expected_action"])
        rec = M.admit(store, req)
        self.assertEqual(rec["measures"][AR]["broken"], 0)
        self.assertEqual(rec["outcome"], M.COMMIT)

    def test_transfer_needs_measured_gain(self):
        # Every transfer task already succeeds on the base store: no gain.
        req = F.request("good")
        req["probes"][TT] = [F.task("tr-json-small", "json", "small")]
        rec = M.admit(F.seed_store(), req)
        self.assertEqual(rec["outcome"], M.REJECT)
        self.assertEqual(rec["reason"], M.TRANSFER_FAILED)

    def test_transfer_needs_every_task(self):
        rec = M.admit(F.seed_store(), F.request("narrow", thresholds={
            "refine_min_gain_pct": 100, "refine_max_risk_pct": 0}))
        self.assertIn(TT, rec["failed_probes"])
        self.assertEqual(rec["measures"][TT], {"n": 2, "base_ok": 0, "temp_ok": 1,
                                               "broken": 0, "matched": 1,
                                               "decided": 1})

    def test_earlier_lessons_take_precedence(self):
        store = F.seed_store()
        log_large = F.task("x-log-large", "log", "large")
        M.admit(store, F.request("good"))
        self.assertEqual(store.act(log_large), "tail")

    def test_measures_shape(self):
        _, rec = admit("good")
        self.assertEqual(set(rec["measures"]), set(M.REQUIRED_PROBES))
        self.assertEqual(rec["measures"][AR], {"n": 3, "base_ok": 3, "temp_ok": 3,
                                               "broken": 0, "matched": 1,
                                               "decided": 0})
        # fa-xml-large is decided by H-good; fa-log-large matches size=large
        # but the stored L0 (kind=log) decides it first.
        self.assertEqual(rec["measures"][FA]["matched"], 2)
        self.assertEqual(rec["measures"][FA]["decided"], 1)

    def test_record_shape(self):
        for name in F.CANDIDATES:
            _, rec = admit(name)
            self.assertEqual(tuple(rec), M.RECORD_FIELDS)
            self.assertIn(rec["outcome"], M.OUTCOMES)
            self.assertIn(rec["reason"], M.REASONS)
            self.assertIs(type(rec["failed_probes"]), tuple)
            self.assertIs(type(rec["committed"]), bool)

    def test_precondition_parse(self):
        self.assertEqual(M.parse_precondition("a=b"), ("a", "b"))
        for bad in ("a", "=b", "a=", "a=b=c", "", None, 3):
            self.assertIsNone(M.parse_precondition(bad), bad)


class Expiry(unittest.TestCase):
    """A deadline declares on_expiry; expiry never commits or acts."""

    def test_expired_records_declared_outcome_and_never_commits(self):
        for value, const in (("hold", M.HOLD), ("escalate", M.ESCALATE),
                             ("deny", M.DENY)):
            store, rec = admit("good", deadline={"timeout_s": 3, "on_expiry": value,
                                                 "expired": True})
            self.assertEqual(rec["outcome"], M.EXPIRED)
            self.assertEqual(rec["reason"], M.EXPIRED)
            self.assertIs(rec["on_expiry"], const)
            self.assertFalse(rec["committed"])
            self.assertEqual(store.ids(), ("L0",))

    def test_on_expiry_is_module_constant_not_caller_object(self):
        caller = "".join(["ho", "ld"])
        _, rec = admit("good", deadline={"timeout_s": 3, "on_expiry": caller,
                                         "expired": True})
        self.assertIs(rec["on_expiry"], M.HOLD)

    def test_missing_on_expiry_is_config_error(self):
        for expired in (True, False):
            store, rec = admit("good", deadline={"timeout_s": 3, "expired": expired})
            self.assertEqual(rec["outcome"], M.CONFIG_ERROR)
            self.assertEqual(store.ids(), ("L0",))

    def test_on_expiry_values_are_closed(self):
        for value in ("commit", "dispatch", "refine", "HOLD", "", None,
                      SpoofStr("x"), RaisingObj()):
            store, rec = admit("good", deadline={"timeout_s": 3, "on_expiry": value,
                                                 "expired": True})
            self.assertEqual(rec["outcome"], M.CONFIG_ERROR, repr(type(value)))
            self.assertEqual(store.ids(), ("L0",))

    def test_deadline_field_checks(self):
        bad = [{"on_expiry": "hold"},
               {"timeout_s": 0, "on_expiry": "hold"},
               {"timeout_s": True, "on_expiry": "hold"},
               {"timeout_s": SubInt(3), "on_expiry": "hold"},
               {"timeout_s": 3, "on_expiry": "hold", "expired": 1},
               {"timeout_s": 3, "on_expiry": "hold", "later": True},
               SubDict({"timeout_s": 3, "on_expiry": "hold"}),
               [("timeout_s", 3)]]
        for deadline in bad:
            store, rec = admit("good", deadline=deadline)
            self.assertEqual(rec["outcome"], M.CONFIG_ERROR, deadline)
            self.assertEqual(store.ids(), ("L0",))

    def test_unexpired_deadline_runs_probes_and_records_on_expiry(self):
        store, rec = admit("good", deadline={"timeout_s": 3, "on_expiry": "deny",
                                             "expired": False})
        self.assertEqual(rec["outcome"], M.COMMIT)
        self.assertIs(rec["on_expiry"], M.DENY)
        store, rec = admit("good", deadline={"timeout_s": 3, "on_expiry": "escalate"})
        self.assertEqual(rec["outcome"], M.COMMIT)

    def test_no_deadline_records_none(self):
        _, rec = admit("good")
        self.assertIsNone(rec["on_expiry"])


class InputChecks(unittest.TestCase):
    """Exact type checks; admit() never raises; config_error writes nothing."""

    def assertConfigError(self, store, req, label=None):
        before = store.lessons()
        rec = M.admit(store, req)
        self.assertEqual(rec["outcome"], M.CONFIG_ERROR, label)
        self.assertEqual(rec["reason"], M.CONFIG_ERROR, label)
        self.assertFalse(rec["committed"])
        self.assertEqual(store.lessons(), before, label)
        return rec

    def test_non_mapping_requests(self):
        for req in (None, [], "x", 5, SubDict(F.request("good")), RaisingObj()):
            self.assertConfigError(F.seed_store(), req, repr(type(req)))

    def test_store_must_be_exact_type(self):
        for store in (None, {}, [], sub_store([F.SEED_LESSON])):
            rec = M.admit(store, F.request("good"))
            self.assertEqual(rec["outcome"], M.CONFIG_ERROR)
        sub = sub_store([F.SEED_LESSON])
        M.admit(sub, F.request("good"))
        self.assertEqual(sub.ids(), ("L0",))

    def test_unknown_and_missing_request_fields(self):
        req = F.request("good")
        req["note"] = "x"
        self.assertConfigError(F.seed_store(), req)
        for key in M.REQUEST_FIELDS:
            req = F.request("good")
            del req[key]
            self.assertConfigError(F.seed_store(), req, key)

    def test_hypothesis_fields(self):
        for key in M.HYPOTHESIS_FIELDS:
            for bad in (None, "", 3, SpoofStr("x"), RaisingStr("x"), RaisingObj()):
                req = F.request("good")
                req["hypothesis"][key] = bad
                self.assertConfigError(F.seed_store(), req, (key, repr(type(bad))))
            req = F.request("good")
            del req["hypothesis"][key]
            self.assertConfigError(F.seed_store(), req, key)
        req = F.request("good")
        req["hypothesis"]["extra"] = "x"
        self.assertConfigError(F.seed_store(), req)
        req = F.request("good")
        req["hypothesis"] = SubDict(req["hypothesis"])
        self.assertConfigError(F.seed_store(), req)

    def test_spoof_keys_rejected(self):
        req = F.request("good")
        req[SpoofStr("deadline")] = {"timeout_s": 3, "on_expiry": "hold"}
        self.assertConfigError(F.seed_store(), req)
        req = F.request("good")
        hyp = req["hypothesis"]
        hyp[SpoofStr("note")] = "x"
        self.assertConfigError(F.seed_store(), req)
        req = F.request("good")
        tasks = req["probes"].pop(FA)
        req["probes"][SpoofStr(FA + "_")] = tasks
        self.assertConfigError(F.seed_store(), req)

    def test_bad_precondition_and_verifier(self):
        for pre in ("size", "=large", "size=", "size=large=x"):
            req = F.request("good")
            req["hypothesis"]["precondition"] = pre
            self.assertConfigError(F.seed_store(), req, pre)
        for ver in ("always_true", SpoofStr(M.ACTION_MATCHES_EXPECTED)):
            req = F.request("good")
            req["hypothesis"]["verifier"] = ver
            self.assertConfigError(F.seed_store(), req, ver)

    def test_duplicate_id_rejected(self):
        req = F.request("good")
        req["hypothesis"]["id"] = "L0"
        self.assertConfigError(F.seed_store(), req)
        self.assertIsNotNone(M.validate(F.seed_store(), req))
        store, _ = admit("good")
        self.assertConfigError(store, F.request("good"))
        self.assertIsNotNone(M.validate(store, F.request("good")))
        self.assertEqual(store.ids(), ("L0", "H-good"))

    def test_local_success_exact_bool(self):
        for bad in (1, 0, "yes", None, RaisingObj()):
            self.assertConfigError(F.seed_store(), F.request("good", local_success=bad))

    def test_probe_containers(self):
        for bad in (None, (), SubDict(), [1]):
            req = F.request("good")
            req["probes"] = bad
            self.assertConfigError(F.seed_store(), req, repr(bad))
        req = F.request("good")
        req["probes"]["other_probe"] = []
        self.assertConfigError(F.seed_store(), req)
        for bad in (None, (), SubList(F.archive()), "tasks"):
            req = F.request("good")
            req["probes"][AR] = bad
            self.assertConfigError(F.seed_store(), req, repr(bad))

    def test_task_checks(self):
        base = F.task("t-x", "csv", "large")
        mutations = [
            lambda t: t.update(note="x"),
            lambda t: t.pop("expected_action"),
            lambda t: t.update(id=""),
            lambda t: t.update(id=SpoofStr("t")),
            lambda t: t.update(features=SubDict(t["features"])),
            lambda t: t.update(features={"kind": 3}),
            lambda t: t.update(features={"": "csv"}),
            lambda t: t.update(features={"kind": SpoofStr("csv")}),
            lambda t: t.update(default_action=None),
            lambda t: t.update(expected_action=RaisingStr("x")),
        ]
        for i, mutate in enumerate(mutations):
            t = copy.deepcopy(base)
            mutate(t)
            req = F.request("good")
            req["probes"][TT] = req["probes"][TT] + [t]
            self.assertConfigError(F.seed_store(), req, i)
        req = F.request("good")
        req["probes"][TT] = req["probes"][TT] + [SubDict(base)]
        self.assertConfigError(F.seed_store(), req)

    def test_hypothesis_id_echo_only_exact_str(self):
        req = F.request("good")
        req["hypothesis"]["id"] = SpoofStr("H-good")
        rec = M.admit(F.seed_store(), req)
        self.assertIsNone(rec["hypothesis_id"])
        _, rec = admit("false")
        self.assertEqual(rec["hypothesis_id"], "H-false")
        self.assertIs(type(rec["hypothesis_id"]), str)

    def test_never_raises_on_internal_error(self):
        store = F.seed_store()
        store._lessons.append(None)  # corrupt internal state
        rec = M.admit(store, F.request("good"))
        self.assertEqual(rec["outcome"], M.CONFIG_ERROR)
        self.assertIsNone(rec["hypothesis_id"])


class Fixtures(unittest.TestCase):

    def test_task_ids_unique(self):
        ids = [t["id"] for t in F.all_tasks()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_labels_follow_truth(self):
        for t in F.all_tasks():
            self.assertEqual(t["expected_action"], F.truth(t["features"]), t["id"])
            self.assertEqual(t["default_action"], F.DEFAULT_ACTION)
            self.assertIsNone(M.validate_task(t), t["id"])

    def test_seed_store_solves_archive(self):
        store = F.seed_store()
        for t in F.archive():
            self.assertEqual(store.act(t), t["expected_action"], t["id"])

    def test_archive_is_shared(self):
        names = list(F.CANDIDATES)
        first = F.request(names[0])["probes"][AR]
        for name in names[1:]:
            self.assertEqual(F.request(name)["probes"][AR], first)

    def test_falsification_sets_not_vacuous(self):
        for name, (hyp, _, falsification) in F.CANDIDATES.items():
            key, value = M.parse_precondition(hyp["precondition"])
            self.assertTrue(any(t["features"].get(key) == value for t in falsification), name)

    def test_every_candidate_valid_and_locally_successful(self):
        for name in F.CANDIDATES:
            req = F.request(name)
            self.assertIs(req["local_success"], True)
            self.assertIsNone(M.validate(F.seed_store(), req), name)

    def test_later_task_not_in_any_probe(self):
        probe_ids = set()
        for name in F.CANDIDATES:
            for tasks in F.request(name)["probes"].values():
                probe_ids.update(t["id"] for t in tasks)
        self.assertNotIn(F.LATER_TASK["id"], probe_ids)

    def test_thresholds_declared(self):
        self.assertEqual(set(F.THRESHOLDS), set(M.THRESHOLD_FIELDS))
        for v in F.THRESHOLDS.values():
            self.assertIs(type(v), int)


class Docs(unittest.TestCase):

    def test_readme_credits_and_scope(self):
        text = flat("README.md")
        ev = json.loads(read("paper_evidence.json"))
        self.assertIn(ev["title"], text)
        for author in ev["authors"]:
            self.assertIn(author, text)
        for needle in ("no clock", "single dict.setdefault",
                       "already decided by a stored lesson",
                       "http://arxiv.org/licenses/nonexclusive-distrib/1.0/",
                       "https://arxiv.org/abs/2611.14326", "method sketch",
                       "not law", "synthetic", "UNVERIFIED",
                       "w18-skill-assurance", "medium overlap",
                       "w20-evidence-linked-memory", "w19-engram-release",
                       "w17-memory-scope", "Refine choice"):
            self.assertIn(needle, text, needle)

    def test_notice_credits(self):
        text = flat("NOTICE")
        ev = json.loads(read("paper_evidence.json"))
        self.assertIn(ev["title"], text)
        self.assertIn("nonexclusive-distrib/1.0/", text)
        for author in ev["authors"]:
            self.assertIn(author, text)

    def test_paper_numbers_only_in_paper_evidence(self):
        ev = json.loads(read("paper_evidence.json"))
        figures = ev["claims"][0]["figures"]
        needles = set()
        for key, value in figures.items():
            needles.add(repr(value))
            if key.endswith("_pct"):
                needles.add(repr(value) + "%")
        needles.discard(repr(figures["falsification_failures_pct"]))  # bare form too generic; the percent form is still scanned
        for name in DOCS + CODE + ("mutants.py",):
            text = read(name)
            for needle in needles:
                self.assertNotIn(needle, text, (name, needle))

    def test_paper_evidence_unverified(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["version"], "v1")
        for item in ev["claims"] + ev["method_quotes"]:
            self.assertEqual(item["status"], "UNVERIFIED")
        self.assertTrue(ev["code"].startswith("UNVERIFIED"))

    def test_quotes_exact_in_source_copy(self):
        ev = json.loads(read("paper_evidence.json"))
        src = ev["abstract_copy"]
        if not SOURCES:
            self.skipTest("W21MA_SOURCES not set")
        path = os.path.join(SOURCES, src["file"])
        if not os.path.exists(path):
            self.skipTest("abstract copy not present")
        with open(path, "rb") as fh:
            data = fh.read()
        self.assertEqual(len(data), src["bytes"])
        self.assertEqual(hashlib.sha256(data).hexdigest(), src["sha256"])
        text = data.decode("utf-8")
        for item in ev["claims"] + ev["method_quotes"]:
            self.assertEqual(text.count(item["quote"]), 1, item["quote"][:40])

    def test_store_is_in_memory_only(self):
        text = read("memory_admission.py")
        self.assertNotIn("import", text.replace("imported", ""))
        for needle in ("sql" + "ite", "open(", "pick" + "le", "shel" + "ve",
                       "sock" + "et", "json.dump", "os."):
            self.assertNotIn(needle, text, needle)

    def test_word_and_path_hygiene(self):
        banned = ["al" + "low", "ke" + "ep", "cloud" + "agent", "sm" + "ith",
                  "che" + "cker"]
        paths = ["/work" + "space", "/t" + "mp"]
        markers = ["<" * 7, ">" * 7, "=" * 7 + "\n"]
        names = list(OWN)
        day = os.path.join("_day", "README.md")
        if os.path.exists(os.path.join(HERE, day)):
            names.append(day)
        for name in names:
            text = read(name)
            low = text.lower()
            for word in banned:
                self.assertNotIn(word, low, (name, word))
            for p in paths:
                self.assertNotIn(p, text, (name, p))
            for m in markers:
                self.assertNotIn(m, text, (name, m))

    def test_day_index_footer(self):
        footer = "Do not merge experiment PRs without Ork review."
        path = day_readme()
        self.assertTrue(os.path.isfile(path), path)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(text.count(footer), 1)
        self.assertEqual(text.rstrip("\n").splitlines()[-1], footer)
        self.assertIn("- [w21-memory-admission](w21-memory-admission/):", text)
        for m in ("<" * 7, ">" * 7):
            self.assertNotIn(m, text)


class FixRound(unittest.TestCase):
    """Regression tests for the PR #121 verdict findings F1, F2, F3, F5, F6."""

    def test_f1_shadowed_falsification_is_vacuous(self):
        # Verifier repro: a correct stored lesson L1 (size=small) decides the
        # only falsification task, so H-false never runs on it.
        store = M.MemoryStore([F.SEED_LESSON, L1_LESSON])
        req = F.request("false")
        req["probes"][FA] = [F.task("fa-csv-small", "csv", "small")]
        rec = M.admit(store, req)
        self.assertEqual(rec["outcome"], M.ON_UNMEASURED)
        self.assertEqual(rec["reason"], M.PROBE_VACUOUS)
        self.assertEqual(rec["failed_probes"], (FA,))
        self.assertEqual(rec["measures"][FA]["matched"], 1)
        self.assertEqual(rec["measures"][FA]["decided"], 0)
        self.assertFalse(rec["committed"])
        self.assertEqual(store.ids(), ("L0", "L1"))
        later = F.task("later-csv-medium", "csv", "medium")
        self.assertEqual(store.act(later), later["expected_action"])

    def test_f1_good_with_only_shadowed_falsification_is_vacuous(self):
        req = F.request("good")
        req["probes"][FA] = [F.task("fa-log-large", "log", "large")]
        store = F.seed_store()
        rec = M.admit(store, req)
        self.assertEqual(rec["outcome"], M.ON_UNMEASURED)
        self.assertEqual(rec["reason"], M.PROBE_VACUOUS)
        self.assertEqual(store.ids(), ("L0",))

    def test_f1_one_decided_task_is_enough(self):
        store = M.MemoryStore([F.SEED_LESSON, L1_LESSON])
        req = F.request("false")
        req["probes"][FA] = [F.task("fa-csv-small", "csv", "small"),
                             F.task("fa-csv-large", "csv", "large")]
        rec = M.admit(store, req)
        self.assertEqual(rec["measures"][FA]["decided"], 1)
        self.assertNotEqual(rec["reason"], M.PROBE_VACUOUS)

    def test_f2_unsolved_archive_is_vacuous(self):
        bad = F.task("arc-json-small", "json", "small")
        bad["expected_action"] = "tail"
        store = F.seed_store()
        rec = M.admit(store, F.request("breaks_archive"))
        self.assertEqual(rec["outcome"], M.REJECT)
        req = F.request("breaks_archive")
        req["probes"][AR] = [bad]
        rec = M.admit(store, req)
        self.assertEqual(rec["outcome"], M.ON_UNMEASURED)
        self.assertEqual(rec["reason"], M.PROBE_VACUOUS)
        self.assertEqual(rec["failed_probes"], (AR,))
        self.assertEqual(rec["measures"][AR]["base_ok"], 0)
        self.assertEqual(store.ids(), ("L0",))
        real = F.archive()[0]
        self.assertEqual(store.act(real), real["expected_action"])

    def test_f1_non_last_stored_lesson_still_shadows(self):
        # L1 (size=small) is stored first, L0 last. A shadow check that
        # looked only at the last stored lesson would miss L1, treat
        # fa-csv-small as decided by H-false, and commit (temp_ok still
        # passes because L1 acts first on the temporary state).
        store = M.MemoryStore([L1_LESSON, F.SEED_LESSON])
        req = F.request("false")
        req["probes"][FA] = [F.task("fa-csv-small", "csv", "small")]
        rec = M.admit(store, req)
        self.assertEqual(rec["outcome"], M.ON_UNMEASURED)
        self.assertEqual(rec["reason"], M.PROBE_VACUOUS)
        self.assertEqual(rec["failed_probes"], (FA,))
        self.assertEqual(rec["measures"][FA]["matched"], 1)
        self.assertEqual(rec["measures"][FA]["decided"], 0)
        self.assertFalse(rec["committed"])
        self.assertEqual(store.ids(), ("L1", "L0"))

    def test_f2_archive_vacuity_uses_current_store(self):
        # Archive task json/large is unsolved by L0, but H-good (size=large)
        # would solve it. Vacuity must look at the current store (base_ok),
        # not the candidate's result (temp_ok); otherwise H-good would commit.
        store = F.seed_store()
        req = F.request("good")
        req["probes"][AR] = [F.task("arc-json-large", "json", "large")]
        rec = M.admit(store, req)
        self.assertEqual(rec["outcome"], M.ON_UNMEASURED)
        self.assertEqual(rec["reason"], M.PROBE_VACUOUS)
        self.assertEqual(rec["failed_probes"], (AR,))
        self.assertEqual(rec["measures"][AR]["base_ok"], 0)
        self.assertEqual(rec["measures"][AR]["temp_ok"], 1)
        self.assertFalse(rec["committed"])
        self.assertEqual(store.ids(), ("L0",))

    def test_f3_commit_rechecks_id(self):
        store, _ = admit("good")
        # A different lesson under the same id, which would commit on probes
        # alone (H-good now solves the large csv on base).
        req = F.request("narrow")
        req["hypothesis"]["id"] = "H-good"
        fresh = F.request("narrow")
        self.assertEqual(M.admit(copy.deepcopy(store), fresh)["outcome"], M.COMMIT)
        store.ids = lambda: ("L0",)  # hide H-good from the early check
        self.assertIsNone(M.validate(store, req))
        rec = M.admit(store, req)
        self.assertEqual(rec["outcome"], M.CONFIG_ERROR)
        self.assertFalse(rec["committed"])
        self.assertEqual(tuple(l[0] for l in store.lessons()), ("L0", "H-good"))

    def test_f3_concurrent_admits_commit_once(self):
        old = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)
        try:
            for _ in range(60):
                store = F.seed_store()
                threads = [threading.Thread(target=M.admit,
                                            args=(store, F.request("good")))
                           for _ in range(6)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                self.assertEqual(store.ids(), ("L0", "H-good"))
        finally:
            sys.setswitchinterval(old)

    def test_f5_no_id_echo_before_validation(self):
        class HashAs(str):
            def __hash__(self):
                return hash("id")

            def __eq__(self, other):
                return True

        req = F.request("good")
        hyp = req["hypothesis"]
        hyp.pop("id")
        hyp[HashAs("zz")] = "SPOOFED-ID"
        rec = M.admit(F.seed_store(), req)
        self.assertEqual(rec["outcome"], M.CONFIG_ERROR)
        self.assertIsNone(rec["hypothesis_id"])
        # A valid id with another defect is not echoed either.
        req = F.request("good", thresholds={"refine_min_gain_pct": 0,
                                            "refine_max_risk_pct": 0})
        rec = M.admit(F.seed_store(), req)
        self.assertEqual(rec["outcome"], M.CONFIG_ERROR)
        self.assertIsNone(rec["hypothesis_id"])

    def test_f6_seed_lessons_validated(self):
        bad = [dict(F.SEED_LESSON, behavior_change=["t", "a", "i", "l"]),
               dict(F.SEED_LESSON, precondition="kind"),
               dict(F.SEED_LESSON, verifier="always_true"),
               dict(F.SEED_LESSON, id=SpoofStr("L0")),
               dict(F.SEED_LESSON, extra="x"),
               SubDict(F.SEED_LESSON), None]
        for lesson in bad:
            with self.assertRaises(ValueError):
                M.MemoryStore([lesson])
        with self.assertRaises(ValueError):
            M.MemoryStore([F.SEED_LESSON, dict(F.SEED_LESSON)])
        self.assertEqual(M.MemoryStore([F.SEED_LESSON, L1_LESSON]).ids(), ("L0", "L1"))

    def test_f4_expiry_is_a_caller_flag(self):
        # No clock: timeout_s is validated but never compared with time.
        _, rec = admit("good", deadline={"timeout_s": 1, "on_expiry": "hold"})
        self.assertEqual(rec["outcome"], M.COMMIT)
        _, rec = admit("good", deadline={"timeout_s": 10 ** 9, "on_expiry": "hold",
                                         "expired": True})
        self.assertEqual(rec["outcome"], M.EXPIRED)


if __name__ == "__main__":
    unittest.main()
