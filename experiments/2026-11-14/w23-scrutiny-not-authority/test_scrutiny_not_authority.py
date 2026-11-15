"""Tests for the w23-scrutiny-not-authority method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
The quote check reads the source copy named in paper_evidence.json from the
directories listed in $W23SCRUTINY_SOURCES (os.pathsep separated). There is
no default: when the variable is unset, or the file is absent, that check
is skipped.

Done-when mapping (Lab Dig 2 Wave23, Top 3):
  (a) test_a_defective_assessment_flags_and_retains
  (b) test_b_auto_elimination_on_a_defective_assessment_refused
  (c) test_c_scrutiny_check_drops_unsound_and_retains_sound
  (d) test_d_forced_agreement_fails_where_the_rating_is_noisy
  (e) test_e_no_llm
  paper statements: test_f_paper_on_unmeasured
"""

import ast
import copy
import hashlib
import itertools
import json
import os
import re
import unittest

import scrutiny_not_authority as M
import fixtures as F
import oracle as O

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W23SCRUTINY_SOURCES")
SLUG = "w23-scrutiny-not-authority"
DAY_HEADER = "# experiments/2026-11-14\n"
ROW_START = "- [%s](%s/): " % (SLUG, SLUG)
ROW_PREFIX = "- [%s](" % SLUG
MB_ROW_PREFIX = "- [mb-boundary-vs-judge]("
ROW_END = ("(Top method sketch of [arXiv 2611.14889](https://arxiv.org/abs/2611.14889);"
           " not a reproduction)")
FOOTER = "Do not merge experiment PRs without Ork review."


def day_readme():
    """Return (relative path, layout) of the day-index README.

    Repo layout: ../README.md in the 2026-11-14 folder, used only when it
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
CODE = ("scrutiny_not_authority.py", "oracle.py", "fixtures.py")
PY = CODE + ("test_scrutiny_not_authority.py", "mutants.py")
ALL = PY + ("README.md", "NOTICE", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
STDLIB_PERMITTED = {"ast", "copy", "hashlib", "io", "itertools", "json", "os", "re", "sys",
                    "unittest", "scrutiny_not_authority", "oracle", "fixtures",
                    "test_scrutiny_not_authority"}
CODE_IMPORTS = {"scrutiny_not_authority.py": set(), "oracle.py": set(),
                "fixtures.py": {"copy", "scrutiny_not_authority", "oracle"}}
NO_GO_TOKENS = ("vo" + "te", "vo" + "ting", "ensem" + "ble", "major" + "ity",
                "api" + "_key", "api" + "key", "open" + "ai", "anthro" + "pic", "ll" + "m",
                "envi" + "ron", "http" + "://", "https" + "://", "sub" + "process",
                "sock" + "et", "url" + "lib", "rand" + "om", "ti" + "me")
ABS_PATHS = ("/" + "workspace", "/" + "tmp", "/" + "home")
MARKERS = ("<" * 7, "=" * 7, ">" * 7)
PAPER_PAT = re.compile(r"\d+(?:\.\d+)?\s*%")
KINDS = [(s, b, v) for s in M.SOURCES for b in M.BASES for v in M.VERDICTS]


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


def make(assessment, triples):
    return {"case_id": "c", "conclusion": "x", "self_assessment": assessment,
            "checks": [{"check_id": "k%d" % i, "source": s, "basis": b, "verdict": v}
                       for i, (s, b, v) in enumerate(triples)]}


def module_tuple(rec):
    return (rec["outcome"], rec["baseline"]["decision"], rec["rule"]["decision"],
            rec["rule"]["flagged"], rec["rule"]["basis"], rec["agree_flip"]["decision"],
            rec["agree_silence"]["decision"])


def oracle_tuple(o):
    return (o["outcome"], o["baseline"], o["rule"], o["flagged"], o["basis"],
            o["agree_flip"], o["agree_silence"])


def scores():
    return M.score([M.evaluate(c) for c in F.cases().values()], F.gold())


class SubStr(str):
    pass


class SubList(list):
    pass


class SubDict(dict):
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


class TestDoneWhen(unittest.TestCase):

    def test_a_defective_assessment_flags_and_retains(self):
        defective = [n for n, c in F.CASES.items() if c["self_assessment"] == "defective"]
        self.assertEqual(len(defective), 10)
        for name in defective:
            rec = run(name)
            self.assertEqual(rec["status"], M.OK, name)
            self.assertTrue(rec["rule"]["flagged"], name)
            # Flagged and nothing independent refutes it: still held.
            if rec["outcome"] != M.REFUTED:
                self.assertIn(rec["rule"]["decision"], (M.RETAIN, M.HOLD), name)
        for name in ("def-sound-unchecked", "def-unsound-unchecked", "def-unsound-not-run",
                     "def-sound-self-recheck", "def-sound-laundered"):
            rec = run(name)
            self.assertEqual((rec["outcome"], rec["rule"]["decision"]), (M.NONE, M.HOLD), name)
        for name, c in F.CASES.items():
            if c["self_assessment"] == "ok":
                self.assertFalse(run(name)["rule"]["flagged"], name)
        # Every defective case with no independent check, whatever else.
        for k in range(3):
            for combo in itertools.product([t for t in KINDS
                                            if t[0] == "self" or t[1] != "own_evidence"
                                            or t[2] == "not_run"], repeat=k):
                rec = M.evaluate(make("defective", combo))
                self.assertEqual((rec["rule"]["decision"], rec["rule"]["flagged"]),
                                 (M.HOLD, True), combo)

    def test_b_auto_elimination_on_a_defective_assessment_refused(self):
        for name, c in F.cases().items():
            if c["self_assessment"] != "defective":
                continue
            rec = M.request_elimination(c, ["self_assessment"])
            self.assertEqual((rec["status"], rec["decision"], rec["basis"]),
                             (M.OK, M.REFUSE, ()), name)
        for name, (cn, cite, want) in F.requests().items():
            rec = M.request_elimination(case(cn), cite)
            self.assertEqual((rec["status"], rec["decision"]), (M.OK, want), name)
            self.assertEqual(O.gate(case(cn), cite), want, name)
        self.assertEqual(M.request_elimination(case("def-unsound-refuted"), ["w1"])["basis"],
                         ("w1",))
        self.assertEqual(M.request_elimination(case("def-unsound-derived"),
                                               ["s1", "x1"])["basis"], ("x1",))
        # The rule arm never eliminates on the rating alone.
        for k in range(3):
            for combo in itertools.product(KINDS, repeat=k):
                rec = M.evaluate(make("defective", combo))
                if rec["rule"]["decision"] == M.ELIMINATE:
                    self.assertEqual(rec["outcome"], M.REFUTED, combo)
                    self.assertTrue(rec["rule"]["basis"], combo)
        self.assertIn("rule: sound lost 0/8", F.summary())
        self.assertIn("eliminations without independent refutation 0, coherent 7/15",
                      F.summary())

    def test_c_scrutiny_check_drops_unsound_and_retains_sound(self):
        g = F.gold()
        for name in ("def-unsound-refuted", "def-unsound-derived"):
            rec = run(name)
            self.assertEqual(g[name], M.UNSOUND)
            self.assertEqual((rec["rule"]["flagged"], rec["rule"]["decision"]),
                             (True, M.ELIMINATE), name)
        for name in ("def-sound-cleared", "def-sound-world"):
            rec = run(name)
            self.assertEqual(g[name], M.SOUND)
            self.assertEqual((rec["rule"]["flagged"], rec["rule"]["decision"]),
                             (True, M.RETAIN), name)
            self.assertEqual(rec["baseline"]["decision"], M.ELIMINATE, name)
        # The same conclusion, before and after its scrutiny check.
        c = case("def-unsound-not-run")
        self.assertEqual(M.evaluate(c)["rule"]["decision"], M.HOLD)
        c["checks"][0]["verdict"] = "refutes"
        self.assertEqual(M.evaluate(c)["rule"]["decision"], M.ELIMINATE)
        c["checks"][0]["verdict"] = "supports"
        self.assertEqual(M.evaluate(c)["rule"]["decision"], M.RETAIN)
        sc = scores()
        self.assertEqual(sc["rule"]["sound_lost"], 0)
        self.assertEqual(sc["rule"]["unsound_eliminated"], 3)
        self.assertEqual(sc["rule"]["eliminated_unbacked"], 0)

    def test_d_forced_agreement_fails_where_the_rating_is_noisy(self):
        g = F.gold()
        for name in F.NOISY_RATING:
            rec = run(name)
            self.assertEqual((g[name], rec["self_assessment"]), (M.SOUND, M.DEFECTIVE), name)
            self.assertEqual(rec["agree_flip"]["decision"], M.NEGATE, name)
            self.assertNotEqual(rec["rule"]["decision"], M.ELIMINATE, name)
        sc = scores()
        self.assertEqual(sc["agree_flip"]["sound_negated"], len(F.NOISY_RATING))
        # Both forced-agreement arms are fully coherent, and both hold more
        # false conclusions unflagged than the rule arm: coherence is not
        # scored as success.
        for arm in ("agree_flip", "agree_silence", "baseline"):
            self.assertEqual(sc[arm]["coherent"], 15, arm)
        self.assertLess(sc["rule"]["coherent"], 15)
        for arm in ("agree_flip", "agree_silence"):
            self.assertGreater(sc[arm]["false_held_unflagged"],
                               sc["rule"]["false_held_unflagged"], arm)
        self.assertEqual(run("def-unsound-unchecked")["agree_silence"]["decision"], M.RETAIN)
        self.assertEqual(run("def-sound-cleared")["agree_flip"]["decision"], M.NEGATE)

    def test_e_no_llm(self):
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
                    got |= {a.name for a in node.names}
                elif isinstance(node, ast.ImportFrom):
                    got.add(node.module)
            self.assertEqual(got, want, name)
            low = code_tokens(read(name))
            for tok in NO_GO_TOKENS:
                self.assertNotIn(tok, low, (name, tok))
        for fname, fobj in sorted(vars(M).items()):
            if callable(fobj) and getattr(fobj, "__module__", None) == M.__name__ \
                    and hasattr(fobj, "__code__"):
                co = fobj.__code__
                low = "\n".join(co.co_names + co.co_varnames).lower()
                for tok in NO_GO_TOKENS:
                    self.assertNotIn(tok, low, (fname, tok))
        self.assertEqual([n for n in ast.walk(ast.parse(read("oracle.py")))
                          if isinstance(n, (ast.Import, ast.ImportFrom, ast.While))], [])

    def test_f_paper_on_unmeasured(self):
        self.assertEqual(M.paper_results(), M.ON_UNMEASURED)
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["measured_here"], "on_unmeasured")
        self.assertEqual(ev["paper_numbers"], [])
        self.assertEqual(len(ev["claims"]), 6)
        for c in ev["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")
            self.assertEqual(c["measured_here"], "on_unmeasured")
            self.assertTrue(c["on_unmeasured"])
            self.assertNotIn("values", c)
            self.assertIsNone(re.search(r"\d", c["quote"]), c["id"])


class TestRules(unittest.TestCase):

    def test_outcome_table(self):
        own = "own_evidence"
        self.assertEqual(M.outcome(()), M.NONE)
        cases = [
            ([("world_record", own, "refutes")], M.REFUTED),
            ([("fixture_test", own, "supports")], M.SUPPORTED),
            ([("world_record", own, "refutes"), ("fixture_test", own, "supports")], M.CONFLICT),
            ([("self", own, "refutes")], M.NONE),
            ([("self", own, "supports")], M.NONE),
            ([("external_derivation", "self_assessment", "refutes")], M.NONE),
            ([("fixture_test", own, "not_run")], M.NONE),
            ([("self", own, "refutes"), ("external_derivation", own, "refutes")], M.REFUTED),
            ([("self", own, "supports"), ("world_record", own, "refutes")], M.REFUTED),
            ([("fixture_test", "self_assessment", "supports"),
              ("world_record", own, "refutes")], M.REFUTED),
        ]
        for triples, want in cases:
            self.assertEqual(M.evaluate(make("ok", triples))["outcome"], want, triples)

    def test_independence(self):
        for s, b, v in KINDS:
            k = {"check_id": "k", "source": s, "basis": b, "verdict": v}
            self.assertEqual(M.independent(k), s != "self" and b == "own_evidence", (s, b))

    def test_rule_differs_from_baseline_only_on_defective(self):
        for k in range(3):
            for combo in itertools.product(KINDS, repeat=k):
                ok = M.evaluate(make("ok", combo))
                self.assertEqual(ok["rule"]["decision"], ok["baseline"]["decision"], combo)
                self.assertEqual(ok["agree_flip"]["decision"], ok["baseline"]["decision"])
                self.assertEqual(ok["agree_silence"]["decision"], ok["baseline"]["decision"])
                d = M.evaluate(make("defective", combo))
                self.assertEqual(d["baseline"]["decision"], M.ELIMINATE, combo)
                self.assertEqual(d["agree_flip"]["decision"], M.NEGATE, combo)
                self.assertEqual(d["agree_silence"]["decision"], ok["rule"]["decision"], combo)

    def test_rule_elimination_matches_gate(self):
        for k in range(3):
            for combo in itertools.product(KINDS, repeat=k):
                for a in M.ASSESSMENTS:
                    c = make(a, combo)
                    cite = ["self_assessment"] + [x["check_id"] for x in c["checks"]]
                    g = M.request_elimination(c, cite)
                    rec = M.evaluate(c)
                    self.assertEqual(rec["rule"]["decision"] == M.ELIMINATE,
                                     g["decision"] == M.PERMIT, (a, combo))
                    self.assertEqual(rec["rule"]["basis"], g["basis"], (a, combo))

    def test_cherry_pick_refused(self):
        c = case("def-sound-conflict")
        for cite in (["x1"], ["self_assessment", "x1"], ["x1", "t1"]):
            self.assertEqual(M.request_elimination(c, cite)["decision"], M.REFUSE, cite)
        c = case("ok-unsound-conflict")
        self.assertEqual(M.request_elimination(c, ["w1"])["decision"], M.REFUSE)

    def test_order_of_checks_is_irrelevant(self):
        for name, c in F.cases().items():
            want = M.evaluate(c)
            for perm in itertools.permutations(c["checks"]):
                d = copy.deepcopy(c)
                d["checks"] = list(perm)
                got = M.evaluate(d)
                self.assertEqual(module_tuple(got)[:4] + module_tuple(got)[5:],
                                 module_tuple(want)[:4] + module_tuple(want)[5:], name)
                self.assertEqual(sorted(got["rule"]["basis"]), sorted(want["rule"]["basis"]))

    def test_conclusion_text_is_not_read(self):
        for name, c in F.cases().items():
            want = module_tuple(M.evaluate(c))
            for text in ("This is wrong.", "defective", "refutes", "RETAIN"):
                d = copy.deepcopy(c)
                d["conclusion"] = text
                self.assertEqual(module_tuple(M.evaluate(d)), want, (name, text))

    def test_gate_inputs(self):
        c = case("def-unsound-refuted")

        def cfg(cs, cite, detail):
            rec = M.request_elimination(cs, cite)
            self.assertEqual((rec["status"], rec["detail"], rec["decision"]),
                             (M.CONFIG_ERROR, detail, None), (cite, detail))

        for bad in ([], None, "w1", ("w1",), SubList(["w1"]), ["w2"], ["w1", "w1"],
                    [SubStr("w1")], [1], [Spoof("w1")]):
            cfg(c, bad, "cite_invalid")
        cfg(None, ["w1"], "case_invalid")
        real = M._decide_elimination

        def boom(snap, cited):
            raise RuntimeError("boom")

        M._decide_elimination = boom
        try:
            cfg(c, ["w1"], "internal_error")
        finally:
            M._decide_elimination = real

    def test_score_counts(self):
        sc = scores()
        self.assertEqual(sc["config_error"], 0)
        want = {
            "baseline": (6, 5, 1, 1, 8, 15),
            "rule": (0, 3, 3, 1, 0, 7),
            "agree_flip": (6, 1, 1, 7, 0, 15),
            "agree_silence": (0, 3, 1, 3, 0, 15),
        }
        for arm, w in want.items():
            s = sc[arm]
            self.assertEqual((s["sound_lost"], s["unsound_eliminated"], s["unsound_held"],
                              s["false_held_unflagged"], s["eliminated_unbacked"],
                              s["coherent"]), w, arm)
            self.assertEqual((s["n"], s["sound"], s["unsound"]), (15, 8, 7), arm)
        # Hand recount from the labels.
        g = F.gold()
        for i, arm in enumerate(M.ARMS):
            lost = sum(1 for n, lab in F.LABELS.items()
                       if lab[0] == "sound" and lab[2 + i] in ("ELIMINATE", "NEGATE"))
            self.assertEqual(sc[arm]["sound_lost"], lost, arm)
            elim = sum(1 for n, lab in F.LABELS.items()
                       if g[n] == "unsound" and lab[2 + i] == "ELIMINATE")
            self.assertEqual(sc[arm]["unsound_eliminated"], elim, arm)

    def test_score_inputs(self):
        recs = [M.evaluate(c) for c in F.cases().values()]
        with_bad = M.score(recs + [M.evaluate(None)], F.gold())
        self.assertEqual(with_bad["config_error"], 1)
        self.assertEqual(with_bad["rule"], scores()["rule"])
        g = F.gold()
        g.pop("def-sound-world")
        self.assertEqual(M.score(recs, g), {"config_error": "gold_missing"})
        self.assertEqual(M.score(recs, {Spoof("x"): "sound"}),
                         {"config_error": "gold_key_invalid"})
        self.assertEqual(M.score(recs, {"x": SubStr("sound")}), {"config_error": "gold_invalid"})
        self.assertEqual(M.score(tuple(recs), F.gold()), {"config_error": "records_invalid"})
        bad = copy.deepcopy(recs[0])
        bad["rule"]["decision"] = "DROP"
        self.assertEqual(M.score([bad], F.gold()), {"config_error": "record_invalid"})
        bad = copy.deepcopy(recs[0])
        bad[Spoof("status")] = bad.pop("status")
        self.assertEqual(M.score([bad], F.gold()), {"config_error": "record_key_invalid"})
        bad = M.evaluate(None)
        bad[Spoof("other")] = 1
        self.assertEqual(M.score([bad], F.gold()), {"config_error": "record_key_invalid"})
        bad = copy.deepcopy(recs[0])
        bad["rule"][1] = 0
        self.assertEqual(M.score([bad], F.gold()), {"config_error": "record_key_invalid"})


class TestOracle(unittest.TestCase):

    def test_module_and_oracle_agree_on_all_fixtures(self):
        rows = F.run_all()
        self.assertEqual(len(rows), 15)
        for name, (m, o) in rows.items():
            self.assertEqual(module_tuple(m), oracle_tuple(o), name)
        self.assertIn("module vs oracle: 15/15 cases agree", F.summary())

    def test_module_and_oracle_agree_exhaustively(self):
        n = 0
        for k in range(4):
            for combo in itertools.product(KINDS, repeat=k):
                for a in M.ASSESSMENTS:
                    c = make(a, combo)
                    self.assertEqual(module_tuple(M.evaluate(c)), oracle_tuple(O.reference(c)),
                                     (a, combo))
                    n += 1
        self.assertEqual(n, 28850)

    def test_gate_matches_oracle_exhaustively(self):
        n = 0
        for k in range(3):
            for combo in itertools.product(KINDS, repeat=k):
                for a in M.ASSESSMENTS:
                    c = make(a, combo)
                    ids = ["self_assessment"] + [x["check_id"] for x in c["checks"]]
                    for r in range(1, len(ids) + 1):
                        for cite in itertools.combinations(ids, r):
                            got = M.request_elimination(c, list(cite))
                            self.assertEqual(got["decision"], O.gate(c, cite), (a, combo, cite))
                            n += 1
        self.assertEqual(n, 2 * (1 + 24 * 3 + 576 * 7))

    def test_oracle_is_a_separate_code_path(self):
        src = read("oracle.py")
        tree = ast.parse(src)
        names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        mod = {n for n, v in vars(M).items() if callable(v)}
        self.assertEqual(names & mod, set())
        self.assertNotIn("scrutiny_not_authority", src)


class TestInputs(unittest.TestCase):

    def cfg(self, c, detail=None):
        rec = M.evaluate(c)
        self.assertEqual(rec["status"], M.CONFIG_ERROR)
        if detail is not None:
            self.assertEqual(rec["detail"], detail)
        for arm in M.ARMS:
            self.assertIsNone(rec[arm])

    def test_case_shape(self):
        self.cfg(None, "case_invalid")
        self.cfg([], "case_invalid")
        self.cfg(SubDict(case("def-sound-cleared")), "case_invalid")
        c = case("def-sound-cleared")
        c["extra"] = 1
        self.cfg(c, "case_key_invalid")
        c = case("def-sound-cleared")
        c.pop("checks")
        self.cfg(c, "case_key_invalid")
        for v in ("", " c", "c ", None, 3):
            c = case("def-sound-cleared")
            c["case_id"] = v
            self.cfg(c, "case_id_invalid")
        for v in ("", "   ", None, ["x"]):
            c = case("def-sound-cleared")
            c["conclusion"] = v
            self.cfg(c, "conclusion_invalid")
        for v in ("OK", "bad", "", None, True):
            c = case("def-sound-cleared")
            c["self_assessment"] = v
            self.cfg(c, "self_assessment_invalid")
        for v in (None, (), "t1", {}):
            c = case("def-sound-cleared")
            c["checks"] = v
            self.cfg(c, "checks_invalid")

    def test_check_shape(self):
        for v in (None, "t1", [], SubDict({"check_id": "t1"})):
            c = case("def-sound-cleared")
            c["checks"] = [v]
            self.cfg(c, "check_invalid")
        c = case("def-sound-cleared")
        c["checks"][0]["weight"] = 1
        self.cfg(c, "check_key_invalid")
        for v in ("", "self_assessment", " t1", None):
            c = case("def-sound-cleared")
            c["checks"][0]["check_id"] = v
            self.cfg(c, "check_id_invalid")
        c = case("def-sound-world")
        c["checks"][1]["check_id"] = "w1"
        self.cfg(c, "check_id_invalid")
        for field, detail in (("source", "check_source_invalid"),
                              ("basis", "check_basis_invalid"),
                              ("verdict", "check_verdict_invalid")):
            for v in ("", "other", None, 1, SubStr("self")):
                c = case("def-sound-cleared")
                c["checks"][0][field] = v
                self.cfg(c, detail)

    def test_exact_types_in_every_value_slot(self):
        c = case("def-sound-cleared")
        c["case_id"] = SubStr("x")
        self.cfg(c, "case_id_invalid")
        c = case("def-sound-cleared")
        c["conclusion"] = SubStr("x")
        self.cfg(c, "conclusion_invalid")
        c = case("def-sound-cleared")
        c["self_assessment"] = SubStr("ok")
        self.cfg(c, "self_assessment_invalid")
        c = case("def-sound-cleared")
        c["checks"] = SubList(c["checks"])
        self.cfg(c, "checks_invalid")
        c = case("def-sound-cleared")
        c["checks"][0] = SubDict(c["checks"][0])
        self.cfg(c, "check_invalid")
        c = case("def-sound-cleared")
        c["checks"][0]["check_id"] = SubStr("t1")
        self.cfg(c, "check_id_invalid")

    def test_run_guard_maps_internal_error(self):
        real = M._run

        def boom(snap):
            raise KeyError("boom")

        M._run = boom
        try:
            self.cfg(case("def-sound-cleared"), "internal_error")
        finally:
            M._run = real

    def test_never_raises(self):
        weird = [None, 1, "x", [], {}, {"case_id": object()}, {1: 2}, object(),
                 {"case_id": "c", "conclusion": "x", "self_assessment": "ok",
                  "checks": [{"check_id": "k", "source": "self", "basis": "own_evidence",
                              "verdict": "refutes", Spoof("x"): 1}]}]
        for w in weird:
            self.assertEqual(M.evaluate(w)["status"], M.CONFIG_ERROR, w)
            self.assertEqual(M.request_elimination(w, ["self_assessment"])["status"],
                             M.CONFIG_ERROR)
            self.assertIn("config_error", M.score(w, w))

    def test_inputs_not_mutated(self):
        for name, c in F.cases().items():
            before = copy.deepcopy(c)
            M.evaluate(c)
            M.request_elimination(c, ["self_assessment"])
            self.assertEqual(c, before, name)


class TestKeysAndSnapshot(unittest.TestCase):
    """F1: exact-str keys before any lookup; arms run on a snapshot only."""

    def cfg(self, rec, detail):
        self.assertEqual((rec["status"], rec["detail"]), (M.CONFIG_ERROR, detail))
        self.assertIsNone(rec["rule"])

    def test_spoofed_case_key_is_config_error(self):
        for field in M.CASE_FIELDS:
            c = case("def-unsound-refuted")
            value = c.pop(field)
            key = Spoof(field)
            c[key] = value
            self.cfg(M.evaluate(c), "case_key_invalid")
            self.assertEqual(key.n, 0, field)

    def test_spoofed_check_key_cannot_turn_a_hold_into_an_elimination(self):
        """A spoofed check key whose comparison would plant an independent
        refutation in the caller's case cannot make the rule eliminate."""
        for field in M.CHECK_FIELDS:
            for flip in range(1, 12):
                c = case("def-sound-unchecked")
                c["checks"] = [{"check_id": "s1", "source": "self", "basis": "own_evidence",
                                "verdict": "refutes"}]
                box = {"c": c}

                def hook(n, flip=flip):
                    if n == flip:
                        box["c"]["checks"].append(
                            {"check_id": "w9", "source": "world_record",
                             "basis": "own_evidence", "verdict": "refutes"})

                k = c["checks"][0]
                value = k.pop(field)
                key = Spoof(field, hook)
                k[key] = value
                rec = M.evaluate(c)
                self.cfg(rec, "check_key_invalid")
                self.assertEqual(key.n, 0, (field, flip))
                self.assertEqual(len(c["checks"]), 1, (field, flip))
                g = M.request_elimination(c, ["self_assessment"])
                self.assertEqual(g["status"], M.CONFIG_ERROR)

    def test_str_subclass_keys_and_values_rejected(self):
        class Two(str):
            def __eq__(self, other):
                return other in ("self", "world_record")

            __hash__ = str.__hash__

        c = case("def-sound-self-recheck")
        c["checks"][0]["source"] = Two("self")
        self.cfg(M.evaluate(c), "check_source_invalid")
        c = case("def-sound-self-recheck")
        c["checks"][0][SubStr("source")] = c["checks"][0].pop("source")
        self.cfg(M.evaluate(c), "check_key_invalid")
        c = case("def-sound-self-recheck")
        c[SubStr("checks")] = c.pop("checks")
        self.cfg(M.evaluate(c), "case_key_invalid")
        for name, c in F.cases().items():
            rec = M.evaluate(c)
            self.assertIs(type(rec["case_id"]), str, name)
            for b in rec["rule"]["basis"]:
                self.assertIs(type(b), str)

    def test_non_str_keys_rejected_at_every_level(self):
        for bad in (1, (1, 2), SubStr("x"), Spoof("other"), None):
            c = case("def-unsound-refuted")
            c[bad] = 1
            self.cfg(M.evaluate(c), "case_key_invalid")
            c = case("def-unsound-refuted")
            c["checks"][0][bad] = 1
            self.cfg(M.evaluate(c), "check_key_invalid")

    def test_arms_see_only_the_snapshot(self):
        seen = []
        real = M._run

        def spy(snap):
            seen.append(snap)
            return real(snap)

        M._run = spy
        try:
            for name, c in F.cases().items():
                rec = M.evaluate(c)
                self.assertEqual(len(seen), 1, name)
                snap = seen.pop()
                self.assertEqual(containers(snap, set()) & containers(c, set()), set(), name)
                self.assertIs(type(snap["checks"]), tuple)
                for k in snap["checks"]:
                    self.assertIs(type(k), dict)
                c["checks"].clear()
                c["self_assessment"] = "ok"
                self.assertEqual(rec, real(snap), name)
        finally:
            M._run = real

    def test_caller_mutation_mid_run_changes_nothing(self):
        """The caller's case is changed while the arms run (before the first
        arm reads anything); every arm still decides from the snapshot."""
        real = M.baseline
        for name in F.CASES:
            clean = run(name)
            c = case(name)

            def meddle(snap, c=c):
                c["self_assessment"] = "ok" if c["self_assessment"] == "defective" else "defective"
                for k in c["checks"]:
                    k["verdict"] = "refutes"
                    k["source"] = "world_record"
                    k["basis"] = "own_evidence"
                c["checks"].append({"check_id": "z9", "source": "world_record",
                                    "basis": "own_evidence", "verdict": "supports"})
                return real(snap)

            M.baseline = meddle
            try:
                rec = M.evaluate(c)
            finally:
                M.baseline = real
            self.assertEqual(rec, clean, name)

    def test_gate_runs_on_a_snapshot(self):
        c = case("def-unsound-refuted")
        cite = ["w1"]
        real = M._decide_elimination

        def spy(snap, cited):
            c["checks"][0]["verdict"] = "supports"
            cite.clear()
            return real(snap, cited)

        M._decide_elimination = spy
        try:
            rec = M.request_elimination(c, cite)
        finally:
            M._decide_elimination = real
        self.assertEqual((rec["decision"], rec["basis"]), (M.PERMIT, ("w1",)))


class TestFixtures(unittest.TestCase):

    def test_expected_table(self):
        for name, (m, o) in F.run_all().items():
            lab = F.LABELS[name]
            self.assertEqual((m["baseline"]["decision"], m["rule"]["decision"],
                              m["agree_flip"]["decision"], m["agree_silence"]["decision"]),
                             lab[2:6], name)

    def test_fixture_invariants(self):
        cs = F.cases()
        self.assertEqual(sorted(cs), sorted(F.LABELS))
        self.assertEqual(len(cs), 15)
        g = F.gold()
        self.assertEqual(sorted(g.values()).count("sound"), 8)
        for name, c in cs.items():
            self.assertEqual(c["case_id"], name)
            self.assertTrue(name.startswith("ok-" if c["self_assessment"] == "ok" else "def-"))
            self.assertIn("-%s-" % g[name], "-" + name + "-")
            out = M.evaluate(c)["outcome"]
            # Independent evidence is truthful except in the conflict cases.
            if out == M.REFUTED:
                self.assertEqual(g[name], "unsound", name)
            if out == M.SUPPORTED:
                self.assertEqual(g[name], "sound", name)
        for name in F.NOISY_RATING:
            self.assertEqual((cs[name]["self_assessment"], g[name]), ("defective", "sound"))
        self.assertEqual(sorted(F.NOISY_RATING),
                         sorted(n for n, c in cs.items()
                                if c["self_assessment"] == "defective" and g[n] == "sound"))
        kinds = set(lab[1] for lab in F.LABELS.values())
        for k in ("noisy_rating", "self_check_only", "laundered_check", "missing_check",
                  "conflict", "independent_refutation", "missed_by_both", "control"):
            self.assertIn(k, kinds)
        for name, (cn, cite, want) in F.requests().items():
            self.assertIn(cn, cs, name)

    def test_fixture_pins(self):
        self.assertEqual(F.CASES["def-sound-laundered"]["checks"],
                         [{"check_id": "x1", "source": "external_derivation",
                           "basis": "self_assessment", "verdict": "refutes"}])
        self.assertEqual(F.CASES["def-unsound-not-run"]["checks"][0]["verdict"], "not_run")
        self.assertEqual(len(F.REQUESTS), 9)
        self.assertEqual(sum(1 for r in F.REQUESTS.values() if r[2] == "PERMIT"), 3)

    def test_fixtures_return_copies(self):
        c = F.cases()
        c["def-sound-cleared"]["checks"].clear()
        r = F.requests()
        r["Q1-self-assessment-only"][1].append("x")
        self.assertEqual(len(F.cases()["def-sound-cleared"]["checks"]), 1)
        self.assertEqual(F.requests()["Q1-self-assessment-only"][1], ["self_assessment"])

    def test_determinism(self):
        self.assertEqual(F.summary(), F.summary())


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
        dirty = ("an al" + "lowlist that ke" + "eps 12.5" + " " + "% in /" + "tmp per Check" + "er "
                 + "<" * 7)
        clean = "clean text " + ROW_END
        every = {"banned_word", "absolute_path", "marker", "paper_number"}
        self.assertEqual(hygiene_hits(dirty), every)
        self.assertEqual(hygiene_hits(clean), set())

        def day(own, sibling):
            return (DAY_HEADER + "\n- [w23-other](w23-other/): " + sibling + "\n"
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
        self.assertIn("Top method sketch", rows[0])
        flat = rows[0]
        for s in ("loses 6 of 8 sound conclusions", "the scrutiny rule loses none",
                  "eliminates 3 of 7 unsound ones only on independent refutation"):
            self.assertIn(s, flat)
        sc = scores()
        self.assertEqual((sc["baseline"]["sound_lost"], sc["baseline"]["sound"]), (6, 8))
        self.assertEqual((sc["rule"]["unsound_eliminated"], sc["rule"]["unsound"]), (3, 7))
        mb = [i for i, line in enumerate(lines) if line.startswith(MB_ROW_PREFIX)]
        self.assertEqual(len(mb), 1)
        if LAYOUT == "flat":
            bullets = [line for line in lines if line.startswith("- ")]
            self.assertEqual(len(bullets), 2)
            self.assertEqual(lines.index(rows[0]), mb[0] + 1)

    def test_no_paper_claims_outside_evidence(self):
        for name in PY + ("README.md", "NOTICE", DAY):
            self.assertIsNone(PAPER_PAT.search(scan_text(name, read(name))), name)

    def test_readme_credits_differentiation_and_limits(self):
        flat = " ".join(read("README.md").split())
        ev = json.loads(read("paper_evidence.json"))
        self.assertIn(ev["paper"]["title"], flat)
        for author in ev["paper"]["authors"]:
            self.assertIn(author, flat)
        for s in ("**Top** method sketch", "not a reproduction", "UNVERIFIED",
                  "on_unmeasured", "paper_evidence.json", "## Limits", "## Builder reflection",
                  "nonexclusive-distrib", "python3 -B -m unittest", "python3 -B mutants.py",
                  "w22-revision-selectivity", "w22-spec-satisficing", "w17-revision-contract",
                  "no timeout", "advisory, not a deletion authority"):
            self.assertIn(s, flat, s)
        for line in F.summary().splitlines()[16:]:
            self.assertIn(line, read("README.md"), line)
        notice = " ".join(read("NOTICE").split())
        for s in (ev["paper"]["title"], "Eno Agolli", "arXiv:2611.14889",
                  "https://arxiv.org/abs/2611.14889", "nonexclusive-distrib", "clean-room",
                  "Nothing was cloned or run"):
            self.assertIn(s, notice, s)

    def test_evidence_shape(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.14889")
        self.assertIn("nonexclusive-distrib", ev["paper"]["licence"])
        self.assertFalse(ev["paper"]["pdf_read"])
        self.assertIsNone(ev["upstream_code"]["repo"])
        for c in ev["claims"]:
            self.assertEqual(len(c["quote"]), c["length"])

    def test_quotes_exact_in_sources(self):
        if not SOURCES:
            self.skipTest("W23SCRUTINY_SOURCES not set")
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
