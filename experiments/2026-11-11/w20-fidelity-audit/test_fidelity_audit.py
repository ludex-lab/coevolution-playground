"""Tests for the w20-fidelity-audit method sketch (stdlib unittest).

Run: python3 -m unittest test_fidelity_audit.py -v
The source check reads the abs-page copy named in paper_evidence.json from
$W20FA_SOURCES (env only, no default path) and is skipped when the
variable is unset or the copy is absent.
"""

import ast
import dataclasses
import enum
import hashlib
import html
import inspect
import json
import os
import re
import unittest

import fidelity_audit as F
import fixtures as X

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.environ.get("W20FA_SOURCES", "")
CODE = ("fidelity_audit.py", "fixtures.py")
DOCS = ("README.md", "NOTICE")
ALL = DOCS + CODE + ("test_fidelity_audit.py", "paper_evidence.json", "mutants.py")
PERMIT = "al" + "low"
INVALID_LABELS = {"split_by_ai", "verdict_by_ai", "token_by_tool", "unattributed_step", "record_without_step",
                  "mixed_actor_verdict"}


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def design(name):
    return next(c for c in X.DESIGN if c[0] == name)


def replace(case, **kw):
    return dataclasses.replace(case, **kw)


def all_cases():
    return X.DESIGN + X.SCENARIOS


def rejudge(case, aid):
    """The human judges the artefact's current content again (new digest)."""
    a = next(x for x in case.artefacts if x.artefact_id == aid)
    d = F.digest(a.content)
    return replace(case,
                   verdicts=tuple(dataclasses.replace(v, content_digest=d) if v.artefact_id == aid else v
                                  for v in case.verdicts),
                   tokens=tuple(dataclasses.replace(t, content_digest=d) if t.artefact_id == aid else t
                                for t in case.tokens))


def _art(case, aid):
    return next((a for a in case.artefacts if a.artefact_id == aid), None)


def _forged(case):
    out = []
    for r in case.results:
        a = _art(case, r.artefact_id)
        if a is not None and r.digest == F.digest(a.content) and F.run_tool(r.tool, a, r.result_id) != r:
            out.append((r, a))
    return out


def _stale(recs, case):
    return [x for x in recs if _art(case, x.artefact_id) is not None
            and x.content_digest != F.digest(_art(case, x.artefact_id).content)]


def _faithful_reproduced(case):
    honest = {r.artefact_id for r in case.results if _art(case, r.artefact_id) is not None
              and F.run_tool(r.tool, _art(case, r.artefact_id), r.result_id) == r}
    return {v.artefact_id for v in case.verdicts if v.verdict == F.FAITHFUL and v.artefact_id in honest
            and v.content_digest == F.digest(_art(case, v.artefact_id).content)}


# Witnesses: the records of each adversarial world must really carry the
# attack, so a fixture edit that quietly disarms the world is caught.
WITNESS = {
    "stale_verdict": lambda c, k: bool(_stale(c.verdicts, c)),
    "stale_token": lambda c, k: bool(_stale(c.tokens, c)) and not _stale(c.verdicts, c),
    "forged_pass": lambda c, k: any(F._content_ok(a.content) and r.outcome == F.PASS for r, a in _forged(c)),
    "forged_junk": lambda c, k: any(not F._content_ok(a.content) and r.outcome == F.PASS for r, a in _forged(c)),
    "verdict_late": lambda c, k: bool(c.verdicts) and all(v.at > k.deadline for v in c.verdicts)
    and any(t.at <= k.deadline for t in c.tokens),
    "token_before_verdict": lambda c, k: bool(c.tokens) and all(
        t.at <= min(v.at for v in c.verdicts) for t in c.tokens) and all(v.at <= k.deadline for v in c.verdicts),
    "several_faithful": lambda c, k: len(_faithful_reproduced(c)) >= 2,
    "mixed_actor_verdict": lambda c, k: any(
        {s.actor for s in c.steps if s.ref == v.verdict_id} > {F.HUMAN} for v in c.verdicts),
    "stale_digest": lambda c, k: any(_art(c, r.artefact_id) is not None
                                     and r.digest != F.digest(_art(c, r.artefact_id).content) for r in c.results),
    "verdict_mismatch": lambda c, k: any(v.artefact_id not in {r.artefact_id for r in c.results}
                                         for v in c.verdicts),
    "token_mismatch": lambda c, k: any(t.artefact_id not in {v.artefact_id for v in c.verdicts} for t in c.tokens),
    "unfaithful_pass": lambda c, k: {v.verdict for v in c.verdicts} == {F.UNFAITHFUL}
    and {r.outcome for r in c.results} == {F.PASS},
}
DESIGN_WITNESS = {
    "stale_verdict_after_content_change": "stale_verdict",
    "stale_token_after_content_change": "stale_token",
    "forged_pass_on_failing_content": "forged_pass",
    "forged_pass_on_uncheckable_content": "forged_junk",
    "verdict_after_deadline_and_token": "verdict_late",
    "order_token_before_verdict": "token_before_verdict",
    "two_artefacts_both_faithful": "several_faithful",
    "pass_on_different_reading": "unfaithful_pass",
    "pass_on_older_content": "stale_digest",
    "verdict_names_other_artefact": "verdict_mismatch",
}


class Fixtures(unittest.TestCase):
    def test_design_and_scenarios(self):
        lines = []
        fd, nd = X.check(X.DESIGN, out=lines.append)
        fh, nh = X.check(X.SCENARIOS, out=lines.append)
        self.assertEqual((fd, fh), (0, 0), "\n".join(lines))
        self.assertEqual(nh, len(X.SCENARIOS))

    def test_adversarial_worlds_present_and_armed(self):
        self.assertEqual(set(X.ADVERSARIAL), set(WITNESS))
        for label in X.ADVERSARIAL:
            self.assertIn(label, X.LABELS)
        seen = {}
        for name, case, conf, want in X.SCENARIOS:
            label = name.split(":")[1]
            if label in WITNESS:
                seen[label] = seen.get(label, 0) + 1
                self.assertTrue(WITNESS[label](case, conf), name)
        self.assertEqual(set(seen), set(WITNESS))
        names = {c[0] for c in X.DESIGN}
        for name, label in DESIGN_WITNESS.items():
            self.assertIn(name, names)
            _, case, conf, _ = design(name)
            self.assertTrue(WITNESS[label](case, conf), name)

    def test_scenarios_deterministic_and_non_trivial(self):
        again = tuple(c for s in X.SCENARIO_SEEDS for c in X.make_scenarios(s))
        self.assertEqual(again, X.SCENARIOS)
        t = X.scenario_totals()
        self.assertEqual(sum(k.startswith("label_") for k in t), len(X.LABELS))
        for st in (F.ACCEPTED, F.REFUTED, F.NOT_ACCEPTED, F.DENIED, F.HELD, F.ESCALATED, F.FALLBACK):
            self.assertGreater(t.get(st, 0), 0, st)

    def test_names_unique(self):
        names = [c[0] for c in all_cases()]
        self.assertEqual(len(names), len(set(names)))


class DoneWhenA(unittest.TestCase):
    """(a) a tool PASS is bound to an artefact id; PASS on a different reading is not accepted."""

    def test_result_names_artefact_and_digest(self):
        _, case, _, _ = design("accepted")
        a = case.artefacts[0]
        for r in case.results:
            self.assertEqual((r.artefact_id, r.digest, r.outcome), (a.artefact_id, F.digest(a.content), F.PASS))
        self.assertEqual(list(inspect.signature(F.run_tool).parameters), ["tool", "artefact", "result_id"])
        self.assertNotIn("claim_id", [f.name for f in dataclasses.fields(F.ToolResult)])

    def test_pass_on_artefact_stating_another_reading_not_accepted(self):
        _, case, conf, want = design("pass_on_different_reading")
        self.assertEqual({r.outcome for r in case.results}, {F.PASS})
        o = F.audit(case, conf, want[0][0])
        self.assertEqual((o.status, o.accepted, o.reason), (F.NOT_ACCEPTED, False, "unfaithful_artefact"))

    def test_pass_on_older_content_not_bound(self):
        _, case, conf, want = design("pass_on_older_content")
        self.assertEqual(case.results[0].outcome, F.PASS)
        o = F.audit(case, conf, want[0][0])
        self.assertEqual((o.status, o.reason), (F.NOT_ACCEPTED, "no_bound_tool_result"))
        self.assertIn((case.results[0].result_id, "result_not_bound_to_artefact"), o.rejected)

    def test_pass_on_another_claims_artefact_does_not_count(self):
        _, good, conf, _ = design("accepted")
        _, other, _, want = design("pass_on_older_content")
        cid = want[0][0]
        merged = F.Case(good.claims + other.claims, good.artefacts + other.artefacts,
                        good.results + other.results[1:], good.verdicts + other.verdicts,
                        good.tokens + other.tokens, (), good.steps + tuple(
                            s for s in other.steps if s.ref != other.results[0].result_id))
        # Point a PASS at the good artefact's id while the target is the other claim.
        self.assertEqual(F.audit(merged, conf, cid).reason, "no_bound_tool_result")
        self.assertTrue(F.audit(merged, conf, good.claims[0].claim_id).accepted)

    def test_every_accepted_target_has_a_bound_pass_on_its_artefact(self):
        n = 0
        for name, case, conf, want in all_cases():
            for cid, rid, _, _ in want:
                o = F.audit(case, conf, cid, rid)
                if o.accepted:
                    n += 1
                    a = next(x for x in case.artefacts if x.artefact_id == o.artefact_id)
                    self.assertEqual((a.claim_id, a.reading_id), (cid, rid))
                    rs = [r for r in case.results if r.artefact_id == a.artefact_id]
                    self.assertTrue(rs and all(r.outcome == F.PASS and r.digest == F.digest(a.content)
                                               and F.run_tool(r.tool, a, r.result_id) == r for r in rs), name)
                    d = F.digest(a.content)
                    self.assertTrue(any(v.artefact_id == a.artefact_id and v.content_digest == d
                                        and v.verdict == F.FAITHFUL for v in case.verdicts), name)
        self.assertGreater(n, 10)

    def test_toy_tools(self):
        a = F.Artefact("x", "c", "", ("forall", 1, 12, "square", "square_wobble"))
        self.assertEqual(F.run_tool(F.ENUMERATE, a, "r").outcome, F.FAIL)
        self.assertEqual(F.run_tool(F.ENDPOINTS, a, "r").outcome, F.PASS)
        for bad in (("forall", 1, F.MAX_N + 1, "tri", "tri"), ("forall", 5, 1, "tri", "tri"),
                    ("forall", 1, 5, "tri", "nope"), ("exists", 1, 5, "tri", "tri"), ["forall", 1, 5, "tri", "tri"],
                    ("forall", True, 5, "tri", "tri")):
            self.assertEqual(F.run_tool(F.ENUMERATE, F.Artefact("x", "c", "", bad), "r").outcome, F.ERROR, bad)
        self.assertEqual(F.run_tool("oracle", a, "r").outcome, F.ERROR)
        self.assertEqual(F.run_tool(F.ENUMERATE, ("x", "c", "", a.content), "r").outcome, F.ERROR)

    def test_forged_pass_on_failing_content_not_accepted(self):
        _, case, conf, want = design("forged_pass_on_failing_content")
        r, a = case.results[0], case.artefacts[0]
        self.assertEqual((r.outcome, r.digest), (F.PASS, F.digest(a.content)))
        self.assertEqual(F.run_tool(r.tool, a, r.result_id).outcome, F.FAIL)
        o = F.audit(case, conf, want[0][0])
        self.assertEqual((o.status, o.reason, o.accepted), (F.NOT_ACCEPTED, "result_not_reproduced", False))
        self.assertIn((r.result_id, "result_not_reproduced"), o.rejected)

    def test_forged_pass_on_uncheckable_content_not_accepted(self):
        _, case, conf, want = design("forged_pass_on_uncheckable_content")
        self.assertEqual(case.artefacts[0].content, ("trust", "me"))
        o = F.audit(case, conf, want[0][0])
        self.assertEqual((o.status, o.reason), (F.NOT_ACCEPTED, "result_not_reproduced"))
        # Every forged outcome on that content differs from a run, except the honest ERROR.
        a = case.artefacts[0]
        for out in (F.PASS, F.FAIL):
            r = F.ToolResult("rx", F.ENUMERATE, a.artefact_id, F.digest(a.content), out)
            c2 = replace(case, results=(r,), steps=tuple(
                dataclasses.replace(s, ref="rx") if s.ref == case.results[0].result_id else s for s in case.steps))
            self.assertEqual(F.audit(c2, conf, want[0][0]).reason, "result_not_reproduced", out)
        honest = F.run_tool(F.ENUMERATE, a, "rx")
        c3 = replace(case, results=(honest,), steps=tuple(
            dataclasses.replace(s, ref="rx") if s.ref == case.results[0].result_id else s for s in case.steps))
        self.assertEqual(F.audit(c3, conf, want[0][0]).reason, "tool_error")

    def test_forged_fail_or_wrong_tool_name_not_reproduced(self):
        _, case, conf, want = design("accepted")
        r = case.results[0]
        for change in ({"outcome": F.FAIL}, {"outcome": F.ERROR}, {"tool": "oracle"}):
            bad = replace(case, results=(dataclasses.replace(r, **change),) + case.results[1:])
            o = F.audit(bad, conf, want[0][0])
            self.assertFalse(o.accepted, change)
            self.assertIn((r.result_id, "result_not_reproduced"), o.rejected, change)


class DoneWhenB(unittest.TestCase):
    """(b) no fidelity oracle; the verdict is a recorded human decision tied to the artefact."""

    def test_module_never_reads_statement_and_reads_content_only_to_digest_or_run_tools(self):
        tree = ast.parse(read("fidelity_audit.py"))
        funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                self.assertNotEqual(node.attr, "statement")
        for name, fn in funcs.items():
            if name in ("run_tool", "claim_summary"):
                continue
            ok = set()
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "digest":
                    ok.update(id(a) for a in node.args)
            for node in ast.walk(fn):
                if isinstance(node, ast.Attribute) and node.attr == "content":
                    self.assertIn(id(node), ok, name)
        self.assertNotIn("oracle", " ".join(funcs))

    def test_verdict_and_token_record_shape(self):
        self.assertEqual([f.name for f in dataclasses.fields(F.FidelityVerdict)],
                         ["verdict_id", "claim_id", "reading_id", "artefact_id", "content_digest", "verdict", "at"])
        self.assertEqual([f.name for f in dataclasses.fields(F.HumanToken)],
                         ["token_id", "claim_id", "reading_id", "artefact_id", "content_digest", "decision", "at"])

    def test_stale_verdict_after_content_change_not_accepted(self):
        _, case, conf, want = design("stale_verdict_after_content_change")
        self.assertEqual({r.outcome for r in case.results}, {F.PASS})
        o = F.audit(case, conf, want[0][0])
        self.assertEqual((o.status, o.reason, o.accepted), (F.NOT_ACCEPTED, "verdict_not_bound_to_content", False))
        self.assertIn((case.verdicts[0].verdict_id, "verdict_not_bound_to_content"), o.rejected)
        # Once the human judges the new content (new digest on both records), it counts.
        self.assertTrue(F.audit(rejudge(case, case.artefacts[0].artefact_id), conf, want[0][0]).accepted)

    def test_content_change_after_acceptance_drops_old_records(self):
        # Review world: an accepted case, then the artefact's content is
        # replaced and the tools are run again on the new content.
        _, case, conf, want = design("accepted")
        a = case.artefacts[0]
        for new_content in (("forall", 1, 40, "twice_n", "n_plus_n"), ("forall", 1, 39, "sum_to_n", "tri")):
            new = dataclasses.replace(a, content=new_content)
            res = tuple(F.run_tool(r.tool, new, r.result_id) for r in case.results)
            moved = replace(case, artefacts=(new,), results=res)
            o = F.audit(moved, conf, want[0][0])
            self.assertEqual((o.reason, o.accepted), ("verdict_not_bound_to_content", False), new_content)
            fresh_verdict = rejudge(moved, a.artefact_id)
            only_v = replace(fresh_verdict, tokens=case.tokens)
            o = F.audit(only_v, conf, want[0][0])
            self.assertEqual((o.reason, o.accepted), ("token_not_bound_to_content", False), new_content)

    def test_stale_token_not_accepted(self):
        _, case, conf, want = design("stale_token_after_content_change")
        o = F.audit(case, conf, want[0][0])
        self.assertEqual((o.status, o.reason), (F.NOT_ACCEPTED, "token_not_bound_to_content"))

    def test_digest_field_fail_closed(self):
        _, case, conf, want = design("accepted")
        v, t = case.verdicts[0], case.tokens[0]
        good = v.content_digest
        for d in ("", good.upper(), good[:-1], good + "0", None, b"x" * 64, "g" * 64):
            self.assertEqual(F.audit(replace(case, verdicts=(dataclasses.replace(v, content_digest=d),)),
                                     conf, want[0][0]).status, F.CONFIG_ERROR, d)
            self.assertEqual(F.audit(replace(case, tokens=(dataclasses.replace(t, content_digest=d),)),
                                     conf, want[0][0]).status, F.CONFIG_ERROR, d)

    def test_two_artefacts_both_faithful_not_accepted(self):
        _, case, conf, want = design("two_artefacts_both_faithful")
        o = F.audit(case, conf, want[0][0])
        self.assertEqual((o.status, o.reason, o.accepted), (F.NOT_ACCEPTED, "several_faithful_artefacts", False))
        # Token on either artefact, or on both: still no pick.
        a1, a2 = (a.artefact_id for a in case.artefacts)
        t = case.tokens[0]
        for toks in ((dataclasses.replace(t, artefact_id=a2, content_digest=F.digest(case.artefacts[1].content)),),
                     ()):
            self.assertEqual(F.audit(replace(case, tokens=toks, steps=tuple(
                s for s in case.steps if toks or s.ref != t.token_id)), conf, want[0][0]).reason,
                "several_faithful_artefacts")

    def test_outcome_follows_the_human_record_only(self):
        _, case, conf, want = design("accepted")
        v = case.verdicts[0]
        flipped = replace(case, verdicts=(dataclasses.replace(v, verdict=F.UNFAITHFUL),))
        self.assertEqual(F.audit(flipped, conf, want[0][0]).reason, "unfaithful_artefact")
        # The module cannot see that this artefact states another reading: if the
        # human records it as faithful, the module does not second-guess it.
        _, case, conf, want = design("pass_on_different_reading")
        v = case.verdicts[0]
        trusted = replace(case, verdicts=(dataclasses.replace(v, verdict=F.FAITHFUL),))
        self.assertTrue(F.audit(trusted, conf, want[0][0]).accepted)

    def test_verdict_naming_other_artefact_rejected(self):
        _, case, conf, want = design("verdict_names_other_artefact")
        o = F.audit(case, conf, want[0][0])
        self.assertEqual((o.status, o.reason, o.accepted), (F.NOT_ACCEPTED, "verdict_artefact_mismatch", False))
        self.assertIn((case.verdicts[0].verdict_id, "verdict_artefact_mismatch"), o.rejected)

    def test_verdict_for_other_target_is_not_used(self):
        _, case, conf, want = design("accepted")
        v = case.verdicts[0]
        for change in ({"reading_id": "x"},):
            moved = replace(case, verdicts=(dataclasses.replace(v, **change),))
            self.assertEqual(F.audit(moved, conf, want[0][0]).reason, "no_fidelity_verdict")

    def test_no_verdict_not_accepted(self):
        _, case, conf, want = design("accepted")
        steps = tuple(s for s in case.steps if s.ref != case.verdicts[0].verdict_id)
        o = F.audit(replace(case, verdicts=(), steps=steps), conf, want[0][0])
        self.assertEqual((o.status, o.reason), (F.NOT_ACCEPTED, "no_fidelity_verdict"))

    def test_verdict_from_ai_or_tool_invalid(self):
        _, case, conf, want = design("verdict_attributed_to_ai")
        self.assertEqual(F.audit(case, conf, want[0][0]).reason, "report_invalid")
        _, case, conf, want = design("accepted")
        vid = case.verdicts[0].verdict_id
        steps = tuple(dataclasses.replace(s, actor=F.TOOL) if s.ref == vid else s for s in case.steps)
        self.assertEqual(F.audit(replace(case, steps=steps), conf, want[0][0]).reason, "report_invalid")

    def test_unknown_verdict_value_config_error(self):
        _, case, conf, want = design("accepted")
        v = case.verdicts[0]
        for val in ("Faithful", "probably", "", "faithful "):
            bad = replace(case, verdicts=(dataclasses.replace(v, verdict=val),))
            self.assertEqual(F.audit(bad, conf, want[0][0]).status, F.CONFIG_ERROR, val)


class DoneWhenC(unittest.TestCase):
    """(c) human token missing or late -> declared on_expiry; never accept."""

    def test_missing_and_late_resolve_to_declared_on_expiry(self):
        seen = set()
        for name, case, conf, want in X.DESIGN:
            if name.startswith("token_"):
                cid, rid, st, reason = want[0]
                o = F.audit(case, conf, cid, rid)
                self.assertEqual((o.status, o.reason, o.accepted), (F.STATUS_ON_EXPIRY[conf.on_expiry], reason, False))
                seen.add((conf.on_expiry, reason))
        self.assertEqual(len(seen), 8)

    def test_verdict_after_deadline_resolves_to_on_expiry(self):
        _, case, conf, want = design("verdict_after_deadline_and_token")
        for oe in F.ON_EXPIRY:
            o = F.audit(case, dataclasses.replace(conf, on_expiry=oe), want[0][0])
            self.assertEqual((o.status, o.reason, o.accepted), (F.STATUS_ON_EXPIRY[oe], "verdict_late", False))
        _, ok, conf, want = design("accepted")
        v = ok.verdicts[0]
        at_dl = replace(ok, verdicts=(dataclasses.replace(v, at=conf.deadline),),
                        tokens=tuple(dataclasses.replace(t, at=conf.deadline) for t in ok.tokens))
        # Verdict at the deadline is on time, but a token at the same tick does not follow it.
        self.assertEqual(F.audit(at_dl, conf, want[0][0]).reason, "token_before_verdict")
        late = replace(ok, verdicts=(dataclasses.replace(v, at=conf.deadline + 1),))
        self.assertEqual(F.audit(late, conf, want[0][0]).reason, "verdict_late")

    def test_token_must_follow_verdict(self):
        _, case, conf, want = design("order_token_before_verdict")
        o = F.audit(case, conf, want[0][0])
        self.assertEqual((o.status, o.reason, o.accepted), (F.NOT_ACCEPTED, "token_before_verdict", False))
        _, ok, conf, want = design("accepted")
        v, t = ok.verdicts[0], ok.tokens[0]
        for t_at, reason in ((v.at - 1, "token_before_verdict"), (v.at, "token_before_verdict"),
                             (v.at + 1, "tool_pass_faithful_human_accept")):
            c2 = replace(ok, tokens=(dataclasses.replace(t, at=t_at),))
            self.assertEqual(F.audit(c2, conf, want[0][0]).reason, reason, t_at)
        # Two faithful verdicts on the same content: the token follows both.
        v2 = dataclasses.replace(v, verdict_id="v-second", at=v.at + 4)
        two = replace(ok, verdicts=(v, v2), steps=ok.steps + (F.Step("s-v2", F.HUMAN, "verdict", "v-second"),))
        for t_at, reason in ((v.at + 2, "token_before_verdict"), (v2.at, "token_before_verdict"),
                             (v2.at + 1, "tool_pass_faithful_human_accept")):
            c2 = replace(two, tokens=(dataclasses.replace(t, at=t_at),))
            self.assertEqual(F.audit(c2, conf, want[0][0]).reason, reason, t_at)

    def test_deadline_boundary(self):
        _, case, conf, want = design("accepted")
        t = case.tokens[0]
        at = replace(case, tokens=(dataclasses.replace(t, at=conf.deadline),))
        self.assertTrue(F.audit(at, conf, want[0][0]).accepted)
        late = replace(case, tokens=(dataclasses.replace(t, at=conf.deadline + 1),))
        o = F.audit(late, conf, want[0][0])
        self.assertEqual((o.status, o.reason), (F.HELD, "token_late"))

    def test_without_tokens_nothing_is_accepted_or_refuted(self):
        for name, case, conf, want in all_cases():
            ids = {t.token_id for t in case.tokens}
            bare = replace(case, tokens=(), steps=tuple(s for s in case.steps if s.ref not in ids))
            for oe in F.ON_EXPIRY:
                c2 = dataclasses.replace(conf, on_expiry=oe)
                for cid, rid, _, _ in want:
                    o = F.audit(bare, c2, cid, rid)
                    self.assertFalse(o.accepted, name)
                    self.assertNotIn(o.status, (F.ACCEPTED, F.REFUTED), name)

    def test_missing_on_expiry_config_error(self):
        _, case, conf, want = design("accepted")
        for c2 in (F.AuditConfig(deadline=10), F.AuditConfig(None, 10)):
            self.assertIn("on_expiry_missing", F.check_config(c2))
            o = F.audit(case, c2, want[0][0])
            self.assertEqual((o.status, o.accepted), (F.CONFIG_ERROR, False))

    def test_permit_token_config_error(self):
        _, case, conf, want = design("accepted")
        for v in (PERMIT, PERMIT.upper(), PERMIT.capitalize(), "al" + "LOW", PERMIT + "_on_expiry",
                  "SAFE_" + PERMIT.upper(), " " + PERMIT):
            c2 = dataclasses.replace(conf, on_expiry=v)
            self.assertIn("on_expiry_permit_token", F.check_config(c2), v)
            self.assertEqual(F.audit(case, c2, want[0][0]).status, F.CONFIG_ERROR, v)

    def test_bad_config_values(self):
        class S(str):
            pass
        _, case, conf, want = design("accepted")
        bad = [dataclasses.replace(conf, on_expiry=v) for v in ("deny", "Hold", "ACCEPT", "", 0, True, S(F.DENY))]
        bad += [dataclasses.replace(conf, deadline=v) for v in (None, -1, 1.5, True, "10")]
        bad += [dataclasses.replace(conf, required_tools=v) for v in ((), [F.ENUMERATE], ("oracle",),
                                                                     (F.ENUMERATE, F.ENUMERATE), None)]
        bad += [("HOLD", 10, (F.ENUMERATE,))]
        for c2 in bad:
            self.assertTrue(F.check_config(c2), repr(c2))
            self.assertEqual(F.audit(case, c2, want[0][0]).status, F.CONFIG_ERROR, repr(c2))

    def test_token_for_other_artefact_not_used(self):
        _, case, conf, want = design("accepted")
        t = case.tokens[0]
        moved = replace(case, tokens=(dataclasses.replace(t, artefact_id=case.claims[0].claim_id),))
        o = F.audit(moved, conf, want[0][0])
        self.assertEqual((o.status, o.reason), (F.NOT_ACCEPTED, "token_artefact_mismatch"))

    def test_human_decision_must_match_tools(self):
        _, case, conf, want = design("accepted")
        t = case.tokens[0]
        rej = replace(case, tokens=(dataclasses.replace(t, decision=F.D_REJECT),))
        self.assertEqual(F.audit(rej, conf, want[0][0]).reason, "rejected_by_human")
        both = replace(case, tokens=(t, dataclasses.replace(t, token_id="t2", decision=F.D_REJECT)),
                       steps=case.steps + (F.Step("s-extra", F.HUMAN, "decides", "t2"),))
        self.assertEqual(F.audit(both, conf, want[0][0]).reason, "conflicting_tokens")


class FailClosed(unittest.TestCase):
    def test_duplicate_ids_config_error(self):
        _, case, conf, want = design("accepted")
        v = case.verdicts[0]
        dup = replace(case, verdicts=(v, dataclasses.replace(v, verdict_id=case.tokens[0].token_id)))
        self.assertEqual(F.audit(dup, conf, want[0][0]).status, F.CONFIG_ERROR)
        self.assertIn("duplicate_id:%s" % case.tokens[0].token_id, F.check_case(dup))

    def test_subclass_records_config_error(self):
        _, case, conf, want = design("accepted")

        class V2(F.FidelityVerdict):
            pass

        class C2(F.Case):
            pass
        v = case.verdicts[0]
        sub = replace(case, verdicts=(V2(*dataclasses.astuple(v)),))
        self.assertEqual(F.audit(sub, conf, want[0][0]).status, F.CONFIG_ERROR)
        self.assertEqual(F.audit(C2(*[getattr(case, f.name) for f in dataclasses.fields(case)]), conf,
                                 want[0][0]).status, F.CONFIG_ERROR)

    def test_unknown_claim_ref_config_error(self):
        _, case, conf, want = design("accepted")
        a = case.artefacts[0]
        stray = replace(case, artefacts=(a, F.Artefact("a-stray", "c-nowhere", "", a.content)),
                        steps=case.steps + (F.Step("s-stray", F.AI, "drafts", "a-stray"),))
        self.assertIn("unknown_claim_ref", F.check_case(stray))
        self.assertEqual(F.audit(stray, conf, want[0][0]).status, F.CONFIG_ERROR)

    def test_bool_fields_reject_ints(self):
        _, case, conf, want = design("accepted")
        for val in (1, 0):
            c2 = replace(case, claims=(dataclasses.replace(case.claims[0], ambiguous=val),))
            self.assertEqual(F.audit(c2, conf, want[0][0]).status, F.CONFIG_ERROR, val)

    def test_negative_times_config_error(self):
        _, case, conf, want = design("accepted")
        v, t = case.verdicts[0], case.tokens[0]
        for c2 in (replace(case, verdicts=(dataclasses.replace(v, at=-1),)),
                   replace(case, tokens=(dataclasses.replace(t, at=-1),)),
                   replace(case, verdicts=(dataclasses.replace(v, at=-2),), tokens=(dataclasses.replace(t, at=-1),))):
            self.assertEqual(F.audit(c2, conf, want[0][0]).status, F.CONFIG_ERROR)

    def test_bad_target_config_error(self):
        _, case, conf, want = design("accepted")
        for cid, rid in (("", ""), (None, ""), ("nope", ""), (want[0][0], None)):
            self.assertEqual(F.audit(case, conf, cid, rid).status, F.CONFIG_ERROR, (cid, rid))


class DoneWhenD(unittest.TestCase):
    """(d) ambiguous claims need an explicit split; each reading has its own audit; no merge."""

    def test_no_split_no_acceptance(self):
        _, case, conf, want = design("ambiguous_without_split")
        for cid, rid, st, reason in want:
            o = F.audit(case, conf, cid, rid)
            self.assertEqual((o.status, o.reason, o.accepted), (st, reason, False))

    def test_split_one_refuted_one_proved(self):
        _, case, conf, want = design("split_one_proved_one_refuted")
        got = {rid: F.audit(case, conf, cid, rid) for cid, rid, _, _ in want}
        self.assertEqual(got[""].reason, "split_no_merge")
        self.assertEqual(got["first_n_odd"].status, F.ACCEPTED)
        self.assertEqual(got["odd_not_above_n"].status, F.REFUTED)
        self.assertNotEqual(got["first_n_odd"].artefact_id, got["odd_not_above_n"].artefact_id)
        for rid in ("first_n_odd", "odd_not_above_n"):
            arts = [a for a in case.artefacts if a.reading_id == rid]
            vs = [v for v in case.verdicts if v.reading_id == rid]
            ts = [t for t in case.tokens if t.reading_id == rid]
            self.assertEqual((len(arts), len(vs), len(ts)), (1, 1, 1), rid)

    def test_no_implicit_merge_even_when_every_reading_is_proved(self):
        _, case, conf, want = design("split_one_proved_one_refuted")
        cid = want[0][0]
        a2 = next(a for a in case.artefacts if a.reading_id == "odd_not_above_n")
        new = dataclasses.replace(a2, content=("forall", 1, 30, "sum_to_n", "tri"))
        res = tuple(F.run_tool(r.tool, new, r.result_id) if r.artefact_id == a2.artefact_id else r
                    for r in case.results)
        toks = tuple(dataclasses.replace(t, decision=F.D_ACCEPT) for t in case.tokens)
        all_proved = rejudge(replace(case, artefacts=tuple(new if a is a2 else a for a in case.artefacts),
                                     results=res, tokens=toks), a2.artefact_id)
        parent, readings = F.claim_summary(all_proved, conf, cid)
        self.assertEqual([o.status for _, o in readings], [F.ACCEPTED, F.ACCEPTED])
        self.assertEqual((parent.status, parent.reason, parent.accepted), (F.NOT_ACCEPTED, "split_no_merge", False))

    def test_reading_cannot_borrow_another_readings_audit(self):
        _, case, conf, want = design("reading_reuses_other_audit")
        for cid, rid, st, reason in want:
            o = F.audit(case, conf, cid, rid)
            self.assertEqual((o.status, o.reason), (st, reason), rid)

    def test_split_records_fail_closed(self):
        _, case, conf, want = design("split_one_proved_one_refuted")
        cid = want[0][0]
        sp = case.splits[0]
        one = replace(case, splits=(dataclasses.replace(sp, readings=("first_n_odd",)),))
        self.assertEqual(F.audit(one, conf, cid, "first_n_odd").status, F.CONFIG_ERROR)
        dup = replace(case, splits=(sp, dataclasses.replace(sp, split_id="p2")),
                      steps=case.steps + (F.Step("s-p2", F.HUMAN, "splits", "p2"),))
        self.assertEqual(F.audit(dup, conf, cid, "first_n_odd").reason, "conflicting_split")
        by_ai = replace(case, steps=tuple(dataclasses.replace(s, actor=F.AI) if s.ref == sp.split_id else s
                                          for s in case.steps))
        self.assertEqual(F.audit(by_ai, conf, cid, "first_n_odd").reason, "report_invalid")

    def test_split_on_unambiguous_claim_not_accepted(self):
        _, case, conf, want = design("accepted")
        cid = want[0][0]
        sp = F.SplitRecord("p9", cid, ("x", "y"), 1)
        c2 = replace(case, splits=(sp,), steps=case.steps + (F.Step("s-p9", F.HUMAN, "splits", "p9"),))
        self.assertEqual(F.audit(c2, conf, cid).reason, "split_on_unambiguous_claim")
        self.assertEqual(F.audit(case, conf, cid, "x").reason, "split_on_unambiguous_claim")


class DoneWhenE(unittest.TestCase):
    """(e) the dialog report attributes every step to human / ai / tool."""

    def test_valid_report_counts(self):
        _, case, _, _ = design("split_one_proved_one_refuted")
        rep = F.dialog_report(case)
        self.assertTrue(rep.valid, rep.errors)
        self.assertEqual(sum(n for _, n in rep.counts), len(case.steps))
        self.assertEqual({a for a, n in rep.counts if n}, {F.HUMAN, F.AI, F.TOOL})

    def test_unattributed_step_invalidates(self):
        _, case, conf, want = design("accepted")
        for actor in (None, "", "model", "Human", 0, ("human",)):
            bad = replace(case, steps=case.steps + (F.Step("s-x", actor, "note"),))
            rep = F.dialog_report(bad)
            self.assertFalse(rep.valid, actor)
            o = F.audit(bad, conf, want[0][0])
            self.assertEqual((o.reason, o.accepted), ("report_invalid", False), actor)

    def test_record_without_step_or_wrong_actor_invalidates(self):
        _, case, conf, want = design("accepted")
        for k in range(len(case.steps)):
            s = case.steps[k]
            if s.ref == case.claims[0].claim_id:
                continue
            dropped = replace(case, steps=case.steps[:k] + case.steps[k + 1:])
            self.assertFalse(F.dialog_report(dropped).valid, s)
        rid = case.results[0].result_id
        ai_tool = replace(case, steps=tuple(dataclasses.replace(s, actor=F.AI) if s.ref == rid else s
                                            for s in case.steps))
        self.assertFalse(F.dialog_report(ai_tool).valid)
        tid = case.tokens[0].token_id
        tool_tok = replace(case, steps=tuple(dataclasses.replace(s, actor=F.TOOL) if s.ref == tid else s
                                             for s in case.steps))
        self.assertFalse(F.dialog_report(tool_tok).valid)
        dangling = replace(case, steps=case.steps + (F.Step("s-d", F.HUMAN, "cites", "nowhere"),))
        self.assertFalse(F.dialog_report(dangling).valid)
        self.assertFalse(F.dialog_report(replace(case, steps=())).valid)

    def test_str_subclass_and_enum_actor_invalid(self):
        class S(str):
            pass

        class A(str, enum.Enum):
            HUMAN = "human"
            AI = "ai"
            TOOL = "tool"
        _, case, conf, want = design("accepted")
        vid = case.verdicts[0].verdict_id
        for actor in (S(F.HUMAN), A.HUMAN):
            self.assertEqual(actor, F.HUMAN)
            c2 = replace(case, steps=tuple(dataclasses.replace(s, actor=actor) if s.ref == vid else s
                                           for s in case.steps))
            rep = F.dialog_report(c2)
            self.assertFalse(rep.valid, actor)
            self.assertIn("unattributed_step:%s" % next(s.step_id for s in case.steps if s.ref == vid), rep.errors)
            o = F.audit(c2, conf, want[0][0])
            self.assertEqual((o.reason, o.accepted), ("report_invalid", False))
        for actor in (S(F.TOOL), A.TOOL):
            rid = case.results[0].result_id
            c2 = replace(case, steps=tuple(dataclasses.replace(s, actor=actor) if s.ref == rid else s
                                           for s in case.steps))
            self.assertFalse(F.dialog_report(c2).valid, actor)

    def test_record_with_human_and_ai_steps_invalid(self):
        _, case, conf, want = design("accepted")
        for rec_id in (case.verdicts[0].verdict_id, case.tokens[0].token_id):
            for other in (F.AI, F.TOOL):
                c2 = replace(case, steps=case.steps + (F.Step("s-mix", other, "also", rec_id),))
                rep = F.dialog_report(c2)
                self.assertIn("wrong_actor:%s" % rec_id, rep.errors)
                o = F.audit(c2, conf, want[0][0])
                self.assertEqual((o.reason, o.accepted), ("report_invalid", False))
        # An artefact may be drafted by ai and edited by a human; a tool step on it is not.
        aid = case.artefacts[0].artefact_id
        both = replace(case, steps=case.steps + (F.Step("s-ed", F.HUMAN, "edits", aid),))
        self.assertTrue(F.dialog_report(both).valid)
        tool_on_art = replace(case, steps=case.steps + (F.Step("s-ta", F.TOOL, "edits", aid),))
        self.assertFalse(F.dialog_report(tool_on_art).valid)

    def test_claims_only_without_steps_invalid(self):
        _, case, _, _ = design("accepted")
        self.assertFalse(F.dialog_report(F.Case(case.claims)).valid)

    def test_scenario_reports(self):
        for name, case, conf, want in X.SCENARIOS:
            label = name.split(":")[1]
            self.assertEqual(F.dialog_report(case).valid, label not in INVALID_LABELS, name)


class DoneWhenF(unittest.TestCase):
    """(f) hygiene; the paper's example and figures UNVERIFIED and not reproduced."""
    # Banned team words, held as sha256 of the lowercase word so the list
    # itself never spells them; every substring of every word is compared.
    BANNED_SHA256 = frozenset((
        "6ca7ea2feefc88ecb5ed6356ed963f47dc9137f82526fdd25d618ea626d0803f",
        "36c1852b63947092f69e46964f3a7400e49d5749741af087f444f458e72b27c9",
        "6627835f988e2c5e50533d491163072d3f4f41f5c8b04630150debb3722ca2dd",
        "d2d2328e3359f3de3515871090d1316cbcdc5383204c204f9390788c3ef8618f",
        "877c3aec832cd41012590679bdb84ebe25e5ebbd71b6b81722b48b129feb76ae",
        "b59e55a5ea2ca7188d212674f35cd482a255ac80326a5a5d09722fcebaf2dea1",
    ))
    BANNED_LENGTHS = (4, 5, 6, 7, 10)

    def setUp(self):
        self.ev = json.loads(read("paper_evidence.json"))

    def test_evidence_unverified(self):
        self.assertEqual(self.ev["paper_example"]["status"], "UNVERIFIED")
        self.assertIs(self.ev["paper_example"]["reproduced"], False)
        ec = self.ev["empirical_claims"]
        self.assertEqual(ec["status"], "UNVERIFIED")
        for c in ec["claims"]:
            self.assertEqual(c["status"], "UNVERIFIED", c["id"])

    def test_figure_labels_match_tokens(self):
        by_id = {c["id"]: c for c in self.ev["empirical_claims"]["claims"]}
        self.assertEqual(by_id["C2-release-year"]["token"], "2026")
        self.assertIn("year", by_id["C2-release-year"]["about"])
        self.assertNotIn("month", by_id["C2-release-year"]["about"])

    def test_paper_figures_only_in_evidence(self):
        tokens = [c["token"] for c in self.ev["empirical_claims"]["claims"] if c["token"] != "2026"]
        self.assertTrue(tokens)
        for name in DOCS + CODE + ("test_fidelity_audit.py",):
            text = read(name)
            for tok in tokens:
                self.assertIsNone(re.search(r"(?<!\d)%s(?!\d)" % re.escape(tok), text), (name, tok))

    def test_offsets_match_source_copy(self):
        src = self.ev["source"]
        if not SOURCES:
            self.skipTest("W20FA_SOURCES not set")
        path = os.path.join(SOURCES, src["file"])
        if not os.path.exists(path):
            self.skipTest("abs-page copy not present")
        with open(path, encoding="utf-8") as f:
            page = f.read()
        self.assertEqual(hashlib.sha256(page.encode("utf-8")).hexdigest(), src["sha256"])
        abstract = html.unescape(re.search(r'<meta name="citation_abstract" content="([^"]*)"', page).group(1))
        self.assertEqual(len(abstract), src["abstract_chars"])
        self.assertEqual(hashlib.sha256(abstract.encode("utf-8")).hexdigest(), src["abstract_sha256"])
        for c in self.ev["empirical_claims"]["claims"]:
            o = c["offset_in_abstract"]
            self.assertEqual(abstract[o:o + len(c["token"])], c["token"], c["id"])
        for s in self.ev["method_spans"] + self.ev["paper_example"]["spans"]:
            span = abstract[s["offset_in_abstract"]:s["offset_in_abstract"] + s["length"]]
            self.assertEqual(hashlib.sha256(span.encode("utf-8")).hexdigest(), s["span_sha256"], s["id"])

    def test_no_abstract_run_copied_outside_evidence(self):
        # No run of five or more abstract words appears in any file but
        # paper_evidence.json (which holds hashes, not text).
        if not SOURCES:
            self.skipTest("W20FA_SOURCES not set")
        path = os.path.join(SOURCES, self.ev["source"]["file"])
        if not os.path.exists(path):
            self.skipTest("abs-page copy not present")
        with open(path, encoding="utf-8") as f:
            page = f.read()
        abstract = html.unescape(re.search(r'<meta name="citation_abstract" content="([^"]*)"', page).group(1))
        words = re.findall(r"[a-z0-9]+", abstract.lower())
        runs = {" ".join(words[i:i + 5]) for i in range(len(words) - 4)}
        # The title is cited by name in NOTICE; runs it shares with the abstract are not counted.
        tw = re.findall(r"[a-z0-9]+", self.ev["paper"]["title"].lower())
        runs -= {" ".join(tw[i:i + 5]) for i in range(len(tw) - 4)}
        for name in DOCS + CODE + ("test_fidelity_audit.py", "mutants.py"):
            mine = re.findall(r"[a-z0-9]+", read(name).lower())
            for i in range(len(mine) - 4):
                self.assertNotIn(" ".join(mine[i:i + 5]), runs, name)

    def test_banned_words_absent(self):
        for name in ALL:
            text = read(name).lower()
            for word in re.findall(r"[a-z]+", text.lower()):
                for n in self.BANNED_LENGTHS:
                    for i in range(len(word) - n + 1):
                        digest = hashlib.sha256(word[i:i + n].encode("ascii")).hexdigest()
                        self.assertNotIn(digest, self.BANNED_SHA256, (name, word))

    def test_no_permit_word_anywhere(self):
        for name in ALL:
            self.assertNotIn(PERMIT, read(name).lower(), name)

    def test_no_conflict_markers(self):
        for name in ALL:
            for line in read(name).splitlines():
                self.assertFalse(line.startswith(("<" * 7, ">" * 7)) or line == "=" * 7, name)

    def test_stdlib_only_no_network_subprocess_or_model(self):
        permitted = {
            "fidelity_audit.py": {"hashlib", "dataclasses"},
            "fixtures.py": {"random", "sys", "fidelity_audit"},
            "test_fidelity_audit.py": {"ast", "dataclasses", "enum", "hashlib", "html", "inspect", "json", "os",
                                       "re", "unittest", "fidelity_audit", "fixtures"},
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
                self.assertNotIn(bad, src.lower(), (name, bad))
            self.assertIsNone(re.search(r"\b(lean|matlab|wolfram)\b", src.lower()), name)


if __name__ == "__main__":
    unittest.main()
