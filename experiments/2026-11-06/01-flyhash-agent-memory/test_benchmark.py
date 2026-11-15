"""Fast smoke tests for flyhash playground benchmark."""

from __future__ import annotations

import unittest

import numpy as np

from benchmark import embed_corpus, recall_at_k_from_ranking, run_bit_budget_benchmark
from corpus import load_playground_chunks
from flyhash import FlyHash, SimHash, vectorized_hamming_ranking


class FlyHashSmokeTests(unittest.TestCase):
    def test_matched_active_bits(self):
        dim = 16
        x = np.random.default_rng(0).normal(size=(5, dim)).astype(np.float32)
        pool = 200
        bits = 8
        fly = FlyHash(dim, hash_dim=pool, wta_percent=bits / pool, seed=0)
        codes = fly.hash(x)
        self.assertEqual(codes.shape, (5, pool))
        self.assertTrue(np.all(codes.sum(axis=1) == bits))

    def test_simhash_bit_count(self):
        dim = 12
        x = np.random.default_rng(1).normal(size=(3, dim)).astype(np.float32)
        sim = SimHash(dim, hash_dim=16, seed=0)
        codes = sim.hash(x)
        self.assertEqual(codes.shape, (3, 16))
        # SimHash uses all hash_dim sign bits in Hamming distance (not k-sparse like FlyHash).
        self.assertTrue(np.all((codes == 0) | (codes == 1)))

    def test_hamming_self_zero(self):
        codes = np.array([[1, 0, 1], [0, 1, 0]], dtype=np.uint8)
        d = vectorized_hamming_ranking(codes, codes[:1])
        self.assertEqual(int(d[0, 0]), 0)

    def test_corpus_non_empty(self):
        ids, texts = load_playground_chunks()
        self.assertGreater(len(texts), 50)
        self.assertEqual(len(ids), len(texts))

    def test_embed_and_recall_bounds(self):
        _, texts = load_playground_chunks()
        emb = embed_corpus(texts[:80], svd_dim=32, seed=0)
        idx = np.array([0, 1, 2])
        res = run_bit_budget_benchmark(
            emb, idx, k_recall=5, bit_budgets=(16, 32), flyhash_pool_size=500
        )
        for r in res:
            self.assertGreaterEqual(r.flyhash_recall, 0.0)
            self.assertLessEqual(r.flyhash_recall, 1.0)
            self.assertGreaterEqual(r.simhash_recall, 0.0)
            self.assertLessEqual(r.simhash_recall, 1.0)

    def test_recall_at_k_perfect_when_same_ranking(self):
        dist = np.array([[0.0, 1.0, 2.0], [2.0, 0.0, 1.0]], dtype=np.float32)
        r = recall_at_k_from_ranking(dist, dist, k=2)
        self.assertAlmostEqual(r, 1.0)


if __name__ == "__main__":
    unittest.main()
