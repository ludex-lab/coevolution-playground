"""Deterministic demo: check the demo draft listing and print the report."""

import os
import sys

import issue_index

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_FIXTURE = os.path.join(HERE, "demo", "issues.tsv")


def render():
    return issue_index.format_text(issue_index.run([DEMO_FIXTURE]))


def main():
    sys.stdout.buffer.write(render().encode("utf-8"))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
