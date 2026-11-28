"""Targeted mutants, applied in memory only; forecast_gate.py on disk is not edited.
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
    ("b_reads_post_t",
     "    a_hit = _strong_hits(case[\"events\"], cutoff, True) > 0\n"
     "    b_hit = _strong_hits(case[\"events\"], cutoff, False) > 0\n",
     "    a_hit = _strong_hits(case[\"events\"], cutoff, True) > 0\n"
     "    b_hit = _strong_hits(case[\"events\"], cutoff, True) > 0\n"),
    ("outcome_at_t_scored",
     "    if not (outcome[\"day\"] > cutoff):\n",
     "    if not (outcome[\"day\"] >= cutoff):\n"),
    ("clean_flagged_as_leak",
     "    if b_hit:\n"
     "        klass = \"forecast\"\n",
     "    if b_hit:\n"
     "        klass = \"recall_not_forecast\"\n"),
    ("date_compare_as_string",
     "    return day <= cutoff\n",
     "    return raw.replace(\"-\", \"\") <= cutoff.isoformat()\n"),
    ("gate_ignores_arm_b",
     "            observed[\"arm_a\"] == want[\"arm_a\"]\n"
     "            and observed[\"arm_b\"] == want[\"arm_b\"]\n"
     "            and observed[\"class\"] == want[\"class\"]\n",
     "            observed[\"arm_a\"] == want[\"arm_a\"]\n"
     "            and observed[\"class\"] == want[\"class\"]\n"),
    ("b_window_t_plus_1",
     "    return day <= cutoff\n",
     "    return day.toordinal() <= cutoff.toordinal() + 1\n"),
    ("gate_ignores_class",
     "            and observed[\"arm_b\"] == want[\"arm_b\"]\n"
     "            and observed[\"class\"] == want[\"class\"]\n",
     "            and observed[\"arm_b\"] == want[\"arm_b\"]\n"),
    ("duplicate_name_check_off",
     "        if name in names:\n",
     "        if False:\n"),
    ("depth_cap_disabled",
     "        if depth > MAX_DEPTH:\n"
     "            raise Deny(\"too_deep\", \"%s nests deeper than %d levels\" % (where, MAX_DEPTH))\n",
     "        if depth > MAX_DEPTH * 1000:\n"
     "            raise Deny(\"too_deep\", \"%s nests deeper than %d levels\" % (where, MAX_DEPTH))\n"),
]

RUNNER = r"""
import io, json, sys, types, unittest
src = sys.stdin.read()
try:
    mod = types.ModuleType("forecast_gate")
    mod.__file__ = sys.argv[1]
    sys.modules["forecast_gate"] = mod
    exec(compile(src, "forecast_gate_mutant", "exec"), mod.__dict__)
    import test_forecast_gate
except Exception:
    sys.exit(97)
res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
    unittest.defaultTestLoader.loadTestsFromModule(test_forecast_gate))
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
            [sys.executable, "-B", "-c", RUNNER, os.path.join(HERE, "forecast_gate.py")],
            input=source, capture_output=True, text=True, cwd=HERE,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, False
    except subprocess.TimeoutExpired:
        return None, "", True


def main():
    with open(os.path.join(HERE, "forecast_gate.py"), encoding="utf-8") as fh:
        source = fh.read()
    verdicts = []
    for name, old, new in MUTANTS:
        if source.count(old) != 1:
            sys.stderr.write("DENY fragment: mutant %r fragment is not unique in forecast_gate.py\n" % name)
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
