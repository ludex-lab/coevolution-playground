# w16-blast-radius

**KEEP Top; method-borrow only; not Team OS law.** Clean-room, stdlib-only
method sketch of Zhan, Forough, Zhang, Li, Ma and Haddadi,
[Airlock: Bounding the Multi-Agent Blast Radius via Selective Online Containment](https://arxiv.org/abs/2611.06727)
(arXiv:2611.06727v1, 4 November 2026).

## What this sketches

The [HTML paper](https://arxiv.org/html/2611.06727), sections 3.1–3.3,
describes an append-only provenance DAG, forward/backward tracing and the
**default containment tier: full quarantine**. This draft models that method,
not the upstream runtime or an Airlock-controller release:

- `add_node` / `add_edge` append immutable producer→consumer records.
  Cycles, missing endpoints, duplicate IDs, deletion and rewrite are rejected.
- `taint(alert)` closes forward from the alerted version through every
  recorded descendant. No model call decides whether an edge matters.
- `roots(symptom)` walks backward to return candidate ancestors (including
  the symptom), not a proven cause, a ranking, or only zero-in-degree roots.
- `quarantine(alert)` monotonically freezes the tainted reach. Tasks are
  treated as paused, artifacts held and pending effects denied at the
  simulated `actuate` gate. Non-descendants remain available.
- Late-recorded consumption refreshes taint/quarantine before a subsequent
  simulated actuation can run. Already committed effects are not undone.
- Authority edges require task endpoints, one parent per child and
  `child.permissions <= parent.permissions`. These are opaque synthetic
  effect-target tokens; administrator grants are assumed sufficient, not
  implemented. Effect scope authorization is not implemented by the gate.

The bad artifact in `fixtures.py` has **already been consumed** when the
alert is applied. Its reader, shared-memory successor, and pending actions
freeze; independent automation shares a planner ancestor but has no path
from the bad version and stays available.

## Deliberate simplifications and recovery boundary

This is synchronous in-memory reachability, not the paper's timestamp-aware
per-site taint rule. Every recorded data/session edge represents exposure;
all authority edges are also conservatively included in forward closure.
This may overtaint relative to the paper's time-respecting data/session rule
(section 3.2). No clocks, journals, distributed races, credentials, leases,
real gateways, task scheduler, persistence, or physical actuators are modeled.
Private Python state is not a security boundary against hostile callers.

Silence is **not approval**: `taint(None)` and `quarantine(None)` never clear
an earlier incident. A repaired version is a new immutable node, not a rewrite
of the bad version, and does not unfreeze old consumers. There is **no release
or approval API**. Appendix F's coding-collaboration case study explicitly
notes that repair reads do not automatically clear incidents and discusses
explicit post-incident endorsement as future work. Our permanent local hold
policy is a conservative assignment constraint, not a claimed reproduction
of an endorsement implementation. Absence of an initial alert does not detect
or prove safety of bad outputs.

The optimized cut tier, minimum-cut solver and fence-then-prune protocol are
entirely omitted. Theorem 5 is not implemented or established here.

## Run (offline)

```bash
python3 -m unittest test_containment.py -v
python3 fixtures.py
```

Run from this directory with Python 3.10+; no installation required. Tests use
synthetic fixtures only, audit imports with an explicit allowlist, and check
implementation string bans. Runtime and tests contain no network or LLM calls.
The demo prints only simulated state; it issues no external action.

## Paper evidence

The actual HTML was downloaded on 2026-11-07 (JST) outside the upload folder.
`paper_evidence.json` stores its SHA-256, three short checked sentences,
limited raw HTML excerpts and distinctive ASCII anchors. `PAPER_QUOTES` in
`fixtures.py` matches those excerpts after HTML text/whitespace normalization.
The test checks the excerpts offline; it does not re-fetch the paper or
independently authenticate the recorded digest. No full paper is bundled.
Paper license is displayed in the HTML as CC BY 4.0; see `NOTICE`.

## Upstream citation, not a port

[EdgeCitadelTeam/EdgeCitadel](https://github.com/EdgeCitadelTeam/EdgeCitadel)
@ `4d464fea391d16069f042873fd20213c6ea07533` is cited as the underlying runtime
(Appendix B), **not an Airlock-controller release**. No upstream source was
cloned, run, vendored or ported. License inspection was limited to public
GitHub pages through WebFetch; see `NOTICE` for URLs and evidence limits.

## Cited method versus UNVERIFIED claims

Cited and checked in HTML: sections 3.1–3.3 describe permission narrowing,
append-only provenance, forward/backward tracing and default full quarantine;
Appendix F discusses non-clearing repair reads and post-incident endorsement.

**UNVERIFIED empirical claims of the paper, not reproduced by this sketch:**
the 1,832-run study, zero post-convergence leaks and +68 to +96 pp healthy-work
retention gains. All other paper empirical results, detector accuracy,
root-cause ranking quality, latency/scale and real-world enforcement guarantees
are likewise unverified here. Synthetic test success is not paper replication,
formal verification, a production containment guarantee or a policy mandate.
The GitHub metadata value `license=null` is expected from the assignment but
**UNVERIFIED in this page-only inspection**; no API metadata was fetched.

## Path

This directory lives at `experiments/2026-11-07/w16-blast-radius/` and is listed
in the parent [day index](../README.md). Do not rewrite earlier experiment folders.
