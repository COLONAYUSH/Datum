#!/usr/bin/env python3
"""Haystack (3.x) runner for the adversarial retrieval benchmark.

Documented standard PDF pipeline (Haystack docs' indexing tutorial):
    PyPDFToDocument -> DocumentCleaner -> DocumentSplitter (defaults:
    split_by=word, split_length=200, split_overlap=0)
    -> embeddings on Document.embedding -> InMemoryDocumentStore,
    queried with InMemoryEmbeddingRetriever(top_k=16).

EMBEDDER NOTE (disclosed workaround): haystack-ai 3.0.0 removed
SentenceTransformersDocumentEmbedder / SentenceTransformersTextEmbedder from
core (they moved to the separate `sentence-transformers-haystack` integration
package, which is NOT installed in this venv and could not be added — pip was
permission-blocked). Embeddings here are therefore computed directly with
sentence_transformers.SentenceTransformer("BAAI/bge-m3").encode(...) and
attached to the Haystack Documents — mechanically identical to what
Haystack's own wrapper does (it calls the same encode on doc.content with
batch_size=32 and no normalization flag). Conversion, cleaning, splitting,
storage and retrieval are pure Haystack.

Reranking (top16 -> cross-encoder -> top5) happens OUTSIDE the framework in
common.py, identically for every system in the benchmark.

Usage:
    python run_haystack.py --pdf ../document-a.pdf \
        --questions ../questions-a.json --out haystack-results-a.json
"""

from __future__ import annotations

import argparse
import sys
import time

import common  # sets SSL cert env vars — must be first project import


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--questions", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    from haystack.components.converters import PyPDFToDocument
    from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
    from haystack.components.retrievers.in_memory import InMemoryEmbeddingRetriever
    from haystack.document_stores.in_memory import InMemoryDocumentStore
    from sentence_transformers import SentenceTransformer

    questions = common.load_questions(args.questions)

    print(f"[haystack] loading {args.pdf}", flush=True)
    t0 = time.time()
    docs = PyPDFToDocument().run(sources=[args.pdf])["documents"]
    docs = DocumentCleaner().run(documents=docs)["documents"]
    splitter = DocumentSplitter()  # library defaults
    splitter.warm_up()
    chunks = splitter.run(documents=docs)["documents"]
    load_s = time.time() - t0
    print(f"[haystack] {len(docs)} documents -> {len(chunks)} chunks "
          f"in {load_s:.1f}s", flush=True)

    t0 = time.time()
    # Direct sentence-transformers embedding (see EMBEDDER NOTE above):
    # same call Haystack's SentenceTransformersDocumentEmbedder makes.
    st_model = SentenceTransformer(common.EMBED_MODEL)
    texts = [c.content or "" for c in chunks]
    embeddings = st_model.encode(texts, batch_size=32, show_progress_bar=False)
    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb.tolist()
    store = InMemoryDocumentStore()  # default similarity: dot_product
    store.write_documents(chunks)
    embed_s = time.time() - t0
    ingest_s = load_s + embed_s
    print(f"[haystack] store populated in {embed_s:.1f}s "
          f"(total ingest {ingest_s:.1f}s)", flush=True)

    retriever_component = InMemoryEmbeddingRetriever(
        document_store=store, top_k=common.RETRIEVE_K)
    reranker = common.get_reranker()

    def retrieve(query: str) -> list[str]:
        embedding = st_model.encode(query).tolist()
        hits = retriever_component.run(query_embedding=embedding)["documents"]
        return [d.content for d in hits]

    results, timing, errors = common.run_queries(questions, retrieve, reranker)

    common.write_results(args.out, results)
    common.write_meta(args.out, {
        "framework": "haystack",
        "pipeline": "PyPDFToDocument + DocumentCleaner + DocumentSplitter "
                    "(defaults) + InMemoryDocumentStore embedding retriever",
        "embedder_note": "haystack-ai 3.0.0 core has no local embedder "
                         "(SentenceTransformers embedders moved to the "
                         "uninstalled sentence-transformers-haystack package; "
                         "pip permission-blocked). Embeddings computed "
                         "directly with sentence_transformers encode() — "
                         "identical to Haystack's own wrapper — and attached "
                         "to Haystack Documents.",
        "embed_model": common.EMBED_MODEL,
        "rerank_model": common.RERANK_MODEL,
        "retrieve_k": common.RETRIEVE_K,
        "final_k": common.FINAL_K,
        "n_documents": len(docs),
        "n_chunks": len(chunks),
        "ingest_load_s": round(load_s, 2),
        "ingest_embed_s": round(embed_s, 2),
        "ingest_total_s": round(ingest_s, 2),
        **timing,
        "errors": errors,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
