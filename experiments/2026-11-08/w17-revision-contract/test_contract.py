"""Unit tests for the call-level revision contract sketch (SYNTHETIC, offline)."""

import ast
import hashlib
import html
import json
import os
import re
import unittest
from pathlib import Path

import contract
import fixtures
from contract import (GateDecision, Ledger, OrphanPolicy, RepeatPolicy, RunOutcome,
                      assign_sites, gate, load_ledger_text, revise, run_workflow)

HERE = Path(__file__).resolve().parent
INPUTS = fixtures.INPUTS


def frozen(name):
    return fixtures.load_frozen_ledgers()[name]


class IdentityTests(unittest.TestCase):
    def test_identity_is_callsite_path_fanout_occurrence(self):
        led = load_ledger_text(frozen("base"))
        keys = sorted(led.records)
        self.assertIn("main/for#0/run#0||0", keys)
        self.assertIn("main/for#0/run#0||2", keys)
        self.assertIn("main/run#0||0", keys)
        fan = load_ledger_text(frozen("fanout"))
        self.assertEqual(sorted(fan.records),
                         ["shot/run#0|0|0", "shot/run#0|1|0", "shot/run#0|2|0"])

    def test_identity_stable_under_comments_and_noncapability_insert(self):
        old = assign_sites(fixtures.BASE_OLD)
        new = assign_sites(fixtures.HAPPY_NEW)
        for site in ("main/run#0", "main/for#0/run#0"):
            self.assertEqual(old[site], new[site])

    def test_committed_ledger_is_frozen_json_fixture(self):
        rebuilt = fixtures.rebuild_ledgers()
        for name, text in fixtures.load_frozen_ledgers().items():
            self.assertEqual(json.loads(text), json.loads(rebuilt[name].to_json()), name)
        # the old base run failed at compose, so compose is not committed
        self.assertFalse(any(r.capability == "video.compose"
                             for r in load_ledger_text(frozen("base")).records.values()))


class GateTests(unittest.TestCase):
    def test_happy_path_replays_retained_identities(self):
        rep = revise(fixtures.BASE_OLD, fixtures.HAPPY_NEW, frozen("base"), INPUTS)
        self.assertIs(rep.gate.decision, GateDecision.ACCEPT)
        self.assertIs(rep.run.outcome, RunOutcome.COMPLETED)
        self.assertEqual(len(rep.run.replayed), 4)
        self.assertEqual(rep.run.dispatch_count, 1)
        self.assertEqual(rep.naive_dispatches, 5)
        self.assertEqual(rep.dispatches_saved, 4)
        self.assertEqual(rep.run.orphans, [])

    def test_literal_argument_edit_stopped_statically(self):
        g = gate(fixtures.BASE_OLD, fixtures.LITERAL_EDIT_NEW, frozen("base"))
        self.assertIs(g.decision, GateDecision.REJECT)
        self.assertEqual(g.kinds, ["call_changed"])
        rep = revise(fixtures.BASE_OLD, fixtures.LITERAL_EDIT_NEW, frozen("base"), INPUTS)
        self.assertEqual(rep.run.dispatch_count, 0)
        self.assertEqual(rep.run.replayed, [])

    def test_capability_change_rejected(self):
        new = fixtures.HAPPY_NEW.replace('"storyboard.plan"', '"storyboard.draft"')
        g = gate(fixtures.BASE_OLD, new, frozen("base"))
        self.assertIs(g.decision, GateDecision.REJECT)
        self.assertIn("capability_changed", g.kinds)

    def test_removed_call_rejected(self):
        loop = ('    for i in range(3):\n'
                '        clips.append(ctx.run("image.generate", {"prompt": inp["brief"], "shot": i, "w": width}))\n')
        self.assertIn(loop, fixtures.HAPPY_NEW)
        g = gate(fixtures.BASE_OLD, fixtures.HAPPY_NEW.replace(loop, ""), frozen("base"))
        self.assertIs(g.decision, GateDecision.REJECT)
        self.assertEqual(g.kinds, ["removed"])

    def test_removal_ahead_of_site_shifts_ordinal_and_rejects(self):
        new = fixtures.HAPPY_NEW.replace(
            '    board = ctx.run("storyboard.plan", {"brief": inp["brief"], "shots": 3})\n', "")
        g = gate(fixtures.BASE_OLD, new, frozen("base"))
        self.assertIs(g.decision, GateDecision.REJECT)
        self.assertTrue(set(g.kinds) <= {"removed", "capability_changed"})

    def test_relocation_is_stop_not_reuse(self):
        g = gate(fixtures.BASE_OLD, fixtures.RELOCATION_NEW, frozen("base"))
        self.assertIs(g.decision, GateDecision.REJECT)
        self.assertEqual(g.kinds, ["relocated_not_reused"])
        self.assertIn("plan/run#0", g.findings[0].detail)
        rep = revise(fixtures.BASE_OLD, fixtures.RELOCATION_NEW, frozen("base"), INPUTS)
        self.assertIs(rep.run.outcome, RunOutcome.NOT_RUN_GATE_REJECTED)
        self.assertEqual(rep.run.replayed, [])   # never served from the old record
        self.assertEqual(rep.run.dispatch_count, 0)

    def test_subset_violations_rejected(self):
        bad = "import os\n" + fixtures.HAPPY_NEW
        self.assertIs(gate(fixtures.BASE_OLD, bad, frozen("base")).decision, GateDecision.REJECT)
        forged = fixtures.HAPPY_NEW.replace('"shots": 3})', '"shots": 3}, _site="main/run#0")')
        self.assertIn("subset_violation", gate(fixtures.BASE_OLD, forged, frozen("base")).kinds)
        self.assertIn("parse_error", gate(fixtures.BASE_OLD, "def main(:\n", frozen("base")).kinds)


class RuntimeDigestTests(unittest.TestCase):
    def test_changed_variable_passes_gate_and_stops_at_digest(self):
        g = gate(fixtures.BASE_OLD, fixtures.CHANGED_VARIABLE_NEW, frozen("base"))
        self.assertIs(g.decision, GateDecision.ACCEPT)
        rep = revise(fixtures.BASE_OLD, fixtures.CHANGED_VARIABLE_NEW, frozen("base"), INPUTS)
        self.assertIs(rep.run.outcome, RunOutcome.STOPPED_DIVERGENCE)
        self.assertEqual(rep.run.diverged, "main/for#0/run#0||0")
        self.assertEqual(rep.run.dispatch_count, 0)
        self.assertEqual(rep.run.orphans, [])            # stopped run: unreached, not orphans
        self.assertEqual(len(rep.run.unreached), 2)
        self.assertEqual(rep.dispatches_saved, 0)

    def test_fanout_path_shift_diverges(self):
        rep = revise(fixtures.FANOUT_OLD, fixtures.FANOUT_SHIFT_NEW, frozen("fanout"), INPUTS)
        self.assertIs(rep.gate.decision, GateDecision.ACCEPT)
        self.assertIs(rep.run.outcome, RunOutcome.STOPPED_DIVERGENCE)
        self.assertEqual(rep.run.diverged, "shot/run#0|0|0")
        self.assertEqual(rep.run.dispatch_count, 0)

    def test_fanout_append_is_new_work_only(self):
        rep = revise(fixtures.FANOUT_OLD, fixtures.FANOUT_APPEND_NEW, frozen("fanout"), INPUTS)
        self.assertIs(rep.run.outcome, RunOutcome.COMPLETED)
        self.assertEqual(sorted(rep.run.replayed),
                         ["shot/run#0|0|0", "shot/run#0|1|0", "shot/run#0|2|0"])
        self.assertEqual(rep.run.dispatched, ["shot/run#0|3|0", "main/run#0||0"])
        self.assertEqual(rep.dispatches_saved, 3)

    def test_occurrence_extension_repeat_policies(self):
        auto = revise(fixtures.RETRY_OLD, fixtures.RETRY_NEW, frozen("retry"), INPUTS)
        self.assertIs(auto.run.outcome, RunOutcome.STOPPED_REPEAT)
        self.assertEqual(auto.run.dispatch_count, 0)
        warn = revise(fixtures.RETRY_OLD, fixtures.RETRY_NEW, frozen("retry"), INPUTS,
                      repeat_policy=RepeatPolicy.WARN)
        self.assertIs(warn.run.outcome, RunOutcome.COMPLETED)
        self.assertEqual(len(warn.run.repeats), 2)


class OrphanTests(unittest.TestCase):
    def test_orphan_warn_default(self):
        rep = revise(fixtures.BASE_OLD, fixtures.ORPHAN_NEW, frozen("base"), INPUTS)
        self.assertIs(rep.gate.decision, GateDecision.ACCEPT)   # acceptance != full replay
        self.assertIs(rep.run.outcome, RunOutcome.COMPLETED_WITH_ORPHANS)
        self.assertEqual(rep.run.orphans, ["main/for#0/run#0||1", "main/for#0/run#0||2"])

    def test_orphan_stop_policy(self):
        rep = revise(fixtures.BASE_OLD, fixtures.ORPHAN_NEW, frozen("base"), INPUTS,
                     orphan_policy=OrphanPolicy.STOP)
        self.assertIs(rep.run.outcome, RunOutcome.STOPPED_ORPHAN)
        self.assertEqual(len(rep.run.orphans), 2)

    def test_replay_claim_only_for_invoked_identities(self):
        rep = revise(fixtures.BASE_OLD, fixtures.ORPHAN_NEW, frozen("base"), INPUTS)
        committed = set(load_ledger_text(frozen("base")).records)
        self.assertEqual(set(rep.run.replayed) | set(rep.run.orphans), committed)
        self.assertTrue(set(rep.run.replayed) <= set(rep.run.invoked))
        self.assertFalse(set(rep.run.orphans) & set(rep.run.invoked))


class LedgerUnavailableTests(unittest.TestCase):
    def test_unavailable_ledger_holds_gate_and_runtime(self):
        for bad in (None, "", "{not json", '{"version": 2}', '{"version": 1, "records": []}'):
            with self.subTest(bad=bad):
                g = gate(fixtures.BASE_OLD, fixtures.HAPPY_NEW, bad)
                self.assertIs(g.decision, GateDecision.HOLD)
                run = run_workflow(fixtures.HAPPY_NEW, bad, INPUTS)
                self.assertIs(run.outcome, RunOutcome.HELD_LEDGER_UNAVAILABLE)
                self.assertEqual(run.dispatch_count, 0)

    def test_conflicting_and_mismatched_ledgers_hold(self):
        for case in fixtures.cases():
            if case.required.startswith("5:"):
                with self.subTest(case=case.name):
                    rep = fixtures.run_case(case)
                    self.assertIs(rep.gate.decision, GateDecision.HOLD)
                    self.assertIs(rep.run.outcome, RunOutcome.HELD_LEDGER_UNAVAILABLE)
                    self.assertEqual(rep.run.dispatch_count, 0)


class FixtureSuiteTests(unittest.TestCase):
    def test_every_case_matches_expectation(self):
        for case in fixtures.cases():
            with self.subTest(case=case.name):
                rep = fixtures.run_case(case)
                self.assertIs(rep.gate.decision, case.expect_gate)
                self.assertIs(rep.run.outcome, case.expect_outcome)

    def test_required_fixtures_present(self):
        req = {c.required.split(":")[0] for c in fixtures.cases()}
        self.assertTrue({"1", "2", "3", "4", "5"} <= req)

    def test_no_repeated_dispatch_at_retained_identity_and_savings(self):
        s = fixtures.summary()
        self.assertEqual(s["totals"]["repeated_dispatch_at_retained_identity"], 0)
        self.assertGreater(s["totals"]["dispatches_saved_completed"], 0)
        self.assertLess(s["totals"]["contract_dispatches"], s["totals"]["naive_dispatches"])


class HygieneTests(unittest.TestCase):
    ALLOWED_CORE = {"ast", "hashlib", "json", "dataclasses", "enum", "typing", "collections"}
    BANNED_NEEDLES = ["22 repairs", "22 gate-passed", "258 identities", "258 committed",
                      "seven vs twelve", "7 vs 12", "7 vs. 12", "seven paid calls", "instead of twelve"]

    def _imports(self, path):
        tree = ast.parse((HERE / path).read_text(encoding="utf-8"))
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add((n.module or "").split(".")[0])
        return mods

    def test_import_allowlist(self):
        self.assertTrue(self._imports("contract.py") <= self.ALLOWED_CORE, self._imports("contract.py"))
        self.assertTrue(self._imports("fixtures.py") <= self.ALLOWED_CORE | {"contract", "pathlib"})
        forbidden = {"sqlite3", "subprocess", "socket", "urllib", "http", "hmac", "requests", "docker"}
        for f in ("contract.py", "fixtures.py"):
            self.assertFalse(self._imports(f) & forbidden, f)

    def test_no_permissive_vocabulary_in_api(self):
        names = [n.lower() for n in dir(contract)]
        for enum_cls in (GateDecision, RunOutcome, OrphanPolicy, RepeatPolicy):
            names += [m.name.lower() for m in enum_cls] + [m.value.lower() for m in enum_cls]
        for bad in ("allow", "approve", "permit"):
            self.assertFalse([n for n in names if bad in n], bad)

    def test_number_hygiene(self):
        for f in ("contract.py", "fixtures.py", "README.md", "NOTICE"):
            text = (HERE / f).read_text(encoding="utf-8").lower()
            for needle in self.BANNED_NEEDLES:
                self.assertNotIn(needle.lower(), text, f"{needle!r} in {f}")

    def test_readme_scope_strings(self):
        text = (HERE / "README.md").read_text(encoding="utf-8")
        for s in ("method sketch", "not Team OS law", "not village law",
                  "https://arxiv.org/abs/2611.06967", "experiments/2026-11-08/w17-revision-contract/",
                  "Not implemented", "UNVERIFIED", "Builder reflection", "Ludex",
                  "no code pin", "SQLite WAL", "Docker", "Host service", "Paid or live providers",
                  "HMAC", "Implementation may be complete; it is not declared verified."):
            self.assertIn(s.lower() if s == "no code pin" else s,
                          text.lower() if s == "no code pin" else text, s)
        self.assertTrue(("Cody" in text and "Naru" in text) or ("Ieum" in text and "Yeoul" in text))
        self.assertNotIn("KEEP", text)
        self.assertNotIn("CloudAgent", text)
        self.assertNotIn("(draft)", text)

    def test_notice_terms(self):
        text = (HERE / "NOTICE").read_text(encoding="utf-8")
        for s in ("perpetual non-exclusive", "not CC BY", "not a software grant",
                  "method-cite only", "No upstream code pin"):
            self.assertIn(s, text)


def _normalize(raw: str) -> str:
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", "", raw)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s))


class PaperEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.ev = json.loads((HERE / "paper_evidence.json").read_text(encoding="utf-8"))
        path = Path(os.environ.get("W17_PAPER_HTML", "/tmp/w17-2611.06967.html"))
        if not path.exists():
            self.skipTest("saved paper HTML not present; offline excerpt check skipped")
        self.raw = path.read_bytes()
        self.text = _normalize(self.raw.decode("utf-8"))

    def test_excerpts_found(self):
        same = hashlib.sha256(self.raw).hexdigest() == self.ev["fetched_html"]["sha256"]
        self.assertGreaterEqual(len(self.ev["excerpts"]), 10)
        for ex in self.ev["excerpts"]:
            with self.subTest(id=ex["id"]):
                self.assertIn(ex["text"], self.text)
                self.assertLessEqual(len(ex["text"]), 160)   # short quotes only
                if same:
                    win = self.text[ex["normalized_offset"]:ex["normalized_offset"] + ex["length"]]
                    self.assertEqual(win, ex["text"])
                    self.assertEqual(hashlib.sha256(win.encode("utf-8")).hexdigest(),
                                     ex["source_window_sha256"])

    def test_number_needles_are_paper_side_only(self):
        self.assertIn(self.ev["number_hygiene"]["paper_sentence_FOUND"], self.text)
        self.assertIsNone(self.ev["code_pin"])


if __name__ == "__main__":
    unittest.main()
