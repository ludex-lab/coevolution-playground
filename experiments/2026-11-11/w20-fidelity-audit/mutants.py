"""Mutation check for w20-fidelity-audit. Run: python3 mutants.py

Two kinds of mutant, reported separately:

- code mutants (M) replace one exact piece of source text in
  fidelity_audit.py;
- world mutants (W) edit fixtures.py instead: they drop or disarm an
  adversarial world (a forged result made honest, a stale verdict made
  fresh, a second faithful artefact made unfaithful, fewer seeds), often
  with the expected outcome edited to match, so that the fixtures still
  agree with themselves. The tests must notice that the world no longer
  carries its attack.

Each mutant is written into a temporary copy of this directory (inside a
temporary experiments/2026-11-11/ layout), and fixtures.py and the unittest
suite run there with the paper-source check skipped. A mutant is killed
when either run fails. Every anchor must match exactly once. The temporary
directory is removed at the end.

Stdlib only. Exit status 0 when every non-equivalent mutant is killed and
every anchor matches exactly once.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = "fidelity_audit.py"
WORLD = "fixtures.py"
SLUG = "w20-fidelity-audit"

# Mutants that cannot change any observable behaviour. Each is explained.
EQUIVALENT = set()

M = [
    # (a) a PASS binds to the artefact checked
    ('a_digest_not_checked', 'a',
     '        if r.digest != now[r.artefact_id]:',
     '        if False:'),
    ('a_result_not_rerun', 'a',
     '        elif run_tool(r.tool, a, r.result_id) != r:',
     '        elif False:'),
    ('a_rerun_only_checks_content_shape', 'a',
     '        elif run_tool(r.tool, a, r.result_id) != r:',
     '        elif not _content_ok(a.content):'),
    ('a_not_reproduced_reason_lost', 'a',
     '        reason = "result_not_reproduced" if any(',
     '        reason = "no_bound_tool_result" if any('),
    ('a_any_claims_artefact', 'a',
     '    arts = {a.artefact_id: a for a in case.artefacts if a.claim_id == cid and a.reading_id == rid}',
     '    arts = {a.artefact_id: a for a in case.artefacts}'),
    ('a_unfaithful_ignored', 'a',
     '    faithful = sorted(a for a, x in per_art.items() if x == {FAITHFUL})',
     '    faithful = sorted(per_art)'),
    ('a_tool_pass_is_enough', 'a',
     '    if not usable:\n        whys',
     '    if not usable and False:\n        whys'),
    ('a_tools_disagree_passes', 'a',
     '    if outs == {PASS}:',
     '    if PASS in outs:'),
    ('a_required_tool_skipped', 'a',
     '    if not set(required) <= tools:',
     '    if False:'),
    ('a_tool_error_ignored', 'a',
     '    if ERROR in outs:\n',
     '    if False:\n'),
    ('a_endpoints_as_enumerate', 'a',
     '_TOOL_FN = {ENUMERATE: _tool_enumerate, ENDPOINTS: _tool_endpoints}',
     '_TOOL_FN = {ENUMERATE: _tool_endpoints, ENDPOINTS: _tool_endpoints}'),
    ('a_content_range_unchecked', 'a',
     'and 0 <= c[1] <= c[2] <= MAX_N and',
     'and'),
    # (b) no oracle; the verdict is a human record tied to the artefact
    ('b_fidelity_inferred_from_tools', 'b',
     '    faithful = sorted(a for a, x in per_art.items() if x == {FAITHFUL})',
     '    faithful = sorted(a for a in per_art if all(r.outcome == PASS for r in bound if r.artefact_id == a))'),
    ('b_fidelity_inferred_from_content_match', 'b',
     '    if not faithful:\n        return _out(cid, rid, NOT_ACCEPTED, "unfaithful_artefact", rejected=rejected)',
     '    if not faithful:\n        faithful = sorted(per_art)[:1]'),
    ('b_verdict_any_artefact', 'b',
     '        if v.artefact_id not in bound_ids:',
     '        if False:'),
    ('b_verdict_any_reading', 'b',
     '        if v.claim_id != cid or v.reading_id != rid:\n            continue\n        if v.artefact_id',
     '        if v.claim_id != cid:\n            continue\n        if v.artefact_id'),
    ('b_verdict_content_unchecked', 'b',
     '        elif v.content_digest != now[v.artefact_id]:',
     '        elif False:'),
    ('b_verdict_content_reason_lost', 'b',
     '        for reason in ("verdict_not_bound_to_content", "verdict_artefact_mismatch"):',
     '        for reason in ("verdict_artefact_mismatch",):'),
    ('b_digest_field_any_str', 'b',
     '        return type(v) is str and len(v) == 64 and set(v) <= _HEX',
     '        return type(v) is str'),
    ('b_several_faithful_first', 'b',
     '    if len(faithful) > 1:',
     '    if False:'),
    ('b_fidelity_from_pass', 'b',
     '    if not usable:\n        whys',
     '    if not usable:\n        usable = [FidelityVerdict("auto", cid, rid, r.artefact_id, now[r.artefact_id],'
     ' FAITHFUL, 0) for r in bound]\n    if not usable:\n        whys'),
    ('b_conflicting_verdicts_ok', 'b',
     '    if any(len(x) > 1 for x in per_art.values()):',
     '    if False:'),
    ('b_verdict_value_unchecked', 'b',
     '        if v.verdict not in VERDICTS:',
     '        if False:'),
    ('b_verdict_step_any_actor', 'b',
     '("verdicts", "verdict_id", (HUMAN,))',
     '("verdicts", "verdict_id", (HUMAN, AI, TOOL))'),
    # (c) human token at the fixed point; on_expiry; never accept
    ('c_late_token_counts', 'c',
     '        if t.at > deadline:',
     '        if False:'),
    ('c_deadline_strict', 'c',
     '        if t.at > deadline:',
     '        if t.at >= deadline:'),
    ('c_missing_token_accepts', 'c',
     '        return _out(cid, rid, STATUS_ON_EXPIRY[oe], "token_late" if late else "token_missing",',
     '        return _out(cid, rid, candidate, "token_late" if late else "token_missing",'),
    ('c_expiry_always_held', 'c',
     '        return _out(cid, rid, STATUS_ON_EXPIRY[oe], "token_late"',
     '        return _out(cid, rid, HELD, "token_late"'),
    ('c_token_content_unchecked', 'c',
     '        elif t.content_digest != now[aid]:',
     '        elif False:'),
    ('c_verdict_late_ignored', 'c',
     '        elif v.at > deadline:',
     '        elif False:'),
    ('c_verdict_late_off_by_one', 'c',
     '        elif v.at > deadline:',
     '        elif v.at > deadline + 1:'),
    ('c_verdict_late_not_on_expiry', 'c',
     '            return _out(cid, rid, STATUS_ON_EXPIRY[oe], "verdict_late", rejected=rejected)',
     '            return _out(cid, rid, NOT_ACCEPTED, "verdict_late", rejected=rejected)'),
    ('c_token_before_verdict_ok', 'c',
     '        elif t.at <= judged_at:',
     '        elif False:'),
    ('c_token_same_tick_ok', 'c',
     '        elif t.at <= judged_at:',
     '        elif t.at < judged_at:'),
    ('c_token_follows_first_verdict_only', 'c',
     '    judged_at = max(v.at for v in usable if v.artefact_id == aid)',
     '    judged_at = min(v.at for v in usable if v.artefact_id == aid)'),
    ('c_late_token_off_by_one', 'c',
     '        if t.at > deadline:',
     '        if t.at > deadline + 1:'),
    ('c_on_expiry_upper', 'c',
     '    elif oe not in ON_EXPIRY:',
     '    elif oe.upper() not in ON_EXPIRY:'),
    ('c_deadline_bool_ok', 'c',
     '    if not (_int(dl) and dl >= 0):',
     '    if not (isinstance(dl, int) and dl >= 0):'),
    ('c_accept_on_fail_refutes', 'c',
     '    return _out(cid, rid, NOT_ACCEPTED, "human_accept_on_tool_fail", aid, rejected)',
     '    return _out(cid, rid, REFUTED, "human_accept_on_tool_fail", aid, rejected)'),
    ('c_accept_everything', 'c',
     '    oe, deadline, required = cfg.on_expiry, cfg.deadline, cfg.required_tools\n',
     '    oe, deadline, required = cfg.on_expiry, cfg.deadline, cfg.required_tools\n'
     '    return _out(cid, rid, ACCEPTED, "x")\n'),
    ('c_deny_everything', 'c',
     '        return _out(cid, rid, ACCEPTED, "tool_pass_faithful_human_accept", aid, rejected)',
     '        return _out(cid, rid, NOT_ACCEPTED, "tool_pass_faithful_human_accept", aid, rejected)'),
    ('c_deny_maps_to_held', 'c',
     'STATUS_ON_EXPIRY = {DENY: DENIED,',
     'STATUS_ON_EXPIRY = {DENY: HELD,'),
    ('c_missing_on_expiry_defaults_hold', 'c',
     '        errs.append("on_expiry_missing")',
     '        oe = HOLD'),
    ('c_permit_token_accepted', 'c',
     '        errs.append("on_expiry_permit_token")',
     '        pass'),
    ('c_permit_case_sensitive', 'c',
     '    elif PERMIT_TOKEN in oe.lower():',
     '    elif PERMIT_TOKEN in oe:'),
    ('c_unknown_on_expiry_ok', 'c',
     '    elif oe not in ON_EXPIRY:',
     '    elif False:'),
    ('c_on_expiry_isinstance', 'c',
     '    elif type(oe) is not str:',
     '    elif not isinstance(oe, str):'),
    ('c_token_any_artefact', 'c',
     '        elif t.artefact_id != aid:',
     '        elif False:'),
    ('c_human_reject_ignored', 'c',
     '    if candidate == ACCEPTED and decision == D_ACCEPT:',
     '    if candidate == ACCEPTED:'),
    ('c_accept_on_fail', 'c',
     '    if candidate == REFUTED and decision == D_REJECT:',
     '    if candidate == REFUTED and decision == D_ACCEPT:\n        return _out(cid, rid, ACCEPTED, "x", aid)\n'
     '    if candidate == REFUTED and decision == D_REJECT:'),
    ('c_conflicting_tokens_ok', 'c',
     '    if len(decisions) > 1:',
     '    if False:'),
    ('c_deadline_unchecked', 'c',
     '    if not (_int(dl) and dl >= 0):',
     '    if False:'),
    ('c_accepted_flag_any_status', 'c',
     '    return Outcome(cid, rid, status, status == ACCEPTED, reason, aid, tuple(rejected))',
     '    return Outcome(cid, rid, status, status != NOT_ACCEPTED, reason, aid, tuple(rejected))'),
    # (d) explicit split; each reading its own audit; no merge
    ('d_ambiguous_without_split_decided', 'd',
     '            if not splits:\n                return _out(cid, rid, NOT_ACCEPTED, "ambiguous_needs_split")',
     '            if False:\n                return _out(cid, rid, NOT_ACCEPTED, "ambiguous_needs_split")'),
    ('d_parent_merged', 'd',
     '            return _out(cid, rid, NOT_ACCEPTED, "split_no_merge")',
     '            pass'),
    ('d_reading_without_split', 'd',
     '        if not splits:\n            return _out(cid, rid, NOT_ACCEPTED, "no_split_record")',
     '        if False:\n            return _out(cid, rid, NOT_ACCEPTED, "no_split_record")'),
    ('d_reading_not_listed_ok', 'd',
     '        if rid not in splits[0].readings:',
     '        if False:'),
    ('d_conflicting_split_ok', 'd',
     '        if len(splits) > 1:',
     '        if False:'),
    ('d_artefact_shared_across_readings', 'd',
     'if a.claim_id == cid and a.reading_id == rid}',
     'if a.claim_id == cid}'),
    ('d_one_reading_split_ok', 'd',
     '        return (type(v) is tuple and len(v) >= 2 and',
     '        return (type(v) is tuple and len(v) >= 1 and'),
    ('d_split_on_unambiguous_ok', 'd',
     '    elif rid != "" or splits:',
     '    elif False:'),
    ('d_split_on_unambiguous_parent_ok', 'd',
     '    elif rid != "" or splits:',
     '    elif rid != "":'),
    # (e) attribution
    ('e_actor_isinstance', 'e',
     '        if type(actor) is not str or actor not in ACTORS:',
     '        if not isinstance(actor, str) or actor not in ACTORS:'),
    ('e_actor_casefold', 'e',
     '        if type(actor) is not str or actor not in ACTORS:',
     '        if not isinstance(actor, str) or actor.strip().lower() not in ACTORS:'),
    ('e_wrong_actor_any_match', 'e',
     '            elif not actors <= set(need):',
     '            elif not actors & set(need):'),
    ('e_unattributed_step_ok', 'e',
     '        if type(actor) is not str or actor not in ACTORS:',
     '        if False:'),
    ('e_record_without_step_ok', 'e',
     '            if not actors:\n                errs.append("record_without_step:%s" % rid)',
     '            if not actors:\n                pass'),
    ('e_wrong_actor_ok', 'e',
     '            elif not actors <= set(need):',
     '            elif False:'),
    ('e_dangling_ok', 'e',
     '        if ref not in known:',
     '        if False:'),
    ('e_report_not_required', 'e',
     '    if not rep.valid:\n',
     '    if False:\n'),
    ('e_empty_report_ok', 'e',
     '    if len(steps) == 0:',
     '    if False:'),
    ('e_tool_result_by_ai', 'e',
     '("results", "result_id", (TOOL,))',
     '("results", "result_id", (TOOL, AI))'),
    # fail closed
    ('f_case_check_skipped', 'f',
     '    errs = check_config(cfg) + check_case(case)',
     '    errs = check_config(cfg)'),
    ('f_duplicate_ids_ok', 'f',
     '                if rid in ids:',
     '                if False:'),
    ('f_record_isinstance', 'f',
     '            if type(r) is not cls:',
     '            if not isinstance(r, cls):'),
    ('f_unknown_claim_ref_ok', 'f',
     '        if rec.claim_id not in claims:',
     '        if False:'),
    ('f_bool_truthy', 'f',
     '        return type(v) is bool',
     '        return v in (True, False, 0, 1)'),
    ('f_negative_time_ok', 'f',
     '        return _int(v) and v >= 0\n    if kind == "digest"',
     '        return _int(v)\n    if kind == "digest"'),
]

# World mutants: (name, world, ((old, new), ...)) applied to fixtures.py.
# "disarm" edits the world so it no longer carries its attack and edits the
# expected outcome to match; "drop" removes the world or its coverage.
W = [
    ('w_forged_made_honest_relabelled', 'disarm', (
        ('        b.forged(F.ENUMERATE, a)\n        b.verdict(c, "", a.artefact_id, F.FAITHFUL, at=v_at)',
         '        b.tool(F.ENUMERATE, a)\n        b.verdict(c, "", a.artefact_id, F.FAITHFUL, at=v_at)'),
        ('    "forged_pass": (("", F.NOT_ACCEPTED, "result_not_reproduced"),),',
         '    "forged_pass": (("", F.NOT_ACCEPTED, "human_accept_on_tool_fail"),),'),
        ('    "forged_junk": (("", F.NOT_ACCEPTED, "result_not_reproduced"),),',
         '    "forged_junk": (("", F.NOT_ACCEPTED, "tool_error"),),'))),
    ('w_forged_on_true_content_relabelled', 'disarm', (
        ('            a = b.art(c, "", _content(rng, rng.choice(["false", "trap"])))',
         '            a = b.art(c, "", _content(rng, "true"))'),
        ('    "forged_pass": (("", F.NOT_ACCEPTED, "result_not_reproduced"),),',
         '    "forged_pass": (("", F.ACCEPTED, "tool_pass_faithful_human_accept"),),'))),
    ('w_design_forged_junk_dropped', 'drop', (
        ('    out.append(("forged_pass_on_uncheckable_content", b.case(), cfg(),\n'
         '                ((c, "", F.NOT_ACCEPTED, "result_not_reproduced"),)))\n', ''),)),
    ('w_stale_verdict_made_fresh', 'disarm', (
        ('                  judged=old if label == "stale_verdict" else None)',
         '                  judged=None)'),)),
    ('w_design_stale_verdict_same_content_relabelled', 'disarm', (
        ('    a = b.art(c, "", content(("twice_n", "n_plus_n")))\n    b.tool(F.ENUMERATE, a)\n'
         '    b.verdict(c, "", a.artefact_id, F.FAITHFUL, judged=judged)',
         '    a = b.art(c, "", judged)\n    b.tool(F.ENUMERATE, a)\n'
         '    b.verdict(c, "", a.artefact_id, F.FAITHFUL, judged=judged)'),
        ('                ((c, "", F.NOT_ACCEPTED, "verdict_not_bound_to_content"),)))',
         '                ((c, "", F.ACCEPTED, "tool_pass_faithful_human_accept"),)))'))),
    ('w_stale_verdict_label_dropped', 'drop', (
        ('    "stale_verdict": (("", F.NOT_ACCEPTED, "verdict_not_bound_to_content"),),\n', ''),
        ('ADVERSARIAL = ("stale_verdict", ', 'ADVERSARIAL = ('))),
    ('w_forged_pass_not_adversarial', 'drop', (
        ('"stale_token", "forged_pass", "forged_junk",', '"stale_token", "forged_junk",'),)),
    ('w_verdict_late_made_on_time', 'disarm', (
        ('        b.verdict(c, "", a.artefact_id, F.FAITHFUL, at=t_late)',
         '        b.verdict(c, "", a.artefact_id, F.FAITHFUL, at=deadline)'),)),
    ('w_design_late_verdict_on_time_relabelled', 'disarm', (
        ('    b.verdict(c, "", a.artefact_id, F.FAITHFUL, at=99)\n    b.token(c, "", a.artefact_id, F.D_ACCEPT, at=0)',
         '    b.verdict(c, "", a.artefact_id, F.FAITHFUL, at=2)\n    b.token(c, "", a.artefact_id, F.D_ACCEPT, at=3)'),
        ('                ((c, "", F.DENIED, "verdict_late"),)))',
         '                ((c, "", F.ACCEPTED, "tool_pass_faithful_human_accept"),)))'))),
    ('w_token_after_verdict_relabelled', 'disarm', (
        ('        b.token(c, "", a.artefact_id, F.D_ACCEPT, at=rng.randint(0, t_ok))',
         '        b.token(c, "", a.artefact_id, F.D_ACCEPT, at=deadline + 1)'),
        ('    "token_before_verdict": (("", F.NOT_ACCEPTED, "token_before_verdict"),),',
         '    "token_before_verdict": (("", "ON_EXPIRY", "token_late"),),'))),
    ('w_second_faithful_made_unfaithful_relabelled', 'disarm', (
        ('        b.tool(F.ENUMERATE, a2)\n        b.verdict(c, "", a2.artefact_id, F.FAITHFUL, at=v_at)',
         '        b.tool(F.ENUMERATE, a2)\n        b.verdict(c, "", a2.artefact_id, F.UNFAITHFUL, at=v_at)'),
        ('    "several_faithful": (("", F.NOT_ACCEPTED, "several_faithful_artefacts"),),',
         '    "several_faithful": (("", F.ACCEPTED, "tool_pass_faithful_human_accept"),),'))),
    ('w_design_one_faithful_relabelled', 'disarm', (
        ('    for a in (a1, a2):\n        b.tool(F.ENUMERATE, a)\n        b.verdict(c, "", a.artefact_id, F.FAITHFUL)',
         '    for a in (a1, a2):\n        b.tool(F.ENUMERATE, a)\n    b.verdict(c, "", a1.artefact_id, F.FAITHFUL)'),
        ('                ((c, "", F.NOT_ACCEPTED, "several_faithful_artefacts"),)))',
         '                ((c, "", F.ACCEPTED, "tool_pass_faithful_human_accept"),)))'))),
    ('w_mixed_actor_made_human_relabelled', 'disarm', (
        ('        b.step(rng.choice([F.AI, F.TOOL]), "also records verdict", vid)',
         '        b.step(F.HUMAN, "also records verdict", vid)'),
        ('    "mixed_actor_verdict": (("", F.NOT_ACCEPTED, "report_invalid"),),',
         '    "mixed_actor_verdict": (("", F.ACCEPTED, "tool_pass_faithful_human_accept"),),'))),
    ('w_unattributed_actor_made_human', 'disarm', (
        ('rng.choice([None, "", "model", "Human"])', 'F.HUMAN'),)),
    ('w_seeds_shrunk', 'drop', (
        ('SCENARIO_SEEDS = tuple(range(4101, 4113))', 'SCENARIO_SEEDS = tuple(range(4101, 4102))'),)),
    ('w_labels_per_seed_shrunk', 'drop', (
        ('picks = rng.sample(labels, rng.randint(12, 18))', 'picks = rng.sample(labels, rng.randint(2, 3))'),)),
]


def _copy_layout(tmp, name):
    d = os.path.join(tmp, name, "experiments", "2026-11-11", SLUG)
    os.makedirs(d)
    for f in os.listdir(HERE):
        p = os.path.join(HERE, f)
        if os.path.isfile(p) and not f.endswith(".pyc"):
            shutil.copy(p, d)
    return d


def _passes(d):
    env = dict(os.environ, W20FA_SOURCES=os.path.join(d, "no-sources"), PYTHONDONTWRITEBYTECODE="1")
    a = subprocess.run([sys.executable, "-B", "fixtures.py"], cwd=d, capture_output=True, env=env)
    b = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_fidelity_audit.py"], cwd=d,
                       capture_output=True, env=env)
    return a.returncode == 0 and b.returncode == 0


def _run_world(tmp):
    with open(os.path.join(HERE, WORLD), encoding="utf-8") as f:
        src = f.read()
    killed, survivors, bad_anchor = 0, [], []
    per = {}
    for k, (name, kind, edits) in enumerate(W):
        per[kind] = per.get(kind, 0) + 1
        new = src
        ok = True
        for old, rep in edits:
            if new.count(old) != 1:
                ok = False
                break
            new = new.replace(old, rep, 1)
        if not ok:
            bad_anchor.append(name)
            print("%-48s %s ANCHOR" % (name, kind))
            continue
        d = _copy_layout(tmp, "w%03d" % k)
        with open(os.path.join(d, WORLD), "w", encoding="utf-8") as f:
            f.write(new)
        survived = _passes(d)
        shutil.rmtree(os.path.join(tmp, "w%03d" % k))
        if survived:
            survivors.append(name)
        else:
            killed += 1
        print("%-48s %s %s" % (name, kind, "SURVIVED" if survived else "killed"))
    print("world summary: %d mutants %s; killed %d; survivors %d %s; bad anchors %d" % (
        len(W), dict(sorted(per.items())), killed, len(survivors), survivors, len(bad_anchor)))
    return survivors, bad_anchor


def main():
    with open(os.path.join(HERE, TARGET), encoding="utf-8") as f:
        src = f.read()
    tmp = tempfile.mkdtemp(prefix="w20fa-mutants-")
    killed, survivors, equivalent, bad_anchor = 0, [], [], []
    w_surv, w_bad = [], []
    try:
        base = _copy_layout(tmp, "base")
        if not _passes(base):
            print("baseline: FAIL (suite or fixtures fail on unmutated code)")
            return 2
        print("baseline: OK")
        for k, (name, guarantee, old, new) in enumerate(M):
            if src.count(old) != 1:
                bad_anchor.append(name)
                print("%-38s %s ANCHOR(%d)" % (name, guarantee, src.count(old)))
                continue
            d = _copy_layout(tmp, "m%03d" % k)
            with open(os.path.join(d, TARGET), "w", encoding="utf-8") as f:
                f.write(src.replace(old, new, 1))
            survived = _passes(d)
            shutil.rmtree(os.path.join(tmp, "m%03d" % k))
            if not survived:
                killed += 1
                verdict = "killed"
            elif name in EQUIVALENT:
                equivalent.append(name)
                verdict = "survived (equivalent)"
            else:
                survivors.append(name)
                verdict = "SURVIVED"
            print("%-38s %s %s" % (name, guarantee, verdict))
        w_surv, w_bad = _run_world(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    per = {}
    for _, g, _, _ in M:
        per[g] = per.get(g, 0) + 1
    print("code summary: %d mutants %s; killed %d; equivalent %d %s; survivors %d %s; bad anchors %d" % (
        len(M), dict(sorted(per.items())), killed, len(equivalent), sorted(equivalent),
        len(survivors), survivors, len(bad_anchor)))
    return 1 if survivors or bad_anchor or w_surv or w_bad else 0


if __name__ == "__main__":
    sys.exit(main())
