"""Unit tests for V15 quote-substring verifier sketch."""

from __future__ import annotations

import unittest

from handoff_showcase import (
    SHOWCASE_EXTRACTIVE_RPT_CONTENT,
    SHOWCASE_PARAPHRASE_RPT_CONTENT,
    SHOWCASE_SOURCE_TURN_A2,
)
from quote_substring_v15 import ELISION_MARKER, verify_quote_substrings_v15


class QuoteSubstringV15Tests(unittest.TestCase):
    def test_accepts_single_exact_substring(self) -> None:
        source = "Latency hit 800ms after the Redis upgrade."
        content = "800ms after the Redis upgrade."
        result = verify_quote_substrings_v15(source_turn=source, quoted_content=content)
        self.assertTrue(result.ok)
        self.assertEqual(result.fragments, (content,))

    def test_accepts_ordered_non_overlapping_extractive_spans(self) -> None:
        source = (
            "Our API latency spiked to 800ms P99 after the Redis upgrade. "
            "Before it was 120ms. Then connection pool exhaustion at 14:32 UTC."
        )
        content = (
            "Our API latency spiked to 800ms P99 after the Redis upgrade."
            f"{ELISION_MARKER}connection pool exhaustion at 14:32 UTC."
        )
        result = verify_quote_substrings_v15(source_turn=source, quoted_content=content)
        self.assertTrue(result.ok)
        self.assertEqual(len(result.fragments), 2)

    def test_rejects_hallucinated_fragment(self) -> None:
        source = "maxclients was at 4096."
        content = "maxclients was at 8192."
        result = verify_quote_substrings_v15(source_turn=source, quoted_content=content)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "not_substring")

    def test_rejects_out_of_order_fragments(self) -> None:
        source = "alpha beta gamma"
        content = f"beta{ELISION_MARKER}alpha"
        result = verify_quote_substrings_v15(source_turn=source, quoted_content=content)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "out_of_order")

    def test_accepts_elision_with_nothing_omitted_between_fragments(self) -> None:
        source = "hello world"
        content = f"hello{ELISION_MARKER}world"
        result = verify_quote_substrings_v15(source_turn=source, quoted_content=content)
        self.assertTrue(result.ok)

    def test_showcase_handoff_extractive_rpt_passes_v15(self) -> None:
        result = verify_quote_substrings_v15(
            source_turn=SHOWCASE_SOURCE_TURN_A2,
            quoted_content=SHOWCASE_EXTRACTIVE_RPT_CONTENT,
        )
        self.assertTrue(result.ok, result.reason)

    def test_showcase_paraphrase_rejected_not_substring(self) -> None:
        result = verify_quote_substrings_v15(
            source_turn=SHOWCASE_SOURCE_TURN_A2,
            quoted_content=SHOWCASE_PARAPHRASE_RPT_CONTENT,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "not_substring")

    def test_skips_when_mode_cond(self) -> None:
        result = verify_quote_substrings_v15(
            source_turn="truth",
            quoted_content="invented prose",
            mode_cond=True,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.reason, "mode=cond_skipped")


if __name__ == "__main__":
    unittest.main()
