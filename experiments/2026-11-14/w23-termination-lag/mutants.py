"""Mutant runner: each mutant patches the code, the fixture world or the test
harness, then the unittest suite runs. A mutant is killed when at least one
test fails.

Code mutants replace one exact snippet of termination_lag.py or oracle.py
(each snippet must occur exactly once) and re-execute the patched source in
memory inside that module. World mutants change the fixtures in memory.
Harness mutants replace one helper of the test module in memory (the
row-scoped hygiene scan). Nothing is written to disk.

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
import termination_lag
import test_termination_lag

MODULES = {"termination_lag": termination_lag, "oracle": oracle}
SNAPSHOTS = {k: dict(vars(m)) for k, m in MODULES.items()}
FIX_SNAPSHOT = dict(vars(fixtures))
TEST_SNAPSHOT = dict(vars(test_termination_lag))
WORLD = ("EPISODES", "LABELS", "LONG_WAIT")
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
    return code("termination_lag", *pairs)


def orc(*pairs):
    return code("oracle", *pairs)


CODE_MUTANTS = [
    # The gate.
    ("gate never refuses", mod(
        ("        if solved and not ok:\n", "        if False:\n"))),
    ("protection expires after three steps (a wait becomes permission)", mod(
        ("        if solved and not ok:\n",
         "        if solved and not ok and i - protected_from <= 3:\n"))),
    ("gate refuses every edit after the first pass", mod(
        ("        if solved and not ok:\n", "        if solved:\n"))),
    ("gate refuses only a revert to the initial content", mod(
        ("        if solved and not ok:\n",
         "        if solved and not ok and snap[\"initial\"].get(name) == content:\n"))),
    ("gate refuses only edits to the last checked file", mod(
        ("        if solved and not ok:\n",
         "        if solved and not ok and name == checks[-1][0]:\n"))),
    ("gate applies a refused edit anyway", mod(
        ("            refused.append(i)\n            continue\n",
         "            refused.append(i)\n            state = candidate\n            continue\n"))),
    ("gate judges the state before the edit", mod(
        ("        ok = passes(checks, candidate)\n", "        ok = passes(checks, state)\n"))),
    ("gate never records the first pass", mod(
        ("            solved = True\n            protected_from = i\n",
         "            protected_from = i\n"))),
    ("gate records the last pass as protected_from", mod(
        ("        if ok and not solved:\n", "        if ok:\n"))),
    ("gate edits the shared state in place", mod(
        ("        candidate = dict(state)\n", "        candidate = state\n"))),
    ("gate verdict read from the raw run", mod(
        ("    return {\"verdict\": PASS if passes(checks, state) else FAIL,\n"
         "            \"protected_from\"",
         "    return {\"verdict\": baseline(snap)[\"verdict\"],\n"
         "            \"protected_from\""))),
    ("non-edit steps marked refused after the pass", mod(
        ("        if kind != EDIT:\n            decisions.append(PERMIT)\n",
         "        if kind != EDIT:\n            decisions.append(REFUSE if solved else PERMIT)\n"))),
    # First pass, lag, regressions.
    ("first_pass off by one", mod(("            return i\n", "            return i + 1\n"))),
    ("first_pass returns the last pass", mod(
        ("    for i, ok in enumerate(flags):\n        if ok:\n            return i\n",
         "    for i, ok in reversed(list(enumerate(flags))):\n        if ok:\n"
         "            return i\n"))),
    ("lag counts the first-pass step too", mod(
        ("    return len(flags) - 1 - fp\n", "    return len(flags) - fp\n"))),
    ("lag counts only edit steps", mod(
        ("    flags, _ = raw_run(snap)\n    rule = gate(snap)\n",
         "    flags, _ = raw_run(snap)\n"
         "    flags = tuple(f for f, s in zip(flags, snap[\"steps\"]) if s[0] == EDIT)\n"
         "    rule = gate(snap)\n"))),
    ("regressions include fail-to-fail steps after a pass", mod(
        ("        if prev and not ok:\n            out.append(i)\n        prev = ok\n",
         "        if prev and not ok:\n            out.append(i)\n        prev = prev or ok\n"))),
    ("regressions never reported", mod(
        ("            out.append(i)\n", "            pass\n"))),
    ("rule arm drops the compare-run regressions", mod(
        ("    rule[\"regressions\"] = regressions(flags)\n", "    rule[\"regressions\"] = ()\n"))),
    # The fixture test.
    ("checks pass when any checked file passes", mod(
        ("        if name not in state or state[name] not in accept:\n            return False\n"
         "    return True\n",
         "        if name in state and state[name] in accept:\n            return True\n"
         "    return False\n"))),
    ("only the first accepted content counts", mod(
        ("state[name] not in accept:", "state[name] != accept[0]:"))),
    # The baseline.
    ("baseline sees mid-run correctness", mod(
        ("    return {\"verdict\": PASS if passes(snap[\"checks\"], final) else FAIL}\n",
         "    return {\"verdict\": PASS if any(flags) else FAIL}\n"))),
    ("baseline judged on the gated state", mod(
        ("    return {\"verdict\": PASS if passes(snap[\"checks\"], final) else FAIL}\n",
         "    return {\"verdict\": gate(snap)[\"verdict\"]}\n"))),
    ("baseline reports regressions too", mod(
        ("    return {\"verdict\": PASS if passes(snap[\"checks\"], final) else FAIL}\n",
         "    return {\"verdict\": PASS if passes(snap[\"checks\"], final) else FAIL,"
         " \"regressions\": regressions(flags)}\n"))),
    # Stop at first pass.
    ("stop_first never stops", mod(
        ("        if passes(checks, state):\n            break\n",
         "        if False:\n            break\n"))),
    ("stop_first counts one step short", mod(
        ("    return {\"verdict\": PASS if passes(checks, state) else FAIL, \"steps_run\": run}\n",
         "    return {\"verdict\": PASS if passes(checks, state) else FAIL,"
         " \"steps_run\": run - 1}\n"))),
    # Validation and F1.
    ("initial passing state permitted", mod(
        ("        raise _Bad(\"initial_passes\")\n", "        pass\n"))),
    ("duplicate check file permitted", mod(
        ("        if not _id(name) or name in seen:\n", "        if not _id(name):\n"))),
    ("duplicate accepted content permitted", mod(
        ("            if type(a) is not str or a in acc:\n",
         "            if type(a) is not str:\n"))),
    ("empty steps permitted", mod(
        ("    if type(steps) is not list or not steps:\n", "    if type(steps) is not list:\n"))),
    ("non-edit step may carry extra fields", mod(
        ("            _fields(s, BARE_FIELDS, \"step_fields_invalid\")\n", "            pass\n"))),
    ("str subclass accepted for edit content", mod(
        ("            if not _id(name) or type(content) is not str:\n",
         "            if not _id(name) or not isinstance(content, str):\n"))),
    ("str subclass accepted for accepted contents", mod(
        ("            if type(a) is not str or a in acc:\n",
         "            if not isinstance(a, str) or a in acc:\n"))),
    ("dict subclass accepted for a step", mod(
        ("        if type(s) is not dict:\n            raise _Bad(\"step_invalid\")\n",
         "        if not isinstance(s, dict):\n            raise _Bad(\"step_invalid\")\n"))),
    ("list subclass accepted for steps", mod(
        ("    if type(steps) is not list or not steps:\n",
         "    if not isinstance(steps, list) or not steps:\n"))),
    ("key check removed (trajectory)", mod(
        ("    _keys(trajectory, \"trajectory_key_invalid\")\n", ""))),
    ("key check removed (initial)", mod(
        ("    _keys(initial, \"initial_key_invalid\")\n", ""))),
    ("key check removed (check)", mod(
        ("        _keys(c, \"check_key_invalid\")\n", ""))),
    ("key check removed (step)", mod(
        ("        _keys(s, \"step_key_invalid\")\n", ""))),
    ("key check after lookup (trajectory)", mod(
        ("    _keys(trajectory, \"trajectory_key_invalid\")\n"
         "    _fields(trajectory, TRAJECTORY_FIELDS, \"trajectory_fields_invalid\")\n",
         "    _fields(trajectory, TRAJECTORY_FIELDS, \"trajectory_fields_invalid\")\n"
         "    _keys(trajectory, \"trajectory_key_invalid\")\n"))),
    ("key check after lookup (step)", mod(
        ("        _keys(s, \"step_key_invalid\")\n        if \"kind\" not in s:\n"
         "            raise _Bad(\"step_fields_invalid\")\n",
         "        if \"kind\" not in s:\n            raise _Bad(\"step_fields_invalid\")\n"
         "        _keys(s, \"step_key_invalid\")\n"))),
    ("key check after lookup (check)", mod(
        ("        _keys(c, \"check_key_invalid\")\n"
         "        _fields(c, CHECK_FIELDS, \"check_fields_invalid\")\n",
         "        _fields(c, CHECK_FIELDS, \"check_fields_invalid\")\n"
         "        _keys(c, \"check_key_invalid\")\n"))),
    ("snapshot reuses the caller's initial dict", mod(
        ("    snap = {\"trajectory_id\": tid, \"initial\": init,",
         "    snap = {\"trajectory_id\": tid, \"initial\": initial,"))),
    ("snapshot reuses the caller's steps list", mod(
        ("\"steps\": tuple(st)}\n", "\"steps\": steps}\n"))),
    ("snapshot reuses the caller's accept list", mod(
        ("        chk.append((name, tuple(acc)))\n", "        chk.append((name, accept))\n"))),
    ("run guard removed", mod(
        ("    try:\n        return _run(snap)\n    except Exception:\n"
         "        return _config(\"internal_error\")\n",
         "    return _run(snap)\n"))),
    # Oracle mutants.
    ("oracle: gate never refuses", orc(
        ("        if locked is not None and not good:\n", "        if False:\n"))),
    ("oracle: regressions include fail-to-fail", orc(
        ("if passing[k - 1] and not passing[k])",
         "if any(passing[:k]) and not passing[k])"))),
    ("oracle: lag off by one", orc(
        ("    lag = None if fp is None else n - fp - 1\n",
         "    lag = None if fp is None else n - fp\n"))),
    ("oracle: checks pass on any file", orc(
        ("    for c in trajectory[\"checks\"]:\n"
         "        if state.get(c[\"file\"], None) not in c[\"accept\"]:\n"
         "            return False\n    return True\n",
         "    for c in trajectory[\"checks\"]:\n"
         "        if state.get(c[\"file\"], None) in c[\"accept\"]:\n"
         "            return True\n    return False\n"))),
    ("oracle: stop runs every step", orc(
        ("        stop, ran = \"PASS\", fp + 1\n", "        stop, ran = \"PASS\", n\n"))),
    ("oracle: refused edit admitted", orc(
        ("            refused.append(i)\n            continue\n",
         "            refused.append(i)\n"))),
]


def _set(**kw):
    for k, v in kw.items():
        setattr(fixtures, k, v)


def _w():
    return copy.deepcopy(WORLD_ORIG)


def w_label_first_correct_flipped():
    w = _w()
    lab = list(w["LABELS"]["d-late-solve"])
    lab[0] = 4
    w["LABELS"]["d-late-solve"] = tuple(lab)
    _set(**w)


def w_planted_undo_removed():
    w = _w()
    w["EPISODES"]["d-undo-at-end"]["steps"][3]["content"] = fixtures.D_ALT
    _set(**w)


def w_refusal_label_emptied():
    w = _w()
    lab = list(w["LABELS"]["d-undo-then-wrong-again"])
    lab[4] = (1,)
    w["LABELS"]["d-undo-then-wrong-again"] = tuple(lab)
    _set(**w)


def w_long_wait_dropped():
    w = _w()
    del w["EPISODES"][fixtures.LONG_WAIT]
    del w["LABELS"][fixtures.LONG_WAIT]
    _set(**w)


def w_alt_becomes_bad():
    w = _w()
    w["EPISODES"]["d-alt-correct"]["steps"][2]["content"] = fixtures.D_BAD2
    _set(**w)


def w_refix_removed():
    w = _w()
    w["EPISODES"]["d-undo-then-refix"]["steps"][3]["content"] = fixtures.D_BAD2
    _set(**w)


def w_baseline_label_flipped():
    w = _w()
    lab = list(w["LABELS"]["d-undo-at-end"])
    lab[3] = fixtures.P
    w["LABELS"]["d-undo-at-end"] = tuple(lab)
    _set(**w)


def w_lag_label_off():
    w = _w()
    lab = list(w["LABELS"]["c-full-then-undo-one"])
    lab[1] = 3
    w["LABELS"]["c-full-then-undo-one"] = tuple(lab)
    _set(**w)


def w_churn_solved_early():
    w = _w()
    w["EPISODES"]["c-churn-before-solve"]["steps"][0] = {
        "kind": "edit", "file": fixtures.C_CONFIG, "content": fixtures.C_CONFIG_FIX}
    _set(**w)


def w_episodes_shared():
    shared = copy.deepcopy(WORLD_ORIG["EPISODES"])
    fixtures.episodes = lambda: shared


WORLD_MUTANTS = [
    ("gold first-correct label moved", w_label_first_correct_flipped),
    ("planted undo replaced by a correct edit", w_planted_undo_removed),
    ("gold refusal label shortened", w_refusal_label_emptied),
    ("long-wait trajectory dropped", w_long_wait_dropped),
    ("alternative correct patch made wrong", w_alt_becomes_bad),
    ("re-fix after the undo removed", w_refix_removed),
    ("gold baseline label flipped", w_baseline_label_flipped),
    ("gold lag label off by one", w_lag_label_off),
    ("churn trajectory solved early", w_churn_solved_early),
    ("episodes() returns shared state", w_episodes_shared),
]


def h_scan_whole_day_readme():
    test_termination_lag.scan_text = lambda name, text: text


def h_own_rows_every_line():
    test_termination_lag.own_rows = lambda text: text.splitlines()


def h_own_rows_nothing():
    test_termination_lag.own_rows = lambda text: []


def h_hygiene_ignores_banned_words():
    real = test_termination_lag.hygiene_hits
    test_termination_lag.hygiene_hits = lambda text: real(text) - {"banned_word"}


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
    test_termination_lag.__dict__.update(TEST_SNAPSHOT)


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_termination_lag)
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
            print("%-7s %-66s BROKEN   (%s)" % (kind, name, type(exc).__name__))
            continue
        finally:
            restore()
        status = "KILLED" if bad else "SURVIVED"
        killed[kind] += 1 if bad else 0
        print("%-7s %-66s %-8s (%d/%d tests failing)" % (kind, name, status, bad, ran))
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
