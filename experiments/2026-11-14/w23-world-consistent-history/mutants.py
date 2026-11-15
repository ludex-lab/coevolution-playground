"""Mutant runner: each mutant patches the code, the fixture world or the test
harness, then the unittest suite runs. A mutant is killed when at least one
test fails.

Code mutants replace one exact snippet of world_history.py or oracle.py
(each snippet must occur exactly once) and re-execute the patched source in
memory inside that module. World mutants change the fixtures in memory.
Harness mutants replace one helper of the test module in memory (the
row-scoped hygiene scan). Nothing is written to disk.

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
import test_world_history
import world_history

MODULES = {"world_history": world_history, "oracle": oracle}
SNAPSHOTS = {k: dict(vars(m)) for k, m in MODULES.items()}
FIX_SNAPSHOT = dict(vars(fixtures))
TEST_SNAPSHOT = dict(vars(test_world_history))
WORLD = ("FREEZES", "EDITS", "LABELS", "PLANTED")
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
    return code("world_history", *pairs)


def orc(*pairs):
    return code("oracle", *pairs)


def both(*applies):
    """Return an apply() that runs each apply() in turn."""
    def apply():
        for a in applies:
            a()
    return apply


CODE_MUTANTS = [
    # Rule arm.
    ("rule admits a done claim the world does not hold", mod(
        ("        elif c[0] == DONE and world[t] != c[1]:\n",
         "        elif False:\n"))),
    ("rule trusts the history text (admits every edit)", mod(
        ("    return {\"decision\": REFUSE if reasons else ADMIT, \"reasons\": tuple(reasons)}\n",
         "    return {\"decision\": ADMIT, \"reasons\": tuple(reasons)}\n"))),
    ("M1: rule admits a blank done claim (round 1 rule)", mod(
        ("        elif c[0] == DONE and blank(c[1]):\n            reasons.append((t, FALSE_DONE))\n",
         ""))),
    ("M1: blank means only \"\" (whitespace done admitted)", mod(
        ("    return value.strip() == \"\"\n", "    return value == \"\"\n"))),
    ("rule ignores erased claims", mod(
        ("            if t in before:\n", "            if False:\n"))),
    ("rule checks the done claim against gold, not the world", mod(
        ("        elif c[0] == DONE and world[t] != c[1]:\n",
         "        elif c[0] == DONE and snap[\"gold\"][t] != c[1]:\n"))),
    ("rule admits a done claim that carries the gold value", mod(
        ("        elif c[0] == DONE and world[t] != c[1]:\n",
         "        elif c[0] == DONE and world[t] != c[1] and snap[\"gold\"][t] != c[1]:\n"))),
    ("rule refuses failure receipts too", mod(
        ("        elif c[0] == DONE and world[t] != c[1]:\n",
         "        elif world[t] != c[1]:\n"))),
    ("rule reads the first claim, not the last", mod(
        ("        if claim in STATUS_CLAIMS:\n            out[target] = (claim, value)\n",
         "        if claim in STATUS_CLAIMS and target not in out:\n"
         "            out[target] = (claim, value)\n"))),
    ("rule checks the original history instead of the edit", mod(
        ("    after = last_claims(snap[\"edited\"])\n",
         "    after = last_claims(snap[\"history\"])\n"))),
    ("rule reads the edit kind", mod(
        ("    return {\"decision\": REFUSE if reasons else ADMIT, \"reasons\": tuple(reasons)}\n",
         "    if snap[\"edit_kind\"] == \"truthful_note\":\n        reasons = []\n"
         "    return {\"decision\": REFUSE if reasons else ADMIT, \"reasons\": tuple(reasons)}\n"))),
    ("rule refuses any edit that adds a note", mod(
        ("    reasons = []\n    for t in snap[\"targets\"]:\n",
         "    reasons = [(r[0], FALSE_DONE) for r in snap[\"edited\"] if r[1] == NOTE][:1]\n"
         "    for t in snap[\"targets\"]:\n"))),
    ("refused edit still reaches the receiver", mod(
        ("    rule_view = snap[\"edited\"] if r[\"decision\"] == ADMIT else snap[\"history\"]\n",
         "    rule_view = snap[\"edited\"]\n"))),
    ("refused edit hands the receiver an empty history", mod(
        ("    rule_view = snap[\"edited\"] if r[\"decision\"] == ADMIT else snap[\"history\"]\n",
         "    rule_view = snap[\"edited\"] if r[\"decision\"] == ADMIT else ()\n"))),
    # Baseline.
    ("baseline reads the world", mod(
        ("    return {\"decision\": ADMIT, \"believed_done\": tuple(believed)}\n",
         "    return {\"decision\": rule(snap)[\"decision\"], \"believed_done\": tuple(believed)}\n"))),
    ("baseline believes failure receipts as done", mod(
        ("                if c[0] == DONE]\n", "                ]\n"))),
    # Receiver stub.
    ("receiver ignores notes", mod(
        ("        if claim == NOTE:\n            notes[target] = value\n",
         "        if False:\n            notes[target] = value\n"))),
    ("receiver reads the world", mod(
        ("    writes = receiver(records, snap[\"guess\"], targets)\n",
         "    writes = receiver(records, world, targets)\n"))),
    ("receiver trusts every done claim", mod(
        ("            writes[t] = None if c[1] == guess[t] else guess[t]\n",
         "            writes[t] = None\n"))),
    ("receiver does not retry failed writes", mod(
        ("        else:\n            writes[t] = c[1]\n",
         "        else:\n            writes[t] = guess[t]\n"))),
    ("receiver skips untouched targets", mod(
        ("        elif c is None:\n            writes[t] = guess[t]\n",
         "        elif c is None:\n            writes[t] = None\n"))),
    ("receiver writes a note even when already done", mod(
        ("            writes[t] = None if done_same else notes[t]\n",
         "            writes[t] = notes[t]\n"))),
    # Scoring.
    ("recovery counts every target", mod(
        ("    remaining = tuple(t for t in targets if world[t] != gold[t])\n",
         "    remaining = tuple(targets)\n"))),
    ("skipped targets score as the gold value", mod(
        ("        final[t] = world[t] if writes[t] is None else writes[t]\n",
         "        final[t] = gold[t] if writes[t] is None else writes[t]\n"))),
    ("damage not counted", mod(
        ("    damaged = tuple(t for t in targets if world[t] == gold[t] and final[t] != gold[t])\n",
         "    damaged = ()\n"))),
    ("totals report no config_error records", mod(
        ("    out = {\"n\": len(rows), \"config_error\": len(records) - len(rows),\n",
         "    out = {\"n\": len(rows), \"config_error\": 0,\n"))),
    ("worse-than-unedited compared the wrong way", mod(
        ("            if len(o[\"recovered\"]) < u:\n", "            if len(o[\"recovered\"]) > u:\n"))),
    # Input (F1: exact-str keys before lookup, exact types, snapshot).
    ("non-str keys admitted everywhere", mod(
        ("        if type(k) is not str:\n            raise _Bad(detail)\n",
         "        if False:\n            raise _Bad(detail)\n"))),
    ("record keys not checked", mod(
        ("        _keys(rec, name + \"_key_invalid\")\n", ""))),
    ("value map keys not checked", mod(
        ("    _keys(m, name + \"_key_invalid\")\n", ""))),
    ("key check after lookup (case)", mod(
        ("    _keys(case, \"case_key_invalid\")\n    for name in CASE_FIELDS:\n"
         "        if name not in case:\n            raise _Bad(name + \"_missing\")\n",
         "    for name in CASE_FIELDS:\n        if name not in case:\n"
         "            raise _Bad(name + \"_missing\")\n"
         "    _keys(case, \"case_key_invalid\")\n"))),
    ("key check after lookup (record)", mod(
        ("        _keys(rec, name + \"_key_invalid\")\n"
         "        _fields(rec, RECORD_FIELDS, name + \"_record_invalid\")\n",
         "        _fields(rec, RECORD_FIELDS, name + \"_record_invalid\")\n"
         "        _keys(rec, name + \"_key_invalid\")\n"))),
    ("str subclasses admitted as ids", mod(
        ("    return type(v) is str and v.strip() != \"\"\n",
         "    return isinstance(v, str) and v.strip() != \"\"\n"))),
    ("record value may be a str subclass", mod(
        ("        if type(value) is not str:\n            raise _Bad(name + \"_value_invalid\")\n"
         "        out.append((target, claim, value))\n",
         "        if not isinstance(value, str):\n            raise _Bad(name + \"_value_invalid\")\n"
         "        out.append((target, claim, value))\n"))),
    ("world value may be a str subclass", mod(
        ("        if type(value) is not str:\n            raise _Bad(name + \"_value_invalid\")\n"
         "        out[target] = value\n",
         "        if not isinstance(value, str):\n            raise _Bad(name + \"_value_invalid\")\n"
         "        out[target] = value\n"))),
    ("histories may be tuples", mod(
        ("    if type(lst) is not list:\n", "    if type(lst) not in (list, tuple):\n"))),
    ("record may be a dict subclass", mod(
        ("        if type(rec) is not dict:\n", "        if not isinstance(rec, dict):\n"))),
    ("unknown case field admitted", mod(
        ("    _fields(case, CASE_FIELDS, \"case_unknown_field\")\n", ""))),
    ("map shape not checked", mod(
        ("    if sorted(m) != sorted(targets):\n        raise _Bad(name + \"_shape\")\n", ""))),
    ("duplicate targets admitted", mod(
        ("        if t in targets:\n            raise _Bad(\"target_duplicate\")\n", ""))),
    ("snapshot reuses the caller's world map", mod(
        ("    world = _value_map(case[\"world\"], targets, \"world\")\n",
         "    world = _value_map(case[\"world\"], targets, \"world\")\n    world = case[\"world\"]\n"))),
    ("snapshot reuses the caller's edited list", mod(
        ("            \"edited\": edited}\n", "            \"edited\": case[\"edited\"]}\n"))),
    ("snapshot reuses the caller's target list", mod(
        ("    targets = tuple(targets)\n", "    targets = raw\n"))),
    ("logic exceptions propagate", mod(
        ("        return _run(snap)\n    except Exception:\n"
         "        return _config(\"internal_error\")\n",
         "        return _run(snap)\n    finally:\n        pass\n"))),
    ("paper numbers reported as measured", mod(
        ("    return ON_UNMEASURED\n", "    return \"measured\"\n"))),
    # Oracle mutants (the oracle must stay a real reference).
    ("oracle: done claim never checked", orc(
        ("        if now is not None and now[0] == \"done\" and (not now[1].split()\n"
         "                                                      or now[1] != case[\"world\"][t]):\n",
         "        if False:\n"))),
    ("oracle: blank done claim matches a blank world", orc(
        ("(not now[1].split()\n                                                      or now[1] != case[\"world\"][t]):\n",
         "(now[1] != case[\"world\"][t]):\n"))),
    ("M1: round 1 rule restored in module and oracle", both(
        mod(("        elif c[0] == DONE and blank(c[1]):\n            reasons.append((t, FALSE_DONE))\n",
             "")),
        orc(("(not now[1].split()\n                                                      or now[1] != case[\"world\"][t]):\n",
             "(now[1] != case[\"world\"][t]):\n")))),
    ("oracle: erased claims ignored", orc(
        ("        if now is None and was is not None:\n", "        if False:\n"))),
    ("oracle: receiver ignores notes", orc(
        ("        if n is not None:\n            w = None if c == (\"done\", n) else n\n",
         "        if False:\n            w = None\n"))),
    ("oracle: failed claims are skipped", orc(
        ("        elif c[0] == \"failed\":\n            w = c[1]\n",
         "        elif c[0] == \"failed\":\n            w = None\n"))),
    ("oracle: refused edit still reaches the receiver", orc(
        ("        \"rule_view\": reference_score(case, case[\"edited\"] if decision == \"ADMIT\"\n"
         "                                     else case[\"history\"]),\n",
         "        \"rule_view\": reference_score(case, case[\"edited\"]),\n"))),
]


def _w():
    return {k: copy.deepcopy(v) for k, v in WORLD_ORIG.items()}


def _set(**kw):
    for k, v in kw.items():
        setattr(fixtures, k, v)


def _edit(case_id, edited):
    w = _w()
    w["EDITS"] = [(e[0], e[1], e[2], edited if e[0] == case_id else e[3]) for e in w["EDITS"]]
    _set(EDITS=w["EDITS"])


def w_planted_made_true():
    w = _w()
    w["FREEZES"]["store-effect-absent"]["world"]["order_status"] = "shipped"
    _set(FREEZES=w["FREEZES"])


def w_planted_done_removed():
    _edit("wrong-commit-completed-action",
          [{"target": "name", "claim": "done", "value": "Ada"},
           {"target": "color", "claim": "done", "value": "navy"}])


def w_note_drops_the_error():
    _edit("hard-error-truthful-note",
          [{"target": "zip", "claim": "done", "value": "69001"},
           {"target": "city", "claim": "note", "value": "Lyon"}])


def w_note_names_the_wrong_value():
    _edit("hard-error-truthful-note",
          [{"target": "city", "claim": "done", "value": "Paris"},
           {"target": "zip", "claim": "done", "value": "69001"},
           {"target": "city", "claim": "note", "value": "Nice"}])


def w_receiver_guess_fixed():
    w = _w()
    w["FREEZES"]["form-hard-error"]["guess"]["city"] = "Lyon"
    _set(FREEZES=w["FREEZES"])


def w_gold_world_fixed():
    w = _w()
    w["FREEZES"]["form-wrong-commit"]["world"]["color"] = "blue"
    _set(FREEZES=w["FREEZES"])


def w_present_effect_removed():
    w = _w()
    w["FREEZES"]["store-effect-present"]["world"]["order_status"] = ""
    _set(FREEZES=w["FREEZES"])


def w_label_flipped():
    w = _w()
    lab = w["LABELS"]["meal-absent-success-receipt"]
    w["LABELS"]["meal-absent-success-receipt"] = (fixtures.M.ADMIT, ()) + lab[2:]
    _set(LABELS=w["LABELS"])


def w_planted_entry_dropped():
    _set(PLANTED=WORLD_ORIG["PLANTED"][1:])


def w_case_dropped():
    _set(EDITS=[e for e in _w()["EDITS"] if e[0] != "effect-absent-erase-error"])


def w_erase_retains_claim():
    _edit("effect-absent-erase-error",
          [{"target": "order_status", "claim": "failed", "value": "shipped"},
           {"target": "email_sent", "claim": "done", "value": "yes"}])


def w_cases_shared():
    shared = dict((e[0], fixtures.C(*e)) for e in fixtures.EDITS)
    fixtures.cases = lambda: shared


WORLD_MUTANTS = [
    ("planted false done made true in the world", w_planted_made_true),
    ("planted completed action reverted to the unedited history", w_planted_done_removed),
    ("truthful note drops the preserved error", w_note_drops_the_error),
    ("truthful note names the wrong value", w_note_names_the_wrong_value),
    ("receiver guess fixed on the hard error", w_receiver_guess_fixed),
    ("gold world: the wrong commit already corrected", w_gold_world_fixed),
    ("present effect removed from the world", w_present_effect_removed),
    ("hand label flipped to ADMIT", w_label_flipped),
    ("planted entry dropped", w_planted_entry_dropped),
    ("erase-error case dropped", w_case_dropped),
    ("erase-error edit retains the claim", w_erase_retains_claim),
    ("cases() returns shared state", w_cases_shared),
]


def h_scan_whole_day_readme():
    test_world_history.scan_text = lambda name, text: text


def h_own_rows_every_line():
    test_world_history.own_rows = lambda text: text.splitlines()


def h_own_rows_nothing():
    test_world_history.own_rows = lambda text: []


def h_hygiene_ignores_banned_words():
    real = test_world_history.hygiene_hits
    test_world_history.hygiene_hits = lambda text: real(text) - {"banned_word"}


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
    fixtures.__dict__.update(FIX_SNAPSHOT)
    _set(**_w())
    test_world_history.__dict__.update(TEST_SNAPSHOT)


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_world_history)
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
