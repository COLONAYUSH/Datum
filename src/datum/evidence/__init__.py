"""datum.evidence: L7, wrapping raw operator output into typed EvidenceState.

`build_evidence_state` (wrap.py) is the boundary where a CandidateSet becomes
the typed, provenance-carrying, abstention-capable result the rest of the
system consumes; `estimate_sufficiency` (sufficiency.py) is v1's explicitly
uncalibrated sufficiency heuristic.
"""

from datum.evidence.sufficiency import estimate_sufficiency
from datum.evidence.wrap import build_evidence_state

__all__ = ["build_evidence_state", "estimate_sufficiency"]
