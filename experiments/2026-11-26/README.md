# experiments/2026-11-26

- [mb-intervention-voucher](mb-intervention-voucher/): a simulator that replays recorded history perfectly can still apply a what-if change to the wrong named record or with the wrong operator; replay-only passes it, a per-question intervention voucher fails exactly that question, a no-change null control is neither failed nor trusted, and bad input is DENY with exit 2 (method sketch of [arXiv 2611.31736](https://arxiv.org/abs/2611.31736); not a reproduction)
- [w35-stopwatch-is-not-the-mechanism](w35-stopwatch-is-not-the-mechanism/): a lower scripted work-cost is not proof of the claimed mechanism and is not proof that the output was unchanged; stopwatch-only passes planted cheaper-wrong, other-cause, and replayed-output versions, while the mechanism-counter plus output-digest plus attribution-bound arm fails them; a self-reported counter is DENY with exit 2 (method sketch of [arXiv 2611.31460](https://arxiv.org/abs/2611.31460); not a reproduction)

Do not merge experiment PRs without Ork review.
