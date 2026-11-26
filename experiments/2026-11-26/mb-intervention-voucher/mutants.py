"""Targeted mutants, applied in memory only; voucher.py on disk is never changed.
Each mutated source runs the test suite in a child `python3 -B`. Classes, counted separately:
KILLED-behaviour (a test assertion failed), CRASH (load failure or errors only; not a kill),
TIMEOUT (on_expiry DENY; not a kill), SURVIVED. Exit 0 only when every mutant is KILLED-behaviour."""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}

MUTANTS = [
    ("arm B skips the named-record check",
     '    if report["applied_to"] != q["record"]:\n        return "FAIL", "change applied',
     '    if False:\n        return "FAIL", "change applied'),
    ("arm B checks only the answer value, not target or operator",
     '    if report["applied_to"] != q["record"]:\n'
     '        return "FAIL", "change applied to %s, not the named record %s" % (report["applied_to"], q["record"])\n'
     '    if report["op"] != q["op"]:\n'
     '        return "FAIL", "operator %s, not the asked %s" % (report["op"], q["op"])\n',
     ''),
    ("null control always passes (identity checked before the report)",
     '    if report["applied_to"] != q["record"]:\n        return "FAIL", "change applied',
     '    if apply_op(fx["records"][q["record"]], q["op"], q["amount"]) == fx["records"][q["record"]]:\n'
     '        return "NO_INTERVENTION", "early"\n'
     '    if report["applied_to"] != q["record"]:\n        return "FAIL", "change applied'),
    ("pass rule off by one (one FAIL tolerated)",
     '    return "PASS" if fails == 0 and vouched > 0 else "FAIL"',
     '    return "PASS" if fails <= 1 and vouched > 0 else "FAIL"'),
    ("identity what-if counted as a trusted answer",
     '        return "NO_INTERVENTION", "the asked change leaves the start value unchanged"',
     '        return "VOUCHED", "the asked change leaves the start value unchanged"'),
]

RUNNER = r"""
import io, json, sys, types, unittest
src = sys.stdin.read()
try:
    mod = types.ModuleType("voucher")
    mod.__file__ = sys.argv[1]
    sys.modules["voucher"] = mod
    exec(compile(src, "voucher_mutant", "exec"), mod.__dict__)
    import test_voucher
except Exception:
    sys.exit(97)
res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
    unittest.defaultTestLoader.loadTestsFromModule(test_voucher))
print(json.dumps({"failures": len(res.failures), "errors": len(res.errors),
                  "failed": sorted(t.id().rsplit(".", 1)[1] for t, _ in res.failures),
                  "errored": sorted(t.id().rsplit(".", 1)[1] for t, _ in res.errors)}))
"""


def classify(proc_rc, stdout, timed_out):
    if timed_out:
        return "TIMEOUT"
    if proc_rc == 97:
        return "CRASH"
    try:
        data = json.loads(stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return "CRASH"
    if data["failures"] > 0:
        return "KILLED-behaviour"
    if data["errors"] > 0:
        return "CRASH"
    return "SURVIVED"


def main():
    with open(os.path.join(HERE, "voucher.py"), encoding="utf-8") as fh:
        source = fh.read()
    counts = {"KILLED-behaviour": 0, "CRASH": 0, "TIMEOUT": 0, "SURVIVED": 0}
    for name, old, new in MUTANTS:
        if source.count(old) != 1:
            sys.stderr.write("DENY fragment: mutant %r fragment is not unique in voucher.py\n" % name)
            return 2
        try:
            proc = subprocess.run([sys.executable, "-B", "-c", RUNNER, os.path.join(HERE, "voucher.py")],
                                  input=source.replace(old, new), capture_output=True, text=True, cwd=HERE,
                                  timeout=TIMEOUT["seconds"])
            verdict = classify(proc.returncode, proc.stdout, False)
            detail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
        except subprocess.TimeoutExpired:
            verdict = classify(None, "", True)
            detail = "timeout %ds, on_expiry %s" % (TIMEOUT["seconds"], TIMEOUT["on_expiry"])
        counts[verdict] += 1
        print("%-17s %s %s" % (verdict, name, detail))
    print("killed-behaviour %d / crash %d / timeout %d / survived %d (of %d)" % (
        counts["KILLED-behaviour"], counts["CRASH"], counts["TIMEOUT"], counts["SURVIVED"], len(MUTANTS)))
    return 0 if counts["KILLED-behaviour"] == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
