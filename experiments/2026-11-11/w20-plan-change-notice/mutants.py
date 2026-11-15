"""Mutation check for w20-plan-change-notice. Run: python3 mutants.py

Each mutant replaces one exact piece of source text in plan_change.py,
writes the result into a temporary copy of this directory (inside a
temporary experiments/2026-11-11/ layout), and runs fixtures.py and the
unittest suite there with the paper-source check skipped. A mutant is
killed when either run fails. The temporary directory is removed at the
end.

The set merges two independent lists, deduplicated by mutated source:
"own" mutants written with the sketch, and "review" mutants from the
independent review of the pull request (methods: flipped comparisons,
dropped checks, isinstance in place of exact type, reordered or unsorted
delivery, detector and summary blind spots, pass-everything and
refuse-everything gates).

Stdlib only. Exit status 0 when every non-equivalent mutant is killed and
every anchor matches exactly once.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = "plan_change.py"

# Mutants that cannot change any observable behaviour. Each is explained.
EQUIVALENT = {
    # known_max: ``known = max(known, v)`` instead of ``known = v``. The
    # assignment runs only for a notice classified valid_notice, and that
    # class already requires ``v > known`` (otherwise it is stale_version),
    # so max(known, v) == v on every path.
    "known_max",
}

M = [
    ('guard_skips_version_check', 'own',
     '        if plan.version != auth_v:',
     '        if False:'),
    ('guard_replans_without_notice', 'own',
     '            if known == auth_v:',
     '            if True:'),
    ('timeout_proceeds_on_stale_plan', 'own',
     '                return Trace(policy, STATUS_ON_EXPIRY[on_expiry], tuple(actions), tuple(acks))',
     '                pass'),
    ('wait_forever', 'own',
     '                if waited < wait_turns:',
     '                if True:'),
    ('wait_counter_not_reset', 'own',
     '                plan = derive_plan(oid, auth_v, auth_t)\n                waited = 0',
     '                plan = derive_plan(oid, auth_v, auth_t)'),
    ('no_fallback_step', 'own',
     '                    actions.append(Action(t, FALLBACK_STEP, i, plan.version, ""))',
     '                    pass'),
    ('fallback_is_consequential', 'own',
     '                    actions.append(Action(t, FALLBACK_STEP, i, plan.version, ""))',
     '                    actions.append(Action(t, CONSEQUENTIAL, i, plan.version, plan.targets[i]))'),
    ('stale_check_off(roll back)', 'own',
     '    if v <= known:\n        return STALE',
     '    if False:\n        return STALE'),
    ('foreign_check_off', 'own',
     '    if noid != oid:\n        return FOREIGN',
     '    if False:\n        return FOREIGN'),
    ('duplicate_check_off', 'own',
     '    if nid in seen:\n        return DUPLICATE',
     '    if False:\n        return DUPLICATE'),
    ('ahead_check_off', 'own',
     '    if v not in auth:\n        return AHEAD',
     '    if False:\n        return AHEAD'),
    ('mismatch_check_off', 'own',
     '    if auth[v] != targets:\n        return MISMATCH',
     '    if False:\n        return MISMATCH'),
    ('delivery_strict_lt', 'own',
     'inbox[delivered][4] <= t',
     'inbox[delivered][4] < t'),
    ('authority_strict_lt', 'own',
     '        if at <= t:\n            cur',
     '        if at < t:\n            cur'),
    ('baseline_acks_nothing', 'own',
     '            acks.append(Ack(t, note[0], note[2], c))',
     '            acks.append(Ack(t, note[0], note[2], c)) if policy == NOTICE_FIRST else None'),
    ('on_expiry_unchecked', 'own',
     'if type(oe) is not str or oe not in ON_EXPIRY:',
     'if False:'),
    ('on_expiry_isinstance', 'own',
     'if type(oe) is not str or',
     'if not isinstance(oe, str) or'),
    ('on_expiry_caller_object', 'own',
     'ON_EXPIRY[ON_EXPIRY.index(oe)])',
     'oe)'),
    ('status_hold_is_done', 'own',
     'HOLD: "held"}',
     'HOLD: "done"}'),
    ('config_not_required', 'own',
     '        cerrs, cfg = check_config(config)\n        errs = errs + cerrs',
     '        cerrs, cfg = check_config(config)\n        cfg = cfg or (1, HOLD)'),
    ('world_isinstance', 'own',
     'if type(world) is not World:',
     'if not isinstance(world, World):'),
    ('change_isinstance', 'own',
     'if type(c) is not Change:',
     'if not isinstance(c, Change):'),
    ('notice_isinstance', 'own',
     'if type(n) is not Notice:',
     'if not isinstance(n, Notice):'),
    ('config_isinstance', 'own',
     'if type(config) is not GuardConfig:',
     'if not isinstance(config, GuardConfig):'),
    ('int_isinstance', 'own',
     'return type(v) is int',
     'return isinstance(v, int)'),
    ('id_isinstance', 'own',
     'return type(s) is str and s != ""',
     'return isinstance(s, str) and s != ""'),
    ('targets_any_sequence', 'own',
     'type(t) is tuple and len(t) > 0',
     'len(t) > 0'),
    ('empty_target_ok', 'own',
     ' and x != "" for x in t)',
     ' for x in t)'),
    ('first_version_any', 'own',
     'if i == 0 and v != 1:',
     'if False:'),
    ('history_order_off', 'own',
     'if i and not (v > hist[i - 1][0] and at > hist[i - 1][2]):',
     'if False:'),
    ('plan_length_off', 'own',
     'if len({len(t) for _, t, _ in hist}) != 1:',
     'if False:'),
    ('turns_order_off', 'own',
     'elif any(b <= a for a, b in zip(turns, turns[1:])):',
     'elif False:'),
    ('wait_turns_negative_ok', 'own',
     'if not (_int(w) and w >= 0):',
     'if not _int(w):'),
    ('notice_version_zero_ok', 'own',
     '_int(v) and v >= 1 and _int(at)',
     '_int(v) and _int(at)'),
    ('policy_type_unchecked', 'own',
     'if type(policy) is not str or policy not in (BASELINE, NOTICE_FIRST):',
     'if policy not in (BASELINE, NOTICE_FIRST, None):'),
    ('no_start_objective_ok', 'own',
     '    if first is None:\n        return Trace',
     '    if False:\n        return Trace'),
    ('detector_version_only', 'own',
     'if a.plan_version == av and at_targets[a.index] == a.target:',
     'if a.plan_version == av:'),
    ('detector_target_only', 'own',
     'if a.plan_version == av and at_targets[a.index] == a.target:',
     'if at_targets[a.index] == a.target:'),
    ('detector_informed_strict', 'own',
     'x.version >= av and x.classification == VALID',
     'x.version > av and x.classification == VALID'),
    ('detector_informed_any_ack', 'own',
     'x.version >= av and x.classification == VALID',
     'x.version >= av'),
    ('detector_ignores_world_errors', 'own',
     '    if errs:\n        return (("config_error",) + errs,)',
     '    if errs and False:\n        return (("config_error",) + errs,)'),
    ('summary_counts_waits', 'own',
     '"steps_completed": sum(a.kind == CONSEQUENTIAL for a in trace.actions),',
     '"steps_completed": len(trace.actions),'),
    ('deny_all', 'review',
     '    errs, snap = check_world(world)\n    if type(policy)',
     "    return Trace(policy, CONFIG_ERROR, (), (), ('x',))\n    errs, snap = check_world(world)\n    if type(policy)"),
    ('pass_all_guard_is_baseline', 'review',
     '        if policy == BASELINE:\n',
     '        if True:\n'),
    ('replan_on_older_notice', 'review',
     '            if known == auth_v:',
     '            if known > plan.version:'),
    ('timeout_status_done', 'review',
     '                return Trace(policy, STATUS_ON_EXPIRY[on_expiry], tuple(actions), tuple(acks))',
     '                return Trace(policy, DONE, tuple(actions), tuple(acks))'),
    ('timeout_acts_stale', 'review',
     '                if on_expiry == SAFE_FALLBACK:',
     '                actions.append(Action(t, CONSEQUENTIAL, i, plan.version, plan.targets[i]))\n                if on_expiry == SAFE_FALLBACK:'),
    ('timeout_proceeds', 'review',
     '                if on_expiry == SAFE_FALLBACK:\n                    actions.append(Action(t, FALLBACK_STEP, i, plan.version, ""))\n                return Trace(',
     '                if True:\n                    pass\n                if False: return Trace('),
    ('missing_oe_defaults_hold', 'review',
     '        errs.append("on_expiry")',
     '        oe = HOLD'),
    ('targets_empty_ok', 'review',
     '    return type(t) is tuple and len(t) > 0 and',
     '    return type(t) is tuple and'),
    ('monotonic_versions_only', 'review',
     '                if i and not (v > hist[i - 1][0] and at > hist[i - 1][2]):',
     '                if i and not (v > hist[i - 1][0]):'),
    ('turns_nondecreasing_ok', 'review',
     '    elif any(b <= a for a, b in zip(turns, turns[1:])):',
     '    elif any(b < a for a, b in zip(turns, turns[1:])):'),
    ('policy_check_off', 'review',
     '    if type(policy) is not str or policy not in (BASELINE, NOTICE_FIRST):',
     '    if False:'),
    ('no_start_check', 'review',
     '    if first is None:\n        return Trace(policy, CONFIG_ERROR, (), (), ("no_objective_at_start",))',
     '    if False:\n        pass'),
    ('classify_stale_lt', 'review',
     '    if v <= known:',
     '    if v < known:'),
    ('classify_no_ahead_time', 'review',
     '    auth = {hv: ht for hv, ht, hat in hist if hat <= t}',
     '    auth = {hv: ht for hv, ht, hat in hist}'),
    ('known_from_mismatch', 'review',
     '            if c == VALID:',
     '            if c in (VALID, MISMATCH):'),
    ('known_from_ahead', 'review',
     '            if c == VALID:',
     '            if c in (VALID, AHEAD):'),
    ('known_max', 'review',
     '                known = note[2]',
     '                known = max(known, note[2])'),
    ('seen_only_valid', 'review',
     '            seen.add(note[0])',
     '            if c == VALID: seen.add(note[0])'),
    ('deliver_everything_early', 'review',
     'inbox[delivered][4] <= t:',
     'inbox[delivered][4] <= t + 10 ** 9:'),
    ('inbox_sort_by_id', 'review',
     '    inbox = sorted(nots, key=lambda x: (x[4], x[0]))',
     '    inbox = sorted(nots, key=lambda x: x[0])'),
    ('inbox_unsorted', 'review',
     '    inbox = sorted(nots, key=lambda x: (x[4], x[0]))',
     '    inbox = list(nots)'),
    ('wait_le', 'review',
     '                if waited < wait_turns:',
     '                if waited <= wait_turns:'),
    ('wait_never', 'review',
     '                if waited < wait_turns:',
     '                if False:'),
    ('no_break', 'review',
     '        if i >= n:\n            break',
     '        if False:\n            break'),
    ('final_status_done_always', 'review',
     '    return Trace(policy, DONE if i >= n else INCOMPLETE,',
     '    return Trace(policy, DONE,'),
    ('baseline_skips_acks', 'review',
     '            acks.append(Ack(t, note[0], note[2], c))',
     '            acks.append(Ack(t, note[0], note[2], c)) if policy != BASELINE else None'),
    ('summary_adds_versions', 'review',
     '        "status": trace.status,\n    }',
     '        "status": trace.status,\n        "versions": tuple(a.plan_version for a in trace.actions),\n    }'),
    ('detector_blind', 'review',
     '    out = []\n    for k, a in enumerate(trace.actions):',
     '    return ()\n    out = []\n    for k, a in enumerate(trace.actions):'),
    ('detector_informed_always', 'review',
     '        informed = any(x.at <= a.at and x.version >= av and x.classification == VALID\n                       for x in trace.acks)',
     '        informed = True'),
    ('detector_informed_lt', 'review',
     '        informed = any(x.at <= a.at and',
     '        informed = any(x.at < a.at and'),
    ('detector_checks_waits', 'review',
     '        if a.kind != CONSEQUENTIAL:\n            continue\n        auth = authoritative_at(hist, a.at)',
     '        auth = authoritative_at(hist, a.at)'),
]


def _copy_layout(tmp, name):
    day = os.path.join(tmp, name, "experiments", "2026-11-11")
    d = os.path.join(day, "w20-plan-change-notice")
    os.makedirs(d)
    for f in os.listdir(HERE):
        p = os.path.join(HERE, f)
        if os.path.isfile(p) and not f.endswith(".pyc"):
            shutil.copy(p, d)
    index = os.path.join(HERE, "..", "README.md")
    if os.path.isfile(index):
        shutil.copy(index, os.path.join(day, "README.md"))
    return d


def _passes(d):
    env = dict(os.environ, W20PCN_SOURCES=os.path.join(d, "no-sources"), PYTHONDONTWRITEBYTECODE="1")
    a = subprocess.run([sys.executable, "-B", "fixtures.py"], cwd=d, capture_output=True, env=env)
    b = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_plan_change.py"], cwd=d,
                       capture_output=True, env=env)
    return a.returncode == 0 and b.returncode == 0


def main():
    with open(os.path.join(HERE, TARGET), encoding="utf-8") as f:
        src = f.read()
    tmp = tempfile.mkdtemp(prefix="w20pcn-mutants-")
    killed, survivors, equivalent, bad_anchor = 0, [], [], []
    try:
        base = _copy_layout(tmp, "base")
        if not _passes(base):
            print("baseline: FAIL (suite or fixtures fail on unmutated code)")
            return 2
        print("baseline: OK")
        for k, (name, origin, old, new) in enumerate(M):
            if src.count(old) != 1:
                bad_anchor.append(name)
                print("%-34s %-6s ANCHOR(%d)" % (name, origin, src.count(old)))
                continue
            d = _copy_layout(tmp, "m%03d" % k)
            with open(os.path.join(d, TARGET), "w", encoding="utf-8") as f:
                f.write(src.replace(old, new, 1))
            survived = _passes(d)
            shutil.rmtree(os.path.dirname(os.path.dirname(os.path.dirname(d))))
            if not survived:
                killed += 1
                verdict = "killed"
            elif name in EQUIVALENT:
                equivalent.append(name)
                verdict = "survived (equivalent)"
            else:
                survivors.append(name)
                verdict = "SURVIVED"
            print("%-34s %-6s %s" % (name, origin, verdict))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    own = sum(o == "own" for _, o, _, _ in M)
    print("summary: %d mutants (%d own, %d review, deduplicated); killed %d; "
          "equivalent %d %s; survivors %d %s; bad anchors %d" % (
              len(M), own, len(M) - own, killed, len(equivalent), equivalent,
              len(survivors), survivors, len(bad_anchor)))
    return 1 if survivors or bad_anchor else 0


if __name__ == "__main__":
    sys.exit(main())
