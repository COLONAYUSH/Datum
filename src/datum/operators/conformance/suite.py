"""ConformanceSuite: the gate `datum.register_operator()` calls before
admitting a physical Operator at all.

`register_operator()` is built later, by a different module, at the call
site named in kernel.operator's own module docstring
("An Operator cannot be registered without first passing
operators.conformance.suite.ConformanceSuite.run() -- that gate lives at
the call site of datum.register_operator(), not here"). This module only
implements the gate itself: `ConformanceSuite.run(operator)` executes all
four mandatory cases and refuses to hide a single failure inside an
aggregate boolean -- `SuiteReport.results` carries every case's own
`CaseResult`, and `SuiteReport.failures` is a convenience view over the
ones that didn't pass, so FRAMEWORK.md's own illustrative call
(`assert report.passed, report.failures`) type-checks against this
implementation exactly as written.

Plain functions and a stateless dispatch table, zero `import pytest`:
`ConformanceSuite.run()` must be callable at production registration time
with no test-framework dependency. Pytest only wraps this suite for CI
visibility -- see tests/conformance/test_suite_self_check.py -- it does not
contain any of this suite's logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from datum.kernel.operator import Operator
from datum.operators.conformance.cases import (
    entitlement_staleness,
    filter_algebra,
    score_contract,
    tenancy_fail_closed,
)
from datum.operators.conformance.types import CaseResult

_CASES = (
    filter_algebra.check,
    score_contract.check,
    tenancy_fail_closed.check,
    entitlement_staleness.check,
)


@dataclass(frozen=True)
class SuiteReport:
    """The suite's own aggregate result. `results` always has one entry per
    mandatory case, in the order `ConformanceSuite.run()` executed them,
    regardless of whether earlier cases failed -- one case's failure never
    short-circuits the rest, because a registration decision should be made
    against the operator's complete conformance picture, not the first
    thing that happened to break.
    """

    passed: bool
    results: tuple[CaseResult, ...]

    @property
    def failures(self) -> tuple[CaseResult, ...]:
        return tuple(result for result in self.results if not result.passed)


class ConformanceSuite:
    """The mandatory suite every physical Operator must pass before
    `datum.register_operator()` admits it: filter algebra, score contract,
    tenancy fail-closed (including the LangChain4j #2513 NOT-IN case), and
    entitlement staleness fail-closed. A hard registration refusal on
    failure, per FRAMEWORK.md's `Operator` section -- not an aspirational
    test file a mistranslating backend can ship without ever running.
    """

    @staticmethod
    def run(operator: Operator) -> SuiteReport:
        results = tuple(case(operator) for case in _CASES)
        return SuiteReport(passed=all(result.passed for result in results), results=results)
