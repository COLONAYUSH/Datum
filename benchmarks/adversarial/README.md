# Adversarial retrieval test corpora

Two synthetic documents written to break document extraction and retrieval, each with a
question-by-question answer key. All entities, organizations, and data in both documents are
fictional. These are the corpora behind the empirical results in the paper and in
`docs/decisions.md` (#34 through #41).

## The documents

**Document A** (`document-a.pdf`, 19 pages, 42 questions) — a fictional deep-sea research
station annual report. Tricks: five languages including a Hindi statement present only as an
image, merged-cell tables, a 46-row dive log spanning a page break, charts whose values exist
only in the plotted pixels, diagrams and an org chart whose labels are drawn art, a simulated
1998 scanned memo, code blocks, and four contradiction traps where two parts of the document
give different values for the same fact.

**Document B** (`document-b.pdf`, 18 pages, 44 questions) — a fictional twin-observatory
yearbook, written after all of Document A's fixes had landed, with a deliberately different
trick set: a three-column layout, table headers rotated 90 degrees inside their cells, tables
nested in table cells, Arabic and Tamil statements present only as images, a page stored with
a `/Rotate 90` flag, a color-only Gantt chart, a near-duplicate appendix page differing in one
figure, clashing date and number locales, a redacted access code (hallucination bait), an
invisible white-on-white sentence, a keyword hidden in the PDF metadata, and a degraded
one-bit fax.

## Scoring

A question passes only if a passage containing the expected answer appears in the top five
retrieved results, checked mechanically against the answer key. Contradiction-trap questions
require BOTH conflicting values to surface. Current results with this repository's defaults
(`Corpus.open(dsn, image_ocr=True)`): **Document A 40/42, Document B 44/44.** Document B's
baseline, before any fix was developed against it, was 37/44.

## Running them

```bash
createdb datum_stress && psql -d datum_stress -c "CREATE EXTENSION vector;"
python - <<'PY'
from datum.corpus import Corpus
from datum.kernel.principal import Principal
c = Corpus.open("postgresql://localhost/datum_stress", image_ocr=True)
c.ingest_file("benchmarks/adversarial/document-a.pdf",
              Principal(id="ing", namespace="tenant:stress"), source_id="document-a.pdf")
ev = c.search("For dive D-2025-018, state the pilot, max depth, duration and samples taken.",
              principal=Principal(id="q", namespace="tenant:stress"))
for h in ev.hits[:3]:
    print(h.section_path, h.content[:80])
c.close()
PY
```

Ingest of either document takes several minutes on CPU: the image-OCR pass renders pages at
288 dpi and runs up to three OCR engines plus a translation model over image regions. The
macOS-specific pieces (Apple Vision OCR) degrade loudly, never silently, on other platforms.
