"""w30-wave-chronicle: turn day README rows under experiments/YYYY-MM-DD/README.md into a dated wave chronicle.

Clean-room team sketch (no paper, no upstream code). Stdlib only, file-in/file-out, deterministic.

Scope (v1): day READMEs dated SCOPE_START or later. Earlier day folders use an older table layout; they are listed
under on_unmeasured as legacy_table_format and are never opened. Days outside --from/--to are never opened either.
Inside the scope and the window, any missing, unreadable or malformed input is DENY: exit 2, empty stdout and exactly
one stderr line starting with ERROR. Every timeline entry carries the path and git blob SHA1 of the README it came from.

Usage:
  python3 -B wave_chronicle.py --root DIR [--pins FILE] [--tracks FILE] [--from DATE] [--to DATE]
                               [--base DIR] [--base-pins FILE] [--base-to DATE] [--json]
  python3 -B wave_chronicle.py --case DIR [--tracks FILE] [--from DATE] [--to DATE] [--base-to DATE] [--json]

--root is the experiments/ folder of a frozen snapshot. --pins lists '<blob sha1> <bytes> experiments/<date>/README.md'
lines; when given, every README the run opens must be pinned and must match. --base (or --base-to alone, which reuses
--root) adds a 'what changed' section: entries added, removed, or changed (same path, different row bytes).
--case DIR is shorthand for DIR/experiments plus DIR/pins.txt, DIR/tracks.json, DIR/base/experiments,
DIR/base/pins.txt and the extra flags in DIR/args, each only when present.
"""

import datetime
import hashlib
import json
import os
import re
import stat
import sys
import unicodedata

SCOPE_START = "2026-11-09"
LEGACY_REASON = "legacy_table_format"
FOOTER = "Do not merge experiment PRs without Ork review."
ON_EXPIRY = "DENY"
CAPS = {
    "readme_bytes": {"limit": 65536, "on_expiry": "DENY"},
    "entries_per_day": {"limit": 60, "on_expiry": "DENY"},
    "days": {"limit": 400, "on_expiry": "DENY"},
    "row_chars": {"limit": 4000, "on_expiry": "DENY"},
    "slug_chars": {"limit": 80, "on_expiry": "DENY"},
    "side_file_bytes": {"limit": 65536, "on_expiry": "DENY"},
    "tracks": {"limit": 100, "on_expiry": "DENY"},
    "track_name_chars": {"limit": 40, "on_expiry": "DENY"},
    "args_file_bytes": {"limit": 1024, "on_expiry": "DENY"},
}

DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\Z")
ITEM_RE = re.compile(r"^- \[([^\]]*)\]\(([^)]*)\): (.*)\Z")
WAVE_RE = re.compile(r"^w([0-9]{2})\Z")
TRACK_KEY_RE = re.compile(r"^(?:w[0-9]{2}|[a-z]{2,8}|[0-9]{2})\Z")
PIN_RE = re.compile(r"^([0-9a-f]{40}) ([1-9][0-9]{0,8}) experiments/([0-9]{4}-[0-9]{2}-[0-9]{2})/README\.md\Z")
BAD_CATEGORIES = {"Cc", "Cf", "Co", "Cn", "Cs", "Zl", "Zp"}


class ChronicleError(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, code)
        self.code = code
        self.detail = detail


def git_blob_sha1(data):
    """The git blob id of these bytes: sha1 over 'blob <len>\\0' plus the bytes."""
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


def valid_date(text):
    if not isinstance(text, str) or not DATE_RE.match(text):
        return False
    try:
        datetime.date(int(text[:4]), int(text[5:7]), int(text[8:]))
    except ValueError:
        return False
    return True


def _clean_text(value, where, limit):
    """Free text: NFC-normalised, no control/format/private/unassigned/surrogate characters, only plain spaces."""
    if not isinstance(value, str):
        raise ChronicleError("wrong_type", "%s must be text" % where)
    if value == "" or value != value.strip(" "):
        raise ChronicleError("bad_text", "%s is empty or has edge spaces" % where)
    if len(value) > limit:
        raise ChronicleError("too_long", "%s exceeds %d characters" % (where, limit))
    for ch in value:
        cat = unicodedata.category(ch)
        if cat in BAD_CATEGORIES or (cat == "Zs" and ch != " "):
            raise ChronicleError("bad_char", "%s contains U+%04X" % (where, ord(ch)))
    return unicodedata.normalize("NFC", value)


def _read_bytes(path, cap, what):
    """Open one regular file (no symlinks) and read at most cap bytes; anything else is DENY."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        raise ChronicleError("missing_file", "%s not found: %s" % (what, os.path.basename(path)))
    except OSError:
        raise ChronicleError("unreadable", "%s cannot be read" % what)
    if not stat.S_ISREG(st.st_mode):
        raise ChronicleError("not_a_file", "%s is not a regular file" % what)
    try:
        with open(path, "rb") as fh:
            data = fh.read(cap + 1)
    except OSError:
        raise ChronicleError("unreadable", "%s cannot be read" % what)
    if len(data) > cap:
        raise ChronicleError("too_large", "%s exceeds %d bytes" % (what, cap))
    return data


def _decode(data, what):
    if data.startswith(b"\xef\xbb\xbf"):
        raise ChronicleError("bad_encoding", "%s starts with a byte order mark" % what)
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ChronicleError("bad_encoding", "%s is not valid UTF-8" % what)


def parse_day(date, text):
    """Parse one in-scope day README into entries. The grammar is exact; anything else is DENY."""
    if "\r" in text:
        raise ChronicleError("bad_line_ending", "%s README has a carriage return" % date)
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    if not lines or lines[0] == "":
        raise ChronicleError("bad_heading", "%s README has no heading on line 1" % date)
    if lines[0] != "# experiments/" + date:
        if lines[0].startswith("# experiments/") and valid_date(lines[0][len("# experiments/"):]):
            raise ChronicleError("heading_date_mismatch", "%s README heading names another date" % date)
        raise ChronicleError("bad_heading", "%s README line 1 is not '# experiments/%s'" % (date, date))
    if len(lines) < 2 or lines[1] != "":
        raise ChronicleError("malformed_line", "%s README line 2 must be blank" % date)
    entries = []
    seen = set()
    i = 2
    while i < len(lines) and lines[i].startswith("- "):
        entries.append(_parse_item(date, lines[i], i + 1, seen))
        if len(entries) > CAPS["entries_per_day"]["limit"]:
            raise ChronicleError("too_many", "%s README has more than %d entries"
                                 % (date, CAPS["entries_per_day"]["limit"]))
        i += 1
    if not entries:
        raise ChronicleError("no_entries", "%s README has no entry rows" % date)
    rest = lines[i:]
    if rest and rest != ["", FOOTER]:
        bad = i + 1 if rest[0] != "" or len(rest) == 1 else i + 2
        raise ChronicleError("malformed_line", "%s README line %d is not an entry row or the footer" % (date, bad))
    return entries


def _parse_item(date, line, number, seen):
    where = "%s README line %d" % (date, number)
    if len(line) > CAPS["row_chars"]["limit"]:
        raise ChronicleError("too_long", "%s exceeds %d characters" % (where, CAPS["row_chars"]["limit"]))
    m = ITEM_RE.match(line)
    if not m:
        raise ChronicleError("malformed_item", "%s is not '- [slug](slug/): text'" % where)
    slug, link, body = m.group(1), m.group(2), m.group(3)
    if len(slug) > CAPS["slug_chars"]["limit"]:
        raise ChronicleError("too_long", "%s slug exceeds %d characters" % (where, CAPS["slug_chars"]["limit"]))
    if not SLUG_RE.match(slug):
        raise ChronicleError("bad_slug", "%s slug is not lowercase ASCII words joined by hyphens" % where)
    if link != slug + "/":
        raise ChronicleError("link_mismatch", "%s link is not the slug folder" % where)
    _clean_text(body, where + " text", CAPS["row_chars"]["limit"])
    if slug in seen:
        raise ChronicleError("duplicate_entry", "%s repeats a slug on the same day" % where)
    seen.add(slug)
    family = slug.split("-")[0]
    w = WAVE_RE.match(family)
    return {"date": date, "slug": slug, "family": family, "wave": int(w.group(1)) if w else None, "row": line}


def parse_pins(data):
    text = _decode(data, "pin file")
    if not text.endswith("\n") or text == "\n":
        raise ChronicleError("bad_pin", "pin file must be non-empty lines ending with a newline")
    pins = {}
    last = ""
    for n, line in enumerate(text[:-1].split("\n"), 1):
        m = PIN_RE.match(line)
        if not m or not valid_date(m.group(3)):
            raise ChronicleError("bad_pin", "pin file line %d is not '<sha1> <bytes> experiments/<date>/README.md'" % n)
        date = m.group(3)
        if date in pins:
            raise ChronicleError("duplicate_pin", "pin file line %d repeats %s" % (n, date))
        if date < last:
            raise ChronicleError("unsorted_pins", "pin file line %d is out of date order" % n)
        if date < SCOPE_START:
            raise ChronicleError("bad_pin", "pin file line %d is before the v1 scope %s" % (n, SCOPE_START))
        pins[date] = (m.group(1), int(m.group(2)))
        last = date
    return pins


def _no_constant(name):
    raise ChronicleError("bad_number", "tracks file contains %s" % name)


def _no_number(text):
    raise ChronicleError("wrong_type", "tracks file contains a number")


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ChronicleError("duplicate_key", "tracks file repeats a key")
        out[key] = value
    return out


def parse_tracks(data):
    text = _decode(data, "tracks file")
    try:
        obj = json.loads(text, object_pairs_hook=_pairs, parse_constant=_no_constant, parse_float=_no_number,
                         parse_int=_no_number)
    except ValueError:
        raise ChronicleError("not_json", "tracks file is not JSON")
    except RecursionError:
        raise ChronicleError("too_deep", "tracks file nests too deeply")
    if type(obj) is not dict:
        raise ChronicleError("wrong_type", "tracks file must be a JSON object")
    if len(obj) > CAPS["tracks"]["limit"]:
        raise ChronicleError("too_many", "tracks file has more than %d keys" % CAPS["tracks"]["limit"])
    tracks = {}
    for key in sorted(obj):
        if not TRACK_KEY_RE.match(key):
            raise ChronicleError("bad_key", "tracks key is not a slug prefix")
        tracks[key] = _clean_text(obj[key], "track name for %s" % key, CAPS["track_name_chars"]["limit"])
    return tracks


def list_days(root):
    """Names of the date folders under root. Listing reads no README."""
    try:
        st = os.lstat(root)
    except OSError:
        raise ChronicleError("missing_root", "corpus root not found")
    if not stat.S_ISDIR(st.st_mode):
        raise ChronicleError("missing_root", "corpus root is not a folder")
    try:
        names = sorted(os.listdir(root))
    except OSError:
        raise ChronicleError("unreadable", "corpus root cannot be listed")
    if len(names) > CAPS["days"]["limit"]:
        raise ChronicleError("too_many", "corpus root has more than %d entries" % CAPS["days"]["limit"])
    for name in names:
        if not valid_date(name):
            raise ChronicleError("bad_root_entry", "corpus root holds a name that is not a calendar date")
        if not stat.S_ISDIR(os.lstat(os.path.join(root, name)).st_mode):
            raise ChronicleError("bad_root_entry", "%s is not a folder" % name)
    return names


def load_corpus(root, pins, lo, hi, read=None):
    """Read the in-scope, in-window day READMEs only. Returns (days, not_measured)."""
    read = read or _read_bytes
    names = list_days(root)
    legacy = [d for d in names if d < SCOPE_START]
    measured = [d for d in names if d >= SCOPE_START and lo <= d <= hi]
    outside = [d for d in names if d >= SCOPE_START and not lo <= d <= hi]
    if pins is not None:
        for date in sorted(pins):
            if lo <= date <= hi and date not in names:
                raise ChronicleError("missing_file", "pinned day %s has no folder" % date)
    if not measured:
        raise ChronicleError("no_days_in_window", "no day README dated %s or later inside the window" % SCOPE_START)
    days = []
    for date in measured:
        path = os.path.join(root, date, "README.md")
        data = read(path, CAPS["readme_bytes"]["limit"], "%s README" % date)
        blob = git_blob_sha1(data)
        if pins is not None:
            if date not in pins:
                raise ChronicleError("unpinned_readme", "%s README is not in the pin file" % date)
            if pins[date] != (blob, len(data)):
                raise ChronicleError("pin_mismatch", "%s README bytes do not match the pinned blob" % date)
        entries = parse_day(date, _decode(data, "%s README" % date))
        days.append({"date": date, "path": "experiments/%s/README.md" % date, "blob": blob, "bytes": len(data),
                     "entries": entries})
    return days, {LEGACY_REASON: legacy, "outside_window": outside}


def _count(values):
    out = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return {k: out[k] for k in sorted(out)}


def build_timeline(days, tracks):
    """Flatten days into timeline entries, each tagged with its source path and blob, and count them."""
    entries = []
    for day in days:
        for e in day["entries"]:
            track = tracks.get(e["family"])
            entries.append({"date": e["date"], "slug": e["slug"], "family": e["family"], "wave": e["wave"],
                            "track": track, "notes": [] if track is not None else ["unknown_track"],
                            "source": {"path": day["path"], "blob": day["blob"]}})
    counts = {
        "days": len(days),
        "entries": len(entries),
        "by_date": {d["date"]: len(d["entries"]) for d in days},
        "by_track": _count(e["track"] if e["track"] is not None else "(no track)" for e in entries),
        "by_family": _count(e["family"] for e in entries),
        "by_wave": {("w%02d" % k): v for k, v in _count(e["wave"] for e in entries if e["wave"] is not None).items()},
    }
    return entries, counts


def diff_entries(base_days, days):
    """Added, removed and changed entries between two corpora, keyed by experiments/<date>/<slug>."""
    def index(ds):
        out = {}
        for d in ds:
            for e in d["entries"]:
                out["experiments/%s/%s" % (d["date"], e["slug"])] = (e["row"], d["blob"])
        return out
    old, new = index(base_days), index(days)
    added = [{"entry": k, "blob": new[k][1]} for k in sorted(new) if k not in old]
    removed = [{"entry": k, "base_blob": old[k][1]} for k in sorted(old) if k not in new]
    changed = [{"entry": k, "base_blob": old[k][1], "blob": new[k][1]}
               for k in sorted(new) if k in old and old[k][0] != new[k][0]]
    return {"added": added, "removed": removed, "changed": changed}


def run(opts, read=None):
    tracks = parse_tracks(_read_bytes(opts["tracks"], CAPS["side_file_bytes"]["limit"], "tracks file")) \
        if opts.get("tracks") else {}
    lo, hi = opts.get("from") or "0000-01-01", opts.get("to") or "9999-12-31"
    if lo > hi:
        raise ChronicleError("bad_window", "--from is after --to")
    pins = parse_pins(_read_bytes(opts["pins"], CAPS["side_file_bytes"]["limit"], "pin file")) \
        if opts.get("pins") else None
    days, not_measured = load_corpus(opts["root"], pins, lo, hi, read)
    entries, counts = build_timeline(days, tracks)
    out = {
        "scope": {"from_date": SCOPE_START, "window": {"from": opts.get("from"), "to": opts.get("to")}},
        "pins": ("verified %d/%d" % (len(days), len(days))) if pins is not None else "not given",
        "days": [{"date": d["date"], "path": d["path"], "blob": d["blob"], "bytes": d["bytes"]} for d in days],
        "entries": entries,
        "counts": counts,
        "on_unmeasured": not_measured,
        "on_expiry": ON_EXPIRY,
    }
    if opts.get("base") or opts.get("base_to"):
        base_hi = opts.get("base_to") or hi
        if lo > base_hi:
            raise ChronicleError("bad_window", "--from is after --base-to")
        base_pins = parse_pins(_read_bytes(opts["base_pins"], CAPS["side_file_bytes"]["limit"], "base pin file")) \
            if opts.get("base_pins") else None
        base_days, _ = load_corpus(opts.get("base") or opts["root"], base_pins, lo, base_hi, read)
        out["changed"] = diff_entries(base_days, days)
        out["changed"]["base_to"] = opts.get("base_to")
    return out


def _tag(e):
    head = ("wave %d" % e["wave"]) if e["wave"] is not None else ("family: %s" % e["family"])
    track = e["track"] if e["track"] is not None else "none, INFO unknown_track"
    return "%s, track: %s" % (head, track)


def render(result):
    """The timeline as markdown. Pure function of the result, so output is deterministic."""
    w = result["scope"]["window"]
    lines = ["# Wave chronicle", "",
             "- scope: day READMEs dated %s or later" % result["scope"]["from_date"],
             "- window: %s to %s" % (w["from"] or "first day", w["to"] or "last day"),
             "- pins: %s" % result["pins"], ""]
    by_date = {}
    for e in result["entries"]:
        by_date.setdefault(e["date"], []).append(e)
    for day in result["days"]:
        lines.append("## %s" % day["date"])
        lines.append("")
        for e in by_date[day["date"]]:
            lines.append("- %s (%s) [%s @ %s]" % (e["slug"], _tag(e), e["source"]["path"], e["source"]["blob"]))
        lines.append("")
    c = result["counts"]
    lines += ["## Counts", "", "- days: %d" % c["days"], "- entries: %d" % c["entries"]]
    for key in ("by_date", "by_track", "by_family", "by_wave"):
        lines.append("- %s: %s" % (key, ", ".join("%s %d" % kv for kv in c[key].items()) or "none"))
    lines += ["", "## Not measured", ""]
    for key in (LEGACY_REASON, "outside_window"):
        lines.append("- %s: %s" % (key, ", ".join(result["on_unmeasured"][key]) or "none"))
    if "changed" in result:
        ch = result["changed"]
        lines += ["", "## What changed", ""]
        if ch["base_to"]:
            lines.append("- base: days up to %s" % ch["base_to"])
        for key, field in (("added", "blob"), ("removed", "base_blob"), ("changed", "blob")):
            items = ["%s @ %s" % (x["entry"], x[field]) for x in ch[key]]
            lines.append("- %s: %s" % (key, "; ".join(items) or "none"))
    return "\n".join(lines) + "\n"


VALUE_FLAGS = {"--root": "root", "--pins": "pins", "--tracks": "tracks", "--from": "from", "--to": "to",
               "--base": "base", "--base-pins": "base_pins", "--base-to": "base_to", "--case": "case"}
CASE_ARGS_FLAGS = {"--from", "--to", "--base-to"}


def parse_args(argv):
    opts = {}
    i = 0
    while i < len(argv):
        flag = argv[i]
        if flag == "--json":
            if "json" in opts:
                raise ChronicleError("bad_args", "--json given twice")
            opts["json"] = True
            i += 1
            continue
        if flag not in VALUE_FLAGS:
            raise ChronicleError("bad_args", "unknown argument")
        key = VALUE_FLAGS[flag]
        if key in opts:
            raise ChronicleError("bad_args", "%s given twice" % flag)
        if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
            raise ChronicleError("bad_args", "%s needs a value" % flag)
        opts[key] = argv[i + 1]
        i += 2
    if "case" in opts:
        _apply_case(opts)
    for key in ("from", "to", "base_to"):
        if key in opts and not valid_date(opts[key]):
            raise ChronicleError("bad_args", "--%s is not a calendar date" % key.replace("_", "-"))
    if "root" not in opts:
        raise ChronicleError("bad_args", "--root or --case is required")
    if "base_pins" in opts and "base" not in opts:
        raise ChronicleError("bad_args", "--base-pins needs --base")
    return opts


def _apply_case(opts):
    case = opts["case"]
    for key in ("root", "pins", "base", "base_pins"):
        if key in opts:
            raise ChronicleError("bad_args", "--case cannot be combined with --%s" % key.replace("_", "-"))
    if not os.path.isdir(case):
        raise ChronicleError("missing_root", "case folder not found")
    opts["root"] = os.path.join(case, "experiments")
    if os.path.lexists(os.path.join(case, "pins.txt")):
        opts["pins"] = os.path.join(case, "pins.txt")
    if os.path.lexists(os.path.join(case, "base")):
        opts["base"] = os.path.join(case, "base", "experiments")
        if os.path.lexists(os.path.join(case, "base", "pins.txt")):
            opts["base_pins"] = os.path.join(case, "base", "pins.txt")
    if os.path.lexists(os.path.join(case, "tracks.json")):
        if "tracks" in opts:
            raise ChronicleError("bad_args", "--tracks given twice (case has tracks.json)")
        opts["tracks"] = os.path.join(case, "tracks.json")
    if os.path.lexists(os.path.join(case, "args")):
        text = _decode(_read_bytes(os.path.join(case, "args"), CAPS["args_file_bytes"]["limit"], "case args"),
                       "case args")
        tokens = text.split()
        if len(tokens) % 2:
            raise ChronicleError("bad_args", "case args must be flag/value pairs")
        for flag, value in zip(tokens[::2], tokens[1::2]):
            if flag not in CASE_ARGS_FLAGS:
                raise ChronicleError("bad_args", "case args may set only --from, --to and --base-to")
            key = VALUE_FLAGS[flag]
            if key in opts:
                raise ChronicleError("bad_args", "%s given twice" % flag)
            opts[key] = value


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        opts = parse_args(argv)
        result = run(opts)
        text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=1) + "\n" if opts.get("json") \
            else render(result)
    except ChronicleError as e:
        sys.stderr.write("ERROR %s: %s (on_expiry=%s)\n" % (e.code, e.detail, ON_EXPIRY))
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
