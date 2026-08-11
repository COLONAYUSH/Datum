"""Table-aware chunking (decisions.md #37).

The load-bearing guarantees: (1) a body with NO table chunks byte-identically
to the plain FastCDC path — so no existing document regresses; (2) a large
markdown table becomes header-carrying row-groups so a specific row stays a
small, self-describing, retrievable chunk (the Q07 fix). Pure/deterministic —
no OCR, embedder, or DB.
"""

from __future__ import annotations

from datum.derivation.chunking import chunk_structured_body, chunk_table_aware
from datum.kernel.record import StructuredBody


def _table(n_rows: int) -> str:
    header = "| Dive ID | Date | Pilot | Max depth (m) | Duration | Samples |"
    sep = "|---------|------|-------|---------------|----------|---------|"
    rows = [
        f"| D-2025-{i:03d} | 15 Apr | L. Fernandez | {5000 + i} | 6:42 | {i % 10} |"
        for i in range(n_rows)
    ]
    return "\n".join([header, sep, *rows])


def test_prose_only_is_byte_identical_to_cdc():
    # A long, table-free body must chunk exactly as the tested FastCDC core —
    # this is what makes the change strictly additive.
    prose = ("The Meridian Trench consortium operates HALCYON DEEP. " * 200).strip()
    body = StructuredBody(text=prose, section_path=("doc", "s"))
    got = chunk_table_aware(body)
    want = chunk_structured_body(body, [])
    assert [(c.text, c.span.start, c.span.end) for c in got] == [
        (c.text, c.span.start, c.span.end) for c in want
    ]
    assert len(got) > 1  # the prose is long enough to actually exercise CDC


def test_large_table_splits_into_header_carrying_row_groups():
    body = StructuredBody(text=_table(30), section_path=("doc", "Dive log"))
    chunks = chunk_table_aware(body, min_size=64, avg_size=256, max_size=512)
    assert len(chunks) > 1, "a 30-row table should split into multiple groups"

    header_marker = "| Dive ID | Date | Pilot |"
    for c in chunks:
        # every group re-carries the header + separator (the column-name words
        # a query uses) and the separator row.
        assert header_marker in c.text
        assert "|---------|" in c.text

    # No data row is lost or duplicated across the groups.
    all_ids = [f"D-2025-{i:03d}" for i in range(30)]
    for did in all_ids:
        hits = [c for c in chunks if did in c.text]
        assert len(hits) == 1, f"{did} should appear in exactly one group, found {len(hits)}"

    # The specific-row fix: the chunk holding D-2025-018 also carries the
    # column names, so a "pilot / max depth / duration" query can match it.
    target = next(c for c in chunks if "D-2025-018" in c.text)
    assert "Pilot" in target.text and "Max depth" in target.text and "Duration" in target.text


def test_small_table_stays_a_single_chunk():
    body = StructuredBody(text=_table(3), section_path=("doc", "tiny"))
    chunks = chunk_table_aware(body)
    assert len(chunks) == 1
    for i in range(3):
        assert f"D-2025-{i:03d}" in chunks[0].text


def test_prose_around_a_table_is_preserved_and_separate():
    intro = "Table 3-1 below is the complete FY2025 dive log. " * 3
    outro = "Seven sorties closed out the year, biased toward recovery. " * 3
    body = StructuredBody(
        text=intro + "\n" + _table(20) + "\n" + outro, section_path=("doc", "Dive log")
    )
    chunks = chunk_table_aware(body, min_size=64, avg_size=256, max_size=512)
    joined = "\n".join(c.text for c in chunks)
    assert "complete FY2025 dive log" in joined  # intro prose survived
    assert "Seven sorties closed out" in joined  # outro prose survived
    # the prose chunks are NOT table groups (no header), the table groups are.
    prose_chunks = [c for c in chunks if "| Dive ID |" not in c.text]
    table_chunks = [c for c in chunks if "| Dive ID |" in c.text]
    assert prose_chunks and table_chunks


def test_pipe_bearing_prose_is_not_treated_as_a_table():
    # A line with pipes but no separator row underneath is prose, not a table,
    # so it must NOT be row-grouped (goes through CDC untouched).
    body = StructuredBody(
        text="Use the command `a | b | c` to pipe output between stages here.",
        section_path=("doc", "s"),
    )
    got = chunk_table_aware(body)
    want = chunk_structured_body(body, [])
    assert [c.text for c in got] == [c.text for c in want]
