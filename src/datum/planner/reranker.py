"""Reranker: the rerank slot in the compiled retrieval pipeline (L6).

The plan-selection policy declares a `rerank_depth` (policy.rule_table); the
compiler applies the configured Reranker to the fused candidate set. Like
plan selection itself, WHICH reranker runs is a versioned slot the trace
records (`name@version` in the rerank PlanStep), not a hard-coded choice.

Semantics when a real reranker is active (recorded as decisions.md #22): the
reranker re-scores the top `depth` fused candidates and its output IS the
final candidate set — candidates past the declared depth are cut, not
carried with incomparable scores. CandidateSet's own contract ("scores ...
NOT assumed comparable across operators; declared, never silently mixed")
forbids the tempting alternative of stitching cross-encoder scores onto the
head and RRF scores onto the tail of one set. The cut is visible: depth is
declared in the dated rule table and shown in the plan's EXPLAIN before
execution.

`IdentityReranker` is the wired-but-empty slot: it returns the fused set
untouched, so deployments without the ML extras run the identical pipeline
shape with no silent behavioral fork — the compiler simply omits the rerank
step from the plan when the slot holds the identity.
"""

from __future__ import annotations

import math
from typing import Protocol

from datum.kernel.errors import DatumError
from datum.kernel.operator import CandidateSet

_DEFAULT_MODEL = "BAAI/bge-reranker-base"


class Reranker(Protocol):
    name: str
    version: str

    def rerank(self, query: str, candidates: CandidateSet, depth: int) -> CandidateSet: ...


class IdentityReranker:
    """The empty slot. Never cuts, never re-scores."""

    name = "identity"
    version = "v1"

    def rerank(self, query: str, candidates: CandidateSet, depth: int) -> CandidateSet:
        del query, depth
        return candidates


class CrossEncoderReranker:
    """Local cross-encoder rerank via sentence-transformers, lazy-loaded.

    The model imports and loads on the FIRST rerank call, never at
    construction — the compiler must be constructible (and the plan
    explainable) in an environment without the ML extras, failing only if a
    rerank actually executes there. Scores are the cross-encoder's logits
    squashed through a sigmoid: monotone in the model's preference (all the
    score contract asks) and bounded to [0, 1] so downstream heuristics see a
    stable range — NOT a calibrated probability, same as every score in v1.
    """

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        self.name = model_name
        self.version = "v1"
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder  # lazy: ML extra

            self._model = CrossEncoder(self.name)
        return self._model

    def rerank(self, query: str, candidates: CandidateSet, depth: int) -> CandidateSet:
        if depth <= 0 or not candidates.records:
            return candidates
        head = candidates.records[: min(depth, len(candidates.records))]
        pairs = [(query, record.body_text()) for record in head]
        logits = list(self._load().predict(pairs))
        # Defense in depth (review finding M4): a cross-encoder should return
        # one finite logit per pair, but a buggy/degenerate model could return
        # too few (zip would silently DROP candidates) or a NaN (which breaks
        # the total order the tie-break relies on, making the output
        # non-deterministic). Both would corrupt the ranking silently, so
        # reject them loudly rather than ship a scrambled or truncated result.
        if len(logits) != len(head):
            raise DatumError(
                f"reranker {self.name!r} returned {len(logits)} scores for {len(head)} "
                "candidates; refusing to drop or misalign candidates."
            )
        scores = [_sigmoid(float(l)) for l in logits]
        if any(not math.isfinite(s) for s in scores):
            raise DatumError(
                f"reranker {self.name!r} produced a non-finite score; a NaN breaks the "
                "deterministic tie-break and would scramble the ranking."
            )
        scored = sorted(
            zip(head, scores),
            key=lambda rs: (-rs[1], str(rs[0].id)),  # deterministic tie-break
        )
        return CandidateSet(
            records=tuple(record for record, _ in scored),
            scores=tuple(score for _, score in scored),
            score_method=f"rerank:{self.name}",
        )


def _sigmoid(x: float) -> float:
    # Split on sign so a large-magnitude negative logit never overflows exp().
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def default_reranker() -> "Reranker":
    """The cross-encoder when the ML extra is importable, else the identity —
    decided by probing importability WITHOUT loading the model (cheap at
    wiring time). The choice is visible, not silent: the compiler names the
    active reranker in the plan and omits the rerank step entirely under the
    identity, so an EXPLAIN never claims a rerank that will not happen.
    """
    import importlib.util

    if importlib.util.find_spec("sentence_transformers") is not None:
        return CrossEncoderReranker()
    return IdentityReranker()
