"""Mutant runner: each mutant patches the code, the fixture world or the test
harness, then the unittest suite runs. A mutant is killed when at least one
test fails.

Code mutants replace one exact snippet of trust_feedback.py or
oracle.py (each snippet must occur exactly once) and re-execute the patched
source in memory inside that module. World mutants change the fixtures in
memory and rebuild the cases. Harness mutants replace one helper of the
test module in memory (the row-scoped hygiene scan). Nothing is written to
disk.

Run: python3 -B mutants.py
Exit code 0 only when every mutant is killed and the clean suite passes.
"""

import copy
import io
import os
import sys
import unittest

import fixtures
import oracle
import test_trust_feedback
import trust_feedback

MODULES = {"trust_feedback": trust_feedback, "oracle": oracle}
SNAPSHOTS = {k: dict(vars(m)) for k, m in MODULES.items()}
FIX_SNAPSHOT = dict(vars(fixtures))
TEST_SNAPSHOT = dict(vars(test_trust_feedback))
WORLD = ("TRACKS", "CONFIDENCE", "CASES", "LABELS", "FEEDBACK", "NO_FEEDBACK", "CONTROLS",
         "SPOOFS", "SPOOF_REASON")
WORLD_ORIG = {k: copy.deepcopy(getattr(fixtures, k)) for k in WORLD}
HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = {}
for _k in MODULES:
    with open(os.path.join(HERE, _k + ".py"), "r", encoding="utf-8") as _fh:
        SOURCES[_k] = _fh.read()


def code(module, *pairs):
    """Return an apply() that swaps each (old, new) snippet once in module."""
    def apply():
        text = SOURCES[module]
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError("snippet not found exactly once: %r" % (old,))
            text = text.replace(old, new)
        path = os.path.join(HERE, module + ".py")
        exec(compile(text, path, "exec"), MODULES[module].__dict__)
    return apply


def mod(*pairs):
    return code("trust_feedback", *pairs)


def orc(*pairs):
    return code("oracle", *pairs)


def both(*applies):
    def apply():
        for a in applies:
            a()
    return apply


CODE_MUTANTS = [
    # Feedback acceptance.
    ("self-sourced feedback accepted", mod(
        ("    if source == snap[\"advisor_id\"] or source == advisor:\n        return SELF_SOURCED\n",
         ""))),
    ("self-sourced checks only the event's advisor", mod(
        ("    if source == snap[\"advisor_id\"] or source == advisor:\n",
         "    if source == advisor and False:\n"))),
    ("undeclared sources accepted", mod(
        ("    if source not in snap[\"external_sources\"]:\n        return NOT_EXTERNAL\n", ""))),
    ("feedback for another advisor accepted", mod(
        ("    if advisor != snap[\"advisor_id\"]:\n        return ADVISOR_MISMATCH\n", ""))),
    ("rounds outside the session accepted", mod(
        ("    if rnd < 1 or rnd > snap[\"rounds\"]:\n", "    if rnd < 1:\n"))),
    ("feedback for a future round accepted", mod(
        ("    if rnd > at:\n        return FUTURE_ROUND\n", ""))),
    ("stale feedback accepted", mod(
        ("    if at - rnd > snap[\"max_age\"]:\n", "    if False:\n"))),
    ("max_age boundary exclusive", mod(
        ("    if at - rnd > snap[\"max_age\"]:\n", "    if at - rnd >= snap[\"max_age\"]:\n"))),
    ("replayed feedback accepted", mod(
        ("    if (source, advisor, rnd, outcome) in seen:\n        return DUPLICATE\n", ""))),
    ("dedupe on the round alone (a timely negative for a graded round refused)", mod(
        ("    if (source, advisor, rnd, outcome) in seen:\n",
         "    if rnd in [key[2] for key in seen]:\n"))),
    ("dedupe on (source, round) (a source cannot correct itself)", mod(
        ("    if (source, advisor, rnd, outcome) in seen:\n",
         "    if (source, rnd) in [(key[0], key[2]) for key in seen]:\n"))),
    ("dedupe ignores the source (a second source's grade refused)", mod(
        ("    if (source, advisor, rnd, outcome) in seen:\n",
         "    if (rnd, outcome) in [(key[2], key[3]) for key in seen]:\n"))),
    ("a re-send in a later round is not a replay", mod(
        ("            seen.append((ev[0], ev[1], ev[2], ev[4]))\n",
         "            seen.append((ev[0], ev[1], ev[2], ev[4], k))\n"),
        ("    if (source, advisor, rnd, outcome) in seen:\n",
         "    if (source, advisor, rnd, outcome, at) in seen:\n"))),
    # Trust dynamics.
    ("prior trusted", mod(
        ("    state = PRIOR\n", "    state = TRUSTED\n"))),
    ("upgrade on the first correct (bar ignored)", mod(
        ("                if score >= snap[\"trust_bar\"] and state != TRUSTED:\n",
         "                if state != TRUSTED:\n"))),
    ("bar off by one", mod(
        ("                if score >= snap[\"trust_bar\"] and state != TRUSTED:\n",
         "                if score > snap[\"trust_bar\"] and state != TRUSTED:\n"))),
    ("a negative does not drop trust", mod(
        ("                score = 0\n                state = UNTRUSTED\n",
         "                score = 0\n"))),
    ("a negative does not reset the score", mod(
        ("                score = 0\n                state = UNTRUSTED\n",
         "                state = UNTRUSTED\n"))),
    ("a negative decrements the score instead of resetting it", mod(
        ("                score = 0\n                state = UNTRUSTED\n",
         "                score = max(0, score - 1)\n                state = UNTRUSTED\n"))),
    ("a round's 'correct' counts again from a second source", mod(
        ("                if rnd in credited:\n                    continue\n", ""))),
    ("a refuted round counts again on a later 'correct'", mod(
        ("                if rnd in refuted:\n                    continue\n", ""))),
    ("events applied in list order (a later correct beats a negative)", mod(
        ("        ordered = ([e for e in this_round if e[1] == CORRECT]\n"
         "                   + [e for e in this_round if e[1] == INCORRECT])\n",
         "        ordered = this_round\n"))),
    ("trust read after the round's feedback", mod(
        ("        reliance.append(RELY if state == TRUSTED else VERIFY)\n        this_round = []\n",
         "        this_round = []\n"),
        ("            else:\n                refuted.append(rnd)\n                score = 0\n"
         "                state = UNTRUSTED\n",
         "            else:\n                refuted.append(rnd)\n                score = 0\n"
         "                state = UNTRUSTED\n"
         "        reliance.append(RELY if state == TRUSTED else VERIFY)\n"))),
    ("trust rises with stated confidence", mod(
        ("        reliance.append(RELY if state == TRUSTED else VERIFY)\n        this_round = []\n",
         "        if snap[\"advice\"][k - 1][1] >= 0.95:\n            state = TRUSTED\n"
         "        reliance.append(RELY if state == TRUSTED else VERIFY)\n        this_round = []\n"))),
    ("trust rises with the advisor's claim", mod(
        ("        reliance.append(RELY if state == TRUSTED else VERIFY)\n        this_round = []\n",
         "        if \"rely on me\" in snap[\"advice\"][k - 1][2]:\n            state = TRUSTED\n"
         "        reliance.append(RELY if state == TRUSTED else VERIFY)\n        this_round = []\n"))),
    ("trust rises with prestige", mod(
        ("        reliance.append(RELY if state == TRUSTED else VERIFY)\n        this_round = []\n",
         "        if \"expert\" in snap[\"advice\"][k - 1][3]:\n            state = TRUSTED\n"
         "        reliance.append(RELY if state == TRUSTED else VERIFY)\n        this_round = []\n"))),
    ("rule reads the condition label", mod(
        ("    state = PRIOR\n", "    state = TRUSTED if snap[\"condition\"] == \"no_feedback\" else PRIOR\n"))),
    # Pending decisions and expiry.
    ("expiry resolves to RELY", mod(
        ("            out.append((pid, on_expiry, deadline))\n",
         "            out.append((pid, RELY, deadline))\n"))),
    ("late feedback resolves a pending decision", mod(
        ("            if graded == rnd and at <= deadline:\n", "            if graded == rnd:\n"))),
    ("stale feedback counts for a pending decision", mod(
        ("        for i, graded, outcome in arm[\"accepted\"]:\n            at = snap[\"feedback\"][i][3]\n",
         "        for e in snap[\"feedback\"]:\n            graded, at, outcome = e[2], e[3], e[4]\n"))),
    ("pending: the first timely event wins (a later timely negative ignored)", mod(
        ("        if timely[INCORRECT]:\n            out.append((pid, DO_NOT_RELY, min(timely[INCORRECT])))\n"
         "        elif timely[CORRECT]:\n",
         "        if timely[INCORRECT] and (not timely[CORRECT]\n"
         "                                  or min(timely[INCORRECT]) < min(timely[CORRECT])):\n"
         "            out.append((pid, DO_NOT_RELY, min(timely[INCORRECT])))\n"
         "        elif timely[CORRECT]:\n"))),
    ("pending: the last timely event wins", mod(
        ("        if timely[INCORRECT]:\n            out.append((pid, DO_NOT_RELY, min(timely[INCORRECT])))\n"
         "        elif timely[CORRECT]:\n",
         "        if timely[INCORRECT] and (not timely[CORRECT]\n"
         "                                  or max(timely[INCORRECT]) >= max(timely[CORRECT])):\n"
         "            out.append((pid, DO_NOT_RELY, min(timely[INCORRECT])))\n"
         "        elif timely[CORRECT]:\n"))),
    ("pending: a timely correct outranks a negative", mod(
        ("        if timely[INCORRECT]:\n            out.append((pid, DO_NOT_RELY, min(timely[INCORRECT])))\n"
         "        elif timely[CORRECT]:\n",
         "        if timely[INCORRECT] and not timely[CORRECT]:\n"
         "            out.append((pid, DO_NOT_RELY, min(timely[INCORRECT])))\n"
         "        elif timely[CORRECT]:\n"))),
    ("missing on_expiry defaults to DENY", mod(
        ("            if \"on_expiry\" not in [k for k in rec]:\n                raise _Bad(\"on_expiry_missing\")\n",
         "            if \"on_expiry\" not in [k for k in rec]:\n                rec = dict(rec, on_expiry=DENY)\n"))),
    ("RELY accepted as an on_expiry", mod(
        ("ON_EXPIRY = (DENY, SAFE_FALLBACK, ESCALATE, HOLD)\n",
         "ON_EXPIRY = (DENY, SAFE_FALLBACK, ESCALATE, HOLD, RELY)\n"))),
    ("pending deadline may pass the last round", mod(
        ("        if not _int(p[\"deadline\"], p[\"round\"], n):\n",
         "        if not _int(p[\"deadline\"], p[\"round\"]):\n"))),
    ("str subclass accepted as on_expiry", mod(
        ("        if type(p[\"on_expiry\"]) is not str or p[\"on_expiry\"] not in ON_EXPIRY:\n",
         "        if not isinstance(p[\"on_expiry\"], str) or p[\"on_expiry\"] not in ON_EXPIRY:\n"))),
    # Persuadable baseline.
    ("baseline starts low", mod(("BASE_START = 2\n", "BASE_START = 1\n"))),
    ("baseline ignores confidence", mod(
        ("            level = min(BASE_TOP, level + 1)\n", "            level = level\n"))),
    ("baseline ignores negative feedback", mod(
        ("            if ev[3] == k and ev[4] == INCORRECT:\n                level = 0\n",
         "            if False:\n                level = 0\n"))),
    ("baseline confidence bar exclusive", mod(
        ("        if snap[\"advice\"][k - 1][1] >= BASE_CONFIDENT:\n",
         "        if snap[\"advice\"][k - 1][1] > BASE_CONFIDENT:\n"))),
    ("baseline uses the rule's validated feedback", mod(
        ("    return tuple(reliance)\n\n\ndef score",
         "    return rule(snap)[\"reliance\"]\n\n\ndef score"))),
    # Validation: exact types and keys.
    ("key types not checked", mod(
        ("        if type(k) is not str:\n            raise _Bad(detail)\n",
         "        if False:\n            raise _Bad(detail)\n"))),
    ("str subclass accepted as an id", mod(
        ("    return type(v) is str and v.strip() != \"\"\n",
         "    return isinstance(v, str) and v.strip() != \"\"\n"))),
    ("bool and int subclass accepted as ints", mod(
        ("    return type(v) is int and v >= lo and (hi is None or v <= hi)\n",
         "    return isinstance(v, int) and v >= lo and (hi is None or v <= hi)\n"))),
    ("NaN, infinities and out-of-range confidence accepted", mod(
        ("    return type(v) is float and 0.0 <= v <= 1.0\n",
         "    return type(v) is float and not 0.0 > v\n"))),
    ("float subclass accepted as confidence", mod(
        ("    return type(v) is float and 0.0 <= v <= 1.0\n",
         "    return isinstance(v, float) and 0.0 <= v <= 1.0\n"))),
    ("event round may be a bool or int subclass", mod(
        ("        if type(e[\"round\"]) is not int:\n", "        if not isinstance(e[\"round\"], int):\n"))),
    ("dict subclass accepted as a record", mod(
        ("    if type(d) is not dict:\n        raise _Bad(name + \"_invalid\")\n",
         "    if not isinstance(d, dict):\n        raise _Bad(name + \"_invalid\")\n"))),
    ("duplicate external sources accepted", mod(
        ("    if len(set(sources)) != len(sources):\n", "    if False:\n"))),
    ("snapshot shares the caller's external_sources", mod(
        ("    sources = tuple(_list(raw[\"external_sources\"], \"external_sources\"))\n",
         "    sources = _list(raw[\"external_sources\"], \"external_sources\") and raw[\"external_sources\"]\n"))),
    ("snapshot shares the caller's truth list", mod(
        ("    truth = tuple(_list(raw[\"truth\"], \"truth\"))\n",
         "    truth = _list(raw[\"truth\"], \"truth\") and raw[\"truth\"]\n"))),
    ("internal errors escape evaluate()", mod(
        ("    try:\n        return _run(snap)\n    except Exception:\n        return _error(\"internal_error\")\n",
         "    return _run(snap)\n"))),
    ("totals count every session as upgraded", mod(
        ("sum(1 for c in present if ok[c][\"upgraded\"])", "len(present)"))),
    # Oracle.
    ("oracle: stale boundary exclusive", orc(
        ("            (\"stale\", age > case[\"max_age\"]),\n",
         "            (\"stale\", age >= case[\"max_age\"]),\n"))),
    ("oracle: replay accepted", orc(
        ("            (\"duplicate\", sig in taken),\n",
         "            (\"duplicate\", False),\n"))),
    ("oracle: dedupe on the round alone", orc(
        ("            (\"duplicate\", sig in taken),\n",
         "            (\"duplicate\", ev[\"round\"] in set(t[2] for t in taken)),\n"))),
    ("oracle: a counted round may count again", orc(
        ("        spent = spent | plus | minus\n", "        spent = spent | minus\n"))),
    ("oracle: pending ranks the earliest event first", orc(
        ("        top = min(timely, key=lambda e: (e[\"outcome\"] == \"correct\", e[\"at\"]))\n",
         "        top = min(timely, key=lambda e: e[\"at\"])\n"))),
    ("oracle: refusal order swapped", orc(
        ("            (\"not_external\", src not in case[\"external_sources\"]),\n"
         "            (\"advisor_mismatch\", ev[\"advisor_id\"] != me),\n",
         "            (\"advisor_mismatch\", ev[\"advisor_id\"] != me),\n"
         "            (\"not_external\", src not in case[\"external_sources\"]),\n"))),
    ("oracle: a negative beside a counted correct is ignored", orc(
        ("        if minus:\n            pts = 0\n            trusted = False\n",
         "        if minus and not plus:\n            pts = 0\n            trusted = False\n"))),
    ("oracle: expiry on late feedback ignored", orc(
        ("                  and case[\"feedback\"][j][\"at\"] <= p[\"deadline\"]]\n", "                  ]\n"))),
    ("oracle: baseline confidence bar inclusive flipped", orc(
        ("        if not case[\"advice\"][k - 1][\"confidence\"] < 0.5:\n",
         "        if case[\"advice\"][k - 1][\"confidence\"] > 0.5:\n"))),
    ("oracle: bar off by one", orc(
        ("        if not trusted and pts + len(plus) >= case[\"trust_bar\"]:\n",
         "        if not trusted and pts + len(plus) > case[\"trust_bar\"]:\n"))),
]


def _w():
    return dict((k, copy.deepcopy(v)) for k, v in WORLD_ORIG.items())


def _set(**kw):
    for k, v in kw.items():
        setattr(fixtures, k, v)


def _rebuild():
    fixtures.CASES = fixtures._build()


def _track(advisor, track):
    t = copy.deepcopy(WORLD_ORIG["TRACKS"])
    t[advisor] = track
    _set(TRACKS=t)
    _rebuild()


def _case(name):
    for c in fixtures.CASES:
        if c["case_id"] == name:
            return c
    raise KeyError(name)


def w_unhelpful_made_helpful():
    _track("U", [True] * fixtures.N)


def w_mixed_made_streaky():
    _track("M", [True] * 4 + [False] * 6)


def w_switch_never_wrong():
    _track("S", [True] * fixtures.N)


def w_no_feedback_gets_feedback():
    _case("H-no-feedback")["feedback"] = fixtures.graded("H")


def w_spoof_made_genuine():
    for e in _case("SP4-stale")["feedback"]:
        e["at"] = e["round"]


def w_spoof_case_dropped():
    _set(SPOOFS=WORLD_ORIG["SPOOFS"][:5],
         SPOOF_REASON=dict((k, v) for k, v in WORLD_ORIG["SPOOF_REASON"].items()
                           if k in WORLD_ORIG["SPOOFS"][:5]))


def w_boundary_control_too_late():
    for e in _case("C3-H-at-max-age")["feedback"]:
        e["at"] = min(e["at"] + 1, fixtures.N)


def w_expiry_case_gets_feedback():
    _case("PE-no-feedback-expiry")["feedback"] = fixtures.graded("H")


def w_unhelpful_not_confident():
    c = copy.deepcopy(WORLD_ORIG["CONFIDENCE"])
    c["U"] = 0.2
    _set(CONFIDENCE=c)
    _rebuild()


def w_label_flipped():
    lab = dict(WORLD_ORIG["LABELS"])
    lab["U-no-feedback"] = ("ok", True, "trusted", 10, True)
    _set(LABELS=lab)


def w_control_dropped():
    _set(CONTROLS=WORLD_ORIG["CONTROLS"][:2])


def w_cases_shared():
    shared = dict((c["case_id"], c) for c in fixtures.CASES)
    fixtures.cases = lambda: shared


WORLD_MUTANTS = [
    ("unhelpful advisor made helpful", w_unhelpful_made_helpful),
    ("mixed advisor made streaky (4 right in a row)", w_mixed_made_streaky),
    ("switching advisor never wrong", w_switch_never_wrong),
    ("no-feedback session given feedback", w_no_feedback_gets_feedback),
    ("stale spoof made fresh", w_spoof_made_genuine),
    ("spoof cases dropped below six", w_spoof_case_dropped),
    ("boundary control one round too late", w_boundary_control_too_late),
    ("expiry case given feedback", w_expiry_case_gets_feedback),
    ("unhelpful advisor not confident", w_unhelpful_not_confident),
    ("hand label flipped", w_label_flipped),
    ("control dropped", w_control_dropped),
    ("cases() returns shared state", w_cases_shared),
]


def h_scan_whole_day_readme():
    test_trust_feedback.scan_text = lambda name, text: text


def h_own_rows_every_line():
    test_trust_feedback.own_rows = lambda text: text.splitlines()


def h_own_rows_nothing():
    test_trust_feedback.own_rows = lambda text: []


def h_hygiene_ignores_banned_words():
    real = test_trust_feedback.hygiene_hits
    test_trust_feedback.hygiene_hits = lambda text: real(text) - {"banned_word"}


HARNESS_MUTANTS = [
    ("hygiene scans read the whole day README", h_scan_whole_day_readme),
    ("own-row filter returns every line", h_own_rows_every_line),
    ("own-row filter returns nothing", h_own_rows_nothing),
    ("hygiene helper ignores banned words", h_hygiene_ignores_banned_words),
]

MUTANTS = ([("code", n, a) for n, a in CODE_MUTANTS]
           + [("world", n, a) for n, a in WORLD_MUTANTS]
           + [("harness", n, a) for n, a in HARNESS_MUTANTS])


def restore():
    for k, m in MODULES.items():
        for name in [n for n in vars(m) if n not in SNAPSHOTS[k]]:
            delattr(m, name)
        m.__dict__.update(SNAPSHOTS[k])
    for name in [n for n in vars(fixtures) if n not in FIX_SNAPSHOT]:
        delattr(fixtures, name)
    fixtures.__dict__.update(FIX_SNAPSHOT)
    _set(**_w())
    test_trust_feedback.__dict__.update(TEST_SNAPSHOT)


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_trust_feedback)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


def main():
    restore()
    ran, bad = run_suite()
    print("clean suite: %d tests, %d failing" % (ran, bad))
    clean_ok = bad == 0
    killed = {"code": 0, "world": 0, "harness": 0}
    for kind, name, apply in MUTANTS:
        try:
            apply()
            ran, bad = run_suite()
        except Exception as exc:
            restore()
            print("%-7s %-62s BROKEN   (%s)" % (kind, name, type(exc).__name__))
            continue
        finally:
            restore()
        status = "KILLED" if bad else "SURVIVED"
        killed[kind] += 1 if bad else 0
        print("%-7s %-62s %-8s (%d/%d tests failing)" % (kind, name, status, bad, ran))
    ran, bad = run_suite()
    print("clean suite after restore: %d tests, %d failing" % (ran, bad))
    clean_ok = clean_ok and bad == 0
    n_code, n_world, n_harness = len(CODE_MUTANTS), len(WORLD_MUTANTS), len(HARNESS_MUTANTS)
    total = killed["code"] + killed["world"] + killed["harness"]
    print("killed %d/%d (code %d/%d, world %d/%d, harness %d/%d)"
          % (total, n_code + n_world + n_harness, killed["code"], n_code,
             killed["world"], n_world, killed["harness"], n_harness))
    ok = clean_ok and total == n_code + n_world + n_harness
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
