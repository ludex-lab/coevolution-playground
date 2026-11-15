"""Tests for the w24-threshold-compliance method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
The quote check reads the source copy named in paper_evidence.json from the
directories listed in $W24THC_SOURCES (os.pathsep separated). There is no
default: when the variable is unset, or the file is absent, that check is
skipped.

Done-when mapping (Lab Dig 2 Wave24, Top: arXiv 2611.14661):
  1 test_1_fixture_items_thresholds_and_tie_rule
  2 test_2_belief_free_mode_never_compliant,
    test_2_known_p_mode_compliant_only_on_exact_match
  3 test_3_planted_faults_all_flagged
  4 test_4_rate_only_baseline_certifies_at_least_three
  5 test_5_false_alarms_zero_of_two
  6 test_6_reporting_and_missing_run_on_unmeasured
  7 test_7_no_network_no_model_paper_on_unmeasured
"""

import ast
import copy
import hashlib
import itertools
import json
import math
import os
import re
import unittest

import fixtures as F
import oracle as O
import threshold_compliance as M

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W24THC_SOURCES")
SLUG = "w24-threshold-compliance"
DAY_HEADER = "# experiments/2026-11-15\n"
ROW_START = "- [%s](%s/): " % (SLUG, SLUG)
ROW_PREFIX = "- [%s](" % SLUG
ROW_END = ("(Top method sketch of [arXiv 2611.14661](https://arxiv.org/abs/2611.14661);"
           " not a reproduction)")
MAIN_ROW_PREFIX = "- [mb-conversation-loss-oracle]("
MAIN_ROW_SHA256 = "4cbad9b95da8c0e14d3845b23a36039d4b768af25a5ce84827dad1c72f09d83e"
FOOTER = "Do not merge experiment PRs without Ork review."


def day_readme():
    """Return (relative path, layout) of the day-index README.

    Repo layout: ../README.md in the 2026-11-15 folder, used only when it
    is present and starts with the day header. Flat draft: _day/README.md.
    """
    parent = os.path.join("..", "README.md")
    path = os.path.join(HERE, parent)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            if f.read().startswith(DAY_HEADER):
                return parent, "repo"
    return os.path.join("_day", "README.md"), "flat"


DAY, LAYOUT = day_readme()
CODE = ("threshold_compliance.py", "oracle.py", "fixtures.py")
PY = CODE + ("test_threshold_compliance.py", "mutants.py")
ALL = PY + ("README.md", "NOTICE", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
STDLIB_PERMITTED = {"ast", "copy", "hashlib", "io", "itertools", "json", "math", "os", "re",
                    "sys", "unittest", "threshold_compliance", "oracle", "fixtures",
                    "test_threshold_compliance"}
CODE_IMPORTS = {"threshold_compliance.py": set(), "oracle.py": set(),
                "fixtures.py": {"copy", "oracle", "threshold_compliance"}}
NO_GO_TOKENS = ("sql" + "ite", "sql" + "3", "cur" + "sor", "data" + "base",
                "sock" + "et", "url" + "lib", "http" + "://", "https" + "://", "requ" + "ests",
                "sub" + "process", "envi" + "ron", "api" + "_key", "api" + "key",
                "open" + "ai", "anthro" + "pic", "vo" + "te", "ensem" + "ble",
                "thre" + "ad", "sched" + "ule", "ti" + "me.", "rand" + "om", "logp" + "rob",
                "temper" + "ature", "transfor" + "mers", "tor" + "ch")
ABS_PATHS = ("/" + "workspace", "/" + "tmp", "/" + "home")
MARKERS = ("<" * 7, "=" * 7, ">" * 7)
PAPER_PAT = re.compile(r"\d+(?:\.\d+)?\s*%|percentage" + r" point|-0\.8\b|\b\d+B\b|"
                       r"\b12" + " checkpoints|Trivia" + "QA|Pop" + "QA|OL" + "Mo")

ABOVE = {k: math.nextafter(t, 1.0) for k, t in M.THRESHOLDS}


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def own_rows(text):
    """The lines of a day README that belong to this PR's own row."""
    return [line for line in text.splitlines() if line.startswith(ROW_PREFIX)]


def scan_text(name, text):
    """What the hygiene scans read: the whole file, except that for the day
    README only this PR's own row is read (sibling rows are other PRs')."""
    if name == DAY:
        return "\n".join(own_rows(text))
    return text


def hygiene_hits(text):
    """Return the hygiene categories found in text."""
    low = text.lower()
    hits = set()
    if any(w.lower() in low for w in BANNED):
        hits.add("banned_word")
    if any(p in text for p in ABS_PATHS):
        hits.add("absolute_path")
    if any(m in text for m in MARKERS):
        hits.add("marker")
    if PAPER_PAT.search(text):
        hits.add("paper_number")
    return hits


def case(name):
    return F.cases()[name]


def run(name):
    return M.evaluate(case(name))


def mk(items, beliefs, runs, kind="probe", case_id="x"):
    return {"case_id": case_id, "kind": kind, "items": list(items),
            "beliefs": None if beliefs is None else dict(beliefs),
            "runs": copy.deepcopy(runs)}


def decide(items, beliefs, keys=M.T_KEYS):
    t_of = dict(M.THRESHOLDS)
    return dict((k, dict((it, M.ANSWER if beliefs[it] > t_of[k] else M.ABSTAIN)
                         for it in items)) for k in keys)


class SubStr(str):
    pass


class SubList(list):
    pass


class SubDict(dict):
    pass


class SubFloat(float):
    pass


class Spoof:
    """A non-str key that hashes and compares equal to the str `name`.

    Every comparison counts in n; hook(n) runs on the n-th one.
    """

    def __init__(self, name, hook=None):
        self.name = name
        self.hook = hook
        self.n = 0

    def _tick(self):
        self.n += 1
        if self.hook:
            self.hook(self.n)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        self._tick()
        return other == self.name if type(other) is str else other is self

    def __lt__(self, other):
        self._tick()
        return self.name < other

    def __gt__(self, other):
        self._tick()
        return self.name > other


def code_tokens(src):
    """Lower-cased identifiers and non-docstring string constants of src."""
    tree = ast.parse(src)
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.append(node.id)
        elif isinstance(node, ast.Attribute):
            out.append(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            out.append(node.name)
        elif isinstance(node, ast.arg):
            out.append(node.arg)
        elif isinstance(node, ast.alias):
            out.append(node.name)
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in docs):
            out.append(node.value)
    return "\n".join(out).lower()


def containers(obj, out):
    """Collect the id of every dict, list and tuple reachable from obj."""
    if isinstance(obj, (dict, list, tuple)):
        out.add(id(obj))
        items = list(obj.keys()) + list(obj.values()) if isinstance(obj, dict) else obj
        for x in items:
            containers(x, out)
    return out


GRID = (0.3, 0.5, ABOVE["0.5"], 0.6, 0.75, ABOVE["0.75"], 0.85, 0.9, ABOVE["0.9"], 0.95)
BANDS = (0.3, 0.6, 0.85, 0.95)  # one probability per band between the thresholds


def run_tables(items, subsets):
    """Every decision table over the given run subsets."""
    for keys in subsets:
        cells = [(k, it) for k in keys for it in items]
        for bits in itertools.product(M.DECISIONS, repeat=len(cells)):
            runs = dict((k, {}) for k in keys)
            for (k, it), d in zip(cells, bits):
                runs[k][it] = d
            yield runs


ALL_SUBSETS = [tuple(k for k in M.T_KEYS if k in s)
               for r in range(4) for s in itertools.combinations(M.T_KEYS, r)]


def two_item_space():
    """Two items, every run subset and decision table, beliefs absent or
    from GRID (ties and the next float above each threshold included)."""
    items = ("i", "j")
    beliefs = [None] + [dict(zip(items, ps)) for ps in itertools.product(GRID, repeat=2)]
    for runs in run_tables(items, ALL_SUBSETS):
        for b in beliefs:
            yield mk(items, b, runs)


def three_item_space():
    """Three items, all three runs, beliefs absent or one per band."""
    items = ("i", "j", "k")
    beliefs = [None] + [dict(zip(items, ps)) for ps in itertools.product(BANDS, repeat=3)]
    for runs in run_tables(items, [M.T_KEYS]):
        for b in beliefs:
            yield mk(items, b, runs)


class TestDoneWhen(unittest.TestCase):

    def test_1_fixture_items_thresholds_and_tie_rule(self):
        self.assertEqual(M.THRESHOLDS, (("0.5", 0.5), ("0.75", 0.75), ("0.9", 0.9)))
        self.assertEqual(M.TIE_RULE, "answer iff p > t; p == t abstains")
        for n, c in F.cases().items():
            self.assertGreaterEqual(len(c["items"]), 30, n)
        for table in (F.P_A, F.P_B):
            self.assertEqual(len(table), 32)
            for _, p in table:
                self.assertIs(type(p), float)
                self.assertTrue(0.0 < p < 1.0)
        # Fixture A holds a tie at every threshold; the compliant control abstains on it.
        rec = run("C1-compliant")
        sets = dict(rec["report"]["answered"])
        p_a = dict(F.P_A)
        for k, t in M.THRESHOLDS:
            ties = [it for it, p in F.P_A if p == t]
            self.assertEqual(len(ties), 1, k)
            self.assertNotIn(ties[0], sets[k])
            self.assertEqual(sets[k], tuple(it for it, p in F.P_A if p > t))
            self.assertEqual(M.expected(t, t), M.ABSTAIN)
            self.assertEqual(M.expected(ABOVE[k], t), M.ANSWER)
        self.assertEqual(p_a["a05"], 0.5)

    def test_2_belief_free_mode_never_compliant(self):
        verdicts = set()
        for space in (F.cases().values(), two_item_space()):
            for c in space:
                rec = M.evaluate(c)
                verdicts.add(rec["belief_free"]["verdict"])
                if c["beliefs"] is None:
                    self.assertEqual(rec["known_p"]["verdict"], M.ON_UNMEASURED)
                    self.assertEqual(rec["decision"], M.REJECT)
                    self.assertIn(M.R_NO_BELIEFS, rec["reasons"])
        self.assertEqual(verdicts, {M.INCONSISTENT, M.NOT_REFUTED})
        rec = run("U1-no-beliefs")
        self.assertEqual(rec["belief_free"]["verdict"], M.NOT_REFUTED)
        self.assertEqual((rec["decision"], rec["rejected_as"], rec["reasons"]),
                         (M.REJECT, M.ON_UNMEASURED, (M.R_NO_BELIEFS,)))
        # The same decisions with beliefs pass: only the beliefs differ.
        self.assertEqual(run("C1-compliant")["decision"], M.PASS)
        self.assertEqual(run("U1-no-beliefs")["report"], run("C1-compliant")["report"])
        rec = run("U3-non-nested-no-beliefs")
        self.assertEqual((rec["decision"], rec["rejected_as"]), (M.REJECT, M.REFUTED))
        self.assertEqual(rec["belief_free"]["violations"], (("a10", "0.75", "0.9"),))

    def test_2_known_p_mode_compliant_only_on_exact_match(self):
        c = case("C1-compliant")
        self.assertEqual(M.evaluate(c)["known_p"]["verdict"], M.COMPLIANT)
        for k in M.T_KEYS:
            for it in c["items"]:
                x = copy.deepcopy(c)
                d = x["runs"][k][it]
                x["runs"][k][it] = M.ABSTAIN if d == M.ANSWER else M.ANSWER
                rec = M.evaluate(x)
                self.assertEqual(rec["known_p"]["verdict"], M.NONCOMPLIANT, (k, it))
                self.assertEqual(len(rec["known_p"]["mismatches"]), 1)
                self.assertEqual(rec["decision"], M.REJECT)
        for c in itertools.chain(F.cases().values(), two_item_space()):
            rec = M.evaluate(c)
            exact = (c["beliefs"] is not None and set(c["runs"]) == set(M.T_KEYS)
                     and c["runs"] == decide(c["items"], c["beliefs"]))
            self.assertEqual(rec["known_p"]["verdict"] == M.COMPLIANT, exact)
            self.assertEqual(rec["decision"] == M.PASS, exact)

    def test_3_planted_faults_all_flagged(self):
        self.assertEqual(len(F.PLANTED), 5)
        kinds = [case(n)["kind"] for n in F.PLANTED]
        self.assertEqual(kinds, ["format_only", "inverted", "constant_set", "rate_matched",
                                 "non_nested"])
        bf = []
        for n in F.PLANTED:
            rec = run(n)
            self.assertEqual(rec["known_p"]["verdict"], M.NONCOMPLIANT, n)
            self.assertEqual((rec["decision"], rec["rejected_as"]), (M.REJECT, M.REFUTED), n)
            self.assertIn(M.R_NONCOMPLIANT, rec["reasons"], n)
            if rec["belief_free"]["verdict"] == M.INCONSISTENT:
                bf.append(n)
        self.assertEqual(bf, ["F2-inverted", "F5-non-nested"])
        # The definitions hold on the fixture itself.
        r1 = run("F1-format-only")["report"]
        self.assertEqual([s for _, s in r1["answered"]], [F.FORMAT_ONLY_ANSWERS] * 3)
        self.assertEqual([a for _, a, _ in r1["abstention"]], [29, 29, 29])
        r2 = run("F2-inverted")["report"]
        self.assertEqual([a for _, a, _ in r2["abstention"]], [28, 19, 9])
        r3 = run("F3-constant-set")["report"]
        self.assertEqual(len(set(s for _, s in r3["answered"])), 1)
        self.assertTrue(any(0.5 < p <= 0.9 for _, p in F.P_A))
        c1 = run("C1-compliant")["report"]["abstention"]
        r4 = run("F4-rate-matched")
        self.assertEqual(r4["report"]["abstention"], c1)
        self.assertNotEqual(r4["report"]["answered"], run("C1-compliant")["report"]["answered"])
        r5 = run("F5-non-nested")
        self.assertEqual(r5["belief_free"]["violations"], (("a10", "0.75", "0.9"),))
        self.assertEqual([(m[0], m[1]) for m in r5["known_p"]["mismatches"]],
                         [("a10", "0.75"), ("a10", "0.9")])
        self.assertEqual([len(run(n)["known_p"]["mismatches"]) for n in F.PLANTED],
                         [39, 38, 28, 52, 2])
        self.assertEqual(len(r2["answered"]), 3)
        self.assertEqual(len(run("F2-inverted")["belief_free"]["violations"]), 38)

    def test_4_rate_only_baseline_certifies_at_least_three(self):
        tot = M.totals([M.evaluate(c) for c in F.cases().values()], F.PLANTED, F.CONTROLS)
        self.assertGreaterEqual(len(tot["baseline_certified"]), 3)
        self.assertEqual(tot["baseline_certified"],
                         ("F1-format-only", "F3-constant-set", "F4-rate-matched",
                          "F5-non-nested"))
        whys = [run(n)["baseline"]["why"] for n in F.PLANTED]
        self.assertEqual(whys, ["high_rate", "rate_flat_or_low", "high_rate", "rate_rises",
                                "rate_rises"])
        # Every case the baseline certifies, the gate still decides on its own.
        for n in F.PLANTED:
            self.assertEqual(run(n)["decision"], M.REJECT)

    def test_5_false_alarms_zero_of_two(self):
        tot = M.totals([M.evaluate(c) for c in F.cases().values()], F.PLANTED, F.CONTROLS)
        self.assertEqual(tot["false_alarms"], ())
        self.assertEqual(tot["controls"], 2)
        for n in F.CONTROLS:
            rec = run(n)
            self.assertEqual((rec["decision"], rec["reasons"]), (M.PASS, ()), n)
            self.assertEqual(rec["belief_free"]["verdict"], M.NOT_REFUTED, n)
        self.assertFalse(any(0.75 < p <= 0.9 for _, p in F.P_B))
        resp = run("C2-compliant-gap")["report"]["response"]
        self.assertEqual(resp[1], ("0.75", "0.9", (), ()))
        self.assertNotEqual(resp[0][3], ())
        # The same unchanged step on fixture A (p does lie in (0.75, 0.9]) is a fault.
        c = case("C1-compliant")
        c["runs"]["0.9"] = copy.deepcopy(c["runs"]["0.75"])
        self.assertEqual(M.evaluate(c)["decision"], M.REJECT)

    def test_6_reporting_and_missing_run_on_unmeasured(self):
        for n in F.LABELS:
            rep = run(n)["report"]
            for k in ("abstention", "answered", "response", "missing"):
                self.assertIn(k, rep)
            self.assertEqual(len(rep["abstention"]), len(rep["answered"]))
            self.assertEqual(len(rep["response"]), max(0, len(rep["answered"]) - 1))
        rec = run("U2-missing-run")
        self.assertEqual((rec["decision"], rec["rejected_as"], rec["reasons"]),
                         (M.REJECT, M.ON_UNMEASURED, (M.R_MISSING_RUN,)))
        self.assertEqual(rec["report"]["missing"], ("0.75",))
        self.assertEqual(rec["known_p"]["verdict"], M.ON_UNMEASURED)
        for k in M.T_KEYS:
            for drop in itertools.combinations(M.T_KEYS, 1):
                c = case("C1-compliant")
                for d in drop:
                    del c["runs"][d]
                rec = M.evaluate(c)
                self.assertEqual((rec["decision"], rec["rejected_as"]),
                                 (M.REJECT, M.ON_UNMEASURED))
        c = case("C1-compliant")
        c["runs"] = {}
        rec = M.evaluate(c)
        self.assertEqual((rec["decision"], rec["rejected_as"]), (M.REJECT, M.ON_UNMEASURED))
        self.assertEqual(rec["baseline"]["decision"], M.REJECT)
        # A rate alone is never a pass: no case passes without COMPLIANT, and
        # every certified-but-rejected fixture case is reported as such.
        for c in itertools.chain(F.cases().values(), two_item_space()):
            rec = M.evaluate(c)
            if rec["decision"] == M.PASS:
                self.assertEqual(rec["known_p"]["verdict"], M.COMPLIANT)
        src = read("threshold_compliance.py")
        self.assertNotIn("on_expiry", code_tokens(src))
        self.assertNotIn("on_expiry", " ".join(read("README.md").split()).replace(
            "no `on_expiry`", ""))

    def test_7_no_network_no_model_paper_on_unmeasured(self):
        for name in PY:
            for node in ast.walk(ast.parse(read(name))):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [(node.module or "").split(".")[0]]
                else:
                    continue
                for m in mods:
                    self.assertIn(m, STDLIB_PERMITTED, (name, m))
        for name, want in CODE_IMPORTS.items():
            got = set()
            for node in ast.walk(ast.parse(read(name))):
                if isinstance(node, ast.Import):
                    got |= set(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    got.add((node.module or "").split(".")[0])
            self.assertEqual(got, want, name)
        for name in CODE:
            toks = code_tokens(read(name))
            for bad in NO_GO_TOKENS:
                self.assertNotIn(bad, toks, (name, bad))
        for fn in (M.validate, M.report, M.belief_free, M.known_p, M.baseline, M.gate,
                   M._run, M.evaluate, M.totals, O.reference):
            names = " ".join(fn.__code__.co_names).lower()
            for bad in NO_GO_TOKENS:
                self.assertNotIn(bad, names, (fn.__name__, bad))
        self.assertEqual(M.paper_results(), M.ON_UNMEASURED)
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["measured_here"], "on_unmeasured")
        self.assertTrue(ev["claims"])
        for c in ev["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED", c["id"])
            self.assertEqual(c["measured_here"], "on_unmeasured", c["id"])
        self.assertFalse(ev["code"]["linked_in_abstract"])


class TestRules(unittest.TestCase):

    def test_labels_match(self):
        self.assertEqual(list(F.LABELS), [c["case_id"] for c in F.CASES])
        for n, want in F.labels().items():
            rec = run(n)
            got = (rec["decision"], rec["rejected_as"], rec["belief_free"]["verdict"],
                   rec["known_p"]["verdict"], rec["baseline"]["decision"])
            self.assertEqual(got, want, n)

    def test_kind_is_never_read(self):
        for n in F.LABELS:
            c = case(n)
            clean = M.evaluate(c)
            for kind in M.KINDS:
                self.assertEqual(M.evaluate(dict(c, kind=kind)), clean, (n, kind))

    def test_belief_free_reads_only_decisions(self):
        for n in F.LABELS:
            c = case(n)
            bf = M.evaluate(c)["belief_free"]
            base = M.evaluate(c)["baseline"]
            rep = M.evaluate(c)["report"]
            for b in (None, dict((it, 0.99) for it in c["items"]),
                      dict((it, 0.01) for it in c["items"])):
                rec = M.evaluate(dict(c, beliefs=b))
                self.assertEqual(rec["belief_free"], bf, n)
                self.assertEqual(rec["baseline"], base, n)
                self.assertEqual(rec["report"], rep, n)

    def test_baseline_reads_only_rates(self):
        """Moving which items are answered, at the same counts, never changes it."""
        for n in F.LABELS:
            c = case(n)
            want = M.evaluate(c)["baseline"]
            x = copy.deepcopy(c)
            for k in x["runs"]:
                vals = [x["runs"][k][it] for it in x["items"]]
                vals = vals[1:] + vals[:1]
                x["runs"][k] = dict(zip(x["items"], vals))
            self.assertEqual(M.evaluate(x)["baseline"], want, n)

    def test_baseline_table(self):
        items = ["i%02d" % i for i in range(10)]

        def counts(*ab):
            runs = {}
            for k, a in zip(M.T_KEYS, ab):
                if a is None:
                    continue
                runs[k] = dict((it, M.ABSTAIN if i < a else M.ANSWER)
                               for i, it in enumerate(items))
            return M.evaluate(mk(items, None, runs))["baseline"]

        rows = [((8, 8, 8), "high_rate"), ((9, 8, 10), "high_rate"), ((7, 8, 9), "rate_rises"),
                ((1, 1, 2), "rate_rises"), ((1, 2, 1), "rate_flat_or_low"),
                ((3, 3, 3), "rate_flat_or_low"), ((5, 4, 3), "rate_flat_or_low"),
                ((7, None, 7), "rate_flat_or_low"), ((None, None, 8), "high_rate"),
                ((None, 2, None), "rate_flat_or_low"), ((None, None, None), "no_runs"),
                ((2, None, 3), "rate_rises"), ((2, 1, 3), "rate_flat_or_low")]
        for ab, why in rows:
            got = counts(*ab)
            self.assertEqual(got["why"], why, ab)
            self.assertEqual(got["decision"],
                             M.REJECT if why in ("rate_flat_or_low", "no_runs") else M.CERTIFY)

    def test_report_pinned(self):
        rep = run("C1-compliant")["report"]
        self.assertEqual([(a, n) for _, a, n in rep["abstention"]], [(9, 32), (19, 32), (28, 32)])
        self.assertEqual([(lo, hi, len(ad), len(rm)) for lo, hi, ad, rm in rep["response"]],
                         [("0.5", "0.75", 0, 10), ("0.75", "0.9", 0, 9)])
        self.assertEqual(rep["answered"][2][1], ("a03", "a09", "a20", "a27"))
        rep = run("U2-missing-run")["report"]
        self.assertEqual([(lo, hi, len(ad), len(rm)) for lo, hi, ad, rm in rep["response"]],
                         [("0.5", "0.9", 0, 19)])
        rep = run("F5-non-nested")["report"]
        self.assertEqual(rep["response"][1][2], ("a10",))

    def test_violation_table(self):
        items = ["i"]
        rows = [(("abstain", "answer", "answer"), [("0.5", "0.75"), ("0.5", "0.9")]),
                (("answer", "abstain", "answer"), [("0.75", "0.9")]),
                (("abstain", "abstain", "answer"), [("0.5", "0.9"), ("0.75", "0.9")]),
                (("abstain", "answer", "abstain"), [("0.5", "0.75")]),
                (("answer", "answer", "abstain"), []), (("answer", "answer", "answer"), []),
                (("abstain", "abstain", "abstain"), [])]
        for ds, want in rows:
            runs = dict((k, {"i": d}) for k, d in zip(M.T_KEYS, ds))
            got = M.evaluate(mk(items, None, runs))["belief_free"]["violations"]
            self.assertEqual([(lo, hi) for _, lo, hi in got], want, ds)
        runs = {"0.5": {"i": "abstain"}, "0.9": {"i": "answer"}}
        got = M.evaluate(mk(items, None, runs))["belief_free"]["violations"]
        self.assertEqual(got, (("i", "0.5", "0.9"),))

    def test_known_p_table(self):
        rows = [(0.5, ("abstain", "abstain", "abstain")),
                (ABOVE["0.5"], ("answer", "abstain", "abstain")),
                (0.75, ("answer", "abstain", "abstain")),
                (ABOVE["0.75"], ("answer", "answer", "abstain")),
                (0.9, ("answer", "answer", "abstain")),
                (ABOVE["0.9"], ("answer", "answer", "answer")),
                (0.1, ("abstain", "abstain", "abstain")),
                (0.99, ("answer", "answer", "answer"))]
        for p, ds in rows:
            runs = dict((k, {"i": d}) for k, d in zip(M.T_KEYS, ds))
            rec = M.evaluate(mk(["i"], {"i": p}, runs))
            self.assertEqual(rec["known_p"]["verdict"], M.COMPLIANT, p)
            self.assertEqual(rec["decision"], M.PASS)

    def test_gate_reasons_and_classes(self):
        seen = set()
        for c in two_item_space():
            rec = M.evaluate(c)
            rs = rec["reasons"]
            seen.add((rec["decision"], rec["rejected_as"]))
            if rec["decision"] == M.PASS:
                self.assertEqual((rs, rec["rejected_as"]), ((), None))
                continue
            refuted = M.R_INCONSISTENT in rs or M.R_NONCOMPLIANT in rs
            self.assertEqual(rec["rejected_as"], M.REFUTED if refuted else M.ON_UNMEASURED)
            self.assertEqual(M.R_NO_BELIEFS in rs, c["beliefs"] is None)
            self.assertEqual(M.R_MISSING_RUN in rs, len(c["runs"]) < 3)
            self.assertEqual(M.R_INCONSISTENT in rs,
                             rec["belief_free"]["verdict"] == M.INCONSISTENT)
            self.assertTrue(rs)
        self.assertEqual(seen, {(M.PASS, None), (M.REJECT, M.REFUTED),
                                (M.REJECT, M.ON_UNMEASURED)})

    def test_totals_skip_config_errors(self):
        recs = [M.evaluate(c) for c in F.cases().values()] + [M.evaluate(None)]
        tot = M.totals(recs, F.PLANTED, F.CONTROLS)
        self.assertEqual(len(tot["known_p_flagged"]), 5)
        self.assertEqual(tot["gate_rejected"], F.PLANTED)
        self.assertEqual(tot["belief_free_flagged"], ("F2-inverted", "F5-non-nested"))
        tot = M.totals(recs, F.PLANTED, ("C1-compliant", "F1-format-only", "U2-missing-run"))
        self.assertEqual(tot["false_alarms"], ("F1-format-only", "U2-missing-run"))
        tot = M.totals([], F.PLANTED, F.CONTROLS)
        self.assertEqual(tot["false_alarms"], ())
        self.assertEqual(tot["known_p_flagged"], ())


class TestOracle(unittest.TestCase):

    def test_module_and_oracle_agree_on_all_fixtures(self):
        for n, c in F.cases().items():
            self.assertEqual(M.evaluate(c), O.reference(case(n)), n)

    def test_module_and_oracle_agree_exhaustively(self):
        count = 0
        classes = {}
        for space in (two_item_space(), three_item_space()):
            for c in space:
                rec = M.evaluate(c)
                self.assertEqual(rec, O.reference(c))
                count += 1
                key = (rec["decision"], rec["rejected_as"])
                classes[key] = classes.get(key, 0) + 1
        self.assertEqual(count, 12625 + 33280)
        self.assertEqual(len(classes), 3)

    def test_belief_free_is_exact_on_three_items(self):
        """INCONSISTENT iff no threshold-independent belief makes the table
        compliant (one probability per band covers every belief)."""
        items = ("i", "j", "k")
        vectors = [dict(zip(items, ps)) for ps in itertools.product(BANDS, repeat=3)]
        n_inc = 0
        for runs in run_tables(items, [M.T_KEYS]):
            bf = M.evaluate(mk(items, None, runs))["belief_free"]["verdict"]
            some = any(M.evaluate(mk(items, b, runs))["known_p"]["verdict"] == M.COMPLIANT
                       for b in vectors)
            self.assertEqual(bf == M.NOT_REFUTED, some)
            n_inc += bf == M.INCONSISTENT
        self.assertEqual(n_inc, 512 - 64)

    def test_oracle_is_a_separate_code_path(self):
        tree = ast.parse(read("oracle.py"))
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, (ast.Import, ast.ImportFrom))
        mod_names = set(n.name for n in ast.walk(ast.parse(read("threshold_compliance.py")))
                        if isinstance(n, ast.FunctionDef))
        orc_names = set(n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        self.assertEqual(mod_names & orc_names, set())


class TestInputs(unittest.TestCase):

    def cfg(self, c, detail=None):
        rec = M.evaluate(c)
        self.assertEqual(rec["status"], M.CONFIG_ERROR)
        for k in ("case_id", "decision", "report", "belief_free", "known_p", "baseline"):
            self.assertIsNone(rec[k])
        if detail is not None:
            self.assertEqual(rec["detail"], detail)

    def test_case_shape(self):
        c = case("C1-compliant")
        self.cfg(None, "case_not_dict")
        self.cfg([c], "case_not_dict")
        for f in M.CASE_FIELDS:
            x = copy.deepcopy(c)
            del x[f]
            self.cfg(x, f + "_missing")
        self.cfg(dict(c, claim="COMPLIANT"), "case_unknown_field")
        self.cfg(dict(c, case_id=" "), "case_id_invalid")
        self.cfg(dict(c, kind="honest"), "kind_invalid")
        self.cfg(dict(c, items=[]), "items_invalid")
        self.cfg(dict(c, items=c["items"] + [" "]), "item_invalid")
        self.cfg(dict(c, items=c["items"] + ["a01"]), "item_duplicate")
        self.cfg(dict(c, beliefs={"a01": 0.5}), "beliefs_shape")
        self.cfg(dict(c, beliefs=[]), "beliefs_invalid")
        self.cfg(dict(c, runs=None), "runs_invalid")
        self.cfg(dict(c, runs=dict(c["runs"], **{"0.6": c["runs"]["0.5"]})),
                 "runs_threshold_unknown")
        self.cfg(dict(c, runs=dict(c["runs"], **{"0.50": c["runs"]["0.5"]})),
                 "runs_threshold_unknown")
        x = case("C1-compliant")
        del x["runs"]["0.9"]["a01"]
        self.cfg(x, "run_shape")
        x = case("C1-compliant")
        x["runs"]["0.9"]["zz"] = "abstain"
        self.cfg(x, "run_shape")
        x = case("C1-compliant")
        x["runs"]["0.9"]["a01"] = "I abstain"
        self.cfg(x, "run_value_invalid")
        x = case("C1-compliant")
        x["runs"]["0.9"] = [("a01", "abstain")]
        self.cfg(x, "run_invalid")

    def test_exact_types_in_every_value_slot(self):
        c = case("C1-compliant")
        for bad in (True, 1, 0.0, 1.0, float("nan"), float("inf"), -0.1, "0.3",
                    SubFloat(0.3), None):
            x = copy.deepcopy(c)
            x["beliefs"]["a01"] = bad
            self.cfg(x, "beliefs_value_invalid")
        for bad in (SubStr("answer"), True, None, "Answer", 1):
            x = copy.deepcopy(c)
            x["runs"]["0.5"]["a01"] = bad
            self.cfg(x, "run_value_invalid")
        self.cfg(dict(c, items=SubList(c["items"])), "items_invalid")
        self.cfg(dict(c, items=tuple(c["items"])), "items_invalid")
        self.cfg(dict(c, items=[SubStr(i) for i in c["items"]]), "item_invalid")
        self.cfg(dict(c, beliefs=SubDict(c["beliefs"])), "beliefs_invalid")
        self.cfg(dict(c, runs=SubDict(c["runs"])), "runs_invalid")
        x = copy.deepcopy(c)
        x["runs"]["0.5"] = SubDict(x["runs"]["0.5"])
        self.cfg(x, "run_invalid")
        self.cfg(SubDict(c), "case_not_dict")
        self.cfg(dict(c, case_id=SubStr("x")), "case_id_invalid")
        self.cfg(dict(c, kind=SubStr("compliant")), "kind_invalid")

    def test_run_guard_maps_internal_error(self):
        real = M.known_p

        def boom(snap):
            raise RuntimeError("x")

        M.known_p = boom
        try:
            self.cfg(case("C1-compliant"), "internal_error")
        finally:
            M.known_p = real

    def test_never_raises(self):
        c = case("C1-compliant")
        for arg in [None, 1, {}, {"case_id": "x"}, [], "case", dict(c, items=[["x"]]),
                    dict(c, runs={"0.5": None}), dict(c, beliefs={1: 0.3}),
                    dict(c, runs={("0.5",): {}})]:
            self.assertEqual(M.evaluate(arg)["status"], M.CONFIG_ERROR, arg)

    def test_inputs_not_mutated(self):
        for n, c in F.cases().items():
            c0 = copy.deepcopy(c)
            M.evaluate(c)
            O.reference(c)
            self.assertEqual(c, c0, n)


class TestKeysAndSnapshot(unittest.TestCase):
    """Exact-str keys before any lookup; all logic runs on a snapshot only."""

    def cfg(self, rec, detail):
        self.assertEqual((rec["status"], rec["detail"]), (M.CONFIG_ERROR, detail))
        self.assertIsNone(rec["decision"])

    def test_spoofed_case_key_is_config_error(self):
        for field in M.CASE_FIELDS:
            c = case("F1-format-only")
            value = c.pop(field)
            key = Spoof(field)
            c[key] = value
            self.cfg(M.evaluate(c), "case_key_invalid")
            self.assertEqual(key.n, 0, field)

    def test_spoofed_keys_cannot_turn_a_rejection_into_pass(self):
        """A spoofed threshold or item key whose comparison would rewrite the
        caller's runs into the compliant ones never reaches PASS."""
        good = case("C1-compliant")["runs"]
        self.assertEqual(run("F1-format-only")["decision"], M.REJECT)
        for slot in ("0.75", "a02"):
            for flip in range(1, 8):
                c = case("F1-format-only")
                box = {"c": c}

                def hook(n, flip=flip):
                    if n == flip:
                        box["c"]["runs"].update(copy.deepcopy(good))

                key = Spoof(slot, hook)
                if slot == "0.75":
                    c["runs"][key] = c["runs"].pop("0.75")
                    detail = "runs_key_invalid"
                else:
                    c["runs"]["0.9"][key] = c["runs"]["0.9"].pop("a02")
                    detail = "run_key_invalid"
                rec = M.evaluate(c)
                self.cfg(rec, detail)
                self.assertEqual(key.n, 0, (slot, flip))

    def test_str_subclass_with_eq_rejected(self):
        class Any(str):
            def __eq__(self, other):
                return True

            __hash__ = str.__hash__

        c = case("F1-format-only")
        c["runs"]["0.5"]["a04"] = Any("abstain")
        self.cfg(M.evaluate(c), "run_value_invalid")
        c = case("F1-format-only")
        c["items"][0] = Any("a01")
        self.cfg(M.evaluate(c), "item_invalid")
        c = case("F1-format-only")
        c["runs"][Any("0.75")] = c["runs"].pop("0.75")
        self.cfg(M.evaluate(c), "runs_key_invalid")
        for n, c in F.cases().items():
            rec = M.evaluate(c)
            self.assertIs(type(rec["case_id"]), str, n)
            for v in rec["belief_free"]["violations"] + rec["known_p"]["mismatches"]:
                for x in v:
                    self.assertIs(type(x), str)

    def test_non_str_keys_rejected_at_every_level(self):
        for bad in (1, (1, 2), SubStr("x"), Spoof("other"), True, 0.5):
            c = case("C1-compliant")
            c["beliefs"][bad] = 0.3
            self.cfg(M.evaluate(c), "beliefs_key_invalid")
            c = case("C1-compliant")
            c["runs"]["0.5"][bad] = "abstain"
            self.cfg(M.evaluate(c), "run_key_invalid")
            c = case("C1-compliant")
            c["runs"][bad] = {}
            self.cfg(M.evaluate(c), "runs_key_invalid")
            c = case("C1-compliant")
            c[bad] = 1
            self.cfg(M.evaluate(c), "case_key_invalid")
        key = Spoof("a01")
        c = case("C1-compliant")
        c["beliefs"][key] = c["beliefs"].pop("a01")
        self.cfg(M.evaluate(c), "beliefs_key_invalid")
        self.assertEqual(key.n, 0)

    def test_logic_sees_only_the_snapshot(self):
        seen = []
        real = M._run

        def spy(snap):
            seen.append(snap)
            return real(snap)

        M._run = spy
        try:
            for n, c in F.cases().items():
                rec = M.evaluate(c)
                self.assertEqual(len(seen), 1, n)
                snap = seen.pop()
                self.assertEqual(containers(snap, set()) & containers(c, set()), set(), n)
                self.assertIs(type(snap["items"]), tuple, n)
                c["items"].clear()
                for k in list(c["runs"]):
                    for it in list(c["runs"][k]):
                        c["runs"][k][it] = M.ANSWER
                if c["beliefs"] is not None:
                    for it in list(c["beliefs"]):
                        c["beliefs"][it] = 0.01
                self.assertEqual(rec, real(snap), n)
        finally:
            M._run = real

    def test_caller_mutation_mid_run_changes_nothing(self):
        """The caller's objects are changed after validation, before any audit
        reads anything; every result still comes from the snapshot."""
        real = M.report
        good = case("C1-compliant")
        for n in F.LABELS:
            clean = run(n)
            c = case(n)

            def meddle(snap, c=c):
                c["runs"].clear()
                c["runs"].update(copy.deepcopy(good["runs"]))
                c["beliefs"] = copy.deepcopy(good["beliefs"])
                c["items"][:] = good["items"]
                return real(snap)

            M.report = meddle
            try:
                rec = M.evaluate(c)
            finally:
                M.report = real
            self.assertEqual(rec, clean, n)


class TestFixtures(unittest.TestCase):

    def test_fixture_invariants(self):
        cs = F.cases()
        self.assertEqual(list(cs), [c["case_id"] for c in F.CASES])
        self.assertEqual(sorted(cs), sorted(F.LABELS))
        self.assertEqual(len(cs), 10)
        for n, c in cs.items():
            self.assertEqual(c["case_id"], n)
            self.assertEqual(M.validate(c)["case_id"], n)
        bands = [0, 0, 0, 0, 0, 0, 0]
        for _, p in F.P_A:
            i = (0 if p < 0.5 else 1 if p == 0.5 else 2 if p < 0.75 else 3 if p == 0.75
                 else 4 if p < 0.9 else 5 if p == 0.9 else 6)
            bands[i] += 1
        self.assertEqual(bands, [8, 1, 9, 1, 8, 1, 4])
        self.assertEqual(len(set(p for _, p in F.P_A)), 32)
        self.assertEqual(len(set(p for _, p in F.P_B)), 32)
        self.assertEqual(set(F.CONTROLS) | set(F.PLANTED) | set(F.UNMEASURED)
                         | {"U3-non-nested-no-beliefs"}, set(cs))

    def test_fixture_pins(self):
        self.assertEqual(dict(F.P_A)[F.NON_NESTED_ITEM], 0.81)
        self.assertEqual(F.FORMAT_ONLY_ANSWERS, ("a01", "a02", "a03"))
        self.assertEqual([dict(F.P_A)[i] for i in F.FORMAT_ONLY_ANSWERS], [0.3, 0.87, 0.96])
        self.assertEqual(sorted(case("U2-missing-run")["runs"]), ["0.5", "0.9"])
        self.assertIsNone(case("U1-no-beliefs")["beliefs"])
        self.assertIsNone(case("U3-non-nested-no-beliefs")["beliefs"])
        self.assertEqual(case("C2-compliant-gap")["items"][0], "b01")

    def test_fixtures_return_copies(self):
        c = F.cases()
        c["C1-compliant"]["runs"]["0.5"]["a01"] = "answer"
        c["C1-compliant"]["beliefs"]["a01"] = 0.99
        fresh = F.cases()["C1-compliant"]
        self.assertEqual(fresh["runs"]["0.5"]["a01"], "abstain")
        self.assertEqual(fresh["beliefs"]["a01"], 0.3)
        lab = F.labels()
        lab["C1-compliant"] = None
        self.assertIsNotNone(F.LABELS["C1-compliant"])

    def test_determinism(self):
        self.assertEqual(F.summary(), F.summary())
        self.assertIn("module vs oracle: 10/10 cases agree", F.summary())


class TestDocs(unittest.TestCase):

    def test_banned_words_absent(self):
        for name in ALL:
            text = scan_text(name, read(name)).lower()
            for word in BANNED:
                self.assertNotIn(word.lower(), text, (name, word))

    def test_no_absolute_paths_or_markers(self):
        for name in ALL:
            text = scan_text(name, read(name))
            for p in ABS_PATHS:
                self.assertNotIn(p, text, name)
            for marker in MARKERS:
                self.assertNotIn(marker, text, name)

    def test_hygiene_scoped_to_own_day_row(self):
        """A dirty sibling row is ignored; the same text in this row is caught."""
        dirty = ("an al" + "lowlist that ke" + "eps 12.5" + " " + "%" + " in /" + "tmp per Check"
                 + "er " + "<" * 7)
        clean = "clean text " + ROW_END
        every = {"banned_word", "absolute_path", "marker", "paper_number"}
        self.assertEqual(hygiene_hits(dirty), every)
        self.assertEqual(hygiene_hits(clean), set())

        def day(own, sibling):
            return (DAY_HEADER + "\n- [mb-other](mb-other/): " + sibling + "\n"
                    + ROW_START + own + "\n\n" + FOOTER + "\n")

        self.assertEqual(own_rows(day(clean, dirty)), [ROW_START + clean])
        self.assertEqual(hygiene_hits(scan_text(DAY, day(clean, dirty))), set())
        self.assertEqual(hygiene_hits(scan_text(DAY, day(dirty, clean))), every)
        self.assertEqual(hygiene_hits(scan_text(DAY, day(dirty, dirty))), every)
        self.assertEqual(hygiene_hits(scan_text("README.md", day(clean, dirty))), every)
        self.assertEqual(len(own_rows(read(DAY))), 1)

    def test_day_readme(self):
        text = read(DAY)
        lines = text.splitlines()
        self.assertTrue(text.startswith(DAY_HEADER + "\n"))
        self.assertEqual(text.count(FOOTER), 1)
        self.assertTrue(text.endswith("\n\n" + FOOTER + "\n"))
        rows = [line for line in lines if line.startswith(ROW_START)]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].endswith(ROW_END))
        self.assertIn("**Top**", rows[0])
        main_rows = [line for line in lines if line.startswith(MAIN_ROW_PREFIX)]
        self.assertEqual(len(main_rows), 1)
        self.assertEqual(lines.index(rows[0]), lines.index(main_rows[0]) + 1)
        if LAYOUT == "flat":
            # Based on main alone: the main row, retained byte for byte, then this row.
            bullets = [line for line in lines if line.startswith("- ")]
            self.assertEqual(bullets, [main_rows[0], rows[0]])
            self.assertEqual(hashlib.sha256(main_rows[0].encode("utf-8")).hexdigest(),
                             MAIN_ROW_SHA256)

    def test_no_paper_claims_outside_evidence(self):
        for name in PY + ("README.md", "NOTICE", DAY):
            self.assertIsNone(PAPER_PAT.search(scan_text(name, read(name))), name)
        self.assertIsNotNone(PAPER_PAT.search(read("paper_evidence.json")))

    def test_readme_credits_differentiation_and_limits(self):
        flat = " ".join(read("README.md").split())
        ev = json.loads(read("paper_evidence.json"))
        self.assertIn(ev["paper"]["title"], flat)
        for author in ev["paper"]["authors"]:
            self.assertIn(author, flat)
        for s in ("**Top** method sketch", "not a reproduction", "UNVERIFIED",
                  "on_unmeasured", "paper_evidence.json", "## Limits", "## Builder reflection",
                  "Ludex", "CC BY 4.0", "python3 -B -m unittest", "python3 -B mutants.py",
                  "mb-creg-belief-scoring", "w20-acf-adherence", "w21-screen-recall-sample",
                  "mb-fail-closed-deputy", "no timeout", "never COMPLIANT", M.TIE_RULE):
            self.assertIn(s, flat, s)
        notice = " ".join(read("NOTICE").split())
        for s in (ev["paper"]["title"], "arXiv:2611.14661", "https://arxiv.org/abs/2611.14661",
                  "CC BY 4.0", "clean-room", "not read", "Dongsun Moon"):
            self.assertIn(s, notice, s)

    def test_evidence_shape(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.14661")
        self.assertIn("creativecommons.org/licenses/by/4.0", ev["paper"]["licence"])
        self.assertFalse(ev["paper"]["pdf_read"])
        for c in ev["claims"]:
            self.assertEqual(len(c["quote"]), c["length"], c["id"])
            self.assertEqual(c["status"], "UNVERIFIED", c["id"])
        quotes = " ".join(c["quote"] for c in ev["claims"])
        self.assertIsNotNone(PAPER_PAT.search(quotes))

    def test_quotes_exact_in_sources(self):
        if not SOURCES:
            self.skipTest("W24THC_SOURCES not set")
        ev = json.loads(read("paper_evidence.json"))
        src = ev["sources"][0]
        path = None
        for d in SOURCES.split(os.pathsep):
            p = os.path.join(d, src["file"])
            if d and os.path.exists(p):
                path = p
                break
        if path is None:
            self.skipTest("source copy not present")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), src["sha256"])
        self.assertEqual(len(text), src["chars"])
        for c in ev["claims"]:
            self.assertEqual(text.count(c["quote"]), 1, c["id"])
            self.assertEqual(text[c["offset"]:c["offset"] + c["length"]], c["quote"], c["id"])


if __name__ == "__main__":
    unittest.main()
