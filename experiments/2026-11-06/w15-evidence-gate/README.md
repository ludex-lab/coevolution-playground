# Wave15 — Evidence-Gated Authority (Layer B day-sketch)

**Layer B only:** reviewer disposition `d(r) ∈ {retain, replace, escalate}` plus a **mechanical certificate schema** checked by gate **G** against fixture task data. This folder does **not** port Layer A recombination (`broad_override` / `violation_only_override` / `mechanical_enforcement` from upstream `experiments/reviewer_authority_gate.py` — that file does not define retain/replace/escalate).

This is a **same-day playground sketch**, **not** Team OS law. A gate-approved review record is **not** merge authority for this repository.

| Artifact | Role |
|----------|------|
| [`gate.py`](./gate.py) | Disposition + certificate parse/validate + `apply_evidence_gate` |
| [`test_evidence_gate.py`](./test_evidence_gate.py) | Stdlib `unittest` on synthetic fixtures (no network) |
| [`NOTICE`](./NOTICE) | MIT © 2025–2026 Fuad Ali + Layer B source attribution |

Paper: [arXiv:2611.05390](https://arxiv.org/abs/2611.05390) ([HTML](https://arxiv.org/html/2611.05390)) — *Institutional Representation ABM* (Fuad Ali).

---

## Upstream pin (do not follow moved `main`)

| Field | Value |
|-------|--------|
| Repository | https://github.com/tofuadmiral/institutional-representation-abm |
| **Tag** | **`v2.0.0`** → commit **`f232d43784484f400bb6634147f389bf50a4f3f4`** |
| Annotated tag object | `c18e65638c3b27bf6bb4556b5219cfbdfb0e924f` (`refs/tags/v2.0.0^{}` peels to pin) |
| **`main` HEAD (unpinned, 2026-11-06)** | `8f1e087e3e78391de532af5468dc91d34af7e339` — **not** used here |
| License | **MIT** © 2025–2026 Fuad Ali (full text in [`NOTICE`](./NOTICE)) |

**Layer B idea sources at pin (read for ideas; clean-room rewrite):**

- `experiments/action_aware_reviewer_validation.py` — RETAIN / REPLACE / ESCALATE disposition and evidence-gate outcome wiring.
- `experiments/prospective_certificate_gate.py` — mechanical certificate field validation against task losses.

**Not cited for disposition:** `experiments/reviewer_authority_gate.py` (Layer A only).

---

## Certificate rule (paper mechanics)

A reviewer recommendation binds only after a **mechanically valid** audit record that (1) the proposal **violates a protected duty** (Duty 1: protected loss above threshold) and (2) the **repair is compliant** (recommended protected loss ≤ threshold). **Assertion alone is not authority** — gate G checks the record against fixture task data.

**Apply rule (`apply_evidence_gate`):**

- **`retain`** and **`escalate`:** leave **a0** (current action in force).
- **`replace`:** bind the recommended policy **only if** `valid_repair_certificate` is true; otherwise leave **a0**.
- **Correct proposals** (`oracle_correct` — no Duty 1 violation): never flipped, because `valid_repair_certificate` requires an actual violation.

Synthetic fixture labels match upstream experiment vocabulary (not abbreviated C/V/U):

| Label | Meaning |
|-------|---------|
| `oracle_correct` | Proposal already satisfies protected duty |
| `aggregate_pressure_violation` | Proposal violates Duty 1 (protected threshold) |
| `compliant_suboptimal` | Compliant but welfare-suboptimal (welfare-only repair) |

---

## Paper caveats (do not over-claim)

The retain/replace/escalate **interface** eliminates correct-proposal corruption for **Qwen**, but **Mistral still replaced all 48 correct proposals**; **Qwen also declined every welfare-only repair**. Interface design changes reviewer behavior but is **not** a model-independent safeguard.

The paper’s **§6.3 hybrid sketch** (narrow unilateral authority for verifiable violations while routing welfare-only changes to another vote, human, or higher-cost process) is **untested** (“We do not test that extension here.”).

**Do not conflate** paper **`escalate`** (reviewer cannot verify the comparison) with Team OS **silence-doctrine ESCALATE** (human timeout). **Human silence still ≠ approval.**

---

## Run tests

```bash
cd experiments/2026-11-06/w15-evidence-gate
python3 -m unittest test_evidence_gate.py -v
```

---

## FORBID (honored)

mesa ABM · Streamlit · local LLM/MLX · importing upstream runners · new bot identities · shipping as Team OS law · merging without review · Slack · gate-approved review as merge authority · DSH · Feishu · SQLite · daemons · headcount bots · network at test/runtime.
