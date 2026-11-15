# Closed sequential failure signatures

KEEP Top; paper-method only; method-cite of [arXiv 2611.04142v1](https://arxiv.org/abs/2611.04142), *Interpretable Early Termination of Web Navigation Agents via Closed Sequential Pattern Mining*, Sergio Talavera and Magdalini Eirinaki. Not Team OS law. Not a reproduction of paper F1, coverage, or token-savings figures.

## What this measures

Python 3.10+ stdlib only. All traces, outcomes, hand counts and displayed metrics are **synthetic**. Opaque `click`, `type`, `nav`, `scroll` tokens represent tool steps, not real evaluation traces. Training and test IDs are disjoint, fixed in fixtures.py; overlapping behavior is intentional, including a failure/success pair with identical observations. This illustrates unavoidable false positives, not deployment accuracy.

The miner grows frequent prefixes using per-trace earliest end positions, then rejects any pattern with a proper supersequence of equal support. Support counts traces, not occurrences. This exact closure check is method-inspired, not the BIDE+ implementation. It mines all closed patterns over the supplied prefixes before training-only failure-precision filtering. Immutable tuples and frozen records hold traces, patterns, signatures and reports. No network, model, third-party package, or data collection is used.

Pinned synthetic settings: K=3; minimum support=2 traces; minimum training failure precision=0.75; primary configuration=Exclude-errors. The resulting synthetic signature is `click -> click -> nav`, support 2, training failure precision 1. The held-out success with that prefix is explicitly counted as a false positive.

Coverage here is **all evaluated traces with at least one signature / all evaluated traces**. Precision is TP/(TP+FP); recall is TP/(TP+FN), where failure includes retained timeout/error labels. These are separate helpers and fields; zero-denominator rates are zero with raw counts retained. The paper's failure-library coverage uses a different denominator; our overall coverage is not that quantity. With the primary synthetic configuration: evaluated=5, matched=3, TP=2, FP=1, FN=1; coverage=3/5, precision=2/3, recall=2/3. Equality of the last two is incidental, not a shared definition.

## Contamination controls (paper Section 3)

Full retains every category, including the zero-step crash and trivial one-step success. Exclude-errors removes every error (including the zero-step crash), retains timeouts as failures, and removes successes with at most one step. Variant C performs that same cleaning and additionally removes timeouts; only natural failures versus multi-step successes remain. No fourth configuration is introduced. All three configurations are exercised on the same fixed held-out IDs with the same training library to isolate denominator/filter effects. Synthetic Full counts are (7,3,2,1,2), cleaned counts are (5,3,2,1,1), and Variant C counts are (4,2,1,1,1), in order evaluated/matched/TP/FP/FN.

The paper names the filters as all categories / remove errors / remove errors and timeouts. Separately, Section 3 says the medium-task corpus avoids single-step successes by design. We model that corpus curation within both cleaned configurations while retaining the pilot contaminants in Full to show their effect. Removing <=1-step successes also rejects hypothetical empty successes (none in fixtures). This is an explicit synthetic modelling choice, **not a literal reconstruction** of the paper's dataset pipeline. The exact interaction of that curation and the named Full configuration is UNVERIFIED. Zero-step natural failures are not silently removed.

## Policy boundary

At each observed step through K, an ordered-subsequence match emits STOP_AND_REPORT with the matched signatures and zero-based positions. An unmatched prefix emits UNMATCHED, which is not success. An already-expired observation emits TIMEOUT, which is not success (deadline precedence). There is no permission-granting API or external action. Offline timeout-labeled traces can be predicted before their eventual deadline; that differs from an already-expired runtime observation. Signature matching uses any-match rather than the paper's aggregated coverage score/tuned threshold; this simplification is UNVERIFIED against the paper policy. No token-savings estimator is implemented.

## Run

```bash
python3 -m unittest test_fail_signatures.py -v
python3 fixtures.py
```

Tests independently enumerate subsequences and compare closed sets, pin held-out counts and contamination settings, expose false positives, check immutable records, audit imports and prohibited implementation strings, and check brief stored paper evidence offline. The intended day-index entry is w16-3, KEEP Top, method-cite, not a reproduction.

## Attribution and number hygiene

Fetched HTML identifies the paper licence as **CC BY-NC-SA 4.0**. Only brief attributed method excerpts/section anchors and metadata are retained in paper_evidence.json; no paper tables, paragraphs, prompts, traces or captions are redistributed. The HTML hash identifies the fetched bytes, not proof of scientific correctness. No upstream code pin: no author repository was found; none was guessed or cloned. See NOTICE. This is clean-room method borrowing, not MIT relicensing of paper text.

The paper's best short-prefix F1 on balanced Exclude-errors, its failure-library coverage, and its high-precision policy's token savings and recall are different quantities, not targets or reproduced results here. The numeric distinctions and configurations are recorded only as non-target provenance in paper_evidence.json. Abstract/result sentences are context-dependent empirical reports, not universal laws.

## UNVERIFIED / limits

- All paper empirical results, upstream behavior (no upstream code pin), and applicability to real traces.
- Synthetic opaque tokens omit selector, outcome, reasoning-intent dimensions and the paper's taxonomy; signatures do not justify architecture-repair claims.
- Corpus curation interpretation, any-match policy, support/precision choices, manual fixed split and lack of balancing/tuning differ from the paper.
- Enumerative closure is exponential in prefix length; only tiny synthetic inputs are intended. No scalability or equivalence to BIDE+ runtime claims.
- Human-reviewable output is structural only; no user study or operational benefit is established.

Implementation may be complete; it is not declared verified.
