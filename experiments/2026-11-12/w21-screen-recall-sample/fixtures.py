"""Synthetic fixtures for the screen-recall-sample sketch.

40 items d00..d39. A fixture-declared truth table says which are relevant
(12 of them). The screening stage forwards 12 items, 8 of them relevant, so
4 relevant items are missed among the 28 not forwarded. The truth table is
used only to label fixture judgments (the assessor stand-in); screen_recall
never reads it.

Screener reports: three screeners that all passed exactly the forwarded
list (full agreement), so agreement says nothing about the 4 misses.

Run: python3 fixtures.py   (prints the report for each fixture request)
"""

import json

import screen_recall as S

ITEMS = ["d%02d" % i for i in range(40)]
RELEVANT_TRUTH = frozenset(["d01", "d03", "d05", "d08", "d11", "d14", "d17",
                            "d20", "d23", "d27", "d31", "d36"])
FORWARDED = ["d01", "d02", "d03", "d05", "d07", "d08", "d11", "d14", "d17",
             "d20", "d25", "d33"]
SEED = 2611
SAMPLE_SIZE = 14


def label(item):
    return S.RELEVANT if item in RELEVANT_TRUTH else S.NOT_RELEVANT


def not_passed():
    fwd = set(FORWARDED)
    return [i for i in ITEMS if i not in fwd]


def screener_reports(n):
    return [{"screener": "s%d" % k, "passed": list(FORWARDED)} for k in range(n)]


def sample(size=SAMPLE_SIZE, seed=SEED):
    drawn = S.draw_sample(not_passed(), size, seed)
    return {"seed": seed, "size": size, "items": drawn,
            "judgments": {i: label(i) for i in drawn}}


def request(n_screeners=3, with_sample=True, **overrides):
    req = {"items": list(ITEMS), "forwarded": list(FORWARDED),
           "screener_reports": screener_reports(n_screeners),
           "assessed_passes": {i: label(i) for i in FORWARDED}}
    if with_sample:
        req["not_passed_sample"] = sample()
    req.update(overrides)
    return req


def true_recall():
    """Ground truth for the fixture only; never available to report()."""
    found = sum(1 for i in FORWARDED if i in RELEVANT_TRUTH)
    return found, len(RELEVANT_TRUTH)


def main():
    for name, req in (("passes only, 3 agreeing screeners", request(with_sample=False)),
                      ("passes only, 9 agreeing screeners", request(9, with_sample=False)),
                      ("passes + seeded not-passed sample", request())):
        rec = S.report(req)
        print(json.dumps({"case": name, "status": rec["status"],
                          "precision": rec["precision"]["exact"],
                          "recall_lower_bound": rec["recall_lower_bound"]["exact"],
                          "recall": [rec["recall"]["status"], rec["recall"]["exact"]]},
                         sort_keys=True))


if __name__ == "__main__":
    main()
