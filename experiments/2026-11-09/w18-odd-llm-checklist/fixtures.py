"""Synthetic fixtures for the w18-odd-llm-checklist method sketch.

Every description is toy data written for this sketch: a made-up
"seed-swap" village simulation where agents trade seed packets. No real
paper, model run or simulation is described.

Run: python3 fixtures.py
"""

import copy

import checklist as C

FULL_BLOCKS = {
    "A": {
        "carried_state": "last 5 trades as rows (round, partner, offer, outcome)",
        "recall_rule": "newest 5 rows, no search; older rows dropped",
        "move_set": ["offer bean", "offer squash", "pass"],
        "who_sees_messages": "only the two trading partners",
    },
    "B": {
        "persona_origin": "hand-written by the sketch author",
        "persona_wording": "personas/seed_swap_v1.txt (verbatim, 3 lines each)",
        "persona_spread": "same template, garden size drawn from {small, large}",
        "persona_over_time": "fixed for the whole run",
    },
    "C": {
        "model_string": "toy-model-2026-10-01 (dated snapshot, not an alias)",
        "sampling": {"temperature": 0.7, "max_output_tokens": 256},
        "seed_or_nondeterminism": 1234,
        "service_and_date": "local stub, 2026-11-09",
    },
    "D": {
        "standing_prompt_text": "prompts/trade_turn_v1.txt (verbatim)",
        "speaker_stance": "narrator predicting what the trader does next, not the trader",
        "reply_to_action": "last line must read MOVE: <one of move_set>, case-insensitive",
        "bad_reply_handling": "re-ask up to 2 times with the same prompt, then pass",
        "history_trim": "keep newest 5 rows, drop the rest",
    },
    "E": {
        "target_pattern": "toy pattern: most pairs settle on one seed within 30 rounds",
        "runs_per_setting": 20,
        "spread_shown": "range across 20 runs, unit = whole run",
        "wording_shakeup": "two paraphrases of the instruction text",
        "no_llm_baseline": "fixed-rule trader that repeats its last good trade",
    },
}


def _desc(name, blocks):
    return {"id": name, "blocks": blocks}


def _without(name, block, *fields):
    blocks = copy.deepcopy(FULL_BLOCKS)
    for f in fields:
        del blocks[block][f]
    return _desc(name, blocks)


def build_descriptions():
    full = _desc("full", copy.deepcopy(FULL_BLOCKS))

    no_c = copy.deepcopy(FULL_BLOCKS)
    del no_c["C"]
    no_inference = _desc("no-inference-config", no_c)

    ph = copy.deepcopy(FULL_BLOCKS)
    ph["C"]["model_string"] = "TBD"
    ph["C"]["sampling"] = "default"
    ph["C"]["seed_or_nondeterminism"] = "   "
    ph["D"]["bad_reply_handling"] = "n/a."
    ph["E"]["spread_shown"] = []
    placeholders = _desc("placeholders", ph)

    extra = copy.deepcopy(FULL_BLOCKS)
    extra["F"] = {"mood_notes": "agents seemed cheerful"}
    extra_block = _desc("extra-block", extra)

    stance_dropped = _without("stance-dropped", "D", "speaker_stance")
    optional_only = _without("optional-gaps", "A", "who_sees_messages")
    del optional_only["blocks"]["E"]["no_llm_baseline"]

    return [full, no_inference, placeholders, extra_block, stance_dropped, optional_only]


def by_id():
    return {d["id"]: d for d in build_descriptions()}


def _flag_of(name):
    for row in C.flag([by_id()[name]]):
        return row
    return None


def check_full_not_flagged():
    d = C.detect(by_id()["full"])
    return (_flag_of("full") is None
            and all(not r["missing"] and not r["placeholder"] for r in d["blocks"].values()))


def check_inference_gap_flagged_in_c_only():
    row = _flag_of("no-inference-config")
    return (row is not None and row["required_gaps"] == {"C": ["C1", "C2", "C3"]}
            and row["undeclared_blocks"] == [])


def check_placeholders_count_as_not_documented():
    d = C.detect(by_id()["placeholders"])
    row = _flag_of("placeholders")
    return (d["blocks"]["C"]["placeholder"] == ["C1", "C2", "C3"]
            and d["blocks"]["D"]["placeholder"] == ["D4"]
            and d["blocks"]["E"]["placeholder"] == ["E3"]
            and row["required_gaps"] == {"C": ["C1", "C2", "C3"], "D": ["D4"], "E": ["E3"]})


def check_undeclared_block_reported():
    d = C.detect(by_id()["extra-block"])
    row = _flag_of("extra-block")
    rep = C.report([by_id()["extra-block"]])[0]
    return (d["undeclared_blocks"] == ["F"] and row["undeclared_blocks"] == ["F"]
            and row["required_gaps"] == {} and rep["undeclared_blocks"] == ["F"])


def check_stance_drop_flagged_in_d():
    row = _flag_of("stance-dropped")
    return row is not None and row["required_gaps"] == {"D": ["D2"]}


def check_optional_gaps_reported_not_flagged():
    rep = C.report([by_id()["optional-gaps"]])[0]["blocks"]
    return (_flag_of("optional-gaps") is None
            and rep["A"]["documented"] == "3/4" and rep["A"]["required_documented"] == "3/3"
            and rep["E"]["documented"] == "4/5" and rep["E"]["required_documented"] == "3/3")


def check_report_is_per_block():
    rows = C.report(build_descriptions())
    nc = {r["id"]: r for r in rows}["no-inference-config"]["blocks"]
    return (all(set(r["blocks"]) == set(C.BLOCK_IDS) for r in rows)
            and nc["C"]["documented"] == "0/4"
            and all(len(set(nc[k]["documented"].split("/"))) == 1 for k in "ABDE")
            and all("overall" not in r and "total" not in r for r in rows))


def check_compare_shows_block_c():
    d = by_id()
    out = C.compare(d["full"], d["no-inference-config"])
    return out["only_in_a"] == {"C": ["C1", "C2", "C3", "C4"]} and out["only_in_b"] == {}


CHECKS = (
    ("full description passes", check_full_not_flagged),
    ("missing inference config flagged in block C only", check_inference_gap_flagged_in_c_only),
    ("TBD / default / blank / n/a / [] count as not documented", check_placeholders_count_as_not_documented),
    ("undeclared block F reported, not dropped", check_undeclared_block_reported),
    ("dropped speaker stance flagged in block D", check_stance_drop_flagged_in_d),
    ("optional gaps lower coverage but are not flagged", check_optional_gaps_reported_not_flagged),
    ("coverage reported per block, no overall number", check_report_is_per_block),
    ("compare lists block C items", check_compare_shows_block_c),
)


def run_checks():
    return [(name, bool(fn())) for name, fn in CHECKS]


def main():
    results = run_checks()
    for name, ok in results:
        print("%s  %s" % ("PASS" if ok else "FAIL", name))
    passed = sum(1 for _, ok in results if ok)
    print("fixtures: %d/%d passed" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
