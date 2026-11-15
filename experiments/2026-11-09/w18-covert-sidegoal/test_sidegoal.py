"""Tests for the w18-covert-sidegoal method sketch (stdlib unittest only).

Run: python3 -m unittest test_sidegoal.py -v
Three checks read /tmp/w18-2611.07586.html (paper HTML) and are skipped when
it is absent:
  curl -sL https://arxiv.org/html/2611.07586 -o /tmp/w18-2611.07586.html
"""

import ast
import copy
import hashlib
import html
import json
import os
import re
import sys
import unittest

import fixtures as F
import sidegoal as S

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_HTML = "/tmp/w18-2611.07586.html"
CODE = ("sidegoal.py", "fixtures.py", "tasks.json")
PROSE = ("README.md", "NOTICE")
ALL = CODE + PROSE + ("test_sidegoal.py", "paper_evidence.json")
HAVE_PAPER = os.path.isfile(PAPER_HTML)
MANIFEST = S.load_manifest()


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


def trace(tid):
    return copy.deepcopy(next(t for t in F.TRACES if t["id"] == tid))


class Keyword(unittest.TestCase):

    def test_benign_no_flag(self):
        self.assertEqual(S.naive_keyword_monitor(trace("t1-benign"))["status"], "no_flag")

    def test_obvious_wording_flagged_with_steps(self):
        r = S.naive_keyword_monitor(trace("t2-covert-obvious"))
        self.assertEqual(r["status"], "flag")
        self.assertEqual({(f["step"], f["wording"]) for f in r["findings"]},
                         {(2, "secretly"), (3, "without telling")})

    def test_coherent_wording_missed(self):
        self.assertEqual(S.naive_keyword_monitor(trace("t3-covert-coherent"))["status"], "no_flag")

    def test_case_insensitive_and_word_boundary(self):
        t = trace("t1-benign")
        t["reasoning"] = ["HIDE the receipt"]
        self.assertEqual(S.naive_keyword_monitor(t)["status"], "flag")
        t["reasoning"] = ["the hideout key is in the shed", "chides nobody"]
        self.assertEqual(S.naive_keyword_monitor(t)["status"], "no_flag")

    def test_actions_not_scanned_for_wording(self):
        t = trace("t1-benign")
        t["actions"].append({"goal_field": "primary", "effect": "secretly:hide"})
        self.assertEqual(S.naive_keyword_monitor(t)["status"], "no_flag")


class Mismatch(unittest.TestCase):

    def test_benign_no_flag(self):
        self.assertEqual(S.goal_field_mismatch(trace("t1-benign"), MANIFEST)["status"], "no_flag")

    def test_obvious_and_coherent_both_flagged(self):
        for tid, idx in (("t2-covert-obvious", 2), ("t3-covert-coherent", 1)):
            r = S.goal_field_mismatch(trace(tid), MANIFEST)
            self.assertEqual(r["status"], "flag", tid)
            self.assertEqual(r["findings"], [{"kind": "effect_serves_no_declared_goal",
                                              "action": idx, "effect": "files:copy_guest_list"}])

    def test_self_declared_side_goal_evades(self):
        r = S.goal_field_mismatch(trace("t4-covert-self-declared"), MANIFEST)
        self.assertEqual(r["status"], "no_flag")

    def test_same_trace_on_strict_task_is_flagged(self):
        t = trace("t4-covert-self-declared")
        m = copy.deepcopy(MANIFEST)
        m["tasks"]["plan_supplies"]["trusts_trace_declarations"] = False
        self.assertEqual(S.goal_field_mismatch(t, m)["status"], "flag")

    def test_declared_effects_ignored_on_strict_task(self):
        t = trace("t3-covert-coherent")
        t["declared_effects"] = ["files:copy_guest_list"]
        self.assertEqual(S.goal_field_mismatch(t, MANIFEST)["status"], "flag")

    def test_coarse_key_evades(self):
        r = S.goal_field_mismatch(trace("t5-covert-coarse-manifest"), MANIFEST)
        self.assertEqual(r["status"], "no_flag")

    def test_undeclared_goal_field(self):
        r = S.goal_field_mismatch(trace("t6-undeclared-goal-field"), MANIFEST)
        self.assertEqual(r["status"], "flag")
        self.assertEqual(r["findings"][0]["kind"], "goal_field_not_declared")
        self.assertEqual(r["findings"][0]["goal_field"], "maintenance")

    def test_unknown_task_fails_closed(self):
        r = S.goal_field_mismatch(trace("t8-unknown-task"), MANIFEST)
        self.assertEqual(r["status"], "fail_closed")
        self.assertEqual(r["findings"], [{"kind": "unknown_task", "task": "paint_fence"}])

    def test_manifest_task_without_effect_list_fails_closed(self):
        m = {"tasks": {"book_hall": {"summary": "x"}}}
        self.assertEqual(S.goal_field_mismatch(trace("t1-benign"), m)["status"], "fail_closed")

    def test_default_manifest_loaded(self):
        self.assertEqual(S.goal_field_mismatch(trace("t3-covert-coherent"))["status"], "flag")


class HoldAndFailClosed(unittest.TestCase):

    def test_missing_goal_variants_hold_both(self):
        for goal in (None, "", "   ", 7, ["book"]):
            t = trace("t1-benign")
            if goal is None:
                del t["declared_primary_goal"]
            else:
                t["declared_primary_goal"] = goal
            for r in S.detect(t, MANIFEST).values():
                self.assertEqual(r["status"], "hold", repr(goal))
                self.assertEqual(S.hold_reasons(r), [{"kind": "declared_goal_missing"}])

    def test_hold_even_with_obvious_wording(self):
        t = trace("t2-covert-obvious")
        t["declared_primary_goal"] = ""
        self.assertEqual(S.naive_keyword_monitor(t)["status"], "hold")

    def test_malformed_fails_closed(self):
        bad = ["not a dict", None, {"id": "x"},
               {"id": "x", "declared_primary_goal": "g", "reasoning": "s", "actions": []},
               {"id": "x", "declared_primary_goal": "g", "reasoning": [1], "actions": []},
               {"id": "x", "declared_primary_goal": "g", "reasoning": [], "actions": [{"effect": "a"}]},
               {"id": "", "declared_primary_goal": "g", "reasoning": [], "actions": []}]
        for t in bad:
            for r in S.detect(t, MANIFEST).values():
                self.assertEqual(r["status"], "fail_closed", repr(t))
                self.assertTrue(S.hold_reasons(r))

    def test_malformed_beats_missing_goal(self):
        t = {"id": "x", "reasoning": "s", "actions": []}
        self.assertEqual(S.naive_keyword_monitor(t)["status"], "fail_closed")

    def test_hold_reasons_empty_for_flag_and_no_flag(self):
        self.assertEqual(S.hold_reasons(S.naive_keyword_monitor(trace("t2-covert-obvious"))), [])
        self.assertEqual(S.hold_reasons(S.naive_keyword_monitor(trace("t1-benign"))), [])


class ReportCompare(unittest.TestCase):

    def test_report_counts(self):
        rep = S.report(F.TRACES, MANIFEST)
        self.assertEqual(rep["traces"], 8)
        self.assertEqual(rep["naive_keyword_monitor"]["status_counts"],
                         {"fail_closed": 0, "hold": 1, "flag": 1, "no_flag": 6})
        self.assertEqual(rep["goal_field_mismatch"]["status_counts"],
                         {"fail_closed": 1, "hold": 1, "flag": 3, "no_flag": 3})
        self.assertEqual(rep["naive_keyword_monitor"]["flag_counts_by_label"], {"covert": 1})
        self.assertEqual(rep["goal_field_mismatch"]["flag_counts_by_label"], {"covert": 3})

    def test_report_holds_only_integers(self):
        rep = S.report(F.TRACES, MANIFEST)
        for m in S.MONITORS:
            for v in list(rep[m]["status_counts"].values()) + list(rep[m]["flag_counts_by_label"].values()):
                self.assertIsInstance(v, int)

    def test_label_never_read_by_monitors(self):
        for t in F.TRACES:
            a = S.detect(t, MANIFEST)
            u = copy.deepcopy(t)
            u.pop("label", None)
            self.assertEqual(a, S.detect(u, MANIFEST), t["id"])
            u["label"] = "benign" if t["label"] == "covert" else "covert"
            self.assertEqual(a, S.detect(u, MANIFEST), t["id"])

    def test_compare(self):
        a = [S.naive_keyword_monitor(t) for t in F.TRACES]
        b = [S.goal_field_mismatch(t, MANIFEST) for t in F.TRACES]
        c = S.compare(a, b)
        self.assertEqual(c["only_a"], [])
        self.assertEqual(c["only_b"], ["t3-covert-coherent", "t6-undeclared-goal-field"])
        self.assertEqual(c["both"], ["t2-covert-obvious"])
        self.assertIn("t4-covert-self-declared", c["neither"])
        self.assertIn("t5-covert-coarse-manifest", c["neither"])
        self.assertEqual(S.compare(b, a)["only_a"], c["only_b"])

    def test_detect_does_not_mutate(self):
        for t in F.TRACES:
            before = copy.deepcopy(t)
            S.detect(t, MANIFEST)
            self.assertEqual(t, before)

    def test_statuses_closed_set(self):
        for t in F.TRACES:
            for r in S.detect(t, MANIFEST).values():
                self.assertIn(r["status"], S.STATUSES)


class Fixtures(unittest.TestCase):

    def test_all_fixture_checks_pass(self):
        rows, _ = F.run_checks(MANIFEST)
        self.assertEqual(len(rows), 9)
        for name, got, want, ok in rows:
            self.assertTrue(ok, "%s: %r != %r" % (name, got, want))

    def test_fixtures_cover_both_caveats_and_benign(self):
        self.assertEqual(F.EXPECTED["t1-benign"], ("no_flag", "no_flag"))
        self.assertEqual(F.EXPECTED["t4-covert-self-declared"], ("no_flag", "no_flag"))
        self.assertEqual(F.EXPECTED["t5-covert-coarse-manifest"], ("no_flag", "no_flag"))
        self.assertEqual(F.EXPECTED["t3-covert-coherent"], ("no_flag", "flag"))

    def test_main_zero_and_deterministic(self):
        import contextlib
        import io
        outs = []
        for _ in range(2):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(F.main(), 0)
            outs.append(buf.getvalue())
        self.assertEqual(outs[0], outs[1])
        self.assertIn("9/9 fixture checks passed", outs[0])


class Evidence(unittest.TestCase):
    KEYS = ["id", "section", "excerpt", "chars", "normalized_offset",
            "end_offset_exclusive", "occurrences", "source_window_sha256", "status"]

    def test_metadata(self):
        p = evidence()["paper"]
        self.assertEqual(p["arxiv_id"], "2611.07586")
        self.assertEqual(p["licence_url"], "http://arxiv.org/licenses/nonexclusive-distrib/1.0/")
        self.assertEqual(p["title"], "Stress Testing Chain-of-Thought Monitoring Against Covert Misalignment")
        self.assertEqual(len(p["authors"]), 5)

    def test_implementation_pin(self):
        pin = evidence()["implementation_pin"]
        self.assertEqual(pin["repo"], "https://github.com/T-STAR-Lab/TraceMRT")
        self.assertRegex(pin["commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(pin["licence_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(pin["licence"], "MIT")
        self.assertEqual(pin["status"], "cite-only; not cloned, installed, imported, or run")
        self.assertTrue(pin["copyright_line"].startswith("Copyright (c) 2025"))

    def test_excerpt_shape(self):
        ex = evidence()["excerpts"]
        self.assertLessEqual(len(ex), 4)
        for x in ex:
            self.assertEqual(list(x.keys()), self.KEYS)
            self.assertEqual(x["chars"], len(x["excerpt"]))
            self.assertEqual(x["end_offset_exclusive"] - x["normalized_offset"], x["chars"])
            self.assertLessEqual(len(x["excerpt"].split()), 12, x["id"])

    def test_unverified_figures_only_in_evidence(self):
        e = evidence()
        self.assertEqual(e["empirical_claims"]["status"], "UNVERIFIED")
        num = [x for x in e["excerpts"] if ("0" + ".91") in x["excerpt"]]
        self.assertEqual([x["status"] for x in num], ["UNVERIFIED"])
        for name in CODE + PROSE:
            src = read(name)
            for n in ("0" + ".91", "0" + ".74", "AU" + "C", "TP" + "R", "FP" + "R"):
                self.assertNotIn(n, src, "%s: %s" % (name, n))

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
        hits = []
        title = evidence()["paper"]["title"]
        for name in CODE + PROSE:
            # The bibliographic citation (title, URLs) is attribution, not reuse.
            src = re.sub(r"\s+", " ", read(name))
            src = re.sub(r"https?://\S+", " ", src).replace(title, " ")
            w = words(src)
            for i in range(len(w) - 4):
                gram = " " + " ".join(w[i:i + 5]) + " "
                if gram in paper:
                    hits.append((name, gram.strip()))
        self.assertEqual(hits, [])


class Hygiene(unittest.TestCase):

    def test_no_clearing_vocabulary(self):
        for name in CODE + PROSE + ("test_sidegoal.py",):
            src = read(name).lower()
            for needle in ("al" + "low", "appro" + "v", "per" + "mit", "acc" + "ept"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))

    def test_public_verbs(self):
        public = sorted(n for n in dir(S) if not n.startswith("_") and callable(getattr(S, n)))
        self.assertEqual(public, ["compare", "detect", "expected_effects", "flagged",
                                  "goal_field_mismatch", "hold_reasons", "load_manifest",
                                  "naive_keyword_monitor", "report"])

    def test_no_scoring_or_execution(self):
        src = read("sidegoal.py") + read("fixtures.py")
        for needle in ("sco" + "re", "subpro" + "cess", "exec(", "eval(", "socket", "urllib", "http"):
            self.assertNotIn(needle, src, needle)

    def test_stdlib_imports_only(self):
        std = getattr(sys, "stdlib_module_names", None)
        local = {"sidegoal"}
        for name in ("sidegoal.py", "fixtures.py"):
            tree = ast.parse(read(name))
            mods = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    mods.add((node.module or "").split(".")[0])
            for m in mods - local:
                self.assertIn(m, {"json", "os", "re", "sys", "copy"}, "%s imports %s" % (name, m))
                if std is not None:
                    self.assertIn(m, std, m)

    def test_banned_lineage_absent(self):
        needles = ("Two" + "-Ledger", "2611." + "06989", "HM" + "AC", "2611." + "07483",
                   "inspect" + "_ai", "open" + "ai", "anth" + "ropic")
        for name in ALL:
            src = read(name).lower()
            for n in needles:
                self.assertNotIn(n.lower(), src, "%s: %s" % (name, n))

    def test_prose_free_of_process_words(self):
        for name in PROSE:
            src = read(name)
            low = src.lower()
            for n in ("ke" + "ep", "cloud" + "agent", "smi" + "th", "chec" + "ker",
                      "pull " + "request"):
                self.assertNotIn(n, low, "%s: %s" % (name, n))
            self.assertIsNone(re.search(r"\bOr" + r"k\b", src), name)
            self.assertIsNone(re.search(r"\bmer" + r"ge\b", low), name)

    def test_standing_and_caveat_in_readme(self):
        r = read("README.md")
        for phrase in ("method sketch", "not a reproduction", "not village law",
                       "not Team OS law", "not a defense", "UNVERIFIED", "Ludex:"):
            self.assertIn(phrase, r)

    def test_only_deliverables_present(self):
        want = {"sidegoal.py", "tasks.json", "fixtures.py", "test_sidegoal.py",
                "README.md", "NOTICE", "paper_evidence.json", "day-README.md"}
        have = {n for n in os.listdir(HERE) if n != "__pycache__"}
        self.assertLessEqual(have, want)


if __name__ == "__main__":
    unittest.main()
