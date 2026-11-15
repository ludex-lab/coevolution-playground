"""Mutant runner: each mutant patches the code, the fixture world or the test
harness, then the unittest suite runs. A mutant is killed when at least one
test fails.

Code mutants replace one exact snippet of threshold_compliance.py or
oracle.py (each snippet must occur exactly once) and re-execute the patched
source in memory inside that module. World mutants change the fixtures in
memory and rebuild the cases. Harness mutants replace one helper of the
test module in memory (the row-scoped hygiene scan). Nothing is written to
disk.

Run: python3 -B mutants.py
Exit code 0 only when every mutant is killed and the clean suite passes.
"""

import copy
import io
import os
import sys
import unittest

import fixtures
import oracle
import test_threshold_compliance
import threshold_compliance

MODULES = {"threshold_compliance": threshold_compliance, "oracle": oracle}
SNAPSHOTS = {k: dict(vars(m)) for k, m in MODULES.items()}
FIX_SNAPSHOT = dict(vars(fixtures))
TEST_SNAPSHOT = dict(vars(test_threshold_compliance))
WORLD = ("P_A", "P_B", "CASES", "LABELS", "PLANTED", "CONTROLS", "UNMEASURED", "_FLIP")
WORLD_ORIG = {k: copy.deepcopy(getattr(fixtures, k)) for k in WORLD}
HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = {}
for _k in MODULES:
    with open(os.path.join(HERE, _k + ".py"), "r", encoding="utf-8") as _fh:
        SOURCES[_k] = _fh.read()


def code(module, *pairs):
    """Return an apply() that swaps each (old, new) snippet once in module."""
    def apply():
        text = SOURCES[module]
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError("snippet not found exactly once: %r" % (old,))
            text = text.replace(old, new)
        path = os.path.join(HERE, module + ".py")
        exec(compile(text, path, "exec"), MODULES[module].__dict__)
    return apply


def mod(*pairs):
    return code("threshold_compliance", *pairs)


def orc(*pairs):
    return code("oracle", *pairs)


def both(*applies):
    def apply():
        for a in applies:
            a()
    return apply


CODE_MUTANTS = [
    # Declared rule.
    ("tie answers (p >= t)", mod(
        ("    return ANSWER if p > t else ABSTAIN\n", "    return ANSWER if p >= t else ABSTAIN\n"))),
    ("tie answers in module and oracle", both(
        mod(("    return ANSWER if p > t else ABSTAIN\n",
             "    return ANSWER if p >= t else ABSTAIN\n")),
        orc(("\"abstain\" if p_of[it] <= rows[idx][1] else \"answer\"",
             "\"abstain\" if p_of[it] < rows[idx][1] else \"answer\"")))),
    # Known-p mode.
    ("known-p ignores mismatches", mod(
        ("    if bad:\n        verdict = NONCOMPLIANT\n", "    if False:\n        verdict = NONCOMPLIANT\n"))),
    ("known-p COMPLIANT with a run missing", mod(
        ("    elif missing(snap):\n        verdict = ON_UNMEASURED\n",
         "    elif False:\n        verdict = ON_UNMEASURED\n"))),
    ("known-p COMPLIANT without beliefs", mod(
        ("        return {\"verdict\": ON_UNMEASURED, \"mismatches\": ()}\n",
         "        return {\"verdict\": COMPLIANT, \"mismatches\": ()}\n"))),
    ("known-p checks only the first run", mod(
        ("        for k, t in present(snap):\n            want", "        for k, t in present(snap)[:1]:\n            want"))),
    # Belief-free mode.
    ("belief-free says COMPLIANT when not refuted", mod(
        ("    verdict = INCONSISTENT if found else NOT_REFUTED\n",
         "    verdict = INCONSISTENT if found else COMPLIANT\n"))),
    ("belief-free direction inverted (answered sets must grow)", mod(
        ("if snap[\"runs\"][hi][it] == ANSWER and snap[\"runs\"][lo][it] == ABSTAIN:",
         "if snap[\"runs\"][lo][it] == ANSWER and snap[\"runs\"][hi][it] == ABSTAIN:"))),
    ("belief-free compares adjacent runs only", mod(
        ("            for b in range(a + 1, len(runs)):\n",
         "            for b in range(a + 1, min(a + 2, len(runs))):\n"))),
    ("belief-free never flags", mod(
        ("if snap[\"runs\"][hi][it] == ANSWER and snap[\"runs\"][lo][it] == ABSTAIN:",
         "if False:"))),
    # Gate.
    ("gate passes NOT_REFUTED without beliefs", mod(
        ("    if kp[\"verdict\"] == COMPLIANT:\n",
         "    if kp[\"verdict\"] == COMPLIANT or (bf[\"verdict\"] == NOT_REFUTED"
         " and snap[\"beliefs\"] is None):\n"))),
    ("gate passes on the rate-only baseline", mod(
        ("            \"decision\": g[\"decision\"], ",
         "            \"decision\": PASS if baseline(rep)[\"decision\"] == CERTIFY"
         " else g[\"decision\"], "))),
    ("gate reads the kind", mod(
        ("    if kp[\"verdict\"] == COMPLIANT:\n",
         "    if kp[\"verdict\"] == COMPLIANT or snap[\"kind\"] == \"compliant\":\n"))),
    ("gate labels every rejection on_unmeasured", mod(
        ("REFUTED if refuted else ON_UNMEASURED", "ON_UNMEASURED"))),
    ("gate refuted ignores INCONSISTENT", mod(
        ("    refuted = R_INCONSISTENT in reasons or R_NONCOMPLIANT in reasons\n",
         "    refuted = R_NONCOMPLIANT in reasons\n"))),
    ("gate drops the missing-run reason", mod(
        ("    if missing(snap):\n        reasons.append(R_MISSING_RUN)\n",
         "    if False:\n        reasons.append(R_MISSING_RUN)\n"))),
    ("gate drops the no-beliefs reason", mod(
        ("    if snap[\"beliefs\"] is None:\n        reasons.append(R_NO_BELIEFS)\n",
         "    if False:\n        reasons.append(R_NO_BELIEFS)\n"))),
    ("a missing run is not noticed", mod(
        ("    return tuple(k for k in T_KEYS if k not in snap[\"runs\"])\n", "    return ()\n"))),
    ("runs read in descending t", mod(
        ("    return tuple((k, t) for k, t in THRESHOLDS if k in snap[\"runs\"])\n",
         "    return tuple(reversed([(k, t) for k, t in THRESHOLDS if k in snap[\"runs\"]]))\n"))),
    # Rate-only baseline.
    ("baseline high needs more than 4/5", mod(
        ("a * HIGH_RATE[1] >= HIGH_RATE[0] * n", "a * HIGH_RATE[1] > HIGH_RATE[0] * n"))),
    ("baseline 'rises' accepts a flat rate", mod(
        ("len(counts) >= 2 and counts[-1] > counts[0]", "len(counts) >= 2 and counts[-1] >= counts[0]"))),
    ("baseline 'rises' ignores a dip", mod(
        ("             and all(counts[i] <= counts[i + 1] for i in range(len(counts) - 1)))\n",
         "             and True)\n"))),
    ("baseline never certifies a rise", mod(
        ("    if rises:\n", "    if False:\n"))),
    # Report.
    ("report counts answers as abstentions", mod(
        ("(k, n - len(a), n)", "(k, len(a), n)"))),
    ("report swaps added and removed", mod(
        ("response.append((lo[0], hi[0], added, removed))",
         "response.append((lo[0], hi[0], removed, added))"))),
    ("answered set lists the abstained items", mod(
        ("if run[it] == ANSWER)", "if run[it] == ABSTAIN)"))),
    # Validation and snapshot.
    ("float subclass accepted as p", mod(
        ("    return type(v) is float and 0.0 < v < 1.0\n",
         "    return isinstance(v, float) and 0.0 < v < 1.0\n"))),
    ("p == 1 accepted", mod(
        ("    return type(v) is float and 0.0 < v < 1.0\n",
         "    return type(v) is float and 0.0 < v <= 1.0\n"))),
    ("str subclass accepted as a decision", mod(
        ("    return type(v) is str and v in DECISIONS\n",
         "    return isinstance(v, str) and v in DECISIONS\n"))),
    ("key types not checked", mod(
        ("        if type(k) is not str:\n            raise _Bad(detail)\n",
         "        if False:\n            raise _Bad(detail)\n"))),
    ("unknown threshold key ignored", mod(
        ("        if key not in T_KEYS:\n            raise _Bad(\"runs_threshold_unknown\")\n",
         "        if False:\n            raise _Bad(\"runs_threshold_unknown\")\n"))),
    ("duplicate items accepted", mod(
        ("    if len(set(items)) != len(items):\n", "    if False:\n"))),
    ("snapshot shares the caller's run dicts", mod(
        ("        got[key] = _item_map(run, items, \"run\", _is_decision)\n",
         "        got[key] = run if _item_map(run, items, \"run\", _is_decision) else run\n"))),
    ("snapshot shares the caller's beliefs", mod(
        ("        beliefs = _item_map(beliefs, items, \"beliefs\", _is_p)\n",
         "        beliefs = beliefs if _item_map(beliefs, items, \"beliefs\", _is_p) else beliefs\n"))),
    ("internal errors escape evaluate()", mod(
        ("    try:\n        return _run(snap)\n    except Exception:\n        return _error(\"internal_error\")\n",
         "    return _run(snap)\n"))),
    # Totals.
    ("totals count rejections as certified", mod(
        ("ok[c][\"baseline\"][\"decision\"] == CERTIFY]", "ok[c][\"baseline\"][\"decision\"] == REJECT]"))),
    ("totals never count a false alarm", mod(
        ("ok[c][\"decision\"] != PASS]", "False]"))),
    # Oracle.
    ("oracle: tie answers", orc(
        ("\"abstain\" if p_of[it] <= rows[idx][1] else \"answer\"",
         "\"abstain\" if p_of[it] < rows[idx][1] else \"answer\""))),
    ("oracle: nestedness reversed", orc(
        ("if s[lo] == \"0\" and s[hi] == \"1\":", "if s[lo] == \"1\" and s[hi] == \"0\":"))),
    ("oracle: high rate on the largest count", orc(
        ("if min(counts) * 5 >= 4 * n:", "if max(counts) * 5 >= 4 * n:"))),
    ("oracle: COMPLIANT with a run missing", orc(
        ("        elif len(absent) > 0:\n", "        elif False:\n"))),
    ("oracle: thresholds out of order", orc(
        ("_TABLE = [[\"0.5\", 0.5], [\"0.75\", 0.75], [\"0.9\", 0.9]]",
         "_TABLE = [[\"0.5\", 0.5], [\"0.9\", 0.9], [\"0.75\", 0.75]]"))),
    ("oracle: refuted ignores INCONSISTENT", orc(
        ("\"refuted\" if (bf == \"INCONSISTENT\" or kp == \"NONCOMPLIANT\") else",
         "\"refuted\" if kp == \"NONCOMPLIANT\" else"))),
    ("oracle: response swaps added and removed", orc(
        ("tuple(x for x in b if x not in a), tuple(x for x in a if x not in b)",
         "tuple(x for x in a if x not in b), tuple(x for x in b if x not in a)"))),
    ("oracle: rise ignores a dip", orc(
        ("        if counts[j] < counts[j - 1]:\n", "        if False:\n"))),
]


def _w():
    return dict((k, copy.deepcopy(v)) for k, v in WORLD_ORIG.items())


def _set(**kw):
    for k, v in kw.items():
        setattr(fixtures, k, v)


def _rebuild():
    fixtures.CASES = fixtures._build()


def _p(table, item, p):
    return [(it, p if it == item else q) for it, q in table]


def w_tie_moved_off_threshold():
    _set(P_A=_p(WORLD_ORIG["P_A"], "a05", 0.51))
    _rebuild()


def w_gap_fixture_gets_a_band_item():
    _set(P_B=_p(WORLD_ORIG["P_B"], "b05", 0.85))
    _rebuild()


def w_fixture_below_thirty_items():
    _set(P_A=copy.deepcopy(WORLD_ORIG["P_A"][:29]))
    _rebuild()


def w_format_only_follows_threshold():
    _set(_format_only=fixtures._compliant)
    _rebuild()


def w_inverted_made_compliant():
    _set(_FLIP={0.5: 0.5, 0.75: 0.75, 0.9: 0.9})
    _rebuild()


def w_constant_set_at_lowest_threshold():
    _set(_constant_set=lambda it, p, t, r: p > 0.5)
    _rebuild()


def w_rate_matched_uses_right_items():
    _set(_rate_matched=fixtures._compliant)
    _rebuild()


def w_non_nested_made_nested():
    _set(_non_nested=fixtures._compliant)
    _rebuild()


def w_missing_run_restored():
    full = fixtures._decide(fixtures.P_A, fixtures._compliant)
    for c in fixtures.CASES:
        if c["case_id"] == "U2-missing-run":
            c["runs"] = full


def w_label_flipped():
    lab = dict(WORLD_ORIG["LABELS"])
    lab["F4-rate-matched"] = ("PASS", None, "NOT_REFUTED", "COMPLIANT", "CERTIFY")
    _set(LABELS=lab)


def w_planted_entry_dropped():
    _set(PLANTED=WORLD_ORIG["PLANTED"][1:])


def w_control_dropped():
    _set(CONTROLS=WORLD_ORIG["CONTROLS"][:1])


def w_cases_shared():
    shared = dict((c["case_id"], c) for c in fixtures.CASES)
    fixtures.cases = lambda: shared


WORLD_MUTANTS = [
    ("tie item moved off its threshold", w_tie_moved_off_threshold),
    ("gap fixture gets a p in (0.75, 0.9]", w_gap_fixture_gets_a_band_item),
    ("fixture A shrunk below 30 items", w_fixture_below_thirty_items),
    ("format-only policy follows the threshold", w_format_only_follows_threshold),
    ("inverted policy made compliant", w_inverted_made_compliant),
    ("constant set taken at the lowest threshold", w_constant_set_at_lowest_threshold),
    ("rate-matched policy answers the right items", w_rate_matched_uses_right_items),
    ("non-nested item made nested", w_non_nested_made_nested),
    ("missing-run case given every run", w_missing_run_restored),
    ("hand label flipped to PASS", w_label_flipped),
    ("planted entry dropped", w_planted_entry_dropped),
    ("control dropped", w_control_dropped),
    ("cases() returns shared state", w_cases_shared),
]


def h_scan_whole_day_readme():
    test_threshold_compliance.scan_text = lambda name, text: text


def h_own_rows_every_line():
    test_threshold_compliance.own_rows = lambda text: text.splitlines()


def h_own_rows_nothing():
    test_threshold_compliance.own_rows = lambda text: []


def h_hygiene_ignores_banned_words():
    real = test_threshold_compliance.hygiene_hits
    test_threshold_compliance.hygiene_hits = lambda text: real(text) - {"banned_word"}


HARNESS_MUTANTS = [
    ("hygiene scans read the whole day README", h_scan_whole_day_readme),
    ("own-row filter returns every line", h_own_rows_every_line),
    ("own-row filter returns nothing", h_own_rows_nothing),
    ("hygiene helper ignores banned words", h_hygiene_ignores_banned_words),
]

MUTANTS = ([("code", n, a) for n, a in CODE_MUTANTS]
           + [("world", n, a) for n, a in WORLD_MUTANTS]
           + [("harness", n, a) for n, a in HARNESS_MUTANTS])


def restore():
    for k, m in MODULES.items():
        for name in [n for n in vars(m) if n not in SNAPSHOTS[k]]:
            delattr(m, name)
        m.__dict__.update(SNAPSHOTS[k])
    for name in [n for n in vars(fixtures) if n not in FIX_SNAPSHOT]:
        delattr(fixtures, name)
    fixtures.__dict__.update(FIX_SNAPSHOT)
    _set(**_w())
    test_threshold_compliance.__dict__.update(TEST_SNAPSHOT)


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_threshold_compliance)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


def main():
    restore()
    ran, bad = run_suite()
    print("clean suite: %d tests, %d failing" % (ran, bad))
    clean_ok = bad == 0
    killed = {"code": 0, "world": 0, "harness": 0}
    for kind, name, apply in MUTANTS:
        try:
            apply()
            ran, bad = run_suite()
        except Exception as exc:
            restore()
            print("%-7s %-58s BROKEN   (%s)" % (kind, name, type(exc).__name__))
            continue
        finally:
            restore()
        status = "KILLED" if bad else "SURVIVED"
        killed[kind] += 1 if bad else 0
        print("%-7s %-58s %-8s (%d/%d tests failing)" % (kind, name, status, bad, ran))
    ran, bad = run_suite()
    print("clean suite after restore: %d tests, %d failing" % (ran, bad))
    clean_ok = clean_ok and bad == 0
    n_code, n_world, n_harness = len(CODE_MUTANTS), len(WORLD_MUTANTS), len(HARNESS_MUTANTS)
    total = killed["code"] + killed["world"] + killed["harness"]
    print("killed %d/%d (code %d/%d, world %d/%d, harness %d/%d)"
          % (total, n_code + n_world + n_harness, killed["code"], n_code,
             killed["world"], n_world, killed["harness"], n_harness))
    ok = clean_ok and total == n_code + n_world + n_harness
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
