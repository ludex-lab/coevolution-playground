"""Tests for prerelease_gate. Run: python3 -B -m unittest"""

import hashlib
import io
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import prerelease_gate as pg

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
CHAIN = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
         "1.0.0-rc.1", "1.0.0"]
S, N = "SATISFIES", "DOES_NOT_SATISFY"

# Expected error code for every bad fixture.
BAD_CODES = {
    'bad_bad_expected.json': 'bad_expected',
    'bad_bidi_override.json': 'bad_text',
    'bad_bom.json': 'not_json',
    'bad_bool_version.json': 'wrong_type',
    'bad_candidate_double_dot_build.json': 'empty_identifier',
    'bad_candidate_double_dot_pre.json': 'empty_identifier',
    'bad_candidate_empty.json': 'bad_core',
    'bad_candidate_empty_build.json': 'empty_identifier',
    'bad_candidate_empty_pre.json': 'empty_identifier',
    'bad_candidate_four_parts.json': 'bad_core',
    'bad_candidate_fullwidth_digits.json': 'bad_core',
    'bad_candidate_greek_pre.json': 'bad_identifier',
    'bad_candidate_leading_space.json': 'bad_core',
    'bad_candidate_leading_zero_major.json': 'leading_zero',
    'bad_candidate_leading_zero_minor.json': 'leading_zero',
    'bad_candidate_leading_zero_patch.json': 'leading_zero',
    'bad_candidate_leading_zero_pre.json': 'leading_zero',
    'bad_candidate_negative.json': 'bad_core',
    'bad_candidate_null_candidate.json': 'wrong_type',
    'bad_candidate_number_candidate.json': 'wrong_type',
    'bad_candidate_plus_in_build.json': 'bad_identifier',
    'bad_candidate_pre_after_build_empty.json': 'empty_identifier',
    'bad_candidate_too_long.json': 'too_long',
    'bad_candidate_trailing_space.json': 'bad_core',
    'bad_candidate_two_parts.json': 'bad_core',
    'bad_candidate_underscore_pre.json': 'bad_identifier',
    'bad_candidate_v_prefix.json': 'bad_core',
    'bad_candidate_zero_width_pre.json': 'bad_identifier',
    'bad_control_char.json': 'bad_text',
    'bad_deep_nesting.json': 'not_json',
    'bad_duplicate_id.json': 'duplicate_id',
    'bad_duplicate_key.json': 'duplicate_key',
    'bad_edge_space_label.json': 'bad_text',
    'bad_empty_file.json': 'not_json',
    'bad_float_version.json': 'wrong_type',
    'bad_giant_int_digits.json': 'not_json',
    'bad_huge_int_version.json': 'bad_version',
    'bad_infinity.json': 'bad_number',
    'bad_invalid_utf8.json': 'bad_encoding',
    'bad_lone_surrogate.json': 'bad_text',
    'bad_missing_pairs.json': 'missing_key',
    'bad_nan.json': 'bad_number',
    'bad_no_pairs.json': 'too_many',
    'bad_not_json.json': 'not_json',
    'bad_one_bad_among_good.json': 'leading_zero',
    'bad_pair_missing_expected.json': 'missing_key',
    'bad_pair_unknown_key.json': 'unknown_key',
    'bad_requirement_build.json': 'bad_requirement',
    'bad_requirement_caret.json': 'bad_requirement',
    'bad_requirement_greater_than.json': 'bad_requirement',
    'bad_requirement_leading_zero.json': 'leading_zero',
    'bad_requirement_less_equal.json': 'bad_requirement',
    'bad_requirement_no_operator.json': 'bad_requirement',
    'bad_requirement_no_space.json': 'bad_requirement',
    'bad_requirement_pre_release.json': 'bad_requirement',
    'bad_requirement_short_version.json': 'bad_core',
    'bad_requirement_tilde.json': 'bad_requirement',
    'bad_requirement_two_spaces.json': 'bad_core',
    'bad_requirement_union.json': 'bad_core',
    'bad_too_large.json': 'too_large',
    'bad_too_many_pairs.json': 'too_many',
    'bad_top_level_list.json': 'wrong_type',
    'bad_unknown_key.json': 'unknown_key',
    'bad_wrong_fixture_version.json': 'bad_version',
}


def V(text):
    return pg.parse_version(text)


def R(text):
    return pg.parse_requirement(text)


def arms(cand, req):
    c, r = V(cand), R(req)
    return pg.stable_arm(c, r), pg.precedence_arm(c, r), pg.weak_arm(c, r)


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = pg.main(["prerelease_gate.py"] + args)
    return code, out.getvalue(), err.getvalue()


def write_fixture(obj):
    tmp = tempfile.mkdtemp(prefix="w31-test-")
    path = os.path.join(tmp, "f.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    return tmp, path


class PlannedCaseTests(unittest.TestCase):
    """Tests (a) to (i) from the pack, with the range-semantics fix applied."""

    def test_a_normal_version_satisfies_both_operators(self):
        for req in (">= 1.0.0", "== 1.0.0"):
            self.assertEqual(arms("1.0.0", req)[0]["verdict"], S, req)

    def test_b_pre_releases_of_the_same_core_satisfy_neither(self):
        for cand in ("1.0.0-alpha", "1.0.0-rc.1"):
            for req in (">= 1.0.0", "== 1.0.0"):
                stable = arms(cand, req)[0]
                self.assertEqual(stable, {"verdict": N, "reason": "pre-release < 1.0.0 (spec §11)"}, (cand, req))

    def test_c_alpha_has_lower_precedence_than_the_normal_version(self):
        self.assertEqual(pg.compare(V("1.0.0-alpha"), V("1.0.0")), -1)
        self.assertEqual(pg.compare(V("1.0.0"), V("1.0.0-alpha")), 1)

    def test_d_weak_arm_wrongly_accepts_rc1_and_the_gate_fails_it(self):
        stable, _, weak = arms("1.0.0-rc.1", ">= 1.0.0")
        self.assertEqual((weak["verdict"], stable["verdict"]), (S, N))
        result = pg.run(pg.load_fixture(os.path.join(FIX, "main.json")))
        self.assertEqual(result["weak_gate"], "FAIL")
        self.assertIn("- 1.0.0-rc.1   >= 1.0.0 wrongly SATISFIES  — gate FAIL", pg.report(result))

    def test_e_leading_zero_major_is_deny(self):
        code, out, err = run_cli([os.path.join(FIX, "bad_candidate_leading_zero_major.json")])
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.startswith("ERROR leading_zero: "))

    def test_f_missing_fixture_is_deny(self):
        code, out, err = run_cli([os.path.join(FIX, "no_such_fixture.json")])
        self.assertEqual((code, out, len(err.splitlines())), (2, "", 1))
        self.assertTrue(err.startswith("ERROR unreadable: "))

    def test_g_higher_core_pre_releases_are_excluded_by_policy(self):
        for cand in ("1.0.1-rc.1", "2.0.0-alpha"):
            stable, precedence, weak = arms(cand, ">= 1.0.0")
            self.assertEqual(stable, {"verdict": N, "reason": "pre-release excluded by stable range (policy)"}, cand)
            self.assertEqual(precedence["verdict"], S, cand)
            self.assertEqual(weak["verdict"], S, cand)

    def test_g_precedence_arm_is_never_called_stable(self):
        text = pg.report(pg.run(pg.load_fixture(os.path.join(FIX, "main.json"))))
        self.assertIn("precedence_arm (pure spec §11 precedence; shown, never called stable):", text)
        self.assertIn("- 1.0.1-rc.1   >= 1.0.0 SATISFIES  by precedence", text)
        self.assertEqual(arms("1.0.1-rc.1", ">= 1.0.0")[1]["reason"], "by precedence (spec §11)")

    def test_h_spec_chain_all_64_ordered_pairs(self):
        versions = [V(t) for t in CHAIN]
        checked = 0
        for i, j in itertools.product(range(8), range(8)):
            expected = (i > j) - (i < j)
            self.assertEqual(pg.compare(versions[i], versions[j]), expected, (CHAIN[i], CHAIN[j]))
            checked += 1
        self.assertEqual(checked, 64)

    def test_h_sorting_recovers_the_chain(self):
        texts = []
        for perm in itertools.islice(itertools.permutations(CHAIN), 0, 40320, 997):
            got = [pg.render_version(v) for v in pg.sort_versions([V(t) for t in perm])]
            self.assertEqual(got, CHAIN)
            texts.append(perm)
        self.assertGreaterEqual(len(texts), 40)
        reversed_chain = [pg.render_version(v) for v in pg.sort_versions([V(t) for t in reversed(CHAIN)])]
        self.assertEqual(reversed_chain, CHAIN)

    def test_h_numeric_identifiers_compare_numerically(self):
        self.assertEqual(pg.compare(V("1.0.0-beta.2"), V("1.0.0-beta.11")), -1)
        self.assertEqual(pg.compare(V("1.0.0-alpha.1"), V("1.0.0-alpha.beta")), -1)
        self.assertEqual(pg.compare(V("1.0.0-alpha"), V("1.0.0-alpha.1")), -1)

    def test_i_leading_zero_numeric_pre_release_is_deny_but_alphanumeric_is_valid(self):
        with self.assertRaises(pg.GateError) as cm:
            V("1.0.0-01")
        self.assertEqual(cm.exception.code, "leading_zero")
        self.assertEqual(V("1.0.0-01a")["pre"], ("01a",))
        self.assertEqual(V("1.0.0-0")["pre"], (0,))


class ParserTests(unittest.TestCase):

    def test_named_malformed_versions_are_deny(self):
        for text, code in (("01.0.0", "leading_zero"), ("1.0", "bad_core"), ("", "bad_core"),
                           ("1.0.0-", "empty_identifier"), ("1.0.0-alpha..1", "empty_identifier"),
                           ("1.0.0-01", "leading_zero"), ("1.0.0+", "empty_identifier"), ("v1.0.0", "bad_core")):
            with self.assertRaises(pg.GateError, msg=text) as cm:
                V(text)
            self.assertEqual(cm.exception.code, code, text)

    def test_named_valid_versions(self):
        self.assertEqual(V("1.0.0-01a"), {"major": 1, "minor": 0, "patch": 0, "pre": ("01a",), "build": ()})
        self.assertEqual(V("1.0.0-0")["pre"], (0,))
        self.assertEqual(V("1.0.0+001")["build"], ("001",))
        self.assertEqual(V("1.0.0-alpha+001")["pre"], ("alpha",))
        self.assertEqual(V("1.0.0-x-y.--")["pre"], ("x-y", "--"))
        self.assertEqual(V("10.20.30")["major"], 10)

    def test_render_round_trip(self):
        for text in CHAIN + ["1.0.0+build.5", "1.0.0-0+001", "0.0.0"]:
            self.assertEqual(pg.render_version(V(text)), text)

    def test_requirement_grammar(self):
        self.assertEqual(R(">= 1.0.0")["op"], ">=")
        self.assertEqual(R("== 2.3.4")["version"]["patch"], 4)
        self.assertEqual(pg.OPERATORS, (">=", "=="))
        for text in ("> 1.0.0", ">=1.0.0", ">= 1.0.0-rc.1", "== 1.0.0+b", "1.0.0", "~1.0.0"):
            with self.assertRaises(pg.GateError, msg=text) as cm:
                R(text)
            self.assertEqual(cm.exception.code, "bad_requirement", text)

    def test_version_length_cap(self):
        limit = pg.CAPS["version_chars"]["limit"]
        V("1.0.0-" + "a" * (limit - 6))
        with self.assertRaises(pg.GateError) as cm:
            V("1.0.0-" + "a" * (limit - 5))
        self.assertEqual(cm.exception.code, "too_long")


class PrecedenceTests(unittest.TestCase):

    def test_build_metadata_is_ignored(self):
        self.assertEqual(pg.compare(V("1.0.0+build.5"), V("1.0.0")), 0)
        self.assertEqual(pg.compare(V("1.0.0+a"), V("1.0.0+b")), 0)
        self.assertEqual(pg.compare(V("1.0.0-rc.1+x"), V("1.0.0-rc.1")), 0)
        self.assertEqual(arms("1.0.0+build.5", "== 1.0.0")[0], {"verdict": S, "reason": "equal precedence (spec §11)"})

    def test_core_compares_numerically(self):
        self.assertEqual(pg.compare(V("1.10.0"), V("1.9.0")), 1)
        self.assertEqual(pg.compare(V("2.0.0"), V("10.0.0")), -1)
        self.assertEqual(pg.compare(V("1.0.10"), V("1.0.9")), 1)

    def test_core_beats_pre_release(self):
        self.assertEqual(pg.compare(V("1.0.1-alpha"), V("1.0.0")), 1)
        self.assertEqual(pg.compare(V("0.9.9"), V("1.0.0-alpha")), -1)

    def test_lexical_compare_of_alphanumeric_identifiers(self):
        self.assertEqual(pg.compare(V("1.0.0-Beta"), V("1.0.0-alpha")), -1)
        self.assertEqual(pg.compare(V("1.0.0-rc"), V("1.0.0-beta")), 1)

    def test_compare_is_antisymmetric_on_a_mixed_set(self):
        texts = CHAIN + ["1.0.0-0", "1.0.0-01a", "1.0.0-a.0", "1.0.0-a.00a", "0.1.0", "1.0.1-rc.1", "2.0.0-alpha"]
        for a, b in itertools.product(texts, texts):
            self.assertEqual(pg.compare(V(a), V(b)), -pg.compare(V(b), V(a)), (a, b))


class ArmTests(unittest.TestCase):

    def test_reasons(self):
        self.assertEqual(arms("0.9.0", ">= 1.0.0")[0], {"verdict": N, "reason": "below 1.0.0 (spec §11)"})
        self.assertEqual(arms("1.0.1", "== 1.0.0")[0], {"verdict": N, "reason": "precedence differs from 1.0.0 (spec §11)"})
        self.assertEqual(arms("1.0.1", ">= 1.0.0")[0], {"verdict": S, "reason": "precedence holds (spec §11)"})
        self.assertEqual(arms("2.0.0-alpha", "== 1.0.0")[0]["reason"], "precedence differs from 1.0.0 (spec §11)")

    def test_stable_arm_never_accepts_a_pre_release(self):
        for cand in CHAIN[:-1] + ["1.0.1-rc.1", "2.0.0-alpha", "1.0.0-0", "9.9.9-z"]:
            for req in (">= 0.0.0", ">= 1.0.0", "== 1.0.0", "== 9.9.9"):
                self.assertEqual(arms(cand, req)[0]["verdict"], N, (cand, req))

    def test_weak_arm_ignores_every_suffix(self):
        self.assertEqual(arms("1.0.0-alpha+x", "== 1.0.0")[2]["verdict"], S)
        self.assertEqual(arms("0.9.0-rc.1", ">= 1.0.0")[2]["verdict"], N)

    def test_main_fixture_closes_five_of_five(self):
        result = pg.run(pg.load_fixture(os.path.join(FIX, "main.json")))
        self.assertEqual((result["closed"], result["total"], result["weak_wrong"]), (5, 5, 3))
        self.assertIn("closed: 5 / 5 on the declared comparator", pg.report(result))

    def test_more_fixture(self):
        result = pg.run(pg.load_fixture(os.path.join(FIX, "more.json")))
        self.assertEqual((result["closed"], result["total"], result["weak_wrong"]), (11, 11, 5))
        rows = {r["id"]: r for r in result["rows"]}
        self.assertEqual(rows["eq_build"]["stable"]["verdict"], S)
        self.assertEqual(rows["next_major_alpha"]["stable"]["reason"], "pre-release excluded by stable range (policy)")

    def test_a_wrong_expectation_is_reported_and_exits_one(self):
        obj = {"fixture_version": 1, "label": "wrong expectation",
               "pairs": [{"id": "x", "candidate": "1.0.0-rc.1", "requirement": ">= 1.0.0", "expected": S}]}
        tmp, path = write_fixture(obj)
        try:
            code, out, err = run_cli([path])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("[expected SATISFIES]", out)
        self.assertIn("closed: 0 / 1 on the declared comparator", out)


class FixtureTests(unittest.TestCase):

    def test_fixture_list(self):
        names = sorted(os.listdir(FIX))
        self.assertEqual([n for n in names if not n.startswith("bad_")], ["korean.json", "main.json", "more.json"])
        self.assertEqual([n for n in names if n.startswith("bad_")], sorted(BAD_CODES))

    def test_every_bad_fixture_is_deny_with_one_error_line(self):
        for name in sorted(BAD_CODES):
            code, out, err = run_cli([os.path.join(FIX, name)])
            self.assertEqual((code, out), (2, ""), name)
            self.assertEqual(len(err.splitlines()), 1, name)
            self.assertTrue(err.startswith("ERROR %s: " % BAD_CODES[name]), (name, err))
            self.assertIn("on_expiry=DENY", err)

    def test_valid_fixtures_exit_zero(self):
        for name in ("main.json", "more.json", "korean.json"):
            code, out, err = run_cli([os.path.join(FIX, name)])
            self.assertEqual((code, err), (0, ""), name)

    def test_korean_fixture_gives_the_same_verdicts(self):
        a = pg.run(pg.load_fixture(os.path.join(FIX, "main.json")))
        b = pg.run(pg.load_fixture(os.path.join(FIX, "korean.json")))
        strip = lambda res: [(r["candidate"], r["stable"], r["precedence"], r["weak"]) for r in res["rows"]]
        self.assertEqual(strip(a), strip(b))

    def test_one_bad_pair_denies_the_whole_run(self):
        code, out, err = run_cli([os.path.join(FIX, "bad_one_bad_among_good.json")])
        self.assertEqual((code, out), (2, ""))
        self.assertNotIn("SATISFIES", err)

    def test_caps_declare_deny(self):
        self.assertEqual(pg.ON_EXPIRY, "DENY")
        for name, cap in pg.CAPS.items():
            self.assertEqual(cap["on_expiry"], "DENY", name)

    def test_usage_errors(self):
        for args in ([], ["a", "b"], ["--json"]):
            code, out, err = run_cli(args)
            self.assertEqual((code, out, len(err.splitlines())), (2, "", 1), args)
            self.assertTrue(err.startswith("ERROR"))

    def test_json_output(self):
        code, out, err = run_cli(["--json", os.path.join(FIX, "main.json")])
        self.assertEqual((code, err), (0, ""))
        data = json.loads(out)
        self.assertEqual((data["closed"], data["total"]), (5, 5))

    def test_subprocess_contract(self):
        p = subprocess.run([sys.executable, "-B", "prerelease_gate.py", os.path.join("fixtures", "bad_nan.json")],
                           cwd=HERE, capture_output=True)
        self.assertEqual((p.returncode, p.stdout), (2, b""))
        self.assertEqual(len(p.stderr.splitlines()), 1)
        self.assertTrue(p.stderr.startswith(b"ERROR bad_number: "))
        self.assertNotIn(b"Traceback", p.stderr)


class DemoTests(unittest.TestCase):

    def demo(self):
        p = subprocess.run([sys.executable, "-B", "demo.py"], cwd=HERE, capture_output=True)
        self.assertEqual((p.returncode, p.stderr), (0, b""))
        return p.stdout

    def test_deterministic_and_matches_the_readme(self):
        a, b = self.demo(), self.demo()
        self.assertEqual(a, b)
        with open(os.path.join(HERE, "README.md"), "r", encoding="utf-8") as fh:
            self.assertIn(hashlib.sha256(a).hexdigest(), fh.read())

    def test_demo_closes_five_of_five(self):
        text = self.demo().decode("utf-8")
        self.assertIn("closed: 5 / 5 on the declared comparator", text)
        self.assertIn("closed: 11 / 11 on the declared comparator", text)


BANNED = ["al" + "low", "ke" + "ep", "cloud" + "agent", "smi" + "th", "chec" + "ker"]
PATHS = ["/" + "workspace", "/" + "tmp", "/" + "home"]
MECHANISM = [r"hm" + "ac", r"\bsign" + r"ing\b", r"hash-" + "chain", r"ledg" + "er", r"sla" + "ck", r"grok" + "ki",
             r"\bll" + r"m\b", "cursor_" + "agent", "<d" + "iv", "<!" + "--"]
INVENTED_MUST = "must have " + "lower precedence"


def all_files():
    out = []
    for base, dirs, files in os.walk(HERE):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        out += [os.path.relpath(os.path.join(base, f), HERE) for f in sorted(files)]
    return out


def read_text(rel):
    with open(os.path.join(HERE, rel), "rb") as fh:
        return fh.read().decode("utf-8", errors="replace")


class HygieneTests(unittest.TestCase):

    def test_file_list(self):
        self.assertEqual(sorted(n for n in os.listdir(HERE) if n != "__pycache__"),
                         ["README.md", "demo.py", "evidence.json", "fixtures", "mutants.py", "prerelease_gate.py",
                          "test_prerelease_gate.py"])

    def test_no_banned_word_or_path(self):
        for rel in all_files():
            low = read_text(rel).lower()
            for word in BANNED + PATHS:
                self.assertNotIn(word, low, rel)
                self.assertNotIn(word, rel.lower())

    def test_no_mechanism_word(self):
        for rel in all_files():
            low = read_text(rel).lower()
            for pattern in MECHANISM:
                self.assertIsNone(re.search(pattern, low), (rel, pattern))

    def test_no_invented_must(self):
        for rel in all_files():
            self.assertNotIn(INVENTED_MUST, " ".join(read_text(rel).lower().split()), rel)

    def test_stdlib_only_and_offline(self):
        src = read_text("prerelease_gate.py")
        imports = set(re.findall(r"^import (\w+)", src, re.M)) | set(re.findall(r"^from (\w+)", src, re.M))
        self.assertEqual(imports, {"functools", "json", "sys", "unicodedata"})
        for word in ("socket", "urllib", "http.client", "subprocess", "random"):
            self.assertNotIn(word, src)


class EvidenceTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "evidence.json"), "r", encoding="utf-8") as fh:
            cls.ev = json.load(fh)

    def test_source_and_licence(self):
        self.assertEqual(self.ev["source"]["url"], "https://semver.org/spec/v2.0.0.html")
        self.assertEqual(self.ev["source"]["title"], "Semantic Versioning 2.0.0")
        self.assertEqual(self.ev["source"]["licence"], "CC BY 3.0")
        self.assertIs(self.ev["clean_room"], True)
        self.assertIs(self.ev["network_used"], False)
        self.assertEqual(self.ev["on_expiry"], "DENY")

    def test_quotes_are_short(self):
        for q in self.ev["source"]["short_quotes"]:
            self.assertLessEqual(len(q.split()), 8, q)

    def test_measured_matches_a_fresh_run(self):
        for name in ("main", "more"):
            result = pg.run(pg.load_fixture(os.path.join(FIX, name + ".json")))
            self.assertEqual(self.ev["measured"][name], {"closed": result["closed"], "total": result["total"],
                                                         "weak_wrong": result["weak_wrong"]})

    def test_unmeasured_and_no_paper_numbers(self):
        items = self.ev["on_unmeasured"]
        self.assertTrue(items)
        for item in items:
            self.assertEqual(item["status"], "UNVERIFIED")
        self.assertNotIn("paper", self.ev)

    def test_mutant_timeout_declared(self):
        self.assertEqual(self.ev["timeouts"]["mutants"]["on_expiry"], "DENY")
        self.assertEqual(self.ev["timeouts"]["tool"], "none")


class DocumentTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.readme = read_text("README.md")
        cls.flat = " ".join(cls.readme.split())

    def test_credit_and_statements(self):
        for needle in ("Semantic Versioning 2.0.0", "Tom Preston-Werner", "CC BY 3.0",
                       "https://creativecommons.org/licenses/by/3.0/", "https://semver.org/spec/v2.0.0.html",
                       "clean-room", "No code was copied", "not an npm or PEP 440 solver", "Policy, not a SemVer rule",
                       "python3 -B -m unittest", "python3 -B demo.py", "on_expiry", "DENY", "Limits"):
            self.assertIn(needle, self.flat, needle)

    def test_operators_listed(self):
        self.assertIn("`>=`", self.readme)
        self.assertIn("`==`", self.readme)

    def test_not_a_remake_line(self):
        lines = [l for l in self.readme.splitlines() if l.startswith("Not a remake")]
        self.assertEqual(len(lines), 1)


class MutantsHarnessTests(unittest.TestCase):

    def test_timeout_declared_and_never_a_kill(self):
        import mutants
        self.assertEqual(set(mutants.TIMEOUT), {"seconds", "on_expiry"})
        self.assertIs(type(mutants.TIMEOUT["seconds"]), int)
        self.assertEqual(mutants.TIMEOUT["on_expiry"], "DENY")
        self.assertEqual(mutants.outcome(None), "TIMEOUT")
        self.assertEqual(mutants.outcome(0), "SURVIVED")
        self.assertEqual(mutants.outcome(1), "KILLED")
        self.assertFalse(mutants.is_killed("TIMEOUT"))
        self.assertTrue(mutants.is_killed("KILLED"))

    def test_a_timed_out_run_is_reported_and_not_counted(self):
        import mutants
        killed, results = mutants.score(["m1", "m2"], lambda name: mutants.outcome(None))
        self.assertEqual((killed, results), (0, [("TIMEOUT", "m1"), ("TIMEOUT", "m2")]))
        self.assertEqual(mutants.summary_line(killed, 2, results),
                         "mutants killed: 0/2 (timeouts: 2, not counted as kills; on_expiry DENY)")


if __name__ == "__main__":
    unittest.main()
