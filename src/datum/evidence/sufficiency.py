"""Uncalibrated sufficiency estimation (L7).

FRAMEWORK.md's MVP definition is explicit that v1 ships an "uncalibrated-but-
typed sufficiency score, labeled as such rather than mis-claimed as
calibrated." This is that estimator: a cheap, monotone heuristic over the
candidate set, returned inside a CalibratedScore whose `calibrated=False` and
whose method name says plainly it is a raw heuristic. Real calibration
(isotonic regression on a corpus-specific human-anchored slice) is a Phase 1
addition behind the same type — not a rewrite of the interface.

The heuristic must never over-claim: with zero candidates it returns 0.0 (the
caller will surface `insufficient_evidence`), and it saturates well below 1.0
so nothing downstream reads it as a calibrated probability of sufficiency.
"""

from __future__ import annotations

import math

from datum.kernel.operator import CandidateSet

SUFFICIENCY_METHOD = "uncalibrated-heuristic-v2"


def estimate_sufficiency(candidates: CandidateSet, *, agreement: float | None = None) -> float:
    """A raw, uncalibrated score in [0, 0.9]. Zero candidates -> 0.0. More
    matches and a stronger top score raise it, with a hard cap below 1.0 so
    it can never be mistaken for a calibrated certainty.

    `agreement` (v2, the Milestone B extension) is the fraction of the fused
    candidates that MORE THAN ONE retrieval operator surfaced independently —
    computed by the compiler, which is the only layer that sees per-operator
    lists before fusion. Cross-operator agreement is the one genuinely new
    signal a hybrid gives over any single retriever (a candidate found both
    lexically and semantically is better evidence than either alone), so it
    earns a term here; None (single-operator retrieval) leaves the v1 blend
    untouched rather than pretending an agreement of zero was measured.
    """
    n = len(candidates.records)
    if n == 0:
        return 0.0
    top = max(candidates.scores) if candidates.scores else 0.0
    # coverage: more distinct hits is weak positive evidence, saturating fast.
    coverage = 1.0 - (1.0 / (1.0 + n))  # n=1 -> 0.5, n=3 -> 0.75, n->inf -> 1.0
    strength = 1.0 - (1.0 / (1.0 + top)) if top > 0 else 0.0
    if agreement is None:
        raw = 0.5 * coverage + 0.5 * strength
    else:
        # A non-finite agreement must never read as MAX agreement through
        # max(0, min(1, nan)) (review finding L3) — clamp NaN to 0.0 first.
        safe_agreement = agreement if math.isfinite(agreement) else 0.0
        raw = 0.4 * coverage + 0.3 * strength + 0.3 * max(0.0, min(1.0, safe_agreement))
    return round(min(0.9, raw), 4)
