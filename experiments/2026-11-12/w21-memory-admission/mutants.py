"""Mutant runner: each mutant patches the code or the fixtures, then the
unittest suite runs. A mutant is killed when at least one test fails.

Code mutants replace exact snippets of memory_admission.py (each snippet
must occur exactly once) and re-execute the patched source in memory inside
the module. World mutants patch the fixtures module in memory. Nothing is
written to disk.

Run: python3 -B mutants.py
Exit code 0 only when every mutant is killed and the clean suite passes.
"""

import copy
import io
import os
import sys
import unittest

import fixtures as F
import memory_admission as M
import test_memory_admission as T

M_SNAPSHOT = dict(vars(M))
F_SNAPSHOT = dict(vars(F))
F_CANDIDATES = copy.deepcopy(F.CANDIDATES)
F_THRESHOLDS = dict(F.THRESHOLDS)
M_PATH = os.path.join(os.path.dirname(os.path.abspath(M.__file__)),
                      "memory_admission.py")
with open(M_PATH, "r", encoding="utf-8") as _fh:
    M_SOURCE = _fh.read()


def src(*pairs):
    """Return an apply() that swaps each (old, new) snippet once."""
    def apply():
        text = M_SOURCE
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError("snippet not found exactly once: %r" % (old,))
            text = text.replace(old, new)
        exec(compile(text, M_PATH, "exec"), M.__dict__)
    return apply


CODE = [
    ("local success alone commits", src(
        ('if request["local_success"] is not True:\n'
         '        return _record(hid, REJECT, SOURCE_EPISODE_FAILED, on_expiry)',
         'if request["local_success"] is True:\n'
         '        store._commit(_freeze(request["hypothesis"]))\n'
         '        return _record(hid, COMMIT, ALL_PROBES_PASSED, on_expiry, (), None, True)'))),
    ("missing probe treated as empty", src(
        ('if name not in probes or len(probes[name]) == 0:',
         'if name in probes and len(probes[name]) == 0:'),
        ('_measure(base, temp, lesson, verifier, probes[name])',
         '_measure(base, temp, lesson, verifier, probes.get(name, []))'))),
    ("empty probe counts as run", src(
        ('len(probes[name]) == 0', 'len(probes[name]) < 0'))),
    ("vacuous falsification accepted", src(
        ('if fa["decided"] == 0:', 'if False:'))),
    ("falsification ignored", src(
        ('falsification_ok = fa["temp_ok"] == fa["n"]', 'falsification_ok = True'))),
    ("archived regression ignored", src(
        ('regression_ok = rg["broken"] == 0', 'regression_ok = True'))),
    ("target transfer ignored", src(
        ('transfer_ok = tr["temp_ok"] == tr["n"] and gain > 0', 'transfer_ok = True'))),
    ("transfer without measured gain", src(
        ('transfer_ok = tr["temp_ok"] == tr["n"] and gain > 0',
         'transfer_ok = tr["temp_ok"] == tr["n"]'))),
    ("partial transfer passes", src(
        ('transfer_ok = tr["temp_ok"] == tr["n"] and gain > 0',
         'transfer_ok = tr["temp_ok"] > 0 and gain > 0'))),
    ("regression counts already-failing tasks", src(
        ('broken += 1 if (b and not t) else 0', 'broken += 1 if (not t) else 0'))),
    ("temporary state aliases the store", src(
        ('temp = list(store._lessons) + [lesson]',
         'temp = store._lessons\n    temp.append(lesson)'))),
    ("candidate placed before archived lessons", src(
        ('temp = list(store._lessons) + [lesson]',
         'temp = [lesson] + list(store._lessons)'))),
    ("falsification failure falls through", src(
        ('    if not falsification_ok:\n        return _record(hid, REJECT, FALSIFICATION_FAILED',
         '    if False:\n        return _record(hid, REJECT, FALSIFICATION_FAILED'))),
    ("refine writes the lesson", src(
        ('return _record(hid, REFINE, WITHIN_REFINE_BOUNDS',
         'return (store._commit(lesson) and None) or _record(hid, REFINE, WITHIN_REFINE_BOUNDS'))),
    ("gain threshold strict", src(
        ('>= th["refine_min_gain_pct"]', '> th["refine_min_gain_pct"]'))),
    ("risk threshold strict", src(
        ('<= th["refine_max_risk_pct"]', '< th["refine_max_risk_pct"]'))),
    ("refine ignores risk", src(
        ('if gain_ok and risk_ok:', 'if gain_ok:'))),
    ("zero min gain accepted", src(
        ('gain < 1 or gain > 100', 'gain < 0 or gain > 100'))),
    ("undeclared thresholds defaulted", src(
        ('if key not in thresholds:\n            return', 'if False:\n            return'),
        ('gain = thresholds["refine_min_gain_pct"]',
         'gain = thresholds.get("refine_min_gain_pct", 1)'),
        ('risk = thresholds["refine_max_risk_pct"]',
         'risk = thresholds.get("refine_max_risk_pct", 100)'),
        ('th = request["thresholds"]',
         'th = dict({"refine_min_gain_pct": 1, "refine_max_risk_pct": 100}, **request["thresholds"])'))),
    ("bool accepted as int", src(
        ('return type(value) is int', 'return isinstance(value, int)'))),
    ("isinstance str", src(
        ('    return type(value) is str\n', '    return isinstance(value, str)\n'),
        ('return type(value) is str and len(value) > 0',
         'return isinstance(value, str) and len(value) > 0'))),
    ("isinstance dict", src(
        ('return type(value) is dict', 'return isinstance(value, dict)'))),
    ("isinstance list", src(
        ('return type(value) is list', 'return isinstance(value, list)'))),
    ("store subclass accepted", src(
        ('type(store) is not MemoryStore', 'not isinstance(store, MemoryStore)'))),
    ("admit without try/except", src(
        ('    try:\n        return _admit(store, request)\n    except Exception:\n'
         '        return _record(None, CONFIG_ERROR, CONFIG_ERROR)',
         '    return _admit(store, request)'))),
    ("expiry ignored, probes run", src(
        ('if deadline.get("expired", False) is True:', 'if False:'))),
    ("expiry commits", src(
        ('            return _record(hid, EXPIRED, EXPIRED, on_expiry)',
         '            store._commit(_freeze(request["hypothesis"]))\n'
         '            return _record(hid, EXPIRED, EXPIRED, on_expiry, (), None, True)'))),
    ("missing on_expiry defaults to hold", src(
        ('if "on_expiry" not in deadline:\n            return "deadline declares a timeout without on_expiry"\n',
         'if False:\n            return "unreachable"\n'),
        ('if _canonical(deadline["on_expiry"], ON_EXPIRY_VALUES) is None:',
         'if _canonical(deadline.get("on_expiry", HOLD), ON_EXPIRY_VALUES) is None:'),
        ('on_expiry = _canonical(deadline["on_expiry"], ON_EXPIRY_VALUES)',
         'on_expiry = deadline.get("on_expiry", HOLD)'))),
    ("record echoes caller on_expiry", src(
        ('on_expiry = _canonical(deadline["on_expiry"], ON_EXPIRY_VALUES)',
         'on_expiry = deadline["on_expiry"]'))),
    ("on_expiry set opened", src(
        ('ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY)',
         'ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY, COMMIT)'))),
    ("unknown request field accepted", src(
        ('return "unknown request field"', 'continue'))),
    ("unknown probe accepted", src(
        ('            return "unknown probe"\n', '            continue\n'))),
    ("duplicate lesson id accepted", src(
        ('if hyp["id"] in store.ids():', 'if False:'))),
    ("precondition with several = accepted", src(
        ('text.count("=") != 1', 'text.count("=") < 1'))),
    ("unknown verifier accepted", src(
        ('if _canonical(hyp["verifier"], VERIFIERS) is None:', 'if False:'))),
    ("commit stores the caller dict", src(
        ('if not store._commit(lesson):',
         'if not store._commit((hyp["id"], hyp, hyp, hyp)):'))),
    ("F5 id read before validation", src(
        ('    error = validate(store, request)\n    if error is not None:\n'
         '        return _record(None, CONFIG_ERROR, CONFIG_ERROR)',
         '    hid = None\n'
         '    if _is_dict(request) and _is_dict(request.get("hypothesis")):\n'
         '        candidate = request["hypothesis"].get("id")\n'
         '        if _is_nonempty_str(candidate):\n'
         '            hid = _str_copy(candidate)\n'
         '    error = validate(store, request)\n    if error is not None:\n'
         '        return _record(hid, CONFIG_ERROR, CONFIG_ERROR)'))),
    ("F1 vacuity counts shadowed tasks", src(
        ('if fa["decided"] == 0:', 'if fa["matched"] == 0:'))),
    ("F1 decided ignores shadowing", src(
        ('decided += 1 if (hit and not shadowed) else 0', 'decided += 1 if hit else 0'))),
    ("F2 unsolved archive accepted", src(
        ('if rg["base_ok"] == 0:', 'if False:'))),
    ("shadow check only last stored lesson", src(
        ('for old in base)', 'for old in base[-1:])'))),
    ("archive vacuity uses temp_ok", src(
        ('if rg["base_ok"] == 0:', 'if rg["temp_ok"] == 0:'))),
    ("F3 commit claim not checked", src(
        ('if self._claimed.setdefault(lesson[0], token) is not token:\n            return False',
         'if False:\n            return False'))),
    ("F3 commit result ignored", src(
        ('if not store._commit(lesson):', 'if store._commit(lesson) and False:'))),
    ("F6 seed lessons not validated", src(
        ('error = validate_hypothesis(lesson)', 'error = None'))),
    ("F6 duplicate seed id accepted", src(
        ('            if not self._commit(frozen):\n                raise',
         '            self._commit(frozen)\n            if False:\n                raise'))),
    ("local_success by equality", src(
        ('type(request["local_success"]) is not bool',
         'request["local_success"] not in (True, False)'))),
    ("unknown task field accepted", src(
        ('return "unknown task field"', 'continue'))),
    ("feature values unchecked", src(
        ('if not _is_nonempty_str(key) or not _is_nonempty_str(features[key]):',
         'if not _is_nonempty_str(key):'))),
    ("timeout type unchecked", src(
        ('if not _is_int(timeout) or timeout <= 0:',
         'if timeout is None or timeout <= 0:'))),
    ("non-bool expired accepted", src(
        ('if "expired" in deadline and type(deadline["expired"]) is not bool:',
         'if False:'))),
    ("last matching lesson wins", src(
        ('    for lesson in lessons:\n        if matches(lesson, task):',
         '    for lesson in reversed(lessons):\n        if matches(lesson, task):'))),
    ("falsification failure not recorded", src(
        ('failed.append(FALSIFICATION)', 'pass'))),
    ("on_unmeasured writes anyway", src(
        ('            return _record(hid, ON_UNMEASURED, PROBE_NOT_RUN',
         '            store._commit(lesson)\n            return _record(hid, ON_UNMEASURED, PROBE_NOT_RUN'))),
    ("reject reason always transfer", src(
        ('reason = REGRESSION_FAILED if not regression_ok else TRANSFER_FAILED',
         'reason = TRANSFER_FAILED'))),
]


def candidate(name, transfer=None, falsification=None):
    hyp, tr, fa = F.CANDIDATES[name]
    F.CANDIDATES[name] = (hyp, tr if transfer is None else transfer,
                          fa if falsification is None else falsification)


def w_weak_falsification_for_false():
    candidate("false", falsification=[F.task("fa-csv-large", "csv", "large")])


def w_archive_without_small_json():
    orig = F_SNAPSHOT["archive"]
    F.archive = lambda: [t for t in orig() if t["id"] != "arc-json-small"]


def w_mislabel_transfer_task():
    bad = F.task("tr-csv-large", "csv", "large")
    bad["expected_action"] = "parse_whole"
    candidate("good", transfer=[bad, F.task("tr-json-large", "json", "large")])


def w_seed_store_empty():
    F.seed_store = lambda: M.MemoryStore()


def w_duplicate_task_id():
    candidate("narrow", falsification=[F.task("fa-xml-large", "xml", "huge")])


def w_narrow_transfer_full():
    candidate("narrow", transfer=[F.task("tr-csv-huge-2", "csv", "huge")])


def w_noop_falsification_vacuous():
    candidate("no_transfer", falsification=[F.task("fa-csv-small-2", "csv", "small")])


def w_later_task_inside_probe():
    hyp, tr, fa = F.CANDIDATES["good"]
    F.CANDIDATES["good"] = (hyp, tr + [F.LATER_TASK], fa)


def w_seed_store_gains_shadowing_lesson():
    # Verifier W01: a correct stored lesson decides H-false's small csv.
    F.seed_store = lambda: M.MemoryStore([F.SEED_LESSON, {
        "id": "L1", "precondition": "size=small", "behavior_change": "parse_whole",
        "expected_effect": "small inputs are parsed whole",
        "verifier": M.ACTION_MATCHES_EXPECTED}])


def w_good_falsification_only_shadowed():
    # Verifier W03: H-good's falsification set is the one task L0 decides.
    candidate("good", falsification=[F.task("fa-log-large", "log", "large")])


def w_lax_thresholds():
    F.THRESHOLDS = {"refine_min_gain_pct": 1, "refine_max_risk_pct": 100}


def w_local_failure_in_fixtures():
    orig = F_SNAPSHOT["request"]

    def request(name, drop=(), **overrides):
        req = orig(name, drop, **overrides)
        if "local_success" not in overrides:
            req["local_success"] = False
        return req
    F.request = request


def w_archive_differs_per_candidate():
    orig = F_SNAPSHOT["request"]

    def request(name, drop=(), **overrides):
        req = orig(name, drop, **overrides)
        if name == "breaks_archive" and M.ARCHIVED_REGRESSION in req["probes"]:
            req["probes"][M.ARCHIVED_REGRESSION] = [
                t for t in req["probes"][M.ARCHIVED_REGRESSION]
                if t["id"] != "arc-json-small"]
        return req
    F.request = request


WORLD = [
    ("weak falsification set for H-false", w_weak_falsification_for_false),
    ("archive loses the task H-breaks breaks", w_archive_without_small_json),
    ("one transfer task mislabelled", w_mislabel_transfer_task),
    ("seed store loses archived lesson L0", w_seed_store_empty),
    ("duplicate task id", w_duplicate_task_id),
    ("narrow candidate given a full transfer", w_narrow_transfer_full),
    ("H-noop falsification made vacuous", w_noop_falsification_vacuous),
    ("later task placed inside a probe", w_later_task_inside_probe),
    ("lax refine thresholds", w_lax_thresholds),
    ("seed store gains a shadowing lesson", w_seed_store_gains_shadowing_lesson),
    ("H-good falsification only shadowed", w_good_falsification_only_shadowed),
    ("fixture episodes not locally successful", w_local_failure_in_fixtures),
    ("archive differs for one candidate", w_archive_differs_per_candidate),
]

MUTANTS = [("code", n, a) for n, a in CODE] + [("world", n, a) for n, a in WORLD]


def restore():
    for mod, snap in ((M, M_SNAPSHOT), (F, F_SNAPSHOT)):
        for name in [n for n in vars(mod) if n not in snap]:
            delattr(mod, name)
        mod.__dict__.update(snap)
    F.CANDIDATES = copy.deepcopy(F_CANDIDATES)
    F.THRESHOLDS = dict(F_THRESHOLDS)


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
    total = len(MUTANTS)
    k = killed["code"] + killed["world"]
    print("killed %d/%d (code %d/%d, world %d/%d)" % (
        k, total, killed["code"], totals["code"], killed["world"], totals["world"]))
    return 0 if clean_ok and k == total else 1


if __name__ == "__main__":
    sys.exit(main())
