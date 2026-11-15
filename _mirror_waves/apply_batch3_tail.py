#!/usr/bin/env python3
"""Apply batch 3 tail payloads from MCP fetch wave."""
from __future__ import annotations

import json
import subprocess

PAYLOADS = [
    {
        "files": [
            {
                "path": "experiments/2026-11-09/w18-effect-reversibility/NOTICE",
                "content": "Tk9USUNFIOKAlCBleHBlcmltZW50cy8yMDI2LTExLTA5L3cxOC1lZmZlY3QtcmV2ZXJzaWJpbGl0eS8KClBhcGVyOiBGcm9tIEVtZXJnZW5jZSB0byBSZXZlcnNpYmlsaXR5OiBUb3dhcmQgUmV2ZXJzaWJsZSBNdWx0aS1BZ2VudApTeXN0ZW1zLCBaaGVuZ3llIEhhbiBhbmQgTGluZGEgTmcgQm95bGUsIGFyWGl2IDI2MTEuMDkwNTQgKHYxLCBjcy5NQSwKc3VibWl0dGVkIDYgTm92IDIwMjYpLCBodHRwczovL2FyeGl2Lm9yZy9hYnMvMjYxMS4wOTA1NC4gUGFwZXIgbGljZW5jZToKQ0MgQlkgNC4wIChodHRwczovL2NyZWF0aXZlY29tbW9ucy5vcmcvbGljZW5zZXMvYnkvNC4wLyksIGNvbmZpcm1lZCBmcm9tIHRoZQphYnMgcGFnZSAiUmlnaHRzIHRvIHRoaXMgYXJ0aWNsZSIgbGluayBvbiAyMDI2LTExLTA5LgpVc2VkIGZvciBtZXRob2QtY2l0ZSBvbmx5OyBzaG9ydCBxdW90ZXMgYXBwZWFyIGluIHBhcGVyX2V2aWRlbmNlLmpzb24gb25seSwgZm9yIGV2aWRlbmNlLCB3aXRoCmF0dHJpYnV0aW9uIHRvIHRoZSBwYXBlcidzIGF1dGhvcnMuCgpUaGUgcGFwZXIgaXMgYSByZXNlYXJjaCBhZ2VuZGEuIEl0IHB1Ymxpc2hlcyBubyBjb2RlIGFuZCByZXBvcnRzIG5vCmV4cGVyaW1lbnRzLCBzbyB0aGVyZSBpcyBubyB1cHN0cmVhbSBjb2RlIHBpbiBhbmQgbm90aGluZyB3YXMgcmVwcm9kdWNlZC4KSXRzIGNyaXRlcmlvbiBpcyB0aGF0IHNvbWUgYXV0aG9yaXplZCBpbnRlcnZlbnRpb24ga2VlcHMgYSBzcGVjaWZpZWQKcHJvaGliaXRlZCBlZmZlY3QgcmFyZSB3aGlsZSBtYWludGFpbmluZyByZXF1aXJlZCBzZXJ2aWNlOyB0aGlzIHNrZXRjaCBkb2VzCm5vdCBjbGFpbSBtb3JlIHRoYW4gdGhhdC4KClRoaXMgZGlyZWN0b3J5J3MgY29kZSBpcyBhbiBpbmRlcGVuZGVudGx5IGF1dGhvcmVkIGNsZWFuLXJvb20gUHl0aG9uIHN0ZGxpYgptZXRob2Qgc2tldGNoLgoKRml4dHVyZXMgYXJlIHN5bnRoZXRpYyB0b3kgZGF0YSBhdXRob3JlZCBmb3IgdGhpcyBza2V0Y2guCg==",
                "encoding": "base64",
                "sha": "3aad6b7e4aee893dbf29ec666666fd8817965c06",
            }
        ]
    },
]

# Remaining payloads appended programmatically after write — run persist from inbox NDJSON when present.
INBOX = __file__.replace("apply_batch3_tail.py", "inbox/batch3_remaining.ndjson")

if __name__ == "__main__":
    from pathlib import Path

    inbox = Path(INBOX)
    if inbox.is_file():
        raw = inbox.read_text(encoding="utf-8").strip()
        for line in raw.splitlines():
            if line.strip():
                PAYLOADS.append(json.loads(line))
    for p in PAYLOADS:
        subprocess.run(
            ["python3", "/tmp/mirror_save_payload.py"],
            input=json.dumps(p),
            text=True,
            check=True,
        )
    subprocess.run(["python3", "/workspace/_mirror_refresh_missing.py"], check=True)