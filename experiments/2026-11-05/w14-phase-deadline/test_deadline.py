"""Invariant tests ported from pi-toolkit tests/core/deadline-grace.test.ts (allowed surface only)."""

from __future__ import annotations

import math
import unittest

from deadline import (
    MAX_DEADLINE_SPAN_MS,
    OVERTIME_PHASES,
    PhaseBudget,
    PhaseDiag,
    RunDeadlines,
    RunSlice,
    due_at_for,
    extendability,
    extendable_span_ms,
    extension_grant_cap_ms,
    grant_extension_ms,
    grace_window,
    hard_deadline_at_for,
    idle_due_at,
)


def lab_budget(**overrides: object) -> PhaseBudget:
    base = PhaseBudget(
        slot_wait_ms=120_000,
        boot_ms=45_000,
        attach_ms=90_000,
        first_token_ms=180_000,
        idle_ms=300_000,
        model_slice_cap_ms=1_200_000,
        tool_ms=900_000,
        compact_ms=420_000,
        shutdown_grace_ms=15_000,
        reap_ms=8_000,
        retry_slack_ms=4_000,
        total_ms=2_400_000,
        total_grace_ms=120_000,
        max_extensions=3,
        max_total_factor=2.0,
        extend_step_ms=3_600_000,
    )
    fields = {f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    fields.update(overrides)
    return PhaseBudget(**fields)


def slice_state(**overrides: object) -> RunSlice:
    base = RunSlice(
        status="running",
        phase="model_slice",
        deadlines=RunDeadlines(deadline_at=100_000, hard_deadline_at=200_000),
        extensions_used=0,
    )
    fields = {f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    fields.update(overrides)
    return RunSlice(**fields)


class ExtendableSpanTests(unittest.TestCase):
    base = {"total_ms": 100, "max_total_factor": 2, "max_extensions": 3, "extend_step_ms": 500}

    cases = [
        ({}, 1_600),
        ({"total_ms": 2_000}, 4_000),
        ({"total_ms": 101, "max_total_factor": 1.5, "extend_step_ms": 0}, 152),
        ({"max_total_factor": 1}, 100),
        ({"max_total_factor": -2}, 100),
        ({"max_total_factor": math.nan}, 100),
        ({"max_total_factor": math.inf}, 100),
        ({"max_extensions": 0}, 200),
        ({"max_extensions": -1}, 200),
        ({"max_extensions": math.nan}, 200),
        ({"max_extensions": math.inf}, 200),
        ({"max_extensions": 1.9}, 600),
        ({"extend_step_ms": 0}, 200),
        ({"extend_step_ms": -1}, 200),
        ({"extend_step_ms": math.nan}, 200),
        ({"extend_step_ms": math.inf}, 200),
        ({"total_ms": 0}, None),
        ({"total_ms": -1}, None),
        ({"total_ms": math.nan}, None),
        ({"total_ms": -math.inf}, None),
        ({"total_ms": math.inf}, MAX_DEADLINE_SPAN_MS),
        ({"max_total_factor": 1e308}, MAX_DEADLINE_SPAN_MS),
        ({"extend_step_ms": 1e308}, MAX_DEADLINE_SPAN_MS),
        ({"total_ms": MAX_DEADLINE_SPAN_MS + 1}, MAX_DEADLINE_SPAN_MS),
    ]

    def test_table(self) -> None:
        for overrides, expected in self.cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(extendable_span_ms({**self.base, **overrides}), expected)


class HardDeadlineTests(unittest.TestCase):
    def test_factor_without_step(self) -> None:
        b = lab_budget(total_ms=100, max_total_factor=2, extend_step_ms=0)
        self.assertEqual(hard_deadline_at_for(1_000, b, None), 1_200)

    def test_step_widens_short_run(self) -> None:
        b = lab_budget(total_ms=25 * 60_000, max_total_factor=2, extend_step_ms=3_600_000)
        self.assertEqual(hard_deadline_at_for(1_000, b, None), 1_000 + 25 * 60_000 + 3 * 3_600_000)
        b2 = lab_budget(total_ms=100, max_total_factor=2, extend_step_ms=500)
        self.assertEqual(hard_deadline_at_for(0, b2, None), 100 + 3 * 500)

    def test_factor_dominates_long_run(self) -> None:
        b = lab_budget(total_ms=4 * 3_600_000, max_total_factor=2, extend_step_ms=3_600_000)
        self.assertEqual(hard_deadline_at_for(0, b, None), 8 * 3_600_000)

    def test_fixed_shape_unchanged(self) -> None:
        b = lab_budget(total_ms=100, max_total_factor=1, extend_step_ms=3_600_000)
        self.assertEqual(hard_deadline_at_for(0, b, None), 100)
        b2 = lab_budget(total_ms=100, max_total_factor=2, max_extensions=0)
        self.assertEqual(hard_deadline_at_for(0, b2, None), 200)

    def test_cap_tightens_only(self) -> None:
        b = lab_budget(total_ms=100, max_total_factor=3, extend_step_ms=0)
        self.assertEqual(hard_deadline_at_for(0, b, 150), 150)
        self.assertEqual(hard_deadline_at_for(0, lab_budget(total_ms=100, max_total_factor=2, extend_step_ms=0), 999_999), 200)

    def test_invalid_total(self) -> None:
        self.assertIsNone(hard_deadline_at_for(0, lab_budget(total_ms=0), None))
        self.assertIsNone(hard_deadline_at_for(0, lab_budget(total_ms=-5), None))


class ExtensionGrantCapTests(unittest.TestCase):
    def test_step_caps_grant(self) -> None:
        b = lab_budget(extend_step_ms=3_600_000)
        self.assertEqual(extension_grant_cap_ms(b, 7_200_000), (True, 3_600_000))
        self.assertEqual(extension_grant_cap_ms(b, 1_800_000), (True, 1_800_000))

    def test_non_positive_step_typed_refuse(self) -> None:
        b = lab_budget(extend_step_ms=0)
        self.assertEqual(extension_grant_cap_ms(b, 7_200_000), (False, "step_disabled"))
        self.assertEqual(extension_grant_cap_ms(lab_budget(extend_step_ms=math.nan), 1_000), (False, "step_disabled"))

    def test_bad_extend_ms_yields_zero_grant_not_refusal(self) -> None:
        b = lab_budget(extend_step_ms=3_600_000)
        self.assertEqual(extension_grant_cap_ms(b, math.nan), (True, 0))


class GrantExtensionTests(unittest.TestCase):
    def test_headroom_clamps_oversized_request(self) -> None:
        """Checker probe: cap=3.6e6 but headroom=100k ⇒ grant 100k, new deadline ≤ hard."""
        st = slice_state(deadlines=RunDeadlines(deadline_at=100_000, hard_deadline_at=200_000))
        b = lab_budget(extend_step_ms=3_600_000)
        ok, grant = grant_extension_ms(st, b, 0, 7_200_000)
        self.assertTrue(ok)
        self.assertEqual(grant, 100_000)
        self.assertLessEqual(st.deadlines.deadline_at + grant, st.deadlines.hard_deadline_at)

    def test_propagates_extendability_refusal(self) -> None:
        self.assertEqual(grant_extension_ms(slice_state(extensions_used=3), lab_budget(), 0, 1_000), (False, "limit_reached"))

    def test_propagates_step_disabled(self) -> None:
        self.assertEqual(
            grant_extension_ms(slice_state(), lab_budget(extend_step_ms=0), 0, 1_000),
            (False, "step_disabled"),
        )


class ExtendabilityTests(unittest.TestCase):
    def test_ok_headroom(self) -> None:
        verdict = extendability(slice_state(), lab_budget(), 50_000)
        self.assertEqual(verdict, (True, 100_000))

    def test_terminal_and_stopping(self) -> None:
        for status in ("completed", "failed", "timed_out", "aborted"):
            self.assertEqual(extendability(slice_state(status=status), lab_budget(), 0), (False, "already_terminal"))
        self.assertEqual(extendability(slice_state(phase="shutdown_grace"), lab_budget(), 0), (False, "stopping"))

    def test_not_started_vs_overtime(self) -> None:
        for phase in ("ingress_queue", "config_resolve", "session_open", "worker_attach"):
            self.assertEqual(extendability(slice_state(phase=phase), lab_budget(), 0), (False, "not_started"))
        for phase in OVERTIME_PHASES:
            self.assertTrue(extendability(slice_state(phase=phase), lab_budget(), 0)[0])

    def test_uncapped_limit_headroom(self) -> None:
        self.assertEqual(
            extendability(slice_state(deadlines=RunDeadlines(None, 200_000)), lab_budget(), 0),
            (False, "uncapped"),
        )
        self.assertEqual(
            extendability(slice_state(extensions_used=3), lab_budget(), 0),
            (False, "limit_reached"),
        )
        self.assertEqual(extendability(slice_state(), lab_budget(), 200_000), (False, "no_headroom"))


class GraceWindowTests(unittest.TestCase):
    def test_clamped_to_hard_ceiling(self) -> None:
        b = lab_budget(total_grace_ms=90_000)
        self.assertEqual(grace_window(slice_state(), b, 100_000), 190_000)
        self.assertEqual(grace_window(slice_state(), b, 150_000), 200_000)

    def test_refusals(self) -> None:
        b = lab_budget()
        self.assertIsNone(grace_window(slice_state(), lab_budget(total_grace_ms=0), 100_000))
        self.assertIsNone(grace_window(slice_state(extensions_used=3), b, 100_000))
        self.assertIsNone(grace_window(slice_state(), lab_budget(max_extensions=0), 100_000))
        self.assertIsNone(grace_window(slice_state(), b, 200_000))
        self.assertIsNone(grace_window(slice_state(phase="ingress_queue"), b, 100_000))


class DueAtTests(unittest.TestCase):
    def test_model_slice_dual_bound(self) -> None:
        b = lab_budget(idle_ms=100, model_slice_cap_ms=500)
        diag = PhaseDiag(phase_entered_at=1_000, last_event_at=1_200)
        self.assertEqual(due_at_for("model_slice", diag, b), 1_300)
        self.assertEqual(due_at_for("model_slice", PhaseDiag(1_000, 1_200), lab_budget(idle_ms=0, model_slice_cap_ms=500)), 1_500)
        self.assertEqual(due_at_for("model_slice", PhaseDiag(1_000, 1_200), lab_budget(idle_ms=100, model_slice_cap_ms=0)), 1_300)

    def test_model_slice_last_event_zero_not_falsy(self) -> None:
        b = lab_budget(idle_ms=100, model_slice_cap_ms=500)
        self.assertEqual(due_at_for("model_slice", PhaseDiag(phase_entered_at=1_000, last_event_at=0), b), 100)

    def test_retry_cooldown_uses_idle(self) -> None:
        b = lab_budget(idle_ms=50, retry_slack_ms=10)
        diag = PhaseDiag(phase_entered_at=0, last_event_at=100, retry_delay_ms=200)
        self.assertEqual(due_at_for("retry_cooldown", diag, b), idle_due_at(diag, b))
        self.assertEqual(idle_due_at(diag, b), 360)


class PropertyInvariants(unittest.TestCase):
    def test_cap_at_never_loosens(self) -> None:
        b = lab_budget(total_ms=100, max_total_factor=2, extend_step_ms=500)
        raw = hard_deadline_at_for(0, b, None)
        assert raw is not None
        for cap in (50, 150, raw, raw + 10_000):
            capped = hard_deadline_at_for(0, b, cap)
            self.assertIsNotNone(capped)
            self.assertLessEqual(capped, raw)  # type: ignore[arg-type]

    def test_grace_never_exceeds_hard(self) -> None:
        st = slice_state()
        b = lab_budget()
        for at in (50_000, 100_000, 199_000):
            gw = grace_window(st, b, at)
            if gw is not None:
                self.assertLessEqual(gw, st.deadlines.hard_deadline_at)


if __name__ == "__main__":
    unittest.main()
