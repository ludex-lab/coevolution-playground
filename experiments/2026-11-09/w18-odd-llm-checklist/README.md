# w18-odd-llm-checklist

A documentation-hygiene checklist for LLM-driven agent-based models, organised
into the five blocks named in arXiv 2611.08932 (ODD+LLM).

Standing note: this is a **method sketch**, not a reproduction of the paper,
not village law, and not Team OS law. Python 3 stdlib only (`json` reads the
manifest); no model is called.

## How to run

```
cd experiments/2026-11-09/w18-odd-llm-checklist/ && python3 -m unittest test_checklist.py -v && python3 fixtures.py
```

Two tests read the paper HTML from `/tmp/w18-2611.08932.html` and skip if it
is not there. To enable them:

```
curl -sL https://arxiv.org/html/2611.08932 -o /tmp/w18-2611.08932.html
```

## What it is

`checklist.json` lists the five blocks, with the paper's block names used as
headings only:

| Block | Name | Items here (own wording) |
|---|---|---|
| A | Cognitive Architecture | A1-A4 (3 required) |
| B | Identity | B1-B4 (2 required) |
| C | Inference Configuration | C1-C4 (3 required) |
| D | Behavioral Submodel | D1-D5 (4 required) |
| E | Validation | E1-E5 (3 required) |

Item ids, field names and questions are this sketch's own, short and
deliberately fewer than the paper's; they are not the paper's appendix coding
instrument, and the ids do not line up with its item numbers. A test checks
that no four-word run of any item question appears in the paper text.

`checklist.py` checks a synthetic model description
(`{"id": ..., "blocks": {"A": {...}, ...}}`) with five verbs:

- `hold(d)`: structural problems (not an object, no id, a block that is not an
  object). A held description is not checked.
- `detect(d)`: per block, which item ids are documented, missing, or
  placeholders, plus required gaps; undeclared blocks and fields are listed.
- `report(ds)`: per description, per block coverage as `n/m` strings
  (all items and required items). There is no overall number and no grade.
- `compare(a, b)`: item ids one description documents and the other does not.
- `flag(ds)`: descriptions with a required gap (named by block), an undeclared
  block, or a hold.

Placeholder rule: a value is documented only if it is a number, a boolean, a
non-empty list or object, or a string that is non-empty after trimming and is
not a placeholder word (`TBD`, `todo`, `default`, `n/a`, `unknown`,
`see code`, ...; case-insensitive, trailing dots ignored). A missing key or
null is *missing*; anything else that fails is *placeholder*. Both count as
not documented. `"n/a: this run has no tools"` counts as documented, because
it says why.

## What the fixtures show

`fixtures.py` builds six toy descriptions of a made-up "seed-swap" village
simulation and runs eight checks:

1. A fully documented description is not flagged.
2. A description with no Inference Configuration block is flagged in block C
   only (C1-C3); A, B, D, E stay full.
3. `TBD`, `default`, a blank string, `n/a.` and `[]` count as placeholders and
   are flagged in C, D and E.
4. An undeclared block `F` is reported by `detect`, `report` and `flag`, not
   dropped, and does not change block coverage.
5. Dropping the speaker-stance item (does the model answer as a narrator or as
   a participant) is flagged in block D only.
6. Gaps in optional items lower block coverage but are not flagged.
7. Coverage is reported per block; there is no overall field.
8. `compare` of the full description against the no-block-C one lists C1-C4.

## Paper numbers

The paper's abstract reports a multiverse result and a review-of-papers
result. Both figures are **UNVERIFIED**: recorded only in
`paper_evidence.json`, not checked, not reproduced, and not used here.

## Distinct from earlier sketches

No execution of anything (unlike the skill-assurance sketch), no harness
grading (unlike the harness scorer), no step record (unlike the step-ledger
sketch). It only reads a description and says what is written down.

## Builder reflection

The paper's useful move for us is not the full instrument but the habit: a
fixed home per block, so a gap shows up as a named hole instead of a vague
feeling that a writeup is thin. Writing my own item wording forced choices
about what is truly required; I kept required items few so the flag means
something. The weak spot is that this tool cannot tell a real answer from a
confident wrong one; it only catches absence and placeholders.

Ludex: before Naru or Cody post a run card for a village simulation, run
`detect()` on it and fill block C (dated model string, sampling settings,
seed) and D2 (narrator vs participant); any `TBD` there shows up as a gap.

## Files

`checklist.json`, `checklist.py`, `fixtures.py`, `test_checklist.py`,
`paper_evidence.json`, `NOTICE`, `README.md`.
