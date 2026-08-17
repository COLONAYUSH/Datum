#!/usr/bin/env python3
"""LlamaIndex runner for the adversarial retrieval benchmark.

Documented standard PDF pipeline (LlamaIndex starter-tutorial defaults):
    SimpleDirectoryReader -> default node parser (SentenceSplitter,
    chunk_size=1024, chunk_overlap=200) -> VectorStoreIndex (in-memory)
    -> retriever with similarity_top_k=16,
    embeddings = HuggingFaceEmbedding("BAAI/bge-m3").

PDF READER NOTE (disclosed workaround): the venv's `llama-index` install did
NOT bring in `llama-index-readers-file` (pip could not add it afterwards —
permission-blocked), and without it SimpleDirectoryReader SILENTLY falls back
to reading the PDF as plain text: document-b.pdf came back as one Document of
raw PDF bytes ("%PDF-1.4\\n1 0 obj..."), and on document-a.pdf the default
SentenceSplitter/nltk-punkt died with RecursionError over those raw bytes
(verbatim log: llamaindex-a-defaultcrash.log). This runner therefore passes
SimpleDirectoryReader the documented `file_extractor` hook with a reader that
reproduces the official llama_index.readers.file.PDFReader behaviour exactly:
pypdf.PdfReader, page.extract_text(), one Document per page.

Reranking (top16 -> cross-encoder -> top5) happens OUTSIDE the framework in
common.py, identically for every system in the benchmark.

Usage:
    python run_llamaindex.py --pdf ../document-a.pdf \
        --questions ../questions-a.json --out llamaindex-results-a.json
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
    parser.add_argument("--recursion-limit", type=int, default=0,
                        help="if >0, call sys.setrecursionlimit(N) before "
                             "ingest (kept from the raw-bytes fallback "
                             "investigation; unused by default)")
    args = parser.parse_args()
    if args.recursion_limit > 0:
        sys.setrecursionlimit(args.recursion_limit)

    from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex
    from llama_index.core.readers.base import BaseReader
    from llama_index.core.schema import Document
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    class PyPDFPageReader(BaseReader):
        """Mirror of llama_index.readers.file.PDFReader (see module docstring):
        pypdf, page.extract_text(), one Document per page."""

        def load_data(self, file, extra_info=None):
            import pypdf
            reader = pypdf.PdfReader(str(file))
            docs = []
            for i, page in enumerate(reader.pages):
                metadata = {"page_label": str(i + 1), "file_name": str(file)}
                if extra_info:
                    metadata.update(extra_info)
                docs.append(Document(text=page.extract_text() or "",
                                     metadata=metadata))
            return docs

    Settings.embed_model = HuggingFaceEmbedding(model_name=common.EMBED_MODEL)
    Settings.llm = None  # retrieval only — no LLM anywhere in this benchmark

    questions = common.load_questions(args.questions)

    print(f"[llamaindex] loading {args.pdf}", flush=True)
    t0 = time.time()
    docs = SimpleDirectoryReader(
        input_files=[args.pdf],
        file_extractor={".pdf": PyPDFPageReader()},
    ).load_data()
    load_s = time.time() - t0
    print(f"[llamaindex] loaded {len(docs)} documents in {load_s:.1f}s", flush=True)

    t0 = time.time()
    index = VectorStoreIndex.from_documents(docs)  # default SentenceSplitter
    embed_s = time.time() - t0
    ingest_s = load_s + embed_s
    print(f"[llamaindex] index built in {embed_s:.1f}s "
          f"(total ingest {ingest_s:.1f}s)", flush=True)

    retriever = index.as_retriever(similarity_top_k=common.RETRIEVE_K)
    reranker = common.get_reranker()

    def retrieve(query: str) -> list[str]:
        nodes = retriever.retrieve(query)
        return [n.node.get_content() for n in nodes]

    results, timing, errors = common.run_queries(questions, retrieve, reranker)

    common.write_results(args.out, results)
    common.write_meta(args.out, {
        "framework": "llamaindex",
        "pipeline": "SimpleDirectoryReader + default SentenceSplitter "
                    "+ VectorStoreIndex (in-memory)",
        "reader_note": "llama-index-readers-file missing from the venv "
                       "(llama-index 0.14.23 meta-package did not install it; "
                       "pip permission-blocked). Without it "
                       "SimpleDirectoryReader silently reads PDFs as plain "
                       "text (raw %PDF bytes) — doc A then crashed nltk punkt "
                       "with RecursionError (llamaindex-a-defaultcrash.log). "
                       "Used the documented file_extractor hook with a "
                       "pypdf-per-page reader identical to the official "
                       "PDFReader.",
        "embed_model": common.EMBED_MODEL,
        "rerank_model": common.RERANK_MODEL,
        "retrieve_k": common.RETRIEVE_K,
        "final_k": common.FINAL_K,
        "n_documents": len(docs),
        "ingest_load_s": round(load_s, 2),
        "ingest_embed_s": round(embed_s, 2),
        "ingest_total_s": round(ingest_s, 2),
        **timing,
        "errors": errors,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
