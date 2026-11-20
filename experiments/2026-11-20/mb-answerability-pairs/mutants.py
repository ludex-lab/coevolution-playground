"""Mutation self-check for mb-answerability-pairs (stdlib only).

Each mutant replaces one exact source fragment (which must occur exactly once) in a copy of this
folder, then runs the unittest suite with the same Python interpreter. A mutant is killed when the
suite fails. Run: python3 -B mutants.py   (exit 0 only when every mutant is killed)
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
COPY = ("answerability.py", "test_answerability.py", "demo.py", "mutants.py", "README.md", "evidence.json", "fixtures")
M = "answerability.py"
NL = "\n"

MUTANTS = [
    # the rule operators and the decision
    ("ops", r'"lt": lambda value, limit: value < limit,', r'"lt": lambda value, limit: value <= limit,'),
    ("ops", r'"le": lambda value, limit: value <= limit,', r'"le": lambda value, limit: value < limit,'),
    ("ops", r'"gt": lambda value, limit: value > limit,', r'"gt": lambda value, limit: value >= limit,'),
    ("ops", r'"ge": lambda value, limit: value >= limit,', r'"ge": lambda value, limit: value > limit,'),
    ("ops", r'    return PERMIT if OPS[rule["op"]](value, rule["limit"]) else REFUSE', r'    return REFUSE if OPS[rule["op"]](value, rule["limit"]) else PERMIT'),
    ("ops", r'    return PERMIT if OPS[rule["op"]](value, rule["limit"]) else REFUSE', r'    return PERMIT if OPS[rule["op"]](rule["limit"], value) else REFUSE'),
    ("ops", r'EXPECTED = (PERMIT, REFUSE)', r'EXPECTED = (PERMIT,)'),
    ("ops", r'FIXTURE_VERSION = 1', r'FIXTURE_VERSION = 2'),
    # the arms
    ("arms", r'def arm_always_permit(inp):' + NL + r'    return PERMIT', r'def arm_always_permit(inp):' + NL + r'    return REFUSE'),
    ("arms", r'def arm_always_refuse(inp):' + NL + r'    return REFUSE', r'def arm_always_refuse(inp):' + NL + r'    return PERMIT'),
    ("arms", r'HEURISTIC_PERMIT_PREFIXES = ("start_", "open_")', r'HEURISTIC_PERMIT_PREFIXES = ("start_",)'),
    ("arms", r'HEURISTIC_PERMIT_PREFIXES = ("start_", "open_")', r'HEURISTIC_PERMIT_PREFIXES = ("start_", "open_", "raise_")'),
    ("arms", r'    return PERMIT if inp["command"].startswith(HEURISTIC_PERMIT_PREFIXES) else REFUSE', r'    return REFUSE if inp["command"].startswith(HEURISTIC_PERMIT_PREFIXES) else PERMIT'),
    ("arms", r'    return PERMIT if inp["command"].startswith(HEURISTIC_PERMIT_PREFIXES) else REFUSE', r'    return PERMIT if HEURISTIC_PERMIT_PREFIXES[0] in inp["command"] else REFUSE'),
    ("arms", r'    if not answerable(inp):' + NL + r'        return ABSTAIN', r'    if False:' + NL + r'        return ABSTAIN'),
    ("arms", r'    if not answerable(inp):' + NL + r'        return ABSTAIN', r'    if not answerable(inp):' + NL + r'        return REFUSE'),
    ("arms", r'    if inp["rules"] is None or inp["state"] is None:', r'    if inp["rules"] is None and inp["state"] is None:'),
    ("arms", r'    if inp["rules"] is None or inp["state"] is None:' + NL + r'        return ABSTAIN', r'    if inp["rules"] is None or inp["state"] is None:' + NL + r'        return REFUSE'),
    ("arms", r'    if rule is None or rule["field"] not in inp["state"]:', r'    if rule is None:'),
    ("arms", r'    if arm not in ARM_FUNCTIONS:', r'    if False:'),
    ("arms", r'    "answerability_aware": arm_answerability_aware,', r'    "answerability_aware": arm_rule_evaluator,'),
    ("arms", r'    "rule_evaluator": arm_rule_evaluator,', r'    "rule_evaluator": arm_answerability_aware,'),
    ("arms", r'    "command_heuristic": arm_command_heuristic,', r'    "command_heuristic": arm_always_permit,'),
    # what the input holds
    ("input", r'    return field is not None and inp["state"] is not None and field in inp["state"]', r'    return inp["state"] is not None'),
    ("input", r'    return field is not None and inp["state"] is not None and field in inp["state"]', r'    return field is not None'),
    ("input", r'    return None if rule is None else rule["field"]', r'    return None if rule is None else rule["limit"]'),
    ("input", r'    if rules is None:', r'    if False:'),
    ("input", r'        if r["command"] == command:', r'        if r["command"] != command:'),
    ("input", r'        "rules": fx["rules"] if "rules" in CONDITION_INPUTS[condition] else None,', r'        "rules": fx["rules"],'),
    ("input", r'        "state": item["state"] if "state" in CONDITION_INPUTS[condition] else None,', r'        "state": item["state"],'),
    ("input", r'        "state": item["state"] if "state" in CONDITION_INPUTS[condition] else None,', r'        "state": None,'),
    ("input", r'    if condition not in CONDITIONS:', r'    if False:'),
    ("input", r'    "command_only": ("command",),', r'    "command_only": ("command", "rules"),'),
    ("input", r'    "command_rules": ("command", "rules"),', r'    "command_rules": ("command",),'),
    ("input", r'    "command_rules_state": ("command", "rules", "state"),', r'    "command_rules_state": ("command", "state"),'),
    ("input", r'CONDITIONS = ("command_only", "command_rules", "command_rules_state")', r'CONDITIONS = ("command_rules", "command_only", "command_rules_state")'),
    # the items
    ("items", r'"state": p["state_a"], "expected": p["expected_a"]})', r'"state": p["state_a"], "expected": p["expected_b"]})'),
    ("items", r'"state": p["state_b"], "expected": p["expected_b"]})', r'"state": p["state_b"], "expected": p["expected_a"]})'),
    ("items", r'out.append({"id": p["id"] + ".a", "pair": p["id"], "command": p["command"],', r'out.append({"id": p["id"] + ".b", "pair": p["id"], "command": p["command"],'),
    ("items", r'"state": x["state"], "expected": x["expected"]})', r'"state": x["state"], "expected": PERMIT})'),
    # the scores
    ("score", r'        correct[it["id"]] = a == it["expected"]', r'        correct[it["id"]] = a != ABSTAIN'),
    ("score", r'        if answerable(inp):', r'        if not answerable(inp):'),
    ("score", r'        if a == ABSTAIN:', r'        if a != ABSTAIN:'),
    ("score", r'    for cls in EXPECTED:', r'    for cls in EXPECTED[:1]:'),
    ("score", r'        group = [it for it in its if it["expected"] == cls]', r'        group = [it for it in its if it["expected"] in EXPECTED]'),
    ("score", r'recalls.append(Fraction(sum(1 for it in group if correct[it["id"]]), len(group)))', r'recalls.append(Fraction(sum(1 for it in group if correct[it["id"]]), len(its)))'),
    ("score", r'"balanced": (recalls[0] + recalls[1]) / 2,', r'"balanced": recalls[0],'),
    ("score", r'"balanced": (recalls[0] + recalls[1]) / 2,', r'"balanced": max(recalls[0], recalls[1]),'),
    ("score", r'if correct[p["id"] + ".a"] and correct[p["id"] + ".b"])', r'if correct[p["id"] + ".a"] or correct[p["id"] + ".b"])'),
    ("score", r'if correct[p["id"] + ".a"] and correct[p["id"] + ".b"])', r'if correct[p["id"] + ".a"])'),
    ("score", r'"raw": Fraction(hits, total),', r'"raw": Fraction(hits, total + 1),'),
    ("score", r'"pairs_total": len(fx["pairs"]), "abstentions": abstentions,', r'"pairs_total": len(fx["pairs"]) + 1, "abstentions": abstentions,'),
    ("score", r'    hits = sum(1 for v in correct.values() if v)', r'    hits = sum(1 for v in correct.values() if v) + abstentions'),
    # number text
    ("text", r'    return "%d/%d" % (f.numerator, f.denominator)', r'    return "%d/%d" % (f.denominator, f.numerator)'),
    ("text", r'    scaled = (f.numerator * 20000 + f.denominator) // (2 * f.denominator)', r'    scaled = f.numerator * 10000 // f.denominator'),
    ("text", r'    return "%d.%04d" % (scaled // 10000, scaled % 10000)', r'    return "%d.%03d" % (scaled // 10000, scaled % 10000)'),
    # the report and the three checks
    ("report", r'    rows = [_row(scores[(c, a)]) for c in CONDITIONS for a in ARMS]', r'    rows = [_row(scores[(c, a)]) for a in ARMS for c in CONDITIONS]'),
    ("report", r'for c in CONDITIONS if c != "command_rules_state" for a in ARMS]', r'for c in CONDITIONS for a in ARMS]'),
    ("report", r'for c in CONDITIONS if c != "command_rules_state" for p in fx["pairs"])', r'for c in CONDITIONS for p in fx["pairs"])'),
    ("report", r'"holds": same_inputs and all(s["pairs_correct"] == 0 for s in no_state),', r'"holds": True,'),
    ("report", r'"holds": (permit["raw"] != refuse["raw"] and permit["balanced"] == Fraction(1, 2)', r'"holds": (permit["raw"] == refuse["raw"] and permit["balanced"] == Fraction(1, 2)'),
    ("report", r'"holds": (permit["raw"] != refuse["raw"] and permit["balanced"] == Fraction(1, 2)', r'"holds": (permit["raw"] != refuse["raw"] and permit["balanced"] != Fraction(1, 2)'),
    ("report", r'and refuse["balanced"] == Fraction(1, 2)', r'and refuse["balanced"] != Fraction(1, 2)'),
    ("report", r'"raw_gap": _frac(abs(permit["raw"] - refuse["raw"])),', r'"raw_gap": _frac(permit["raw"] - refuse["raw"]),'),
    ("report", r'"holds": evaluator["pairs_correct"] == evaluator["pairs_total"] and evaluator["raw"] == 1,', r'"holds": evaluator["pairs_correct"] == evaluator["pairs_total"],'),
    ("report", r'"holds": evaluator["pairs_correct"] == evaluator["pairs_total"] and evaluator["raw"] == 1,', r'"holds": True,'),
    ("report", r'    evaluator = scores[("command_rules_state", "rule_evaluator")]', r'    evaluator = scores[("command_rules_state", "answerability_aware")]'),
    ("report", r'    permit = scores[("command_only", "always_permit")]', r'    permit = scores[("command_only", "always_refuse")]'),
    ("report", r'SCOPE_NOTE = ("fixture completeness check only: the expected answers', r'SCOPE_NOTE = ("fixture check only: the expected answers'),
    ("report", r'    permit_items = sum(1 for it in its if it["expected"] == PERMIT)', r'    permit_items = sum(1 for it in its if it["expected"] == REFUSE)'),
    # the CLI
    ("cli", r'    if len(argv) != 2:', r'    if len(argv) != 3:'),
    ("cli", r'    except AnswerError as e:', r'    except KeyError as e:'),
    ("cli", r'        sys.stderr.write("ERROR %s: %s\n" % (e.code, e.detail))', r'        sys.stderr.write("ERROR %s %s\n" % (e.code, e.detail))'),
    ("cli", r'    sys.stdout.write(text)' + NL + r'    return 0', r'    sys.stdout.write(text)' + NL + r'    return 1'),
    ("cli", r'    except OSError:', r'    except KeyError:'),
    ("cli", r'    except UnicodeDecodeError:', r'    except KeyError:'),
    ("cli", r'        with open(path, "rb") as fh:' + NL + r'            data = fh.read(MAX_BYTES + 1)', r'        with open(path, "rb") as fh:' + NL + r'            data = fh.read(MAX_BYTES)'),
    ("cli", r'    if len(data) > MAX_BYTES:', r'    if len(data) >= MAX_BYTES:'),
    # strict loading
    ("load", r'    except (ValueError, RecursionError):', r'    except ValueError:'),
    ("load", r'    except AnswerError:' + NL + r'        raise', r'    except AnswerError:' + NL + r'        raise AnswerError("not_json", "input is not valid JSON")'),
    ("load", r'        if key in out:', r'        if False:'),
    ("load", r'    raise AnswerError("bad_number", "%s is not a finite number" % _esc(name))', r'    raise AnswerError("not_json", "%s is not a finite number" % _esc(name))'),
    ("load", r'    if missing:', r'    if False:'),
    ("load", r'    if unknown:', r'    if False:'),
    ("load", r'    if type(value) is not dict:' + NL + r'        raise AnswerError("wrong_type", "%s must be an object" % where)' + NL + r'    missing', r'    if False:' + NL + r'        raise AnswerError("wrong_type", "%s must be an object" % where)' + NL + r'    missing'),
    ("load", r'    if type(value) is not dict:' + NL + r'        raise AnswerError("wrong_type", "%s must be an object" % where)' + NL + r'    if sorted', r'    if False:' + NL + r'        raise AnswerError("wrong_type", "%s must be an object" % where)' + NL + r'    if sorted'),
    ("load", r'    if type(value) is not list or len(value) < minimum or len(value) > maximum:', r'    if type(value) is not list or len(value) <= minimum or len(value) > maximum:'),
    ("load", r'    if type(value) is not list or len(value) < minimum or len(value) > maximum:', r'    if type(value) is not list or len(value) < minimum or len(value) >= maximum:'),
    ("load", r'    if type(value) is not list or len(value) < minimum or len(value) > maximum:', r'    if len(value) < minimum or len(value) > maximum:'),
    ("load", r'MAX_ITEMS = 200', r'MAX_ITEMS = 199'),
    ("load", r'MAX_NAMES = 20', r'MAX_NAMES = 19'),
    ("load", r'ID_RE.fullmatch(value) is None', r'ID_RE.match(value) is None'),
    ("load", r'ID_RE = re.compile(r"[A-Za-z0-9_]{1,40}")', r'ID_RE = re.compile(r"[A-Za-z0-9_]{1,41}")'),
    ("load", r'ID_RE = re.compile(r"[A-Za-z0-9_]{1,40}")', r'ID_RE = re.compile(r"[A-Za-z0-9_]{0,40}")'),
    ("load", r'ID_RE = re.compile(r"[A-Za-z0-9_]{1,40}")', r'ID_RE = re.compile(r"[A-Za-z0-9_ ]{1,40}")'),
    ("load", r'    if type(value) is not str or ID_RE', r'    if ID_RE'),
    ("load", r'    if type(value) is not int:', r'    if not isinstance(value, int):'),
    ("load", r'    if not 0 <= value <= MAX_VALUE:', r'    if not 0 < value <= MAX_VALUE:'),
    ("load", r'    if not 0 <= value <= MAX_VALUE:', r'    if not 0 <= value < MAX_VALUE:'),
    ("load", r'MAX_VALUE = 100000', r'MAX_VALUE = 200000'),
    ("load", r'MAX_BYTES = 1000000', r'MAX_BYTES = 999999'),
    ("load", r'    if len(set(names)) != len(names):', r'    if False:'),
    ("load", r'    if sorted(value) != sorted(fields):', r'    if False:'),
    ("load", r'    if sorted(value) != sorted(fields):', r'    if set(value) < set(fields):'),
    ("load", r'    if type(value) is not dict or not 1 <= len(value) <= MAX_NAMES:', r'    if type(value) is not dict or not 0 <= len(value) <= MAX_NAMES:'),
    ("load", r'        _unique(fields, "systems.%s" % name)', r'        pass'),
    ("load", r'        if rule["system"] not in systems:', r'        if False:'),
    ("load", r'        if rule["field"] not in systems[rule["system"]]:', r'        if False:'),
    ("load", r'        if type(r["op"]) is not str or r["op"] not in OPS:', r'        if r["op"] not in OPS:'),
    ("load", r'    _unique([r["id"] for r in rules], "rule ids")', r'    pass'),
    ("load", r'    _unique([r["command"] for r in rules], "rule commands")', r'    pass'),
    ("load", r'    if value not in by_command:', r'    if False:'),
    ("load", r'    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:', r'    if root["fixture_version"] != FIXTURE_VERSION:'),
    ("load", r'        if pair["expected_a"] == pair["expected_b"]:', r'        if False:'),
    ("load", r'        if pair["state_a"] == pair["state_b"]:', r'        if False:'),
    ("load", r'    _unique([p["id"] for p in pairs] + [x["id"] for x in extras], "pair and extra ids")', r'    _unique([p["id"] for p in pairs], "pair and extra ids")'),
    ("load", r'    _unique([p["id"] for p in pairs] + [x["id"] for x in extras], "pair and extra ids")', r'    _unique([x["id"] for x in extras], "pair and extra ids")'),
]


def run_suite(folder):
    res = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q", "test_answerability"], cwd=folder,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return res.returncode


def main():
    base = tempfile.mkdtemp(prefix="mb-answerability-mutants-")
    try:
        clean = os.path.join(base, "clean")
        os.mkdir(clean)
        for name in COPY:
            src = os.path.join(HERE, name)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(clean, name))
            else:
                shutil.copy2(src, os.path.join(clean, name))
        if run_suite(clean) != 0:
            print("baseline suite fails; no mutants run")
            return 1
        with open(os.path.join(clean, M), encoding="utf-8") as handle:
            source = handle.read()
        survivors = 0
        for idx, (group, old, new) in enumerate(MUTANTS, 1):
            if source.count(old) != 1:
                print("mutant %02d %-7s fragment occurs %d times" % (idx, group, source.count(old)))
                return 1
            folder = os.path.join(base, "m%03d" % idx)
            shutil.copytree(clean, folder)
            with open(os.path.join(folder, M), "w", encoding="utf-8") as handle:
                handle.write(source.replace(old, new))
            killed = run_suite(folder) != 0
            survivors += 0 if killed else 1
            print("mutant %03d %-7s %s" % (idx, group, "killed" if killed else "SURVIVED"))
            shutil.rmtree(folder)
        total = len(MUTANTS)
        print("killed %d/%d" % (total - survivors, total))
        return 0 if survivors == 0 else 1
    finally:
        shutil.rmtree(base)


if __name__ == "__main__":
    sys.exit(main())
