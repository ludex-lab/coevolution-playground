"""Targeted mutants, applied in memory only; stopwatch.py on disk is not edited.
Each mutated source runs the test suite in a child `python3 -B`. Classes, counted separately:
KILLED-behaviour (a test assertion failed), CRASH (load failure or errors only; not a kill),
TIMEOUT (on_expiry DENY; not a kill), SURVIVED. Exit 0 only when every mutant is KILLED-behaviour.
A crash or timeout is never counted as killed.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}
LOAD_FAILED = 97

MUTANTS = [
    ("arm B ignores the digest",
     '    if after["digest"] != before["digest"]:\n        return "FAIL"',
     '    if False and after["digest"] != before["digest"]:\n        return "FAIL"'),
    ("arm B ignores the counter",
     '    delta = _delta(before["counters"], after["counters"], claim["mechanism"], claim["direction"])\n'
     '    if delta is None or delta <= 0:\n'
     '        return "FAIL"\n'
     '    if (before["cost"] - after["cost"]) > delta * claim["saving_per_unit"]:\n'
     '        return "FAIL"\n'
     '    return "PASS"',
     '    return "PASS"'),
    ("cost tie counts as faster",
     '    return "PASS" if after_cost < before_cost else "FAIL"',
     '    return "PASS" if after_cost <= before_cost else "FAIL"'),
    ("harness accepts a self-reported counter",
     '    for key in ("cost", "counters"):\n'
     '        if key in item:\n'
     '            raise Deny("self_reported_measure",\n'
     '                       "%s declares %s; the harness measures this itself" % (where, key))',
     '    for key in ("cost", "counters"):\n'
     '        if key in item:\n'
     '            item = dict(item)\n'
     '            del item[key]'),
    ("digest is taken over one input set only",
     '    blob = json.dumps(outputs, sort_keys=True, separators=(",", ":"))',
     '    blob = json.dumps(outputs[:1], sort_keys=True, separators=(",", ":"))'),
    ("arm B ignores the attribution bound",
     '    if (before["cost"] - after["cost"]) > delta * claim["saving_per_unit"]:\n        return "FAIL"',
     '    if False and (before["cost"] - after["cost"]) > delta * claim["saving_per_unit"]:\n        return "FAIL"'),
]

RUNNER = r"""
import io, json, sys, types, unittest
src = sys.stdin.read()
try:
    mod = types.ModuleType("stopwatch")
    mod.__file__ = sys.argv[1]
    sys.modules["stopwatch"] = mod
    exec(compile(src, "stopwatch_mutant", "exec"), mod.__dict__)
    import test_stopwatch
except Exception:
    sys.exit(97)
res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
    unittest.defaultTestLoader.loadTestsFromModule(test_stopwatch))
print(json.dumps({"failures": len(res.failures), "errors": len(res.errors),
                  "failed": sorted(t.id().rsplit(".", 1)[1] for t, _ in res.failures),
                  "errored": sorted(t.id().rsplit(".", 1)[1] for t, _ in res.errors)}))
"""


def is_killed(verdict):
    return verdict == "KILLED-behaviour"


def tally(verdicts):
    counts = {"KILLED-behaviour": 0, "CRASH": 0, "TIMEOUT": 0, "SURVIVED": 0}
    for verdict in verdicts:
        counts[verdict] += 1
    return counts


def classify(proc_rc, stdout, timed_out):
    if timed_out:
        return "TIMEOUT"
    if proc_rc == LOAD_FAILED:
        return "CRASH"
    try:
        data = json.loads(stdout.strip().splitlines()[-1])
    except (ValueError, IndexError, AttributeError):
        return "CRASH"
    if data.get("failures", 0) > 0:
        return "KILLED-behaviour"
    if data.get("errors", 0) > 0:
        return "CRASH"
    return "SURVIVED"


def run_source(source, timeout=None):
    """Run one in-memory source through the child test runner. on_expiry is DENY."""
    if timeout is None:
        timeout = TIMEOUT["seconds"]
    try:
        proc = subprocess.run(
            [sys.executable, "-B", "-c", RUNNER, os.path.join(HERE, "stopwatch.py")],
            input=source, capture_output=True, text=True, cwd=HERE,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, False
    except subprocess.TimeoutExpired:
        return None, "", True


def main():
    with open(os.path.join(HERE, "stopwatch.py"), encoding="utf-8") as fh:
        source = fh.read()
    verdicts = []
    for name, old, new in MUTANTS:
        if source.count(old) != 1:
            sys.stderr.write("DENY fragment: mutant %r fragment is not unique in stopwatch.py\n" % name)
            return 2
        rc, stdout, timed_out = run_source(source.replace(old, new), timeout=TIMEOUT["seconds"])
        verdict = classify(rc, stdout, timed_out)
        verdicts.append(verdict)
        if timed_out:
            detail = "timeout %ds, on_expiry %s" % (TIMEOUT["seconds"], TIMEOUT["on_expiry"])
        else:
            detail = stdout.strip().splitlines()[-1] if stdout.strip() else ""
        print("%-17s %s %s" % (verdict, name, detail))
    counts = tally(verdicts)
    print("killed-behaviour %d / crash %d / timeout %d / survived %d (of %d)" % (
        counts["KILLED-behaviour"], counts["CRASH"], counts["TIMEOUT"], counts["SURVIVED"], len(MUTANTS)))
    return 0 if counts["KILLED-behaviour"] == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
