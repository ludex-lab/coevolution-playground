"""Deterministic demo for w27-worker-lead-handoff (stdlib only). Run: python3 -B demo.py"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import handoff  # noqa: E402


def show(name):
    report = handoff.run(handoff.load(os.path.join(HERE, "fixtures", name)))
    print("%s: now=%d, %d docs, on_expiry=%s" % (name, report["now"], report["docs"], report["on_expiry"]))
    for row in report["rows"]:
        print("  %-16s %-15s retrieved=%-5s detected=%-5s %-4s %s%s" % (
            row["case"], row["layout"], str(row["both_retrieved"]).lower(), str(row["lead_detected"]).lower(),
            row["verdict"], row["reason"], " dropped=" + ",".join(row["dropped_claims"]) if row["dropped_claims"] else ""))
    for layout in handoff.LAYOUTS:
        t = report["totals"][layout]
        print("  totals %-15s " % layout + " ".join("%s=%d" % (key, t[key]) for key in sorted(t)))
    return report


def main():
    try:
        main_report = show("main.json")
        expired_report = show("expired.json")
    except handoff.Deny as exc:
        sys.stderr.write("DENY %s: %s\n" % (exc.code, exc.detail))
        return 2
    t = main_report["totals"]
    rows = main_report["rows"]
    split = [r for r in rows if r["layout"] == "delegated_split"]
    same = [r for r in rows if r["layout"] == "delegated_same"]
    a = any(r["both_retrieved"] and r["dropped_claims"] and r["verdict"] == "FAIL" for r in split) and \
        all(r["verdict"] == "FAIL" for r in split if r["dropped_claims"])
    b = any(r["verdict"] == "PASS" and not r["dropped_claims"] for r in same)
    c = all(r["verdict"] == "FAIL" for r in rows if r["both_retrieved"] and not r["lead_detected"]) and \
        sum(x["both_retrieved"] for x in t.values()) > sum(x["lead_detected"] for x in t.values())
    d = {r["reason"] for r in expired_report["rows"] if r["verdict"] == "DENY"} == {"expired_packet", "missing_packet"}
    both = sum(x["both_retrieved"] for x in t.values())
    det = sum(x["lead_detected"] for x in t.values())
    print("done-when (a) %s: delegated_split fails %d of %d, both claims retrieved in every one" % (
        "PASS" if a else "FAIL", sum(1 for r in split if r["verdict"] == "FAIL"), len(split)))
    print("done-when (b) %s: delegated_same lead detects in %d of %d" % ("PASS" if b else "FAIL", t["delegated_same"]["lead_detected"], len(same)))
    print("done-when (c) %s: both retrieved %d of %d, lead detected %d, so retrieval alone is not a pass" % (
        "PASS" if c else "FAIL", both, len(rows), det))
    print("expiry %s: a missing packet and an expired packet both give DENY" % ("PASS" if d else "FAIL"))
    print("no model, no network; sketch counts are not comparable with the paper")
    return 0 if (a and b and c and d) else 1


if __name__ == "__main__":
    sys.exit(main())
