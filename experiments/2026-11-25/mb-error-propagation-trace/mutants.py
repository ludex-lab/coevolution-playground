"""Mutation run: each mutant is applied to an in-memory copy of propagation_trace.py and the suite must fail by behaviour.

Run: python3 -B mutants.py
Each mutant replaces one fragment (which must occur exactly once) in the module text held in memory. A child
python3 -B builds the module from that text, registers it as 'propagation_trace' and runs the unittest suite. Nothing
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
MODULE = "propagation_trace"
TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}
LOAD_FAILED = 97

RUNNER = r"""
import json, sys, types, unittest
src = sys.stdin.read()
mod = types.ModuleType("propagation_trace")
mod.__file__ = "propagation_trace.py"
try:
    exec(compile(src, "propagation_trace.py", "exec"), mod.__dict__)
except BaseException as e:
    sys.stderr.write("mutant failed to load: %r\n" % (e,))
    sys.exit(97)
sys.modules["propagation_trace"] = mod
suite = unittest.defaultTestLoader.loadTestsFromName("test_propagation_trace")
result = unittest.TextTestRunner(stream=sys.stderr, verbosity=0).run(suite)
name = lambda t: t.id().split(".", 1)[-1]
print(json.dumps({"failures": len(result.failures), "errors": len(result.errors),
                  "failed": sorted({name(t) for t, _ in result.failures}),
                  "errored": sorted({name(t) for t, _ in result.errors})}))
sys.exit(0 if result.wasSuccessful() else 1)
"""

MUTANTS = [
    # hop classification
    ("clean_edge_strict", '        return "clean" if err <= tol else "introduced"', '        return "clean" if err < tol else "introduced"'),
    ("received_edge_strict", '    if prev <= tol:\n', '    if prev < tol:\n'),
    ("corrected_edge_strict", '    if err <= tol:\n        return "corrected"', '    if err < tol:\n        return "corrected"'),
    ("equal_counts_as_attenuated", 'return "amplified" if err >= prev else "attenuated"', 'return "amplified" if err > prev else "attenuated"'),
    ("amplified_attenuated_swapped", 'return "amplified" if err >= prev else "attenuated"', 'return "attenuated" if err >= prev else "amplified"'),
    ("corrected_called_clean", '        return "corrected"\n', '        return "clean"\n'),
    ("introduced_called_amplified", '"clean" if err <= tol else "introduced"', '"clean" if err <= tol else "amplified"'),
    ("prev_never_updated", '        ref, msg, prev = ref_out, msg_out, err\n', '        ref, msg = ref_out, msg_out\n'),
    # the chain
    ("recheck_ignored", 'base = ref if h["recheck"] else msg', 'base = msg'),
    ("fault_ignored", 'msg_out = _apply("add", _apply(h["op"], base, h["arg"]), h["fault"])', 'msg_out = _apply(h["op"], base, h["arg"])'),
    ("message_restarts_from_reference", '        ref, msg, prev = ref_out, msg_out, err\n', '        ref, msg, prev = ref_out, ref_out, err\n'),
    ("error_signed", 'err = (msg_out - ref_out).copy_abs()', 'err = msg_out - ref_out'),
    ("mul_as_add", 'out = value + arg if op == "add" else value * arg', 'out = value + arg'),
    ("step_precision_low", 'prec=STEP_PREC', 'prec=6'),
    ("step_precision_40", 'STEP_PREC = 700', 'STEP_PREC = 40'),
    ("inexact_untrapped", ', decimal.Inexact])', '])'),
    ("step_precision_28", 'STEP_PREC = 700', 'STEP_PREC = 28'),
    ("step_precision_34", 'STEP_PREC = 700', 'STEP_PREC = 34'),
    ("round_down_untrapped",
     'rounding=decimal.ROUND_HALF_EVEN, Emax=999999, Emin=-999999,\n'
     '                          traps=[decimal.Overflow, decimal.InvalidOperation, decimal.DivisionByZero, decimal.Inexact])',
     'rounding=decimal.ROUND_DOWN, Emax=999999, Emin=-999999,\n'
     '                          traps=[decimal.Overflow, decimal.InvalidOperation, decimal.DivisionByZero])'),
    # outcome and trace
    ("outcome_edge_strict", 'outcome = "PASS" if final <= tol else "FAIL"', 'outcome = "PASS" if final < tol else "FAIL"'),
    ("outcome_uses_first_hop", 'final = hops[-1]["error"]', 'final = hops[0]["error"]'),
    ("corrected_trace_reported_clean", '    elif any(x["error"] > tol for x in hops):\n        trace = "corrected"',
     '    elif False:\n        trace = "corrected"'),
    ("closed_b_ignores_hop_classes", '(outcome, trace, measured_classes) == (exp["outcome"], exp["trace"], exp["hops"])',
     '(outcome, trace) == (exp["outcome"], exp["trace"])'),
    ("closed_b_ignores_trace", '(outcome, trace, measured_classes) == (exp["outcome"], exp["trace"], exp["hops"])',
     '(outcome, measured_classes) == (exp["outcome"], exp["hops"])'),
    ("closed_a_always", '"closed_a": outcome == exp["outcome"],', '"closed_a": True,'),
    ("gate_uses_arm_a", 'return "PASS" if res["closed_b"] == res["total"] else "FAIL"', 'return "PASS" if res["closed_a"] == res["total"] else "FAIL"'),
    ("open_gate_exits_zero", 'return 0 if gate(res) == "PASS" else 1', 'return 0'),
    ("hidden_count_counts_clean", 'r["outcome"] == "PASS" and r["trace"] == "corrected"', 'r["outcome"] == "PASS"'),
    # report
    ("story_says_no_error_when_corrected", '    if r["trace"] == "clean":\n        return "no hop error above tolerance"',
     '    if r["outcome"] == "PASS":\n        return "no hop error above tolerance"'),
    ("story_hides_did_occur", 'return text + "; final PASS, but an error did occur"', 'return text + "; final PASS"'),
    ("story_drops_later_introductions", 'for x in starts)', 'for x in starts[:1])'),
    ("report_hides_class", '_fmt(x["message"]), _fmt(x["error"]), x["class"]))', '_fmt(x["message"]), _fmt(x["error"]), "-"))'),
    ("report_hides_recheck", '" (recheck)" if x["recheck"] else ""', '""'),
    # numbers and contract
    ("bool_counts_as_number", '    if type(value) is not D:\n        raise TraceError("bad_type", "%s must be a number"',
     '    if type(value) not in (D, bool):\n        raise TraceError("bad_type", "%s must be a number"'),
    ("nan_becomes_zero", 'parse_constant=_constant', 'parse_constant=lambda name: D(0)'),
    ("non_finite_passes", '    if not value.is_finite():\n', '    if False:\n'),
    ("range_cap_removed", 'if value.copy_abs() > CAPS["abs_value"]["limit"]:', 'if False:'),
    ("range_cap_uses_context_abs", 'if value.copy_abs() > CAPS["abs_value"]["limit"]:', 'if abs(value) > CAPS["abs_value"]["limit"]:'),
    ("positive_exponent_passes", '    if exponent > 0:\n', '    if False:\n'),
    ("decimal_places_cap_removed", 'if -exponent > CAPS["decimal_places"]["limit"]:', 'if False:'),
    ("negative_zero_kept_signed", '    if value.is_zero():\n        value = value.copy_abs()', '    if False:\n        value = value.copy_abs()'),
    ("computed_negative_zero_kept", '    if out.is_zero():\n        out = out.copy_abs()', '    if False:\n        out = out.copy_abs()'),
    ("computed_cap_removed", 'if not out.is_finite() or out.copy_abs() > CAPS["computed_abs"]["limit"]:', 'if not out.is_finite():'),
    ("computed_cap_off_by_one", 'out.copy_abs() > CAPS["computed_abs"]["limit"]', 'out.copy_abs() >= CAPS["computed_abs"]["limit"]'),
    ("empty_chain_passes", '    if not hops:\n', '    if False:\n'),
    ("tolerance_zero_passes", 'if tol <= 0:', 'if tol < 0:'),
    ("recheck_type_unchecked", '    if type(recheck) is not bool:\n', '    if False:\n'),
    ("bad_op_passes", '    if h["op"] not in OPS:\n', '    if False:\n'),
    ("expect_length_unchecked", ' or len(\n            e["hops"]) != len(hops)', ''),
    ("duplicate_id_passes", '        if c["id"] in seen:\n', '        if False:\n'),
    ("duplicate_keys_pass", '        if key in out:\n', '        if False:\n'),
    ("unknown_fields_pass", '        if key not in required and key not in optional:\n', '        if False:\n'),
    ("size_cap_off_by_one", 'if len(data) > limit:', 'if len(data) >= limit:'),
    ("hop_cap_removed", 'if len(hops) > CAPS["hops"]["limit"]:', 'if False:'),
    ("float_version_passes", 'version.as_tuple().exponent != 0 or ', ''),
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
