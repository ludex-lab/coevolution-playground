"""Tests for the mb-conversation-loss-oracle method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
The quote check reads the source copy named in paper_evidence.json from the
directories listed in $MBCONVLOSS_SOURCES (os.pathsep separated). There is
no default: when the variable is unset, or the file is absent, that check
is skipped.

Done-when mapping (Morning Brief 2026-11-15, experiment #1):
  (a) test_a_rule_arm_flags_every_planted_fault
  (b) test_b_permitted_controls_do_not_alarm_or_are_reported
  (c) test_c_static_check_passes_encoding_changes_and_planted_faults
  (d) test_d_every_finding_names_rule_id_and_field_path
  (e) test_e_no_model_no_network_stdlib_only
  forced changes: test_f_forced_changes_labelled_forced_not_faults
  paper figures: test_g_paper_numbers_on_unmeasured
"""

import ast
import copy
import hashlib
import itertools
import json
import os
import re
import unittest

import conv_loss as M
import fixtures as F
import oracle as O

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("MBCONVLOSS_SOURCES")
SLUG = "mb-conversation-loss-oracle"
DAY_HEADER = "# experiments/2026-11-15\n"
ROW_START = "- [%s](%s/): " % (SLUG, SLUG)
ROW_PREFIX = "- [%s](" % SLUG
ROW_END = ("(Soft method sketch of [arXiv 2611.15543](https://arxiv.org/abs/2611.15543);"
           " not a reproduction)")
FOOTER = "Do not merge experiment PRs without Ork review."


def day_readme():
    """Return (relative path, layout) of the day-index README.

    Repo layout: ../README.md in the 2026-11-15 folder, used only when it
    is present and starts with the day header. Flat draft: _day/README.md.
    """
    parent = os.path.join("..", "README.md")
    path = os.path.join(HERE, parent)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            if f.read().startswith(DAY_HEADER):
                return parent, "repo"
    return os.path.join("_day", "README.md"), "flat"


DAY, LAYOUT = day_readme()
CODE = ("conv_loss.py", "oracle.py", "fixtures.py")
PY = CODE + ("test_conv_loss.py", "mutants.py")
ALL = PY + ("README.md", "NOTICE", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
STDLIB_PERMITTED = {"ast", "copy", "hashlib", "io", "itertools", "json", "os", "re", "sys",
                    "unittest", "conv_loss", "oracle", "fixtures", "test_conv_loss"}
CODE_IMPORTS = {"conv_loss.py": set(), "oracle.py": set(),
                "fixtures.py": {"copy", "conv_loss", "oracle"}}
NO_GO_TOKENS = ("vo" + "te", "vo" + "ting", "ensem" + "ble", "major" + "ity",
                "api" + "_key", "api" + "key", "open" + "ai", "anthro" + "pic",
                "envi" + "ron", "http" + "://", "https" + "://", "sub" + "process",
                "sock" + "et", "url" + "lib", "requ" + "ests", "random", "time" + "out",
                "hm" + "ac", "sql" + "ite", "thread")
ABS_PATHS = ("/" + "workspace", "/" + "tmp", "/" + "home")
MARKERS = ("<" * 7, "=" * 7, ">" * 7)
PAPER_PAT = re.compile(r"\d+\.\d+\s*%|\b(?:9" + r"5|12" + r"5|12" + r"7|68" + r"5|20" + r"3|55"
                       + r"8)\b|2/1" + "00|two false " + "alarms|2" + r"7 (?:deterministic )?rules"
                       + "|six mo" + "dels|five transl" + "ator|six config" + "urations")


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def own_rows(text):
    """The lines of a day README that belong to this PR's own row."""
    return [line for line in text.splitlines() if line.startswith(ROW_PREFIX)]


def scan_text(name, text):
    """What the hygiene scans read: the whole file, except that for the day
    README only this PR's own row is read (sibling rows are other PRs')."""
    if name == DAY:
        return "\n".join(own_rows(text))
    return text


def hygiene_hits(text):
    """Return the hygiene categories found in text."""
    low = text.lower()
    hits = set()
    if any(w.lower() in low for w in BANNED):
        hits.add("banned_word")
    if any(p in text for p in ABS_PATHS):
        hits.add("absolute_path")
    if any(m in text for m in MARKERS):
        hits.add("marker")
    if PAPER_PAT.search(text):
        hits.add("paper_number")
    return hits


def case(name):
    return F.cases()[name]


def run(name):
    return M.evaluate(case(name))


def names_in(category):
    return [n for n, lab in F.LABELS.items() if lab[0] == category]


def as_oracle(rec):
    return (rec["baseline"]["verdict"] == M.PASS, rec["rule_arm"]["findings"],
            rec["rule_arm"]["verdict"])


def oracle_of(c):
    return O.reference(copy.deepcopy(c["source"]), copy.deepcopy(c["target"]),
                       copy.deepcopy(c["profile"]))


# Exhaustive spaces for the module-vs-oracle agreement.
E_SRC = (
    {"role": "user", "content": "hi"},
    {"role": "user", "content": "go"},
    {"role": "assistant", "content": "ok"},
    {"role": "assistant", "tool_call": {"id": "k1", "name": "t1", "args": {"x": "1"}}},
    {"role": "tool", "call_id": "k1", "result": ["r", "s"], "is_error": True},
    {"role": "tool", "call_id": "k1", "result": "r\ns", "is_error": False},
)
E_DST = (
    {"speaker": "human", "text": "hi"},
    {"speaker": "human", "text": "go"},
    {"speaker": "model", "text": "ok"},
    {"speaker": "human", "text": "ok"},
    {"speaker": "human", "text": "hi\ngo"},
    {"speaker": "human", "text": "ok\ngo"},
    {"speaker": "human", "text": "S"},
    {"speaker": "model", "invoke": {"ref": "k1", "fn": "t1", "params": {"x": "1"}}},
    {"speaker": "model", "invoke": {"ref": "k1", "fn": "t2", "params": {"x": "1"}}},
    {"speaker": "tool", "ref": "k1", "output": "r\ns", "failed": True},
    {"speaker": "tool", "ref": "k1", "output": "r\ns"},
    {"speaker": "tool", "ref": "k1", "output": "r, s", "failed": False},
)
E_PROFILES = {
    "full": {"has_system": True, "alternating": False, "controls": ["max_tokens"],
             "max_tokens_cap": 10},
    "no_system": {"has_system": False, "alternating": False, "controls": ["max_tokens"],
                  "max_tokens_cap": 10},
    "alternating": {"has_system": True, "alternating": True, "controls": ["max_tokens"],
                    "max_tokens_cap": 10},
}
E_SYSTEMS = ([("full", s, p) for s in ("", "S") for p in (None, "S", "T")]
             + [("no_system", "", None), ("no_system", "S", None), ("no_system", "S", "S"),
                ("alternating", "", None), ("alternating", "S", "S")])
E_MAX_LEN = 2


def seqs(items, n):
    for k in range(n + 1):
        for seq in itertools.product(items, repeat=k):
            yield seq


def enum_message_cases():
    for src in seqs(E_SRC, E_MAX_LEN):
        for dst in seqs(E_DST, E_MAX_LEN):
            for prof, system, preamble in E_SYSTEMS:
                target = {"turns": copy.deepcopy(list(dst)),
                          "functions": [{"name": "t1"}, {"name": "t2"}]}
                if preamble is not None:
                    target["preamble"] = preamble
                yield {"case_id": "enum", "profile": copy.deepcopy(E_PROFILES[prof]),
                       "source": {"system": system, "messages": copy.deepcopy(list(src)),
                                  "tools": ["t1", "t2"], "controls": {}},
                       "target": target}


def _opt_maps(choices):
    keys = sorted(choices)
    for combo in itertools.product(*[choices[k] for k in keys]):
        yield dict((k, v) for k, v in zip(keys, combo) if v is not None)


def enum_control_cases():
    src_choices = {"max_tokens": (None, 100, 9000), "temperature_milli": (None, 200),
                   "thinking_budget": (None, 512)}
    dst_choices = {"max_output": (None, 100, 4096, 9000),
                   "temperature_milli": (None, 200, 300), "reasoning_budget": (None, 512)}
    profiles = ({"has_system": True, "alternating": False,
                 "controls": ["max_tokens", "temperature_milli", "thinking_budget"],
                 "max_tokens_cap": 4096},
                {"has_system": True, "alternating": False,
                 "controls": ["max_tokens", "temperature_milli"], "max_tokens_cap": 4096})
    for sc in _opt_maps(src_choices):
        for dc in _opt_maps(dst_choices):
            for p in profiles:
                yield {"case_id": "enum", "profile": copy.deepcopy(p),
                       "source": {"system": "", "messages": [{"role": "user", "content": "hi"}],
                                  "tools": [], "controls": dict(sc)},
                       "target": {"turns": [{"speaker": "human", "text": "hi"}],
                                  "functions": [], "settings": dict(dc)}}


def enum_tool_cases():
    names = ("t1", "t2", "t3")
    subsets = [list(c) for k in range(4) for c in itertools.combinations(names, k)]
    ordered = [list(p) for k in range(4) for p in itertools.permutations(names, k)]
    for st in subsets:
        for dt in ordered:
            yield {"case_id": "enum", "profile": copy.deepcopy(F.PROFILES["full"]),
                   "source": {"system": "", "messages": [], "tools": list(st), "controls": {}},
                   "target": {"turns": [], "functions": [{"name": n} for n in dt]}}


def agreement(gen):
    """(cases, accepted, schema-accepted, disagreements, rules seen, forced rules seen)."""
    n = acc = schema_ok = bad = 0
    seen = set()
    forced = set()
    for c in gen:
        n += 1
        rec = M.evaluate(c)
        if rec["status"] != M.OK:
            continue
        acc += 1
        ref = oracle_of(c)
        if as_oracle(rec) != ref:
            bad += 1
        if ref[0]:
            schema_ok += 1
        seen |= set(f[0] for f in rec["rule_arm"]["findings"])
        forced |= set(f[0] for f in rec["rule_arm"]["findings"] if f[2] == M.FORCED)
    return n, acc, schema_ok, bad, seen, forced


class SubStr(str):
    pass


class SubInt(int):
    pass


class SubList(list):
    pass


class SubDict(dict):
    pass


class Spoof:
    """A non-str key that hashes and compares equal to the str `name`.

    Every comparison counts in n, so a test can show none ever ran.
    """

    def __init__(self, name):
        self.name = name
        self.n = 0

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        self.n += 1
        return other == self.name if type(other) is str else other is self

    def __lt__(self, other):
        self.n += 1
        return self.name < other

    def __gt__(self, other):
        self.n += 1
        return self.name > other


def code_tokens(src):
    """Lower-cased identifiers and non-docstring string constants of src."""
    tree = ast.parse(src)
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.append(node.id)
        elif isinstance(node, ast.Attribute):
            out.append(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            out.append(node.name)
        elif isinstance(node, ast.arg):
            out.append(node.arg)
        elif isinstance(node, ast.alias):
            out.append(node.name)
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in docs):
            out.append(node.value)
    return "\n".join(out).lower()


def containers(obj, out):
    """Collect the id of every dict, list and tuple reachable from obj."""
    if isinstance(obj, (dict, list, tuple)):
        out.add(id(obj))
        items = list(obj.keys()) + list(obj.values()) if isinstance(obj, dict) else obj
        for x in items:
            containers(x, out)
    return out


class TestDoneWhen(unittest.TestCase):

    def test_a_rule_arm_flags_every_planted_fault(self):
        planted = names_in("fault")
        self.assertEqual(len(planted), 23)
        for name in planted:
            rec = run(name)
            self.assertEqual(rec["status"], M.OK, name)
            self.assertEqual(rec["rule_arm"]["verdict"], M.FAIL, name)
            gold = F.LABELS[name][3]
            planted_avoidable = [f for f in gold if f[2] == M.AVOIDABLE]
            self.assertEqual(len(planted_avoidable), 1, name)
            self.assertIn(planted_avoidable[0], rec["rule_arm"]["findings"], name)
            self.assertEqual(rec["rule_arm"]["findings"], gold, name)
        # Every one of the 21 rule ids is planted at least once.
        seen = set(f[0] for n in planted for f in F.LABELS[n][3])
        self.assertEqual(seen, set(M.RULES))
        self.assertIn("planted faults flagged: baseline 0/23, rule arm 23/23", F.summary())

    def test_b_permitted_controls_do_not_alarm_or_are_reported(self):
        controls = names_in("control")
        self.assertEqual(len(controls), 7)
        alarmed = [n for n in controls if run(n)["rule_arm"]["verdict"] == M.FAIL]
        # The one alarm is the declared, honestly reported false alarm.
        self.assertEqual(alarmed, ["ctl-trailing-newline-stripped"])
        self.assertEqual(run("ctl-trailing-newline-stripped")["rule_arm"]["findings"],
                         (("CL02", "system", M.AVOIDABLE),))
        for n in controls:
            if n not in alarmed:
                self.assertEqual(run(n)["rule_arm"]["findings"], (), n)
        self.assertIn("permitted-change controls alarmed: baseline 0/7, rule arm 1/7",
                      F.summary())
        flat = " ".join(read("README.md").split())
        self.assertIn("ctl-trailing-newline-stripped", flat)
        self.assertIn("false alarm", flat)

    def test_c_static_check_passes_encoding_changes_and_planted_faults(self):
        for name in names_in("control") + names_in("fault") + names_in("forced"):
            rec = run(name)
            self.assertEqual(rec["baseline"], {"verdict": M.PASS, "schema_error": None}, name)
        # The baseline (static check only) misses every planted fault.
        self.assertEqual([n for n in names_in("fault")
                          if run(n)["baseline"]["verdict"] == M.FAIL], [])
        # The static check is not vacuous: it rejects the over-cap payload.
        rec = run("s-over-cap")
        self.assertEqual(rec["baseline"]["schema_error"], ("setting_over_cap", "settings.max_output"))
        self.assertEqual(rec["rule_arm"]["verdict"], M.FAIL)
        self.assertIn("planted faults passing the static target check: 23/23", F.summary())

    def test_d_every_finding_names_rule_id_and_field_path(self):
        pat = re.compile(r"^(system|messages|messages\[\d+\](\.(role|text|name|args|call|"
                         r"content|is_error))?|tools\.[a-z_0-9]+|controls\.(max_tokens|"
                         r"temperature_milli|thinking_budget))$")
        n = 0
        for name, (m, _) in F.run_all().items():
            if m["status"] != M.OK:
                continue
            for f in m["rule_arm"]["findings"]:
                n += 1
                self.assertEqual(len(f), 3, name)
                self.assertIn(f[0], M.RULES, name)
                self.assertRegex(f[1], pat)
                self.assertIn(f[2], (M.AVOIDABLE, M.FORCED), name)
                text = M.describe(f)
                self.assertTrue(text.startswith(f[0] + " " + M.RULES[f[0]] + " at " + f[1]),
                                text)
        self.assertEqual(n, 29)
        self.assertIn("planted faults named with rule id and path: 23/23", F.summary())
        # The paths point at the source position of the change.
        self.assertEqual(run("f-error-flag-dropped")["rule_arm"]["findings"][0][1],
                         "messages[6].is_error")
        self.assertEqual(case("f-error-flag-dropped")["source"]["messages"][6]["is_error"], True)

    def test_e_no_model_no_network_stdlib_only(self):
        for name in PY:
            for node in ast.walk(ast.parse(read(name))):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [(node.module or "").split(".")[0]]
                else:
                    continue
                for m in mods:
                    self.assertIn(m, STDLIB_PERMITTED, (name, m))
        for name, want in CODE_IMPORTS.items():
            got = set()
            for node in ast.walk(ast.parse(read(name))):
                if isinstance(node, ast.Import):
                    got |= {a.name for a in node.names}
                elif isinstance(node, ast.ImportFrom):
                    got.add(node.module)
            self.assertEqual(got, want, name)
            low = code_tokens(read(name))
            for tok in NO_GO_TOKENS:
                self.assertNotIn(tok, low, (name, tok))
        # The same on the loaded code, not only the file.
        for mod in (M, O):
            for fname, fobj in sorted(vars(mod).items()):
                if callable(fobj) and getattr(fobj, "__module__", None) == mod.__name__ \
                        and hasattr(fobj, "__code__"):
                    co = fobj.__code__
                    low = "\n".join(co.co_names + co.co_varnames).lower()
                    for tok in NO_GO_TOKENS + ("open", "eval", "exec", "__import__"):
                        self.assertNotIn(tok, low.split("\n"), (fname, tok))

    def test_f_forced_changes_labelled_forced_not_faults(self):
        forced = names_in("forced")
        self.assertEqual(len(forced), 4)
        for name in forced:
            rec = run(name)
            self.assertEqual(rec["rule_arm"]["verdict"], M.PASS, name)
            self.assertEqual(rec["rule_arm"]["avoidable"], 0, name)
            self.assertEqual(rec["rule_arm"]["forced"], 1, name)
            self.assertEqual(rec["rule_arm"]["findings"], F.LABELS[name][3], name)
        # The same change is a fault when the target could have preserved it.
        pairs = (("fo-system-demoted", "f-system-demoted-needlessly"),
                 ("fo-same-role-merge", "f-same-role-merge-needless"))
        for forced_name, fault_name in pairs:
            a, b = case(forced_name), case(fault_name)
            self.assertEqual(a["target"], b["target"])
            self.assertNotEqual(a["profile"], b["profile"])
            fa = run(forced_name)["rule_arm"]["findings"]
            fb = run(fault_name)["rule_arm"]["findings"]
            self.assertEqual([f[:2] for f in fa], [f[:2] for f in fb])
            self.assertEqual((fa[0][2], fb[0][2]), (M.FORCED, M.AVOIDABLE))
        # A forced clamp beside an avoidable injection: both reported.
        rec = run("f-clamp-plus-injection")
        self.assertEqual((rec["rule_arm"]["avoidable"], rec["rule_arm"]["forced"]), (1, 1))
        # Dropping the system text is avoidable even when the target has no
        # system field, because the declared encoding can demote it.
        self.assertEqual(run("f-system-dropped-no-system-target")["rule_arm"]["findings"],
                         (("CL01", "system", M.AVOIDABLE),))
        self.assertIn("forced findings reported as forced: 5", F.summary())

    def test_g_paper_numbers_on_unmeasured(self):
        self.assertEqual(M.paper_results(), M.ON_UNMEASURED)
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["measured_here"], "on_unmeasured")
        nums = [c for c in ev["claims"] + ev["upstream_readme_claims"] if "values" in c]
        vals = sorted(v for c in nums for v in c["values"].values())
        self.assertEqual(vals, sorted(["9" + "5/12" + "5", "76" + ".0%", "2/1" + "00",
                                       "2" + ".0%", "12" + "7/68" + "5", "18" + ".5%",
                                       "20" + "3/55" + "8", "36" + ".4%", "2" + "7"]))
        for c in nums:
            for v in c["values"].values():
                self.assertIn(v.split("/")[0], c["quote"], c["id"])
        for c in ev["claims"] + ev["upstream_readme_claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")
            self.assertEqual(c["measured_here"], "on_unmeasured")
            self.assertTrue(c["on_unmeasured"])


class TestRules(unittest.TestCase):

    def test_expected_table(self):
        for name, lab in F.LABELS.items():
            rec = run(name)
            self.assertEqual(rec["status"], M.OK, name)
            self.assertEqual(rec["case_id"], name)
            self.assertEqual((rec["baseline"]["verdict"], rec["rule_arm"]["verdict"],
                              rec["rule_arm"]["findings"]), lab[1:], name)
            self.assertEqual(rec["rule_arm"]["avoidable"],
                             len([f for f in lab[3] if f[2] == M.AVOIDABLE]), name)

    def test_hand_target_is_the_declared_encoding(self):
        src = M._source(F.cases()["ctl-role-field-renamed"]["source"])
        prof = M._profile(F.PROFILES["full"])
        enc = M.encode_b(src, prof)
        self.assertIsNone(M.schema_check(enc, prof))
        self.assertEqual(M.target_ir(enc), M.target_ir(copy.deepcopy(F.TARGET0)))
        self.assertEqual(M.target_ir(enc), src)
        self.assertEqual(enc["turns"][2]["output"], "KTX 101 07:00\nKTX 105 09:30")
        self.assertEqual(enc["turns"][1]["invoke"]["ref"], "call-0")
        for name in ("fo-system-demoted", "fo-same-role-merge", "fo-thinking-unsupported",
                     "fo-max-tokens-clamped"):
            c = case(name)
            p = M._profile(c["profile"])
            self.assertEqual(M.target_ir(M.encode_b(M._source(c["source"]), p)),
                             M.target_ir(c["target"]), name)

    def test_declared_encoding_makes_only_forced_changes(self):
        sources = [F.SOURCE0, F.SOURCE1, dict(F.SOURCE1, controls=dict(F.BIG1))]
        n = 0
        for s in sources:
            for pname, p in sorted(F.PROFILES.items()):
                src = M._source(copy.deepcopy(s))
                prof = M._profile(copy.deepcopy(p))
                enc = M.encode_b(src, prof)
                self.assertIsNone(M.schema_check(enc, prof), pname)
                found = M.rules(src, M.target_ir(enc), prof)
                self.assertEqual([f for f in found if f[2] != M.FORCED], [], (pname, found))
                rec = M.evaluate({"case_id": "e", "source": copy.deepcopy(s), "target": enc,
                                  "profile": copy.deepcopy(p)})
                self.assertEqual(rec["rule_arm"]["verdict"], M.PASS)
                self.assertEqual(as_oracle(rec)[1:], oracle_of(
                    {"source": s, "target": enc, "profile": p})[1:])
                n += len(found)
        self.assertEqual(n, 11)

    def test_clamp_rules(self):
        base = case("fo-max-tokens-clamped")
        for out, status in ((4096, M.FORCED), (4000, M.AVOIDABLE), (2000, M.AVOIDABLE)):
            c = copy.deepcopy(base)
            c["target"]["settings"]["max_output"] = out
            self.assertEqual(M.evaluate(c)["rule_arm"]["findings"],
                             (("CL21", "controls.max_tokens", status),), out)
        c = case("f-control-altered")
        c["profile"]["max_tokens_cap"] = 512
        self.assertEqual(M.evaluate(c)["rule_arm"]["findings"],
                         (("CL21", "controls.max_tokens", M.FORCED),))

    def test_merge_and_drop_shapes(self):
        c = case("f-cross-role-merge")
        c["target"]["turns"][3]["speaker"] = "model"
        self.assertEqual(M.evaluate(c)["rule_arm"]["findings"],
                         (("CL09", "messages[3]", M.AVOIDABLE),))
        # Joined in the wrong order: neither a merge nor a drop.
        c = case("f-cross-role-merge")
        c["target"]["turns"][3]["text"] = F.T4 + "\n" + F.T3
        self.assertEqual(M.evaluate(c)["rule_arm"]["findings"],
                         (("CL10", "messages", M.AVOIDABLE),))
        c = case("fo-same-role-merge")
        c["target"]["turns"][0]["speaker"] = "model"
        self.assertEqual(M.evaluate(c)["baseline"]["verdict"], M.FAIL)
        c = case("f-message-dropped")
        c["target"]["turns"].pop(0)
        self.assertEqual(M.evaluate(c)["rule_arm"]["findings"],
                         (("CL10", "messages", M.AVOIDABLE),))

    def test_system_rules(self):
        c = case("ctl-role-field-renamed")
        c["source"]["system"] = ""
        self.assertEqual(M.evaluate(c)["rule_arm"]["findings"],
                         (("CL02", "system", M.AVOIDABLE),))
        c = case("fo-system-demoted")
        c["target"]["turns"][0]["text"] = F.SYS0 + "!"
        rec = M.evaluate(c)
        self.assertIn(("CL01", "system", M.AVOIDABLE), rec["rule_arm"]["findings"])
        c = case("fo-system-demoted")
        c["target"]["preamble"] = F.SYS0
        self.assertEqual(M.evaluate(c)["baseline"]["schema_error"],
                         ("preamble_unsupported", "preamble"))

    def test_rules_never_read_the_raw_payloads(self):
        """rules() sees only intermediate records: equal records, equal findings."""
        a = M._source(case("ctl-role-field-renamed")["source"])
        b = M._source(case("ctl-source-text-result")["source"])
        self.assertEqual(a, b)
        t1 = M.target_ir(case("ctl-key-order")["target"])
        t2 = M.target_ir(case("ctl-ids-reminted")["target"])
        self.assertEqual(t1, t2)


class TestSchema(unittest.TestCase):

    def check(self, edit, code, path, profile="full"):
        t = copy.deepcopy(F.TARGET0)
        edit(t)
        self.assertEqual(M.schema_check(t, M._profile(F.PROFILES[profile])), (code, path))
        self.assertFalse(O.reference_schema(t, M._profile(F.PROFILES[profile])))
        rec = M.evaluate({"case_id": "s", "source": copy.deepcopy(F.SOURCE0), "target": t,
                          "profile": copy.deepcopy(F.PROFILES[profile])})
        self.assertEqual(rec["baseline"]["verdict"], M.FAIL)
        self.assertEqual(rec["rule_arm"], {"verdict": M.FAIL, "findings": (), "avoidable": 0,
                                           "forced": 0})

    def test_rejections(self):
        def setk(k, v):
            return lambda t: t.__setitem__(k, v)

        self.check(setk("extra", 1), "unknown_field", "extra")
        self.check(lambda t: t.pop("turns"), "missing_field", "turns")
        self.check(lambda t: t.pop("functions"), "missing_field", "functions")
        self.check(lambda t: None, "preamble_unsupported", "preamble", "no_system")
        self.check(setk("preamble", ""), "preamble_invalid", "preamble")
        self.check(setk("preamble", 3), "preamble_invalid", "preamble")
        self.check(setk("functions", {}), "functions_invalid", "functions")
        self.check(lambda t: t["functions"].append({"name": "x", "y": 1}), "function_invalid",
                   "functions[3]")
        self.check(lambda t: t["functions"].append({"name": "hold_seat"}),
                   "function_name_invalid", "functions[3].name")
        self.check(lambda t: t["functions"].append({"name": " "}), "function_name_invalid",
                   "functions[3].name")
        self.check(setk("settings", []), "settings_invalid", "settings")
        self.check(lambda t: t["settings"].update(top_p=1), "setting_unknown", "settings.top_p")
        self.check(lambda t: t["settings"].update(max_output=-1), "setting_invalid",
                   "settings.max_output")
        self.check(lambda t: t["settings"].update(max_output=True), "setting_invalid",
                   "settings.max_output")
        self.check(lambda t: t["settings"].update(reasoning_budget=5), "setting_unsupported",
                   "settings.reasoning_budget", "no_thinking")
        self.check(lambda t: t["settings"].update(max_output=4097), "setting_over_cap",
                   "settings.max_output")
        self.check(setk("turns", {}), "turns_invalid", "turns")
        self.check(lambda t: t["turns"].append("hi"), "turn_invalid", "turns[8]")
        self.check(lambda t: t["turns"][0].update(text=5), "turn_text_invalid", "turns[0].text")
        self.check(lambda t: t["turns"][0].update(speaker="system"), "turn_shape_invalid",
                   "turns[0]")
        self.check(lambda t: t["turns"][1]["invoke"].pop("params"), "invoke_invalid",
                   "turns[1].invoke")
        self.check(lambda t: t["turns"][5]["invoke"].update(ref="c1"), "invoke_ref_invalid",
                   "turns[5].invoke.ref")
        self.check(lambda t: t["turns"][5]["invoke"].update(fn="book_seat"),
                   "invoke_fn_undeclared", "turns[5].invoke.fn")
        self.check(lambda t: t["turns"][5]["invoke"].update(params={"train": 105}),
                   "invoke_params_invalid", "turns[5].invoke.params")
        self.check(lambda t: t["turns"][6].update(ref="c9"), "tool_ref_unknown", "turns[6].ref")
        self.check(lambda t: t["turns"][6].update(output=["x"]), "tool_output_invalid",
                   "turns[6].output")
        self.check(lambda t: t["turns"][6].update(failed="yes"), "tool_failed_invalid",
                   "turns[6].failed")
        self.check(lambda t: t["turns"].insert(1, {"speaker": "human", "text": "again"}),
                   "alternation_violated", "turns[1]", "alternating")
        self.check(lambda t: t["turns"][6].update(speaker="model"), "turn_shape_invalid",
                   "turns[6]")

    def test_not_an_object(self):
        p = M._profile(F.PROFILES["full"])
        self.assertEqual(M.schema_check([], p), ("payload_not_object", ""))
        self.assertFalse(O.reference_schema([], p))


class TestHardening(unittest.TestCase):

    def cfg(self, rec, detail):
        self.assertEqual((rec["status"], rec["detail"]), (M.CONFIG_ERROR, detail))
        self.assertIsNone(rec["rule_arm"])
        self.assertIsNone(rec["baseline"])

    def test_config_errors(self):
        base = case("ctl-role-field-renamed")

        def with_(edit):
            c = copy.deepcopy(base)
            edit(c)
            return M.evaluate(c)

        self.cfg(M.evaluate(None), "case_not_dict")
        self.cfg(M.evaluate(SubDict(base)), "case_not_dict")
        self.cfg(with_(lambda c: c.pop("target")), "target_missing")
        self.cfg(with_(lambda c: c.update(extra=1)), "case_unknown_field")
        self.cfg(with_(lambda c: c.update(case_id=" ")), "case_id_invalid")
        self.cfg(with_(lambda c: c.update(case_id=SubStr("x"))), "case_id_invalid")
        self.cfg(with_(lambda c: c.update(source=SubDict(c["source"]))), "source_not_dict")
        self.cfg(with_(lambda c: c["source"].pop("tools")), "source_fields_invalid")
        self.cfg(with_(lambda c: c["source"].update(system=None)), "source_system_invalid")
        self.cfg(with_(lambda c: c["source"].update(system=SubStr("x"))),
                 "source_system_invalid")
        self.cfg(with_(lambda c: c["source"].update(tools=("a",))), "source_tools_invalid")
        self.cfg(with_(lambda c: c["source"]["tools"].append("hold_seat")),
                 "source_tools_invalid")
        self.cfg(with_(lambda c: c["source"]["tools"].append(SubStr("z"))),
                 "source_tools_invalid")
        self.cfg(with_(lambda c: c["source"]["controls"].update(max_tokens=True)),
                 "source_controls_invalid")
        self.cfg(with_(lambda c: c["source"]["controls"].update(max_tokens=SubInt(5))),
                 "source_controls_invalid")
        self.cfg(with_(lambda c: c["source"]["controls"].update(max_tokens=-1)),
                 "source_controls_invalid")
        self.cfg(with_(lambda c: c["source"]["controls"].update(top_p=1)),
                 "source_controls_invalid")
        self.cfg(with_(lambda c: c["source"].update(messages=SubList(c["source"]["messages"]))),
                 "source_messages_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"].append("hi")), "source_message_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][0].update(role="system")),
                 "source_role_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][0].update(role=SubStr("user"))),
                 "source_role_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][0].update(content=SubStr("x"))),
                 "source_content_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][0].update(extra="x")),
                 "source_message_shape")
        self.cfg(with_(lambda c: c["source"]["messages"][1].update(role="user")),
                 "source_role_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][1].update(tool_call=[])),
                 "source_call_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][1]["tool_call"].pop("args")),
                 "source_call_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][5]["tool_call"].update(id="c1")),
                 "source_call_id_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][5]["tool_call"].update(name="nope")),
                 "source_call_name_unknown")
        self.cfg(with_(lambda c: c["source"]["messages"][5]["tool_call"].update(
            args={"train": 105})), "source_call_args_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][2].update(role="assistant")),
                 "source_role_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][2].update(call_id="c2")),
                 "source_result_link_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][2].update(result=["a", 1])),
                 "source_result_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][2].update(result=SubList(["a"]))),
                 "source_result_invalid")
        self.cfg(with_(lambda c: c["source"]["messages"][2].update(is_error=0)),
                 "source_is_error_invalid")
        self.cfg(with_(lambda c: c.update(profile=[])), "profile_not_dict")
        self.cfg(with_(lambda c: c["profile"].pop("alternating")), "profile_fields_invalid")
        self.cfg(with_(lambda c: c["profile"].update(has_system=1)), "profile_flag_invalid")
        self.cfg(with_(lambda c: c["profile"].update(has_system=False, alternating=True)),
                 "profile_combination_unsupported")
        self.cfg(with_(lambda c: c["profile"].update(controls=["max_tokens", "max_tokens"])),
                 "profile_controls_invalid")
        self.cfg(with_(lambda c: c["profile"].update(controls="max_tokens")),
                 "profile_controls_invalid")
        self.cfg(with_(lambda c: c["profile"].update(max_tokens_cap=0)), "profile_cap_invalid")
        self.cfg(with_(lambda c: c["profile"].update(max_tokens_cap=SubInt(9))),
                 "profile_cap_invalid")
        self.cfg(with_(lambda c: c["target"].update(preamble=SubStr("x"))),
                 "target_value_invalid")
        self.cfg(with_(lambda c: c["target"]["settings"].update(temperature_milli=0.2)),
                 "target_value_invalid")
        self.cfg(with_(lambda c: c["target"].update(turns=tuple(c["target"]["turns"]))),
                 "target_value_invalid")
        self.cfg(with_(lambda c: c["target"]["turns"].append(SubDict(speaker="human",
                                                                     text="x"))),
                 "target_value_invalid")
        self.cfg(with_(lambda c: c["target"]["turns"].append(None)), "target_value_invalid")

        def deep(c):
            v = "x"
            for _ in range(M.MAX_DEPTH + 1):
                v = [v]
            c["target"]["deep"] = v
        self.cfg(with_(deep), "target_too_deep")

    def test_spoofed_keys_never_compared(self):
        def plant(where):
            key = Spoof("extra")
            c = case("ctl-role-field-renamed")
            where(c)[key] = "x"
            key.n = 0
            return key, M.evaluate(c)

        spots = (
            (lambda c: c, "case_key_invalid"),
            (lambda c: c["source"], "source_key_invalid"),
            (lambda c: c["source"]["messages"][0], "source_message_key_invalid"),
            (lambda c: c["source"]["messages"][1]["tool_call"], "source_call_invalid"),
            (lambda c: c["source"]["messages"][1]["tool_call"]["args"],
             "source_call_args_invalid"),
            (lambda c: c["source"]["controls"], "source_controls_invalid"),
            (lambda c: c["profile"], "profile_key_invalid"),
            (lambda c: c["target"], "target_key_invalid"),
            (lambda c: c["target"]["turns"][1]["invoke"]["params"], "target_key_invalid"),
        )
        for where, detail in spots:
            key, rec = plant(where)
            self.cfg(rec, detail)
            self.assertEqual(key.n, 0, detail)
        # A spoof that replaces a real key: the check runs before the lookup.
        c = case("ctl-role-field-renamed")
        m = c["source"]["messages"][0]
        key = Spoof("role")
        m[key] = m.pop("role")
        key.n = 0
        self.cfg(M.evaluate(c), "source_message_key_invalid")
        self.assertEqual(key.n, 0)
        for bad in (1, (1, 2), SubStr("zz")):
            c = case("ctl-role-field-renamed")
            c["target"]["turns"][0][bad] = "x"
            self.cfg(M.evaluate(c), "target_key_invalid")

    def test_snapshot_shares_nothing_with_the_caller(self):
        seen = []
        real = M._run

        def spy(snap):
            seen.append(snap)
            return real(snap)

        M._run = spy
        try:
            for name in F.CASES:
                c = case(name)
                M.evaluate(c)
                mine = containers(c, set())
                theirs = containers(seen[-1], set())
                self.assertEqual(mine & theirs, set(), name)
        finally:
            M._run = real

    def test_caller_mutation_mid_run_changes_nothing(self):
        real = M.schema_check
        for name in F.CASES:
            clean = run(name)
            c = case(name)

            def meddle(t, profile, c=c):
                c["source"]["messages"].clear()
                c["source"]["system"] = "meddled"
                c["target"]["turns"].clear()
                c["target"].pop("preamble", None)
                c["profile"]["controls"].clear()
                return real(t, profile)

            M.schema_check = meddle
            try:
                rec = M.evaluate(c)
            finally:
                M.schema_check = real
            self.assertEqual(rec, clean, name)

    def test_never_raises(self):
        real = M.rules

        def boom(*a):
            raise OverflowError("boom")

        M.rules = boom
        try:
            self.cfg(run("ctl-role-field-renamed"), "internal_error")
        finally:
            M.rules = real
        real_v = M._profile
        M._profile = boom
        try:
            self.cfg(run("ctl-role-field-renamed"), "internal_error")
        finally:
            M._profile = real_v
        for junk in (0, "x", [], (), set(), 1.5, b"x"):
            self.assertEqual(M.evaluate(junk)["status"], M.CONFIG_ERROR)

    def test_no_timeout_or_expiry(self):
        low = code_tokens(read("conv_loss.py"))
        for tok in ("expir", "dead" + "line", "clock", "sleep", "on_expiry"):
            self.assertNotIn(tok, low, tok)
        flat = " ".join(read("README.md").split())
        self.assertIn("no timeout or expiry", flat)


class TestOracle(unittest.TestCase):

    def test_module_and_oracle_agree_on_all_fixtures(self):
        rows = F.run_all()
        self.assertEqual(len(rows), 35)
        for name, (m, o) in rows.items():
            self.assertEqual(as_oracle(m), o, name)
        self.assertIn("module vs oracle: 35/35 cases agree", F.summary())

    def test_exhaustive_messages(self):
        n, acc, schema_ok, bad, seen, forced = agreement(enum_message_cases())
        self.assertEqual(bad, 0)
        self.assertEqual((n, acc, schema_ok), E_COUNTS["messages"])
        self.assertEqual(seen, {"CL01", "CL02", "CL03", "CL04", "CL05", "CL06", "CL07", "CL08",
                                "CL09", "CL10", "CL11", "CL14", "CL15", "CL16"})
        # Forced status appears only where a declared target limit exists.
        self.assertEqual(forced, {"CL03", "CL08"})

    def test_exhaustive_controls(self):
        n, acc, schema_ok, bad, seen, forced = agreement(enum_control_cases())
        self.assertEqual(bad, 0)
        self.assertEqual((n, acc, schema_ok), E_COUNTS["controls"])
        self.assertEqual(seen, {"CL19", "CL20", "CL21"})
        self.assertEqual(forced, {"CL19", "CL21"})

    def test_exhaustive_tools(self):
        n, acc, schema_ok, bad, seen, forced = agreement(enum_tool_cases())
        self.assertEqual(bad, 0)
        self.assertEqual((n, acc, schema_ok), E_COUNTS["tools"])
        self.assertEqual(seen, {"CL17", "CL18"})
        self.assertEqual(forced, set())

    def test_harness_calls_the_oracle(self):
        real = O.reference
        sentinel = ("oracle", "was", "called")
        O.reference = lambda *a: sentinel
        try:
            self.assertEqual(oracle_of(case("f-reordered")), sentinel)
        finally:
            O.reference = real

    def test_oracle_imports_nothing(self):
        tree = ast.parse(read("oracle.py"))
        self.assertEqual([n for n in ast.walk(tree)
                          if isinstance(n, (ast.Import, ast.ImportFrom, ast.While))], [])
        shared = set(n for n in vars(O) if not n.startswith("__")) & set(vars(M))
        self.assertEqual(shared, set())


E_COUNTS = {"messages": (74261, 37994, 18832), "controls": (576, 576, 324),
            "tools": (128, 128, 128)}


class TestFixtures(unittest.TestCase):

    def test_fixture_invariants(self):
        cs = F.cases()
        self.assertEqual(sorted(cs), sorted(F.LABELS))
        self.assertEqual(len(cs), 35)
        for name, c in cs.items():
            self.assertEqual(c["case_id"], name)
            self.assertIn(c["profile"], F.PROFILES.values(), name)
            self.assertTrue(name.startswith({"control": "ctl-", "fault": "f-", "forced": "fo-",
                                             "schema": "s-"}[F.LABELS[name][0]]), name)
        cats = [lab[0] for lab in F.LABELS.values()]
        self.assertEqual((cats.count("control"), cats.count("fault"), cats.count("forced"),
                          cats.count("schema")), (7, 23, 4, 1))
        # Each planted fault differs from the faithful target or profile.
        for name in names_in("fault"):
            c = cs[name]
            faithful = cs["ctl-role-field-renamed"] if c["source"]["system"] == F.SYS0 else None
            if faithful is not None and c["profile"] == faithful["profile"]:
                self.assertNotEqual(c["target"], faithful["target"], name)

    def test_fixture_pins(self):
        self.assertEqual(F.TARGET0["turns"][6], {"speaker": "tool", "ref": "c2",
                                                  "output": "seat map unavailable",
                                                  "failed": True})
        self.assertEqual(F.SOURCE0["messages"][6]["is_error"], True)
        self.assertNotIn("failed", F.CASES["f-error-flag-dropped"]["target"]["turns"][6])
        self.assertEqual(F.SOURCE0["controls"], {"max_tokens": 1024, "temperature_milli": 200})
        self.assertEqual(F.PROFILES["full"]["max_tokens_cap"], 4096)
        self.assertEqual(F.BIG1["max_tokens"], 8000)
        self.assertEqual(list(F.CASES["ctl-key-order"]["target"]), ["settings", "functions",
                                                                     "turns", "preamble"])

    def test_fixtures_return_copies(self):
        c = F.cases()
        c["ctl-role-field-renamed"]["target"]["turns"].clear()
        lab = F.labels()
        lab["f-system-dropped"] = None
        self.assertEqual(len(F.cases()["ctl-role-field-renamed"]["target"]["turns"]), 8)
        self.assertIsNotNone(F.LABELS["f-system-dropped"])

    def test_determinism(self):
        self.assertEqual(F.summary(), F.summary())


class TestDocs(unittest.TestCase):

    def test_banned_words_absent(self):
        for name in ALL:
            text = scan_text(name, read(name)).lower()
            for word in BANNED:
                self.assertNotIn(word.lower(), text, (name, word))

    def test_no_absolute_paths_or_markers(self):
        for name in ALL:
            text = scan_text(name, read(name))
            for p in ABS_PATHS:
                self.assertNotIn(p, text, name)
            for marker in MARKERS:
                self.assertNotIn(marker, text, name)

    def test_hygiene_scoped_to_own_day_row(self):
        """A dirty sibling row is ignored; the same text in this row is caught."""
        dirty = ("an al" + "lowlist that ke" + "eps 12" + ".5 % in /" + "tmp per Check" + "er "
                 + "<" * 7)
        clean = "clean text " + ROW_END
        every = {"banned_word", "absolute_path", "marker", "paper_number"}
        self.assertEqual(hygiene_hits(dirty), every)
        self.assertEqual(hygiene_hits(clean), set())

        def day(own, sibling):
            return (DAY_HEADER + "\n- [mb-other](mb-other/): " + sibling + "\n"
                    + ROW_START + own + "\n\n" + FOOTER + "\n")

        self.assertEqual(own_rows(day(clean, dirty)), [ROW_START + clean])
        self.assertEqual(hygiene_hits(scan_text(DAY, day(clean, dirty))), set())
        self.assertEqual(hygiene_hits(scan_text(DAY, day(dirty, clean))), every)
        self.assertEqual(hygiene_hits(scan_text(DAY, day(dirty, dirty))), every)
        # Files other than the day README are still scanned whole.
        self.assertEqual(hygiene_hits(scan_text("README.md", day(clean, dirty))), every)
        # The real day README has this PR's row, so the scoped scans read something.
        self.assertEqual(len(own_rows(read(DAY))), 1)

    def test_day_readme(self):
        text = read(DAY)
        lines = text.splitlines()
        self.assertTrue(text.startswith(DAY_HEADER + "\n"))
        self.assertEqual(text.count(FOOTER), 1)
        self.assertTrue(text.endswith("\n\n" + FOOTER + "\n"))
        rows = [line for line in lines if line.startswith(ROW_START)]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].endswith(ROW_END))
        if LAYOUT == "flat":
            self.assertEqual(sum(1 for line in lines if line.startswith("- ")), 1)

    def test_no_paper_claims_outside_evidence(self):
        for name in PY + ("README.md", "NOTICE", DAY):
            self.assertIsNone(PAPER_PAT.search(scan_text(name, read(name))), name)

    def test_readme_results_match_the_code(self):
        summary = F.summary()
        readme = read("README.md")
        for line in summary.splitlines():
            self.assertIn(line, readme, line)
        flat = " ".join(readme.split())
        self.assertIn("not comparable with any figure in the paper", flat)
        self.assertNotRegex(summary, r"%")
        for key, (n, acc, ok) in E_COUNTS.items():
            self.assertIn("%s: %d cases, %d accepted, %d past the static check, 0 disagreements"
                          % (key, n, acc, ok), readme)

    def test_readme_credits_differentiation_and_limits(self):
        flat = " ".join(read("README.md").split())
        ev = json.loads(read("paper_evidence.json"))
        self.assertIn(ev["paper"]["title"], flat)
        for author in ev["paper"]["authors"]:
            self.assertIn(author, flat)
        for s in ("**Soft** method sketch", "not a reproduction", "UNVERIFIED",
                  "on_unmeasured", "paper_evidence.json", "## Limits", "## Builder reflection",
                  "Apache-2.0", "8c34759bb854767e55b80af3016693400f5cb698",
                  "https://github.com/convpreserve/conv-preserve", "not run",
                  "python3 -B -m unittest", "python3 -B mutants.py",
                  "w23-world-consistent-history", "no timeout or expiry", "CC BY 4.0",
                  "Ludex Village"):
            self.assertIn(s, flat, s)
        notice = " ".join(read("NOTICE").split())
        for s in (ev["paper"]["title"], "Xin Liu", "arXiv:2611.15543",
                  "https://arxiv.org/abs/2611.15543", "Apache-2.0", "CC BY 4.0", "clean-room",
                  "not run", "8c34759bb854767e55b80af3016693400f5cb698"):
            self.assertIn(s, notice, s)

    def test_evidence_shape(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.15543")
        self.assertIn("by/4.0", ev["paper"]["licence"])
        self.assertFalse(ev["paper"]["pdf_read"])
        repo = ev["upstream_repo"]
        self.assertEqual(repo["head"], "8c34759bb854767e55b80af3016693400f5cb698")
        self.assertFalse(repo["run"])
        self.assertFalse(repo["code_copied"])
        self.assertIn("Apache-2.0", repo["licence"])
        for c in ev["claims"]:
            self.assertEqual(len(c["quote"]), c["length"])

    def test_quotes_exact_in_sources(self):
        if not SOURCES:
            self.skipTest("MBCONVLOSS_SOURCES not set")
        ev = json.loads(read("paper_evidence.json"))
        src = ev["sources"][0]
        path = None
        for d in SOURCES.split(os.pathsep):
            p = os.path.join(d, src["file"])
            if d and os.path.exists(p):
                path = p
                break
        if path is None:
            self.skipTest("source copy not present")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), src["sha256"])
        self.assertEqual(len(text), src["chars"])
        for c in ev["claims"]:
            self.assertEqual(text.count(c["quote"]), 1, c["id"])
            self.assertEqual(text[c["offset"]:c["offset"] + c["length"]], c["quote"], c["id"])


if __name__ == "__main__":
    unittest.main()
