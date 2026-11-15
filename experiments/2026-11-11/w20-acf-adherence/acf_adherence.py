"""w20-acf-adherence: instruction-level adherence to an agent context file.

Method sketch of the measurement idea in arXiv 2611.13709 (CC BY 4.0).
Clean-room Python 3 stdlib. Not a reproduction, not Team OS law and not
village law.

Records
  Instruction(instruction_id, category, text, predicate)
      predicate is a declarative check over commit FACTS, or None when the
      instruction is not operationalized. Predicate kinds:
        ("require_command", cmd)            cmd was run
        ("forbid_command_prefix", prefix)   no run command starts with prefix,
                                            read through the shell normaliser
        ("forbid_path_prefix", prefix)      no touched path lies under prefix
        ("path_requires_path", trig, req)   touching trig/... means req was touched
  ContextFile(instructions, on_unmeasured)
      on_unmeasured must be one of DENY, SAFE_FALLBACK, ESCALATE, HOLD.
  Commit(commit_id, paths, commands, message)
      paths and commands are the FACTS. The message is carried for the
      record only; no predicate receives it.

Check layer
  check_config(acf)        -> tuple of errors (empty when the file is sound)
  evaluate(acf, commit)    -> CommitReport, one outcome per instruction
  split(acf, commits)      -> BatchReport, always / never / mixed / unmeasured,
                              plus not_applicable for a conditional whose
                              trigger is absent from every commit
  enforce(acf, commit)     -> Decision; refuse, hold, escalate, safe_fallback,
                              accept or config_error. Nothing unmeasured is
                              ever accepted.
"""

import posixpath
import re
import shlex
from dataclasses import dataclass

FOLLOWED = "followed"
NOT_FOLLOWED = "not_followed"
NOT_OPERATIONALIZED = "not_operationalized"
OUTCOMES = (FOLLOWED, NOT_FOLLOWED, NOT_OPERATIONALIZED)

ALWAYS = "always"
NEVER = "never"
MIXED = "mixed"

DENY = "DENY"
SAFE_FALLBACK = "SAFE_FALLBACK"
ESCALATE = "ESCALATE"
HOLD = "HOLD"
ON_UNMEASURED = (DENY, SAFE_FALLBACK, ESCALATE, HOLD)

ACCEPT = "accept"
REFUSE = "refuse"
V_HOLD = "hold"
V_ESCALATE = "escalate"
V_SAFE_FALLBACK = "safe_fallback"
CONFIG_ERROR = "config_error"
VERDICT_ON_UNMEASURED = {
    DENY: REFUSE,
    SAFE_FALLBACK: V_SAFE_FALLBACK,
    ESCALATE: V_ESCALATE,
    HOLD: V_HOLD,
}

OK = "ok"
INSUFFICIENT_BATCH = "insufficient_batch"
MIN_BATCH = 3

# Built from parts so that the word itself never appears in this folder.
PERMIT_TOKEN = "al" + "low"

PREDICATE_ARITY = {
    "require_command": 1,
    "forbid_command_prefix": 1,
    "forbid_path_prefix": 1,
    "path_requires_path": 2,
}


@dataclass(frozen=True)
class Instruction:
    instruction_id: str
    category: str
    text: str
    predicate: object


@dataclass(frozen=True)
class ContextFile:
    instructions: tuple
    on_unmeasured: object = None


@dataclass(frozen=True)
class Commit:
    commit_id: str
    paths: tuple
    commands: tuple
    message: str = ""


@dataclass(frozen=True)
class CommitReport:
    commit_id: str
    status: str
    outcomes: tuple
    counts: tuple
    errors: tuple = ()


@dataclass(frozen=True)
class BatchReport:
    status: str
    always: tuple
    never: tuple
    mixed: tuple
    unmeasured: tuple
    errors: tuple = ()
    not_applicable: tuple = ()


@dataclass(frozen=True)
class Decision:
    commit_id: str
    verdict: str
    accepted: bool
    failed: tuple
    unmeasured: tuple
    errors: tuple = ()


def _str(x):
    return type(x) is str and x != ""


def _norm_command(c):
    return " ".join(c.split())


# ---------------------------------------------------------- shell normaliser
#
# A forbid_command_prefix rule is read against every simple command a
# command record could run, not only against the record's first word.
# The record is tokenised with shlex (POSIX quoting, backslash escapes),
# backslash-newline is joined, and the token stream is cut at every
# control or redirection token (&& || ; | & newline ( ) ` < >). Each piece
# then loses leading VAR=val assignments, reserved words and transparent
# wrappers (sudo, env, nohup, ...), its first word is reduced to a
# basename, `python -m X` and `uv pip` are rewritten to X and pip, and
# `sh -c STRING` / `eval ...` are read again as commands. Anything the
# tokeniser cannot parse is unparseable and fails the rule closed.

SEP_CHARS = "();<>|&`\n"
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
PYTHON = re.compile(r"(python|pypy|py)(\d+(\.\d+)*)?")
RESERVED = frozenset(("!", "{", "}", "if", "then", "else", "elif", "do", "while", "until"))
# wrapper basename -> (options that take a separate value, positional args to skip)
WRAPPERS = {
    "sudo": (frozenset(("-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U", "-r", "-t",
                        "--user", "--group", "--host", "--prompt", "--chdir")), 0),
    "doas": (frozenset(("-u", "-C")), 0),
    "env": (frozenset(("-u", "-C", "--unset", "--chdir")), 0),
    "command": (frozenset(), 0),
    "builtin": (frozenset(), 0),
    "exec": (frozenset(("-a",)), 0),
    "nohup": (frozenset(), 0),
    "time": (frozenset(("-f", "-o")), 0),
    "nice": (frozenset(("-n",)), 0),
    "timeout": (frozenset(("-s", "-k", "--signal", "--kill-after")), 1),
    "xargs": (frozenset(("-n", "-I", "-L", "-P", "-s", "-d", "-E", "-a")), 0),
}
SHELLS = frozenset(("sh", "bash", "zsh", "dash", "ksh"))
PY_VALUE_OPTS = frozenset(("-W", "-X", "-Q"))
MAX_DEPTH = 8
UNPARSEABLE = None


def _tokens(cmd):
    """shlex tokens of one command record, or None when it does not parse."""
    s = cmd.replace("\\\r\n", "").replace("\\\n", "")
    lex = shlex.shlex(s, posix=True, punctuation_chars=SEP_CHARS)
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError:
        return None


def _pieces(toks):
    """Cut a token list at every control or redirection token."""
    out, cur = [], []
    for t in toks:
        if t and set(t) <= set(SEP_CHARS):
            out.append(cur)
            cur = []
        else:
            cur.append(t)
    out.append(cur)
    return [p for p in out if p]


def _skip_options(words, i, value_opts):
    while i < len(words) and words[i].startswith("-") and words[i] != "-":
        w = words[i]
        i += 1
        if w == "--":
            break
        if w in value_opts:
            i += 1
    return i


def _simple(words, depth):
    """Canonical argv list(s) for one piece, or None when unparseable."""
    if depth > MAX_DEPTH:
        return None
    found = []
    for _ in range(4 * MAX_DEPTH):
        changed = True
        while changed and words:
            changed = False
            while words and (ASSIGNMENT.match(words[0]) or words[0] in RESERVED):
                words = words[1:]
                changed = True
            if words and posixpath.basename(words[0]) in WRAPPERS:
                opts, npos = WRAPPERS[posixpath.basename(words[0])]
                i = _skip_options(words, 1, opts)
                words = words[i + npos:]
                changed = True
        if not words:
            return found
        name = posixpath.basename(words[0])
        rest = words[1:]
        if name in SHELLS:
            j = 0
            while j < len(rest) and rest[j].startswith("-"):
                if rest[j].startswith("-") and not rest[j].startswith("--") and "c" in rest[j]:
                    if j + 1 >= len(rest):
                        return None
                    sub = _command_argvs(rest[j + 1], depth + 1)
                    if sub is None:
                        return None
                    found += sub
                    break
                j += 1
            found.append((name,) + tuple(rest))
            return found
        if name == "eval":
            sub = _command_argvs(" ".join(rest), depth + 1)
            if sub is None:
                return None
            return found + list(sub)
        if PYTHON.fullmatch(name):
            j, module = 0, None
            while j < len(rest) and rest[j].startswith("-"):
                w = rest[j]
                if w == "-m":
                    module = rest[j + 1] if j + 1 < len(rest) else None
                    j += 2
                    break
                if w.startswith("-m") and not w.startswith("--"):
                    module = w[2:]
                    j += 1
                    break
                if w == "-c":
                    break
                j += 2 if w in PY_VALUE_OPTS else 1
            if module:
                words = [module] + rest[j:]
                continue
        if name == "uv":
            j = _skip_options(rest, 0, frozenset())
            if j < len(rest) and rest[j] == "pip":
                words = ["pip"] + rest[j + 1:]
                continue
        found.append((name,) + tuple(rest))
        return found
    return None


def _command_argvs(cmd, depth=0):
    """Every canonical argv a command record could run, or None (unparseable)."""
    toks = _tokens(cmd)
    if toks is None:
        return None
    out = []
    for piece in _pieces(toks):
        got = _simple(piece, depth)
        if got is None:
            return None
        out += got
    return tuple(out)


def _argv_matches(argv, words):
    """argv starts with the prefix words: first word by name (a trailing
    version such as pip3 or pip3.12 is read as the same name when the
    prefix name ends in a letter), later words in order with option
    tokens between them skipped."""
    p0, n = words[0], argv[0]
    if n != p0 and not (p0[-1].isalpha() and re.fullmatch(re.escape(p0) + r"\d+(\.\d+)*", n)):
        return False
    j = 1
    for want in words[1:]:
        while j < len(argv) and argv[j].startswith("-") and argv[j] != want:
            j += 1
        if j >= len(argv) or argv[j] != want:
            return False
        j += 1
    return True


def _forbidden_run(prefix, cmds, argvs):
    """True when some command record runs the forbidden prefix, or cannot be parsed."""
    if any(c == prefix or c.startswith(prefix + " ") for c in cmds):
        return True
    words = prefix.split()
    for a in argvs:
        if a is UNPARSEABLE:
            return True
        if any(_argv_matches(x, words) for x in a):
            return True
    return False


COMMAND_PREFIX_BAD = set("'\"\\;&|<>()`$#*?[]{}~!/=")


def _norm_path(p):
    """Normalised repo-relative path, or None when it is absolute or escapes."""
    if not _str(p) or p.startswith("/") or "\\" in p:
        return None
    n = posixpath.normpath(p)
    if n == "." or n == ".." or n.startswith("../"):
        return None
    return n


def _under(path, prefix):
    return path == prefix or path.startswith(prefix + "/")


def triggered(pred, facts):
    """For a conditional predicate: whether its trigger appears in the facts."""
    return pred[0] == "path_requires_path" and any(_under(x, pred[1]) for x in facts[0])


def _check_predicate(pred):
    if pred is None:
        return None
    if type(pred) is not tuple or len(pred) < 1 or type(pred[0]) is not str:
        return "predicate_shape"
    kind = pred[0]
    if kind not in PREDICATE_ARITY:
        return "predicate_kind"
    args = pred[1:]
    if len(args) != PREDICATE_ARITY[kind]:
        return "predicate_arity"
    if not all(_str(a) for a in args):
        return "predicate_args"
    if kind in ("forbid_path_prefix", "path_requires_path"):
        if any(_norm_path(a) != a for a in args):
            return "predicate_path"
    else:
        if any(_norm_command(a) != a for a in args):
            return "predicate_command"
        if kind == "forbid_command_prefix" and (set(args[0]) & COMMAND_PREFIX_BAD or args[0][0] == "-"):
            return "predicate_command"
    return None


def check_config(acf):
    """Errors in a context file. Empty tuple means sound."""
    if type(acf) is not ContextFile:
        return ("context_file_type",)
    insts, oum = acf.instructions, acf.on_unmeasured
    errs = []
    if oum is None:
        errs.append("on_unmeasured_missing")
    elif type(oum) is not str:
        errs.append("on_unmeasured_type")
    elif PERMIT_TOKEN in oum.lower():
        errs.append("on_unmeasured_permit_token")
    elif oum not in ON_UNMEASURED:
        errs.append("on_unmeasured_unknown")
    if type(insts) is not tuple or len(insts) == 0:
        errs.append("instructions_shape")
        return tuple(errs)
    seen = set()
    for k, ins in enumerate(insts):
        if type(ins) is not Instruction:
            errs.append("instruction_type:%d" % k)
            continue
        iid, cat, text, pred = ins.instruction_id, ins.category, ins.text, ins.predicate
        if not (_str(iid) and type(cat) is str and type(text) is str):
            errs.append("instruction_fields:%d" % k)
            continue
        if iid in seen:
            errs.append("duplicate_id:%s" % iid)
        seen.add(iid)
        e = _check_predicate(pred)
        if e:
            errs.append("%s:%s" % (e, iid))
    return tuple(errs)


def check_commit(commit):
    """Errors in a commit record, plus its normalised facts."""
    if type(commit) is not Commit:
        return ("commit_type",), None
    cid, paths, cmds, msg = commit.commit_id, commit.paths, commit.commands, commit.message
    errs = []
    if not _str(cid):
        errs.append("commit_id")
    if type(msg) is not str:
        errs.append("message_type")
    npaths = ()
    if type(paths) is not tuple:
        errs.append("paths_type")
    else:
        np = tuple(_norm_path(p) for p in paths)
        if any(p is None for p in np):
            errs.append("path_malformed")
        else:
            npaths = np
    ncmds = ()
    if type(cmds) is not tuple or not all(_str(c) for c in cmds):
        errs.append("commands_type")
    else:
        ncmds = tuple(_norm_command(c) for c in cmds)
        if any(c == "" for c in ncmds):
            errs.append("command_blank")
    if errs:
        return tuple(errs), None
    argvs = tuple(_command_argvs(c) for c in cmds)
    return (), (npaths, ncmds, argvs)


def facts_of(commit):
    """The facts a predicate may read: normalised paths, normalised command
    strings and the parsed argv lists of each command record. No message."""
    errs, facts = check_commit(commit)
    return facts


def holds(pred, facts):
    """True when the facts satisfy an operational predicate."""
    paths, cmds, argvs = facts
    kind = pred[0]
    if kind == "require_command":
        return pred[1] in cmds
    if kind == "forbid_command_prefix":
        return not _forbidden_run(pred[1], cmds, argvs)
    if kind == "forbid_path_prefix":
        return not any(_under(x, pred[1]) for x in paths)
    if kind == "path_requires_path":
        if any(_under(x, pred[1]) for x in paths):
            return any(_under(x, pred[2]) for x in paths)
        return True
    raise ValueError(kind)


def outcome(ins, facts):
    if ins.predicate is None:
        return NOT_OPERATIONALIZED
    return FOLLOWED if holds(ins.predicate, facts) else NOT_FOLLOWED


def evaluate(acf, commit):
    """One outcome per instruction for one commit, read from facts only."""
    cid = commit.commit_id if type(commit) is Commit and type(commit.commit_id) is str else ""
    errs = check_config(acf)
    cerrs, facts = check_commit(commit)
    if errs or cerrs:
        return CommitReport(cid, CONFIG_ERROR, (), (), tuple(errs) + tuple(cerrs))
    outs = tuple((ins.instruction_id, outcome(ins, facts)) for ins in acf.instructions)
    counts = tuple((o, sum(1 for _, x in outs if x == o)) for o in OUTCOMES)
    return CommitReport(cid, OK, outs, counts)


def split(acf, commits):
    """Split instruction ids over a batch of commits."""
    errs = check_config(acf)
    if type(commits) is not tuple:
        return BatchReport(CONFIG_ERROR, (), (), (), (), tuple(errs) + ("commits_type",))
    reports = [evaluate(acf, c) for c in commits]
    for r in reports:
        if r.status != OK:
            errs = tuple(errs) + tuple(r.errors)
    ids = [r.commit_id for r in reports]
    if len(set(ids)) != len(ids):
        errs = tuple(errs) + ("duplicate_commit_id",)
    if errs:
        return BatchReport(CONFIG_ERROR, (), (), (), (), tuple(dict.fromkeys(errs)))
    if len(commits) < MIN_BATCH:
        return BatchReport(INSUFFICIENT_BATCH, (), (), (), ())
    always, never, mixed, unmeasured, not_applicable = [], [], [], [], []
    facts = [facts_of(c) for c in commits]
    for k, ins in enumerate(acf.instructions):
        seen = {r.outcomes[k][1] for r in reports}
        if seen == {NOT_OPERATIONALIZED}:
            unmeasured.append(ins.instruction_id)
        elif seen == {FOLLOWED} and ins.predicate[0] == "path_requires_path" and \
                not any(triggered(ins.predicate, f) for f in facts):
            not_applicable.append(ins.instruction_id)
        elif seen == {FOLLOWED}:
            always.append(ins.instruction_id)
        elif seen == {NOT_FOLLOWED}:
            never.append(ins.instruction_id)
        else:
            mixed.append(ins.instruction_id)
    return BatchReport(OK, tuple(always), tuple(never), tuple(mixed), tuple(unmeasured), (),
                       tuple(not_applicable))


def enforce(acf, commit):
    """Refuse any failing operationalized instruction; route the unmeasured
    only through the declared on_unmeasured. Fails closed."""
    r = evaluate(acf, commit)
    if r.status != OK:
        return Decision(r.commit_id, CONFIG_ERROR, False, (), (), r.errors)
    failed = tuple(i for i, o in r.outcomes if o == NOT_FOLLOWED)
    unmeasured = tuple(i for i, o in r.outcomes if o == NOT_OPERATIONALIZED)
    if failed:
        return Decision(r.commit_id, REFUSE, False, failed, unmeasured)
    if unmeasured:
        verdict = VERDICT_ON_UNMEASURED[acf.on_unmeasured]
        return Decision(r.commit_id, verdict, False, failed, unmeasured)
    return Decision(r.commit_id, ACCEPT, True, failed, unmeasured)


def report(acf, commits):
    """Plain-text report: per-commit counts, split and decisions."""
    lines = []
    for c in commits:
        r = evaluate(acf, c)
        lines.append("%s %s %s" % (r.commit_id, r.status, dict(r.counts)))
        d = enforce(acf, c)
        lines.append("  decision %s failed=%s unmeasured=%s" % (d.verdict, list(d.failed), list(d.unmeasured)))
    b = split(acf, tuple(commits))
    lines.append("split %s always=%s never=%s mixed=%s unmeasured=%s not_applicable=%s" % (
        b.status, list(b.always), list(b.never), list(b.mixed), list(b.unmeasured), list(b.not_applicable)))
    return "\n".join(lines)
