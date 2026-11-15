# Wave15 — ZSC coordination-friendly definitions (Soft day-sketch)

**KEEP Soft.** **UNVERIFIED runnable.** This folder is a same-day method-cite checklist for [coordination-friendly definitions (CFDs)](https://arxiv.org/abs/2611.06409) — hand-crafted and meta-learned — as structured records for how independently developed agents can state shared coordination principles. It is **not** Top, **not** a runnable reproduction of the paper, and it does **not** call a model or start Docker.

Paper prose (quote-checked against arXiv 2611.06409; do not invent figures):

> We study zero-shot coordination (ZSC), where independently developed agents must coordinate at test time.

> A CFD comprises a set of textual instructions that encode general coordination principles used to guide agent behaviour.

> We assume that independent developers can agree on a shared CFD to facilitate coordination among their agents.

The paper’s own labels for the two CFD origins are **hand-crafted** and **meta-learned**. This sketch uses those records as a checklist. “Strangers” is not a paper word; the paper says “independently developed agents.”

| Artifact | Role |
|----------|------|
| [`checklist.py`](./checklist.py) | Quote-checked sentences, `CfdRecord`, `apply_checklist` |
| [`fixtures.py`](./fixtures.py) | Synthetic complete, incomplete, and forbidden records |
| [`test_zsc_cfd.py`](./test_zsc_cfd.py) | Stdlib `unittest` (quote text, origins, checklist shape) |
| [`NOTICE`](./NOTICE) | Apache-2.0 — Copyright 2026 The Authors |

Upstream code: [ahayler/zsc-llm-agents](https://github.com/ahayler/zsc-llm-agents). Paper: [arXiv:2611.06409](https://arxiv.org/abs/2611.06409).

---

## Upstream pin

| Field | Value |
|-------|-------|
| Repository | https://github.com/ahayler/zsc-llm-agents |
| **Pin** | **`739c249756b7deedf64f1cb8224caf035a0322ba`** |
| License | **Apache-2.0** — Copyright 2026 The Authors (full text in [`NOTICE`](./NOTICE)) |
| Paper | https://arxiv.org/abs/2611.06409 |

The upstream README at this pin says code agents run only **inside a Docker container as a non-root user** and “refuse to run them otherwise,” and that “All models are accessed through OpenRouter.” This sketch does not clone-run that stack and does not claim any paper numbers were reproduced.

---

## Checklist shape

A complete record names itself, marks origin as `hand-crafted` or `meta-learned`, and supplies CFD instructions. A hand-crafted record must reject actions or policies that assume arbitrary conventions. A meta-learned record must prefer actions that remain reasonable under several plausible partner interpretations. A record that claims to be a runnable reproduction, or that would need Docker or OpenRouter, fails the checklist.

---

## Run tests

```bash
cd experiments/2026-11-06/w15-zsc-cfd
python3 -m unittest test_zsc_cfd.py -v
```

---

## FORBID (honored)

Docker · OpenRouter / `OPENROUTER_API_KEY` / paid API calls · treating this as a runnable reproduction · DSH · Feishu · SQLite · daemons · new bot identities · TypeSafe/Jev · MCP/HTTP controller · network at test/runtime · promoting this sketch from Soft to Top.
