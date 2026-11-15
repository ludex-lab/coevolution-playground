# w20-acf-adherence

Does an agent do what its context file says? An agent context file (an
AGENTS.md-like list of instructions) is checked against commits one
instruction at a time. Each instruction either has an operational predicate
over commit facts (paths touched, commands run) or is marked not
operationalized. The report says, per commit, which instructions were
followed, not followed or not measured; over a batch, which instruction ids
were always, never or sometimes followed; and an enforcement hook refuses a
commit that fails any measured instruction.

This is a method sketch of the measurement idea in
[arXiv 2611.13709](https://arxiv.org/abs/2611.13709) (Voria, Kashiwa,
Catolino and Palomba; CC BY 4.0; no code linked). It is not a
reproduction, not Team OS law and not village law. Clean-room Python 3
stdlib, synthetic deterministic data, no network, no model in the loop.

## Run

```
cd experiments/2026-11-11/w20-acf-adherence/
python3 -m unittest test_acf_adherence.py -v
python3 fixtures.py
python3 mutants.py
```

The source check in the tests reads the abs-page copy named in
`paper_evidence.json` from the directory in `$W20ACF_SOURCES`. There is no
default path: when the variable is unset (the normal case) the check is
skipped, so a plain run reports `Ran 65 tests` and `OK (skipped=1)`.

`mutants.py` applies one source-text mutation at a time in a temporary
copy of this directory, runs `fixtures.py` and the suite there, prints
killed or survived per mutant and a summary, and removes the copy. There
are two lists, reported separately:

- code mutants (85) change `acf_adherence.py`: not_operationalized
  counted as followed, predicates that read the message, mixed
  misclassified, enforcement that skips a failure, a missing, unknown or
  permit-token `on_unmeasured` accepted, loosened path and command
  matching, dropped batch and fail-closed type checks, and for the shell
  normaliser: each separator dropped, line continuation not joined, quoting
  ignored, unparseable records passed, VAR=val / reserved word / wrapper /
  wrapper option stripping dropped, basename, version suffix, `python -m`,
  `-mX`, `uv pip`, `sh -c` and `eval` handling dropped, the recursion bound
  removed, and the not_applicable marker dropped;
- world mutants (17) change the test world instead (`fixtures.py`
  or `test_acf_adherence.py`): compound forms dropped from the generator,
  an entry dropped or replaced in the review's bypass list, the
  tuple-subclass predicate fixture weakened to a plain tuple, the extra
  shell-form, legit, unparseable or pinned-gap lists thinned, the property
  seeds cut, and the untriggered-conditional fixture made triggered.

All 85 code mutants and all 17 world mutants are killed; none is marked
equivalent and every anchor matches exactly once.

## Records

| Record | Fields | Meaning |
|---|---|---|
| `Instruction` | `instruction_id, category, text, predicate` | `predicate` is a declarative check or `None` (not operationalized) |
| `ContextFile` | `instructions, on_unmeasured` | `on_unmeasured` in {`DENY`, `SAFE_FALLBACK`, `ESCALATE`, `HOLD`} |
| `Commit` | `commit_id, paths, commands, message` | paths and commands are the facts; the message is carried, never read by a check |

Predicate kinds, all over normalised facts:

| Kind | Followed when |
|---|---|
| `("require_command", cmd)` | `cmd` is one of the commands run (whitespace-normalised, exact) |
| `("forbid_command_prefix", p)` | no command record runs `p`, read through the shell normaliser below; an unparseable record counts as not followed |
| `("forbid_path_prefix", d)` | no touched path is `d` or lies under `d/` (component-wise, after `normpath`) |
| `("path_requires_path", t, r)` | if any touched path lies under `t`, some touched path lies under `r` |

A predicate cannot be a Python callable; it is data, so the only inputs a
check can see are the facts returned by `facts_of(commit)`: the normalised
paths, the whitespace-normalised command strings, and the argv lists the
shell normaliser parsed from each command record. The message is not among
them.

### Shell normaliser (forbid_command_prefix only)

A command record is read as a shell line, not as one string:

1. backslash-newline is joined;
2. the line is tokenised with `shlex` (POSIX quoting and escapes, no
   comments), so `'pip'`, `"pip"` and `p\ip` are all `pip`;
3. the tokens are cut at every control or redirection token
   (`&&`, `||`, `;`, `|`, `&`, newline, `(`, `)`, backticks, `<`, `>`);
4. each piece loses leading `VAR=val` assignments, the reserved words
   `! { } if then else elif do while until`, and transparent wrappers
   (`sudo`, `doas`, `env`, `command`, `builtin`, `exec`, `nohup`, `time`,
   `nice`, `timeout`, `xargs`) with their options, including the listed
   options that take a separate value;
5. the first word becomes its basename (`/usr/bin/pip`, `./venv/bin/pip`);
   `python`, `python3`, `python3.12`, `py`, `pypy` with `-m X` or `-mX`
   become `X`; `uv pip` becomes `pip`; `sh|bash|zsh|dash|ksh -c STRING` and
   `eval ...` are read again as command lines, at most 8 levels deep;
6. a piece runs the prefix when its first word equals the prefix's first
   word (or that word plus a version such as `pip3`, `pip3.12`, when the
   prefix word ends in a letter) and the later prefix words follow in
   order, with option tokens between them skipped (`pip -q install`).

The old string rule (normalised record equals `p` or starts with `p `) is
kept as well, so nothing refused before is accepted now. A record the
tokeniser cannot parse (an unbalanced quote) or that nests deeper than the
bound fails closed: the forbid rule is `not_followed` and the commit is
refused. Other predicate kinds do not read the parsed form, so an
unparseable record does not change them. `check_config` reports
`predicate_command` for a forbid prefix with quotes, shell punctuation,
`$`, `/`, `=`, a glob character, or a leading `-`.

`require_command` is unchanged: exact match on the whitespace-normalised
record, so `make test && make lint` and `cd a && make test` are not
followed (conservative).

## Check layer

- `check_config(acf)`: report every error in a context file; an empty tuple
  means sound.
- `evaluate(acf, commit)`: exactly one of `followed`, `not_followed`,
  `not_operationalized` per instruction, in file order, with counts that sum
  to the instruction count.
- `split(acf, commits)`: over a tuple of 3 or more commits, report
  instruction ids as `always`, `never` or `mixed`; instructions with no
  predicate go to `unmeasured` and never to `always`. Fewer than 3 commits:
  `insufficient_batch`, no split.
- `enforce(acf, commit)`: `refuse` if any measured instruction is not
  followed, whatever `on_unmeasured` says; otherwise, if anything is
  unmeasured, the declared `on_unmeasured` decides (`DENY` -> `refuse`,
  `HOLD` -> `hold`, `ESCALATE` -> `escalate`, `SAFE_FALLBACK` ->
  `safe_fallback`); only a commit with every instruction measured and
  followed is `accept`. `accepted` is true only for `accept`.
- `report(acf, commits)`: plain-text report of the above.

## Silence doctrine

Taken from merged
[#78 w14-silence-expiry](https://cursor.com/codebase/coevolution-lab/playground/pull/78),
applied to measurement:

- an instruction that cannot be measured is never counted as followed;
- `on_unmeasured` must be declared even when every instruction is measured;
  a missing value is `config_error` and nothing is evaluated;
- the permit token, in any case and anywhere in the value, is
  `config_error`; so is any value outside the four names (exact, upper
  case), a non-`str`, or a `str` subclass;
- none of the four declared values leads to `accept`.

## Done-when, as tests

| | Requirement | Tests |
|---|---|---|
| (a) | per commit, every instruction is exactly one of followed / not_followed / not_operationalized; counts sum to the instruction count; not_operationalized never counted as followed | `DoneWhenA.*`: design and all generated property commits, an all-unmeasured file, adversarial facts, malformed commits. The F4 marker does not change this: it is a batch-split bucket only |
| (b) | over 3 or more commits, ids split into always / never / mixed; the fixture has one of each | `DoneWhenB.test_design_split_has_one_of_each` (I1 always, I3 never, I2 mixed, I4 and I5 unmeasured), `test_property_splits`, `test_split_is_a_partition`, `test_small_batch_is_not_split`, `test_bad_batch_fails_closed`; `NotApplicableF4.*` |
| (c) | predicates read facts, not the message; a commit whose message claims compliance but whose facts violate is refused | `DoneWhenC.*`: the lying commit is refused, a confessing commit with clean facts is accepted, random messages never change an outcome, and the check-layer source never reads `message` |
| (d) | enforcement refuses any failing measured instruction; unmeasured only via declared `on_unmeasured`; missing -> config_error; permit token -> config_error | `DoneWhenD.*` (including `test_tuple_subclass_predicate_is_config_error`); `ForbidCommandF1.*` for a "never run X" rule read through shell syntax |
| (e) | paper compliance rates UNVERIFIED | `DoneWhenE.*`: claims in `paper_evidence.json` all UNVERIFIED, no rates recorded, no percent figures in docs or code, offsets checked against the abs-page copy |

Hygiene tests: banned words (held as sha256 digests of the lowercase words
and compared against every substring of every `[a-z]+` token, so no
banned word is written here, whole or in parts), the permit token,
conflict markers, an import whitelist (no network, subprocess or model
imports in the module, the fixtures or the tests). `mutants.py` itself uses `subprocess` to run the
suite and is outside that whitelist.

## Fixtures

- Design (`fixtures.DESIGN_*`): five instructions (run `make test`; nothing
  under `secrets/`; `CHANGELOG.md` with any `src/` change; two style and
  process instructions with no predicate) and three commits. One commit's
  message claims full compliance while it touches `secrets/token.txt`.
- Adversarial facts: a dot-dot path into `secrets/`, look-alike directories
  (`secretsx/`, `docs/secrets`), `make test || true`, `echo make test`, a
  look-alike changelog, an empty commit.
- Malformed commits (all `config_error`): absolute, escaping, `.` and
  backslash paths, a list for paths, a blank command, an empty id, a
  non-`str` message.
- Forbid-command worlds (`fixtures.PIP_*`, `VERDICT_BYPASSES`): the 17
  forms the round-1 review found accepted (pinned by count and digest),
  the forms refused before, more shell forms the normaliser reads
  through, unparseable records, legit commands that stay accepted, and the
  pinned gaps below.
- Generated property cases (`fixtures.PROPERTY_CASES`): twelve cases from
  seeds 3101-3112. This is a seeded property test, not a held-out set: the
  generator passes for any seed (the suite also runs seeds 1-40). It plants
  the outcome of every (instruction, commit) cell, then writes facts that
  realise it, with near-miss decoys, compound shell commands
  (`FORBID_BREAK_FORMS`, `FORBID_FOLLOW_FORMS`: `&&`, `||`, `;`, `|`,
  `sudo`, `env`, `VAR=val`, quoting, absolute paths, `python -m`, line
  continuation) and claiming messages. A planted always conditional is
  triggered at least once; a planted untriggered one (followed in every
  commit, trigger never touched) is expected under `not_applicable`. Each case also has enforcement probes outside the
  batch: one clean commit, and one commit per measured instruction where
  only that instruction fails. `on_unmeasured` cycles through the four
  values by seed; every third seed has a fully measured file, so `accept`
  is reachable.

## Overlap with earlier experiments

- [#109 w19-guardrail-order](https://cursor.com/codebase/coevolution-lab/playground/pull/109)
  (merged, `experiments/2026-11-10/w19-guardrail-order/`) checks what
  actually ran instead of what the config says. Same stance here: the check
  reads the commit's facts, never the commit's account of itself. What
  differs: there the question is stage order on a decision path; here it is
  compliance with each instruction of a context file.
- [#110 w19-authz-drift](https://cursor.com/codebase/coevolution-lab/playground/pull/110)
  (open, head `56f5dc38`; read only) derives which grant limit (data, tool,
  scope, time) each step exceeded. Here the limits are the project's own
  written instructions, and the new parts are per-instruction
  operationalizability (an instruction may be unmeasurable, and that is
  reported, never passed) and the always / never / mixed split across
  commits.
- [#78 w14-silence-expiry](https://cursor.com/codebase/coevolution-lab/playground/pull/78)
  (merged) is the source of the four declared values and
  the rule that a missing declaration is `config_error`.

## Not included

No signing, keyed hashes or ledger; no SQLite; no daemon, thread or network;
no language-model API; no voting; no measurement scripts, data or snapshots
from the paper.

## Limitations

- Synthetic and deterministic. Nothing here measures a real coding agent or
  a real context file, and no count here says anything about any agent.
- Four predicate kinds only. Instructions about code quality, tone or
  design stay unmeasured, and the sketch's answer to them is the declared
  `on_unmeasured`, which in practice may hold or refuse most commits.
- Facts are trusted as given. Who records paths and commands, and whether
  that record is complete, is out of scope; a command run outside the
  record is invisible.
- The shell normaliser is a reading of common shell syntax, not a shell.
  `forbid_command_prefix` is a lint over recorded command strings, not a
  security boundary: a prefix rule cannot stand in for a sandbox, and
  forms not named here may still run an install in substance and be
  accepted. These forms are still accepted under a `pip install` rule;
  each is pinned by `ForbidCommandF1.test_pinned_gaps_are_still_accepted`
  or `ForbidCommandF1.test_further_pinned_gaps_are_still_accepted`:
  - variable expansion: `$P install x`, `P=pip; $P install x`;
  - aliases, functions and scripts: `alias p=pip; p install x`,
    `./scripts/setup.sh`;
  - code that calls the tool: `python3 -c 'import pip'`;
  - `env -S` string splitting: `env -S 'pip install x'`;
  - an option with a separate value before the subcommand:
    `pip --proxy http://h:1 install x`;
  - case: `PIP install x` (case-sensitive, like the file system);
  - other installers that run the tool: `pipx run pip install x`;
  - a pipe into a shell: `echo pip install x | sh`;
  - a here-string into a shell: `sh <<< 'pip install x'`;
  - `find -exec`: `find . -name req.txt -exec pip install -r {} ;`;
  - wrappers outside the eleven the normaliser reads (`stdbuf`,
    `ionice`, `chronic`, `watch`, `strace`) are treated as the command
    name: `stdbuf -oL pip install x`;
  - ANSI-C quoting: `$'pip' install x`;
  - the `function` keyword form: `function f { pip install x; }; f`;
  - a `python -m` path that is not exactly `pip`:
    `python3 -m pip.__main__ install x`.
  `pip download x` and `pip==1 install` are not `pip install` and are
  accepted on purpose. Wrapper options that take a separate value and are
  not in the module's list are read as the command name.
- The normaliser over-reads on purpose: a quoted separator token
  (`echo ';' pip install`) and a redirect target are cut like real ones,
  and `# comments` are not stripped, so some harmless lines are refused.
  An apostrophe in unquoted text or in a comment (`echo it's done`) makes
  the record unparseable, so the forbid rule fails closed and the commit
  is refused under any `forbid_command_prefix` rule, not only
  `pip install`.
- The normaliser treats `!`, `{` and the other listed reserved words as
  prefixes wherever they start a piece; the `while`/`until` condition is
  read as a command like any other piece.
- Path matching is component-wise after `normpath`; symlinks, case-folding
  file systems, renames and Unicode look-alikes or zero-width characters
  (`secrets\u200b/x`) are not modelled: `Secrets/x` and that form are not
  under `secrets`.
- Per commit, every operational predicate still yields followed or not
  followed, so a conditional whose trigger is absent is followed in that
  commit and does not block it. Over a batch, a conditional that is
  followed in every commit and never triggered is reported under
  `not_applicable`, not `always` (F4). The per-commit partition and counts
  of done-when (a) are unchanged.

## Paper figures

The abstract states no numeric compliance rate. Its qualitative findings
are recorded only in `paper_evidence.json`, as offsets, lengths and span
hashes in the abstract field, and are marked UNVERIFIED. The PDF was not
read.

## Round 2 changes

- F1: `forbid_command_prefix` reads command records through the shell
  normaliser; the 17 review bypasses are refused and tested one by one;
  unparseable records fail closed (refuse); remaining gaps are listed
  above and pinned by tests.
- F2: the source check is env-only; no default path, no reviewer path,
  and the banned-word test holds digests, not words built from parts.
- F3: a tuple-subclass predicate is `config_error` (`predicate_shape`),
  now pinned by a test.
- F4: `BatchReport.not_applicable` for untriggered conditionals.
- F5: "held-out" is renamed to generated property cases, and the
  generator emits compound shell commands.
- `mutants.py` gains normaliser mutants and a separate list of world
  mutants.

## Documentation follow-up

Documentation and tests only; the normaliser is unchanged.

- Named further accepted install forms in Limitations (a pipe or
  here-string into a shell, `find -exec`, wrappers outside the listed
  eleven, ANSI-C quoting, the `function` keyword, and
  `python3 -m pip.__main__`) and pinned one example of each.
- Stated that `forbid_command_prefix` is a lint, not a security
  boundary.
- Documented the apostrophe over-refusal under any command-prefix
  rule, and pinned the `Secrets/x` path-case limit.

## Builder reflection

Writing predicates as data instead of functions made the facts-only rule a
property of the design, not a promise. The hardest part was deciding what an
unmeasurable instruction means for enforcement: counting it as followed
would make every unmeasured line a silent pass, so it falls to a declared
value instead. The property generator plants outcomes first and builds facts
second, so the expected labels stay independent of the code under test;
round 2 showed that a "never run X" rule is only as good as its reading of
the shell line.

Ludex: a note that says "I followed the rules" is a claim; the footprints
are the evidence.

Implementation may be complete; it is not declared verified.
