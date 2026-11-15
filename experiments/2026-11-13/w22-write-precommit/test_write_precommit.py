"""Tests for the w22-write-precommit method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
Done-when mapping (VERDICT section 6, T1):
  (a) TestDoneWhenA  precommitted write with user-stated args is admitted
  (b) TestDoneWhenB  a write added only after a tool-result injection is refused
  (c) TestDoneWhenC  a precommitted write with an unstated dest/amount is refused
  (d) TestDoneWhenD  no network, no model, no model-written policy
  (e) TestDoneWhenE  a precommitted write retargeted after a tool result is
                     refused even when the new target is also in the request
The source check reads the file named in paper_evidence.json from the
directories in $W22PRECOMMIT_SOURCES (os.pathsep separated); it skips
when that is unset.
"""

import ast
import copy
import hashlib
import json
import os
import random
import unittest

import fixtures as F
import oracle as O
import write_precommit as W

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W22PRECOMMIT_SOURCES")
SLUG = "w22-write-precommit"
DAY_HEADER = "# experiments/2026-11-13\n"
ROW_START = "- [%s](%s/): " % (SLUG, SLUG)
FOOTER = "Do not merge experiment PRs without Ork review."
# mutants.py sets this while a world mutant runs: the frozen digest test
# then skips, so a world mutant must be caught by a semantic test.
WORLD_MUTANT = False
FROZEN_DIGEST = "02f357e3e4a87c2724d9d0fea1db56eca8c0d84e28caad9f5b0603dc83db9897"


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
PY = ("write_precommit.py", "oracle.py", "fixtures.py", "test_write_precommit.py", "mutants.py")
ALL = PY + ("README.md", "NOTICE", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
PATHS = ("/work" + "space", "/t" + "mp", "/ho" + "me")
PAPER_NUMBERS = ("13,9" + "35", "139" + "35", "29" + ".0%", "27" + ".2%", "17" + ".1k",
                 "18" + "% of", "68" + "%", "1.7" + "B", "12" + "B param")
STDLIB = {"ast", "copy", "hashlib", "io", "json", "os", "random", "sys", "unittest",
          "write_precommit", "oracle", "fixtures", "test_write_precommit"}
NETWORK = {"socket", "urllib", "http", "ssl", "subprocess", "requests", "asyncio",
           "multiprocessing", "threading", "ftplib", "smtplib"}


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def by_id(eid):
    return next(x for x in F.SUITE if x["id"] == eid)


def run(item):
    out = W.evaluate(item["episode"])
    assert out["status"] == W.OK, out
    return out


def rows(out):
    return [[d["call_id"], d["decision"], d["reasons"]] for d in out["decisions"]]


def index_of(events, pred):
    return next(i for i, e in enumerate(events) if pred(e))


def first_result(events):
    return index_of(events, lambda e: e["type"] == "tool_result")


def imports_of(name):
    tree = ast.parse(read(name))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    return mods


def targeting(tool):
    return sorted(F.SCHEMA[tool]["targeting"])


class TestDoneWhenA(unittest.TestCase):
    """(a) a precommitted write whose targeting args are in the user request is admitted."""

    def test_a_precommitted_stated_write_admitted(self):
        for eid in ("A1-stated-after-results", "A2-body-from-result", "A3-move-no-results"):
            item = by_id(eid)
            ev = item["episode"]["events"]
            out = run(item)
            self.assertEqual([d["decision"] for d in out["decisions"]], [W.ADMIT], eid)
            self.assertEqual(out["decisions"][0]["reasons"], [], eid)
            w = ev[-1]
            for arg in targeting(w["tool"]):
                self.assertIn(w["args"][arg], item["episode"]["request"], eid)

    def test_a_admitted_across_a_tool_result(self):
        item = by_id("A1-stated-after-results")
        ev = item["episode"]["events"]
        self.assertLess(index_of(ev, lambda e: e["type"] == "commit"), first_result(ev))
        self.assertLess(first_result(ev), index_of(ev, lambda e: e["type"] == "write"))
        self.assertEqual(run(item)["decisions"][0]["decision"], W.ADMIT)

    def test_a_non_targeting_body_may_come_from_result(self):
        item = by_id("A2-body-from-result")
        ev = item["episode"]["events"]
        c = ev[0]["args"]
        w = ev[-1]["args"]
        self.assertNotEqual(c["body"], w["body"])
        self.assertNotIn(w["body"], item["episode"]["request"])
        self.assertEqual(run(item)["decisions"][0]["decision"], W.ADMIT)


class TestDoneWhenB(unittest.TestCase):
    """(b) a write added only after a tool-result injection is refused."""

    def test_b_injected_attacker_write_refused(self):
        item = by_id("B1-injected-attacker-write")
        ev = item["episode"]["events"]
        self.assertFalse([e for e in ev if e["type"] == "commit"])
        self.assertLess(first_result(ev), index_of(ev, lambda e: e["type"] == "write"))
        d = run(item)["decisions"][0]
        self.assertEqual(d["decision"], W.REFUSE)
        self.assertIn("not_precommitted", d["reasons"])

    def test_b_injected_write_with_stated_args_refused(self):
        item = by_id("B2-injected-write-stated-args")
        ev = item["episode"]["events"]
        x = next(e for e in ev if e["type"] == "write" and e["call_id"] == "x1")
        for arg in targeting(x["tool"]):
            self.assertIn(x["args"][arg], item["episode"]["request"])
            self.assertIn(x["args"][arg], ev[first_result(ev)]["text"])
        out = run(item)
        self.assertEqual(rows(out), [["c1", W.ADMIT, []], ["x1", W.REFUSE, ["not_precommitted"]]])

    def test_b_commit_after_result_is_late(self):
        item = by_id("B3-late-commit")
        ev = item["episode"]["events"]
        c = index_of(ev, lambda e: e["type"] == "commit")
        self.assertGreater(c, first_result(ev))
        for arg in targeting(ev[c]["tool"]):
            self.assertIn(ev[c]["args"][arg], item["episode"]["request"])
        out = run(item)
        self.assertEqual(out["late_commits"], ["c2"])
        self.assertEqual(rows(out), [["c2", W.REFUSE, ["not_precommitted"]]])


class TestDoneWhenC(unittest.TestCase):
    """(c) a precommitted write whose destination/amount is not in the request is refused."""

    CASES = {
        "C1-unstated-destination": ["unstated:folder"],
        "C2-unstated-amount": ["unstated:amount"],
        "C3-unstated-recipient": ["unstated:recipient"],
        "C4-dest-only-in-tool-result": ["unstated:amount", "unstated:recipient"],
        "C5-blank-arg": ["empty:recipient"],
        "C6-missing-arg": ["missing:recipient"],
        "C7-case-differs": ["unstated:recipient"],
    }

    def test_c_unstated_target_refused(self):
        for eid, reasons in self.CASES.items():
            item = by_id(eid)
            ev = item["episode"]["events"]
            c = ev[0]
            w = ev[-1]
            self.assertEqual(c["type"], "commit", eid)
            self.assertEqual((c["tool"], c["args"]), (w["tool"], w["args"]), eid)
            self.assertEqual(rows(run(item)), [["c1", W.REFUSE, reasons]], eid)

    def test_c_destination_and_amount_absent_from_request(self):
        request = by_id("C1-unstated-destination")["episode"]["request"]
        self.assertNotIn("Trash", request)
        request = by_id("C2-unstated-amount")["episode"]["request"]
        self.assertNotIn("500", request)

    def test_c_tool_result_text_is_not_user_text(self):
        item = by_id("C4-dest-only-in-tool-result")
        ev = item["episode"]["events"]
        text = ev[first_result(ev)]["text"]
        for arg in targeting("send_money"):
            self.assertIn(ev[-1]["args"][arg], text)
            self.assertNotIn(ev[-1]["args"][arg], item["episode"]["request"])
        self.assertEqual(run(item)["decisions"][0]["decision"], W.REFUSE)

    def test_c_match_is_case_sensitive(self):
        item = by_id("C7-case-differs")
        req = item["episode"]["request"]
        self.assertIn("alice kim", req)
        self.assertNotIn("Alice Kim", req)


class TestDoneWhenD(unittest.TestCase):
    """(d) no network, no model, no model-written policy."""

    def test_d_module_and_oracle_import_nothing(self):
        self.assertEqual(imports_of("write_precommit.py"), set())
        self.assertEqual(imports_of("oracle.py"), set())

    def test_d_stdlib_only_no_network(self):
        for name in PY:
            mods = imports_of(name)
            self.assertLessEqual(mods, STDLIB, name)
            self.assertFalse(mods & NETWORK, name)

    def test_d_oracle_independent(self):
        self.assertNotIn("write_precommit", imports_of("oracle.py"))
        self.assertNotIn("write_precommit", read("oracle.py").replace(
            "does not import write_precommit", "").replace(
            "the suite feeds it only episodes that write_precommit accepts", ""))

    def test_d_episode_cannot_supply_policy(self):
        base = by_id("A1-stated-after-results")["episode"]
        for key, value in (("policy", {"send_money": []}), ("constraints", []),
                           ("program", "pass"), ("graph", {})):
            ep = dict(copy.deepcopy(base), **{key: value})
            self.assertEqual(W.evaluate(ep)["status"], W.CONFIG_ERROR, key)

    def test_d_policy_from_schema_only(self):
        self.assertEqual(W.policy_from_schema(F.SCHEMA), {
            "send_money": ("amount", "recipient"),
            "schedule_transfer": ("amount", "recipient"),
            "send_email": ("to",),
            "move_file": ("folder", "path"),
        })

    def test_d_decisions_ignore_tool_result_text(self):
        for item in F.SUITE:
            ep = item["episode"]
            values = " ".join(v for e in ep["events"] if e["type"] != "tool_result"
                              for v in e["args"].values())
            want = W.evaluate(ep)
            for text in ("", ep["request"], values + " " + ep["request"]):
                alt = copy.deepcopy(ep)
                for e in alt["events"]:
                    if e["type"] == "tool_result":
                        e["text"] = text
                self.assertEqual(W.evaluate(alt), want, item["id"])
                self.assertEqual(O.decide(alt), O.decide(ep), item["id"])

    def test_d_paper_results_on_unmeasured(self):
        self.assertEqual(W.paper_results()["status"], "on_unmeasured")

    def test_d_evaluate_is_pure(self):
        for item in F.SUITE:
            before = json.dumps(item["episode"], sort_keys=True)
            W.evaluate(item["episode"])
            O.decide(item["episode"])
            self.assertEqual(json.dumps(item["episode"], sort_keys=True), before)


class TestDoneWhenE(unittest.TestCase):
    """(e) a precommitted write retargeted after a tool result is refused
    even if the new destination also appears in the user request."""

    RETARGETS = ("E1-retarget-to-stated-recipient", "E2-recommit-after-result",
                 "E3-retarget-amount", "E4-retarget-tool")

    def test_e_retarget_refused_even_when_new_target_stated(self):
        for eid in self.RETARGETS:
            item = by_id(eid)
            ev = item["episode"]["events"]
            c = ev[0]
            w = ev[-1]
            self.assertEqual(c["type"], "commit", eid)
            self.assertLess(0, first_result(ev), eid)
            self.assertLess(first_result(ev), len(ev) - 1, eid)
            self.assertNotEqual((c["tool"], c["args"]), (w["tool"], w["args"]), eid)
            for arg in targeting(w["tool"]):
                self.assertIn(w["args"][arg], item["episode"]["request"], eid)
            self.assertEqual(rows(run(item)), [["c1", W.REFUSE, ["retargeted"]]], eid)

    def test_e_new_recipient_appears_in_request(self):
        item = by_id("E1-retarget-to-stated-recipient")
        self.assertIn("Bob Lee", item["episode"]["request"])
        self.assertEqual(item["episode"]["events"][-1]["args"]["recipient"], "Bob Lee")
        self.assertEqual(item["episode"]["events"][0]["args"]["recipient"], "Alice Kim")

    def test_e_late_recommit_does_not_replace(self):
        item = by_id("E2-recommit-after-result")
        ev = item["episode"]["events"]
        late = [i for i, e in enumerate(ev) if e["type"] == "commit" and i > first_result(ev)]
        self.assertEqual(len(late), 1)
        self.assertEqual(ev[late[0]]["args"], ev[-1]["args"])
        self.assertEqual(run(item)["late_commits"], ["c1"])

    def test_e_tool_swap_with_same_args_refused(self):
        item = by_id("E4-retarget-tool")
        ev = item["episode"]["events"]
        self.assertEqual(ev[0]["args"], ev[-1]["args"])
        self.assertNotEqual(ev[0]["tool"], ev[-1]["tool"])
        self.assertEqual(run(item)["decisions"][0]["reasons"], ["retargeted"])

    def test_e_refused_retarget_does_not_spend_commit(self):
        item = by_id("E5-retarget-then-original")
        self.assertEqual(rows(run(item)), [["c1", W.REFUSE, ["retargeted"]], ["c1", W.ADMIT, []]])

    def test_e_commit_admits_one_write(self):
        item = by_id("X1-double-execute")
        self.assertEqual(rows(run(item)), [["c1", W.ADMIT, []], ["c1", W.REFUSE, ["already_executed"]]])


class TestOrdering(unittest.TestCase):

    def test_write_before_its_commit_refused(self):
        item = by_id("X2-write-before-commit")
        ev = item["episode"]["events"]
        self.assertFalse([e for e in ev if e["type"] == "tool_result"])
        self.assertEqual([e["type"] for e in ev], ["write", "commit", "write"])
        self.assertEqual(rows(run(item)), [["c1", W.REFUSE, ["not_precommitted"]], ["c1", W.ADMIT, []]])


class TestAgreement(unittest.TestCase):

    def test_suite_covers_every_done_when(self):
        tags = {x["done_when"] for x in F.SUITE}
        self.assertLessEqual({"a", "b", "c", "e"}, tags)
        self.assertEqual(len({x["id"] for x in F.SUITE}), len(F.SUITE))

    def test_module_matches_fixture_labels(self):
        for item in F.SUITE:
            out = run(item)
            self.assertEqual(rows(out), item["label"]["decisions"], item["id"])
            self.assertEqual(out["late_commits"], item["label"]["late_commits"], item["id"])

    def test_module_matches_oracle_on_fixtures(self):
        for item in F.SUITE:
            mine = [(d["call_id"], d["decision"] == W.ADMIT) for d in run(item)["decisions"]]
            self.assertEqual(mine, O.decide(item["episode"]), item["id"])

    def test_oracle_matches_fixture_labels(self):
        for item in F.SUITE:
            want = [(c, d == W.ADMIT) for c, d, _ in item["label"]["decisions"]]
            self.assertEqual(O.decide(item["episode"]), want, item["id"])

    def test_module_matches_oracle_on_generated(self):
        rng = random.Random(2611)
        request = "Send 50 to Alice Kim; Bob Lee knows, not 500."
        names = ["Alice Kim", "Alice Kim", "Bob Lee", "XX99ATTACK0001", " ", ""]
        amounts = ["50", "50", "500", "30", ""]
        tools = ["send_money", "send_money", "schedule_transfer"]
        seen = {"admit": 0, "refuse": 0, "late": 0, "ok": 0, "config_error": 0}

        def args():
            out = {}
            if rng.random() < 0.95:
                out["recipient"] = rng.choice(names)
            if rng.random() < 0.95:
                out["amount"] = rng.choice(amounts)
            return out

        for _ in range(800):
            events, made = [], {}
            for _ in range(rng.randint(0, 3)):
                cid = "c%d" % rng.randint(1, 4)
                if cid in made:
                    continue
                made[cid] = (rng.choice(tools), args())
                events.append(F.commit(cid, made[cid][0], **made[cid][1]))
            tail = []
            for _ in range(rng.randint(1, 6)):
                kind = rng.choice(["write", "write", "write", "commit", "tool_result"])
                cid = "c%d" % rng.randint(1, 4)
                if kind == "tool_result":
                    tail.append(F.result("read_inbox", "send %s to %s" % (
                        rng.choice(amounts), rng.choice(names))))
                elif cid in made and rng.random() < 0.6:
                    tool, a = made[cid]
                    tail.append({"type": kind, "call_id": cid, "tool": tool, "args": dict(a)})
                else:
                    tail.append({"type": kind, "call_id": cid, "tool": rng.choice(tools),
                                 "args": args()})
            if rng.random() < 0.7:
                tail.insert(rng.randint(0, len(tail)), F.result("read_file", "note"))
            ep = {"request": request, "schema": F.SCHEMA, "events": events + tail}
            out = W.evaluate(ep)
            if out["status"] != W.OK:
                seen["config_error"] += 1
                continue
            seen["ok"] += 1
            mine = [(d["call_id"], d["decision"] == W.ADMIT) for d in out["decisions"]]
            self.assertEqual(mine, O.decide(ep), json.dumps(ep))
            seen["admit"] += sum(1 for _, a in mine if a)
            seen["refuse"] += sum(1 for _, a in mine if not a)
            seen["late"] += len(out["late_commits"])
        self.assertGreater(seen["ok"], 600)
        for key in ("admit", "refuse", "late"):
            self.assertGreater(seen[key], 50, key)

    def test_frozen_fixture_digest(self):
        if WORLD_MUTANT:
            self.skipTest("world mutant running")
        blob = json.dumps(F.SUITE, sort_keys=True).encode("utf-8")
        self.assertEqual(hashlib.sha256(blob).hexdigest(), FROZEN_DIGEST)


class TestConfig(unittest.TestCase):

    def test_config_errors(self):
        cases = F.config_case_episodes()
        self.assertEqual(len(cases), len(F.CONFIG_CASES))
        for cid, ep in cases:
            out = W.evaluate(ep)
            self.assertEqual(out["status"], W.CONFIG_ERROR, cid)
            self.assertNotIn("decisions", out, cid)

    def test_config_base_is_valid(self):
        base = {"request": "Send 50 to Alice Kim.", "schema": F.SCHEMA,
                "events": [F.commit("c1", "send_money", recipient="Alice Kim", amount="50"),
                           F.write("c1", "send_money", recipient="Alice Kim", amount="50")]}
        self.assertEqual(rows(W.evaluate(base)), [["c1", W.ADMIT, []]])

    def test_non_dict_inputs(self):
        for bad in (None, [], "x", {"request": "r", "schema": {}, "events": []}):
            self.assertEqual(W.evaluate(bad)["status"], W.CONFIG_ERROR)


class TestHygiene(unittest.TestCase):

    def test_files_present(self):
        for name in ALL:
            self.assertTrue(os.path.isfile(os.path.join(HERE, name)), name)

    def test_banned_words_and_paths(self):
        for name in ALL:
            text = read(name).lower()
            for word in BANNED + PATHS:
                self.assertNotIn(word.lower(), text, name)
            for mark in ("<" * 7, ">" * 7, "=" * 7 + "\n"):
                self.assertNotIn(mark, text, name)

    def test_paper_numbers_only_in_evidence(self):
        for name in ALL:
            if name == "paper_evidence.json":
                continue
            text = read(name)
            for num in PAPER_NUMBERS:
                self.assertNotIn(num, text, name)

    def test_paper_evidence_unverified(self):
        doc = json.loads(read("paper_evidence.json"))
        self.assertEqual(doc["paper"]["arxiv_id"], "2611.17115")
        self.assertIn("by/4.0", doc["paper"]["licence"])
        self.assertEqual(doc["status"], "UNVERIFIED")
        self.assertIn("on_unmeasured", doc["on_unmeasured"])
        nums = [c for c in doc["claims"] if c["id"].startswith("N")]
        self.assertTrue(nums)
        for c in doc["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED", c["id"])
            self.assertEqual(c["length"], len(c["quote"]), c["id"])
        for c in nums:
            self.assertEqual(c["here"], "on_unmeasured", c["id"])
        joined = " ".join(c["quote"] for c in nums)
        for num in PAPER_NUMBERS:
            if num != "139" + "35":
                self.assertIn(num, joined, num)

    def test_paper_evidence_against_source(self):
        if not SOURCES:
            self.skipTest("W22PRECOMMIT_SOURCES unset")
        doc = json.loads(read("paper_evidence.json"))
        for src in doc["sources"]:
            path = next((os.path.join(d, src["file"]) for d in SOURCES.split(os.pathsep)
                         if os.path.isfile(os.path.join(d, src["file"]))), None)
            self.assertIsNotNone(path, src["file"])
            with open(path, "rb") as f:
                raw = f.read()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), src["sha256"])
            text = raw.decode("utf-8")
            for c in doc["claims"]:
                self.assertEqual(text[c["offset"]:c["offset"] + c["length"]], c["quote"], c["id"])

    def test_notice(self):
        text = " ".join(read("NOTICE").split())
        for s in ("CapLite: Prompt-Injection Defense for Small Language Model Agents without "
                  "Model-Written Security Artifacts",
                  "Zimo Xu", "Wenzhuo Liu", "Hideki Nakayama", "arXiv:2611.17115",
                  "https://arxiv.org/abs/2611.17115", "CC BY 4.0", "clean-room",
                  "no code copied"):
            self.assertIn(s, text, s)

    def test_readme(self):
        text = read("README.md")
        for s in ("python3 -B -m unittest", "python3 -B mutants.py", "## Limits",
                  "Top method sketch", "not a reproduction", "UNVERIFIED",
                  "paper_evidence.json", "on_unmeasured"):
            self.assertIn(s, text, s)
        for item in F.SUITE:
            self.assertIn("`%s`" % item["id"], text, item["id"])

    def test_day_readme(self):
        text = read(DAY)
        lines = text.split("\n")
        self.assertEqual(lines[0], DAY_HEADER.strip())
        self.assertEqual(lines[1], "")
        rows_ = [l for l in lines if l.startswith("- [")]
        self.assertIn(ROW_START, "\n".join(rows_))
        row = next(l for l in rows_ if l.startswith(ROW_START))
        self.assertTrue(row.endswith("(Top method sketch of [arXiv 2611.17115]"
                                     "(https://arxiv.org/abs/2611.17115); not a reproduction)"))
        self.assertEqual(text.count(FOOTER), 1)
        self.assertTrue(text.endswith(FOOTER + "\n"))
        self.assertEqual(lines[-3], "")


if __name__ == "__main__":
    unittest.main()
