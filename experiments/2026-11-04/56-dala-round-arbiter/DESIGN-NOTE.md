# DALA auction core + BudgetTracker — near-verbatim vendored copy (Top KEEP-with-caveats)

**날짜**: 2026-11-04  
**Wave**: Usage Sprint wave12 Top **#3**  
**Verdict**: **Top KEEP-with-caveats** — DALA **auction mechanisms + token budget** vendored @ pin; playground does **not** ship MAPPO/REINFORCE training, full Lightning training harness, HF backends, or paper **VCG / knapsack WDP** ports.

## Upstream pin (honest — weak provenance)

| Field | Value |
|-------|--------|
| Upstream | [waltstephen/Cost-Effective-Communication](https://github.com/waltstephen/Cost-Effective-Communication) (DALA reference tree) |
| Pin SHA | `d6f5939ab1409444348e62aceefa8dfedbeb9508` |
| Pin check (this fold) | Clone @ default branch **HEAD equals pin** on GitHub; sprint card SHA **not** re-attested via independent signed tag — treat as **weak provenance** |
| Vendoring | **~97% near-verbatim** copy of `src/dala/auction/mechanism.py` + `budget.py` @ pin into [`dala_auction_pure.py`](./dala_auction_pure.py) (single module; not a git submodule) |
| Tests copied | **~9** tests near-verbatim from upstream `tests/test_auction.py` + `tests/test_budget.py` @ pin in [`test_dala_auction_pure.py`](./test_dala_auction_pure.py) |
| **New in playground only** | `pick_speakers_second_price`, `dynamic_round_budget` (+ 4 local tests: second-price top-k clearing, budget rewrap, round-budget helper, harness honesty) |
| License (repo file) | Upstream root `LICENSE` is **truncated MIT** (stops mid disclaimer) → SPDX **`NOASSERTION`** for the **repo badge** until upstream fixes the file |
| License (this copy) | **MIT notice** in substantial-file headers (© 2025 Yijia Fan + permission text per upstream file fragment @ pin) |
| Paper | [arXiv:2511.13193](https://arxiv.org/abs/2511.13193) — cite for motivation; **code ≠ paper** (no combinatorial VCG/knapsack port in this folder) |
| ≠ RESMP-DEV / arbiter | No SQLite; no RESMP conflation |

Authoring tip commit on playground default branch: `a3d544105a19e325dbbb2b5d7e2c5edfcb156098` — this experiment branches from that tip without rewriting history.

## Real mechanism (Checker framing)

- **Vendored core:** `FirstPriceAuction` / `SecondPriceAuction` / `SoftmaxAuction` + `BudgetTracker` — **near-verbatim @ pin**, not rewritten from scratch.
- **Playground-only helpers:** `pick_speakers_second_price` = **second-price `top_k`** then **budget rewrap** (charge winner `completion_tokens` in rank order until `round_cap` / global budget; **skip-and-continue** on drop) — **not** paper combinatorial WDP or VCG payments. After rewrap drops, **`clearing_price` is not recomputed** (still the pre-rewrap second-price clearing value).
- **`dynamic_round_budget`:** paper-style even-split **idea** only; no knapsack solver.
- **NOT** an upstream symbol port: there is **no** `round_arbiter` in the pinned DALA tree; folder name is sprint label only.
- **E2E honesty (upstream `tests/test_end_to_end.py`, 3 tests):**
  - **2/3** — `test_auctioneer_runs_end_to_end_and_respects_budget`, `test_auctioneer_stops_when_budget_runs_out`: **`Auctioneer` + `MockBackend` only** (no PyTorch Lightning import in those tests).
  - **1/3** — `test_run_example_via_lightning_module`: imports **`DALALightningModule`** (Lightning-stack path).
  - Playground **does not vendor** `dala.agents.*` or `dala.models.*` — none of the three upstream E2E tests run here; local `test_upstream_e2e_harness_not_vendored` asserts missing imports (**fail closed**, not `pytest.skip`).

### ALLOW (this experiment)

- Near-verbatim vendored copy + MIT headers + DESIGN honesty (weak pin, repo **NOASSERTION**).
- `pick_speakers_second_price` / `dynamic_round_budget` on top of vendored core.
- Unittest-green under `experiments/2026-11-04/56-dala-round-arbiter/` only.

### FORBID (hard)

- MAPPO / REINFORCE / Lightning **training** or HF eval harness in this folder
- Paper **VCG** / **0/1 knapsack WDP** port or payment rule claims
- SQLite, RESMP-DEV arbiter, daemon, DSH, Feishu
- Forbidden stack + headcount Soft→Top conflation
- **Do not touch** open **PR #10** — paths under **`experiments/2026-11-03/`**.
- **Do not touch** merged **PR #11** — [`01-agentbaton-failure-escalate-handoff.md`](../01-agentbaton-failure-escalate-handoff.md) on `main`.

## Vendored module + helpers

Module: [`dala_auction_pure.py`](./dala_auction_pure.py)

```text
# @ pin — mechanism.py + budget.py (near-verbatim)
FirstPriceAuction / SecondPriceAuction / SoftmaxAuction.run(bids, top_k=…)
BudgetTracker.charge / try_charge / snapshot / reset

# playground-only
pick_speakers_second_price(bids, budget, round_cap=…, top_k=…)
dynamic_round_budget(episode_budget, rounds_remaining, spent_so_far, hard_cap=…)
```

| Component | Source |
|-----------|--------|
| **Auctions + BudgetTracker** | Near-verbatim vendored @ `d6f5939` |
| **pick_speakers_second_price** | **New** — rewrap trim; clearing_price unchanged after drops |
| **dynamic_round_budget** | **New** — even split helper |

Tests: [`test_dala_auction_pure.py`](./test_dala_auction_pure.py) — **13** total (**~9** copied from upstream auction+budget units + **4** playground):

```bash
cd experiments/2026-11-04/56-dala-round-arbiter
python3 -m unittest test_dala_auction_pure.py
```

## Sibling links (folder names — not PR numbers)

| Experiment | Link |
|------------|------|
| AgentBaton failure escalate (markdown) | [01-agentbaton-failure-escalate-handoff.md](../01-agentbaton-failure-escalate-handoff.md) |
| Four Bridges deception checklist | [02-four-bridges-deception-observation-checklist.md](../02-four-bridges-deception-observation-checklist.md) |
| PCP shared-human ask queue | [07-pcp-shared-human-ask-queue-checklist.md](../07-pcp-shared-human-ask-queue-checklist.md) |
| Nunchi look_again | [54-nunchi-look-again](../54-nunchi-look-again/) *(parallel wave12 branch)* |
| PAIRL extractive `#rpt` | [55-pairl-extractive-rpt](../55-pairl-extractive-rpt/) *(parallel wave12 branch)* |
| **This folder** | [56-dala-round-arbiter](./) |

## Checker-ready honesty (KEEP-with-caveats)

**KEEP**

- Pin SHA + **weak provenance**; repo truncated MIT → **NOASSERTION**; copy carries **MIT header notice**.
- **Near-verbatim vendored** core @ pin; **new** helpers named explicitly.
- Paper [2511.13193](https://arxiv.org/abs/2511.13193) cited; **no** VCG/knapsack port claim.
- **13/13** unittest OK locally; upstream E2E split **2/3 MockBackend vs 1/3 Lightning module** documented.

**Caveats / UNVERIFIED**

- Upstream **33** tests @ pin not executed in playground CI for this PR.
- Vendored slice may **drift** from pin without continuous diff job.
- `pick_speakers_second_price` rewrap is **greedy**, not paper WDP/VCG.
- Loser prompt-token bid costs and compression / silence policies — **out of scope**.

## Status

- [x] Design note (this file)  
- [x] Vendored core + helpers + **13** unittests  
- [x] PR #67 fold F1 (vendored labeling + MIT headers) + F2 (E2E honesty)  
- [ ] Complete (no full DALA tree; **do not merge** this PR by agent)

**Model (completion summary)**: composer-2.5
