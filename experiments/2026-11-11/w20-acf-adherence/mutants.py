"""Mutation check for w20-acf-adherence. Run: python3 mutants.py

Each mutant replaces one exact piece of source text in one file, writes
the result into a temporary copy of this directory (inside a temporary
experiments/2026-11-11/ layout), and runs fixtures.py and the unittest
suite there with the paper-source check skipped (W20ACF_SOURCES unset). A
mutant is killed when either run fails. The temporary directory is removed
at the end.

Two lists, reported separately:
  code   mutants of acf_adherence.py: not_operationalized counted as
         followed, predicates that read the message, mixed misclassified,
         enforcement that skips a failure, a missing, unknown or
         permit-token on_unmeasured accepted, path and command matching
         loosened, batch checks dropped, fail-closed checks removed, and
         each step of the shell normaliser dropped or weakened.
  world  mutants of the test world (fixtures.py, test_acf_adherence.py):
         thinner or weaker fixtures that a sound suite must notice.

Stdlib only. Exit status 0 when every non-equivalent mutant is killed and
every anchor matches exactly once.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = "acf_adherence.py"
FIX = "fixtures.py"
TEST = "test_acf_adherence.py"
SLUG = "w20-acf-adherence"

# Mutants that cannot change any observable behaviour. Each is explained.
EQUIVALENT = set()

M = [
    # not_operationalized is never followed
    ('unmeasured_counted_followed',
     '        return NOT_OPERATIONALIZED\n',
     '        return FOLLOWED\n'),
    ('counts_add_unmeasured_to_followed',
     'sum(1 for _, x in outs if x == o)',
     'sum(1 for _, x in outs if x == o or (o == FOLLOWED and x == NOT_OPERATIONALIZED))'),
    ('enforce_accepts_unmeasured',
     '    if unmeasured:\n',
     '    if False:\n'),
    ('split_unmeasured_as_mixed',
     '        if seen == {NOT_OPERATIONALIZED}:',
     '        if False:'),
    # predicates read the message
    ('predicate_reads_message',
     'outs = tuple((ins.instruction_id, outcome(ins, facts)) for ins in acf.instructions)',
     'outs = tuple((ins.instruction_id, FOLLOWED if ins.predicate is not None and "followed" in commit.message'
     ' else outcome(ins, facts)) for ins in acf.instructions)'),
    ('message_refuses',
     '    if failed:\n',
     '    if failed or "skipped" in commit.message:\n'),
    # mixed misclassified
    ('mixed_as_never',
     '        elif seen == {NOT_FOLLOWED}:',
     '        elif NOT_FOLLOWED in seen:'),
    ('mixed_as_always',
     '        elif seen == {FOLLOWED}:',
     '        elif FOLLOWED in seen:'),
    ('small_batch_split',
     '    if len(commits) < MIN_BATCH:',
     '    if False:'),
    ('min_batch_two',
     'MIN_BATCH = 3',
     'MIN_BATCH = 2'),
    ('duplicate_commit_ok',
     '    if len(set(ids)) != len(ids):',
     '    if False:'),
    ('malformed_in_batch_ignored',
     '        if r.status != OK:\n            errs',
     '        if False:\n            errs'),
    # enforcement skips a failure
    ('enforce_skips_failure',
     '    if failed:\n',
     '    if False:\n'),
    ('enforce_config_error_accepts',
     '        return Decision(r.commit_id, CONFIG_ERROR, False, (), (), r.errors)',
     '        return Decision(r.commit_id, ACCEPT, True, (), (), r.errors)'),
    ('unmeasured_sets_accepted',
     '        return Decision(r.commit_id, verdict, False, failed, unmeasured)',
     '        return Decision(r.commit_id, verdict, True, failed, unmeasured)'),
    ('on_unmeasured_ignored_hold',
     '        verdict = VERDICT_ON_UNMEASURED[acf.on_unmeasured]',
     '        verdict = V_HOLD'),
    ('deny_maps_to_hold',
     '    DENY: REFUSE,',
     '    DENY: V_HOLD,'),
    # missing / unknown / permit-token on_unmeasured accepted
    ('missing_on_unmeasured_defaults_hold',
     '        errs.append("on_unmeasured_missing")',
     '        oum = HOLD'),
    ('permit_token_accepted',
     '        errs.append("on_unmeasured_permit_token")',
     '        pass'),
    ('permit_token_case_sensitive',
     '    elif PERMIT_TOKEN in oum.lower():',
     '    elif PERMIT_TOKEN in oum:'),
    ('unknown_on_unmeasured_accepted',
     '    elif oum not in ON_UNMEASURED:',
     '    elif False:'),
    ('on_unmeasured_isinstance',
     '    elif type(oum) is not str:',
     '    elif not isinstance(oum, str):'),
    ('evaluate_ignores_config_errors',
     '    if errs or cerrs:',
     '    if cerrs:'),
    # config fail-closed checks
    ('empty_instructions_ok',
     '    if type(insts) is not tuple or len(insts) == 0:',
     '    if type(insts) is not tuple:'),
    ('duplicate_instruction_ok',
     '        if iid in seen:',
     '        if False:'),
    ('predicate_shape_ok',
     '        return "predicate_shape"',
     '        return None'),
    ('predicate_arity_ok',
     '    if len(args) != PREDICATE_ARITY[kind]:',
     '    if False:'),
    ('predicate_args_ok',
     '    if not all(_str(a) for a in args):',
     '    if False:'),
    ('predicate_path_unnormalised_ok',
     '        if any(_norm_path(a) != a for a in args):',
     '        if False:'),
    ('predicate_command_unnormalised_ok',
     '        if any(_norm_command(a) != a for a in args):',
     '        if False:'),
    # path and command matching loosened
    ('path_not_normalised',
     '    n = posixpath.normpath(p)',
     '    n = p'),
    ('escaping_path_ok',
     '    if n == "." or n == ".." or n.startswith("../"):',
     '    if False:'),
    ('absolute_path_ok',
     '    if not _str(p) or p.startswith("/") or "\\\\" in p:',
     '    if not _str(p) or "\\\\" in p:'),
    ('backslash_path_ok',
     '    if not _str(p) or p.startswith("/") or "\\\\" in p:',
     '    if not _str(p) or p.startswith("/"):'),
    ('under_is_startswith',
     '    return path == prefix or path.startswith(prefix + "/")',
     '    return path.startswith(prefix)'),
    ('under_is_substring',
     '    return path == prefix or path.startswith(prefix + "/")',
     '    return prefix in path'),
    ('require_command_substring',
     '        return pred[1] in cmds',
     '        return any(pred[1] in c for c in cmds)'),
    ('command_not_normalised',
     '    return " ".join(c.split())',
     '    return c'),
    ('blank_command_ok',
     '        if any(c == "" for c in ncmds):',
     '        if False:'),
    ('forbid_command_loose_prefix',
     '    if any(c == prefix or c.startswith(prefix + " ") for c in cmds):',
     '    if any(c.startswith(prefix) for c in cmds):'),
    ('forbid_command_exact_only',
     '    if any(c == prefix or c.startswith(prefix + " ") for c in cmds):',
     '    if any(c == prefix for c in cmds):'),
    ('forbid_string_rule_dropped',
     '    if any(c == prefix or c.startswith(prefix + " ") for c in cmds):\n        return True\n',
     ''),
    ('predicate_tuple_isinstance',
     '    if type(pred) is not tuple or',
     '    if not isinstance(pred, tuple) or'),
    # shell normaliser (F1)
    ('sep_drop_semicolon', r'SEP_CHARS = "();<>|&`\n"', r'SEP_CHARS = "()<>|&`\n"'),
    ('sep_drop_ampersand', r'SEP_CHARS = "();<>|&`\n"', r'SEP_CHARS = "();<>|`\n"'),
    ('sep_drop_pipe', r'SEP_CHARS = "();<>|&`\n"', r'SEP_CHARS = "();<>&`\n"'),
    ('sep_drop_newline', r'SEP_CHARS = "();<>|&`\n"', r'SEP_CHARS = "();<>|&`"'),
    ('sep_drop_parens', r'SEP_CHARS = "();<>|&`\n"', r'SEP_CHARS = ";<>|&`\n"'),
    ('sep_drop_backtick', r'SEP_CHARS = "();<>|&`\n"', r'SEP_CHARS = "();<>|&\n"'),
    ('newline_is_whitespace', r'    lex.whitespace = " \t\r"', r'    lex.whitespace = " \t\r\n"'),
    ('no_line_continuation_join',
     r'    s = cmd.replace("\\\r\n", "").replace("\\\n", "")',
     '    s = cmd'),
    ('quotes_ignored', '        return list(lex)', '        return cmd.split()'),
    ('unparseable_passes_tokens', '    except ValueError:\n        return None', '    except ValueError:\n        return []'),
    ('unparseable_passes_rule', '        if a is UNPARSEABLE:\n            return True',
     '        if a is UNPARSEABLE:\n            continue'),
    ('first_piece_only', '    return [p for p in out if p]', '    return [p for p in out if p][:1]'),
    ('no_assignment_strip', '            while words and (ASSIGNMENT.match(words[0]) or words[0] in RESERVED):',
     '            while words and words[0] in RESERVED:'),
    ('no_reserved_strip', '            while words and (ASSIGNMENT.match(words[0]) or words[0] in RESERVED):',
     '            while words and ASSIGNMENT.match(words[0]):'),
    ('no_wrapper_strip', '            if words and posixpath.basename(words[0]) in WRAPPERS:', '            if False:'),
    ('wrapper_value_option_unskipped', '        if w in value_opts:\n            i += 1', '        if False:\n            i += 1'),
    ('wrapper_options_unskipped', '                i = _skip_options(words, 1, opts)', '                i = 1'),
    ('wrapper_positional_unskipped', '                words = words[i + npos:]', '                words = words[i:]'),
    ('no_basename', '        name = posixpath.basename(words[0])\n        rest', '        name = words[0]\n        rest'),
    ('no_version_suffix',
     r'    if n != p0 and not (p0[-1].isalpha() and re.fullmatch(re.escape(p0) + r"\d+(\.\d+)*", n)):',
     '    if n != p0:'),
    ('version_suffix_any_name',
     r'    if n != p0 and not (p0[-1].isalpha() and re.fullmatch(re.escape(p0) + r"\d+(\.\d+)*", n)):',
     r'    if n != p0 and not re.fullmatch(re.escape(p0) + r"\d+(\.\d+)*", n):'),
    ('version_suffix_loose',
     r'    if n != p0 and not (p0[-1].isalpha() and re.fullmatch(re.escape(p0) + r"\d+(\.\d+)*", n)):',
     '    if n != p0 and not n.startswith(p0):'),
    ('no_python_m', '            if module:\n', '            if False:\n'),
    ('no_glued_m', '                if w.startswith("-m") and not w.startswith("--"):', '                if False:'),
    ('python_options_unskipped', '                j += 2 if w in PY_VALUE_OPTS else 1', '                break'),
    ('no_uv_pip', '            if j < len(rest) and rest[j] == "pip":', '            if False:'),
    ('no_shell_c', '        if name in SHELLS:', '        if False:'),
    ('no_eval', '        if name == "eval":', '        if False:'),
    ('no_option_skip_between_words',
     '        while j < len(argv) and argv[j].startswith("-") and argv[j] != want:', '        while False:'),
    ('option_skip_eats_wanted',
     '        while j < len(argv) and argv[j].startswith("-") and argv[j] != want:',
     '        while j < len(argv) and argv[j] != want:'),
    ('depth_unbounded', '    if depth > MAX_DEPTH:\n        return None', '    if False:\n        return None'),
    ('prefix_config_unchecked',
     '        if kind == "forbid_command_prefix" and (set(args[0]) & COMMAND_PREFIX_BAD or args[0][0] == "-"):',
     '        if False:'),
    ('argvs_from_plain_split', '    argvs = tuple(_command_argvs(c) for c in cmds)',
     '    argvs = tuple(((tuple(c.split()),) for c in ncmds))'),
    # not_applicable marker (F4)
    ('not_applicable_dropped',
     '        elif seen == {FOLLOWED} and ins.predicate[0] == "path_requires_path" and \\',
     '        elif False and \\'),
    ('triggered_never', '    return pred[0] == "path_requires_path" and any(_under(x, pred[1]) for x in facts[0])',
     '    return False'),
    ('triggered_always', '    return pred[0] == "path_requires_path" and any(_under(x, pred[1]) for x in facts[0])',
     '    return True'),
    ('requires_ignores_trigger',
     '        if any(_under(x, pred[1]) for x in paths):\n',
     '        if True:\n'),
    ('requires_any_suffix',
     '            return any(_under(x, pred[2]) for x in paths)',
     '            return any(x.endswith(pred[2]) for x in paths)'),
    ('commit_type_unchecked',
     '    if type(commit) is not Commit:\n        return ("commit_type",), None',
     '    if commit is None:\n        return ("commit_type",), None'),
    ('paths_list_ok',
     '    if type(paths) is not tuple:',
     '    if not isinstance(paths, (tuple, list)):'),
    ('message_type_unchecked',
     '    if type(msg) is not str:',
     '    if False:'),
    ('empty_commit_id_ok',
     '    if not _str(cid):',
     '    if False:'),
]


# World mutants: (name, file, old, new). The code is unchanged; the test
# world is made thinner or weaker, and the suite must notice.
W = [
    ('gen_break_forms_plain_only', FIX,
     '    "cd src && {t} install pkg", "true; {t} install", "make lint || {t} install x",\n'
     '    "sudo {t} install x", "X_{k}=1 env {t} install", "/opt/bin/{t} install x",\n'
     '    "\'{t}\' install", "python3 -m {t} install x", "{t} \\\\\\n  install x",\n'
     '    "echo a | {t} install -r -",\n',
     ''),
    ('gen_break_forms_drop_compound', FIX,
     '    "cd src && {t} install pkg", "true; {t} install", "make lint || {t} install x",\n', ''),
    ('gen_follow_forms_plain_only', FIX,
     '    "{t} list", "{t} installed", "echo {t} install", "make lint && {t} list",\n'
     '    "echo \'{t} install\'; true", "sudo {t} list", "grep {t} install.log | wc -l",',
     '    "{t} list", "{t} installed", "echo {t} install",'),
    ('gen_no_forced_trigger', FIX,
     '            force = True if (c == 0 and plan[i] == "always") else False if plan[i] == "untriggered" else None',
     '            force = None'),
    ('gen_hits_ignored', FIX, '            hits[i] = hits[i] or hit', '            hits[i] = True'),
    ('bypass_list_drop_sudo', FIX, ' "sudo pip install x",', ''),
    ('bypass_list_replace_chain', FIX, '"cd src && pip install x"', '"pip install src"'),
    ('bypass_list_replace_python_m', FIX, '"python3 -m pip install x"', '"pip install x3"'),
    ('more_forms_thinned', FIX,
     '    "make lint || pip install x", "ls | pip install -r -", "pip install x &", "false\\npip install x",\n', ''),
    ('legit_list_thinned', FIX, '"pip list", "pip download x", "pip==1 install", "pipx install x", ', ''),
    ('unparseable_list_thinned', FIX,
     'PIP_UNPARSEABLE = ("echo \'x", \'echo "x\', "pip install \'x", "bash -c \'echo \\"a\'")',
     'PIP_UNPARSEABLE = ("echo \'x",)'),
    ('pinned_gap_dropped', FIX, '    ("case", "PIP install x"),\n', ''),
    ('property_seeds_cut', FIX, 'PROPERTY_SEEDS = tuple(range(3101, 3113))', 'PROPERTY_SEEDS = tuple(range(3101, 3104))'),
    ('lying_fixture_honest', FIX,
     'LYING = C("lying", ("src/app.py", "CHANGELOG.md", "secrets/key.pem"), ("make lint",), CLAIM)',
     'LYING = C("lying", ("src/app.py", "CHANGELOG.md"), ("make test",), CLAIM)'),
    ('tuple_subclass_fixture_plain', TEST,
     '        for pred in (T(("require_command", "make test")), T(("forbid_command_prefix", "pip install"))):',
     '        for pred in (("require_command", "make test"), ("forbid_command_prefix", "pip install")):'),
    ('tuple_subclass_fixture_list', TEST,
     '        for pred in (T(("require_command", "make test")), T(("forbid_command_prefix", "pip install"))):',
     '        for pred in (["require_command", "make test"], ["forbid_command_prefix", "pip install"]):'),
    ('untriggered_fixture_triggered', TEST,
     '        cs = tuple(C("v%d" % k, ("docs/x%d" % k,), ()) for k in range(3))',
     '        cs = tuple(C("v%d" % k, ("src/x%d" % k, "CHANGELOG.md"), ()) for k in range(3))'),
]

# World mutants that cannot make the suite fail, each explained.
EQUIVALENT_WORLD = set()


def _copy_layout(tmp, name):
    d = os.path.join(tmp, name, "experiments", "2026-11-11", SLUG)
    os.makedirs(d)
    for f in os.listdir(HERE):
        p = os.path.join(HERE, f)
        if os.path.isfile(p) and not f.endswith(".pyc"):
            shutil.copy(p, d)
    return d


def _passes(d):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("W20ACF_SOURCES", None)
    a = subprocess.run([sys.executable, "-B", "fixtures.py"], cwd=d, capture_output=True, env=env)
    b = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_acf_adherence.py"], cwd=d,
                       capture_output=True, env=env)
    return a.returncode == 0 and b.returncode == 0


def _run(tmp, label, items, equivalent_names):
    killed, survivors, equivalent, bad_anchor = 0, [], [], []
    for k, (name, fname, old, new) in enumerate(items):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            src = f.read()
        if src.count(old) != 1:
            bad_anchor.append(name)
            print("%-38s ANCHOR(%d)" % (name, src.count(old)))
            continue
        sub = "%s%03d" % (label, k)
        d = _copy_layout(tmp, sub)
        with open(os.path.join(d, fname), "w", encoding="utf-8") as f:
            f.write(src.replace(old, new, 1))
        survived = _passes(d)
        shutil.rmtree(os.path.join(tmp, sub))
        if not survived:
            killed += 1
            verdict = "killed"
        elif name in equivalent_names:
            equivalent.append(name)
            verdict = "survived (equivalent)"
        else:
            survivors.append(name)
            verdict = "SURVIVED"
        print("%-38s %s" % (name, verdict))
    print("summary %s: %d mutants; killed %d; equivalent %d %s; survivors %d %s; bad anchors %d %s" % (
        label, len(items), killed, len(equivalent), sorted(equivalent), len(survivors), survivors,
        len(bad_anchor), bad_anchor))
    return bool(survivors or bad_anchor)


def main():
    tmp = tempfile.mkdtemp(prefix="w20acf-mutants-")
    try:
        base = _copy_layout(tmp, "base")
        if not _passes(base):
            print("baseline: FAIL (suite or fixtures fail on unmutated code)")
            return 2
        print("baseline: OK")
        print("-- code mutants (%s)" % TARGET)
        bad_code = _run(tmp, "code", [(n, TARGET, o, w) for n, o, w in M], EQUIVALENT)
        print("-- world mutants (%s, %s)" % (FIX, TEST))
        bad_world = _run(tmp, "world", W, EQUIVALENT_WORLD)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if bad_code or bad_world else 0


if __name__ == "__main__":
    sys.exit(main())
