"""Deterministic demo for w27-ranked-conflict-set (stdlib only). Run: python3 -B demo.py"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import conflict_set  # noqa: E402


def describe(decision):
    if decision["decision"] == "ADOPT":
        return "ADOPT " + decision["value"]
    if decision["decision"] == "ESCALATE":
        return "ESCALATE " + "|".join(decision["values"])
    return decision["decision"] + " " + decision["reason"]


def show(name):
    report = conflict_set.run(conflict_set.load(os.path.join(HERE, "fixtures", name)))
    print("%s: k=%d, %d entries, on_expiry=%s" % (name, report["k"], report["entries"], report["on_expiry"]))
    for row in report["rows"]:
        print("  %-8s %-10s %-34s -> %s" % (row["policy"], row["query"], describe(row["decision"]), row["outcome"]))
    for policy, t in sorted(report["totals"].items()):
        print("  totals %-8s " % policy + " ".join("%s=%d" % (key, t[key]) for key in sorted(t)))
    return report


def main():
    try:
        main_report = show("main.json")
        expired_report = show("expired.json")
    except conflict_set.Deny as exc:
        sys.stderr.write("DENY %s: %s\n" % (exc.code, exc.detail))
        return 2
    t = main_report["totals"]
    a = t["collapse"]["conflict_visible"] == 0 and t["surface"]["conflict_visible"] >= 1
    b = t["collapse"]["poisoned"] >= 1 and t["surface"]["poisoned"] == 0
    c = all(r["k"] == main_report["k"] for r in main_report["rows"])
    d = {r["decision"]["decision"] for r in expired_report["rows"] if r["query"] != "q_fresh"} == {"DENY"}
    print("done-when (a) %s: collapse hides every conflict, surface shows %d" % ("PASS" if a else "FAIL", t["surface"]["conflict_visible"]))
    print("done-when (b) %s: poison adopted by collapse %d, by surface %d" % ("PASS" if b else "FAIL", t["collapse"]["poisoned"], t["surface"]["poisoned"]))
    print("done-when (c) %s: both policies read one snapshot at k=%d" % ("PASS" if c else "FAIL", main_report["k"]))
    print("expiry %s: passed deadline and expired entry both DENY" % ("PASS" if d else "FAIL"))
    print("no model, no network; sketch counts are not comparable with the paper")
    return 0 if (a and b and c and d) else 1


if __name__ == "__main__":
    sys.exit(main())
