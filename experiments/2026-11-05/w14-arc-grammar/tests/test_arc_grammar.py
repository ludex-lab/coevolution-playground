import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from arc_grammar import (  # noqa: E402
    ArcSeed,
    CadenceConfig,
    CadenceController,
    ReceiptLiveness,
    validate,
    validate_sequence,
)

CONF_DIR = ROOT / "conformance"
FLOOR = 5 * 60_000
# Upstream reference default (§5.2) — test-only; not a Team OS timing constant.
REFERENCE_SILENCE_WINDOW_MS = 20 * 60_000


class Clock:
    def __init__(self, t: int = 0) -> None:
        self.t = t

    def __call__(self) -> int:
        return self.t

    def advance(self, ms: int) -> None:
        self.t += ms


class ConformanceCorpus(unittest.TestCase):
    def test_vendor_corpus_matches_validator(self) -> None:
        manifest = json.loads((CONF_DIR / "manifest.json").read_text(encoding="utf-8"))
        failures: list[str] = []
        total = 0
        for entry in manifest["files"]:
            cases = json.loads((CONF_DIR / entry["file"]).read_text(encoding="utf-8"))
            for c in cases:
                total += 1
                if "event" in c:
                    if (
                        c.get("validator_valid") is not None
                        and validate(c["event"]).ok != c["validator_valid"]
                    ):
                        failures.append(c["id"])
                else:
                    opts = c.get("options") or {}
                    res = validate_sequence(
                        c["events"],
                        partial=opts.get("partial", False),
                        check_monotonic_sent_at=opts.get("checkMonotonicSentAt", False),
                    )
                    if res.ok != c["sequence_valid"]:
                        failures.append(c["id"])
        self.assertEqual(failures, [], failures)
        self.assertGreaterEqual(total, 70)


class CadenceSketch(unittest.TestCase):
    def test_floor_gates_started(self) -> None:
        clk = Clock(0)
        ctrl = CadenceController(
            CadenceConfig(
                cadence_floor_ms=FLOOR,
                heartbeat_interval_ms=REFERENCE_SILENCE_WINDOW_MS,
                now=clk,
            )
        )
        self.assertIsNone(ctrl.begin(ArcSeed(arc_id="a", title="build")))
        clk.advance(FLOOR + 1)
        event = ctrl.tick()
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["phase"], "started")
        self.assertTrue(validate(event).ok)

    def test_heartbeat_after_interval(self) -> None:
        clk = Clock(0)
        ctrl = CadenceController(
            CadenceConfig(cadence_floor_ms=0, heartbeat_interval_ms=REFERENCE_SILENCE_WINDOW_MS, now=clk)
        )
        started = ctrl.begin(ArcSeed(arc_id="a", title="build"))
        assert started is not None
        ctrl.on_emit(started)
        clk.advance(REFERENCE_SILENCE_WINDOW_MS + 1)
        hb = ctrl.tick("working")
        self.assertIsNotNone(hb)
        assert hb is not None
        self.assertEqual(hb["phase"], "heartbeat")

    def test_no_heartbeat_after_blocked_until_milestone(self) -> None:
        clk = Clock(0)
        ctrl = CadenceController(
            CadenceConfig(
                cadence_floor_ms=0,
                heartbeat_interval_ms=REFERENCE_SILENCE_WINDOW_MS,
                now=clk,
            )
        )
        started = ctrl.begin(ArcSeed(arc_id="a", title="build"))
        assert started is not None
        ctrl.on_emit(started)
        blocked = {
            "arc_id": "a",
            "phase": "blocked",
            "title": "waiting",
            "sent_at": "2026-06-14T09:00:00Z",
        }
        ctrl.on_emit(blocked)
        clk.advance(REFERENCE_SILENCE_WINDOW_MS + 1)
        self.assertIsNone(ctrl.tick())
        self.assertTrue(validate_sequence([started, blocked], partial=True).ok)
        milestone = {
            "arc_id": "a",
            "phase": "milestone",
            "title": "resumed",
            "sent_at": "2026-06-14T09:05:00Z",
        }
        ctrl.on_emit(milestone)
        clk.advance(REFERENCE_SILENCE_WINDOW_MS + 1)
        hb = ctrl.tick("working")
        self.assertIsNotNone(hb)
        assert hb is not None
        self.assertEqual(hb["phase"], "heartbeat")


class ReceiptLivenessSketch(unittest.TestCase):
    def test_uses_local_receipt_not_sent_at(self) -> None:
        clk = Clock(0)
        live = ReceiptLiveness(now=clk)
        live.record("a", receipt_ms=0)
        _ = {
            "arc_id": "a",
            "phase": "heartbeat",
            "title": "looks recent",
            "sent_at": "2099-01-01T00:00:00Z",
        }
        clk.advance(REFERENCE_SILENCE_WINDOW_MS + 1)
        self.assertTrue(live.heartbeat_due("a", REFERENCE_SILENCE_WINDOW_MS))
        live.forget("a")
        self.assertIsNone(live.ms_since_receipt("a"))


if __name__ == "__main__":
    unittest.main()
