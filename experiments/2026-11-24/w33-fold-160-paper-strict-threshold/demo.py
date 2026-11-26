"""Deterministic demo: both arms on the synthetic fixtures, inclusive and paper-strict zero-reference readings.

Run: python3 -B demo.py   (prints the same bytes every run; compare with sha256sum)
"""

import os
import sys

import strict_threshold as st

HERE = os.path.dirname(os.path.abspath(__file__))


def main(out=None):
    out = sys.stdout if out is None else out
    parts = [st.report(st.run(st.load_fixture(os.path.join(HERE, "fixtures", name))))
             for name in ("main.json", "more.json")]
    out.write("\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
