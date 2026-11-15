"""Mutant runner: each mutant patches code, the fixture world or a baseline,
then the unittest suite runs. A mutant is killed when at least one test
fails or errors.

- code: replaces one exact snippet of creg_belief.py or oracle.py (each
  snippet must occur exactly once) and re-executes the patched source in
  memory inside that module.
- world: changes the frozen suite in memory. The frozen digest, frozen
  reference and README sync tests are skipped for these
  (test_creg_belief.WORLD_MUTANT), so only semantic tests can kill them.
- baseline: changes one baseline's options in memory.

Nothing is written to disk. Run: python3 -B mutants.py
Exit code 0 only when every mutant is killed and the clean suite passes
before and after.
"""

import copy
import io
import os
import sys
import unittest

import creg_belief
import fixtures
import oracle
import test_creg_belief

HERE = os.path.dirname(os.path.abspath(__file__))
MODULES = {"creg_belief": creg_belief, "oracle": oracle}
SNAPSHOTS = {k: dict(vars(m)) for k, m in MODULES.items()}
SOURCES = {}
for _k in MODULES:
    with open(os.path.join(HERE, _k + ".py"), encoding="utf-8") as _fh:
        SOURCES[_k] = _fh.read()
SUITE_ORIG = copy.deepcopy(fixtures.SUITE)
BASELINES_ORIG = copy.deepcopy(creg_belief.BASELINES)


def code(module, *pairs):
    def apply():
        text = SOURCES[module]
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError("snippet not found exactly once: %r" % (old,))
            text = text.replace(old, new)
        exec(compile(text, os.path.join(HERE, module + ".py"), "exec"), MODULES[module].__dict__)
    return apply


def cb(*pairs):
    return code("creg_belief", *pairs)


def orc(*pairs):
    return code("oracle", *pairs)


def find(sid):
    return next(x for x in fixtures.SUITE if x["id"] == sid)


def report(sid, rid):
    return next(r for r in find(sid)["reports"] if r["id"] == rid)


def world(edit):
    def apply():
        test_creg_belief.WORLD_MUTANT = True
        edit()
    return apply


def _drop_report(sid, rid):
    sc = find(sid)
    sc["reports"] = [r for r in sc["reports"] if r["id"] != rid]


def _set(sid, rid, **kw):
    report(sid, rid).update(kw)


def _scen(sid, **kw):
    find(sid).update(kw)


def _remove_scenario(sid):
    fixtures.SUITE[:] = [x for x in fixtures.SUITE if x["id"] != sid]


def _strip_measures():
    for sc in fixtures.SUITE:
        sc["relations"] = [r for r in sc["relations"] if r[1] != "measures" or r[2] != sc["target"]]


def _del(sid, field):
    del find(sid)[field]


def baseline(name, **kw):
    def apply():
        creg_belief.BASELINES[name] = dict(creg_belief.BASELINES[name], **kw)
    return apply


CODE_MUTANTS = [
    ("strong threshold log 2", cb(("STRONG_LLR = math.log(3.0)", "STRONG_LLR = math.log(2.0)"))),
    ("dispatch threshold 0.95", cb(("HI = 0.9\n", "HI = 0.95\n"))),
    ("continue threshold 0.05", cb(("LO = 0.1\n", "LO = 0.05\n"))),
    ("expiry strictly after deadline", cb(("    if now >= deadline:\n", "    if now > deadline:\n"))),
    ("expiry never fires", cb(("    if now >= deadline:\n", "    if False:\n"))),
    ("dispatch on timeout", cb(("    if now >= deadline:\n        return on_expiry\n",
                                "    if now >= deadline:\n        return DISPATCH\n"))),
    ("expiry only when undecided", cb(("    if now >= deadline:\n        return on_expiry\n    if contradiction:\n        return RECONCILE\n    if posterior >= HI:\n        return DISPATCH\n",
                                       "    if contradiction:\n        return RECONCILE\n    if posterior >= HI:\n        return DISPATCH\n    if now >= deadline:\n        return on_expiry\n"))),
    ("dispatch outranks contradiction", cb(("    if contradiction:\n        return RECONCILE\n    if posterior >= HI:\n        return DISPATCH\n",
                                            "    if posterior >= HI:\n        return DISPATCH\n    if contradiction:\n        return RECONCILE\n"))),
    ("stale at age == max_age", cb(("now - r[\"t\"] > max_age", "now - r[\"t\"] >= max_age"))),
    ("age from arrival, not observation", cb(("now - r[\"t\"] > max_age", "now - r[\"at\"] > max_age"))),
    ("now is observation time", cb(("        now = report[\"at\"]\n", "        now = report[\"t\"]\n"))),
    ("supersedes ignored", cb(("            superseded.add(report[\"supersedes\"])\n", "            pass\n"))),
    ("future supersession leaks", cb(("    superseded = set()\n",
                                      "    superseded = {x[\"supersedes\"] for x in snap[\"reports\"] if \"supersedes\" in x}\n"))),
    ("lookahead over all reports", cb(("        for r in arrived:\n", "        for r in snap[\"reports\"]:\n"))),
    ("reliability ignored", cb(("    w = sources[report[\"source\"]] if use_reliability else 1.0\n", "    w = 1.0\n"))),
    ("polarity ignored", cb(("    return report[\"polarity\"] * w * math.log", "    return w * math.log"))),
    ("prior ignored", cb(("    prior_lo = math.log(prior / (1.0 - prior))\n", "    prior_lo = 0.0\n"))),
    ("any relation links", cb(("if r[1] == MEASURES and r[2] == target}", "if r[2] == target}"))),
    ("relation direction ignored", cb(("if r[1] == MEASURES and r[2] == target}", "if r[1] == MEASURES}"))),
    ("relations always used", cb(("    if opts[\"relations\"]:\n", "    if True:\n"))),
    ("contradiction needs one strong side", cb(("            conflicts = tuple((a, b) for a in strong_for for b in strong_against)\n",
                                                "            conflicts = tuple((a, a) for a in strong_for + strong_against)\n"))),
    ("contradiction never flagged", cb(("        contradiction = bool(conflicts)\n", "        contradiction = False\n"))),
    ("stale evidence still supports", cb(("            elif opts[\"staleness\"] and now - r[\"t\"] > max_age:\n                stale.append(r[\"id\"])\n",
                                          "            elif opts[\"staleness\"] and now - r[\"t\"] > max_age:\n                stale.append(r[\"id\"])\n                live.append((r[\"id\"], _llr(r, sources, opts[\"reliability\"])))\n"))),
    ("missing on_expiry defaults to HOLD", cb(("    if \"on_expiry\" not in scenario:\n        raise _Bad(\"on_expiry_missing\")\n",
                                               "    if \"on_expiry\" not in scenario:\n        scenario[\"on_expiry\"] = HOLD\n"))),
    ("on_expiry accepts a dispatch", cb(("ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY)\n",
                                         "ON_EXPIRY_VALUES = (HOLD, ESCALATE, DENY, DISPATCH)\n"))),
    ("on_expiry str subclass accepted", cb(("    if type(scenario[\"on_expiry\"]) is not str or", "    if not isinstance(scenario[\"on_expiry\"], str) or"))),
    ("bool accepted as int", cb(("    return type(v) is int\n", "    return isinstance(v, int)\n"))),
    ("unknown source accepted", cb(("        if r[\"source\"] not in weights:\n            raise _Bad(\"report_source_unknown\")\n", ""))),
    ("arrival order not checked", cb(("        if last_at is not None and r[\"at\"] < last_at:\n", "        if False:\n"))),
    ("observed after arrival accepted", cb(("or r[\"t\"] > r[\"at\"]:", ":"))),
    ("forward supersedes accepted", cb(("        if \"supersedes\" in r and r[\"supersedes\"] not in seen:\n", "        if False:\n"))),
    ("confidence 0.5 accepted", cb(("not 0.5 < c < 1.0", "not 0.5 <= c < 1.0"))),
    ("strict match ignores posterior", cb(("    if abs(pred[\"posterior\"] - ref[\"posterior\"]) > tol:\n", "    if False:\n"))),
    ("strict match ignores action", cb(("STRICT_KEYS = (\"support\", \"contradict\", \"contradiction\", \"action\")",
                                        "STRICT_KEYS = (\"support\", \"contradict\", \"contradiction\")"))),
    ("endpoint is first prefix", cb(("    ends = [marks[-1] for marks", "    ends = [marks[0] for marks"))),
    ("length mismatch scored by zip", cb(("    if len(pred_prefixes) != len(ref_prefixes):\n        return [False] * len(ref_prefixes)\n", ""))),
    ("drop_relations is a no-op", cb(("    out[\"relations\"] = []\n", ""))),
    ("drop_relations mutates input", cb(("    out = dict(scenario)\n", "    out = scenario\n"))),
    # r2 (F1): exact-str keys, exact-str source and supersedes, one snapshot.
    ("scenario key type not checked", cb(("    if not _str_keys(scenario):\n        raise _Bad(\"scenario_key_invalid\")\n", ""))),
    ("report key type not checked", cb(("        if not _str_keys(r):\n            raise _Bad(\"report_key_invalid\")\n", ""))),
    ("str subclass key accepted", cb(("    return all(type(k) is str for k in d)\n", "    return all(isinstance(k, str) for k in d)\n"))),
    ("source type not checked", cb(("        if type(r[\"source\"]) is not str:\n            raise _Bad(\"report_source_invalid\")\n", ""))),
    ("supersedes type not checked", cb(("        if \"supersedes\" in r and type(r[\"supersedes\"]) is not str:\n            raise _Bad(\"report_supersedes_invalid\")\n", ""))),
    ("on_expiry read back from input", cb(("    on_expiry = ON_EXPIRY_VALUES[ON_EXPIRY_VALUES.index(scenario[\"on_expiry\"])]\n",
                                           "    on_expiry = scenario[\"on_expiry\"]\n"))),
    ("run re-reads on_expiry after validation", cb(("        prefixes = _trajectory(snap, opts)\n", "        prefixes = _trajectory(dict(snap, on_expiry=scenario[\"on_expiry\"]), opts)\n"))),
    ("run re-reads deadline after validation", cb(("        prefixes = _trajectory(snap, opts)\n", "        prefixes = _trajectory(dict(snap, deadline=scenario[\"deadline\"]), opts)\n"))),
    ("run re-reads reports after validation", cb(("        prefixes = _trajectory(snap, opts)\n", "        prefixes = _trajectory(dict(snap, reports=scenario[\"reports\"]), opts)\n"))),
    ("original F1: key check off, on_expiry re-read", cb(("    if not _str_keys(scenario):\n        raise _Bad(\"scenario_key_invalid\")\n", ""),
                                                         ("        prefixes = _trajectory(snap, opts)\n", "        prefixes = _trajectory(dict(snap, on_expiry=scenario[\"on_expiry\"]), opts)\n"))),
    ("report snapshot shares caller dict", cb(("        r = dict(r)\n", ""), ("        snapped.append(snap)\n", "        snapped.append(r)\n"))),
    ("sources snapshot shares caller dict", cb(("\"sources\": weights,", "\"sources\": sources,"))),
    # r2 (F5): hostile or extreme input is config_error.
    ("overflow not mapped", cb(("    except OverflowError:\n        return {\"status\": CONFIG_ERROR, \"reason\": \"numeric_overflow\", \"prefixes\": []}\n", ""))),
    ("type error not mapped", cb(("    except TypeError:\n        return {\"status\": CONFIG_ERROR, \"reason\": \"type_invalid\", \"prefixes\": []}\n", ""))),
    # r2 (F3): exact container types and supersession by stale or unlinked reports.
    ("relation fields not type-checked", cb(("len(rel) != 3 or not all(_is_str(x) for x in rel)", "len(rel) != 3"))),
    ("dict subclass accepted as scenario", cb(("    if type(scenario) is not dict:\n", "    if not isinstance(scenario, dict):\n"))),
    ("list subclass accepted as reports", cb(("    if type(reports) is not list or not reports:", "    if not isinstance(reports, list) or not reports:"))),
    ("dict subclass accepted as report", cb(("        if type(r) is not dict:\n", "        if not isinstance(r, dict):\n"))),
    ("supersession only by a linked report", cb(("        if opts[\"supersedes\"] and \"supersedes\" in report:\n",
                                                 "        if opts[\"supersedes\"] and \"supersedes\" in report and report[\"entity\"] in linked:\n"))),
    ("supersession only by a fresh report", cb(("        if opts[\"supersedes\"] and \"supersedes\" in report:\n",
                                                "        if opts[\"supersedes\"] and \"supersedes\" in report and now - report[\"t\"] <= max_age:\n"))),
    ("oracle: supersession only by a linked report", orc(("    gone = {r[\"supersedes\"] for r in reports if \"supersedes\" in r}\n",
                                                          "    gone = {r[\"supersedes\"] for r in reports if \"supersedes\" in r and r[\"entity\"] in entities}\n"))),
    ("oracle: strong factor 2.5", orc(("STRONG_FACTOR = 3.0\n", "STRONG_FACTOR = 2.5\n"))),
    ("oracle: dispatch odds 8", orc(("DISPATCH_ODDS = 9.0 ", "DISPATCH_ODDS = 8.0 "))),
    ("oracle: stale at age == max_age", orc(("if now > r[\"t\"] + scenario[\"max_age\"]:", "if now >= r[\"t\"] + scenario[\"max_age\"]:"))),
    ("oracle: supersedes ignored", orc(("    gone = {r[\"supersedes\"] for r in reports if \"supersedes\" in r}\n", "    gone = set()\n"))),
    ("oracle: reliability ignored", orc(("    return ratio ** reliability[report[\"source\"]]\n", "    return ratio\n"))),
    ("oracle: expiry after deadline", orc(("    if now >= scenario[\"deadline\"]:\n", "    if now > scenario[\"deadline\"]:\n"))),
    ("oracle: any relation links", orc(("        if rel == \"measures\":\n", "        if True:\n"))),
]

WORLD_MUTANTS = [
    ("resolution-a loses its correction", world(lambda: _drop_report("contradiction-resolution-a", "i4"))),
    ("resolution-a contradiction never opens", world(lambda: _set("contradiction-resolution-a", "i3", polarity=1))),
    ("resolution-b robot never ages out", world(lambda: _scen("contradiction-resolution-b", max_age=10))),
    ("onset-b contradiction removed", world(lambda: _set("contradiction-onset-b", "h2", confidence=0.6))),
    ("relation-a mis-tagged", world(lambda: _scen("relation-a", relation_dependent=False))),
    ("measures relations removed", world(_strip_measures)),
    ("no-relation scenario uses the sensor", world(lambda: _set("preservation-a", "c3", entity="sensor-p3"))),
    ("stale-a report arrives fresh", world(lambda: _set("stale-a", "k1", at=1))),
    ("stale-b nothing ages out", world(lambda: _scen("stale-b", max_age=10))),
    ("deadline-a deadline far", world(lambda: _scen("deadline-a", deadline=50))),
    ("deadline-b on_expiry missing", world(lambda: _del("deadline-b", "on_expiry"))),
    ("iot-9 fully reliable", world(lambda: [find(x)["sources"].update({"iot-9": 1.0})
                                           for x in ("reliability-a", "reliability-b")])),
    ("onset regime down to one scenario", world(lambda: _remove_scenario("contradiction-onset-b"))),
    ("revision-b first lean removed", world(lambda: _set("revision-b", "b1", polarity=-1))),
    ("other-gauge measures relation removed", world(lambda: [x.__setitem__("relations", [r for r in x["relations"] if r[0] != "sensor-p9"])
                                                             for x in fixtures.SUITE])),
    ("preservation-a weak report made decisive", world(lambda: _set("preservation-a", "c2", source="robot-1", confidence=0.99))),
]

BASELINE_MUTANTS = [
    ("no_contradiction is full", baseline("no_contradiction", contradiction=True)),
    ("no_staleness is full", baseline("no_staleness", staleness=True)),
    ("no_supersedes is full", baseline("no_supersedes", supersedes=True)),
    ("no_reliability is full", baseline("no_reliability", reliability=True)),
    ("full drops contradiction", baseline("full", contradiction=False)),
    ("no_staleness also drops reliability", baseline("no_staleness", reliability=False)),
]

MUTANTS = ([("code", n, a) for n, a in CODE_MUTANTS]
           + [("world", n, a) for n, a in WORLD_MUTANTS]
           + [("baseline", n, a) for n, a in BASELINE_MUTANTS])


def restore():
    for key, mod in MODULES.items():
        for name in [n for n in vars(mod) if n not in SNAPSHOTS[key]]:
            delattr(mod, name)
        mod.__dict__.update(SNAPSHOTS[key])
    fixtures.SUITE[:] = copy.deepcopy(SUITE_ORIG)
    creg_belief.BASELINES.clear()
    creg_belief.BASELINES.update(copy.deepcopy(BASELINES_ORIG))
    test_creg_belief.WORLD_MUTANT = False


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_creg_belief)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


def main():
    restore()
    ran, bad = run_suite()
    print("clean suite: %d tests, %d failing" % (ran, bad))
    clean_ok = bad == 0
    killed = {"code": 0, "world": 0, "baseline": 0}
    totals = {"code": len(CODE_MUTANTS), "world": len(WORLD_MUTANTS),
              "baseline": len(BASELINE_MUTANTS)}
    for kind, name, apply in MUTANTS:
        try:
            apply()
            ran, bad = run_suite()
        except Exception as exc:
            print("%-8s %-44s BROKEN   (%s)" % (kind, name, type(exc).__name__))
            continue
        finally:
            restore()
        killed[kind] += 1 if bad else 0
        print("%-8s %-44s %-8s (%d/%d tests failing)" % (
            kind, name, "KILLED" if bad else "SURVIVED", bad, ran))
    ran, bad = run_suite()
    print("clean suite after restore: %d tests, %d failing" % (ran, bad))
    clean_ok = clean_ok and bad == 0
    total = sum(killed.values())
    print("killed %d/%d (code %d/%d, world %d/%d, baseline %d/%d)" % (
        total, sum(totals.values()), killed["code"], totals["code"],
        killed["world"], totals["world"], killed["baseline"], totals["baseline"]))
    return 0 if clean_ok and total == sum(totals.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
