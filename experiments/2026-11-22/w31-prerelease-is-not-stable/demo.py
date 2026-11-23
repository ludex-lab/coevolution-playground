"""Deterministic demo: the gate report on the fixture-authored pairs.

Run: python3 -B demo.py   (prints the same bytes every run; compare with sha256sum)
Part 1 is fixtures/main.json (the stable range >= 1.0.0; expected 'closed: 5 / 5 on the declared comparator').
Part 2 is fixtures/more.json (equality, higher-core pre-releases and build metadata).
"""

import os
import sys

import prerelease_gate as pg

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parts = []
    for name in ("main.json", "more.json"):
        parts.append(pg.report(pg.run(pg.load_fixture(os.path.join(HERE, "fixtures", name)))))
    sys.stdout.write("\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
