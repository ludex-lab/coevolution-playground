"""Mutation self-check for w26-verification-transport (stdlib only).

Each mutant replaces one exact source fragment (which must occur exactly once) in a copy of this
folder made in a private temporary directory, then runs the unittest suite with the same Python
interpreter. A mutant is killed when the suite fails. Only that temporary directory is removed.
Run: python3 -B mutants.py   (exit 0 only when every mutant is killed)
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
COPY = ("transport.py", "test_transport.py", "demo.py", "evidence.json", "README.md", "fixtures")
T = "transport.py"
D = "demo.py"

MUTANTS = [
    # verifiers
    (T, "verifier", "        if summary is not None and item in summary[\"claims\"]:", "        if False:"),
    (T, "verifier", "        if value is None:\n            value = _claimed(obs, item)", "        if False:\n            value = _claimed(obs, item)"),
    (T, "verifier", "        if value is not True:\n            return \"fail\"", "        if value is False:\n            return \"fail\""),
    (T, "verifier", "    return \"pass\"\n\n\ndef grounded", "    return \"fail\"\n\n\ndef grounded"),
    (T, "verifier", "    if any(v is None for v in values):", "    if all(v is None for v in values):"),
    (T, "verifier", "        return \"abstain\"\n    return \"pass\" if all(values)", "        return \"fail\"\n    return \"pass\" if all(values)"),
    (T, "verifier", "    return \"pass\" if all(values) else \"fail\"", "    return \"pass\" if any(values) else \"fail\""),
    (T, "verifier", "    return {\"criterion\": list(view[\"criterion\"]), \"steps\": copy.deepcopy(view[\"steps\"])}",
     "    return dict(view, criterion=list(view[\"criterion\"]))"),
    (T, "verifier", "    if v not in VERDICTS:", "    if False:"),
    # views
    (T, "views", "        \"step_ids\": tuple(s[\"id\"] for s in execution[\"steps\"]),", "        \"step_ids\": len(execution[\"steps\"]),"),
    (T, "views", "        \"criterion\": tuple(execution[\"criterion\"]),", "        \"criterion\": tuple(sorted(execution[\"criterion\"])),"),
    (T, "views", "        if boundary in s.get(\"hidden_by\", ()):", "        if s.get(\"hidden_by\"):"),
    (T, "views", "            view[\"steps\"].append({\"id\": s[\"id\"], \"tool\": s[\"tool\"], \"evidence\": None, \"summary\": summary})",
     "            view[\"steps\"].append({\"id\": s[\"id\"], \"tool\": s[\"tool\"], \"evidence\": None, \"summary\": None})"),
    (T, "views", "            provenance[s[\"id\"]] = dict(s[\"evidence\"])\n", "            provenance[s[\"id\"]] = {}\n"),
    (T, "views", "    if not provenance:\n        raise Deny(\"boundary_hides_nothing\"", "    if False:\n        raise Deny(\"boundary_hides_nothing\""),
    (T, "views", "    if boundary not in BOUNDARIES:\n        raise Deny(\"unknown_boundary\", repr(boundary))",
     "    if boundary is None:\n        raise Deny(\"unknown_boundary\", repr(boundary))"),
    (T, "views", "            step[\"evidence\"] = {k: None for k in hidden} if lossy else dict(hidden)",
     "            step[\"evidence\"] = dict(hidden)"),
    (T, "views", "            step[\"evidence\"] = {k: None for k in hidden} if lossy else dict(hidden)",
     "            step[\"evidence\"] = {k: None for k in hidden}"),
    (T, "views", "            step[\"summary\"] = None if not lossy else step[\"summary\"]", "            step[\"summary\"] = None"),
    (T, "views", "    out[\"restore\"] = \"lossy\" if lossy else \"full\"", "    out[\"restore\"] = \"full\""),
    (T, "views", "    out = copy.deepcopy(view)", "    out = view"),
    # matching
    (T, "match", "FROZEN = (\"task\", \"trajectory_id\", \"step_ids\", \"outcome\", \"ground_truth\", \"criterion\", \"verifier\")",
     "FROZEN = (\"task\", \"trajectory_id\", \"step_ids\", \"outcome\", \"ground_truth\", \"criterion\")"),
    (T, "match", "FROZEN = (\"task\", \"trajectory_id\", \"step_ids\", \"outcome\", \"ground_truth\", \"criterion\", \"verifier\")",
     "FROZEN = (\"task\", \"step_ids\", \"outcome\", \"ground_truth\", \"criterion\", \"verifier\")"),
    (T, "match", "FROZEN = (\"task\", \"trajectory_id\", \"step_ids\", \"outcome\", \"ground_truth\", \"criterion\", \"verifier\")",
     "FROZEN = (\"trajectory_id\", \"step_ids\", \"outcome\", \"ground_truth\", \"criterion\", \"verifier\")"),
    (T, "match", "FROZEN = (\"task\", \"trajectory_id\", \"step_ids\", \"outcome\", \"ground_truth\", \"criterion\", \"verifier\")",
     "FROZEN = (\"task\", \"trajectory_id\", \"outcome\", \"ground_truth\", \"criterion\", \"verifier\")"),
    (T, "match", "FROZEN = (\"task\", \"trajectory_id\", \"step_ids\", \"outcome\", \"ground_truth\", \"criterion\", \"verifier\")",
     "FROZEN = (\"task\", \"trajectory_id\", \"step_ids\", \"ground_truth\", \"criterion\", \"verifier\")"),
    (T, "match", "FROZEN = (\"task\", \"trajectory_id\", \"step_ids\", \"outcome\", \"ground_truth\", \"criterion\", \"verifier\")",
     "FROZEN = (\"task\", \"trajectory_id\", \"step_ids\", \"outcome\", \"criterion\", \"verifier\")"),
    (T, "match", "FROZEN = (\"task\", \"trajectory_id\", \"step_ids\", \"outcome\", \"ground_truth\", \"criterion\", \"verifier\")",
     "FROZEN = (\"task\", \"trajectory_id\", \"step_ids\", \"outcome\", \"ground_truth\", \"verifier\")"),
    (T, "match", "        if a[field] != b[field]:", "        if a[field] != b[field] and field != \"verifier\" and False:"),
    (T, "match", "    check_matched(native, abstracted)\n", "\n"),
    # labels and counts
    (T, "label", "    if native_v != truth:\n        return \"native_not_correct\"", "    if False:\n        return \"native_not_correct\""),
    (T, "label", "    if abstracted_v == \"abstain\":\n        return \"transport_abstain\"", "    if False:\n        return \"transport_abstain\""),
    (T, "label", "    if abstracted_v == \"abstain\":\n        return \"transport_abstain\"", "    if abstracted_v == \"abstain\":\n        return \"transport_incorrect\""),
    (T, "label", "    if abstracted_v == truth:\n        return \"stable\"", "    if abstracted_v != \"fail\":\n        return \"stable\""),
    (T, "label", "    if lab in (\"transport_incorrect\", \"transport_abstain\"):", "    if lab == \"transport_incorrect\":"),
    (T, "label", "            row[mode] = \"recovered\" if verdict(restored) == truth else \"not_recovered\"",
     "            row[mode] = \"recovered\" if verdict(restored) != \"abstain\" else \"not_recovered\""),
    (T, "label", "        for mode, lossy in ((\"restore_full\", False), (\"restore_lossy\", True)):",
     "        for mode, lossy in ((\"restore_full\", False), (\"restore_lossy\", False)):"),
    (T, "count", "        if row[\"label\"] != \"native_not_correct\":\n            s[\"native_correct\"] += 1",
     "        if True:\n            s[\"native_correct\"] += 1"),
    (T, "count", "        if row[\"label\"] in (\"transport_incorrect\", \"transport_abstain\"):\n            s[\"transport_failures\"] += 1",
     "        if row[\"label\"] == \"transport_incorrect\":\n            s[\"transport_failures\"] += 1"),
    (T, "count", "        if row[\"restore_full\"] == \"recovered\":\n            s[\"recovered_full\"] += 1",
     "        if row[\"restore_full\"] != \"n/a\":\n            s[\"recovered_full\"] += 1"),
    (T, "count", "        if row[\"restore_lossy\"] == \"recovered\":\n            s[\"recovered_lossy\"] += 1",
     "        if row[\"restore_lossy\"] != \"n/a\":\n            s[\"recovered_lossy\"] += 1"),
    # ranking
    (T, "rank", "    if ai <= bi and aa <= ba:\n        return \"first_more_reliable\"",
     "    if ai + aa < bi + ba:\n        return \"first_more_reliable\""),
    (T, "rank", "    if bi <= ai and ba <= aa:\n        return \"second_more_reliable\"",
     "    if bi + ba < ai + aa:\n        return \"second_more_reliable\""),
    (T, "rank", "    if ai <= bi and aa <= ba:", "    if ai <= bi:"),
    (T, "rank", "    if bi <= ai and ba <= aa:", "    if ba <= aa:"),
    (T, "rank", "    if (ai, aa) == (bi, ba):\n        return \"equal\"", "    if ai == bi:\n        return \"equal\""),
    (T, "rank", "    return \"not_ranked\"", "    return \"first_more_reliable\""),
    # native only
    (T, "native", "            \"transport\": \"unmeasured\", \"status\": \"unmeasured\"}", "            \"transport\": \"unmeasured\", \"status\": \"PASS\"}"),
    (T, "native", "            \"transport\": \"unmeasured\", \"status\": \"unmeasured\"}", "            \"transport\": \"measured\", \"status\": \"unmeasured\"}"),
    (T, "native", "    correct = sum(1 for v in views if verdict(v) == v[\"ground_truth\"])", "    correct = len(views)"),
    (T, "native", "    return {\"mode\": \"pairs\", \"rows\": rows, \"summary\": summarize(rows),\n            \"transport\": \"measured\", \"status\": \"measured\", \"info\": info}",
     "    return {\"mode\": \"pairs\", \"rows\": rows, \"summary\": summarize(rows),\n            \"transport\": \"measured\", \"status\": \"PASS\", \"info\": info}"),
    # fixture checks and DENY
    (T, "deny", "    _need(spec.get(\"expired\") is not True, \"on_expiry\"", "    _need(True, \"on_expiry\""),
    (T, "deny", "ON_EXPIRY = \"DENY\"", "ON_EXPIRY = \"HOLD\""),
    (T, "deny", "        _need(\"native\" in pair and \"abstracted\" in pair, \"missing_view\"",
     "        _need(\"native\" in pair, \"missing_view\""),
    (T, "deny", "    _need(isinstance(spec, dict), \"missing_view\"", "    _need(spec is not None or True, \"missing_view\""),
    (T, "deny", "    _need(spec.get(\"execution\") in executions, \"missing_view\"", "    _need(True, \"missing_view\""),
    (T, "deny", "    _need(spec.get(\"verifier\") in VERIFIERS, \"unknown_verifier\"", "    _need(True, \"unknown_verifier\""),
    (T, "deny", "    _need(has_pairs != has_native, \"malformed_fixture\"", "    _need(has_pairs or has_native, \"malformed_fixture\""),
    (T, "deny", "    _need(isinstance(data[key], list) and data[key], \"malformed_fixture\"", "    _need(isinstance(data[key], list), \"malformed_fixture\""),
    (T, "deny", "        _need(pid not in ids, \"malformed_fixture\"", "        _need(True, \"malformed_fixture\""),
    (T, "deny", "        _need(e[\"id\"] not in by_id, \"malformed_fixture\"", "        _need(True, \"malformed_fixture\""),
    (T, "deny", "    return isinstance(m, dict) and all(isinstance(k, str) and isinstance(v, bool) for k, v in m.items())",
     "    return isinstance(m, dict)"),
    (T, "deny", "    _need(e.get(\"ground_truth\") in (\"pass\", \"fail\"), \"malformed_fixture\"", "    _need(True, \"malformed_fixture\""),
    (T, "deny", "    _need(isinstance(crit, list) and crit and", "    _need(isinstance(crit, list) and"),
    (T, "deny", "            _need(k not in seen, \"malformed_fixture\"", "            _need(True, \"malformed_fixture\""),
    (T, "deny", "    _need(all(c in seen for c in crit), \"malformed_fixture\"", "    _need(True, \"malformed_fixture\""),
    (T, "deny", "    _need(full == (e[\"ground_truth\"] == \"pass\"), \"ground_truth_inconsistent\", eid)", "    pass"),
    (T, "deny", "        _need(isinstance(hb, list) and all(b in BOUNDARIES for b in hb), \"unknown_boundary\",",
     "        _need(isinstance(hb, list), \"unknown_boundary\","),
    (T, "deny", "        _need(_text(e.get(f)), \"malformed_fixture\"", "        _need(isinstance(e.get(f), str) and e.get(f), \"malformed_fixture\""),
    (T, "deny", "            _need(isinstance(sm, dict) and _text(sm.get(\"text\")) and _is_bool_map(sm.get(\"claims\")),",
     "            _need(isinstance(sm, dict),"),
    (T, "deny", "    except ValueError:\n        raise Deny(\"malformed_fixture\", \"not JSON\")", "    except ValueError:\n        data = {}"),
    (T, "deny", "        raise Deny(\"unreadable_fixture\", \"%s (%s)\" % (path, exc.__class__.__name__))",
     "        raise Deny(\"malformed_fixture\", \"%s (%s)\" % (path, exc.__class__.__name__))"),
    (T, "deny", "        sys.stderr.write(\"DENY %s: %s\\n\" % (exc.code, exc.detail))\n        return 2",
     "        sys.stderr.write(\"DENY %s: %s\\n\" % (exc.code, exc.detail))\n        return 0"),
    (T, "deny", "    if len(argv) != 1:", "    if len(argv) > 1:"),
    # r2: pair binding (same execution id and equal step content)
    (T, "r2-bind", "BINDING = (\"execution\", \"step_content\")", "BINDING = (\"step_content\",)"),
    (T, "r2-bind", "BINDING = (\"execution\", \"step_content\")", "BINDING = (\"execution\",)"),
    (T, "r2-bind", "    for field in FROZEN + BINDING:", "    for field in FROZEN:"),
    (T, "r2-bind", "        \"step_content\": _content(execution),", "        \"step_content\": (),"),
    (T, "r2-bind", "            summary = (summary[\"text\"], tuple(sorted(summary[\"claims\"].items())))",
     "            summary = None"),
    (T, "r2-bind", "            summary = (summary[\"text\"], tuple(sorted(summary[\"claims\"].items())))",
     "            summary = (summary[\"text\"],)"),
    (T, "r2-bind", "            summary = (summary[\"text\"], tuple(sorted(summary[\"claims\"].items())))",
     "            summary = tuple(sorted(summary[\"claims\"].items()))"),
    (T, "r2-bind", "        out.append((s[\"id\"], s[\"tool\"], tuple(sorted(s[\"evidence\"].items())), summary,",
     "        out.append((s[\"id\"], None, tuple(sorted(s[\"evidence\"].items())), summary,"),
    (T, "r2-bind", "        out.append((s[\"id\"], s[\"tool\"], tuple(sorted(s[\"evidence\"].items())), summary,",
     "        out.append((s[\"id\"], s[\"tool\"], (), summary,"),
    (T, "r2-bind", "                    tuple(sorted(s.get(\"hidden_by\", ())))))", "                    ()))"),
    # r2: unique step ids
    (T, "r2-step", "        _need(s[\"id\"] not in step_ids, \"malformed_fixture\"", "        _need(True, \"malformed_fixture\""),
    (T, "r2-step", "        step_ids.add(s[\"id\"])", "        pass"),
    # r2: expired must be a JSON boolean
    (T, "r2-exp", "        _need(type(spec[\"expired\"]) is bool, \"malformed_fixture\",",
     "        _need(isinstance(spec[\"expired\"], int), \"malformed_fixture\","),
    (T, "r2-exp", "        _need(type(spec[\"expired\"]) is bool, \"malformed_fixture\",",
     "        _need(spec[\"expired\"] in (True, False), \"malformed_fixture\","),
    (T, "r2-exp", "    if \"expired\" in spec:", "    if spec.get(\"expired\"):"),
    (T, "r2-exp", "    if \"expired\" in spec:", "    if False:"),
    # r2: duplicate JSON keys
    (T, "r2-keys", "json.loads(text, object_pairs_hook=_no_duplicate_keys)", "json.loads(text)"),
    (T, "r2-keys", "        if k in out:\n            raise Deny(\"malformed_fixture\", \"duplicate key",
     "        if False:\n            raise Deny(\"malformed_fixture\", \"duplicate key"),
    # r2: a repeated pair is counted once and reported
    (T, "r2-dup", "        if key in first:", "        if False:"),
    (T, "r2-dup", "        key = (row[\"execution\"], row[\"verifier\"], row[\"boundary\"])",
     "        key = (row[\"execution\"], row[\"boundary\"])"),
    (T, "r2-dup", "    for note in report[\"info\"]:", "    for note in ():"),
    # r2: blank ids and text fields
    (T, "r2-blank", "    return isinstance(v, str) and v.strip() != \"\"", "    return isinstance(v, str) and v != \"\""),
    (T, "r2-blank", "    return isinstance(v, str) and v.strip() != \"\"", "    return isinstance(v, str)"),
    (T, "r2-blank", "        _need(isinstance(pair, dict) and _text(pair.get(\"id\")), \"malformed_fixture\", \"pair id\")",
     "        _need(isinstance(pair, dict) and isinstance(pair.get(\"id\"), str), \"malformed_fixture\", \"pair id\")"),
    (T, "r2-blank", "            _need(isinstance(sm, dict) and _text(sm.get(\"text\")) and",
     "            _need(isinstance(sm, dict) and isinstance(sm.get(\"text\"), str) and"),
    (T, "r2-blank", "all(_text(c) for c in crit)", "all(isinstance(c, str) for c in crit)"),
    (T, "r2-blank", "_text(s.get(\"id\")) and _text(s.get(\"tool\"))", "isinstance(s.get(\"id\"), str) and _text(s.get(\"tool\"))"),
    (T, "r2-blank", "_text(s.get(\"id\")) and _text(s.get(\"tool\"))", "_text(s.get(\"id\")) and isinstance(s.get(\"tool\"), str)"),
    # output
    (T, "render", "    if len(names) == 2:", "    if len(names) == 3:"),
    (T, "render", "    names = sorted(report[\"summary\"])", "    names = sorted(report[\"summary\"], reverse=True)"),
    (D, "demo", "    lines.append(\"(e) mismatched, missing and expired views: DENY exit 2, no verdict\")\n", ""),
    (D, "demo", "        out.append(\"DENY %s: %s (exit 2)\" % (exc.code, exc.detail))", "        out.append(\"DENY %s (exit 2)\" % exc.code)"),
]


def run_suite(folder):
    res = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q"], cwd=folder,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return res.returncode


def main():
    base = tempfile.mkdtemp(prefix="w26-mutants-")
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
            print("clean suite fails; no mutants run")
            return 1
        survivors = 0
        for idx, (target, group, old, new) in enumerate(MUTANTS, 1):
            with open(os.path.join(clean, target), encoding="utf-8") as handle:
                source = handle.read()
            if source.count(old) != 1:
                print("mutant %02d %-8s fragment occurs %d times" % (idx, group, source.count(old)))
                return 1
            folder = os.path.join(base, "m%02d" % idx)
            shutil.copytree(clean, folder)
            with open(os.path.join(folder, target), "w", encoding="utf-8") as handle:
                handle.write(source.replace(old, new))
            killed = run_suite(folder) != 0
            survivors += 0 if killed else 1
            print("mutant %02d %-8s %s" % (idx, group, "killed" if killed else "SURVIVED"))
            shutil.rmtree(folder)
        print("killed %d/%d" % (len(MUTANTS) - survivors, len(MUTANTS)))
        return 0 if survivors == 0 else 1
    finally:
        shutil.rmtree(base)


if __name__ == "__main__":
    sys.exit(main())
