"""Mutation run: break record_presence.py one way at a time and require a real test failure each time.

Run: python3 -B mutants.py
Each mutant is (name, fragment, replacement); this script, not the test suite, checks that the fragment occurs exactly
once before it runs anything. The tests never read any source file.
Outcomes:
- KILLED   the mutant imports and at least one test fails on behaviour (unittest reports failures).
- CRASH    the mutant does not import, or the suite only errors; counted apart from kills.
- TIMEOUT  the suite run reached TIMEOUT; on_expiry DENY, never a kill.
- SURVIVED the suite passed.
Exit 0 only if every mutant is KILLED. Work happens in a private temporary folder this script creates and removes.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = "record_presence.py"
TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}

MUTANTS = [
    # criterion 1: table and braces
    ("brace_not_expanded", 'names = [x + a for x in names for a in alts]', 'names = [x + piece for x in names]'),
    ("single_choice_brace_expands", 'if len(alts) < 2 or any(a == "" for a in alts):', 'if any(a == "" for a in alts):'),
    ("files_column_from_group", 'cell = cells[fcol]', 'cell = cells[gcol]'),
    ("heading_inside_fence_counts", '        if fenced:\n            continue\n', '        if False:\n            continue\n'),
    ("table_runs_past_blank_line", "while n < len(lines) and lines[n].lstrip().startswith(\"|\"):",
     "while n < len(lines) and (lines[n].lstrip().startswith(\"|\") or lines[n].strip() == \"\"):"),
    # criterion 2: unparsed tokens
    ("range_token_becomes_a_name", '        if ".." in name:\n            return None, "not a single filename"',
     '        if False:\n            return None, "not a single filename"'),
    ("unparsed_dropped_silently", '                unparsed.append({"group": group, "token": token, "after": None, '
                                  '"why": why})', '                pass'),
    ("plus_note_ignored", 'm.group("note").strip().startswith("+")', 'm.group("note").strip().startswith("++")'),
    ("loose_text_ignored", 'unparsed.append({"group": group, "token": part.strip(), "after": previous,',
     'None and ({"group": group, "token": part.strip(), "after": previous,'),
    ("unparsed_counted_as_fail", '        findings.append({"level": "INFO", "code": "unparsed_name"',
     '        findings.append({"level": "FAIL", "code": "unparsed_name"'),
    ("loose_names_unchecked", '        if LOOSE_NAME_RE.match(segs[-1]) and all(', '        if False and all('),
    ("path_checks_full_token", '            out.append(segs[-1])', '            out.append(name)'),
    ("loose_admits_glob", 'LOOSE_NAME_RE = re.compile(r"^(?! )[^/\\\\*?', 'LOOSE_NAME_RE = re.compile(r"^(?! )[^/\\\\'),
    ("loose_dirs_unchecked", 'all(LOOSE_DIR_RE.match(d) for d in segs[:-1])', 'True'),
    # criterion 3 and 4: misses and receipts
    ("missing_is_not_fail", 'row = {"level": "FAIL", "code"', 'row = {"level": "INFO", "code"'),
    ("receipt_not_special", 'is_receipt = f["name"] == receipt_name or "receipt" in f["name"].lower()',
     'is_receipt = f["name"] == receipt_name'),
    ("receipt_option_ignored", 'is_receipt = f["name"] == receipt_name or "receipt" in f["name"].lower()',
     'is_receipt = "receipt" in f["name"].lower()'),
    ("group_not_reported", '"name": f["name"], "group": f["group"], "ignored_by_pattern": None}',
     '"name": f["name"], "group": None, "ignored_by_pattern": None}'),
    ("receipt_not_named_silent", 'if receipt_name is not None and receipt_name not in named_names:', 'if False:'),
    ("case_folded_match", '        if f["name"] in present:\n', '        if f["name"].lower() in {x.lower() for x in present}:\n'),
    # criterion 5: listed, not named
    ("listed_not_named_dropped", 'for name in sorted(present - set(named_names)):', 'for name in []:'),
    # criterion 6: ignore rules
    ("first_rule_wins", '            decided = rule\n', '            decided = decided or rule\n'),
    ("negation_ignored", 'if decided is None or decided["negate"]:', 'if decided is None:'),
    ("slash_rule_matches_basename", '    if "/" not in body:\n        return _match_segments([body], [name])',
     '    if True:\n        return _match_segments([body.split("/")[-1]], [name])'),
    ("dir_rule_matches_files", '    if rule["dir_only"]:\n        return False', '    if False:\n        return False'),
    ("double_star_one_segment", 'for i in range(len(path) + 1))', 'for i in (1,) if i <= len(path))'),
    ("matcher_ignores_case", 'fnmatch.fnmatchcase(path[0], pat[0])', 'fnmatch.fnmatch(path[0].lower(), pat[0].lower())'),
    ("tag_never_set", 'row["ignored_by_pattern"] = explain(rules, f["name"], record_path)', 'pass'),
    ("comments_become_rules", 'if line == "" or line.startswith("#"):', 'if line == "":'),
    # criterion 8 and 9: DENY and caps
    ("no_files_table_passes", '        raise PresenceError("no_files_table", "cover has no \'## Files\' section")',
     '        return {"title": title, "groups": [], "named": [], "unparsed": []}'),
    ("second_table_passes", 'if len(starts) > 1:', 'if False:'),
    ("row_width_unchecked", 'if cells is None or len(cells) != len(header):', 'if cells is None:'),
    ("rows_cap_removed", 'if len(rows) > CAPS["table_rows"]["limit"]:', 'if False:'),
    ("names_cap_off_by_one", 'if len(named) > CAPS["named_files"]["limit"]:',
     'if len(named) >= CAPS["named_files"]["limit"]:'),
    ("invisible_name_passes", '            if _invisible(part):\n', '            if False:\n'),
    ("duplicate_name_passes", '                if name in seen:\n', '                if False:\n'),
    ("unclosed_backtick_passes", 'if len(parts) % 2 == 0:', 'if False:'),
    ("blank_listing_line_passes", '        if line.strip() == "":\n            raise PresenceError("blank_listing_line"',
     '        if False:\n            raise PresenceError("blank_listing_line"'),
    ("listing_path_passes", '"/" in line or ', ''),
    ("listing_not_nfc", '        name = unicodedata.normalize("NFC", line)', '        name = line'),
    ("bom_passes", 'if text.startswith("\\ufeff"):', 'if False:'),
    ("size_cap_removed", 'if len(data) > limit:', 'if False:'),
    ("record_path_unchecked", '    record_path = None if opts["record_path"] is None else _check_record_path(opts["record_path"])',
     '    record_path = opts["record_path"]'),
    ("error_to_stdout", 'sys.stderr.write("ERROR %s: %s (on_expiry=DENY)\\n" % (e.code, e.detail))',
     'sys.stdout.write("ERROR %s: %s (on_expiry=DENY)\\n" % (e.code, e.detail))'),
    ("fail_exits_zero", 'return 1 if res["result"] == "FAIL" else 0', 'return 0'),
]

SUMMARY_RE = re.compile(r"FAILED \(([^)]*)\)")


def classify(imported, code, output):
    """imported: the mutant module imported cleanly; code: suite exit code, None when TIMEOUT was reached."""
    if not imported:
        return "CRASH"
    if code is None:
        return "TIMEOUT"
    if code == 0:
        return "SURVIVED"
    m = SUMMARY_RE.search(output)
    if m is None:
        return "CRASH"
    counts = dict((k.strip(), int(v)) for k, v in (p.split("=") for p in m.group(1).split(",")))
    return "KILLED" if counts.get("failures", 0) > 0 else "CRASH"


def is_kill(outcome):
    return outcome == "KILLED"


def summary(outcomes):
    n = {k: sum(1 for o in outcomes if o == k) for k in ("KILLED", "TIMEOUT", "CRASH", "SURVIVED")}
    return ("mutants: killed %d / timeout %d / crash %d / survived %d of %d (a timeout or crash is never a kill; "
            "on_expiry %s)" % (n["KILLED"], n["TIMEOUT"], n["CRASH"], n["SURVIVED"], len(outcomes),
                               TIMEOUT["on_expiry"]))


def _imports(work):
    try:
        done = subprocess.run([sys.executable, "-B", "-c", "import record_presence"], cwd=work, capture_output=True,
                              timeout=TIMEOUT["seconds"])
    except subprocess.TimeoutExpired:
        return False
    return done.returncode == 0


def _suite(work):
    try:
        done = subprocess.run([sys.executable, "-B", "-m", "unittest"], cwd=work, capture_output=True, text=True,
                              timeout=TIMEOUT["seconds"])
    except subprocess.TimeoutExpired:
        return None, ""
    return done.returncode, done.stderr + done.stdout


def evaluate(work):
    imported = _imports(work)
    if not imported:
        return classify(False, None, "")
    code, output = _suite(work)
    return classify(True, code, output)


def main():
    with open(os.path.join(HERE, MODULE), "r", encoding="utf-8") as fh:
        original = fh.read()
    if len({m[0] for m in MUTANTS}) != len(MUTANTS):
        sys.stdout.write("ERROR duplicate mutant names\n")
        return 2
    for name, fragment, replacement in MUTANTS:
        if original.count(fragment) != 1 or fragment == replacement:
            sys.stdout.write("ERROR fragment for %s occurs %d times\n" % (name, original.count(fragment)))
            return 2
    work = tempfile.mkdtemp(prefix="w32-mutants-")
    try:
        for entry in os.listdir(HERE):
            if entry == "__pycache__":
                continue
            src = os.path.join(HERE, entry)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(work, entry))
            else:
                shutil.copy(src, os.path.join(work, entry))
        target = os.path.join(work, MODULE)
        base = evaluate(work)
        sys.stdout.write("baseline suite: %s\n" % ("passes" if base == "SURVIVED" else base))
        if base != "SURVIVED":
            sys.stdout.write("ERROR the unmodified suite must pass within the timeout\n")
            return 2
        outcomes = []
        for name, fragment, replacement in MUTANTS:
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(original.replace(fragment, replacement))
            outcome = evaluate(work)
            outcomes.append(outcome)
            sys.stdout.write("%-8s %s\n" % (outcome, name))
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(original)
        sys.stdout.write(summary(outcomes) + "\n")
        return 0 if all(is_kill(o) for o in outcomes) else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
