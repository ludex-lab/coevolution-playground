"""Mutation check for w21-unused-contradiction. Run: python3 -B mutants.py

Each mutant replaces one exact piece of source text in one file, writes
the result into a temporary copy of this directory (inside a temporary
experiments/2026-11-12/ layout, with the day README copied to the day
folder as README.md), and runs fixtures.py and the unittest suite there
with the paper-source check skipped (W21UC_SOURCES unset). A mutant is
killed when either run fails. The temporary directory is removed at the
end.

Two lists, reported separately:
  code   mutants of unused_contradiction.py: a flag counted as a repair,
         repairs that match any state, any time or any holder, a relapse
         after the repair excused, unused or unlabeled evidence passed,
         timeouts that succeed or need no declared on_expiry, isinstance
         in place of exact type, dropped validator branches, no
         try/except, a guessing detector.
  world  mutants of the test world (fixtures.py, the test file,
         paper_evidence.json, the day README): fixtures that no longer
         have the shape their name claims, a thinner grid, wrong expected
         labels, edited quotes or status, a doubled footer or lost row.

Stdlib only. Exit status 0 when every non-equivalent mutant is killed and
every anchor matches exactly once.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = "unused_contradiction.py"
FIX = "fixtures.py"
TEST = "test_unused_contradiction.py"
EVID = "paper_evidence.json"
SLUG = "w21-unused-contradiction"
DAYF = "_day/README.md"   # label for the day README; copied to the day folder as README.md
DAY = "2026-11-12"


def _day_src():
    """The day README, resolved like the tests: ../README.md in the repo
    layout (this folder inside experiments/2026-11-12/), else _day/README.md
    in a flat draft copy. None when neither exists."""
    parent = os.path.dirname(HERE)
    repo = os.path.join(parent, "README.md")
    if os.path.basename(parent) == DAY and os.path.isfile(repo):
        return repo
    flat = os.path.join(HERE, "_day", "README.md")
    return flat if os.path.isfile(flat) else None


def _src(fname):
    return _day_src() if fname == DAYF else os.path.join(HERE, fname)

# Mutants that cannot change any observable behaviour. Each is explained.
EQUIVALENT = set()
EQUIVALENT_WORLD = set()

M = [
    # flag is not a repair
    ('flag_counts_as_repair',
     '            if policy == FLAG_AS_REPAIR:\n                continue\n',
     '            continue\n'),
    ('flag_any_time',
     'any(f_index > e_index and target == h_id',
     'any(target == h_id'),
    ('flag_any_target',
     'any(f_index > e_index and target == h_id',
     'any(f_index > e_index'),
    # repair must remove the contradicted holder, after the evidence
    ('repair_any_state',
     '                if r_index > e_index and removed == h_id]',
     '                if r_index > e_index]'),
    ('repair_any_time',
     '                if r_index > e_index and removed == h_id]',
     '                if removed == h_id]'),
    ('repair_any_holder',
     '                if r_index > e_index and removed == h_id]',
     '                if r_index > e_index and removed is not None]'),
    # a re-assertion after the repair is a relapse (review F1)
    ('reassert_check_dropped',
     '            if any(a_index > first and a_state == state_of[h_id] for a_index, a_state in asserts):\n',
     '            if False:\n'),
    ('reassert_any_state',
     'if any(a_index > first and a_state == state_of[h_id] for a_index, a_state in asserts):',
     'if any(a_index > first for a_index, a_state in asserts):'),
    ('reassert_direction_flipped',
     'if any(a_index > first and a_state == state_of[h_id] for a_index, a_state in asserts):',
     'if any(a_index < first and a_state == state_of[h_id] for a_index, a_state in asserts):'),
    ('reassert_not_unresolved',
     '            unresolved.append((e_id, h_id, REASSERTED_AFTER_REPAIR))\n',
     '            continue\n'),
    ('reassert_branch_dropped',
     '    elif any(r == REASSERTED_AFTER_REPAIR for _, _, r in unresolved):\n'
     '        verdict, reason = FAIL, REASSERTED_AFTER_REPAIR\n',
     ''),
    ('reassert_excused_by_flag_policy',
     '        if status == "reasserted":\n            unresolved.append((e_id, h_id, REASSERTED_AFTER_REPAIR))\n',
     '        if status == "reasserted":\n            if policy == FLAG_AS_REPAIR:\n                continue\n'
     '            unresolved.append((e_id, h_id, REASSERTED_AFTER_REPAIR))\n'),
    ('repair_not_removing',
     'holder.pop(step["state"], None)',
     'holder.get(step["state"])'),
    ('overwrite_ignored',
     '            holder[step["state"]] = step["id"]\n',
     '            holder.setdefault(step["state"], step["id"])\n'),
    ('ineffective_not_reported',
     'ineffective = tuple(sorted(r_id for _, r_id, _ in removals if r_id not in effective))',
     'ineffective = ()'),
    ('neutral_as_contradiction',
     '            elif step["contradicts"] is not None:\n',
     '            else:\n'),
    # closing rules
    ('unused_branch_dropped',
     '    elif any(r == UNUSED_CONTRADICTION for _, _, r in unresolved):\n'
     '        verdict, reason = FAIL, UNUSED_CONTRADICTION\n',
     ''),
    ('flag_branch_dropped',
     '    elif unresolved:\n        verdict, reason = FAIL, FLAG_WITHOUT_REPAIR\n',
     ''),
    ('unlabeled_passes',
     '    elif unlabeled:\n',
     '    elif False:\n'),
    ('unlabeled_not_tracked',
     '                unlabeled.append(step["id"])\n',
     '                pass\n'),
    ('task_done_ignored',
     '    if not episode["task_done"]:\n',
     '    if False:\n'),
    ('symptom_baseline_is_gate',
     '    elif policy == SYMPTOM_ONLY:\n',
     '    elif False:\n'),
    # waits
    ('expiry_skipped',
     '        if wait["expired"]:\n',
     '        if False:\n'),
    ('expiry_retains_success',
     'return _record(eid, pol, action, EXPIRED, verdict, reason, action,',
     'return _record(eid, pol, verdict if verdict == SUCCESS else action, EXPIRED, verdict, reason, action,'),
    ('expiry_prior_dropped',
     'return _record(eid, pol, action, EXPIRED, verdict, reason, action,',
     'return _record(eid, pol, action, EXPIRED, None, None, action,'),
    ('on_expiry_optional',
     '        return "wait declares a timeout without on_expiry"\n',
     '        return None\n'),
    ('on_expiry_any_str',
     '    if _canonical(wait["on_expiry"], ON_EXPIRY_VALUES) is None:\n',
     '    if not _is_str(wait["on_expiry"]):\n'),
    ('on_expiry_caller_object',
     '        action = _canonical(wait["on_expiry"], ON_EXPIRY_VALUES)\n',
     '        action = wait["on_expiry"]\n'),
    ('timeout_isinstance',
     '    if type(timeout) is not int or timeout <= 0:\n',
     '    if not isinstance(timeout, int) or timeout <= 0:\n'),
    ('timeout_unchecked',
     '    if type(timeout) is not int or timeout <= 0:\n',
     '    if False:\n'),
    ('expired_any_type',
     '    if type(wait.get("expired")) is not bool:\n',
     '    if "expired" not in wait:\n'),
    # exact types and validation
    ('str_isinstance',
     '    return type(value) is str\n',
     '    return isinstance(value, str)\n'),
    ('dict_isinstance',
     '    return type(value) is dict\n',
     '    return isinstance(value, dict)\n'),
    ('steps_any_sequence',
     '    if type(steps) is not list or not steps:\n',
     '    if not isinstance(steps, (list, tuple)) or not steps:\n'),
    ('task_done_truthy',
     '    if type(episode["task_done"]) is not bool:\n',
     '    if episode["task_done"] not in (True, False):\n'),
    ('labels_not_declared',
     '    if _canonical(episode["contradiction_labels"], LABEL_MODES) is None:\n',
     '    if False:\n'),
    ('contradicts_unknown_id',
     '                    if label not in holders:\n'
     '                        return "contradicts must name an earlier belief or act"\n',
     ''),
    ('contradicts_any_type',
     '                    if not _is_str(label):\n'
     '                        return "contradicts must be None or a step id"\n',
     ''),
    ('flag_target_unchecked',
     '            if not _is_str(step["target"]) or step["target"] not in holders:\n',
     '            if not _is_str(step["target"]):\n'),
    ('repair_state_unchecked',
     '            if not _is_str(step["state"]) or step["state"] not in states:\n',
     '            if not _is_str(step["state"]):\n'),
    ('duplicate_ids',
     '        if sid in seen_ids:\n            return "duplicate step id"\n',
     ''),
    ('unknown_fields',
     '        if _canonical(key, required + optional) is None:\n'
     '            return "unknown %s field" % where\n',
     ''),
    ('step_key_types',
     '        for key in step:\n            if not _is_str(key):\n'
     '                return "step field names must be strings"\n',
     ''),
    ('kind_not_canonical',
     '        kind = _canonical(step.get("kind"), KINDS)\n',
     '        kind = step.get("kind")\n'),
    ('empty_state',
     '            if not _is_str(step["state"]) or not step["state"]:\n',
     '            if not _is_str(step["state"]):\n'),
    # never raise, record hygiene
    ('no_try',
     '    except Exception:\n',
     '    except ZeroDivisionError:\n'),
    ('policy_echoed',
     '        return _record(None, INVALID_POLICY, CONFIG_ERROR, CONFIG_ERROR)\n',
     '        return _record(None, policy, CONFIG_ERROR, CONFIG_ERROR)\n'),
    ('policy_isinstance',
     '    pol = _canonical(policy, POLICIES)\n    if pol is None:\n',
     '    pol = policy if isinstance(policy, str) and policy in POLICIES else None\n    if pol is None:\n'),
    ('summarise_any_iterable',
     '    if type(episodes) is not list:\n',
     '    if episodes is None:\n'),
    ('validate_key_types_late',
     '    err = _check_keys(episode, REQUIRED_FIELDS, OPTIONAL_FIELDS, "episode")\n',
     '    err = None if "steps" in episode else _check_keys(episode, REQUIRED_FIELDS, OPTIONAL_FIELDS, "episode")\n'),
    # no oracle
    ('detector_guesses',
     '    return {"verdict": ON_UNMEASURED, "axis": CONTRADICTION_DETECTION}\n',
     '    return {"verdict": FAIL if first != second else SUCCESS, "axis": CONTRADICTION_DETECTION}\n'),
    ('localiser_guesses',
     '    return {"verdict": ON_UNMEASURED, "axis": (ORIGIN_LOCALISATION, PHASE_LOCALISATION)}\n',
     '    return {"verdict": FAIL, "axis": (ORIGIN_LOCALISATION, PHASE_LOCALISATION)}\n'),
]

W = [
    ('status_reassert_as_repaired', FIX,
     '    "repair_then_reassert": "reasserted",\n',
     '    "repair_then_reassert": "repaired",\n'),
    ('reasserted_fixture_without_relapse', FIX,
     '        belief("b1", "total"), evidence("e1", "b1"), repair("r1", "total"), belief("b3", "total")]),\n',
     '        belief("b1", "total"), evidence("e1", "b1"), repair("r1", "total")]),\n'),
    ('reassert_shape_without_relapse', FIX,
     '                                     evidence("e1", "b1"), repair("r1", "total"),\n'
     '                                     belief("b3", "total")],\n',
     '                                     evidence("e1", "b1"), repair("r1", "total")],\n'),
    ('day_footer_twice', DAYF,
     'Do not merge experiment PRs without Ork review.\n',
     'Do not merge experiment PRs without Ork review.\n\nDo not merge experiment PRs without Ork review.\n'),
    ('day_row_dropped', DAYF,
     '- [w21-unused-contradiction](w21-unused-contradiction/)',
     '- w21-unused-contradiction'),
    ('status_table_wrong', FIX,
     '    "repair_other_state": "unused",\n',
     '    "repair_other_state": "repaired",\n'),
    ('other_state_becomes_real_repair', FIX,
     '                                   evidence("e1", "b1"), repair("r1", "route")],\n',
     '                                   evidence("e1", "b1"), repair("r1", "total")],\n'),
    ('overwrite_removed', FIX,
     '                                       evidence("e1", "b1"), belief("b3", "total"),\n',
     '                                       evidence("e1", "b1"),\n'),
    ('flag_before_moved_after', FIX,
     '                                     flag("f1", "b1"), evidence("e1", "b1")],\n',
     '                                     evidence("e1", "b1"), flag("f1", "b1")],\n'),
    ('extras_thinned', FIX,
     'EXTRAS = ("neutral", "unlabeled")\n',
     'EXTRAS = ("neutral",)\n'),
    ('task_done_never_false', FIX,
     'for t in (True, False)',
     'for t in (True, True)'),
    ('unlabeled_extra_labeled', FIX,
     '    steps.append(evidence("e2", None) if extra == "neutral" else unlabeled("e2"))\n',
     '    steps.append(evidence("e2", None))\n'),
    ('labels_inferred', FIX,
     '    ep = {"episode_id": eid, "contradiction_labels": "declared_fixture",\n',
     '    ep = {"episode_id": eid, "contradiction_labels": "inferred",\n'),
    ('two_repaired_loses_one', FIX,
     '        repair("r1", "route"), repair("r2", "total")]), (U.SUCCESS, U.CONSUMED)),\n',
     '        repair("r2", "total")]), (U.SUCCESS, U.CONSUMED)),\n'),
    ('neutral_fixture_labeled', FIX,
     '    "neutral_only": (episode("neutral_only", [belief("b1", "total"), evidence("e1", None)]),\n',
     '    "neutral_only": (episode("neutral_only", [belief("b1", "total"), evidence("e1", "b1")]),\n'),
    ('before_evidence_is_plain_unused', FIX,
     '    "d_before_evidence": (episode("d_before_evidence", RESPONSES["repair_before_evidence"]()),\n',
     '    "d_before_evidence": (episode("d_before_evidence", RESPONSES["none"]()),\n'),
    ('other_state_is_plain_unused', FIX,
     '    "d_other_state": (episode("d_other_state", RESPONSES["repair_other_state"]()),\n',
     '    "d_other_state": (episode("d_other_state", RESPONSES["none"]()),\n'),
    ('flag_only_has_no_flag', FIX,
     '    "b_flag_only": (episode("b_flag_only", RESPONSES["flag"]()), (U.FAIL, U.FLAG_WITHOUT_REPAIR)),\n',
     '    "b_flag_only": (episode("b_flag_only", RESPONSES["none"]()), (U.FAIL, U.FLAG_WITHOUT_REPAIR)),\n'),
    ('unlabeled_fixture_labeled', FIX,
     '    "e_unlabeled": (episode("e_unlabeled", [belief("b1", "total"), unlabeled("e1")]),\n',
     '    "e_unlabeled": (episode("e_unlabeled", [belief("b1", "total"), evidence("e1", None)]),\n'),
    ('figure_list_thinned', TEST,
     '("35 of ", "95"),\n',
     '\n'),
    ('banned_digest_dropped', TEST,
     '    BANNED_DIGESTS = (\n        "',
     '    BANNED_DIGESTS = (\n        "0" + "'),
    ('quote_edited', EVID,
     'of those no agent acted on it.',
     'of those no agent used it.'),
    ('claims_status_flipped', EVID,
     '  "status": "UNVERIFIED",\n  "note"',
     '  "status": "VERIFIED",\n  "note"'),
]


def _copy_layout(tmp, name):
    d = os.path.join(tmp, name, "experiments", "2026-11-12", SLUG)
    os.makedirs(d)
    for f in os.listdir(HERE):
        p = os.path.join(HERE, f)
        if os.path.isfile(p) and not f.endswith(".pyc"):
            shutil.copy(p, d)
    shutil.copy(_day_src(), os.path.join(os.path.dirname(d), "README.md"))
    return d


def _dest(d, fname):
    if fname == DAYF:
        return os.path.join(os.path.dirname(d), "README.md")
    return os.path.join(d, fname)


def _passes(d):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("W21UC_SOURCES", None)
    a = subprocess.run([sys.executable, "-B", "fixtures.py"], cwd=d, capture_output=True, env=env)
    b = subprocess.run([sys.executable, "-B", "-m", "unittest", TEST], cwd=d,
                       capture_output=True, env=env)
    return a.returncode == 0 and b.returncode == 0


def _run(tmp, label, items, equivalent_names):
    killed, survivors, equivalent, bad_anchor = 0, [], [], []
    for k, (name, fname, old, new) in enumerate(items):
        with open(_src(fname), encoding="utf-8") as f:
            src = f.read()
        if src.count(old) != 1:
            bad_anchor.append(name)
            print("%-36s ANCHOR(%d)" % (name, src.count(old)))
            continue
        sub = "%s%03d" % (label, k)
        d = _copy_layout(tmp, sub)
        with open(_dest(d, fname), "w", encoding="utf-8") as f:
            f.write(src.replace(old, new, 1))
        survived = _passes(d)
        shutil.rmtree(os.path.join(tmp, sub))
        if not survived:
            killed += 1
            verdict = "killed"
        elif name in equivalent_names:
            equivalent.append(name)
            verdict = "survived (equivalent)"
        else:
            survivors.append(name)
            verdict = "SURVIVED"
        print("%-36s %s" % (name, verdict))
    print("summary %s: %d mutants; killed %d; equivalent %d %s; survivors %d %s; bad anchors %d %s" % (
        label, len(items), killed, len(equivalent), sorted(equivalent), len(survivors), survivors,
        len(bad_anchor), bad_anchor))
    return bool(survivors or bad_anchor)


def main():
    if _day_src() is None:
        print("baseline: FAIL (no day README at ../README.md or _day/README.md)")
        return 2
    tmp = tempfile.mkdtemp(prefix="w21uc-mutants-")
    try:
        base = _copy_layout(tmp, "base")
        if not _passes(base):
            print("baseline: FAIL (suite or fixtures fail on unmutated code)")
            return 2
        print("baseline: OK")
        print("-- code mutants (%s)" % TARGET)
        bad_code = _run(tmp, "code", [(n, TARGET, o, w) for n, o, w in M], EQUIVALENT)
        print("-- world mutants (%s, %s, %s, %s)" % (FIX, TEST, EVID, DAYF))
        bad_world = _run(tmp, "world", W, EQUIVALENT_WORLD)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if bad_code or bad_world else 0


if __name__ == "__main__":
    sys.exit(main())
