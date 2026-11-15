"""Tests for the w20-acf-adherence method sketch (stdlib unittest).

Run: python3 -m unittest test_acf_adherence.py -v
The source check reads the abs-page copy named in paper_evidence.json from
the directory in $W20ACF_SOURCES. There is no default: when the variable is
unset, or the file is absent there, the check is skipped.
"""

import ast
import hashlib
import html
import inspect
import json
import os
import random
import re
import unittest

import acf_adherence as A
import fixtures as F

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W20ACF_SOURCES")
CODE = ("acf_adherence.py", "fixtures.py")
DOCS = ("README.md", "NOTICE")
ALL = DOCS + CODE + ("test_acf_adherence.py", "paper_evidence.json", "mutants.py")
I, CF, C = A.Instruction, A.ContextFile, A.Commit
PERMIT = "al" + "low"


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def outs(acf, commit):
    return tuple(o for _, o in A.evaluate(acf, commit).outcomes)


def all_cases():
    yield "design", F.DESIGN_ACF, F.DESIGN_COMMITS, F.DESIGN_EXPECT
    for case in F.PROPERTY_CASES:
        yield case


class Fixtures(unittest.TestCase):
    def test_design_and_property_reports(self):
        lines = []
        fd, nd = F.check_design(out=lines.append)
        fh, nh = F.check_property(out=lines.append)
        self.assertEqual((fd, fh), (0, 0), "\n".join(lines))
        self.assertEqual(nh, 12)

    def test_property_cases_are_deterministic_and_non_trivial(self):
        again = tuple(F.make_property_case(s) for s in F.PROPERTY_SEEDS)
        self.assertEqual(again, F.PROPERTY_CASES)
        t = F.property_totals()
        for key in ("followed", "not_followed", "not_operationalized", "probe_accept", "probe_refuse",
                    "probe_hold", "probe_escalate", "probe_safe_fallback", "split_always",
                    "split_never", "split_mixed", "split_unmeasured", "split_not_applicable",
                    "claim_messages", "compound_commands"):
            self.assertGreater(t.get(key, 0), 0, key)

    def test_property_holds_for_other_seeds(self):
        for s in range(1, 41):
            name, acf, commits, expect = F.make_property_case(s)
            self.assertEqual(F.check_case(acf, commits, expect), 0, name)

    def test_names_unique(self):
        names = [c[0] for c in F.PROPERTY_CASES] + [c[0] for c in F.ADVERSARIAL] + [c[0] for c in F.MALFORMED]
        self.assertEqual(len(names), len(set(names)))


class DoneWhenA(unittest.TestCase):
    """(a) exactly one outcome per instruction; counts sum; unmeasured never followed.
    The not_applicable marker (F4) lives only in the batch split; per-commit
    outcomes stay three-way."""

    def test_one_outcome_per_instruction_and_counts_sum(self):
        for name, acf, commits, _ in all_cases():
            ids = tuple(x.instruction_id for x in acf.instructions)
            for cm in commits:
                r = A.evaluate(acf, cm)
                self.assertEqual(r.status, A.OK, name)
                self.assertEqual(tuple(i for i, _ in r.outcomes), ids, name)
                for _, o in r.outcomes:
                    self.assertIn(o, A.OUTCOMES)
                counts = dict(r.counts)
                self.assertEqual(set(counts), set(A.OUTCOMES))
                self.assertEqual(sum(counts.values()), len(acf.instructions), name)
                for o in A.OUTCOMES:
                    self.assertEqual(counts[o], sum(1 for _, x in r.outcomes if x == o))

    def test_design_outcomes(self):
        for cm in F.DESIGN_COMMITS:
            self.assertEqual(outs(F.DESIGN_ACF, cm), F.DESIGN_EXPECT["outcomes"][cm.commit_id])

    def test_not_operationalized_is_never_followed(self):
        for name, acf, commits, _ in all_cases():
            unmeasured = {x.instruction_id for x in acf.instructions if x.predicate is None}
            for cm in commits:
                r = A.evaluate(acf, cm)
                for i, o in r.outcomes:
                    if i in unmeasured:
                        self.assertEqual(o, A.NOT_OPERATIONALIZED, (name, i))
                self.assertEqual(dict(r.counts)[A.FOLLOWED],
                                 sum(1 for i, o in r.outcomes if o == A.FOLLOWED and i not in unmeasured))

    def test_all_unmeasured_file_counts_zero_followed(self):
        acf = CF((I("U1", "style", "Write clearly.", None), I("U2", "style", "Be kind.", None)), A.HOLD)
        r = A.evaluate(acf, F.CLEAN)
        self.assertEqual(dict(r.counts), {A.FOLLOWED: 0, A.NOT_FOLLOWED: 0, A.NOT_OPERATIONALIZED: 2})
        self.assertFalse(A.enforce(acf, F.CLEAN).accepted)

    def test_adversarial_facts(self):
        for name, cm, want in F.ADVERSARIAL:
            self.assertEqual(outs(F.MEASURED_ACF, cm), want, name)

    def test_malformed_commit_has_no_outcomes(self):
        for name, cm in F.MALFORMED:
            r = A.evaluate(F.MEASURED_ACF, cm)
            self.assertEqual((r.status, r.outcomes, r.counts), (A.CONFIG_ERROR, (), ()), name)


class DoneWhenB(unittest.TestCase):
    """(b) over >= 3 commits, ids split into always / never / mixed."""

    def test_design_split_has_one_of_each(self):
        b = A.split(F.DESIGN_ACF, F.DESIGN_COMMITS)
        self.assertEqual(b.status, A.OK)
        self.assertEqual((b.always, b.never, b.mixed), (("I1",), ("I3",), ("I2",)))
        self.assertEqual(b.unmeasured, ("I4", "I5"))
        self.assertEqual(b.not_applicable, ())

    def test_property_splits(self):
        for name, acf, commits, expect in F.PROPERTY_CASES:
            b = A.split(acf, commits)
            self.assertEqual(F.split_tuple(b), expect["split"], name)
            self.assertTrue(b.always and b.never and b.mixed, name)

    def test_split_is_a_partition(self):
        for name, acf, commits, _ in all_cases():
            b = A.split(acf, commits)
            got = b.always + b.never + b.mixed + b.unmeasured + b.not_applicable
            self.assertEqual(sorted(got), sorted(x.instruction_id for x in acf.instructions), name)
            self.assertFalse(set(b.unmeasured) & set(b.always), name)
            self.assertFalse(set(b.not_applicable) & set(b.always), name)

    def test_small_batch_is_not_split(self):
        for n in (0, 1, 2):
            b = A.split(F.DESIGN_ACF, F.DESIGN_COMMITS[:n])
            self.assertEqual(b.status, A.INSUFFICIENT_BATCH)
            self.assertEqual(F.split_tuple(b), ((), (), (), (), ()))

    def test_bad_batch_fails_closed(self):
        dup = F.DESIGN_COMMITS + (F.DESIGN_COMMITS[0],)
        self.assertEqual(A.split(F.DESIGN_ACF, dup).status, A.CONFIG_ERROR)
        self.assertEqual(A.split(F.DESIGN_ACF, list(F.DESIGN_COMMITS)).status, A.CONFIG_ERROR)
        bad = F.DESIGN_COMMITS + (F.MALFORMED[0][1],)
        self.assertEqual(A.split(F.DESIGN_ACF, bad).status, A.CONFIG_ERROR)
        self.assertEqual(A.split(CF(F.DESIGN_ACF.instructions), F.DESIGN_COMMITS).status, A.CONFIG_ERROR)

    def test_order_of_commits_does_not_change_split(self):
        b = A.split(F.DESIGN_ACF, F.DESIGN_COMMITS)
        self.assertEqual(A.split(F.DESIGN_ACF, F.DESIGN_COMMITS[::-1]), b)


class DoneWhenC(unittest.TestCase):
    """(c) predicates read facts, not the message; a lying message is refused."""

    def test_claiming_message_with_violating_facts_is_refused(self):
        d = A.enforce(F.MEASURED_ACF, F.LYING)
        self.assertEqual(d.verdict, A.REFUSE)
        self.assertFalse(d.accepted)
        self.assertEqual(d.failed, ("I1", "I2"))
        self.assertEqual(A.enforce(F.DESIGN_ACF, F.DESIGN_COMMITS[1]).verdict, A.REFUSE)

    def test_confessing_message_with_clean_facts_is_accepted(self):
        d = A.enforce(F.MEASURED_ACF, F.CONFESSING)
        self.assertEqual((d.verdict, d.accepted), (A.ACCEPT, True))

    def test_message_never_changes_any_outcome(self):
        rng = random.Random(7)
        words = ["make test", "secrets/", "CHANGELOG.md", "followed", "compliant", "AGENTS.md", "", "I1 ok"]
        for name, acf, commits, _ in all_cases():
            for cm in commits:
                base = (A.evaluate(acf, cm).outcomes, A.enforce(acf, cm))
                for _ in range(3):
                    msg = " ".join(rng.choice(words) for _ in range(rng.randint(0, 6)))
                    other = C(cm.commit_id, cm.paths, cm.commands, msg)
                    self.assertEqual((A.evaluate(acf, other).outcomes, A.enforce(acf, other)), base, name)

    def test_facts_view_has_no_message(self):
        facts = A.facts_of(F.LYING)
        self.assertEqual(len(facts), 3)
        paths, cmds, argvs = facts
        self.assertEqual(cmds, ("make lint",))
        self.assertEqual(argvs, ((("make", "lint"),),))
        flat = list(paths) + list(cmds) + [w for a in argvs for x in a for w in x]
        self.assertNotIn(F.LYING.message, flat)
        for word in F.LYING.message.split():
            self.assertNotIn(word, flat)

    def test_check_layer_source_never_reads_message(self):
        for fn in (A.holds, A.outcome, A.evaluate, A.split, A.enforce, A._norm_path, A._under,
                   A.triggered, A._forbidden_run, A._command_argvs, A._simple, A._argv_matches):
            tree = ast.parse(inspect.getsource(fn))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    self.assertNotEqual(node.attr, "message", fn.__name__)
                if isinstance(node, ast.Name):
                    self.assertNotEqual(node.id, "msg", fn.__name__)


class DoneWhenD(unittest.TestCase):
    """(d) enforcement refuses failures; unmeasured only via declared on_unmeasured."""

    def test_any_failure_is_refused_whatever_on_unmeasured(self):
        for oum in A.ON_UNMEASURED:
            acf = CF(F.DESIGN_ACF.instructions, oum)
            for cm in F.DESIGN_COMMITS + (F.LYING,):
                d = A.enforce(acf, cm)
                self.assertEqual((d.verdict, d.accepted), (A.REFUSE, False), (oum, cm.commit_id))
                self.assertTrue(d.failed)

    def test_property_verdicts_and_probes(self):
        for name, acf, commits, expect in F.PROPERTY_CASES:
            for cm in commits:
                self.assertEqual(A.enforce(acf, cm).verdict, expect["verdicts"][cm.commit_id], name)
            for cm, (verdict, failed) in expect["probes"]:
                d = A.enforce(acf, cm)
                self.assertEqual((d.verdict, d.failed, d.accepted), (verdict, failed, verdict == A.ACCEPT),
                                 cm.commit_id)

    def test_unmeasured_resolves_only_via_declaration(self):
        want = {A.DENY: A.REFUSE, A.SAFE_FALLBACK: A.V_SAFE_FALLBACK,
                A.ESCALATE: A.V_ESCALATE, A.HOLD: A.V_HOLD}
        for oum, verdict in want.items():
            acf = CF(F.DESIGN_ACF.instructions, oum)
            d = A.enforce(acf, F.CLEAN)
            self.assertEqual((d.verdict, d.accepted, d.failed, d.unmeasured),
                             (verdict, False, (), ("I4", "I5")), oum)

    def test_clean_commit_on_measured_file_is_accepted(self):
        d = A.enforce(F.MEASURED_ACF, F.CLEAN)
        self.assertEqual((d.verdict, d.accepted, d.failed, d.unmeasured), (A.ACCEPT, True, (), ()))

    def test_missing_on_unmeasured_is_config_error(self):
        for ins in (F.DESIGN_ACF.instructions, F.MEASURED_ACF.instructions):
            acf = CF(ins)
            self.assertIn("on_unmeasured_missing", A.check_config(acf))
            for cm in (F.CLEAN, F.LYING):
                d = A.enforce(acf, cm)
                self.assertEqual((d.verdict, d.accepted), (A.CONFIG_ERROR, False))
                self.assertEqual(A.evaluate(acf, cm).outcomes, ())

    def test_permit_token_is_config_error(self):
        variants = (PERMIT, PERMIT.upper(), PERMIT.capitalize(), "al" + "LOW", PERMIT + "_all",
                    " " + PERMIT.upper(), "SAFE_" + PERMIT.upper(), "DENY_OR_" + PERMIT.upper())
        for v in variants:
            acf = CF(F.MEASURED_ACF.instructions, v)
            self.assertIn("on_unmeasured_permit_token", A.check_config(acf), v)
            d = A.enforce(acf, F.CLEAN)
            self.assertEqual((d.verdict, d.accepted), (A.CONFIG_ERROR, False), v)

    def test_unknown_or_mistyped_on_unmeasured_is_config_error(self):
        for v in ("deny", "Hold", "ACCEPT", "PROCEED", "", "DENY ", 0, 1, True, (A.DENY,), [A.HOLD]):
            acf = CF(F.MEASURED_ACF.instructions, v)
            self.assertTrue(A.check_config(acf), repr(v))
            self.assertEqual(A.enforce(acf, F.CLEAN).verdict, A.CONFIG_ERROR, repr(v))

    def test_str_subclass_on_unmeasured_is_config_error(self):
        class S(str):
            pass
        acf = CF(F.MEASURED_ACF.instructions, S(A.DENY))
        self.assertEqual(A.check_config(acf), ("on_unmeasured_type",))

    def test_subclass_records_fail_closed(self):
        class SubCommit(C):
            pass

        class SubFile(CF):
            pass

        class SubInstruction(I):
            pass
        cm = SubCommit(F.CLEAN.commit_id, F.CLEAN.paths, F.CLEAN.commands, F.CLEAN.message)
        self.assertEqual(A.enforce(F.MEASURED_ACF, cm).verdict, A.CONFIG_ERROR)
        self.assertEqual(A.enforce(SubFile(F.MEASURED_ACF.instructions, A.DENY), F.CLEAN).verdict,
                         A.CONFIG_ERROR)
        ins = SubInstruction("X", "c", "t", ("require_command", "make test"))
        self.assertEqual(A.enforce(CF((ins,), A.DENY), F.CLEAN).verdict, A.CONFIG_ERROR)

    def test_bad_instruction_files_fail_closed(self):
        good = F.MEASURED_ACF.instructions
        bad_sets = {
            "empty": (),
            "list": list(good),
            "dup": good + (good[0],),
            "kind": (I("X", "c", "t", ("trust_message", "ok")),),
            "arity": (I("X", "c", "t", ("require_command",)),),
            "arg_type": (I("X", "c", "t", ("require_command", 3)),),
            "list_pred": (I("X", "c", "t", ["require_command", "make test"]),),
            "path_arg": (I("X", "c", "t", ("forbid_path_prefix", "secrets/")),),
            "dotdot_arg": (I("X", "c", "t", ("forbid_path_prefix", "../x")),),
            "cmd_arg": (I("X", "c", "t", ("require_command", "make  test")),),
            "prefix_quote": (I("X", "c", "t", ("forbid_command_prefix", "'pip' install")),),
            "prefix_sep": (I("X", "c", "t", ("forbid_command_prefix", "pip;install")),),
            "prefix_path": (I("X", "c", "t", ("forbid_command_prefix", "/usr/bin/pip install")),),
            "prefix_assign": (I("X", "c", "t", ("forbid_command_prefix", "X=1 pip")),),
            "prefix_option": (I("X", "c", "t", ("forbid_command_prefix", "-m pip")),),
            "id": (I("", "c", "t", None),),
            "not_instruction": (("I1", "c", "t", None),),
        }
        for name, insts in bad_sets.items():
            acf = CF(insts, A.DENY)
            self.assertTrue(A.check_config(acf), name)
            self.assertEqual(A.enforce(acf, F.CLEAN).verdict, A.CONFIG_ERROR, name)
        self.assertEqual(A.check_config(("not", "a", "file")), ("context_file_type",))

    def test_tuple_subclass_predicate_is_config_error(self):
        class T(tuple):
            pass
        for pred in (T(("require_command", "make test")), T(("forbid_command_prefix", "pip install"))):
            self.assertTrue(isinstance(pred, tuple) and type(pred) is not tuple)
            acf = CF((I("X", "c", "t", pred),), A.DENY)
            self.assertEqual(A.check_config(acf), ("predicate_shape:X",))
            d = A.enforce(acf, F.CLEAN)
            self.assertEqual((d.verdict, d.accepted), (A.CONFIG_ERROR, False))

    def test_malformed_commits_never_accepted(self):
        for name, cm in F.MALFORMED:
            d = A.enforce(F.MEASURED_ACF, cm)
            self.assertEqual((d.verdict, d.accepted), (A.CONFIG_ERROR, False), name)

    def test_only_accept_sets_accepted(self):
        seen = set()
        for name, acf, commits, expect in all_cases():
            for cm in commits + tuple(p for p, _ in expect.get("probes", ())):
                d = A.enforce(acf, cm)
                seen.add(d.verdict)
                self.assertEqual(d.accepted, d.verdict == A.ACCEPT)
        self.assertNotIn(PERMIT, " ".join(seen).lower())


class ForbidCommandF1(unittest.TestCase):
    """F1: a forbid_command_prefix rule reads every simple command a record runs."""

    def verdict(self, cmd, oum=A.DENY):
        return A.enforce(CF(F.PIP_ACF.instructions, oum), C("c", ("a.txt",), (cmd,))).verdict

    def test_verdict_bypass_list_is_whole(self):
        self.assertEqual(len(F.VERDICT_BYPASSES), 17)
        self.assertEqual(len(set(F.VERDICT_BYPASSES)), 17)
        self.assertEqual(hashlib.sha256("\0".join(F.VERDICT_BYPASSES).encode()).hexdigest(),
                         "ab5d4ba8293fddc7ec027a522d628e52e7a22074d17b981fa55263b96186f9ab")

    def test_each_verdict_bypass_is_refused(self):
        for cmd in F.VERDICT_BYPASSES:
            for oum in A.ON_UNMEASURED:
                self.assertEqual(self.verdict(cmd, oum), A.REFUSE, (cmd, oum))

    def test_forms_refused_before_are_still_refused(self):
        for cmd in F.PIP_REFUSED_BEFORE:
            self.assertEqual(self.verdict(cmd), A.REFUSE, cmd)

    def test_more_shell_forms_are_refused(self):
        self.assertGreaterEqual(len(F.PIP_MORE_FORMS), 30)
        for cmd in F.PIP_MORE_FORMS:
            self.assertEqual(self.verdict(cmd), A.REFUSE, cmd)

    def test_bypass_inside_a_batch_of_commands_is_refused(self):
        for cmd in F.VERDICT_BYPASSES:
            cm = C("c", ("a.txt",), ("make lint", cmd, "make test"))
            self.assertEqual(A.enforce(F.PIP_ACF, cm).failed, ("P",), cmd)

    def test_world_lists_are_not_thin(self):
        self.assertEqual(len(F.PIP_LEGIT), 17)
        self.assertEqual(len(F.PIP_UNPARSEABLE), 4)
        self.assertEqual(len(F.PIP_MORE_FORMS), 37)
        self.assertEqual(len(F.PIP_PINNED_GAPS), 9)
        self.assertEqual(len(F.PIP_REFUSED_BEFORE), 6)

    def test_generator_forms_exercise_the_normaliser(self):
        def string_rule(prefix, cmd):
            c = " ".join(cmd.split())
            return c == prefix or c.startswith(prefix + " ")
        acf = CF((I("T", "t", "", ("forbid_command_prefix", "tool3 install")),), A.DENY)
        missed = 0
        for form in F.FORBID_BREAK_FORMS:
            cmd = form.format(t="tool3", k=3)
            self.assertEqual(A.enforce(acf, C("c", (), (cmd,))).verdict, A.REFUSE, cmd)
            missed += not string_rule("tool3 install", cmd)
        self.assertGreaterEqual(missed, 8)
        compound = 0
        for form in F.FORBID_FOLLOW_FORMS:
            cmd = form.format(t="tool3", k=3)
            self.assertEqual(A.enforce(acf, C("c", (), (cmd,))).verdict, A.ACCEPT, cmd)
            compound += any(x in cmd for x in ("&&", ";", "|"))
        self.assertGreaterEqual(compound, 3)

    def test_property_cases_hold_normaliser_only_cells(self):
        cells = 0
        for name, acf, commits, expect in F.PROPERTY_CASES:
            for ins in acf.instructions:
                if ins.predicate is None or ins.predicate[0] != "forbid_command_prefix":
                    continue
                p = ins.predicate[1]
                for cm in commits:
                    for c in cm.commands:
                        n = " ".join(c.split())
                        if not (n == p or n.startswith(p + " ")) and \
                                not A.holds(ins.predicate, A.facts_of(C("x", (), (c,)))):
                            cells += 1
        self.assertGreaterEqual(cells, 10)

    def test_unparseable_record_fails_closed(self):
        for cmd in F.PIP_UNPARSEABLE:
            cm = C("c", ("a.txt",), (cmd,))
            r = A.evaluate(F.PIP_ACF, cm)
            self.assertEqual((r.status, r.outcomes), (A.OK, (("P", A.NOT_FOLLOWED),)), cmd)
            self.assertEqual(self.verdict(cmd), A.REFUSE, cmd)
            self.assertIsNone(A._command_argvs(cmd), cmd)

    def test_unparseable_record_does_not_touch_other_kinds(self):
        acf = CF((I("T", "t", "", ("require_command", "make test")),), A.DENY)
        cm = C("c", ("a.txt",), ("make test", "echo 'x"))
        self.assertEqual(A.enforce(acf, cm).verdict, A.ACCEPT)

    def test_legit_commands_are_accepted(self):
        for cmd in F.PIP_LEGIT:
            self.assertEqual(self.verdict(cmd), A.ACCEPT, cmd)

    def test_pinned_gaps_are_still_accepted(self):
        # Pinned, not hidden: each is named in the README Limitations.
        readme = read("README.md")
        for name, cmd in F.PIP_PINNED_GAPS:
            self.assertEqual(self.verdict(cmd), A.ACCEPT, (name, cmd))
            self.assertIn("`%s`" % cmd, readme, name)

    # One example per further accepted class named in Limitations.
    FURTHER_PINNED_GAPS = (
        ("pipe_into_shell", "echo pip install x | sh"),
        ("here_string", "sh <<< 'pip install x'"),
        ("find_exec", "find . -name req.txt -exec pip install -r {} ;"),
        ("wrapper_outside_list", "stdbuf -oL pip install x"),
        ("ansi_c_quoting", "$'pip' install x"),
        ("function_keyword", "function f { pip install x; }; f"),
        ("python_m_main", "python3 -m pip.__main__ install x"),
    )

    def test_further_pinned_gaps_are_still_accepted(self):
        readme = read("README.md")
        self.assertEqual(len(self.FURTHER_PINNED_GAPS), 7)
        for name, cmd in self.FURTHER_PINNED_GAPS:
            self.assertEqual(self.verdict(cmd), A.ACCEPT, (name, cmd))
            self.assertIn("`%s`" % cmd, readme, name)

    def test_apostrophe_is_unparseable_under_any_prefix_rule(self):
        # An apostrophe in unquoted text fails closed for every
        # forbid_command_prefix rule, not only pip install.
        cmd = "echo it's done"
        self.assertEqual(self.verdict(cmd), A.REFUSE, cmd)
        acf = CF((I("T", "t", "", ("forbid_command_prefix", "rm -rf")),), A.DENY)
        self.assertEqual(A.enforce(acf, C("c", ("a.txt",), (cmd,))).verdict, A.REFUSE)
        self.assertIsNone(A._command_argvs(cmd))
        self.assertIn("`%s`" % cmd, read("README.md"))

    def test_path_prefix_is_case_sensitive(self):
        # Known limit: Secrets/x is not under secrets.
        acf = CF((I("S", "s", "", ("forbid_path_prefix", "secrets")),), A.DENY)
        self.assertEqual(A.enforce(acf, C("c", ("Secrets/x",), ())).verdict, A.ACCEPT)
        self.assertEqual(A.enforce(acf, C("c", ("secrets/x",), ())).verdict, A.REFUSE)
        self.assertIn("`Secrets/x`", read("README.md"))

    def test_generic_prefix_reads_the_same_forms(self):
        acf = CF((I("T", "t", "", ("forbid_command_prefix", "tool3 install")),), A.DENY)
        for cmd in ("cd a && tool3 install", "sudo /opt/tool3 install x", "python3 -m tool3 install",
                    "'tool3' install", "X=1 tool3 -v install"):
            self.assertEqual(A.enforce(acf, C("c", (), (cmd,))).verdict, A.REFUSE, cmd)
        for cmd in ("tool31 install", "tool3 installed", "echo tool3 install", "tool3 list"):
            self.assertEqual(A.enforce(acf, C("c", (), (cmd,))).verdict, A.ACCEPT, cmd)

    def test_version_suffix_only_for_names_ending_in_a_letter(self):
        acf = CF((I("T", "t", "", ("forbid_command_prefix", "pip")),), A.DENY)
        for cmd in ("pip3", "pip3.12 list", "pip"):
            self.assertEqual(A.enforce(acf, C("c", (), (cmd,))).verdict, A.REFUSE, cmd)
        for cmd in ("pipx", "pip3x", "pip.3"):
            self.assertEqual(A.enforce(acf, C("c", (), (cmd,))).verdict, A.ACCEPT, cmd)

    def test_recursion_is_bounded_and_fails_closed(self):
        deep = "pip install x"
        for _ in range(A.MAX_DEPTH + 2):
            deep = "eval " + deep
        self.assertIsNone(A._command_argvs(deep))
        self.assertEqual(self.verdict(deep), A.REFUSE)
        self.assertEqual(A._command_argvs("eval eval pip install x"), (("pip", "install", "x"),))

    def test_require_command_is_unchanged(self):
        acf = CF((I("T", "t", "", ("require_command", "make test")),), A.DENY)
        for cmd, want in (("make test", A.ACCEPT), ("make\ttest", A.ACCEPT), ("make test && make lint", A.REFUSE),
                          ("make test || true", A.REFUSE), ("cd a && make test", A.REFUSE)):
            self.assertEqual(A.enforce(acf, C("c", (), (cmd,))).verdict, want, cmd)


class NotApplicableF4(unittest.TestCase):
    """F4: a conditional whose trigger is absent from every commit is
    reported not_applicable in the split, not always. Per-commit outcomes
    and counts are unchanged (still three-way, still summing)."""

    ACF = CF((I("C", "docs", "", ("path_requires_path", "src", "CHANGELOG.md")),), A.DENY)

    def test_untriggered_conditional_is_not_always(self):
        cs = tuple(C("v%d" % k, ("docs/x%d" % k,), ()) for k in range(3))
        b = A.split(self.ACF, cs)
        self.assertEqual((b.status, b.always, b.not_applicable), (A.OK, (), ("C",)))
        for cm in cs:
            r = A.evaluate(self.ACF, cm)
            self.assertEqual(r.outcomes, (("C", A.FOLLOWED),))
            self.assertEqual(sum(dict(r.counts).values()), 1)
            self.assertEqual(A.enforce(self.ACF, cm).verdict, A.ACCEPT)

    def test_triggered_once_is_always(self):
        cs = (C("v0", ("src/a.py", "CHANGELOG.md"), ()),) + tuple(C("v%d" % k, ("docs/x",), ()) for k in (1, 2))
        b = A.split(self.ACF, cs)
        self.assertEqual((b.always, b.not_applicable), (("C",), ()))

    def test_other_kinds_are_never_not_applicable(self):
        acf = CF((I("S", "s", "", ("forbid_path_prefix", "secrets")),
                  I("P", "p", "", ("forbid_command_prefix", "pip install"))), A.DENY)
        b = A.split(acf, tuple(C("v%d" % k, ("docs/x",), ()) for k in range(3)))
        self.assertEqual((b.always, b.not_applicable), (("S", "P"), ()))


class DoneWhenE(unittest.TestCase):
    """(e) paper compliance rates UNVERIFIED and only in paper_evidence.json."""

    def setUp(self):
        self.ev = json.loads(read("paper_evidence.json"))

    def test_claims_unverified(self):
        ec = self.ev["empirical_claims"]
        self.assertEqual(ec["status"], "UNVERIFIED")
        self.assertTrue(ec["claims"])
        for c in ec["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED", c["id"])
        self.assertEqual(self.ev["compliance_rates"]["status"], "UNVERIFIED")
        self.assertEqual(self.ev["compliance_rates"]["values"], [])

    def test_no_paper_figures_outside_evidence(self):
        for name in DOCS + CODE:
            text = read(name)
            self.assertIsNone(re.search(r"\d\s*%", text), name)

    def test_offsets_match_source_copy(self):
        src = self.ev["source"]
        if not SOURCES:
            self.skipTest("W20ACF_SOURCES not set")
        path = os.path.join(SOURCES, src["file"])
        if not os.path.exists(path):
            self.skipTest("abs-page copy not present")
        with open(path, encoding="utf-8") as f:
            page = f.read()
        self.assertEqual(hashlib.sha256(page.encode("utf-8")).hexdigest(), src["sha256"])
        m = re.search(r'<meta name="citation_abstract" content="([^"]*)"', page)
        abstract = html.unescape(m.group(1))
        self.assertEqual(len(abstract), src["abstract_chars"])
        self.assertEqual(hashlib.sha256(abstract.encode("utf-8")).hexdigest(), src["abstract_sha256"])
        self.assertEqual(re.findall(r"\d", abstract), [])
        for c in self.ev["empirical_claims"]["claims"]:
            span = abstract[c["offset_in_abstract"]:c["offset_in_abstract"] + c["length"]]
            self.assertEqual(hashlib.sha256(span.encode("utf-8")).hexdigest(), c["span_sha256"], c["id"])


class Hygiene(unittest.TestCase):
    # sha256 of each lowercase banned word; the words themselves are not
    # written anywhere in this folder, whole or in parts.
    BANNED_SHA256 = frozenset((
        "6ca7ea2feefc88ecb5ed6356ed963f47dc9137f82526fdd25d618ea626d0803f",
        "36c1852b63947092f69e46964f3a7400e49d5749741af087f444f458e72b27c9",
        "6627835f988e2c5e50533d491163072d3f4f41f5c8b04630150debb3722ca2dd",
        "d2d2328e3359f3de3515871090d1316cbcdc5383204c204f9390788c3ef8618f",
        "877c3aec832cd41012590679bdb84ebe25e5ebbd71b6b81722b48b129feb76ae",
        "b59e55a5ea2ca7188d212674f35cd482a255ac80326a5a5d09722fcebaf2dea1",
    ))
    BANNED_LENGTHS = (4, 5, 6, 7, 10)

    def test_banned_words_absent(self):
        for name in ALL:
            for word in re.findall(r"[a-z]+", read(name).lower()):
                for n in self.BANNED_LENGTHS:
                    for i in range(len(word) - n + 1):
                        digest = hashlib.sha256(word[i:i + n].encode("ascii")).hexdigest()
                        self.assertNotIn(digest, self.BANNED_SHA256, (name, word))

    def test_banned_digest_scan_works(self):
        # The scan finds a planted digest inside a longer token.
        probe = "zzqprobezz"
        digest = hashlib.sha256(b"qprobe").hexdigest()
        hits = [w for w in re.findall(r"[a-z]+", probe)
                for i in range(len(w) - 5) if hashlib.sha256(w[i:i + 6].encode()).hexdigest() == digest]
        self.assertEqual(hits, [probe])

    def test_no_permit_word_anywhere(self):
        for name in ALL:
            self.assertNotIn(PERMIT, read(name).lower(), name)

    def test_no_conflict_markers(self):
        for name in ALL:
            for line in read(name).splitlines():
                self.assertFalse(line.startswith(("<" * 7, ">" * 7)) or line == "=" * 7, name)

    def test_no_day_index_in_this_folder(self):
        self.assertFalse(os.path.exists(os.path.join(HERE, "day-README.md")))

    def test_stdlib_only_no_network_subprocess_or_model(self):
        permitted = {
            "acf_adherence.py": {"posixpath", "re", "shlex", "dataclasses"},
            "fixtures.py": {"random", "sys", "acf_adherence"},
            "test_acf_adherence.py": {"ast", "hashlib", "html", "inspect", "json", "os", "random", "re",
                                      "unittest", "acf_adherence", "fixtures"},
        }
        for name, ok in permitted.items():
            for node in ast.walk(ast.parse(read(name))):
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [(node.module or "").split(".")[0]]
                else:
                    continue
                for m in mods:
                    self.assertIn(m, ok, (name, m))
        for name in CODE:
            src = read(name)
            for bad in ("socket", "urllib", "http.client", "requests", "subprocess", "openai", "anthropic",
                        "sqlite", "hmac", "__import__", "importlib", "eval(", "exec("):
                self.assertNotIn(bad, src, (name, bad))


if __name__ == "__main__":
    unittest.main()
