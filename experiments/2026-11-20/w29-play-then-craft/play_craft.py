"""w29-play-then-craft: a play-then-revise loop on one tiny deterministic game.

Method sketch of the play-and-craft idea in arXiv 2611.26624 (clean room: abstract page only, no code was
read or copied). Stdlib only, no network, no model call, no randomness, no clock, no files written.

Scripted players at three declared levels play a small two-path game. Each episode yields a report object.
A crafter reads only those reports and may change only declared integer knobs, inside their range, toward a
target that was declared before any episode. A fresh evaluation with new players scores the revised game
against the target band. The improvement in the shipped fixture is fixture-authored: the knobs were chosen
so that the loop works. All metrics are exact fractions.
"""

import fractions
import json
import re
import sys
import unicodedata

FIXTURE_VERSION = 1
ROLES = ("cue", "reserve")
LEVEL_COUNT = 3
KNOB_COUNT = 2
ON_EXPIRY = ("HOLD", "ESCALATE", "DENY")
MAX_BYTES = 200000
MIN_EPISODES = 3
MAX_EPISODES = 50
MAX_ROUNDS = 10
MAX_COST = 1000
MAX_KNOB = 1000
MAX_SMALL = 100
MAX_LABEL = 80
ID_RE = re.compile(r"[A-Za-z0-9_\uAC00-\uD7A3\u1100-\u1112\u1161-\u1175\u11A8-\u11C2]{1,40}")
BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp", "Zs")
BLOCKED_CODEPOINTS = frozenset((0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x2800, 0x3164, 0xFFA0))
Fraction = fractions.Fraction

SCOPE_NOTE = ("the improvement is fixture-authored by construction: the knobs were chosen so that the loop works; "
              "nothing here says the revised game is engaging, and no paper number is reproduced")


class PlayError(Exception):
    """Malformed input or a refused step: the CLI prints one ERROR line on stderr and exits 2."""

    def __init__(self, code, detail):
        Exception.__init__(self, "%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


class DenyError(PlayError):
    def __init__(self, name, detail):
        PlayError.__init__(self, "DENY " + name, detail)


def _esc(value):
    return json.dumps(str(value), ensure_ascii=True)


# ---------------------------------------------------------------- strict loading

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise PlayError("duplicate_key", "key %s is repeated" % _esc(key))
        out[key] = value
    return out


def _constant(name):
    raise PlayError("bad_number", "%s is not a finite number" % _esc(name))


def parse(text):
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except PlayError:
        raise
    except (ValueError, RecursionError, OverflowError):
        raise PlayError("not_json", "input is not valid JSON")


def _obj(value, keys, where):
    if type(value) is not dict:
        raise PlayError("wrong_type", "%s must be an object" % where)
    missing = [k for k in keys if k not in value]
    if missing:
        raise PlayError("missing_key", "%s lacks %s" % (where, _esc(missing[0])))
    unknown = sorted(set(value) - set(keys))
    if unknown:
        raise PlayError("unknown_key", "%s has unknown key %s" % (where, _esc(unknown[0])))
    return value


def _int(value, where, low, high):
    if type(value) is not int:
        raise PlayError("wrong_type", "%s must be an integer" % where)
    if not low <= value <= high:
        raise PlayError("bad_value", "%s must be from %d to %d" % (where, low, high))
    return value


def _id(value, where):
    if type(value) is not str or ID_RE.fullmatch(value) is None:
        raise PlayError("bad_id", "%s must be 1 to 40 letters, digits, underscores or Hangul" % where)
    return value


def _label(value, where):
    if type(value) is not str or not 1 <= len(value) <= MAX_LABEL:
        raise PlayError("wrong_type", "%s must be text of 1 to %d characters" % (where, MAX_LABEL))
    for ch in value:
        if ch == " ":
            continue
        if ord(ch) in BLOCKED_CODEPOINTS or unicodedata.category(ch) in BAD_CATEGORIES:
            raise PlayError("bad_text", "%s holds a control, invisible or unassigned character" % where)
    if value != value.strip(" "):
        raise PlayError("bad_text", "%s has a leading or trailing space" % where)
    return value


def _unique_ids(names, where):
    seen = set()
    for name in names:
        key = unicodedata.normalize("NFC", name)
        if key in seen:
            raise PlayError("duplicate_name", "%s repeats an id (compared after NFC)" % where)
        seen.add(key)


def _levels(value):
    if type(value) is not dict or len(value) != LEVEL_COUNT:
        raise PlayError("bad_levels", "levels must be an object of exactly %d levels" % LEVEL_COUNT)
    ids = [_id(k, "level id") for k in value]
    _unique_ids(ids, "levels")
    out = []
    for lid in ids:
        where = "levels.%s" % _esc(lid)
        spec = _obj(value[lid], ("label", "patience", "sign_weight"), where)
        out.append({"id": lid, "label": _label(spec["label"], where + ".label"),
                    "patience": _int(spec["patience"], where + ".patience", 0, MAX_SMALL),
                    "sign_weight": _int(spec["sign_weight"], where + ".sign_weight", 0, MAX_SMALL)})
    return out


def _knobs(value):
    if type(value) is not dict or len(value) != KNOB_COUNT:
        raise PlayError("bad_knob", "knobs must be an object of exactly %d knobs" % KNOB_COUNT)
    ids = [_id(k, "knob id") for k in value]
    _unique_ids(ids, "knobs")
    out = []
    for kid in ids:
        where = "knobs.%s" % _esc(kid)
        spec = _obj(value[kid], ("label", "role", "min", "max", "step", "initial"), where)
        if type(spec["role"]) is not str or spec["role"] not in ROLES:
            raise PlayError("bad_roles", "%s role must be one of %s" % (where, ", ".join(ROLES)))
        knob = {"id": kid, "label": _label(spec["label"], where + ".label"), "role": spec["role"],
                "min": _int(spec["min"], where + ".min", 0, MAX_KNOB),
                "max": _int(spec["max"], where + ".max", 0, MAX_KNOB),
                "step": _int(spec["step"], where + ".step", 1, MAX_KNOB),
                "initial": _int(spec["initial"], where + ".initial", 0, MAX_KNOB)}
        if knob["min"] > knob["max"]:
            raise PlayError("bad_knob", "%s min is above max" % where)
        if (knob["max"] - knob["min"]) % knob["step"] != 0:
            raise PlayError("bad_knob", "%s max is not on the step grid" % where)
        if not knob["min"] <= knob["initial"] <= knob["max"] or (knob["initial"] - knob["min"]) % knob["step"] != 0:
            raise PlayError("bad_knob", "%s initial is outside the range or off the step grid" % where)
        out.append(knob)
    if sorted(k["role"] for k in out) != sorted(ROLES):
        raise PlayError("bad_roles", "knobs must hold one cue and one reserve knob")
    return out


def _game(value):
    game = _obj(value, ("long_cost", "short_cost", "step_cap", "episodes", "max_rounds", "no_report"), "game")
    out = {"long_cost": _int(game["long_cost"], "game.long_cost", 1, MAX_COST),
           "short_cost": _int(game["short_cost"], "game.short_cost", 1, MAX_COST),
           "step_cap": _int(game["step_cap"], "game.step_cap", 1, MAX_COST),
           "episodes": _int(game["episodes"], "game.episodes", MIN_EPISODES, MAX_EPISODES),
           "max_rounds": _int(game["max_rounds"], "game.max_rounds", 1, MAX_ROUNDS)}
    silent = game["no_report"]
    if type(silent) is not list or len(silent) > out["episodes"]:
        raise PlayError("wrong_type", "game.no_report must be a list of episode numbers")
    silent = [_int(n, "game.no_report item", 1, out["episodes"]) for n in silent]
    if len(set(silent)) != len(silent):
        raise PlayError("duplicate_name", "game.no_report repeats an episode number")
    out["no_report"] = sorted(silent)
    return out


def _target(value, level_ids, episodes):
    target = _obj(value, ("level", "band"), "target")
    level = _id(target["level"], "target.level")
    if level not in level_ids:
        raise PlayError("unknown_level", "target.level is not a declared level")
    band = _obj(target["band"], ("lo", "hi"), "target.band")
    lo = _int(band["lo"], "target.band.lo", 1, episodes)
    hi = _int(band["hi"], "target.band.hi", 1, episodes)
    if lo > hi:
        raise PlayError("bad_band", "target.band.lo is above target.band.hi")
    return {"level": level, "band": {"lo": lo, "hi": hi}}


def validate(root):
    root = _obj(root, ("fixture_version", "label", "game", "knobs", "levels", "target", "on_expiry", "crafter"),
                "fixture")
    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:
        raise PlayError("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    label = _label(root["label"], "label")
    game = _game(root["game"])
    knobs = _knobs(root["knobs"])
    levels = _levels(root["levels"])
    target = _target(root["target"], [lv["id"] for lv in levels], game["episodes"])
    if type(root["on_expiry"]) is not str or root["on_expiry"] not in ON_EXPIRY:
        raise PlayError("bad_on_expiry", "on_expiry must be one of %s" % ", ".join(ON_EXPIRY))
    if type(root["crafter"]) is not str or root["crafter"] not in CRAFTERS:
        raise PlayError("unknown_crafter", "crafter must be one of %s" % ", ".join(sorted(CRAFTERS)))
    return {"label": label, "game": game, "knobs": knobs, "levels": levels, "target": target,
            "on_expiry": root["on_expiry"], "crafter": root["crafter"]}


def load_fixture(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_BYTES + 1)
    except OSError:
        raise PlayError("unreadable", "file could not be read")
    if len(data) > MAX_BYTES:
        raise PlayError("too_large", "file is larger than %d bytes" % MAX_BYTES)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise PlayError("bad_encoding", "file is not valid UTF-8")
    return validate(parse(text))


# ---------------------------------------------------------------- the game and its players

def _clone(obj):
    if type(obj) is dict:
        return {k: _clone(v) for k, v in obj.items()}
    if type(obj) is list:
        return [_clone(v) for v in obj]
    return obj


def _same(a, b):
    """Strict structural equality: types must match too, so True is not 1."""
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return sorted(a) == sorted(b) and all(_same(a[k], b[k]) for k in a)
    if type(a) is list:
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def knob_of(fx, role):
    for knob in fx["knobs"]:
        if knob["role"] == role:
            return knob
    raise PlayError("bad_roles", "no knob has role %s" % role)


def initial_params(fx):
    return {k["id"]: k["initial"] for k in fx["knobs"]}


def fresh_memory():
    return {"long_fails": 0}


def effective_patience(level, cue):
    return max(0, level["patience"] - level["sign_weight"] * cue)


def choose_path(level, cue, memory):
    """A player takes the short path once its failures on the long path reach its effective patience."""
    return "short" if memory["long_fails"] >= effective_patience(level, cue) else "long"


def play_episode(fx, level, params, memory, episode):
    """One episode. Returns a record: held is None when a usable report exists, else the reason."""
    game = fx["game"]
    cue = params[knob_of(fx, "cue")["id"]]
    budget = params[knob_of(fx, "reserve")["id"]]
    path = choose_path(level, cue, memory)
    cost = game["long_cost"] if path == "long" else game["short_cost"]
    needed = min(cost, budget)
    report = {"level": level["id"], "episode": episode, "decisions": [path],
              "switched": path == "short" and memory["long_fails"] > 0}
    if needed > game["step_cap"]:
        report.update({"outcome": "capped", "steps": game["step_cap"], "progress_num": game["step_cap"],
                       "progress_den": cost, "capped": True})
        return {"level": level["id"], "episode": episode, "report": report, "held": "step_cap"}
    outcome = "clear" if cost <= budget else "fail"
    report.update({"outcome": outcome, "steps": needed, "progress_num": needed, "progress_den": cost,
                   "capped": False})
    if path == "long" and outcome == "fail":
        memory["long_fails"] += 1
    if episode in game["no_report"]:
        return {"level": level["id"], "episode": episode, "report": None, "held": "no_report"}
    return {"level": level["id"], "episode": episode, "report": report, "held": None}


def play_session(fx, level, params, memory, episodes):
    return [play_episode(fx, level, params, memory, k) for k in range(1, episodes + 1)]


def held_episodes(records):
    return [{"level": r["level"], "episode": r["episode"], "reason": r["held"]} for r in records if r["held"]]


def first_clear(reports):
    for r in reports:
        if r["outcome"] == "clear":
            return r["episode"]
    return None


def band_verdict(first, band):
    if first is None or first > band["hi"]:
        return "too_hard"
    if first < band["lo"]:
        return "too_easy"
    return "in_band"


# ---------------------------------------------------------------- the crafter and its rules

def make_view(reports, knobs, params, target):
    """The only thing a crafter may read: report objects, the declared knob table, the current values, the target."""
    return {"reports": _clone(reports),
            "knobs": [{"id": k["id"], "role": k["role"], "min": k["min"], "max": k["max"], "step": k["step"]}
                      for k in knobs],
            "params": dict(params), "target": _clone(target)}


def _move(view, role, direction):
    for knob in view["knobs"]:
        if knob["role"] != role:
            continue
        current = view["params"][knob["id"]]
        new = current + direction * knob["step"]
        if knob["min"] <= new <= knob["max"]:
            return {knob["id"]: new}
    return None


def crafter_ladder(view):
    """Reads reports only. Too hard: reserve up when the short path was reached and still failed, else cue up.
    Too easy: cue down, then reserve down. In band: no change."""
    target = view["target"]
    band = target["band"]
    mine = [r for r in view["reports"] if r["level"] == target["level"]]
    if not mine:
        return {"target": target, "changes": {}, "why": "no_reports"}
    verdict = band_verdict(first_clear(mine), band)
    if verdict == "in_band":
        return {"target": target, "changes": {}, "why": "in_band"}
    if verdict == "too_hard":
        reached_short_and_failed = any(r["outcome"] == "fail" and r["decisions"][0] == "short" for r in mine)
        order = ("reserve", "cue") if reached_short_and_failed else ("cue", "reserve")
        why = "no_reserve" if reached_short_and_failed else "missed_cue"
        direction = 1
    else:
        order = ("cue", "reserve")
        why = "too_easy"
        direction = -1
    for role in order:
        change = _move(view, role, direction)
        if change is not None:
            return {"target": target, "changes": change, "why": why}
    return {"target": target, "changes": {}, "why": "ladder_exhausted"}


def crafter_noop(view):
    return {"target": view["target"], "changes": {}, "why": "noop"}


def crafter_overtune(view):
    changes = {k["id"]: k["max"] for k in view["knobs"]}
    return {"target": view["target"], "changes": changes, "why": "overtune"}


def crafter_edits_target(view):
    target = _clone(view["target"])
    target["band"]["hi"] = target["band"]["hi"] + 1
    return {"target": target, "changes": {}, "why": "edits_target"}


def crafter_wild_knob(view):
    return {"target": view["target"], "changes": {"not_a_declared_knob": 1}, "why": "wild_knob"}


def crafter_out_of_range(view):
    knob = view["knobs"][0]
    return {"target": view["target"], "changes": {knob["id"]: knob["max"] + knob["step"]}, "why": "out_of_range"}


CRAFTERS = {
    "ladder": crafter_ladder,
    "noop": crafter_noop,
    "overtune": crafter_overtune,
    "edits_target": crafter_edits_target,
    "wild_knob": crafter_wild_knob,
    "out_of_range": crafter_out_of_range,
}


def check_proposal(declared, knobs, params, proposal):
    """DENY unless the proposal names the declared target and changes only declared knobs inside their range."""
    if type(proposal) is not dict or sorted(proposal) != ["changes", "target", "why"]:
        raise DenyError("bad_proposal", "a proposal must hold exactly target, changes and why")
    if not _same(proposal["target"], declared):
        raise DenyError("target_not_declared", "the proposal target is not the target declared before any episode")
    changes = proposal["changes"]
    if type(changes) is not dict:
        raise DenyError("bad_proposal", "changes must be an object")
    by_id = {k["id"]: k for k in knobs}
    for name in sorted(changes):
        knob = by_id.get(name)
        if knob is None:
            raise DenyError("knob_undeclared", "knob %s is not declared" % _esc(name))
        value = changes[name]
        if type(value) is not int:
            raise DenyError("knob_bad_value", "knob %s needs an integer value" % _esc(name))
        if not knob["min"] <= value <= knob["max"]:
            raise DenyError("knob_out_of_range", "knob %s must stay from %d to %d" % (_esc(name), knob["min"], knob["max"]))
        if (value - knob["min"]) % knob["step"] != 0:
            raise DenyError("knob_off_step", "knob %s is off its step grid" % _esc(name))
    new = dict(params)
    new.update(changes)
    return new


# ---------------------------------------------------------------- the loop

def _expire(fx, held):
    """A capped or report-less episode: on_expiry says what happens. It is never a clear and licenses no craft."""
    action = fx["on_expiry"]
    if action == "DENY":
        first = held[0]
        raise DenyError("episode_held", "level %s episode %d has %s" % (_esc(first["level"]), first["episode"], first["reason"]))
    return action


def _expire_rounds(fx):
    """The round cap was reached before the revision settled: on_expiry says what happens."""
    if fx["on_expiry"] == "DENY":
        raise DenyError("rounds_exhausted", "the crafting rounds ran out before the revision settled")
    return fx["on_expiry"]


def crafting_round(fx, params):
    memories = {}
    reports = []
    held = []
    for level in fx["levels"]:
        memories[level["id"]] = fresh_memory()
        records = play_session(fx, level, params, memories[level["id"]], fx["game"]["episodes"])
        held.extend(held_episodes(records))
        reports.extend(r["report"] for r in records if r["held"] is None)
    return reports, held, memories


def _stats(clears, episodes):
    """clears: list of 0/1 per episode. Formulas are this sketch's own definitions."""
    third = max(1, episodes // 3)
    first_rate = Fraction(sum(clears[:third]), third)
    last_rate = Fraction(sum(clears[-third:]), third)
    xs = list(range(1, episodes + 1))
    sx = sum(xs)
    sy = sum(clears)
    sxy = sum(x * y for x, y in zip(xs, clears))
    sxx = sum(x * x for x in xs)
    slope = Fraction(episodes * sxy - sx * sy, episodes * sxx - sx * sx)
    curve = [Fraction(sum(clears[:k]), k) for k in range(1, episodes + 1)]
    return {"curve": curve, "gain": last_rate - first_rate, "slope": slope,
            "first_third": first_rate, "last_third": last_rate}


def evaluate(fx, params, memories=None):
    """A fresh evaluation: new players with empty memory. `memories` exists only so a deliberately leaky run can
    be shown for contrast; the loop never passes it."""
    episodes = fx["game"]["episodes"]
    levels = {}
    held = []
    for level in fx["levels"]:
        memory = fresh_memory() if memories is None else memories[level["id"]]
        records = play_session(fx, level, params, memory, episodes)
        held.extend(held_episodes(records))
        clears = [1 if (r["held"] is None and r["report"]["outcome"] == "clear") else 0 for r in records]
        stats = _stats(clears, episodes)
        first = None
        for r in records:
            if r["held"] is None and r["report"]["outcome"] == "clear":
                first = r["episode"]
                break
        stats["first_clear"] = first
        stats["episodes"] = [_episode_line(r) for r in records]
        levels[level["id"]] = stats
    return {"levels": levels, "held": held}


def _episode_line(record):
    rep = record["report"]
    if rep is None:
        return {"episode": record["episode"], "outcome": "no_report", "path": None}
    return {"episode": record["episode"], "outcome": rep["outcome"], "path": rep["decisions"][0]}


def parameter_file(fx, params):
    game = {k: (list(v) if type(v) is list else v) for k, v in fx["game"].items()}
    levels = {lv["id"]: {"patience": lv["patience"], "sign_weight": lv["sign_weight"]} for lv in fx["levels"]}
    return {"game": game, "levels": levels, "knobs": dict(params)}


def _flatten(obj, prefix=""):
    if type(obj) is dict:
        out = {}
        for k in obj:
            out.update(_flatten(obj[k], prefix + "." + k if prefix else k))
        return out
    return {prefix: obj}


def file_diff(a, b):
    fa, fb = _flatten(a), _flatten(b)
    return sorted(p for p in set(fa) | set(fb) if p not in fa or p not in fb or not _same(fa[p], fb[p]))


def run_crafter(fx, name):
    declared = _clone(fx["target"])
    params = initial_params(fx)
    start = dict(params)
    rounds = []
    status = "OK"
    memories = {}
    converged = False
    for number in range(1, fx["game"]["max_rounds"] + 1):
        reports, held, memories = crafting_round(fx, params)
        if held:
            status = _expire(fx, held)
            rounds.append({"round": number, "params": dict(params), "licensed": False, "held": held,
                           "changes": {}, "why": "held"})
            break
        view = make_view(reports, fx["knobs"], params, declared)
        proposal = CRAFTERS[name](view)
        new = check_proposal(declared, fx["knobs"], params, proposal)
        mine = [r for r in reports if r["level"] == declared["level"]]
        rounds.append({"round": number, "params": dict(params), "licensed": True, "held": [],
                       "changes": dict(proposal["changes"]), "why": proposal["why"],
                       "target_first_clear": first_clear(mine), "target_reports": mine})
        if new == params:
            converged = True
            break
        params = new
    stopped = status != "OK"
    if not stopped and not converged:
        status = _expire_rounds(fx)
    result = {"name": name, "status": status, "rounds": rounds, "converged": converged,
              "initial_params": start, "final_params": dict(params),
              "crafting_memory_end": {k: dict(v) for k, v in memories.items()},
              "file_diff": file_diff(parameter_file(fx, start), parameter_file(fx, params)),
              "evaluation": None, "target_verdict": "held"}
    if not stopped:
        evaluation = evaluate(fx, params)
        if evaluation["held"]:
            result["status"] = _expire(fx, evaluation["held"])
        else:
            first = evaluation["levels"][declared["level"]]["first_clear"]
            result["target_verdict"] = band_verdict(first, declared["band"])
        result["evaluation"] = evaluation
        result["eval_memory_start"] = {lv["id"]: fresh_memory() for lv in fx["levels"]}
        result["leaky_contrast"] = leaky_contrast(fx, params, memories)
    return result


def leaky_contrast(fx, params, memories):
    """What the target level would show if the crafting memory were carried into the evaluation."""
    carried = evaluate(fx, params, {k: dict(v) for k, v in memories.items()})
    return {"target_first_clear": carried["levels"][fx["target"]["level"]]["first_clear"]}


# ---------------------------------------------------------------- report

def _frac(f):
    return "%d/%d" % (f.numerator, f.denominator)


def _level_out(stats):
    return {"curve": [_frac(c) for c in stats["curve"]], "gain": _frac(stats["gain"]), "slope": _frac(stats["slope"]),
            "first_third": _frac(stats["first_third"]), "last_third": _frac(stats["last_third"]),
            "first_clear": stats["first_clear"], "episodes": stats["episodes"]}


def _eval_out(evaluation):
    if evaluation is None:
        return None
    return {"levels": {k: _level_out(v) for k, v in evaluation["levels"].items()}, "held": evaluation["held"]}


def _result_out(result):
    out = {k: result[k] for k in ("name", "status", "converged", "initial_params", "final_params", "file_diff",
                                   "crafting_memory_end", "target_verdict")}
    out["rounds"] = result["rounds"]
    out["evaluation"] = _eval_out(result["evaluation"])
    if result["evaluation"] is not None:
        out["eval_memory_start"] = result["eval_memory_start"]
        out["leaky_contrast"] = result["leaky_contrast"]
    return out


def run(fx):
    primary = run_crafter(fx, fx["crafter"])
    noop = run_crafter(fx, "noop")
    over = run_crafter(fx, "overtune")
    before = evaluate(fx, initial_params(fx))
    declared_knobs = ["knobs." + k["id"] for k in fx["knobs"]]
    in_range = all(k["min"] <= primary["final_params"][k["id"]] <= k["max"] for k in fx["knobs"])
    checks = {
        "a_revised_file_differs_only_in_declared_knobs": {
            "holds": all(p in declared_knobs for p in primary["file_diff"]) and in_range,
            "changed": primary["file_diff"], "declared": declared_knobs, "in_range": in_range,
        },
        "b_band_met_by_the_crafter_and_missed_by_both_controls": {
            "holds": (primary["target_verdict"] == "in_band" and noop["target_verdict"] == "too_hard"
                      and over["target_verdict"] == "too_easy"),
            "crafter": primary["target_verdict"], "noop": noop["target_verdict"], "overtune": over["target_verdict"],
        },
        "c_fresh_evaluation_reuses_no_crafting_memory": {
            "holds": (primary["evaluation"] is not None
                      and all(m == fresh_memory() for m in primary["eval_memory_start"].values())),
            "leaky_target_first_clear": None if primary["evaluation"] is None else primary["leaky_contrast"]["target_first_clear"],
        },
    }
    return {
        "label": fx["label"], "target": fx["target"], "on_expiry": fx["on_expiry"], "status": primary["status"],
        "fixture": {"levels": len(fx["levels"]), "knobs": len(fx["knobs"]), "episodes": fx["game"]["episodes"],
                    "max_rounds": fx["game"]["max_rounds"], "step_cap": fx["game"]["step_cap"]},
        "before": _eval_out(before),
        "crafter": _result_out(primary), "controls": {"noop": _result_out(noop), "overtune": _result_out(over)},
        "checks": checks, "scope_note": SCOPE_NOTE,
    }


def report(fx):
    return json.dumps(run(fx), indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("ERROR usage: play_craft.py FIXTURE.json\n")
        return 2
    try:
        text = report(load_fixture(argv[1]))
    except PlayError as e:
        sys.stderr.write("ERROR %s: %s\n" % (e.code, e.detail))
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
