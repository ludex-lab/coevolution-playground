# w31-prerelease-is-not-stable

A pre-release is not the associated normal version. A requirement such as `>= 1.0.0` that is meant to name the
stable line should not accept `1.0.0-rc.1`, and a comparator that strips the `-rc.1` suffix before comparing gets
this wrong. `prerelease_gate.py` parses versions strictly, orders them by the precedence rules of Semantic
Versioning 2.0.0, and evaluates a small fixture of `{candidate, requirement}` pairs with three arms side by side.

## Credit and licence

Source: "Semantic Versioning 2.0.0" by Tom Preston-Werner (the page says the specification was "originally authored
by Tom Preston-Werner"), https://semver.org/spec/v2.0.0.html, licensed CC BY 3.0
(https://creativecommons.org/licenses/by/3.0/). This is a clean-room method sketch: the version grammar and the
precedence rules (spec §9 to §11) are borrowed as a method only. No code was copied, no implementation or package
was run, and the spec text is paraphrased except for a few short quoted phrases.

Not a remake: the Dependabot pin checklist (2026-11-04) is about pin types and the w14 version regex is a shape check only, while #153, w20-fidelity-audit, #154 and #155 are about evidence, claims, timelines and scoreboards; this is a precedence gate for pre-releases.

## What the spec says, and what is policy

- Spec: pre-release versions "have a lower precedence" than the associated normal version, so `1.0.0-alpha < 1.0.0`.
  Identifiers made of digits are "compared numerically", the rest lexically in ASCII order, numeric identifiers rank
  below alphanumeric ones, and a larger set of identifiers ranks higher when all earlier ones are equal. Build
  metadata is "ignored when determining version precedence".
- Spec: SemVer 2.0.0 defines precedence only. It has **no range operators**.
- Policy, not a SemVer rule: this tool declares two operators, `>=` and `==`, evaluated by §11 precedence, and
  treats every requirement as a **stable range** that also rejects any candidate with pre-release identifiers,
  whatever its core. The spec says a pre-release "might not satisfy the intended compatibility requirements"; the
  policy turns that into a hard line.
- It is not an npm or PEP 440 solver: other operators (`>`, `<`, `<=`, `~`, `^`, unions) and requirements naming a
  pre-release or build metadata are refused as `bad_requirement`, not evaluated.

## The three arms

| Arm | Rule | Role |
|---|---|---|
| `stable` | §11 precedence, then the stable-range policy | the declared gate |
| `precedence` | §11 precedence only | shown for contrast, never called stable |
| `weak` | strip every suffix, then compare cores | the planted wrong arm |

Reasons on the stable arm:

- `1.0.0-rc.1` vs `>= 1.0.0`: DOES_NOT_SATISFY, `pre-release < 1.0.0 (spec §11)`.
- `1.0.1-rc.1` and `2.0.0-alpha` vs `>= 1.0.0`: DOES_NOT_SATISFY, `pre-release excluded by stable range (policy)`.
  The precedence arm says SATISFIES for both.
- `1.0.0+build.5` vs `== 1.0.0`: SATISFIES (equal precedence; build metadata ignored). This pair is shipped in
  `fixtures/more.json`, so it is measured.

## Results (fixture-authored pairs)

- `fixtures/main.json`, the stable range `>= 1.0.0`: `1.0.0` and `1.0.1` satisfy; `1.0.0-alpha`, `1.0.0-rc.1`
  and `1.0.1-rc.1` do not. **closed: 5 / 5 on the declared comparator.** The weak arm gets 3 of 5 wrong (gate FAIL).
- `fixtures/more.json`: equality, `2.0.0-alpha`, `0.9.0`, `1.0.0-0`, `1.0.0-01a`, `1.0.0+001` and the
  build-metadata pair: closed 11 / 11; the weak arm gets 5 wrong.
- The spec's own chain `1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta < 1.0.0-beta.2 < 1.0.0-beta.11
  < 1.0.0-rc.1 < 1.0.0` holds for all 64 ordered pairs, and sorting shuffled copies recovers it.

## Strict version grammar

`MAJOR.MINOR.PATCH`, optional `-` pre-release identifiers, optional `+` build metadata, ASCII letters, digits and
hyphens only. These are DENY: `01.0.0`, `1.0`, empty, `1.0.0-`, `1.0.0-alpha..1`, `1.0.0-01`, `1.0.0+`,
`v1.0.0`. These are valid: `1.0.0-01a`, `1.0.0-0`, `1.0.0+001`.

## How to run

```
python3 -B prerelease_gate.py fixtures/main.json          # report; exit 0 when every pair closes
python3 -B prerelease_gate.py --json fixtures/main.json   # the same as JSON
python3 -B -m unittest                                    # the test suite
python3 -B demo.py                                        # deterministic demo (main.json, then more.json)
python3 -B mutants.py                                     # mutation run
```

## Contract

- Exit 0: every pair's stable verdict equals its `expected` value. Exit 1: a verdict was issued but some pair does
  not close (marked `[expected …]` in the report).
- Exit 2, on_expiry DENY: a missing, unreadable or malformed fixture, or any malformed version or requirement in it.
  Stdout is empty, stderr is one line starting `ERROR`, and no range verdict is issued for any pair.
- Caps, all on_expiry DENY: fixture 65536 bytes, 200 pairs, 128 characters per version, 200 per text field.
- The tool has no timeout. `mutants.py` bounds each suite run with `TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}`;
  a run that reaches it is reported TIMEOUT and is never counted as a kill.
- Stdlib only, system `python3 -B`, no network, deterministic.

## Fixtures

`main.json`, `more.json` and `korean.json` (Korean label and ids, same verdicts as `main.json`) are valid. The
64 `bad_*.json` files cover the malformed versions above and more (leading zeros in any part, four parts, a leading
hyphen, underscores, `+` inside build metadata, spaces, full-width digits, Greek letters, a zero-width space, the
length cap, non-text candidates), refused requirements (`>`, `<=`, `>=1.0.0` without a space, `~`, `^`, a
pre-release or build in the requirement, a union, no operator), and the JSON battery (not JSON, empty, duplicate
keys, NaN, Infinity, floats, booleans, huge integers, deep nesting, size cap, invalid UTF-8, byte order mark, lone
surrogates, control and bidi characters, edge spaces, missing and unknown keys, bad `expected`, no or too many
pairs, duplicate ids, and one bad pair among good ones).

## Files

| Path | What it is |
|---|---|
| `prerelease_gate.py` | parser, precedence, the three arms, fixture loader, report, command line |
| `test_prerelease_gate.py` | unittest suite, tests (a) to (i) and more |
| `demo.py` | deterministic demo |
| `mutants.py` | breaks the module one way at a time and requires the suite to fail every time |
| `evidence.json` | source, licence, measured counts, untested items under `on_unmeasured` |
| `fixtures/` | valid and `bad_*` fixtures |

Demo output sha256 (two runs, identical): `cce94c05bec379b16428fa866da54aab0138f768508f40d7dcb81201059ea18a`

## Limits

- Two operators only; the stable-range policy is a choice, and other ecosystems choose differently.
- Precedence is tested on the spec's chain and on authored pairs, not against any real package index.
- Build metadata is tested for equal precedence only.
- The saved copy of the spec page is the reference; later edits to the live page are not tracked.

## How a Ludex village would use it

When a village or Lab Dig pin says `>= 1.0.0`, run the candidate tag through the stable arm before taking it as the
stable line: a release candidate is reported with its reason instead of slipping in.
