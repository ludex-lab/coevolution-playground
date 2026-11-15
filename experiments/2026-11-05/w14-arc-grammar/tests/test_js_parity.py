"""Reject cases where Python unicode-regex/len diverged from JS reference."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from arc_grammar import validate  # noqa: E402

_BASE = {
    "arc_id": "a",
    "phase": "heartbeat",
    "title": "ok",
    "sent_at": "2026-06-14T09:00:00Z",
}


def _event(**overrides: object) -> dict:
    out = dict(_BASE)
    out.update(overrides)
    return out


class JsParityRejects(unittest.TestCase):
    def test_sent_at_trailing_newline(self) -> None:
        self.assertFalse(validate(_event(sent_at="2026-06-14T09:00:00Z\n")).ok)

    def test_sent_at_arabic_indic_digits(self) -> None:
        sent_at = "\u0662\u0660\u0662\u0666-06-14T09:00:00Z"
        self.assertFalse(validate(_event(sent_at=sent_at)).ok)

    def test_protocol_version_fullwidth_digits(self) -> None:
        self.assertFalse(validate(_event(protocol_version="\uff10.\uff12")).ok)

    def test_protocol_version_trailing_newline(self) -> None:
        self.assertFalse(validate(_event(protocol_version="0.2\n")).ok)

    def test_title_101_emoji_utf16_cap(self) -> None:
        title = "😀" * 101
        self.assertFalse(validate(_event(title=title)).ok)

    def test_sent_at_year_leading_zeros(self) -> None:
        self.assertFalse(validate(_event(sent_at="0050-06-14T09:00:00Z")).ok)

    def test_sent_at_year_0100_accept(self) -> None:
        self.assertTrue(validate(_event(sent_at="0100-06-15T09:00:00Z")).ok)

    def test_arc_id_65_emoji_utf16_cap(self) -> None:
        arc_id = "😀" * 65
        self.assertFalse(validate(_event(arc_id=arc_id)).ok)


class JsParityAccepts(unittest.TestCase):
    def test_title_lone_surrogate_does_not_crash(self) -> None:
        result = validate(_event(title="\ud83d"))
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
