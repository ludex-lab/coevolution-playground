# Morning Brief 2026-11-06 — FlyHash agent memory (same-day experiment)

**Lab Dig** · **do not merge** without review · CPU-only · one experiment folder only.

Compare **FlyHash vs SimHash vs FAISS HNSW** on **recall@10** under a **matched active-bit budget** (FlyHash k-WTA winners vs SimHash code width), on a **local playground markdown corpus**. Ground truth is **exact cosine** neighbors in a cheap **TF-IDF + TruncatedSVD** embedding space.

| Artifact | Role |
|----------|------|
| [`flyhash.py`](./flyhash.py) | Minimal MIT port of `FlyHash` / `SimHash` + Hamming matmul (upstream v1.0) |
| [`corpus.py`](./corpus.py) | Chunks from markdown at git pin **`887d5ef0d547528568f5b2067cc5ef8c3defe13c`** (PR base; no live `**/README` glob) |
| [`benchmark.py`](./benchmark.py) | Recall table + end-to-end latency subsample sweep |
| [`test_benchmark.py`](./test_benchmark.py) | Fast smoke tests |
| [`NOTICE`](./NOTICE) | Full upstream MIT text + source file attribution |
| [`requirements.txt`](./requirements.txt) | Pinned deps (reproduced on this VM) |

Paper: [arXiv:2611.05791](https://arxiv.org/abs/2611.05791) — FlyHash (sparse random projection + k-winners-take-all) vs SimHash at matched bit budgets; authors stress **quality-per-bit**, not raw speed. **§4.6** reports HNSW beating both hashes on quality and latency at **one** scale (**5,000 GloVe records**); **§6** states corpus scale was **not swept**.

---

## Upstream pin

| Field | Value |
|-------|--------|
| Repository | https://github.com/mohanji/flyhash-agent-memory |
| **Tag** | **`v1.0`** → **`ba836793f40b1ff9ab827395c7d1f55631406d6b`** |
| License | **MIT** © 2026 Mohan Bheemadolu (full text in [`NOTICE`](./NOTICE)) |
| `master` HEAD (unpinned) | `58569f2991fba20e67e9250b4582276b8505af75` (moved past tag) |

**`git ls-remote` (2026-11-06 VM):**

```text
58569f2991fba20e67e9250b4582276b8505af75	HEAD
ba836793f40b1ff9ab827395c7d1f55631406d6b	refs/tags/v1.0
```

Peeled annotated tag `refs/tags/v1.0^{}`: *(empty — lightweight tag; commit resolves directly)*.

Upstream `bash reproduce.sh quick` was smoke-run elsewhere (~4 tests, ~12s OK); this folder does **not** vendor or run the full upstream tree.

---

## Embedding & protocol

- **Corpus:** **420** paragraphs (≥80 chars) from `experiments/**/README.md` and `DESIGN-NOTE.md` **as stored at playground pin `887d5ef…`** (excludes `experiments/2026-11-06/**` and avoids reading this PR’s own README from disk).
- **Embedding:** `TfidfVectorizer` (1–2 grams, `max_features=8000`) → `TruncatedSVD(n_components=64)` → row L2 normalize; **embedding seed=0**.
- **Queries:** **40** indices sampled **from the corpus** (`benchmark.py --seed 1`); **recall@10 includes self-match** when the query chunk is in the index (absolute recall is inflated vs held-out queries).
- **Hashes:** **single** projection seed **42** (not a multi-seed sweep).
- **Matched-bit hash comparison** (per upstream `recall_vs_bits.py`): FlyHash pool `hash_dim=2000`, `wta_percent = k/2000`; SimHash `hash_dim=k`. Rank by **Hamming** via vectorized matmul.
- **Ground truth:** cosine distance `1 − dot(q, doc)` on normalized SVD vectors; **recall@10** = mean overlap with exact top-10.
- **HNSW:** `faiss.IndexHNSWFlat` (`M=32`, `efConstruction=200`, `efSearch=64`) on **full** float vectors — separate **systems** baseline (not matched-bit).

---

## Results (2026-11-06, this VM)

```bash
pip install -r requirements.txt   # numpy==2.5.4, scikit-learn==1.9.1, faiss-cpu==1.15.1
python3 benchmark.py
```

| k (active / code bits) | FlyHash recall@10 | SimHash recall@10 | FlyHash / SimHash |
|------------------------|-------------------|-------------------|-------------------|
| 16 | 0.657 | 0.358 | 1.83× |
| 32 | 0.755 | 0.458 | 1.65× |
| 64 | 0.807 | 0.600 | 1.35× |

**HNSW** recall@10 @ n=420: **0.980** (same query set; full-vector ANN).

**Number change:** Pinning via `git ls-tree` sorts paths differently than the prior filesystem glob, so query seed 1 selects a different 40 chunks; the old chunk order reproduced FlyHash 0.608/0.700/0.778, SimHash 0.375/0.503/0.575, HNSW 0.995.

**End-to-end query latency** (median ms, one query, k=10; timed per repeat):

| n corpus | brute cosine (matmul+top-k) | FlyHash (projection build+hash+Hamming+top-k, k=32) | HNSW (build+add+search) |
|----------|----------------------------|-------------------------------------|-------------------------|
| 50 | 0.003 | 20.226 | 0.323 |
| 100 | 0.004 | 20.488 | 1.224 |
| 200 | 0.005 | 21.243 | 4.521 |
| 400 | 0.007 | 24.931 | 14.435 |
| 420 | 0.007 | 25.176 | 15.638 |

**Scale note:** The paper’s HNSW comparison is a **single** 5k-record snapshot, not a crossover sweep. This corpus (**n=420**) cannot test scale effects; the latency table is **local timing only** (FlyHash re-encodes the corpus each timed repeat).

Full console capture:

```
Corpus: 420 chunks @ git pin 887d5ef0d547 | embed_dim=64 | queries=40
Embedding: TF-IDF (1-2 grams, max_features=8000) + TruncatedSVD, L2-normalized (seed=0)
Query indices: sample from corpus (seed=1); recall@10 includes self-match when query∈corpus
Hash projection seed=42 (single run — not multi-seed sweep)
Ground truth: exact cosine top-10

 k active bits | FlyHash R@10 | SimHash R@10 | fly μ ones | sim code bits
------------------------------------------------------------------------
            16 |        0.657 |        0.358 |       16.0 |             16
            32 |        0.755 |        0.458 |       32.0 |             32
            64 |        0.807 |        0.600 |       64.0 |             64

HNSW (full vectors, efSearch=64) recall@10 @ n=420: 0.980

End-to-end query latency (median ms, one query, k=10; brute=cosine matmul+top-k, FlyHash=hash+Hamming+top-k @ 32 active bits, HNSW=build+add+search per timed repeat):
     n |   brute cosine |    FlyHash e2e |   HNSW e2e | HNSW R@10
--------------------------------------------------------------
    50 |          0.003 |         20.226 |      0.323 |    1.000
   100 |          0.004 |         20.488 |      1.224 |    1.000
   200 |          0.005 |         21.243 |      4.521 |    1.000
   400 |          0.007 |         24.931 |     14.435 |    0.900
   420 |          0.007 |         25.176 |     15.638 |    0.800

Paper §4.6 (arXiv:2611.05791): at a single scale (5,000 GloVe records) HNSW beats both hash methods on quality and latency; authors note corpus scale was not swept. This playground corpus (n=420) cannot test scale effects.
```

---

## Rerun

```bash
cd experiments/2026-11-06/01-flyhash-agent-memory
python3 -m pip install -r requirements.txt
python3 -m unittest test_benchmark.py -v
python3 benchmark.py
```

Requires a git checkout of `playground` (corpus reads blobs via `git show` at pin).

---

## Smoke test output (2026-11-06, post-fold)

```
test_corpus_non_empty ... ok
test_embed_and_recall_bounds ... ok
test_hamming_self_zero ... ok
test_matched_active_bits ... ok
test_recall_at_k_perfect_when_same_ranking ... ok
test_simhash_bit_count ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.127s

OK
```

---

## Done-when

- [x] Upstream **v1.0** pin recorded with `git ls-remote` evidence  
- [x] Corpus pinned to **`887d5ef…`** (stable at PR head)  
- [x] Matched-bit FlyHash vs SimHash recall@10 (k=16, 32, 64)  
- [x] HNSW (faiss-cpu) quality baseline + labeled end-to-end latency table  
- [x] NOTICE (full MIT) + smoke tests with output in this README  
- [x] PR open, **not merged**; no edits to other open PRs (#78–#83)

## Caveats

- Numbers are **only** from the commands above on the pinned corpus — not upstream’s GloVe/MiniLM tables.  
- Queries are **drawn from the corpus** (self-match included).  
- **Single seed** configuration (embedding 0, query sample 1, hash 42).  
- SimHash “bits” are **code width**; FlyHash bits are **count of ones** after k-WTA.  
- **No GPU**, no daemon/HTTP/SQLite/DSH/Feishu; partial code copy only (`flyhash.py`), not full repo vendoring.

## FORBID (honored)

DSH/Feishu/SQLite/daemon/HTTP service · GPU · whole-repo vendoring · merging this PR without review · touching unrelated open PRs.
