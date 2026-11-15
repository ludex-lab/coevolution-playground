"""Mutant runner: each mutant patches the code, the fixture world or the test
harness, then the unittest suite runs. A mutant is killed when at least one
test fails.

Code mutants replace one exact snippet of scrutiny_not_authority.py or
oracle.py (each snippet must occur exactly once) and re-execute the patched
source in memory inside that module. World mutants change the fixtures in
memory. Harness mutants replace one helper of the test module in memory
(the row-scoped hygiene scan). Nothing is written to disk.

Run: python3 -B mutants.py
Exit code 0 only when every mutant is killed and the clean suite passes.
"""

import copy
import io
import os
import sys
import unittest

import scrutiny_not_authority
import fixtures
import oracle
import test_scrutiny_not_authority

MODULES = {"scrutiny_not_authority": scrutiny_not_authority, "oracle": oracle}
SNAPSHOTS = {k: dict(vars(m)) for k, m in MODULES.items()}
FIX_SNAPSHOT = dict(vars(fixtures))
TEST_SNAPSHOT = dict(vars(test_scrutiny_not_authority))
WORLD = ("CASES", "LABELS", "REQUESTS", "NOISY_RATING")
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
    return code("scrutiny_not_authority", *pairs)


def orc(*pairs):
    return code("oracle", *pairs)


CODE_MUTANTS = [
    # Doctrine: the rating has no authority to eliminate.
    ("rule arm eliminates on a defective rating (auto-elimination)", mod(
        ("    if gate_decision == PERMIT:\n", "    if gate_decision == PERMIT or flagged:\n"))),
    ("missing check after a flag retains unflagged", mod(
        ("    elif flagged:\n        decision = HOLD\n",
         "    elif flagged:\n        decision = RETAIN\n"))),
    ("missing check after a flag drops implicitly", mod(
        ("    elif flagged:\n        decision = HOLD\n",
         "    elif flagged:\n        decision = ELIMINATE\n"))),
    ("defective rating raises no flag", mod(
        ("    flagged = snap[\"self_assessment\"] == DEFECTIVE\n",
         "    flagged = False\n"))),
    ("supported flagged conclusion held instead of retained", mod(
        ("    elif out == SUPPORTED:\n        decision = RETAIN\n",
         "    elif out == SUPPORTED:\n        decision = HOLD\n"))),
    ("supported flagged conclusion eliminated", mod(
        ("    elif out == SUPPORTED:\n        decision = RETAIN\n",
         "    elif out == SUPPORTED:\n        decision = ELIMINATE if flagged else RETAIN\n"))),
    ("rule conflict eliminates", mod(
        ("    elif out == CONFLICT:\n        decision = HOLD\n",
         "    elif out == CONFLICT:\n        decision = ELIMINATE\n"))),
    ("rule reads the conclusion text", mod(
        ("    flagged = snap[\"self_assessment\"] == DEFECTIVE\n",
         "    flagged = snap[\"self_assessment\"] == DEFECTIVE or "
         "\"wrong\" in snap[\"conclusion\"].lower()\n"))),
    # Independence.
    ("self check counts as independent", mod(
        ("    return check[\"source\"] != SELF and check[\"basis\"] == OWN_EVIDENCE\n",
         "    return check[\"basis\"] == OWN_EVIDENCE\n"))),
    ("check based on the self-assessment counts as independent", mod(
        ("    return check[\"source\"] != SELF and check[\"basis\"] == OWN_EVIDENCE\n",
         "    return check[\"source\"] != SELF\n"))),
    ("unrun check counts as a refutation", mod(
        ("        elif k[\"verdict\"] == SUPPORTS:\n            supported = True\n",
         "        elif k[\"verdict\"] == SUPPORTS:\n            supported = True\n"
         "        elif k[\"verdict\"] == NOT_RUN:\n            refuted = True\n"))),
    ("unrun check counts as support", mod(
        ("        elif k[\"verdict\"] == SUPPORTS:\n            supported = True\n",
         "        else:\n            supported = True\n"))),
    ("conflict resolves to refuted", mod(
        ("    if refuted and supported:\n        return CONFLICT\n",
         "    if refuted and supported:\n        return REFUTED\n"))),
    ("conflict resolves to supported", mod(
        ("    if refuted and supported:\n        return CONFLICT\n",
         "    if refuted and supported:\n        return SUPPORTED\n"))),
    ("outcome reads only the first check", mod(
        ("    for k in checks:\n        if not independent(k):\n",
         "    for k in checks[:1]:\n        if not independent(k):\n"))),
    ("a later refutation erases earlier support", mod(
        ("        if k[\"verdict\"] == REFUTES:\n            refuted = True\n",
         "        if k[\"verdict\"] == REFUTES:\n            refuted = True\n"
         "            supported = False\n"))),
    # The elimination gate.
    ("gate ignores a conflict (cherry-pick permitted)", mod(
        ("    if outcome(snap[\"checks\"]) == CONFLICT:\n        return REFUSE, ()\n", ""))),
    ("gate permits on the self-assessment cite", mod(
        ("    if basis:\n        return PERMIT, basis\n",
         "    if basis or CITE_SELF in cited:\n        return PERMIT, basis\n"))),
    ("gate ignores which checks were cited", mod(
        ("if k[\"check_id\"] in cited and independent(k)", "if independent(k)"))),
    ("gate permits on a supporting check", mod(
        ("and independent(k) and k[\"verdict\"] == REFUTES)",
         "and independent(k) and k[\"verdict\"] != NOT_RUN)"))),
    ("gate basis lists every cited id", mod(
        ("        return PERMIT, basis\n", "        return PERMIT, tuple(sorted(cited))\n"))),
    # Baseline and forced-agreement arms.
    ("baseline does not obey the rating", mod(
        ("    if snap[\"self_assessment\"] == DEFECTIVE:\n        return {\"decision\": ELIMINATE}\n",
         ""))),
    ("agree_flip holds instead of negating", mod(
        ("        return {\"decision\": NEGATE}\n", "        return {\"decision\": HOLD}\n"))),
    ("agree_silence obeys the rating", mod(
        ("(treated as ok).\"\"\"\n    return {\"decision\": _ok_path(outcome(snap[\"checks\"]))}\n",
         "(treated as ok).\"\"\"\n    return baseline(snap)\n"))),
    ("ok path retains a conflict", mod(
        ("    if out == CONFLICT:\n        return HOLD\n",
         "    if out == CONFLICT:\n        return RETAIN\n"))),
    ("ok path retains a refuted conclusion", mod(
        ("    if out == REFUTED:\n        return ELIMINATE\n",
         "    if out == REFUTED:\n        return RETAIN\n"))),
    # F1: keys, exact types, snapshot, guards.
    ("key check after lookup", mod(
        ("    keys = tuple(d)\n    for k in keys:\n",
         "    early = [d.get(f) for f in fields]\n    keys = tuple(d)\n    for k in keys:\n"))),
    ("key type check skipped", mod(
        ("        if type(k) is not str:\n            raise _Bad(keyerr)\n", "        pass\n"))),
    ("exact field set not enforced", mod(
        ("    if sorted(keys) != sorted(fields):\n",
         "    if not set(fields) <= set(keys):\n"))),
    ("str subclass accepted for enum values", mod(
        ("    if type(v) is not str or v not in choices:\n",
         "    if not isinstance(v, str) or v not in choices:\n"))),
    ("dict subclass accepted", mod(
        ("    if type(d) is not dict:\n        raise _Bad(shape)\n",
         "    if not isinstance(d, dict):\n        raise _Bad(shape)\n"))),
    ("list subclass accepted for checks", mod(
        ("    if type(raw_checks) is not list:\n", "    if not isinstance(raw_checks, list):\n"))),
    ("str subclass accepted for ids", mod(
        ("    return type(v) is str and v != \"\" and v == v.strip()\n",
         "    return isinstance(v, str) and v != \"\" and v == v.strip()\n"))),
    ("blank conclusion accepted", mod(
        ("conclusion.strip() == \"\"", "conclusion == \"\""))),
    ("duplicate check ids accepted", mod(
        ("cid == CITE_SELF or cid in seen:", "cid == CITE_SELF:"))),
    ("check id equal to the self-assessment cite accepted", mod(
        ("cid == CITE_SELF or cid in seen:", "cid in seen:"))),
    ("snapshot reuses the caller's check dicts", mod(
        ("        checks.append({\"check_id\": cid,\n",
         "        checks.append(raw)\n        _unused = ({\"check_id\": cid,\n"))),
    ("snapshot reuses the caller's check list", mod(
        ("\"self_assessment\": assessment, \"checks\": tuple(checks)}",
         "\"self_assessment\": assessment, \"checks\": raw_checks}"))),
    ("arms read the caller's case", mod(
        ("        return _run(snap)\n",
         "        return _run(dict(snap, checks=tuple(case[\"checks\"])))\n"))),
    ("internal error raised by evaluate", mod(
        ("        return _run(snap)\n    except Exception:\n        return _cfg(\"internal_error\")\n",
         "        return _run(snap)\n    finally:\n        pass\n"))),
    ("internal error raised by the gate", mod(
        ("        return {\"status\": OK, \"detail\": OK, \"decision\": decision, \"basis\": basis}\n"
         "    except Exception:\n",
         "        return {\"status\": OK, \"detail\": OK, \"decision\": decision, \"basis\": basis}\n"
         "    except ZeroDivisionError:\n"))),
    ("cite subclass or spoof accepted", mod(
        ("        if type(c) is not str or c not in ids or c in cited:\n",
         "        if c not in ids or c in cited:\n"))),
    ("empty cite accepted", mod(
        ("    if type(cite) is not list or not cite:\n", "    if type(cite) is not list:\n"))),
    # Scoring.
    ("coherence counts every case", mod(
        ("            if d in (ELIMINATE, NEGATE) or _final_assessment(arm, rec) == ASSESS_OK:\n",
         "            if True:\n"))),
    ("silence arm scored with the original rating", mod(
        ("    if arm == \"agree_silence\":\n        return ASSESS_OK\n",
         "    if False:\n        return ASSESS_OK\n"))),
    ("unbacked eliminations ignore backing", mod(
        ("                if not backed:\n", "                if True:\n"))),
    ("HOLD counted as unflagged retention", mod(
        ("                if d == RETAIN:\n                    s[\"unsound_retained_unflagged\"]",
         "                if d in (RETAIN, HOLD):\n                    s[\"unsound_retained_unflagged\"]"))),
    ("negated sound conclusion not counted as false", mod(
        ("                    s[\"sound_negated\"] += 1\n                    s[\"false_held_unflagged\"] += 1\n",
         "                    s[\"sound_negated\"] += 1\n"))),
    ("config_error records scored", mod(
        ("            out[\"config_error\"] += 1\n            continue\n",
         "            out[\"config_error\"] += 1\n"))),
    ("record key check skipped", mod(
        ("        if type(k) is not str:\n            raise _Bad(\"record_key_invalid\")\n    if \"status\"",
         "        pass\n    if \"status\""))),
    ("gold key check skipped", mod(
        ("        if type(k) is not str:\n            raise _Bad(\"gold_key_invalid\")\n",
         "        pass\n"))),
    ("paper results claimed as measured", mod(
        ("    return ON_UNMEASURED\n", "    return \"measured\"\n"))),
    # Oracle.
    ("oracle: defective with no check eliminates", orc(
        ("(\"defective\", \"none\"): \"HOLD\"", "(\"defective\", \"none\"): \"ELIMINATE\""))),
    ("oracle: independence ignores the basis", orc(
        ("if src == \"self\" or basis != \"own_evidence\" or verdict == \"not_run\":",
         "if src == \"self\" or verdict == \"not_run\":"))),
    ("oracle: gate ignores a conflict", orc(
        ("    if whole == \"conflict\":\n        return \"REFUSE\"\n", ""))),
    ("oracle: flip retains a supported conclusion", orc(
        ("(\"defective\", \"supported\"): \"NEGATE\"", "(\"defective\", \"supported\"): \"RETAIN\""))),
    ("oracle: basis includes self checks", orc(
        ("if c[\"source\"] != \"self\" and c[\"basis\"] == \"own_evidence\" \\",
         "if c[\"basis\"] == \"own_evidence\" \\"))),
]


def _w():
    return copy.deepcopy(WORLD_ORIG)


def _set(**kw):
    for k, v in kw.items():
        setattr(fixtures, k, v)


def w_noisy_case_gold_flipped():
    w = _w()
    lab = list(w["LABELS"]["def-sound-cleared"])
    lab[0] = "unsound"
    w["LABELS"]["def-sound-cleared"] = tuple(lab)
    _set(LABELS=w["LABELS"])


def w_laundered_made_own_evidence():
    w = _w()
    w["CASES"]["def-sound-laundered"]["checks"][0]["basis"] = "own_evidence"
    _set(CASES=w["CASES"])


def w_not_run_made_refutes():
    w = _w()
    w["CASES"]["def-unsound-not-run"]["checks"][0]["verdict"] = "refutes"
    _set(CASES=w["CASES"])


def w_self_recheck_made_world_record():
    w = _w()
    w["CASES"]["def-sound-self-recheck"]["checks"][0]["source"] = "world_record"
    _set(CASES=w["CASES"])


def w_conflict_support_removed():
    w = _w()
    w["CASES"]["def-sound-conflict"]["checks"].pop(0)
    _set(CASES=w["CASES"])


def w_label_rule_decision_edited():
    w = _w()
    lab = list(w["LABELS"]["def-sound-unchecked"])
    lab[3] = "ELIMINATE"
    w["LABELS"]["def-sound-unchecked"] = tuple(lab)
    _set(LABELS=w["LABELS"])


def w_cherry_pick_expected_permit():
    w = _w()
    cn, cite, _ = w["REQUESTS"]["Q5-cherry-pick"]
    w["REQUESTS"]["Q5-cherry-pick"] = (cn, cite, "PERMIT")
    _set(REQUESTS=w["REQUESTS"])


def w_permit_request_cites_self_only():
    w = _w()
    cn, _, want = w["REQUESTS"]["Q7-independent-refutation"]
    w["REQUESTS"]["Q7-independent-refutation"] = (cn, ["self_assessment"], want)
    _set(REQUESTS=w["REQUESTS"])


def w_noisy_list_shortened():
    _set(NOISY_RATING=WORLD_ORIG["NOISY_RATING"][1:])


def w_case_removed():
    w = _w()
    w["CASES"].pop("def-unsound-unchecked")
    w["LABELS"].pop("def-unsound-unchecked")
    _set(CASES=w["CASES"], LABELS=w["LABELS"])


def w_missed_case_gold_made_sound():
    w = _w()
    lab = list(w["LABELS"]["ok-unsound-missed"])
    lab[0] = "sound"
    w["LABELS"]["ok-unsound-missed"] = tuple(lab)
    _set(LABELS=w["LABELS"])


def w_refutation_removed():
    w = _w()
    w["CASES"]["def-unsound-refuted"]["checks"].clear()
    _set(CASES=w["CASES"])


def w_cases_shared():
    fixtures.cases = lambda: fixtures.CASES


def w_requests_shared():
    fixtures.requests = lambda: fixtures.REQUESTS


WORLD_MUTANTS = [
    ("noisy-rating case gold flipped to unsound", w_noisy_case_gold_flipped),
    ("laundered check made own evidence", w_laundered_made_own_evidence),
    ("unrun check made a refutation", w_not_run_made_refutes),
    ("self re-check relabelled as a world record", w_self_recheck_made_world_record),
    ("conflict case loses its support", w_conflict_support_removed),
    ("hand label for a rule decision edited", w_label_rule_decision_edited),
    ("cherry-pick request expected to be permitted", w_cherry_pick_expected_permit),
    ("permitted request cites only the rating", w_permit_request_cites_self_only),
    ("noisy-rating list shortened", w_noisy_list_shortened),
    ("unchecked unsound case removed", w_case_removed),
    ("missed unsound case relabelled sound", w_missed_case_gold_made_sound),
    ("independent refutation removed", w_refutation_removed),
    ("cases() returns shared state", w_cases_shared),
    ("requests() returns shared state", w_requests_shared),
]


def h_scan_whole_day_readme():
    test_scrutiny_not_authority.scan_text = lambda name, text: text


def h_own_rows_every_line():
    test_scrutiny_not_authority.own_rows = lambda text: text.splitlines()


def h_own_rows_nothing():
    test_scrutiny_not_authority.own_rows = lambda text: []


def h_hygiene_ignores_banned_words():
    real = test_scrutiny_not_authority.hygiene_hits
    test_scrutiny_not_authority.hygiene_hits = lambda text: real(text) - {"banned_word"}


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
    fixtures.__dict__.update(FIX_SNAPSHOT)
    _set(**_w())
    test_scrutiny_not_authority.__dict__.update(TEST_SNAPSHOT)


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_scrutiny_not_authority)
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
            print("%-7s %-62s BROKEN   (%s)" % (kind, name, type(exc).__name__))
            continue
        finally:
            restore()
        status = "KILLED" if bad else "SURVIVED"
        killed[kind] += 1 if bad else 0
        print("%-7s %-62s %-8s (%d/%d tests failing)" % (kind, name, status, bad, ran))
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
