"""Tests for the w18-skill-assurance method sketch (stdlib unittest only).

Run: python3 -m unittest test_assurance.py -v
The excerpt checks read /tmp/w18-2611.07652.html (paper HTML) and
/tmp/w18-skillware-README.md (README at the pin) and are skipped when absent.
"""

import contextlib
import hashlib
import html
import io
import json
import os
import re
import unittest

import assurance as A
import effect
import fixtures as F

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_HTML = "/tmp/w18-2611.07652.html"
PIN_README = "/tmp/w18-skillware-README.md"
IMPL = ("effect.py", "assurance.py", "fixtures.py", "manifest.json")
PROSE = ("README.md", "NOTICE")


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def evidence():
    return json.loads(read("paper_evidence.json"))


def normalize(raw):
    t = raw
    for tag in ("script", "style", "math"):
        t = re.sub(r"<%s\b.*?</%s>" % (tag, tag), "", t, flags=re.DOTALL | re.IGNORECASE)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t)


def registered_good():
    skills = F.build_skills()
    reg = A.Registry()
    reg.hold(skills["pack_cart"])
    res = reg.register("pack_cart")
    return reg, skills["pack_cart"], res


class Manifest(unittest.TestCase):

    def test_manifest_is_well_formed(self):
        m = A.load_manifest()
        self.assertEqual(A.check_manifest(m), [])
        self.assertEqual(m["skill_id"], "pack_cart")

    def test_manifest_declares_contract_and_boundary(self):
        m = A.load_manifest()
        out = {f["name"]: f for f in m["output_contract"]["fields"]}
        self.assertEqual(out["crates"]["maximum"], 10)
        self.assertEqual(m["input_contract"]["extra_fields"], "reject")
        b = m["safety_boundary"]
        self.assertIn("bin_key", b["forbidden_output_fields"])
        self.assertTrue(b["no_runtime_code_synthesis"])
        self.assertTrue(b["deterministic"])

    def test_bad_manifest_rejected(self):
        m = json.loads(read("manifest.json"))
        m["input_contract"]["fields"][0].pop("maximum")
        m["output_contract"]["extra_fields"] = "keep"
        problems = A.check_manifest(m)
        self.assertTrue(any("minimum <= maximum" in p for p in problems))
        self.assertTrue(any("extra_fields" in p for p in problems))


class A_ContractedShape(unittest.TestCase):

    def test_valid_input_returns_contracted_shape(self):
        reg, skill, res = registered_good()
        self.assertEqual(res["status"], "registered")
        out = reg.invoke("pack_cart", F.GOOD_INPUT)
        self.assertEqual(out, {"crates": 7, "bin": "east"})
        self.assertEqual(A.check_against(F.MANIFEST["output_contract"], out, "output"), [])

    def test_every_derived_probe_is_in_contract_for_good_effect(self):
        reg, skill, _ = registered_good()
        for probe in A.derive_probes(F.MANIFEST):
            out = reg.invoke("pack_cart", probe)
            self.assertLessEqual(out["crates"], 10)
            self.assertEqual(set(out), {"crates", "bin"})

    def test_effect_is_deterministic_and_pure(self):
        p = {"sacks": 8, "bin": "south", "spare": True}
        snapshot = dict(p)
        self.assertEqual(effect.pack_cart(p), effect.pack_cart(p))
        self.assertEqual(p, snapshot)
        self.assertEqual(effect.pack_cart(p), {"crates": 10, "bin": "south"})


class B_RejectedBeforeEffect(unittest.TestCase):

    def test_out_of_contract_inputs_never_reach_effect(self):
        reg, skill, _ = registered_good()
        before = skill.calls
        for label, payload in F.OUT_OF_CONTRACT:
            with self.subTest(label):
                with self.assertRaises(A.Rejected):
                    reg.invoke("pack_cart", payload)
                self.assertEqual(skill.calls, before, label)

    def test_spy_effect_untouched(self):
        hits = []

        def spy(payload):
            hits.append(payload)
            return {"crates": 0, "bin": "south"}

        reg = A.Registry()
        sk = A.Skill(F.manifest_for("spy"), spy, [("ok", lambda call: True)])
        reg.hold(sk)
        self.assertEqual(reg.register("spy")["status"], "registered")
        hits.clear()
        with self.assertRaises(A.Rejected):
            reg.invoke("spy", {"sacks": 9, "bin": "south", "spare": False})
        self.assertEqual(hits, [])

    def test_bool_is_not_integer(self):
        v = A.check_against(F.MANIFEST["input_contract"],
                            {"sacks": True, "bin": "south", "spare": False}, "input")
        self.assertTrue(any("not integer" in x for x in v))

    def test_in_contract_input_does_reach_effect(self):
        reg, skill, _ = registered_good()
        before = skill.calls
        reg.invoke("pack_cart", F.SMALL)
        self.assertEqual(skill.calls, before + 1)


class C_ContractDerived(unittest.TestCase):

    def setUp(self):
        self.skills = F.build_skills()

    def test_author_checks_pass_but_assurance_fails(self):
        for sid in F.BROKEN:
            with self.subTest(sid):
                author = A.run_author_checks(self.skills[sid])
                self.assertTrue(author and all(r["passed"] for r in author))
                self.assertEqual(A.detect(self.skills[sid])["status"], "fail")

    def test_doubling_example_not_tautological(self):
        sk = self.skills["pack_cart_double"]
        # The author's check uses a small in-contract input whose output is
        # inside the declared maximum, so it passes and says nothing about it.
        self.assertEqual(sk.call(F.SMALL)["crates"], 6)
        self.assertLessEqual(6, 10)
        self.assertTrue(all(r["passed"] for r in A.run_author_checks(sk)))
        report = A.detect(sk)
        failing = [f["probe"] for f in report["failing_probes"]]
        self.assertIn({"sacks": 8, "bin": "south", "spare": False}, failing)
        self.assertNotIn(F.SMALL, failing)
        for probe in failing:
            self.assertEqual(A.check_against(F.MANIFEST["input_contract"], probe, "input"), [])
        self.assertTrue(any("above declared maximum 10" in v
                            for f in report["failing_probes"] for v in f["violations"]))

    def test_rejection_follows_the_declared_number(self):
        wider = A.Skill(F.manifest_for("pack_cart_double", output_contract__crates__maximum=18),
                        F.pack_cart_double)
        self.assertEqual(A.detect(wider)["status"], "pass")
        tighter = A.Skill(F.manifest_for("pack_cart", output_contract__crates__maximum=9),
                          effect.pack_cart)
        self.assertEqual(A.detect(tighter)["status"], "fail")

    def test_author_check_cannot_tell_good_from_broken(self):
        # The same author check (three sacks, three crates) passes on the good
        # effect and on three broken ones: it does not see the boundary.
        check = F.author_check(3, F.SMALL)
        for sid in ("pack_cart", "pack_cart_east_spill", "pack_cart_empty_key", "pack_cart_synth"):
            self.assertTrue(check(self.skills[sid].effect), sid)

    def test_each_boundary_kind_detected(self):
        expect = {
            "pack_cart_double": "above declared maximum",
            "pack_cart_east_spill": "forbidden value bin='north'",
            "pack_cart_empty_key": "forbidden output field 'bin_key'",
            "pack_cart_synth": "runtime code synthesis via 'eval'",
            "pack_cart_drift": "not deterministic",
        }
        for sid, needle in expect.items():
            r = A.detect(self.skills[sid])
            text = " ".join(r["static_violations"]
                            + [v for f in r["failing_probes"] for v in f["violations"]])
            self.assertIn(needle, text, sid)

    def test_synth_effect_never_runs_during_assurance(self):
        r = A.detect(self.skills["pack_cart_synth"])
        self.assertEqual(r["effect_calls"], 0)
        self.assertEqual(r["probes"], 0)

    def test_scan_ignores_strings_and_comments(self):
        def quiet(payload):
            # eval exec compile
            note = "eval(exec)"
            return {"crates": payload["sacks"], "bin": payload["bin"], "n": note}
        self.assertEqual(A.scan_source(quiet, F.MANIFEST["safety_boundary"]), [])

    def test_probes_derived_from_manifest_only(self):
        probes = A.derive_probes(F.MANIFEST)
        self.assertEqual(len(probes), 5 * 2 * 2)
        self.assertEqual(sorted({p["sacks"] for p in probes}), [0, 1, 4, 7, 8])
        self.assertEqual(probes, A.derive_probes(F.MANIFEST))

    def test_assurance_code_names_no_fixture_skill(self):
        src = read("assurance.py")
        for sid in F.BROKEN:
            self.assertNotIn(sid, src)
        self.assertNotIn("pack_cart", src)

    def test_good_skill_passes(self):
        r = A.detect(self.skills["pack_cart"])
        self.assertEqual(r["status"], "pass")
        self.assertEqual(r["effect_calls"], 40)


class D_CannotRegister(unittest.TestCase):

    def test_failed_assurance_rejected_and_not_invokable(self):
        skills = F.build_skills()
        reg = A.Registry()
        for sid in F.BROKEN:
            reg.hold(skills[sid])
            res = reg.register(sid)
            self.assertEqual(res["status"], "rejected", sid)
            self.assertTrue(res["reasons"])
            with self.assertRaises(A.Rejected):
                reg.invoke(sid, F.SMALL)
        self.assertEqual(reg.report()["registered"], [])
        self.assertEqual(sorted(reg.report()["rejected"]), sorted(F.BROKEN))

    def test_retry_is_still_rejected(self):
        skills = F.build_skills()
        reg = A.Registry()
        for _ in range(2):
            reg.hold(skills["pack_cart_double"])
            self.assertEqual(reg.register("pack_cart_double")["status"], "rejected")
        self.assertNotIn("pack_cart_double", reg.report()["registered"])

    def test_held_is_not_registered(self):
        skills = F.build_skills()
        reg = A.Registry()
        reg.hold(skills["pack_cart"])
        with self.assertRaises(A.Rejected):
            reg.invoke("pack_cart", F.SMALL)
        self.assertEqual(reg.register("never_held")["status"], "rejected")

    def test_register_takes_no_external_report(self):
        import inspect
        params = list(inspect.signature(A.Registry.register).parameters)
        self.assertEqual(params, ["self", "skill_id"])

    def test_missing_author_checks_rejected(self):
        reg = A.Registry()
        reg.hold(A.Skill(F.manifest_for("bare"), effect.pack_cart, []))
        self.assertEqual(reg.register("bare")["status"], "rejected")

    def test_good_skill_registers(self):
        reg, _, res = registered_good()
        self.assertEqual(res["status"], "registered")
        self.assertEqual(reg.report()["registered"], ["pack_cart"])


class FixturesRunner(unittest.TestCase):

    def test_all_fixtures_pass(self):
        for name, ok, detail in F.run_all():
            self.assertTrue(ok, "%s: %s" % (name, detail))

    def test_baseline_would_pass_broken(self):
        base = F.baseline_author_checks_only()
        self.assertEqual(sorted(base), sorted(("pack_cart",) + F.BROKEN))

    def test_main_returns_zero_and_is_deterministic(self):
        outs = []
        for _ in range(2):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(F.main(), 0)
            outs.append(buf.getvalue())
        self.assertEqual(outs[0], outs[1])
        self.assertIn("summary: 4/4 fixtures pass", outs[0])


class PaperEvidence(unittest.TestCase):

    def test_metadata(self):
        ev = evidence()
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.07652")
        self.assertEqual(ev["paper"]["licence"], "CC BY 4.0")
        pin = ev["implementation_pin"]
        self.assertEqual(pin["commit"], "25e4cf662a39a907f721455c0f0044444c019465")
        self.assertEqual(pin["licence"], "MIT")
        self.assertIn("ARPA Hellenic Logical Systems", pin["licence_header"])
        self.assertEqual(ev["empirical_claims"]["status"], "UNVERIFIED")

    def test_required_quotes_present(self):
        quotes = [e["excerpt"] for e in evidence()["excerpts"]]
        for needle in ("before any skill is admitted into the registry",
                       "typed JSON input contract",
                       "the Effect honors the Contract"):
            self.assertTrue(any(needle in q for q in quotes), needle)
        self.assertIn("before a skill joins the registry",
                      evidence()["implementation_pin"]["readme_quote"]["raw"])

    def test_offsets_consistent(self):
        for e in evidence()["excerpts"]:
            self.assertEqual(e["end_offset_exclusive"] - e["normalized_offset"], len(e["excerpt"]))
            self.assertEqual(e["chars"], len(e["excerpt"]))

    @unittest.skipUnless(os.path.exists(PAPER_HTML), "paper HTML not cached at " + PAPER_HTML)
    def test_excerpts_found(self):
        with open(PAPER_HTML, encoding="utf-8") as fh:
            t = normalize(fh.read())
        ev = evidence()
        self.assertEqual(len(t), ev["normalization"]["normalized_chars"])
        for e in ev["excerpts"]:
            with self.subTest(e["id"]):
                s, end = e["normalized_offset"], e["end_offset_exclusive"]
                self.assertEqual(t[s:end], e["excerpt"])
                self.assertEqual(t.count(e["excerpt"]), e["occurrences"])
                w = t[max(0, s - 64):min(len(t), end + 64)]
                self.assertEqual(hashlib.sha256(w.encode("utf-8")).hexdigest(),
                                 e["source_window_sha256"])

    @unittest.skipUnless(os.path.exists(PIN_README), "pin README not cached at " + PIN_README)
    def test_pin_readme_line(self):
        q = evidence()["implementation_pin"]["readme_quote"]
        with open(PIN_README, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        self.assertEqual(lines[q["line"] - 1], q["raw"])


class Hygiene(unittest.TestCase):

    def test_no_allow_vocabulary_in_impl(self):
        for name in IMPL:
            src = read(name).lower()
            for needle in ("al" + "low", "appro" + "v", "per" + "mit"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))

    def test_public_verbs(self):
        for verb in ("hold", "register", "reject", "report"):
            self.assertTrue(callable(getattr(A.Registry, verb)), verb)
        for verb in ("detect", "compare"):
            self.assertTrue(callable(getattr(A, verb)), verb)
        names = dir(A) + dir(A.Registry)
        for bad in ("al" + "low", "appro" + "ve", "per" + "mit"):
            self.assertFalse([n for n in names if bad in n.lower()], bad)

    def test_banned_lineage_absent(self):
        needles = ("HM" + "AC", "Two" + "-Ledger", "two" + "_ledger", "2611." + "06989",
                   "2611." + "06924", "2611." + "07483")
        for name in sorted(os.listdir(HERE)):
            if os.path.isfile(os.path.join(HERE, name)):
                src = read(name)
                for n in needles:
                    self.assertNotIn(n, src, "%s: %s" % (name, n))

    def test_no_paper_empirical_figures(self):
        needles = ("23 models", "23 frontier", "368", "84.8", "97.3",
                   "parameter errors entirely", "token usage by", "inference costs by")
        for name in IMPL + PROSE:
            src = read(name)
            for n in needles:
                self.assertNotIn(n, src, "%s: %s" % (name, n))

    def test_readme_standing_notes(self):
        src = read("README.md")
        for needle in ("method sketch", "not a reproduction", "not village law",
                       "not Team OS law", "UNVERIFIED", "python3 -m unittest test_assurance.py -v",
                       "python3 fixtures.py", "Builder reflection", "Ludex:"):
            self.assertIn(needle, src, needle)
        for word in ("KEEP", "CloudAgent", "Smith", "Checker", "Ork"):
            self.assertIsNone(re.search(r"\b%s\b" % word, src), word)
        for word in ("pull request", "merge"):
            self.assertNotIn(word, src.lower(), word)

    def test_notice(self):
        src = read("NOTICE")
        for needle in ("2611.07652", "CC BY 4.0", "Vladimiros Peilivanidis",
                       "25e4cf662a39a907f721455c0f0044444c019465", "MIT",
                       "ARPA Hellenic Logical Systems", "not cloned", "stdlib", "Synthetic"):
            self.assertIn(needle, src, needle)

    def test_no_test_reads_parent_index(self):
        src = read("test_assurance.py")
        self.assertNotIn("day" + "-README", src)
        self.assertNotIn("../" + "README", src)

    def test_imports_stdlib_only(self):
        stdlib_mods = {"copy", "importlib", "inspect", "io", "itertools", "json", "os", "sys",
                        "tokenize", "contextlib", "hashlib", "html", "re", "unittest",
                        "assurance", "effect", "fixtures"}
        for name in ("effect.py", "assurance.py", "fixtures.py", "test_assurance.py"):
            for m in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z_][\w]*)", read(name), re.M):
                self.assertIn(m.group(1), stdlib_mods, "%s: %s" % (name, m.group(1)))

    def test_effect_has_no_io(self):
        src = read("effect.py")
        self.assertNotIn("import", src)
        self.assertEqual(A.scan_source(effect.pack_cart, F.MANIFEST["safety_boundary"]), [])


if __name__ == "__main__":
    unittest.main()
