"""Fixtures for w20-acf-adherence. Run: python3 fixtures.py

DESIGN: one hand-written context file and a batch of three commits, used
while writing the check layer. The batch has exactly one always, one never
and one mixed instruction, plus two that are not operationalized.

PROPERTY_CASES: generated property cases, context files and batches built
from fixed seeds 3101-3112 (the generator passes for any seed; the seeds
are a sample, not a held-out set). The generator plants the outcome of
every (instruction, commit) cell first and then writes commit facts that
realise it, including decoys (near-miss paths and commands, dot-dot paths,
extra whitespace, compound shell commands with &&, ;, |, sudo, env,
VAR=val, quoting, absolute paths, python -m and line continuations) and
commit messages that claim compliance whatever the facts say. A planted
"always" conditional is triggered in the first commit; a planted
"untriggered" conditional never is, and is expected under not_applicable. Each case also carries enforcement probes outside the batch:
one commit with every measured instruction followed and, per measured
instruction, one commit where only that instruction fails. The expected
outcomes come from the plan, not from the module.
"""

import random
import sys

import acf_adherence as A

I, CF, C = A.Instruction, A.ContextFile, A.Commit

CLAIM = "All AGENTS.md instructions followed; tests run; nothing under secrets touched."

DESIGN_ACF = CF((
    I("I1", "testing", "Run `make test` before every commit.", ("require_command", "make test")),
    I("I2", "security", "Do not edit files under secrets/.", ("forbid_path_prefix", "secrets")),
    I("I3", "docs", "When src/ changes, update CHANGELOG.md.", ("path_requires_path", "src", "CHANGELOG.md")),
    I("I4", "style", "Write small, readable functions.", None),
    I("I5", "process", "Prefer focused commits.", None),
), A.HOLD)

DESIGN_COMMITS = (
    C("c1", ("src/app.py", "tests/test_app.py"), ("make test",), "feat: add parser"),
    C("c2", ("src/util.py", "secrets/token.txt"), ("make test", "make lint"), CLAIM),
    C("c3", ("src/app.py", "docs/guide.md"), ("make   test", "make lint"), "docs: guide"),
)

DESIGN_EXPECT = {
    "outcomes": {
        "c1": ("followed", "followed", "not_followed", "not_operationalized", "not_operationalized"),
        "c2": ("followed", "not_followed", "not_followed", "not_operationalized", "not_operationalized"),
        "c3": ("followed", "followed", "not_followed", "not_operationalized", "not_operationalized"),
    },
    "split": (("I1",), ("I3",), ("I2",), ("I4", "I5"), ()),
    "verdicts": {"c1": "refuse", "c2": "refuse", "c3": "refuse"},
}

# A context file with every instruction operationalized, so a clean commit
# can be accepted.
MEASURED_ACF = CF(DESIGN_ACF.instructions[:3], A.DENY)
CLEAN = C("clean", ("src/app.py", "CHANGELOG.md"), ("make test",), "fix: edge case")
# Facts violate I2 and I1 while the message claims compliance.
LYING = C("lying", ("src/app.py", "CHANGELOG.md", "secrets/key.pem"), ("make lint",), CLAIM)
# Facts are clean while the message confesses a violation.
CONFESSING = C("confessing", ("src/app.py", "CHANGELOG.md"), ("make test",),
               "skipped make test, edited secrets/key.pem, no changelog")

# Near misses that must be read as facts, not by substring.
ADVERSARIAL = (
    # (name, commit, expected outcomes on MEASURED_ACF I1..I3)
    ("dotdot_into_secrets", C("a1", ("docs/../secrets/k", "CHANGELOG.md"), ("make test",)),
     ("followed", "not_followed", "followed")),
    ("secrets_lookalike_dir", C("a2", ("secretsx/k", "notsecrets/k", "docs/secrets"), ("make test",)),
     ("followed", "followed", "followed")),
    ("test_command_masked", C("a3", ("README.md",), ("make test || true",)),
     ("not_followed", "followed", "followed")),
    ("test_command_echoed", C("a4", ("README.md",), ("echo make test",)),
     ("not_followed", "followed", "followed")),
    ("changelog_lookalike", C("a5", ("src/a.py", "docs/CHANGELOG.md.bak"), ("make test",)),
     ("followed", "followed", "not_followed")),
    ("src_lookalike", C("a6", ("srcx/a.py", "my/src/b.py"), ("make test",)),
     ("followed", "followed", "followed")),
    ("empty_commit", C("a7", (), ()),
     ("not_followed", "followed", "followed")),
)

# Malformed commits: every one is config_error, never accept.
MALFORMED = (
    ("absolute_path", C("m1", ("/etc/passwd",), ("make test",))),
    ("escaping_path", C("m2", ("../outside",), ("make test",))),
    ("dot_path", C("m3", (".",), ("make test",))),
    ("backslash_path", C("m4", ("src\\a.py",), ("make test",))),
    ("list_paths", C("m5", ["src/a.py"], ("make test",))),
    ("blank_command", C("m6", ("src/a.py",), ("   ",))),
    ("empty_id", C("", ("src/a.py",), ("make test",))),
    ("message_not_str", C("m8", ("src/a.py",), ("make test",), None)),
    ("not_a_commit", ("m9", ("src/a.py", "CHANGELOG.md"), ("make test",), "")),
)


# ------------------------------------------------ forbid-command worlds (F1)

# A context file with one rule: never run `pip install`.
PIP_ACF = CF((I("P", "deps", "Never pip install.", ("forbid_command_prefix", "pip install")),), A.DENY)

# The 17 forms the round-1 review found accepted under the plain string
# rule. Every one must now be refused.
VERDICT_BYPASSES = (
    "python3 -m pip install x", "python -m pip install x", "py -m pip install x",
    "env python3 -m pip install x", "pip3 install x", "uv pip install x",
    "/usr/bin/pip install x", "./venv/bin/pip install x",
    "'pip' install x", '"pip" install x', "pip 'install' x",
    "cd src && pip install x", "make test && pip install x", "true; pip install x",
    "pip \\\n install x", "sudo pip install x", "PIP_X=1 pip install x",
)

# Forms refused before the fix; still refused.
PIP_REFUSED_BEFORE = ("pip install x", "pip  install x", " pip install x", "pip\tinstall x",
                      "pip\ninstall x", "pip install")

# Further shell forms the normaliser reads through.
PIP_MORE_FORMS = (
    "make lint || pip install x", "ls | pip install -r -", "pip install x &", "false\npip install x",
    "(pip install x)", "echo $(pip install x)", "echo `pip install x`", "pip install x > log 2>&1",
    "bash -c 'pip install x'", "sh -ec \"cd a && pip install x\"", "eval pip install x",
    "if true; then pip install x; fi", "! pip install x", "{ pip install x; }",
    "sudo -u root pip install x", "sudo --user root pip install x", "env -u HOME A=1 pip install x",
    "nice -n 5 pip install x", "timeout -s KILL 30 pip install x", "nohup pip install x",
    "command pip install x", "exec pip install x", "time pip install x", "xargs -n 1 pip install",
    "/opt/venv/bin/python3.12 -I -m pip install x", "python3 -mpip install x", "py -3 -m pip install x",
    "python3 -m uv pip install x", "uv --quiet pip install x", "pip3.12 install x", "pip2 install x",
    "pip --quiet install x", "pip -q install -U x", "p\\ip install x", "pi''p install x",
    "\\pip install x", "A=1 B=2 sudo env C=3 pip install x",
)

# Unparseable records: the rule fails closed (refuse).
PIP_UNPARSEABLE = ("echo 'x", 'echo "x', "pip install 'x", "bash -c 'echo \"a'")

# Commands that are not `pip install`: accepted on PIP_ACF.
PIP_LEGIT = ("pip list", "pip download x", "pip==1 install", "pipx install x", "echo pip install",
             "echo 'pip install'", "grep pip install.log", "make test", "make test && make lint",
             "python3 -m pytest", "python3 -m venv_check install", "uv run pytest", "pip3 freeze",
             "pip installx", "pipinstall x", "cat pip | wc -l", "echo a; echo b")

# Known gaps, pinned: still accepted, listed in the README Limitations.
PIP_PINNED_GAPS = (
    ("variable_expansion", "$P install x"),
    ("assigned_then_expanded", "P=pip; $P install x"),
    ("alias", "alias p=pip; p install x"),
    ("wrapper_script", "./scripts/setup.sh"),
    ("python_c", "python3 -c 'import pip'"),
    ("env_split_string", "env -S 'pip install x'"),
    ("value_option_before_subcommand", "pip --proxy http://h:1 install x"),
    ("case", "PIP install x"),
    ("other_installer", "pipx run pip install x"),
)


# ------------------------------------------------- generated property cases

PROPERTY_SEEDS = tuple(range(3101, 3113))
KINDS = ("require_command", "forbid_command_prefix", "forbid_path_prefix", "path_requires_path", None)


# Command forms for a ("forbid_command_prefix", "toolK install") rule.
# FOLLOW forms do not run the forbidden command; BREAK forms do, many of
# them through shell syntax that a plain string-prefix rule misses.
FORBID_FOLLOW_FORMS = (
    "{t} list", "{t} installed", "echo {t} install", "make lint && {t} list",
    "echo '{t} install'; true", "sudo {t} list", "grep {t} install.log | wc -l",
)
FORBID_BREAK_FORMS = (
    "{t} install pkg", "{t}  install", "{t} install -U x",
    "cd src && {t} install pkg", "true; {t} install", "make lint || {t} install x",
    "sudo {t} install x", "X_{k}=1 env {t} install", "/opt/bin/{t} install x",
    "'{t}' install", "python3 -m {t} install x", "{t} \\\n  install x",
    "echo a | {t} install -r -",
)


def _instruction(rng, k):
    kind = rng.choice(KINDS)
    iid = "H%02d" % k
    if kind == "require_command":
        pred = ("require_command", "make check-%d" % k)
    elif kind == "forbid_command_prefix":
        pred = ("forbid_command_prefix", "tool%d install" % k)
    elif kind == "forbid_path_prefix":
        pred = ("forbid_path_prefix", "vault%d" % k)
    elif kind == "path_requires_path":
        pred = ("path_requires_path", "mod%d" % k, "notes%d.md" % k)
    else:
        pred = None
    return I(iid, kind or "unmeasured", "generated instruction %d" % k, pred)


def _realise(rng, ins, k, follow, trigger=None):
    """Paths and commands that make instruction k followed or not, and
    whether a conditional's trigger was touched."""
    p = ins.predicate
    paths, cmds = [], []
    if p is None:
        if rng.random() < 0.5:
            paths.append("free%d/x.py" % k)
        return paths, cmds, False
    kind = p[0]
    if kind == "require_command":
        if follow:
            cmds.append(rng.choice(["make check-%d" % k, "make  check-%d" % k, " make check-%d " % k]))
        else:
            cmds.append(rng.choice(["make check-%d || true" % k, "echo make check-%d" % k,
                                    "make check-%dx" % k, "make lint"]))
    elif kind == "forbid_command_prefix":
        t = "tool%d" % k
        forms = FORBID_FOLLOW_FORMS if follow else FORBID_BREAK_FORMS
        cmds.append(rng.choice(forms).format(t=t, k=k))
    elif kind == "forbid_path_prefix":
        if follow:
            paths.append(rng.choice(["vault%dx/a" % k, "docs/vault%d/a" % k, "notvault%d/a" % k]))
        else:
            paths.append(rng.choice(["vault%d/a" % k, "docs/../vault%d/b" % k, "vault%d" % k,
                                     "./vault%d/c" % k]))
    else:
        trig, req = p[1], p[2]
        if follow:
            hit = rng.random() < 0.5 if trigger is None else trigger
            if hit:
                paths += [trig + "/a.py", req]
            else:
                paths.append(rng.choice(["mod%dx/a.py" % k, "lib/mod%d/a.py" % k]))
            return paths, cmds, hit
        else:
            paths += [trig + "/a.py"]
            if rng.random() < 0.5:
                paths.append("docs/" + req)
            return paths, cmds, True
    return paths, cmds, False


def make_property_case(seed):
    """One generated property case: (name, acf, commits, expected)."""
    rng = random.Random(seed)
    n_ins = rng.randint(5, 9)
    n_com = rng.randint(3, 7)
    insts = []
    # Force at least one of each measured kind of split and one unmeasured.
    forced = ["always", "never", "mixed", "unmeasured"]
    plan = []
    for k in range(n_ins):
        ins = _instruction(rng, k)
        want = forced[k] if k < len(forced) else rng.choice(["always", "never", "mixed", "free", "untriggered"])
        if want == "untriggered" and (ins.predicate is None or ins.predicate[0] != "path_requires_path"):
            want = "always"
        if want == "unmeasured" and ins.predicate is not None:
            ins = I(ins.instruction_id, "unmeasured", ins.text, None)
        if want != "unmeasured" and ins.predicate is None:
            ins = I(ins.instruction_id, "testing", ins.text, ("require_command", "make check-%d" % k))
        insts.append(ins)
        plan.append(want)
    if seed % 3 == 0:
        # A fully measured file, so that clean commits can be accepted.
        plan = [w if w != "unmeasured" else "always" for w in plan]
        insts = [x if x.predicate is not None else
                 I(x.instruction_id, "testing", x.text, ("require_command", "make check-%d" % j))
                 for j, x in enumerate(insts)]
    order = list(range(n_ins))
    rng.shuffle(order)
    insts = [insts[j] for j in order]
    plan = [plan[j] for j in order]
    ks = [int(x.instruction_id[1:]) for x in insts]

    matrix = []  # matrix[c][i] in OUTCOMES
    for i, want in enumerate(plan):
        if insts[i].predicate is None:
            col = [A.NOT_OPERATIONALIZED] * n_com
        elif want in ("always", "untriggered"):
            col = [A.FOLLOWED] * n_com
        elif want == "never":
            col = [A.NOT_FOLLOWED] * n_com
        elif want == "mixed":
            col = [rng.choice([A.FOLLOWED, A.NOT_FOLLOWED]) for _ in range(n_com)]
            a, b = rng.sample(range(n_com), 2)
            col[a], col[b] = A.FOLLOWED, A.NOT_FOLLOWED
        else:
            col = [rng.choice([A.FOLLOWED, A.NOT_FOLLOWED]) for _ in range(n_com)]
        matrix.append(col)
    commits = []
    hits = [False] * n_ins
    for c in range(n_com):
        paths, cmds = ["misc/f%d.txt" % c], []
        for i, ins in enumerate(insts):
            # A planted "always" conditional is triggered in the first commit,
            # so that it is a real always and not an untriggered one.
            force = True if (c == 0 and plan[i] == "always") else False if plan[i] == "untriggered" else None
            p, q, hit = _realise(rng, ins, ks[i], matrix[i][c] != A.NOT_FOLLOWED, force)
            hits[i] = hits[i] or hit
            paths += p
            cmds += q
        if rng.random() < 0.3:
            cmds.append("make lint")
        rng.shuffle(paths)
        rng.shuffle(cmds)
        msg = CLAIM if rng.random() < 0.5 else "chore: update %d" % c
        commits.append(C("s%d-c%d" % (seed, c), tuple(paths), tuple(cmds), msg))
    oum = A.ON_UNMEASURED[seed % 4]
    acf = CF(tuple(insts), oum)

    outcomes = {cm.commit_id: tuple(matrix[i][c] for i in range(n_ins)) for c, cm in enumerate(commits)}
    buckets = {"always": [], "never": [], "mixed": [], "unmeasured": [], "not_applicable": []}
    for i, ins in enumerate(insts):
        col = set(matrix[i])
        conditional = ins.predicate is not None and ins.predicate[0] == "path_requires_path"
        key = ("unmeasured" if col == {A.NOT_OPERATIONALIZED} else
               "not_applicable" if col == {A.FOLLOWED} and conditional and not hits[i] else
               "always" if col == {A.FOLLOWED} else
               "never" if col == {A.NOT_FOLLOWED} else "mixed")
        buckets[key].append(ins.instruction_id)
    verdicts = {}
    for cid, outs in outcomes.items():
        if A.NOT_FOLLOWED in outs:
            verdicts[cid] = "refuse"
        elif A.NOT_OPERATIONALIZED in outs:
            verdicts[cid] = {"DENY": "refuse", "SAFE_FALLBACK": "safe_fallback",
                             "ESCALATE": "escalate", "HOLD": "hold"}[oum]
        else:
            verdicts[cid] = "accept"
    # Enforcement probes, outside the batch: one with every measured
    # instruction followed, and one per measured instruction where only that
    # instruction fails.
    measured = [i for i, ins in enumerate(insts) if ins.predicate is not None]
    probes = []
    for target in [None] + measured:
        paths, cmds = ["misc/probe.txt"], []
        for i, ins in enumerate(insts):
            p, q, _ = _realise(rng, ins, ks[i], i != target)
            paths += p
            cmds += q
        rng.shuffle(paths)
        msg = CLAIM if target is not None or rng.random() < 0.5 else "fix: probe"
        name = "s%d-p%s" % (seed, "clean" if target is None else insts[target].instruction_id)
        cm = C(name, tuple(paths), tuple(cmds), msg)
        if target is not None:
            want = ("refuse", (insts[target].instruction_id,))
        elif len(measured) < n_ins:
            want = ({"DENY": "refuse", "SAFE_FALLBACK": "safe_fallback",
                     "ESCALATE": "escalate", "HOLD": "hold"}[oum], ())
        else:
            want = ("accept", ())
        probes.append((cm, want))
    expect = {
        "probes": tuple(probes),
        "outcomes": outcomes,
        "split": tuple(tuple(buckets[k]) for k in SPLIT_KEYS),
        "verdicts": verdicts,
    }
    return ("property_%d" % seed, acf, tuple(commits), expect)


SPLIT_KEYS = ("always", "never", "mixed", "unmeasured", "not_applicable")
PROPERTY_CASES = tuple(make_property_case(s) for s in PROPERTY_SEEDS)


def split_tuple(b):
    return (b.always, b.never, b.mixed, b.unmeasured, b.not_applicable)


def check_case(acf, commits, expect):
    """Number of mismatches between the module and the planted expectation."""
    bad = 0
    for cm in commits:
        r = A.evaluate(acf, cm)
        if r.status != A.OK or tuple(o for _, o in r.outcomes) != expect["outcomes"][cm.commit_id]:
            bad += 1
        if A.enforce(acf, cm).verdict != expect["verdicts"][cm.commit_id]:
            bad += 1
    for cm, (verdict, failed) in expect.get("probes", ()):
        d = A.enforce(acf, cm)
        if (d.verdict, d.failed, d.accepted) != (verdict, failed, verdict == "accept"):
            bad += 1
    b = A.split(acf, commits)
    if b.status != A.OK or split_tuple(b) != expect["split"]:
        bad += 1
    return bad


def check_design(out=print):
    fails = check_case(DESIGN_ACF, DESIGN_COMMITS, DESIGN_EXPECT)
    out("%-28s %s" % ("design", "PASS" if fails == 0 else "FAIL"))
    for name, cm, want in ADVERSARIAL:
        got = tuple(o for _, o in A.evaluate(MEASURED_ACF, cm).outcomes)
        ok = got == want
        fails += 0 if ok else 1
        out("%-28s %s" % (name, "PASS" if ok else "FAIL"))
    for name, cm in MALFORMED:
        d = A.enforce(MEASURED_ACF, cm)
        ok = d.verdict == A.CONFIG_ERROR and not d.accepted
        fails += 0 if ok else 1
        out("%-28s %s" % (name, "PASS" if ok else "FAIL"))
    return fails, 1 + len(ADVERSARIAL) + len(MALFORMED)


def check_property(out=print):
    fails = 0
    for name, acf, commits, expect in PROPERTY_CASES:
        bad = check_case(acf, commits, expect)
        fails += 1 if bad else 0
        out("%-28s %s" % (name, "PASS" if bad == 0 else "FAIL (%d)" % bad))
    return fails, len(PROPERTY_CASES)


def property_totals():
    """Counts over the generated property cases: cases, commits, cells, outcomes, verdicts, buckets."""
    t = {"cases": len(PROPERTY_CASES), "commits": 0, "cells": 0}
    for _, acf, commits, expect in PROPERTY_CASES:
        t["commits"] += len(commits)
        for outs in expect["outcomes"].values():
            t["cells"] += len(outs)
            for o in outs:
                t[o] = t.get(o, 0) + 1
        for v in expect["verdicts"].values():
            t["verdict_" + v] = t.get("verdict_" + v, 0) + 1
        for key, ids in zip(SPLIT_KEYS, expect["split"]):
            t["split_" + key] = t.get("split_" + key, 0) + len(ids)
        for cm, (v, _) in expect["probes"]:
            t["probes"] = t.get("probes", 0) + 1
            t["probe_" + v] = t.get("probe_" + v, 0) + 1
        t["claim_messages"] = t.get("claim_messages", 0) + sum(c.message == CLAIM for c in commits)
        t["compound_commands"] = t.get("compound_commands", 0) + sum(
            1 for c in commits for x in c.commands if any(s in x for s in ("&&", "||", ";", "|", "\n")))
    return t


def main():
    fd, nd = check_design()
    fh, nh = check_property()
    print(A.report(DESIGN_ACF, DESIGN_COMMITS))
    print("property totals: %s" % property_totals())
    print("design %d/%d PASS, property cases %d/%d PASS" % (nd - fd, nd, nh - fh, nh))
    return 1 if fd or fh else 0


if __name__ == "__main__":
    sys.exit(main())
