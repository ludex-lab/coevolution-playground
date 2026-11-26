"""Deterministic demo: both arms on the synthetic fixtures.

Run: python3 -B demo.py   (prints the same bytes every run; compare with sha256sum)
Part 1 is fixtures/main.json, the three planted contrasts. Part 2 is fixtures/more.json, the edge cases.
"""

import os
import sys

import zero_reference as zr

HERE = os.path.dirname(os.path.abspath(__file__))


def main(out=None):
    out = sys.stdout if out is None else out
    parts = [zr.report(zr.run(zr.load_fixture(os.path.join(HERE, "fixtures", name))))
             for name in ("main.json", "more.json")]
    out.write("\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
