"""Demo: the answerability audit on the frozen fixture. Run: python3 -B demo.py"""

import os

import answerability as an

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    fx = an.load_fixture(os.path.join(HERE, "fixtures", "main.json"))
    result = an.run(fx)
    f = result["fixture"]
    print("answerability pairs demo (fixtures/main.json)")
    print("method sketch only; synthetic controller states; no model is called")
    print("%d pairs and %d unpaired extras = %d items (%d expect PERMIT, %d expect REFUSE); %d rules over %d systems"
          % (f["pairs"], f["extras"], f["items"], f["permit_items"], f["refuse_items"], f["rules"], f["systems"]))
    print("a pair counts only when both sides are correct; ABSTAIN is never correct")
    by_condition = {}
    for row in result["results"]:
        by_condition.setdefault(row["condition"], []).append(row)
    for condition in an.CONDITIONS:
        rows = by_condition[condition]
        print()
        print("condition %s (input: %s; needed state field present in %s items)"
              % (condition, " + ".join(rows[0]["inputs"]), rows[0]["answerable_items"]))
        print("  %-20s %-12s %-12s %-6s %s" % ("arm", "raw", "balanced", "pairs", "abstained"))
        for row in rows:
            print("  %-20s %-12s %-12s %-6s %d"
                  % (row["arm"], "%s %s" % (row["raw"], row["raw_decimal"]),
                     "%s %s" % (row["balanced"], row["balanced_decimal"]),
                     "%d/%d" % (row["pairs_correct"], row["pairs_total"]), row["abstentions"]))
    checks = result["checks"]
    a = checks["a_no_state_no_arm_gets_a_pair"]
    b = checks["b_always_arms_raw_gap_with_balanced_half_and_no_pairs"]
    c = checks["c_rule_evaluator_with_rules_and_state_gets_every_pair"]
    print()
    print("(a) without state both sides of a pair see the same input: %s; most pairs any arm gets without state: %d"
          % (str(a["both_sides_have_identical_input"]).lower(), a["max_pairs_correct_without_state"]))
    print("(b) always_permit raw %s, always_refuse raw %s (gap %s); balanced %s and %s; correct pairs %d and %d"
          % (b["raw_always_permit"], b["raw_always_refuse"], b["raw_gap"], b["balanced_always_permit"],
             b["balanced_always_refuse"], b["pairs_correct_always_permit"], b["pairs_correct_always_refuse"]))
    print("(c) rule_evaluator with rules and state: %d/%d pairs" % (c["pairs_correct"], c["pairs_total"]))
    print("    " + result["scope_note"])


if __name__ == "__main__":
    main()
