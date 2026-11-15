"""Mutation check for w21-advice-cooldown. Run: python3 -B mutants.py

Each mutant replaces one exact piece of source text in one file, writes
the result into a temporary copy of this directory (inside a temporary
experiments/2026-11-12/ layout, with the day README copied to the day
folder as README.md), and runs fixtures.py and the unittest suite there
with the paper-source check skipped (W21AC_SOURCES unset). A mutant is
killed when either run fails. The day README is read like the tests read
it: ../README.md in the repo layout, else _day/README.md in a flat draft
copy; it works from either. The temporary directory is removed
at the end. This harness is the only file in the folder that starts a
process.

Two lists, reported separately:
  code   mutants of advice_cooldown.py: cooldown skipped, off by one or
         keyed wrongly, budget skipped or an empty budget that sends,
         contract checks dropped, a missing contract treated as relevant,
         expiry skipped, sending, or sending at the deadline, on_expiry
         optional, isinstance in place
         of exact type, dropped validator branches, no try/except, a
         runtime import or a sleep.
  world  mutants of the test world (fixtures.py, test file,
         paper_evidence.json, the day README): fixtures that no longer
         have the shape their name claims, wrong expected labels, edited
         quotes or status, and a day README with a conflict marker, a paper
         figure, a second footer or a dropped scope phrase.

Stdlib only. Exit status 0 when every non-equivalent mutant is killed and
every anchor matches exactly once.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = "advice_cooldown.py"
FIX = "fixtures.py"
TEST = "test_advice_cooldown.py"
EVID = "paper_evidence.json"
SLUG = "w21-advice-cooldown"
DAYF = "_day/README.md"   # label for the day README; copied to the day folder as README.md
DAY = "2026-11-12"
DAY_HEADER = "# experiments/" + DAY + "\n"


def _day_src():
    """The day README, resolved like the tests: ../README.md in the repo
    layout (parent folder is 2026-11-12 and the file opens with the day
    header), else _day/README.md in a flat draft copy. None when neither
    exists."""
    parent = os.path.dirname(HERE)
    repo = os.path.join(parent, "README.md")
    if os.path.basename(parent) == DAY and os.path.isfile(repo):
        with open(repo, encoding="utf-8") as f:
            if f.read().startswith(DAY_HEADER):
                return repo
    flat = os.path.join(HERE, "_day", "README.md")
    return flat if os.path.isfile(flat) else None


def _src(fname):
    return _day_src() if fname == DAYF else os.path.join(HERE, fname)

# Mutants that cannot change any observable behaviour. Each is explained.
EQUIVALENT = set()
EQUIVALENT_WORLD = set()

M = [
    # cooldown
    ('cooldown_skipped',
     '                if last is not None and now - last < item["cooldown"]:\n',
     '                if False:\n'),
    ('cooldown_off_by_one',
     'now - last < item["cooldown"]',
     'now - last <= item["cooldown"]'),
    ('cooldown_any_id',
     '                last = last_sent.get(item["id"])\n',
     '                last = max(last_sent.values()) if last_sent else None\n'),
    ('cooldown_tool_fallback',
     '                last = last_sent.get(item["id"])\n',
     '                last = last_sent.get(item["id"], last_sent.get(item["tool"]))\n'),
    ('cooldown_earliest_send',
     '        if entry["at"] >= last_sent.get(entry["advice_id"], -1):\n',
     '        if entry["advice_id"] not in last_sent:\n'),
    # budget
    ('budget_skipped',
     '                elif item["tokens"] > remaining:\n',
     '                elif False:\n'),
    ('budget_off_by_one',
     'item["tokens"] > remaining',
     'item["tokens"] >= remaining'),
    ('budget_ignores_history',
     '    spent = sum(entry["tokens"] for entry in history)\n',
     '    spent = 0\n'),
    ('empty_budget_dispatches',
     '                elif item["tokens"] > remaining:\n',
     '                elif item["tokens"] > remaining and remaining > 0:\n'),
    # contracts
    ('required_unchecked',
     '        if name not in args:\n            return REQUIRED_ARG_MISSING\n',
     ''),
    ('options_unchecked',
     '        if name in args and args[name] not in contract["options"][name]:\n',
     '        if False:\n'),
    ('contract_on_planned_args_only',
     '            merged.update(item["args"])\n',
     ''),
    ('advice_args_ignored_for_options',
     '            merged = dict(state["args"])\n            merged.update(item["args"])\n',
     '            merged = dict(item["args"])\n            merged.update(state["args"])\n'),
    ('missing_contract_relevant',
     '        if contract is None:\n            outcome = NO_CONTRACT\n',
     '        if contract is None:\n            contract = {"required": [], "options": {}}\n            outcome = SENT\n'),
    ('violation_sends',
     '            outcome = check_contract(contract, merged)\n',
     '            outcome = None\n'),
    # shortlist
    ('shortlist_any_tool',
     '    if item["tool"] != state["tool"]:\n        return False\n',
     ''),
    ('shortlist_ignores_when_missing',
     '    return item["when_missing"] is None or item["when_missing"] not in state["args"]\n',
     '    return True\n'),
    ('first_failure_stops',
     '        if outcome == SENT:\n',
     '        if outcome != SENT:\n            break\n        if outcome == SENT:\n'),
    # pending / expiry
    ('expiry_skipped',
     '        if now >= pending["deadline"]:\n',
     '        if False:\n'),
    ('expiry_strict_after_deadline',
     'now >= pending["deadline"]',
     'now > pending["deadline"]'),
    ('expiry_only_without_advice',
     '        if now >= pending["deadline"]:\n',
     '        if now >= pending["deadline"] and not state["advice"]:\n'),
    ('expiry_sends_anyway',
     '            return _record(action, EXPIRED, None, 0, remaining, (), pending_id, action)\n',
     '            pass\n'),
    ('on_expiry_optional',
     '        if "on_expiry" not in pending:\n            return "pending decision declares a deadline without on_expiry"\n',
     '        if "on_expiry" not in pending:\n            return None\n'),
    ('on_expiry_any_str',
     '        if _canonical(pending["on_expiry"], ON_EXPIRY_VALUES) is None:\n',
     '        if "on_expiry" in pending and not _is_str(pending["on_expiry"]):\n'),
    ('on_expiry_caller_object',
     '        action = _canonical(pending["on_expiry"], ON_EXPIRY_VALUES)\n',
     '        action = pending["on_expiry"]\n'),
    # exact types and validation
    ('str_isinstance',
     '    return type(v) is str\n',
     '    return isinstance(v, str)\n'),
    ('int_isinstance',
     '    return type(v) is int\n',
     '    return isinstance(v, int)\n'),
    ('dict_isinstance',
     '    if type(mapping) is not dict:\n        return "not a mapping"\n',
     '    if not isinstance(mapping, dict):\n        return "not a mapping"\n'),
    ('unknown_fields',
     '        if _canonical(key, fields) is None:\n            return "unknown field"\n',
     ''),
    ('key_types_lookup',
     '        if _canonical(key, fields) is None:\n',
     '        if key not in fields:\n'),
    ('history_future',
     ' or entry["at"] > now:',
     ':'),
    ('history_future_by_one',
     'entry["at"] > now:',
     'entry["at"] > now + 1:'),
    ('history_not_list',
     '    if type(history) is not list:\n',
     '    if history is None:\n'),
    ('advice_not_list',
     '    if type(advice) is not list:\n',
     '    if advice is None:\n'),
    ('duplicate_ids',
     '        if item["id"] in ids:\n            return "duplicate advice id"\n',
     ''),
    ('tokens_zero',
     '    if not _is_int(item["tokens"]) or item["tokens"] <= 0:\n',
     '    if not _is_int(item["tokens"]) or item["tokens"] < 0:\n'),
    ('cooldown_zero',
     '    if not _is_int(item["cooldown"]) or item["cooldown"] <= 0:\n',
     '    if not _is_int(item["cooldown"]):\n'),
    ('budget_negative',
     '    if not _is_int(budget["limit"]) or budget["limit"] < 0:\n',
     '    if not _is_int(budget["limit"]):\n'),
    ('now_negative',
     '    if not _is_int(now) or now < 0:\n',
     '    if not _is_int(now):\n'),
    ('args_values_unchecked',
     ' or not _is_str(value[k]):',
     ':'),
    ('options_list_unchecked',
     ' or not _str_list(options[k]) or not options[k]:',
     ':'),
    ('pending_deadline_type',
     '        if not _is_int(pending["deadline"]) or pending["deadline"] < 0:\n',
     '        if pending["deadline"] is None:\n'),
    # never raise, runtime creep
    ('no_try',
     '    except Exception:\n',
     '    except ZeroDivisionError:\n'),
    ('runtime_import',
     'SEND = "send"\n',
     'import threading\nSEND = "send"\n'),
    ('poll_loop',
     '    reason = candidates[0][1] if candidates else NO_CANDIDATE\n',
     '    while False:\n        pass\n    reason = candidates[0][1] if candidates else NO_CANDIDATE\n'),
    ('scoring_helper',
     'def _shortlisted(item, state):\n',
     'def _score(item):\n    return 0\n\n\ndef _shortlisted(item, state):\n'),
]

W = [
    ('cooldown_case_out_of_cooldown', FIX,
     '                           budget(100), 2, (A.NO_SEND, A.IN_COOLDOWN, None)),\n',
     '                           budget(100), 3, (A.NO_SEND, A.IN_COOLDOWN, None)),\n'),
    ('after_cooldown_too_early', FIX,
     '                       budget(100), 3, (A.SEND, A.SENT, "sort_hint")),\n',
     '                       budget(100), 2, (A.SEND, A.SENT, "sort_hint")),\n'),
    ('required_case_complete', FIX,
     '    "required_arg_missing": (state("checkout", {"address": "home"}, [speed_hint()]), [], budget(100),\n',
     '    "required_arg_missing": (state("checkout", {"address": "home", "item_id": "i"}, [speed_hint()]), [], budget(100),\n'),
    ('bad_option_made_valid', FIX,
     '{"sort": "newest"}',
     '{"sort": "rating"}'),
    ('budget_short_enough', FIX,
     '    "budget_short": (state("search", SEARCH, [sort_hint()]), [], budget(30), 0,\n',
     '    "budget_short": (state("search", SEARCH, [sort_hint()]), [], budget(40), 0,\n'),
    ('pending_not_past', FIX,
     '                              {"id": "p1", "deadline": 5, "on_expiry": "HOLD"}), [], budget(100), 6,\n',
     '                              {"id": "p1", "deadline": 5, "on_expiry": "HOLD"}), [], budget(100), 4,\n'),
    ('pending_open_at_deadline', FIX,
     '                           {"id": "p1", "deadline": 5, "on_expiry": "DENY"}), [], budget(100), 4,\n',
     '                           {"id": "p1", "deadline": 5, "on_expiry": "DENY"}), [], budget(100), 5,\n'),
    ('ship_gets_contract', FIX,
     '    "checkout": {"required": ["item_id", "address"], "options": {"speed": ["standard", "express"]}},\n',
     '    "checkout": {"required": ["item_id", "address"], "options": {"speed": ["standard", "express"]}},\n'
     '    "ship": {"required": [], "options": {}},\n'),
    ('timeline_expect_wrong', FIX,
     '                   A.SENT, A.IN_COOLDOWN, A.IN_COOLDOWN, A.BUDGET_EXHAUSTED)\n',
     '                   A.SENT, A.IN_COOLDOWN, A.IN_COOLDOWN, A.SENT)\n'),
    ('timeline_budget_bigger', FIX,
     'TIMELINE_BUDGET = 120\n',
     'TIMELINE_BUDGET = 160\n'),
    ('sort_hint_cooldown_one', FIX,
     '    return advice("sort_hint", "search", "sort", {"sort": "price"}, 40, 3)\n',
     '    return advice("sort_hint", "search", "sort", {"sort": "price"}, 40, 1)\n'),
    ('fallback_order_swapped', FIX,
     '[bad_sort_hint(), sort_hint()]',
     '[sort_hint(), bad_sort_hint()]'),
    ('figure_list_thinned', TEST,
     '("4,", "987"), ',
     ''),
    ('fixtures_import_time', FIX,
     'import json\n',
     'import json\nimport time\n'),
    ('fixtures_sleep', FIX,
     '        reasons.append(rec["reason"])\n',
     '        reasons.append(rec["reason"])\n        json.sleep = None\n'),
    ('banned_digest_dropped', TEST,
     '    BANNED_DIGESTS = (\n        "',
     '    BANNED_DIGESTS = (\n        "0" + "'),
    ('quote_edited', EVID,
     'without prescribing complete task programs.',
     'without prescribing whole task programs.'),
    ('claims_status_flipped', EVID,
     '  "status": "UNVERIFIED",\n  "note"',
     '  "status": "VERIFIED",\n  "note"'),
    # the day README (experiments/2026-11-12/README.md)
    ('day_conflict_marker', DAYF,
     'Do not merge experiment PRs without Ork review.\n',
     '<' * 7 + ' HEAD\nDo not merge experiment PRs without Ork review.\n'),
    ('day_paper_figure', DAYF,
     'Do not merge experiment PRs without Ork review.\n',
     'Paper: ' + '1.7' + 'B scorer, ' + '29.8' + '% more.\n\nDo not merge experiment PRs without Ork review.\n'),
    ('day_footer_twice', DAYF,
     'Do not merge experiment PRs without Ork review.\n',
     'Do not merge experiment PRs without Ork review.\n\nDo not merge experiment PRs without Ork review.\n'),
    ('day_drops_no_classifier', DAYF,
     'not a runtime port, no classifier; ',
     ''),
]


def _copy_layout(tmp, name):
    d = os.path.join(tmp, name, "experiments", "2026-11-12", SLUG)
    os.makedirs(d)
    for f in os.listdir(HERE):
        p = os.path.join(HERE, f)
        if os.path.isfile(p) and not f.endswith(".pyc"):
            shutil.copy(p, d)
    shutil.copy(_day_src(), os.path.join(os.path.dirname(d), "README.md"))
    return d


def _dest(d, fname):
    if fname == DAYF:
        return os.path.join(os.path.dirname(d), "README.md")
    return os.path.join(d, fname)


def _passes(d):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("W21AC_SOURCES", None)
    a = subprocess.run([sys.executable, "-B", "fixtures.py"], cwd=d, capture_output=True, env=env)
    b = subprocess.run([sys.executable, "-B", "-m", "unittest", TEST], cwd=d,
                       capture_output=True, env=env)
    return a.returncode == 0 and b.returncode == 0


def _run(tmp, label, items, equivalent_names):
    killed, survivors, equivalent, bad_anchor = 0, [], [], []
    for k, (name, fname, old, new) in enumerate(items):
        with open(_src(fname), encoding="utf-8") as f:
            src = f.read()
        if src.count(old) != 1:
            bad_anchor.append(name)
            print("%-36s ANCHOR(%d)" % (name, src.count(old)))
            continue
        sub = "%s%03d" % (label, k)
        d = _copy_layout(tmp, sub)
        with open(_dest(d, fname), "w", encoding="utf-8") as f:
            f.write(src.replace(old, new, 1))
        survived = _passes(d)
        shutil.rmtree(os.path.join(tmp, sub))
        if not survived:
            killed += 1
            verdict = "killed"
        elif name in equivalent_names:
            equivalent.append(name)
            verdict = "survived (equivalent)"
        else:
            survivors.append(name)
            verdict = "SURVIVED"
        print("%-36s %s" % (name, verdict))
    print("summary %s: %d mutants; killed %d; equivalent %d %s; survivors %d %s; bad anchors %d %s" % (
        label, len(items), killed, len(equivalent), sorted(equivalent), len(survivors), survivors,
        len(bad_anchor), bad_anchor))
    return bool(survivors or bad_anchor)


def main():
    if _day_src() is None:
        print("baseline: FAIL (no day README at ../README.md or _day/README.md)")
        return 2
    tmp = tempfile.mkdtemp(prefix="w21ac-mutants-")
    try:
        base = _copy_layout(tmp, "base")
        if not _passes(base):
            print("baseline: FAIL (suite or fixtures fail on unmutated code)")
            return 2
        print("baseline: OK")
        print("-- code mutants (%s)" % TARGET)
        bad_code = _run(tmp, "code", [(n, TARGET, o, w) for n, o, w in M], EQUIVALENT)
        print("-- world mutants (%s, %s, %s, %s)" % (FIX, TEST, EVID, DAYF))
        bad_world = _run(tmp, "world", W, EQUIVALENT_WORLD)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if bad_code or bad_world else 0


if __name__ == "__main__":
    sys.exit(main())
