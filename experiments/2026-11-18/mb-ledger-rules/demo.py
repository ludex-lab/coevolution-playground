"""Deterministic demo for mb-ledger-rules (stdlib only). Run: python3 -B demo.py"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ledger  # noqa: E402


def main():
    try:
        fx = ledger.load(os.path.join(HERE, "fixtures", "main.json"))
        rows = ledger.run(fx)
    except ledger.Deny as exc:
        sys.stderr.write("DENY %s: %s\n" % (exc.code, exc.detail))
        return 2
    print("mb-ledger-rules demo: 8 probes, 1 describe-only deletion (day 8), synthetic fixture")
    for line in ledger.report(fx):
        print(line)
    s = ledger.summary(fx, rows)
    after = [r for r in rows if r["deleted"]]
    a = all(r["ledger"]["facts"][0]["value"] == "3.11" for r in rows if r["probe"]["id"] in ("p1", "p6"))
    b = all(not ledger.leaks(r["ledger"], r["deleted"]) for r in after)
    c = s["replay_deleted_leaks"] >= 1 or s["replay_stale_leaks"] >= 1
    print("done-when (a) %s: in-period high-trust value 3.11 chosen over stale 3.8 and low-trust 3.9" % ("PASS" if a else "FAIL"))
    print("done-when (b) %s: deleted value absent from all %d post-deletion ledger bundles" % ("PASS" if b else "FAIL", len(after)))
    print("done-when (c) %s: full replay carries a deleted or stale value" % ("PASS" if c else "FAIL"))
    print("no model, no network, no paper accuracy claimed; sketch counts are not comparable with the paper")
    return 0 if (a and b and c) else 1


if __name__ == "__main__":
    sys.exit(main())
