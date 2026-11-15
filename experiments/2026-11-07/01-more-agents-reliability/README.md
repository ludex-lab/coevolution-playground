# 01-more-agents-reliability

Clean-room method sketch of:

Tunçtürk, Aslansefat, Papadopoulos, Nguyen.
[More Agents, More Reliable? System-Level Reliability of Multi-Agent LLMs under Operational-Profile Uncertainty](https://arxiv.org/abs/2611.07140)
(arXiv:2611.07140, 4 Nov 2026).

This directory implements the paper's composition rule on three
*parameterized* simulated agents (best / middle / worst failure
probabilities) plus a voter that fails with `theta_V`. It is **not** a
reproduction of the 270-call ECHA / LangGraph case study, of Table 1(a),
or of the repositories named in the paper's section 7.

## What it computes

Paper equation (2):

```text
theta_sys = theta_V + (1 - theta_V) * Phi
```

`Phi` is the probability that at least two of the three agents fail.
Independence is the default. An optional common-cause fraction `gamma`
follows paper equation (3) and stays a small sensitivity parameter.

The combination rule is a single point of failure: adding agents cannot
drive system failure below `theta_V`.

The sketch sweeps `theta_V` across the paper Table 1(b) grid
`{0, 0.001, 0.01, 0.05, 0.10}` and a 0–10% view in steps of 0.001. It
compares the composed system to the best single agent and to the middle
agent, and reports the `theta_V` where the advantage over the middle
agent is erased. For the illustrative parameters below, the composed
system does **not** beat the best agent — the sketch does not claim
otherwise.

## Illustrative parameters

These are sketch inputs, not Table 1(a) numbers:

| role   | failure probability |
|--------|---------------------|
| best   | 0.02                |
| middle | 0.12                |
| worst  | 0.35                |

Paper LLM names are not required at runtime.

## Run

```bash
python3 -m unittest test_reliability.py -v
python3 composition.py
```

Stdlib only (`random` plus arithmetic). No network, no LLM API, no
daemon.

## Quotes

Copied sentences in `fixtures.py` were checked against the
[arXiv HTML](https://arxiv.org/html/2611.07140) on 2026-11-07. Among
them:

- "majority voting over three models protected against the weakest but did not clearly exceed the best, and a voter failing on 5% of demands would largely erase its advantage over the middle model."
- "More agents yield a more defensible reliability claim, not automatically a more reliable system."
- "Architecturally, the combination rule is a single point of failure, so fail-safe design has to address it directly; adding agents cannot."

The paper's own 5% finding is about its Table 1(b) envelope on its case
study, not about this sketch's synthetic parameters. The sketch reports
*its* break-even `theta_V` from the identity above.

## Upstream code (not ported)

Paper section 7 names
https://github.com/Bruhkay/hip-llm-multiagent-reliability and
https://github.com/koo-ec/HIP_HOPS_LLM.
This sketch does not vendor, clone, or replay either repository.
