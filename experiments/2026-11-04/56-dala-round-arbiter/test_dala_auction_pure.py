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
# Tests: ~9 near-verbatim from upstream @ d6f5939 test_auction.py + test_budget.py;
# plus playground tests for top-k clearing, rewrap, dynamic_round_budget, harness honesty.

"""Unittests for vendored DALA auction + BudgetTracker slice (13 tests — not upstream 33)."""

from __future__ import annotations

import importlib
import unittest

from dala_auction_pure import (
    Bid,
    BudgetExhausted,
    BudgetTracker,
    FirstPriceAuction,
    SecondPriceAuction,
    SoftmaxAuction,
    dynamic_round_budget,
    pick_speakers_second_price,
)


def _bid(
    agent_id: str,
    value: float,
    *,
    utility: float = 0.5,
    text: str = "hello",
    p: int = 10,
    c: int = 5,
) -> Bid:
    return Bid(
        agent_id=agent_id,
        value=value,
        utility=utility,
        message=text,
        prompt_tokens=p,
        completion_tokens=c,
    )


class TestAuctionMechanisms(unittest.TestCase):
    def test_first_price_winner_and_clearing(self) -> None:
        bids = [_bid("a", 10), _bid("b", 3), _bid("c", 7)]
        result = FirstPriceAuction().run(bids, top_k=1)
        self.assertEqual(result.winner_ids(), ["a"])
        self.assertEqual(result.clearing_price, 10)

    def test_second_price_clearing_is_runner_up(self) -> None:
        bids = [_bid("a", 10), _bid("b", 3), _bid("c", 7)]
        result = SecondPriceAuction().run(bids, top_k=1)
        self.assertEqual(result.winner_ids(), ["a"])
        self.assertEqual(result.clearing_price, 7)

    def test_empty_message_is_ignored(self) -> None:
        bids = [_bid("a", 10, text=""), _bid("b", 5)]
        result = FirstPriceAuction().run(bids)
        self.assertEqual(result.winner_ids(), ["b"])

    def test_reserve_price_blocks_all(self) -> None:
        bids = [_bid("a", 1), _bid("b", 2)]
        result = FirstPriceAuction(reserve_price=10).run(bids)
        self.assertEqual(result.winners, [])

    def test_top_k_first_price(self) -> None:
        bids = [_bid("a", 10), _bid("b", 9), _bid("c", 8), _bid("d", 1)]
        result = FirstPriceAuction().run(bids, top_k=2)
        self.assertEqual(result.winner_ids(), ["a", "b"])

    def test_softmax_is_deterministic_with_seed(self) -> None:
        bids = [_bid("a", 10), _bid("b", 5), _bid("c", 1)]
        r1 = SoftmaxAuction(temperature=1.0, seed=42).run(bids)
        r2 = SoftmaxAuction(temperature=1.0, seed=42).run(bids)
        self.assertEqual(r1.winner_ids(), r2.winner_ids())

    def test_second_price_top_k_clearing_is_k_plus_one_bid(self) -> None:
        bids = [_bid("a", 10), _bid("b", 9), _bid("c", 8), _bid("d", 1)]
        result = SecondPriceAuction().run(bids, top_k=2)
        self.assertEqual(result.winner_ids(), ["a", "b"])
        self.assertEqual(result.clearing_price, 8)


class TestBudgetTracker(unittest.TestCase):
    def test_charge_and_snapshot(self) -> None:
        tracker = BudgetTracker(total=100)
        tracker.charge("a", 30, round_idx=0)
        tracker.charge("b", 40, round_idx=0)
        self.assertEqual(tracker.spent, 70)
        self.assertEqual(tracker.per_agent, {"a": 30, "b": 40})
        self.assertEqual(tracker.snapshot()["remaining"], 30)

    def test_budget_exhaustion(self) -> None:
        tracker = BudgetTracker(total=50)
        tracker.charge("a", 40)
        self.assertFalse(tracker.try_charge("a", 20))
        self.assertEqual(tracker.spent, 40)
        with self.assertRaises(BudgetExhausted):
            tracker.charge("a", 20)

    def test_reset(self) -> None:
        tracker = BudgetTracker(total=10)
        tracker.charge("a", 5)
        tracker.reset()
        self.assertEqual(tracker.spent, 0)
        self.assertFalse(tracker.per_agent)
        self.assertFalse(tracker.history)


class TestSpeakerPickSketch(unittest.TestCase):
    def test_pick_speakers_budget_rewrap_drops_second_winner(self) -> None:
        bids = [
            _bid("a", 10, c=8),
            _bid("b", 9, c=8),
            _bid("c", 1, c=2),
        ]
        budget = BudgetTracker(total=100)
        result = pick_speakers_second_price(
            bids, budget, top_k=2, round_cap=10, round_idx=1
        )
        self.assertEqual(result.winner_ids(), ["a"])
        self.assertIn("b", [b.agent_id for b in result.losers])
        self.assertEqual(budget.spent, 8)

    def test_dynamic_round_budget_even_split(self) -> None:
        cap = dynamic_round_budget(
            episode_budget=100, rounds_remaining=4, spent_so_far=20, hard_cap=30
        )
        self.assertEqual(cap, 20)


class TestUpstreamHonesty(unittest.TestCase):
    def test_upstream_e2e_harness_not_vendored(self) -> None:
        """Upstream ``tests/test_end_to_end.py`` has 3 tests — not all Lightning.

        Two use ``Auctioneer`` + ``MockBackend`` only; one imports ``DALALightningModule``.
        This folder vendors ``mechanism.py`` + ``budget.py`` only — package imports fail
        here (no pytest.skip).
        """
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("dala.agents.auctioneer")
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("dala.models.dala_module")


if __name__ == "__main__":
    unittest.main()
