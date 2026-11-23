"""Deterministic demo on the hand-made fixtures that mirror the E1 and E2 record covers.

Run: python3 -B demo.py   (prints the same bytes every run; compare with sha256sum)
Expected: E1 4 missing, E2 2 missing, each absent and matching ignore pattern *.jsonl; the E1 brace name expands to
3 files and the CORRECTION range is INFO unparsed_name; E2 without its receipt adds FAIL missing_receipt; the complete
E1 listing passes. Nothing is fetched, hashed, written or restored.
"""

import os
import sys

import record_presence as rp

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")

RUNS = (
    ("E1 against its listing", "e1/cover.md", "e1/listing.txt", "research/physics-e1"),
    ("E2 against its listing", "e2/cover.md", "e2/listing.txt", "research/uptake-e2"),
    ("E2 with the receipt removed from the listing", "e2/cover.md", "e2/listing_no_receipt.txt", "research/uptake-e2"),
    ("E1 against a complete listing", "e1/cover.md", "e1/listing_complete.txt", "research/physics-e1"),
)
NOTES = (
    "note: the E1 analysis script's usage line names e1_screen.jsonl, while the cover names e1_screen_v2.jsonl; "
    "this check uses the cover's name.",
    "note: every miss above is absent from the listing and matches ignore pattern *.jsonl; that explains the gap, "
    "it does not fill it.",
)


def main():
    parts = []
    for label, cover, listing, record_path in RUNS:
        opts = {"cover": os.path.join(FIX, cover), "listing": os.path.join(FIX, listing),
                "ignore": os.path.join(FIX, "ignore_rules.txt"), "record_path": record_path, "receipt_name": None,
                "json": False}
        res = rp.run(opts)
        parts.append("== %s (exit %d)\n\n%s" % (label, 1 if res["result"] == "FAIL" else 0, rp.report(res)))
    sys.stdout.write("\n".join(parts) + "\n" + "\n".join(NOTES) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
