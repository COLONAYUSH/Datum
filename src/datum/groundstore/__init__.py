"""datum.groundstore: L2, the canonical bitemporal record store.

Imports downward only (kernel, storage). Nothing above L2 imports from here
except through the composition root (Corpus). The uniqueness-CAS and atomic-
supersede invariants that make this the safety-critical layer live in
`store.py`; `precondition.py` holds the write-time admission hooks.
"""

from datum.groundstore.store import GroundStore, compute_record_id, require_writer_namespace

__all__ = ["GroundStore", "compute_record_id", "require_writer_namespace"]
