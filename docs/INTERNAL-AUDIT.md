# Internal audit: what we have not proven

**Status:** standing internal document, last updated 2026-08-17.

This is the internal accounting behind the paper's claims. It began life as the paper's own
"What we have not proven" section and was moved here so the paper stays reader-facing while the
full ledger keeps living next to the code. Update this file whenever a claim in the paper, the
README, or a benchmark result changes. Read it together with `docs/decisions.md` (the numbered
architecture decisions) and `LEARNING.md` (the process lessons). Nothing in here is secret; it is
the same honesty, kept where the maintainers work.

The system exists and the paper reports real measurements, so this accounting is about what the
measurements do and do not cover, which is a different and longer list than we expected.

## Test provenance and independence

The two adversarial test documents were written by us. They were written to be hostile, and the
second was scored before any fix was developed against it, but an adversary who knows what a
system's authors consider hard is not the same as an independent one. The right next step is a
test document written by someone else, with an answer key we never see until after the run. Not
done yet. The framework head-to-head (paper Table 3) softens this only partly: the competitors
faced the same documents zero-shot, but the documents still came from us.

## Environment specificity

Everything ran on one machine, one operating system, and one set of locally runnable models. The
OCR findings (paper Section 6.3), in particular Apple Vision's ordered-language-list behavior,
are findings about specific engines on specific hardware. A deployment on different
infrastructure must re-verify them rather than trust them. Two of the twenty writing scripts,
Gujarati and Myanmar, read back only weakly with the best engine available to us; they ship as
best-effort, not verified.

## Benchmark coverage and scale

The public benchmark result covers one task from one suite. SciFact is real and independently
maintained, and 300 queries is a real test, but MIRACL, LIMIT, BRIGHT, and any benchmark centered
on unanswerable questions remain unrun, and a system can look different across tasks. The
5,183-document SciFact corpus is the largest thing this system has ever held. Nothing measured
says anything about millions of documents, concurrent writers, or multi-machine deployments, and
the single-writer-per-tenant simplification (decisions.md #14) has never been stressed by real
contention.

## Open failures, named exactly

Two failures from the test documents remain open:

1. **Document A, contradiction trap:** one trap's second value sits at rank five, one position
   outside the five-result scoring cut. A trade accepted knowingly for two cross-language wins
   (decisions.md #39); not re-tuned away on purpose.
2. **Document A, French passage:** effectively unreachable because Docling merges four language
   sections into one run-on block attributed to the wrong heading. The safe fix is recovering
   headings from Docling's layout signals; the regex patch we built was rejected as too likely to
   corrupt correct documents (decisions.md #38).

## Rank-boundary variance

Exact counts near the cutoff carry one rank of noise. A question whose deciding passage sits
fifth can sit sixth after an index rebuild, because pgvector's HNSW construction is stochastic.
This is why Document B appears as 44 of 44 in the paper's Section 6.3 (committed corpus) and
43 of 44 in the Section 6.5 comparison (fresh same-day ingest). Both runs are reported as
measured. The matching SciFact noise band is about ±0.003 nDCG (decisions.md #45). Rule: never
read a one-rank or ±0.003 movement as a real improvement or regression, and always compare
systems on same-day fresh runs.

## Mechanisms without real inputs

The feedback loop and the vision-model interface are tested mechanisms without their real inputs.
The loop's calibration has run only on judgments we generated during testing, never on organic
traffic; the with-and-without comparison that would justify it remains ahead. The vision
interface has only ever hosted models too weak to use (decisions.md #43), so its value is an
argument about the socket, not a measurement of what flows through it.

## Novelty ledger: ours versus adapted

Checked claim by claim, only one idea originally described as novel held up with no real
precedent found: one shared set of write rules for both documents and an agent's own memory. Two
other ideas are existing techniques from other fields, applied correctly here but not invented
here. The remaining claims are more standard architecture than first described, with a narrower,
real contribution inside a familiar shape. The build added one more entry: the context-prefixed
indexing that closed Document B's last gap is our variant of Anthropic's 2024 contextual
retrieval technique, cheaper here because the write path already preserves the context worth
prefixing, but not our idea. The closest academic relatives to the central request/plan split are
LOTUS and Palimpzest, credited by name in the paper.

## Research gaps we caught late

- Our survey initially missed the academic line on query planners over mixed structured and
  unstructured data, the closest relative to the central idea. Found during our own review,
  credited once found.
- The first internal version of the design was roughly twice what a small team could build in a
  normal amount of time. It was cut to the buildable first version, with the ambitious pieces
  moved to a clearly separate later phase. Anyone judging buildability should judge the smaller
  version.
- When the design was graded mechanism by mechanism against the 27 surveyed problems, five
  claims were graded more generously than the mechanism supported; all five were corrected. Two
  problems never got an independent adversarial check at all.

## Standing assumptions the paper cannot resolve

- **Identity is upstream.** Whether callers are who they claim to be is handled outside Datum;
  everything here depends on that being done correctly somewhere else.
- **Crypto-shred soundness.** Truly-unrecoverable deletion depends on the soundness of the
  key-management system that destroys the key, and no one whose job is breaking such systems has
  reviewed ours.
- **Trust-tier smuggling.** The authority-tier mechanism makes untrustworthy information harder
  to smuggle into fact-position; it does not fully close every path. Honest to draw, easy to
  blur.

---

We keep this list not to undercut the work, but because a design checked hard enough to find its
own weak points is more trustworthy than one that has not been checked at all.
