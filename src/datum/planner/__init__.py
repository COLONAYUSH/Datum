"""datum.planner: L6, the plan compiler and trace store.

`PlanCompiler` (compiler.py) turns a request into a `Plan` with a bound
executor, resolving the coarse namespace ACL first. `TraceStore` (trace.py)
persists each executed plan and its full result, so a plan is replayable by
record. EXPLAIN lives on the kernel `Plan` type itself (`plan.explain()`).
"""

from datum.planner.compiler import PlanCompiler
from datum.planner.trace import TraceStore

__all__ = ["PlanCompiler", "TraceStore"]
