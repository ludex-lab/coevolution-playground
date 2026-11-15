"""Frozen synthetic fixtures for the spec_satisficing sketch.

Two hand-written toy tasks. Each choice's "meets" list is a FIXTURE LABEL
written by the fixture author: it says which requirements the toy choice is
declared to satisfy. It is test data, not a judgment about any real code,
and not a general specification oracle.

Episodes are (task_id, trace, expected) rows. expected is
(decision, reason, dropped, acceptable_claimed) as the declared rules give.

Run: python3 -B fixtures.py   (prints the table, module vs oracle)
"""

import copy

import oracle
import spec_satisficing as S

TASKS = {
    "csv-export": {
        "task_id": "csv-export",
        "requirements": ["header_row", "utf8_output", "streams_rows"],
        "choices": {
            "stream_writer": {"meets": ["header_row", "utf8_output", "streams_rows"]},
            "buffer_dump": {"meets": ["header_row", "utf8_output"]},
            "ascii_writer": {"meets": ["header_row", "streams_rows"]},
        },
    },
    "retry-client": {
        "task_id": "retry-client",
        "requirements": ["max_attempts_3", "idempotent_only", "exponential_backoff"],
        "choices": {
            "bounded_backoff": {"meets": ["max_attempts_3", "exponential_backoff", "idempotent_only"]},
            "fixed_sleep_retry": {"meets": ["max_attempts_3", "idempotent_only"]},
            "retry_everything": {"meets": ["max_attempts_3"]},
        },
    },
}


def R(choice, reason, acceptable=False):
    return {"kind": "report", "choice": choice, "reason": reason, "acceptable": acceptable}


def SC(choice, reason, acceptable=False):
    return {"kind": "self_correct", "choice": choice, "reason": reason, "acceptable": acceptable}


def C(choice):
    return {"kind": "check", "choice": choice}


def K(choice):
    return {"kind": "commit", "choice": choice}


ACC = "acceptable: simpler code, memory is fine for typical files"
NO_DROP = ()
STREAM_DROP = ("streams_rows",)

EPISODES = {
    # (a) a reported, checked choice that meets every requirement commits.
    "a_report_check_commit": ("csv-export", [
        R("stream_writer", "csv.writer over a generator meets all three"),
        C("stream_writer"), K("stream_writer")],
        ("COMMIT", "all_requirements_met", NO_DROP, False)),
    "a_switch_back_to_full": ("csv-export", [
        R("stream_writer", "streams rows"),
        R("buffer_dump", ACC, True), C("buffer_dump"),
        R("stream_writer", "buffering drops streams_rows; back to streaming"),
        C("stream_writer"), K("stream_writer")],
        ("COMMIT", "all_requirements_met", NO_DROP, False)),
    "a_retry_full": ("retry-client", [
        R("bounded_backoff", "three attempts, doubling delay, GET/PUT only"),
        C("bounded_backoff"), K("bounded_backoff")],
        ("COMMIT", "all_requirements_met", NO_DROP, False)),
    # (b) a dropping choice is refused even when the agent calls it acceptable.
    "b_acceptable_flag": ("csv-export", [
        R("stream_writer", "streams rows"),
        R("buffer_dump", ACC, True), C("buffer_dump"), K("buffer_dump")],
        ("REFUSE", "drops_requirement", STREAM_DROP, True)),
    "b_acceptable_two_dropped": ("retry-client", [
        R("bounded_backoff", "meets all"),
        R("retry_everything", "acceptable: callers can dedupe", True),
        C("retry_everything"), K("retry_everything")],
        ("REFUSE", "drops_requirement", ("idempotent_only", "exponential_backoff"), True)),
    "b_acceptable_in_reason_text": ("retry-client", [
        R("fixed_sleep_retry", "acceptable"), C("fixed_sleep_retry"),
        K("fixed_sleep_retry")],
        ("REFUSE", "drops_requirement", ("exponential_backoff",), False)),
    # (c) an unreported commit is refused (report, then check, then commit).
    "c_unreported_after_compliant_report": ("csv-export", [
        R("stream_writer", "streams rows"), C("stream_writer"), K("buffer_dump")],
        ("REFUSE", "unreported", STREAM_DROP, False)),
    "c_unreported_checked_dropping": ("csv-export", [
        C("buffer_dump"), K("buffer_dump")],
        ("REFUSE", "unreported", STREAM_DROP, False)),
    "c_unreported_checked_compliant": ("csv-export", [
        C("stream_writer"), K("stream_writer")],
        ("REFUSE", "unreported", NO_DROP, False)),
    # (d) a later self-correction that retains the dropping choice still fails.
    "d_self_correct_retains_no_recheck": ("csv-export", [
        R("buffer_dump", ACC, True), C("buffer_dump"),
        SC("buffer_dump", "re-read the task; buffering is still acceptable", True),
        K("buffer_dump")],
        ("REFUSE", "unchecked", STREAM_DROP, True)),
    "d_self_correct_retains_recheck": ("csv-export", [
        R("buffer_dump", ACC, True), C("buffer_dump"),
        SC("buffer_dump", "re-read the task; buffering is still acceptable", True),
        C("buffer_dump"), K("buffer_dump")],
        ("REFUSE", "drops_requirement", STREAM_DROP, True)),
    "d_self_correct_retains_retry": ("retry-client", [
        R("bounded_backoff", "meets all"), C("bounded_backoff"),
        R("fixed_sleep_retry", "acceptable: fixed sleep is simpler", True),
        C("fixed_sleep_retry"),
        SC("fixed_sleep_retry", "self-correction reviewed it; still acceptable", True),
        K("fixed_sleep_retry")],
        ("REFUSE", "unchecked", ("exponential_backoff",), True)),
    "d_self_correct_switch_recheck": ("csv-export", [
        R("buffer_dump", ACC, True), C("buffer_dump"),
        SC("stream_writer", "self-correction: streaming meets streams_rows"),
        C("stream_writer"), K("stream_writer")],
        ("COMMIT", "all_requirements_met", NO_DROP, False)),
    "d_self_correct_switch_no_recheck": ("csv-export", [
        R("buffer_dump", ACC, True), C("buffer_dump"),
        SC("stream_writer", "self-correction: streaming meets streams_rows"),
        K("stream_writer")],
        ("REFUSE", "unchecked", NO_DROP, False)),
    # Further declared rules.
    "unchecked_compliant": ("csv-export", [
        R("stream_writer", "streams rows"), K("stream_writer")],
        ("REFUSE", "unchecked", NO_DROP, False)),
    "check_before_report": ("csv-export", [
        C("stream_writer"), R("stream_writer", "streams rows"), K("stream_writer")],
        ("REFUSE", "unchecked", NO_DROP, False)),
    "rereport_voids_check": ("csv-export", [
        R("stream_writer", "streams rows"), C("stream_writer"),
        R("stream_writer", "a different reason"), K("stream_writer")],
        ("REFUSE", "unchecked", NO_DROP, False)),
    "self_correct_voids_same_choice_check": ("csv-export", [
        R("stream_writer", "streams rows"), C("stream_writer"),
        SC("stream_writer", "confirmed on review"), K("stream_writer")],
        ("REFUSE", "unchecked", NO_DROP, False)),
    "self_correct_elsewhere_voids_check": ("csv-export", [
        R("stream_writer", "streams rows"), C("stream_writer"),
        SC("ascii_writer", "maybe ascii is enough", True), K("stream_writer")],
        ("REFUSE", "unchecked", NO_DROP, False)),
    "drop_without_acceptable_claim": ("csv-export", [
        R("ascii_writer", "ascii covers our data"), C("ascii_writer"),
        K("ascii_writer")],
        ("REFUSE", "drops_requirement", ("utf8_output",), False)),
}


def tasks():
    return copy.deepcopy(TASKS)


def episodes():
    return copy.deepcopy(EPISODES)


def run_all():
    """Return {episode: (module tuple, oracle tuple, expected)}."""
    ts, es = tasks(), episodes()
    out = {}
    for name in sorted(es):
        tid, trace, expected = es[name]
        rec = S.evaluate(ts[tid], trace)
        orc = oracle.decide(ts[tid], trace)
        out[name] = ((rec["decision"], rec["reason"], rec["dropped"], rec["acceptable_claimed"]),
                     (orc["decision"], orc["reason"], orc["dropped"], orc["acceptable_claimed"]),
                     expected)
    return out


def summary():
    rows = run_all()
    agree = sum(1 for m, o, e in rows.values() if m == o)
    lines = ["%-38s %-7s %-21s %s" % (n, m[0], m[1], ",".join(m[2]) or "-")
             for n, (m, o, e) in sorted(rows.items())]
    lines.append("module vs oracle: %d/%d episodes agree" % (agree, len(rows)))
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
