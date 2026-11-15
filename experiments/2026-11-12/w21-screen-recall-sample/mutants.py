"""Mutant runner: each mutant patches the code or the fixtures, then the
unittest suite runs. A mutant is killed when at least one test fails.

Code mutants replace exact snippets of screen_recall.py (each snippet must
occur exactly once) and re-execute the patched source in memory. World
mutants patch the fixtures module in memory. Nothing is written to disk.

Run: python3 -B mutants.py
Exit code 0 only when every mutant is killed and the clean suite passes.
"""

import io
import os
import sys
import unittest

import fixtures as F
import screen_recall as S
import test_screen_recall as T

S_SNAPSHOT = dict(vars(S))
F_SNAPSHOT = dict(vars(F))
S_PATH = os.path.join(os.path.dirname(os.path.abspath(S.__file__)), "screen_recall.py")
with open(S_PATH, "r", encoding="utf-8") as _fh:
    S_SOURCE = _fh.read()
SOURCE_READER = T.read


def src(*pairs):
    """apply(): swap each (old, new) snippet once, exec in memory, and make
    the suite's source scans read the patched text."""
    def apply():
        text = S_SOURCE
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError("snippet not found exactly once: %r" % (old,))
            text = text.replace(old, new)
        exec(compile(text, S_PATH, "exec"), S.__dict__)

        def read(name):
            return text if name == "screen_recall.py" else SOURCE_READER(name)
        T.read = read
    return apply


FWD = 'forwarded = request["forwarded"]\n    assessed = request["assessed_passes"]'
UN = ('(len(request.get(REQUEST_FIELDS[2])) >= 4 and all(r["passed"] == '
      'request["forwarded"] for r in request.get(REQUEST_FIELDS[2])))')

CODE = [
    ("majority rule over screener reports (named)", src(
        (FWD, 'forwarded = request["forwarded"]\n'
              '    reps = request["screener_reports"]\n'
              '    if reps:\n'
              '        majority = [i for i in forwarded\n'
              '                    if sum(1 for r in reps if i in r["passed"]) * 2 > len(reps)]\n'
              '        forwarded = majority\n'
              '    assessed = request["assessed_passes"]'))),
    ("majority rule over screener reports (renamed)", src(
        (FWD, 'forwarded = request["forwarded"]\n'
              '    rs = request["screener_reports"]\n'
              '    if rs:\n'
              '        forwarded = [i for i in forwarded\n'
              '                     if len([r for r in rs if i in r["passed"]]) * 2 > len(rs)]\n'
              '    assessed = request["assessed_passes"]'))),
    ("agreeing screeners unlock recall", src(
        ('    elif sample is None:\n        recall = _unmeasured(NO_NOT_PASSED_SAMPLE)',
         '    elif sample is None and n_screeners >= 2:\n'
         '        recall = _fig(ESTIMATE, Fraction(found, max(found, 1)))\n'
         '    elif sample is None:\n        recall = _unmeasured(NO_NOT_PASSED_SAMPLE)'))),
    ("lower bound reported as recall", src(
        ('recall = _unmeasured(NO_NOT_PASSED_SAMPLE)',
         'recall = dict(lower, status=ESTIMATE)'))),
    ("empty sample not special-cased", src(
        ('elif sample["size"] == 0:', 'elif False:'))),
    ("seeded-draw check skipped", src(
        ('if list(sample["items"]) != drawn:', 'if False:'))),
    ("estimate not scaled to not-passed count", src(
        ('Fraction(hits * not_passed_count, sample["size"])', 'Fraction(hits)'))),
    ("estimate scaled to all items", src(
        ('Fraction(hits * not_passed_count, sample["size"])',
         'Fraction(hits * len(items), sample["size"])'))),
    ("lower bound equals precision", src(
        ('Fraction(found, found + not_passed_count)', 'Fraction(found, len(forwarded))'))),
    ("precision over all items", src(
        ('Fraction(found, len(forwarded))', 'Fraction(found, len(items))'))),
    ("partial assessment measured", src(
        ('    elif None in labels:\n        precision = _unmeasured(PASSES_NOT_FULLY_ASSESSED)',
         '    elif False:\n        precision = _unmeasured(PASSES_NOT_FULLY_ASSESSED)'))),
    ("recall ignores unassessed passes", src(
        ('passes_ok = None not in labels and ', 'passes_ok = '))),
    ("expiry ignored", src(
        ('if dl.get("expired", False) is True:', 'if False:'))),
    ("record echoes caller on_expiry", src(
        ('on_expiry = _canonical(dl["on_expiry"], ON_EXPIRY_VALUES)',
         'on_expiry = dl["on_expiry"]'))),
    ("missing on_expiry defaults to hold", src(
        ('if "on_expiry" not in dl:\n            return "deadline declares a timeout without on_expiry"\n',
         'if False:\n            return "unreachable"\n'),
        ('if _canonical(dl["on_expiry"], ON_EXPIRY_VALUES) is None:',
         'if _canonical(dl.get("on_expiry", HOLD), ON_EXPIRY_VALUES) is None:'),
        ('on_expiry = _canonical(dl["on_expiry"], ON_EXPIRY_VALUES)',
         'on_expiry = dl.get("on_expiry", HOLD)'))),
    ("pending without deadline accepted", src(
        ('    elif pending:\n        return', '    elif False:\n        return'))),
    ("pending sample judgment read as not relevant", src(
        ('elif JUDGMENT_PENDING in s_labels:', 'elif False:'))),
    ("pending pass ignored", src(
        ('    elif JUDGMENT_PENDING in labels:\n        precision = _unmeasured(ASSESSMENT_PENDING)',
         '    elif False:\n        precision = _unmeasured(ASSESSMENT_PENDING)'))),
    ("on_expiry set opened", src(
        ('ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY)',
         'ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY, REPORTED)'))),
    ("isinstance str", src(
        ('return type(v) is str and len(v) > 0', 'return isinstance(v, str) and len(v) > 0'),
        ('    if type(value) is not str:\n        return None',
         '    if not isinstance(value, str):\n        return None'))),
    ("isinstance dict", src(('return type(v) is dict', 'return isinstance(v, dict)'))),
    ("isinstance list", src(('return type(v) is list', 'return isinstance(v, list)'))),
    ("bool accepted as int", src(('return type(v) is int', 'return isinstance(v, int)'))),
    ("report without try/except", src(
        ('    try:\n        return _report(request)\n    except Exception:\n'
         '        return _record(CONFIG_ERROR)',
         '    return _report(request)'))),
    ("judgments of non-forwarded items accepted", src(
        ('if not _is_str(k) or k not in fwd:', 'if not _is_str(k):'))),
    ("sample may hold forwarded items", src(
        ('_id_list(sample["items"], not_passed)', '_id_list(sample["items"])'))),
    ("sample size mismatch accepted", src(
        ('if s_items is None or len(s_items) != size:', 'if s_items is None:'))),
    ("sample judgments may be partial", src(
        ('    if len(value) != len(keys):\n        return None', '    if False:\n        return None'))),
    ("unknown request field accepted", src(
        ('            return "unknown field"\n', '            continue\n'))),
    ("duplicate screener id accepted", src(
        ('if not _is_str(rep["screener"]) or rep["screener"] in names:',
         'if not _is_str(rep["screener"]):'))),
    ("draw not sorted first", src(
        ('sample(sorted(not_passed), size)', 'sample(list(not_passed), size)'))),
    ("interval claimed", src(('interval=None)', 'interval=(0.0, 1.0))'))),
    ("non-bool expired accepted", src(
        ('if "expired" in dl and type(dl["expired"]) is not bool:', 'if False:'))),
    ("timeout type unchecked", src(
        ('if not _is_int(timeout) or timeout <= 0:', 'if timeout is None or timeout <= 0:'))),
    ("forwarded ids not checked against items", src(
        ('forwarded = _id_list(request["forwarded"], universe)',
         'forwarded = _id_list(request["forwarded"])'))),
    # Gated on 4+ screeners all passing the forwarded list, read through a
    # computed key so no literal "screener_reports" appears (K1-K3).
    ("K1 unanimous 4+ waive the seeded-draw check", src(
        ('if list(sample["items"]) != drawn:',
         'if list(sample["items"]) != drawn and not ' + UN + ':'))),
    ("K2 unanimous 4+ bypass expiry", src(
        ('if dl.get("expired", False) is True:',
         'if dl.get("expired", False) is True and not ' + UN + ':'))),
    ("K3 unanimous 4+ read pending sample as judged", src(
        ('elif JUDGMENT_PENDING in s_labels:',
         'elif JUDGMENT_PENDING in s_labels and not ' + UN + ':'))),
    ("K12 seed None accepted", src(
        ('if not _is_int(sample["seed"]):',
         'if sample["seed"] is not None and not _is_int(sample["seed"]):'))),
    ("K15 upper field on the lower bound", src(
        ('found=found, not_passed=not_passed_count)',
         'found=found, not_passed=not_passed_count, upper=1.0)'))),
    ("K16 agreement field on recall", src(
        ('return _record(status, on_expiry, n_screeners, precision, lower, recall)',
         'recall = dict(recall, concur=sum(1 for r in request.get(REQUEST_FIELDS[2])'
         ' if r["passed"] == forwarded))\n'
         '    return _record(status, on_expiry, n_screeners, precision, lower, recall)'))),
    ("K18 deadline needed only with a sample", src(
        ('    elif pending:\n        return "a pending judgment needs a declared deadline"',
         '    elif pending and "not_passed_sample" in request:\n'
         '        return "a pending judgment needs a declared deadline"'))),
    # r3: stash, alias, process-RNG and disagreement gates the new tests close.
    ("global stash 51+ unanimous waive the seeded-draw check", src(
        ('    assessed = request["assessed_passes"]\n    if not _is_dict(assessed):',
         '    global _U\n'
         '    _U = (len(reports) >= 51 and '
         'all(r["passed"] == forwarded for r in reports))\n'
         '    assessed = request["assessed_passes"]\n    if not _is_dict(assessed):'),
        ('if list(sample["items"]) != drawn:',
         'if list(sample["items"]) != drawn and not _U:'))),
    ("locals alias of request waives the seeded-draw check at 51+", src(
        ('    n_screeners = len(request["screener_reports"])',
         '    n_screeners = len(request["screener_reports"])\n'
         '    rq = locals()["request"]'),
        ('if list(sample["items"]) != drawn:',
         'if list(sample["items"]) != drawn and not ('
         'len(rq[REQUEST_FIELDS[2]]) >= 51 and '
         'all(r["passed"] == rq["forwarded"] for r in rq[REQUEST_FIELDS[2]])):'))),
    ("draw reseeds the process random", src(
        ('return random.Random(seed).sample(sorted(not_passed), size)',
         'random.seed(seed)\n    return random.sample(sorted(not_passed), size)'))),
    ("ten or more disagreeing screeners is a config error", src(
        ('    assessed = request["assessed_passes"]\n    if not _is_dict(assessed):',
         '    if (len(reports) >= 10 and '
         'len({tuple(r["passed"]) for r in reports}) > 1):\n'
         '        return "screeners disagree"\n'
         '    assessed = request["assessed_passes"]\n    if not _is_dict(assessed):'))),
]


def w_screeners_disagree():
    F.screener_reports = lambda n: [{"screener": "s%d" % k,
                                     "passed": list(F.FORWARDED[k:])} for k in range(n)]


def w_sample_cherry_picked():
    def sample(size=F.SAMPLE_SIZE, seed=F.SEED):
        picked = sorted(F.not_passed())[:size]
        return {"seed": seed, "size": size, "items": picked,
                "judgments": {i: F.label(i) for i in picked}}
    F.sample = sample


def w_sample_mislabelled():
    orig = F_SNAPSHOT["sample"]

    def sample(size=F.SAMPLE_SIZE, seed=F.SEED):
        s = orig(size, seed)
        s["judgments"] = {i: S.NOT_RELEVANT for i in s["items"]}
        return s
    F.sample = sample


def w_truth_drops_a_miss():
    F.RELEVANT_TRUTH = frozenset(F_SNAPSHOT["RELEVANT_TRUTH"] - {"d36"})


def w_forwarded_duplicate():
    F.FORWARDED = list(F_SNAPSHOT["FORWARDED"]) + ["d01"]


def w_sample_size_zero():
    F.SAMPLE_SIZE = 0


def w_passes_partially_judged():
    orig = F_SNAPSHOT["request"]

    def request(n_screeners=3, with_sample=True, **overrides):
        req = orig(n_screeners, with_sample, **overrides)
        if "assessed_passes" not in overrides:
            req["assessed_passes"].pop(F.FORWARDED[0], None)
        return req
    F.request = request


def w_sample_includes_forwarded():
    orig = F_SNAPSHOT["sample"]

    def sample(size=F.SAMPLE_SIZE, seed=F.SEED):
        s = orig(size, seed)
        if s["items"]:
            s["judgments"].pop(s["items"][0])
            s["items"][0] = F.FORWARDED[0]
            s["judgments"][F.FORWARDED[0]] = F.label(F.FORWARDED[0])
        return s
    F.sample = sample


def w_assessor_reads_screeners_not_truth():
    F.label = lambda item: S.RELEVANT if item in F.FORWARDED else S.NOT_RELEVANT


WORLD = [
    ("fixture screeners disagree", w_screeners_disagree),
    ("fixture sample cherry-picked", w_sample_cherry_picked),
    ("fixture sample mislabelled", w_sample_mislabelled),
    ("truth table drops a missed item", w_truth_drops_a_miss),
    ("forwarded list has a duplicate", w_forwarded_duplicate),
    ("fixture sample size zero", w_sample_size_zero),
    ("fixture passes partially judged", w_passes_partially_judged),
    ("fixture sample includes a forwarded item", w_sample_includes_forwarded),
    ("assessor stand-in trusts the screeners", w_assessor_reads_screeners_not_truth),
]

MUTANTS = [("code", n, a) for n, a in CODE] + [("world", n, a) for n, a in WORLD]


def restore():
    for mod, snap in ((S, S_SNAPSHOT), (F, F_SNAPSHOT)):
        for name in [n for n in vars(mod) if n not in snap]:
            delattr(mod, name)
        mod.__dict__.update(snap)
    T.read = SOURCE_READER


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(T)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


def main():
    restore()
    ran, bad = run_suite()
    print("clean suite: %d tests, %d failing" % (ran, bad))
    clean_ok = bad == 0
    killed = {"code": 0, "world": 0}
    totals = {"code": 0, "world": 0}
    for kind, name, apply in MUTANTS:
        totals[kind] += 1
        try:
            apply()
            ran, bad = run_suite()
        except Exception as exc:
            restore()
            print("%-5s %-46s BROKEN   (%s)" % (kind, name, type(exc).__name__))
            continue
        finally:
            restore()
        status = "KILLED" if bad else "SURVIVED"
        killed[kind] += 1 if bad else 0
        print("%-5s %-46s %-8s (%d/%d tests failing)" % (kind, name, status, bad, ran))
    ran, bad = run_suite()
    print("clean suite after restore: %d tests, %d failing" % (ran, bad))
    clean_ok = clean_ok and bad == 0
    k = killed["code"] + killed["world"]
    print("killed %d/%d (code %d/%d, world %d/%d)" % (
        k, len(MUTANTS), killed["code"], totals["code"], killed["world"], totals["world"]))
    return 0 if clean_ok and k == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
