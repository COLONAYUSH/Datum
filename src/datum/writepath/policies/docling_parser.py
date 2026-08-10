"""DoclingParser: the multi-format `Parser` (L3), lazy-importing Docling.

Where `MarkdownParser` reads `DocumentInput.text` and only understands
markdown, this parser reads `DocumentInput.source_path` and understands every
format Docling does — docx/pptx/xlsx, html, csv, pdf, images, epub, audio, the
XML dialects. It is the format-coverage feeder task #30 calls for, and it is a
drop-in `Parser`: `DocumentPolicy` consumes it exactly like the markdown one,
so nothing downstream (chunking, CAS, retrieval) changes shape per format.

**Design (decisions.md #31): Docling converts the file to markdown, then the
existing `MarkdownParser` sections that markdown.** Docling's strength is
turning any format into clean structured markdown (headings, lists, tables as
pipe-tables); the markdown parser's job is turning markdown into
section-path-keyed `ParsedSection`s, and it is already tested for exactly that.
Composing them means one sectioning implementation, not a second one that
could drift, and tables arrive as inlined markdown text (searchable) under
their heading. The honest v1 limit this draws: structural provenance is the
heading-derived `section_path`; per-item PAGE and BBOX are NOT carried, because
`export_to_markdown` does not preserve them and the only formats that HAVE
pages (pdf, scanned images) need Docling's layout models — which route through
a separate, currently unstaged download path. Page/bbox mapping via
`iterate_items()` is the Phase-1 enrichment that lands with the PDF/image
pipeline, tested against the formats that actually carry it.

Lazy import: Docling (and its torch/layout stack) is the `datum[parse]` extra,
imported inside `parse()` on first use, never at module import — the core
write path and the markdown ingest path cost nothing for it.
"""

from __future__ import annotations

from datum.writepath.policies.document import DocumentInput, MarkdownParser, ParsedSection

# Bumped in lockstep with the installed docling; part of the record's
# source_version lineage (the CI-07 tuple), so a docling upgrade that changes
# extraction is a detectable producer change, not a silent re-parse.
_DOCLING_VERSION = "2.118.1"


class DoclingParser:
    """Converts a file at `DocumentInput.source_path` to markdown via Docling,
    then delegates sectioning to `MarkdownParser`. Requires `source_path`;
    a DoclingParser fed a text-only DocumentInput is a caller error (route
    plain text/markdown through MarkdownParser instead).
    """

    version = f"docling-{_DOCLING_VERSION}/md-sections"

    def __init__(self) -> None:
        self._converter = None  # lazy: built on first parse()
        self._markdown = MarkdownParser()

    def _convert(self, source_path: str) -> str:
        if self._converter is None:
            from docling.document_converter import DocumentConverter  # lazy: datum[parse]

            self._converter = DocumentConverter()
        result = self._converter.convert(source_path)
        return result.document.export_to_markdown()

    def parse(self, raw: DocumentInput) -> list[ParsedSection]:
        if not raw.source_path:
            raise ValueError(
                "DoclingParser needs DocumentInput.source_path (a file to convert); "
                "route plain text through MarkdownParser instead."
            )
        markdown = self._convert(raw.source_path)
        # Reuse the markdown sectioner on Docling's output, keyed by the same
        # source_id so section paths match the text-ingest convention.
        as_markdown = DocumentInput(
            source_id=raw.source_id,
            policy_id=raw.policy_id,
            text=markdown,
            content_type="text/markdown",
            observed_at=raw.observed_at,
        )
        return self._markdown.parse(as_markdown)
