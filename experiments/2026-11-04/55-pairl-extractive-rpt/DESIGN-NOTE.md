# PAIRL extractive `#rpt` + columnar `#evid` — V15 quote-substring verifier (Top KEEP-with-caveats)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint wave12 Top **#2**  
**Verdict**: **Top KEEP-with-caveats** — PAIRL v1.6 extractive carriage + encoder-side **V15** verifier sketched here; playground does **not** ship `pairl` PyPI/npm/Rust ports, LLM encoders, or `#cost` / `#quota` machinery.

## Upstream pin (honest)

| Field | Value |
|-------|--------|
| Upstream | [dwehrmann/PAIRL](https://github.com/dwehrmann/PAIRL) |
| Pin SHA | `0286fd1a3e6261872e56af50d48947927315b6e0` |
| License | **Apache-2.0** (repo `LICENSE`) |
| Test evidence (upstream @ pin, **VERIFIED** this fold) | Checker/Ork re-run at `0286fd1a3e6261872e56af50d48947927315b6e0`: `impl/python` **`python3 -m unittest discover -s tests` → 33/33 OK**; **`python3 -m pairl validate --strict` on `examples/*.pairl` → 9/9 OK** (clone at pin; not vendored in playground) |
| V15 in upstream | **Specified** in [SPEC.md §3.1 / §11 V15](https://github.com/dwehrmann/PAIRL/blob/main/SPEC.md) — **reference parser validates V1–V12 only**; **no shipped V15 verifier** at pin (ours to write, sketch below) |

Authoring tip commit on playground default branch: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` — this experiment branches from that tip without rewriting history.

## Real mechanism (Checker framing)

- **v1.6 lossy channel**: `#req` / `#rpt` `content="…"` may use **extractive** carriage — byte-exact source fragments joined by the normative elision marker `` ` [...] ` `` (space-bracket-three-dots-bracket-space). Unmarked records are **quotation promises**, not paraphrase ([SPEC §3.1](https://github.com/dwehrmann/PAIRL/blob/main/SPEC.md)).
- **V15 (encoder-side)**: split unmarked `content` on `` ` [...] ` ``; each fragment must appear **in source order**, **non-overlapping**, and **byte-exact in the source turn** (SPEC also mentions whitespace normalization at encode time — this playground sketch uses **literal substring** `str.find` for clarity; see caveats).
- **Lossless handoff**: citable numbers/names live in **`#fact` / `#evid`**, not only inside lossy quotes. **v1.5 columnar blocks** declare schema once (`#evid[claim,src,conf]` + positional rows) — see upstream [examples/08-columnar-report.pairl](https://github.com/dwehrmann/PAIRL/blob/main/examples/08-columnar-report.pairl).
- **One-message Ork→Smith handoff sketch** (extractive `#rpt` + columnar `#evid`; **quoted `content` fragments are excerpts of a source turn, not full messages**). Source turn bytes: upstream [examples/09-extractive-quotes.pairl](https://github.com/dwehrmann/PAIRL/blob/main/examples/09-extractive-quotes.pairl) `#a2` @ pin (also in [`handoff_showcase.py`](./handoff_showcase.py)).

```text
@v 1
@id handoff-m1
@ts 2026-11-04T10:00:00.000Z

#a_ork
#rpt content="Check maxclients in redis.conf — Redis 7.2 lowered the default from 10000 to 4096. [...] stuck in CLOSE_WAIT you could hit the limit." @rid=r1
#evid[claim,src,conf]
"maxclients default 4096 on Redis 7.2" redis.conf@7.2 0.95
"pool 200 conn × 12 pods = 2400" capacity-sheet 0.90
#fact redis_maxclients_default_7_2=4096 @rid=f1
```

**V15 on showcase**: `SHOWCASE_EXTRACTIVE_RPT_CONTENT` in [`handoff_showcase.py`](./handoff_showcase.py) **passes** `verify_quote_substrings_v15` against `SHOWCASE_SOURCE_TURN_A2` (unittest `test_showcase_handoff_extractive_rpt_passes_v15`). A paraphrased first span (`lowered maxclients default` vs source `lowered the default`) **fails** with `not_substring` — see `SHOWCASE_PARAPHRASE_RPT_CONTENT`.

Every byte inside unmarked `content="…"` must survive **V15** against the **source turn text** before emit; columnar `#evid` rows carry audit-friendly claims separately. **Elision with nothing omitted** between adjacent fragments (e.g. `hello [...] world` on source `hello world`) is **accepted** when both spans are exact substrings in order.

### ALLOW (this experiment)

- Document pin, ALLOW/FORBID, extractive one-message `#rpt` + columnar `#evid` handoff sketch.
- ~30 LOC pure **`verify_quote_substrings_v15`** — accept exact substring quotes; reject non-substring / out-of-order overlap failures.
- Unittest green in this folder only.

### FORBID (hard)

- LLM encoder / span proposer wired to production
- Rust / TypeScript **ports** of `pairl` (upstream owns `impl/`)
- `#cost` / `#quota` machinery in this folder
- Forbidden stack: DSH, Feishu, SQLite, daemon, headcount Soft→Top conflation
- **Do not touch** AgentBaton park (open PR #10) or NVIDIA note (merged PR #11)

## Pure-fn sketch (playground)

Module: [`quote_substring_v15.py`](./quote_substring_v15.py)

```text
verify_quote_substrings_v15(
  source_turn,
  quoted_content,
  mode_cond=False,
) -> QuoteVerifyResult(ok, reason, fragments)
```

| Outcome | When (sketch) |
|---------|----------------|
| **ok** | Each fragment after `` ` [...] ` `` split is found in `source_turn` via ordered, non-overlapping `find` |
| **reject** | Empty fragment, **`not_substring`** (fragment absent from source), **`out_of_order`** (fragment exists earlier but not after prior span), or overlap violation |
| **skip** | `mode=cond=True` → V15 not applicable (condensate carriage) |

Tests: [`test_quote_substring_v15.py`](./test_quote_substring_v15.py):

```bash
cd experiments/2026-11-04/55-pairl-extractive-rpt
python3 -m unittest test_quote_substring_v15.py
```

## Conceptual overlap (not Soft→Top)

- **AXL** typed handoff + validator gate ([`42-axl-protocol-handoff-design-note.md`](../42-axl-protocol-handoff-design-note.md) when present on branch) also separates **claims vs verified bytes** — PAIRL adds **extractive quotation** + **columnar evidence blocks** on the wire. Mention only; no promotion of Soft rows to Top.

## Sibling links (folder names — not PR numbers)

| Experiment | Link |
|------------|------|
| Nunchi `look_again` presend recheck | [54-nunchi-look-again](../54-nunchi-look-again/) (sibling Top sketch when merged) |
| Columnar / lossless patterns (upstream) | PAIRL `08-columnar-report` example (pin repo) |
| AgentBaton failure escalate (markdown) | [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) |
| PCP shared-human ask queue | [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) |
| **This folder** | [55-pairl-extractive-rpt](./) |

## Checker-ready honesty (KEEP-with-caveats)

**KEEP**

- Pin SHA, Apache-2.0, and **V15 missing upstream** stated plainly.
- Extractive `#rpt` + `#evid[…]` handoff sketch matches SPEC v1.6 intent channel + v1.5 columnar lossless channel.
- Minimal verifier + unittest passing locally in this directory.

**Caveats**

- Sketch **does not** implement SPEC whitespace normalization — production encoder should normalize then re-copy source bytes before emit.
- No `pairl` parser integration; message-level validators **must not** flag V15 without source (per SPEC).
- Elision marker is **exact** `` ` [...] ` `` — typos in spacing/brackets are rejections, not fuzzy repair.
- `#evid` conf scores in the sketch are placeholders, not calibrated.

## Status

- [x] Design note (this file)  
- [x] Pure-fn V15 verifier sketch + unittest  
- [ ] Complete (no `pairl` submodule; **do not merge** this PR by agent)

**Model (completion summary)**: composer-2.5
