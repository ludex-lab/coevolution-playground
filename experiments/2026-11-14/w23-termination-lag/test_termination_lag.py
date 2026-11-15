"""Tests for the w23-termination-lag method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
The quote check reads the source copy named in paper_evidence.json from the
directories listed in $W23TERMLAG_SOURCES (os.pathsep separated). There is
no default: when the variable is unset, or the file is absent, that check
is skipped.

Done-when mapping (Lab Dig 2 Wave23, Top: termination lag):
  (a) test_a_first_passing_patch_recorded_and_lag_counted
  (b) test_b_later_breaking_edit_refused_or_scored_fail
  (c) test_c_stop_at_first_pass_leaves_solution_correct
  (d) test_d_no_model_and_paper_numbers_on_unmeasured
  wait is not permission: test_wait_after_first_pass_never_permits_breaking_edit
  honest baseline: test_baseline_misses_mid_run_correctness_and_regressions
"""

import ast
import copy
import hashlib
import itertools
import json
import os
import re
import unittest

import fixtures as F
import oracle as O
import termination_lag as M

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W23TERMLAG_SOURCES")
SLUG = "w23-termination-lag"
DAY_HEADER = "# experiments/2026-11-14\n"
ROW_START = "- [%s](%s/): " % (SLUG, SLUG)
ROW_PREFIX = "- [%s](" % SLUG
ROW_END = ("(Top method sketch of [arXiv 2611.14960](https://arxiv.org/abs/2611.14960);"
           " not a reproduction)")
FOOTER = "Do not merge experiment PRs without Ork review."
# The existing main row (#130), retained byte for byte; checked by hash.
MAIN_ROW_PREFIX = "- [mb-boundary-vs-judge](mb-boundary-vs-judge/): "
MAIN_ROW_SHA256 = "aae8fb872d0cb1de22745e358bc832d84e4c71ab3a77e5b2589a88fa68b0e720"


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
CODE = ("termination_lag.py", "oracle.py", "fixtures.py")
PY = CODE + ("test_termination_lag.py", "mutants.py")
ALL = PY + ("README.md", "NOTICE", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
STDLIB_PERMITTED = {"ast", "copy", "hashlib", "io", "itertools", "json", "os", "re", "sys",
                    "unittest", "termination_lag", "oracle", "fixtures",
                    "test_termination_lag"}
CODE_IMPORTS = {"termination_lag.py": set(), "oracle.py": set(),
                "fixtures.py": {"copy", "termination_lag", "oracle"}}
NO_GO_TOKENS = ("vo" + "te", "ensem" + "ble", "major" + "ity", "api" + "_key", "api" + "key",
                "open" + "ai", "anthro" + "pic", "envi" + "ron", "http" + "://",
                "https" + "://", "sub" + "process", "sock" + "et", "url" + "lib",
                "ran" + "dom", "sle" + "ep", "time" + "out", "expi" + "r", "dead" + "line",
                "sql" + "ite", "hm" + "ac", "thre" + "ad", "led" + "ger")
ABS_PATHS = ("/" + "workspace", "/" + "tmp", "/" + "home")
MARKERS = ("<" * 7, "=" * 7, ">" * 7)
PAPER_PAT = re.compile(r"\d+\s*-+\s*\d+\s*%|\d+-" + r"-\d+|\b(?:3" + "8|8" + "2|3" + "5|3"
                       + "7|5" + "4|6" + r"0|1)\s*%|five " + "models|two agent "
                       + "frameworks|three SWE-" + "bench|Qw" + "en|Lag" + "una")


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


def tr(name):
    return F.episodes()[name]


def run(name):
    return M.evaluate(tr(name))


def mod_tuple(r):
    """Module record in the oracle's tuple order."""
    return (r["first_pass"], r["lag"], r["regressions"], r["baseline"]["verdict"],
            r["rule"]["verdict"], r["rule"]["protected_from"], r["rule"]["refused"],
            r["stop_first"]["verdict"], r["stop_first"]["steps_run"])


def edit(name, content):
    return {"kind": "edit", "file": name, "content": content}


class SubStr(str):
    pass


class SubList(list):
    pass


class SubDict(dict):
    pass


class Spoof:
    """A non-str key that hashes and compares equal to the str `name`.

    Every comparison counts in n; hook(n) runs on the n-th one (the lever
    for the A1 / A2b / A3 style attacks).
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
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0])
    return names


def containers(obj, out):
    """Collect the id of every dict, list and tuple reachable from obj."""
    if isinstance(obj, (dict, list, tuple)):
        out.add(id(obj))
        items = list(obj.keys()) + list(obj.values()) if isinstance(obj, dict) else obj
        for x in items:
            containers(x, out)
    return out


# Exhaustive short traces: three small worlds, every step sequence up to a length.
WORLDS = (
    ({"a": "bug", "b": "x"}, [{"file": "a", "accept": ["good", "alt"]}],
     [edit("a", "good"), edit("a", "alt"), edit("a", "bad"), edit("a", "bug"),
      edit("b", "y"), {"kind": "verify"}, {"kind": "explore"}], 5),
    ({"a": "bug", "b": "bug"}, [{"file": "a", "accept": ["fix"]},
                                {"file": "b", "accept": ["fix"]}],
     [edit("a", "fix"), edit("a", "bug"), edit("b", "fix"), edit("b", "bug"),
      {"kind": "verify"}], 5),
    ({}, [{"file": "n", "accept": ["ok"]}],
     [edit("n", "ok"), edit("n", "no"), {"kind": "explore"}], 4),
)
EXHAUSTIVE_COUNT = sum(sum(len(alpha) ** k for k in range(1, depth + 1))
                       for _, _, alpha, depth in WORLDS)


def short_traces():
    n = 0
    for initial, checks, alpha, depth in WORLDS:
        for k in range(1, depth + 1):
            for combo in itertools.product(range(len(alpha)), repeat=k):
                n += 1
                yield {"trajectory_id": "x%d" % n, "initial": copy.deepcopy(initial),
                       "checks": copy.deepcopy(checks),
                       "steps": [copy.deepcopy(alpha[i]) for i in combo]}


class TestDoneWhen(unittest.TestCase):

    def test_a_first_passing_patch_recorded_and_lag_counted(self):
        for name, lab in F.LABELS.items():
            r = run(name)
            self.assertEqual((r["first_pass"], r["lag"]), lab[:2], name)
            self.assertEqual(r["rule"]["protected_from"], lab[0], name)
            if lab[0] is not None:
                self.assertEqual(r["lag"], r["steps"] - 1 - r["first_pass"], name)
        r = run("d-late-solve")
        self.assertEqual((r["first_pass"], r["lag"], r["steps"]), (3, 1, 5))
        r = run("c-partial-then-full")
        self.assertEqual((r["first_pass"], r["lag"]), (2, 1))
        self.assertEqual(run("d-first-edit-stop")["lag"], 0)
        self.assertIsNone(run("d-never-solved")["first_pass"])
        self.assertIsNone(run("d-never-solved")["lag"])

    def test_b_later_breaking_edit_refused_or_scored_fail(self):
        planted = [n for n, lab in F.LABELS.items() if lab[2]]
        self.assertEqual(len(planted), 6)
        for name in planted:
            r = run(name)
            lab = F.LABELS[name]
            self.assertEqual(r["rule"]["refused"], lab[4], name)
            self.assertEqual(r["rule"]["verdict"], M.PASS, name)
            for i in r["rule"]["refused"]:
                self.assertEqual(r["rule"]["decisions"][i], M.REFUSE, name)
            # Compare run that applies everything: the regression is scored.
            self.assertEqual(r["rule"]["regressions"], lab[2], name)
            self.assertEqual(r["regressions"], lab[2], name)
        for name in ("d-undo-at-end", "d-revert-to-bug", "d-undo-then-wrong-again",
                     LONG_WAIT_NAME, "c-full-then-undo-one"):
            self.assertEqual(run(name)["baseline"]["verdict"], M.FAIL, name)

    def test_c_stop_at_first_pass_leaves_solution_correct(self):
        for name, lab in F.LABELS.items():
            s = run(name)["stop_first"]
            if lab[0] is None:
                self.assertEqual(s["verdict"], M.FAIL, name)
                self.assertEqual(s["steps_run"], len(F.EPISODES[name]["steps"]), name)
            else:
                self.assertEqual(s, {"verdict": M.PASS, "steps_run": lab[0] + 1}, name)
        self.assertEqual(run("d-first-edit-stop")["rule"]["decisions"], (M.PERMIT,))

    def test_d_no_model_and_paper_numbers_on_unmeasured(self):
        self.assertEqual(M.paper_results(), M.ON_UNMEASURED)
        for name, permitted in CODE_IMPORTS.items():
            self.assertEqual(imports_of(read(name)), permitted, name)
        for name in PY:
            self.assertLessEqual(imports_of(read(name)), STDLIB_PERMITTED, name)
        for name in CODE:
            toks = code_tokens(read(name))
            for t in NO_GO_TOKENS:
                self.assertNotIn(t, toks, (name, t))
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["measured_here"], "on_unmeasured")
        for c in ev["claims"]:
            self.assertEqual((c["status"], c["measured_here"]), ("UNVERIFIED", "on_unmeasured"))

    def test_wait_after_first_pass_never_permits_breaking_edit(self):
        r = run(LONG_WAIT_NAME)
        self.assertEqual(r["rule"]["refused"], (8,))
        self.assertEqual(r["rule"]["verdict"], M.PASS)
        for waits in range(0, 41):
            for filler in ({"kind": "verify"}, {"kind": "explore"}):
                t = F.dates("w", [edit(F.D_FILE, F.D_GOOD)] + [dict(filler)] * waits
                            + [edit(F.D_FILE, F.D_BAD)])
                r = M.evaluate(t)
                self.assertEqual(r["rule"]["refused"], (waits + 1,), waits)
                self.assertEqual(r["rule"]["verdict"], M.PASS, waits)
                self.assertEqual(r["lag"], waits + 1, waits)

    def test_baseline_misses_mid_run_correctness_and_regressions(self):
        s = F.summary()
        self.assertEqual((s["solved"], s["base_missed_solved"], s["base_silent_regression"]),
                         (13, 5, 1))
        self.assertEqual(s["base_vs_solved"], 10)
        self.assertEqual(s["rule_vs_solved"], 15)
        r = run("d-undo-then-refix")
        self.assertEqual(r["baseline"], {"verdict": M.PASS})
        self.assertEqual(r["rule"]["regressions"], (1,))
        for name in F.EPISODES:
            self.assertEqual(sorted(run(name)["baseline"]), ["verdict"], name)
            self.assertEqual(run(name)["baseline"]["verdict"], F.LABELS[name][3], name)


LONG_WAIT_NAME = F.LONG_WAIT


class TestRules(unittest.TestCase):

    def test_alternative_correct_patch_is_not_a_regression(self):
        r = run("d-alt-correct")
        self.assertEqual((r["regressions"], r["rule"]["refused"]), ((), ()))
        self.assertEqual(r["rule"]["decisions"], (M.PERMIT,) * 4)

    def test_unrelated_edit_after_pass_permitted(self):
        r = run("c-unrelated-edit-after")
        self.assertEqual(r["rule"]["decisions"], (M.PERMIT,) * 3)
        self.assertEqual(r["rule"]["verdict"], M.PASS)

    def test_churn_before_first_pass_is_not_protected(self):
        r = run("c-churn-before-solve")
        self.assertEqual((r["first_pass"], r["regressions"], r["rule"]["refused"]), (3, (), ()))

    def test_refused_edit_does_not_change_state(self):
        r = run("d-undo-then-wrong-again")
        self.assertEqual(r["rule"]["refused"], (1, 2))
        self.assertEqual(r["regressions"], (1,))
        r = run("d-undo-then-refix")
        self.assertEqual(r["rule"]["decisions"], (M.PERMIT, M.REFUSE, M.PERMIT, M.PERMIT))

    def test_decisions_shape(self):
        for name in F.EPISODES:
            r = run(name)
            d = r["rule"]["decisions"]
            self.assertEqual(len(d), r["steps"], name)
            self.assertEqual(tuple(i for i, x in enumerate(d) if x == M.REFUSE),
                             r["rule"]["refused"], name)
            for i, s in enumerate(F.EPISODES[name]["steps"]):
                if s["kind"] != M.EDIT:
                    self.assertEqual(d[i], M.PERMIT, name)

    def test_baseline_reads_only_the_final_state(self):
        a = F.dates("a", [edit(F.D_FILE, F.D_BAD)])
        b = F.dates("b", [edit(F.D_FILE, F.D_GOOD), {"kind": "verify"}, edit(F.D_FILE, F.D_BAD)])
        self.assertEqual(M.evaluate(a)["baseline"], M.evaluate(b)["baseline"])
        self.assertNotEqual(M.evaluate(a)["rule"], M.evaluate(b)["rule"])

    def test_initial_passing_is_config_error(self):
        t = F.dates("p", [{"kind": "verify"}])
        t["initial"][F.D_FILE] = F.D_GOOD
        r = M.evaluate(t)
        self.assertEqual((r["status"], r["detail"]), (M.CONFIG_ERROR, "initial_passes"))

    def test_missing_checked_file_fails(self):
        t = F.dates("m", [edit("other.py", "x")])
        del t["initial"][F.D_FILE]
        r = M.evaluate(t)
        self.assertEqual((r["status"], r["first_pass"]), (M.OK, None))

    def test_no_timeout_in_design(self):
        for name in ("termination_lag.py", "oracle.py"):
            toks = code_tokens(read(name))
            for t in ("on_" + "expiry", "time" + "out", "expi" + "r", "dead" + "line"):
                self.assertNotIn(t, toks, name)
        self.assertIn("no timeout", " ".join(read("README.md").split()))


class TestOracle(unittest.TestCase):

    def test_module_and_oracle_agree_on_all_fixtures(self):
        for name, (m, o) in F.run_all().items():
            self.assertEqual(mod_tuple(m), o, name)
        self.assertEqual(F.summary()["oracle_agree"], 15)

    def test_module_and_oracle_agree_exhaustively(self):
        n = 0
        skipped = 0
        for t in short_traces():
            r = M.evaluate(copy.deepcopy(t))
            n += 1
            if r["status"] == M.CONFIG_ERROR:
                self.assertEqual(r["detail"], "initial_passes")
                skipped += 1
                continue
            self.assertEqual(mod_tuple(r), O.reference(t), t["steps"])
        self.assertEqual(n, EXHAUSTIVE_COUNT)
        self.assertEqual(skipped, 0)

    def test_oracle_is_a_separate_code_path(self):
        src = read("oracle.py")
        self.assertEqual(imports_of(src), set())
        toks = code_tokens(src)
        self.assertNotIn("termination_lag", toks)
        mod_funcs = set(n.name for n in ast.walk(ast.parse(read("termination_lag.py")))
                        if isinstance(n, ast.FunctionDef))
        orc_funcs = set(n.name for n in ast.walk(ast.parse(src))
                        if isinstance(n, ast.FunctionDef))
        self.assertEqual(mod_funcs & orc_funcs, set())


class TestInputs(unittest.TestCase):

    def cfg(self, t, detail=None):
        r = M.evaluate(t)
        self.assertEqual(r["status"], M.CONFIG_ERROR, detail)
        if detail is not None:
            self.assertEqual(r["detail"], detail)
        for k in ("baseline", "rule", "stop_first", "first_pass", "lag"):
            self.assertIsNone(r[k])
        return r

    def test_trajectory_shape(self):
        self.cfg(None, "trajectory_not_dict")
        self.cfg([], "trajectory_not_dict")
        t = tr("d-undo-at-end")
        del t["checks"]
        self.cfg(t, "trajectory_fields_invalid")
        t = tr("d-undo-at-end")
        t["extra"] = 1
        self.cfg(t, "trajectory_fields_invalid")
        for bad in ("", "  ", 3, None):
            t = tr("d-undo-at-end")
            t["trajectory_id"] = bad
            self.cfg(t, "trajectory_id_invalid")
        t = tr("d-undo-at-end")
        t["initial"] = []
        self.cfg(t, "initial_invalid")
        t = tr("d-undo-at-end")
        t["initial"][" "] = "x"
        self.cfg(t, "initial_value_invalid")
        t = tr("d-undo-at-end")
        t["initial"]["f"] = 1
        self.cfg(t, "initial_value_invalid")
        t = tr("d-undo-at-end")
        t["checks"] = []
        self.cfg(t, "checks_invalid")
        t = tr("d-undo-at-end")
        t["checks"].append("x")
        self.cfg(t, "check_invalid")
        t = tr("d-undo-at-end")
        t["checks"][0]["extra"] = 1
        self.cfg(t, "check_fields_invalid")
        t = tr("d-undo-at-end")
        t["checks"].append(copy.deepcopy(t["checks"][0]))
        self.cfg(t, "check_file_invalid")
        t = tr("d-undo-at-end")
        t["checks"][0]["accept"] = []
        self.cfg(t, "check_accept_invalid")
        t = tr("d-undo-at-end")
        t["checks"][0]["accept"].append(F.D_GOOD)
        self.cfg(t, "check_accept_invalid")
        t = tr("d-undo-at-end")
        t["steps"] = []
        self.cfg(t, "steps_invalid")
        t = tr("d-undo-at-end")
        t["steps"].append("verify")
        self.cfg(t, "step_invalid")
        t = tr("d-undo-at-end")
        t["steps"].append({"file": "a"})
        self.cfg(t, "step_fields_invalid")
        t = tr("d-undo-at-end")
        t["steps"].append({"kind": "revert"})
        self.cfg(t, "step_kind_unknown")
        t = tr("d-undo-at-end")
        t["steps"].append({"kind": "verify", "file": "a"})
        self.cfg(t, "step_fields_invalid")
        t = tr("d-undo-at-end")
        t["steps"].append({"kind": "edit", "file": "a"})
        self.cfg(t, "step_fields_invalid")
        t = tr("d-undo-at-end")
        t["steps"].append(edit("", "x"))
        self.cfg(t, "step_edit_invalid")
        t = tr("d-undo-at-end")
        t["steps"].append(edit("a", None))
        self.cfg(t, "step_edit_invalid")

    def test_exact_types_in_every_value_slot(self):
        def check(mutate, detail):
            t = tr("d-undo-at-end")
            mutate(t)
            self.cfg(t, detail)

        check(lambda t: t.__setitem__("trajectory_id", SubStr("x")), "trajectory_id_invalid")
        check(lambda t: t["initial"].__setitem__(F.D_FILE, SubStr(F.D_BUG)),
              "initial_value_invalid")
        check(lambda t: t.__setitem__("initial", SubDict(t["initial"])), "initial_invalid")
        check(lambda t: t.__setitem__("checks", SubList(t["checks"])), "checks_invalid")
        check(lambda t: t.__setitem__("checks", tuple(t["checks"])), "checks_invalid")
        check(lambda t: t["checks"].__setitem__(0, SubDict(t["checks"][0])), "check_invalid")
        check(lambda t: t["checks"][0].__setitem__("file", SubStr(F.D_FILE)),
              "check_file_invalid")
        check(lambda t: t["checks"][0].__setitem__("accept", tuple(t["checks"][0]["accept"])),
              "check_accept_invalid")
        check(lambda t: t["checks"][0].__setitem__("accept",
                                                   SubList(t["checks"][0]["accept"])),
              "check_accept_invalid")
        check(lambda t: t["checks"][0]["accept"].__setitem__(0, SubStr(F.D_GOOD)),
              "check_accept_invalid")
        check(lambda t: t.__setitem__("steps", SubList(t["steps"])), "steps_invalid")
        check(lambda t: t.__setitem__("steps", tuple(t["steps"])), "steps_invalid")
        check(lambda t: t.__setitem__("steps", (s for s in t["steps"])), "steps_invalid")
        check(lambda t: t["steps"].__setitem__(0, SubDict(t["steps"][0])), "step_invalid")
        check(lambda t: t["steps"][1].__setitem__("kind", SubStr("verify")),
              "step_kind_unknown")
        check(lambda t: t["steps"][0].__setitem__("file", SubStr(F.D_FILE)),
              "step_edit_invalid")
        check(lambda t: t["steps"][0].__setitem__("content", SubStr(F.D_GOOD)),
              "step_edit_invalid")
        check(lambda t: t["steps"][0].__setitem__("content", True), "step_edit_invalid")
        check(lambda t: t.__setitem__("trajectory_id", True), "trajectory_id_invalid")
        check(lambda t: t.__setitem__("trajectory_id", SubDict()), "trajectory_id_invalid")
        check(lambda t: t.__setitem__("trajectory_id", "\t "), "trajectory_id_invalid")
        self.cfg(SubDict(tr("d-undo-at-end")), "trajectory_not_dict")

    def test_run_guard_maps_internal_error(self):
        real = M._run

        def boom(snap):
            raise RuntimeError("x")

        M._run = boom
        try:
            r = M.evaluate(tr("d-undo-at-end"))
        finally:
            M._run = real
        self.assertEqual((r["status"], r["detail"]), (M.CONFIG_ERROR, "internal_error"))

    def test_never_raises(self):
        junk = [None, 0, "x", [], {}, {"trajectory_id": "x"}, {1: 2}, {(1,): 2}, set(),
                b"x", 1.5, object()]
        for j in junk:
            self.assertEqual(M.evaluate(j)["status"], M.CONFIG_ERROR, repr(j))

    def test_inputs_not_mutated(self):
        for name in F.EPISODES:
            t = tr(name)
            before = copy.deepcopy(t)
            M.evaluate(t)
            self.assertEqual(t, before, name)


class TestKeysAndSnapshot(unittest.TestCase):
    """F1: exact-str keys before any lookup; every arm runs on a snapshot only."""

    def cfg(self, r, detail):
        self.assertEqual((r["status"], r["detail"]), (M.CONFIG_ERROR, detail))
        self.assertIsNone(r["rule"])

    def test_a1_spoofed_trajectory_key_is_config_error(self):
        for field in M.TRAJECTORY_FIELDS:
            t = tr("d-undo-at-end")
            value = t.pop(field)
            key = Spoof(field)
            t[key] = value
            self.cfg(M.evaluate(t), "trajectory_key_invalid")
            self.assertEqual(key.n, 0, field)

    def test_a2b_validated_refusal_stays_refused(self):
        """A spoofed step key whose comparison would drop the breaking edit from
        the caller's list cannot turn a refused undo into a clean run."""
        plain = run("d-undo-at-end")
        self.assertEqual(plain["rule"]["refused"], (3,))
        for field in M.EDIT_FIELDS:
            for flip in range(1, 12):
                t = tr("d-undo-at-end")
                box = {"t": t}

                def hook(n, flip=flip):
                    if n == flip:
                        box["t"]["steps"].pop()
                        box["t"]["checks"][0]["accept"].append(F.D_BAD)

                s = t["steps"][3]
                value = s.pop(field)
                key = Spoof(field, hook)
                s[key] = value
                r = M.evaluate(t)
                self.assertNotEqual(r["status"], M.OK, (field, flip))
                self.cfg(r, "step_key_invalid")
                self.assertEqual(key.n, 0, (field, flip))
                self.assertEqual(len(t["steps"]), 4, (field, flip))

    def test_a3_str_subclass_cannot_reach_a_record(self):
        class Two(str):
            def __eq__(self, other):
                return other in (F.D_GOOD, F.D_BAD)

            __hash__ = str.__hash__

        t = tr("d-undo-at-end")
        t["steps"][3]["content"] = Two(F.D_BAD)
        self.cfg(M.evaluate(t), "step_edit_invalid")
        t = tr("d-undo-at-end")
        t["checks"][0]["accept"][0] = Two(F.D_GOOD)
        self.cfg(M.evaluate(t), "check_accept_invalid")
        for name in F.EPISODES:
            r = run(name)
            self.assertIs(type(r["trajectory_id"]), str, name)
            for i in r["rule"]["refused"] + r["regressions"]:
                self.assertIs(type(i), int)

    def test_non_str_keys_rejected_at_every_level(self):
        for bad in (1, (1, 2), SubStr("x"), Spoof("other"), None):
            t = tr("d-undo-at-end")
            t[bad] = 1
            self.cfg(M.evaluate(t), "trajectory_key_invalid")
            t = tr("d-undo-at-end")
            t["initial"][bad] = "x"
            self.cfg(M.evaluate(t), "initial_key_invalid")
            t = tr("d-undo-at-end")
            t["checks"][0][bad] = "x"
            self.cfg(M.evaluate(t), "check_key_invalid")
            t = tr("d-undo-at-end")
            t["steps"][0][bad] = "x"
            self.cfg(M.evaluate(t), "step_key_invalid")
            t = tr("d-undo-at-end")
            t["steps"][1][bad] = "x"
            self.cfg(M.evaluate(t), "step_key_invalid")
        for field in M.CHECK_FIELDS:
            t = tr("d-undo-at-end")
            value = t["checks"][0].pop(field)
            key = Spoof(field)
            t["checks"][0][key] = value
            self.cfg(M.evaluate(t), "check_key_invalid")
            self.assertEqual(key.n, 0)
        key = Spoof(F.D_FILE)
        t = tr("d-undo-at-end")
        t["initial"] = {key: F.D_BUG}
        self.cfg(M.evaluate(t), "initial_key_invalid")
        self.assertEqual(key.n, 0)
        key = Spoof("kind")
        t = tr("d-undo-at-end")
        t["steps"][1] = {key: "verify"}
        self.cfg(M.evaluate(t), "step_key_invalid")
        self.assertEqual(key.n, 0)

    def test_arms_see_only_the_snapshot(self):
        seen = []
        real = M._run

        def spy(snap):
            seen.append(snap)
            return real(snap)

        M._run = spy
        try:
            for name in F.EPISODES:
                t = tr(name)
                r = M.evaluate(t)
                self.assertEqual(len(seen), 1, name)
                snap = seen.pop()
                self.assertEqual(containers(snap, set()) & containers(t, set()), set(), name)
                self.assertIs(type(snap["steps"]), tuple)
                self.assertIs(type(snap["checks"]), tuple)
                for c in snap["checks"]:
                    self.assertIs(type(c[1]), tuple)
                t["steps"].clear()
                t["checks"][0]["accept"].append(F.D_BAD)
                t["initial"].clear()
                self.assertEqual(r, real(snap), name)
        finally:
            M._run = real

    def test_caller_mutation_mid_run_changes_nothing(self):
        """The caller's objects are changed while the arms run (before the
        first arm reads anything); every result still comes from the snapshot."""
        real = M.raw_run
        for name in F.EPISODES:
            clean = run(name)
            t = tr(name)

            def meddle(snap, t=t):
                for s in t["steps"]:
                    if s["kind"] == "edit":
                        s["content"] = "meddled"
                t["steps"].append(edit("x", "y"))
                for c in t["checks"]:
                    c["accept"].append("meddled")
                for k in list(t["initial"]):
                    t["initial"][k] = "meddled"
                return real(snap)

            M.raw_run = meddle
            try:
                r = M.evaluate(t)
            finally:
                M.raw_run = real
            self.assertEqual(r, clean, name)


class TestFixtures(unittest.TestCase):

    def test_expected_table(self):
        for name, (m, _) in F.run_all().items():
            self.assertEqual(F.labels_of(m), F.LABELS[name], name)

    def test_fixture_invariants(self):
        es = F.episodes()
        self.assertEqual(sorted(es), sorted(F.LABELS))
        self.assertEqual(len(es), 15)
        for name, t in es.items():
            self.assertEqual(t["trajectory_id"], name)
            lab = F.LABELS[name]
            for i in lab[2] + lab[4]:
                self.assertEqual(t["steps"][i]["kind"], "edit", name)
            if lab[0] is not None:
                self.assertEqual(t["steps"][lab[0]]["kind"], "edit", name)
                self.assertEqual(lab[1], len(t["steps"]) - 1 - lab[0], name)
                for i in lab[2] + lab[4]:
                    self.assertGreater(i, lab[0], name)
            else:
                self.assertEqual((lab[1], lab[2], lab[4]), (None, (), ()), name)
        names = [n for n, lab in F.LABELS.items()]
        self.assertTrue(any(F.LABELS[n][2] and F.LABELS[n][3] == M.PASS for n in names))
        self.assertTrue(any(F.LABELS[n][2] != F.LABELS[n][4] for n in names))
        self.assertEqual(F.LABELS[F.LONG_WAIT][1], 8)

    def test_fixture_pins(self):
        self.assertEqual(F.EPISODES["d-undo-at-end"]["steps"][3],
                         {"kind": "edit", "file": "src/dates.py",
                          "content": "return parse(s, tz=False)"})
        self.assertEqual(F.EPISODES["d-alt-correct"]["steps"][2]["content"],
                         "return parse_aware(s)")
        self.assertEqual(F.LONG_WAIT, "d-long-wait-then-undo")

    def test_fixtures_return_copies(self):
        e = F.episodes()
        e["d-undo-at-end"]["steps"].clear()
        self.assertEqual(len(F.episodes()["d-undo-at-end"]["steps"]), 4)

    def test_determinism(self):
        self.assertEqual(F.summary(), F.summary())
        self.assertEqual(F.summary_lines(), F.summary_lines())


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
        dirty = ("an al" + "lowlist that ke" + "eps 3" + "5-" + "-3" + "7% in /" + "tmp per Check"
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
        # Files other than the day README are still scanned whole.
        self.assertEqual(hygiene_hits(scan_text("README.md", day(clean, dirty))), every)
        # The real day README has this PR's row, so the scoped scans read something.
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
        self.assertIn("(Top method sketch of ", rows[0])
        main = [line for line in lines if line.startswith(MAIN_ROW_PREFIX)]
        self.assertEqual(len(main), 1)
        self.assertEqual(hashlib.sha256(main[0].encode("utf-8")).hexdigest(), MAIN_ROW_SHA256)
        self.assertEqual(lines.index(rows[0]), lines.index(main[0]) + 1)
        if LAYOUT == "flat":
            self.assertEqual(sum(1 for line in lines if line.startswith("- ")), 2)

    def test_no_paper_claims_outside_evidence(self):
        for name in PY + ("README.md", "NOTICE", DAY):
            self.assertIsNone(PAPER_PAT.search(scan_text(name, read(name))), name)

    def test_readme_results_match_computed(self):
        readme = read("README.md")
        for line in F.summary_lines():
            self.assertEqual(readme.count(line + "\n"), 1, line)

    def test_readme_credits_differentiation_and_limits(self):
        flat = " ".join(read("README.md").split())
        ev = json.loads(read("paper_evidence.json"))
        self.assertIn(ev["paper"]["title"], flat)
        for author in ev["paper"]["authors"]:
            self.assertIn(author, flat)
        for s in ("**Top** method sketch", "not a reproduction", "UNVERIFIED", "on_unmeasured",
                  "paper_evidence.json", "## Limits", "## Builder reflection", "CC BY 4.0",
                  "python3 -B -m unittest", "python3 -B mutants.py", "w21-info-friction",
                  "w14-phase-deadline", "w14-silence-expiry", "no timeout",
                  "honest baseline", "independent oracle"):
            self.assertIn(s, flat, s)
        notice = " ".join(read("NOTICE").split())
        for s in (ev["paper"]["title"], "arXiv:2611.14960", "https://arxiv.org/abs/2611.14960",
                  "CC BY 4.0", "http://creativecommons.org/licenses/by/4.0/", "clean-room"):
            self.assertIn(s, notice, s)
        for author in ev["paper"]["authors"]:
            self.assertIn(author, notice)

    def test_evidence_shape(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.14960")
        self.assertEqual(ev["paper"]["version"], "v1")
        self.assertIn("creativecommons.org/licenses/by/4.0", ev["paper"]["licence"])
        self.assertFalse(ev["paper"]["pdf_read"])
        self.assertGreaterEqual(len(ev["claims"]), 3)
        for c in ev["claims"]:
            self.assertEqual(len(c["quote"]), c["length"])

    def test_quotes_exact_in_sources(self):
        if not SOURCES:
            self.skipTest("W23TERMLAG_SOURCES not set")
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
