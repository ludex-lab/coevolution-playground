import unittest

from unseen_time_sketch import (
    LadderPhase,
    Presence,
    record_ping,
    tick_unseen,
    unseen_rate,
)


class UnseenTimeSketchTests(unittest.TestCase):
    def test_rates_match_sundial_prose(self) -> None:
        self.assertEqual(unseen_rate(Presence.HERE), 0.0)
        self.assertEqual(unseen_rate(Presence.ELSEWHERE), 0.5)
        self.assertEqual(unseen_rate(Presence.AWAY), 1.0)

    def test_here_paused_elsewhere_half_away_full(self) -> None:
        r = tick_unseen(
            unseen_seconds=0.0,
            wall_seconds=0.0,
            pings_sent=0,
            delta_wall_s=120.0,
            presence=Presence.HERE,
            wall_ceiling_s=9999.0,
        )
        self.assertEqual(r.unseen_seconds, 0.0)
        self.assertEqual(r.wall_seconds, 120.0)

        r = tick_unseen(
            unseen_seconds=0.0,
            wall_seconds=0.0,
            pings_sent=0,
            delta_wall_s=120.0,
            presence=Presence.ELSEWHERE,
            wall_ceiling_s=9999.0,
        )
        self.assertEqual(r.unseen_seconds, 60.0)

        r = tick_unseen(
            unseen_seconds=0.0,
            wall_seconds=0.0,
            pings_sent=0,
            delta_wall_s=120.0,
            presence=Presence.AWAY,
            wall_ceiling_s=9999.0,
        )
        self.assertEqual(r.unseen_seconds, 120.0)

    def test_wall_ceiling_forces_terminal_even_if_here(self) -> None:
        r = tick_unseen(
            unseen_seconds=0.0,
            wall_seconds=1700.0,
            pings_sent=0,
            delta_wall_s=200.0,
            presence=Presence.HERE,
            wall_ceiling_s=1800.0,
        )
        self.assertEqual(r.phase, LadderPhase.WALL_FORCED_TERMINAL)
        self.assertGreaterEqual(r.wall_seconds, 1800.0)

    def test_ping_cap_three(self) -> None:
        n = 0
        n = record_ping(n)
        n = record_ping(n)
        n = record_ping(n)
        with self.assertRaises(ValueError):
            record_ping(n)


if __name__ == "__main__":
    unittest.main()
