"""w25-daily-issue-index: a file-in/file-out list check of Naru Daily issues.

Reads one or more fixture files (TSV with the header ``list kind id no date en ko``).  A
``kind=index`` list is an issue listing such as the public Daily page: one row per issue with
the anchor id, the printed number, the printed date and whether an EN and a KO body exist.  A
``kind=close`` list names the Daily issues that one day's close reports as having reached
readers (number, and the date if the close gives one).

The check reports facts.  Structural errors are FAIL: an id that differs from the printed
number, a number missing between the lowest and highest listed (or the declared ``first`` and
``last``), a number outside the declared range, one number listed twice in one index list, a
missing language body, a field that cannot be parsed, a close naming a number no index lists,
or a close date that differs from the index date.  Facts that are not errors are INFO: a number
dated before the number below it (``published_late``), a date with no issue (``date_gap``), one
number named in more than one close (``reissued``), one number named more than once in one
close (``counted_twice``, as the annals count a same-day reissue), a list name outside plain
ASCII letters, digits and hyphens (``list_name_form``), and a few listing facts.  It does not decide whether an
issue should have been published; the village's own Daily duty does that.

Decisions: PASS (no FAIL finding, exit 0), FAIL (exit 1), DENY (exit 2).  ``on_expiry`` is
DENY: a missing, unreadable or malformed fixture gives DENY, never a pass.

Every field is folded before parsing: NFC, then default-ignorable characters (format
characters such as the zero-width space, variation selectors, Hangul fillers) are removed,
decimal digits of any script become ASCII digits, and every other character is
NFKC-normalised.  A field that folding changes is FAIL ``unicode_field``.

Python standard library only.  No network, no child processes, no clock, no randomness.
"""

import datetime
import json
import os
import re
import sys
import unicodedata

TOOL = "w25-daily-issue-index"
HEADER = ("list", "kind", "id", "no", "date", "en", "ko")
TSV_HEADER = "\t".join(HEADER)
ON_EXPIRY = "DENY"
KINDS = ("index", "close")
PRESENCE = ("yes", "no")

PASS = "PASS"
FAIL = "FAIL"
DENY = "DENY"
INFO = "INFO"
EXIT_CODES = {PASS: 0, FAIL: 1, DENY: 2}
SEVERITY_ORDER = {FAIL: 0, INFO: 1}

CODE_SEVERITY = {
    "id_mismatch": FAIL,
    "missing_number": FAIL,
    "duplicate_listing": FAIL,
    "out_of_range": FAIL,
    "language_missing": FAIL,
    "unparsed_number": FAIL,
    "unparsed_date": FAIL,
    "unicode_field": FAIL,
    "not_in_index": FAIL,
    "date_mismatch": FAIL,
    "published_late": INFO,
    "date_gap": INFO,
    "reissued": INFO,
    "counted_twice": INFO,
    "shared_date": INFO,
    "listing_order": INFO,
    "index_absent": INFO,
    "list_name_form": INFO,
}

MAX_NUMBER = 999999
MAX_LIST_SHOWN = 20
_NUM_RE = re.compile(r"[1-9][0-9]{0,5}")
_DATE_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_NAME_RE = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")

# Default_Ignorable_Code_Point ranges that are not category Cf (Unicode DerivedCoreProperties).
_IGNORABLE_RANGES = (
    (0x034F, 0x034F),    # combining grapheme joiner
    (0x115F, 0x1160),    # Hangul choseong / jungseong fillers
    (0x17B4, 0x17B5),    # Khmer inherent vowels
    (0x180B, 0x180F),    # Mongolian free variation selectors
    (0x2060, 0x206F),    # word joiner block, including unassigned points
    (0x3164, 0x3164),    # Hangul filler
    (0xFE00, 0xFE0F),    # variation selectors
    (0xFFA0, 0xFFA0),    # halfwidth Hangul filler
    (0xE0000, 0xE0FFF),  # tags and variation selectors supplement
)


class InputError(Exception):
    """Raised for any missing, unreadable or malformed input; always maps to DENY."""

    def __init__(self, reason, detail):
        Exception.__init__(self, reason, detail)
        self.reason = reason
        self.detail = detail


def _bad(detail):
    return InputError("fixture_malformed", detail)


# ---------------------------------------------------------------------------
# Folding
# ---------------------------------------------------------------------------

def ignorable(ch):
    """True for a default-ignorable character (category Cf or a listed range)."""
    if unicodedata.category(ch) == "Cf":
        return True
    cp = ord(ch)
    for low, high in _IGNORABLE_RANGES:
        if low <= cp <= high:
            return True
    return False


def _fold_char(ch):
    if ignorable(ch):
        return ""
    if ch.isdecimal() and not ("0" <= ch <= "9"):
        return str(unicodedata.decimal(ch))
    return unicodedata.normalize("NFKC", ch)


def fold(value):
    """Return the folded form of a field value (the text every check parses)."""
    text = unicodedata.normalize("NFC", value)
    return "".join(_fold_char(ch) for ch in text)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def parse_fixture_text(text):
    """Parse fixture text into (rows, comment_lines, blank_lines).

    ``#`` comment lines exist only before the header.  After the header every non-blank line
    is a row with exactly seven tab-separated fields, including a line that starts with ``#``.
    Blank lines are counted and reported, never dropped silently.
    """
    if type(text) is not str:
        raise InputError("fixture_unreadable", "fixture text must be str")
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = [raw[:-1] if raw.endswith("\r") else raw for raw in text.split("\n")]
    if lines and lines[-1] == "":
        lines.pop()
    comments = 0
    blanks = 0
    start = None
    for idx, line in enumerate(lines):
        if line.startswith("#"):
            comments += 1
            continue
        if not line.strip():
            blanks += 1
            continue
        if line != TSV_HEADER:
            raise _bad("line %d: expected the header %r" % (idx + 1, TSV_HEADER))
        start = idx + 1
        break
    if start is None:
        raise InputError("fixture_empty", "no header")
    rows = []
    for idx in range(start, len(lines)):
        line = lines[idx]
        if not line.strip():
            blanks += 1
            continue
        parts = line.split("\t")
        if len(parts) != len(HEADER):
            raise _bad("line %d: expected %d TSV fields, got %d" % (idx + 1, len(HEADER), len(parts)))
        row = dict(zip(HEADER, parts))
        row["line"] = idx + 1
        rows.append(row)
    if not rows:
        raise InputError("fixture_empty", "no rows after the header")
    return rows, comments, blanks


def validate_rows(rows):
    """Validate rows and return an immutable snapshot (a tuple of tuples).

    Each row must be an exact ``dict`` with exactly the keys of ``HEADER`` plus ``line``.
    Keys must be exact ``str``; field values exact ``str``; ``line`` an exact ``int`` >= 1.
    bool, float (NaN, inf), other types and subclasses are refused.  Structure is checked on
    folded values: ``kind`` in index/close, one kind per list, ``en``/``ko`` yes/no on an index
    row and empty on a close row, ``id`` empty on a close row.  The snapshot shares no mutable
    state with ``rows``.
    """
    if type(rows) is not list and type(rows) is not tuple:
        raise _bad("rows: expected a list")
    if not rows:
        raise InputError("fixture_empty", "no rows")
    want = set(HEADER) | {"line"}
    kinds = {}
    out = []
    for i, row in enumerate(rows):
        where = "row %d" % (i + 1)
        if type(row) is not dict:
            raise _bad(where + ": expected a dict")
        for key in row:
            if type(key) is not str:
                raise _bad(where + ": keys must be exact str")
        if set(row) != want:
            raise _bad(where + ": keys must be exactly " + ",".join(HEADER) + ",line")
        line = row["line"]
        if type(line) is not int or line < 1:
            raise _bad(where + ".line: expected exact int >= 1 (bool and float are rejected)")
        raw = []
        for key in HEADER:
            value = row[key]
            if type(value) is not str:
                raise _bad(where + "." + key + ": expected exact str (bool, int, float, NaN, inf are rejected)")
            if "\t" in value or "\n" in value or "\r" in value:
                raise _bad(where + "." + key + ": control characters are not permitted")
            raw.append(value)
        folded = [fold(v) for v in raw]
        changed = tuple((HEADER[j], raw[j], folded[j]) for j in range(len(HEADER)) if raw[j] != folded[j])
        name, kind, ident, number, date, en, ko = folded
        if not name.strip() or name != name.strip():
            raise _bad("line %d: list name blank or padded" % line)
        if kind not in KINDS:
            raise _bad("line %d: kind must be index or close" % line)
        if kinds.setdefault(name, kind) != kind:
            raise _bad("line %d: list %s mixes kinds" % (line, name))
        if kind == "index":
            if en not in PRESENCE or ko not in PRESENCE:
                raise _bad("line %d: en and ko must be yes or no on an index row" % line)
        elif ident or en or ko:
            raise _bad("line %d: id, en and ko must be empty on a close row" % line)
        out.append((line, name, kind, ident, number, date, en, ko, changed))
    return tuple(out)


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------

def _number(value):
    if _NUM_RE.fullmatch(value) is None:
        return None
    return int(value)


def _date(value):
    m = _DATE_RE.fullmatch(value)
    if m is None:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _span(nums):
    if not nums:
        return "-"
    if nums[0] == nums[-1]:
        return str(nums[0])
    return "%d..%d" % (nums[0], nums[-1])


def _finding(code, name, line, number, found, expected):
    return {
        "code": code,
        "severity": CODE_SEVERITY[code],
        "list": name,
        "line": line,
        "number": number,
        "found": found,
        "expected": expected,
    }


def _declared(value, what):
    """A declared first/last number: None, or an exact int 1..MAX_NUMBER (bool is refused)."""
    if value is None:
        return None
    if type(value) is not int or not 1 <= value <= MAX_NUMBER:
        raise InputError("bad_range", what + ": expected an exact int 1..%d" % MAX_NUMBER)
    return value


def check(snapshot, first=None, last=None):
    """Check a validated snapshot and return the report (a dict).

    ``first`` and ``last`` optionally declare the expected number range of every index list.
    """
    first = _declared(first, "first")
    last = _declared(last, "last")
    if first is not None and last is not None and first > last:
        raise InputError("bad_range", "first is above last")
    findings = []
    order = []
    lists = {}
    for line, name, kind, ident, number, date, en, ko, changed in snapshot:
        for field, raw, folded in changed:
            findings.append(_finding("unicode_field", name, line, None, field + "=" + repr(raw),
                                     field + "=" + repr(folded)))
        no = _number(number)
        if no is None:
            findings.append(_finding("unparsed_number", name, line, None, "no=" + repr(number),
                                     "a plain number 1..%d" % MAX_NUMBER))
        day = None
        if kind == "index" or date:
            day = _date(date)
            if day is None:
                findings.append(_finding("unparsed_date", name, line, no, "date=" + repr(date),
                                         "a calendar date YYYY-MM-DD"))
        if kind == "index":
            id_no = _number(ident)
            if id_no is None:
                findings.append(_finding("unparsed_number", name, line, no, "id=" + repr(ident),
                                         "a plain number 1..%d" % MAX_NUMBER))
            elif no is not None and id_no != no:
                findings.append(_finding("id_mismatch", name, line, no, "id=%d no=%d" % (id_no, no),
                                         "id equal to the printed number"))
            for lang, present in (("en", en), ("ko", ko)):
                if present == "no":
                    findings.append(_finding("language_missing", name, line, no, lang + "=no",
                                             lang + " body present"))
        if name not in lists:
            lists[name] = (kind, [])
            order.append(name)
            if _NAME_RE.fullmatch(name) is None:
                findings.append(_finding("list_name_form", name, line, None, "list=" + ascii(name),
                                         "a fact; list names are usually ASCII letters, digits and hyphens"))
        lists[name][1].append((line, no, day))

    index_dates = {}
    for name in order:
        kind, rows = lists[name]
        seen = {}
        for line, no, day in rows:
            if no is None:
                continue
            if no in seen:
                seen[no].append(line)
            else:
                seen[no] = [line]
        for no in sorted(seen):
            if len(seen[no]) > 1:
                lines_text = ",".join(str(x) for x in seen[no])
                if kind == "index":
                    findings.append(_finding("duplicate_listing", name, seen[no][1], no,
                                             "No. %d listed %d times (lines %s)" % (
                                                 no, len(seen[no]), lines_text),
                                             "each number once in one list"))
                else:
                    findings.append(_finding("counted_twice", name, seen[no][1], no,
                                             "Daily %d named %d times in %s (lines %s)" % (
                                                 no, len(seen[no]), name, lines_text),
                                             "a fact; a close may count a same-day reissue again"))
        if kind == "index":
            _index_facts(name, rows, seen, findings, first, last)
            for line, no, day in rows:
                if no is not None and day is not None:
                    index_dates.setdefault(no, set()).add(day)

    closes = [n for n in order if lists[n][0] == "close"]
    if closes and not index_dates:
        findings.append(_finding("index_absent", "", 0, None, "%d close list(s), no index list" % len(closes),
                                 "an index list for not_in_index and date_mismatch"))
    named = {}
    for name in closes:
        for line, no, day in lists[name][1]:
            if no is None:
                continue
            named.setdefault(no, [])
            if name not in [n for n, _ in named[no]]:
                named[no].append((name, line))
            if index_dates and no not in index_dates:
                findings.append(_finding("not_in_index", name, line, no, "No. %d" % no,
                                         "a number listed in an index list"))
            elif day is not None and index_dates and day not in index_dates[no]:
                findings.append(_finding("date_mismatch", name, line, no,
                                         "No. %d · %s" % (no, day.isoformat()),
                                         "No. %d · %s" % (no, ",".join(sorted(d.isoformat() for d in index_dates[no])))))
    for no in sorted(named):
        where = named[no]
        if len(where) > 1:
            findings.append(_finding("reissued", where[1][0], where[1][1], no,
                                     "Daily %d named in %s" % (no, ", ".join(n for n, _ in where)),
                                     "a fact; not a duplicate listing"))

    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], order.index(f["list"]) if f["list"] in lists else -1,
                                 f["line"], f["code"], f["found"]))
    counts = {FAIL: 0, INFO: 0}
    for f in findings:
        counts[f["severity"]] += 1
    summary = {}
    for name in order:
        kind, rows = lists[name]
        nums = sorted({no for _, no, _ in rows if no is not None})
        summary[name] = {"kind": kind, "rows": len(rows),
                         "numbers": _span(nums)}
    return {
        "tool": TOOL,
        "decision": FAIL if counts[FAIL] else PASS,
        "on_expiry": ON_EXPIRY,
        "first": first,
        "last": last,
        "rows": len(snapshot),
        "lists": summary,
        "list_order": order,
        "counts": counts,
        "findings": findings,
    }


def _index_facts(name, rows, seen, findings, first=None, last=None):
    """Missing and out-of-range numbers (FAIL) and the INFO facts of one index list."""
    if seen:
        low = min(seen) if first is None else first
        top = max(seen) if last is None else last
        for no in sorted(seen):
            if no < low or no > top:
                findings.append(_finding("out_of_range", name, seen[no][0], no, "No. %d" % no,
                                         "a number in the declared range %d..%d" % (low, top)))
        inside = [no for no in seen if low <= no <= top]
        missing = []
        n = low
        while n <= top and len(missing) < MAX_LIST_SHOWN:
            if n not in seen:
                missing.append(n)
            n += 1
        total = top - low + 1 - len(inside)
        if total:
            shown = ",".join(str(x) for x in missing)
            if total > MAX_LIST_SHOWN:
                shown += ",... (%d missing)" % total
            findings.append(_finding("missing_number", name, 0, None, "missing " + shown,
                                     "%d..%d contiguous" % (low, top)))
    first = {}
    for line, no, day in rows:
        if no is not None and day is not None and no not in first:
            first[no] = (line, day)
    nums = sorted(first)
    for a, b in zip(nums, nums[1:]):
        if first[b][1] < first[a][1]:
            findings.append(_finding("published_late", name, first[b][0], b,
                                     "No. %d · %s" % (b, first[b][1].isoformat()),
                                     "dated on or after No. %d · %s" % (a, first[a][1].isoformat())))
    by_date = {}
    for no in nums:
        by_date.setdefault(first[no][1], []).append(no)
    for day in sorted(by_date):
        if len(by_date[day]) > 1:
            findings.append(_finding("shared_date", name, first[by_date[day][1]][0], by_date[day][1],
                                     "%s on No. %s" % (day.isoformat(), ",".join(str(x) for x in by_date[day])),
                                     "a fact; one date per number"))
    days = sorted(by_date)
    for d1, d2 in zip(days, days[1:]):
        span = d2.toordinal() - d1.toordinal() - 1
        if span > 0:
            lo = datetime.date.fromordinal(d1.toordinal() + 1).isoformat()
            hi = datetime.date.fromordinal(d2.toordinal() - 1).isoformat()
            found = lo if span == 1 else "%s..%s (%d days)" % (lo, hi, span)
            findings.append(_finding("date_gap", name, 0, None, found,
                                     "a fact; no issue dated between %s and %s" % (d1.isoformat(), d2.isoformat())))
    listed = [(line, no) for line, no, _ in rows if no is not None]
    breaks = [cur for prev, cur in zip(listed, listed[1:]) if not prev[1] > cur[1]]
    if breaks:
        findings.append(_finding("listing_order", name, breaks[0][0], breaks[0][1],
                                 "%d of %d adjacent pairs not newest-first" % (len(breaks), len(listed) - 1),
                                 "a fact; listing by number, highest first"))


# ---------------------------------------------------------------------------
# File in / file out
# ---------------------------------------------------------------------------

def deny_report(reason, detail):
    return {
        "tool": TOOL,
        "decision": DENY,
        "on_expiry": ON_EXPIRY,
        "reason": reason,
        "detail": detail,
    }


def _read_text(path):
    if type(path) is not str or not path:
        raise InputError("fixture_missing", "no path given")
    if not os.path.exists(path):
        raise InputError("fixture_missing", "file not found")
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise InputError("fixture_unreadable", type(exc).__name__)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise InputError("fixture_unreadable", "not UTF-8")


def run(paths, first=None, last=None):
    """Read every fixture and check them together. Any input problem returns a DENY report.

    ``first`` and ``last`` optionally declare the expected number range of every index list.
    """
    try:
        if type(paths) is not list or not paths:
            raise InputError("fixture_missing", "no fixture given")
        rows = []
        comments = 0
        blanks = 0
        owner = {}
        for fi, path in enumerate(paths):
            file_rows, c, b = parse_fixture_text(_read_text(path))
            for row in file_rows:
                name = fold(row["list"])
                if owner.setdefault(name, fi) != fi:
                    raise _bad("list %s appears in more than one fixture file" % name)
            rows.extend(file_rows)
            comments += c
            blanks += b
        snapshot = validate_rows(rows)
        report = check(snapshot, first, last)
    except InputError as exc:
        return deny_report(exc.reason, exc.detail)
    except (RecursionError, ValueError) as exc:
        return deny_report("input_limit", type(exc).__name__)
    report["files"] = len(paths)
    report["comment_lines"] = comments
    report["blank_lines"] = blanks
    return report


def format_text(report):
    out = ["%s decision=%s on_expiry=%s" % (TOOL, report["decision"], report["on_expiry"])]
    if report["decision"] == DENY:
        out.append("reason=%s detail=%s" % (report["reason"], report["detail"]))
        return "\n".join(out) + "\n"
    c = report["counts"]
    kinds = [report["lists"][n]["kind"] for n in report["list_order"]]
    out.append("files=%d rows=%d lists=%d (index=%d close=%d) comment_lines=%d blank_lines=%d FAIL=%d INFO=%d" % (
        report["files"], report["rows"], len(kinds), kinds.count("index"), kinds.count("close"),
        report["comment_lines"], report["blank_lines"], c[FAIL], c[INFO]))
    if report.get("first") is not None or report.get("last") is not None:
        out.append("declared first=%s last=%s" % (report.get("first"), report.get("last")))
    for f in report["findings"]:
        where = ("L%d" % f["line"]) if f["line"] else "--"
        num = "" if f["number"] is None else " %d" % f["number"]
        out.append("%-4s %-5s %s %s%s found=%r expected=%r" % (
            f["severity"], where, f["code"], f["list"] or "-", num, f["found"], f["expected"]))
    for name in report["list_order"]:
        s = report["lists"][name]
        out.append("list %s kind=%s rows=%d numbers=%s" % (name, s["kind"], s["rows"], s["numbers"]))
    return "\n".join(out) + "\n"


def format_json(report):
    return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


USAGE = ("usage: python3 -B issue_index.py FIXTURE [FIXTURE ...] [--first N] [--last N] "
         "[--out PATH] [--format text|json]")


def main(argv):
    pos = []
    out_path = None
    fmt = "text"
    declared = {"--first": None, "--last": None}
    args = list(argv)
    bad = None
    while args:
        a = args.pop(0)
        if a in ("--out", "--format", "--first", "--last"):
            if not args:
                bad = a + " needs a value"
                break
            v = args.pop(0)
            if a in declared:
                if _NUM_RE.fullmatch(v) is None:
                    bad = a + " must be a plain number 1..%d" % MAX_NUMBER
                    break
                declared[a] = int(v)
            elif a == "--out":
                out_path = v
            elif v in ("text", "json"):
                fmt = v
            else:
                bad = "--format must be text or json"
                break
        elif a.startswith("--"):
            bad = "unknown option " + a
            break
        else:
            pos.append(a)
    if bad is None and not pos:
        bad = "expected at least one FIXTURE"
    if bad is not None:
        report = deny_report("usage", bad)
        sys.stderr.write(USAGE + "\n")
    else:
        report = run(pos, declared["--first"], declared["--last"])
    text = format_json(report) if fmt == "json" else format_text(report)
    data = text.encode("utf-8")
    if out_path is not None:
        try:
            with open(out_path, "wb") as fh:
                fh.write(data)
        except OSError:
            sys.stderr.write("cannot write report; decision=DENY\n")
            return EXIT_CODES[DENY]
    else:
        sys.stdout.buffer.write(data)
        sys.stdout.flush()
    return EXIT_CODES[report["decision"]]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
