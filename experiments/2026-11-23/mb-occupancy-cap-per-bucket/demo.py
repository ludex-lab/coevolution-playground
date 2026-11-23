"""Deterministic demo: the occupancy report on the synthetic village fixtures.

Run: python3 -B demo.py   (prints the same bytes every run; compare with sha256sum)
Part 1 is fixtures/village.json (festival burst, quiet market, busy council; expected 'closed: 3 / 3').
Part 2 is fixtures/more.json (two bursts, equal scores, Korean text).
"""

import os
import sys

import occupancy_cap as oc

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parts = []
    for name in ("village.json", "more.json"):
        parts.append(oc.report(oc.run(oc.load_fixture(os.path.join(HERE, "fixtures", name)))))
    sys.stdout.write("\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
