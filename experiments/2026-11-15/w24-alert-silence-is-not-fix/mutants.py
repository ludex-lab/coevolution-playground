"""Mutant runner: each mutant patches the code, the fixture world or the test
harness, then the unittest suite runs. A mutant is killed when at least one
test fails.

Code mutants replace one exact snippet of alert_silence.py, executor.py or
oracle.py (each snippet must occur exactly once) and re-run the patched
source in memory inside that module; this runner is the only file that
does so, and the code files themselves never run program text. World
mutants change the fixtures in memory and rebuild the cases. Harness
mutants replace one helper of the test module in memory. Nothing is written
to disk.

Run: python3 -B mutants.py
Exit code 0 only when every mutant is killed and the clean suite passes.
"""

import copy
import io
import os
import sys
import unittest

import alert_silence
import executor
import fixtures
import oracle
import test_alert_silence

MODULES = {"alert_silence": alert_silence, "executor": executor, "oracle": oracle}
SNAPSHOTS = {k: dict(vars(m)) for k, m in MODULES.items()}
FIX_SNAPSHOT = dict(vars(fixtures))
TEST_SNAPSHOT = dict(vars(test_alert_silence))
WORLD = ("ORIGINALS", "SILENCING", "CONTROLS", "FIXES", "CASES", "LABELS", "SILENCING_IDS",
         "CONTROL_IDS", "FIX_IDS", "FAMILIES", "UNMEASURED_IDS", "CONFIG_IDS", "EXPLOIT",
         "HARMLESS", "SPLIT_OFF", "TWO_SINKS")
WORLD_ORIG = {k: copy.deepcopy(getattr(fixtures, k)) for k in WORLD}
HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = {}
for _k in MODULES:
    with open(os.path.join(HERE, _k + ".py"), "r", encoding="utf-8") as _fh:
        SOURCES[_k] = _fh.read()


def code(module, *pairs):
    """Return an apply() that swaps each (old, new) snippet once in module."""
    def apply():
        text = SOURCES[module]
        for old, new in pairs:
            if text.count(old) != 1:
                raise ValueError("snippet not found exactly once: %r" % (old,))
            text = text.replace(old, new)
        path = os.path.join(HERE, module + ".py")
        exec(compile(text, path, "exec"), MODULES[module].__dict__)
    return apply


def mod(*pairs):
    return code("alert_silence", *pairs)


def exe(*pairs):
    return code("executor", *pairs)


def orc(*pairs):
    return code("oracle", *pairs)


CODE_MUTANTS = [
    # Input hardening.
    ("key types not checked", mod(
        ("        if type(k) is not str:\n            raise _Bad(detail)\n", "        pass\n"))),
    ("dict subclass accepted as a record", mod(
        ("    if type(d) is not dict:\n        raise _Bad(detail)\n    keys = list(d)\n",
         "    if not isinstance(d, dict):\n        raise _Bad(detail)\n    keys = list(d)\n"))),
    ("extra or missing fields accepted", mod(
        ("    keys = _strkeys(d, detail)\n    if sorted(keys) != sorted(fields):\n",
         "    keys = _strkeys(d, detail)\n    if not keys:\n"))),
    ("str subclass accepted as a name", mod(
        ("    return (type(v) is str and 0 < len(v) <= MAX_NAME",
         "    return (isinstance(v, str) and 0 < len(v) <= MAX_NAME"))),
    ("str subclass accepted as text", mod(
        ("    return type(v) is str and 0 < len(v) <= MAX_TEXT and v.strip() != \"\"\n",
         "    return isinstance(v, str) and 0 < len(v) <= MAX_TEXT and v.strip() != \"\"\n"))),
    ("bool and int subclass accepted as ints", mod(
        ("    return type(v) is int and lo <= v <= hi\n",
         "    return isinstance(v, int) and lo <= v <= hi\n"))),
    ("any number accepted as an index", mod(
        ("    return type(v) is int and lo <= v <= hi\n",
         "    return not (v != v) and v is not None and not isinstance(v, str) and lo <= v <= hi\n"))),
    ("op may be a str subclass", mod(
        ("    if type(op) is not str or op not in OPS:\n", "    if op not in OPS:\n"))),
    ("field name may be a str subclass", mod(
        ("            ok = type(v) is str and v in URL_FIELDS\n", "            ok = v in URL_FIELDS\n"))),
    ("const value unchecked", mod(
        ("            ok = type(v) is str and len(v) <= MAX_TEXT\n", "            ok = True\n"))),
    ("args may be any sequence", mod(
        ("            ok = type(v) is list\n", "            ok = isinstance(v, (list, tuple))\n"))),
    ("args length unchecked", mod(
        ("                ok = MIN_ARGS[op] <= len(v) <= MAX_ARGS and all(_name(a) for a in v)\n",
         "                ok = all(_name(a) for a in v)\n"))),
    ("body may be any sequence", mod(
        ("    if type(raw) is not list:\n        raise _Bad(detail)\n    items = tuple(raw)\n",
         "    if not isinstance(raw, (list, tuple)):\n        raise _Bad(detail)\n    items = tuple(raw)\n"))),
    ("body length unchecked", mod(
        ("    if len(items) > MAX_BODY:\n", "    if False:\n"))),
    ("helper count unchecked", mod(
        ("    if len(names) > MAX_HELPERS or not all(_name(n) for n in names):\n",
         "    if not all(_name(n) for n in names):\n"))),
    ("snapshot shares the caller's body list", mod(
        ("    return tuple(_instr(i) for i in items)\n",
         "    return [_instr(i) for i in items] and raw\n"))),
    ("reached may be any truthy value", mod(
        ("    if type(reached) is not bool:\n", "    if reached is None:\n"))),
    ("ran_on may be a str subclass", mod(
        ("    if not (type(ran_on) is str and len(ran_on) == 64",
         "    if not (isinstance(ran_on, str) and len(ran_on) == 64"))),
    ("ran_on format unchecked", mod(
        ("len(ran_on) == 64 and all(c in HEX for c in ran_on)):\n", "True):\n"))),
    ("unknown run names accepted", mod(
        ("        if n not in RUN_NAMES:\n            raise _Bad(\"runs_invalid\")\n", "        pass\n"))),
    # Static kinds.
    ("redefinition accepted", mod(
        ("        if ins[\"dst\"] in env:\n            raise _Bad(\"var_redefined\")\n", ""))),
    ("undefined variables accepted", mod(
        ("        if v not in env:\n            raise _Bad(\"var_undefined\")\n", ""))),
    ("kinds unchecked", mod(
        ("        if kind is not None and env[v] != kind:\n", "        if False:\n"))),
    ("helper cycles not detected", mod(
        ("        if state.get(name) == \"visiting\":\n            raise _Bad(\"helper_cycle\")\n",
         ""))),
    ("index bound unchecked", mod(
        ("            if type(k) is not tuple or ins[\"at\"] >= k[1]:\n",
         "            if type(k) is not tuple:\n"))),
    # Analyzer.
    ("analyzer gap closed (path tainted)", mod(
        ("            env[ins[\"dst\"]] = {\"query\": t, \"path\": False if gap else t}\n",
         "            env[ins[\"dst\"]] = {\"query\": t, \"path\": t}\n"))),
    ("analyzer gap on the query too", mod(
        ("            env[ins[\"dst\"]] = {\"query\": t, \"path\": False if gap else t}\n",
         "            env[ins[\"dst\"]] = {\"query\": False, \"path\": False if gap else t}\n"))),
    ("sanitize does not clean", mod(
        ("        elif op in (\"const\", \"sanitize\"):\n            env[ins[\"dst\"]] = False\n",
         "        elif op == \"const\":\n            env[ins[\"dst\"]] = False\n"
         "        elif op == \"sanitize\":\n            env[ins[\"dst\"]] = env[ins[\"src\"]]\n"))),
    ("concat reads its first argument only", mod(
        ("            env[ins[\"dst\"]] = any(env[a] for a in ins[\"args\"])\n",
         "            env[ins[\"dst\"]] = env[ins[\"args\"][0]]\n"))),
    ("container read loses taint", mod(
        ("        elif op == \"index\":\n            env[ins[\"dst\"]] = env[ins[\"src\"]]\n",
         "        elif op == \"index\":\n            env[ins[\"dst\"]] = False\n"))),
    ("helpers not followed (returns clean)", mod(
        ("            env[ins[\"dst\"]] = inner[h[\"ret\"]]\n", "            env[ins[\"dst\"]] = False\n"))),
    ("helper sinks labelled as body sinks", mod(
        ("\"helper \" + ins[\"fn\"], alerts)\n", "where, alerts)\n"))),
    # Gate.
    ("gate: alert gone means fixed", mod(
        ("    if runs[\"after\"][2]:\n        return REFUSE, (VULN_PRESENT if alert_after else ALERT_SILENCED), \"\"\n",
         "    if alert_after:\n        return REFUSE, VULN_PRESENT, \"\"\n"))),
    ("gate: missing after run passes", mod(
        ("    for name in RUN_NAMES:\n        if name not in runs:\n            return REFUSE, RUN_MISSING, name\n",
         "    if \"after\" not in runs:\n        return FIXED, EXPLOIT_GONE, \"\"\n"
         "    for name in RUN_NAMES:\n        if name not in runs:\n            return REFUSE, RUN_MISSING, name\n"))),
    ("gate: result not bound to the program", mod(
        ("        if ran_on != digest(snap[name]) or exploit != snap[\"exploit\"]:\n",
         "        if exploit != snap[\"exploit\"]:\n"))),
    ("gate: result not bound to the exploit", mod(
        ("        if ran_on != digest(snap[name]) or exploit != snap[\"exploit\"]:\n",
         "        if ran_on != digest(snap[name]):\n"))),
    ("gate: before run never needed", mod(
        ("    if not runs[\"before\"][2]:\n        return REFUSE, NOTHING_TO_FIX, \"\"\n", ""))),
    ("gate: silenced and present swapped", mod(
        ("(VULN_PRESENT if alert_after else ALERT_SILENCED)", "(ALERT_SILENCED if alert_after else VULN_PRESENT)"))),
    ("unbound results counted as measured", mod(
        ("UNMEASURED_REASONS = (RUN_MISSING, RUN_UNBOUND, RUN_UNREPRODUCED)\n",
         "UNMEASURED_REASONS = (RUN_MISSING, RUN_UNREPRODUCED)\n"))),
    ("unreproduced results counted as measured", mod(
        ("UNMEASURED_REASONS = (RUN_MISSING, RUN_UNBOUND, RUN_UNREPRODUCED)\n",
         "UNMEASURED_REASONS = (RUN_MISSING, RUN_UNBOUND)\n"))),
    # Declared exploit (r2).
    ("case exploit not checked against the declared set", mod(
        ("    if v[\"exploit\"] not in DECLARED_EXPLOITS:\n        raise _Bad(\"exploit_undeclared\")\n",
         ""))),
    ("declared set widened to the split-off payload", mod(
        ("DECLARED_EXPLOITS = (\"1' OR '1'='1\",)\n",
         "DECLARED_EXPLOITS = (\"1' OR '1'='1\", \"1' OR '1'='1?\")\n"))),
    ("declared set checked by prefix", mod(
        ("    if v[\"exploit\"] not in DECLARED_EXPLOITS:\n",
         "    if not any(v[\"exploit\"].startswith(e) for e in DECLARED_EXPLOITS):\n"))),
    # Re-run (r2).
    ("records never re-run", mod(
        ("        if rerun[name] is None or rerun[name] != runs[name]:\n            return REFUSE, RUN_UNREPRODUCED, name\n",
         "        pass\n"))),
    ("re-run checks the after record only", mod(
        ("        if rerun[name] is None or rerun[name] != runs[name]:\n",
         "        if name == \"after\" and (rerun[name] is None or rerun[name] != runs[name]):\n"))),
    ("re-run compares reached only", mod(
        ("        if rerun[name] is None or rerun[name] != runs[name]:\n",
         "        if rerun[name] is None or rerun[name][2] != runs[name][2]:\n"))),
    ("failed re-run treated as reproduced", mod(
        ("        if rerun[name] is None or rerun[name] != runs[name]:\n",
         "        if rerun[name] is not None and rerun[name] != runs[name]:\n"))),
    ("re-run record types unchecked", mod(
        ("            if type(rec[0]) is not str or type(rec[1]) is not str or type(rec[2]) is not bool:\n                rec = None\n",
         ""))),
    ("re-run errors escape the re-run", mod(
        ("        except Exception:\n            rec = None\n", "        except KeyError:\n            rec = None\n"))),
    ("re-run on a probe input", mod(
        ("            got = executor.execute(snap[name], snap[\"exploit\"])\n",
         "            got = executor.execute(snap[name], \"page?1\")\n"))),
    ("re-run always on the after program", mod(
        ("            got = executor.execute(snap[name], snap[\"exploit\"])\n",
         "            got = executor.execute(snap[\"after\"], snap[\"exploit\"])\n"))),
    ("reported exploit ignores reproduction", mod(
        ("    if run is None or rerun[name] != run:\n", "    if run is None:\n"))),
    ("unreproduced checked before unbound", mod(
        ("    for name in RUN_NAMES:\n        ran_on, exploit, _ = runs[name]\n"
         "        if ran_on != digest(snap[name]) or exploit != snap[\"exploit\"]:\n"
         "            return REFUSE, RUN_UNBOUND, name\n"
         "    for name in RUN_NAMES:\n        if rerun[name] is None or rerun[name] != runs[name]:\n"
         "            return REFUSE, RUN_UNREPRODUCED, name\n",
         "    for name in RUN_NAMES:\n        if rerun[name] is None or rerun[name] != runs[name]:\n"
         "            return REFUSE, RUN_UNREPRODUCED, name\n"
         "    for name in RUN_NAMES:\n        ran_on, exploit, _ = runs[name]\n"
         "        if ran_on != digest(snap[name]) or exploit != snap[\"exploit\"]:\n"
         "            return REFUSE, RUN_UNBOUND, name\n"))),
    # Review deferreds (r2).
    ("str subclass accepted as a key", mod(
        ("        if type(k) is not str:\n", "        if not isinstance(k, str):\n"))),
    ("ran_on may be longer than 64", mod(
        ("len(ran_on) == 64", "len(ran_on) >= 64"))),
    ("digest uses unescaped unicode", mod(
        ("    text = json.dumps(program, sort_keys=True, separators=(\",\", \":\"), ensure_ascii=True)\n"
         "    return hashlib.sha256(text.encode(\"ascii\")).hexdigest()\n",
         "    text = json.dumps(program, sort_keys=True, separators=(\",\", \":\"), ensure_ascii=False)\n"
         "    return hashlib.sha256(text.encode(\"utf-8\")).hexdigest()\n"))),
    ("baseline consults the executor", mod(
        ("            \"baseline\": baseline(bool(before), bool(after))}",
         "            \"baseline\": receipt}"))),
    ("baseline needs no alert before", mod(
        ("    return FIXED if alert_before and not alert_after else NOT_FIXED\n",
         "    return FIXED if not alert_after else NOT_FIXED\n"))),
    ("config error receipt is fixed", mod(
        ("    rec.update(status=CONFIG_ERROR, detail=detail, receipt=REFUSE,",
         "    rec.update(status=CONFIG_ERROR, detail=detail, receipt=FIXED,"))),
    ("internal errors escape evaluate()", mod(
        ("    try:\n        return _run(snap)\n    except Exception:\n        return _error(\"internal_error\")\n",
         "    return _run(snap)\n"))),
    ("robustness counts every measured change", mod(
        ("            if r[\"exploit_after\"] is True:\n", "            if r[\"exploit_after\"] is not None:\n"))),
    ("detection counts every original as found", mod(
        ("    return {\"detection\": (sum(1 for a in seen.values() if a), len(seen)),",
         "    return {\"detection\": (len(seen), len(seen)),"))),
    ("totals count baseline as gate", mod(
        ("        out[name] = (sum(1 for i in present if by_id[i][\"receipt\"] == FIXED),",
         "        out[name] = (sum(1 for i in present if by_id[i][\"baseline\"] == FIXED),"))),
    # Executor.
    ("executor: sanitize does nothing", exe(
        ("            val = mem[st[\"src\"]].replace(QUOTE, QUOTE_ESCAPED)\n",
         "            val = mem[st[\"src\"]]\n"))),
    ("executor: path mirrors the analyzer gap", exe(
        ("            val = {\"path\": text, \"query\": \"\"} if cut < 0 else \\\n",
         "            val = {\"path\": \"\", \"query\": \"\"} if cut < 0 else \\\n"))),
    ("executor: only the first sink counts", exe(
        ("            \"reached\": any(exploit in s for s in got)}\n",
         "            \"reached\": bool(got) and exploit in got[0]}\n"))),
    ("executor: fingerprint not canonical", exe(
        ("    blob = json.dumps(program, sort_keys=True, separators=(\",\", \":\"), ensure_ascii=True)\n",
         "    blob = json.dumps(program, sort_keys=True, ensure_ascii=True)\n"))),
    ("executor: no depth guard", exe(
        ("    if depth > MAX_DEPTH:\n        raise ExecError(\"too deep\")\n", ""))),
    ("executor: only the last sink counts", exe(
        ("            \"reached\": any(exploit in s for s in got)}\n",
         "            \"reached\": any(exploit in s for s in got[-1:])}\n"))),
    # Oracle.
    ("oracle: gap closed", orc(
        ("    before = _labels(case[\"before\"], True)\n    after = _labels(case[\"after\"], True)\n",
         "    before = _labels(case[\"before\"], False)\n    after = _labels(case[\"after\"], False)\n"))),
    ("oracle: unbound checked before missing", orc(
        ("        (state[\"before\"][0] == \"missing\", (\"refuse\", \"executor_missing\", \"before\")),\n"
         "        (state[\"after\"][0] == \"missing\", (\"refuse\", \"executor_missing\", \"after\")),\n"
         "        (state[\"before\"][0] == \"unbound\", (\"refuse\", \"executor_unbound\", \"before\")),\n",
         "        (state[\"before\"][0] == \"unbound\", (\"refuse\", \"executor_unbound\", \"before\")),\n"
         "        (state[\"before\"][0] == \"missing\", (\"refuse\", \"executor_missing\", \"before\")),\n"
         "        (state[\"after\"][0] == \"missing\", (\"refuse\", \"executor_missing\", \"after\")),\n"))),
    ("oracle: assign drops URL fields", orc(
        ("            for part in (\"path\", \"query\"):\n", "            for part in ():\n"))),
    ("oracle: helper result unmapped", orc(
        ("            names[st[\"dst\"]] = inner[h[\"ret\"]]\n",
         "            names[st[\"dst\"]] = names[st[\"arg\"]]\n"))),
    ("oracle: no declared-exploit rule", orc(
        ("    if case[\"exploit\"] != ATTACK:\n", "    if False:\n"))),
    ("oracle: records never reproduced", orc(
        ("    if rec[\"reached\"] is not _concrete(case[which], case[\"exploit\"]):\n",
         "    if False:\n"))),
    ("oracle: unreproduced checked before unbound", orc(
        ("        (state[\"before\"][0] == \"unbound\", (\"refuse\", \"executor_unbound\", \"before\")),\n"
         "        (state[\"after\"][0] == \"unbound\", (\"refuse\", \"executor_unbound\", \"after\")),\n"
         "        (state[\"before\"][0] == \"unreproduced\", (\"refuse\", \"executor_unreproduced\", \"before\")),\n",
         "        (state[\"before\"][0] == \"unreproduced\", (\"refuse\", \"executor_unreproduced\", \"before\")),\n"
         "        (state[\"before\"][0] == \"unbound\", (\"refuse\", \"executor_unbound\", \"before\")),\n"
         "        (state[\"after\"][0] == \"unbound\", (\"refuse\", \"executor_unbound\", \"after\")),\n"))),
    ("oracle: concrete sanitize does nothing", orc(
        ("            v = \"&#39;\".join(val[st[\"src\"]].split(\"'\"))\n", "            v = val[st[\"src\"]]\n"))),
    ("oracle: concrete path is the whole text", orc(
        ("            v = {\"path\": head, \"query\": tail}\n",
         "            v = {\"path\": val[st[\"src\"]], \"query\": tail}\n"))),
    ("oracle: concrete reads the last sink only", orc(
        ("    return len([s for s in sunk if attack in s]) > 0\n",
         "    return len([s for s in sunk[-1:] if attack in s]) > 0\n"))),
    ("oracle: duplicate sinks merged by name", orc(
        ("    return tuple(sorted(hits))\n", "    return tuple(sorted(set(h.split(\"[\")[0] + \"[0]\" for h in hits)))\n"))),
]


def _w():
    return dict((k, copy.deepcopy(v)) for k, v in WORLD_ORIG.items())


def _set(**kw):
    for k, v in kw.items():
        setattr(fixtures, k, v)


def _rebuild():
    fixtures.CASES = fixtures._build()


def _patch_after(group, cid, fn):
    g = copy.deepcopy(getattr(fixtures, group))
    orig, fam, after = g[cid]
    g[cid] = (orig, fam, fn(after))
    _set(**{group: g})
    _rebuild()


def w_silencing_made_a_fix():
    def fn(after):
        body = after["body"]
        i = [s["op"] for s in body].index("sink")
        body.insert(i, fixtures.sanitize("qq", body[i]["src"]))
        body[i + 1] = fixtures.sink("qq")
        return after
    _patch_after("SILENCING", "A2-parse-then-path", fn)


def w_control_silenced():
    def fn(after):
        for s in after["body"]:
            if s["op"] == "field":
                s["name"] = "path"
        return after
    _patch_after("CONTROLS", "K3-rename-query", fn)


def w_family_dropped():
    g = copy.deepcopy(WORLD_ORIG["SILENCING"])
    for k, (orig, fam, after) in list(g.items()):
        if fam == "split":
            g[k] = (orig, "field", after)
    _set(SILENCING=g, FAMILIES=tuple(f for f in WORLD_ORIG["FAMILIES"] if f != "split"))
    _rebuild()


def w_one_control():
    g = dict(list(WORLD_ORIG["CONTROLS"].items())[:1])
    _set(CONTROLS=copy.deepcopy(g), CONTROL_IDS=tuple(g),
         LABELS=dict((k, v) for k, v in WORLD_ORIG["LABELS"].items()
                     if not k.startswith("K") or k in g))
    _rebuild()


def w_one_fix():
    g = dict(list(WORLD_ORIG["FIXES"].items())[:1])
    _set(FIXES=copy.deepcopy(g), FIX_IDS=tuple(g),
         LABELS=dict((k, v) for k, v in WORLD_ORIG["LABELS"].items()
                     if not k.startswith("X") or k in g))
    _rebuild()


def w_exploit_without_quote():
    _set(EXPLOIT="1 OR 1=1")
    _rebuild()


def w_probe_reaches():
    _set(HARMLESS="probe")
    _rebuild()


def w_label_flipped():
    lab = dict(WORLD_ORIG["LABELS"])
    lab["A1-path-routing"] = ("ok", "fixed", "exploit_gone", "fixed", True, False)
    _set(LABELS=lab)


def w_original_undetected():
    o = copy.deepcopy(WORLD_ORIG["ORIGINALS"])
    for s in o["O2"]["body"]:
        if s["op"] == "field":
            s["name"] = "path"
    _set(ORIGINALS=o)
    _rebuild()


def w_replayed_result_genuine():
    cs = fixtures.CASES
    c = cs["U4-result-from-another-program"]
    c["runs"]["after"] = executor.execute(c["after"], fixtures.EXPLOIT)


def w_forged_record_genuine():
    c = fixtures.CASES["U6-forged-after-record"]
    c["runs"]["after"] = executor.execute(c["after"], fixtures.EXPLOIT)


def w_chosen_exploit_declared():
    c = fixtures.CASES["E4-exploit-not-declared"]
    c["exploit"] = fixtures.EXPLOIT


def w_cases_shared():
    shared = fixtures.CASES
    fixtures.cases = lambda: shared


WORLD_MUTANTS = [
    ("silencing rewrite turned into a fix", w_silencing_made_a_fix),
    ("control rewritten through the gap", w_control_silenced),
    ("one rewrite family dropped", w_family_dropped),
    ("controls reduced to one", w_one_control),
    ("fixes reduced to one", w_one_fix),
    ("exploit without a quote", w_exploit_without_quote),
    ("probe input that reaches the sink", w_probe_reaches),
    ("hand label flipped", w_label_flipped),
    ("original made undetected", w_original_undetected),
    ("replayed result made genuine", w_replayed_result_genuine),
    ("forged record made genuine", w_forged_record_genuine),
    ("chosen exploit made the declared one", w_chosen_exploit_declared),
    ("cases() returns shared state", w_cases_shared),
]


def h_scan_whole_day_readme():
    test_alert_silence.scan_text = lambda name, text: text


def h_own_rows_every_line():
    test_alert_silence.own_rows = lambda text: text.splitlines()


def h_own_rows_nothing():
    test_alert_silence.own_rows = lambda text: []


def h_hygiene_ignores_banned_words():
    real = test_alert_silence.hygiene_hits
    test_alert_silence.hygiene_hits = lambda text: real(text) - {"banned_word"}


def h_exec_scan_blind():
    test_alert_silence.exec_hits = lambda src: set()


HARNESS_MUTANTS = [
    ("hygiene scans read the whole day README", h_scan_whole_day_readme),
    ("own-row filter returns every line", h_own_rows_every_line),
    ("own-row filter returns nothing", h_own_rows_nothing),
    ("hygiene helper ignores banned words", h_hygiene_ignores_banned_words),
    ("execution scan finds nothing", h_exec_scan_blind),
]

MUTANTS = ([("code", n, a) for n, a in CODE_MUTANTS]
           + [("world", n, a) for n, a in WORLD_MUTANTS]
           + [("harness", n, a) for n, a in HARNESS_MUTANTS])


def restore():
    for k, m in MODULES.items():
        for name in [n for n in vars(m) if n not in SNAPSHOTS[k]]:
            delattr(m, name)
        m.__dict__.update(SNAPSHOTS[k])
    for name in [n for n in vars(fixtures) if n not in FIX_SNAPSHOT]:
        delattr(fixtures, name)
    fixtures.__dict__.update(FIX_SNAPSHOT)
    _set(**_w())
    for name in [n for n in vars(test_alert_silence) if n not in TEST_SNAPSHOT]:
        delattr(test_alert_silence, name)
    test_alert_silence.__dict__.update(TEST_SNAPSHOT)


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_alert_silence)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


def main():
    restore()
    ran, bad = run_suite()
    print("clean suite: %d tests, %d failing" % (ran, bad))
    clean_ok = bad == 0
    killed = {"code": 0, "world": 0, "harness": 0}
    for kind, name, apply in MUTANTS:
        try:
            apply()
            ran, bad = run_suite()
        except Exception as exc:
            restore()
            print("%-7s %-50s BROKEN   (%s)" % (kind, name, type(exc).__name__))
            continue
        finally:
            restore()
        status = "KILLED" if bad else "SURVIVED"
        killed[kind] += 1 if bad else 0
        print("%-7s %-50s %-8s (%d/%d tests failing)" % (kind, name, status, bad, ran))
    ran, bad = run_suite()
    print("clean suite after restore: %d tests, %d failing" % (ran, bad))
    clean_ok = clean_ok and bad == 0
    n_code, n_world, n_harness = len(CODE_MUTANTS), len(WORLD_MUTANTS), len(HARNESS_MUTANTS)
    total = killed["code"] + killed["world"] + killed["harness"]
    print("killed %d/%d (code %d/%d, world %d/%d, harness %d/%d)"
          % (total, n_code + n_world + n_harness, killed["code"], n_code,
             killed["world"], n_world, killed["harness"], n_harness))
    ok = clean_ok and total == n_code + n_world + n_harness
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
