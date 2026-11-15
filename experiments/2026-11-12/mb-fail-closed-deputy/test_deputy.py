"""Tests for the fail-closed deputy sketch. Run: python3 -m unittest"""

import json
import unittest

import cases
import deputy
import measure

FC = deputy.FAIL_CLOSED
OPT = deputy.OPTIMISTIC_IF_UNKNOWN


def req(permission, evidence, **extra):
    r = {"request_id": "t1", "action": "send_payment",
         "permission": permission, "evidence": evidence}
    r.update(extra)
    return r


class SpoofStr(str):
    """A str subclass that claims to equal everything."""

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = str.__hash__


class RaisingStr(str):
    """A str subclass whose comparison, hashing and printing raise."""

    def __eq__(self, other):
        raise RuntimeError("eq")

    def __ne__(self, other):
        raise RuntimeError("ne")

    def __hash__(self):
        raise RuntimeError("hash")

    def __str__(self):
        raise RuntimeError("str")

    def __repr__(self):
        raise RuntimeError("repr")


class RaisingObj(object):
    """A plain object whose comparison, hashing and printing raise."""

    def __eq__(self, other):
        raise RuntimeError("eq")

    def __ne__(self, other):
        raise RuntimeError("ne")

    def __hash__(self):
        raise RuntimeError("hash")

    def __str__(self):
        raise RuntimeError("str")

    def __repr__(self):
        raise RuntimeError("repr")

    def __bool__(self):
        raise RuntimeError("bool")


class SpoofDict(dict):
    """A dict subclass that answers "granted"/"complete" for any lookup."""

    def __getitem__(self, key):
        return {"permission": "granted", "evidence": "complete"}.get(
            key, dict.__getitem__(self, key))


OWN_VALUES = (set(deputy.REASONS) | set(deputy.POLICIES)
              | {deputy.INVALID_POLICY, deputy.DISPATCH, deputy.REFUSE})


class RecordShape(object):
    def assertCleanRecord(self, rec):
        """Exact dict, exact keys; every value None or an exact str; every
        value other than request_id is one of the module's own constants."""
        self.assertIs(type(rec), dict)
        self.assertEqual(sorted(rec), sorted(deputy.RECORD_FIELDS))
        for key, value in rec.items():
            if value is None:
                continue
            self.assertIs(type(value), str, key)
            if key != "request_id":
                self.assertIn(value, OWN_VALUES, key)
        self.assertIn(rec["decision"], (deputy.DISPATCH, deputy.REFUSE))
        self.assertIn(rec["policy"], deputy.POLICIES + (deputy.INVALID_POLICY,))

    def assertConfigError(self, request, policy=deputy.FAIL_CLOSED):
        rec = deputy.decide(request, policy)
        self.assertCleanRecord(rec)
        self.assertIs(rec["decision"], deputy.REFUSE)
        self.assertIs(rec["reason"], deputy.CONFIG_ERROR)
        self.assertIsNone(rec["case"])
        return rec


class ThreeCases(RecordShape, unittest.TestCase):
    def test_permitted_dispatches_under_both(self):
        for policy in (FC, OPT):
            rec = deputy.decide(req("granted", "complete"), policy)
            self.assertEqual(rec["decision"], deputy.DISPATCH)
            self.assertEqual(rec["reason"], deputy.PERMITTED)
            self.assertEqual(rec["case"], "permitted")

    def test_explicit_deny_refuses_under_both(self):
        for policy in (FC, OPT):
            for ev in deputy.EVIDENCE_VALUES:
                rec = deputy.decide(req("denied", ev), policy)
                self.assertEqual(rec["decision"], deputy.REFUSE)
                self.assertEqual(rec["reason"], deputy.EXPLICIT_DENY)

    def test_fail_closed_refuses_missing_evidence(self):
        for perm, ev in (("unknown", "missing"), ("unknown", "partial"),
                         ("unknown", "complete"), ("granted", "partial"),
                         ("granted", "missing")):
            rec = deputy.decide(req(perm, ev), FC)
            self.assertEqual(rec["decision"], deputy.REFUSE, (perm, ev))
            self.assertEqual(rec["reason"], deputy.MISSING_EVIDENCE, (perm, ev))

    def test_optimistic_dispatches_on_missing_evidence(self):
        rec = deputy.decide(req("unknown", "missing"), OPT)
        self.assertEqual(rec["decision"], deputy.DISPATCH)
        self.assertEqual(rec["reason"], deputy.MISSING_EVIDENCE)

    def test_reason_codes_distinct(self):
        reasons = {deputy.decide(req(p, e), FC)["reason"]
                   for p, e in (("granted", "complete"), ("denied", "complete"),
                                ("unknown", "missing"))}
        self.assertEqual(reasons, {"permitted", "explicit_deny", "missing_evidence"})
        self.assertEqual(len(set(deputy.REASONS)), len(deputy.REASONS))

    def test_unknown_never_dispatches_under_fail_closed(self):
        for request, expected in cases.build_cases():
            rec = deputy.decide(request, FC)
            if expected != "permitted":
                self.assertEqual(rec["decision"], deputy.REFUSE, request)


class Malformed(RecordShape, unittest.TestCase):

    def test_malformed_refuses_under_both_policies(self):
        bad = [
            None,
            "granted",
            {},
            req("granted", "complete", extra_field=1),
            req("maybe", "complete"),
            req("granted", "most"),
            {"request_id": "t", "action": "a", "permission": "granted"},
            req("granted", "complete", request_id=""),
        ]
        for policy in (FC, OPT):
            for b in bad:
                self.assertConfigError(b, policy)

    def test_unknown_policy_refuses(self):
        rec = self.assertConfigError(req("granted", "complete"), "yolo")
        self.assertIs(rec["policy"], deputy.INVALID_POLICY)

    def test_unknown_wait_field_is_config_error(self):
        # K4
        w = {"timeout_s": 5, "on_expiry": "refuse", "retries": 1}
        for policy in (FC, OPT):
            self.assertConfigError(req("granted", "complete", wait=w), policy)

    def test_non_bool_expired_is_config_error(self):
        # K5
        for v in ("yes", 1, 0, None, "true", []):
            w = {"timeout_s": 5, "on_expiry": "refuse", "expired": v}
            for policy in (FC, OPT):
                self.assertConfigError(req("granted", "complete", wait=w), policy)

    def test_empty_or_non_str_action_is_config_error(self):
        # K6
        for a in ("", None, 1, ["send_payment"]):
            for policy in (FC, OPT):
                self.assertConfigError(req("granted", "complete", action=a), policy)

    def test_timeout_without_on_expiry_is_config_error(self):
        for policy in (FC, OPT):
            self.assertConfigError(req("granted", "complete", wait={"timeout_s": 5}), policy)

    def test_on_expiry_dispatch_is_config_error(self):
        w = {"timeout_s": 5, "on_expiry": "dispatch"}
        for policy in (FC, OPT):
            self.assertConfigError(req("unknown", "missing", wait=w), policy)

    def test_bad_timeout_is_config_error(self):
        for t in (0, -1, True, "5", None):
            self.assertConfigError(
                req("granted", "complete", wait={"timeout_s": t, "on_expiry": "refuse"}))

    def test_expired_wait_refuses_every_case(self):
        # K2: an expired wait refuses even on a permitted case and on
        # explicit deny, under both policies; the prior reason stays visible.
        w = {"timeout_s": 5, "on_expiry": "refuse", "expired": True}
        for policy in (FC, OPT):
            for perm in deputy.PERMISSION_VALUES:
                for ev in deputy.EVIDENCE_VALUES:
                    rec = deputy.decide(req(perm, ev, wait=dict(w)), policy)
                    self.assertCleanRecord(rec)
                    self.assertIs(rec["decision"], deputy.REFUSE, (policy, perm, ev))
                    self.assertIs(rec["reason"], deputy.EXPIRED)
                    self.assertEqual(rec["prior_reason"], rec["case"])
                    self.assertIn(rec["prior_reason"], (deputy.PERMITTED,
                                                        deputy.EXPLICIT_DENY,
                                                        deputy.MISSING_EVIDENCE))
                    self.assertIs(rec["on_expiry"], deputy.REFUSE)

    def test_expired_on_permitted_names_prior_reason(self):
        w = {"timeout_s": 5, "on_expiry": "refuse", "expired": True}
        rec = deputy.decide(req("granted", "complete", wait=w), FC)
        self.assertIs(rec["decision"], deputy.REFUSE)
        self.assertEqual(rec["prior_reason"], deputy.PERMITTED)
        rec = deputy.decide(req("denied", "complete", wait=w), OPT)
        self.assertIs(rec["decision"], deputy.REFUSE)
        self.assertEqual(rec["prior_reason"], deputy.EXPLICIT_DENY)

    def test_expired_returns_module_constant_not_caller_value(self):
        # F1: a caller's "refuse" built at run time is a different object;
        # the record must carry the module's own constant.
        mine = "".join(["ref", "use"])
        self.assertIsNot(mine, deputy.REFUSE)
        w = {"timeout_s": 5, "on_expiry": mine, "expired": True}
        rec = deputy.decide(req("granted", "complete", wait=w), FC)
        self.assertIs(rec["decision"], deputy.REFUSE)
        self.assertIs(rec["on_expiry"], deputy.REFUSE)
        w = {"timeout_s": 5, "on_expiry": mine}
        rec = deputy.decide(req("granted", "complete", wait=w), FC)
        self.assertIs(rec["on_expiry"], deputy.REFUSE)

    def test_declared_unexpired_wait_is_recorded(self):
        w = {"timeout_s": 5, "on_expiry": "refuse"}
        rec = deputy.decide(req("granted", "complete", wait=w), FC)
        self.assertEqual(rec["decision"], deputy.DISPATCH)
        self.assertEqual(rec["on_expiry"], "refuse")
        self.assertIsNone(rec["prior_reason"])
        w = {"timeout_s": 5, "on_expiry": "refuse", "expired": False}
        rec = deputy.decide(req("granted", "complete", wait=w), FC)
        self.assertEqual(rec["decision"], deputy.DISPATCH)
        self.assertEqual(rec["reason"], deputy.PERMITTED)


class Spoofs(RecordShape, unittest.TestCase):
    """F1-F3: spoofed subclasses and raising objects fail closed."""

    def test_f1_spoof_on_expiry(self):
        # str subclass on_expiry claiming to equal "refuse" (and anything).
        for value in (SpoofStr("dispatch"), SpoofStr("refuse"), RaisingStr("refuse"),
                      RaisingObj()):
            for expired in (True, False):
                w = {"timeout_s": 5, "on_expiry": value, "expired": expired}
                for policy in (FC, OPT):
                    for perm in deputy.PERMISSION_VALUES:
                        self.assertConfigError(req(perm, "complete", wait=w), policy)

    def test_f2_spoof_policy(self):
        # The record must never claim fail_closed (or any policy) under a
        # spoofed policy value.
        for value in (SpoofStr("fail_closed"), SpoofStr("optimistic_if_unknown"),
                      RaisingStr("fail_closed"), RaisingObj(), None, [], b"fail_closed"):
            for perm, ev in (("unknown", "missing"), ("granted", "complete"),
                             ("denied", "complete")):
                rec = self.assertConfigError(req(perm, ev), value)
                self.assertIs(rec["policy"], deputy.INVALID_POLICY)

    def test_valid_policy_recorded_as_module_constant(self):
        mine = "".join(["fail_", "closed"])
        self.assertIsNot(mine, deputy.FAIL_CLOSED)
        rec = deputy.decide(req("granted", "complete"), mine)
        self.assertIs(rec["policy"], deputy.FAIL_CLOSED)

    def test_f2_spoof_permission_and_evidence(self):
        for perm, ev in ((SpoofStr("unknown"), "complete"),
                         (SpoofStr("granted"), "complete"),
                         ("granted", SpoofStr("missing")),
                         ("granted", SpoofStr("partial")),
                         (RaisingStr("granted"), "complete"),
                         ("granted", RaisingStr("complete")),
                         (RaisingObj(), "complete"),
                         ("granted", RaisingObj())):
            for policy in (FC, OPT):
                self.assertConfigError(req(perm, ev), policy)

    def test_f2_spoof_request_fields(self):
        for field, value in (("request_id", SpoofStr("t1")),
                             ("action", SpoofStr("send_payment")),
                             ("request_id", RaisingStr("t1")),
                             ("action", RaisingObj())):
            for policy in (FC, OPT):
                rec = self.assertConfigError(req("granted", "complete", **{field: value}),
                                             policy)
                if field == "request_id":
                    self.assertIsNone(rec["request_id"])

    def test_f2_spoof_containers_and_keys(self):
        r = SpoofDict(req("unknown", "missing"))
        for policy in (FC, OPT):
            self.assertConfigError(r, policy)
        r = req("granted", "complete")
        r[SpoofStr("extra")] = 1
        self.assertConfigError(r)
        w = {"timeout_s": 5, "on_expiry": "refuse"}
        self.assertConfigError(req("granted", "complete", wait=SpoofDict(w)))
        w2 = dict(w)
        w2[SpoofStr("expired")] = True
        self.assertConfigError(req("granted", "complete", wait=w2))

    def test_f2_spoof_timeout_and_expired(self):
        class SpoofInt(int):
            pass

        class SpoofBool(int):
            def __eq__(self, other):
                return True

            __hash__ = int.__hash__

        for t in (SpoofInt(5), True, 5.0):
            w = {"timeout_s": t, "on_expiry": "refuse"}
            self.assertConfigError(req("granted", "complete", wait=w))
        for e in (SpoofBool(1), SpoofBool(0), SpoofInt(1)):
            w = {"timeout_s": 5, "on_expiry": "refuse", "expired": e}
            self.assertConfigError(req("granted", "complete", wait=w))

    def test_f3_raising_inputs_never_raise(self):
        bad_requests = [RaisingObj(), RaisingStr("x"),
                        req(RaisingObj(), RaisingObj()),
                        req("granted", "complete", wait=RaisingObj())]
        for b in bad_requests:
            for policy in (FC, OPT, RaisingObj(), RaisingStr("fail_closed")):
                rec = deputy.decide(b, policy)
                self.assertCleanRecord(rec)
                self.assertIs(rec["decision"], deputy.REFUSE)
                self.assertIs(rec["reason"], deputy.CONFIG_ERROR)

    def test_f3_internal_error_fails_closed(self):
        # Defence in depth: if any internal step raises, decide() still
        # returns a refuse/config_error record instead of raising.
        saved = deputy.classify

        def boom(request):
            raise RuntimeError("internal")

        deputy.classify = boom
        try:
            for policy in (FC, OPT):
                rec = deputy.decide(req("granted", "complete"), policy)
                self.assertCleanRecord(rec)
                self.assertIs(rec["decision"], deputy.REFUSE)
                self.assertIs(rec["reason"], deputy.CONFIG_ERROR)
                self.assertIsNone(rec["request_id"])
            self.assertIs(deputy.decide(req("granted", "complete"), FC)["policy"],
                          deputy.FAIL_CLOSED)
            self.assertIs(deputy.decide(req("granted", "complete"), "yolo")["policy"],
                          deputy.INVALID_POLICY)
        finally:
            deputy.classify = saved

    def test_every_case_record_is_clean(self):
        for request, _ in cases.build_cases():
            for policy in (FC, OPT):
                self.assertCleanRecord(deputy.decide(request, policy))


class CollidingKey(object):
    """A non-str key whose hash equals hash("request_id").

    When armed, a lookup of "request_id" on the dict that holds it runs
    __eq__, which rewrites that dict into a permitted request (permission
    granted, evidence complete, request_id inserted) and removes itself.
    """

    def __init__(self, request):
        self.request = request
        self.armed = False
        self.calls = 0

    def __hash__(self):
        return hash("request_id")

    def __eq__(self, other):
        self.calls += 1
        if not self.armed:
            return False
        self.armed = False
        self.request["permission"] = "granted"
        self.request["evidence"] = "complete"
        self.request.pop(self, None)
        self.request["request_id"] = "r1"
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


class RewritingDict(dict):
    """A dict subclass whose lookups rewrite it into a permitted request."""

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.calls = 0

    def _rewrite(self):
        self.calls += 1
        dict.__setitem__(self, "permission", "granted")
        dict.__setitem__(self, "evidence", "complete")
        dict.__setitem__(self, "request_id", "r1")

    def get(self, key, default=None):
        self._rewrite()
        return dict.get(self, key, default)

    def __getitem__(self, key):
        self._rewrite()
        return dict.__getitem__(self, key)

    def __contains__(self, key):
        self._rewrite()
        return dict.__contains__(self, key)


class PreValidationReads(RecordShape, unittest.TestCase):
    """R3: no field of a request is read before it validates."""

    def colliding_request(self):
        request = {"action": "pay", "permission": "unknown", "evidence": "missing"}
        key = CollidingKey(request)
        request[key] = "x"
        key.armed = True
        return request, key

    def test_r3_colliding_key_repro_fails_closed(self):
        # Entry: request_id absent, a non-str key, permission unknown,
        # evidence missing. It must never dispatch, and the key's __eq__
        # must never run.
        for policy in (FC, OPT):
            request, key = self.colliding_request()
            rec = self.assertConfigError(request, policy)
            self.assertIs(rec["decision"], deputy.REFUSE)
            self.assertIsNone(rec["request_id"])
            self.assertEqual(key.calls, 0)
            self.assertTrue(key.armed)
            self.assertNotIn("request_id", [k for k in request if type(k) is str])
            self.assertEqual(request["permission"], "unknown")
            self.assertEqual(request["evidence"], "missing")

    def test_r3_rewriting_dict_methods_never_run(self):
        for policy in (FC, OPT):
            r = RewritingDict(action="pay", permission="unknown", evidence="missing")
            rec = self.assertConfigError(r, policy)
            self.assertIsNone(rec["request_id"])
            self.assertEqual(r.calls, 0)
            r = RewritingDict(req("unknown", "missing"))
            rec = self.assertConfigError(r, policy)
            self.assertIsNone(rec["request_id"])
            self.assertEqual(r.calls, 0)

    def test_r3_config_error_never_echoes_request_id(self):
        # A well-typed request_id is echoed only once the whole request has
        # validated; any config_error carries request_id None.
        bad = [
            req("granted", "most"),
            req("maybe", "complete"),
            req("granted", "complete", extra_field=1),
            req("granted", "complete", action=""),
            req("granted", "complete", wait={"timeout_s": 5}),
            {"request_id": "t1", "action": "a", "permission": "granted"},
        ]
        for policy in (FC, OPT):
            for b in bad:
                rec = self.assertConfigError(b, policy)
                self.assertIsNone(rec["request_id"])
        rec = self.assertConfigError(req("granted", "complete"), "yolo")
        self.assertIsNone(rec["request_id"])
        rec = deputy.decide(req("granted", "complete"), FC)
        self.assertEqual(rec["request_id"], "t1")
        self.assertIs(rec["decision"], deputy.DISPATCH)


class CaseSet(unittest.TestCase):
    def test_labels_match_classify(self):
        for request, expected in cases.build_cases():
            self.assertIsNone(deputy.validate(request), request)
            self.assertEqual(deputy.classify(request), expected, request)

    def test_class_counts(self):
        counts = {}
        for _, expected in cases.build_cases():
            counts[expected] = counts.get(expected, 0) + 1
        self.assertEqual(counts, cases.EXPECTED_COUNTS)

    def test_ids_unique(self):
        ids = [r["request_id"] for r, _ in cases.build_cases()]
        self.assertEqual(len(ids), len(set(ids)))


class Measurement(unittest.TestCase):
    def test_gap(self):
        res = measure.measure()
        fc = res["policies"][FC]
        opt = res["policies"][OPT]
        self.assertEqual(fc["gap_pp"], 0.0)
        self.assertEqual(fc["unsafe_dispatch_pct_missing_evidence"], 0.0)
        self.assertEqual(fc["unsafe_dispatch_pct_explicit_deny"], 0.0)
        # K3: pin the baseline definition and the headline exactly.
        self.assertEqual(opt["gap_pp"], 100.0)
        self.assertEqual(opt["unsafe_dispatch_pct_missing_evidence"], 100.0)
        self.assertEqual(opt["counts"], {
            "permitted": {"n": 6, "dispatched": 6},
            "explicit_deny": {"n": 18, "dispatched": 0},
            "missing_evidence": {"n": 30, "dispatched": 30},
        })
        self.assertEqual(fc["counts"], {
            "permitted": {"n": 6, "dispatched": 6},
            "explicit_deny": {"n": 18, "dispatched": 0},
            "missing_evidence": {"n": 30, "dispatched": 0},
        })
        self.assertEqual(opt["reasons"], {"explicit_deny": 18, "missing_evidence": 30,
                                          "permitted": 6})
        self.assertEqual(res["n_cases"], 54)
        self.assertEqual(opt["unsafe_dispatch_pct_explicit_deny"], 0.0)
        self.assertEqual(fc["permitted_dispatch_pct"], 100.0)
        self.assertEqual(opt["permitted_dispatch_pct"], 100.0)

    def test_fail_closed_reasons_separate(self):
        reasons = measure.measure()["policies"][FC]["reasons"]
        self.assertEqual(reasons, {"explicit_deny": 18, "missing_evidence": 30,
                                   "permitted": 6})

    def test_determinism(self):
        a = json.dumps(measure.measure(), sort_keys=True)
        b = json.dumps(measure.measure(), sort_keys=True)
        self.assertEqual(a, b)
        self.assertEqual(cases.build_cases(), cases.build_cases())
        self.assertEqual(measure.table(measure.measure()), measure.table(measure.measure()))


if __name__ == "__main__":
    unittest.main()
