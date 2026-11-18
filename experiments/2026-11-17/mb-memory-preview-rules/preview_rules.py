"""Enumerate the memory rules compatible with a permission preview (stdlib only).

A memory rule says when an assistant may reuse a remembered event. In this sketch a rule is a
pair (scope, kinds) from a small typed vocabulary. A preview is one use the rule permits and one
use it blocks. A rule is compatible with a preview when it permits the first use and blocks the
second. Everything is computed from the fixture; no network, clock, randomness or model.

Run: python3 -B preview_rules.py fixtures/memory_rules.json [--permitted USE --blocked USE]
Exit 0 with a report, exit 2 with "DENY <code>: <detail>" on stderr for a bad fixture or usage.
"""

import itertools
import json
import re
import sys
import unicodedata

SCOPES = ("same_task", "same_topic", "any_task")
KINDS = ("preference_only", "one_off_only", "any_kind")
EVENT_KINDS = ("preference", "one_off")
AUDIENCES = ("self", "others")
FIXTURE_VERSION = 1
MAX_TEXT = 200
ID_RE = re.compile(r"[a-z][a-z0-9_]{0,31}", re.ASCII)
BAD_TEXT_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp")


class FixtureError(Exception):
    """A malformed fixture or request. The CLI turns it into DENY with exit 2."""

    def __init__(self, code, detail):
        Exception.__init__(self, code + ": " + detail)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- strict JSON reading

def _no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise FixtureError("duplicate_key", "key %r appears twice in one object" % key)
        out[key] = value
    return out


def _reject_constant(name):
    raise FixtureError("non_finite_number", "%s is not a permitted value" % name)


def _reject_float(text):
    raise FixtureError("float_not_permitted", "%s: the fixture has no fractional numbers" % text)


def parse_fixture_text(text):
    if type(text) is not str:
        raise FixtureError("fixture_unreadable", "fixture text must be str")
    if text.startswith("\ufeff"):
        raise FixtureError("bom_not_permitted", "the fixture starts with a byte order mark")
    try:
        obj = json.loads(text, object_pairs_hook=_no_duplicate_keys,
                         parse_constant=_reject_constant, parse_float=_reject_float)
    except FixtureError:
        raise
    except (ValueError, RecursionError) as exc:
        raise FixtureError("malformed_json", str(exc))
    return validate_fixture(obj)


def load_fixture(path):
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        raise FixtureError("fixture_unreadable", "%s: %s" % (path, exc.strerror or exc))
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FixtureError("fixture_not_utf8", str(exc))
    return parse_fixture_text(text)


# ---------------------------------------------------------------- validation

def _object(value, keys, where):
    if type(value) is not dict:
        raise FixtureError("wrong_type", "%s must be an object" % where)
    for key in value:
        if type(key) is not str:
            raise FixtureError("wrong_type", "%s has a non-str key" % where)
    unknown = sorted(set(value) - set(keys))
    if unknown:
        raise FixtureError("unknown_key", "%s: %s" % (where, ", ".join(unknown)))
    missing = [k for k in keys if k not in value]
    if missing:
        raise FixtureError("missing_key", "%s: %s" % (where, ", ".join(missing)))
    return value


def _list(value, where):
    if type(value) is not list:
        raise FixtureError("wrong_type", "%s must be a list" % where)
    if not value:
        raise FixtureError("empty_list", "%s is empty" % where)
    return value


def _ident(value, where):
    if type(value) is not str:
        raise FixtureError("wrong_type", "%s must be a str" % where)
    if ID_RE.fullmatch(value) is None:
        raise FixtureError("bad_id", "%s: %r is not [a-z][a-z0-9_]{0,31}" % (where, value))
    return value


def _choice(value, options, where):
    if type(value) is not str:
        raise FixtureError("wrong_type", "%s must be a str" % where)
    if value not in options:
        raise FixtureError("unknown_value", "%s: %r not in %s" % (where, value, "/".join(options)))
    return value


def _text(value, where):
    if type(value) is not str:
        raise FixtureError("wrong_type", "%s must be a str" % where)
    if not value.strip() or value != value.strip() or len(value) > MAX_TEXT:
        raise FixtureError("bad_text", "%s: empty, padded or longer than %d" % (where, MAX_TEXT))
    if unicodedata.normalize("NFC", value) != value:
        raise FixtureError("bad_text", "%s: not in NFC form" % where)
    for ch in value:
        if unicodedata.category(ch) in BAD_TEXT_CATEGORIES:
            raise FixtureError("bad_text", "%s: control or invisible character U+%04X" % (where, ord(ch)))
    return value


def _unique(seen, value, where):
    if value in seen:
        raise FixtureError("duplicate_id", "%s: %r" % (where, value))
    seen.add(value)


def validate_fixture(obj):
    """Validate a parsed fixture and return a fresh snapshot (no references into obj)."""
    root = _object(obj, ("fixture_version", "vocabulary", "tasks", "events", "uses",
                         "intended", "previews"), "fixture")
    version = root["fixture_version"]
    if type(version) is not int or version != FIXTURE_VERSION:
        raise FixtureError("bad_version", "fixture_version must be the int %d" % FIXTURE_VERSION)

    vocab = _object(root["vocabulary"], ("scopes", "kinds"), "vocabulary")
    scopes = []
    for i, value in enumerate(_list(vocab["scopes"], "vocabulary.scopes")):
        scope = _choice(value, SCOPES, "vocabulary.scopes[%d]" % i)
        if scope in scopes:
            raise FixtureError("duplicate_id", "vocabulary.scopes: %r" % scope)
        scopes.append(scope)
    kinds = []
    for i, value in enumerate(_list(vocab["kinds"], "vocabulary.kinds")):
        kind = _choice(value, KINDS, "vocabulary.kinds[%d]" % i)
        if kind in kinds:
            raise FixtureError("duplicate_id", "vocabulary.kinds: %r" % kind)
        kinds.append(kind)
    rules = tuple((s, k) for s in scopes for k in kinds)

    tasks = {}
    seen = set()
    for i, item in enumerate(_list(root["tasks"], "tasks")):
        where = "tasks[%d]" % i
        row = _object(item, ("id", "topic"), where)
        tid = _ident(row["id"], where + ".id")
        _unique(seen, tid, "tasks")
        tasks[tid] = _ident(row["topic"], where + ".topic")

    events = {}
    seen = set()
    for i, item in enumerate(_list(root["events"], "events")):
        where = "events[%d]" % i
        row = _object(item, ("id", "kind", "origin_task", "text"), where)
        eid = _ident(row["id"], where + ".id")
        _unique(seen, eid, "events")
        origin = _ident(row["origin_task"], where + ".origin_task")
        if origin not in tasks:
            raise FixtureError("unknown_reference", "%s.origin_task: %r" % (where, origin))
        events[eid] = {"kind": _choice(row["kind"], EVENT_KINDS, where + ".kind"),
                       "origin_task": origin, "text": _text(row["text"], where + ".text")}

    uses = []
    use_by_id = {}
    triples = set()
    for i, item in enumerate(_list(root["uses"], "uses")):
        where = "uses[%d]" % i
        row = _object(item, ("id", "event", "task", "audience", "text"), where)
        uid = _ident(row["id"], where + ".id")
        if uid in use_by_id:
            raise FixtureError("duplicate_id", "uses: %r" % uid)
        event = _ident(row["event"], where + ".event")
        if event not in events:
            raise FixtureError("unknown_reference", "%s.event: %r" % (where, event))
        task = _ident(row["task"], where + ".task")
        if task not in tasks:
            raise FixtureError("unknown_reference", "%s.task: %r" % (where, task))
        audience = _choice(row["audience"], AUDIENCES, where + ".audience")
        triple = (event, task, audience)
        if triple in triples:
            raise FixtureError("duplicate_use", "%s repeats event, task and audience" % where)
        triples.add(triple)
        use = {"id": uid, "event": event, "task": task, "audience": audience,
               "text": _text(row["text"], where + ".text")}
        uses.append(use)
        use_by_id[uid] = use

    intended_row = _object(root["intended"], ("scope", "kinds"), "intended")
    intended = (_choice(intended_row["scope"], SCOPES, "intended.scope"),
                _choice(intended_row["kinds"], KINDS, "intended.kinds"))
    if intended not in rules:
        raise FixtureError("intended_not_in_vocabulary", "%s/%s" % intended)

    fx = {"rules": rules, "scopes": tuple(scopes), "kinds": tuple(kinds), "tasks": tasks,
          "events": events, "uses": tuple(uses), "use_by_id": use_by_id, "intended": intended,
          "previews": ()}

    previews = []
    seen = set()
    for i, item in enumerate(_list(root["previews"], "previews")):
        where = "previews[%d]" % i
        row = _object(item, ("id", "permitted", "blocked"), where)
        pid = _ident(row["id"], where + ".id")
        _unique(seen, pid, "previews")
        permitted = _ident(row["permitted"], where + ".permitted")
        blocked = _ident(row["blocked"], where + ".blocked")
        for uid in (permitted, blocked):
            if uid not in use_by_id:
                raise FixtureError("unknown_reference", "%s: use %r" % (where, uid))
        if permitted == blocked:
            raise FixtureError("same_use_twice", "%s shows %r as both permitted and blocked" % (where, permitted))
        if not permits(fx, intended, use_by_id[permitted]) or permits(fx, intended, use_by_id[blocked]):
            raise FixtureError("preview_contradicts_intended", "%s is not what the intended rule does" % where)
        previews.append({"id": pid, "permitted": permitted, "blocked": blocked})
    fx["previews"] = tuple(previews)
    return fx


# ---------------------------------------------------------------- semantics

def rule_name(rule):
    return "%s/%s" % rule


def permits(fx, rule, use):
    """True when rule permits reusing use's event in use's task for use's audience."""
    scope, kinds = rule
    event = fx["events"][use["event"]]
    if use["audience"] != "self":
        return False
    if kinds == "preference_only" and event["kind"] != "preference":
        return False
    if kinds == "one_off_only" and event["kind"] != "one_off":
        return False
    if scope == "same_task":
        return use["task"] == event["origin_task"]
    if scope == "same_topic":
        return fx["tasks"][use["task"]] == fx["tasks"][event["origin_task"]]
    return scope == "any_task"


def is_transfer(fx, use):
    """A transfer use reuses an event in a task other than the one it was remembered in."""
    return use["task"] != fx["events"][use["event"]]["origin_task"]


def _use(fx, uid):
    if type(uid) is not str or uid not in fx["use_by_id"]:
        raise FixtureError("unknown_use", "%r is not a use in the fixture" % (uid,))
    return fx["use_by_id"][uid]


def compatible(fx, permitted_id, blocked_id):
    """Every rule (in vocabulary order) that permits permitted_id and blocks blocked_id."""
    p = _use(fx, permitted_id)
    b = _use(fx, blocked_id)
    return [r for r in fx["rules"] if permits(fx, r, p) and not permits(fx, r, b)]


def scopes_of(rules):
    out = []
    for scope, _ in rules:
        if scope not in out:
            out.append(scope)
    return out


def verdict(rules, chosen):
    """What a confirmed preview says about the rule the person chose. Not proof unless IDENTIFIED."""
    if chosen not in rules:
        return "CONFLICT"
    if len(rules) == 1:
        return "IDENTIFIED"
    return "AMBIGUOUS"


def consistent(fx, rules, uids):
    """Rules that answer every listed use the way the intended rule does."""
    want = {uid: permits(fx, fx["intended"], _use(fx, uid)) for uid in uids}
    return [r for r in rules if all(permits(fx, r, _use(fx, u)) == want[u] for u in uids)]


def all_pairs(fx):
    """Every (permitted, blocked) preview the intended rule could show, with its compatible set."""
    yes = [u["id"] for u in fx["uses"] if permits(fx, fx["intended"], u)]
    no = [u["id"] for u in fx["uses"] if not permits(fx, fx["intended"], u)]
    return [(p, b, compatible(fx, p, b)) for p in yes for b in no], yes, no


def vacuous_blocked(fx):
    """Uses that no rule in the vocabulary permits: blocking them in a preview says nothing."""
    return [u["id"] for u in fx["uses"] if not any(permits(fx, r, u) for r in fx["rules"])]


def probe_table(fx, rules, exclude=()):
    """For each use not in exclude: which of rules permit it and which block it."""
    out = []
    for use in fx["uses"]:
        if use["id"] in exclude:
            continue
        yes = [r for r in rules if permits(fx, r, use)]
        no = [r for r in rules if not permits(fx, r, use)]
        out.append({"use": use["id"], "transfer": is_transfer(fx, use), "permit": yes,
                    "block": no, "separates": bool(yes) and bool(no)})
    return out


def smallest_probe_sets(fx):
    """Smallest sets of uses whose intended answers leave only the intended rule."""
    ids = [u["id"] for u in fx["uses"]]
    for size in range(1, len(ids) + 1):
        found = [combo for combo in itertools.combinations(ids, size)
                 if consistent(fx, fx["rules"], combo) == [fx["intended"]]]
        if found:
            return size, found
    return None, []


def indistinguishable(fx):
    """Groups of two or more rules that decide every fixture use the same way."""
    groups = {}
    for rule in fx["rules"]:
        key = tuple(permits(fx, rule, u) for u in fx["uses"])
        groups.setdefault(key, []).append(rule)
    return [g for g in groups.values() if len(g) > 1]


# ---------------------------------------------------------------- report

def _names(rules):
    return " ".join(rule_name(r) for r in rules) if rules else "-"


def report(fx):
    lines = []
    rules = fx["rules"]
    n = len(rules)
    lines.append("fixture: rules=%d (scopes=%d x kinds=%d) tasks=%d events=%d uses=%d previews=%d"
                 % (n, len(fx["scopes"]), len(fx["kinds"]), len(fx["tasks"]), len(fx["events"]),
                    len(fx["uses"]), len(fx["previews"])))
    lines.append("intended: " + rule_name(fx["intended"]))
    for use in fx["uses"]:
        by = [r for r in rules if permits(fx, r, use)]
        lines.append("use %s %s@%s %s: intended=%s permitted_by=%d/%d transfer=%s"
                     % (use["id"], use["event"], use["task"], use["audience"],
                        "permit" if permits(fx, fx["intended"], use) else "block", len(by), n,
                        "yes" if is_transfer(fx, use) else "no"))
    pairs, yes, no = all_pairs(fx)
    vac = vacuous_blocked(fx)
    lines.append("pairs under intended: %d (permitted %d x blocked %d)" % (len(pairs), len(yes), len(no)))
    lines.append("blocked uses no rule permits: %s" % (" ".join(vac) if vac else "-"))
    lines.append("pairs whose blocked use no rule permits: %d/%d"
                 % (sum(1 for _, b, _c in pairs if b in vac), len(pairs)))
    lines.append("pairs that identify the intended rule: %d/%d"
                 % (sum(1 for _, _b, c in pairs if verdict(c, fx["intended"]) == "IDENTIFIED"), len(pairs)))
    sizes = {}
    for _, _b, c in pairs:
        sizes[len(c)] = sizes.get(len(c), 0) + 1
    lines.append("compatible-set sizes: " + " ".join("%d:%d" % (k, sizes[k]) for k in sorted(sizes)))
    together = list(rules)
    for pv in fx["previews"]:
        comp = compatible(fx, pv["permitted"], pv["blocked"])
        together = [r for r in together if r in comp]
        lines.append("preview %s (%s permit, %s block): %d rules, %d scopes -> %s: %s"
                     % (pv["id"], pv["permitted"], pv["blocked"], len(comp), len(scopes_of(comp)),
                        verdict(comp, fx["intended"]), _names(comp)))
    lines.append("all previews together: %d rules, %d scopes -> %s: %s"
                 % (len(together), len(scopes_of(together)), verdict(together, fx["intended"]),
                    _names(together)))
    first = fx["previews"][0]
    left = compatible(fx, first["permitted"], first["blocked"])
    for row in probe_table(fx, left, (first["permitted"], first["blocked"])):
        after = consistent(fx, left, (row["use"],))
        lines.append("probe after %s: %s transfer=%s separates=%s scopes_left=%d (%s)"
                     % (first["id"], row["use"], "yes" if row["transfer"] else "no",
                        "yes" if row["separates"] else "no", len(scopes_of(after)),
                        " ".join(scopes_of(after))))
    size, sets = smallest_probe_sets(fx)
    if size is None:
        lines.append("smallest probe set identifying the intended rule: none")
    else:
        lines.append("smallest probe set identifying the intended rule: %d uses, %d sets: %s"
                     % (size, len(sets), " | ".join(",".join(s) for s in sets)))
    groups = indistinguishable(fx)
    lines.append("rule groups no fixture use can tell apart: %d%s"
                 % (len(groups), "".join(" [" + _names(g) + "]" for g in groups)))
    return lines


# ---------------------------------------------------------------- CLI

USAGE = "usage: preview_rules.py FIXTURE [--permitted USE --blocked USE]"


def _parse_args(argv):
    if not argv:
        raise FixtureError("usage", USAGE)
    path = None
    opts = {}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--permitted", "--blocked"):
            if arg in opts or i + 1 >= len(argv):
                raise FixtureError("usage", USAGE)
            opts[arg] = argv[i + 1]
            i += 2
            continue
        if arg.startswith("-") or path is not None:
            raise FixtureError("usage", USAGE)
        path = arg
        i += 1
    if path is None or len(opts) == 1:
        raise FixtureError("usage", USAGE)
    return path, opts


def main(argv, out=None, err=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    try:
        path, opts = _parse_args(list(argv))
        fx = load_fixture(path)
        if opts:
            comp = compatible(fx, opts["--permitted"], opts["--blocked"])
            lines = ["preview (%s permit, %s block): %d rules, %d scopes -> %s: %s"
                     % (opts["--permitted"], opts["--blocked"], len(comp), len(scopes_of(comp)),
                        verdict(comp, fx["intended"]), _names(comp))]
        else:
            lines = report(fx)
    except FixtureError as exc:
        err.write("DENY %s: %s\n" % (exc.code, exc.detail))
        return 2
    for line in lines:
        out.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
