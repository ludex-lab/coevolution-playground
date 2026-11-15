# Disclosure-policy illustration

A clean-room stdlib **method sketch** of [Who Should Know What? Empirical
Information Design for Multi-Agent LLM Economies](https://arxiv.org/abs/2611.07667).
Future playground path: `experiments/2026-11-08/w17-disclosure-policy/`.
This is a **scripted counterexample**, **not a replication**; it is **not Team OS law**
and **not village law**. No model calls, external effects, or execution authority.
There is no ALLOW path: outcomes are `welfare` or `hold`, never an authorization.

## What is paired

One synthetic buyer makes one integer price offer to one cost-floor seller.
Buyer utility is value minus price; seller utility is price minus cost; disagreement
has zero utility. Cost is 4 and value is 12. The finite illustrative price menu is
5 and 9. The seller's acceptance rule and the buyer's value ceiling never change.
Each pair uses the exact same immutable setting, strategy function, and interaction
rules. Only an optional exact-cost signal changes: coarse
`withhold-optional-signal` reveals the cost set {4, 8}; fine `disclose` retains
that set and adds the actual cost. The buyer always knows its own value. The seller
always knows its own cost; only the buyer receives the optional signal.
No controller chooses a strategy using privileged labels. Strategy identity is
fixed before each comparison, not selected after seeing the outcome.

## Candidate quality is not realized welfare

Physical opportunities are identical across policies. The robust feasible candidate
set is the menu prices that would satisfy both parties in every cost state still
possible to the buyer: coarse {9}, fine {5, 9}. `feasible_quality` is the maximum
actual joint surplus over this set, or zero for an empty set. It stays 8 here;
the set expands. `physical_quality` separately reports the best menu outcome under
true utilities, also 8. Neither is a strategy's actual selection.
This information-set robust menu metric is original to this illustration, **not**
the paper's best-proposed-offer metric and not an estimate of the paper's scores.
The diagnostic evaluator uses true utilities; the buyer receives only its view.

| Fixed buyer / fixed seller | Coarse offer | Fine offer | Quality coarse/fine | Welfare coarse/fine |
|---|---|---|---|---|
| steady / cost-floor | 9 | 9 | 8 / 8 | 8 / 8 |
| cautious / cost-floor | none | 5 | 8 / 8 | 0 / 8 |
| pressure / cost-floor | 9 | 3 | 8 / 8 | 8 / 0 |

Steady ignores the signal. Cautious waits without an exact cost and benefits from
it. Pressure follows the same brittle rule in both runs: if the exact floor is
known, demand below it; otherwise use the conservative menu price. The fine offer
is rejected by the unchanged seller rule. Scripts may propose off-menu prices;
the menu defines the candidate diagnostic, not a proposal restriction.
This deliberately irrational pressure script produces a **sign reversal** while
candidate quality stays fixed and its feasible set improves. It is an existence
example, not evidence about LLMs or a village disclosure optimum. It does not show
that less information is always better: the cautious strategy has the opposite sign.
Changing the script, recipient, or protocol can change the sign. The paper reports
model-, protocol-, and recipient-dependent effects; none are established here.

## Safeguards remain visible

Required safety/authorization evidence is never withheld from a checker. `Evidence`
is immutable and is passed intact into every view; only optional market cost detail
can be coarsened. The simulated review step reads both required bits before calling
the strategy and holds if either is absent/false. These are synthetic booleans,
not an implementation of real authorization, truth, or identity checking. Candidate
quality can remain positive even when safeguard failure holds realized welfare.
The disclosure API cannot designate a safeguard as optional.

## Run offline

```sh
python3 -m unittest test_disclosure.py -v
python3 fixtures.py
```

Tests inspect only local files and stdlib; no test reads the day index. Paper excerpt
checks read `/tmp/w17-2611.07667.html` and `/tmp/w17-2611.07667-abs.html` when
present and skip a source when absent. Snapshot byte counts, SHA256, normalization,
short excerpt offsets, and source-window hashes are in `paper_evidence.json`.
These provenance checks establish text presence, not empirical correctness.

## Provenance and limits

Method-cite only. Paper: arXiv perpetual non-exclusive licence
(`licenses/nonexclusive-distrib/1.0/`), **not CC BY**, **not a software grant**.
There is no accessible code pin: the paper's GitHub footnote
https://github.com/meterdogan07/agent-information-design returned public HTTP 404
on 2026-11-08 at 15:31:36 JST, independently checked with `curl -sI`.
A public 404 cannot distinguish nonexistent from private; no private mirror was sought.
No author implementation, data, prompts, or benchmark cases were used.

**Not implemented:** language models, double auctions, economic equilibrium,
price discovery, repeated negotiation, order books, continuous matching, tokens,
payments, market services, allocation engines, budget runtimes, production review
or authorization, policy optimization, and real-world disclosure recommendations.
Only deterministic one-shot arithmetic on original fixtures is implemented.

**UNVERIFIED:** all paper empirical / model results; transfer to real LLMs;
any claim that coarser disclosure is generally better; production use as a market
or allocation system. The pressure rule is authored to fail, not discovered from
observations. This scripted counterexample is not a replication and does not
establish any preferred disclosure policy outside these fixtures.

## Builder reflection

I separated the menu opportunity diagnostic from the action the script actually takes.
I kept the seller rule and each buyer function unchanged across policies so that the
sign reversal comes only from the optional signal triggering an existing branch.
I would not infer a real agent's information needs from a deliberately brittle script.

Ludex: Cody/Naru should keep required safety and authorization evidence visible to
reviewers, and compare optional disclosure only in paired, clearly labeled fixtures.

Implementation may be complete; it is not declared verified.
