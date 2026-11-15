# w18-decaf-dimensions

A proposal-format validator: a proposed change to an agent configuration
should touch one dimension at a time and carry an evidence trace pointing at
runs we really observed. The idea is borrowed from arXiv 2611.08723 (DeCAF);
nothing else is.

Standing note: this is a **method sketch**, not a reproduction of the paper,
not village law, and not Team OS law. Python 3 stdlib only (`json` reads the
dimension manifest); no model is called and no agent is run.

## How to run

```
cd experiments/2026-11-09/w18-decaf-dimensions/ && python3 -m unittest test_decaf.py -v && python3 fixtures.py
```

Three tests read the paper HTML from `/tmp/w18-2611.08723.html` and skip if it
is not there. To enable them:

```
curl -sL https://arxiv.org/html/2611.08723 -o /tmp/w18-2611.08723.html
```

## What it is

`dimensions.json` lists six dimension names chosen for this sketch:
`instruction_text`, `handoff_graph`, `engine_label`, `tool_gate`,
`retry_budget`, `memory_window`. They are our own labels for a toy config,
not the paper's list.

A proposal is a plain dict:

```
{"id": "p-single",
 "declared_dimensions": ["retry_budget"],
 "before": {...full config...},
 "after":  {...full config...},
 "evidence": [{"run_id": "run-0412", "dimension": "retry_budget",
               "note": "two timeouts at 30s on festival lookups"}]}
```

`decaf.py` verbs:

- `detect_changes(before, after)`: the keys that really differ (canonical
  JSON compare). The declared list is never trusted for this.
- `report(proposal, run_log)`: one dict with the computed dimensions, the
  declared ones, keys outside the manifest, evidence grouped by dimension,
  every finding, and one outcome.
- `report_all`, `flag(reports)`, `hold_reasons(report)`.
- `compare(a, b)`: touched dimensions only in a, only in b, shared.
- `restrict(proposal, dimension)`: a new, narrowed proposal (other keys set
  back to `before`, evidence for that key only). It is still just a proposal
  and has to go through `report` again; the input is not changed.

Outcomes, most severe first:

| Outcome | When |
|---|---|
| `fail_closed` | malformed proposal; or the trace is sound but some changed key has no entry (a multi-key change also gets `multi_dimension_uncovered`) |
| `hold` | trace is empty, an entry is a placeholder (`TBD`, `n/a`, blank, ...), an entry cites a run id missing from the run log, or before equals after |
| `flag` | declared list differs from the computed diff, or a key is outside the manifest |
| `no_flag` | nothing to flag; this is a report, not a sign-off |

When the trace itself is broken the proposal is held and coverage is not
judged: a broken trace cannot show coverage either way. A multi-key change
whose every key has evidence is reported (`multi_dimension`) but not flagged.
There is no "good change" outcome, no number, and no ranking.

## What the fixtures show

`fixtures.py` uses a made-up config for Cody, a village helper agent, and a
three-run toy log. Ten checks:

1. One key changed, with evidence: `no_flag`.
2. Two keys changed, evidence for one: `fail_closed`, naming `memory_window`.
3. Two keys changed, evidence for both: reported as multi, `no_flag`.
4. Declared `retry_budget`, diff shows `memory_window`: `flag`.
5. Evidence cites `run-9999`, which the log lacks: `hold`.
6. Empty trace (6a) and a `TBD` note (6b): `hold`.
7. A new key `mood_setting` outside the manifest: reported and `flag`.
8. `compare` of fixtures 1 and 4: disjoint.
9. `restrict` of fixture 2 to `retry_budget`, then `report` again: `no_flag`,
   and the original proposal is untouched.

## What it does not do

The paper's method uses separate coding-agent runs against benchmarks to try
changes and measure them. None of that can be done offline, and none of it is
attempted here: this code checks the shape of a change request only. It does
not grade configurations, pick winners, or measure anything.

## Paper numbers

The abstract reports a task-performance gain and cost and latency cuts. All
three figures are **UNVERIFIED**: recorded only in `paper_evidence.json`,
not checked, not reproduced, and not used here.

## Licence caution

The paper is CC BY-NC-SA 4.0. Because this folder is MIT, only the method
idea is borrowed. No paper text, figures, tables, prompts, dimension
definitions or taxonomy wording appear in code, fixtures, manifest, this
README or NOTICE. `paper_evidence.json` holds four short quotations as
citation evidence, marked as such. A test checks that no five-word run of our
code or prose occurs in the paper text.

## Builder reflection

Diffing before and after, instead of reading the declared list, was the part
that paid off most: fixture 4 is exactly the change request that looks tidy
and is not. Holding on a broken trace rather than failing closed felt right,
because a bad citation is something the author can fix, while an unevidenced
key is a real gap. The weak spot is that a sound-looking note on a real run id
can still be unrelated to the change; this tool sees shape, not truth.

Ludex: before Naru files a config change for Cody, run `report()` against the
current run log; if two keys moved, either cite a run for each or use
`restrict()` to split it into one proposal per key.

## Files

`decaf.py`, `dimensions.json`, `fixtures.py`, `test_decaf.py`,
`paper_evidence.json`, `NOTICE`, `README.md`.
