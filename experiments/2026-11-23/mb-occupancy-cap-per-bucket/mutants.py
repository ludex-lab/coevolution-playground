"""Mutation run: break occupancy_cap.py one way at a time and require the unittest suite to fail each time.

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
    # the occupancy control itself
    ("bucket_cap_not_enforced", 'if len(same) > case["bucket_cap"]:', 'if False:'),
    ("bucket_cap_off_by_one", 'if len(same) > case["bucket_cap"]:', 'if len(same) > case["bucket_cap"] + 1:'),
    ("bucket_eviction_drops_highest", 'memory.remove(min(same, key=rank_key))', 'memory.remove(max(same, key=rank_key))'),
    ("bucket_eviction_drops_newcomer", 'memory.remove(min(same, key=rank_key))', 'memory.remove(item)'),
    ("overflow_from_any_bucket", 'for b in sorted(counts) if counts[b] == top]', 'for b in sorted(counts)]'),
    ("overflow_drops_oldest", 'memory.remove(min(lowest, key=rank_key))', 'memory.pop(0)'),
    ("overflow_never_happens", '        if len(memory) > case["capacity"]:\n            counts = _occupancy(memory)',
     '        if False:\n            counts = _occupancy(memory)'),
    ("bucket_rounds_up", '"bucket": t // seconds', '"bucket": -(-t // seconds)'),
    ("one_bucket_for_all", '"bucket": t // seconds', '"bucket": 0'),
    # rank order and the weak arms
    ("rank_ignores_age", 'return (item["score"], item["t"], item["id"])', 'return (item["score"], item["id"])'),
    ("rank_prefers_newer", 'return (item["score"], item["t"], item["id"])',
     'return (item["score"], -item["t"], item["id"])'),
    ("score_only_drops_highest", '            memory.remove(min(memory, key=rank_key))',
     '            memory.remove(max(memory, key=rank_key))'),
    ("recency_drops_newest", 'memory.pop(0)', 'memory.pop()'),
    ("score_only_never_evicts", '        if len(memory) > case["capacity"]:\n            memory.remove(min(memory',
     '        if len(memory) > case["capacity"] + 99:\n            memory.remove(min(memory'),
    # measuring and judging
    ("over_cap_uses_ge", '"over_cap": top > case["bucket_cap"]', '"over_cap": top >= case["bucket_cap"]'),
    ("earlier_lost_uses_le", 'bucket_of[n] < crowded]', 'bucket_of[n] <= crowded]'),
    ("lost_list_empty", 'lost = [n for n in needed if n not in kept]', 'lost = []'),
    ("burst_judge_skips_weak_check", 'if not weak["over_cap"] or not weak["earlier_lost"]:', 'if False:'),
    ("burst_judge_skips_strict_loss", '        if strict["lost"]:\n            return False, "bucket_cap lost',
     '        if False:\n            return False, "bucket_cap lost'),
    ("none_judge_ignores_weak", 'if strict["lost"] or weak["lost"]:', 'if strict["lost"]:'),
    ("over_cap_judge_inverted", '    if not strict["lost"]:\n        return False, "need_over_cap',
     '    if strict["lost"]:\n        return False, "need_over_cap'),
    ("strict_cap_break_ignored", 'if strict["over_cap"] or len(strict["kept"]) > case["capacity"]:',
     'if len(strict["kept"]) > case["capacity"]:'),
    ("strict_capacity_break_ignored", 'if strict["over_cap"] or len(strict["kept"]) > case["capacity"]:',
     'if strict["over_cap"]:'),
    ("arm_gate_counts_over_cap_needs", 'if r["planted"] != "need_over_cap" and a["lost"]:', 'if a["lost"]:'),
    ("gate_always_passes", 'return "PASS" if result["closed"] == result["total"] else "FAIL"', 'return "PASS"'),
    ("exit_zero_on_open_gate", 'return 0 if gate(result) == "PASS" else 1', 'return 0'),
    # loading and contract
    ("out_of_order_passes", 'if t < last_t:', 'if False:'),
    ("cap_above_capacity_passes", 'if cap > capacity:', 'if False:'),
    ("duplicate_item_passes", '        if iid in seen:\n', '        if False:\n'),
    ("unknown_need_passes", 'if name not in seen:', 'if False:'),
    ("duplicate_need_passes", 'if len(set(needs)) != len(needs):', 'if False:'),
    ("duplicate_keys_pass", '        if key in out:', '        if False:'),
    ("unknown_keys_pass", '        if key not in keys:', '        if False:'),
    ("bool_counts_as_int", 'if type(value) is not int:', 'if not isinstance(value, int):'),
    ("floats_parse", 'parse_float=_no_float)', 'parse_float=lambda t: int(float(t)))'),
    ("nan_passes", 'parse_constant=_constant', 'parse_constant=float'),
    ("size_cap_removed", 'if len(data) > limit:', 'if False:'),
    ("control_characters_pass", 'if any(unicodedata.category(ch) in BAD_CATEGORIES for ch in value):', 'if False:'),
    ("no_nfc", 'return unicodedata.normalize("NFC", value)', 'return value'),
    ("bad_planted_passes", 'if c["planted"] not in PLANTED:', 'if False:'),
    ("empty_lists_pass", 'def _list(value, cap, where, low=1):', 'def _list(value, cap, where, low=0):'),
    ("error_goes_to_stdout", 'sys.stderr.write("ERROR %s: %s (on_expiry=DENY)\\n" % (e.code, e.detail))',
     'sys.stdout.write("ERROR %s: %s (on_expiry=DENY)\\n" % (e.code, e.detail))'),
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
        env = dict(os.environ, OCCUPANCY_MUTANT_RUN="1")
        done = subprocess.run([sys.executable, "-B", "-m", "unittest", "-f"], cwd=workdir, capture_output=True,
                              timeout=TIMEOUT["seconds"], env=env)
    except subprocess.TimeoutExpired:
        return None
    return done.returncode


def main():
    with open(os.path.join(HERE, "occupancy_cap.py"), "r", encoding="utf-8") as fh:
        original = fh.read()
    table = {m[0]: m for m in MUTANTS}
    if len(table) != len(MUTANTS):
        sys.stdout.write("ERROR duplicate mutant names\n")
        return 2
    for name, fragment, _ in MUTANTS:
        if original.count(fragment) != 1:
            sys.stdout.write("ERROR fragment for %s occurs %d times\n" % (name, original.count(fragment)))
            return 2
    work = tempfile.mkdtemp(prefix="occupancy-mutants-")
    try:
        for entry in os.listdir(HERE):
            if entry == "__pycache__":
                continue
            src = os.path.join(HERE, entry)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(work, entry))
            else:
                shutil.copy(src, os.path.join(work, entry))
        target = os.path.join(work, "occupancy_cap.py")
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
