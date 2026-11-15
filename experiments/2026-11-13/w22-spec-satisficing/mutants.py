"""Mutant runner: each mutant patches the code or the fixture world, then the
unittest suite runs. A mutant is killed when at least one test fails.

Code mutants replace one exact snippet of spec_satisficing.py or oracle.py
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
import spec_satisficing
import test_spec_satisficing

MODULES = {"spec_satisficing": spec_satisficing, "oracle": oracle}
SNAPSHOTS = {k: dict(vars(m)) for k, m in MODULES.items()}
FIX_SNAPSHOT = dict(vars(fixtures))
TEST_SNAPSHOT = dict(vars(test_spec_satisficing))
TASKS_ORIG = copy.deepcopy(fixtures.TASKS)
EPISODES_ORIG = copy.deepcopy(fixtures.EPISODES)
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
    return code("spec_satisficing", *pairs)


def orc(*pairs):
    return code("oracle", *pairs)


CODE_MUTANTS = [
    # The three VERDICT done-when mutants.
    ("honor 'acceptable' at the commit gate", mod(
        ("    if not ok:\n", "    if not ok and not acc:\n"))),
    ("permit unreported commit", mod(
        ("    if cid not in reported:\n", "    if False:\n"))),
    ("skip re-check after self-correction (self-correction counts as a pass)", mod(
        ("            passed.clear()\n",
         "            passed.clear()\n            passed[cid] = (True, ())\n"))),
    # Further mutants of the same rules.
    ("honor 'acceptable' at check time", mod(
        ("            passed[cid] = check(choices[cid], requirements)\n",
         "            passed[cid] = (True, ()) if claimed.get(cid) else check(choices[cid], requirements)\n"))),
    ("self-correction does not void earlier checks", mod(
        ("            passed.clear()\n", "            pass\n"))),
    ("self-correction voids only its named choice", mod(
        ("            passed.clear()\n", "            passed.pop(cid, None)\n"))),
    ("self-correction is not a report", mod(
        ("        elif kind == SELF_CORRECT:\n            reported.add(cid)\n",
         "        elif kind == SELF_CORRECT:\n"))),
    ("new report does not void its check", mod(
        ("            passed.pop(cid, None)\n", "            pass\n"))),
    ("commit without a check", mod(
        ("    if cid not in passed:\n        return", "    if False:\n        return"))),
    ("check ignores the last requirement", mod(
        ("    for req in requirements:\n", "    for req in requirements[:-1]:\n"))),
    ("check passes on any met requirement", mod(
        ("    return (len(dropped) == 0, tuple(dropped))\n",
         "    return (len(dropped) < len(requirements), tuple(dropped))\n"))),
    ("acceptable verdict not recorded", mod(
        ("    acc = claimed.get(cid, False)\n", "    acc = False\n"))),
    ("missing reason admitted", mod(
        ("            if not _is_str(reason) or reason.strip() == \"\":\n", "            if False:\n"))),
    ("non-bool acceptable admitted", mod(
        ("            if type(acc) is not bool:\n", "            if False:\n"))),
    ("label may name unknown requirements", mod(
        ("            if not _is_str(r) or r not in reqs:\n", "            if not _is_str(r):\n"))),
    ("events after the commit admitted", mod(
        ("        if kind == COMMIT_EVENT and i != len(items) - 1:\n", "        if False:\n"))),
    # r2 F1: exact-str keys before any lookup, and a snapshot-only gate.
    ("non-str keys admitted everywhere", mod(
        ("        if type(k) is not str:\n            raise _Bad(detail)\n",
         "        if False:\n            raise _Bad(detail)\n"))),
    ("task keys not checked", mod(
        ("    _keys(task, \"task_key_invalid\")\n", ""))),
    ("choice ids not checked", mod(
        ("    for cid in choices:\n        if not _is_str(cid):\n            raise _Bad(\"choice_id_invalid\")\n", ""))),
    ("choice entry keys not checked", mod(
        ("        _keys(entry, \"choice_entry_key_invalid\")\n", ""))),
    ("event keys not checked", mod(
        ("        _keys(ev, \"event_key_invalid\")\n", ""))),
    ("event keys checked only after the kind lookup", mod(
        ("        _keys(ev, \"event_key_invalid\")\n        kind = ev.get(\"kind\")\n",
         "        kind = ev.get(\"kind\")\n        _keys(ev, \"event_key_invalid\")\n"))),
    ("snapshot reuses the caller's event dicts", mod(
        ("        events.append({\"kind\": kind, \"choice\": cid, \"acceptable\": acc})\n",
         "        events.append(ev)\n"))),
    ("snapshot reuses the caller's choice entries", mod(
        ("        snap_choices[cid] = {\"meets\": meets}\n", "        snap_choices[cid] = entry\n"))),
    ("snapshot reuses the caller's requirement list", mod(
        ("    return {\"task_id\": task_id, \"requirements\": reqs,\n",
         "    return {\"task_id\": task_id, \"requirements\": task[\"requirements\"],\n"))),
    ("gate re-reads the caller's trace", mod(
        ("        return _run(snap)\n",
         "        return _run(dict(snap, events=tuple(trace)))\n"))),
    # r2 F3: exact value types (the verifier's non-equivalent survivors).
    ("str subclasses admitted as ids and reasons", mod(
        ("    return type(v) is str and v != \"\"\n", "    return isinstance(v, str) and v != \"\"\n"))),
    ("event choice may be a str subclass", mod(
        ("        if type(cid) is not str or cid not in snap_choices:\n",
         "        if not isinstance(cid, str) or cid not in snap_choices:\n"))),
    ("event kind type not checked", mod(
        ("        if type(kind) is not str or kind not in KINDS:\n", "        if kind not in KINDS:\n"))),
    ("duplicate requirements admitted", mod(
        ("    if len(set(reqs)) != len(reqs):\n        raise _Bad(\"requirements_duplicate\")\n", ""))),
    ("trace may be a tuple", mod(
        ("    if type(trace) is not list or not trace:\n",
         "    if type(trace) not in (list, tuple) or not trace:\n"))),
    ("choice entry may be a dict subclass", mod(
        ("        if type(entry) is not dict:\n", "        if not isinstance(entry, dict):\n"))),
    ("meets may be a tuple", mod(
        ("        if type(meets) is not list:\n", "        if type(meets) not in (list, tuple):\n"))),
    ("gate exceptions propagate", mod(
        ("        return _run(snap)\n    except Exception:\n        return _config(\"internal_error\")\n",
         "        return _run(snap)\n    finally:\n        pass\n"))),
    # r2 F5: whitespace-only reason.
    ("whitespace-only reason admitted", mod(
        ("            if not _is_str(reason) or reason.strip() == \"\":\n",
         "            if not _is_str(reason):\n"))),
    ("paper numbers reported as measured", mod(
        ("    return ON_UNMEASURED\n", "    return \"measured\"\n"))),
    # Oracle mutants (the oracle must stay a real reference).
    ("oracle: honors 'acceptable'", orc(
        ("    elif missing:\n", "    elif missing and not claimed:\n"))),
    ("oracle: no report gate", orc(
        ("    if not names_c:\n        out.update", "    if False:\n        out.update"))),
    ("oracle: self-correction not a boundary", orc(
        ("        if e[\"kind\"] == \"self_correct\":\n            break\n", ""))),
    ("oracle: dropped order lost", orc(
        ("    dropped = tuple(sorted(missing, key=reqs.index))\n",
         "    dropped = tuple(sorted(missing))\n"))),
]


def _set(tasks=None, episodes=None):
    if tasks is not None:
        fixtures.TASKS = tasks
    if episodes is not None:
        fixtures.EPISODES = episodes


def _t():
    return copy.deepcopy(TASKS_ORIG)


def _e():
    return copy.deepcopy(EPISODES_ORIG)


def w_label_flipped():
    t = _t()
    t["csv-export"]["choices"]["buffer_dump"]["meets"].append("streams_rows")
    _set(tasks=t)


def w_requirement_added():
    t = _t()
    t["csv-export"]["requirements"].append("quotes_fields")
    _set(tasks=t)


def w_acceptable_removed():
    e = _e()
    for name in ("b_acceptable_flag", "b_acceptable_two_dropped"):
        for ev in e[name][1]:
            if "acceptable" in ev:
                ev["acceptable"] = False
                ev["reason"] = "simpler"
    _set(episodes=e)


def w_report_dropped_from_a():
    e = _e()
    e["a_report_check_commit"][1].pop(0)
    _set(episodes=e)


def w_check_dropped_from_a():
    e = _e()
    e["a_retry_full"][1].pop(1)
    _set(episodes=e)


def w_self_correction_dropped_from_d():
    e = _e()
    tr = e["d_self_correct_retains_no_recheck"][1]
    e["d_self_correct_retains_no_recheck"][1][:] = [x for x in tr if x["kind"] != "self_correct"]
    _set(episodes=e)


def w_recheck_added_to_d():
    e = _e()
    tr = e["d_self_correct_retains_retry"][1]
    tr.insert(len(tr) - 1, {"kind": "check", "choice": "fixed_sleep_retry"})
    _set(episodes=e)


def w_report_added_to_c():
    e = _e()
    tr = e["c_unreported_checked_dropping"][1]
    tr.insert(0, {"kind": "report", "choice": "buffer_dump", "reason": "r", "acceptable": True})
    _set(episodes=e)


def w_expected_edited():
    e = _e()
    tid, tr, _ = e["b_acceptable_flag"]
    e["b_acceptable_flag"] = (tid, tr, ("COMMIT", "all_requirements_met", (), True))
    _set(episodes=e)


def w_episodes_shared():
    fixtures.episodes = lambda: fixtures.EPISODES


def w_tasks_shared():
    fixtures.tasks = lambda: fixtures.TASKS


WORLD_MUTANTS = [
    ("fixture label: buffer_dump meets every requirement", w_label_flipped),
    ("requirement added to a task", w_requirement_added),
    ("'acceptable' removed from (b) episodes", w_acceptable_removed),
    ("report dropped from an (a) episode", w_report_dropped_from_a),
    ("check dropped from an (a) episode", w_check_dropped_from_a),
    ("self-correction dropped from a (d) episode", w_self_correction_dropped_from_d),
    ("re-check added to a (d) episode", w_recheck_added_to_d),
    ("report added to a (c) episode", w_report_added_to_c),
    ("expected row edited to COMMIT", w_expected_edited),
    ("episodes() returns shared state", w_episodes_shared),
    ("tasks() returns shared state", w_tasks_shared),
]

def h_scan_whole_day_readme():
    test_spec_satisficing.scan_text = lambda name, text: text


def h_own_rows_every_line():
    test_spec_satisficing.own_rows = lambda text: text.splitlines()


def h_own_rows_nothing():
    test_spec_satisficing.own_rows = lambda text: []


def h_hygiene_ignores_banned_words():
    real = test_spec_satisficing.hygiene_hits
    test_spec_satisficing.hygiene_hits = lambda text: real(text) - {"banned_word"}


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
    test_spec_satisficing.__dict__.update(TEST_SNAPSHOT)
    _set(tasks=copy.deepcopy(TASKS_ORIG), episodes=copy.deepcopy(EPISODES_ORIG))


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_spec_satisficing)
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
            print("%-5s %-72s BROKEN   (%s)" % (kind, name, type(exc).__name__))
            continue
        finally:
            restore()
        status = "KILLED" if bad else "SURVIVED"
        killed[kind] += 1 if bad else 0
        print("%-5s %-72s %-8s (%d/%d tests failing)" % (kind, name, status, bad, ran))
    ran, bad = run_suite()
    print("clean suite after restore: %d tests, %d failing" % (ran, bad))
    clean_ok = clean_ok and bad == 0
    n_code, n_world, n_harness = len(CODE_MUTANTS), len(WORLD_MUTANTS), len(HARNESS_MUTANTS)
    total = killed["code"] + killed["world"] + killed["harness"]
    print("killed %d/%d (code %d/%d, world %d/%d, harness %d/%d)" % (
        total, n_code + n_world + n_harness, killed["code"], n_code,
        killed["world"], n_world, killed["harness"], n_harness))
    return 0 if clean_ok and total == n_code + n_world + n_harness else 1


if __name__ == "__main__":
    sys.exit(main())
