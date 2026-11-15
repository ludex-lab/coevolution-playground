"""Tests for the w24-alert-silence-is-not-fix method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
The quote check reads the source copy named in paper_evidence.json from the
directories listed in $W24ASF_SOURCES (os.pathsep separated). There is no
default: when the variable is unset, or the file is absent, that check is
skipped.

Done-when mapping (Lab Dig 2 Wave24, Top: arXiv 2611.17123, verifier Build #3):
  1 test_1_toy_analyzer_has_one_declared_gap
  2 test_2_executor_is_independent_ground_truth
  3 test_3_rewrite_fixture_families
  4 test_4_gate_fixed_only_when_executor_says_gone
  5 test_5_baseline_accepts_every_silencing_rewrite
  6 test_6_false_alarm_budget
  7 test_7_detection_and_robustness_side_by_side
  8 test_8_no_ensemble_no_codeql_no_model_no_execution
  9 test_9_readme_states_what_is_new
  10 test_10_missing_run_unmeasured_no_on_expiry_paper_unmeasured
"""

import ast
import copy
import hashlib
import json
import os
import re
import unittest

import alert_silence as M
import executor as X
import fixtures as F
import oracle as O

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W24ASF_SOURCES")
SLUG = "w24-alert-silence-is-not-fix"
DAY_HEADER = "# experiments/2026-11-15\n"
ROW_START = "- [%s](%s/): " % (SLUG, SLUG)
ROW_PREFIX = "- [%s](" % SLUG
ROW_END = ("(Top method sketch of [arXiv 2611.17123](https://arxiv.org/abs/2611.17123);"
           " not a reproduction)")
MAIN_ROW_PREFIXES = ("- [mb-conversation-loss-oracle](",)
MAIN_ROW_SHA256 = {"- [mb-conversation-loss-oracle](":
                   "4cbad9b95da8c0e14d3845b23a36039d4b768af25a5ce84827dad1c72f09d83e"}
FOOTER = "Do not merge experiment PRs without Ork review."
NEIGHBOURS = ("w23-world-consistent-history", "w21-unused-contradiction", "w20-fidelity-audit")


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
CODE = ("alert_silence.py", "executor.py", "oracle.py", "fixtures.py")
PY = CODE + ("test_alert_silence.py", "mutants.py")
ALL = PY + ("README.md", "NOTICE", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
STDLIB_PERMITTED = {"ast", "copy", "hashlib", "io", "itertools", "json", "os", "re", "sys",
                    "unittest", "alert_silence", "executor", "oracle", "fixtures",
                    "test_alert_silence"}
CODE_IMPORTS = {"alert_silence.py": {"hashlib", "json", "executor"},
                "executor.py": {"hashlib", "json"},
                "oracle.py": {"hashlib", "json"},
                "fixtures.py": {"copy", "alert_silence", "executor", "oracle"}}
# Process, network, dynamic-code and system access: never in the code files.
EXEC_MODULES = {"sub" + "process", "sock" + "et", "url" + "lib", "http", "import" + "lib",
                "ctypes", "multiprocessing", "os", "sys", "shutil", "pty", "runpy", "code",
                "pickle", "marshal", "builtins"}
EXEC_CALLS = {"ev" + "al", "ex" + "ec", "comp" + "ile", "__imp" + "ort__", "open",
              "sys" + "tem", "pop" + "en", "spawnv", "execv", "getattr", "globals", "vars",
              "breakpoint", "input"}
EXEC_TEXT = ("sub" + "process", "os." + "system", "ev" + "al(", "ex" + "ec(", "sock" + "et",
             "url" + "lib", "import" + "lib", "__imp" + "ort__", "comp" + "ile(")
NO_GO_TOKENS = ("code" + "ql", "l" + "lm", "gp" + "t", "cla" + "ude", "open" + "ai",
                "anthro" + "pic", "ensem" + "ble", "vo" + "te", "combi" + "ned", "maj" + "ority",
                "rewri" + "ter", "envi" + "ron", "api" + "_key", "ti" + "me.", "date" + "time",
                "rand" + "om", "thre" + "ad", "sql" + "ite", "requ" + "ests", "http" + "://",
                "https" + "://")
ABS_PATHS = ("/" + "workspace", "/" + "tmp", "/" + "home")
MARKERS = ("<" * 7, "=" * 7, ">" * 7)
PAPER_PAT = re.compile(r"\d+(?:\.\d+)?\s*%|US" + r"D\s*\d|\b17" + r"2\b|\b64" + r" of\b|"
                       r"\bseven" + r" gaps\b|\bthree" + r" (?:analyzers|rewrites)\b|"
                       r"\b0\.5" + r"1\b|\b26\.2\b", re.I)


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


class SubStr(str):
    pass


class EqStr(str):
    """A str subclass that claims equality with everything."""

    def __eq__(self, other):
        return True

    def __hash__(self):
        return 0


class SubInt(int):
    pass


class CmpInt(int):
    def __lt__(self, other):
        return True

    def __le__(self, other):
        return True

    def __ge__(self, other):
        return True


class SubFloat(float):
    pass


class SubList(list):
    pass


class SubDict(dict):
    pass


class SubBool:
    """Truthy object standing in for a bool."""

    def __bool__(self):
        return True


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


def imports_of(src):
    got = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            got |= set(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            got.add((node.module or "").split(".")[0])
    return got


def exec_hits(src):
    """Process, network and dynamic-code use found in a code file."""
    hits = set()
    for m in imports_of(src):
        if m in EXEC_MODULES:
            hits.add("import " + m)
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) \
                else ""
            if name in EXEC_CALLS:
                hits.add("call " + name)
    low = src.lower()
    for t in EXEC_TEXT:
        if t in low:
            hits.add("text " + t)
    return hits


def function_names(name):
    return set(n.name for n in ast.walk(ast.parse(read(name))) if isinstance(n, ast.FunctionDef))


def containers(obj, out):
    """Collect the id of every dict, list and tuple reachable from obj."""
    if isinstance(obj, (dict, list, tuple)):
        out.add(id(obj))
        items = list(obj.keys()) + list(obj.values()) if isinstance(obj, dict) else obj
        for x in items:
            containers(x, out)
    return out


def flat_ops(program, body=None):
    """(op, name) of every step the program runs, called helpers included."""
    out = []
    for st in program["body"] if body is None else body:
        out.append((st["op"], st.get("name")))
        if st["op"] == "call":
            out += flat_ops(program, program["helpers"][st["fn"]]["body"])
    return out


# Exhaustive space of short programs: a source, then up to three steps over
# every op and every earlier variable of the right kind, then an optional
# sink on any string variable. Two helpers are declared in every program.
SPACE_HELPERS = {"h": F.helper("x", [F.parse("u", "x"), F.field("y", "u", "path")], "y"),
                 "w": F.helper("x", [F.const("p", "q="), F.concat("y", "p", "x")], "y")}


def _steps(env, n):
    strs = [v for v, k in env if k == "str"]
    urls = [v for v, k in env if k == "url"]
    lists = [v for v, k in env if k == "list"]
    d = "v%d" % n
    out = [(F.const(d, "/a?"), "str")]
    for s in strs:
        out += [(F.sanitize(d, s), "str"), (F.parse(d, s), "url"), (F.pack(d, s), "list"),
                (F.call(d, "h", s), "str"), (F.call(d, "w", s), "str")]
        out += [(F.concat(d, s, t), "str") for t in strs]
    for u in urls:
        out += [(F.field(d, u, "path"), "str"), (F.field(d, u, "query"), "str"),
                (F.assign(d, u), "url")]
    out += [(F.index(d, li, 0), "str") for li in lists]
    return out


def space_programs(depth=3):
    def rec(body, env, n):
        yield F.prog(body, SPACE_HELPERS)
        for v, k in env:
            if k == "str":
                yield F.prog(body + [F.sink(v)], SPACE_HELPERS)
        if n > depth:
            return
        for st, kind in _steps(env, n):
            yield from rec(body + [st], env + [(st["dst"], kind)], n + 1)
    return rec([F.src("r")], [("r", "str")], 1)


SPACE_SIZE = 9149
RUN_STATES = ("missing", "bound", "other_program", "harmless_input", "flipped")


def with_runs(before, after, sb, sa):
    """A change with each run in one of RUN_STATES."""
    c = {"case_id": "s", "family": "space", "exploit": F.EXPLOIT,
         "before": copy.deepcopy(before), "after": copy.deepcopy(after), "runs": {}}
    other = F.prog([F.const("z", "other"), F.sink("z")])
    for name, state in (("before", sb), ("after", sa)):
        p = c[name]
        if state == "bound":
            c["runs"][name] = X.execute(p, F.EXPLOIT)
        elif state == "other_program":
            c["runs"][name] = X.execute(other, F.EXPLOIT)
        elif state == "harmless_input":
            c["runs"][name] = X.execute(p, F.HARMLESS)
        elif state == "flipped":
            r = X.execute(p, F.EXPLOIT)
            r["reached"] = not r["reached"]
            c["runs"][name] = r
    return c


def gate_space():
    """Every run state for both programs, over every fixture after program."""
    afters = ([F.ORIGINALS["O1"]] + [g[2] for g in F.SILENCING.values()]
              + [g[2] for g in F.CONTROLS.values()] + [g[2] for g in F.FIXES.values()])
    # Before programs: both originals, a vulnerable program the analyzer
    # already misses (so "alert before" is not a given), and a program the
    # exploit does not reach (so "vulnerable before" is not a given either).
    befores = (list(F.ORIGINALS.values()) + [F.SILENCING["A1-path-routing"][2]]
               + [F.FIXES["X3-constant-id"][2]])
    for before in befores:
        for after in afters:
            for sb in RUN_STATES:
                for sa in RUN_STATES:
                    yield with_runs(before, after, sb, sa)


GATE_SPACE_SIZE = 4 * 15 * 25


class TestDoneWhen(unittest.TestCase):

    def test_1_toy_analyzer_has_one_declared_gap(self):
        self.assertEqual((M.GAP_API, M.GAP_FIELD), ("parse_url", "path"))
        base = [F.src("r"), F.parse("u", "r")]
        q = F.prog(base + [F.field("v", "u", "query"), F.sink("v")])
        p = F.prog(base + [F.field("v", "u", "path"), F.sink("v")])
        self.assertEqual(M.analyze(q), ("body[3]",))
        self.assertEqual(M.analyze(p), ())
        self.assertEqual(M.analyze(p, gap=False), ("body[3]",))
        # The gap is the one unsoundness: over every short program, an
        # exploit that reaches a sink is always alerted with the gap closed,
        # and when the declared analyzer is silent the flow reads a path.
        n = silent = 0
        for prog in space_programs():
            reached = X.execute(prog, F.EXPLOIT)["reached"]
            if reached:
                self.assertNotEqual(M.analyze(prog, gap=False), ())
                if M.analyze(prog) == ():
                    silent += 1
                    self.assertIn(("field", "path"), flat_ops(prog))
            n += 1
        self.assertEqual(n, SPACE_SIZE)
        self.assertGreater(silent, 0)
        # Every fixture rewrite is alerted once the gap is closed.
        for cid, (_, _, after) in F.SILENCING.items():
            self.assertNotEqual(M.analyze(after, gap=False), (), cid)

    def test_2_executor_is_independent_ground_truth(self):
        self.assertEqual(imports_of(read("executor.py")), {"hashlib", "json"})
        self.assertNotIn("executor", imports_of(read("oracle.py")))
        # The module imports the executor for one purpose: _rerun() calls
        # executor.execute(); no other function names it, and the analyzer,
        # the gate and the baseline never see it.
        tree = ast.parse(read("alert_silence.py"))
        users = set()
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                for node in ast.walk(fn):
                    if isinstance(node, ast.Name) and node.id == "executor":
                        users.add(fn.name)
        self.assertEqual(users, {"_rerun"})
        uses = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name) and n.value.id == "executor"]
        self.assertEqual([n.attr for n in uses], ["execute"])
        ex_names = function_names("executor.py")
        self.assertEqual(ex_names & function_names("alert_silence.py"), set())
        self.assertEqual(ex_names & function_names("oracle.py"), set())
        for p in F.ORIGINALS.values():
            self.assertTrue(X.execute(p, F.EXPLOIT)["reached"])
        for group, want in ((F.SILENCING, True), (F.CONTROLS, True), (F.FIXES, False)):
            for cid, (_, _, after) in group.items():
                self.assertEqual(X.execute(after, F.EXPLOIT)["reached"], want, cid)
        # A probe input is no substitute: it "passes" a vulnerable program.
        d1 = F.SILENCING["D1-split-route"][2]
        self.assertEqual((X.execute(d1, F.HARMLESS)["reached"],
                          X.execute(d1, F.EXPLOIT)["reached"]), (False, True))
        r = X.execute(F.ORIGINALS["O1"], F.EXPLOIT)
        self.assertEqual(r["ran_on"], M.digest(M.validate(case("K2-list-alias"))["before"]))
        self.assertEqual(X.received(F.FIXES["X1-sanitize"][2], F.EXPLOIT),
                         [F.SELECT + "1&#39; OR &#39;1&#39;=&#39;1"])

    def test_3_rewrite_fixture_families(self):
        fams = {}
        for cid, (orig, fam, after) in F.SILENCING.items():
            fams.setdefault(fam, []).append(cid)
            self.assertNotEqual(X.fingerprint(after), X.fingerprint(F.ORIGINALS[orig]))
        self.assertEqual(sorted(fams), sorted(F.FAMILIES))
        self.assertGreaterEqual(len(fams), 4)
        for fam, ids in fams.items():
            self.assertGreaterEqual(len(ids), 1, fam)
        self.assertGreaterEqual(len(F.CONTROLS), 2)
        self.assertGreaterEqual(len(F.FIXES), 2)
        for ids, want in ((F.SILENCING_IDS, (True, False, True, True)),
                          (F.CONTROL_IDS, (True, True, True, True)),
                          (F.FIX_IDS, (True, False, True, False))):
            for cid in ids:
                r = run(cid)
                self.assertEqual((r["alert_before"], r["alert_after"], r["exploit_before"],
                                  r["exploit_after"]), want, cid)
        kinds = set(fam for _, fam, _ in F.FIXES.values())
        self.assertEqual(kinds, {"fix"})
        self.assertNotIn("sink", [s["op"] for s in F.FIXES["X2-sink-removed"][2]["body"]])
        self.assertIn("sanitize", [s["op"] for s in F.FIXES["X1-sanitize"][2]["body"]])

    def test_4_gate_fixed_only_when_executor_says_gone(self):
        for cid in F.SILENCING_IDS:
            r = run(cid)
            self.assertEqual((r["receipt"], r["reason"]), (M.REFUSE, M.ALERT_SILENCED), cid)
        for cid in F.UNMEASURED_IDS:
            r = run(cid)
            self.assertEqual((r["receipt"], r["measurement"]), (M.REFUSE, M.ON_UNMEASURED))
        n = 0
        seen = set()
        for c in gate_space():
            r = M.evaluate(c)
            self.assertEqual(r["status"], M.OK)
            seen.add(r["reason"])
            if r["receipt"] == M.FIXED:
                self.assertIs(r["exploit_after"], False)
                self.assertIs(r["exploit_before"], True)
                self.assertEqual(r["measurement"], M.MEASURED)
            if r["exploit_after"] is None or r["exploit_before"] is None:
                self.assertEqual((r["receipt"], r["measurement"]), (M.REFUSE, M.ON_UNMEASURED))
            if r["reason"] in M.UNMEASURED_REASONS:
                self.assertEqual(r["measurement"], M.ON_UNMEASURED)
                self.assertIsNone(r["exploit_before"] if r["run"] == "before"
                                  else r["exploit_after"])
            if r["exploit_after"] is True and r["exploit_before"] is True:
                self.assertEqual(r["reason"], M.VULN_PRESENT if r["alert_after"]
                                 else M.ALERT_SILENCED)
            n += 1
        self.assertEqual(n, GATE_SPACE_SIZE)
        self.assertEqual(seen, set(M.REASONS))

    def test_5_baseline_accepts_every_silencing_rewrite(self):
        recs = [M.evaluate(c) for c in F.cases().values()]
        tot = M.totals(recs, (("s", F.SILENCING_IDS), ("x", F.FIX_IDS)))
        k, m = len(F.SILENCING_IDS), len(F.FIX_IDS)
        self.assertEqual(tot["s"], (0, k, k))
        self.assertEqual(tot["x"], (m, m, m))
        for c in gate_space():
            r = M.evaluate(c)
            self.assertEqual(r["baseline"] == M.FIXED,
                             r["alert_before"] and not r["alert_after"])

    def test_6_false_alarm_budget(self):
        refused_fixes = [c for c in F.FIX_IDS if run(c)["receipt"] != M.FIXED]
        control_receipts = [c for c in F.CONTROL_IDS
                            if M.FIXED in (run(c)["receipt"], run(c)["baseline"])]
        self.assertEqual((refused_fixes, control_receipts), ([], []))
        for cid in F.CONTROL_IDS:
            self.assertEqual(run(cid)["reason"], M.VULN_PRESENT)

    def test_7_detection_and_robustness_side_by_side(self):
        recs = [M.evaluate(c) for c in F.cases().values()]
        sbs = M.side_by_side(recs)
        vp = len(F.SILENCING_IDS) + len(F.CONTROL_IDS)
        self.assertEqual(sbs, {"detection": (2, 2), "robustness": (len(F.CONTROL_IDS), vp)})
        # The same analyzer with the gap closed is fully robust on the fixture.
        kept = sum(1 for g in (F.SILENCING, F.CONTROLS) for _, _, a in g.values()
                   if M.analyze(a, gap=False))
        self.assertEqual(kept, vp)
        self.assertEqual(M.side_by_side([]), {"detection": (0, 0), "robustness": (0, 0)})
        # An original the analyzer misses counts against detection.
        missed = with_runs(F.SILENCING["A1-path-routing"][2], F.FIXES["X1-sanitize"][2],
                           "bound", "bound")
        r = M.evaluate(missed)
        # The gate accepts this true fix; the baseline, with no alert to lose,
        # does not.
        self.assertEqual((r["alert_before"], r["baseline"], r["receipt"]),
                         (False, M.NOT_FIXED, M.FIXED))
        self.assertEqual(M.side_by_side(recs + [r])["detection"], (2, 3))

    def test_8_no_ensemble_no_codeql_no_model_no_execution(self):
        for name in CODE:
            self.assertEqual(exec_hits(read(name)), set(), name)
            toks = code_tokens(read(name))
            for t in NO_GO_TOKENS:
                self.assertNotIn(t, toks, (name, t))
        # One analyzer: analyze() is the only analyzer entry point the
        # decision path calls, and it is called once per program.
        src = read("alert_silence.py")
        self.assertEqual(src.count("analyze(snap["), 2)
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "analyze":
                self.assertEqual((len(node.args), node.keywords), (1, []))
        # The scan itself catches each forbidden use.
        for bad in ("import sub" + "process\n", "import sock" + "et\n", "import url" + "lib\n",
                    "x = ev" + "al('1')\n", "ex" + "ec('1')\n", "import os\nos.sys" + "tem('x')\n",
                    "import import" + "lib\n", "__imp" + "ort__('os')\n", "comp" + "ile('', '', '')\n"):
            self.assertNotEqual(exec_hits(bad), set(), bad)

    def test_9_readme_states_what_is_new(self):
        flat = " ".join(read("README.md").split())
        for n in NEIGHBOURS:
            self.assertIn(n, flat, n)
        for s in ("absence", "robustness", "alert gone means fixed", "never permits",
                  "No combined-analyzer arm"):
            self.assertIn(s, flat, s)

    def test_10_missing_run_unmeasured_no_on_expiry_paper_unmeasured(self):
        for cid in F.UNMEASURED_IDS:
            r = run(cid)
            self.assertEqual((r["receipt"], r["measurement"]), (M.REFUSE, M.ON_UNMEASURED), cid)
            self.assertEqual(r["baseline"], M.FIXED, cid)
        self.assertEqual(run("U1-after-run-missing")["run"], "after")
        self.assertEqual(run("U2-before-run-missing")["run"], "before")
        self.assertEqual(run("U4-result-from-another-program")["reason"], M.RUN_UNBOUND)
        self.assertEqual(run("U5-result-for-a-harmless-input")["reason"], M.RUN_UNBOUND)
        u6 = run("U6-forged-after-record")
        self.assertEqual((u6["reason"], u6["run"], u6["exploit_after"]),
                         (M.RUN_UNREPRODUCED, "after", None))
        for name in CODE:
            self.assertNotIn("on_expiry", code_tokens(read(name)), name)
        self.assertEqual(M.paper_results(), M.ON_UNMEASURED)
        ev_ = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev_["measured_here"], "on_unmeasured")
        for c in ev_["claims"]:
            self.assertEqual((c["status"], c["measured_here"]), ("UNVERIFIED", "on_unmeasured"))


class TestAnalyzerAndExecutor(unittest.TestCase):

    def test_analyzer_table(self):
        s, c, sk = F.src, F.const, F.sink
        rows = [
            ([s("r"), sk("r")], ("body[1]",)),
            ([c("r", "a"), sk("r")], ()),
            ([s("r"), F.sanitize("t", "r"), sk("t")], ()),
            ([s("r"), c("a", "x"), F.concat("t", "a", "r"), sk("t")], ("body[3]",)),
            ([s("r"), F.pack("l", "r"), F.index("t", "l", 0), sk("t")], ("body[3]",)),
            ([s("r"), c("a", "x"), F.pack("l", "a", "r"), F.index("t", "l", 0), sk("t")],
             ("body[4]",)),
            ([s("r"), F.parse("u", "r"), F.assign("w", "u"), F.field("t", "w", "query"),
              sk("t")], ("body[4]",)),
            ([s("r"), F.parse("u", "r"), F.assign("w", "u"), F.field("t", "w", "path"),
              sk("t")], ()),
            ([s("r"), sk("r"), sk("r")], ("body[1]", "body[2]")),
        ]
        for body, want in rows:
            self.assertEqual(M.analyze(F.prog(body)), want, body)
        h = {"g": F.helper("x", [F.sink("x"), F.assign("y", "x")], "y")}
        p = F.prog([s("r"), F.call("a", "g", "r"), c("k", "1"), F.call("b", "g", "k")], h)
        self.assertEqual(M.analyze(p), ("helper g[0]",))

    def test_executor_semantics(self):
        s, c = F.src, F.const
        p = F.prog([s("r"), c("h", "/a/"), F.concat("t", "h", "r"), c("q", "?z=9"),
                    F.concat("w", "t", "q"), F.parse("u", "w"), F.field("p", "u", "path"),
                    F.field("v", "u", "query"), F.sink("p"), F.sink("v")])
        self.assertEqual(X.received(p, "E"), ["/a/E", "z=9"])
        p = F.prog([c("x", "no-mark"), F.parse("u", "x"), F.field("q", "u", "query"),
                    F.field("p", "u", "path"), F.sink("q"), F.sink("p")])
        self.assertEqual(X.received(p, "E"), ["", "no-mark"])
        self.assertEqual(X.received(F.prog([s("r"), F.sanitize("t", "r"), F.sink("t")]), "a'b"),
                         ["a&#39;b"])
        with self.assertRaises(X.ExecError):
            X.received(F.prog([{"op": "nope", "dst": "a"}]), "E")
        deep = {"g": F.helper("x", [F.call("y", "g", "x")], "y")}
        with self.assertRaises(X.ExecError):
            X.received(F.prog([s("r"), F.call("a", "g", "r")], deep), "E")
        two = F.prog([s("r"), c("k", "ok"), F.sink("k"), F.sink("r")])
        self.assertEqual(X.received(two, "E"), ["ok", "E"])
        self.assertTrue(X.execute(two, "E")["reached"])
        # Two sinks, the exploit at the first only.
        self.assertEqual(X.received(F.TWO_SINKS, F.EXPLOIT), [F.SELECT + F.EXPLOIT, "ok"])
        self.assertTrue(X.execute(F.TWO_SINKS, F.EXPLOIT)["reached"])
        self.assertIs(O._concrete(F.TWO_SINKS, F.EXPLOIT), True)
        c2 = {"case_id": "two", "family": "two-sinks", "exploit": F.EXPLOIT,
              "before": copy.deepcopy(F.ORIGINALS["O1"]), "after": copy.deepcopy(F.TWO_SINKS),
              "runs": F.runs_for(F.ORIGINALS["O1"], F.TWO_SINKS)}
        r = M.evaluate(c2)
        self.assertEqual((r["receipt"], r["reason"], r["alert_after"]),
                         (M.REFUSE, M.ALERT_SILENCED, False))
        self.assertEqual(r, O.reference(c2))
        self.assertEqual(X.execute(F.ORIGINALS["O1"], F.EXPLOIT),
                         X.execute(copy.deepcopy(F.ORIGINALS["O1"]), F.EXPLOIT))

    def test_digest_binds_exact_program(self):
        a = M.validate(case("A1-path-routing"))
        self.assertEqual(M.digest(a["after"]), X.fingerprint(F.SILENCING["A1-path-routing"][2]))
        p = copy.deepcopy(F.SILENCING["A1-path-routing"][2])
        p["body"][1]["value"] = "/item/x"
        self.assertNotEqual(X.fingerprint(p), M.digest(a["after"]))
        # Canonical JSON is ASCII-escaped even for non-ASCII constants.
        p = F.prog([F.const("x", "caf\u00e9"), F.sink("x")])
        canon = '{"body":[{"dst":"x","op":"const","value":"caf\\u00e9"},{"op":"sink","src":"x"}],"helpers":{}}'
        expected = hashlib.sha256(canon.encode("ascii")).hexdigest()
        self.assertEqual(M.digest(p), expected)
        self.assertEqual(X.fingerprint(p), expected)
        self.assertEqual(O._sha(p), expected)


class TestOracle(unittest.TestCase):

    def test_module_and_oracle_agree_on_all_fixtures(self):
        n = 0
        for name, c in F.cases().items():
            rec = M.evaluate(c)
            if rec["status"] != M.OK:
                continue
            self.assertEqual(rec, O.reference(case(name)), name)
            n += 1
        self.assertEqual(n, 20)
        for name in ("E4-exploit-not-declared", "E5-probe-as-exploit"):
            self.assertEqual(M.evaluate(case(name)), O.reference(case(name)), name)

    def test_module_and_oracle_agree_exhaustively(self):
        n = 0
        before = F.ORIGINALS["O1"]
        b_run = X.execute(before, F.EXPLOIT)
        for prog in space_programs():
            self.assertEqual(M.analyze(prog), O._labels(prog, True))
            self.assertEqual(M.analyze(prog, gap=False), O.labels_open(prog))
            self.assertIs(O._concrete(prog, F.EXPLOIT), X.execute(prog, F.EXPLOIT)["reached"])
            c = {"case_id": "s", "family": "space", "exploit": F.EXPLOIT,
                 "before": copy.deepcopy(before), "after": prog,
                 "runs": {"before": dict(b_run), "after": X.execute(prog, F.EXPLOIT)}}
            rec = M.evaluate(c)
            self.assertEqual(rec["status"], M.OK)
            self.assertEqual(rec, O.reference(c))
            n += 1
        g = 0
        for c in gate_space():
            self.assertEqual(M.evaluate(c), O.reference(c))
            g += 1
        self.assertEqual((n, g), (SPACE_SIZE, GATE_SPACE_SIZE))

    def test_oracle_is_a_separate_code_path(self):
        self.assertEqual(imports_of(read("oracle.py")), {"hashlib", "json"})
        self.assertEqual(function_names("alert_silence.py") & function_names("oracle.py"), set())


class TestInputs(unittest.TestCase):

    def cfg(self, c, detail=None):
        rec = M.evaluate(c)
        self.assertEqual((rec["status"], rec["receipt"]), (M.CONFIG_ERROR, M.REFUSE))
        self.assertEqual(rec["measurement"], M.ON_UNMEASURED)
        self.assertIsNone(rec["baseline"])
        if detail is not None:
            self.assertEqual(rec["detail"], detail)

    def test_case_shape(self):
        c = case("A1-path-routing")
        self.cfg(None, "case_invalid")
        self.cfg([c], "case_invalid")
        for f in M.CASE_FIELDS:
            x = copy.deepcopy(c)
            del x[f]
            self.cfg(x, "case_invalid")
        self.cfg(dict(c, extra=1), "case_invalid")
        for f in ("case_id", "family", "exploit"):
            self.cfg(dict(c, **{f: " "}), f + "_invalid")
            self.cfg(dict(c, **{f: ""}), f + "_invalid")
            self.cfg(dict(c, **{f: "x" * 65}), f + "_invalid")
        x = copy.deepcopy(c)
        x["runs"]["later"] = x["runs"]["after"]
        self.cfg(x, "runs_invalid")
        x = copy.deepcopy(c)
        x["runs"]["after"]["ran_on"] = "A" * 64
        self.cfg(x, "run_ran_on_invalid")
        x = copy.deepcopy(c)
        x["runs"]["after"]["ran_on"] = "a" * 63
        self.cfg(x, "run_ran_on_invalid")
        x = copy.deepcopy(c)
        x["runs"]["after"]["ran_on"] += "a"
        self.cfg(x, "run_ran_on_invalid")
        x = copy.deepcopy(c)
        del x["runs"]["after"]["reached"]
        self.cfg(x, "run_invalid")
        x = copy.deepcopy(c)
        x["after"]["helpers"]["bad-name"] = F.NORMALIZE
        self.cfg(x, "after_helpers_invalid")
        x = copy.deepcopy(c)
        x["before"]["body"] = [F.src("r")] * 33
        self.cfg(x, "before_body_invalid")

    def test_program_kinds(self):
        c = case("A1-path-routing")
        bodies = [
            ([F.sink("r")], "var_undefined"),
            ([F.src("r"), F.src("r")], "var_redefined"),
            ([F.src("r"), F.field("v", "r", "path")], "kind_mismatch"),
            ([F.src("r"), F.parse("u", "r"), F.sink("u")], "kind_mismatch"),
            ([F.src("r"), F.pack("l", "r"), F.index("v", "l", 1)], "kind_mismatch"),
            ([F.src("r"), F.index("v", "r", 0)], "kind_mismatch"),
            ([F.src("r"), F.call("v", "nope", "r")], "helper_unknown"),
            ([F.src("r"), F.concat("v", "r")], "instr_args_invalid"),
            ([F.src("r"), F.pack("v")], "instr_args_invalid"),
            ([F.src("r"), F.field("v", "r", "host")], "instr_name_invalid"),
            ([{"op": "eval", "dst": "r"}], "instr_op_invalid"),
            ([{"dst": "r"}], "instr_op_invalid"),
            ([{"op": "source", "dst": "r", "src": "r"}], "instr_fields_invalid"),
            ([F.src("1r")], "instr_dst_invalid"),
            ([F.src("R")], "instr_dst_invalid"),
            ([F.const("r", "x" * 65)], "instr_value_invalid"),
        ]
        for body, detail in bodies:
            x = copy.deepcopy(c)
            x["after"]["body"] = body
            self.cfg(x, detail)
        x = copy.deepcopy(c)
        x["after"]["helpers"] = {"g": F.helper("x", [F.call("y", "g", "x")], "y")}
        self.cfg(x, "helper_cycle")
        x = copy.deepcopy(c)
        x["after"]["helpers"] = {"g": F.helper("x", [F.parse("y", "x")], "y")}
        self.cfg(x, "helper_ret_invalid")
        x = copy.deepcopy(c)
        x["after"]["helpers"] = {"g": F.helper("x", [], "x"), "h": {"param": "x", "body": []}}
        self.cfg(x, "helper_invalid")
        x = copy.deepcopy(c)
        x["after"]["helpers"] = dict(("g%d" % i, F.helper("x", [], "x")) for i in range(9))
        self.cfg(x, "after_helpers_invalid")

    def test_exact_types_in_every_value_slot(self):
        c = case("A1-path-routing")
        for f in ("case_id", "family", "exploit"):
            self.cfg(dict(c, **{f: SubStr(c[f])}), f + "_invalid")
        for slot, detail in (("ran_on", "run_ran_on_invalid"), ("exploit", "run_exploit_invalid")):
            x = copy.deepcopy(c)
            x["runs"]["after"][slot] = SubStr(x["runs"]["after"][slot])
            self.cfg(x, detail)
            x = copy.deepcopy(c)
            x["runs"]["after"][slot] = EqStr(x["runs"]["after"][slot])
            self.cfg(x, detail)
        for bad in (1, 0, SubBool(), None, "true"):
            x = copy.deepcopy(c)
            x["runs"]["after"]["reached"] = bad
            self.cfg(x, "run_reached_invalid")
        # Instruction slots.
        idx = case("C1-list-detour")
        pos = [s["op"] for s in idx["after"]["body"]].index("index")
        for bad in (True, False, SubInt(0), CmpInt(0), 0.0, float("nan"), float("inf"),
                    -1, 4, "0", None):
            x = copy.deepcopy(idx)
            x["after"]["body"][pos]["at"] = bad
            self.cfg(x, "instr_at_invalid")
        for slot, detail in (("op", "instr_op_invalid"), ("dst", "instr_dst_invalid"),
                             ("src", "instr_src_invalid"), ("name", "instr_name_invalid")):
            x = copy.deepcopy(c)
            st = [s for s in x["after"]["body"] if s["op"] == "field"][0]
            st[slot] = SubStr(st[slot])
            self.cfg(x, detail)
            x = copy.deepcopy(c)
            st = [s for s in x["after"]["body"] if s["op"] == "field"][0]
            st[slot] = EqStr(st[slot])
            self.cfg(x, detail)
        x = copy.deepcopy(c)
        st = [s for s in x["after"]["body"] if s["op"] == "const"][0]
        st["value"] = SubStr(st["value"])
        self.cfg(x, "instr_value_invalid")
        for bad in (SubList(["h", "r"]), ("h", "r"), ["h", SubStr("r")], ["h", 1], "hr"):
            x = copy.deepcopy(c)
            st = [s for s in x["after"]["body"] if s["op"] == "concat"][0]
            st["args"] = bad
            self.cfg(x, "instr_args_invalid")
        for bad in (SubList(c["after"]["body"]), tuple(c["after"]["body"])):
            self.cfg(dict(c, after=dict(c["after"], body=bad)), "after_body_invalid")
        self.cfg(dict(c, after=SubDict(c["after"])), "after_invalid")
        self.cfg(dict(c, after=dict(c["after"], helpers=SubDict())), "after_helpers_invalid")
        x = copy.deepcopy(c)
        x["after"]["body"][0] = SubDict(x["after"]["body"][0])
        self.cfg(x, "instr_invalid")
        x = copy.deepcopy(case("B1-normalize-helper"))
        x["after"]["helpers"]["normalize"] = SubDict(x["after"]["helpers"]["normalize"])
        self.cfg(x, "helper_invalid")
        x = copy.deepcopy(case("B1-normalize-helper"))
        x["after"]["helpers"]["normalize"]["param"] = SubStr("x")
        self.cfg(x, "helper_invalid")
        x = copy.deepcopy(c)
        x["runs"] = SubDict(x["runs"])
        self.cfg(x, "runs_invalid")
        x = copy.deepcopy(c)
        x["runs"]["after"] = SubDict(x["runs"]["after"])
        self.cfg(x, "run_invalid")
        self.cfg(SubDict(c), "case_invalid")

    def test_run_guard_maps_internal_error(self):
        real = M.gate

        def boom(*args):
            raise RuntimeError("x")

        M.gate = boom
        try:
            self.cfg(case("X1-sanitize"), "internal_error")
        finally:
            M.gate = real

    def test_never_raises(self):
        c = case("A1-path-routing")
        for arg in [None, 1, {}, {"case_id": "x"}, [], "case", dict(c, before=[]),
                    dict(c, runs=None), dict(c, runs={"after": None}),
                    dict(c, after={"body": [None], "helpers": {}}),
                    dict(c, after={"body": [{1: 2}], "helpers": {}}),
                    dict(c, after={"body": [], "helpers": {"g": None}}),
                    dict(c, after={"body": [], "helpers": {1: 2}})]:
            r = M.evaluate(arg)
            self.assertEqual((r["status"], r["receipt"]), (M.CONFIG_ERROR, M.REFUSE), arg)

    def test_inputs_not_mutated(self):
        for n, c in F.cases().items():
            c0 = copy.deepcopy(c)
            rec = M.evaluate(c)
            if rec["status"] == M.OK:
                O.reference(c)
            self.assertEqual(c, c0, n)


class TestKeysAndSnapshot(unittest.TestCase):

    def cfg(self, c, detail):
        rec = M.evaluate(c)
        self.assertEqual((rec["status"], rec["detail"], rec["receipt"]),
                         (M.CONFIG_ERROR, detail, M.REFUSE))

    def test_spoofed_keys_at_every_level(self):
        """A key that hashes and compares like the real one is refused before
        its comparison ever runs; a hook that would rewrite the case into a
        passing one therefore never fires."""
        base = case("A2-parse-then-path")

        def make(level):
            x = copy.deepcopy(base)
            fired = []

            def hook(n):
                fired.append(n)
                x["runs"]["after"] = X.execute(F.FIXES["X1-sanitize"][2], F.EXPLOIT)

            def swap(d, key, detail):
                sp = Spoof(key, hook)
                d[sp] = d.pop(key)
                return sp, detail

            if level == "case":
                sp, detail = swap(x, "after", "case_invalid")
            elif level == "program":
                sp, detail = swap(x["after"], "body", "after_invalid")
            elif level == "instr":
                sp, detail = swap(x["after"]["body"][1], "src", "instr_invalid")
            elif level == "instr_op":
                sp, detail = swap(x["after"]["body"][1], "op", "instr_invalid")
            elif level == "helpers":
                x["after"]["helpers"]["g"] = F.helper("x", [], "x")
                sp, detail = swap(x["after"]["helpers"], "g", "after_helpers_invalid")
            elif level == "helper":
                x["after"]["helpers"]["g"] = F.helper("x", [], "x")
                sp, detail = swap(x["after"]["helpers"]["g"], "ret", "helper_invalid")
            elif level == "runs":
                sp, detail = swap(x["runs"], "after", "runs_invalid")
            else:
                sp, detail = swap(x["runs"]["after"], "reached", "run_invalid")
            return x, sp, fired, detail

        for level in ("case", "program", "instr", "instr_op", "helpers", "helper", "runs",
                      "run"):
            x, sp, fired, detail = make(level)
            self.cfg(x, detail)
            self.assertEqual((sp.n, fired), (0, []), level)

    def test_fixture_colliding_key_case(self):
        rec = run("E3-colliding-run-key")
        self.assertEqual((rec["status"], rec["detail"]), (M.CONFIG_ERROR, "runs_invalid"))

    def test_non_str_keys_rejected_at_every_level(self):
        base = case("B1-normalize-helper")
        for path, detail in (((), "case_invalid"), (("after",), "after_invalid"),
                             (("after", "body", 0), "instr_invalid"),
                             (("after", "helpers"), "after_helpers_invalid"),
                             (("after", "helpers", "normalize"), "helper_invalid"),
                             (("runs",), "runs_invalid"), (("runs", "after"), "run_invalid")):
            for key in (1, None, b"after", ("after",), True):
                x = copy.deepcopy(base)
                d = x
                for p in path:
                    d = d[p]
                d[key] = 1
                self.cfg(x, detail)

    def test_str_subclass_keys_rejected_at_every_level(self):
        """An existing key replaced by a str subclass of the same text (it
        hashes and compares equal) is refused at every level."""
        base = case("B1-normalize-helper")
        for path, key, detail in (((), "after", "case_invalid"),
                                  (("after",), "body", "after_invalid"),
                                  (("after", "body", 0), "op", "instr_invalid"),
                                  (("after", "helpers"), "normalize", "after_helpers_invalid"),
                                  (("after", "helpers", "normalize"), "param", "helper_invalid"),
                                  (("runs",), "after", "runs_invalid"),
                                  (("runs", "after"), "reached", "run_invalid")):
            x = copy.deepcopy(base)
            d = x
            for p in path:
                d = d[p]
            d[SubStr(key)] = d.pop(key)
            self.assertEqual([type(k) for k in d if k == key], [SubStr], path)
            self.cfg(x, detail)

    def test_snapshot_shares_nothing_with_caller(self):
        c = case("B2-nested-helpers")
        snap = M.validate(c)
        theirs = containers(c, set())
        ours = containers(snap, set())
        self.assertEqual(theirs & ours, set())
        for name in ("before", "after"):
            for st in snap[name]["body"]:
                for v in st.values():
                    self.assertIn(type(v), (str, int, tuple))

    def test_logic_sees_only_the_snapshot(self):
        """Once validated, rewriting the caller's case (here: swapping in a
        passing result for the fix) changes nothing."""
        for n in F.SILENCING_IDS + F.UNMEASURED_IDS:
            c = case(n)
            clean = M.evaluate(copy.deepcopy(c))
            real = M.analyze
            calls = []

            def meddle(program, gap=True):
                if not calls:
                    c["runs"] = {"before": X.execute(F.ORIGINALS["O1"], F.EXPLOIT),
                                 "after": X.execute(F.FIXES["X1-sanitize"][2], F.EXPLOIT)}
                    c["after"]["body"][:] = F.FIXES["X1-sanitize"][2]["body"]
                    c["exploit"] = "other"
                calls.append(1)
                return real(program, gap)

            M.analyze = meddle
            try:
                rec = M.evaluate(c)
            finally:
                M.analyze = real
            self.assertEqual(rec, clean, n)
            self.assertNotEqual(rec["receipt"], M.FIXED, n)


# Exploits a case might pick for itself so that an honest run of a
# silencing rewrite passes (or that the parser splits), plus a quote-free one.
CHOSEN_EXPLOITS = (F.HARMLESS, "x?" + F.EXPLOIT, "?" + F.EXPLOIT, F.SPLIT_OFF, "42",
                   "1 OR 1=1")


def honest(before, after, exploit):
    return {"case_id": "h", "family": "honest", "exploit": exploit,
            "before": copy.deepcopy(before), "after": copy.deepcopy(after),
            "runs": F.runs_for(before, after, exploit)}


class TestDeclaredExploit(unittest.TestCase):

    def test_case_cannot_pick_its_exploit(self):
        n = 0
        for cid, (orig, _, after) in F.SILENCING.items():
            before = F.ORIGINALS[orig]
            r = M.evaluate(honest(before, after, F.EXPLOIT))
            self.assertEqual((r["receipt"], r["reason"]), (M.REFUSE, M.ALERT_SILENCED), cid)
            for ex in CHOSEN_EXPLOITS:
                c = honest(before, after, ex)
                r = M.evaluate(c)
                self.assertEqual((r["status"], r["detail"], r["receipt"]),
                                 (M.CONFIG_ERROR, "exploit_undeclared", M.REFUSE), (cid, ex))
                self.assertEqual(r, O.reference(c), (cid, ex))
                n += 1
        self.assertEqual(n, len(F.SILENCING) * len(CHOSEN_EXPLOITS))

    def test_split_off_payload_and_promoted_probe(self):
        """E4: A2 with the payload plus "?" (the sink gets the whole payload,
        yet the honest run says the case exploit is gone). E5: U5's probe
        moved into the case's own exploit field."""
        e4 = case("E4-exploit-not-declared")
        self.assertEqual(e4["exploit"], F.SPLIT_OFF)
        self.assertFalse(e4["runs"]["after"]["reached"])
        self.assertTrue(e4["runs"]["before"]["reached"])
        self.assertEqual(X.received(e4["after"], F.SPLIT_OFF), [F.SELECT + F.EXPLOIT])
        e5 = case("E5-probe-as-exploit")
        self.assertEqual(e5["exploit"], F.HARMLESS)
        self.assertEqual((e5["runs"]["before"]["reached"], e5["runs"]["after"]["reached"]),
                         (True, False))
        for c in (e4, e5):
            r = M.evaluate(c)
            self.assertEqual((r["status"], r["detail"], r["receipt"], r["measurement"]),
                             (M.CONFIG_ERROR, "exploit_undeclared", M.REFUSE, M.ON_UNMEASURED))
        # The same programs and runs with the declared exploit are judged.
        u5 = run("U5-result-for-a-harmless-input")
        self.assertEqual(u5["reason"], M.RUN_UNBOUND)


class TestReproduction(unittest.TestCase):

    def forged(self, before, after, which, reached):
        c = honest(before, after, F.EXPLOIT)
        c["runs"][which] = {"ran_on": M.digest(c[which]), "exploit": F.EXPLOIT,
                            "reached": reached}
        return c

    def test_forged_records_refused(self):
        n = 0
        for cid, (orig, _, after) in F.SILENCING.items():
            c = self.forged(F.ORIGINALS[orig], after, "after", False)
            r = M.evaluate(c)
            self.assertEqual((r["receipt"], r["reason"], r["run"], r["measurement"]),
                             (M.REFUSE, M.RUN_UNREPRODUCED, "after", M.ON_UNMEASURED), cid)
            self.assertEqual((r["exploit_before"], r["exploit_after"]), (True, None), cid)
            self.assertEqual(r, O.reference(c), cid)
            n += 1
        self.assertEqual(n, 8)
        # A forged "reached" on the before program, and a forged failure on
        # a true fix, are refused the same way.
        c = self.forged(F.ORIGINALS["O1"], F.FIXES["X1-sanitize"][2], "before", False)
        r = M.evaluate(c)
        self.assertEqual((r["reason"], r["run"], r["exploit_before"]),
                         (M.RUN_UNREPRODUCED, "before", None))
        self.assertEqual(r, O.reference(c))
        c = self.forged(F.ORIGINALS["O1"], F.FIXES["X1-sanitize"][2], "after", True)
        r = M.evaluate(c)
        self.assertEqual((r["reason"], r["run"]), (M.RUN_UNREPRODUCED, "after"))
        self.assertEqual(r, O.reference(c))
        # An honest record of the same shape is accepted.
        r = M.evaluate(self.forged(F.ORIGINALS["O1"], F.FIXES["X1-sanitize"][2], "after", False))
        self.assertEqual(r["receipt"], M.FIXED)

    def test_rerun_runs_the_snapshot(self):
        """evaluate() calls the executor once per program, on its own
        snapshot (never the caller's objects), with the case exploit."""
        real = X.execute
        seen = []

        def spy(program, exploit):
            seen.append((program, exploit))
            return real(program, exploit)

        c = case("X1-sanitize")
        X.execute = spy
        try:
            r = M.evaluate(c)
        finally:
            X.execute = real
        self.assertEqual(r["receipt"], M.FIXED)
        self.assertEqual(len(seen), 2)
        mine = containers(c, set())
        for (program, exploit), name in zip(seen, ("before", "after")):
            self.assertEqual(exploit, F.EXPLOIT)
            self.assertIs(type(program["body"]), tuple)
            self.assertEqual(X.fingerprint(program), X.fingerprint(c[name]))
            self.assertEqual(containers(program, set()) & mine, set())

    def test_rerun_failures_refused(self):
        real = X.execute

        def boom(program, exploit):
            raise X.ExecError("x")

        def as_int(program, exploit):
            got = real(program, exploit)
            got["reached"] = int(got["reached"])
            return got

        def eq_digest(program, exploit):
            got = real(program, exploit)
            got["ran_on"] = EqStr(got["ran_on"])
            return got

        def eq_exploit(program, exploit):
            got = real(program, exploit)
            got["exploit"] = EqStr(got["exploit"])
            return got

        def other_digest(program, exploit):
            got = real(program, exploit)
            got["ran_on"] = "0" * 64
            return got

        def other_exploit(program, exploit):
            got = real(program, exploit)
            got["exploit"] = F.HARMLESS
            return got

        for fake in (boom, as_int, eq_digest, eq_exploit, other_digest, other_exploit):
            X.execute = fake
            try:
                for cid in F.FIX_IDS + F.SILENCING_IDS:
                    r = run(cid)
                    self.assertEqual((r["status"], r["receipt"], r["reason"], r["run"],
                                      r["measurement"]),
                                     (M.OK, M.REFUSE, M.RUN_UNREPRODUCED, "before",
                                      M.ON_UNMEASURED), (fake.__name__, cid))
                    self.assertEqual((r["exploit_before"], r["exploit_after"]), (None, None))
            finally:
                X.execute = real


class TestFixtures(unittest.TestCase):

    def test_labels_match(self):
        for cid, c in F.cases().items():
            self.assertEqual(F.label_of(M.evaluate(c)), F.LABELS[cid], cid)

    def test_fixture_invariants(self):
        cs = F.cases()
        self.assertEqual(sorted(cs), sorted(F.LABELS))
        self.assertEqual(len(cs), 25)
        groups = (F.SILENCING_IDS + F.CONTROL_IDS + F.FIX_IDS + F.UNMEASURED_IDS
                  + F.CONFIG_IDS)
        self.assertEqual(sorted(groups), sorted(cs))
        for n, c in cs.items():
            self.assertEqual(c["case_id"], n)
        self.assertNotIn("'", "".join(s.get("value", "") for p in F.ORIGINALS.values()
                                      for s in p["body"]))
        self.assertNotIn("?", F.EXPLOIT)
        self.assertIn("'", F.EXPLOIT)
        self.assertEqual(M.DECLARED_EXPLOITS, (F.EXPLOIT,))
        self.assertEqual(O.ATTACK, F.EXPLOIT)
        for e in M.DECLARED_EXPLOITS:
            self.assertIs(type(e), str)
            self.assertNotIn("?", e)
        for e in (F.HARMLESS, F.SPLIT_OFF):
            self.assertNotIn(e, M.DECLARED_EXPLOITS)

    def test_fixtures_return_copies(self):
        c = F.cases()
        c["A1-path-routing"]["runs"].clear()
        c["X1-sanitize"]["after"]["body"].pop()
        fresh = F.cases()
        self.assertEqual(sorted(fresh["A1-path-routing"]["runs"]), ["after", "before"])
        self.assertEqual(run("X1-sanitize")["receipt"], M.FIXED)
        lab = F.labels()
        lab["X1-sanitize"] = None
        self.assertIsNotNone(F.LABELS["X1-sanitize"])

    def test_determinism(self):
        a, b = F.summary(), F.summary()
        self.assertEqual(a, b)
        self.assertEqual((a[3], a[4]), (20, 20))


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

    def test_imports_stdlib_only(self):
        for name in PY:
            for m in imports_of(read(name)):
                self.assertIn(m, STDLIB_PERMITTED, (name, m))
        for name, want in CODE_IMPORTS.items():
            self.assertEqual(imports_of(read(name)), want, name)

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
        bullets = [line for line in lines if line.startswith("- ")]
        self.assertEqual(bullets[-1], rows[0])
        if LAYOUT == "flat":
            self.assertEqual(len(bullets), len(MAIN_ROW_PREFIXES) + 1)
            for prefix, line in zip(MAIN_ROW_PREFIXES, bullets):
                self.assertTrue(line.startswith(prefix))
                self.assertEqual(hashlib.sha256(line.encode("utf-8")).hexdigest(),
                                 MAIN_ROW_SHA256[prefix])

    def test_no_paper_claims_outside_evidence(self):
        for name in PY + ("README.md", "NOTICE", DAY):
            self.assertIsNone(PAPER_PAT.search(scan_text(name, read(name))), name)
        self.assertIsNotNone(PAPER_PAT.search(read("paper_evidence.json")))

    def test_readme_credits_differentiation_and_limits(self):
        flat = " ".join(read("README.md").split())
        ev_ = json.loads(read("paper_evidence.json"))
        self.assertIn(ev_["paper"]["title"], flat)
        for author in ev_["paper"]["authors"]:
            self.assertIn(author, flat)
        for s in ("**Top** method sketch", "not a reproduction", "UNVERIFIED",
                  "on_unmeasured", "paper_evidence.json", "## Limits", "## Builder reflection",
                  "Ludex", "non-exclusive", "python3 -B -m unittest", "python3 -B mutants.py",
                  "No human data", "no on_expiry", "one declared modelling gap"):
            self.assertIn(s, flat, s)
        notice = " ".join(read("NOTICE").split())
        for s in (ev_["paper"]["title"], "arXiv:2611.17123", "https://arxiv.org/abs/2611.17123",
                  "non-exclusive", "Clean-room", "not read", "No human data"):
            self.assertIn(s, notice, s)
        for author in ev_["paper"]["authors"]:
            self.assertIn(author, notice)

    def test_evidence_shape(self):
        ev_ = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev_["paper"]["arxiv_id"], "2611.17123")
        self.assertIn("nonexclusive-distrib/1.0", ev_["paper"]["licence"])
        self.assertFalse(ev_["paper"]["pdf_read"])
        self.assertFalse(ev_["code"]["linked_in_abstract"])
        self.assertEqual(len(ev_["claims"]), 7)
        for c in ev_["claims"]:
            self.assertEqual(len(c["quote"]), c["length"], c["id"])
            self.assertEqual(c["status"], "UNVERIFIED", c["id"])
        quotes = " ".join(c["quote"] for c in ev_["claims"])
        self.assertIsNotNone(PAPER_PAT.search(quotes))

    def test_quotes_exact_in_sources(self):
        if not SOURCES:
            self.skipTest("W24ASF_SOURCES not set")
        ev_ = json.loads(read("paper_evidence.json"))
        src = ev_["sources"][0]
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
        for c in ev_["claims"]:
            self.assertEqual(text.count(c["quote"]), 1, c["id"])
            self.assertEqual(text[c["offset"]:c["offset"] + c["length"]], c["quote"], c["id"])


if __name__ == "__main__":
    unittest.main()
