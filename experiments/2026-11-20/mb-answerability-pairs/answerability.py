"""mb-answerability-pairs: an answerability audit on a tiny synthetic industrial-controller fixture.

Method sketch of arXiv 2611.24682 (clean room: abstract page only, no repository exists, no code copied).
Stdlib only, no network, no model call. The same command is paired with two machine states that require
opposite answers (PERMIT in one, REFUSE in the other). Each arm is run under three input conditions, and the
audit records what the input contained, so a wrong answer can be told apart from a missing fact.

Scores: raw accuracy and balanced accuracy over all items, and a paired score in which a pair counts only
when both of its sides are answered correctly. ABSTAIN is never correct.
"""

import fractions
import json
import re
import sys

FIXTURE_VERSION = 1
PERMIT = "PERMIT"
REFUSE = "REFUSE"
ABSTAIN = "ABSTAIN"
EXPECTED = (PERMIT, REFUSE)
ARMS = ("always_permit", "always_refuse", "command_heuristic", "answerability_aware", "rule_evaluator")
CONDITIONS = ("command_only", "command_rules", "command_rules_state")
CONDITION_INPUTS = {
    "command_only": ("command",),
    "command_rules": ("command", "rules"),
    "command_rules_state": ("command", "rules", "state"),
}
ID_RE = re.compile(r"[A-Za-z0-9_]{1,40}")
MAX_ITEMS = 200
MAX_NAMES = 20
MAX_BYTES = 1000000
MAX_VALUE = 100000
Fraction = fractions.Fraction

OPS = {
    "lt": lambda value, limit: value < limit,
    "le": lambda value, limit: value <= limit,
    "gt": lambda value, limit: value > limit,
    "ge": lambda value, limit: value >= limit,
}
HEURISTIC_PERMIT_PREFIXES = ("start_", "open_")

SCOPE_NOTE = ("fixture completeness check only: the expected answers were written from the same rules the "
              "evaluator applies, so a perfect score shows the fixture is complete and says nothing about "
              "independent safety")


class AnswerError(Exception):
    """Malformed input: the CLI prints one ERROR line on stderr and exits 2."""

    def __init__(self, code, detail):
        Exception.__init__(self, "%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def _esc(value):
    return json.dumps(str(value), ensure_ascii=True)


# ---------------------------------------------------------------- strict loading

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise AnswerError("duplicate_key", "key %s is repeated" % _esc(key))
        out[key] = value
    return out


def _constant(name):
    raise AnswerError("bad_number", "%s is not a finite number" % _esc(name))


def parse(text):
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except AnswerError:
        raise
    except (ValueError, RecursionError):
        raise AnswerError("not_json", "input is not valid JSON")


def _obj(value, keys, where):
    if type(value) is not dict:
        raise AnswerError("wrong_type", "%s must be an object" % where)
    missing = [k for k in keys if k not in value]
    if missing:
        raise AnswerError("missing_key", "%s lacks %s" % (where, _esc(missing[0])))
    unknown = sorted(set(value) - set(keys))
    if unknown:
        raise AnswerError("unknown_key", "%s has unknown key %s" % (where, _esc(unknown[0])))
    return value


def _list(value, where, minimum, maximum):
    if type(value) is not list or len(value) < minimum or len(value) > maximum:
        raise AnswerError("wrong_type", "%s must be a list of %d to %d items" % (where, minimum, maximum))
    return value


def _id(value, where):
    if type(value) is not str or ID_RE.fullmatch(value) is None:
        raise AnswerError("bad_id", "%s must match [A-Za-z0-9_]{1,40}" % where)
    return value


def _value(value, where):
    if type(value) is not int:
        raise AnswerError("wrong_type", "%s must be an integer" % where)
    if not 0 <= value <= MAX_VALUE:
        raise AnswerError("bad_value", "%s must be from 0 to %d" % (where, MAX_VALUE))
    return value


def _answer(value, where):
    if type(value) is not str or value not in EXPECTED:
        raise AnswerError("bad_answer", "%s must be PERMIT or REFUSE" % where)
    return value


def _unique(names, where):
    if len(set(names)) != len(names):
        raise AnswerError("duplicate_name", "%s holds a repeated name" % where)


def _state(value, fields, where):
    if type(value) is not dict:
        raise AnswerError("wrong_type", "%s must be an object" % where)
    if sorted(value) != sorted(fields):
        raise AnswerError("bad_state", "%s must hold exactly the fields of its system" % where)
    return {f: _value(value[f], "%s.%s" % (where, f)) for f in fields}


def _systems(value):
    if type(value) is not dict or not 1 <= len(value) <= MAX_NAMES:
        raise AnswerError("wrong_type", "systems must be an object of 1 to %d systems" % MAX_NAMES)
    out = {}
    for name in value:
        _id(name, "system name")
        fields = [_id(f, "systems.%s field" % name) for f in _list(value[name], "systems.%s" % name, 1, MAX_NAMES)]
        _unique(fields, "systems.%s" % name)
        out[name] = fields
    return out


def _rules(value, systems):
    rules = []
    for i, r in enumerate(_list(value, "rules", 1, MAX_ITEMS)):
        where = "rules[%d]" % i
        r = _obj(r, ("id", "system", "command", "field", "op", "limit"), where)
        rule = {"id": _id(r["id"], where + ".id"), "system": _id(r["system"], where + ".system"),
                "command": _id(r["command"], where + ".command"), "field": _id(r["field"], where + ".field")}
        if rule["system"] not in systems:
            raise AnswerError("unknown_system", "%s names a system that is not declared" % where)
        if rule["field"] not in systems[rule["system"]]:
            raise AnswerError("unknown_field", "%s names a field its system does not have" % where)
        if type(r["op"]) is not str or r["op"] not in OPS:
            raise AnswerError("unknown_op", "%s op must be one of %s" % (where, ", ".join(sorted(OPS))))
        rule["op"] = r["op"]
        rule["limit"] = _value(r["limit"], where + ".limit")
        rules.append(rule)
    _unique([r["id"] for r in rules], "rule ids")
    _unique([r["command"] for r in rules], "rule commands")
    return rules


def _command(value, by_command, where):
    _id(value, where)
    if value not in by_command:
        raise AnswerError("unknown_command", "%s has no rule" % where)
    return by_command[value]


def validate(root):
    root = _obj(root, ("fixture_version", "systems", "rules", "pairs", "extras"), "fixture")
    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:
        raise AnswerError("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    systems = _systems(root["systems"])
    rules = _rules(root["rules"], systems)
    by_command = {r["command"]: r for r in rules}
    pairs = []
    for i, p in enumerate(_list(root["pairs"], "pairs", 1, MAX_ITEMS)):
        where = "pairs[%d]" % i
        p = _obj(p, ("id", "command", "state_a", "state_b", "expected_a", "expected_b"), where)
        pid = _id(p["id"], where + ".id")
        rule = _command(p["command"], by_command, where + ".command")
        fields = systems[rule["system"]]
        pair = {"id": pid, "command": p["command"],
                "state_a": _state(p["state_a"], fields, where + ".state_a"),
                "state_b": _state(p["state_b"], fields, where + ".state_b"),
                "expected_a": _answer(p["expected_a"], where + ".expected_a"),
                "expected_b": _answer(p["expected_b"], where + ".expected_b")}
        if pair["expected_a"] == pair["expected_b"]:
            raise AnswerError("pair_not_opposite", "%s must require opposite answers" % where)
        if pair["state_a"] == pair["state_b"]:
            raise AnswerError("same_state", "%s must hold two different states" % where)
        pairs.append(pair)
    extras = []
    for i, x in enumerate(_list(root["extras"], "extras", 0, MAX_ITEMS)):
        where = "extras[%d]" % i
        x = _obj(x, ("id", "command", "state", "expected"), where)
        xid = _id(x["id"], where + ".id")
        rule = _command(x["command"], by_command, where + ".command")
        extras.append({"id": xid, "command": x["command"],
                       "state": _state(x["state"], systems[rule["system"]], where + ".state"),
                       "expected": _answer(x["expected"], where + ".expected")})
    _unique([p["id"] for p in pairs] + [x["id"] for x in extras], "pair and extra ids")
    return {"systems": systems, "rules": rules, "pairs": pairs, "extras": extras}


def load_fixture(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_BYTES + 1)
    except OSError:
        raise AnswerError("unreadable", "file could not be read")
    if len(data) > MAX_BYTES:
        raise AnswerError("too_large", "file is larger than %d bytes" % MAX_BYTES)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise AnswerError("bad_encoding", "file is not valid UTF-8")
    return validate(parse(text))


# ---------------------------------------------------------------- items and inputs

def items(fx):
    """Every scored item: both sides of each pair, then the unpaired extras."""
    out = []
    for p in fx["pairs"]:
        out.append({"id": p["id"] + ".a", "pair": p["id"], "command": p["command"],
                    "state": p["state_a"], "expected": p["expected_a"]})
        out.append({"id": p["id"] + ".b", "pair": p["id"], "command": p["command"],
                    "state": p["state_b"], "expected": p["expected_b"]})
    for x in fx["extras"]:
        out.append({"id": x["id"], "pair": None, "command": x["command"],
                    "state": x["state"], "expected": x["expected"]})
    return out


def build_input(fx, item, condition):
    """The only thing an arm may read. Fields not in the condition are None."""
    if condition not in CONDITIONS:
        raise ValueError("unknown condition")
    return {
        "command": item["command"],
        "rules": fx["rules"] if "rules" in CONDITION_INPUTS[condition] else None,
        "state": item["state"] if "state" in CONDITION_INPUTS[condition] else None,
    }


def find_rule(rules, command):
    if rules is None:
        return None
    for r in rules:
        if r["command"] == command:
            return r
    return None


def needed_field(inp):
    rule = find_rule(inp["rules"], inp["command"])
    return None if rule is None else rule["field"]


def answerable(inp):
    """True only when the input holds the state field the command's rule depends on."""
    field = needed_field(inp)
    return field is not None and inp["state"] is not None and field in inp["state"]


def decide(rule, value):
    return PERMIT if OPS[rule["op"]](value, rule["limit"]) else REFUSE


# ---------------------------------------------------------------- arms

def arm_always_permit(inp):
    return PERMIT


def arm_always_refuse(inp):
    return REFUSE


def arm_command_heuristic(inp):
    """State-blind: reads the command text only."""
    return PERMIT if inp["command"].startswith(HEURISTIC_PERMIT_PREFIXES) else REFUSE


def arm_answerability_aware(inp):
    """Answers only when the input holds the needed state field; otherwise ABSTAIN."""
    if not answerable(inp):
        return ABSTAIN
    rule = find_rule(inp["rules"], inp["command"])
    return decide(rule, inp["state"][rule["field"]])


def arm_rule_evaluator(inp):
    """Deterministic reference: applies the fixture rules to the state it is given."""
    if inp["rules"] is None or inp["state"] is None:
        return ABSTAIN
    rule = find_rule(inp["rules"], inp["command"])
    if rule is None or rule["field"] not in inp["state"]:
        return ABSTAIN
    return decide(rule, inp["state"][rule["field"]])


ARM_FUNCTIONS = {
    "always_permit": arm_always_permit,
    "always_refuse": arm_always_refuse,
    "command_heuristic": arm_command_heuristic,
    "answerability_aware": arm_answerability_aware,
    "rule_evaluator": arm_rule_evaluator,
}


def answer(arm, inp):
    if arm not in ARM_FUNCTIONS:
        raise ValueError("unknown arm")
    return ARM_FUNCTIONS[arm](inp)


# ---------------------------------------------------------------- scoring

def _frac(f):
    return "%d/%d" % (f.numerator, f.denominator)


def _dec(f):
    scaled = (f.numerator * 20000 + f.denominator) // (2 * f.denominator)
    return "%d.%04d" % (scaled // 10000, scaled % 10000)


def score(fx, arm, condition):
    its = items(fx)
    answers = {}
    correct = {}
    answerable_count = 0
    abstentions = 0
    for it in its:
        inp = build_input(fx, it, condition)
        if answerable(inp):
            answerable_count += 1
        a = answer(arm, inp)
        if a == ABSTAIN:
            abstentions += 1
        answers[it["id"]] = a
        correct[it["id"]] = a == it["expected"]
    total = len(its)
    hits = sum(1 for v in correct.values() if v)
    recalls = []
    for cls in EXPECTED:
        group = [it for it in its if it["expected"] == cls]
        recalls.append(Fraction(sum(1 for it in group if correct[it["id"]]), len(group)))
    pairs_hit = sum(1 for p in fx["pairs"] if correct[p["id"] + ".a"] and correct[p["id"] + ".b"])
    return {
        "condition": condition, "arm": arm, "inputs": list(CONDITION_INPUTS[condition]),
        "answerable_items": "%d/%d" % (answerable_count, total),
        "raw": Fraction(hits, total), "balanced": (recalls[0] + recalls[1]) / 2,
        "pairs_correct": pairs_hit, "pairs_total": len(fx["pairs"]), "abstentions": abstentions,
        "answers": answers,
    }


def _row(s):
    return {
        "condition": s["condition"], "arm": s["arm"], "inputs": s["inputs"],
        "answerable_items": s["answerable_items"],
        "raw": _frac(s["raw"]), "raw_decimal": _dec(s["raw"]),
        "balanced": _frac(s["balanced"]), "balanced_decimal": _dec(s["balanced"]),
        "pairs_correct": s["pairs_correct"], "pairs_total": s["pairs_total"], "abstentions": s["abstentions"],
    }


def run(fx):
    scores = {(c, a): score(fx, a, c) for c in CONDITIONS for a in ARMS}
    rows = [_row(scores[(c, a)]) for c in CONDITIONS for a in ARMS]
    its = items(fx)
    permit_items = sum(1 for it in its if it["expected"] == PERMIT)
    no_state = [scores[(c, a)] for c in CONDITIONS if c != "command_rules_state" for a in ARMS]
    same_inputs = all(build_input(fx, {"command": p["command"], "state": p["state_a"]}, c)
                      == build_input(fx, {"command": p["command"], "state": p["state_b"]}, c)
                      for c in CONDITIONS if c != "command_rules_state" for p in fx["pairs"])
    permit = scores[("command_only", "always_permit")]
    refuse = scores[("command_only", "always_refuse")]
    evaluator = scores[("command_rules_state", "rule_evaluator")]
    checks = {
        "a_no_state_no_arm_gets_a_pair": {
            "holds": same_inputs and all(s["pairs_correct"] == 0 for s in no_state),
            "both_sides_have_identical_input": same_inputs,
            "max_pairs_correct_without_state": max(s["pairs_correct"] for s in no_state),
        },
        "b_always_arms_raw_gap_with_balanced_half_and_no_pairs": {
            "holds": (permit["raw"] != refuse["raw"] and permit["balanced"] == Fraction(1, 2)
                      and refuse["balanced"] == Fraction(1, 2)
                      and permit["pairs_correct"] == 0 and refuse["pairs_correct"] == 0),
            "raw_always_permit": _frac(permit["raw"]), "raw_always_refuse": _frac(refuse["raw"]),
            "raw_gap": _frac(abs(permit["raw"] - refuse["raw"])),
            "balanced_always_permit": _frac(permit["balanced"]), "balanced_always_refuse": _frac(refuse["balanced"]),
            "pairs_correct_always_permit": permit["pairs_correct"],
            "pairs_correct_always_refuse": refuse["pairs_correct"],
        },
        "c_rule_evaluator_with_rules_and_state_gets_every_pair": {
            "holds": evaluator["pairs_correct"] == evaluator["pairs_total"] and evaluator["raw"] == 1,
            "pairs_correct": evaluator["pairs_correct"], "pairs_total": evaluator["pairs_total"],
            "scope": SCOPE_NOTE,
        },
    }
    return {
        "fixture": {"systems": len(fx["systems"]), "rules": len(fx["rules"]), "pairs": len(fx["pairs"]),
                    "extras": len(fx["extras"]), "items": len(its), "permit_items": permit_items,
                    "refuse_items": len(its) - permit_items},
        "results": rows, "checks": checks, "scope_note": SCOPE_NOTE,
    }


def report(fx):
    return json.dumps(run(fx), indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("ERROR usage: answerability.py FIXTURE.json\n")
        return 2
    try:
        text = report(load_fixture(argv[1]))
    except AnswerError as e:
        sys.stderr.write("ERROR %s: %s\n" % (e.code, e.detail))
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
