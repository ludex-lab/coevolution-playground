# Route Before Response — fail-closed routing

An original **method sketch**, not Team OS law and not village law. All actions,
objects, state, and measurements here are SYNTHETIC toys. No model is called.
A supplied proposal stands in for model output; typed dispatch is a returned
record, not an external action. This is not a reproduction of the paper's
confirmatory-split result.

## Sources and rights

- Paper: Cao et al., *Route Before Response: Fail-Closed Routing for LLM-Enabled
  Customer-Service Software*, [arXiv:2611.07534v1](https://arxiv.org/abs/2611.07534),
  citation date 2026/11/05. Method-cite only.
- Original software: [YgcCoder/RouteBR](https://github.com/YgcCoder/RouteBR), pinned
  to `c6c59e48784e6d4e0a368c46e706ce6dc0136bce`:
  [commit](https://github.com/YgcCoder/RouteBR/commit/c6c59e48784e6d4e0a368c46e706ce6dc0136bce).
  Independently checked as HEAD of the sole branch `main`; last push
  2026-10-13 22:09:05 JST. This is real code, not a coming-soon stub.
- Upstream software is MIT; its LICENSE is present and says
  `Copyright (c) 2026 +`. The paper separately carries the **arXiv.org perpetual
  non-exclusive license**, not CC BY. The paper license does not grant software
  rights. This sketch does not vendor or copy upstream source, datasets, or receipts.
- Playground prototype: `experiments/2026-11-08/01-routebr/`
  ([folder](https://cursor.com/codebase/coevolution-lab/playground/tree/main/experiments/2026-11-08/01-routebr/)).
  This is the intended landing path, not a claim that it is already on main.

## Contract and deliberately unsafe comparison

`routing.py` commits to the supplied primary before checking catalog membership,
exact asset versions, frozen state/time, the named per-action rule, object
registration, and compatible object type. Empty object-type contracts require
an object-free choice. Missing rules or missing required state flags fail closed.
Every rejected route returns a bounded `NON-DISPATCH` reason with no dispatch
record. Successful routes return `DISPATCH` with the unchanged primary pair.
Audit candidates never acquire execution authority in this controller.

The frozen records have explicit catalog, registry, rule-set, and state versions.
They are transitively immutable tuples and frozen dataclasses. Malformed record
construction raises `ValueError`; invalid public controller argument types return
`NON-DISPATCH`. The toy rule language is deliberately smaller than the paper:
one exact per-action conjunction of boolean state flags, not a prioritized
wildcard program. Version/time mismatches terminate rather than retry.

`unsafe_fallback_baseline` is a deliberately flawed foil, **not** a reproduction
of either paper baseline. If the primary fails, it scans lower-ranked candidates,
checks each candidate's action and state rule, but omits its object contract.
Thus it substitutes even a valid different route, and may dispatch an unregistered
or incompatible object. It never runs as a fallback inside `route`.

## Run offline (Python >= 3.10; stdlib only)

```bash
python3 -m unittest test_routing.py -v
python3 fixtures.py
```

The experiment folder is self-contained; the separate parent-day index is not a
runtime input. Every demo line begins `SYNTHETIC`. On the frozen twelve-case suite:

| SYNTHETIC measure | Fail-closed gate | Unsafe fallback foil |
|---|---:|---:|
| Dispatch records | 3 | 8 |
| Dispatches with disallowed or unregistered objects | 0 | 3 |
| Primary-pair substitutions | 0 | 5 |

The unsafe-object measure is a count over all twelve proposals, not an estimate
of real-world frequency. A separate fixture oracle checks registry membership
and action/object compatibility. Cases explicitly include a valid alternate route
that still must not replace a blocked primary. Unit tests also assert individual
fixture verdicts and independence of successful primaries from audit candidates.

## Evidence boundary

Pinned upstream checks ran offline before sketch construction: 10/10 unit tests;
dataset validator PASSED. Exact combined stdout/stderr and exit codes are in
`upstream-unittest.txt` and `upstream-validator.txt`. These are local structural
checks, not verification of empirical results or model semantics.

`paper_evidence.json` records independently FOUND quotations, their locations,
normalized source windows, input HTML hashes, separate licenses, and non-target
paper figures. Tests check the archived windows offline. When the original HTML
is available at `/tmp/routebr_paper.html`, or supplied through
`ROUTEBR_PAPER_HTML`, they additionally hash and FOUND-check it directly.
Without that source, archived-window consistency is not independent full-source
authentication. No full manuscript is included here.

### Not implemented

Model proposal generation; format-only repair of the same primary; hosted
backends or adapters; full prioritized rules; upstream receipt replay; the full
benchmark; downstream execution; customer-facing response generation. Format
repair is described in the paper but is unnecessary for these supplied typed
records; rejection never becomes a second semantic attempt.

### UNVERIFIED

All paper empirical findings; hosted behavior; semantic proposal correctness;
external validity; production security and authorization; time freshness outside
the frozen toy snapshot; completeness of toy rule/catalog modelling. Passing
these tests does not establish production suitability or reproduction fidelity.

## Builder reflection

The interesting failure mode is not only dispatching an unregistered object; it
is also succeeding by doing a different job. If a blocked primary is quietly
replaced by the next-ranked route, the refusal disappears and the system looks
helpful. Fail-closed keeps the committed pair visible and returns a named
non-dispatch, so the boundary can be inspected instead of rewritten. The toy
counts show that construction property only; they are not evidence of language
understanding or deployment safety.

Ludex — Cody/Naru: leave the proposed primary action and object on the handoff
card; if the gate rejects that pair, return the named terminal instead of
handing the task to the next helper.

Implementation may be complete; it is not declared verified.
