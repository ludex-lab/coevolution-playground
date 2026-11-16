"""Mutation harness for w25-daily-issue-index (stdlib only).

Each mutant replaces one exact source fragment (which must occur exactly once) in a copy of
this folder, then runs the unittest suite with the same Python interpreter.  A mutant is
killed when the suite fails.  Run: python3 -B mutants.py   (exit 0 iff all are killed)
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
COPY = ("issue_index.py", "test_issue_index.py", "demo.py", "README.md", "evidence.json",
        "fixtures", "demo")
M = "issue_index.py"

MUTANTS = [
    # validation (F1: exact types, snapshot, declared structure)
    ("validation", M, "    if type(rows) is not list and type(rows) is not tuple:", "    if not isinstance(rows, (list, tuple)):"),
    ("validation", M, "    if not rows:\n        raise InputError(\"fixture_empty\", \"no rows\")", "    if False:\n        raise InputError(\"fixture_empty\", \"no rows\")"),
    ("validation", M, "        if type(row) is not dict:", "        if not isinstance(row, dict):"),
    ("validation", M, "            if type(key) is not str:", "            if not isinstance(key, str):"),
    ("validation", M, "        if set(row) != want:", "        if not want <= set(row):"),
    ("validation", M, "        if type(line) is not int or line < 1:", "        if not isinstance(line, int) or line < 1:"),
    ("validation", M, "        if type(line) is not int or line < 1:", "        if type(line) is not int:"),
    ("validation", M, "            if type(value) is not str:", "            if not isinstance(value, str):"),
    ("validation", M, "            if \"\\t\" in value or \"\\n\" in value or \"\\r\" in value:", "            if \"\\t\" in value:"),
    ("validation", M, "        if not name.strip() or name != name.strip():", "        if not name.strip():"),
    ("validation", M, "        if not name.strip() or name != name.strip():", "        if name != name.strip():"),
    ("validation", M, "        if kind not in KINDS:", "        if False:"),
    ("validation", M, "        if kinds.setdefault(name, kind) != kind:", "        if False:"),
    ("validation", M, "            if en not in PRESENCE or ko not in PRESENCE:", "            if en not in PRESENCE:"),
    ("validation", M, "            if en not in PRESENCE or ko not in PRESENCE:", "            if ko not in PRESENCE:"),
    ("validation", M, "        elif ident or en or ko:", "        elif ident or en:"),
    ("validation", M, "        elif ident or en or ko:", "        elif en or ko:"),
    ("validation", M, "        name, kind, ident, number, date, en, ko = folded", "        name, kind, ident, number, date, en, ko = raw"),
    # parsing and comments
    ("parsing", M, "    if text.startswith(\"\\ufeff\"):", "    if False:"),
    ("parsing", M, "raw[:-1] if raw.endswith(\"\\r\") else raw", "raw"),
    ("parsing", M, "    if lines and lines[-1] == \"\":\n        lines.pop()", "    if False:\n        lines.pop()"),
    ("parsing", M, "        if len(parts) != len(HEADER):", "        if len(parts) < len(HEADER):"),
    ("parsing", M, "        row[\"line\"] = idx + 1", "        row[\"line\"] = idx + 2"),
    ("parsing", M, "    if not rows:\n        raise InputError(\"fixture_empty\", \"no rows after the header\")", "    if False:\n        raise InputError(\"fixture_empty\", \"no rows after the header\")"),
    ("parsing", M, "        raise InputError(\"fixture_unreadable\", \"fixture text must be str\")", "        text = str(text)"),
    ("comments", M, "        if line.startswith(\"#\"):\n            comments += 1", "        if line.lstrip().startswith(\"#\"):\n            comments += 1"),
    ("comments", M, "            comments += 1\n", "            comments += 2\n"),
    ("comments", M, "        if not line.strip():\n            blanks += 1\n            continue\n        if line != TSV_HEADER:",
     "        if not line.strip():\n            continue\n        if line != TSV_HEADER:"),
    ("comments", M, "        if not line.strip():\n            blanks += 1\n            continue\n        parts",
     "        if not line.strip():\n            continue\n        parts"),
    ("comments", M, "        line = lines[idx]\n", "        line = lines[idx]\n        if line.startswith(\"#\"):\n            continue\n"),
    ("comments", M, "        if line != TSV_HEADER:", "        if line.strip() != TSV_HEADER:"),
    ("comments", M, "    report[\"comment_lines\"] = comments", "    report[\"comment_lines\"] = 0"),
    # folding
    ("folding", M, "    if unicodedata.category(ch) == \"Cf\":", "    if ch in \"\\u200b\\u200c\\u200d\\ufeff\":"),
    ("folding", M, "        if low <= cp <= high:", "        if low < cp < high:"),
    ("folding", M, "    (0x034F, 0x034F),    # combining grapheme joiner\n", ""),
    ("folding", M, "    (0x115F, 0x1160),    # Hangul choseong / jungseong fillers\n", ""),
    ("folding", M, "    (0x3164, 0x3164),    # Hangul filler\n", ""),
    ("folding", M, "    (0xFE00, 0xFE0F),    # variation selectors\n", ""),
    ("folding", M, "    (0xE0000, 0xE0FFF),  # tags and variation selectors supplement\n", ""),
    ("folding", M, "    (0x17B4, 0x17B5),    # Khmer inherent vowels\n", ""),
    ("folding", M, "    (0x180B, 0x180F),    # Mongolian free variation selectors\n", ""),
    ("folding", M, "    (0x2060, 0x206F),    # word joiner block, including unassigned points\n", ""),
    ("folding", M, "    (0xFFA0, 0xFFA0),    # halfwidth Hangul filler\n", ""),
    ("folding", M, "    if ch.isdecimal() and not (\"0\" <= ch <= \"9\"):\n        return str(unicodedata.decimal(ch))\n", ""),
    ("folding", M, "    return unicodedata.normalize(\"NFKC\", ch)", "    return ch"),
    ("folding", M, "    text = unicodedata.normalize(\"NFC\", value)", "    text = value"),
    ("folding", M, "if raw[j] != folded[j])", "if raw[j].strip() != folded[j].strip())"),
    ("folding", M, "        for field, raw, folded in changed:", "        for field, raw, folded in changed[:0]:"),
    ("folding", M, "                name = fold(row[\"list\"])", "                name = row[\"list\"]"),
    # numbers and dates
    ("numbers", M, "_NUM_RE = re.compile(r\"[1-9][0-9]{0,5}\")", "_NUM_RE = re.compile(r\"[0-9]{1,6}\")"),
    ("numbers", M, "_NUM_RE = re.compile(r\"[1-9][0-9]{0,5}\")", "_NUM_RE = re.compile(r\"[1-9][0-9]{0,6}\")"),
    ("numbers", M, "    if _NUM_RE.fullmatch(value) is None:", "    if _NUM_RE.match(value) is None:"),
    ("numbers", M, "    if _NUM_RE.fullmatch(value) is None:", "    if _NUM_RE.search(value.strip()) is None:"),
    ("dates", M, "    m = _DATE_RE.fullmatch(value)", "    m = _DATE_RE.match(value)"),
    ("dates", M, "    except ValueError:\n        return None", "    except TypeError:\n        return None"),
    ("dates", M, "        if kind == \"index\" or date:", "        if date:"),
    ("dates", M, "        if kind == \"index\" or date:", "        if kind == \"index\":"),
    # index-list facts
    ("index", M, "            elif no is not None and id_no != no:", "            elif False:"),
    ("index", M, "            if id_no is None:", "            if False:"),
    ("index", M, "                if present == \"no\":", "                if present == \"never\":"),
    ("index", M, "            for lang, present in ((\"en\", en), (\"ko\", ko)):", "            for lang, present in ((\"en\", en),):"),
    ("index", M, "        low = min(seen)", "        low = 1"),
    ("index", M, "        total = top - low + 1 - len(inside)", "        total = top - low - len(inside)"),
    # declared range (PR review Low L2)
    ("range", M, "        low = min(seen) if first is None else first", "        low = min(seen)"),
    ("range", M, "        top = max(seen) if last is None else last", "        top = max(seen)"),
    ("range", M, "            if no < low or no > top:", "            if no > top:"),
    ("range", M, "            if no < low or no > top:", "            if no < low:"),
    ("range", M, "        inside = [no for no in seen if low <= no <= top]", "        inside = list(seen)"),
    ("range", M, "    if type(value) is not int or not 1 <= value <= MAX_NUMBER:", "    if not isinstance(value, int) or not 1 <= value <= MAX_NUMBER:"),
    ("range", M, "    if type(value) is not int or not 1 <= value <= MAX_NUMBER:", "    if type(value) is not int:"),
    ("range", M, "    if first is not None and last is not None and first > last:", "    if False:"),
    ("range", M, "                if _NUM_RE.fullmatch(v) is None:", "                if not v.isdigit():"),
    ("range", M, "                declared[a] = int(v)", "                declared[a] = None"),
    ("range", M, "        report = run(pos, declared[\"--first\"], declared[\"--last\"])", "        report = run(pos)"),
    ("range", M, "        \"first\": first,", "        \"first\": None,"),
    ("range", M, "    if report.get(\"first\") is not None or report.get(\"last\") is not None:", "    if False:"),
    ("index", M, "        while n <= top and len(missing) < MAX_LIST_SHOWN:", "        while n <= top:"),
    ("index", M, "            if total > MAX_LIST_SHOWN:", "            if total >= MAX_LIST_SHOWN:"),
    ("index", M, "        if first[b][1] < first[a][1]:", "        if first[b][1] <= first[a][1]:"),
    ("index", M, "        if first[b][1] < first[a][1]:", "        if first[b][1] > first[a][1]:"),
    ("index", M, "    for a, b in zip(nums, nums[1:]):", "    for a, b in zip(nums, nums[2:]):"),
    ("index", M, "        if no is not None and day is not None and no not in first:", "        if no is not None and day is not None:"),
    ("index", M, "        if len(by_date[day]) > 1:", "        if len(by_date[day]) > 2:"),
    ("index", M, "        if span > 0:", "        if span > 1:"),
    ("index", M, "            found = lo if span == 1 else", "            found = lo if span else"),
    ("index", M, "if not prev[1] > cur[1]]", "if prev[1] < cur[1]]"),
    ("index", M, "        if kind == \"index\":\n            _index_facts(", "        if True:\n            _index_facts("),
    # close lists: duplicate versus reissue (review verdict section 3 T2)
    ("close", M, "            if len(seen[no]) > 1:", "            if len(seen[no]) > 2:"),
    # PR review M1: a repeat inside one close is INFO counted_twice; inside an index list FAIL
    ("close", M, "                if kind == \"index\":\n                    findings.append(_finding(\"duplicate_listing\"", "                if True:\n                    findings.append(_finding(\"duplicate_listing\""),
    ("close", M, "                if kind == \"index\":\n                    findings.append(_finding(\"duplicate_listing\"", "                if False:\n                    findings.append(_finding(\"duplicate_listing\""),
    ("close", M, "                    findings.append(_finding(\"counted_twice\", name, seen[no][1], no,", "                    findings.append(_finding(\"counted_twice\", name, seen[no][0], no,"),
    ("close", M, "                lines_text = \",\".join(str(x) for x in seen[no])", "                lines_text = \";\".join(str(x) for x in seen[no])"),
    ("close", M, "            if no in seen:\n                seen[no].append(line)", "            if False:\n                seen[no].append(line)"),
    ("close", M, "            if name not in [n for n, _ in named[no]]:", "            if True:"),
    ("close", M, "        if len(where) > 1:", "        if len(where) > 2:"),
    ("close", M, "            if index_dates and no not in index_dates:", "            if False:"),
    ("close", M, "            elif day is not None and index_dates and day not in index_dates[no]:", "            elif False:"),
    ("close", M, "    if closes and not index_dates:", "    if False:"),
    ("close", M, "                    index_dates.setdefault(no, set()).add(day)", "                    pass"),
    # severity and decision
    ("severity", M, "    \"published_late\": INFO,", "    \"published_late\": FAIL,"),
    ("severity", M, "    \"date_gap\": INFO,", "    \"date_gap\": FAIL,"),
    ("severity", M, "    \"reissued\": INFO,", "    \"reissued\": FAIL,"),
    ("severity", M, "    \"counted_twice\": INFO,", "    \"counted_twice\": FAIL,"),
    ("severity", M, "    \"out_of_range\": FAIL,", "    \"out_of_range\": INFO,"),
    ("severity", M, "    \"list_name_form\": INFO,", "    \"list_name_form\": FAIL,"),
    # list names (PR review Low L4)
    ("names", M, "            if _NAME_RE.fullmatch(name) is None:", "            if False:"),
    ("names", M, "            if _NAME_RE.fullmatch(name) is None:", "            if _NAME_RE.match(name) is None:"),
    ("names", M, "_NAME_RE = re.compile(r\"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\")", "_NAME_RE = re.compile(r\"[\\w-]+\")"),
    ("severity", M, "    \"shared_date\": INFO,", "    \"shared_date\": FAIL,"),
    ("severity", M, "    \"listing_order\": INFO,", "    \"listing_order\": FAIL,"),
    ("severity", M, "    \"index_absent\": INFO,", "    \"index_absent\": FAIL,"),
    ("severity", M, "    \"duplicate_listing\": FAIL,", "    \"duplicate_listing\": INFO,"),
    ("severity", M, "    \"missing_number\": FAIL,", "    \"missing_number\": INFO,"),
    ("severity", M, "    \"id_mismatch\": FAIL,", "    \"id_mismatch\": INFO,"),
    ("severity", M, "    \"language_missing\": FAIL,", "    \"language_missing\": INFO,"),
    ("severity", M, "    \"unicode_field\": FAIL,", "    \"unicode_field\": INFO,"),
    ("severity", M, "    \"unparsed_number\": FAIL,", "    \"unparsed_number\": INFO,"),
    ("severity", M, "    \"unparsed_date\": FAIL,", "    \"unparsed_date\": INFO,"),
    ("severity", M, "    \"not_in_index\": FAIL,", "    \"not_in_index\": INFO,"),
    ("severity", M, "    \"date_mismatch\": FAIL,", "    \"date_mismatch\": INFO,"),
    ("severity", M, "        \"decision\": FAIL if counts[FAIL] else PASS,", "        \"decision\": FAIL if counts[FAIL] or counts[INFO] else PASS,"),
    ("severity", M, "EXIT_CODES = {PASS: 0, FAIL: 1, DENY: 2}", "EXIT_CODES = {PASS: 0, FAIL: 1, DENY: 1}"),
    # deny paths
    ("deny", M, "    if not os.path.exists(path):", "    if False:"),
    ("deny", M, "    if type(path) is not str or not path:", "    if False:"),
    ("deny", M, "    except UnicodeDecodeError:\n        raise InputError(\"fixture_unreadable\", \"not UTF-8\")", "    except UnicodeDecodeError:\n        return \"\""),
    ("deny", M, "        raise InputError(\"fixture_unreadable\", type(exc).__name__)", "        return \"\""),
    ("deny", M, "    except (RecursionError, ValueError) as exc:\n        return deny_report(\"input_limit\", type(exc).__name__)", "    except RecursionError as exc:\n        return deny_report(\"input_limit\", type(exc).__name__)"),
    ("deny", M, "    if start is None:", "    if False:"),
    ("deny", M, "            raise _bad(\"line %d: expected the header %r\" % (idx + 1, TSV_HEADER))", "            continue"),
    ("deny", M, "                if owner.setdefault(name, fi) != fi:", "                if False:"),
    ("deny", M, "        if type(paths) is not list or not paths:", "        if not paths:"),
    ("deny", M, "        \"on_expiry\": ON_EXPIRY,\n        \"reason\"", "        \"on_expiry\": \"HOLD\",\n        \"reason\""),
    ("deny", M, "            return EXIT_CODES[DENY]", "            return 0"),
    ("deny", M, "    if bad is None and not pos:", "    if False:"),
    ("deny", M, "            else:\n                bad = \"--format must be text or json\"", "            else:\n                fmt = \"text\""),
    ("deny", M, "        elif a.startswith(\"--\"):", "        elif False:"),
    # output
    ("output", M, "            shown += \",... (%d missing)\" % total", "            shown += \",...\""),
    ("output", M, "    if nums[0] == nums[-1]:\n        return str(nums[0])", "    if False:\n        return str(nums[0])"),
    ("output", M, "    findings.sort(key=lambda f: (SEVERITY_ORDER[f[\"severity\"]],", "    findings.sort(key=lambda f: (0,"),
    ("output", M, "    report[\"blank_lines\"] = blanks", "    report[\"blank_lines\"] = 0"),
    ("output", M, "        out.append(\"list %s kind=%s rows=%d numbers=%s\" % (name, s[\"kind\"], s[\"rows\"], s[\"numbers\"]))", "        pass"),
]


def _copy_tree(dst):
    for name in COPY:
        src = os.path.join(HERE, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, name),
                            ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, os.path.join(dst, name))


def _run_suite(cwd):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q"], cwd=cwd, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    except subprocess.TimeoutExpired:
        return "timeout"
    return proc.returncode


def _read(rel):
    with open(os.path.join(HERE, rel), encoding="utf-8") as fh:
        return fh.read()


CATEGORIES = ("validation", "parsing", "comments", "folding", "numbers", "dates", "index", "range",
              "close", "names", "severity", "deny", "output")


def main():
    problems = []
    for i, (cat, rel, old, new) in enumerate(MUTANTS):
        n = _read(rel).count(old)
        if n != 1:
            problems.append("mutant %d (%s, %s): fragment occurs %d times" % (i + 1, cat, rel, n))
        if cat not in CATEGORIES:
            problems.append("mutant %d: unknown category %s" % (i + 1, cat))
    if problems:
        for p in problems:
            print("HARNESS ERROR " + p)
        return 2
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "base")
        os.mkdir(base)
        _copy_tree(base)
        if _run_suite(base) != 0:
            print("HARNESS ERROR baseline suite does not pass")
            return 2
    totals = {}
    survivors = []
    for i, (cat, rel, old, new) in enumerate(MUTANTS):
        with tempfile.TemporaryDirectory() as td:
            work = os.path.join(td, "m")
            os.mkdir(work)
            _copy_tree(work)
            path = os.path.join(work, rel)
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src.replace(old, new, 1))
            rc = _run_suite(work)
        killed = rc != 0
        k, t = totals.get(cat, (0, 0))
        totals[cat] = (k + (1 if killed else 0), t + 1)
        if not killed:
            survivors.append((i + 1, cat, rel, old.strip()[:70]))
    killed_all = sum(k for k, _ in totals.values())
    for cat in CATEGORIES:
        if cat in totals:
            print("%-10s %d/%d killed" % (cat, totals[cat][0], totals[cat][1]))
    for num, cat, rel, frag in survivors:
        print("SURVIVED #%d %s %s: %s" % (num, cat, rel, frag))
    print("TOTAL %d/%d killed" % (killed_all, len(MUTANTS)))
    return 0 if killed_all == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
