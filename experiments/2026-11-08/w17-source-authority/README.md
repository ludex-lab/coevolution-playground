# w17-source-authority — decision-field source authority

Playground path: `experiments/2026-11-08/w17-source-authority/`

This is a **method sketch** of [arXiv 2611.07640](https://arxiv.org/abs/2611.07640),
*Beyond Instruction Override: Benchmarking Indirect Prompt Injection with
Task-Tampering Attacks* (submitted 5 Nov 2026). Paper method only; no repo code or data copied.
It is not Team OS law and not village law. There is no ALLOW path.

## Idea borrowed from the paper (paraphrased)

The paper draws the injection boundary by *authority over a decision*, not by
instruction-like wording: content is out of bounds when it tries to influence
a decision its source is not authorized to determine, and a false claim from a
source that *is* authorized is a different problem (misinformation) that needs
independent evidence. Short evidence excerpts with offsets are in
`paper_evidence.json`.

## What this sketch does

`authority.py` (stdlib only) resolves claims against a per-field authority map:

- Each consequential decision field declares exactly one **authorized source**
  (toy fields: `credit_amount` → `billing-ledger`, `ship_to` → `user-request`,
  `priority` → `user-request`, `stock_count` → `inventory-tool`).
- A claim from any other known source gets **REJECT_SET**: the field is left
  unchanged. The claim text is never read, so a truthful, polite, or
  instruction-free claim is treated the same as an override-style one.
- Authority is per source × field: `inventory-tool` may set `stock_count` and
  is rejected on `credit_amount`.
- **APPLIED** means the authorized source's value was copied into the field as
  data. It is not permission to act and not a truth verdict: every record has
  `truth_status = "unverified"`, and `check_correctness()` is a separate check
  that can fail on an APPLIED field (authority is not a truth oracle).
- Unknown source, missing authority map, missing/ambiguous/conflicting
  declaration, or disagreeing values from the authorized source → **HOLD** and
  report. Nothing is auto-resolved.
- `hold_consequential_action()` returns HOLD for send, payment, and merge and
  never emits a token. The module has no function that authorizes a send,
  payment, or merge.

## How this differs from #85 and #95

- **#85** asks whether a reviewer may replace a proposal. This sketch never
  replaces proposals; it asks which source may resolve each decision field.
- **#95** is role / speech-act admission (ATC): whether a message is admitted
  given who says it and what kind of act it is. Here every claim may be
  "admitted" as a message, yet it still cannot set a field its source does not
  hold authority for. The unit is source × field, not speech act.

## Fixtures (SYNTHETIC, original)

A toy village seed-shed order desk, authored independently. No upstream
benchmark case, prompt, schema, or data is used or paraphrased.

| id | case | expected |
|---|---|---|
| F1 | unauthorized `vendor-note` states a true credit value | REJECT_SET, field unchanged |
| F2 | instruction-free statement from `carrier-portal` about `ship_to` | REJECT_SET |
| F3 | `inventory-tool` sets `stock_count` and tries `credit_amount` | APPLIED / REJECT_SET |
| F4 | authorized `billing-ledger` reports a wrong credit | APPLIED, truth unverified, correctness check fails |
| F5a–e | unknown source, missing map, value conflict, conflicting or ambiguous declaration | HOLD |

Every fixture reports send/payment/merge as HOLD with zero tokens.

## How to run

```bash
cd experiments/2026-11-08/w17-source-authority/
python3 -m unittest test_authority.py -v
python3 fixtures.py
```

Offline, stdlib only. Excerpt checks run only if `/tmp/w17-2611.07640.html`
is present and are skipped otherwise.

## Repo pin (cite-only)

The authors' repository is cited for reference only:
https://github.com/amazon-science/task-tampering-prompt-injection @
`804b00dd03051c00e5e3000982bbf7ce2b9d9ad5`.
It was not cloned and nothing from it was copied (no repo code or data copied). Its dependency inspect-ai
was not installed, imported, or run.

## Not implemented

- No agent, no model calls, no tool runtime; claims are hand-built tuples.
- No learned or inferred authority: the map is declared by hand. Inferring it
  from a user request is out of scope.
- No attack metrics and no reproduction of the paper's tables. The paper's
  headline percentages are not results of this sketch.
- No send, payment, or merge path of any kind.

## UNVERIFIED

- All of the paper's empirical findings, including every attack metric it
  reports by model, defense, or target.
- Whether a real tool-using agent would honor field-level authority.
- Production safety of the send/payment/merge holds.
- Whether a hand-written authority map can be complete for real tasks.

## Builder reflection

The part I had to keep pushing back toward was that the claim text must never
be read: as soon as the resolver looks at wording, it becomes a generic
untrusted-content filter and the paper's point disappears. The F4 fixture
keeps me honest that applying an authorized value is a copy, not a verdict.
Holds on unknown or ambiguous authority are cheap here because nothing
downstream can act on an APPLIED field.

Ludex: when Cody reads a vendor note in Naru's seed shed, the note may update
nothing that the ledger owns — Cody writes REJECT_SET in the log and asks the
ledger, even if the note sounds right.

Implementation may be complete; it is not declared verified.
