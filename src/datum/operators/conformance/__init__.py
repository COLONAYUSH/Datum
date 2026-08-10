"""operators.conformance: the mandatory suite that gates whether a physical
Operator may register at all -- filter algebra, score contract, tenancy
fail-closed (including the LangChain4j #2513 NOT-IN case), and entitlement
staleness fail-closed. See suite.py for the gate itself, cases/ for the four
mandatory checks, types.py for the shared probe vocabulary, and fixtures.py
for this suite's own positive/negative controls.

Re-exported here for convenience (`from datum.operators.conformance import
ConformanceSuite`); NOT re-exported from the top-level `datum` package --
that addition belongs to whoever builds `datum.register_operator()` and
updates `datum/__init__.py`'s own budget accounting, per that module's own
comment reserving the slot.
"""

from __future__ import annotations

from datum.operators.conformance.suite import ConformanceSuite, SuiteReport
from datum.operators.conformance.types import CaseResult

__all__ = ["CaseResult", "ConformanceSuite", "SuiteReport"]
