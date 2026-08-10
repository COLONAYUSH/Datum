"""Conformance probe vocabulary: the synthetic fragment/row/predicate shapes
the four conformance cases hand to an Operator's real `plan()`/`execute()`.

This is deliberately NOT the real planner fragment type. `Operator.plan()`
takes `fragment: Any` (kernel.operator) precisely because the compiled,
live-index fragment planner/ builds is out of scope for this suite (a later
build phase, per FRAMEWORK.md's Plan section) — but a conformance gate that
runs at `datum.register_operator()` time cannot wait for that to exist. So
this module defines the minimal probe vocabulary the suite itself needs:
enough shape (rows with filterable metadata, a boolean filter algebra,
a tenancy predicate, an entitlement snapshot) to exercise filter algebra,
score contracts, and tenancy/entitlement fail-closed semantics against any
Operator's actual `plan()`/`execute()` methods, without provisioning live
infrastructure. An operator that wants to register reads
`ConformanceFragment`'s fields the same way it would read its real compiled
fragment; the suite never reaches around `plan()`/`execute()` to inspect an
operator's internals directly. Any operator implementation choosing to
register through `datum.register_operator()` must be able to interpret this
fragment shape when the suite passes it in — that is the (informal) contract
this module fixes by construction.

CaseResult is the typed pass/fail every case function returns. Kept
alongside the probe vocabulary rather than in suite.py because both
`operators.conformance.suite.SuiteReport` and every module under
`operators.conformance.cases/` depend on it, and neither should import from
the other's usual home.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Mapping

from datum.kernel.ids import PolicyID, RecordID
from datum.kernel.principal import Principal
from datum.kernel.record import ProvenanceCapsule, Record

FilterOp = Literal["eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "is_null", "is_not_null"]
BoolKind = Literal["leaf", "and", "or", "not"]


@dataclass(frozen=True)
class CaseResult:
    """One conformance case's outcome. `detail` always carries enough of the
    actual mismatch (expected vs. got, which row leaked) that a failure is
    diagnosable from the result alone — the suite has no separate log stream
    to fall back on at register_operator() time in production.
    """

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class FieldPredicate:
    """A single leaf comparison: `field <op> value` against a ProbeRow's
    `fields` mapping.
    """

    field: str
    op: FilterOp
    value: Any = None


@dataclass(frozen=True)
class BoolExpr:
    """A boolean-algebra node: either a leaf `FieldPredicate` or an AND/OR/NOT
    combinator over children. This is the same algebra CI-03's "next-gen
    requirement" names first (boolean nesting, negation, IN/NOT-IN) — both
    `ConformanceFragment.filter` (an ordinary relevance-shaped filter) and
    `TenancyPredicate.filter` (a security predicate) reuse this one type, on
    purpose: the LangChain4j #2513 defect this suite exists to catch was a
    NOT-IN clause mistranslated in the filter channel, not a separate
    "security predicate" code path with its own algebra.
    """

    kind: BoolKind
    predicate: FieldPredicate | None = None
    children: tuple["BoolExpr", ...] = ()

    @classmethod
    def leaf(cls, field: str, op: FilterOp, value: Any = None) -> "BoolExpr":
        return cls(kind="leaf", predicate=FieldPredicate(field, op, value))

    @classmethod
    def and_(cls, *children: "BoolExpr") -> "BoolExpr":
        return cls(kind="and", children=tuple(children))

    @classmethod
    def or_(cls, *children: "BoolExpr") -> "BoolExpr":
        return cls(kind="or", children=tuple(children))

    @classmethod
    def not_(cls, child: "BoolExpr") -> "BoolExpr":
        return cls(kind="not", children=(child,))


def evaluate_expr(expr: BoolExpr, fields: Mapping[str, Any]) -> bool:
    """The plain, textbook boolean/IN/NOT-IN/null semantics every case in this
    suite treats as ground truth, and the same semantics
    `fixtures.CorrectFixtureOperator` implements directly to serve as the
    positive control.

    Null-handling rule, stated once here rather than per-case: a comparison
    against a missing or `None` field never matches — this includes
    `not_in`, deliberately. `NOT-IN` over an unknown value is itself unknown
    in three-valued logic, not `TRUE`; treating it as `TRUE` (matching
    everything) is precisely the LangChain4j #2513 failure shape this
    module's null rule is written to make impossible to reproduce by
    accident in a reference implementation.
    """
    if expr.kind == "not":
        return not evaluate_expr(expr.children[0], fields)
    if expr.kind == "and":
        return all(evaluate_expr(child, fields) for child in expr.children)
    if expr.kind == "or":
        return any(evaluate_expr(child, fields) for child in expr.children)
    assert expr.predicate is not None  # kind == "leaf" is the only remaining case
    return _evaluate_predicate(expr.predicate, fields)


def _evaluate_predicate(pred: FieldPredicate, fields: Mapping[str, Any]) -> bool:
    present = pred.field in fields and fields[pred.field] is not None
    if pred.op == "is_null":
        return not present
    if pred.op == "is_not_null":
        return present
    if not present:
        return False
    value = fields[pred.field]
    if pred.op == "eq":
        return bool(value == pred.value)
    if pred.op == "ne":
        return bool(value != pred.value)
    if pred.op == "in":
        return value in pred.value
    if pred.op == "not_in":
        return value not in pred.value
    if pred.op == "gt":
        return value > pred.value
    if pred.op == "gte":
        return value >= pred.value
    if pred.op == "lt":
        return value < pred.value
    if pred.op == "lte":
        return value <= pred.value
    raise ValueError(f"unknown FilterOp {pred.op!r}")  # pragma: no cover - exhaustive Literal above


@dataclass(frozen=True)
class ProbeRow:
    """One synthetic row a conformance case hands an Operator: a real kernel
    `Record` plus the filterable metadata `Operator.plan()`/`execute()` would
    normally derive from a live index rather than a Python dict, plus a
    ground-truth `relevance` used only by `cases/score_contract.py`.
    """

    record: Record
    fields: dict[str, Any] = field(default_factory=dict)
    relevance: float = 0.0


@dataclass(frozen=True)
class TenancyPredicate:
    """A namespace/entitlement filter `Operator.execute()` must apply per row,
    with fail-closed semantics on two distinct failure shapes:

    `filter` is a `BoolExpr` like any other — the point of typing this
    separately from `ConformanceFragment.filter` is only so a case can
    assert fail-closed behavior *by convention at the Operator level*, one
    layer below where `kernel.plan.PlanStep.fails_closed` pins the identical
    distinction on the compiled `Plan`; the boolean algebra itself is
    identical, which is exactly why `cases/tenancy_fail_closed.py`'s NOT-IN
    scenario reproduces LangChain4j #2513 faithfully rather than testing a
    different mechanism.

    `unevaluable_row_ids` simulates the case where the tenancy/entitlement
    data needed to decide a row cannot be fetched at all (an entitlement
    lookup times out, or the row is missing the field the predicate needs
    upstream of this probe) — genuinely distinct from "the predicate
    evaluates to False": the operator receives no answer and must still
    exclude, never default to include.
    """

    filter: BoolExpr
    unevaluable_row_ids: frozenset[str] = frozenset()

    def evaluate(self, row: ProbeRow) -> bool:
        if str(row.record.id) in self.unevaluable_row_ids:
            raise RuntimeError(
                f"tenancy predicate unevaluable for row {row.record.id!r} "
                "(simulated entitlement-lookup failure)"
            )
        return evaluate_expr(self.filter, row.fields)


@dataclass(frozen=True)
class EntitlementSnapshot:
    """A point-in-time snapshot of which entitlement values (role/trial/tier)
    the calling principal currently holds, gating any row whose
    `entitlement_field` requires a value in `granted`.

    Per FRAMEWORK.md's CI-03 addendum (`Operator` section): staleness is a
    typed, checkable condition, not identity-provider freshness Datum owns
    (Identity/ACL-sync stays explicit anti-scope) — `is_stale` is the only
    thing an Operator is obligated to check before trusting this snapshot at
    all. `now` is a fixed synthetic "current time" rather than the wall
    clock, deliberately: a conformance probe must be deterministic, and
    real staleness evaluation happens against whatever clock the caller
    supplies at plan time, not against `datetime.now()` baked into this
    probe type.
    """

    granted: frozenset[str]
    entitlement_field: str
    as_of: datetime
    max_staleness: timedelta
    now: datetime

    @property
    def is_stale(self) -> bool:
        return (self.now - self.as_of) > self.max_staleness

    def permits(self, row: ProbeRow) -> bool:
        """True only when the snapshot is fresh AND the row's entitlement
        field is among the granted values. Staleness always wins: a stale
        snapshot permits nothing, regardless of what the row would otherwise
        require — the fail-closed rule `cases/entitlement_staleness.py`
        checks an Operator actually implements.
        """
        if self.is_stale:
            return False
        return row.fields.get(self.entitlement_field) in self.granted


@dataclass(frozen=True)
class ConformanceFragment:
    """The synthetic query fragment conformance cases hand to
    `Operator.plan()`. See this module's own docstring for why it exists and
    what it deliberately is not.
    """

    rows: tuple[ProbeRow, ...]
    filter: BoolExpr | None = None
    tenancy: TenancyPredicate | None = None
    entitlement: EntitlementSnapshot | None = None
    score_method: str = "conformance-fixture-v1"


def make_record(record_id: str, namespace: str, *, writer_id: str = "conformance-fixture") -> Record:
    """Builds a minimal, valid `kernel.record.Record` for a conformance probe.

    Every conformance case needs real `Record` instances — `Operator.execute()`
    returns `CandidateSet.records`, a `tuple[Record, ...]` per kernel.operator
    — but there is no live writepath here to produce one from. This is a
    probe-only construction helper, not a substitute for
    `writepath.orchestrator`, and every field beyond `id`/`namespace` is a
    fixed, deterministic placeholder chosen only so the type checks; no case
    reads `body`, `provenance.source_version`, or `parser_confidence` for any
    assertion.
    """
    fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Record(
        id=RecordID(record_id),
        kind="chunk",
        body=f"conformance probe row {record_id}",
        valid_from=fixed_now,
        valid_to=None,
        tx_from=fixed_now,
        tx_to=None,
        provenance=ProvenanceCapsule(
            writer=Principal(id=writer_id, namespace=namespace),
            ingestion_path="conformance-probe",
            authority_tier="UNVERIFIED",
            trust_class="untrusted",
            source_version="conformance-fixture-v1",
        ),
        policy_id=PolicyID("conformance-fixture-policy"),
        parser_confidence=None,
    )
