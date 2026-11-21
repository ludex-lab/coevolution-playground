"""Mutation check: break play_craft.py one way at a time and require the unittest suite to fail each time.

Run: python3 -B mutants.py
Each mutant is a (name, fragment, replacement) triple. The fragment must occur exactly once in the module.
A mutant is killed when the suite exits non-zero (a failure, an error or a timeout). Exit 0 only if all are killed.
Work happens in a private temporary directory that this script creates and removes.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TIMEOUT = 300

MUTANTS = [
    # the crafter's view and its independence
    ("view_peeks_at_game_internals",
     '"params": dict(params), "target": _clone(target)}',
     '"params": dict(params), "target": _clone(target), "game": {"long_cost": 9}}'),
    ("view_reports_not_copied",
     '"reports": _clone(reports),',
     '"reports": reports,'),
    ("view_target_not_copied",
     '"target": _clone(target)}',
     '"target": target}'),
    ("ladder_hard_codes_the_reserve_first_order",
     'order = ("reserve", "cue") if reached_short_and_failed else ("cue", "reserve")',
     'order = ("reserve", "cue")'),
    ("ladder_ignores_the_reports",
     'verdict = band_verdict(first_clear(mine), band)',
     'verdict = "too_hard"'),
    ("ladder_reads_other_levels",
     'mine = [r for r in view["reports"] if r["level"] == target["level"]]',
     'mine = [r for r in view["reports"]]'),
    ("ladder_too_easy_raises_instead_of_lowering",
     'direction = -1',
     'direction = 1'),
    ("ladder_move_ignores_the_step",
     'new = current + direction * knob["step"]',
     'new = current + direction'),
    ("overtune_goes_to_min",
     'changes = {k["id"]: k["max"] for k in view["knobs"]}',
     'changes = {k["id"]: k["min"] for k in view["knobs"]}'),
    # the rules
    ("target_check_removed",
     'if not _same(proposal["target"], declared):',
     'if False:'),
    ("target_compared_loosely_so_true_is_one",
     'if not _same(proposal["target"], declared):',
     'if not proposal["target"] == declared:'),
    ("same_ignores_types",
     'if type(a) is not type(b):\n        return False\n    if type(a) is dict:',
     'if type(a) is dict and type(b) is not dict:\n        return False\n    if type(a) is dict:'),
    ("undeclared_knob_check_removed",
     'if knob is None:',
     'if knob is None and False:'),
    ("range_check_widened",
     'if not knob["min"] <= value <= knob["max"]:',
     'if not knob["min"] <= value <= knob["max"] + knob["step"]:'),
    ("range_check_drops_the_low_end",
     'if not knob["min"] <= value <= knob["max"]:',
     'if not value <= knob["max"]:'),
    ("boolean_value_accepted",
     'if type(value) is not int:\n            raise DenyError',
     'if not isinstance(value, int):\n            raise DenyError'),
    ("step_grid_check_removed",
     '% knob["step"] != 0:\n            raise DenyError',
     '% knob["step"] < 0:\n            raise DenyError'),
    ("proposal_shape_check_removed",
     'if type(proposal) is not dict or sorted(proposal) != ["changes", "target", "why"]:',
     'if type(proposal) is not dict:'),
    # HOLD, ESCALATE, DENY
    ("held_episode_still_licenses_craft",
     'if held:\n            status = _expire(fx, held)',
     'if False:\n            status = _expire(fx, held)'),
    ("round_marked_licensed_when_held",
     '"licensed": False,',
     '"licensed": True,'),
    ("step_cap_never_hit",
     'if needed > game["step_cap"]:',
     'if needed > game["step_cap"] + 1000:'),
    ("report_less_episode_still_reports",
     'if episode in game["no_report"]:',
     'if episode in game["no_report"] and False:'),
    ("deny_on_expiry_ignored",
     'if action == "DENY":',
     'if action == "NEVER":'),
    ("escalate_turned_into_hold",
     '    return action\n\n\ndef _expire_rounds',
     '    return "HOLD"\n\n\ndef _expire_rounds'),
    ("round_cap_ignores_on_expiry",
     'status = _expire_rounds(fx)',
     'status = "OK"'),
    ("capped_evaluation_not_held",
     'result["status"] = _expire(fx, evaluation["held"])',
     'result["status"] = "OK"'),
    # fresh evaluation
    ("evaluation_reuses_crafting_memory",
     'evaluation = evaluate(fx, params)',
     'evaluation = evaluate(fx, params, memories)'),
    ("evaluation_memory_start_not_reset",
     'result["eval_memory_start"] = {lv["id"]: fresh_memory() for lv in fx["levels"]}',
     'result["eval_memory_start"] = {k: dict(v) for k, v in memories.items()}'),
    ("contrast_run_mutates_stored_memory",
     'carried = evaluate(fx, params, {k: dict(v) for k, v in memories.items()})',
     'carried = evaluate(fx, params, memories)'),
    ("round_never_converges",
     'if new == params:',
     'if False:'),
    # players and metrics
    ("patience_grows_with_the_cue",
     'level["patience"] - level["sign_weight"] * cue',
     'level["patience"] + level["sign_weight"] * cue'),
    ("player_switches_one_failure_late",
     'return "short" if memory["long_fails"] >= effective_patience(level, cue) else "long"',
     'return "short" if memory["long_fails"] > effective_patience(level, cue) else "long"'),
    ("progress_uses_max_not_min",
     'needed = min(cost, budget)',
     'needed = max(cost, budget)'),
    ("memory_counts_short_failures_too",
     'if path == "long" and outcome == "fail":',
     'if outcome == "fail":'),
    ("gain_sign_flipped",
     '"gain": last_rate - first_rate',
     '"gain": first_rate - last_rate'),
    ("slope_denominator_wrong",
     'episodes * sxx - sx * sx)',
     'episodes * sxx - sx)'),
    ("third_is_half",
     'third = max(1, episodes // 3)',
     'third = max(1, episodes // 2)'),
    ("band_hi_edge_moved",
     'if first is None or first > band["hi"]:',
     'if first is None or first >= band["hi"]:'),
    ("band_lo_edge_moved",
     'if first < band["lo"]:',
     'if first <= band["lo"]:'),
    ("file_diff_blind",
     'not _same(fa[p], fb[p])',
     'False'),
    # loading
    ("bool_accepted_as_int",
     'if type(value) is not int:\n        raise PlayError("wrong_type", "%s must be an integer" % where)',
     'if not isinstance(value, int):\n        raise PlayError("wrong_type", "%s must be an integer" % where)'),
    ("hangul_jamo_ids_refused",
     '\\u1100-\\u1112\\u1161-\\u1175\\u11A8-\\u11C2]',
     ']'),
    ("nfc_duplicates_missed",
     'key = unicodedata.normalize("NFC", name)',
     'key = name'),
    ("duplicate_json_keys_accepted",
     'if key in out:',
     'if False:'),
    ("nan_and_infinity_pass_the_parser",
     'parse_constant=_constant',
     'parse_constant=float'),
    ("size_cap_removed",
     'if len(data) > MAX_BYTES:',
     'if len(data) > MAX_BYTES * 1000:'),
    ("recursion_error_escapes",
     'except (ValueError, RecursionError, OverflowError):',
     'except (ValueError, OverflowError):'),
    ("control_characters_in_labels_pass",
     'unicodedata.category(ch) in BAD_CATEGORIES',
     'False'),
    ("invisible_fillers_in_labels_pass",
     'ord(ch) in BLOCKED_CODEPOINTS or ',
     ''),
    ("label_edge_spaces_pass",
     'if value != value.strip(" "):',
     'if False:'),
    ("role_set_not_checked",
     'if sorted(k["role"] for k in out) != sorted(ROLES):',
     'if False:'),
    ("knob_grid_not_checked",
     'if (knob["max"] - knob["min"]) % knob["step"] != 0:',
     'if False:'),
    ("band_order_not_checked",
     'if lo > hi:',
     'if False:'),
    ("error_exit_code_changed",
     '        sys.stderr.write("ERROR %s: %s\\n" % (e.code, e.detail))\n        return 2',
     '        sys.stderr.write("ERROR %s: %s\\n" % (e.code, e.detail))\n        return 1'),
]


def run_suite(workdir):
    try:
        done = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-f", "-s", ".", "-p", "test_*.py"],
                              cwd=workdir, capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return None
    return done.returncode


def main():
    with open(os.path.join(HERE, "play_craft.py"), "r", encoding="utf-8") as fh:
        original = fh.read()
    names = [m[0] for m in MUTANTS]
    if len(set(names)) != len(names):
        sys.stdout.write("ERROR duplicate mutant names\n")
        return 2
    for name, fragment, _ in MUTANTS:
        if original.count(fragment) != 1:
            sys.stdout.write("ERROR fragment for %s occurs %d times\n" % (name, original.count(fragment)))
            return 2
    work = tempfile.mkdtemp(prefix="mutants-")
    try:
        for entry in os.listdir(HERE):
            if entry in ("__pycache__", "mutants.py"):
                continue
            src = os.path.join(HERE, entry)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(work, entry))
            else:
                shutil.copy(src, os.path.join(work, entry))
        # the suite scans for stray files, so the harness itself is copied too
        shutil.copy(os.path.join(HERE, "mutants.py"), os.path.join(work, "mutants.py"))
        target = os.path.join(work, "play_craft.py")
        base = run_suite(work)
        sys.stdout.write("baseline suite exit code: %s\n" % base)
        if base != 0:
            sys.stdout.write("ERROR the unmodified suite must pass\n")
            return 2
        killed = 0
        for name, fragment, replacement in MUTANTS:
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(original.replace(fragment, replacement))
            code = run_suite(work)
            verdict = "KILLED" if code != 0 else "SURVIVED"
            if code != 0:
                killed += 1
            sys.stdout.write("%-8s %s%s\n" % (verdict, name, " (timeout)" if code is None else ""))
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(original)
        sys.stdout.write("mutants killed: %d/%d\n" % (killed, len(MUTANTS)))
        return 0 if killed == len(MUTANTS) else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
