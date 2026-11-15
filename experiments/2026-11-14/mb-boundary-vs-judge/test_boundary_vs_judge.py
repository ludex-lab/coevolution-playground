"""Tests for the mb-boundary-vs-judge method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
The quote check reads the source copy named in paper_evidence.json from the
directories listed in $MBBOUNDARY_SOURCES (os.pathsep separated). There is
no default: when the variable is unset, or the file is absent, that check
is skipped.

Done-when mapping (Morning Brief 2026-11-14, experiment #1):
  (a) test_a_arm_a_catches_every_planted_forbidden_write
  (b) test_b_arm_b_lets_a_planted_forbidden_write_through
  (c) test_c_arm_b_gold_agreement_reported_honestly
  (d) test_d_no_judge_voting_no_paid_api
  optional gate: test_gate_lossy_digest_rejects_valid_and_misses_forbidden
  paper figures: test_e_paper_numbers_on_unmeasured
"""

import ast
import copy
import hashlib
import itertools
import json
import os
import random
import re
import unittest

import boundary_vs_judge as M
import fixtures as F
import oracle as O

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("MBBOUNDARY_SOURCES")
SLUG = "mb-boundary-vs-judge"
DAY_HEADER = "# experiments/2026-11-14\n"
ROW_START = "- [%s](%s/): " % (SLUG, SLUG)
ROW_PREFIX = "- [%s](" % SLUG
ROW_END = ("(Soft method sketch of [arXiv 2611.14581](https://arxiv.org/abs/2611.14581);"
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
CODE = ("boundary_vs_judge.py", "oracle.py", "fixtures.py")
PY = CODE + ("test_boundary_vs_judge.py", "mutants.py")
ALL = PY + ("README.md", "NOTICE", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
STDLIB_PERMITTED = {"ast", "copy", "hashlib", "io", "itertools", "json", "os", "random",
                    "re", "sys", "unittest",
                    "boundary_vs_judge", "oracle", "fixtures", "test_boundary_vs_judge"}
CODE_IMPORTS = {"boundary_vs_judge.py": {"random"}, "oracle.py": set(),
                "fixtures.py": {"copy", "boundary_vs_judge", "oracle"}}
NO_GO_TOKENS = ("vo" + "te", "vo" + "ting", "ensem" + "ble", "major" + "ity",
                "api" + "_key", "api" + "key", "open" + "ai", "anthro" + "pic",
                "envi" + "ron", "http" + "://", "https" + "://", "sub" + "process",
                "sock" + "et", "url" + "lib")
ABS_PATHS = ("/" + "workspace", "/" + "tmp", "/" + "home")
MARKERS = ("<" * 7, "=" * 7, ">" * 7)
PAPER_PAT = re.compile(r"\d+\.\d+\s*%|\b98\.2\b|\b56\.2\b|\b11\.1\b|" + "2," + "160|10 " + "to 11|"
                       + "all " + "11|passed " + "6|120 " + "episodes|11 " + "episodes")


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


SEED = F.JUDGE_SEED


def ep(name):
    return F.episodes()[name]


def run(name, seed=SEED):
    return M.evaluate(ep(name), seed)


def planted():
    return [(name, i) for name, lab in F.LABELS.items() for i in lab[0]]


def planted_episodes():
    return sorted(set(name for name, _ in planted()))


def arm_a_tuple(rec):
    a = rec["arm_a"]
    return (rec["gold"]["verdict"], rec["gold"]["diff"], a["verdict"], a["class"], a["flags"],
            a["missing"])


def oracle_tuple(o):
    return (o["gold"], o["diff"], o["arm_a"], o["class"], o["flags"], o["missing"])


class SubStr(str):
    pass


class SubInt(int):
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


def containers(obj, out):
    """Collect the id of every dict, list and tuple reachable from obj."""
    if isinstance(obj, (dict, list, tuple)):
        out.add(id(obj))
        items = list(obj.keys()) + list(obj.values()) if isinstance(obj, dict) else obj
        for x in items:
            containers(x, out)
    return out


class TestDoneWhen(unittest.TestCase):

    def test_a_arm_a_catches_every_planted_forbidden_write(self):
        pl = planted()
        self.assertEqual(len(pl), 7)
        for name, i in pl:
            rec = run(name)
            self.assertEqual(rec["status"], M.OK, name)
            self.assertEqual(rec["arm_a"]["verdict"], M.FAIL, name)
            self.assertIn(i, [f[0] for f in rec["arm_a"]["flags"]], name)
            kind = dict(rec["arm_a"]["flags"])[i]
            want = M.FORBIDDEN if not ep(name)["expected_writes"] else M.UNEXPECTED_FLAG
            self.assertEqual(kind, want, name)
        # Clean episodes raise no flag.
        for name, lab in F.LABELS.items():
            if not lab[0]:
                self.assertEqual(run(name)["arm_a"]["flags"], (), name)
        # Whatever the final text says, the planted writes are still caught.
        texts = [e["final_text"] for e in F.episodes().values()] + ["", "Done.", "ERROR"]
        for name, i in pl:
            for t in texts:
                e = ep(name)
                e["final_text"] = t
                rec = M.evaluate(e, SEED)
                self.assertEqual(rec["arm_a"]["verdict"], M.FAIL, (name, t))
                self.assertIn(i, [f[0] for f in rec["arm_a"]["flags"]], (name, t))
        summary = F.summary()
        self.assertIn("arm A catches planted forbidden writes: 7/7", summary)

    def test_b_arm_b_lets_a_planted_forbidden_write_through(self):
        through = [n for n in planted_episodes() if run(n)["arm_b"]["verdict"] == M.PASS]
        self.assertGreaterEqual(len(through), 1)
        self.assertEqual(through, sorted(n for n in planted_episodes()
                                         if F.PINNED_ARM_B[n] == M.PASS))
        self.assertIn("air-forbidden-cancel", through)
        # The noise-free cue rule already passes every planted episode whose
        # text sounds successful; the stub never sees the write.
        base = [n for n in planted_episodes() if M.judge_base(ep(n)["final_text"]) == M.PASS]
        self.assertEqual(len(base), 6)
        # The result is not an artefact of one seed: on seeds 0..199 at
        # least one planted-forbidden episode passes every time.
        eps = [ep(n) for n in planted_episodes()]
        counts = [sum(1 for e in eps if M.evaluate(e, s)["arm_b"]["verdict"] == M.PASS)
                  for s in range(200)]
        self.assertGreaterEqual(min(counts), 1)
        self.assertEqual((min(counts), max(counts)), F.SEED_SWEEP_RANGE)
        self.assertIn("arm B passes planted-forbidden episodes: %d/7" % len(through),
                      F.summary())

    def test_c_arm_b_gold_agreement_reported_honestly(self):
        recs = [M.evaluate(e, SEED) for e in F.episodes().values()]
        ag = M.agreement(recs)
        gold = dict((n, lab[1]) for n, lab in F.LABELS.items())
        hand_a = sum(1 for n, lab in F.LABELS.items()
                     if (M.PASS if lab[2] in M.PASSING else M.FAIL) == gold[n])
        hand_b = sum(1 for n in F.LABELS if F.PINNED_ARM_B[n] == gold[n])
        self.assertEqual(ag["n"], 16)
        self.assertEqual(ag["config_error"], 0)
        with_bad = M.agreement(recs + [M.evaluate(None, SEED)])
        self.assertEqual((with_bad["n"], with_bad["config_error"]), (16, 1))
        self.assertEqual(with_bad["arm_b"], ag["arm_b"])
        self.assertEqual(ag["arm_a"]["agree"], hand_a)
        self.assertEqual(ag["arm_b"]["agree"], hand_b)
        self.assertEqual((hand_a, hand_b), (14, 8))
        self.assertEqual(ag["arm_b"]["agree"] + ag["arm_b"]["pass_gold_fail"]
                         + ag["arm_b"]["fail_gold_pass"], 16)
        self.assertEqual((ag["arm_b"]["pass_gold_fail"], ag["arm_b"]["fail_gold_pass"]), (6, 2))
        self.assertEqual((ag["arm_a"]["pass_gold_fail"], ag["arm_a"]["fail_gold_pass"]), (1, 1))
        summary = F.summary()
        self.assertIn("arm B vs gold agreement: 8/16 = 0.500", summary)
        self.assertIn("arm A vs gold agreement: 14/16 = 0.875", summary)
        # The README reports exactly the computed lines, as counts and
        # fractions on the frozen fixture, and says they are not comparable
        # with the paper.
        readme = read("README.md")
        for line in summary.splitlines()[17:]:
            self.assertIn(line, readme, line)
        flat = " ".join(readme.split())
        self.assertIn("not comparable with any figure in the paper", flat)
        self.assertNotRegex(summary, r"%")

    def test_d_no_judge_voting_no_paid_api(self):
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
        tree = ast.parse(read("boundary_vs_judge.py"))
        attrs = [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                 and isinstance(n.value, ast.Name) and n.value.id == "random"]
        self.assertEqual(attrs, ["Random"])
        fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "judge"][0]
        self.assertEqual([a.arg for a in fn.args.args], ["final_text", "seed"])
        loops = (ast.For, ast.While, ast.ListComp, ast.GeneratorExp, ast.SetComp, ast.DictComp)
        self.assertEqual([n for n in ast.walk(fn) if isinstance(n, loops)], [])
        draws = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                 and n.func.value.id == "rng"]
        self.assertEqual(len(draws), 1)
        self.assertEqual([n for n in ast.walk(ast.parse(read("oracle.py")))
                          if isinstance(n, (ast.Import, ast.ImportFrom, ast.While))], [])
        # The same on the loaded code, not only the file: every function of
        # the module uses no voting, network or key names, and judge uses
        # only one private Random draw.
        for fname, fobj in sorted(vars(M).items()):
            if callable(fobj) and getattr(fobj, "__module__", None) == M.__name__ \
                    and hasattr(fobj, "__code__"):
                co = fobj.__code__
                low = "\n".join(co.co_names + co.co_varnames).lower()
                for tok in NO_GO_TOKENS:
                    self.assertNotIn(tok, low, (fname, tok))
        self.assertLessEqual(set(M.judge.__code__.co_names),
                             {"random", "Random", "judge_base", "randrange", "NOISE_ONE_IN",
                              "FAIL", "PASS"})
        self.assertEqual(M.judge.__code__.co_varnames, ("final_text", "seed", "rng", "verdict"))

    def test_e_paper_numbers_on_unmeasured(self):
        self.assertEqual(M.paper_results(), M.ON_UNMEASURED)
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["measured_here"], "on_unmeasured")
        nums = [c for c in ev["claims"] if "values" in c]
        vals = [v for c in nums for v in c["values"].values()]
        self.assertEqual(sorted(vals), sorted(["2," + "160", "120", "98" + ".2" + "%",
                                               "56" + ".2" + "%", "11", "10 " + "to 11", "6",
                                               "11", "11" + ".1" + "%"]))
        for c in nums:
            for v in c["values"].values():
                self.assertIn(v, c["quote"], c["id"])
        for c in ev["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")
            self.assertEqual(c["measured_here"], "on_unmeasured")
            self.assertTrue(c["on_unmeasured"])


class TestRules(unittest.TestCase):

    def test_classes_and_verdicts(self):
        for name, lab in F.LABELS.items():
            rec = run(name)
            self.assertEqual(rec["gold"]["verdict"], lab[1], name)
            self.assertEqual(rec["arm_a"]["class"], lab[2], name)
            self.assertEqual(rec["arm_a"]["flags"], lab[3], name)
            self.assertEqual(M.judge_base(ep(name)["final_text"]), lab[4], name)
            self.assertEqual(rec["arm_b"]["verdict"], F.PINNED_ARM_B[name], name)
            self.assertEqual(rec["arm_b"]["seed"], SEED)
            self.assertEqual(rec["arm_a"]["verdict"],
                             M.PASS if lab[2] in M.PASSING else M.FAIL, name)

    def test_disagreements_are_the_declared_ones(self):
        # Arm A checks occurrence, not values: a wrong value on the expected
        # target passes Arm A and fails gold.
        rec = run("retail-wrong-value")
        self.assertEqual((rec["arm_a"]["verdict"], rec["gold"]["verdict"]), (M.PASS, M.FAIL))
        self.assertEqual(rec["gold"]["diff"], (("O3", "address"),))
        # A forbidden write that leaves the state unchanged passes gold and
        # fails Arm A.
        rec = run("retail-forbidden-noop")
        self.assertEqual((rec["arm_a"]["verdict"], rec["gold"]["verdict"]), (M.FAIL, M.PASS))
        # A claimed but absent write.
        rec = run("air-missed-write")
        self.assertEqual(rec["arm_a"]["missing"], (("cancel_reservation", "R5"),))
        self.assertEqual(M.judge_base(ep("air-missed-write")["final_text"]), M.PASS)
        # A correct refusal fails the cue rule.
        for name in ("air-refuse-ok", "retail-refuse-delivered"):
            self.assertEqual(M.judge_base(ep(name)["final_text"]), M.FAIL, name)
            self.assertEqual(run(name)["gold"]["verdict"], M.PASS, name)
        # A forbidden write behind a refusal text: the stub fails it only
        # because of the wording.
        self.assertEqual(M.judge_base(ep("air-forbidden-refusal-text")["final_text"]), M.FAIL)

    def test_partial_and_repeated_expected_writes(self):
        e = ep("retail-forbidden-extra")
        e["expected_writes"].append({"tool": "cancel_pending_order", "target": "O6"})
        rec = M.evaluate(e, SEED)
        self.assertEqual((rec["arm_a"]["class"], rec["arm_a"]["flags"]), (M.COMMIT_OK, ()))
        e = ep("retail-address-ok")
        e["expected_writes"].append({"tool": "return_delivered_order_items", "target": "O1"})
        rec = M.evaluate(e, SEED)
        self.assertEqual(rec["arm_a"]["class"], M.MISSED)
        self.assertEqual(rec["arm_a"]["missing"], (("return_delivered_order_items", "O1"),))
        e = ep("air-cancel-ok")
        e["writes"].append(copy.deepcopy(e["writes"][0]))
        self.assertEqual(M.evaluate(e, SEED)["arm_a"]["class"], M.COMMIT_OK)

    def test_arm_a_reads_neither_text_nor_values_nor_gold(self):
        texts = [e["final_text"] for e in F.episodes().values()] + ["", "error", "Done!"]
        for name in F.EPISODES:
            base = run(name)["arm_a"]
            for t in texts:
                e = ep(name)
                e["final_text"] = t
                self.assertEqual(M.evaluate(e, SEED)["arm_a"], base, (name, t))
            e = ep(name)
            for w in e["writes"]:
                for f in w["set"]:
                    w["set"][f] = "zz-" + w["set"][f]
            for t in e["gold_state"]:
                for f in e["gold_state"][t]:
                    e["gold_state"][t][f] = "gold-" + e["gold_state"][t][f]
            self.assertEqual(M.evaluate(e, SEED)["arm_a"], base, name)

    def test_arm_b_sees_only_the_final_text(self):
        for name in F.EPISODES:
            rec = run(name)
            self.assertEqual(rec["arm_b"]["verdict"], M.judge(ep(name)["final_text"], SEED))
            e = ep(name)
            e["writes"] = []
            e["expected_writes"] = []
            e["gold_state"] = copy.deepcopy(e["initial_state"])
            self.assertEqual(M.evaluate(e, SEED)["arm_b"], rec["arm_b"], name)
            e = ep(name)
            target = sorted(e["initial_state"])[0]
            field = sorted(e["initial_state"][target])[0]
            tool = M.DOMAINS[e["domain"]][0]
            e["writes"] = [{"tool": tool, "target": target, "set": {field: "x"}}] * 3
            self.assertEqual(M.evaluate(e, SEED)["arm_b"], rec["arm_b"], name)
        # Same text, same verdict, whatever the episode.
        a, b = ep("air-forbidden-cancel"), ep("air-info-ok")
        b["final_text"] = a["final_text"]
        self.assertEqual(M.evaluate(a, SEED)["arm_b"], M.evaluate(b, SEED)["arm_b"])

    def test_seed_is_used_and_explicit(self):
        def vector(seed):
            return tuple(M.evaluate(e, seed)["arm_b"]["verdict"] for e in F.episodes().values())
        vs = set(vector(s) for s in range(30))
        self.assertGreater(len(vs), 1)
        self.assertEqual(vector(SEED), vector(SEED))
        self.assertEqual(vector(SEED), tuple(F.PINNED_ARM_B[n] for n in F.EPISODES))
        self.assertNotEqual(vector(SEED), tuple(F.LABELS[n][4] for n in F.EPISODES))
        for bad in (None, True, 1.0, "1", SubInt(SEED), [SEED]):
            rec = M.evaluate(ep("air-cancel-ok"), bad)
            self.assertEqual((rec["status"], rec["detail"]), (M.CONFIG_ERROR, "seed_invalid"))
        self.assertEqual(M.evaluate(ep("air-cancel-ok"), -3)["status"], M.OK)

    def test_no_global_random_state(self):
        random.seed(1)
        before = random.getstate()
        a = [r["arm_b"] for r, _ in F.run_all().values()]
        self.assertEqual(random.getstate(), before)
        random.seed(2)
        b = [r["arm_b"] for r, _ in F.run_all().values()]
        self.assertEqual(a, b)

    def test_noise_rate_is_declared(self):
        texts = ["text %d" % i for i in range(400)]
        flips = sum(1 for t in texts if M.judge(t, 7) != M.judge_base(t))
        self.assertEqual(M.NOISE_ONE_IN, 4)
        self.assertTrue(60 <= flips <= 140, flips)


class TestGate(unittest.TestCase):

    def test_gate_full_evidence_matches_policy_label(self):
        for name, (req, valid, _) in F.gate_cases().items():
            rec = M.gate(req, [])
            self.assertEqual(rec["status"], M.OK, name)
            self.assertEqual(rec["decision"], M.PERMIT if valid else M.REJECT, name)
            self.assertEqual(rec["seen"], tuple(sorted(M.GATE_FIELDS)), name)

    def test_gate_lossy_digest_rejects_valid_and_misses_forbidden(self):
        cases = F.gate_cases()
        lossy = dict((n, M.gate(r, list(F.LOSSY_DROP))) for n, (r, _, _) in cases.items())
        for rec in lossy.values():
            self.assertEqual(rec["seen"], ("request_text", "tool"))
        rejected_valid = [n for n, (_, v, _) in cases.items()
                          if v and lossy[n]["decision"] == M.REJECT]
        missed_forbidden = [n for n, (_, v, _) in cases.items()
                            if not v and lossy[n]["decision"] == M.PERMIT]
        self.assertEqual(rejected_valid, ["G1-valid-indirect"])
        self.assertEqual(missed_forbidden, ["G2-forbidden-flown", "G3-forbidden-unauth"])
        # The boundary check still flags the write each missed request stands for.
        for n in missed_forbidden:
            rec = run(cases[n][2])
            self.assertEqual(rec["arm_a"]["class"], M.PREMATURE, n)
            self.assertEqual(rec["arm_a"]["flags"], ((0, M.FORBIDDEN),), n)
        # Dropping only one of the two fields is as lossy.
        for drop in (["customer_auth"], ["order_status"]):
            self.assertEqual(M.gate(cases["G2-forbidden-flown"][0], drop)["decision"], M.PERMIT)

    def test_gate_matches_oracle_exhaustively(self):
        n = 0
        drops = ([], ["customer_auth"], ["order_status"], ["customer_auth", "order_status"],
                 ["order_status", "customer_auth"])
        for tool in sorted(M.PERMITTED_STATUS):
            for text in ("please %s it" % M.REQUEST_VERB[tool], "please sort it out"):
                for auth in (True, False):
                    for status in ("booked", "pending", "delivered", "flown"):
                        for drop in drops:
                            req = {"tool": tool, "request_text": text, "customer_auth": auth,
                                   "order_status": status}
                            self.assertEqual(M.gate(req, list(drop))["decision"],
                                             O.reference_gate(req, drop), (req, drop))
                            n += 1
        self.assertEqual(n, 6 * 2 * 2 * 4 * 5)

    def test_gate_inputs(self):
        req = F.gate_cases()["G1-valid-indirect"][0]

        def cfg(r, d, detail):
            rec = M.gate(r, d)
            self.assertEqual((rec["status"], rec["detail"], rec["decision"]),
                             (M.CONFIG_ERROR, detail, None))

        cfg(None, [], "request_not_dict")
        cfg(SubDict(req), [], "request_not_dict")
        cfg(dict(req, extra=1), [], "request_fields_invalid")
        cfg(dict(req, tool="refund_everything"), [], "request_tool_unknown")
        cfg(dict(req, tool=SubStr("cancel_reservation")), [], "request_tool_unknown")
        cfg(dict(req, request_text=SubStr("x")), [], "request_text_invalid")
        cfg(dict(req, customer_auth=1), [], "customer_auth_invalid")
        cfg(dict(req, order_status=" "), [], "order_status_invalid")
        cfg(dict(req, order_status=SubStr("booked")), [], "order_status_invalid")
        cfg(req, ("customer_auth",), "drop_invalid")
        cfg(req, SubList(["customer_auth"]), "drop_invalid")
        cfg(req, ["tool"], "drop_invalid")
        cfg(req, ["customer_auth", "customer_auth"], "drop_invalid")
        cfg(req, [SubStr("customer_auth")], "drop_invalid")
        key = Spoof("tool")
        r = dict(req)
        tool = r.pop("tool")
        r[key] = tool
        n0 = key.n
        cfg(r, [], "request_key_invalid")
        self.assertEqual(key.n, n0)
        real = M._gate_decide

        def boom(digest):
            raise OverflowError("boom")

        M._gate_decide = boom
        try:
            cfg(req, [], "internal_error")
        finally:
            M._gate_decide = real


class TestOracle(unittest.TestCase):

    def test_module_and_oracle_agree_on_all_fixtures(self):
        rows = F.run_all()
        self.assertEqual(len(rows), len(F.EPISODES))
        for name, (m, o) in rows.items():
            self.assertEqual(arm_a_tuple(m), oracle_tuple(o), name)
            self.assertEqual(M.judge_base(ep(name)["final_text"]),
                             O.reference_cue(ep(name)["final_text"]), name)
        self.assertIn("module vs oracle: %d/%d episodes agree" % (len(rows), len(rows)),
                      F.summary())

    def test_module_and_oracle_agree_exhaustively(self):
        """Every expected set and every write sequence of up to 3 writes on a
        two-reservation world, against three gold states."""
        tools = ("cancel_reservation", "update_passengers")
        pairs = [(t, r) for t in tools for r in ("R1", "R2")]
        alphabet = [{"tool": t, "target": r, "set": {"status": v}}
                    for t, r in pairs for v in ("cancelled", "booked")]
        golds = [{"R1": {"status": "booked"}, "R2": {"status": "booked"}},
                 {"R1": {"status": "cancelled"}, "R2": {"status": "booked"}},
                 {"R1": {"status": "booked"}, "R2": {"status": "cancelled"}}]
        n = 0
        for mask in range(16):
            exp = [{"tool": t, "target": r} for j, (t, r) in enumerate(pairs) if mask >> j & 1]
            for k in range(4):
                for seq in itertools.product(alphabet, repeat=k):
                    for gold in golds:
                        e = {"episode_id": "x", "domain": "airline", "expected_writes": exp,
                             "initial_state": golds[0], "writes": list(seq),
                             "final_text": "ok", "gold_state": gold}
                        rec = M.evaluate(e, 0)
                        self.assertEqual(arm_a_tuple(rec), oracle_tuple(O.reference(e)), e)
                        if not exp and seq:
                            self.assertEqual(len(rec["arm_a"]["flags"]), k)
                        n += 1
        self.assertEqual(n, 16 * (1 + 8 + 8 ** 2 + 8 ** 3) * 3)

    def test_cue_rule_matches_oracle(self):
        for t in [e["final_text"] for e in F.episodes().values()] + [
                "", "ERROR", "Could Not", "can't", "It failed.", "not eligible", "fine"]:
            self.assertEqual(M.judge_base(t), O.reference_cue(t), t)

    def test_oracle_is_a_separate_code_path(self):
        tree = ast.parse(read("oracle.py"))
        self.assertEqual([x for x in ast.walk(tree)
                          if isinstance(x, (ast.Import, ast.ImportFrom))], [])
        self.assertNotIn("boundary_vs_judge", read("oracle.py"))
        m_tree = ast.parse(read("boundary_vs_judge.py"))
        m_names = {x.id for x in ast.walk(m_tree) if isinstance(x, ast.Name)}
        m_names |= {x.attr for x in ast.walk(m_tree) if isinstance(x, ast.Attribute)}
        self.assertFalse({"oracle", "reference", "O"} & m_names)
        o_defs = {x.name for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)}
        m_defs = {x.name for x in ast.walk(m_tree) if isinstance(x, ast.FunctionDef)}
        self.assertEqual(o_defs & m_defs, set())


class TestInputs(unittest.TestCase):

    def cfg(self, e, detail=None, seed=SEED):
        rec = M.evaluate(e, seed)
        self.assertEqual(rec["status"], M.CONFIG_ERROR)
        for k in ("episode_id", "gold", "arm_a", "arm_b"):
            self.assertIsNone(rec[k])
        if detail is not None:
            self.assertEqual(rec["detail"], detail)

    def test_episode_shape(self):
        e = ep("air-cancel-ok")
        self.cfg(None, "episode_not_dict")
        self.cfg([e], "episode_not_dict")
        for f in M.EPISODE_FIELDS:
            x = copy.deepcopy(e)
            del x[f]
            self.cfg(x, f + "_missing")
        self.cfg(dict(e, planted=[0]), "episode_unknown_field")
        self.cfg(dict(e, episode_id=" "), "episode_id_invalid")
        self.cfg(dict(e, domain="rail"), "domain_invalid")
        self.cfg(dict(e, final_text=None), "final_text_invalid")
        self.cfg(dict(e, initial_state={}), "initial_state_invalid")
        self.cfg(dict(e, initial_state={"R1": {}}), "initial_state_row_invalid")
        self.cfg(dict(e, initial_state={"R1": {"status": 1}}), "initial_state_value_invalid")
        self.cfg(dict(e, initial_state={" ": {"status": "booked"}}),
                 "initial_state_target_invalid")
        self.cfg(dict(e, gold_state={"R2": {"status": "booked"}}), "gold_state_shape")
        self.cfg(dict(e, gold_state={"R1": {"fare": "x"}}), "gold_state_shape")
        self.cfg(dict(e, expected_writes=[{"tool": "cancel_pending_order", "target": "R1"}]),
                 "expected_tool_unknown")
        self.cfg(dict(e, expected_writes=[{"tool": "cancel_reservation", "target": "R9"}]),
                 "expected_target_unknown")
        self.cfg(dict(e, expected_writes=[{"tool": "cancel_reservation", "target": "R1"}] * 2),
                 "expected_duplicate")
        self.cfg(dict(e, expected_writes=[{"tool": "cancel_reservation"}]),
                 "expected_entry_invalid")
        self.cfg(dict(e, expected_writes=["cancel_reservation"]), "expected_entry_invalid")
        w = e["writes"][0]
        self.cfg(dict(e, writes=[dict(w, tool="cancel_pending_order")]), "write_tool_unknown")
        self.cfg(dict(e, writes=[dict(w, target="R9")]), "write_target_unknown")
        self.cfg(dict(e, writes=[dict(w, set={})]), "write_set_invalid")
        self.cfg(dict(e, writes=[dict(w, set={"fare": "x"})]), "write_set_invalid")
        self.cfg(dict(e, writes=[dict(w, set={"status": 0})]), "write_set_invalid")
        self.cfg(dict(e, writes=[dict(w, note="x")]), "write_fields_invalid")
        self.cfg(dict(e, writes=["cancel"]), "write_not_dict")

    def test_exact_types_in_every_value_slot(self):
        e = ep("air-forbidden-cancel")
        w = e["writes"][0]
        self.cfg(SubDict(e), "episode_not_dict")
        self.cfg(dict(e, episode_id=SubStr("x")), "episode_id_invalid")
        self.cfg(dict(e, domain=SubStr("airline")), "domain_invalid")
        self.cfg(dict(e, final_text=SubStr("ok")), "final_text_invalid")
        self.cfg(dict(e, writes=tuple(e["writes"])), "writes_invalid")
        self.cfg(dict(e, writes=SubList(e["writes"])), "writes_invalid")
        self.cfg(dict(e, writes=(x for x in e["writes"])), "writes_invalid")
        self.cfg(dict(e, expected_writes=()), "expected_writes_invalid")
        self.cfg(dict(e, expected_writes=SubList()), "expected_writes_invalid")
        self.cfg(dict(e, writes=[SubDict(w)]), "write_not_dict")
        self.cfg(dict(e, writes=[dict(w, tool=SubStr("cancel_reservation"))]),
                 "write_tool_unknown")
        self.cfg(dict(e, writes=[dict(w, target=SubStr("R3"))]), "write_target_unknown")
        self.cfg(dict(e, writes=[dict(w, set=SubDict(w["set"]))]), "write_set_invalid")
        self.cfg(dict(e, writes=[dict(w, set={"status": SubStr("cancelled")})]),
                 "write_set_invalid")
        self.cfg(dict(e, initial_state=SubDict(e["initial_state"])), "initial_state_invalid")
        self.cfg(dict(e, initial_state={"R3": SubDict({"status": "flown"})}),
                 "initial_state_row_invalid")
        self.cfg(dict(e, initial_state={"R3": {"status": SubStr("flown")}}),
                 "initial_state_value_invalid")
        self.cfg(dict(e, initial_state={SubStr("R3"): {"status": "flown"}}),
                 "initial_state_key_invalid")
        self.cfg(dict(e, gold_state={"R3": {SubStr("status"): "flown"}}),
                 "gold_state_key_invalid")
        x = ep("air-cancel-ok")
        self.cfg(dict(x, expected_writes=[SubDict(x["expected_writes"][0])]),
                 "expected_entry_invalid")
        self.cfg(dict(x, expected_writes=[{"tool": SubStr("cancel_reservation"),
                                           "target": "R1"}]), "expected_tool_unknown")
        self.cfg(dict(x, expected_writes=[{"tool": "cancel_reservation",
                                           "target": SubStr("R1")}]), "expected_target_unknown")

    def test_run_guard_maps_internal_error(self):
        real = M.boundary

        def boom(snap):
            raise OverflowError("boom")

        M.boundary = boom
        try:
            self.cfg(ep("air-cancel-ok"), "internal_error")
        finally:
            M.boundary = real

    def test_never_raises(self):
        for args in [(None, None), (1, 0), ({}, 0), ({"episode_id": "x"}, 0), ([], 0),
                     (ep("air-cancel-ok"), None), (dict(ep("air-cancel-ok"), writes=[[]]), 0)]:
            rec = M.evaluate(*args)
            self.assertEqual(rec["status"], M.CONFIG_ERROR, args)
        for args in [(None, None), ({}, []), ([], [])]:
            self.assertEqual(M.gate(*args)["status"], M.CONFIG_ERROR)

    def test_inputs_not_mutated(self):
        for name, e in F.episodes().items():
            e0 = copy.deepcopy(e)
            M.evaluate(e, SEED)
            O.reference(e)
            self.assertEqual(e, e0, name)


class TestKeysAndSnapshot(unittest.TestCase):
    """F1: exact-str keys before any lookup; scoring runs on a snapshot only."""

    def cfg(self, rec, detail):
        self.assertEqual((rec["status"], rec["detail"]), (M.CONFIG_ERROR, detail))
        self.assertIsNone(rec["arm_a"])

    def test_a1_spoofed_episode_key_is_config_error(self):
        for field in M.EPISODE_FIELDS:
            e = ep("air-forbidden-cancel")
            value = e.pop(field)
            key = Spoof(field)
            e[key] = value
            rec = M.evaluate(e, SEED)
            self.cfg(rec, "episode_key_invalid")
            self.assertEqual(key.n, 0, field)

    def test_a2b_validated_fail_stays_fail(self):
        """A spoofed write key whose comparison would empty the caller's write
        list cannot turn a caught forbidden write into a PASS."""
        plain = run("air-forbidden-cancel")
        self.assertEqual((plain["arm_a"]["verdict"], plain["arm_a"]["class"]),
                         (M.FAIL, M.PREMATURE))
        for field in M.WRITE_FIELDS:
            for flip in range(1, 12):
                e = ep("air-forbidden-cancel")
                box = {"e": e}

                def hook(n, flip=flip):
                    if n == flip:
                        box["e"]["writes"].clear()
                        box["e"]["expected_writes"].append(
                            {"tool": "cancel_reservation", "target": "R3"})

                w = e["writes"][0]
                value = w.pop(field)
                key = Spoof(field, hook)
                w[key] = value
                rec = M.evaluate(e, SEED)
                self.assertNotEqual(rec["status"], M.OK, (field, flip))
                self.cfg(rec, "write_key_invalid")
                self.assertEqual(key.n, 0, (field, flip))
                self.assertEqual(len(e["writes"]), 1, (field, flip))

    def test_a3_str_subclass_keys_and_values_rejected(self):
        class Two(str):
            def __eq__(self, other):
                return other in ("cancel_reservation", "update_passengers")

            __hash__ = str.__hash__

        e = ep("air-forbidden-cancel")
        e["writes"][0]["tool"] = Two("cancel_reservation")
        self.cfg(M.evaluate(e, SEED), "write_tool_unknown")
        for name, e in F.episodes().items():
            rec = M.evaluate(e, SEED)
            self.assertIs(type(rec["episode_id"]), str, name)
            for i, kind in rec["arm_a"]["flags"]:
                self.assertIs(type(i), int)
                self.assertIs(type(kind), str)

    def test_non_str_keys_rejected_at_every_level(self):
        bad_keys = (1, (1, 2), SubStr("x"), Spoof("other"))

        def put(d, k):
            d[k] = "v"

        for bad in bad_keys:
            e = ep("air-cancel-ok")
            e["expected_writes"][0][bad] = "x"
            self.cfg(M.evaluate(e, SEED), "expected_key_invalid")
            e = ep("air-cancel-ok")
            e["initial_state"][bad] = {"status": "booked"}
            self.cfg(M.evaluate(e, SEED), "initial_state_key_invalid")
            e = ep("air-cancel-ok")
            put(e["initial_state"]["R1"], bad)
            self.cfg(M.evaluate(e, SEED), "initial_state_key_invalid")
            e = ep("air-cancel-ok")
            put(e["gold_state"]["R1"], bad)
            self.cfg(M.evaluate(e, SEED), "gold_state_key_invalid")
            e = ep("air-cancel-ok")
            e["gold_state"][bad] = {"status": "booked"}
            self.cfg(M.evaluate(e, SEED), "gold_state_key_invalid")
            e = ep("air-cancel-ok")
            put(e["writes"][0], bad)
            self.cfg(M.evaluate(e, SEED), "write_key_invalid")
            e = ep("air-cancel-ok")
            put(e["writes"][0]["set"], bad)
            self.cfg(M.evaluate(e, SEED), "write_set_key_invalid")
            e = ep("air-cancel-ok")
            e[bad] = 1
            self.cfg(M.evaluate(e, SEED), "episode_key_invalid")
        key = Spoof("status")
        e = ep("air-cancel-ok")
        e["writes"][0]["set"] = {key: "cancelled"}
        self.cfg(M.evaluate(e, SEED), "write_set_key_invalid")
        self.assertEqual(key.n, 0)

    def test_scores_see_only_the_snapshot(self):
        seen = []
        real = M._run

        def spy(snap, seed):
            seen.append(snap)
            return real(snap, seed)

        M._run = spy
        try:
            for name, e in F.episodes().items():
                rec = M.evaluate(e, SEED)
                self.assertEqual(len(seen), 1, name)
                snap = seen.pop()
                self.assertEqual(containers(snap, set()) & containers(e, set()), set(), name)
                self.assertIs(type(snap["writes"]), tuple)
                self.assertIs(type(snap["expected"]), tuple)
                for w in snap["writes"]:
                    self.assertIs(type(w), dict)
                    self.assertIs(type(w["tool"]), str)
                    self.assertIs(type(w["set"]), dict)
                e["writes"].clear()
                e["expected_writes"].clear()
                e["final_text"] = "error"
                self.assertEqual(rec, real(snap, SEED), name)
        finally:
            M._run = real

    def test_caller_mutation_mid_run_changes_nothing(self):
        """The caller's objects are changed while the scores run (before the
        first score reads anything); every score still comes from the snapshot."""
        real = M.gold_score
        for name in F.EPISODES:
            clean = run(name)
            e = ep(name)

            def meddle(snap, e=e):
                e["writes"].clear()
                e["expected_writes"].clear()
                for t in e["initial_state"]:
                    for f in e["initial_state"][t]:
                        e["initial_state"][t][f] = "meddled"
                        e["gold_state"][t][f] = "meddled"
                e["final_text"] = "error"
                return real(snap)

            M.gold_score = meddle
            try:
                rec = M.evaluate(e, SEED)
            finally:
                M.gold_score = real
            self.assertEqual(rec, clean, name)

    def test_gate_digest_is_a_snapshot(self):
        req = F.gate_cases()["G2-forbidden-flown"][0]
        drop = list(F.LOSSY_DROP)
        real = M._gate_decide
        seen = []

        def spy(digest):
            seen.append(digest)
            req["request_text"] = "nothing here"
            drop.clear()
            return real(digest)

        M._gate_decide = spy
        try:
            rec = M.gate(req, drop)
        finally:
            M._gate_decide = real
        self.assertEqual(rec["decision"], M.PERMIT)
        self.assertEqual(sorted(seen[0]), ["request_text", "tool"])


class TestFixtures(unittest.TestCase):

    def test_expected_table(self):
        for name, (m, o) in F.run_all().items():
            lab = F.LABELS[name]
            self.assertEqual((m["gold"]["verdict"], m["arm_a"]["class"], m["arm_a"]["flags"]),
                             lab[1:4], name)

    def test_fixture_invariants(self):
        es = F.episodes()
        self.assertEqual(sorted(es), sorted(F.LABELS))
        self.assertEqual(sorted(es), sorted(F.PINNED_ARM_B))
        self.assertEqual(len(es), 16)
        self.assertEqual(sorted(set(e["domain"] for e in es.values())), ["airline", "retail"])
        for name, e in es.items():
            self.assertEqual(e["episode_id"], name)
            for i in F.LABELS[name][0]:
                self.assertLess(i, len(e["writes"]), name)
                w = e["writes"][i]
                self.assertNotIn({"tool": w["tool"], "target": w["target"]},
                                 e["expected_writes"], name)
        clean = [n for n, lab in F.LABELS.items() if not lab[0]]
        self.assertEqual(len(clean), 9)
        self.assertTrue(any(not es[n]["expected_writes"] for n in clean))
        self.assertTrue(any(es[n]["expected_writes"] for n in clean))
        for n, (_, _, ep_name) in F.gate_cases().items():
            self.assertIn(ep_name, es, n)

    def test_fixture_pins(self):
        self.assertEqual(F.JUDGE_SEED, 20261114)
        self.assertEqual(F.LOSSY_DROP, ["customer_auth", "order_status"])
        self.assertEqual(F.EPISODES["air-forbidden-cancel"]["writes"],
                         [{"tool": "cancel_reservation", "target": "R3",
                           "set": {"status": "cancelled"}}])
        self.assertEqual(len(F.GATE_CASES), 4)

    def test_fixtures_return_copies(self):
        e = F.episodes()
        e["air-cancel-ok"]["writes"].clear()
        g = F.gate_cases()
        g["G1-valid-indirect"][0]["customer_auth"] = False
        self.assertEqual(len(F.episodes()["air-cancel-ok"]["writes"]), 1)
        self.assertIs(F.gate_cases()["G1-valid-indirect"][0]["customer_auth"], True)

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
        dirty = ("an al" + "lowlist that ke" + "eps 12" + ".5 % in /" + "tmp per Check" + "er "
                 + "<" * 7)
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
        if LAYOUT == "flat":
            self.assertEqual(sum(1 for line in lines if line.startswith("- ")), 1)

    def test_no_paper_claims_outside_evidence(self):
        for name in PY + ("README.md", "NOTICE", DAY):
            self.assertIsNone(PAPER_PAT.search(scan_text(name, read(name))), name)

    def test_readme_credits_differentiation_and_limits(self):
        flat = " ".join(read("README.md").split())
        ev = json.loads(read("paper_evidence.json"))
        self.assertIn(ev["paper"]["title"], flat)
        for author in ev["paper"]["authors"]:
            self.assertIn(author, flat)
        for s in ("**Soft** method sketch", "not a reproduction", "UNVERIFIED",
                  "on_unmeasured", "paper_evidence.json", "## Limits", "MIT", "CC BY 4.0",
                  "10.5281/zenodo.23683806", "not run", "python3 -B -m unittest",
                  "python3 -B mutants.py", "w22-write-precommit",
                  "evaluator-choice comparison", "gold final-state agreement",
                  "not a pre-commit write gate", "no timeout"):
            self.assertIn(s, flat, s)
        notice = " ".join(read("NOTICE").split())
        for s in (ev["paper"]["title"], "Sungbin Im", "arXiv:2611.14581",
                  "https://arxiv.org/abs/2611.14581", "10.5281/zenodo.23683806", "MIT",
                  "CC BY 4.0", "clean-room", "not run"):
            self.assertIn(s, notice, s)

    def test_evidence_shape(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.14581")
        self.assertIn("nonexclusive-distrib", ev["paper"]["licence"])
        self.assertFalse(ev["paper"]["pdf_read"])
        pkg = ev["replication_package"]
        self.assertEqual(pkg["doi"], "10.5281/zenodo.23683806")
        self.assertFalse(pkg["run"])
        self.assertIn("MIT", pkg["code_licence"])
        self.assertIn("CC BY 4.0", pkg["data_licence"])
        for c in ev["claims"]:
            self.assertEqual(len(c["quote"]), c["length"])

    def test_quotes_exact_in_sources(self):
        if not SOURCES:
            self.skipTest("MBBOUNDARY_SOURCES not set")
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
