"""Targeted mutants, applied in memory only; ownership.py on disk is not edited.
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
    ("arm B fails any cowrite session by mode label",
     'def arm_b(measured, min_num, min_den):\n'
     '    human, total = _ownership_parts(measured)\n',
     'def arm_b(measured, min_num, min_den):\n'
     '    if measured["mode"] == "cowrite":\n'
     '        return "FAIL"\n'
     '    human, total = _ownership_parts(measured)\n'),
    ("arm B fails any session with a surviving AI span",
     'def arm_b(measured, min_num, min_den):\n'
     '    human, total = _ownership_parts(measured)\n',
     'def arm_b(measured, min_num, min_den):\n'
     '    if measured["ai_chars"] > 0:\n'
     '        return "FAIL"\n'
     '    human, total = _ownership_parts(measured)\n'),
    ("arm B uses cumulative accepted AI chars instead of surviving spans",
     '    return measured["human_chars"], measured["total_chars"]\n',
     '    human = measured["inserted_human_chars"]\n'
     '    return human, human + measured["accepted_ai_chars"]\n'),
    ("arm B ignores the ownership threshold",
     '    if human * min_den >= min_num * total:\n'
     '        return "PASS"\n'
     '    return "FAIL"\n',
     '    return "PASS"\n'),
    ("harness accepts a self-reported ownership or help field",
     '                raise Deny("self_reported_measure",\n'
     '                           "%s declares %s; the harness measures this itself" % (where, key))',
     '                continue'),
    ("arm B uses a strict bound instead of inclusive on min_ownership",
     '    if human * min_den >= min_num * total:\n',
     '    if human * min_den > min_num * total:\n'),
]

RUNNER = r"""
import io, json, sys, types, unittest
src = sys.stdin.read()
try:
    mod = types.ModuleType("ownership")
    mod.__file__ = sys.argv[1]
    sys.modules["ownership"] = mod
    exec(compile(src, "ownership_mutant", "exec"), mod.__dict__)
    import test_ownership
except Exception:
    sys.exit(97)
res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
    unittest.defaultTestLoader.loadTestsFromModule(test_ownership))
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
            [sys.executable, "-B", "-c", RUNNER, os.path.join(HERE, "ownership.py")],
            input=source, capture_output=True, text=True, cwd=HERE,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, False
    except subprocess.TimeoutExpired:
        return None, "", True


def main():
    with open(os.path.join(HERE, "ownership.py"), encoding="utf-8") as fh:
        source = fh.read()
    verdicts = []
    for name, old, new in MUTANTS:
        if source.count(old) != 1:
            sys.stderr.write("DENY fragment: mutant %r fragment is not unique in ownership.py\n" % name)
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
