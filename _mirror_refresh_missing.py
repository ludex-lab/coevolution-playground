#!/usr/bin/env python3
"""Rebuild /tmp/missing_on_disk.txt from manifest vs non-zero workspace files."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

MANIFEST = Path("/tmp/mirror-manifest.json")
OUT = Path("/tmp/missing_on_disk.txt")
ROOT = Path("/workspace")
SKIP = {"README.md"}


def main() -> int:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing: list[str] = []
    for b in m.get("blobs", []):
        p = b["path"]
        if p in SKIP:
            continue
        if p.endswith(".env") or "__pycache__" in p.split("/"):
            continue
        sz = b.get("size", 0) or 0
        if sz > 5_242_880:
            continue
        fp = ROOT / p
        if not fp.is_file() or fp.stat().st_size == 0:
            missing.append(p)
    OUT.write_text("\n".join(missing) + ("\n" if missing else ""), encoding="utf-8")
    exp = subprocess.run(
        ["find", str(ROOT / "experiments"), "-type", "f"],
        capture_output=True,
        text=True,
    )
    exp_n = len([x for x in exp.stdout.splitlines() if x.strip()])
    top_ok = sum(
        1
        for p in (".gitignore", "CONTRIBUTING.md")
        if (ROOT / p).is_file() and (ROOT / p).stat().st_size > 0
    )
    print(
        json.dumps(
            {
                "missing": len(missing),
                "experiment_files": exp_n,
                "top_level_ok": top_ok,
                "target_experiments": 531,
                "target_total_excl_readme": 533,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())