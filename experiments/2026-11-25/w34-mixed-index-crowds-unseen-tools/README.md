# w34-mixed-index-crowds-unseen-tools

Shared tool experience (past requests from several clients, each labelled with the tool that served it) is put into
the same retrieval index as tool descriptions. Under an equal budget of k distinct tools, can it crowd a tool that no
client has used out of the router's candidate list, while a separate description index still offers it?

This is a method sketch with planted synthetic data. The demo shows the mechanism only. It is not evidence of how
often this happens and does not reproduce any paper number.

## Source and licence

- Chakraborty, Gupta and Trieu, "STUN-Bench: Truly Unseen Tools for Evaluating Shared Tool Experience",
  [arXiv 2611.30034](https://arxiv.org/abs/2611.30034), submitted 23 Nov 2026. Paper licence CC BY 4.0. The
  citation_title above was read from the abs page meta tags.
- Upstream repo github.com/Abhijit85/STUN-Bench at 816dc772 is Apache-2.0. It was not cloned, installed or run. No
  upstream code, data or text is copied here; the catalog, clients and requests are made up.
- Short attributed quotes, disclosed as quotes:
  - Abstract: "On the split we find crowding: experience pooled from five simulated clients, added to an index of
    tool descriptions, outranks the descriptions of tools no client has used, which then often drop out of the
    candidate list."
  - Upstream DATASHEET, full sentence as reported by the review (not re-opened for this draft): "The held-out tool
    set H contains 172 tool IDs, formed from the gold tools of the G1-tool and G1-category query groups."

## Method

- Tokens are the lowercase `[a-z0-9]+` runs. Score is the count of distinct tokens shared by the request and an
  index item. One scorer only, no Jaccard, so a long description is not penalised for its length.
- Total order over both item kinds: `(-score, kind, id)`, with description (0) before experience (1).
- Arm A (mixed index): walk the ranked list of descriptions and experience items. An experience item contributes
  its `gold_tool_id`. Skip ids already taken until there are k distinct tools.
- Arm B (separate index): the top k descriptions. Experience never takes a slot.
- Both arms must return exactly k distinct tools, else FAIL `unequal_budget`.
- Every pool declares `split: heldout | leaky`. A heldout pool may not label a held-out tool (as `gold_tool_id`) or
  name it. Naming means the tool id, or a token of its declared `name`, appearing as a token of the experience text.
  Either one is DENY `heldout_leak`. A missing or unknown split is DENY `bad_split`.

## Mandatory controls and criteria

| role | expected (pinned) |
|---|---|
| crowding (heldout pool) | arm A omits the held-out gold; arm B includes it |
| n1_empty (empty pool) | arm A list equals arm B list |
| n2_nonoverlap (pool with zero token overlap with the request) | arm A includes the held-out gold |
| n3_labeled (gold tool already used in the pool) | arm A includes the gold |
| leaky (leaky pool) | arm A includes the gold |

- (a) is PASS only when every crowding row holds and n1, n2 and n3 all hold.
- (b) is the leaky row. Held-out and leaky rows are printed in separate tables. No combined number is reported.
- Client sweep: clients c1..c5 are added one at a time to the crowding request's pool at fixed k = 3.
  - Pre-registered rule: the gold drops once at least k distinct used tools outrank its description.
  - The fixture states `flip_at: 4` before the run. Client c2 repeats the weather tool, so only c4 brings the third
    distinct tool.
  - The sweep holds only if the observed flip, the rule's flip and `flip_at` are all equal.
  - The rule counts only tools reached through experience (used tools). It assumes no other tool's description outranks the gold; if one does, the observed flip comes earlier and the sweep fails, so the gate is FAIL.
  - The observed flip is the first step at which the gold drops out of arm A. A later re-entry is not checked by the sweep; for the main fixture the tests pin the full step list.
- The gate is PASS (exit 0) only if the budget is equal, (a) and (b) hold, and the sweep holds. Otherwise it is FAIL
  (exit 1).

## Fail-closed

- `on_expiry` must be the literal `DENY`.
- Bad input is DENY: exit 2, empty stdout, one stderr line `DENY <code>: <detail>`. Codes:
  not_json, duplicate_key, unknown_field, missing_field, bad_type, bad_k, unknown_tool, unknown_pool, duplicate_id,
  bad_split, heldout_leak, bad_on_expiry, bad_role, bad_control, missing_role, bad_sweep, bad_version, unreadable,
  too_large, usage (wrong arguments).
- There is no pass-through path. A mutant timeout also declares on_expiry DENY and is not counted as a kill.

## Files and how to run

- `crowding.py`: module and CLI (`python3 -B crowding.py [--json] fixtures/main.json`).
- `test_crowding.py`: unit tests (`python3 -B -m unittest test_crowding`).
  - The forbidden-word test reads this folder's `.py` files as text. VERDICT C8 requires it, and it is the only test
    that reads source files.
- `demo.py`: prints the report for the planted fixture.
- `mutants.py`: five in-memory mutants, three of them required by C4. Crashes and timeouts are counted apart from
  kills.
- `evidence.json`: the measured rows and the `on_unmeasured` list.
- `fixtures/main.json` and `fixtures/bad/*.json` (21 bad fixtures, including a non-string `gold_tool_id`).
- `SHA256SUMS`: sha256 of every other file in this folder, relative paths, sorted. Check with `sha256sum -c SHA256SUMS` run inside the folder.
- Stdlib only, `python3 -B`, no network, no embeddings, no model calls.

## on_unmeasured (UNVERIFIED)

- 0.534 to 0.278 held-out routing accuracy under Jina-v2, as reported by the paper: UNVERIFIED.
- Jina-v2 retriever behaviour: UNVERIFIED (no embeddings here).
- "Five simulated clients": UNVERIFIED (the five clients here are scripted and synthetic).
- 90704 pool items after filters: UNVERIFIED.
- The 172 held-out ids and 729 queries of the release: UNVERIFIED here, not imported.

## Limits

- The fixture is planted so crowding happens. It shows that the mechanism exists under this scorer, not how often it
  happens.
- A token-overlap router is not a dense retriever. With other scorers the flip point can move.
- The sketch does not measure routing accuracy, argument filling or task completion.

## Distinct from

- #158 `mb-occupancy-cap-per-bucket`: a per-time-bucket slot cap, so a burst cannot evict memory. That is about
  slot occupancy. This sketch compares mixed and separate retrieval indexes over a declared heldout or leaky
  experience split.
- #162 `mb-error-propagation-trace`: outcome-only vs per-hop error classes on agent chains. That is a different
  question.
- `w27-worker-lead-handoff`: fillers crowd a claim out of a fixed handoff budget. That is crowding by packet
  ordering. It has no experience pool, no index composition and no split.
