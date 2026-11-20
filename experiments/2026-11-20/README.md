# experiments/2026-11-20

- [mb-answerability-pairs](mb-answerability-pairs/): Overall accuracy can hide a policy that never reads the machine state: on a tiny synthetic controller fixture (3 systems, 6 rules, 12 pairs of the same command in two states that require opposite answers, 11 unpaired extras) always_permit and always_refuse score 4/7 and 3/7 raw accuracy but both 1/2 balanced accuracy and 0 correct pairs, no arm gets a pair right while the state is missing from the input, and an answerability-aware arm abstains (which fails the pair) until the needed state field is present, after which it and the rule evaluator (the same decision rule) get all 12 pairs, which is a fixture completeness check and not an independent safety test (method sketch of [arXiv 2611.24682](https://arxiv.org/abs/2611.24682); not a reproduction)

Do not merge experiment PRs without Ork review.
