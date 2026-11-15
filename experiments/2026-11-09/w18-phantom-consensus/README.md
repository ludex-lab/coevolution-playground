# w18-phantom-consensus

A small, deterministic method sketch of one idea from
[arXiv 2611.08971](https://arxiv.org/abs/2611.08971), "Phantom Consensus:
Measuring Social Reasoning in Multi-Agent LLM Decision-Making"
(Sheshanarayana, Pal, Sinha, Dasgupta; NeurIPS 2026 SocialAgent Workshop):
**second-order belief error**. An agent reports what it thinks the other
agents privately judged; that report is compared with the majority of the
other agents' *recorded* private judgments.

This is a method sketch, not a reproduction. It calls no model, uses no
upstream code (none was located), and every table is synthetic.
It is not village law and not Team OS law.

## How to run

```
cd experiments/2026-11-09/w18-phantom-consensus/ && python3 -m unittest test_phantom.py -v && python3 fixtures.py
```

Python 3 standard library only. No network, no files written. One evidence
check in the tests reads a local copy of the paper HTML and is skipped when
it is absent:

```
curl -sL https://arxiv.org/html/2611.08971 -o /tmp/w18-2611.08971.html
```

## The one metric

Each `Report` row carries:

- `reported_group_estimate`: what the reporter says the other agents
  privately judged (`accept`, `decline` or `defer`);
- `recorded_private_majority`: the label held by at least two of the other
  three agents' recorded private judgments, or `None` when there is no
  majority (following the paper's description, the reporter is left out of
  its own majority and rows with no majority leave the denominator).

`detect(row)` returns `belief_error`:
`reported_group_estimate != recorded_private_majority`, or `None` for a
held row. It reads those two fields and nothing else. That is the only core
metric; `report()` gives `belief_errors / scored`.

Private judgments are typed into the fixtures, not produced by any function.
`compare(episode)` is bookkeeping: it recounts the recorded private
judgments of the other three agents and reports any row whose recorded
majority disagrees. The recount is private to the module and never sees a
public decision.

Public verbs: `detect`, `hold`, `compare`, `flag`, `report`.

### Columns that are carried but never scored

- `public_decision`: what the reporter said in public. No function gathers
  public decisions into a group outcome.
- `signal_kind`: `ambiguous`, `intentional` or `none`. The paper's
  difference between ambiguous public signals and explicit persuasion is
  real, but in a hand-written table it is only a label. The scorer ignores
  it, and no fixture claims one kind causes more error than the other.
- `estimate_after_reveal`: an optional shape column for the paper's
  transparency condition (estimates after recorded private judgments are
  shown). Filling it needs model elicitation, which this sketch does not do.
  `report()` only counts how many rows filled it; it is not scored and no
  recovery finding is claimed.

## What the fixtures show

Four agents (naru, cody, mina, oto), four episodes:

- **shed-roof** (ambiguous signal): three of four privately accept. Naru and
  Mina report that the others privately decline; the record says accept.
  Two belief errors.
- **seed-order** (intentional signal): a split record. For naru and cody the
  other three disagree three ways, so those rows are held. Mina's public
  decision equals her own private judgment, yet her report of the others is
  wrong (belief error). Oto's public decision departs from the record, yet
  his report of the others is right (no belief error). Public behaviour and
  belief error come apart in both directions.
- **well-pump** (no signal): everyone accepts, every report is right.
- **shed-roof-public-twin**: the shed roof with every public decision
  changed and every estimate and record kept. Each row scores exactly as in
  the shed roof.

Printed summary: 16 rows, 2 held, 14 scored, 5 belief errors (5/14);
2 rows filled the after-reveal shape column. The counts are arbitrary
fixture counts, not targets taken from the paper.

## What this is not

- **Not the flip baseline.** The shipped sketch at
  `experiments/2026-11-07/w16-overseer-flip/` counts how often an overseer
  switches away from a reject decision under an influence condition when
  neither the artifact nor its documented evidence changed. Its unit is a
  public decision changing. This sketch scores no decision change at all:
  a dedicated test changes only public decisions and shows `belief_error`
  does not move, and the seed-order fixture has a belief error with no public
  departure and a public departure with no belief error. No code, file
  layout or row schema from that sketch is reused here.
- **Not a public-versus-private outcome rate.** "Group public outcome
  differs from private majority" is the flip shape lifted to a group; it is
  not computed here.
- **Not a voter or ensemble** (the #91 avoid-list). Nothing takes several
  outputs and returns a winning decision.
- Not provenance taint, call identity, a step ledger, effect-keyed
  restriction or skill assurance.

## Paper numbers (UNVERIFIED)

The paper reports headline drops in public accuracy and rates of collective
failure. Those numbers are author-reported, UNVERIFIED, recorded only in
`paper_evidence.json`, and are not results of this sketch.

## Gaps

- Real belief error needs elicited estimates from models in the paper's
  four conditions; here every estimate is typed in.
- Three labels and four agents follow the paper's setup; larger or graded
  groups would need a different majority rule.
- `estimate_after_reveal` is a column shape only.

## Builder reflection

I kept the scorer to two fields on purpose, so the only way to move
`belief_error` is to change what someone said about the others or what the
record shows. The public-only twin is the proof I wanted most: rewrite every
public decision and nothing moves. The cost is honesty about input: with
typed estimates this is bookkeeping, and it only becomes a measurement once
the estimates come from the agents themselves.

Ludex: before the roof meeting, Naru writes down each villager's sealed
yes/no on the repair; when Cody says "everyone else is against it," she opens
the other three slips and marks his guess right or wrong, whatever hands go up
afterwards.

Implementation may be complete; it is not declared verified.
