"""DocumentPolicy: v1's only WritePolicy (L3).

Turns a document upload into a list of WriteOps, one per chunk-span, deciding
assert-vs-supersede per span by consulting the ground store's find_span —
exactly the shape FRAMEWORK.md's own DocumentPolicy sketch shows. The parser
is pluggable behind a small `Parser` Protocol; v1 ships a dependency-free
plain-text/markdown parser so the walking skeleton runs with zero ML
dependencies. Docling (for PDFs) is an opt-in parser injected the same way,
lazy-imported only when used (per pyproject's `parse` extra) — it is not
imported here.

Span identity (the CAS key, decisions.md #17): `stable_key` is the chunk's
POSITION, not its content — `<section-path>#<ordinal-in-section>` — so
re-ingesting an edited document supersedes the changed span rather than
duplicating it. Known v1 limitation, stated plainly: inserting content early
in a section shifts later ordinals, so downstream spans in that section look
superseded even if their text is unchanged. Content-stable chunk identity
under arbitrary edits is a genuinely hard problem; the positional key is the
honest v1 choice and is documented as such rather than presented as more than
it is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from datum.derivation.chunking import chunk_table_aware
from datum.groundstore.store import GroundStore
from datum.kernel.ids import PolicyID
from datum.kernel.principal import Principal
from datum.kernel.record import ProvenanceCapsule, StructuredBody
from datum.kernel.writeop import WriteOp

_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class DocumentInput:
    """What DocumentPolicy.ingest receives (a concrete RawInput). Carries the
    source identity, the governing policy, the raw text, and when the content
    was observed — everything the write path needs, nothing it doesn't.
    """

    source_id: str
    policy_id: PolicyID
    text: str
    content_type: str = "text/markdown"
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # A filesystem path to the source, set for binary/rich formats a text
    # parser cannot read (docx, pptx, xlsx, pdf, ...). The dependency-free
    # MarkdownParser reads `text`; the DoclingParser reads `source_path` and
    # ignores `text`. Exactly one is the real input for a given ingest.
    source_path: str | None = None


@dataclass(frozen=True)
class ParsedSection:
    section_path: tuple[str, ...]
    text: str


class Parser(Protocol):
    version: str

    def parse(self, raw: DocumentInput) -> list[ParsedSection]: ...


class MarkdownParser:
    """Dependency-free parser: splits a document into sections at ATX (`#`)
    headings, maintaining a heading path stack, and returns one ParsedSection
    per heading's body (plus a leading pre-heading section if the doc opens
    with body text). Plain text with no headings is one section keyed by the
    source id. No table/structural-region extraction yet — the chunker
    supports protected regions (decisions.md #15), but this v1 parser emits
    none; that is a Phase 1 enrichment, flagged here rather than faked.

    ATX detection is SUSPENDED inside fenced code blocks (``` or ~~~). A
    document with code sketches — FRAMEWORK.md's Python blocks are the case
    that surfaced this — is full of `# comment` lines that are NOT headings;
    treating them as headings shattered `section_path` into sentence-fragment
    "sections" and mis-anchored every citation drawn from those spans
    (section_path is the load-bearing provenance the surface promises). Found
    by real MCP use over real docs; decisions.md #33.
    """

    version = "markdown-v2"

    def parse(self, raw: DocumentInput) -> list[ParsedSection]:
        sections: list[ParsedSection] = []
        path_stack: list[str] = [raw.source_id]
        buf: list[str] = []
        current_path: tuple[str, ...] = (raw.source_id,)
        fence_char = ""  # "" outside a code fence; "`" or "~" while inside one

        def flush() -> None:
            text = "\n".join(buf).strip()
            if text:
                sections.append(ParsedSection(section_path=current_path, text=text))
            buf.clear()

        for line in raw.text.splitlines():
            stripped = line.lstrip()
            # A run of >=3 backticks or tildes toggles fenced-code state (a
            # closing fence must repeat the opener's char). Fence lines and
            # everything between them are body text, never heading candidates.
            if stripped[:3] in ("```", "~~~"):
                marker = stripped[0]
                if not fence_char:
                    fence_char = marker
                elif marker == fence_char:
                    fence_char = ""
                buf.append(line)
                continue
            if fence_char:
                buf.append(line)
                continue
            m = _ATX_HEADING.match(line)
            if m is None:
                buf.append(line)
                continue
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            # Rebuild the path stack to this heading's depth (level 1 == just
            # under the doc root). Truncate deeper entries, then append.
            path_stack = path_stack[:level] + [title]
            current_path = tuple(path_stack)
        flush()

        if not sections:  # e.g. empty or whitespace-only document
            return []
        return sections


class DocumentPolicy:
    name = "document-v1"
    version = "1.0"

    def __init__(self, store: GroundStore, parser: Parser | None = None) -> None:
        self._store = store
        self._parser = parser or MarkdownParser()

    def ingest(self, raw: DocumentInput, principal: Principal) -> list[WriteOp]:
        provenance = ProvenanceCapsule(
            writer=principal,
            ingestion_path=f"document:{raw.content_type}",
            # A document's text is what the source says; the writer vouches
            # for having ingested it, not for its authority — UNVERIFIED is
            # the honest default (a registry upgrades it later). trust_class
            # is "trusted" because this is ingested source content, not an
            # agent-inferred write (which would be "untrusted").
            authority_tier="UNVERIFIED",
            trust_class="trusted",
            source_version=self._parser.version,
        )
        ops: list[WriteOp] = []
        seen_prefixes: dict[str, int] = {}
        for section in self._parser.parse(raw):
            base_body = StructuredBody(text=section.text, section_path=section.section_path)
            # Table-aware: a section with no pipe-table chunks byte-identically
            # to the plain FastCDC path (chunk_table_aware delegates to it); a
            # section WITH a large table gets header-carrying row-group chunks
            # so a specific row stays retrievable (decisions.md #37).
            chunks = chunk_table_aware(base_body)
            path_key = "/".join(section.section_path)
            # A section_path that repeats within ONE document (e.g. two `#
            # Notes` headings, or repeated deeper sub-headings) would otherwise
            # produce a colliding stable_key, and the CAS invariant would make
            # the second section silently SUPERSEDE the first — real data loss
            # through the primary ingest API (review finding H1). Disambiguate
            # the CAS key by occurrence: the first keeps the bare key so an
            # already-ingested corpus re-keys identically (no spurious
            # supersedes on re-ingest), repeats get a positional suffix. Only
            # the internal stable_key changes; section_path — the provenance a
            # caller SEES — is untouched, so both sections still trace to their
            # real heading.
            occurrence = seen_prefixes.get(path_key, 0)
            seen_prefixes[path_key] = occurrence + 1
            key_prefix = path_key if occurrence == 0 else f"{path_key}@{occurrence}"
            for ordinal, chunk in enumerate(chunks):
                stable_key = f"{key_prefix}#{ordinal}"
                prior = self._store.find_span(
                    raw.source_id, stable_key, namespace=principal.namespace
                )
                if prior is None:
                    ops.append(
                        WriteOp.assert_(
                            body=chunk,
                            valid_from=raw.observed_at,
                            provenance=provenance,
                            policy_id=raw.policy_id,
                            source_id=raw.source_id,
                            stable_key=stable_key,
                        )
                    )
                    continue
                # A live version of this span already exists. If the content is
                # identical the assert path will no-op (record_id matches); if
                # it changed, supersede the prior version explicitly.
                from datum.groundstore.store import compute_record_id

                if compute_record_id(chunk, "chunk") == prior.id:
                    continue  # unchanged span, nothing to write
                ops.append(
                    WriteOp.supersede(
                        old_id=prior.id,
                        body=chunk,
                        valid_from=raw.observed_at,
                        provenance=provenance,
                        source_id=raw.source_id,
                        stable_key=stable_key,
                    )
                )
        return ops
