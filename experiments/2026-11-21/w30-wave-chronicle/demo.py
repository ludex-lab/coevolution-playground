"""Deterministic demo on the frozen, pinned snapshot of the 13 real day READMEs (2026-11-09 to 2026-11-21, main f2fa1e5d).

Run: python3 -B demo.py   (prints the same bytes every run; compare with sha256sum)
Part 1 is the full v1 chronicle; part 2 is the week 2026-11-15..2026-11-21 with what changed since the 2026-11-20 day.
Every README is checked against fixtures/snapshot-f2fa1e5d/pins.txt (git blob SHA1 and size) before it is parsed.
"""

import os
import sys

import wave_chronicle as wc

HERE = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT = os.path.join(HERE, "fixtures", "snapshot-f2fa1e5d")
TRACKS = os.path.join(HERE, "fixtures", "tracks.json")


def main():
    base = {"root": os.path.join(SNAPSHOT, "experiments"), "pins": os.path.join(SNAPSHOT, "pins.txt"),
            "tracks": TRACKS}
    full = wc.run(dict(base))
    week = wc.run(dict(base, **{"from": "2026-11-15", "to": "2026-11-21", "base_to": "2026-11-20"}))
    out = ["Demo part 1: full chronicle (snapshot of main f2fa1e5d)", "",
           wc.render(full), "Demo part 2: week 2026-11-15 to 2026-11-21, what changed since 2026-11-20", "",
           wc.render(week)]
    sys.stdout.write("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
