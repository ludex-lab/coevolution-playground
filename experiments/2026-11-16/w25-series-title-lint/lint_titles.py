"""w25-series-title-lint: a file-in/file-out lint of series labels in video titles.

Reads a titles file (plain lines, or TSV with the header ``ref<TAB>lang<TAB>title``)
and a JSON series catalog.  The catalog declares, per series, the canonical label for
every language, the number format (zero pad, suffix), retired aliases in order with
the last number each one covered, and known drift spellings ("variants").  An optional
``names`` table declares character names per language.

Decisions: PASS (no FAIL finding), FAIL (at least one FAIL finding), DENY (missing,
unreadable or malformed input).  ``on_expiry`` is DENY: when the inputs cannot be read
there is no pass and no permit, only DENY with a non-zero exit.

Before matching, each title is folded: format characters (category Cf: zero-width space,
zero-width joiner, soft hyphen, ...) are removed, decimal digits of any script become ASCII
digits, and every other character is NFKC-normalised.  Matching runs on the folded text; every
finding quotes the original text.  A declared label whose number cannot be parsed, a near miss
of a declared label, and folded (invisible or compatibility) characters inside a series mention
are all FAIL.  A title that mentions no series is listed as INFO ``unmatched_title``.

Python standard library only.  No network, no subprocess, no clock, no randomness.
"""

import json
import os
import re
import sys
import unicodedata

TOOL = "w25-series-title-lint"
CATALOG_SCHEMA = "w25-series-title-lint/catalog-1"
TSV_HEADER = "ref\tlang\ttitle"
ON_EXPIRY = "DENY"

PASS = "PASS"
FAIL = "FAIL"
DENY = "DENY"
EXIT_CODES = {PASS: 0, FAIL: 1, DENY: 2}

SEVERITY_ORDER = {"FAIL": 0, "WARN": 1, "INFO": 2}

CODE_SEVERITY = {
    "label_drift": "FAIL",
    "language_label": "FAIL",
    "spacing_drift": "FAIL",
    "case_drift": "FAIL",
    "number_format_drift": "FAIL",
    "retired_alias_out_of_era": "FAIL",
    "duplicate_number": "FAIL",
    "name_drift": "FAIL",
    "name_case_drift": "FAIL",
    "unicode_drift": "FAIL",
    "label_without_number": "FAIL",
    "label_near_miss": "FAIL",
    "number_gap": "WARN",
    "retired_alias": "INFO",
    "unmatched_title": "INFO",
}

_SEP = r"[\s\u00b7.\-_]"
_SEP_RUN = re.compile(_SEP + "+")
_LANG_RE = re.compile(r"^[a-z]{2}$")
_KEY_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_HANGUL_RE = re.compile("[\uac00-\ud7a3]")
MAX_PAD = 4
MAX_DIGITS = 6
MAX_GAP_LIST = 20
NEAR_MIN_LETTERS = 6
_WORD_RE = re.compile(r"\w+")


class InputError(Exception):
    """Raised for any missing, unreadable or malformed input; always maps to DENY."""

    def __init__(self, reason, detail):
        Exception.__init__(self, reason, detail)
        self.reason = reason
        self.detail = detail


# ---------------------------------------------------------------------------
# Catalog validation (F1: exact types, no subclasses, no bool/NaN/inf/float numbers)
# ---------------------------------------------------------------------------

def _cfg(detail):
    return InputError("config_error", detail)


def _exact_dict(value, where, required, optional=()):
    if type(value) is not dict:
        raise _cfg(where + ": expected a JSON object")
    for key in value:
        if type(key) is not str:
            raise _cfg(where + ": keys must be exact str")
    names = set(value)
    missing = [k for k in required if k not in names]
    if missing:
        raise _cfg(where + ": missing key " + missing[0])
    extra = sorted(names - set(required) - set(optional))
    if extra:
        raise _cfg(where + ": unknown key " + extra[0])
    return value


def _exact_list(value, where, nonempty=True):
    if type(value) is not list:
        raise _cfg(where + ": expected a JSON array")
    if nonempty and not value:
        raise _cfg(where + ": must not be empty")
    return value


def _exact_str(value, where, empty_ok=False):
    if type(value) is not str:
        raise _cfg(where + ": expected exact str")
    if not empty_ok and not value.strip():
        raise _cfg(where + ": must not be blank")
    if "\t" in value or "\n" in value or "\r" in value:
        raise _cfg(where + ": control characters are not permitted")
    return value


def _exact_int(value, where, low, high):
    if type(value) is not int:
        raise _cfg(where + ": expected exact int (bool, float, NaN, inf are rejected)")
    if value < low or value > high:
        raise _cfg(where + ": out of range")
    return value


def _label(value, where):
    label = _exact_str(value, where)
    if label != label.strip():
        raise _cfg(where + ": leading or trailing whitespace")
    if label[-1].isdigit():
        raise _cfg(where + ": label must not end with a digit")
    if any(_fold_char(ch) != ch for ch in label):
        raise _cfg(where + ": label must be NFKC-normal with ASCII digits and no invisible characters")
    return label


def _fold_char(ch):
    if unicodedata.category(ch) == "Cf":
        return ""
    if ch.isdecimal() and not ("0" <= ch <= "9"):
        return str(unicodedata.decimal(ch))
    return unicodedata.normalize("NFKC", ch)


def fold(title):
    """Return (text, folded, index, foreign) for a title.

    ``text`` is the NFC form of the title (the text findings quote); ``folded`` is the text
    matching runs on; ``index[i]`` is the position in ``text`` of folded character ``i``;
    ``foreign`` is the set of positions in ``text`` whose character was removed or changed by
    folding, not counting whitespace (whitespace changes are reported as spacing drift).
    """
    text = unicodedata.normalize("NFC", title)
    out = []
    index = []
    foreign = set()
    for i, ch in enumerate(text):
        f = _fold_char(ch)
        if f != ch and not ch.isspace():
            foreign.add(i)
        out.append(f)
        index.extend([i] * len(f))
    return text, "".join(out), tuple(index), frozenset(foreign)


def _strip(text):
    return _SEP_RUN.sub("", text)


def _norm(text):
    return _strip(text).casefold()


def _reject_constant(name):
    raise InputError("catalog_malformed", "non-finite number " + name)


def _no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise InputError("catalog_malformed", "duplicate key " + key)
        out[key] = value
    return out


def parse_catalog_text(text):
    """Parse catalog JSON text (no NaN/Infinity, no duplicate keys) and validate it."""
    if type(text) is not str:
        raise InputError("catalog_unreadable", "catalog text must be str")
    try:
        obj = json.loads(text, parse_constant=_reject_constant,
                         object_pairs_hook=_no_duplicate_keys)
    except ValueError as exc:
        raise InputError("catalog_malformed", "invalid JSON: " + str(exc))
    return validate_catalog(obj)


def validate_catalog(obj):
    """Validate a catalog object and return an immutable snapshot (nested tuples).

    The snapshot shares no mutable state with ``obj``: later edits to ``obj`` do not
    change any lint result computed from the snapshot.
    """
    top = _exact_dict(obj, "catalog", ("schema", "languages", "series"), ("names",))
    if _exact_str(top["schema"], "schema") != CATALOG_SCHEMA:
        raise _cfg("schema: expected " + CATALOG_SCHEMA)
    langs = []
    for i, lang in enumerate(_exact_list(top["languages"], "languages")):
        lang = _exact_str(lang, "languages[%d]" % i)
        if not _LANG_RE.match(lang):
            raise _cfg("languages[%d]: expected a two-letter code" % i)
        if lang in langs:
            raise _cfg("languages[%d]: duplicate" % i)
        langs.append(lang)
    langs = tuple(langs)

    series_out = []
    seen_keys = set()
    owners = {}  # normalized label -> series key

    def claim(label, key, where):
        norm = _norm(label)
        if not norm:
            raise _cfg(where + ": label has no letters")
        prev = owners.get(norm)
        if prev is not None and prev != key:
            raise _cfg(where + ": label collides with series " + prev)
        owners[norm] = key

    for si, raw in enumerate(_exact_list(top["series"], "series")):
        where = "series[%d]" % si
        ser = _exact_dict(raw, where, ("key", "first", "labels", "retired", "variants"))
        key = _exact_str(ser["key"], where + ".key")
        if not _KEY_RE.match(key):
            raise _cfg(where + ".key: expected [a-z][a-z0-9_-]*")
        if key in seen_keys:
            raise _cfg(where + ".key: duplicate series key")
        seen_keys.add(key)
        first = _exact_int(ser["first"], where + ".first", 0, 10 ** 6)

        labels = _exact_dict(ser["labels"], where + ".labels", langs)
        forms = []
        canon_norms = set()
        for lang in langs:
            lw = where + ".labels." + lang
            form = _exact_dict(labels[lang], lw, ("label", "pad", "suffix"))
            label = _label(form["label"], lw + ".label")
            pad = _exact_int(form["pad"], lw + ".pad", 0, MAX_PAD)
            suffix = _exact_str(form["suffix"], lw + ".suffix", empty_ok=True)
            if suffix != suffix.strip() or any(ch.isdigit() for ch in suffix):
                raise _cfg(lw + ".suffix: no whitespace or digits")
            claim(label, key, lw + ".label")
            canon_norms.add(_norm(label))
            forms.append((lang, (label, pad, suffix)))

        retired = []
        last_seen = first - 1
        for ri, rraw in enumerate(_exact_list(ser["retired"], where + ".retired", False)):
            rw = where + ".retired[%d]" % ri
            ret = _exact_dict(rraw, rw, ("label", "last", "pad"))
            label = _label(ret["label"], rw + ".label")
            last = _exact_int(ret["last"], rw + ".last", 0, 10 ** 6)
            pad = _exact_int(ret["pad"], rw + ".pad", 0, MAX_PAD)
            if last <= last_seen:
                raise _cfg(rw + ".last: retired aliases must be in increasing order")
            if _norm(label) in canon_norms:
                raise _cfg(rw + ".label: equals a canonical label")
            claim(label, key, rw + ".label")
            retired.append((label, last_seen + 1, last, pad))
            last_seen = last

        variants = []
        for vi, vraw in enumerate(_exact_list(ser["variants"], where + ".variants", False)):
            vw = where + ".variants[%d]" % vi
            var = _exact_dict(vraw, vw, ("label", "lang"))
            label = _label(var["label"], vw + ".label")
            lang = _exact_str(var["lang"], vw + ".lang")
            if lang not in langs:
                raise _cfg(vw + ".lang: not a declared language")
            if _norm(label) in canon_norms:
                raise _cfg(vw + ".label: equals a canonical label")
            claim(label, key, vw + ".label")
            variants.append((label, lang))

        series_out.append((key, first, tuple(forms), tuple(retired), tuple(variants)))

    names_out = []
    if "names" in top:
        name_keys = set()
        name_norms = {}
        for ni, nraw in enumerate(_exact_list(top["names"], "names", False)):
            nw = "names[%d]" % ni
            ent = _exact_dict(nraw, nw, ("key", "labels", "variants"))
            nkey = _exact_str(ent["key"], nw + ".key")
            if not _KEY_RE.match(nkey) or nkey in name_keys:
                raise _cfg(nw + ".key: invalid or duplicate")
            name_keys.add(nkey)
            nlabels = _exact_dict(ent["labels"], nw + ".labels", (), langs)
            if not nlabels:
                raise _cfg(nw + ".labels: must not be empty")
            pairs = []
            for lang in langs:
                if lang in nlabels:
                    lab = _label(nlabels[lang], nw + ".labels." + lang)
                    owner = name_norms.setdefault(lab.casefold(), nkey)
                    if owner != nkey:
                        raise _cfg(nw + ".labels." + lang + ": collides with " + owner)
                    pairs.append((lang, lab))
            nvars = []
            for vi, vraw in enumerate(_exact_list(ent["variants"], nw + ".variants", False)):
                vw = nw + ".variants[%d]" % vi
                var = _exact_dict(vraw, vw, ("label", "lang"))
                lab = _label(var["label"], vw + ".label")
                lang = _exact_str(var["lang"], vw + ".lang")
                if lang not in nlabels:
                    raise _cfg(vw + ".lang: name has no label in that language")
                owner = name_norms.setdefault(lab.casefold(), nkey + "/variant")
                if owner != nkey + "/variant":
                    raise _cfg(vw + ".label: collides with " + owner)
                nvars.append((lab, lang))
            names_out.append((nkey, tuple(pairs), tuple(nvars)))

    return (langs, tuple(series_out), tuple(names_out))


# ---------------------------------------------------------------------------
# Titles file
# ---------------------------------------------------------------------------

def parse_titles_text(text, langs):
    """Return a tuple of rows (line_no, ref, lang_or_empty, title)."""
    if type(text) is not str:
        raise InputError("titles_unreadable", "titles text must be str")
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = [raw[:-1] if raw.endswith("\r") else raw for raw in text.split("\n")]
    # '#' comment lines exist only in TSV mode, before the header.  Without a header every
    # non-blank line is a title, including one that starts with '#'.
    tsv = False
    start = 0
    for idx, line in enumerate(lines):
        if not line.strip() or line.startswith("#"):
            continue
        if line == TSV_HEADER:
            tsv = True
            start = idx + 1
        break
    rows = []
    for idx in range(start, len(lines)):
        line_no = idx + 1
        line = lines[idx]
        if not line.strip():
            continue
        if tsv:
            parts = line.split("\t")
            if len(parts) != 3:
                raise InputError("titles_malformed", "line %d: expected 3 TSV fields" % line_no)
            ref, lang, title = parts
            if lang and lang not in langs:
                raise InputError("titles_malformed", "line %d: undeclared lang" % line_no)
        else:
            if "\t" in line:
                raise InputError("titles_malformed", "line %d: tab in a plain title line" % line_no)
            ref, lang, title = "", "", line
        if not title.strip():
            raise InputError("titles_malformed", "line %d: empty title" % line_no)
        rows.append((line_no, ref, lang, title))
    if not rows:
        raise InputError("titles_empty", "no titles")
    return tuple(rows)


# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------

def _loose(label):
    tokens = [t for t in _SEP_RUN.split(label) if t]
    return (_SEP + "*").join(re.escape(t) for t in tokens)


def render(label, number, pad, suffix):
    digits = str(number).zfill(pad) if pad else str(number)
    return label + " " + digits + suffix


def _classify(found, expected):
    """Name the drift between two different renderings (``found != expected``)."""
    if _strip(found) == _strip(expected):
        return "spacing_drift"
    if _strip(found).casefold() == _strip(expected).casefold():
        return "case_drift"
    return "number_format_drift"


def _build_patterns(snapshot):
    langs, series, _names = snapshot
    suffixes = sorted({f[1][2] for s in series for f in s[2] if f[1][2]}, key=lambda s: (-len(s), s))
    suffix_re = "(?P<suffix>" + "|".join(re.escape(s) for s in suffixes) + ")?" if suffixes else "(?P<suffix>)"
    tail = r"(?P<gap>" + _SEP + r"*(?:ep\.?\s*)?)(?P<num>[0-9]+)" + suffix_re + r"(?![0-9])"
    head = "(?<![0-9A-Za-z\uac00-\ud7a3])"
    pats = []
    for si, (key, first, forms, retired, variants) in enumerate(series):
        seen = set()
        for lang, (label, pad, suffix) in forms:
            if _norm(label) in seen:
                continue
            seen.add(_norm(label))
            pats.append((si, 0, "canonical", label, re.compile(head + "(?P<label>" + _loose(label) + ")" + tail, re.IGNORECASE)))
        for ri, (label, lo, hi, pad) in enumerate(retired):
            pats.append((si, 1, ("retired", ri), label, re.compile(head + "(?P<label>" + _loose(label) + ")" + tail, re.IGNORECASE)))
        for vi, (label, vlang) in enumerate(variants):
            pats.append((si, 2, ("variant", vi), label, re.compile(head + "(?P<label>" + _loose(label) + ")" + tail, re.IGNORECASE)))
    return pats


def _label_patterns(snapshot):
    """Every declared label (canonical, retired, variant) as (series index, label, lang, regex)."""
    langs, series, _names = snapshot
    head = "(?<![0-9A-Za-z\uac00-\ud7a3])"
    out = []
    for si, (key, first, forms, retired, variants) in enumerate(series):
        labels = [(label, lang) for lang, (label, pad, suffix) in forms]
        labels += [(r[0], "") for r in retired]
        labels += list(variants)
        for label, lang in labels:
            out.append((si, label, lang, re.compile(head + _loose(label), re.IGNORECASE),
                        tuple(t.casefold() for t in _WORD_RE.findall(label))))
    return out


def _edit_distance_at_most_one(a, b):
    """0, 1, or 2 (meaning: more than one edit)."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 1:
        return 2
    if len(a) == len(b):
        return 1 if sum(1 for x, y in zip(a, b) if x != y) == 1 else 2
    if len(a) > len(b):
        a, b = b, a
    for i in range(len(b)):
        if a == b[:i] + b[i + 1:]:
            return 1
    return 2


def _overlaps(s, e, spans):
    return any(s < e2 and s2 < e for s2, e2 in spans)


def _unparsed(folded, taken, label_pats):
    """Declared labels with no parsed number, then near misses of declared labels.

    Returns a list of (kind, series index, label, lang, start, end) over ``folded``.
    """
    occ = []
    for si, label, lang, rx, _tokens in label_pats:
        for m in rx.finditer(folded):
            occ.append((-(m.end() - m.start()), m.start(), m.end(), si, label, lang))
    occ.sort(key=lambda c: (c[0], c[1]))
    spans = list(taken)
    out = []
    for _neg, s, e, si, label, lang in occ:
        if _overlaps(s, e, spans):
            continue
        spans.append((s, e))
        out.append(("label_without_number", si, label, lang, s, e))
    words = [(m.start(), m.end(), m.group(0).casefold()) for m in _WORD_RE.finditer(folded)]
    for si, label, lang, _rx, tokens in label_pats:
        k = len(tokens)
        if not k or sum(len(t) for t in tokens) < NEAR_MIN_LETTERS:
            continue
        for i in range(len(words) - k + 1):
            window = words[i:i + k]
            dist = 0
            for (ws, we, w), t in zip(window, tokens):
                dist += _edit_distance_at_most_one(w, t)
                if dist > 1:
                    break
            if dist > 1:
                continue
            s, e = window[0][0], window[-1][1]
            if _overlaps(s, e, spans):
                continue
            spans.append((s, e))
            out.append(("label_near_miss", si, label, lang, s, e))
    out.sort(key=lambda c: c[4])
    return out


def _drift(found, expected, foreign):
    if found == expected:
        return None
    if foreign:
        return "unicode_drift"
    return _classify(found, expected)


def _mentions(title, pats):
    cands = []
    for order, (si, rank, kind, label, rx) in enumerate(pats):
        for m in rx.finditer(title):
            span = -(m.end() - m.start())
            label_span = -(m.end("label") - m.start("label"))
            cands.append((span, m.start(), label_span, order, si, kind, label, m))
    cands.sort(key=lambda c: (c[0], c[1], c[2], c[3]))
    taken = []
    chosen = []
    for c in cands:
        m = c[7]
        if any(m.start() < e and s < m.end() for s, e in taken):
            continue
        taken.append((m.start(), m.end()))
        chosen.append(c)
    chosen.sort(key=lambda c: c[1])
    return chosen


def _finding(code, line_no, ref, series, number, found, expected, title):
    return {
        "severity": CODE_SEVERITY[code],
        "code": code,
        "line": line_no,
        "ref": ref,
        "series": series,
        "number": number,
        "found": found,
        "expected": expected,
        "title": title,
    }


def _name_regex(label):
    if _HANGUL_RE.search(label):
        left, right = "(?<![\uac00-\ud7a3])", ""
    else:
        left, right = "(?<![0-9A-Za-z])", "(?![0-9A-Za-z])"
    return re.compile(left + re.escape(label) + right, re.IGNORECASE)


def lint(snapshot, rows):
    """Pure lint over a validated catalog snapshot and parsed rows. Returns a report dict."""
    langs, series, names = snapshot
    pats = _build_patterns(snapshot)
    label_pats = _label_patterns(snapshot)
    findings = []
    numbers = {s[0]: [] for s in series}
    matched = 0
    for line_no, ref, row_lang, title in rows:
        text, folded, index, foreign_at = fold(title)
        hits = _mentions(folded, pats)
        if hits:
            matched += 1
        taken = [(c[7].start(), c[7].end()) for c in hits]
        misses = _unparsed(folded, taken, label_pats)
        if not hits and not misses:
            findings.append(_finding("unmatched_title", line_no, ref, "", None, text,
                                     "no declared series label", title))
        for kind_code, si, plabel, plang, s, e in misses:
            key, first, forms, retired, variants = series[si]
            form_by_lang = dict(forms)
            lab, pad, suf = form_by_lang[row_lang or plang or langs[0]]
            os_, oe_ = index[s], index[e - 1] + 1
            tail_end = index[min(e + 8, len(folded)) - 1] + 1
            shown = (text[os_:oe_] + text[oe_:tail_end].split("|")[0]).rstrip()
            findings.append(_finding(kind_code, line_no, ref, key, None, shown,
                                     lab + " <number>" + suf, title))
        for _span, _start, _lspan, _order, si, kind, plabel, m in hits:
            key, first, forms, retired, variants = series[si]
            form_by_lang = dict(forms)
            os_, oe_ = index[m.start()], index[m.end() - 1] + 1
            found = text[os_:oe_]
            foreign = any(i in foreign_at for i in range(os_, oe_))
            digits = m.group("num")
            if len(digits) > MAX_DIGITS:
                findings.append(_finding("number_format_drift", line_no, ref, key, None, found,
                                         "a number of at most %d digits" % MAX_DIGITS, title))
                continue
            number = int(digits)
            numbers[key].append((number, line_no))
            if kind == "canonical":
                label_langs = [lg for lg, f in forms if _norm(f[0]) == _norm(plabel)]
                if row_lang and row_lang not in label_langs:
                    lab, pad, suf = form_by_lang[row_lang]
                    findings.append(_finding("language_label", line_no, ref, key, number, found,
                                             render(lab, number, pad, suf), title))
                    continue
                if row_lang:
                    use = row_lang
                else:
                    exact = [lg for lg in label_langs
                             if render(form_by_lang[lg][0], number, form_by_lang[lg][1], form_by_lang[lg][2]) == found]
                    use = exact[0] if exact else label_langs[0]
                lab, pad, suf = form_by_lang[use]
                expected = render(lab, number, pad, suf)
                code = _drift(found, expected, foreign)
                if code:
                    findings.append(_finding(code, line_no, ref, key, number, found, expected, title))
            elif kind[0] == "retired":
                label, lo, hi, pad = retired[kind[1]]
                use = row_lang or langs[0]
                clab, cpad, csuf = form_by_lang[use]
                canonical = render(clab, number, cpad, csuf)
                if not (lo <= number <= hi):
                    findings.append(_finding("retired_alias_out_of_era", line_no, ref, key, number,
                                             found, canonical, title))
                    continue
                code = _drift(found, render(label, number, pad, ""), foreign)
                if code:
                    findings.append(_finding(code, line_no, ref, key, number, found,
                                             render(label, number, pad, ""), title))
                else:
                    findings.append(_finding("retired_alias", line_no, ref, key, number, found,
                                             canonical, title))
            else:
                label, vlang = variants[kind[1]]
                use = row_lang or vlang
                lab, pad, suf = form_by_lang[use]
                findings.append(_finding("label_drift", line_no, ref, key, number, found,
                                         render(lab, number, pad, suf), title))
        for nkey, pairs, nvars in names:
            name_by_lang = dict(pairs)
            for lab in sorted(set(name_by_lang.values())):
                for m in _name_regex(lab).finditer(title):
                    if m.group(0) != lab:
                        findings.append(_finding("name_case_drift", line_no, ref, nkey, None,
                                                 m.group(0), lab, title))
            for lab, vlang in nvars:
                for m in _name_regex(lab).finditer(title):
                    expected = name_by_lang.get(row_lang) or name_by_lang[vlang]
                    findings.append(_finding("name_drift", line_no, ref, nkey, None,
                                             m.group(0), expected, title))

    series_summary = {}
    for key, first, forms, retired, variants in series:
        seen = {}
        for number, line_no in numbers[key]:
            seen.setdefault(number, []).append(line_no)
        for number in sorted(seen):
            if len(seen[number]) > 1:
                findings.append(_finding("duplicate_number", seen[number][1], "", key, number,
                                         "lines " + ",".join(str(x) for x in seen[number]),
                                         "one title per number", ""))
        if seen:
            top_n = max(seen)
            missing = [n for n in range(first, top_n + 1) if n not in seen]
            if missing:
                shown = ",".join(str(n) for n in missing[:MAX_GAP_LIST])
                if len(missing) > MAX_GAP_LIST:
                    shown += ",... (%d missing)" % len(missing)
                findings.append(_finding("number_gap", 0, "", key, None,
                                         "missing " + shown,
                                         "%d..%d contiguous" % (first, top_n), ""))
        series_summary[key] = sorted(seen)

    findings.sort(key=lambda f: (f["line"], SEVERITY_ORDER[f["severity"]], f["code"], f["series"], f["found"]))
    counts = {"FAIL": 0, "WARN": 0, "INFO": 0}
    for f in findings:
        counts[f["severity"]] += 1
    decision = FAIL if counts["FAIL"] else PASS
    return {
        "tool": TOOL,
        "decision": decision,
        "on_expiry": ON_EXPIRY,
        "titles": len(rows),
        "matched": matched,
        "unmatched": len(rows) - matched,
        "counts": counts,
        "findings": findings,
        "series": series_summary,
    }


def deny_report(reason, detail):
    return {
        "tool": TOOL,
        "decision": DENY,
        "on_expiry": ON_EXPIRY,
        "reason": reason,
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# File in / file out
# ---------------------------------------------------------------------------

def _read_text(path, what):
    if type(path) is not str or not path:
        raise InputError(what + "_missing", "no path given")
    if not os.path.exists(path):
        raise InputError(what + "_missing", "file not found")
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise InputError(what + "_unreadable", type(exc).__name__)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise InputError(what + "_unreadable", "not UTF-8")


def run(titles_path, catalog_path):
    """Read both files and lint. Any input problem returns a DENY report."""
    try:
        snapshot = parse_catalog_text(_read_text(catalog_path, "catalog"))
        rows = parse_titles_text(_read_text(titles_path, "titles"), snapshot[0])
    except InputError as exc:
        return deny_report(exc.reason, exc.detail)
    except (RecursionError, ValueError) as exc:
        return deny_report("input_limit", type(exc).__name__)
    try:
        return lint(snapshot, rows)
    except (RecursionError, ValueError) as exc:
        return deny_report("input_limit", type(exc).__name__)


def format_text(report):
    out = ["%s decision=%s on_expiry=%s" % (TOOL, report["decision"], report["on_expiry"])]
    if report["decision"] == DENY:
        out.append("reason=%s detail=%s" % (report["reason"], report["detail"]))
        return "\n".join(out) + "\n"
    c = report["counts"]
    out.append("titles=%d matched=%d unmatched=%d FAIL=%d WARN=%d INFO=%d" % (
        report["titles"], report["matched"], report["unmatched"], c["FAIL"], c["WARN"], c["INFO"]))
    for f in report["findings"]:
        num = "" if f["number"] is None else " %d" % f["number"]
        where = ("L%d" % f["line"]) if f["line"] else "--"
        ref = (" ref=" + f["ref"]) if f["ref"] else ""
        out.append("%-4s %-4s %s %s%s%s found=%r expected=%r" % (
            f["severity"], where, f["code"], f["series"], num, ref, f["found"], f["expected"]))
    for key in sorted(report["series"]):
        nums = report["series"][key]
        out.append("series %s numbers=%s" % (key, ",".join(str(n) for n in nums) or "-"))
    return "\n".join(out) + "\n"


def format_json(report):
    return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


USAGE = "usage: python3 -B lint_titles.py TITLES CATALOG [--out PATH] [--format text|json]"


def main(argv):
    pos = []
    out_path = None
    fmt = "text"
    args = list(argv)
    bad = None
    while args:
        a = args.pop(0)
        if a in ("--out", "--format"):
            if not args:
                bad = "missing value for " + a
                break
            v = args.pop(0)
            if a == "--out":
                out_path = v
            elif v in ("text", "json"):
                fmt = v
            else:
                bad = "unknown format"
                break
        elif a.startswith("--"):
            bad = "unknown option"
            break
        else:
            pos.append(a)
    if bad is None and len(pos) != 2:
        bad = "expected TITLES and CATALOG"
    if bad is not None:
        report = deny_report("usage", bad)
        sys.stderr.write(USAGE + "\n")
    else:
        report = run(pos[0], pos[1])
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
