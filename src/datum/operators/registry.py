"""OperatorRegistry: the conformance gate at registration time.

`register(operator)` runs the full ConformanceSuite against the operator and
REFUSES registration (raises ConformanceError, naming the failed cases) if it
does not pass — the literal "a mistranslating backend cannot register"
mechanism from FRAMEWORK.md §Core abstractions #4. The suite call needs no
test framework and no live infrastructure (it runs the operator against
synthetic fragments), so this gate runs in production, not just in CI.

The registry is held by the composition root (Corpus), not module-global:
which operators are live is per-deployment state, and module-global mutable
state is exactly what the kernel's Plan design avoids (decisions.md #8).
"""

from __future__ import annotations

from datum.kernel.errors import ConformanceError
from datum.kernel.operator import Operator
from datum.operators.conformance.suite import ConformanceSuite


class OperatorRegistry:
    def __init__(self) -> None:
        self._operators: dict[str, Operator] = {}

    def register(self, operator: Operator) -> None:
        report = ConformanceSuite.run(operator)
        if not report.passed:
            failed = ", ".join(r.name for r in report.results if not r.passed)
            details = "; ".join(
                f"{r.name}: {r.detail}" for r in report.results if not r.passed
            )
            raise ConformanceError(
                f"operator {operator.kind!r} refused registration — failed conformance "
                f"case(s): {failed}. {details}"
            )
        self._operators[operator.kind] = operator

    def get(self, kind: str) -> Operator:
        return self._operators[kind]

    def kinds(self) -> tuple[str, ...]:
        return tuple(self._operators)

    def close(self) -> None:
        """Close any registered operator that holds resources. Operators that
        open a lazy database connection (bm25, ann) expose `close()`; grep
        reads through the shared ground store and has nothing of its own.
        Best-effort: one operator's close failure never blocks the rest.
        """
        for operator in self._operators.values():
            closer = getattr(operator, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:  # pragma: no cover - defensive teardown
                    pass
