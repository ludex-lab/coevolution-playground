"""Mutation run: break spec_review.py one way at a time and require the unittest suite to fail each time.

Run: python3 -B mutants.py
Each mutant is (name, fragment, replacement); the fragment must occur exactly once in the module.
Each suite run is bounded by TIMEOUT. A run that reaches it has on_expiry DENY: it is reported as TIMEOUT and is NOT
counted as killed, so the whole run fails. Exit 0 only if every mutant is killed by a real test failure.
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
    # clause audit
    ("audit_skips_full_push", 'if o["ok"]:\n                    flag("capacity", "push_accepted_when_full", n)',
     'if False:\n                    flag("capacity", "push_accepted_when_full", n)'),
    ("audit_skips_refused_push", 'elif not o["ok"]:\n                flag("capacity"', 'elif False:\n                flag("capacity"'),
    ("audit_skips_order", 'if o["value"] != queue.pop(0):', 'if queue.pop(0) is None:'),
    ("audit_expects_newest", 'if o["value"] != queue.pop(0):', 'if o["value"] != queue.pop():'),
    ("audit_skips_underflow", 'if o["served"] or o["value"] is not None:', 'if False:'),
    ("audit_underflow_served_only", 'if o["served"] or o["value"] is not None:', 'if o["served"]:'),
    ("audit_skips_unserved_pop", 'flag("order", "pop_not_served_when_not_empty", n)', 'pass'),
    ("audit_skips_count", 'if o["count"] != occupancy:', 'if False:'),
    ("audit_skips_full_flag", 'if o["full"] != (occupancy == depth):', 'if False:'),
    ("audit_skips_empty_flag", 'if o["empty"] != (occupancy == 0):', 'if False:'),
    ("audit_fixed_depth", 'depth = spec["capacity"]["depth"]', 'depth = 4'),
    ("audit_invents_clause_ids", 'key = (spec[rule]["id"], rule, code)', 'key = ("S" + str(RULES.index(rule) + 1), rule, code)'),
    ("audit_last_step_not_first", 'first, count = found.get(key, (step, 0))',
     'first, count = (step, found.get(key, (step, 0))[1])'),
    ("audit_reason_order", 'reasons.sort(key=lambda r: (r["first_step"], r["clause"], r["code"]))',
     'reasons.sort(key=lambda r: r["clause"], reverse=True)'),
    ("view_shares_outputs", '"out": dict(s["out"])', '"out": s["out"]'),
    # scoreboard and run
    ("scoreboard_compares_every_field", 'for field in case["compare"]:', 'for field in FIELDS:'),
    ("scoreboard_compares_nothing", 'if field in d["out"] and d["out"][field] != g["out"][field]:', 'if False:'),
    ("scoreboard_uses_a_fixed_golden", 'gold = simulate(case["golden"], depth, case["stimulus"])',
     'gold = simulate("correct", depth, case["stimulus"])'),
    ("audit_reads_the_golden_trace", 'trace_view(simulate(case["dut"], fx["depth"], case["stimulus"]))',
     'trace_view(simulate(case["golden"], fx["depth"], case["stimulus"]))'),
    ("outcome_labels_swapped", '("PASS", "FAIL"): "escape"', '("PASS", "FAIL"): "real_fail"'),
    ("check_a_ignores_the_audit", 'lambda r: sb_pass(r) and not au_pass(r)', 'lambda r: sb_pass(r)'),
    ("empty_group_counts_as_met", 'return bool(group) and all(pred(r) for r in group)',
     'return all(pred(r) for r in group)'),
    ("rate_numerator_wrong", 'return "%d/%d" % (sum(1 for r in group if pred(r)), len(group))',
     'return "%d/%d" % (len(group), len(group))'),
    # design models
    ("overwrite_bug_removed", 'elif variant == "overwrite_when_full":', 'elif False:'),
    ("lifo_bug_removed", 'value = queue.pop() if variant == "lifo" else queue.pop(0)', 'value = queue.pop(0)'),
    ("early_flag_bug_removed", 'full_at = depth - 1 if variant == "full_flag_early" else depth', 'full_at = depth'),
    ("underflow_bug_removed", 'elif variant == "underflow_returns_data":', 'elif False:'),
    # loading and the probe battery
    ("duplicate_keys_pass", 'if key in out:', 'if False:'),
    ("nan_passes", 'parse_constant=_constant', 'parse_constant=float'),
    ("floats_parse", 'parse_float=_no_float)', 'parse_float=lambda t: int(float(t)))'),
    ("bool_counts_as_int", 'if type(value) is not int:', 'if not isinstance(value, int):'),
    ("range_not_checked", 'if not low <= value <= high:', 'if False:'),
    ("size_cap_removed", 'if len(data) > MAX_BYTES:', 'if False:'),
    ("recursion_escapes", 'except (ValueError, RecursionError, OverflowError):', 'except (ValueError, OverflowError):'),
    ("control_chars_pass", 'if ch != " " and unicodedata.category(ch) in BAD_CATEGORIES:', 'if False:'),
    ("edge_spaces_pass", 'if value != value.strip(" "):', 'if False:'),
    ("ids_not_normalised", 'cid = unicodedata.normalize("NFC", c["id"]) if type(c["id"]) is str else None',
     'cid = c["id"] if type(c["id"]) is str else None'),
    ("missing_clause_passes", 'len(clauses) != len(RULES)', 'len(clauses) > len(RULES)'),
    ("duplicate_rule_passes", 'if c["id"] in ids or rule in rules:', 'if c["id"] in ids:'),
    ("depth_placement_unchecked", 'if ("depth" in c) != (rule == "capacity"):', 'if False:'),
    ("unknown_keys_pass", 'unknown = sorted(set(value) - set(keys) - set(optional))', 'unknown = []'),
    ("duplicate_compare_passes", 'if len(set(compare)) != len(compare):', 'if False:'),
    ("error_exit_code_changed", '        return 2\n    sys.stdout.write(text)', '        return 1\n    sys.stdout.write(text)'),
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


def run_suite(workdir):
    try:
        done = subprocess.run([sys.executable, "-B", "-m", "unittest", "-f"], cwd=workdir, capture_output=True,
                              timeout=TIMEOUT["seconds"])
    except subprocess.TimeoutExpired:
        return None
    return done.returncode


def main():
    with open(os.path.join(HERE, "spec_review.py"), "r", encoding="utf-8") as fh:
        original = fh.read()
    table = {m[0]: m for m in MUTANTS}
    if len(table) != len(MUTANTS):
        sys.stdout.write("ERROR duplicate mutant names\n")
        return 2
    for name, fragment, _ in MUTANTS:
        if original.count(fragment) != 1:
            sys.stdout.write("ERROR fragment for %s occurs %d times\n" % (name, original.count(fragment)))
            return 2
    work = tempfile.mkdtemp(prefix="mbvv-mutants-")
    try:
        for entry in os.listdir(HERE):
            if entry == "__pycache__":
                continue
            src = os.path.join(HERE, entry)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(work, entry))
            else:
                shutil.copy(src, os.path.join(work, entry))
        target = os.path.join(work, "spec_review.py")
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

        killed, _ = score([m[0] for m in MUTANTS], evaluate)
        sys.stdout.write("mutants killed: %d/%d (timeouts are not kills; on_expiry %s)\n"
                         % (killed, len(MUTANTS), TIMEOUT["on_expiry"]))
        return 0 if killed == len(MUTANTS) else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
