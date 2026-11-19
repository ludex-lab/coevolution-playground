# experiments/2026-11-19

- [mb-certified-region-delta](mb-certified-region-delta/): Leaving the operating domain is a request to recertify, not an authority cut or a shutdown: on a tiny synthetic fixture (4 state dimensions with a certified region and hard-safety limits, 2 operating-domain variables, 13 observations) a certified-region monitor classifies each observation as in-region, out-of-region, hard-safety or ODD-exit and answers with four distinct responses (CONTINUE, WITHDRAW_AUTHORIZATION, SHUTDOWN, RECERTIFY) while a naive baseline shuts down on any deviation outside the region and cuts authority on an ODD exit, so it shuts down in 8 of 13 observations against 2 and never asks for recertification (method sketch of [arXiv 2611.21811](https://arxiv.org/abs/2611.21811); not a reproduction)

Do not merge experiment PRs without Ork review.
