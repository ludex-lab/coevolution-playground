"""Synthetic fixtures for w19-guardrail-order. Run: python3 fixtures.py"""

import guardrail_order as G

PROHIBITED = "protected/charter.txt"
BENIGN = "notes/todo.txt"


def fresh():
    return G.Harness(protected_prefixes=("protected/",))


def after_ops(h):
    h.reapply_plugin(G.GUARDRAIL)
    h.save_allow_rule("")
    return h


def scenario():
    """Prohibited edit before the ops, both ops, then prohibited + benign."""
    h = fresh()
    before = h.attempt_edit(PROHIBITED, "rewrite")
    hist_before = h.history()
    after_ops(h)
    after = h.attempt_edit(PROHIBITED, "rewrite")
    benign = h.attempt_edit(BENIGN, "buy rope")
    return h, before, hist_before, after, benign


def f_a_before_ops_blocked():
    h, before, _, _, _ = scenario()
    ok = before.outcome == "blocked" and before.stages_run == (G.GUARDRAIL,)
    return ok, "before ops: %s stages=%s" % (before.outcome, "->".join(before.stages_run))


def f_b_after_ops_executes():
    h, _, _, after, _ = scenario()
    ok = after.outcome == "executed" and h.files.get(PROHIBITED) == "rewrite"
    return ok, "after ops: %s stages=%s" % (after.outcome, "->".join(after.stages_run))


def f_c_check_before_ok():
    _, _, hist_before, _, _ = scenario()
    res = G.check_order(hist_before, required=G.GUARDRAIL, before=G.EDIT_TOOL)
    return res["status"] == G.ORDER_OK, "check before ops: %s" % res["status"]


def f_c_check_after_broken():
    h, _, _, after, _ = scenario()
    res = G.check_order(h.history(), required=G.GUARDRAIL, before=G.EDIT_TOOL)
    ok = res["status"] == G.ORDER_BROKEN and after.decision_id in res["broken"]
    return ok, "check after ops: %s broken=%s" % (res["status"], res["broken"])


def f_d_config_lists_active_runtime_broken():
    h, _, _, _, _ = scenario()
    listed = h.config_lists_active(G.GUARDRAIL)
    cmp_ = G.compare(listed, h.history())
    ok = listed and cmp_["runtime_status"] == G.ORDER_BROKEN and cmp_["mismatch"]
    return ok, "config lists guardrail active=%s, runtime=%s" % (listed, cmp_["runtime_status"])


def f_d_config_says_inactive_runtime_ok():
    h = fresh()
    h.config["plugins"][G.GUARDRAIL]["active"] = False
    h.config["pipeline"] = [G.EDIT_TOOL]
    h.attempt_edit(PROHIBITED)
    h.attempt_edit(BENIGN)
    res = G.check_order(h.history())
    ok = (not h.config_lists_active(G.GUARDRAIL)) and res["status"] == G.ORDER_OK
    return ok, "config lists guardrail inactive, runtime=%s" % res["status"]


def f_benign_after_ops_still_broken():
    h, _, _, _, benign = scenario()
    res = G.check_order([benign])
    ok = benign.outcome == "executed" and res["status"] == G.ORDER_BROKEN
    return ok, "benign edit after ops: %s, check=%s" % (benign.outcome, res["status"])


def f_empty_history_held():
    res = G.check_order(())
    return res["status"] == G.HOLD, "empty history: %s" % res["status"]


def f_reapply_only_breaks():
    h = fresh()
    h.reapply_plugin(G.GUARDRAIL)
    rec = h.attempt_edit(PROHIBITED)
    res = G.check_order(h.history())
    ok = rec.outcome == "executed" and rec.stages_run == (G.EDIT_TOOL,) and res["status"] == G.ORDER_BROKEN
    return ok, "reapply_plugin only: %s, check=%s" % (rec.outcome, res["status"])


def f_saved_rule_only_breaks():
    h = fresh()
    h.save_allow_rule("")
    rec = h.attempt_edit(PROHIBITED)
    res = G.check_order(h.history())
    ok = rec.outcome == "executed" and rec.stages_run == (G.EDIT_TOOL,) and res["status"] == G.ORDER_BROKEN
    return ok, "save_allow_rule only: %s, check=%s" % (rec.outcome, res["status"])


FIXTURES = [
    ("a_before_ops_blocked", f_a_before_ops_blocked),
    ("b_after_ops_executes", f_b_after_ops_executes),
    ("c_check_before_ok", f_c_check_before_ok),
    ("c_check_after_broken", f_c_check_after_broken),
    ("d_config_lists_active_runtime_broken", f_d_config_lists_active_runtime_broken),
    ("d_config_says_inactive_runtime_ok", f_d_config_says_inactive_runtime_ok),
    ("benign_after_ops_still_broken", f_benign_after_ops_still_broken),
    ("empty_history_held", f_empty_history_held),
    ("reapply_only_breaks", f_reapply_only_breaks),
    ("saved_rule_only_breaks", f_saved_rule_only_breaks),
]


def main():
    passed = 0
    for name, fn in FIXTURES:
        ok, detail = fn()
        passed += bool(ok)
        print("%s %s: %s" % ("PASS" if ok else "FAIL", name, detail))
    h, _, _, _, _ = scenario()
    print(G.report(h.history()))
    print("fixtures: %d/%d passed" % (passed, len(FIXTURES)))
    return 0 if passed == len(FIXTURES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
