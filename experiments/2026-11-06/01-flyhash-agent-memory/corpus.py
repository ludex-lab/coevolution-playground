"""Local playground markdown corpus pinned to a fixed git snapshot (no live glob drift)."""

from __future__ import annotations

import subprocess
from pathlib import Path

# Playground `main` at PR base (2026-11-06 Morning Brief); corpus excludes this PR's tree.
CORPUS_PIN_REV = "887d5ef0d547528568f5b2067cc5ef8c3defe13c"


def _git(repo: Path, *args: str) -> str:
    out = subprocess.check_output(["git", "-C", str(repo), *args], text=True)
    return out


def list_corpus_paths_at_pin(playground_root: Path) -> list[str]:
    """Relative paths under experiments/ for README.md and DESIGN-NOTE.md at CORPUS_PIN_REV."""
    listing = _git(
        playground_root,
        "ls-tree",
        "-r",
        "--name-only",
        CORPUS_PIN_REV,
        "experiments/",
    )
    paths: list[str] = []
    for line in listing.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.endswith("/README.md") or line.endswith("/DESIGN-NOTE.md"):
            if line.startswith("experiments/2026-11-06/"):
                continue
            paths.append(line)
    return sorted(paths)


def read_file_at_pin(playground_root: Path, rel_path: str) -> str:
    return _git(playground_root, "show", f"{CORPUS_PIN_REV}:{rel_path}")


def load_playground_chunks(
    playground_root: Path | None = None,
    min_chars: int = 80,
) -> tuple[list[str], list[str]]:
    """
    Returns (doc_ids, text_chunks) from markdown at CORPUS_PIN_REV (stable at PR head).
    """
    root = playground_root or Path(__file__).resolve().parents[3]
    paths = list_corpus_paths_at_pin(root)
    doc_ids: list[str] = []
    texts: list[str] = []
    for rel in paths:
        raw = read_file_at_pin(root, rel)
        for i, para in enumerate(raw.split("\n\n")):
            para = para.strip()
            if len(para) >= min_chars:
                doc_ids.append(f"{rel}#p{i}")
                texts.append(para)
    if not texts:
        raise RuntimeError(
            f"No corpus chunks at pin {CORPUS_PIN_REV} under {root / 'experiments'}"
        )
    return doc_ids, texts
