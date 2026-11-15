"""Synthetic fixtures for the w18-phantom-consensus method sketch.

Run: python3 fixtures.py
Four hand-written episodes, four agents each (naru, cody, mina, oto),
labels accept / decline / defer. Every private judgment and every recorded
majority is typed in here; nothing is produced by a model or a function.
"""

import dataclasses

import phantom as P


def _ep(episode_id, privates, rows, signal_kind):
    reports = tuple(
        P.Report(reporter=who, reported_group_estimate=est,
                 recorded_private_majority=rec, public_decision=pub,
                 signal_kind=signal_kind, estimate_after_reveal=after)
        for who, est, rec, pub, after in rows)
    return P.Episode(episode_id, tuple(privates), reports)


def build_episodes():
    # Shed roof: three of four privately accept the repair plan. An ambiguous
    # public comment hints at doubt. Naru and Mina report that the others
    # privately decline; the record says the others' majority is accept.
    roof = _ep(
        "shed-roof",
        [("naru", "accept"), ("cody", "accept"), ("mina", "accept"), ("oto", "decline")],
        [  # reporter, reported estimate, recorded majority of others, public, after reveal
            ("naru", "decline", "accept", "decline", "accept"),
            ("cody", "accept", "accept", "accept", None),
            ("mina", "decline", "accept", "decline", None),
            ("oto", "accept", "accept", "accept", None),
        ],
        "ambiguous")

    # Seed order: split record. For naru and cody the other three disagree
    # three ways, so there is no recorded majority and the row is held.
    # Mina's public decision equals her own private judgment, yet her report
    # of the others is wrong. Oto's public decision departs from the record,
    # yet his report of the others is right.
    seed = _ep(
        "seed-order",
        [("naru", "decline"), ("cody", "decline"), ("mina", "accept"), ("oto", "defer")],
        [
            ("naru", "accept", None, "accept", None),
            ("cody", "decline", None, "decline", None),
            ("mina", "accept", "decline", "accept", None),
            ("oto", "decline", "decline", "accept", None),
        ],
        "intentional")

    # Well pump: everyone privately accepts, no public signal, every report
    # matches the record.
    pump = _ep(
        "well-pump",
        [("naru", "accept"), ("cody", "accept"), ("mina", "accept"), ("oto", "accept")],
        [(who, "accept", "accept", "accept", None) for who in ("naru", "cody", "mina", "oto")],
        "none")

    # Public-only twin of the shed roof: every public decision is changed,
    # every reported estimate and recorded majority is kept.
    twin = dataclasses.replace(
        roof, episode_id="shed-roof-public-twin",
        reports=tuple(dataclasses.replace(r, public_decision="defer") for r in roof.reports))

    return [roof, seed, pump, twin]


def _errors(ep):
    return [r.reporter for r in ep.reports if P.detect(r) is True]


def run_checks():
    eps = {ep.episode_id: ep for ep in build_episodes()}
    roof, seed, pump, twin = (eps["shed-roof"], eps["seed-order"],
                              eps["well-pump"], eps["shed-roof-public-twin"])
    checks = [
        ("bookkeeping: every recorded majority matches the recorded privates",
         all(P.compare(ep) == [] for ep in eps.values())),
        ("shed-roof: naru and mina misreport the others' private majority",
         _errors(roof) == ["naru", "mina"]),
        ("seed-order: no recorded majority for naru and cody, rows held",
         [r.reporter for r in seed.reports if P.hold(r)] == ["naru", "cody"]),
        ("seed-order: mina's public matches her private, belief_error still True",
         _errors(seed) == ["mina"]),
        ("seed-order: oto's public departs from the record, belief_error False",
         P.detect(seed.reports[3]) is False),
        ("well-pump: no belief error",
         _errors(pump) == []),
        ("public-only twin: every public decision changed, same belief_error per row",
         [P.detect(r) for r in twin.reports] == [P.detect(r) for r in roof.reports]
         and all(a.public_decision != b.public_decision
                 for a, b in zip(twin.reports, roof.reports))),
    ]
    return checks


def main():
    eps = build_episodes()
    checks = run_checks()
    for name, ok in checks:
        print("%s  %s" % ("PASS" if ok else "FAIL", name))
    summary = P.report(eps)
    print("summary: " + ", ".join("%s=%s" % (k, summary[k]) for k in summary))
    print("flagged: " + ", ".join("%s/%s" % pair for pair in P.flag(eps)))
    passed = sum(1 for _, ok in checks if ok)
    print("fixtures: %d/%d passed" % (passed, len(checks)))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
