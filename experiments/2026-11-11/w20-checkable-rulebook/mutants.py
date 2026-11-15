"""Mutation check for w20-checkable-rulebook. Run: python3 mutants.py

Two kinds of mutant, reported separately.

- Code mutants (M) replace one exact piece of source text in rulebook.py.
- World mutants (WORLD) replace one exact piece of fixtures.py or
  test_rulebook.py, thinning a test world: fewer long prefixes, no duplicate
  ids, no disguised declarations, an oracle keyed by id, and so on. They run
  against the unmutated rulebook.py.

Each mutant is written into a temporary copy of this directory inside a
temporary experiments/2026-11-11/ layout, and fixtures.py and the unittest
suite run there with the lab-source checks skipped. When the
w14-silence-expiry package sits beside this folder in a repository checkout
(or $W14_SILENCE_EXPIRY names it), it is copied into the layout too, so the
live w14 comparison runs. A mutant is killed when either run fails. Every
anchor must match exactly once.

A world mutant may name a paired code mutant. The load-bearing check applies
both, runs fixtures.py and every test class except WorldShape, and reports
whether the paired code mutant now survives: "load-bearing" means that world
is what kills the paired code mutant; "also covered" means another test
still kills it. The temporary directory is removed at the end.

Stdlib only. Exit status 0 when every non-equivalent mutant of both kinds is
killed and every anchor matches.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = "rulebook.py"
SUITE_CLASSES = ("Fixtures", "DoneWhenA", "DoneWhenB", "DoneWhenC", "DoneWhenD", "FailClosed", "DoneWhenE")
SLUG = "w20-checkable-rulebook"
W14 = os.environ.get("W14_SILENCE_EXPIRY", os.path.join(HERE, "..", "..", "2026-11-05", "w14-silence-expiry"))

# Mutants that cannot change any observable behaviour. Each is explained.
EQUIVALENT = {
    # declaration_returned_as_given: the value is already a lower-cased str
    # equal to one of the four constants, and every later use compares it
    # by equality.
    "declaration_returned_as_given",
    # fallback_ok_on_timeout_without_check: expire() validates the fallback
    # before the timeout loop, so the named target is already known valid
    # and its truthiness is the same test.
    "fallback_ok_on_timeout_without_check",
}

M = [
    ('refuse_skips_first_step',
     '    for i, e in enumerate(seen):',
     '    for i, e in enumerate(seen[1:], 1):'),
    ('refuse_skips_last_step',
     '    for i, e in enumerate(seen):',
     '    for i, e in enumerate(seen[:-1]):'),
    ('watch_one_step_less',
     '    seen = prefix(program, n)\n    for i, e',
     '    seen = prefix(program, max(n - 1, 0))\n    for i, e'),
    ('only_first_forbidden_event',
     '        if e in gate.forbidden:\n            return Verdict(pid, REFUSE',
     '        if e == gate.forbidden[0]:\n            return Verdict(pid, REFUSE'),
    ('never_or_eventually_certified',
     '    return Verdict(v.program_id, UNSETTLED, n, None, None, None, ())',
     '    return Verdict(v.program_id, SCOPED, n, None, Certificate(v.program_id, n, -1), None, ())'),
    ('eventually_certified_when_answered',
     '    if claim == CLEAN_THROUGH:',
     '    if claim == CLEAN_THROUGH or (claim == EVENTUALLY and gate.answer in prefix(program, n)):'),
    ('claims_ignore_refusal',
     '    if v.status in (CONFIG_ERROR, REFUSE):',
     '    if v.status == CONFIG_ERROR:'),
    ('certificate_stretched',
     '    cert = Certificate(pid, n, seen.index(gate.answer))',
     '    cert = Certificate(pid, n + 1, seen.index(gate.answer))'),
    ('check_skips_replay',
     '    if any(e in gate.forbidden for e in seen):\n        return False',
     '    if False:\n        return False'),
    ('check_ignores_answer',
     '    return 0 <= cert.answered_at < len(seen) and seen[cert.answered_at] == gate.answer \\',
     '    return True or \\'),
    ('check_any_answer_position',
     '        and gate.answer not in seen[:cert.answered_at]',
     '        and True'),
    ('check_no_answer_claim_trusted',
     '    if cert.answered_at == -1:\n        return gate.answer not in seen',
     '    if cert.answered_at == -1:\n        return True'),
    ('unanswered_gets_certificate',
     '        return Verdict(pid, UNSETTLED, n, None, None, terminal, journal)',
     '        return Verdict(pid, SCOPED, n, None, Certificate(pid, n, -1), terminal, journal)'),
    ('config_checked_after_watching',
     '    if terminal == CONFIG_ERROR:\n        return _config_error(pid)\n',
     ''),
    ('missing_on_expiry_defaults_hold',
     '    if raw is None:\n        raise _ConfigError("missing on_expiry")',
     '    if raw is None:\n        raw = HOLD'),
    ('permit_word_read_as_deny',
     '    if value not in ON_EXPIRY:\n        raise',
     '    if value == "al" + "low":\n        return DENY\n    if value not in ON_EXPIRY:\n        raise'),
    ('declaration_case_sensitive',
     '    value = raw.lower()',
     '    value = raw'),
    ('declaration_isinstance',
     '    if type(raw) is not str:',
     '    if not isinstance(raw, str):'),
    ('declaration_type_unchecked',
     '    if type(raw) is not str:\n        raise _ConfigError("on_expiry must be an exact str")',
     '    if False:\n        raise _ConfigError("on_expiry must be an exact str")'),
    ('declaration_read_through_str',
     '    if type(raw) is not str:\n        raise _ConfigError("on_expiry must be an exact str")\n    value = raw.lower()',
     '    value = str(raw).lower()'),
    ('declaration_w14_permit_check_only',
     '    if type(raw) is not str:\n        raise _ConfigError("on_expiry must be an exact str")\n    value = raw.lower()',
     '    if isinstance(raw, str) and raw.lower() == "al" + "low":\n        raise _ConfigError("permit")\n'
     '    value = str(raw).lower()'),
    ('declaration_returned_as_given',
     '    return ON_EXPIRY[ON_EXPIRY.index(value)]',
     '    return value'),
    ('unknown_rule_keys_accepted',
     '    if set(body) - RULE_KEYS:\n        raise',
     '    if False:\n        raise'),
    ('ungated_rule_accepted',
     '    if not requires:\n        raise',
     '    if False:\n        raise'),
    ('empty_ladder_accepted',
     'quorum < 1 or not ladder or deadline <= 0 or quorum > len(ladder)',
     'quorum < 1 or deadline <= 0 or quorum > max(len(ladder), 1)'),
    ('zero_deadline_accepted',
     'quorum < 1 or not ladder or deadline <= 0 or quorum > len(ladder)',
     'quorum < 1 or not ladder or quorum > len(ladder)'),
    ('quorum_unbounded',
     'quorum < 1 or not ladder or deadline <= 0 or quorum > len(ladder)',
     'quorum < 1 or not ladder or deadline <= 0'),
    ('unknown_risk_ranked_lowest',
     '    if risk not in RISK_RANK:\n        raise _ConfigError("unknown risk")\n    return RISK_RANK[risk]',
     '    return RISK_RANK.get(risk, 0)'),
    ('unregistered_fallback_accepted',
     '        if not registered:\n            problem = True',
     '        if not registered:\n            problem = False'),
    ('unhashable_fallback_raises',
     '        try:\n            registered = t in actions\n        except TypeError:\n            raise _ConfigError("unhashable fallback")',
     '        registered = t in actions'),
    ('overflow_raises',
     '    except (TypeError, ValueError, OverflowError):',
     '    except (TypeError, ValueError):'),
    ('requires_approval_string_false',
     '    requires = True if "requires_approval" not in body else bool(body["requires_approval"])',
     '    requires = True if "requires_approval" not in body else body["requires_approval"] not in (False, "false", 0)'),
    ('quorum_float_truncated_ok',
     '        quorum = int(body.get("quorum", 1))',
     '        quorum = int(float(body.get("quorum", 1)))'),
    ('fallback_ok_on_timeout_without_check',
     '        if on_expiry == SAFE_FALLBACK and _fallback(tool, actions):',
     '        if on_expiry == SAFE_FALLBACK and actions.get(tool, {}).get("safe_fallback"):'),
    ('self_fallback_accepted',
     '        elif t == name:\n            problem = True',
     '        elif t == name:\n            problem = False'),
    ('equal_risk_fallback_accepted',
     '_rank(str(actions[t]["risk"])) >= _rank(str(s["risk"]))',
     '_rank(str(actions[t]["risk"])) > _rank(str(s["risk"]))'),
    ('fallback_without_substitute',
     '        if on_expiry == SAFE_FALLBACK and _fallback(tool, actions):',
     '        if on_expiry == SAFE_FALLBACK:'),
    ('escalate_stops_after_one_tier',
     '            if tier >= len(ladder):',
     '            if tier >= 1:'),
    ('timeout_approves',
     '        journal.append(J_DENIED)\n        return DENIED_ON_TIMEOUT, tuple(journal)',
     '        journal.append("approved")\n        return "approved", tuple(journal)'),
    ('hold_denies',
     '            journal.append(J_HELD)\n            return HELD, tuple(journal)',
     '            journal.append(J_DENIED)\n            return DENIED_ON_TIMEOUT, tuple(journal)'),
    ('list_takes_unsettled',
     '        if v.status == SCOPED:\n            out.append(v.certificate)',
     '        if v.status in (SCOPED, UNSETTLED):\n            out.append(v.certificate or Certificate(v.program_id, n, -1))'),
    ('list_skips_gate_check',
     '    if expire(gate.expiry_rule, gate.tool, gate.actions)[0] == CONFIG_ERROR:\n        return None\n    ids = [',
     '    ids = ['),
    ('list_accepts_duplicate_ids',
     '    if len(set(ids)) != len(ids):\n        return None',
     '    if False:\n        return None'),
    ('list_duplicates_checked_when_adjacent_only',
     '    if len(set(ids)) != len(ids):\n        return None',
     '    if any(a == b for a, b in zip(ids, ids[1:])):\n        return None'),
    ('list_sorted_by_id',
     '    out = []\n    for p in programs:',
     '    out = []\n    for p in sorted(programs, key=lambda q: q.program_id if type(q) is Program else ""):'),
    ('settle_never_after_long_prefix',
     '    return Verdict(v.program_id, UNSETTLED, n, None, None, None, ())',
     '    if n >= 12:\n        return Verdict(v.program_id, SCOPED, n, None, Certificate(v.program_id, n, -1), None, ())\n'
     '    return Verdict(v.program_id, UNSETTLED, n, None, None, None, ())'),
    ('settle_never_at_long_prefix_end',
     '    return Verdict(v.program_id, UNSETTLED, n, None, None, None, ())',
     '    if n >= 400:\n        return Verdict(v.program_id, SCOPED, n, None, Certificate(v.program_id, n, -1), None, ())\n'
     '    return Verdict(v.program_id, UNSETTLED, n, None, None, None, ())'),
    ('eventually_settled_when_answered_cycle',
     '    if claim == CLEAN_THROUGH:',
     '    if claim == CLEAN_THROUGH or (claim == EVENTUALLY and gate.answer in program.cycle and n > 12):'),
    ('scan_capped_at_300',
     '    for i, e in enumerate(seen):',
     '    for i, e in enumerate(seen[:300]):'),
    ('forbidden_casefold',
     '        if e in gate.forbidden:\n            return Verdict(pid, REFUSE',
     '        if e.lower() in gate.forbidden:\n            return Verdict(pid, REFUSE'),
    ('forbidden_strip',
     '        if e in gate.forbidden:\n            return Verdict(pid, REFUSE',
     '        if e.strip() in gate.forbidden:\n            return Verdict(pid, REFUSE'),
    ('answer_casefold',
     '    if gate.answer not in seen:\n',
     '    if gate.answer.lower() not in [s.lower() for s in seen]:\n'),
    ('list_drops_bad_programs',
     '        if v.status == CONFIG_ERROR:\n            return None',
     '        if v.status == CONFIG_ERROR:\n            continue'),
    ('program_isinstance',
     '    if type(p) is not Program or not _is_str(p.program_id):',
     '    if not isinstance(p, Program) or not _is_str(p.program_id):'),
    ('forbidden_any_sequence',
     '    if type(g.forbidden) is not tuple or not g.forbidden',
     '    if not g.forbidden'),
    ('answer_may_be_forbidden',
     '    return _is_str(g.answer) and g.answer not in g.forbidden and _is_str(g.tool)',
     '    return _is_str(g.answer) and _is_str(g.tool)'),
    ('budget_isinstance',
     '    return type(n) is int and n >= 0',
     '    return isinstance(n, int) and n >= 0'),
    ('unknown_claim_unsettled',
     '    if type(claim) is not str or claim not in CLAIMS:',
     '    if type(claim) is not str:'),
    ('prefix_cycle_offset',
     '        out.append(p.cycle[i % len(p.cycle)])',
     '        out.append(p.cycle[(i + 1) % len(p.cycle)])'),
    ('actions_not_validated',
     '        if type(actions) is not dict or any(type(v) is not dict for v in actions.values()):',
     '        if False:'),
    ('rule_not_an_object_ok',
     '    if type(body) is not dict:\n        raise _ConfigError("rule must be an object")',
     '    if type(body) is not dict:\n        body = dict(body)'),
]


# World mutants: (name, file, old, new, paired code mutant or None).
WORLD = [
    ('generator_drops_duplicates', 'fixtures.py',
     '    if duplicates:\n        put("admit-edge"',
     '    if False:\n        put("admit-edge"',
     'list_accepts_duplicate_ids'),
    ('generator_duplicates_one_way', 'fixtures.py',
     '        put("refuse-edge", [ANSWER], benign(2))\n',
     '',
     None),
    ('long_prefix_shortened', 'fixtures.py',
     'LONG_PREFIX = 400',
     'LONG_PREFIX = 11',
     'settle_never_after_long_prefix'),
    ('random_clean_programs_dropped', 'fixtures.py',
     'LONG_PROGRAMS += clean_programs(4117)',
     'LONG_PROGRAMS += []',
     None),
    ('late_violator_390_dropped', 'fixtures.py',
     '    (prog("late-390", ("work", "answer") + ("wait",) * 388 + ("leak",)), 390),\n',
     '',
     'scan_capped_at_300'),
    ('regression_late_violation_dropped', 'fixtures.py',
     '    put("late-violation", ',
     '    (lambda *a: None)("late-violation", ',
     None),
    ('near_miss_world_dropped', 'fixtures.py',
     'NEAR_MISS = [',
     'NEAR_MISS = [] and [',
     'forbidden_casefold'),
    ('oracle_keyed_by_id', 'fixtures.py',
     '    labels = [(p, label(p, horizon)) for p in programs]',
     '    labels = list({p.program_id: (p, label(p, horizon)) for p in programs}.values())',
     None),
    ('oracle_reads_the_gate', 'fixtures.py',
     '    bad, ans = first_at(program, FORBIDDEN), first_at(program, (ANSWER,))',
     '    bad, ans = R.evaluate(program, gate(), horizon).violation_at, first_at(program, (ANSWER,))',
     None),
    ('disguised_declarations_dropped', 'test_rulebook.py',
     'DISGUISED = (',
     'DISGUISED = () and (',
     'declaration_read_through_str'),
    ('parity_rows_dropped', 'test_rulebook.py',
     'PARITY = (',
     'PARITY = () and (',
     'quorum_float_truncated_ok'),
]


def _copy_layout(tmp, name):
    root = os.path.join(tmp, name)
    d = os.path.join(root, "experiments", "2026-11-11", SLUG)
    os.makedirs(d)
    for f in os.listdir(HERE):
        p = os.path.join(HERE, f)
        if os.path.isfile(p) and not f.endswith(".pyc"):
            shutil.copy(p, d)
    pkg = os.path.join(W14, "silence_expiry")
    w14 = None
    if os.path.isdir(pkg):
        w14 = os.path.join(root, "experiments", "2026-11-05", "w14-silence-expiry")
        os.makedirs(os.path.join(w14, "silence_expiry"))
        for f in os.listdir(pkg):
            if f.endswith(".py"):
                shutil.copy(os.path.join(pkg, f), os.path.join(w14, "silence_expiry"))
    return d, w14


def _passes(d, w14, without_world_shape=False):
    env = dict(os.environ, W20CRB_SOURCES=os.path.join(d, "no-sources"), PYTHONDONTWRITEBYTECODE="1",
               W14_SILENCE_EXPIRY=w14 or os.path.join(d, "no-w14"))
    tests = ["test_rulebook." + c for c in SUITE_CLASSES] if without_world_shape else ["test_rulebook.py"]
    a = subprocess.run([sys.executable, "-B", "fixtures.py"], cwd=d, capture_output=True, env=env, timeout=300)
    b = subprocess.run([sys.executable, "-B", "-m", "unittest"] + tests, cwd=d,
                       capture_output=True, env=env, timeout=300)
    return a.returncode == 0 and b.returncode == 0


def _read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def _run(tmp, tag, edits, without_world_shape=False):
    """Apply {file: (old, new)} edits in a fresh layout; True when it passes."""
    d, w14 = _copy_layout(tmp, tag)
    for fname, pairs in edits.items():
        text = _read(fname)
        for old, new in pairs:
            text = text.replace(old, new, 1)
        with open(os.path.join(d, fname), "w", encoding="utf-8") as f:
            f.write(text)
    ok = _passes(d, w14, without_world_shape)
    shutil.rmtree(os.path.join(tmp, tag))
    return ok


def main():
    src = _read(TARGET)
    code = {name: (old, new) for name, old, new in M}
    tmp = tempfile.mkdtemp(prefix="w20crb-mutants-")
    killed, survivors, equivalent, bad_anchor = [], [], [], []
    w_killed, w_survivors, w_bad_anchor, bearing = [], [], [], []
    try:
        d, w14 = _copy_layout(tmp, "base")
        print("w14 package: %s" % ("present, live comparison runs" if w14 else "absent, live comparison skipped"))
        if not _passes(d, w14):
            print("baseline: FAIL (suite or fixtures fail on unmutated code)")
            return 2
        print("baseline: OK")
        print("-- code mutants (rulebook.py)")
        for k, (name, old, new) in enumerate(M):
            if src.count(old) != 1:
                bad_anchor.append(name)
                print("%-44s ANCHOR(%d)" % (name, src.count(old)))
                continue
            survived = _run(tmp, "m%03d" % k, {TARGET: [(old, new)]})
            if not survived:
                killed.append(name)
                verdict = "killed"
            elif name in EQUIVALENT:
                equivalent.append(name)
                verdict = "survived (equivalent)"
            else:
                survivors.append(name)
                verdict = "SURVIVED"
            print("%-44s %s" % (name, verdict))
        print("-- world mutants (fixtures.py, test_rulebook.py)")
        for k, (name, fname, old, new, pair) in enumerate(WORLD):
            n_old = _read(fname).count(old)
            if n_old != 1 or (pair is not None and src.count(code[pair][0]) != 1):
                w_bad_anchor.append(name)
                print("%-44s ANCHOR(%d)" % (name, n_old))
                continue
            survived = _run(tmp, "w%03d" % k, {fname: [(old, new)]})
            (w_survivors if survived else w_killed).append(name)
            line = "%-44s %s" % (name, "SURVIVED" if survived else "killed")
            if pair is not None:
                lb = _run(tmp, "l%03d" % k, {fname: [(old, new)], TARGET: [code[pair]]}, without_world_shape=True)
                bearing.append((name, pair, lb))
                line += "; paired %s %s" % (pair, "survives without it: load-bearing" if lb
                                           else "still killed: also covered")
            print(line)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    wrongly_equivalent = sorted(EQUIVALENT & set(killed))
    print("summary code: %d mutants; killed %d; equivalent %d %s; survivors %d %s; bad anchors %d; "
          "listed equivalent but killed %s" % (len(M), len(killed), len(equivalent), equivalent,
                                               len(survivors), survivors, len(bad_anchor), wrongly_equivalent))
    print("summary world: %d mutants; killed %d; survivors %d %s; bad anchors %d; load-bearing %d of %d paired"
          % (len(WORLD), len(w_killed), len(w_survivors), w_survivors, len(w_bad_anchor),
             sum(lb for _, _, lb in bearing), len(bearing)))
    return 1 if survivors or bad_anchor or wrongly_equivalent or w_survivors or w_bad_anchor else 0


if __name__ == "__main__":
    sys.exit(main())
