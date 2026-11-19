"""Demo: run both arms on the frozen fixture and print the log. Run: python3 -B demo.py"""

import os

import region

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    fx = region.load_fixture(os.path.join(HERE, "fixtures", "main.json"))
    print("certified-region delta demo (fixtures/main.json)")
    print("method sketch only; synthetic numbers; not a reproduction of the paper")
    print()
    print(region.report(fx), end="")
    print()
    print("what each response does")
    for name in region.RESPONSES:
        e = region.EFFECTS[name]
        print("  %-22s authority=%-9s power=%-3s recertify=%s"
              % (name, e["authority"], e["power"], "yes" if e["recertify"] else "no"))
    rows = region.run_a(fx)
    print()
    print("arm A first row per response")
    for name in region.RESPONSES:
        first = next(r for r in rows if r["response"] == name)
        print("  %-22s %s (%s)" % (name, first["id"], first["reason"]))


if __name__ == "__main__":
    main()
