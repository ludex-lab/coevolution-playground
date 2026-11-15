# Call-level revision contracts — method sketch

Playground path: `experiments/2026-11-08/w17-revision-contract/`

This is a clean-room, stdlib-only **method sketch** of the call-level revision
contract described in [arXiv 2611.06967](https://arxiv.org/abs/2611.06967)
("Call-Level Revision Contracts for LLM-Authored Workflows"). It is not a
reproduction of the paper's media-workflow results. It is not Team OS law and
not village law. All workflows are synthetic toy Python snippets and the
"provider" is a deterministic in-process stub.

There is no code pin: the paper mentions the authors' repository, but no public
URL was found, so nothing upstream was read or copied.

## What the sketch does

- **Identity** of a call is the triple *(callsite path, fanout index, occurrence count)*.
  The callsite path is the enclosing function, the block kind/ordinal path, and the
  ordinal of the `ctx.run(...)` call in the innermost block. It does not depend on
  line numbers, comments, or non-capability statements.
- **Committed ledger** is a JSON fixture (`committed_ledgers.json`), loaded strictly.
- **`gate(old_src, new_src, committed)`** is a static pre-spend gate. It rejects a
  candidate that removes, changes (capability or call-expression AST), or moves a
  committed call expression. Relocation is reported as `relocated_not_reused`: a
  stop, never a reuse. An unavailable, corrupt, conflicting, or mismatched ledger
  gives `hold` (fail closed).
- **Runtime payload digest**: at each committed identity the candidate actually
  invokes, the sha256 of the canonical payload must match the record (replay);
  otherwise the run stops with divergence before any new dispatch.
- **Orphan report**: committed identities that an accepted candidate never invokes
  are listed explicitly. Policy `warn` (default) completes with orphans;
  policy `stop` fails the run.
- **Occurrence check** (reduced): a miss at a (callsite, path) whose payload was
  already committed there is named as a repeat; `auto` stops it for side-effecting
  capabilities.

## Scope of the claims

- The static gate freezes the call expression, not upstream data dependencies.
  A literal argument edit is stopped statically; a changed variable feeding an
  unchanged call expression passes the gate and is stopped by the runtime digest.
- Gate acceptance does not mean every committed identity is replayed. Replay or
  divergence is claimed only for committed identities that are actually invoked;
  the rest are orphans. Nothing here claims semantic completeness of a repair.
- In these fixtures there is no repeated dispatch at a retained identity. That is
  a fixture observation, not a universal exactly-once claim.
- Dispatches saved are counted against a naive rerun of the repaired script from
  an empty ledger, using SYNTHETIC toy counts only.

## Fixtures (`fixtures.py`)

1. `unchanged_expression_changed_variable` — gate accepts, runtime digest stops.
2. `relocation` — gate stops (`relocated_not_reused`).
3. `orphan_warn` / `orphan_stop` — loop shrinks; explicit orphan report under both policies.
4. `fanout_path_shift` (divergence stop) and `fanout_append` (new work only).
5. `unavailable_ledger_*` — missing, corrupt, conflicting duplicate, mismatched fingerprint: all hold.

Extras: `happy_retained_replay`, `literal_argument_edit`, `occurrence_extension_*`.

## How to run

```bash
cd experiments/2026-11-08/w17-revision-contract/
python3 -m unittest test_contract.py -v
python3 fixtures.py
```

The paper-excerpt tests check `paper_evidence.json` against a saved copy of the
paper HTML at `$W17_PAPER_HTML` or `/tmp/w17-2611.06967.html`; they skip when
neither exists. Everything else is offline.

## Not implemented

- SQLite WAL run store
- Docker / networkless sandbox
- Host service and bounded file RPC
- Capability broker grants and per-run nonce
- Paid or live providers
- HMAC (the payload digest is plain sha256)
- Hash-chain certificate over the prefix
- The paper's full checker rule set (only a small subset check here)
- Attempt records and crash-window policies
- Repair loop / model rewriter, and all of the paper's evaluation studies

## UNVERIFIED

- All of the paper's empirical findings; none are targets here.
- Whether this toy callsite labelling matches the paper's `assign_sites` in detail.
- Behavior under concurrent fanout (the toy fanout is sequential).
- Whether `exec` of synthetic toy sources with trimmed builtins is a safe sandbox
  (it is not intended to be one; only trusted toy fixtures run).
- Production security of any of these checks.

## Builder reflection

The useful split is static versus runtime: the gate can only see the call
expression, so the changed-variable fixture is the one that proves the digest is
not optional. Orphans were the easy thing to forget, because an accepted gate
feels like "everything replays", and the shrink-loop fixture shows it does not.
Reporting stopped-run identities as "unreached" rather than "orphans" avoided a
misleading count.

Ludex: before Cody or Naru re-run a repaired multi-call script, gate it against
the committed ledger, then read the orphan report, not just the gate verdict.

Implementation may be complete; it is not declared verified.
