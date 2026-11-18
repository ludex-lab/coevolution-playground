"""Mutation self-check for mb-memory-preview-rules (stdlib only).

Each mutant replaces one exact source fragment (which must occur exactly once) in a copy of this
folder, then runs the unittest suite with the same Python interpreter. A mutant is killed when the
suite fails. Run: python3 -B mutants.py   (exit 0 only when every mutant is killed)
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
COPY = ("preview_rules.py", "test_preview_rules.py", "demo.py", "fixtures")
M = "preview_rules.py"

MUTANTS = [
    # semantics of a rule
    ("semantics", "    if use[\"audience\"] != \"self\":\n        return False", "    if False:\n        return False"),
    ("semantics", "    if kinds == \"preference_only\" and event[\"kind\"] != \"preference\":", "    if kinds == \"preference_only\" and False:"),
    ("semantics", "    if kinds == \"one_off_only\" and event[\"kind\"] != \"one_off\":", "    if False:"),
    ("semantics", "        return use[\"task\"] == event[\"origin_task\"]", "        return True"),
    ("semantics", "        return fx[\"tasks\"][use[\"task\"]] == fx[\"tasks\"][event[\"origin_task\"]]", "        return use[\"task\"] == event[\"origin_task\"]"),
    ("semantics", "    return scope == \"any_task\"", "    return False"),
    ("semantics", "    if scope == \"same_task\":", "    if scope == \"same_topic\":"),
    ("semantics", "    return use[\"task\"] != fx[\"events\"][use[\"event\"]][\"origin_task\"]", "    return True"),
    # enumeration
    ("enumerate", "    return [r for r in fx[\"rules\"] if permits(fx, r, p) and not permits(fx, r, b)]", "    return [r for r in fx[\"rules\"] if permits(fx, r, p)]"),
    ("enumerate", "    return [r for r in fx[\"rules\"] if permits(fx, r, p) and not permits(fx, r, b)]", "    return [r for r in fx[\"rules\"] if not permits(fx, r, b)]"),
    ("enumerate", "    return [r for r in fx[\"rules\"] if permits(fx, r, p) and not permits(fx, r, b)]", "    return [r for r in fx[\"rules\"] if permits(fx, r, p) or not permits(fx, r, b)]"),
    ("enumerate", "    rules = tuple((s, k) for s in scopes for k in kinds)", "    rules = tuple((s, k) for k in kinds for s in scopes)"),
    ("enumerate", "    rules = tuple((s, k) for s in scopes for k in kinds)", "    rules = tuple((s, k) for s in scopes for k in kinds[:-1])"),
    ("enumerate", "    no = [u[\"id\"] for u in fx[\"uses\"] if not permits(fx, fx[\"intended\"], u)]", "    no = [u[\"id\"] for u in fx[\"uses\"] if not permits(fx, fx[\"intended\"], u) and u[\"audience\"] == \"self\"]"),
    ("enumerate", "    return [u[\"id\"] for u in fx[\"uses\"] if not any(permits(fx, r, u) for r in fx[\"rules\"])]", "    return [u[\"id\"] for u in fx[\"uses\"] if not permits(fx, fx[\"intended\"], u)]"),
    ("verdict", "    if chosen not in rules:\n        return \"CONFLICT\"", "    if not rules:\n        return \"CONFLICT\""),
    ("verdict", "    if len(rules) == 1:", "    if len(rules) <= 2:"),
    ("probes", "    return [r for r in rules if all(permits(fx, r, _use(fx, u)) == want[u] for u in uids)]", "    return [r for r in rules if any(permits(fx, r, _use(fx, u)) == want[u] for u in uids)]"),
    ("probes", "\"block\": no, \"separates\": bool(yes) and bool(no)})", "\"block\": no, \"separates\": bool(yes)})"),
    ("probes", "        if use[\"id\"] in exclude:\n            continue", "        if False:\n            continue"),
    ("probes", "    for size in range(1, len(ids) + 1):", "    for size in range(2, len(ids) + 1):"),
    ("probes", "                 if consistent(fx, fx[\"rules\"], combo) == [fx[\"intended\"]]]", "                 if fx[\"intended\"] in consistent(fx, fx[\"rules\"], combo)]"),
    ("probes", "    return [g for g in groups.values() if len(g) > 1]", "    return [g for g in groups.values() if len(g) > 0]"),
    ("probes", "    for scope, _ in rules:\n        if scope not in out:", "    for scope, _ in rules:\n        if True:"),
    # validation: exact types, keys, values
    ("validation", "    if type(value) is not dict:", "    if not isinstance(value, dict):"),
    ("validation", "        if type(key) is not str:", "        if not isinstance(key, str):"),
    ("validation", "    unknown = sorted(set(value) - set(keys))\n    if unknown:", "    unknown = sorted(set(value) - set(keys))\n    if False:"),
    ("validation", "    missing = [k for k in keys if k not in value]\n    if missing:", "    missing = [k for k in keys if k not in value]\n    if False:"),
    ("validation", "    if type(value) is not list:", "    if not isinstance(value, (list, tuple)):"),
    ("validation", "    if not value:\n        raise FixtureError(\"empty_list\"", "    if False:\n        raise FixtureError(\"empty_list\""),
    ("validation", "    if ID_RE.fullmatch(value) is None:", "    if ID_RE.match(value) is None:"),
    ("validation", "ID_RE = re.compile(r\"[a-z][a-z0-9_]{0,31}\", re.ASCII)", "ID_RE = re.compile(r\"[a-z][a-z0-9_]{0,32}\", re.ASCII)"),
    ("validation", "ID_RE = re.compile(r\"[a-z][a-z0-9_]{0,31}\", re.ASCII)", "ID_RE = re.compile(r\"\\w+\")"),
    ("validation", "    if type(value) is not str:\n        raise FixtureError(\"wrong_type\", \"%s must be a str\" % where)\n    if value not in options:", "    if not isinstance(value, str):\n        raise FixtureError(\"wrong_type\", \"%s must be a str\" % where)\n    if value not in options:"),
    ("validation", "    if not value.strip() or value != value.strip() or len(value) > MAX_TEXT:", "    if not value.strip() or len(value) > MAX_TEXT:"),
    ("validation", "    if not value.strip() or value != value.strip() or len(value) > MAX_TEXT:", "    if not value.strip() or value != value.strip():"),
    ("validation", "MAX_TEXT = 200", "MAX_TEXT = 201"),
    ("validation", "    if unicodedata.normalize(\"NFC\", value) != value:", "    if False:"),
    ("validation", "BAD_TEXT_CATEGORIES = (\"Cc\", \"Cf\", \"Cs\", \"Co\", \"Cn\", \"Zl\", \"Zp\")", "BAD_TEXT_CATEGORIES = (\"Cc\", \"Cs\", \"Co\", \"Cn\", \"Zl\", \"Zp\")"),
    ("validation", "BAD_TEXT_CATEGORIES = (\"Cc\", \"Cf\", \"Cs\", \"Co\", \"Cn\", \"Zl\", \"Zp\")", "BAD_TEXT_CATEGORIES = (\"Cf\", \"Cs\", \"Co\", \"Cn\", \"Zl\", \"Zp\")"),
    ("validation", "BAD_TEXT_CATEGORIES = (\"Cc\", \"Cf\", \"Cs\", \"Co\", \"Cn\", \"Zl\", \"Zp\")", "BAD_TEXT_CATEGORIES = (\"Cc\", \"Cf\", \"Cs\", \"Cn\", \"Zl\", \"Zp\")"),
    ("validation", "BAD_TEXT_CATEGORIES = (\"Cc\", \"Cf\", \"Cs\", \"Co\", \"Cn\", \"Zl\", \"Zp\")", "BAD_TEXT_CATEGORIES = (\"Cc\", \"Cf\", \"Cs\", \"Co\", \"Zl\", \"Zp\")"),
    ("validation", "BAD_TEXT_CATEGORIES = (\"Cc\", \"Cf\", \"Cs\", \"Co\", \"Cn\", \"Zl\", \"Zp\")", "BAD_TEXT_CATEGORIES = (\"Cc\", \"Cf\", \"Cs\", \"Co\", \"Cn\", \"Zp\")"),
    ("validation", "    if type(version) is not int or version != FIXTURE_VERSION:", "    if version != FIXTURE_VERSION:"),
    ("validation", "    if type(version) is not int or version != FIXTURE_VERSION:", "    if type(version) is not int:"),
    ("validation", "        if scope in scopes:\n", "        if False:\n"),
    ("validation", "        if kind in kinds:\n", "        if False:\n"),
    ("validation", "    if value in seen:", "    if False:"),
    ("validation", "        if uid in use_by_id:", "        if False:"),
    ("validation", "        if origin not in tasks:", "        if False:"),
    ("validation", "        if event not in events:", "        if False:"),
    ("validation", "        if task not in tasks:", "        if False:"),
    ("validation", "        if triple in triples:", "        if False:"),
    ("validation", "    if intended not in rules:", "    if False:"),
    ("validation", "            if uid not in use_by_id:", "            if False:"),
    ("validation", "        if permitted == blocked:", "        if False:"),
    ("validation", "        if not permits(fx, intended, use_by_id[permitted]) or permits(fx, intended, use_by_id[blocked]):", "        if permits(fx, intended, use_by_id[blocked]):"),
    ("validation", "        if not permits(fx, intended, use_by_id[permitted]) or permits(fx, intended, use_by_id[blocked]):", "        if not permits(fx, intended, use_by_id[permitted]):"),
    ("validation", "    if type(uid) is not str or uid not in fx[\"use_by_id\"]:", "    if uid not in fx[\"use_by_id\"]:"),
    ("snapshot", "        use = {\"id\": uid, \"event\": event, \"task\": task, \"audience\": audience,\n               \"text\": _text(row[\"text\"], where + \".text\")}", "        use = row\n        _text(row[\"text\"], where + \".text\")"),
    ("snapshot", "        events[eid] = {\"kind\": _choice(row[\"kind\"], EVENT_KINDS, where + \".kind\"),\n                       \"origin_task\": origin, \"text\": _text(row[\"text\"], where + \".text\")}", "        _choice(row[\"kind\"], EVENT_KINDS, where + \".kind\")\n        _text(row[\"text\"], where + \".text\")\n        events[eid] = row"),
    # strict JSON
    ("json", "        if key in out:", "        if False:"),
    ("json", "parse_constant=_reject_constant, parse_float=_reject_float)", "parse_float=_reject_float)"),
    ("json", "parse_constant=_reject_constant, parse_float=_reject_float)", "parse_constant=_reject_constant)"),
    ("json", "    if text.startswith(\"\\ufeff\"):", "    if False:"),
    ("json", "    except (ValueError, RecursionError) as exc:", "    except ValueError as exc:"),
    ("json", "    if type(text) is not str:\n        raise FixtureError(\"fixture_unreadable\"", "    if not isinstance(text, (str, bytes)):\n        raise FixtureError(\"fixture_unreadable\""),
    ("json", "        text = data.decode(\"utf-8\")", "        text = data.decode(\"latin-1\")"),
    # report and CLI
    ("report", "                 % (sum(1 for _, b, _c in pairs if b in vac), len(pairs)))", "                 % (sum(1 for _, b, _c in pairs if b not in vac), len(pairs)))"),
    ("report", "        together = [r for r in together if r in comp]", "        together = comp"),
    ("report", "        sizes[len(c)] = sizes.get(len(c), 0) + 1", "        sizes[len(c)] = 1"),
    ("report", "        lines.append(\"smallest probe set identifying the intended rule: none\")", "        lines.append(\"smallest probe set identifying the intended rule: 0 uses\")"),
    ("cli", "            if arg in opts or i + 1 >= len(argv):", "            if i + 1 >= len(argv):"),
    ("cli", "        if arg.startswith(\"-\") or path is not None:", "        if path is not None:"),
    ("cli", "        if arg.startswith(\"-\") or path is not None:", "        if arg.startswith(\"-\"):"),
    ("cli", "    if path is None or len(opts) == 1:", "    if path is None:"),
    ("cli", "    if not argv:\n        raise FixtureError(\"usage\", USAGE)", "    if not argv:\n        raise FixtureError(\"empty\", USAGE)"),
    ("cli", "        return 2\n", "        return 1\n"),
    ("cli", "        err.write(\"DENY %s: %s\\n\" % (exc.code, exc.detail))", "        out.write(\"DENY %s: %s\\n\" % (exc.code, exc.detail))"),
]


def run_suite(folder):
    res = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q"], cwd=folder,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return res.returncode


def main():
    base = tempfile.mkdtemp(prefix="mb-preview-mutants-")
    try:
        clean = os.path.join(base, "clean")
        os.mkdir(clean)
        for name in COPY:
            src = os.path.join(HERE, name)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(clean, name))
            else:
                shutil.copy2(src, os.path.join(clean, name))
        if run_suite(clean) != 0:
            print("baseline suite fails; no mutants run")
            return 1
        with open(os.path.join(clean, M), encoding="utf-8") as handle:
            source = handle.read()
        survivors = 0
        for idx, (group, old, new) in enumerate(MUTANTS, 1):
            if source.count(old) != 1:
                print("mutant %02d %-10s fragment occurs %d times" % (idx, group, source.count(old)))
                return 1
            folder = os.path.join(base, "m%02d" % idx)
            shutil.copytree(clean, folder)
            with open(os.path.join(folder, M), "w", encoding="utf-8") as handle:
                handle.write(source.replace(old, new))
            killed = run_suite(folder) != 0
            survivors += 0 if killed else 1
            print("mutant %02d %-10s %s" % (idx, group, "killed" if killed else "SURVIVED"))
            shutil.rmtree(folder)
        print("killed %d/%d" % (len(MUTANTS) - survivors, len(MUTANTS)))
        return 0 if survivors == 0 else 1
    finally:
        shutil.rmtree(base)


if __name__ == "__main__":
    sys.exit(main())
