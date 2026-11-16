"""Tests for w25-daily-issue-index (unittest, stdlib only)."""

import contextlib
import hashlib
import io
import json
import math
import os
import re
import tempfile
import unittest
from unittest import mock

import demo
import issue_index as ii

HERE = os.path.dirname(os.path.abspath(__file__))
DAILY = os.path.join(HERE, "fixtures", "daily_list.tsv")
CLOSES = os.path.join(HERE, "fixtures", "annals_closes.tsv")
DEMO = os.path.join(HERE, "demo", "issues.tsv")
DEMO_STDOUT_SHA256 = "9360bac2557738984c84bf61a4add84bd3bfd39c2362c06cd8b632398246d70e"
DAILY_SHA256 = "bc3f37dec58492e02a5f1cdc82450967017393685a59a605399dddd436a09799"
CLOSES_SHA256 = "39a990a52f535d6bc54654efccfe50d9dcfd8a40bc07a320a95f17ac7a01af51"
H = ii.TSV_HEADER + "\n"


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def idx(no, date, ident=None, en="yes", ko="yes", name="daily"):
    return "\t".join([name, "index", str(no) if ident is None else ident, str(no), date, en, ko])


def close(name, no, date=""):
    return "\t".join([name, "close", "", str(no), date, "", ""])


def run_text(*texts):
    """Write each text to its own fixture file and run the check."""
    with tempfile.TemporaryDirectory() as td:
        paths = []
        for i, text in enumerate(texts):
            p = os.path.join(td, "f%d.tsv" % i)
            with open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            paths.append(p)
        return ii.run(paths)


def run_rows(*lines):
    return run_text(H + "\n".join(lines) + "\n")


def codes(report, severity=None):
    return sorted((f["code"], f["number"]) for f in report["findings"]
                  if severity is None or f["severity"] == severity)


def cli(argv):
    out = io.BytesIO()

    class _Std(object):
        buffer = out

        def flush(self):
            pass

    err = io.StringIO()
    with mock.patch.object(ii.sys, "stdout", _Std()), contextlib.redirect_stderr(err):
        rc = ii.main(argv)
    return rc, out.getvalue().decode("utf-8")


SEQ = [idx(5, "2026-08-25"), idx(4, "2026-08-24"), idx(3, "2026-08-23"), idx(2, "2026-08-22"), idx(1, "2026-08-21")]


class LiveFixtures(unittest.TestCase):
    """The observed Daily list and annals closes (review verdict section 2a, section 3 T2)."""

    def test_fixture_hashes_pinned(self):
        self.assertEqual(sha256_file(DAILY), DAILY_SHA256)
        self.assertEqual(sha256_file(CLOSES), CLOSES_SHA256)

    def test_daily_list_shape(self):
        r = ii.run([DAILY])
        self.assertEqual(r["rows"], 83)
        self.assertEqual(r["lists"], {"daily": {"kind": "index", "rows": 83, "numbers": "1..83"}})

    def test_daily_list_is_pass_with_info_only(self):
        r = ii.run([DAILY])
        self.assertEqual(r["decision"], "PASS")
        self.assertEqual(r["counts"], {"FAIL": 0, "INFO": 5})
        got = [(f["code"], f["severity"], f["found"]) for f in r["findings"]]
        self.assertEqual(got, [
            ("date_gap", "INFO", "2026-08-25"),
            ("date_gap", "INFO", "2026-08-29"),
            ("date_gap", "INFO", "2026-08-31"),
            ("date_gap", "INFO", "2026-11-10"),
            ("published_late", "INFO", "No. 82 · 2026-11-13"),
        ])

    def test_live_82_above_81_is_info_and_exit_0(self):
        # review verdict MEDIUM-1: the (b) test must assert severity INFO and exit 0
        r = ii.run([DAILY])
        late = [f for f in r["findings"] if f["code"] == "published_late"]
        self.assertEqual(len(late), 1)
        self.assertEqual(late[0]["severity"], "INFO")
        self.assertEqual(late[0]["number"], 82)
        self.assertEqual(late[0]["expected"], "dated on or after No. 81 · 2026-11-14")
        rc, _ = cli([DAILY])
        self.assertEqual(rc, 0)

    def test_live_with_closes(self):
        # PR review M1: both in-close repeats are same-day reissues in the annals text -> INFO
        r = ii.run([DAILY, CLOSES])
        self.assertEqual(r["decision"], "PASS")
        self.assertEqual(r["rows"], 99)
        self.assertEqual(r["counts"], {"FAIL": 0, "INFO": 10})
        fails = [f for f in r["findings"] if f["severity"] == "FAIL"]
        self.assertEqual(fails, [])
        twice = [(f["severity"], f["list"], f["number"], f["line"], f["found"])
                 for f in r["findings"] if f["code"] == "counted_twice"]
        self.assertEqual(twice, [
            ("INFO", "annals-day-94", 78, 15, "Daily 78 named 2 times in annals-day-94 (lines 14,15)"),
            ("INFO", "annals-day-91", 74, 22, "Daily 74 named 2 times in annals-day-91 (lines 21,22)"),
        ])
        self.assertNotIn("duplicate_listing", [f["code"] for f in r["findings"]])
        reissued = [(f["list"], f["number"], f["found"]) for f in r["findings"] if f["code"] == "reissued"]
        self.assertEqual(reissued, [
            ("annals-day-97", 80, "Daily 80 named in annals-day-98, annals-day-97"),
            ("annals-day-94", 78, "Daily 78 named in annals-day-96, annals-day-94"),
            ("annals-day-92", 76, "Daily 76 named in annals-day-93, annals-day-92"),
        ])
        for f in r["findings"]:
            if f["code"] == "reissued":
                self.assertEqual(f["severity"], "INFO")
        self.assertNotIn("not_in_index", [f["code"] for f in r["findings"]])
        self.assertNotIn("date_mismatch", [f["code"] for f in r["findings"]])
        rc, _ = cli([DAILY, CLOSES])
        self.assertEqual(rc, 0)

    def test_live_with_closes_text(self):
        rc, out = cli([DAILY, CLOSES])
        self.assertEqual(rc, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], "w25-daily-issue-index decision=PASS on_expiry=DENY")
        self.assertEqual(lines[1], "files=2 rows=99 lists=10 (index=1 close=9) comment_lines=9 "
                                   "blank_lines=0 FAIL=0 INFO=10")
        self.assertIn("INFO L15   counted_twice annals-day-94 78 found='Daily 78 named 2 times in "
                      "annals-day-94 (lines 14,15)' expected='a fact; a close may count a same-day "
                      "reissue again'", lines)

    def test_closes_only_reports_index_absent(self):
        r = ii.run([CLOSES])
        self.assertIn(("index_absent", None), codes(r, "INFO"))
        self.assertIn(("counted_twice", 74), codes(r, "INFO"))
        self.assertIn(("counted_twice", 78), codes(r, "INFO"))
        self.assertEqual(r["decision"], "PASS")  # INFO only; the cross-checks did not run
        self.assertEqual(r["counts"]["FAIL"], 0)

    def test_comment_and_blank_counts_live(self):
        r = ii.run([DAILY, CLOSES])
        self.assertEqual((r["comment_lines"], r["blank_lines"], r["files"]), (9, 0, 2))


class Severity(unittest.TestCase):
    def test_published_late_uses_first_listing_of_a_number(self):
        r = run_rows(idx(2, "2026-11-13"), idx(2, "2026-11-20"), idx(1, "2026-11-14"))
        self.assertIn(("published_late", 2), codes(r))
        self.assertIn(("duplicate_listing", 2), codes(r))

    def test_clean_list_passes(self):
        r = run_rows(*SEQ)
        self.assertEqual((r["decision"], r["findings"]), ("PASS", []))

    def test_inversion_is_info_published_late(self):
        r = run_rows(idx(3, "2026-11-15"), idx(2, "2026-11-13"), idx(1, "2026-11-14"))
        self.assertEqual(r["decision"], "PASS")
        self.assertEqual(codes(r), [("published_late", 2)])

    def test_inversion_compares_neighbour_numbers_by_number(self):
        r = run_rows(idx(1, "2026-11-14"), idx(3, "2026-11-15"), idx(2, "2026-11-13"))
        self.assertIn(("published_late", 2), codes(r))
        self.assertIn(("listing_order", 3), codes(r))

    def test_inversion_uses_neighbours_only(self):
        r = run_rows(idx(3, "2026-11-12"), idx(2, "2026-11-14"), idx(1, "2026-11-13"))
        self.assertEqual(codes(r), [("published_late", 3)])

    def test_equal_dates_are_shared_date_not_late(self):
        r = run_rows(idx(2, "2026-11-13"), idx(1, "2026-11-13"))
        self.assertEqual(codes(r), [("shared_date", 2)])
        self.assertEqual(r["findings"][0]["found"], "2026-11-13 on No. 1,2")
        self.assertEqual(r["decision"], "PASS")

    def test_date_gap_single_and_run(self):
        r = run_rows(idx(3, "2026-11-15"), idx(2, "2026-11-11"), idx(1, "2026-11-09"))
        gaps = [f["found"] for f in r["findings"] if f["code"] == "date_gap"]
        self.assertEqual(gaps, ["2026-11-10", "2026-11-12..2026-11-14 (3 days)"])
        self.assertEqual(r["decision"], "PASS")

    def test_date_gap_across_years_without_iteration(self):
        r = run_rows(idx(2, "9999-12-31"), idx(1, "0001-01-01"))
        gaps = [f["found"] for f in r["findings"] if f["code"] == "date_gap"]
        self.assertEqual(gaps, ["0001-01-02..9999-12-30 (3652057 days)"])

    def test_missing_number_fails(self):
        r = run_rows(idx(4, "2026-08-24"), idx(2, "2026-08-22"), idx(1, "2026-08-21"))
        self.assertEqual(r["decision"], "FAIL")
        f = [f for f in r["findings"] if f["code"] == "missing_number"]
        self.assertEqual((f[0]["found"], f[0]["expected"], f[0]["severity"]), ("missing 3", "1..4 contiguous", "FAIL"))

    def test_missing_number_counts_from_lowest_listed(self):
        r = run_rows(idx(9, "2026-08-29"), idx(8, "2026-08-28"))
        self.assertEqual(r["decision"], "PASS")

    def test_missing_number_list_capped(self):
        r = run_rows(idx(100, "2026-08-24"), idx(1, "2026-08-21"))
        f = [f for f in r["findings"] if f["code"] == "missing_number"][0]
        self.assertEqual(f["found"], "missing " + ",".join(str(n) for n in range(2, 22)) + ",... (98 missing)")

    def test_missing_number_exactly_cap_not_truncated(self):
        r = run_rows(idx(22, "2026-08-24"), idx(1, "2026-08-21"))
        f = [f for f in r["findings"] if f["code"] == "missing_number"][0]
        self.assertEqual(f["found"], "missing " + ",".join(str(n) for n in range(2, 22)))

    def test_id_mismatch_fails(self):
        r = run_rows(idx(2, "2026-08-22", ident="12"), idx(1, "2026-08-21"))
        self.assertEqual(r["decision"], "FAIL")
        f = r["findings"][0]
        self.assertEqual((f["code"], f["found"], f["number"]), ("id_mismatch", "id=12 no=2", 2))

    def test_unparsed_id_fails(self):
        r = run_rows(idx(2, "2026-08-22", ident="issue-2"), idx(1, "2026-08-21"))
        self.assertEqual(codes(r), [("unparsed_number", 2)])
        self.assertEqual(r["findings"][0]["found"], "id='issue-2'")

    def test_language_missing_fails(self):
        r = run_rows(idx(2, "2026-08-22", en="no"), idx(1, "2026-08-21", ko="no"))
        self.assertEqual(codes(r), [("language_missing", 1), ("language_missing", 2)])
        self.assertEqual(r["decision"], "FAIL")

    def test_duplicate_listing_in_index_fails(self):
        r = run_rows(idx(2, "2026-08-22"), idx(2, "2026-08-22"), idx(1, "2026-08-21"))
        self.assertIn(("duplicate_listing", 2), codes(r, "FAIL"))
        f = [f for f in r["findings"] if f["code"] == "duplicate_listing"][0]
        self.assertEqual((f["line"], f["found"]), (3, "No. 2 listed 2 times (lines 2,3)"))

    def test_triple_listing(self):
        r = run_rows(idx(1, "2026-08-21"), idx(1, "2026-08-21"), idx(1, "2026-08-21"))
        f = [f for f in r["findings"] if f["code"] == "duplicate_listing"][0]
        self.assertEqual(f["found"], "No. 1 listed 3 times (lines 2,3,4)")

    def test_repeat_in_one_close_is_info_counted_twice(self):
        r = run_rows(*(SEQ + [close("day-91", 4), close("day-91", 4)]))
        self.assertEqual(r["decision"], "PASS")
        self.assertEqual(codes(r), [("counted_twice", 4)])
        f = r["findings"][0]
        self.assertEqual((f["severity"], f["line"], f["found"], f["expected"]),
                         ("INFO", 8, "Daily 4 named 2 times in day-91 (lines 7,8)",
                          "a fact; a close may count a same-day reissue again"))

    def test_day_94_style_repeat_with_date_is_info(self):
        r = run_rows(*(SEQ + [close("day-94", 5, "2026-08-25"), close("day-94", 5, "2026-08-25")]))
        self.assertEqual(r["decision"], "PASS")
        self.assertEqual(codes(r), [("counted_twice", 5)])
        rc, _ = cli_rows(*(SEQ + [close("day-94", 5, "2026-08-25"), close("day-94", 5, "2026-08-25")]))
        self.assertEqual(rc, 0)

    def test_triple_in_one_close_is_info(self):
        r = run_rows(*(SEQ + [close("c", 2), close("c", 2), close("c", 2)]))
        self.assertEqual(codes(r), [("counted_twice", 2)])
        self.assertEqual(r["findings"][0]["found"], "Daily 2 named 3 times in c (lines 7,8,9)")
        self.assertEqual(r["decision"], "PASS")

    def test_repeat_in_index_still_fails_next_to_close_repeat(self):
        r = run_rows(idx(2, "2026-08-22"), idx(2, "2026-08-22"), idx(1, "2026-08-21"),
                     close("c", 2), close("c", 2))
        self.assertEqual(codes(r, "FAIL"), [("duplicate_listing", 2)])
        self.assertEqual(codes(r, "INFO"), [("counted_twice", 2), ("listing_order", 2)])
        self.assertEqual(r["decision"], "FAIL")

    def test_close_repeat_still_checks_index_and_date(self):
        r = run_rows(*(SEQ + [close("c", 9), close("c", 9), close("d", 5, "2026-08-01"),
                              close("d", 5, "2026-08-01")]))
        self.assertEqual(codes(r, "FAIL"), [("date_mismatch", 5), ("date_mismatch", 5),
                                            ("not_in_index", 9), ("not_in_index", 9)])
        self.assertEqual(codes(r, "INFO"), [("counted_twice", 5), ("counted_twice", 9)])

    def test_daily_80_style_reissue_across_closes_is_info(self):
        r = run_rows(*(SEQ + [close("day-98", 5, "2026-08-25"), close("day-97", 5, "2026-08-25")]))
        self.assertEqual(r["decision"], "PASS")
        self.assertEqual(codes(r), [("reissued", 5)])
        self.assertEqual(r["findings"][0]["found"], "Daily 5 named in day-98, day-97")
        self.assertEqual(r["findings"][0]["line"], 8)

    def test_reissue_and_counted_twice_together(self):
        r = run_rows(*(SEQ + [close("a", 3), close("b", 3), close("b", 3)]))
        self.assertEqual(codes(r), [("counted_twice", 3), ("reissued", 3)])
        self.assertEqual(r["decision"], "PASS")
        re_f = [f for f in r["findings"] if f["code"] == "reissued"][0]
        self.assertEqual(re_f["found"], "Daily 3 named in a, b")

    def test_reissue_three_lists(self):
        r = run_rows(*(SEQ + [close("a", 3), close("b", 3), close("c", 3)]))
        self.assertEqual(r["findings"][0]["found"], "Daily 3 named in a, b, c")

    def test_close_number_not_in_index_fails(self):
        r = run_rows(*(SEQ + [close("day-96", 9)]))
        self.assertEqual(codes(r), [("not_in_index", 9)])
        self.assertEqual(r["decision"], "FAIL")

    def test_close_date_mismatch_fails(self):
        r = run_rows(*(SEQ + [close("day-96", 5, "2026-08-24")]))
        self.assertEqual(codes(r), [("date_mismatch", 5)])
        self.assertEqual(r["findings"][0]["expected"], "No. 5 · 2026-08-25")

    def test_close_date_matches(self):
        r = run_rows(*(SEQ + [close("day-96", 5, "2026-08-25")]))
        self.assertEqual(r["findings"], [])

    def test_close_without_date_is_fine(self):
        r = run_rows(*(SEQ + [close("day-96", 5)]))
        self.assertEqual(r["findings"], [])

    def test_close_bad_date_unparsed(self):
        r = run_rows(*(SEQ + [close("day-96", 5, "November 12")]))
        self.assertEqual(codes(r), [("unparsed_date", 5)])

    def test_close_only_no_cross_checks(self):
        r = run_rows(close("a", 9, "2026-01-01"))
        self.assertEqual(codes(r), [("index_absent", None)])
        self.assertEqual(r["decision"], "PASS")

    def test_two_index_lists_checked_separately(self):
        r = run_rows(idx(2, "2026-08-22", name="a"), idx(2, "2026-08-22", name="b"))
        self.assertEqual(codes(r), [])

    def test_listing_order_fact(self):
        r = run_rows(idx(1, "2026-08-21"), idx(2, "2026-08-22"), idx(3, "2026-08-23"))
        f = [f for f in r["findings"] if f["code"] == "listing_order"][0]
        self.assertEqual((f["severity"], f["found"], f["line"]), ("INFO", "2 of 2 adjacent pairs not newest-first", 3))
        self.assertEqual(r["decision"], "PASS")

    def test_every_code_has_a_severity_and_info_never_fails(self):
        self.assertEqual(set(ii.CODE_SEVERITY.values()), {"FAIL", "INFO"})
        info = ("published_late", "date_gap", "reissued", "counted_twice", "shared_date", "listing_order",
                "index_absent", "list_name_form")
        fail = ("id_mismatch", "missing_number", "out_of_range", "duplicate_listing", "language_missing",
                "unparsed_number", "unparsed_date", "unicode_field", "not_in_index", "date_mismatch")
        for code in info:
            self.assertEqual(ii.CODE_SEVERITY[code], "INFO")
        for code in fail:
            self.assertEqual(ii.CODE_SEVERITY[code], "FAIL")
        self.assertEqual(set(ii.CODE_SEVERITY), set(info) | set(fail))

    def test_findings_sorted_fail_first(self):
        r = ii.run([DAILY, CLOSES])
        sev = [f["severity"] for f in r["findings"]]
        self.assertEqual(sev, sorted(sev, key=lambda s: ii.SEVERITY_ORDER[s]))


# Decorated or folded number variants (in the style of the sibling build's M1 probe).
FOLDED_NO = ["\uff18\uff12", "\u0668\u0662", "\u06f8\u06f2", "\u096e\u0968", "\u09ee\u09e8",
             "\u200b82", "8\u200d2", "82\u00ad", "\ufeff82", "8\u20602", "82\u034f", "82\ufe0f",
             "\u3164" + "82", "82\U000e0101", "\u2078\u00b2"]
UNPARSED_NO = ["#82", "No. 82", "No.82", "82\ud654", "\uc81c82\ud638", "(82)", "82.", "82.0", "+82", "-82",
               "082", " 82", "82 ", "8 2", "", "eighty-two", "\u2167", "8\u00a02", "1234567", "0"]


class Folding(unittest.TestCase):
    def _late_row(self, no_text):
        return run_rows(idx(83, "2026-11-15"), "daily\tindex\t82\t" + no_text + "\t2026-11-13\tyes\tyes",
                        idx(81, "2026-11-14"))

    def test_folded_variants_fail_unicode_field_and_parse(self):
        for v in FOLDED_NO:
            with self.subTest(v=ascii(v)):
                r = self._late_row(v)
                self.assertEqual(r["decision"], "FAIL")
                self.assertIn("unicode_field", [f["code"] for f in r["findings"]])
                self.assertNotIn("unparsed_number", [f["code"] for f in r["findings"]])
                if ii.fold(v) == "82":
                    self.assertNotIn("id_mismatch", [f["code"] for f in r["findings"]])

    def test_unparsed_variants_fail(self):
        for v in UNPARSED_NO:
            with self.subTest(v=ascii(v)):
                r = self._late_row(v)
                self.assertEqual(r["decision"], "FAIL")
                self.assertIn("unparsed_number", [f["code"] for f in r["findings"]])

    def test_edge_whitespace_variant_flags_both(self):
        for v in ("\u00a082", "82\u3000"):
            with self.subTest(v=ascii(v)):
                got = [f["code"] for f in self._late_row(v)["findings"]]
                self.assertIn("unicode_field", got)
                self.assertIn("unparsed_number", got)

    def test_no_variant_passes(self):
        self.assertEqual(len(FOLDED_NO) + len(UNPARSED_NO), 35)
        for v in FOLDED_NO + UNPARSED_NO:
            with self.subTest(v=ascii(v)):
                rc, _ = cli_rows(idx(83, "2026-11-15"), "daily\tindex\t82\t" + v + "\t2026-11-13\tyes\tyes")
                self.assertNotEqual(rc, 0)

    def test_superscript_folds_to_82(self):
        self.assertEqual(ii.fold("\u2078\u00b2"), "82")
        self.assertEqual(ii.fold("\u2167"), "VIII")

    def test_fold_quotes_original(self):
        r = self._late_row("\uff18\uff12")
        f = [f for f in r["findings"] if f["code"] == "unicode_field"][0]
        self.assertEqual((f["found"], f["expected"], f["line"]), ("no='\uff18\uff12'", "no='82'", 3))

    def test_folded_date_and_kind_fields(self):
        r = run_rows("daily\t\uff49ndex\t1\t1\t\uff12026-08-21\tyes\tye\u200bs")
        found = sorted(f["found"] for f in r["findings"] if f["code"] == "unicode_field")
        self.assertEqual(found, ["date='\uff12026-08-21'", "kind='\uff49ndex'", "ko='ye\\u200bs'"])
        self.assertEqual(r["decision"], "FAIL")

    def test_bad_dates(self):
        for d in ("2026/11/13", "2026-11-31", "26-11-13", "2026-11-13T00:00", "2026-13-01", "2026\u201011\u201013",
                  "", "2026-11-1", " 2026-11-13"):
            with self.subTest(d=ascii(d)):
                r = run_rows(idx(1, d))
                self.assertIn("unparsed_date", [f["code"] for f in r["findings"]])

    def test_ignorable_set(self):
        for ch in ("\u200b", "\u200d", "\u00ad", "\ufeff", "\u2060", "\u2065", "\u034f", "\u115f", "\u1160",
                   "\u17b4", "\u180b", "\u180f", "\u3164", "\ufe00", "\ufe0f", "\uffa0", "\U000e0001", "\U000e0fff"):
            with self.subTest(ch=ascii(ch)):
                self.assertTrue(ii.ignorable(ch))
        for ch in ("a", "8", " ", "\u00a0", "\u034e", "\u115e", "\u1161", "\u17b3", "\u17b6", "\u180a",
                   "\u3163", "\u3165", "\ufdff", "\ufe10", "\uff9f", "\uffa1", "\U000dffff", "\U000e1000"):
            with self.subTest(ch=ascii(ch)):
                self.assertFalse(ii.ignorable(ch))

    def test_nfd_is_flagged(self):
        r = run_rows("caf\u0065\u0301\tindex\t1\t1\t2026-08-21\tyes\tyes")
        self.assertIn("caf\u00e9", r["lists"])
        self.assertIn("unicode_field", [f["code"] for f in r["findings"]])

    def test_list_names_fold_before_grouping(self):
        r = run_rows(*(SEQ + [close("day\u200b-9", 3), close("day-9", 3)]))
        self.assertIn(("counted_twice", 3), codes(r))
        self.assertIn(("unicode_field", None), codes(r, "FAIL"))
        self.assertEqual(list(r["lists"]), ["daily", "day-9"])

    def test_index_list_names_fold_before_grouping(self):
        r = run_rows(idx(1, "2026-08-21", name="dai\u200bly"), idx(1, "2026-08-21"))
        self.assertIn(("duplicate_listing", 1), codes(r, "FAIL"))


def cli_rows(*lines):
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "f.tsv")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(H + "\n".join(lines) + "\n")
        return cli([p])


class Comments(unittest.TestCase):
    def test_hash_lines_before_header_are_comments_and_counted(self):
        r = run_text("# one\n#two\n\n" + H + "\n".join(SEQ) + "\n")
        self.assertEqual((r["decision"], r["comment_lines"], r["blank_lines"], r["rows"]), ("PASS", 2, 1, 5))

    def test_hash_row_after_header_is_checked_not_skipped(self):
        r = run_rows(*(SEQ + [close("#day-91", 4), close("#day-91", 4)]))
        self.assertEqual(r["rows"], 7)
        self.assertEqual(codes(r), [("counted_twice", 4), ("list_name_form", None)])
        self.assertIn("#day-91", r["lists"])

    def test_hash_index_row_after_header(self):
        r = run_rows(idx(3, "2026-08-23", name="#daily"), idx(1, "2026-08-21", name="#daily"))
        self.assertEqual(r["rows"], 2)
        self.assertIn(("missing_number", None), codes(r, "FAIL"))

    def test_comment_after_header_is_deny(self):
        r = run_text(H + "# note\n" + "\n".join(SEQ) + "\n")
        self.assertEqual((r["decision"], r["reason"]), ("DENY", "fixture_malformed"))
        self.assertIn("line 2", r["detail"])

    def test_blank_lines_after_header_counted(self):
        r = run_text(H + SEQ[0] + "\n\n  \n" + "\n".join(SEQ[1:]) + "\n")
        self.assertEqual((r["blank_lines"], r["rows"]), (2, 5))

    def test_crlf_and_bom(self):
        r = run_text("\ufeff" + (H + "\n".join(SEQ) + "\n").replace("\n", "\r\n"))
        self.assertEqual((r["decision"], r["rows"]), ("PASS", 5))

    def test_no_trailing_newline(self):
        r = run_text(H + "\n".join(SEQ))
        self.assertEqual(r["rows"], 5)

    def test_line_numbers_count_comments(self):
        r = run_text("# c\n" + H + idx(2, "2026-08-22", ident="9") + "\n" + idx(1, "2026-08-21") + "\n")
        self.assertEqual(r["findings"][0]["line"], 3)


class Deny(unittest.TestCase):
    def assertDeny(self, report, reason):
        self.assertEqual(report["decision"], "DENY")
        self.assertEqual(report["on_expiry"], "DENY")
        self.assertEqual(report["reason"], reason)
        self.assertNotIn("findings", report)

    def test_unknown_kind_with_empty_fields(self):
        r = run_rows("c\tlist\t\t5\t\t\t")
        self.assertDeny(r, "fixture_malformed")
        self.assertIn("kind", r["detail"])

    def test_header_only_file_next_to_a_good_file(self):
        r = run_text(H, H + "\n".join(SEQ) + "\n")
        self.assertDeny(r, "fixture_empty")
        self.assertEqual(r["detail"], "no rows after the header")

    def test_indented_hash_before_header_is_not_a_comment(self):
        r = run_text(" # note\n" + H + SEQ[0] + "\n")
        self.assertDeny(r, "fixture_malformed")
        self.assertIn("line 1", r["detail"])

    def test_folded_list_name_in_two_files(self):
        r = run_text(H + close("day\u200b-9", 3) + "\n", H + close("day-9", 3) + "\n")
        self.assertDeny(r, "fixture_malformed")

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertDeny(ii.run([os.path.join(td, "nope.tsv")]), "fixture_missing")

    def test_directory(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertDeny(ii.run([td]), "fixture_unreadable")

    def test_not_utf8(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "x.tsv")
            with open(p, "wb") as fh:
                fh.write(H.encode() + b"\xff\xfe\n")
            self.assertDeny(ii.run([p]), "fixture_unreadable")

    def test_empty_and_header_only(self):
        self.assertDeny(run_text(""), "fixture_empty")
        self.assertDeny(run_text("# only comments\n\n"), "fixture_empty")
        self.assertDeny(run_text(H), "fixture_empty")
        self.assertDeny(run_text(H + "\n\n"), "fixture_empty")

    def test_no_header(self):
        r = run_text("\n".join(SEQ) + "\n")
        self.assertDeny(r, "fixture_malformed")
        self.assertIn("line 1", r["detail"])

    def test_wrong_header(self):
        self.assertDeny(run_text(H.replace("ko", "kr") + SEQ[0] + "\n"), "fixture_malformed")
        self.assertDeny(run_text(" " + H + SEQ[0] + "\n"), "fixture_malformed")

    def test_field_count(self):
        self.assertDeny(run_rows(SEQ[0] + "\textra"), "fixture_malformed")
        self.assertDeny(run_rows("daily\tindex\t1\t1\t2026-08-21\tyes"), "fixture_malformed")

    def test_bad_kind(self):
        self.assertDeny(run_rows("daily\tlist\t1\t1\t2026-08-21\tyes\tyes"), "fixture_malformed")

    def test_bad_presence(self):
        for en, ko in (("y", "yes"), ("yes", ""), ("YES", "yes"), ("yes", "true")):
            with self.subTest(en=en, ko=ko):
                self.assertDeny(run_rows(idx(1, "2026-08-21", en=en, ko=ko)), "fixture_malformed")

    def test_close_with_id_or_languages(self):
        self.assertDeny(run_rows("c\tclose\t5\t5\t\t\t"), "fixture_malformed")
        self.assertDeny(run_rows("c\tclose\t\t5\t\tyes\t"), "fixture_malformed")
        self.assertDeny(run_rows("c\tclose\t\t5\t\t\tyes"), "fixture_malformed")

    def test_list_mixing_kinds(self):
        self.assertDeny(run_rows(idx(1, "2026-08-21", name="x"), close("x", 1)), "fixture_malformed")

    def test_blank_or_padded_list_name(self):
        self.assertDeny(run_rows(idx(1, "2026-08-21", name=" ")), "fixture_malformed")
        self.assertDeny(run_rows(idx(1, "2026-08-21", name=" daily")), "fixture_malformed")
        self.assertDeny(run_rows(idx(1, "2026-08-21", name="\u200b")), "fixture_malformed")

    def test_list_in_two_files(self):
        r = run_text(H + SEQ[0] + "\n", H + SEQ[1] + "\n")
        self.assertDeny(r, "fixture_malformed")

    def test_one_bad_file_denies_all(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertDeny(ii.run([DAILY, os.path.join(td, "nope.tsv")]), "fixture_missing")

    def test_no_paths(self):
        self.assertDeny(ii.run([]), "fixture_missing")
        self.assertDeny(ii.run(DAILY), "fixture_missing")
        self.assertDeny(ii.run([""]), "fixture_missing")
        self.assertDeny(ii.run([None]), "fixture_missing")

    def test_value_and_recursion_errors_are_deny(self):
        for exc in (ValueError, RecursionError):
            with self.subTest(exc=exc.__name__):
                with mock.patch.object(ii, "check", side_effect=exc("x")):
                    self.assertDeny(ii.run([DAILY]), "input_limit")

    def test_oserror_reading_is_unreadable(self):
        with mock.patch("builtins.open", side_effect=PermissionError("x")):
            r = ii.run([DAILY])
        self.assertDeny(r, "fixture_unreadable")
        self.assertEqual(r["detail"], "PermissionError")

    def test_cli_deny_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = cli([os.path.join(td, "nope.tsv")])
        self.assertEqual(rc, 2)
        self.assertEqual(out, "w25-daily-issue-index decision=DENY on_expiry=DENY\nreason=fixture_missing detail=file not found\n")
        self.assertNotIn("PASS", out)

    def test_cli_usage(self):
        for argv in ([], ["--format"], ["--format", "xml", DAILY], [DAILY, "--format", "xml"], ["--bogus", DAILY],
                     [DAILY, "--bogus"], ["--out"]):
            with self.subTest(argv=argv):
                rc, out = cli(argv)
                self.assertEqual(rc, 2)
                self.assertIn("reason=usage", out)

    def test_cli_unwritable_out(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = cli([DAILY, "--out", td])
        self.assertEqual((rc, out), (2, ""))

    def test_cli_out_and_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "r.json")
            rc, out = cli([DAILY, CLOSES, "--out", p, "--format", "json"])
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
        self.assertEqual((rc, out), (0, ""))
        self.assertEqual(data["decision"], "PASS")
        self.assertEqual(data["counts"], {"FAIL": 0, "INFO": 10})
        self.assertEqual((data["first"], data["last"]), (None, None))
        self.assertEqual(data["on_expiry"], "DENY")

    def test_cli_text_pass(self):
        rc, out = cli(["--format", "text", DAILY])
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("w25-daily-issue-index decision=PASS on_expiry=DENY\n"
                                       "files=1 rows=83 lists=1 (index=1 close=0) comment_lines=4 blank_lines=0 FAIL=0 INFO=5\n"))
        self.assertTrue(out.endswith("list daily kind=index rows=83 numbers=1..83\n"))

    def test_deny_json(self):
        r = ii.deny_report("fixture_missing", "file not found")
        self.assertEqual(json.loads(ii.format_json(r))["decision"], "DENY")


class Snapshot(unittest.TestCase):
    """F1: exact str keys, exact types, validated immutable snapshot."""

    def row(self, **kw):
        r = {"list": "daily", "kind": "index", "id": "1", "no": "1", "date": "2026-08-21",
             "en": "yes", "ko": "yes", "line": 1}
        r.update(kw)
        return r

    def assertBad(self, rows):
        with self.assertRaises(ii.InputError) as cm:
            ii.validate_rows(rows)
        self.assertEqual(cm.exception.reason, "fixture_malformed")

    def test_good_row(self):
        snap = ii.validate_rows([self.row()])
        self.assertIs(type(snap), tuple)
        self.assertEqual(snap[0][:8], (1, "daily", "index", "1", "1", "2026-08-21", "yes", "yes"))
        self.assertEqual(ii.check(snap)["decision"], "PASS")
        self.assertEqual(ii.validate_rows((self.row(),)), snap)

    def test_rejects_non_str_values(self):
        class S(str):
            pass
        for bad in (True, False, 1, 1.0, float("nan"), float("inf"), -math.inf, None, b"1", ["1"], S("1")):
            with self.subTest(bad=repr(bad)):
                self.assertBad([self.row(no=bad)])
                self.assertBad([self.row(date=bad)])

    def test_rejects_bad_line(self):
        class I(int):
            pass
        for bad in (True, False, 1.0, float("nan"), float("inf"), "1", 0, -1, I(1), None):
            with self.subTest(bad=repr(bad)):
                self.assertBad([self.row(line=bad)])

    def test_rejects_key_problems(self):
        r = self.row()
        r[1] = "x"
        self.assertBad([r])

        class K(str):
            pass
        r = self.row()
        del r["ko"]
        r[K("ko")] = "yes"
        self.assertBad([r])
        r = self.row()
        del r["ko"]
        self.assertBad([r])
        self.assertBad([self.row(extra="x")])

    def test_rejects_container_types(self):
        class D(dict):
            pass

        class L(list):
            pass
        self.assertBad([D(self.row())])
        self.assertBad(L([self.row()]))
        self.assertBad({"rows": 1})
        self.assertBad("rows")
        self.assertBad([[("list", "daily")]])
        with self.assertRaises(ii.InputError) as cm:
            ii.validate_rows([])
        self.assertEqual(cm.exception.reason, "fixture_empty")

    def test_rejects_control_characters(self):
        for bad in ("1\t", "1\n", "\r1"):
            with self.subTest(bad=repr(bad)):
                self.assertBad([self.row(no=bad)])

    def test_snapshot_detached(self):
        rows = [self.row(), self.row(id="2", no="2", date="2026-08-22", line=2)]
        snap = ii.validate_rows(rows)
        before = ii.check(snap)
        rows[0]["no"] = "9"
        rows.append(self.row(line=3))
        self.assertEqual(ii.check(snap), before)
        with self.assertRaises(TypeError):
            snap[0] = None

    def test_parse_text_type(self):
        with self.assertRaises(ii.InputError) as cm:
            ii.parse_fixture_text(b"x")
        self.assertEqual(cm.exception.reason, "fixture_unreadable")


def run_rows_range(lines, first=None, last=None):
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "f.tsv")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(H + "\n".join(lines) + "\n")
        return ii.run([p], first, last)


def without(path, number):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    lines = text.split("\n")
    drop = [x for x in lines if x.startswith("daily\tindex\t%d\t" % number)]
    if len(drop) != 1:
        raise AssertionError("expected one row of No. %d" % number)
    return "\n".join(x for x in lines if x not in drop)


class DeclaredRange(unittest.TestCase):
    """PR review Low L2: a declared first/last number catches a lost No. 1 or a lost newest issue."""

    def test_live_list_with_declared_range_passes(self):
        r = ii.run([DAILY], 1, 83)
        self.assertEqual((r["decision"], r["counts"]), ("PASS", {"FAIL": 0, "INFO": 5}))
        rc, out = cli([DAILY, "--first", "1", "--last", "83"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.splitlines()[2], "declared first=1 last=83")

    def test_lost_first_issue_fails_only_when_declared(self):
        lines = SEQ[:-1]  # Nos. 5..2, No. 1 lost
        self.assertEqual(run_rows_range(lines)["decision"], "PASS")
        r = run_rows_range(lines, first=1)
        self.assertEqual(codes(r, "FAIL"), [("missing_number", None)])
        f = r["findings"][0]
        self.assertEqual((f["found"], f["expected"]), ("missing 1", "1..5 contiguous"))

    def test_lost_newest_issue_fails_only_when_declared(self):
        lines = SEQ[1:]  # Nos. 4..1, No. 5 lost
        self.assertEqual(run_rows_range(lines)["decision"], "PASS")
        r = run_rows_range(lines, last=5)
        self.assertEqual(codes(r, "FAIL"), [("missing_number", None)])
        self.assertEqual(r["findings"][0]["found"], "missing 5")
        self.assertEqual(r["findings"][0]["expected"], "1..5 contiguous")

    def test_live_list_losing_newest_or_first(self):
        for number in (83, 1):
            with tempfile.TemporaryDirectory() as td:
                p = os.path.join(td, "daily.tsv")
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(without(DAILY, number))
                self.assertEqual(ii.run([p])["decision"], "PASS")
                r = ii.run([p], 1, 83)
                self.assertEqual(r["decision"], "FAIL")
                self.assertEqual([f["found"] for f in r["findings"] if f["code"] == "missing_number"],
                                 ["missing %d" % number])
                rc, _ = cli([p, "--first", "1", "--last", "83"])
                self.assertEqual(rc, 1)

    def test_number_outside_declared_range_fails(self):
        r = run_rows_range([idx(7, "2026-08-27")] + SEQ, first=2, last=5)
        got = sorted((f["code"], f["number"], f["line"]) for f in r["findings"] if f["severity"] == "FAIL")
        self.assertEqual(got, [("out_of_range", 1, 7), ("out_of_range", 7, 2)])
        f = [f for f in r["findings"] if f["code"] == "out_of_range"][0]
        self.assertEqual(f["expected"], "a number in the declared range 2..5")
        self.assertNotIn("missing_number", [f["code"] for f in r["findings"]])

    def test_missing_counts_only_inside_declared_range(self):
        r = run_rows_range([idx(7, "2026-08-27"), idx(5, "2026-08-25"), idx(3, "2026-08-23")], first=1, last=5)
        miss = [f for f in r["findings"] if f["code"] == "missing_number"][0]
        self.assertEqual((miss["found"], miss["expected"]), ("missing 1,2,4", "1..5 contiguous"))
        self.assertIn(("out_of_range", 7), codes(r, "FAIL"))

    def test_first_equal_last(self):
        r = run_rows_range([idx(1, "2026-08-21")], first=1, last=1)
        self.assertEqual(r["decision"], "PASS")

    def test_close_numbers_are_not_range_checked(self):
        r = run_rows_range(SEQ + [close("c", 3)], first=1, last=5)
        self.assertEqual(r["findings"], [])
        r = run_rows_range(SEQ + [close("c", 9)], first=1, last=5)
        self.assertEqual(codes(r), [("not_in_index", 9)])

    def test_bad_declared_values_deny(self):
        for first, last in ((0, None), (None, 0), (True, None), (None, False), (1.0, None),
                            (float("nan"), None), (float("inf"), None), ("1", None), (None, 1000000),
                            (5, 4)):
            r = run_rows_range(SEQ, first, last)
            self.assertEqual((r["decision"], r["reason"]), ("DENY", "bad_range"), (first, last))

    def test_bad_declared_cli_values_deny(self):
        for argv in (["--first", "0"], ["--first", "x"], ["--last", "\uff18\uff13"], ["--last", "083"],
                     ["--first", "-1"], ["--first", "5", "--last", "4"], ["--first"], ["--last", "1000000"]):
            rc, out = cli([DAILY] + argv)
            self.assertEqual(rc, 2, argv)
            self.assertTrue(out.startswith("w25-daily-issue-index decision=DENY on_expiry=DENY\n"), argv)


class ListNames(unittest.TestCase):
    """PR review Low L4: a look-alike list name is reported as a fact, not checked silently apart."""

    def test_homoglyph_list_name_is_info(self):
        r = run_rows(idx(2, "2026-08-22"), idx(1, "2026-08-21", name="d\u0430ily"))
        self.assertIn(("list_name_form", None), codes(r, "INFO"))
        f = [f for f in r["findings"] if f["code"] == "list_name_form"][0]
        self.assertEqual((f["list"], f["line"], f["found"]), ("d\u0430ily", 3, "list='d\\u0430ily'"))
        self.assertEqual(len(r["lists"]), 2)

    def test_hash_list_name_is_info(self):
        r = run_rows(idx(3, "2026-08-23", name="#daily"), idx(1, "2026-08-21", name="#daily"))
        self.assertEqual([f["code"] for f in r["findings"] if f["code"] == "list_name_form"], ["list_name_form"])

    def test_plain_names_not_flagged(self):
        for name in ("daily", "annals-day-100", "Draft-2", "a"):
            r = run_rows(idx(1, "2026-08-21", name=name))
            self.assertEqual(r["findings"], [], name)
        for name in ("a_b", "a--b", "-a", "a-", "a.b", "a b"):
            r = run_rows(idx(1, "2026-08-21", name=name))
            self.assertEqual(codes(r), [("list_name_form", None)], name)

    def test_live_names_not_flagged(self):
        r = ii.run([DAILY, CLOSES])
        self.assertNotIn("list_name_form", [f["code"] for f in r["findings"]])

    def test_one_finding_per_list(self):
        r = run_rows(idx(2, "2026-08-22", name="#d"), idx(1, "2026-08-21", name="#d"), close("#c", 1))
        self.assertEqual(codes(r), [("list_name_form", None), ("list_name_form", None)])


class Demo(unittest.TestCase):
    def test_demo_stdout_sha_pinned(self):
        text = demo.render()
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), DEMO_STDOUT_SHA256)

    def test_demo_main_writes_same_bytes(self):
        buf = io.BytesIO()

        class _Std(object):
            buffer = buf

            def flush(self):
                pass
        with mock.patch.object(demo.sys, "stdout", _Std()):
            self.assertEqual(demo.main(), 0)
        self.assertEqual(hashlib.sha256(buf.getvalue()).hexdigest(), DEMO_STDOUT_SHA256)

    def test_demo_covers_each_planted_defect(self):
        r = ii.run([DEMO])
        got = set(f["code"] for f in r["findings"])
        self.assertEqual(got, {"missing_number", "id_mismatch", "language_missing", "unicode_field",
                               "duplicate_listing", "not_in_index", "date_gap", "published_late",
                               "listing_order", "reissued"})


class Hygiene(unittest.TestCase):
    def test_module_imports_stdlib_only_and_no_hashing(self):
        with open(os.path.join(HERE, "issue_index.py"), encoding="utf-8") as fh:
            src = fh.read()
        imports = sorted(set(re.findall(r"^(?:import|from) (\w+)", src, re.M)))
        self.assertEqual(imports, ["datetime", "json", "os", "re", "sys", "unicodedata"])
        for word in ("hashlib", "hmac", "subprocess", "socket", "urllib", "sqlite3"):
            self.assertNotIn(word, src)

    def test_readme_disclaimer(self):
        with open(os.path.join(HERE, "README.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("not a signed, hash-chained or append-only", text)
        self.assertIn("does not verify editor signatures", text)

    def test_evidence_marked_unverified(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as fh:
            ev = json.load(fh)
        self.assertEqual(ev["status"], "UNVERIFIED")
        for s in ev["sources"]:
            self.assertEqual(s["status"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
