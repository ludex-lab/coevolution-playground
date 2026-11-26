"""Demo: run both arms on the synthetic fixture and print the report. Planted faults; a mechanism demo only."""

import os
import sys

import voucher

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    print("Synthetic fixture with planted faults: shows the mechanism, not evidence of any rate.\n")
    sys.stdout.flush()
    sys.exit(voucher.main(["voucher.py", os.path.join(HERE, "fixtures", "main.json")]))
