"""Offline tests for the SYNTHETIC role-contract admission sketch."""
import ast
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import unittest

import admission
from admission import AdmissionController, ContractTable, Message, RoleContract, Verdict
import fixtures

HERE = Path(__file__).resolve().parent
IMPLEMENTATION = ("admission.py", "fixtures.py")
PIN = "VishalPramanik/ATC @ fd8a2cb4638fe8c9f4e12742d1d5e6c523e25e8d"
BANNER = "The code for ATC will be available soon."
PAPER_NUMBERS = {"74.6", "91.8", "76.4", "93.5", "0.11", "1.47", "72.6%"}


def evidence():
    return json.loads((HERE / "paper_evidence.json").read_text())


class AdmissionTests(unittest.TestCase):
    def test_every_out_of_role_act_rejected_and_in_role_admitted(self):
        for contract in fixtures.TABLE.contracts:
            others = set().union(*(c.speech_acts for c in fixtures.TABLE.contracts)) - contract.speech_acts
            for act in sorted(contract.speech_acts):
                gate = fixtures.controller()
                message = Message("in-" + act, contract.role, (act,))
                self.assertEqual(gate.propose(message).verdict, Verdict.ADMITTED)
                self.assertEqual(gate.context.entries, (message,))
            for act in sorted(others):
                gate = fixtures.controller()
                first = sorted(contract.speech_acts)[0]
                message = Message("out-" + act, contract.role, (first, act))
                decision = gate.propose(message)
                self.assertEqual(decision.verdict, Verdict.REJECTED)
                self.assertEqual(decision.out_of_role, (act,))
                self.assertEqual(gate.context.entries, ())
        gate = fixtures.controller()
        self.assertEqual(gate.propose(fixtures.UNKNOWN_ROLE).reason, "unknown-role")
        self.assertEqual(gate.context.entries, ())

    def test_revision_admitted_only_after_recheck(self):
        gate = fixtures.controller()
        gate.propose(fixtures.OUT_OF_ROLE, 0)
        self.assertEqual(gate.status("m-out-of-role", 0), Verdict.HELD)
        gate.revise(fixtures.REVISED_IN_ROLE)
        self.assertEqual(gate.status("m-out-of-role", 1), Verdict.HELD)
        self.assertEqual(gate.context.entries, ())
        decision = gate.recheck("m-out-of-role", 1)
        self.assertEqual((decision.verdict, decision.revision), (Verdict.ADMITTED, 1))
        self.assertEqual(gate.context.entries, (fixtures.REVISED_IN_ROLE,))
        self.assertNotIn(fixtures.OUT_OF_ROLE, gate.context.entries)
        with self.assertRaises(ValueError):
            gate.recheck("m-out-of-role", 1)

    def test_missing_recheck_never_admits(self):
        gate = fixtures.controller()
        gate.propose(fixtures.SILENT, 0)
        gate.revise(fixtures.REVISED_SILENT)
        self.assertEqual(gate.expire(2), ())
        self.assertEqual(gate.status("m-silent", 2), Verdict.HELD)
        expired = gate.expire(3)
        self.assertEqual([(d.verdict, d.reason) for d in expired],
                         [(Verdict.HELD, "missing-recheck-timeout")])
        self.assertEqual(gate.status("m-silent", 9), Verdict.HELD)
        self.assertEqual(gate.context.entries, ())
        with self.assertRaises(ValueError):
            gate.recheck("m-silent", 3)
        no_revision = fixtures.controller()
        no_revision.propose(fixtures.OUT_OF_ROLE, 0)
        self.assertEqual(no_revision.expire(5)[0].reason, "no-revision-timeout")
        self.assertEqual(no_revision.context.entries, ())

    def test_failed_recheck_never_admits(self):
        gate = fixtures.controller()
        gate.propose(fixtures.DRIFT, 0)
        gate.revise(fixtures.REVISED_STILL_OUT)
        decision = gate.recheck("m-drift", 1)
        self.assertEqual((decision.verdict, decision.reason), (Verdict.REJECTED, "failed-recheck"))
        self.assertEqual(gate.status("m-drift", 1), Verdict.REJECTED)
        self.assertEqual(gate.context.entries, ())
        with self.assertRaises(ValueError):
            gate.revise(Message("m-drift", "reviewer", ("CRITIQUE",), revision=2))
        multi = AdmissionController(fixtures.TABLE, 2, max_revisions=2)
        multi.propose(fixtures.DRIFT, 0)
        multi.revise(fixtures.REVISED_STILL_OUT)
        self.assertEqual(multi.recheck("m-drift", 1).verdict, Verdict.REJECTED)
        self.assertEqual(multi.status("m-drift", 1), Verdict.HELD)
        multi.revise(Message("m-drift", "reviewer", ("CRITIQUE",), revision=2))
        self.assertEqual(multi.recheck("m-drift", 2).verdict, Verdict.ADMITTED)
        self.assertEqual(multi.context.ids(), (("m-drift", 2),))

    def test_timeout_never_admits(self):
        gate = fixtures.controller()
        gate.propose(fixtures.SLOW, 0)
        gate.revise(fixtures.REVISED_SLOW)
        late = gate.recheck("m-slow", 3)
        self.assertEqual((late.verdict, late.reason), (Verdict.HELD, "recheck-timeout"))
        flagged = fixtures.controller()
        flagged.propose(fixtures.SLOW, 0)
        flagged.revise(fixtures.REVISED_SLOW)
        self.assertEqual(flagged.recheck("m-slow", 1, check_timed_out=True).verdict, Verdict.HELD)
        first = fixtures.controller()
        self.assertEqual(first.propose(fixtures.IN_ROLE, 0, check_timed_out=True).verdict,
                         Verdict.HELD)
        for g in (gate, flagged, first):
            self.assertEqual(g.context.entries, ())
        on_time = fixtures.controller()
        on_time.propose(fixtures.SLOW, 0)
        on_time.revise(fixtures.REVISED_SLOW)
        self.assertEqual(on_time.recheck("m-slow", 2).verdict, Verdict.ADMITTED)

    def test_shared_context_holds_only_admitted_messages(self):
        gate, lines = fixtures.run_demo()
        admitted = {(d.message_id, d.revision) for d in gate.decisions
                    if d.verdict is Verdict.ADMITTED}
        self.assertEqual(set(gate.context.ids()), admitted)
        self.assertEqual(gate.context.ids(), (("m-in-role", 0), ("m-out-of-role", 1)))
        for message in (fixtures.OUT_OF_ROLE, fixtures.UNKNOWN_ROLE, fixtures.DRIFT,
                        fixtures.REVISED_STILL_OUT, fixtures.SLOW, fixtures.REVISED_SLOW,
                        fixtures.SILENT, fixtures.REVISED_SILENT):
            self.assertNotIn(message, gate.context.entries)
        for entry in gate.context.entries:
            self.assertTrue(admission.check_acts(fixtures.TABLE, entry.role, entry.acts).in_role)
        self.assertTrue(all(line.startswith("SYNTHETIC") for line in lines[:-1]))

    def test_records_immutable(self):
        decision = fixtures.controller().propose(fixtures.IN_ROLE)
        for record, field, value in [(fixtures.IN_ROLE, "acts", ("APPROVE",)),
                                     (fixtures.TABLE.contracts[0], "speech_acts", frozenset()),
                                     (fixtures.TABLE, "contracts", ()),
                                     (decision, "verdict", Verdict.REJECTED)]:
            with self.assertRaises(FrozenInstanceError):
                setattr(record, field, value)
        listed = Message("listed", "researcher", ["INFORM"])
        self.assertIsInstance(listed.acts, tuple)
        self.assertIsInstance(RoleContract("r", ["A"]).speech_acts, frozenset)
        gate = fixtures.controller()
        gate.propose(fixtures.IN_ROLE)
        self.assertIsInstance(gate.context.entries, tuple)
        self.assertIsInstance(gate.decisions, tuple)

    def test_invalid_inputs(self):
        bad = [lambda: Message("", "researcher", ("INFORM",)),
               lambda: Message("x", "researcher", ()),
               lambda: Message("x", "researcher", "INFORM"),
               lambda: Message("x", "researcher", ("",)),
               lambda: Message("x", "researcher", ("INFORM",), revision=-1),
               lambda: RoleContract("", ("A",)),
               lambda: RoleContract("r", ()),
               lambda: ContractTable(()),
               lambda: ContractTable((RoleContract("r", ("A",)), RoleContract("r", ("B",)))),
               lambda: AdmissionController(fixtures.TABLE, -1),
               lambda: AdmissionController(fixtures.TABLE, 2, max_revisions=0),
               lambda: AdmissionController("table")]
        for build in bad:
            with self.assertRaises(ValueError):
                build()
        gate = fixtures.controller()
        with self.assertRaises(ValueError):
            gate.propose(fixtures.REVISED_IN_ROLE)
        with self.assertRaises(ValueError):
            gate.propose(fixtures.IN_ROLE, -1)
        gate.propose(fixtures.IN_ROLE)
        with self.assertRaises(ValueError):
            gate.propose(fixtures.IN_ROLE)
        with self.assertRaises(ValueError):
            gate.revise(Message("m-in-role", "researcher", ("INFORM",), revision=1))
        gate.propose(fixtures.OUT_OF_ROLE)
        with self.assertRaises(ValueError):
            gate.recheck("m-out-of-role", 1)
        with self.assertRaises(ValueError):
            gate.revise(Message("m-out-of-role", "reviewer", ("QUERY",), revision=1))
        with self.assertRaises(ValueError):
            gate.revise(Message("m-out-of-role", "researcher", ("QUERY",), revision=2))
        gate.revise(fixtures.REVISED_IN_ROLE)
        with self.assertRaises(ValueError):
            gate.revise(fixtures.REVISED_IN_ROLE)
        with self.assertRaises(ValueError):
            gate.status("never-seen", 0)

    def test_no_permission_path_or_public_names(self):
        self.assertEqual({v.value for v in Verdict}, {"ADMITTED", "REJECTED", "HELD"})
        forbidden = ("allow", "approve", "permit", "grant", "release", "certificate", "success")
        for filename in IMPLEMENTATION:
            tree = ast.parse((HERE / filename).read_text())
            names = [n.name for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
            names += [n.id for n in ast.walk(tree)
                      if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
            names += [n.target.id for n in ast.walk(tree)
                      if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]
            for name in names:
                self.assertFalse(any(word in name.lower() for word in forbidden), (filename, name))
            self.assertNotIn('"ALLOW"', (HERE / filename).read_text())
        public = [n for n in dir(admission) if not n.startswith("_")]
        public += [n for n in dir(AdmissionController) if not n.startswith("_")]
        for name in public:
            self.assertFalse(any(word in name.lower() for word in forbidden), name)


class HygieneEvidenceTests(unittest.TestCase):
    def test_ast_import_allowlist_and_no_dynamic_execution(self):
        permitted = {"dataclasses", "enum", "admission"}
        for filename in IMPLEMENTATION:
            tree = ast.parse((HERE / filename).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(a.name in permitted for a in node.names), filename)
                if isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, permitted)
                    self.assertEqual(node.level, 0)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"exec", "eval", "compile", "__import__", "open"})

    def test_implementation_string_bans(self):
        common = ("miniwob", "openai", "anthropic", "xai_api_key", "inspect_ai", "inspect ai",
                  "sqlite3", "docker", "nats", "two-ledger", "two_ledger", "hmac-manifest",
                  "hmac_manifest", "voting", "ensemble", "huggingface", "smith copies",
                  "the cloudagent", "wave15 evidence-gated authority implemented")
        code_only = ("requests", "urllib", "http://", "https://", "socket", "subprocess",
                     "threading", "asyncio", "torch", "numpy", "embedding", "energy",
                     "leakage", "encoder", "regenerat", "w16-blast-radius",
                     "w16-overseer-flip", "w16-fail-signatures")
        claims = ("implements role-drift energy", "energy is implemented", "leakage is implemented",
                  "encoder is implemented", "implements constrained regeneration",
                  "we reproduce", "reproduced results:", "universally guarantees")
        for filename in (*IMPLEMENTATION, "README.md", "NOTICE"):
            source = (HERE / filename).read_text().lower()
            needles = common + claims + (code_only if filename in IMPLEMENTATION else ())
            for needle in needles:
                self.assertNotIn(needle, source, (filename, needle))

    def test_paper_numbers_distinct_non_targets_not_implementation_or_readme(self):
        hygiene = evidence()["number_hygiene"]
        self.assertTrue(hygiene["not_targets"])
        self.assertTrue(hygiene["not_reproduced"])
        quantities = {q["value"]: q for q in hygiene["quantities"]}
        self.assertEqual(set(quantities), PAPER_NUMBERS)
        self.assertEqual(len({(q["kind"], q["configuration"]) for q in quantities.values()}),
                         len(PAPER_NUMBERS))
        for filename in (*IMPLEMENTATION, "README.md", "NOTICE"):
            source = (HERE / filename).read_text()
            for needle in PAPER_NUMBERS:
                self.assertNotIn(needle, source, (filename, needle))

    def test_short_attributed_offline_evidence(self):
        ev = evidence()
        self.assertEqual(ev["authors"], ["Maisha Maliha", "Vishal Pramanik", "Sumit Kumar Jha"])
        self.assertEqual(ev["version"], "2611.04321v1")
        self.assertEqual(ev["source_url"], "https://arxiv.org/html/2611.04321")
        self.assertRegex(ev["html_sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(ev["license_line"], "License: CC BY 4.0")
        self.assertTrue(ev["license_found_in_html"])
        self.assertIn("does not grant software rights", ev["license_scope_note"])
        excerpts = ev["html_excerpts"]
        self.assertTrue(4 <= len(excerpts) <= 6)
        self.assertLess(sum(len(e["text"].split()) for e in excerpts), 100)
        for excerpt in excerpts:
            self.assertTrue(excerpt["found_after_tag_strip_whitespace_collapse"])
            self.assertTrue(excerpt["text"].isascii())
            self.assertTrue(excerpt["section"])
        stored = " ".join(e["text"] for e in excerpts)
        for checked in ("point where a message would enter the shared conversation",
                        "re-checked before admission", "not permitted to make",
                        "encode, score, correct, regenerate, and re-evaluate",
                        "constrained revision call"):
            self.assertIn(checked, stored)
        for part in ("role-drift energy", "cross-role leakage", "behavior encoder",
                     "constrained regeneration"):
            self.assertIn(part, ev["not_implemented_paper_components"])
        self.assertIn("not the full ATC method", ev["modelling_note"])

    def test_stub_pin_banner_and_licence_absence_recorded(self):
        ev = evidence()
        self.assertEqual(ev["upstream_code_pin"], PIN)
        self.assertEqual(ev["stub_readme"], "# " + BANNER)
        self.assertEqual(ev["stub_tree_at_pin"], ["README.md"])
        self.assertIsNone(ev["stub_license"])
        checks = ev["stub_license_checks"]
        self.assertIsNone(checks["github_api_repo_license_field"])
        self.assertEqual(checks["raw_LICENSE_at_pin_http"], 404)
        self.assertIn(PIN.split(" @ ")[1], checks["raw_LICENSE_url"])
        notice = (HERE / "NOTICE").read_text()
        for phrase in (PIN, BANNER, "LICENSE 404", "null", "does not relicense",
                       "grants no software rights", "Method-cite only"):
            self.assertIn(phrase, " ".join(notice.split()))

    def test_readme_scope_without_sibling_day_file(self):
        source = (HERE / "README.md").read_text()
        lower = source.lower()
        for phrase in ("KEEP Soft", "paper-method only", "method-cite", "Not Team OS law",
                       "not the same as, Wave15 Evidence-Gated Authority",
                       "generic role-gating collapse would not be this paper",
                       "not a reproduction", "Maisha Maliha", "Vishal Pramanik", "Sumit Kumar Jha",
                       "CC BY 4.0", "does not grant software rights", "coming-soon stub",
                       BANNER, PIN.split(" @ ")[1], "UNVERIFIED", "synthetic", "w16-s1",
                       "taxonomy", "intervention point", "upstream behavior"):
            self.assertIn(phrase.lower(), lower, phrase)
        for part in ("role-drift energy", "cross-role leakage", "behavior encoder",
                     "constrained regeneration"):
            self.assertIn(part, lower.split("## what the sketch does not do")[1])
        self.assertIn("Implementation may be complete; it is not declared verified.", source)
        self.assertNotIn("KEEP Top", source)
        self.assertNotIn("ALLOW", source)


if __name__ == "__main__":
    unittest.main()
