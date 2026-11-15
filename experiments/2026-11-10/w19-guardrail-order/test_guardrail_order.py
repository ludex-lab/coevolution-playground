"""Tests for the w19-guardrail-order method sketch (stdlib unittest only).

Run: python3 -m unittest test_guardrail_order.py -v
The excerpt check reads /tmp/w19-2611.09088.html (paper HTML) and is skipped
when absent:
  curl -sL https://arxiv.org/html/2611.09088 -o /tmp/w19-2611.09088.html
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
import sys
import unittest

import fixtures as F
import guardrail_order as G

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_HTML = "/tmp/w19-2611.09088.html"
IMPL = ("guardrail_order.py", "fixtures.py")
PROSE = ("README.md", "NOTICE")
OP_TOKEN = "save_" + "allow_rule"


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


def deliverables():
    return sorted(n for n in os.listdir(HERE)
                  if os.path.isfile(os.path.join(HERE, n)) and not n.endswith(".pyc"))


class BeforeAfter(unittest.TestCase):
    """(a) blocked before the ops, (b) executes after them."""

    def test_a_prohibited_edit_blocked_before_ops(self):
        h = F.fresh()
        rec = h.attempt_edit(F.PROHIBITED, "rewrite")
        self.assertEqual(rec.outcome, "blocked")
        self.assertEqual(rec.stages_run, (G.GUARDRAIL,))
        self.assertNotIn(F.PROHIBITED, h.files)

    def test_b_prohibited_edit_executes_after_ops(self):
        h, before, _, after, _ = F.scenario()
        self.assertEqual(before.outcome, "blocked")
        self.assertEqual(after.outcome, "executed")
        self.assertEqual(after.stages_run, (G.EDIT_TOOL,))
        self.assertEqual(h.files[F.PROHIBITED], "rewrite")

    def test_reapply_alone_breaks(self):
        h = F.fresh()
        h.reapply_plugin(G.GUARDRAIL)
        self.assertEqual(h.attempt_edit(F.PROHIBITED).outcome, "executed")

    def test_saved_rule_alone_breaks(self):
        h = F.fresh()
        getattr(h, OP_TOKEN)("")
        self.assertEqual(h.attempt_edit(F.PROHIBITED).outcome, "executed")

    def test_saved_rule_scoped_elsewhere_leaves_path(self):
        h = F.fresh()
        getattr(h, OP_TOKEN)("notes/")
        self.assertEqual(h.attempt_edit(F.PROHIBITED).outcome, "blocked")
        self.assertEqual(G.check_order(h.history())["status"], G.ORDER_OK)

    def test_ops_are_logged_and_config_untouched(self):
        h = F.fresh()
        cfg = copy.deepcopy(h.config)
        F.after_ops(h)
        self.assertEqual(h.config, cfg)
        self.assertEqual(h.ops_log, ["reapply_plugin:guardrail", OP_TOKEN + ":"])
        self.assertTrue(h.config_lists_active(G.GUARDRAIL))

    def test_unknown_plugin_rejected(self):
        with self.assertRaises(ValueError):
            F.fresh().reapply_plugin("nope")


class OrderCheck(unittest.TestCase):
    """(c) check passes before the ops and fails after them."""

    def test_c_check_ok_before_ops(self):
        _, _, hist_before, _, _ = F.scenario()
        res = G.check_order(hist_before, required="guardrail", before="edit_tool")
        self.assertEqual(res["status"], G.ORDER_OK)
        self.assertEqual(res["broken"], [])

    def test_c_check_broken_after_ops(self):
        h, _, _, after, benign = F.scenario()
        res = G.check_order(h.history(), required="guardrail", before="edit_tool")
        self.assertEqual(res["status"], G.ORDER_BROKEN)
        self.assertEqual(res["broken"], [after.decision_id, benign.decision_id])

    def test_benign_edit_after_ops_still_broken(self):
        h, _, _, _, benign = F.scenario()
        self.assertEqual(benign.outcome, "executed")
        self.assertEqual(G.check_order([benign])["status"], G.ORDER_BROKEN)

    def test_benign_edit_before_ops_ok(self):
        h = F.fresh()
        rec = h.attempt_edit(F.BENIGN)
        self.assertEqual(rec.stages_run, (G.GUARDRAIL, G.EDIT_TOOL))
        self.assertEqual(G.check_order(h.history())["status"], G.ORDER_OK)

    def test_late_guardrail_is_broken(self):
        rec = G.DecisionRecord(0, "edit", "a", (G.EDIT_TOOL, G.GUARDRAIL), "executed")
        self.assertEqual(G.check_order([rec])["status"], G.ORDER_BROKEN)

    def test_empty_history_held(self):
        res = G.check_order([])
        self.assertEqual(res["status"], G.HOLD)
        self.assertNotEqual(res["status"], G.ORDER_OK)
        self.assertIsNotNone(G.hold([]))

    def test_malformed_record_held(self):
        rec = G.DecisionRecord(0, "edit", "a", (), "unhandled")
        self.assertEqual(G.check_order([rec])["status"], G.HOLD)

    def test_history_is_append_only_snapshot(self):
        h = F.fresh()
        h.attempt_edit(F.BENIGN)
        snap = h.history()
        self.assertIsInstance(snap, tuple)
        with self.assertRaises(Exception):
            snap[0].stages_run = ()
        h.attempt_edit(F.PROHIBITED)
        self.assertEqual(len(snap), 1)
        self.assertEqual([r.decision_id for r in h.history()], [0, 1])

    def test_report_and_flag(self):
        h, _, _, _, _ = F.scenario()
        out = G.report(h.history())
        self.assertTrue(out.startswith("order check: order_broken"))
        self.assertEqual(len(G.flag(h.history())), 2)

    def test_status_vocabulary(self):
        self.assertEqual({G.ORDER_OK, G.ORDER_BROKEN, G.HOLD},
                         {"order_ok", "order_broken", "hold"})


class RuntimeNotConfig(unittest.TestCase):
    """(d) the check reads runtime history, never static config."""

    def test_d_config_lists_active_while_check_fails(self):
        h, _, _, _, _ = F.scenario()
        self.assertTrue(h.config_lists_active(G.GUARDRAIL))
        self.assertEqual(G.check_order(h.history())["status"], G.ORDER_BROKEN)
        cmp_ = G.compare(h.config_lists_active(G.GUARDRAIL), h.history())
        self.assertTrue(cmp_["mismatch"])

    def test_d_mutating_config_has_no_effect(self):
        h, _, _, _, _ = F.scenario()
        hist = h.history()
        base = G.check_order(hist)
        for mutate in (lambda c: c["plugins"].pop(G.GUARDRAIL),
                       lambda c: c.update(pipeline=[G.EDIT_TOOL]),
                       lambda c: c.clear()):
            mutate(h.config)
            self.assertEqual(G.check_order(hist), base)
        self.assertEqual(G.check_order(h.history()), base)

    def test_d_config_says_inactive_runtime_ok(self):
        ok, _ = F.f_d_config_says_inactive_runtime_ok()
        self.assertTrue(ok)

    def test_d_check_signature_has_no_config(self):
        params = list(inspect.signature(G.check_order).parameters)
        self.assertEqual(params, ["history", "required", "before"])

    def test_d_check_layer_source_never_names_config(self):
        tree = ast.parse(read("guardrail_order.py"))
        layer = {"check_order", "detect", "hold", "flag", "report", "compare", "_decision_ok"}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in layer:
                names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
                attrs = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
                for bad in ("config", "Harness", "_chain", "plugins", "pipeline",
                            "config_lists_active", "_saved_rules"):
                    self.assertNotIn(bad, names | attrs, "%s reads %s" % (node.name, bad))

    def test_d_compare_bool_never_changes_status(self):
        h, _, _, _, _ = F.scenario()
        a = G.compare(True, h.history())
        b = G.compare(False, h.history())
        self.assertEqual(a["runtime_status"], b["runtime_status"])


class Fixtures(unittest.TestCase):

    def test_all_fixtures_pass(self):
        for name, fn in F.FIXTURES:
            with self.subTest(name):
                self.assertTrue(fn()[0], name)

    def test_main_returns_zero_and_is_deterministic(self):
        outs = []
        for _ in range(2):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(F.main(), 0)
            outs.append(buf.getvalue())
        self.assertEqual(outs[0], outs[1])
        self.assertIn("fixtures: 10/10 passed", outs[0])


class PaperEvidence(unittest.TestCase):

    def test_metadata(self):
        ev = evidence()
        p = ev["paper"]
        self.assertEqual(p["arxiv_id"], "2611.09088")
        self.assertEqual(p["licence_url"], "http://arxiv.org/licenses/nonexclusive-distrib/1.0/")
        self.assertEqual(p["authors"], ["Boming Xia", "Qinghua Lu", "Dino Sejdinovic", "Liming Zhu"])
        self.assertTrue(p["citation_title"].startswith("When Routine Operations Break"))
        self.assertIsNone(ev["implementation_pin"])
        self.assertEqual(ev["empirical_claims"]["status"], "UNVERIFIED")
        for c in ev["empirical_claims"]["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")

    def test_required_quotes_present(self):
        quotes = [e["excerpt"] for e in evidence()["excerpts"]]
        self.assertTrue(3 <= len(quotes) <= 6)
        for needle in ("runtime order or retained state",
                       "a prohibited edit executed without policy evaluation",
                       "property of the running system and its history",
                       "run in registration order"):
            self.assertTrue(any(needle in q for q in quotes), needle)

    def test_offsets_consistent(self):
        keys = {"id", "section", "excerpt", "chars", "normalized_offset",
                "end_offset_exclusive", "occurrences", "source_window_sha256", "status"}
        for e in evidence()["excerpts"]:
            self.assertEqual(set(e), keys)
            self.assertEqual(e["status"], "FOUND")
            self.assertEqual(e["end_offset_exclusive"] - e["normalized_offset"], len(e["excerpt"]))
            self.assertEqual(e["chars"], len(e["excerpt"]))

    def test_unverified_figures_only_in_evidence(self):
        texts = " ".join(c["text"] for c in evidence()["empirical_claims"]["claims"])
        self.assertIn("four" + "teen", texts)
        self.assertIn("five re" + "leased", texts)

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

    def test_deliverables_only(self):
        expected = ["NOTICE", "README.md", "fixtures.py", "guardrail_order.py",
                    "paper_evidence.json", "test_guardrail_order.py"]
        extra = set(deliverables()) - set(expected) - {"day" + "-README.md"}
        self.assertEqual(extra, set())

    def test_no_allow_vocabulary_except_op_name(self):
        for name in IMPL + PROSE:
            src = read(name).replace(OP_TOKEN, "").lower()
            for needle in ("al" + "low", "appro" + "v", "per" + "mit"):
                self.assertNotIn(needle, src, "%s: %s" % (name, needle))

    def test_public_verbs(self):
        for verb in ("hold", "report", "detect", "compare", "flag", "check_order"):
            self.assertTrue(callable(getattr(G, verb)), verb)
        funcs = [n for n, v in vars(G).items()
                 if inspect.isfunction(v) and not n.startswith("_")
                 and v.__module__ == "guardrail_order"]
        self.assertEqual(sorted(funcs), ["check_order", "compare", "detect", "flag", "hold", "report"])
        for n in dir(G):
            low = n.lower()
            for bad in ("al" + "low", "appro" + "v", "per" + "mit", "clear"):
                self.assertNotIn(bad, low, n)

    def test_absence_needles(self):
        needles = ("Two" + "-Ledger", "2611." + "06989", "HM" + "AC", "2611." + "07483",
                   "inspect" + "_ai", "open" + "ai", "anth" + "ropic")
        for name in deliverables():
            src = read(name)
            for n in needles:
                self.assertNotIn(n, src, "%s: %s" % (name, n))

    def test_no_paper_figures_outside_evidence(self):
        needles = ("four" + "teen", "five re" + "leased", "five re" + "lationships",
                   "five har" + "nesses", "ele" + "ven for")
        for name in IMPL + PROSE:
            src = read(name).lower()
            for n in needles:
                self.assertNotIn(n, src, "%s: %s" % (name, n))

    def test_no_conflict_markers(self):
        markers = ("<" * 7, ">" * 7)
        sep = "=" * 7
        for name in deliverables():
            src = read(name)
            for m in markers:
                self.assertNotIn(m, src, "%s: %s" % (name, m))
            for line in src.splitlines():
                self.assertNotEqual(line.strip(), sep, name)

    def test_prose_words(self):
        for name in PROSE:
            src = read(name)
            low = src.lower()
            self.assertNotIn("kee" + "p", low, name)
            for word in ("CloudAgent", "Smith", "Checker", "Ork"):
                self.assertIsNone(re.search(r"\b%s\b" % word, src, re.IGNORECASE),
                                  "%s: %s" % (name, word))
            self.assertNotIn("pull " + "request", low, name)
            self.assertIsNone(re.search(r"\bmer" + r"ge\b", src, re.IGNORECASE), name)

    def test_op_name_only_in_code_spans_in_prose(self):
        for name in PROSE:
            src = read(name)
            for m in re.finditer(re.escape(OP_TOKEN), src):
                line_start = src.rfind("\n", 0, m.start()) + 1
                inside = src.count("`", line_start, m.start()) % 2 == 1
                self.assertTrue(inside, "%s: op name outside a code span at %d" % (name, m.start()))

    def test_readme_standing_notes(self):
        src = read("README.md")
        for needle in ("method sketch", "not a reproduction", "not village law",
                       "not Team OS law", "UNVERIFIED",
                       "python3 -m unittest test_guardrail_order.py -v",
                       "python3 fixtures.py", "Builder reflection", "Ludex:",
                       "2611.09088", "nonexclusive-distrib/1.0"):
            self.assertIn(needle, src, needle)

    def test_notice(self):
        src = read("NOTICE")
        for needle in ("2611.09088", "Boming Xia", "Qinghua Lu", "Dino Sejdinovic",
                       "Liming Zhu", "nonexclusive-distrib/1.0", "no upstream code pin",
                       "stdlib", "Synthetic"):
            self.assertIn(needle, src, needle)

    def test_no_test_reads_parent_index(self):
        self.assertNotIn("day" + "-README", read("test_guardrail_order.py"))

    def test_imports_stdlib_only(self):
        ok = {"dataclasses", "typing", "guardrail_order"}
        for name in IMPL:
            for node in ast.walk(ast.parse(read(name))):
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [node.module]
                else:
                    continue
                for m in mods:
                    root = m.split(".")[0]
                    self.assertIn(root, ok, "%s imports %s" % (name, m))
                    if root != "guardrail_order" and hasattr(sys, "stdlib_module_names"):
                        self.assertIn(root, sys.stdlib_module_names)

    def test_no_network_or_process_modules(self):
        for name in IMPL:
            src = read(name)
            for n in ("soc" + "ket", "url" + "lib", "http" + ".client", "subpro" + "cess",
                      "sql" + "ite3", "thread" + "ing"):
                self.assertNotIn(n, src, "%s: %s" % (name, n))


if __name__ == "__main__":
    unittest.main()
