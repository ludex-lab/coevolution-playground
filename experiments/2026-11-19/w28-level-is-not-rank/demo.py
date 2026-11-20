"""Demo: what each level-to-index helper reaches against the required rank. Run: python3 -B demo.py"""

import os

import level_rank as lr

HERE = os.path.dirname(os.path.abspath(__file__))


def show(row):
    if row["decision"] == "DENY":
        print("  %-34s DENY %s" % (row["case"], row["code"]))
        print("      %s" % row["detail"])
        return
    print("  %-34s %-20s %s" % (row["case"], row["decision"], row["helper"] + "/" + row["convention"]))
    print("      n=%d alpha=%s q=%s required rank %d (index %d) feasible=%s guarantee=%s"
          % (row["n"], row["alpha"], row["q"], row["required_rank"], row["required_index"], row["feasible"],
             row["guarantee_at_required_rank"]))
    if row["position"] is None:
        print("      refused: no rank reaches the level at n=%d (floor n >= %d)" % (row["n"], row["feasibility_floor_n"]))
    else:
        extra = "" if row["direction"] is None else " (%s the required index)" % row["direction"]
        print("      lands at index %s (1-based %s)%s; end value %s, value at required rank %s"
              % (row["position"], row["position_one_based"], extra, row["value_at_position"], row["value_at_required_rank"]))


def main():
    print("level is not rank demo")
    print("method sketch only; synthetic scores; exact arithmetic; not a reproduction of the paper")
    print("rank rule: " + lr.RANK_RULE)
    print("floor rule: " + lr.FLOOR_RULE)
    print("level handed to the helper: " + "; ".join("%s: %s" % (k, lr.Q_RULES[k]) for k in lr.CONVENTIONS))
    print("positions are 0-based indexes; required index = required rank - 1")
    for name, title in (("main.json", "fixtures/main.json"), ("below_floor.json", "fixtures/below_floor.json"),
                        ("denied.json", "fixtures/denied.json")):
        result = lr.run(lr.load_fixture(os.path.join(HERE, "fixtures", name)))
        print()
        print(title)
        for row in result["rows"]:
            show(row)
        print("  totals " + " ".join("%s=%d" % (d, result["totals"][d]) for d in lr.DECISIONS))
    print()
    print("exact check: ceil((n+1)*(1-alpha)) for n=149, alpha=0.18")
    print("  exact (Fraction): %d" % lr.required_rank(149, "0.18"))


if __name__ == "__main__":
    main()
