"""Verified paper quotes and illustrative sketch parameters.

Quotes were checked against the arXiv HTML of 2611.07140
(https://arxiv.org/html/2611.07140) on 2026-11-07. They are citations,
not sketch results. Demo failure probabilities are synthetic parameters
for the composition identity; they are not Table 1(a) numbers and must
not be reported as a reproduction of the paper's LLM case study.
"""

from composition import PAPER_THETA_V_GRID

# Illustrative sketch parameters (best / middle / worst). Chosen so that
# at theta_V = 0 the composed system beats the middle agent but does not
# beat the best agent — the qualitative shape discussed in the paper —
# without copying Table 1(a) point estimates or model names.
DEMO_THETA_BEST = 0.02
DEMO_THETA_MIDDLE = 0.12
DEMO_THETA_WORST = 0.35

# Synthetic interval ends for the monotone envelope helper. Not paper
# Table 1(a) envelopes.
DEMO_LOWER = (0.01, 0.10, 0.32)
DEMO_UPPER = (0.04, 0.14, 0.38)

PAPER_QUOTES: tuple[dict[str, str], ...] = (
    {
        "id": "abstract-majority",
        "section": "abstract",
        "text": (
            "majority voting over three models protected against the weakest "
            "but did not clearly exceed the best, and a voter failing on 5% "
            "of demands would largely erase its advantage over the middle model."
        ),
    },
    {
        "id": "abstract-conclusion",
        "section": "abstract",
        "text": (
            "More agents yield a more defensible reliability claim, not "
            "automatically a more reliable system."
        ),
    },
    {
        "id": "sec2-floor",
        "section": "2.3",
        "text": (
            "no amount of agent redundancy reduces system failure below"
        ),
    },
    {
        "id": "sec2-single-point",
        "section": "2.3",
        "text": (
            "Architecturally, the combination rule is a single point of "
            "failure, so fail-safe design has to address it directly; "
            "adding agents cannot."
        ),
    },
    {
        "id": "sec2-phi",
        "section": "2.3",
        "text": "probability that at least two agents fail",
    },
    {
        "id": "sec35-middle",
        "section": "3.5",
        "text": (
            "the lower bound of the redundant configuration reaches that "
            "of the middle agent, so beyond this point the voter, not the "
            "agents, drives the risk at the lower end of the envelope, and "
            "redundancy no longer improves even on the middle agent."
        ),
    },
    {
        "id": "sec6-conditional",
        "section": "6",
        "text": (
            "more agents compose into a more defensible reliability claim, "
            "not automatically into a more reliable system."
        ),
    },
)

# Distinctive ASCII anchors confirmed present in the downloaded HTML text.
PAPER_HTML_ANCHORS: tuple[str, ...] = tuple(item["text"] for item in PAPER_QUOTES)

assert PAPER_THETA_V_GRID == (0.0, 0.001, 0.01, 0.05, 0.10)
