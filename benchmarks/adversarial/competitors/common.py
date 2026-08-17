"""Shared machinery for the competitor benchmark runners.

Fairness contract (identical for every framework):
  * embeddings   = BAAI/bge-m3 via each framework's own HuggingFace /
                   sentence-transformers integration
  * retrieval    = each framework returns its top RETRIEVE_K (16) chunks
  * reranking    = applied HERE, outside the framework, identically for all:
                   sentence_transformers.CrossEncoder("BAAI/bge-reranker-v2-m3")
                   over the 16 candidates, keep the top FINAL_K (5)
  * queries      = verbatim from the questions JSON, zero-shot
  * output       = {"Q01": ["passage 1", ..., "passage 5"], ...}  (score.py format)

IMPORT THIS MODULE FIRST in every runner: it sets the corporate-TLS cert
env vars before requests/huggingface_hub are imported anywhere.
"""

from __future__ import annotations

import json
import os
import time

_CERT = "/opt/homebrew/etc/openssl@3/cert.pem"
os.environ.setdefault("SSL_CERT_FILE", _CERT)
os.environ.setdefault("REQUESTS_CA_BUNDLE", _CERT)
# Keep HF tokenizers quiet and deterministic in forked dataloaders.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

EMBED_MODEL = "BAAI/bge-m3"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
RETRIEVE_K = 16
FINAL_K = 5


def load_questions(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["questions"]


def get_reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(RERANK_MODEL)


def rerank(reranker, query: str, passages: list[str], top_k: int = FINAL_K) -> list[str]:
    """Score (query, passage) pairs with the shared cross-encoder, keep top_k."""
    if not passages:
        return []
    scores = reranker.predict([(query, p) for p in passages])
    order = sorted(range(len(passages)), key=lambda i: -float(scores[i]))
    return [passages[i] for i in order[:top_k]]


def write_results(out_path: str, results: dict[str, list[str]]) -> None:
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print(f"[runner] wrote {out_path}", flush=True)


def write_meta(out_path: str, meta: dict) -> None:
    meta_path = out_path + ".meta.json"
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    print(f"[runner] wrote {meta_path}", flush=True)


def run_queries(questions: list[dict], retrieve_fn, reranker) -> tuple[dict, dict, list[str]]:
    """retrieve_fn(query) -> list[str] of up to RETRIEVE_K passage texts.

    Returns (results, timing, errors). A query that raises records an empty
    passage list (scores as FAIL) and the verbatim error string.
    """
    results: dict[str, list[str]] = {}
    errors: list[str] = []
    t_retrieve = 0.0
    t_rerank = 0.0
    for question in questions:
        qid, query = question["id"], question["query"]
        try:
            t0 = time.time()
            candidates = retrieve_fn(query)[:RETRIEVE_K]
            t_retrieve += time.time() - t0
            t0 = time.time()
            results[qid] = rerank(reranker, query, candidates)
            t_rerank += time.time() - t0
            print(f"[runner] {qid}: {len(results[qid])} passages — {query[:60]}",
                  flush=True)
        except Exception as exc:  # a crash on one query is itself a result
            results[qid] = []
            msg = f"{qid}: {type(exc).__name__}: {exc}"
            errors.append(msg)
            print(f"[runner] {msg}", flush=True)
    timing = {"query_retrieve_s": round(t_retrieve, 2),
              "query_rerank_s": round(t_rerank, 2),
              "query_total_s": round(t_retrieve + t_rerank, 2)}
    return results, timing, errors
