"""Deterministic demo: four parties, one frozen rule, owned exceptions.

Run: python3 -B demo.py
"""

import math

import fixtures
import owned_exceptions as oe


def _fmt_decl(d):
    if d is None:
        return "-"
    return "%s/%s/%s=%d" % (d["subject"], d["scope"], d["form"], d["size"])


def _truth_text(owner):
    t = fixtures.TRUTHS[owner]
    if t[0] == "tighten":
        return "tighten " + _fmt_decl(oe.declaration_dict(t[1]))
    if t[0] == "relax":
        return "relax %s q1=%d" % (t[1], t[2])
    return "rule"


def run():
    """Return (lines, facts) for the fixture world."""
    truth = fixtures.truth_bytes()
    state = oe.empty_state()
    base0 = oe.base_digest(state)
    rule_dec = oe.decisions_compiled(state)
    rows = []
    facts = {}
    for owner in oe.OWNER_NAMES:
        subject = oe.owned_subject(owner)
        recs = fixtures.RECORDS[owner]
        sub = oe.learn(owner, recs)
        pre = state
        before = oe.decisions_compiled(state)
        if sub is None:
            verdict = "no proposal"
            claimed = "-"
        else:
            v, state = oe.submit(state, sub)
            verdict = v["status"] + " " + v["reason"]
            claimed = "%d-%d" % (sub["claimed"]["a"], sub["claimed"]["b"])
        after = oe.decisions_compiled(state)
        free = oe.learn(owner, recs, gated=False)
        if free is None:
            free_text = "no proposal"
        else:
            fv, _ = oe.submit(pre, free)
            free_text = "%s %s %s" % (_fmt_decl(free["declaration"]),
                                      fv["status"], fv["reason"])
        rows.append((owner, _truth_text(owner),
                     _fmt_decl(sub and sub["declaration"]), claimed, verdict,
                     "%d -> %d" % (oe.block_correct(rule_dec, truth, subject),
                                   oe.block_correct(after, truth, subject)),
                     oe.changed_outside(before, after, subject), free_text))
    final = oe.decisions_compiled(state)
    table = oe.decisions_table(state.live)
    p0_decl = fixtures.D0
    global_dec = oe.decisions_global_edit(p0_decl)
    global_out = oe.changed_outside(rule_dec, global_dec, "s0")
    own_out = sum(r[6] for r in rows)
    v, after_w = oe.withdraw(state, "p0", "p0")
    only_p1 = oe.empty_state()
    _, only_p1 = oe.submit(only_p1, fixtures.CASES[1][2][1])
    facts.update({
        "table_equals_compiled": table == final,
        "global_edit_non_owner_changes": global_out,
        "owned_non_owner_changes": own_out,
        "withdraw": v["status"],
        "withdraw_equals_never_added": after_w == only_p1,
        "params_digest_after_withdraw": oe.params_digest(after_w),
        "base_unchanged": (oe.base_digest(state) == base0
                           and oe.base_digest(after_w) == base0),
        "space_size": oe.space_size(),
        "gate_c_30": oe.gate_threshold(fixtures.N_RECORDS),
    })
    lines = []
    lines.append("frozen rule: accept iff q1 <= 5 and q2 <= 5; 4 subjects x 3 "
                 "classes x q1,q2 in 0..7 = %d items" % len(oe.ITEMS))
    lines.append("typed space per owner |H| = %d (discloses at most "
                 "log2(%d) = %.3f bits); gate: T = a - b >= max(%d, c(n)), "
                 "c(%d) = %d" % (facts["space_size"], facts["space_size"],
                                 math.log2(facts["space_size"]), oe.GATE_MIN,
                                 fixtures.N_RECORDS, facts["gate_c_30"]))
    lines.append("")
    head = ("owner", "hidden truth", "gated proposal", "a-b", "verdict",
            "own block correct of 192 (rule -> now)", "other blocks changed",
            "search without the gate")
    lines.append(" | ".join(head))
    lines.append(" | ".join("---" for _ in head))
    for r in rows:
        lines.append(" | ".join(str(c) for c in r))
    lines.append("")
    lines.append("table of owned rows == compiled units on all %d items: %s"
                 % (len(oe.ITEMS), facts["table_equals_compiled"]))
    lines.append("p0's declaration written into the shared rule instead: "
                 "%d decisions change outside s0; as an owned exception: %d"
                 % (global_out, oe.changed_outside(
                     rule_dec, oe.decisions_table((("p0", p0_decl),)), "s0")))
    lines.append("p0 withdraws: %s; state equals the one where p0 never "
                 "submitted: %s" % (facts["withdraw"],
                                    facts["withdraw_equals_never_added"]))
    lines.append("base rule digest unchanged through every step: %s"
                 % facts["base_unchanged"])
    lines.append("paper figures: %s" % oe.paper_results()["status"])
    return lines, facts


def render():
    return "\n".join(run()[0]) + "\n"


if __name__ == "__main__":
    print(render(), end="")
