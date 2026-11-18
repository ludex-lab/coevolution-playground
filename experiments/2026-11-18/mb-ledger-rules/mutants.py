"""Mutation self-check for mb-ledger-rules (stdlib only).

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
COPY = ("ledger.py", "test_ledger.py", "demo.py", "mutants.py", "README.md", "evidence.json", "fixtures")
M = "ledger.py"

MUTANTS = [
    # current-value and trust rules
    ("rules", "    return fact[\"start\"] <= day and (fact[\"end\"] is None or day <= fact[\"end\"])", "    return fact[\"start\"] <= day"),
    ("rules", "    return fact[\"start\"] <= day and (fact[\"end\"] is None or day <= fact[\"end\"])", "    return fact[\"start\"] <= day and (fact[\"end\"] is None or day < fact[\"end\"])"),
    ("rules", "    return fact[\"start\"] <= day and (fact[\"end\"] is None or day <= fact[\"end\"])", "    return fact[\"start\"] < day and (fact[\"end\"] is None or day <= fact[\"end\"])"),
    ("rules", "    return fact[\"start\"] <= day and (fact[\"end\"] is None or day <= fact[\"end\"])", "    return fact[\"end\"] is None or day <= fact[\"end\"]"),
    ("rules", "    return (TRUST[fact[\"trust\"]], fact[\"start\"], fact[\"learned\"])", "    return (fact[\"start\"], TRUST[fact[\"trust\"]], fact[\"learned\"])"),
    ("rules", "    return (TRUST[fact[\"trust\"]], fact[\"start\"], fact[\"learned\"])", "    return (-TRUST[fact[\"trust\"]], fact[\"start\"], fact[\"learned\"])"),
    ("rules", "    return (TRUST[fact[\"trust\"]], fact[\"start\"], fact[\"learned\"])", "    return (TRUST[fact[\"trust\"]], -fact[\"start\"], fact[\"learned\"])"),
    ("rules", "    return (TRUST[fact[\"trust\"]], fact[\"start\"], fact[\"learned\"])", "    return (TRUST[fact[\"trust\"]], fact[\"start\"], 0)"),
    ("rules", "    return (TRUST[fact[\"trust\"]], fact[\"start\"], fact[\"learned\"])", "    return (TRUST[fact[\"trust\"]],)"),
    ("rules", "TRUST = {\"high\": 3, \"medium\": 2, \"low\": 1}", "TRUST = {\"high\": 3, \"medium\": 1, \"low\": 1}"),
    ("rules", "TRUST = {\"high\": 3, \"medium\": 2, \"low\": 1}", "TRUST = {\"high\": 3, \"medium\": 2, \"low\": 1, \"certain\": 4}"),
    ("rules", "        best = max(rank(f) for f in live)", "        best = min(rank(f) for f in live)"),
    ("rules", "        if len({f[\"value\"].lower() for f in top}) > 1:", "        if len({f[\"value\"] for f in top}) > 100:"),
    ("rules", "        return \"current\", top[:1]", "        return \"current\", top"),
    ("rules", "                if f[\"subject\"] == subject and f[\"attribute\"] == attribute and in_period(f, day)]", "                if f[\"subject\"] == subject and in_period(f, day)]"),
    ("rules", "                if f[\"subject\"] == subject and f[\"attribute\"] == attribute and in_period(f, day)]", "                if f[\"attribute\"] == attribute and in_period(f, day)]"),
    ("rules", "    return a[\"start\"] <= b_end and b[\"start\"] <= a_end", "    return a[\"start\"] <= b_end"),
    ("rules", "    return a[\"start\"] <= b_end and b[\"start\"] <= a_end", "    return a[\"start\"] < b_end and b[\"start\"] <= a_end"),
    ("rules", "    return a[\"start\"] <= b_end and b[\"start\"] <= a_end", "    return True"),
    # deletion
    ("delete", "        if not hits:\n            raise Deny(\"no_match\"", "        if False:\n            raise Deny(\"no_match\""),
    ("delete", "        if len(hits) > 1:", "        if len(hits) > 2:"),
    ("delete", "                if (f[\"subject\"], f[\"attribute\"], f[\"source\"]) == (req[\"subject\"], req[\"attribute\"], req[\"source\"])", "                if (f[\"subject\"], f[\"attribute\"]) == (req[\"subject\"], req[\"attribute\"])"),
    ("delete", "        if value in req[\"text\"].lower():", "        if value in req[\"text\"]:"),
    ("delete", "        if value in req[\"text\"].lower():", "        if False:"),
    ("delete", "        if any(o[\"value\"].lower() == value for o in self.facts.values() if o is not fact):", "        if False:"),
    ("delete", "        del self.facts[fact[\"id\"]]\n", "        pass\n"),
    ("delete", "        pattern = re.compile(re.escape(fact[\"value\"]), re.IGNORECASE)", "        pattern = re.compile(re.escape(fact[\"value\"]))"),
    ("delete", "            turn[\"text\"] = pattern.sub(REMOVED, turn[\"text\"])", "            pass"),
    ("delete", "        self.turns[turn[\"id\"]] = dict(turn)", "        self.turns[turn[\"id\"]] = turn"),
    ("delete", "            self.facts[fact[\"id\"]] = dict(fact, learned=turn[\"day\"])", "            self.facts[fact[\"id\"]] = dict(fact, learned=0)"),
    ("delete", "        self.tombstones.append({\"id\": req[\"id\"], \"subject\": req[\"subject\"],", "        self.tombstones.append({\"id\": req[\"id\"], \"value\": fact[\"value\"], \"subject\": req[\"subject\"],"),
    # bundles and baseline
    ("bundle", "        if status == \"none\" and probe[\"fallback\"]:", "        if status == \"none\":"),
    ("bundle", "        if status == \"none\" and probe[\"fallback\"]:", "        if probe[\"fallback\"]:"),
    ("bundle", "                if t[\"day\"] <= probe[\"day\"] and matches_terms(t[\"text\"], probe[\"terms\"])]\n        return {\"probe\": probe[\"id\"], \"mode\": \"ledger\"", "                if matches_terms(t[\"text\"], probe[\"terms\"])]\n        return {\"probe\": probe[\"id\"], \"mode\": \"ledger\""),
    ("bundle", "                self.turns.values(), key=lambda t: (t[\"day\"], t[\"id\"]))", "                self.turns.values(), key=lambda t: t[\"id\"], reverse=True)"),
    ("bundle", "    return any(t.lower() in low for t in terms)", "    return all(t.lower() in low for t in terms) and False"),
    ("bundle", "    low = text.lower()\n", "    low = text\n"),
    ("bundle", "    turns = [{\"id\": t[\"id\"], \"text\": t[\"text\"]} for t in sorted(fx[\"turns\"], key=lambda t: (t[\"day\"], t[\"id\"]))\n             if t[\"day\"] <= probe[\"day\"] and", "    turns = [{\"id\": t[\"id\"], \"text\": t[\"text\"]} for t in sorted(fx[\"turns\"], key=lambda t: (t[\"day\"], t[\"id\"]))\n             if"),
    ("bundle", "    return json.dumps(bundle, sort_keys=True, ensure_ascii=False)", "    return json.dumps(bundle[\"facts\"], sort_keys=True, ensure_ascii=False)"),
    ("bundle", "    text = serialize(bundle).lower()\n    return sorted(v for v in values if v.lower() in text)", "    text = serialize(bundle)\n    return sorted(v for v in values if v in text)"),
    ("bundle", "                   and f[\"end\"] < probe[\"day\"]})", "                   and f[\"end\"] <= probe[\"day\"]})"),
    # timeline
    ("timeline", "(d[\"day\"], 1, d[\"id\"], \"delete\", d)", "(d[\"day\"], 3, d[\"id\"], \"delete\", d)"),
    ("timeline", "(t[\"day\"], 0, t[\"id\"], \"turn\", t)", "(t[\"day\"], 3, t[\"id\"], \"turn\", t)"),
    ("timeline", "            ledger.ingest(item, [f for f in fx[\"facts\"] if f[\"turn\"] == item[\"id\"]])", "            ledger.ingest(item, [])"),
    ("timeline", "            deleted.append(ledger.delete(item))", "            ledger.delete(item)"),
    ("timeline", "    ledger, deleted, rows = Ledger(), [], []", "    ledger, deleted, rows = Ledger(), [\"unrelated\"], []"),
    # validation
    ("validate", "        if type(row[\"fallback\"]) is not bool:", "        if row[\"fallback\"] not in (True, False):"),
    ("validate", "        if end < start:", "        if end < start - 1:"),
    ("validate", "    if ID_RE.fullmatch(value) is None:", "    if ID_RE.match(value) is None:"),
    ("validate", "    if value in seen:\n        raise Deny(\"duplicate_id\"", "    if False:\n        raise Deny(\"duplicate_id\""),
    ("validate", "        if type(row[\"trust\"]) is not str or row[\"trust\"] not in TRUST:", "        if type(row[\"trust\"]) is not str:"),
    ("validate", "        if value.lower() not in turns[turn][\"text\"].lower():", "        if False:"),
    ("validate", "        if turn not in turns:", "        if False:"),
    ("validate", "    if type(value) is not int:", "    if not isinstance(value, int):"),
    ("validate", "    if not lo <= value <= MAX_DAY:", "    if not lo <= value:"),
    ("validate", "    if not value.strip() or value != value.strip() or len(value) > MAX_TEXT:", "    if not value.strip() or len(value) > MAX_TEXT:"),
    ("validate", "    if any(unicodedata.category(ch).startswith(\"C\") for ch in value):", "    if False:"),
    ("validate", "    unknown = sorted(set(value) - set(keys))\n    if unknown:", "    unknown = []\n    if unknown:"),
    ("validate", "    missing = [k for k in keys if k not in value]\n    if missing:", "    missing = []\n    if missing:"),
    ("validate", "    if not value and not empty_ok:", "    if False:"),
    ("validate", "    if type(root[\"fixture_version\"]) is not int or root[\"fixture_version\"] != FIXTURE_VERSION:", "    if root[\"fixture_version\"] != FIXTURE_VERSION:"),
    ("validate", "    if type(value) is not dict:", "    if False:"),
    # strict JSON and CLI
    ("json", "        if key in out:", "        if False:"),
    ("json", "parse_constant=_reject_constant, parse_float=_reject_float)", "parse_float=_reject_float)"),
    ("json", "parse_constant=_reject_constant, parse_float=_reject_float)", "parse_constant=_reject_constant)"),
    ("json", "    if text.startswith(\"\\ufeff\"):", "    if False:"),
    ("json", "    except (ValueError, RecursionError) as exc:", "    except ValueError as exc:"),
    ("json", "        text = data.decode(\"utf-8\")", "        text = data.decode(\"latin-1\")"),
    ("cli", "        if len(argv) != 1 or argv[0].startswith(\"-\"):", "        if len(argv) != 1:"),
    ("cli", "        if len(argv) != 1 or argv[0].startswith(\"-\"):", "        if len(argv) < 1:"),
    ("cli", "        return 2\n", "        return 1\n"),
    ("cli", "        err.write(\"DENY %s: %s\\n\" % (exc.code, exc.detail))", "        out.write(\"DENY %s: %s\\n\" % (exc.code, exc.detail))"),
]


def run_suite(folder):
    res = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q", "test_ledger"], cwd=folder,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return res.returncode


def main():
    base = tempfile.mkdtemp(prefix="mb-ledger-mutants-")
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
                print("mutant %02d %-9s fragment occurs %d times" % (idx, group, source.count(old)))
                return 1
            folder = os.path.join(base, "m%02d" % idx)
            shutil.copytree(clean, folder)
            with open(os.path.join(folder, M), "w", encoding="utf-8") as handle:
                handle.write(source.replace(old, new))
            killed = run_suite(folder) != 0
            survivors += 0 if killed else 1
            print("mutant %02d %-9s %s" % (idx, group, "killed" if killed else "SURVIVED"))
            shutil.rmtree(folder)
        total = len(MUTANTS)
        print("killed %d/%d" % (total - survivors, total))
        return 0 if survivors == 0 else 1
    finally:
        shutil.rmtree(base)


if __name__ == "__main__":
    sys.exit(main())
