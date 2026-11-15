"""Tests for the w24-trust-needs-feedback method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
The quote check reads the source copy named in paper_evidence.json from the
directories listed in $W24TNF_SOURCES (os.pathsep separated). There is no
default: when the variable is unset, or the file is absent, that check is
skipped.

Done-when mapping (Lab Dig 2 Wave24, Top: arXiv 2611.14833, verifier Build #2):
  1 test_1_fixture_three_advisors_two_conditions
  2 test_2_declared_prior_untrusted
  3 test_3_upgrade_only_on_valid_external_feedback
  4 test_4_one_negative_drops_within_one_round
  5 test_5_expected_end_state
  6 test_6_planted_spoofs_all_refused
  7 test_7_persuadable_baseline_relies_on_unhelpful
  8 test_8_controls_zero_false_alarms
  9 test_9_silence_resolves_to_declared_on_expiry
  10 test_10_no_human_data_no_network_paper_on_unmeasured
Order independence (review round 2): TestOrdering.
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
import trust_feedback as M

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W24TNF_SOURCES")
SLUG = "w24-trust-needs-feedback"
DAY_HEADER = "# experiments/2026-11-15\n"
ROW_START = "- [%s](%s/): " % (SLUG, SLUG)
ROW_PREFIX = "- [%s](" % SLUG
ROW_END = ("(Top method sketch of [arXiv 2611.14833](https://arxiv.org/abs/2611.14833);"
           " not a reproduction)")
MAIN_ROW_PREFIXES = ("- [mb-conversation-loss-oracle](",)
MAIN_ROW_SHA256 = {"- [mb-conversation-loss-oracle](":
                   "4cbad9b95da8c0e14d3845b23a36039d4b768af25a5ce84827dad1c72f09d83e"}
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
CODE = ("trust_feedback.py", "oracle.py", "fixtures.py")
PY = CODE + ("test_trust_feedback.py", "mutants.py")
ALL = PY + ("README.md", "NOTICE", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
STDLIB_PERMITTED = {"ast", "copy", "hashlib", "io", "itertools", "json", "os", "re", "sys",
                    "unittest", "trust_feedback", "oracle", "fixtures", "test_trust_feedback"}
CODE_IMPORTS = {"trust_feedback.py": set(), "oracle.py": set(),
                "fixtures.py": {"copy", "oracle", "trust_feedback"}}
NO_GO_TOKENS = ("sql" + "ite", "sql" + "3", "cur" + "sor", "data" + "base",
                "sock" + "et", "url" + "lib", "http" + "://", "https" + "://", "requ" + "ests",
                "sub" + "process", "envi" + "ron", "api" + "_key", "api" + "key",
                "open" + "ai", "anthro" + "pic", "vo" + "te", "ensem" + "ble",
                "thre" + "ad", "sched" + "ule", "ti" + "me.", "date" + "time",
                "rand" + "om", "partici" + "pant", "sur" + "vey")
ABS_PATHS = ("/" + "workspace", "/" + "tmp", "/" + "home")
MARKERS = ("<" * 7, "=" * 7, ">" * 7)
PAPER_PAT = re.compile(r"\d+(?:\.\d+)?\s*%|\b4" + r" experiments\b|Experiment" + r" 4\b|"
                       r"\b(?:67|48|83)\s+vs\b|\bvs\.?\s+(?:21|38|65)\b")


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


class SubInt(int):
    pass


class SubFloat(float):
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


def small(events, bar=1, max_age=1, pending=(), conf=(0.2, 0.2, 0.2),
          truth=(True, False, True), sources=("ext",)):
    """A three-round session of advisor "A" with external source(s) "ext"..."""
    return {"case_id": "x", "condition": "feedback", "advisor_id": "A", "rounds": 3,
            "truth": list(truth),
            "advice": [{"round": r, "confidence": conf[r - 1], "claim": "c", "prestige": "p"}
                       for r in (1, 2, 3)],
            "external_sources": list(sources), "max_age": max_age, "trust_bar": bar,
            "feedback": [dict(e) for e in events], "pending": [dict(p) for p in pending]}


def ev(source, advisor, rnd, at, outcome):
    return {"source": source, "advisor_id": advisor, "round": rnd, "at": at, "outcome": outcome}


VALID = [ev("ext", "A", r, a, o) for r in (1, 2, 3) for a in (1, 2, 3)
         for o in (M.CORRECT, M.INCORRECT)]
FULL = [ev(s, adv, r, a, o) for s in ("ext", "A", "x") for adv in ("A", "B")
        for r in (0, 1, 2, 3, 4) for a in (1, 2, 3) for o in (M.CORRECT, M.INCORRECT)]


TWO = ("ext", "ext2")
# Two declared sources, every round, arrival at age 0 or 1, both outcomes:
# the review's ordering space (20 events).
POOL2 = [ev(s, "A", r, a, o) for s in TWO for r in (1, 2, 3) for a in (1, 2, 3)
         for o in (M.CORRECT, M.INCORRECT) if 0 <= a - r <= 1]
# One pending decision per (round, deadline) shape, each with its own on_expiry.
PENDS6 = [{"pending_id": "p%d%d" % (r, d), "round": r, "deadline": d, "on_expiry": x}
          for (r, d), x in zip(((1, 1), (1, 2), (1, 3), (2, 2), (2, 3), (3, 3)),
                               M.ON_EXPIRY + M.ON_EXPIRY)]


def seqs(alphabet, upto):
    for n in range(upto + 1):
        for s in itertools.product(alphabet, repeat=n):
            yield s


def space_valid():
    """Up to three events over the valid-shaped alphabet, four configurations."""
    for bar, age in itertools.product((1, 2), (0, 1)):
        for s in seqs(VALID, 3):
            yield small(s, bar, age)


def space_refusals():
    """Up to two events over the full alphabet (every refusal reason)."""
    for s in seqs(FULL, 2):
        yield small(s, 1, 1)


def space_pending():
    """Up to two valid events, with one pending decision of every shape."""
    pends = [{"pending_id": "p", "round": r, "deadline": d, "on_expiry": x}
             for r in (1, 2, 3) for d in range(r, 4) for x in M.ON_EXPIRY]
    for s in seqs(VALID, 2):
        for p in pends:
            yield small(s, 2, 1, (p,))


def space_baseline():
    """Every confidence triple over four values, with up to one valid event."""
    for conf in itertools.product((0.0, 0.49, 0.5, 1.0), repeat=3):
        for s in seqs(VALID, 1):
            yield small(s, 1, 1, conf=conf)


def space_two_source():
    """Up to three events over the two-source pool (same-round conflicts across
    sources and arrivals), trust bars 1 and 2, six pending decisions."""
    for bar in (1, 2):
        for s in seqs(POOL2, 3):
            yield small(s, bar, 1, PENDS6, sources=TWO)


def long_session(conf, events):
    """A session of len(conf) rounds of advisor "A" (baseline boundaries)."""
    n = len(conf)
    c = small(events)
    c["rounds"], c["truth"] = n, [r % 2 == 1 for r in range(1, n + 1)]
    c["advice"] = [{"round": r, "confidence": conf[r - 1], "claim": "c", "prestige": "p"}
                   for r in range(1, n + 1)]
    return c


def space_baseline_long():
    """Five rounds, every confidence over three values, with and without an
    early negative (the level climbs back only over several rounds)."""
    for conf in itertools.product((0.49, 0.5, 1.0), repeat=5):
        for s in ((), (ev("x", "B", 9, 1, M.INCORRECT),)):
            yield long_session(conf, s)


SPACES = (("valid", space_valid, 24700), ("refusals", space_refusals, 32581),
          ("pending", space_pending, 8232), ("baseline", space_baseline, 1216),
          ("baseline-long", space_baseline_long, 486),
          ("two-source", space_two_source, 16842))


class TestDoneWhen(unittest.TestCase):

    def test_1_fixture_three_advisors_two_conditions(self):
        self.assertEqual(F.N, 10)
        self.assertEqual([sum(F.TRACKS[a]) for a in "HUM"], [10, 0, 5])
        for group, cond in ((F.FEEDBACK, "feedback"), (F.NO_FEEDBACK, "no_feedback")):
            self.assertEqual([case(n)["advisor_id"] for n in group], ["H", "U", "M"])
            for n in group:
                c = case(n)
                self.assertEqual(c["condition"], cond)
                self.assertEqual(c["rounds"], 10)
                self.assertEqual(len(c["feedback"]), 10 if cond == "feedback" else 0)
                self.assertEqual(c["truth"], F.TRACKS[c["advisor_id"]])

    def test_2_declared_prior_untrusted(self):
        self.assertEqual(M.PRIOR, M.UNTRUSTED)
        for n, lab in F.LABELS.items():
            rec = run(n)
            if rec["status"] == M.OK:
                self.assertEqual(rec["reliance"][0], M.VERIFY, n)
        for c in space_valid():
            self.assertEqual(M.evaluate(c)["reliance"][0], M.VERIFY)

    def test_3_upgrade_only_on_valid_external_feedback(self):
        # Fixture: the advisor's confidence, claim and prestige never move the rule.
        for n in F.LABELS:
            c = case(n)
            rec = M.evaluate(c)
            if rec["status"] != M.OK:
                continue
            for conf, claim, prestige in ((1.0, "trust me", "famous"), (0.0, "", "")):
                x = copy.deepcopy(c)
                for a in x["advice"]:
                    a["confidence"], a["claim"], a["prestige"] = conf, claim, prestige
                got = M.evaluate(x)
                for k in ("reliance", "final", "upgrades", "accepted", "refused", "pending"):
                    self.assertEqual(got[k], rec[k], (n, k))
            # The condition label is never read either.
            for cond in M.CONDITIONS:
                self.assertEqual(M.evaluate(dict(c, condition=cond))["reliance"],
                                 rec["reliance"], n)
        # Exhaustive: an upgrade needs trust_bar accepted "correct" events; every
        # accepted event passes each declared check, boundary inclusive.
        for _, gen, _ in SPACES:
            for c in gen():
                rec = M.evaluate(c)
                pos = [a for a in rec["accepted"] if a[2] == M.CORRECT]
                if rec["upgraded"]:
                    self.assertGreaterEqual(len(set(a[1] for a in pos)), c["trust_bar"])
                if not pos:
                    self.assertNotIn(M.RELY, rec["reliance"])
                for i, rnd, _ in rec["accepted"]:
                    e = c["feedback"][i]
                    self.assertIn(e["source"], c["external_sources"])
                    self.assertEqual(e["advisor_id"], "A")
                    self.assertTrue(1 <= rnd <= e["at"])
                    self.assertLessEqual(e["at"] - rnd, c["max_age"])
                keys = [(c["feedback"][i]["source"], rnd, out) for i, rnd, out in rec["accepted"]]
                self.assertEqual(len(set(keys)), len(keys))
        # Boundary: age == max_age accepted, max_age + 1 refused.
        self.assertEqual(M.evaluate(small([ev("ext", "A", 1, 2, M.CORRECT)], 1, 1))["accepted"],
                         ((0, 1, M.CORRECT),))
        self.assertEqual(M.evaluate(small([ev("ext", "A", 1, 3, M.CORRECT)], 1, 1))["refused"],
                         ((0, M.STALE),))
        self.assertEqual(M.evaluate(small([ev("ext", "A", 1, 1, M.CORRECT)], 1, 0))["accepted"],
                         ((0, 1, M.CORRECT),))

    def test_4_one_negative_drops_within_one_round(self):
        rec = run("S-feedback-switch")
        self.assertEqual(rec["reliance"], (M.VERIFY,) * 3 + (M.RELY,) * 4 + (M.VERIFY,) * 3)
        self.assertEqual(rec["relied_wrong"], 1)
        self.assertEqual(rec["final"], M.UNTRUSTED)
        for c in itertools.chain(space_valid(), space_refusals(), space_two_source()):
            rec = M.evaluate(c)
            for i, rnd, out in rec["accepted"]:
                at = c["feedback"][i]["at"]
                if out == M.INCORRECT and at < 3:
                    self.assertEqual(rec["reliance"][at], M.VERIFY)
            # Every timely, exact-source, round-matched negative is accepted,
            # unless the very same event was accepted already (a replay).
            why = dict(rec["refused"])
            for i, e in enumerate(c["feedback"]):
                if (e["outcome"] == M.INCORRECT and e["source"] in c["external_sources"]
                        and e["advisor_id"] == "A" and 0 <= e["at"] - e["round"] <= c["max_age"]
                        and 1 <= e["round"] <= 3):
                    if why.get(i) == M.DUPLICATE:
                        self.assertTrue(any(c["feedback"][j]["source"] == e["source"]
                                            and r == e["round"] and o == M.INCORRECT
                                            for j, r, o in rec["accepted"]), (c, i))
                    else:
                        self.assertIn((i, e["round"], M.INCORRECT), rec["accepted"])
        # A negative for a round that already has an accepted "correct" still drops it.
        for evs in ([ev("ext", "A", 1, 1, M.CORRECT), ev("ext2", "A", 1, 2, M.INCORRECT)],
                    [ev("ext", "A", 1, 1, M.CORRECT), ev("ext", "A", 1, 2, M.INCORRECT)]):
            rec = M.evaluate(small(evs, 1, 1, sources=TWO))
            self.assertEqual(rec["reliance"], (M.VERIFY, M.RELY, M.VERIFY), evs)

    def test_5_expected_end_state(self):
        recs = [M.evaluate(c) for c in F.cases().values()]
        tot = M.totals(recs, (("fb", F.FEEDBACK), ("nf", F.NO_FEEDBACK)))
        self.assertEqual(tot, {"fb": (1, 3), "nf": (0, 3)})
        self.assertEqual([run(n)["final"] for n in F.FEEDBACK],
                         [M.TRUSTED, M.UNTRUSTED, M.UNTRUSTED])
        m = run("M-feedback")
        self.assertEqual(m["upgrades"], 0)
        score, top = 0, 0
        for _, _, out in m["accepted"]:
            score = score + 1 if out == M.CORRECT else 0
            top = max(top, score)
        self.assertLess(top, F.BAR)
        for n in F.NO_FEEDBACK:
            rec = run(n)
            self.assertEqual((rec["upgraded"], rec["reliance"]), (False, (M.VERIFY,) * 10), n)
        # The declared cost: the helpful advisor stays untrusted and is verified 10/10.
        self.assertEqual(run("H-no-feedback")["verified_right"], 10)

    def test_6_planted_spoofs_all_refused(self):
        self.assertGreaterEqual(len(F.SPOOFS), 6)
        for n in F.SPOOFS:
            rec = run(n)
            want = F.SPOOF_REASON[n]
            if want == "config_error":
                self.assertEqual(rec["status"], M.CONFIG_ERROR, n)
                continue
            self.assertEqual((rec["upgraded"], rec["accepted"]), (False, ()), n)
            self.assertNotIn(M.RELY, rec["reliance"], n)
            c = case(n)
            self.assertEqual(len(rec["refused"]), len(c["feedback"]), n)
            self.assertEqual(set(w for _, w in rec["refused"]), set() if want is None else {want})
        self.assertEqual(run("SP2-str-subclass-source")["detail"], "event_source_invalid")
        self.assertEqual(run("SP3-colliding-source-key")["detail"], "event_key_invalid")
        # Each spoof is the only thing standing between U and an upgrade:
        # the same events made genuine would upgrade it.
        for n in ("SP1-self-sourced", "SP5-other-advisor", "SP8-undeclared-source"):
            c = case(n)
            for e in c["feedback"]:
                e["source"], e["advisor_id"] = F.SOURCE, "U"
            self.assertTrue(M.evaluate(c)["upgraded"], n)
        # Replay is refused too: one genuine event repeated counts once.
        c = case("U-no-feedback")
        c["feedback"] = [F.event(1, 1, M.CORRECT)] * 5
        rec = M.evaluate(c)
        self.assertEqual((rec["upgraded"], len(rec["accepted"])), (False, 1))
        self.assertEqual(set(w for _, w in rec["refused"]), {M.DUPLICATE})
        # A declared external set that names the advisor still refuses it.
        c = case("SP1-self-sourced")
        c["external_sources"] = [F.SOURCE, "U"]
        self.assertEqual(set(w for _, w in M.evaluate(c)["refused"]), {M.SELF_SOURCED})
        # Every refusal reason occurs in the exhaustive spaces.
        seen = set()
        for c in space_refusals():
            seen |= set(w for _, w in M.evaluate(c)["refused"])
        self.assertEqual(seen, set(M.REASONS))

    def test_7_persuadable_baseline_relies_on_unhelpful(self):
        u = run("U-no-feedback")["baseline"]
        self.assertTrue(u["final_relied"])
        self.assertEqual((u["reliance"], u["relied_wrong"]), ((M.RELY,) * 10, 10))
        self.assertEqual(run("SP7-confident-claim")["baseline"]["relied_wrong"], 10)
        self.assertEqual(run("M-no-feedback")["baseline"]["relied_wrong"], 5)
        self.assertFalse(run("U-feedback")["baseline"]["final_relied"])
        self.assertEqual(run("U-feedback")["baseline"]["relied_wrong"], 1)
        # The rule arm never relies on U in any fixture.
        for n in F.LABELS:
            rec = run(n)
            if rec["status"] == M.OK and case(n)["advisor_id"] == "U":
                self.assertEqual(rec["relied_wrong"], 0, n)

    def test_8_controls_zero_false_alarms(self):
        self.assertEqual(len(F.CONTROLS), 3)
        alarms = [n for n in F.CONTROLS if not F.control_ok(n, run(n))]
        self.assertEqual(alarms, [])
        c3 = run("C3-H-at-max-age")
        self.assertEqual(len(c3["accepted"]), 9)
        for i, rnd, _ in c3["accepted"]:
            self.assertEqual(case("C3-H-at-max-age")["feedback"][i]["at"] - rnd, F.MAX_AGE)
        self.assertEqual(run("H-feedback")["reliance"], (M.VERIFY,) * 3 + (M.RELY,) * 7)
        self.assertFalse(F.control_ok("M-feedback", dict(run("M-feedback"), upgraded=True)))
        self.assertFalse(F.control_ok("H-feedback", dict(run("H-feedback"), upgraded=False)))
        self.assertFalse(F.control_ok("C3-H-at-max-age",
                                      dict(c3, refused=((0, M.STALE),))))

    def test_9_silence_resolves_to_declared_on_expiry(self):
        self.assertEqual(set(M.ON_EXPIRY), {"DENY", "SAFE_FALLBACK", "ESCALATE", "HOLD"})
        pe = run("PE-no-feedback-expiry")["pending"]
        self.assertEqual(pe, (("deny", "DENY", 6), ("fallback", "SAFE_FALLBACK", 6),
                              ("escalate", "ESCALATE", 7), ("hold", "HOLD", 5)))
        self.assertEqual(run("PS-stale-is-silence")["pending"], (("stale", "HOLD", 8),))
        self.assertEqual(run("H-feedback")["pending"], (("h-r5", M.RELY, 5),))
        for c in itertools.chain(space_pending(), space_two_source()):
            rec = M.evaluate(c)
            for (pid, res, at), p in zip(rec["pending"], c["pending"]):
                arr = dict((o, [c["feedback"][i]["at"] for i, rnd, out in rec["accepted"]
                                if out == o and rnd == p["round"]
                                and c["feedback"][i]["at"] <= p["deadline"]])
                           for o in M.OUTCOMES)
                if arr[M.INCORRECT]:
                    self.assertEqual((res, at), (M.DO_NOT_RELY, min(arr[M.INCORRECT])))
                elif arr[M.CORRECT]:
                    self.assertEqual((res, at), (M.RELY, min(arr[M.CORRECT])))
                else:
                    self.assertEqual((res, at), (p["on_expiry"], p["deadline"]))
                    self.assertNotEqual(res, M.RELY)
        base = case("PE-no-feedback-expiry")
        for bad, detail in ((None, "on_expiry_missing"), ("RELY", "on_expiry_invalid"),
                            ("TRUST", "on_expiry_invalid"), ("deny", "on_expiry_invalid"),
                            (SubStr("DENY"), "on_expiry_invalid"), (1, "on_expiry_invalid")):
            c = copy.deepcopy(base)
            if bad is None:
                del c["pending"][0]["on_expiry"]
            else:
                c["pending"][0]["on_expiry"] = bad
            rec = M.evaluate(c)
            self.assertEqual((rec["status"], rec["detail"]), (M.CONFIG_ERROR, detail), bad)

    def test_10_no_human_data_no_network_paper_on_unmeasured(self):
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
        for fn in (M.validate, M.refusal, M.rule, M.resolve, M.baseline, M.score, M._run,
                   M.evaluate, M.totals, O.reference):
            names = " ".join(fn.__code__.co_names).lower()
            for bad in NO_GO_TOKENS:
                self.assertNotIn(bad, names, (fn.__name__, bad))
        self.assertEqual(M.paper_results(), M.ON_UNMEASURED)
        ev_ = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev_["status"], "UNVERIFIED")
        self.assertEqual(ev_["measured_here"], "on_unmeasured")
        for c in ev_["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED", c["id"])
            self.assertEqual(c["measured_here"], "on_unmeasured", c["id"])
        self.assertFalse(ev_["code"]["linked_in_abstract"])


class TestRules(unittest.TestCase):

    def test_labels_match(self):
        self.assertEqual(list(F.LABELS), [c["case_id"] for c in F.CASES])
        for n, want in F.labels().items():
            rec = run(n)
            if want[0] == "config_error":
                self.assertEqual(rec["status"], M.CONFIG_ERROR, n)
                continue
            got = (rec["status"], rec["upgraded"], rec["final"],
                   rec["reliance"].count(M.RELY), rec["baseline"]["final_relied"])
            self.assertEqual(got, want, n)

    def test_refusal_order_table(self):
        rows = [(ev("A", "A", 1, 1, M.CORRECT), M.SELF_SOURCED),
                (ev("B", "B", 1, 1, M.CORRECT), M.SELF_SOURCED),
                (ev("x", "A", 1, 1, M.CORRECT), M.NOT_EXTERNAL),
                (ev("ext", "B", 1, 1, M.CORRECT), M.ADVISOR_MISMATCH),
                (ev("ext", "A", 0, 1, M.CORRECT), M.NO_SUCH_ROUND),
                (ev("ext", "A", 4, 3, M.CORRECT), M.NO_SUCH_ROUND),
                (ev("ext", "A", 3, 2, M.CORRECT), M.FUTURE_ROUND),
                (ev("ext", "A", 1, 3, M.CORRECT), M.STALE),
                (ev("x", "B", 4, 1, M.CORRECT), M.NOT_EXTERNAL)]
        for e, why in rows:
            self.assertEqual(M.evaluate(small([e]))["refused"], ((0, why),), e)
        # Replay is the exact same event (arrival aside); a fresh negative for a
        # graded round is not a replay.
        rec = M.evaluate(small([ev("ext", "A", 1, 1, M.CORRECT), ev("ext", "A", 1, 2, M.INCORRECT)]))
        self.assertEqual((rec["refused"], rec["reliance"]), ((), (M.VERIFY, M.RELY, M.VERIFY)))
        rec = M.evaluate(small([ev("ext", "A", 1, 1, M.CORRECT), ev("ext", "A", 1, 2, M.CORRECT)]))
        self.assertEqual(rec["refused"], ((1, M.DUPLICATE),))

    def test_trust_score_table(self):
        c, i = M.CORRECT, M.INCORRECT
        rows = [((c,), 1, (M.VERIFY, M.RELY, M.RELY), 1),
                ((c, i), 1, (M.VERIFY, M.RELY, M.VERIFY), 1),
                ((c, i, c), 1, (M.VERIFY, M.RELY, M.VERIFY), 2),
                ((c, c), 2, (M.VERIFY, M.VERIFY, M.RELY), 1),
                ((c, i, c), 2, (M.VERIFY, M.VERIFY, M.VERIFY), 0),
                ((i, c, c), 2, (M.VERIFY, M.VERIFY, M.VERIFY), 1)]
        for outs, bar, rel, ups in rows:
            evs = [ev("ext", "A", k + 1, k + 1, o) for k, o in enumerate(outs)]
            rec = M.evaluate(small(evs, bar))
            self.assertEqual((rec["reliance"], rec["upgrades"]), (rel, ups), (outs, bar))

    def test_events_read_by_arrival_round(self):
        evs = [ev("ext", "A", 2, 2, M.CORRECT), ev("ext", "A", 1, 1, M.INCORRECT)]
        rec = M.evaluate(small(evs, 1))
        self.assertEqual(rec["accepted"], ((1, 1, M.INCORRECT), (0, 2, M.CORRECT)))
        self.assertEqual(rec["reliance"], (M.VERIFY, M.VERIFY, M.RELY))
        # Same round: a negative wins its round whatever the list order.
        for evs in ([ev("ext", "A", 1, 2, M.CORRECT), ev("ext", "A", 2, 2, M.INCORRECT)],
                    [ev("ext", "A", 2, 2, M.INCORRECT), ev("ext", "A", 1, 2, M.CORRECT)]):
            self.assertEqual(M.evaluate(small(evs, 1))["reliance"], (M.VERIFY,) * 3)
        # Two "correct" in one round count twice towards the bar.
        evs = [ev("ext", "A", 1, 2, M.CORRECT), ev("ext", "A", 2, 2, M.CORRECT)]
        self.assertEqual(M.evaluate(small(evs, 2))["reliance"], (M.VERIFY, M.VERIFY, M.RELY))

    def test_baseline_table(self):
        rows = [((0.2, 0.2, 0.2), (), (M.RELY, M.RELY, M.RELY)),
                ((0.5, 0.5, 0.5), (), (M.RELY, M.RELY, M.RELY)),
                ((0.9, 0.2, 0.2), [ev("x", "B", 9, 1, M.INCORRECT)], (M.RELY, M.VERIFY, M.VERIFY)),
                ((0.9, 0.9, 0.9), [ev("x", "B", 9, 1, M.INCORRECT)], (M.RELY, M.VERIFY, M.VERIFY)),
                ((0.2, 0.9, 0.9), [ev("x", "B", 9, 1, M.INCORRECT)], (M.RELY, M.VERIFY, M.VERIFY)),
                ((0.9, 0.9, 0.2), [ev("ext", "A", 1, 1, M.CORRECT)], (M.RELY, M.RELY, M.RELY)),
                ((0.49, 0.9, 0.9), [ev("ext", "A", 1, 1, M.INCORRECT),
                                    ev("ext", "A", 2, 2, M.INCORRECT)],
                 (M.RELY, M.VERIFY, M.VERIFY))]
        for conf, evs, rel in rows:
            self.assertEqual(M.evaluate(small(evs, conf=conf))["baseline"]["reliance"], rel,
                             (conf, evs))
        c = small([ev("x", "B", 9, 1, M.INCORRECT)], conf=(0.9, 0.9, 0.9))
        c["rounds"] = 4
        c["truth"].append(True)
        c["advice"].append({"round": 4, "confidence": 0.9, "claim": "c", "prestige": "p"})
        self.assertEqual(M.evaluate(c)["baseline"]["reliance"],
                         (M.RELY, M.VERIFY, M.VERIFY, M.RELY))
        # Confidence exactly 1/2 counts as confident; just below does not.
        neg = [ev("x", "B", 9, 1, M.INCORRECT)]
        self.assertEqual(M.evaluate(long_session((0.9, 0.5, 0.5, 0.5), neg))["baseline"]
                         ["reliance"], (M.RELY, M.VERIFY, M.VERIFY, M.RELY))
        self.assertEqual(M.evaluate(long_session((0.9, 0.49, 0.5, 0.5), neg))["baseline"]
                         ["reliance"], (M.RELY, M.VERIFY, M.VERIFY, M.VERIFY))

    def test_scoring(self):
        rec = run("U-no-feedback")
        self.assertEqual((rec["relied_wrong"], rec["verified_right"]), (0, 0))
        rec = run("H-feedback")
        self.assertEqual((rec["relied_wrong"], rec["verified_right"]), (0, 3))
        self.assertEqual(M.score((M.RELY, M.VERIFY, M.RELY), (False, True, True)), (1, 1))

    def test_totals_skip_config_errors(self):
        recs = [M.evaluate(c) for c in F.cases().values()] + [M.evaluate(None)]
        tot = M.totals(recs, (("spoofs", F.SPOOFS), ("c", F.CONTROLS)))
        self.assertEqual(tot, {"spoofs": (0, 6), "c": (2, 3)})
        self.assertEqual(M.totals([], (("x", ("a",)),)), {"x": (0, 0)})


class TestOrdering(unittest.TestCase):
    """Review round 2: a timely negative always applies, whatever the order."""

    @staticmethod
    def view(c, rec):
        """Everything the decision depends on, with event indices replaced by
        event contents (indices move under a permutation, contents do not)."""
        fb = c["feedback"]
        acc = sorted((fb[i]["source"], rnd, fb[i]["at"], out) for i, rnd, out in rec["accepted"])
        ref = sorted((fb[i]["source"], fb[i]["round"], fb[i]["at"], fb[i]["outcome"], why)
                     for i, why in rec["refused"])
        rest = tuple(rec[k] for k in ("status", "reliance", "final", "upgrades", "upgraded",
                                      "pending", "relied_wrong", "verified_right"))
        return rest, tuple(acc), tuple(ref), tuple(sorted(rec["baseline"].items()))

    def test_p5b_same_arrival_conflict_negative_wins_any_order(self):
        x = [ev("ext", "A", 1, 1, M.CORRECT), ev("ext2", "A", 1, 1, M.INCORRECT)]
        for evs in (x, x[::-1]):
            rec = M.evaluate(small(evs, 1, 1, sources=TWO, truth=(False,) * 3))
            self.assertEqual((rec["reliance"], rec["final"], rec["refused"]),
                             ((M.VERIFY,) * 3, M.UNTRUSTED, ()), evs)
            self.assertEqual(len(rec["accepted"]), 2)

    def test_p5c_later_timely_correction_from_another_source(self):
        x = [ev("ext", "A", 1, 1, M.CORRECT), ev("ext2", "A", 1, 2, M.INCORRECT)]
        for evs in (x, x[::-1]):
            rec = M.evaluate(small(evs, 1, 1, sources=TWO, truth=(False,) * 3))
            self.assertEqual((rec["reliance"], rec["final"], rec["relied_wrong"], rec["refused"]),
                             ((M.VERIFY, M.RELY, M.VERIFY), M.UNTRUSTED, 1, ()), evs)

    def test_p5d_same_source_corrects_itself(self):
        x = [ev("ext", "A", 1, 1, M.CORRECT), ev("ext", "A", 1, 2, M.INCORRECT)]
        for evs in (x, x[::-1]):
            rec = M.evaluate(small(evs, 1, 1, truth=(False,) * 3))
            self.assertEqual((rec["reliance"], rec["final"], rec["refused"]),
                             ((M.VERIFY, M.RELY, M.VERIFY), M.UNTRUSTED, ()), evs)

    def test_p5e_pending_with_timely_negative_is_not_rely(self):
        x = [ev("ext", "A", 1, 1, M.CORRECT), ev("ext2", "A", 1, 1, M.INCORRECT)]
        p = ({"pending_id": "p", "round": 1, "deadline": 1, "on_expiry": M.DENY},)
        for evs in (x, x[::-1]):
            rec = M.evaluate(small(evs, 1, 1, p, sources=TWO))
            self.assertEqual(rec["pending"], (("p", M.DO_NOT_RELY, 1),), evs)

    def test_pending_negative_outranks_any_timely_correct(self):
        def pend(evs, deadline):
            p = ({"pending_id": "p", "round": 1, "deadline": deadline, "on_expiry": M.HOLD},)
            return M.evaluate(small(evs, 1, 1, p, sources=TWO))["pending"]
        neg_first = [ev("ext", "A", 1, 1, M.INCORRECT), ev("ext2", "A", 1, 2, M.CORRECT)]
        pos_first = [ev("ext", "A", 1, 1, M.CORRECT), ev("ext2", "A", 1, 2, M.INCORRECT)]
        self.assertEqual(pend(neg_first, 2), (("p", M.DO_NOT_RELY, 1),))
        self.assertEqual(pend(pos_first, 2), (("p", M.DO_NOT_RELY, 2),))
        # A negative after the deadline does not count; the timely correct does.
        self.assertEqual(pend(pos_first, 1), (("p", M.RELY, 1),))
        self.assertEqual(pend(neg_first[:1], 3), (("p", M.DO_NOT_RELY, 1),))

    def test_a_round_counts_once_and_never_after_a_negative(self):
        both_ok = [ev("ext", "A", 1, 1, M.CORRECT), ev("ext2", "A", 1, 1, M.CORRECT)]
        rec = M.evaluate(small(both_ok, 2, 1, sources=TWO))
        self.assertEqual((rec["reliance"], rec["upgrades"], len(rec["accepted"]), rec["refused"]),
                         ((M.VERIFY,) * 3, 0, 2, ()))
        self.assertEqual(M.evaluate(small(both_ok, 1, 1, sources=TWO))["reliance"],
                         (M.VERIFY, M.RELY, M.RELY))
        # A refuted round never counts again, from any source or arrival.
        late_ok = [ev("ext", "A", 1, 1, M.INCORRECT), ev("ext2", "A", 1, 2, M.CORRECT)]
        rec = M.evaluate(small(late_ok, 1, 1, sources=TWO))
        self.assertEqual((rec["reliance"], rec["upgrades"], len(rec["accepted"])),
                         ((M.VERIFY,) * 3, 0, 2))

    def test_negative_resets_the_score_not_decrements(self):
        evs = [ev("ext", "A", 1, 1, M.CORRECT), ev("ext", "A", 2, 2, M.CORRECT),
               ev("ext", "A", 3, 3, M.INCORRECT), ev("ext", "A", 4, 4, M.CORRECT)]
        c = long_session((0.2,) * 6, evs)
        c["trust_bar"] = 2
        rec = M.evaluate(c)
        # Trusted after two; the negative resets to 0, so one more "correct"
        # (score 1 of 2) does not re-trust (a decrement would leave 2).
        self.assertEqual(rec["reliance"], (M.VERIFY, M.VERIFY, M.RELY) + (M.VERIFY,) * 3)
        self.assertEqual((rec["final"], rec["upgrades"]), (M.UNTRUSTED, 1))
        self.assertEqual(rec, O.reference(c))

    def test_permutation_invariance_over_all_orderings(self):
        """Every 2- and 3-event subset of the two-source pool, every list order,
        trust bars 1 and 2, six pending decisions: one outcome per subset."""
        orderings = dependent = flips = subsets = 0
        for bar in (1, 2):
            for k in (2, 3):
                for combo in itertools.combinations(POOL2, k):
                    subsets += 1
                    views = set()
                    relies = set()
                    for perm in itertools.permutations(combo):
                        c = small(perm, bar, 1, PENDS6, sources=TWO)
                        rec = M.evaluate(c)
                        views.add(self.view(c, rec))
                        relies.add(M.RELY in rec["reliance"]
                                   or any(r == M.RELY for _, r, _ in rec["pending"]))
                        orderings += 1
                    dependent += len(views) > 1
                    flips += len(relies) > 1
        self.assertEqual((subsets, orderings), (2 * (190 + 1140), 2 * 7220))
        self.assertEqual((dependent, flips), (0, 0))


class TestOracle(unittest.TestCase):

    def test_module_and_oracle_agree_on_all_fixtures(self):
        n = 0
        for name, c in F.cases().items():
            rec = M.evaluate(c)
            if rec["status"] != M.OK:
                continue
            self.assertEqual(rec, O.reference(case(name)), name)
            n += 1
        self.assertEqual(n, 16)

    def test_module_and_oracle_agree_exhaustively(self):
        total = 0
        for name, gen, want in SPACES:
            count = 0
            for c in gen():
                rec = M.evaluate(c)
                self.assertEqual(rec["status"], M.OK)
                self.assertEqual(rec, O.reference(c))
                count += 1
            self.assertEqual(count, want, name)
            total += count
        self.assertEqual(total, 84057)

    def test_oracle_is_a_separate_code_path(self):
        tree = ast.parse(read("oracle.py"))
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, (ast.Import, ast.ImportFrom))
        mod_names = set(n.name for n in ast.walk(ast.parse(read("trust_feedback.py")))
                        if isinstance(n, ast.FunctionDef))
        orc_names = set(n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        self.assertEqual(mod_names & orc_names, set())


class TestInputs(unittest.TestCase):

    def cfg(self, c, detail=None):
        rec = M.evaluate(c)
        self.assertEqual(rec["status"], M.CONFIG_ERROR)
        for k in M.FIELDS_OUT:
            self.assertIsNone(rec[k])
        if detail is not None:
            self.assertEqual(rec["detail"], detail)

    def test_case_shape(self):
        c = case("H-feedback")
        self.cfg(None, "case_not_dict")
        self.cfg([c], "case_not_dict")
        for f in M.CASE_FIELDS:
            x = copy.deepcopy(c)
            del x[f]
            self.cfg(x, f + "_missing")
        self.cfg(dict(c, trusted=True), "case_unknown_field")
        self.cfg(dict(c, case_id=" "), "case_id_invalid")
        self.cfg(dict(c, condition="maybe"), "condition_invalid")
        self.cfg(dict(c, advisor_id=""), "advisor_id_invalid")
        self.cfg(dict(c, rounds=0), "rounds_invalid")
        self.cfg(dict(c, truth=c["truth"][:9]), "truth_invalid")
        self.cfg(dict(c, advice=c["advice"][:9]), "advice_shape")
        x = copy.deepcopy(c)
        x["advice"][3]["round"] = 3
        self.cfg(x, "advice_round_invalid")
        x = copy.deepcopy(c)
        del x["advice"][0]["prestige"]
        self.cfg(x, "advice_shape")
        self.cfg(dict(c, external_sources=["grader", "grader"]), "external_source_duplicate")
        self.cfg(dict(c, external_sources=[" "]), "external_source_invalid")
        self.cfg(dict(c, max_age=-1), "max_age_invalid")
        self.cfg(dict(c, trust_bar=0), "trust_bar_invalid")
        x = copy.deepcopy(c)
        x["feedback"][0]["at"] = 11
        self.cfg(x, "event_at_invalid")
        x = copy.deepcopy(c)
        x["feedback"][0]["outcome"] = "right"
        self.cfg(x, "event_outcome_invalid")
        x = copy.deepcopy(c)
        del x["feedback"][0]["round"]
        self.cfg(x, "event_shape")
        x = copy.deepcopy(c)
        x["pending"].append(dict(x["pending"][0]))
        self.cfg(x, "pending_id_invalid")
        x = copy.deepcopy(c)
        x["pending"][0]["deadline"] = 4
        self.cfg(x, "pending_deadline_invalid")
        # A deadline past the last round is config_error; the last round is fine.
        x = copy.deepcopy(c)
        x["pending"][0]["deadline"] = 11
        self.cfg(x, "pending_deadline_invalid")
        x = copy.deepcopy(c)
        x["pending"][0]["deadline"] = 10
        self.assertEqual(M.evaluate(x)["status"], M.OK)
        self.cfg(small([], pending=({"pending_id": "p", "round": 3, "deadline": 4,
                                     "on_expiry": M.HOLD},)), "pending_deadline_invalid")
        x = copy.deepcopy(c)
        x["pending"][0]["round"] = 11
        self.cfg(x, "pending_round_invalid")

    def test_exact_types_in_every_value_slot(self):
        c = case("H-feedback")
        nums = (True, False, SubInt(3), 3.0, "3", None)
        for slot in ("rounds", "max_age", "trust_bar"):
            for bad in nums:
                self.cfg(dict(c, **{slot: bad}), slot + "_invalid")
        for bad in (float("nan"), float("inf"), -float("inf"), 1.5, -0.1, 1, True,
                    SubFloat(0.5), "0.5"):
            x = copy.deepcopy(c)
            x["advice"][2]["confidence"] = bad
            self.cfg(x, "advice_confidence_invalid")
        for bad in (True, SubInt(1), 1.0, "1"):
            x = copy.deepcopy(c)
            x["feedback"][0]["round"] = bad
            self.cfg(x, "event_round_invalid")
            x = copy.deepcopy(c)
            x["feedback"][0]["at"] = bad
            self.cfg(x, "event_at_invalid")
            x = copy.deepcopy(c)
            x["pending"][0]["deadline"] = bad
            self.cfg(x, "pending_deadline_invalid")
        for slot, detail in (("source", "event_source_invalid"),
                             ("advisor_id", "event_advisor_invalid"),
                             ("outcome", "event_outcome_invalid")):
            x = copy.deepcopy(c)
            x["feedback"][0][slot] = SubStr(x["feedback"][0][slot])
            self.cfg(x, detail)
        self.cfg(dict(c, truth=[1] * 10), "truth_invalid")
        self.cfg(dict(c, advisor_id=SubStr("H")), "advisor_id_invalid")
        self.cfg(dict(c, external_sources=[SubStr("grader")]), "external_source_invalid")
        self.cfg(dict(c, condition=SubStr("feedback")), "condition_invalid")
        x = copy.deepcopy(c)
        x["advice"][0]["claim"] = SubStr("x")
        self.cfg(x, "advice_claim_invalid")
        x = copy.deepcopy(c)
        x["advice"][0]["prestige"] = None
        self.cfg(x, "advice_prestige_invalid")
        for slot in ("truth", "advice", "external_sources", "feedback", "pending"):
            self.cfg(dict(c, **{slot: SubList(c[slot])}), slot + "_invalid")
            self.cfg(dict(c, **{slot: tuple(c[slot])}), slot + "_invalid")
        x = copy.deepcopy(c)
        x["feedback"][0] = SubDict(x["feedback"][0])
        self.cfg(x, "event_invalid")
        x = copy.deepcopy(c)
        x["advice"][0] = SubDict(x["advice"][0])
        self.cfg(x, "advice_invalid")
        self.cfg(SubDict(c), "case_not_dict")

    def test_run_guard_maps_internal_error(self):
        real = M.rule

        def boom(snap):
            raise RuntimeError("x")

        M.rule = boom
        try:
            self.cfg(case("H-feedback"), "internal_error")
        finally:
            M.rule = real

    def test_never_raises(self):
        c = case("H-feedback")
        for arg in [None, 1, {}, {"case_id": "x"}, [], "case", dict(c, advice=[[]]),
                    dict(c, feedback=[None]), dict(c, pending=[1]), dict(c, truth=None),
                    dict(c, feedback=[{1: 2}])]:
            self.assertEqual(M.evaluate(arg)["status"], M.CONFIG_ERROR, arg)

    def test_inputs_not_mutated(self):
        for n, c in F.cases().items():
            c0 = copy.deepcopy(c)
            rec = M.evaluate(c)
            if rec["status"] == M.OK:
                O.reference(c)
            self.assertEqual(c, c0, n)


class TestKeysAndSnapshot(unittest.TestCase):
    """Exact-str keys before any lookup; all logic runs on a snapshot only."""

    def cfg(self, rec, detail):
        self.assertEqual((rec["status"], rec["detail"]), (M.CONFIG_ERROR, detail))
        self.assertIsNone(rec["reliance"])

    def test_spoofed_case_key_is_config_error(self):
        for field in M.CASE_FIELDS:
            c = case("U-no-feedback")
            value = c.pop(field)
            key = Spoof(field)
            c[key] = value
            self.cfg(M.evaluate(c), "case_key_invalid")
            self.assertEqual(key.n, 0, field)

    def test_spoofed_keys_at_every_level(self):
        """No spoofed key's comparison ever runs, even one whose hook would
        rewrite the caller's events into genuine ones."""
        slots = (("advice", 0, M.ADVICE_FIELDS, "advice_key_invalid"),
                 ("feedback", 0, M.EVENT_FIELDS, "event_key_invalid"),
                 ("pending", 0, M.PENDING_FIELDS, "pending_key_invalid"))
        for slot, idx, fields, detail in slots:
            for field in fields:
                for flip in (1, 2, 5):
                    c = case("SP5-other-advisor")
                    c["pending"] = [F.pend("p", 5, 6, M.DENY)]
                    box = {"c": c}

                    def hook(n, flip=flip):
                        if n == flip:
                            for e in box["c"]["feedback"]:
                                e["advisor_id"] = "U"

                    rec = c[slot][idx]
                    value = rec.pop(field)
                    key = Spoof(field, hook)
                    rec[key] = value
                    self.cfg(M.evaluate(c), detail)
                    self.assertEqual(key.n, 0, (slot, field, flip))
                    self.assertEqual(c["feedback"][1]["advisor_id"], "H")

    def test_str_subclass_with_eq_rejected(self):
        class Any(str):
            def __eq__(self, other):
                return True

            __hash__ = str.__hash__

        for slot, detail in (("source", "event_source_invalid"),
                             ("advisor_id", "event_advisor_invalid")):
            c = case("SP8-undeclared-source")
            c["feedback"][0][slot] = Any("grader")
            self.cfg(M.evaluate(c), detail)
        c = case("PE-no-feedback-expiry")
        c["pending"][0]["on_expiry"] = Any("DENY")
        self.cfg(M.evaluate(c), "on_expiry_invalid")
        c = case("SP8-undeclared-source")
        c["external_sources"] = [Any("advisor-blog")]
        self.cfg(M.evaluate(c), "external_source_invalid")

    def test_int_subclass_with_compare_rejected(self):
        class Small(int):
            def __gt__(self, other):
                return False

            def __lt__(self, other):
                return False

        c = case("SP4-stale")
        c["feedback"][0]["at"] = Small(c["feedback"][0]["at"])
        self.cfg(M.evaluate(c), "event_at_invalid")
        c = case("SP4-stale")
        c["max_age"] = Small(99)
        self.cfg(M.evaluate(c), "max_age_invalid")

    def test_non_str_keys_rejected_at_every_level(self):
        for bad in (1, (1, 2), SubStr("x"), Spoof("other"), True, 0.5):
            c = case("H-feedback")
            c[bad] = 1
            self.cfg(M.evaluate(c), "case_key_invalid")
            for slot, detail in (("advice", "advice_key_invalid"),
                                 ("feedback", "event_key_invalid"),
                                 ("pending", "pending_key_invalid")):
                c = case("H-feedback")
                c[slot][0][bad] = 1
                self.cfg(M.evaluate(c), detail)

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
                if rec["status"] != M.OK:
                    self.assertEqual(seen, [], n)
                    continue
                snap = seen.pop()
                self.assertEqual(containers(snap, set()) & containers(c, set()), set(), n)
                for k in ("truth", "advice", "external_sources", "feedback", "pending"):
                    self.assertIs(type(snap[k]), tuple, (n, k))
                c["feedback"].clear()
                c["external_sources"].append("U")
                c["pending"].clear()
                c["trust_bar"] = 1
                self.assertEqual(rec, real(snap), n)
        finally:
            M._run = real

    def test_caller_mutation_mid_run_changes_nothing(self):
        """The caller's objects are changed after validation, before the rule
        reads anything; every result still comes from the snapshot."""
        real = M.rule
        for n in F.LABELS:
            clean = run(n)
            if clean["status"] != M.OK:
                continue
            c = case(n)

            def meddle(snap, c=c):
                c["external_sources"][:] = ["U", "H", "advisor-blog"]
                for e in c["feedback"]:
                    e["advisor_id"] = c["advisor_id"]
                    e["at"] = e["round"] if type(e["round"]) is int and 1 <= e["round"] <= 10 \
                        else 1
                    e["outcome"] = M.CORRECT
                for p in c["pending"]:
                    p["on_expiry"] = "RELY"
                c["trust_bar"] = 1
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
        self.assertEqual(list(cs), [c["case_id"] for c in F.CASES])
        self.assertEqual(sorted(cs), sorted(F.LABELS))
        self.assertEqual(len(cs), 18)
        self.assertEqual(set(F.SPOOF_REASON), set(F.SPOOFS))
        for n, c in cs.items():
            self.assertEqual(c["case_id"], n)
        for n in F.SPOOFS:
            self.assertEqual(cs[n]["advisor_id"], "U", n)

    def test_fixture_pins(self):
        self.assertEqual((F.SOURCE, F.MAX_AGE, F.BAR), ("grader", 1, 3))
        self.assertEqual(F.TRACKS["S"], [True] * 6 + [False] * 4)
        self.assertEqual(F.TRACKS["M"][:4], [True, False, True, False])
        self.assertGreater(F.CONFIDENCE["U"], F.CONFIDENCE["H"])
        self.assertEqual(case("SP7-confident-claim")["advice"][0]["confidence"], 1.0)

    def test_fixtures_return_copies(self):
        c = F.cases()
        c["U-no-feedback"]["feedback"].append(F.event(1, 1, M.CORRECT))
        c["H-feedback"]["external_sources"].append("H")
        fresh = F.cases()
        self.assertEqual(fresh["U-no-feedback"]["feedback"], [])
        self.assertEqual(fresh["H-feedback"]["external_sources"], ["grader"])
        lab = F.labels()
        lab["H-feedback"] = None
        self.assertIsNotNone(F.LABELS["H-feedback"])

    def test_determinism(self):
        self.assertEqual(F.summary(), F.summary())
        self.assertIn("module vs oracle: 16/16 valid cases agree", F.summary())


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
        bullets = [line for line in lines if line.startswith("- ")]
        self.assertEqual(bullets[-1], rows[0])
        if LAYOUT == "flat":
            # Based on main alone: the main rows, retained byte for byte, then this row.
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
                  "w23-scrutiny-not-authority", "w22-revision-selectivity",
                  "w21-advice-cooldown", "w17-source-authority", "mb-fail-closed-deputy",
                  "declared cost", "never RELY", "No human data"):
            self.assertIn(s, flat, s)
        notice = " ".join(read("NOTICE").split())
        for s in (ev_["paper"]["title"], "arXiv:2611.14833", "https://arxiv.org/abs/2611.14833",
                  "non-exclusive", "clean-room", "not read", "No human data"):
            self.assertIn(s, notice, s)
        for author in ev_["paper"]["authors"]:
            self.assertIn(author, notice)

    def test_evidence_shape(self):
        ev_ = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev_["paper"]["arxiv_id"], "2611.14833")
        self.assertIn("nonexclusive-distrib/1.0", ev_["paper"]["licence"])
        self.assertFalse(ev_["paper"]["pdf_read"])
        self.assertEqual([c["id"] for c in ev_["claims"]], ["C1", "C2", "C6"])
        for c in ev_["claims"]:
            self.assertEqual(len(c["quote"]), c["length"], c["id"])
            self.assertEqual(c["status"], "UNVERIFIED", c["id"])
        quotes = " ".join(c["quote"] for c in ev_["claims"])
        self.assertIsNotNone(PAPER_PAT.search(quotes))

    def test_quotes_exact_in_sources(self):
        if not SOURCES:
            self.skipTest("W24TNF_SOURCES not set")
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
