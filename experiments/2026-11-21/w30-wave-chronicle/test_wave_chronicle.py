"""Tests for wave_chronicle. Run: python3 -B -m unittest"""

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from contextlib import redirect_stderr, redirect_stdout

import wave_chronicle as wc

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
SNAPSHOT = os.path.join(FIX, "snapshot-f2fa1e5d")
TRACKS = os.path.join(FIX, "tracks.json")

# Git blob ids of the 13 day READMEs on main f2fa1e5d341f2f022d5b4a61d7563a6560db0212, as listed in the
# SHA-verified blob index this draft was built from. The snapshot copies must match these byte for byte.
PINNED = {
    "2026-11-09": ("8bbf7cd5ea399b604703b410490e671dbdcc6f7d", 2058),
    "2026-11-10": ("fbbb8e35eea5582f29ceff159ccf2bf50ae070b2", 1741),
    "2026-11-11": ("ecdcbc5fb46ca3ebd2ec9b521ed899b94d7503b7", 2533),
    "2026-11-12": ("36b0ad9d07458193cacab4197adc34e8dd8e32f5", 4389),
    "2026-11-13": ("2418287a218324b8e6d23c340974a719ee3c2303", 2916),
    "2026-11-14": ("2416cb030cb393c488dc6130607dc2a4622c71e2", 3290),
    "2026-11-15": ("dbc65da1e8d58aa80d1180a8f66b083247a912e7", 4820),
    "2026-11-16": ("5a2116fc02f93cf7a86d9d70b22d211c54d67fac", 2928),
    "2026-11-17": ("1065b30776462f2b58ddd95d9e792840a0fda28a", 2443),
    "2026-11-18": ("0e05012d8719559149c1aadf309355715f8942f2", 2432),
    "2026-11-19": ("624a682be3dbe1e70e9d529e145f596301bc05a1", 2266),
    "2026-11-20": ("a067f73a9223802c3034b52afc8bef83f49e302a", 1733),
    "2026-11-21": ("6a3b18f6a57c6b5c5d7c1ca179b8845de016d9b7", 707),
}
# Entries per day from the grammar probe over the same 13 READMEs.
PROBE_COUNTS = {"2026-11-09": 7, "2026-11-10": 4, "2026-11-11": 5, "2026-11-12": 7, "2026-11-13": 4,
                "2026-11-14": 4, "2026-11-15": 4, "2026-11-16": 3, "2026-11-17": 2, "2026-11-18": 3,
                "2026-11-19": 3, "2026-11-20": 2, "2026-11-21": 1}

# Expected error code for every bad fixture folder.
BAD_CODES = {
    'args_bad_date': 'bad_args',
    'args_duplicate_flag': 'bad_args',
    'args_file_invalid_utf8': 'bad_encoding',
    'args_odd_tokens': 'bad_args',
    'args_root_from_case': 'bad_args',
    'args_unknown_flag': 'bad_args',
    'base_malformed_day': 'malformed_item',
    'base_missing_root': 'missing_root',
    'base_pin_mismatch': 'pin_mismatch',
    'base_to_before_from': 'bad_window',
    'pins_crlf': 'bad_pin',
    'pins_duplicate_line': 'duplicate_pin',
    'pins_empty': 'bad_pin',
    'pins_huge_size': 'bad_pin',
    'pins_invalid_utf8': 'bad_encoding',
    'pins_is_a_folder': 'not_a_file',
    'pins_leading_zero_size': 'bad_pin',
    'pins_legacy_day': 'bad_pin',
    'pins_no_final_newline': 'bad_pin',
    'pins_other_path': 'bad_pin',
    'pins_pinned_day_missing': 'missing_file',
    'pins_sha_mismatch': 'pin_mismatch',
    'pins_short_sha': 'bad_pin',
    'pins_size_mismatch': 'pin_mismatch',
    'pins_too_large': 'too_large',
    'pins_unpinned_day': 'unpinned_readme',
    'pins_unsorted': 'unsorted_pins',
    'pins_uppercase_hex': 'bad_pin',
    'readme_blank_between_rows': 'malformed_line',
    'readme_bom': 'bad_encoding',
    'readme_bullet_bold_label': 'malformed_item',
    'readme_bullet_no_colon': 'malformed_item',
    'readme_crlf': 'bad_line_ending',
    'readme_duplicate_slug': 'duplicate_entry',
    'readme_empty': 'bad_heading',
    'readme_empty_text': 'bad_text',
    'readme_encoded_surrogate': 'bad_encoding',
    'readme_footer_without_blank': 'malformed_line',
    'readme_footer_without_period': 'malformed_line',
    'readme_heading_date_mismatch': 'heading_date_mismatch',
    'readme_heading_korean_index': 'bad_heading',
    'readme_heading_other_title': 'bad_heading',
    'readme_heading_trailing_space': 'bad_heading',
    'readme_invalid_utf8': 'bad_encoding',
    'readme_is_a_folder': 'not_a_file',
    'readme_link_dot_slash': 'link_mismatch',
    'readme_link_other_slug': 'link_mismatch',
    'readme_link_without_slash': 'link_mismatch',
    'readme_lone_cr': 'bad_line_ending',
    'readme_missing': 'missing_file',
    'readme_no_blank_after_heading': 'malformed_line',
    'readme_no_entries': 'no_entries',
    'readme_only_trailing_blank': 'malformed_line',
    'readme_overlong_utf8': 'bad_encoding',
    'readme_row_too_long': 'too_long',
    'readme_slug_backticks': 'bad_slug',
    'readme_slug_double_hyphen': 'bad_slug',
    'readme_slug_korean': 'bad_slug',
    'readme_slug_too_long': 'too_long',
    'readme_slug_uppercase': 'bad_slug',
    'readme_table_rows': 'no_entries',
    'readme_text_after_rows': 'malformed_line',
    'readme_text_bidi_override': 'bad_char',
    'readme_text_bom_inside': 'bad_char',
    'readme_text_escape_char': 'bad_char',
    'readme_text_line_separator': 'bad_char',
    'readme_text_no_break_space': 'bad_char',
    'readme_text_nul': 'bad_char',
    'readme_text_private_use': 'bad_char',
    'readme_text_tab': 'bad_char',
    'readme_text_trailing_space': 'bad_text',
    'readme_text_unassigned': 'bad_char',
    'readme_text_zero_width_space': 'bad_char',
    'readme_too_large': 'too_large',
    'readme_too_many_entries': 'too_many',
    'readme_trailing_blank_line': 'malformed_line',
    'readme_two_footers': 'malformed_line',
    'readme_utf16': 'bad_encoding',
    'root_date_fullwidth_digits': 'bad_root_entry',
    'root_date_is_a_file': 'bad_root_entry',
    'root_impossible_date': 'bad_root_entry',
    'root_is_a_file': 'missing_root',
    'root_missing': 'missing_root',
    'root_not_a_date': 'bad_root_entry',
    'root_only_legacy_days': 'no_days_in_window',
    'root_stray_file': 'bad_root_entry',
    'tracks_bad_key': 'bad_key',
    'tracks_bom': 'bad_encoding',
    'tracks_bool': 'wrong_type',
    'tracks_control_char': 'bad_char',
    'tracks_deep_nesting': 'too_deep',
    'tracks_duplicate_key': 'duplicate_key',
    'tracks_edge_space': 'bad_text',
    'tracks_empty_file': 'not_json',
    'tracks_empty_name': 'bad_text',
    'tracks_float': 'wrong_type',
    'tracks_huge_int': 'wrong_type',
    'tracks_infinity': 'bad_number',
    'tracks_int': 'wrong_type',
    'tracks_invalid_utf8': 'bad_encoding',
    'tracks_korean_key': 'bad_key',
    'tracks_list_value': 'wrong_type',
    'tracks_lone_surrogate': 'bad_char',
    'tracks_name_too_long': 'too_long',
    'tracks_nan': 'bad_number',
    'tracks_negative_infinity': 'bad_number',
    'tracks_nested': 'wrong_type',
    'tracks_not_json': 'not_json',
    'tracks_null': 'wrong_type',
    'tracks_too_large': 'too_large',
    'tracks_too_many': 'too_many',
    'tracks_top_level_list': 'wrong_type',
    'tracks_trailing_comma': 'not_json',
    'tracks_zero_width_joiner': 'bad_char',
    'window_broken_day_inside': 'bad_heading',
    'window_empty': 'no_days_in_window',
    'window_inverted': 'bad_window',
}


def snapshot_opts(**extra):
    opts = {"root": os.path.join(SNAPSHOT, "experiments"), "pins": os.path.join(SNAPSHOT, "pins.txt"),
            "tracks": TRACKS}
    opts.update(extra)
    return opts


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = wc.main(args)
    return code, out.getvalue(), err.getvalue()


class Tree:
    """A private temporary corpus for one test; removed afterwards."""

    def __init__(self, files):
        self.dir = tempfile.mkdtemp(prefix="w30-test-")
        self.root = os.path.join(self.dir, "experiments")
        os.makedirs(self.root)
        for rel, data in files.items():
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def day(date, slugs, footer=True):
    lines = ["# experiments/" + date, ""] + ["- [%s](%s/): authored row" % (s, s) for s in slugs]
    if footer:
        lines += ["", wc.FOOTER]
    return "\n".join(lines) + "\n"


class RecordingRead:
    def __init__(self):
        self.paths = []

    def __call__(self, path, cap, what):
        self.paths.append(path)
        return wc._read_bytes(path, cap, what)


class SnapshotRegressionTests(unittest.TestCase):
    """Regression on the frozen real snapshot: count assertions over pinned bytes, not a live tree."""

    @classmethod
    def setUpClass(cls):
        cls.full = wc.run(snapshot_opts())

    def test_each_copy_matches_its_pinned_git_blob(self):
        for date, (sha, size) in PINNED.items():
            with open(os.path.join(SNAPSHOT, "experiments", date, "README.md"), "rb") as fh:
                data = fh.read()
            self.assertEqual(len(data), size, date)
            self.assertEqual(hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest(), sha, date)
            self.assertEqual(wc.git_blob_sha1(data), sha, date)

    def test_pin_file_lists_exactly_the_thirteen_blobs(self):
        with open(os.path.join(SNAPSHOT, "pins.txt"), "r", encoding="utf-8") as fh:
            text = fh.read()
        expected = "".join("%s %d experiments/%s/README.md\n" % (sha, size, date)
                           for date, (sha, size) in sorted(PINNED.items()))
        self.assertEqual(text, expected)

    def test_snapshot_holds_only_the_thirteen_readmes_and_the_pins(self):
        found = []
        for base, dirs, files in os.walk(SNAPSHOT):
            for name in files:
                found.append(os.path.relpath(os.path.join(base, name), SNAPSHOT).replace(os.sep, "/"))
        self.assertEqual(sorted(found), sorted(["pins.txt"] + ["experiments/%s/README.md" % d for d in PINNED]))

    def test_thirteen_days_and_forty_nine_entries(self):
        self.assertEqual(self.full["counts"]["days"], 13)
        self.assertEqual(self.full["counts"]["entries"], 49)
        self.assertEqual(len(self.full["entries"]), 49)
        self.assertEqual(self.full["pins"], "verified 13/13")

    def test_per_day_counts_equal_the_probe(self):
        self.assertEqual(self.full["counts"]["by_date"], PROBE_COUNTS)

    def test_slugs_equal_an_independent_reading_of_the_bytes(self):
        pattern = re.compile(r"^- \[([a-z0-9-]+)\]\(([a-z0-9-]+)/\): ", re.M)
        for date in PINNED:
            with open(os.path.join(SNAPSHOT, "experiments", date, "README.md"), "r", encoding="utf-8") as fh:
                expected = [m.group(1) for m in pattern.finditer(fh.read())]
            got = [e["slug"] for e in self.full["entries"] if e["date"] == date]
            self.assertEqual(got, expected, date)

    def test_every_entry_carries_its_readme_path_and_blob(self):
        for e in self.full["entries"]:
            self.assertEqual(e["source"], {"path": "experiments/%s/README.md" % e["date"],
                                           "blob": PINNED[e["date"]][0]})
        self.assertEqual([(d["date"], d["blob"], d["bytes"]) for d in self.full["days"]],
                         [(k, v[0], v[1]) for k, v in sorted(PINNED.items())])

    def test_track_counts_on_the_snapshot(self):
        self.assertEqual(self.full["counts"]["by_track"],
                         {"(no track)": 31, "morning-brief": 10, "검증": 3, "빌리지 생활 도구": 2,
                          "에이전트 사이 협업": 2, "창작·놀이": 1})

    def test_wave_and_family_counts_on_the_snapshot(self):
        self.assertEqual(self.full["counts"]["by_wave"],
                         {"w18": 6, "w19": 4, "w20": 5, "w21": 6, "w22": 3, "w23": 3, "w24": 3, "w25": 2,
                          "w26": 1, "w27": 2, "w28": 2, "w29": 1})
        self.assertEqual(self.full["counts"]["by_family"]["mb"], 10)
        self.assertEqual(self.full["counts"]["by_family"]["01"], 1)
        self.assertEqual(sum(self.full["counts"]["by_family"].values()), 49)

    def test_week_window_and_what_changed(self):
        week = wc.run(snapshot_opts(**{"from": "2026-11-15", "to": "2026-11-21", "base_to": "2026-11-20"}))
        self.assertEqual((week["counts"]["days"], week["counts"]["entries"]), (7, 18))
        self.assertEqual(week["on_unmeasured"]["outside_window"],
                         ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14"])
        self.assertEqual(week["changed"]["added"],
                         [{"entry": "experiments/2026-11-21/mb-evidence-binding", "blob": PINNED["2026-11-21"][0]}])
        self.assertEqual((week["changed"]["removed"], week["changed"]["changed"]), ([], []))

    def test_no_legacy_day_in_the_snapshot(self):
        self.assertEqual(self.full["on_unmeasured"], {"legacy_table_format": [], "outside_window": []})

    def test_a_flipped_byte_in_a_copy_is_refused(self):
        tmp = tempfile.mkdtemp(prefix="w30-test-")
        try:
            shutil.copytree(SNAPSHOT, os.path.join(tmp, "snap"))
            path = os.path.join(tmp, "snap", "experiments", "2026-11-14", "README.md")
            with open(path, "rb") as fh:
                data = bytearray(fh.read())
            data[-3] = ord("X")
            with open(path, "wb") as fh:
                fh.write(bytes(data))
            code, out, err = run_cli(["--case", os.path.join(tmp, "snap")])
            self.assertEqual((code, out), (2, ""))
            self.assertTrue(err.startswith("ERROR pin_mismatch:"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ScopeTests(unittest.TestCase):
    """F1: v1 scope starts at 2026-11-09; earlier days and out-of-window days are never opened."""

    def setUp(self):
        self.tree = Tree({
            "2026-10-29/README.md": b"# Morning Brief \xe2\x80\x94 2026-10-29\n| 01 | x |\n",
            "2026-11-08/README.md": b"\xff\xfe not even UTF-8",
            "2026-11-09/README.md": day("2026-11-09", ["w18-alpha"]),
            "2026-11-10/README.md": day("2026-11-10", ["w19-beta", "mb-gamma"]),
            "2026-11-11/README.md": b"# broken\n",
        })

    def tearDown(self):
        self.tree.close()

    def test_scope_start_is_declared(self):
        self.assertEqual(wc.SCOPE_START, "2026-11-09")
        self.assertEqual(wc.LEGACY_REASON, "legacy_table_format")

    def test_legacy_days_are_listed_not_measured_and_never_opened(self):
        read = RecordingRead()
        result = wc.run({"root": self.tree.root, "to": "2026-11-10"}, read=read)
        self.assertEqual(result["on_unmeasured"]["legacy_table_format"], ["2026-10-29", "2026-11-08"])
        opened = sorted(os.path.basename(os.path.dirname(p)) for p in read.paths)
        self.assertEqual(opened, ["2026-11-09", "2026-11-10"])
        self.assertEqual(result["counts"]["entries"], 3)

    def test_out_of_window_days_are_never_opened(self):
        read = RecordingRead()
        result = wc.run({"root": self.tree.root, "from": "2026-11-10", "to": "2026-11-10"}, read=read)
        self.assertEqual([os.path.basename(os.path.dirname(p)) for p in read.paths], ["2026-11-10"])
        self.assertEqual(result["on_unmeasured"]["outside_window"], ["2026-11-09", "2026-11-11"])

    def test_window_bounds_are_inclusive(self):
        result = wc.run({"root": self.tree.root, "from": "2026-11-09", "to": "2026-11-10"})
        self.assertEqual([d["date"] for d in result["days"]], ["2026-11-09", "2026-11-10"])

    def test_malformed_day_inside_scope_and_window_is_deny(self):
        with self.assertRaises(wc.ChronicleError) as cm:
            wc.run({"root": self.tree.root})
        self.assertEqual(cm.exception.code, "bad_heading")

    def test_window_before_scope_only_is_deny(self):
        with self.assertRaises(wc.ChronicleError) as cm:
            wc.run({"root": self.tree.root, "to": "2026-11-08"})
        self.assertEqual(cm.exception.code, "no_days_in_window")

    def test_empty_root_is_deny(self):
        tree = Tree({})
        try:
            with self.assertRaises(wc.ChronicleError) as cm:
                wc.run({"root": tree.root})
            self.assertEqual(cm.exception.code, "no_days_in_window")
        finally:
            tree.close()

    def test_symlinked_readme_is_refused(self):
        tree = Tree({"2026-11-09/target.md": day("2026-11-09", ["w18-alpha"])})
        try:
            os.symlink("target.md", os.path.join(tree.root, "2026-11-09", "README.md"))
            with self.assertRaises(wc.ChronicleError) as cm:
                wc.run({"root": tree.root})
            self.assertEqual(cm.exception.code, "not_a_file")
        finally:
            tree.close()

    def test_symlinked_day_folder_is_refused(self):
        tree = Tree({"2026-11-09/README.md": day("2026-11-09", ["w18-alpha"])})
        try:
            os.symlink("2026-11-09", os.path.join(tree.root, "2026-11-10"))
            with self.assertRaises(wc.ChronicleError) as cm:
                wc.run({"root": tree.root})
            self.assertEqual(cm.exception.code, "bad_root_entry")
        finally:
            tree.close()


class GrammarTests(unittest.TestCase):

    def test_entries_carry_family_wave_and_row(self):
        entries = wc.parse_day("2026-11-19", day("2026-11-19", ["w28-alpha", "mb-gamma", "01-step-x"]))
        self.assertEqual([(e["slug"], e["family"], e["wave"]) for e in entries],
                         [("w28-alpha", "w28", 28), ("mb-gamma", "mb", None), ("01-step-x", "01", None)])
        self.assertEqual(entries[0]["row"], "- [w28-alpha](w28-alpha/): authored row")

    def test_footer_is_not_an_entry_and_is_optional(self):
        with_footer = wc.parse_day("2026-11-19", day("2026-11-19", ["w28-alpha"]))
        without = wc.parse_day("2026-11-19", day("2026-11-19", ["w28-alpha"], footer=False))
        self.assertEqual(with_footer, without)
        self.assertEqual(len(with_footer), 1)

    def test_final_newline_is_optional(self):
        text = day("2026-11-19", ["w28-alpha"])
        self.assertEqual(wc.parse_day("2026-11-19", text), wc.parse_day("2026-11-19", text[:-1]))

    def test_wave_is_two_digits_only(self):
        entries = wc.parse_day("2026-11-19", day("2026-11-19", ["w3-alpha", "w100-beta", "wx-gamma"]))
        self.assertEqual([e["wave"] for e in entries], [None, None, None])

    def test_heading_must_be_exact(self):
        for heading, code in (("# experiments/2026-11-18", "heading_date_mismatch"),
                              ("## experiments/2026-11-19", "bad_heading"),
                              ("# Experiments/2026-11-19", "bad_heading"),
                              ("# experiments/2026-11-19 ", "bad_heading")):
            with self.assertRaises(wc.ChronicleError) as cm:
                wc.parse_day("2026-11-19", heading + "\n\n- [w28-a](w28-a/): x\n")
            self.assertEqual(cm.exception.code, code, heading)

    def test_footer_must_follow_one_blank_line(self):
        ok = "# experiments/2026-11-19\n\n- [w28-a](w28-a/): x\n\n" + wc.FOOTER + "\n"
        self.assertEqual(len(wc.parse_day("2026-11-19", ok)), 1)
        for text in (ok.replace("\n\n" + wc.FOOTER, "\n" + wc.FOOTER), ok + "\n", ok + wc.FOOTER + "\n",
                     ok.replace(wc.FOOTER, wc.FOOTER.lower())):
            with self.assertRaises(wc.ChronicleError) as cm:
                wc.parse_day("2026-11-19", text)
            self.assertEqual(cm.exception.code, "malformed_line")

    def test_korean_text_is_accepted_in_rows(self):
        text = "# experiments/2026-11-19\n\n- [w30-a](w30-a/): 마을 연대기, 한 주의 실험\n"
        self.assertEqual(wc.parse_day("2026-11-19", text)[0]["slug"], "w30-a")
        nfd = unicodedata.normalize("NFD", text)
        self.assertEqual(wc.parse_day("2026-11-19", nfd)[0]["slug"], "w30-a")

    def test_entry_cap(self):
        limit = wc.CAPS["entries_per_day"]["limit"]
        self.assertEqual(len(wc.parse_day("2026-11-19", day("2026-11-19", ["w28-a%d" % i for i in range(limit)]))),
                         limit)
        with self.assertRaises(wc.ChronicleError) as cm:
            wc.parse_day("2026-11-19", day("2026-11-19", ["w28-a%d" % i for i in range(limit + 1)]))
        self.assertEqual(cm.exception.code, "too_many")

    def test_every_cap_declares_deny(self):
        self.assertTrue(wc.CAPS)
        for name, cap in wc.CAPS.items():
            self.assertEqual(cap["on_expiry"], "DENY", name)
            self.assertIs(type(cap["limit"]), int, name)
        self.assertEqual(wc.ON_EXPIRY, "DENY")

    def test_readme_size_cap_boundary(self):
        limit = wc.CAPS["readme_bytes"]["limit"]
        tree = Tree({"2026-11-19/README.md": b"x" * (limit + 1)})
        try:
            with self.assertRaises(wc.ChronicleError) as cm:
                wc.run({"root": tree.root})
            self.assertEqual(cm.exception.code, "too_large")
        finally:
            tree.close()


class TrackTests(unittest.TestCase):

    def test_unknown_prefix_is_listed_with_info_and_no_invented_track(self):
        tree = Tree({"2026-11-19/README.md": day("2026-11-19", ["zz-foo", "w28-alpha"])})
        try:
            result = wc.run({"root": tree.root, "tracks": TRACKS})
        finally:
            tree.close()
        zz = [e for e in result["entries"] if e["slug"] == "zz-foo"][0]
        self.assertEqual((zz["track"], zz["notes"]), (None, ["unknown_track"]))
        alpha = [e for e in result["entries"] if e["slug"] == "w28-alpha"][0]
        self.assertEqual((alpha["track"], alpha["notes"]), ("검증", []))

    def test_without_tracks_every_entry_is_unknown(self):
        result = wc.run({"root": os.path.join(SNAPSHOT, "experiments")})
        self.assertEqual(result["counts"]["by_track"], {"(no track)": 49})
        self.assertEqual(result["pins"], "not given")

    def test_shipped_tracks_file(self):
        with open(TRACKS, "rb") as fh:
            tracks = wc.parse_tracks(fh.read())
        self.assertEqual(tracks, {"mb": "morning-brief", "w25": "빌리지 생활 도구", "w26": "검증",
                                  "w27": "에이전트 사이 협업", "w28": "검증", "w29": "창작·놀이", "w30": "관찰·회고"})
        self.assertNotIn("w24", tracks)

    def test_track_names_are_nfc_normalised(self):
        nfd = json.dumps({"w28": unicodedata.normalize("NFD", "검증")}, ensure_ascii=False).encode("utf-8")
        self.assertEqual(wc.parse_tracks(nfd), {"w28": "검증"})

    def test_track_value_types(self):
        for text, code in (('{"mb": true}', "wrong_type"), ('{"mb": 1}', "wrong_type"), ('{"mb": 1.0}', "wrong_type"),
                           ('{"mb": NaN}', "bad_number"), ('{"mb": "a", "mb": "b"}', "duplicate_key"),
                           ('[]', "wrong_type"), ('{"mb": "\\udc00"}', "bad_char")):
            with self.assertRaises(wc.ChronicleError) as cm:
                wc.parse_tracks(text.encode())
            self.assertEqual(cm.exception.code, code, text)


class DiffTests(unittest.TestCase):

    def test_added_removed_and_changed(self):
        result = wc.run({"root": os.path.join(FIX, "valid", "diff_snapshots", "experiments"),
                         "base": os.path.join(FIX, "valid", "diff_snapshots", "base", "experiments")})
        ch = result["changed"]
        self.assertEqual([x["entry"] for x in ch["added"]], ["experiments/2026-11-20/w29-epsilon"])
        self.assertEqual([x["entry"] for x in ch["removed"]], ["experiments/2026-11-20/w29-delta"])
        self.assertEqual([x["entry"] for x in ch["changed"]], ["experiments/2026-11-19/mb-gamma"])
        self.assertNotEqual(ch["changed"][0]["base_blob"], ch["changed"][0]["blob"])

    def test_identical_trees_have_an_empty_change_set(self):
        result = wc.run({"root": os.path.join(FIX, "valid", "diff_identical", "experiments"),
                         "base": os.path.join(FIX, "valid", "diff_identical", "base", "experiments")})
        self.assertEqual({k: result["changed"][k] for k in ("added", "removed", "changed")},
                         {"added": [], "removed": [], "changed": []})

    def test_a_day_moved_to_another_date_is_added_and_removed(self):
        old = Tree({"2026-11-19/README.md": day("2026-11-19", ["w28-alpha"])})
        new = Tree({"2026-11-20/README.md": day("2026-11-20", ["w28-alpha"])})
        try:
            ch = wc.run({"root": new.root, "base": old.root})["changed"]
        finally:
            old.close()
            new.close()
        self.assertEqual(([x["entry"] for x in ch["added"]], [x["entry"] for x in ch["removed"]]),
                         (["experiments/2026-11-20/w28-alpha"], ["experiments/2026-11-19/w28-alpha"]))

    def test_no_change_section_without_a_base(self):
        self.assertNotIn("changed", wc.run(snapshot_opts()))


class PinTests(unittest.TestCase):

    def test_git_blob_ids_of_known_contents(self):
        self.assertEqual(wc.git_blob_sha1(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")
        self.assertEqual(wc.git_blob_sha1(b"hello\n"), "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_parse_pins(self):
        text = "%s 12 experiments/2026-11-09/README.md\n%s 7 experiments/2026-11-10/README.md\n" % ("a" * 40, "b" * 40)
        self.assertEqual(wc.parse_pins(text.encode()), {"2026-11-09": ("a" * 40, 12), "2026-11-10": ("b" * 40, 7)})

    def test_pins_outside_the_window_are_not_required(self):
        result = wc.run(snapshot_opts(**{"from": "2026-11-20"}))
        self.assertEqual(result["pins"], "verified 2/2")


class PlannedCaseTests(unittest.TestCase):
    """The seven cases (a)-(g) planned for this sketch, on authored fixtures."""

    def test_a_three_entries_two_days_with_tracks(self):
        result = wc.run({"root": os.path.join(FIX, "valid", "two_days", "experiments"),
                         "tracks": os.path.join(FIX, "valid", "two_days", "tracks.json")})
        self.assertEqual([(e["date"], e["slug"], e["track"]) for e in result["entries"]],
                         [("2026-11-19", "w28-alpha", "검증"), ("2026-11-19", "mb-gamma", "morning-brief"),
                          ("2026-11-20", "w29-beta", "창작·놀이")])
        self.assertEqual(result["counts"]["by_track"], {"morning-brief": 1, "검증": 1, "창작·놀이": 1})

    def test_b_heading_date_mismatch_is_deny(self):
        self.assertEqual(run_cli(["--case", os.path.join(FIX, "bad", "readme_heading_date_mismatch")])[0], 2)

    def test_c_missing_readme_is_deny(self):
        self.assertEqual(run_cli(["--case", os.path.join(FIX, "bad", "readme_missing")])[0], 2)

    def test_d_malformed_bullet_is_deny(self):
        self.assertEqual(run_cli(["--case", os.path.join(FIX, "bad", "readme_bullet_no_colon")])[0], 2)

    def test_e_unknown_prefix_is_info(self):
        code, out, err = run_cli(["--case", os.path.join(FIX, "valid", "unknown_prefix")])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("- zz-foo (family: zz, track: none, INFO unknown_track)", out)

    def test_f_snapshots_added_and_identical(self):
        code, out, _ = run_cli(["--case", os.path.join(FIX, "valid", "diff_snapshots")])
        self.assertEqual(code, 0)
        self.assertIn("- added: experiments/2026-11-20/w29-epsilon @ ", out)
        code, out, _ = run_cli(["--case", os.path.join(FIX, "valid", "diff_identical")])
        self.assertIn("- added: none\n- removed: none\n- changed: none\n", out)

    def test_g_window_omits_dates_outside(self):
        code, out, _ = run_cli(["--case", os.path.join(FIX, "valid", "two_days"), "--from", "2026-11-20"])
        self.assertEqual(code, 0)
        self.assertNotIn("## 2026-11-19", out)
        self.assertIn("## 2026-11-20", out)
        self.assertIn("- outside_window: 2026-11-19", out)


class CommandLineTests(unittest.TestCase):

    def test_every_bad_fixture_is_deny_with_one_error_line(self):
        names = sorted(os.listdir(os.path.join(FIX, "bad")))
        self.assertEqual(names, sorted(BAD_CODES))
        for name in names:
            code, out, err = run_cli(["--case", os.path.join(FIX, "bad", name)])
            self.assertEqual((code, out), (2, ""), name)
            self.assertEqual(len(err.splitlines()), 1, name)
            self.assertTrue(err.endswith("\n"), name)
            self.assertTrue(err.startswith("ERROR %s: " % BAD_CODES[name]), (name, err))
            self.assertIn("on_expiry=DENY", err)

    def test_every_valid_fixture_exits_zero(self):
        names = sorted(os.listdir(os.path.join(FIX, "valid")))
        self.assertGreaterEqual(len(names), 10)
        for name in names:
            code, out, err = run_cli(["--case", os.path.join(FIX, "valid", name)])
            self.assertEqual((code, err), (0, ""), name)
            self.assertTrue(out.startswith("# Wave chronicle\n"), name)

    def test_korean_fixtures_agree(self):
        a = wc.run({"root": os.path.join(FIX, "valid", "korean_text", "experiments"),
                    "tracks": os.path.join(FIX, "valid", "korean_text", "tracks.json")})
        b = wc.run({"root": os.path.join(FIX, "valid", "korean_nfd", "experiments"),
                    "tracks": os.path.join(FIX, "valid", "korean_nfd", "tracks.json")})
        self.assertEqual(a["counts"], b["counts"])
        self.assertEqual([(e["slug"], e["track"]) for e in a["entries"]], [(e["slug"], e["track"]) for e in b["entries"]])

    def test_subprocess_error_contract(self):
        p = subprocess.run([sys.executable, "-B", "wave_chronicle.py", "--case",
                            os.path.join("fixtures", "bad", "readme_crlf")], cwd=HERE, capture_output=True)
        self.assertEqual((p.returncode, p.stdout), (2, b""))
        self.assertEqual(len(p.stderr.splitlines()), 1)
        self.assertTrue(p.stderr.startswith(b"ERROR bad_line_ending: "))
        self.assertNotIn(b"Traceback", p.stderr)

    def test_subprocess_snapshot_run(self):
        p = subprocess.run([sys.executable, "-B", "wave_chronicle.py", "--case",
                            os.path.join("fixtures", "snapshot-f2fa1e5d"), "--json"], cwd=HERE, capture_output=True)
        self.assertEqual((p.returncode, p.stderr), (0, b""))
        self.assertEqual(json.loads(p.stdout.decode("utf-8"))["counts"]["entries"], 49)

    def test_bad_arguments(self):
        for args in ([], ["--root"], ["--root", "a", "--root", "b"], ["--nope"], ["--json", "--json", "--root", "a"],
                     ["--root", "a", "--from", "2026-02-30"], ["--case", FIX, "--root", "a"],
                     ["--root", "a", "--base-pins", "p"], ["--root", "--json"]):
            code, out, err = run_cli(args)
            self.assertEqual((code, out), (2, ""), args)
            self.assertEqual(len(err.splitlines()), 1, args)
            self.assertTrue(err.startswith("ERROR bad_args: "), (args, err))

    def test_missing_case_folder(self):
        code, out, err = run_cli(["--case", os.path.join(FIX, "no-such-case")])
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.startswith("ERROR missing_root: "))

    def test_json_and_markdown_agree(self):
        code, out, _ = run_cli(["--case", SNAPSHOT, "--tracks", TRACKS, "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data, wc.run(snapshot_opts()))
        self.assertEqual(run_cli(["--case", SNAPSHOT, "--tracks", TRACKS])[1], wc.render(data))

    def test_markdown_lines_carry_path_and_blob(self):
        text = wc.render(wc.run(snapshot_opts()))
        rows = [l for l in text.splitlines() if l.startswith("- ") and " @ " in l and l.endswith("]")]
        self.assertEqual(len(rows), 49)
        for line in rows:
            self.assertRegex(line, r"\[experiments/2026-11-[0-9]{2}/README\.md @ [0-9a-f]{40}\]$")


class DemoTests(unittest.TestCase):

    def demo(self):
        p = subprocess.run([sys.executable, "-B", "demo.py"], cwd=HERE, capture_output=True)
        self.assertEqual((p.returncode, p.stderr), (0, b""))
        return p.stdout

    def test_demo_is_deterministic_and_matches_the_readme(self):
        a, b = self.demo(), self.demo()
        self.assertEqual(a, b)
        digest = hashlib.sha256(a).hexdigest()
        with open(os.path.join(HERE, "README.md"), "r", encoding="utf-8") as fh:
            self.assertIn(digest, fh.read())

    def test_demo_reports_the_real_counts(self):
        text = self.demo().decode("utf-8")
        self.assertIn("- days: 13\n- entries: 49\n", text)
        self.assertIn("- days: 7\n- entries: 18\n", text)
        self.assertIn("- added: experiments/2026-11-21/mb-evidence-binding @ " + PINNED["2026-11-21"][0], text)
        self.assertIn("- pins: verified 13/13", text)


SNAP_PREFIX = os.path.join("fixtures", "snapshot-f2fa1e5d") + os.sep
BANNED = ["al" + "low", "ke" + "ep", "cloud" + "agent", "smi" + "th", "chec" + "ker"]
PATHS = ["/" + "workspace", "/" + "tmp", "/" + "home"]
MECHANISM = [r"fei" + "shu", r"sql" + "ite", r"hm" + "ac", r"dae" + "mon", r"grok" + "ki", r"sla" + "ck",
             r"hash-" + "chain", r"vot" + "ing", r"ensem" + "ble", r"\bds" + r"h\b", r"\bn" + r"c\b",
             r"\bgp" + r"l\b", r"\bsign" + r"ing\b", r"\bhoo" + r"ks?\b", r"cursor_" + "agent", "<d" + "iv", "<!" + "--"]


def authored_files():
    out = []
    for base, dirs, files in os.walk(HERE):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(base, name), HERE)
            if not rel.startswith(SNAP_PREFIX):
                out.append(rel)
    return out


def read_text(rel):
    with open(os.path.join(HERE, rel), "rb") as fh:
        return fh.read().decode("utf-8", errors="replace")


class HygieneTests(unittest.TestCase):

    def test_top_level_files(self):
        self.assertEqual(sorted(n for n in os.listdir(HERE) if n != "__pycache__"),
                         ["README.md", "demo.py", "evidence.json", "fixtures", "mutants.py", "test_wave_chronicle.py",
                          "wave_chronicle.py"])

    def test_fixture_layout(self):
        self.assertEqual(sorted(os.listdir(FIX)), ["bad", "snapshot-f2fa1e5d", "tracks.json", "valid"])

    def test_no_banned_word_or_path_in_authored_files(self):
        for rel in authored_files():
            low = read_text(rel).lower()
            for word in BANNED + PATHS:
                self.assertNotIn(word, low, rel)
                self.assertNotIn(word, rel.lower())

    def test_no_mechanism_word_in_authored_files(self):
        for rel in authored_files():
            low = read_text(rel).lower()
            for pattern in MECHANISM:
                self.assertIsNone(re.search(pattern, low), (rel, pattern))

    def test_stdlib_only_and_no_network(self):
        expected_imports = {"datetime", "hashlib", "json", "os", "re", "stat", "sys", "unicodedata"}
        src = read_text("wave_chronicle.py")
        imports = set(re.findall(r"^import (\w+)", src, re.M)) | set(re.findall(r"^from (\w+)", src, re.M))
        self.assertEqual(imports, expected_imports)
        for word in ("socket", "urllib", "http.client", "subprocess", "requests"):
            self.assertNotIn(word, src)
        self.assertNotIn("subprocess", read_text("demo.py"))

    def test_no_empty_folders(self):
        for base, dirs, files in os.walk(HERE):
            if "__pycache__" in base:
                continue
            self.assertTrue(dirs or files, os.path.relpath(base, HERE))


class EvidenceTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "evidence.json"), "r", encoding="utf-8") as fh:
            cls.ev = json.load(fh)

    def test_flags(self):
        self.assertIs(self.ev["network_used"], False)
        self.assertIs(self.ev["paid_api_used"], False)
        self.assertIs(self.ev["clean_room"], True)
        self.assertIsNone(self.ev["paper"])
        self.assertEqual(self.ev["snapshot"]["main"], "f2fa1e5d341f2f022d5b4a61d7563a6560db0212")

    def test_measured_counts_match_a_fresh_run(self):
        full = wc.run(snapshot_opts())
        self.assertEqual(self.ev["measured"]["full"], full["counts"])
        week = wc.run(snapshot_opts(**{"from": "2026-11-15", "to": "2026-11-21", "base_to": "2026-11-20"}))
        self.assertEqual(self.ev["measured"]["week"]["counts"], week["counts"])
        self.assertEqual(self.ev["measured"]["week"]["added"], [x["entry"] for x in week["changed"]["added"]])

    def test_snapshot_pins_recorded(self):
        self.assertEqual(self.ev["snapshot"]["blobs"], {k: v[0] for k, v in PINNED.items()})

    def test_unmeasured_items_are_unverified(self):
        items = self.ev["on_unmeasured"]["items"]
        self.assertGreaterEqual(len(items), 4)
        for item in items:
            self.assertEqual(item["status"], "UNVERIFIED", item["id"])
        self.assertIn("legacy_table_format", [i["id"] for i in items])

    def test_timeouts_declared(self):
        self.assertEqual(self.ev["timeouts"]["tool"], "none")
        self.assertEqual(self.ev["timeouts"]["mutants"]["on_expiry"], "DENY")


class DocumentTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.readme = read_text("README.md")
        cls.flat = " ".join(cls.readme.split())

    def test_title_and_statements(self):
        self.assertTrue(self.readme.startswith("# w30-wave-chronicle\n"))
        for needle in ("Clean-room", "no paper", "2026-11-09", "legacy_table_format", "on_expiry", "DENY",
                       "f2fa1e5d341f2f022d5b4a61d7563a6560db0212", "git blob SHA1", "UNVERIFIED"):
            self.assertIn(needle, self.flat, needle)

    def test_not_a_remake_line(self):
        lines = [l for l in self.readme.splitlines() if "w25-daily-issue-index" in l and "w20-fidelity-audit" in l]
        self.assertEqual(len(lines), 1)
        self.assertIn("Not a remake", lines[0])


class MutantsHarnessTests(unittest.TestCase):

    def test_timeout_is_declared_and_never_counts_as_killed(self):
        import mutants
        self.assertEqual(set(mutants.TIMEOUT), {"seconds", "on_expiry"})
        self.assertIs(type(mutants.TIMEOUT["seconds"]), int)
        self.assertIn(mutants.TIMEOUT["on_expiry"], {"HOLD", "ESCALATE", "DENY"})
        self.assertEqual(mutants.TIMEOUT["on_expiry"], "DENY")
        self.assertEqual(mutants.outcome(None), "TIMEOUT")
        self.assertEqual(mutants.outcome(0), "SURVIVED")
        self.assertEqual(mutants.outcome(1), "KILLED")
        self.assertFalse(mutants.is_killed(mutants.outcome(None)))
        self.assertTrue(mutants.is_killed(mutants.outcome(1)))


if __name__ == "__main__":
    unittest.main()
