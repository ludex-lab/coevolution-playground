"""mb-evidence-binding: a quote that contains the number can still be the wrong scale or the wrong period.

Method sketch of the evidence contract in arXiv 2611.24990 (abstract page only; the upstream Apache-2.0 repository
was not cloned, run or copied). Stdlib only: no network, no model call, no randomness, no clock, no files written.

A frozen synthetic filing holds tables in which the same line appears for two periods and in two units (a table
in thousands and a table in millions, or thousands of shares and a raw share count). Each question asks for one
line, one period and one unit. Each answer reports a number string and cites a page and a quote.

- The loose test passes when the reported number string appears, as a whole number, in a cited quote on the cited
  page.
- The strict test also requires that the cited quote is the asked line, that the number is the cell for the asked
  period, and that the table's unit (named by its scale note) matches the asked unit. All arithmetic is exact.

The planted label of each answer is never read by either test; it is only used to score the tests afterwards.
"""

import fractions
import json
import re
import sys
import unicodedata

Fraction = fractions.Fraction

FIXTURE_VERSION = 1
PLANTS = ("correct", "scale_error", "wrong_period")
MAX_BYTES = 200000
# every cap says what happens when it is reached; all of them refuse the input (exit 2)
CAPS = {
    "file_bytes": {"limit": MAX_BYTES, "on_expiry": "DENY"},
    "units": {"limit": 20, "on_expiry": "DENY"},
    "periods": {"limit": 20, "on_expiry": "DENY"},
    "lines": {"limit": 100, "on_expiry": "DENY"},
    "tables": {"limit": 50, "on_expiry": "DENY"},
    "columns": {"limit": 4, "on_expiry": "DENY"},
    "quotes": {"limit": 500, "on_expiry": "DENY"},
    "questions": {"limit": 200, "on_expiry": "DENY"},
    "answers": {"limit": 1000, "on_expiry": "DENY"},
    "citations": {"limit": 5, "on_expiry": "DENY"},
}
ON_EXPIRY = ("HOLD", "ESCALATE", "DENY")
MAX_PAGE = 10000
MAX_SCALE = 10 ** 12
MAX_NUMBER_CHARS = 40
MAX_SHORT_TEXT = 160
MAX_QUOTE_TEXT = 400
ID_RE = re.compile(r"[A-Za-z0-9_\uAC00-\uD7A3\u1100-\u1112\u1161-\u1175\u11A8-\u11C2]{1,40}")
KIND_RE = re.compile(r"[a-z][a-z0-9_]{0,19}")
NUM = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?"
NUMBER_RE = re.compile(r"\((%s)\)|(-?)(%s)" % (NUM, NUM))
BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp", "Zs")
BLOCKED_CODEPOINTS = frozenset((0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x2800, 0x3164, 0xFFA0))
DIGITS = "0123456789"

# strict reasons, in the order the strict test reaches them; when no citation binds, the furthest one is reported
STAGES = ("not_on_cited_page", "number_not_in_quote", "wrong_line", "number_not_a_cell", "wrong_period",
          "unit_kind_mismatch", "scale_mismatch")

SCOPE_NOTE = ("the filing, its numbers and the planted answers are fixture-authored; the result shows how the two "
              "tests behave on these planted cases and is not a measurement of any model or of the paper's rates")


class BindingError(Exception):
    """Malformed input: the CLI prints one ERROR line on stderr and exits 2."""

    def __init__(self, code, detail):
        Exception.__init__(self, "%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def _esc(value):
    return json.dumps(str(value), ensure_ascii=True)


# ---------------------------------------------------------------- exact numbers

def parse_number(text):
    """A display number such as 5,432.1 or (12.3) or -7 as an exact Fraction; None when it is not one."""
    if type(text) is not str or len(text) > MAX_NUMBER_CHARS:
        return None
    m = NUMBER_RE.fullmatch(text)
    if m is None:
        return None
    if m.group(1) is not None:
        negative, body = True, m.group(1)
    else:
        negative, body = m.group(2) == "-", m.group(3)
    body = body.replace(",", "")
    if "." in body:
        whole, frac = body.split(".")
        value = Fraction(int(whole + frac), 10 ** len(frac))
    else:
        value = Fraction(int(body))
    return -value if negative else value


def appears_as_number(needle, text):
    """True when needle occurs in text and is not part of a longer number on either side."""
    start = text.find(needle)
    while start != -1:
        end = start + len(needle)
        before = text[max(0, start - 2):start].rjust(2)
        after = text[end:end + 2].ljust(2)
        glued_before = before[1] in DIGITS or (before[1] in ",." and before[0] in DIGITS)
        glued_after = after[0] in DIGITS or (after[0] in ",." and after[1] in DIGITS)
        if not glued_before and not glued_after:
            return True
        start = text.find(needle, start + 1)
    return False


# ---------------------------------------------------------------- strict loading

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise BindingError("duplicate_key", "key %s is repeated" % _esc(key))
        out[key] = value
    return out


def _constant(name):
    raise BindingError("bad_number", "%s is not a finite number" % _esc(name))


def parse(text):
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except BindingError:
        raise
    except (ValueError, RecursionError, OverflowError):
        raise BindingError("not_json", "input is not valid JSON")


def _obj(value, keys, where):
    if type(value) is not dict:
        raise BindingError("wrong_type", "%s must be an object" % where)
    missing = [k for k in keys if k not in value]
    if missing:
        raise BindingError("missing_key", "%s lacks %s" % (where, _esc(missing[0])))
    unknown = sorted(set(value) - set(keys))
    if unknown:
        raise BindingError("unknown_key", "%s has unknown key %s" % (where, _esc(unknown[0])))
    return value


def _int(value, where, low, high):
    if type(value) is not int:
        raise BindingError("wrong_type", "%s must be an integer" % where)
    if not low <= value <= high:
        raise BindingError("bad_value", "%s must be from %d to %d" % (where, low, high))
    return value


def _id(value, where):
    if type(value) is not str or ID_RE.fullmatch(value) is None:
        raise BindingError("bad_id", "%s must be 1 to 40 letters, digits, underscores or Hangul" % where)
    return value


def _text(value, where, limit):
    if type(value) is not str or not 1 <= len(value) <= limit:
        raise BindingError("wrong_type", "%s must be text of 1 to %d characters" % (where, limit))
    for ch in value:
        if ch == " ":
            continue
        if ord(ch) in BLOCKED_CODEPOINTS or unicodedata.category(ch) in BAD_CATEGORIES:
            raise BindingError("bad_text", "%s holds a control, invisible or unassigned character" % where)
    if value != value.strip(" "):
        raise BindingError("bad_text", "%s has a leading or trailing space" % where)
    return value


def _display(value, where):
    if type(value) is not str:
        raise BindingError("wrong_type", "%s must be a number written as text" % where)
    number = parse_number(value)
    if number is None:
        raise BindingError("bad_display", "%s is not a display number such as 5,432.1 or (12.3)" % where)
    return number


def _table_of_ids(value, where, cap):
    if type(value) is not dict:
        raise BindingError("wrong_type", "%s must be an object" % where)
    if not 1 <= len(value) <= CAPS[cap]["limit"]:
        raise BindingError("too_many", "%s must hold 1 to %d entries (on_expiry %s)"
                           % (where, CAPS[cap]["limit"], CAPS[cap]["on_expiry"]))
    seen = set()
    for key in value:
        _id(key, where + " id")
        folded = unicodedata.normalize("NFC", key)
        if folded in seen:
            raise BindingError("duplicate_name", "%s repeats an id (compared after NFC)" % where)
        seen.add(folded)
    return value


def _ref(value, table, where):
    if type(value) is not str or value not in table:
        raise BindingError("bad_ref", "%s does not name a declared entry" % where)
    return value


def _units(value):
    out = {}
    for uid, spec in _table_of_ids(value, "units", "units").items():
        where = "units.%s" % _esc(uid)
        spec = _obj(spec, ("kind", "scale", "note"), where)
        if type(spec["kind"]) is not str or KIND_RE.fullmatch(spec["kind"]) is None:
            raise BindingError("bad_id", "%s.kind must be a short lowercase word" % where)
        note = spec["note"]
        if note != "":
            note = _text(note, where + ".note", MAX_SHORT_TEXT)
        out[uid] = {"kind": spec["kind"], "scale": _int(spec["scale"], where + ".scale", 1, MAX_SCALE), "note": note}
    return out


def _tables(value, units, periods, lines):
    out = {}
    for tid, spec in _table_of_ids(value, "tables", "tables").items():
        where = "tables.%s" % _esc(tid)
        spec = _obj(spec, ("page", "title", "unit", "scale_note", "columns", "rows"), where)
        unit = _ref(spec["unit"], units, where + ".unit")
        scale_note = _text(spec["scale_note"], where + ".scale_note", MAX_SHORT_TEXT)
        if units[unit]["note"] and units[unit]["note"] not in scale_note:
            raise BindingError("bad_scale_note", "%s.scale_note does not name the unit's note" % where)
        columns = spec["columns"]
        if type(columns) is not list or not 1 <= len(columns) <= CAPS["columns"]["limit"]:
            raise BindingError("too_many", "%s.columns must list 1 to %d periods (on_expiry %s)"
                               % (where, CAPS["columns"]["limit"], CAPS["columns"]["on_expiry"]))
        columns = [_ref(c, periods, where + ".columns item") for c in columns]
        if len(set(columns)) != len(columns):
            raise BindingError("duplicate_name", "%s.columns repeats a period" % where)
        rows = _table_of_ids(spec["rows"], where + ".rows", "lines")
        cells = {}
        for line, row in rows.items():
            _ref(line, lines, where + ".rows id")
            if type(row) is not list or len(row) != len(columns):
                raise BindingError("wrong_type", "%s.rows.%s must list one cell per column" % (where, _esc(line)))
            cells[line] = [{"period": p, "display": d, "value": _display(d, "%s.rows.%s cell" % (where, _esc(line)))}
                           for p, d in zip(columns, row)]
        out[tid] = {"page": _int(spec["page"], where + ".page", 1, MAX_PAGE),
                    "title": _text(spec["title"], where + ".title", MAX_SHORT_TEXT),
                    "unit": unit, "scale_note": scale_note, "columns": columns, "cells": cells}
    return out


def _quotes(value, tables):
    out = {}
    for qid, spec in _table_of_ids(value, "quotes", "quotes").items():
        where = "quotes.%s" % _esc(qid)
        spec = _obj(spec, ("page", "table", "row", "text"), where)
        table = _ref(spec["table"], tables, where + ".table")
        row = _ref(spec["row"], tables[table]["cells"], where + ".row")
        page = _int(spec["page"], where + ".page", 1, MAX_PAGE)
        if page != tables[table]["page"]:
            raise BindingError("bad_quote", "%s.page is not the page of its table" % where)
        text = _text(spec["text"], where + ".text", MAX_QUOTE_TEXT)
        for cell in tables[table]["cells"][row]:
            if not appears_as_number(cell["display"], text):
                raise BindingError("bad_quote", "%s.text does not show the cell %s" % (where, _esc(cell["display"])))
        out[qid] = {"page": page, "table": table, "row": row, "text": text}
    return out


def answer_key(fx, question):
    """The asked line and period in the asked unit, exact, from every table that holds it (they must agree)."""
    unit = fx["units"][question["unit"]]
    found = set()
    for table in fx["tables"].values():
        tunit = fx["units"][table["unit"]]
        if tunit["kind"] != unit["kind"]:
            continue
        for cell in table["cells"].get(question["line"], []):
            if cell["period"] == question["period"]:
                found.add(cell["value"] * tunit["scale"] / unit["scale"])
    return found


def _consistency(fx):
    for line in fx["lines"]:
        for period in fx["periods"]:
            seen = {}
            for table in fx["tables"].values():
                tunit = fx["units"][table["unit"]]
                for cell in table["cells"].get(line, []):
                    if cell["period"] == period:
                        seen.setdefault(tunit["kind"], set()).add(cell["value"] * tunit["scale"])
            for kind, values in seen.items():
                if len(values) > 1:
                    raise BindingError("inconsistent_filing", "line %s period %s disagrees across tables"
                                       % (_esc(line), _esc(period)))


def _questions(value, fx):
    out = {}
    for qid, spec in _table_of_ids(value, "questions", "questions").items():
        where = "questions.%s" % _esc(qid)
        spec = _obj(spec, ("text", "line", "period", "unit"), where)
        q = {"text": _text(spec["text"], where + ".text", MAX_SHORT_TEXT),
             "line": _ref(spec["line"], fx["lines"], where + ".line"),
             "period": _ref(spec["period"], fx["periods"], where + ".period"),
             "unit": _ref(spec["unit"], fx["units"], where + ".unit")}
        if len(answer_key(fx, q)) != 1:
            raise BindingError("unanswerable", "%s has no value in the filing for its line, period and unit kind" % where)
        out[qid] = q
    return out


def _answers(value, fx):
    if type(value) is not list:
        raise BindingError("wrong_type", "answers must be a list")
    if not 1 <= len(value) <= CAPS["answers"]["limit"]:
        raise BindingError("too_many", "answers must hold 1 to %d entries (on_expiry %s)"
                           % (CAPS["answers"]["limit"], CAPS["answers"]["on_expiry"]))
    out = []
    seen = set()
    plants = {}
    for k, spec in enumerate(value):
        where = "answers[%d]" % k
        spec = _obj(spec, ("id", "question", "value", "citations", "planted"), where)
        aid = _id(spec["id"], where + ".id")
        if unicodedata.normalize("NFC", aid) in seen:
            raise BindingError("duplicate_name", "%s.id repeats an answer id" % where)
        seen.add(unicodedata.normalize("NFC", aid))
        question = _ref(spec["question"], fx["questions"], where + ".question")
        _display(spec["value"], where + ".value")
        cites = spec["citations"]
        if type(cites) is not list or not 1 <= len(cites) <= CAPS["citations"]["limit"]:
            raise BindingError("too_many", "%s.citations must hold 1 to %d citations (on_expiry %s)"
                               % (where, CAPS["citations"]["limit"], CAPS["citations"]["on_expiry"]))
        citations = []
        for j, c in enumerate(cites):
            c = _obj(c, ("page", "quote"), "%s.citations[%d]" % (where, j))
            citations.append({"page": _int(c["page"], "%s.citations[%d].page" % (where, j), 1, MAX_PAGE),
                              "quote": _ref(c["quote"], fx["quotes"], "%s.citations[%d].quote" % (where, j))})
        if type(spec["planted"]) is not str or spec["planted"] not in PLANTS:
            raise BindingError("bad_plant", "%s.planted must be one of %s" % (where, ", ".join(PLANTS)))
        plants.setdefault(question, []).append(spec["planted"])
        out.append({"id": aid, "question": question, "value": spec["value"], "citations": citations,
                    "planted": spec["planted"]})
    for qid in fx["questions"]:
        if sorted(plants.get(qid, [])) != sorted(PLANTS):
            raise BindingError("bad_plant", "question %s needs exactly one answer of each planted kind" % _esc(qid))
    return out


def validate(root):
    root = _obj(root, ("fixture_version", "label", "filing", "units", "periods", "lines", "tables", "quotes",
                       "questions", "answers"), "fixture")
    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:
        raise BindingError("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    filing = _obj(root["filing"], ("company", "form", "note"), "filing")
    fx = {"label": _text(root["label"], "label", MAX_SHORT_TEXT),
          "filing": {"company": _text(filing["company"], "filing.company", MAX_SHORT_TEXT),
                     "form": _text(filing["form"], "filing.form", MAX_SHORT_TEXT),
                     "note": _text(filing["note"], "filing.note", MAX_SHORT_TEXT)}}
    fx["units"] = _units(root["units"])
    fx["periods"] = {k: _text(v, "periods.%s" % _esc(k), MAX_SHORT_TEXT)
                     for k, v in _table_of_ids(root["periods"], "periods", "periods").items()}
    fx["lines"] = {k: _text(v, "lines.%s" % _esc(k), MAX_SHORT_TEXT)
                   for k, v in _table_of_ids(root["lines"], "lines", "lines").items()}
    fx["tables"] = _tables(root["tables"], fx["units"], fx["periods"], fx["lines"])
    fx["quotes"] = _quotes(root["quotes"], fx["tables"])
    _consistency(fx)
    fx["questions"] = _questions(root["questions"], fx)
    fx["answers"] = _answers(root["answers"], fx)
    return fx


def load_fixture(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_BYTES + 1)
    except OSError:
        raise BindingError("unreadable", "file could not be read")
    if len(data) > MAX_BYTES:
        raise BindingError("too_large", "file is larger than %d bytes (on_expiry DENY)" % MAX_BYTES)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise BindingError("bad_encoding", "file is not valid UTF-8")
    return validate(parse(text))


# ---------------------------------------------------------------- the two binding tests

def answer_view(answer):
    """What a binding test may read about an answer: the question, the number string and the citations."""
    return {"question": answer["question"], "value": answer["value"],
            "citations": [dict(c) for c in answer["citations"]]}


def _loose_citation(fx, value, citation):
    quote = fx["quotes"][citation["quote"]]
    if quote["page"] != citation["page"]:
        return "not_on_cited_page"
    if not appears_as_number(value, quote["text"]):
        return "number_not_in_quote"
    return "bound"


def loose_binding(fx, view):
    """Passes when the reported number string appears, as a whole number, in a cited quote on the cited page."""
    reasons = [_loose_citation(fx, view["value"], c) for c in view["citations"]]
    for k, r in enumerate(reasons):
        if r == "bound":
            return {"pass": True, "reason": "bound", "citation": k}
    return {"pass": False, "reason": max(reasons, key=STAGES.index), "citation": None}


def _strict_citation(fx, question, value, citation):
    first = _loose_citation(fx, value, citation)
    if first != "bound":
        return first
    quote = fx["quotes"][citation["quote"]]
    table = fx["tables"][quote["table"]]
    if quote["row"] != question["line"]:
        return "wrong_line"
    reported = parse_number(value)
    matches = [c for c in table["cells"][quote["row"]] if c["value"] == reported]
    if not matches:
        return "number_not_a_cell"
    asked = [c for c in matches if c["period"] == question["period"]]
    if not asked:
        return "wrong_period"
    tunit = fx["units"][table["unit"]]
    qunit = fx["units"][question["unit"]]
    if tunit["kind"] != qunit["kind"]:
        return "unit_kind_mismatch"
    if reported * qunit["scale"] != asked[0]["value"] * tunit["scale"]:
        return "scale_mismatch"
    return "bound"


def strict_binding(fx, view):
    """The loose test, plus: the quote is the asked line, the number is the asked period's cell, and the table's
    unit (named by its scale note) is the asked unit."""
    question = fx["questions"][view["question"]]
    reasons = [_strict_citation(fx, question, view["value"], c) for c in view["citations"]]
    for k, r in enumerate(reasons):
        if r == "bound":
            return {"pass": True, "reason": "bound", "citation": k}
    return {"pass": False, "reason": max(reasons, key=STAGES.index), "citation": None}


# ---------------------------------------------------------------- scoring

def _frac(f):
    return "%d/%d" % (f.numerator, f.denominator)


def _rate(num, den):
    """An exact rate written as passes/total, not reduced, so the counts stay visible."""
    if den == 0:
        return None
    rate = Fraction(num, den)
    return "%d/%d" % (rate.numerator * (den // rate.denominator), den)


def run(fx):
    rows = []
    for answer in fx["answers"]:
        view = answer_view(answer)
        loose = loose_binding(fx, view)
        strict = strict_binding(fx, view)
        key = answer_key(fx, fx["questions"][answer["question"]]).pop()
        rows.append({"id": answer["id"], "question": answer["question"], "planted": answer["planted"],
                     "value": answer["value"], "value_matches_key": parse_number(answer["value"]) == key,
                     "key": _frac(key), "loose": loose, "strict": strict})
    by_q = {}
    for r in rows:
        by_q.setdefault(r["question"], {})[r["planted"]] = r
    per_question = {}
    for qid, cases in by_q.items():
        c, s, w = cases["correct"], cases["scale_error"], cases["wrong_period"]
        per_question[qid] = {
            "loose_passes_all_three": c["loose"]["pass"] and s["loose"]["pass"] and w["loose"]["pass"],
            "strict_accepts_only_correct": c["strict"]["pass"] and not s["strict"]["pass"] and not w["strict"]["pass"],
            "strict_reasons": {"scale_error": s["strict"]["reason"], "wrong_period": w["strict"]["reason"]},
            "reasons_distinct": s["strict"]["reason"] != w["strict"]["reason"],
        }
    wrong = [r for r in rows if not r["value_matches_key"]]
    right = [r for r in rows if r["value_matches_key"]]
    summary = {
        "answers": len(rows), "questions": len(per_question),
        "loose_passes": sum(1 for r in rows if r["loose"]["pass"]),
        "strict_passes": sum(1 for r in rows if r["strict"]["pass"]),
        "wrong_values": len(wrong),
        "loose_false_pass_rate": _rate(sum(1 for r in wrong if r["loose"]["pass"]), len(wrong)),
        "strict_false_pass_rate": _rate(sum(1 for r in wrong if r["strict"]["pass"]), len(wrong)),
        "strict_true_pass_rate": _rate(sum(1 for r in right if r["strict"]["pass"]), len(right)),
        "strict_reason_counts": {k: v for k, v in sorted(_count(r["strict"]["reason"] for r in rows).items())},
    }
    checks = {
        "a_loose_passes_all_three_cases": {"holds": all(q["loose_passes_all_three"] for q in per_question.values())},
        "b_strict_accepts_only_the_correct_case_with_distinct_reasons": {
            "holds": all(q["strict_accepts_only_correct"] and q["reasons_distinct"] for q in per_question.values()),
            "scale_error_reasons": sorted({q["strict_reasons"]["scale_error"] for q in per_question.values()}),
            "wrong_period_reasons": sorted({q["strict_reasons"]["wrong_period"] for q in per_question.values()}),
        },
        "c_offline": {"holds": True, "network_used": False, "paid_api_used": False},
    }
    return {"label": fx["label"], "filing": fx["filing"], "answers": rows, "per_question": per_question,
            "summary": summary, "checks": checks, "scope_note": SCOPE_NOTE}


def _count(items):
    out = {}
    for item in items:
        out[item] = out.get(item, 0) + 1
    return out


def report(fx):
    return json.dumps(run(fx), indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("ERROR usage: evidence_binding.py FIXTURE.json\n")
        return 2
    try:
        text = report(load_fixture(argv[1]))
    except BindingError as e:
        sys.stderr.write("ERROR %s: %s\n" % (e.code, e.detail))
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
