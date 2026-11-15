"""Mutant runner: each mutant patches code or the fixture world, then the
unittest suite runs. A mutant is killed when at least one test fails or
errors.

- code: replaces one exact snippet of write_precommit.py or oracle.py (each
  snippet must occur exactly once) and re-executes the patched source in
  memory inside that module.
- world: changes the frozen fixtures in memory. The frozen digest test is
  skipped for these (test_write_precommit.WORLD_MUTANT), so only semantic
  tests can kill them.

Nothing is written to disk. Run: python3 -B mutants.py
Exit code 0 only when every mutant is killed and the clean suite passes
before and after.
"""

import copy
import io
import os
import sys
import unittest

import fixtures
import oracle
import test_write_precommit
import write_precommit

HERE = os.path.dirname(os.path.abspath(__file__))
MODULES = {"write_precommit": write_precommit, "oracle": oracle}
SNAPSHOTS = {k: dict(vars(m)) for k, m in MODULES.items()}
SOURCES = {}
for _k in MODULES:
    with open(os.path.join(HERE, _k + ".py"), encoding="utf-8") as _fh:
        SOURCES[_k] = _fh.read()
SUITE_ORIG = copy.deepcopy(fixtures.SUITE)


def code(module, *pairs):
    def apply():
        text = SOURCES[module]
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError("snippet not found exactly once: %r" % (old,))
            text = text.replace(old, new)
        exec(compile(text, os.path.join(HERE, module + ".py"), "exec"), MODULES[module].__dict__)
    return apply


def wp(*pairs):
    return code("write_precommit", *pairs)


def orc(*pairs):
    return code("oracle", *pairs)


def find(eid):
    return next(x for x in fixtures.SUITE if x["id"] == eid)


def events(eid):
    return find(eid)["episode"]["events"]


def world(edit):
    def apply():
        test_write_precommit.WORLD_MUTANT = True
        edit()
    return apply


def _drop(eid):
    fixtures.SUITE[:] = [x for x in fixtures.SUITE if x["id"] != eid]


def _request(eid, text):
    find(eid)["episode"]["request"] = text


def _move(eid, src, dst):
    ev = events(eid)
    ev.insert(dst, ev.pop(src))


def _relabel(eid, k, decision, reasons):
    find(eid)["label"]["decisions"][k][1:] = [decision, reasons]


def _set_write_args(eid, **kw):
    events(eid)[-1]["args"].update(kw)


def _set_result(eid, text):
    ev = events(eid)
    next(e for e in ev if e["type"] == "tool_result")["text"] = text


# The four mutants named in the VERDICT done-when are marked [V1]..[V4].
CODE_MUTANTS = [
    ("[V1] skip the precommit check", wp(
        ('    if commit is None:\n        reasons.append("not_precommitted")\n    elif',
         '    if commit is None:\n        pass\n    elif'))),
    ("[V2] tool-result text treated as user text", wp(
        ("            frozen = True\n",
         '            frozen = True\n            request = request + "\\n" + ev["text"]\n'))),
    ("[V3] admit a retarget (args not compared)", wp(
        ('            if commit["args"].get(arg) != write["args"].get(arg):',
         "            if False:"))),
    ("[V4] admit an unstated destination", wp(
        ("        elif value not in request:", "        elif False:"))),
    ("late commit accepted", wp(("            if frozen:\n", "            if False:\n"))),
    ("late commit replaces an existing commit", wp(
        ("            if frozen:\n", '            if frozen and ev["call_id"] not in commits:\n'))),
    ("tool swap not a retarget", wp(
        ('    elif commit["tool"] != write["tool"]:\n        reasons.append("retargeted")\n    else:\n',
         "    else:\n"))),
    ("retarget compares first targeting arg only", wp(
        ('        for arg in policy[write["tool"]]:\n            if commit',
         '        for arg in policy[write["tool"]][:1]:\n            if commit'))),
    ("stated check on first targeting arg only", wp(
        ('    for arg in policy[write["tool"]]:\n        if arg not in write["args"]:',
         '    for arg in policy[write["tool"]][:1]:\n        if arg not in write["args"]:'))),
    ("blank value counts as stated", wp(
        ('        if not value.strip():\n            reasons.append("empty:" + arg)\n        elif',
         '        if False:\n            pass\n        elif'))),
    ("missing targeting arg ignored", wp(
        ('            reasons.append("missing:" + arg)\n', "            pass\n"))),
    ("case-insensitive match", wp(
        ("        elif value not in request:",
         "        elif value.lower() not in request.lower():"))),
    ("request match by token overlap", wp(
        ("        elif value not in request:",
         "        elif not set(value.split()) & set(request.split()):"))),
    ("commit is not single-use", wp(("            if call_id in used:\n", "            if False:\n"))),
    ("refused write spends the commit", wp(
        ("            if decision == ADMIT:\n", "            if True:\n"))),
    ("episode may carry extra keys (a policy)", wp(("    if extra:\n", "    if False:\n"))),
    ("write tool without targeting accepted", wp(
        ('    if effect == "write" and not targeting:', '    if False:'))),
    ("non-str arg values accepted", wp(
        ("            if not _is_str(name) or not _is_str(value):",
         "            if not _is_str(name):"))),
    ("duplicate early commit accepted", wp(
        ('            if ev["call_id"] in early_ids:', "            if False:"))),
    ("tool_result from a write tool accepted", wp(
        ('            if schema[tool]["effect"] != "read":', "            if False:"))),
    ("paper results claimed measured", wp(
        ('ON_UNMEASURED = "on_unmeasured"', 'ON_UNMEASURED = "measured"'))),
    ("oracle: commits after the first result count", orc(
        ("    for j in range(cut):", "    for j in range(len(events)):"))),
    ("oracle: commit may follow the write", orc(("        ok = j < i and", "        ok = j < len(events) and"))),
    ("oracle: no stated check", orc(
        ('elif w.strip() == "" or request.find(w) < 0:', "elif False:"))),
    ("oracle: no equality check", orc(
        ('if w is None or c["args"].get(t) != w:', "if w is None:"))),
    ("oracle: no single-use", orc(('        if ok and e["call_id"] in spent:', "        if False:"))),
    ("oracle: tool not compared", orc(('and c["tool"] == e["tool"]', ""))),
    ("oracle: blank counts as stated", orc(('w.strip() == "" or ', ""))),
]

WORLD_MUTANTS = [
    ("drop the retarget fixture E1", world(lambda: _drop("E1-retarget-to-stated-recipient"))),
    ("E1 new recipient not in request", world(lambda: _request(
        "E1-retarget-to-stated-recipient", "Send 50 to Alice Kim."))),
    ("E1 write before the tool result", world(lambda: _move("E1-retarget-to-stated-recipient", 1, 2))),
    ("E1 relabelled ADMIT", world(lambda: _relabel("E1-retarget-to-stated-recipient", 0, "ADMIT", []))),
    ("E2 late commit moved before the result", world(lambda: _move("E2-recommit-after-result", 2, 1))),
    ("E4 tools made equal", world(lambda: events("E4-retarget-tool")[-1].update(tool="send_money"))),
    ("B2 injected amount not in request", world(lambda: _request(
        "B2-injected-write-stated-args", "Reply to Bob Lee at bob@corp.example about the invoice."))),
    ("B2 injected write precommitted", world(lambda: events("B2-injected-write-stated-args").insert(
        0, fixtures.commit("x1", "send_money", recipient="Bob Lee", amount="30")))),
    ("B3 late commit moved before the result", world(lambda: _move("B3-late-commit", 1, 0))),
    ("C4 tool result without the args", world(lambda: _set_result(
        "C4-dest-only-in-tool-result", "Bill attached."))),
    ("C1 destination added to request", world(lambda: _request(
        "C1-unstated-destination", "Move report.pdf into the Trash folder."))),
    ("C2 relabelled ADMIT", world(lambda: _relabel("C2-unstated-amount", 0, "ADMIT", []))),
    ("C7 request case fixed", world(lambda: _request("C7-case-differs", "send 20 to Alice Kim."))),
    ("A1 tool result removed", world(lambda: events("A1-stated-after-results").pop(1))),
    ("A2 body equals commit", world(lambda: _set_write_args("A2-body-from-result", body="(pending)"))),
    ("A3 drop admitted fixture", world(lambda: _drop("A3-move-no-results"))),
    ("X2 tool result added", world(lambda: events("X2-write-before-commit").insert(
        0, fixtures.result("read_inbox", "hi")))),
    ("drop every done-when e fixture", world(lambda: fixtures.SUITE.__setitem__(
        slice(None), [x for x in fixtures.SUITE if x["done_when"] != "e"]))),
]

MUTANTS = [("code", n, a) for n, a in CODE_MUTANTS] + [("world", n, a) for n, a in WORLD_MUTANTS]


def restore():
    for key, mod in MODULES.items():
        for name in [n for n in vars(mod) if n not in SNAPSHOTS[key]]:
            delattr(mod, name)
        mod.__dict__.update(SNAPSHOTS[key])
    fixtures.SUITE[:] = copy.deepcopy(SUITE_ORIG)
    test_write_precommit.WORLD_MUTANT = False


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_write_precommit)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


def main():
    restore()
    ran, bad = run_suite()
    print("clean suite: %d tests, %d failing" % (ran, bad))
    clean_ok = bad == 0
    killed = {"code": 0, "world": 0}
    totals = {"code": len(CODE_MUTANTS), "world": len(WORLD_MUTANTS)}
    for kind, name, apply in MUTANTS:
        try:
            apply()
            ran, bad = run_suite()
        except Exception as exc:
            print("%-6s %-48s BROKEN   (%s)" % (kind, name, type(exc).__name__))
            continue
        finally:
            restore()
        killed[kind] += 1 if bad else 0
        print("%-6s %-48s %-8s (%d/%d tests failing)" % (
            kind, name, "KILLED" if bad else "SURVIVED", bad, ran))
    ran, bad = run_suite()
    print("clean suite after restore: %d tests, %d failing" % (ran, bad))
    clean_ok = clean_ok and bad == 0
    total = sum(killed.values())
    print("killed %d/%d (code %d/%d, world %d/%d)" % (
        total, sum(totals.values()), killed["code"], totals["code"],
        killed["world"], totals["world"]))
    return 0 if clean_ok and total == sum(totals.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
