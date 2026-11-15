#!/usr/bin/env python3
"""Print next-wave status; apply NDJSON wave file if present."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WAVE = Path("/workspace/_mirror_waves/wave_pending.ndjson")


def main() -> int:
    subprocess.run([sys.executable, "/workspace/_mirror_refresh_missing.py"], check=False)
    if WAVE.is_file() and WAVE.stat().st_size > 0:
        data = WAVE.read_bytes()
        proc = subprocess.run(
            [sys.executable, "/workspace/_mirror_agent_persist_mcp.py"],
            input=data,
            capture_output=True,
        )
        print(proc.stdout.decode() or proc.stderr.decode())
        WAVE.unlink(missing_ok=True)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    out = subprocess.check_output(
        [sys.executable, "/workspace/_mirror_next_batch_by_size.py", str(n)],
        text=True,
    )
    print(out, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())