"""Tests for the w21-advice-cooldown method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest -v
The quote check reads the abstract copy named in paper_evidence.json from
the directory in $W21AC_SOURCES. There is no default: when the variable is
unset, or the file is absent there, that one check is skipped.

The day index is resolved by day_readme(): ../README.md in the repo layout
(this folder inside experiments/2026-11-12/), else _day/README.md in a flat
draft copy. A missing day index fails the day-index tests.
"""

import ast
import copy
import hashlib
import json
import os
import re
import unittest

import advice_cooldown as A
import fixtures as F

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W21AC_SOURCES")
CODE = ("advice_cooldown.py", "fixtures.py")
DOCS = ("README.md", "NOTICE")
ALL = DOCS + CODE + ("test_advice_cooldown.py", "paper_evidence.json", "mutants.py")
PERMIT = "al" + "low"
SEARCH = F.SEARCH
DAY = "2026-11-12"
DAY_HEADER = "# experiments/" + DAY + "\n"
FOOTER = "Do not merge experiment PRs without Ork review."


def present(names):
    return [n for n in names if os.path.isfile(os.path.join(HERE, n))]


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def day_readme():
    """The day index: ../README.md in the repo layout (parent folder is
    2026-11-12 and the file opens with the day header), else _day/README.md
    in a flat copy, else None."""
    parent = os.path.dirname(HERE)
    up = os.path.join(parent, "README.md")
    if os.path.basename(parent) == DAY and os.path.isfile(up):
        with open(up, encoding="utf-8") as fh:
            if fh.read().startswith(DAY_HEADER):
                return up
    flat_copy = os.path.join(HERE, "_day", "README.md")
    if os.path.isfile(flat_copy):
        return flat_copy
    return None


def scanned():
    """(label, text) for every folder file present, plus the day index."""
    out = [(n, read(n)) for n in present(ALL)]
    day = day_readme()
    if day is not None:
        with open(day, encoding="utf-8") as fh:
            out.append(("day README", fh.read()))
    return out


def run(name, **over):
    s, h, b, now, _ = copy.deepcopy(F.DESIGN[name])
    s = over.get("state", s)
    h = over.get("history", h)
    b = over.get("budget", b)
    now = over.get("now", now)
    return A.select_advice(s, h, b, now)


def key(rec):
    return rec["decision"], rec["reason"], rec["sent"]


class SpoofStr(str):
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = str.__hash__


class RaisingStr(str):
    def __eq__(self, other):
        raise RuntimeError("eq")

    __hash__ = str.__hash__


class RaisingObj(object):
    def __eq__(self, other):
        raise RuntimeError("eq")

    def __hash__(self):
        raise RuntimeError("hash")


class SpoofDict(dict):
    pass


class SpoofList(list):
    pass


class SpoofInt(int):
    pass


class DoneWhen(unittest.TestCase):
    def test_matching_first_suggestion_is_sent(self):
        rec = run("first_send")
        self.assertEqual(key(rec), (A.SEND, A.SENT, "sort_hint"))
        self.assertEqual((rec["tokens"], rec["remaining"]), (40, 60))
        self.assertEqual(rec["candidates"], (("sort_hint", A.SENT),))

    def test_repeat_during_cooldown_is_suppressed(self):
        for now in (0, 1, 2):
            rec = run("repeat_in_cooldown", now=now)
            self.assertEqual(key(rec), (A.NO_SEND, A.IN_COOLDOWN, None), now)
            self.assertEqual(rec["tokens"], 0)

    def test_after_cooldown_it_can_be_sent_again(self):
        for now in (3, 4, 50):
            self.assertEqual(key(run("after_cooldown", now=now)), (A.SEND, A.SENT, "sort_hint"), now)

    def test_cooldown_uses_latest_send(self):
        h = [F.sent("sort_hint", 5, 1), F.sent("sort_hint", 0, 1)]
        self.assertEqual(run("after_cooldown", history=h, now=7)["reason"], A.IN_COOLDOWN)
        self.assertEqual(run("after_cooldown", history=h, now=8)["reason"], A.SENT)

    def test_cooldown_is_per_advice_id(self):
        h = [F.sent("other_hint", 2, 1)]
        self.assertEqual(run("first_send", history=h, now=2)["reason"], A.SENT)

    def test_history_id_equal_to_tool_name_cools_nothing_else(self):
        # a history entry whose advice_id equals the tool name ("search")
        # cools only an advice item with that exact id, never sort_hint
        h = [F.sent("search", 2, 1)]
        self.assertEqual(key(run("first_send", history=h, now=2)), (A.SEND, A.SENT, "sort_hint"))
        named = F.advice("search", "search", "sort", {"sort": "price"}, 40, 3)
        s = F.state("search", SEARCH, [named])
        self.assertEqual(A.select_advice(s, h, F.budget(100), 2)["reason"], A.IN_COOLDOWN)

    def test_cooldown_is_exact_id_not_content(self):
        # Limits: same content under a new id, or an NFC/NFD lookalike id,
        # is a different advice id and is not cooled by the first send.
        twin = F.advice("sort_hint_2", "search", "sort", {"sort": "price"}, 40, 3)
        s = F.state("search", SEARCH, [F.sort_hint(), twin])
        rec = A.select_advice(s, [F.sent("sort_hint", 0, 40)], F.budget(200), 1)
        self.assertEqual(key(rec), (A.SEND, A.SENT, "sort_hint_2"))
        nfc, nfd = "h\u00efnt", "hi\u0308nt"
        self.assertNotEqual(nfc, nfd)
        items = [F.advice(i, "search", "sort", {"sort": "price"}, 40, 3) for i in (nfc, nfd)]
        s = F.state("search", SEARCH, items)
        self.assertIsNone(A.validate(s, [], F.budget(200), 0))
        rec = A.select_advice(s, [F.sent(nfc, 0, 40)], F.budget(200), 1)
        self.assertEqual(key(rec), (A.SEND, A.SENT, nfd))

    def test_required_argument_miss_is_refused(self):
        rec = run("required_arg_missing")
        self.assertEqual(key(rec), (A.NO_SEND, A.REQUIRED_ARG_MISSING, None))
        self.assertEqual(rec["candidates"], (("speed_hint", A.REQUIRED_ARG_MISSING),))
        self.assertEqual(key(run("checkout_ok")), (A.SEND, A.SENT, "speed_hint"))

    def test_advice_can_supply_the_missing_required_arg(self):
        s = F.state("checkout", {"item_id": "i1"},
                    [F.advice("addr_hint", "checkout", "address", {"address": "home"}, 5, 2)])
        self.assertEqual(key(A.select_advice(s, [], F.budget(10), 0)), (A.SEND, A.SENT, "addr_hint"))

    def test_invalid_option_is_refused(self):
        self.assertEqual(key(run("invalid_option")), (A.NO_SEND, A.INVALID_OPTION, None))
        s = F.state("checkout", {"item_id": "i", "address": "a", "speed": "teleport"},
                    [F.advice("gift_hint", "checkout", None, {"gift": "no"}, 5, 2)])
        self.assertEqual(key(A.select_advice(s, [], F.budget(100), 0))[1], A.INVALID_OPTION)

    def test_suggestion_overrides_planned_value(self):
        fix = F.advice("fix_sort", "search", None, {"sort": "price"}, 5, 2)
        s = F.state("search", {"query": "q", "sort": "newest"}, [fix])
        self.assertEqual(key(A.select_advice(s, [], F.budget(10), 0)), (A.SEND, A.SENT, "fix_sort"))
        s = F.state("search", {"query": "q", "sort": "rating"},
                    [F.advice("bad", "search", None, {"sort": "newest"}, 5, 2)])
        self.assertEqual(A.select_advice(s, [], F.budget(10), 0)["reason"], A.INVALID_OPTION)

    def test_refused_candidate_falls_through_to_next(self):
        rec = run("fallback_second")
        self.assertEqual(key(rec), (A.SEND, A.SENT, "sort_hint"))
        self.assertEqual(rec["candidates"], (("bad_sort_hint", A.INVALID_OPTION),
                                             ("sort_hint", A.SENT)))

    def test_budget_exhausted_never_sends(self):
        for name in ("budget_short", "budget_spent", "budget_zero"):
            rec = run(name)
            self.assertEqual(key(rec), (A.NO_SEND, A.BUDGET_EXHAUSTED, None), name)
            self.assertEqual(rec["tokens"], 0)
        self.assertEqual(run("budget_spent")["remaining"], 30)
        self.assertEqual(key(run("first_send", budget=F.budget(40))), (A.SEND, A.SENT, "sort_hint"))
        self.assertEqual(run("first_send", budget=F.budget(39))["reason"], A.BUDGET_EXHAUSTED)

    def test_overspent_budget_never_sends(self):
        rec = run("first_send", history=[F.sent("x", 0, 500)], now=1)
        self.assertEqual((rec["decision"], rec["remaining"]), (A.NO_SEND, -400))

    def test_no_contract_means_not_relevant(self):
        self.assertEqual(key(run("no_contract")), (A.NO_SEND, A.NO_CONTRACT, None))

    def test_rule_shortlist(self):
        self.assertEqual(key(run("no_candidate")), (A.NO_SEND, A.NO_CANDIDATE, None))
        s = F.state("checkout", {"item_id": "i", "address": "a"}, [F.sort_hint()])
        self.assertEqual(A.select_advice(s, [], F.budget(100), 0)["reason"], A.NO_CANDIDATE)

    def test_pending_past_deadline_returns_declared_on_expiry(self):
        for action in A.ON_EXPIRY_VALUES:
            s = F.state("search", SEARCH, [F.sort_hint()],
                        {"id": "p1", "deadline": 5, "on_expiry": "".join(list(action))})
            for now in (5, 6, 7, 100):
                rec = A.select_advice(s, [], F.budget(100), now)
                self.assertEqual(key(rec), (action, A.EXPIRED, None))
                self.assertIs(rec["decision"], action)
                self.assertIs(rec["on_expiry"], action)
                self.assertEqual((rec["tokens"], rec["candidates"], rec["pending_id"]), (0, (), "p1"))
        self.assertEqual(key(run("pending_expired")), (A.HOLD, A.EXPIRED, None))

    def test_pending_not_yet_due_is_recorded(self):
        rec = run("pending_open")
        self.assertEqual(key(rec), (A.SEND, A.SENT, "sort_hint"))
        self.assertEqual((rec["pending_id"], rec["on_expiry"]), ("p1", A.DENY))

    def test_pending_deadline_boundary(self):
        # deadline-1 may send; at the deadline and after it the declared
        # on_expiry is returned and nothing is sent (silence doctrine).
        for deadline in (0, 1, 5, 40):
            for action in A.ON_EXPIRY_VALUES:
                s = F.state("search", SEARCH, [F.sort_hint()],
                            {"id": "p1", "deadline": deadline, "on_expiry": action})
                if deadline > 0:
                    rec = A.select_advice(s, [], F.budget(100), deadline - 1)
                    self.assertEqual(key(rec), (A.SEND, A.SENT, "sort_hint"), (deadline, action))
                for now in (deadline, deadline + 1):
                    rec = A.select_advice(s, [], F.budget(100), now)
                    self.assertEqual(key(rec), (action, A.EXPIRED, None), (deadline, action, now))
                    self.assertEqual((rec["tokens"], rec["candidates"]), (0, ()))
                    self.assertNotEqual(rec["decision"], A.SEND)
        self.assertEqual(key(run("pending_at_deadline")), (A.ESCALATE, A.EXPIRED, None))

    def test_missing_on_expiry_is_config_error(self):
        for pending in ({"id": "p1", "deadline": 5},
                        {"id": "p1", "deadline": 5, "on_expiry": "send"},
                        {"id": "p1", "deadline": 5, "on_expiry": "dispatch"},
                        {"id": "p1", "deadline": 5, "on_expiry": "hold"},
                        {"id": "p1", "deadline": 5, "on_expiry": None},
                        {"id": "p1", "deadline": 5, "on_expiry": SpoofStr("HOLD")}):
            s = F.state("search", SEARCH, [F.sort_hint()], pending)
            for now in (0, 9):
                self.assertEqual(key(A.select_advice(s, [], F.budget(100), now)),
                                 (A.CONFIG_ERROR, A.CONFIG_ERROR, None), (pending, now))
        self.assertIn("on_expiry", A.validate(F.state("search", SEARCH, [], {"id": "p", "deadline": 1}),
                                              [], F.budget(1), 0))

    def test_timeline(self):
        reasons, history = F.run_timeline()
        self.assertEqual(reasons, F.TIMELINE_EXPECT)
        self.assertEqual([e["at"] for e in history], [0, 3, 6])
        self.assertEqual(sum(e["tokens"] for e in history), F.TIMELINE_BUDGET)

    def test_select_is_pure(self):
        s, h, b, now, _ = copy.deepcopy(F.DESIGN["after_cooldown"])
        before = copy.deepcopy((s, h, b, now))
        first = A.select_advice(s, h, b, now)
        self.assertEqual((s, h, b, now), before)
        self.assertEqual(A.select_advice(s, h, b, now), first)


class NotARuntime(unittest.TestCase):
    FORBIDDEN = {"threading", "_thread", "socket", "socketserver", "asyncio", "subprocess", "http",
                 "urllib", "multiprocessing", "concurrent", "select", "selectors", "signal", "sched",
                 "time", "ssl", "random", "sqlite3", "ctypes", "os", "sys", "importlib"}

    def imports(self, name):
        mods = set()
        for node in ast.walk(ast.parse(read(name))):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add((node.module or "").split(".")[0])
        return mods

    def test_module_imports_nothing(self):
        self.assertEqual(self.imports("advice_cooldown.py"), set())

    def test_fixtures_import_no_runtime(self):
        self.assertEqual(self.imports("fixtures.py") - {"advice_cooldown"}, {"json", "sys"})
        self.assertFalse(self.imports("fixtures.py") & (self.FORBIDDEN - {"sys"}))

    def test_no_loop_forever_sleep_or_dynamic_code(self):
        for name in CODE:
            tree = ast.parse(read(name))
            for node in ast.walk(tree):
                self.assertNotIsInstance(node, (ast.While, ast.AsyncFunctionDef, ast.Await,
                                                ast.AsyncFor, ast.AsyncWith, ast.Global), name)
                if isinstance(node, ast.Name):
                    self.assertNotIn(node.id, ("eval", "exec", "compile", "__import__", "open",
                                               "input"), name)
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, ("sleep", "start", "serve_forever", "listen",
                                                 "connect", "run_forever"), name)

    def test_for_loops_only_over_finite_inputs(self):
        tree = ast.parse(read("advice_cooldown.py"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, ("iter", "range"))

    def test_no_classifier_or_scoring(self):
        names = {n.name for n in ast.walk(ast.parse(read("advice_cooldown.py")))
                 if isinstance(n, ast.FunctionDef)}
        self.assertEqual(names, {"_is_str", "_is_int", "_canonical", "_exact_keys", "_str_list",
                                 "_str_map", "_validate_contract", "_validate_advice", "validate",
                                 "check_contract", "_shortlisted", "_record", "_select",
                                 "select_advice"})


class ExactTypes(unittest.TestCase):
    def cfg(self, s, h=(), b=(), now=0):
        h = [] if h == () and type(h) is tuple else h
        b = F.budget(100) if b == () and type(b) is tuple else b
        rec = A.select_advice(s, h, b, now)
        self.assertEqual(key(rec), (A.CONFIG_ERROR, A.CONFIG_ERROR, None), repr((s, h, b, now)))

    def good(self):
        return copy.deepcopy(F.DESIGN["first_send"][0])

    def test_state_shape(self):
        for mutate in (lambda s: s.pop("tool"), lambda s: s.update(extra=1),
                       lambda s: s.update(tool=""), lambda s: s.update(tool=SpoofStr("search")),
                       lambda s: s.update(args={"query": 3}), lambda s: s.update(args=SpoofDict(SEARCH)),
                       lambda s: s.update(args={SpoofStr("query"): "x"}),
                       lambda s: s.update(advice=tuple(s["advice"])),
                       lambda s: s.update(advice=SpoofList(s["advice"])),
                       lambda s: s.update(contracts=SpoofDict(F.CONTRACTS)),
                       lambda s: s.update(contracts={"search": {"required": ["query"]}}),
                       lambda s: s.update(contracts={"search": {"required": "query", "options": {}}}),
                       lambda s: s.update(contracts={"search": {"required": [], "options": {"x": []}}}),
                       lambda s: s.update(contracts={"search": {"required": [SpoofStr("q")],
                                                                "options": {}}}),
                       lambda s: s.update(contracts={"search": {"required": [], "options": {"s": "price"}}}),
                       lambda s: s.update(contracts={SpoofStr("search"): F.CONTRACTS["search"]})):
            s = self.good()
            mutate(s)
            self.cfg(s)
        self.cfg(SpoofDict(self.good()))
        self.cfg(None)

    def test_advice_shape(self):
        for field, bad in (("id", ""), ("id", SpoofStr("sort_hint")), ("tool", SpoofStr("search")),
                           ("when_missing", ""), ("when_missing", 3), ("args", {"sort": 1}),
                           ("tokens", 0), ("tokens", True), ("tokens", SpoofInt(40)), ("tokens", 4.0),
                           ("cooldown", 0), ("cooldown", -1), ("cooldown", True),
                           ("cooldown", SpoofInt(3))):
            s = self.good()
            s["advice"][0][field] = bad
            self.cfg(s)
        s = self.good()
        s["advice"][0]["score"] = 0.9
        self.cfg(s)
        s = self.good()
        del s["advice"][0]["cooldown"]
        self.cfg(s)
        s = self.good()
        s["advice"].append(F.sort_hint())
        self.cfg(s)
        s = self.good()
        s["advice"][0] = SpoofDict(s["advice"][0])
        self.cfg(s)

    def test_history_budget_now(self):
        s = self.good()
        for h in ([F.sent("a", 5, 1)], [F.sent("a", 2, 1)], [F.sent("a", -1, 1)], [F.sent("a", 0, 0)], [F.sent("", 0, 1)],
                  [F.sent("a", True, 1)], [F.sent("a", 0, SpoofInt(1))], [dict(F.sent("a", 0, 1), x=1)],
                  [{"advice_id": "a", "at": 0}], [SpoofDict(F.sent("a", 0, 1))],
                  SpoofList(), "x", None):
            self.cfg(s, h=h, now=1)
        for b in ({"limit": -1}, {"limit": True}, {"limit": SpoofInt(9)}, {"limit": 1.0}, {},
                  {"limit": 1, "extra": 1}, SpoofDict(limit=1), None, []):
            self.cfg(s, b=b)
        for now in (-1, True, 1.0, SpoofInt(1), None, "0"):
            self.cfg(s, now=now)

    def test_pending_shape(self):
        for pending in ({"deadline": 5, "on_expiry": "HOLD"}, {"id": "p", "on_expiry": "HOLD"},
                        {"id": "", "deadline": 5, "on_expiry": "HOLD"},
                        {"id": "p", "deadline": -1, "on_expiry": "HOLD"},
                        {"id": "p", "deadline": True, "on_expiry": "HOLD"},
                        {"id": "p", "deadline": SpoofInt(5), "on_expiry": "HOLD"},
                        {"id": "p", "deadline": 5, "on_expiry": "HOLD", "x": 1},
                        SpoofDict(id="p", deadline=5, on_expiry="HOLD"), None, []):
            s = self.good()
            s["pending"] = pending
            self.cfg(s, now=9)

    def test_raising_inputs_never_raise(self):
        bad_states = [RaisingObj()]
        s = self.good()
        s[RaisingStr("zz")] = "x"
        bad_states.append(s)
        s = self.good()
        s["args"] = {"query": RaisingStr("lamp")}
        bad_states.append(s)
        s = self.good()
        s["pending"] = {"id": "p", "deadline": 1, "on_expiry": RaisingObj()}
        bad_states.append(s)
        s = self.good()
        s["advice"][0]["args"] = {RaisingStr("sort"): "price"}
        bad_states.append(s)
        for st in bad_states:
            for h in ([], RaisingObj(), [RaisingObj()]):
                for b in (F.budget(100), RaisingObj()):
                    for now in (0, RaisingObj()):
                        rec = A.select_advice(st, h, b, now)
                        self.assertEqual(rec["decision"], A.CONFIG_ERROR)
                        self.assertIsInstance(A.validate(st, h, b, now), str)

    def test_internal_error_fails_closed(self):
        saved = A.check_contract

        def boom(contract, args):
            raise RuntimeError("boom")
        A.check_contract = boom
        try:
            rec = run("first_send")
        finally:
            A.check_contract = saved
        self.assertEqual(key(rec), (A.CONFIG_ERROR, A.CONFIG_ERROR, None))

    def test_records_are_clean(self):
        consts = set(A.DECISIONS + A.REASONS)
        for name in sorted(F.DESIGN):
            rec = run(name)
            self.assertEqual(tuple(rec), A.RECORD_FIELDS)
            self.assertIn(rec["decision"], consts)
            self.assertIn(rec["reason"], consts)
            self.assertTrue(rec["sent"] is None or type(rec["sent"]) is str)
            self.assertIs(type(rec["tokens"]), int)
            self.assertTrue(rec["on_expiry"] is None or rec["on_expiry"] in A.ON_EXPIRY_VALUES)
            self.assertIs(type(rec["candidates"]), tuple)
            for cid, outcome in rec["candidates"]:
                self.assertIs(type(cid), str)
                self.assertIn(outcome, A.OUTCOMES)
            if rec["decision"] != A.SEND:
                self.assertEqual((rec["sent"], rec["tokens"]), (None, 0))


class Fixtures(unittest.TestCase):
    def test_all_cases_match_tables(self):
        lines = []
        self.assertEqual(F.check(out=lines.append), 0, "\n".join(lines))

    def test_design_covers_done_when(self):
        reasons = {F.DESIGN[n][4][1] for n in F.DESIGN}
        for r in (A.SENT, A.IN_COOLDOWN, A.REQUIRED_ARG_MISSING, A.INVALID_OPTION,
                  A.BUDGET_EXHAUSTED, A.EXPIRED, A.NO_CONTRACT, A.NO_CANDIDATE):
            self.assertIn(r, reasons)

    def test_fixture_shapes(self):
        s, h, b, now, _ = F.DESIGN["repeat_in_cooldown"]
        self.assertEqual([e["advice_id"] for e in h], ["sort_hint"])
        self.assertLess(now - h[0]["at"], s["advice"][0]["cooldown"])
        s, h, b, now, _ = F.DESIGN["after_cooldown"]
        self.assertEqual(now - h[0]["at"], s["advice"][0]["cooldown"])
        s = F.DESIGN["required_arg_missing"][0]
        merged = dict(s["args"], **s["advice"][0]["args"])
        self.assertTrue(set(F.CONTRACTS["checkout"]["required"]) - set(merged))
        s = F.DESIGN["invalid_option"][0]
        self.assertNotIn(s["advice"][0]["args"]["sort"], F.CONTRACTS["search"]["options"]["sort"])
        s, h, b, now, _ = F.DESIGN["budget_short"]
        self.assertGreater(s["advice"][0]["tokens"], b["limit"])
        self.assertEqual(F.DESIGN["budget_zero"][2]["limit"], 0)
        s, h, b, now, _ = F.DESIGN["pending_expired"]
        self.assertGreater(now, s["pending"]["deadline"])
        s, h, b, now, _ = F.DESIGN["pending_open"]
        self.assertEqual(now, s["pending"]["deadline"] - 1)
        s, h, b, now, _ = F.DESIGN["pending_at_deadline"]
        self.assertEqual(now, s["pending"]["deadline"])
        self.assertNotIn("ship", F.CONTRACTS)
        self.assertEqual(len(F.TIMELINE_EXPECT), 10)


class PaperEvidence(unittest.TestCase):
    # built by concatenation so the figures never appear in this file
    FIGURES = tuple(a + b for a, b in (("1.7", "B"), ("1,", "308"), ("2", "70"), ("29.8", "%"),
                                       ("4,", "987"), ("50.2", "%"), ("51.0", "%")))

    def setUp(self):
        self.ev = json.loads(read("paper_evidence.json"))

    def test_metadata(self):
        p = self.ev["paper"]
        self.assertEqual((p["arxiv_id"], p["version"]), ("2611.13615", "v1"))
        self.assertEqual(p["title"], "Synapse-Control: Making Agent Experience Actionable with "
                                     "Lightweight Runtime Control")
        self.assertEqual(len(p["authors"]), 8)
        self.assertEqual((p["authors"][0], p["authors"][-1]), ("Zhiyuan Huang", "Linpeng Huang"))
        self.assertEqual(p["licence_url"], "http://arxiv.org/licenses/nonexclusive-distrib/1.0/")
        self.assertIn("UNVERIFIED", p["code"])

    def test_figures_unverified_and_only_here(self):
        claims = self.ev["empirical_claims"]
        self.assertEqual(claims["status"], "UNVERIFIED")
        figs = [f for c in claims["claims"] for f in c["figures"]]
        self.assertEqual(sorted(figs), sorted(self.FIGURES))
        for c in claims["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")
            for f in c["figures"]:
                self.assertIn(f, c["quote"])
            self.assertEqual(hashlib.sha256(c["quote"].encode("utf-8")).hexdigest(), c["span_sha256"])
            self.assertEqual(len(c["quote"]), c["length"])
        for name, text in scanned():
            if name == "paper_evidence.json":
                continue
            for f in self.FIGURES:
                pat = r"(?<![\w.,])" + re.escape(f) + r"(?![\w.,])"
                self.assertIsNone(re.search(pat, text), (name, f))

    def test_quotes_are_exact_abstract_substrings(self):
        src = self.ev["source"]
        if not SOURCES:
            self.skipTest("W21AC_SOURCES not set")
        path = os.path.join(SOURCES, src["file"])
        if not os.path.isfile(path):
            self.skipTest("abstract copy not present")
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        self.assertEqual(hashlib.sha256(raw.encode("utf-8")).hexdigest(), src["sha256"])
        abstract = raw[len("Abstract:"):].strip() if raw.startswith("Abstract:") else raw.strip()
        self.assertEqual(hashlib.sha256(abstract.encode("utf-8")).hexdigest(), src["abstract_sha256"])
        for c in self.ev["empirical_claims"]["claims"]:
            off = c["offset_in_abstract"]
            self.assertEqual(abstract[off:off + c["length"]], c["quote"], c["id"])


class Readme(unittest.TestCase):
    def test_readme_scope_and_credit(self):
        text = read("README.md")
        flat = " ".join(text.split())
        self.assertIn("Synapse-Control: Making Agent Experience Actionable with Lightweight Runtime "
                      "Control", flat)
        for s in ("Zhiyuan Huang", "Shengan Zheng", "Chenghu Yang", "Song Zhang", "Lingyun Li",
                  "Chen Yu", "Weiquan Huang", "Linpeng Huang",
                  "http://arxiv.org/licenses/nonexclusive-distrib/1.0/", "method sketch, not law",
                  "synthetic", "Soft", "not a runtime port", "no classifier", "w18-skill-assurance",
                  "w14-phase-deadline", "retry_cooldown", "UNVERIFIED", "same advice id",
                  "53-shut-up-budget-cooldown", "retry_backoff", "MIT port", "not a proof",
                  "NFC/NFD", "pending item at its deadline"):
            self.assertIn(s, flat, s)
        self.assertIn("the same advice id is not still in cooldown", flat)
        self.assertNotIn("the same suggestion is not still in cooldown", flat)
        self.assertNotIn("mapping for retries", flat)


class DayReadme(unittest.TestCase):
    """The day index, read at ../README.md in the repo layout."""

    def text(self):
        path = day_readme()
        self.assertIsNotNone(path, "no day README at ../README.md or _day/README.md")
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_resolves_in_repo_layout(self):
        parent = os.path.dirname(HERE)
        up = os.path.join(parent, "README.md")
        if os.path.basename(parent) == DAY and os.path.isfile(up):
            self.assertEqual(day_readme(), up)
        else:
            self.assertEqual(day_readme(), os.path.join(HERE, "_day", "README.md"))

    def test_shape(self):
        text = self.text()
        self.assertTrue(text.startswith(DAY_HEADER))
        bullets = [ln for ln in text.splitlines() if ln.startswith("- ")]
        prefix = "- [w21-advice-cooldown](w21-advice-cooldown/)"
        ours = [ln for ln in bullets if ln.startswith(prefix)]
        self.assertEqual(len(ours), 1)
        for ln in bullets:
            self.assertTrue(ln[2:].strip(), ln)
        self.assertEqual(text.count(FOOTER), 1)
        self.assertTrue(text.endswith(FOOTER + "\n"))
        flat = " ".join(ours[0].split())
        for s in ("not a runtime port, no classifier", "not a reproduction", "arXiv 2611.13615",
                  "on_expiry", "the same advice id is out of cooldown",
                  "at or past its deadline"):
            self.assertIn(s, flat, s)
        self.assertNotIn("the same suggestion is out of cooldown", ours[0])
        self.assertNotIn("decision past its deadline", ours[0])


class Hygiene(unittest.TestCase):
    # sha256 of each lowercase banned word; the words are not written here.
    BANNED_DIGESTS = (
        "410083735735a10e658a19edd1704e606c9dd112e225825b63fafeded766c8b9",
        "6ca7ea2feefc88ecb5ed6356ed963f47dc9137f82526fdd25d618ea626d0803f",
        "36c1852b63947092f69e46964f3a7400e49d5749741af087f444f458e72b27c9",
        "6627835f988e2c5e50533d491163072d3f4f41f5c8b04630150debb3722ca2dd",
        "d2d2328e3359f3de3515871090d1316cbcdc5383204c204f9390788c3ef8618f",
    )
    BANNED_LENGTHS = (4, 5, 7, 10)

    def banned(self):
        return frozenset(self.BANNED_DIGESTS)

    def test_banned_words_absent(self):
        self.assertIsNotNone(day_readme())
        for name, text in scanned():
            for word in re.findall(r"[a-z]+", text.lower()):
                for n in self.BANNED_LENGTHS:
                    for i in range(len(word) - n + 1):
                        digest = hashlib.sha256(word[i:i + n].encode("ascii")).hexdigest()
                        self.assertNotIn(digest, self.banned(), (name, word))

    def test_banned_digest_scan_works(self):
        probe = "zzqprobezz"
        digest = hashlib.sha256(b"qprobe").hexdigest()
        hits = [w for w in re.findall(r"[a-z]+", probe)
                for i in range(len(w) - 5) if hashlib.sha256(w[i:i + 6].encode()).hexdigest() == digest]
        self.assertEqual(hits, [probe])
        self.assertEqual(len(self.banned()), 5)
        for d in self.BANNED_DIGESTS:
            self.assertRegex(d, r"\A[0-9a-f]{64}\Z")

    def test_no_permit_word_anywhere(self):
        for name, text in scanned():
            self.assertNotIn(PERMIT, text.lower(), name)

    def test_no_conflict_markers_or_box_paths(self):
        markers = ("<" * 7, "=" * 7, ">" * 7)
        paths = ("/" + "workspace", "/" + "tmp/", "/" + "home/")
        self.assertIsNotNone(day_readme())
        for name, text in scanned():
            for line in text.splitlines():
                self.assertFalse(line.startswith(markers), (name, line))
            for p in paths:
                self.assertNotIn(p, text, (name, p))
