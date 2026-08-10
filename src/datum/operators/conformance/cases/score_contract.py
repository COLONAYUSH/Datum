"""cases.score_contract: `CandidateSet.scores` are declared with a
`score_method` string and are internally consistent -- monotonic in
relevance -- for a synthetic ranked fixture.

Written generically ("monotonic in relevance"), NOT against an exact BM25
formula: FRAMEWORK.md's own MVP definition still treats the BM25 backing
implementation as a go/no-go decision, so pinning a specific scoring formula
here would gate operator registration on an implementation choice this
suite has no business making. What every operator DOES owe a caller,
regardless of formula: scores line up 1:1 with records, declare which
method produced them, are finite numbers, and never rank a less-relevant
row above a more-relevant one within the same CandidateSet.
`kernel.operator.CandidateSet.scores` itself notes scores are "NOT assumed
comparable across operators" -- this case only ever compares scores an
Operator produced within a single call, never across two different
operators' outputs.

Plain function, zero `import pytest` -- see cases/filter_algebra.py's module
docstring for why.
"""

from __future__ import annotations

import math
from collections import Counter
from itertools import combinations

from datum.kernel.operator import Operator
from datum.kernel.plan import Budget
from datum.operators.conformance.types import CaseResult, ConformanceFragment, ProbeRow, make_record


def _ranked_rows() -> tuple[ProbeRow, ...]:
    # Distinct, deliberately non-monotonic-with-id relevance (including a tie)
    # so an operator that merely echoes insertion order, or breaks ties badly,
    # cannot pass by accident.
    return (
        ProbeRow(record=make_record("r1", namespace="acme"), relevance=0.2),
        ProbeRow(record=make_record("r2", namespace="acme"), relevance=0.9),
        ProbeRow(record=make_record("r3", namespace="acme"), relevance=0.5),
        ProbeRow(record=make_record("r4", namespace="acme"), relevance=0.5),
    )


def check(operator: Operator) -> CaseResult:
    rows = _ranked_rows()
    fragment = ConformanceFragment(rows=rows)
    try:
        op_plan = operator.plan(fragment, Budget())
        candidates = operator.execute(op_plan)
    except Exception as exc:
        # An operator that raises inside plan()/execute() must become a failed
        # case, never an uncaught exception that aborts ConformanceSuite.run()
        # and denies a caller any SuiteReport at all -- a crashed gate is
        # indistinguishable from an absent one at register_operator() time.
        return CaseResult(
            name="score_contract",
            passed=False,
            detail=f"operator.plan()/execute() raised {exc!r} instead of returning",
        )

    if len(candidates.records) != len(candidates.scores):
        return CaseResult(
            name="score_contract",
            passed=False,
            detail=(
                f"records/scores length mismatch: {len(candidates.records)} records, "
                f"{len(candidates.scores)} scores -- CandidateSet requires one score per record."
            ),
        )
    if not candidates.score_method or not isinstance(candidates.score_method, str):
        return CaseResult(
            name="score_contract",
            passed=False,
            detail=f"score_method must be a non-empty declared string, got {candidates.score_method!r}.",
        )

    relevance_by_id = {str(row.record.id): row.relevance for row in rows}
    returned_ids = [str(record.id) for record in candidates.records]

    # Duplicate detection runs FIRST -- before the finite-score loop and before
    # any dict keyed by id -- because a plain dict silently collapses a repeated
    # id to last-write-wins, so an operator returning the same record twice with
    # two different scores would otherwise pass with one score quietly dropped.
    # Detecting duplicates up front also keeps every downstream failure message
    # unambiguous: past this point an id names exactly one record.
    duplicates = sorted(rid for rid, count in Counter(returned_ids).items() if count > 1)
    if duplicates:
        return CaseResult(
            name="score_contract",
            passed=False,
            detail=(
                f"CandidateSet returned duplicate record ids {duplicates} -- a record must appear "
                "at most once, else its declared score is ambiguous."
            ),
        )

    score_by_id: dict[str, float] = {}
    for record, score in zip(candidates.records, candidates.scores):
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            return CaseResult(
                name="score_contract",
                passed=False,
                detail=f"score for record {record.id!r} is not a finite number: {score!r}.",
            )
        score_by_id[str(record.id)] = float(score)

    missing = set(relevance_by_id) - set(score_by_id)
    if missing:
        return CaseResult(
            name="score_contract",
            passed=False,
            detail=(
                f"CandidateSet dropped rows {sorted(missing)} even though this probe applied no "
                "filter, tenancy, or entitlement gate -- score_contract issues no filter at all."
            ),
        )

    # The converse of `missing`: ids the operator returned that were never in
    # the probe's input rows. A fabricated record is a leak shape (the operator
    # invented a candidate), and it must be caught here rather than surfacing
    # downstream as a `relevance_by_id[extra_id]` KeyError inside the monotonic
    # loop, which would abort ConformanceSuite.run() instead of failing the case.
    extra = set(score_by_id) - set(relevance_by_id)
    if extra:
        return CaseResult(
            name="score_contract",
            passed=False,
            detail=(
                f"CandidateSet returned fabricated records {sorted(extra)} that were never in the "
                "probe's input rows -- an operator must not invent candidates."
            ),
        )

    violations: list[str] = []
    for a, b in combinations(score_by_id, 2):
        rel_a, rel_b = relevance_by_id[a], relevance_by_id[b]
        score_a, score_b = score_by_id[a], score_by_id[b]
        if rel_a > rel_b and score_a < score_b:
            violations.append(f"{a}(rel={rel_a}, score={score_a}) < {b}(rel={rel_b}, score={score_b})")
        elif rel_b > rel_a and score_b < score_a:
            violations.append(f"{b}(rel={rel_b}, score={score_b}) < {a}(rel={rel_a}, score={score_a})")

    if violations:
        return CaseResult(
            name="score_contract",
            passed=False,
            detail="scores not monotonic in relevance: " + "; ".join(violations),
        )

    return CaseResult(
        name="score_contract",
        passed=True,
        detail=(
            f"score_method={candidates.score_method!r} declared; "
            f"{len(score_by_id)} scores monotonic in relevance."
        ),
    )
