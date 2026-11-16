"""Mutation harness for w25-series-title-lint (stdlib only).

Each mutant replaces one exact source fragment (which must occur exactly once) in a copy
of this folder, then runs the unittest suite with the same Python interpreter.  A mutant
is killed when the suite fails.  Run: python3 -B mutants.py   (exit 0 iff all are killed)
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
COPY = ("lint_titles.py", "test_lint_titles.py", "demo.py", "fixtures", "demo")
M = "lint_titles.py"

MUTANTS = [
    # validation (F1: exact types, snapshot, declared structure)
    ("validation", M, "    if type(value) is not dict:", "    if not isinstance(value, dict):"),
    ("validation", M, "        if type(key) is not str:", "        if not isinstance(key, str):"),
    ("validation", M, "    if type(value) is not str:\n        raise _cfg(where + \": expected exact str\")",
     "    if not isinstance(value, str):\n        raise _cfg(where + \": expected exact str\")"),
    ("validation", M, "    if type(value) is not int:", "    if not isinstance(value, int):"),
    ("validation", M, "    if value < low or value > high:", "    if value < low:"),
    ("validation", M, "    if missing:\n        raise _cfg(where + \": missing key \" + missing[0])", "    if False:\n        raise _cfg(where + \": missing key \" + missing[0])"),
    ("validation", M, "    if extra:\n", "    if False:\n"),
    ("validation", M, "    if nonempty and not value:", "    if False:"),
    ("validation", M, "    if not empty_ok and not value.strip():", "    if False:"),
    ("validation", M, "    if \"\\t\" in value or \"\\n\" in value or \"\\r\" in value:", "    if False:"),
    ("validation", M, "    if label != label.strip():", "    if False:"),
    ("validation", M, "    if label[-1].isdigit():", "    if False:"),
    ("validation", M, "    raise InputError(\"catalog_malformed\", \"non-finite number \" + name)", "    return float(name)"),
    ("validation", M, "        if key in out:", "        if False:"),
    ("validation", M, "    if _exact_str(top[\"schema\"], \"schema\") != CATALOG_SCHEMA:", "    if False:"),
    ("validation", M, "        if not _LANG_RE.match(lang):", "        if False:"),
    ("validation", M, "        if lang in langs:\n", "        if False:\n"),
    ("validation", M, "        if not _KEY_RE.match(key):", "        if False:"),
    ("validation", M, "        if key in seen_keys:", "        if False:"),
    ("validation", M, "        if prev is not None and prev != key:", "        if False:"),
    ("validation", M, "        if not norm:\n", "        if False:\n"),
    ("validation", M, "            if suffix != suffix.strip() or any(ch.isdigit() for ch in suffix):", "            if False:"),
    ("validation", M, "            if last <= last_seen:", "            if last < last_seen:"),
    ("validation", M, "            retired.append((label, last_seen + 1, last, pad))", "            retired.append((label, first, last, pad))"),
    ("validation", M, "                raise _cfg(rw + \".label: equals a canonical label\")", "                pass"),
    ("validation", M, "                raise _cfg(vw + \".label: equals a canonical label\")", "                pass"),
    ("validation", M, "            if lang not in langs:\n", "            if False:\n"),
    ("validation", M, "            if not _KEY_RE.match(nkey) or nkey in name_keys:", "            if not _KEY_RE.match(nkey):"),
    ("validation", M, "            if not nlabels:", "            if False:"),
    ("validation", M, "                    if owner != nkey:", "                    if False:"),
    ("validation", M, "                if lang not in nlabels:", "                if False:"),
    ("validation", M, "                if owner != nkey + \"/variant\":", "                if False:"),
    ("validation", M, "        series_out.append((key, first, tuple(forms), tuple(retired), tuple(variants)))",
     "        series_out.append((key, first, forms, retired, variants))"),
    ("validation", M, "    return (langs, tuple(series_out), tuple(names_out))", "    return (list(langs), series_out, names_out)"),
    # titles parsing
    ("parsing", M, "    if text.startswith(\"\\ufeff\"):", "    if False:"),
    ("parsing", M, "    lines = [raw[:-1] if raw.endswith(\"\\r\") else raw for raw in text.split(\"\\n\")]", "    lines = text.split(\"\\n\")"),
    ("parsing", M, "        if not line.strip() or line.startswith(\"#\"):", "        if not line.strip():"),
    ("parsing", M, "            if len(parts) != 3:", "            if len(parts) < 3:"),
    ("parsing", M, "            if lang and lang not in langs:", "            if False:"),
    ("parsing", M, "            if \"\\t\" in line:", "            if False:"),
    ("parsing", M, "        if not title.strip():", "        if False:"),
    ("parsing", M, "    if not rows:\n", "    if False:\n"),
    # matching
    ("matching", M, "_SEP = r\"[\\s\\u00b7.\\-_]\"", "_SEP = r\"[\\s.\\-_]\""),
    ("matching", M, "    return (_SEP + \"*\").join(", "    return (_SEP + \"+\").join("),
    ("matching", M, "(?:ep\\.?\\s*)?", ""),
    ("matching", M, "    head = \"(?<![0-9A-Za-z\\uac00-\\ud7a3])\"\n    pats = []", "    head = \"\"\n    pats = []"),
    ("matching", M, "            pats.append((si, 0, \"canonical\", label, re.compile(head + \"(?P<label>\" + _loose(label) + \")\" + tail, re.IGNORECASE)))",
     "            pats.append((si, 0, \"canonical\", label, re.compile(head + \"(?P<label>\" + _loose(label) + \")\" + tail)))"),
    ("matching", M, "            pats.append((si, 1, (\"retired\", ri), label, re.compile(head + \"(?P<label>\" + _loose(label) + \")\" + tail, re.IGNORECASE)))",
     "            pats.append((si, 1, (\"retired\", ri), label, re.compile(head + \"(?P<label>\" + _loose(label) + \")\" + tail)))"),
    ("matching", M, "    cands.sort(key=lambda c: (c[0], c[1], c[2], c[3]))", "    cands.sort(key=lambda c: (c[0], c[1], c[3]))"),
    ("matching", M, "        if any(m.start() < e and s < m.end() for s, e in taken):", "        if False:"),
    ("matching", M, "            matched += 1", "            matched += len(hits)"),
    # severity and classification
    ("severity", M, "    \"retired_alias\": \"INFO\",", "    \"retired_alias\": \"WARN\","),
    ("severity", M, "    \"number_gap\": \"WARN\",", "    \"number_gap\": \"FAIL\","),
    ("severity", M, "    \"spacing_drift\": \"FAIL\",", "    \"spacing_drift\": \"WARN\","),
    ("severity", M, "    \"label_drift\": \"FAIL\",", "    \"label_drift\": \"INFO\","),
    ("severity", M, "    if found == expected:\n        return None\n    if foreign:", "    if False:\n        return None\n    if foreign:"),
    ("severity", M, "        return \"spacing_drift\"", "        return \"case_drift\""),
    ("severity", M, "    if _strip(found).casefold() == _strip(expected).casefold():", "    if False:"),
    ("severity", M, "                if not (lo <= number <= hi):", "                if not (number <= hi):"),
    ("severity", M, "                code = _drift(found, render(label, number, pad, \"\"), foreign)", "                code = None"),
    ("severity", M, "                if row_lang and row_lang not in label_langs:", "                if False:"),
    ("severity", M, "                use = row_lang or vlang", "                use = vlang"),
    ("severity", M, "    return label + \" \" + digits + suffix", "    return label + \" \" + digits"),
    ("severity", M, "    decision = FAIL if counts[\"FAIL\"] else PASS", "    decision = FAIL if counts[\"FAIL\"] or counts[\"WARN\"] else PASS"),
    # numbers
    ("numbers", M, "            if len(seen[number]) > 1:", "            if len(seen[number]) > 2:"),
    ("numbers", M, "            missing = [n for n in range(first, top_n + 1) if n not in seen]",
     "            missing = [n for n in range(first + 1, top_n + 1) if n not in seen]"),
    ("numbers", M, "            numbers[key].append((number, line_no))", "            numbers[key].append((number, 0))"),
    # names
    ("names", M, "        left, right = \"(?<![0-9A-Za-z])\", \"(?![0-9A-Za-z])\"", "        left, right = \"(?<![0-9A-Za-z])\", \"\""),
    ("names", M, "        left, right = \"(?<![\\uac00-\\ud7a3])\", \"\"", "        left, right = \"\", \"\""),
    ("names", M, "                    if m.group(0) != lab:", "                    if False:"),
    ("names", M, "                    expected = name_by_lang.get(row_lang) or name_by_lang[vlang]", "                    expected = name_by_lang[vlang]"),
    ("names", M, "    return re.compile(left + re.escape(label) + right, re.IGNORECASE)", "    return re.compile(left + re.escape(label) + right)"),
    # fail-closed input handling (on_expiry=DENY)
    ("deny", M, "    if not os.path.exists(path):", "    if False:"),
    ("deny", M, "        raise InputError(what + \"_unreadable\", type(exc).__name__)", "        raise InputError(what + \"_missing\", type(exc).__name__)"),
    ("deny", M, "        return data.decode(\"utf-8\")", "        return data.decode(\"utf-8\", \"replace\")"),
    ("deny", M, "EXIT_CODES = {PASS: 0, FAIL: 1, DENY: 2}", "EXIT_CODES = {PASS: 0, FAIL: 1, DENY: 0}"),
    ("deny", M, "ON_EXPIRY = \"DENY\"", "ON_EXPIRY = \"HOLD\""),
    ("deny", M, "        \"decision\": DENY,", "        \"decision\": PASS,"),
    ("deny", M, "    if bad is None and len(pos) != 2:", "    if bad is None and len(pos) < 2:"),
    ("deny", M, "            return EXIT_CODES[DENY]", "            return 0"),
    ("deny", M, "            elif v in (\"text\", \"json\"):", "            elif True:"),
    ("deny", M, "        raise InputError(what + \"_missing\", \"no path given\")", "        raise InputError(what + \"_unreadable\", \"no path given\")"),
    # data (fixtures and demo)
    ("data", "fixtures/catalog.json", "        {\"label\": \"Ludex Village Doc\", \"lang\": \"en\"}\n", ""),
    ("data", "fixtures/catalog.json", "        {\"label\": \"Naru Daily Weekly\", \"last\": 1, \"pad\": 2},\n", ""),
    ("data", "fixtures/catalog.json", "\"ko\": {\"label\": \"\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050\", \"pad\": 0,",
     "\"ko\": {\"label\": \"\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050\", \"pad\": 2,"),
    ("data", "fixtures/live_titles.tsv", "| Ludex Weekly06\n", "| Ludex Weekly 06\n"),
    ("data", "demo/titles.tsv", "| Ludex Weekly08\n", "| Ludex Weekly 08\n"),
    ("data", "demo.py", "DEMO_TITLES = os.path.join(HERE, \"demo\", \"titles.tsv\")",
     "DEMO_TITLES = os.path.join(HERE, \"fixtures\", \"live_titles.tsv\")"),
    # r2: folding (NFKC, decimal digits, Cf characters) and catalog label hygiene (L6)
    ("folding", M, "    if unicodedata.category(ch) == \"Cf\":\n        return \"\"", "    if False:\n        return \"\""),
    ("folding", M, "    if ch.isdecimal() and not (\"0\" <= ch <= \"9\"):", "    if False:"),
    ("folding", M, "    return unicodedata.normalize(\"NFKC\", ch)", "    return ch"),
    ("folding", M, "        if f != ch and not ch.isspace():", "        if f != ch:"),
    ("folding", M, "        if f != ch and not ch.isspace():", "        if False:"),
    ("folding", M, "    text = unicodedata.normalize(\"NFC\", title)", "    text = title"),
    ("folding", M, "        index.extend([i] * len(f))", "        index.append(i)"),
    ("folding", M, "    if foreign:\n        return \"unicode_drift\"", "    if False:\n        return \"unicode_drift\""),
    ("folding", M, "            foreign = any(i in foreign_at for i in range(os_, oe_))", "            foreign = False"),
    ("folding", M, "            found = text[os_:oe_]", "            found = m.group(0)"),
    ("folding", M, "                code = _drift(found, expected, foreign)", "                code = _classify(found, expected)"),
    ("folding", M, "        hits = _mentions(folded, pats)", "        hits = _mentions(title, pats)"),
    ("folding", M, "    if any(_fold_char(ch) != ch for ch in label):", "    if False:"),
    ("folding", M, "    \"unicode_drift\": \"FAIL\",", "    \"unicode_drift\": \"WARN\","),
    # r2: declared label with no parsed number, near misses, unmatched rows listed (M1)
    ("unparsed", M, "        out.append((\"label_without_number\", si, label, lang, s, e))", "        pass"),
    ("unparsed", M, "            out.append((\"label_near_miss\", si, label, lang, s, e))", "            pass"),
    ("unparsed", M, "        if _overlaps(s, e, spans):\n            continue\n        spans.append((s, e))\n        out.append((\"label_without",
     "        spans.append((s, e))\n        out.append((\"label_without"),
    ("unparsed", M, "            if _overlaps(s, e, spans):\n                continue", "            if False:\n                continue"),
    ("unparsed", M, "    occ.sort(key=lambda c: (c[0], c[1]))", "    occ.sort(key=lambda c: (-c[0], c[1]))"),
    ("unparsed", M, "            if dist > 1:\n                continue", "            if dist > 0:\n                continue"),
    ("unparsed", M, "        if not k or sum(len(t) for t in tokens) < NEAR_MIN_LETTERS:", "        if not k:"),
    ("unparsed", M, "NEAR_MIN_LETTERS = 6", "NEAR_MIN_LETTERS = 7"),
    ("unparsed", M, "        return 1 if sum(1 for x, y in zip(a, b) if x != y) == 1 else 2", "        return 1"),
    ("unparsed", M, "        if a == b[:i] + b[i + 1:]:", "        if a == b[:i]:"),
    ("unparsed", M, "    if len(a) > len(b):\n        a, b = b, a", "    if False:\n        a, b = b, a"),
    ("unparsed", M, "        if not hits and not misses:", "        if not hits:"),
    ("unparsed", M, "        taken = [(c[7].start(), c[7].end()) for c in hits]", "        taken = []"),
    ("unparsed", M, "            lab, pad, suf = form_by_lang[row_lang or plang or langs[0]]", "            lab, pad, suf = form_by_lang[plang or langs[0]]"),
    ("unparsed", M, "            lab, pad, suf = form_by_lang[row_lang or plang or langs[0]]", "            lab, pad, suf = form_by_lang[row_lang or langs[0]]"),
    ("unparsed", M, "            tail_end = index[min(e + 8, len(folded)) - 1] + 1", "            tail_end = oe_"),
    ("unparsed", M, "text[oe_:tail_end].split(\"|\")[0]", "text[oe_:tail_end]"),
    ("unparsed", M, "    head = \"(?<![0-9A-Za-z\\uac00-\\ud7a3])\"\n    out = []", "    head = \"\"\n    out = []"),
    ("unparsed", M, "    \"label_without_number\": \"FAIL\",", "    \"label_without_number\": \"WARN\","),
    ("unparsed", M, "    \"label_near_miss\": \"FAIL\",", "    \"label_near_miss\": \"WARN\","),
    ("unparsed", M, "    \"unmatched_title\": \"INFO\",", "    \"unmatched_title\": \"WARN\","),
    # r2: comments only before the TSV header (M2)
    ("comments", M, "            start = idx + 1", "            start = idx"),
    ("comments", M, "        break\n    rows = []", "        continue\n    rows = []"),
    ("comments", M, "    for idx in range(start, len(lines)):", "    for idx in range(len(lines)):"),
    ("comments", M, "        if not line.strip():\n            continue\n        if tsv:", "        if not line.strip() or line.startswith(\"#\"):\n            continue\n        if tsv:"),
    # r2: limits (L1, L2)
    ("limits", M, "            if len(digits) > MAX_DIGITS:", "            if False:"),
    ("limits", M, "MAX_DIGITS = 6", "MAX_DIGITS = 7"),
    ("limits", M, "MAX_GAP_LIST = 20", "MAX_GAP_LIST = 21"),
    ("limits", M, "                if len(missing) > MAX_GAP_LIST:", "                if len(missing) >= MAX_GAP_LIST:"),
    ("limits", M, "    except (RecursionError, ValueError) as exc:\n        return deny_report(\"input_limit\", type(exc).__name__)\n    try:", "    try:"),
    ("limits", M, "    try:\n        return lint(snapshot, rows)\n    except (RecursionError, ValueError) as exc:\n        return deny_report(\"input_limit\", type(exc).__name__)",
     "    return lint(snapshot, rows)"),
    ("data", "demo/titles.tsv", "draft-o06e\ten\tDraft: Evening Song | Ludex Village OST 6\n", "draft-o05e\ten\tDraft: Morning Song | Ludex Village OST 5\n"),
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


def main():
    problems = []
    for i, (cat, rel, old, new) in enumerate(MUTANTS):
        n = _read(rel).count(old)
        if n != 1:
            problems.append("mutant %d (%s, %s): fragment occurs %d times" % (i + 1, cat, rel, n))
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
    for cat in ("validation", "parsing", "matching", "severity", "numbers", "names", "deny",
                "folding", "unparsed", "comments", "limits", "data"):
        if cat in totals:
            print("%-10s %d/%d killed" % (cat, totals[cat][0], totals[cat][1]))
    for num, cat, rel, frag in survivors:
        print("SURVIVED #%d %s %s: %s" % (num, cat, rel, frag))
    print("TOTAL %d/%d killed" % (killed_all, len(MUTANTS)))
    return 0 if killed_all == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
