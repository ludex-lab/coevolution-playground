# w14-yukh — envelope lifecycle checklist (Soft #3)

**Wave14 Soft KEEP** — checklist + reading pointers only. **No runnable port.** Soft→Top forbidden.

| Item | Value |
|------|--------|
| Upstream | [nomed/yukh-coordination](https://github.com/nomed/yukh-coordination) |
| **Pin SHA** | **`85eb6a005529e2da6fc7151d7409336c18308986`** |
| License | **Apache-2.0** ([LICENSE](https://github.com/nomed/yukh-coordination/blob/85eb6a005529e2da6fc7151d7409336c18308986/LICENSE)) |
| Playground base at authoring | `8cf0d98931d6367375313e5a2c5f7adf3f09cfd6` (`origin/main` at branch creation) |
| Docs | [DESIGN-NOTE.md](./DESIGN-NOTE.md) · [CHECKLIST.md](./CHECKLIST.md) |

## Pin verification (`git ls-remote`, 2026-11-05)

```text
$ git ls-remote https://github.com/nomed/yukh-coordination HEAD refs/heads/main
85eb6a005529e2da6fc7151d7409336c18308986	HEAD
85eb6a005529e2da6fc7151d7409336c18308986	refs/heads/main

$ git ls-remote https://github.com/nomed/yukh-coordination 85eb6a005529e2da6fc7151d7409336c18308986
(no ref line — object reachable via HEAD/main at same tip)
```

Both `HEAD` and `refs/heads/main` resolve to the pinned commit. License confirmed Apache-2.0 in upstream `LICENSE` at pin.

## One-line goal

Borrow **Team OS checklist text** for the **13** envelope verb/types, **verdict-before-handoff** ordering, and **immutable evidence refs**, plus **RFC-0016 / RFC-0021 reading pointers** — without porting relay, Go runtime, SQLite, or NATS.

## Author claim

| Field | Value |
|-------|--------|
| Tier | **Soft KEEP** (method-only checklist + citations) |
| Runnable upstream | **None required** — no `go test`, no relay daemon, no npm replay in this folder |
| Checker | Verdict section intentionally **omitted** — Checker fills KEEP/UNVERIFIED |

## Quick links

- Morning brief row: [`../README.md`](../README.md)
- Sibling Soft (same day): [`../01-coworkos-revision-checked-leases/`](../01-coworkos-revision-checked-leases/)
