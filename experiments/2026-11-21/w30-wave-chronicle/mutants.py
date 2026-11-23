"""Mutation run: break wave_chronicle.py one way at a time and require the unittest suite to fail each time.

Run: python3 -B mutants.py
Each mutant is (name, fragment, replacement); the fragment must occur exactly once in the module.
A suite run is bounded by TIMEOUT. A run that reaches it has on_expiry DENY: it is reported as TIMEOUT and is NOT
counted as killed, so the whole run fails. Exit 0 only if every mutant is killed by a real test failure.
Work happens in a private temporary folder that this script creates and removes.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}

MUTANTS = [
    # F1 scope and window
    ("scope_starts_a_day_early", 'SCOPE_START = "2026-11-09"', 'SCOPE_START = "2026-11-08"'),
    ("legacy_days_are_measured",
     'measured = [d for d in names if d >= SCOPE_START and lo <= d <= hi]',
     'measured = [d for d in names if lo <= d <= hi]'),
    ("window_ignored_when_reading",
     'measured = [d for d in names if d >= SCOPE_START and lo <= d <= hi]',
     'measured = [d for d in names if d >= SCOPE_START]'),
    ("window_upper_bound_exclusive",
     'measured = [d for d in names if d >= SCOPE_START and lo <= d <= hi]',
     'measured = [d for d in names if d >= SCOPE_START and lo <= d < hi]'),
    ("legacy_list_dropped", 'legacy = [d for d in names if d < SCOPE_START]', 'legacy = []'),
    ("outside_list_dropped", 'outside = [d for d in names if d >= SCOPE_START and not lo <= d <= hi]', 'outside = []'),
    ("empty_window_passes",
     '    if not measured:\n        raise ChronicleError("no_days_in_window"',
     '    if False:\n        raise ChronicleError("no_days_in_window"'),
    ("inverted_window_passes", '    if lo > hi:\n        raise ChronicleError("bad_window", "--from is after --to")',
     '    if False:\n        raise ChronicleError("bad_window", "--from is after --to")'),
    # F2 provenance
    ("entry_blob_dropped", '"source": {"path": day["path"], "blob": day["blob"]}})',
     '"source": {"path": day["path"]}})'),
    ("blob_without_header", 'return hashlib.sha1(b"blob %d\\x00" % len(data) + data).hexdigest()',
     'return hashlib.sha1(data).hexdigest()'),
    ("pin_mismatch_ignored", 'if pins[date] != (blob, len(data)):', 'if pins[date][0] != blob and False:'),
    ("pin_size_ignored", 'if pins[date] != (blob, len(data)):', 'if pins[date][0] != blob:'),
    ("unpinned_day_passes", '            if date not in pins:\n                raise ChronicleError("unpinned_readme"',
     '            if False:\n                raise ChronicleError("unpinned_readme"'),
    ("pinned_missing_day_passes", 'if lo <= date <= hi and date not in names:', 'if False:'),
    ("pins_unsorted_accepted", 'if date < last:', 'if False:'),
    ("pins_legacy_day_accepted", 'if date < SCOPE_START:\n            raise ChronicleError("bad_pin"',
     'if False:\n            raise ChronicleError("bad_pin"'),
    ("render_drops_blob", '"- %s (%s) [%s @ %s]" % (e["slug"], _tag(e), e["source"]["path"], e["source"]["blob"])',
     '"- %s (%s) [%s]" % (e["slug"], _tag(e), e["source"]["path"])'),
    # grammar
    ("heading_date_not_compared", 'if lines[0] != "# experiments/" + date:',
     'if not lines[0].startswith("# experiments/"):'),
    ("blank_line_two_optional", 'if len(lines) < 2 or lines[1] != "":', 'if len(lines) < 2:'),
    ("tail_lines_ignored", 'if rest and rest != ["", FOOTER]:', 'if False:'),
    ("footer_counted_loosely", 'if rest and rest != ["", FOOTER]:', 'if rest and rest[0] != "":'),
    ("no_entries_passes", '    if not entries:\n        raise ChronicleError("no_entries"',
     '    if False:\n        raise ChronicleError("no_entries"'),
    ("link_not_compared", 'if link != slug + "/":', 'if False:'),
    ("slug_charset_open", 'SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\\Z")', 'SLUG_RE = re.compile(r"^.+\\Z")'),
    ("duplicate_slug_passes", 'if slug in seen:', 'if False:'),
    ("carriage_return_passes", 'if "\\r" in text:', 'if False:'),
    ("entry_cap_off_by_one", 'if len(entries) > CAPS["entries_per_day"]["limit"]:',
     'if len(entries) > CAPS["entries_per_day"]["limit"] + 1:'),
    ("wave_from_any_w_prefix", 'WAVE_RE = re.compile(r"^w([0-9]{2})\\Z")', 'WAVE_RE = re.compile(r"^w([0-9]+)\\Z")'),
    # text and encoding
    ("control_chars_pass", 'if cat in BAD_CATEGORIES or (cat == "Zs" and ch != " "):', 'if cat == "Cc" and ch == "\\x00":'),
    ("odd_spaces_pass", 'if cat in BAD_CATEGORIES or (cat == "Zs" and ch != " "):', 'if cat in BAD_CATEGORIES:'),
    ("edge_spaces_pass", 'if value == "" or value != value.strip(" "):', 'if value == "":'),
    ("bom_accepted", 'if data.startswith(b"\\xef\\xbb\\xbf"):', 'if False:'),
    ("lenient_decoding", 'return data.decode("utf-8", errors="strict")', 'return data.decode("utf-8", errors="replace")'),
    ("track_names_not_normalised", 'return unicodedata.normalize("NFC", value)', 'return value'),
    ("size_cap_ignored", 'if len(data) > cap:', 'if False:'),
    ("symlinks_followed", 'st = os.lstat(path)', 'st = os.stat(path)'),
    # tracks file
    ("duplicate_keys_pass", 'if key in out:', 'if False:'),
    ("nan_passes", 'parse_constant=_no_constant', 'parse_constant=float'),
    ("ints_pass_the_parser", 'parse_int=_no_number)', 'parse_int=int)'),
    ("non_text_track_passes", 'if not isinstance(value, str):', 'if value is None:'),
    ("recursion_escapes", '    except RecursionError:\n        raise ChronicleError("too_deep"',
     '    except MemoryError:\n        raise ChronicleError("too_deep"'),
    ("invented_track_name", 'track = tracks.get(e["family"])', 'track = tracks.get(e["family"], "misc")'),
    # root, diff, cli
    ("stray_root_entries_pass", '        if not valid_date(name):\n            raise ChronicleError("bad_root_entry"',
     '        if not valid_date(name):\n            continue'),
    ("calendar_not_checked", 'datetime.date(int(text[:4]), int(text[5:7]), int(text[8:]))', 'pass'),
    ("changed_ignores_row_bytes", 'if k in old and old[k][0] != new[k][0]]', 'if k in old and old[k][1] != new[k][1]]'),
    ("removed_list_dropped", 'removed = [{"entry": k, "base_blob": old[k][1]} for k in sorted(old) if k not in new]',
     'removed = []'),
    ("base_window_ignored", 'base_hi = opts.get("base_to") or hi', 'base_hi = hi'),
    ("duplicate_flag_passes", '        if key in opts:\n            raise ChronicleError("bad_args", "%s given twice" % flag)\n        if i + 1',
     '        if False:\n            raise ChronicleError("bad_args", "%s given twice" % flag)\n        if i + 1'),
    ("error_exit_code_changed", '        sys.stderr.write("ERROR %s: %s (on_expiry=%s)\\n" % (e.code, e.detail, ON_EXPIRY))\n        return 2',
     '        sys.stderr.write("ERROR %s: %s (on_expiry=%s)\\n" % (e.code, e.detail, ON_EXPIRY))\n        return 1'),
]


def outcome(code):
    """None means the suite run reached TIMEOUT; that is on_expiry DENY and never a kill."""
    if code is None:
        return "TIMEOUT"
    return "SURVIVED" if code == 0 else "KILLED"


def is_killed(result):
    return result == "KILLED"


def run_suite(workdir):
    try:
        done = subprocess.run([sys.executable, "-B", "-m", "unittest", "-f"], cwd=workdir, capture_output=True,
                              timeout=TIMEOUT["seconds"])
    except subprocess.TimeoutExpired:
        return None
    return done.returncode


def main():
    with open(os.path.join(HERE, "wave_chronicle.py"), "r", encoding="utf-8") as fh:
        original = fh.read()
    names = [m[0] for m in MUTANTS]
    if len(set(names)) != len(names):
        sys.stdout.write("ERROR duplicate mutant names\n")
        return 2
    for name, fragment, _ in MUTANTS:
        if original.count(fragment) != 1:
            sys.stdout.write("ERROR fragment for %s occurs %d times\n" % (name, original.count(fragment)))
            return 2
    work = tempfile.mkdtemp(prefix="w30-mutants-")
    try:
        for entry in os.listdir(HERE):
            if entry == "__pycache__":
                continue
            src = os.path.join(HERE, entry)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(work, entry), symlinks=True)
            else:
                shutil.copy(src, os.path.join(work, entry))
        target = os.path.join(work, "wave_chronicle.py")
        base = outcome(run_suite(work))
        sys.stdout.write("baseline suite: %s\n" % ("passes" if base == "SURVIVED" else base))
        if base != "SURVIVED":
            sys.stdout.write("ERROR the unmodified suite must pass within the timeout\n")
            return 2
        killed = 0
        for name, fragment, replacement in MUTANTS:
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(original.replace(fragment, replacement))
            result = outcome(run_suite(work))
            killed += is_killed(result)
            sys.stdout.write("%-8s %s\n" % (result, name))
        sys.stdout.write("mutants killed: %d/%d (timeouts are not kills; on_expiry %s)\n"
                         % (killed, len(MUTANTS), TIMEOUT["on_expiry"]))
        return 0 if killed == len(MUTANTS) else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
