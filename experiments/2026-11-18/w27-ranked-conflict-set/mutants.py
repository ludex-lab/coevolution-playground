"""Mutation self-check for w27-ranked-conflict-set (stdlib only).

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
COPY = ("conflict_set.py", "test_conflict_set.py", "demo.py", "mutants.py", "README.md", "evidence.json", "fixtures")
M = "conflict_set.py"

MUTANTS = [
    # rank key
    ("rank", r'    return (-entry["score"], entry["id"])', r'    return (entry["score"], entry["id"])'),
    ("rank", r'    return (-entry["score"], entry["id"])', r'    return (-entry["score"],)'),
    ("rank", r'    return (-entry["score"], entry["id"])', r'    return (-entry["score"], entry["writer"])'),
    ("rank", r'    return (-entry["score"], entry["id"])', r'    return (-entry["score"], entry["poisoned"], entry["id"])'),
    ("rank", r'    return (-entry["score"], entry["id"])', r'    return (-entry["score"], entry["value"], entry["id"])'),
    ("rank", r'    return (-entry["score"], entry["id"])', r'    return (-entry["score"], [-ord(c) for c in entry["id"]])'),
    # store
    ("store", r'        return [e for e in self.snapshot() if e["field"] == field][:k]', r'        return [e for e in self.snapshot() if e["field"] == field][:k + 1]'),
    ("store", r'        return [e for e in self.snapshot() if e["field"] == field][:k]', r'        return [e for e in self.snapshot() if e["field"] == field][:max(k - 1, 1)]'),
    ("store", r'        return [e for e in self.snapshot() if e["field"] == field][:k]', r'        return [e for e in self.snapshot()][:k]'),
    ("store", r'        return [e for e in self.snapshot() if e["field"] == field][:k]', r'        return [e for e in self.snapshot() if e["field"] == field]'),
    ("store", r'        if entry["id"] in self._entries:', r'        if False:'),
    ("store", r'        self._entries[entry["id"]] = dict(entry)', r'        self._entries[entry["id"]] = entry'),
    ("store", r'        return [dict(e) for e in sorted(self._entries.values(), key=rank_key)]', r'        return [e for e in sorted(self._entries.values(), key=rank_key)]'),
    ("store", r'        return [dict(e) for e in sorted(self._entries.values(), key=rank_key)]', r'        return [dict(e) for e in self._entries.values()]'),
    # policies
    ("policy", r'    return retrieved[:1]', r'    return retrieved[:2]'),
    ("policy", r'    return retrieved[:1]', r'    return retrieved[-1:]'),
    ("policy", r'    return retrieved[:1]', r'    return retrieved'),
    ("policy", r'        if entry["value"] not in seen:', r'        if True:'),
    ("policy", r'        if entry["value"] not in seen:', r'        if entry["id"] not in seen:'),
    ("policy", r'            out.append(entry)', r'            pass'),
    ("policy", r'    for entry in retrieved:', r'    for entry in reversed(retrieved):'),
    ("policy", r'POLICIES = {"collapse": collapse, "surface": surface}', r'POLICIES = {"collapse": surface, "surface": surface}'),
    ("policy", r'POLICIES = {"collapse": collapse, "surface": surface}', r'POLICIES = {"collapse": collapse, "surface": collapse}'),
    # budget
    ("budget", r'    if len(retrieved) > k or len(view) > k:', r'    if len(retrieved) > k + 1 or len(view) > k + 1:'),
    ("budget", r'    if len(retrieved) > k or len(view) > k:', r'    if len(view) > k:'),
    ("budget", r'    if len(retrieved) > k or len(view) > k:', r'    if len(retrieved) > k:'),
    ("budget", r'    if any(e["id"] not in ids for e in view):', r'    if False:'),
    # fixed reader
    ("reader", r'        return {"decision": "ESCALATE", "values": values}', r'        return {"decision": "HOLD", "reason": "conflict"}'),
    ("reader", r'        return {"decision": "ESCALATE", "values": values}', r'        return {"decision": "ESCALATE", "values": values, "value": values[0]}'),
    ("reader", r'        return {"decision": "ESCALATE", "values": values}', r'        return {"decision": "ADOPT", "value": values[0]}'),
    ("reader", r'    if len(values) > 1:', r'    if len(values) > 2:'),
    ("reader", r'        return {"decision": "HOLD", "reason": "empty_view"}', r'        return {"decision": "ADOPT", "value": ""}'),
    ("reader", r'        if entry["value"] not in values:', r'        if True:'),
    # what an agent sees
    ("public", r'    return {"id": entry["id"], "writer": entry["writer"], "value": entry["value"], "score": entry["score"]}', r'    return dict(entry)'),
    ("public", r'    return {"id": entry["id"], "writer": entry["writer"], "value": entry["value"], "score": entry["score"]}', r'    return {"id": entry["id"], "writer": entry["writer"], "value": entry["value"], "score": entry["score"], "poisoned": entry["poisoned"]}'),
    # expiry
    ("expiry", r'    if query["deadline"] is not None and query["read_at"] > query["deadline"]:', r'    if query["deadline"] is not None and query["read_at"] >= query["deadline"]:'),
    ("expiry", r'    if query["deadline"] is not None and query["read_at"] > query["deadline"]:', r'    if False:'),
    ("expiry", r'    if query["deadline"] is not None and query["read_at"] > query["deadline"]:', r'    if query["deadline"] is not None and query["read_at"] < query["deadline"]:'),
    ("expiry", r'    elif any(e["expires"] is not None and e["expires"] < query["read_at"] for e in retrieved):', r'    elif any(e["expires"] is not None and e["expires"] <= query["read_at"] for e in retrieved):'),
    ("expiry", r'    elif any(e["expires"] is not None and e["expires"] < query["read_at"] for e in retrieved):', r'    elif False:'),
    ("expiry", r'    elif any(e["expires"] is not None and e["expires"] < query["read_at"] for e in retrieved):', r'    elif any(e["expires"] is not None and e["expires"] < query["read_at"] for e in store.snapshot()):'),
    ("expiry", r'    elif any(e["expires"] is not None and e["expires"] < query["read_at"] for e in retrieved):', r'    elif all(e["expires"] is not None and e["expires"] < query["read_at"] for e in retrieved):'),
    ("expiry", r'ON_EXPIRY = "DENY"', r'ON_EXPIRY = "HOLD"'),
    ("expiry", r'        decision = {"decision": "DENY", "reason": "entry_expired"}', r'        decision = {"decision": "HOLD", "reason": "entry_expired"}'),
    # outcome and report
    ("report", r'        if decision["value"] == gold:', r'        if decision["value"] != gold:'),
    ("report", r'        if any(e["poisoned"] and e["value"] == decision["value"] for e in retrieved):', r'        if any(e["value"] == decision["value"] for e in retrieved):'),
    ("report", r'        if any(e["poisoned"] and e["value"] == decision["value"] for e in retrieved):', r'        if False:'),
    ("report", r'    row["conflict_retrieved"] = distinct(retrieved) > 1', r'    row["conflict_retrieved"] = distinct(retrieved) > 0'),
    ("report", r'        row["conflict_visible"] = distinct(view) > 1', r'        row["conflict_visible"] = distinct(view) > 0'),
    ("report", r'    row["field_conflict"] = distinct([e for e in store.snapshot() if e["field"] == query["field"]]) > 1', r'    row["field_conflict"] = distinct(retrieved) > 1'),
    ("report", r'    return len({e["value"] for e in entries})', r'    return len(entries)'),
    ("report", r'    rows = [read_query(store, q, p, k) for p in policies for q in queries]', r'    rows = [read_query(store, q, p, k + (p == "surface")) for p in policies for q in queries]'),
    ("report", r'        counts["conflict_visible"] = sum(1 for r in mine if r["conflict_visible"])', r'        counts["conflict_visible"] = 0'),
    # validation
    ("validate", r'    if type(entry["poisoned"]) is not bool:', r'    if entry["poisoned"] not in (True, False):'),
    ("validate", r'    if type(value) not in (int, float) or abs(value) > MAX_SCORE:', r'    if not isinstance(value, (int, float)) or abs(value) > MAX_SCORE:'),
    ("validate", r'    if type(value) not in (int, float) or abs(value) > MAX_SCORE:', r'    if type(value) not in (int, float):'),
    ("validate", r'    if type(value) not in (int, float) or abs(value) > MAX_SCORE:', r'    if type(value) is not int or abs(value) > MAX_SCORE:'),
    ("validate", r'    if type(k) is not int or not 1 <= k <= MAX_K:', r'    if not isinstance(k, int) or not 1 <= k <= MAX_K:'),
    ("validate", r'    if type(k) is not int or not 1 <= k <= MAX_K:', r'    if type(k) is not int or not 0 <= k <= MAX_K:'),
    ("validate", r'    if type(k) is not int or not 1 <= k <= MAX_K:', r'    if type(k) is not int or not 1 <= k:'),
    ("validate", r'    if type(value) is not int or not 0 <= value <= MAX_TIME:', r'    if not isinstance(value, int) or not 0 <= value <= MAX_TIME:'),
    ("validate", r'    if type(value) is not int or not 0 <= value <= MAX_TIME:', r'    if type(value) is not int or not 0 <= value:'),
    ("validate", r'    if type(value) is not int or not 0 <= value <= MAX_TIME:', r'    if type(value) is not int or not 1 <= value <= MAX_TIME:'),
    ("validate", r'    if value is None and nullable:', r'    if value is None:'),
    ("validate", r'    if type(value) is not str or ID_RE.fullmatch(value) is None:', r'    if type(value) is not str or ID_RE.match(value) is None:'),
    ("validate", r'    if type(value) is not str or not value.strip() or value != value.strip() or len(value) > MAX_VALUE:', r'    if type(value) is not str or not value.strip() or len(value) > MAX_VALUE:'),
    ("validate", r'    if type(value) is not str or not value.strip() or value != value.strip() or len(value) > MAX_VALUE:', r'    if type(value) is not str or value != value.strip() or len(value) > MAX_VALUE:'),
    ("validate", r'    if type(value) is not str or not value.strip() or value != value.strip() or len(value) > MAX_VALUE:', r'    if type(value) is not str or not value.strip() or value != value.strip():'),
    ("validate", r'    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):', r'    if False:'),
    ("validate", r'    missing = [k for k in keys if k not in value]', r'    missing = []'),
    ("validate", r'    unknown = sorted(set(value) - set(keys))', r'    unknown = []'),
    ("validate", r'    if type(value) is not dict:', r'    if False:'),
    ("validate", r'    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:', r'    if root["fixture_version"] != FIXTURE_VERSION:'),
    ("validate", r'    if root["on_expiry"] != ON_EXPIRY:', r'    if False:'),
    ("validate", r'        if type(root[name]) is not list or not root[name]:', r'        if type(root[name]) is not list:'),
    ("validate", r'        if query["id"] in seen:', r'        if False:'),
    ("validate", r'    if type(names) is not list or not names or len(set(map(str, names))) != len(names):', r'    if type(names) is not list or not names:'),
    ("validate", r'    if type(names) is not list or not names or len(set(map(str, names))) != len(names):', r'    if type(names) is not list or len(set(map(str, names))) != len(names):'),
    ("validate", r'        if type(name) is not str or name not in POLICIES:', r'        if name not in POLICIES:'),
    ("validate", r'        if type(name) is not str or name not in POLICIES:', r'        if False:'),
    # strict JSON and CLI
    ("json", r'        if key in out:', r'        if False:'),
    ("json", r'                          parse_constant=_reject_constant, parse_float=_parse_float)', r'                          parse_float=_parse_float)'),
    ("json", r'                          parse_constant=_reject_constant, parse_float=_parse_float)', r'                          parse_constant=_reject_constant)'),
    ("json", r'    if not math.isfinite(value):', r'    if False:'),
    ("json", r'    if text.startswith("\ufeff"):', r'    if False:'),
    ("json", r'    except (ValueError, RecursionError) as exc:', r'    except ValueError as exc:'),
    ("cli", r'        if len(argv) != 1 or argv[0].startswith("-"):', r'        if len(argv) != 1:'),
    ("cli", r'        if len(argv) != 1 or argv[0].startswith("-"):', r'        if len(argv) < 1:'),
    ("cli", r'        return 2', r'        return 1'),
    ("cli", r'    return 2 if any(r["decision"]["decision"] == "DENY" for r in report["rows"]) else 0', r'    return 0'),
    ("cli", r'        err.write("DENY %s: %s\n" % (exc.code, exc.detail))', r'        out.write("DENY %s: %s\n" % (exc.code, exc.detail))'),
    ("cli", r'    except (OSError, UnicodeDecodeError) as exc:', r'    except OSError as exc:'),
    ("cli", r'        text = data.decode("utf-8")', r'        text = data.decode("latin-1")'),
]


def run_suite(folder):
    res = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q", "test_conflict_set"], cwd=folder,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return res.returncode


def main():
    base = tempfile.mkdtemp(prefix="w27-mutants-")
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
