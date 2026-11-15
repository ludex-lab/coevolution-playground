"""Mutant runner: each mutant patches the code or the fixture world, then the
unittest suite runs. A mutant is killed when at least one test fails.

Code mutants replace one exact snippet of plan_ask.py (each snippet must
occur exactly once) and re-execute the patched source in memory inside the
plan_ask module. World mutants change the fixtures in memory. Nothing is
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
import plan_ask
import test_plan_ask

SNAPSHOT = dict(vars(plan_ask))
FIX_SNAPSHOT = dict(vars(fixtures))
TASKS_ORIG = copy.deepcopy(fixtures.TASKS)
PATH = os.path.join(os.path.dirname(os.path.abspath(plan_ask.__file__)), "plan_ask.py")
with open(PATH, "r", encoding="utf-8") as _fh:
    SOURCE = _fh.read()


def code(*pairs):
    """Return an apply() that swaps each (old, new) snippet once in plan_ask.py."""
    def apply():
        text = SOURCE
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError("snippet not found exactly once: %r" % (old,))
            text = text.replace(old, new)
        exec(compile(text, PATH, "exec"), plan_ask.__dict__)
    return apply


# ---- code mutants -------------------------------------------------------

CODE_MUTANTS = [
    ("act ignores missing plan_changing facts", code(
        ("            if missing:\n                return _record(task_id, REJECT,",
         "            if False:\n                return _record(task_id, REJECT,"))),
    ("an ask counts as an answer", code(
        ("        if kind == ANSWER:\n            known.add(fact_id)",
         "        if kind in (ANSWER, ASK):\n            known.add(fact_id)"))),
    ("inert answers satisfy the plan", code(
        ("            missing = tuple(f for f in required if f not in known)\n            if missing:",
         "            missing = () if known else tuple(f for f in required if f not in known)\n            if missing:"))),
    ("inert facts also required", code(
        ("if label == PLAN_CHANGING)", "if label in LABELS)"))),
    ("dispatch on timeout (expiry returns ACT)", code(
        ("return _record(task_id, on_expiry, EXPIRED,", "return _record(task_id, ACT, EXPIRED,"))),
    ("expiry returns caller on_expiry object", code(
        ("return _record(task_id, on_expiry, EXPIRED,", "return _record(task_id, task[\"on_expiry\"], EXPIRED,"))),
    ("expiry always HOLD", code(
        ("return _record(task_id, on_expiry, EXPIRED,", "return _record(task_id, HOLD, EXPIRED,"))),
    ("missing on_expiry defaults to HOLD", code(
        ("    if \"on_expiry\" not in task:\n        raise _Bad(D_ON_EXPIRY_MISSING)\n    on_expiry = _canonical(task[\"on_expiry\"], ON_EXPIRY_VALUES)",
         "    on_expiry = _canonical(task.get(\"on_expiry\", HOLD), ON_EXPIRY_VALUES)"))),
    ("missing on_expiry reported as invalid", code(
        ("        raise _Bad(D_ON_EXPIRY_MISSING)", "        raise _Bad(D_ON_EXPIRY_INVALID)"))),
    ("ACT accepted as on_expiry", code(
        ("ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY)\n", "ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY, ACT)\n"))),
    ("isinstance(str) instead of exact type", code(
        ("    return type(value) is str\n", "    return isinstance(value, str)\n"))),
    ("isinstance(int) instead of exact type", code(
        ("    return type(value) is int\n", "    return isinstance(value, int)\n"))),
    ("canonical match without type check", code(
        ("    if not _is_str(value):\n        return None\n    for choice", "    for choice"))),
    ("dict subclass accepted", code(
        ("    if type(mapping) is not dict:\n        raise _Bad(detail)",
         "    if not isinstance(mapping, dict):\n        raise _Bad(detail)"))),
    ("list subclass or tuple trace accepted", code(
        ("    if type(trace) is not list:", "    if not isinstance(trace, (list, tuple)):"))),
    ("late answers counted (t > deadline)", code(
        ("        if t >= deadline:\n", "        if t > deadline:\n"))),
    ("late acts executed", code(
        ("        if t >= deadline:\n            # The deadline has passed: late answers and late acts do not count.\n            break\n",
         "        if t >= deadline and kind != ACT_EVENT:\n            continue\n"))),
    ("expiry only strictly after deadline", code(
        ("    if now >= deadline:\n", "    if now > deadline:\n"))),
    ("unlabeled fact treated as inert", code(
        ("            label = None\n", "            label = INERT\n"))),
    ("unlabeled fact reported as config_error", code(
        ("return _record(task_id, REJECT, ON_UNMEASURED, D_UNLABELED,",
         "return _record(task_id, REJECT, CONFIG_ERROR, D_UNLABELED,"))),
    ("unknown label accepted as inert", code(
        ("            if label is None:\n                raise _Bad(D_LABEL)",
         "            if label is None:\n                label = INERT"))),
    ("decide without try/except", code(
        ("        return _decide(task, trace, now)\n    except Exception:",
         "        return _decide(task, trace, now)\n    except ZeroDivisionError:"))),
    ("non-positive deadline accepted", code(
        ("    if not _is_int(deadline) or deadline <= 0:", "    if not _is_int(deadline):"))),
    ("events after now accepted", code(
        ("t < last_t or t > now:", "t < last_t:"))),
    ("time going backwards accepted", code(
        ("t < last_t or t > now:", "t < 0 or t > now:"))),
    ("answer without ask accepted", code(
        ("        if kind == ANSWER and fact_id not in asked:\n            raise _Bad(D_TRACE)\n", ""))),
    ("events after act accepted", code(
        ("            if \"fact\" in event or i != len(trace) - 1:", "            if \"fact\" in event:"))),
    ("unknown fact id accepted", code(
        ("        if not _is_str(fact_id) or fact_id not in labels:", "        if not _is_str(fact_id):"))),
    ("fact text not checked", code(
        ("        if \"text\" not in fact or not _is_str(fact[\"text\"]) or not fact[\"text\"]:\n            raise _Bad(D_FACT)\n", ""))),
    ("unknown task field accepted", code(
        ("    _check_keys(task, TASK_FIELDS, D_TASK)\n", "    _check_keys(task, TASK_FIELDS + (\"extra\",), D_TASK)\n"))),
    ("missing list not reported on reject", code(
        ("return _record(task_id, REJECT, MISSING_PLAN_CHANGING, None,\n                               missing, on_expiry)",
         "return _record(task_id, REJECT, MISSING_PLAN_CHANGING, None,\n                               (), on_expiry)"))),
    ("WAIT reported as ACT before deadline", code(
        ("    return _record(task_id, WAIT, AWAITING,", "    return _record(task_id, ACT, AWAITING,"))),
    ("optimality claims a solved plan", code(
        ("    \"\"\"No solver here: optimality of any plan is not measured.\"\"\"\n    return ON_UNMEASURED",
         "    \"\"\"No solver here: optimality of any plan is not measured.\"\"\"\n    return \"optimal\""))),
    # r2 fixes
    ("F1 early task_id read before validation (r1 code)", code(
        ("    try:\n        task_id, labels, deadline, on_expiry = validate_task(task)\n    except _Bad as bad:\n        return _record(None, REJECT, CONFIG_ERROR, bad.detail)",
         "    rid = None\n    if type(task) is dict:\n        candidate = task.get(\"task_id\")\n        if _is_str(candidate) and candidate:\n            rid = candidate\n"
         "    try:\n        task_id, labels, deadline, on_expiry = validate_task(task)\n    except _Bad as bad:\n        return _record(rid, REJECT, CONFIG_ERROR, bad.detail)"))),
    ("F1 bare early read (value unused)", code(
        ("    try:\n        task_id, labels, deadline, on_expiry = validate_task(task)\n",
         "    if type(task) is dict:\n        task.get(\"task_id\")\n    try:\n        task_id, labels, deadline, on_expiry = validate_task(task)\n"))),
    ("F3 config_error echoes a looked-up task_id", code(
        ("        return _record(None, REJECT, CONFIG_ERROR, bad.detail)",
         "        return _record(task.get(\"task_id\") if type(task) is dict else None, REJECT, CONFIG_ERROR, bad.detail)"))),
    ("F3 trace error drops the validated task_id", code(
        ("        return _record(task_id, REJECT, CONFIG_ERROR, bad.detail)",
         "        return _record(None, REJECT, CONFIG_ERROR, bad.detail)"))),
    ("F2 fallback record built by a call", code(
        ("        return {\"task_id\": None, \"decision\": REJECT, \"reason\": CONFIG_ERROR,\n                \"detail\": D_INTERNAL, \"missing\": (), \"on_expiry\": None}",
         "        return _record(None, REJECT, CONFIG_ERROR, D_INTERNAL)"))),
    ("F2 fallback echoes nothing safe (caller task)", code(
        ("        return {\"task_id\": None, \"decision\": REJECT,",
         "        return {\"task_id\": task, \"decision\": REJECT,"))),
    ("F1 fact ids looked up before all are type-checked (r1 code)", code(
        ("    # First pass: every fact id is an exact, non-empty str before any lookup.\n    for fact_id in facts:\n        if not _is_str(fact_id) or not fact_id:\n            raise _Bad(D_FACT)\n    labels = {}\n    for fact_id in facts:\n        fact = facts[fact_id]",
         "    labels = {}\n    for fact_id in facts:\n        if not _is_str(fact_id) or not fact_id:\n            raise _Bad(D_FACT)\n        fact = facts[fact_id]"))),
    ("F4 missing order follows insertion (sorted -> list)", code(
        ("    required = sorted(f for f, label in labels.items() if label == PLAN_CHANGING)",
         "    required = list(f for f, label in labels.items() if label == PLAN_CHANGING)"))),
]


# ---- world / fixture mutants -------------------------------------------

def _set_tasks(tasks):
    fixtures.TASKS[:] = tasks


def w_swap_labels():
    tasks = copy.deepcopy(TASKS_ORIG)
    f = tasks[0]["facts"]
    f["d_licence"]["label"], f["d_paint"]["label"] = "inert", "plan_changing"
    _set_tasks(tasks)


def w_drop_plan_changing_fact():
    tasks = copy.deepcopy(TASKS_ORIG)
    del tasks[1]["facts"]["n_leave"]
    _set_tasks(tasks)


def w_drop_inert_fact():
    tasks = copy.deepcopy(TASKS_ORIG)
    del tasks[2]["facts"]["r_colour"]
    _set_tasks(tasks)


def w_on_expiry_removed():
    tasks = copy.deepcopy(TASKS_ORIG)
    del tasks[0]["on_expiry"]
    _set_tasks(tasks)


def w_on_expiry_changed():
    tasks = copy.deepcopy(TASKS_ORIG)
    tasks[2]["on_expiry"] = "HOLD"
    _set_tasks(tasks)


def w_duplicate_task_ids():
    tasks = copy.deepcopy(TASKS_ORIG)
    tasks[2]["task_id"] = "drivers"
    _set_tasks(tasks)


def w_deadline_shortened():
    tasks = copy.deepcopy(TASKS_ORIG)
    tasks[1]["deadline"] = 3
    _set_tasks(tasks)


def w_label_dropped():
    tasks = copy.deepcopy(TASKS_ORIG)
    del tasks[0]["facts"]["d_paint"]["label"]
    _set_tasks(tasks)


def _wrap_script(change):
    orig = FIX_SNAPSHOT["script"]

    def script(task, strategy):
        trace, now = orig(task, strategy)
        return change(task, strategy, trace, now)
    fixtures.script = script


def w_operator_silent_everywhere():
    _wrap_script(lambda task, s, trace, now:
                 ([e for e in trace if e["kind"] != "answer"], now))


def w_operator_answers_late():
    def change(task, s, trace, now):
        if s != "plan_changing_then_act":
            return trace, now
        d = task["deadline"]
        out = [dict(e, t=d) if e["kind"] == "answer" else e for e in trace]
        out[-1] = dict(out[-1], t=d + 1)
        return out, d + 1
    _wrap_script(change)


def w_operator_answers_inert_for_plan_changing():
    def change(task, s, trace, now):
        inert = sorted(f for f, v in task["facts"].items() if v["label"] == "inert")
        out = [dict(e, fact=inert[0]) if e["kind"] in ("ask", "answer") else e for e in trace]
        return out, now
    _wrap_script(change)


def w_clock_frozen_before_deadline():
    def change(task, s, trace, now):
        if s == "silent_operator":
            return trace, task["deadline"] - 1
        return trace, now
    _wrap_script(change)


def w_nurses_deadline_raised():
    tasks = copy.deepcopy(TASKS_ORIG)
    tasks[1]["deadline"] = 100
    _set_tasks(tasks)


def w_room_deadline_lowered():
    tasks = copy.deepcopy(TASKS_ORIG)
    tasks[2]["deadline"] = 5
    _set_tasks(tasks)


def w_operator_answers_at_ask_time():
    def change(task, s, trace, now):
        return [dict(e, t=e["t"] - 1) if e["kind"] == "answer" and e["t"] > 0 else e
                for e in trace], now
    _wrap_script(change)


def w_tasks_shared_not_copied():
    fixtures.tasks = lambda: fixtures.TASKS


WORLD_MUTANTS = [
    ("labels swapped in one task", w_swap_labels),
    ("one plan_changing fact dropped", w_drop_plan_changing_fact),
    ("one inert fact dropped", w_drop_inert_fact),
    ("on_expiry removed from one task", w_on_expiry_removed),
    ("on_expiry changed in one task", w_on_expiry_changed),
    ("duplicate task ids", w_duplicate_task_ids),
    ("deadline shortened in one task", w_deadline_shortened),
    ("one fact label dropped", w_label_dropped),
    ("operator never answers", w_operator_silent_everywhere),
    ("operator answers after the deadline", w_operator_answers_late),
    ("operator answers an inert fact instead", w_operator_answers_inert_for_plan_changing),
    ("clock stopped before the deadline", w_clock_frozen_before_deadline),
    ("nurses deadline raised to 100 (r2 F5)", w_nurses_deadline_raised),
    ("room deadline lowered to 5 (r2 F5)", w_room_deadline_lowered),
    ("operator answers at ask time (r2 F5)", w_operator_answers_at_ask_time),
    ("tasks() returns shared state", w_tasks_shared_not_copied),
]

MUTANTS = [("code", n, a) for n, a in CODE_MUTANTS] + [("world", n, a) for n, a in WORLD_MUTANTS]


def restore():
    for name in [n for n in vars(plan_ask) if n not in SNAPSHOT]:
        delattr(plan_ask, name)
    plan_ask.__dict__.update(SNAPSHOT)
    fixtures.__dict__.update(FIX_SNAPSHOT)
    fixtures.TASKS[:] = copy.deepcopy(TASKS_ORIG)


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_plan_ask)
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
            print("%-5s %-48s BROKEN   (%s)" % (kind, name, type(exc).__name__))
            continue
        finally:
            restore()
        status = "KILLED" if bad else "SURVIVED"
        killed[kind] += 1 if bad else 0
        print("%-5s %-48s %-8s (%d/%d tests failing)" % (kind, name, status, bad, ran))
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
