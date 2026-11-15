"""Tests for the w23-world-consistent-history method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
The quote check reads the source copy named in paper_evidence.json from the
directories listed in $W23WCH_SOURCES (os.pathsep separated). There is no
default: when the variable is unset, or the file is absent, that check is
skipped.

Done-when mapping (Lab Dig 2 Wave23, Top: arXiv 2611.14654):
  (a) test_a_unedited_history_is_the_baseline
  (b) test_b_truthful_note_admitted_and_receiver_recovers
  (c) test_c_done_rewrite_refused_and_receiver_worse
  (d) test_d_success_receipt_only_once_effect_present
  (e) test_e_no_network_no_model_no_database_paper_on_unmeasured
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
import world_history as M

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W23WCH_SOURCES")
SLUG = "w23-world-consistent-history"
DAY_HEADER = "# experiments/2026-11-14\n"
ROW_START = "- [%s](%s/): " % (SLUG, SLUG)
ROW_PREFIX = "- [%s](" % SLUG
ROW_END = ("(Top method sketch of [arXiv 2611.14654](https://arxiv.org/abs/2611.14654);"
           " not a reproduction)")
MAIN_ROW_PREFIX = "- [mb-boundary-vs-judge]("
MAIN_ROW_SHA256 = "aae8fb872d0cb1de22745e358bc832d84e4c71ab3a77e5b2589a88fa68b0e720"
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
CODE = ("world_history.py", "oracle.py", "fixtures.py")
PY = CODE + ("test_world_history.py", "mutants.py")
ALL = PY + ("README.md", "NOTICE", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
STDLIB_PERMITTED = {"ast", "copy", "hashlib", "io", "itertools", "json", "os", "re", "sys",
                    "unittest", "world_history", "oracle", "fixtures", "test_world_history"}
CODE_IMPORTS = {"world_history.py": set(), "oracle.py": set(),
                "fixtures.py": {"copy", "oracle", "world_history"}}
NO_GO_TOKENS = ("sql" + "ite", "sql" + "3", "cur" + "sor", "data" + "base", "db" + "_",
                "sock" + "et", "url" + "lib", "http" + "://", "https" + "://", "requ" + "ests",
                "sub" + "process", "envi" + "ron", "api" + "_key", "api" + "key",
                "open" + "ai", "anthro" + "pic", "vo" + "te", "ensem" + "ble",
                "thre" + "ad", "sched" + "ule", "ti" + "me.", "rand" + "om")
ABS_PATHS = ("/" + "workspace", "/" + "tmp", "/" + "home")
MARKERS = ("<" * 7, "=" * 7, ">" * 7)
PAPER_PAT = re.compile(r"\d+(?:\.\d+)?\s*%|\b27\s+points|\b97\.5\b|" + "six " + "of eight|"
                       + "seven " + "at|" + "from " + "5[01]|" + "from " + "45|" + "from " + "38")


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


def n_rec(rec, view):
    return len(rec["outcomes"][view]["recovered"])


def of_kind(kind):
    return [n for n, c in F.cases().items() if c["edit_kind"] == kind]


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


def one_target_space():
    """Every one-target case with histories of up to two records."""
    vals = ("u", "v")
    alphabet = [{"target": "t", "claim": c, "value": v} for c in M.CLAIMS for v in vals]
    hists = [[]] + [[a] for a in alphabet] + [[a, b] for a in alphabet for b in alphabet]
    for world, gold, guess in itertools.product(("", "u", "v"), vals, vals):
        for h, e in itertools.product(hists, hists):
            yield {"case_id": "x", "setting": "form", "edit_kind": "compact",
                   "targets": ["t"], "gold": {"t": gold}, "world": {"t": world},
                   "guess": {"t": guess}, "history": copy.deepcopy(h),
                   "edited": copy.deepcopy(e)}


def blank_space():
    """One target with blank and non-blank values: histories of up to one
    record, edits of up to two, every world among "", " " and "u"."""
    vals = ("", " ", "u")
    alphabet = [{"target": "t", "claim": c, "value": v} for c in M.CLAIMS for v in vals]
    one = [[]] + [[a] for a in alphabet]
    two = one + [[a, b] for a in alphabet for b in alphabet]
    for world, gold, guess in itertools.product(vals, ("u", "v"), ("", "u")):
        for h, e in itertools.product(one, two):
            yield {"case_id": "z", "setting": "store", "edit_kind": "compact",
                   "targets": ["t"], "gold": {"t": gold}, "world": {"t": world},
                   "guess": {"t": guess}, "history": copy.deepcopy(h),
                   "edited": copy.deepcopy(e)}


def two_target_space():
    """Two targets, histories of up to one record each, every world and guess."""
    alphabet = [{"target": t, "claim": c, "value": v}
                for t in ("p", "q") for c in M.CLAIMS for v in ("u", "v")]
    hists = [[]] + [[a] for a in alphabet]
    vals = ("u", "v")
    for wp, wq, gp, gq in itertools.product(vals, vals, vals, vals):
        for h, e in itertools.product(hists, hists):
            yield {"case_id": "y", "setting": "store", "edit_kind": "compact",
                   "targets": ["p", "q"], "gold": {"p": "u", "q": "v"},
                   "world": {"p": wp, "q": wq}, "guess": {"p": gp, "q": gq},
                   "history": copy.deepcopy(h), "edited": copy.deepcopy(e)}


class TestDoneWhen(unittest.TestCase):

    def test_a_unedited_history_is_the_baseline(self):
        """Each freeze has an unedited case; its error persists in the world;
        every edit of that freeze is compared with the same unedited outcome."""
        cs = F.cases()
        unedited = of_kind("none")
        self.assertEqual(len(unedited), len(F.FREEZES))
        freeze_of = dict((e[0], e[1]) for e in F.EDITS)
        self.assertEqual(sorted(freeze_of[n] for n in unedited), sorted(F.FREEZES))
        base = {}
        for n in unedited:
            c = cs[n]
            self.assertEqual(c["edited"], c["history"], n)
            rec = run(n)
            self.assertEqual(rec["rule"]["decision"], M.ADMIT, n)
            remaining = rec["outcomes"]["unedited"]["remaining"]
            self.assertGreaterEqual(len(remaining), 1, n)
            for view in M.VIEWS:
                self.assertEqual(rec["outcomes"][view], rec["outcomes"]["unedited"], (n, view))
            base[freeze_of[n]] = rec["outcomes"]["unedited"]
        for n, c in cs.items():
            rec = M.evaluate(c)
            self.assertEqual(rec["outcomes"]["unedited"], base[freeze_of[n]], n)
            # The unedited view never depends on the edit.
            c2 = copy.deepcopy(c)
            c2["edited"] = [{"target": c["targets"][0], "claim": "done", "value": "zz"}]
            self.assertEqual(M.evaluate(c2)["outcomes"]["unedited"], base[freeze_of[n]], n)
        # At least one freeze holds an error the receiver does not fix alone.
        self.assertTrue(any(len(o["recovered"]) < len(o["remaining"]) for o in base.values()))
        self.assertIn("unedited: recovery 20/24 = 0.833", F.summary())

    def test_b_truthful_note_admitted_and_receiver_recovers(self):
        notes = of_kind("truthful_note")
        self.assertEqual(len(notes), 4)
        for n in notes:
            c = case(n)
            rec = run(n)
            self.assertEqual(rec["rule"], {"decision": M.ADMIT, "reasons": ()}, n)
            self.assertEqual(rec["baseline"]["decision"], M.ADMIT, n)
            noted = [r["target"] for r in c["edited"] if r["claim"] == M.NOTE]
            self.assertEqual(len(noted), 1, n)
            t = noted[0]
            # The error is preserved beside the note: the target's claim is
            # unchanged and still matches the world.
            self.assertEqual(M.last_claims(M.validate(c)["edited"])[t],
                             M.last_claims(M.validate(c)["history"])[t], n)
            self.assertIn(t, rec["outcomes"]["rule"]["remaining"], n)
            self.assertIn(t, rec["outcomes"]["rule"]["recovered"], n)
            self.assertGreaterEqual(n_rec(rec, "rule"), n_rec(rec, "unedited"), n)
        # Where the receiver cannot fix the error alone, the note raises
        # recovery above both the unedited history and a matched neutral note.
        note, neutral, plain = (run("hard-error-truthful-note"), run("hard-error-neutral-note"),
                                run("hard-error-unedited"))
        self.assertEqual((n_rec(note, "rule"), n_rec(neutral, "rule"), n_rec(plain, "rule")),
                         (1, 0, 0))
        self.assertEqual(neutral["rule"]["decision"], M.ADMIT)

    def test_c_done_rewrite_refused_and_receiver_worse(self):
        self.assertEqual(len(F.PLANTED), 5)
        worse = 0
        for n in F.PLANTED:
            rec = run(n)
            self.assertEqual(rec["rule"]["decision"], M.REFUSE, n)
            self.assertTrue(rec["rule"]["reasons"], n)
            for t, why in rec["rule"]["reasons"]:
                self.assertEqual(why, M.FALSE_DONE, n)
                self.assertIn(t, rec["outcomes"]["unedited"]["remaining"], n)
            self.assertEqual(rec["baseline"]["decision"], M.ADMIT, n)
            # The rule arm falls back to the unedited history.
            self.assertEqual(rec["outcomes"]["rule"], rec["outcomes"]["unedited"], n)
            self.assertLessEqual(n_rec(rec, "baseline"), n_rec(rec, "unedited"), n)
            worse += n_rec(rec, "baseline") < n_rec(rec, "unedited")
        self.assertEqual(worse, 4)
        # Every refusal is a planted false done, except the one erased claim.
        refused = sorted(n for n in F.LABELS if run(n)["rule"]["decision"] == M.REFUSE)
        self.assertEqual(refused, sorted(F.PLANTED + ("effect-absent-erase-error",)))
        self.assertEqual(run("effect-absent-erase-error")["rule"]["reasons"],
                         (("order_status", M.CLAIM_ERASED),))
        # The value's presence alone does not decide: the note and the
        # completed action both carry the gold value; only the note helps.
        gold = case("hard-error-completed-action")["gold"]["city"]
        for n in ("hard-error-truthful-note", "hard-error-completed-action"):
            self.assertIn(gold, [r["value"] for r in case(n)["edited"]], n)
        self.assertEqual(run("hard-error-truthful-note")["rule"]["decision"], M.ADMIT)
        self.assertEqual(run("hard-error-completed-action")["rule"]["decision"], M.REFUSE)
        t = M.totals([run(n) for n in F.LABELS])
        self.assertEqual(t["baseline"]["worse_than_unedited"], 4)
        self.assertEqual(t["rule"]["worse_than_unedited"], 0)
        summary = F.summary()
        self.assertIn("rule arm refuses planted false-done edits: 5/5", summary)
        self.assertIn("baseline admits planted false-done edits: 5/5", summary)
        # The README reports exactly the computed lines.
        readme = read("README.md")
        for line in summary.splitlines():
            self.assertIn(line, readme, line)
        flat = " ".join(readme.split())
        self.assertIn("not comparable with any figure in the paper", flat)
        self.assertNotRegex(summary, r"%")

    def test_c_done_blank_on_absent_effect_refused(self):
        """Fix round 2 (M1): rewriting the failure receipt "failed veg" as
        "done \"\"" on the absent meal effect is refused as false_done, never
        admitted; the same holds for whitespace values and a wrong guess."""
        base = case("meal-absent-unedited")
        self.assertEqual(base["world"]["meal"], "")
        self.assertIn({"target": "meal", "claim": "failed", "value": "veg"}, base["history"])
        for v in ("", " ", "\t", "   "):
            for guess in ("veg", "fish", ""):
                c = copy.deepcopy(base)
                c["guess"]["meal"] = guess
                c["edited"] = [{"target": "seat", "claim": "done", "value": "12A"},
                               {"target": "meal", "claim": "done", "value": v}]
                rec = M.evaluate(c)
                self.assertEqual(rec["status"], M.OK, (v, guess))
                self.assertEqual(rec["rule"]["decision"], M.REFUSE, (v, guess))
                self.assertNotEqual(rec["rule"]["decision"], M.ADMIT, (v, guess))
                self.assertEqual(rec["rule"]["reasons"], (("meal", M.FALSE_DONE),), (v, guess))
                self.assertEqual(rec["outcomes"]["rule"], rec["outcomes"]["unedited"], (v, guess))
                self.assertEqual(rec["baseline"]["decision"], M.ADMIT, (v, guess))
                self.assertEqual(O.reference(copy.deepcopy(c))["rule"], M.REFUSE, (v, guess))
        # The world also blank-valued: still no match for a blank done claim.
        c = copy.deepcopy(base)
        c["world"]["meal"] = " "
        c["edited"] = [{"target": "seat", "claim": "done", "value": "12A"},
                       {"target": "meal", "claim": "done", "value": " "}]
        self.assertEqual(M.evaluate(c)["rule"]["reasons"], (("meal", M.FALSE_DONE),))

    def test_d_success_receipt_only_once_effect_present(self):
        receipts = of_kind("success_receipt")
        self.assertEqual(len(receipts), 3)
        for n in receipts:
            c = case(n)
            rec = run(n)
            done = [(r["target"], r["value"]) for r in c["edited"] if r["claim"] == M.DONE]
            present = all(c["world"][t] == v for t, v in done)
            self.assertEqual(rec["rule"]["decision"], M.ADMIT if present else M.REFUSE, n)
        self.assertEqual(run("effect-present-success-receipt")["rule"]["decision"], M.ADMIT)
        self.assertEqual(run("effect-absent-success-receipt")["rule"]["decision"], M.REFUSE)
        # The same receipt, once its effect lands in the world, is admitted ...
        c = case("effect-absent-success-receipt")
        c["world"]["order_status"] = "shipped"
        self.assertEqual(M.evaluate(c)["rule"], {"decision": M.ADMIT, "reasons": ()})
        # ... and a receipt whose effect is gone is refused.
        c = case("effect-present-success-receipt")
        c["world"]["order_status"] = "pending"
        self.assertEqual(M.evaluate(c)["rule"]["reasons"], (("order_status", M.FALSE_DONE),))
        # Exhaustively on one target: a done claim is admitted iff the world holds it.
        for c in one_target_space():
            claims = [r for r in c["edited"] if r["claim"] in M.STATUS_CLAIMS]
            if claims and claims[-1]["claim"] == M.DONE:
                want = M.ADMIT if c["world"]["t"] == claims[-1]["value"] else M.REFUSE
                self.assertEqual(M.evaluate(c)["rule"]["decision"], want)

    def test_e_no_network_no_model_no_database_paper_on_unmeasured(self):
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
        # The loaded functions name nothing outside the declared code either.
        for fn in (M.validate, M.rule, M.baseline, M.receiver, M.outcome, M._run,
                   M.evaluate, M.totals):
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
        self.assertFalse(ev["ancillary_files"]["downloaded"])
        self.assertFalse(ev["ancillary_files"]["run"])


class TestRules(unittest.TestCase):

    def test_labels_match(self):
        for n, lab in F.LABELS.items():
            rec = run(n)
            got = (rec["rule"]["decision"], rec["rule"]["reasons"],
                   len(rec["outcomes"]["unedited"]["remaining"]), n_rec(rec, "unedited"),
                   n_rec(rec, "baseline"), n_rec(rec, "rule"))
            self.assertEqual(got, lab, n)
            for view in M.VIEWS:
                self.assertEqual(rec["outcomes"][view]["damaged"], (), (n, view))

    def test_rule_reads_neither_gold_nor_guess_nor_kind(self):
        for n, c in F.cases().items():
            want = run(n)["rule"]
            for kind in M.EDIT_KINDS:
                self.assertEqual(M.evaluate(dict(c, edit_kind=kind))["rule"], want, (n, kind))
            for t in c["targets"]:
                x = copy.deepcopy(c)
                x["gold"][t] = "other"
                x["guess"][t] = "other"
                self.assertEqual(M.evaluate(x)["rule"], want, (n, t))

    def test_rule_reads_the_world(self):
        for n in F.PLANTED:
            c = case(n)
            for t, _ in run(n)["rule"]["reasons"]:
                claimed = M.last_claims(M.validate(c)["edited"])[t][1]
                c["world"][t] = claimed
            self.assertEqual(M.evaluate(c)["rule"]["decision"], M.ADMIT, n)

    def test_baseline_trusts_the_history_text(self):
        for n, c in F.cases().items():
            rec = run(n)
            self.assertEqual(rec["baseline"]["decision"], M.ADMIT, n)
            done = {}
            for r in c["edited"]:
                if r["claim"] in M.STATUS_CLAIMS:
                    done[r["target"]] = r
            want = tuple(sorted((t, r["value"]) for t, r in done.items()
                                if r["claim"] == M.DONE))
            self.assertEqual(rec["baseline"]["believed_done"], want, n)
            x = copy.deepcopy(c)
            for t in x["targets"]:
                x["world"][t] = "elsewhere"
                x["gold"][t] = "elsewhere"
            self.assertEqual(M.evaluate(x)["baseline"], rec["baseline"], n)

    def test_receiver_never_reads_world_or_gold(self):
        for n, c in F.cases().items():
            rec = run(n)
            x = copy.deepcopy(c)
            for t in x["targets"]:
                x["world"][t] = "w-" + t
                x["gold"][t] = "g-" + t
            got = M.evaluate(x)
            for view in M.VIEWS:
                if got["rule"]["decision"] == rec["rule"]["decision"] or view != "rule":
                    self.assertEqual(got["outcomes"][view]["writes"],
                                     rec["outcomes"][view]["writes"], (n, view))

    def test_receiver_table(self):
        g = {"t": "u"}
        cases = [
            ([], "u"),
            ([{"target": "t", "claim": "done", "value": "u"}], None),
            ([{"target": "t", "claim": "done", "value": "v"}], "u"),
            ([{"target": "t", "claim": "failed", "value": "v"}], "v"),
            ([{"target": "t", "claim": "neutral", "value": "v"}], "u"),
            ([{"target": "t", "claim": "done", "value": "v"},
              {"target": "t", "claim": "note", "value": "w"}], "w"),
            ([{"target": "t", "claim": "note", "value": "w"},
              {"target": "t", "claim": "done", "value": "w"}], None),
            ([{"target": "t", "claim": "done", "value": "v"},
              {"target": "t", "claim": "failed", "value": "u"}], "u"),
        ]
        for hist, want in cases:
            recs = M._records(hist, ("t",), "history")
            self.assertEqual(M.receiver(recs, g, ("t",)), {"t": want}, hist)

    def test_rule_table(self):
        def snap(world, hist, edited):
            return {"targets": ("t",), "world": {"t": world},
                    "history": M._records(hist, ("t",), "h"),
                    "edited": M._records(edited, ("t",), "e")}
        d = lambda v: {"target": "t", "claim": "done", "value": v}
        x = lambda v: {"target": "t", "claim": "failed", "value": v}
        nt = lambda v: {"target": "t", "claim": "note", "value": v}
        self.assertEqual(M.rule(snap("u", [d("u")], [d("u")]))["decision"], M.ADMIT)
        self.assertEqual(M.rule(snap("u", [d("u")], [d("v")]))["reasons"],
                         (("t", M.FALSE_DONE),))
        self.assertEqual(M.rule(snap("", [x("u")], [d("u")]))["reasons"],
                         (("t", M.FALSE_DONE),))
        self.assertEqual(M.rule(snap("u", [x("u")], [d("u")]))["decision"], M.ADMIT)
        self.assertEqual(M.rule(snap("u", [d("u")], [nt("v")]))["reasons"],
                         (("t", M.CLAIM_ERASED),))
        self.assertEqual(M.rule(snap("u", [d("u")], []))["reasons"], (("t", M.CLAIM_ERASED),))
        self.assertEqual(M.rule(snap("u", [], []))["decision"], M.ADMIT)
        self.assertEqual(M.rule(snap("u", [], [x("v")]))["decision"], M.ADMIT)
        # A failure receipt is never refused by this rule, even when the
        # effect is present (the rule is about false "done", not stale failures).
        self.assertEqual(M.rule(snap("u", [d("u")], [x("u")]))["decision"], M.ADMIT)
        # A blank done value names no effect: never a match, even on a blank world.
        for world in ("", " ", "u"):
            for v in ("", " ", "\t", "  "):
                self.assertEqual(M.rule(snap(world, [x("u")], [d(v)]))["reasons"],
                                 (("t", M.FALSE_DONE),), (world, v))
        self.assertEqual(M.rule(snap("", [x("u")], [x("")]))["decision"], M.ADMIT)
        # Only the last claim counts.
        self.assertEqual(M.rule(snap("u", [d("u")], [d("v"), d("u")]))["decision"], M.ADMIT)
        self.assertEqual(M.rule(snap("u", [d("u")], [d("u"), d("v")]))["decision"], M.REFUSE)

    def test_totals_skip_config_errors(self):
        recs = [run(n) for n in F.LABELS]
        t = M.totals(recs)
        bad = M.totals(recs + [M.evaluate(None)])
        self.assertEqual((t["n"], t["config_error"]), (20, 0))
        self.assertEqual((bad["n"], bad["config_error"]), (20, 1))
        self.assertEqual(bad["rule"], t["rule"])
        self.assertEqual((t["rule_refused"], t["baseline_refused"]), (6, 0))
        self.assertEqual((t["unedited"]["recovered"], t["baseline"]["recovered"],
                          t["rule"]["recovered"], t["rule"]["remaining"]), (20, 17, 21, 24))
        self.assertEqual((t["unedited"]["task_success"], t["baseline"]["task_success"],
                          t["rule"]["task_success"]), (16, 13, 17))
        self.assertEqual((t["baseline"]["better_than_unedited"],
                          t["rule"]["better_than_unedited"]), (1, 1))


class TestOracle(unittest.TestCase):

    def test_module_and_oracle_agree_on_all_fixtures(self):
        rows = F.run_all()
        self.assertEqual(len(rows), 20)
        for n, (m, o) in rows.items():
            self.assertEqual(F.module_tuple(m), F.oracle_tuple(o), n)
        self.assertIn("module vs oracle: 20/20 cases agree", F.summary())

    def test_module_and_oracle_agree_exhaustively(self):
        count = 0
        refused = 0
        blank_done_admitted = 0
        for c in itertools.chain(one_target_space(), two_target_space(), blank_space()):
            m = M.evaluate(c)
            self.assertEqual(m["status"], M.OK)
            o = O.reference(c)
            self.assertEqual(F.module_tuple(m), F.oracle_tuple(o), c)
            count += 1
            refused += m["rule"]["decision"] == M.REFUSE
            last = [r for r in c["edited"] if r["claim"] in M.STATUS_CLAIMS]
            if (m["rule"]["decision"] == M.ADMIT and last and last[-1]["claim"] == "done"
                    and last[-1]["value"].strip() == ""):
                blank_done_admitted += 1
        self.assertEqual(count, 63948 + 4624 + 24492)
        self.assertEqual(blank_done_admitted, 0)
        self.assertGreater(refused, 0)
        self.assertLess(refused, count)

    def test_oracle_is_a_separate_code_path(self):
        tree = ast.parse(read("oracle.py"))
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, (ast.Import, ast.ImportFrom))
        mod_names = set(n.name for n in ast.walk(ast.parse(read("world_history.py")))
                        if isinstance(n, ast.FunctionDef))
        orc_names = set(n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        self.assertEqual(mod_names & orc_names, set())


class TestInputs(unittest.TestCase):

    def cfg(self, c, detail=None):
        rec = M.evaluate(c)
        self.assertEqual(rec["status"], M.CONFIG_ERROR)
        for k in ("case_id", "rule", "baseline", "outcomes"):
            self.assertIsNone(rec[k])
        if detail is not None:
            self.assertEqual(rec["detail"], detail)

    def test_case_shape(self):
        c = case("wrong-commit-truthful-note")
        self.cfg(None, "case_not_dict")
        self.cfg([c], "case_not_dict")
        for f in M.CASE_FIELDS:
            x = copy.deepcopy(c)
            del x[f]
            self.cfg(x, f + "_missing")
        self.cfg(dict(c, planted=True), "case_unknown_field")
        self.cfg(dict(c, case_id=" "), "case_id_invalid")
        self.cfg(dict(c, setting="bank"), "setting_invalid")
        self.cfg(dict(c, edit_kind="rewrite"), "edit_kind_invalid")
        self.cfg(dict(c, targets=[]), "targets_invalid")
        self.cfg(dict(c, targets=["name", " ", "size"]), "target_invalid")
        self.cfg(dict(c, targets=["name", "name", "size"]), "target_duplicate")
        self.cfg(dict(c, gold={"name": "Ada"}), "gold_shape")
        self.cfg(dict(c, world=dict(c["world"], extra="x")), "world_shape")
        self.cfg(dict(c, guess=dict(c["guess"], name=1)), "guess_value_invalid")
        self.cfg(dict(c, world=None), "world_invalid")
        r = c["edited"][0]
        self.cfg(dict(c, edited=[dict(r, target="zzz")]), "edited_target_unknown")
        self.cfg(dict(c, edited=[dict(r, claim="maybe")]), "edited_claim_unknown")
        self.cfg(dict(c, edited=[dict(r, value=None)]), "edited_value_invalid")
        self.cfg(dict(c, edited=[dict(r, why="x")]), "edited_record_invalid")
        self.cfg(dict(c, edited=["done"]), "edited_record_invalid")
        self.cfg(dict(c, history=[{"target": "name"}]), "history_record_invalid")
        self.cfg(dict(c, history="done"), "history_invalid")

    def test_exact_types_in_every_value_slot(self):
        c = case("effect-absent-success-receipt")
        r = c["edited"][0]
        self.cfg(SubDict(c), "case_not_dict")
        self.cfg(dict(c, case_id=SubStr("x")), "case_id_invalid")
        self.cfg(dict(c, setting=SubStr("store")), "setting_invalid")
        self.cfg(dict(c, edit_kind=SubStr("none")), "edit_kind_invalid")
        self.cfg(dict(c, targets=SubList(c["targets"])), "targets_invalid")
        self.cfg(dict(c, targets=tuple(c["targets"])), "targets_invalid")
        self.cfg(dict(c, targets=[SubStr("order_status"), "email_sent"]), "target_invalid")
        self.cfg(dict(c, edited=tuple(c["edited"])), "edited_invalid")
        self.cfg(dict(c, edited=SubList(c["edited"])), "edited_invalid")
        self.cfg(dict(c, edited=(x for x in c["edited"])), "edited_invalid")
        self.cfg(dict(c, history=SubList(c["history"])), "history_invalid")
        self.cfg(dict(c, edited=[SubDict(r)]), "edited_record_invalid")
        self.cfg(dict(c, edited=[dict(r, target=SubStr("order_status"))]),
                 "edited_target_unknown")
        self.cfg(dict(c, edited=[dict(r, claim=SubStr("done"))]), "edited_claim_unknown")
        self.cfg(dict(c, edited=[dict(r, value=SubStr("shipped"))]), "edited_value_invalid")
        self.cfg(dict(c, world=SubDict(c["world"])), "world_invalid")
        self.cfg(dict(c, world=dict(c["world"], order_status=SubStr("shipped"))),
                 "world_value_invalid")
        self.cfg(dict(c, gold=dict(c["gold"], order_status=SubStr("shipped"))),
                 "gold_value_invalid")
        self.cfg(dict(c, guess=SubDict(c["guess"])), "guess_invalid")

    def test_run_guard_maps_internal_error(self):
        real = M.rule

        def boom(snap):
            raise OverflowError("boom")

        M.rule = boom
        try:
            self.cfg(case("wrong-commit-unedited"), "internal_error")
        finally:
            M.rule = real

    def test_never_raises(self):
        c = case("wrong-commit-unedited")
        for arg in [None, 1, {}, {"case_id": "x"}, [], "case", dict(c, edited=[[]]),
                    dict(c, targets=[["x"]]), dict(c, gold=[]), dict(c, history=[None])]:
            self.assertEqual(M.evaluate(arg)["status"], M.CONFIG_ERROR, arg)

    def test_inputs_not_mutated(self):
        for n, c in F.cases().items():
            c0 = copy.deepcopy(c)
            M.evaluate(c)
            O.reference(c)
            self.assertEqual(c, c0, n)


class TestKeysAndSnapshot(unittest.TestCase):
    """F1: exact-str keys before any lookup; all logic runs on a snapshot only."""

    def cfg(self, rec, detail):
        self.assertEqual((rec["status"], rec["detail"]), (M.CONFIG_ERROR, detail))
        self.assertIsNone(rec["rule"])

    def test_spoofed_case_key_is_config_error(self):
        for field in M.CASE_FIELDS:
            c = case("effect-absent-success-receipt")
            value = c.pop(field)
            key = Spoof(field)
            c[key] = value
            self.cfg(M.evaluate(c), "case_key_invalid")
            self.assertEqual(key.n, 0, field)

    def test_validated_refusal_stays_refused(self):
        """A spoofed record key whose comparison would make the caller's edit
        and world consistent cannot turn a refused false done into ADMIT."""
        plain = run("effect-absent-success-receipt")
        self.assertEqual(plain["rule"]["decision"], M.REFUSE)
        for field in M.RECORD_FIELDS:
            for flip in range(1, 12):
                c = case("effect-absent-success-receipt")
                box = {"c": c}

                def hook(n, flip=flip):
                    if n == flip:
                        box["c"]["world"]["order_status"] = "shipped"
                        box["c"]["edited"][1:] = []

                r = c["edited"][0]
                value = r.pop(field)
                key = Spoof(field, hook)
                r[key] = value
                rec = M.evaluate(c)
                self.cfg(rec, "edited_key_invalid")
                self.assertEqual(key.n, 0, (field, flip))
                self.assertEqual(c["world"]["order_status"], "pending", (field, flip))

    def test_str_subclass_with_eq_rejected(self):
        class Any(str):
            def __eq__(self, other):
                return True

            __hash__ = str.__hash__

        c = case("effect-absent-success-receipt")
        c["world"]["order_status"] = Any("pending")
        self.cfg(M.evaluate(c), "world_value_invalid")
        c = case("effect-absent-success-receipt")
        c["edited"][0]["value"] = Any("shipped")
        self.cfg(M.evaluate(c), "edited_value_invalid")
        for n, c in F.cases().items():
            rec = M.evaluate(c)
            self.assertIs(type(rec["case_id"]), str, n)
            for t, why in rec["rule"]["reasons"]:
                self.assertIs(type(t), str)
                self.assertIs(type(why), str)

    def test_non_str_keys_rejected_at_every_level(self):
        for bad in (1, (1, 2), SubStr("x"), Spoof("other"), True):
            for slot in ("gold", "world", "guess"):
                c = case("wrong-commit-unedited")
                c[slot][bad] = "x"
                self.cfg(M.evaluate(c), slot + "_key_invalid")
            for slot in ("history", "edited"):
                c = case("wrong-commit-unedited")
                c[slot][0][bad] = "x"
                self.cfg(M.evaluate(c), slot + "_key_invalid")
            c = case("wrong-commit-unedited")
            c[bad] = 1
            self.cfg(M.evaluate(c), "case_key_invalid")
        key = Spoof("color")
        c = case("wrong-commit-unedited")
        del c["world"]["color"]
        c["world"][key] = "navy"
        self.cfg(M.evaluate(c), "world_key_invalid")
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
                for k in ("targets", "history", "edited"):
                    self.assertIs(type(snap[k]), tuple, (n, k))
                for r in snap["history"] + snap["edited"]:
                    self.assertIs(type(r), tuple)
                    for v in r:
                        self.assertIs(type(v), str)
                c["edited"].clear()
                c["history"].clear()
                for t in c["targets"]:
                    c["world"][t] = "meddled"
                self.assertEqual(rec, real(snap), n)
        finally:
            M._run = real

    def test_caller_mutation_mid_run_changes_nothing(self):
        """The caller's objects are changed after validation, before the rule
        reads anything; every result still comes from the snapshot."""
        real = M.rule
        for n in F.LABELS:
            clean = run(n)
            c = case(n)

            def meddle(snap, c=c):
                for t in c["targets"]:
                    c["world"][t] = c["gold"][t] = c["guess"][t] = "meddled"
                c["edited"][:] = c["history"][:] = []
                c["targets"].clear()
                return real(snap)

            M.rule = meddle
            try:
                rec = M.evaluate(c)
            finally:
                M.rule = real
            self.assertEqual(rec, clean, n)


class TestFixtures(unittest.TestCase):

    def test_fixture_invariants(self):
        cs = F.cases()
        self.assertEqual(list(cs), [e[0] for e in F.EDITS])
        self.assertEqual(sorted(cs), sorted(F.LABELS))
        self.assertEqual(len(cs), 20)
        self.assertEqual(sorted(set(c["setting"] for c in cs.values())), ["form", "store"])
        for n, c in cs.items():
            self.assertEqual(c["case_id"], n)
            self.assertEqual(M.validate(c)["case_id"], n)
        for p in F.PLANTED:
            self.assertIn(cs[p]["edit_kind"], ("completed_action", "success_receipt"), p)
        # Gold world states: every freeze holds at least one error.
        for name, f in F.FREEZES.items():
            self.assertTrue(any(f["world"][t] != f["gold"][t] for t in f["targets"]), name)

    def test_fixture_pins(self):
        self.assertEqual(F.FREEZES["store-effect-absent"]["world"]["order_status"], "pending")
        self.assertEqual(F.FREEZES["form-hard-error"]["guess"]["city"], "Paris")
        self.assertEqual(len(F.FREEZES), 6)
        self.assertEqual(len(F.PLANTED), 5)

    def test_fixtures_return_copies(self):
        c = F.cases()
        c["wrong-commit-unedited"]["edited"].clear()
        c["wrong-commit-unedited"]["world"]["color"] = "blue"
        fresh = F.cases()["wrong-commit-unedited"]
        self.assertEqual(len(fresh["edited"]), 2)
        self.assertEqual(fresh["world"]["color"], "navy")
        lab = F.labels()
        lab["wrong-commit-unedited"] = None
        self.assertIsNotNone(F.LABELS["wrong-commit-unedited"])

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
        self.assertIn("**Top**", rows[0])
        main_rows = [line for line in lines if line.startswith(MAIN_ROW_PREFIX)]
        self.assertEqual(len(main_rows), 1)
        if LAYOUT == "flat":
            # Based on main alone: the main row, retained byte for byte, then this row.
            bullets = [line for line in lines if line.startswith("- ")]
            self.assertEqual(bullets, [main_rows[0], rows[0]])
            self.assertEqual(hashlib.sha256(main_rows[0].encode("utf-8")).hexdigest(),
                             MAIN_ROW_SHA256)
            self.assertEqual(lines.index(rows[0]), lines.index(main_rows[0]) + 1)

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
                  "CC BY 4.0", "python3 -B -m unittest", "python3 -B mutants.py",
                  "w21-unused-contradiction", "w20-evidence-linked-memory",
                  "w21-memory-admission", "w22-write-precommit", "mb-boundary-vs-judge",
                  "no timeout", "not a database"):
            self.assertIn(s, flat, s)
        notice = " ".join(read("NOTICE").split())
        for s in (ev["paper"]["title"], "arXiv:2611.14654", "https://arxiv.org/abs/2611.14654",
                  "CC BY 4.0", "clean-room", "not downloaded", "not run"):
            self.assertIn(s, notice, s)
        for author in ev["paper"]["authors"]:
            self.assertIn(author, notice)

    def test_evidence_shape(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.14654")
        self.assertIn("creativecommons.org/licenses/by/4.0", ev["paper"]["licence"])
        self.assertFalse(ev["paper"]["pdf_read"])
        for c in ev["claims"]:
            self.assertEqual(len(c["quote"]), c["length"], c["id"])
            self.assertEqual(c["status"], "UNVERIFIED", c["id"])
        quotes = " ".join(c["quote"] for c in ev["claims"])
        self.assertIsNotNone(PAPER_PAT.search(quotes))

    def test_quotes_exact_in_sources(self):
        if not SOURCES:
            self.skipTest("W23WCH_SOURCES not set")
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
