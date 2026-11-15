"""Tests for the w21-unused-contradiction method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest -v
The source check reads the abstract copy named in paper_evidence.json from
the directory in $W21UC_SOURCES. There is no default: when the variable is
unset, or the file is absent there, that one check is skipped.
"""

import ast
import copy
import hashlib
import json
import os
import re
import unittest

import fixtures as F
import unused_contradiction as U

HERE = os.path.dirname(os.path.abspath(__file__))
DAY = "2026-11-12"
SOURCES = os.environ.get("W21UC_SOURCES")
CODE = ("unused_contradiction.py", "fixtures.py")
DOCS = ("README.md", "NOTICE")
ALL = DOCS + CODE + ("test_unused_contradiction.py", "paper_evidence.json", "mutants.py")
PERMIT = "al" + "low"
NOT_SUCCESS = (U.FAIL, U.ON_UNMEASURED, U.CONFIG_ERROR) + U.ON_EXPIRY_VALUES


def day_readme():
    """Path of the day README: ../README.md in the repo layout, else _day/README.md."""
    parent = os.path.dirname(HERE)
    repo = os.path.join(parent, "README.md")
    if os.path.basename(parent) == DAY and os.path.isfile(repo):
        return repo
    flat = os.path.join(HERE, "_day", "README.md")
    return flat if os.path.isfile(flat) else None


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def ep(steps, task_done=True, wait=None, eid="x"):
    return F.episode(eid, steps, task_done, wait)


def verdict(episode, policy=U.CONSUME):
    rec = U.decide(episode, policy)
    return rec["verdict"], rec["reason"]


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

    __hash__ = str.__hash__

    def __str__(self):
        raise RuntimeError("str")


class RaisingObj(object):
    def __eq__(self, other):
        raise RuntimeError("eq")

    def __hash__(self):
        raise RuntimeError("hash")


class SpoofDict(dict):
    pass


class SpoofList(list):
    pass


class SpoofInt(int):
    pass


class DoneWhen(unittest.TestCase):
    """(a)-(e) of the day sketch."""

    def test_a_unused_contradiction_cannot_close_success(self):
        e = F.DESIGN["a_unused"][0]
        self.assertEqual(verdict(e), (U.FAIL, U.UNUSED_CONTRADICTION))
        rec = U.decide(e)
        self.assertEqual(rec["unresolved"], (("e1", "b1", U.UNUSED_CONTRADICTION),))
        # the symptom-only baseline closes it as success: that is the gap
        self.assertEqual(verdict(e, U.SYMPTOM_ONLY), (U.SUCCESS, U.CONSUMED))

    def test_a_contradiction_against_an_act(self):
        e = ep([F.act("a1", "file"), F.evidence("e1", "a1")])
        self.assertEqual(verdict(e), (U.FAIL, U.UNUSED_CONTRADICTION))
        e = ep([F.act("a1", "file"), F.evidence("e1", "a1"), F.repair("r1", "file")])
        self.assertEqual(verdict(e), (U.SUCCESS, U.CONSUMED))

    def test_a_task_not_done_fails_regardless(self):
        e = ep(F.RESPONSES["repair"](), task_done=False)
        self.assertEqual(verdict(e), (U.FAIL, U.TASK_NOT_DONE))
        for policy in U.POLICIES:
            self.assertEqual(verdict(e, policy), (U.FAIL, U.TASK_NOT_DONE))

    def test_b_flag_without_repair_fails(self):
        e = F.DESIGN["b_flag_only"][0]
        self.assertEqual(verdict(e), (U.FAIL, U.FLAG_WITHOUT_REPAIR))
        self.assertEqual(U.decide(e)["unresolved"], (("e1", "b1", U.FLAG_WITHOUT_REPAIR),))
        # the flag-as-repair baseline counts it: that is the gap
        self.assertEqual(verdict(e, U.FLAG_AS_REPAIR), (U.SUCCESS, U.CONSUMED))

    def test_b_flag_before_evidence_is_not_a_response(self):
        e = ep(F.RESPONSES["flag_before_evidence"]())
        self.assertEqual(verdict(e), (U.FAIL, U.UNUSED_CONTRADICTION))
        self.assertEqual(verdict(e, U.FLAG_AS_REPAIR), (U.FAIL, U.UNUSED_CONTRADICTION))

    def test_b_flag_and_wrong_repair_still_fails(self):
        e = F.DESIGN["d_flag_and_wrong_repair"][0]
        self.assertEqual(verdict(e), (U.FAIL, U.FLAG_WITHOUT_REPAIR))
        self.assertEqual(U.decide(e)["ineffective_repairs"], ("r1",))

    def test_b_unused_outranks_flag(self):
        e = ep([F.belief("b1", "total"), F.act("a2", "route"), F.evidence("e1", "b1"),
                F.evidence("e2", "a2"), F.flag("f1", "a2")])
        self.assertEqual(verdict(e), (U.FAIL, U.UNUSED_CONTRADICTION))
        self.assertEqual(U.decide(e)["unresolved"], (("e1", "b1", U.UNUSED_CONTRADICTION),
                                                     ("e2", "a2", U.FLAG_WITHOUT_REPAIR)))

    def test_c_removing_repair_permits_completion(self):
        for name in ("c_repair", "c_two_repaired"):
            self.assertEqual(verdict(F.DESIGN[name][0]), (U.SUCCESS, U.CONSUMED), name)
        rec = U.decide(F.DESIGN["c_repair"][0])
        self.assertEqual((rec["unresolved"], rec["ineffective_repairs"]), ((), ()))
        self.assertEqual(verdict(ep(F.RESPONSES["flag_then_repair"]())), (U.SUCCESS, U.CONSUMED))
        self.assertEqual(verdict(F.DESIGN["c_other_state_after_repair"][0]), (U.SUCCESS, U.CONSUMED))

    def test_d_reassertion_after_repair_fails(self):
        # regression (PR #122 review F1): [b1 S, e1 -> b1, repair S, b3 S] used to close success
        e = ep([F.belief("b1", "S"), F.evidence("e1", "b1"), F.repair("r1", "S"), F.belief("b3", "S")])
        rec = U.decide(e)
        self.assertEqual((rec["verdict"], rec["reason"]), (U.FAIL, U.REASSERTED_AFTER_REPAIR))
        self.assertEqual(rec["unresolved"], (("e1", "b1", U.REASSERTED_AFTER_REPAIR),))
        self.assertEqual(rec["ineffective_repairs"], ())
        e = ep([F.belief("b1", "S"), F.evidence("e1", "b1"), F.repair("r1", "S"), F.act("a3", "S")])
        self.assertEqual(verdict(e), (U.FAIL, U.REASSERTED_AFTER_REPAIR))
        # a flag does not excuse a relapse, under either non-symptom policy
        e = ep([F.belief("b1", "S"), F.evidence("e1", "b1"), F.flag("f1", "b1"), F.repair("r1", "S"),
                F.belief("b3", "S")])
        self.assertEqual(verdict(e), (U.FAIL, U.REASSERTED_AFTER_REPAIR))
        self.assertEqual(verdict(e, U.FLAG_AS_REPAIR), (U.FAIL, U.REASSERTED_AFTER_REPAIR))
        self.assertEqual(verdict(e, U.SYMPTOM_ONLY), (U.SUCCESS, U.CONSUMED))
        for name in ("d_reasserted_after_repair", "d_reacted_after_repair"):
            self.assertEqual(verdict(F.DESIGN[name][0]), (U.FAIL, U.REASSERTED_AFTER_REPAIR), name)
        self.assertEqual(verdict(ep(F.RESPONSES["repair_then_reassert"]())),
                         (U.FAIL, U.REASSERTED_AFTER_REPAIR))

    def test_d_reassertion_ordering(self):
        # a re-assertion before the repair is an overwrite: the repair removes b3, not b1
        e = ep([F.belief("b1", "S"), F.evidence("e1", "b1"), F.belief("b3", "S"), F.repair("r1", "S")])
        self.assertEqual(verdict(e), (U.FAIL, U.UNUSED_CONTRADICTION))
        # unused outranks a relapse elsewhere; a relapse outranks a bare flag
        e = ep([F.belief("b1", "S"), F.act("a2", "T"), F.evidence("e1", "b1"), F.evidence("e2", "a2"),
                F.repair("r1", "S"), F.belief("b3", "S")])
        self.assertEqual(verdict(e), (U.FAIL, U.UNUSED_CONTRADICTION))
        e = ep([F.belief("b1", "S"), F.act("a2", "T"), F.evidence("e1", "b1"), F.evidence("e2", "a2"),
                F.flag("f1", "a2"), F.repair("r1", "S"), F.belief("b3", "S")])
        self.assertEqual(verdict(e), (U.FAIL, U.REASSERTED_AFTER_REPAIR))
        # two repairs of the same state after a relapse do not cure it
        e = ep([F.belief("b1", "S"), F.evidence("e1", "b1"), F.repair("r1", "S"), F.belief("b3", "S"),
                F.repair("r2", "S")])
        self.assertEqual(verdict(e), (U.FAIL, U.REASSERTED_AFTER_REPAIR))

    def test_d_superseded_holder_is_fail_closed(self):
        # review note F3: a label against an already superseded holder cannot be consumed
        self.assertEqual(verdict(F.DESIGN["d_superseded_holder"][0]), (U.FAIL, U.UNUSED_CONTRADICTION))

    def test_c_one_repair_consumes_two_pieces_of_evidence(self):
        e = ep([F.belief("b1", "total"), F.evidence("e1", "b1"), F.evidence("e2", "b1"),
                F.repair("r1", "total")])
        self.assertEqual(verdict(e), (U.SUCCESS, U.CONSUMED))

    def test_c_later_evidence_after_repair_needs_its_own_response(self):
        e = ep([F.belief("b1", "total"), F.evidence("e1", "b1"), F.repair("r1", "total"),
                F.evidence("e2", "b1")])
        self.assertEqual(verdict(e), (U.FAIL, U.UNUSED_CONTRADICTION))

    def test_d_repair_that_misses_the_state_fails(self):
        for name in ("d_other_state", "d_before_evidence", "d_after_overwrite", "d_one_of_two"):
            self.assertEqual(verdict(F.DESIGN[name][0]), (U.FAIL, U.UNUSED_CONTRADICTION), name)
        self.assertEqual(U.decide(F.DESIGN["d_other_state"][0])["ineffective_repairs"], ("r1",))
        self.assertEqual(U.decide(F.DESIGN["d_after_overwrite"][0])["ineffective_repairs"], ("r1",))

    def test_d_repair_of_already_removed_state(self):
        e = ep([F.belief("b1", "total"), F.evidence("e1", "b1"), F.repair("r1", "total"),
                F.repair("r2", "total")])
        rec = U.decide(e)
        self.assertEqual((rec["verdict"], rec["ineffective_repairs"]), (U.SUCCESS, ("r2",)))

    def test_e_unlabeled_evidence_is_on_unmeasured(self):
        e = F.DESIGN["e_unlabeled"][0]
        self.assertEqual(verdict(e), (U.ON_UNMEASURED, U.UNLABELED_EVIDENCE))
        self.assertEqual(U.decide(e)["unlabeled"], ("e1",))
        self.assertEqual(verdict(e, U.FLAG_AS_REPAIR), (U.ON_UNMEASURED, U.UNLABELED_EVIDENCE))

    def test_e_declared_neutral_label_is_success(self):
        self.assertEqual(verdict(F.DESIGN["neutral_only"][0]), (U.SUCCESS, U.CONSUMED))

    def test_e_labels_must_be_declared_fixtures(self):
        base = F.DESIGN["c_repair"][0]
        for value in ("inferred", "nli", "", None, True, SpoofStr("x")):
            e = copy.deepcopy(base)
            e["contradiction_labels"] = value
            self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR), repr(value))
        e = copy.deepcopy(base)
        del e["contradiction_labels"]
        self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR))

    def test_e_bad_contradiction_field_is_config_error(self):
        cases = [
            [F.belief("b1", "s"), F.evidence("e1", "zz")],          # unknown id
            [F.evidence("e1", "b1"), F.belief("b1", "s")],          # forward reference
            [F.belief("b1", "s"), F.evidence("e1", 1)],             # not a str
            [F.belief("b1", "s"), F.evidence("e1", ["b1"])],
            [F.belief("b1", "s"), F.evidence("e1", SpoofStr("b1"))],
            [F.belief("b1", "s"), F.flag("f1", "b1"), F.evidence("e1", "f1")],  # flag is no belief
            [F.belief("b1", "s"), dict(F.evidence("e1", "b1"), score=0.9)],
            [F.belief("b1", "s"), dict(F.unlabeled("e1"), contradiction="b1")],
            [dict(F.belief("b1", "s"), contradicts="b1")],
            [dict(F.belief("b1", "s"), origin="step 1")],
            [dict(F.belief("b1", "s"), phase="plan")],
        ]
        for steps in cases:
            self.assertEqual(verdict(ep(steps)), (U.CONFIG_ERROR, U.CONFIG_ERROR), repr(steps))

    def test_e_no_detector_and_no_localisation(self):
        self.assertEqual(U.detect_contradiction("x is 3", "x is 4"),
                         {"verdict": U.ON_UNMEASURED, "axis": U.CONTRADICTION_DETECTION})
        self.assertEqual(U.localise_origin(F.DESIGN["a_unused"][0])["verdict"], U.ON_UNMEASURED)
        rec = U.decide(F.DESIGN["c_repair"][0])
        self.assertIs(rec["unmeasured_axes"], U.UNMEASURED_AXES)
        self.assertEqual(set(U.UNMEASURED_AXES), {"contradiction_detection", "origin_localisation",
                                                  "phase_localisation"})

    def test_e_never_success_without_labels_anywhere_in_grid(self):
        for e in F.GRID:
            if any(s["kind"] == "evidence" and "contradicts" not in s for s in e["steps"]):
                self.assertIn(U.decide(e)["verdict"], NOT_SUCCESS, e["episode_id"])

    def test_e_no_model_network_or_process(self):
        stdlib = {"json", "sys", "os", "copy", "hashlib", "re", "ast", "unittest", "shutil",
                  "subprocess", "tempfile"}
        local = {"unused_contradiction", "fixtures"}
        for name, permitted in (("unused_contradiction.py", set()), ("fixtures.py", {"json", "sys"}),
                                ("test_unused_contradiction.py", stdlib),
                                ("mutants.py", stdlib)):
            tree = ast.parse(read(name))
            mods = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    mods.add((node.module or "").split(".")[0])
            self.assertLessEqual(mods - local, permitted, name)


class Expiry(unittest.TestCase):
    def wait(self, **kw):
        w = {"timeout_s": 30, "on_expiry": U.HOLD, "expired": False}
        w.update(kw)
        return w

    def test_expired_returns_declared_action_never_success(self):
        for action in U.ON_EXPIRY_VALUES:
            for name in sorted(F.DESIGN):
                e = copy.deepcopy(F.DESIGN[name][0])
                e["wait"] = self.wait(on_expiry=action, expired=True)
                for policy in U.POLICIES:
                    rec = U.decide(e, policy)
                    self.assertEqual((rec["verdict"], rec["reason"]), (action, U.EXPIRED))
                    self.assertIs(rec["verdict"], action)
                    self.assertIs(rec["on_expiry"], action)

    def test_expired_returns_module_constant_not_caller_object(self):
        for action in U.ON_EXPIRY_VALUES:
            caller = "".join(list(action))
            self.assertIsNot(caller, action)
            e = copy.deepcopy(F.DESIGN["c_repair"][0])
            e["wait"] = self.wait(on_expiry=caller, expired=True)
            rec = U.decide(e)
            self.assertIs(rec["verdict"], action)
            self.assertIs(rec["on_expiry"], action)
            e["wait"] = self.wait(on_expiry=caller, expired=False)
            self.assertIs(U.decide(e)["on_expiry"], action)

    def test_expired_records_prior(self):
        e = copy.deepcopy(F.DESIGN["c_repair"][0])
        e["wait"] = self.wait(on_expiry=U.DENY, expired=True)
        rec = U.decide(e)
        self.assertEqual((rec["prior_verdict"], rec["prior_reason"]), (U.SUCCESS, U.CONSUMED))
        e = copy.deepcopy(F.DESIGN["b_flag_only"][0])
        e["wait"] = self.wait(on_expiry=U.ESCALATE, expired=True)
        rec = U.decide(e)
        self.assertEqual((rec["verdict"], rec["prior_verdict"], rec["prior_reason"]),
                         (U.ESCALATE, U.FAIL, U.FLAG_WITHOUT_REPAIR))

    def test_unexpired_wait_is_recorded_and_judged(self):
        e = copy.deepcopy(F.DESIGN["c_repair"][0])
        e["wait"] = self.wait(on_expiry=U.ESCALATE)
        rec = U.decide(e)
        self.assertEqual((rec["verdict"], rec["on_expiry"], rec["prior_verdict"]),
                         (U.SUCCESS, U.ESCALATE, None))
        e["wait"] = self.wait(on_expiry=U.HOLD)
        self.assertEqual(U.decide(F.DESIGN["a_unused"][0])["verdict"], U.FAIL)

    def test_missing_or_bad_on_expiry_is_config_error(self):
        e = copy.deepcopy(F.DESIGN["c_repair"][0])
        e["wait"] = {"timeout_s": 30, "expired": True}
        self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR))
        e["wait"] = {"timeout_s": 30, "expired": False}
        self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR))
        for bad in ("success", "dispatch", "hold", "", None, SpoofStr("HOLD"), U.SUCCESS):
            e["wait"] = self.wait(on_expiry=bad, expired=True)
            self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR), repr(bad))

    def test_bad_wait_fields_are_config_error(self):
        e = copy.deepcopy(F.DESIGN["c_repair"][0])
        for w in (self.wait(timeout_s=0), self.wait(timeout_s=-1), self.wait(timeout_s=True),
                  self.wait(timeout_s=1.5), self.wait(timeout_s=SpoofInt(5)),
                  self.wait(expired=1), self.wait(expired=None), self.wait(extra=1),
                  {"on_expiry": U.HOLD, "expired": False}, {"timeout_s": 5, "on_expiry": U.HOLD},
                  SpoofDict(self.wait()), [], None):
            e["wait"] = w
            self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR), repr(w))


class ExactTypes(unittest.TestCase):
    def test_policy_exact_and_known(self):
        e = F.DESIGN["c_repair"][0]
        for bad in ("", "consume", SpoofStr(U.CONSUME), None, 1):
            rec = U.decide(e, bad)
            self.assertEqual((rec["verdict"], rec["policy"]), (U.CONFIG_ERROR, U.INVALID_POLICY))
        for policy in U.POLICIES:
            self.assertIs(U.decide(e, "".join(policy))["policy"], policy)

    def test_spoofed_containers(self):
        base = F.DESIGN["c_repair"][0]
        self.assertEqual(verdict(SpoofDict(base)), (U.CONFIG_ERROR, U.CONFIG_ERROR))
        e = copy.deepcopy(base)
        e["steps"] = SpoofList(e["steps"])
        self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR))
        e["steps"] = tuple(base["steps"])
        self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR))
        e = copy.deepcopy(base)
        e["steps"][0] = SpoofDict(e["steps"][0])
        self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR))

    def test_spoofed_fields(self):
        base = F.DESIGN["c_repair"][0]
        for field in ("kind", "id", "state"):
            for i in range(len(base["steps"])):
                if field not in base["steps"][i]:
                    continue
                e = copy.deepcopy(base)
                e["steps"][i][field] = SpoofStr(e["steps"][i][field])
                self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR), (field, i))
        e = copy.deepcopy(base)
        e["episode_id"] = SpoofStr("x")
        self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR))
        e = copy.deepcopy(base)
        e["task_done"] = 1
        self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR))
        e = copy.deepcopy(F.DESIGN["b_flag_only"][0])
        e["steps"][3]["target"] = SpoofStr("b1")
        self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR))
        e = copy.deepcopy(base)
        e[SpoofStr("steps")] = e.pop("steps")
        self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR))

    def test_shape_errors(self):
        good = F.DESIGN["c_repair"][0]
        bad = [None, [], "x", {}, dict(good, steps=[]), dict(good, extra=1), dict(good, episode_id=""),
               dict(good, steps=[F.belief("b1", "s"), F.belief("b1", "t")]),
               dict(good, steps=[F.belief("b1", "")]), dict(good, steps=[{"kind": "note", "id": "n"}]),
               dict(good, steps=[{"id": "n"}]), dict(good, steps=[F.repair("r1", "never")]),
               dict(good, steps=[F.belief("b1", "s"), F.flag("f1", "zz")]),
               dict(good, steps=[F.belief("b1", "s"), {"kind": "flag", "id": "f1"}]),
               dict(good, steps=[{"kind": "belief", "id": "b1"}]),
               dict(good, steps=[F.belief("", "s")]), dict(good, steps=[F.belief(3, "s")]),
               dict(good, steps=[{1: "x", "kind": "belief", "id": "b", "state": "s"}]),
               dict(good, steps=["belief"])]
        for e in bad:
            self.assertEqual(verdict(e), (U.CONFIG_ERROR, U.CONFIG_ERROR), repr(e))
        self.assertIsNone(U.validate(good))

    def test_raising_inputs_never_raise(self):
        base = F.DESIGN["c_repair"][0]
        weird = [RaisingStr("x")]
        e1 = copy.deepcopy(base)
        e1["episode_id"] = RaisingStr("x")
        e2 = copy.deepcopy(base)
        e2["steps"][0]["state"] = RaisingStr("total")
        e3 = copy.deepcopy(base)
        e3[RaisingStr("k")] = 1
        e4 = copy.deepcopy(base)
        e4["steps"][2]["contradicts"] = RaisingObj()
        e5 = copy.deepcopy(base)
        e5["wait"] = {"timeout_s": 5, "on_expiry": RaisingObj(), "expired": True}
        e6 = copy.deepcopy(base)
        e6["steps"][0]["kind"] = RaisingObj()
        for e in weird + [e1, e2, e3, e4, e5, e6, RaisingObj()]:
            for policy in U.POLICIES + (RaisingStr("p"), RaisingObj()):
                rec = U.decide(e, policy)
                self.assertEqual(rec["verdict"], U.CONFIG_ERROR)

    def test_validate_never_raises_and_names_the_error(self):
        base = F.DESIGN["c_repair"][0]
        e1 = copy.deepcopy(base)
        e1["steps"][0] = {RaisingStr("kind"): "belief", "id": "b1", "state": "total"}
        e2 = copy.deepcopy(base)
        e2["wait"] = {"timeout_s": 30, "expired": True}
        e3 = copy.deepcopy(base)
        e3["wait"] = {RaisingStr("timeout_s"): 30, "on_expiry": U.HOLD, "expired": True}
        e4 = copy.deepcopy(base)
        e4[RaisingStr("steps")] = e4.pop("steps")
        for e in (e1, e2, e3, e4, RaisingObj(), None):
            err = U.validate(e)
            self.assertIs(type(err), str)
        self.assertIn("on_expiry", U.validate(e2))

    def test_summarise_never_raises(self):
        for bad in (None, RaisingObj(), tuple(F.GRID), 3):
            counts = U.summarise(bad)
            self.assertEqual(counts[U.CONFIG_ERROR], 1)
            self.assertEqual(sum(counts.values()), 1)
        counts = U.summarise([None, RaisingObj()], RaisingObj())
        self.assertEqual(counts[U.CONFIG_ERROR], 2)

    def test_internal_error_fails_closed(self):
        saved = U._analyse

        def boom(episode):
            raise RuntimeError("boom")
        U._analyse = boom
        try:
            rec = U.decide(F.DESIGN["c_repair"][0])
        finally:
            U._analyse = saved
        self.assertEqual((rec["verdict"], rec["reason"], rec["policy"]),
                         (U.CONFIG_ERROR, U.CONFIG_ERROR, U.CONSUME))

    def test_records_are_clean(self):
        consts = set(U.VERDICTS + U.REASONS + U.POLICIES + (U.INVALID_POLICY,))
        cases = [F.DESIGN[n][0] for n in sorted(F.DESIGN)] + list(F.GRID) + [None, {}]
        for e in cases:
            for policy in U.POLICIES:
                rec = U.decide(e, policy)
                self.assertEqual(tuple(rec), U.RECORD_FIELDS)
                for key in ("policy", "verdict", "reason"):
                    self.assertIn(rec[key], consts)
                for key in ("prior_verdict", "prior_reason", "on_expiry"):
                    self.assertTrue(rec[key] is None or rec[key] in consts)
                self.assertTrue(rec["episode_id"] is None or type(rec["episode_id"]) is str)
                for key in ("unresolved", "ineffective_repairs", "unlabeled"):
                    self.assertIs(type(rec[key]), tuple)
                for item in rec["unresolved"]:
                    self.assertEqual([type(x) for x in item], [str, str, str])
                    self.assertIn(item[2], (U.UNUSED_CONTRADICTION, U.FLAG_WITHOUT_REPAIR,
                                            U.REASSERTED_AFTER_REPAIR))

    def test_decide_does_not_mutate_input(self):
        e = copy.deepcopy(F.DESIGN["d_after_overwrite"][0])
        before = copy.deepcopy(e)
        U.decide(e)
        self.assertEqual(e, before)


class Fixtures(unittest.TestCase):
    def test_all_cases_match_tables(self):
        lines = []
        self.assertEqual(F.check(out=lines.append), 0, "\n".join(lines))

    def test_grid_shape(self):
        self.assertEqual(len(F.GRID), 36)
        self.assertEqual(len({e["episode_id"] for e in F.GRID}), 36)
        self.assertEqual(set(F.STATUS), set(F.RESPONSES))
        self.assertEqual(sorted(set(F.STATUS.values())), ["flagged", "reasserted", "repaired", "unused"])
        for e in F.GRID:
            self.assertIsNone(U.validate(e), e["episode_id"])
            self.assertEqual(e["contradiction_labels"], "declared_fixture")

    def test_design_fixtures_have_their_shape(self):
        def idx(steps, kind, **kw):
            return [i for i, st in enumerate(steps)
                    if st["kind"] == kind and all(st.get(k) == v for k, v in kw.items())]

        def contradicted_state(steps):
            target = [st["contradicts"] for st in steps if st["kind"] == "evidence"][0]
            return [st["state"] for st in steps if st["id"] == target][0]

        s = F.DESIGN["a_unused"][0]["steps"]
        self.assertEqual((idx(s, "flag"), idx(s, "repair")), ([], []))
        self.assertTrue(idx(s, "evidence", contradicts="b1"))
        s = F.DESIGN["b_flag_only"][0]["steps"]
        self.assertEqual(idx(s, "repair"), [])
        self.assertGreater(idx(s, "flag", target="b1")[0], idx(s, "evidence", contradicts="b1")[0])
        s = F.DESIGN["d_other_state"][0]["steps"]
        r = idx(s, "repair")
        self.assertEqual(len(r), 1)
        self.assertNotEqual(s[r[0]]["state"], contradicted_state(s))
        self.assertGreater(r[0], idx(s, "evidence", contradicts="b1")[0])
        s = F.DESIGN["d_before_evidence"][0]["steps"]
        r = idx(s, "repair", state="total")
        self.assertEqual(len(r), 1)
        self.assertLess(r[0], idx(s, "evidence", contradicts="b1")[0])
        s = F.DESIGN["d_after_overwrite"][0]["steps"]
        e, r = idx(s, "evidence", contradicts="b1")[0], idx(s, "repair", state="total")[0]
        self.assertTrue([i for i in idx(s, "belief", state="total") if e < i < r])
        s = F.DESIGN["c_repair"][0]["steps"]
        self.assertGreater(idx(s, "repair", state=contradicted_state(s))[0],
                           idx(s, "evidence", contradicts="b1")[0])
        s = F.DESIGN["c_two_repaired"][0]["steps"]
        self.assertEqual(len(idx(s, "repair")), 2)
        self.assertEqual(len([x for x in s if x["kind"] == "evidence" and x["contradicts"]]), 2)
        s = F.DESIGN["neutral_only"][0]["steps"]
        self.assertEqual(idx(s, "evidence", contradicts=None), [1])
        self.assertIn("contradicts", s[1])
        s = F.DESIGN["e_unlabeled"][0]["steps"]
        self.assertNotIn("contradicts", s[1])
        for name, shape in (("flag_before_evidence", ("flag", "evidence")),
                            ("flag", ("evidence", "flag")),
                            ("repair_other_state", ("evidence", "repair"))):
            kinds = [st["kind"] for st in F.RESPONSES[name]()]
            self.assertLess(kinds.index(shape[0]), kinds.index(shape[1]), name)

    def test_design_expectations_cover_done_when(self):
        got = {F.DESIGN[n][1] for n in F.DESIGN}
        for want in ((U.FAIL, U.UNUSED_CONTRADICTION), (U.FAIL, U.FLAG_WITHOUT_REPAIR),
                     (U.FAIL, U.REASSERTED_AFTER_REPAIR),
                     (U.SUCCESS, U.CONSUMED), (U.ON_UNMEASURED, U.UNLABELED_EVIDENCE)):
            self.assertIn(want, got)

    def test_measure(self):
        rows = {r["policy"]: r for r in F.measure()}
        self.assertEqual(rows[U.CONSUME]["success"], 2)
        self.assertEqual(rows[U.CONSUME]["success_over_gate"], 0)
        self.assertEqual(rows[U.SYMPTOM_ONLY]["success"], 18)
        self.assertEqual(rows[U.SYMPTOM_ONLY]["success_over_gate"], 16)
        self.assertEqual(rows[U.FLAG_AS_REPAIR]["success"], 3)
        self.assertEqual(rows[U.FLAG_AS_REPAIR]["success_over_gate"], 1)
        self.assertEqual(F.measure(), F.measure())

    def test_summarise(self):
        counts = U.summarise(list(F.GRID))
        self.assertEqual(counts[U.SUCCESS], 2)
        self.assertEqual(sum(counts.values()), 36)
        self.assertEqual(counts[U.FAIL], 18 + 14)
        self.assertEqual(counts[U.ON_UNMEASURED], 2)


class PaperEvidence(unittest.TestCase):
    # built by concatenation so the figures never appear in this file
    FIGURES = tuple(a + b for a, b in (("72", "%"), ("88", "%"), ("31", "%"), ("35 of ", "95"),
                                       ("45", "%")))

    def setUp(self):
        self.ev = json.loads(read("paper_evidence.json"))

    def test_metadata(self):
        p = self.ev["paper"]
        self.assertEqual(p["arxiv_id"], "2611.13254")
        self.assertEqual(p["version"], "v1")
        self.assertTrue(p["title"].startswith("Dependable Long-Horizon LLM Agents: "))
        self.assertEqual(p["authors"], ["Shaohuang Wang", "Jinghao Wen", "Xulei Zhang", "Xun Jiao"])
        self.assertEqual(p["licence_url"], "http://arxiv.org/licenses/nonexclusive-distrib/1.0/")
        self.assertIn("UNVERIFIED", p["code"])

    def test_figures_unverified_and_only_here(self):
        claims = self.ev["empirical_claims"]
        self.assertEqual(claims["status"], "UNVERIFIED")
        figs = [f for c in claims["claims"] for f in c["figures"]]
        self.assertEqual(sorted(figs), sorted(self.FIGURES))
        for c in claims["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")
            for f in c["figures"]:
                self.assertIn(f, c["quote"])
            self.assertEqual(hashlib.sha256(c["quote"].encode("utf-8")).hexdigest(), c["span_sha256"])
            self.assertEqual(len(c["quote"]), c["length"])
        for name in ALL:
            if name == "paper_evidence.json":
                continue
            text = read(name)
            for f in self.FIGURES:
                self.assertNotIn(f, text, (name, f))

    def test_quotes_are_exact_abstract_substrings(self):
        src = self.ev["source"]
        if not SOURCES:
            self.skipTest("W21UC_SOURCES not set")
        path = os.path.join(SOURCES, src["file"])
        if not os.path.isfile(path):
            self.skipTest("abstract copy not present")
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        self.assertEqual(hashlib.sha256(raw.encode("utf-8")).hexdigest(), src["sha256"])
        abstract = raw[len("Abstract:"):].strip() if raw.startswith("Abstract:") else raw.strip()
        self.assertEqual(hashlib.sha256(abstract.encode("utf-8")).hexdigest(), src["abstract_sha256"])
        for c in self.ev["empirical_claims"]["claims"]:
            off = c["offset_in_abstract"]
            self.assertEqual(abstract[off:off + c["length"]], c["quote"], c["id"])


class Readme(unittest.TestCase):
    def test_readme_scope_and_credit(self):
        text = read("README.md")
        self.assertIn("Dependable Long-Horizon LLM Agents: A Trajectory-Centered Empirical Study of "
                      "Where Errors Enter and Which Controls Reach Them", " ".join(text.split()))
        for s in ("Shaohuang Wang", "Jinghao Wen", "Xulei Zhang", "Xun Jiao",
                  "http://arxiv.org/licenses/nonexclusive-distrib/1.0/", "method sketch", "not law",
                  "w20-fidelity-audit", "w16-fail-signatures", "w20-evidence-linked-memory",
                  "on_unmeasured", "UNVERIFIED", "declared fixture"):
            self.assertIn(s, text, s)


class Hygiene(unittest.TestCase):
    # sha256 of each lowercase banned word; the words are not written here.
    BANNED_DIGESTS = (
        "410083735735a10e658a19edd1704e606c9dd112e225825b63fafeded766c8b9",
        "6ca7ea2feefc88ecb5ed6356ed963f47dc9137f82526fdd25d618ea626d0803f",
        "36c1852b63947092f69e46964f3a7400e49d5749741af087f444f458e72b27c9",
        "6627835f988e2c5e50533d491163072d3f4f41f5c8b04630150debb3722ca2dd",
        "d2d2328e3359f3de3515871090d1316cbcdc5383204c204f9390788c3ef8618f",
    )

    def banned(self):
        return frozenset(self.BANNED_DIGESTS)

    BANNED_LENGTHS = (4, 5, 7, 10)

    def test_banned_words_absent(self):
        for name in ALL:
            for word in re.findall(r"[a-z]+", read(name).lower()):
                for n in self.BANNED_LENGTHS:
                    for i in range(len(word) - n + 1):
                        digest = hashlib.sha256(word[i:i + n].encode("ascii")).hexdigest()
                        self.assertNotIn(digest, self.banned(), (name, word))

    def test_banned_digest_scan_works(self):
        probe = "zzqprobezz"
        digest = hashlib.sha256(b"qprobe").hexdigest()
        hits = [w for w in re.findall(r"[a-z]+", probe)
                for i in range(len(w) - 5) if hashlib.sha256(w[i:i + 6].encode()).hexdigest() == digest]
        self.assertEqual(hits, [probe])
        self.assertEqual(len(self.banned()), 5)
        for d in self.BANNED_DIGESTS:
            self.assertRegex(d, r"\A[0-9a-f]{64}\Z")

    def test_no_permit_word_anywhere(self):
        for name in ALL:
            self.assertNotIn(PERMIT, read(name).lower(), name)

    def test_no_conflict_markers_or_box_paths(self):
        markers = ("<" * 7, "=" * 7, ">" * 7)
        paths = ("/" + "workspace", "/" + "tmp/", "/" + "home/")
        texts = [(name, read(name)) for name in ALL]
        with open(day_readme(), encoding="utf-8") as f:
            texts.append(("day README", f.read()))
        for name, text in texts:
            for line in text.splitlines():
                self.assertFalse(line.startswith(markers), (name, line))
            for p in paths:
                self.assertNotIn(p, text, (name, p))

    def test_day_readme_row_and_footer(self):
        path = day_readme()
        self.assertIsNotNone(path, "no day README in repo layout or _day/")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("# experiments/2026-11-12\n"))
        rows = [ln for ln in text.splitlines() if ln.startswith("- [w21-unused-contradiction](")]
        self.assertEqual(len(rows), 1)
        self.assertIn("(w21-unused-contradiction/)", rows[0])
        self.assertIn("https://arxiv.org/abs/2611.13254", rows[0])
        self.assertEqual(text.count("Do not merge experiment PRs without Ork review."), 1)
        self.assertTrue(text.endswith("Do not merge experiment PRs without Ork review.\n"))
        for word in re.findall(r"[a-z]+", text.lower()):
            for n in Hygiene.BANNED_LENGTHS:
                for i in range(len(word) - n + 1):
                    digest = hashlib.sha256(word[i:i + n].encode("ascii")).hexdigest()
                    self.assertNotIn(digest, frozenset(Hygiene.BANNED_DIGESTS), word)
