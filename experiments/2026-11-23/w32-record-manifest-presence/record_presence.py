"""w32-record-manifest-presence: does the folder hold every file its record cover names?

A read-only presence check. Inputs are local files only: a record cover in Markdown with a '## Files' pipe table, a
listing of the record folder (one filename per line) and, optionally, an ignore-rule file in .gitignore syntax.

- Every file the cover names that the listing lacks is FAIL missing_named_file, reported with its cover group.
- A missing receipt the cover names is FAIL missing_receipt.
- A miss that an ignore rule explains is tagged INFO ignored_by_pattern <pattern> (it stays FAIL).
- Brace names expand per file: `x_{a,b}.json` names x_a.json and x_b.json.
- A token that is not one filename (a range such as `CORRECTION_01...03`, a '+' note about in-file additions, loose
  words) is INFO unparsed_name: never FAIL and never silently dropped.
- Files listed but not named are INFO listed_not_named. A Corrections group is optional.

It never creates, writes or restores files, hashes nothing, and makes no network call. Malformed, missing or
unreadable input is on_expiry DENY: exit 2, empty stdout, one stderr line 'ERROR <code>: ...'. Clean-room, stdlib only.
"""

import fnmatch
import json
import re
import sys
import unicodedata

ON_EXPIRY = "DENY"
CAPS = {
    "input_bytes": {"limit": 65536, "on_expiry": "DENY"},
    "table_rows": {"limit": 50, "on_expiry": "DENY"},
    "named_files": {"limit": 500, "on_expiry": "DENY"},
    "listing_names": {"limit": 2000, "on_expiry": "DENY"},
    "ignore_lines": {"limit": 1000, "on_expiry": "DENY"},
    "name_chars": {"limit": 255, "on_expiry": "DENY"},
}
INVISIBLE = {"Cc", "Cf", "Co", "Cs", "Cn", "Zl", "Zp"}
HEADING_RE = re.compile(r"^##[ \t]+Files[ \t]*$")
SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
NOTE_RE = re.compile(r"^\s*(?:\((?P<note>[^()]*)\))?\s*[,+]?\s*$")
BRACE_RE = re.compile(r"\{([^{}]*)\}")
NAME_RE = re.compile(r"^[^\W][\w.\-]*$")
# A token that still reads as one file (a stem and an extension) is checked, even with a space, '@', '+', '~', '=' or
# a leading dot, or with a folder path in front (then its last segment is checked). Ranges, globs and lists are not.
LOOSE_NAME_RE = re.compile(r"^(?! )[^/\\*?\[\],{}`|\u2026]*(?<! )\.[A-Za-z0-9]{1,10}$")
LOOSE_DIR_RE = re.compile(r"^(?! )[^/\\*?\[\],{}`|\u2026]+(?<! )$")
CORRECTIONS = "corrections"


class PresenceError(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- reading

def read_text(path, what):
    limit = CAPS["input_bytes"]["limit"]
    try:
        with open(path, "rb") as fh:
            data = fh.read(limit + 1)
    except OSError:
        raise PresenceError("unreadable", "%s is missing or cannot be read" % what)
    if len(data) > limit:
        raise PresenceError("too_large", "%s is larger than %d bytes (on_expiry DENY)" % (what, limit))
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise PresenceError("bad_encoding", "%s is not valid UTF-8" % what)
    if text.startswith("\ufeff"):
        raise PresenceError("bad_encoding", "%s starts with a byte-order mark" % what)
    return text


def _invisible(text):
    return any(unicodedata.category(ch) in INVISIBLE for ch in text)


# ---------------------------------------------------------------- cover

def _cells(line):
    body = line.strip()
    if not (body.startswith("|") and body.endswith("|")) or len(body) < 2:
        return None
    return [c.strip() for c in body[1:-1].split("|")]


def _expand(token):
    """One backtick token -> (list of names, None) or (None, reason it is not one filename)."""
    if len(token) > CAPS["name_chars"]["limit"]:
        return None, "longer than %d characters" % CAPS["name_chars"]["limit"]
    groups = BRACE_RE.findall(token)
    stripped = BRACE_RE.sub("", token)
    if "{" in stripped or "}" in stripped:
        return None, "unbalanced or nested braces"
    names = [""]
    pieces = BRACE_RE.split(token)
    for n, piece in enumerate(pieces):
        if n % 2 == 0:
            names = [x + piece for x in names]
            continue
        alts = piece.split(",")
        if len(alts) < 2 or any(a == "" for a in alts):
            return None, "a brace group needs two or more non-empty choices"
        names = [x + a for x in names for a in alts]
        if len(names) > CAPS["named_files"]["limit"]:
            raise PresenceError("too_many_names", "brace expansion passes %d names (on_expiry DENY)"
                                % CAPS["named_files"]["limit"])
    out = []
    for name in names:
        if ".." in name:
            return None, "not a single filename"
        if NAME_RE.match(name):
            out.append(name)
            continue
        segs = name.split("/")
        if LOOSE_NAME_RE.match(segs[-1]) and all(LOOSE_DIR_RE.match(d) for d in segs[:-1]):
            out.append(segs[-1])
            continue
        return None, "not a single filename"
    return out, None


def parse_cover(text):
    lines = text.split("\n")
    title, fenced, starts = None, False, []
    for n, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if title is None and line.startswith("# "):
            title = line[2:].strip()
        if HEADING_RE.match(line):
            starts.append(n)
    if not starts:
        raise PresenceError("no_files_table", "cover has no '## Files' section")
    if len(starts) > 1:
        raise PresenceError("two_files_tables", "cover has more than one '## Files' section")
    n = starts[0] + 1
    while n < len(lines) and lines[n].strip() == "":
        n += 1
    header = _cells(lines[n]) if n < len(lines) else None
    if header is None:
        raise PresenceError("no_files_table", "'## Files' is not followed by a pipe table")
    lowered = [h.lower() for h in header]
    if lowered.count("group") != 1 or lowered.count("files") != 1:
        raise PresenceError("bad_files_header", "the Files table needs one 'Group' and one 'Files' column")
    gcol, fcol = lowered.index("group"), lowered.index("files")
    sep = _cells(lines[n + 1]) if n + 1 < len(lines) else None
    if sep is None or len(sep) != len(header) or not all(SEPARATOR_CELL_RE.match(c) for c in sep):
        raise PresenceError("bad_files_header", "the Files table header has no separator row")
    rows = []
    n += 2
    while n < len(lines) and lines[n].lstrip().startswith("|"):
        cells = _cells(lines[n])
        if cells is None or len(cells) != len(header):
            raise PresenceError("bad_table_row", "Files table row %d has the wrong number of cells" % (len(rows) + 1))
        rows.append(cells)
        if len(rows) > CAPS["table_rows"]["limit"]:
            raise PresenceError("too_many_rows", "Files table has more than %d rows (on_expiry DENY)"
                                % CAPS["table_rows"]["limit"])
        n += 1
    if not rows:
        raise PresenceError("empty_files_table", "the Files table has no rows")
    named, unparsed, groups, seen = [], [], [], set()
    for r, cells in enumerate(rows):
        group = cells[gcol]
        if group == "" or _invisible(group):
            raise PresenceError("empty_group", "Files table row %d has an empty or invisible group" % (r + 1))
        group = unicodedata.normalize("NFC", group)
        if group in groups:
            raise PresenceError("duplicate_group", "group %r appears twice" % group)
        groups.append(group)
        cell = cells[fcol]
        parts = cell.split("`")
        if len(parts) % 2 == 0:
            raise PresenceError("bad_cell", "group %r has an unclosed backtick" % group)
        previous = None
        for p, part in enumerate(parts):
            if p % 2 == 0:
                m = NOTE_RE.match(part)
                if part.strip() == "":
                    continue
                if m is None or (p == 0 and part.strip() != ""):
                    unparsed.append({"group": group, "token": part.strip(), "after": previous,
                                     "why": "text outside a backtick name"})
                elif m.group("note") is not None and m.group("note").strip().startswith("+"):
                    unparsed.append({"group": group, "token": "(%s)" % m.group("note").strip(), "after": previous,
                                     "why": "names additions that are not separate files"})
                continue
            if _invisible(part):
                raise PresenceError("bad_name", "group %r names a file with an invisible or control character"
                                    % group)
            token = unicodedata.normalize("NFC", part)
            names, why = _expand(token)
            if names is None:
                unparsed.append({"group": group, "token": token, "after": None, "why": why})
                previous = token
                continue
            for name in names:
                if name in seen:
                    raise PresenceError("duplicate_name", "the cover names %r twice" % name)
                seen.add(name)
                named.append({"name": name, "group": group, "token": token})
                if len(named) > CAPS["named_files"]["limit"]:
                    raise PresenceError("too_many_names", "the cover names more than %d files (on_expiry DENY)"
                                        % CAPS["named_files"]["limit"])
            previous = token
    return {"title": title, "groups": groups, "named": named, "unparsed": unparsed}


# ---------------------------------------------------------------- listing and ignore rules

def parse_listing(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) > CAPS["listing_names"]["limit"]:
        raise PresenceError("too_many_listing_names", "listing has more than %d names (on_expiry DENY)"
                            % CAPS["listing_names"]["limit"])
    names = []
    for n, line in enumerate(lines):
        if line.strip() == "":
            raise PresenceError("blank_listing_line", "listing line %d is blank" % (n + 1))
        if _invisible(line) or "/" in line or line != line.strip() or len(line) > CAPS["name_chars"]["limit"]:
            raise PresenceError("bad_listing_name", "listing line %d is not one plain filename" % (n + 1))
        name = unicodedata.normalize("NFC", line)
        if name in names:
            raise PresenceError("duplicate_listing_name", "listing names %r twice" % name)
        names.append(name)
    return names


def parse_ignore(text):
    lines = text.split("\n")
    if len(lines) > CAPS["ignore_lines"]["limit"]:
        raise PresenceError("too_many_ignore_lines", "ignore file has more than %d lines (on_expiry DENY)"
                            % CAPS["ignore_lines"]["limit"])
    rules = []
    for n, raw in enumerate(lines):
        if _invisible(raw):
            raise PresenceError("bad_ignore_line", "ignore line %d holds an invisible or control character" % (n + 1))
        line = raw.rstrip(" ")
        if line == "" or line.startswith("#"):
            continue
        negate = line.startswith("!")
        body = line[1:] if negate else line
        if body in ("", "/", "!"):
            raise PresenceError("bad_ignore_line", "ignore line %d has no pattern" % (n + 1))
        rules.append({"line": n + 1, "text": line, "negate": negate, "dir_only": body.endswith("/"),
                      "body": body.rstrip("/")})
    return rules


def _match_segments(pat, path):
    if not pat:
        return not path
    if pat[0] == "**":
        return any(_match_segments(pat[1:], path[i:]) for i in range(len(path) + 1))
    return bool(path) and fnmatch.fnmatchcase(path[0], pat[0]) and _match_segments(pat[1:], path[1:])


def rule_matches(rule, name, record_path):
    """Own matcher, no git: a pattern without '/' tests the filename at any depth; one with '/' tests the full path."""
    if rule["dir_only"]:
        return False
    body = rule["body"]
    if "/" not in body:
        return _match_segments([body], [name])
    if record_path is None:
        return False
    full = record_path.split("/") + [name]
    return _match_segments(body.lstrip("/").split("/"), full)


def explain(rules, name, record_path):
    """The last matching rule decides; a matching '!' rule means the name is not ignored."""
    decided = None
    for rule in rules:
        if rule_matches(rule, name, record_path):
            decided = rule
    if decided is None or decided["negate"]:
        return None
    return decided["text"]


# ---------------------------------------------------------------- check and report

def check(cover, listing, rules=None, record_path=None, receipt_name=None):
    present = set(listing)
    findings = []
    named_names = [f["name"] for f in cover["named"]]
    for f in cover["named"]:
        if f["name"] in present:
            continue
        is_receipt = f["name"] == receipt_name or "receipt" in f["name"].lower()
        row = {"level": "FAIL", "code": "missing_receipt" if is_receipt else "missing_named_file",
               "name": f["name"], "group": f["group"], "ignored_by_pattern": None}
        if rules is not None:
            row["ignored_by_pattern"] = explain(rules, f["name"], record_path)
        findings.append(row)
    for u in cover["unparsed"]:
        findings.append({"level": "INFO", "code": "unparsed_name", "name": u["token"], "group": u["group"],
                         "after": u["after"], "why": u["why"]})
    if receipt_name is not None and receipt_name not in named_names:
        findings.append({"level": "INFO", "code": "receipt_not_named", "name": receipt_name, "group": None})
    for name in sorted(present - set(named_names)):
        findings.append({"level": "INFO", "code": "listed_not_named", "name": name, "group": None})
    fails = sum(1 for f in findings if f["level"] == "FAIL")
    has_corrections = any(g.lower().startswith(CORRECTIONS) for g in cover["groups"])
    return {"title": cover["title"], "groups": cover["groups"], "named": len(cover["named"]), "listed": len(listing),
            "missing": fails, "unparsed": len(cover["unparsed"]), "findings": findings,
            "corrections_group": "present" if has_corrections else "absent (optional, not required)",
            "ignore_rules": None if rules is None else len(rules), "record_path": record_path,
            "result": "FAIL" if fails else "PASS", "on_expiry": ON_EXPIRY}


def report(res):
    out = ["# Record file presence", "",
           "record: %s" % (res["title"] or "(no title line)"),
           "groups: %s" % "; ".join(res["groups"]),
           "named: %d  listed: %d  missing: %d  unparsed: %d" % (res["named"], res["listed"], res["missing"],
                                                                res["unparsed"]),
           "corrections group: %s" % res["corrections_group"],
           "ignore rules: %s" % ("not given" if res["ignore_rules"] is None else res["ignore_rules"]),
           ""]
    for f in res["findings"]:
        if f["level"] == "FAIL":
            line = "FAIL %s %s (group: %s)" % (f["code"], f["name"], f["group"])
            if f["ignored_by_pattern"] is not None:
                line += "; INFO ignored_by_pattern %s" % f["ignored_by_pattern"]
        elif f["code"] == "unparsed_name":
            line = "INFO unparsed_name \"%s\" (group: %s%s; %s)" % (
                f["name"], f["group"], "" if f["after"] is None else ", after %s" % f["after"], f["why"])
        else:
            line = "INFO %s %s" % (f["code"], f["name"])
        out.append(line)
    out += ["", "result: %s" % res["result"],
            "scope: absent from this listing only; this does not say the files never existed, that any result is "
            "wrong, or what the missing files contain",
            "on_expiry: %s" % res["on_expiry"]]
    return "\n".join(out) + "\n"


def _check_record_path(value):
    parts = value.split("/")
    if value == "" or _invisible(value) or any(p in ("", ".", "..") or not NAME_RE.match(p) for p in parts):
        raise PresenceError("bad_record_path", "--record-path must be a relative folder path such as research/x")
    return value


def parse_args(args):
    opts = {"json": False, "cover": None, "listing": None, "ignore": None, "record_path": None, "receipt_name": None}
    flags = {"--cover": "cover", "--listing": "listing", "--ignore": "ignore", "--record-path": "record_path",
             "--receipt-name": "receipt_name"}
    n = 0
    while n < len(args):
        a = args[n]
        if a == "--json" and not opts["json"]:
            opts["json"] = True
            n += 1
        elif a in flags and opts[flags[a]] is None and n + 1 < len(args):
            opts[flags[a]] = args[n + 1]
            n += 2
        else:
            raise PresenceError("usage", "usage: record_presence.py --cover FILE --listing FILE [--ignore FILE] "
                                         "[--record-path PATH] [--receipt-name NAME] [--json]")
    if opts["cover"] is None or opts["listing"] is None:
        raise PresenceError("usage", "--cover and --listing are both required")
    return opts


def run(opts):
    cover = parse_cover(read_text(opts["cover"], "cover"))
    listing = parse_listing(read_text(opts["listing"], "listing"))
    rules = None if opts["ignore"] is None else parse_ignore(read_text(opts["ignore"], "ignore file"))
    record_path = None if opts["record_path"] is None else _check_record_path(opts["record_path"])
    receipt = opts["receipt_name"]
    if receipt is not None and (_invisible(receipt) or not NAME_RE.match(receipt) or ".." in receipt):
        raise PresenceError("bad_receipt_name", "--receipt-name must be one plain filename")
    return check(cover, listing, rules, record_path, receipt)


def main(argv):
    try:
        opts = parse_args(argv[1:])
        res = run(opts)
    except PresenceError as e:
        sys.stderr.write("ERROR %s: %s (on_expiry=DENY)\n" % (e.code, e.detail))
        return 2
    if opts["json"]:
        sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    else:
        sys.stdout.write(report(res))
    return 1 if res["result"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
