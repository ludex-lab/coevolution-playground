"""Showcase source + extractive `#rpt` bytes for V15 (not full PAIRL messages)."""

from __future__ import annotations

from quote_substring_v15 import ELISION_MARKER

# Upstream examples/09-extractive-quotes.pairl `#a2` turn text @ pin 0286fd1 (verbatim).
SHOWCASE_SOURCE_TURN_A2 = (
    "Check maxclients in redis.conf — Redis 7.2 lowered the default from 10000 to 4096. "
    "Your pool size of 200 connections per pod across 12 pods = 2400, which fits, "
    "but if some connections are stuck in CLOSE_WAIT you could hit the limit."
)

# Extractive fragments only — elided middle is omitted on purpose, not a full turn replay.
SHOWCASE_EXTRACTIVE_RPT_CONTENT = (
    "Check maxclients in redis.conf — Redis 7.2 lowered the default from 10000 to 4096."
    f"{ELISION_MARKER}stuck in CLOSE_WAIT you could hit the limit."
)

# Paraphrase of the same spans (Checker fold: must fail V15).
SHOWCASE_PARAPHRASE_RPT_CONTENT = (
    "Redis 7.2 lowered maxclients default from 10000 to 4096."
    f"{ELISION_MARKER}stuck in CLOSE_WAIT you could hit the limit."
)
