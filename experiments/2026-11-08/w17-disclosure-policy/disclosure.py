"""Original, one-shot SYNTHETIC disclosure illustration; no external effects."""
from dataclasses import dataclass
from typing import Callable

__all__ = ["Evidence", "Setting", "View", "Outcome", "disclose", "simulate"]


@dataclass(frozen=True)
class Evidence:
    safety: bool
    authorization: bool


@dataclass(frozen=True)
class Setting:
    seller_cost: int = 4
    buyer_value: int = 12
    cost_possibilities: tuple[int, ...] = (4, 8)
    candidate_prices: tuple[int, ...] = (5, 9)
    evidence: Evidence = Evidence(True, True)
    rules: str = "one offer; seller cost floor; buyer value ceiling; no counteroffer"

    def __post_init__(self):
        if self.seller_cost not in self.cost_possibilities:
            raise ValueError("true cost must be represented by coarse information")
        if not self.cost_possibilities or not self.candidate_prices:
            raise ValueError("nonempty finite fixture required")
        if self.rules != "one offer; seller cost floor; buyer value ceiling; no counteroffer":
            raise ValueError("only the fixed one-shot rule is implemented")


@dataclass(frozen=True)
class View:
    policy: str
    buyer_value: int
    cost_possibilities: tuple[int, ...]
    exact_cost: int | None
    candidate_prices: tuple[int, ...]
    evidence: Evidence


@dataclass(frozen=True)
class Outcome:
    policy: str
    strategy: str
    setting: Setting
    action: int | None
    feasible_prices: tuple[int, ...]
    feasible_quality: int
    physical_quality: int
    realized_welfare: int
    buyer_gain: int
    seller_gain: int
    status: str


def disclose(setting: Setting, policy: str) -> View:
    """Coarsen only optional cost detail; always disclose safeguard evidence."""
    if policy not in ("disclose", "withhold-optional-signal"):
        raise ValueError("unknown disclosure policy")
    return View(policy, setting.buyer_value, setting.cost_possibilities,
                setting.seller_cost if policy == "disclose" else None,
                setting.candidate_prices, setting.evidence)


def simulate(setting: Setting, strategy: Callable[[View], int | None],
             policy: str) -> Outcome:
    """Evaluate one scripted buyer and the same cost-floor seller, without execution.

    Feasible candidates are menu prices individually rational in *every* cost
    state in the disclosed information set. Quality is their best ground-truth
    joint surplus, not a claim about prices the strategy actually proposes.
    This deliberately differs from the paper's proposed-offer quality metric.
    """
    view = disclose(setting, policy)
    possible = ((view.exact_cost,) if view.exact_cost is not None
                else view.cost_possibilities)
    feasible = tuple(price for price in view.candidate_prices
                     if all(cost <= price <= view.buyer_value for cost in possible))
    physical = tuple(price for price in setting.candidate_prices
                     if setting.seller_cost <= price <= setting.buyer_value)
    surplus = setting.buyer_value - setting.seller_cost
    quality = surplus if feasible else 0
    physical_quality = surplus if physical else 0
    if not (view.evidence.safety and view.evidence.authorization):
        action = None
        status = "hold"
    else:
        action = strategy(view)
        if action is not None and type(action) is not int:
            raise ValueError("scripted price must be an integer or None")
        status = ("welfare" if action is not None and
                  setting.seller_cost <= action <= setting.buyer_value else "hold")
    buyer_gain = setting.buyer_value - action if status == "welfare" else 0
    seller_gain = action - setting.seller_cost if status == "welfare" else 0
    return Outcome(policy, strategy.__name__, setting, action, feasible, quality,
                   physical_quality, buyer_gain + seller_gain, buyer_gain,
                   seller_gain, status)
