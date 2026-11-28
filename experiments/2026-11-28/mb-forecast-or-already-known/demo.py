"""Deterministic demo: run fixtures/main.json and print the gate table."""

import os
import sys

import forecast_gate

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "fixtures", "main.json")


def main():
    res = forecast_gate.run(forecast_gate.load(MAIN))
    sys.stdout.write(forecast_gate.report(res))
    return 0 if res["gate"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
