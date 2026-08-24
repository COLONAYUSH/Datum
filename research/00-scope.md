# Reimagining RAG — Research Program: Scope & Method

**Date started:** 2026-08-05
**Objective:** (1) An exhaustive, citation-grounded survey of RAG and the retrieval/memory component of agentic LLM systems — foundations through the mid-2026 frontier. (2) An evidence-based catalogue of the *common, recurring* failure modes across every significant RAG framework/platform in production today. (3) A first-principles design for a next-generation retrieval framework for the agentic ecosystem, motivated by (1) and (2). Output feeds a research paper.

## Method

Four chained multi-agent workflows; every agent writes full findings to disk with citations, returns only compact structured summaries. Verification is built in at each stage.

| Stage | Workflow | Design |
|---|---|---|
| 1 | `rag-landscape-sweep` | 14 parallel deep-research agents (one per research dimension, web-grounded, ≥15 searches each) → 1 coverage-audit critic |
| 2 | `rag-framework-autopsy` | 14 parallel autopsy agents (one per framework/family; evidence mined from docs, source, GitHub issues, HN/Reddit, blogs, benchmarks) → 1 completeness critic |
| 3 | `failure-synthesis` | 6 cross-cutting failure-dimension synthesizers → 1 merge into canonical taxonomy → adversarial skeptic agents attempt to refute each top issue → final editor |
| 4 | `first-principles-design` | 5 rival designers, each from a different first-principles stance → 3-judge scoring panel → 1 synthesis architect → red-team critics (feasibility, prior-art, issue-coverage) → final revision |

## Research taxonomy (Stage 1 dimensions)

1. `foundations-and-surveys` — RAG lineage, major surveys, taxonomies, debates
2. `document-processing-chunking` — parsing, layout, chunking strategies & evidence
3. `embeddings-representation` — dense/sparse/late-interaction, theory & limits
4. `indexing-vector-databases` — ANN algorithms, vector DB landscape, hybrid infra
5. `query-understanding-transformation` — rewriting, decomposition, routing
6. `retrieval-reranking-fusion` — hybrid fusion, rerankers, context selection/compression
7. `advanced-rag-architectures` — Self-RAG, CRAG, FLARE, RAPTOR, adaptive/iterative RAG
8. `graph-structured-rag` — GraphRAG family, HippoRAG, KG quality, graph-vs-vector evidence
9. `agentic-rag-deep-research` — agentic retrieval patterns, deep research systems, RL-trained search agents
10. `memory-context-engineering` — agent memory systems, context rot, long-context vs RAG, KV-cache economics
11. `evaluation-benchmarks` — RAGAS et al., benchmarks, LLM-judge reliability, the eval crisis
12. `multimodal-structured-rag` — vision-native retrieval, tables, SQL, code retrieval
13. `production-industry` — what Anthropic/OpenAI/Google/AWS/Azure/enterprise actually ship; security
14. `frontier-2025-2026` — the bleeding edge; what's rising; what died

## Framework corpus (Stage 2 autopsy targets)

LangChain+LangGraph · LlamaIndex · Haystack · DSPy · Microsoft GraphRAG (+forks) · HKUDS family (LightRAG/PathRAG/MiniRAG) · RAGFlow · low-code builders (Dify/Flowise/LangFlow/n8n) · OSS RAG platforms (R2R/Onyx/AnythingLLM/Verba/Kotaemon/Cognita/Morphik) · research toolkits (FlashRAG/AutoRAG/BERGEN) · managed OpenAI/Azure · managed AWS/Google · vector-DB-native & startup platforms (Pinecone/Weaviate/Qdrant/Chroma/Vectara/Contextual AI/GroundX/Ragie) · retrieval inside agent frameworks (OpenAI Agents SDK, Claude Agent SDK/MCP, CrewAI, AG2, Semantic Kernel, ADK, smolagents, Letta, Mastra)

## Issue taxonomy (fixed categories, used by Stages 2–4)

`abstraction-design` · `retrieval-quality` · `data-processing` · `evaluation-observability` · `production-ops` · `agentic-integration` · `security-governance` · `dx-docs` · `performance-cost` · `other`

## Evidence standards

- Cite only sources actually retrieved during research; never fabricate citations, arXiv IDs, or quotes.
- Papers: Title — first author et al. — venue/arXiv ID — year — contribution — known limitations.
- Framework issues must carry concrete evidence (GitHub issue #, thread URL, benchmark, postmortem) and be labeled: documented-recurring / single-anecdote / architectural-inference.
- Stage 3 accepts an issue as "common" only if evidenced across ≥3 independent frameworks and it survives adversarial refutation.

## Deliverables map

- `research/01-landscape/*.md` — 14 dimension surveys
- `research/02-frameworks/*.md` — 14 framework autopsies
- `research/03-synthesis/*.md` — failure-dimension syntheses + `common-issues.md` (verified taxonomy)
- `design/proposal-*.md` — 5 rival first-principles designs; `design/judgment.md`; `design/FRAMEWORK.md` (final spec)
- paper outline (private `Datum-paper` repo) — paper skeleton mapping corpus → sections
- `README.md` — index + executive summary
