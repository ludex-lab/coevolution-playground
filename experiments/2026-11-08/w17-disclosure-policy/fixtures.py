"""Original SYNTHETIC agents: fixed functions, no learned or language models."""
from disclosure import Setting, View, simulate


def steady(view: View) -> int:
    """Ignore optional exact cost and offer the same conservative menu price."""
    return max(view.candidate_prices)


def cautious(view: View) -> int | None:
    """Wait under uncertainty; with an exact cost choose a feasible menu price."""
    if view.exact_cost is None:
        return None
    candidates = tuple(p for p in view.candidate_prices
                       if view.exact_cost <= p <= view.buyer_value)
    return min(candidates) if candidates else None


def pressure(view: View) -> int:
    """Deliberately brittle: demand below the known floor, else use safe menu.

    This is an authored irrational script, not a rational equilibrium or an
    inferred agent behavior. The seller's fixed floor rejects its fine offer.
    """
    return (view.exact_cost - 1 if view.exact_cost is not None
            else max(view.candidate_prices))


STRATEGIES = (steady, cautious, pressure)
POLICIES = ("withhold-optional-signal", "disclose")


def paired_runs():
    setting = Setting()
    return [(simulate(setting, strategy, POLICIES[0]),
             simulate(setting, strategy, POLICIES[1])) for strategy in STRATEGIES]


def main():
    print("SYNTHETIC one-shot bilateral trade; no transactions executed")
    print("strategy | coarse action / fine action | feasible quality coarse/fine | "
          "realized welfare coarse/fine | interpretation")
    labels = ("unaffected", "benefits", "sign reversal (existence only)")
    for (coarse, fine), label in zip(paired_runs(), labels):
        print(f"{coarse.strategy} | {coarse.action} / {fine.action} | "
              f"{coarse.feasible_quality}/{fine.feasible_quality} | "
              f"{coarse.realized_welfare}/{fine.realized_welfare} | {label}")
    print("Coarse robust feasible menu: (9,); fine: (5, 9). Physical quality: 8 both.")


if __name__ == "__main__":
    main()
