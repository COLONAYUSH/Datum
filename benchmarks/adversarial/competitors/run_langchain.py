#!/usr/bin/env python3
"""LangChain runner for the adversarial retrieval benchmark.

Documented standard PDF pipeline (LangChain docs' RAG tutorial defaults):
    PyPDFLoader -> RecursiveCharacterTextSplitter(chunk_size=1000,
    chunk_overlap=200) -> FAISS vector store -> similarity search (k=16),
    embeddings = HuggingFaceEmbeddings("BAAI/bge-m3").

Optional best-effort config: --loader unstructured-hires swaps the loader for
UnstructuredPDFLoader(strategy="hi_res") (OCR-capable), everything else equal.

Reranking (top16 -> cross-encoder -> top5) happens OUTSIDE the framework in
common.py, identically for every system in the benchmark.

Usage:
    python run_langchain.py --pdf ../document-a.pdf \
        --questions ../questions-a.json --out langchain-results-a.json \
        [--loader pypdf|unstructured-hires]
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
    parser.add_argument("--loader", choices=["pypdf", "unstructured-hires"],
                        default="pypdf")
    args = parser.parse_args()

    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    questions = common.load_questions(args.questions)

    print(f"[langchain] loading {args.pdf} with {args.loader}", flush=True)
    t0 = time.time()
    if args.loader == "pypdf":
        from langchain_community.document_loaders import PyPDFLoader
        docs = PyPDFLoader(args.pdf).load()
    else:
        from langchain_community.document_loaders import UnstructuredPDFLoader
        docs = UnstructuredPDFLoader(args.pdf, mode="single",
                                     strategy="hi_res").load()
    load_s = time.time() - t0
    print(f"[langchain] loaded {len(docs)} documents in {load_s:.1f}s", flush=True)

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)
    print(f"[langchain] {len(chunks)} chunks", flush=True)

    t0 = time.time()
    embeddings = HuggingFaceEmbeddings(model_name=common.EMBED_MODEL)
    store = FAISS.from_documents(chunks, embeddings)
    embed_s = time.time() - t0
    ingest_s = load_s + embed_s
    print(f"[langchain] FAISS index built in {embed_s:.1f}s "
          f"(total ingest {ingest_s:.1f}s)", flush=True)

    reranker = common.get_reranker()

    def retrieve(query: str) -> list[str]:
        hits = store.similarity_search(query, k=common.RETRIEVE_K)
        return [d.page_content for d in hits]

    results, timing, errors = common.run_queries(questions, retrieve, reranker)

    common.write_results(args.out, results)
    common.write_meta(args.out, {
        "framework": "langchain",
        "loader": args.loader,
        "pipeline": ("PyPDFLoader" if args.loader == "pypdf"
                     else "UnstructuredPDFLoader(strategy=hi_res, mode=single)")
                    + " + RecursiveCharacterTextSplitter(1000/200) + FAISS",
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
