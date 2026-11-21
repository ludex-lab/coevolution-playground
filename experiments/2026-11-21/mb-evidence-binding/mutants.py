"""Mutation check: break evidence_binding.py one way at a time and require the unittest suite to fail each time.

Run: python3 -B mutants.py
Each mutant is a (name, fragment, replacement) triple. The fragment must occur exactly once in the module.
A mutant is killed when the suite exits non-zero (a failure, an error or a timeout). Exit 0 only if all are killed.
Work happens in a private temporary directory that this script creates and removes.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
# the one timeout in this experiment: a suite run that exceeds it is refused a pass (on_expiry DENY), so a hung
# mutant counts as killed and a hung unmodified suite stops the harness with exit 2
TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}

MUTANTS = [
    # the loose test
    ("loose_ignores_the_cited_page",
     'if quote["page"] != citation["page"]:',
     'if False:'),
    ("loose_uses_plain_substring",
     'if not appears_as_number(value, quote["text"]):',
     'if value not in quote["text"]:'),
    ("whole_number_ignores_the_left_side",
     'glued_before = before[1] in DIGITS or (before[1] in ",." and before[0] in DIGITS)',
     'glued_before = False'),
    ("whole_number_ignores_the_right_side",
     'glued_after = after[0] in DIGITS or (after[0] in ",." and after[1] in DIGITS)',
     'glued_after = False'),
    ("trailing_punctuation_counts_as_glued",
     '(after[0] in ",." and after[1] in DIGITS)',
     '(after[0] in ",.")'),
    ("loose_reads_only_the_first_citation",
     'reasons = [_loose_citation(fx, view["value"], c) for c in view["citations"]]',
     'reasons = [_loose_citation(fx, view["value"], c) for c in view["citations"][:1]]'),
    # the strict test
    ("strict_skips_the_line",
     'if quote["row"] != question["line"]:',
     'if False:'),
    ("strict_skips_the_period",
     'asked = [c for c in matches if c["period"] == question["period"]]',
     'asked = matches'),
    ("strict_skips_the_scale",
     'if reported * qunit["scale"] != asked[0]["value"] * tunit["scale"]:',
     'if False:'),
    ("strict_skips_the_unit_kind",
     'if tunit["kind"] != qunit["kind"]:',
     'if False:'),
    ("strict_takes_any_cell",
     'matches = [c for c in table["cells"][quote["row"]] if c["value"] == reported]',
     'matches = [c for c in table["cells"][quote["row"]]]'),
    ("strict_reads_only_the_first_citation",
     'reasons = [_strict_citation(fx, question, view["value"], c) for c in view["citations"]]',
     'reasons = [_strict_citation(fx, question, view["value"], c) for c in view["citations"][:1]]'),
    ("reason_order_swapped",
     '"wrong_period",\n          "unit_kind_mismatch", "scale_mismatch")',
     '"scale_mismatch",\n          "unit_kind_mismatch", "wrong_period")'),
    ("view_leaks_the_planted_label",
     'return {"question": answer["question"], "value": answer["value"],',
     'return {"planted": answer["planted"], "question": answer["question"], "value": answer["value"],'),
    ("view_citations_not_copied",
     '"citations": [dict(c) for c in answer["citations"]]}',
     '"citations": answer["citations"]}'),
    # exact numbers
    ("parentheses_not_negative",
     'negative, body = True, m.group(1)',
     'negative, body = False, m.group(1)'),
    ("decimal_places_off_by_one",
     'value = Fraction(int(whole + frac), 10 ** len(frac))',
     'value = Fraction(int(whole + frac), 10 ** (len(frac) + 1))'),
    ("loose_digit_grouping",
     '(?:,[0-9]{3})+',
     '(?:,[0-9]{1,3})+'),
    ("answer_key_ignores_scale",
     'found.add(cell["value"] * tunit["scale"] / unit["scale"])',
     'found.add(cell["value"])'),
    ("value_always_matches_key",
     '"value_matches_key": parse_number(answer["value"]) == key,',
     '"value_matches_key": True,'),
    ("rate_reduced_so_counts_vanish",
     'return "%d/%d" % (rate.numerator * (den // rate.denominator), den)',
     'return "%d/%d" % (rate.numerator, den)'),
    # filing integrity
    ("inconsistent_tables_accepted",
     'if len(values) > 1:',
     'if False:'),
    ("quote_need_not_show_its_cells",
     'if not appears_as_number(cell["display"], text):',
     'if False:'),
    ("quote_page_not_checked",
     'if page != tables[table]["page"]:',
     'if False:'),
    ("scale_note_not_checked",
     'if units[unit]["note"] and units[unit]["note"] not in scale_note:',
     'if False:'),
    ("plants_not_checked",
     'if sorted(plants.get(qid, [])) != sorted(PLANTS):',
     'if False:'),
    ("unanswerable_question_accepted",
     'if len(answer_key(fx, q)) != 1:',
     'if False:'),
    ("duplicate_columns_accepted",
     'if len(set(columns)) != len(columns):',
     'if False:'),
    ("empty_citation_list_accepted",
     'not 1 <= len(cites) <= CAPS["citations"]["limit"]',
     'not 0 <= len(cites) <= CAPS["citations"]["limit"]'),
    # loading and the probe battery
    ("bool_accepted_as_int",
     'if type(value) is not int:\n        raise BindingError("wrong_type", "%s must be an integer" % where)',
     'if not isinstance(value, int):\n        raise BindingError("wrong_type", "%s must be an integer" % where)'),
    ("nfc_duplicates_missed",
     'folded = unicodedata.normalize("NFC", key)',
     'folded = key'),
    ("duplicate_json_keys_accepted",
     'if key in out:',
     'if False:'),
    ("nan_and_infinity_pass_the_parser",
     'parse_constant=_constant',
     'parse_constant=float'),
    ("size_cap_removed",
     'if len(data) > MAX_BYTES:',
     'if len(data) > MAX_BYTES * 1000:'),
    ("recursion_error_escapes",
     'except (ValueError, RecursionError, OverflowError):',
     'except (ValueError, OverflowError):'),
    ("control_characters_pass",
     'unicodedata.category(ch) in BAD_CATEGORIES',
     'False'),
    ("invisible_fillers_pass",
     'ord(ch) in BLOCKED_CODEPOINTS or ',
     ''),
    ("edge_spaces_pass",
     'if value != value.strip(" "):',
     'if False:'),
    ("hangul_jamo_ids_refused",
     '\\u1100-\\u1112\\u1161-\\u1175\\u11A8-\\u11C2]',
     ']'),
    ("error_exit_code_changed",
     '        sys.stderr.write("ERROR %s: %s\\n" % (e.code, e.detail))\n        return 2',
     '        sys.stderr.write("ERROR %s: %s\\n" % (e.code, e.detail))\n        return 1'),
]


def run_suite(workdir):
    try:
        done = subprocess.run([sys.executable, "-B", "-m", "unittest", "-f"], cwd=workdir, capture_output=True,
                              timeout=TIMEOUT["seconds"])
    except subprocess.TimeoutExpired:
        return None
    return done.returncode


def main():
    with open(os.path.join(HERE, "evidence_binding.py"), "r", encoding="utf-8") as fh:
        original = fh.read()
    names = [m[0] for m in MUTANTS]
    if len(set(names)) != len(names):
        sys.stdout.write("ERROR duplicate mutant names\n")
        return 2
    for name, fragment, _ in MUTANTS:
        if original.count(fragment) != 1:
            sys.stdout.write("ERROR fragment for %s occurs %d times\n" % (name, original.count(fragment)))
            return 2
    work = tempfile.mkdtemp(prefix="mutants-")
    try:
        for entry in os.listdir(HERE):
            if entry == "__pycache__":
                continue
            src = os.path.join(HERE, entry)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(work, entry))
            else:
                shutil.copy(src, os.path.join(work, entry))
        target = os.path.join(work, "evidence_binding.py")
        base = run_suite(work)
        sys.stdout.write("baseline suite exit code: %s\n" % base)
        if base != 0:
            sys.stdout.write("ERROR the unmodified suite must pass\n")
            return 2
        killed = 0
        for name, fragment, replacement in MUTANTS:
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(original.replace(fragment, replacement))
            code = run_suite(work)
            if code != 0:
                killed += 1
            sys.stdout.write("%-8s %s%s\n" % ("KILLED" if code != 0 else "SURVIVED", name,
                                              " (timeout)" if code is None else ""))
        sys.stdout.write("mutants killed: %d/%d\n" % (killed, len(MUTANTS)))
        return 0 if killed == len(MUTANTS) else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
