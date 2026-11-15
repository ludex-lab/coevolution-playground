"""Fixtures runner for the step-record sketch. SYNTHETIC toy data only.

Each fixture injects one silent fault on the wire and states what the step
record compare and the outcome (gain) baseline are expected to report.
F1-F6 are single-value faults in env 1, episode 8; F7 changes every reward.
Run: python3 fixtures.py
"""

import math

import ledger
from ledger import Fault

N_ENVS = 2
N_EPISODES = 10

# expect_where: (env_id, episode_id, step_id, field) of the first difference.
FIXTURES = [
    {"id": "F0-clean", "fault": None,
     "expect_ledger": "agree", "expect_where": None, "expect_baseline": "pass"},
    {"id": "F1-float16-observation", "fault": Fault("float16_obs", 1, 8, 3),
     "expect_ledger": "detect", "expect_where": (1, 8, 3, "observation"),
     "expect_baseline": "pass"},
    {"id": "F2-float16-reward", "fault": Fault("float16_reward", 1, 8, 4),
     "expect_ledger": "detect", "expect_where": (1, 8, 4, "reward"),
     "expect_baseline": "pass"},
    {"id": "F3-stale-reward", "fault": Fault("stale_reward", 1, 8, 5),
     "expect_ledger": "detect", "expect_where": (1, 8, 5, "reward"),
     "expect_baseline": "pass"},
    {"id": "F4-terminated-truncated-swap", "fault": Fault("swap_end", 1, 8, None),
     # episode 8 of env 1 ends by termination at step 11 in the clean run
     "expect_ledger": "detect", "expect_where": (1, 8, 11, "terminated"),
     "expect_baseline": "pass"},
    {"id": "F5-skipped-step-filled-in", "fault": Fault("skip_step", 1, 8, 6),
     "expect_ledger": "detect", "expect_where": (1, 8, 6, "step_id"),
     "expect_baseline": "pass"},
    {"id": "F6-zeroed-action", "fault": Fault("zero_action", 1, 8, 7),
     "expect_ledger": "detect", "expect_where": (1, 8, 7, "action"),
     "expect_baseline": "pass"},
    {"id": "F7-every-reward-zeroed", "fault": Fault("zero_reward", None, None, None),
     "expect_ledger": "detect", "expect_where": (0, 0, 1, "reward"),
     "expect_baseline": "detect"},
]

REQUIRED_FAULT_IDS = ("F1-float16-observation", "F3-stale-reward",
                      "F4-terminated-truncated-swap", "F5-skipped-step-filled-in")


def run_fixture(fx):
    faults = [fx["fault"]] if fx["fault"] is not None else []
    res = ledger.run(N_ENVS, N_EPISODES, faults)
    status, diff = ledger.detect(res)
    b_status, g = ledger.gain_check(res.curve)
    where = None if diff is None else (diff.env_id, diff.episode_id,
                                       diff.step_id, diff.field)
    return {"id": fx["id"], "ledger": status, "diff": diff, "where": where,
            "baseline": b_status, "gain": g}


def run_all():
    return [run_fixture(fx) for fx in FIXTURES]


def summary(results=None, repeats=20):
    results = run_all() if results is None else results
    faulted = [r for r in results if r["id"] != "F0-clean"]
    base_s, led_s, ratio = ledger.measure_overhead(repeats, N_ENVS, N_EPISODES)
    return {
        "faults": len(faulted),
        "ledger_detected": sum(r["ledger"] == "detect" for r in faulted),
        "baseline_detected": sum(r["baseline"] == "detect" for r in faulted),
        "localised": sum(r["where"] == fx["expect_where"]
                         for r, fx in zip(results, FIXTURES)
                         if fx["fault"] is not None),
        "baseline_seconds": base_s,
        "ledger_seconds": led_s,
        "overhead_ratio": ratio,
    }


def main():
    results = run_all()
    print("Step-record sketch fixtures (SYNTHETIC toy; not paper results)")
    print("gain threshold %.2f over a %d-episode window" %
          (ledger.GAIN_THRESHOLD, ledger.GAIN_WINDOW))
    ok = True
    for r, fx in zip(results, FIXTURES):
        match = (r["ledger"] == fx["expect_ledger"]
                 and r["where"] == fx["expect_where"]
                 and r["baseline"] == fx["expect_baseline"])
        ok = ok and match
        d = r["diff"]
        loc = "-" if d is None else "env=%d episode=%d step=%d field=%s env=%r trainer=%r" % (
            d.env_id, d.episode_id, d.step_id, d.field, d.env_value, d.trainer_value)
        print("%-30s ledger=%-6s baseline=%-6s gain=%+.4f %s %s" % (
            r["id"], r["ledger"], r["baseline"], r["gain"], loc,
            "OK" if match else "MISMATCH"))
    s = summary(results)
    print("ledger detection:   %d/%d" % (s["ledger_detected"], s["faults"]))
    print("baseline detection: %d/%d" % (s["baseline_detected"], s["faults"]))
    print("first-difference localisation matched: %d/%d" % (s["localised"], s["faults"]))
    print("overhead: baseline-only %.4fs, records+compare %.4fs, ratio %.2fx" % (
        s["baseline_seconds"], s["ledger_seconds"], s["overhead_ratio"]))
    ok = ok and math.isfinite(s["overhead_ratio"]) and s["overhead_ratio"] > 0
    print("all fixtures match expectations" if ok else "FIXTURE MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
