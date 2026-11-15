"""Mutant runner: each mutant patches the code or the case set, then the
unittest suite runs. A mutant is killed when at least one test fails.

Two kinds of code mutant: wrappers around deputy functions, and source-text
mutants that replace one exact snippet of deputy.py (each snippet must occur
exactly once) and re-execute the patched source in memory inside the deputy
module. Nothing is written to disk.

Run: python3 mutants.py
Exit code 0 only when every mutant is killed and the clean suite passes.
"""

import io
import os
import sys
import unittest

import cases
import deputy
import test_deputy

ORIG_DECIDE = deputy.decide
ORIG_VALIDATE = deputy.validate
ORIG_CLASSIFY = deputy.classify
ORIG_BUILD = cases.build_cases
DEPUTY_SNAPSHOT = dict(vars(deputy))
DEPUTY_PATH = os.path.join(os.path.dirname(os.path.abspath(deputy.__file__)), "deputy.py")
with open(DEPUTY_PATH, "r", encoding="utf-8") as _fh:
    DEPUTY_SOURCE = _fh.read()


def source_mutant(*pairs):
    """Return an apply() that swaps each (old, new) snippet once in deputy.py."""
    def apply():
        text = DEPUTY_SOURCE
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError("snippet not found exactly once: %r" % (old,))
            text = text.replace(old, new)
        exec(compile(text, DEPUTY_PATH, "exec"), deputy.__dict__)
    return apply


# ---- code mutants -------------------------------------------------------

def m_collapse_missing_into_deny():
    def decide(request, policy=deputy.FAIL_CLOSED):
        rec = ORIG_DECIDE(request, policy)
        if rec["reason"] == deputy.MISSING_EVIDENCE:
            rec["reason"] = deputy.EXPLICIT_DENY
        return rec
    deputy.decide = decide


def m_fail_closed_dispatches_unknown():
    def decide(request, policy=deputy.FAIL_CLOSED):
        rec = ORIG_DECIDE(request, policy)
        if rec["reason"] == deputy.MISSING_EVIDENCE:
            rec["decision"] = deputy.DISPATCH
        return rec
    deputy.decide = decide


def m_optimistic_refuses_missing():
    def decide(request, policy=deputy.FAIL_CLOSED):
        rec = ORIG_DECIDE(request, policy)
        if rec["reason"] == deputy.MISSING_EVIDENCE:
            rec["decision"] = deputy.REFUSE
        return rec
    deputy.decide = decide


def m_optimistic_dispatches_deny():
    def decide(request, policy=deputy.FAIL_CLOSED):
        rec = ORIG_DECIDE(request, policy)
        if policy == deputy.OPTIMISTIC_IF_UNKNOWN and rec["reason"] == deputy.EXPLICIT_DENY:
            rec["decision"] = deputy.DISPATCH
        return rec
    deputy.decide = decide


def m_fail_closed_refuses_permitted():
    def decide(request, policy=deputy.FAIL_CLOSED):
        rec = ORIG_DECIDE(request, policy)
        if policy == deputy.FAIL_CLOSED and rec["reason"] == deputy.PERMITTED:
            rec["decision"] = deputy.REFUSE
        return rec
    deputy.decide = decide


def m_unknown_fields_pass():
    def validate(request):
        if isinstance(request, dict):
            request = {k: v for k, v in request.items()
                       if k in deputy.REQUIRED_FIELDS or k in deputy.OPTIONAL_FIELDS}
        return ORIG_VALIDATE(request)
    deputy.validate = validate


def m_missing_on_expiry_passes():
    def validate(request):
        if isinstance(request, dict) and isinstance(request.get("wait"), dict):
            w = dict(request["wait"])
            w.setdefault("on_expiry", deputy.REFUSE)
            request = dict(request, wait=w)
        return ORIG_VALIDATE(request)
    deputy.validate = validate


def m_classify_granted_partial_as_permitted():
    def classify(request):
        if request["permission"] == "granted":
            return deputy.PERMITTED
        return ORIG_CLASSIFY(request)
    deputy.classify = classify


def m_k2_expiry_after_permitted():
    # K2: expiry checked only after the permitted dispatch.
    def decide(request, policy=deputy.FAIL_CLOSED):
        rec = ORIG_DECIDE(request, policy)
        if rec["reason"] == deputy.EXPIRED and rec["case"] == deputy.PERMITTED:
            rec["decision"] = deputy.DISPATCH
            rec["reason"] = deputy.PERMITTED
            rec["prior_reason"] = None
        return rec
    deputy.decide = decide


# ---- source-text mutants (one per fix in this round) --------------------

S_ISINSTANCE_STR = source_mutant(
    ("    return type(value) is str\n", "    return isinstance(value, str)\n"))
S_ISINSTANCE_DICT = source_mutant(
    ("    return type(value) is dict\n", "    return isinstance(value, dict)\n"))
S_CANONICAL_NO_TYPE = source_mutant(
    ("    if not _is_str(value):\n        return None\n    for choice", "    for choice"))
S_POLICY_BY_EQUALITY = source_mutant(
    ("    canon = _canonical(policy, POLICIES)\n    if canon is None:",
     "    canon = next((c for c in POLICIES if policy == c), None)\n    if canon is None:"))
S_RECORD_CALLER_POLICY = source_mutant(
    ("return _record(rid, INVALID_POLICY, None, REFUSE, CONFIG_ERROR)",
     "return _record(rid, policy, None, REFUSE, CONFIG_ERROR)"))
S_EXPIRY_CALLER_DECISION = source_mutant(
    ("_record(rid, canon, case, REFUSE, EXPIRED, case, on_expiry)",
     "_record(rid, canon, case, wait[\"on_expiry\"], EXPIRED, case, on_expiry)"))
S_ON_EXPIRY_CALLER_VALUE = source_mutant(
    ("on_expiry = REFUSE if wait is not None else None",
     "on_expiry = wait[\"on_expiry\"] if wait is not None else None"))
S_ORIGINAL_SPOOF_BREACH = source_mutant(
    ("    return type(value) is str\n", "    return isinstance(value, str)\n"),
    ("_record(rid, canon, case, REFUSE, EXPIRED, case, on_expiry)",
     "_record(rid, canon, case, wait[\"on_expiry\"], EXPIRED, case, on_expiry)"))
S_NO_TRY = source_mutant(
    ("        return _decide(request, policy)\n    except Exception:",
     "        return _decide(request, policy)\n    except ZeroDivisionError:"))
S_EXPIRY_SKIPS_PERMITTED = source_mutant(
    ("    if wait is not None and wait.get(\"expired\", False) is True:",
     "    if case != PERMITTED and wait is not None and wait.get(\"expired\", False) is True:"))
S_EXPIRY_SKIPS_DENY = source_mutant(
    ("    if wait is not None and wait.get(\"expired\", False) is True:",
     "    if case != EXPLICIT_DENY and wait is not None and wait.get(\"expired\", False) is True:"))
S_NO_PRIOR_REASON = source_mutant(
    ("_record(rid, canon, case, REFUSE, EXPIRED, case, on_expiry)",
     "_record(rid, canon, case, REFUSE, EXPIRED, None, on_expiry)"))
S_K3_BASELINE_UNKNOWN_ONLY = source_mutant(
    ("    if canon == OPTIMISTIC_IF_UNKNOWN:",
     "    if canon == OPTIMISTIC_IF_UNKNOWN and request[\"permission\"] == \"unknown\":"))
S_K4_UNKNOWN_WAIT_FIELD = source_mutant(
    ("                return \"unknown wait field\"\n", "                continue\n"))
S_K5_EXPIRED_NOT_CHECKED = source_mutant(
    ("        if \"expired\" in wait and type(wait[\"expired\"]) is not bool:",
     "        if False:"))
S_K6_EMPTY_ACTION = source_mutant(
    ("    if not _is_str(request[\"action\"]) or not request[\"action\"]:",
     "    if not _is_str(request[\"action\"]):"))
S_TIMEOUT_ISINSTANCE = source_mutant(
    ("        if type(timeout) is not int or timeout <= 0:",
     "        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:"))


# r3: a request field read outside a passed validation (before it, or on
# the config_error path). Each must make the suite fail.
S_R3_EARLY_REQUEST_ID_READ = source_mutant(
    ("    rid = None\n    canon = _canonical(policy, POLICIES)\n",
     "    rid = None\n"
     "    if _is_dict(request):\n"
     "        candidate = request.get(\"request_id\")\n"
     "        if _is_str(candidate):\n"
     "            rid = candidate\n"
     "    canon = _canonical(policy, POLICIES)\n"))
S_R3_ECHO_ID_ON_CONFIG_ERROR = source_mutant(
    ("        return _record(rid, canon, None, REFUSE, CONFIG_ERROR)",
     "        return _record(request.get(\"request_id\") if _is_dict(request) else None,\n"
     "                       canon, None, REFUSE, CONFIG_ERROR)"))


# ---- world / fixture mutants -------------------------------------------

def w_mislabel_one_case():
    def build():
        out = ORIG_BUILD()
        req, _ = out[20]  # a denied case
        out[20] = (req, "missing_evidence")
        return out
    cases.build_cases = build


def w_drop_missing_evidence_cases():
    def build():
        return [p for p in ORIG_BUILD() if p[1] != "missing_evidence"]
    cases.build_cases = build


def w_partial_evidence_presented_as_complete():
    def build():
        out = []
        for req, exp in ORIG_BUILD():
            if req["evidence"] == "partial":
                req = dict(req, evidence="complete")
            out.append((req, exp))
        return out
    cases.build_cases = build


def w_nondeterministic_ids():
    counter = [0]

    def build():
        counter[0] += 1
        return [(dict(r, request_id="%s-%d" % (r["request_id"], counter[0])), e)
                for r, e in ORIG_BUILD()]
    cases.build_cases = build


def w_duplicate_ids():
    def build():
        return [(dict(r, request_id="dup"), e) for r, e in ORIG_BUILD()]
    cases.build_cases = build


MUTANTS = [
    ("code", "collapse missing_evidence into explicit_deny", m_collapse_missing_into_deny),
    ("code", "fail_closed dispatches on unknown", m_fail_closed_dispatches_unknown),
    ("code", "optimistic refuses missing evidence (no baseline gap)", m_optimistic_refuses_missing),
    ("code", "optimistic dispatches explicit deny", m_optimistic_dispatches_deny),
    ("code", "fail_closed refuses permitted", m_fail_closed_refuses_permitted),
    ("code", "unknown fields pass validation", m_unknown_fields_pass),
    ("code", "timeout without on_expiry passes", m_missing_on_expiry_passes),
    ("code", "granted with partial evidence classified permitted", m_classify_granted_partial_as_permitted),
    ("code", "K2 expiry checked after permitted dispatch", m_k2_expiry_after_permitted),
    ("code", "F1 isinstance(str) instead of exact type", S_ISINSTANCE_STR),
    ("code", "F2 isinstance(dict) instead of exact type", S_ISINSTANCE_DICT),
    ("code", "F2 canonical match without type check", S_CANONICAL_NO_TYPE),
    ("code", "F2 policy matched by equality only", S_POLICY_BY_EQUALITY),
    ("code", "F2 record echoes caller policy", S_RECORD_CALLER_POLICY),
    ("code", "F1 expiry returns caller on_expiry", S_EXPIRY_CALLER_DECISION),
    ("code", "F1 record echoes caller on_expiry", S_ON_EXPIRY_CALLER_VALUE),
    ("code", "F1 original breach (isinstance + echo)", S_ORIGINAL_SPOOF_BREACH),
    ("code", "F3 decide without try/except", S_NO_TRY),
    ("code", "K2 expiry skipped on permitted", S_EXPIRY_SKIPS_PERMITTED),
    ("code", "K2 expiry skipped on explicit deny", S_EXPIRY_SKIPS_DENY),
    ("code", "F1 expiry drops prior_reason", S_NO_PRIOR_REASON),
    ("code", "K3 baseline dispatches on unknown only", S_K3_BASELINE_UNKNOWN_ONLY),
    ("code", "K4 unknown wait field accepted", S_K4_UNKNOWN_WAIT_FIELD),
    ("code", "K5 non-bool expired accepted", S_K5_EXPIRED_NOT_CHECKED),
    ("code", "K6 empty action accepted", S_K6_EMPTY_ACTION),
    ("code", "F2 timeout int subclass accepted", S_TIMEOUT_ISINSTANCE),
    ("code", "R3 request_id read before validation", S_R3_EARLY_REQUEST_ID_READ),
    ("code", "R3 request_id echoed on config_error", S_R3_ECHO_ID_ON_CONFIG_ERROR),
    ("world", "one case mislabelled", w_mislabel_one_case),
    ("world", "missing-evidence cases dropped", w_drop_missing_evidence_cases),
    ("world", "partial evidence presented as complete", w_partial_evidence_presented_as_complete),
    ("world", "case ids change between runs", w_nondeterministic_ids),
    ("world", "duplicate case ids", w_duplicate_ids),
]


def restore():
    for name in [n for n in vars(deputy) if n not in DEPUTY_SNAPSHOT]:
        delattr(deputy, name)
    deputy.__dict__.update(DEPUTY_SNAPSHOT)
    deputy.decide = ORIG_DECIDE
    deputy.validate = ORIG_VALIDATE
    deputy.classify = ORIG_CLASSIFY
    cases.build_cases = ORIG_BUILD


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_deputy)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


def main():
    restore()
    ran, bad = run_suite()
    print("clean suite: %d tests, %d failing" % (ran, bad))
    clean_ok = bad == 0
    killed = 0
    for kind, name, apply in MUTANTS:
        try:
            apply()
            ran, bad = run_suite()
        except Exception as exc:
            restore()
            print("%-5s %-52s BROKEN   (%s)" % (kind, name, type(exc).__name__))
            continue
        finally:
            restore()
        status = "KILLED" if bad else "SURVIVED"
        killed += 1 if bad else 0
        print("%-5s %-52s %-8s (%d/%d tests failing)" % (kind, name, status, bad, ran))
    ran, bad = run_suite()
    print("clean suite after restore: %d tests, %d failing" % (ran, bad))
    clean_ok = clean_ok and bad == 0
    total = len(MUTANTS)
    code_total = sum(1 for k, _, _ in MUTANTS if k == "code")
    print("killed %d/%d (code %d, world %d)" % (killed, total, code_total, total - code_total))
    return 0 if clean_ok and killed == total else 1


if __name__ == "__main__":
    sys.exit(main())
