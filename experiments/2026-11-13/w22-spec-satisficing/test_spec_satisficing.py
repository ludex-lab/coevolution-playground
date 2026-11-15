"""Tests for the w22-spec-satisficing method sketch (stdlib unittest).

Run from this folder: python3 -B -m unittest
The quote check reads the source copy named in paper_evidence.json from the
directories listed in $W22SATISFICE_SOURCES (os.pathsep separated). There
is no default: when the variable is unset, or the file is absent, that
check is skipped.

Done-when mapping (VERDICT section 6, T2):
  (a) test_a_all_requirements_choice_may_commit
  (b) test_b_dropping_choice_refused_even_if_acceptable
  (c) test_c_unreported_dropping_commit_refused
  (d) test_d_self_correction_retaining_dropping_choice_still_fails
  (e) test_e_paper_numbers_on_unmeasured_no_model  (paper pass@1 figures
      are on_unmeasured and UNVERIFIED; no model in the loop)
"""

import ast
import copy
import hashlib
import itertools
import json
import os
import re
import unittest

import fixtures as F
import oracle as O
import spec_satisficing as S

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W22SATISFICE_SOURCES")
SLUG = "w22-spec-satisficing"
DAY_HEADER = "# experiments/2026-11-13\n"
ROW_START = "- [%s](%s/): " % (SLUG, SLUG)
ROW_PREFIX = "- [%s](" % SLUG
FOOTER = "Do not merge experiment PRs without Ork review."
OWN_RULES = ("The self-correction rule (a self-correction voids every earlier check) and"
             " the re-report rule (re-reporting a choice voids its check) are this"
             " sketch's own rules, not the paper's.")


def day_readme():
    """Return (relative path, layout) of the day-index README.

    Repo layout: ../README.md in the 2026-11-13 folder, used only when it
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
PY = ("spec_satisficing.py", "oracle.py", "fixtures.py",
      "test_spec_satisficing.py", "mutants.py")
ALL = PY + ("README.md", "NOTICE", "paper_evidence.json", DAY)
BANNED = ("al" + "low", "ke" + "ep", "Cloud" + "Agent", "Smi" + "th", "Check" + "er")
STDLIB_PERMITTED = {"ast", "copy", "hashlib", "io", "itertools", "json", "os",
                    "re", "sys", "unittest",
                    "spec_satisficing", "oracle", "fixtures", "test_spec_satisficing"}


ABS_PATHS = ("/" + "workspace", "/" + "tmp", "/" + "home")
MARKERS = ("<" * 7, "=" * 7, ">" * 7)
PAPER_PAT = re.compile(r"\d+\.\d+\s*%|" + "Deep" + "SWE|" + "SWE-" + "bench|" + "five " + "LLMs")


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


def ep(name):
    tid, trace, expected = F.episodes()[name]
    return F.tasks()[tid], trace, expected


def run(name):
    task, trace, _ = ep(name)
    return S.evaluate(task, trace)


def as_tuple(rec):
    return (rec["decision"], rec["reason"], rec["dropped"], rec["acceptable_claimed"])


class TestDoneWhen(unittest.TestCase):

    def test_a_all_requirements_choice_may_commit(self):
        for name in ("a_report_check_commit", "a_switch_back_to_full", "a_retry_full"):
            task, trace, _ = ep(name)
            rec = S.evaluate(task, trace)
            self.assertEqual(rec["decision"], S.COMMIT, name)
            self.assertEqual(rec["reason"], S.ALL_MET, name)
            self.assertEqual(rec["dropped"], (), name)
            c = trace[-1]["choice"]
            self.assertEqual(S.check(task["choices"][c], task["requirements"]), (True, ()))
            kinds = [e["kind"] for e in trace]
            self.assertIn("report", kinds)
            self.assertIn("check", kinds)

    def test_b_dropping_choice_refused_even_if_acceptable(self):
        rec = run("b_acceptable_flag")
        self.assertEqual((rec["decision"], rec["reason"]), (S.REFUSE, S.DROPS))
        self.assertEqual(rec["dropped"], ("streams_rows",))
        self.assertIs(rec["acceptable_claimed"], True)
        task, trace, _ = ep("b_acceptable_flag")
        rep = [e for e in trace if e["kind"] == "report" and e["choice"] == "buffer_dump"][-1]
        self.assertIs(rep["acceptable"], True)
        self.assertIn("acceptable", rep["reason"])
        rec = run("b_acceptable_two_dropped")
        self.assertEqual((rec["decision"], rec["reason"]), (S.REFUSE, S.DROPS))
        # dropped follows requirement order, not alphabetical order.
        self.assertEqual(rec["dropped"], ("idempotent_only", "exponential_backoff"))
        self.assertIs(rec["acceptable_claimed"], True)
        # The bare word "acceptable" as the reason is not honored either.
        rec = run("b_acceptable_in_reason_text")
        self.assertEqual((rec["decision"], rec["reason"]), (S.REFUSE, S.DROPS))

    def test_c_unreported_dropping_commit_refused(self):
        for name in ("c_unreported_after_compliant_report", "c_unreported_checked_dropping"):
            task, trace, _ = ep(name)
            c = trace[-1]["choice"]
            self.assertFalse(S.check(task["choices"][c], task["requirements"])[0], name)
            self.assertFalse(any(e["kind"] in ("report", "self_correct") and e["choice"] == c
                                 for e in trace), name)
            rec = S.evaluate(task, trace)
            self.assertEqual((rec["decision"], rec["reason"]), (S.REFUSE, S.UNREPORTED), name)
        # Even a checked choice that meets every requirement must be reported.
        rec = run("c_unreported_checked_compliant")
        self.assertEqual((rec["decision"], rec["reason"]), (S.REFUSE, S.UNREPORTED))

    def test_d_self_correction_retaining_dropping_choice_still_fails(self):
        for name in ("d_self_correct_retains_no_recheck", "d_self_correct_retains_recheck",
                     "d_self_correct_retains_retry"):
            task, trace, _ = ep(name)
            c = trace[-1]["choice"]
            self.assertFalse(S.check(task["choices"][c], task["requirements"])[0], name)
            sc = [i for i, e in enumerate(trace) if e["kind"] == "self_correct"]
            self.assertTrue(sc, name)
            self.assertEqual(trace[sc[-1]]["choice"], c, name)
            self.assertTrue(any(e["kind"] == "check" and e["choice"] == c
                                for e in trace[:sc[-1]]), name)
            rec = S.evaluate(task, trace)
            self.assertEqual(rec["decision"], S.REFUSE, name)
            self.assertIs(rec["acceptable_claimed"], True, name)
        self.assertEqual(run("d_self_correct_retains_no_recheck")["reason"], S.UNCHECKED)
        self.assertEqual(run("d_self_correct_retains_retry")["reason"], S.UNCHECKED)
        self.assertEqual(run("d_self_correct_retains_recheck")["reason"], S.DROPS)
        # A self-correction that switches to a full choice commits after a re-check.
        self.assertEqual(run("d_self_correct_switch_recheck")["decision"], S.COMMIT)
        self.assertEqual(run("d_self_correct_switch_no_recheck")["reason"], S.UNCHECKED)

    def test_e_paper_numbers_on_unmeasured_no_model(self):
        self.assertEqual(S.paper_results(), S.ON_UNMEASURED)
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["status"], "UNVERIFIED")
        self.assertEqual(ev["measured_here"], "on_unmeasured")
        nums = [c for c in ev["claims"] if "values" in c]
        vals = [v for c in nums for v in c["values"].values()]
        self.assertEqual(len(vals), 3)
        for v in vals:
            self.assertIn(v, " ".join(c["quote"] for c in nums))
        for c in ev["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED")
            self.assertEqual(c["measured_here"], "on_unmeasured")
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
        for name in ("spec_satisficing.py", "oracle.py"):
            tree = ast.parse(read(name))
            self.assertEqual([n for n in ast.walk(tree)
                              if isinstance(n, (ast.Import, ast.ImportFrom, ast.While))], [], name)


class TestRules(unittest.TestCase):

    def test_check_reads_the_fixture_label(self):
        t = F.tasks()["csv-export"]
        reqs = t["requirements"]
        self.assertEqual(S.check(t["choices"]["stream_writer"], reqs), (True, ()))
        self.assertEqual(S.check(t["choices"]["buffer_dump"], reqs), (False, ("streams_rows",)))
        self.assertEqual(S.check(t["choices"]["ascii_writer"], reqs), (False, ("utf8_output",)))
        self.assertEqual(S.check({"meets": []}, reqs), (False, tuple(reqs)))

    def test_reported_but_unchecked_refused(self):
        self.assertEqual(run("unchecked_compliant")["reason"], S.UNCHECKED)

    def test_check_must_follow_report(self):
        self.assertEqual(run("check_before_report")["reason"], S.UNCHECKED)

    def test_new_report_voids_check(self):
        self.assertEqual(run("rereport_voids_check")["reason"], S.UNCHECKED)

    def test_self_correction_voids_every_check(self):
        self.assertEqual(run("self_correct_voids_same_choice_check")["reason"], S.UNCHECKED)
        self.assertEqual(run("self_correct_elsewhere_voids_check")["reason"], S.UNCHECKED)

    def test_dropping_without_claim_refused(self):
        rec = run("drop_without_acceptable_claim")
        self.assertEqual((rec["decision"], rec["reason"], rec["dropped"]),
                         (S.REFUSE, S.DROPS, ("utf8_output",)))

    def test_acceptable_flag_never_changes_decision(self):
        for name, (tid, trace, _) in F.episodes().items():
            task = F.tasks()[tid]
            base = as_tuple(S.evaluate(task, trace))[:3]
            for flag in (True, False):
                t2 = copy.deepcopy(trace)
                for e in t2:
                    if "acceptable" in e:
                        e["acceptable"] = flag
                        e["reason"] = "acceptable" if flag else e["reason"]
                self.assertEqual(as_tuple(S.evaluate(task, t2))[:3], base, (name, flag))

    def test_only_commit_decision_requires_full_label(self):
        for name, (tid, trace, _) in F.episodes().items():
            task = F.tasks()[tid]
            rec = S.evaluate(task, trace)
            if rec["decision"] == S.COMMIT:
                c = trace[-1]["choice"]
                self.assertEqual(set(task["choices"][c]["meets"]), set(task["requirements"]))


class TestOracle(unittest.TestCase):

    def test_module_and_oracle_agree_on_all_fixtures(self):
        rows = F.run_all()
        self.assertEqual(len(rows), len(F.EPISODES))
        for name, (m, o, e) in rows.items():
            self.assertEqual(m, o, name)
        self.assertIn("module vs oracle: %d/%d episodes agree" % (len(rows), len(rows)),
                      F.summary())

    def test_module_and_oracle_agree_exhaustively(self):
        """Every trace of up to 3 events before the commit, on both tasks."""
        n = 0
        for task in F.tasks().values():
            cs = sorted(task["choices"])
            alphabet = []
            for c in cs:
                alphabet += [F.R(c, "r", True), F.R(c, "r", False), F.C(c),
                             F.SC(c, "s", True), F.SC(c, "s", False)]
            for k in range(4):
                for prefix in itertools.product(alphabet, repeat=k):
                    for c in cs:
                        trace = [dict(e) for e in prefix] + [F.K(c)]
                        rec = S.evaluate(task, trace)
                        orc = O.decide(task, trace)
                        self.assertEqual(
                            as_tuple(rec),
                            (orc["decision"], orc["reason"], orc["dropped"],
                             orc["acceptable_claimed"]), trace)
                        n += 1
        self.assertEqual(n, 2 * 3 * (1 + 15 + 15 ** 2 + 15 ** 3))

    def test_oracle_is_a_separate_code_path(self):
        tree = ast.parse(read("oracle.py"))
        self.assertEqual([x for x in ast.walk(tree)
                          if isinstance(x, (ast.Import, ast.ImportFrom))], [])
        self.assertNotIn("spec_satisficing", read("oracle.py").split('"""', 2)[2])
        m_tree = ast.parse(read("spec_satisficing.py"))
        m_names = {x.id for x in ast.walk(m_tree) if isinstance(x, ast.Name)}
        m_names |= {x.attr for x in ast.walk(m_tree) if isinstance(x, ast.Attribute)}
        self.assertFalse({"oracle", "decide", "O"} & m_names)
        o_defs = {x.name for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)}
        m_defs = {x.name for x in ast.walk(m_tree) if isinstance(x, ast.FunctionDef)}
        self.assertEqual(o_defs & m_defs, set())


class TestInputs(unittest.TestCase):

    def cfg(self, task, trace, detail=None):
        rec = S.evaluate(task, trace)
        self.assertEqual((rec["decision"], rec["reason"]), (S.REJECT, S.CONFIG_ERROR))
        self.assertIsNone(rec["task_id"])
        self.assertIsNone(rec["choice"])
        if detail is not None:
            self.assertEqual(rec["detail"], detail)

    def test_task_shape(self):
        task, trace, _ = ep("a_report_check_commit")
        self.cfg(None, trace, "task_not_dict")
        for f in ("task_id", "requirements", "choices"):
            t = copy.deepcopy(task)
            del t[f]
            self.cfg(t, trace, f + "_missing")
        self.cfg(dict(task, extra=1), trace, "task_unknown_field")
        self.cfg(dict(task, task_id=""), trace, "task_id_invalid")
        self.cfg(dict(task, requirements=[]), trace, "requirements_invalid")
        self.cfg(dict(task, requirements=("header_row",)), trace, "requirements_invalid")
        self.cfg(dict(task, requirements=["a", "a"]), trace)
        self.cfg(dict(task, requirements=["a", 1]), trace, "requirement_invalid")
        self.cfg(dict(task, choices={}), trace, "choices_invalid")

    def test_choice_labels(self):
        task, trace, _ = ep("a_report_check_commit")
        t = copy.deepcopy(task)
        t["choices"]["stream_writer"]["meets"].append("not_a_requirement")
        self.cfg(t, trace, "meets_unknown_requirement")
        t = copy.deepcopy(task)
        t["choices"]["stream_writer"]["meets"].append("header_row")
        self.cfg(t, trace, "meets_duplicate")
        t = copy.deepcopy(task)
        t["choices"]["stream_writer"]["claims"] = ["header_row"]
        self.cfg(t, trace, "choice_entry_invalid")
        t = copy.deepcopy(task)
        t["choices"]["stream_writer"]["meets"] = "header_row"
        self.cfg(t, trace, "meets_invalid")

    def test_trace_shape(self):
        task, trace, _ = ep("a_report_check_commit")
        self.cfg(task, [], "trace_invalid")
        self.cfg(task, trace[:-1], "commit_missing")
        self.cfg(task, trace + [F.K("stream_writer")], "commit_not_last")
        self.cfg(task, [F.K("stream_writer"), F.R("stream_writer", "r")] + trace[1:])
        self.cfg(task, [{"kind": "approve", "choice": "stream_writer"}] + trace,
                 "event_kind_invalid")
        self.cfg(task, [F.R("nope", "r")] + trace, "event_choice_unknown")
        self.cfg(task, trace[:-1] + [F.K("nope")], "event_choice_unknown")
        self.cfg(task, [F.R("stream_writer", "")] + trace[1:], "reason_missing")
        self.cfg(task, [F.SC("stream_writer", "")] + trace[1:], "reason_missing")
        bad = F.R("stream_writer", "r")
        bad["acceptable"] = 1
        self.cfg(task, [bad] + trace[1:], "acceptable_invalid")
        bad = F.R("stream_writer", "r")
        del bad["acceptable"]
        self.cfg(task, [bad] + trace[1:], "event_fields_invalid")
        bad = F.C("stream_writer")
        bad["passed"] = True
        self.cfg(task, [trace[0], bad, trace[-1]], "event_fields_invalid")
        self.cfg(task, ["report"] + trace, "event_not_dict")

    def test_exact_types_in_every_value_slot(self):
        """Subclasses of str, list and dict are rejected (F3)."""
        task, trace, _ = ep("a_report_check_commit")
        R, C, K = F.R, F.C, F.K
        for tr, detail in [
            ([R(SubStr("stream_writer"), "r"), C("stream_writer"), K("stream_writer")],
             "event_choice_unknown"),
            ([R("stream_writer", "r"), C("stream_writer"), K(SubStr("stream_writer"))],
             "event_choice_unknown"),
            ([R("stream_writer", SubStr("r")), C("stream_writer"), K("stream_writer")],
             "reason_missing"),
            ([dict(R("stream_writer", "r"), kind=SubStr("report")), C("stream_writer"),
              K("stream_writer")], "event_kind_invalid"),
            ([SubDict(R("stream_writer", "r")), C("stream_writer"), K("stream_writer")],
             "event_not_dict"),
        ]:
            self.cfg(task, tr, detail)
        self.cfg(task, tuple(trace), "trace_invalid")
        self.cfg(task, SubList(trace), "trace_invalid")
        self.cfg(task, (e for e in trace), "trace_invalid")
        self.cfg(SubDict(task), trace, "task_not_dict")
        self.cfg(dict(task, task_id=SubStr("x")), trace, "task_id_invalid")
        self.cfg(dict(task, requirements=SubList(task["requirements"])), trace,
                 "requirements_invalid")
        self.cfg(dict(task, requirements=[SubStr(r) for r in task["requirements"]]), trace,
                 "requirement_invalid")
        self.cfg(dict(task, requirements=["header_row", "utf8_output", "streams_rows",
                                          "header_row"]), trace, "requirements_duplicate")
        self.cfg(dict(task, choices=SubDict(task["choices"])), trace, "choices_invalid")
        for entry, detail in [
            (SubDict({"meets": ["header_row"]}), "choice_entry_invalid"),
            ({"meets": ("header_row", "utf8_output", "streams_rows")}, "meets_invalid"),
            ({"meets": SubList(["header_row", "utf8_output", "streams_rows"])}, "meets_invalid"),
            ({"meets": [SubStr("header_row")]}, "meets_unknown_requirement"),
        ]:
            t = copy.deepcopy(task)
            t["choices"]["stream_writer"] = entry
            self.cfg(t, trace, detail)

    def test_whitespace_only_reason_rejected(self):
        task, trace, _ = ep("a_report_check_commit")
        for reason in (" ", "\t\n", "\u3000"):
            self.cfg(task, [F.R("stream_writer", reason)] + trace[1:], "reason_missing")
            self.cfg(task, [F.R("stream_writer", "r"), F.SC("stream_writer", reason),
                            F.C("stream_writer"), F.K("stream_writer")], "reason_missing")
        rec = S.evaluate(task, [F.R("stream_writer", " r ")] + trace[1:])
        self.assertEqual(rec["decision"], S.COMMIT)

    def test_run_guard_maps_internal_error(self):
        """An exception inside the gate is config_error, never raised."""
        real = S.check

        def boom(choice, requirements):
            raise OverflowError("boom")

        S.check = boom
        try:
            task, trace, _ = ep("a_report_check_commit")
            self.cfg(task, trace, "internal_error")
        finally:
            S.check = real

    def test_never_raises(self):
        for args in [(None, None), (1, []), ({}, {}), ({"task_id": "x"}, [1]),
                     (F.tasks()["csv-export"], [{"kind": []}])]:
            rec = S.evaluate(*args)
            self.assertEqual(rec["reason"], S.CONFIG_ERROR)

    def test_inputs_not_mutated(self):
        for name, (tid, trace, _) in F.episodes().items():
            task = F.tasks()[tid]
            t0, tr0 = copy.deepcopy(task), copy.deepcopy(trace)
            S.evaluate(task, trace)
            O.decide(task, trace)
            self.assertEqual((task, trace), (t0, tr0), name)


class Spoof:
    """A non-str key that hashes and compares equal to the str `name`.

    hook(n) runs on its n-th __eq__ call (the verifier's A1/A2b/A3 lever).
    """

    def __init__(self, name, hook=None):
        self.name = name
        self.hook = hook
        self.n = 0

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        self.n += 1
        if self.hook:
            self.hook(self.n)
        return other == self.name if type(other) is str else other is self

    def __lt__(self, other):
        return self.name < other

    def __gt__(self, other):
        return self.name > other


class Two(str):
    """A str subclass equal to both csv-export full and dropping choices."""

    def __eq__(self, other):
        return other in ("stream_writer", "buffer_dump")

    __hash__ = str.__hash__


class SubStr(str):
    pass


class SubList(list):
    pass


class SubDict(dict):
    pass


def csv():
    return F.tasks()["csv-export"]


def ok_trace():
    return [F.R("stream_writer", "r"), F.C("stream_writer"), F.K("stream_writer")]


def containers(obj, out):
    """Collect the id of every dict, list and tuple reachable from obj."""
    if isinstance(obj, (dict, list, tuple)):
        out.add(id(obj))
        items = list(obj.keys()) + list(obj.values()) if isinstance(obj, dict) else obj
        for x in items:
            containers(x, out)
    return out


class TestKeysAndSnapshot(unittest.TestCase):
    """F1: exact-str keys before any lookup; the gate runs on a snapshot only."""

    def cfg(self, rec, detail=None):
        self.assertEqual((rec["decision"], rec["reason"]), (S.REJECT, S.CONFIG_ERROR))
        self.assertIsNone(rec["choice"])
        if detail is not None:
            self.assertEqual(rec["detail"], detail)

    def test_a1_spoofed_kind_key_is_config_error(self):
        key = Spoof("kind")
        ev = {key: "commit", "choice": "stream_writer"}
        n0 = key.n
        rec = S.evaluate(csv(), [F.R("stream_writer", "r"), F.C("stream_writer"), ev])
        self.cfg(rec, "event_key_invalid")
        self.assertEqual(key.n, n0)  # its __eq__ never ran

    def test_a2b_validated_refuse_stays_refuse(self):
        base = [F.R("buffer_dump", "acceptable", True), F.C("buffer_dump"),
                F.R("stream_writer", "s"), F.C("stream_writer")]
        plain = S.evaluate(csv(), copy.deepcopy(base) + [F.K("buffer_dump")])
        self.assertEqual((plain["decision"], plain["reason"], plain["choice"], plain["dropped"]),
                         (S.REFUSE, S.DROPS, "buffer_dump", ("streams_rows",)))
        for flip in range(1, 15):
            box = {}

            def hook(n, flip=flip):
                if n == flip:
                    box["ev"]["choice"] = "stream_writer"
                if n == flip + 1:
                    box["ev"]["choice"] = "buffer_dump"

            key = Spoof("kind", hook)
            ev = {key: "commit", "choice": "buffer_dump"}
            box["ev"] = ev
            n0 = key.n
            rec = S.evaluate(csv(), copy.deepcopy(base) + [ev])
            self.assertNotEqual(rec["decision"], S.COMMIT, flip)
            self.cfg(rec, "event_key_invalid")
            self.assertEqual(key.n, n0, flip)
            self.assertEqual(ev["choice"], "buffer_dump", flip)

    def test_a3_str_subclass_cannot_leave_in_a_record(self):
        for flip in range(1, 10):
            box = {}

            def hook(n, flip=flip):
                if n == flip:
                    box["ev"]["choice"] = Two("stream_writer")

            ev = {Spoof("kind", hook): "commit", "choice": "buffer_dump"}
            box["ev"] = ev
            rec = S.evaluate(csv(), [F.R("stream_writer", "r"), F.C("stream_writer"), ev])
            self.cfg(rec, "event_key_invalid")
        rec = S.evaluate(csv(), [F.R("stream_writer", "r"), F.C("stream_writer"),
                                 F.K(Two("stream_writer"))])
        self.cfg(rec, "event_choice_unknown")
        for name, (tid, trace, _) in F.episodes().items():
            rec = S.evaluate(F.tasks()[tid], trace)
            self.assertIs(type(rec["choice"]), str, name)
            self.assertIs(type(rec["task_id"]), str, name)

    def test_non_str_keys_rejected_at_every_level(self):
        rep = {"kind": "report", "choice": "stream_writer", "reason": "r",
               Spoof("acceptable"): True}
        self.cfg(S.evaluate(csv(), [rep, F.C("stream_writer"), F.K("stream_writer")]),
                 "event_key_invalid")
        t = csv()
        t["choices"]["stream_writer"] = {Spoof("meets"): ["header_row", "utf8_output",
                                                         "streams_rows"]}
        self.cfg(S.evaluate(t, ok_trace()), "choice_entry_key_invalid")
        t = csv()
        tid = t.pop("task_id")
        t[Spoof("task_id")] = tid
        self.cfg(S.evaluate(t, ok_trace()), "task_key_invalid")
        t = csv()
        t[1] = "x"
        self.cfg(S.evaluate(t, ok_trace()), "task_key_invalid")
        for bad in (1, SubStr("zz"), ""):
            t = csv()
            t["choices"][bad] = {"meets": []}
            self.cfg(S.evaluate(t, ok_trace()), "choice_id_invalid")
        t = csv()
        t["choices"]["stream_writer"][1] = []
        self.cfg(S.evaluate(t, ok_trace()), "choice_entry_key_invalid")
        ev = F.K("stream_writer")
        ev[(1, 2)] = "x"
        self.cfg(S.evaluate(csv(), ok_trace()[:2] + [ev]), "event_key_invalid")
        ev = F.C("stream_writer")
        ev[SubStr("x")] = 1
        self.cfg(S.evaluate(csv(), [ok_trace()[0], ev, ok_trace()[2]]), "event_key_invalid")

    def test_run_sees_only_snapshot(self):
        seen = []
        real = S._run

        def spy(snap):
            seen.append(snap)
            return real(snap)

        S._run = spy
        try:
            for name, (tid, trace, _) in F.episodes().items():
                task = F.tasks()[tid]
                rec = S.evaluate(task, trace)
                self.assertEqual(len(seen), 1, name)
                snap = seen.pop()
                caller = containers(task, containers(trace, set()))
                self.assertEqual(containers(snap, set()) & caller, set(), name)
                self.assertIs(type(snap["events"]), tuple)
                self.assertIs(type(snap["requirements"]), tuple)
                for ev in snap["events"]:
                    self.assertIs(type(ev), dict)
                    self.assertIs(type(ev["kind"]), str)
                    self.assertIs(type(ev["choice"]), str)
                for entry in snap["choices"].values():
                    self.assertIs(type(entry["meets"]), tuple)
                # Changing the caller's objects after evaluate changes nothing seen.
                self.assertEqual(rec, real(snap), name)
        finally:
            S._run = real

    def test_validated_values_are_read_once(self):
        """The snapshot, not the caller's objects, decides: mutating the trace
        list during the run (via the gate's own check()) has no effect."""
        task = csv()
        trace = [F.R("buffer_dump", "acceptable", True), F.C("buffer_dump"), F.K("buffer_dump")]
        real = S.check

        def meddle(choice, requirements):
            trace[-1]["choice"] = "stream_writer"
            trace[0]["choice"] = "stream_writer"
            task["choices"]["buffer_dump"]["meets"].append("streams_rows")
            return real(choice, requirements)

        S.check = meddle
        try:
            rec = S.evaluate(task, trace)
        finally:
            S.check = real
        self.assertEqual((rec["decision"], rec["reason"], rec["choice"], rec["dropped"]),
                         (S.REFUSE, S.DROPS, "buffer_dump", ("streams_rows",)))


class TestFixtures(unittest.TestCase):

    def test_expected_table(self):
        for name, (m, o, e) in F.run_all().items():
            self.assertEqual(m, e, name)

    def test_fixture_invariants(self):
        es = F.episodes()
        for prefix in ("a_", "b_", "c_", "d_"):
            self.assertGreaterEqual(sum(1 for n in es if n.startswith(prefix)), 3, prefix)
        for name, (tid, trace, e) in es.items():
            self.assertIn(tid, F.TASKS)
            self.assertEqual(trace[-1]["kind"], "commit", name)
            if name.startswith("b_"):
                self.assertTrue(any("acceptable" in e2.get("reason", "") for e2 in trace), name)
        self.assertEqual(sorted(e[2][1] for e in es.values() if e[2][0] == "COMMIT"),
                         ["all_requirements_met"] * 4)

    def test_fixture_pins(self):
        t = F.TASKS
        self.assertEqual(t["csv-export"]["requirements"],
                         ["header_row", "utf8_output", "streams_rows"])
        self.assertEqual(t["csv-export"]["choices"]["buffer_dump"]["meets"],
                         ["header_row", "utf8_output"])
        self.assertEqual(t["retry-client"]["choices"]["retry_everything"]["meets"],
                         ["max_attempts_3"])
        self.assertEqual(len(F.EPISODES), 20)

    def test_fixtures_return_copies(self):
        t = F.tasks()
        t["csv-export"]["requirements"].append("x")
        e = F.episodes()
        e["a_report_check_commit"][1].clear()
        self.assertEqual(len(F.tasks()["csv-export"]["requirements"]), 3)
        self.assertEqual(len(F.episodes()["a_report_check_commit"][1]), 3)

    def test_determinism(self):
        self.assertEqual(F.run_all(), F.run_all())


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
        clean = ("clean text (Top method sketch of [arXiv 2611.16289]"
                 "(https://arxiv.org/abs/2611.16289); not a reproduction)")
        every = {"banned_word", "absolute_path", "marker", "paper_number"}
        self.assertEqual(hygiene_hits(dirty), every)
        self.assertEqual(hygiene_hits(clean), set())

        def day(own, sibling):
            return (DAY_HEADER + "\n- [w22-other](w22-other/): " + sibling + "\n"
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
        self.assertTrue(rows[0].endswith(
            "(Top method sketch of [arXiv 2611.16289](https://arxiv.org/abs/2611.16289);"
            " not a reproduction)"))
        if LAYOUT == "flat":
            self.assertEqual(sum(1 for line in lines if line.startswith("- ")), 1)

    def test_no_paper_claims_outside_evidence(self):
        for name in PY + ("README.md", "NOTICE", DAY):
            self.assertIsNone(PAPER_PAT.search(scan_text(name, read(name))), name)

    def test_readme_credits_and_limits(self):
        flat = " ".join(read("README.md").split())
        ev = json.loads(read("paper_evidence.json"))
        self.assertIn(ev["paper"]["title"], flat)
        for author in ev["paper"]["authors"]:
            self.assertIn(author, flat)
        for s in ("http://creativecommons.org/licenses/by/4.0/", "CC BY 4.0",
                  "**Top** method sketch", "not a reproduction", "UNVERIFIED",
                  "on_unmeasured", "paper_evidence.json", "## Limits",
                  "is a fixture label, not a general specification oracle",
                  "python3 -B -m unittest", "python3 -B mutants.py",
                  "w20-acf-adherence", "w20-fidelity-audit", OWN_RULES):
            self.assertIn(s, flat, s)
        notice = " ".join(read("NOTICE").split())
        for s in (ev["paper"]["title"], "Ruixin Wang", "Tianyi Zhang", "arXiv:2611.16289",
                  "https://arxiv.org/abs/2611.16289", "CC BY 4.0", "clean-room"):
            self.assertIn(s, notice, s)

    def test_evidence_shape(self):
        ev = json.loads(read("paper_evidence.json"))
        self.assertEqual(ev["paper"]["arxiv_id"], "2611.16289")
        self.assertIn("4.0", ev["paper"]["licence"])
        self.assertFalse(ev["paper"]["pdf_read"])
        for c in ev["claims"]:
            self.assertEqual(len(c["quote"]), c["length"])

    def test_quotes_exact_in_sources(self):
        if not SOURCES:
            self.skipTest("W22SATISFICE_SOURCES not set")
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
