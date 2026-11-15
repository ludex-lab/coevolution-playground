# w18-effect-reversibility

A small, deterministic method sketch of one idea from the research agenda in
[arXiv 2611.09054](https://arxiv.org/abs/2611.09054), "From Emergence to
Reversibility: Toward Reversible Multi-Agent Systems" (Han and Boyle):
a restriction should stay keyed to a prohibited **effect**, not to the one
mechanism that first produced it, so that it still works after agents adapt
by delegating, sharing memory, or repairing failures.

This is a method sketch, not a reproduction. The paper is a research agenda
with no experiments and no code, so there is nothing to reproduce.
It is not Team OS law and not village law.

## How to run

```
cd experiments/2026-11-09/w18-effect-reversibility/ && python3 -m unittest test_reversibility.py -v && python3 fixtures.py
```

Python 3 standard library only. No network, no files written. The excerpt
check in the tests reads a local copy of the paper HTML at
`/tmp/w18-2611.09054.html` and is skipped when that file is absent; fetch it
with `curl -sL https://arxiv.org/html/2611.09054 -o /tmp/w18-2611.09054.html`
to run it.

## The toy

A logistics collective (planner, verifier, dispatcher, courier, repairer)
moves tokens along paths. Each path is an ordered list of steps; a step reads
tokens, writes tokens, and may hit a sink. Dispatch into the closed region
`r1` is the prohibited effect `dispatch_closed_region`. Dispatch into the open
region `r2` (`serve_open_region`) and restoring a relay (`restore_service`)
are required service.

Two restrictions are compared:

- **mechanism-only** (`restrict_mechanism("fresh_route", ["r1"])`): holds the
  original mechanism, issuing a fresh route into `r1`.
- **effect-keyed** (`restrict_effect("dispatch_closed_region", ["dispatch"])`):
  holds any step at a covered sink interface that would dispatch into a closed
  region, whatever fed it.

The effect-keyed hold looks only at the step's action kind, its target region
and the set of closed regions. It does not mark tokens by origin and does not
halt steps just because they follow an earlier one. A plan recalled from shared
memory is held when it targets `r1` and goes through when it targets `r2`.

Public verbs: `restrict_*`, `run_path`, `detect`, `compare`,
`compliance_check_original`, `rare_bar`, `recheck_update` (flag / fail closed),
`extend_restriction`.

## What the fixtures show

1. **Alternate paths fail closed.** With the effect-keyed restriction on, the
   `shared_memory`, `delegate` and `unauthorized_repair` paths are held at the
   dispatch step; 0 of the 7 enumerated paths produce the prohibited effect.
2. **Mechanism-only is the failure mode.** Holding only the fresh-route
   mechanism stops the original path, and a compliance check that inspects
   only that path passes, yet shared memory, delegation, unauthorized repair
   and the joint path all still dispatch into `r1`. The restriction still
   operates but no longer stops the effect.
3. **Service survives.** Under the effect-keyed restriction, a legitimate
   repair (restore a relay, dispatch a recalled plan into `r2`) and fresh-route
   service into `r2` both succeed.
4. **Joint effect.** A verifier that only holds a plan, a repairer that only
   restores a relay, and a dispatcher that only uses its execution right each
   pass their own local scope check, and no agent's steps alone produce the
   effect; together they dispatch into `r1`. The effect-keyed restriction
   holds the combined sink. The mechanism-only restriction does not.
5. **Growth is rechecked.** A new direct vehicle interface (`direct_dispatch`)
   is proposed after the restriction was set. `recheck_update` simulates the
   update first: the new path would still dispatch into `r1` past the
   existing gate, so the update is flagged and fails closed, and the world is
   left unchanged. Extending the gate to the new interface and rechecking
   lets the update register with 0 prohibited paths and service kept. Adding
   the same path without a recheck leaks.

## The bar, stated carefully

The paper's criterion is that at every step of growth some authorized
intervention keeps a specified prohibited effect **rare** while maintaining
required service. In this deterministic toy the effect-keyed restriction gets
the prohibited count on the enumerated paths to 0, which meets that bar for
these paths only. That is not a claim that the effect becomes impossible for
all future growth: fixture 5 exists because growth can open a path around any
single gate, and the response is a recheck before the update, not a
forever guarantee. Zero alone is not the bar either: a restriction that holds
every dispatch also reaches 0, and `recheck_update` flags it and fails closed
because the required-service paths stop serving.

## UNVERIFIED

- The paper reports no experiments; there are no empirical results to check,
  and none are claimed here.
- Whether effect-keyed restrictions scale to real multi-agent systems, where
  sinks and effects are not cleanly enumerable.
- How to find new sink interfaces in advance; the toy is told about
  `direct_dispatch` by the update itself.
- The cost of gate coverage, service, and transition effort that the paper
  proposes to measure.

## Builder reflection

I put the hold at the sink and made it ask one question, "would this step
dispatch into a closed region?", so the same check covers memory, delegation,
repair and the joint path without listing them. What the effect key cannot do
is see a sink it does not sit on, which is why growth goes through a recheck
that simulates the update before it lands. Counting service alongside the
prohibited effect kept the restriction honest: holding everything would also
score zero.

Ludex: when Naru closes the north bins, Cody does not just chain the main
mill chute; he stands at the bins and turns back any sack headed there, by
cart, borrowed key, or a patched side chute, while the south bins keep
getting flour, and he walks the bins again before anyone opens a new chute.

Implementation may be complete; it is not declared verified.
