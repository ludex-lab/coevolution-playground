"""Mutation check for w20-evidence-linked-memory. Run: python3 mutants.py

Two kinds of mutant, each replacing one exact piece of source text:
- behaviour mutants change evidence_memory.py (the rule);
- world mutants change fixtures.py (the test worlds): each one removes or
  breaks the adversarial shape of a fixture, often so that its expected
  outcome still holds. They check that the suite notices when a world is
  made easy, not only when the code is wrong.
Each mutant is written into a temporary copy of this directory (inside a
temporary experiments/2026-11-11/ layout), and fixtures.py and the unittest
suite are run there with W20ELM_SOURCES removed from the environment, so the
lab-source checks are skipped. A mutant is killed when either run fails; the
report names which run failed. Every anchor must match exactly once. The
temporary directory is removed at the end.

Stdlib only. Exit status 0 when every non-equivalent mutant is killed and
every anchor matches.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RULE, WORLD = "evidence_memory.py", "fixtures.py"
SLUG = "w20-evidence-linked-memory"

# Mutants that cannot change any observable behaviour. Each is explained.
EQUIVALENT = {
    # conflict_skips_self_check: an insight never disagrees with itself
    # (same verb, same arg), so dropping the self-exclusion adds nothing.
    "conflict_skips_self_check",
    # declaration_returned_as_given: the value has already passed an exact
    # str check and membership in ON_UNRESOLVED, so the caller's string is
    # equal to the module constant, and every later use is an equality test
    # or a dict lookup by that equal key.
    "declaration_returned_as_given",
}

M = [
    ('drop_missing_detail_trigger',
     '    if not has_detail(ins):\n        out.append(MISSING_DETAIL)',
     '    if False:\n        out.append(MISSING_DETAIL)'),
    ('drop_conflict_trigger',
     '        out.append(CONFLICT)',
     '        pass'),
    ('drop_failed_origin_trigger',
     '        out.append(FAILED_ORIGIN)',
     '        pass'),
    ('missing_outcome_defaults_clean',
     '    claimed = ins.outcome == SUCCESS',
     '    claimed = ins.outcome in (SUCCESS, None)'),
    ('outcome_compared_loosely',
     '    claimed = ins.outcome == SUCCESS',
     '    claimed = str(ins.outcome).strip().lower() == SUCCESS'),
    ('outcome_prefix_match',
     '    claimed = ins.outcome == SUCCESS',
     '    claimed = str(ins.outcome).startswith(SUCCESS)'),
    ('run_label_ignored',
     '    labelled = run_label(ins, memory) == SUCCESS',
     '    labelled = True'),
    ('run_label_prefix_match',
     '    labelled = run_label(ins, memory) == SUCCESS',
     '    labelled = str(run_label(ins, memory)).startswith(SUCCESS)'),
    ('run_label_absent_is_success',
     '    labelled = run_label(ins, memory) == SUCCESS',
     '    labelled = run_label(ins, memory) in (SUCCESS, None)'),
    ('failed_run_gives_evidence',
     '    if not run_ok:\n        return REJECTED, None',
     '    if False:\n        return REJECTED, None'),
    ('evidence_trusts_insight_claim',
     '            run_ok = run_label(ins, memory) == SUCCESS',
     '            run_ok = ins.outcome == SUCCESS'),
    ('evidence_from_any_run',
     '            run_ok = run_label(ins, memory) == SUCCESS',
     '            run_ok = True'),
    ('loader_outcome_defaults_success',
     'arg, outcome, link = _opt_str(d, "arg"), _opt_str(d, "outcome"), _opt_str(d, "summary")',
     'arg, outcome, link = _opt_str(d, "arg"), d.get("outcome", SUCCESS), _opt_str(d, "summary")'),
    ('empty_arg_counts_as_detail',
     '    return type(ins.arg) is str and ins.arg != ""',
     '    return type(ins.arg) is str'),
    ('missing_arg_defaults_detail',
     '    return type(ins.arg) is str and ins.arg != ""',
     '    return ins.arg is None or (type(ins.arg) is str and ins.arg != "")'),
    ('summary_link_guessed',
     '    sid = ins.summary_id\n',
     '    sid = ins.summary_id or "s-" + ins.insight_id\n'),
    ('trajectory_link_guessed',
     '    tid = summ.traj_id\n',
     '    tid = summ.traj_id or "t-" + ins.insight_id\n'),
    ('unreadable_read_as_empty',
     '    if tr is None or tr.steps is None:\n        return None',
     '    if tr is not None and tr.steps is None:\n        tr = Trajectory(tr.traj_id, tr.key, ())\n    if tr is None:\n        return None'),
    ('summary_link_any',
     '    return next((s for s in memory.summaries if s.summary_id == sid), None)',
     '    return next((s for s in memory.summaries if s.summary_id == sid), '
     'memory.summaries[0] if memory.summaries else None)'),
    ('trajectory_link_any',
     '    tr = next((t for t in memory.trajectories if t.traj_id == tid), None)',
     '    tr = next((t for t in memory.trajectories if t.traj_id == tid), '
     'memory.trajectories[0] if memory.trajectories else None)'),
    ('trajectory_key_case_insensitive',
     '    if tr.key != ins.key:\n        return None',
     '    if tr.key.lower() != ins.key.lower():\n        return None'),
    ('trajectory_key_not_checked',
     '    if tr.key != ins.key:\n        return None',
     '    if False:\n        return None'),
    ('trajectory_loses_on_correction',
     '    return CORRECTED, ev\n',
     '    return CORRECTED, (ins.verb, ins.arg)\n'),
    ('rejected_insight_followed',
     '    if not ok:\n        return REJECTED, None',
     '    if not ok:\n        return REJECTED, (ins.verb, ins.arg if has_detail(ins) else "")'),
    ('first_ok_step_is_evidence',
     '    ev = (ok[-1].verb, ok[-1].arg)',
     '    ev = (ok[0].verb, ok[0].arg)'),
    ('clean_beats_trajectory',
     '    if evidence is not None:\n        action = evidence',
     '    if evidence is not None and not clean:\n        action = evidence'),
    ('agrees_ignores_arg',
     '    return ins.verb == ev[0] and (not has_detail(ins) or ins.arg == ev[1])',
     '    return ins.verb == ev[0]'),
    ('conflict_verb_needs_details',
     '    if a.verb != b.verb:\n        return True',
     '    if a.verb != b.verb:\n        return has_detail(a) and has_detail(b)'),
    ('conflict_on_verb_only',
     '    return has_detail(a) and has_detail(b) and a.arg != b.arg',
     '    return False'),
    ('conflict_skips_self_check',
     'o.insight_id != ins.insight_id and _disagree(ins, o)',
     '_disagree(ins, o)'),
    ('descend_every_triggered',
     '        if evidence is None:\n            descends += 1',
     '        if True:\n            descends += 1'),
    ('stop_after_first_descend',
     '        if evidence is None:\n            descends += 1',
     '        if descends == 0:\n            descends += 1'),
    ('descends_not_counted',
     '            descends += 1',
     '            descends += 0'),
    ('link_checked_only_when_triggered',
     '        tr = resolve_link(ins, memory)\n        if tr is None:',
     '        tr = resolve_link(ins, memory)\n        if tr is None and triggers(ins, rel, memory):'),
    ('fallback_acts_on_insight',
     '        action = task.default if oe == SAFE_FALLBACK else None',
     '        action = (rel[0].verb, rel[0].arg) if oe == SAFE_FALLBACK else None'),
    ('unresolved_status_done',
     '        return STATUS_ON_UNRESOLVED[oe], action, 0, verdicts',
     '        return DONE, action, 0, verdicts'),
    ('relevance_ignores_key',
     '(i for i in memory.insights if i.key == task.key)',
     '(i for i in memory.insights)'),
    ('relevance_key_casefold',
     '(i for i in memory.insights if i.key == task.key)',
     '(i for i in memory.insights if i.key.lower() == task.key.lower())'),
    ('on_unresolved_accepts_permit_word',
     '    if type(oe) is not str or oe not in ON_UNRESOLVED:',
     '    if type(oe) is str and oe.lower() == "al" + "low":\n        return HOLD\n    if type(oe) is not str or oe not in ON_UNRESOLVED:'),
    ('missing_declaration_defaults_hold',
     '    oe = cfg.on_unresolved\n',
     '    oe = cfg.on_unresolved if cfg.on_unresolved is not None else HOLD\n'),
    ('declaration_isinstance_str',
     '    if type(oe) is not str or oe not in ON_UNRESOLVED:',
     '    if not isinstance(oe, str) or oe not in ON_UNRESOLVED:'),
    ('config_isinstance',
     '    if type(cfg) is not Config:',
     '    if not isinstance(cfg, Config):'),
    ('declaration_returned_as_given',
     '    return ON_UNRESOLVED[ON_UNRESOLVED.index(oe)]',
     '    return oe'),
    ('declaration_only_checked_with_memory',
     '    oe = _declared(cfg)\n    if oe is None:',
     '    oe = _declared(cfg)\n    if oe is None and memory.insights:'),
    ('bare_agent_gets_the_read_rule',
     '    if agent == BARE:',
     '    if agent == BARE and False:'),
    ('empty_agent_reads_memory',
     '    if agent == EMPTY:\n        return out(DONE, task.default)',
     '    if agent == EMPTY and not memory.insights:\n        return out(DONE, task.default)'),
    ('bare_missing_arg_left_empty',
     '    return (ins.verb, ins.arg if has_detail(ins) else task.default[1])',
     '    return (ins.verb, ins.arg)'),
    ('passed_ignores_answer',
     '        and action == task.answer',
     '        and True'),
    ('fallback_never_passes',
     'passed = status in (DONE, STATUS_ON_UNRESOLVED[SAFE_FALLBACK]) and',
     'passed = status in (DONE,) and'),
    ('duplicate_ids_accepted',
     '        if len(ids) != len(set(ids)):\n            return False',
     '        if False:\n            return False'),
    ('insight_isinstance',
     '        if type(i) is not Insight or',
     '        if not isinstance(i, Insight) or'),
    ('step_list_accepted',
     '            if type(t.steps) is not tuple:\n                return False',
     '            if False:\n                return False'),
    ('loader_bad_steps_read_as_empty',
     '    if type(raw) is not list:\n        return None',
     '    if type(raw) is not list:\n        return ()'),
    ('loader_unknown_field_accepted',
     '        if type(d) is not dict or set(d) - _INSIGHT_FIELDS:',
     '        if type(d) is not dict:'),
    ('loader_any_type_accepted',
     '    return v if v is None or type(v) is str else _BAD',
     '    return v'),
    ('task_answer_not_checked',
     '    return type(t) is Task and _is_str(t.task_id) and _is_str(t.key) and _is_action(t.answer) \\',
     '    return type(t) is Task and _is_str(t.task_id) and _is_str(t.key) \\'),
    ('memory_not_validated',
     '    if not _valid_memory(memory):\n        return out(CONFIG_ERROR)',
     '    if memory is None:\n        return out(CONFIG_ERROR)'),
]

# World mutants on fixtures.py. Most leave the fixture's expected outcome as is, so
# only a WorldShapes test can notice that the adversarial shape is gone.
W = [
    ('world_f1_claim_not_success',
     '("run_label_failure_beats_claim", lesson("i1", WRONG, SO,',
     '("run_label_failure_beats_claim", lesson("i1", WRONG, "failure",'),
    ('world_f1_label_set_loses_successful',
     '[(WRONG, OK)], run="successful")',
     '[(WRONG, OK)], run="failure")'),
    ('world_f1_label_set_loses_trailing_space',
     '[(WRONG, OK)], run="success ")',
     '[(WRONG, OK)], run=ABSENT)'),
    ('world_f2a_failed_ok_step_honest',
     '("failed_run_ok_step_is_wrong", lesson("i1", WRONG, "failure", [(WRONG, OK)])',
     '("failed_run_ok_step_is_wrong", lesson("i1", WRONG, "failure", [(RIGHT, OK)])'),
    ('world_f2a_misleading_step_removed',
     '[(OTHER, ERR), (WRONG, OK)]',
     '[(OTHER, ERR), (WRONG, ERR)]'),
    ('world_f2b_failed_run_has_no_ok_step',
     'lesson("i0", WRONG, "failure", [(RIGHT, ERR), (WRONG, OK)])',
     'lesson("i0", WRONG, "failure", [(RIGHT, ERR), (WRONG, ERR)])'),
    ('world_f2b_failed_sorts_last',
     'lesson("i0", WRONG, "failure", [(RIGHT, ERR), (WRONG, OK)])',
     'lesson("i9", WRONG, "failure", [(RIGHT, ERR), (WRONG, OK)])'),
    ('world_f3_good_chain_removed',
     '("summary_missing_beside_good_chain", merge(lesson("i1", RIGHT, SO, [(RIGHT, OK)]),',
     '("summary_missing_beside_good_chain", merge(lesson("i1", RIGHT, SO, [(RIGHT, OK)], key="bridge"),'),
    ('world_f3_key_case_becomes_other_word',
     'traj_key="GATE")',
     'traj_key="BRIDGE")'),
    ('world_f3_relevance_case_becomes_other_word',
     'lesson("i1", WRONG, key="GATE")',
     'lesson("i1", WRONG, key="bridge")'),
    ('world_f5_successful_claim_removed',
     'lesson("i1", WRONG, "successful",',
     'lesson("i1", WRONG, "Success",'),
    ('world_f5_trailing_space_claim_removed',
     'lesson("i1", WRONG, "success ",',
     'lesson("i1", WRONG, "failure",'),
    ('world_f5_near_miss_tuple_trimmed',
     'NEAR_MISS = ("Success", "SUCCESS", " success", "", "successful", "success ")',
     'NEAR_MISS = ("Success", "SUCCESS", " success", "")'),
    ('world_f5_verb_conflict_gets_detail',
     'lesson("i2", RIGHT, SO, [], arg=None))',
     'lesson("i2", RIGHT, SO, []))'),
    ('world_gen_mismatch_claim_not_success',
     'rec = lesson(iid(), wrong, SO, [(wrong, OK)], key=key,',
     'rec = lesson(iid(), wrong, "failure", [(wrong, OK)], key=key,'),
    ('world_gen_misleads_step_honest',
     '[(truth, ERR), (w2, OK)], key=key)',
     '[(truth, ERR), (w2, ERR)], key=key)'),
    ('world_gen_sorts_first_step_honest',
     'lesson(lo, wrong, "failure", [(truth, ERR), (wrong, OK)], key=key)',
     'lesson(lo, wrong, "failure", [(truth, ERR), (wrong, ERR)], key=key)'),
    ('world_gen_verb_conflict_gets_detail',
     'lesson(hi, truth, SO, [], key=key, arg=None)',
     'lesson(hi, truth, SO, [], key=key)'),
    ('world_gen_key_case_becomes_other_word',
     '"key_case": {"traj_key": key.upper()}',
     '"key_case": {"traj_key": "y" + key}'),
    ('world_gen_beside_good_link_restored',
     'lesson(bad, action, SO, honest([(truth, OK)]), key=key, link="missing")',
     'lesson(bad, action, SO, honest([(truth, OK)]), key=key, link=None)'),
]


def _copy_layout(tmp, name):
    d = os.path.join(tmp, name, "experiments", "2026-11-11", SLUG)
    os.makedirs(d)
    for f in os.listdir(HERE):
        p = os.path.join(HERE, f)
        if os.path.isfile(p) and not f.endswith(".pyc"):
            shutil.copy(p, d)
    return d


def _runs(d):
    """(fixtures.py passed, unittest passed) in directory d."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("W20ELM_SOURCES", None)
    a = subprocess.run([sys.executable, "-B", "fixtures.py"], cwd=d, capture_output=True, env=env, timeout=120)
    b = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_evidence_memory.py"], cwd=d,
                       capture_output=True, env=env, timeout=120)
    return a.returncode == 0, b.returncode == 0


def main():
    srcs = {}
    for target in (RULE, WORLD):
        with open(os.path.join(HERE, target), encoding="utf-8") as f:
            srcs[target] = f.read()
    plan = [(RULE, m) for m in M] + [(WORLD, m) for m in W]
    tmp = tempfile.mkdtemp(prefix="w20elm-mutants-")
    killed, survivors, equivalent, bad_anchor = [], [], [], []
    by_tests_only = []
    try:
        if _runs(_copy_layout(tmp, "base")) != (True, True):
            print("baseline: FAIL (suite or fixtures fail on unmutated code)")
            return 2
        print("baseline: OK")
        for k, (target, (name, old, new)) in enumerate(plan):
            src = srcs[target]
            if src.count(old) != 1:
                bad_anchor.append(name)
                print("%-44s ANCHOR(%d)" % (name, src.count(old)))
                continue
            d = _copy_layout(tmp, "m%03d" % k)
            with open(os.path.join(d, target), "w", encoding="utf-8") as f:
                f.write(src.replace(old, new, 1))
            fix_ok, test_ok = _runs(d)
            shutil.rmtree(os.path.join(tmp, "m%03d" % k))
            if not (fix_ok and test_ok):
                killed.append(name)
                by = "fixtures+tests" if not fix_ok and not test_ok else ("fixtures" if not fix_ok else "tests")
                if by == "tests":
                    by_tests_only.append(name)
                verdict = "killed (%s)" % by
            elif name in EQUIVALENT:
                equivalent.append(name)
                verdict = "survived (equivalent)"
            else:
                survivors.append(name)
                verdict = "SURVIVED"
            print("%-44s %s" % (name, verdict))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    wrongly_equivalent = sorted(EQUIVALENT & set(killed))
    world = {w[0] for w in W}
    print("behaviour: %d mutants, killed %d" % (len(M), sum(1 for n in killed if n not in world)))
    print("world: %d mutants, killed %d, killed only by the unittest suite %d" % (
        len(W), sum(1 for n in killed if n in world), sum(1 for n in by_tests_only if n in world)))
    print("summary: %d mutants; killed %d; equivalent %d %s; survivors %d %s; bad anchors %d; "
          "listed equivalent but killed %s" % (len(plan), len(killed), len(equivalent), equivalent,
                                               len(survivors), survivors, len(bad_anchor), wrongly_equivalent))
    return 1 if survivors or bad_anchor or wrongly_equivalent else 0


if __name__ == "__main__":
    sys.exit(main())
