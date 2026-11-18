"""Tests for transport (stdlib unittest). Run from this folder: python3 -B -m unittest"""

import ast
import copy
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import transport as tp  # noqa: E402

FX = os.path.join(HERE, "fixtures")
MAIN = os.path.join(FX, "executions.json")
DEMO_SHA256 = "1d502196a280551084d39b5572b2b4179f8269a6a1300dc53f9ca5229d4b3c4b"
PERCENT = re.compile(r"\d+(?:\.\d+)?\s*%")


def load_main():
    with open(MAIN, encoding="utf-8") as handle:
        return json.load(handle)


def execution(eid):
    return [e for e in load_main()["executions"] if e["id"] == eid][0]


class TempFixture:
    """Write a fixture object into a private temporary folder; removed on exit."""

    def __init__(self, obj, raw=None):
        self.obj, self.raw = obj, raw

    def __enter__(self):
        self.dir = tempfile.TemporaryDirectory()
        path = os.path.join(self.dir.name, "fx.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.raw if self.raw is not None else json.dumps(self.obj))
        return path

    def __exit__(self, *exc):
        self.dir.cleanup()


def deny_code(obj, raw=None):
    with TempFixture(obj, raw) as path:
        try:
            tp.run(path)
        except tp.Deny as exc:
            return exc.code, exc.detail
    return None, None


def run_cli(*args):
    return subprocess.run([sys.executable, "-B", os.path.join(HERE, "transport.py")] + list(args),
                          capture_output=True, text=True, cwd=HERE)


class TestVerifiers(unittest.TestCase):
    def obs(self, steps, criterion=("x",)):
        return {"criterion": list(criterion), "steps": steps}

    def test_direct_uses_visible_evidence(self):
        self.assertEqual(tp.direct(self.obs([{"evidence": {"x": True}, "summary": None}])), "pass")
        self.assertEqual(tp.direct(self.obs([{"evidence": {"x": False}, "summary": None}])), "fail")

    def test_direct_trusts_summary_claim_when_hidden(self):
        hidden = {"evidence": None, "summary": {"text": "ok", "claims": {"x": True}}}
        self.assertEqual(tp.direct(self.obs([hidden])), "pass")
        hidden["summary"]["claims"]["x"] = False
        self.assertEqual(tp.direct(self.obs([hidden])), "fail")

    def test_direct_treats_unseen_unclaimed_as_unmet(self):
        self.assertEqual(tp.direct(self.obs([{"evidence": None, "summary": None}])), "fail")
        self.assertEqual(tp.direct(self.obs([{"evidence": {"x": None}, "summary": None}])), "fail")

    def test_direct_visible_beats_summary(self):
        steps = [{"evidence": {"x": False}, "summary": None},
                 {"evidence": None, "summary": {"text": "ok", "claims": {"x": True}}}]
        self.assertEqual(tp.direct(self.obs(steps)), "fail")

    def test_direct_needs_every_item(self):
        steps = [{"evidence": {"x": True, "y": False}, "summary": None}]
        self.assertEqual(tp.direct(self.obs(steps, ("x", "y"))), "fail")
        self.assertEqual(tp.direct(self.obs(steps, ("x",))), "pass")

    def test_grounded_abstains_on_unseen(self):
        self.assertEqual(tp.grounded(self.obs([{"evidence": None, "summary": {"text": "", "claims": {"x": True}}}])),
                         "abstain")
        self.assertEqual(tp.grounded(self.obs([{"evidence": {"x": None}, "summary": None}])), "abstain")

    def test_grounded_decides_on_visible(self):
        self.assertEqual(tp.grounded(self.obs([{"evidence": {"x": True}, "summary": None}])), "pass")
        self.assertEqual(tp.grounded(self.obs([{"evidence": {"x": False}, "summary": None}])), "fail")
        steps = [{"evidence": {"x": True, "y": False}, "summary": None}]
        self.assertEqual(tp.grounded(self.obs(steps, ("x", "y"))), "fail")

    def test_observable_hides_ground_truth(self):
        view = tp.native_view(execution("e1"), "direct")
        obs = tp.observable(view)
        self.assertEqual(sorted(obs), ["criterion", "steps"])
        self.assertNotIn("ground_truth", json.dumps(obs))

    def test_bad_verdict_is_deny(self):
        view = tp.native_view(execution("e4"), "direct")
        saved = tp.VERIFIERS["direct"]
        tp.VERIFIERS["direct"] = lambda obs: "maybe"
        try:
            with self.assertRaises(tp.Deny) as ctx:
                tp.verdict(view)
            self.assertEqual(ctx.exception.code, "bad_verdict")
        finally:
            tp.VERIFIERS["direct"] = saved


class TestViews(unittest.TestCase):
    def test_native_view_is_full(self):
        view = tp.native_view(execution("e1"), "direct")
        self.assertEqual(view["kind"], "native")
        self.assertEqual([s["evidence"] for s in view["steps"]],
                         [{"order_found": True}, {"refund_posted": False}, {"customer_told": True}])
        self.assertEqual(view["step_ids"], ("s1", "s2", "s3"))
        self.assertEqual(view["criterion"], ("order_found", "refund_posted", "customer_told"))

    def test_abstract_hides_only_boundary_steps(self):
        view, prov = tp.abstract(execution("e1"), "direct", "delegation")
        self.assertEqual(view["kind"], "abstracted")
        self.assertEqual(view["boundary"], "delegation")
        self.assertEqual(prov, {"s2": {"refund_posted": False}})
        self.assertEqual([s["evidence"] for s in view["steps"]], [{"order_found": True}, None, {"customer_told": True}])
        self.assertEqual(view["steps"][1]["summary"]["claims"], {"refund_posted": True})
        self.assertIsNone(view["steps"][0]["summary"])

    def test_abstract_composed_tool_hides_both_steps(self):
        view, prov = tp.abstract(execution("e2"), "grounded", "composed_tool")
        self.assertEqual(sorted(prov), ["s1", "s2"])
        self.assertTrue(all(s["evidence"] is None for s in view["steps"]))

    def test_abstract_does_not_change_frozen_fields(self):
        ex = execution("e3")
        view, _ = tp.abstract(ex, "direct", "compaction")
        native = tp.native_view(ex, "direct")
        for field in tp.FROZEN:
            self.assertEqual(view[field], native[field])
        tp.check_matched(native, view)

    def test_unknown_boundary(self):
        with self.assertRaises(tp.Deny) as ctx:
            tp.abstract(execution("e1"), "direct", "teleport")
        self.assertEqual(ctx.exception.code, "unknown_boundary")

    def test_boundary_that_hides_nothing_is_deny(self):
        with self.assertRaises(tp.Deny) as ctx:
            tp.abstract(execution("e1"), "direct", "compaction")
        self.assertEqual(ctx.exception.code, "boundary_hides_nothing")

    def test_full_restore_equals_native_evidence(self):
        ex = execution("e1")
        view, prov = tp.abstract(ex, "direct", "delegation")
        full = tp.restore(view, prov)
        self.assertEqual(full["kind"], "restored")
        self.assertEqual(full["restore"], "full")
        self.assertEqual([s["evidence"] for s in full["steps"]],
                         [s["evidence"] for s in tp.native_view(ex, "direct")["steps"]])
        self.assertIsNone(full["steps"][1]["summary"])

    def test_lossy_restore_loses_values(self):
        view, prov = tp.abstract(execution("e1"), "direct", "delegation")
        lossy = tp.restore(view, prov, lossy=True)
        self.assertEqual(lossy["restore"], "lossy")
        self.assertEqual(lossy["steps"][1]["evidence"], {"refund_posted": None})
        self.assertEqual(lossy["steps"][0]["evidence"], {"order_found": True})
        self.assertEqual(lossy["steps"][1]["summary"]["claims"], {"refund_posted": True})

    def test_restore_leaves_input_untouched(self):
        view, prov = tp.abstract(execution("e1"), "direct", "delegation")
        before = copy.deepcopy(view)
        tp.restore(view, prov)
        tp.restore(view, prov, lossy=True)
        self.assertEqual(view, before)


class TestLabels(unittest.TestCase):
    def test_label_table(self):
        cases = [
            ("pass", "pass", "pass", "stable"),
            ("fail", "fail", "fail", "stable"),
            ("pass", "pass", "fail", "transport_incorrect"),
            ("fail", "fail", "pass", "transport_incorrect"),
            ("pass", "pass", "abstain", "transport_abstain"),
            ("fail", "fail", "abstain", "transport_abstain"),
            ("pass", "fail", "pass", "native_not_correct"),
            ("pass", "abstain", "pass", "native_not_correct"),
            ("fail", "pass", "abstain", "native_not_correct"),
        ]
        for truth, nv, av, want in cases:
            self.assertEqual(tp.label(truth, nv, av), want, (truth, nv, av))


EXPECTED_ROWS = [
    ("p1", "e1", "direct", "delegation", "fail", "fail", "pass", "transport_incorrect", "recovered", "not_recovered"),
    ("p2", "e2", "direct", "composed_tool", "pass", "pass", "pass", "stable", "n/a", "n/a"),
    ("p3", "e3", "direct", "compaction", "pass", "pass", "fail", "transport_incorrect", "recovered", "not_recovered"),
    ("p4", "e4", "direct", "compaction", "pass", "pass", "pass", "stable", "n/a", "n/a"),
    ("p5", "e1", "grounded", "delegation", "fail", "fail", "abstain", "transport_abstain", "recovered", "not_recovered"),
    ("p6", "e2", "grounded", "composed_tool", "pass", "pass", "abstain", "transport_abstain", "recovered", "not_recovered"),
    ("p7", "e3", "grounded", "compaction", "pass", "pass", "abstain", "transport_abstain", "recovered", "not_recovered"),
    ("p8", "e4", "grounded", "compaction", "pass", "pass", "pass", "stable", "n/a", "n/a"),
]
KEYS = ("pair", "execution", "verifier", "boundary", "truth", "native", "abstracted", "label",
        "restore_full", "restore_lossy")


class TestMeasure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = tp.run(MAIN)

    def test_rows(self):
        got = [tuple(r[k] for k in KEYS) for r in self.report["rows"]]
        self.assertEqual(got, EXPECTED_ROWS)

    def test_incorrect_and_abstain_counted_separately(self):
        s = self.report["summary"]
        self.assertEqual(s["direct"], {"pairs": 4, "native_correct": 4, "stable": 2, "transport_incorrect": 2,
                                       "transport_abstain": 0, "transport_failures": 2, "native_not_correct": 0,
                                       "recovered_full": 2, "recovered_lossy": 0})
        self.assertEqual(s["grounded"], {"pairs": 4, "native_correct": 4, "stable": 1, "transport_incorrect": 0,
                                         "transport_abstain": 3, "transport_failures": 3, "native_not_correct": 0,
                                         "recovered_full": 3, "recovered_lossy": 0})

    def test_no_single_score(self):
        for s in self.report["summary"].values():
            for key in ("score", "reliability", "accuracy", "rate"):
                self.assertNotIn(key, s)

    def test_full_vs_lossy_restore(self):
        failures = [r for r in self.report["rows"] if r["label"].startswith("transport_")]
        self.assertEqual(len(failures), 5)
        self.assertTrue(all(r["restore_full"] == "recovered" for r in failures))
        self.assertTrue(all(r["restore_lossy"] == "not_recovered" for r in failures))
        stable = [r for r in self.report["rows"] if r["label"] == "stable"]
        self.assertTrue(all(r["restore_full"] == "n/a" and r["restore_lossy"] == "n/a" for r in stable))

    def test_status_measured_never_pass(self):
        self.assertEqual(self.report["transport"], "measured")
        self.assertEqual(self.report["status"], "measured")
        self.assertNotIn("PASS", "\n".join(tp.render(self.report)))

    def test_fewer_failures_more_wrong_is_not_ranked_more_reliable(self):
        d, g = self.report["summary"]["direct"], self.report["summary"]["grounded"]
        self.assertLess(d["transport_failures"], g["transport_failures"])
        self.assertGreater(d["transport_incorrect"], g["transport_incorrect"])
        self.assertEqual(tp.rank(d, g), "not_ranked")
        self.assertEqual(tp.rank(g, d), "not_ranked")
        self.assertIn("rank(direct, grounded): not_ranked", tp.render(self.report))

    def test_rank_orders_only_on_dominance(self):
        def s(i, a):
            return {"transport_incorrect": i, "transport_abstain": a, "transport_failures": i + a}
        self.assertEqual(tp.rank(s(1, 1), s(1, 1)), "equal")
        self.assertEqual(tp.rank(s(0, 1), s(1, 1)), "first_more_reliable")
        self.assertEqual(tp.rank(s(1, 0), s(1, 1)), "first_more_reliable")
        self.assertEqual(tp.rank(s(2, 2), s(1, 1)), "second_more_reliable")
        self.assertEqual(tp.rank(s(1, 2), s(1, 1)), "second_more_reliable")
        self.assertEqual(tp.rank(s(2, 0), s(0, 3)), "not_ranked")
        self.assertEqual(tp.rank(s(0, 3), s(2, 0)), "not_ranked")
        self.assertEqual(tp.rank(s(1, 0), s(0, 1)), "not_ranked")

    def test_native_not_correct_is_not_a_transport_failure(self):
        saved = tp.VERIFIERS["direct"]
        tp.VERIFIERS["direct"] = lambda obs: "abstain"
        try:
            ex = execution("e1")
            native = tp.native_view(ex, "direct")
            view, prov = tp.abstract(ex, "direct", "delegation")
            row = tp.measure_pair("x", native, view, prov)
        finally:
            tp.VERIFIERS["direct"] = saved
        self.assertEqual(row["label"], "native_not_correct")
        self.assertEqual((row["restore_full"], row["restore_lossy"]), ("n/a", "n/a"))
        summ = tp.summarize([row])["direct"]
        self.assertEqual((summ["native_correct"], summ["transport_failures"], summ["native_not_correct"]), (0, 0, 1))

    def test_mismatched_stable_pair_is_deny(self):
        ex = execution("e4")
        other = copy.deepcopy(ex)
        other["outcome"] = "agent replied: not added"
        native = tp.native_view(ex, "grounded")
        view, prov = tp.abstract(other, "grounded", "compaction")
        self.assertEqual(tp.verdict(view), "pass")
        with self.assertRaises(tp.Deny) as ctx:
            tp.measure_pair("x", native, view, prov)
        self.assertEqual(ctx.exception.code, "mismatched_pair")

    def test_summary_counts_only_recovered_restores(self):
        rows = [{"verifier": "v", "label": "transport_incorrect", "restore_full": "not_recovered",
                 "restore_lossy": "not_recovered"},
                {"verifier": "v", "label": "transport_abstain", "restore_full": "recovered",
                 "restore_lossy": "recovered"}]
        s = tp.summarize(rows)["v"]
        self.assertEqual((s["recovered_full"], s["recovered_lossy"], s["transport_failures"]), (1, 1, 2))

    def test_cli_main_fixture(self):
        res = run_cli(MAIN)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stderr, "")
        self.assertEqual(res.stdout, "\n".join(tp.render(self.report)) + "\n")

    def test_main_in_process(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = tp.main([MAIN])
        self.assertEqual(code, 0)
        self.assertIn("status: measured", out.getvalue())


class TestNativeOnly(unittest.TestCase):
    def test_native_only_is_unmeasured_never_pass(self):
        report = tp.run(os.path.join(FX, "native_only.json"))
        self.assertEqual(report["mode"], "native_only")
        self.assertEqual(report["result"], {"native_correct": 4, "native_views": 4,
                                            "transport": "unmeasured", "status": "unmeasured"})
        text = "\n".join(tp.render(report))
        self.assertIn("transport: unmeasured", text)
        self.assertNotIn("PASS", text)

    def test_perfect_native_accuracy_still_unmeasured(self):
        views = [tp.native_view(execution(e), v) for e in ("e1", "e2", "e3", "e4") for v in ("direct", "grounded")]
        r = tp.score_native_only(views)
        self.assertEqual((r["native_correct"], r["native_views"]), (8, 8))
        self.assertEqual((r["transport"], r["status"]), ("unmeasured", "unmeasured"))

    def test_native_only_counts_wrong(self):
        saved = tp.VERIFIERS["direct"]
        tp.VERIFIERS["direct"] = lambda obs: "pass"
        try:
            r = tp.score_native_only([tp.native_view(execution("e1"), "direct"),
                                      tp.native_view(execution("e4"), "direct")])
        finally:
            tp.VERIFIERS["direct"] = saved
        self.assertEqual(r["native_correct"], 1)


def pair_fixture(native=None, abstracted=None, mutate=None, drop=None):
    data = load_main()
    e1 = data["executions"][0]
    e1b = copy.deepcopy(e1)
    e1b["id"] = "e1b"
    if mutate:
        mutate(e1b)
    pair = {"id": "p1", "native": native or {"execution": "e1", "verifier": "direct"},
            "abstracted": abstracted or {"execution": "e1b", "verifier": "direct", "boundary": "delegation"}}
    if drop:
        del pair[drop]
    return {"executions": [e1, e1b], "pairs": [pair]}


SAME = {"execution": "e1", "verifier": "direct", "boundary": "delegation"}
TITLE = ("Do Verifier Judgments Survive Abstraction? Measuring Verification Transport "
         "for LLM Agent Evaluation")


def single_fixture(eid, verifier, boundary, mutate=None):
    """One execution from the main fixture and one pair over it (the same execution on both sides)."""
    ex = copy.deepcopy(execution(eid))
    if mutate:
        mutate(ex)
    return {"executions": [ex], "pairs": [{"id": "p1", "native": {"execution": eid, "verifier": verifier},
                                           "abstracted": {"execution": eid, "verifier": verifier,
                                                          "boundary": boundary}}]}


def run_rows(obj):
    with TempFixture(obj) as path:
        return tp.run(path)


class TestDeny(unittest.TestCase):
    def test_identical_copy_is_matched(self):
        # r2: a pair is matched only within one execution id; an identical copy under a new id is DENY.
        self.assertEqual(deny_code(pair_fixture(abstracted=dict(SAME))), (None, None))
        code, detail = deny_code(pair_fixture())
        self.assertEqual(code, "mismatched_pair")
        self.assertTrue(detail.startswith("execution differs (e1 vs e1b)"), detail)

    def test_each_frozen_field_mismatch_is_deny(self):
        muts = {
            "task": lambda e: e.__setitem__("task", "refund order B-2"),
            "trajectory_id": lambda e: e.__setitem__("trajectory_id", "t-other"),
            "step_ids": lambda e: e["steps"][0].__setitem__("id", "s0"),
            "outcome": lambda e: e.__setitem__("outcome", "agent replied: pending"),
            "criterion": lambda e: e["criterion"].reverse(),
        }
        for field, fn in muts.items():
            code, detail = deny_code(pair_fixture(mutate=fn))
            self.assertEqual(code, "mismatched_pair", field)
            self.assertTrue(detail.startswith(field + " differs"), (field, detail))

    def test_ground_truth_mismatch_is_deny(self):
        def fn(e):
            e["ground_truth"] = "pass"
            e["steps"][1]["evidence"]["refund_posted"] = True
        code, detail = deny_code(pair_fixture(mutate=fn))
        self.assertEqual(code, "mismatched_pair")
        self.assertTrue(detail.startswith("ground_truth differs"))

    def test_verifier_mismatch_is_deny(self):
        code, detail = deny_code(pair_fixture(abstracted={"execution": "e1", "verifier": "grounded",
                                                          "boundary": "delegation"}))
        self.assertEqual(code, "mismatched_pair")
        self.assertTrue(detail.startswith("verifier differs"))

    def test_missing_views(self):
        self.assertEqual(deny_code(pair_fixture(drop="abstracted"))[0], "missing_view")
        self.assertEqual(deny_code(pair_fixture(drop="native"))[0], "missing_view")
        self.assertEqual(deny_code(pair_fixture(abstracted={"execution": "e9", "verifier": "direct",
                                                            "boundary": "delegation"}))[0], "missing_view")
        self.assertEqual(deny_code(pair_fixture(native={"execution": "e9", "verifier": "direct"}))[0], "missing_view")
        bad = pair_fixture()
        bad["pairs"][0]["abstracted"] = None
        self.assertEqual(deny_code(bad)[0], "missing_view")

    def test_expired_view_is_deny_never_a_verdict(self):
        for side in ("native", "abstracted"):
            fx = pair_fixture()
            fx["pairs"][0][side]["expired"] = True
            code, detail = deny_code(fx)
            self.assertEqual(code, "on_expiry")
            self.assertIn("on_expiry=DENY", detail)
        self.assertEqual(tp.ON_EXPIRY, "DENY")

    def test_unknown_verifier_and_boundary(self):
        self.assertEqual(deny_code(pair_fixture(native={"execution": "e1", "verifier": "oracle"}))[0],
                         "unknown_verifier")
        self.assertEqual(deny_code(pair_fixture(abstracted={"execution": "e1", "verifier": "direct",
                                                            "boundary": "wormhole"}))[0], "unknown_boundary")
        self.assertEqual(deny_code(pair_fixture(abstracted={"execution": "e1", "verifier": "direct"}))[0],
                         "unknown_boundary")

    def test_malformed_inputs(self):
        self.assertEqual(deny_code(None, raw="{not json"), ("malformed_fixture", "not JSON"))
        self.assertEqual(deny_code([])[0], "malformed_fixture")
        self.assertEqual(deny_code({"executions": [], "pairs": []})[0], "malformed_fixture")
        both = pair_fixture()
        both["native_only"] = [{"execution": "e1", "verifier": "direct"}]
        self.assertEqual(deny_code(both)[0], "malformed_fixture")
        neither = pair_fixture()
        del neither["pairs"]
        self.assertEqual(deny_code(neither)[0], "malformed_fixture")
        empty = pair_fixture()
        empty["pairs"] = []
        self.assertEqual(deny_code(empty)[0], "malformed_fixture")
        dup = pair_fixture(abstracted=dict(SAME))
        dup["pairs"].append(copy.deepcopy(dup["pairs"][0]))
        self.assertEqual(deny_code(dup)[0], "malformed_fixture")
        noid = pair_fixture()
        del noid["pairs"][0]["id"]
        self.assertEqual(deny_code(noid)[0], "malformed_fixture")

    def test_malformed_executions(self):
        cases = {
            "int evidence": lambda e: e["steps"][0]["evidence"].__setitem__("order_found", 1),
            "bad truth": lambda e: e.__setitem__("ground_truth", "PASS"),
            "empty criterion": lambda e: e.__setitem__("criterion", []),
            "no steps": lambda e: e.__setitem__("steps", []),
            "empty task": lambda e: e.__setitem__("task", ""),
            "bad claims": lambda e: e["steps"][1]["summary"].__setitem__("claims", {"refund_posted": "yes"}),
            "repeat item": lambda e: e["steps"][2]["evidence"].__setitem__("order_found", True),
            "criterion w/o evidence": lambda e: e["criterion"].append("ghost"),
            "dup id": lambda e: e.__setitem__("id", "e1"),
        }
        for name, fn in cases.items():
            self.assertEqual(deny_code(pair_fixture(mutate=fn))[0], "malformed_fixture", name)
        hb = deny_code(pair_fixture(mutate=lambda e: e["steps"][1].__setitem__("hidden_by", ["fog"])))
        self.assertEqual(hb[0], "unknown_boundary")

    def test_ground_truth_inconsistent_with_criterion(self):
        code, _ = deny_code(pair_fixture(mutate=lambda e: e.__setitem__("ground_truth", "pass")))
        self.assertEqual(code, "ground_truth_inconsistent")

    def test_unreadable(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(tp.Deny) as ctx:
                tp.run(os.path.join(d, "absent.json"))
        self.assertEqual(ctx.exception.code, "unreadable_fixture")

    def test_bad_fixtures_cli_exit_2(self):
        want = {"bad_mismatched_pair.json": "DENY mismatched_pair: outcome differs",
                "bad_missing_view.json": "DENY missing_view:",
                "bad_expired_view.json": "DENY on_expiry:"}
        for name, prefix in sorted(want.items()):
            res = run_cli(os.path.join(FX, name))
            self.assertEqual(res.returncode, 2, name)
            self.assertEqual(res.stdout, "", name)
            self.assertTrue(res.stderr.startswith(prefix), (name, res.stderr))

    def test_cli_usage_and_missing_file(self):
        res = run_cli()
        self.assertEqual((res.returncode, res.stdout), (2, ""))
        self.assertTrue(res.stderr.startswith("DENY"))
        res = run_cli("no-such-fixture.json")
        self.assertEqual((res.returncode, res.stdout), (2, ""))
        self.assertTrue(res.stderr.startswith("DENY unreadable_fixture"))


class TestR2Strictness(unittest.TestCase):
    """r2: each test here fails against the r1 module (head 796cdf5b)."""

    def assert_deny(self, obj, code, raw=None, prefix=None):
        got, detail = deny_code(obj, raw)
        self.assertEqual(got, code, detail)
        if prefix is not None:
            self.assertTrue(detail.startswith(prefix), detail)
        return detail

    # M1: same execution id AND equal step content
    def test_m1_summary_drift_across_executions_is_deny(self):
        # probe p56: e1b equals e1 except the delegated summary claims refund_posted false
        fx = pair_fixture(mutate=lambda e: e["steps"][1]["summary"]["claims"].__setitem__("refund_posted", False))
        self.assert_deny(fx, "mismatched_pair", prefix="execution differs")

    def test_m1_evidence_drift_across_executions_is_deny(self):
        # probe p55: evidence values drifted, frozen fields and ground truth unchanged
        def fn(e):
            e["steps"][0]["evidence"]["order_found"] = False
            e["steps"][1]["evidence"]["refund_posted"] = True
        self.assert_deny(pair_fixture(mutate=fn), "mismatched_pair", prefix="execution differs")

    def test_m1_tool_drift_across_executions_is_deny(self):
        # probe p57: the delegated step's tool drifted
        fx = pair_fixture(mutate=lambda e: e["steps"][1].__setitem__("tool", "human.refund"))
        self.assert_deny(fx, "mismatched_pair", prefix="execution differs")

    def test_m1_step_content_checked_within_one_execution_id(self):
        ex = execution("e1")
        native = tp.native_view(ex, "direct")
        drifts = {
            "summary": lambda e: e["steps"][1]["summary"]["claims"].__setitem__("refund_posted", False),
            "summary text": lambda e: e["steps"][1]["summary"].__setitem__("text", "subagent reports: pending"),
            "evidence": lambda e: e["steps"][0]["evidence"].__setitem__("order_found", False),
            "tool": lambda e: e["steps"][1].__setitem__("tool", "human.refund"),
            "hidden_by": lambda e: e["steps"][0].__setitem__("hidden_by", ["delegation"]),
        }
        for name, fn in drifts.items():
            other = copy.deepcopy(ex)
            fn(other)
            view, prov = tp.abstract(other, "direct", "delegation")
            with self.assertRaises(tp.Deny, msg=name) as ctx:
                tp.measure_pair("x", native, view, prov)
            self.assertEqual(ctx.exception.code, "mismatched_pair", name)
            self.assertTrue(ctx.exception.detail.startswith("step_content differs"), (name, ctx.exception.detail))

    def test_m1_cli_p56_exit_2(self):
        fx = pair_fixture(mutate=lambda e: e["steps"][1]["summary"]["claims"].__setitem__("refund_posted", False))
        with TempFixture(fx) as path:
            res = run_cli(path)
        self.assertEqual((res.returncode, res.stdout), (2, ""))
        self.assertTrue(res.stderr.startswith("DENY mismatched_pair: execution differs"), res.stderr)

    # M2: duplicate step ids
    def test_m2_duplicate_step_id_is_deny(self):
        # probe p27: e3 with step s2 renamed s1 (r1 flipped the full restore to not_recovered)
        fx = single_fixture("e3", "direct", "compaction", lambda e: e["steps"][1].__setitem__("id", "s1"))
        self.assert_deny(fx, "malformed_fixture", prefix="e3 step id s1 repeated")
        # probe p26: e4 with step s2 renamed s1
        fx = single_fixture("e4", "grounded", "compaction", lambda e: e["steps"][1].__setitem__("id", "s1"))
        self.assert_deny(fx, "malformed_fixture", prefix="e4 step id s1 repeated")
        with TempFixture(single_fixture("e3", "direct", "compaction",
                                        lambda e: e["steps"][1].__setitem__("id", "s1"))) as path:
            res = run_cli(path)
        self.assertEqual((res.returncode, res.stdout), (2, ""))

    # M3: expired must be a JSON boolean
    def test_m3_expired_must_be_a_json_boolean(self):
        # probes p11-p16; 1 == True and isinstance(True, int) in Python, so the check is on type
        for side in ("abstracted", "native"):
            for value in (1, "true", "yes", 1.0, "True", 0, "false", None, [True], {"v": True}):
                fx = single_fixture("e4", "grounded", "compaction")
                fx["pairs"][0][side]["expired"] = value
                detail = self.assert_deny(fx, "malformed_fixture")
                self.assertIn("expired is not a JSON boolean", detail)
        raw = json.dumps(single_fixture("e4", "grounded", "compaction")).replace(
            '"boundary": "compaction"}', '"boundary": "compaction", "expired": 1}')
        self.assertIn('"expired": 1}', raw)
        self.assert_deny(None, "malformed_fixture", raw=raw)

    def test_m3_boolean_expired_still_decides(self):
        fx = single_fixture("e4", "grounded", "compaction")
        fx["pairs"][0]["abstracted"]["expired"] = False
        self.assertEqual([r["label"] for r in run_rows(fx)["rows"]], ["stable"])
        fx["pairs"][0]["abstracted"]["expired"] = True
        self.assert_deny(fx, "on_expiry")
        native = {"native_only": [{"execution": "e4", "verifier": "grounded", "expired": 1}],
                  "executions": [execution("e4")]}
        self.assert_deny(native, "malformed_fixture")

    def test_m3_cli_exit_2(self):
        fx = single_fixture("e4", "grounded", "compaction")
        fx["pairs"][0]["abstracted"]["expired"] = "true"
        with TempFixture(fx) as path:
            res = run_cli(path)
        self.assertEqual((res.returncode, res.stdout), (2, ""))
        self.assertTrue(res.stderr.startswith("DENY malformed_fixture:"), res.stderr)

    # M4: duplicate JSON keys at every nesting level
    def test_m4_duplicate_keys_are_deny_at_every_level(self):
        base = json.dumps(single_fixture("e4", "grounded", "compaction"))
        cases = {
            "evidence (p18)": ('"item_added": true', '"item_added": false, "item_added": true'),
            "ground_truth (p19)": ('"ground_truth": "pass"', '"ground_truth": "fail", "ground_truth": "pass"'),
            "boundary (p20)": ('"boundary": "compaction"', '"boundary": "delegation", "boundary": "compaction"'),
            "expired (p21)": ('"boundary": "compaction"', '"boundary": "compaction", "expired": true, "expired": false'),
            "executions (p22)": ('{"executions": [', '{"executions": [], "executions": ['),
            "pair id": ('"id": "p1"', '"id": "p0", "id": "p1"'),
            "step id": ('"id": "s2"', '"id": "s9", "id": "s2"'),
            "summary-free step tool": ('"tool": "notes.append"', '"tool": "notes.read", "tool": "notes.append"'),
        }
        self.assertEqual(deny_code(None, raw=base), (None, None))
        for name, (old, new) in cases.items():
            self.assertEqual(base.count(old), 1, name)
            detail = self.assert_deny(None, "malformed_fixture", raw=base.replace(old, new, 1))
            self.assertTrue(detail.startswith("duplicate key"), (name, detail))

    def test_m4_cli_exit_2(self):
        raw = json.dumps(single_fixture("e4", "grounded", "compaction")).replace(
            '"item_added": true', '"item_added": false, "item_added": true')
        with TempFixture(None, raw) as path:
            res = run_cli(path)
        self.assertEqual((res.returncode, res.stdout), (2, ""))
        self.assertTrue(res.stderr.startswith("DENY malformed_fixture: duplicate key 'item_added'"), res.stderr)

    # L1: full paper title
    def test_l1_full_paper_title(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["paper"]["title"], TITLE)
        with open(os.path.join(HERE, "README.md"), encoding="utf-8") as handle:
            self.assertIn(TITLE, " ".join(handle.read().split()))

    # L2: the same pair under a new id is counted once
    def test_l2_same_pair_under_new_id_counted_once(self):
        fx = single_fixture("e4", "grounded", "compaction")  # probe p25
        fx["pairs"].append(dict(copy.deepcopy(fx["pairs"][0]), id="p2"))
        report = run_rows(fx)
        self.assertEqual([r["pair"] for r in report["rows"]], ["p1"])
        self.assertEqual(report["summary"]["grounded"]["pairs"], 1)
        self.assertEqual(report["info"], ["counted_twice: p2 repeats p1 (counted once)"])
        self.assertIn("INFO counted_twice: p2 repeats p1 (counted once)", tp.render(report))
        other = single_fixture("e4", "direct", "compaction")["pairs"][0]
        fx["pairs"].append(dict(other, id="p3"))
        self.assertEqual([r["pair"] for r in run_rows(fx)["rows"]], ["p1", "p3"])
        self.assertEqual(tp.run(MAIN)["info"], [])

    # L3: blank ids and text fields
    def test_l3_blank_strings_are_deny(self):
        cases = {
            "task whitespace (p67)": lambda e: e.__setitem__("task", " "),
            "trajectory tab": lambda e: e.__setitem__("trajectory_id", "\t"),
            "outcome newline": lambda e: e.__setitem__("outcome", "\n"),
            "step id empty": lambda e: e["steps"][0].__setitem__("id", ""),
            "tool blank": lambda e: e["steps"][1].__setitem__("tool", "  "),
            "criterion item blank": lambda e: (e["criterion"].append(" "),
                                               e["steps"][1]["evidence"].__setitem__(" ", True)),
        }
        for name, fn in cases.items():
            self.assert_deny(single_fixture("e4", "grounded", "compaction", fn), "malformed_fixture")
        fx = single_fixture("e2", "direct", "composed_tool",
                            lambda e: e["steps"][0]["summary"].__setitem__("text", " "))
        self.assert_deny(fx, "malformed_fixture")
        for pid in ("", "   "):  # probe p68
            fx = single_fixture("e4", "grounded", "compaction")
            fx["pairs"][0]["id"] = pid
            self.assert_deny(fx, "malformed_fixture", prefix="pair id")


class TestDemo(unittest.TestCase):
    def run_demo(self):
        res = subprocess.run([sys.executable, "-B", os.path.join(HERE, "demo.py")], capture_output=True, cwd=HERE)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stderr, b"")
        return res.stdout

    def test_demo_sha256_pinned(self):
        self.assertEqual(hashlib.sha256(self.run_demo()).hexdigest(), DEMO_SHA256)

    def test_demo_is_deterministic_and_has_no_figures(self):
        a, b = self.run_demo(), self.run_demo()
        self.assertEqual(a, b)
        self.assertIsNone(PERCENT.search(a.decode("utf-8")))
        self.assertNotIn(b"PASS", a)


class TestHygiene(unittest.TestCase):
    EXPECTED_IMPORTS = {
        "transport.py": {"copy", "json", "sys"},
        "demo.py": {"os", "sys", "transport"},
    }

    @staticmethod
    def imports(name):
        with open(os.path.join(HERE, name), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                found.add((node.module or "").split(".")[0])
        return found

    def test_stdlib_only_imports(self):
        local = {"transport"}
        for name in sorted(f for f in os.listdir(HERE) if f.endswith(".py")):
            for mod in self.imports(name):
                self.assertTrue(mod in sys.stdlib_module_names or mod in local, (name, mod))

    def test_module_and_demo_import_exactly_these(self):
        for name, want in self.EXPECTED_IMPORTS.items():
            self.assertEqual(self.imports(name), want, name)

    def test_paper_figures_only_in_evidence_on_unmeasured(self):
        for name in ("README.md", "transport.py", "demo.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                self.assertIsNone(PERCENT.search(handle.read()), name)
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as handle:
            ev = json.load(handle)
        self.assertEqual(ev["status"], "UNVERIFIED")
        hits = []

        def walk(node, path):
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, path + (k,))
            elif isinstance(node, list):
                for v in node:
                    walk(v, path)
            elif isinstance(node, str) and PERCENT.search(node):
                hits.append(path)
        walk(ev, ())
        self.assertTrue(hits)
        for path in hits:
            self.assertEqual(path[0], "on_unmeasured", path)
        for item in ev["on_unmeasured"]["figures"]:
            self.assertEqual(item["status"], "UNVERIFIED")
            self.assertEqual(item["measured_here"], "on_unmeasured")


if __name__ == "__main__":
    unittest.main()
