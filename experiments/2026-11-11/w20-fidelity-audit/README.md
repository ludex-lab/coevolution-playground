# w20-fidelity-audit

A tool pass vouches for the one artefact it ran on and says nothing about
any claim. Here a claim is checked by toy tools against an artefact; each
tool result binds to that artefact's id and content digest, and audit()
runs the named tool again and drops a result whose outcome it cannot
reproduce. Whether the artefact says what the claim says is a separate,
recorded human decision, and that record, like the human token that
decides at a fixed point, names the digest of the content the human
judged: change the content and the old records stop counting. A claim with
two meanings must be cut into readings on purpose before anything about it
is accepted, and a dialog report credits every step to human, ai or tool.

This is a method sketch of the framework in
[arXiv 2611.13042](https://arxiv.org/abs/2611.13042) (Eigner, Süli and
Hollós; CC BY 4.0; no code linked). It is not a reproduction, not Team OS
law and not village law. Clean-room Python 3 stdlib, synthetic deterministic
data, no network, no model in the loop. The paper's tool layer is out of
scope; two toy deterministic tools stand in.

## Run

```
cd experiments/2026-11-11/w20-fidelity-audit/
python3 -m unittest test_fidelity_audit.py -v
python3 fixtures.py
python3 mutants.py
```

The source check in the tests reads the abs-page copy named in
`paper_evidence.json` from `$W20FA_SOURCES` and is skipped when it is
absent. `mutants.py` applies one source-text mutation at a time to
`fidelity_audit.py` (code mutants) or to `fixtures.py` (world mutants) in
a temporary copy of this directory, runs `fixtures.py` and the suite there,
prints killed or survived per mutant and two summaries, and removes the
copy. Its 78 code mutants are grouped by guarantee: (a) binding and
re-run 12, (b) no oracle, the human record and its content digest 12, (c)
fixed point, ordering and `on_expiry` 29, (d) split and no merge 9, (e)
attribution 10, fail-closed checks 6. All 78 are killed; none is marked
equivalent. Its 16 world mutants (11 disarm an adversarial world, most of
them with the expected outcome edited to match; 5 drop a world or shrink
the seeds) are all killed; 13 of them leave `fixtures.py` passing and are
caught only by the suite, mostly by the witness test.

## No fidelity oracle

The paper points out that, in general, no procedure can settle whether a
formal translation preserves the meaning of the original text. This sketch
claims no automatic fidelity check:

- the fidelity verdict is a record `FidelityVerdict(verdict_id, claim_id,
  reading_id, artefact_id, content_digest, verdict, at)`, `verdict` in
  {`faithful`, `unfaithful`}; it counts only when the dialog report
  credits it to a human and its `content_digest` equals the digest of the
  artefact's content now;
- the module never reads a claim's statement, and reads artefact content
  only inside the toy tools and `digest()` (a test walks the source to
  hold this);
- so if a human records a wrong-reading artefact as faithful, the module
  follows the record (`DoneWhenB.test_outcome_follows_the_human_record_only`).
  It reports; it does not second-guess.

## Records

| Record | Fields |
|---|---|
| `Claim` | `claim_id, statement, ambiguous` |
| `Artefact` | `artefact_id, claim_id, reading_id, content` with `content = ("forall", lo, hi, lhs, rhs)` over named toy functions |
| `ToolResult` | `result_id, tool, artefact_id, digest, outcome` (`PASS`, `FAIL`, `ERROR`), produced by `run_tool(tool, artefact, result_id)` |
| `FidelityVerdict` | `verdict_id, claim_id, reading_id, artefact_id, content_digest, verdict, at` |
| `HumanToken` | `token_id, claim_id, reading_id, artefact_id, content_digest, decision, at` (`accept` or `reject`) |
| `SplitRecord` | `split_id, claim_id, readings, at` (two or more distinct reading ids) |
| `Step` | `step_id, actor, action, ref` (`actor` in `human`, `ai`, `tool`) |
| `AuditConfig` | `on_expiry, deadline, required_tools` |

Toy tools: `enumerate` checks `lhs(n) == rhs(n)` for every `n` in
`[lo, hi]`; `endpoints` checks only `lo` and `hi`, a weaker ground of trust.
Malformed content, `hi` above 200 or an unknown name gives `ERROR`. The
digest is a plain sha256 of the content's repr: no key, no signature.
`content_digest` must be 64 lower-case hex characters; anything else is
`config_error`.

## Audit order

`audit(case, cfg, claim_id, reading_id="")` fails closed, in this order:

1. config or case errors (types, ids, values, missing `on_expiry`, the
   permit token, bad deadline or tools) -> `config_error`;
2. invalid dialog report -> `not_accepted` / `report_invalid`;
3. ambiguity: an ambiguous claim itself is never decided
   (`ambiguous_needs_split` with no split, `split_no_merge` with one); a
   reading needs exactly one split record that lists it;
4. tool results for the target's own artefacts whose digest matches the
   artefact's content now (else `result_not_bound_to_artefact`) and which
   a fresh `run_tool` on that artefact reproduces exactly (else
   `result_not_reproduced`: a hand-written PASS on content the tool FAILs,
   or on content no tool can check, is dropped); none ->
   `result_not_reproduced` if any result was dropped for that reason, else
   `no_bound_tool_result`;
5. human fidelity verdicts for the target that name an artefact with a
   bound result (else `verdict_artefact_mismatch`), whose `content_digest`
   is that artefact's digest now (else `verdict_not_bound_to_content`), and
   recorded by the deadline (else `verdict_late`). None usable ->
   `verdict_not_bound_to_content`, then `verdict_artefact_mismatch` (both
   `not_accepted`), then `verdict_late` (the declared `on_expiry` status),
   else `no_fidelity_verdict`. Conflicting, all unfaithful
   (`unfaithful_artefact`, even if every tool passed) or several faithful
   artefacts (`several_faithful_artefacts`) -> `not_accepted`;
6. on the faithful artefact: any `ERROR`, a required tool missing, or
   tools that disagree -> `not_accepted`; all `PASS` -> candidate proved;
   all `FAIL` -> candidate refuted;
7. human token at the fixed point: tokens with `at > deadline` are late;
   tokens naming another artefact (`token_artefact_mismatch`) or other
   content (`token_not_bound_to_content`) are rejected, and so is a token
   not strictly after every usable faithful verdict on that artefact
   (`token_before_verdict`). If tokens were rejected for one of those three
   reasons -> `not_accepted` with it; otherwise no on-time token ->
   declared `on_expiry` (`DENY` -> `denied`, `HOLD` -> `held`, `ESCALATE`
   -> `escalated`, `SAFE_FALLBACK` -> `safe_fallback`);
8. proved + `accept` -> `accepted`; refuted + `reject` -> `refuted`; any
   other pairing -> `not_accepted`.

Only `accepted` sets `accepted=True`. `claim_summary` reports a split
claim's readings one by one next to its parent, which stays
`split_no_merge`.

## Silence doctrine

Taken from merged
[#78 w14-silence-expiry](https://cursor.com/codebase/coevolution-lab/playground/pull/78):
a missing or late human token, or a fidelity verdict recorded after the
deadline, resolves only to the declared `on_expiry`, none of which accepts; a missing declaration is `config_error`, even when a
token is present; the permit token in any case is `config_error`; so is any
value outside the four names, a non-`str` or a `str` subclass.

## Done-when, as tests

| | Requirement | Tests |
|---|---|---|
| (a) | a tool PASS is bound to an artefact id; PASS on an artefact stating a different reading -> not accepted | `DoneWhenA.*`: result carries artefact id and digest and no claim id; `pass_on_different_reading`; PASS on older content or on another claim's artefact does not count; a forged PASS on failing or uncheckable content, a forged FAIL or ERROR, and a result naming an unknown tool are not reproduced; every accepted target has a bound, reproduced PASS on its own artefact |
| (b) | no fidelity oracle; the verdict is a recorded human decision {claim_id, artefact_id, verdict}; a verdict naming a different artefact_id is rejected | `DoneWhenB.*`: source walk, record shape, outcome follows the record, `verdict_names_other_artefact`, verdicts from ai or tool invalid; a verdict or token for content that has since changed does not count; malformed digests are `config_error`; two faithful artefacts -> no pick |
| (c) | human token missing or late -> declared on_expiry; missing declaration -> config_error; permit token -> config_error; never accept | `DoneWhenC.*`: all four values x missing / late, deadline boundary, a verdict after the deadline -> declared on_expiry, a token at or before a verdict -> not accepted, every design and scenario target with tokens removed is never accepted or refuted |
| (d) | ambiguous claim not accepted until an explicit split; one reading refuted, the other proved, each with its own audit; no implicit merge | `DoneWhenD.*`: `split_one_proved_one_refuted`, `reading_reuses_other_audit`, parent stays `split_no_merge` even when every reading is proved |
| (e) | dialog report attributes every step to human / ai / tool; an unattributed step makes it invalid | `DoneWhenE.*`: unattributed actors (including a `str` subclass and a `str` Enum equal to `"human"`), a verdict or token with both a human and an ai or tool step, records without steps, wrong actors, dangling refs, empty report |
| (f) | hygiene; the paper's example UNVERIFIED and not reproduced | `DoneWhenF.*`: banned words, the permit token, conflict markers, import whitelist, paper figures only in `paper_evidence.json`, figure labels match their tokens, offsets against the abs-page copy, no run of five abstract words outside `paper_evidence.json` (title excepted) |

## Fixtures

- Design (`fixtures.DESIGN`, 24 cases): accepted; PASS on a different
  reading; verdict naming another artefact; PASS on older content; token
  missing and late for each `on_expiry`; ambiguous without a split; the
  shape of the paper's example, on a toy identity of this sketch's own
  choosing (the sum of the odd numbers up to n is n squared: "the first n
  odd numbers" is proved, "the odd numbers not above n" is refuted); a
  reading that borrows another reading's audit; a verdict attributed to
  the ai; tools that disagree; and seven adversarial worlds from review:
  a stale verdict and a stale token after a content change, a forged PASS
  on failing and on uncheckable content (`("trust", "me")`), a verdict
  after the deadline and after the token, a token before the verdict, and
  two artefacts both judged faithful.
- Seeded scenario test (`fixtures.SCENARIOS`): seeds 4101-4112. Each seed
  draws 13-19 labels from a table of 31 scenarios; each label fixes the
  expected `(status, reason)` of every target before any record is built.
  Records are then written with random identities, ranges, ids, times,
  deadlines, tool sets and `on_expiry` values, and steps are shuffled. The
  seeds vary the records but add no evidence beyond the labels, so every
  attack is a label of its own. Twelve labels are adversarial
  (`fixtures.ADVERSARIAL`), and the tests hold a witness for each: the
  generated records must really carry the attack (a forged result really
  differs from a fresh run, a stale verdict's digest really differs from
  the content, two faithful artefacts really both reproduce), so a fixture
  edit that disarms a world fails the suite.

## Overlap with earlier experiments

- `experiments/2026-11-04/12-pcm-proof-carrying-handoff-day-sketch.md`
  (on main, markdown only): its stale-evidence row (a green test on an old
  SHA) is the same failure as a PASS bound to other content. Here it is
  executable: a result counts only when its digest matches the artefact's
  content now.
- `experiments/2026-11-04/27-pc2-lean-proof-handoff-checklist.md` (on
  main, markdown only): a proof receipt per action. Here the receipt is a
  tool result, and a receipt alone never accepts a claim.
- [`experiments/2026-11-06/w15-evidence-gate/`](../../2026-11-06/w15-evidence-gate/)
  (on main): reviewer disposition plus a mechanical certificate check.
  Here the mechanical part (tools) and the judgment part (fidelity, human
  token) are separate records that must agree on one artefact.
- `experiments/2026-11-04/50-claim-vs-verified-ledger-design-note.md` (on
  main; the name is that note's own): separates self-report, host
  verification and acceptance. Same separation here, with fidelity as a
  fourth lane. Nothing here stores an append-only record of any kind.
- [#109 w19-guardrail-order](https://cursor.com/codebase/coevolution-lab/playground/pull/109)
  (merged) and [#110 w19-authz-drift](https://cursor.com/codebase/coevolution-lab/playground/pull/110)
  (open, read only): checks that read what ran. Neither asks whether the
  thing checked is the thing claimed.

What this adds: the artefact may state a different claim; a tool pass binds
to the artefact; acceptance needs a separate human fidelity record on the
same artefact plus a human decision at a fixed point.

## Not included

No signing, keyed hashes or ledger; no SQLite; no daemon, thread or network;
no language-model API; no voting; no computer algebra, numerics, proof
assistant or statistics package; no reproduction of the paper's example.

## Limitations

- Synthetic and deterministic. The tools are two toy integer-identity
  tools, not the paper's tools, and nothing here checks a real proof.
- Fidelity is exactly as good as the human record. The module holds the
  binding (same claim, reading and artefact) but cannot detect a human
  who records a wrong-reading artefact as faithful.
- Tool disagreement, conflicting verdicts and conflicting tokens all end
  in `not_accepted`; there is no resolution protocol.
- A reading's content is not compared across readings; two readings with
  identical artefacts are audited separately and may both pass.
- Time is an integer per case with one fixed point; multi-stage fixed
  points are not modelled. A verdict must be recorded by the deadline and
  strictly before the token; the times themselves are taken as recorded.
- Re-running a tool proves only that the stored outcome is what this
  module's own toy tool gives on that content. It holds a forged record,
  not a faulty tool.
- The content digest binds a verdict to the bytes the human judged, not to
  what the human understood; a human who records a digest without reading
  the content cannot be detected.
- The dialog report checks attribution, not truthfulness: a step marked
  `human` is taken as human.
- The seeded scenario test is a labelled generator: it covers the 31
  scenarios its author wrote down and no others.

## Paper figures and wording

The paper's figures and its example are recorded only in
`paper_evidence.json`, as number tokens and span hashes with offsets in the
abstract field, and are marked UNVERIFIED. The PDF was not read. This
README, `NOTICE` and the code describe the method in their own words; no
sentence of the abstract is copied (the source test compares every run of
five words against the abs-page copy when it is present).

## Status

Review round 1 returned fix items; this revision addresses them. Its tier
is decided by re-verification, not claimed here.

## Builder reflection

The first version bound everything to names: a verdict to an artefact id
and a tool result to a record anyone could write, which is the weakness
the method warns about. Binding the human records to a content digest and
re-running the deterministic tool turned both into lookups that fail
closed. The larger lesson was about the fixtures: my generator only tested
the cases I had thought of, so the adversarial worlds now carry witnesses
and are mutated too.

Ludex: a seal on the jar says nothing once someone swaps the jam.

Implementation may be complete; it is not declared verified.
