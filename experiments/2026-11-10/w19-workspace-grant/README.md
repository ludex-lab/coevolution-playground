# w19-workspace-grant

One grant per workspace, issued before the action, instead of a prompt per
action. A Python 3 standard-library method sketch of the approval-unit shift
described in [arXiv 2611.08516](https://arxiv.org/abs/2611.08516) (Aegis OS).

**Honesty note.** This is a method sketch. It is not Team OS law, not village
law, and not a port of Aegis OS. It does not reproduce or check any result
from the paper. All grants, actions, paths, hosts and claims are synthetic.

## Run

```
python3 fixtures.py
python3 -m unittest test_workspace_grant.py -v
```

No dependencies, no network, no filesystem access beyond reading the files in
this directory. The excerpt test reads the review copies named in
`paper_evidence.json` from `$W19WG_SOURCES` and is skipped when they are
absent.

## Method

A `Grant` holds `grant_id`, a workspace `root`, the path `prefixes` inside the
root that the grant covers, a frozen set of `egress` hosts, `issued_at`,
`ttl` and `on_expiry`. An `Action` holds a time `at`, and a `path`, an `egress`
host, or both.

`decide(grant, action, claimed_by_other=False)` returns `pass_within_grant`
only when every one of these holds:

1. a grant exists, is exactly a `Grant` (not a subclass) with exact `str`,
   `tuple`, `frozenset` and `int` field types, and its configuration is
   valid;
2. it was issued strictly before the action (`issued_at < at`);
3. it has not lapsed (`at < issued_at + ttl`);
4. the path, after string normalisation, is at or below one of the prefixes,
   compared segment by segment, so `/ws/app` covers `/ws/app/x` but not
   `/ws/apple`;
5. the egress host is printable ASCII and, lowercased with one trailing dot
   dropped, is exactly one of the grant's hosts (no subdomains, no
   wildcards, no ports);
6. the external claim input does not mark the action as touching something
   another agent holds.

Otherwise the decision fails closed with reasons:

| Situation | Outcome |
|---|---|
| no grant, unknown grant id | `deny` / `no_grant` |
| grant issued at or after the action | `deny` / `grant_not_issued_before_action` |
| path outside the root or the prefixes; `..` segment | `deny` |
| egress host not in the grant | `deny` / `egress_outside_grant` |
| path at or below a claimed path, or claim flag `True` (external input) | `deny` / `claimed_by_other` |
| path is a parent of a claimed path | `deny` / `path_contains_claimed_path` |
| a subclass of `Grant` or of a field type | `hold` / `config_error` |
| invalid grant configuration, incl. missing or unknown `on_expiry` | `hold` / `config_error` |
| malformed time, path, host, claims or action | `hold` |
| ttl passed | exactly the declared `on_expiry` / `expired` |

Times are plain `int` only: `bool`, `float` (including NaN and infinity) and
strings are refused. Paths containing a backslash, `%`, `~`, `$`, a NUL or
control character, a space-padded segment or a dots-only segment other than
`.` are refused as malformed rather than guessed at. Empty and `.` segments
collapse, so `//` and a trailing slash are harmless. Relative paths resolve
under the root.

Each grant field is read once into a checked local copy, and the decision
uses only that copy. After the ttl the returned outcome is the module's own
constant for the declared value, never the caller's object, so a value that
changes between reads cannot turn into a pass.

Hosts must be printable ASCII. Any other character is refused as
`egress_malformed` before any case mapping, so the Kelvin sign (U+212A) is
not mapped to `k` and `pa\u00dfau.de` is not folded to `passau.de`.
Internationalised names can only be given in their ASCII `xn--` form.

Claims: a claim flag of `True` denies any action, egress-only ones included.
A claim set lists absolute path prefixes held by others; a write at or below
one is `claimed_by_other`, and a write to a parent of one (for example
`/ws/app` when `/ws/app/lib` is held) is `path_contains_claimed_path`,
because it reaches into the held subtree. A claim set does not affect an
egress-only action; a malformed claim set holds.

`prompts_needed(actions, "per_action" | "per_workspace")` shows the shift on
a toy run: one prompt per action versus one grant for the run.

## Silence doctrine

This rule is taken from merged
[#78 w14-silence-expiry](https://cursor.com/codebase/coevolution-lab/playground/pull/78)
(`experiments/2026-11-05/w14-silence-expiry/`), which is the source of the
four `on_expiry` values, of the rule that a missing `on_expiry` is a config
error, and of the stance that nothing passes on timeout (paraphrased). This
sketch reuses that rule unchanged.

After the ttl the outcome resolves only to the grant's declared `on_expiry`,
one of `deny`, `safe_fallback`, `escalate` or `hold`. None of those is a pass.
A missing or unknown `on_expiry` (including `pass_within_grant` itself) is a
`config_error` at any time, before or after expiry, and never passes. The
layer has no renew or extend function: silence, a quiet period or a missing
objection never extends a grant. A boundary crossing needs a new grant,
issued before the action.

## Overlap with earlier experiments

- [#78 w14-silence-expiry](https://cursor.com/codebase/coevolution-lab/playground/pull/78)
  (merged on main) has every approval rule declare `on_expiry` in {`deny`,
  `safe_fallback`, `escalate`, `hold`}; a missing or permissive value is a
  `ConfigError`, and nothing passes on timeout. The silence doctrine here is
  that rule, not a new one. What this sketch adds beyond #78 is the scope of
  the approval: one grant covering a workspace's path prefixes and egress
  hosts, issued before the actions, instead of a per-action rule. Unlike #78,
  `safe_fallback` here names no substitute action; it is only an outcome
  label, and this layer executes nothing.
- [#73 brigade claim fence](https://cursor.com/codebase/coevolution-lab/playground/pull/73)
  fences which agent holds a path. This sketch does not reimplement that. It
  only accepts an external `claimed_by_other` input (a `bool`, or a frozen set
  of claimed path prefixes) and turns a hit into `deny`.
- [#59 append-only claim board](https://cursor.com/codebase/coevolution-lab/playground/pull/59)
  records claims over time. Here there is no board, no history and no state;
  `decide` is a pure function of its inputs.
- [#77 CoworkOS revision-checked leases](https://cursor.com/codebase/coevolution-lab/playground/pull/77)
  tracks lease expiry (`expires_at`, `lease_state`) and revisions for shared
  work, and its `ask_main` record carries `wait_ms` and a
  `fallback_assumption`, a declared fallback when a question goes unanswered.
  That fallback-on-silence is the piece closest to `on_expiry`. Here expiry is
  a fixed `issued_at + ttl` with one declared `on_expiry` per grant, and there
  are no revisions, lease states or questions.
- [#19 delegated-scope checklist](https://cursor.com/codebase/coevolution-lab/playground/pull/19)
  (`experiments/2026-11-04/08-delegated-scope-affordance-violation-checklist.md`)
  lists the paths a delegation covers. Here the path list is one field of a
  time-boxed grant that also covers egress.

The distinct borrow from the paper is the approval-unit shift aimed at
authorization fatigue: the unit of approval moves from the single action to
a workspace grant (path prefixes plus hosts) made before the actions. The
expiry rule is #78's.

## Upstream reference

[heurion-org/aegis-os](https://github.com/heurion-org/aegis-os), Apache-2.0,
pin `14653158e820b0ca46f170e0125c8528b72205c0`. Its README was read as text
from a review copy only. It was never cloned, built, installed, run or ported,
no code was copied, and it has no NOTICE file at that pin. Paper credit
(CC BY 4.0) and the reference are in `NOTICE`.

Not borrowed: the hash-chained audit ledger, the egress proxy, telemetry, the
sandbox and copy-on-write workspace, MCP and A2A servers, claim fencing,
auto-merge, and any daemon or runtime.

## Limitations

- Trust boundary. The layer trusts whatever grant object it is handed, as
  long as it is an exact `Grant` with valid fields. Issuance, authenticity,
  integrity, subject binding and replay are out of scope: there is no
  issuer, no signature and no binding to an agent. Concretely, each of these
  still passes:
  - a self-written grant (no issuer exists to check);
  - a widened copy with the same `grant_id`, made with
    `dataclasses.replace`;
  - an in-place change to a frozen grant via `object.__setattr__`;
  - a registry entry swapped after issue, looked up with `decide_by_id`;
  - extra hosts written openly into the grant's own host set. Hidden extra
    hosts behind a frozenset subclass (iteration that differs from the
    contents) are now refused as `config_error`; what remains is that any
    host the caller puts in a real frozenset is trusted.
  Replaying one grant for many actions inside its window is the design, not
  a defect. Adding signatures, keyed hashes or a ledger is deliberately not
  done here.
- Paths are strings. Symlinks, hard links, bind mounts and case-insensitive
  or Unicode-normalising filesystems are not seen; a real system must resolve
  paths against the filesystem it guards.
- Egress is an exact ASCII host name. There is no DNS, IP, port, scheme or
  redirect handling. Every non-ASCII host is refused before case mapping,
  so look-alikes are refused, not mapped; ASCII look-alikes (for example
  `rn` for `m`) are just different names and are denied if not in the
  grant.
- Times are trusted integers from the caller; there is no clock.
- Claims are external input; their correctness belongs to #73. Claim
  matching is by string segments, so a case variant of a claimed path is
  not seen, and a parent of a claimed path is denied as
  `path_contains_claimed_path`.
- Malformed input holds rather than denies. A hold leaves the refusal visible
  for a person to look at, and it is still a refusal.

## Paper figures

Figures from the paper and the upstream README are recorded only in
`paper_evidence.json` and are marked UNVERIFIED there. Nothing in this
directory measures or reproduces them.

## Builder reflection

The useful idea is small: approval belongs to a boundary decided ahead of
time, and what happens when that boundary lapses must be written down rather
than inferred. Most of the work went into refusing ambiguous paths and hosts
instead of normalising them cleverly, because a clever normaliser is where a
grant quietly widens. Review showed the real edge is the grant object
itself: this layer can refuse odd shapes, but who made a grant has to be
settled somewhere else.

Ludex: one grant, one window, and when it closes the answer is whatever you
wrote down.

Implementation may be complete; it is not declared verified.
