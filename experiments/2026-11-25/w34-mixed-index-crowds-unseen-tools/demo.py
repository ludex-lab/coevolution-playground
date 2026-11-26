"""Demo: run the router on the planted synthetic fixture and print the report.
The fixture is planted to show the mechanism; it is not evidence of the paper's rate and measures nothing upstream."""

import os
import sys

import crowding

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    print("Planted synthetic fixture: a mechanism demo, not evidence of the phenomenon's size.\n")
    sys.stdout.flush()
    sys.exit(crowding.main(["crowding.py", os.path.join(HERE, "fixtures", "main.json")]))
