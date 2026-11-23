"""Deterministic demo: the scoreboard and the clause audit on the fixture-authored toy FIFO.

Run: python3 -B demo.py   (prints the same bytes every run; compare with sha256sum)
"""

import os
import sys

import spec_review as sr

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    fx = sr.load_fixture(os.path.join(HERE, "fixtures", "main.json"))
    result = sr.run(fx)
    out = ["mb-verify-the-verifier demo (fixture-authored toy FIFO, depth %d; no model call)" % fx["depth"], "",
           "Spec clauses:"]
    for rule in sr.RULES:
        out.append("  %s %-9s %s" % (fx["spec"][rule]["id"], rule, fx["spec"][rule]["text"]))
    out += ["", "%-24s %-9s %-15s %-12s %-10s %s" % ("case", "planted", "scoreboard", "clause_audit", "outcome",
                                                     "reasons (clause:code@first_step x count)")]
    for r in result["rows"]:
        sb = r["scoreboard"]
        sb_text = sb["verdict"] if sb["verdict"] == "PASS" else "FAIL:%s@%d" % (sb["field"], sb["step"])
        reasons = ", ".join("%s:%s@%d x%d" % (x["clause"], x["code"], x["first_step"], x["count"])
                            for x in r["clause_audit"]["reasons"]) or "-"
        out.append("%-24s %-9s %-15s %-12s %-10s %s" % (r["id"], r["planted"], sb_text, r["clause_audit"]["verdict"],
                                                       r["outcome"], reasons))
    out += ["", "Summary (planted counts, not model or real-world rates):"]
    out += ["  %s: %s" % (k, result["summary"][k]) for k in sorted(result["summary"])]
    out += ["", "Done-when:"]
    out += ["  %s: %s" % (k, result["checks"][k]) for k in sorted(result["checks"])]
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
