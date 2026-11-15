"""Clean-room TMR reliability composition for three parameterized agents.

Implements the structure in Tuncturk, Aslansefat, Papadopoulos, and Nguyen,
"More Agents, More Reliable? System-Level Reliability of Multi-Agent LLMs
under Operational-Profile Uncertainty," arXiv:2611.07140 (4 Nov 2026),
equation (2):

    theta_sys = theta_V + (1 - theta_V) * Phi

where Phi is the probability that at least two of the three agents fail,
and theta_V is the probability that the voter (combination rule) itself
fails. Independence is the default. An optional beta-factor common-cause
fraction gamma follows equation (3): a shared cause with probability
gamma * theta_min defeats all three agents; otherwise the residual parts
act independently.

This is a method sketch. Agent roles are parameters labeled best / middle
/ worst (failure probabilities), not paper LLM names. It does not
reproduce Table 1(a), the 270-call ECHA case study, or the upstream
repositories named in the paper's section 7.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Iterable, Sequence


# Paper Table 1(b) column grid (voter failure probabilities), verified
# against the arXiv HTML of 2611.07140 on 2026-11-07. Values only — this
# sketch does not copy Table 1(b) envelope entries.
PAPER_THETA_V_GRID: tuple[float, ...] = (0.0, 0.001, 0.01, 0.05, 0.10)

# 0-10% view at 0.1 percentage-point steps, including the Table 1(b) grid.
FINE_THETA_V_GRID: tuple[float, ...] = tuple(i / 1000.0 for i in range(0, 101))


def _require_unit(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be a real number, got {type(value)!r}")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {number}")
    return number


def _triple(
    theta_best: float, theta_middle: float, theta_worst: float
) -> tuple[float, float, float]:
    return (
        _require_unit("theta_best", theta_best),
        _require_unit("theta_middle", theta_middle),
        _require_unit("theta_worst", theta_worst),
    )


def phi_independent(theta_best: float, theta_middle: float, theta_worst: float) -> float:
    """Probability that at least two agents fail, under independence."""
    a, b, c = _triple(theta_best, theta_middle, theta_worst)
    return a * b * (1.0 - c) + a * c * (1.0 - b) + b * c * (1.0 - a) + a * b * c


def common_cause_and_residuals(
    theta_best: float, theta_middle: float, theta_worst: float, gamma: float
) -> tuple[float, tuple[float, float, float]]:
    """Paper equation (3).

    theta_min is the failure probability of the strongest agent (smallest
    theta). theta_c = gamma * theta_min. Residuals are
    (theta_a - theta_c) / (1 - theta_c).
    """
    thetas = _triple(theta_best, theta_middle, theta_worst)
    gamma = _require_unit("gamma", gamma)
    theta_min = min(thetas)
    theta_c = gamma * theta_min
    if theta_c >= 1.0:
        return 1.0, (0.0, 0.0, 0.0)
    residuals = tuple((t - theta_c) / (1.0 - theta_c) for t in thetas)
    return theta_c, residuals  # type: ignore[return-value]


def phi_at_least_two(
    theta_best: float,
    theta_middle: float,
    theta_worst: float,
    gamma: float = 0.0,
) -> float:
    """Phi: P(at least two agents fail), independence first, optional gamma."""
    gamma = _require_unit("gamma", gamma)
    if gamma == 0.0:
        return phi_independent(theta_best, theta_middle, theta_worst)
    theta_c, residuals = common_cause_and_residuals(
        theta_best, theta_middle, theta_worst, gamma
    )
    return theta_c + (1.0 - theta_c) * phi_independent(*residuals)


def theta_sys(
    theta_best: float,
    theta_middle: float,
    theta_worst: float,
    theta_v: float,
    gamma: float = 0.0,
) -> float:
    """Paper equation (2): theta_sys = theta_V + (1 - theta_V) * Phi."""
    theta_v = _require_unit("theta_v", theta_v)
    phi = phi_at_least_two(theta_best, theta_middle, theta_worst, gamma)
    return theta_v + (1.0 - theta_v) * phi


def theta_sys_envelope(
    lower: Sequence[float],
    upper: Sequence[float],
    theta_v: float,
    gamma: float = 0.0,
) -> tuple[float, float]:
    """Compose at both envelope ends.

    Paper section 2.4: the two-out-of-three structure is monotone in each
    agent's failure probability, so evaluating the network at both ends
    of each component envelope bounds theta_sys.
    """
    if len(lower) != 3 or len(upper) != 3:
        raise ValueError("lower and upper must each be a triple")
    lo = theta_sys(lower[0], lower[1], lower[2], theta_v, gamma)
    hi = theta_sys(upper[0], upper[1], upper[2], theta_v, gamma)
    return lo, hi


def sweep_theta_v(
    theta_best: float,
    theta_middle: float,
    theta_worst: float,
    grid: Iterable[float] = PAPER_THETA_V_GRID,
    gamma: float = 0.0,
) -> list[tuple[float, float]]:
    """Return (theta_v, theta_sys) pairs along a voter-failure grid."""
    return [
        (
            _require_unit("theta_v", theta_v),
            theta_sys(theta_best, theta_middle, theta_worst, theta_v, gamma),
        )
        for theta_v in grid
    ]


@dataclass(frozen=True)
class BreakEven:
    """theta_V at which the redundant system no longer beats the middle agent."""

    theta_v: float
    phi: float
    theta_middle: float
    already_erased_at_zero: bool

    @property
    def erased_advantage(self) -> bool:
        return self.already_erased_at_zero or self.theta_v <= 0.0


def break_even_vs_middle(
    theta_best: float,
    theta_middle: float,
    theta_worst: float,
    gamma: float = 0.0,
) -> BreakEven:
    """Smallest theta_V where theta_sys >= theta_middle.

    Solve theta_V + (1 - theta_V) * Phi = theta_middle, which rearranges
    to theta_V = (theta_middle - Phi) / (1 - Phi) when Phi < theta_middle.
    If Phi is already at least theta_middle, the advantage is gone at
    theta_V = 0.
    """
    middle = _require_unit("theta_middle", theta_middle)
    phi = phi_at_least_two(theta_best, theta_middle, theta_worst, gamma)
    if phi >= middle:
        return BreakEven(
            theta_v=0.0,
            phi=phi,
            theta_middle=middle,
            already_erased_at_zero=True,
        )
    theta_v = (middle - phi) / (1.0 - phi)
    return BreakEven(
        theta_v=theta_v,
        phi=phi,
        theta_middle=middle,
        already_erased_at_zero=False,
    )


@dataclass(frozen=True)
class Comparison:
    theta_sys: float
    theta_best: float
    theta_middle: float
    theta_worst: float
    theta_v: float
    gamma: float
    better_than_best: bool
    better_than_middle: bool
    better_than_worst: bool
    break_even: BreakEven


def compare_to_singles(
    theta_best: float,
    theta_middle: float,
    theta_worst: float,
    theta_v: float,
    gamma: float = 0.0,
) -> Comparison:
    """Compare the composed system to each single agent.

    Do not claim the sketch beats the best agent unless better_than_best
    is true. For typical TMR parameters it is not.
    """
    best, middle, worst = _triple(theta_best, theta_middle, theta_worst)
    system = theta_sys(best, middle, worst, theta_v, gamma)
    return Comparison(
        theta_sys=system,
        theta_best=best,
        theta_middle=middle,
        theta_worst=worst,
        theta_v=_require_unit("theta_v", theta_v),
        gamma=_require_unit("gamma", gamma),
        better_than_best=system < best,
        better_than_middle=system < middle,
        better_than_worst=system < worst,
        break_even=break_even_vs_middle(best, middle, worst, gamma),
    )


def simulate_system_failure_rate(
    draws: int,
    theta_best: float,
    theta_middle: float,
    theta_worst: float,
    theta_v: float,
    gamma: float = 0.0,
    seed: int = 0,
) -> float:
    """Monte-Carlo check of the same failure rule (stdlib random only).

    The voter fails first. If it does not, a shared cause (when gamma > 0)
    defeats all three agents; otherwise each residual (or each agent, when
    gamma is 0) fails independently. The system fails if the voter fails
    or at least two agents fail.
    """
    if draws <= 0:
        raise ValueError(f"draws must be positive, got {draws}")
    thetas = _triple(theta_best, theta_middle, theta_worst)
    theta_v = _require_unit("theta_v", theta_v)
    gamma = _require_unit("gamma", gamma)
    rng = Random(seed)
    failures = 0
    for _ in range(draws):
        if rng.random() < theta_v:
            failures += 1
            continue
        if gamma > 0.0:
            theta_c, residuals = common_cause_and_residuals(*thetas, gamma)
            if rng.random() < theta_c:
                failures += 1
                continue
            agent_failures = sum(1 for residual in residuals if rng.random() < residual)
        else:
            agent_failures = sum(1 for theta in thetas if rng.random() < theta)
        if agent_failures >= 2:
            failures += 1
    return failures / draws


def demo_report(
    theta_best: float,
    theta_middle: float,
    theta_worst: float,
    gamma: float = 0.0,
) -> str:
    """Plain-text sweep used by __main__ and by tests."""
    lines = [
        "clean-room TMR composition (method sketch; not Table 1(a))",
        f"theta_best={theta_best} theta_middle={theta_middle} "
        f"theta_worst={theta_worst} gamma={gamma}",
    ]
    for theta_v, system in sweep_theta_v(
        theta_best, theta_middle, theta_worst, PAPER_THETA_V_GRID, gamma
    ):
        cmp = compare_to_singles(
            theta_best, theta_middle, theta_worst, theta_v, gamma
        )
        vs_best = "better than best" if cmp.better_than_best else "does not beat best"
        vs_mid = (
            "better than middle" if cmp.better_than_middle else "does not beat middle"
        )
        lines.append(
            f"  theta_V={theta_v:.3f}  theta_sys={system:.6f}  {vs_best}; {vs_mid}"
        )
    even = break_even_vs_middle(theta_best, theta_middle, theta_worst, gamma)
    if even.already_erased_at_zero:
        lines.append(
            "advantage over middle already erased at theta_V=0 "
            f"(Phi={even.phi:.6f} >= theta_middle={even.theta_middle:.6f})"
        )
    else:
        lines.append(
            f"advantage over middle erased at theta_V={even.theta_v:.6f} "
            f"(Phi={even.phi:.6f})"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    from fixtures import DEMO_THETA_BEST, DEMO_THETA_MIDDLE, DEMO_THETA_WORST

    print(demo_report(DEMO_THETA_BEST, DEMO_THETA_MIDDLE, DEMO_THETA_WORST))
