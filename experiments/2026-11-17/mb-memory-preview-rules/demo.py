"""Deterministic demo: python3 -B demo.py  (prints the fixture report and the done-when checks)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import preview_rules as pr  # noqa: E402


def main():
    fx = pr.load_fixture(os.path.join(HERE, "fixtures", "memory_rules.json"))
    for line in pr.report(fx):
        print(line)
    weak = pr.compatible(fx, "u1", "u5")
    transfer = pr.compatible(fx, "u2", "u3")
    print("done-when a: %d intended pairs enumerated; the tests compare each with a hand-listed table"
          % len(pr.all_pairs(fx)[0]))
    print("done-when b: weak preview fits %d rules, verdict %s" % (len(weak), pr.verdict(weak, fx["intended"])))
    print("done-when c: transfer preview leaves %d scope(s) where the weak preview leaves %d"
          % (len(pr.scopes_of(transfer)), len(pr.scopes_of(weak))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
