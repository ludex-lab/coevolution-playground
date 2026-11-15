"""Offline construction and provenance tests; not empirical routing accuracy."""
import ast
from dataclasses import FrozenInstanceError, replace
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import unittest

from routing import (Action, Choice, Proposal, Reason, RegisteredObject, Rule,
                     Snapshot, State, Verdict, route, unsafe_fallback_baseline)
from fixtures import BLOCKED, CASES, READY, SNAPSHOT, compare, proposal, unsafe_object

HERE = Path(__file__).resolve().parent
PIN = "c6c59e48784e6d4e0a368c46e706ce6dc0136bce"


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def normalize(raw):
    parser = Text()
    parser.feed(raw.decode())
    return " ".join(" ".join(parser.parts).split())


class RoutingTests(unittest.TestCase):
    def test_permitted_primary(self):
        p = proposal("paint", "tile-blue")
        result = route(p, SNAPSHOT, READY)
        self.assertIs(result.verdict, Verdict.DISPATCH)
        self.assertEqual((result.dispatch.action, result.dispatch.object_id), ("paint", "tile-blue"))
        self.assertEqual(result.committed, p.primary)
        self.assertEqual(result.versions, SNAPSHOT.versions)
        self.assertEqual(result.rule_id, "paint-ready")

    def test_rule_block_and_missing_state_flag(self):
        for state in (BLOCKED, replace(READY, flags=(("online", True),))):
            with self.subTest(state=state):
                result = route(proposal("paint", "tile-blue"), SNAPSHOT, state)
                self.assertIs(result.verdict, Verdict.NON_DISPATCH)
                self.assertIs(result.reason, Reason.STATE_BLOCK)
                self.assertIsNone(result.dispatch)

    def test_unregistered_object(self):
        result = route(proposal("paint", "tile-ghost"), SNAPSHOT, READY)
        self.assertIs(result.reason, Reason.UNREGISTERED_OBJECT)
        self.assertIs(result.verdict, Verdict.NON_DISPATCH)
        self.assertIsNone(result.dispatch)

    def test_incompatible_and_missing_object(self):
        for obj, reason in (("bell-small", Reason.OBJECT_TYPE), (None, Reason.OBJECT_REQUIRED)):
            result = route(proposal("paint", obj), SNAPSHOT, READY)
            self.assertIs(result.reason, reason)
            self.assertIs(result.verdict, Verdict.NON_DISPATCH)
            self.assertIsNone(result.dispatch)

    def test_object_free_contract(self):
        self.assertIs(route(proposal("wave", None), SNAPSHOT, READY).verdict, Verdict.DISPATCH)
        result = route(proposal("wave", "tile-blue"), SNAPSHOT, READY)
        self.assertIs(result.reason, Reason.OBJECT_FORBIDDEN)
        self.assertIsNone(result.dispatch)

    def test_unknown_action_and_missing_rule(self):
        result = route(proposal("teleport", None), SNAPSHOT, READY)
        self.assertIs(result.reason, Reason.UNKNOWN_ACTION)
        self.assertIsNone(result.dispatch)
        no_paint = replace(SNAPSHOT, rules=tuple(r for r in SNAPSHOT.rules if r.action != "paint"))
        result = route(proposal("paint", "tile-blue"), no_paint, READY)
        self.assertIs(result.reason, Reason.MISSING_RULE)
        self.assertIsNone(result.dispatch)

    def test_blocked_primary_never_substitutes_valid_secondary(self):
        p = proposal("paint", "tile-blue", Choice("describe", "tile-blue"))
        result = route(p, SNAPSHOT, BLOCKED)
        self.assertIs(result.verdict, Verdict.NON_DISPATCH)
        self.assertEqual(result.committed, p.primary)
        self.assertEqual(result.audit_candidates, p.candidates)
        self.assertIsNone(result.dispatch)
        foil = unsafe_fallback_baseline(p, SNAPSHOT, BLOCKED)
        self.assertIs(foil.verdict, Verdict.DISPATCH)
        self.assertEqual(foil.dispatch.action, "describe")
        self.assertFalse(unsafe_object(foil.dispatch))
        self.assertEqual(foil.committed, p.primary)

    def test_fallback_object_bypass_and_next_candidate_scan(self):
        for obj in ("tile-ghost", "bell-small"):
            p = proposal("paint", "tile-blue", Choice("teleport", None), Choice("describe", obj))
            gate = route(p, SNAPSHOT, BLOCKED)
            foil = unsafe_fallback_baseline(p, SNAPSHOT, BLOCKED)
            self.assertIs(gate.verdict, Verdict.NON_DISPATCH)
            self.assertIsNone(gate.dispatch)
            self.assertIs(foil.verdict, Verdict.DISPATCH)
            self.assertTrue(unsafe_object(foil.dispatch))
            self.assertEqual(foil.dispatch.object_id, obj)
        p = proposal("describe", "tile-ghost", Choice("paint", "tile-blue"))
        self.assertIs(unsafe_fallback_baseline(p, SNAPSHOT, BLOCKED).verdict, Verdict.NON_DISPATCH)

    def test_successful_primary_ignores_candidate_semantics(self):
        base = route(proposal("paint", "tile-blue"), SNAPSHOT, READY)
        for alt in (Choice("describe", "tile-ghost"), Choice("teleport", None), Choice("ring", "tile-blue")):
            p = proposal("paint", "tile-blue", alt)
            result = route(p, SNAPSHOT, READY)
            self.assertEqual(result.dispatch, base.dispatch)
            self.assertEqual(result.reason, base.reason)
            self.assertEqual(unsafe_fallback_baseline(p, SNAPSHOT, READY), result)

    def test_frozen_suite_oracle_and_counts(self):
        for case in CASES:
            with self.subTest(case=case.name):
                gate = route(case.proposal, SNAPSHOT, case.state)
                foil = unsafe_fallback_baseline(case.proposal, SNAPSHOT, case.state)
                self.assertIs(gate.verdict, case.expected_gate)
                self.assertIs(foil.verdict, case.expected_baseline)
                self.assertFalse(unsafe_object(gate.dispatch))
                self.assertEqual(unsafe_object(foil.dispatch), case.expected_unsafe_object)
                substituted = foil.dispatch is not None and (
                    foil.dispatch.action, foil.dispatch.object_id) != (
                        case.proposal.primary.action, case.proposal.primary.object_id)
                self.assertEqual(substituted, case.expected_substitution)
                if gate.dispatch is not None:
                    self.assertEqual((gate.dispatch.action, gate.dispatch.object_id),
                                     (case.proposal.primary.action, case.proposal.primary.object_id))
                else:
                    self.assertIs(gate.verdict, Verdict.NON_DISPATCH)
        self.assertEqual(compare(), dict(cases=12, gate_dispatches=3, baseline_dispatches=8,
                         gate_unsafe_objects=0, baseline_unsafe_objects=3,
                         gate_substitutions=0, baseline_substitutions=5))
        self.assertEqual(compare(), compare())

    def test_version_and_time_mismatch(self):
        p = proposal("paint", "tile-blue", Choice("wave", None))
        for i in range(4):
            changed = list(p.versions)
            changed[i] = "stale.v0"
            invalid = replace(p, versions=tuple(changed))
            for controller in (route, unsafe_fallback_baseline):
                result = controller(invalid, SNAPSHOT, READY)
                self.assertIs(result.reason, Reason.VERSION_MISMATCH)
                self.assertIsNone(result.dispatch)
        for state in (replace(READY, version="stale.v0"), replace(READY, frozen_time="stale")):
            for controller in (route, unsafe_fallback_baseline):
                result = controller(p, SNAPSHOT, state)
                self.assertIs(result.reason, Reason.VERSION_MISMATCH)
                self.assertIsNone(result.dispatch)

    def test_immutability_and_invalid_inputs(self):
        p = proposal("paint", "tile-blue")
        for obj, field, value in ((p, "primary", Choice("wave", None)),
                                   (SNAPSHOT, "rules", ()), (READY, "flags", ()),
                                   (SNAPSHOT.actions[0], "object_types", ()),
                                   (SNAPSHOT.rules[0], "required_flags", ()),
                                   (SNAPSHOT.objects[0], "kind", "bell")):
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, field, value)
        bad_constructors = (
            lambda: Choice("", None), lambda: Choice("paint", []),
            lambda: Choice("paint", "x" * 81), lambda: Action("paint", ["tile"]),
            lambda: State("v1", "time", (("online", 1),)),
            lambda: State("v1", "time", (("online", True), ("online", False))),
            lambda: Proposal(p.primary, [], p.versions),
            lambda: Proposal(p.primary, (p.primary,), p.versions),
            lambda: replace(SNAPSHOT, actions=()),
            lambda: replace(SNAPSHOT, objects=(SNAPSHOT.objects[0], SNAPSHOT.objects[0])),
            lambda: replace(SNAPSHOT, rules=(Rule("x", "teleport", ()),)),
            lambda: replace(SNAPSHOT, rules=(Rule("x", "paint", ()), Rule("y", "paint", ()))),
        )
        for construct in bad_constructors:
            with self.assertRaises(ValueError):
                construct()
        for args in ((None, SNAPSHOT, READY), ({}, SNAPSHOT, READY),
                     (p, None, READY), (p, SNAPSHOT, {})):
            for controller in (route, unsafe_fallback_baseline):
                result = controller(*args)
                self.assertIs(result.reason, Reason.INVALID_INPUT)
                self.assertIsNone(result.dispatch)

    def test_import_allowlist_and_number_hygiene(self):
        source = (HERE / "routing.py").read_text()
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(x.name for x in node.names)
            if isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                imports.append(node.module)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"exec", "eval", "__import__", "open", "compile"})
        self.assertTrue(imports)
        self.assertLessEqual(set(imports), {"dataclasses", "enum", "typing", "collections"})
        figures = ("97.5", "95.5", "94.0", "41.0", "1,960", "1960")
        for filename in ("routing.py", "fixtures.py", "README.md", "NOTICE"):
            content = (HERE / filename).read_text()
            for needle in figures:
                self.assertNotIn(needle, content, (filename, needle))
        for filename in ("routing.py", "fixtures.py"):
            content = (HERE / filename).read_text()
            for needle in ("not implemented", "OpenAICompatibleBackend", "receipt replay", "600", "200", "166"):
                self.assertNotIn(needle.lower(), content.lower(), (filename, needle))

    def test_paper_found_excerpts_offline(self):
        evidence = json.loads((HERE / "paper_evidence.json").read_text())
        self.assertEqual(evidence["html_sha256"], "28ce09393c884680dc8a094542b1d8d1756951d6a4e76a01aaedf1fb268ab25b")
        self.assertEqual(len(evidence["excerpts"]), 12)
        path = Path(os.environ.get("ROUTEBR_PAPER_HTML", "/tmp/routebr_paper.html"))
        if "ROUTEBR_PAPER_HTML" in os.environ:
            self.assertTrue(path.is_file(), "Explicit full-source path must exist")
        raw = path.read_bytes() if path.is_file() else None
        if raw is not None:
            self.assertEqual(hashlib.sha256(raw).hexdigest(), evidence["html_sha256"])
            full = normalize(raw)
        for excerpt in evidence["excerpts"]:
            self.assertTrue(excerpt["found"])
            self.assertIn("Cao et al.", excerpt["attribution"])
            self.assertTrue(excerpt["where"])
            self.assertIn(excerpt["quote"], excerpt["source_window"])
            self.assertEqual(hashlib.sha256(excerpt["source_window"].encode()).hexdigest(),
                             excerpt["source_window_sha256"])
            if raw is not None:
                self.assertIn(excerpt["quote"], full)
                offset = excerpt["normalized_offset"]
                self.assertEqual(full[offset:offset + len(excerpt["quote"])], excerpt["quote"])
        self.assertIn("UNVERIFIED", evidence["number_hygiene"]["status"])
        self.assertIn("never targets", evidence["number_hygiene"]["status"])

    def test_pin_licenses_real_code_and_recorded_upstream_checks(self):
        evidence = json.loads((HERE / "paper_evidence.json").read_text())
        upstream = evidence["upstream"]
        self.assertEqual(upstream["pin"], PIN)
        self.assertEqual(upstream["parent"], "f93cbca48117362d1e1a44bc2b0ba181e4212adc")
        self.assertEqual(upstream["license"], "MIT")
        self.assertTrue(upstream["license_file_present"])
        self.assertIn("MIT License", upstream["license_excerpt"])
        self.assertIn("Copyright (c) 2026 +", upstream["license_excerpt"])
        self.assertEqual(upstream["stub_or_code"], "real MIT code (not a coming-soon stub)")
        self.assertEqual(evidence["paper_license"], "arXiv.org perpetual non-exclusive license")
        self.assertEqual(upstream["offline_unittest"]["passed"], 10)
        self.assertEqual(upstream["offline_unittest"]["exit_code"], 0)
        self.assertIn("Ran 10 tests", (HERE / "upstream-unittest.txt").read_text())
        self.assertIn("\nOK\n", (HERE / "upstream-unittest.txt").read_text())
        self.assertEqual(upstream["offline_validator"]["result"], "PASSED")
        self.assertIn("\nPASSED\n", (HERE / "upstream-validator.txt").read_text())

    def test_readme_scope_and_omissions(self):
        readme = (HERE / "README.md").read_text()
        for text in ("method sketch", "not Team OS law", "not village law", PIN,
                     "https://arxiv.org/abs/2611.07534", "https://github.com/YgcCoder/RouteBR",
                     "experiments/2026-11-08/01-routebr/", "Not implemented", "UNVERIFIED",
                     "format-only repair", "Builder reflection", "Ludex", "Cody/Naru"):
            self.assertIn(text, readme)
        self.assertNotIn("KEEP", readme)
        self.assertNotIn("CloudAgent", readme)
        self.assertTrue(readme.rstrip().endswith("Implementation may be complete; it is not declared verified."))
        self.assertFalse(hasattr(Verdict, "ALLOW"))
        self.assertEqual(set(Verdict), {Verdict.DISPATCH, Verdict.NON_DISPATCH})


if __name__ == "__main__":
    unittest.main()
