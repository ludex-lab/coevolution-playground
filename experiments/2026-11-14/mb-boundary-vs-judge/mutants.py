"""Mutant runner: each mutant patches the code, the fixture world or the test
harness, then the unittest suite runs. A mutant is killed when at least one
test fails.

Code mutants replace one exact snippet of boundary_vs_judge.py or oracle.py
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

import boundary_vs_judge
import fixtures
import oracle
import test_boundary_vs_judge

MODULES = {"boundary_vs_judge": boundary_vs_judge, "oracle": oracle}
SNAPSHOTS = {k: dict(vars(m)) for k, m in MODULES.items()}
FIX_SNAPSHOT = dict(vars(fixtures))
TEST_SNAPSHOT = dict(vars(test_boundary_vs_judge))
WORLD = ("EPISODES", "LABELS", "PINNED_ARM_B", "GATE_CASES", "LOSSY_DROP",
         "SEED_SWEEP_RANGE")
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
    return code("boundary_vs_judge", *pairs)


def orc(*pairs):
    return code("oracle", *pairs)


CODE_MUTANTS = [
    # The named mutants.
    ("Arm A ignores forbidden writes", mod(
        ("            flags.append((i, FORBIDDEN))\n", "            pass\n"))),
    ("Arm A reads the final text (flags only on a failure-sounding text)", mod(
        ("            flags.append((i, FORBIDDEN))\n",
         "            if judge_base(snap[\"final_text\"]) == FAIL:\n"
         "                flags.append((i, FORBIDDEN))\n"))),
    ("Arm A reads the final text (a successful text passes)", mod(
        ("    return {\"verdict\": PASS if cls in PASSING else FAIL, \"class\": cls,\n",
         "    return {\"verdict\": PASS if cls in PASSING or judge_base(snap[\"final_text\"])"
         " == PASS else FAIL, \"class\": cls,\n"))),
    ("Arm B sees the writes (fails any flagged episode)", mod(
        ("\"arm_b\": {\"verdict\": judge(snap[\"final_text\"], seed), \"seed\": seed}}",
         "\"arm_b\": {\"verdict\": FAIL if boundary(snap)[\"flags\"] else "
         "judge(snap[\"final_text\"], seed), \"seed\": seed}}"))),
    ("Arm B sees the writes (write count mixed into its text)", mod(
        ("\"arm_b\": {\"verdict\": judge(snap[\"final_text\"], seed), \"seed\": seed}}",
         "\"arm_b\": {\"verdict\": judge(snap[\"final_text\"] + str(len(snap[\"writes\"])), "
         "seed), \"seed\": seed}}"))),
    ("drop the seed", mod(
        ("    rng = random.Random(\"%d|%s\" % (seed, final_text))\n",
         "    rng = random.Random(final_text)\n"))),
    ("global random state instead of a private Random", mod(
        ("    rng = random.Random(\"%d|%s\" % (seed, final_text))\n",
         "    random.seed(\"%d|%s\" % (seed, final_text))\n    rng = random\n"))),
    ("judge votes over three draws", mod(
        ("    if rng.randrange(NOISE_ONE_IN) == 0:\n",
         "    votes = [rng.randrange(NOISE_ONE_IN) == 0 for _ in range(3)]\n"
         "    if sum(votes) >= 2:\n"))),
    ("snapshot reuses the caller's write dicts", mod(
        ("        writes.append({\"tool\": tool, \"target\": target, \"set\": fresh})\n",
         "        writes.append(w)\n"))),
    ("snapshot reuses the caller's write set dicts", mod(
        ("        writes.append({\"tool\": tool, \"target\": target, \"set\": fresh})\n",
         "        writes.append({\"tool\": tool, \"target\": target, \"set\": sets})\n"))),
    ("snapshot reuses the caller's write list", mod(
        ("            \"initial\": initial, \"writes\": tuple(writes), \"final_text\": final_text,\n",
         "            \"initial\": initial, \"writes\": recorded, \"final_text\": final_text,\n"))),
    ("snapshot reuses the caller's state rows", mod(
        ("        out[target] = fresh\n", "        out[target] = row\n"))),
    ("key check after lookup (episode)", mod(
        ("    _keys(episode, \"episode_key_invalid\")\n    for name in EPISODE_FIELDS:\n"
         "        if name not in episode:\n            raise _Bad(name + \"_missing\")\n",
         "    for name in EPISODE_FIELDS:\n        if name not in episode:\n"
         "            raise _Bad(name + \"_missing\")\n"
         "    _keys(episode, \"episode_key_invalid\")\n"))),
    ("key check after lookup (write)", mod(
        ("        _keys(w, \"write_key_invalid\")\n"
         "        _fields(w, WRITE_FIELDS, \"write_fields_invalid\")\n",
         "        _fields(w, WRITE_FIELDS, \"write_fields_invalid\")\n"
         "        _keys(w, \"write_key_invalid\")\n"))),
    # Further Arm A mutants.
    ("Arm A: a write where none was expected is no_write_ok", mod(
        ("        cls = PREMATURE if occurred else NO_WRITE_OK\n",
         "        cls = NO_WRITE_OK\n"))),
    ("Arm A ignores unexpected writes", mod(
        ("            flags.append((i, UNEXPECTED_FLAG))\n", "            pass\n"))),
    ("Arm A tags unexpected writes as forbidden", mod(
        ("            flags.append((i, UNEXPECTED_FLAG))\n",
         "            flags.append((i, FORBIDDEN))\n"))),
    ("Arm A ignores a partly missing expected set", mod(
        ("    elif missing:\n        cls = MISSED\n", "    elif False:\n        cls = MISSED\n"))),
    ("Arm A: no write when one was expected is commit_ok", mod(
        ("    elif not occurred:\n        cls = MISSED\n",
         "    elif not occurred:\n        cls = COMMIT_OK\n"))),
    ("Arm A matches writes by tool only", mod(
        ("        if pair in expected:\n",
         "        if pair[0] in [p[0] for p in expected]:\n"))),
    # Arm B mutants.
    ("noise off", mod(("NOISE_ONE_IN = 4\n", "NOISE_ONE_IN = 10 ** 9\n"))),
    ("noise doubled", mod(
        ("    if rng.randrange(NOISE_ONE_IN) == 0:\n",
         "    if rng.randrange(NOISE_ONE_IN) < 2:\n"))),
    ("cue rule loses 'cannot'", mod(
        ("FAIL_CUES = (\"unable\", \"cannot\", ", "FAIL_CUES = (\"unable\", "))),
    ("cue rule is case-sensitive", mod(
        ("    low = final_text.lower()\n", "    low = final_text\n"))),
    # Gold mutants.
    ("gold ignores the writes", mod(
        ("        state[w[\"target\"]].update(w[\"set\"])\n", "        pass\n"))),
    ("gold compares only the first field", mod(
        ("        for field in sorted(state[target]):\n",
         "        for field in sorted(state[target])[:1]:\n"))),
    ("agreement counts disagreements the wrong way round", mod(
        ("            elif mine == PASS:\n", "            elif mine == FAIL:\n"))),
    ("agreement counts config_error records", mod(
        ("    rows = [r for r in records if r[\"status\"] == OK]\n",
         "    rows = [r for r in records if r[\"arm_a\"] is not None or True]\n"))),
    # Input mutants (F1: exact-str keys, exact types).
    ("non-str keys admitted everywhere", mod(
        ("        if type(k) is not str:\n            raise _Bad(detail)\n",
         "        if False:\n            raise _Bad(detail)\n"))),
    ("state keys not checked", mod(
        ("    _keys(s, name + \"_key_invalid\")\n", ""))),
    ("state row keys not checked", mod(
        ("        _keys(row, name + \"_key_invalid\")\n", ""))),
    ("expected entry keys not checked", mod(
        ("        _keys(entry, \"expected_key_invalid\")\n", ""))),
    ("write keys not checked", mod(
        ("        _keys(w, \"write_key_invalid\")\n", ""))),
    ("write set keys not checked", mod(
        ("        _keys(sets, \"write_set_key_invalid\")\n", ""))),
    ("str subclasses admitted as ids", mod(
        ("    return type(v) is str and v.strip() != \"\"\n",
         "    return isinstance(v, str) and v.strip() != \"\"\n"))),
    ("write tool may be a str subclass", mod(
        ("        if type(tool) is not str or tool not in tools:\n"
         "            raise _Bad(\"write_tool_unknown\")\n",
         "        if not isinstance(tool, str) or tool not in tools:\n"
         "            raise _Bad(\"write_tool_unknown\")\n"))),
    ("seed may be a bool or an int subclass", mod(
        ("        if type(seed) is not int:\n", "        if not isinstance(seed, int):\n"))),
    ("writes may be a tuple", mod(
        ("    if type(recorded) is not list:\n",
         "    if type(recorded) not in (list, tuple):\n"))),
    ("write may be a dict subclass", mod(
        ("        if type(w) is not dict:\n", "        if not isinstance(w, dict):\n"))),
    ("final text may be a str subclass", mod(
        ("    if type(final_text) is not str:\n",
         "    if not isinstance(final_text, str):\n"))),
    ("state value may be a str subclass", mod(
        ("            if not _id(field) or type(value) is not str:\n",
         "            if not _id(field) or not isinstance(value, str):\n"))),
    ("write set value may be a str subclass", mod(
        ("            if field not in initial[target] or type(value) is not str:\n",
         "            if field not in initial[target] or not isinstance(value, str):\n"))),
    ("unknown episode field admitted", mod(
        ("    _fields(episode, EPISODE_FIELDS, \"episode_unknown_field\")\n", ""))),
    ("gold shape not checked", mod(
        ("    if sorted(gold) != sorted(initial):\n        raise _Bad(\"gold_state_shape\")\n",
         "    if False:\n        raise _Bad(\"gold_state_shape\")\n"))),
    ("duplicate expected writes admitted", mod(
        ("        if (tool, target) in expected:\n            raise _Bad(\"expected_duplicate\")\n",
         ""))),
    ("scoring exceptions propagate", mod(
        ("        return _run(snap, seed)\n    except Exception:\n"
         "        return _config(\"internal_error\")\n",
         "        return _run(snap, seed)\n    finally:\n        pass\n"))),
    ("paper numbers reported as measured", mod(
        ("    return ON_UNMEASURED\n", "    return \"measured\"\n"))),
    # Gate mutants.
    ("gate ignores customer auth", mod(
        ("        ok = digest[\"customer_auth\"] is True and digest[\"order_status\"] in "
         "PERMITTED_STATUS[tool]\n",
         "        ok = digest[\"order_status\"] in PERMITTED_STATUS[tool]\n"))),
    ("gate ignores order status", mod(
        ("        ok = digest[\"customer_auth\"] is True and digest[\"order_status\"] in "
         "PERMITTED_STATUS[tool]\n",
         "        ok = digest[\"customer_auth\"] is True\n"))),
    ("gate digest drops nothing", mod(
        ("    return dict((k, v) for k, v in full.items() if k not in dropped)\n",
         "    return full\n"))),
    ("lossy gate fails closed", mod(
        ("        ok = REQUEST_VERB[tool] in digest[\"request_text\"].lower()\n",
         "        ok = False\n"))),
    ("gate auth may be an int", mod(
        ("    if type(auth) is not bool:\n", "    if auth not in (True, False):\n"))),
    ("gate request keys not checked", mod(
        ("    _keys(request, \"request_key_invalid\")\n", ""))),
    ("gate re-reads the caller's request", mod(
        ("        return {\"status\": OK, \"detail\": OK, \"decision\": _gate_decide(digest),\n",
         "        return {\"status\": OK, \"detail\": OK, \"decision\": "
         "_gate_decide(request if drop else digest),\n"))),
    ("gate exceptions propagate", mod(
        ("    try:\n        return {\"status\": OK, \"detail\": OK, \"decision\": _gate_decide(digest),\n"
         "                \"seen\": tuple(sorted(digest))}\n    except Exception:\n",
         "    try:\n        return {\"status\": OK, \"detail\": OK, \"decision\": _gate_decide(digest),\n"
         "                \"seen\": tuple(sorted(digest))}\n    except ZeroDivisionError:\n"))),
    # Oracle mutants (the oracle must stay a real reference).
    ("oracle: every stray write tagged forbidden", orc(
        ("    tag = \"unexpected\" if want else \"forbidden\"\n", "    tag = \"forbidden\"\n"))),
    ("oracle: gold ignores the writes", orc(
        ("            flat[(w[\"target\"], f)] = w[\"set\"][f]\n", "            pass\n"))),
    ("oracle: absent expected writes ignored", orc(
        ("    elif absent:\n        cls = \"missed_commitment\"\n",
         "    elif False:\n        cls = \"missed_commitment\"\n"))),
    ("oracle: cue rule case-sensitive", orc(
        ("    t = text.lower()\n", "    t = text\n"))),
    ("oracle: gate ignores auth", orc(
        ("    if request[\"customer_auth\"] and request[\"order_status\"] == _OK_STATUS[tool]:\n",
         "    if request[\"order_status\"] == _OK_STATUS[tool]:\n"))),
]


def _w():
    return {k: copy.deepcopy(v) for k, v in WORLD_ORIG.items()}


def _set(**kw):
    for k, v in kw.items():
        setattr(fixtures, k, v)


def w_planted_write_removed():
    w = _w()
    w["EPISODES"]["air-forbidden-cancel"]["writes"] = []
    _set(EPISODES=w["EPISODES"])


def w_planted_write_made_expected():
    w = _w()
    e = w["EPISODES"]["retail-forbidden-extra"]
    e["expected_writes"].append({"tool": "cancel_pending_order", "target": "O6"})
    _set(EPISODES=w["EPISODES"])


def w_planted_text_made_refusal():
    w = _w()
    w["EPISODES"]["air-forbidden-cancel"]["final_text"] = "I cannot cancel R3."
    _set(EPISODES=w["EPISODES"])


def w_planted_label_removed():
    w = _w()
    lab = w["LABELS"]["air-forbidden-cancel"]
    w["LABELS"]["air-forbidden-cancel"] = ((),) + lab[1:]
    _set(LABELS=w["LABELS"])


def w_pinned_arm_b_edited():
    w = _w()
    w["PINNED_ARM_B"]["retail-return-ok"] = "PASS"
    _set(PINNED_ARM_B=w["PINNED_ARM_B"])


def w_seed_changed():
    _set(JUDGE_SEED=fixtures.JUDGE_SEED + 1)


def w_gold_matches_wrong_value():
    w = _w()
    w["EPISODES"]["retail-wrong-value"]["gold_state"]["O3"]["address"] = "1 Pine Road West"
    _set(EPISODES=w["EPISODES"])


def w_clean_episode_gets_a_write():
    w = _w()
    w["EPISODES"]["air-info-ok"]["writes"] = [
        {"tool": "update_passengers", "target": "R8", "set": {"status": "booked"}}]
    _set(EPISODES=w["EPISODES"])


def w_gate_valid_text_explicit():
    w = _w()
    w["GATE_CASES"]["G1-valid-indirect"][0]["request_text"] = "Please cancel booking R1."
    _set(GATE_CASES=w["GATE_CASES"])


def w_gate_forbidden_status_fixed():
    w = _w()
    w["GATE_CASES"]["G2-forbidden-flown"][0]["order_status"] = "booked"
    _set(GATE_CASES=w["GATE_CASES"])


def w_lossy_drop_emptied():
    _set(LOSSY_DROP=[])


def w_sweep_range_edited():
    _set(SEED_SWEEP_RANGE=(0, 7))


def w_episodes_shared():
    fixtures.episodes = lambda: fixtures.EPISODES


def w_gate_cases_shared():
    fixtures.gate_cases = lambda: fixtures.GATE_CASES


WORLD_MUTANTS = [
    ("planted forbidden write removed", w_planted_write_removed),
    ("planted forbidden write made expected", w_planted_write_made_expected),
    ("planted episode's final text made a refusal", w_planted_text_made_refusal),
    ("planted label removed", w_planted_label_removed),
    ("pinned Arm B verdict edited", w_pinned_arm_b_edited),
    ("judge seed changed", w_seed_changed),
    ("gold state matches the wrong value", w_gold_matches_wrong_value),
    ("clean no-write episode gets a write", w_clean_episode_gets_a_write),
    ("gate: valid request names the verb", w_gate_valid_text_explicit),
    ("gate: forbidden request gets a permitted status", w_gate_forbidden_status_fixed),
    ("gate: lossy digest drops nothing", w_lossy_drop_emptied),
    ("seed sweep range edited", w_sweep_range_edited),
    ("episodes() returns shared state", w_episodes_shared),
    ("gate_cases() returns shared state", w_gate_cases_shared),
]


def h_scan_whole_day_readme():
    test_boundary_vs_judge.scan_text = lambda name, text: text


def h_own_rows_every_line():
    test_boundary_vs_judge.own_rows = lambda text: text.splitlines()


def h_own_rows_nothing():
    test_boundary_vs_judge.own_rows = lambda text: []


def h_hygiene_ignores_banned_words():
    real = test_boundary_vs_judge.hygiene_hits
    test_boundary_vs_judge.hygiene_hits = lambda text: real(text) - {"banned_word"}


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
    test_boundary_vs_judge.__dict__.update(TEST_SNAPSHOT)


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_boundary_vs_judge)
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
