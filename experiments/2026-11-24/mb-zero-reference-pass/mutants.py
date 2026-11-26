"""Mutation run: each mutant is applied to an in-memory copy of zero_reference.py and the suite must fail.

Run: python3 -B mutants.py
For each mutant this script replaces one fragment (which must occur exactly once) in the module text held in memory,
then starts a child python3 -B that builds the module from that text, registers it as 'zero_reference' and runs the
unittest suite against it. Nothing is written to disk.
Outcomes:
- KILLED   at least one test fails (unittest reports failures).
- CRASH    the mutated module does not load, or the suite only errors; counted apart from kills.
- TIMEOUT  the child reached TIMEOUT; on_expiry DENY, never a kill.
- SURVIVED the suite passed.
The summary prints k/t/c (killed / timeout / crash). Exit 0 only if every mutant is KILLED.
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = "zero_reference"
TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}
IMPORT_FAILED = 97

RUNNER = r"""
import sys, types, unittest
src = sys.stdin.read()
mod = types.ModuleType("zero_reference")
mod.__file__ = "zero_reference.py"
try:
    exec(compile(src, "zero_reference.py", "exec"), mod.__dict__)
except BaseException as e:
    sys.stderr.write("mutant failed to load: %r\n" % (e,))
    sys.exit(97)
sys.modules["zero_reference"] = mod
suite = unittest.defaultTestLoader.loadTestsFromName("test_zero_reference")
result = unittest.TextTestRunner(stream=sys.stderr, verbosity=0).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
"""

MUTANTS = [
    # the rule
    ("window_uses_strict_edges", 'return hi - margin <= effect <= lo + margin', 'return hi - margin < effect < lo + margin'),
    ("window_swapped", 'return hi - margin <= effect <= lo + margin', 'return lo - margin <= effect <= hi + margin'),
    ("window_only_lower_edge", 'return hi - margin <= effect <= lo + margin', 'return hi - margin <= effect'),
    ("margin_doubled", 'return hi - margin <= effect <= lo + margin',
     'return hi - 2 * margin <= effect <= lo + 2 * margin'),
    ("zero_reference_uses_candidate", 'zero = equivalent(D(0), c["human_lo"]', 'zero = equivalent(c["candidate"], c["human_lo"]'),
    ("zero_reference_never_passes", 'zero = equivalent(D(0), c["human_lo"], c["human_hi"], c["margin"])', 'zero = False'),
    ("threshold_uses_hi_only", 'return max(abs(lo), abs(hi))', 'return abs(hi)'),
    ("threshold_without_abs", 'return max(abs(lo), abs(hi))', 'return max(lo, hi)'),
    # verdicts and arms
    ("zero_pass_counted_as_response", '    if eq and not zero:\n', '    if eq:\n'),
    ("zero_pass_label_dropped", 'note = "PASS, but the zero reference passes too: this does not establish a response"',
     'note = "PASS"'),
    ("fail_zero_note_dropped", 'note = "FAIL; the zero reference would have passed"', 'note = "FAIL"'),
    ("reachable_off_by_factor", '<= 2 * c["margin"]', '<= c["margin"]'),
    ("expected_zero_reference_wrong", '"zero_reference": ("PASS", "PASS"),', '"zero_reference": ("PASS", "FAIL"),'),
    ("closed_ignores_zero", 'closed = (d["equivalence"], d["zero_reference"]) == EXPECTED[c["planted"]]',
     'closed = d["equivalence"] == EXPECTED[c["planted"]][0]'),
    ("responses_count_all_passes", 'responses = sum(1 for r in rows if r["verdict"] == "response")',
     'responses = sum(1 for r in rows if r["equivalence"] == "PASS")'),
    ("gate_always_passes", 'return "PASS" if res["closed"] == res["total"] else "FAIL"', 'return "PASS"'),
    ("open_gate_exits_zero", 'return 0 if gate(res) == "PASS" else 1', 'return 0'),
    # the report
    ("strict_row_hides_zero", 'out.append("| %s | %s | %s | %s | %s |" % (r["id"], r["equivalence"], r["zero_reference"],',
     'out.append("| %s | %s | %s | %s | %s |" % (r["id"], r["equivalence"], r["equivalence"],'),
    ("threshold_not_printed", '_fmt(r["zero_threshold"]), r["verdict"]))', '"-", r["verdict"]))'),
    # loading and contract
    ("nan_becomes_zero", 'parse_constant=_constant', 'parse_constant=lambda name: D(0)'),
    ("infinite_passes", '    if not value.is_finite():\n', '    if False:\n'),
    ("bool_counts_as_number", '    if type(value) is not D:\n        raise ZeroRefError("bad_type", "%s must be a number"',
     '    if type(value) not in (D, bool):\n        raise ZeroRefError("bad_type", "%s must be a number"'),
    ("zero_margin_passes", 'if margin <= 0:', 'if margin < 0:'),
    ("reversed_interval_passes", 'if lo > hi:', 'if False:'),
    ("duplicate_id_passes", '        if c["id"] in seen:\n', '        if False:\n'),
    ("duplicate_keys_pass", '        if key in out:\n', '        if False:\n'),
    ("unknown_fields_pass", '        if key not in keys:\n', '        if False:\n'),
    ("empty_list_passes", '    if not items:\n', '    if False:\n'),
    ("range_cap_removed", 'if value.copy_abs() > CAPS["abs_value"]["limit"]:', 'if False:'),
    ("range_cap_uses_context_abs", 'if value.copy_abs() >', 'if abs(value) >'),
    ("size_cap_removed", 'if len(data) > limit:', 'if False:'),
    ("decimal_places_cap_removed", 'if -value.as_tuple().exponent > CAPS["decimal_places"]["limit"]:', 'if False:'),
    ("rule_uses_default_precision", 'ctx.prec = RULE_PREC', 'ctx.prec = 28'),
    ("number_length_cap_removed", 'if len(text) > CAPS["number_chars"]["limit"]:', 'if False:'),
    ("float_version_passes", 'version.as_tuple().exponent != 0 or ', ''),
    ("bad_planted_passes", 'if c["planted"] not in PLANTED:', 'if False:'),
    ("invisible_text_passes", 'if any(unicodedata.category(ch) in INVISIBLE for ch in value):', 'if False:'),
    ("error_to_stdout", '        err.write("ERROR %s: %s (on_expiry=DENY)\\n" % (e.code, e.detail))',
     '        out.write("ERROR %s: %s (on_expiry=DENY)\\n" % (e.code, e.detail))'),
]

SUMMARY_RE = re.compile(r"FAILED \(([^)]*)\)")


def classify(code, output):
    """code is the child's exit code, None when TIMEOUT was reached."""
    if code is None:
        return "TIMEOUT"
    if code == IMPORT_FAILED:
        return "CRASH"
    if code == 0:
        return "SURVIVED"
    m = SUMMARY_RE.search(output)
    if m is None:
        return "CRASH"
    counts = dict((k.strip(), int(v)) for k, v in (p.split("=") for p in m.group(1).split(",")))
    return "KILLED" if counts.get("failures", 0) > 0 else "CRASH"


def summary(outcomes):
    n = {k: outcomes.count(k) for k in ("KILLED", "TIMEOUT", "CRASH", "SURVIVED")}
    return "mutants k/t/c: %d/%d/%d (survived %d of %d; a timeout or crash is never a kill; on_expiry %s)" % (
        n["KILLED"], n["TIMEOUT"], n["CRASH"], n["SURVIVED"], len(outcomes), TIMEOUT["on_expiry"])


def evaluate(source):
    try:
        done = subprocess.run([sys.executable, "-B", "-c", RUNNER], input=source, cwd=HERE, capture_output=True,
                              text=True, timeout=TIMEOUT["seconds"])
    except subprocess.TimeoutExpired:
        return classify(None, "")
    return classify(done.returncode, done.stderr + done.stdout)


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
    base = evaluate(original)
    sys.stdout.write("baseline suite: %s\n" % ("passes" if base == "SURVIVED" else base))
    if base != "SURVIVED":
        sys.stdout.write("ERROR the unmodified suite must pass within the timeout\n")
        return 2
    outcomes = []
    for name, fragment, replacement in MUTANTS:
        outcome = evaluate(original.replace(fragment, replacement))
        outcomes.append(outcome)
        sys.stdout.write("%-8s %s\n" % (outcome, name))
    sys.stdout.write(summary(outcomes) + "\n")
    return 0 if all(o == "KILLED" for o in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
