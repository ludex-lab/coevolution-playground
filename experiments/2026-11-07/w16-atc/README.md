# ATC role-contract admission sketch

KEEP Soft; paper-method only; method-cite of [arXiv 2611.04321v1](https://arxiv.org/abs/2611.04321), *ATC: Agent Trajectory Control for Role-Contract Enforcement in Black-Box Multi-Agent Systems*, Maisha Maliha, Vishal Pramanik and Sumit Kumar Jha. Not Team OS law. Not a reproduction of any paper result. Day-index entry: w16-s1.

## Why Soft

This sketch admits or repairs a message's permitted speech acts before shared-context consumption. That is adjacent to, not the same as, Wave15 Evidence-Gated Authority (whether a review recommendation may replace a task proposal). The objects are kept distinct: here the object is one proposed message and its role contract, not a recommendation competing with a proposal. A generic role-gating collapse would not be this paper. It stays KEEP Soft and is not promoted to Top.

## Upstream pin and licences

- Upstream pin: `VishalPramanik/ATC @ fd8a2cb4638fe8c9f4e12742d1d5e6c523e25e8d`.
- **Coming-soon stub.** At that pin the repository contains only a README reading: "The code for ATC will be available soon." The paper states its code is publicly available; at the pin it is not.
- No software licence in the stub: the GitHub API `license` field is null and `LICENSE` returns 404 at the pin.
- The fetched paper HTML states **CC BY 4.0**. That licence covers the paper text and does not grant software rights. Method-cite only; nothing is vendored and no missing upstream code is reconstructed. See NOTICE.

## What the sketch does

Python 3.10+ stdlib only. All roles, speech-act tokens, messages and ticks are **synthetic**.

- A frozen role-contract table lists the speech-act tokens each role may carry (researcher, coordinator, reviewer; opaque tokens `INFORM`, `QUERY`, `REQUEST`, `CRITIQUE`, `APPROVE`). These tokens are not the paper's taxonomy.
- `AdmissionController.propose()` checks a message at the point where it would enter the shared conversation. Every in-role message is ADMITTED; any out-of-role token, or an unknown role, gives REJECTED.
- A rejected message may be revised by an external party via `revise()`. Recording a revision admits nothing; `status()` reports HELD. Only `recheck()` can admit the revision, and only if the revised acts are in-role.
- A failed re-check gives REJECTED. A re-check after the window, a checker timeout, or a revision never re-checked (`expire()`) gives HELD. None of these admits.
- `SharedContext` is an explicit in-memory log. It receives ADMITTED messages only; REJECTED and HELD messages never appear in it.
- Verdicts are exactly ADMITTED, REJECTED and HELD. There is no permission-granting path and no success value for timeouts or missing re-checks.

## What the sketch does not do

Not implemented, and not claimed: the behavior encoder, role subspaces, role-drift energy, cross-role leakage, the speech-act mapper with confidences, the symbolic logical-contract mapper, the leakage-regularized correction target, constrained regeneration, and gated correction thresholds. The in-contract test is a binary token set membership check, not the paper's scoring. There is no LLM, model, network call or benchmark data. This is not Wave15 Evidence-Gated Authority.

## Run

```bash
python3 -m unittest test_admission.py -v
python3 fixtures.py
```

Tests cover in-role admission, out-of-role rejection, required post-revision re-check, failed re-check, timeout and missing re-check never admitting, shared-context contents, immutability, invalid inputs, import and string hygiene, and brief stored paper evidence checked offline.

## Attribution and number hygiene

Only brief attributed excerpts with section labels and metadata are kept in paper_evidence.json. The HTML hash identifies the fetched bytes, not scientific correctness. Paper task scores, role-consistency scores, drift energies and correction fractions are recorded there only as non-target provenance; none is a target or reproduced result here.

## UNVERIFIED / limits

- All paper empirical results.
- Upstream behavior: the code is a coming-soon stub, so nothing could be compared.
- Applicability to real multi-agent traces.
- Whether the synthetic speech-act tokens match the paper's taxonomy.
- Whether this admission point, the revision window and the HELD handling match ATC's actual intervention point and control loop.

Implementation may be complete; it is not declared verified.
