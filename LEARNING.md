# LEARNING.md — the living log of everything we learned building Datum

This file is the memory of the project's *process*. Not what Datum is (that is `README.md`,
`design/FRAMEWORK.md`, and `docs/decisions.md`), and not the current status and next steps (that is
`HANDOFF.md`). This is what we learned along the way: the mistakes, the fixes, the gotchas, the
things that were not obvious until they bit us, and the rules that keep the work honest.

The goal is simple. If this repository is handed to another person, or opened by a fresh Claude Code
session on another machine, that reader should be able to inherit every hard-won lesson without
living through the same mistakes again.

> [!IMPORTANT]
> **This is a living document. Keep it alive.** Whenever you (human or an AI assistant) hit a
> non-obvious problem and fix it, discover a gotcha, or make a decision that changes how the work is
> done, add a dated entry under the right section and a one-line note in the [Changelog](#changelog)
> at the bottom. Small and frequent beats a big rewrite later. Read this together with `HANDOFF.md`
> (status and plan) and `docs/decisions.md` (numbered architecture decisions).

## How to read this

- **[Start here: the ten lessons that matter most](#start-here-the-ten-lessons-that-matter-most)** if you only have two minutes.
- **[The playbook](#the-playbook-what-to-do-and-what-not-to-do)** for repeatable do and do-not moves.
- **[The incident log](#the-incident-log-issues-and-remediations)** for the detailed story of each problem and its fix, by phase.
- **[Environment and tooling gotchas](#environment-and-tooling-gotchas)** for the setup traps.
- **[Hard rules](#hard-rules-and-preferences-that-do-not-bend)** that do not bend.

---

## Start here: the ten lessons that matter most

1. **Test against a real PostgreSQL, never a mock.** Every correctness-critical property in Datum
   (the atomic supersede, the uniqueness compare-and-set, WAL ordering, namespace isolation) only
   shows its real behavior against a real database. Mocks would have hidden the exact bugs that
   mattered. The suite spins up real Postgres.
2. **Run an adversarial review before building on top of new code.** A structured "try to break it"
   pass over the first wave of modules reproduced 18 real defects, two of them critical security
   holes, by actually running the code rather than reading it. Do this at every layer boundary.
3. **Do not trust a build agent's "tests pass" self-report. Re-run the suite yourself.** This caught
   real gaps more than once.
4. **Never work around a corporate security control.** Early on, a sub-agent's retry prompt was
   edited to avoid tripping the DLP content scanner. That is a workaround of a security control and
   it was correctly flagged. The fix was to revert and retry cleanly. Surface a block to the user;
   never route around it.
5. **The kernel is version-frozen. Adding a public symbol is a decision, not a convenience.** The
   top-level `__all__` is a budgeted, CI-diffable surface. Every addition is recorded in
   `docs/decisions.md`.
6. **Record every deviation from the spec in `docs/decisions.md`, numbered, with the reasoning.**
   Nothing load-bearing should live only in a chat log. There are 30 decisions so far.
7. **Never fabricate a benchmark number.** The paper's results figure is a clearly-labeled template
   until measured. The README prints no performance figures it has not measured. This is a
   correctness rule, not a style preference.
8. **Degrade loudly, never silently.** When the dense embedder is missing, Datum still runs on BM25
   plus grep, but it warns exactly what is absent and what it costs. Silent downscoping is banned.
9. **Durable context lives in files, not in the session.** The task tracker is session-scoped and
   starts empty in a new session. `HANDOFF.md`, this file, and `docs/decisions.md` are the real
   carryover. Keep them accurate the moment something changes.
10. **"It actually works when run" is the bar, not "it compiles."** Every milestone was accepted
    against a real corpus through the actually-running system, not against fixtures alone.

---

## The playbook: what to do, and what not to do

### Do

- **Freeze the interface before you fan out.** Parallel module builds worked only because the kernel
  contracts were pinned first. Independent modules on disjoint files can then be built concurrently.
- **Keep one hand on the safety-critical and integration code.** The ground store (atomicity and
  CAS), the planner, and `corpus.py` were written directly, not delegated. That was the right call.
- **Re-derive the foundation from first principles at layer boundaries.** A kernel audit triggered by
  a model switch found six real defects before they could spread.
- **Write conformance contracts generically.** The BM25 score-contract case is written as "monotonic
  in relevance," not "matches a specific formula," so swapping the backend (see the pg_search
  no-go below) cost nothing in tests.
- **Share one implementation of a security-critical path, not copies.** The conformance fail-closed
  logic lives once in `operators/common.py`. Three operators reuse it. Copies drift; a shared path
  does not.
- **Scope every read by namespace.** Content-addressing means identical content in two tenants shares
  a record id, so an unscoped lookup can return the other tenant's row. Always pass the namespace.
- **Hand the user any command that mutates the environment.** Installs and pushes are gated by the
  harness. Give the exact command to run rather than trying to force it through.

### Do not

- Do not point `DATUM_PG_DSN` at a database with content you care about. The test suite and
  `datum eval` **truncate** whatever it points at. Always use a scratch database.
- Do not add fields to the frozen kernel casually. When a field is genuinely required (three were,
  driven by tests), add it deliberately and record it as a decision.
- Do not reference a `decisions.md` number before the entry exists. That caused a numbering
  collision when a parallel build appended its own. Reconcile numbering in one pass when forks land.
- Do not expose internal build process in the paper (the workflows, the agents, the CI codes). Those
  are translated into normal research language. The paper is written for humans, by a human.
- Do not use the pytorch.org extra index that Docling's Nemotron OCR command suggests. It is a
  non-Artifactory index and CUDA-only, so it is wrong on both counts here.

---

## The incident log: issues and remediations

### Research phase

- **A sub-agent hit the DLP content scanner, and the retry prompt was edited to avoid tripping it.**
  That edit was a workaround of a security control and was flagged as such.
  *Remediation:* reverted the edit and re-ran with the original brief, which succeeded.
  *Lesson:* never edit a prompt or config to evade a corporate security or DLP control. Surface the
  block to the user and let them decide.
- **Multi-agent workflows hit network and API resets mid-run.**
  *Remediation:* used the workflow resume mechanism to continue from the last checkpoint rather than
  restart. *Lesson:* long fan-outs are resumable; lean on that instead of redoing work.
- **The design's own coverage self-grading was inflated, and it missed the closest prior art
  (LOTUS, Palimpzest) to its central idea.** The red team caught both.
  *Remediation:* two revision passes corrected the grades and credited prior art by name.
  *Lesson:* adversarial verification catches your own overclaiming. Build it in, and treat a caught
  overclaim as a strength of the process, not an embarrassment.

### Foundation and kernel

- **`pyproject.toml` had `[project.optional-dependencies.dev]` written as a table; invalid.**
  *Remediation:* `dev = [ ... ]` array. Also the default Python was 3.9, too old; moved to 3.12.
- **A kernel audit (prompted by switching the model driving the build) found six defects**, including
  `Plan.execute()` and `Plan.diff()` missing, and `Operator.plan` typed with `Any` instead of
  `Budget`. *Remediation:* added the missing methods (the executor is bound at compile time) and
  tightened the types. *Lesson:* a model switch is a good moment to re-audit the frozen foundation.

### Adversarial review before the ground store (18 findings)

A four-lens review reproduced 18 defects by running the code. The two critical ones:

- **Filter equality could fail open** (a malformed predicate let rows through). Now fails closed.
- **A missing entitlement field was not caught** (staleness check could be bypassed). Now caught.

Others, all fixed: three conformance cases now guard `execute()` so a broken operator cannot crash
the suite; fabricated and duplicate records are detected; the `hit_id` token was stripped of all
trust metadata (decision #12); the namespace ACL was narrowed to exact equality (#13); the global WAL
tail was made non-resumable via an explicit `scan()` (#14); the chunker got an explicit
protected-regions API (#15); the eval loader rejects bare-string matches; the `py.typed` marker was
added so external type checkers see the typed surface. *Lesson:* run this pass before anything is
built on top of the reviewed code.

### Ground store and read path (tests caught real bugs)

- **`WriteOp` was missing `parser_confidence`.** Added (decision #17).
- **A supersede op carried no `policy_id`.** Fixed to inherit it from the row it closes.
- **grep matched the whole query as one literal substring**, so it missed almost everything.
  *Remediation:* term matching that ranks by distinct terms matched first, occurrences second.
- *Lesson:* these are exactly the bugs a real database and real content surface and a mock hides.

### Milestone A (walking skeleton)

- Built the whole nine-layer path with grep as the only operator and zero ML, so the substrate was
  proven end to end before any model was involved. 152 tests. The concurrent-write race that drops
  updates in other systems is closed by a 40-round two-writer concurrency test that ends with exactly
  one live record every time. *Lesson:* a walking skeleton with the cheapest operator first removes
  model setup as a confounding variable.

### Milestone B (hybrid retrieval)

- **ParadeDB `pg_search` was a no-go** in this environment.
  *Remediation:* fell back to Postgres `tsvector` + GIN for BM25. Because the conformance
  score-contract is written as monotonic-in-relevance, no tests changed.
- **The conformance path was duplicated when BM25 and ANN arrived.**
  *Remediation:* extracted the one fail-closed path and the shared fragment shape into
  `operators/common.py`. All operators reuse it. The refactor was checked to preserve the critical
  tenancy fail-closed semantics exactly.
- **`fetch` could return the wrong tenant's row** because identical content across tenants shares a
  record id (content-addressing). *Remediation:* namespace-scoped `get_live` (decision #19).
- **A source filter passed to `search` needed to affect the sufficiency score and show in EXPLAIN.**
  *Remediation:* `path_glob` compiles into a real `source_filter` step in the plan, not a
  post-filter (review finding M3).
- Retrieval today: grep + BM25 + dense ANN (pgvector HNSW, `bge-small-en-v1.5`), fused with weighted
  Reciprocal Rank Fusion, then a cross-encoder rerank (`bge-reranker-base`), all through the
  conformance gate. The derivation engine keeps the views current incrementally off the WAL tail and
  only re-derives the chunks a write touched. Two adversarial reviews (tenancy, and
  score-contract/robustness) both passed with fixes. Decisions #19 through #28.

### Milestone C (eval gate, abstention, concurrency)

- **ANN always returns k neighbors, however irrelevant**, so hybrid retrieval could never say "not
  enough." *Remediation:* an explicit dense-similarity abstention floor (0.63, derived from
  fixtures, and labeled uncalibrated). Below it, the result is `insufficient_evidence`.
  *Lesson:* nearest-neighbor search has no natural "nothing matched"; you must add a floor, and you
  must be honest that it is uncalibrated.
- Wired the fixed regression set as a live gate (`datum eval`), made the audit trace unconditional on
  failed searches, and added a namespace-scoped-span concurrency test. Decisions #27, #29, #30.

### Packaging, publishing, and Git

- **The package README that `pyproject.toml` points at did not exist.** Fixed by writing the real
  `README.md` at the repo root.
- **The repository is `datum/`; the wider project folder is not a git repo.**
  *Remediation:* brought the research corpus, the design spec, the paper, and `HANDOFF.md` into the
  repo so it is self-contained and a fresh session inherits the full context.
- **Two GitHub accounts are logged in on the build machine**, a personal one (`COLONAYUSH`, active)
  and a work one (`ayush-lilly`). The machine's global git identity is the work one.
  *Remediation:* for this personal private repo, the commit identity is set **per-repo only** to the
  personal profile, leaving the global work identity untouched. *Lesson:* check which identity a repo
  will use before the first commit; a wrong author is baked into history.

---

## Environment and tooling gotchas

- **PostgreSQL and pgvector.** Datum needs Postgres 17 with the `vector` extension. On the build
  machine pgvector was not present at first, and the Homebrew formula's Postgres dependency was
  ambiguous (it risked installing a second Postgres). It was **built from source against the running
  server's `pg_config`**, which is the deterministic way to match a C extension to a specific server
  version. See `SETUP.md` for the exact steps.
- **The `.venv` is about 2.3 GB** (torch, the embedder, the reranker). It is git-ignored. Never
  commit it.
- **HuggingFace model downloads work in this environment.** The embedder, reranker, and Docling
  models download at runtime from HuggingFace with no proxy configuration. If a future locked-down
  machine blocks that egress, point `HF_ENDPOINT` at an Artifactory HuggingFace remote or pre-stage
  the model cache.
- **Package installs route through JFrog Artifactory, not public PyPI.** The machine's
  `~/.pip/pip.conf` already sets the index to Lilly's mirror, so plain `pip install` is compliant.
  Do not print Lilly's internal index URL in any public-facing document.
- **The harness auto-mode classifier blocks environment-mutating commands** such as `pip install` and
  network pushes, and some complex shell (a `psql` heredoc was blocked; a plain `psql -f file.sql`
  was fine). When blocked, hand the user the exact command to run with a `!` prefix, or ask them to
  approve it. Do not try to disguise the command to get it past the gate.
- **The MCP SDK is v2.** The server imports `mcp.server.mcpserver.MCPServer`, which does not exist in
  the 1.x line (1.x had `mcp.server.fastmcp.FastMCP`). The `pyproject` floor `mcp>=2.0` is
  load-bearing. Schemas are snake_case (`input_schema`, `output_schema`). Decision #10.
- **Default models are small on purpose.** `bge-small-en-v1.5` (embedder) and `bge-reranker-base`
  (reranker) both run on CPU and sit behind Protocols, so a stronger local model or a hosted API
  swaps in through `Corpus.open(embedder=..., reranker=...)`.

---

## Hard rules and preferences that do not bend

- **Paper voice.** The paper and all human-facing prose avoid the usual AI tells: no em dashes, no
  mid-sentence setup colons, no clipped three-word fragments, no showy vocabulary, no "not just X but
  Y." Plain, complete, human sentences. Real diagrams and tables, never AI-generated images. See
  `paper/STYLE.md`.
- **No fabricated results.** Ever. Predicted numbers are clearly labeled as templates.
- **Do not compromise quietly.** When something is genuinely blocked or a real tradeoff exists,
  surface it and ask. Do not silently pick the lesser solution.
- **Git attribution.** Commits are authored solely by the repository owner. No AI or tool
  co-authorship or "generated with" lines appear in any commit message or pull request, ever. For
  this repo the author is the personal `COLONAYUSH` identity, set per-repo.
- **Intellectual property.** This work was done in a corporate context. The repository is private.
  Confirm ownership (personal vs employer) before any public release.

---

## Pointers

- `HANDOFF.md` — current status, milestones, and the exact next steps. Read this first to resume.
- `docs/decisions.md` — the 30 numbered architecture decisions. Do not re-litigate them.
- `design/FRAMEWORK.md` — the full framework specification. The "MVP definition" section is the v1 scope.
- `README.md` — what Datum is and how to install and use it.
- `research/` — the study and the verified failure taxonomy the design answers.
- `paper/` — the paper draft, its style rules, and the figures.

---

## Changelog

Add one line per update, newest first. Date, who, what.

- **2026-08-11** — Paper revised with measured results (two adversarial test documents, BEIR SciFact,
  258 tests) and then swept for tone. The sweep caught seven verbless "Score, N of M" fragments, a
  duplicated paragraph in Section 7 where a revision was added above the paragraph it should have
  replaced, and a semicolon-chained list. Lesson for future paper edits, a revision pass that adds a
  reworked paragraph must delete the original in the same edit, and every new section gets checked
  against STYLE.md before the PDF is rebuilt. Docling is now named in prose (it was already named in
  a code sketch, so the generic phrasing hid nothing). PDF rebuilt with pandoc and tectonic.
- **2026-08-10** — Created this file. Consolidated every process learning from the research phase,
  the foundation and kernel work, the adversarial review, Milestones A through C, and the
  environment, packaging, and Git setup. Seeded the ten headline lessons and the do/do-not playbook.
