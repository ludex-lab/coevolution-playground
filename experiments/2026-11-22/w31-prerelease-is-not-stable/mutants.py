"""Mutation run: break prerelease_gate.py one way at a time and require the unittest suite to fail each time.

Run: python3 -B mutants.py
Each mutant is (name, fragment, replacement); the fragment must occur exactly once in the module.
Each suite run is bounded by TIMEOUT. A run that reaches it has on_expiry DENY: it is reported as TIMEOUT and is
never counted as a kill, so the run fails. Exit 0 only if every mutant is killed by a real test failure.
Work happens in a private temporary folder that this script creates and removes.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}

MUTANTS = [
    # from the pack
    ("pre_release_satisfies_its_normal_range", '    if not a["pre"] and not b["pre"]:\n        return 0',
     '    if not a["pre"] or not b["pre"]:\n        return 0'),
    ("leading_zero_numeric_identifier_passes",
     '            if len(ident) > 1 and ident[0] == "0":\n                raise GateError("leading_zero"',
     '            if False:\n                raise GateError("leading_zero"'),
    # from the range-semantics fix
    ("lexical_compare_of_numeric_identifiers", '        if xn and yn:\n            return -1 if x < y else 1',
     '        if xn and yn:\n            return -1 if str(x) < str(y) else 1'),
    ("numeric_ranked_above_alphanumeric", 'return -1 if xn else 1', 'return 1 if xn else -1'),
    ("shorter_pre_release_set_ranked_higher", 'return (len(a) > len(b)) - (len(a) < len(b))',
     'return (len(a) < len(b)) - (len(a) > len(b))'),
    ("stable_range_filter_removed", '    if cand["pre"]:\n        return {"verdict": VERDICTS[1]',
     '    if False:\n        return {"verdict": VERDICTS[1]'),
    # more precedence
    ("build_metadata_counts", 'ca = (a["major"], a["minor"], a["patch"])', 'ca = (a["major"], a["minor"], a["patch"], a["build"])'),
    ("normal_version_ranked_lower", '    if not a["pre"]:\n        return 1', '    if not a["pre"]:\n        return -1'),
    ("alphanumeric_order_reversed", '            return -1 if xn else 1\n        return -1 if x < y else 1',
     '            return -1 if xn else 1\n        return -1 if x > y else 1'),
    ("core_compared_as_text", '    major, minor, patch = (_numeric(p, where) for p in parts)',
     '    major, minor, patch = (_numeric(p, where) and p for p in parts)'),
    ("equality_treated_as_at_least", 'return order >= 0 if op == ">=" else order == 0', 'return order >= 0'),
    ("weak_arm_retains_the_suffix", 'core = dict(cand, pre=(), build=())', 'core = dict(cand)'),
    ("policy_and_spec_reasons_swapped", 'if cand["pre"] and same_core:', 'if cand["pre"] and not same_core:'),
    # parser
    ("leading_zero_core_passes", '    if len(text) > 1 and text[0] == "0":\n        raise GateError("leading_zero", "%s has a leading zero"',
     '    if False:\n        raise GateError("leading_zero", "%s has a leading zero"'),
    ("empty_identifier_passes", '        if ident == "":\n            raise GateError("empty_identifier"',
     '        if False:\n            raise GateError("empty_identifier"'),
    ("any_identifier_character_passes", 'if any(ch not in IDENT_CHARS for ch in ident):', 'if False:'),
    ("unicode_digits_in_core", 'if text == "" or any(ch not in DIGITS for ch in text):', 'if text == "" or not text.isdigit():'),
    ("two_part_core_passes", 'if len(parts) != 3:', 'if len(parts) not in (2, 3):'),
    ("length_cap_removed", 'if len(text) > CAPS["version_chars"]["limit"]:', 'if False:'),
    ("requirement_suffix_accepted", 'if version["pre"] or version["build"]:', 'if False:'),
    ("any_operator_accepted", 'if sep != " " or op not in OPERATORS:', 'if sep != " ":'),
    # loading and contract
    ("duplicate_keys_pass", 'if key in out:', 'if False:'),
    ("nan_passes", 'parse_constant=_constant', 'parse_constant=float'),
    ("floats_parse", 'parse_float=_no_float)', 'parse_float=lambda t: int(float(t)))'),
    ("bool_fixture_version_passes", 'if type(root["fixture_version"]) is not int:', 'if root["fixture_version"] is None:'),
    ("size_cap_removed", 'if len(data) > limit:', 'if False:'),
    ("recursion_escapes", 'except (ValueError, RecursionError):', 'except ValueError:'),
    ("control_chars_pass", 'if ch != " " and unicodedata.category(ch) in BAD_CATEGORIES:', 'if False:'),
    ("duplicate_ids_pass", 'if pid in seen:', 'if False:'),
    ("expected_not_checked", 'if type(p["expected"]) is not str or p["expected"] not in VERDICTS:', 'if False:'),
    ("deny_exit_code_changed", '        sys.stderr.write("ERROR %s: %s (on_expiry=DENY)\\n" % (e.code, e.detail))\n        return 2',
     '        sys.stderr.write("ERROR %s: %s (on_expiry=DENY)\\n" % (e.code, e.detail))\n        return 1'),
    ("open_gate_exits_zero", 'return 0 if result["closed"] == result["total"] else 1', 'return 0'),
]


def outcome(code):
    """None means the suite run reached TIMEOUT; that is on_expiry DENY and never a kill."""
    if code is None:
        return "TIMEOUT"
    return "SURVIVED" if code == 0 else "KILLED"


def is_killed(result):
    return result == "KILLED"


def score(names, evaluate):
    """Evaluate each mutant; only KILLED counts. Returns (killed, [(result, name), ...])."""
    results = [(evaluate(name), name) for name in names]
    return sum(1 for r, _ in results if is_killed(r)), results


def summary_line(killed, total, results):
    timeouts = sum(1 for r, _ in results if r == "TIMEOUT")
    return "mutants killed: %d/%d (timeouts: %d, not counted as kills; on_expiry %s)" % (
        killed, total, timeouts, TIMEOUT["on_expiry"])


def run_suite(workdir):
    try:
        done = subprocess.run([sys.executable, "-B", "-m", "unittest", "-f"], cwd=workdir, capture_output=True,
                              timeout=TIMEOUT["seconds"])
    except subprocess.TimeoutExpired:
        return None
    return done.returncode


def main():
    with open(os.path.join(HERE, "prerelease_gate.py"), "r", encoding="utf-8") as fh:
        original = fh.read()
    table = {m[0]: m for m in MUTANTS}
    if len(table) != len(MUTANTS):
        sys.stdout.write("ERROR duplicate mutant names\n")
        return 2
    for name, fragment, _ in MUTANTS:
        if original.count(fragment) != 1:
            sys.stdout.write("ERROR fragment for %s occurs %d times\n" % (name, original.count(fragment)))
            return 2
    work = tempfile.mkdtemp(prefix="w31-mutants-")
    try:
        for entry in os.listdir(HERE):
            if entry == "__pycache__":
                continue
            src = os.path.join(HERE, entry)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(work, entry))
            else:
                shutil.copy(src, os.path.join(work, entry))
        target = os.path.join(work, "prerelease_gate.py")
        base = outcome(run_suite(work))
        sys.stdout.write("baseline suite: %s\n" % ("passes" if base == "SURVIVED" else base))
        if base != "SURVIVED":
            sys.stdout.write("ERROR the unmodified suite must pass within the timeout\n")
            return 2

        def evaluate(name):
            _, fragment, replacement = table[name]
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(original.replace(fragment, replacement))
            result = outcome(run_suite(work))
            sys.stdout.write("%-8s %s\n" % (result, name))
            return result

        killed, results = score([m[0] for m in MUTANTS], evaluate)
        sys.stdout.write(summary_line(killed, len(MUTANTS), results) + "\n")
        return 0 if killed == len(MUTANTS) else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
