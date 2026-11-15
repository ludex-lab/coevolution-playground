"""
Sparse FlyHash + SimHash baselines (minimal port from upstream v1.0).

Upstream: https://github.com/mohanji/flyhash-agent-memory @ ba836793…
MIT — see NOTICE.
"""

from __future__ import annotations

import numpy as np


class FlyHash:
    def __init__(
        self,
        input_dim: int,
        hash_dim: int = 2000,
        sparsity: float = 0.10,
        wta_percent: float = 0.05,
        seed: int = 42,
        weight_mode: str = "signed",
    ):
        self.input_dim = input_dim
        self.hash_dim = hash_dim
        self.sparsity = sparsity
        self.wta_percent = wta_percent
        self.k = max(1, int(round(wta_percent * hash_dim)))
        self.weight_mode = weight_mode

        rng = np.random.default_rng(seed)
        if weight_mode not in ("signed", "binary"):
            raise ValueError(f"Unknown weight_mode: {weight_mode!r}")
        num_connections = max(1, int(round(sparsity * input_dim)))
        self.projection = np.zeros((hash_dim, input_dim), dtype=np.float32)
        for i in range(hash_dim):
            idx = rng.choice(input_dim, size=num_connections, replace=False)
            if weight_mode == "signed":
                weights = rng.choice([-1.0, 1.0], size=num_connections)
            else:
                weights = np.ones(num_connections, dtype=np.float32)
            self.projection[i, idx] = weights

    def hash(self, x: np.ndarray) -> np.ndarray:
        single = x.ndim == 1
        if single:
            x = x[None, :]
        projected = x @ self.projection.T
        codes = np.zeros_like(projected, dtype=np.uint8)
        k = self.k
        top_k_idx = np.argpartition(-projected, kth=k - 1, axis=1)[:, :k]
        rows = np.arange(projected.shape[0])[:, None]
        codes[rows, top_k_idx] = 1
        return codes[0] if single else codes


class SimHash:
    def __init__(self, input_dim: int, hash_dim: int = 64, seed: int = 42):
        self.input_dim = input_dim
        self.hash_dim = hash_dim
        rng = np.random.default_rng(seed)
        self.hyperplanes = rng.normal(size=(hash_dim, input_dim)).astype(np.float32)

    def hash(self, x: np.ndarray) -> np.ndarray:
        single = x.ndim == 1
        if single:
            x = x[None, :]
        projected = x @ self.hyperplanes.T
        codes = (projected > 0).astype(np.uint8)
        return codes[0] if single else codes


def vectorized_hamming_ranking(codes: np.ndarray, queries: np.ndarray) -> np.ndarray:
    """Hamming distance matrix (q, n) via one matmul."""
    codes = codes.astype(np.int16)
    queries = queries.astype(np.int16)
    code_sums = codes.sum(axis=1)
    query_sums = queries.sum(axis=1)
    dots = queries @ codes.T
    return query_sums[:, None] + code_sums[None, :] - 2 * dots
