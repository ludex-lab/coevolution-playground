# w14 arc-grammar — report grammar day-sketch (Top)

**Lab Dig Wave14 Top #3** · Team OS playground · **do not merge** without Ork review.

## Upstream pin (grammar source)

| Field | Value |
|-------|--------|
| Repository | https://github.com/joethefisher/agent-arc-status |
| Pin SHA | `7a3206b0c466a619d066a3a05872340e93a5a618` |
| Port-time check | `git ls-remote https://github.com/joethefisher/agent-arc-status 7a3206b0c466a619d066a3a05872340e93a5a618` → resolves to `HEAD` / `refs/heads/main` at this SHA |
| License | MIT — Copyright (c) 2026 **Joe Fisher** (`LICENSE`; covers ported code + vendored fixtures) |

This folder is a **port** of upstream **`validate.ts`** / **`cadence.ts`** (verbatim regex and error strings at the pin) into stdlib Python, plus vendored **conformance JSON**. It is **not** a clean-room reimplementation. Team OS adds: cadence §4.5 fix (no heartbeat after `blocked`), JS/Py parity tightening (`fullmatch`, ASCII digits, UTF-16 title cap, canonical year), and `receipt_liveness.py` helper. Excludes dashboard, LangChain/MCP/OTel adapters, webhooks, MQ, npm/PyPI packaging, daemons, HTTP servers, SQLite/DSH/Feishu, and headcount bots.

## What was ported

| Area | Module | Notes |
|------|--------|--------|
| Phase enum | `arc_grammar/types.py` | `started \| milestone \| heartbeat \| done \| blocked` |
| Single-event validate | `arc_grammar/validate.py` | From `validate.ts` + JS parity (see `tests/test_js_parity.py`) |
| Sequence validate | `arc_grammar/validate.py` | §4.5–§4.6 ordering; `done` ≤1; terminal `blocked` allowed |
| Cadence floor + heartbeat | `arc_grammar/cadence.py` | From `cadence.ts`; **suppress heartbeat while last phase is `blocked`** |
| Receive-time liveness | `arc_grammar/receipt_liveness.py` | Receipt clock only — not stallwatch |
| Conformance fixtures | `conformance/**` | Vendored corpus + `manifest.json` sha256; `examples/streams.json` only |

## What is forbidden here (by design)

- Dashboard / adapters / transport
- Using heartbeat silence as **stall** forensics → **`stallwatch`** territory
- Soft→Top confusion with **OnTrack** (cite-only elsewhere)
- Rebuilding **claim-vs-verified #61** — noted below only

## Pairing note: claim vs verified (#61)

Operational **`done`** should reflect deliverable truth from the **consumer vantage**, as in `experiments/2026-11-04/50-claim-vs-verified-ledger/`. This sketch validates payload shape and phase legality only.

## Run tests

```bash
cd experiments/2026-11-05/w14-arc-grammar
python3 -m unittest discover -s tests -v
python3 run_conformance.py
```

Stdlib only; no install step.

## Layout

```
w14-arc-grammar/
  arc_grammar/
  conformance/
  tests/
  run_conformance.py
  LICENSE
  NOTICE
  README.md
```
