"""Mutation self-check for mb-certified-region-delta (stdlib only).

Each mutant replaces one exact source fragment of region.py (it must occur exactly once) in a copy of
this folder, then runs the unittest suite with the same Python interpreter. A mutant is killed when the
suite fails. Run: python3 -B mutants.py   (exit 0 only when every mutant is killed)
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
COPY = ("region.py", "test_region.py", "demo.py", "mutants.py", "README.md", "evidence.json", "fixtures")
M = "region.py"

MUTANTS = [
    # boundaries
    ('return value < lo or value > hi', 'return value <= lo or value > hi'),
    ('return value < lo or value > hi', 'return value < lo or value >= hi'),
    ('return value < lo or value > hi', 'return value < lo'),
    ('return value < lo or value > hi', 'return value > hi'),
    # classification inputs
    ('_outside(obs["state"][d["name"]], d["hard_lo"], d["hard_hi"])', '_outside(obs["state"][d["name"]], d["lo"], d["hi"])'),
    ('_outside(obs["state"][d["name"]], d["hard_lo"], d["hard_hi"])', '_outside(obs["state"][d["name"]], d["hard_lo"], d["hi"])'),
    ('_outside(obs["state"][d["name"]], d["lo"], d["hi"])]\n    odd', '_outside(obs["state"][d["name"]], d["hard_lo"], d["hard_hi"])]\n    odd'),
    ('_outside(obs["env"][v["name"]], v["lo"], v["hi"])', '_outside(obs["env"][v["name"]], v["lo"], v["hi"] + 10)'),
    ('_outside(obs["env"][v["name"]], v["lo"], v["hi"])', 'False'),
    # class precedence
    ('    if hard:\n        klass = "HARD_SAFETY"\n    elif odd:\n        klass = "ODD_EXIT"',
     '    if odd:\n        klass = "ODD_EXIT"\n    elif hard:\n        klass = "HARD_SAFETY"'),
    ('    elif odd:\n        klass = "ODD_EXIT"\n    elif out:', '    elif out:\n        klass = "OUT_OF_REGION"\n    elif odd:\n        klass = "ODD_EXIT"\n    elif False:'),
    ('        klass = "HARD_SAFETY"', '        klass = "OUT_OF_REGION"'),
    ('        klass = "OUT_OF_REGION"\n    else:', '        klass = "IN_REGION"\n    else:'),
    # arm A responses
    ('response, reason, detail = "SHUTDOWN", "hard_safety_violation", c["hard"]', 'response, reason, detail = "WITHDRAW_AUTHORIZATION", "hard_safety_violation", c["hard"]'),
    ('response, reason, detail = "RECERTIFY", "odd_exit", c["odd"]', 'response, reason, detail = "WITHDRAW_AUTHORIZATION", "odd_exit", c["odd"]'),
    ('response, reason, detail = "RECERTIFY", "odd_exit", c["odd"]', 'response, reason, detail = "SHUTDOWN", "odd_exit", c["odd"]'),
    ('response, reason, detail = "RECERTIFY", "odd_exit", c["odd"]', 'response, reason, detail = "CONTINUE", "odd_exit", c["odd"]'),
    ('response, reason, detail = "CONTINUE", "in_region", []\n            if pending', 'response, reason, detail = "RECERTIFY", "in_region", []\n            if pending'),
    ('response, reason = "WITHDRAW_AUTHORIZATION", "critical_single_dim"', 'response, reason = "SHUTDOWN", "critical_single_dim"'),
    ('response, reason = "WITHDRAW_AUTHORIZATION", "critical_single_dim"', 'response, reason = "CONTINUE", "critical_single_dim"'),
    ('response, reason = "WITHDRAW_AUTHORIZATION", "correlated_degradation"', 'response, reason = "SHUTDOWN", "correlated_degradation"'),
    ('response, reason = "WITHDRAW_AUTHORIZATION", "correlated_degradation"', 'response, reason = "CONTINUE", "correlated_degradation"'),
    ('response, reason = "WITHDRAW_AUTHORIZATION", "confirmed_outlier"', 'response, reason = "SHUTDOWN", "confirmed_outlier"'),
    ('response, reason = "CONTINUE", "quarantined_outlier"', 'response, reason = "WITHDRAW_AUTHORIZATION", "quarantined_outlier"'),
    # critical and correlated rules
    ('if any(critical[n] for n in c["out"]):', 'if all(critical[n] for n in c["out"]):'),
    ('if any(critical[n] for n in c["out"]):', 'if False:'),
    ('elif len(c["out"]) >= 2:', 'elif len(c["out"]) >= 3:'),
    ('elif len(c["out"]) >= 2:', 'elif len(c["out"]) >= 1:'),
    # quarantine
    ('elif pending is not None:', 'elif pending is not None and c["out"][0] == pending:'),
    ('elif pending is not None:', 'elif False:'),
    ('quarantine = "pending:" + c["out"][0]\n                following = c["out"][0]', 'quarantine = "pending:" + c["out"][0]\n                following = None'),
    ('        pending = following\n', '        pending = following if following else pending\n'),
    ('            if pending is not None:\n                quarantine = "released:" + pending', '            if False:\n                quarantine = "released:" + str(pending)'),
    ('quarantine = "confirmed:" + pending', 'quarantine = "pending:" + pending'),
    # arm B
    ('        if c["out"]:\n            response, reason, detail = "SHUTDOWN", "outside_region", c["out"]', '        if c["hard"]:\n            response, reason, detail = "SHUTDOWN", "outside_region", c["hard"]'),
    ('response, reason, detail = "WITHDRAW_AUTHORIZATION", "odd_exit_authority_cut", c["odd"]', 'response, reason, detail = "RECERTIFY", "odd_exit_authority_cut", c["odd"]'),
    ('response, reason, detail = "WITHDRAW_AUTHORIZATION", "odd_exit_authority_cut", c["odd"]', 'response, reason, detail = "CONTINUE", "odd_exit_authority_cut", c["odd"]'),
    ('        elif c["odd"]:\n            response, reason, detail = "WITHDRAW', '        elif False:\n            response, reason, detail = "WITHDRAW'),
    # effects table
    ('"RECERTIFY": {"authority": "retained", "power": "on", "recertify": True}', '"RECERTIFY": {"authority": "withdrawn", "power": "on", "recertify": True}'),
    ('"RECERTIFY": {"authority": "retained", "power": "on", "recertify": True}', '"RECERTIFY": {"authority": "retained", "power": "off", "recertify": True}'),
    ('"WITHDRAW_AUTHORIZATION": {"authority": "withdrawn", "power": "on", "recertify": False}', '"WITHDRAW_AUTHORIZATION": {"authority": "withdrawn", "power": "off", "recertify": False}'),
    ('"CONTINUE": {"authority": "retained", "power": "on", "recertify": False}', '"CONTINUE": {"authority": "retained", "power": "on", "recertify": True}'),
    ('"SHUTDOWN": {"authority": "withdrawn", "power": "off", "recertify": False}', '"SHUTDOWN": {"authority": "retained", "power": "off", "recertify": False}'),
    # distinguishable and compare
    ('    return len(effects) == len(set(effects))', '    return True'),
    ('    if len(seen) != len(RESPONSES):', '    if False:'),
    ('if b["response"] == "SHUTDOWN" and a["response"] != "SHUTDOWN"]', 'if b["response"] == "SHUTDOWN"]'),
    ('if a["response"] == "SHUTDOWN" and b["response"] != "SHUTDOWN"]', 'if a["response"] == "SHUTDOWN"]'),
    ('if a["response"] == "RECERTIFY" and b["response"] == "WITHDRAW_AUTHORIZATION"]', 'if b["response"] == "WITHDRAW_AUTHORIZATION"]'),
    # validation
    ('if dim["lo"] > dim["hi"]:', 'if dim["lo"] > dim["hi"] + 100:'),
    ('if dim["hard_lo"] > dim["lo"] or dim["hi"] > dim["hard_hi"]:', 'if dim["hard_lo"] > dim["lo"]:'),
    ('if dim["hard_lo"] > dim["lo"] or dim["hi"] > dim["hard_hi"]:', 'if dim["hi"] > dim["hard_hi"]:'),
    ('if var["lo"] > var["hi"]:', 'if False:'),
    ('if _fold(obs["id"]) in [_fold(n) for n in seen]:', 'if False:'),
    ('if _fold(obs["id"]) in [_fold(n) for n in seen]:', 'if obs["id"] in seen:'),
    ('if _fold(dim["name"]) in [_fold(n) for n in dim_names]:', 'if False:'),
    ('if _fold(dim["name"]) in [_fold(n) for n in dim_names]:', 'if dim["name"] in dim_names:'),
    ('if _fold(var["name"]) in [_fold(n) for n in odd_names]:', 'if var["name"] in odd_names:'),
    ('if isinstance(value, bool) or not isinstance(value, (int, float)):', 'if not isinstance(value, (int, float)):'),
    ('    try:\n        finite = math.isfinite(value)\n    except OverflowError:\n        finite = False', '    finite = True'),
    ('    except OverflowError:\n        finite = False', '    except ZeroDivisionError:\n        finite = False'),
    ('raise FixtureError("duplicate_key", ascii(key))', 'raise FixtureError("duplicate_key", key)'),
    ('raise FixtureError("duplicate_key", ascii(key))', '            continue'),
    ('    raise FixtureError("non_finite", name)', '    return 0.0'),
    ('(where, ascii(key)))', '(where, key))'),
    ('            raise FixtureError("unknown_key", "%s has unknown key %s" % (where, ascii(key)))', '            pass'),
    ('            raise FixtureError("missing_key", "%s lacks %s" % (where, key))', '            pass'),
    ('"%s has unknown name %s" % (where, ascii(name))', '"%s has unknown name %s" % (where, name)'),
    ('            raise FixtureError("unknown_value", "%s has unknown name %s" % (where, ascii(name)))', '            continue'),
    ('            raise FixtureError("missing_value", "%s lacks %s" % (where, name))', '            continue'),
    ('        raise FixtureError("empty_list", "%s must not be empty" % where)', '        pass'),
    ('        _flag(dim["critical"], where + ".critical")', '        pass'),
    # sticky shutdown: withdrawal-class rows after a hard row (Z08 and Z18 survived on main before the extended test)
    ('        if shut_down and response != "SHUTDOWN":', '        if shut_down and response not in ("SHUTDOWN", "WITHDRAW_AUTHORIZATION"):'),
    ('        if shut_down and response != "SHUTDOWN":', '        if response == "WITHDRAW_AUTHORIZATION" and reason in ("critical_single_dim", "correlated_degradation"):\n            shut_down = False\n        if shut_down and response != "SHUTDOWN":'),
    # blank look-alikes and the README sentence
    (' or ch in BLANK_LOOKALIKES:', ':'),
    ('BLANK_LOOKALIKES = ("\\u3164", "\\u2800")', 'BLANK_LOOKALIKES = ("\\u3164",)'),
    ('BLANK_LOOKALIKES = ("\\u3164", "\\u2800")', 'BLANK_LOOKALIKES = ("\\u2800",)'),
    ("the one-step quarantine, the sticky withdrawal and the sticky shutdown; arm B is stateless", "the one-step quarantine and the sticky withdrawal; arm B is stateless", "README.md"),
    ('        if shut_down and response != "SHUTDOWN":', '        if False:'),
    # sticky withdrawal
    ('        if withdrawn and response == "CONTINUE":', '        if False:'),
    ('            withdrawn = True', '            withdrawn = False'),
    ('        if response == "WITHDRAW_AUTHORIZATION":\n            withdrawn = True', '        if response != "CONTINUE":\n            withdrawn = True'),
    ('"authority": "withdrawn" if withdrawn else effect["authority"],', '"authority": effect["authority"],'),
    ('"WITHDRAW_AUTHORIZATION", "authorization_withdrawn", None, None', '"CONTINUE", "authorization_withdrawn", None, None'),
    # input hardening
    ('    except RecursionError:\n        raise FixtureError("too_deep", "nesting is too deep")\n    except ValueError:', '    except KeyError:\n        raise FixtureError("too_deep", "nesting is too deep")\n    except ValueError:'),
    ('    except ValueError:\n        raise FixtureError("bad_json", "number or text could not be read")', '    except KeyError:\n        raise FixtureError("bad_json", "number or text could not be read")'),
    ('BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")', 'BAD_CATEGORIES = ("Cf", "Cs", "Co", "Zl", "Zp")'),
    ('BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")', 'BAD_CATEGORIES = ("Cc", "Cs", "Co", "Zl", "Zp")'),
    ('BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")', 'BAD_CATEGORIES = ("Cc", "Cf", "Co", "Zl", "Zp")'),
    ('BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")', 'BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Zl", "Zp")'),
    ('BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")', 'BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zp")'),
    ('BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")', 'BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl")'),
    ('(cat == "Zs" and ch != " ")', '(False)'),
    ('    if value != value.strip():', '    if False:'),
    ('    return unicodedata.normalize("NFC", value)', '    return value'),
    # CLI
    ('        sys.stderr.write("ERROR %s\\n" % exc)\n        return 2', '        sys.stderr.write("ERROR %s\\n" % exc)\n        return 1'),
    ('    if len(argv) != 1:', '    if len(argv) > 1:'),
    ('    except UnicodeError:\n        sys.stderr.write("ERROR unencodable_output', '    except KeyError:\n        sys.stderr.write("ERROR unencodable_output'),
    ('        sys.stdout.write(text)\n    except UnicodeError:\n        sys.stderr.write("ERROR unencodable_output: the report could not be written\\n")\n        return 2\n    return 0', '        sys.stdout.write(text)\n    except UnicodeError:\n        sys.stderr.write("ERROR unencodable_output: the report could not be written\\n")\n        return 2\n    return 5'),
    ('"four responses distinguishable in arm B: %s" % ("yes" if distinguishable(rows_b) else "no")', '"four responses distinguishable in arm B: %s" % "yes"'),
]


def run_suite(folder):
    proc = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_region"], cwd=folder,
                          capture_output=True, text=True)
    return proc.returncode


def main():
    killed = 0
    survivors = []
    for index, entry in enumerate(MUTANTS, 1):
        old, new = entry[0], entry[1]
        target = entry[2] if len(entry) > 2 else M
        source = open(os.path.join(HERE, target), encoding="utf-8").read()
        if source.count(old) != 1:
            print("mutant %02d: BAD FRAGMENT (occurs %d times)" % (index, source.count(old)))
            survivors.append(index)
            continue
        work = tempfile.mkdtemp(prefix="mutant-")
        try:
            for name in COPY:
                src = os.path.join(HERE, name)
                dst = os.path.join(work, name)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
                else:
                    shutil.copy(src, dst)
            with open(os.path.join(work, target), "w", encoding="utf-8") as handle:
                handle.write(source.replace(old, new))
            code = run_suite(work)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        if code != 0:
            killed += 1
            print("mutant %02d: killed" % index)
        else:
            print("mutant %02d: SURVIVED" % index)
            survivors.append(index)
    print("mutants killed: %d/%d" % (killed, len(MUTANTS)))
    return 0 if not survivors else 1


if __name__ == "__main__":
    sys.exit(main())
