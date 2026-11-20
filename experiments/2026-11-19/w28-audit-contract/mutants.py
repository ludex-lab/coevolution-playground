"""Mutation self-check for w28-audit-contract (stdlib only).

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
COPY = ("audit_contract.py", "test_audit_contract.py", "demo.py", "mutants.py", "README.md", "evidence.json", "fixtures")
M = "audit_contract.py"

MUTANTS = [
    # the headline mutants: one contract is not enough, the weights may not change, no post-hoc test, no dropped range
    ("headline", r'        if c not in ran:', r'        if False:'),
    ("headline", r'    for c in decl["contracts"]:' + "\n" + r'        if c not in ran:', r'    for c in decl["contracts"][:1]:' + "\n" + r'        if c not in ran:'),
    ("headline", r'        if r["weights_text"].encode("utf-8") != decl["weights_text"].encode("utf-8"):', r'        if False:'),
    ("headline", r'        if name not in declared:', r'        if False:'),
    ("headline", r'    decision = combine([t["outcome"] for t in tests])', r'    decision = "STABLE_PASS" if views[decl["contracts"][0]] == "PASS" else "STABLE_FAIL"'),
    ("headline", r'            "range": {"min": _frac(min(stats)), "max": _frac(max(stats))},', r'            "range": {"min": _frac(stats[0]), "max": _frac(stats[0])},'),
    ("headline", r'        "single_contract_views": views, "tests": tests,', r'        "single_contract_views": {}, "tests": tests,'),
    # byte comparison, not a normalised or numeric one
    ("bytes", r'        if r["weights_text"].encode("utf-8") != decl["weights_text"].encode("utf-8"):', r'        if r["weights_text"].strip() != decl["weights_text"].strip():'),
    ("bytes", r'        if r["weights_text"].encode("utf-8") != decl["weights_text"].encode("utf-8"):', r'        if parse_weights(r["weights_text"]) != decl["weights"]:'),
    ("bytes", r'        if r["weights_text"].encode("utf-8") != decl["weights_text"].encode("utf-8"):', r'        if r["weights_text"].lower() != decl["weights_text"].lower():'),
    ("bytes", r'        if r["weights_text"].encode("utf-8") != decl["weights_text"].encode("utf-8"):', r'        if r["weights_text"].replace(" ", "") != decl["weights_text"].replace(" ", ""):'),
    ("bytes", r'        if r["weights_text"].encode("utf-8") != decl["weights_text"].encode("utf-8"):', r'        if r["weights_text"][:5] != decl["weights_text"][:5]:'),
    ("bytes", r'        if r["weights_text"].encode("utf-8") != decl["weights_text"].encode("utf-8"):' + "\n" + r'            return ("weights_changed"', r'        if r["weights_text"].encode("utf-8") != decl["weights_text"].encode("utf-8"):' + "\n" + r'            return ("threshold_changed"'),
    # order, presence and equality of the declared items
    ("seq", r'    if not decl["seq"] < scoring["seq"]:', r'    if not decl["seq"] <= scoring["seq"]:'),
    ("seq", r'    if not decl["seq"] < scoring["seq"]:', r'    if False:'),
    ("seq", r'    if not decl["seq"] < scoring["seq"]:', r'    if not decl["seq"] > scoring["seq"]:'),
    ("seq", r'    if decl is None:' + "\n" + r'        return ("no_declaration"', r'    if False:' + "\n" + r'        return ("no_declaration"'),
    ("contracts", r'        if c not in decl["contracts"]:', r'        if False:'),
    ("contracts", r'            return ("contract_missing", "declared contract %s was not run" % c)', r'            return ("contract_not_declared", "declared contract %s was not run" % c)'),
    ("contracts", r'            return ("contract_not_declared", "contract %s was run but not declared" % c)', r'            return ("contract_missing", "contract %s was run but not declared" % c)'),
    ("threshold", r'    if scoring["threshold"] != decl["threshold"]:', r'    if False:'),
    ("threshold", r'    if scoring["threshold"] != decl["threshold"]:', r'    if scoring["threshold"] < decl["threshold"]:'),
    ("threshold", r'    if scoring["threshold"] != decl["threshold"]:', r'    if scoring["threshold"] > decl["threshold"]:'),
    ("groups", r'    if scoring["groups"] != decl["groups"]:', r'    if False:'),
    ("groups", r'    if scoring["groups"] != decl["groups"]:', r'    if sorted(scoring["groups"]) != sorted(decl["groups"]):'),
    ("groups", r'    if scoring["groups"] != decl["groups"]:', r'    if scoring["groups"][:1] != decl["groups"][:1]:'),
    ("tests", r'        if name not in used:', r'        if False:'),
    ("tests", r'        if used[name] != declared[name]:', r'        if False:'),
    ("tests", r'        if used[name] != declared[name]:', r'        if used[name] > declared[name]:'),
    ("tests", r'        if used[name] != declared[name]:', r'        if used[name] < declared[name]:'),
    ("tests", r'            return ("post_hoc_test", "test %s was not declared before scoring" % name)', r'            return ("test_changed", "test %s was not declared before scoring" % name)'),
    ("tests", r'            return ("test_missing", "declared test %s was not scored" % name)', r'            return ("post_hoc_test", "declared test %s was not scored" % name)'),
    ("tests", r'    declared = dict((t["name"], t["bound"]) for t in decl["tests"])', r'    declared = dict((t["name"], t["bound"]) for t in decl["tests"][:1])'),
    ("tests", r'    used = dict((t["name"], t["bound"]) for t in scoring["tests"])', r'    used = dict((t["name"], t["bound"]) for t in scoring["tests"][:1])'),
    # contracts
    ("dot", r'        for p in reversed(products):', r'        for p in products:'),
    ("dot", r'            if i % 2 == 0:', r'            if i % 3 == 0:'),
    ("dot", r'        result = even + odd', r'        result = even'),
    ("dot", r'        result = math.fsum(products)', r'        result = math.fsum(products[:-1])'),
    ("dot", r'    elif contract == "fsum":', r'    elif True:'),
    ("dot", r'        raise AuditError("unknown_contract", "unknown contract %s" % _esc(contract))', r'        result = 0.0'),
    ("dot", r'    products = [w * v for w, v in zip(weights, x)]', r'    products = [w * v for w, v in zip(weights, x)][::-1]'),
    ("dot", r'    if not math.isfinite(result):', r'    if False:'),
    ("dot", r'        except (OverflowError, ValueError):', r'        except KeyError:'),
    ("dot", r'        except (OverflowError, ValueError):', r'        except OverflowError:'),
    ("dot", r'        except (OverflowError, ValueError):', r'        except ValueError:'),
    ("validate", r'    except UnicodeEncodeError:', r'    except KeyError:'),
    ("validate", r'        value.encode("utf-8")' + "\n" + r'    except UnicodeEncodeError:', r'        value.encode("utf-8", "surrogatepass")' + "\n" + r'    except UnicodeEncodeError:'),
    ("dot", r'        acc = 0.0' + "\n" + r'        for p in products:' + "\n" + r'            acc += p' + "\n" + r'        result = acc', r'        result = math.fsum(products)'),
    # selection and statistics
    ("select", r'if dot(c, decl["weights"], r["x"]) > decl["threshold"])', r'if dot(c, decl["weights"], r["x"]) >= decl["threshold"])'),
    ("select", r'if dot(c, decl["weights"], r["x"]) > decl["threshold"])', r'if dot(c, decl["weights"], r["x"]) < decl["threshold"])'),
    ("select", r'if dot(c, decl["weights"], r["x"]) > decl["threshold"])', r'if dot("ltr", decl["weights"], r["x"]) > decl["threshold"])'),
    ("stats", r'    if name == "dp_gap":' + "\n" + r'        return abs(rate_a - rate_b)', r'    if name == "dp_gap":' + "\n" + r'        return rate_a - rate_b'),
    ("stats", r'    return Fraction(1) if high == 0 else low / high', r'    return Fraction(0) if high == 0 else low / high'),
    ("stats", r'    return Fraction(1) if high == 0 else low / high', r'    return Fraction(1) if high == 0 else high / low'),
    ("stats", r'    low, high = min(rate_a, rate_b), max(rate_a, rate_b)', r'    low, high = rate_a, rate_b'),
    ("stats", r'    return stat <= bound if name == "dp_gap" else stat >= bound', r'    return stat < bound if name == "dp_gap" else stat >= bound'),
    ("stats", r'    return stat <= bound if name == "dp_gap" else stat >= bound', r'    return stat <= bound if name == "dp_gap" else stat > bound'),
    ("stats", r'    return stat <= bound if name == "dp_gap" else stat >= bound', r'    return stat >= bound if name == "dp_gap" else stat <= bound'),
    ("stats", r'    size = {ga: sum(1 for r in records if r["group"] == ga), gb: sum(1 for r in records if r["group"] == gb)}', r'    size = {ga: len(records), gb: len(records)}'),
    ("stats", r'    ga, gb = decl["groups"]', r'    ga, gb = decl["groups"][0], decl["groups"][0]'),
    ("outcome", r'        outcome = "pass_all_contracts" if flags == {True} else "fail_all_contracts" if flags == {False} else "contract_dependent"', r'        outcome = "pass_all_contracts" if True in flags else "fail_all_contracts"'),
    ("outcome", r'        outcome = "pass_all_contracts" if flags == {True} else "fail_all_contracts" if flags == {False} else "contract_dependent"', r'        outcome = "pass_all_contracts" if flags == {True} else "contract_dependent"'),
    ("combine", r'    if "contract_dependent" in outcomes:' + "\n" + r'        return "CONTRACT_DEPENDENT"' + "\n" + r'    if "fail_all_contracts" in outcomes:', r'    if "fail_all_contracts" in outcomes:' + "\n" + r'        return "STABLE_FAIL"' + "\n" + r'    if "contract_dependent" in outcomes:' + "\n" + r'        return "CONTRACT_DEPENDENT"' + "\n" + r'    if False:'),
    ("combine", r'    if "fail_all_contracts" in outcomes:' + "\n" + r'        return "STABLE_FAIL"', r'    if "fail_all_contracts" in outcomes and "pass_all_contracts" not in outcomes:' + "\n" + r'        return "STABLE_FAIL"'),
    ("combine", r'    if "contract_dependent" in outcomes:' + "\n" + r'        return "CONTRACT_DEPENDENT"' + "\n" + r'    if "fail_all', r'    if outcomes.count("contract_dependent") > 1:' + "\n" + r'        return "CONTRACT_DEPENDENT"' + "\n" + r'    if "fail_all'),
    ("report", r'    differing = [r["id"] for r in records if r["id"] in union and r["id"] not in common]', r'    differing = []'),
    ("report", r'    differing = [r["id"] for r in records if r["id"] in union and r["id"] not in common]', r'    differing = [r["id"] for r in records if r["id"] in union]'),
    ("report", r'        "sampling_uncertainty": "not_computed",', r'        "sampling_uncertainty": "computed",'),
    ("report", r'        "contracts": list(decl["contracts"]), "weights_text": decl["weights_text"], "weights_identical": True,', r'        "contracts": list(decl["contracts"]), "weights_text": decl["weights_text"], "weights_identical": False,'),
    ("report", r'    totals = {d: sum(1 for r in rows if r["decision"] == d) for d in DECISIONS}', r'    totals = {d: sum(1 for r in rows if r["decision"] == d and d != "DENY") for d in DECISIONS}'),
    ("report", r'    for c in decl["contracts"]:' + "\n" + r'        chosen', r'    for c in decl["contracts"][:-1]:' + "\n" + r'        chosen'),
    # validation
    ("validate", r'    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:', r'    if root["fixture_version"] != FIXTURE_VERSION:'),
    ("validate", r'    if type(root["on_expiry"]) is not str or root["on_expiry"] != "DENY":', r'    if root["on_expiry"] not in ("DENY", "HOLD", "ESCALATE"):'),
    ("validate", r'    if len(contracts) < 2:', r'    if len(contracts) < 1:'),
    ("validate", r'    if len(groups) != 2:', r'    if len(groups) < 2:'),
    ("validate", r'    if type(value) is not int or not 0 <= value <= 10 ** 6:', r'    if not isinstance(value, int) or not 0 <= value <= 10 ** 6:'),
    ("validate", r'    if type(value) is not int or not 0 <= value <= 10 ** 6:', r'    if type(value) is not int or not 1 <= value <= 10 ** 6:'),
    ("validate", r'    if type(value) not in (int, float):', r'    if not isinstance(value, (int, float)):'),
    ("validate", r'        raise AuditError("bad_number", "%s is too large" % where)' + "\n" + r'    if not math.isfinite(f):', r'        raise AuditError("bad_number", "%s is too large" % where)' + "\n" + r'    if False:'),
    ("validate", r'        f = float(token)' + "\n" + r'        if not math.isfinite(f):', r'        f = float(token)' + "\n" + r'        if False:'),
    ("validate", r'    if not 0 <= b <= 1:', r'    if not 0 <= b:'),
    ("validate", r'    if not 0 <= b <= 1:', r'    if not 0 < b <= 1:'),
    ("validate", r'    if type(value) is not str or ID_RE.fullmatch(value) is None:', r'    if type(value) is not str or ID_RE.match(value) is None:'),
    ("validate", r'TOKEN_RE = re.compile(r"-?[0-9]{1,30}(\.[0-9]{1,30})?([eE][+-]?[0-9]{1,3})?")', r'TOKEN_RE = re.compile(r"-?\d{1,30}(\.\d{1,30})?([eE][+-]?\d{1,3})?")'),
    ("validate", r'        if TOKEN_RE.fullmatch(token) is None:', r'        if TOKEN_RE.match(token) is None:'),
    ("validate", r'    if len(set(items)) != len(items):', r'    if False:'),
    ("validate", r'    _unique(contracts, where + ".contracts")', r'    pass'),
    ("validate", r'    _unique([r["contract"] for r in runs], where + ".runs")', r'    pass'),
    ("validate", r'        _unique([r["id"] for r in records], where + ".records")', r'        pass'),
    ("validate", r'    _unique([a["id"] for a in audits], "audits")', r'    pass'),
    ("validate", r'                if r["group"] not in decl["groups"]:', r'                if False:'),
    ("validate", r'                if len(r["x"]) != len(decl["weights"]):', r'                if False:'),
    ("validate", r'                if not any(r["group"] == g for r in records):', r'                if False:'),
    ("validate", r'    unknown = sorted(set(value) - set(keys))', r'    unknown = []'),
    ("validate", r'    missing = [k for k in keys if k not in value]', r'    missing = []'),
    ("validate", r'    if not 1 <= len(tokens) <= MAX_WEIGHTS:', r'    if False:'),
    ("validate", r'    if type(value) is not str or len(value) > MAX_TEXT:', r'    if type(value) is not str:'),
    ("validate", r'    if type(value) is not str or value not in CONTRACTS:', r'    if type(value) is not str:'),
    ("validate", r'    if type(spec["name"]) is not str or spec["name"] not in TESTS:', r'    if type(spec["name"]) is not str:'),
    ("validate", r'        if key in out:', r'        if False:'),
    ("validate", r'        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)', r'        return json.loads(text, object_pairs_hook=_pairs)'),
    ("validate", r'    except (ValueError, RecursionError):', r'    except ValueError:'),
    ("validate", r'    bound = _bound(spec["bound"], where + ".bound")', r'    bound = Fraction(spec["bound"])'),
    ("validate", r'    b = Fraction(value) if type(value) is int else Fraction(repr(value))', r'    b = Fraction(value)'),
    ("validate", r'    return json.dumps(str(value), ensure_ascii=True)', r'    return json.dumps(str(value), ensure_ascii=False)'),
    # cli
    ("cli", r'    return 2 if any(r["decision"] == "DENY" for r in result["rows"]) else 0', r'    return 0'),
    ("cli", r'    return 2 if any(r["decision"] == "DENY" for r in result["rows"]) else 0', r'    return 2 if any(r["decision"] == "DENY" for r in result["rows"][:1]) else 0'),
    ("cli", r'    return 2 if any(r["decision"] == "DENY" for r in result["rows"]) else 0', r'    return 2 if all(r["decision"] == "DENY" for r in result["rows"]) else 0'),
    ("cli", r'        sys.stderr.write("ERROR %s: %s\n" % (e.code, e.detail))', r'        sys.stdout.write("ERROR %s: %s\n" % (e.code, e.detail))'),
    ("cli", r'        sys.stderr.write("ERROR %s: %s\n" % (e.code, e.detail))', r'        sys.stderr.write("DENY %s: %s\n" % (e.code, e.detail))'),
    ("cli", r'        sys.stderr.write("ERROR usage: audit_contract.py FIXTURE.json\n")' + "\n" + r'        return 2', r'        sys.stderr.write("ERROR usage: audit_contract.py FIXTURE.json\n")' + "\n" + r'        return 1'),
    ("cli", r'    except UnicodeDecodeError:', r'    except KeyError:'),
    ("cli", r'    except OSError:', r'    except KeyError:'),
    ("cli", r'        with open(path, encoding="utf-8") as fh:', r'        with open(path, encoding="latin-1") as fh:'),
]


def run_suite(folder):
    res = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q", "test_audit_contract"], cwd=folder,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return res.returncode


def main():
    base = tempfile.mkdtemp(prefix="w28-mutants-")
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
                print("mutant %02d %-9s fragment occurs %d times" % (idx, group, source.count(old)))
                return 1
            folder = os.path.join(base, "m%02d" % idx)
            shutil.copytree(clean, folder)
            with open(os.path.join(folder, M), "w", encoding="utf-8") as handle:
                handle.write(source.replace(old, new))
            killed = run_suite(folder) != 0
            survivors += 0 if killed else 1
            print("mutant %02d %-9s %s" % (idx, group, "killed" if killed else "SURVIVED"))
            shutil.rmtree(folder)
        total = len(MUTANTS)
        print("killed %d/%d" % (total - survivors, total))
        return 0 if survivors == 0 else 1
    finally:
        shutil.rmtree(base)


if __name__ == "__main__":
    sys.exit(main())
