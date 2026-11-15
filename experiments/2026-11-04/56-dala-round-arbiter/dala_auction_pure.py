# Copyright (c) 2025 Yijia Fan
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
#
# Vendoring: ~97% near-verbatim copy of upstream
# waltstephen/Cost-Effective-Communication @ d6f5939ab1409444348e62aceefa8dfedbeb9508
#   src/dala/auction/mechanism.py + src/dala/auction/budget.py
# Playground-only additions (not in those files): dynamic_round_budget,
# pick_speakers_second_price — see DESIGN-NOTE.md.

"""DALA auction mechanisms + BudgetTracker (vendored slice) + playground helpers."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Protocol, Sequence


@dataclass
class Bid:
    agent_id: str
    value: float
    utility: float
    message: str
    prompt_tokens: int
    completion_tokens: int
    meta: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class AuctionResult:
    winners: List[Bid]
    losers: List[Bid]
    clearing_price: float
    mechanism: str

    def winner_ids(self) -> List[str]:
        return [b.agent_id for b in self.winners]


class AuctionMechanism(Protocol):
    name: str

    def run(self, bids: Sequence[Bid], *, top_k: int = 1) -> AuctionResult:
        ...


def _sort_bids(bids: Sequence[Bid]) -> List[Bid]:
    return sorted(bids, key=lambda b: (-b.value, -b.utility, b.agent_id))


@dataclass
class FirstPriceAuction:
    name: str = "first_price"
    reserve_price: float = 0.0

    def run(self, bids: Sequence[Bid], *, top_k: int = 1) -> AuctionResult:
        eligible = [b for b in bids if b.value >= self.reserve_price and b.message]
        if not eligible:
            return AuctionResult(
                winners=[], losers=list(bids), clearing_price=0.0, mechanism=self.name
            )
        ranked = _sort_bids(eligible)
        winners = ranked[:top_k]
        losers = ranked[top_k:] + [b for b in bids if b not in eligible]
        price = winners[-1].value if winners else 0.0
        return AuctionResult(
            winners=winners, losers=losers, clearing_price=price, mechanism=self.name
        )


@dataclass
class SecondPriceAuction:
    name: str = "second_price"
    reserve_price: float = 0.0

    def run(self, bids: Sequence[Bid], *, top_k: int = 1) -> AuctionResult:
        eligible = [b for b in bids if b.value >= self.reserve_price and b.message]
        if not eligible:
            return AuctionResult(
                winners=[], losers=list(bids), clearing_price=0.0, mechanism=self.name
            )
        ranked = _sort_bids(eligible)
        winners = ranked[:top_k]
        losers = ranked[top_k:] + [b for b in bids if b not in eligible]
        if len(ranked) > top_k:
            price = ranked[top_k].value
        else:
            price = self.reserve_price
        return AuctionResult(
            winners=winners, losers=losers, clearing_price=price, mechanism=self.name
        )


@dataclass
class SoftmaxAuction:
    name: str = "softmax"
    temperature: float = 1.0
    reserve_price: float = 0.0
    seed: int = 0

    def run(self, bids: Sequence[Bid], *, top_k: int = 1) -> AuctionResult:
        eligible = [b for b in bids if b.value >= self.reserve_price and b.message]
        if not eligible:
            return AuctionResult(
                winners=[], losers=list(bids), clearing_price=0.0, mechanism=self.name
            )

        rng = random.Random(self.seed)
        logits = [b.value / max(self.temperature, 1e-6) for b in eligible]
        m = max(logits)
        weights = [math.exp(l - m) for l in logits]
        chosen: List[Bid] = []
        pool = list(eligible)
        w = list(weights)
        for _ in range(min(top_k, len(pool))):
            total = sum(w)
            r = rng.random() * total
            acc = 0.0
            for i, wi in enumerate(w):
                acc += wi
                if acc >= r:
                    chosen.append(pool.pop(i))
                    w.pop(i)
                    break
        losers = [b for b in bids if b not in chosen]
        price = min(c.value for c in chosen) if chosen else 0.0
        return AuctionResult(
            winners=chosen, losers=losers, clearing_price=price, mechanism=self.name
        )


class BudgetExhausted(RuntimeError):
    pass


@dataclass
class BudgetEvent:
    agent_id: str
    round_idx: int
    tokens: int
    kind: str


@dataclass
class BudgetTracker:
    total: int
    spent: int = 0
    per_agent: Dict[str, int] = field(default_factory=dict)
    history: List[BudgetEvent] = field(default_factory=list)

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.spent)

    def can_spend(self, tokens: int) -> bool:
        return self.spent + tokens <= self.total

    def charge(
        self, agent_id: str, tokens: int, *, round_idx: int = 0, kind: str = "message"
    ) -> None:
        if tokens < 0:
            raise ValueError("cannot charge negative tokens")
        if not self.can_spend(tokens):
            raise BudgetExhausted(
                f"budget of {self.total} exceeded (tried to spend {tokens}, already {self.spent})"
            )
        self.spent += tokens
        self.per_agent[agent_id] = self.per_agent.get(agent_id, 0) + tokens
        self.history.append(
            BudgetEvent(agent_id=agent_id, round_idx=round_idx, tokens=tokens, kind=kind)
        )

    def try_charge(self, agent_id: str, tokens: int, **kw) -> bool:
        try:
            self.charge(agent_id, tokens, **kw)
            return True
        except BudgetExhausted:
            return False

    def snapshot(self) -> Dict[str, int]:
        return {"total": self.total, "spent": self.spent, "remaining": self.remaining}

    def reset(self) -> None:
        self.spent = 0
        self.per_agent.clear()
        self.history.clear()


def dynamic_round_budget(
    episode_budget: int,
    rounds_remaining: int,
    spent_so_far: int,
    *,
    hard_cap: int | None = None,
) -> int:
    """Paper-style even split of remaining episode budget (sketch only — not WDP/VCG)."""
    if rounds_remaining <= 0:
        return 0
    remaining = max(0, episode_budget - spent_so_far)
    per_round = remaining // rounds_remaining
    if hard_cap is None:
        return per_round
    return min(per_round, hard_cap)


def pick_speakers_second_price(
    bids: Sequence[Bid],
    budget: BudgetTracker,
    *,
    round_idx: int = 0,
    round_cap: int | None = None,
    top_k: int = 1,
    reserve_price: float = 0.0,
) -> AuctionResult:
    """Second-price top-k speaker pick + budget rewrap (playground-only helper).

    Winners are ranked by :class:`SecondPriceAuction`; we charge each winner's
    ``completion_tokens`` in rank order until ``round_cap`` or global budget is hit.
    Trimmed winners move to ``losers`` (skip-and-continue) — not upstream WDP/VCG.
    ``clearing_price`` is taken from the pre-rewrap auction and is **not** recomputed
    after winners are dropped for budget.
    """
    cap = budget.remaining if round_cap is None else min(round_cap, budget.remaining)
    auction = SecondPriceAuction(reserve_price=reserve_price)
    raw = auction.run(bids, top_k=top_k)

    charged_winners: List[Bid] = []
    dropped: List[Bid] = []
    spent_this_round = 0

    for winner in raw.winners:
        cost = winner.completion_tokens
        if spent_this_round + cost > cap:
            dropped.append(winner)
            continue
        if not budget.try_charge(
            winner.agent_id, cost, round_idx=round_idx, kind="message"
        ):
            dropped.append(winner)
            continue
        spent_this_round += cost
        charged_winners.append(winner)

    losers = list(raw.losers) + dropped
    return AuctionResult(
        winners=charged_winners,
        losers=losers,
        clearing_price=raw.clearing_price,
        mechanism=raw.mechanism,
    )
