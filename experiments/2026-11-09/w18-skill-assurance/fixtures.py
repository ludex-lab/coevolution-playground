"""Synthetic fixtures for the w18-skill-assurance method sketch.

Run: python3 fixtures.py  (prints a summary; exit code 0 when every fixture
holds). Every skill below is toy data authored for this sketch.
"""

import copy
import json
import sys

import assurance as A

MANIFEST = A.load_manifest()

GOOD_INPUT = {"sacks": 5, "bin": "east", "spare": True}

# Each payload breaks the input contract in exactly one way.
OUT_OF_CONTRACT = [
    ("sacks above maximum", {"sacks": 9, "bin": "south", "spare": False}),
    ("sacks below minimum", {"sacks": -1, "bin": "south", "spare": False}),
    ("sacks as string", {"sacks": "3", "bin": "south", "spare": False}),
    ("sacks as boolean", {"sacks": True, "bin": "south", "spare": False}),
    ("sacks as float", {"sacks": 3.0, "bin": "south", "spare": False}),
    ("bin outside enum", {"sacks": 3, "bin": "north", "spare": False}),
    ("missing spare", {"sacks": 3, "bin": "south"}),
    ("undeclared field", {"sacks": 3, "bin": "south", "spare": False, "bin_key": "N-7"}),
    ("not an object", [3, "south", False]),
]


def manifest_for(skill_id, **changes):
    m = copy.deepcopy(MANIFEST)
    m["skill_id"] = skill_id
    for path, value in changes.items():
        side, field, key = path.split("__")
        for f in m[side]["fields"]:
            if f["name"] == field:
                f[key] = value
    return m


# ---------------------------------------------------------- author effects
# Each effect below is plausible, runs, and passes its author's own check.
# None of the author checks mention the declared boundary it breaks.

def pack_cart_double(payload):
    """Author's idea: two crates per sack (sturdier packing)."""
    return {"crates": 2 * payload["sacks"] + (2 if payload["spare"] else 0),
            "bin": payload["bin"]}


def pack_cart_east_spill(payload):
    """Spare loads for east are rerouted through the north bins."""
    to_bin = "north" if (payload["bin"] == "east" and payload["spare"]) else payload["bin"]
    return {"crates": payload["sacks"] + (2 if payload["spare"] else 0), "bin": to_bin}


def pack_cart_empty_key(payload):
    """An empty cart carries the bin key back."""
    out = {"crates": payload["sacks"] + (2 if payload["spare"] else 0), "bin": payload["bin"]}
    if payload["sacks"] == 0:
        out["bin_key"] = "N-7"
    return out


def pack_cart_synth(payload):
    """Builds its arithmetic from a string at call time."""
    expr = "s + (2 if p else 0)"
    crates = eval(expr, {}, {"s": payload["sacks"], "p": payload["spare"]})
    return {"crates": crates, "bin": payload["bin"]}


_tally = {"n": 0}


def pack_cart_drift(payload):
    """Adds one crate on every other call (hidden state)."""
    _tally["n"] += 1
    return {"crates": payload["sacks"] + (_tally["n"] % 2), "bin": payload["bin"]}


def author_check(expect_crates, payload):
    def check(call):
        return call(payload)["crates"] == expect_crates
    return check


SMALL = {"sacks": 3, "bin": "south", "spare": False}


def build_skills():
    _tally["n"] = 0  # fresh hidden state per build, so runs repeat exactly
    good_effect = A.load_effect(MANIFEST)
    return {
        "pack_cart": A.Skill(MANIFEST, good_effect,
                             [("three sacks, three crates", author_check(3, SMALL))]),
        "pack_cart_double": A.Skill(manifest_for("pack_cart_double"), pack_cart_double,
                                    [("three sacks, six crates", author_check(6, SMALL))]),
        "pack_cart_east_spill": A.Skill(manifest_for("pack_cart_east_spill"), pack_cart_east_spill,
                                        [("three sacks, three crates", author_check(3, SMALL))]),
        "pack_cart_empty_key": A.Skill(manifest_for("pack_cart_empty_key"), pack_cart_empty_key,
                                       [("three sacks, three crates", author_check(3, SMALL))]),
        "pack_cart_synth": A.Skill(manifest_for("pack_cart_synth"), pack_cart_synth,
                                   [("three sacks, three crates", author_check(3, SMALL))]),
        "pack_cart_drift": A.Skill(manifest_for("pack_cart_drift"), pack_cart_drift,
                                   [("three sacks, at least three crates",
                                     lambda call: call(SMALL)["crates"] >= 3)]),
    }


BROKEN = ("pack_cart_double", "pack_cart_east_spill", "pack_cart_empty_key",
          "pack_cart_synth", "pack_cart_drift")


# ---------------------------------------------------------------- fixtures

def fixture_a_contracted_shape():
    skills = build_skills()
    reg = A.Registry()
    reg.hold(skills["pack_cart"])
    res = reg.register("pack_cart")
    out = reg.invoke("pack_cart", GOOD_INPUT)
    shape = not A.check_against(MANIFEST["output_contract"], out, "output")
    ok = res["status"] == "registered" and out == {"crates": 7, "bin": "east"} and shape
    return ok, "registered; %s -> %s; output in contract: %s" % (
        json.dumps(GOOD_INPUT, sort_keys=True), json.dumps(out, sort_keys=True), shape)


def fixture_b_rejected_before_effect():
    skills = build_skills()
    reg = A.Registry()
    reg.hold(skills["pack_cart"])
    reg.register("pack_cart")
    skill = skills["pack_cart"]
    before = skill.calls
    rejected = 0
    for _, payload in OUT_OF_CONTRACT:
        try:
            reg.invoke("pack_cart", payload)
        except A.Rejected:
            rejected += 1
    ok = rejected == len(OUT_OF_CONTRACT) and skill.calls == before
    return ok, "%d/%d out-of-contract inputs rejected; effect calls %d -> %d" % (
        rejected, len(OUT_OF_CONTRACT), before, skill.calls)


def fixture_c_contract_derived():
    skills = build_skills()
    rows = []
    ok = True
    for sid in BROKEN:
        c = A.compare(skills[sid])
        ok = ok and c["author_checks"] == "pass" and c["contract_assurance"] == "fail"
        rows.append("%s: author checks %s, assurance %s (%s)" % (
            sid, c["author_checks"], c["contract_assurance"], c["first_failure"][0]))
    # The reject comes from the manifest number: declare a cart cap of 18 and
    # the same doubling effect passes the same assurance code.
    wider = A.Skill(manifest_for("pack_cart_double", output_contract__crates__maximum=18),
                    pack_cart_double, skills["pack_cart_double"].author_checks)
    wide = A.detect(wider)["status"]
    ok = ok and wide == "pass"
    rows.append("pack_cart_double with declared maximum 18: assurance %s" % wide)
    return ok, rows


def fixture_d_cannot_register():
    skills = build_skills()
    reg = A.Registry()
    statuses = {}
    for sid in ("pack_cart",) + BROKEN:
        reg.hold(skills[sid])
        statuses[sid] = reg.register(sid)["status"]
    invoke_blocked = 0
    for sid in BROKEN:
        try:
            reg.invoke(sid, SMALL)
        except A.Rejected:
            invoke_blocked += 1
    # Holding a broken skill again and retrying does not change the outcome.
    reg.hold(skills["pack_cart_double"])
    retry = reg.register("pack_cart_double")["status"]
    rep = reg.report()
    ok = (statuses["pack_cart"] == "registered"
          and all(statuses[s] == "rejected" for s in BROKEN)
          and invoke_blocked == len(BROKEN) and retry == "rejected"
          and rep["registered"] == ["pack_cart"])
    return ok, "registered %s; rejected %d/%d broken; invoke on rejected blocked %d/%d; retry %s" % (
        rep["registered"], sum(statuses[s] == "rejected" for s in BROKEN), len(BROKEN),
        invoke_blocked, len(BROKEN), retry)


def baseline_author_checks_only():
    """The shape this sketch is not: register whenever the author's checks pass."""
    skills = build_skills()
    passed = [sid for sid in ("pack_cart",) + BROKEN
              if all(r["passed"] for r in A.run_author_checks(skills[sid]))]
    return passed


FIXTURES = (
    ("a contracted shape", fixture_a_contracted_shape),
    ("b rejected before effect", fixture_b_rejected_before_effect),
    ("c contract-derived assurance", fixture_c_contract_derived),
    ("d failed assurance cannot register", fixture_d_cannot_register),
)


def run_all():
    results = []
    for name, fn in FIXTURES:
        ok, detail = fn()
        results.append((name, ok, detail))
    return results


def main():
    results = run_all()
    print("w18-skill-assurance fixtures (synthetic, deterministic)")
    for name, ok, detail in results:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
        for line in (detail if isinstance(detail, list) else [detail]):
            print("    " + line)
    base = baseline_author_checks_only()
    print("baseline, author checks only: %d/%d skills would pass, incl. %d broken"
          % (len(base), 1 + len(BROKEN), len([s for s in base if s in BROKEN])))
    passed = sum(ok for _, ok, _ in results)
    print("summary: %d/%d fixtures pass" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
