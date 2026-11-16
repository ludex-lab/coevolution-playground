"""unittest suite for w25-series-title-lint (stdlib only; run: python3 -B -m unittest)."""

import ast
import copy
import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

import demo
import lint_titles as lt

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "fixtures", "catalog.json")
LIVE = os.path.join(HERE, "fixtures", "live_titles.tsv")

DEMO_STDOUT_SHA256 = "b58c1e167e4223b5959347c40969eadeb5c61bcffa2fe2d3f7e3051d01670973"
LIVE_FIXTURE_SHA256 = "93466a04d89b6d9b9177c9a32499831f38395a62c7f7efe5daec101dc8bcc7d3"
CATALOG_SHA256 = "6fcf4c62d659e631807f171ddde6364c95a646b0d42f4f46f36dd920746ead8e"

# Live drift observed on @LudexVillage (Wave25 VERDICT section 2c), as linted with fixtures/catalog.json.
LIVE_EXPECTED = [
    ("WARN", "number_gap", "", "documentary", None, "missing 1", "1..7 contiguous"),
    ("FAIL", "label_drift", "OI7T4YiBjvQ", "documentary", 7, "Ludex Village Doc 07", "Ludex Village Documentary 07"),
    ("FAIL", "spacing_drift", "5PmEeWP2i6I", "weekly", 6, "Ludex Weekly06", "Ludex Weekly 06"),
    ("FAIL", "spacing_drift", "2PNq9HAiHtQ", "weekly", 5, "Ludex Weekly05", "Ludex Weekly 05"),
    ("INFO", "retired_alias", "HsNupqme-Is", "weekly", 2, "Ludex Daily Weekly 02", "Ludex Weekly 02"),
    ("INFO", "retired_alias", "G7ZfTlY4bmY", "weekly", 1, "Naru Daily Weekly 01", "Ludex Weekly 01"),
    ("FAIL", "number_format_drift", "cFAe8QRvvL8", "documentary", 2, "Ludex Village Documentary \u00b7 Ep. 2", "Ludex Village Documentary 02"),
]
# Live rows that mention no declared series: listed as INFO unmatched_title (r2), in line order.
LIVE_UNMATCHED = [
    (7, "Rcjuf2oD7Lo"), (10, "ul-SOEF7CRQ"), (11, "--rKxmXZ7Bg"), (14, "4wJmyvFnX-o"),
    (18, "--pWy5YFitc"), (19, "MaIpArLQjEI"), (22, "fSDFurX5fAQ"), (26, "kfcF8d8satg"),
    (27, "ymAxGuLj-zE"), (28, "Ka-uhyudZes"), (32, "Z2T9DktKzNA"), (33, "sw2scAPEBSU"),
]


def drift(report):
    return [key(f) for f in report["findings"] if f["code"] != "unmatched_title"]


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_catalog_obj():
    with open(CATALOG, encoding="utf-8") as fh:
        return json.load(fh)


def snap(obj=None):
    return lt.validate_catalog(load_catalog_obj() if obj is None else obj)


def lint_lines(lines, obj=None, tsv=False):
    s = snap(obj)
    text = ("ref\tlang\ttitle\n" if tsv else "") + "\n".join(lines) + "\n"
    return lt.lint(s, lt.parse_titles_text(text, s[0]))


def key(f):
    return (f["severity"], f["code"], f["ref"], f["series"], f["number"], f["found"], f["expected"])


def codes(report, severity=None):
    return [f["code"] for f in report["findings"] if severity is None or f["severity"] == severity]


class Files(object):
    def __init__(self):
        self._td = tempfile.TemporaryDirectory()
        self.dir = self._td.name

    def write(self, name, data):
        path = os.path.join(self.dir, name)
        mode = "wb" if isinstance(data, bytes) else "w"
        kw = {} if isinstance(data, bytes) else {"encoding": "utf-8"}
        with open(path, mode, **kw) as fh:
            fh.write(data)
        return path

    def close(self):
        self._td.cleanup()


def call_main(argv):
    out, err = io.StringIO(), io.StringIO()

    class Buf(io.BytesIO):
        pass

    buf = Buf()

    class Wrapper(object):
        buffer = buf

        def write(self, s):
            out.write(s)

        def flush(self):
            pass

    with redirect_stdout(Wrapper()), redirect_stderr(err):
        code = lt.main(argv)
    return code, buf.getvalue().decode("utf-8")


class LiveFixtureTests(unittest.TestCase):
    def test_fixture_hashes_pinned(self):
        self.assertEqual(sha256_file(LIVE), LIVE_FIXTURE_SHA256)
        self.assertEqual(sha256_file(CATALOG), CATALOG_SHA256)

    def test_verdict_quotes_present_verbatim(self):
        with open(LIVE, encoding="utf-8") as fh:
            text = fh.read()
        for q in ("Ludex Weekly 07", "Ludex Weekly06", "Ludex Weekly05", "Ludex Weekly 04",
                  "Ludex Weekly 03", "Ludex Daily Weekly 02", "Naru Daily Weekly 01",
                  "Ludex Village Doc 07", "Ludex Village Documentary 06",
                  "Ludex Village Documentary 05", "\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050 4\ud654",
                  "\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050 3\ud654",
                  "Ludex Village Documentary \u00b7 Ep. 2", "Ludex Village OST 04 \u00b7 Instrumental",
                  "\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 OST 03", "A Little Room to Rest \u00b7 Ludex Village OST 02",
                  "Ludex Village OST 01", "Luma & Ieum", "Luma\uc640 \uc774\uc74c"):
            self.assertIn(q, text)

    def test_live_report_exact(self):
        report = lt.run(LIVE, CATALOG)
        self.assertEqual(report["decision"], "FAIL")
        self.assertEqual(report["on_expiry"], "DENY")
        self.assertEqual((report["titles"], report["matched"], report["unmatched"]), (29, 17, 12))
        self.assertEqual(report["counts"], {"FAIL": 4, "WARN": 1, "INFO": 14})
        self.assertEqual(drift(report), LIVE_EXPECTED)
        um = [f for f in report["findings"] if f["code"] == "unmatched_title"]
        self.assertEqual([(f["line"], f["ref"]) for f in um], LIVE_UNMATCHED)
        self.assertTrue(all(f["severity"] == "INFO" and f["found"] == f["title"] for f in um))
        self.assertEqual(report["series"], {"documentary": [2, 3, 4, 5, 6, 7], "ost": [1, 2, 3, 4],
                                            "weekly": [1, 2, 3, 4, 5, 6, 7]})

    def test_live_lines(self):
        report = lt.run(LIVE, CATALOG)
        lines = [f["line"] for f in report["findings"] if f["code"] != "unmatched_title"]
        self.assertEqual(lines, [0, 8, 9, 13, 25, 29, 31])

    def test_live_names_clean(self):
        report = lt.run(LIVE, CATALOG)
        self.assertFalse([c for c in codes(report) if c.startswith("name")])

    def test_live_cli_exit_and_json(self):
        f = Files()
        try:
            out = os.path.join(f.dir, "report.json")
            code, _ = call_main([LIVE, CATALOG, "--out", out, "--format", "json"])
            self.assertEqual(code, 1)
            with open(out, encoding="utf-8") as fh:
                rep = json.load(fh)
            self.assertEqual(rep["decision"], "FAIL")
            self.assertEqual(len(rep["findings"]), 19)
        finally:
            f.close()


class SeriesRuleTests(unittest.TestCase):
    def test_canonical_passes(self):
        r = lint_lines(["Ludex Weekly %02d" % n for n in range(3, 8)] +
                       ["Naru Daily Weekly 01", "Ludex Daily Weekly 02"])
        self.assertEqual(r["decision"], "PASS")
        self.assertEqual(codes(r), ["retired_alias", "retired_alias"])

    def test_single_canonical_title(self):
        r = lint_lines(["Same Answer, Different Process | \uac19\uc740 \uc815\ub2f5, \ub2e4\ub978 \uacfc\uc815 \u00b7 Ludex Weekly 07"])
        self.assertEqual(codes(r, "FAIL"), [])
        self.assertEqual(r["decision"], "PASS")

    def test_retired_alias_is_info_not_drift(self):
        r = lint_lines(["What Counts as Progress? | Naru Daily Weekly 01"])
        self.assertEqual([key(f) for f in r["findings"] if f["code"] != "number_gap"],
                         [("INFO", "retired_alias", "", "weekly", 1, "Naru Daily Weekly 01", "Ludex Weekly 01")])
        self.assertEqual(r["decision"], "PASS")
        r = lint_lines(["What Survives the Next Step? | Ludex Daily Weekly 02"])
        self.assertEqual(codes(r, "INFO"), ["retired_alias"])
        self.assertEqual(codes(r, "FAIL"), [])

    def test_retired_alias_out_of_era(self):
        for title, number in (("Naru Daily Weekly 02", 2), ("Ludex Daily Weekly 03", 3),
                              ("Ludex Daily Weekly 01", 1), ("Naru Daily Weekly 08", 8)):
            r = lint_lines([title])
            self.assertEqual(codes(r, "FAIL"), ["retired_alias_out_of_era"], title)
            f = [x for x in r["findings"] if x["severity"] == "FAIL"][0]
            self.assertEqual(f["expected"], "Ludex Weekly %02d" % number)
            self.assertEqual(r["decision"], "FAIL")

    def test_retired_alias_spacing(self):
        r = lint_lines(["Naru Daily Weekly01"])
        self.assertEqual(codes(r, "FAIL"), ["spacing_drift"])
        self.assertEqual(r["findings"][0]["expected"], "Naru Daily Weekly 01")

    def test_retired_alias_case(self):
        r = lint_lines(["naru daily weekly 01"])
        self.assertEqual(codes(r, "FAIL"), ["case_drift"])

    def test_spacing_case_pad(self):
        self.assertEqual(codes(lint_lines(["Ludex Weekly06"]), "FAIL"), ["spacing_drift"])
        self.assertEqual(codes(lint_lines(["Ludex  Weekly 06"]), "FAIL"), ["spacing_drift"])
        self.assertEqual(codes(lint_lines(["LudexWeekly 06"]), "FAIL"), ["spacing_drift"])
        self.assertEqual(codes(lint_lines(["ludex weekly 06"]), "FAIL"), ["case_drift"])
        self.assertEqual(codes(lint_lines(["Ludex Weekly 6"]), "FAIL"), ["number_format_drift"])
        self.assertEqual(codes(lint_lines(["Ludex Weekly 006"]), "FAIL"), ["number_format_drift"])

    def test_documentary_label_drift(self):
        r = lint_lines(["A Small Internet: Who Gets to Speak? | Ludex Village Documentary 06",
                        "What Quiet Means \u00b7 Ludex Village Doc 07"])
        self.assertEqual([key(f) for f in r["findings"] if f["severity"] == "FAIL"],
                         [("FAIL", "label_drift", "", "documentary", 7, "Ludex Village Doc 07",
                           "Ludex Village Documentary 07")])

    def test_variant_expected_follows_row_lang(self):
        r = lint_lines(["x\tko\tLudex Village Doc 07"], tsv=True)
        f = [x for x in r["findings"] if x["code"] == "label_drift"][0]
        self.assertEqual(f["expected"], "\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050 7\ud654")

    def test_ep_format_drift(self):
        r = lint_lines(["A Hand Across the River | Ludex Village Documentary \u00b7 Ep. 2"])
        fails = [f for f in r["findings"] if f["severity"] == "FAIL"]
        self.assertEqual([(f["code"], f["number"]) for f in fails], [("number_format_drift", 2)])

    def test_per_language_label_ok(self):
        r = lint_lines(["a\tko\t\ub2e4\uc2dc \ub3cc\uc544\uc62c \uc790\ub9ac\ub97c \ub9cc\ub4dc\ub294 \uc77c | \ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050 4\ud654",
                        "b\tko\t\ubcf4\ub85c | \ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050 3\ud654",
                        "c\tko\t\uc120\uc744 \ub530\ub77c | \ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 OST 03",
                        "d\tko\t\uc5d0\uc774\uc804\ud2b8 | Ludex Weekly 03",
                        "e\ten\tThe Village Begins to Move | Ludex Village Documentary 05"], tsv=True)
        self.assertEqual(codes(r, "FAIL"), [])
        self.assertEqual(r["decision"], "PASS")

    def test_per_language_label_inferred_without_lang(self):
        r = lint_lines(["\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050 4\ud654", "Ludex Village Documentary 05"])
        self.assertEqual(codes(r, "FAIL"), [])

    def test_wrong_language_label(self):
        r = lint_lines(["a\ten\t\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050 4\ud654"], tsv=True)
        self.assertEqual([key(f) for f in r["findings"] if f["severity"] == "FAIL"],
                         [("FAIL", "language_label", "a", "documentary", 4,
                           "\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050 4\ud654", "Ludex Village Documentary 04")])
        r = lint_lines(["b\tko\tLudex Village Documentary 04"], tsv=True)
        f = [x for x in r["findings"] if x["severity"] == "FAIL"]
        self.assertEqual([(x["code"], x["expected"]) for x in f],
                         [("language_label", "\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050 4\ud654")])

    def test_korean_number_format(self):
        self.assertEqual(codes(lint_lines(["\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050 04\ud654"]), "FAIL"),
                         ["number_format_drift"])
        self.assertEqual(codes(lint_lines(["\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050 4"]), "FAIL"),
                         ["number_format_drift"])
        self.assertEqual(codes(lint_lines(["\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud0504\ud654"]), "FAIL"),
                         ["spacing_drift"])

    def test_unmatched_titles(self):
        r = lint_lines(["A Door That Actually Opens | Building Ludex Village",
                        "\uc601\uc0c1 \uc18d \uce74\ud398 | \ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 3D \uacf5\ubc29",
                        "XYLudex Weekly 07", "Ludex Village Maker Film"])
        self.assertEqual((r["matched"], r["unmatched"]), (0, 4))
        self.assertEqual([(f["severity"], f["code"], f["line"]) for f in r["findings"]],
                         [("INFO", "unmatched_title", n, ) for n in (1, 2, 3, 4)])
        self.assertEqual(r["decision"], "PASS")

    def test_two_series_in_one_title(self):
        r = lint_lines(["Ludex Weekly 07 \u00b7 Ludex Village OST 04"])
        self.assertEqual(r["series"]["weekly"], [7])
        self.assertEqual(r["series"]["ost"], [4])
        self.assertEqual(r["matched"], 1)

    def test_duplicate_number_fails(self):
        r = lint_lines(["Ludex Weekly 05", "Ludex Weekly 06", "Ludex Weekly 05"])
        dup = [f for f in r["findings"] if f["code"] == "duplicate_number"]
        self.assertEqual([(d["severity"], d["number"], d["line"], d["found"]) for d in dup],
                         [("FAIL", 5, 3, "lines 1,3")])
        self.assertEqual(r["decision"], "FAIL")

    def test_gap_is_warn_and_does_not_fail(self):
        r = lint_lines(["Ludex Weekly 03", "Ludex Weekly 05"])
        gaps = [(f["severity"], f["series"], f["found"], f["expected"]) for f in r["findings"]]
        self.assertEqual(gaps, [("WARN", "weekly", "missing 1,2,4", "1..5 contiguous")])
        self.assertEqual(r["decision"], "PASS")

    def test_first_number_respected(self):
        obj = load_catalog_obj()
        obj["series"][0]["first"] = 3
        obj["series"][0]["retired"] = []
        r = lint_lines(["Ludex Weekly 03", "Ludex Weekly 05"], obj)
        self.assertEqual([f["found"] for f in r["findings"]], ["missing 4"])

    def test_names(self):
        r = lint_lines(["Leave a Little Light | Luma & Ieum \u00b7 Ludex Village Music Video",
                        "\ub9c8\uc744 | Luma\uc640 \uc774\uc74c\uc758 \uc81c\uc791 \uc774\uc57c\uae30"])
        self.assertEqual(codes(r), ["unmatched_title", "unmatched_title"])
        r = lint_lines(["Two Voices | luma & Ieum"])
        self.assertEqual([(f["code"], f["found"], f["expected"]) for f in r["findings"] if f["code"] != "unmatched_title"],
                         [("name_case_drift", "luma", "Luma")])
        obj = load_catalog_obj()
        obj["names"][4]["variants"] = [{"label": "Ieom", "lang": "en"}, {"label": "\uc774\uc6c0", "lang": "ko"}]
        r = lint_lines(["a\tko\tLuma & Ieom", "b\ten\t\uc774\uc6c0 \uc774\uc57c\uae30", "c\ten\tIeomy",
                        "d\tko\t\ubc14\uc774\uc6c0 \uc774\uc57c\uae30"], obj, tsv=True)
        self.assertEqual([(f["code"], f["ref"], f["found"], f["expected"]) for f in r["findings"] if f["code"] != "unmatched_title"],
                         [("name_drift", "a", "Ieom", "\uc774\uc74c"), ("name_drift", "b", "\uc774\uc6c0", "Ieum")])
        self.assertEqual(r["decision"], "FAIL")

    def test_names_table_optional(self):
        obj = load_catalog_obj()
        del obj["names"]
        r = lint_lines(["luma & ieum | Ludex Weekly 03"], obj)
        self.assertEqual(codes(r), ["number_gap"])

    def test_retired_declaration_turns_ep_format_into_info(self):
        obj = load_catalog_obj()
        obj["series"][1]["retired"] = [{"label": "Ludex Village Documentary \u00b7 Ep.", "last": 2, "pad": 0}]
        r = lint_lines(["A Hand Across the River | Ludex Village Documentary \u00b7 Ep. 2",
                        "Ludex Village Documentary \u00b7 Ep. 3", "Ludex Village Documentary 01"], obj)
        self.assertEqual([(f["severity"], f["code"], f["number"], f["expected"]) for f in r["findings"]],
                         [("INFO", "retired_alias", 2, "Ludex Village Documentary 02"),
                          ("FAIL", "retired_alias_out_of_era", 3, "Ludex Village Documentary 03")])
        obj["series"][1]["retired"] = [{"label": "Ludex Village \u00b7 Documentary", "last": 2, "pad": 0}]
        with self.assertRaises(lt.InputError):
            lt.validate_catalog(obj)  # normalizes equal to the canonical label: refused

    def test_render(self):
        self.assertEqual(lt.render("Ludex Weekly", 6, 2, ""), "Ludex Weekly 06")
        self.assertEqual(lt.render("\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050", 4, 0, "\ud654"),
                         "\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050 4\ud654")
        self.assertEqual(lt.render("L", 123, 2, ""), "L 123")


class DenyTests(unittest.TestCase):
    def setUp(self):
        self.f = Files()

    def tearDown(self):
        self.f.close()

    def assertDeny(self, titles, catalog, reason):
        rep = lt.run(titles, catalog)
        self.assertEqual(rep["decision"], "DENY")
        self.assertEqual(rep["on_expiry"], "DENY")
        self.assertEqual(rep["reason"], reason)
        self.assertNotIn("findings", rep)
        code, text = call_main([titles, catalog])
        self.assertEqual(code, 2)
        self.assertNotEqual(code, 0)
        self.assertTrue(text.startswith("w25-series-title-lint decision=DENY on_expiry=DENY\n"))
        self.assertNotIn("PASS", text)
        return rep

    def test_missing_titles(self):
        self.assertDeny(os.path.join(self.f.dir, "nope.tsv"), CATALOG, "titles_missing")

    def test_missing_catalog(self):
        self.assertDeny(LIVE, os.path.join(self.f.dir, "nope.json"), "catalog_missing")

    def test_unreadable_titles_directory(self):
        self.assertDeny(self.f.dir, CATALOG, "titles_unreadable")

    def test_unreadable_catalog_directory(self):
        self.assertDeny(LIVE, self.f.dir, "catalog_unreadable")

    def test_unreadable_non_utf8(self):
        p = self.f.write("bad.txt", b"Ludex Weekly 07\n\xff\xfe\n")
        self.assertDeny(p, CATALOG, "titles_unreadable")
        c = self.f.write("bad.json", b"\xff{}")
        self.assertDeny(LIVE, c, "catalog_unreadable")

    def test_malformed_catalog_json(self):
        self.assertDeny(LIVE, self.f.write("c.json", "{not json"), "catalog_malformed")
        self.assertDeny(LIVE, self.f.write("c2.json", '{"a": NaN}'), "catalog_malformed")

    def test_config_error_catalog(self):
        self.assertDeny(LIVE, self.f.write("c.json", '{"schema": "x", "languages": ["en"], "series": []}'),
                        "config_error")

    def test_empty_titles(self):
        self.assertDeny(self.f.write("t.txt", "\n  \n\n"), CATALOG, "titles_empty")
        self.assertDeny(self.f.write("t3.tsv", "# only a comment\nref\tlang\ttitle\n\n"), CATALOG, "titles_empty")
        self.assertDeny(self.f.write("t2.tsv", "ref\tlang\ttitle\n"), CATALOG, "titles_empty")

    def test_malformed_titles(self):
        self.assertDeny(self.f.write("a.tsv", "ref\tlang\ttitle\nx\ten\n"), CATALOG, "titles_malformed")
        self.assertDeny(self.f.write("b.tsv", "ref\tlang\ttitle\nx\tfr\tLudex Weekly 07\n"), CATALOG, "titles_malformed")
        self.assertDeny(self.f.write("c.txt", "Ludex Weekly 07\nfoo\tbar\n"), CATALOG, "titles_malformed")
        self.assertDeny(self.f.write("d.tsv", "ref\tlang\ttitle\nx\ten\t  \n"), CATALOG, "titles_malformed")
        self.assertDeny(self.f.write("e.tsv", "ref\tlang\ttitle\nx\ten\tA\tB\n"), CATALOG, "titles_malformed")

    def test_usage_is_deny(self):
        for argv in ([], [LIVE], [LIVE, CATALOG, "extra"], [LIVE, CATALOG, "--bogus"],
                     [LIVE, CATALOG, "--format"], [LIVE, CATALOG, "--format", "xml"]):
            code, text = call_main(argv)
            self.assertEqual(code, 2, argv)
            self.assertIn("decision=DENY", text)

    def test_unwritable_out_is_nonzero(self):
        code, _ = call_main([LIVE, CATALOG, "--out", self.f.dir])
        self.assertEqual(code, 2)

    def test_out_file_written_for_deny(self):
        out = os.path.join(self.f.dir, "r.txt")
        code, _ = call_main([os.path.join(self.f.dir, "nope"), CATALOG, "--out", out])
        self.assertEqual(code, 2)
        with open(out, encoding="utf-8") as fh:
            self.assertIn("decision=DENY", fh.read())

    def test_pass_exit_zero(self):
        p = self.f.write("ok.txt", "Ludex Weekly 01\nLudex Weekly 02\n")
        code, text = call_main([p, CATALOG])
        self.assertEqual(code, 0)
        self.assertIn("decision=PASS", text)

    def test_bom_and_crlf(self):
        p = self.f.write("bom.tsv", "\ufeffref\tlang\ttitle\r\nx\ten\tLudex Weekly 01\r\n")
        rep = lt.run(p, CATALOG)
        self.assertEqual(rep["decision"], "PASS")
        self.assertEqual(rep["titles"], 1)

    def test_non_str_text_inputs(self):
        with self.assertRaises(lt.InputError):
            lt.parse_titles_text(b"x", ("en",))
        with self.assertRaises(lt.InputError):
            lt.parse_catalog_text(b"{}")
        self.assertEqual(lt.run(None, CATALOG)["reason"], "titles_missing")
        self.assertEqual(lt.run(LIVE, "")["reason"], "catalog_missing")


class StrSub(str):
    pass


class DictSub(dict):
    pass


class IntSub(int):
    pass


class CatalogValidationTests(unittest.TestCase):
    def bad(self, mutate, reason="config_error"):
        obj = load_catalog_obj()
        mutate(obj)
        with self.assertRaises(lt.InputError) as cm:
            lt.validate_catalog(obj)
        self.assertEqual(cm.exception.reason, reason)

    def test_valid(self):
        langs, series, names = snap()
        self.assertEqual(langs, ("en", "ko"))
        self.assertEqual([s[0] for s in series], ["weekly", "documentary", "ost"])
        self.assertEqual(len(names), 8)

    def test_str_subclass_key(self):
        def m(o):
            o[StrSub("schema")] = o.pop("schema")
        self.bad(m)

        def m2(o):
            lab = o["series"][0]["labels"]
            lab[StrSub("en")] = lab.pop("en")
        self.bad(m2)

    def test_str_subclass_values(self):
        self.bad(lambda o: o["series"][0]["labels"]["en"].__setitem__("label", StrSub("Ludex Weekly")))
        self.bad(lambda o: o["series"][0].__setitem__("key", StrSub("weekly")))
        self.bad(lambda o: o.__setitem__("languages", ["en", StrSub("ko")]))
        self.bad(lambda o: o["names"][0]["labels"].__setitem__("en", StrSub("Nella")))
        self.bad(lambda o: o["series"][0]["labels"]["en"].__setitem__("suffix", StrSub("")))

    def test_dict_subclasses(self):
        self.bad(lambda o: o["series"].__setitem__(0, DictSub(o["series"][0])))
        self.bad(lambda o: o["series"][0].__setitem__("labels", DictSub(o["series"][0]["labels"])))
        self.bad(lambda o: o["series"][0]["labels"].__setitem__("en", DictSub(o["series"][0]["labels"]["en"])))
        self.bad(lambda o: o["series"][0]["retired"].__setitem__(0, DictSub(o["series"][0]["retired"][0])))
        self.bad(lambda o: o["names"].__setitem__(0, DictSub(o["names"][0])))
        obj = DictSub(load_catalog_obj())
        with self.assertRaises(lt.InputError):
            lt.validate_catalog(obj)

    def test_bad_numbers(self):
        for v in (True, False, 2.0, float("nan"), float("inf"), -1, 5, IntSub(2), "2", None):
            self.bad(lambda o, v=v: o["series"][0]["labels"]["en"].__setitem__("pad", v))
        for v in (True, 1.0, float("nan"), float("-inf"), IntSub(1)):
            self.bad(lambda o, v=v: o["series"][0].__setitem__("first", v))
            self.bad(lambda o, v=v: o["series"][0]["retired"][0].__setitem__("last", v))

    def test_json_non_finite_and_dupes(self):
        with open(CATALOG, encoding="utf-8") as fh:
            text = fh.read()
        for bad in ('"pad": NaN', '"pad": Infinity', '"pad": -Infinity'):
            with self.assertRaises(lt.InputError) as cm:
                lt.parse_catalog_text(text.replace('"pad": 2', bad, 1))
            self.assertEqual(cm.exception.reason, "catalog_malformed")
        for bad in ('"pad": 1e400', '"pad": 2.0', '"pad": true'):
            with self.assertRaises(lt.InputError) as cm:
                lt.parse_catalog_text(text.replace('"pad": 2', bad, 1))
            self.assertEqual(cm.exception.reason, "config_error")
        with self.assertRaises(lt.InputError) as cm:
            lt.parse_catalog_text(text.replace('"first": 1,', '"first": 1, "first": 1,', 1))
        self.assertEqual(cm.exception.reason, "catalog_malformed")

    def test_structure_errors(self):
        self.bad(lambda o: o.__setitem__("schema", "other"))
        self.bad(lambda o: o.__setitem__("extra", 1))
        self.bad(lambda o: o.pop("series"))
        self.bad(lambda o: o.__setitem__("series", []))
        self.bad(lambda o: o.__setitem__("series", ()))
        self.bad(lambda o: o.__setitem__("languages", ["en", "en"]))
        self.bad(lambda o: o.__setitem__("languages", ["EN", "ko"]))
        self.bad(lambda o: o.__setitem__("languages", []))
        self.bad(lambda o: o["series"][0]["labels"].pop("ko"))
        self.bad(lambda o: o["series"][0]["labels"].__setitem__("fr", o["series"][0]["labels"]["en"]))
        self.bad(lambda o: o["series"][1].__setitem__("key", "weekly"))
        self.bad(lambda o: o["series"][1].__setitem__("key", "Doc"))
        self.bad(lambda o: o["series"][0]["labels"]["en"].__setitem__("label", "   "))
        self.bad(lambda o: o["series"][0]["labels"]["en"].__setitem__("label", ""))
        self.bad(lambda o: o["series"][0]["retired"][0].__setitem__("label", ""))
        self.bad(lambda o: o["names"][0]["labels"].__setitem__("en", ""))
        self.bad(lambda o: o.__setitem__("languages", ["en", "ko", "ko"]))
        self.bad(lambda o: o["series"][0]["labels"]["en"].__setitem__("label", " Ludex Weekly"))
        self.bad(lambda o: o["series"][0]["labels"]["en"].__setitem__("label", "Ludex Weekly 2"))
        self.bad(lambda o: o["series"][0]["labels"]["en"].__setitem__("label", "Ludex\tWeekly"))
        self.bad(lambda o: o["series"][0]["labels"]["en"].__setitem__("label", "\u00b7 . -"))
        self.bad(lambda o: o["series"][0]["labels"]["en"].__setitem__("suffix", " x"))
        self.bad(lambda o: o["series"][0]["labels"]["en"].__setitem__("suffix", "x1"))
        self.bad(lambda o: o["series"][0]["labels"]["en"].pop("suffix"))

    def test_language_code_shape(self):
        with open(CATALOG, encoding="utf-8") as fh:
            text = fh.read()
        for code in ("KO", "kor", "k1"):
            with self.assertRaises(lt.InputError) as cm:
                lt.parse_catalog_text(text.replace('"ko"', '"%s"' % code))
            self.assertEqual(cm.exception.reason, "config_error")

    def test_collisions_and_order(self):
        self.bad(lambda o: o["series"][2]["labels"]["en"].__setitem__("label", "ludex  weekly"))
        self.bad(lambda o: o["series"][0]["retired"][1].__setitem__("last", 1))
        self.bad(lambda o: o["series"][0]["retired"][0].__setitem__("last", 0))
        self.bad(lambda o: o["series"][0]["retired"][0].__setitem__("label", "Ludex Weekly"))
        self.bad(lambda o: o["series"][1]["variants"][0].__setitem__("label", "Ludex Village Documentary"))
        self.bad(lambda o: o["series"][1]["variants"][0].__setitem__("label", "Ludex Village OST"))
        self.bad(lambda o: o["series"][1]["variants"][0].__setitem__("lang", "fr"))
        self.bad(lambda o: o["series"][1]["variants"][0].__setitem__("lang", StrSub("en")))
        self.bad(lambda o: o["names"][1]["labels"].__setitem__("en", "nella"))
        self.bad(lambda o: o["names"][1].__setitem__("key", "nella"))
        self.bad(lambda o: o["names"][0].__setitem__("labels", {}))
        self.bad(lambda o: o["names"][0].__setitem__("variants", [{"label": "Nela", "lang": "ko"}]))
        self.bad(lambda o: o["names"][0].__setitem__("variants", [{"label": "Milo", "lang": "en"}]))
        self.bad(lambda o: o["names"][1].__setitem__("variants", [{"label": "Nella", "lang": "en"}]))

    def test_snapshot_is_immutable_and_detached(self):
        obj = load_catalog_obj()
        s = lt.validate_catalog(obj)

        def walk(x):
            self.assertNotIsInstance(x, (list, dict))
            if isinstance(x, tuple):
                for y in x:
                    walk(y)
        walk(s)
        with open(LIVE, encoding="utf-8") as fh:
            rows = lt.parse_titles_text(fh.read(), s[0])
        before = lt.lint(s, rows)
        obj["series"][0]["labels"]["en"]["label"] = "Something Else"
        obj["series"][0]["retired"].clear()
        obj["languages"].append("fr")
        after = lt.lint(s, rows)
        self.assertEqual(before, after)
        self.assertEqual(drift(after), LIVE_EXPECTED)

    def test_deterministic(self):
        a = lt.format_json(lt.run(LIVE, CATALOG))
        b = lt.format_json(lt.run(LIVE, CATALOG))
        self.assertEqual(a, b)
        self.assertEqual(json.loads(a)["decision"], "FAIL")


# r2 (review verdict sha256 afae228e...): the 27 decorated, unparseable or invisible-character
# variants of a declared label from the verdict's probe P1, one row each (lang ko for the
# documentary 다큐 rows, else en).  None may PASS.
KO_DOC = "\ub8e8\ub371\uc2a4 \ube4c\ub9ac\uc9c0 \ub2e4\ud050"
VERDICT_VARIANTS = [
    ("hash #08", "X | Ludex Weekly #08", "label_without_number"),
    ("No. 8", "X | Ludex Weekly No. 8", "label_without_number"),
    ("Episode 8", "X | Ludex Weekly Episode 8", "label_without_number"),
    ("colon 08", "X | Ludex Weekly: 08", "label_without_number"),
    ("em dash 08", "X | Ludex Weekly \u2014 08", "label_without_number"),
    ("paren (08)", "X | Ludex Weekly (08)", "label_without_number"),
    ("Vol. 8", "X | Ludex Weekly Vol. 8", "label_without_number"),
    ("E08", "X | Ludex Weekly E08", "label_without_number"),
    ("circled 8", "X | Ludex Weekly \u2467", "unicode_drift"),
    ("fullwidth 08", "X | Ludex Weekly \uff10\uff18", "unicode_drift"),
    ("arabic-indic 08", "X | Ludex Weekly \u0660\u0668", "unicode_drift"),
    ("ZWSP in gap", "X | Ludex Weekly\u200b08", "unicode_drift"),
    ("ZWSP in label", "X | Ludex\u200bWeekly 08", "unicode_drift"),
    ("ZWJ in label", "X | Lu\u200ddex Weekly 08", "unicode_drift"),
    ("soft hyphen in label", "X | Lu\u00addex Weekly 08", "unicode_drift"),
    ("NBSP in label", "X | Ludex\u00a0Weekly 08", "spacing_drift"),
    ("fullwidth space", "X | Ludex\u3000Weekly 08", "spacing_drift"),
    ("Cyrillic e lookalike", "X | Lud\u0435x Weekly 08", "label_near_miss"),
    ("fullwidth letters", "X | \uff2cudex Weekly 08", "unicode_drift"),
    ("misspelt Weekley", "X | Ludex Weekley 08", "label_near_miss"),
    ("label no number", "X | Ludex Weekly Special", "label_without_number"),
    ("KO je-8-hwa", "X | " + KO_DOC + " \uc81c8\ud654", "label_without_number"),
    ("KO documentary long form", "X | " + KO_DOC + "\uba58\ud130\ub9ac 8\ud654", "label_without_number"),
    ("KO 8 hwa with space", "X | " + KO_DOC + " 8 \ud654", "number_format_drift"),
    ("KO 08hwa", "X | " + KO_DOC + " 08\ud654", "number_format_drift"),
    ("Doc #7", "X | Ludex Village Doc #7", "label_without_number"),
    ("Documentary: Ep 8", "X | Ludex Village Documentary: Ep 8", "label_without_number"),
]


def lint_one(title, lang=None):
    if lang is None:
        lang = "ko" if KO_DOC in title else "en"
    return lint_lines(["r\t%s\t%s" % (lang, title)], tsv=True)


def fails(report):
    return [(f["code"], f["found"], f["expected"]) for f in report["findings"] if f["severity"] == "FAIL"]


class R2DecoratedNumberTests(unittest.TestCase):
    def test_all_27_verdict_variants_fail(self):
        self.assertEqual(len(VERDICT_VARIANTS), 27)
        passed = [name for name, title, _code in VERDICT_VARIANTS if lint_one(title)["decision"] == "PASS"]
        self.assertEqual(passed, [])

    def test_variant_codes(self):
        for name, title, code in VERDICT_VARIANTS:
            r = lint_one(title)
            self.assertEqual(r["decision"], "FAIL", name)
            self.assertEqual([c for c, _f, _e in fails(r)], [code], name)
            self.assertNotIn("unmatched_title", codes(r), name)

    def test_cli_hash_number_exit_1(self):
        f = Files()
        try:
            code, text = call_main([f.write("t.txt", "ok | Ludex Weekly #02\n"), CATALOG])
            self.assertEqual(code, 1)
            self.assertIn("FAIL L1   label_without_number weekly found='Ludex Weekly #02' expected='Ludex Weekly <number>'\n", text)
        finally:
            f.close()

    def test_found_quotes_original_text(self):
        r = lint_one("X | Ludex\u200bWeekly 08")
        self.assertEqual(fails(r), [("unicode_drift", "Ludex\u200bWeekly 08", "Ludex Weekly 08")])
        self.assertEqual(r["series"]["weekly"], [8])
        r = lint_one("X | Ludex Weekly \uff10\uff18")
        self.assertEqual(fails(r), [("unicode_drift", "Ludex Weekly \uff10\uff18", "Ludex Weekly 08")])
        self.assertEqual(r["series"]["weekly"], [8])
        r = lint_one("X | Ludex Weekly \u0660\u0668 | tail")
        self.assertEqual(r["series"]["weekly"], [8])

    def test_unicode_drift_on_retired_alias(self):
        r = lint_lines(["Naru Daily\u200b Weekly 01"])
        self.assertEqual([c for c, _f, _e in fails(r)], ["unicode_drift"])
        self.assertEqual(fails(r)[0][2], "Naru Daily Weekly 01")

    def test_fold(self):
        text, folded, index, foreign = lt.fold("A\u200bB\uff10 \u00a0\u2467")
        self.assertEqual(text, "A\u200bB\uff10 \u00a0\u2467")
        self.assertEqual(folded, "AB0  8")
        self.assertEqual(index, (0, 2, 3, 4, 5, 6))
        self.assertEqual(foreign, frozenset({1, 3, 6}))
        text, folded, index, foreign = lt.fold("e\u0301")
        self.assertEqual((text, folded, index, foreign), ("\u00e9", "\u00e9", (0,), frozenset()))
        self.assertEqual(lt.fold("\ufb01x")[1:3], ("fix", (0, 0, 1)))

    def test_label_with_number_elsewhere(self):
        r = lint_lines(["Ludex Weekly recap | Ludex Weekly 07"])
        self.assertEqual([c for c, _f, _e in fails(r)], ["label_without_number"])
        self.assertEqual(fails(r)[0][1], "Ludex Weekly recap")
        self.assertEqual(r["series"]["weekly"], [7])
        self.assertEqual(r["matched"], 1)

    def test_label_without_number_expected_by_lang(self):
        r = lint_lines(["a\tko\tLudex Village Doc \ud2b9\uc9d1"], tsv=True)
        self.assertEqual(fails(r), [("label_without_number", "Ludex Village Doc \ud2b9\uc9d1",
                                     KO_DOC + " <number>\ud654")])
        r = lint_lines([KO_DOC + " \ud2b9\uc9d1"])
        self.assertEqual(fails(r)[0][2], KO_DOC + " <number>\ud654")
        r = lint_lines(["Naru Daily Weekly special"])
        self.assertEqual(fails(r), [("label_without_number", "Naru Daily Weekly special", "Ludex Weekly <number>")])

    def test_one_finding_per_overlapping_label(self):
        r = lint_lines(["Ludex Village Documentary: Ep 8"])
        self.assertEqual(fails(r), [("label_without_number", "Ludex Village Documentary: Ep 8",
                                     "Ludex Village Documentary <number>")])
        r = lint_lines(["Ludex Weekly A | Ludex Weekly B"])
        self.assertEqual([f[1] for f in fails(r)], ["Ludex Weekly A", "Ludex Weekly B"])
        r = lint_lines(["Ludex Weekly special edition"])
        self.assertEqual([f[1] for f in fails(r)], ["Ludex Weekly special"])

    def test_near_miss_edits(self):
        for t in ("Ludex Wekly 08", "Ludex Weeekly 08", "Ludex Weakly 08", "XLudex Weekly 07", "Ludex & Weekly 03"):
            self.assertEqual([c for c, _f, _e in fails(lint_lines([t]))], ["label_near_miss"], t)
        for t in ("Ludx Wekly 08", "Ludex Weekyl 08", "Ludex Village 08", "Ludex Daily 03"):
            r = lint_lines([t])
            self.assertEqual(codes(r), ["unmatched_title"], t)
        r = lint_lines(["Ludex Weekley 08"])
        self.assertEqual(r["findings"][0]["number"], None)
        self.assertEqual(r["series"]["weekly"], [])

    def test_edit_distance(self):
        d = lt._edit_distance_at_most_one
        self.assertEqual([d("abc", "abc"), d("abc", "abd"), d("abc", "ab"), d("ab", "abc"),
                          d("abc", "axc"), d("abc", "a"), d("abc", "bca"), d("abcd", "abdc"),
                          d("abc", "xabc"), d("abc", "abxc")],
                         [0, 1, 1, 1, 1, 2, 2, 2, 1, 1])

    def test_near_miss_needs_enough_letters(self):
        obj = load_catalog_obj()
        obj["series"].append({"key": "kit", "first": 1, "labels": {
            "en": {"label": "Kit Go", "pad": 2, "suffix": ""},
            "ko": {"label": "Kit Go", "pad": 2, "suffix": ""}}, "retired": [], "variants": []})
        r = lint_lines(["Kit Go 01", "Kip Go 02", "Kiit Go 03"], obj)
        self.assertEqual([(f["code"], f["line"]) for f in r["findings"]],
                         [("unmatched_title", 2), ("unmatched_title", 3)])
        obj["series"][3]["labels"]["en"]["label"] = "Kit Gox"
        obj["series"][3]["labels"]["ko"]["label"] = "Kit Gox"
        r = lint_lines(["Kip Gox 02"], obj)
        self.assertEqual(codes(r), ["label_near_miss"])

    def test_hangul_head_guard(self):
        r = lint_lines(["\uac00\ub098" + KO_DOC + " 4\ud654"])
        self.assertEqual(codes(r), ["unmatched_title"])
        self.assertEqual(r["series"]["documentary"], [])

    def test_number_too_long(self):
        r = lint_lines(["Ludex Weekly 1234567", "Ludex Weekly " + "9" * 5000, "Ludex Weekly 123456"])
        self.assertEqual([(f["code"], f["number"], f["expected"]) for f in r["findings"] if f["severity"] == "FAIL"],
                         [("number_format_drift", None, "a number of at most 6 digits")] * 2)
        self.assertEqual(r["series"]["weekly"], [123456])

    def test_gap_list_capped(self):
        r = lint_lines(["Ludex Weekly 100"])
        gap = [f for f in r["findings"] if f["code"] == "number_gap"][0]
        self.assertEqual(gap["found"], "missing " + ",".join(str(n) for n in range(1, 21)) + ",... (99 missing)")
        r = lint_lines(["Ludex Weekly 21"])
        gap = [f for f in r["findings"] if f["code"] == "number_gap"][0]
        self.assertEqual(gap["found"], "missing " + ",".join(str(n) for n in range(1, 21)))
        r = lint_lines(["Ludex Weekly 22"])
        gap = [f for f in r["findings"] if f["code"] == "number_gap"][0]
        self.assertTrue(gap["found"].endswith(",20,... (21 missing)"))


class R2CommentTests(unittest.TestCase):
    def setUp(self):
        self.f = Files()

    def tearDown(self):
        self.f.close()

    def test_plain_hash_line_is_a_title(self):
        path = self.f.write("p.txt", "#LudexVillage | Ludex Weekly06\nGood | Ludex Weekly 07\n")
        r = lt.run(path, CATALOG)
        self.assertEqual((r["decision"], r["titles"]), ("FAIL", 2))
        self.assertEqual([(f["code"], f["line"], f["found"]) for f in r["findings"] if f["severity"] == "FAIL"],
                         [("spacing_drift", 1, "Ludex Weekly06")])
        code, _ = call_main([path, CATALOG])
        self.assertEqual(code, 1)

    def test_plain_only_hash_titles(self):
        r = lt.run(self.f.write("p.txt", "#Shorts Ludex Weekly06\n"), CATALOG)
        self.assertEqual((r["decision"], r["titles"]), ("FAIL", 1))
        r = lt.run(self.f.write("q.txt", "# heading\nLudex Weekly 03\n"), CATALOG)
        self.assertEqual([(f["code"], f["line"]) for f in r["findings"] if f["code"] != "number_gap"],
                         [("unmatched_title", 1)])
        self.assertEqual(r["titles"], 2)

    def test_tsv_ref_starting_with_hash(self):
        path = self.f.write("t.tsv", "ref\tlang\ttitle\n#tag\ten\tLudex Weekly06\nx\ten\tLudex Weekly 07\n")
        r = lt.run(path, CATALOG)
        self.assertEqual((r["decision"], r["titles"]), ("FAIL", 2))
        self.assertEqual([(f["code"], f["ref"], f["line"]) for f in r["findings"] if f["severity"] == "FAIL"],
                         [("spacing_drift", "#tag", 2)])

    def test_tsv_comments_only_before_header(self):
        r = lt.run(self.f.write("t.tsv", "# note\n\n# more\nref\tlang\ttitle\nx\ten\tLudex Weekly 03\n"), CATALOG)
        self.assertEqual((r["decision"], r["titles"]), ("PASS", 1))
        self.assertEqual(r["findings"][0]["code"], "number_gap")
        r = lt.run(self.f.write("u.tsv", "ref\tlang\ttitle\n# note\nx\ten\tLudex Weekly 03\n"), CATALOG)
        self.assertEqual((r["decision"], r["reason"]), ("DENY", "titles_malformed"))
        r = lt.run(self.f.write("v.txt", "# note\nLudex Weekly 03\nref\tlang\ttitle\n"), CATALOG)
        self.assertEqual((r["decision"], r["reason"]), ("DENY", "titles_malformed"))

    def test_crlf_and_hash(self):
        r = lt.run(self.f.write("c.txt", b"#x Ludex Weekly06\r\nLudex Weekly 07\r\n"), CATALOG)
        self.assertEqual([f["found"] for f in r["findings"] if f["severity"] == "FAIL"], ["Ludex Weekly06"])


class R2LimitAndCatalogTests(unittest.TestCase):
    def test_deep_catalog_is_deny(self):
        f = Files()
        try:
            cat = f.write("deep.json", "[" * 100000 + "]" * 100000)
            titles = f.write("t.txt", "Ludex Weekly 03\n")
            rep = lt.run(titles, cat)
            self.assertEqual((rep["decision"], rep["reason"], rep["detail"]), ("DENY", "input_limit", "RecursionError"))
            code, text = call_main([titles, cat])
            self.assertEqual(code, 2)
            self.assertTrue(text.startswith("w25-series-title-lint decision=DENY on_expiry=DENY\n"))
        finally:
            f.close()

    def test_lint_value_error_is_deny(self):
        orig = lt.lint

        def boom(snapshot, rows):
            raise ValueError("x")
        lt.lint = boom
        try:
            rep = lt.run(LIVE, CATALOG)
        finally:
            lt.lint = orig
        self.assertEqual((rep["decision"], rep["reason"], rep["detail"]), ("DENY", "input_limit", "ValueError"))

    def bad(self, mutate):
        obj = load_catalog_obj()
        mutate(obj)
        with self.assertRaises(lt.InputError) as cm:
            lt.validate_catalog(obj)
        self.assertEqual(cm.exception.reason, "config_error")

    def test_invisible_or_unnormalised_labels_rejected(self):
        for lab in ("Ludex\u200bWeekly", "Lu\u00addex Weekly", "Lu\u200ddex Weekly", "\uff2cudex Weekly",
                    "Ludex\u00a0Weekly", "Ludex Weekly \u2467x"):
            self.bad(lambda o, lab=lab: o["series"][0]["labels"]["en"].__setitem__("label", lab))
            self.bad(lambda o, lab=lab: o["series"][0]["retired"][0].__setitem__("label", lab))
            self.bad(lambda o, lab=lab: o["series"][1]["variants"][0].__setitem__("label", lab))
        self.bad(lambda o: o["names"][0]["labels"].__setitem__("en", "Nel\u200bla"))

    def test_overlap_prefers_longest_span(self):
        obj = load_catalog_obj()
        obj["series"][0]["variants"] = [{"label": "Daily Weekly", "lang": "en"}]
        r = lint_lines(["Ludex Daily Weekly 02"], obj)
        self.assertEqual([f["code"] for f in r["findings"] if f["code"] != "number_gap"], ["retired_alias"])

    def test_empty_lang_in_tsv(self):
        r = lint_lines(["x\t\tLudex Weekly 03", "y\t\t" + KO_DOC + " 4\ud654"], tsv=True)
        self.assertEqual(codes(r, "FAIL"), [])
        self.assertEqual(r["decision"], "PASS")

    def test_first_bounds(self):
        for v in (-1, 10 ** 6 + 1):
            self.bad(lambda o, v=v: o["series"][0].__setitem__("first", v))
        obj = load_catalog_obj()
        obj["series"][0]["first"] = 10 ** 6
        obj["series"][0]["retired"] = []
        lt.validate_catalog(obj)

    def test_names_variants_required(self):
        self.bad(lambda o: o["names"][0].pop("variants"))


class DemoAndHygieneTests(unittest.TestCase):
    def test_demo_sha_pinned(self):
        text = demo.render()
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), DEMO_STDOUT_SHA256)
        self.assertTrue(text.startswith("w25-series-title-lint decision=FAIL on_expiry=DENY\n"))

    def test_demo_main_stdout(self):
        code, text = None, None
        buf = io.BytesIO()

        class W(object):
            buffer = buf

            def write(self, s):
                pass

            def flush(self):
                pass
        with redirect_stdout(W()):
            code = demo.main()
        self.assertEqual(code, 0)
        self.assertEqual(hashlib.sha256(buf.getvalue()).hexdigest(), DEMO_STDOUT_SHA256)

    def test_module_imports_stdlib_only(self):
        with open(os.path.join(HERE, "lint_titles.py"), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module)
        self.assertEqual(names, {"json", "os", "re", "sys", "unicodedata"})

    def test_text_format_lines(self):
        rep = lt.run(LIVE, CATALOG)
        text = lt.format_text(rep)
        self.assertIn("titles=29 matched=17 unmatched=12 FAIL=4 WARN=1 INFO=14\n", text)
        self.assertIn("INFO L33  unmatched_title  ref=sw2scAPEBSU found='Myoha: Two Tiny Rules | Behind the Workbench' expected='no declared series label'\n", text)
        self.assertIn("FAIL L9   spacing_drift weekly 6 ref=5PmEeWP2i6I found='Ludex Weekly06' expected='Ludex Weekly 06'\n", text)
        self.assertIn("WARN --   number_gap documentary found='missing 1' expected='1..7 contiguous'\n", text)
        self.assertTrue(text.endswith("series weekly numbers=1,2,3,4,5,6,7\n"))


if __name__ == "__main__":
    unittest.main()
