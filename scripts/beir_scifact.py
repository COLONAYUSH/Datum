"""BEIR SciFact benchmark harness for Datum.

Runs the ENTIRE benchmark through the real system, exactly as decisions.md #42
describes: every document through the full write path (WAL, CAS, chunking,
both views), every query through the real compiled plan (namespace ACL, fused
operators, reranker, audit trace). One disclosed setting change: the
evidence-sufficiency threshold is set to zero, because BEIR measures ranking
and has no way to score correct refusal.

This file replaces the original scratchpad harness that produced the paper's
0.697 (nDCG@10) and was later lost to temp cleanup. It lives in the repo so
the paper's headline number stays reproducible. The dataset downloads itself
from the official BEIR mirror on first run (about 3 MB).

Usage (ALWAYS a scratch database -- ingest writes real records):

    createdb datum_scifact
    python scripts/beir_scifact.py --dsn postgresql://localhost/datum_scifact

    # variant runs, e.g. the English-specialist embedder:
    createdb datum_scifact_large
    python scripts/beir_scifact.py --dsn postgresql://localhost/datum_scifact_large \
        --embedder bge-large

Use one fresh database per embedder config: the dense view's vector dimension
is embedder-dependent DDL, and mixing dims in one database is refused by
design (a lineage bug, not a config option).
"""

from __future__ import annotations

import argparse
import io
import json
import math
import time
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

BEIR_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
DEFAULT_DATA_DIR = Path.home() / ".cache" / "datum-bench"
NAMESPACE = "tenant:scifact"
K = 10


def download_scifact(data_dir: Path) -> Path:
    root = data_dir / "scifact"
    if (root / "corpus.jsonl").exists() and (root / "qrels" / "test.tsv").exists():
        print(f"dataset already present at {root}")
        return root
    data_dir.mkdir(parents=True, exist_ok=True)
    print(f"downloading SciFact from {BEIR_URL} ...")
    with urllib.request.urlopen(BEIR_URL, timeout=120) as resp:
        payload = resp.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        zf.extractall(data_dir)
    if not (root / "corpus.jsonl").exists():
        raise SystemExit(f"download extracted, but {root}/corpus.jsonl is missing")
    print(f"dataset ready at {root}")
    return root


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_qrels(path: Path) -> dict[str, dict[str, int]]:
    qrels: dict[str, dict[str, int]] = defaultdict(dict)
    with open(path, encoding="utf-8") as f:
        next(f)  # header: query-id \t corpus-id \t score
        for line in f:
            qid, did, score = line.strip().split("\t")
            qrels[qid][did] = int(score)
    return dict(qrels)


def build_embedder(choice: str, device: str):
    """None means the package default (bge-m3, the config behind the paper's
    0.697). Named choices cover the documented variants; anything else is
    treated as a HuggingFace model name and needs --dim.
    """
    if choice in ("default", "bge-m3"):
        return None
    from datum.derivation.views.dense import (
        _BGE_V15_QUERY_PREFIX,
        SentenceTransformersEmbedder,
        bge_small_en,
    )

    if choice == "bge-small":
        return bge_small_en()
    if choice == "bge-large":
        return SentenceTransformersEmbedder(
            "BAAI/bge-large-en-v1.5",
            dim=1024,
            query_prefix=_BGE_V15_QUERY_PREFIX,
            device=device,
        )
    raise SystemExit(
        f"unknown embedder {choice!r}: use default | bge-small | bge-large, "
        "or extend build_embedder() for a new model (set dim and query_prefix "
        "to the model's documented values)."
    )


def ndcg_at_k(ranked: list[str], rels: dict[str, int], k: int) -> float:
    dcg = sum(
        rels.get(doc, 0) / math.log2(i + 2) for i, doc in enumerate(ranked[:k])
    )
    ideal = sorted(rels.values(), reverse=True)[:k]
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", default="postgresql://localhost/datum_scifact")
    ap.add_argument("--embedder", default="default")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--skip-ingest", action="store_true",
                    help="database already holds the corpus; just run queries")
    ap.add_argument("--queries-limit", type=int, default=None,
                    help="smoke-test on the first N test queries")
    args = ap.parse_args()

    if args.dsn.rstrip("/").endswith("/datum"):
        raise SystemExit(
            "refusing to run against the default 'datum' database: ingest "
            "writes real records. Create a scratch db (createdb datum_scifact)."
        )

    from datum import Corpus
    from datum.kernel.principal import Principal

    root = download_scifact(args.data_dir)
    corpus_docs = load_jsonl(root / "corpus.jsonl")
    queries = {q["_id"]: q["text"] for q in load_jsonl(root / "queries.jsonl")}
    qrels = load_qrels(root / "qrels" / "test.tsv")
    test_qids = list(qrels)
    if args.queries_limit:
        test_qids = test_qids[: args.queries_limit]
    print(f"{len(corpus_docs)} documents, {len(test_qids)} test queries")

    principal = Principal(id="bench", namespace=NAMESPACE)
    corpus = Corpus.open(
        args.dsn,
        hit_signing_key=b"beir-bench",
        embedder=build_embedder(args.embedder, args.device),
        abstain_min_similarity=0.0,  # disclosed: BEIR cannot score refusal
    )
    try:
        if not args.skip_ingest:
            t0 = time.time()
            for i, doc in enumerate(corpus_docs, 1):
                title = (doc.get("title") or "").strip()
                body = (doc.get("text") or "").strip()
                text = f"# {title}\n\n{body}\n" if title else body + "\n"
                corpus.ingest(doc["_id"], text, principal=principal)
                if i % 250 == 0:
                    rate = i / (time.time() - t0)
                    eta = (len(corpus_docs) - i) / rate / 60
                    print(f"  ingested {i}/{len(corpus_docs)} "
                          f"({rate:.1f} docs/s, ~{eta:.0f} min left)", flush=True)
            print(f"ingest done in {(time.time() - t0) / 60:.1f} min")

        t0 = time.time()
        ndcgs: list[float] = []
        hits_any = 0
        for n, qid in enumerate(test_qids, 1):
            evidence = corpus.search(queries[qid], principal=principal)
            ranked_docs: list[str] = []
            for hit in evidence.hits:
                doc_id = hit.source_path
                if doc_id and doc_id not in ranked_docs:
                    ranked_docs.append(doc_id)
            ndcgs.append(ndcg_at_k(ranked_docs, qrels[qid], K))
            if any(d in qrels[qid] and qrels[qid][d] > 0 for d in ranked_docs[:K]):
                hits_any += 1
            if n % 25 == 0:
                print(f"  {n}/{len(test_qids)} queries, "
                      f"running nDCG@{K}={sum(ndcgs)/len(ndcgs):.4f}", flush=True)
        elapsed = time.time() - t0

        result = {
            "task": "BEIR SciFact",
            "embedder": args.embedder,
            "queries": len(test_qids),
            f"ndcg@{K}": round(sum(ndcgs) / len(ndcgs), 4),
            f"recall_any@{K}": round(hits_any / len(test_qids), 4),
            "sec_per_query": round(elapsed / len(test_qids), 2),
        }
        print(json.dumps(result, indent=2))
        out = Path(f"scifact-result-{args.embedder}.json")
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"result written to {out.resolve()}")
    finally:
        corpus.close()


if __name__ == "__main__":
    main()
