"""Mutation run: each mutant is applied to an in-memory copy of strict_threshold.py and the suite must fail by behaviour.

Run: python3 -B mutants.py
Each mutant replaces one fragment (which must occur exactly once) in the module text held in memory. A child
python3 -B builds the module from that text, registers it as 'strict_threshold' and runs the unittest suite. Nothing
is written to disk. The child prints one JSON line with its failure and error counts and the failing test names.
Outcomes:
- KILLED-behaviour  at least one test fails by assertion (a unittest failure).
- CRASH             the module does not load, or tests only error (exceptions); counted apart, never a kill.
- TIMEOUT           the child reached TIMEOUT; on_expiry DENY, never a kill.
- SURVIVED          the suite passed.
The last line prints k/t/c (behaviour kills / timeouts / crashes). Exit 0 only if every mutant is KILLED-behaviour.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = "strict_threshold"
TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}
LOAD_FAILED = 97

RUNNER = r"""
import json, sys, types, unittest
src = sys.stdin.read()
mod = types.ModuleType("strict_threshold")
mod.__file__ = "strict_threshold.py"
try:
    exec(compile(src, "strict_threshold.py", "exec"), mod.__dict__)
except BaseException as e:
    sys.stderr.write("mutant failed to load: %r\n" % (e,))
    sys.exit(97)
sys.modules["strict_threshold"] = mod
suite = unittest.defaultTestLoader.loadTestsFromName("test_strict_threshold")
result = unittest.TextTestRunner(stream=sys.stderr, verbosity=0).run(suite)
name = lambda t: t.id().split(".", 1)[-1]
print(json.dumps({"failures": len(result.failures), "errors": len(result.errors),
                  "failed": sorted({name(t) for t, _ in result.failures}),
                  "errored": sorted({name(t) for t, _ in result.errors})}))
sys.exit(0 if result.wasSuccessful() else 1)
"""

ROW0 = 'v.get("id") in (None, "reminder_letter", "edge_upper")'
MUTANTS = [
    # paper-strict reading and critical value
    ("paper_strict_uses_inclusive", 'return critical_value(lo, hi) < margin', 'return critical_value(lo, hi) <= margin'),
    ("paper_strict_never_passes", '"zero_reference_paper_strict": "PASS" if strict else "FAIL"',
     '"zero_reference_paper_strict": "FAIL"'),
    ("paper_strict_copies_inclusive", '"zero_reference_paper_strict": "PASS" if strict else "FAIL"',
     '"zero_reference_paper_strict": "PASS" if zero else "FAIL"'),
    ("critical_value_uses_hi_only", 'return max(lo.copy_abs(), hi.copy_abs())', 'return hi.copy_abs()'),
    ("critical_value_without_abs", 'return max(lo.copy_abs(), hi.copy_abs())', 'return max(lo, hi)'),
    ("critical_value_uses_min", 'return max(lo.copy_abs(), hi.copy_abs())', 'return min(lo.copy_abs(), hi.copy_abs())'),
    ("readings_differ_counts_all", 'if r["zero_reference"] != r["zero_reference_paper_strict"]', 'if r["zero_reference"]'),
    # strict-arm report
    ("header_inclusive_relabelled", 'inclusive (passes when T <= m)', 'inclusive (passes when T < m)'),
    ("header_strict_relabelled", 'paper-strict (passes only when T < m)', 'paper-strict (passes only when T <= m)'),
    ("legend_dropped", 'out += ["", STRICT_ARM_LEGEND, ""]', 'out += ["", ""]'),
    ("strict_column_prints_inclusive", 'r["zero_reference_paper_strict"], _fmt(r["zero_threshold"]),',
     'r["zero_reference"], _fmt(r["zero_threshold"]),'),
    ("inclusive_column_prints_equivalence", 'r["equivalence"], r["zero_reference"],\n',
     'r["equivalence"], r["equivalence"],\n'),
    ("threshold_not_printed", '_fmt(r["zero_threshold"]),\n', '"-",\n'),
    ("threshold_printed_as_margin", '_fmt(r["zero_threshold"]),\n', '_fmt(r["margin"]),\n'),
    ("threshold_rounded_to_2dp_in_report", '_fmt(r["zero_threshold"]),\n', '_fmt(r["zero_threshold"].quantize(D("0.01"))),\n'),
    ("reachable_flag_ignored_in_report", '"" if r["reachable"] else', '"" if True else'),
    # JSON rows after row 0 (the review's survivors, adapted)
    ("json_threshold_dropped_after_row0", '            return {k: conv(x) for k, x in v.items()}',
     '            return {k: conv(x) for k, x in v.items() if k != "zero_threshold" or %s}' % ROW0),
    ("json_threshold_wrong_after_row0", '            return {k: conv(x) for k, x in v.items()}',
     '            return {k: (conv(x) if k != "zero_threshold" or %s else "0") for k, x in v.items()}' % ROW0),
    ("json_paper_strict_dropped_after_row0", '            return {k: conv(x) for k, x in v.items()}',
     '            return {k: conv(x) for k, x in v.items() if k != "zero_reference_paper_strict" or %s}' % ROW0),
    ("json_paper_strict_wrong_after_row0", '            return {k: conv(x) for k, x in v.items()}',
     '            return {k: (conv(x) if k != "zero_reference_paper_strict" or %s else "FAIL") for k, x in v.items()}'
     % ROW0),
    # the inclusive rule and verdicts (from #160)
    ("window_uses_strict_edges", 'return hi - margin <= effect <= lo + margin', 'return hi - margin < effect < lo + margin'),
    ("window_swapped", 'return hi - margin <= effect <= lo + margin', 'return lo - margin <= effect <= hi + margin'),
    ("zero_reference_uses_candidate", 'zero = equivalent(D(0), c["human_lo"]', 'zero = equivalent(c["candidate"], c["human_lo"]'),
    ("zero_pass_counted_as_response", '    if eq and not zero:\n', '    if eq:\n'),
    ("fail_zero_note_dropped", 'note = "FAIL; the zero reference would have passed"', 'note = "FAIL"'),
    ("reachable_off_by_factor", '<= 2 * c["margin"]', '<= c["margin"]'),
    ("closed_ignores_zero", 'closed = (d["equivalence"], d["zero_reference"]) == EXPECTED[c["planted"]]',
     'closed = d["equivalence"] == EXPECTED[c["planted"]][0]'),
    ("gate_always_passes", 'return "PASS" if res["closed"] == res["total"] else "FAIL"', 'return "PASS"'),
    ("open_gate_exits_zero", 'return 0 if gate(res) == "PASS" else 1', 'return 0'),
    ("rule_uses_default_precision", 'ctx.prec = RULE_PREC', 'ctx.prec = 28'),
    # loading and contract
    ("bool_counts_as_number", '    if type(value) is not D:\n        raise FoldError("bad_type", "%s must be a number"',
     '    if type(value) not in (D, bool):\n        raise FoldError("bad_type", "%s must be a number"'),
    ("text_counts_as_number", '    if type(value) is not D:\n        raise FoldError("bad_type", "%s must be a number"',
     '    if type(value) not in (D, str):\n        raise FoldError("bad_type", "%s must be a number"'),
    ("nan_becomes_zero", 'parse_constant=_constant', 'parse_constant=lambda name: D(0)'),
    ("infinite_passes", '    if not value.is_finite():\n', '    if False:\n'),
    ("range_cap_removed", 'if value.copy_abs() > CAPS["abs_value"]["limit"]:', 'if False:'),
    ("range_cap_uses_context_abs", 'if value.copy_abs() >', 'if abs(value) >'),
    ("positive_exponent_passes", '    if exponent > 0:\n', '    if False:\n'),
    ("decimal_places_cap_removed", 'if -exponent > CAPS["decimal_places"]["limit"]:', 'if False:'),
    ("number_length_cap_removed", 'if len(text) > CAPS["number_chars"]["limit"]:', 'if False:'),
    ("size_cap_removed", 'if len(data) > limit:', 'if False:'),
    ("zero_margin_passes", 'if margin <= 0:', 'if margin < 0:'),
    ("reversed_interval_passes", 'if lo > hi:', 'if False:'),
    ("duplicate_id_passes", '        if c["id"] in seen:\n', '        if False:\n'),
    ("duplicate_keys_pass", '        if key in out:\n', '        if False:\n'),
    ("unknown_fields_pass", '        if key not in keys:\n', '        if False:\n'),
    ("empty_list_passes", '    if not items:\n', '    if False:\n'),
    ("float_version_passes", 'version.as_tuple().exponent != 0 or ', ''),
    ("bad_planted_passes", 'if c["planted"] not in PLANTED:', 'if False:'),
    ("invisible_text_passes", 'if any(unicodedata.category(ch) in INVISIBLE for ch in value):', 'if False:'),
    ("error_to_stdout", '        err.write("ERROR %s: %s (on_expiry=DENY)\\n" % (e.code, e.detail))',
     '        out.write("ERROR %s: %s (on_expiry=DENY)\\n" % (e.code, e.detail))'),
]


def classify(code, counts):
    """code is the child's exit code (None when TIMEOUT was reached); counts is its JSON line ({} when missing)."""
    if code is None:
        return "TIMEOUT"
    if code == LOAD_FAILED:
        return "CRASH"
    if code == 0 and counts.get("failures") == 0 and counts.get("errors") == 0:
        return "SURVIVED"
    if counts.get("failures", 0) > 0:
        return "KILLED-behaviour"
    return "CRASH"


def evaluate(source):
    try:
        done = subprocess.run([sys.executable, "-B", "-c", RUNNER], input=source, cwd=HERE, capture_output=True,
                              text=True, timeout=TIMEOUT["seconds"])
    except subprocess.TimeoutExpired:
        return "TIMEOUT", {}
    counts = {}
    lines = done.stdout.strip().splitlines()
    if lines:
        try:
            counts = json.loads(lines[-1])
        except ValueError:
            counts = {}
    return classify(done.returncode, counts), counts


def summary(outcomes):
    n = {k: outcomes.count(k) for k in ("KILLED-behaviour", "TIMEOUT", "CRASH", "SURVIVED")}
    return "mutants k/t/c: %d/%d/%d (behaviour kills %d, crash-only %d, survived %d of %d; on_expiry %s)" % (
        n["KILLED-behaviour"], n["TIMEOUT"], n["CRASH"], n["KILLED-behaviour"], n["CRASH"], n["SURVIVED"],
        len(outcomes), TIMEOUT["on_expiry"])


def main():
    with open(os.path.join(HERE, MODULE + ".py"), "r", encoding="utf-8") as fh:
        original = fh.read()
    if len({m[0] for m in MUTANTS}) != len(MUTANTS):
        sys.stdout.write("ERROR duplicate mutant names\n")
        return 2
    for name, fragment, replacement in MUTANTS:
        if original.count(fragment) != 1 or fragment == replacement:
            sys.stdout.write("ERROR fragment for %s occurs %d times\n" % (name, original.count(fragment)))
            return 2
    base, _ = evaluate(original)
    sys.stdout.write("baseline suite: %s\n" % ("passes" if base == "SURVIVED" else base))
    if base != "SURVIVED":
        sys.stdout.write("ERROR the unmodified suite must pass within the timeout\n")
        return 2
    outcomes = []
    for name, fragment, replacement in MUTANTS:
        outcome, counts = evaluate(original.replace(fragment, replacement))
        outcomes.append(outcome)
        sys.stdout.write("%-16s %s (failures %s, errors %s; failed: %s)\n" % (
            outcome, name, counts.get("failures", "-"), counts.get("errors", "-"),
            ", ".join(counts.get("failed", [])) or "-"))
    sys.stdout.write(summary(outcomes) + "\n")
    return 0 if all(o == "KILLED-behaviour" for o in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
