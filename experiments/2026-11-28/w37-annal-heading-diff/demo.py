"""Deterministic demo: diff fixtures/valid/before against fixtures/valid/after.

Prints changes.md to stdout. Pass --json for the JSON form.
"""

import os
import sys

import annal_diff

HERE = os.path.dirname(os.path.abspath(__file__))
VALID = os.path.join(HERE, "fixtures", "valid")


def demo_argv(extra=()):
    return ["--before", os.path.join(VALID, "before"),
            "--after", os.path.join(VALID, "after"),
            "--pins", os.path.join(VALID, "pins.txt")] + list(extra)


if __name__ == "__main__":
    sys.exit(annal_diff.main(demo_argv(sys.argv[1:])))
