"""Targeted mutants, applied in memory only; no file on disk is edited.

Each mutated source replaces one module (annal_diff or this runner) inside a
child `python3 -B` that runs test_annal_diff. Verdicts, counted separately:
KILLED-behaviour (a test assertion failed), CRASH (load failure, or test errors
only; not a kill), TIMEOUT (on_expiry DENY; not a kill), SURVIVED. Exit 0 only
when every mutant is KILLED-behaviour. A crash or timeout is never a kill.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}
LOAD_FAILED = 97

MUTANTS = [
    ("pair_ambiguous_leftovers", "annal_diff",
     "        if len(olds) == 1 and len(news) == 1:\n",
     "        if True:\n"),
    ("ignore_level", "annal_diff",
     "            if hashes != 2:\n",
     "            if hashes < 1:\n"),
    ("timeout_counts_as_kill", "mutants",
     "    if timed_out:\n        return \"TIMEOUT\"\n",
     "    if timed_out:\n        return \"KILLED-behaviour\"\n"),
    ("leftover_singleton_only", "annal_diff",
     "        if len(olds) == 1 and len(news) == 1:\n",
     "        if len(olds) == 1 and len(news) == 1 and len(left_old) == 1 and len(left_new) == 1:\n"),
    ("no_rename_class", "annal_diff",
     "    for body in sorted(old_body):\n",
     "    for body in sorted(old_body)[:0]:\n"),
    ("ignore_id", "annal_diff",
     "        if e.ident is None:\n            continue\n        j = new_by_id.get(e.ident)\n",
     "        if True:\n            continue\n        j = new_by_id.get(e.ident)\n"),
    ("body_and_heading_is_rename", "annal_diff",
     "        kind = \"edited\"  # heading and body both changed under one id\n",
     "        kind = \"renamed\"  # heading and body both changed under one id\n"),
    ("moved_as_removed_added", "annal_diff",
     "        rows.append(_pair_by_id(e, new[j]))\n",
     "        if e.path != new[j].path:\n            continue\n        rows.append(_pair_by_id(e, new[j]))\n"),
    ("duplicate_heading_check_off", "annal_diff",
     "        if len(group) > 1 and any(e.ident is None for e in group):\n",
     "        if False:\n"),
    ("pair_distinct_ids", "annal_diff",
     "    return not (o.ident is not None and n.ident is not None)\n",
     "    return True\n"),
    ("empty_body_paired", "annal_diff",
     "    return body != \"\"\n",
     "    return True\n"),
    ("pin_check_off", "annal_diff",
     "        if len(data) != size or hashlib.sha256(data).hexdigest() != sha:\n",
     "        if len(data) != size:\n"),
    ("size_cap_off", "annal_diff",
     "    if len(data) > MAX_FILE_BYTES:\n        raise Deny(\"too_large\"",
     "    if len(data) > MAX_FILE_BYTES * 4:\n        raise Deny(\"too_large\""),
    ("entry_cap_off", "annal_diff",
     "            if len(chunks) > MAX_ENTRIES_PER_FILE:\n",
     "            if len(chunks) > MAX_ENTRIES_PER_FILE + 1:\n"),
    ("depth_cap_off", "annal_diff",
     "                if depth + 1 > MAX_DEPTH:\n",
     "                if depth + 1 > MAX_DEPTH * 100:\n"),
    ("crash_counts_as_kill", "mutants",
     "    if proc_rc == LOAD_FAILED:\n        return \"CRASH\"\n",
     "    if proc_rc == LOAD_FAILED:\n        return \"KILLED-behaviour\"\n"),
]

RUNNER = r"""
import io, json, sys, types, unittest
target, path = sys.argv[1], sys.argv[2]
src = sys.stdin.read()
try:
    mod = types.ModuleType(target)
    mod.__file__ = path
    sys.modules[target] = mod
    exec(compile(src, target + "_mutant", "exec"), mod.__dict__)
    import test_annal_diff
except (SyntaxError, ImportError, NameError, AttributeError, TypeError, ValueError, KeyError, IndexError):
    sys.exit(97)
res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
    unittest.defaultTestLoader.loadTestsFromModule(test_annal_diff))
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
    if not isinstance(data, dict):
        return "CRASH"
    if data.get("failures", 0) > 0:
        return "KILLED-behaviour"
    if data.get("errors", 0) > 0:
        return "CRASH"
    return "SURVIVED"


def run_source(source, target="annal_diff", timeout=None):
    """Run one in-memory source for `target` through the child test runner."""
    if timeout is None:
        timeout = TIMEOUT["seconds"]
    try:
        proc = subprocess.run(
            [sys.executable, "-B", "-c", RUNNER, target, os.path.join(HERE, target + ".py")],
            input=source, capture_output=True, text=True, cwd=HERE, timeout=timeout,
        )
        return proc.returncode, proc.stdout, False
    except subprocess.TimeoutExpired:
        return None, "", True


def main():
    sources = {}
    for target in ("annal_diff", "mutants"):
        with open(os.path.join(HERE, target + ".py"), encoding="utf-8") as fh:
            sources[target] = fh.read()
    rc, stdout, timed_out = run_source(sources["annal_diff"], "annal_diff", TIMEOUT["seconds"])
    if classify(rc, stdout, timed_out) != "SURVIVED":
        sys.stderr.write("DENY baseline: unmutated suite does not pass (on_expiry=%s)\n" % TIMEOUT["on_expiry"])
        return 2
    verdicts = []
    for name, target, old, new in MUTANTS:
        if sources[target].count(old) != 1:
            sys.stderr.write("DENY fragment: mutant %s fragment is not unique in %s.py\n" % (name, target))
            return 2
        rc, stdout, timed_out = run_source(sources[target].replace(old, new), target, TIMEOUT["seconds"])
        verdict = classify(rc, stdout, timed_out)
        verdicts.append(verdict)
        if timed_out:
            detail = "timeout %ds, on_expiry %s" % (TIMEOUT["seconds"], TIMEOUT["on_expiry"])
        else:
            detail = stdout.strip().splitlines()[-1] if stdout.strip() else "rc %s" % rc
        print("%-17s %-28s %s" % (verdict, name, detail))
    counts = tally(verdicts)
    print("killed-behaviour %d / crash %d / timeout %d / survived %d (of %d)" % (
        counts["KILLED-behaviour"], counts["CRASH"], counts["TIMEOUT"], counts["SURVIVED"], len(MUTANTS)))
    return 0 if counts["KILLED-behaviour"] == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
