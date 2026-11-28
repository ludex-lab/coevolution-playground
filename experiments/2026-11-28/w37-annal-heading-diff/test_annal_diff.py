"""Tests for annal_diff (stdlib unittest). Run: python3 -B -m unittest test_annal_diff"""

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import annal_diff
import mutants
from annal_diff import Deny, Entry

HERE = os.path.dirname(os.path.abspath(__file__))
VALID = os.path.join(HERE, "fixtures", "valid")
BAD = os.path.join(HERE, "fixtures", "bad")
STDERR_RE = re.compile(r"^DENY [a-z_]+: ")

BAD_CODES = {
    "bad_bom": "bad_bom",
    "bad_cr": "bad_cr",
    "bad_encoding": "bad_encoding",
    "bad_heading_empty": "bad_heading",
    "bad_heading_no_space": "bad_heading",
    "bad_heading_trailing_space": "bad_heading",
    "bad_id": "bad_id",
    "bad_level_h1_mid": "bad_level",
    "bad_level_h3": "bad_level",
    "bad_pins": "bad_pins",
    "bad_tab": "bad_tab",
    "duplicate_heading": "duplicate_heading",
    "duplicate_id": "duplicate_id",
    "missing_tree": "missing_tree",
    "no_pins": "unpinned",
    "not_markdown": "not_markdown",
    "pin_mismatch": "pin_mismatch",
    "pin_missing": "pin_missing",
    "stray_text": "stray_text",
    "unpinned_file": "unpinned",
}


def blobs(files):
    return {rel: text.encode("utf-8") if isinstance(text, str) else text for rel, text in files.items()}


def compare(before, after):
    return annal_diff.compare_blobs(blobs(before), blobs(after))


def classes(result):
    return {k: v for k, v in result["counts"].items() if k != "unchanged" and v}


def write_case(root, before, after, pins=True):
    """Write before/after trees under root plus a pins.txt for every file."""
    lines = []
    for side, files in (("before", before), ("after", after)):
        os.makedirs(os.path.join(root, side), exist_ok=True)
        for rel, data in files.items():
            data = data.encode("utf-8") if isinstance(data, str) else data
            path = os.path.join(root, side, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(data)
            lines.append("%s  %d  %s/%s" % (hashlib.sha256(data).hexdigest(), len(data), side, rel))
    if pins:
        with open(os.path.join(root, "pins.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(sorted(lines)) + ("\n" if lines else ""))
    return ["--before", os.path.join(root, "before"), "--after", os.path.join(root, "after"),
            "--pins", os.path.join(root, "pins.txt")]


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    rc = annal_diff.main(argv, out, err)
    return rc, out.getvalue(), err.getvalue()


class DenyShape:
    def assertDeny(self, code, argv):
        rc, out, err = run_main(argv)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertRegex(err, STDERR_RE)
        self.assertTrue(err.startswith("DENY %s: " % code), err)

    def assertDenyCode(self, code, fn, *args):
        with self.assertRaises(Deny) as ctx:
            fn(*args)
        self.assertEqual(ctx.exception.code, code)


class TestMatching(unittest.TestCase):
    def test_a_planted_rename_without_id_is_renamed(self):
        r = compare({"d.md": "# T\n## Harbour walk\nbody-a\n"},
                    {"d.md": "# T\n## Morning harbour walk\nbody-a\n"})
        self.assertEqual(classes(r), {"renamed": 1})
        row = r["changes"][0]
        self.assertEqual((row["old_heading"], row["new_heading"], row["matched_by"]),
                         ("Harbour walk", "Morning harbour walk", "body"))

    def test_a_planted_rename_with_id_is_renamed(self):
        r = compare({"d.md": "## Harbour walk\nid: morning-note\nbody-a\n## Other\nbody-a\n"},
                    {"d.md": "## Morning harbour walk\nid: morning-note\nbody-a\n## Other\nbody-a\n"})
        self.assertEqual(classes(r), {"renamed": 1})
        self.assertEqual(r["changes"][0]["matched_by"], "id")
        self.assertEqual(r["counts"]["unchanged"], 1)

    def test_b_same_heading_different_body_is_edited(self):
        r = compare({"d.md": "## supper\nold\n"}, {"d.md": "## supper\nnew\n"})
        self.assertEqual(classes(r), {"edited": 1})
        self.assertFalse(r["changes"][0]["also_renamed"])

    def test_b_same_id_same_heading_different_body_is_edited(self):
        r = compare({"d.md": "## supper\nid: supper\nold\n"}, {"d.md": "## supper\nid: supper\nnew\n"})
        self.assertEqual(classes(r), {"edited": 1})
        self.assertEqual(r["changes"][0]["matched_by"], "id")

    def test_c_new_heading_new_body_is_added(self):
        r = compare({"d.md": "## A\nx\n"}, {"d.md": "## A\nx\n## visitor\nhello\n"})
        self.assertEqual(classes(r), {"added": 1})

    def test_d_disappeared_heading_is_removed(self):
        r = compare({"d.md": "## A\nx\n## leftover\ngone\n"}, {"d.md": "## A\nx\n"})
        self.assertEqual(classes(r), {"removed": 1})

    def test_e_two_unrelated_pairs_are_not_renamed(self):
        r = compare({"d.md": "## A\nbody-x\n## B\nbody-y\n"}, {"d.md": "## C\nbody-z\n## D\nbody-w\n"})
        self.assertEqual(classes(r), {"added": 2, "removed": 2})
        self.assertEqual(r["info"], [])

    def test_f_two_plus_two_shared_body_is_ambiguous_not_paired(self):
        r = compare({"d.md": "## A\nshared\n## B\nshared\n"}, {"d.md": "## C\nshared\n## D\nshared\n"})
        self.assertEqual(classes(r), {"added": 2, "removed": 2})
        self.assertEqual([d["code"] for d in r["info"]], ["ambiguous_rename"])
        self.assertEqual(len(r["info"][0]["old"]), 2)
        self.assertEqual(len(r["info"][0]["new"]), 2)

    def test_f_one_old_two_new_shared_body_is_ambiguous_not_paired(self):
        r = compare({"d.md": "## A\nshared\n"}, {"d.md": "## C\nshared\n## D\nshared\n"})
        self.assertEqual(classes(r), {"added": 2, "removed": 1})
        self.assertEqual([d["code"] for d in r["info"]], ["ambiguous_rename"])

    def test_f_two_old_one_new_shared_body_is_ambiguous_not_paired(self):
        r = compare({"d.md": "## A\nshared\n## B\nshared\n"}, {"d.md": "## C\nshared\n"})
        self.assertEqual(classes(r), {"added": 1, "removed": 2})
        self.assertEqual(len(r["info"]), 1)

    def test_g_two_unique_body_pairs_are_two_renamed(self):
        r = compare({"d.md": "# T\n## A\nbody-x\n## B\nbody-y\n"},
                    {"d.md": "# T\n## C\nbody-x\n## D\nbody-y\n"})
        self.assertEqual(classes(r), {"renamed": 2})
        pairs = sorted((c["old_heading"], c["new_heading"]) for c in r["changes"])
        self.assertEqual(pairs, [("A", "C"), ("B", "D")])

    def test_g_unique_pair_next_to_ambiguous_group(self):
        r = compare({"d.md": "## A\nbody-x\n## B\nshared\n## E\nshared\n"},
                    {"d.md": "## C\nbody-x\n## D\nshared\n## F\nshared\n"})
        self.assertEqual(classes(r), {"renamed": 1, "added": 2, "removed": 2})
        self.assertEqual(len(r["info"]), 1)

    def test_h_same_id_heading_and_body_change_is_edited_also_renamed(self):
        r = compare({"d.md": "## old-title\nid: k\nbody-1\n"}, {"d.md": "## new-title\nid: k\nbody-2\n"})
        self.assertEqual(classes(r), {"edited": 1})
        row = r["changes"][0]
        self.assertTrue(row["also_renamed"])
        self.assertEqual((row["old_heading"], row["new_heading"]), ("old-title", "new-title"))

    def test_i_path_heading_body_change_without_id_is_removed_added(self):
        r = compare({"a.md": "## Note\nbody-1\n"}, {"b.md": "## Note retitled\nbody-2\n"})
        self.assertEqual(classes(r), {"added": 1, "removed": 1})

    def test_j_stable_id_new_path_same_bytes_is_moved(self):
        r = compare({"a.md": "## Note\nid: note\nbody\n"}, {"b.md": "## Note\nid: note\nbody\n"})
        self.assertEqual(classes(r), {"moved": 1})
        row = r["changes"][0]
        self.assertEqual((row["old_path"], row["new_path"]), ("a.md", "b.md"))
        self.assertFalse(row["also_moved"])

    def test_j_id_match_is_snapshot_wide_with_rename(self):
        r = compare({"a.md": "## Note\nid: note\nbody\n"}, {"b.md": "## Note two\nid: note\nbody\n"})
        self.assertEqual(classes(r), {"renamed": 1})
        self.assertTrue(r["changes"][0]["also_moved"])

    def test_j_unique_body_same_heading_new_path_without_id_is_moved(self):
        r = compare({"a.md": "## Note\nbody\n"}, {"b.md": "## Note\nbody\n"})
        self.assertEqual(classes(r), {"moved": 1})
        self.assertEqual(r["changes"][0]["matched_by"], "body")

    def test_two_distinct_ids_with_same_body_are_not_paired(self):
        r = compare({"d.md": "## A\nid: one\nbody\n"}, {"d.md": "## B\nid: two\nbody\n"})
        self.assertEqual(classes(r), {"added": 1, "removed": 1})

    def test_two_distinct_ids_same_path_heading_are_not_paired(self):
        r = compare({"d.md": "## A\nid: one\nbody\n"}, {"d.md": "## A\nid: two\nother\n"})
        self.assertEqual(classes(r), {"added": 1, "removed": 1})

    def test_empty_bodies_are_never_paired_by_body(self):
        r = compare({"d.md": "## A\n"}, {"d.md": "## B\n"})
        self.assertEqual(classes(r), {"added": 1, "removed": 1})
        self.assertEqual(r["info"], [])

    def test_unchanged_is_omitted_and_counted(self):
        r = compare({"d.md": "## A\nx\n## B\ny\n"}, {"d.md": "## A\nx\n## B\ny\n"})
        self.assertEqual(r["changes"], [])
        self.assertEqual(r["counts"]["unchanged"], 2)

    def test_duplicate_headings_with_distinct_ids_match_by_id(self):
        r = compare({"d.md": "## Note\nid: a\none\n## Note\nid: b\ntwo\n"},
                    {"d.md": "## Note\nid: a\none\n## Note\nid: b\ntwo changed\n"})
        self.assertEqual(classes(r), {"edited": 1})
        self.assertEqual(r["changes"][0]["id"], "b")

    def test_id_line_added_alone_is_unchanged(self):
        r = compare({"d.md": "## A\nx\n"}, {"d.md": "## A\nid: a\nx\n"})
        self.assertEqual(r["changes"], [])

    def test_blank_lines_around_body_do_not_count(self):
        r = compare({"d.md": "## A\n\nx\n\n"}, {"d.md": "## A\nx"})
        self.assertEqual(r["changes"], [])

    def test_order_independent_and_deterministic(self):
        before = {"b.md": "## B\ny\n", "a.md": "## A\nx\n"}
        after = {"a.md": "## A2\nx\n", "b.md": "## B2\ny\n"}
        r1 = compare(before, after)
        r2 = compare(dict(reversed(list(before.items()))), dict(reversed(list(after.items()))))
        self.assertEqual(json.dumps(r1, sort_keys=True), json.dumps(r2, sort_keys=True))

    def test_rows_carry_path_and_file_digest(self):
        data = "## A\nx\n"
        r = compare({"d.md": "## A0\nx\n"}, {"d.md": data})
        row = r["changes"][0]
        self.assertEqual(row["new_file_sha256"], hashlib.sha256(data.encode()).hexdigest())
        self.assertEqual(row["new_path"], "d.md")


class TestGrammar(DenyShape, unittest.TestCase):
    def deny(self, code, after, before=None):
        self.assertDenyCode(code, compare, before or {"ok.md": "## Ok\nx\n"}, after)

    def test_k_duplicate_heading_without_ids(self):
        self.deny("duplicate_heading", {"d.md": "## Note\na\n## Note\nb\n"})

    def test_k_duplicate_heading_with_one_id_only(self):
        self.deny("duplicate_heading", {"d.md": "## Note\nid: a\na\n## Note\nb\n"})

    def test_k_same_heading_in_two_files_is_fine(self):
        r = compare({"a.md": "## Note\nx\n", "b.md": "## Note\ny\n"},
                    {"a.md": "## Note\nx\n", "b.md": "## Note\ny\n"})
        self.assertEqual(r["counts"]["unchanged"], 2)

    def test_k_duplicate_id_across_files(self):
        self.deny("duplicate_id", {"a.md": "## A\nid: same\nx\n", "b.md": "## B\nid: same\ny\n"})

    def test_k_h3_entry(self):
        self.deny("bad_level", {"d.md": "# T\n## A\nx\n### Deep\ny\n"})

    def test_k_h1_after_first_line(self):
        self.deny("bad_level", {"d.md": "## A\nx\n# Not a title here\n"})

    def test_k_hash_text_in_body(self):
        self.deny("bad_level", {"d.md": "## A\n#tag line\n"})

    def test_k_trailing_space(self):
        self.deny("bad_heading", {"d.md": "## Note \nx\n"})

    def test_k_empty_heading(self):
        self.deny("bad_heading", {"d.md": "## \nx\n"})

    def test_k_two_spaces_or_no_space(self):
        self.deny("bad_heading", {"d.md": "##  Note\nx\n"})
        self.deny("bad_heading", {"d.md": "##Note\nx\n"})

    def test_bad_title(self):
        self.deny("bad_title", {"d.md": "#  T\n## A\nx\n"})

    def test_bad_id_forms(self):
        for line in ("id: Bad", "id: two words", "id:x", "id: a--b", "id: -a", "id: "):
            self.deny("bad_id", {"d.md": "## A\n%s\nx\n" % line})

    def test_stray_text_before_first_entry(self):
        self.deny("stray_text", {"d.md": "# T\nloose\n## A\nx\n"})

    def test_bytes_level_checks(self):
        self.deny("bad_bom", {"d.md": b"\xef\xbb\xbf## A\nx\n"})
        self.deny("bad_encoding", {"d.md": b"## A\n\xff\n"})
        self.deny("bad_cr", {"d.md": "## A\r\nx\r\n"})
        self.deny("bad_tab", {"d.md": "## A\n\tx\n"})

    def test_type_checks_before_lookup(self):
        good = Entry("d.md", "A", None, "x", "0" * 64)
        self.assertDenyCode("bad_type", annal_diff.diff, [good._replace(ident=["k"])], [good])
        self.assertDenyCode("bad_type", annal_diff.diff, [good], [good._replace(ident={"k": 1})])
        self.assertDenyCode("bad_type", annal_diff.diff, [("d.md", "A", None, "x", "0")], [good])
        self.assertDenyCode("bad_type", annal_diff.diff, [good._replace(body=None)], [good])
        self.assertDenyCode("bad_type", annal_diff.diff, (good,), [good])
        self.assertDenyCode("bad_type", annal_diff.parse_snapshot, {"d.md": "text not bytes"}, "after")
        self.assertDenyCode("bad_type", annal_diff.parse_snapshot, [("d.md", b"")], "after")


class TestCaps(DenyShape, unittest.TestCase):
    def test_l_file_size_at_cap_and_over(self):
        head = b"## A\n"
        at_cap = head + b"x" * 3999 + b"\n" + b"\n" * (annal_diff.MAX_FILE_BYTES - len(head) - 4000)
        self.assertEqual(len(at_cap), annal_diff.MAX_FILE_BYTES)
        compare({"d.md": at_cap}, {"d.md": at_cap})
        self.assertDenyCode("too_large", compare, {"d.md": at_cap + b"\n"}, {"d.md": at_cap})

    def test_l_file_size_over_cap_on_disk(self):
        with tempfile.TemporaryDirectory() as root:
            argv = write_case(root, {"d.md": "## A\nx\n"}, {"d.md": "## A\n" + "\n" * annal_diff.MAX_FILE_BYTES})
            self.assertDeny("too_large", argv)

    def test_l_entries_at_cap_and_over(self):
        at_cap = "".join("## E%d\nb%d\n" % (n, n) for n in range(annal_diff.MAX_ENTRIES_PER_FILE))
        r = compare({"d.md": at_cap}, {"d.md": at_cap})
        self.assertEqual(r["counts"]["unchanged"], annal_diff.MAX_ENTRIES_PER_FILE)
        self.assertDenyCode("too_many_entries", compare, {"d.md": at_cap + "## Extra\nz\n"}, {"d.md": at_cap})

    def test_l_heading_and_body_length(self):
        cap = annal_diff.MAX_TEXT_CHARS
        compare({"d.md": "## %s\n%s\n" % ("h" * cap, "b" * cap)}, {"d.md": "## A\nx\n"})
        self.assertDenyCode("too_long", compare, {"d.md": "## %s\nx\n" % ("h" * (cap + 1))}, {"d.md": "## A\nx\n"})
        self.assertDenyCode("too_long", compare, {"d.md": "## A\n%s\n" % ("b" * (cap + 1))}, {"d.md": "## A\nx\n"})

    def test_l_files_per_tree_at_cap_and_over(self):
        cap = annal_diff.MAX_FILES_PER_TREE
        files = {"f%03d.md" % n: "## E\nx%d\n" % n for n in range(cap)}
        with tempfile.TemporaryDirectory() as root:
            rc, out, err = run_main(write_case(root, files, {"a.md": "## A\nx\n"}))
            self.assertEqual((rc, err), (0, ""))
        files["zz.md"] = "## E\nlast\n"
        with tempfile.TemporaryDirectory() as root:
            self.assertDeny("too_many_files", write_case(root, files, {"a.md": "## A\nx\n"}))

    def test_l_directory_depth_at_cap_and_over(self):
        at_cap = "/".join(["d"] * annal_diff.MAX_DEPTH) + "/n.md"
        with tempfile.TemporaryDirectory() as root:
            rc, out, err = run_main(write_case(root, {at_cap: "## A\nx\n"}, {"a.md": "## A\nx\n"}))
            self.assertEqual((rc, err), (0, ""))
            self.assertIn("moved", out)
        with tempfile.TemporaryDirectory() as root:
            self.assertDeny("too_deep", write_case(root, {"d/" + at_cap: "## A\nx\n"}, {"a.md": "## A\nx\n"}))

    def test_deep_nesting_is_bounded_in_process(self):
        with tempfile.TemporaryDirectory() as root:
            argv = write_case(root, {"a.md": "## A\nx\n"}, {"a.md": "## A\nx\n"})
            deep = os.path.join(root, "before", *(["n"] * 60))
            os.makedirs(deep)
            with open(os.path.join(deep, "z.md"), "w", encoding="utf-8") as fh:
                fh.write("## Z\nz\n")
            try:
                self.assertDeny("too_deep", argv)
            except RecursionError:
                self.fail("deep tree raised RecursionError")


class TestCli(DenyShape, unittest.TestCase):
    def test_demo_matches_committed_changes_md(self):
        import demo
        rc, out, err = run_main(demo.demo_argv())
        self.assertEqual((rc, err), (0, ""))
        with open(os.path.join(HERE, "changes.md"), encoding="utf-8") as fh:
            self.assertEqual(out, fh.read())

    def test_demo_counts(self):
        import demo
        rc, out, err = run_main(demo.demo_argv(["--json"]))
        self.assertEqual(rc, 0)
        doc = json.loads(out)
        self.assertEqual(doc["counts"], {"renamed": 3, "moved": 1, "edited": 2, "added": 3,
                                         "removed": 3, "unchanged": 1})
        self.assertEqual([d["code"] for d in doc["info"]], ["ambiguous_rename"])
        self.assertEqual(doc["on_expiry"], "DENY")

    def test_missing_tree(self):
        with tempfile.TemporaryDirectory() as root:
            argv = write_case(root, {"a.md": "## A\nx\n"}, {"a.md": "## A\nx\n"})
            argv[3] = os.path.join(root, "absent")
            self.assertDeny("missing_tree", argv)
        self.assertDeny("missing_tree", ["--after", "x", "--pins", "p"])

    def test_unpinned_without_pins_flag(self):
        with tempfile.TemporaryDirectory() as root:
            argv = write_case(root, {"a.md": "## A\nx\n"}, {"a.md": "## A\nx\n"})
            self.assertDeny("unpinned", argv[:4])

    def test_unpinned_file_and_pin_missing(self):
        with tempfile.TemporaryDirectory() as root:
            argv = write_case(root, {"a.md": "## A\nx\n"}, {"a.md": "## A\nx\n"})
            with open(os.path.join(root, "after", "b.md"), "w", encoding="utf-8") as fh:
                fh.write("## B\ny\n")
            self.assertDeny("unpinned", argv)
            os.remove(os.path.join(root, "after", "b.md"))
            os.remove(os.path.join(root, "after", "a.md"))
            with open(os.path.join(root, "after", "c.md"), "w", encoding="utf-8") as fh:
                fh.write("## C\n")
            self.assertDeny("unpinned", argv)

    def test_pin_missing(self):
        with tempfile.TemporaryDirectory() as root:
            argv = write_case(root, {"a.md": "## A\nx\n"}, {"a.md": "## A\nx\n", "b.md": "## B\ny\n"})
            os.remove(os.path.join(root, "after", "b.md"))
            self.assertDeny("pin_missing", argv)

    def test_pin_mismatch_same_size(self):
        with tempfile.TemporaryDirectory() as root:
            argv = write_case(root, {"a.md": "## A\nx\n"}, {"a.md": "## A\nx\n"})
            with open(os.path.join(root, "after", "a.md"), "w", encoding="utf-8") as fh:
                fh.write("## A\ny\n")
            self.assertDeny("pin_mismatch", argv)

    def test_bad_pins_lines(self):
        for text in ("nonsense\n", "%s  7  before/a.md\n%s  7  before/a.md\n" % ("a" * 64, "a" * 64),
                     "%s  07  before/a.md\n" % ("a" * 64), "%s  7  middle/a.md\n" % ("a" * 64),
                     "%s  7  before/a.md\n" % ("A" * 64), "\n\n"):
            with tempfile.TemporaryDirectory() as root:
                argv = write_case(root, {"a.md": "## A\nx\n"}, {"a.md": "## A\nx\n"})
                with open(os.path.join(root, "pins.txt"), "w", encoding="utf-8") as fh:
                    fh.write(text)
                self.assertDeny("bad_pins", argv)

    def test_not_markdown_bad_path_and_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertDeny("not_markdown", write_case(root, {"a.md": "## A\n"}, {"a.txt": "x"}))
        with tempfile.TemporaryDirectory() as root:
            self.assertDeny("bad_path", write_case(root, {"a.md": "## A\n"}, {"a b.md": "## A\n"}))
        with tempfile.TemporaryDirectory() as root:
            argv = write_case(root, {"a.md": "## A\n"}, {"a.md": "## A\n"})
            os.symlink(os.path.join(root, "after", "a.md"), os.path.join(root, "after", "l.md"))
            self.assertDeny("bad_file", argv)

    def test_bad_args(self):
        self.assertDeny("bad_args", ["--before", "a", "--after", "b", "--pins", "p", "--color"])
        self.assertDeny("bad_args", ["--before", "a", "--before", "b"])
        self.assertDeny("bad_args", ["--before"])

    def test_on_expiry_is_deny_and_in_set(self):
        self.assertEqual(annal_diff.ON_EXPIRY, "DENY")
        self.assertIn(annal_diff.ON_EXPIRY, annal_diff.ON_EXPIRY_SET)
        self.assertEqual(set(annal_diff.ON_EXPIRY_SET), {"DENY", "SAFE_FALLBACK", "ESCALATE", "HOLD"})


class TestOnDisk(unittest.TestCase):
    """Child-process checks of the file on disk (shape only; kills come from in-process tests)."""

    def run_cli(self, args):
        return subprocess.run([sys.executable, "-B", os.path.join(HERE, "annal_diff.py")] + args,
                              capture_output=True, text=True, cwd=HERE, timeout=60)

    def test_demo_twice_identical(self):
        outs = [subprocess.run([sys.executable, "-B", os.path.join(HERE, "demo.py")],
                               capture_output=True, text=True, cwd=HERE, timeout=60) for _ in range(2)]
        self.assertEqual([p.returncode for p in outs], [0, 0])
        self.assertEqual(hashlib.sha256(outs[0].stdout.encode()).hexdigest(),
                         hashlib.sha256(outs[1].stdout.encode()).hexdigest())
        self.assertNotEqual(outs[0].stdout, "")

    def test_bad_fixtures(self):
        names = sorted(n for n in os.listdir(BAD) if os.path.isdir(os.path.join(BAD, n)))
        self.assertEqual(names, sorted(BAD_CODES))
        for name in names:
            case = os.path.join(BAD, name)
            args = ["--before", os.path.join(case, "before"), "--after", os.path.join(case, "after")]
            if os.path.isfile(os.path.join(case, "pins.txt")):
                args += ["--pins", os.path.join(case, "pins.txt")]
            proc = self.run_cli(args)
            with self.subTest(name=name):
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")
                self.assertEqual(len(proc.stderr.splitlines()), 1)
                self.assertRegex(proc.stderr, STDERR_RE)
                self.assertTrue(proc.stderr.startswith("DENY %s: " % BAD_CODES[name]), proc.stderr)


class TestMutantRunner(unittest.TestCase):
    def test_timeout_object(self):
        self.assertEqual(mutants.TIMEOUT, {"seconds": 300, "on_expiry": "DENY"})
        self.assertIn(mutants.TIMEOUT["on_expiry"], annal_diff.ON_EXPIRY_SET)

    def test_classify_timeout_is_not_killed(self):
        verdict = mutants.classify(None, "", True)
        self.assertEqual(verdict, "TIMEOUT")
        self.assertFalse(mutants.is_killed(verdict))

    def test_forced_real_timeout_is_not_killed(self):
        rc, out, timed_out = mutants.run_source("import time\ntime.sleep(30)\n", "annal_diff", timeout=1)
        self.assertTrue(timed_out)
        verdict = mutants.classify(rc, out, timed_out)
        self.assertEqual(verdict, "TIMEOUT")
        self.assertFalse(mutants.is_killed(verdict))

    def test_forced_crash_is_crash_not_killed(self):
        rc, out, timed_out = mutants.run_source("raise RuntimeError('forced crash')\n", "annal_diff", timeout=60)
        verdict = mutants.classify(rc, out, timed_out)
        self.assertEqual(verdict, "CRASH")
        self.assertFalse(mutants.is_killed(verdict))

    def test_load_failure_is_crash_not_killed(self):
        self.assertEqual(mutants.classify(mutants.LOAD_FAILED, "", False), "CRASH")
        rc, out, timed_out = mutants.run_source("def broken(:\n", "annal_diff", timeout=60)
        self.assertEqual(rc, mutants.LOAD_FAILED)
        self.assertEqual(mutants.classify(rc, out, timed_out), "CRASH")

    def test_classify_failures_errors_and_pass(self):
        self.assertEqual(mutants.classify(1, '{"failures": 2, "errors": 0}\n', False), "KILLED-behaviour")
        self.assertEqual(mutants.classify(1, '{"failures": 0, "errors": 3}\n', False), "CRASH")
        self.assertEqual(mutants.classify(0, '{"failures": 0, "errors": 0}\n', False), "SURVIVED")
        self.assertEqual(mutants.classify(1, "not json\n", False), "CRASH")
        self.assertEqual(mutants.classify(1, "[1]\n", False), "CRASH")

    def test_tally_counts_only_behaviour_kills(self):
        counts = mutants.tally(["KILLED-behaviour", "CRASH", "TIMEOUT", "SURVIVED"])
        self.assertEqual(counts, {"KILLED-behaviour": 1, "CRASH": 1, "TIMEOUT": 1, "SURVIVED": 1})
        self.assertEqual(sum(mutants.is_killed(v) for v in ("CRASH", "TIMEOUT", "SURVIVED")), 0)

    def test_required_mutants_present(self):
        names = [m[0] for m in mutants.MUTANTS]
        for need in ("pair_ambiguous_leftovers", "ignore_level", "timeout_counts_as_kill",
                     "leftover_singleton_only"):
            self.assertIn(need, names)
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
