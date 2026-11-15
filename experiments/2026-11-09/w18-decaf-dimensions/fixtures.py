"""Synthetic fixtures for w18-decaf-dimensions (toy data, village-flavoured).

Run: python3 fixtures.py   (exit 0 when every check holds)

The setting is made up: Cody, a village helper agent, has a small config,
and Naru files change proposals against it. Run ids refer to the toy run
log below; none of this comes from the paper.
"""

import copy
import sys

import decaf as D

BASE = {
    "instruction_text": "Answer villagers briefly; cite the notice board.",
    "handoff_graph": {"cody": ["archivist"], "archivist": []},
    "engine_label": {"cody": "engine-small", "archivist": "engine-small"},
    "tool_gate": {"cody": ["read_board"], "archivist": ["read_board", "read_ledger"]},
    "retry_budget": {"max_retries": 2, "timeout_s": 30},
    "memory_window": {"turns": 4},
}

RUN_LOG = [
    {"run_id": "run-0412", "summary": "cody timed out twice on festival questions"},
    {"run_id": "run-0413", "summary": "cody answered harvest dates without board citation"},
    {"run_id": "run-0415", "summary": "archivist lost thread after five turns"},
]


def proposal(pid, declared, changes, evidence):
    after = copy.deepcopy(BASE)
    after.update(changes)
    return {"id": pid, "declared_dimensions": declared,
            "before": copy.deepcopy(BASE), "after": after, "evidence": evidence}


def ev(run, dim, note):
    return {"run_id": run, "dimension": dim, "note": note}


RETRY = {"retry_budget": {"max_retries": 3, "timeout_s": 45}}
MEMORY = {"memory_window": {"turns": 8}}

PROPOSALS = {
    "single_evidenced": proposal(
        "p-single", ["retry_budget"], RETRY,
        [ev("run-0412", "retry_budget", "two timeouts at 30s on festival lookups")]),
    "two_dims_one_evidenced": proposal(
        "p-two-half", ["retry_budget", "memory_window"], dict(RETRY, **MEMORY),
        [ev("run-0412", "retry_budget", "two timeouts at 30s on festival lookups")]),
    "two_dims_both_evidenced": proposal(
        "p-two-full", ["retry_budget", "memory_window"], dict(RETRY, **MEMORY),
        [ev("run-0412", "retry_budget", "two timeouts at 30s on festival lookups"),
         ev("run-0415", "memory_window", "archivist dropped the thread after turn five")]),
    "declared_mismatch": proposal(
        "p-mismatch", ["retry_budget"], MEMORY,
        [ev("run-0415", "memory_window", "archivist dropped the thread after turn five")]),
    "unknown_run": proposal(
        "p-ghost-run", ["retry_budget"], RETRY,
        [ev("run-9999", "retry_budget", "timeouts seen last week")]),
    "empty_evidence": proposal(
        "p-empty", ["retry_budget"], RETRY, []),
    "placeholder_evidence": proposal(
        "p-tbd", ["retry_budget"], RETRY,
        [ev("run-0412", "retry_budget", "TBD")]),
    "undeclared_key": proposal(
        "p-new-key", ["instruction_text"],
        {"instruction_text": "Answer villagers briefly; cite the notice board by date.",
         "mood_setting": "cheerful"},
        [ev("run-0413", "instruction_text", "harvest answers lacked a board citation"),
         ev("run-0413", "mood_setting", "villagers said replies felt flat")]),
}


def checks():
    """Yield (name, ok, detail) for every fixture expectation."""
    R = {k: D.report(p, RUN_LOG) for k, p in PROPOSALS.items()}

    r = R["single_evidenced"]
    yield ("1 single dimension with evidence: no flag (reported, not signed off)",
           r["outcome"] == D.NO_FLAG and r["actual_dimensions"] == ["retry_budget"],
           r["outcome"])

    r = R["two_dims_one_evidenced"]
    codes = [f["code"] for f in r["findings"]]
    yield ("2 two dimensions, evidence for one: fail closed",
           r["outcome"] == D.FAIL_CLOSED and "multi_dimension_uncovered" in codes
           and [f.get("dimension") for f in r["findings"] if f["code"] == "uncovered_dimension"]
           == ["memory_window"], r["outcome"])

    r = R["two_dims_both_evidenced"]
    yield ("3 two dimensions, evidence for both: reported as multi, not flagged",
           r["outcome"] == D.NO_FLAG and r["multi_dimension"]
           and r["actual_dimensions"] == ["memory_window", "retry_budget"], r["outcome"])

    r = R["declared_mismatch"]
    yield ("4 declared retry_budget, diff shows memory_window: flagged",
           r["outcome"] == D.FLAG and r["actual_dimensions"] == ["memory_window"]
           and "declared_mismatch" in [f["code"] for f in r["findings"]], r["outcome"])

    r = R["unknown_run"]
    yield ("5 evidence cites a run not in the log: held",
           r["outcome"] == D.HOLD and D.hold_reasons(r) == ["unknown_run"], r["outcome"])

    r = R["empty_evidence"]
    yield ("6a empty evidence trace: held",
           r["outcome"] == D.HOLD and D.hold_reasons(r) == ["empty_evidence"], r["outcome"])

    r = R["placeholder_evidence"]
    yield ("6b placeholder evidence note: held",
           r["outcome"] == D.HOLD and D.hold_reasons(r) == ["placeholder_evidence"], r["outcome"])

    r = R["undeclared_key"]
    yield ("7 key outside the manifest: reported and flagged",
           r["outcome"] == D.FLAG and r["unknown_dimensions"] == ["mood_setting"], r["outcome"])

    c = D.compare(PROPOSALS["single_evidenced"], PROPOSALS["declared_mismatch"])
    yield ("8 compare single vs mismatch: disjoint touched dimensions",
           c["disjoint"] and c["only_a"] == ["retry_budget"] and c["only_b"] == ["memory_window"],
           str(c))

    narrowed = D.restrict(PROPOSALS["two_dims_one_evidenced"], "retry_budget")
    r = D.report(narrowed, RUN_LOG)
    yield ("9 restrict the half-evidenced proposal to retry_budget: re-reported, no flag",
           r["outcome"] == D.NO_FLAG and r["actual_dimensions"] == ["retry_budget"]
           and PROPOSALS["two_dims_one_evidenced"]["after"]["memory_window"] == {"turns": 8},
           r["outcome"])


def main(out=sys.stdout):
    failures = 0
    for name, ok, detail in checks():
        out.write("%s  %s  [%s]\n" % ("ok  " if ok else "FAIL", name, detail))
        failures += 0 if ok else 1
    total = len(list(checks()))
    out.write("%d/%d fixture checks hold\n" % (total - failures, total))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
