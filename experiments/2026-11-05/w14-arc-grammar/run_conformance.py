#!/usr/bin/env python3
"""Run vendored upstream conformance corpus against arc_grammar."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from arc_grammar import validate, validate_sequence  # noqa: E402

CONF_DIR = ROOT / "conformance"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    manifest = json.loads((CONF_DIR / "manifest.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    total = 0

    for entry in manifest["files"]:
        rel = entry["file"]
        path = CONF_DIR / rel
        expected_sha = entry.get("sha256")
        if expected_sha and _sha256(path) != expected_sha:
            failures.append(f"sha256 drift on {rel}")
            continue
        cases = json.loads(path.read_text(encoding="utf-8"))
        for c in cases:
            total += 1
            if "event" in c:
                if c.get("validator_valid") is not None:
                    got = validate(c["event"]).ok
                    if got != c["validator_valid"]:
                        failures.append(
                            f"{c['id']}: validator_valid expected {c['validator_valid']}, got {got}"
                        )
            else:
                opts = c.get("options") or {}
                res = validate_sequence(
                    c["events"],
                    partial=opts.get("partial", False),
                    check_monotonic_sent_at=opts.get("checkMonotonicSentAt", False),
                )
                if res.ok != c["sequence_valid"]:
                    failures.append(
                        f"{c['id']}: sequence_valid expected {c['sequence_valid']}, got {res.ok}"
                    )
                if c.get("issue_index") is not None:
                    first = res.issues[0].index if res.issues else None
                    if first != c["issue_index"]:
                        failures.append(
                            f"{c['id']}: issue_index expected {c['issue_index']}, got {first}"
                        )

    for f in failures:
        print(f"FAIL  {f}", file=sys.stderr)

    print(f"conformance (arc_grammar): {total - len(failures)}/{total} cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
