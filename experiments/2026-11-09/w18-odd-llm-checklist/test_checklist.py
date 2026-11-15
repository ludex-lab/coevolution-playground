"""Tests for the w18-odd-llm-checklist method sketch (stdlib unittest only).

Run: python3 -m unittest test_checklist.py -v
Two checks read /tmp/w18-2611.08932.html (paper HTML) and are skipped when
it is absent:
  curl -sL https://arxiv.org/html/2611.08932 -o /tmp/w18-2611.08932.html
"""

import ast
import contextlib
import copy
import hashlib
import html
import inspect
import io
import json
import os
import re
import unittest

import checklist as C
import fixtures as F

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_HTML = "/tmp/w18-2611.08932.html"
IMPL = ("checklist.py", "fixtures.py", "checklist.json")
PROSE = ("README.md", "NOTICE")
BLOCK_NAMES = ["Cognitive Architecture", "Identity", "Inference Configuration",
               "Behavioral Submodel", "Validation"]


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


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def desc(blocks, name="t"):
    return {"id": name, "blocks": blocks}


class Manifest(unittest.TestCase):

    def test_five_blocks_exact_names_in_order(self):
        blocks = C.CHECKLIST["blocks"]
        self.assertEqual([b["id"] for b in blocks], list("ABCDE"))
        self.assertEqual([b["name"] for b in blocks], BLOCK_NAMES)

    def test_items_are_well_formed(self):
        seen_ids, seen_fields = set(), set()
        for b in C.CHECKLIST["blocks"]:
            self.assertGreaterEqual(len(b["items"]), 3)
            self.assertTrue(any(i["required"] for i in b["items"]), b["id"])
            for n, item in enumerate(b["items"], 1):
                self.assertEqual(item["id"], "%s%d" % (b["id"], n))
                self.assertIsInstance(item["required"], bool)
                self.assertRegex(item["field"], r"^[a-z][a-z_]+$")
                self.assertTrue(item["asks"].strip())
                self.assertNotIn(item["id"], seen_ids)
                self.assertNotIn(item["field"], seen_fields)
                seen_ids.add(item["id"])
                seen_fields.add(item["field"])

    def test_no_scoring_scale_in_manifest(self):
        src = read("checklist.json").lower()
        for needle in ("score", "partially", "determined", "weight", "points"):
            self.assertNotIn(needle, src, needle)


class PlaceholderRule(unittest.TestCase):

    def state(self, value):
        blocks = copy.deepcopy(F.FULL_BLOCKS)
        blocks["C"]["model_string"] = value
        d = C.detect(desc(blocks))["blocks"]["C"]
        for key in ("documented", "missing", "placeholder"):
            if "C1" in d[key]:
                return key
        return None

    def test_placeholder_words(self):
        for v in ("TBD", "tbd.", " default ", "Default", "", "   ", "n/a", "N/A.", "unknown",
                  "see code", "...", [], {}):
            self.assertEqual(self.state(v), "placeholder", repr(v))

    def test_documented_values(self):
        for v in ("toy-model-2026-10-01", 0, 0.0, False, ["x"], {"k": "v"},
                  "n/a: this run has no tools", "default temperature 0.7 per service docs"):
            self.assertEqual(self.state(v), "documented", repr(v))

    def test_none_and_absent_are_missing(self):
        self.assertEqual(self.state(None), "missing")
        blocks = copy.deepcopy(F.FULL_BLOCKS)
        del blocks["C"]["model_string"]
        self.assertIn("C1", C.detect(desc(blocks))["blocks"]["C"]["missing"])


class Detect(unittest.TestCase):

    def test_full_has_no_gaps(self):
        d = C.detect(F.by_id()["full"])
        for key, row in d["blocks"].items():
            self.assertEqual(row["required_gaps"], [], key)
        self.assertEqual(d["undeclared_blocks"], [])
        self.assertEqual(d["undeclared_fields"], {})

    def test_gap_stays_in_its_block(self):
        d = C.detect(F.by_id()["no-inference-config"])
        self.assertEqual(d["blocks"]["C"]["missing"], ["C1", "C2", "C3", "C4"])
        for key in "ABDE":
            self.assertEqual(d["blocks"][key]["missing"], [], key)

    def test_undeclared_field_listed(self):
        blocks = copy.deepcopy(F.FULL_BLOCKS)
        blocks["C"]["vibe"] = "warm"
        self.assertEqual(C.detect(desc(blocks))["undeclared_fields"], {"C": ["vibe"]})

    def test_hold(self):
        self.assertEqual(C.hold(desc(F.FULL_BLOCKS)), [])
        self.assertEqual(C.hold("text"), ["description is not an object"])
        self.assertIn("no id", C.hold({"blocks": {}}))
        self.assertIn("no blocks object", C.hold({"id": "x", "blocks": []}))
        self.assertIn("block C is not an object", C.hold(desc({"C": "TBD"})))
        self.assertIsNone(C.detect({"id": "x"}))

    def test_empty_description_flags_every_block(self):
        row = C.flag([desc({}, "empty")])[0]
        self.assertEqual(sorted(row["required_gaps"]), list("ABCDE"))


class ReportCompareFlag(unittest.TestCase):

    def test_report_has_only_per_block_counts(self):
        for row in C.report(F.build_descriptions()):
            self.assertEqual(sorted(row), ["blocks", "id", "undeclared_blocks"])
            for key, b in row["blocks"].items():
                self.assertEqual(b["name"], BLOCK_NAMES["ABCDE".index(key)])
                self.assertRegex(b["documented"], r"^\d+/\d+$")
                self.assertRegex(b["required_documented"], r"^\d+/\d+$")

    def test_report_held_row(self):
        self.assertEqual(C.report([{"id": "x"}]), [{"id": "x", "held": ["no blocks object"]}])

    def test_flag_set(self):
        flagged = {r["id"]: r for r in C.flag(F.build_descriptions())}
        self.assertEqual(sorted(flagged), ["extra-block", "no-inference-config",
                                           "placeholders", "stance-dropped"])
        self.assertEqual(flagged["stance-dropped"]["required_gaps"], {"D": ["D2"]})

    def test_compare_both_ways(self):
        d = F.by_id()
        out = C.compare(d["no-inference-config"], d["full"])
        self.assertEqual(out["only_in_a"], {})
        self.assertEqual(out["only_in_b"], {"C": ["C1", "C2", "C3", "C4"]})
        self.assertEqual((out["a"], out["b"]), ("no-inference-config", "full"))
        same = C.compare(d["full"], d["full"])
        self.assertEqual((same["only_in_a"], same["only_in_b"]), ({}, {}))
        self.assertIsNone(C.compare({"id": "x"}, d["full"]))

    def test_extra_block_does_not_change_coverage(self):
        d = F.by_id()
        a = C.report([d["full"]])[0]["blocks"]
        b = C.report([d["extra-block"]])[0]["blocks"]
        self.assertEqual(a, b)


class FixturesRunner(unittest.TestCase):

    def test_all_fixtures_pass(self):
        self.assertTrue(all(ok for _, ok in F.run_checks()))

    def test_main_returns_zero_and_is_deterministic(self):
        outs = []
        for _ in range(2):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(F.main(), 0)
            outs.append(buf.getvalue())
        self.assertEqual(outs[0], outs[1])
        self.assertIn("fixtures: 8/8 passed", outs[0])


class PaperEvidence(unittest.TestCase):

    def test_metadata(self):
        ev = evidence()
        p = ev["paper"]
        self.assertEqual(p["arxiv_id"], "2611.08932")
        self.assertEqual(p["title"],
                         "ODD+LLM: Specifying LLM-Agent Behavior for Reproducible Social Simulation")
        self.assertEqual(p["licence"], "CC BY 4.0")
        self.assertIn("creativecommons.org/licenses/by/4.0/", p["licence_evidence"])
        self.assertEqual(p["authors"], ["Justin Downes", "Robby Milletich", "Newel Hirst"])
        self.assertIsNone(ev["implementation_pin"])
        self.assertEqual(ev["empirical_claims"]["status"], "UNVERIFIED")

    def test_block_heading_quotes_match_manifest(self):
        quotes = [e["excerpt"] for e in evidence()["excerpts"]]
        for letter, name in zip("ABCDE", BLOCK_NAMES):
            self.assertIn("Block %s: %s" % (letter, name), quotes)
        self.assertTrue(any("five documentation blocks" in q for q in quotes))

    def test_offsets_consistent(self):
        for e in evidence()["excerpts"]:
            self.assertEqual(e["status"], "FOUND")
            self.assertEqual(e["end_offset_exclusive"] - e["normalized_offset"], len(e["excerpt"]))
            self.assertEqual(e["chars"], len(e["excerpt"]))

    def test_unverified_figures_only_in_evidence(self):
        texts = " ".join(c["text"] for c in evidence()["empirical_claims"]["claims"])
        self.assertIn("0" + ".35", texts)
        self.assertIn("77" + "%", texts)

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
        for c in ev["empirical_claims"]["claims"]:
            self.assertEqual(t.count(c["text"]), c["occurrences"])

    @unittest.skipUnless(os.path.exists(PAPER_HTML), "paper HTML not cached at " + PAPER_HTML)
    def test_item_wording_not_lifted_from_paper(self):
        """No 4-word run of any item question or field name appears in the paper."""
        with open(PAPER_HTML, encoding="utf-8") as fh:
            paper = " " + " ".join(words(re.sub(r"<[^>]+>", " ", normalize(fh.read())))) + " "
        for b in C.CHECKLIST["blocks"]:
            for item in b["items"]:
                for text in (item["asks"], item["field"].replace("_", " ")):
                    w = words(text)
                    for i in range(max(1, len(w) - 3)):
                        gram = " " + " ".join(w[i:i + 4]) + " "
                        if len(w[i:i + 4]) == 4:
                            self.assertNotIn(gram, paper, "%s: %r" % (item["id"], gram))
                    if len(w) > 1:
                        self.assertNotIn(" " + " ".join(w) + " ", paper, item["id"])


class Hygiene(unittest.TestCase):

    def test_no_allow_vocabulary(self):
        for name in IMPL + PROSE:
            src = read(name).lower()
            for needle in ("al" + "low", "appro" + "v", "per" + "mit"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))

    def test_public_verbs(self):
        funcs = [n for n, v in vars(C).items()
                 if inspect.isfunction(v) and not n.startswith("_") and v.__module__ == "checklist"]
        self.assertEqual(sorted(funcs), ["compare", "detect", "flag", "hold", "report"])

    def test_banned_lineage_absent(self):
        needles = ("HM" + "AC", "Two" + "-Ledger", "two" + "_ledger", "2611." + "06989",
                   "2611." + "06924", "2611." + "07483")
        for name in sorted(os.listdir(HERE)):
            if os.path.isfile(os.path.join(HERE, name)):
                src = read(name)
                for n in needles:
                    self.assertNotIn(n, src, "%s: %s" % (name, n))

    def test_no_sibling_mechanisms(self):
        for name in IMPL:
            src = read(name).lower()
            for needle in ("ledger", "effect", "harness", "execute", "subprocess", "score"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))

    def test_no_paper_empirical_figures(self):
        for name in IMPL + PROSE:
            src = read(name)
            for n in ("0" + ".35", "1" + ".00", "77" + "%"):
                self.assertNotIn(n, src, "%s: %s" % (name, n))

    def test_readme_standing_notes(self):
        src = read("README.md")
        for needle in ("method sketch", "not a reproduction", "not village law",
                       "not Team OS law", "UNVERIFIED", "python3 -m unittest test_checklist.py -v",
                       "python3 fixtures.py", "Builder reflection", "Ludex:"):
            self.assertIn(needle, src, needle)
        for name in BLOCK_NAMES:
            self.assertIn(name, src, name)

    def test_prose_words(self):
        for name in PROSE:
            src = read(name)
            for word in ("KEEP", "CloudAgent", "Smith", "Checker", "Ork"):
                self.assertIsNone(re.search(r"\b%s\b" % word, src), "%s: %s" % (name, word))
            self.assertNotIn("pull request", src.lower(), name)
            self.assertIsNone(re.search(r"\bmerge\b", src, re.IGNORECASE), name)

    def test_notice(self):
        src = read("NOTICE")
        for needle in ("2611.08932", "CC BY 4.0", "Justin Downes", "Robby Milletich",
                       "Newel Hirst", "ODD+LLM: Specifying LLM-Agent Behavior",
                       "no upstream code", "stdlib", "Synthetic", "not copied"):
            self.assertIn(needle, src, needle)

    def test_no_test_reads_parent_index(self):
        self.assertNotIn("day" + "-README", read("test_checklist.py"))

    def test_imports_stdlib_only(self):
        ok = {"json", "os", "copy", "checklist"}
        for name in ("checklist.py", "fixtures.py"):
            for node in ast.walk(ast.parse(read(name))):
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [node.module]
                else:
                    continue
                for m in mods:
                    self.assertIn(m.split(".")[0], ok, "%s imports %s" % (name, m))


if __name__ == "__main__":
    unittest.main()
