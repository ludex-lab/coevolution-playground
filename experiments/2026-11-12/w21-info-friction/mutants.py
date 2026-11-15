"""Mutant runner: each mutant patches the code or the fixture world, then the
unittest suite runs. A mutant is killed when at least one test fails.

Code mutants replace one exact snippet of info_friction.py (each snippet
must occur exactly once) and re-execute the patched source in memory inside
the info_friction module; the patched text is also handed to the suite's
source checks (test_info_friction.SOURCE_OVERRIDE). World mutants change
the fixtures in memory. Nothing is written to disk.

Run: python3 -B mutants.py
Exit code 0 only when every mutant is killed and the clean suite passes.
"""

import copy
import io
import os
import sys
import unittest

import fixtures
import info_friction
import test_info_friction

SNAPSHOT = dict(vars(info_friction))
FIX_SNAPSHOT = dict(vars(fixtures))
TASKS_ORIG = copy.deepcopy(fixtures.TASKS)
EPISODES_ORIG = copy.deepcopy(fixtures.EPISODES)
PATH = os.path.join(os.path.dirname(os.path.abspath(info_friction.__file__)), "info_friction.py")
with open(PATH, "r", encoding="utf-8") as _fh:
    SOURCE = _fh.read()


def code(*pairs):
    """Return an apply() that swaps each (old, new) snippet once in info_friction.py."""
    def apply():
        text = SOURCE
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError("snippet not found exactly once: %r" % (old,))
            text = text.replace(old, new)
        exec(compile(text, PATH, "exec"), info_friction.__dict__)
        # The suite's source checks read the patched text, not the file.
        test_info_friction.SOURCE_OVERRIDE = text
    return apply


CODE_MUTANTS = [
    ("friction never trips", code(
        ("        if friction > bound:\n", "        if False:\n"))),
    ("bound checked with >= (off by one)", code(
        ("        if friction > bound:\n", "        if friction >= bound:\n"))),
    ("trip ends as SUCCESS", code(
        ("            return (STOP, FRICTION_BOUND, tuple(sorted(unresolved)), friction,",
         "            return (SUCCESS, FRICTION_BOUND, tuple(sorted(unresolved)), friction,"))),
    ("trip is not final (gathering goes on)", code(
        ("            # Fail closed: gathering stops and success cannot be declared.\n            return (STOP, FRICTION_BOUND, tuple(sorted(unresolved)), friction,\n                    tuple(signals))\n",
         "            pass\n"))),
    ("exploration counted as friction", code(
        ("            if is_new:\n                kind = EXPLORE\n                friction = 0\n",
         "            if is_new:\n                kind = EXPLORE\n                friction += 1\n"))),
    ("exploration does not reset friction", code(
        ("            if is_new:\n                kind = EXPLORE\n                friction = 0\n",
         "            if is_new:\n                kind = EXPLORE\n"))),
    ("resolution does not reset friction", code(
        ("            kind = RESOLVED\n            friction = 0\n", "            kind = RESOLVED\n"))),
    ("recurrent adds no friction", code(
        ("                kind = RECURRENT\n                friction += 1\n",
         "                kind = RECURRENT\n"))),
    ("re-resolving counts as progress", code(
        ("        if resolves is not None and resolves in unresolved:\n            unresolved.remove(resolves)\n",
         "        if resolves is not None:\n            if resolves in unresolved:\n                unresolved.remove(resolves)\n"))),
    ("evidence never recorded as seen", code(
        ("        seen_evidence.add(evidence)\n", ""))),
    ("declared rule ignored (always evidence key)", code(
        ("            if rule == NOVELTY_DECLARED:\n                is_new = novel\n",
         "            if False:\n                is_new = novel\n"))),
    ("declared rule inverted", code(
        ("                is_new = novel\n", "                is_new = not novel\n"))),
    ("success with requirements left", code(
        ("        if not unresolved:\n", "        if len(unresolved) <= 1:\n"))),
    ("post-completion activity counted", code(
        ("            # Observations after completion are not counted.\n            return SUCCESS,",
         "            # Observations after completion are not counted.\n            return CONTINUE,"))),
    ("success on timeout", code(
        ("        decision, reason = on_expiry, EXPIRED\n",
         "        decision, reason = SUCCESS, EXPIRED\n"))),
    ("continue on timeout", code(
        ("    if now >= deadline:\n", "    if False:\n"))),
    ("expiry strictly after deadline", code(
        ("    if now >= deadline:\n", "    if now > deadline:\n"))),
    ("expiry returns caller on_expiry object", code(
        ("        decision, reason = on_expiry, EXPIRED\n",
         "        decision, reason = task[\"on_expiry\"], EXPIRED\n"))),
    ("expiry always HOLD", code(
        ("        decision, reason = on_expiry, EXPIRED\n",
         "        decision, reason = HOLD, EXPIRED\n"))),
    ("expiry guard removed (backdated evidence overturns expiry)", code(
        ("    if now >= deadline:\n", "    if now >= deadline and decision == CONTINUE:\n"))),
    ("expiry guard skips a stop", code(
        ("    if now >= deadline:\n", "    if now >= deadline and decision != STOP:\n"))),
    ("expiry guard skips a success", code(
        ("    if now >= deadline:\n", "    if now >= deadline and decision != SUCCESS:\n"))),
    ("late observations counted", code(
        ("        if t >= deadline:\n", "        if t > deadline:\n"))),
    ("missing bound defaults to 3", code(
        ("    if \"friction_bound\" not in task:\n        raise _Bad(D_BOUND_MISSING)\n    bound = task[\"friction_bound\"]\n",
         "    bound = task.get(\"friction_bound\", 3)\n"))),
    ("missing on_expiry defaults to HOLD", code(
        ("    if \"on_expiry\" not in task:\n        raise _Bad(D_ON_EXPIRY_MISSING)\n    on_expiry = _canonical(task[\"on_expiry\"], ON_EXPIRY_VALUES)",
         "    on_expiry = _canonical(task.get(\"on_expiry\", HOLD), ON_EXPIRY_VALUES)"))),
    ("missing novelty rule defaults to evidence_key", code(
        ("    if \"novelty_rule\" not in task:\n        raise _Bad(D_RULE_MISSING)\n    rule = _canonical(task[\"novelty_rule\"], NOVELTY_RULES)",
         "    rule = _canonical(task.get(\"novelty_rule\", NOVELTY_EVIDENCE_KEY), NOVELTY_RULES)"))),
    ("SUCCESS accepted as on_expiry", code(
        ("ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY)\n", "ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY, SUCCESS)\n"))),
    ("negative bound accepted", code(
        ("    if not _is_int(bound) or bound < 0:", "    if not _is_int(bound):"))),
    ("isinstance(str) instead of exact type", code(
        ("    return type(value) is str\n", "    return isinstance(value, str)\n"))),
    ("isinstance(int) instead of exact type", code(
        ("    return type(value) is int\n", "    return isinstance(value, int)\n"))),
    ("canonical match without type check", code(
        ("    if not _is_str(value):\n        return None\n    for choice", "    for choice"))),
    ("dict subclass accepted", code(
        ("    if type(mapping) is not dict:\n        raise _Bad(detail)",
         "    if not isinstance(mapping, dict):\n        raise _Bad(detail)"))),
    ("non-bool novel accepted", code(
        ("            novel = obs[\"novel\"]\n            if type(novel) is not bool:\n                raise _Bad(D_OBS)\n",
         "            novel = obs[\"novel\"]\n"))),
    ("novel label under evidence_key accepted", code(
        ("        elif \"novel\" in obs:\n            raise _Bad(D_OBS)\n", ""))),
    ("unknown requirement accepted", code(
        ("            if not _is_str(resolves) or resolves not in requirements:",
         "            if not _is_str(resolves):"))),
    ("duplicate requirements accepted", code(
        ("        if not _is_str(req) or not req or req in seen:", "        if not _is_str(req) or not req:"))),
    ("empty requirements accepted", code(
        ("    if type(reqs) is not list or not reqs:", "    if type(reqs) is not list:"))),
    ("time going backwards accepted", code(
        ("        if not _is_int(t) or t < last_t or t > now:", "        if not _is_int(t) or t > now:"))),
    ("observations after now accepted", code(
        ("        if not _is_int(t) or t < last_t or t > now:", "        if not _is_int(t) or t < last_t:"))),
    ("evaluate without try/except", code(
        ("        return _evaluate(task, observations, now)\n    except Exception:",
         "        return _evaluate(task, observations, now)\n    except ZeroDivisionError:"))),
    ("domain results claimed", code(
        ("    \"\"\"The paper's eight-domain and RL results are not measured here.\"\"\"\n    return ON_UNMEASURED",
         "    \"\"\"The paper's eight-domain and RL results are not measured here.\"\"\"\n    return \"measured\""))),
    ("config_error echoes the caller task_id", code(
        ("        return _record(None, REJECT, CONFIG_ERROR, bad.detail)",
         "        return _record(task.get(\"task_id\") if type(task) is dict else None, REJECT, CONFIG_ERROR, bad.detail)"))),
    ("task_id read twice (re-read after validation)", code(
        ("    return task_id, tuple(seen), bound, deadline, on_expiry, rule",
         "    return task[\"task_id\"], tuple(seen), bound, deadline, on_expiry, rule"))),
    ("task_id assigned late from a second read (G1)", code(
        ("    # Read once; the same local is validated and returned.\n    task_id = task[\"task_id\"]\n    if not _is_str(task_id) or not task_id:\n        raise _Bad(D_TASK)\n",
         "    if not _is_str(task[\"task_id\"]) or not task[\"task_id\"]:\n        raise _Bad(D_TASK)\n"),
        ("    return task_id, tuple(seen), bound, deadline, on_expiry, rule",
         "    task_id = task[\"task_id\"]\n    return task_id, tuple(seen), bound, deadline, on_expiry, rule"))),
    ("task_id re-read via unbound dict.get (G8)", code(
        ("    return task_id, tuple(seen), bound, deadline, on_expiry, rule",
         "    return dict.get(task, \"task_id\"), tuple(seen), bound, deadline, on_expiry, rule"))),
    ("friction_bound re-read after validation (G11)", code(
        ("    return task_id, tuple(seen), bound, deadline, on_expiry, rule",
         "    return task_id, tuple(seen), task[\"friction_bound\"], deadline, on_expiry, rule"))),
    ("novel read twice, r2 shape (G12)", code(
        ("            if \"novel\" not in obs:\n                raise _Bad(D_OBS)\n            novel = obs[\"novel\"]\n            if type(novel) is not bool:\n                raise _Bad(D_OBS)\n",
         "            if \"novel\" not in obs or type(obs[\"novel\"]) is not bool:\n                raise _Bad(D_OBS)\n            novel = obs[\"novel\"]\n"))),
    ("evidence re-read after validation (G13)", code(
        ("        out.append((t, evidence, resolves, novel))",
         "        out.append((t, obs[\"evidence\"], resolves, novel))"))),
    ("task_id re-read via dict(task) snapshot (G14)", code(
        ("    return task_id, tuple(seen), bound, deadline, on_expiry, rule",
         "    return dict(task)[\"task_id\"], tuple(seen), bound, deadline, on_expiry, rule"))),
    ("task_id re-read via items() (G15)", code(
        ("    return task_id, tuple(seen), bound, deadline, on_expiry, rule",
         "    return next(v for k, v in task.items() if k == \"task_id\"), tuple(seen), bound, deadline, on_expiry, rule"))),
    ("equal timestamps rejected", code(
        ("        if not _is_int(t) or t < last_t or t > now:", "        if not _is_int(t) or t <= last_t or t > now:"))),
    ("evidence key normalised (case and spaces)", code(
        ("                is_new = evidence not in seen_evidence\n",
         "                is_new = evidence.strip().lower() not in {e.strip().lower() for e in seen_evidence}\n"))),
    ("negative t accepted", code(
        ("    last_t = 0\n", "    last_t = -10\n"))),
    ("unresolved not reported on stop", code(
        ("            return (STOP, FRICTION_BOUND, tuple(sorted(unresolved)), friction,",
         "            return (STOP, FRICTION_BOUND, (), friction,"))),
]


def _set(tasks=None, episodes=None):
    if tasks is not None:
        fixtures.TASKS[:] = tasks
    if episodes is not None:
        fixtures.EPISODES.clear()
        fixtures.EPISODES.update(episodes)


def _t():
    return copy.deepcopy(TASKS_ORIG)


def _e():
    return copy.deepcopy(EPISODES_ORIG)


def w_bound_raised():
    t = _t(); t[0]["friction_bound"] = 5; _set(tasks=t)


def w_bound_lowered():
    t = _t(); t[0]["friction_bound"] = 1; _set(tasks=t)


def w_on_expiry_removed():
    t = _t(); del t[0]["on_expiry"]; _set(tasks=t)


def w_bound_removed():
    t = _t(); del t[1]["friction_bound"]; _set(tasks=t)


def w_on_expiry_changed():
    t = _t(); t[1]["on_expiry"] = "ESCALATE"; _set(tasks=t)


def w_rule_swapped():
    t = _t(); t[1]["novelty_rule"] = "evidence_key"; _set(tasks=t)


def w_requirement_added():
    t = _t(); t[0]["requirements"].append("weather"); _set(tasks=t)


def w_deadline_shortened():
    t = _t(); t[0]["deadline"] = 6; _set(tasks=t)


def w_duplicate_task_ids():
    t = _t(); t[1]["task_id"] = "rescue"; _set(tasks=t)


def w_repeats_relabelled_new():
    e = _e()
    obs, now = e["rescue"]["repeat_loop"]
    e["rescue"]["repeat_loop"] = ([dict(x, evidence="%s-%d" % (x["evidence"], x["t"])) for x in obs], now)
    _set(episodes=e)


def w_exploration_becomes_repeats():
    e = _e()
    obs, now = e["rescue"]["explore_then_resolve"]
    e["rescue"]["explore_then_resolve"] = ([dict(x, evidence="drone-1") if x["evidence"].startswith("drone") else x for x in obs], now)
    _set(episodes=e)


def w_declared_labels_flipped():
    e = _e()
    obs, now = e["grid"]["declared_revisit"]
    e["grid"]["declared_revisit"] = ([dict(x, novel=not x["novel"]) for x in obs], now)
    _set(episodes=e)


def w_resolution_dropped():
    e = _e()
    obs, now = e["rescue"]["direct"]
    obs = copy.deepcopy(obs)
    del obs[2]["resolves"]
    e["rescue"]["direct"] = (obs, now)
    _set(episodes=e)


def w_clock_stopped():
    e = _e()
    obs, now = e["grid"]["silent_until_deadline"]
    e["grid"]["silent_until_deadline"] = (obs, 11)
    _set(episodes=e)


def w_tasks_shared():
    fixtures.tasks = lambda: fixtures.TASKS


WORLD_MUTANTS = [
    ("friction bound raised", w_bound_raised),
    ("friction bound lowered", w_bound_lowered),
    ("on_expiry removed from a task", w_on_expiry_removed),
    ("friction bound removed from a task", w_bound_removed),
    ("on_expiry changed in a task", w_on_expiry_changed),
    ("declared novelty rule swapped", w_rule_swapped),
    ("extra requirement added", w_requirement_added),
    ("deadline shortened", w_deadline_shortened),
    ("duplicate task ids", w_duplicate_task_ids),
    ("repeats relabelled as new evidence", w_repeats_relabelled_new),
    ("exploration turned into repeats", w_exploration_becomes_repeats),
    ("declared novelty labels flipped", w_declared_labels_flipped),
    ("one resolution dropped", w_resolution_dropped),
    ("clock stopped before the deadline", w_clock_stopped),
    ("tasks() returns shared state", w_tasks_shared),
]

MUTANTS = [("code", n, a) for n, a in CODE_MUTANTS] + [("world", n, a) for n, a in WORLD_MUTANTS]


def restore():
    for name in [n for n in vars(info_friction) if n not in SNAPSHOT]:
        delattr(info_friction, name)
    info_friction.__dict__.update(SNAPSHOT)
    fixtures.__dict__.update(FIX_SNAPSHOT)
    _set(tasks=copy.deepcopy(TASKS_ORIG), episodes=copy.deepcopy(EPISODES_ORIG))
    test_info_friction.SOURCE_OVERRIDE = None


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_info_friction)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


def main():
    restore()
    ran, bad = run_suite()
    print("clean suite: %d tests, %d failing" % (ran, bad))
    clean_ok = bad == 0
    killed = {"code": 0, "world": 0}
    for kind, name, apply in MUTANTS:
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
    n_code, n_world = len(CODE_MUTANTS), len(WORLD_MUTANTS)
    total = killed["code"] + killed["world"]
    print("killed %d/%d (code %d/%d, world %d/%d)" % (
        total, n_code + n_world, killed["code"], n_code, killed["world"], n_world))
    return 0 if clean_ok and total == n_code + n_world else 1


if __name__ == "__main__":
    sys.exit(main())
