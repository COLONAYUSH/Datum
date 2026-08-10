"""Identity types shared across every layer.

RecordID is a content hash of (body, structure) at a given version, never an
arbitrary counter — this is what makes idempotent re-ingestion possible: the
same content produces the same id, so re-asserting an unchanged span is a
no-op the caller can detect without a round trip.
"""

from __future__ import annotations

from typing import NewType

RecordID = NewType("RecordID", str)
PolicyID = NewType("PolicyID", str)
