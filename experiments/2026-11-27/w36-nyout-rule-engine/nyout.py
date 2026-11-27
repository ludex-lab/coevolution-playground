"""w36-nyout-rule-engine: a deterministic Nyout (윷놀이) rule engine from Culin 1895.

Method sketch of Stewart Culin, Korean Games with Notes on the Corresponding
Games of China and Japan, Philadelphia: University of Pennsylvania, 1895,
chapter LXX (public domain). Not a modern 윷놀이 variant. Fig. 75, Fig. 76
and Plate XV were not used. Throws are listed in the fixture; there is no
runtime chance source and no wall-clock metric.

Bad input is DENY: exit 2, empty stdout, one stderr line 'DENY <code>: <detail>'.
"""

import json
import re
import sys

FIXTURE_VERSION = 1
ON_EXPIRY_OK = ("DENY", "SAFE_FALLBACK", "ESCALATE", "HOLD")
TIMEOUT = {"seconds": 300, "on_expiry": "DENY"}

THROW_STEPS = {"to": 1, "kai": 2, "kel": 3, "nyout": 4, "mo": 5}
BONUS_THROWS = ("nyout", "mo")
ARM_VALUES = ("A", "B")
GATE_VALUES = ("PASS", "FAIL")

RIM = tuple("r%d" % i for i in range(1, 21))
ARM_MARKS = ("b1", "b2", "c1", "c2", "d1", "d2", "a1", "a2")
CENTRE = "E"
STATIONS = RIM + ARM_MARKS + (CENTRE,)
ALIASES = {"A": "r20", "B": "r5", "C": "r10", "D": "r15"}

EDGES = tuple((RIM[i], RIM[i + 1]) for i in range(19)) + (
    ("r5", "b1"), ("b1", "b2"), ("b2", "E"),
    ("r10", "c1"), ("c1", "c2"), ("c2", "E"),
    ("E", "a1"), ("a1", "a2"), ("a2", "r20"),
)

BE_NEXT = {
    "r5": "b1", "b1": "b2", "b2": "E",
    "E": "a1", "a1": "a2", "a2": "r20", "r20": "out",
}
CE_NEXT = {
    "r10": "c1", "c1": "c2", "c2": "E",
    "E": "a1", "a1": "a2", "a2": "r20", "r20": "out",
}
RIM_NEXT = dict((RIM[i], RIM[i + 1]) for i in range(19))
RIM_NEXT["r20"] = "out"

START = "start"
OUT = "out"

ROOT_KEYS = (
    "fixture_version", "on_expiry", "horse_count",
    "take_c_shortcut", "join_stack", "sessions", "expected",
)
OPTIONAL_ROOT = ("board",)
SESSION_KEYS = ("id", "throws", "moves")
OPTIONAL_SESSION = ("take_c_shortcut", "join_stack", "overrun_mark")
MOVE_KEYS = ("horse",)
BOARD_KEYS = ("stations", "edges")
EXPECTED_SESSION_KEYS = ("arm_a",)
OPTIONAL_EXPECTED = ("arm_b", "pos_a")

SID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
HORSE_RE = re.compile(r"[pq][1-4]\Z")

MAX_BYTES = 32768
MAX_NESTING_DEPTH = 16
MAX_SESSIONS = 32
MAX_THROWS = 64
MAX_MOVES = 64

# Unique assignment sites used by in-memory mutants. Each line occurs once.
ENTRY_COUNTS_AS = 1
SHORTCUT_ONLY_ON_STOP = True
GRANT_EXTRA_BEFORE_MOVE = True
CAPTURE_SENDS_HOME = True
EXACT_A_IS_TIED = True
APPLY_THROWS_ONE_BY_ONE = True
STACK_COUNTS_AS_N = True
ONE_SIDE_PER_BUFFER = True


class Deny(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, code)
        self.code = code
        self.detail = detail


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise Deny("duplicate_key", "JSON object repeats the key %r" % key)
        out[key] = value
    return out


def _no_float(text):
    raise Deny("bad_type", "number %s is not an integer" % text[:12])


def _obj(value, required, where, optional=()):
    if type(value) is not dict:
        raise Deny("bad_type", "%s must be an object" % where)
    known = set(required) | set(optional)
    for key in required:
        if key not in value:
            raise Deny("missing_field", "%s lacks %r" % (where, key))
    for key in value:
        if key not in known:
            raise Deny("unknown_field", "%s has unknown field %r" % (where, key))
    return value


def _list(value, where):
    if type(value) is not list:
        raise Deny("bad_type", "%s must be a list" % where)
    return value


def _bool(value, where):
    if type(value) is not bool:
        raise Deny("bad_type", "%s must be a boolean" % where)
    return value


def _int(value, where):
    if type(value) is not int:
        raise Deny("bad_type", "%s must be an integer" % where)
    return value


def _str(value, where):
    if type(value) is not str:
        raise Deny("bad_type", "%s must be a string" % where)
    return value


def _sid(value, where):
    if type(value) is not str or not SID_RE.match(value):
        raise Deny("bad_type", "%s must be a string matching [A-Za-z][A-Za-z0-9_]{0,63}" % where)
    return value


def _walk(value, where, depth=0):
    if depth > MAX_NESTING_DEPTH:
        raise Deny("too_deep", "%s nests deeper than %d levels" % (where, MAX_NESTING_DEPTH))
    if type(value) is dict:
        for key in value:
            if type(key) is str and key in ("seed", "random"):
                raise Deny("seed_forbidden", "%s has field %r" % (where, key))
            _walk(value[key], where, depth + 1)
    elif type(value) is list:
        for item in value:
            _walk(item, where, depth + 1)


def _board_ok(raw, where):
    raw = _obj(raw, BOARD_KEYS, where)
    stations = _list(raw["stations"], where + " stations")
    edges = _list(raw["edges"], where + " edges")
    seen = []
    for i, name in enumerate(stations):
        if type(name) is not str:
            raise Deny("bad_board", "%s stations[%d] must be a string" % (where, i))
        if name in seen:
            raise Deny("bad_board", "%s repeats station %r" % (where, name))
        seen.append(name)
    if tuple(seen) != STATIONS:
        missing = [s for s in STATIONS if s not in seen]
        extra = [s for s in seen if s not in STATIONS]
        raise Deny("bad_board", "%s station set is not the 29 named marks (missing %s extra %s)" % (
            where, missing, extra))
    got_edges = []
    edge_set = set()
    for i, edge in enumerate(edges):
        if type(edge) is not list or len(edge) != 2:
            raise Deny("bad_board", "%s edges[%d] must be a two-item list" % (where, i))
        a, b = edge[0], edge[1]
        if type(a) is not str or type(b) is not str:
            raise Deny("bad_board", "%s edges[%d] ends must be strings" % (where, i))
        pair = (a, b)
        if pair in edge_set:
            raise Deny("bad_board", "%s repeats edge %s->%s" % (where, a, b))
        if a not in STATIONS or b not in STATIONS:
            raise Deny("bad_board", "%s has an edge whose end is not a station" % where)
        edge_set.add(pair)
        got_edges.append(pair)
    if set(got_edges) != set(EDGES):
        raise Deny("bad_board", "%s edge set does not match the declared graph" % where)
    return True


def _horses_for(count):
    if count == 1:
        return ("p1", "q1")
    return ("p1", "p2", "p3", "p4", "q1", "q2", "q3", "q4")


def _throw_name(value, where):
    if type(value) is not str or value not in THROW_STEPS:
        raise Deny("bad_throw", "%s must be one of to, kai, kel, nyout, mo" % where)
    return value


def _horse_id(value, where, horses):
    if type(value) is not str:
        raise Deny("bad_type", "%s must be a string" % where)
    if value not in horses:
        raise Deny("unknown_horse", "%s names horse %r, which is not in this fixture" % (where, value))
    return value


def _moves(raw, where, horses):
    moves = _list(raw, where)
    if len(moves) > MAX_MOVES:
        raise Deny("too_many", "%s may have at most %d moves" % (where, MAX_MOVES))
    if len(moves) < 1:
        raise Deny("missing_field", "%s must have at least one move" % where)
    out = []
    for i, item in enumerate(moves):
        item = _obj(item, MOVE_KEYS, "%s[%d]" % (where, i))
        out.append({"horse": _horse_id(item["horse"], "%s[%d] horse" % (where, i), horses)})
    return out


def _throws(raw, where):
    throws = _list(raw, where)
    if len(throws) > MAX_THROWS:
        raise Deny("too_many", "%s may have at most %d throws" % (where, MAX_THROWS))
    if len(throws) < 1:
        raise Deny("missing_field", "%s must have at least one throw" % where)
    return [_throw_name(t, "%s[%d]" % (where, i)) for i, t in enumerate(throws)]


def _sessions(raw, horses, default_take_c, default_join):
    sessions = _list(raw, "sessions")
    if len(sessions) < 1:
        raise Deny("missing_field", "sessions must have at least one session")
    if len(sessions) > MAX_SESSIONS:
        raise Deny("too_many", "sessions may have at most %d entries" % MAX_SESSIONS)
    out = []
    seen = set()
    for i, item in enumerate(sessions):
        where = "sessions[%d]" % i
        item = _obj(item, SESSION_KEYS, where, OPTIONAL_SESSION)
        sid = _sid(item["id"], where + " id")
        if sid in seen:
            raise Deny("duplicate_id", "sessions repeat the id %r" % sid)
        seen.add(sid)
        take_c = default_take_c
        join = default_join
        if "take_c_shortcut" in item:
            take_c = _bool(item["take_c_shortcut"], where + " take_c_shortcut")
        if "join_stack" in item:
            join = _bool(item["join_stack"], where + " join_stack")
        overrun_mark = None
        if "overrun_mark" in item:
            overrun_mark = _str(item["overrun_mark"], where + " overrun_mark")
            if overrun_mark not in ("B", "C"):
                raise Deny("bad_type", "%s overrun_mark must be B or C" % where)
        out.append({
            "id": sid,
            "throws": _throws(item["throws"], where + " throws"),
            "moves": _moves(item["moves"], where + " moves", horses),
            "take_c_shortcut": take_c,
            "join_stack": join,
            "overrun_mark": overrun_mark,
        })
    return out


def _gate(value, where):
    if type(value) is not str or value not in GATE_VALUES:
        raise Deny("bad_expected", "%s must be PASS or FAIL" % where)
    return value


def _pos_map(raw, where, horses):
    raw = raw if type(raw) is dict else _obj(raw, (), where)
    if type(raw) is not dict:
        raise Deny("bad_type", "%s must be an object" % where)
    out = {}
    for key in raw:
        if type(key) is not str:
            raise Deny("bad_type", "%s keys must be strings" % where)
        if key not in horses:
            raise Deny("unknown_horse", "%s names horse %r, which is not in this fixture" % (where, key))
        val = raw[key]
        if type(val) is not str:
            raise Deny("bad_type", "%s.%s must be a string" % (where, key))
        if val not in STATIONS and val not in (START, OUT):
            raise Deny("bad_expected", "%s.%s is not a station, start, or out" % (where, key))
        out[key] = val
    return out


def _expected(raw, sessions, horses):
    if type(raw) is not dict:
        raise Deny("bad_type", "expected must be an object")
    ids = [s["id"] for s in sessions]
    for key in raw:
        if type(key) is not str:
            raise Deny("bad_type", "expected keys must be strings")
        if key not in ids:
            raise Deny("bad_expected", "expected names unknown session %r" % key)
    out = {}
    for sid in ids:
        if sid not in raw:
            raise Deny("missing_field", "expected lacks session %r" % sid)
        where = "expected.%s" % sid
        item = _obj(raw[sid], EXPECTED_SESSION_KEYS, where, OPTIONAL_EXPECTED)
        row = {"arm_a": _gate(item["arm_a"], where + " arm_a")}
        if "arm_b" in item:
            row["arm_b"] = _gate(item["arm_b"], where + " arm_b")
        if "pos_a" in item:
            row["pos_a"] = _pos_map(item["pos_a"], where + " pos_a", horses)
        out[sid] = row
    return out


def validate(root):
    if type(root) is not dict:
        raise Deny("bad_type", "fixture must be an object")
    _walk(root, "fixture")
    root = _obj(root, ROOT_KEYS, "fixture", OPTIONAL_ROOT)
    version = root["fixture_version"]
    if type(version) is not int:
        raise Deny("bad_type", "fixture_version must be an integer")
    if version != FIXTURE_VERSION:
        raise Deny("bad_version", "fixture_version must be %d" % FIXTURE_VERSION)
    on_expiry = root["on_expiry"]
    if type(on_expiry) is not str:
        raise Deny("bad_type", "on_expiry must be a string")
    if on_expiry not in ON_EXPIRY_OK:
        raise Deny("bad_on_expiry", "on_expiry must be one of %s" % ", ".join(ON_EXPIRY_OK))
    horse_count = _int(root["horse_count"], "horse_count")
    if horse_count not in (1, 4):
        raise Deny("bad_horse_count", "horse_count must be 1 or 4")
    take_c = _bool(root["take_c_shortcut"], "take_c_shortcut")
    join = _bool(root["join_stack"], "join_stack")
    if "board" in root:
        _board_ok(root["board"], "board")
    horses = _horses_for(horse_count)
    sessions = _sessions(root["sessions"], horses, take_c, join)
    expected = _expected(root["expected"], sessions, horses)
    return {
        "on_expiry": on_expiry,
        "horse_count": horse_count,
        "take_c_shortcut": take_c,
        "join_stack": join,
        "horses": horses,
        "sessions": sessions,
        "expected": expected,
    }


def load_text(text):
    if type(text) is not str:
        raise Deny("bad_type", "fixture text must be a string")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise Deny("too_large", "fixture is larger than %d bytes" % MAX_BYTES)
    try:
        root = json.loads(text, object_pairs_hook=_pairs, parse_float=_no_float)
    except RecursionError:
        raise Deny("too_deep", "fixture nests deeper than %d levels" % MAX_NESTING_DEPTH)
    except Deny:
        raise
    except ValueError as e:
        raise Deny("not_json", "fixture is not valid JSON (%s)" % str(e)[:80])
    return validate(root)


def load(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_BYTES + 1)
    except OSError:
        raise Deny("unreadable", "fixture %s cannot be read" % path)
    if len(data) > MAX_BYTES:
        raise Deny("too_large", "fixture is larger than %d bytes" % MAX_BYTES)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Deny("bad_utf", "fixture is not valid UTF-8")
    return load_text(text)


def legal_successors(pos, take_c):
    """Next station (or out) for a one-step move that starts on pos."""
    if pos == START:
        return RIM[1 - ENTRY_COUNTS_AS]
    if pos == OUT:
        return OUT
    if pos == "r5":
        return BE_NEXT["r5"]
    if pos == "r10" and take_c:
        return CE_NEXT["r10"]
    if pos in BE_NEXT and pos not in ("r5", "r10", "r20") and pos not in RIM:
        # on a BE/CE/EA arm or the centre, continue toward A
        if pos in ("c1", "c2"):
            return CE_NEXT[pos]
        return BE_NEXT[pos]
    if pos in RIM_NEXT:
        return RIM_NEXT[pos]
    return None


def reachable_from_start(take_c=True):
    found = set()
    queue = [START]
    seen_pos = set([START])
    while queue:
        cur = queue.pop(0)
        nxt = legal_successors(cur, take_c)
        if nxt is None or nxt in seen_pos:
            continue
        seen_pos.add(nxt)
        if nxt != OUT:
            found.add(nxt)
            queue.append(nxt)
    return found


def reachable_stations():
    """Stations a horse can land on by legal throws (Arm A), including mid-move passes."""
    found = set()
    seen = set([START])
    queue = [START]
    while queue:
        cur = queue.pop(0)
        if cur not in (START, OUT):
            found.add(cur)
        for take_c in (True, False):
            for steps in range(1, 6):
                landing, _ev, _ill = apply_steps(cur, steps, take_c, "A")
                if landing not in seen and landing != OUT:
                    seen.add(landing)
                    queue.append(landing)
    return found


def _side(horse):
    return horse[0]


def _group_of(groups, horse):
    return groups[horse]


def _set_group(groups, members):
    bunch = frozenset(members)
    for h in bunch:
        groups[h] = bunch


def _reset_singleton(groups, horse):
    groups[horse] = frozenset([horse])


def _count_out(horses, side, pos, groups):
    n = 0
    seen = set()
    for h in horses:
        if _side(h) != side or pos[h] != OUT or h in seen:
            continue
        bunch = groups[h]
        if STACK_COUNTS_AS_N:
            n += len(bunch)
        else:
            n += 1
        seen.update(bunch)
    return n


def _step_once(cur, mode):
    if cur == START:
        return RIM[1 - ENTRY_COUNTS_AS]
    if cur == OUT:
        return OUT
    if mode == "be":
        if cur not in BE_NEXT:
            raise Deny("bad_path", "no BE step from %s" % cur)
        return BE_NEXT[cur]
    if mode == "ce":
        if cur not in CE_NEXT:
            raise Deny("bad_path", "no CE step from %s" % cur)
        return CE_NEXT[cur]
    if cur not in RIM_NEXT:
        raise Deny("bad_path", "no rim step from %s" % cur)
    return RIM_NEXT[cur]


def _start_mode(pos, take_c):
    if pos == "r5":
        return "be"
    if pos == "r10" and take_c:
        return "ce"
    if pos in ("b1", "b2", "E", "a1", "a2"):
        return "be"
    if pos in ("c1", "c2"):
        return "ce"
    return "rim"


def _arm_b_diverts(cur, overrun_mark):
    if overrun_mark == "B":
        return cur == "r5"
    if overrun_mark == "C":
        return cur == "r10"
    return cur in ("r5", "r10")


def apply_steps(pos, steps, take_c, arm, overrun_mark=None):
    """Walk `steps` from pos. Returns (landing, events, illegal)."""
    events = []
    illegal = False
    cur = pos
    mode = _start_mode(pos, take_c)
    if mode in ("be", "ce") and pos in ("r5", "r10"):
        events.append("shortcut")
    for i in range(steps):
        cur = _step_once(cur, mode)
        more = i < steps - 1
        if more and cur in ("r5", "r10"):
            mutant_divert = not SHORTCUT_ONLY_ON_STOP
            arm_b_divert = arm == "B" and _arm_b_diverts(cur, overrun_mark)
            if mutant_divert or arm_b_divert:
                mode = "be" if cur == "r5" else "ce"
                if SHORTCUT_ONLY_ON_STOP and arm_b_divert:
                    illegal = True
                    events.append("illegal_shortcut")
    if cur == "r20":
        if EXACT_A_IS_TIED:
            events.append("tied")
        else:
            cur = OUT
            events.append("out")
    elif cur == OUT:
        events.append("out")
    if pos == START and cur != START:
        events.append("enter")
    return cur, events, illegal


def _consume_move(move_i, moves, where):
    if move_i >= len(moves):
        raise Deny("missing_field", "%s has no move left for an applied throw" % where)
    return moves[move_i]["horse"], move_i + 1


def play_session(session, arm, horses, horse_count):
    pos = dict((h, START) for h in horses)
    groups = dict((h, frozenset([h])) for h in horses)
    throws = list(session["throws"])
    moves = list(session["moves"])
    take_c = session["take_c_shortcut"]
    join = session["join_stack"]
    ti = 0
    mi = 0
    transcript = []
    illegal = False
    end_reason = None

    def collect_into(pending):
        nonlocal ti, end_reason
        got = False
        while ti < len(throws):
            name = throws[ti]
            ti += 1
            pending.append(name)
            transcript.append({"kind": "throw", "throw": name})
            got = True
            if GRANT_EXTRA_BEFORE_MOVE and name in BONUS_THROWS:
                transcript.append({"kind": "extra_throw", "cause": name})
                continue
            return True
        if got:
            end_reason = "throws_exhausted"
            return True
        return False

    pending = []
    buffer_side = None
    while True:
        if not pending:
            buffer_side = None
            if not collect_into(pending):
                end_reason = "throws_exhausted"
                break
        if APPLY_THROWS_ONE_BY_ONE:
            name = pending.pop(0)
            steps_list = [(name, THROW_STEPS[name])]
        else:
            total = 0
            names = list(pending)
            pending[:] = []
            for name in names:
                total += THROW_STEPS[name]
            steps_list = [("+".join(names), total)]
        for label, steps in steps_list:
            horse, mi = _consume_move(mi, moves, session["id"])
            # Culin: the extra throws are his; one buffer is spent by one side.
            if buffer_side is None:
                buffer_side = _side(horse)
            elif ONE_SIDE_PER_BUFFER and _side(horse) != buffer_side:
                raise Deny("wrong_side", "%s spends a throw of side %s on horse %s" % (
                    session["id"], buffer_side, horse))
            if pos[horse] == OUT:
                # Culin: excess past the going-out place does not matter.
                transcript.append({
                    "kind": "apply",
                    "throw": label,
                    "horse": horse,
                    "from": OUT,
                    "to": OUT,
                    "events": ["out"],
                    "captured": [],
                    "stack": [],
                })
                continue
            bunch = list(groups[horse])
            origin = pos[horse]
            landing, ev, ill = apply_steps(
                origin, steps, take_c, arm, session.get("overrun_mark"))
            if ill:
                illegal = True
            # capture / stack at the landing, if still on a station
            captured = []
            stacked_with = []
            if landing not in (START, OUT):
                occupants = [h for h in horses if pos[h] == landing]
                opp = [h for h in occupants if _side(h) != _side(horse)]
                own = [h for h in occupants if _side(h) == _side(horse)]
                if opp:
                    ev = list(ev) + ["capture"]
                    seen = set()
                    for other in opp:
                        if other in seen:
                            continue
                        team = list(groups[other])
                        seen.update(team)
                        if CAPTURE_SENDS_HOME:
                            for h in team:
                                pos[h] = START
                                _reset_singleton(groups, h)
                                captured.append(h)
                        else:
                            captured.extend(team)
                    transcript.append({"kind": "extra_throw", "cause": "capture"})
                    if not collect_into(pending):
                        end_reason = "throws_exhausted"
                if own and join and landing != OUT:
                    members = set(bunch)
                    for other in own:
                        members.update(groups[other])
                    _set_group(groups, members)
                    stacked_with = sorted(members)
                    ev = list(ev) + ["stack"]
            for h in bunch:
                pos[h] = landing
            if landing != origin and bunch:
                # after capture, groups for the moving bunch are unchanged unless stacked
                pass
            if stacked_with:
                _set_group(groups, stacked_with)
            transcript.append({
                "kind": "apply",
                "throw": label,
                "horse": horse,
                "from": origin,
                "to": landing,
                "events": ev,
                "captured": captured,
                "stack": stacked_with,
            })

        if not pending and ti >= len(throws):
            end_reason = "throws_exhausted"
            break
        if not pending and ti < len(throws):
            continue

    if end_reason == "throws_exhausted":
        transcript.append({"kind": "throws_exhausted"})

    out_p = _count_out(horses, "p", pos, groups)
    out_q = _count_out(horses, "q", pos, groups)
    winner = None
    if out_p >= horse_count:
        winner = "p"
    elif out_q >= horse_count:
        winner = "q"
    result = "FAIL" if illegal else "PASS"
    return {
        "id": session["id"],
        "arm": arm,
        "result": result,
        "positions": pos,
        "transcript": transcript,
        "out_p": out_p,
        "out_q": out_q,
        "winner": winner,
        "end": end_reason,
        "illegal": illegal,
    }


def _pos_view(pos):
    parts = []
    for h in sorted(pos):
        if pos[h] != START:
            parts.append("%s:%s" % (h, pos[h]))
    return ",".join(parts) if parts else "-"


def run(fx):
    rows = []
    observed = {}
    for session in fx["sessions"]:
        sid = session["id"]
        want = fx["expected"][sid]
        got_a = play_session(session, "A", fx["horses"], fx["horse_count"])
        if want.get("pos_a") is not None:
            for h, st in want["pos_a"].items():
                if got_a["positions"].get(h) != st:
                    got_a["result"] = "FAIL"
                    got_a["pos_mismatch"] = True
        row = {
            "id": sid,
            "arm_a": got_a["result"],
            "pos_a": got_a["positions"],
            "out_p": got_a["out_p"],
            "out_q": got_a["out_q"],
            "winner": got_a["winner"],
            "end": got_a["end"],
            "transcript_a": got_a["transcript"],
        }
        observed[sid] = {"arm_a": got_a["result"]}
        if "arm_b" in want:
            got_b = play_session(session, "B", fx["horses"], fx["horse_count"])
            row["arm_b"] = got_b["result"]
            row["pos_b"] = got_b["positions"]
            row["transcript_b"] = got_b["transcript"]
            observed[sid]["arm_b"] = got_b["result"]
        rows.append(row)

    gate = "PASS"
    for session in fx["sessions"]:
        sid = session["id"]
        want = fx["expected"][sid]
        got = observed[sid]
        if got["arm_a"] != want["arm_a"]:
            gate = "FAIL"
        if "arm_b" in want and got.get("arm_b") != want["arm_b"]:
            gate = "FAIL"
        if "arm_b" in got and "arm_b" not in want:
            gate = "FAIL"

    report = format_report({
        "on_expiry": fx["on_expiry"],
        "horse_count": fx["horse_count"],
        "take_c_shortcut": fx["take_c_shortcut"],
        "join_stack": fx["join_stack"],
        "rows": rows,
        "gate": gate,
        "expected": fx["expected"],
    })
    return {
        "on_expiry": fx["on_expiry"],
        "rows": rows,
        "gate": gate,
        "report": report,
        "observed": observed,
    }


def format_report(res):
    lines = [
        "w36-nyout-rule-engine",
        "on_expiry: %s" % res["on_expiry"],
        "horse_count: %d" % res["horse_count"],
        "take_c_shortcut: %s" % res["take_c_shortcut"],
        "join_stack: %s" % res["join_stack"],
        "",
        "%-32s %-4s %-5s %s" % ("session", "arm", "gate", "positions"),
    ]
    for row in res["rows"]:
        want_a = res["expected"][row["id"]]["arm_a"]
        mark_a = "PASS" if row["arm_a"] == want_a else "FAIL"
        # The column is the observed result; match is folded into gate.
        lines.append("%-32s %-4s %-5s %s" % (
            row["id"], "A", row["arm_a"], _pos_view(row["pos_a"])))
        if "arm_b" in row:
            lines.append("%-32s %-4s %-5s %s" % (
                row["id"], "B", row["arm_b"], _pos_view(row["pos_b"])))
    lines.append("")
    lines.append("gate: %s" % res["gate"])
    return "\n".join(lines) + "\n"


def main(argv=None):
    if argv is None:
        argv = sys.argv
    err = sys.stderr
    if len(argv) != 2:
        err.write("DENY usage: nyout.py FIXTURE.json\n")
        return 2
    try:
        fx = load(argv[1])
        res = run(fx)
    except Deny as e:
        err.write("DENY %s: %s\n" % (e.code, e.detail))
        return 2
    sys.stdout.write(res["report"])
    return 0 if res["gate"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
