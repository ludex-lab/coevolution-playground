"""Tests for the w18-phantom-consensus method sketch (stdlib unittest only).

Run: python3 -m unittest test_phantom.py -v
The excerpt check reads /tmp/w18-2611.08971.html (paper HTML) and is skipped
when absent:
  curl -sL https://arxiv.org/html/2611.08971 -o /tmp/w18-2611.08971.html
"""

import ast
import contextlib
import dataclasses
import hashlib
import html
import inspect
import io
import json
import os
import re
import unittest

import fixtures as F
import phantom as P

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_HTML = "/tmp/w18-2611.08971.html"
IMPL = ("phantom.py", "fixtures.py")
PROSE = ("README.md", "NOTICE")
UNSCORED = ("public_decision", "signal_kind", "estimate_after_reveal")


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


def episodes():
    return {ep.episode_id: ep for ep in F.build_episodes()}


def attrs_read(fn_name):
    """Attribute names read inside one phantom.py function (docstrings ignored)."""
    tree = ast.parse(read("phantom.py"))
    fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == fn_name][0]
    names = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    names |= {n.value for n in ast.walk(fn)
              if isinstance(n, ast.Constant) and isinstance(n.value, str) and n is not
              (fn.body[0].value if isinstance(fn.body[0], ast.Expr) else None)}
    return names


def row(est, rec, pub="accept", kind="ambiguous", after=None, who="naru"):
    return P.Report(reporter=who, reported_group_estimate=est,
                    recorded_private_majority=rec, public_decision=pub,
                    signal_kind=kind, estimate_after_reveal=after)


class CoreMetric(unittest.TestCase):

    def test_belief_error_is_estimate_vs_recorded_majority(self):
        for est in P.LABELS:
            for rec in P.LABELS:
                self.assertEqual(P.detect(row(est, rec)), est != rec, (est, rec))

    def test_no_recorded_majority_is_held(self):
        r = row("accept", None)
        self.assertTrue(P.hold(r))
        self.assertIsNone(P.detect(r))
        self.assertFalse(P.hold(row("accept", "decline")))

    def test_report_counts(self):
        s = P.report(F.build_episodes())
        self.assertEqual((s["rows"], s["held"], s["scored"], s["belief_errors"]), (16, 2, 14, 5))
        self.assertEqual(s["belief_error_rate"], "5/14")

    def test_flag_lists_error_rows(self):
        self.assertEqual(P.flag(F.build_episodes()), [
            ("shed-roof", "naru"), ("shed-roof", "mina"), ("seed-order", "mina"),
            ("shed-roof-public-twin", "naru"), ("shed-roof-public-twin", "mina")])

    def test_detect_reads_only_two_fields(self):
        read_ = attrs_read("detect") | attrs_read("hold")
        self.assertEqual(read_ & {"reported_group_estimate", "recorded_private_majority"},
                         {"reported_group_estimate", "recorded_private_majority"})
        for field in UNSCORED:
            self.assertNotIn(field, read_, field)


class RecordedPrivates(unittest.TestCase):

    def test_fixture_records_are_consistent(self):
        for ep in F.build_episodes():
            self.assertEqual(P.compare(ep), [], ep.episode_id)

    def test_majority_excludes_reporter(self):
        # oto privately declines; the other three accept -> his recorded
        # majority is accept, which matches the record without him.
        roof = episodes()["shed-roof"]
        self.assertEqual(roof.private_of("oto"), "decline")
        self.assertEqual(roof.reports[3].recorded_private_majority, "accept")

    def test_wrong_recorded_majority_is_reported_by_compare(self):
        roof = episodes()["shed-roof"]
        bad = dataclasses.replace(roof.reports[1], recorded_private_majority="decline")
        ep = dataclasses.replace(roof, reports=(roof.reports[0], bad) + roof.reports[2:])
        problems = P.compare(ep)
        self.assertEqual(len(problems), 1)
        self.assertIn("cody", problems[0])

    def test_score_uses_recorded_field_not_a_recount(self):
        # Change a private judgment without touching the recorded field:
        # detect() does not move; compare() reports the stale record.
        roof = episodes()["shed-roof"]
        privates = (("naru", "accept"), ("cody", "decline"), ("mina", "decline"), ("oto", "decline"))
        ep = dataclasses.replace(roof, private_judgments=privates)
        self.assertEqual([P.detect(r) for r in ep.reports], [P.detect(r) for r in roof.reports])
        self.assertTrue(P.compare(ep))

    def test_compare_rejects_unknown_labels_and_kinds(self):
        roof = episodes()["shed-roof"]
        bad = dataclasses.replace(roof.reports[0], signal_kind="loud", public_decision="maybe")
        ep = dataclasses.replace(roof, reports=(bad,) + roof.reports[1:])
        joined = " ".join(P.compare(ep))
        self.assertIn("signal_kind", joined)
        self.assertIn("public_decision", joined)


class NotTheFlipTable(unittest.TestCase):
    """Proves this is not #93 w16-overseer-flip and not a phantom_rate."""

    def test_public_only_change_keeps_belief_error(self):
        for est, rec in (("decline", "accept"), ("accept", "accept"), ("defer", "decline")):
            scores = {P.detect(row(est, rec, pub=pub)) for pub in P.LABELS}
            self.assertEqual(len(scores), 1, (est, rec))

    def test_public_twin_fixture_scores_identically(self):
        eps = episodes()
        roof, twin = eps["shed-roof"], eps["shed-roof-public-twin"]
        for a, b in zip(roof.reports, twin.reports):
            self.assertNotEqual(a.public_decision, b.public_decision)
            self.assertEqual(a.reported_group_estimate, b.reported_group_estimate)
            self.assertEqual(a.recorded_private_majority, b.recorded_private_majority)
            self.assertEqual(P.detect(a), P.detect(b))
        self.assertEqual(P.report([roof])["belief_errors"], P.report([twin])["belief_errors"])

    def test_belief_error_and_public_departure_come_apart(self):
        seed = episodes()["seed-order"]
        mina, oto = seed.reports[2], seed.reports[3]
        # mina: public equals her own private judgment, belief error True
        self.assertEqual(mina.public_decision, seed.private_of("mina"))
        self.assertTrue(P.detect(mina))
        # oto: public departs from the recorded majority, belief error False
        self.assertNotEqual(oto.public_decision, oto.recorded_private_majority)
        self.assertFalse(P.detect(oto))

    def test_no_flip_schema(self):
        for name in IMPL:
            src = read(name).lower()
            for needle in ("hash", "pair_", "flip", "overseer", "baseline", "influence"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))
            self.assertIsNone(re.search(r"\barm\b", src), name)

    def test_report_has_no_public_outcome_rate(self):
        keys = set(P.report(F.build_episodes()))
        self.assertFalse([k for k in keys if "public" in k or "phantom" in k or "outcome" in k])


class NotAnAggregator(unittest.TestCase):

    def test_no_aggregator_in_public_api(self):
        names = [n for n in dir(P) if not n.startswith("_")]
        for bad in ("vo" + "te", "ensem" + "ble", "majority_" + "vo" + "te",
                    "aggregat", "winner", "consensus", "decide"):
            self.assertFalse([n for n in names if bad in n.lower()], bad)
        for bad in ("vo" + "te", "ensem" + "ble"):
            for name in IMPL:
                self.assertNotIn(bad, read(name).lower(), "%s: %s" % (name, bad))

    def test_public_decisions_never_counted(self):
        self.assertNotIn("public_decision", attrs_read("_recount_others"))
        self.assertIn("private_judgments", attrs_read("_recount_others"))
        # public_decision is only read for label validation in compare()
        tree = ast.parse(read("phantom.py"))
        for fn in tree.body:
            if isinstance(fn, ast.FunctionDef) and fn.name != "compare":
                self.assertNotIn("public_decision", attrs_read(fn.name), fn.name)

    def test_no_function_returns_a_group_decision(self):
        eps = F.build_episodes()
        outs = [P.report(eps), P.flag(eps), P.compare(eps[0])]
        for out in outs:
            self.assertNotIn(out, P.LABELS)


class LabelsAndShapeColumns(unittest.TestCase):

    def test_signal_kind_is_ignored(self):
        for est, rec in (("decline", "accept"), ("accept", "accept")):
            scores = {P.detect(row(est, rec, kind=k)) for k in P.SIGNAL_KINDS}
            self.assertEqual(len(scores), 1)
        self.assertNotIn("signal_kind", attrs_read("report") | attrs_read("detect"))

    def test_relabel_all_signal_kinds_keeps_report(self):
        eps = F.build_episodes()
        relabelled = [dataclasses.replace(ep, reports=tuple(
            dataclasses.replace(r, signal_kind="none") for r in ep.reports)) for ep in eps]
        self.assertEqual(P.report(eps), P.report(relabelled))

    def test_after_reveal_is_shape_only(self):
        for after in (None,) + P.LABELS:
            self.assertTrue(P.detect(row("decline", "accept", after=after)))
        self.assertEqual(P.report(F.build_episodes())["after_reveal_filled_shape_only"], 2)

    def test_no_model_call(self):
        for name in IMPL:
            src = read(name).lower()
            for needle in ("openai", "anthropic", "requests", "urllib", "http", "socket", "subprocess"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))


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
        self.assertIn("fixtures: 7/7 passed", outs[0])


class PaperEvidence(unittest.TestCase):

    def test_metadata(self):
        ev = evidence()
        p = ev["paper"]
        self.assertEqual(p["arxiv_id"], "2611.08971")
        self.assertEqual(p["licence"], "CC BY 4.0")
        self.assertIn("creativecommons.org/licenses/by/4.0/", p["licence_evidence"])
        self.assertEqual(p["authors"], ["Disha Sheshanarayana", "Rajat Subhra Pal",
                                        "Manjira Sinha", "Tirthankar Dasgupta"])
        self.assertIsNone(ev["implementation_pin"])
        self.assertEqual(ev["empirical_claims"]["status"], "UNVERIFIED")

    def test_required_quotes_present(self):
        quotes = [e["excerpt"] for e in evidence()["excerpts"]]
        for needle in ("inaccurate estimates of what other agents privately judged",
                       "PBE measures second-order belief error",
                       "recorded private majority of the other agents",
                       "cases with no majority are excluded",
                       "reported estimate of peers"):
            self.assertTrue(any(needle in q for q in quotes), needle)

    def test_offsets_consistent(self):
        for e in evidence()["excerpts"]:
            self.assertEqual(e["status"], "FOUND")
            self.assertEqual(e["end_offset_exclusive"] - e["normalized_offset"], len(e["excerpt"]))
            self.assertEqual(e["chars"], len(e["excerpt"]))

    def test_unverified_figures_only_in_evidence(self):
        texts = " ".join(c["text"] for c in evidence()["empirical_claims"]["claims"])
        self.assertIn("47" + ".8", texts)
        self.assertIn("47" + ".3", texts)

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


class Hygiene(unittest.TestCase):

    def test_no_allow_vocabulary(self):
        for name in IMPL + PROSE:
            src = read(name).lower()
            for needle in ("al" + "low", "appro" + "v", "per" + "mit"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))

    def test_public_verbs(self):
        for verb in ("hold", "report", "detect", "compare", "flag"):
            self.assertTrue(callable(getattr(P, verb)), verb)
        funcs = [n for n, v in vars(P).items()
                 if inspect.isfunction(v) and not n.startswith("_") and v.__module__ == "phantom"]
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
            for needle in ("taint", "freeze", "ledger", "registry", "call_id", "effect_key"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))

    def test_no_paper_empirical_figures(self):
        for name in IMPL + PROSE:
            src = read(name)
            for n in ("47" + ".8", "47" + ".3", "percentage points"):
                self.assertNotIn(n, src, "%s: %s" % (name, n))

    def test_readme_standing_notes(self):
        src = read("README.md")
        for needle in ("method sketch", "not a reproduction", "not village law",
                       "not Team OS law", "UNVERIFIED", "python3 -m unittest test_phantom.py -v",
                       "python3 fixtures.py", "experiments/2026-11-07/w16-overseer-flip/",
                       "Builder reflection", "Ludex:"):
            self.assertIn(needle, src, needle)

    def test_prose_words(self):
        for name in PROSE:
            src = read(name)
            for word in ("KEEP", "CloudAgent", "Smith", "Checker", "Ork"):
                self.assertIsNone(re.search(r"\b%s\b" % word, src), "%s: %s" % (name, word))
            self.assertNotIn("pull request", src.lower(), name)
            self.assertIsNone(re.search(r"\bmerge\b", src, re.IGNORECASE), name)

    def test_notice(self):
        src = read("NOTICE")
        for needle in ("2611.08971", "CC BY 4.0", "Disha Sheshanarayana", "Rajat Subhra Pal",
                       "Manjira Sinha", "Tirthankar Dasgupta", "NeurIPS 2026 SocialAgent",
                       "no upstream code pin", "stdlib", "Synthetic"):
            self.assertIn(needle, src, needle)

    def test_no_test_reads_parent_index(self):
        self.assertNotIn("day" + "-README", read("test_phantom.py"))

    def test_imports_stdlib_only(self):
        ok = {"dataclasses", "typing", "phantom"}
        for name in IMPL:
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
