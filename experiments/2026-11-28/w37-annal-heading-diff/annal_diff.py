"""Two-snapshot diff of headed markdown entries (annals or Daily-like folders).

Stdlib only, file-in/file-out, deterministic: sorted paths, no clock, no
randomness, no network. A retitled entry whose body bytes did not change is
reported as `renamed`, not as a deletion plus a new entry.

Usage:
    python3 -B annal_diff.py --before DIR --after DIR --pins FILE [--json]

Exit 0 prints the report (changes.md, or JSON with --json). Any malformed,
unreadable or unpinned input is on_expiry=DENY: exit 2, empty stdout, one
stderr line `DENY <code>: <detail>`.
"""

import hashlib
import json
import os
import re
import sys
from collections import namedtuple

MAX_FILE_BYTES = 65536
MAX_ENTRIES_PER_FILE = 80
MAX_FILES_PER_TREE = 200
MAX_TEXT_CHARS = 4000
MAX_DEPTH = 8
MAX_PINS_BYTES = 65536
ON_EXPIRY = "DENY"
ON_EXPIRY_SET = ("DENY", "SAFE_FALLBACK", "ESCALATE", "HOLD")

ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TITLE_RE = re.compile(r"# \S(?:.*\S)?")
PATH_PART_RE = re.compile(r"[A-Za-z0-9._-]+")
HEX64_RE = re.compile(r"[0-9a-f]{64}")
SIZE_RE = re.compile(r"0|[1-9][0-9]{0,9}")
SIDES = ("before", "after")
CLASSES = ("renamed", "moved", "edited", "added", "removed")

Entry = namedtuple("Entry", "path heading ident body digest")


class Deny(Exception):
    """A refusal with a short code; rendered as one `DENY <code>: <detail>` line."""

    def __init__(self, code, detail):
        super().__init__(code, detail)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- trees and pins

def walk_tree(root, side):
    """Sorted relative `.md` paths under root. Iterative walk with a depth cap."""
    if not isinstance(root, str) or os.path.islink(root) or not os.path.isdir(root):
        raise Deny("missing_tree", "%s tree is missing or not a directory" % side)
    found = []
    stack = [("", 0)]
    while stack:
        rel_dir, depth = stack.pop()
        abs_dir = os.path.join(root, *rel_dir.split("/")) if rel_dir else root
        try:
            with os.scandir(abs_dir) as it:
                items = sorted(it, key=lambda e: e.name)
            kinds = [(e.name, e.is_symlink(), e.is_dir(follow_symlinks=False),
                      e.is_file(follow_symlinks=False)) for e in items]
        except OSError as exc:
            raise Deny("unreadable", "%s/%s: %s" % (side, rel_dir, exc.__class__.__name__))
        for name, is_link, is_dir, is_file in kinds:
            if not PATH_PART_RE.fullmatch(name) or name in (".", ".."):
                raise Deny("bad_path", "%s tree has a path part outside [A-Za-z0-9._-]" % side)
            rel = rel_dir + "/" + name if rel_dir else name
            if is_link:
                raise Deny("bad_file", "%s/%s is a symlink" % (side, rel))
            if is_dir:
                if depth + 1 > MAX_DEPTH:
                    raise Deny("too_deep", "%s/%s nests deeper than %d directories" % (side, rel, MAX_DEPTH))
                stack.append((rel, depth + 1))
            elif is_file:
                if not name.endswith(".md"):
                    raise Deny("not_markdown", "%s/%s is not a .md file" % (side, rel))
                found.append(rel)
                if len(found) > MAX_FILES_PER_TREE:
                    raise Deny("too_many_files", "%s tree has more than %d files" % (side, MAX_FILES_PER_TREE))
            else:
                raise Deny("bad_file", "%s/%s is not a regular file" % (side, rel))
    return sorted(found)


def read_bytes(path, label, cap):
    try:
        with open(path, "rb") as fh:
            return fh.read(cap + 1)
    except OSError as exc:
        raise Deny("unreadable", "%s: %s" % (label, exc.__class__.__name__))


def read_tree(root, side):
    blobs = {}
    for rel in walk_tree(root, side):
        blobs[rel] = read_bytes(os.path.join(root, *rel.split("/")), "%s/%s" % (side, rel), MAX_FILE_BYTES)
    return blobs


def load_pins(path):
    """Pins lines: `<sha256>  <size>  <side>/<relpath>`, two spaces between fields."""
    if not isinstance(path, str):
        raise Deny("unpinned", "--pins FILE is required")
    if not os.path.isfile(path):
        raise Deny("unreadable", "pins file is missing")
    data = read_bytes(path, "pins", MAX_PINS_BYTES)
    if len(data) > MAX_PINS_BYTES:
        raise Deny("bad_pins", "pins file exceeds %d bytes" % MAX_PINS_BYTES)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Deny("bad_pins", "pins file is not UTF-8")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    pins = {}
    for n, line in enumerate(lines, 1):
        parts = line.split("  ")
        if len(parts) != 3:
            raise Deny("bad_pins", "pins line %d does not have three fields" % n)
        sha, size, key = parts
        side, _, rel = key.partition("/")
        if not HEX64_RE.fullmatch(sha) or not SIZE_RE.fullmatch(size) or side not in SIDES or not rel:
            raise Deny("bad_pins", "pins line %d is malformed" % n)
        if key in pins:
            raise Deny("bad_pins", "pins line %d repeats %s" % (n, key))
        pins[key] = (sha, int(size))
    return pins


def check_pins(pins, before, after):
    present = {}
    for side, blobs in (("before", before), ("after", after)):
        for rel in blobs:
            present[side + "/" + rel] = blobs[rel]
    for key in sorted(present):
        if key not in pins:
            raise Deny("unpinned", "%s has no pin" % key)
        sha, size = pins[key]
        data = present[key]
        if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
            raise Deny("pin_mismatch", "%s does not match its pin" % key)
    for key in sorted(pins):
        if key not in present:
            raise Deny("pin_missing", "pinned file %s is absent" % key)


# ---------------------------------------------------------------- grammar (v1)

def decode(data, label):
    if len(data) > MAX_FILE_BYTES:
        raise Deny("too_large", "%s exceeds %d bytes" % (label, MAX_FILE_BYTES))
    if data.startswith(b"\xef\xbb\xbf"):
        raise Deny("bad_bom", "%s starts with a byte order mark" % label)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Deny("bad_encoding", "%s is not UTF-8" % label)
    if "\r" in text:
        raise Deny("bad_cr", "%s contains a carriage return" % label)
    if "\t" in text:
        raise Deny("bad_tab", "%s contains a tab" % label)
    return text


def parse_file(rel, text, digest, label):
    """Entries of one file: optional `# title`, then `## heading` blocks."""
    lines = text.split("\n")
    start = 0
    if lines and lines[0].startswith("#") and not lines[0].startswith("##"):
        if not TITLE_RE.fullmatch(lines[0]):
            raise Deny("bad_title", "%s line 1 is not `# <title>`" % label)
        start = 1
    chunks = []
    current = None
    for n in range(start, len(lines)):
        line = lines[n]
        if line.startswith("#"):
            hashes = len(line) - len(line.lstrip("#"))
            rest = line[hashes:]
            if hashes != 2:
                raise Deny("bad_level", "%s line %d starts with %d hash marks; entries use exactly two" % (label, n + 1, hashes))
            heading = rest[1:]
            if not rest.startswith(" ") or heading == "" or heading.startswith(" ") or heading.endswith(" "):
                raise Deny("bad_heading", "%s line %d is not `## <heading>`" % (label, n + 1))
            if len(heading) > MAX_TEXT_CHARS:
                raise Deny("too_long", "%s line %d heading exceeds %d characters" % (label, n + 1, MAX_TEXT_CHARS))
            current = [heading, [], n + 1]
            chunks.append(current)
            if len(chunks) > MAX_ENTRIES_PER_FILE:
                raise Deny("too_many_entries", "%s has more than %d entries" % (label, MAX_ENTRIES_PER_FILE))
        elif current is None:
            if line.strip(" ") != "":
                raise Deny("stray_text", "%s line %d has text before the first entry" % (label, n + 1))
        else:
            current[1].append(line)
    entries = []
    for heading, body_lines, at in chunks:
        ident = None
        if body_lines and body_lines[0].startswith("id:"):
            first = body_lines[0]
            if not first.startswith("id: ") or not ID_RE.fullmatch(first[4:]):
                raise Deny("bad_id", "%s line %d id is not lowercase words joined by hyphens" % (label, at + 1))
            ident = first[4:]
            body_lines = body_lines[1:]
        body = "\n".join(body_lines).strip("\n")
        if len(body) > MAX_TEXT_CHARS:
            raise Deny("too_long", "%s entry at line %d body exceeds %d characters" % (label, at, MAX_TEXT_CHARS))
        entries.append(Entry(rel, heading, ident, body, digest))
    groups = {}
    for e in entries:
        groups.setdefault(e.heading, []).append(e)
    for heading in sorted(groups):
        group = groups[heading]
        if len(group) > 1 and any(e.ident is None for e in group):
            raise Deny("duplicate_heading", "%s repeats a heading without a distinct id on every copy" % label)
    return entries


def parse_snapshot(blobs, side):
    """blobs: {relpath: bytes}. Returns entries in sorted path order."""
    if not isinstance(blobs, dict):
        raise Deny("bad_type", "%s snapshot is not a mapping" % side)
    entries = []
    seen_ids = {}
    for rel in sorted(blobs):
        data = blobs[rel]
        if not isinstance(rel, str) or not isinstance(data, bytes):
            raise Deny("bad_type", "%s snapshot has a non-text path or non-bytes body" % side)
        label = "%s/%s" % (side, rel)
        text = decode(data, label)
        digest = hashlib.sha256(data).hexdigest()
        for e in parse_file(rel, text, digest, label):
            if e.ident is not None:
                if e.ident in seen_ids:
                    raise Deny("duplicate_id", "%s id %s repeats (first in %s)" % (side, e.ident, seen_ids[e.ident]))
                seen_ids[e.ident] = rel
            entries.append(e)
    return entries


# ---------------------------------------------------------------- matching

def _check_entries(entries, side):
    if not isinstance(entries, list):
        raise Deny("bad_type", "%s entries are not a list" % side)
    for e in entries:
        if not isinstance(e, Entry):
            raise Deny("bad_type", "%s entry is not an Entry" % side)
        if not (isinstance(e.path, str) and isinstance(e.heading, str) and isinstance(e.body, str)
                and isinstance(e.digest, str)):
            raise Deny("bad_type", "%s entry has a non-text field" % side)
        if e.ident is not None and not isinstance(e.ident, str):
            raise Deny("bad_type", "%s entry id is not text" % side)


def _row(kind, old, new, matched_by, also_renamed=False):
    ref = new if new is not None else old
    return {
        "class": kind,
        "id": (new.ident if new is not None and new.ident is not None
               else (old.ident if old is not None else None)),
        "old_path": old.path if old is not None else None,
        "new_path": new.path if new is not None else None,
        "old_heading": old.heading if old is not None else None,
        "new_heading": new.heading if new is not None else None,
        "old_file_sha256": old.digest if old is not None else None,
        "new_file_sha256": new.digest if new is not None else None,
        "also_renamed": also_renamed,
        "also_moved": old is not None and new is not None and old.path != new.path and kind != "moved",
        "matched_by": matched_by,
        "_sort": (ref.path, ref.heading),
    }


def _pair_by_id(o, n):
    same_body = o.body == n.body
    same_head = o.heading == n.heading
    if same_body and same_head:
        kind = "unchanged" if o.path == n.path else "moved"
    elif same_body:
        kind = "renamed"
    elif same_head:
        kind = "edited"
    else:
        kind = "edited"  # heading and body both changed under one id
    return _row(kind, o, n, "id", also_renamed=(not same_body and not same_head))


def _pair_by_body(o, n):
    if o.heading == n.heading:
        kind = "unchanged" if o.path == n.path else "moved"
    else:
        kind = "renamed"
    return _row(kind, o, n, "body")


def _pairable_body(body):
    """An empty body carries no identity, so it is never paired by body."""
    return body != ""


def _eligible(o, n):
    """Two different declared ids are two identities; never pair them after pass 1."""
    return not (o.ident is not None and n.ident is not None)


def diff(old, new):
    """Three exact passes: (1) id, snapshot-wide; (2) path + heading;
    (3) leftover bodies seen once on each side (Reading B)."""
    _check_entries(old, "before")
    _check_entries(new, "after")
    rows = []
    info = []
    used_old = set()
    used_new = set()

    # pass 1: same id anywhere in the snapshot
    new_by_id = {}
    for j, e in enumerate(new):
        if e.ident is not None:
            new_by_id[e.ident] = j
    for i, e in enumerate(old):
        if e.ident is None:
            continue
        j = new_by_id.get(e.ident)
        if j is None:
            continue
        rows.append(_pair_by_id(e, new[j]))
        used_old.add(i)
        used_new.add(j)

    # pass 2: same relative path and exact heading, unique on both sides
    old_ph = {}
    new_ph = {}
    for i, e in enumerate(old):
        if i not in used_old:
            old_ph.setdefault((e.path, e.heading), []).append(i)
    for j, e in enumerate(new):
        if j not in used_new:
            new_ph.setdefault((e.path, e.heading), []).append(j)
    for key in sorted(old_ph):
        if key in new_ph and len(old_ph[key]) == 1 and len(new_ph[key]) == 1:
            i, j = old_ph[key][0], new_ph[key][0]
            if _eligible(old[i], new[j]):
                kind = "unchanged" if old[i].body == new[j].body else "edited"
                rows.append(_row(kind, old[i], new[j], "path_heading"))
                used_old.add(i)
                used_new.add(j)

    # pass 3: per unique leftover body (Reading B); shared bodies are never paired
    left_old = [i for i in range(len(old)) if i not in used_old]
    left_new = [j for j in range(len(new)) if j not in used_new]
    old_body = {}
    new_body = {}
    for i in left_old:
        if _pairable_body(old[i].body):
            old_body.setdefault(old[i].body, []).append(i)
    for j in left_new:
        if _pairable_body(new[j].body):
            new_body.setdefault(new[j].body, []).append(j)
    for body in sorted(old_body):
        if body not in new_body:
            continue
        olds, news = old_body[body], new_body[body]
        if len(olds) == 1 and len(news) == 1:
            i, j = olds[0], news[0]
            if _eligible(old[i], new[j]):
                rows.append(_pair_by_body(old[i], new[j]))
                used_old.add(i)
                used_new.add(j)
        else:
            info.append({
                "code": "ambiguous_rename",
                "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "old": sorted([old[i].path, old[i].heading] for i in olds),
                "new": sorted([new[j].path, new[j].heading] for j in news),
            })

    for i in range(len(old)):
        if i not in used_old:
            rows.append(_row("removed", old[i], None, None))
    for j in range(len(new)):
        if j not in used_new:
            rows.append(_row("added", None, new[j], None))

    changes = [r for r in rows if r["class"] != "unchanged"]
    changes.sort(key=lambda r: (CLASSES.index(r["class"]), r["_sort"], r["old_path"] or "", r["old_heading"] or ""))
    for r in changes:
        del r["_sort"]
    counts = {k: 0 for k in CLASSES}
    for r in changes:
        counts[r["class"]] += 1
    counts["unchanged"] = len(rows) - len(changes)
    info.sort(key=lambda d: (d["old"], d["new"]))
    return {"changes": changes, "info": info, "counts": counts}


def compare_blobs(before, after):
    return diff(parse_snapshot(before, "before"), parse_snapshot(after, "after"))


def run(before_dir, after_dir, pins_path):
    pins = load_pins(pins_path)
    before = read_tree(before_dir, "before")
    after = read_tree(after_dir, "after")
    for side, blobs in (("before", before), ("after", after)):
        for rel in sorted(blobs):
            if len(blobs[rel]) > MAX_FILE_BYTES:
                raise Deny("too_large", "%s/%s exceeds %d bytes" % (side, rel, MAX_FILE_BYTES))
    check_pins(pins, before, after)
    return compare_blobs(before, after)


# ---------------------------------------------------------------- rendering

def _q(text):
    return json.dumps(text, ensure_ascii=False)


def _where(r):
    if r["old_path"] is not None and r["new_path"] is not None and r["old_path"] != r["new_path"]:
        return "%s -> %s" % (r["old_path"], r["new_path"])
    return "in %s" % (r["new_path"] if r["new_path"] is not None else r["old_path"])


def _digests(r):
    parts = []
    if r["old_file_sha256"] is not None:
        parts.append("before " + r["old_file_sha256"][:12])
    if r["new_file_sha256"] is not None:
        parts.append("after " + r["new_file_sha256"][:12])
    return "[" + ", ".join(parts) + "]"


def _line(r):
    ident = " (id: %s)" % r["id"] if r["id"] is not None else ""
    kind = r["class"]
    if kind == "renamed" or r["also_renamed"]:
        head = "%s -> %s" % (_q(r["old_heading"]), _q(r["new_heading"]))
    else:
        head = _q(r["new_heading"] if r["new_heading"] is not None else r["old_heading"])
    notes = []
    if kind == "edited":
        notes.append("body changed")
    if r["also_renamed"]:
        notes.append("also_renamed=true")
    if r["also_moved"]:
        notes.append("also_moved=true")
    if r["matched_by"] is not None:
        notes.append("matched by " + r["matched_by"])
    note = ": " + ", ".join(notes) if notes else ""
    return "- %s%s%s %s %s" % (head, ident, note, _where(r), _digests(r))


def render_md(result):
    out = ["# Annal heading diff", ""]
    for kind in CLASSES:
        out.append("## " + kind)
        rows = [r for r in result["changes"] if r["class"] == kind]
        if rows:
            out.extend(_line(r) for r in rows)
        else:
            out.append("- (none)")
        out.append("")
    out.append("## info")
    if result["info"]:
        for d in result["info"]:
            out.append("- ambiguous_rename: %d before / %d after leftover entries share one body "
                       "(body sha256 %s); not paired: %s -> %s" % (
                           len(d["old"]), len(d["new"]), d["body_sha256"][:12],
                           "; ".join("%s %s" % (p, _q(h)) for p, h in d["old"]),
                           "; ".join("%s %s" % (p, _q(h)) for p, h in d["new"])))
    else:
        out.append("- (none)")
    out.append("")
    out.append("## counts")
    for kind in CLASSES + ("unchanged",):
        out.append("- %s: %d" % (kind, result["counts"][kind]))
    out.append("- on_expiry: %s" % ON_EXPIRY)
    return "\n".join(out) + "\n"


def render_json(result):
    doc = dict(result)
    doc["on_expiry"] = ON_EXPIRY
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- CLI

def parse_args(argv):
    if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        raise Deny("bad_args", "arguments are not a list of text")
    opts = {"before": None, "after": None, "pins": None, "json": False}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--json":
            opts["json"] = True
            i += 1
        elif arg in ("--before", "--after", "--pins"):
            key = arg[2:]
            if i + 1 >= len(argv) or opts[key] is not None:
                raise Deny("bad_args", "%s needs exactly one value" % arg)
            opts[key] = argv[i + 1]
            i += 2
        else:
            raise Deny("bad_args", "unknown argument %s" % _q(arg))
    for key in ("before", "after"):
        if opts[key] is None:
            raise Deny("missing_tree", "--%s DIR is required" % key)
    if opts["pins"] is None:
        raise Deny("unpinned", "--pins FILE is required")
    return opts


def main(argv, out=None, err=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    try:
        opts = parse_args(argv)
        result = run(opts["before"], opts["after"], opts["pins"])
        text = render_json(result) if opts["json"] else render_md(result)
    except Deny as d:
        detail = " ".join(str(d.detail).split())
        err.write("DENY %s: %s (on_expiry=%s)\n" % (d.code, detail, ON_EXPIRY))
        return 2
    out.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
