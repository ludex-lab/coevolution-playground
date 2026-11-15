"""Entirely synthetic, fixed train/test split; no trace collection."""
from dataclasses import asdict
import json
from miner import Trace, emit_signatures, evaluate, filter_traces

K = 3
CONFIGURATIONS = ("Full", "Exclude-errors", "Variant C")
PRIMARY_CONFIGURATION = "Exclude-errors"
MIN_SUPPORT = 2
MIN_PRECISION = 0.75
TRAIN = (
    Trace("train-f1", ("click", "click", "nav", "scroll"), "failure"),
    Trace("train-f2", ("click", "click", "nav", "type"), "failure"),
    Trace("train-s1", ("type", "nav", "scroll"), "success"),
    Trace("train-s2", ("type", "nav", "scroll", "click"), "success"),
)
TEST = (
    Trace("test-f-hit", ("click", "click", "nav", "type"), "failure"),
    Trace("test-f-miss", ("type", "scroll", "nav"), "failure"),
    Trace("test-timeout-hit", ("click", "click", "nav", "scroll"), "timeout"),
    Trace("test-false-positive", ("click", "click", "nav", "type"), "success"),
    Trace("test-s-miss", ("type", "nav", "scroll"), "success"),
    Trace("test-zero-step-crash", (), "error"),
    Trace("test-trivial-success", ("click",), "success"),
)
# Hand counts: evaluated, matched, TP, FP, FN. Never tuned to paper results.
HAND_COUNTS = {
    "Full": (7, 3, 2, 1, 2),
    "Exclude-errors": (5, 3, 2, 1, 1),
    "Variant C": (4, 2, 1, 1, 1),
}


def library():
    return emit_signatures(filter_traces(TRAIN, PRIMARY_CONFIGURATION), K,
                           MIN_SUPPORT, MIN_PRECISION)


def main():
    signatures = library()
    print("SYNTHETIC fixed split; K=3; min_support=2; min_precision=0.75")
    for s in signatures:
        print("SYNTHETIC signature:", " -> ".join(s.pattern.tokens),
              "support=", s.pattern.support, "training failure precision=", s.precision)
    for config in CONFIGURATIONS:
        metrics = evaluate(filter_traces(TEST, config), signatures, K)
        print("SYNTHETIC", config, json.dumps(asdict(metrics), sort_keys=True))
    print("SYNTHETIC test-false-positive: stopped incorrectly; counted as FP")
    print("UNMATCHED and TIMEOUT are not success; decisions only stop and report.")


if __name__ == "__main__":
    main()
