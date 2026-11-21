"""Demo: one play-then-craft session on the frozen fixture. Run: python3 -B demo.py

The whole transcript below is produced by this code from the fixture; none of it is written by hand.
"""

import os
import sys

import play_craft as pc

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    return pc.load_fixture(os.path.join(HERE, "fixtures", name))


def knob_text(fx, params):
    return " ".join("%s=%d" % (k["id"], params[k["id"]]) for k in fx["knobs"])


def episode_text(line):
    return line["outcome"] if line["path"] is None else "%s path, %s" % (line["path"], line["outcome"])


def deny_text(fx, declared, params, proposal):
    try:
        pc.check_proposal(declared, fx["knobs"], params, proposal)
    except pc.DenyError as e:
        return "%s (%s)" % (e.code, e.detail)
    return "accepted"


def main():
    out = []
    fx = load("main.json")
    result = pc.run(fx)
    crafter = result["crafter"]
    target = fx["target"]
    band = target["band"]
    episodes = fx["game"]["episodes"]
    out.append("play-then-craft demo (fixtures/main.json)")
    out.append("transcript produced by this code from the fixture, not written by hand")
    out.append("method sketch only; scripted players; no model is called; the gain is fixture-authored by construction")
    out.append("")
    out.append("TARGET (declared before any episode): level %s, first clear in episodes %d..%d of %d"
               % (target["level"], band["lo"], band["hi"], episodes))
    out.append("KNOBS at the start: " + knob_text(fx, crafter["initial_params"]))
    for rnd in crafter["rounds"]:
        out.append("")
        out.append("-- crafting round %d (%s) --" % (rnd["round"], knob_text(fx, rnd["params"])))
        for rep in rnd["target_reports"]:
            out.append("PLAY %s ep%d: %s path, %s (progress %d/%d)" % (
                rep["level"], rep["episode"], rep["decisions"][0], rep["outcome"], rep["progress_num"], rep["progress_den"]))
        reports = rnd["target_reports"]
        clears = sum(1 for r in reports if r["outcome"] == "clear")
        long_fails = sum(1 for r in reports if r["outcome"] == "fail" and r["decisions"][0] == "long")
        short_fails = sum(1 for r in reports if r["outcome"] == "fail" and r["decisions"][0] == "short")
        first = rnd["target_first_clear"]
        out.append("REPORT: %d clears in %d episodes; first clear %s; long-path failures %d; short-path failures %d"
                   % (clears, len(reports), "none" if first is None else "ep%d" % first, long_fails, short_fails))
        if rnd["changes"]:
            name = sorted(rnd["changes"])[0]
            out.append("CRAFT (%s): %s %d -> %d" % (rnd["why"], name, rnd["params"][name], rnd["changes"][name]))
        else:
            out.append("CRAFT (%s): no change" % rnd["why"])
    out.append("")
    out.append("REVISED: " + knob_text(fx, crafter["final_params"]))
    out.append("FILE DIFF against the initial parameter file: " + ", ".join(crafter["file_diff"]))
    ev = crafter["evaluation"]
    out.append("EVAL fresh players with empty memory, %d episodes each:" % episodes)
    for level in fx["levels"]:
        lv = ev["levels"][level["id"]]
        out.append("  %-8s %s | gain %s slope %s first clear %s" % (
            level["id"], " ".join(e["outcome"] for e in lv["episodes"]), lv["gain"], lv["slope"],
            "none" if lv["first_clear"] is None else "ep%d" % lv["first_clear"]))
    out.append("RESULT: %s first clear lands %s" % (target["level"], crafter["target_verdict"]))
    out.append("")
    out.append("CONTROLS against the same declared band:")
    for name in ("noop", "overtune"):
        c = result["controls"][name]
        first = c["evaluation"]["levels"][target["level"]]["first_clear"]
        out.append("  %-8s %s -> first clear %s -> %s" % (name, knob_text(fx, c["final_params"]),
                                                          "none" if first is None else "ep%d" % first, c["target_verdict"]))
    out.append("")
    leaky = crafter["leaky_contrast"]["target_first_clear"]
    out.append("FRESH EVALUATION: crafting memory at the end of the last round was %s; the evaluation started from %s"
               % (crafter["crafting_memory_end"][target["level"]], crafter["eval_memory_start"][target["level"]]))
    out.append("  carrying that memory over would have shown first clear ep%s (counterfactual; the loop never does it)" % leaky)
    out.append("")
    out.append("REFUSALS (the same check the loop applies):")
    declared = target
    params = crafter["final_params"]
    cue = pc.knob_of(fx, "cue")
    reserve = pc.knob_of(fx, "reserve")
    edited = {"level": target["level"], "band": {"lo": 1, "hi": band["hi"]}}
    out.append("  target edited after the reports: " + deny_text(fx, declared, params,
               {"target": edited, "changes": {}, "why": "edit"}))
    out.append("  craft with no target after seeing EVAL: " + deny_text(fx, declared, params,
               {"target": None, "changes": {}, "why": "no_target"}))
    out.append("  undeclared knob: " + deny_text(fx, declared, params,
               {"target": declared, "changes": {"volume": 1}, "why": "wild"}))
    out.append("  knob above its max: " + deny_text(fx, declared, params,
               {"target": declared, "changes": {cue["id"]: cue["max"] + 1}, "why": "wild"}))
    out.append("  knob given as a boolean: " + deny_text(fx, declared, params,
               {"target": declared, "changes": {reserve["id"]: True}, "why": "wild"}))
    out.append("")
    out.append("HOLD (an episode that is capped or has no report is never a clear and licenses no craft):")
    for name in ("hold_capped.json", "hold_no_report.json"):
        held = pc.run(load(name))
        rnd = held["crafter"]["rounds"][0]
        first = rnd["held"][0]
        out.append("  %-20s status %s; round 1 licensed %s; first held: %s ep%d (%s); knobs stay %s" % (
            name, held["status"], str(rnd["licensed"]).lower(), first["level"], first["episode"], first["reason"],
            knob_text(fx, held["crafter"]["final_params"])))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
