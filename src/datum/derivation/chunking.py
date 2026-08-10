"""Boundary-constrained content-defined chunking (L4 Derivation Engine).

FRAMEWORK.md, "Ingestion & derivation": chunk boundaries are content-defined
via FastCDC (Xia, Jiang, Feng, Douglis, Shilane, Hua, "FastCDC: a Fast and
Efficient Content-Defined Chunking Approach for Data Deduplication," USENIX
ATC 2016) — a rolling-hash function that picks a split point wherever a
window of bytes hashes below a threshold. A chunk's identity is therefore a
function of its *content*, not its byte offset: editing one paragraph shifts
every downstream byte offset, but it does not change the hash computed over
bytes the edit never touched, so unrelated, untouched chunks keep the exact
same boundaries and the exact same content hash (the correctness property
this module calls *shift-invariance*; see `cdc_boundaries`'s docstring and
`tests/derivation/test_chunking.py`'s edit-far-from-boundary tests). This is
the concrete mechanism behind CI-06's "only the touched chunk and its
dependents re-derive" acceptance test.

FastCDC itself is well-specified, decades-old dedup/backup engineering with
no novelty claimed here (cited above, not reinvented). No off-the-shelf
Python library implements the second half this module provides — boundary
CONSTRAINING against a structural IR (never split inside a table, never cut
across a heading/body boundary) — because that merge is specific to
Datum's L2 structural representation, not a general dedup concern; per the
plan, it is hand-rolled directly rather than bolted onto a borrowed library.

FRAMEWORK.md, "Reconciling content-defined boundaries with the structural
IR": plain rolling-hash CDC cuts wherever the hash condition fires, an
arbitrary byte position, while the structural IR demands a table's cells
and a section's heading stay intact within one chunk. The spec resolves
this with candidate split points drawn from the *union* of {rolling-hash
trigger positions, structural-unit boundaries}, snapping a trigger back to
a structural boundary only where it would otherwise cut inside a protected
unit. `chunk_structured_body` below implements that union directly (see
docs/decisions.md #15): a trigger in open prose is used as-is, so prose
keeps CDC's fine, shift-invariant granularity and stays bounded by
`max_size`; only a trigger that falls *strictly inside* a protected region
(a table, a heading/body unit) is snapped to that region's start, and each
region's start and end are themselves always boundaries so the unit becomes
its own chunk. Granularity therefore degrades from paragraph-level to
unit-level only around structural content — a single protected region wider
than `max_size` is the one case a prose-free chunk exceeds it by design —
while every prose chunk stays within `max_size` up to a few bytes of
char-boundary slack on multi-byte text (see `_snap_char`), and no chunk ever
splits a table row or separates a heading from the content it governs.
"""

from __future__ import annotations

import hashlib
import math
from bisect import bisect_left, bisect_right

from datum.kernel.record import Span, StructuredBody


def _build_gear_table() -> tuple[int, ...]:
    """256 deterministic 64-bit values, one per possible input byte.

    FastCDC's rolling fingerprint is `fp = (fp << 1) + GEAR[byte]`; GEAR only
    needs to look like noise (no algebraic structure a real byte stream
    would resonate with), not to be cryptographically secure. It does,
    however, need to be *exactly reproducible across processes and Python
    versions* — `cdc_boundaries`'s determinism test (same bytes in, same
    boundaries out, forever) is meaningless if the table itself drifts.
    `random.Random(seed)` does not carry that guarantee across Python
    versions; hashing a fixed label is stable by construction and needs no
    table checked into source to prove it didn't change.
    """
    return tuple(
        int.from_bytes(hashlib.sha256(b"datum-fastcdc-gear-v1-" + bytes([i])).digest()[:8], "big")
        for i in range(256)
    )


_GEAR: tuple[int, ...] = _build_gear_table()
_FP_MASK = (1 << 64) - 1


def _high_mask(bits: int) -> int:
    """A 64-bit mask with the top `bits` bits set, 0 if `bits <= 0`.

    In `fp = (fp << 1) + GEAR[byte]`, the shift-then-add means bit *k* of
    `fp` is a function of only the most recent *k + 1* input bytes: addition
    only carries upward (low bit to high bit), never downward, and each new
    byte's contribution occupies bit 0 upward, so a term from *j* bytes ago
    cannot influence any bit below position *j*. Consequently the LOW bits
    of `fp` have a rolling window of just one or two bytes — masking them
    would make the chunker sensitive to almost no context and produce a
    degenerate, non-CDC size distribution — while the HIGH bits carry a
    window of up to 64 bytes, which is the amount of local context FastCDC's
    boundary test is supposed to see. The mask must therefore be built from
    the high end.
    """
    if bits <= 0:
        return 0
    bits = min(bits, 64)
    return ((1 << bits) - 1) << (64 - bits)


def _validate_sizes(min_size: int, avg_size: int, max_size: int) -> None:
    if not (0 < min_size < avg_size < max_size):
        raise ValueError(
            "require 0 < min_size < avg_size < max_size, got "
            f"min_size={min_size}, avg_size={avg_size}, max_size={max_size}"
        )


def cdc_boundaries(data: bytes, min_size: int, avg_size: int, max_size: int) -> list[int]:
    """FastCDC (Xia et al., USENIX ATC 2016) with normalized chunking (NC-2).

    Returns a sorted list of exclusive chunk-end byte offsets: for return
    value `b`, chunk *i* occupies `data[b[i-1]:b[i]]` (with `b[-1] == 0` for
    `i == 0`). The final element is always `len(data)`; the empty list is
    returned only when `data` is empty.

    Algorithm: a gear-table rolling hash `fp = (fp << 1) + GEAR[byte]` is
    fed one byte at a time. The first `min_size` bytes of a new chunk are
    fed to the hash but never tested (cut-point skipping — the chunk cannot
    end before `min_size` regardless of what the hash does). After that,
    each position is tested against one of two masks: a harder-to-satisfy
    mask (more bits required zero) while the chunk is shorter than
    `avg_size`, and an easier one once it has reached `avg_size` — this
    normalization is what keeps the size distribution concentrated around
    `avg_size` rather than the wide range plain content-defined chunking
    produces. If no boundary fires by `max_size`, a hard cut is forced
    there (or at `len(data)` if the input runs out first).

    Correctness property this function must have — shift-invariance:
    inserting or deleting bytes far from a boundary must not change that
    boundary's position. This holds by construction because the rolling
    hash only ever looks backward at the most recent bytes (see
    `_high_mask`): a boundary at offset `k` is a pure function of
    `data[k-63:k]` (clamped to the current chunk's start), so an edit at
    offset `e` cannot affect any boundary at `k < e - 63`, and a chunk
    boundary once found doesn't reconsider bytes before it. An edit shifts
    every boundary *after* it (their positions are defined relative to
    where scanning resumed) but leaves every boundary *before* it bit-for-
    bit identical — this is exactly the "only the touched chunk and its
    dependents re-derive" property FRAMEWORK.md's CI-06 names, not a
    stronger claim that a mid-document insert never touches anything: it
    is CDC's whole reason for existing over fixed-size chunking, which
    reshuffles every boundary after an edit's containing chunk.
    """
    _validate_sizes(min_size, avg_size, max_size)
    n = len(data)
    if n == 0:
        return []

    bits = round(math.log2(avg_size))
    mask_hard = _high_mask(bits + 2)  # below avg_size: harder to hit, discourages tiny chunks
    mask_easy = _high_mask(bits - 2)  # at/after avg_size: easier to hit, discourages oversize chunks

    boundaries: list[int] = []
    pos = 0
    while pos < n:
        end = min(pos + max_size, n)
        if pos + min_size >= end:
            # Not enough bytes left in this window to skip past min_size
            # and still have room to test for a boundary; the rest of the
            # data (or the rest up to max_size) becomes the final chunk.
            boundaries.append(end)
            pos = end
            continue

        fp = 0
        i = pos
        while i < pos + min_size:  # cut-point skipping: prime the hash, don't test it
            fp = ((fp << 1) + _GEAR[data[i]]) & _FP_MASK
            i += 1

        avg_point = pos + avg_size
        cut = end  # fallback: hard cut at max_size (or end of data)
        while i < end:
            fp = ((fp << 1) + _GEAR[data[i]]) & _FP_MASK
            mask = mask_hard if i < avg_point else mask_easy
            if fp & mask == 0:
                cut = i + 1
                break
            i += 1

        boundaries.append(cut)
        pos = cut

    return boundaries


def _char_boundary_byte_offsets(text: str) -> list[int]:
    """`offsets[i]` = byte length of `text[:i].encode("utf-8")`, for i in
    `0..len(text)` inclusive.

    Every value in this list is a position it is always safe to slice
    `text`'s UTF-8 encoding at without splitting a multi-byte code point;
    raw FastCDC byte offsets are not guaranteed to be, since FastCDC has no
    notion of character boundaries. This list is the bridge in both
    directions: structural char offsets are looked up by index to become
    byte offsets for snapping, and snapped byte offsets are looked up by
    value (via bisect) to become char offsets for slicing `text` itself.
    """
    offsets = [0]
    total = 0
    for ch in text:
        total += len(ch.encode("utf-8"))
        offsets.append(total)
    return offsets


def _snap_char(byte_offset: int, byte_at_char: list[int]) -> int:
    """Largest valid UTF-8 char-boundary byte offset that is `<= byte_offset`.

    FastCDC triggers on raw bytes and has no notion of a character, so a raw
    trigger can land in the middle of a multi-byte code point; slicing there
    would corrupt the text. `byte_at_char` holds exactly the byte offsets it
    is safe to cut at (see `_char_boundary_byte_offsets`), so snapping down
    to the nearest one is the bridge back from a byte trigger to a slice
    point. Snapping is independent per trigger, so it can grow the following
    chunk by at most `len(largest UTF-8 code point) - 1 == 3` bytes past
    `max_size` on multi-byte text (a trigger mid-code-point moves back while
    the next trigger, already on a boundary, does not); on single-byte text
    it is a no-op and `max_size` holds exactly.
    """
    return byte_at_char[bisect_right(byte_at_char, byte_offset) - 1]


def chunk_structured_body(
    body: StructuredBody,
    protected_regions: list[tuple[int, int]],
    min_size: int = 256,
    avg_size: int = 1024,
    max_size: int = 4096,
) -> list[StructuredBody]:
    """Boundary-constrained FastCDC over one `StructuredBody`.

    `protected_regions` is a sorted, non-overlapping list of `(start, end)`
    character extents into `body.text` that the structural parser marks as
    indivisible units — a table's full span, a heading together with the
    body it governs — each of which must land inside a single chunk, never
    split across (FRAMEWORK.md, "Reconciling content-defined boundaries with
    the structural IR"). The candidate cut points are the *union* that
    section names: every raw CDC trigger (`cdc_boundaries`) that falls in
    open prose is used as-is, so prose keeps CDC's fine, shift-invariant
    granularity and stays bounded by `max_size`; a trigger that would land
    *strictly inside* a protected region is snapped back to that region's
    start (equivalently — and how it is built here — simply dropped, since
    the region's start is already an unconditional cut); and each region's
    start and end are always cuts, so the region becomes its own chunk. See
    docs/decisions.md #15 for why the spec's "nearest structural boundary at
    or before" rule is applied only to a trigger inside a protected unit
    rather than to every trigger (the earlier reading collapsed all prose
    between sparse units into one unbounded chunk).

    The one accepted cost (FRAMEWORK.md, same section): a protected region
    wider than `max_size` yields a chunk wider than `max_size`, because that
    unit is indivisible by construction; every prose chunk still respects
    `max_size` up to a few bytes of char-boundary slack on multi-byte text
    (see `_snap_char`). An empty `protected_regions` means there is no
    structural
    constraint and raw triggers are used directly (still snapped to the
    nearest character boundary, since FastCDC cuts on raw UTF-8 bytes and a
    mid-code-point cut would corrupt the text).

    Every emitted `StructuredBody` inherits `section_path`, `page`, and
    `bbox` unchanged from `body` (§Core abstractions #6: "every retrieved
    chunk traces to page + bounding region" survives chunking because this
    is a straight copy, not a re-derivation) and gets a `span` re-based
    onto `body.span`'s own frame, so a chunk's offsets are still offsets
    into the *original document*, not into `body.text` alone. `table_cells`
    is carried through only when the body was not actually split (the
    common case for a body entirely inside one protected region, which
    produces exactly one chunk): once a body is split into more than one
    chunk, the parent's cell grid cannot be sliced by character offset the
    way `text` can, so it is dropped (`None`) rather than attached wholesale
    to every fragment, which would silently claim cells for a fragment that
    doesn't contain them.

    Judgment call, undocumented by the kernel: a chunk with no `body.span`
    (span is `Optional`) is treated as based at offset 0 — there is no
    parent frame to re-base onto, so the chunk's own local offsets are the
    only offsets available. Nested or overlapping regions are rejected
    rather than merged (docs/decisions.md #15): silently merging a table
    nested in a section would coarsen the whole section into one chunk — the
    very collapse this signature exists to prevent — so the caller must
    flatten IR extents to their outermost protected unit first.
    """
    _validate_sizes(min_size, avg_size, max_size)

    text = body.text
    n_chars = len(text)

    prev_region_end = 0
    for start, end in protected_regions:
        if not (0 <= start < end <= n_chars):
            raise ValueError(
                "each protected region must satisfy 0 <= start < end <= "
                f"len(body.text)={n_chars}, got {(start, end)}"
            )
        if start < prev_region_end:
            raise ValueError(
                "protected_regions must be sorted ascending and non-overlapping, "
                f"got region {(start, end)} starting before the previous region's "
                f"end {prev_region_end}"
            )
        prev_region_end = end

    data = text.encode("utf-8")
    if not data:
        return [body]

    byte_at_char = _char_boundary_byte_offsets(text)
    raw_cuts = cdc_boundaries(data, min_size, avg_size, max_size)

    region_bytes = [(byte_at_char[s], byte_at_char[e]) for s, e in protected_regions]
    region_starts = [rs for rs, _ in region_bytes]

    def _strictly_inside_region(offset: int) -> bool:
        # Regions are sorted and disjoint, so the only one that could contain
        # `offset` is the region with the greatest start `<= offset`.
        i = bisect_right(region_starts, offset) - 1
        if i < 0:
            return False
        rs, re = region_bytes[i]
        return rs < offset < re

    # Union of {region edges, prose triggers}: region starts/ends are always
    # cuts (so a protected unit stands alone); a trigger keeps its own
    # position unless it lands inside a region, in which case dropping it is
    # exactly "snap to the region start" because that start is already a cut.
    cut_set: set[int] = {len(data)}
    for rs, re in region_bytes:
        cut_set.add(rs)
        cut_set.add(re)
    for trigger in raw_cuts:
        snapped = _snap_char(trigger, byte_at_char)
        if not _strictly_inside_region(snapped):
            cut_set.add(snapped)
    cut_set.discard(0)
    cuts = sorted(cut_set)

    parent_start = body.span.start if body.span is not None else 0
    single_chunk = len(cuts) == 1

    chunks: list[StructuredBody] = []
    prev_byte = 0
    for cut_byte in cuts:
        start_char = bisect_left(byte_at_char, prev_byte)
        end_char = bisect_left(byte_at_char, cut_byte)
        chunks.append(
            StructuredBody(
                text=text[start_char:end_char],
                section_path=body.section_path,
                page=body.page,
                bbox=body.bbox,
                table_cells=body.table_cells if single_chunk else None,
                span=Span(start=parent_start + start_char, end=parent_start + end_char),
            )
        )
        prev_byte = cut_byte

    return chunks
