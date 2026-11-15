"""Mutant runner: each mutant patches the code, the fixture world or the
test harness, then the unittest suite runs. A mutant is killed when at least
one test fails.

Code mutants replace one exact snippet of revision_selectivity.py (each
snippet must occur exactly once) and re-execute the patched source in
memory inside the revision_selectivity module. World mutants change the
fixtures in memory; while one runs, the frozen digest, frozen expected
table and README sync tests skip, so it must be caught by a semantic test.
Harness mutants swap one helper of the test module (for example, the
day-README row scoping of the hygiene scans). Nothing is written to disk.

The first three code mutants are the ones the done-when names: flip on the
expert label, report "helped" from reversal counts alone, and mix neutral
into the disagreement score. The r2 input-handling mutants skip an exact-str
key check, loosen an exact-type check, or make the module read the caller's
objects instead of its validated snapshot.

Run: python3 -B mutants.py
Exit code 0 only when every mutant is killed and the clean suite passes.
"""

import copy
import io
import os
import sys
import unittest

import fixtures
import revision_selectivity
import test_revision_selectivity

SNAPSHOT = dict(vars(revision_selectivity))
FIX_SNAPSHOT = dict(vars(fixtures))
TEST_SNAPSHOT = dict(vars(test_revision_selectivity))
POLICY_ORIG = copy.deepcopy(fixtures.POLICY_ITEMS)
BATCHES_ORIG = copy.deepcopy(fixtures.BATCHES)
RULE_ORIG = copy.deepcopy(fixtures.HELP_RULE)
PATH = os.path.join(os.path.dirname(os.path.abspath(revision_selectivity.__file__)),
                    "revision_selectivity.py")
with open(PATH, "r", encoding="utf-8") as _fh:
    SOURCE = _fh.read()


def code(*pairs):
    """Return an apply() that swaps each (old, new) snippet once in the module."""
    def apply():
        text = SOURCE
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError("snippet not found exactly once: %r" % (old,))
            text = text.replace(old, new)
        exec(compile(text, PATH, "exec"), revision_selectivity.__dict__)
    return apply


CALL = "    record = _decide(item, trial[\"argument\"])\n"

CODE_MUTANTS = [
    # --- the three done-when mutants ---
    ("flip on expert label (revise whenever an expert disagrees)", code(
        (CALL, CALL + "    if context == EXPERT:\n"
               "        record = dict(record, decision=REVISE, final=_other(item[\"initial\"]))\n"))),
    ("helped from reversal counts alone (any reversal)", code(
        ("    helped = wrong_rev > k * correct_rev\n", "    helped = reversals > 0\n"))),
    ("neutral mixed into the disagreement score", code(
        ("[r for r in rows if r[1] in DISAGREEMENT]", "[r for r in rows if r[1] in CONTEXTS]"))),
    # --- further code mutants ---
    ("expert label raises the bar to revise (retain under expert)", code(
        (CALL, CALL + "    if context == EXPERT and record[\"decision\"] == REVISE:\n"
               "        record = dict(record, decision=RETAIN, final=item[\"initial\"])\n"))),
    ("helped from reversal counts alone (reversals > k)", code(
        ("    helped = wrong_rev > k * correct_rev\n", "    helped = reversals > k\n"))),
    ("helped from net accuracy alone", code(
        ("    helped = wrong_rev > k * correct_rev\n",
         "    helped = final_correct > initial_correct\n"))),
    ("threshold checked with >= (off by one)", code(
        ("    helped = wrong_rev > k * correct_rev\n", "    helped = wrong_rev >= k * correct_rev\n"))),
    ("declared threshold ignored (k = 1)", code(
        ("    helped = wrong_rev > k * correct_rev\n", "    helped = wrong_rev > correct_rev\n"))),
    ("DISAGREEMENT constant includes neutral", code(
        ("DISAGREEMENT = (ANONYMOUS, EXPERT)\n", "DISAGREEMENT = (NEUTRAL, ANONYMOUS, EXPERT)\n"))),
    ("expert rows dropped from disagreement", code(
        ("[r for r in rows if r[1] in DISAGREEMENT]", "[r for r in rows if r[1] == ANONYMOUS]"))),
    ("neutral block reports the disagreement block", code(
        ("                \"neutral\": neutral, \"disagreement\": disagreement,",
         "                \"neutral\": disagreement, \"disagreement\": disagreement,"))),
    ("wrong and correct reversals swapped", code(
        ("            if was_right:\n                correct_rev += 1\n            else:\n                wrong_rev += 1\n",
         "            if was_right:\n                wrong_rev += 1\n            else:\n                correct_rev += 1\n"))),
    ("reversal judged against the correct label", code(
        ("        if final != item[\"initial\"]:\n            reversals += 1\n",
         "        if final != item[\"correct\"]:\n            reversals += 1\n"))),
    ("missing help rule defaults to 3", code(
        ("    if type(help_rule) is not dict:\n        raise _Bad(\"help_rule_missing\")\n"
         "    _require_str_keys(help_rule, \"help_rule_non_str_key\")\n"
         "    if RULE_KEY not in help_rule:\n        raise _Bad(\"help_rule_missing\")\n",
         "    if type(help_rule) is not dict or RULE_KEY not in help_rule:\n"
         "        help_rule = {RULE_KEY: 3}\n"))),
    ("extra help-rule keys admitted (e.g. an imported bar)", code(
        ("    if set(help_rule) != {RULE_KEY}:\n        raise _Bad(\"help_rule_unknown_key\")\n", ""))),
    ("zero threshold admitted", code(
        ("    if type(k) is not int or k < 1:\n", "    if type(k) is not int or k < 0:\n"))),
    ("bool admitted as threshold", code(
        ("    if type(k) is not int or k < 1:\n", "    if not isinstance(k, int) or k < 1:\n"))),
    ("unpaired argument admitted", code(
        ("    if trial[\"argument\"] != item[\"argument\"]:\n        raise _Bad(\"unpaired_argument\")\n", ""))),
    ("duplicate trial admitted", code(
        ("        if (item[\"id\"], context) in seen:\n            raise _Bad(\"duplicate_trial\")\n", ""))),
    ("prestige flips not reported", code(
        ("    flips = tuple(i for i in paired if anon[i] != expert[i])\n", "    flips = ()\n"))),
    ("unknown citation revises", code(
        ("        decision, reason = RETAIN, R_UNKNOWN\n", "        decision, reason = REVISE, R_UNKNOWN\n"))),
    ("mixed citations revise", code(
        ("        decision, reason = RETAIN, R_SUPPORTS_INITIAL\n",
         "        decision, reason = REVISE, R_SUPPORTS_INITIAL\n"))),
    ("uncited appeal revises", code(
        ("        decision, reason = RETAIN, R_NO_CITATION\n", "        decision, reason = REVISE, R_NO_CITATION\n"))),
    ("revise leaves the final unchanged", code(
        ("    final = other if decision == REVISE else initial\n", "    final = initial\n"))),
    ("context validation dropped", code(
        ("    if not _is_str(context) or context not in CONTEXTS:\n", "    if not _is_str(context):\n"))),
    ("exact-type answer check loosened", code(
        ("    return _is_str(value) and value in ANSWERS\n", "    return value in ANSWERS\n"))),
    # --- r2 (F1): exact-str keys, exact types, validated snapshot ---
    ("item key check skipped", code(
        ("    _require_str_keys(item, \"item_non_str_key\")\n", ""))),
    ("trial key check skipped", code(
        ("    _require_str_keys(trial, \"trial_non_str_key\")\n", ""))),
    ("help-rule key check skipped", code(
        ("    _require_str_keys(help_rule, \"help_rule_non_str_key\")\n", ""))),
    ("evidence key check skipped (non-str evidence keys admitted)", code(
        ("    _require_str_keys(evidence, \"item_evidence_non_str_key\")\n", ""))),
    ("key check admits str subclasses", code(
        ("        if type(key) is not str:\n", "        if not isinstance(key, str):\n"))),
    ("item snapshot is the caller's dict (re-read after validation)", code(
        ("    snap[\"evidence\"] = _snap_evidence(item[\"evidence\"])\n    return snap\n",
         "    _snap_evidence(item[\"evidence\"])\n    return item\n"))),
    ("evidence snapshot aliases the caller's dict", code(
        ("        out[key] = value\n    return out\n", "        out[key] = value\n    return evidence\n"))),
    ("decide works from the caller's item, not the snapshot", code(
        ("        return _decide_trial(snap, snap_trial)\n", "        return _decide_trial(item, snap_trial)\n"))),
    ("a source field on the caller's trial changes the decision", code(
        ("        return _decide_trial(snap, snap_trial)\n",
         "        record = _decide_trial(snap, snap_trial)\n"
         "        if trial.get(\"source\") == \"expert\":\n"
         "            record = dict(record, decision=REVISE, final=_other(snap[\"initial\"]))\n"
         "        return record\n"))),
    # --- r2 (F5): exact types and pairing everywhere ---
    ("int-subclass threshold admitted", code(
        ("    if type(k) is not int or k < 1:\n",
         "    if not isinstance(k, int) or type(k) is bool or k < 1:\n"))),
    ("str-subclass context admitted", code(
        ("    if not _is_str(context) or context not in CONTEXTS:\n",
         "    if not isinstance(context, str) or context not in CONTEXTS:\n"))),
    ("dict-subclass trial admitted", code(
        ("    if type(trial) is not dict:\n        raise _Bad(\"trial_not_dict\")\n",
         "    if not isinstance(trial, dict):\n        raise _Bad(\"trial_not_dict\")\n"))),
    ("dict-subclass item admitted", code(
        ("    if type(item) is not dict:\n        raise _Bad(\"item_not_dict\")\n",
         "    if not isinstance(item, dict):\n        raise _Bad(\"item_not_dict\")\n"))),
    ("unpaired argument checked only on expert trials", code(
        ("    if trial[\"argument\"] != item[\"argument\"]:\n",
         "    if trial[\"context\"] == EXPERT and trial[\"argument\"] != item[\"argument\"]:\n"))),
    ("decide raises on an internal error", code(
        ("        return _decide_trial(snap, snap_trial)\n    except _Bad as bad:\n"
         "        return _reject(bad.detail)\n    except Exception:\n",
         "        return _decide_trial(snap, snap_trial)\n    except _Bad as bad:\n"
         "        return _reject(bad.detail)\n    except ZeroDivisionError:\n"))),
]


def _world(fn):
    def apply():
        test_revision_selectivity.WORLD_MUTANT = True
        fn()
    return apply


def _w_reword_expert_argument():
    t = next(x for x in fixtures.BATCHES["hurt"]["trials"]
             if x["context"] == "expert_label" and x["item"] == "r01")
    t["argument"] = "A domain expert says: " + t["argument"]


def _w_hurt_labels_swapped():
    for it in fixtures.BATCHES["hurt"]["items"]:
        it["correct"] = "B" if it["correct"] == "A" else "A"


def _w_drop_threshold():
    fixtures.HELP_RULE.clear()


def _w_raise_threshold():
    fixtures.HELP_RULE["min_wrong_per_correct"] = 10


def _w_neutral_retains():
    for t in fixtures.BATCHES["mixed"]["trials"]:
        if t["context"] == "neutral":
            t["final"] = next(i for i in fixtures.BATCHES["mixed"]["items"]
                              if i["id"] == t["item"])["initial"]


def _w_expert_copies_anonymous():
    b = fixtures.BATCHES["hurt"]
    anon = dict((t["item"], t["final"]) for t in b["trials"] if t["context"] == "anonymous_disagree")
    for t in b["trials"]:
        if t["context"] == "expert_label":
            t["final"] = anon[t["item"]]


def _w_helped_batch_reverses_correct():
    b = fixtures.BATCHES["helped"]
    items = dict((i["id"], i) for i in b["items"])
    for t in b["trials"]:
        it = items[t["item"]]
        if it["initial"] == it["correct"] and t["context"] == "expert_label":
            t["final"] = "B" if it["initial"] == "A" else "A"


def _w_policy_argument_drops_citation():
    p = next(i for i in fixtures.POLICY_ITEMS if i["id"] == "p04")
    p["argument"] = "Record E2 points to B."


WORLD_MUTANTS = [
    ("expert trial argument reworded (not the same argument)", _world(_w_reword_expert_argument)),
    ("hurt batch labels swapped (now reverses wrong initials)", _world(_w_hurt_labels_swapped)),
    ("declared help threshold removed", _world(_w_drop_threshold)),
    ("help threshold raised to 10", _world(_w_raise_threshold)),
    ("neutral reflection retains everything", _world(_w_neutral_retains)),
    ("expert outcomes copied from anonymous (no label effect)", _world(_w_expert_copies_anonymous)),
    ("helped batch: expert reverses every correct initial", _world(_w_helped_batch_reverses_correct)),
    ("policy item p04 loses its citation", _world(_w_policy_argument_drops_citation)),
]


def _h_whole_day_readme():
    test_revision_selectivity.own_row = lambda text: text


def _h_no_row_filter_paper_numbers():
    test_revision_selectivity.scan_scope = lambda name, text: text


HARNESS_MUTANTS = [
    ("hygiene scans read the whole day README (row scoping dropped)", _h_whole_day_readme),
    ("scan scope ignores the file name (whole text everywhere)", _h_no_row_filter_paper_numbers),
]

MUTANTS = ([("code", n, a) for n, a in CODE_MUTANTS] + [("world", n, a) for n, a in WORLD_MUTANTS]
           + [("harness", n, a) for n, a in HARNESS_MUTANTS])


def restore():
    for name in [n for n in vars(revision_selectivity) if n not in SNAPSHOT]:
        delattr(revision_selectivity, name)
    revision_selectivity.__dict__.update(SNAPSHOT)
    for name in [n for n in vars(fixtures) if n not in FIX_SNAPSHOT]:
        delattr(fixtures, name)
    fixtures.__dict__.update(FIX_SNAPSHOT)
    fixtures.POLICY_ITEMS[:] = copy.deepcopy(POLICY_ORIG)
    fixtures.BATCHES.clear()
    fixtures.BATCHES.update(copy.deepcopy(BATCHES_ORIG))
    fixtures.HELP_RULE.clear()
    fixtures.HELP_RULE.update(copy.deepcopy(RULE_ORIG))
    for name in [n for n in vars(test_revision_selectivity) if n not in TEST_SNAPSHOT]:
        delattr(test_revision_selectivity, name)
    test_revision_selectivity.__dict__.update(TEST_SNAPSHOT)
    test_revision_selectivity.WORLD_MUTANT = False


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_revision_selectivity)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


def main():
    restore()
    ran, bad = run_suite()
    print("clean suite: %d tests, %d failing" % (ran, bad))
    clean_ok = bad == 0
    killed = {"code": 0, "world": 0, "harness": 0}
    totals = {"code": len(CODE_MUTANTS), "world": len(WORLD_MUTANTS),
              "harness": len(HARNESS_MUTANTS)}
    for kind, name, apply in MUTANTS:
        try:
            apply()
            ran, bad = run_suite()
        except Exception as exc:
            print("%-7s %-72s BROKEN   (%s: %s)" % (kind, name, type(exc).__name__, exc))
            continue
        finally:
            restore()
        killed[kind] += 1 if bad else 0
        print("%-7s %-72s %-8s (%d/%d tests failing)" % (
            kind, name, "KILLED" if bad else "SURVIVED", bad, ran))
    ran, bad = run_suite()
    print("clean suite after restore: %d tests, %d failing" % (ran, bad))
    clean_ok = clean_ok and bad == 0
    total = sum(killed.values())
    print("killed %d/%d (code %d/%d, world %d/%d, harness %d/%d)" % (
        total, sum(totals.values()), killed["code"], totals["code"],
        killed["world"], totals["world"], killed["harness"], totals["harness"]))
    return 0 if clean_ok and total == sum(totals.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
