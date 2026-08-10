# Reimagining RAG — Master Handoff

**Purpose of this file:** everything a fresh session needs to continue this work exactly where it left off, with no re-discovery and no repeated mistakes. Read section 0 first, then 9 (next steps). The rest is reference.

**Last updated:** 2026-08-10, mid-session building Milestone B (real hybrid retrieval). The Milestone B build is CODE-COMPLETE and self-verified — 197 tests pass against a real Postgres, and end-to-end semantic search works (a query with zero term overlap retrieves the right section through dense+BM25+ANN fusion and a real cross-encoder rerank). An adversarial review of the new operators was running when this line was written; §12 records its outcome and any fixes. The prior line, kept for provenance: "2026-08-08, end of the session that built Datum through Milestone A and fully provisioned the Milestone B environment (pgvector, embedder, Docling + OCR + ASR installed and verified)."

---

## 0. TL;DR — how to resume without wasting time

This project has three arcs, done in order:
1. **Research** (DONE) — an exhaustive, adversarially-verified survey of RAG + a taxonomy of common framework failures. Lives in `research/`.
2. **Paper** (FIRST DRAFT DONE) — a human-voiced research paper + typeset PDF arguing the failures and proposing the framework. Lives in `paper/`.
3. **Build** (IN PROGRESS) — `Datum`, the actual framework, implemented and tested. Lives in `datum/`. **This is the active work.**

**Where the build is:** Milestones M0 (foundation), A (walking skeleton), **B (real hybrid retrieval: dense + BM25 + ANN fused by RRF + a cross-encoder rerank; §12)**, and **C (eval gate wired to the live Corpus + abstention + concurrency hardening; §13)** are all DONE and verified, and so is the **multi-format DoclingParser track (task #30; §14)** — **221 tests pass against a real Postgres**. The system runs end-to-end through a real CLI (`datum ingest|search|serve|eval|benchmark`) and MCP server; semantic search works (a query with zero term overlap retrieves the right section), out-of-corpus queries abstain, and docx/pptx/xlsx/html/csv all ingest through Docling into the same pipeline. **Milestone D (final acceptance: a real Claude Code/Desktop MCP session against `datum serve`) is the only thing left** — it is interactive (needs a real MCP client attached), so it's the natural hand-back point.

**To resume the build immediately:**
```bash
cd /Users/L054011/Downloads/Reimagining-RAG/datum
source .venv/bin/activate                 # Python 3.12 venv already set up
createdb datum_dev 2>/dev/null || true     # a SCRATCH db — the suite TRUNCATEs whatever DATUM_PG_DSN points at
export DATUM_PG_DSN="postgresql://localhost/datum_dev"   # NEVER point this at a db holding real content
export DATUM_HIT_SIGNING_KEY="dev-key"     # optional: stable hit_ids across restarts; if unset => random per-process key + a warning
# The suite loads real models; HuggingFace's network HEAD checks can HANG for
# many minutes on an SSL-cert error here. The models are already cached, so
# run OFFLINE — identical result, ~22s instead of minutes (or a hang):
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m pytest tests/ -q   # expect: 221 passed (verified 2026-08-11)
datum ingest <somefile.md> --source-id x --namespace tenant:acme
datum search "your query" --namespace tenant:acme
dropdb datum_dev
```

**Milestone B prerequisites — ALL DONE (verified 2026-08-08):** the environment is fully provisioned; the next work is code, not setup.
- `pgvector` 0.8.0 — source-built against PG17; extension + HNSW index + KNN query all verified.
- Embedder — `sentence-transformers` 5.7.0 + `BAAI/bge-small-en-v1.5` (384-dim); loads and encodes. torch 2.13.0.
- Docling 2.118.1 — with ALL OCR engines (easyocr, ocrmac [Mac-native, the default Datum will use], rapidocr, tesserocr) + Whisper ASR. Advertises every input format (pdf, docx/xlsx/pptx, doc/xls/ppt, odt/ods/odp, epub, html, latex, csv, image, audio, video, USPTO/JATS/XBRL XML, …).
- **HuggingFace model downloads WORK here** (bge-small pulled fine) — no `HF_ENDPOINT`/proxy config needed. Docling's layout/table/VLM/Whisper models will download at runtime the same way.
- Artifactory is pip's index (all the above routed through it). Note: the harness auto-mode classifier blocks `pip install`, so any further installs must be user-run via a `!` prompt or approved.

**Read these repo files before writing code:** `datum/docs/decisions.md` (31 recorded decisions — do NOT re-litigate them; #19–28 are Milestone B + its two adversarial reviews, #29–30 are Milestone C, #31 is the multi-format DoclingParser), the approved plan at `~/.claude/plans/lazy-popping-frost.md`, and `design/FRAMEWORK.md` (the spec; the "MVP definition" section is the actual v1 scope).

---

## 1. The mission (verbatim intent)

The user asked, across the arc: research RAG/retrieval in agentic systems end to end from every credible source; find the common failures across every existing framework; from first principles design the best RAG framework in the agentic ecosystem; write a research paper on it; then **build that framework for real** ("perfect implementation," "I'm gonna be testing and using it," "don't compromise / don't adjust to a lower solution"). The build is the current focus.

The framework is **Datum**: *"retrieval is a compiled query, not a hand-wired pipeline call."* Its thesis: a `retrieve(query, k) -> docs` signature can't express who's asking, what it should cost, whether a source is trusted, or whether there's enough evidence — so all of that gets smuggled through a metadata filter, which is why a relevance bug and a tenant-isolation breach are empirically the same bug. Datum separates the logical request from the physical plan (System-R style) over a canonical, bitemporal, content-addressed store.

---

## 2. Status snapshot

| Arc | Status | Location |
|---|---|---|
| Research corpus (42 files, ~1500 sources) | DONE, verified | `research/` |
| Verified common-issues taxonomy (CI-01…27) | DONE (2 adversarial rounds) | `research/03-synthesis/common-issues.md` |
| Framework design spec | DONE | `design/FRAMEWORK.md` (+ 5 `proposal-*.md`, `judgment.md`) |
| Paper draft (~9,500 words) + PDF (21pp, 6 figures) | FIRST DRAFT DONE | `paper/draft.md`, `paper/datum-paper.pdf` |
| **Datum code — M0 foundation** | **DONE, verified** | `datum/src/datum/{kernel,storage,security,groundstore,writepath,operators,derivation/chunking,evidence,planner,policy,mcp_server}` |
| **Datum code — Milestone A (walking skeleton)** | **DONE, verified (152 tests)** | `datum/` — runs end-to-end via CLI + MCP |
| **Datum code — Milestone B (hybrid retrieval)** | **DONE + verified (214 tests); both adversarial reviews passed, fixes applied (decisions #19–28)** | dense+BM25+ANN fused (RRF) + cross-encoder rerank, all through the conformance gate |
| **Datum code — Milestone C (eval gate + concurrency hardening)** | **DONE + verified (219 tests); decisions #27,#29,#30** | eval gate wired to live Corpus (`datum eval`); real dense-similarity abstention; unconditional audit trace; namespace-scoped-span concurrency test |
| **Datum code — multi-format ingestion (task #30; §14)** | **DONE + verified (221 tests); decision #31** | DoclingParser + `ingest_file`/`datum benchmark`; md/txt/html/csv/docx/pptx/xlsx pass end-to-end; pdf/image/audio env-blocked & reported |
| Datum code — Milestone D (real tool-calling-model MCP test) | **NEXT (interactive)** | point a real Claude Code/Desktop session at `datum serve` |

---

## 3. The Datum code build — detailed status

Package: `datum/src/datum/`. Layer model (FRAMEWORK.md §architecture): L0 object storage · L1 WAL · L2 ground store · L3 write path · L4 derivation/views · L5 operators · L6 planner · L7 evidence · L8 MCP surface, plus cross-cutting security/eval/governance. **Strict one-directional imports** (kernel ← storage ← groundstore ← writepath ← derivation ← operators ← planner ← evidence; security/eval/mcp cross-cutting; `corpus.py` is the composition root above all).

**BUILT and tested (152 tests pass, real Postgres):**
- `kernel/` — all 11 modules; frozen dataclasses + Protocols, zero I/O. The semver-frozen surface. `datum/__init__.py`'s `__all__` (36 symbols) IS the budget (35 spec + 5 exceptions, 4 deferred symbols must land within 40 — budget is effectively full at Phase 2).
- `storage/` — `LocalFilesystemBlobStore` (content-addressed) + Postgres `WAL` (`append`, `append_in_txn` [the L1↔L2 txn seam], `tail_since` [namespace-required, resumable], `scan` [one-shot global]). Migration `0001_wal.sql`. Hand-rolled migration runner.
- `security/` — `current_principal()` (contextvar, RAISES if unbound — no default principal ever), `bind_principal()`, `check_namespace_access`/`require_namespace_access` (v1 exact-equality ACL, fail-closed).
- `groundstore/` (L2, **the safety-critical module, built by one hand**) — `GroundStore` with the uniqueness-CAS invariant (partial unique index `records_one_live_per_span`), atomic supersede (close-old + insert-new + WAL-append in one txn), `forget` tombstone, `find_span`, `get_live`, `live_in_namespace`. **The write-race (Mem0 #4892 / paper Fig 5) is proven closed by a 40-round two-writer concurrency test → exactly one live record every time.** Migration `0002_records.sql` (bitemporal columns). `precondition.py` (reject-destructive-composition hooks).
- `writepath/` (L3) — `WriteOrchestrator` (authority-tier clamp, write-side namespace guard, preconditions) + `DocumentPolicy` (v1's only policy) + `MarkdownParser` (dependency-free; Docling is opt-in/lazy).
- `operators/` (L5) — `GrepOperator` (reads L2 canonical records directly; dual-fragment so it passes conformance), `OperatorRegistry` (the conformance gate — refuses registration on fail), and the full `conformance/` suite (has real teeth: proven to catch fail-open operators; built + hardened by the parallel wave and adversarial review).
- `derivation/chunking.py` — hand-rolled boundary-constrained FastCDC (takes `protected_regions`, per decision #15). **`derivation/views/` and `derivation/engine.py` are NOT built — Milestone B.**
- `evidence/` (L7) — `build_evidence_state` (copies structural provenance straight through; `insufficient_evidence` is a first-class status), `estimate_sufficiency` (explicitly uncalibrated).
- `planner/` (L6) — `PlanCompiler` (request → Plan with bound executor, ACL resolved first, fail-closed) + `TraceStore` (replay-by-record; migration `0003_plan_traces.sql`). `Plan.explain()`/`.execute()`/`.diff()` on the kernel type.
- `policy/rule_table.py` — the declared static plan-selection policy (v1's fusion slot; `SearcherShim` is Phase 3, not built).
- `mcp_server/` — `HitRegistry` (stateless HMAC token carrying a reference only, NEVER trust metadata — decision #12), `build_server`/`build_tools` (5 read verbs: search/fetch/navigate/explain/since; no `principal` param — comes from session), `auth_middleware`.
- `corpus.py` — **the composition root.** `Corpus.open(dsn)` wires everything and registers grep through the conformance gate. Methods: `ingest`, `search`, `fetch`, `navigate`, `explain`, `since`, `compile_plan`, `replay(plan_id, against=)`, `precondition`.
- `cli.py` — `datum ingest|search|serve`.
- `eval/regression.py` — fixed human-curated regression harness (built by the wave; not yet wired into a CI gate — that's Milestone C).

**Migrations:** `0001_wal`, `0002_records`, `0003_plan_traces`. Runner is idempotent, advisory-locked.

---

## 4. Environment & how to run

- **Python:** 3.12 (`/opt/homebrew/bin/python3.12`). venv at `datum/.venv`. System python is 3.9 — do NOT use it (pyproject needs 3.11+).
- **Postgres:** local Homebrew `postgresql@17` on default port 5432 (other databases live here — don't touch `mantis*`). **`pgvector` 0.8.0 IS installed** (source-built against PG17 on 2026-08-08; verified with an HNSW KNN query). **TEST-SAFETY (important):** the DB-backed tests TRUNCATE `records`/`wal_entries`/`plan_traces` on whatever `DATUM_PG_DSN` points at, which defaults to `postgresql://localhost/datum` when unset — the SAME default the `datum` CLI ingests real content into. Always point `DATUM_PG_DSN` at a throwaway DB before running the suite; never run tests against a DB holding content you care about.
- **Install:** `pip install -e '.[dev]'` inside the venv. **As of 2026-08-08 the venv ALSO has the full Milestone-B + multi-format stack installed:** `[embed]` (sentence-transformers 5.7.0, torch 2.13.0) and Docling 2.118.1 with all OCR engines (easyocr/ocrmac/rapidocr/tesserocr) + Whisper ASR. These are lazy-imported, so the core still runs without them. All routed through Artifactory. (pyproject's `parse`/`embed` extras should be updated to pin these + the OCR extras when the Docling parser is wired — see task #30.)
- **MCP SDK:** installed `mcp==2.0.0` — the class is `mcp.server.mcpserver.MCPServer` (NOT the v1 `FastMCP`). Schemas are `input_schema`/`output_schema` (snake_case). pyproject floor is `mcp>=2.0`.
- **Tests:** `DATUM_PG_DSN=postgresql://localhost/<scratch-db> python -m pytest tests/ -q`. DB-backed tests skip cleanly if no Postgres is reachable. **152 pass** (verified 2026-08-08, ~1.8s). See the TEST-SAFETY note above before running.
- **Paper tooling:** `tectonic` (LaTeX) + `pandoc` for the PDF; `rsvg-convert` renders the SVG figures. Rebuild: see `paper/` (figures are hand-authored SVG in `paper/figures/`).

---

## 5. Research corpus & paper

- `research/00-scope.md` — methodology.
- `research/01-landscape/` — 20 survey files (foundations → 2026 frontier, incl. gap-fills: multilingual, private/federated, medical, AIGC-contamination, generative-retrieval lineage, QPP).
- `research/02-frameworks/` — 20 evidence-based autopsies (~60 products; every issue tagged + severity + documented-recurring/anecdote/inference).
- `research/03-synthesis/common-issues.md` — the VERIFIED taxonomy (CI-01…27; 4 confirmed / 8 weakened-and-restated / 0 refuted after 2 adversarial rounds) + `verification-report.md` + 6 `failures-*.md`.
- `design/FRAMEWORK.md` — the full spec (name: Datum). `proposal-*.md` (5 rival designs), `judgment.md`.
- `paper/draft.md` — the paper (source of truth). `paper/STYLE.md` — the anti-AI-slop style rules (SEE §11 — critical). `paper/outline.md`. `paper/datum-paper.pdf` — 21pp typeset output. `paper/figures/*.svg` — 6 figures (fig6 is a TEMPLATE with placeholder XX.X values, honestly marked — no fabricated results).

---

## 6. Key learnings — what worked, what NOT to do

**Process moves that worked (repeat these):**
- **Adversarial review before building on top.** A 4-lens review of the parallel-wave modules reproduced 18 real defects (2 CRITICAL) by running code, before the ground store was built on them. Worth every token.
- **Fork parallelism for genuinely independent modules only.** Modules with no interface dependency (once the kernel was pinned) were built by concurrent `Workflow`/`Agent` forks on DISJOINT file sets. It worked because interfaces were frozen first.
- **One consistent hand for safety-critical + composition-coupled code.** The ground store (CAS/atomicity), planner, and `corpus.py` were built directly, not delegated — the plan reserved these and it was right.
- **Test against real Postgres, never mocks,** for anything touching transactions/CAS/ordering. Mocks would have hidden the exact bugs that matter.
- **Every deviation → `datum/docs/decisions.md`,** numbered, with reasoning. 18 so far. This is how nothing load-bearing lives only in chat.
- **First-principles re-derivation of the foundation** (when the user flagged a model switch) caught 6 real kernel defects. Do this at layer boundaries.

**What NOT to do (mistakes made and corrected):**
- Do NOT trust a build agent's "verified, tests pass" self-report — re-run tests yourself. (Caught real gaps this way.)
- Do NOT let one agent's prompt instruct another to evade a security control (a fork's edited retry once tried to work around Lilly's content-scanning proxy; it was correctly blocked). Surface blocks to the user instead.
- Do NOT add fields to the frozen kernel casually — but when the integration genuinely needs one (source_id/stable_key/parser_confidence on WriteOp #17; record_id on EvidenceItem #18), do it deliberately and record it. Three such additions were forced by tests; all justified.
- Do NOT reference a decisions.md number before the entry exists (caused a numbering collision with a fork's append; reconcile numbering in one pass when forks land).
- Do NOT fabricate benchmark numbers, ever. The paper's results figure is a labeled TEMPLATE. The user explicitly wants predicted-but-clearly-marked placeholders, NOT fake real-looking numbers.
- Watch the `decisions.md` header text — it drifts; update the "N–M during phase X" line when you add entries.

---

## 7. The "zero ML" question — answered (it is NOT a compromise)

The user asked whether "zero ML dependencies" in the walking skeleton was a limitation/compromise. **It is not.** It is deliberate build sequencing:
- Milestone A uses grep (plain text match) as the FIRST operator specifically to prove the whole 9-layer substrate works end-to-end WITHOUT the confounding variable of model setup. If plumbing breaks, you find out with grep (fast, deterministic), not while also debugging embeddings.
- Grep is also a legitimately strong operator, not a toy — this project's OWN research found agentic grep/filesystem search beat embeddings for code retrieval (the Claude Code finding). It stays as one first-class operator among several.
- **Real semantic retrieval is Milestone B** (next): a real open-weight embedding model (dense vectors via pgvector), real BM25 lexical, fusion, and reranking — the hybrid the paper argues for. Grep is joined by these, not the ceiling.
- Nothing was lowered. The design always expected multiple fused operators; A just built the substrate + the cheapest operator first.

---

## 8. COMPLIANCE — resolved 2026-08-08

Lilly org policy: packages come from **JFrog Artifactory**; public PyPI/NPM are prohibited. **This is satisfied.** pip's `global.index-url` in `~/.pip/pip.conf` points at Lilly's Artifactory PyPI mirror (`elilillyco.jfrog.io/.../Lilly-Python`, with the user's embedded token), so every `pip install` already routes through Artifactory, not public PyPI. Nothing to change on the package-source front.

A few related notes:
1. The harness **auto-mode classifier blocks `pip install`** outright — it must be user-approved or run via a `!`-prefixed prompt. This is an approval gate, not a policy problem.
2. The `vector` Postgres extension is a **C extension, not a pip package**, so it sits outside the PyPI rule. It was built from source against PG17 (the standard, deterministic path; there is no Artifactory route for a Postgres C extension).
3. Model weights (embedder, Docling layout/table, VLM, Whisper) download from **HuggingFace at runtime**, a separate egress path from PyPI. **Verified working in this environment 2026-08-08** (bge-small pulled fine) — no `HF_ENDPOINT`/proxy config needed. If a future locked-down machine ever blocks it, Lilly may expose an Artifactory `huggingfaceml` remote to point `HF_ENDPOINT` at, or pre-stage the model cache.

---

## 9. Next steps — Milestone C/D (Milestone B is DONE; see §12 for its build record)

> **Milestone naming:** this handoff and the task tracker call them Milestone A/B/C/D; the plan file (`lazy-popping-frost.md`) calls the same checkpoints M1/M2/M3/M4 (with M0 = foundation). So **A = M1 (walking skeleton, DONE), B = M2 (hybrid retrieval, DONE — §12), C = M3 (eval gate + concurrency), D = M4 (real-model MCP test).** Same things, two labels.

> **MCP-SDK-v2 deviation is now written up** as `decisions.md` #10 — nothing owed there anymore.

> **The build order below is the RECORD OF WHAT WAS DONE for Milestone B, kept for reference.** For where to go next, read §12's last paragraph (Milestone C, then D, then the multi-format DoclingParser track #30 which is now unblocked).

Goal: real semantic + lexical retrieval, fused, replacing grep-as-sole-operator with a real hybrid (grep stays as one cheap operator). Build order (all steps below are COMPLETE):

1. **Prereqs — ALL DONE (verified 2026-08-08), nothing to install:** `pgvector` 0.8.0 (source-built vs PG17; `CREATE EXTENSION vector` + HNSW + KNN verified), `sentence-transformers` 5.7.0 + `BAAI/bge-small-en-v1.5` (loads/encodes, 384-dim), Docling 2.118.1 + all OCR engines + Whisper ASR. HuggingFace downloads work here (no proxy needed). Full list in §0. Go straight to code.
2. **`derivation/views/dense.py`** — an `Embedder` Protocol + a default local embedder via `sentence-transformers`, lazy-imported. **Concrete model already installed and verified: `BAAI/bge-small-en-v1.5` (384-dim, CPU-fine).** Keep it behind the Protocol so it swaps to a stronger model (Qwen3-Embedding) or a hosted API in one line. A dense `View` builder embeds each chunk and stores vectors in a pgvector column (new migration `0004`; column is `vector(384)` for bge-small — parameterize the dim by the embedder, don't hardcode). Build an HNSW index; match the opclass to the model (bge is cosine-normalized → `vector_cosine_ops`).
3. **`derivation/views/lexical.py`** — a BM25-shaped lexical view. **Decision #4 is a GO/NO-GO:** ParadeDB `pg_search` is NOT installed (checked 2026-08-08 — only stock Postgres FTS is present), so the pragmatic default is Postgres `tsvector`+GIN unless you first build/install the `pg_search` C extension. The conformance score-contract case is written "monotonic in relevance," so either backend passes the same tests and the swap needs no test changes.
4. **`derivation/engine.py`** — the DerivationEngine: subscribes to L3 commits (via the WAL tail), incrementally (re)derives the two views for changed records only (the "only the touched chunk re-derives" property). `derivation/lineage.py` writes L2→L4 edges.
5. **`operators/bm25_op.py`** + **`operators/ann_op.py`** — real Operators reading their views, each registered through `OperatorRegistry` (they must PASS the conformance suite — that's the Milestone B moment the gate first bites real operators). ANN uses pgvector HNSW.
6. **Extend `planner/compiler.py`** — the rule-table policy now fuses grep + BM25 + ANN (RRF-style), with a rerank step. The fusion machinery already exists in the compiler's `_run` loop (written to generalize); wire the real operators in.
7. **Extend `evidence/sufficiency.py`** — score across fused multi-operator candidates (still uncalibrated).
8. **Verify:** end-to-end hybrid search returns semantically-relevant hits (not just term matches) on the sample corpus; conformance gate passes for BM25/ANN; the walking-skeleton tests still green.

**Parallel track — multi-format ingestion + all-format benchmark (task #30, an explicit user priority).** Docling + every OCR engine + Whisper ASR are installed. Write a `DoclingParser` (a new parser/`WritePolicy`) that maps Docling's document model to Datum's `StructuredBody`/`Record` (sections, tables, spans, page/bbox), and wire it into `WriteOrchestrator` keyed by content type so `datum ingest report.pdf | deck.pptx | scan.png | call.mp3` all work. Default OCR to `ocrmac` on macOS. Then build a small corpus with one file per format family (md/txt/html/latex/csv · docx/xlsx/pptx · odt/epub · pdf-digital · pdf-scanned+png/tiff · mp3/wav audio · USPTO/JATS/XBRL XML) and a benchmark that ingests each and runs retrieval, reporting per-format ingest success + retrieval quality. **Ordering:** retrieval-first is the sounder path — get dense/BM25/ANN correct on simple text, THEN pour every format through the same pipeline. Multi-format is a write-path feeder, not a change to retrieval.

**Recommended way to run this build (matches what worked for the foundation, §6).** Delegate genuinely independent module builds to subagents / `Workflow` forks on DISJOINT files — the dense track, the lexical track, and the `DoclingParser` are mutually independent once the kernel/chunker are frozen (they are). Keep the safety-critical and integration work in ONE hand: operator registration through the conformance gate, planner fusion, `corpus.py` wiring. Run an adversarial review (actually run the code; try to break tenancy / score-contract / fail-closed) BEFORE wiring any new operator into the live planner. Re-run the full suite yourself — never trust a sub-agent's "tests pass" self-report. Record every deviation in `datum/docs/decisions.md` (next number is 19; also finally write up the MCP-SDK-v2 deviation noted above).

Then **Milestone C** (wire `eval/regression.py` as a real gate; more concurrency hardening) and **Milestone D** (point a real Claude Code/Desktop session at `datum serve` and use it — the plan's final acceptance).

---

## 10. All artifact paths + memory

- Repo root: `/Users/L054011/Downloads/Reimagining-RAG/` (research + paper + design + `datum/` code + this file). NOT a git repo at root; `datum/` IS `git init`'d but has **no commits yet** (user rule: commit only when asked).
- Approved build plan: `~/.claude/plans/lazy-popping-frost.md`.
- Decisions log: `datum/docs/decisions.md` (1–18).
- Persistent memory: `/Users/L054011/.claude/projects/-Users-L054011-Downloads-Reimagining-RAG/memory/` → `MEMORY.md` (index) + `reimagining-rag-research-project.md`. **A fresh session auto-loads MEMORY.md**, which points here as the authoritative resume doc (both updated 2026-08-08).
- Tracker status: #26 Milestone B — DONE; #27 Milestone C — DONE; #30 multi-format ingestion + benchmark — DONE. **Only #28 Milestone D remains** (interactive: a real MCP client against `datum serve`). Phase-1 roadmap items (as-of queries, crypto-shred, fine-grained predicate ACL, learned plan selection, calibrated scoring/abstention, pdf/image once Docling models are staged) are out of v1 scope per `design/FRAMEWORK.md`.

---

## 11. User preferences & hard rules (do not violate)

- **Quality bar: "don't compromise / don't adjust to a lower solution."** When something's genuinely blocked or a tradeoff is real, surface it and ask — don't silently downscope.
- **Paper voice (`paper/STYLE.md`):** NO AI tells. No em/en dashes; no mid-paragraph setup-colons; no clipped 3-word fragments; no showy vocabulary; no "leverage/delve/robust/landscape/ecosystem" etc. Plain, human, complete sentences. Internal process (workflows, agents, adversarial rounds, CI-NN codes) is translated to normal research language in the paper, never exposed. Real diagrams (hand-authored SVG), real tables — never AI-image-generated. No fabricated results — the results figure is a labeled template.
- **Git (user's global CLAUDE.md):** commit/PR ONLY when asked. NEVER add Claude/Anthropic co-authorship or "Generated with" lines. Author as the user's own identity (`ayush-lilly <ayush.kumar1@lilly.com>`). User must be sole contributor.
- **Compliance:** Artifactory is pip's index — RESOLVED (§8); packages route through Lilly's mirror. `brew` / GitHub-source / Postgres C-extensions are outside the PyPI rule. Do NOT use the pytorch.org `--extra-index-url` (Docling's Nemotron OCR command) — non-Artifactory and CUDA-only.
- The user is testing/using the build directly — "it actually works when run" is the bar, not "it compiles."
- Today's date base was 2026-08-05→08 across the session; convert relative dates to absolute.

---

## 12. Milestone B build record (hybrid retrieval) — 2026-08-10

What got built, in dependency order, and how it was verified. This section is the resume anchor for Milestone C.

**New modules (all under `datum/src/datum/`):**
- `operators/common.py` — the ONE `QueryFragment` every operator answers, plus the shared conformance-probe path (`is_conformance_fragment`, `execute_conformance`). `grep_op.py` was refactored onto it; `GrepFragment` is now an alias of `QueryFragment`.
- `derivation/views/base.py` — the `ViewBuilder` Protocol + `RecordRow`. Transaction rule: `derive`/`remove` run on the engine's cursor and never commit; `ensure_schema` owns its own DDL (views own their schema because the dense column type is embedder-dependent).
- `derivation/views/dense.py` — `Embedder` Protocol + lazy `SentenceTransformersEmbedder` (bge-small-en-v1.5, 384-dim, cosine, query-instruction prefix) + `DenseView` (owns `CREATE EXTENSION vector`, dim-parameterized `view_dense`, HNSW cosine index; hard-errors on a dim mismatch). `vector_literal()` is the one wire-format helper.
- `derivation/views/lexical.py` — `LexicalView` (tsvector+GIN, server-side `to_tsvector`). Decision #4 go/no-go resolved **NO-GO** (pg_search absent); this is the sanctioned fallback.
- `operators/ann_op.py`, `operators/bm25_op.py` — real operators, dual-fragment, both JOIN back to `records` for namespace + liveness (the view is never the source of truth at query time). BM25 uses `websearch_to_tsquery` (injection-proof) + `ts_rank_cd`. Both pass the conformance gate.
- `derivation/engine.py` + `derivation/lineage.py` — `DerivationEngine.refresh(namespace)` tails the WAL from a per-(view,namespace) cursor, delete-then-rederive per touched record_id, cursor advance atomic with view writes. Lineage edges are append-only.
- `planner/reranker.py` — `Reranker` Protocol + lazy `CrossEncoderReranker` (BAAI/bge-reranker-base) + `IdentityReranker`. `default_reranker()` picks the cross-encoder when the embed extra is importable, else identity (and the compiler then omits the rerank step from the plan entirely).

**Changed:** `planner/compiler.py` now runs every selected operator over the same fragment and fuses by **weighted RRF** (K=60, over rankings only — kernel scores are incomparable across operators), then applies the rerank slot to the fused head. `policy/rule_table.py` bumped to `2026-08-10` with `rerank_depth=16`. `evidence/sufficiency.py` → v2 (adds a cross-operator **agreement** term; still uncalibrated, capped 0.9). `corpus.py` registers grep+BM25+ANN through the gate, wires the engine, refreshes synchronously after ingest, and **degrades loudly** (a `UserWarning`, never silent) when no embedder is available — running grep+BM25 only. `groundstore/store.py`, `writepath/*`: span identity + record-id resolution are now **namespace-scoped** (see decisions #19/#20). `operators/registry.py` gained `close()` (bm25/ann hold lazy connections).

**Migrations added:** `0004_views.sql` (view_cursors, lineage_edges — NOT the view tables), `0005_span_namespace.sql` (rebuilds the uniqueness-CAS index as `(namespace, source_id, stable_key)`).

**Decisions recorded:** `datum/docs/decisions.md` #19–23. (The MCP-SDK-v2 deviation flagged in the old §9 was already #10 — nothing owed there.)

**Verified (self-run, not agent self-report):** `DATUM_PG_DSN=<scratch> python -m pytest tests/ -q` → **214 passed** (~156s; the time is real model loads). End-to-end CLI: `datum ingest` then `datum search "how do I log in"` on a KB whose auth section shares no term with the query returns the auth section first, banana bread last. No-embedder path warns loudly and still serves grep+BM25; MCP server builds against the real Corpus. Milestone B acceptance test is `tests/test_milestone_b_hybrid.py` (real embedder + reranker; skips without the embed extra).

**Adversarial review — tenancy/liveness (complete, passed):** an agent ran real attacks against a scratch DB. The core isolation properties HELD — cross-namespace search/fetch, stale-view-after-supersede/forget, the same-record_id-across-tenants collision, and a planted "lying" view row (namespace column faked to the caller's tenant) were all defeated by the operator's records-join. Three gaps were surfaced and fixed (decisions #24–25, all with proven-discriminating regression tests): the conformance gate could not see the real query-path tenancy SQL (a hand-modified fail-open operator could register) and the compiler trusted operator output namespaces → a **compiler-side namespace backstop** now drops any record whose writer namespace ≠ the caller's, before fusion; RRF counted occurrences not distinct operators → **per-operator dedup** + `found_by` as a set of kinds; and `forget` is content-scoped within a namespace (documented as deliberate, #25). Plan step 7 (run conformance against real operators with real multi-tenant data) is now `tests/conformance/test_live_tenancy.py` (decision #26). Two more I handled: a connection leak in `Corpus.close()` (→ `registry.close()`), and the audit-trace-on-failed-search gap (recorded #27, scheduled for Milestone C — a failed search currently persists no trace).

**Adversarial review — score-contract/injection/robustness (complete):** the second agent's attacks HELD on SQL/tsquery injection, ts_rank_cd tie-determinism, ANN cosine range, sufficiency bounds, the >200-span batch seam, rerank output size, and single-operator plans. Findings fixed, each with a regression test verified to fail before the fix (decision #28): **H1** two same-titled sections silently overwriting each other via `Corpus.ingest` (real data loss — DocumentPolicy now disambiguates the CAS key by occurrence); **M2** hostile query text (NUL byte / 1MB paste) crashing `search()` (BM25 now strips NUL + caps term count); **M3** `path_glob` reporting pre-filter sufficiency (now a real `source_filter` plan step applied before sufficiency, shown in EXPLAIN); **L1** tiny budget → LIMIT 0 (floored at 1); **L2** empty query returning the whole namespace at status=ok (grep now returns empty). Defense-in-depth guards for gaps NOT reachable via the shipped path (chunker caps chunks at 4096 chars; bge never emits a degenerate vector) but invisible to the conformance gate: **H2** an oversized record wedging the engine (LexicalView caps indexed text via `left()`), **M1** NaN cosine from a zero-norm vector (ann_op drops non-finite), **M4** NaN/short cross-encoder output (reranker asserts finite + 1:1), **L3** NaN agreement (clamped). **H3** (gate certifies the score contract only on the synthetic path) is contained by the compiler's dedup + rank-fusion and now has a real-path score-contract regression in `test_milestone_b_hybrid.py`. The one unfixed item is the audit-trace-on-failed-search gap (#27), scheduled for Milestone C.

**Milestone C is DONE** — see §13. Next is **Milestone D** (task #28): point a real Claude Code/Desktop session at `datum serve` and use it (the plan's final acceptance). The **multi-format DoclingParser track (task #30)** is deliberately deferred until after retrieval was proven — retrieval is now proven, so #30 is unblocked and is a clean write-path feeder (map Docling's model → `StructuredBody`, key a new `WritePolicy` by content type; default OCR `ocrmac`).

---

## 13. Milestone C build record (eval gate + concurrency hardening) — 2026-08-11

Three sequential, one-hand work items (no fan-out — this milestone is wiring + hardening, not new subsystems). All verified by my own full-suite run: **219 tests pass** against a real Postgres.

**C1 — eval gate wired to the live Corpus.** `eval/gate.py` ingests the fixture corpus (`tests/fixtures/sample_corpus/`, filename prefix → namespace: `eng`/`hr`) into a real Corpus and runs the fixed human-curated set (`regression_set.yaml`) through the real hybrid pipeline via `corpus.search`. `datum eval [--corpus-dir --regression-set --dsn]` runs it and exits non-zero on regression; `tests/eval/test_gate_integration.py` is the pytest form (the CI gate). **Wiring the gate surfaced two real gaps** (this is the gate doing its job):
  - **Abstention (decision #29).** Adding ANN broke abstention — dense retrieval always returns nearest neighbors, so out-of-corpus queries returned `status=ok` (grep-only Milestone A abstained by accident). Sufficiency doesn't separate positives from non-matches (RRF scores are rank-based); top dense cosine does (positives ≥0.669, out-of-corpus ≤0.606 on the fixture). Added a `RuleTablePolicy` abstention floor (**0.63**, carried on `Fusion`, applied by the compiler where the raw cosine is visible, `abstain_check` in EXPLAIN). **The 0.63 is fixture-derived and uncalibrated** (0.06 gap, 11 cases / 5 docs) — honestly not the same footing as the pre-declared weights; calibration is Phase 1, and the gate's role is regression-locking, not certifying abstention. Non-vacuity proven by dropping the floor to 0.0 (exactly the 3 abstention cases then fail).
  - **Test-isolation bug (also #29).** The walking-skeleton fixture truncated `records`/`wal_entries` but not `view_cursors`, leaving a stale cursor ahead of the RESTART'd WAL → the derivation engine silently never re-derived → ANN was effectively OFF for every walking-skeleton test after the first, and its hybrid assertions passed through grep/BM25 alone. Fixture now resets view state; those tests (and the abstention test) now genuinely exercise the dense path.

**C2 — unconditional audit trace (decisions #27→#30).** The compiler's executor now persists a terminal `status="error"` EvidenceState (empty items; error type + message in `extra`) when a search raises, then re-raises — the failure is recorded, never swallowed; `explain`/`replay` work on the failed plan. `EvidenceStatus` gained an audit-only `"error"` member (compatible Literal widening).

**C3 — concurrency hardening (#19).** New `test_concurrent_asserts_to_the_same_span_in_different_namespaces_do_not_contend`: two writers racing the SAME `(source_id, stable_key)` in DIFFERENT namespaces (identical content → identical record_id) both stay live, one per namespace — proving migration 0005's namespace-scoped CAS index doesn't create false cross-tenant contention. The original same-namespace write-race test (exactly one live) still holds.

**Decisions recorded:** #29 (abstention floor + the fixture-isolation fix), #30 (audit trail implemented). **New files:** `eval/gate.py`, `tests/eval/test_gate_integration.py`. **Changed:** `policy/rule_table.py` (floor, version → 2026-08-11), `planner/compiler.py` (abstention gate + failure trace), `kernel/evidence.py` (`error` status), `cli.py` (`datum eval`), the walking-skeleton fixture, and the fusion/hybrid/groundstore test suites. No migration added.

**After Milestone C, task #30 (multi-format) was built — see §14.** The one thing left is **Milestone D**: the plan's final acceptance is a real tool-calling model (Claude Code/Desktop) pointed at `datum serve` over the fused hybrid pipeline. That is an interactive step — it needs the user to attach a real MCP client to the running server (it can't be self-driven headlessly here), so it's the natural point to hand back.

---

## 14. Multi-format ingestion build record (task #30) — 2026-08-11

Retrieval-first was the ordering, and it held: dense/BM25/ANN were proven correct on text before any format-conversion was added, so this track is a pure write-path feeder — it changed nothing about retrieval.

**What shipped:**
- `writepath/policies/docling_parser.py` — `DoclingParser`, a `Parser` that reads `DocumentInput.source_path` (extended with that field) and lazy-imports Docling. Design (decision #31): **Docling converts the file → markdown, then the existing tested `MarkdownParser` sections it** — one sectioning implementation, tables inlined as searchable text. Page/bbox is deliberately not carried at v1 (only paged formats have it, and those are blocked here — see below).
- `Corpus.ingest_file(path, principal)` + a `docling` WritePolicy registered beside `document`; `datum ingest` auto-routes by extension (`.md/.txt` → text/MarkdownParser, everything else → Docling). New `datum benchmark` CLI.
- `eval/multiformat_benchmark.py` + `tests/eval/test_multiformat.py` — generate one file per format family, ingest through its parser, retrieve its fact.

**Verified (self-run):** the benchmark passes **7/7 covered formats** end-to-end — **md, txt, html, csv, docx, pptx, xlsx** — each ingested through its parser and its fact retrieved by a semantic query through the full hybrid pipeline. A tenancy test confirms `ingest_file` records are namespace-isolated exactly like text ingest. Full suite **221 passed**.

**Environment-blocked, reported not hidden (decision #31, §11's no-silent-downscope rule):** **pdf** and **image/scanned** need Docling's layout/OCR models, which download from HuggingFace on first use — that egress is unavailable here (models not cached; HF network HEAD calls hang, the same failure that stalls the suite without `HF_HUB_OFFLINE=1`). **audio**: Whisper is cached, but there's no honest way to synthesize known-transcript speech to assert on. The DoclingParser handles all of these unchanged once the models are staged; only the benchmark's coverage is limited, and `datum benchmark` prints the skipped families with reasons. **To unblock pdf/image:** stage the Docling models into the HF cache (or point `HF_ENDPOINT` at Lilly's Artifactory `huggingfaceml` remote, HANDOFF §8's noted path), then add pdf/image cases to `eval/multiformat_benchmark.py` and the page/bbox `iterate_items()` mapping to `DoclingParser`.

**IMPORTANT operational note:** run the suite and any Docling/model work with `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` — cached models load instantly; without it, HF's cert-failing network HEAD checks retry and can hang for many minutes.
