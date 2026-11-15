import unittest

from coop_ack_floor_pure import (
    PAUSE_BUDGET,
    SideTurnBudget,
    after_public_turn,
    gate_agent_public_move,
    next_floor_side,
    unread_human_seqs,
    validate_one_line_summary,
)


class CoopAckFloorPureTests(unittest.TestCase):
    def test_summary_one_line(self) -> None:
        self.assertIsNone(validate_one_line_summary("Ship UTC dates only."))
        self.assertEqual(validate_one_line_summary(""), "summary_required")
        self.assertEqual(validate_one_line_summary("a\nb"), "summary_one_line")

    def test_unread_human_seqs(self) -> None:
        self.assertEqual(unread_human_seqs(ack=3, human_seqs=(2, 4, 5)), (4, 5))

    def test_happy_path(self) -> None:
        r = gate_agent_public_move(
            floor_side=0,
            poster_side=0,
            pause_kind="",
            ack=5,
            move_type="say",
            summary="Propose API shape.",
            re_seq=0,
            human_seqs=(1, 3, 5),
        )
        self.assertTrue(r.ok, r.code)

    def test_unread_human_refuse(self) -> None:
        r = gate_agent_public_move(
            floor_side=0,
            poster_side=0,
            pause_kind="",
            ack=3,
            move_type="agree",
            summary="OK with constraint.",
            re_seq=10,
            human_seqs=(1, 4),
        )
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "unread_human_message")
        self.assertEqual(r.unread_seqs, (4,))

    def test_floor_and_existing_budget_pause(self) -> None:
        wrong_floor = gate_agent_public_move(
            floor_side=1,
            poster_side=0,
            pause_kind="",
            ack=9,
            move_type="say",
            summary="Wait my turn.",
            re_seq=0,
            human_seqs=(9,),
        )
        self.assertEqual(wrong_floor.code, "not_your_turn")
        paused = gate_agent_public_move(
            floor_side=0,
            poster_side=0,
            pause_kind=PAUSE_BUDGET,
            ack=9,
            move_type="say",
            summary="After resume.",
            re_seq=0,
            human_seqs=(9,),
        )
        self.assertEqual(paused.code, "paused")

    def test_turn_budget_counter_sets_pause(self) -> None:
        budget = SideTurnBudget(turn_budget=2, turns_used=(0, 0))
        budget, pause = after_public_turn(budget, side=0)
        self.assertEqual(pause, "")
        self.assertEqual(budget.turns_used, (1, 0))
        budget, pause = after_public_turn(budget, side=0)
        self.assertEqual(pause, PAUSE_BUDGET)
        self.assertEqual(budget.turns_used, (2, 0))
        blocked = gate_agent_public_move(
            floor_side=0,
            poster_side=0,
            pause_kind=pause,
            ack=10,
            move_type="say",
            summary="Should block while paused.",
            re_seq=0,
            human_seqs=(10,),
        )
        self.assertEqual(blocked.code, "paused")

    def test_next_floor_pass_keep_to(self) -> None:
        self.assertEqual(
            next_floor_side(floor_side=0, poster_side=0, n_sides=2, floor_mode="keep"),
            0,
        )
        self.assertEqual(
            next_floor_side(floor_side=0, poster_side=0, n_sides=2, floor_mode="pass"),
            1,
        )
        self.assertEqual(
            next_floor_side(
                floor_side=0, poster_side=0, n_sides=3, floor_mode="pass", to_side=2
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()
