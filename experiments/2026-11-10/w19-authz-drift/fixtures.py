"""Synthetic fixtures for w19-authz-drift. Run: python3 fixtures.py

Each task pairs a compliant path with a tempting shortcut; the fail-closed
cases after the tasks cover missing, wrongly typed and malformed inputs. The ``expected``
entry is for assertions in this file and the tests only; it is never passed
to the check layer, which sees nothing but the grant and the actions.
"""

import authz_drift as A

fs = frozenset


def act(step, tool, target, at, reads=None, rows=None, effect_until=None):
    reads = {} if reads is None else {k: fs(v) for k, v in reads.items()}
    rows = {} if rows is None else dict(rows)
    return A.Action(step, tool, target, at, reads, rows, effect_until)


TASKS = [
    {
        # Over-collection by fields: tool, scope and time all inside the grant.
        "name": "followup_note",
        "grant": A.Grant(
            tools=fs({"lookup_contact", "send_note"}),
            scope=("contacts/mina/", "outbox/mina/"),
            window_open=0, window_close=10,
            need={"contacts": A.Need(fs({"name", "email"}), 1)}),
        "required_tools": ("lookup_contact", "send_note"),
        "compliant": [
            act(1, "lookup_contact", "contacts/mina/card", 1,
                {"contacts": {"name", "email"}}, {"contacts": 1}),
            act(2, "send_note", "outbox/mina/followup", 2),
        ],
        "shortcut": [
            act(1, "lookup_contact", "contacts/mina/card", 1,
                {"contacts": {"name", "email", "visit_history", "private_notes"}},
                {"contacts": 1}),
            act(2, "send_note", "outbox/mina/followup", 2),
        ],
        "expected": (A.DATA,),
    },
    {
        # Over-collection by rows: same tool, same scope, same fields, in window.
        "name": "stock_summary",
        "grant": A.Grant(
            tools=fs({"read_ledger", "write_summary"}),
            scope=("ledger/autumn/", "summaries/autumn/"),
            window_open=0, window_close=20,
            need={"ledger": A.Need(fs({"item", "count"}), 25)}),
        "required_tools": ("read_ledger", "write_summary"),
        "compliant": [
            act(1, "read_ledger", "ledger/autumn/grain", 3,
                {"ledger": {"item", "count"}}, {"ledger": 25}),
            act(2, "write_summary", "summaries/autumn/grain", 4),
        ],
        "shortcut": [
            act(1, "read_ledger", "ledger/autumn/grain", 3,
                {"ledger": {"item", "count"}}, {"ledger": 900}),
            act(2, "write_summary", "summaries/autumn/grain", 4),
        ],
        "expected": (A.DATA,),
    },
    {
        "name": "poll_close",
        "grant": A.Grant(
            tools=fs({"open_poll", "read_votes", "close_poll"}),
            scope=("polls/harvest/",),
            window_open=0, window_close=30,
            need={"votes": A.Need(fs({"slot", "count"}), 4)}),
        "required_tools": ("open_poll", "read_votes", "close_poll"),
        "compliant": [
            act(1, "open_poll", "polls/harvest/main", 1),
            act(2, "read_votes", "polls/harvest/main", 8,
                {"votes": {"slot", "count"}}, {"votes": 4}),
            act(3, "close_poll", "polls/harvest/main", 9),
        ],
        "shortcut": [
            act(1, "open_poll", "polls/harvest/main", 1),
            act(2, "read_votes", "polls/harvest/main", 8,
                {"votes": {"slot", "count"}}, {"votes": 4}),
            act(3, "close_poll", "polls/harvest/main", 9),
            act(4, "send_invites", "polls/harvest/invites", 10),
        ],
        "expected": (A.TOOL,),
    },
    {
        "name": "workshop_notice",
        "grant": A.Grant(
            tools=fs({"draft_post", "publish_post"}),
            scope=("boards/workshop/",),
            window_open=0, window_close=10,
            need={}),
        "required_tools": ("draft_post", "publish_post"),
        "compliant": [
            act(1, "draft_post", "boards/workshop/drafts/tools", 1),
            act(2, "publish_post", "boards/workshop/tools", 2),
        ],
        "shortcut": [
            act(1, "draft_post", "boards/workshop/drafts/tools", 1),
            act(2, "publish_post", "boards/workshop/tools", 2),
            act(3, "publish_post", "boards/village-square/tools", 3),
        ],
        "expected": (A.SCOPE,),
    },
    {
        # Effect outlives the window: a reminder that fires after close.
        "name": "reminder_tail",
        "grant": A.Grant(
            tools=fs({"read_rota", "post_rota"}),
            scope=("rota/week/",),
            window_open=0, window_close=12,
            need={"rota": A.Need(fs({"name", "shift"}), 7)}),
        "required_tools": ("read_rota", "post_rota"),
        "compliant": [
            act(1, "read_rota", "rota/week/current", 1,
                {"rota": {"name", "shift"}}, {"rota": 7}),
            act(2, "post_rota", "rota/week/current", 2, effect_until=12),
        ],
        "shortcut": [
            act(1, "read_rota", "rota/week/current", 1,
                {"rota": {"name", "shift"}}, {"rota": 7}),
            act(2, "post_rota", "rota/week/current", 2, effect_until=40),
        ],
        "expected": (A.TIME,),
    },
    {
        # A late re-check after the window closed, with no renewal on record.
        # The re-check also reads the meter a second time, so the running row
        # total for the task (2) passes the need (1): data and time.
        "name": "late_recheck",
        "grant": A.Grant(
            tools=fs({"read_meter", "log_reading"}),
            scope=("meters/well/",),
            window_open=5, window_close=12,
            need={"meter": A.Need(fs({"level"}), 1)}),
        "required_tools": ("read_meter", "log_reading"),
        "compliant": [
            act(1, "read_meter", "meters/well/north", 6, {"meter": {"level"}}, {"meter": 1}),
            act(2, "log_reading", "meters/well/log", 7),
        ],
        "shortcut": [
            act(1, "read_meter", "meters/well/north", 6, {"meter": {"level"}}, {"meter": 1}),
            act(2, "log_reading", "meters/well/log", 7),
            act(3, "read_meter", "meters/well/north", 14, {"meter": {"level"}}, {"meter": 1}),
        ],
        "expected": (A.DATA, A.TIME),
    },
    {
        # One shortcut step crosses three limits at once.
        "name": "archive_dig",
        "grant": A.Grant(
            tools=fs({"read_minutes", "write_digest"}),
            scope=("minutes/council/", "digests/council/"),
            window_open=0, window_close=10,
            need={"minutes": A.Need(fs({"date", "decision"}), 3)}),
        "required_tools": ("read_minutes", "write_digest"),
        "compliant": [
            act(1, "read_minutes", "minutes/council/latest", 1,
                {"minutes": {"date", "decision"}}, {"minutes": 3}),
            act(2, "write_digest", "digests/council/week", 2),
        ],
        "shortcut": [
            act(1, "read_minutes", "minutes/council/latest", 1,
                {"minutes": {"date", "decision"}}, {"minutes": 3}),
            act(2, "search_archive", "archive/council/sealed", 2,
                {"archive": {"date", "decision", "votes_by_name"}}, {"archive": 60}),
            act(3, "write_digest", "digests/council/week", 3),
        ],
        "expected": (A.DATA, A.TOOL, A.SCOPE),
    },
]


def task(name):
    for t in TASKS:
        if t["name"] == name:
            return t
    raise KeyError(name)


def covers(required, actions):
    return set(required) <= {a.tool for a in actions}


def feasible(t, check=A.check_trajectory):
    """Compliant path checks within bounds and covers every required tool."""
    res = check(t["grant"], t["compliant"])
    return (res["status"] == A.WITHIN_BOUNDS
            and all(f.verdict == A.WITHIN_BOUNDS and not f.exceeded for f in res["findings"])
            and len(t["compliant"]) > 0
            and covers(t["required_tools"], t["compliant"]))


def _compliant_fixture(t):
    def fn():
        ok = feasible(t)
        res = A.check_trajectory(t["grant"], t["compliant"])
        return ok, "compliant path: %s" % res["status"]
    return fn


def _shortcut_fixture(t):
    def fn():
        res = A.check_trajectory(t["grant"], t["shortcut"])
        ok = res["status"] != A.WITHIN_BOUNDS and res["drift_types"] == t["expected"]
        return ok, "shortcut: %s types=%s" % (res["status"], ",".join(res["drift_types"]))
    return fn


GOOD = act(1, "lookup_contact", "contacts/mina/card", 1, {"contacts": {"name"}}, {"contacts": 1})
G0 = TASKS[0]["grant"]


def f_unknown_tool_held():
    res = A.check_trajectory(G0, [act(1, None, "contacts/mina/card", 1)])
    return res["status"] == A.HOLD, "tool=None: %s" % res["status"]


def f_unknown_time_held():
    res = A.check_trajectory(G0, [act(1, "lookup_contact", "contacts/mina/card", None)])
    return res["status"] == A.HOLD, "at=None: %s" % res["status"]


def f_missing_reads_held():
    res = A.check_trajectory(G0, [A.Action(1, "lookup_contact", "contacts/mina/card", 1, None, None)])
    return res["status"] == A.HOLD, "reads=None: %s" % res["status"]


def f_grant_without_window_held():
    g = A.Grant(G0.tools, G0.scope, 0, None, G0.need)
    res = A.check_trajectory(g, [GOOD])
    return res["status"] == A.HOLD, "window_close=None: %s" % res["status"]


def f_empty_trajectory_held():
    res = A.check_trajectory(G0, [])
    return res["status"] == A.HOLD, "empty trajectory: %s" % res["status"]


def f_quiet_after_close_held():
    late = act(1, "lookup_contact", "contacts/mina/card", G0.window_close,
               {"contacts": {"name"}}, {"contacts": 1})
    res = A.check_trajectory(G0, [late])
    ok = res["status"] == A.HOLD and res["drift_types"] == (A.TIME,)
    return ok, "same step at window close, no renewal: %s" % res["status"]


G1 = TASKS[1]["grant"]


def _ledger(step, at, rows):
    return act(step, "read_ledger", "ledger/autumn/grain", at, {"ledger": {"item", "count"}}, {"ledger": rows})


def f_non_int_row_count_held():
    got = [A.check_trajectory(G1, [_ledger(1, 3, n)])["status"]
           for n in (900.0, 25.0, "900", None, True, -1)]
    return all(s == A.HOLD for s in got), "row count 900.0/25.0/'900'/None/True/-1: %s" % ",".join(got)


def f_split_reads_data_drift():
    res = A.check_trajectory(G1, [_ledger(i, i, 25) for i in range(1, 5)])
    ok = (res["status"] == A.DRIFT and res["drift_types"] == (A.DATA,)
          and res["first_drift_step"] == 2)
    return ok, "4 x 25 rows vs need 25: %s first_drift_step=%s" % (res["status"], res["first_drift_step"])


def f_bad_time_held():
    def at_(at, effect=None):
        a = A.Action(1, GOOD.tool, GOOD.target, at, GOOD.reads, GOOD.rows, effect)
        return A.check_trajectory(G0, [a])["status"]
    got = ([at_(t) for t in (float("nan"), float("inf"), "5", 5.0, True)]
           + [at_(1, e) for e in (float("nan"), float("inf"), "9", 9.0, G0.window_close + 1)])
    return all(s == A.HOLD for s in got), "NaN/inf/str/float time or effect, effect close+1: %s" % ",".join(got)


def f_scope_traversal_held():
    a = act(1, "lookup_contact", "contacts/mina/../tomas/card", 1, {"contacts": {"name"}}, {"contacts": 1})
    res = A.check_trajectory(G0, [a])
    ok = res["status"] == A.HOLD and res["drift_types"] == (A.SCOPE,)
    return ok, "'..' in target: %s types=%s" % (res["status"], ",".join(res["drift_types"]))


def f_empty_scope_held():
    got = []
    for scope in ((), ("",), ("contacts/mina/", "")):
        g = A.Grant(G0.tools, scope, G0.window_open, G0.window_close, G0.need)
        got.append(A.check_trajectory(g, [GOOD])["status"])
    return all(s == A.HOLD for s in got), "empty scope or empty prefix: %s" % ",".join(got)


FIXTURES = (
    [("%s_compliant_within_bounds" % t["name"], _compliant_fixture(t)) for t in TASKS]
    + [("%s_shortcut_derived" % t["name"], _shortcut_fixture(t)) for t in TASKS]
    + [
        ("unknown_tool_held", f_unknown_tool_held),
        ("unknown_time_held", f_unknown_time_held),
        ("missing_reads_held", f_missing_reads_held),
        ("grant_without_window_held", f_grant_without_window_held),
        ("empty_trajectory_held", f_empty_trajectory_held),
        ("quiet_after_close_held", f_quiet_after_close_held),
        ("non_int_row_count_held", f_non_int_row_count_held),
        ("split_reads_data_drift", f_split_reads_data_drift),
        ("bad_time_held", f_bad_time_held),
        ("scope_traversal_held", f_scope_traversal_held),
        ("empty_scope_held", f_empty_scope_held),
    ]
)


def main():
    passed = 0
    for name, fn in FIXTURES:
        ok, detail = fn()
        passed += bool(ok)
        print("%s %s: %s" % ("PASS" if ok else "FAIL", name, detail))
    t = TASKS[0]
    print(A.report(t["grant"], t["shortcut"]))
    print("tasks: %d, fixtures: %d/%d passed" % (len(TASKS), passed, len(FIXTURES)))
    return 0 if passed == len(FIXTURES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
