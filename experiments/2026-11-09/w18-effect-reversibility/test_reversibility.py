"""Offline unittest suite for the effect-reversibility method sketch."""

import ast
import hashlib
import html
import json
import os
import re
import sys
import unittest

import fixtures
import reversibility as rv

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_HTML = "/tmp/w18-2611.09054.html"
IMPL = ("reversibility.py", "fixtures.py")
DOCS = ("README.md", "NOTICE")


def _read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def normalize(raw):
    """Same normalization as documented in paper_evidence.json."""
    t = re.sub(r"<script\b.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r"<style\b.*?</style>", "", t, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r"<math\b.*?</math>", "", t, flags=re.DOTALL | re.IGNORECASE)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t)


class Fixture1EffectKeyed(unittest.TestCase):

    def test_alternates_fail_closed(self):
        rep = rv.detect(fixtures.build_world(), fixtures.effect_r())
        for name in fixtures.ALTERNATES:
            r = rep.by_name(name)
            self.assertFalse(r.prohibited, name)
            self.assertGreaterEqual(r.held_at, 0, name)
            self.assertTrue(r.hold.startswith("hold:effect:"), name)

    def test_zero_prohibited_and_rare_bar(self):
        rep = rv.detect(fixtures.build_world(), fixtures.effect_r())
        self.assertEqual(rep.prohibited_count, 0)
        self.assertTrue(rv.rare_bar(rep))

    def test_alternates_leak_with_no_restriction(self):
        rep = rv.detect(fixtures.build_world(), None)
        for name in fixtures.ALTERNATES + ("original_mechanism",):
            self.assertTrue(rep.by_name(name).prohibited, name)

    def test_alternates_use_other_mechanisms(self):
        w = fixtures.build_world()
        for name in fixtures.ALTERNATES:
            mechs = {s.mechanism for s in w.path(name).steps}
            self.assertNotIn("fresh_route", mechs, name)


class Fixture2MechanismOnly(unittest.TestCase):

    def test_original_held_but_alternates_leak(self):
        w = fixtures.build_world()
        rep = rv.detect(w, fixtures.mechanism_r())
        orig = rep.by_name("original_mechanism")
        self.assertEqual(orig.held_at, 0)
        self.assertFalse(orig.prohibited)
        leaking = [n for n in fixtures.ALTERNATES if rep.by_name(n).prohibited]
        self.assertGreaterEqual(len(leaking), 1)
        self.assertFalse(rv.rare_bar(rep))

    def test_compliance_check_on_original_is_insufficient(self):
        w = fixtures.build_world()
        self.assertTrue(rv.compliance_check_original(w, fixtures.mechanism_r()))
        self.assertGreater(rv.detect(w, fixtures.mechanism_r()).prohibited_count, 0)

    def test_compare(self):
        c = rv.compare(fixtures.build_world(), fixtures.effect_r(), fixtures.mechanism_r())
        self.assertEqual(c["effect_keyed"]["prohibited"], 0)
        self.assertGreater(c["mechanism_only"]["prohibited"], 0)
        self.assertTrue(c["mechanism_only"]["compliance_check_original"])
        self.assertTrue(c["effect_keyed"]["rare_bar"])
        self.assertFalse(c["mechanism_only"]["rare_bar"])


class Fixture3Service(unittest.TestCase):

    def test_legitimate_repair_succeeds(self):
        rep = rv.detect(fixtures.build_world(), fixtures.effect_r())
        lr = rep.by_name("legitimate_repair")
        self.assertEqual((lr.held_at, lr.stalled_at), (-1, -1))
        self.assertIn(rv.RESTORE, lr.effects)
        self.assertIn(rv.SERVE_OPEN, lr.effects)
        self.assertFalse(lr.prohibited)

    def test_open_region_service_succeeds(self):
        rep = rv.detect(fixtures.build_world(), fixtures.effect_r())
        r = rep.by_name("open_region_service")
        self.assertEqual(r.held_at, -1)
        self.assertEqual(r.effects, (rv.SERVE_OPEN,))
        self.assertTrue(r.served)

    def test_held_repair_is_not_counted_as_service(self):
        rep = rv.detect(fixtures.build_world(), fixtures.effect_r())
        self.assertFalse(rep.by_name("unauthorized_repair").served)
        self.assertEqual(rep.service_count, 2)

    def test_unauthorized_repair_differs_only_in_sink(self):
        # Same repair mechanism, different effect: held because of the sink.
        w = fixtures.build_world()
        bad = w.path("unauthorized_repair")
        good = w.path("legitimate_repair")
        self.assertEqual(bad.steps[0].mechanism, good.steps[0].mechanism)
        r = rv.run_path(w, bad, fixtures.effect_r())
        self.assertEqual(r.held_at, len(bad.steps) - 1)


class Fixture4Joint(unittest.TestCase):

    def test_each_local_check_passes(self):
        w = fixtures.build_world()
        r = rv.run_path(w, w.path("joint_three_agents"))
        self.assertTrue(all(r.local_ok))
        self.assertEqual(len({s.agent for s in w.path("joint_three_agents").steps}), 3)

    def test_no_agent_alone_produces_effect(self):
        w = fixtures.build_world()
        alone = fixtures.per_agent_reports(w, w.path("joint_three_agents"))
        self.assertEqual(len(alone), 3)
        for agent, rep in alone.items():
            self.assertFalse(rep.prohibited, agent)

    def test_together_produce_effect_and_are_held(self):
        w = fixtures.build_world()
        p = w.path("joint_three_agents")
        self.assertTrue(rv.run_path(w, p).prohibited)
        held = rv.run_path(w, p, fixtures.effect_r())
        self.assertFalse(held.prohibited)
        self.assertEqual(held.held_at, len(p.steps) - 1)
        self.assertTrue(rv.run_path(w, p, fixtures.mechanism_r()).prohibited)


class SinkNotProvenance(unittest.TestCase):

    def test_same_source_held_only_by_target(self):
        w = fixtures.build_world()
        to_closed = rv.run_path(w, w.path("shared_memory"), fixtures.effect_r())
        to_open = rv.run_path(w, w.path("legitimate_repair"), fixtures.effect_r())
        self.assertGreaterEqual(to_closed.held_at, 0)
        self.assertEqual(to_open.held_at, -1)

    def test_effect_of_ignores_inputs(self):
        w = fixtures.build_world()
        a = rv.Step("dispatcher", "dispatch", "x", ("plan:r1",), (), "r1")
        b = rv.Step("courier", "dispatch", "y", ("anything",), ("z",), "r1")
        self.assertEqual(rv.effect_of(a, w), rv.effect_of(b, w))
        self.assertEqual(rv.effect_of(a, w), rv.PROHIBITED)

    def test_no_taint_or_freeze_vocabulary(self):
        src = _read("reversibility.py").lower()
        for needle in ("taint", "freeze", "blast", "provenance"):
            self.assertNotIn(needle, src, needle)

class Fixture5Growth(unittest.TestCase):

    def test_recheck_fails_closed_under_old_gate(self):
        w = fixtures.build_world()
        n = len(w.paths)
        up = rv.recheck_update(w, fixtures.effect_r(), fixtures.growth_paths(),
                               fixtures.GROWTH_ACTIONS)
        self.assertEqual(up.status, "fail_closed")
        self.assertIn("flag:prohibited:growth_direct_dispatch", up.flags)
        self.assertEqual(len(w.paths), n)
        self.assertNotIn("direct_dispatch", w.actions)

    def test_extended_gate_registers_with_service(self):
        w = fixtures.build_world()
        wider = rv.extend_restriction(fixtures.effect_r(), ("direct_dispatch",))
        up = rv.recheck_update(w, wider, fixtures.growth_paths(), fixtures.GROWTH_ACTIONS)
        self.assertEqual(up.status, "registered")
        self.assertTrue(up.service_kept)
        rep = rv.detect(w, wider)
        self.assertEqual(rep.prohibited_count, 0)
        self.assertIn(rv.SERVE_OPEN, rep.by_name("growth_direct_open").effects)

    def test_unchecked_registration_leaks(self):
        w = fixtures.build_world()
        rv.register_unchecked(w, fixtures.growth_paths(), fixtures.GROWTH_ACTIONS)
        self.assertTrue(rv.detect(w, fixtures.effect_r())
                        .by_name("growth_direct_dispatch").prohibited)

    def test_over_broad_restriction_flags_service_loss(self):
        # Holding every dispatch would also score zero prohibited; the
        # recheck refuses it because required service stops.
        w = fixtures.build_world()
        n = len(w.paths)
        everything = rv.restrict_mechanism("dispatch_interface", ("r1", "r2"))
        up = rv.recheck_update(w, everything, [], {})
        self.assertEqual(up.status, "fail_closed")
        self.assertFalse(up.service_kept)
        self.assertIn("flag:service_lost:legitimate_repair", up.flags)
        self.assertNotIn("flag:service_lost:unauthorized_repair", up.flags)
        self.assertIn("flag:service_lost:open_region_service", up.flags)
        self.assertEqual(len(w.paths), n)

    def test_unknown_action_rejected(self):
        w = fixtures.build_world()
        with self.assertRaises(ValueError):
            rv.effect_of(rv.Step("a", "teleport", "m"), w)


class FixturesRunner(unittest.TestCase):

    def test_all_fixtures_pass(self):
        results = fixtures.run_all()
        self.assertEqual([r[0] for r in results], [1, 2, 3, 4, 5])
        for fid, title, ok, detail in results:
            self.assertTrue(ok, "fixture %d: %s" % (fid, detail))

    def test_deterministic(self):
        self.assertEqual(fixtures.summary(), fixtures.summary())

    def test_main_returns_zero(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(fixtures.main(), 0)
        self.assertIn("fixture 5 [PASS]", buf.getvalue())


class PaperEvidence(unittest.TestCase):

    def setUp(self):
        self.ev = json.loads(_read("paper_evidence.json"))

    def test_metadata(self):
        p = self.ev["paper"]
        self.assertEqual(p["arxiv_id"], "2611.09054")
        self.assertEqual(p["licence"], "CC BY 4.0")
        self.assertIsNone(self.ev["implementation_pin"])
        self.assertGreaterEqual(len(self.ev["excerpts"]), 8)

    def test_required_quotes_present(self):
        quotes = [e["excerpt"] for e in self.ev["excerpts"]]
        for needle in ("the gate is easy to add once the bypass is known",
                       "each passes its own permission check, yet together they can "
                       "dispatch into a closed region",
                       "keep a specified prohibited effect rare while maintaining "
                       "required service",
                       "What is reversed is the ability to produce a specified effect",
                       "a restriction on the original mechanism still operates but no "
                       "longer stops them"):
            self.assertTrue(any(needle.lower() in q.lower() for q in quotes), needle)

    def test_offsets_consistent(self):
        for e in self.ev["excerpts"]:
            self.assertEqual(e["end_offset_exclusive"] - e["normalized_offset"],
                             len(e["excerpt"]), e["id"])
            self.assertEqual(e["chars"], len(e["excerpt"]))

    @unittest.skipUnless(os.path.exists(PAPER_HTML),
                         "paper HTML cache absent at " + PAPER_HTML)
    def test_excerpts_found(self):
        with open(PAPER_HTML, encoding="utf-8") as fh:
            t = normalize(fh.read())
        self.assertEqual(len(t), self.ev["normalization"]["normalized_chars"])
        for e in self.ev["excerpts"]:
            s, end = e["normalized_offset"], e["end_offset_exclusive"]
            self.assertEqual(t[s:end], e["excerpt"], e["id"])
            self.assertEqual(t.count(e["excerpt"]), e["occurrences"], e["id"])
            win = t[max(0, s - 64):min(len(t), end + 64)]
            self.assertEqual(hashlib.sha256(win.encode("utf-8")).hexdigest(),
                             e["source_window_sha256"], e["id"])
        self.assertIn("4.2. </span>Recheck Control Before Each Update", t)


class Hygiene(unittest.TestCase):

    def test_no_allow_vocabulary_in_impl(self):
        for name in IMPL:
            src = _read(name).lower()
            for needle in ("al" + "low", "appro" + "v", "per" + "mit"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))

    def test_banned_lineage_absent(self):
        needles = ("Two" + "-Ledger", "two" + "_ledger", "2611." + "06989",
                   "2611." + "06924", "2611." + "07483", "HM" + "AC",
                   "NA" + "TS", "dock" + "er", "Insp" + "ect AI", "Fei" + "shu",
                   "SQL" + "ite", "certifi" + "cate")
        for name in IMPL + DOCS + ("paper_evidence.json",):
            src = _read(name)
            for n in needles:
                self.assertNotIn(n.lower(), src.lower(), "%s: %s" % (name, n))

    def test_no_paper_empirical_figures(self):
        pat = re.compile(r"\d+(?:\.\d+)?\s?%|\bp\s?[<=]\s?0\.\d")
        for name in IMPL + DOCS:
            self.assertIsNone(pat.search(_read(name)), name)

    def test_readme_standing_notes(self):
        r = re.sub(r"\s+", " ", _read("README.md"))
        for phrase in ("method sketch", "not a reproduction", "not village law",
                       "not Team OS law", "UNVERIFIED", "rare",
                       "maintaining required service", "Builder reflection",
                       "Ludex:", "python3 -m unittest test_reversibility.py -v",
                       "python3 fixtures.py"):
            self.assertIn(phrase, r, phrase)
        low = r.lower()
        for banned in ("KEEP", "Checker", "Ork", "Smith", "CloudAgent"):
            self.assertIsNone(re.search(r"" + banned + r"", r), banned)
        # word-boundary match: "Emergence" in the paper title is not a hit
        for banned in ("cloudagent", "smith", "checker", "pull request", "merg"):
            self.assertIsNone(re.search(r"\b" + banned, low), banned)

    def test_notice(self):
        n = re.sub(r"\s+", " ", _read("NOTICE"))
        for phrase in ("2611.09054", "CC BY 4.0", "method-cite only",
                       "clean-room", "stdlib", "Synthetic", "no upstream code pin",
                       "Zhengye Han", "Linda Ng Boyle"):
            self.assertIn(phrase.lower(), n.lower(), phrase)
        for banned in ("KEEP", "CloudAgent", "Smith", "Ork"):
            self.assertIsNone(re.search(r"\b" + banned + r"\b", n), banned)

    def test_no_test_reads_parent_index(self):
        src = _read("test_reversibility.py")
        self.assertNotIn('"day-' + 'README.md"', src)

    def test_imports_stdlib_only(self):
        ok = {"dataclasses", "sys", "reversibility"}
        for name in IMPL:
            tree = ast.parse(_read(name))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [(node.module or "").split(".")[0]]
                else:
                    continue
                for m in mods:
                    self.assertIn(m, ok, "%s imports %s" % (name, m))

    def test_public_verbs(self):
        for verb in ("restrict_effect", "restrict_mechanism", "detect", "compare",
                     "recheck_update", "run_path", "compliance_check_original"):
            self.assertTrue(callable(getattr(rv, verb)), verb)
        self.assertEqual(sys.version_info[0], 3)


if __name__ == "__main__":
    unittest.main()
