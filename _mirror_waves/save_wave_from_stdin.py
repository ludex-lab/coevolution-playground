#!/usr/bin/env python3
"""Read NDJSON MCP get_file_contents objects from stdin; persist via _mirror_agent_persist_mcp."""
from __future__ import annotations

import subprocess
import sys

if __name__ == "__main__":
    data = sys.stdin.buffer.read()
    if not data.strip():
        print("empty stdin", file=sys.stderr)
        raise SystemExit(1)
    proc = subprocess.run(
        [sys.executable, "/workspace/_mirror_agent_persist_mcp.py"],
        input=data,
        capture_output=True,
    )
    sys.stdout.buffer.write(proc.stdout)
    sys.stderr.buffer.write(proc.stderr)
    raise SystemExit(proc.returncode)