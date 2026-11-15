"""V15 quote-substring verifier sketch (encoder-side) — not shipped in upstream pairl."""

from __future__ import annotations

from dataclasses import dataclass

ELISION_MARKER = " [...] "


@dataclass(frozen=True, slots=True)
class QuoteVerifyResult:
    ok: bool
    reason: str | None = None
    fragments: tuple[str, ...] = ()


def verify_quote_substrings_v15(
    *,
    source_turn: str,
    quoted_content: str,
    mode_cond: bool = False,
) -> QuoteVerifyResult:
    """Every extractive fragment must be an exact substring of source_turn, in order, no overlap."""

    if mode_cond:
        return QuoteVerifyResult(ok=True, reason="mode=cond_skipped")
    fragments = tuple(quoted_content.split(ELISION_MARKER))
    if not fragments or any(not frag for frag in fragments):
        return QuoteVerifyResult(ok=False, reason="empty_fragment")
    pos = 0
    for frag in fragments:
        idx = source_turn.find(frag, pos)
        if idx < 0:
            if source_turn.find(frag, 0) >= 0:
                return QuoteVerifyResult(
                    ok=False, reason="out_of_order", fragments=fragments
                )
            return QuoteVerifyResult(ok=False, reason="not_substring", fragments=fragments)
        pos = idx + len(frag)
    return QuoteVerifyResult(ok=True, fragments=fragments)
