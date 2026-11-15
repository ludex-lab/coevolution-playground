"""Unit tests for the look_again pure-fn sketch."""

from __future__ import annotations

import unittest

from look_again_pure import look_again_pure


class LookAgainPureTests(unittest.TestCase):
    def test_go_when_board_unchanged(self) -> None:
        verdict = look_again_pure(
            board_revision_at_compose=3,
            board_revision_now=3,
            action_kind="message",
            interim_events=(),
            answer_candidates=("speak", "silent"),
        )
        self.assertEqual(verdict.decision, "GO")
        self.assertEqual(verdict.answer_candidates, ("speak", "silent"))

    def test_hold_when_board_advanced_with_other_message(self) -> None:
        verdict = look_again_pure(
            board_revision_at_compose=2,
            board_revision_now=5,
            action_kind="message",
            interim_events=(
                {"id": "e1", "type": "message", "author": "peer", "text": "wait"},
            ),
            answer_candidates=("speak",),
        )
        self.assertEqual(verdict.decision, "HOLD")
        self.assertEqual(verdict.held_by_other_messages, 1)

    def test_go_when_board_advanced_but_only_own_messages(self) -> None:
        verdict = look_again_pure(
            board_revision_at_compose=1,
            board_revision_now=4,
            action_kind="message",
            interim_events=(
                {"id": "e1", "type": "message", "author": "agent", "text": "draft"},
            ),
            answer_candidates=(),
        )
        self.assertEqual(verdict.decision, "GO")

    def test_go_when_board_advanced_but_only_reactions(self) -> None:
        verdict = look_again_pure(
            board_revision_at_compose=1,
            board_revision_now=2,
            action_kind="message",
            interim_events=(
                {"id": "r1", "type": "reaction", "author": "peer", "emoji": "👍"},
            ),
            answer_candidates=("speak",),
        )
        self.assertEqual(verdict.decision, "GO")

    def test_go_on_second_look(self) -> None:
        verdict = look_again_pure(
            board_revision_at_compose=1,
            board_revision_now=9,
            action_kind="message",
            interim_events=(
                {"id": "e1", "type": "message", "author": "peer", "text": "new"},
            ),
            answer_candidates=("speak",),
            already_looked_again=True,
        )
        self.assertEqual(verdict.decision, "GO")

    def test_go_when_expand_failed_even_if_messages(self) -> None:
        verdict = look_again_pure(
            board_revision_at_compose=0,
            board_revision_now=2,
            action_kind="message",
            interim_events=(
                {"id": "e1", "type": "message", "author": "peer", "text": "x"},
            ),
            answer_candidates=("speak",),
            expand_failed=True,
        )
        self.assertEqual(verdict.decision, "GO")


if __name__ == "__main__":
    unittest.main()
