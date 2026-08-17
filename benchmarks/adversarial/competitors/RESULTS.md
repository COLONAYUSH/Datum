# Adversarial retrieval benchmark — competitor results

Scored by `benchmarks/adversarial/score.py` (unmodified), mechanical top-5 rule. All systems: BAAI/bge-m3 embeddings, framework retrieves top 16, shared external CrossEncoder(BAAI/bge-reranker-v2-m3) reranks to top 5. Queries verbatim, zero-shot.

## Totals (questions passed)

| System | Document A (42 q) | Document B (44 q) |
|---|---|---|
| Datum | 40/42 | 43/44 |
| LangChain | 30/42 | 34/44 |
| LlamaIndex | 32/42 | 34/44 |
| Haystack | 32/42 | 35/44 |
| LangChain-OCR | 32/42 | 34/44 |

## Per-question grid — document A

| Q | Datum | LangChain | LlamaIndex | Haystack | LangChain-OCR |
|---|---|---|---|---|---|
| Q01 | PASS | PASS | PASS | PASS | PASS |
| Q02 | PASS | PASS | PASS | PASS | PASS |
| Q03 | PASS | PASS | PASS | PASS | PASS |
| Q04 | PASS | PASS | PASS | PASS | PASS |
| Q05 | PASS | PASS | PASS | PASS | PASS |
| Q06 | PASS | PASS | PASS | PASS | FAIL |
| Q07 | PASS | PASS | PASS | PASS | FAIL |
| Q08 | PASS | PASS | PASS | PASS | PASS |
| Q09 | FAIL | FAIL | PASS | PASS | PASS |
| Q10 | PASS | FAIL | PASS | FAIL | PASS |
| Q11 | PASS | FAIL | FAIL | FAIL | FAIL |
| Q12 | PASS | FAIL | FAIL | FAIL | PASS |
| Q13 | PASS | PASS | PASS | PASS | PASS |
| Q14 | PASS | PASS | PASS | PASS | PASS |
| Q15 | PASS | PASS | PASS | PASS | FAIL |
| Q16 | PASS | PASS | PASS | PASS | PASS |
| Q17 | PASS | PASS | PASS | PASS | PASS |
| Q18 | PASS | PASS | PASS | PASS | PASS |
| Q19 | PASS | PASS | PASS | PASS | FAIL |
| Q20 | PASS | PASS | PASS | PASS | PASS |
| Q21 | FAIL | PASS | PASS | PASS | PASS |
| Q22 | PASS | FAIL | FAIL | FAIL | FAIL |
| Q23 | PASS | PASS | PASS | PASS | PASS |
| Q24 | PASS | PASS | PASS | PASS | PASS |
| Q25 | PASS | PASS | PASS | PASS | PASS |
| Q26 | PASS | PASS | PASS | PASS | PASS |
| Q27 | PASS | FAIL | FAIL | FAIL | FAIL |
| Q28 | PASS | PASS | PASS | PASS | PASS |
| Q29 | PASS | FAIL | FAIL | FAIL | FAIL |
| Q30 | PASS | FAIL | FAIL | FAIL | FAIL |
| Q31 | PASS | PASS | PASS | PASS | PASS |
| Q32 | PASS | PASS | PASS | PASS | PASS |
| Q33 | PASS | PASS | PASS | PASS | PASS |
| Q34 | PASS | PASS | PASS | PASS | PASS |
| Q35 | PASS | PASS | PASS | PASS | PASS |
| Q36 | PASS | PASS | PASS | PASS | PASS |
| Q37 | PASS | PASS | PASS | PASS | FAIL |
| Q38 | PASS | FAIL | FAIL | FAIL | PASS |
| Q39 | PASS | FAIL | FAIL | FAIL | PASS |
| Q40 | PASS | PASS | PASS | PASS | PASS |
| Q41 | PASS | FAIL | FAIL | PASS | PASS |
| Q42 | PASS | FAIL | FAIL | FAIL | PASS |

## Per-question grid — document B

| Q | Datum | LangChain | LlamaIndex | Haystack | LangChain-OCR |
|---|---|---|---|---|---|
| Q01 | FAIL | PASS | PASS | PASS | PASS |
| Q02 | PASS | PASS | PASS | PASS | PASS |
| Q03 | PASS | FAIL | FAIL | FAIL | FAIL |
| Q04 | PASS | PASS | PASS | PASS | PASS |
| Q05 | PASS | FAIL | FAIL | PASS | PASS |
| Q06 | PASS | PASS | PASS | PASS | PASS |
| Q07 | PASS | PASS | PASS | PASS | PASS |
| Q08 | PASS | FAIL | FAIL | FAIL | FAIL |
| Q09 | PASS | FAIL | FAIL | FAIL | FAIL |
| Q10 | PASS | FAIL | FAIL | FAIL | FAIL |
| Q11 | PASS | FAIL | FAIL | FAIL | FAIL |
| Q12 | PASS | PASS | PASS | PASS | PASS |
| Q13 | PASS | PASS | PASS | PASS | PASS |
| Q14 | PASS | FAIL | FAIL | FAIL | FAIL |
| Q15 | PASS | PASS | PASS | PASS | PASS |
| Q16 | PASS | PASS | PASS | PASS | PASS |
| Q17 | PASS | PASS | PASS | PASS | PASS |
| Q18 | PASS | PASS | PASS | PASS | PASS |
| Q19 | PASS | PASS | PASS | PASS | PASS |
| Q20 | PASS | PASS | PASS | PASS | PASS |
| Q21 | PASS | PASS | PASS | PASS | PASS |
| Q22 | PASS | PASS | PASS | PASS | PASS |
| Q23 | PASS | PASS | PASS | PASS | PASS |
| Q24 | PASS | PASS | PASS | PASS | PASS |
| Q25 | PASS | PASS | PASS | PASS | PASS |
| Q26 | PASS | PASS | PASS | PASS | PASS |
| Q27 | PASS | FAIL | FAIL | FAIL | FAIL |
| Q28 | PASS | PASS | PASS | PASS | PASS |
| Q29 | PASS | PASS | PASS | PASS | PASS |
| Q30 | PASS | PASS | PASS | PASS | PASS |
| Q31 | PASS | PASS | PASS | PASS | PASS |
| Q32 | PASS | PASS | PASS | PASS | PASS |
| Q33 | PASS | PASS | PASS | PASS | FAIL |
| Q34 | PASS | PASS | PASS | PASS | FAIL |
| Q35 | PASS | FAIL | FAIL | FAIL | PASS |
| Q36 | PASS | PASS | PASS | PASS | PASS |
| Q37 | PASS | PASS | PASS | PASS | PASS |
| Q38 | PASS | PASS | PASS | PASS | PASS |
| Q39 | PASS | PASS | PASS | PASS | PASS |
| Q40 | PASS | PASS | PASS | PASS | PASS |
| Q41 | PASS | PASS | PASS | PASS | PASS |
| Q42 | PASS | PASS | PASS | PASS | PASS |
| Q43 | PASS | PASS | PASS | PASS | PASS |
| Q44 | PASS | FAIL | FAIL | FAIL | FAIL |

## Wall time (seconds)

Indicative, single machine (Apple Silicon, MPS). Rerank time is the shared external cross-encoder over 16 candidates x 42/44 queries — identical machinery for all systems. LangChain/Haystack ingest windows include loading bge-m3; the LlamaIndex runner loads it before its ingest timer.

| System | Doc | Ingest | Query (retrieve) | Query (rerank) | Query total |
|---|---|---|---|---|---|
| LangChain | A | 22.17 | 2.17 | 35.14 | 37.3 |
| LangChain | B | 17.59 | 2.46 | 41.28 | 43.74 |
| LlamaIndex | A | 3.09 | 4.78 | 86.94 | 91.72 |
| LlamaIndex | B | 2.76 | 4.9 | 96.46 | 101.36 |
| Haystack | A | 19.01 | 2.09 | 53.57 | 55.66 |
| Haystack | B | 15.94 | 1.58 | 42.79 | 44.37 |
| LangChain-OCR | A | 80.79 | 1.83 | 40.99 | 42.82 |
| LangChain-OCR | B | 54.73 | 2.37 | 39.77 | 42.13 |

## Caveats and disclosed workarounds

- **LlamaIndex, out of the box, crashed on document A and silently mis-read document B.** The venv's `llama-index==0.14.23` install did not include `llama-index-readers-file` (pip additions were permission-blocked), and without it `SimpleDirectoryReader` reads a PDF as plain text: document B came back as ONE document of raw `%PDF-1.4` bytes (scored 0/44 — preserved as `llamaindex-results-b-rawfallback.json`), and on document A the default SentenceSplitter/nltk-punkt died with `RecursionError: maximum recursion depth exceeded` over those raw bytes (verbatim log: `llamaindex-a-defaultcrash.log`). The scored runs pass SimpleDirectoryReader's documented `file_extractor` hook a pypdf-per-page reader identical in behaviour to the official `llama_index.readers.file.PDFReader`.
- **Haystack 3.0.0 core has no local embedder.** First run failed with `ImportError: cannot import name 'SentenceTransformersDocumentEmbedder' from 'haystack.components.embedders'` — in Haystack 3.x those embedders moved to the separate `sentence-transformers-haystack` package, which is not installed (pip permission-blocked). The scored runs compute embeddings directly with `sentence_transformers.SentenceTransformer('BAAI/bge-m3').encode()` — the identical call Haystack's own wrapper makes — and attach them to Haystack Documents; conversion, cleaning, splitting, storage and retrieval are pure Haystack.
- **LangChain-OCR** = UnstructuredPDFLoader(strategy='hi_res', mode='single') with local tesseract/poppler; everything else identical to the standard LangChain config.
- Datum results (`../datum-results-*.json`) were produced the same day by `../run_datum.py` (its pipeline applies the same bge-m3 + bge-reranker-v2-m3 internally, plus its own OCR ingest).

## Failure categories (from the answer keys)

- All three competitor standard configs fail the same core cluster: **text that exists only inside images** — chart-only values (A: Q11/Q12/Q22, B: Q11/Q27), diagram/org-chart text (A: Q38/Q39), image-only multilingual facsimiles (A: Q27 Hindi; B: Q08/Q10 Arabic, Q14 Tamil), degraded scans/faxes (A: Q29/Q30, B: Q35), and **PDF metadata** (B: Q44). None of these pipelines OCR images or read metadata; Datum's ingest does, which accounts for almost the entire gap.
- LangChain additionally lost A-Q10 (sentence split across a page boundary — page-scoped chunks) which LlamaIndex passed, and conflict-trap A-Q09.
- LangChain-OCR (hi_res) recovered A: Q09, Q10, Q12, Q38, Q39, Q41, Q42 and B: Q05, Q35, but LOST previously-passing footnote/list/table questions (A: Q06, Q07, Q15, Q19, Q37; B: Q33, Q34) — hi_res element segmentation scrambles fine-grained text order — netting only 32/42 and 34/44.
- Datum's only failures: the two document-A contradiction traps (Q09, Q21 — both conflicting values must surface in the top 5) and document-B Q01 (nested-table lookup).

## Package versions (pip freeze, relevant lines)

```
faiss-cpu==1.15.0
haystack-ai==3.0.0
langchain-community==0.4.2
langchain-core==1.5.5
langchain-huggingface==1.2.2
langchain-text-splitters==1.1.2
langchain==1.3.15
llama-index-core==0.14.23
llama-index-embeddings-huggingface==0.7.0
llama-index==0.14.23
pdf2image==1.17.0
pdfminer.six==20260107
pypdf==6.16.1
sentence-transformers==5.7.0
torch==2.13.0
transformers==5.15.0
unstructured==0.25.2
```

## Rerun commands

```bash
cd benchmarks/adversarial/competitors
V=.venv/bin/python
caffeinate -i $V run_langchain.py --pdf ../document-a.pdf --questions ../questions-a.json --out langchain-results-a.json
caffeinate -i $V run_llamaindex.py --pdf ../document-a.pdf --questions ../questions-a.json --out llamaindex-results-a.json
caffeinate -i $V run_haystack.py --pdf ../document-a.pdf --questions ../questions-a.json --out haystack-results-a.json
caffeinate -i $V run_langchain.py --loader unstructured-hires --pdf ../document-a.pdf --questions ../questions-a.json --out langchain-ocr-results-a.json
caffeinate -i $V run_langchain.py --pdf ../document-b.pdf --questions ../questions-b.json --out langchain-results-b.json
caffeinate -i $V run_llamaindex.py --pdf ../document-b.pdf --questions ../questions-b.json --out llamaindex-results-b.json
caffeinate -i $V run_haystack.py --pdf ../document-b.pdf --questions ../questions-b.json --out haystack-results-b.json
caffeinate -i $V run_langchain.py --loader unstructured-hires --pdf ../document-b.pdf --questions ../questions-b.json --out langchain-ocr-results-b.json
$V ../score.py ../questions-a.json ../datum-results-a.json
$V ../score.py ../questions-a.json langchain-results-a.json
$V ../score.py ../questions-a.json llamaindex-results-a.json
$V ../score.py ../questions-a.json haystack-results-a.json
$V ../score.py ../questions-a.json langchain-ocr-results-a.json
$V ../score.py ../questions-b.json ../datum-results-b.json
$V ../score.py ../questions-b.json langchain-results-b.json
$V ../score.py ../questions-b.json llamaindex-results-b.json
$V ../score.py ../questions-b.json haystack-results-b.json
$V ../score.py ../questions-b.json langchain-ocr-results-b.json
$V build_results_md.py   # regenerate this file
```
