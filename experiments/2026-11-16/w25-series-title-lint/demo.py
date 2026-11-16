"""Deterministic demo: lint the demo sample against the series catalog and print the report."""

import os
import sys

import lint_titles

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_TITLES = os.path.join(HERE, "demo", "titles.tsv")
CATALOG = os.path.join(HERE, "fixtures", "catalog.json")


def render():
    report = lint_titles.run(DEMO_TITLES, CATALOG)
    return lint_titles.format_text(report)


def main():
    text = render()
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
