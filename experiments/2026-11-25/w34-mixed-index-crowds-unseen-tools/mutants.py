"""Small targeted mutants (VERDICT C4), applied in memory only; the source file on disk is never changed.
Each mutated source runs the test suite in a child `python3 -B`. Classes: KILLED-behaviour (a test failure),
CRASH (load failure or errors only; counted apart, not a kill), TIMEOUT (on_expiry DENY; not a kill), SURVIVED.
Exit 0 only when every mutant is KILLED-behaviour."""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TIMEOUT_S = 120
ON_EXPIRY = "DENY"

MUTANTS = [
    ("C4-1 arm B secretly reads the mixed list",
     '    return [tool for score, kind, item_id, tool in ranked(query_text, catalog, [], False)[:k]]',
     '    return arm_mixed(query_text, catalog, experience, k)'),
    ("C4-2 arm A without distinct-tool dedupe",
     '        if tool not in out:\n            out.append(tool)\n        if len(out) == k:\n            break',
     '        out.append(tool)\n        if len(out) == k:\n            break'),
    ("C4-3 leaky pool declared heldout passes",
     '            if p["split"] == "heldout":\n                if it["gold_tool_id"] in heldout:',
     '            if False:\n                if it["gold_tool_id"] in heldout:'),
    ("L4 kind order swapped (experience before description on ties)",
     'KIND_ORDER = {"description": 0, "experience": 1}',
     'KIND_ORDER = {"description": 1, "experience": 0}'),
    ("C3 flip rule off by one (> k)",
     '        if predicted is None and len(outrank) >= k:',
     '        if predicted is None and len(outrank) > k:'),
]

RUNNER = r"""
import io, json, sys, types, unittest
src = sys.stdin.read()
try:
    mod = types.ModuleType("crowding")
    mod.__file__ = sys.argv[1]
    sys.modules["crowding"] = mod
    exec(compile(src, "crowding_mutant", "exec"), mod.__dict__)
    import test_crowding
except Exception:
    sys.exit(97)
res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
    unittest.defaultTestLoader.loadTestsFromModule(test_crowding))
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
    with open(os.path.join(HERE, "crowding.py"), encoding="utf-8") as fh:
        source = fh.read()
    counts = {"KILLED-behaviour": 0, "CRASH": 0, "TIMEOUT": 0, "SURVIVED": 0}
    for name, old, new in MUTANTS:
        if source.count(old) != 1:
            sys.stderr.write("DENY fragment: mutant %r fragment is not unique in crowding.py\n" % name)
            return 2
        try:
            proc = subprocess.run([sys.executable, "-B", "-c", RUNNER, os.path.join(HERE, "crowding.py")],
                                  input=source.replace(old, new), capture_output=True, text=True, cwd=HERE,
                                  timeout=TIMEOUT_S)
            verdict = classify(proc.returncode, proc.stdout, False)
            detail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
        except subprocess.TimeoutExpired:
            verdict, detail = classify(None, "", True), "timeout %ds, on_expiry %s" % (TIMEOUT_S, ON_EXPIRY)
        counts[verdict] += 1
        print("%-17s %s %s" % (verdict, name, detail))
    print("killed-behaviour %d / crash %d / timeout %d / survived %d (of %d)" % (
        counts["KILLED-behaviour"], counts["CRASH"], counts["TIMEOUT"], counts["SURVIVED"], len(MUTANTS)))
    return 0 if counts["KILLED-behaviour"] == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
