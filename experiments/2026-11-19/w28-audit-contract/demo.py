"""Demo: audit the frozen fixture under four declared execution contracts. Run: python3 -B demo.py"""

import os

import audit_contract as ac

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    fx = ac.load_fixture(os.path.join(HERE, "fixtures", "main.json"))
    result = ac.run(fx)
    print("audit contract demo (fixtures/main.json)")
    print("method sketch only; synthetic records; the verdict flip in a1 is authored into the fixture by construction")
    print("contracts differ only in how the same products are summed: " + ", ".join(ac.CONTRACTS))
    for row in result["rows"]:
        print()
        print("audit %s -> %s" % (row["audit"], row["decision"]))
        print("  weights_text %s (byte-identical under every contract)" % row["weights_text"])
        print("  a single-contract audit would print: " + "  ".join(
            "%s=%s" % (c, row["single_contract_views"][c]) for c in row["contracts"]))
        for t in row["tests"]:
            cells = "  ".join("%s=%s" % (c, t["per_contract"][c]["statistic"]) for c in row["contracts"])
            print("  test %-10s bound %-5s %-19s range %s..%s   %s"
                  % (t["name"], t["bound"], t["outcome"], t["range"]["min"], t["range"]["max"], cells))
        print("  records that change side across contracts: %s"
              % (", ".join(row["differing_records"]) if row["differing_records"] else "none"))
        print("  sampling uncertainty: %s" % row["sampling_uncertainty"])
    print()
    print("totals " + " ".join("%s=%d" % (d, result["totals"][d]) for d in ac.DECISIONS))
    deny = ac.run(ac.load_fixture(os.path.join(HERE, "fixtures", "denied.json")))
    print()
    print("fixtures/denied.json (pre-declaration broken; each row is DENY, none is a pass)")
    for row in deny["rows"]:
        if row["decision"] == "DENY":
            print("  %-34s DENY %s" % (row["audit"], row["code"]))
        else:
            print("  %-34s %s" % (row["audit"], row["decision"]))


if __name__ == "__main__":
    main()
