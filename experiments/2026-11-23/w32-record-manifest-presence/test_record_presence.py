"""unittest suite for record_presence.py.  Run: python3 -B -m unittest

No test reads any Python source file; every check is on behaviour (return values, exit codes, output).
"""

import json
import os
import subprocess
import sys
import tempfile
import unicodedata
import unittest

import mutants
import record_presence as rp

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
BAD = os.path.join(FIX, "bad")
BAD_CODES = {
    "bad_cover_bidi_in_name.md": "bad_name",
    "bad_cover_bom.md": "bad_encoding",
    "bad_cover_duplicate_by_brace.md": "duplicate_name",
    "bad_cover_duplicate_group.md": "duplicate_group",
    "bad_cover_duplicate_name.md": "duplicate_name",
    "bad_cover_duplicate_nfc_nfd.md": "duplicate_name",
    "bad_cover_empty.md": "no_files_table",
    "bad_cover_empty_group.md": "empty_group",
    "bad_cover_files_heading_level3.md": "no_files_table",
    "bad_cover_header_only.md": "empty_files_table",
    "bad_cover_heading_at_end.md": "no_files_table",
    "bad_cover_heading_in_fence_only.md": "no_files_table",
    "bad_cover_heading_without_table.md": "no_files_table",
    "bad_cover_invisible_group.md": "empty_group",
    "bad_cover_no_files_column.md": "bad_files_header",
    "bad_cover_no_files_heading.md": "no_files_table",
    "bad_cover_no_group_column.md": "bad_files_header",
    "bad_cover_no_separator_row.md": "bad_files_header",
    "bad_cover_not_utf8.md": "bad_encoding",
    "bad_cover_row_extra_cell.md": "bad_table_row",
    "bad_cover_row_missing_cell.md": "bad_table_row",
    "bad_cover_row_not_closed.md": "bad_table_row",
    "bad_cover_separator_wrong_width.md": "bad_files_header",
    "bad_cover_short_separator.md": "bad_files_header",
    "bad_cover_tab_in_name.md": "bad_name",
    "bad_cover_too_large.md": "too_large",
    "bad_cover_too_many_names.md": "too_many_names",
    "bad_cover_too_many_names_rows.md": "too_many_names",
    "bad_cover_too_many_rows.md": "too_many_rows",
    "bad_cover_two_files_columns.md": "bad_files_header",
    "bad_cover_two_files_sections.md": "two_files_tables",
    "bad_cover_unclosed_backtick.md": "bad_cell",
    "bad_cover_utf16.md": "bad_encoding",
    "bad_cover_zero_width_in_name.md": "bad_name",
    "bad_ignore_bang_only.txt": "bad_ignore_line",
    "bad_ignore_control_char.txt": "bad_ignore_line",
    "bad_ignore_crlf.txt": "bad_ignore_line",
    "bad_ignore_double_bang.txt": "bad_ignore_line",
    "bad_ignore_not_utf8.txt": "bad_encoding",
    "bad_ignore_slash_only.txt": "bad_ignore_line",
    "bad_ignore_too_large.txt": "too_large",
    "bad_ignore_too_many_lines.txt": "too_many_ignore_lines",
    "bad_ignore_zero_width.txt": "bad_ignore_line",
    "bad_listing_blank_line.txt": "blank_listing_line",
    "bad_listing_bom.txt": "bad_encoding",
    "bad_listing_control_char.txt": "bad_listing_name",
    "bad_listing_crlf.txt": "bad_listing_name",
    "bad_listing_duplicate.txt": "duplicate_listing_name",
    "bad_listing_duplicate_nfc_nfd.txt": "duplicate_listing_name",
    "bad_listing_leading_space.txt": "bad_listing_name",
    "bad_listing_name_too_long.txt": "bad_listing_name",
    "bad_listing_not_utf8.txt": "bad_encoding",
    "bad_listing_only_newline.txt": "blank_listing_line",
    "bad_listing_path_not_name.txt": "bad_listing_name",
    "bad_listing_space_line.txt": "blank_listing_line",
    "bad_listing_too_large.txt": "too_large",
    "bad_listing_too_many.txt": "too_many_listing_names",
    "bad_listing_zero_width.txt": "bad_listing_name",
}


def fx(*parts):
    return os.path.join(FIX, *parts)


def tool(*args):
    return subprocess.run([sys.executable, "-B", os.path.join(HERE, "record_presence.py")] + list(args),
                          capture_output=True, text=True, timeout=120)


def result(cover, listing, ignore=None, record_path=None, receipt_name=None):
    return rp.run({"cover": fx(*cover.split("/")), "listing": fx(*listing.split("/")),
                   "ignore": None if ignore is None else fx(ignore), "record_path": record_path,
                   "receipt_name": receipt_name, "json": False})


def cover_text(rows):
    return "# t\n\n## Files\n\n| Group | Files | Note |\n|---|---|---|\n" + "".join(
        "| %s | %s | n |\n" % r for r in rows)


def ok(test, fn, *args):
    """Call a parser that should succeed; an unexpected DENY becomes a test failure, not an error."""
    try:
        return fn(*args)
    except rp.PresenceError as e:
        test.fail("unexpected DENY %s: %s" % (e.code, e.detail))


def codes(res, level=None):
    return [(f["code"], f["name"]) for f in res["findings"] if level is None or f["level"] == level]


class CriterionTests(unittest.TestCase):
    """Acceptance criteria 1-9 of the verdict, each by behaviour."""

    def test_1_files_table_and_brace_expansion(self):
        cover = rp.parse_cover(rp.read_text(fx("e1", "cover.md"), "cover"))
        names = [f["name"] for f in cover["named"]]
        self.assertEqual(len(names), 20)
        for who in ("agy", "haiku", "grok"):
            self.assertIn("e1_selftest_%s.json" % who, names)
        self.assertNotIn("e1_selftest_{agy,haiku,grok}.json", names)
        self.assertEqual(cover["groups"], ["Specification (verbatim)", "Corrections", "Verdict", "Instruments",
                                           "Data as run"])
        self.assertEqual(cover["title"], "Physics E1 (hand-made fixture cover)")

    def test_1_brace_forms(self):
        self.assertEqual(rp._expand("x_{a,b}{1,2}.json"), (["x_a1.json", "x_a2.json", "x_b1.json", "x_b2.json"],
                                                           None))
        for token in ("x_{a}.json", "x_{a,}.json", "x_{a,{b,c}}.json", "x_{a,b.json", "x_a}.json"):
            names, why = rp._expand(token)
            self.assertIsNone(names, token)
            self.assertTrue(why)

    def test_2_unparsed_tokens_are_info_never_fail(self):
        res = result("e1/cover.md", "e1/listing_complete.txt")
        self.assertEqual(res["result"], "PASS")
        unparsed = [(f["name"], f["group"], f["after"]) for f in res["findings"] if f["code"] == "unparsed_name"]
        self.assertEqual(unparsed, [("(+ AMENDMENT 01–04 in-file)", "Specification (verbatim)",
                                     "PREREG_physics_e1.md"), ("CORRECTION_01…03", "Corrections", None)])
        self.assertTrue(all(f["level"] == "INFO" for f in res["findings"]))
        self.assertIn("INFO unparsed_name \"CORRECTION_01…03\"", rp.report(res))

    def test_2_other_unparsed_shapes(self):
        cover = ok(self, rp.parse_cover, cover_text([
            ("A", "`CORRECTION_01...03`"), ("B", "none yet"), ("C", "`two words.md`"), ("D", "`sub/x.json`"),
            ("E", "`a.json` and `b.json`"), ("F", "`c.json` (48 runs), `d.json` + `e.json`")]))
        self.assertEqual([f["name"] for f in cover["named"]],
                         ["two words.md", "x.json", "a.json", "b.json", "c.json", "d.json", "e.json"])
        self.assertEqual([u["token"] for u in cover["unparsed"]],
                         ["CORRECTION_01...03", "none yet", "and"])

    def test_2_prereg_name_is_still_checked(self):
        res = result("e1/cover.md", "e1/listing_complete.txt")
        self.assertNotIn(("missing_named_file", "PREREG_physics_e1.md"), codes(res))
        with tempfile.TemporaryDirectory() as work:
            path = os.path.join(work, "l.txt")
            with open(fx("e1", "listing_complete.txt"), encoding="utf-8") as fh:
                names = [n for n in fh.read().split("\n") if n and n != "PREREG_physics_e1.md"]
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(names) + "\n")
            res = rp.check(rp.parse_cover(rp.read_text(fx("e1", "cover.md"), "c")), rp.parse_listing(
                rp.read_text(path, "l")))
        self.assertEqual(codes(res, "FAIL"), [("missing_named_file", "PREREG_physics_e1.md")])

    def test_3_missing_named_file_fails_with_group(self):
        res = result("e1/cover.md", "e1/listing.txt")
        fails = [(f["code"], f["name"], f["group"]) for f in res["findings"] if f["level"] == "FAIL"]
        self.assertEqual(fails, [("missing_named_file", n, "Data as run") for n in (
            "e1_screen_v2.jsonl", "e1_battery.jsonl", "e1_anchor.jsonl", "e1_telemetry.jsonl")])
        self.assertEqual((res["named"], res["listed"], res["missing"], res["result"]), (20, 20, 4, "FAIL"))
        p = tool("--cover", fx("e1", "cover.md"), "--listing", fx("e1", "listing.txt"))
        self.assertEqual((p.returncode, p.stderr), (1, ""))
        self.assertIn("FAIL missing_named_file e1_battery.jsonl (group: Data as run)", p.stdout)

    def test_3_e2_two_missing(self):
        res = result("e2/cover.md", "e2/listing.txt")
        self.assertEqual(codes(res, "FAIL"), [("missing_named_file", "e2_battery.jsonl"),
                                              ("missing_named_file", "e2_telemetry.jsonl")])
        self.assertEqual((res["named"], res["listed"]), (13, 12))

    def test_4_missing_receipt_fails(self):
        res = result("e2/cover.md", "e2/listing_no_receipt.txt")
        self.assertEqual(codes(res, "FAIL")[0], ("missing_receipt", "PREREG_PUBLISH_RECEIPT.json"))
        self.assertEqual(res["missing"], 3)
        p = tool("--cover", fx("e2", "cover.md"), "--listing", fx("e2", "listing_no_receipt.txt"))
        self.assertEqual(p.returncode, 1)
        self.assertIn("FAIL missing_receipt PREREG_PUBLISH_RECEIPT.json (group: Specification (verbatim))",
                      p.stdout)

    def test_4_receipt_name_option(self):
        res = result("e2/cover.md", "e2/listing_no_receipt.txt", receipt_name="e2_pool.json")
        self.assertIn(("missing_receipt", "PREREG_PUBLISH_RECEIPT.json"), codes(res, "FAIL"))
        cover = rp.parse_cover(cover_text([("Spec", "`spec.md`, `ordering_proof.json`")]))
        res = rp.check(cover, ["spec.md"], receipt_name="ordering_proof.json")
        self.assertEqual(codes(res, "FAIL"), [("missing_receipt", "ordering_proof.json")])
        res = rp.check(cover, ["spec.md"])
        self.assertEqual(codes(res, "FAIL"), [("missing_named_file", "ordering_proof.json")])
        res = rp.check(cover, ["spec.md", "ordering_proof.json"], receipt_name="other.json")
        self.assertEqual(codes(res), [("receipt_not_named", "other.json")])
        self.assertEqual(res["result"], "PASS")

    def test_5_listed_not_named_is_info(self):
        res = result("e1/cover.md", "e1/listing.txt")
        extra = [f["name"] for f in res["findings"] if f["code"] == "listed_not_named"]
        self.assertEqual(extra, ["BUNDLE_README.md", "CORRECTION_01_report_does_not_accumulate.md",
                                 "CORRECTION_02_boundary_is_experientially_vacuous.md",
                                 "CORRECTION_03_env_selection_was_underdetermined.md"])
        cover = rp.parse_cover(cover_text([("A", "`a.json`")]))
        res = rp.check(cover, ["a.json", "z.json"])
        self.assertEqual((res["result"], codes(res)), ("PASS", [("listed_not_named", "z.json")]))

    def test_6_ignore_rule_tags_each_miss(self):
        res = result("e1/cover.md", "e1/listing.txt", ignore="ignore_rules.txt", record_path="research/physics-e1")
        tags = [f["ignored_by_pattern"] for f in res["findings"] if f["level"] == "FAIL"]
        self.assertEqual(tags, ["*.jsonl"] * 4)
        self.assertEqual(res["result"], "FAIL")
        self.assertIn("FAIL missing_named_file e1_battery.jsonl (group: Data as run); INFO ignored_by_pattern "
                      "*.jsonl", rp.report(res))
        res = result("e1/cover.md", "e1/listing.txt")
        self.assertEqual([f["ignored_by_pattern"] for f in res["findings"] if f["level"] == "FAIL"], [None] * 4)

    def test_6_negation_last_rule_wins(self):
        res = result("e2/cover.md", "e2/listing.txt", ignore="ignore_negated.txt", record_path="research/uptake-e2")
        tags = {f["name"]: f["ignored_by_pattern"] for f in res["findings"] if f["level"] == "FAIL"}
        self.assertEqual(tags, {"e2_battery.jsonl": "*.jsonl", "e2_telemetry.jsonl": None})
        res = result("e2/cover.md", "e2/listing.txt", ignore="ignore_negated.txt")
        tags = {f["name"]: f["ignored_by_pattern"] for f in res["findings"] if f["level"] == "FAIL"}
        self.assertEqual(tags, {"e2_battery.jsonl": "*.jsonl", "e2_telemetry.jsonl": "*.jsonl"})

    def test_6_matcher_rules(self):
        rules = rp.parse_ignore("# c\n\n*.jsonl\n!creatures/Comet/store/*.jsonl\nlogs/\n/research/**/raw_*.json\n"
                                "fields/*/*.json  \n")
        self.assertEqual(len(rules), 5)
        self.assertEqual(rp.explain(rules, "a.jsonl", "research/x"), "*.jsonl")
        self.assertIsNone(rp.explain(rules, "a.jsonl", "creatures/Comet/store"))
        self.assertEqual(rp.explain(rules, "a.jsonl", "creatures/Other/store"), "*.jsonl")
        self.assertIsNone(rp.explain(rules, "logs", "research/x"))
        self.assertEqual(rp.explain(rules, "raw_1.json", "research/x/y"), "/research/**/raw_*.json")
        self.assertEqual(rp.explain(rules, "raw_1.json", "research"), "/research/**/raw_*.json")
        self.assertIsNone(rp.explain(rules, "raw_1.json", "other/research"))
        self.assertIsNone(rp.explain(rules, "raw_1.json", None))
        self.assertEqual(rp.explain(rules, "a.json", "fields/f1"), "fields/*/*.json")
        self.assertIsNone(rp.explain(rules, "a.json", "fields/f1/deeper"))
        self.assertIsNone(rp.explain(rules, "a.json", "research/x"))
        self.assertEqual(rp.explain(rp.parse_ignore("e?_*.jsonl\n"), "e2_x.jsonl", None), "e?_*.jsonl")
        self.assertIsNone(rp.explain(rp.parse_ignore("E2_*\n"), "e2_x.jsonl", None))

    def test_7_corrections_group_is_optional(self):
        res = result("e2/cover.md", "e2/listing_complete.txt")
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["corrections_group"], "absent (optional, not required)")
        self.assertEqual(result("e1/cover.md", "e1/listing.txt")["corrections_group"], "present")

    def test_8_bad_fixture_set_matches_folder(self):
        self.assertEqual(sorted(os.listdir(BAD)), sorted(BAD_CODES))
        self.assertGreaterEqual(len(BAD_CODES), 15)

    def test_8_every_bad_fixture_is_deny(self):
        for name, code in sorted(BAD_CODES.items()):
            with self.subTest(name=name):
                path = os.path.join(BAD, name)
                if name.startswith("bad_cover_"):
                    args = ["--cover", path, "--listing", fx("e2", "listing.txt")]
                elif name.startswith("bad_listing_"):
                    args = ["--cover", fx("e2", "cover.md"), "--listing", path]
                else:
                    args = ["--cover", fx("e2", "cover.md"), "--listing", fx("e2", "listing.txt"), "--ignore", path]
                p = tool(*args)
                self.assertEqual(p.returncode, 2)
                self.assertEqual(p.stdout, "")
                lines = p.stderr.splitlines()
                self.assertEqual(len(lines), 1, p.stderr)
                self.assertTrue(lines[0].startswith("ERROR %s: " % code), lines[0])
                self.assertTrue(lines[0].endswith("(on_expiry=DENY)"))
                self.assertNotIn("Traceback", p.stderr)

    def test_8_missing_unreadable_and_usage_are_deny(self):
        cover, listing = fx("e2", "cover.md"), fx("e2", "listing.txt")
        absent = fx("absent.txt")
        cases = [
            ["--cover", absent, "--listing", listing], ["--cover", cover, "--listing", absent],
            ["--cover", cover, "--listing", listing, "--ignore", absent], ["--cover", FIX, "--listing", listing],
            [], ["--cover", cover], ["--listing", listing], ["--cover", cover, "--listing"],
            ["--cover", cover, "--listing", listing, "--cover", cover], ["--cover", cover, "--listing", listing, "x"],
            ["--cover", cover, "--listing", listing, "--record-path", "../up"],
            ["--cover", cover, "--listing", listing, "--record-path", "/abs"],
            ["--cover", cover, "--listing", listing, "--record-path", "a//b"],
            ["--cover", cover, "--listing", listing, "--receipt-name", "a/b.json"],
            ["--cover", cover, "--listing", listing, "--receipt-name", "r\u200b.json"],
            ["--json", "--json", "--cover", cover, "--listing", listing],
        ]
        expect = ["unreadable", "unreadable", "unreadable", "unreadable", "usage", "usage", "usage", "usage",
                  "usage", "usage", "bad_record_path", "bad_record_path", "bad_record_path", "bad_receipt_name",
                  "bad_receipt_name", "usage"]
        for args, code in zip(cases, expect):
            with self.subTest(args=args):
                p = tool(*args)
                self.assertEqual((p.returncode, p.stdout), (2, ""))
                self.assertEqual(len(p.stderr.splitlines()), 1)
                self.assertTrue(p.stderr.startswith("ERROR %s: " % code), p.stderr)

    def test_9_caps_declare_deny(self):
        self.assertEqual(set(rp.CAPS), {"input_bytes", "table_rows", "named_files", "listing_names", "ignore_lines",
                                        "name_chars"})
        self.assertTrue(all(c["on_expiry"] == "DENY" for c in rp.CAPS.values()))
        self.assertEqual(rp.ON_EXPIRY, "DENY")

    def test_9_caps_hold_at_the_limit(self):
        rows = [("G%d" % i, "`f%d.json`" % i) for i in range(50)]
        self.assertEqual(len(ok(self, rp.parse_cover, cover_text(rows))["named"]), 50)
        rows = [("G%d" % i, ", ".join("`f%d_%d.json`" % (i, j) for j in range(10))) for i in range(50)]
        self.assertEqual(len(ok(self, rp.parse_cover, cover_text(rows))["named"]), 500)
        names, _ = ok(self, rp._expand, "f_{0,1,2,3,4}{0,1,2,3,4,5,6,7,8,9}{0,1,2,3,4,5,6,7,8,9}.json")
        self.assertEqual(len(names), 500)
        self.assertEqual(len(ok(self, rp.parse_listing, "".join("f%d\n" % i for i in range(2000)))), 2000)
        self.assertEqual(len(ok(self, rp.parse_ignore, "".join("*.x%d\n" % i for i in range(999)))), 999)
        self.assertEqual(ok(self, rp.parse_listing, "a" * 255 + "\n"), ["a" * 255])
        names, _ = rp._expand("a" * 255)
        self.assertEqual(names, ["a" * 255])
        names, why = rp._expand("a" * 256)
        self.assertIsNone(names)


class LooseNameTests(unittest.TestCase):
    """A token that reads as one file must be checked: a missing one is FAIL, never a quiet PASS."""

    def check(self, cell, listing):
        cover = rp.parse_cover("# c\n\n## Files\n\n| Group | Files | Note |\n|---|---|---|\n| Data | %s | n |\n" % cell)
        return rp.check(cover, listing)

    def test_space_at_plus_tilde_and_dot_names_are_checked(self):
        res = self.check("`run 3.jsonl`, `run@2.jsonl`, `a+b.json`, `c~.json`, `.hidden.json`", ["x.json"])
        self.assertEqual(res["result"], "FAIL")
        self.assertEqual(sorted(f["name"] for f in res["findings"] if f["level"] == "FAIL"),
                         [".hidden.json", "a+b.json", "c~.json", "run 3.jsonl", "run@2.jsonl"])
        self.assertEqual(res["unparsed"], 0)

    def test_path_qualified_name_checks_its_last_segment(self):
        res = self.check("`research/uptake-e2/e2_battery.jsonl`", ["x.json"])
        self.assertEqual([(f["code"], f["name"]) for f in res["findings"] if f["level"] == "FAIL"],
                         [("missing_named_file", "e2_battery.jsonl")])
        self.assertEqual(self.check("`research/uptake-e2/e2_battery.jsonl`", ["e2_battery.jsonl"])["result"], "PASS")

    def test_ranges_globs_lists_and_bare_dirs_stay_unparsed(self):
        res = self.check("`CORRECTION_01…03`, `e1_*.json`, `a.json, b.json`, `sub/`, ` lead.json`, `x/ y.json`, `run*/y.json`",
                         ["x.json"])
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["unparsed"], 7)


class ShapeTests(unittest.TestCase):
    def test_unicode_nfd_listing_matches_nfc_cover(self):
        res = result("unicode/cover.md", "unicode/listing_nfd.txt")
        self.assertEqual((res["result"], res["named"], res["missing"]), ("PASS", 4, 0))
        cover = rp.parse_cover(rp.read_text(fx("unicode", "cover.md"), "c"))
        self.assertIn(unicodedata.normalize("NFC", "측정_가.json"), [f["name"] for f in cover["named"]])

    def test_case_sensitive_names(self):
        cover = rp.parse_cover(cover_text([("A", "`Data.json`")]))
        res = rp.check(cover, ["data.json"])
        self.assertEqual(codes(res, "FAIL"), [("missing_named_file", "Data.json")])

    def test_empty_listing_names_every_file_missing(self):
        cover = rp.parse_cover(rp.read_text(fx("e2", "cover.md"), "c"))
        res = rp.check(cover, rp.parse_listing(""))
        self.assertEqual(res["missing"], 13)

    def test_table_ends_at_first_non_table_line_and_fence_headings_skip(self):
        text = ("# t\n\n```\n## Files\n```\n\n## Files\n\n| Files | Group |\n| --- | :---: |\n| `a.json` | A |\n\n"
                "| `b.json` | B |\n")
        cover = ok(self, rp.parse_cover, text)
        self.assertEqual([f["name"] for f in cover["named"]], ["a.json"])
        self.assertEqual(cover["groups"], ["A"])

    def test_tool_writes_nothing(self):
        before = sorted(os.listdir(fx("e1")))
        p = tool("--cover", fx("e1", "cover.md"), "--listing", fx("e1", "listing.txt"), "--ignore",
                 fx("ignore_rules.txt"))
        self.assertEqual(p.returncode, 1)
        self.assertEqual(sorted(os.listdir(fx("e1"))), before)
        self.assertFalse(os.path.exists(fx("e1", "e1_battery.jsonl")))

    def test_json_mode(self):
        p = tool("--json", "--cover", fx("e2", "cover.md"), "--listing", fx("e2", "listing.txt"), "--ignore",
                 fx("ignore_rules.txt"), "--record-path", "research/uptake-e2")
        self.assertEqual(p.returncode, 1)
        data = json.loads(p.stdout)
        self.assertEqual((data["missing"], data["result"], data["on_expiry"]), (2, "FAIL", "DENY"))
        self.assertEqual(data["record_path"], "research/uptake-e2")
        self.assertEqual(data["ignore_rules"], 6)

    def test_pass_exit_zero(self):
        p = tool("--cover", fx("e1", "cover.md"), "--listing", fx("e1", "listing_complete.txt"))
        self.assertEqual((p.returncode, p.stderr), (0, ""))
        self.assertIn("result: PASS", p.stdout)


class DemoTests(unittest.TestCase):
    def test_demo_is_deterministic_and_says_what_it_should(self):
        runs = [subprocess.run([sys.executable, "-B", os.path.join(HERE, "demo.py")], capture_output=True,
                               timeout=120) for _ in range(2)]
        self.assertEqual(runs[0].returncode, 0)
        self.assertEqual(runs[0].stdout, runs[1].stdout)
        text = runs[0].stdout.decode("utf-8")
        self.assertEqual(text.count("INFO ignored_by_pattern *.jsonl"), 8)
        self.assertIn("named: 20  listed: 20  missing: 4  unparsed: 2", text)
        self.assertIn("named: 13  listed: 12  missing: 2  unparsed: 0", text)
        self.assertIn("FAIL missing_receipt PREREG_PUBLISH_RECEIPT.json", text)
        self.assertIn("== E1 against a complete listing (exit 0)", text)
        self.assertIn("e1_screen.jsonl", text)
        self.assertNotIn(HERE, text)


class EvidenceTests(unittest.TestCase):
    def test_evidence_matches_a_fresh_run(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            ev = json.load(fh)
        self.assertEqual(ev["on_expiry"], "DENY")
        self.assertTrue(all(u["status"] == "UNVERIFIED" for u in ev["on_unmeasured"]))
        self.assertEqual(ev["timeouts"]["mutants"]["seconds"], mutants.TIMEOUT["seconds"])
        self.assertEqual(ev["timeouts"]["mutants"]["on_expiry"], "DENY")
        for key, cover, listing in (("e1", "e1/cover.md", "e1/listing.txt"), ("e2", "e2/cover.md", "e2/listing.txt")):
            res = result(cover, listing, ignore="ignore_rules.txt")
            m = ev["measured"][key]
            self.assertEqual((m["named"], m["listed"], m["missing"], m["unparsed"]),
                             (res["named"], res["listed"], res["missing"], res["unparsed"]))
            self.assertEqual(m["missing_ignored_by_pattern"],
                             sum(1 for f in res["findings"] if f["level"] == "FAIL" and f["ignored_by_pattern"]))


class MutantsHarnessTests(unittest.TestCase):
    def test_timeout_declared_and_never_a_kill(self):
        self.assertEqual(mutants.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})
        self.assertEqual(mutants.classify(True, None, ""), "TIMEOUT")
        self.assertFalse(mutants.is_kill("TIMEOUT"))

    def test_crash_is_not_a_kill(self):
        self.assertEqual(mutants.classify(False, 1, "FAILED (failures=3)"), "CRASH")
        self.assertEqual(mutants.classify(True, 1, "FAILED (errors=2)"), "CRASH")
        self.assertFalse(mutants.is_kill("CRASH"))

    def test_kill_needs_a_test_failure(self):
        self.assertEqual(mutants.classify(True, 1, "...\nFAILED (failures=2)\n"), "KILLED")
        self.assertEqual(mutants.classify(True, 1, "FAILED (failures=1, errors=4)"), "KILLED")
        self.assertEqual(mutants.classify(True, 0, "OK"), "SURVIVED")
        self.assertEqual(mutants.classify(True, 1, "no summary"), "CRASH")
        self.assertTrue(mutants.is_kill("KILLED"))

    def test_summary_counts(self):
        line = mutants.summary(["KILLED", "KILLED", "TIMEOUT", "CRASH", "SURVIVED"])
        self.assertEqual(line, "mutants: killed 2 / timeout 1 / crash 1 / survived 1 of 5 (a timeout or crash is "
                               "never a kill; on_expiry DENY)")


if __name__ == "__main__":
    unittest.main()
