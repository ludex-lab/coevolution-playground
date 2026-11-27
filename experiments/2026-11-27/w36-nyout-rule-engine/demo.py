"""Deterministic demo: run fixtures/main.json and print the gate table."""

import os
import sys

import nyout

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "fixtures", "main.json")


def main():
    fx = nyout.load(MAIN)
    res = nyout.run(fx)
    sys.stdout.write(res["report"])
    return 0 if res["gate"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
