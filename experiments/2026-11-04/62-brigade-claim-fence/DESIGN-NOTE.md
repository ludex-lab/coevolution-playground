# Brigade claim fencing — per-target generation + retired-holder refuse (Top KEEP-with-caveats)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint wave13 Top **#3**  
**Verdict**: **Top KEEP-with-caveats** — upstream **claim generation fence** and **retired-holder horizon** refusal paths sketched as a clean-room pure gate; playground does **not** ship fleet **hub**, **SQLite**, **daemon**, **dashboard**, or **OpenSwarm claim-vs-verified** (Origin **PR #61** — not this folder).

**Naming:** experiment folder **`62-brigade-claim-fence`** is wave13 Top **#3** numbering only — **not** the unrelated Origin Soft **PR #62** (fael sketch on a sibling branch).

## Upstream pin (honest — clean-room)

| Field | Value |
|-------|--------|
| Upstream | [escoffier-labs/brigade](https://github.com/escoffier-labs/brigade) |
| Pin SHA | `dbd6999f8e23ae47b3207e9a19e8608d65d3144f` (short `dbd6999f8e23`) |
| License | **MIT** ([LICENSE](https://github.com/escoffier-labs/brigade/blob/dbd6999f8e23ae47b3207e9a19e8608d65d3144f/LICENSE) @ pin) |
| Mechanism source @ pin | `src/brigade/fleet_hub_claims.py` — `claim_fences` generation, `claim_retired_holders`, `_stale`, `_retired` |
| Test evidence (upstream, cited) | `tests/test_fleet_claim_generations.py` + `registry/skills/verify-brigade/hub-contract-golden.json` **`stale-holder` / `stale-generation`** refusals — **UNVERIFIED** in this agent run (hub stack **FORBID** here; not re-executed on pin) |
| Vendoring | **NONE** — upstream fencing lives in fleet hub + SQLite; we **do not** import or vendor that stack |

Authoring tip commit on playground default branch: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` — this experiment branches from that tip without rewriting history.

## Real mechanism (Checker framing)

- **Per-target generation fence:** each claim **target** carries a monotonic **`generation`** in `claim_fences` (@ pin). Callers that send an explicit **`generation`** must match the current fence (with a narrow **acquire retry** exception when the same live holder retries with `generation == current - 1`).
- **Retired-holder set:** when a holder loses a claim, a row in **`claim_retired_holders`** `(target, owner_node, holder_token, generation, retired_at)` bars that identity from regaining authority without a generation for **`RETIRED_HOLDER_HORIZON_SECONDS`** (7 days @ pin).
- **Refuse paths (`_stale` @ pin):**
  - **`stale-generation`** — `expected_generation` present and ≠ current (and not a valid acquire retry).
  - **`stale-holder`** — no `generation` on the request while a retired-holder row is still inside the horizon (generation-less callers cannot bypass retirement).

Playground models a live claim as **`(target, holder, generation)`** plus an in-memory **`retired`** set; no `claims` table, TTL prune, supersede, or hub HTTP. **`refuse_stale_fence` does not advance generation or retire holders** — callers own fence bump / retirement (upstream `_advance` / `_RetirementBudget.retire` @ pin).

### ≠ conceptual siblings (different mechanisms)

| Sketch | Mechanism | Relation |
|--------|-----------|----------|
| [48-append-only-claim-board](../48-append-only-claim-board/) — Origin **PR #59** | [victorkwak/baton](https://github.com/victorkwak/baton) **Apache-2.0** append-only claim board: **addressee-only**, **first-claim-wins**, **>4h age-stale** rows — **no** per-target **generation** fence and **no** **retired-holder** refuse | **Not** brigade fleet fencing; **not** AgentBaton / **PR #10** park |
| [50-claim-vs-verified-ledger](../50-claim-vs-verified-ledger/) — Origin **PR #61** | OpenSwarm **claim vs verified** ledger (surlymochan/swrm) | **Not** generation fencing — **claim-vs-verify ≠ brigade stale-generation / stale-holder refuse** |
| [61-coop-ack-floor](../61-coop-ack-floor/) — Origin **PR #72** | Coop **ack + floor + budget pause** | **Not** generation fence; no shared gate code |
| This folder — Origin **PR #73** | **Generation + retired-holder refuse** before acquire/renew | brigade `fleet_hub_claims` slice only |

## Pure-fn sketch (playground)

Module: [`brigade_claim_fence_pure.py`](./brigade_claim_fence_pure.py) (~45 LOC)

```text
Claim(target, holder, generation)
RetiredHolder(target, node, holder, generation, retired_at)

refuse_stale_fence(...) -> FenceRefusal
```

| `reason` (sketch) | When |
|-------------------|------|
| **`stale-generation`** | Caller `expected_generation` ≠ current fence generation (no valid acquire retry) |
| **`stale-holder`** | Caller omits generation while retired-holder row is still within horizon |

Tests: [`test_brigade_claim_fence_pure.py`](./test_brigade_claim_fence_pure.py):

```bash
cd experiments/2026-11-04/62-brigade-claim-fence
python3 -m unittest test_brigade_claim_fence_pure.py
```

**Playground test status:** **VERIFIED** — unittest green in this PR branch (run locally as above).

### ALLOW (this experiment)

- Document pin, MIT, mechanism, ALLOW/FORBID, clean-room honesty (no hub/SQLite/daemon/dashboard).
- Pure **stale-generation / stale-holder** refuse gate aligned with `_stale` ordering.
- Unittest green under `experiments/2026-11-04/62-brigade-claim-fence/` only.

### FORBID (hard)

- Fleet **hub**, **SQLite**, **daemon**, **dashboard**, DSH, Feishu
- **OpenSwarm claim-vs-verified** product slice — Origin **PR #61**, folder [`50-claim-vs-verified-ledger`](../50-claim-vs-verified-ledger/) (surlymochan/swrm); **not** coop-ack (**PR #72** / `61-coop-ack-floor`). One-line boundary: **brigade generation fencing ≠ claim-vs-verify**.
- Vendoring `fleet_hub*.py` or hub schema migrations
- **Do not touch** open **PR #10** — paths under **`experiments/2026-11-03/`** (Copilot trajectories / AgentBaton park).
- **Do not touch** merged **PR #11** — [`01-agentbaton-failure-escalate-handoff.md`](../01-agentbaton-failure-escalate-handoff.md) on `main`.

## Sibling links (folder names — not PR numbers)

| Experiment | Link |
|------------|------|
| AgentBaton failure escalate (markdown) | [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) |
| PCP shared-human ask queue | [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) |
| Baton append-only claim board (**PR #59**) | [48-append-only-claim-board](../48-append-only-claim-board/) *(parallel branch when merged)* |
| OpenSwarm claim-vs-verified (**PR #61**) | [50-claim-vs-verified-ledger](../50-claim-vs-verified-ledger/) *(parallel branch when merged)* |
| Handoff Debt seven-field (wave13 Top #1) | [60-handoff-debt-notes](../60-handoff-debt-notes/) *(parallel branch when merged)* |
| Coop ack-floor (wave13 Top #2, **PR #72**) | [61-coop-ack-floor](../61-coop-ack-floor/) *(parallel branch when merged)* |
| **This folder (PR #73)** | [62-brigade-claim-fence](./) |

## Checker-ready honesty (KEEP-with-caveats)

**KEEP**

- Pin SHA + MIT + real upstream symbols (`stale-generation`, `stale-holder`, 7-day retirement horizon).
- Clean-room: no forbidden stack; refuse logic mirrors `_stale` before acquire/renew side effects.
- Playground unittest **VERIFIED** on branch.

**Caveats / UNVERIFIED**

- No hub HTTP, `handle_claim`, TTL prune, supersede, capacity limits, or schema migration — refuse slice only; **no gen-advance / retire in sketch**.
- Upstream hub contract / fleet generation tests **not** re-run in playground (hub **FORBID**).
- `retired` is an in-memory frozenset, not `claim_retired_holders` eviction or per-node quotas.

## Status

- [x] Design note (this file)  
- [x] Pure-fn sketch + unittest  
- [ ] Complete (no brigade submodule; **do not merge** this PR by agent)

**Model (completion summary)**: composer-2.5
