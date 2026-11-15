"""Tests for the mb-creg-belief-scoring method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
The source check reads the two files named in paper_evidence.json from the
directories listed in $MB_CREG_SOURCES (os.pathsep separated). There is no
default: when the variable is unset that check is skipped; when it is set,
both files must be found and match.
"""

import ast
import copy
import hashlib
import json
import math
import os
import re
import unittest

import creg_belief as C
import fixtures as F
import oracle as O

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("MB_CREG_SOURCES")
SLUG = "mb-creg-belief-scoring"
DAY_HEADER = "# experiments/2026-11-13\n"
ROW_START = "- [%s](%s/): " % (SLUG, SLUG)
FOOTER = "Do not merge experiment PRs without Ork review."
# mutants.py sets this while a world mutant runs: the frozen digest,
# frozen reference and README sync tests then skip, so a world mutant must
# be caught by the semantic tests, not by a hash.
WORLD_MUTANT = False


def day_readme():
    """Repo layout: ../README.md (when it starts with the day header).
    Flat draft: _day/README.md beside this file."""
    parent = os.path.join("..", "README.md")
    path = os.path.join(HERE, parent)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            if f.read().startswith(DAY_HEADER):
                return parent
    return os.path.join("_day", "README.md")


DAY = day_readme()
PY = ("creg_belief.py", "oracle.py", "fixtures.py", "test_creg_belief.py", "mutants.py")
ALL = PY + ("README.md", "NOTICE", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
PATHS = ("/work" + "space", "/t" + "mp", "/ho" + "me")
PAPER_NUMBERS = ("15" + ".3", "1,1" + "50", "11" + "50 ", "35" + "0 scen", "0.20" + "\u2013")
STDLIB = {"ast", "copy", "hashlib", "io", "json", "math", "os", "re", "sys", "unittest",
          "creg_belief", "oracle", "fixtures", "test_creg_belief"}
FAR = 10 ** 6


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def own_rows(day_text):
    """This PR's own row(s) of the day README. Sibling rows belong to other
    PRs, so the word, path, marker and paper-number scans skip them."""
    return "\n".join(ln for ln in day_text.split("\n") if ln.startswith(ROW_START))


def scanned(name):
    text = read(name)
    return own_rows(text) if name == DAY else text


def hygiene_hits(text):
    low = text.lower()
    hits = [w for w in BANNED if w.lower() in low] + [p for p in PATHS if p in text]
    if re.search(r"^(<{7}|>{7}|={7})( |$)", text, re.M):
        hits.append("conflict marker")
    return hits


def paper_number_hits(text):
    return [n for n in PAPER_NUMBERS if n in text]


def by_id(sid):
    return next(x for x in F.SUITE if x["id"] == sid)


def regime(name):
    return [x for x in F.SUITE if x["regime"] == name]


def prefixes(sc, options=None):
    out = C.run(sc, options)
    assert out["status"] == C.OK, out
    return out["prefixes"]


def far(sc):
    out = copy.deepcopy(sc)
    out["deadline"] = FAR
    return out


def differs(sc, name):
    return not all(C.prefix_marks(prefixes(sc, C.BASELINES[name]), O.reference(sc)))


COMPARE = ("step", "now", "support", "contradict", "stale", "superseded", "unlinked",
           "contradiction", "conflicts", "action")


class DoneWhenA(unittest.TestCase):
    """(a) the independent oracle and the updater agree on every prefix."""

    def assert_agree(self, sc):
        pred, ref = prefixes(sc), O.reference(sc)
        self.assertEqual(len(pred), len(sc["reports"]))
        self.assertEqual(len(pred), len(ref))
        for p, q in zip(pred, ref):
            self.assertLess(abs(p["posterior"] - q["posterior"]), 1e-9, (sc["id"], p["step"]))
            for k in COMPARE:
                self.assertEqual(p[k], q[k], (sc["id"], p["step"], k))
        return len(pred)

    def test_agree_every_prefix_of_frozen_suite(self):
        n = sum(self.assert_agree(sc) for sc in F.SUITE)
        self.assertEqual(n, sum(len(x["reports"]) for x in F.SUITE))
        self.assertGreaterEqual(n, 40)

    def test_agree_under_prior_and_age_variants(self):
        for sc in F.SUITE:
            for prior in (0.2, 0.5, 0.8):
                for age in (1, 3, 10):
                    v = copy.deepcopy(sc)
                    v["prior"], v["max_age"] = prior, age
                    self.assert_agree(v)

    def test_frozen_reference(self):
        if WORLD_MUTANT:
            self.skipTest("world mutant")
        self.assertEqual(set(F.REFERENCE), {x["id"] for x in F.SUITE})
        for sc in F.SUITE:
            self.assertEqual(F.compact(prefixes(sc)), F.REFERENCE[sc["id"]], sc["id"])
            self.assertEqual(F.compact(O.reference(sc)), F.REFERENCE[sc["id"]], sc["id"])

    def test_frozen_suite_digest(self):
        if WORLD_MUTANT:
            self.skipTest("world mutant")
        self.assertEqual(F.suite_digest(), F.SUITE_SHA256)

    def test_hand_computed_prefixes(self):
        # revision-b step 2: only b2 is live, odds of anomalous = (1/4) ** 0.6.
        odds = 0.25 ** 0.6
        self.assertAlmostEqual(prefixes(by_id("revision-b"))[1]["posterior"], odds / (1 + odds), 12)
        # stale-a step 1: k1 arrives stale, so the posterior is the prior.
        self.assertEqual(prefixes(by_id("stale-a"))[0]["posterior"], 0.5)
        # reliability-a step 2: two iot-9 reports, odds = 19 ** 0.25 * 19 ** 0.25.
        odds = 19 ** 0.5
        self.assertAlmostEqual(prefixes(by_id("reliability-a"))[1]["posterior"], odds / (1 + odds), 12)

    def test_no_prefix_near_a_threshold(self):
        for sc in F.SUITE:
            for p in prefixes(sc):
                self.assertGreater(abs(abs(p["log_odds"]) - math.log(9.0)), 1e-6, sc["id"])
            for r in sc["reports"]:
                w = sc["sources"][r["source"]]
                llr = w * math.log(r["confidence"] / (1 - r["confidence"]))
                self.assertGreater(abs(llr - math.log(3.0)), 1e-6, (sc["id"], r["id"]))

    def test_oracle_is_a_separate_code_path(self):
        o_tree = ast.parse(read("oracle.py"))
        c_tree = ast.parse(read("creg_belief.py"))
        o_imports = [n for n in ast.walk(o_tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual(o_imports, [], "oracle.py imports nothing")
        c_names = {a.name for n in ast.walk(c_tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertEqual(c_names, {"math"})
        self.assertFalse([n for n in ast.walk(c_tree) if isinstance(n, ast.ImportFrom)])
        self.assertNotIn("log", {n.attr for n in ast.walk(o_tree) if isinstance(n, ast.Attribute)})
        self.assertNotIn("oracle", read("creg_belief.py"))

    def test_run_does_not_mutate_input(self):
        for sc in F.SUITE:
            before = copy.deepcopy(sc)
            C.run(sc)
            O.reference(sc)
            C.drop_relations(sc)
            self.assertEqual(sc, before)


class DoneWhenB(unittest.TestCase):
    """(b) a scenario is right at the endpoint but wrong mid-trajectory."""

    def test_full_updater_is_perfect_everywhere(self):
        pa, ma, ea = C.accuracy(F.score(F.SUITE))
        self.assertEqual((pa, ma, ea), (1.0, 1.0, 1.0))

    def test_endpoint_right_mid_wrong_exists(self):
        marks = F.score(F.SUITE, C.BASELINES["no_contradiction"])
        ids = F.endpoint_right_mid_wrong(marks)
        self.assertIn("contradiction-resolution-a", ids)
        self.assertIn("contradiction-resolution-b", ids)

    def test_mid_below_endpoint_on_resolution_regime(self):
        res = regime("contradiction_resolution")
        _, ma, ea = C.accuracy(F.score(res, C.BASELINES["no_contradiction"]))
        self.assertEqual(ea, 1.0)
        self.assertLess(ma, ea)
        self.assertEqual(C.accuracy(F.score(res))[1:], (1.0, 1.0))

    def test_endpoint_only_score_cannot_tell(self):
        res = regime("contradiction_resolution")
        base = F.score(res, C.BASELINES["no_contradiction"])
        full = F.score(res)
        self.assertEqual([m[-1] for m in base], [m[-1] for m in full])
        self.assertNotEqual(base, full)

    def test_resolution_a_step_3(self):
        sc = by_id("contradiction-resolution-a")
        full, base = prefixes(sc), prefixes(sc, C.BASELINES["no_contradiction"])
        self.assertTrue(full[2]["contradiction"])
        self.assertEqual(full[2]["conflicts"], (("i2", "i3"),))
        self.assertEqual(full[2]["action"], C.RECONCILE)
        self.assertEqual(base[2]["action"], C.GATHER)
        self.assertEqual(full[3]["action"], base[3]["action"])
        self.assertIn("i2", full[3]["superseded"])

    def test_every_baseline_loses_somewhere(self):
        self.assertEqual(set(C.BASELINES), {"full", "no_contradiction", "no_staleness",
                                            "no_supersedes", "no_reliability"})
        self.assertEqual(C.BASELINES["full"], C.FULL)
        for name, opts in C.BASELINES.items():
            if name == "full":
                continue
            self.assertEqual(sum(1 for v in opts.values() if not v), 1, name)
            self.assertLess(C.accuracy(F.score(F.SUITE, opts))[0], 1.0, name)


class DoneWhenC(unittest.TestCase):
    """(c) dropping relation content hurts only the relation-dependent subset."""

    def test_relation_ablation(self):
        dep, nodep = F.relation_subsets()
        self.assertGreaterEqual(len(dep), 3)
        self.assertGreaterEqual(len(nodep), 3)
        drop_dep = C.accuracy(F.score(dep))[0] - C.accuracy(F.score(dep, ablate=True))[0]
        drop_nodep = C.accuracy(F.score(nodep))[0] - C.accuracy(F.score(nodep, ablate=True))[0]
        self.assertGreaterEqual(drop_dep, 0.25)
        self.assertLessEqual(drop_nodep, 0.0)
        self.assertGreaterEqual(drop_dep - drop_nodep, 0.25)

    def test_relation_dependent_tag_is_true(self):
        for sc in F.SUITE:
            measured = {r[0] for r in sc["relations"] if r[1] == "measures" and r[2] == sc["target"]}
            uses = any(r["entity"] in measured for r in sc["reports"])
            self.assertEqual(sc["relation_dependent"], uses, sc["id"])
            hurt = not all(m for marks in F.score([sc], ablate=True) for m in marks)
            self.assertEqual(hurt, uses, sc["id"])

    def test_no_relation_subset_carries_distractor_relations(self):
        for sc in F.relation_subsets()[1]:
            self.assertTrue(sc["relations"], sc["id"])

    def test_relation_order_irrelevant(self):
        for sc in F.SUITE:
            v = copy.deepcopy(sc)
            v["relations"] = list(reversed(v["relations"]))
            self.assertEqual(prefixes(v), prefixes(sc))

    def test_only_measures_to_target_links(self):
        self.assertEqual(prefixes(by_id("preservation-a"))[2]["unlinked"], ("c3",))
        self.assertEqual(prefixes(by_id("preservation-b"))[1]["unlinked"], ("d2",))
        ab = prefixes(C.drop_relations(by_id("relation-a")))
        self.assertEqual(ab[-1]["unlinked"], ("e1", "e2"))
        self.assertEqual(ab[-1]["posterior"], 0.5)

    def test_relations_option_matches_ablation(self):
        opts = dict(C.FULL, relations=False)
        for sc in F.SUITE:
            self.assertEqual(prefixes(sc, opts), prefixes(C.drop_relations(sc)), sc["id"])
        self.assertNotEqual(prefixes(by_id("relation-a"), opts), prefixes(by_id("relation-a")))

    def test_drop_relations_copies(self):
        sc = by_id("relation-a")
        out = C.drop_relations(sc)
        self.assertEqual(out["relations"], [])
        self.assertTrue(sc["relations"])


class Regimes(unittest.TestCase):

    def test_coverage(self):
        for name in F.REGIMES:
            self.assertGreaterEqual(len(regime(name)), 2, name)
        self.assertTrue(all(x["regime"] in F.REGIMES for x in F.SUITE))
        self.assertEqual(len({x["id"] for x in F.SUITE}), len(F.SUITE))

    def test_revision(self):
        for sc in regime("revision"):
            ps = prefixes(sc)
            self.assertGreater(ps[0]["posterior"], 0.5, sc["id"])
            self.assertEqual(ps[-1]["action"], C.CONTINUE, sc["id"])
            self.assertFalse(any(p["contradiction"] for p in ps), sc["id"])
        self.assertTrue(differs(by_id("revision-b"), "no_supersedes"))

    def test_preservation(self):
        for sc in regime("preservation"):
            ps = prefixes(sc)
            self.assertEqual(len({p["action"] for p in ps}), 1, sc["id"])
            self.assertTrue(any(p["unlinked"] for p in ps), sc["id"])
            self.assertGreater(len(ps), 1)

    def test_contradiction_onset(self):
        for sc in regime("contradiction_onset"):
            ps = prefixes(sc)
            self.assertFalse(ps[0]["contradiction"], sc["id"])
            self.assertTrue(ps[-1]["contradiction"], sc["id"])
            self.assertEqual(ps[-1]["action"], C.RECONCILE, sc["id"])

    def test_contradiction_resolution(self):
        ways = set()
        for sc in regime("contradiction_resolution"):
            ps = prefixes(sc)
            self.assertFalse(ps[-1]["contradiction"], sc["id"])
            opened = [i for i, p in enumerate(ps) if p["contradiction"]]
            self.assertTrue(opened, sc["id"])
            k = opened[-1] + 1
            gone = {x for pair in ps[k - 1]["conflicts"] for x in pair}
            if gone & set(ps[k]["superseded"]):
                ways.add("superseded")
            if gone & set(ps[k]["stale"]):
                ways.add("stale")
        self.assertEqual(ways, {"superseded", "stale"})

    def test_stale(self):
        arrived_stale = aged_out = False
        for sc in regime("stale"):
            ps = prefixes(sc)
            self.assertTrue(any(p["stale"] for p in ps), sc["id"])
            self.assertTrue(differs(sc, "no_staleness"), sc["id"])
            for i, r in enumerate(sc["reports"]):
                later = [p["stale"] for p in ps[i:]]
                if r["id"] in later[0]:
                    arrived_stale = True
                elif any(r["id"] in s for s in later[1:]):
                    aged_out = True
        self.assertTrue(arrived_stale and aged_out)

    def test_delayed_but_fresh_counts(self):
        sc = by_id("stale-c")
        self.assertLess(sc["reports"][0]["t"], sc["reports"][0]["at"])
        self.assertEqual(prefixes(sc)[0]["support"], ("m1",))

    def test_reliability(self):
        for sc in regime("reliability"):
            self.assertTrue(differs(sc, "no_reliability"), sc["id"])
        sc = by_id("reliability-a")
        self.assertFalse(prefixes(sc)[-1]["contradiction"])
        self.assertTrue(prefixes(sc, C.BASELINES["no_reliability"])[-1]["contradiction"])

    def test_deadline(self):
        for sc in regime("deadline"):
            last = prefixes(sc)[-1]
            self.assertGreaterEqual(last["now"], sc["deadline"])
            self.assertEqual(last["action"], sc["on_expiry"])
            self.assertIn(prefixes(far(sc))[-1]["action"], (C.DISPATCH, C.RECONCILE))
        self.assertEqual({x["on_expiry"] for x in regime("deadline")} - {"HOLD"}, {"ESCALATE"})


def bad(sc):
    out = C.run(sc)
    return out["status"], out["reason"], out["prefixes"]


class FailClosed(unittest.TestCase):

    def base(self):
        return copy.deepcopy(by_id("contradiction-resolution-a"))

    def assert_error(self, sc, reason=None):
        status, why, ps = bad(sc)
        self.assertEqual(status, C.CONFIG_ERROR)
        self.assertEqual(ps, [])
        if reason:
            self.assertEqual(why, reason)

    def test_missing_on_expiry_is_config_error(self):
        for sc in F.SUITE:
            v = copy.deepcopy(sc)
            del v["on_expiry"]
            self.assert_error(v, "on_expiry_missing")

    def test_on_expiry_values(self):
        self.assertEqual(C.ON_EXPIRY_VALUES, ("HOLD", "ESCALATE", "DENY"))

        class S(str):
            pass

        for value in ("hold", "Hold", "", None, 0, C.DISPATCH, C.RECONCILE, C.GATHER,
                      "CONTINUE_MONITORING", S("HOLD"), ["HOLD"]):
            v = self.base()
            v["on_expiry"] = value
            self.assert_error(v, "on_expiry_invalid")
        for value in C.ON_EXPIRY_VALUES:
            v = self.base()
            v["on_expiry"] = value
            self.assertEqual(bad(v)[0], C.OK)

    def test_missing_fields(self):
        for name in C.SCENARIO_FIELDS:
            v = self.base()
            del v[name]
            self.assert_error(v)
        for name in C.REPORT_FIELDS:
            v = self.base()
            del v["reports"][1][name]
            self.assert_error(v)

    def test_invalid_values(self):
        cases = [
            ("prior", 0.0), ("prior", 1.0), ("prior", True), ("prior", float("nan")),
            ("max_age", -1), ("max_age", 1.5), ("max_age", True),
            ("deadline", 0), ("deadline", "50"), ("deadline", True),
            ("relations", None), ("relations", [["a", "measures"]]),
            ("sources", {}), ("sources", {"robot-1": 0.0, "iot-3": 0.8, "edge-2": 0.6}),
            ("sources", {"robot-1": 1.5, "iot-3": 0.8, "edge-2": 0.6}),
            ("reports", []), ("target", ""),
        ]
        for name, value in cases:
            v = self.base()
            v[name] = value
            self.assert_error(v)

    def test_invalid_reports(self):
        edits = [
            ("source", "ghost"), ("polarity", True), ("polarity", 0), ("polarity", 1.0),
            ("confidence", 0.5), ("confidence", 1.0), ("confidence", True),
            ("t", 9), ("at", 0), ("id", "i1"), ("supersedes", "i4"),
            ("supersedes", "nope"), ("weight", 2.0), ("entity", ""),
        ]
        for name, value in edits:
            v = self.base()
            v["reports"][1][name] = value
            self.assert_error(v)
        v = self.base()
        v["reports"][3]["at"] = 2
        self.assert_error(v, "report_order_invalid")
        self.assert_error(["not", "a", "dict"])

    def test_bad_options_raise(self):
        with self.assertRaises(ValueError):
            C.run(self.base(), {"relations": False})
        with self.assertRaises(ValueError):
            C.run(self.base(), dict(C.FULL, extra=True))

    def test_no_dispatch_on_timeout_sweep(self):
        seen_expiry = 0
        for sc in F.SUITE:
            free = prefixes(far(sc))
            last = sc["reports"][-1]["at"]
            for deadline in range(1, last + 2):
                for on_expiry in C.ON_EXPIRY_VALUES:
                    v = copy.deepcopy(sc)
                    v["deadline"], v["on_expiry"] = deadline, on_expiry
                    for p, q in zip(prefixes(v), free):
                        if p["now"] >= deadline:
                            seen_expiry += 1
                            self.assertEqual(p["action"], on_expiry)
                        else:
                            self.assertEqual(p["action"], q["action"])
                        self.assertEqual(p["posterior"], q["posterior"])
        self.assertGreater(seen_expiry, 100)

    def test_expiry_at_exact_deadline(self):
        v = self.base()
        v["deadline"] = v["reports"][1]["at"]
        ps = prefixes(v)
        self.assertEqual(ps[0]["action"], C.GATHER)
        self.assertEqual(ps[1]["action"], v["on_expiry"])

    def test_contradiction_never_dispatches(self):
        for sc in F.SUITE:
            for name, opts in C.BASELINES.items():
                if not opts["contradiction"]:
                    continue
                for p in prefixes(far(sc), opts):
                    if p["contradiction"]:
                        self.assertEqual(p["action"], C.RECONCILE, (sc["id"], name))

    def test_strict_match_parts(self):
        ref = prefixes(by_id("revision-b"))[1]
        near = dict(ref, posterior=ref["posterior"] + 0.04)
        off = dict(ref, posterior=ref["posterior"] + 0.06)
        self.assertTrue(C.strict_match(near, ref))
        self.assertFalse(C.strict_match(off, ref))
        for k in ("support", "contradict", "contradiction", "action"):
            self.assertFalse(C.strict_match(dict(ref, **{k: "x"}), ref), k)
        self.assertEqual(C.prefix_marks([ref], [ref, ref]), [False, False])
        self.assertEqual(C.accuracy([[True, False, True], [False]]), (0.5, 0.5, 0.5))
        self.assertEqual(C.accuracy([[False, True]]), (0.5, 0.0, 1.0))
        with self.assertRaises(ValueError):
            C.accuracy([])


class Hygiene(unittest.TestCase):

    def test_files_present(self):
        for name in ALL:
            self.assertTrue(os.path.isfile(os.path.join(HERE, name)), name)

    def test_banned_words_paths_markers(self):
        for name in ALL:
            self.assertEqual(hygiene_hits(scanned(name)), [], name)
        self.assertTrue(own_rows(read(DAY)))

    def test_sibling_rows_do_not_break_hygiene(self):
        # Pure in-memory: a sibling row full of banned words, paths and
        # paper numbers is ignored; the same text in this PR's row is not.
        own = own_rows(read(DAY))
        dirty = ("ke" + "ep al" + "low Smi" + "th Check" + "er Cloud" + "Agent /t" + "mp /ho" + "me "
                 + "15" + ".3 1,1" + "50")
        sibling = "- [other-slug](other-slug/): " + dirty
        day = "\n".join([DAY_HEADER, sibling, own, sibling, "", FOOTER, ""])
        self.assertEqual(own_rows(day), own)
        self.assertEqual(hygiene_hits(own_rows(day)), [])
        self.assertEqual(paper_number_hits(own_rows(day)), [])
        self.assertTrue(hygiene_hits(day))
        self.assertTrue(paper_number_hits(day))
        bad_own = own + " " + dirty
        day2 = "\n".join([DAY_HEADER, bad_own, "", FOOTER, ""])
        self.assertEqual(len(hygiene_hits(own_rows(day2))), len(BANNED) + len(PATHS) - 1)
        self.assertTrue(paper_number_hits(own_rows(day2)))

    def test_stdlib_only(self):
        for name in PY:
            for n in ast.walk(ast.parse(read(name))):
                if isinstance(n, ast.Import):
                    for a in n.names:
                        self.assertIn(a.name.split(".")[0], STDLIB, (name, a.name))
                elif isinstance(n, ast.ImportFrom):
                    self.assertIn((n.module or "").split(".")[0], STDLIB, name)

    def test_day_readme(self):
        text = read(DAY)
        self.assertTrue(text.startswith(DAY_HEADER))
        lines = text.split("\n")
        rows = [ln for ln in lines if ln.startswith(ROW_START)]
        self.assertEqual(len(rows), 1)
        self.assertIn("arXiv 2611.11842", rows[0])
        self.assertTrue(text.endswith("\n\n" + FOOTER + "\n"))
        self.assertEqual(text.count(FOOTER), 1)

    def test_folder_readme(self):
        text = read("README.md")
        self.assertTrue(text.startswith("# %s\n" % SLUG))
        for head in ("## Usage", "## Regimes", "## Done-when", "## Limits"):
            self.assertIn("\n" + head + "\n", text)
        self.assertIn("UNVERIFIED", text)
        self.assertIn("not a reproduction", text)
        self.assertIn(FOOTER, text)

    def test_paper_numbers_only_in_evidence(self):
        for name in ALL:
            if name == "paper_evidence.json" or name == "test_creg_belief.py":
                continue
            self.assertEqual(paper_number_hits(scanned(name)), [], name)

    def test_readme_matches_summary(self):
        if WORLD_MUTANT:
            self.skipTest("world mutant")
        text = read("README.md")
        for line in F.summary().split("\n"):
            self.assertIn(line, text)

    def test_summary_deterministic(self):
        self.assertEqual(F.summary(), F.summary())
        n = sum(len(x["reports"]) for x in F.SUITE)
        self.assertIn("updater vs oracle: %d/%d prefixes agree" % (n, n), F.summary())

    def test_paper_evidence(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.11842")
        self.assertEqual(ev["paper"]["authors"], ["Ranulfo Bezerra", "Kimitoshi Yamazaki"])
        self.assertIn("UNVERIFIED", ev["paper"]["code"])
        self.assertIn("MB_CREG_SOURCES", ev["env"])
        self.assertEqual([s["file"] for s in ev["sources"]], ["2611.11842.html", "creg.html"])
        for s in ev["sources"]:
            self.assertRegex(s["sha256"], r"^[0-9a-f]{64}$")
            self.assertIs(type(s["chars"]), int)
        files = {s["file"] for s in ev["sources"]}
        self.assertGreaterEqual(len(ev["claims"]), 8)
        for c in ev["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED", c["id"])
            self.assertIn(c["source"], files)
            self.assertEqual(len(c["quote"]), c["length"], c["id"])

    def test_quotes_exact_in_sources(self):
        if not SOURCES:
            self.skipTest("MB_CREG_SOURCES not set")
        ev = json.loads(read("paper_evidence.json"))
        texts = {}
        for s in ev["sources"]:
            found = [os.path.join(d, s["file"]) for d in SOURCES.split(os.pathsep)
                     if os.path.isfile(os.path.join(d, s["file"]))]
            self.assertTrue(found, s["file"])
            with open(found[0], "rb") as f:
                raw = f.read()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), s["sha256"], s["file"])
            texts[s["file"]] = raw.decode("utf-8")
            self.assertEqual(len(texts[s["file"]]), s["chars"], s["file"])
        for c in ev["claims"]:
            text = texts[c["source"]]
            self.assertEqual(text[c["offset"]:c["offset"] + c["length"]], c["quote"], c["id"])


def no_expiry_leak(testcase, out, deadline):
    """Invariant: no ok record shows a non-on_expiry action at now >= deadline."""
    if out["status"] != C.OK:
        testcase.assertEqual(out["prefixes"], [])
        return 0
    n = 0
    for p in out["prefixes"]:
        if p["now"] >= deadline:
            n += 1
            testcase.assertIn(p["action"], C.ON_EXPIRY_VALUES, p)
    return n


def colliding_scenario(flip):
    """Verifier repro A1: a non-str key whose hash equals hash("on_expiry")
    swaps the validated HOLD for a dispatch on its flip-th comparison."""
    d = {}

    class K:
        n = 0

        def __hash__(self):
            return hash("on_expiry")

        def __eq__(self, other):
            K.n += 1
            if K.n == flip:
                d["on_expiry"] = C.DISPATCH
            return False

    d[K()] = 0
    d.update(copy.deepcopy(by_id("deadline-a")))
    d["on_expiry"] = C.HOLD
    K.n = 0
    return d


def polarity_swap_scenario(flip):
    """Verifier repro A2: a report key equal to "polarity" with a colliding
    hash turns the validated -1 into 40 on its flip-th comparison."""
    sc = far(by_id("revision-a"))
    old = sc["reports"][5]
    box = {}

    class P:
        n = 0

        def __hash__(self):
            return hash("polarity")

        def __eq__(self, other):
            P.n += 1
            if P.n == flip:
                box["r"][box["k"]] = 40
            return type(other) is str and other == "polarity"

    key = P()
    rr = {key: -1}
    for k, v in old.items():
        if k != "polarity":
            rr[k] = v
    box["r"], box["k"] = rr, key
    sc["reports"][5] = rr
    P.n = 0
    return sc


class Snapshot(unittest.TestCase):
    """F1: validate once, snapshot, never re-read the caller's object."""

    def test_a1_on_expiry_hash_collision_never_dispatches(self):
        for flip in range(1, 16):
            out = C.run(colliding_scenario(flip))
            no_expiry_leak(self, out, 4)
            self.assertEqual((out["status"], out["reason"], out["prefixes"]),
                             (C.CONFIG_ERROR, "scenario_key_invalid", []), flip)

    def test_a2_report_polarity_swap_rejected(self):
        for flip in range(1, 31):
            out = C.run(polarity_swap_scenario(flip))
            self.assertEqual((out["status"], out["reason"], out["prefixes"]),
                             (C.CONFIG_ERROR, "report_key_invalid", []), flip)

    def test_non_str_keys_rejected_at_every_level(self):
        class S(str):
            pass

        for key in (3, ("x",), S("note"), None, 1.5):
            v = copy.deepcopy(by_id("deadline-a"))
            v[key] = 1
            self.assertEqual(bad(v)[:2], (C.CONFIG_ERROR, "scenario_key_invalid"), key)
            v = copy.deepcopy(by_id("deadline-a"))
            v["reports"][1][key] = 1
            self.assertEqual(bad(v)[:2], (C.CONFIG_ERROR, "report_key_invalid"), key)
            v = copy.deepcopy(by_id("deadline-a"))
            v["sources"][key] = 0.5
            self.assertEqual(bad(v)[:2], (C.CONFIG_ERROR, "reliability_invalid"), key)
        v = copy.deepcopy(by_id("deadline-a"))
        v["regime_note"] = "extra str keys are fine"
        self.assertEqual(bad(v)[0], C.OK)

    def test_source_and_supersedes_exact_str(self):
        class S(str):
            pass

        for value in (S("robot-1"), ["robot-1"], 1, None):
            v = copy.deepcopy(by_id("deadline-a"))
            v["reports"][1]["source"] = value
            self.assertEqual(bad(v)[:2], (C.CONFIG_ERROR, "report_source_invalid"), value)
        for value in (S("i1"), ["i1"], 1, None):
            v = copy.deepcopy(by_id("contradiction-resolution-a"))
            v["reports"][3]["supersedes"] = value
            self.assertEqual(bad(v)[:2], (C.CONFIG_ERROR, "report_supersedes_invalid"), value)

    def test_on_expiry_is_the_module_constant(self):
        for want in C.ON_EXPIRY_VALUES:
            v = copy.deepcopy(by_id("deadline-a"))
            v["on_expiry"] = "".join(list(want))
            self.assertIsNot(v["on_expiry"], want)
            self.assertIs(C.validate(v)["on_expiry"], want)
            self.assertIs(prefixes(v)[-1]["action"], want)

    def test_snapshot_is_private(self):
        sc = copy.deepcopy(by_id("contradiction-resolution-a"))
        snap = C.validate(sc)
        self.assertIs(type(snap["reports"]), tuple)
        self.assertIs(type(snap["relations"]), tuple)
        self.assertIsNot(snap["sources"], sc["sources"])
        for a, b in zip(snap["reports"], sc["reports"]):
            self.assertIsNot(a, b)
            self.assertEqual(a, b)
        before = copy.deepcopy(snap)
        sc["on_expiry"], sc["deadline"], sc["target"] = "DENY", 1, "gauge-9"
        sc["reports"][0]["polarity"] = -1
        sc["sources"]["robot-1"] = 0.1
        sc["relations"].clear()
        self.assertEqual(snap, before)

    def test_run_reads_only_the_snapshot(self):
        good = by_id("deadline-b")
        poisoned = copy.deepcopy(by_id("revision-a"))
        poisoned.update(target="gauge-9", prior=0.2, max_age=0, deadline=1,
                        on_expiry=C.DISPATCH, relations=[],
                        sources={k: 0.3 for k in F.SOURCES})
        real = C.validate
        C.validate = lambda scenario: real(good)
        try:
            out = C.run(poisoned)
        finally:
            C.validate = real
        self.assertEqual(out, C.run(good))

    def test_invariant_no_expiry_leak_sweep(self):
        seen = 0
        for sc in F.SUITE + F.WITNESSES:
            last = sc["reports"][-1]["at"]
            for deadline in range(1, last + 2):
                for on_expiry in C.ON_EXPIRY_VALUES:
                    v = copy.deepcopy(sc)
                    v["deadline"], v["on_expiry"] = deadline, on_expiry
                    for opts in C.BASELINES.values():
                        out = C.run(v, opts)
                        self.assertEqual(out["status"], C.OK)
                        seen += no_expiry_leak(self, out, deadline)
                        for p in out["prefixes"]:
                            if p["now"] >= deadline:
                                self.assertEqual(p["action"], on_expiry)
        self.assertGreater(seen, 500)


class HostileInput(unittest.TestCase):
    """F3 type gaps and F5: hostile or extreme input is config_error."""

    def test_container_types_exact(self):
        class D(dict):
            pass

        class L(list):
            pass

        sc = by_id("deadline-a")
        self.assertEqual(bad(D(copy.deepcopy(sc)))[:2], (C.CONFIG_ERROR, "scenario_not_dict"))
        v = copy.deepcopy(sc)
        v["reports"] = L(v["reports"])
        self.assertEqual(bad(v)[:2], (C.CONFIG_ERROR, "reports_invalid"))
        v = copy.deepcopy(sc)
        v["reports"][0] = D(v["reports"][0])
        self.assertEqual(bad(v)[:2], (C.CONFIG_ERROR, "report_invalid"))
        for rel in (["sensor-p3", "measures", 7], ["sensor-p3", None, "gauge-7"], "abc"):
            v = copy.deepcopy(sc)
            v["relations"] = [rel]
            self.assertEqual(bad(v)[:2], (C.CONFIG_ERROR, "relations_invalid"), rel)
        v = copy.deepcopy(sc)
        v["relations"] = [tuple(x) for x in v["relations"]]
        self.assertEqual(prefixes(v), prefixes(sc))

    def test_overflow_is_config_error(self):
        v = copy.deepcopy(by_id("deadline-a"))
        v["prior"] = 10 ** 400
        self.assertEqual(bad(v), (C.CONFIG_ERROR, "numeric_overflow", []))
        v = far(by_id("revision-a"))
        v["max_age"] = 10
        v["reports"] = [dict(id="z%d" % i, source="robot-1", entity="gauge-7", polarity=-1,
                             confidence=0.999999999999, t=1, at=1) for i in range(40)]
        self.assertEqual(bad(v), (C.CONFIG_ERROR, "numeric_overflow", []))
        v["reports"] = v["reports"][:2]
        self.assertEqual(bad(v)[0], C.OK)

    def test_type_error_is_config_error(self):
        real = C.validate

        def boom(scenario):
            raise TypeError("hostile")

        C.validate = boom
        try:
            out = C.run(by_id("deadline-a"))
        finally:
            C.validate = real
        self.assertEqual(out, {"status": C.CONFIG_ERROR, "reason": "type_invalid", "prefixes": []})


class Witnesses(unittest.TestCase):
    """F3: supersession by a stale or unlinked report, and the other-gauge rule."""

    def test_witnesses_agree_with_oracle(self):
        self.assertEqual({x["id"] for x in F.WITNESSES}, {"supersede-unlinked", "supersede-stale"})
        for sc in F.WITNESSES:
            self.assertNotIn(sc["id"], {x["id"] for x in F.SUITE})
            DoneWhenA.assert_agree(self, sc)

    def test_unlinked_report_still_supersedes(self):
        ps = prefixes(next(x for x in F.WITNESSES if x["id"] == "supersede-unlinked"))
        self.assertEqual(ps[0]["support"], ("y1",))
        self.assertEqual(ps[1]["superseded"], ("y1",))
        self.assertEqual(ps[1]["unlinked"], ("y2",))
        self.assertEqual((ps[1]["support"], ps[1]["contradict"]), ((), ()))
        self.assertEqual((ps[1]["posterior"], ps[1]["action"]), (0.5, C.GATHER))

    def test_stale_report_still_supersedes(self):
        ps = prefixes(next(x for x in F.WITNESSES if x["id"] == "supersede-stale"))
        self.assertEqual((ps[0]["support"], ps[0]["action"]), (("z1",), C.DISPATCH))
        self.assertEqual(ps[1]["superseded"], ("z1",))
        self.assertEqual(ps[1]["stale"], ("z2",))
        self.assertEqual((ps[1]["posterior"], ps[1]["action"]), (0.5, C.GATHER))

    def test_other_gauge_sensor_links_nothing(self):
        hits = 0
        for sc in F.SUITE:
            other = {r[0] for r in sc["relations"] if r[1] == "measures" and r[2] != sc["target"]}
            ps = prefixes(sc)
            for i, rep in enumerate(sc["reports"]):
                if rep["entity"] in other:
                    hits += 1
                    for p in ps[i:]:
                        self.assertIn(rep["id"], p["unlinked"], (sc["id"], rep["id"]))
        self.assertGreater(hits, 0)
        v = copy.deepcopy(by_id("preservation-b"))
        v["relations"] = [r if r[0] != "sensor-p9" else ["sensor-p9", "measures", v["target"]]
                          for r in v["relations"]]
        self.assertEqual(prefixes(v)[1]["support"], ("d2",))


if __name__ == "__main__":
    unittest.main()
