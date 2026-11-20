"""Tests for w27-worker-lead-handoff (stdlib unittest). Run: python3 -B -m unittest -v test_handoff"""

import copy
import glob
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import handoff as h

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(HERE, "fixtures")


def D(i, e, a, v):
    return {"id": i, "entity": e, "attribute": a, "value": v}


def P(rule="id_asc", budget=1, issued=5, exp=20):
    return {"rule": rule, "budget": budget, "issued_at": issued, "expires_at": exp}


DOCS = [D("d_a", "acme", "city", "Oslo"), D("d_b", "acme", "city", "Bergen"),
        D("f_x", "acme", "year", "2001"), D("f_y", "zeta", "city", "Rome")]


def split_case(pa=None, pb=None, cid="s"):
    return {"id": cid, "layout": "delegated_split", "entity": "acme", "attribute": "city",
            "claims": ["d_a", "d_b"], "assign": {"w_a": ["d_a", "f_x"], "w_b": ["d_b", "f_y"]},
            "packets": {"w_a": pa if pa is not None else P(), "w_b": pb if pb is not None else P()}}


def same_case(pa=None, pb=None, cid="m"):
    return {"id": cid, "layout": "delegated_same", "entity": "acme", "attribute": "city",
            "claims": ["d_a", "d_b"], "assign": {"w_a": ["d_a", "d_b", "f_x"], "w_b": ["f_y"]},
            "packets": {"w_a": pa if pa is not None else P("id_asc", 2), "w_b": pb if pb is not None else P()}}


def single_case(cid="o"):
    return {"id": cid, "layout": "single_agent", "entity": "acme", "attribute": "city",
            "claims": ["d_a", "d_b"], "assign": {"w_solo": ["d_a", "d_b", "f_x", "f_y"]}, "packets": {}}


def make(cases, now=10):
    return {"fixture_version": 1, "on_expiry": "DENY", "now": now, "workers": ["w_solo", "w_a", "w_b"],
            "docs": copy.deepcopy(DOCS), "cases": cases}


def row(case, now=10):
    return h.run(make([case], now))["rows"][0]


def main_report():
    return h.run(h.load(os.path.join(FX, "main.json")))


def expired_report():
    return h.run(h.load(os.path.join(FX, "expired.json")))


def denies(test, root, code=None):
    with test.assertRaises(h.Deny) as ctx:
        h.run(root)
    if code is not None:
        test.assertEqual(ctx.exception.code, code)


class PacketRule(unittest.TestCase):
    CTX = [DOCS[0], DOCS[1], DOCS[2]]

    def test_id_asc_budget(self):
        self.assertEqual([i["doc"] for i in h.write_packet(self.CTX, P("id_asc", 2))], ["d_a", "d_b"])

    def test_id_desc_budget_drops_a_claim(self):
        self.assertEqual([i["doc"] for i in h.write_packet(self.CTX, P("id_desc", 2))], ["f_x", "d_b"])

    def test_budget_one(self):
        self.assertEqual([i["doc"] for i in h.write_packet(self.CTX, P("id_asc", 1))], ["d_a"])

    def test_budget_beyond_context(self):
        self.assertEqual(len(h.write_packet(self.CTX, P("id_asc", 9))), 3)

    def test_input_order_irrelevant(self):
        self.assertEqual(h.write_packet(self.CTX, P("id_desc", 2)), h.write_packet(self.CTX[::-1], P("id_desc", 2)))

    def test_item_fields_only(self):
        self.assertEqual(sorted(h.item(DOCS[0])), ["attribute", "doc", "entity", "value"])

    def test_empty_context(self):
        self.assertEqual(h.write_packet([], P()), [])


class Lead(unittest.TestCase):
    def test_two_values_detected(self):
        ev = [h.item(DOCS[0]), h.item(DOCS[1])]
        self.assertEqual(h.lead_detect("acme", "city", ev), {"detected": True, "values": ["Bergen", "Oslo"]})

    def test_one_claim_not_detected(self):
        self.assertFalse(h.lead_detect("acme", "city", [h.item(DOCS[0]), h.item(DOCS[2]), h.item(DOCS[3])])["detected"])

    def test_same_claim_twice_not_detected(self):
        self.assertFalse(h.lead_detect("acme", "city", [h.item(DOCS[0]), h.item(DOCS[0])])["detected"])

    def test_filler_values_do_not_count(self):
        ev = [h.item(DOCS[0]), h.item(DOCS[3])]
        self.assertFalse(h.lead_detect("acme", "city", ev)["detected"])

    def test_lead_never_names_a_winner(self):
        out = h.lead_detect("acme", "city", [h.item(DOCS[0]), h.item(DOCS[1])])
        self.assertEqual(sorted(out), ["detected", "values"])

    def test_lead_receives_items_only(self):
        seen = []
        original = h.lead_detect

        def spy(entity, attribute, evidence):
            seen.extend(evidence)
            return original(entity, attribute, evidence)

        h.lead_detect = spy
        try:
            row(split_case())
        finally:
            h.lead_detect = original
        self.assertTrue(seen)
        for entry in seen:
            self.assertEqual(sorted(entry), ["attribute", "doc", "entity", "value"])

    def test_lead_misses_a_dropped_claim_even_if_workers_held_it(self):
        r = row(split_case(pa=P("id_desc", 1)))
        self.assertEqual((r["both_retrieved"], r["lead_detected"], r["dropped_claims"]), (True, False, ["d_a"]))


class Verdict(unittest.TestCase):
    def test_truth_table(self):
        self.assertEqual(h.verdict(True, True), ("PASS", "detected"))
        self.assertEqual(h.verdict(True, False), ("FAIL", "handoff_failure"))
        self.assertEqual(h.verdict(False, False), ("FAIL", "not_retrieved"))
        self.assertEqual(h.verdict(False, True), ("FAIL", "not_retrieved"))

    def test_both_retrieved_lead_missed_is_fail_not_pass(self):
        r = row(split_case(pb=P("id_desc", 1)))
        self.assertTrue(r["both_retrieved"])
        self.assertFalse(r["lead_detected"])
        self.assertEqual((r["verdict"], r["reason"]), ("FAIL", "handoff_failure"))

    def test_retrieval_alone_is_not_a_pass(self):
        r = row(same_case(pa=P("id_desc", 2)))
        self.assertEqual((r["both_retrieved"], r["verdict"]), (True, "FAIL"))

    def test_split_both_reported_passes(self):
        r = row(split_case())
        self.assertEqual((r["both_retrieved"], r["lead_detected"], r["verdict"]), (True, True, "PASS"))

    def test_split_either_drop_fails(self):
        for pa, pb in ((P("id_desc", 1), P()), (P(), P("id_desc", 1)), (P("id_desc", 1), P("id_desc", 1))):
            r = row(split_case(pa=pa, pb=pb))
            self.assertEqual(r["verdict"], "FAIL")

    def test_split_drop_lists(self):
        self.assertEqual(row(split_case(pa=P("id_desc", 1), pb=P("id_desc", 1)))["dropped_claims"], ["d_a", "d_b"])
        self.assertEqual(row(split_case(pb=P("id_desc", 1)))["dropped_claims"], ["d_b"])

    def test_same_worker_reports_both_passes(self):
        r = row(same_case())
        self.assertEqual((r["verdict"], r["reported_claims"], r["dropped_claims"]), ("PASS", ["d_a", "d_b"], []))

    def test_same_worker_budget_one_fails(self):
        r = row(same_case(pa=P("id_asc", 1)))
        self.assertEqual((r["verdict"], r["dropped_claims"]), ("FAIL", ["d_b"]))

    def test_single_agent_has_no_packet_and_passes(self):
        r = row(single_case())
        self.assertEqual((r["verdict"], r["lead_detected"], r["reported_claims"]), ("PASS", True, ["d_a", "d_b"]))

    def test_idle_worker_packet_does_not_matter(self):
        self.assertEqual(row(same_case(pb=P("id_desc", 1)))["verdict"], "PASS")


class Expiry(unittest.TestCase):
    def test_missing_packet_denies(self):
        case = split_case()
        case["packets"]["w_b"] = None
        r = row(case)
        self.assertEqual((r["verdict"], r["reason"], r["denied_workers"]), ("DENY", "missing_packet", ["w_b"]))
        self.assertTrue(r["both_retrieved"])
        self.assertFalse(r["lead_detected"])

    def test_expired_packet_denies(self):
        r = row(split_case(pa=P(exp=9)), now=10)
        self.assertEqual((r["verdict"], r["reason"], r["denied_workers"]), ("DENY", "expired_packet", ["w_a"]))

    def test_expiry_on_now_is_still_valid(self):
        self.assertEqual(row(split_case(pa=P(exp=10)), now=10)["verdict"], "PASS")

    def test_expiry_is_judged_by_fixture_now(self):
        case = split_case()
        self.assertEqual(row(case, now=20)["verdict"], "PASS")
        self.assertEqual(row(case, now=21)["verdict"], "DENY")

    def test_idle_worker_missing_packet_denies(self):
        case = same_case()
        case["packets"]["w_b"] = None
        self.assertEqual(row(case)["verdict"], "DENY")

    def test_both_denied_lists_both_workers(self):
        case = split_case()
        case["packets"]["w_a"] = None
        case["packets"]["w_b"] = None
        self.assertEqual(row(case)["denied_workers"], ["w_a", "w_b"])

    def test_deny_beats_a_good_handoff(self):
        case = split_case(pb=P(issued=1, exp=3), pa=P())
        self.assertEqual(row(case)["verdict"], "DENY")

    def test_on_expiry_is_deny(self):
        self.assertEqual(h.ON_EXPIRY, "DENY")
        self.assertEqual(main_report()["on_expiry"], "DENY")


class Fixtures(unittest.TestCase):
    def test_main_rows(self):
        got = {r["case"]: (r["verdict"], r["reason"]) for r in main_report()["rows"]}
        self.assertEqual(got, {
            "c1_single": ("PASS", "detected"), "c1_same": ("PASS", "detected"), "c1_split": ("PASS", "detected"),
            "c2_single": ("PASS", "detected"), "c2_same": ("FAIL", "handoff_failure"),
            "c2_split": ("FAIL", "handoff_failure"), "c3_single": ("PASS", "detected"),
            "c3_same": ("PASS", "detected"), "c3_split": ("FAIL", "handoff_failure")})

    def test_main_totals(self):
        t = main_report()["totals"]
        self.assertEqual(t["single_agent"], {"cases": 3, "both_retrieved": 3, "lead_detected": 3, "pass": 3, "fail": 0, "deny": 0, "handoff_failure": 0})
        self.assertEqual(t["delegated_same"], {"cases": 3, "both_retrieved": 3, "lead_detected": 2, "pass": 2, "fail": 1, "deny": 0, "handoff_failure": 1})
        self.assertEqual(t["delegated_split"], {"cases": 3, "both_retrieved": 3, "lead_detected": 1, "pass": 1, "fail": 2, "deny": 0, "handoff_failure": 2})

    def test_main_both_retrieved_everywhere(self):
        self.assertTrue(all(r["both_retrieved"] for r in main_report()["rows"]))

    def test_main_retrieval_exceeds_detection(self):
        rows = main_report()["rows"]
        self.assertGreater(sum(r["both_retrieved"] for r in rows), sum(r["lead_detected"] for r in rows))

    def test_main_never_a_pass_when_lead_missed(self):
        for r in main_report()["rows"]:
            if r["both_retrieved"] and not r["lead_detected"]:
                self.assertEqual(r["verdict"], "FAIL")
            if r["verdict"] == "PASS":
                self.assertTrue(r["lead_detected"])

    def test_same_documents_across_layouts(self):
        root = h.load(os.path.join(FX, "main.json"))
        by = {}
        for case in root["cases"]:
            by.setdefault(case["id"][:2], set()).add(tuple(sorted(case["claims"])))
        self.assertEqual(sorted(by), ["c1", "c2", "c3"])
        self.assertTrue(all(len(v) == 1 for v in by.values()))
        self.assertEqual({c["layout"] for c in root["cases"]}, set(h.LAYOUTS))

    def test_expired_rows(self):
        got = {r["case"]: (r["verdict"], r["reason"]) for r in expired_report()["rows"]}
        self.assertEqual(got, {"e_single": ("PASS", "detected"), "e_same_expired": ("DENY", "expired_packet"),
                               "e_split_missing": ("DENY", "missing_packet"), "e_split_fresh": ("PASS", "detected")})

    def test_expired_totals_count_deny_rows_in_both_retrieved(self):
        t = expired_report()["totals"]
        same = {k: t["delegated_same"][k] for k in ("cases", "both_retrieved", "deny")}
        split = {k: t["delegated_split"][k] for k in ("cases", "both_retrieved", "deny")}
        self.assertEqual(same, {"cases": 1, "both_retrieved": 1, "deny": 1})
        self.assertEqual(split, {"cases": 2, "both_retrieved": 2, "deny": 1})

    def test_deterministic(self):
        a = json.dumps(main_report(), sort_keys=True)
        self.assertEqual(a, json.dumps(main_report(), sort_keys=True))

    def test_report_has_no_wall_clock(self):
        self.assertEqual(main_report()["now"], 10)


class Validation(unittest.TestCase):
    def good(self):
        return make([same_case(), split_case(), single_case()])

    def test_good_fixture_runs(self):
        self.assertEqual(len(h.run(self.good())["rows"]), 3)

    def test_unknown_root_key(self):
        root = self.good()
        root["extra"] = 1
        denies(self, root, "unknown_key")

    def test_missing_root_key(self):
        root = self.good()
        del root["now"]
        denies(self, root, "missing_key")

    def test_bad_version(self):
        root = self.good()
        root["fixture_version"] = True
        denies(self, root, "bad_version")

    def test_on_expiry_other(self):
        root = self.good()
        root["on_expiry"] = "HOLD"
        denies(self, root, "bad_on_expiry")

    def test_now_bool_negative_string(self):
        for bad in (True, -1, "3", 1.5, 10000):
            root = self.good()
            root["now"] = bad
            denies(self, root, "bad_time")

    def test_unknown_layout(self):
        root = self.good()
        root["cases"][0]["layout"] = "delegated_all"
        denies(self, root, "unknown_layout")

    def test_duplicate_case_id(self):
        denies(self, make([same_case(cid="x"), split_case(cid="x")]), "duplicate_id")

    def test_duplicate_doc_id(self):
        root = self.good()
        root["docs"].append(copy.deepcopy(root["docs"][0]))
        denies(self, root, "duplicate_id")

    def test_duplicate_worker(self):
        root = self.good()
        root["workers"].append("w_a")
        denies(self, root, "duplicate_id")

    def test_unknown_worker_in_assign(self):
        case = split_case()
        case["assign"]["w_z"] = case["assign"].pop("w_b")
        case["packets"]["w_z"] = case["packets"].pop("w_b")
        denies(self, make([case]), "unknown_worker")

    def test_packet_for_unassigned_worker(self):
        case = split_case()
        case["packets"]["w_solo"] = P()
        denies(self, make([case]), "unknown_worker")

    def test_missing_packet_key(self):
        case = split_case()
        del case["packets"]["w_b"]
        denies(self, make([case]), "missing_key")

    def test_packets_on_single_agent(self):
        case = single_case()
        case["packets"] = {"w_solo": P()}
        denies(self, make([case]), "packet_not_expected")

    def test_layout_mismatch(self):
        case = split_case()
        case["layout"] = "delegated_same"
        denies(self, make([case]), "layout_mismatch")
        case = same_case()
        case["layout"] = "single_agent"
        denies(self, make([case]), "layout_mismatch")

    def test_claim_unassigned(self):
        case = split_case()
        case["assign"]["w_b"] = ["f_y"]
        denies(self, make([case]), "claim_unassigned")

    def test_doc_assigned_twice(self):
        case = split_case()
        case["assign"]["w_b"].append("f_x")
        denies(self, make([case]), "duplicate_id")

    def test_unknown_doc(self):
        case = split_case()
        case["assign"]["w_b"].append("f_none")
        denies(self, make([case]), "unknown_doc")

    def test_claims_same_value(self):
        root = self.good()
        root["docs"][1]["value"] = "Oslo"
        denies(self, root, "no_conflict")

    def test_claim_about_other_entity(self):
        root = self.good()
        root["docs"][1]["entity"] = "zeta"
        denies(self, root, "claim_mismatch")

    def test_three_claims(self):
        case = split_case()
        case["claims"] = ["d_a", "d_b", "f_x"]
        denies(self, make([case]), "bad_claims")

    def test_filler_repeats_conflict(self):
        root = self.good()
        root["docs"].append(D("f_z", "acme", "city", "Rome"))
        root["cases"][0]["assign"]["w_b"].append("f_z")
        denies(self, root, "filler_conflict")

    def test_packet_unknown_rule(self):
        denies(self, make([split_case(pa=P("vote"))]), "unknown_rule")

    def test_packet_budget_bad(self):
        for bad in (True, 0, 21, "1", 1.0):
            denies(self, make([split_case(pa=dict(P(), budget=bad))]), "bad_budget")

    def test_packet_window(self):
        denies(self, make([split_case(pa=P(issued=8, exp=7))]), "bad_packet_window")
        denies(self, make([split_case(pa=P(issued=11, exp=20))]), "bad_packet_window")

    def test_packet_extra_or_missing_field(self):
        packet = P()
        packet["votes"] = 3
        denies(self, make([split_case(pa=packet)]), "unknown_key")
        packet = P()
        del packet["expires_at"]
        denies(self, make([split_case(pa=packet)]), "missing_key")

    def test_empty_lists(self):
        for name in ("workers", "docs", "cases"):
            root = self.good()
            root[name] = []
            self.assertRaises(h.Deny, h.run, root)

    def test_bad_text_value(self):
        root = self.good()
        root["docs"][0]["value"] = " Oslo"
        denies(self, root, "bad_text")

    def test_interior_invisible_characters_in_values_are_denied(self):
        # "Oslo" vs "Oslo" plus a zero-width space must not be scored as a conflict: both are denied as text.
        for ch in ("\u200b", "\u200d", "\ufeff", "\u00ad", "\u0080", "\u0085", "\u009f", "\u00a0", "\u3000", "\u2028",
                   "\u2029", "\ue000", "\ud800", "\u3164", "\u2800", "\x1b", "\x7f"):
            root = self.good()
            root["docs"][0]["value"] = "Os%slo" % ch
            denies(self, root, "bad_text")
            root = self.good()
            root["docs"][1]["value"] = "Oslo" + ch + "x"
            denies(self, root, "bad_text")

    def test_zero_width_look_alike_cannot_fake_a_conflict(self):
        root = self.good()
        root["docs"][0]["value"] = "Oslo"
        root["docs"][1]["value"] = "Oslo\u200b"
        denies(self, root, "bad_text")

    def test_korean_and_plain_inner_space_values_are_accepted(self):
        root = self.good()
        root["docs"][0]["value"] = "\uc11c\uc6b8 \ud2b9\ubcc4\uc2dc"
        root["docs"][1]["value"] = "\ubd80\uc0b0"
        self.assertEqual(h.run(root)["docs"], len(root["docs"]))

    def test_bad_ids(self):
        root = self.good()
        root["docs"][0]["id"] = "D A"
        denies(self, root, "bad_id")

    def test_wrong_types(self):
        for value in (None, [], "x", 3):
            root = self.good()
            root["cases"][0]["assign"] = value
            self.assertRaises(h.Deny, h.run, root)


class Direct(unittest.TestCase):
    """Calls below the fixture validator, so internal checks do not rest on validation alone."""

    def norm(self, claims_assigned):
        return {"id": "n", "layout": "delegated_split", "entity": "acme", "attribute": "city",
                "claims": ["d_a", "d_b"], "assign": {"w_a": claims_assigned, "w_b": ["f_y"]},
                "packets": {"w_a": P("id_asc", 5), "w_b": P()}}

    def test_unretrieved_claim_is_fail(self):
        docs = {d["id"]: d for d in DOCS}
        r = h.profile_case(self.norm(["d_a", "f_x"]), docs, 10)
        self.assertEqual((r["both_retrieved"], r["lead_detected"], r["verdict"], r["reason"]),
                         (False, False, "FAIL", "not_retrieved"))

    def test_nothing_retrieved_is_fail(self):
        docs = {d["id"]: d for d in DOCS}
        r = h.profile_case(self.norm(["f_x"]), docs, 10)
        self.assertEqual((r["both_retrieved"], r["verdict"]), (False, "FAIL"))

    def test_both_retrieved_row(self):
        docs = {d["id"]: d for d in DOCS}
        r = h.profile_case(self.norm(["d_a", "d_b"]), docs, 10)
        self.assertEqual((r["both_retrieved"], r["verdict"]), (True, "PASS"))

    def test_report_values_and_reported_claims(self):
        r = row(split_case())
        self.assertEqual((r["lead_values"], r["reported_claims"]), (["Bergen", "Oslo"], ["d_a", "d_b"]))
        r = row(split_case(pa=P("id_desc", 1)))
        self.assertEqual((r["lead_values"], r["reported_claims"]), (["Bergen"], ["d_b"]))

    def test_totals_count_reasons_not_all_fails(self):
        original = h.profile_case

        def fake(case, docs, now):
            r = original(case, docs, now)
            r.update(verdict="FAIL", reason="not_retrieved", both_retrieved=False)
            return r

        h.profile_case = fake
        try:
            t = h.run(make([split_case()]))["totals"]["delegated_split"]
        finally:
            h.profile_case = original
        self.assertEqual((t["fail"], t["handoff_failure"], t["pass"], t["lead_detected"], t["both_retrieved"]), (1, 0, 0, 1, 0))

    def test_layout_shapes(self):
        ok = {"single_agent": {"w": ["a", "b"]}, "delegated_same": {"w": ["a", "b"], "v": []},
              "delegated_split": {"w": ["a"], "v": ["b"]}}
        for layout, holds in ok.items():
            h._layout_shape(layout, holds)
        bad = [("single_agent", {"w": ["a"]}), ("single_agent", {"w": ["a"], "v": ["b"]}),
               ("delegated_same", {"w": ["a"], "v": ["b"]}), ("delegated_same", {"w": ["a", "b"]}),
               ("delegated_split", {"w": ["a", "b"], "v": []}), ("delegated_split", {"w": ["a"], "v": ["b"], "u": []}),
               ("delegated_split", {"w": ["a"], "v": []})]
        for layout, holds in bad:
            with self.assertRaises(h.Deny, msg=(layout, holds)):
                h._layout_shape(layout, holds)

    def test_claim_about_other_attribute(self):
        root = make([split_case()])
        root["docs"][1]["attribute"] = "year"
        denies(self, root, "claim_mismatch")

    def test_repeated_claim_id(self):
        case = split_case()
        case["claims"] = ["d_a", "d_a"]
        denies(self, make([case]), "duplicate_id")

    def test_non_utf8_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.json")
            with open(path, "wb") as handle:
                handle.write(b"\xff\xfe{}")
            rc = h.main([path], io.StringIO(), io.StringIO())
        self.assertEqual(rc, 2)


class StrictJson(unittest.TestCase):
    def test_duplicate_key(self):
        with self.assertRaises(h.Deny) as ctx:
            h.parse_text('{"a": 1, "a": 2}')
        self.assertEqual(ctx.exception.code, "duplicate_key")

    def test_nested_duplicate_key(self):
        self.assertRaises(h.Deny, h.parse_text, '{"a": {"b": 1, "b": 2}}')

    def test_non_finite(self):
        for text in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.assertRaises(h.Deny) as ctx:
                h.parse_text(text)
            self.assertEqual(ctx.exception.code, "non_finite_number")

    def test_bom(self):
        with self.assertRaises(h.Deny) as ctx:
            h.parse_text("\ufeff{}")
        self.assertEqual(ctx.exception.code, "bom_not_permitted")

    def test_bad_json(self):
        with self.assertRaises(h.Deny) as ctx:
            h.parse_text("{")
        self.assertEqual(ctx.exception.code, "bad_json")

    def test_unreadable(self):
        with self.assertRaises(h.Deny) as ctx:
            h.load(os.path.join(FX, "no_such.json"))
        self.assertEqual(ctx.exception.code, "fixture_unreadable")


class Cli(unittest.TestCase):
    def call(self, argv):
        out, err = io.StringIO(), io.StringIO()
        rc = h.main(argv, out, err)
        return rc, out.getvalue(), err.getvalue()

    def test_main_exit_zero_json(self):
        rc, out, err = self.call([os.path.join(FX, "main.json")])
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(json.loads(out)["totals"]["delegated_split"]["fail"], 2)

    def test_expired_exits_two_with_deny_rows(self):
        rc, out, err = self.call([os.path.join(FX, "expired.json")])
        self.assertEqual((rc, err), (2, ""))
        self.assertEqual(sum(1 for r in json.loads(out)["rows"] if r["verdict"] == "DENY"), 2)

    def test_main_fixture_has_no_deny_row(self):
        rc, out, _ = self.call([os.path.join(FX, "main.json")])
        self.assertEqual(rc, 0)
        self.assertNotIn("DENY", [r["verdict"] for r in json.loads(out)["rows"]])

    def test_subprocess_expired_exit_two(self):
        res = subprocess.run([sys.executable, "-B", os.path.join(HERE, "handoff.py"),
                              os.path.join(FX, "expired.json")], capture_output=True, text=True)
        self.assertEqual((res.returncode, res.stderr), (2, ""))
        self.assertEqual(sum(1 for r in json.loads(res.stdout)["rows"] if r["verdict"] == "DENY"), 2)

    def test_demo_exits_zero_on_purpose(self):
        res = subprocess.run([sys.executable, "-B", os.path.join(HERE, "demo.py")],
                             capture_output=True, text=True, cwd=HERE)
        self.assertEqual((res.returncode, res.stderr), (0, ""))
        self.assertIn("DENY", res.stdout)

    def test_usage(self):
        for argv in ([], ["a", "b"], ["-x"]):
            rc, out, err = self.call(argv)
            self.assertEqual((rc, out), (2, ""))
            self.assertTrue(err.startswith("DENY usage:"))

    def test_bad_fixtures_deny_exit_two(self):
        paths = sorted(glob.glob(os.path.join(FX, "bad_*.json")))
        self.assertGreaterEqual(len(paths), 11)
        for path in paths:
            rc, out, err = self.call([path])
            self.assertEqual((rc, out), (2, ""), path)
            self.assertEqual(len(err.splitlines()), 1, path)
            self.assertRegex(err, r"^DENY [a-z_]+: ", path)

    def test_bad_fixture_codes(self):
        want = {"bad_duplicate_key": "duplicate_key", "bad_missing_packet": "missing_key",
                "bad_packet_window": "bad_packet_window", "bad_unknown_layout": "unknown_layout",
                "bad_duplicate_case_id": "duplicate_id", "bad_unknown_worker": "unknown_worker",
                "bad_missing_field": "missing_key", "bad_layout_mismatch": "layout_mismatch",
                "bad_no_conflict": "no_conflict", "bad_filler_conflict": "filler_conflict",
                "bad_unknown_rule": "unknown_rule", "bad_budget_bool": "bad_budget",
                "bad_on_expiry": "bad_on_expiry", "bad_now_string": "bad_time",
                "bad_packet_on_single": "packet_not_expected"}
        for name, code in want.items():
            rc, out, err = self.call([os.path.join(FX, name + ".json")])
            self.assertEqual(rc, 2, name)
            self.assertTrue(err.startswith("DENY %s:" % code), (name, err))

    def test_subprocess_deny(self):
        res = subprocess.run([sys.executable, "-B", os.path.join(HERE, "handoff.py"),
                              os.path.join(FX, "bad_duplicate_key.json")], capture_output=True, text=True)
        self.assertEqual((res.returncode, res.stdout), (2, ""))
        self.assertTrue(res.stderr.startswith("DENY duplicate_key:"))

    def test_subprocess_main(self):
        res = subprocess.run([sys.executable, "-B", os.path.join(HERE, "handoff.py"),
                              os.path.join(FX, "main.json")], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(json.loads(res.stdout), json.loads(json.dumps(main_report())))


class Hygiene(unittest.TestCase):
    def source(self):
        with open(os.path.join(HERE, "handoff.py"), encoding="utf-8") as handle:
            return handle.read()

    def test_stdlib_imports_only(self):
        mods = set(re.findall(r"^(?:import|from) (\w+)", self.source(), re.M))
        self.assertEqual(mods, {"json", "math", "re", "sys", "unicodedata"})

    def test_no_wall_clock_or_random(self):
        src = self.source()
        for word in ("time.", "datetime", "random", "socket", "urllib", "subprocess", "hashlib", "hmac"):
            self.assertNotIn(word, src)

    def test_evidence_json_marks_paper_figures_unverified(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as handle:
            ev = json.load(handle)
        claims = ev["on_unmeasured"]["claims"]
        self.assertGreaterEqual(len(claims), 5)
        self.assertTrue(all(c["status"] == "UNVERIFIED" for c in claims))
        text = json.dumps({k: v for k, v in ev.items() if k != "on_unmeasured"})
        for number in re.findall(r"\d+\.\d+", json.dumps(claims)):
            self.assertNotIn(number, text)

    def test_evidence_counts_match_run(self):
        with open(os.path.join(HERE, "evidence.json"), encoding="utf-8") as handle:
            ev = json.load(handle)
        self.assertEqual(ev["measured"]["main_totals"], main_report()["totals"])


if __name__ == "__main__":
    unittest.main()
