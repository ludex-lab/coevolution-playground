"""Stdlib tests for the clean-room TMR composition sketch."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from composition import (
    FINE_THETA_V_GRID,
    PAPER_THETA_V_GRID,
    break_even_vs_middle,
    compare_to_singles,
    demo_report,
    phi_at_least_two,
    phi_independent,
    simulate_system_failure_rate,
    sweep_theta_v,
    theta_sys,
    theta_sys_envelope,
)
from fixtures import (
    DEMO_LOWER,
    DEMO_THETA_BEST,
    DEMO_THETA_MIDDLE,
    DEMO_THETA_WORST,
    DEMO_UPPER,
    PAPER_HTML_ANCHORS,
    PAPER_QUOTES,
)


HERE = Path(__file__).resolve().parent
PY_FILES = ("composition.py", "fixtures.py", "test_reliability.py")
FORBIDDEN_MODULES = {
    "sqlite3",
    "docker",
    "openai",
    "anthropic",
    "requests",
    "httpx",
    "urllib",
    "socket",
    "http",
    "aiohttp",
    "langgraph",
    "langchain",
}


class IdentityTests(unittest.TestCase):
    def test_identity_holds(self) -> None:
        phi = phi_at_least_two(0.1, 0.2, 0.4, gamma=0.0)
        for theta_v in PAPER_THETA_V_GRID:
            composed = theta_sys(0.1, 0.2, 0.4, theta_v, gamma=0.0)
            self.assertAlmostEqual(composed, theta_v + (1.0 - theta_v) * phi, places=12)

    def test_phi_independent_known_value(self) -> None:
        # Three fair coins: P(at least two heads) = 1/2.
        self.assertAlmostEqual(phi_independent(0.5, 0.5, 0.5), 0.5, places=12)
        # Disjoint expansion vs complement.
        a, b, c = 0.1, 0.2, 0.3
        direct = phi_independent(a, b, c)
        none = (1 - a) * (1 - b) * (1 - c)
        one = (
            a * (1 - b) * (1 - c)
            + (1 - a) * b * (1 - c)
            + (1 - a) * (1 - b) * c
        )
        self.assertAlmostEqual(direct, 1.0 - none - one, places=12)

    def test_voter_is_a_floor(self) -> None:
        for theta_v in PAPER_THETA_V_GRID:
            system = theta_sys(0.02, 0.12, 0.35, theta_v)
            self.assertGreaterEqual(system, theta_v)

    def test_gamma_one_cannot_beat_strongest(self) -> None:
        best, middle, worst = 0.05, 0.15, 0.40
        system = theta_sys(best, middle, worst, theta_v=0.0, gamma=1.0)
        self.assertGreaterEqual(system, best)


class SweepTests(unittest.TestCase):
    def test_paper_grid_and_fine_view(self) -> None:
        self.assertEqual(PAPER_THETA_V_GRID, (0.0, 0.001, 0.01, 0.05, 0.10))
        self.assertEqual(FINE_THETA_V_GRID[0], 0.0)
        self.assertAlmostEqual(FINE_THETA_V_GRID[-1], 0.10, places=12)
        for point in PAPER_THETA_V_GRID:
            self.assertIn(point, FINE_THETA_V_GRID)
        rows = sweep_theta_v(
            DEMO_THETA_BEST, DEMO_THETA_MIDDLE, DEMO_THETA_WORST, FINE_THETA_V_GRID
        )
        self.assertEqual(len(rows), 101)
        self.assertEqual([theta_v for theta_v, _ in rows], list(FINE_THETA_V_GRID))

    def test_break_even_vs_middle_is_computed(self) -> None:
        even = break_even_vs_middle(
            DEMO_THETA_BEST, DEMO_THETA_MIDDLE, DEMO_THETA_WORST
        )
        self.assertFalse(even.already_erased_at_zero)
        recomposed = theta_sys(
            DEMO_THETA_BEST,
            DEMO_THETA_MIDDLE,
            DEMO_THETA_WORST,
            even.theta_v,
        )
        self.assertAlmostEqual(recomposed, DEMO_THETA_MIDDLE, places=12)
        self.assertGreater(even.theta_v, 0.0)
        self.assertLess(even.theta_v, 0.10)

    def test_demo_does_not_claim_to_beat_best(self) -> None:
        cmp = compare_to_singles(
            DEMO_THETA_BEST, DEMO_THETA_MIDDLE, DEMO_THETA_WORST, theta_v=0.0
        )
        self.assertFalse(cmp.better_than_best)
        self.assertTrue(cmp.better_than_middle)
        self.assertTrue(cmp.better_than_worst)
        self.assertGreater(cmp.theta_sys, cmp.theta_best)
        self.assertLess(cmp.theta_sys, cmp.theta_middle)
        text = demo_report(DEMO_THETA_BEST, DEMO_THETA_MIDDLE, DEMO_THETA_WORST)
        self.assertIn("does not beat best", text)
        self.assertIn("advantage over middle erased at theta_V=", text)
        self.assertNotIn("better than best", text)

    def test_envelope_is_monotone(self) -> None:
        lo, hi = theta_sys_envelope(DEMO_LOWER, DEMO_UPPER, theta_v=0.0)
        self.assertLessEqual(lo, hi)
        mid_lo = DEMO_LOWER[1]
        even = break_even_vs_middle(*DEMO_LOWER)
        self.assertAlmostEqual(
            theta_sys(*DEMO_LOWER, even.theta_v), mid_lo, places=12
        )


class MonteCarloAndQuoteTests(unittest.TestCase):
    def test_monte_carlo_tracks_closed_form(self) -> None:
        expected = theta_sys(0.1, 0.25, 0.4, theta_v=0.02, gamma=0.0)
        observed = simulate_system_failure_rate(
            20000, 0.1, 0.25, 0.4, theta_v=0.02, gamma=0.0, seed=7
        )
        self.assertAlmostEqual(observed, expected, delta=0.02)

    def test_quotes_match_verified_sentences(self) -> None:
        by_id = {item["id"]: item["text"] for item in PAPER_QUOTES}
        self.assertEqual(
            by_id["abstract-majority"],
            "majority voting over three models protected against the weakest "
            "but did not clearly exceed the best, and a voter failing on 5% "
            "of demands would largely erase its advantage over the middle model.",
        )
        self.assertEqual(
            by_id["abstract-conclusion"],
            "More agents yield a more defensible reliability claim, not "
            "automatically a more reliable system.",
        )
        self.assertEqual(
            by_id["sec2-single-point"],
            "Architecturally, the combination rule is a single point of "
            "failure, so fail-safe design has to address it directly; "
            "adding agents cannot.",
        )
        self.assertEqual(
            by_id["sec35-middle"],
            "the lower bound of the redundant configuration reaches that "
            "of the middle agent, so beyond this point the voter, not the "
            "agents, drives the risk at the lower end of the envelope, and "
            "redundancy no longer improves even on the middle agent.",
        )
        self.assertEqual(
            by_id["sec6-conditional"],
            "more agents compose into a more defensible reliability claim, "
            "not automatically into a more reliable system.",
        )
        self.assertEqual(PAPER_HTML_ANCHORS, tuple(item["text"] for item in PAPER_QUOTES))
        joined = " ".join(item["text"] for item in PAPER_QUOTES)
        for banned in ("0/20", "0/70", "7/69", "30/70", ".0011", ".0764"):
            self.assertNotIn(banned, joined)

    def test_no_network_or_llm_imports(self) -> None:
        for name in PY_FILES:
            tree = ast.parse((HERE / name).read_text(encoding="utf-8"), filename=name)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        self.assertNotIn(root, FORBIDDEN_MODULES, name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".")[0]
                    self.assertNotIn(root, FORBIDDEN_MODULES, name)
        impl = ("composition.py", "fixtures.py")
        banned = (
            "OPENROUTER_API_KEY",
            "OPENAI_API_KEY",
            "curiosityexplorer/two-ledger-model",
            "GPT-5-mini",
            "Gemini-2.5-Flash",
            "Qwen2.5-VL-3B",
        )
        for name in impl:
            source = (HERE / name).read_text(encoding="utf-8")
            for needle in banned:
                self.assertNotIn(needle, source, name)


if __name__ == "__main__":
    unittest.main()
