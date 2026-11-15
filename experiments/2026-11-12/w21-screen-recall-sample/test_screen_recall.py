"""Tests for the screen-recall-sample sketch. Run: python3 -B -m unittest

The source check reads the abstract copy named in paper_evidence.json from
the directory in $W21SR_SOURCES. There is no default: when the variable is
unset, or the file is absent there, that one test is skipped.
"""

import ast
import copy
import hashlib
import json
import os
import random
import unittest
from fractions import Fraction

import fixtures as F
import screen_recall as S

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W21SR_SOURCES")
CODE = ("screen_recall.py", "fixtures.py")
DOCS = ("README.md", "NOTICE")
OWN = DOCS + CODE + ("test_screen_recall.py", "mutants.py", "paper_evidence.json")
FIGS = ("precision", "recall_lower_bound", "recall")
DAY_HEADER = "# experiments/2026-11-12"


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def flat(name):
    return " ".join(read(name).split())


def day_readme():
    """The day index: ../README.md in the repo layout (parent folder is
    2026-11-12 and the file opens with the day header), else _day/README.md
    in a flat copy, else None."""
    parent = os.path.dirname(HERE)
    up = os.path.join(parent, "README.md")
    if os.path.basename(parent) == "2026-11-12" and os.path.isfile(up):
        with open(up, encoding="utf-8") as fh:
            if fh.read().startswith(DAY_HEADER):
                return up
    flat_copy = os.path.join(HERE, "_day", "README.md")
    if os.path.isfile(flat_copy):
        return flat_copy
    return None


def figures(rec):
    """The whole record except screener_count (a count of reports, checked
    on its own): status, on_expiry and every figure with all its fields."""
    out = copy.deepcopy(rec)
    del out["screener_count"]
    return out


class SpoofStr(str):
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = str.__hash__


class RaisingStr(str):
    def __eq__(self, other):
        raise RuntimeError("eq")

    def __hash__(self):
        raise RuntimeError("hash")

    def __len__(self):
        raise RuntimeError("len")


class RaisingObj(object):
    def __eq__(self, other):
        raise RuntimeError("eq")

    def __hash__(self):
        raise RuntimeError("hash")

    def __bool__(self):
        raise RuntimeError("bool")


class SubDict(dict):
    pass


class SubList(list):
    pass


class SubInt(int):
    pass


class DoneWhen(unittest.TestCase):

    def test_precision_from_assessed_passes(self):
        rec = S.report(F.request(with_sample=False))
        self.assertEqual(rec["status"], S.REPORTED)
        self.assertEqual(rec["precision"]["status"], S.MEASURED)
        self.assertEqual(rec["precision"]["exact"], "2/3")
        self.assertEqual(rec["precision"]["judged"], 12)
        self.assertEqual(rec["precision"]["relevant"], 8)

    def test_screener_count_never_unlocks_recall(self):
        for n in (0, 1, 2, 3, 5, 9, 50):
            rec = S.report(F.request(n, with_sample=False))
            self.assertEqual(rec["screener_count"], n)
            self.assertEqual(rec["recall"]["status"], S.ON_UNMEASURED, n)
            self.assertEqual(rec["recall"]["reason"], S.NO_NOT_PASSED_SAMPLE)
            self.assertIsNone(rec["recall"]["value"])

    def test_screener_reports_never_change_any_figure(self):
        base = figures(S.report(F.request(3)))
        rng = random.Random(7)
        variants = [[], F.screener_reports(1), F.screener_reports(40),
                    [{"screener": "x", "passed": []}],
                    [{"screener": "a", "passed": list(F.ITEMS)},
                     {"screener": "b", "passed": list(F.ITEMS)},
                     {"screener": "c", "passed": []}]]
        for k in range(5):
            variants.append([{"screener": "r%d" % j,
                              "passed": rng.sample(F.ITEMS, rng.randint(0, 40))}
                             for j in range(rng.randint(1, 7))])
        for reports in variants:
            rec = S.report(F.request(screener_reports=reports))
            self.assertEqual(figures(rec), base)
            self.assertEqual(rec["screener_count"], len(reports))
        base_ns = figures(S.report(F.request(with_sample=False)))
        for reports in variants:
            rec = S.report(F.request(with_sample=False, screener_reports=reports))
            self.assertEqual(figures(rec), base_ns)
            self.assertEqual(rec["screener_count"], len(reports))

    def test_fixture_records_whole(self):
        # Whole records, every key: no extra field (an upper bound, an
        # agreement figure) can ride along unseen.
        precision = {"status": S.MEASURED, "value": float(Fraction(2, 3)),
                     "exact": "2/3", "reason": None, "judged": 12, "relevant": 8}
        lower = {"status": S.LOWER_BOUND, "value": float(Fraction(2, 9)),
                 "exact": "2/9", "reason": None, "found": 8, "not_passed": 28}
        no_sample = {"status": S.ON_UNMEASURED, "value": None, "exact": None,
                     "reason": S.NO_NOT_PASSED_SAMPLE}
        estimate = {"status": S.ESTIMATE, "value": 0.5, "exact": "1/2",
                    "reason": None, "sample_size": 14, "relevant_in_sample": 4,
                    "not_passed": 28, "missed_estimate": 8.0, "interval": None}
        for n in (0, 3, 9):
            for with_sample, recall in ((False, no_sample), (True, estimate)):
                rec = S.report(F.request(n, with_sample))
                self.assertEqual(rec, {"status": S.REPORTED, "on_expiry": None,
                                       "screener_count": n, "precision": precision,
                                       "recall_lower_bound": lower,
                                       "recall": recall}, (n, with_sample))

    def test_full_agreement_does_not_mean_full_recall(self):
        found, total = F.true_recall()
        self.assertLess(found, total)  # the screeners all agree yet miss items
        rec = S.report(F.request(9, with_sample=False))
        self.assertNotEqual(rec["recall"]["status"], S.ESTIMATE)

    def test_not_passed_sample_unlocks_estimate(self):
        rec = S.report(F.request())
        r = rec["recall"]
        self.assertEqual(r["status"], S.ESTIMATE)
        self.assertEqual(r["sample_size"], F.SAMPLE_SIZE)
        self.assertEqual(r["not_passed"], 28)
        hits = sum(1 for i in F.sample()["items"] if i in F.RELEVANT_TRUTH)
        self.assertEqual(r["relevant_in_sample"], hits)
        missed = Fraction(hits * 28, F.SAMPLE_SIZE)
        self.assertEqual(r["missed_estimate"], float(missed))
        expect = Fraction(8) / (8 + missed)
        self.assertEqual(r["exact"], "%d/%d" % (expect.numerator, expect.denominator))
        self.assertIsNone(r["interval"])

    def test_estimate_is_estimate_not_truth(self):
        found, total = F.true_recall()
        rec = S.report(F.request())
        self.assertEqual(rec["recall"]["status"], S.ESTIMATE)
        self.assertNotEqual(rec["recall"]["exact"], "%d/%d" % (
            Fraction(found, total).numerator, Fraction(found, total).denominator))

    def test_full_sample_recovers_truth(self):
        np = F.not_passed()
        req = F.request(not_passed_sample=F.sample(size=len(np)))
        rec = S.report(req)
        found, total = F.true_recall()
        self.assertEqual(Fraction(rec["recall"]["exact"]), Fraction(found, total))

    def test_omitted_or_empty_sample_is_unmeasured(self):
        rec = S.report(F.request(with_sample=False))
        self.assertEqual(rec["recall"]["status"], S.ON_UNMEASURED)
        self.assertEqual(rec["recall"]["reason"], S.NO_NOT_PASSED_SAMPLE)
        rec = S.report(F.request(not_passed_sample=F.sample(size=0)))
        self.assertEqual(rec["recall"]["status"], S.ON_UNMEASURED)
        self.assertEqual(rec["recall"]["reason"], S.SAMPLE_EMPTY)

    def test_acceptance_only_is_lower_bound_never_recall(self):
        rec = S.report(F.request(with_sample=False))
        lb = rec["recall_lower_bound"]
        self.assertEqual(lb["status"], S.LOWER_BOUND)
        self.assertEqual(lb["exact"], "2/9")
        self.assertNotEqual(rec["recall"]["status"], S.ESTIMATE)
        self.assertIsNone(rec["recall"]["value"])
        found, total = F.true_recall()
        self.assertLessEqual(Fraction(lb["exact"]), Fraction(found, total))

    def test_lower_bound_still_a_bound_with_sample(self):
        rec = S.report(F.request())
        self.assertEqual(rec["recall_lower_bound"]["status"], S.LOWER_BOUND)
        self.assertLessEqual(rec["recall_lower_bound"]["value"], rec["recall"]["value"])

    def test_pending_assessment_expires_to_declared_on_expiry(self):
        for value, const in (("hold", S.HOLD), ("escalate", S.ESCALATE), ("deny", S.DENY)):
            smp = F.sample()
            smp["judgments"][smp["items"][0]] = "pending"
            rec = S.report(F.request(not_passed_sample=smp, deadline={
                "timeout_s": 60, "on_expiry": "".join(value), "expired": True}))
            self.assertEqual(rec["status"], S.EXPIRED)
            self.assertIs(rec["on_expiry"], const)
            for k in FIGS:
                self.assertEqual(rec[k]["status"], S.ON_UNMEASURED, k)
                self.assertIsNone(rec[k]["value"])

    def test_expired_without_pending_still_reports_nothing(self):
        rec = S.report(F.request(deadline={"timeout_s": 60, "on_expiry": "hold",
                                            "expired": True}))
        self.assertEqual(rec["status"], S.EXPIRED)
        self.assertEqual(rec["recall"]["status"], S.ON_UNMEASURED)

    def test_pending_not_expired_withholds_recall(self):
        smp = F.sample()
        smp["judgments"][smp["items"][0]] = "pending"
        rec = S.report(F.request(not_passed_sample=smp, deadline={
            "timeout_s": 60, "on_expiry": "deny", "expired": False}))
        self.assertEqual(rec["status"], S.PENDING)
        self.assertIs(rec["on_expiry"], S.DENY)
        self.assertEqual(rec["recall"]["status"], S.ON_UNMEASURED)
        self.assertEqual(rec["recall"]["reason"], S.ASSESSMENT_PENDING)
        self.assertEqual(rec["precision"]["status"], S.MEASURED)

    def test_pending_pass_withholds_everything(self):
        req = F.request(deadline={"timeout_s": 60, "on_expiry": "hold"})
        req["assessed_passes"]["d01"] = "pending"
        rec = S.report(req)
        self.assertEqual(rec["status"], S.PENDING)
        for k in FIGS:
            self.assertEqual(rec[k]["status"], S.ON_UNMEASURED, k)
            self.assertEqual(rec[k]["reason"], S.ASSESSMENT_PENDING, k)

    def test_pending_without_deadline_is_config_error(self):
        smp = F.sample()
        smp["judgments"][smp["items"][0]] = "pending"
        rec = S.report(F.request(not_passed_sample=smp))
        self.assertEqual(rec["status"], S.CONFIG_ERROR)
        req = F.request()
        req["assessed_passes"]["d01"] = "pending"
        self.assertEqual(S.report(req)["status"], S.CONFIG_ERROR)

    def test_pending_without_deadline_is_config_error_without_sample(self):
        # No not-passed sample at all: a pending pass still needs a deadline.
        req = F.request(with_sample=False)
        req["assessed_passes"]["d01"] = "pending"
        self.assertIsNotNone(S.validate(req))
        rec = S.report(req)
        self.assertEqual(rec["status"], S.CONFIG_ERROR)
        self.assertIsNone(rec["on_expiry"])
        for k in FIGS:
            self.assertIsNone(rec[k]["value"], k)
        req["deadline"] = {"timeout_s": 60, "on_expiry": "hold"}
        self.assertEqual(S.report(req)["status"], S.PENDING)


class Semantics(unittest.TestCase):

    def test_partially_assessed_passes(self):
        req = F.request()
        del req["assessed_passes"]["d02"]
        rec = S.report(req)
        for k in FIGS:
            self.assertEqual(rec[k]["status"], S.ON_UNMEASURED, k)
            self.assertEqual(rec[k]["reason"], S.PASSES_NOT_FULLY_ASSESSED, k)

    def test_nothing_forwarded(self):
        rec = S.report(F.request(forwarded=[], assessed_passes={},
                                 screener_reports=[], with_sample=False))
        self.assertEqual(rec["precision"]["reason"], S.NOTHING_PASSED)
        self.assertEqual(rec["recall_lower_bound"]["exact"], "0/1")

    def test_everything_forwarded(self):
        rec = S.report(F.request(forwarded=list(F.ITEMS), with_sample=False,
                                 assessed_passes={i: F.label(i) for i in F.ITEMS}))
        self.assertEqual(rec["recall"]["reason"], S.NOTHING_NOT_PASSED)
        self.assertEqual(rec["recall_lower_bound"]["exact"], "1/1")

    def test_no_relevant_anywhere(self):
        req = F.request(forwarded=["d02"], assessed_passes={"d02": "not_relevant"},
                        screener_reports=[])
        np = [i for i in F.ITEMS if i != "d02"]
        drawn = S.draw_sample(np, 5, 1)
        req["not_passed_sample"] = {"seed": 1, "size": 5, "items": drawn,
                                    "judgments": {i: "not_relevant" for i in drawn}}
        rec = S.report(req)
        self.assertEqual(rec["recall"]["reason"], S.NO_RELEVANT_OBSERVED)

    def test_sample_must_be_the_seeded_draw(self):
        smp = F.sample()
        smp["items"] = list(reversed(smp["items"]))
        rec = S.report(F.request(not_passed_sample=smp))
        self.assertEqual(rec["recall"]["reason"], S.SAMPLE_NOT_SEEDED_DRAW)
        # Cherry-picked: only relevant misses plus fillers, same size.
        picked = [i for i in F.not_passed() if i not in F.RELEVANT_TRUTH][:F.SAMPLE_SIZE]
        rec = S.report(F.request(not_passed_sample={
            "seed": F.SEED, "size": F.SAMPLE_SIZE, "items": picked,
            "judgments": {i: F.label(i) for i in picked}}))
        self.assertEqual(rec["recall"]["status"], S.ON_UNMEASURED)
        smp = F.sample()
        smp["seed"] = F.SEED + 1
        rec = S.report(F.request(not_passed_sample=smp))
        self.assertEqual(rec["recall"]["reason"], S.SAMPLE_NOT_SEEDED_DRAW)

    def test_draw_sample_is_seeded_and_order_free(self):
        np = F.not_passed()
        a = S.draw_sample(np, 6, 5)
        b = S.draw_sample(list(reversed(np)), 6, 5)
        self.assertEqual(a, b)
        self.assertEqual(a, random.Random(5).sample(sorted(np), 6))

    def test_draw_does_not_touch_global_random(self):
        # draw_sample and report must use a local Random; they must not
        # reseed or consume the process RNG. The process RNG is first
        # put in a distinctive state, so a re-seed to the fixture seed
        # cannot look like a no-op after an earlier fixture draw.
        saved = random.getstate()
        try:
            random.seed(424242)
            for _ in range(7):
                random.random()
            before = random.getstate()
            rec = S.report(F.request(with_sample=True))
            self.assertEqual(rec["recall"]["status"], S.ESTIMATE)
            self.assertEqual(random.getstate(), before)
            S.draw_sample(F.not_passed(), F.SAMPLE_SIZE, F.SEED)
            self.assertEqual(random.getstate(), before)
            S.report(F.request(with_sample=False))
            self.assertEqual(random.getstate(), before)
        finally:
            random.setstate(saved)

    def test_record_shape(self):
        for req in (F.request(), F.request(with_sample=False), None):
            rec = S.report(req)
            self.assertEqual(tuple(rec), S.RECORD_FIELDS)
            self.assertIn(rec["status"], S.STATUSES)
            for k in FIGS:
                self.assertIn(rec[k]["status"], (S.MEASURED, S.ESTIMATE,
                                                 S.LOWER_BOUND, S.ON_UNMEASURED))

    def test_recall_status_is_only_estimate_or_unmeasured(self):
        reqs = [F.request(n, s) for n in (0, 2, 7) for s in (True, False)]
        for req in reqs:
            self.assertIn(S.report(req)["recall"]["status"], (S.ESTIMATE, S.ON_UNMEASURED))

    def test_request_not_mutated(self):
        req = F.request()
        before = copy.deepcopy(req)
        S.report(req)
        self.assertEqual(req, before)


class AntiEnsemble(unittest.TestCase):
    """Not a voter or ensemble: no majority, vote, aggregate or consensus."""

    TERMS = ("majorit", "vote", "voting", "ensemble", "consensus", "quorum",
             "aggregat", "most_common", "counter", "plurality", "agreement",
             "weighted", "tally", "threshold")

    def test_module_has_no_ensemble_terms(self):
        text = read("screen_recall.py").lower()
        for term in self.TERMS:
            self.assertNotIn(term, text, term)

    def test_screener_reports_only_validated_and_counted(self):
        tree = ast.parse(read("screen_recall.py"))
        uses = []
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                for node in ast.walk(fn):
                    if isinstance(node, ast.Constant) and node.value == "screener_reports":
                        uses.append(fn.name)
        self.assertEqual(sorted(uses), ["_report", "validate"])
        src = ast.get_source_segment(read("screen_recall.py"), next(
            n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_report"))
        self.assertEqual(src.count('request["screener_reports"]'), 1)
        self.assertIn('len(request["screener_reports"])', src)

    def test_no_counting_of_screener_passes(self):
        # A per-item count over screener lists is the shape of a vote.
        tree = ast.parse(read("screen_recall.py"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        for bad in ("Counter", "votes", "counts", "support"):
            self.assertNotIn(bad, names)
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        self.assertNotIn("passed", attrs)

    def test_report_reads_request_by_literal_key_only(self):
        # In _report, `request` is passed to validate() or read by a literal
        # field name; screener_reports is read only inside len(). A computed
        # key (request.get(REQUEST_FIELDS[2])) or an alias is flagged.
        # global/nonlocal statements, locals() and vars() calls, and
        # getattr on the request object are rejected in the module (a
        # validate() stash, or a locals() alias of the request).
        tree = ast.parse(read("screen_recall.py"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_report")
        fields = S.REQUEST_FIELDS + S.OPTIONAL_FIELDS
        parents = {}
        for node in ast.walk(fn):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        uses = 0
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Name) and node.id == "request"):
                continue
            uses += 1
            up = parents[node]
            if isinstance(up, ast.Call):
                self.assertEqual(ast.unparse(up), "validate(request)")
                continue
            if isinstance(up, ast.Compare):
                self.assertEqual(len(up.comparators), 1)
                key = up.left
                self.assertIs(up.comparators[0], node)
            elif isinstance(up, ast.Subscript):
                key = up.slice
            else:
                self.assertIsInstance(up, ast.Attribute, ast.unparse(up))
                self.assertEqual(up.attr, "get")
                call = parents[up]
                self.assertIsInstance(call, ast.Call)
                self.assertEqual(len(call.args), 1)
                key = call.args[0]
            self.assertIsInstance(key, ast.Constant, ast.unparse(up))
            self.assertIn(key.value, fields)
            if key.value == "screener_reports":
                self.assertEqual(ast.unparse(parents[up]),
                                 "len(request['screener_reports'])")
        self.assertGreater(uses, 0)
        # Also ban a state stash out of validate() or _report, a locals()
        # or vars() alias of the request, and getattr on the request object.
        for node in ast.walk(tree):
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                self.fail(ast.unparse(node))
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id in ("locals", "vars"):
                self.fail(ast.unparse(node))
            if isinstance(func, ast.Name) and func.id == "getattr":
                if (node.args and isinstance(node.args[0], ast.Name)
                        and node.args[0].id == "request"):
                    self.fail(ast.unparse(node))


def screener_variants():
    """Screener report lists with different counts and agreement patterns:
    unanimous on the forwarded list (0..50), unanimous on another list,
    disagreeing, empty, random, reordered."""
    rng = random.Random(20261112)
    out = [F.screener_reports(n) for n in (0, 1, 2, 4, 5, 9, 50)]
    out.append([{"screener": "u%d" % k, "passed": list(F.ITEMS)} for k in range(7)])
    out.append([{"screener": "e%d" % k, "passed": []} for k in range(4)])
    out.append([{"screener": "a", "passed": list(F.ITEMS)},
                {"screener": "b", "passed": []}])
    out.append([{"screener": "g%d" % k, "passed": list(F.FORWARDED[k:])}
                for k in range(6)])
    out.append([{"screener": "h%d" % k, "passed": list(F.FORWARDED)} for k in range(5)]
               + [{"screener": "h5", "passed": list(F.FORWARDED[1:])}])
    for _ in range(4):
        out.append([{"screener": "r%d" % j,
                     "passed": rng.sample(F.ITEMS, rng.randint(0, 40))}
                    for j in range(rng.randint(1, 9))])
    out.append(list(reversed(F.screener_reports(6))))
    return out


SWEEP_SEED = 20261112
SWEEP_COUNTS = range(65)


def sweep_count_variants():
    """Screener lists for a seeded invariance sweep: every count 0-64,
    unanimous on the forwarded list and on another list, mixed lists,
    and, at counts 10-64, lists of disagreeing screeners. Uses only a
    local random.Random, so the process RNG is untouched."""
    rng = random.Random(SWEEP_SEED)
    other = list(F.ITEMS)
    out = []
    for n in SWEEP_COUNTS:
        out.append(F.screener_reports(n))
        if n >= 1:
            out.append([{"screener": "u%d" % k, "passed": list(other)}
                        for k in range(n)])
        if n >= 2:
            mid = n // 2
            out.append(
                [{"screener": "m%d" % k, "passed": list(F.FORWARDED)}
                 for k in range(mid)]
                + [{"screener": "m%d" % k, "passed": []}
                   for k in range(mid, n)])
        if n >= 10:
            reports = []
            for k in range(n):
                reports.append({
                    "screener": "d%d" % k,
                    "passed": rng.sample(F.ITEMS, rng.randint(0, len(F.ITEMS))),
                })
            if len({tuple(r["passed"]) for r in reports}) < 2:
                reports[0]["passed"] = list(F.FORWARDED)
                reports[1]["passed"] = []
            out.append(reports)
    return out


def cherry_sample():
    picked = [i for i in F.not_passed() if i not in F.RELEVANT_TRUTH][:F.SAMPLE_SIZE]
    return {"seed": F.SEED, "size": F.SAMPLE_SIZE, "items": picked,
            "judgments": {i: F.label(i) for i in picked}}


def reordered_sample():
    smp = F.sample()
    smp["items"] = list(reversed(smp["items"]))
    return smp


def pending_sample():
    smp = F.sample()
    smp["judgments"][smp["items"][0]] = "pending"
    return smp


def partial_passes():
    passes = {i: F.label(i) for i in F.FORWARDED}
    del passes["d02"]
    return passes


def pending_passes():
    passes = {i: F.label(i) for i in F.FORWARDED}
    passes["d01"] = "pending"
    return passes


LIVE = {"timeout_s": 60, "on_expiry": "deny", "expired": False}
GONE = {"timeout_s": 60, "on_expiry": "hold", "expired": True}

# path name -> (request overrides, check on the record with no screeners)
PATHS = {
    "plain": ({}, lambda r: r["recall"]["status"] == S.ESTIMATE),
    "no sample": ({"__no_sample": True},
                  lambda r: r["recall"]["reason"] == S.NO_NOT_PASSED_SAMPLE),
    "cherry": ({"not_passed_sample": cherry_sample},
               lambda r: r["recall"]["reason"] == S.SAMPLE_NOT_SEEDED_DRAW),
    "reordered": ({"not_passed_sample": reordered_sample},
                  lambda r: r["recall"]["reason"] == S.SAMPLE_NOT_SEEDED_DRAW),
    "expired": ({"deadline": GONE},
                lambda r: r["status"] == S.EXPIRED and r["on_expiry"] == S.HOLD),
    "expired pending": ({"not_passed_sample": pending_sample, "deadline": GONE},
                        lambda r: r["status"] == S.EXPIRED),
    "pending sample": ({"not_passed_sample": pending_sample, "deadline": LIVE},
                       lambda r: r["status"] == S.PENDING
                       and r["recall"]["reason"] == S.ASSESSMENT_PENDING),
    "pending pass": ({"assessed_passes": pending_passes, "deadline": LIVE},
                     lambda r: r["status"] == S.PENDING
                     and r["precision"]["reason"] == S.ASSESSMENT_PENDING),
    "partial": ({"assessed_passes": partial_passes},
                lambda r: r["recall"]["reason"] == S.PASSES_NOT_FULLY_ASSESSED),
    "partial no sample": ({"assessed_passes": partial_passes, "__no_sample": True},
                          lambda r: r["precision"]["reason"] == S.PASSES_NOT_FULLY_ASSESSED),
}


def path_request(path, reports):
    overrides, _ = PATHS[path]
    kw = {}
    with_sample = True
    for k, v in overrides.items():
        if k == "__no_sample":
            with_sample = False
        else:
            kw[k] = copy.deepcopy(v() if callable(v) else v)
    return F.request(with_sample=with_sample, screener_reports=copy.deepcopy(reports), **kw)


class ScreenerInvariance(unittest.TestCase):
    """The whole record is the same whatever the screeners reported: count,
    agreement and order of screener reports change nothing but
    screener_count (the number of reports)."""

    def check_path(self, path):
        base_rec = S.report(path_request(path, []))
        self.assertTrue(PATHS[path][1](base_rec), (path, base_rec))
        base = figures(base_rec)
        for reports in screener_variants():
            rec = S.report(path_request(path, reports))
            self.assertEqual(figures(rec), base, (path, len(reports)))
            self.assertEqual(rec["screener_count"], len(reports), path)

    def test_plain_and_no_sample(self):
        self.check_path("plain")
        self.check_path("no sample")

    def test_cherry_picked_and_reordered_samples(self):
        self.check_path("cherry")
        self.check_path("reordered")

    def test_expired(self):
        self.check_path("expired")
        self.check_path("expired pending")

    def test_pending(self):
        self.check_path("pending sample")
        self.check_path("pending pass")

    def test_partial(self):
        self.check_path("partial")
        self.check_path("partial no sample")

    def test_variants_cover_agreement(self):
        # The variant set is not vacuous: it holds unanimous lists of 4 or
        # more on the forwarded list, and lists that disagree.
        variants = screener_variants()
        unanimous = [v for v in variants if len(v) >= 4
                     and all(r["passed"] == F.FORWARDED for r in v)]
        split = [v for v in variants
                 if len({tuple(r["passed"]) for r in v}) > 1]
        self.assertGreaterEqual(len(unanimous), 4)
        self.assertGreaterEqual(len(split), 4)

    def test_seeded_count_sweep(self):
        # 0-64 screeners, unanimous and mixed lists, and 10 or more
        # disagreeing screeners, on every path.
        variants = sweep_count_variants()
        counts = {len(v) for v in variants}
        self.assertEqual(counts, set(SWEEP_COUNTS))
        unanimous_fwd = [v for v in variants
                         if v and all(r["passed"] == F.FORWARDED for r in v)]
        unanimous_other = [v for v in variants
                           if v and all(r["passed"] == v[0]["passed"] for r in v)
                           and v[0]["passed"] != F.FORWARDED]
        mixed = [v for v in variants
                 if len({tuple(r["passed"]) for r in v}) > 1]
        disagreeing_10 = [v for v in mixed if len(v) >= 10]
        self.assertEqual(len(unanimous_fwd), 64)
        self.assertEqual(len(unanimous_other), 64)
        self.assertGreaterEqual(len(mixed), 63)
        self.assertGreaterEqual(len(disagreeing_10), 55)
        self.assertEqual({len(v) for v in unanimous_fwd}, set(range(1, 65)))
        self.assertEqual({len(v) for v in disagreeing_10}, set(range(10, 65)))
        for path in PATHS:
            base_rec = S.report(path_request(path, []))
            self.assertTrue(PATHS[path][1](base_rec), (path, base_rec))
            base = figures(base_rec)
            for reports in variants:
                rec = S.report(path_request(path, reports))
                self.assertEqual(figures(rec), base, (path, len(reports)))
                self.assertEqual(rec["screener_count"], len(reports), path)


class Expiry(unittest.TestCase):

    def test_missing_on_expiry_is_config_error(self):
        for expired in (True, False):
            rec = S.report(F.request(deadline={"timeout_s": 5, "expired": expired}))
            self.assertEqual(rec["status"], S.CONFIG_ERROR)

    def test_on_expiry_closed_set(self):
        for v in ("report", "reported", "estimate", "dispatch", "HOLD", "", None,
                  SpoofStr("x"), RaisingObj()):
            rec = S.report(F.request(deadline={"timeout_s": 5, "on_expiry": v,
                                                "expired": True}))
            self.assertEqual(rec["status"], S.CONFIG_ERROR, repr(type(v)))

    def test_deadline_field_checks(self):
        for dl in ({"on_expiry": "hold"}, {"timeout_s": 0, "on_expiry": "hold"},
                   {"timeout_s": True, "on_expiry": "hold"},
                   {"timeout_s": SubInt(5), "on_expiry": "hold"},
                   {"timeout_s": 5, "on_expiry": "hold", "expired": 1},
                   {"timeout_s": 5, "on_expiry": "hold", "later": 1},
                   SubDict({"timeout_s": 5, "on_expiry": "hold"}), [1]):
            self.assertEqual(S.report(F.request(deadline=dl))["status"], S.CONFIG_ERROR, dl)

    def test_unexpired_deadline_records_constant(self):
        rec = S.report(F.request(deadline={"timeout_s": 5, "on_expiry": "".join("hold")}))
        self.assertEqual(rec["status"], S.REPORTED)
        self.assertIs(rec["on_expiry"], S.HOLD)
        self.assertIsNone(S.report(F.request())["on_expiry"])


class InputChecks(unittest.TestCase):

    def err(self, req, label=None):
        if type(req) is dict:
            # The validator itself names the defect; config_error is not
            # left to the catch-all.
            self.assertIsNotNone(S.validate(req), label)
        rec = S.report(req)
        self.assertEqual(rec["status"], S.CONFIG_ERROR, label)
        for k in FIGS:
            self.assertIsNone(rec[k]["value"], label)
        self.assertIsNone(rec["screener_count"])

    def test_non_mapping(self):
        for req in (None, [], "x", 3, SubDict(F.request()), RaisingObj()):
            self.err(req, repr(type(req)))

    def test_fields(self):
        req = F.request()
        req["note"] = 1
        self.err(req)
        for key in S.REQUEST_FIELDS:
            req = F.request()
            del req[key]
            self.err(req, key)
        req = F.request()
        req[SpoofStr("deadline")] = {"timeout_s": 5, "on_expiry": "hold"}
        self.err(req)

    def test_item_lists(self):
        for bad in (SubList(F.ITEMS), F.ITEMS + ["d00"], F.ITEMS + [""],
                    F.ITEMS + [SpoofStr("z")], F.ITEMS + [3], tuple(F.ITEMS)):
            self.err(F.request(items=bad), repr(bad)[:30])
        for bad in (["zz"], ["d01", "d01"], SubList(F.FORWARDED), [RaisingStr("d01")]):
            self.err(F.request(forwarded=bad, with_sample=False), repr(type(bad)))
        self.err(F.request(forwarded=["zz"], assessed_passes={"zz": "relevant"},
                           screener_reports=[], with_sample=False))

    def test_screener_reports_checked(self):
        bad = [None, SubList(), [None], [SubDict(screener="a", passed=[])],
               [{"screener": "a"}], [{"screener": "a", "passed": [], "w": 1}],
               [{"screener": "a", "passed": []}, {"screener": "a", "passed": []}],
               [{"screener": "", "passed": []}],
               [{"screener": SpoofStr("a"), "passed": []}],
               [{"screener": "a", "passed": ["zz"]}],
               [{"screener": "a", "passed": SubList()}]]
        for reps in bad:
            self.err(F.request(screener_reports=reps), repr(reps)[:40])

    def test_assessed_passes_checked(self):
        for bad in (SubDict(), {"d00": "relevant"}, {"d01": "yes"},
                    {"d01": SpoofStr("relevant")}, {SpoofStr("d01"): "relevant"},
                    None):
            self.err(F.request(assessed_passes=bad), repr(bad)[:30])

    def test_sample_checked(self):
        good = F.sample()
        muts = [lambda s: s.update(seed=True), lambda s: s.update(seed="1"),
                lambda s: s.update(seed=SubInt(1)), lambda s: s.update(seed=None),
                lambda s: s.update(seed=float(s["seed"])),
                lambda s: s.update(size=-1),
                lambda s: s.update(size=29), lambda s: s.update(size=True),
                lambda s: s.update(size=s["size"] + 1),
                lambda s: s.update(items=SubList(s["items"])),
                lambda s: s["items"].__setitem__(0, "d01"),
                lambda s: s.update(judgments=SubDict(s["judgments"])),
                lambda s: s["judgments"].pop(s["items"][0]),
                lambda s: s["judgments"].update(d01="relevant"),
                lambda s: s["judgments"].__setitem__(s["items"][0], "maybe"),
                lambda s: s.pop("judgments"), lambda s: s.update(extra=1)]
        for i, m in enumerate(muts):
            s = copy.deepcopy(good)
            m(s)
            self.err(F.request(not_passed_sample=s), i)
        self.err(F.request(not_passed_sample=SubDict(good)))
        s = copy.deepcopy(good)
        s["judgments"].pop(s["items"][0])
        s["items"][0] = F.FORWARDED[0]
        s["judgments"][F.FORWARDED[0]] = F.label(F.FORWARDED[0])
        self.err(F.request(not_passed_sample=s))
        self.err(F.request(not_passed_sample=None))

    def test_unseeded_sample_rejected_with_one_not_passed_item(self):
        # Seed None with a single not-passed item: any draw would match, so
        # only the seed type check stands between it and an estimate.
        items = list(F.FORWARDED) + ["d36"]
        good = {"seed": 0, "size": 1, "items": ["d36"],
                "judgments": {"d36": "relevant"}}
        req = F.request(items=items, not_passed_sample=good)
        self.assertEqual(S.report(req)["recall"]["status"], S.ESTIMATE)
        for seed in (None, 0.0):
            bad = dict(good, seed=seed)
            self.err(F.request(items=items, not_passed_sample=bad), seed)

    def test_internal_error_is_config_error(self):
        req = F.request()
        orig = S.draw_sample

        def boom(*args):
            raise RuntimeError("internal")
        S.draw_sample = boom
        try:
            rec = S.report(req)
        finally:
            S.draw_sample = orig
        self.assertEqual(rec["status"], S.CONFIG_ERROR)
        for k in FIGS:
            self.assertIsNone(rec[k]["value"])

    def test_raising_inputs_are_config_error(self):
        req = F.request()
        req["items"] = [RaisingStr("a")]
        self.err(req)
        req = F.request()
        req["not_passed_sample"]["items"] = [RaisingObj()]
        self.err(req)


class Fixtures(unittest.TestCase):

    def test_fixture_counts(self):
        self.assertEqual(len(F.ITEMS), 40)
        self.assertEqual(len(set(F.ITEMS)), 40)
        self.assertEqual(len(F.RELEVANT_TRUTH), 12)
        self.assertTrue(F.RELEVANT_TRUTH <= set(F.ITEMS))
        self.assertEqual(len(F.FORWARDED), len(set(F.FORWARDED)))
        self.assertEqual(F.true_recall(), (8, 12))

    def test_fixture_screeners_agree_fully(self):
        reps = F.screener_reports(3)
        self.assertTrue(all(r["passed"] == F.FORWARDED for r in reps))

    def test_fixture_sample_is_seeded_draw(self):
        s = F.sample()
        self.assertEqual(s["items"], random.Random(F.SEED).sample(sorted(F.not_passed()), F.SAMPLE_SIZE))
        for i in s["items"]:
            self.assertEqual(s["judgments"][i], F.label(i))

    def test_fixture_request_valid(self):
        self.assertIsNone(S.validate(F.request()))


class Docs(unittest.TestCase):

    def test_readme(self):
        text = flat("README.md")
        ev = json.loads(read("paper_evidence.json"))
        self.assertIn(ev["title"], text)
        for a in ev["authors"]:
            self.assertIn(a, text)
        for needle in ("http://arxiv.org/licenses/nonexclusive-distrib/1.0/",
                       "https://arxiv.org/abs/2611.12705", "method sketch, not law",
                       "synthetic", "Soft", "w18-phantom-consensus",
                       "not a voter or ensemble", "#91", "UNVERIFIED",
                       "to any chosen accuracy"):
            self.assertIn(needle, text, needle)

    def test_notice(self):
        text = flat("NOTICE")
        ev = json.loads(read("paper_evidence.json"))
        self.assertIn(ev["title"], text)
        self.assertIn("nonexclusive-distrib/1.0/", text)
        for a in ev["authors"]:
            self.assertIn(a, text)

    def test_paper_evidence(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["version"], "v1")
        for item in ev["method_quotes"] + ev["claims"]:
            self.assertEqual(item["status"], "UNVERIFIED")
        for item in ev["claims"]:
            self.assertIs(item["claimed_here"], False)
        self.assertTrue(ev["code"].startswith("UNVERIFIED"))

    def test_raise_wording_matches_behaviour(self):
        # report() turns an Exception into config_error but can raise
        # RecursionError on a nearly exhausted stack; no doc says otherwise.
        for name in ("screen_recall.py", "README.md"):
            text = flat(name)
            for claim in ("never raises", "does not raise", "doesn't raise"):
                self.assertNotIn(claim, text.lower(), (name, claim))
            self.assertIn("RecursionError", text, name)

    def test_accuracy_claim_not_made_in_code(self):
        for name in CODE:
            self.assertNotIn("chosen accuracy", read(name))

    def test_quotes_exact_in_source_copy(self):
        ev = json.loads(read("paper_evidence.json"))
        src = ev["abstract_copy"]
        if not SOURCES:
            self.skipTest("W21SR_SOURCES not set")
        path = os.path.join(SOURCES, src["file"])
        if not os.path.exists(path):
            self.skipTest("abstract copy not present")
        with open(path, "rb") as fh:
            data = fh.read()
        self.assertEqual(len(data), src["bytes"])
        self.assertEqual(hashlib.sha256(data).hexdigest(), src["sha256"])
        text = data.decode("utf-8")
        for item in ev["method_quotes"] + ev["claims"]:
            self.assertEqual(text.count(item["quote"]), 1, item["quote"][:40])

    def test_word_and_path_hygiene(self):
        banned = ["al" + "low", "ke" + "ep", "cloud" + "agent", "sm" + "ith", "che" + "cker"]
        paths = ["/work" + "space", "/t" + "mp", "/ho" + "me"]
        markers = ["<" * 7, ">" * 7, "=" * 7 + "\n"]
        texts = [(name, read(name)) for name in OWN]
        day = day_readme()
        if day is not None:
            with open(day, encoding="utf-8") as fh:
                texts.append(("day README", fh.read()))
        for name, text in texts:
            for w in banned:
                self.assertNotIn(w, text.lower(), (name, w))
            for p in paths:
                self.assertNotIn(p, text, (name, p))
            for m in markers:
                self.assertNotIn(m, text, (name, m))

    def test_day_index_footer(self):
        footer = "Do not merge experiment PRs without Ork review."
        path = day_readme()
        if path is None:
            self.skipTest("no day index next to this folder")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertTrue(text.startswith(DAY_HEADER))
        self.assertEqual(text.count(footer), 1)
        self.assertEqual(text.rstrip("\n").splitlines()[-1], footer)
        self.assertIn("- [w21-screen-recall-sample](w21-screen-recall-sample/):", text)
        for m in ("<" * 7, ">" * 7):
            self.assertNotIn(m, text)


if __name__ == "__main__":
    unittest.main()
