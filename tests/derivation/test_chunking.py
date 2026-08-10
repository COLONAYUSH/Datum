"""Tests for L4's boundary-constrained content-defined chunking.

No external service needed -- pure in-memory bytes/text, so these always
run. Test data is built with `random.Random(seed)` (never `os.urandom`):
every test here makes a determinism claim somewhere, and a reproducible
generator is what lets a failure be reproduced by re-running the file.
"""

from __future__ import annotations

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from datum.derivation.chunking import (
    _build_gear_table,
    _GEAR,
    cdc_boundaries,
    chunk_structured_body,
)
from datum.kernel.record import BoundingBox, Span, StructuredBody, TableCell


def _pseudo_bytes(seed: int, n: int) -> bytes:
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(n))


def _pseudo_ascii_text(seed: int, n_chars: int) -> str:
    """Printable-ASCII text (so char offset == byte offset), for tests that
    reason about offsets directly without a UTF-8 conversion in the way.
    """
    rng = random.Random(seed)
    alphabet = "abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ .,\n"
    return "".join(rng.choice(alphabet) for _ in range(n_chars))


def _chunk_bytes(data: bytes, boundaries: list[int]) -> list[bytes]:
    out = []
    prev = 0
    for b in boundaries:
        out.append(data[prev:b])
        prev = b
    return out


def _fixed_size_boundaries(n: int, window: int) -> list[int]:
    """A naive fixed-size chunker, used only as a negative control in the
    shift-invariance test: this is the strategy CDC exists to beat.
    """
    return list(range(window, n, window)) + [n]


# --- (a) determinism -------------------------------------------------------


def test_gear_table_is_a_pure_deterministic_function_of_the_byte_value():
    """The table is rebuilt from a fixed label, not `random`, precisely so
    this holds across processes and Python versions, not just within one
    run.
    """
    assert _build_gear_table() == _GEAR
    assert len(_GEAR) == 256
    assert len(set(_GEAR)) == 256  # no accidental collisions


def test_cdc_boundaries_deterministic_across_repeated_calls():
    data = _pseudo_bytes(seed=0, n=50_000)
    first = cdc_boundaries(data, min_size=256, avg_size=1024, max_size=4096)
    second = cdc_boundaries(data, min_size=256, avg_size=1024, max_size=4096)
    assert first == second
    assert len(first) > 1
    assert first[-1] == len(data)


def test_chunk_structured_body_deterministic_across_repeated_calls():
    text = _pseudo_ascii_text(seed=1, n_chars=20_000)
    body = StructuredBody(text=text, span=Span(0, len(text)))
    first = chunk_structured_body(body, protected_regions=[])
    second = chunk_structured_body(body, protected_regions=[])
    assert first == second
    assert len(first) > 1


# --- (b) shift-invariance ---------------------------------------------------


def test_boundaries_before_a_far_edit_are_byte_identical():
    """Editing near the very end must not move any boundary that was
    already finalized before the edit point -- the property that makes
    "only the touched chunk and its dependents re-derive" (CI-06) true.
    """
    baseline = _pseudo_bytes(seed=2, n=40_000)
    base_boundaries = cdc_boundaries(baseline, min_size=256, avg_size=1024, max_size=4096)
    assert len(base_boundaries) >= 4  # need at least a few internal boundaries to test against

    # Insert well inside the *last* chunk, i.e. strictly after the
    # second-to-last real boundary -- everything up to and including that
    # boundary was decided using only bytes the edit never touches.
    insertion_point = base_boundaries[-2] + 10
    extra = _pseudo_bytes(seed=99, n=777)
    edited = baseline[:insertion_point] + extra + baseline[insertion_point:]

    edited_boundaries = cdc_boundaries(edited, min_size=256, avg_size=1024, max_size=4096)

    prefix_len = len(base_boundaries) - 1  # exclude the final len(data) marker, which must differ
    assert edited_boundaries[:prefix_len] == base_boundaries[:prefix_len]


def test_content_defined_chunks_resync_after_an_early_edit_fixed_size_does_not():
    """The property that actually distinguishes CDC from fixed-size
    chunking: after an edit near the *start*, most chunks far from the edit
    still contain byte-identical content once the rolling hash resyncs --
    even though their offsets all shifted. A fixed-size chunker's windows
    never resync unless the edit length happens to be a multiple of the
    window size, which this test deliberately avoids.
    """
    baseline = _pseudo_bytes(seed=3, n=40_000)
    base_boundaries = cdc_boundaries(baseline, min_size=256, avg_size=1024, max_size=4096)
    assert len(base_boundaries) >= 6

    insertion_point = base_boundaries[2] + 5  # early: well before most of the document
    extra = _pseudo_bytes(seed=100, n=777)  # not a multiple of any window size used below
    edited = baseline[:insertion_point] + extra + baseline[insertion_point:]

    edited_boundaries = cdc_boundaries(edited, min_size=256, avg_size=1024, max_size=4096)

    base_chunks = _chunk_bytes(baseline, base_boundaries)
    edited_chunks = _chunk_bytes(edited, edited_boundaries)

    # Compare from the tail: CDC resyncs, so the last several chunks should
    # be byte-for-byte identical despite everything before them shifting.
    tail = min(3, len(base_chunks), len(edited_chunks))
    assert base_chunks[-tail:] == edited_chunks[-tail:]

    # Negative control: a fixed-size chunker over the same edit does NOT
    # resync -- every window after the insertion point is shifted by 777
    # bytes, and 777 is not a multiple of the window size, so no later
    # window ever realigns with its original content again.
    window = 1024
    fixed_base = _fixed_size_boundaries(len(baseline), window)
    fixed_edited = _fixed_size_boundaries(len(edited), window)
    fixed_base_chunks = _chunk_bytes(baseline, fixed_base)
    fixed_edited_chunks = _chunk_bytes(edited, fixed_edited)
    fixed_tail = min(3, len(fixed_base_chunks), len(fixed_edited_chunks))
    assert fixed_base_chunks[-fixed_tail:] != fixed_edited_chunks[-fixed_tail:]


# --- (c) structural boundaries are always respected -------------------------


def test_no_chunk_boundary_falls_inside_a_declared_structural_region():
    prose_before = _pseudo_ascii_text(seed=4, n_chars=2_000)
    table_blob = _pseudo_ascii_text(seed=5, n_chars=6_000)  # long enough that raw CDC WILL trigger inside it
    prose_after = _pseudo_ascii_text(seed=6, n_chars=2_000)
    full_text = prose_before + table_blob + prose_after

    table_start = len(prose_before)
    table_end = len(prose_before) + len(table_blob)

    # Sanity check the test is actually exercising the constraint: prove an
    # UNCONSTRAINED trigger would have landed inside the table region, so a
    # passing assertion below is evidence the snap logic did something, not
    # a coincidence of no trigger ever landing there.
    unconstrained = cdc_boundaries(full_text.encode("utf-8"), min_size=256, avg_size=1024, max_size=4096)
    assert any(table_start < t < table_end for t in unconstrained)

    body = StructuredBody(text=full_text, span=Span(0, len(full_text)))
    chunks = chunk_structured_body(
        body,
        protected_regions=[(table_start, table_end)],
        min_size=256,
        avg_size=1024,
        max_size=4096,
    )

    # The two structural-safety properties, stated directly. (1) No chunk
    # boundary falls strictly inside the protected table region -- this is
    # the "never split a table row" guarantee. (2) The region's edges are
    # both real cuts, so the table stands alone as its own chunk.
    cut_offsets = set()
    running = 0
    for chunk in chunks:
        running += len(chunk.text)
        cut_offsets.add(running)

    assert not any(table_start < c < table_end for c in cut_offsets)
    assert table_start in ({0} | cut_offsets)  # a chunk ends exactly where the table begins
    assert table_end in cut_offsets  # and the table ends exactly on a cut, so it is one chunk
    table_chunk = full_text[table_start:table_end]
    assert table_chunk in {c.text for c in chunks}

    # The documented oversized-region exemption, pinned: this table is 6,000
    # chars > max_size=4096, and because it is indivisible it legitimately
    # produces a chunk over max_size. A future "fix" that split protected
    # regions to satisfy max_size would break structural safety and must fail
    # here loudly, not silently.
    assert len(table_chunk) == 6_000 > 4096

    assert "".join(c.text for c in chunks) == full_text


# --- (c') regressions for the sparse-protected-region collapse (findings 7 & 16) ---
#
# Before the fix, chunk_structured_body took a flat `structural_boundaries`
# offset list and snapped EVERY raw CDC trigger to the nearest such boundary
# at or before it. With a realistic SPARSE structural IR -- a single table
# region inside long prose -- that collapsed all prose between the sparse
# boundaries into one unbounded chunk: the 10k+table+10k document below
# yielded exactly 3 chunks [10000, 498, 10000], a 10,000-char chunk 2.4x over
# max_size, and destroyed CDC's fine-grained shift-invariance for prose. The
# only pre-fix test touching constrained granularity used boundaries every
# 500 chars (implausibly dense), so it never exercised the sparse case.


def test_sparse_table_region_keeps_prose_chunks_bounded_and_fine_grained():
    """Finding 7 regression. The discriminating property is GRANULARITY, not
    tail-identity: under the old collapse the prose_after chunk was still
    byte-identical after an early edit, so a shift-invariance assertion alone
    passed against the bug. What the old code could not produce is many small
    prose chunks each under max_size -- it produced one 10,000-char chunk.
    """
    prose_before = _pseudo_ascii_text(seed=20, n_chars=10_000)
    table_blob = _pseudo_ascii_text(seed=21, n_chars=498)
    prose_after = _pseudo_ascii_text(seed=22, n_chars=10_000)
    full_text = prose_before + table_blob + prose_after
    min_size, avg_size, max_size = 256, 1024, 4096

    table_start = len(prose_before)
    table_end = table_start + len(table_blob)
    body = StructuredBody(text=full_text, span=Span(0, len(full_text)))
    chunks = chunk_structured_body(
        body,
        protected_regions=[(table_start, table_end)],
        min_size=min_size,
        avg_size=avg_size,
        max_size=max_size,
    )

    # (1) The table is its own chunk (its edges are cuts, nothing inside it).
    table_chunk = full_text[table_start:table_end]
    assert table_chunk in {c.text for c in chunks}

    # (2) Granularity: ~20 chunks for 20,498 chars at avg 1024, NOT 3. A loose
    # band -- the guard is "prose was NOT collapsed", and 3 is nowhere near it.
    assert 12 <= len(chunks) <= 30

    # (3) Every prose chunk stays under max_size (the old code's first chunk
    # was 10,000 = 2.4x over). The table region alone is exempt, and here it
    # is smaller than max_size anyway.
    prose_chunks = [c for c in chunks if c.text != table_chunk]
    assert max(len(c.text) for c in prose_chunks) <= max_size

    # (4) Prose chunk sizes cluster around avg_size (same loose band the raw
    # NC-2 size test uses), not one giant outlier dragging the mean up.
    prose_sizes = [len(c.text) for c in prose_chunks]
    mean = sum(prose_sizes) / len(prose_sizes)
    assert avg_size * 0.5 <= mean <= avg_size * 2.0

    assert "".join(c.text for c in chunks) == full_text


def test_sparse_region_preserves_prose_shift_invariance_after_an_early_edit():
    """Finding 16 regression. A 1-char insert early in the prose must leave
    chunks far from the edit byte-identical -- CDC's shift-invariance for
    prose, the property the old collapse destroyed by making the whole first
    prose block a single chunk. Stated ABSOLUTELY (many chunks must survive),
    so it cannot pass against a 3-chunk collapse where "the tail chunk is
    unchanged" is trivially true.
    """
    prose_before = _pseudo_ascii_text(seed=30, n_chars=10_000)
    table_blob = _pseudo_ascii_text(seed=31, n_chars=498)
    prose_after = _pseudo_ascii_text(seed=32, n_chars=10_000)
    full_text = prose_before + table_blob + prose_after
    kw = dict(min_size=256, avg_size=1024, max_size=4096)

    table_start = len(prose_before)
    table_end = table_start + len(table_blob)
    base = chunk_structured_body(
        StructuredBody(text=full_text, span=Span(0, len(full_text))),
        protected_regions=[(table_start, table_end)],
        **kw,
    )

    # Insert one char at offset 5 (early prose). A re-parse reports the table
    # region shifted by one char, so pass the shifted extent -- comparing the
    # unshifted region would fabricate a failure.
    edited_text = full_text[:5] + "X" + full_text[5:]
    edited = chunk_structured_body(
        StructuredBody(text=edited_text, span=Span(0, len(edited_text))),
        protected_regions=[(table_start + 1, table_end + 1)],
        **kw,
    )

    base_texts = [c.text for c in base]
    edited_texts = [c.text for c in edited]
    unchanged = sum(1 for t in base_texts if t in edited_texts)

    # Far-from-edit chunks resync and stay byte-identical. Demand a large
    # absolute count: a 3-chunk collapse could never satisfy this.
    assert len(base) >= 12
    assert unchanged >= 10

    # And the table survives as its own chunk on both sides.
    assert full_text[table_start:table_end] in base_texts
    assert edited_text[table_start + 1 : table_end + 1] in edited_texts


# --- size-distribution sanity (backs the docstring's NC-2 claim) -----------


def test_cdc_boundaries_produces_sizes_clustered_around_avg_size_and_bounded():
    data = _pseudo_bytes(seed=8, n=2_000_000)
    min_size, avg_size, max_size = 256, 1024, 4096
    boundaries = cdc_boundaries(data, min_size, avg_size, max_size)
    sizes = _chunk_bytes(data, boundaries)
    lengths = [len(s) for s in sizes]

    mean = sum(lengths) / len(lengths)
    # Gear-based NC-2 chunking is known to skew above avg_size (cut-point
    # skipping unconditionally consumes the first min_size bytes of every
    # chunk); a loose band pins that this doesn't run away, not a specific
    # unrealistic mean.
    assert avg_size * 0.5 <= mean <= avg_size * 2.0

    assert max(lengths) <= max_size
    # every chunk except possibly the very last (tail, can be short) respects min_size
    assert all(length >= min_size for length in lengths[:-1])


# --- UTF-8 correctness ------------------------------------------------------


def test_multibyte_text_reconstructs_exactly_with_no_structural_constraint():
    text = ("café résumé 世界 🎉 naïve façade — " * 200) + "tail"
    body = StructuredBody(text=text, span=Span(0, len(text)))
    chunks = chunk_structured_body(body, protected_regions=[], min_size=64, avg_size=256, max_size=1024)

    assert len(chunks) > 1
    reconstructed = "".join(c.text for c in chunks)
    assert reconstructed == text
    total_bytes = sum(len(c.text.encode("utf-8")) for c in chunks)
    assert total_bytes == len(text.encode("utf-8"))


def test_multibyte_text_reconstructs_exactly_with_structural_constraint():
    text = ("café résumé 世界 🎉 naïve façade — " * 200) + "tail"
    # A couple of protected regions whose char edges land between multi-byte
    # runs -- the point is to exercise the char<->byte offset conversion on
    # genuinely multi-byte content, where a byte-offset bug would surface.
    protected_regions = [(50, 300), (900, len(text) // 2)]
    body = StructuredBody(text=text, span=Span(0, len(text)))
    chunks = chunk_structured_body(
        body, protected_regions=protected_regions, min_size=64, avg_size=256, max_size=1024
    )

    # Reconstruction alone is true for any correct slicing of a contiguous
    # [0, n) range and would pass even if the byte<->char conversion silently
    # used wrong offsets; the region-edge and byte-total checks below are what
    # actually exercise that conversion.
    assert "".join(c.text for c in chunks) == text
    assert sum(len(c.text.encode("utf-8")) for c in chunks) == len(text.encode("utf-8"))

    cut_offsets = set()
    running = 0
    for chunk in chunks:
        running += len(chunk.text)
        cut_offsets.add(running)
    for start, end in protected_regions:
        assert not any(start < c < end for c in cut_offsets)  # no cut inside a region
        assert start in ({0} | cut_offsets)  # region edges are exact cuts
        assert end in cut_offsets


# --- inheritance: span / section_path / page / bbox / table_cells ----------


def test_child_chunks_inherit_section_path_page_and_bbox_and_have_contiguous_spans():
    text = _pseudo_ascii_text(seed=9, n_chars=5_000)
    parent_span = Span(start=1_000, end=1_000 + len(text))
    bbox = BoundingBox(page=3, x0=0.0, y0=0.0, x1=1.0, y1=1.0)
    body = StructuredBody(
        text=text,
        section_path=("Doc", "Section 1"),
        page=3,
        bbox=bbox,
        span=parent_span,
    )

    chunks = chunk_structured_body(body, protected_regions=[], min_size=128, avg_size=256, max_size=512)
    assert len(chunks) > 1

    for chunk in chunks:
        assert chunk.section_path == body.section_path
        assert chunk.page == body.page
        assert chunk.bbox == bbox
        assert chunk.table_cells is None  # body was split; parent's cell grid cannot be sliced by offset

    assert chunks[0].span.start == parent_span.start
    assert chunks[-1].span.end == parent_span.end
    for a, b in zip(chunks, chunks[1:]):
        assert a.span.end == b.span.start  # contiguous, no gaps or overlaps

    # Spans re-base onto the parent's frame, not onto body.text's own local offsets.
    for chunk in chunks:
        local_len = chunk.span.end - chunk.span.start
        assert local_len == len(chunk.text)


def test_table_cells_survive_only_when_the_body_is_not_actually_split():
    short_text = "one two three four five"
    cells = (TableCell(row=0, col=0, text="one two three four five", is_header=False),)
    body = StructuredBody(text=short_text, table_cells=cells, span=Span(0, len(short_text)))

    # Defaults (min_size=256) are far bigger than short_text, so it cannot split.
    chunks = chunk_structured_body(body, protected_regions=[])
    assert len(chunks) == 1
    assert chunks[0].table_cells == cells


def test_table_as_a_body_wrapped_in_one_protected_region_keeps_its_cells():
    """The docstring's headline case: a body that IS one table -- larger than
    max_size, so raw CDC would split it -- wrapped in a single protected
    region spanning the whole body. It must collapse to exactly one chunk
    (region start/end are the only cuts) with `table_cells` preserved, since
    an unsplit body's cell grid still maps to its text.
    """
    text = _pseudo_ascii_text(seed=40, n_chars=6_000)  # > max_size=4096
    cells = (
        TableCell(row=0, col=0, text="h", is_header=True),
        TableCell(row=1, col=0, text="v"),
    )
    body = StructuredBody(text=text, table_cells=cells, span=Span(0, len(text)))

    chunks = chunk_structured_body(
        body, protected_regions=[(0, len(text))], min_size=256, avg_size=1024, max_size=4096
    )

    assert len(chunks) == 1
    assert chunks[0].text == text  # the whole indivisible table, over max_size, is one chunk
    assert chunks[0].table_cells == cells


# --- validation --------------------------------------------------------------


@pytest.mark.parametrize(
    "min_size,avg_size,max_size",
    [
        (1024, 1024, 4096),  # min == avg
        (256, 4096, 4096),  # avg == max
        (0, 1024, 4096),  # min == 0
        (2048, 1024, 4096),  # min > avg
    ],
)
def test_cdc_boundaries_rejects_invalid_size_ordering(min_size, avg_size, max_size):
    with pytest.raises(ValueError):
        cdc_boundaries(b"irrelevant payload", min_size, avg_size, max_size)


def test_chunk_structured_body_rejects_unsorted_protected_regions():
    body = StructuredBody(text="abcdefgh")
    with pytest.raises(ValueError):
        chunk_structured_body(body, protected_regions=[(4, 6), (1, 3)])


def test_chunk_structured_body_rejects_overlapping_protected_regions():
    """Overlapping (or nested) regions are rejected, not merged: silently
    merging a table nested in a section would coarsen the whole section into
    one chunk, reintroducing finding 7 through the back door (decisions.md
    #12). The caller must flatten IR extents to the outermost unit first.
    """
    body = StructuredBody(text="abcdefgh")
    with pytest.raises(ValueError):
        chunk_structured_body(body, protected_regions=[(1, 5), (3, 7)])


def test_chunk_structured_body_rejects_empty_protected_region():
    body = StructuredBody(text="abcdefgh")
    with pytest.raises(ValueError):
        chunk_structured_body(body, protected_regions=[(3, 3)])  # start == end


def test_chunk_structured_body_rejects_out_of_range_protected_region():
    body = StructuredBody(text="abcdefgh")
    with pytest.raises(ValueError):
        chunk_structured_body(body, protected_regions=[(2, 4), (6, 999)])


# --- degenerate/edge inputs ---------------------------------------------------


def test_empty_body_text_returns_the_body_unchanged():
    body = StructuredBody(text="")
    assert chunk_structured_body(body, protected_regions=[]) == [body]


def test_text_shorter_than_min_size_returns_a_single_chunk():
    body = StructuredBody(text="short", span=Span(0, 5))
    chunks = chunk_structured_body(body, protected_regions=[], min_size=256, avg_size=1024, max_size=4096)
    assert len(chunks) == 1
    assert chunks[0].text == "short"


def test_cdc_boundaries_empty_data_returns_empty_list():
    assert cdc_boundaries(b"", min_size=256, avg_size=1024, max_size=4096) == []


# --- property-based: shift-invariance and structural safety, fuzzed --------


@given(
    doc_len=st.integers(min_value=6_000, max_value=20_000),
    doc_seed=st.integers(min_value=0, max_value=2**31 - 1),
    insert_len=st.integers(min_value=1, max_value=900),
    insert_seed=st.integers(min_value=0, max_value=2**31 - 1),
)
@settings(max_examples=40)
def test_property_far_edit_never_moves_earlier_boundaries(doc_len, doc_seed, insert_len, insert_seed):
    """Generalizes `test_boundaries_before_a_far_edit_are_byte_identical`
    across random document lengths, contents, and insertion lengths: an
    edit strictly inside the last chunk must never move any boundary
    finalized before it.
    """
    baseline = _pseudo_bytes(seed=doc_seed, n=doc_len)
    base_boundaries = cdc_boundaries(baseline, min_size=256, avg_size=1024, max_size=4096)
    if len(base_boundaries) < 3:
        return  # too short to have a meaningful "earlier boundary" to protect

    insertion_point = base_boundaries[-2] + 1
    extra = _pseudo_bytes(seed=insert_seed, n=insert_len)
    edited = baseline[:insertion_point] + extra + baseline[insertion_point:]

    edited_boundaries = cdc_boundaries(edited, min_size=256, avg_size=1024, max_size=4096)

    prefix_len = len(base_boundaries) - 1
    assert edited_boundaries[:prefix_len] == base_boundaries[:prefix_len]


@given(
    text=st.text(min_size=1, max_size=4_000),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
@settings(max_examples=60)
def test_property_no_cut_falls_inside_a_protected_region_and_text_reconstructs(text, seed):
    """Fuzzes arbitrary unicode text (hypothesis's default text strategy
    includes astral-plane, multi-byte characters -- the cases most likely
    to expose a byte/char offset bug) and a random set of disjoint protected
    regions. Two invariants must hold for any input: no emitted cut falls
    strictly inside a protected region, and the chunks reconstruct the
    original text exactly.
    """
    n = len(text)
    rng = random.Random(seed)
    # Sample sorted distinct offsets and pair them into CONSECUTIVE disjoint
    # regions; random pairing would produce overlaps and hit the validator.
    candidates = list(range(1, n)) if n > 1 else []
    k = rng.randint(0, len(candidates))
    k -= k % 2  # even count -> whole (start, end) pairs
    points = sorted(rng.sample(candidates, k)) if k else []
    protected_regions = [(points[i], points[i + 1]) for i in range(0, len(points), 2)]

    body = StructuredBody(text=text, span=Span(0, n))
    chunks = chunk_structured_body(
        body, protected_regions=protected_regions, min_size=32, avg_size=128, max_size=512
    )

    assert "".join(c.text for c in chunks) == text

    if protected_regions:
        cut_offsets = set()
        running = 0
        for chunk in chunks:
            running += len(chunk.text)
            cut_offsets.add(running)
        for start, end in protected_regions:
            assert not any(start < c < end for c in cut_offsets)
            assert start in ({0} | cut_offsets)  # region edges are always cuts
            assert end in cut_offsets
