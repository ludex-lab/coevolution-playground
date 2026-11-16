"""Mutant runner: each mutant patches the code, the fixture world or the test
harness, then the unittest suite runs. A mutant is killed when at least one
test fails or errors.

Code mutants replace one exact snippet of owned_exceptions.py or oracle.py
(each snippet must occur exactly once) and re-execute the patched source in
memory inside that module. World mutants change the fixtures in memory.
Harness mutants replace one helper of the test module in memory. Nothing is
written to disk.

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
import owned_exceptions
import test_owned_exceptions

MODULES = {"owned_exceptions": owned_exceptions, "oracle": oracle}
SNAPSHOTS = {k: dict(vars(m)) for k, m in MODULES.items()}
FIX_SNAPSHOT = dict(vars(fixtures))
TEST_SNAPSHOT = dict(vars(test_owned_exceptions))
WORLD = ("TRUTHS", "RECORDS", "CASES", "D0", "D1", "D2")
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
    return code("owned_exceptions", *pairs)


def orc(*pairs):
    return code("oracle", *pairs)


CODE_MUTANTS = [
    # Validation (F1 lessons: exact types, exact-str keys, snapshot).
    ("key type not checked", mod(
        ("    for k in obj:\n        if type(k) is not str:\n            raise ConfigError(what + \"_key_not_str\")\n",
         "    pass\n"))),
    ("dict subclass accepted", mod(
        ("    if type(obj) is not dict:\n        raise ConfigError(what + \"_not_dict\")\n",
         "    if not isinstance(obj, dict):\n        raise ConfigError(what + \"_not_dict\")\n"))),
    ("bool and int subclass accepted as int", mod(
        ("    if type(value) is not int:\n        raise ConfigError(what + \"_not_int\")\n",
         "    if not isinstance(value, int):\n        raise ConfigError(what + \"_not_int\")\n"))),
    ("size accepts bool", mod(
        ("    if type(obj[\"size\"]) is not int:", "    if not isinstance(obj[\"size\"], (int, float)):"))),
    ("str subclass value accepted", mod(
        ("    if type(value) is not str:\n        raise ConfigError(what + \"_not_str\")\n",
         "    if not isinstance(value, str):\n        raise ConfigError(what + \"_not_str\")\n"))),
    ("owner str subclass accepted", mod(
        ("    if type(value) is not str:\n        raise ConfigError(\"owner_not_str\")\n",
         "    if not isinstance(value, str):\n        raise ConfigError(\"owner_not_str\")\n"))),
    ("upper range not checked", mod(
        ("    if value < lo or value > hi:", "    if value < lo:"))),
    ("size range not checked", mod(
        ("    if obj[\"size\"] not in sizes:", "    if False:"))),
    ("tuple evidence accepted", mod(
        ("    if type(obj) is not list:", "    if not isinstance(obj, (list, tuple)):"))),
    ("extra submission keys accepted", mod(
        ("    if not need <= keys or not keys <= need | set(GATE_KEYS):", "    if not need <= keys:"))),
    ("submission key type not checked", mod(
        ("            raise ConfigError(\"submission_key_not_str\")\n", "            pass\n"))),
    ("submission dict subclass accepted", mod(
        ("        raise ConfigError(\"submission_not_dict\")\n", "        pass\n"))),
    ("evidence not validated", mod(
        ("        evidence = validate_records(obj[\"evidence\"])", "        evidence = tuple(obj[\"evidence\"])"))),
    # Semantics of the rule and the typed space.
    ("base q1 bound strict", mod(
        ("    return 1 if (item[2] <= _q1_max() and item[3] <= _q2_max()) else 0",
         "    return 1 if (item[2] < _q1_max() and item[3] <= _q2_max()) else 0"))),
    ("scope ignored", mod(
        ("    if scope != \"all\" and item[1] != scope:\n        return False\n", ""))),
    ("subject ignored in fires", mod(
        ("    if item[0] != subject:\n        return False\n    if scope", "    if scope"))),
    ("q1 margin off by one", mod(
        ("        return item[2] > _q1_max() - size", "        return item[2] >= _q1_max() - size"))),
    ("q2 margin reads q1", mod(
        ("        return item[3] > _q2_max() - size", "        return item[2] > _q2_max() - size"))),
    ("sum cap off by one", mod(
        ("        return item[2] + item[3] > size", "        return item[2] + item[3] >= size"))),
    ("canonical returns the first declaration", mod(
        ("        if region(d) == target:", "        if True:"))),
    ("domain shrunk", mod(
        ("Q_VALUES = tuple(range(8))", "Q_VALUES = tuple(range(7))"))),
    # Compiled units.
    ("gating weight too small", mod(
        ("GATING = 100  #", "GATING = 3  #"))),
    ("scope gate not compiled", mod(
        ("        w[len(SUBJECTS) + CLASSES.index(scope)] = GATING\n        bias -= GATING\n", "        pass\n"))),
    ("q1 margin bias off", mod(
        ("        bias += size - _q1_max()", "        bias += size - _q1_max() + 1"))),
    ("sum cap bias off", mod(
        ("        bias -= size\n", "        bias -= size - 1\n"))),
    ("relu dropped", mod(
        ("    return s if s > 0 else 0", "    return s"))),
    ("decision threshold off", mod(
        ("    return 1 if out >= 1 else 0", "    return 1 if out >= 0 else 0"))),
    ("reserved units ignored", mod(
        ("    units = state.base + tuple(u for u in state.reserved if u != ZERO_UNIT)\n    return bytes(",
         "    units = state.base\n    return bytes("))),
    ("table row applies to every subject", mod(
        ("                if decl[0] == x[0] and fires(decl, x):", "                if fires((x[0],) + tuple(decl[1:]), x):"))),
    ("global edit baseline scoped to owner", mod(
        ("        moved = (x[0],) + tuple(decl[1:])", "        moved = tuple(decl)"))),
    ("withdraw leaves the bias", mod(
        ("    return tuple(x - y for x, y in zip(u, v))", "    return tuple(x - y for x, y in zip(u, v[:-1] + (0,)))"))),
    ("withdraw leaves the row live", mod(
        ("    live = tuple(r for r in state.live if r[0] != owner)", "    live = state.live"))),
    ("live rows not sorted", mod(
        ("                _sorted_live(state.live + ((owner, decl),)))", "                state.live + ((owner, decl),))"))),
    ("behaviour check disabled", mod(
        ("        if new_dec[i] != want:\n            return False\n", "        pass\n"))),
    ("base digest ignores units", mod(
        ("        [BASE_RULE, state.base]).encode", "        [BASE_RULE]).encode"))),
    ("params digest ignores reserved", mod(
        ("        [state.base, state.reserved]).encode", "        [state.base]).encode"))),
    # Gate.
    ("broken records not counted", mod(
        ("            b += 1\n", "            pass\n"))),
    ("fixed records counted loosely", mod(
        ("        if after == label and before != label:", "        if after == label:"))),
    ("tail drops the mass", mod(
        ("        tails[j] = tails[j + 1] + pmf[j]", "        tails[j] = tails[j + 1]"))),
    ("threshold ignores the typed-space size", mod(
        ("            if h * tails[c] <= GATE_ALPHA:", "            if tails[c] <= GATE_ALPHA:"))),
    ("gate minimum ignored", mod(
        ("    return c is not None and a - b >= max(GATE_MIN, c)", "    return c is not None and a - b >= c"))),
    ("gate strict", mod(
        ("    return c is not None and a - b >= max(GATE_MIN, c)", "    return c is not None and a - b > max(GATE_MIN, c)"))),
    ("noise rate changed", mod(
        ("GATE_ETA = Fraction(1, 20)", "GATE_ETA = Fraction(1, 10)"))),
    # Learner.
    ("learner ignores the gate", mod(
        ("    if gated and not gate_passes(a, b, len(snap)):", "    if False:"))),
    ("learner tie-break by index only", mod(
        ("        key = (-(a - b), len(region(d)))", "        key = (-(a - b), 0)"))),
    ("learner proposes zero improvement", mod(
        ("        if a - b <= 0:\n            continue\n", "        if a - b < 0:\n            continue\n"))),
    # Acceptance body.
    ("ownership not checked", mod(
        ("    if decl[0] != subject:", "    if False:"))),
    ("half-gated submission accepted", mod(
        ("    if claimed is None or evidence is None:", "    if claimed is None and evidence is None:"))),
    ("claimed stats not compared", mod(
        ("    if (a, b) != claimed:", "    if False:"))),
    ("gate not re-run at acceptance", mod(
        ("    if not gate_passes(a, b, len(evidence)):", "    if False:"))),
    ("slot not checked", mod(
        ("    if _live_owner(state, owner) is not None:\n        return _verdict(REFUSE, \"slot_taken\"), state\n", ""))),
    ("unknown owner not refused", mod(
        ("    if subject is None:\n        return _verdict(REFUSE, \"unknown_owner\"), state\n", ""))),
    ("other party may withdraw", mod(
        ("    if actor != owner:\n        return _verdict(REFUSE, \"not_owner\"), state\n", ""))),
    ("state type not checked", mod(
        ("    if type(state) is not State:\n        raise ConfigError(\"state_not_state\")\n", "    pass\n"))),
    # Oracle (spec).
    ("oracle rule strict", orc(
        ("    return int(x[2] <= LIMIT1 and x[3] <= LIMIT2)", "    return int(x[2] < LIMIT1 and x[3] <= LIMIT2)"))),
    ("oracle scope ignored", orc(
        ("    if area != \"all\" and area != x[1]:\n        return False\n", ""))),
    ("oracle sum cap off by one", orc(
        ("    return x[2] + x[3] >= amount + 1", "    return x[2] + x[3] >= amount"))),
    ("oracle row applies to every subject", orc(
        ("        if row[0] == x[0] and hits(row, x):", "        if hits((x[0],) + tuple(row[1:]), x):"))),
    ("oracle noise doubled", orc(
        ("            nxt[j + 1] += p * NOISE", "            nxt[j + 1] += p * (NOISE + NOISE)"))),
    ("oracle ownership not checked", orc(
        ("    if HOLDERS[who] != row[0]:\n        return (\"REFUSE\", \"not_owner\")\n", ""))),
    ("oracle slot not checked", orc(
        ("    if any(w == who for w, _ in rows):\n        return (\"REFUSE\", \"slot_taken\")\n", ""))),
    ("oracle half-gated accepted", orc(
        ("    if claim is None or recs is None:", "    if claim is None and recs is None:"))),
    ("oracle tally counts every change as fixed", orc(
        ("            if new == y:\n                fixed += 1\n            else:\n                broken += 1\n",
         "            fixed += 1\n"))),
    ("oracle other party may withdraw", orc(
        ("    if actor != holder:\n        return (\"REFUSE\", \"not_owner\")\n", ""))),
    ("oracle bool label accepted", orc(
        ("    if not (_plain(y, int) and y in (0, 1)):", "    if not (isinstance(y, int) and y in (0, 1)):"))),
    ("oracle gate minimum ignored", orc(
        ("    if c is None or t[0] - t[1] < max(MIN_GAIN, c):", "    if c is None or t[0] - t[1] < c:"))),
]


def _set(name, value):
    def apply():
        setattr(fixtures, name, value)
    return apply


def _flip_label():
    recs = copy.deepcopy(WORLD_ORIG["RECORDS"])
    recs["p0"][0]["label"] = 1 - recs["p0"][0]["label"]
    fixtures.RECORDS = recs


def _truncate():
    recs = copy.deepcopy(WORLD_ORIG["RECORDS"])
    recs["p1"] = recs["p1"][:20]
    fixtures.RECORDS = recs


def _swap_p3():
    recs = copy.deepcopy(WORLD_ORIG["RECORDS"])
    recs["p3"] = copy.deepcopy(recs["p2"])
    fixtures.RECORDS = recs


def _case_reason():
    cases = list(WORLD_ORIG["CASES"])
    for i, c in enumerate(cases):
        if c[0].startswith("R6 "):
            cases[i] = c[:4] + ("gate_failed",)
    fixtures.CASES = cases


def _drop_case():
    fixtures.CASES = [c for c in WORLD_ORIG["CASES"] if not c[0].startswith("C2 ")]


def _truth_p1_wide():
    t = dict(WORLD_ORIG["TRUTHS"])
    t["p1"] = ("tighten", ("s1", "all", "q2_margin", 2))
    fixtures.TRUTHS = t


def _truth_p2_tight():
    t = dict(WORLD_ORIG["TRUTHS"])
    t["p2"] = ("tighten", WORLD_ORIG["D2"])
    fixtures.TRUTHS = t


def _evidence_once():
    orig = FIX_SNAPSHOT["evidence_for"]

    def evidence_for(decl, reps=1):
        return orig(decl, reps)
    fixtures.evidence_for = evidence_for


def _substr_is_str():
    fixtures.SubStr = str


WORLD_MUTANTS = [
    ("p0 record label flipped", _flip_label),
    ("p1 records truncated", _truncate),
    ("p3 records replaced", _swap_p3),
    ("R6 expected reason changed", _case_reason),
    ("C2 NaN case dropped", _drop_case),
    ("p1 truth widened", _truth_p1_wide),
    ("p2 truth tightened", _truth_p2_tight),
    ("D0 size changed", _set("D0", ("s0", "all", "q1_margin", 3))),
    ("sweep evidence once", _evidence_once),
    ("str subclass helper is str", _substr_is_str),
]


def _harness(name, fn):
    def apply():
        setattr(test_owned_exceptions, name, fn)
    return apply


HARNESS_MUTANTS = [
    ("sweep empty", _harness("_sweep", lambda: [])),
    ("scan finds nothing", _harness("_scan_text", lambda text: [])),
    ("oracle helper reads weights", _harness(
        "_oracle_decisions", lambda state: owned_exceptions.decisions_compiled(state))),
    ("block mask empty", _harness(
        "_block_mask", lambda subject: [False] * len(owned_exceptions.ITEMS))),
    ("rebuild returns the empty state", _harness(
        "_rebuild", lambda live, rng, pool: owned_exceptions.empty_state())),
    ("declarations of one subject", _harness(
        "_all_decls", lambda: list(owned_exceptions.typed_space("s0")))),
    ("no files listed", _harness("_text_files", lambda: [])),
    ("case start ignored", _harness(
        "_run_case", lambda name: (lambda st, c: (st,) + owned_exceptions.submit(st, c[2][1])
                                   if c[2][0] == "submit" else
                                   (st,) + owned_exceptions.withdraw(st, c[2][1], c[2][2]))(
            owned_exceptions.empty_state(),
            {c[0]: c for c in fixtures.CASES}[name]))),
]


def restore():
    for k, m in MODULES.items():
        m.__dict__.clear()
        m.__dict__.update(SNAPSHOTS[k])
    fixtures.__dict__.clear()
    fixtures.__dict__.update(FIX_SNAPSHOT)
    for k in WORLD:
        setattr(fixtures, k, copy.deepcopy(WORLD_ORIG[k]))
    test_owned_exceptions.__dict__.clear()
    test_owned_exceptions.__dict__.update(TEST_SNAPSHOT)


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_owned_exceptions)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors), len(result.skipped)


def main():
    restore()
    ran, bad, skipped = run_suite()
    print("clean suite: %d tests, %d failing, %d skipped" % (ran, bad, skipped))
    if bad:
        return 1
    groups = (("code", CODE_MUTANTS), ("world", WORLD_MUTANTS),
              ("harness", HARNESS_MUTANTS))
    survivors = []
    totals = {}
    for group, mutants in groups:
        killed = 0
        for name, apply in mutants:
            restore()
            try:
                apply()
                _ran, bad, _sk = run_suite()
                dead = bad > 0
            except Exception as e:  # a crash while patching counts as killed
                dead = True
                if isinstance(e, ValueError) and "snippet" in str(e):
                    raise
            finally:
                restore()
            if dead:
                killed += 1
            else:
                survivors.append((group, name))
        totals[group] = (killed, len(mutants))
        print("%s: %d/%d killed" % (group, killed, len(mutants)))
    k = sum(v[0] for v in totals.values())
    n = sum(v[1] for v in totals.values())
    print("total: %d/%d killed" % (k, n))
    for group, name in survivors:
        print("SURVIVED [%s] %s" % (group, name))
    return 0 if not survivors else 1


if __name__ == "__main__":
    sys.exit(main())
