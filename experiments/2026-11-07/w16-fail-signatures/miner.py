"""Small, exact closed-sequence miner for synthetic traces; Python stdlib only."""
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Trace:
    name: str
    steps: tuple[str, ...]
    outcome: str

    def __post_init__(self):
        object.__setattr__(self, "steps", tuple(self.steps))
        if self.outcome not in {"failure", "success", "timeout", "error"}:
            raise ValueError("unknown outcome")
        if any(not isinstance(s, str) or not s for s in self.steps):
            raise ValueError("step tokens must be nonempty strings")


@dataclass(frozen=True)
class Pattern:
    tokens: tuple[str, ...]
    support: int

    def __post_init__(self):
        object.__setattr__(self, "tokens", tuple(self.tokens))


@dataclass(frozen=True)
class Signature:
    pattern: Pattern
    failure_support: int
    precision: float


class Verdict(Enum):
    STOP_AND_REPORT = "STOP_AND_REPORT"
    UNMATCHED = "UNMATCHED"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class Match:
    signature: Signature
    positions: tuple[int, ...]


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    matches: tuple[Match, ...]
    observed_steps: int


@dataclass(frozen=True)
class Metrics:
    evaluated: int
    matched: int
    tp: int
    fp: int
    fn: int
    coverage: float
    precision: float
    recall: float


def positions(pattern, sequence):
    """Earliest ordered embedding, zero-based; None means no embedding."""
    result = []
    start = 0
    for token in pattern:
        for i in range(start, len(sequence)):
            if sequence[i] == token:
                result.append(i)
                start = i + 1
                break
        else:
            return None
    return tuple(result)


def mine_closed(sequences, min_support=1):
    """Prefix-growth enumeration plus exact global closure check, not BIDE+."""
    if not isinstance(min_support, int) or min_support < 1:
        raise ValueError("min_support must be a positive integer")
    sequences = tuple(tuple(s) for s in sequences)
    alphabet = sorted({t for s in sequences for t in s})
    frequent = {}
    # Earliest prefix end suffices for all subsequence extensions in each trace.
    stack = [((), tuple((i, 0) for i in range(len(sequences))))]
    while stack:
        prefix, projected = stack.pop()
        for token in alphabet:
            extension = []
            for i, start in projected:
                for j in range(start, len(sequences[i])):
                    if sequences[i][j] == token:
                        extension.append((i, j + 1))
                        break
            if len(extension) >= min_support:
                candidate = prefix + (token,)
                frequent[candidate] = len(extension)
                stack.append((candidate, tuple(extension)))
    closed = []
    for candidate, support in frequent.items():
        if not any(len(other) > len(candidate) and other_support == support
                   and positions(candidate, other) is not None
                   for other, other_support in frequent.items()):
            closed.append(Pattern(candidate, support))
    return tuple(sorted(closed, key=lambda p: p.tokens))


def filter_traces(traces, configuration):
    """Three named configs; cleaned variants model the multi-step-success corpus."""
    if configuration not in {"Full", "Exclude-errors", "Variant C"}:
        raise ValueError("unknown configuration")
    return tuple(t for t in traces if configuration == "Full" or (
        t.outcome != "error"
        and not (t.outcome == "success" and len(t.steps) <= 1)
        and not (configuration == "Variant C" and t.outcome == "timeout")))


def emit_signatures(training, k, min_support=1, min_precision=0.75):
    if k < 1 or not 0 <= min_precision <= 1:
        raise ValueError("invalid training parameters")
    training = tuple(training)
    prefixes = tuple(t.steps[:k] for t in training)
    result = []
    for pattern in mine_closed(prefixes, min_support):
        failures = sum(t.outcome != "success" and
                       positions(pattern.tokens, t.steps[:k]) is not None
                       for t in training)
        precision = failures / pattern.support
        if precision >= min_precision:
            result.append(Signature(pattern, failures, precision))
    return tuple(result)


def decide(prefix, signatures, timed_out=False):
    """Observation only: no matched result authorizes any external action."""
    prefix = tuple(prefix)
    if timed_out:
        return Decision(Verdict.TIMEOUT, (), len(prefix))
    matches = tuple(Match(s, found) for s in signatures
                    if (found := positions(s.pattern.tokens, prefix)) is not None)
    verdict = Verdict.STOP_AND_REPORT if matches else Verdict.UNMATCHED
    return Decision(verdict, matches, len(prefix))


def early_stop(steps, signatures, k):
    if k < 1:
        raise ValueError("k must be positive")
    prefix = tuple(steps)[:k]
    for length in range(1, len(prefix) + 1):
        decision = decide(prefix[:length], signatures)
        if decision.verdict is Verdict.STOP_AND_REPORT:
            return decision
    return decide(prefix, signatures)


def ratio(numerator, denominator):
    """Zero denominators are reported as zero; raw counts remain available."""
    return numerator / denominator if denominator else 0.0


def coverage(matched, evaluated):
    return ratio(matched, evaluated)


def precision(tp, fp):
    return ratio(tp, tp + fp)


def recall(tp, fn):
    return ratio(tp, tp + fn)


def evaluate(traces, signatures, k):
    """Offline prefix predictions, including timeout-labeled future outcomes."""
    traces = tuple(traces)
    tp = fp = fn = 0
    for trace in traces:
        stopped = early_stop(trace.steps, signatures, k).verdict is Verdict.STOP_AND_REPORT
        failure = trace.outcome != "success"
        tp += int(stopped and failure)
        fp += int(stopped and not failure)
        fn += int(not stopped and failure)
    matched = tp + fp
    return Metrics(len(traces), matched, tp, fp, fn,
                   coverage(matched, len(traces)), precision(tp, fp), recall(tp, fn))
