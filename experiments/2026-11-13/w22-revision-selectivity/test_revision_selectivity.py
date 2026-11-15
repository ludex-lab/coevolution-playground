"""Tests for the w22-revision-selectivity method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
Done-when (a)..(d) each have their own TestCase class, named DoneWhenA..D.
The source check reads the two files named in paper_evidence.json from the
directories listed in $W22SELECT_SOURCES (os.pathsep separated). There is
no default: when the variable is unset that check is skipped; when it is
set, both files must be found and match.
"""

import ast
import copy
import hashlib
import json
import os
import re
import unittest

import fixtures as F
import oracle as O
import revision_selectivity as R

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W22SELECT_SOURCES")
SLUG = "w22-revision-selectivity"
DAY_HEADER = "# experiments/2026-11-13\n"
ROW_START = "- [%s](%s/): " % (SLUG, SLUG)
FOOTER = "Do not merge experiment PRs without Ork review."
PIN = "c511a2a033336248c916dd9b7dc9ba2d72a64bbb"
# mutants.py sets this while a world mutant runs: the frozen digest, frozen
# expected table and README sync tests then skip, so a world mutant must be
# caught by the semantic tests, not by a hash.
WORLD_MUTANT = False
FIXTURE_DIGEST = "633213912274814963b5fe2973df43de9b8ef930a3a7ae14bc1f20dccb6f5252"


def day_readme():
    """Repo layout: ../README.md (when it starts with the day header).
    Flat draft: _day/README.md beside this file."""
    parent = os.path.join("..", "README.md")
    path = os.path.join(HERE, parent)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            if f.read().startswith(DAY_HEADER):
                return parent
    return os.path.join("_day", "README.md")


DAY = day_readme()
PY = ("revision_selectivity.py", "oracle.py", "fixtures.py",
      "test_revision_selectivity.py", "mutants.py")
ALL = PY + ("README.md", "NOTICE", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
PATHS = ("/work" + "space", "/t" + "mp", "/ho" + "me")
PAPER_NUMBERS = ("16" + ".1", "5" + ".2", "2" + ".4", "1,9" + "89", "19" + "89")
STDLIB = {"ast", "copy", "hashlib", "io", "json", "os", "re", "sys", "unittest",
          "revision_selectivity", "oracle", "fixtures", "test_revision_selectivity"}
# Tokens that would point at a model, a paid API or the network.
NETWORK_TOKENS = ("open" + "router", "url" + "lib", "sock" + "et", "http" + ".client",
                  "requ" + "ests", "api" + "_key", "open" + "ai", "anthro" + "pic",
                  "subpro" + "cess", "http" + "s://")
RULE = F.HELP_RULE


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def item_by_id(items, item_id):
    return next(x for x in items if x["id"] == item_id)


def trial(item, context, **extra):
    t = {"item": item["id"], "context": context, "argument": item["argument"]}
    t.update(extra)
    return t


def report(name):
    b = F.all_batches()[name]
    out = R.score(b["items"], b["trials"], RULE)
    assert out["status"] == R.OK, out
    return out


def block(rep, scope):
    return rep["disagreement"] if scope == "disagreement" else rep["by_context"][scope]


def raw_counts(batch, contexts):
    """Count reversals straight from the fixture rows (no module, no oracle)."""
    items = dict((x["id"], x) for x in batch["items"])
    wrong = right = 0
    for t in batch["trials"]:
        if t["context"] not in contexts:
            continue
        it = items[t["item"]]
        if t["final"] != it["initial"]:
            if it["initial"] == it["correct"]:
                right += 1
            else:
                wrong += 1
    return wrong, right


def digest():
    blob = json.dumps({"rule": F.HELP_RULE, "policy": F.POLICY_ITEMS, "batches": F.BATCHES},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


DIS = ("anonymous_disagree", "expert_label")


def own_row(text):
    """Only this PR's own row of a day README (sibling rows are not ours)."""
    return "\n".join(ln for ln in text.split("\n") if ln.startswith(ROW_START))


def scan_scope(name, text):
    """Hygiene scans read this PR's own row of the day README, all of any other file."""
    return own_row(text) if name == DAY else text


def banned_hits(text):
    low = text.lower()
    return [w for w in BANNED if w.lower() in low] + [p for p in PATHS if p in text]


def paper_number_hits(text):
    return [n for n in PAPER_NUMBERS if n in text]


class _Off(object):
    """Temporarily replace the module's exact-str key check with a no-op, to
    test that the validated snapshot alone still isolates the caller's objects."""

    def __enter__(self):
        self.saved = R._require_str_keys
        R._require_str_keys = lambda mapping, detail: None
        return self

    def __exit__(self, *exc):
        R._require_str_keys = self.saved
        return False


def hostile_key(field, action):
    """A non-str key whose hash equals `field`; once armed, its __eq__ runs
    `action` the first time it is called."""
    class Key(object):
        armed = False
        fired = 0

        def __hash__(self):
            return hash(field)

        def __eq__(self, other):
            if Key.armed and not Key.fired:
                Key.fired = 1
                action()
            return False
    return Key


def with_key(key_cls, t):
    d = {key_cls(): "spoof"}
    d.update(t)
    key_cls.armed = True
    return d


def attack_a1():
    """Verifier A1: hurt batch; a key in trial 0 rewrites every item's initial."""
    b = copy.deepcopy(F.BATCHES["hurt"])

    def act():
        for it in b["items"]:
            it["initial"] = "C"
    key = hostile_key("item", act)
    b["trials"][0] = with_key(key, b["trials"][0])
    return R.score(b["items"], b["trials"], RULE), key


def attack_a2():
    """Verifier A2: decide(p02); a trial key rewrites the validated initial."""
    item = copy.deepcopy(item_by_id(F.POLICY_ITEMS, "p02"))

    def act():
        item["initial"] = "Z"
    key = hostile_key("item", act)
    return R.decide(item, with_key(key, trial(item, R.EXPERT))), key


class _Sub(str):
    pass


def attack_a3(context):
    """Verifier A3: on the expert trial only, a key fired by the "final" probe
    swaps evidence E1 to a str subclass of the other answer."""
    item = copy.deepcopy(item_by_id(F.POLICY_ITEMS, "p02"))

    def act():
        if context == R.EXPERT:
            item["evidence"]["E1"] = _Sub("B")
    key = hostile_key("final", act)
    return R.decide(item, with_key(key, trial(item, context))), key


class DoneWhenA_PrestigeBlind(unittest.TestCase):
    """(a) expert vs anonymous, same argument: no decision change."""

    def test_a_expert_vs_anonymous_same_argument_same_decision(self):
        for item in F.POLICY_ITEMS:
            anon = R.decide(item, trial(item, R.ANONYMOUS))
            expert = R.decide(item, trial(item, R.EXPERT))
            self.assertEqual(anon["status"], R.OK, item["id"])
            self.assertEqual((anon["decision"], anon["final"], anon["reason"]),
                             (expert["decision"], expert["final"], expert["reason"]), item["id"])

    def test_a_all_three_contexts_same_decision(self):
        for item in F.POLICY_ITEMS:
            got = set((R.decide(item, trial(item, c))["decision"]) for c in R.CONTEXTS)
            self.assertEqual(len(got), 1, item["id"])

    def test_a_source_words_on_the_trial_are_ignored(self):
        for item in F.POLICY_ITEMS:
            plain = R.decide(item, trial(item, R.ANONYMOUS))
            dressed = R.decide(item, trial(item, R.EXPERT, source="Prof. X, domain expert",
                                           credentials="board certified", confidence="certain"))
            self.assertEqual(plain["decision"], dressed["decision"], item["id"])

    def test_a_ungrounded_appeal_to_authority_retained_under_expert(self):
        for item_id in ("p03", "p08"):
            item = item_by_id(F.POLICY_ITEMS, item_id)
            rec = R.decide(item, trial(item, R.EXPERT))
            self.assertEqual((rec["decision"], rec["reason"]), (R.RETAIN, R.R_NO_CITATION))

    def test_a_policy_is_content_based_not_a_truth_oracle(self):
        item = item_by_id(F.POLICY_ITEMS, "p04")
        self.assertEqual(item["initial"], item["correct"])
        for c in R.CONTEXTS:
            rec = R.decide(item, trial(item, c))
            self.assertEqual(rec["decision"], R.REVISE)
            self.assertNotEqual(rec["final"], item["correct"])

    def test_a_second_pass_varies_only_context(self):
        out = R.second_pass(F.POLICY_ITEMS)
        self.assertEqual(out["status"], R.OK)
        self.assertEqual(len(out["trials"]), len(F.POLICY_ITEMS) * len(R.CONTEXTS))
        for item in F.POLICY_ITEMS:
            rows = [t for t in out["trials"] if t["item"] == item["id"]]
            self.assertEqual(sorted(t["context"] for t in rows), sorted(R.CONTEXTS))
            self.assertEqual(set(t["argument"] for t in rows), {item["argument"]})
            self.assertEqual(len(set(t["final"] for t in rows)), 1, item["id"])

    def test_a_render_differs_only_in_frame_line(self):
        for item in F.POLICY_ITEMS:
            texts = [R.render(item, c).split("\n") for c in R.CONTEXTS]
            for lines in texts:
                self.assertEqual(lines[3], item["argument"])
            for i in (0, 1, 3):
                self.assertEqual(len(set(t[i] for t in texts)), 1)
            self.assertEqual(len(set(t[2] for t in texts)), 3)
        self.assertIn("expert", R.FRAMES[R.EXPERT])
        self.assertNotIn("expert", R.FRAMES[R.ANONYMOUS])

    def test_a_policy_batch_has_no_prestige_flips(self):
        rep = report("policy")
        self.assertEqual(rep["prestige"]["paired"], len(F.POLICY_ITEMS))
        self.assertEqual(rep["prestige"]["flips"], ())
        anon, expert = rep["by_context"][R.ANONYMOUS], rep["by_context"][R.EXPERT]
        self.assertEqual(anon, expert)

    def test_a_decide_never_reads_the_context(self):
        tree = ast.parse(read("revision_selectivity.py"))
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_decide")
        self.assertEqual([a.arg for a in fn.args.args], ["item", "argument"])
        names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        for bad in ("context", "EXPERT", "ANONYMOUS", "NEUTRAL", "FRAMES", "trial"):
            self.assertNotIn(bad, names)

    def test_a_unpaired_argument_is_config_error(self):
        item = item_by_id(F.POLICY_ITEMS, "p03")
        rec = R.decide(item, trial(item, R.EXPERT, argument="Record [E1] points to A."))
        self.assertEqual((rec["status"], rec["reason"], rec["detail"]),
                         (R.REJECT, R.CONFIG_ERROR, "unpaired_argument"))
        b = copy.deepcopy(F.BATCHES["hurt"])
        b["trials"][-1]["argument"] += " (said by an expert)"
        out = R.score(b["items"], b["trials"], RULE)
        self.assertEqual((out["status"], out["detail"]), (R.REJECT, "unpaired_argument"))

    def test_a_audit_flags_a_label_sensitive_log(self):
        rep = report("hurt")
        p = rep["prestige"]
        self.assertEqual(p["paired"], 10)
        self.assertGreaterEqual(len(p["expert_only_reversals"]), 3)
        self.assertGreater(len(p["expert_only_reversals"]), len(p["anonymous_only_reversals"]))
        self.assertEqual(set(p["flips"]),
                         set(p["expert_only_reversals"]) | set(p["anonymous_only_reversals"]))
        self.assertGreater(rep["by_context"][R.EXPERT]["reversals"],
                           rep["by_context"][R.ANONYMOUS]["reversals"])

    def test_a_expected_decisions(self):
        if WORLD_MUTANT:
            self.skipTest("world mutant")
        for item in F.POLICY_ITEMS:
            rec = R.decide(item, trial(item, R.NEUTRAL))
            self.assertEqual((rec["decision"], rec["reason"]), F.EXPECTED_DECISIONS[item["id"]])
        reasons = set(v[1] for v in F.EXPECTED_DECISIONS.values())
        self.assertEqual(reasons, {R.R_GROUNDED, R.R_NO_CITATION, R.R_UNKNOWN,
                                   R.R_SUPPORTS_INITIAL})


class DoneWhenB_DeclaredThreshold(unittest.TestCase):
    """(b) mostly-correct reversals cannot be reported as helped; mostly-wrong can."""

    def test_b_mostly_reverses_correct_initials_not_helped(self):
        w, c = raw_counts(F.BATCHES["hurt"], DIS)
        self.assertGreater(c, w)
        self.assertGreater(c, (w + c) // 2)
        d = report("hurt")["disagreement"]
        self.assertEqual((d["wrong_reversals"], d["correct_reversals"]), (w, c))
        self.assertGreater(d["reversals"], 0)
        self.assertFalse(d["helped"])
        self.assertEqual(d["claim"], R.NOT_HELPED)

    def test_b_mostly_reverses_wrong_initials_helped(self):
        w, c = raw_counts(F.BATCHES["helped"], DIS)
        self.assertGreater(w, (w + c) // 2)
        self.assertGreater(w, RULE["min_wrong_per_correct"] * c)
        d = report("helped")["disagreement"]
        self.assertTrue(d["helped"])
        self.assertEqual(d["claim"], R.HELPED)

    def test_b_reversal_counts_alone_do_not_decide(self):
        hurt, helped = report("hurt")["disagreement"], report("helped")["disagreement"]
        self.assertGreater(hurt["reversals"], helped["reversals"])
        self.assertGreater(hurt["reversals"], RULE["min_wrong_per_correct"])
        self.assertFalse(hurt["helped"])
        self.assertTrue(helped["helped"])

    def test_b_border_net_gain_but_threshold_not_cleared(self):
        d = report("border")["disagreement"]
        k = RULE["min_wrong_per_correct"]
        self.assertEqual(d["wrong_reversals"], k * d["correct_reversals"])
        self.assertGreater(d["net"], 0)
        self.assertGreater(d["wrong_reversals"], d["correct_reversals"])
        self.assertFalse(d["helped"])

    def test_b_threshold_sweep_matches_rule(self):
        for name, b in F.all_batches().items():
            for k in range(1, 9):
                rep = R.score(b["items"], b["trials"], {"min_wrong_per_correct": k})
                for scope in F.SCOPES:
                    blk = block(rep, scope)
                    self.assertEqual(blk["helped"],
                                     blk["wrong_reversals"] > k * blk["correct_reversals"],
                                     (name, k, scope))

    def test_b_binary_net_is_wrong_minus_correct_reversals(self):
        for name in F.all_batches():
            rep = report(name)
            for scope in F.SCOPES:
                blk = block(rep, scope)
                self.assertEqual(blk["net"], blk["wrong_reversals"] - blk["correct_reversals"])
                self.assertEqual(blk["reversals"], blk["wrong_reversals"] + blk["correct_reversals"])

    def test_b_threshold_is_declared_in_fixtures(self):
        self.assertEqual(set(F.HELP_RULE), {R.RULE_KEY})
        self.assertIs(type(F.HELP_RULE[R.RULE_KEY]), int)
        self.assertGreaterEqual(F.HELP_RULE[R.RULE_KEY], 1)
        self.assertEqual(report("helped")["help_rule"], F.HELP_RULE)

    def test_b_missing_help_rule_is_config_error(self):
        b = F.BATCHES["helped"]
        for rule in (None, {}, [], {"min_wrong": 3}):
            out = R.score(b["items"], b["trials"], rule)
            self.assertEqual((out["status"], out["reason"]), (R.REJECT, R.CONFIG_ERROR), rule)
            self.assertNotIn("disagreement", out)

    def test_b_bad_help_rule_values(self):
        b = F.BATCHES["helped"]
        for value in (0, -1, True, False, 3.0, "3", None):
            out = R.score(b["items"], b["trials"], {R.RULE_KEY: value})
            self.assertEqual(out["status"], R.REJECT, value)
        out = R.score(b["items"], b["trials"], {R.RULE_KEY: 3, "binary_bar": True})
        self.assertEqual((out["status"], out["detail"]), (R.REJECT, "help_rule_unknown_key"))

    def test_b_empty_scope_is_not_helped(self):
        n = report("hurt")["neutral"]
        self.assertEqual((n["n"], n["reversals"], n["helped"]), (0, 0, False))


class DoneWhenC_NeutralSeparate(unittest.TestCase):
    """(c) neutral reflection is scored separately from disagreement."""

    def test_c_neutral_helped_disagreement_not(self):
        rep = report("mixed")
        self.assertTrue(rep["neutral"]["helped"])
        self.assertFalse(rep["disagreement"]["helped"])
        w, c = raw_counts(F.BATCHES["mixed"], ("neutral",))
        self.assertEqual((rep["neutral"]["wrong_reversals"], rep["neutral"]["correct_reversals"]),
                         (w, c))
        # pooled, the neutral rows would push disagreement over the threshold
        w2, c2 = raw_counts(F.BATCHES["mixed"], R.CONTEXTS)
        self.assertGreater(w2, RULE["min_wrong_per_correct"] * c2)

    def test_c_disagreement_unchanged_when_neutral_rows_dropped(self):
        for name, b in F.all_batches().items():
            full = R.score(b["items"], b["trials"], RULE)
            only = [t for t in b["trials"] if t["context"] != R.NEUTRAL]
            part = R.score(b["items"], only, RULE)
            self.assertEqual(full["disagreement"], part["disagreement"], name)
            self.assertEqual(part["neutral"]["n"], 0)

    def test_c_disagreement_pools_exactly_anonymous_and_expert(self):
        for name in F.all_batches():
            rep = report(name)
            for key in ("n", "reversals", "wrong_reversals", "correct_reversals", "net"):
                self.assertEqual(rep["disagreement"][key],
                                 rep["by_context"][R.ANONYMOUS][key] + rep["by_context"][R.EXPERT][key],
                                 (name, key))
            self.assertEqual(rep["neutral"], rep["by_context"][R.NEUTRAL])

    def test_c_neutral_rows_only_in_neutral_scope(self):
        b = F.BATCHES["mixed"]
        only = [t for t in b["trials"] if t["context"] == R.NEUTRAL]
        rep = R.score(b["items"], only, RULE)
        self.assertEqual(rep["disagreement"]["n"], 0)
        self.assertEqual(rep["neutral"]["n"], len(only))
        self.assertEqual(rep["prestige"]["paired"], 0)


class DoneWhenD_NoModelNoNetwork(unittest.TestCase):
    """(d) no LLM, no OpenRouter, no network; paper figures on_unmeasured."""

    def test_d_stdlib_only_imports(self):
        for name in PY:
            for n in ast.walk(ast.parse(read(name))):
                if isinstance(n, ast.Import):
                    for a in n.names:
                        self.assertIn(a.name.split(".")[0], STDLIB, (name, a.name))
                elif isinstance(n, ast.ImportFrom):
                    self.assertIn((n.module or "").split(".")[0], STDLIB, name)

    def test_d_module_imports_nothing(self):
        tree = ast.parse(read("revision_selectivity.py"))
        self.assertEqual([n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))], [])
        calls = {n.func.id for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        for bad in ("open", "exec", "eval", "__import__", "compile", "input"):
            self.assertNotIn(bad, calls)

    def test_d_no_model_or_network_tokens_in_code(self):
        for name in ("revision_selectivity.py", "oracle.py", "fixtures.py", "mutants.py"):
            low = read(name).lower()
            for tok in NETWORK_TOKENS:
                self.assertNotIn(tok, low, (name, tok))

    def test_d_paper_results_on_unmeasured(self):
        self.assertEqual(R.paper_results()["status"], "on_unmeasured")

    def test_d_paper_numbers_only_in_evidence(self):
        for name in ALL:
            if name in ("paper_evidence.json", "test_revision_selectivity.py"):
                continue
            self.assertEqual(paper_number_hits(scan_scope(name, read(name))), [], name)

    def test_d_paper_evidence_unverified_on_unmeasured(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.16694")
        self.assertEqual(ev["paper"]["authors"], ["Yupeng Tang", "Mingfeng Lin"])
        self.assertIn("CC BY 4.0", ev["paper"]["licence"])
        up = ev["upstream_code"]
        self.assertEqual(up["pin"], PIN)
        self.assertIs(up["cloned"], False)
        self.assertIs(up["run"], False)
        self.assertIn("UNVERIFIED", up["status"])
        self.assertIn("W22SELECT_SOURCES", ev["env"])
        files = {s["file"] for s in ev["sources"]}
        for s in ev["sources"]:
            self.assertRegex(s["sha256"], r"^[0-9a-f]{64}$")
            self.assertIs(type(s["chars"]), int)
        for c in ev["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED", c["id"])
            self.assertEqual(c["measurement"], "on_unmeasured", c["id"])
            self.assertIn(c["source"], files)
            self.assertEqual(len(c["quote"]), c["length"], c["id"])
        quotes = " ".join(c["quote"] for c in ev["claims"])
        for n in PAPER_NUMBERS[:4]:
            self.assertIn(n, quotes)
        bar = next(c for c in ev["claims"] if c["id"] == "P3")
        self.assertIs(bar["imported"], False)
        self.assertEqual(sorted(ev["on_unmeasured"]), ["P4", "P5"])

    def test_d_quotes_exact_in_sources(self):
        if not SOURCES:
            self.skipTest("W22SELECT_SOURCES not set")
        ev = json.loads(read("paper_evidence.json"))
        texts = {}
        for s in ev["sources"]:
            found = [os.path.join(d, s["file"]) for d in SOURCES.split(os.pathsep)
                     if os.path.isfile(os.path.join(d, s["file"]))]
            self.assertTrue(found, s["file"])
            with open(found[0], "rb") as f:
                raw = f.read()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), s["sha256"], s["file"])
            texts[s["file"]] = raw.decode("utf-8")
            self.assertEqual(len(texts[s["file"]]), s["chars"], s["file"])
        for c in ev["claims"]:
            text = texts[c["source"]]
            self.assertEqual(text[c["offset"]:c["offset"] + c["length"]], c["quote"], c["id"])


def norm_oracle(o):
    out = {}
    for scope in F.SCOPES:
        c = o[scope]
        out[scope] = (c["n"], c["initial_correct"], c["final_correct"], c["net"], c["reversals"],
                      c["wrong_reversals"], c["correct_reversals"], c["helped"])
    out["prestige"] = (o["paired"], o["flips"], o["expert_only"], o["anonymous_only"])
    return out


def norm_module(rep):
    out = {}
    for scope in F.SCOPES:
        b = block(rep, scope)
        out[scope] = (b["n"], b["initial_correct"], b["final_correct"], b["net"], b["reversals"],
                      b["wrong_reversals"], b["correct_reversals"], b["helped"])
    p = rep["prestige"]
    out["prestige"] = (p["paired"], p["flips"], p["expert_only_reversals"],
                       p["anonymous_only_reversals"])
    return out


class OracleAgreement(unittest.TestCase):

    def test_decide_matches_oracle(self):
        for item in F.POLICY_ITEMS + [x for b in F.BATCHES.values() for x in b["items"]]:
            for c in R.CONTEXTS:
                rec = R.decide(item, trial(item, c))
                self.assertEqual((rec["decision"], rec["reason"], rec["final"]),
                                 O.decide(item, item["argument"]), (item["id"], c))

    def test_score_matches_oracle(self):
        for name, b in F.all_batches().items():
            for k in range(1, 9):
                rep = R.score(b["items"], b["trials"], {"min_wrong_per_correct": k})
                self.assertEqual(norm_module(rep), norm_oracle(O.score(b["items"], b["trials"], k)),
                                 (name, k))

    def test_score_matches_oracle_on_context_subsets(self):
        for name, b in F.all_batches().items():
            for drop in R.CONTEXTS:
                trials = [t for t in b["trials"] if t["context"] != drop]
                rep = R.score(b["items"], trials, RULE)
                self.assertEqual(norm_module(rep), norm_oracle(O.score(b["items"], trials, 3)),
                                 (name, drop))

    def test_frozen_expected_table(self):
        if WORLD_MUTANT:
            self.skipTest("world mutant")
        for name, exp in F.EXPECTED_SCORES.items():
            rep = report(name)
            for scope in F.SCOPES:
                b = block(rep, scope)
                self.assertEqual((b["n"], b["wrong_reversals"], b["correct_reversals"], b["helped"]),
                                 exp[scope], (name, scope))
            self.assertEqual(rep["prestige"]["flips"], exp["flips"], name)

    def test_frozen_fixture_digest(self):
        if WORLD_MUTANT:
            self.skipTest("world mutant")
        self.assertEqual(digest(), FIXTURE_DIGEST)

    def test_oracle_is_a_separate_code_path(self):
        tree = ast.parse(read("oracle.py"))
        mods = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods += [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                mods.append(n.module)
        self.assertEqual(mods, ["re"])
        body = [n for n in tree.body
                if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
        code_text = "\n".join(ast.unparse(n) for n in body)
        self.assertNotIn("revision_selectivity", code_text)
        self.assertNotIn("_decide", code_text)


class Validation(unittest.TestCase):

    def test_bad_items(self):
        good = F.POLICY_ITEMS[0]
        bads = [None, [], "x"]
        for key in R.ITEM_KEYS:
            x = copy.deepcopy(good)
            del x[key]
            bads.append(x)
        for key, value in (("id", ""), ("correct", "C"), ("initial", "a"), ("argument", " "),
                           ("evidence", []), ("evidence", {"E1": "C"}), ("question", 1)):
            x = copy.deepcopy(good)
            x[key] = value
            bads.append(x)

        class S(str):
            pass
        x = copy.deepcopy(good)
        x["correct"] = S("A")
        bads.append(x)
        for bad in bads:
            rec = R.decide(bad, {"item": "p01", "context": R.NEUTRAL, "argument": good["argument"]})
            self.assertEqual((rec["status"], rec["reason"]), (R.REJECT, R.CONFIG_ERROR), bad)
            out = R.score([bad], [], RULE)
            self.assertEqual(out["status"], R.REJECT, bad)

    def test_bad_trials(self):
        b = F.BATCHES["helped"]
        t0 = b["trials"][0]
        cases = [None, "x", {}]
        for key in ("item", "context", "argument", "final"):
            x = dict(t0)
            del x[key]
            cases.append(x)
        for key, value in (("item", "zz"), ("context", "expert"), ("context", "Expert_Label"),
                           ("final", "C"), ("argument", 1)):
            x = dict(t0)
            x[key] = value
            cases.append(x)
        for bad in cases:
            out = R.score(b["items"], [bad], RULE)
            self.assertEqual((out["status"], out["reason"]), (R.REJECT, R.CONFIG_ERROR), bad)
        self.assertEqual(R.score(b["items"], "x", RULE)["status"], R.REJECT)
        self.assertEqual(R.score([], [], RULE)["status"], R.REJECT)

    def test_duplicate_trial_and_item(self):
        b = F.BATCHES["helped"]
        out = R.score(b["items"], b["trials"] + [dict(b["trials"][0])], RULE)
        self.assertEqual((out["status"], out["detail"]), (R.REJECT, "duplicate_trial"))
        out = R.score(b["items"] + [b["items"][0]], b["trials"], RULE)
        self.assertEqual((out["status"], out["detail"]), (R.REJECT, "duplicate_item"))

    def test_trial_item_mismatch_in_decide(self):
        item = F.POLICY_ITEMS[0]
        rec = R.decide(item, {"item": "p02", "context": R.EXPERT, "argument": item["argument"]})
        self.assertEqual(rec["status"], R.REJECT)

    def test_inputs_not_mutated(self):
        before = copy.deepcopy((F.POLICY_ITEMS, F.BATCHES))
        for name, b in F.all_batches().items():
            R.score(b["items"], b["trials"], RULE)
        R.second_pass(F.POLICY_ITEMS)
        self.assertEqual(before, (F.POLICY_ITEMS, F.BATCHES))

    def test_citations(self):
        self.assertEqual(R.citations("a [E1] b [E2] c [x"), ("E1", "E2"))
        self.assertEqual(R.citations("none"), ())
        for item in F.POLICY_ITEMS:
            self.assertEqual(list(R.citations(item["argument"])),
                             re.findall(r"\[([^\]]*)\]", item["argument"]))


class R2_SnapshotIsolation(unittest.TestCase):
    """r2 F1: exact-str keys before any lookup; work only from the snapshot."""

    def test_a1_hurt_to_helped_rewrite_fails_closed(self):
        out, key = attack_a1()
        self.assertEqual((out["status"], out["reason"], out["detail"]),
                         (R.REJECT, R.CONFIG_ERROR, "trial_non_str_key"))
        self.assertEqual(key.fired, 0)

    def test_a2_initial_rewrite_fails_closed(self):
        rec, key = attack_a2()
        self.assertEqual((rec["status"], rec["reason"], rec["detail"]),
                         (R.REJECT, R.CONFIG_ERROR, "trial_non_str_key"))
        self.assertEqual(key.fired, 0)

    def test_a3_expert_only_evidence_swap_fails_closed(self):
        for c in R.CONTEXTS:
            rec, key = attack_a3(c)
            self.assertEqual((rec["status"], rec["reason"], rec["detail"]),
                             (R.REJECT, R.CONFIG_ERROR, "trial_non_str_key"), c)
            self.assertEqual(key.fired, 0, c)

    def test_a1_snapshot_alone_gives_honest_result(self):
        with _Off():
            out, key = attack_a1()
        self.assertEqual(key.fired, 1)
        self.assertEqual(out, report("hurt"))
        self.assertEqual(out["disagreement"]["claim"], R.NOT_HELPED)

    def test_a2_snapshot_alone_gives_honest_result(self):
        with _Off():
            rec, key = attack_a2()
        self.assertEqual(key.fired, 1)
        self.assertEqual((rec["status"], rec["decision"], rec["reason"], rec["final"]),
                         (R.OK, R.RETAIN, R.R_SUPPORTS_INITIAL, "A"))

    def test_a3_snapshot_alone_is_prestige_blind(self):
        got = []
        with _Off():
            for c in R.CONTEXTS:
                rec, key = attack_a3(c)
                self.assertEqual(rec["status"], R.OK, c)
                got.append((rec["decision"], rec["final"], rec["reason"]))
        self.assertEqual(got, [(R.RETAIN, "A", R.R_SUPPORTS_INITIAL)] * 3)

    def test_non_str_alias_keys_rejected(self):
        class Alias(object):
            def __init__(self, name):
                self.name = name

            def __hash__(self):
                return hash(self.name)

            def __eq__(self, other):
                return other == self.name
        b = F.BATCHES["hurt"]
        out = R.score(b["items"], b["trials"], {Alias(R.RULE_KEY): 3})
        self.assertEqual(out["detail"], "help_rule_non_str_key")
        item = F.POLICY_ITEMS[0]
        aliased = dict((Alias(k) if k == "evidence" else k, v) for k, v in item.items())
        self.assertEqual(R.decide(aliased, trial(item, R.NEUTRAL))["detail"], "item_non_str_key")
        self.assertEqual(R.score([aliased], [], RULE)["detail"], "item_non_str_key")
        t = dict((Alias(k) if k == "final" else k, v) for k, v in b["trials"][0].items())
        self.assertEqual(R.score(b["items"], [t], RULE)["detail"], "trial_non_str_key")

    def test_str_subclass_keys_rejected(self):
        item = F.POLICY_ITEMS[0]
        sub_item = dict((_Sub(k) if k == "id" else k, v) for k, v in item.items())
        self.assertEqual(R.decide(sub_item, trial(item, R.NEUTRAL))["detail"], "item_non_str_key")
        sub_trial = dict((_Sub(k) if k == "context" else k, v)
                         for k, v in trial(item, R.NEUTRAL).items())
        self.assertEqual(R.decide(item, sub_trial)["detail"], "trial_non_str_key")
        b = F.BATCHES["hurt"]
        out = R.score(b["items"], b["trials"], {_Sub(R.RULE_KEY): 3})
        self.assertEqual(out["detail"], "help_rule_non_str_key")

    def test_trial_snapshot_holds_only_trial_fields(self):
        item = F.POLICY_ITEMS[0]
        t = trial(item, R.EXPERT, source="expert", prestige="high", final="A")
        snap = R._snap_trial(t, False)
        self.assertEqual(set(snap), set(R.TRIAL_KEYS) | {"final"})
        self.assertIsNot(snap, t)
        snap_item = R._snap_item(item)
        self.assertEqual(snap_item, item)
        self.assertIsNot(snap_item, item)
        self.assertIsNot(snap_item["evidence"], item["evidence"])

    def test_snapshot_survives_later_caller_mutation(self):
        b = copy.deepcopy(F.BATCHES["hurt"])
        by_id, order = R._snap_items(b["items"])
        for it in b["items"]:
            it["initial"] = "C"
            it["evidence"].clear()
        self.assertEqual([x["initial"] for x in order],
                         [x["initial"] for x in F.BATCHES["hurt"]["items"]])
        self.assertEqual([x["evidence"] for x in order],
                         [x["evidence"] for x in F.BATCHES["hurt"]["items"]])


class R2_TypesAndPairing(unittest.TestCase):
    """r2 F5: one-field prestige leak, pairing in every context, subclasses,
    non-str evidence keys, never raises."""

    FIELDS = ("source", "speaker", "prestige", "role", "label", "authority",
              "credentials", "confidence", "expert", "attribution")
    VALUES = ("expert", "domain expert", R.EXPERT, R.ANONYMOUS, "Prof. X", "anonymous", "high")

    def test_one_field_prestige_leak(self):
        for item in F.POLICY_ITEMS:
            plain = R.decide(item, trial(item, R.ANONYMOUS))
            want = (plain["decision"], plain["final"], plain["reason"])
            for field in self.FIELDS:
                for value in self.VALUES:
                    for c in R.CONTEXTS:
                        rec = R.decide(item, trial(item, c, **{field: value}))
                        self.assertEqual((rec["decision"], rec["final"], rec["reason"]), want,
                                         (item["id"], field, value, c))

    def test_unpaired_argument_in_every_context(self):
        item = item_by_id(F.POLICY_ITEMS, "p03")
        for c in R.CONTEXTS:
            rec = R.decide(item, trial(item, c, argument=item["argument"] + " [E1]"))
            self.assertEqual(rec["detail"], "unpaired_argument", c)
        for name in ("mixed", "policy"):
            b = copy.deepcopy(F.all_batches()[name])
            for c in R.CONTEXTS:
                trials = copy.deepcopy(b["trials"])
                t = next(x for x in trials if x["context"] == c)
                t["argument"] += " (restated)"
                out = R.score(b["items"], trials, RULE)
                self.assertEqual((out["status"], out["detail"]),
                                 (R.REJECT, "unpaired_argument"), (name, c))

    def test_int_str_dict_list_subclasses_rejected(self):
        class I(int):
            pass

        class D(dict):
            pass

        class L(list):
            pass
        b = F.BATCHES["hurt"]
        item = F.POLICY_ITEMS[0]
        self.assertEqual(R.score(b["items"], b["trials"], {R.RULE_KEY: I(3)})["detail"],
                         "help_rule_bad_value")
        self.assertEqual(R.score(b["items"], b["trials"], D({R.RULE_KEY: 3}))["detail"],
                         "help_rule_missing")
        self.assertEqual(R.score(L(b["items"]), b["trials"], RULE)["detail"], "items_not_list")
        self.assertEqual(R.score(b["items"], L(b["trials"]), RULE)["detail"], "trials_not_list")
        for field, detail in (("item", "trial_bad_item"), ("context", "trial_bad_context"),
                              ("argument", "trial_bad_argument"), ("final", "trial_bad_final")):
            t = dict(b["trials"][0])
            t[field] = _Sub(t[field])
            self.assertEqual(R.score(b["items"], [t], RULE)["detail"], detail, field)
        for c in R.CONTEXTS:
            rec = R.decide(item, trial(item, _Sub(c)))
            self.assertEqual(rec["detail"], "trial_bad_context", c)
        self.assertEqual(R.decide(item, D(trial(item, R.NEUTRAL)))["detail"], "trial_not_dict")
        self.assertEqual(R.decide(D(item), trial(item, R.NEUTRAL))["detail"], "item_not_dict")
        self.assertEqual(R.score(b["items"], [D(b["trials"][0])], RULE)["detail"], "trial_not_dict")
        for field in ("id", "question", "argument", "correct", "initial"):
            x = copy.deepcopy(item)
            x[field] = _Sub(x[field])
            self.assertEqual(R.decide(x, trial(item, R.NEUTRAL))["detail"], "item_bad_" + field)
        for ev in (D(item["evidence"]), {"E1": _Sub("B")}, {"E1": True}, {"": "B"}):
            x = copy.deepcopy(item)
            x["evidence"] = ev
            self.assertEqual(R.decide(x, trial(item, R.NEUTRAL))["detail"], "item_bad_evidence", ev)

    def test_non_str_evidence_keys_rejected(self):
        item = F.POLICY_ITEMS[0]
        for key in (1, (1,), b"E1", None, 1.5, _Sub("E9")):
            x = copy.deepcopy(item)
            x["evidence"] = dict(x["evidence"])
            x["evidence"][key] = "B"
            rec = R.decide(x, trial(item, R.NEUTRAL))
            self.assertEqual((rec["status"], rec["detail"]),
                             (R.REJECT, "item_evidence_non_str_key"), key)
            out = R.score([x], [], RULE)
            self.assertEqual(out["detail"], "item_evidence_non_str_key", key)

    def test_internal_error_is_config_error_not_raised(self):
        saved = R.citations

        def boom(text):
            raise RuntimeError("forced")
        R.citations = boom
        try:
            item = F.POLICY_ITEMS[0]
            self.assertEqual(R.decide(item, trial(item, R.EXPERT)),
                             {"status": R.REJECT, "reason": R.CONFIG_ERROR, "detail": "internal"})
            self.assertEqual(R.second_pass(F.POLICY_ITEMS)["detail"], "internal")
        finally:
            R.citations = saved

    def test_render_validates_its_input(self):
        item = F.POLICY_ITEMS[0]
        for bad_item, c in ((None, R.NEUTRAL), (dict(item, initial="C"), R.NEUTRAL),
                            (item, "expert"), (item, _Sub(R.EXPERT))):
            with self.assertRaises(ValueError):
                R.render(bad_item, c)


class Hygiene(unittest.TestCase):

    def test_files_present(self):
        for name in ALL:
            self.assertTrue(os.path.isfile(os.path.join(HERE, name)), name)

    def test_banned_words_paths_markers(self):
        for name in ALL:
            text = read(name)
            self.assertEqual(banned_hits(scan_scope(name, text)), [], name)
            self.assertIsNone(re.search(r"^(<{7}|>{7}|={7})( |$)", text, re.M), name)

    def test_day_scans_read_only_this_row(self):
        dirty = " ".join(BANNED + PATHS + PAPER_NUMBERS)
        mine = ROW_START + "clean row text"
        sibling = "- [other-slug](other-slug/): " + dirty
        day = DAY_HEADER + "\n" + sibling + "\n" + mine + "\n\n" + FOOTER + "\n"
        self.assertEqual(own_row(day), mine)
        self.assertEqual(banned_hits(scan_scope(DAY, day)), [])
        self.assertEqual(paper_number_hits(scan_scope(DAY, day)), [])
        dirty_day = day.replace(mine, mine + " " + dirty)
        self.assertEqual(banned_hits(scan_scope(DAY, dirty_day)), list(BANNED + PATHS))
        self.assertEqual(paper_number_hits(scan_scope(DAY, dirty_day)), list(PAPER_NUMBERS))
        # every other file is scanned whole
        self.assertEqual(scan_scope("README.md", day), day)
        self.assertEqual(len(own_row(read(DAY)).split("\n")), 1)

    def test_day_readme(self):
        text = read(DAY)
        self.assertTrue(text.startswith(DAY_HEADER + "\n"))
        rows = [ln for ln in text.split("\n") if ln.startswith(ROW_START)]
        self.assertEqual(len(rows), 1)
        self.assertIn("[arXiv 2611.16694](https://arxiv.org/abs/2611.16694)", rows[0])
        self.assertTrue(rows[0].endswith("; not a reproduction)"))
        self.assertIn("(Top method sketch of ", rows[0])
        self.assertTrue(text.endswith("\n\n" + FOOTER + "\n"))
        self.assertEqual(text.count(FOOTER), 1)

    def test_folder_readme(self):
        text = read("README.md")
        self.assertTrue(text.startswith("# %s\n" % SLUG))
        for head in ("## Run", "## Results", "## Done-when", "## Limits"):
            self.assertIn("\n" + head + "\n", text)
        for phrase in ("UNVERIFIED", "not a reproduction", "Top method sketch",
                       "python3 -B -m unittest", "python3 -B mutants.py", "paper_evidence.json"):
            self.assertIn(phrase, text)

    def test_notice(self):
        text = read("NOTICE")
        for phrase in ("When Expert Disagreement Hurts: Prestige and Selectivity in LLM",
                       "Yupeng Tang", "Mingfeng Lin", "arXiv:2611.16694",
                       "https://arxiv.org/abs/2611.16694", "CC BY 4.0", "MIT", PIN,
                       "not cloned, not run", "clean-room"):
            self.assertIn(phrase, text)

    def test_readme_matches_summary(self):
        if WORLD_MUTANT:
            self.skipTest("world mutant")
        text = read("README.md")
        for line in F.summary().split("\n"):
            self.assertIn(line, text)

    def test_summary_deterministic(self):
        self.assertEqual(F.summary(), F.summary())


if __name__ == "__main__":
    unittest.main()
