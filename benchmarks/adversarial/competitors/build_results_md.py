#!/usr/bin/env python3
"""Build RESULTS.md for the competitor benchmark.

Runs ../score.py (unmodified) over every results JSON present, collects
per-question PASS/FAIL and totals, pulls timings from the runners'
*.meta.json sidecars and package versions from pip freeze, and writes
RESULTS.md next to this script.

Usage:  .venv/bin/python build_results_md.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADV = HERE.parent
PY = sys.executable

# (label, results-file template relative to HERE)
SYSTEMS = [
    ("Datum", str(ADV / "datum-results-{d}.json")),
    ("LangChain", str(HERE / "langchain-results-{d}.json")),
    ("LlamaIndex", str(HERE / "llamaindex-results-{d}.json")),
    ("Haystack", str(HERE / "haystack-results-{d}.json")),
    ("LangChain-OCR", str(HERE / "langchain-ocr-results-{d}.json")),
]
DOCS = ["a", "b"]

_LINE = re.compile(r"^(Q\d+)\s+(\S+)\s+(PASS|FAIL)\s+(.*)$")
_TOTAL = re.compile(r"^TOTAL: (\d+)/(\d+)$")

RELEVANT_PKGS = re.compile(
    r"^(langchain|langchain-core|langchain-community|langchain-huggingface|"
    r"langchain-text-splitters|llama-index|llama-index-core|"
    r"llama-index-embeddings-huggingface|haystack-ai|pypdf|unstructured|"
    r"unstructured-inference|sentence-transformers|faiss-cpu|torch|"
    r"transformers|pdfminer\.six|pi-heif|pytesseract|pdf2image)==", re.I)


def score(doc: str, results_path: str):
    """Returns (per_q: {qid: 'PASS'/'FAIL'}, total: 'n/m') or None if absent."""
    if not Path(results_path).is_file():
        return None
    proc = subprocess.run(
        [PY, str(ADV / "score.py"), str(ADV / f"questions-{doc}.json"), results_path],
        capture_output=True, text=True, check=True)
    per_q, total = {}, "?"
    for line in proc.stdout.splitlines():
        m = _LINE.match(line)
        if m:
            per_q[m.group(1)] = m.group(3)
        m = _TOTAL.match(line)
        if m:
            total = f"{m.group(1)}/{m.group(2)}"
    return per_q, total


def meta_for(results_path: str) -> dict:
    p = Path(results_path + ".meta.json")
    if p.is_file():
        return json.loads(p.read_text())
    return {}


def main() -> int:
    lines: list[str] = []
    lines.append("# Adversarial retrieval benchmark — competitor results\n")
    lines.append("Scored by `benchmarks/adversarial/score.py` (unmodified), "
                 "mechanical top-5 rule. All systems: BAAI/bge-m3 embeddings, "
                 "framework retrieves top 16, shared external "
                 "CrossEncoder(BAAI/bge-reranker-v2-m3) reranks to top 5. "
                 "Queries verbatim, zero-shot.\n")

    scored: dict[str, dict[str, tuple[dict, str]]] = {d: {} for d in DOCS}
    for doc in DOCS:
        for label, tpl in SYSTEMS:
            res = score(doc, tpl.format(d=doc))
            if res is not None:
                scored[doc][label] = res

    # Totals table
    lines.append("## Totals (questions passed)\n")
    labels = [l for l, _ in SYSTEMS]
    lines.append("| System | Document A (42 q) | Document B (44 q) |")
    lines.append("|---|---|---|")
    for label in labels:
        row_a = scored["a"].get(label)
        row_b = scored["b"].get(label)
        if row_a is None and row_b is None:
            continue
        lines.append(f"| {label} | {row_a[1] if row_a else 'not run'} "
                     f"| {row_b[1] if row_b else 'not run'} |")
    lines.append("")

    # Per-question grids
    for doc in DOCS:
        lines.append(f"## Per-question grid — document {doc.upper()}\n")
        present = [l for l in labels if l in scored[doc]]
        qids = sorted(next(iter(scored[doc].values()))[0]) if scored[doc] else []
        lines.append("| Q | " + " | ".join(present) + " |")
        lines.append("|---|" + "---|" * len(present))
        for qid in qids:
            cells = ["PASS" if scored[doc][l][0].get(qid) == "PASS" else "FAIL"
                     for l in present]
            lines.append(f"| {qid} | " + " | ".join(cells) + " |")
        lines.append("")

    # Timings
    lines.append("## Wall time (seconds)\n")
    lines.append("Indicative, single machine (Apple Silicon, MPS). Rerank time "
                 "is the shared external cross-encoder over 16 candidates x "
                 "42/44 queries — identical machinery for all systems. "
                 "LangChain/Haystack ingest windows include loading bge-m3; "
                 "the LlamaIndex runner loads it before its ingest timer.\n")
    lines.append("| System | Doc | Ingest | Query (retrieve) | Query (rerank) | Query total |")
    lines.append("|---|---|---|---|---|---|")
    for label, tpl in SYSTEMS:
        if label == "Datum":
            continue
        for doc in DOCS:
            m = meta_for(tpl.format(d=doc))
            if not m:
                continue
            lines.append(f"| {label} | {doc.upper()} | {m.get('ingest_total_s', '?')} "
                         f"| {m.get('query_retrieve_s', '?')} "
                         f"| {m.get('query_rerank_s', '?')} "
                         f"| {m.get('query_total_s', '?')} |")
    lines.append("")

    # Errors recorded by runners
    err_lines = []
    for label, tpl in SYSTEMS:
        for doc in DOCS:
            m = meta_for(tpl.format(d=doc))
            for e in m.get("errors", []):
                err_lines.append(f"- {label} / doc {doc.upper()}: `{e}`")
    if err_lines:
        lines.append("## Runner errors (verbatim)\n")
        lines.extend(err_lines)
        lines.append("")

    # Static caveats — kept here so regeneration preserves them.
    lines.append("## Caveats and disclosed workarounds\n")
    lines.append(
        "- **LlamaIndex, out of the box, crashed on document A and silently "
        "mis-read document B.** The venv's `llama-index==0.14.23` install did "
        "not include `llama-index-readers-file` (pip additions were "
        "permission-blocked), and without it `SimpleDirectoryReader` reads a "
        "PDF as plain text: document B came back as ONE document of raw "
        "`%PDF-1.4` bytes (scored 0/44 — preserved as "
        "`llamaindex-results-b-rawfallback.json`), and on document A the "
        "default SentenceSplitter/nltk-punkt died with `RecursionError: "
        "maximum recursion depth exceeded` over those raw bytes (verbatim "
        "log: `llamaindex-a-defaultcrash.log`). The scored runs pass "
        "SimpleDirectoryReader's documented `file_extractor` hook a "
        "pypdf-per-page reader identical in behaviour to the official "
        "`llama_index.readers.file.PDFReader`.")
    lines.append(
        "- **Haystack 3.0.0 core has no local embedder.** First run failed "
        "with `ImportError: cannot import name "
        "'SentenceTransformersDocumentEmbedder' from "
        "'haystack.components.embedders'` — in Haystack 3.x those embedders "
        "moved to the separate `sentence-transformers-haystack` package, "
        "which is not installed (pip permission-blocked). The scored runs "
        "compute embeddings directly with "
        "`sentence_transformers.SentenceTransformer('BAAI/bge-m3').encode()` "
        "— the identical call Haystack's own wrapper makes — and attach them "
        "to Haystack Documents; conversion, cleaning, splitting, storage and "
        "retrieval are pure Haystack.")
    lines.append(
        "- **LangChain-OCR** = UnstructuredPDFLoader(strategy='hi_res', "
        "mode='single') with local tesseract/poppler; everything else "
        "identical to the standard LangChain config.")
    lines.append(
        "- Datum results (`../datum-results-*.json`) were produced the same "
        "day by `../run_datum.py` (its pipeline applies the same "
        "bge-m3 + bge-reranker-v2-m3 internally, plus its own OCR ingest).\n")

    lines.append("## Failure categories (from the answer keys)\n")
    lines.append(
        "- All three competitor standard configs fail the same core cluster: "
        "**text that exists only inside images** — chart-only values "
        "(A: Q11/Q12/Q22, B: Q11/Q27), diagram/org-chart text (A: Q38/Q39), "
        "image-only multilingual facsimiles (A: Q27 Hindi; B: Q08/Q10 Arabic, "
        "Q14 Tamil), degraded scans/faxes (A: Q29/Q30, B: Q35), and **PDF "
        "metadata** (B: Q44). None of these pipelines OCR images or read "
        "metadata; Datum's ingest does, which accounts for almost the entire "
        "gap.")
    lines.append(
        "- LangChain additionally lost A-Q10 (sentence split across a page "
        "boundary — page-scoped chunks) which LlamaIndex passed, and "
        "conflict-trap A-Q09.")
    lines.append(
        "- LangChain-OCR (hi_res) recovered A: Q09, Q10, Q12, Q38, Q39, Q41, "
        "Q42 and B: Q05, Q35, but LOST previously-passing footnote/list/table "
        "questions (A: Q06, Q07, Q15, Q19, Q37; B: Q33, Q34) — hi_res element "
        "segmentation scrambles fine-grained text order — netting only "
        "32/42 and 34/44.")
    lines.append(
        "- Datum's only failures: the two document-A contradiction traps "
        "(Q09, Q21 — both conflicting values must surface in the top 5) and "
        "document-B Q01 (nested-table lookup).\n")

    # Package versions
    freeze = subprocess.run([PY, "-m", "pip", "freeze"],
                            capture_output=True, text=True).stdout
    relevant = [l for l in freeze.splitlines() if RELEVANT_PKGS.match(l)]
    lines.append("## Package versions (pip freeze, relevant lines)\n")
    lines.append("```")
    lines.extend(sorted(relevant))
    lines.append("```")
    lines.append("")

    # Rerun commands
    lines.append("## Rerun commands\n")
    lines.append("```bash")
    lines.append("cd benchmarks/adversarial/competitors")
    lines.append("V=.venv/bin/python")
    for doc in DOCS:
        lines.append(f"caffeinate -i $V run_langchain.py --pdf ../document-{doc}.pdf "
                     f"--questions ../questions-{doc}.json --out langchain-results-{doc}.json")
        lines.append(f"caffeinate -i $V run_llamaindex.py --pdf ../document-{doc}.pdf "
                     f"--questions ../questions-{doc}.json --out llamaindex-results-{doc}.json")
        lines.append(f"caffeinate -i $V run_haystack.py --pdf ../document-{doc}.pdf "
                     f"--questions ../questions-{doc}.json --out haystack-results-{doc}.json")
        lines.append(f"caffeinate -i $V run_langchain.py --loader unstructured-hires "
                     f"--pdf ../document-{doc}.pdf --questions ../questions-{doc}.json "
                     f"--out langchain-ocr-results-{doc}.json")
    for doc in DOCS:
        for label, tpl in SYSTEMS:
            rp = Path(tpl.format(d=doc))
            rel = f"../{rp.name}" if rp.parent == ADV else rp.name
            lines.append(f"$V ../score.py ../questions-{doc}.json {rel}")
    lines.append("$V build_results_md.py   # regenerate this file")
    lines.append("```")
    lines.append("")

    out = HERE / "RESULTS.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
