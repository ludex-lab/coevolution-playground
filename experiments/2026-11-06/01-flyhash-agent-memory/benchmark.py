"""
Recall@k at matched active-bit budgets: FlyHash vs SimHash vs FAISS HNSW.

Ground truth: exact cosine nearest neighbors on L2-normalized TF-IDF+SVD vectors.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass

import faiss
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from corpus import load_playground_chunks
from flyhash import FlyHash, SimHash, vectorized_hamming_ranking


@dataclass
class BitBudgetResult:
    active_bits: int
    flyhash_recall: float
    simhash_recall: float
    fly_active_mean: float
    sim_active_mean: float


def embed_corpus(texts: list[str], svd_dim: int = 64, seed: int = 0) -> np.ndarray:
    """TF-IDF (word unigrams+bigrams) + TruncatedSVD, row L2-normalized."""
    vec = TfidfVectorizer(max_features=8000, ngram_range=(1, 2), min_df=1)
    tfidf = vec.fit_transform(texts)
    dim = min(svd_dim, tfidf.shape[1] - 1, tfidf.shape[0] - 1)
    dim = max(2, dim)
    svd = TruncatedSVD(n_components=dim, random_state=seed)
    dense = svd.fit_transform(tfidf).astype(np.float32)
    return normalize(dense, norm="l2", axis=1)


def cosine_distance_matrix(queries: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    """Distance = 1 - cosine similarity (queries and corpus already unit norm)."""
    sims = queries @ corpus.T
    return (1.0 - sims).astype(np.float32)


def recall_at_k_from_ranking(pred_dists: np.ndarray, exact_dists: np.ndarray, k: int) -> float:
    pred_topk = np.argsort(pred_dists, axis=1)[:, :k]
    exact_topk = np.argsort(exact_dists, axis=1)[:, :k]
    recalls = []
    for p, e in zip(pred_topk, exact_topk):
        recalls.append(len(set(p.tolist()) & set(e.tolist())) / k)
    return float(np.mean(recalls))


def hnsw_recall_at_k(
    corpus: np.ndarray,
    queries: np.ndarray,
    exact_dists: np.ndarray,
    k: int,
    ef_search: int = 64,
) -> float:
    dim = corpus.shape[1]
    index = faiss.IndexHNSWFlat(dim, 32)
    index.hnsw.efConstruction = 200
    index.hnsw.efSearch = ef_search
    index.add(corpus.astype(np.float32))
    _, indices = index.search(queries.astype(np.float32), k)
    exact_topk = np.argsort(exact_dists, axis=1)[:, :k]
    recalls = []
    for pred, exact in zip(indices, exact_topk):
        valid = [int(i) for i in pred if i >= 0]
        recalls.append(len(set(valid) & set(exact.tolist())) / k)
    return float(np.mean(recalls))


def median_query_ms(fn, n_repeats: int = 30) -> float:
    times = []
    for _ in range(n_repeats):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000.0)
    return float(np.median(times))


def run_bit_budget_benchmark(
    embeddings: np.ndarray,
    query_idx: np.ndarray,
    *,
    k_recall: int = 10,
    bit_budgets: tuple[int, ...] = (16, 32, 64),
    flyhash_pool_size: int = 2000,
    seed: int = 42,
) -> list[BitBudgetResult]:
    queries = embeddings[query_idx]
    exact_dists = cosine_distance_matrix(queries, embeddings)
    actual_dim = embeddings.shape[1]
    out: list[BitBudgetResult] = []

    for bits in bit_budgets:
        wta_percent = bits / flyhash_pool_size
        fly = FlyHash(
            actual_dim,
            hash_dim=flyhash_pool_size,
            sparsity=0.10,
            wta_percent=wta_percent,
            seed=seed,
        )
        fly_codes = fly.hash(embeddings)
        fly_q = fly.hash(queries)
        sim = SimHash(actual_dim, hash_dim=bits, seed=seed)
        sim_codes = sim.hash(embeddings)
        sim_q = sim.hash(queries)

        fly_d = vectorized_hamming_ranking(fly_codes, fly_q)
        sim_d = vectorized_hamming_ranking(sim_codes, sim_q)
        out.append(
            BitBudgetResult(
                active_bits=bits,
                flyhash_recall=recall_at_k_from_ranking(fly_d, exact_dists, k_recall),
                simhash_recall=recall_at_k_from_ranking(sim_d, exact_dists, k_recall),
                fly_active_mean=float(fly_codes.sum(axis=1).mean()),
                sim_active_mean=float(sim_codes.sum(axis=1).mean()),
            )
        )
    return out


def run_latency_e2e(
    embeddings: np.ndarray,
    query_idx: np.ndarray,
    sizes: tuple[int, ...],
    *,
    k_search: int = 10,
    active_bits: int = 32,
    flyhash_pool_size: int = 2000,
    seed: int = 42,
) -> list[dict]:
    """
    Median end-to-end single-query latency (ms): encode/rank + top-k for each method.
    HNSW times build+add+search per repeat (no prebuilt index reuse).
    """
    q = embeddings[query_idx[0:1]]
    qf = q.astype(np.float32)
    dim = embeddings.shape[1]
    rows = []
    for n in sizes:
        if n > embeddings.shape[0]:
            continue
        sub = embeddings[:n]
        exact_d = cosine_distance_matrix(q, sub)

        def brute_e2e():
            dist = cosine_distance_matrix(q, sub)
            _ = np.argsort(dist, axis=1)[:, :k_search]

        wta_percent = active_bits / flyhash_pool_size

        def flyhash_e2e():
            fly = FlyHash(
                dim,
                hash_dim=flyhash_pool_size,
                sparsity=0.10,
                wta_percent=wta_percent,
                seed=seed,
            )
            codes = fly.hash(sub)
            qcode = fly.hash(q)
            ham = vectorized_hamming_ranking(codes, qcode)
            _ = np.argsort(ham, axis=1)[:, :k_search]

        def hnsw_e2e():
            index = faiss.IndexHNSWFlat(dim, 32)
            index.hnsw.efConstruction = 200
            index.hnsw.efSearch = 64
            index.add(sub.astype(np.float32))
            index.search(qf, k_search)

        rows.append(
            {
                "n_corpus": n,
                "brute_ms": median_query_ms(brute_e2e, n_repeats=25),
                "flyhash_ms": median_query_ms(flyhash_e2e, n_repeats=25),
                "hnsw_ms": median_query_ms(hnsw_e2e, n_repeats=25),
                "hnsw_recall10": hnsw_recall_at_k(sub, q, exact_d, k_search),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k-recall", type=int, default=10)
    parser.add_argument("--n-queries", type=int, default=40)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    _, texts = load_playground_chunks()
    embeddings = embed_corpus(texts, svd_dim=64, seed=0)
    n = embeddings.shape[0]
    rng = np.random.default_rng(args.seed)
    n_q = min(args.n_queries, n)
    query_idx = rng.choice(n, size=n_q, replace=False)

    from corpus import CORPUS_PIN_REV

    print(f"Corpus: {n} chunks @ git pin {CORPUS_PIN_REV[:12]} | embed_dim={embeddings.shape[1]} | queries={n_q}")
    print(f"Embedding: TF-IDF (1-2 grams, max_features=8000) + TruncatedSVD, L2-normalized (seed=0)")
    print(f"Query indices: sample from corpus (seed={args.seed}); recall@10 includes self-match when query∈corpus")
    print(f"Hash projection seed=42 (single run — not multi-seed sweep)")
    print(f"Ground truth: exact cosine top-{args.k_recall}\n")

    budgets = (16, 32, 64)
    results = run_bit_budget_benchmark(
        embeddings,
        query_idx,
        k_recall=args.k_recall,
        bit_budgets=budgets,
    )

    hnsw_r = hnsw_recall_at_k(
        embeddings,
        embeddings[query_idx],
        cosine_distance_matrix(embeddings[query_idx], embeddings),
        args.k_recall,
    )

    print(f"{'k active bits':>14} | {'FlyHash R@'+str(args.k_recall):>12} | "
          f"{'SimHash R@'+str(args.k_recall):>12} | fly μ ones | sim code bits")
    print("-" * 72)
    for r in results:
        print(
            f"{r.active_bits:>14} | {r.flyhash_recall:>12.3f} | {r.simhash_recall:>12.3f} | "
            f"{r.fly_active_mean:>10.1f} | {r.active_bits:>14}"
        )
    print(f"\nHNSW (full vectors, efSearch=64) recall@{args.k_recall} @ n={n}: {hnsw_r:.3f}")

    sizes = (50, 100, 200, 400, n)
    sizes = tuple(sorted(set(s for s in sizes if s <= n)))
    print(
        "\nEnd-to-end query latency (median ms, one query, k=10; "
        "brute=cosine matmul+top-k, FlyHash=hash+Hamming+top-k @ 32 active bits, "
        "HNSW=build+add+search per timed repeat):"
    )
    print(f"{'n':>6} | {'brute cosine':>14} | {'FlyHash e2e':>14} | {'HNSW e2e':>10} | HNSW R@10")
    print("-" * 62)
    for row in run_latency_e2e(embeddings, query_idx, sizes, active_bits=32):
        print(
            f"{row['n_corpus']:>6} | {row['brute_ms']:>14.3f} | "
            f"{row['flyhash_ms']:>14.3f} | {row['hnsw_ms']:>10.3f} | "
            f"{row['hnsw_recall10']:>8.3f}"
        )
    print(
        "\nPaper §4.6 (arXiv:2611.05791): at a single scale (5,000 GloVe records) HNSW beats "
        "both hash methods on quality and latency; authors note corpus scale was not swept. "
        f"This playground corpus (n={n}) cannot test scale effects."
    )


if __name__ == "__main__":
    main()
