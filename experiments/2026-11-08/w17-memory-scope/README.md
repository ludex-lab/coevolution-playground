# Memory scope write/read holds

An original, stdlib-only **method sketch** of [The Memory Trap](https://arxiv.org/abs/2611.07554).
Location: `experiments/2026-11-08/w17-memory-scope/`.
This is a proposed harness mitigation / adopt-check, **not a proven defense** and not a defense validated by the paper. It is not Team OS law and not village law.

## Boundary model

Each entry is `{text, scope: {task_class, stakes, tools}, source_event}`.
The source event contains an identity and the explicit scope of formation.
`lint_write` checks formation-scope: an entry cannot change the source task class or stakes label, or expand its tools.
`read_scope` checks application-scope: the task must match the source identity, task class, stakes label, and a subset of the entry's tools. It also rechecks formation lint.
`applicable(entry, task)` reports only this metadata match. It never grants authority to act, skip confirmation, change a judgment, or edit a test.
`action_hold` requires independent action review even for in-scope metadata. There is no dispatch path.

Missing or ambiguous fields, wildcards, and malformed values yield hold.
An empty, explicitly frozen tool set means no tools, not unrestricted tools.
Stakes are exact categorical labels represented by integers; neither lower nor higher numeric stakes establish compatible authority.
Source identity must match independently of stakes. This deliberately conservative model does not support cross-event generalization.
The caller supplies trusted source-event records and task metadata; the sketch does not authenticate them or infer scope from natural language.
A misleading text paired with narrow metadata is not detected semantically.

Frozen synthetic fixtures cover **confirmation skip**, **sycophancy bias**, and **test weakening**.
Both write-time widening and read-time out-of-scope application hold for each trap.
The Ludex adopt-check replays a benign skip-confirmation chore memory against a synthetic high-stakes record change: both boundaries hold, and a correct failing safeguard test remains intact.
A proposed repair that changes the expected result, input, enabled flag, or deletes the protected test is blocked; the entire test specification is retained and its assertion still fails against the frozen defective function. An unchanged proposal also reports the blocked frozen defect. The outer harness asserts that this failure remains observable; it does not mark the safeguard as an expected failure or erase it.

This differs from playground #90 tooling-memory (provenance/quarantine) and #84 FlyHash (indexing): this sketch exercises formation-scope vs application-scope and out-of-scope behavior, not retrieval or provenance infrastructure.

## Evidence and limits

Method-cite only; independently authored implementation and synthetic fixtures, with no copied upstream implementation. The paper uses the arXiv perpetual non-exclusive license, not CC BY and not a software grant.
The paper's code footnote points to https://github.com/safety-research/memory-trap; an independent public HEAD request returned HTTP 404. No accessible implementation pin or software licence was established. A public 404 does not establish that no private repository exists.
`paper_evidence.json` stores short quote checks, raw-HTML byte offsets, window hashes, source hashes, and excluded empirical-number needles. Tests recheck the saved HTML offline when available; otherwise the source-file checks are explicitly skipped, not silently treated as found.

### Not implemented

Natural-language scope extraction, trustworthy source capture, authentication, retrieval, memory persistence, production policy integration, action execution, real user workflows, and model evaluation. No network access, database, paid APIs, or external services are used by the sketch.

**UNVERIFIED:** paper empirical results, effectiveness against model-driven overgeneralization, correctness of supplied metadata, semantic compatibility of task labels, adversarial robustness, and production safety. Passing these synthetic checks does not validate a general defense.

## Run

```bash
cd experiments/2026-11-08/w17-memory-scope/
python3 -m unittest test_scope.py -v
python3 fixtures.py
```

## Builder reflection

Separating formation-scope from application-scope makes a benign memory's boundary visible at both points where it can be lost. Exact identity and stakes-label matching are conservative modelling choices, not an account of real-world authority. Preserving the correct failing safeguard is more informative than turning a blocked repair into a passing check.

Ludex for Cody/Naru: replay the chore's skip-confirmation memory against a synthetic high-stakes change; require write-time and read-time holds and retain the correct failing safeguard test.

Implementation may be complete; it is not declared verified.
