"""Deterministic demo for w26-verification-transport. Run: python3 -B demo.py

Prints the matched-pair report, the native-only report and the DENY lines for the three bad
fixtures, then the done-when lines. Same output on every run; its sha256 is pinned in a test.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import transport as tp  # noqa: E402

FIXTURES = ("executions.json", "native_only.json", "bad_mismatched_pair.json",
            "bad_missing_view.json", "bad_expired_view.json")


def section(name):
    path = os.path.join(HERE, "fixtures", name)
    out = ["== fixtures/%s" % name]
    try:
        report = tp.run(path)
    except tp.Deny as exc:
        out.append("DENY %s: %s (exit 2)" % (exc.code, exc.detail))
        return out, None
    out.extend(tp.render(report))
    return out, report


def main():
    lines = ["w26-verification-transport demo (fictional fixtures, fixture verifiers, no model)",
             "on_expiry=%s" % tp.ON_EXPIRY]
    reports = {}
    for name in FIXTURES:
        out, report = section(name)
        lines.extend(out)
        reports[name] = report
    s = reports["executions.json"]["summary"]
    d, g = s["direct"], s["grounded"]
    lines.append("== done-when")
    lines.append("(a) direct: transport_incorrect=%d transport_abstain=%d; grounded: transport_incorrect=%d "
                 "transport_abstain=%d (counted separately)" % (
                     d["transport_incorrect"], d["transport_abstain"], g["transport_incorrect"], g["transport_abstain"]))
    lines.append("(b) full restore recovered %d of %d failures; lossy restore recovered %d of %d" % (
        d["recovered_full"] + g["recovered_full"], d["transport_failures"] + g["transport_failures"],
        d["recovered_lossy"] + g["recovered_lossy"], d["transport_failures"] + g["transport_failures"]))
    lines.append("(c) native-only suite: transport=%s status=%s" % (
        reports["native_only.json"]["result"]["transport"], reports["native_only.json"]["result"]["status"]))
    lines.append("(d) direct has fewer transport failures (%d < %d) but more incorrect verdicts (%d > %d): rank=%s" % (
        d["transport_failures"], g["transport_failures"], d["transport_incorrect"], g["transport_incorrect"],
        tp.rank(d, g)))
    lines.append("(e) mismatched, missing and expired views: DENY exit 2, no verdict")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
