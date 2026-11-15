"""Tests for the w18-decaf-dimensions method sketch (stdlib unittest only).

Run: python3 -m unittest test_decaf.py -v
Three checks read /tmp/w18-2611.08723.html (paper HTML) and are skipped when
it is absent:
  curl -sL https://arxiv.org/html/2611.08723 -o /tmp/w18-2611.08723.html
"""

import ast
import copy
import hashlib
import html
import io
import json
import os
import re
import sys
import unittest

import decaf as D
import fixtures as F

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_HTML = "/tmp/w18-2611.08723.html"
CODE = ("decaf.py", "fixtures.py", "dimensions.json")
PROSE = ("README.md", "NOTICE")
ALL = CODE + PROSE + ("test_decaf.py", "paper_evidence.json")
HAVE_PAPER = os.path.isfile(PAPER_HTML)


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


def paper_text():
    with open(PAPER_HTML, encoding="utf-8") as fh:
        return normalize(fh.read())


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def base_proposal(**kw):
    p = copy.deepcopy(F.PROPOSALS["single_evidenced"])
    p.update(kw)
    return p


class Changes(unittest.TestCase):

    def test_identical_is_empty(self):
        self.assertEqual(D.detect_changes(F.BASE, copy.deepcopy(F.BASE)), [])

    def test_nested_change_detected(self):
        after = copy.deepcopy(F.BASE)
        after["tool_gate"]["cody"].append("read_ledger")
        self.assertEqual(D.detect_changes(F.BASE, after), ["tool_gate"])

    def test_key_order_is_not_a_change(self):
        after = copy.deepcopy(F.BASE)
        after["retry_budget"] = {"timeout_s": 30, "max_retries": 2}
        self.assertEqual(D.detect_changes(F.BASE, after), [])

    def test_added_and_removed_keys(self):
        after = copy.deepcopy(F.BASE)
        del after["memory_window"]
        after["extra"] = 1
        self.assertEqual(D.detect_changes(F.BASE, after), ["extra", "memory_window"])

    def test_none_value_differs_from_absent(self):
        before, after = {"a": None}, {}
        self.assertEqual(D.detect_changes(before, after), ["a"])


class Outcomes(unittest.TestCase):

    def rep(self, key):
        return D.report(F.PROPOSALS[key], F.RUN_LOG)

    def test_single_evidenced(self):
        r = self.rep("single_evidenced")
        self.assertEqual(r["outcome"], D.NO_FLAG)
        self.assertEqual(r["evidence_by_dimension"], {"retry_budget": ["run-0412"]})
        self.assertFalse(r["multi_dimension"])

    def test_two_half_fails_closed(self):
        r = self.rep("two_dims_one_evidenced")
        self.assertEqual(r["outcome"], D.FAIL_CLOSED)
        unc = [f["dimension"] for f in r["findings"] if f["code"] == "uncovered_dimension"]
        self.assertEqual(unc, ["memory_window"])

    def test_two_full_reported_not_flagged(self):
        r = self.rep("two_dims_both_evidenced")
        self.assertEqual(r["outcome"], D.NO_FLAG)
        self.assertTrue(r["multi_dimension"])
        self.assertIn("multi_dimension", [f["code"] for f in r["findings"]])
        self.assertNotIn("two_dims_both_evidenced", D.flag([r]))

    def test_declared_mismatch(self):
        r = self.rep("declared_mismatch")
        self.assertEqual(r["outcome"], D.FLAG)
        self.assertEqual(r["declared_dimensions"], ["retry_budget"])
        self.assertEqual(r["actual_dimensions"], ["memory_window"])

    def test_declared_superset_flagged(self):
        p = base_proposal(declared_dimensions=["retry_budget", "tool_gate"])
        self.assertEqual(D.report(p, F.RUN_LOG)["outcome"], D.FLAG)

    def test_unknown_run_held(self):
        r = self.rep("unknown_run")
        self.assertEqual(r["outcome"], D.HOLD)
        self.assertEqual(D.hold_reasons(r), ["unknown_run"])

    def test_one_bad_entry_holds_whole_trace(self):
        p = copy.deepcopy(F.PROPOSALS["two_dims_both_evidenced"])
        p["evidence"].append(F.ev("run-0000", "memory_window", "a run nobody logged"))
        self.assertEqual(D.report(p, F.RUN_LOG)["outcome"], D.HOLD)

    def test_empty_and_placeholder_held(self):
        self.assertEqual(D.hold_reasons(self.rep("empty_evidence")), ["empty_evidence"])
        self.assertEqual(D.hold_reasons(self.rep("placeholder_evidence")), ["placeholder_evidence"])

    def test_placeholder_variants(self):
        for note in ("", "   ", "n/a", "TODO.", "lgtm", "See above", "..."):
            p = base_proposal(evidence=[F.ev("run-0412", "retry_budget", note)])
            self.assertEqual(D.report(p, F.RUN_LOG)["outcome"], D.HOLD, repr(note))
        for run in ("", "tbd", None):
            p = base_proposal(evidence=[F.ev(run, "retry_budget", "real note here")])
            self.assertEqual(D.report(p, F.RUN_LOG)["outcome"], D.HOLD, repr(run))

    def test_real_note_not_placeholder(self):
        p = base_proposal(evidence=[F.ev("run-0412", "retry_budget", "n/a was wrong: saw 2 timeouts")])
        self.assertEqual(D.report(p, F.RUN_LOG)["outcome"], D.NO_FLAG)

    def test_undeclared_key_reported(self):
        r = self.rep("undeclared_key")
        self.assertEqual(r["outcome"], D.FLAG)
        self.assertEqual(r["unknown_dimensions"], ["mood_setting"])
        self.assertIn("mood_setting", r["actual_dimensions"])

    def test_single_with_evidence_for_other_key_fails_closed(self):
        p = base_proposal(evidence=[F.ev("run-0415", "memory_window", "archivist lost thread")])
        r = D.report(p, F.RUN_LOG)
        self.assertEqual(r["outcome"], D.FAIL_CLOSED)
        self.assertIn("evidence_for_unchanged", [f["code"] for f in r["findings"]])

    def test_no_change_held(self):
        p = base_proposal(after=copy.deepcopy(F.BASE))
        self.assertIn("empty_diff", D.hold_reasons(D.report(p, F.RUN_LOG)))

    def test_malformed_fails_closed(self):
        bad = [None, [], {"id": ""}, base_proposal(before=[]),
               base_proposal(declared_dimensions="retry_budget"),
               base_proposal(evidence={"run_id": "run-0412"}),
               base_proposal(evidence=["run-0412"])]
        for b in bad:
            r = D.report(b, F.RUN_LOG)
            self.assertEqual(r["outcome"], D.FAIL_CLOSED, repr(b)[:60])
            self.assertEqual(r["findings"][0]["code"], "malformed")

    def test_run_log_accepts_ids_or_dicts(self):
        p = F.PROPOSALS["single_evidenced"]
        self.assertEqual(D.report(p, ["run-0412"])["outcome"], D.NO_FLAG)
        self.assertEqual(D.report(p, [])["outcome"], D.HOLD)

    def test_outcomes_closed_set(self):
        for r in D.report_all(F.PROPOSALS.values(), F.RUN_LOG):
            self.assertIn(r["outcome"], (D.FAIL_CLOSED, D.HOLD, D.FLAG, D.NO_FLAG))

    def test_flag_lists_everything_but_no_flag(self):
        reps = D.report_all(F.PROPOSALS.values(), F.RUN_LOG)
        self.assertEqual(sorted(D.flag(reps)), sorted(
            ["p-two-half", "p-mismatch", "p-ghost-run", "p-empty", "p-tbd", "p-new-key"]))

    def test_report_does_not_mutate(self):
        p = F.PROPOSALS["two_dims_one_evidenced"]
        snap = json.dumps(p, sort_keys=True)
        D.report(p, F.RUN_LOG)
        self.assertEqual(json.dumps(p, sort_keys=True), snap)


class CompareRestrict(unittest.TestCase):

    def test_compare_shared(self):
        c = D.compare(F.PROPOSALS["single_evidenced"], F.PROPOSALS["two_dims_both_evidenced"])
        self.assertEqual(c["shared"], ["retry_budget"])
        self.assertEqual(c["only_b"], ["memory_window"])
        self.assertFalse(c["disjoint"])

    def test_compare_uses_diff_not_declared(self):
        c = D.compare(F.PROPOSALS["single_evidenced"], F.PROPOSALS["declared_mismatch"])
        self.assertTrue(c["disjoint"])

    def test_restrict_narrows_and_copies(self):
        src = F.PROPOSALS["two_dims_one_evidenced"]
        snap = json.dumps(src, sort_keys=True)
        n = D.restrict(src, "retry_budget")
        self.assertEqual(json.dumps(src, sort_keys=True), snap)
        self.assertEqual(D.detect_changes(n["before"], n["after"]), ["retry_budget"])
        self.assertEqual(n["restricted_from"], "p-two-half")
        self.assertEqual(D.report(n, F.RUN_LOG)["outcome"], D.NO_FLAG)

    def test_restrict_to_unevidenced_key_is_held(self):
        n = D.restrict(F.PROPOSALS["two_dims_one_evidenced"], "memory_window")
        self.assertEqual(D.report(n, F.RUN_LOG)["outcome"], D.HOLD)  # trace now empty

    def test_restrict_removed_key(self):
        p = base_proposal()
        del p["after"]["memory_window"]
        n = D.restrict(p, "memory_window")
        self.assertNotIn("memory_window", n["after"])
        self.assertEqual(D.detect_changes(n["before"], n["after"]), ["memory_window"])


class Manifest(unittest.TestCase):

    def test_six_own_names(self):
        self.assertEqual(len(D.DIMENSIONS), 6)
        self.assertEqual(len(set(D.DIMENSIONS)), 6)
        for n in D.DIMENSIONS:
            self.assertRegex(n, r"^[a-z]+_[a-z]+$")

    def test_manifest_avoids_paper_labels(self):
        src = read("dimensions.json").lower()
        for needle in ("prom" + "pt", "topo" + "logy", "model sel" + "ection", "tool pol" + "ic"):
            self.assertNotIn(needle, src, needle)


class Fixtures(unittest.TestCase):

    def test_all_fixtures_hold(self):
        for name, ok, detail in F.checks():
            self.assertTrue(ok, "%s [%s]" % (name, detail))

    def test_main_zero_and_deterministic(self):
        a, b = io.StringIO(), io.StringIO()
        self.assertEqual(F.main(a), 0)
        F.main(b)
        self.assertEqual(a.getvalue(), b.getvalue())
        self.assertIn("10/10", a.getvalue())


class Evidence(unittest.TestCase):

    KEYS = ["id", "section", "excerpt", "chars", "normalized_offset",
            "end_offset_exclusive", "occurrences", "source_window_sha256", "status"]

    def test_metadata(self):
        e = evidence()
        self.assertEqual(e["paper"]["licence"], "CC BY-NC-SA 4.0")
        self.assertEqual(e["paper"]["licence_url"], "https://creativecommons.org/licenses/by-nc-sa/4.0/")
        self.assertIsNone(e["implementation_pin"])
        self.assertIn("CC BY-NC-SA", e["quotation_notice"])
        self.assertEqual(len(e["paper"]["authors"]), 4)

    def test_excerpt_shape(self):
        ex = evidence()["excerpts"]
        self.assertLessEqual(len(ex), 5)
        for x in ex:
            self.assertEqual(list(x), self.KEYS)
            self.assertEqual(x["chars"], len(x["excerpt"]))
            self.assertEqual(x["end_offset_exclusive"] - x["normalized_offset"], x["chars"])
            self.assertLessEqual(x["chars"], 200)
            self.assertNotIn("<", x["excerpt"])

    def test_unverified_figures_only_in_evidence(self):
        e = evidence()
        self.assertEqual(e["empirical_claims"]["status"], "UNVERIFIED")
        texts = " ".join(c["text"] for c in e["empirical_claims"]["claims"])
        for n in ("2" + ".58", "4" + ".30", "42" + ".45"):
            self.assertIn(n, texts)
        num = [x for x in e["excerpts"] if "42" + ".45" in x["excerpt"]]
        self.assertTrue(num and all(x["status"] == "UNVERIFIED" for x in num))

    @unittest.skipUnless(HAVE_PAPER, "paper HTML cache absent")
    def test_excerpts_found_at_offsets(self):
        t = paper_text()
        self.assertEqual(len(t), evidence()["normalization"]["normalized_chars"])
        for x in evidence()["excerpts"]:
            s, e = x["normalized_offset"], x["end_offset_exclusive"]
            self.assertEqual(t[s:e], x["excerpt"], x["id"])
            self.assertEqual(t.count(x["excerpt"]), x["occurrences"], x["id"])

    @unittest.skipUnless(HAVE_PAPER, "paper HTML cache absent")
    def test_window_hashes(self):
        t = paper_text()
        for x in evidence()["excerpts"]:
            s, e = x["normalized_offset"], x["end_offset_exclusive"]
            w = t[max(0, s - 64):min(len(t), e + 64)]
            self.assertEqual(hashlib.sha256(w.encode("utf-8")).hexdigest(),
                             x["source_window_sha256"], x["id"])

    @unittest.skipUnless(HAVE_PAPER, "paper HTML cache absent")
    def test_no_five_word_run_copied(self):
        paper = " " + " ".join(words(re.sub(r"<[^>]+>", " ", paper_text()))) + " "
        e = evidence()["paper"]
        # Attribution (title, authors, licence name) is citation, not copying.
        cite = [e["title"], e["licence_url"], "CC BY-NC-SA 4.0"] + e["authors"]
        for name in CODE + PROSE:
            src = re.sub(r"\s+", " ", read(name))
            for c in cite:
                src = src.replace(c, " | ")
            w = []
            for chunk in src.split("|"):
                cw = words(chunk)
                w.extend(cw + ["\x00"])
            for i in range(len(w) - 4):
                if "\x00" in w[i:i + 5]:
                    continue
                gram = " " + " ".join(w[i:i + 5]) + " "
                self.assertNotIn(gram, paper, "%s: %r" % (name, gram.strip()))


class Hygiene(unittest.TestCase):

    def test_no_allow_vocabulary(self):
        for name in CODE:
            src = read(name).lower()
            for needle in ("al" + "low", "appro" + "v", "per" + "mit", "acc" + "ept"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))

    def test_public_verbs(self):
        tree = ast.parse(read("decaf.py"))
        public = sorted(n.name for n in tree.body
                        if isinstance(n, ast.FunctionDef) and not n.name.startswith("_"))
        self.assertEqual(public, ["compare", "detect_changes", "flag", "hold_reasons",
                                  "load_manifest", "report", "report_all", "restrict"])

    def test_no_scoring_or_execution(self):
        src = read("decaf.py").lower()
        for needle in ("sco" + "re", "subpro" + "cess", "exec(", "eval(", "rank(", "best"):
            self.assertNotIn(needle, src, needle)

    def test_banned_lineage_absent(self):
        needles = ("HM" + "AC", "Two" + "-Ledger", "2611." + "06989", "2611." + "07483",
                   "Harness-" + "Is-the-Model")
        for name in ALL:
            if name == "test_decaf.py":
                continue
            src = read(name)
            for n in needles:
                self.assertNotIn(n, src, "%s: %s" % (name, n))

    def test_paper_numbers_absent_outside_evidence(self):
        for name in CODE + PROSE:
            src = read(name)
            for n in ("2" + ".58", "4" + ".30", "42" + ".45"):
                self.assertNotIn(n, src, "%s: %s" % (name, n))

    def test_prose_words(self):
        for name in PROSE:
            src = read(name)
            for needle in ("KE" + "EP", "Cloud" + "Agent", "Sm" + "ith", "Chec" + "ker",
                           "O" + "rk", "pull " + "request"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))
            self.assertIsNone(re.search(r"\b" + "mer" + r"ge\b", src, re.IGNORECASE), name)

    def test_readme_standing_notes(self):
        src = read("README.md")
        for needle in ("method sketch", "not a reproduction", "not village law",
                       "not Team OS law", "UNVERIFIED", "CC BY-NC-SA 4.0", "Ludex:",
                       "offline"):
            self.assertIn(needle, src, needle)

    def test_notice(self):
        src = read("NOTICE")
        for needle in ("2611.08723", "CC BY-NC-SA 4.0", "Divij Handa", "Christopher Tensmeyer",
                       "Jihyung Kil", "Vlad I. Morariu", "clean-room"):
            self.assertIn(needle, src, needle)

    def test_no_file_reads_parent_index(self):
        for name in ("decaf.py", "fixtures.py", "test_decaf.py"):
            src = read(name)
            self.assertNotIn("os." + "pardir", src, name)
            self.assertNotIn("\"." + "./", src, name)
            self.assertNotIn("day" + "-READ", src, name)

    def test_imports_stdlib_only(self):
        ok = {"copy", "json", "os", "re", "sys", "ast", "hashlib", "html", "io",
              "unittest", "decaf", "fixtures"}
        for name in ("decaf.py", "fixtures.py", "test_decaf.py"):
            for node in ast.walk(ast.parse(read(name))):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [(node.module or "").split(".")[0]]
                else:
                    continue
                for m in mods:
                    self.assertIn(m, ok, "%s imports %s" % (name, m))


if __name__ == "__main__":
    unittest.main()
