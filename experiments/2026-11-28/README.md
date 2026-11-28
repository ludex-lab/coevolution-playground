# experiments/2026-11-28

- [mb-forecast-or-already-known](mb-forecast-or-already-known/): a score that uses a post-cutoff outcome edge is recall, not a forecast; arm A hits a planted own-edge case and arm B does not, while a case with only pre-cutoff evidence is a forecast on both arms (method sketch of [arXiv 2611.34247](https://arxiv.org/abs/2611.34247); not a reproduction)
- [w37-annal-heading-diff](w37-annal-heading-diff/): a renamed heading is not a deletion; two frozen annal or Daily-like markdown snapshots are compared as headed entries in three exact passes (same id, then same path and heading, then a body seen once on each side), so a retitled entry is renamed, a stable id on a new path is moved, and leftovers that share a body are never paired (Lab Dig 2 Wave37 build; clean-room, no paper)

Do not merge experiment PRs without Ork review.
