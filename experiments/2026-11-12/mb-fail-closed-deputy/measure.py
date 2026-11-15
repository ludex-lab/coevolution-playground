"""Measure unsafe dispatch per policy on the synthetic case set.

Unsafe dispatch = a "dispatch" decision on a case whose expected label is
explicit_deny or missing_evidence. The gap is the missing_evidence rate
minus the explicit_deny rate, in percentage points, on this set only.

Prints a compact table, then one JSON line. Writes no files.
"""

import json

import cases
import deputy

CLASSES = ("permitted", "explicit_deny", "missing_evidence")


def measure():
    pairs = cases.build_cases()
    result = {"n_cases": len(pairs), "policies": {}}
    for policy in deputy.POLICIES:
        counts = {c: {"n": 0, "dispatched": 0} for c in CLASSES}
        reasons = {}
        for request, expected in pairs:
            rec = deputy.decide(request, policy)
            counts[expected]["n"] += 1
            if rec["decision"] == deputy.DISPATCH:
                counts[expected]["dispatched"] += 1
            reasons[rec["reason"]] = reasons.get(rec["reason"], 0) + 1

        def rate(c):
            n = counts[c]["n"]
            return round(100.0 * counts[c]["dispatched"] / n, 1) if n else None

        miss = rate("missing_evidence")
        deny = rate("explicit_deny")
        gap = round(miss - deny, 1) if miss is not None and deny is not None else None
        result["policies"][policy] = {
            "counts": counts,
            "reasons": dict(sorted(reasons.items())),
            "permitted_dispatch_pct": rate("permitted"),
            "unsafe_dispatch_pct_missing_evidence": miss,
            "unsafe_dispatch_pct_explicit_deny": deny,
            "gap_pp": gap,
        }
    return result


def table(result):
    lines = [
        "%-22s %10s %12s %12s %8s" % ("policy", "permitted%", "missing_ev%", "expl_deny%", "gap_pp"),
    ]
    for policy, row in result["policies"].items():
        lines.append(
            "%-22s %10.1f %12.1f %12.1f %8.1f %c"
            % (
                policy,
                row["permitted_dispatch_pct"],
                row["unsafe_dispatch_pct_missing_evidence"],
                row["unsafe_dispatch_pct_explicit_deny"],
                row["gap_pp"],
            )
        )
    lines.append("n_cases=%d (synthetic set only)" % result["n_cases"])
    return "\n".join(lines)


def main():
    result = measure()
    print(table(result))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
