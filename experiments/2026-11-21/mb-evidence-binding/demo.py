"""Demo: the loose test and the strict test on every planted answer. Run: python3 -B demo.py

The whole transcript below is produced by this code from fixtures/main.json; none of it is written by hand.
"""

import os
import sys

import evidence_binding as eb

HERE = os.path.dirname(os.path.abspath(__file__))


def verdict(v):
    return "PASS" if v["pass"] else "FAIL %s" % v["reason"]


def main():
    fx = eb.load_fixture(os.path.join(HERE, "fixtures", "main.json"))
    result = eb.run(fx)
    out = []
    out.append("evidence binding demo (fixtures/main.json)")
    out.append("transcript produced by this code from the fixture, not written by hand")
    out.append("synthetic filing; the planted answers are fixture-authored; no model is called; no network")
    out.append("")
    out.append("FILING: %s, %s" % (fx["filing"]["company"], fx["filing"]["form"]))
    for tid in sorted(fx["tables"], key=lambda t: fx["tables"][t]["page"]):
        t = fx["tables"][tid]
        out.append("  p.%d %s %s: %s" % (t["page"], t["title"], t["scale_note"],
                                        ", ".join(fx["lines"][line] for line in t["cells"])))
    by_q = {}
    for row in result["answers"]:
        by_q.setdefault(row["question"], []).append(row)
    for qid, q in fx["questions"].items():
        out.append("")
        key = eb.answer_key(fx, q).pop()
        out.append("QUESTION %s: %s" % (qid, q["text"]))
        out.append("  asks line=%s period=%s unit=%s; exact key %d/%d" % (q["line"], q["period"], q["unit"],
                                                                         key.numerator, key.denominator))
        for row in sorted(by_q[qid], key=lambda r: eb.PLANTS.index(r["planted"])):
            answer = [a for a in fx["answers"] if a["id"] == row["id"]][0]
            cite = answer["citations"][0]
            out.append("  %-12s reports %-12s cites p.%d %-24s loose %-26s strict %s" % (
                row["planted"], row["value"], cite["page"], cite["quote"], verdict(row["loose"]), verdict(row["strict"])))
    s = result["summary"]
    out.append("")
    out.append("SUMMARY: %d answers over %d questions; %d carry a wrong value" % (s["answers"], s["questions"], s["wrong_values"]))
    out.append("  loose test passes %d of %d; wrong values passing the loose test: %s"
               % (s["loose_passes"], s["answers"], s["loose_false_pass_rate"]))
    out.append("  strict test passes %d of %d; wrong values passing the strict test: %s; right values passing: %s"
               % (s["strict_passes"], s["answers"], s["strict_false_pass_rate"], s["strict_true_pass_rate"]))
    out.append("  strict reasons: " + ", ".join("%s=%d" % kv for kv in sorted(s["strict_reason_counts"].items())))
    out.append("")
    for name, check in sorted(result["checks"].items()):
        out.append("CHECK %s: %s" % (name, "holds" if check["holds"] else "fails"))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
