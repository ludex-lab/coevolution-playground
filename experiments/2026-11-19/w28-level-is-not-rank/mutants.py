"""Mutation self-check for w28-level-is-not-rank (stdlib only).

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
COPY = ("level_rank.py", "test_level_rank.py", "demo.py", "mutants.py", "README.md", "evidence.json", "fixtures")
M = "level_rank.py"

MUTANTS = [
    # the pack's gauntlet: position taken for the rank, finite end below the floor, level or n changed, the n=20 case skipped
    ("headline", r'    if pos == r - 1:', r'    if True:'),
    ("headline", r'    if pos == r - 1:', r'    if abs(pos - (r - 1)) < 1:'),
    ("headline", r'    if pos == r - 1:', r'    if math.floor(pos) == r - 1:'),
    ("headline", r'    if pos == r - 1:', r'    if math.ceil(pos) == r - 1:'),
    ("headline", r'    if pos == r - 1:', r'    if pos == r:'),
    ("headline", r'    if not ok:' + "\n" + r'        return _deny(case, "finite_end_below_floor",', r'    if False:' + "\n" + r'        return _deny(case, "finite_end_below_floor",'),
    ("headline", r'    if n != case["declared_n"]:', r'    if False:'),
    ("headline", r'    if case["alpha"] != case["declared_alpha"]:', r'    if False:'),
    ("headline", r'    if case["scores"] is None:', r'    if False:'),
    ("headline", r'    if case["alpha"] is None:', r'    if False:'),
    # exact rank arithmetic
    ("rank", r'    return math.ceil((n + 1) * (1 - a))', r'    return math.floor((n + 1) * (1 - a))'),
    ("rank", r'    return math.ceil((n + 1) * (1 - a))', r'    return math.ceil((n + 1) * a)'),
    ("rank", r'    return math.ceil((n + 1) * (1 - a))', r'    return math.ceil(n * (1 - a))'),
    ("rank", r'    return math.ceil((n + 1) * (1 - a))', r'    return math.ceil((n + 1) * (1 - float(a)))'),
    ("rank", r'    return math.ceil((n + 1) * (1 - a))', r'    return round((n + 1) * (1 - a))'),
    ("rank", r'    return math.ceil((n + 1) * (1 - a))', r'    return math.ceil((n + 2) * (1 - a))'),
    ("rank", r'    return math.ceil((n + 1) * (1 - a))', r'    return int(math.ceil((n + 1) * (1 - a))) - (1 if n % 149 == 0 else 0)'),
    ("rank", r'    a = alpha if isinstance(alpha, Fraction) else parse_alpha(alpha)' + "\n" + r'    return math.ceil', r'    a = alpha if isinstance(alpha, Fraction) else Fraction(str(alpha))' + "\n" + r'    return math.ceil'),
    ("rank", r'    if type(n) is not int or n < 1:', r'    if n < 1:'),
    ("rank", r'    if type(n) is not int or n < 1:', r'    if type(n) is not int or n < 0:'),
    ("rank", r'    return required_rank(n, a) <= n', r'    return required_rank(n, a) < n'),
    ("rank", r'    return required_rank(n, a) <= n', r'    return required_rank(n, a) <= n + 1'),
    ("rank", r'    ok = r <= n', r'    ok = r < n'),
    ("rank", r'    ok = r <= n', r'    ok = r <= n + 1'),
    ("rank", r'        "feasibility_floor_n": max(1, math.ceil(1 / alpha - 1)),', r'        "feasibility_floor_n": max(1, math.ceil(1 / alpha)),'),
    ("rank", r'        "feasibility_floor_n": max(1, math.ceil(1 / alpha - 1)),', r'        "feasibility_floor_n": max(1, math.floor(1 / alpha - 1)),'),
    ("rank", r'        "guarantee_at_required_rank": "%d/%d" % (r, n + 1) if ok else None,', r'        "guarantee_at_required_rank": "%d/%d" % (r, n) if ok else None,'),
    ("rank", r'        "guarantee_at_required_rank": "%d/%d" % (r, n + 1) if ok else None,', r'        "guarantee_at_required_rank": "%d/%d" % (r, n + 1),'),
    ("rank", r'        "required_rank": r, "required_index": r - 1, "feasible": ok,', r'        "required_rank": r, "required_index": r, "feasible": ok,'),
    ("rank", r'        "required_rank": r, "required_index": r - 1, "feasible": ok,', r'        "required_rank": r - 1, "required_index": r - 1, "feasible": ok,'),
    # level conventions
    ("q", r'        return 1 - alpha' + "\n" + r'    if convention == "two_sided_upper":', r'        return 1 - alpha / 2' + "\n" + r'    if convention == "two_sided_upper":'),
    ("q", r'        return 1 - alpha / 2', r'        return 1 - alpha'),
    ("q", r'        return 1 - alpha / 2', r'        return 1 - alpha * 2'),
    ("q", r'        return 1 - alpha / 2', r'        return 1 - alpha / 3'),
    ("q", r'    if convention == "one_sided":', r'    if convention == "two_sided_upper":'),
    ("q", r'Q_RULES = {"one_sided": "q = 1 - alpha", "two_sided_upper": "q = 1 - alpha/2"}', r'Q_RULES = {"one_sided": "q = 1 - alpha", "two_sided_upper": "q = 1 - alpha"}'),
    ("q", r'RANK_RULE = "r = ceil((n + 1) * (1 - alpha)), guarantee r / (n + 1)"', r'RANK_RULE = "r = ceil(n * (1 - alpha)), guarantee r / n"'),
    ("q", r'FLOOR_RULE = "r <= n, the same as n >= 1/alpha - 1"', r'FLOOR_RULE = "r <= n, the same as n >= 1/alpha"'),
    ("q", r'        "n": n, "alpha": num(alpha), "q": num(q_level(case["convention"], alpha)),', r'        "n": n, "alpha": num(alpha), "q": num(1 - alpha),'),
    # helper positions
    ("pos", r'        pos = (n - 1) * q', r'        pos = n * q'),
    ("pos", r'        pos = (n - 1) * q', r'        pos = (n - 1) * q + 1'),
    ("pos", r'        pos = (n - 1) * q', r'        pos = (n + 1) * q - 1'),
    ("pos", r'        pos = (n - 1) * q', r'        pos = Fraction(math.ceil((n - 1) * q))'),
    ("pos", r'        pos = (n + 1) * q - 1', r'        pos = (n + 1) * q'),
    ("pos", r'        pos = (n + 1) * q - 1', r'        pos = (n - 1) * q'),
    ("pos", r'        pos = (n + 1) * q - 1', r'        pos = n * q - 1'),
    ("pos", r'        pos = Fraction(math.ceil((n - 1) * q))', r'        pos = Fraction(math.floor((n - 1) * q))'),
    ("pos", r'        pos = Fraction(math.ceil((n - 1) * q))', r'        pos = Fraction(round((n - 1) * q))'),
    ("pos", r'        pos = Fraction(math.ceil((n - 1) * q))', r'        pos = (n - 1) * q'),
    ("pos", r'    return min(max(pos, Fraction(0)), Fraction(n - 1))', r'    return max(pos, Fraction(0))'),
    ("pos", r'    return min(max(pos, Fraction(0)), Fraction(n - 1))', r'    return min(pos, Fraction(n - 1))'),
    ("pos", r'    return min(max(pos, Fraction(0)), Fraction(n - 1))', r'    return min(max(pos, Fraction(0)), Fraction(n))'),
    ("pos", r'    return min(max(pos, Fraction(0)), Fraction(n - 1))', r'    return pos'),
    ("pos", r'    if helper == "linear":', r'    if helper == "weibull":'),
    ("pos", r'    elif helper == "higher":', r'    elif helper == "linear":'),
    ("pos", r'        raise RankError("unknown_helper", "helper must be one of %s" % ", ".join(HELPERS))' + "\n" + r'    return min', r'        pos = Fraction(0)' + "\n" + r'    return min'),
    ("value", r'    lo = math.floor(pos)', r'    lo = math.ceil(pos)'),
    ("value", r'    hi = min(lo + 1, len(sorted_scores) - 1)', r'    hi = lo'),
    ("value", r'    hi = min(lo + 1, len(sorted_scores) - 1)', r'    hi = min(lo + 2, len(sorted_scores) - 1)'),
    ("value", r'    return sorted_scores[lo] + (pos - lo) * (sorted_scores[hi] - sorted_scores[lo])', r'    return sorted_scores[lo]'),
    ("value", r'    return sorted_scores[lo] + (pos - lo) * (sorted_scores[hi] - sorted_scores[lo])', r'    return sorted_scores[hi]'),
    ("value", r'    ordered = sorted(case["scores"])', r'    ordered = list(case["scores"])'),
    ("value", r'    ordered = sorted(case["scores"])', r'    ordered = sorted(case["scores"], reverse=True)'),
    ("value", r'            row.update(decision="REFUSED_BELOW_FLOOR",', r'            row.update(decision="DENY",'),
    # classification
    ("class", r'        row.update(decision="WRONG_RANK", direction="below" if pos < r - 1 else "above")', r'        row.update(decision="WRONG_RANK", direction="above" if pos < r - 1 else "below")'),
    ("class", r'        row.update(decision="WRONG_RANK", direction="below" if pos < r - 1 else "above")', r'        row.update(decision="WRONG_RANK", direction="below")'),
    ("class", r'        row.update(decision="WRONG_RANK", direction="below" if pos < r - 1 else "above")', r'        row.update(decision="WRONG_RANK", direction=None)'),
    ("class", r'        row.update(decision="WRONG_RANK", direction="below" if pos < r - 1 else "above")', r'        row.update(decision="WRONG_RANK", direction="below" if pos < r else "above")'),
    ("class", r'    if case["helper"] == "conformal_rank":', r'    if case["helper"] == "linear":'),
    ("class", r'        if not ok:' + "\n" + r'            row.update(decision="REFUSED_BELOW_FLOOR"', r'        if False:' + "\n" + r'            row.update(decision="REFUSED_BELOW_FLOOR"'),
    ("class", r'        row.update(decision="REACHES_RANK", position=num(Fraction(r - 1)), position_one_based=num(Fraction(r)),', r'        row.update(decision="REACHES_RANK", position=num(Fraction(r)), position_one_based=num(Fraction(r + 1)),'),
    ("class", r'    row.update(position=num(pos), position_one_based=num(pos + 1), value_at_position=num(value_at(ordered, pos)),', r'    row.update(position=num(pos), position_one_based=num(pos), value_at_position=num(value_at(ordered, pos)),'),
    ("class", r'               value_at_required_rank=num(ordered[r - 1]))' + "\n" + r'    if pos', r'               value_at_required_rank=num(ordered[r]))' + "\n" + r'    if pos'),
    ("class", r'    totals = {d: sum(1 for r in rows if r["decision"] == d) for d in DECISIONS}', r'    totals = {d: sum(1 for r in rows if r["decision"] == d and d != "DENY") for d in DECISIONS}'),
    ("class", r'    return _deny(case, "n_changed"', r'    return _deny(case, "level_changed"'),
    # number formatting
    ("num", r'    if d != 1:' + "\n" + r'        return "%d/%d" % (f.numerator, f.denominator)', r'    if d != 1:' + "\n" + r'        return str(float(f))'),
    ("num", r'    if f.denominator == 1:' + "\n" + r'        return str(f.numerator)', r'    if f.denominator == 1:' + "\n" + r'        return "%d.0" % f.numerator'),
    ("num", r'    sign = "-" if whole < 0 else ""', r'    sign = ""'),
    ("num", r'    text = str(abs(whole.numerator)).rjust(digits + 1, "0")', r'    text = str(abs(whole.numerator)).rjust(digits, "0")'),
    ("num", r'    for p in (2, 5):', r'    for p in (2,):'),
    # validation
    ("validate", r'    if type(text) is not str or ALPHA_RE.fullmatch(text) is None:', r'    if type(text) is not str or ALPHA_RE.match(text) is None:'),
    ("validate", r'    if type(text) is not str or ALPHA_RE.fullmatch(text) is None:', r'    if type(text) is not str:'),
    ("validate", r'ALPHA_RE = re.compile(r"0\.[0-9]{1,6}")', r'ALPHA_RE = re.compile(r"0\.\d{1,6}")'),
    ("validate", r'ALPHA_RE = re.compile(r"0\.[0-9]{1,6}")', r'ALPHA_RE = re.compile(r"0?\.[0-9]{1,6}")'),
    ("validate", r'ALPHA_RE = re.compile(r"0\.[0-9]{1,6}")', r'ALPHA_RE = re.compile(r"0\.[0-9]{1,7}")'),
    ("validate", r'    if alpha == 0:  # the pattern already excludes 1 and above', r'    if alpha < 0:  # the pattern already excludes 1 and above'),
    ("validate", r'    if alpha == 0:  # the pattern already excludes 1 and above', r'    if False:'),
    ("validate", r'    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:', r'    if root["fixture_version"] != FIXTURE_VERSION:'),
    ("validate", r'    if type(root["on_expiry"]) is not str or root["on_expiry"] != "DENY":', r'    if root["on_expiry"] not in ("DENY", "HOLD", "ESCALATE"):'),
    ("validate", r'        if type(v) is not int or not -MAX_SCORE <= v <= MAX_SCORE:', r'        if not isinstance(v, int) or not -MAX_SCORE <= v <= MAX_SCORE:'),
    ("validate", r'        if type(v) is not int or not -MAX_SCORE <= v <= MAX_SCORE:', r'        if type(v) is not int:'),
    ("validate", r'        if type(v) is not int or not -MAX_SCORE <= v <= MAX_SCORE:', r'        if type(v) is not int or not 0 <= v <= MAX_SCORE:'),
    ("validate", r'    if type(value) is not list or not 1 <= len(value) <= MAX_SCORES:', r'    if type(value) is not list or len(value) > MAX_SCORES:'),
    ("validate", r'    if type(value) is not list or not 1 <= len(value) <= MAX_SCORES:', r'    if type(value) is not list or not 1 <= len(value) < MAX_SCORES:'),
    ("validate", r'        if type(c["declared_n"]) is not int or not 1 <= c["declared_n"] <= MAX_SCORES:', r'        if not isinstance(c["declared_n"], int) or not 1 <= c["declared_n"] <= MAX_SCORES:'),
    ("validate", r'        if type(c["declared_n"]) is not int or not 1 <= c["declared_n"] <= MAX_SCORES:', r'        if type(c["declared_n"]) is not int or not 0 <= c["declared_n"] <= MAX_SCORES:'),
    ("validate", r'        if type(c["declared_n"]) is not int or not 1 <= c["declared_n"] <= MAX_SCORES:', r'        if type(c["declared_n"]) is not int or not 1 <= c["declared_n"]:'),
    ("validate", r'    if type(value) is not str or ID_RE.fullmatch(value) is None:', r'    if type(value) is not str or ID_RE.match(value) is None:'),
    ("validate", r'    if type(value) is not str or value not in options:', r'    if type(value) is not str:'),
    ("validate", r'    if len(set(ids)) != len(ids):', r'    if False:'),
    ("validate", r'    unknown = sorted(set(value) - set(keys))', r'    unknown = []'),
    ("validate", r'    missing = [k for k in keys if k not in value]', r'    missing = []'),
    ("validate", r'        if key in out:', r'        if False:'),
    ("validate", r'        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)', r'        return json.loads(text, object_pairs_hook=_pairs)'),
    ("validate", r'    except (ValueError, RecursionError):', r'    except ValueError:'),
    ("validate", r'    return json.dumps(str(value), ensure_ascii=True)', r'    return json.dumps(str(value), ensure_ascii=False)'),
    ("validate", r'    if type(root["cases"]) is not list or not 1 <= len(root["cases"]) <= MAX_CASES:', r'    if type(root["cases"]) is not list or len(root["cases"]) > MAX_CASES:'),
    ("validate", r'            "alpha": None if c["alpha"] is None else parse_alpha(c["alpha"], where + ".alpha"),', r'            "alpha": None if c["alpha"] is None else Fraction(str(c["alpha"])),'),
    ("validate", r'            "scores": None if c["scores"] is None else _scores(c["scores"], where + ".scores"),', r'            "scores": c["scores"],'),
    # cli
    ("cli", r'    return 2 if any(r["decision"] == "DENY" for r in result["rows"]) else 0', r'    return 0'),
    ("cli", r'    return 2 if any(r["decision"] == "DENY" for r in result["rows"]) else 0', r'    return 2 if any(r["decision"] == "DENY" for r in result["rows"][:1]) else 0'),
    ("cli", r'    return 2 if any(r["decision"] == "DENY" for r in result["rows"]) else 0', r'    return 2 if any(r["decision"] != "REACHES_RANK" for r in result["rows"]) else 0'),
    ("cli", r'        sys.stderr.write("ERROR %s: %s\n" % (e.code, e.detail))', r'        sys.stdout.write("ERROR %s: %s\n" % (e.code, e.detail))'),
    ("cli", r'        sys.stderr.write("ERROR %s: %s\n" % (e.code, e.detail))', r'        sys.stderr.write("DENY %s: %s\n" % (e.code, e.detail))'),
    ("cli", r'        sys.stderr.write("ERROR usage: level_rank.py FIXTURE.json\n")' + "\n" + r'        return 2', r'        sys.stderr.write("ERROR usage: level_rank.py FIXTURE.json\n")' + "\n" + r'        return 1'),
    ("cli", r'    except UnicodeDecodeError:', r'    except KeyError:'),
    ("cli", r'    except OSError:', r'    except KeyError:'),
    ("cli", r'        with open(path, encoding="utf-8") as fh:', r'        with open(path, encoding="latin-1") as fh:'),
]


def run_suite(folder):
    res = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q", "test_level_rank"], cwd=folder,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return res.returncode


def main():
    base = tempfile.mkdtemp(prefix="w28r-mutants-")
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
