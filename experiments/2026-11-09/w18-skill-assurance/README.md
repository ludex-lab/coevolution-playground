# w18-skill-assurance

A small, deterministic method sketch of one idea from
[arXiv 2611.07652](https://arxiv.org/abs/2611.07652), "Don't Prompt Your
Agents. Equip Them: Skillware as a Modular Standard for Sovereign, Auditable,
and Deterministic Capability Execution for Logical Systems" (Peilivanidis):
a skill is a typed input contract, a deterministic effect and an offline
assurance step, and the assurance runs before the skill can join a registry.

The part this sketch tests is narrower: the assurance is **derived from the
contract**. Probe inputs come from the manifest's input contract, and each
output is checked against the manifest's output contract and declared safety
boundary. The author's own checks must pass too, but passing them is not
enough to register.

This is a method sketch, not a reproduction. It does not import, install or
run Skillware, and it does not reuse its code or its source audit.
It is not village law and not Team OS law.

## How to run

```
cd experiments/2026-11-09/w18-skill-assurance/ && python3 -m unittest test_assurance.py -v && python3 fixtures.py
```

Python 3 standard library only (`json` for the manifest). No network, no
files written. Two evidence checks in the tests read local copies and are
skipped when the file is absent:

- `/tmp/w18-2611.07652.html`, the paper HTML:
  `curl -sL https://arxiv.org/html/2611.07652 -o /tmp/w18-2611.07652.html`
- `/tmp/w18-skillware-README.md`, the upstream README at the cited commit:
  `curl -sL https://raw.githubusercontent.com/ARPAHLS/skillware/25e4cf662a39a907f721455c0f0044444c019465/README.md -o /tmp/w18-skillware-README.md`

## Files

- `manifest.json`: the toy `pack_cart` skill. Input contract: `sacks`
  integer 0 to 8, `bin` one of `south`/`east`, `spare` boolean, no extra
  fields. Output contract: `crates` integer 0 to 10 (the cart cap), `bin`
  one of `south`/`east`, no extra fields. Safety boundary: no `bin_key`
  field in output, never `bin = north`, no runtime code synthesis, no network
  modules, deterministic.
- `effect.py`: one crate per sack plus two spare crates on request. Pure.
- `assurance.py`: contract checks, probe derivation, a simple original
  source-token scan, and the registry. Verbs: `hold`, `register`, `reject`,
  `report` on the registry; `detect` (assurance report) and `compare`
  (author checks beside assurance). `invoke` runs a registered skill.
- `fixtures.py`: the good skill and five broken ones, and a summary printer.

### How assurance is derived

`derive_probes` reads only the manifest: each integer field gives its
minimum, minimum+1, midpoint, maximum-1 and maximum; each string field gives
every enum value; each boolean gives both. The cross product is 20 in-contract
probes for `pack_cart`. `detect` scans the effect's source tokens first (an
effect that names `exec`, `eval`, `compile` or `__import__` is rejected
without being run), then runs every probe twice and records any output that
breaks the output contract, the safety boundary, or gives a different result
on the second call. `register` runs the author's checks and `detect` itself;
it takes no report from the caller.

## What the fixtures show

- **(a) Contracted shape.** The good skill registers. `{"sacks": 5, "bin":
  "east", "spare": true}` returns `{"crates": 7, "bin": "east"}`, which
  checks clean against the output contract.
- **(b) Rejected before the effect runs.** Nine out-of-contract inputs (too
  many sacks, negative, string, boolean, float, `north`, a missing field, an
  extra field, a list) are all rejected, and the effect's call counter does
  not move. A spy effect confirms it is never entered.
- **(c) Assurance comes from the contract, not the author's test.** Five
  broken skills each pass their author's own check, then fail assurance:
  - doubling packer: the author checks 3 sacks gives 6 crates, which is true
    and under the cap; the probe at 7 sacks gives 14, above the declared
    maximum of 10. Raise the declared maximum to 18 and the same effect passes
    the same assurance code, so the reject comes from the declared number;
  - east spill: spare loads for `east` go to `north` (forbidden value);
  - empty-cart key: an empty cart returns `bin_key` (forbidden field);
  - built-from-string: the effect works, but names `eval` (never run);
  - drift: hidden state adds a crate on every other call (not deterministic).

  None of the author checks mentions the boundary it breaks, and the same
  author check passes on the good effect and on three broken ones.
- **(d) A failed skill cannot be registered.** All five broken skills are
  rejected with reasons, cannot be invoked, and a retry is rejected again.
  Only `pack_cart` is registered. For comparison, a gate that registers
  whenever the author's checks pass would have taken all six.

## UNVERIFIED

- The paper's benchmark results and cost or token figures are the author's
  claims about their own framework. They are not checked here and none are
  used; `paper_evidence.json` lists them, marked UNVERIFIED.
- Skillware's own code, tests and source audit were not run or read beyond
  the LICENSE and README at the cited commit.
- Boundary probes catch boundary breaks only where the effect misbehaves at
  an edge, a midpoint or an enum value. An effect that misbehaves only at an
  input between probes (say, only at 5 sacks) would slip past; the probe set
  is a sketch, not a proof.
- Real contracts (nested objects, free text, floats) need richer probe rules
  than these three field types.

## Builder reflection

I made the author's check true and useful on purpose, so the only thing
that can reject the doubling packer is the cart cap written in the
manifest. Deriving probes from declared edges turned the contract into the
test plan, which is why raising the cap to 18 changes the verdict and
nothing else does. The weak spot is between the probes: assurance is only
as good as the edges the contract declares.

Ludex: before Naru lets Cody's new packing routine onto the mill road, she
loads a cart at 0, 1, 4, 7 and 8 sacks, both bins, spare or not, and turns
the routine away the moment any cart tops ten crates or heads north, even
though Cody's own three-sack trial came out fine.

Implementation may be complete; it is not declared verified.
